"""Unit tests for crud_canonical_match_log module — Cohort 3 slot 0073.

Covers (function-by-function):
    - append_match_log_row: happy path, action validation, decided_by prefix
      validation, decided_by length boundary (#1085 finding #3),
      confidence validation including Decimal('NaN') guard.
    - get_match_log_for_link include_orphans=False / =True query shape.

Pattern 73 SSOT real-guard discipline (#1085 finding #2 strengthening):
    Both ``ACTION_VALUES`` and ``DECIDED_BY_PREFIXES`` are imported and
    USED in real-guard ValueError-raising validation in the SUT.  These
    tests assert that the validation fires — the side-effect-only
    convention from slot 0072's ``LINK_STATE_VALUES`` does NOT survive
    into slot 0073.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that
the real query returns.  Mocks of ``get_cursor`` use the
``__enter__`` / ``__exit__`` protocol consistent with sibling unit tests.

Reference:
    - ``src/precog/database/crud_canonical_match_log.py``
    - ``src/precog/database/alembic/versions/0073_canonical_match_log.py``
    - ``tests/unit/database/test_crud_canonical_market_links_unit.py``
      (style reference)
    - ADR-118 v2.41 + v2.42 sub-amendment B + S82 build spec § 6
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from precog.database.constants import ACTION_VALUES, DECIDED_BY_PREFIXES
from precog.database.crud_canonical_match_log import (
    append_match_log_row,
    get_match_log_by_action,
    get_match_log_for_link,
    get_match_log_for_platform_market,
)
from tests.unit.database._crud_unit_helpers import wire_get_cursor_mock


def _full_log_row_dict(
    *,
    id: int = 7,
    link_id: int | None = 100,
    platform_market_id: int = 42,
    canonical_market_id: int | None = 5,
    action: str = "link",
    confidence: Decimal | None = None,
    algorithm_id: int = 1,
    features: dict | None = None,
    prior_link_id: int | None = None,
    decided_by: str = "system:test",
    decided_at: datetime | None = None,
    note: str | None = None,
    created_at: datetime | None = None,
) -> dict:
    """Build a full canonical_match_log row dict matching the real query shape.

    Pattern 43 fidelity: every key the real RETURNING / SELECT projection
    emits is present, with no extras.
    """
    if confidence is None:
        confidence = Decimal("0.987")
    if decided_at is None:
        decided_at = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    if created_at is None:
        created_at = decided_at
    return {
        "id": id,
        "link_id": link_id,
        "platform_market_id": platform_market_id,
        "canonical_market_id": canonical_market_id,
        "action": action,
        "confidence": confidence,
        "algorithm_id": algorithm_id,
        "features": features,
        "prior_link_id": prior_link_id,
        "decided_by": decided_by,
        "decided_at": decided_at,
        "note": note,
        "created_at": created_at,
    }


_ALL_COLUMNS = (
    "id",
    "link_id",
    "platform_market_id",
    "canonical_market_id",
    "action",
    "confidence",
    "algorithm_id",
    "features",
    "prior_link_id",
    "decided_by",
    "decided_at",
    "note",
    "created_at",
)


# =============================================================================
# append_match_log_row — happy path
# =============================================================================


@pytest.mark.unit
class TestAppendMatchLogRowValidInputs:
    """Happy-path: valid inputs produce a single INSERT with returned id."""

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_append_match_log_row_valid_inputs(self, mock_get_cursor_factory):
        """append_match_log_row INSERTs and returns the id when all inputs valid."""
        mock_cursor = wire_get_cursor_mock(mock_get_cursor_factory, returning_id=42)

        result = append_match_log_row(
            link_id=100,
            platform_market_id=42,
            canonical_market_id=5,
            action="link",
            confidence=Decimal("0.987"),
            algorithm_id=1,
            features={"source": "keyword_jaccard_v1"},
            prior_link_id=None,
            decided_by="service:matching-v1",
            note="initial match",
        )

        assert result == 42
        mock_get_cursor_factory.assert_called_once_with(commit=True)
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO canonical_match_log" in sql
        assert "RETURNING id" in sql
        # All 10 column slots in the INSERT.
        for col in (
            "link_id",
            "platform_market_id",
            "canonical_market_id",
            "action",
            "confidence",
            "algorithm_id",
            "features",
            "prior_link_id",
            "decided_by",
            "note",
        ):
            assert col in sql, f"INSERT must include column {col!r}"
        # features serialized to JSON text via json.dumps; cast in SQL.
        assert "::jsonb" in sql
        # Param order must match SQL placeholder order.
        assert params[0] == 100  # link_id
        assert params[1] == 42  # platform_market_id
        assert params[2] == 5  # canonical_market_id
        assert params[3] == "link"  # action
        assert params[4] == Decimal("0.987")  # confidence
        assert params[5] == 1  # algorithm_id
        assert params[6] == '{"source": "keyword_jaccard_v1"}'  # features (JSON text)
        assert params[7] is None  # prior_link_id
        assert params[8] == "service:matching-v1"  # decided_by
        assert params[9] == "initial match"  # note

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_append_match_log_row_features_none_passes_through(self, mock_get_cursor_factory):
        """features=None is forwarded as NULL (not the JSON string "null")."""
        mock_cursor = wire_get_cursor_mock(mock_get_cursor_factory, returning_id=42)

        append_match_log_row(
            link_id=None,
            platform_market_id=42,
            canonical_market_id=None,
            action="override",
            confidence=None,
            algorithm_id=1,
            features=None,
            prior_link_id=None,
            decided_by="human:eric",
        )

        params = mock_cursor.execute.call_args[0][1]
        # features is the 7th positional param (0-indexed: 6).
        assert params[6] is None, "features=None must pass as SQL NULL, not JSON 'null'"

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_append_match_log_row_confidence_none_passes_through(self, mock_get_cursor_factory):
        """confidence=None is forwarded as NULL (human override convention)."""
        mock_cursor = wire_get_cursor_mock(mock_get_cursor_factory, returning_id=42)

        append_match_log_row(
            link_id=None,
            platform_market_id=42,
            canonical_market_id=None,
            action="override",
            confidence=None,  # human overrides have no algorithmic confidence
            algorithm_id=1,
            features=None,
            prior_link_id=None,
            decided_by="human:eric",
        )

        params = mock_cursor.execute.call_args[0][1]
        # confidence is the 5th positional param (0-indexed: 4).
        assert params[4] is None


# =============================================================================
# append_match_log_row — Pattern 73 SSOT real-guard validation
# =============================================================================


@pytest.mark.unit
class TestAppendMatchLogRowRejectsInvalidAction:
    """Pattern 73 SSOT real-guard validation on action."""

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_rejects_invalid_action(self, mock_get_cursor_factory):
        """action not in ACTION_VALUES raises ValueError before SQL.

        Pattern 73 SSOT real-guard: the import of ACTION_VALUES is USED here
        in actual validation (NOT side-effect-only #noqa: F401 import).  This
        is the #1085 finding #2 strengthening of slot-0072's convention.
        """
        for bad_action in ("not_a_real_action", "LINK", "create", "delete", ""):
            with pytest.raises(ValueError, match="ACTION_VALUES"):
                append_match_log_row(
                    link_id=None,
                    platform_market_id=42,
                    canonical_market_id=None,
                    action=bad_action,
                    confidence=None,
                    algorithm_id=1,
                    features=None,
                    prior_link_id=None,
                    decided_by="system:test",
                )
        # No SQL was ever attempted (validation fires before get_cursor).
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_accepts_every_canonical_action(self, mock_get_cursor_factory):
        """Every value in ACTION_VALUES is accepted (Pattern 73 SSOT lockstep).

        If this fails, the constant and the validation drifted apart —
        which is exactly the failure mode Pattern 73 SSOT prevents.
        """
        mock_cursor = wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)

        for canonical_action in ACTION_VALUES:
            # Should NOT raise.
            append_match_log_row(
                link_id=None,
                platform_market_id=42,
                canonical_market_id=None,
                action=canonical_action,
                confidence=None,
                algorithm_id=1,
                features=None,
                prior_link_id=None,
                decided_by="system:test",
            )
        # Each call hits the cursor exactly once.
        assert mock_cursor.execute.call_count == len(ACTION_VALUES)


@pytest.mark.unit
class TestAppendMatchLogRowRejectsInvalidDecidedByPrefix:
    """Pattern 73 SSOT real-guard validation on decided_by prefix."""

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_rejects_invalid_decided_by_prefix(self, mock_get_cursor_factory):
        """decided_by missing canonical prefix raises ValueError before SQL.

        Pattern 73 SSOT real-guard: ``DECIDED_BY_PREFIXES`` import is USED
        in actual validation.
        """
        for bad_decider in (
            "eric",  # no prefix
            "User:eric",  # wrong-case prefix
            "operator:bob",  # not in canonical taxonomy
            "human",  # no colon
            "",  # empty
        ):
            with pytest.raises(ValueError, match="DECIDED_BY_PREFIXES"):
                append_match_log_row(
                    link_id=None,
                    platform_market_id=42,
                    canonical_market_id=None,
                    action="link",
                    confidence=None,
                    algorithm_id=1,
                    features=None,
                    prior_link_id=None,
                    decided_by=bad_decider,
                )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_accepts_every_canonical_prefix(self, mock_get_cursor_factory):
        """Every prefix in DECIDED_BY_PREFIXES is accepted (Pattern 73 lockstep)."""
        mock_cursor = wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)

        for prefix in DECIDED_BY_PREFIXES:
            append_match_log_row(
                link_id=None,
                platform_market_id=42,
                canonical_market_id=None,
                action="link",
                confidence=None,
                algorithm_id=1,
                features=None,
                prior_link_id=None,
                decided_by=f"{prefix}user-{prefix}",
            )
        assert mock_cursor.execute.call_count == len(DECIDED_BY_PREFIXES)


@pytest.mark.unit
class TestAppendMatchLogRowRejectsDecidedByOver64Chars:
    """Boundary validation per #1085 finding #3 — VARCHAR(64) discipline at CRUD layer."""

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_rejects_decided_by_over_64_chars(self, mock_get_cursor_factory):
        """decided_by length > 64 chars raises ValueError before SQL.

        #1085 finding #3 inheritance from slot 0072's retire_reason
        length-not-validated case: the boundary surfaces a clear
        ValueError at the CRUD layer rather than letting psycopg2 raise a
        generic StringDataRightTruncation when VARCHAR(64) overflows.
        """
        # Construct a decided_by that has the canonical prefix but exceeds 64.
        # Prefix "human:" is 6 chars; pad with 60 chars to make total 66 > 64.
        too_long = "human:" + ("x" * 60)
        assert len(too_long) > 64

        with pytest.raises(ValueError, match=r"VARCHAR\(64\)"):
            append_match_log_row(
                link_id=None,
                platform_market_id=42,
                canonical_market_id=None,
                action="link",
                confidence=None,
                algorithm_id=1,
                features=None,
                prior_link_id=None,
                decided_by=too_long,
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_accepts_decided_by_exactly_64_chars(self, mock_get_cursor_factory):
        """decided_by exactly 64 chars is the boundary — accepted, not rejected."""
        mock_cursor = wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)

        exactly_64 = "human:" + ("x" * 58)
        assert len(exactly_64) == 64

        append_match_log_row(
            link_id=None,
            platform_market_id=42,
            canonical_market_id=None,
            action="link",
            confidence=None,
            algorithm_id=1,
            features=None,
            prior_link_id=None,
            decided_by=exactly_64,
        )
        # Made it through validation + executed the INSERT.
        mock_cursor.execute.assert_called_once()


@pytest.mark.unit
class TestAppendMatchLogRowRejectsInvalidConfidence:
    """Confidence bound validation parity with DDL CHECK."""

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_rejects_confidence_below_zero(self, mock_get_cursor_factory):
        """confidence < 0 raises ValueError."""
        with pytest.raises(ValueError, match=r"confidence must be in \[0, 1\]"):
            append_match_log_row(
                link_id=None,
                platform_market_id=42,
                canonical_market_id=None,
                action="link",
                confidence=Decimal("-0.001"),
                algorithm_id=1,
                features=None,
                prior_link_id=None,
                decided_by="system:test",
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_rejects_confidence_above_one(self, mock_get_cursor_factory):
        """confidence > 1 raises ValueError."""
        with pytest.raises(ValueError, match=r"confidence must be in \[0, 1\]"):
            append_match_log_row(
                link_id=None,
                platform_market_id=42,
                canonical_market_id=None,
                action="link",
                confidence=Decimal("1.5"),
                algorithm_id=1,
                features=None,
                prior_link_id=None,
                decided_by="system:test",
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_rejects_confidence_nan(self, mock_get_cursor_factory):
        """confidence=Decimal('NaN') raises ValueError.

        Decimal('NaN') silently passes ``>=`` and ``<=`` comparisons in
        Python (returns False for both), so a naive bound check would
        admit NaN as valid.  Explicit NaN guard catches this — the kind
        of trap a Builder might miss without surfacing at the validation
        layer.
        """
        with pytest.raises(ValueError, match="NaN"):
            append_match_log_row(
                link_id=None,
                platform_market_id=42,
                canonical_market_id=None,
                action="link",
                confidence=Decimal("NaN"),
                algorithm_id=1,
                features=None,
                prior_link_id=None,
                decided_by="system:test",
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_match_log.get_cursor")
    def test_rejects_float_confidence_per_critical_pattern_1(self, mock_get_cursor_factory):
        """confidence=<float> raises TypeError per CLAUDE.md Critical Pattern #1.

        Ripley P1 sentinel finding (session 81): a Python float silently
        satisfies ``>= 0`` and ``<= 1`` because Python compares float vs
        Decimal with the standard ordering relation; without an explicit
        ``isinstance(confidence, Decimal)`` guard, a caller passing
        ``confidence=0.5`` would slip past validation entirely.  Worse,
        ``confidence.is_nan()`` on a float raises AttributeError (cryptic
        exception type, no boundary signal).

        The isinstance guard surfaces the type violation as a clear
        TypeError with the canonical Critical-Pattern-#1 message before
        any value-level check runs.
        """
        with pytest.raises(TypeError, match="Critical Pattern #1"):
            append_match_log_row(
                link_id=None,
                platform_market_id=42,
                canonical_market_id=None,
                action="link",
                confidence=0.5,  # type: ignore[arg-type]  # intentional float for test
                algorithm_id=1,
                features=None,
                prior_link_id=None,
                decided_by="system:test",
            )
        mock_get_cursor_factory.assert_not_called()


# =============================================================================
# get_match_log_for_link — include_orphans semantics
# =============================================================================


@pytest.mark.unit
class TestGetMatchLogForLinkIncludeOrphans:
    """include_orphans=False (default) excludes NULL link_id rows; True includes them."""

    @patch("precog.database.crud_canonical_match_log.fetch_all")
    def test_get_match_log_for_link_include_orphans_default_false_excludes_null_link_id_rows(
        self, mock_fetch_all
    ):
        """Default include_orphans=False uses link_id = %s (excludes NULL rows).

        This is the contract: a naive INNER JOIN on link_id silently drops
        post-deletion orphan rows; the default form preserves that
        exclusion explicitly via ``WHERE link_id = %s``.  Callers needing
        orphan rows must opt in via include_orphans=True.
        """
        live_row = _full_log_row_dict(link_id=7)
        mock_fetch_all.return_value = [live_row]

        result = get_match_log_for_link(7)  # default include_orphans=False

        assert result == [live_row]
        sql, params = mock_fetch_all.call_args[0]
        assert "FROM canonical_match_log" in sql
        assert "WHERE link_id = %s" in sql
        # No UNION / no IS NULL clause in the default form.
        assert "UNION" not in sql.upper()
        assert "IS NULL" not in sql.upper()
        assert params == (7,)

    @patch("precog.database.crud_canonical_match_log.fetch_all")
    def test_get_match_log_for_link_include_orphans_true_returns_them(self, mock_fetch_all):
        """include_orphans=True uses a UNION over (live link_id, orphan tuple).

        The orphan branch joins on link_attribution.platform_market_id +
        canonical_market_id + the live link's NULL link_id sentinel; this
        makes the v2.42 sub-amendment B SET NULL rows recoverable.
        """
        live_row = _full_log_row_dict(link_id=7)
        orphan_row = _full_log_row_dict(id=8, link_id=None)
        mock_fetch_all.return_value = [live_row, orphan_row]

        result = get_match_log_for_link(7, include_orphans=True)

        assert result == [live_row, orphan_row]
        sql, params = mock_fetch_all.call_args[0]
        assert "UNION ALL" in sql.upper()
        assert "link_attribution" in sql
        assert "IS NULL" in sql
        # Orphan branch keys on platform_market_id + canonical_market_id.
        assert "platform_market_id" in sql
        # IS NOT DISTINCT FROM handles NULL canonical_market_id correctly.
        assert "IS NOT DISTINCT FROM" in sql.upper()
        assert params == (7,)


# =============================================================================
# get_match_log_for_platform_market — orphan-aware-by-construction
# =============================================================================


@pytest.mark.unit
class TestGetMatchLogForPlatformMarket:
    """Operator audit hot-path: ORDER BY decided_at DESC + LIMIT."""

    @patch("precog.database.crud_canonical_match_log.fetch_all")
    def test_get_match_log_for_platform_market_returns_rows_newest_first(self, mock_fetch_all):
        """Returns rows in decided_at DESC order; LIMIT bounded."""
        rows = [_full_log_row_dict(id=99), _full_log_row_dict(id=98)]
        mock_fetch_all.return_value = rows

        result = get_match_log_for_platform_market(42)

        assert result == rows
        sql, params = mock_fetch_all.call_args[0]
        assert "FROM canonical_match_log" in sql
        assert "WHERE platform_market_id = %s" in sql
        assert "ORDER BY decided_at DESC" in sql
        assert "LIMIT %s" in sql
        # Default limit is 50.
        assert params == (42, 50)

    @patch("precog.database.crud_canonical_match_log.fetch_all")
    def test_query_selects_all_canonical_match_log_columns(self, mock_fetch_all):
        """Pattern 43 fidelity: SELECT projection must include all 13 columns."""
        mock_fetch_all.return_value = []

        get_match_log_for_platform_market(42)

        sql = mock_fetch_all.call_args[0][0]
        for col in _ALL_COLUMNS:
            assert col in sql, f"Column {col!r} missing from SELECT projection"

    @patch("precog.database.crud_canonical_match_log.fetch_all")
    def test_get_match_log_for_platform_market_custom_limit(self, mock_fetch_all):
        """Custom limit forwarded to SQL."""
        mock_fetch_all.return_value = []

        get_match_log_for_platform_market(42, limit=10)

        params = mock_fetch_all.call_args[0][1]
        assert params == (42, 10)


# =============================================================================
# get_match_log_by_action — Pattern 73 SSOT real-guard on action arg
# =============================================================================


@pytest.mark.unit
class TestGetMatchLogByAction:
    """Pattern 73 SSOT real-guard validation also fires on the read path."""

    @patch("precog.database.crud_canonical_match_log.fetch_all")
    def test_get_match_log_by_action_rejects_invalid_action(self, mock_fetch_all):
        """action not in ACTION_VALUES raises ValueError before SQL.

        Pattern 73 SSOT discipline applies on read path too — typos at
        the call site fail loudly rather than silently returning empty
        result sets.
        """
        with pytest.raises(ValueError, match="ACTION_VALUES"):
            get_match_log_by_action("not_real", datetime(2026, 1, 1, tzinfo=UTC))
        mock_fetch_all.assert_not_called()

    @patch("precog.database.crud_canonical_match_log.fetch_all")
    def test_get_match_log_by_action_accepts_canonical_action(self, mock_fetch_all):
        """Each value in ACTION_VALUES is accepted (Pattern 73 lockstep)."""
        mock_fetch_all.return_value = []
        since = datetime(2026, 1, 1, tzinfo=UTC)

        get_match_log_by_action("quarantine", since)

        sql, params = mock_fetch_all.call_args[0]
        assert "WHERE action = %s" in sql
        assert "AND decided_at >= %s" in sql
        assert "ORDER BY decided_at DESC" in sql
        assert params == ("quarantine", since)
