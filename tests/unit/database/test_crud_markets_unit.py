"""Unit tests for crud_markets module — extracted from test_crud_operations_unit.py (split per #893 Option 1).

Covers settlement_value flow and Migration 0046 enrichment fields on the
create_market / update_market_with_versioning surface.
"""

from datetime import UTC
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_markets import (
    create_market,
    update_market_with_versioning,
)


@pytest.mark.unit
class TestUpdateMarketSettlementValue:
    """Test settlement_value flows through update_market_with_versioning."""

    @patch("precog.database.crud_markets.get_cursor")
    @patch("precog.database.crud_markets.get_current_market")
    def test_settlement_value_included_in_dimension_update(self, mock_get_current, mock_get_cursor):
        """settlement_value is written to the markets dimension UPDATE.

        Issue #625: update_market_with_versioning now wraps its mutation
        body in retry_on_scd_unique_conflict. The closure executes:
            [0] SELECT NOW() AS ts
            [1] SELECT id ... FOR UPDATE (market_snapshots lock)
            [2] UPDATE markets SET ...          <- dimension UPDATE
            [3] UPDATE market_snapshots ... (close)
            [4] INSERT INTO market_snapshots ...
        So the dimension UPDATE is now at call_args_list[2].
        """
        from datetime import datetime as _dt

        mock_get_current.return_value = {
            "id": 1,
            "yes_ask_price": Decimal("0.5000"),
            "no_ask_price": Decimal("0.5000"),
            "status": "open",
            "volume": 100,
            "open_interest": 50,
            "metadata": None,
            "spread": None,
            "yes_bid_price": None,
            "no_bid_price": None,
            "last_price": None,
            "liquidity": None,
            "subtitle": None,
            "open_time": None,
            "close_time": None,
            "expiration_time": None,
            "outcome_label": None,
            "subcategory": None,
            "bracket_count": None,
            "source_url": None,
            "settlement_value": None,
        }

        mock_cursor = MagicMock()
        # fetchone returns the NOW() ts row for the first call; remaining
        # calls (lock result) can return a generic MagicMock without
        # breaking the test because the closure does not read them.
        mock_cursor.fetchone.return_value = {"ts": _dt(2026, 1, 15, 12, 0, 0, tzinfo=UTC)}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        update_market_with_versioning(
            ticker="TEST-MKT",
            status="settled",
            settlement_value=Decimal("1.0000"),
        )

        # Issue #625: dimension UPDATE is now at index 2 (after SELECT NOW()
        # and FOR UPDATE lock).
        dim_call = mock_cursor.execute.call_args_list[2]
        sql = dim_call[0][0]
        params = dim_call[0][1]

        assert "settlement_value" in sql
        # settlement_value is the 11th param (after source_url, before market_pk)
        assert Decimal("1.0000") in params

    @patch("precog.database.crud_markets.get_cursor")
    @patch("precog.database.crud_markets.get_current_market")
    def test_settlement_value_none_preserves_existing(self, mock_get_current, mock_get_cursor):
        """When settlement_value is None, the existing value is preserved.

        Issue #625: dimension UPDATE is at index 2 (not 0) in call_args_list
        because the closure now runs SELECT NOW() + FOR UPDATE lock first.
        """
        from datetime import datetime as _dt

        mock_get_current.return_value = {
            "id": 1,
            "yes_ask_price": Decimal("0.5000"),
            "no_ask_price": Decimal("0.5000"),
            "status": "settled",
            "volume": 100,
            "open_interest": 50,
            "metadata": None,
            "spread": None,
            "yes_bid_price": None,
            "no_bid_price": None,
            "last_price": None,
            "liquidity": None,
            "subtitle": None,
            "open_time": None,
            "close_time": None,
            "expiration_time": None,
            "outcome_label": None,
            "subcategory": None,
            "bracket_count": None,
            "source_url": None,
            "settlement_value": Decimal("1.0000"),
        }

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ts": _dt(2026, 1, 15, 12, 0, 0, tzinfo=UTC)}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Do NOT pass settlement_value — it should use existing
        update_market_with_versioning(
            ticker="TEST-MKT",
            yes_ask_price=Decimal("0.6000"),
        )

        # Issue #625: dimension UPDATE is now at index 2.
        dim_call = mock_cursor.execute.call_args_list[2]
        params = dim_call[0][1]
        # Existing Decimal("1.0000") should be preserved
        assert Decimal("1.0000") in params

    def test_settlement_value_rejects_float(self):
        """settlement_value must be Decimal, not float."""
        with pytest.raises(TypeError, match="settlement_value must be Decimal"):
            update_market_with_versioning(
                ticker="TEST-MKT",
                settlement_value=1.0,  # type: ignore[arg-type]
            )


