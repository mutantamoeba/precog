"""Unit tests for crud_canonical_match_overrides module — Cohort 3 slot 0074.

Covers (function-by-function per build spec § 6 unit test list):
    - create_override: happy paths (MUST_MATCH + MUST_NOT_MATCH),
      polarity-pairing rule (raises BEFORE INSERT for both wrong-pairing
      branches), Pattern 73 SSOT real-guard on polarity, human-only
      prefix invariant (Holden Item 1 P1 — negative path asserts NO log
      row written), length boundary on created_by, empty/whitespace-only
      reason rejection, manual_v1-on-human-decided-actions convention
      verification.
    - delete_override: empty/whitespace-only reason rejection, log-row
      write shape, LookupError on missing override_id.

Pattern 73 SSOT real-guard discipline (#1085 finding #2 strengthening):
    Both ``POLARITY_VALUES`` and ``DECIDED_BY_PREFIXES`` are imported and
    USED in real-guard ValueError-raising validation in the SUT.  These
    tests assert that the validation fires.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that
the real query returns.  Mocks of ``get_cursor`` use the
``__enter__`` / ``__exit__`` protocol consistent with sibling unit tests.

Reference:
    - ``src/precog/database/crud_canonical_match_overrides.py``
    - ``src/precog/database/alembic/versions/0074_canonical_match_overrides_reviews.py``
    - ``tests/unit/database/test_crud_canonical_match_log_unit.py``
      (style reference)
    - ADR-118 v2.41 + S82 build spec § 6
"""

from unittest.mock import MagicMock, patch

import pytest

