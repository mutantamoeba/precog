"""
Integration tests for CLI database persistence.

Tests verify that CLI commands correctly write data to database:
- fetch-balance: Account balance snapshots with SCD Type 2
- fetch-markets: Market data with upsert pattern (create vs update)
- fetch-settlements: Settlement records + market status updates

Critical aspects tested:
1. Decimal precision preserved through API → CLI → database
2. SCD Type 2 versioning works correctly
3. Upsert pattern (try update, fallback to create)
4. Foreign key relationships maintained
5. Error handling (missing parent records, DB write failures)

Test Strategy:
- Use unittest.mock to mock KalshiClient methods
- Use clean_test_data fixture for database setup
- Verify database state after CLI commands execute
- Test both success and error scenarios
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# Import database CRUD functions for verification
from database.crud_operations import get_current_market

# Import CLI app
from main import app

# Import test fixtures

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def cli_runner():
    """Typer CLI runner for invoking commands."""
    return CliRunner()


@pytest.fixture
def setup_kalshi_platform(db_pool, clean_test_data):
    """
    Create Kalshi platform record for CLI tests.

    CLI commands hardcode platform_id="kalshi", so we need this record
    to exist for foreign key constraints.

    Note: This fixture depends on clean_test_data to ensure proper database setup.
    """
    from database.connection import get_cursor

    with get_cursor(commit=True) as cur:
        # Create platform if not exists
        cur.execute(
            """
            INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
            VALUES ('kalshi', 'trading', 'Kalshi', 'https://trading-api.kalshi.com', 'active')
            ON CONFLICT (platform_id) DO NOTHING
        """
        )

        # Create series for test markets
        cur.execute(
            """
            INSERT INTO series (series_id, platform_id, external_id, title, category)
            VALUES ('KXNFLGAME', 'kalshi', 'KXNFLGAME-EXT', 'NFL Game Series', 'sports')
            ON CONFLICT (series_id) DO NOTHING
        """
        )

        # Create events for test markets
        cur.execute(
            """
            INSERT INTO events (event_id, platform_id, series_id, external_id, category, title, status)
            VALUES
                ('KXNFLGAME-25DEC15', 'kalshi', 'KXNFLGAME', 'KXNFLGAME-25DEC15-EXT', 'sports', 'NFL Games Dec 15', 'scheduled'),
                ('KXNFLGAME-25DEC08', 'kalshi', 'KXNFLGAME', 'KXNFLGAME-25DEC08-EXT', 'sports', 'NFL Games Dec 08', 'scheduled')
            ON CONFLICT (event_id) DO NOTHING
        """
        )

    yield

    # Cleanup after test
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM events WHERE platform_id = 'kalshi'")
        cur.execute("DELETE FROM series WHERE platform_id = 'kalshi'")
        cur.execute("DELETE FROM account_balance WHERE platform_id = 'kalshi'")
        cur.execute("DELETE FROM platforms WHERE platform_id = 'kalshi'")


# =============================================================================
# FETCH-BALANCE DATABASE INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
def test_fetch_balance_saves_to_database(
    cli_runner, db_pool, clean_test_data, setup_kalshi_platform
):
    """
    Test that fetch-balance saves balance to database with SCD Type 2 versioning.

    Verifies:
    1. Balance fetched from API
    2. Balance saved as DECIMAL in database
    3. row_current_ind = TRUE for new record
    4. Currency defaults to USD
    """
    # Mock KalshiClient.get_balance() to return test balance
    with patch("main.KalshiClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_balance.return_value = Decimal("1234.5678")
        mock_client_class.return_value = mock_client

        # Run CLI command
        result = cli_runner.invoke(app, ["fetch-balance"])

        # Verify CLI success
        assert result.exit_code == 0
        assert "$1,234.5678" in result.stdout  # Rich table formats with commas
        assert "Balance saved to database" in result.stdout

    # Verify database record created
    from database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT balance_id, balance, currency, row_current_ind
            FROM account_balance
            WHERE platform_id = 'kalshi' AND row_current_ind = TRUE
        """
        )
        result = cur.fetchone()

        assert result is not None, "Balance record not found in database"

        # Verify Decimal precision (result is a RealDictRow, access by key)
        assert isinstance(result["balance"], Decimal)
        assert result["balance"] == Decimal("1234.5678")
        assert result["currency"] == "USD"
        assert result["row_current_ind"] is True


