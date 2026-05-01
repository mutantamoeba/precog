"""
Unit Tests for Temporal Alignment CRUD Operations (Migration 0027).

Tests the temporal alignment functions: insert_temporal_alignment,
insert_temporal_alignment_batch, and get_alignments_by_market. Validates
Decimal enforcement, enum validation, optional parameter handling, batch
operations, quality filtering, and ordering.

Related:
- Migration 0027: temporal_alignment
- Issue #375: Add temporal alignment table linking Kalshi polls to ESPN game states
- migration_batch_plan_v1.md: Migration 0027 spec

Usage:
    pytest tests/unit/database/test_crud_ledger_temporal.py -v
    pytest tests/unit/database/test_crud_ledger_temporal.py -v -m unit
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_ledger import (
    VALID_ALIGNMENT_QUALITIES,
    get_alignments_by_market,
    insert_temporal_alignment,
    insert_temporal_alignment_batch,
)

# =============================================================================
# HELPERS
# =============================================================================


def _mock_cursor_context(mock_get_cursor, mock_cursor=None):
    """Set up mock_get_cursor to return a context manager yielding mock_cursor."""
    if mock_cursor is None:
        mock_cursor = MagicMock()
    mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


def _default_alignment_kwargs():
    """Return minimal valid kwargs for insert_temporal_alignment."""
    return {
        "market_id": 42,
        "market_snapshot_id": 1001,
        "game_state_id": 501,
        "snapshot_time": datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
        "game_state_time": datetime(2026, 1, 15, 20, 30, 5, tzinfo=UTC),
        "time_delta_seconds": Decimal("5.00"),
    }


def _default_alignment_dict():
    """Return minimal valid dict for insert_temporal_alignment_batch."""
    return {
        "market_id": 42,
        "market_snapshot_id": 1001,
        "game_state_id": 501,
        "snapshot_time": datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
        "game_state_time": datetime(2026, 1, 15, 20, 30, 5, tzinfo=UTC),
        "time_delta_seconds": Decimal("5.00"),
    }


# =============================================================================
# INSERT TEMPORAL ALIGNMENT TESTS
# =============================================================================


@pytest.mark.unit
class TestInsertTemporalAlignment:
    """Unit tests for insert_temporal_alignment function."""

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_returns_surrogate_id(self, mock_get_cursor):
        """Test insert_temporal_alignment returns the integer surrogate PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = insert_temporal_alignment(**_default_alignment_kwargs())

        assert result == 1

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_validates_decimal_time_delta(self, mock_get_cursor):
        """Test that float values are rejected for time_delta_seconds."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_alignment_kwargs()
        kwargs["time_delta_seconds"] = 5.0  # float -- should raise

        with pytest.raises(TypeError, match="time_delta_seconds must be Decimal"):
            insert_temporal_alignment(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_validates_decimal_yes_ask_price(self, mock_get_cursor):
        """Test that float values are rejected for yes_ask_price."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_alignment_kwargs()
        kwargs["yes_ask_price"] = 0.55  # float -- should raise

        with pytest.raises(TypeError, match="yes_ask_price must be Decimal"):
            insert_temporal_alignment(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_validates_decimal_no_ask_price(self, mock_get_cursor):
        """Test that float values are rejected for no_ask_price."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_alignment_kwargs()
        kwargs["no_ask_price"] = 0.45  # float -- should raise

        with pytest.raises(TypeError, match="no_ask_price must be Decimal"):
            insert_temporal_alignment(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_validates_decimal_spread(self, mock_get_cursor):
        """Test that float values are rejected for spread."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_alignment_kwargs()
        kwargs["spread"] = 0.10  # float -- should raise

        with pytest.raises(TypeError, match="spread must be Decimal"):
            insert_temporal_alignment(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_validates_alignment_quality(self, mock_get_cursor):
        """Test that invalid alignment_quality values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_alignment_kwargs()
        kwargs["alignment_quality"] = "excellent"

        with pytest.raises(ValueError, match="alignment_quality must be one of"):
            insert_temporal_alignment(**kwargs)

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_allows_none_optional_fields(self, mock_get_cursor):
        """Test that all optional fields accept None (default behavior)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 2}

        # Only required fields -- all optional fields default to None
        result = insert_temporal_alignment(**_default_alignment_kwargs())

        assert result == 2

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_with_all_optional_fields(self, mock_get_cursor):
        """Test insert_temporal_alignment with every optional parameter provided."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 99}

        result = insert_temporal_alignment(
            market_id=42,
            market_snapshot_id=1001,
            game_state_id=501,
            snapshot_time=datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
            game_state_time=datetime(2026, 1, 15, 20, 30, 5, tzinfo=UTC),
            time_delta_seconds=Decimal("5.00"),
            alignment_quality="exact",
            yes_ask_price=Decimal("0.5500"),
            no_ask_price=Decimal("0.4500"),
            spread=Decimal("0.1000"),
            volume=150,
            game_status="in_progress",
            home_score=21,
            away_score=14,
            period="3rd",
            clock="08:42",
        )

        assert result == 99

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_accepts_all_valid_alignment_qualities(self, mock_get_cursor):
        """Test that every valid alignment_quality is accepted."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        for quality in VALID_ALIGNMENT_QUALITIES:
            kwargs = _default_alignment_kwargs()
            kwargs["alignment_quality"] = quality
            result = insert_temporal_alignment(**kwargs)
            assert result == 1

    @patch("precog.database.crud_ledger.get_cursor")
    def test_insert_default_alignment_quality_is_good(self, mock_get_cursor):
        """Test that default alignment_quality is 'good' when not specified."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 5}

        kwargs = _default_alignment_kwargs()
        # Do NOT set alignment_quality -- should default to 'good'
        insert_temporal_alignment(**kwargs)

        # Verify the SQL params include 'good' in the alignment_quality position
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        # alignment_quality is the 7th param (index 6)
        assert params[6] == "good"


# =============================================================================
# INSERT TEMPORAL ALIGNMENT BATCH TESTS
# =============================================================================


@pytest.mark.unit
class TestInsertTemporalAlignmentBatch:
    """Unit tests for insert_temporal_alignment_batch function."""

    @patch("precog.database.crud_ledger.execute_values")
    @patch("precog.database.crud_ledger.get_cursor")
    def test_batch_insert_returns_rowcount(self, mock_get_cursor, mock_exec_values):
        """Batch insert returns cur.rowcount (actually inserted, not submitted).

        The earlier implementation returned len(validated_params), which
        inflated the count under ON CONFLICT DO NOTHING retries. This test
        pins the rowcount-based return value to prevent regression.
        """
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 2

        rows = [_default_alignment_dict(), _default_alignment_dict()]
        rows[1]["market_snapshot_id"] = 1002
        rows[1]["game_state_id"] = 502

        result = insert_temporal_alignment_batch(rows)

        assert result == 2
        mock_exec_values.assert_called_once()

    @patch("precog.database.crud_ledger.execute_values")
    @patch("precog.database.crud_ledger.get_cursor")
    def test_batch_insert_returns_rowcount_under_conflict(self, mock_get_cursor, mock_exec_values):
        """rowcount=0 (all duplicates skipped) must return 0, not submitted count."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0  # all rows were ON CONFLICT DO NOTHING

        rows = [_default_alignment_dict(), _default_alignment_dict()]
        rows[1]["market_snapshot_id"] = 1002
        rows[1]["game_state_id"] = 502

        result = insert_temporal_alignment_batch(rows)

        assert result == 0
        mock_exec_values.assert_called_once()

    def test_batch_insert_empty_list_returns_zero(self):
        """Test that empty list returns 0 without DB interaction."""
        result = insert_temporal_alignment_batch([])

        assert result == 0

    @patch("precog.database.crud_ledger.get_cursor")
    def test_batch_insert_validates_decimal_time_delta(self, mock_get_cursor):
        """Test that float time_delta_seconds is rejected in batch."""
        _mock_cursor_context(mock_get_cursor)

        row = _default_alignment_dict()
        row["time_delta_seconds"] = 5.0  # float -- should raise

        with pytest.raises(TypeError, match="time_delta_seconds must be Decimal"):
            insert_temporal_alignment_batch([row])

    @patch("precog.database.crud_ledger.get_cursor")
    def test_batch_insert_validates_alignment_quality(self, mock_get_cursor):
        """Test that invalid alignment_quality is rejected in batch."""
        _mock_cursor_context(mock_get_cursor)

        row = _default_alignment_dict()
        row["alignment_quality"] = "perfect"

        with pytest.raises(ValueError, match="alignment_quality must be one of"):
            insert_temporal_alignment_batch([row])

    @patch("precog.database.crud_ledger.execute_values")
    @patch("precog.database.crud_ledger.get_cursor")
    def test_batch_insert_defaults_quality_to_good(self, mock_get_cursor, mock_exec_values):
        """Test that batch rows without alignment_quality default to 'good'."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        row = _default_alignment_dict()
        # alignment_quality NOT set -- should default to 'good'

        insert_temporal_alignment_batch([row])

        # execute_values(cur, sql, argslist, template=template)
        call_args = mock_exec_values.call_args
        params_list = call_args[0][2]
        # alignment_quality is the 7th param (index 6)
        assert params_list[0][6] == "good"

    @patch("precog.database.crud_ledger.get_cursor")
    def test_batch_insert_validates_decimal_yes_ask_price(self, mock_get_cursor):
        """Test that float yes_ask_price is rejected in batch."""
        _mock_cursor_context(mock_get_cursor)

        row = _default_alignment_dict()
        row["yes_ask_price"] = 0.55  # float -- should raise

        with pytest.raises(TypeError, match="yes_ask_price must be Decimal"):
            insert_temporal_alignment_batch([row])

    @patch("precog.database.crud_ledger.execute_values")
    @patch("precog.database.crud_ledger.get_cursor")
    def test_batch_insert_calls_execute_values(self, mock_get_cursor, mock_exec_values):
        """Batch insert uses execute_values (matches upsert_market_trades_batch).

        Switched from executemany in the S68 audit remediation: execute_values
        supports well-defined cur.rowcount so the return value can reflect
        actually-inserted rows (not submitted rows) under ON CONFLICT DO NOTHING.
        """
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        rows = [_default_alignment_dict()]
        insert_temporal_alignment_batch(rows)

        mock_exec_values.assert_called_once()
        # First positional arg to execute_values is the cursor
        assert mock_exec_values.call_args[0][0] is mock_cursor

    @patch("precog.database.crud_ledger.execute_values")
    @patch("precog.database.crud_ledger.get_cursor")
    def test_batch_insert_sql_has_on_conflict_do_nothing(self, mock_get_cursor, mock_exec_values):
        """Batch insert SQL uses ON CONFLICT DO NOTHING on uq_alignment_snapshot_game."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        insert_temporal_alignment_batch([_default_alignment_dict()])

        # execute_values(cur, sql, argslist, template=template)
        sql = mock_exec_values.call_args[0][1]
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql
        assert "market_snapshot_id, game_state_id" in sql

    @patch("precog.database.crud_ledger.execute_values")
    @patch("precog.database.crud_ledger.get_cursor")
    def test_batch_insert_passes_page_size_full_batch(self, mock_get_cursor, mock_exec_values):
        """execute_values is called with page_size=len(params) for accurate rowcount.

        psycopg2.extras.execute_values defaults page_size=100. For batches >100 rows,
        cur.rowcount reports only the LAST page's count. The fix passes
        page_size=len(validated_params) so rowcount reflects the full batch.

        This test uses N=150 rows to exercise the >100 boundary (issue #912).
        """
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 150

        # 150 rows crosses the default 100-row page boundary
        rows = []
        for i in range(150):
            row = _default_alignment_dict()
            row["market_snapshot_id"] = 2000 + i
            row["game_state_id"] = 3000 + i
            rows.append(row)

        insert_temporal_alignment_batch(rows)

        # execute_values must have been called with page_size=150 as a kwarg
        call_kwargs = mock_exec_values.call_args.kwargs
        assert call_kwargs.get("page_size") == 150, (
            f"expected page_size=150, got {call_kwargs.get('page_size')!r}"
        )


# =============================================================================
# GET ALIGNMENTS BY MARKET TESTS
# =============================================================================


@pytest.mark.unit
class TestGetAlignmentsByMarket:
    """Unit tests for get_alignments_by_market function."""

    @patch("precog.database.crud_ledger.fetch_all")
    def test_returns_empty_list(self, mock_fetch_all):
        """Test that empty result set returns empty list."""
        mock_fetch_all.return_value = []

        result = get_alignments_by_market(42)

        assert result == []

    @patch("precog.database.crud_ledger.fetch_all")
    def test_returns_list_of_dicts(self, mock_fetch_all):
        """Test that result is a list of dicts."""
        mock_fetch_all.return_value = [
            {"id": 1, "market_id": 42, "alignment_quality": "good"},
            {"id": 2, "market_id": 42, "alignment_quality": "exact"},
        ]

        result = get_alignments_by_market(42)

        assert len(result) == 2
        assert result[0]["id"] == 1

    @patch("precog.database.crud_ledger.fetch_all")
    def test_filters_by_min_quality(self, mock_fetch_all):
        """Test filtering by min_quality includes correct quality levels."""
        mock_fetch_all.return_value = []

        get_alignments_by_market(42, min_quality="good")

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "alignment_quality IN" in query
        # 'good' and 'exact' should be in params (good or better)
        assert "good" in params
        assert "exact" in params
        # 'stale', 'poor', 'fair' should NOT be in params
        assert "stale" not in params
        assert "poor" not in params
        assert "fair" not in params

    @patch("precog.database.crud_ledger.fetch_all")
    def test_min_quality_stale_includes_all(self, mock_fetch_all):
        """Test that min_quality='stale' includes all quality levels."""
        mock_fetch_all.return_value = []

        get_alignments_by_market(42, min_quality="stale")

        params = mock_fetch_all.call_args[0][1]
        for quality in VALID_ALIGNMENT_QUALITIES:
            assert quality in params

    def test_validates_invalid_min_quality(self):
        """Test that invalid min_quality is rejected."""
        with pytest.raises(ValueError, match="min_quality must be one of"):
            get_alignments_by_market(42, min_quality="excellent")

    @patch("precog.database.crud_ledger.fetch_all")
    def test_respects_limit(self, mock_fetch_all):
        """Test that custom limit is applied."""
        mock_fetch_all.return_value = []

        get_alignments_by_market(42, limit=25)

        params = mock_fetch_all.call_args[0][1]
        assert 25 in params

    @patch("precog.database.crud_ledger.fetch_all")
    def test_default_limit(self, mock_fetch_all):
        """Test that default limit of 100 is applied."""
        mock_fetch_all.return_value = []

        get_alignments_by_market(42)

        params = mock_fetch_all.call_args[0][1]
        assert 100 in params

    @patch("precog.database.crud_ledger.fetch_all")
    def test_orders_by_snapshot_time_desc(self, mock_fetch_all):
        """Test that query orders by snapshot_time DESC, id DESC."""
        mock_fetch_all.return_value = []

        get_alignments_by_market(42)

        query = mock_fetch_all.call_args[0][0]
        assert "ORDER BY snapshot_time DESC, id DESC" in query

    @patch("precog.database.crud_ledger.fetch_all")
    def test_filters_by_market_id(self, mock_fetch_all):
        """Test that query filters by market_id."""
        mock_fetch_all.return_value = []

        get_alignments_by_market(42)

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "market_id = %s" in query
        assert 42 in params

    @patch("precog.database.crud_ledger.fetch_all")
    def test_min_quality_fair_includes_fair_good_exact(self, mock_fetch_all):
        """Test that min_quality='fair' includes fair, good, and exact."""
        mock_fetch_all.return_value = []

        get_alignments_by_market(42, min_quality="fair")

        params = mock_fetch_all.call_args[0][1]
        assert "fair" in params
        assert "good" in params
        assert "exact" in params
        assert "stale" not in params
        assert "poor" not in params

    @patch("precog.database.crud_ledger.fetch_all")
    def test_no_min_quality_omits_quality_filter(self, mock_fetch_all):
        """Test that omitting min_quality does not add quality filter."""
        mock_fetch_all.return_value = []

        get_alignments_by_market(42)

        query = mock_fetch_all.call_args[0][0]
        assert "alignment_quality IN" not in query
