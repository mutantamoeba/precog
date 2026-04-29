"""Unit tests for crud_canonical_match_reviews module — Cohort 3 slot 0074.

Covers (function-by-function per build spec § 6 unit test list):
    - create_review: happy path + flagged_reason length boundary.
    - transition_review: state-vocabulary validation (Pattern 73 SSOT
      real-guard), reviewer-prefix validation, reviewer length boundary,
      self-transition rejection (Holden Item 3 P2 — parametrized over
      all 4 self-transition pairs), state-machine matrix violations,
      log-row write coupling for approve/reject (and NO log row for
      pending/needs_info).

Pattern 73 SSOT real-guard discipline (#1085 finding #2 strengthening):
    Both ``REVIEW_STATE_VALUES`` and ``DECIDED_BY_PREFIXES`` are imported
    and USED in real-guard ValueError-raising validation in the SUT.
    These tests assert that the validation fires.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that
the real query returns.  Mocks of ``get_cursor`` use the
``__enter__`` / ``__exit__`` protocol consistent with sibling unit tests
(test_crud_canonical_match_log_unit.py).

Reference:
    - ``src/precog/database/crud_canonical_match_reviews.py``
    - ``src/precog/database/alembic/versions/0074_canonical_match_overrides_reviews.py``
    - ``tests/unit/database/test_crud_canonical_match_log_unit.py``
      (style reference)
    - ADR-118 v2.41 + S82 build spec § 6
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from precog.database.constants import DECIDED_BY_PREFIXES, REVIEW_STATE_VALUES
from precog.database.crud_canonical_match_reviews import (
    create_review,
    transition_review,
)


def _wire_get_cursor_mock(mock_get_cursor_factory: MagicMock, returning_id: int = 99) -> MagicMock:
    """Wire a @patch-supplied get_cursor mock so it acts as a context manager.

    Returns the inner ``mock_cursor`` that the SUT sees as the yielded
    cursor object.  Pattern 43 fidelity: ``fetchone()`` returns a
    RealDictCursor-style dict (``{"id": <int>}``) matching the real
    INSERT ... RETURNING id shape.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id": returning_id}
    mock_get_cursor_factory.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_cursor_factory.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


def _wire_transition_cursor_mock(
    mock_get_cursor_factory: MagicMock,
    *,
    review_state: str,
    link_id: int = 100,
    canonical_market_id: int | None = 7,
    platform_market_id: int | None = 42,
) -> MagicMock:
    """Wire a get_cursor mock for the transition_review JOIN-SELECT shape.

    Per Glokta F1+F5 atomicity refactor: transition_review's SELECT pulls
    review_state alongside the link's (canonical_market_id,
    platform_market_id) via a single LEFT JOIN.  The cursor's
    ``fetchone()`` returns a 4-key dict.  Pattern 43 fidelity.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "review_state": review_state,
        "link_id": link_id,
        "link_canonical_market_id": canonical_market_id,
        "link_platform_market_id": platform_market_id,
    }
    mock_get_cursor_factory.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_cursor_factory.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


# =============================================================================
# create_review
# =============================================================================


@pytest.mark.unit
class TestCreateReviewValidInputs:
    """Happy-path: valid inputs produce a single INSERT with returned id."""

    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_create_review_valid_inputs(self, mock_get_cursor_factory):
        """create_review INSERTs and returns the id when all inputs valid."""
        mock_cursor = _wire_get_cursor_mock(mock_get_cursor_factory, returning_id=42)

        result = create_review(link_id=100, flagged_reason="low confidence")

        assert result == 42
        mock_get_cursor_factory.assert_called_once_with(commit=True)
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO canonical_match_reviews" in sql
        assert "RETURNING id" in sql
        # Default review_state is 'pending' in the SQL literal (NOT a parameter).
        assert "'pending'" in sql
        assert params == (100, "low confidence")

    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_create_review_flagged_reason_none_passes_through(self, mock_get_cursor_factory):
        """flagged_reason=None is forwarded as NULL."""
        mock_cursor = _wire_get_cursor_mock(mock_get_cursor_factory, returning_id=42)

        create_review(link_id=100)  # default flagged_reason=None

        params = mock_cursor.execute.call_args[0][1]
        assert params == (100, None)


@pytest.mark.unit
class TestCreateReviewRejectsFlaggedReasonOver256Chars:
    """Boundary validation per #1085 finding #3 — VARCHAR(256) discipline at CRUD layer."""

    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_create_review_rejects_flagged_reason_over_256_chars(self, mock_get_cursor_factory):
        """flagged_reason length > 256 raises ValueError before SQL."""
        too_long = "x" * 257
        with pytest.raises(ValueError, match=r"VARCHAR\(256\)"):
            create_review(link_id=100, flagged_reason=too_long)
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_create_review_accepts_flagged_reason_exactly_256_chars(self, mock_get_cursor_factory):
        """flagged_reason exactly 256 chars is the boundary — accepted, not rejected."""
        mock_cursor = _wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)

        exactly_256 = "x" * 256
        create_review(link_id=100, flagged_reason=exactly_256)
        mock_cursor.execute.assert_called_once()