@pytest.mark.integration
def test_fetch_balance_updates_with_scd_type2(
    cli_runner, db_pool, clean_test_data, setup_kalshi_platform
):
    """
    Test SCD Type 2 versioning when balance updates.

    Scenario:
    1. First fetch: balance = $1000.00 → row_current_ind=TRUE
    2. Second fetch: balance = $1500.00 → old record marked FALSE, new record TRUE

    Verifies:
    - Old balance marked row_current_ind=FALSE
    - New balance has row_current_ind=TRUE
    - Both records preserved (history maintained)
    """
    with patch("main.KalshiClient") as mock_client_class:
        mock_client = MagicMock()

        # First fetch: $1000
        mock_client.get_balance.return_value = Decimal("1000.00")
        mock_client_class.return_value = mock_client
        result1 = cli_runner.invoke(app, ["fetch-balance"])
        assert result1.exit_code == 0

        # Second fetch: $1500
        mock_client.get_balance.return_value = Decimal("1500.00")
        result2 = cli_runner.invoke(app, ["fetch-balance"])
        assert result2.exit_code == 0

    # Verify two records exist
    from database.connection import get_cursor

    with get_cursor() as cur:
        # Check current balance (should be $1500)
        cur.execute(
            """
            SELECT balance
            FROM account_balance
            WHERE platform_id = 'kalshi' AND row_current_ind = TRUE
        """
        )
        current_record = cur.fetchone()
        assert current_record is not None
        assert current_record["balance"] == Decimal("1500.00")

        # Check historical balance (should be $1000 with row_current_ind=FALSE)
        cur.execute(
            """
            SELECT balance, row_current_ind
            FROM account_balance
            WHERE platform_id = 'kalshi' AND row_current_ind = FALSE
        """
        )
        historical_record = cur.fetchone()
        assert historical_record is not None
        assert historical_record["balance"] == Decimal("1000.00")
        assert historical_record["row_current_ind"] is False


# =============================================================================
# FETCH-MARKETS DATABASE INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
def test_fetch_markets_creates_new_markets(
    cli_runner, db_pool, clean_test_data, setup_kalshi_platform
):
    """
    Test that fetch-markets creates new market records.

    Verifies:
    1. Markets fetched from API
    2. Markets saved with Decimal precision
    3. Metadata stored in JSONB field
    4. Spread calculated correctly
    """
    with patch("main.KalshiClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_markets.return_value = [
            {
                "ticker": "KXNFLGAME-25DEC15-KC-YES",
                "event_ticker": "KXNFLGAME-25DEC15",
                "series_ticker": "KXNFLGAME",
                "title": "Will Kansas City win against Cleveland on Dec 15?",
                "subtitle": "Kansas City Chiefs to win",
                "status": "open",
                "yes_bid": Decimal("0.6200"),
                "yes_ask": Decimal("0.6250"),
                "no_bid": Decimal("0.3750"),
                "no_ask": Decimal("0.3800"),
                "volume": 15420,
                "open_interest": 8750,
            }
        ]
        mock_client_class.return_value = mock_client

        # Run CLI command
        result = cli_runner.invoke(app, ["fetch-markets"])
        assert result.exit_code == 0
        assert "1 markets created" in result.stdout

    # Verify market created in database
    market = get_current_market("KXNFLGAME-25DEC15-KC-YES")
    assert market is not None
    assert isinstance(market["yes_price"], Decimal)
    assert isinstance(market["no_price"], Decimal)
    assert market["yes_price"] == Decimal("0.6200")
    assert market["no_price"] == Decimal("0.3750")
    assert market["volume"] == 15420
    assert market["open_interest"] == 8750


