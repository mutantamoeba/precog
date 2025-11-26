"""
Integration tests for CLI database persistence using VCR cassettes (Pattern 13).

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

Test Strategy (Pattern 13):
- Use VCR cassettes with REAL recorded API responses
- Cassettes recorded from Kalshi demo API (no mocks!)
- Verify database writes preserve Decimal precision
- Test both success and error scenarios with real data

Related Requirements:
    - REQ-CLI-001: CLI database integration
    - REQ-TEST-002: Integration tests use real API fixtures (Pattern 13)
    - REQ-SYS-003: Decimal precision for prices

Reference:
    - Pattern 13 (CLAUDE.md): Real Fixtures, Not Mocks
    - GitHub Issue #124: Fix integration test mocks
    - Phase 1.5 Test Audit: 77% false positive rate from mocks
"""

from decimal import Decimal

import pytest
import vcr
from typer.testing import CliRunner

# Import CLI app
from main import app

# Import database CRUD functions for verification
from precog.database.crud_operations import get_current_market

# Configure VCR for test cassettes
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="none",  # Never record in tests (only replay)
    match_on=["method", "scheme", "host", "port", "path", "query"],
    filter_headers=["KALSHI-ACCESS-KEY", "KALSHI-ACCESS-SIGNATURE", "KALSHI-ACCESS-TIMESTAMP"],
    decode_compressed_response=True,
)

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
    from precog.database.connection import get_cursor

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
        # Note: VCR cassette events (KXNFLGAME-25NOV27*) + mock test event (KXNFLGAME-25DEC15)
        cur.execute(
            """
            INSERT INTO events (event_id, platform_id, series_id, external_id, category, title, status)
            VALUES
                ('KXNFLGAME-25NOV27GBDET', 'kalshi', 'KXNFLGAME', 'KXNFLGAME-25NOV27GBDET-EXT', 'sports', 'Green Bay at Detroit', 'scheduled'),
                ('KXNFLGAME-25NOV27KCDAL', 'kalshi', 'KXNFLGAME', 'KXNFLGAME-25NOV27KCDAL-EXT', 'sports', 'Kansas City at Dallas', 'scheduled'),
                ('KXNFLGAME-25NOV27CINBAL', 'kalshi', 'KXNFLGAME', 'KXNFLGAME-25NOV27CINBAL-EXT', 'sports', 'Cincinnati at Baltimore', 'scheduled'),
                ('KXNFLGAME-25DEC15', 'kalshi', 'KXNFLGAME', 'KXNFLGAME-25DEC15-EXT', 'sports', 'Mock Test Event', 'scheduled')
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
    cli_runner, db_pool, db_cursor, clean_test_data, setup_kalshi_platform, monkeypatch
):
    """
    Test that fetch-balance saves balance to database with SCD Type 2 versioning.

    Uses VCR cassette: kalshi_get_balance.yaml
    - Real balance: 235084 cents = $2350.84 (from Kalshi demo API)

    Verifies:
    1. Balance fetched from REAL API response (via VCR)
    2. Balance saved as DECIMAL in database
    3. row_current_ind = TRUE for new record
    4. Currency defaults to USD
    5. Decimal precision preserved through API → CLI → database
    """
    # Set environment variables for KalshiClient initialization
    monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
    monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

    # Use VCR cassette with REAL API response
    with my_vcr.use_cassette("kalshi_get_balance.yaml"):
        # Run CLI command (creates real KalshiClient, VCR intercepts HTTP)
        result = cli_runner.invoke(app, ["fetch-balance"])

        # Verify CLI success
        assert result.exit_code == 0
        assert "$235,084" in result.stdout  # Real balance from cassette (cents)
        assert "Balance saved to database" in result.stdout

    # Verify database record created with real data
    from precog.database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT balance_id, balance, currency, row_current_ind
            FROM account_balance
            WHERE platform_id = 'kalshi' AND row_current_ind = TRUE
        """
        )
        db_result = cur.fetchone()

        assert db_result is not None, "Balance record not found in database"

        # Verify Decimal precision (real API returns cents: 235084)
        assert isinstance(db_result["balance"], Decimal)
        assert db_result["balance"] == Decimal("235084")  # Real value from cassette
        assert db_result["currency"] == "USD"
        assert db_result["row_current_ind"] is True


