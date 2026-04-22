"""Unit tests for crud_events module — extracted from test_crud_operations_unit.py (split per #893 Option 1).

Covers:
- update_event_game_id (linking events to games)
- update_event (general-purpose event field updater)
- check_event_fully_settled (settlement check helper)
- _fill_event_null_fields (enrichment gap-filling helper)
- get_or_create_event (upsert behavior with enrichment fill)
- build_event_result (JSONB result construction from child markets)
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_events import (
    _fill_event_null_fields,
    get_or_create_event,
)
from precog.database.crud_game_states import (
    build_event_result,
    check_event_fully_settled,
    update_event,
    update_event_game_id,
)


@pytest.mark.unit
class TestUpdateEventGameIdUnit:
    """Unit tests for update_event_game_id — linking events to games."""

    @patch("precog.database.crud_game_states.get_cursor")
    def test_returns_true_when_updated(self, mock_get_cursor):
        """Returns True when event was found and updated."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event_game_id(event_id=42, game_id=15)

        assert result is True
        mock_cursor.execute.assert_called_once()
        # Verify params include game_id and event_id
        call_args = mock_cursor.execute.call_args[0]
        params = call_args[1]
        assert 15 in params  # game_id
        assert 42 in params  # event_id

    @patch("precog.database.crud_game_states.get_cursor")
    def test_returns_false_when_no_event_found(self, mock_get_cursor):
        """Returns False when no event matched (rowcount=0)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event_game_id(event_id=999, game_id=15)

        assert result is False


@pytest.mark.unit
class TestUpdateEventUnit:
    """Unit tests for update_event — general-purpose event field updater."""

    @patch("precog.database.crud_game_states.get_cursor")
    def test_basic_status_update(self, mock_get_cursor):
        """Single-field update (status) executes correct SQL."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(42, status="final")

        assert result is True
        mock_cursor.execute.assert_called_once()
        query, params = mock_cursor.execute.call_args[0]
        assert "status = %s" in query
        assert "updated_at = NOW()" in query
        assert "final" in params
        assert 42 in params  # event_id in WHERE clause

    @patch("precog.database.crud_game_states.get_cursor")
    def test_partial_update_multiple_fields(self, mock_get_cursor):
        """Update start_time and end_time together, leaving other fields untouched."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(
            7,
            start_time="2025-12-01T12:00:00Z",
            end_time="2025-12-01T23:59:00Z",
        )

        assert result is True
        query, _params = mock_cursor.execute.call_args[0]
        assert "start_time = %s" in query
        assert "end_time = %s" in query
        # status, result, description should NOT appear
        assert "status = %s" not in query
        assert "result = %s" not in query
        assert "description = %s" not in query

    @patch("precog.database.crud_game_states.get_cursor")
    def test_returns_false_when_event_not_found(self, mock_get_cursor):
        """Returns False when no row matches the event_id."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(999, status="live")

        assert result is False

    def test_invalid_status_raises_value_error(self):
        """Invalid status value raises ValueError before touching the DB."""
        with pytest.raises(ValueError, match="Invalid event status 'bogus'"):
            update_event(42, status="bogus")

    def test_all_none_returns_false(self):
        """Calling with no fields to update returns False without DB call."""
        # No DB mock needed — should short-circuit before get_cursor()
        result = update_event(42)
        assert result is False

    @patch("precog.database.crud_game_states.get_cursor")
    def test_result_serialized_as_json(self, mock_get_cursor):
        """result dict is JSON-serialized (matching create_event metadata pattern)."""
        import json

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result_dict = {"winner": "yes", "settlement_value": "1.0000"}
        update_event(42, result=result_dict)

        query, params = mock_cursor.execute.call_args[0]
        assert "result = %s" in query
        # The result should be a JSON string, not a dict
        json_param = params[0]  # result is first non-None field
        assert isinstance(json_param, str)
        assert json.loads(json_param) == result_dict

    @patch("precog.database.crud_game_states.get_cursor")
    def test_description_update(self, mock_get_cursor):
        """Description field can be updated."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(42, description="Updated event description")

        assert result is True
        query, params = mock_cursor.execute.call_args[0]
        assert "description = %s" in query
        assert "Updated event description" in params

    @patch("precog.database.crud_game_states.get_cursor")
    def test_all_fields_together(self, mock_get_cursor):
        """All five fields can be updated in a single call."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(
            42,
            start_time="2025-12-01T12:00:00Z",
            end_time="2025-12-01T23:59:00Z",
            status="final",
            result={"winner": "yes"},
            description="Settled",
        )

        assert result is True
        query, _params = mock_cursor.execute.call_args[0]
        assert "start_time = %s" in query
        assert "end_time = %s" in query
        assert "status = %s" in query
        assert "result = %s" in query
        assert "description = %s" in query
        assert "updated_at = NOW()" in query

    def test_valid_statuses_accepted(self):
        """All five valid statuses pass validation (ValueError not raised)."""
        valid = ["scheduled", "live", "final", "cancelled", "postponed"]
        for s in valid:
            # Should NOT raise — we don't care about the DB call,
            # just that validation passes. Use mock to avoid actual DB.
            with patch("precog.database.crud_game_states.get_cursor") as mock_gc:
                mock_cursor = MagicMock()
                mock_cursor.rowcount = 0
                mock_gc.return_value.__enter__ = MagicMock(return_value=mock_cursor)
                mock_gc.return_value.__exit__ = MagicMock(return_value=False)
                # Should not raise ValueError
                update_event(1, status=s)