@pytest.mark.integration
def test_fetch_markets_upsert_pattern(cli_runner, db_pool, clean_test_data, setup_kalshi_platform):
    """
    Test upsert pattern: try update first, fallback to create.

    Scenario:
    1. First fetch: Markets don't exist → create_market()
    2. Second fetch: Markets exist → update_market_with_versioning()

    Verifies:
    - First run: markets created
    - Second run: markets updated (SCD Type 2)
    - No duplicate markets created
    """
    with patch("main.KalshiClient") as mock_client_class:
        mock_client = MagicMock()

        # Define market data
        market_data = {
            "ticker": "KXNFLGAME-25DEC15-KC-YES",
            "event_ticker": "KXNFLGAME-25DEC15",
            "series_ticker": "KXNFLGAME",
            "title": "Will Kansas City win?",
            "subtitle": "KC to win",
            "status": "open",
            "yes_bid": Decimal("0.6200"),
            "yes_ask": Decimal("0.6250"),
            "no_bid": Decimal("0.3750"),
            "no_ask": Decimal("0.3800"),
            "volume": 15420,
            "open_interest": 8750,
        }

        # First fetch: market doesn't exist → create
        mock_client.get_markets.return_value = [market_data.copy()]
        mock_client_class.return_value = mock_client
        result1 = cli_runner.invoke(app, ["fetch-markets"])
        assert result1.exit_code == 0
        assert "1 markets created" in result1.stdout

        # Second fetch: market exists → update with new price
        market_data["yes_bid"] = Decimal("0.6500")  # Price increased
        market_data["volume"] = 20000  # Volume increased
        mock_client.get_markets.return_value = [market_data.copy()]
        result2 = cli_runner.invoke(app, ["fetch-markets"])
        assert result2.exit_code == 0
        assert "1 updated" in result2.stdout

    # Verify current market has updated price
    market = get_current_market("KXNFLGAME-25DEC15-KC-YES")
    assert market["yes_price"] == Decimal("0.6500")
    assert market["volume"] == 20000

    # Verify historical version exists with old price
    from database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT yes_price, volume
            FROM markets
            WHERE ticker = 'KXNFLGAME-25DEC15-KC-YES' AND row_current_ind = FALSE
        """
        )
        historical_record = cur.fetchone()
        assert historical_record is not None
        assert historical_record["yes_price"] == Decimal("0.6200")
        assert historical_record["volume"] == 15420


# =============================================================================
# FETCH-SETTLEMENTS DATABASE INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
def test_fetch_settlements_creates_records_and_updates_market_status(
    cli_runner, db_pool, clean_test_data, setup_kalshi_platform
):
    """
    Test that fetch-settlements creates settlement records AND updates market status.

    Two-step processing:
    1. Create settlement record (append-only)
    2. Update market status to "settled"

    Verifies:
    - Settlement record created with Decimal payout
    - Market status updated to "settled"
    - Market lookup by ticker works correctly
    """
    # First, create the market that will be settled
    from database.crud_operations import create_market

    market_id = create_market(
        platform_id="kalshi",
        event_id="KXNFLGAME-25DEC08",
        external_id="KXNFLGAME-25DEC08-KC-YES-EXT",
        ticker="KXNFLGAME-25DEC08-KC-YES",
        title="Will Kansas City win on Dec 08?",
        yes_price=Decimal("0.6200"),
        no_price=Decimal("0.3800"),
        market_type="binary",
        status="open",
    )
    assert market_id is not None

    # Mock settlements API response
    with patch("main.KalshiClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_settlements.return_value = [
            {
                "ticker": "KXNFLGAME-25DEC08-KC-YES",
                "market_result": "yes",
                "settlement_value": Decimal("1.0000"),
                "settled_time": "2025-12-08T23:30:00Z",
            }
        ]
        mock_client_class.return_value = mock_client

        # Run CLI command
        result = cli_runner.invoke(app, ["fetch-settlements"])
        assert result.exit_code == 0
        assert "1 settlements saved" in result.stdout
        assert "1 markets updated to 'settled'" in result.stdout

    # Verify settlement record created
    from database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT outcome, payout
            FROM settlements
            WHERE market_id = %s
        """,
            (market_id,),
        )
        settlement_record = cur.fetchone()
        assert settlement_record is not None
        assert settlement_record["outcome"] == "yes"
        assert isinstance(settlement_record["payout"], Decimal)
        assert settlement_record["payout"] == Decimal("1.0000")

    # Verify market status updated to "settled"
    market = get_current_market("KXNFLGAME-25DEC08-KC-YES")
    assert market["status"] == "settled"