# =============================================================================
# transition_review — Pattern 73 SSOT real-guard validation
# =============================================================================


@pytest.mark.unit
class TestTransitionReviewRejectsInvalidState:
    """Pattern 73 SSOT real-guard validation on new_state."""

    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    @patch("precog.database.crud_canonical_match_reviews.fetch_one")
    def test_rejects_invalid_state(self, mock_fetch_one, mock_get_cursor_factory):
        """new_state not in REVIEW_STATE_VALUES raises ValueError before SQL.

        Pattern 73 SSOT real-guard: REVIEW_STATE_VALUES import is USED in
        actual validation (NOT side-effect-only #noqa: F401 import).
        """
        for bad_state in ("not_a_real_state", "PENDING", "done", ""):
            with pytest.raises(ValueError, match="REVIEW_STATE_VALUES"):
                transition_review(
                    review_id=42,
                    new_state=bad_state,
                    reviewer="human:eric",
                )
        # No SQL was ever attempted (validation fires before fetch_one + cursor).
        mock_fetch_one.assert_not_called()
        mock_get_cursor_factory.assert_not_called()


@pytest.mark.unit
class TestTransitionReviewRejectsInvalidReviewerPrefix:
    """Pattern 73 SSOT real-guard validation on reviewer prefix."""

    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    @patch("precog.database.crud_canonical_match_reviews.fetch_one")
    def test_rejects_invalid_reviewer_prefix(self, mock_fetch_one, mock_get_cursor_factory):
        """reviewer missing canonical prefix raises ValueError before SQL."""
        for bad_reviewer in (
            "eric",  # no prefix
            "User:eric",  # wrong-case prefix
            "operator:bob",  # not in canonical taxonomy
            "human",  # no colon
            "",  # empty
        ):
            with pytest.raises(ValueError, match="DECIDED_BY_PREFIXES"):
                transition_review(
                    review_id=42,
                    new_state="approved",
                    reviewer=bad_reviewer,
                )
        mock_fetch_one.assert_not_called()
        mock_get_cursor_factory.assert_not_called()


@pytest.mark.unit
class TestTransitionReviewRejectsReviewerOver64Chars:
    """Boundary validation per #1085 finding #3 — VARCHAR(64) discipline at CRUD layer."""

    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    @patch("precog.database.crud_canonical_match_reviews.fetch_one")
    def test_rejects_reviewer_over_64_chars(self, mock_fetch_one, mock_get_cursor_factory):
        """reviewer length > 64 chars raises ValueError before SQL."""
        too_long = "human:" + ("x" * 60)
        assert len(too_long) > 64
        with pytest.raises(ValueError, match=r"VARCHAR\(64\)"):
            transition_review(
                review_id=42,
                new_state="approved",
                reviewer=too_long,
            )
        mock_fetch_one.assert_not_called()
        mock_get_cursor_factory.assert_not_called()


# =============================================================================
# transition_review — self-transition rule (Holden Item 3 P2)
# =============================================================================