@pytest.mark.unit
class TestCheckEventFullySettled:
    """Test check_event_fully_settled helper."""

    @patch("precog.database.crud_game_states.fetch_one")
    def test_all_markets_settled_returns_true(self, mock_fetch_one):
        """Returns True when all markets in the event are settled."""
        mock_fetch_one.return_value = {"total": 3, "settled": 3}

        assert check_event_fully_settled(42) is True
        mock_fetch_one.assert_called_once()
        # Verify event_id is passed as param
        call_args = mock_fetch_one.call_args
        assert call_args[0][1] == (42,)

    @patch("precog.database.crud_game_states.fetch_one")
    def test_some_unsettled_returns_false(self, mock_fetch_one):
        """Returns False when some markets are not yet settled."""
        mock_fetch_one.return_value = {"total": 3, "settled": 1}

        assert check_event_fully_settled(42) is False

    @patch("precog.database.crud_game_states.fetch_one")
    def test_no_markets_returns_false(self, mock_fetch_one):
        """Returns False when no markets exist for the event."""
        mock_fetch_one.return_value = {"total": 0, "settled": 0}

        assert check_event_fully_settled(42) is False

    @patch("precog.database.crud_game_states.fetch_one")
    def test_fetch_one_returns_none(self, mock_fetch_one):
        """Returns False when fetch_one returns None (defensive)."""
        mock_fetch_one.return_value = None

        assert check_event_fully_settled(42) is False

    @patch("precog.database.crud_game_states.fetch_one")
    def test_single_market_settled(self, mock_fetch_one):
        """Returns True when a single market in the event is settled."""
        mock_fetch_one.return_value = {"total": 1, "settled": 1}

        assert check_event_fully_settled(99) is True

    @patch("precog.database.crud_game_states.fetch_one")
    def test_query_uses_filter_clause(self, mock_fetch_one):
        """Verify the SQL uses FILTER (WHERE status = 'settled') pattern."""
        mock_fetch_one.return_value = {"total": 0, "settled": 0}

        check_event_fully_settled(1)

        call_args = mock_fetch_one.call_args
        sql = call_args[0][0]
        assert "FILTER" in sql
        assert "settled" in sql
        assert "event_id" in sql


