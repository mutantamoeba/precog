"""Unit tests for crud_canonical_event_phase_log module -- Cohort 4 slot 0079.

Covers (function-by-function):
    - append_phase_transition: happy path, new_phase validation,
      previous_phase nullable + validation, changed_by prefix validation,
      changed_by length boundary (slot-0073 #1085 finding #3 inheritance).
    - get_phase_history_for_event: query shape + parameters.

Pattern 73 SSOT real-guard discipline (slot 0073 #1085 finding #2 inheritance):
    Both ``CANONICAL_EVENT_LIFECYCLE_PHASES`` and ``DECIDED_BY_PREFIXES``
    are imported and USED in real-guard ValueError-raising validation in
    the SUT.  These tests assert that the validation fires -- the side-
    effect-only convention from slot 0072's ``LINK_STATE_VALUES`` does
    NOT survive into slot 0079.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that
the real query returns.  Mocks of ``get_cursor`` use the
``__enter__`` / ``__exit__`` protocol consistent with sibling unit tests.

Reference:
    - ``src/precog/database/crud_canonical_event_phase_log.py``
    - ``src/precog/database/alembic/versions/0079_canonical_event_phase_log.py``
    - ``tests/unit/database/test_crud_canonical_match_log_unit.py`` (style + sister-module reference)
    - ADR-118 V2.40 Item 3 + V2.43 Item 2 + slot 0079 build spec § 5a
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from precog.database.constants import CANONICAL_EVENT_LIFECYCLE_PHASES, DECIDED_BY_PREFIXES
from precog.database.crud_canonical_event_phase_log import (
    append_phase_transition,
    get_phase_history_for_event,
)
from tests.unit.database._crud_unit_helpers import wire_get_cursor_mock

pytestmark = [pytest.mark.unit]


def _full_phase_log_row_dict(
    *,
    id: int = 7,
    canonical_event_id: int = 42,
    previous_phase: str | None = "proposed",
    new_phase: str = "listed",
    transition_at: datetime | None = None,
    changed_by: str = "system:trigger",
    note: str | None = None,
    created_at: datetime | None = None,
) -> dict:
    """Build a full canonical_event_phase_log row dict matching the real query shape.

    Pattern 43 fidelity: every key the real RETURNING / SELECT projection
    emits is present, with no extras.
    """
    if transition_at is None:
        transition_at = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
    if created_at is None:
        created_at = transition_at
    return {
        "id": id,
        "canonical_event_id": canonical_event_id,
        "previous_phase": previous_phase,
        "new_phase": new_phase,
        "transition_at": transition_at,
        "changed_by": changed_by,
        "note": note,
        "created_at": created_at,
    }


_ALL_COLUMNS = (
    "id",
    "canonical_event_id",
    "previous_phase",
    "new_phase",
    "transition_at",
    "changed_by",
    "note",
    "created_at",
)


# =============================================================================
# append_phase_transition -- happy path
# =============================================================================


class TestAppendPhaseTransitionValidInputs:
    """Happy-path: valid inputs produce a single INSERT with returned id."""

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_append_phase_transition_valid_inputs(self, mock_get_cursor_factory):
        """append_phase_transition INSERTs and returns the id when all inputs valid."""
        mock_cursor = wire_get_cursor_mock(mock_get_cursor_factory, returning_id=42)

        result = append_phase_transition(
            canonical_event_id=10,
            new_phase="live",
            changed_by="human:eric",
            previous_phase="pre_event",
            note="Manual correction: kickoff time confirmation",
        )

        assert result == 42
        mock_get_cursor_factory.assert_called_once_with(commit=True)
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO canonical_event_phase_log" in sql
        assert "RETURNING id" in sql
        # All 5 column slots in the INSERT.
        for col in (
            "canonical_event_id",
            "previous_phase",
            "new_phase",
            "changed_by",
            "note",
        ):
            assert col in sql, f"INSERT must include column {col!r}"
        # Param order matches the INSERT column order.
        assert params == (
            10,
            "pre_event",
            "live",
            "human:eric",
            "Manual correction: kickoff time confirmation",
        )

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_append_phase_transition_minimal_inputs(self, mock_get_cursor_factory):
        """append_phase_transition with only required args (previous_phase=None, note=None)."""
        wire_get_cursor_mock(mock_get_cursor_factory, returning_id=99)

        result = append_phase_transition(
            canonical_event_id=5,
            new_phase="proposed",
            changed_by="service:matching-v1",
        )

        assert result == 99

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_append_phase_transition_returns_int_id(self, mock_get_cursor_factory):
        """Return type is int (cast from RealDictCursor row dict)."""
        wire_get_cursor_mock(mock_get_cursor_factory, returning_id=12345)

        result = append_phase_transition(
            canonical_event_id=1,
            new_phase="resolved",
            changed_by="human:operator",
        )

        assert isinstance(result, int)
        assert result == 12345


# =============================================================================
# append_phase_transition -- new_phase validation (Pattern 73 SSOT real-guard)
# =============================================================================


class TestAppendPhaseTransitionNewPhaseValidation:
    """Pattern 73 SSOT: new_phase must be in CANONICAL_EVENT_LIFECYCLE_PHASES."""

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_invalid_new_phase_raises_value_error(self, mock_get_cursor_factory):
        """new_phase='not_a_real_phase' raises ValueError before SQL."""
        with pytest.raises(ValueError, match="new_phase"):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="not_a_real_phase",
                changed_by="human:eric",
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_empty_new_phase_raises_value_error(self, mock_get_cursor_factory):
        """new_phase='' raises ValueError before SQL."""
        with pytest.raises(ValueError, match="new_phase"):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="",
                changed_by="human:eric",
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_each_canonical_phase_value_accepted(self, mock_get_cursor_factory):
        """Every value in CANONICAL_EVENT_LIFECYCLE_PHASES is accepted by validation.

        Pattern 73 SSOT real-guard: the validation MUST accept exactly the
        same vocabulary the DDL CHECK accepts; any drift would be visible
        here AND in the SSOT parity integration test.
        """
        wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)

        for phase in CANONICAL_EVENT_LIFECYCLE_PHASES:
            # Each call should not raise.
            append_phase_transition(
                canonical_event_id=1,
                new_phase=phase,
                changed_by="system:test",
            )

    def test_canonical_event_lifecycle_phases_imported_for_validation(self):
        """Sentinel: the SUT actually uses CANONICAL_EVENT_LIFECYCLE_PHASES.

        If a future refactor drops the import + validation, this real-guard
        sentinel test fires.  The slot-0073 #1085 finding #2 strengthening
        applied to slot 0079: side-effect-only ``# noqa: F401`` imports
        do NOT survive into the new slot.
        """
        # This both tests and asserts the real-guard discipline.
        assert "proposed" in CANONICAL_EVENT_LIFECYCLE_PHASES
        assert "voided" in CANONICAL_EVENT_LIFECYCLE_PHASES
        assert len(CANONICAL_EVENT_LIFECYCLE_PHASES) == 8


# =============================================================================
# append_phase_transition -- previous_phase validation
# =============================================================================


class TestAppendPhaseTransitionPreviousPhaseValidation:
    """previous_phase nullable + validation when non-NULL."""

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_invalid_previous_phase_raises_value_error(self, mock_get_cursor_factory):
        """Non-NULL previous_phase='not_real' raises ValueError before SQL."""
        with pytest.raises(ValueError, match="previous_phase"):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="live",
                changed_by="human:eric",
                previous_phase="not_real",
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_none_previous_phase_accepted(self, mock_get_cursor_factory):
        """previous_phase=None is accepted (first-transition case)."""
        wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)

        # No raise expected.
        append_phase_transition(
            canonical_event_id=1,
            new_phase="proposed",
            changed_by="human:eric",
            previous_phase=None,
        )

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_default_previous_phase_is_none(self, mock_get_cursor_factory):
        """previous_phase has default of None (omitted in call)."""
        wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)

        # No raise expected when omitted.
        append_phase_transition(
            canonical_event_id=1,
            new_phase="proposed",
            changed_by="human:eric",
        )

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_each_canonical_phase_accepted_as_previous(self, mock_get_cursor_factory):
        """Every CANONICAL_EVENT_LIFECYCLE_PHASES value valid as previous_phase too."""
        wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)

        for phase in CANONICAL_EVENT_LIFECYCLE_PHASES:
            # No raise expected.
            append_phase_transition(
                canonical_event_id=1,
                new_phase="resolved",
                changed_by="system:test",
                previous_phase=phase,
            )


# =============================================================================
# append_phase_transition -- changed_by validation
# =============================================================================


class TestAppendPhaseTransitionChangedByValidation:
    """Pattern 73 SSOT: changed_by must start with one of DECIDED_BY_PREFIXES."""

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_changed_by_no_prefix_raises_value_error(self, mock_get_cursor_factory):
        """changed_by='nopfx' (no recognized prefix) raises ValueError."""
        with pytest.raises(ValueError, match="changed_by"):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="live",
                changed_by="nopfx",
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_changed_by_wrong_prefix_raises_value_error(self, mock_get_cursor_factory):
        """changed_by='admin:eric' (not in DECIDED_BY_PREFIXES) raises ValueError."""
        with pytest.raises(ValueError, match="changed_by"):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="live",
                changed_by="admin:eric",
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_changed_by_too_long_raises_value_error(self, mock_get_cursor_factory):
        """changed_by length > 64 raises ValueError before SQL.

        Slot-0073 #1085 finding #3 inheritance: surface a clear ValueError
        before psycopg2 raises a generic StringDataRightTruncation.
        """
        too_long = "human:" + "x" * 60  # 6 + 60 = 66, > 64
        with pytest.raises(ValueError, match="changed_by length"):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="live",
                changed_by=too_long,
            )
        mock_get_cursor_factory.assert_not_called()

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_changed_by_at_64_boundary_accepted(self, mock_get_cursor_factory):
        """changed_by exactly 64 chars is accepted (boundary inclusive)."""
        wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)
        at_boundary = "human:" + "x" * 58  # 6 + 58 = 64
        assert len(at_boundary) == 64

        append_phase_transition(
            canonical_event_id=1,
            new_phase="live",
            changed_by=at_boundary,
        )

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_each_decided_by_prefix_accepted(self, mock_get_cursor_factory):
        """Every prefix in DECIDED_BY_PREFIXES is acceptable in changed_by."""
        wire_get_cursor_mock(mock_get_cursor_factory, returning_id=1)

        for prefix in DECIDED_BY_PREFIXES:
            # No raise expected.
            append_phase_transition(
                canonical_event_id=1,
                new_phase="proposed",
                changed_by=f"{prefix}example_actor",
            )

    def test_decided_by_prefixes_imported_for_validation(self):
        """Sentinel: the SUT actually uses DECIDED_BY_PREFIXES."""
        assert "human:" in DECIDED_BY_PREFIXES
        assert "service:" in DECIDED_BY_PREFIXES
        assert "system:" in DECIDED_BY_PREFIXES


# =============================================================================
# append_phase_transition -- validation precedes SQL (defense-in-depth)
# =============================================================================


class TestAppendPhaseTransitionValidationPrecedesSql:
    """All ValueError-raising paths fire BEFORE any SQL is issued."""

    @patch("precog.database.crud_canonical_event_phase_log.get_cursor")
    def test_validation_failure_emits_no_sql(self, mock_get_cursor_factory):
        """get_cursor() is never called on validation-failure paths.

        Multiple validation-fail inputs; each one must not invoke get_cursor.
        Pattern 43 + 73 discipline: validation precedes SQL so callers
        asserting ``mock_get_cursor.assert_not_called()`` consistently pass.
        """
        # Bad new_phase
        with pytest.raises(ValueError):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="bad",
                changed_by="human:eric",
            )

        # Bad previous_phase
        with pytest.raises(ValueError):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="live",
                changed_by="human:eric",
                previous_phase="bad",
            )

        # Bad changed_by prefix
        with pytest.raises(ValueError):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="live",
                changed_by="bad",
            )

        # Bad changed_by length
        with pytest.raises(ValueError):
            append_phase_transition(
                canonical_event_id=1,
                new_phase="live",
                changed_by="human:" + "x" * 60,
            )

        mock_get_cursor_factory.assert_not_called()


# =============================================================================
# get_phase_history_for_event -- read query shape
# =============================================================================


class TestGetPhaseHistoryForEvent:
    """Read query: returns rows newest-first, parameterized by canonical_event_id + limit."""

    @patch("precog.database.crud_canonical_event_phase_log.fetch_all")
    def test_get_phase_history_returns_list_of_dicts(self, mock_fetch_all):
        """Function returns the fetch_all result verbatim (list of row dicts)."""
        expected_rows = [
            _full_phase_log_row_dict(id=2, new_phase="live", previous_phase="pre_event"),
            _full_phase_log_row_dict(id=1, new_phase="pre_event", previous_phase="listed"),
        ]
        mock_fetch_all.return_value = expected_rows

        result = get_phase_history_for_event(42)

        assert result == expected_rows
        # Verify fetch_all signature: query string + params tuple.
        sql, params = mock_fetch_all.call_args[0]
        assert "SELECT" in sql
        assert "FROM canonical_event_phase_log" in sql
        assert "WHERE canonical_event_id = %s" in sql
        assert "ORDER BY transition_at DESC" in sql
        assert "LIMIT %s" in sql
        assert params == (42, 50)  # default limit=50

    @patch("precog.database.crud_canonical_event_phase_log.fetch_all")
    def test_get_phase_history_custom_limit(self, mock_fetch_all):
        """Custom limit propagates into the query parameters."""
        mock_fetch_all.return_value = []

        get_phase_history_for_event(7, limit=10)

        _, params = mock_fetch_all.call_args[0]
        assert params == (7, 10)

    @patch("precog.database.crud_canonical_event_phase_log.fetch_all")
    def test_get_phase_history_empty_result(self, mock_fetch_all):
        """Empty result returns empty list (no exception)."""
        mock_fetch_all.return_value = []

        result = get_phase_history_for_event(99999)

        assert result == []

    @patch("precog.database.crud_canonical_event_phase_log.fetch_all")
    def test_get_phase_history_query_projects_all_columns(self, mock_fetch_all):
        """SELECT projects every column the table exposes (Pattern 43 fidelity)."""
        mock_fetch_all.return_value = []

        get_phase_history_for_event(1)

        sql, _ = mock_fetch_all.call_args[0]
        for col in _ALL_COLUMNS:
            assert col in sql, f"Query must project column {col!r}"