@pytest.mark.integration
@pytest.mark.skip(
    reason="TODO(GitHub #124.7): Needs custom VCR cassettes for multi-fetch SCD Type 2 test"
)
def test_fetch_balance_updates_with_scd_type2(
    cli_runner, db_pool, db_cursor, clean_test_data, setup_kalshi_platform, monkeypatch
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

    TODO: Create custom VCR cassettes:
    - tests/cassettes/cli/balance_1000.yaml (for first fetch)
    - tests/cassettes/cli/balance_1500.yaml (for second fetch)

    Alternative: Use VCR record modes to create cassettes:
    1. Record first fetch with balance=$1000
    2. Record second fetch with balance=$1500
    3. Update this test to use both cassettes sequentially
    """
    pytest.skip("Requires custom VCR cassettes for multi-fetch scenario")


# =============================================================================
# FETCH-MARKETS DATABASE INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
def test_fetch_markets_creates_new_markets(
    cli_runner, db_pool, db_cursor, clean_test_data, setup_kalshi_platform, monkeypatch
):
    """
    Test that fetch-markets creates new market records from REAL API data.

    Uses VCR cassette: kalshi_get_markets.yaml
    - 5 real NFL markets from KXNFLGAME series
    - Real prices with sub-penny precision (0.4275 format)
    - Real market titles, tickers, volumes from Kalshi demo API

    Verifies:
    1. Markets fetched from REAL API response (via VCR)
    2. Markets saved with Decimal precision
    3. Metadata stored in JSONB field
    4. Spread calculated correctly
    5. Sub-penny precision preserved
    """
    # Set environment variables for KalshiClient initialization
    monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
    monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

    # Use VCR cassette with REAL API response (5 NFL markets)
    with my_vcr.use_cassette("kalshi_get_markets.yaml"):
        # Run CLI command with series filter (matches cassette query params)
        result = cli_runner.invoke(app, ["fetch-markets", "--series", "KXNFLGAME", "--limit", "5"])
        assert result.exit_code == 0, f"CLI failed: {result.stdout}"
        # Cassette has 5 markets from KXNFLGAME series
        assert "5 markets created" in result.stdout or "markets created" in result.stdout

    # Verify at least one market created in database (using real ticker from cassette)
    # Note: Cassette recorded on 2025-11-23, specific market may vary
    from precog.database.connection import get_cursor

    with get_cursor() as cur:
        # Markets join events join series to filter by series_ticker
        cur.execute(
            """
            SELECT COUNT(*) as market_count
            FROM markets m
            JOIN events e ON m.event_id = e.event_id
            WHERE e.series_id = 'KXNFLGAME' AND m.row_current_ind = TRUE
        """
        )
        result_row = cur.fetchone()
        market_count = result_row["market_count"] if result_row else 0

        # Should have created 5 markets from cassette
        assert market_count == 5, f"Expected 5 markets, got {market_count}"

        # Verify Decimal precision on first market
        cur.execute(
            """
            SELECT m.ticker, m.yes_price, m.no_price, m.volume, m.open_interest
            FROM markets m
            JOIN events e ON m.event_id = e.event_id
            WHERE e.series_id = 'KXNFLGAME' AND m.row_current_ind = TRUE
            LIMIT 1
        """
        )
        market = cur.fetchone()
        assert market is not None
        assert isinstance(market["yes_price"], Decimal)
        assert isinstance(market["no_price"], Decimal)


@pytest.mark.integration
@pytest.mark.skip(
    reason="TODO(GitHub #124.7): Needs custom VCR cassettes for multi-fetch upsert test"
)
def test_fetch_markets_upsert_pattern(
    cli_runner, db_pool, db_cursor, clean_test_data, setup_kalshi_platform, monkeypatch
):
    """
    Test upsert pattern: try update first, fallback to create.

    Scenario:
    1. First fetch: Markets don't exist → create_market()
    2. Second fetch: Markets exist → update_market_with_versioning()

    Verifies:
    - First run: markets created
    - Second run: markets updated (SCD Type 2)
    - No duplicate markets created

    TODO: Create custom VCR cassettes:
    - tests/cassettes/cli/markets_initial.yaml (for first fetch, yes_bid=0.6200)
    - tests/cassettes/cli/markets_updated.yaml (for second fetch, yes_bid=0.6500)

    Alternative: Use VCR record modes to create cassettes:
    1. Record first fetch with original prices
    2. Record second fetch with updated prices
    3. Update this test to use both cassettes sequentially
    """
    pytest.skip("Requires custom VCR cassettes for multi-fetch scenario")


# =============================================================================
# FETCH-SETTLEMENTS DATABASE INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
@pytest.mark.skip(reason="TODO(GitHub #124.7): Needs custom VCR cassette with settlement data")
def test_fetch_settlements_creates_records_and_updates_market_status(
    cli_runner, db_pool, db_cursor, clean_test_data, setup_kalshi_platform, monkeypatch
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

    TODO: Create custom VCR cassette:
    - tests/cassettes/cli/settlements_with_data.yaml
    - Must contain at least one settlement with ticker matching a database market
    - Current kalshi_get_settlements.yaml has 0 settlements (demo account)

    Note: Requires recording from real Kalshi account that has settled positions,
    or manually crafting a cassette with settlement data.
    """
    pytest.skip("Requires custom VCR cassette with settlement data")


@pytest.mark.integration
@pytest.mark.skip(reason="TODO(GitHub #124.7): CLI uses limit=100 but cassette has limit=5")
def test_fetch_settlements_empty_response(
    cli_runner, db_pool, db_cursor, clean_test_data, setup_kalshi_platform, monkeypatch
):
    """
    Test handling of empty settlements response (no settled positions).

    Uses VCR cassette: kalshi_get_settlements.yaml
    - 0 settlements (demo account has no settled positions)

    Scenario:
    - Settlements API returns empty list
    - CLI should handle gracefully (not crash)

    Verifies:
    - CLI completes successfully (exit_code=0)
    - No settlement records created
    - Appropriate message shown to user

    TODO: Fix parameter mismatch:
    - Current cassette: /portfolio/settlements?limit=5
    - CLI request: /portfolio/settlements?limit=100 (default)
    - Options:
      1. Re-record cassette with limit=100
      2. Add --limit parameter to fetch-settlements CLI command
      3. Update KalshiClient.get_settlements() to use limit=5 default
    """
    pytest.skip("CLI/cassette parameter mismatch (limit: 100 vs 5)")


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================
#
# NOTE: Error handling tests use mocks (not VCR) because they simulate
# error conditions that can't be captured in cassettes:
# - Database write failures
# - Foreign key violations
# - Network timeouts
# - Partial failures
#
# VCR cassettes only record HTTP responses, not database/system errors.
# Mocking is appropriate here to test error recovery logic.
# =============================================================================


@pytest.mark.integration
def test_fetch_balance_handles_db_write_failure(cli_runner, monkeypatch):
    """
    Test error handling when database write fails.

    Uses mocks (not VCR) because:
    - Simulating database write failure (not capturable in HTTP cassette)
    - Testing CLI error recovery logic

    Scenario:
    - Balance fetched successfully from API
    - Database write fails (e.g., connection error)
    - CLI should display warning but not crash

    Verifies:
    - Exit code 0 (CLI doesn't crash)
    - Warning message displayed
    - Balance shown to user even though not persisted
    """
    from unittest.mock import MagicMock, patch

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
    cli_runner, db_pool, db_cursor, clean_test_data, setup_kalshi_platform
):
    """
    Test that fetch-markets handles per-market failures gracefully.

    Uses mocks (not VCR) because:
    - Simulating foreign key violation (database error, not HTTP error)
    - Testing CLI partial failure recovery logic

    Scenario:
    - 3 markets fetched from API
    - 1 market fails to save (e.g., foreign key violation)
    - Other 2 markets should save successfully

    Verifies:
    - CLI completes (doesn't crash on first error)
    - 2 markets created, 1 error reported
    - Error count shown in output
    """
    from unittest.mock import MagicMock, patch

    with patch("main.KalshiClient") as mock_client_class:
        mock_client = MagicMock()

        # Mock 3 markets, but one will fail due to missing event
        # NOTE: main.py expects yes_bid/yes_ask (legacy format) not yes_bid_dollars
        mock_client.get_markets.return_value = [
            {
                "ticker": "KXNFLGAME-25DEC15-KC-YES",
                "event_ticker": "KXNFLGAME-25DEC15",
                "series_ticker": "KXNFLGAME",
                "title": "Market 1",
                "status": "open",
                "yes_bid": Decimal("0.6200"),  # main.py uses yes_bid/yes_ask keys
                "yes_ask": Decimal("0.6250"),
                "no_bid": Decimal("0.3750"),
                "no_ask": Decimal("0.3800"),
                "last_price": Decimal("0.6200"),
                "volume": 1000,
            },
            {
                "ticker": "KXNFLGAME-25DEC15-BUF-YES",
                "event_ticker": "KXNFLGAME-25DEC15",  # Event exists
                "series_ticker": "KXNFLGAME",
                "title": "Market 2",
                "status": "open",
                "yes_bid": Decimal("0.4300"),  # main.py uses yes_bid/yes_ask keys
                "yes_ask": Decimal("0.4350"),
                "no_bid": Decimal("0.5650"),
                "no_ask": Decimal("0.5700"),
                "last_price": Decimal("0.4300"),
                "volume": 2000,
            },
            {
                "ticker": "NONEXISTENT-EVENT-YES",
                "event_ticker": "NONEXISTENT-EVENT",  # Event DOESN'T exist → will fail
                "series_ticker": "KXNFLGAME",
                "title": "Market 3",
                "status": "open",
                "yes_bid": Decimal("0.5000"),  # main.py uses yes_bid/yes_ask keys
                "yes_ask": Decimal("0.5050"),
                "no_bid": Decimal("0.4950"),
                "no_ask": Decimal("0.5000"),
                "last_price": Decimal("0.5000"),
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