@pytest.mark.unit
class TestFillEventNullFields:
    """Test _fill_event_null_fields helper for enrichment gap filling.

    Educational Note:
        _fill_event_null_fields implements the "fill gaps" pattern: it only
        writes values where the existing column is NULL AND the caller has
        provided a non-None replacement.  Non-NULL values are never
        overwritten.  This is critical on the hot path (every poll cycle)
        because it short-circuits when all fields are already populated.

    Reference:
        - Issue #513: Enrichment data gaps
        - get_or_create_event(): sole caller
    """

    @patch("precog.database.crud_events.get_cursor")
    def test_fills_null_start_time(self, mock_get_cursor):
        """When existing start_time is NULL, caller value is written."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {
            "id": 42,
            "start_time": None,
            "end_time": "2025-01-01T20:00:00Z",
            "status": "live",
            "game_id": None,
        }

        _fill_event_null_fields(existing, start_time="2025-01-01T18:00:00Z")

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "start_time" in sql
        assert "2025-01-01T18:00:00Z" in params
        # end_time and status should NOT be in the update
        assert "end_time" not in sql.split("WHERE")[0]

    @patch("precog.database.crud_events.get_cursor")
    def test_fills_multiple_null_fields(self, mock_get_cursor):
        """Multiple NULL fields are all filled in a single UPDATE."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {"id": 42, "start_time": None, "end_time": None, "status": None, "game_id": None}

        _fill_event_null_fields(
            existing,
            start_time="2025-01-01T18:00:00Z",
            end_time="2025-01-01T22:00:00Z",
            status="live",
            game_id=15,
        )

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "start_time" in sql
        assert "end_time" in sql
        assert "status" in sql
        assert "game_id" in sql
        assert "updated_at = NOW()" in sql

    @patch("precog.database.crud_events.get_cursor")
    def test_does_not_overwrite_non_null_values(self, mock_get_cursor):
        """Non-NULL existing values are never overwritten."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {
            "id": 42,
            "start_time": "2025-01-01T18:00:00Z",
            "end_time": "2025-01-01T22:00:00Z",
            "status": "live",
            "game_id": 10,
        }

        _fill_event_null_fields(
            existing,
            start_time="2025-06-01T00:00:00Z",
            end_time="2025-06-01T04:00:00Z",
            status="final",
            game_id=99,
        )

        # No UPDATE should be issued because all fields are non-NULL
        mock_cursor.execute.assert_not_called()

    @patch("precog.database.crud_events.get_cursor")
    def test_no_update_when_no_values_provided(self, mock_get_cursor):
        """No UPDATE when caller provides no enrichment values."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {"id": 42, "start_time": None, "end_time": None, "status": None, "game_id": None}

        _fill_event_null_fields(existing)

        # No caller values -> no UPDATE
        mock_cursor.execute.assert_not_called()

    @patch("precog.database.crud_events.get_cursor")
    def test_partial_fill_only_null_columns(self, mock_get_cursor):
        """Only NULL columns get updated; populated columns are skipped."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {
            "id": 42,
            "start_time": "2025-01-01T18:00:00Z",
            "end_time": None,
            "status": "live",
            "game_id": None,
        }

        _fill_event_null_fields(
            existing,
            start_time="SHOULD-NOT-OVERWRITE",
            end_time="2025-01-01T22:00:00Z",
            status="SHOULD-NOT-OVERWRITE",
            game_id=15,
        )

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        # Only end_time and game_id should appear
        assert "end_time" in sql
        assert "game_id" in sql
        # start_time and status should NOT appear in SET clause
        set_clause = sql.split("WHERE")[0]
        assert "start_time" not in set_clause
        # The status keyword appears in the WHERE clause but not SET
        assert set_clause.count("status") == 0
        assert "2025-01-01T22:00:00Z" in params
        assert 15 in params

    @patch("precog.database.crud_events.get_cursor")
    def test_empty_string_start_time_is_written(self, mock_get_cursor):
        """start_time='' is falsy in Python but ``is not None`` — should still be written.

        Regression test for #914: previously ``if start_time and ...`` would
        silently skip empty-string values. After the fix we use ``is not None``
        (matching the adjacent game_id pattern), so "" is treated as a real
        caller-provided value and written to the column.
        """
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {"id": 42, "start_time": None, "end_time": None, "status": None, "game_id": None}

        _fill_event_null_fields(existing, start_time="", end_time="", status="")

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        # All three fields should appear in SET clause
        set_clause = sql.split("WHERE")[0]
        assert "start_time" in set_clause
        assert "end_time" in set_clause
        assert "status" in set_clause
        # Empty-string params included
        assert params.count("") == 3

    @patch("precog.database.crud_events.get_cursor")
    def test_none_string_fields_are_skipped(self, mock_get_cursor):
        """None caller values for start_time/end_time/status should still be skipped.

        Regression test for #914: verifies the ``is not None`` guard still
        correctly filters out None (the common no-value case). Paired with
        test_empty_string_start_time_is_written, this pins down both ends of
        the behavior change.
        """
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {"id": 42, "start_time": None, "end_time": None, "status": None, "game_id": None}

        _fill_event_null_fields(existing, start_time=None, end_time=None, status=None)

        mock_cursor.execute.assert_not_called()

    @patch("precog.database.crud_events.get_cursor")
    def test_game_id_zero_is_treated_as_value(self, mock_get_cursor):
        """game_id=0 is falsy in Python but should still be written if existing is NULL.

        Educational Note:
            We use ``game_id is not None`` (not ``if game_id``) to correctly
            handle the edge case where game_id could be 0.  In practice this
            shouldn't happen (PKs start at 1), but defensive coding matters.
        """
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {"id": 42, "start_time": None, "end_time": None, "status": None, "game_id": None}

        # game_id=0 should still trigger an update (0 is not None)
        _fill_event_null_fields(existing, game_id=0)

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "game_id" in sql


@pytest.mark.unit
class TestGetOrCreateEventUpsert:
    """Test get_or_create_event fills NULL enrichment fields on existing events.

    Educational Note:
        Prior to the enrichment fix, get_or_create_event returned immediately
        for existing events without updating any fields.  Now it calls
        _fill_event_null_fields to fill NULL gaps.  These tests verify the
        integration between get_or_create_event and the fill helper.

    Reference:
        - Issue #513: 98.7% of events had NULL start_time/end_time
    """

    @patch("precog.database.crud_events._fill_event_null_fields")
    @patch("precog.database.crud_events.get_event")
    def test_existing_event_triggers_fill(self, mock_get_event, mock_fill):
        """Existing event triggers _fill_event_null_fields with caller args."""
        mock_get_event.return_value = {
            "id": 42,
            "start_time": None,
            "end_time": None,
            "status": None,
            "game_id": None,
        }

        pk, created = get_or_create_event(
            event_id="TEST-EVT-1",
            platform_id="kalshi",
            external_id="TEST-EVT-1",
            category="sports",
            title="Test Event",
            start_time="2025-01-01T18:00:00Z",
            end_time="2025-01-01T22:00:00Z",
            status="live",
            game_id=15,
        )

        assert pk == 42
        assert created is False
        mock_fill.assert_called_once_with(
            mock_get_event.return_value,
            "2025-01-01T18:00:00Z",
            "2025-01-01T22:00:00Z",
            "live",
            15,
        )

    @patch("precog.database.crud_events._fill_event_null_fields")
    @patch("precog.database.crud_events.get_event")
    def test_new_event_does_not_trigger_fill(self, mock_get_event, mock_fill):
        """New event (not existing) goes through create path, not fill."""
        mock_get_event.return_value = None

        with patch("precog.database.crud_events.create_event", return_value=99):
            pk, created = get_or_create_event(
                event_id="NEW-EVT-1",
                platform_id="kalshi",
                external_id="NEW-EVT-1",
                category="sports",
                title="New Event",
            )

        assert pk == 99
        assert created is True
        mock_fill.assert_not_called()


@pytest.mark.unit
class TestBuildEventResult:
    """Test build_event_result JSONB construction from child markets.

    Educational Note:
        build_event_result assembles a result dict from child market
        settlement values, serializing Decimal to string to avoid float
        precision issues in JSONB.

    Reference:
        - Issue #513: Event result population on settlement
    """

    @patch("precog.database.crud_game_states.fetch_all")
    def test_basic_result_structure(self, mock_fetch_all):
        """Verify correct JSONB structure from settled markets."""
        mock_fetch_all.return_value = [
            {"ticker": "KXNFL-T1", "settlement_value": Decimal("1.0000"), "status": "settled"},
            {"ticker": "KXNFL-T2", "settlement_value": Decimal("0.0000"), "status": "settled"},
        ]

        result = build_event_result(42)

        assert result["markets_total"] == 2
        assert result["markets_settled"] == 2
        assert result["outcomes"]["KXNFL-T1"]["settlement_value"] == "1.0000"
        assert result["outcomes"]["KXNFL-T2"]["settlement_value"] == "0.0000"

    @patch("precog.database.crud_game_states.fetch_all")
    def test_handles_null_settlement_values(self, mock_fetch_all):
        """Markets with NULL settlement_value are included with None."""
        mock_fetch_all.return_value = [
            {"ticker": "KXNFL-T1", "settlement_value": Decimal("1.0000"), "status": "settled"},
            {"ticker": "KXNFL-T2", "settlement_value": None, "status": "settled"},
        ]

        result = build_event_result(42)

        assert result["markets_total"] == 2
        assert result["markets_settled"] == 2
        assert result["outcomes"]["KXNFL-T1"]["settlement_value"] == "1.0000"
        assert result["outcomes"]["KXNFL-T2"]["settlement_value"] is None

    @patch("precog.database.crud_game_states.fetch_all")
    def test_mixed_settled_and_open_markets(self, mock_fetch_all):
        """Result correctly counts settled vs non-settled markets."""
        mock_fetch_all.return_value = [
            {"ticker": "MKT-A", "settlement_value": Decimal("1.0000"), "status": "settled"},
            {"ticker": "MKT-B", "settlement_value": None, "status": "open"},
        ]

        result = build_event_result(42)

        assert result["markets_total"] == 2
        assert result["markets_settled"] == 1
        assert result["outcomes"]["MKT-A"]["settlement_value"] == "1.0000"
        assert result["outcomes"]["MKT-B"]["settlement_value"] is None

    @patch("precog.database.crud_game_states.fetch_all")
    def test_no_markets_returns_empty(self, mock_fetch_all):
        """Event with no child markets returns empty structure."""
        mock_fetch_all.return_value = []

        result = build_event_result(42)

        assert result["markets_total"] == 0
        assert result["markets_settled"] == 0
        assert result["outcomes"] == {}

    @patch("precog.database.crud_game_states.fetch_all")
    def test_decimal_precision_preserved(self, mock_fetch_all):
        """Decimal precision is preserved via string serialization.

        Educational Note:
            Storing Decimal as string in JSONB avoids float precision issues.
            e.g., float(Decimal("0.3333")) -> 0.3333 (OK) but
            json.dumps(float(Decimal("0.1"))) -> "0.1" (could lose precision
            with other values like 0.04 + 0.96 = 1.0000000000000002).
        """
        mock_fetch_all.return_value = [
            {"ticker": "SCALAR-MKT", "settlement_value": Decimal("0.3333"), "status": "settled"},
        ]

        result = build_event_result(99)

        assert result["outcomes"]["SCALAR-MKT"]["settlement_value"] == "0.3333"

    @patch("precog.database.crud_game_states.fetch_all")
    def test_query_filters_by_event_id(self, mock_fetch_all):
        """Verify the SQL uses event_id filter."""
        mock_fetch_all.return_value = []

        build_event_result(42)

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "event_id" in sql
        assert params == (42,)