@pytest.mark.unit
class TestCreateMarketEnrichment:
    """Unit tests for create_market with enrichment fields (migration 0046).

    Verifies that new dimension fields (expiration_value, notional_value) and
    snapshot fields (volume_24h, previous_*, yes_bid_size, yes_ask_size) are
    correctly passed through to SQL INSERT statements.

    Educational Note:
        Dimension fields (markets table) are per-market constants that don't
        change between polls. Snapshot fields (market_snapshots table) are
        per-poll observations captured via SCD Type 2 versioning.

    Reference:
        - Migration 0046: depth signals + daily movement columns
        - Issue #513: Kalshi API enrichment (P1)
    """

    @patch("precog.database.crud_markets.get_cursor")
    def test_create_market_with_all_enrichment_fields(self, mock_get_cursor):
        """All 8 new enrichment fields are passed to SQL INSERT statements.

        Verifies that dimension fields go to markets table INSERT and
        snapshot fields go to market_snapshots table INSERT.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 99}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_market(
            platform_id="kalshi",
            event_id=7,
            external_id="KXNFLKCBUF",
            ticker="NFL-KC-BUF-YES",
            title="Chiefs to beat Bills",
            yes_ask_price=Decimal("0.5200"),
            no_ask_price=Decimal("0.4900"),
            # Dimension enrichment (migration 0046)
            expiration_value="above 42.5",
            notional_value=Decimal("1.0000"),
            # Snapshot enrichment (migration 0046)
            volume_24h=150,
            previous_yes_bid=Decimal("0.5100"),
            previous_yes_ask=Decimal("0.5300"),
            previous_price=Decimal("0.5200"),
            yes_bid_size=45,
            yes_ask_size=30,
        )

        assert result == 99

        # Three execute calls: dimension INSERT + dimension UPDATE (0062 two-step
        # canonical market_key) + snapshot INSERT
        assert mock_cursor.execute.call_count == 3

        # Verify dimension INSERT includes expiration_value and notional_value
        dim_call = mock_cursor.execute.call_args_list[0]
        dim_sql = dim_call[0][0]
        dim_params = dim_call[0][1]
        assert "expiration_value" in dim_sql
        assert "notional_value" in dim_sql
        # expiration_value is 2nd-to-last before metadata in the params tuple
        assert "above 42.5" in dim_params
        assert Decimal("1.0000") in dim_params

        # Verify snapshot INSERT includes all 6 new fields (now at index 2 after
        # the 0062 canonical market_key UPDATE at index 1)
        snap_call = mock_cursor.execute.call_args_list[2]
        snap_sql = snap_call[0][0]
        snap_params = snap_call[0][1]
        assert "volume_24h" in snap_sql
        assert "previous_yes_bid" in snap_sql
        assert "previous_yes_ask" in snap_sql
        assert "previous_price" in snap_sql
        assert "yes_bid_size" in snap_sql
        assert "yes_ask_size" in snap_sql
        # Verify actual values in params
        assert 150 in snap_params  # volume_24h
        assert Decimal("0.5100") in snap_params  # previous_yes_bid
        assert Decimal("0.5300") in snap_params  # previous_yes_ask
        assert Decimal("0.5200") in snap_params  # previous_price
        assert 45 in snap_params  # yes_bid_size
        assert 30 in snap_params  # yes_ask_size

    @patch("precog.database.crud_markets.get_cursor")
    def test_create_market_enrichment_fields_nullable(self, mock_get_cursor):
        """Enrichment fields default to None when not provided.

        Educational Note:
            All new columns are nullable because existing markets won't have
            these values and not all API responses include them. The poller
            passes None (via .get() on missing keys) which becomes SQL NULL.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 100}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_market(
            platform_id="kalshi",
            event_id=None,
            external_id="KXTEST",
            ticker="TEST-MKT",
            title="Test Market",
            yes_ask_price=Decimal("0.5000"),
            no_ask_price=Decimal("0.5000"),
            # No enrichment fields provided -- all should be None
        )

        assert result == 100

        # Verify dimension INSERT includes the new column names
        # (values will be None since not provided, validated via snapshot below)
        dim_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "expiration_value" in dim_sql
        assert "notional_value" in dim_sql

        # Verify snapshot INSERT: all 6 new fields are None (index shifted to 2
        # by the 0062 two-step market_key UPDATE at index 1)
        snap_params = mock_cursor.execute.call_args_list[2][0][1]
        # The last 6 params before row_current_ind/updated_at should be None
        # Snapshot params: market_pk, yes_ask, no_ask, yes_bid, no_bid, last_price,
        #                  spread, volume, open_interest, liquidity,
        #                  volume_24h, prev_yes_bid, prev_yes_ask, prev_price,
        #                  yes_bid_size, yes_ask_size
        # Indices 10-15 are the new enrichment fields (all None)
        assert snap_params[10] is None  # volume_24h
        assert snap_params[11] is None  # previous_yes_bid
        assert snap_params[12] is None  # previous_yes_ask
        assert snap_params[13] is None  # previous_price
        assert snap_params[14] is None  # yes_bid_size
        assert snap_params[15] is None  # yes_ask_size

    @patch("precog.database.crud_markets.get_cursor")
    def test_create_market_decimal_validation_on_enrichment(self, mock_get_cursor):
        """Decimal enrichment fields are validated by validate_decimal().

        Educational Note:
            previous_yes_bid, previous_yes_ask, previous_price, and
            notional_value are DECIMAL(10,4) columns. They must go through
            validate_decimal() to enforce Decimal type at runtime, catching
            accidental float usage early (Pattern 1: NEVER USE FLOAT).
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 101}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Should succeed with proper Decimal values
        create_market(
            platform_id="kalshi",
            event_id=None,
            external_id="KXTEST2",
            ticker="TEST-MKT-2",
            title="Test Market 2",
            yes_ask_price=Decimal("0.6000"),
            no_ask_price=Decimal("0.4000"),
            notional_value=Decimal("1.0000"),
            previous_yes_bid=Decimal("0.5900"),
            previous_yes_ask=Decimal("0.6100"),
            previous_price=Decimal("0.6000"),
        )

        # Verify the function completed (3 SQL calls: dim INSERT + 0062
        # canonical market_key UPDATE + snap INSERT)
        assert mock_cursor.execute.call_count == 3


@pytest.mark.unit
class TestUpdateMarketEnrichment:
    """Unit tests for update_market_with_versioning with enrichment fields.

    Verifies that dimension enrichment (expiration_value, notional_value) goes
    to the UPDATE on markets table, and snapshot enrichment (volume_24h,
    previous_*, yes_bid_size, yes_ask_size) goes to the new snapshot INSERT.

    Reference:
        - Migration 0046: depth signals + daily movement columns
        - Issue #513: Kalshi API enrichment (P1)
    """

    @patch("precog.database.crud_markets.get_current_market")
    @patch("precog.database.crud_markets.get_cursor")
    def test_update_market_with_enrichment_fields(self, mock_get_cursor, mock_get_current):
        """All 8 enrichment fields are passed through on update path.

        Dimension fields go to UPDATE markets SET ..., and snapshot fields
        go to INSERT INTO market_snapshots (...).

        Issue #625: update_market_with_versioning now wraps its mutation
        body in retry_on_scd_unique_conflict. Execute call sequence is:
            [0] SELECT NOW() AS ts
            [1] SELECT id ... FOR UPDATE (market_snapshots lock)
            [2] UPDATE markets SET ...          <- dimension UPDATE
            [3] UPDATE market_snapshots ... (close)
            [4] INSERT INTO market_snapshots ...
        """
        from datetime import datetime as _dt

        # Mock existing market (current state)
        mock_get_current.return_value = {
            "id": 42,
            "yes_ask_price": Decimal("0.5000"),
            "no_ask_price": Decimal("0.5000"),
            "status": "open",
            "volume": 100,
            "open_interest": 50,
            "metadata": None,
            "spread": Decimal("0.0200"),
            "yes_bid_price": Decimal("0.4900"),
            "no_bid_price": Decimal("0.4900"),
            "last_price": Decimal("0.5000"),
            "liquidity": Decimal("10.0000"),
            "subtitle": "Week 14",
            "open_time": "2026-01-01T00:00:00Z",
            "close_time": "2026-01-15T18:00:00Z",
            "expiration_time": "2026-01-15T23:59:00Z",
            "outcome_label": "YES",
            "subcategory": "nfl",
            "bracket_count": 2,
            "source_url": "https://kalshi.com/markets/kxnflgame/NFL-KC-BUF-YES",
            "settlement_value": None,
            # Migration 0046 fields (existing values)
            "expiration_value": None,
            "notional_value": None,
            "volume_24h": None,
            "previous_yes_bid": None,
            "previous_yes_ask": None,
            "previous_price": None,
            "yes_bid_size": None,
            "yes_ask_size": None,
        }

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ts": _dt(2026, 1, 15, 12, 0, 0, tzinfo=UTC)}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        update_market_with_versioning(
            ticker="NFL-KC-BUF-YES",
            yes_ask_price=Decimal("0.5500"),
            no_ask_price=Decimal("0.4500"),
            # Migration 0046: dimension enrichment
            expiration_value="Chiefs win",
            notional_value=Decimal("1.0000"),
            # Migration 0046: snapshot enrichment
            volume_24h=200,
            previous_yes_bid=Decimal("0.5000"),
            previous_yes_ask=Decimal("0.5200"),
            previous_price=Decimal("0.5100"),
            yes_bid_size=60,
            yes_ask_size=40,
        )

        # Issue #625: 5 execute calls now:
        # SELECT NOW(), FOR UPDATE lock, dim UPDATE, snap close, snap INSERT
        assert mock_cursor.execute.call_count == 5

        # Verify dimension UPDATE includes expiration_value and notional_value
        # (now at index 2)
        dim_call = mock_cursor.execute.call_args_list[2]
        dim_sql = dim_call[0][0]
        dim_params = dim_call[0][1]
        assert "expiration_value" in dim_sql
        assert "notional_value" in dim_sql
        assert "Chiefs win" in dim_params
        assert Decimal("1.0000") in dim_params

        # Verify snapshot INSERT includes all 6 new fields (now at index 4)
        snap_call = mock_cursor.execute.call_args_list[4]
        snap_sql = snap_call[0][0]
        snap_params = snap_call[0][1]
        assert "volume_24h" in snap_sql
        assert "previous_yes_bid" in snap_sql
        assert "previous_yes_ask" in snap_sql
        assert "previous_price" in snap_sql
        assert "yes_bid_size" in snap_sql
        assert "yes_ask_size" in snap_sql
        assert 200 in snap_params  # volume_24h
        assert Decimal("0.5000") in snap_params  # previous_yes_bid
        assert Decimal("0.5200") in snap_params  # previous_yes_ask
        assert Decimal("0.5100") in snap_params  # previous_price
        assert 60 in snap_params  # yes_bid_size
        assert 40 in snap_params  # yes_ask_size

    @patch("precog.database.crud_markets.get_current_market")
    @patch("precog.database.crud_markets.get_cursor")
    def test_update_market_enrichment_falls_back_to_current(
        self, mock_get_cursor, mock_get_current
    ):
        """When enrichment fields are not provided, falls back to current values.

        Educational Note:
            The update function merges new values with existing ones. If a new
            enrichment field is None (not provided), the existing value from the
            current snapshot is carried forward. This prevents data loss when the
            poller only updates prices without re-providing all enrichment fields.

            Issue #625: dimension UPDATE is at call_args_list[2] and snapshot
            INSERT is at call_args_list[4] (shifted by SELECT NOW() +
            FOR UPDATE lock at [0] and [1]).
        """
        from datetime import datetime as _dt

        # Mock existing market with enrichment values already populated
        mock_get_current.return_value = {
            "id": 42,
            "yes_ask_price": Decimal("0.5000"),
            "no_ask_price": Decimal("0.5000"),
            "status": "open",
            "volume": 100,
            "open_interest": 50,
            "metadata": None,
            "spread": Decimal("0.0200"),
            "yes_bid_price": Decimal("0.4900"),
            "no_bid_price": Decimal("0.4900"),
            "last_price": Decimal("0.5000"),
            "liquidity": Decimal("10.0000"),
            "subtitle": None,
            "open_time": None,
            "close_time": None,
            "expiration_time": None,
            "outcome_label": None,
            "subcategory": "nfl",
            "bracket_count": None,
            "source_url": None,
            "settlement_value": None,
            # Existing enrichment values that should be preserved
            "expiration_value": "Chiefs win",
            "notional_value": Decimal("1.0000"),
            "volume_24h": 150,
            "previous_yes_bid": Decimal("0.4800"),
            "previous_yes_ask": Decimal("0.5100"),
            "previous_price": Decimal("0.4900"),
            "yes_bid_size": 30,
            "yes_ask_size": 25,
        }

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ts": _dt(2026, 1, 15, 12, 0, 0, tzinfo=UTC)}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Only update prices -- no enrichment fields provided
        update_market_with_versioning(
            ticker="NFL-KC-BUF-YES",
            yes_ask_price=Decimal("0.5500"),
            no_ask_price=Decimal("0.4500"),
        )

        # Issue #625: dim UPDATE at index 2, snap INSERT at index 4.
        dim_params = mock_cursor.execute.call_args_list[2][0][1]
        assert "Chiefs win" in dim_params  # expiration_value preserved
        assert Decimal("1.0000") in dim_params  # notional_value preserved

        # Verify snapshot INSERT carries forward existing enrichment values
        snap_params = mock_cursor.execute.call_args_list[4][0][1]
        assert 150 in snap_params  # volume_24h preserved
        assert Decimal("0.4800") in snap_params  # previous_yes_bid preserved
        assert Decimal("0.5100") in snap_params  # previous_yes_ask preserved
        assert Decimal("0.4900") in snap_params  # previous_price preserved
        assert 30 in snap_params  # yes_bid_size preserved
        assert 25 in snap_params  # yes_ask_size preserved

    @patch("precog.database.crud_markets.get_current_market")
    @patch("precog.database.crud_markets.get_cursor")
    def test_update_market_integer_fields_pass_through(self, mock_get_cursor, mock_get_current):
        """Integer enrichment fields (volume_24h, yes_bid_size, yes_ask_size)
        are passed through without Decimal validation.

        Educational Note:
            These fields are contract counts, not dollar prices. They are
            stored as INTEGER in the database, not DECIMAL(10,4). They should
            NOT go through validate_decimal() -- that would be a type error.

            Issue #625: snapshot INSERT is at call_args_list[4] (shifted by
            SELECT NOW() and FOR UPDATE lock).
        """
        from datetime import datetime as _dt

        mock_get_current.return_value = {
            "id": 42,
            "yes_ask_price": Decimal("0.5000"),
            "no_ask_price": Decimal("0.5000"),
            "status": "open",
            "volume": 100,
            "open_interest": 50,
            "metadata": None,
            "spread": None,
            "yes_bid_price": None,
            "no_bid_price": None,
            "last_price": None,
            "liquidity": None,
            "subtitle": None,
            "open_time": None,
            "close_time": None,
            "expiration_time": None,
            "outcome_label": None,
            "subcategory": None,
            "bracket_count": None,
            "source_url": None,
            "settlement_value": None,
            "expiration_value": None,
            "notional_value": None,
            "volume_24h": None,
            "previous_yes_bid": None,
            "previous_yes_ask": None,
            "previous_price": None,
            "yes_bid_size": None,
            "yes_ask_size": None,
        }

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ts": _dt(2026, 1, 15, 12, 0, 0, tzinfo=UTC)}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Pass integer values directly -- no Decimal wrapping needed
        update_market_with_versioning(
            ticker="NFL-KC-BUF-YES",
            yes_ask_price=Decimal("0.5500"),
            no_ask_price=Decimal("0.4500"),
            volume_24h=500,
            yes_bid_size=100,
            yes_ask_size=75,
        )

        # Issue #625: snapshot INSERT is at index 4.
        snap_params = mock_cursor.execute.call_args_list[4][0][1]
        assert 500 in snap_params  # volume_24h as int
        assert 100 in snap_params  # yes_bid_size as int
        assert 75 in snap_params  # yes_ask_size as int