from precog.database.constants import DECIDED_BY_PREFIXES, POLARITY_VALUES
from precog.database.crud_canonical_match_overrides import (
    create_override,
    delete_override,
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


# =============================================================================
# create_override — happy paths
# =============================================================================


@pytest.mark.unit
class TestCreateOverrideHappyPaths:
    """Happy paths exercise both polarity branches per Ripley false-pass-hunt frame."""

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_create_override_must_match_with_canonical_id_valid(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """polarity='MUST_MATCH' + canonical_market_id=<int> succeeds."""
        mock_get_manual_v1.return_value = 1
        mock_append_log.return_value = 99
        mock_cursor = _wire_get_cursor_mock(mock_get_cursor_factory, returning_id=42)

        result = create_override(
            platform_market_id=10,
            canonical_market_id=7,
            polarity="MUST_MATCH",
            reason="Operator confirmed canonical for this market",
            created_by="human:eric",
        )

        assert result == 42
        mock_get_cursor_factory.assert_called_once_with(commit=True)
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO canonical_match_overrides" in sql
        assert "RETURNING id" in sql
        assert params[0] == 10  # platform_market_id
        assert params[1] == 7  # canonical_market_id
        assert params[2] == "MUST_MATCH"
        assert params[3] == "Operator confirmed canonical for this market"
        assert params[4] == "human:eric"

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_create_override_must_not_match_with_null_canonical_id_valid(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """polarity='MUST_NOT_MATCH' + canonical_market_id=None succeeds."""
        mock_get_manual_v1.return_value = 1
        mock_append_log.return_value = 99
        mock_cursor = _wire_get_cursor_mock(mock_get_cursor_factory, returning_id=42)

        result = create_override(
            platform_market_id=10,
            canonical_market_id=None,
            polarity="MUST_NOT_MATCH",
            reason="This market is NOT in any canonical group",
            created_by="human:eric",
        )

        assert result == 42
        params = mock_cursor.execute.call_args[0][1]
        assert params[1] is None  # canonical_market_id
        assert params[2] == "MUST_NOT_MATCH"


# =============================================================================
# create_override — polarity-pairing rule
# =============================================================================


@pytest.mark.unit
class TestCreateOverrideRejectsInvalidPolarityPairing:
    """Both wrong-pairing branches MUST be exercised per Ripley false-pass-hunt frame."""

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_rejects_must_match_with_null_canonical_id(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """polarity='MUST_MATCH' + canonical_market_id=None raises ValueError."""
        with pytest.raises(ValueError, match=r"MUST_MATCH.*non-NULL"):
            create_override(
                platform_market_id=10,
                canonical_market_id=None,
                polarity="MUST_MATCH",
                reason="bad pairing",
                created_by="human:eric",
            )
        mock_get_cursor_factory.assert_not_called()
        mock_append_log.assert_not_called()

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_rejects_must_not_match_with_non_null_canonical_id(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """polarity='MUST_NOT_MATCH' + canonical_market_id=<int> raises ValueError."""
        with pytest.raises(ValueError, match=r"MUST_NOT_MATCH.*NULL"):
            create_override(
                platform_market_id=10,
                canonical_market_id=7,
                polarity="MUST_NOT_MATCH",
                reason="bad pairing",
                created_by="human:eric",
            )
        mock_get_cursor_factory.assert_not_called()
        mock_append_log.assert_not_called()


# =============================================================================
# create_override — Pattern 73 SSOT polarity vocabulary
# =============================================================================


@pytest.mark.unit
class TestCreateOverrideRejectsInvalidPolarity:
    """Pattern 73 SSOT real-guard validation on polarity."""

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_rejects_invalid_polarity(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """polarity not in POLARITY_VALUES raises ValueError before SQL.

        Pattern 73 SSOT real-guard: POLARITY_VALUES import is USED in
        actual validation (NOT side-effect-only #noqa: F401 import).
        """
        for bad_polarity in (
            "WRONG",
            "must_match",  # wrong case
            "MUST",
            "match",
            "",
        ):
            with pytest.raises(ValueError, match="POLARITY_VALUES"):
                create_override(
                    platform_market_id=10,
                    canonical_market_id=7,
                    polarity=bad_polarity,
                    reason="bad polarity",
                    created_by="human:eric",
                )
        mock_get_cursor_factory.assert_not_called()
        mock_append_log.assert_not_called()


# =============================================================================
# create_override — human-only invariant (Holden Item 1 P1 negative path)
# =============================================================================


@pytest.mark.unit
class TestCreateOverrideRejectsNonHumanCreatedByPrefix:
    """Overrides are human-only by definition.

    Per Holden re-engagement Item 1 (P1): the human-only convention must
    have bidirectional anchoring — enforced at the CRUD-call site AND
    asserted to NOT WRITE A LOG ROW when the negative path fires.  The
    parallel integration test will assert the convention is observable
    from the LOG read-back side.
    """

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_rejects_non_human_created_by_prefix_no_log_row_written(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """Per Holden Item 1 P1: non-human created_by raises BEFORE log row written.

        Negative path proves the human-only invariant has bidirectional
        anchoring: the validation fires AND no audit-ledger row is
        written.  The parallel integration test confirms the convention
        is observable from the canonical_match_log read-back side.
        """
        for bad_creator in (
            "service:foo",  # in canonical taxonomy but not human
            "system:bar",  # in canonical taxonomy but not human
            "eric",  # no prefix
            "User:eric",  # wrong-case prefix
            "operator:bob",  # not in canonical taxonomy
            "",  # empty
        ):
            with pytest.raises(ValueError, match="'human:'"):
                create_override(
                    platform_market_id=10,
                    canonical_market_id=7,
                    polarity="MUST_MATCH",
                    reason="some reason",
                    created_by=bad_creator,
                )
        # No SQL was ever attempted — neither override INSERT nor log row.
        mock_get_cursor_factory.assert_not_called()
        mock_append_log.assert_not_called()


@pytest.mark.unit
class TestCreateOverrideRejectsCreatedByOver64Chars:
    """Boundary validation per #1085 finding #3 — VARCHAR(64) discipline at CRUD layer."""

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_rejects_created_by_over_64_chars(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """created_by length > 64 raises ValueError before SQL."""
        too_long = "human:" + ("x" * 60)
        assert len(too_long) > 64
        with pytest.raises(ValueError, match=r"VARCHAR\(64\)"):
            create_override(
                platform_market_id=10,
                canonical_market_id=7,
                polarity="MUST_MATCH",
                reason="some reason",
                created_by=too_long,
            )
        mock_get_cursor_factory.assert_not_called()
        mock_append_log.assert_not_called()


# =============================================================================
# create_override — empty / whitespace-only reason rejection
# =============================================================================


@pytest.mark.unit
class TestCreateOverrideRejectsEmptyReason:
    """#1085 finding #7 inheritance — slot-0072 retire_reason='' empty-string-acceptance pattern."""

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_rejects_empty_reason(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """reason='' raises ValueError before SQL (#1085 finding #7)."""
        with pytest.raises(ValueError, match="cannot be empty"):
            create_override(
                platform_market_id=10,
                canonical_market_id=7,
                polarity="MUST_MATCH",
                reason="",
                created_by="human:eric",
            )
        mock_get_cursor_factory.assert_not_called()
        mock_append_log.assert_not_called()

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_rejects_whitespace_only_reason(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """reason='   ' (whitespace-only) raises ValueError before SQL."""
        with pytest.raises(ValueError, match="cannot be empty"):
            create_override(
                platform_market_id=10,
                canonical_market_id=7,
                polarity="MUST_MATCH",
                reason="   \t\n   ",
                created_by="human:eric",
            )
        mock_get_cursor_factory.assert_not_called()
        mock_append_log.assert_not_called()


# =============================================================================
# create_override — manual_v1-on-human-decided-actions convention
# =============================================================================


@pytest.mark.unit
class TestCreateOverrideWritesLogRowWithManualV1AlgorithmId:
    """The convention test: log row carries algorithm_id=manual_v1.id.

    Per Holden Item 1 (P1) bidirectional anchoring: the convention is
    observable from BOTH the CRUD-call site (this test) AND the LOG
    read-back side (the parallel integration test).
    """

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_create_override_writes_log_row_with_manual_v1_algorithm_id(
        self, mock_get_cursor_factory, mock_append_log, mock_get_manual_v1
    ):
        """create_override writes log row with manual_v1.id + action='override' + decided_by=human:..."""
        mock_get_manual_v1.return_value = 1
        mock_append_log.return_value = 99
        _wire_get_cursor_mock(mock_get_cursor_factory, returning_id=42)

        create_override(
            platform_market_id=10,
            canonical_market_id=7,
            polarity="MUST_MATCH",
            reason="testing the convention",
            created_by="human:eric",
        )

        mock_append_log.assert_called_once()
        call_kwargs = mock_append_log.call_args.kwargs
        assert call_kwargs["action"] == "override"
        assert call_kwargs["link_id"] is None  # overrides are link-independent
        assert call_kwargs["platform_market_id"] == 10
        assert call_kwargs["canonical_market_id"] == 7
        assert call_kwargs["algorithm_id"] == 1  # manual_v1.id placeholder
        assert call_kwargs["decided_by"] == "human:eric"
        assert call_kwargs["decided_by"].startswith("human:")
        assert call_kwargs["note"] == "testing the convention"
        assert call_kwargs["confidence"] is None  # human override has no confidence


# =============================================================================
# delete_override
# =============================================================================


@pytest.mark.unit
class TestDeleteOverrideValidation:
    """delete_override validation surface."""

    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_rejects_empty_reason(self, mock_get_cursor_factory):
        """delete_override(reason='') raises ValueError before SQL."""
        with pytest.raises(ValueError, match="cannot be empty"):
            delete_override(42, deleted_by="human:eric", reason="")
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_rejects_non_human_deleted_by(self, mock_get_cursor_factory):
        """delete_override with non-human deleted_by raises ValueError."""
        with pytest.raises(ValueError, match="'human:'"):
            delete_override(42, deleted_by="service:foo", reason="cleanup")
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_raises_lookup_error_on_missing_override_id(
        self,
        mock_get_cursor_factory,
        mock_append_log,
        mock_get_manual_v1,
    ):
        """Non-existent override_id raises LookupError, not silent no-op.

        Per Glokta F1 atomicity refactor: the pre-DELETE attribution
        SELECT runs on the same cursor as the DELETE + log INSERT.
        Mock the cursor's fetchone() to return None on the SELECT call
        (simulating "row not found"); the SUT must raise before the
        DELETE / log-INSERT runs.
        """
        mock_get_manual_v1.return_value = 1
        mock_cursor = MagicMock()
        # First (and only) fetchone() call inside the cursor block — the
        # SELECT pre-DELETE attribution returns None.
        mock_cursor.fetchone.return_value = None
        mock_get_cursor_factory.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor_factory.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(LookupError, match="does not exist"):
            delete_override(99999, deleted_by="human:eric", reason="missing")
        # The SELECT executed; the DELETE + log-INSERT did NOT.
        mock_append_log.assert_not_called()


@pytest.mark.unit
class TestDeleteOverrideWritesLogRow:
    """delete_override writes a log row with action='override' + 'deleted: ' note prefix."""

    @patch("precog.database.crud_canonical_match_overrides.get_manual_v1_algorithm_id")
    @patch("precog.database.crud_canonical_match_overrides._append_match_log_row_in_cursor")
    @patch("precog.database.crud_canonical_match_overrides.get_cursor")
    def test_delete_override_writes_log_row_shape(
        self,
        mock_get_cursor_factory,
        mock_append_log,
        mock_get_manual_v1,
    ):
        """Verify the audit row carries the canonical override-delete shape.

        Per Glokta F1 atomicity refactor: the pre-DELETE attribution
        SELECT, the DELETE, and the log-INSERT all run on the same
        cursor.  Mock ``cur.fetchone()`` to return the attribution dict
        (Pattern 43 fidelity).
        """
        mock_get_manual_v1.return_value = 1
        mock_append_log.return_value = 99
        mock_cursor = MagicMock()
        # Pre-DELETE attribution SELECT returns the row.
        mock_cursor.fetchone.return_value = {
            "platform_market_id": 10,
            "canonical_market_id": 7,
            "polarity": "MUST_MATCH",
        }
        mock_get_cursor_factory.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor_factory.return_value.__exit__ = MagicMock(return_value=False)

        delete_override(42, deleted_by="human:eric", reason="cleanup")

        mock_append_log.assert_called_once()
        # First positional arg is the shared cursor object.
        assert mock_append_log.call_args.args[0] is mock_cursor
        call_kwargs = mock_append_log.call_args.kwargs
        assert call_kwargs["action"] == "override"
        assert call_kwargs["link_id"] is None
        assert call_kwargs["platform_market_id"] == 10
        assert call_kwargs["canonical_market_id"] == 7
        assert call_kwargs["algorithm_id"] == 1  # manual_v1.id placeholder
        assert call_kwargs["decided_by"] == "human:eric"
        # The "deleted: " prefix on note is the convention discriminator
        # (the action vocabulary is fixed at 7 values; note column carries
        # the create-vs-delete distinction).
        assert call_kwargs["note"].startswith("deleted: ")
        assert "cleanup" in call_kwargs["note"]


# =============================================================================
# Sentinel: POLARITY_VALUES + DECIDED_BY_PREFIXES are referenced above for
# parametrize lists + assertion regex matching.  This keeps the imports as
# real-guard usage from the test side.
# =============================================================================


@pytest.mark.unit
def test_imports_used_as_real_guards():
    """Pattern 73 SSOT lockstep meta-test: POLARITY_VALUES contains the canonical 2-value set."""
    assert set(POLARITY_VALUES) == {"MUST_MATCH", "MUST_NOT_MATCH"}
    # human-only invariant relies on 'human:' being a member of the broader taxonomy.
    assert "human:" in DECIDED_BY_PREFIXES