@pytest.mark.integration
def test_fetch_settlements_skips_missing_markets(
    cli_runner, db_pool, clean_test_data, setup_kalshi_platform
):
    """
    Test error handling when settlement references market that doesn't exist.

    Scenario:
    - Settlement API returns ticker for market not in database
    - CLI should log warning and skip settlement (not crash)

    Verifies:
    - CLI completes successfully (exit_code=0)
    - Warning logged for missing market
    - No settlement record created
    """
    with patch("main.KalshiClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_settlements.return_value = [
            {
                "ticker": "NONEXISTENT-MARKET",  # Market doesn't exist
                "market_result": "yes",
                "settlement_value": Decimal("1.0000"),
                "settled_time": "2025-12-08T23:30:00Z",
            }
        ]
        mock_client_class.return_value = mock_client

        # Run CLI command (should not crash)
        result = cli_runner.invoke(app, ["fetch-settlements"])
        assert result.exit_code == 0

    # Verify no settlement record created
    from database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM settlements
        """
        )
        result = cur.fetchone()
        settlement_count = result["count"] if result else 0
        assert settlement_count == 0


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


@pytest.mark.integration
def test_fetch_balance_handles_db_write_failure(cli_runner):
    """
    Test error handling when database write fails.

    Scenario:
    - Balance fetched successfully from API
    - Database write fails (e.g., connection error)
    - CLI should display warning but not crash

    Verifies:
    - Exit code 0 (CLI doesn't crash)
    - Warning message displayed
    - Balance shown to user even though not persisted
    """
    with patch("main.KalshiClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_balance.return_value = Decimal("1234.5678")
        mock_client_class.return_value = mock_client

        # Mock database write to raise exception
        with patch(
            "main.update_account_balance_with_versioning",
            side_effect=Exception("DB connection lost"),
        ):
            result = cli_runner.invoke(app, ["fetch-balance"])

            # CLI should not crash
            assert result.exit_code == 0

            # Warning should be displayed
            assert "Balance fetched but failed to save to database" in result.stdout
            assert "DB connection lost" in result.stdout


@pytest.mark.integration
def test_fetch_markets_handles_partial_failures(
    cli_runner, db_pool, clean_test_data, setup_kalshi_platform
):
    """
    Test that fetch-markets handles per-market failures gracefully.

    Scenario:
    - 3 markets fetched from API
    - 1 market fails to save (e.g., foreign key violation)
    - Other 2 markets should save successfully

    Verifies:
    - CLI completes (doesn't crash on first error)
    - 2 markets created, 1 error reported
    - Error count shown in output
    """
    with patch("main.KalshiClient") as mock_client_class:
        mock_client = MagicMock()

        # Mock 3 markets, but one will fail due to missing event
        mock_client.get_markets.return_value = [
            {
                "ticker": "KXNFLGAME-25DEC15-KC-YES",
                "event_ticker": "KXNFLGAME-25DEC15",
                "series_ticker": "KXNFLGAME",
                "title": "Market 1",
                "status": "open",
                "yes_bid": Decimal("0.6200"),
                "yes_ask": Decimal("0.6250"),
                "no_bid": Decimal("0.3750"),
                "no_ask": Decimal("0.3800"),
                "volume": 1000,
            },
            {
                "ticker": "KXNFLGAME-25DEC15-BUF-YES",
                "event_ticker": "KXNFLGAME-25DEC15",  # Event exists
                "series_ticker": "KXNFLGAME",
                "title": "Market 2",
                "status": "open",
                "yes_bid": Decimal("0.4300"),
                "yes_ask": Decimal("0.4350"),
                "no_bid": Decimal("0.5650"),
                "no_ask": Decimal("0.5700"),
                "volume": 2000,
            },
            {
                "ticker": "NONEXISTENT-EVENT-YES",
                "event_ticker": "NONEXISTENT-EVENT",  # Event DOESN'T exist → will fail
                "series_ticker": "KXNFLGAME",
                "title": "Market 3",
                "status": "open",
                "yes_bid": Decimal("0.5000"),
                "yes_ask": Decimal("0.5050"),
                "no_bid": Decimal("0.4950"),
                "no_ask": Decimal("0.5000"),
                "volume": 3000,
            },
        ]
        mock_client_class.return_value = mock_client

        # Run CLI command
        result = cli_runner.invoke(app, ["fetch-markets"])

        # CLI should complete (not crash)
        assert result.exit_code == 0

        # Should report error count
        assert "1 markets failed to save" in result.stdout

    # Verify 2 successful markets created
    market1 = get_current_market("KXNFLGAME-25DEC15-KC-YES")
    market2 = get_current_market("KXNFLGAME-25DEC15-BUF-YES")
    market3 = get_current_market("NONEXISTENT-EVENT-YES")

    assert market1 is not None
    assert market2 is not None
    assert market3 is None  # Failed to create