@pytest.mark.unit
class TestTransitionReviewRejectsSelfTransition:
    """Self-transition rule beats the matrix REGARDLESS of source state.

    Per Holden re-engagement Item 3 (P2): all 4 self-transition pairs
    raise ValueError, including the corner-cases where the matrix would
    naturally reject (`pending` -> `pending` is not in the pending
    allowed set anyway) AND the corner-cases where the matrix MIGHT
    naively allow (e.g., `needs_info` -> `pending` is allowed; ensures
    `pending` -> `pending` doesn't accidentally route through that path).
    """

    @pytest.mark.parametrize(
        "state",
        list(REVIEW_STATE_VALUES),
        ids=lambda s: f"self_transition_{s}",
    )
    @patch("precog.database.crud_canonical_match_reviews._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_rejects_self_transition(self, mock_get_cursor_factory, mock_append_log, state):
        """Self-transition <state> -> <state> raises ValueError for every state.

        Per Holden Item 3 (P2): the self-transition rule beats the
        matrix on the diagonal regardless of source state.  All 4 of
        ``(pending, approved, rejected, needs_info)`` self-pairs must
        raise.

        Per Glokta F1+F5 atomicity refactor: the SELECT runs inside the
        cursor block, so the cursor IS opened but the UPDATE / log-
        INSERT path is never reached.
        """
        _wire_transition_cursor_mock(mock_get_cursor_factory, review_state=state)

        with pytest.raises(ValueError, match="self-transition"):
            transition_review(
                review_id=42,
                new_state=state,
                reviewer="human:eric",
            )
        # The audit log INSERT was NOT reached.
        mock_append_log.assert_not_called()


# =============================================================================
# transition_review — state-machine matrix violations
# =============================================================================


@pytest.mark.unit
class TestTransitionReviewRejectsDisallowedStateTransitions:
    """State-machine matrix is enforced beyond the self-transition rule.

    Per build spec § 4a:
        'pending'    -> {'approved', 'rejected', 'needs_info'}
        'needs_info' -> {'approved', 'rejected', 'pending'}
        'approved'   -> {'rejected', 'needs_info'}
        'rejected'   -> {'approved', 'needs_info'}

    Notable disallowed transitions exercised here:
        'approved'   -> 'pending'  (cannot rewind to pending after approval)
        'rejected'   -> 'pending'  (cannot rewind to pending after rejection)
    """

    @pytest.mark.parametrize(
        ("current_state", "new_state"),
        [
            ("approved", "pending"),  # cannot rewind to pending
            ("rejected", "pending"),  # cannot rewind to pending
        ],
    )
    @patch("precog.database.crud_canonical_match_reviews._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_rejects_disallowed_transition(
        self,
        mock_get_cursor_factory,
        mock_append_log,
        current_state,
        new_state,
    ):
        """Disallowed forward transitions raise ValueError.

        The self-transition rule is exercised in the parametrized
        TestTransitionReviewRejectsSelfTransition class above; this
        class targets non-self disallowed transitions specifically.

        Per Glokta F1+F5 atomicity refactor: the SELECT runs inside the
        cursor block, so the cursor IS opened but the log-INSERT path
        is never reached.
        """
        _wire_transition_cursor_mock(mock_get_cursor_factory, review_state=current_state)

        with pytest.raises(ValueError, match="state transition"):
            transition_review(
                review_id=42,
                new_state=new_state,
                reviewer="human:eric",
            )
        mock_append_log.assert_not_called()

    @pytest.mark.parametrize(
        ("current_state", "new_state"),
        [
            ("pending", "approved"),
            ("pending", "rejected"),
            ("pending", "needs_info"),
            ("needs_info", "approved"),
            ("needs_info", "rejected"),
            ("needs_info", "pending"),
            ("approved", "rejected"),
            ("approved", "needs_info"),
            ("rejected", "approved"),
            ("rejected", "needs_info"),
        ],
    )
    @patch("precog.database.crud_canonical_match_reviews.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_reviews._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_accepts_allowed_transition(
        self,
        mock_get_cursor_factory,
        mock_append_log,
        mock_get_manual_v1,
        current_state,
        new_state,
    ):
        """Every allowed forward transition reaches the UPDATE call."""
        mock_get_manual_v1.return_value = 1
        mock_append_log.return_value = 99
        # JOIN SELECT returns review_state + link_id + link's
        # canonical_market_id + platform_market_id all in one row
        # (Glokta F5 atomicity refactor).
        _wire_transition_cursor_mock(mock_get_cursor_factory, review_state=current_state)

        # Should NOT raise.
        transition_review(
            review_id=42,
            new_state=new_state,
            reviewer="human:eric",
        )
        # UPDATE happened.
        mock_get_cursor_factory.assert_called()


# =============================================================================
# transition_review — log-row write coupling
# =============================================================================


@pytest.mark.unit
class TestTransitionReviewLogRowCoupling:
    """approve/reject transitions write a log row; pending/needs_info do NOT."""

    @patch("precog.database.crud_canonical_match_reviews.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_reviews._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_transition_to_approved_writes_log_row(
        self,
        mock_get_cursor_factory,
        mock_append_log,
        mock_get_manual_v1,
    ):
        """new_state='approved' triggers append_match_log_row(action='review_approve')."""
        mock_get_manual_v1.return_value = 1
        mock_append_log.return_value = 99
        mock_cursor = _wire_transition_cursor_mock(mock_get_cursor_factory, review_state="pending")

        transition_review(
            review_id=42,
            new_state="approved",
            reviewer="human:eric",
            reviewed_at=datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC),
        )

        mock_append_log.assert_called_once()
        # Cursor passed positionally per Glokta F1 atomicity refactor.
        assert mock_append_log.call_args.args[0] is mock_cursor
        call_kwargs = mock_append_log.call_args.kwargs
        assert call_kwargs["action"] == "review_approve"
        assert call_kwargs["link_id"] == 100
        assert call_kwargs["platform_market_id"] == 42
        assert call_kwargs["canonical_market_id"] == 7
        assert call_kwargs["algorithm_id"] == 1  # manual_v1.id placeholder
        assert call_kwargs["decided_by"] == "human:eric"

    @patch("precog.database.crud_canonical_match_reviews.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_reviews._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_transition_to_rejected_writes_log_row(
        self,
        mock_get_cursor_factory,
        mock_append_log,
        mock_get_manual_v1,
    ):
        """new_state='rejected' triggers append_match_log_row(action='review_reject')."""
        mock_get_manual_v1.return_value = 1
        mock_append_log.return_value = 99
        _wire_transition_cursor_mock(mock_get_cursor_factory, review_state="pending")

        transition_review(
            review_id=42,
            new_state="rejected",
            reviewer="human:eric",
        )

        mock_append_log.assert_called_once()
        call_kwargs = mock_append_log.call_args.kwargs
        assert call_kwargs["action"] == "review_reject"

    @patch("precog.database.crud_canonical_match_reviews.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_reviews._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_transition_to_needs_info_does_not_write_log_row(
        self,
        mock_get_cursor_factory,
        mock_append_log,
        mock_get_manual_v1,
    ):
        """new_state='needs_info' does NOT trigger append_match_log_row.

        Only resolved decisions (approved/rejected) are audit-ledger
        events.  Needs-info is intermediate.
        """
        mock_get_manual_v1.return_value = 1
        _wire_transition_cursor_mock(mock_get_cursor_factory, review_state="pending")

        transition_review(
            review_id=42,
            new_state="needs_info",
            reviewer="human:eric",
        )

        mock_append_log.assert_not_called()

    @patch("precog.database.crud_canonical_match_reviews.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_reviews._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_transition_to_pending_does_not_write_log_row(
        self,
        mock_get_cursor_factory,
        mock_append_log,
        mock_get_manual_v1,
    ):
        """new_state='pending' (re-pend from needs_info) does NOT write a log row."""
        mock_get_manual_v1.return_value = 1
        _wire_transition_cursor_mock(mock_get_cursor_factory, review_state="needs_info")

        transition_review(
            review_id=42,
            new_state="pending",
            reviewer="human:eric",
        )

        mock_append_log.assert_not_called()


# =============================================================================
# transition_review — review_id not found
# =============================================================================


@pytest.mark.unit
class TestTransitionReviewLookupErrorOnMissingReviewId:
    """LookupError surfaces before SQL UPDATE silently affects 0 rows."""

    @patch("precog.database.crud_canonical_match_reviews._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_reviews.get_cursor")
    def test_raises_lookup_error_on_missing_review_id(
        self, mock_get_cursor_factory, mock_append_log
    ):
        """Non-existent review_id raises LookupError, not silent no-op.

        Per Glokta F1+F5 atomicity refactor: the SELECT runs inside the
        cursor block.  Mock the cursor's fetchone() to return None
        (simulating "row not found"); the SUT must raise before the
        UPDATE / log-INSERT runs.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # SELECT returns no row
        mock_get_cursor_factory.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor_factory.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(LookupError, match="does not exist"):
            transition_review(
                review_id=99999,
                new_state="approved",
                reviewer="human:eric",
            )
        # The audit log INSERT was NOT reached.
        mock_append_log.assert_not_called()


# =============================================================================
# Sentinel: REVIEW_STATE_VALUES + DECIDED_BY_PREFIXES are referenced above for
# parametrize lists + assertion regex matching.  This keeps the imports as
# real-guard usage from the test side; the SUT imports them in its own
# real-guard validation per the slot-0073 strengthening convention.
# =============================================================================


@pytest.mark.unit
def test_imports_used_as_real_guards():
    """Pattern 73 SSOT lockstep meta-test: tests import the constants too.

    Asserts that DECIDED_BY_PREFIXES is iterable + that 'human:' is a member
    (load-bearing for the slot-0074 human-only invariant in
    crud_canonical_match_overrides; also used here in transition_review's
    reviewer prefix validation).
    """
    assert "human:" in DECIDED_BY_PREFIXES
    # All 4 review states present.
    assert set(REVIEW_STATE_VALUES) == {
        "pending",
        "approved",
        "rejected",
        "needs_info",
    }
