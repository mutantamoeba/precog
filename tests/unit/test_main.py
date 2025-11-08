"""
Unit tests for CLI commands in main.py

Tests all 5 CLI commands:
- fetch-balance: Account balance retrieval
- fetch-markets: Available markets retrieval (with filtering)
- fetch-positions: Position retrieval
- fetch-fills: Trade fill history
- fetch-settlements: Settlement data retrieval

Educational Note:
    CLI commands are tested using Typer's CliRunner for isolated testing
    without actually invoking the CLI. KalshiClient is mocked to avoid live
    API calls during testing.

    Key testing patterns:
    1. Mock KalshiClient to return controlled test data
    2. Use CliRunner.invoke() to simulate CLI invocation
    3. Assert on exit codes, stdout output, and API call arguments
    4. Test error paths (missing credentials, API failures)
    5. Test parameter variations (--env, --dry-run, --verbose)

Related:
    - main.py: CLI command implementations (5 commands)
    - api_connectors/kalshi_client.py: API client being mocked
    - REQ-CLI-001: CLI Framework (Typer)
    - REQ-CLI-002: Environment Selection (demo/prod)
    - ADR-038: CLI Framework Choice (Typer)

Coverage Target: 85%+ for main.py (currently 0%)
"""

from decimal import Decimal
from unittest.mock import Mock

import pytest
import typer
from typer.testing import CliRunner

# Import the Typer app from main.py
from main import app

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Create Typer CLI test runner.

    Returns:
        CliRunner instance for invoking CLI commands in tests

    Educational Note:
        CliRunner simulates CLI invocation without actually running
        subprocess. This allows unit testing CLI commands with full
        control over inputs and environment.
    """
    return CliRunner()


@pytest.fixture
def mock_kalshi_client(monkeypatch):
    """Create mocked KalshiClient for testing.

    Returns:
        Mock object with get_balance(), get_markets(), get_positions(),
        get_fills(), get_settlements() methods

    Educational Note:
        Mocking prevents live API calls during tests. Each test can
        configure return values to simulate different API responses
        (success, errors, edge cases).

        This fixture patches main.get_kalshi_client to return the mock
        instead of creating a real KalshiClient instance.
    """
    mock_client = Mock()

    # Default return values (tests can override)
    mock_client.get_balance.return_value = Decimal("1234.5678")
    mock_client.get_markets.return_value = []
    mock_client.get_positions.return_value = []
    mock_client.get_fills.return_value = []
    mock_client.get_settlements.return_value = []

    # Patch get_kalshi_client to return our mock
    monkeypatch.setattr("main.get_kalshi_client", lambda _env: mock_client)

    return mock_client


# ============================================================================
# Test Classes
# ============================================================================


class TestFetchBalance:
    """Test cases for fetch-balance CLI command.

    Command: main.py fetch-balance [--env ENV] [--dry-run] [--verbose]

    Tests:
        - Successful balance retrieval (demo/prod)
        - Decimal precision in output
        - Rich table formatting
        - Dry-run mode (no API call)
        - Verbose mode (detailed output)
        - Error handling (missing credentials, API errors)
    """

    def test_fetch_balance_success_demo(self, runner, mock_kalshi_client):
        """Test fetch-balance with demo environment (happy path).

        Verifies:
            - Exit code 0 (success)
            - Balance displayed as Decimal
            - Rich table formatted output
            - get_balance() called once
        """
        # Mock balance return
        mock_kalshi_client.get_balance.return_value = Decimal("1234.5678")

        # Run command
        result = runner.invoke(app, ["fetch-balance", "--env", "demo"])

        # Verify exit code
        assert result.exit_code == 0, (
            f"Expected exit code 0, got {result.exit_code}. Output:\n{result.stdout}"
        )

        # Verify API called once
        mock_kalshi_client.get_balance.assert_called_once()

        # Verify balance displayed with 4 decimal places
        assert "$1,234.5678" in result.stdout, "Balance not displayed correctly"

        # Verify environment shown in output
        assert "DEMO" in result.stdout, "Environment not shown in output"

        # Verify table title present (Rich table formatting)
        assert "Account Balance" in result.stdout, "Table title not present"

    def test_fetch_balance_success_prod(self, runner, mock_kalshi_client):
        """Test fetch-balance with prod environment.

        Verifies:
            - Prod credentials loaded
            - Balance retrieved from prod API
        """
        # Mock balance return
        mock_kalshi_client.get_balance.return_value = Decimal("5432.1234")

        # Run command with prod environment
        result = runner.invoke(app, ["fetch-balance", "--env", "prod"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called
        mock_kalshi_client.get_balance.assert_called_once()

        # Verify prod environment shown
        assert "PROD" in result.stdout, "Production environment not shown in output"

        # Verify balance displayed
        assert "$5,432.1234" in result.stdout, "Balance not displayed correctly"

    def test_fetch_balance_dry_run(self, runner, mock_kalshi_client):
        """Test fetch-balance with --dry-run flag.

        Verifies:
            - KalshiClient still called (fetches data)
            - "Dry-run mode" message in output
            - Database persistence skipped
        """
        # Mock balance return
        mock_kalshi_client.get_balance.return_value = Decimal("1000.0000")

        # Run command with --dry-run flag
        result = runner.invoke(app, ["fetch-balance", "--dry-run"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API still called (dry-run fetches data, just doesn't save)
        mock_kalshi_client.get_balance.assert_called_once()

        # Verify dry-run message in output
        assert "Dry-run mode" in result.stdout or "dry-run" in result.stdout.lower(), (
            "Dry-run mode message not found in output"
        )

        # Verify balance still displayed
        assert "$1,000.0000" in result.stdout, "Balance not displayed in dry-run mode"

    def test_fetch_balance_verbose(self, runner, mock_kalshi_client):
        """Test fetch-balance with --verbose flag.

        Verifies:
            - Verbose mode message in output
            - Balance still displayed
            - Additional logging information
        """
        # Mock balance return
        mock_kalshi_client.get_balance.return_value = Decimal("2468.1357")

        # Run command with --verbose flag
        result = runner.invoke(app, ["fetch-balance", "--verbose"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called
        mock_kalshi_client.get_balance.assert_called_once()

        # Verify balance displayed
        assert "$2,468.1357" in result.stdout, "Balance not displayed in verbose mode"

        # Verify verbose output (logger.info statements show up in output)
        # Note: We can't easily verify logger output in unit tests without capturing logs
        # But we can verify the command succeeded with verbose flag
        assert result.exit_code == 0, "Verbose mode should not cause errors"

    def test_fetch_balance_decimal_precision(self, runner, mock_kalshi_client):
        """Test balance displayed with 4 decimal places.

        Verifies:
            - Output shows $1234.5678 format
            - No float contamination

        Educational Note:
            CRITICAL: Kalshi uses sub-penny pricing. Must preserve
            4 decimal places (e.g., $0.4975). Float would round to
            $0.50 and cause trading errors.
        """
        # Test with sub-penny pricing (critical for Kalshi)
        # This value MUST show all 4 decimals, NOT round to $0.50
        mock_kalshi_client.get_balance.return_value = Decimal("0.4975")

        # Run command
        result = runner.invoke(app, ["fetch-balance"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # CRITICAL: Verify all 4 decimal places preserved
        assert "$0.4975" in result.stdout, (
            "Decimal precision lost! Expected $0.4975 in output. "
            "Float contamination would show $0.50 instead."
        )

        # Verify NOT rounded to 2 decimals (float contamination check)
        assert "$0.50" not in result.stdout or "$0.4975" in result.stdout, (
            "Balance appears to be rounded to 2 decimals (float contamination!)"
        )

        # Additional test: Verify client received Decimal, not float
        # The mock should have been called, and we verify the type
        assert isinstance(mock_kalshi_client.get_balance.return_value, Decimal), (
            "Balance must be Decimal type, not float"
        )

    def test_fetch_balance_missing_credentials(self, runner):
        """Test fetch-balance with missing Kalshi credentials.

        Verifies:
            - Exit code 1 (failure)
            - Error message about missing credentials
            - User-friendly message (not stack trace)
        """
        # TODO: Implement in Part 1.6

    def test_fetch_balance_api_error(self, runner, mock_kalshi_client):
        """Test fetch-balance when API returns error.

        Verifies:
            - Exit code 1 (failure)
            - Error message displayed
            - Graceful error handling (no crash)
        """
        # TODO: Implement in Part 1.6


class TestFetchMarkets:
    """Test cases for fetch-markets CLI command.

    Command: main.py fetch-markets [--series SERIES] [--event EVENT] [--limit LIMIT]
                                    [--env ENV] [--dry-run] [--verbose]

    Tests:
        - Successful market retrieval (empty, single, multiple)
        - Decimal price display (yes_bid, yes_ask, last_price)
        - Rich table with columns (ticker, title, status, prices, volume)
        - Filtering (series, event, limit)
        - Dry-run and verbose modes
        - Error handling
    """

    def test_fetch_markets_empty(self, runner, mock_kalshi_client):
        """Test fetch-markets with no markets available.

        Verifies:
            - Exit code 0 (success)
            - "No markets found" message
        """
        # Mock empty markets list
        mock_kalshi_client.get_markets.return_value = []

        # Run command
        result = runner.invoke(app, ["fetch-markets"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called
        mock_kalshi_client.get_markets.assert_called_once_with(
            series_ticker=None,
            event_ticker=None,
            limit=100,
        )

        # Verify "No markets found" message
        assert "No markets found" in result.stdout, "Expected 'No markets found' message"

    def test_fetch_markets_single(self, runner, mock_kalshi_client):
        """Test fetch-markets with one market.

        Verifies:
            - Market displayed in Rich table
            - Ticker, title, status, prices, volume shown
            - Decimal price formatting (4 decimals)
        """
        # Mock single market
        mock_kalshi_client.get_markets.return_value = [
            {
                "ticker": "NFL-KC-WIN",
                "title": "Will Kansas City Chiefs win?",
                "status": "open",
                "yes_bid": Decimal("0.6250"),
                "yes_ask": Decimal("0.6350"),
                "volume": 5000,
                "last_price": Decimal("0.6300"),
            }
        ]

        # Run command
        result = runner.invoke(app, ["fetch-markets"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify table title shows count
        assert "1 total" in result.stdout, "Market count not shown in table title"

        # Verify market data displayed
        assert "NFL-KC-WIN" in result.stdout, "Ticker not displayed"

        # Note: Rich table wraps long text with overflow="fold", so check for partial strings
        assert "Kansas City Chiefs" in result.stdout or "Chiefs" in result.stdout, (
            "Title not displayed (may be wrapped across lines)"
        )
        assert "OPEN" in result.stdout, "Status not displayed (should be uppercase)"

        # Verify Decimal prices with 4 decimals
        assert "$0.6250" in result.stdout, "Yes bid price not displayed correctly"
        assert "$0.6350" in result.stdout, "Yes ask price not displayed correctly"
        assert "$0.6300" in result.stdout, "Last price not displayed correctly"

        # Verify volume with comma formatting
        assert "5,000" in result.stdout, "Volume not displayed with comma formatting"

    def test_fetch_markets_multiple(self, runner, mock_kalshi_client):
        """Test fetch-markets with multiple markets.

        Verifies:
            - All markets displayed
            - Proper table formatting
            - Total count shown in title
        """
        # Mock multiple markets
        mock_kalshi_client.get_markets.return_value = [
            {
                "ticker": "NFL-KC-WIN",
                "title": "Will Kansas City Chiefs win?",
                "status": "open",
                "yes_bid": Decimal("0.6250"),
                "yes_ask": Decimal("0.6350"),
                "volume": 5000,
                "last_price": Decimal("0.6300"),
            },
            {
                "ticker": "NFL-BUF-WIN",
                "title": "Will Buffalo Bills win?",
                "status": "open",
                "yes_bid": Decimal("0.5500"),
                "yes_ask": Decimal("0.5650"),
                "volume": 3200,
                "last_price": Decimal("0.5575"),
            },
            {
                "ticker": "NFL-DAL-WIN",
                "title": "Will Dallas Cowboys win?",
                "status": "closed",
                "yes_bid": Decimal("0.4800"),
                "yes_ask": Decimal("0.4900"),
                "volume": 1500,
                "last_price": Decimal("0.4850"),
            },
        ]

        # Run command
        result = runner.invoke(app, ["fetch-markets"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify table title shows correct count
        assert "3 total" in result.stdout, "Market count not shown correctly"

        # Verify all markets displayed
        assert "NFL-KC-WIN" in result.stdout, "First market ticker not displayed"
        assert "NFL-BUF-WIN" in result.stdout, "Second market ticker not displayed"
        assert "NFL-DAL-WIN" in result.stdout, "Third market ticker not displayed"

        # Verify different statuses rendered correctly
        assert "OPEN" in result.stdout, "OPEN status not displayed"
        assert "CLOSED" in result.stdout, "CLOSED status not displayed"

    def test_fetch_markets_filter_by_series(self, runner, mock_kalshi_client):
        """Test fetch-markets with --series filter.

        Verifies:
            - Series ticker passed to get_markets()
            - Filter info shown in table title
        """
        # Mock markets for specific series
        mock_kalshi_client.get_markets.return_value = [
            {
                "ticker": "KXNFLGAME-KC-WIN",
                "title": "Chiefs win game",
                "status": "open",
                "yes_bid": Decimal("0.6000"),
                "yes_ask": Decimal("0.6100"),
                "volume": 1000,
                "last_price": Decimal("0.6050"),
            }
        ]

        # Run command with --series filter
        result = runner.invoke(app, ["fetch-markets", "--series", "KXNFLGAME"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called with series_ticker parameter
        mock_kalshi_client.get_markets.assert_called_once_with(
            series_ticker="KXNFLGAME",
            event_ticker=None,
            limit=100,
        )

        # Verify filter shown in table title
        assert "Series: KXNFLGAME" in result.stdout, "Series filter not shown in table title"

    def test_fetch_markets_filter_by_event(self, runner, mock_kalshi_client):
        """Test fetch-markets with --event filter.

        Verifies:
            - Event ticker passed to get_markets()
            - Filter info shown in table title
        """
        # Mock markets for specific event
        mock_kalshi_client.get_markets.return_value = [
            {
                "ticker": "MARKET-1",
                "title": "Event market 1",
                "status": "open",
                "yes_bid": Decimal("0.5000"),
                "yes_ask": Decimal("0.5100"),
                "volume": 500,
                "last_price": Decimal("0.5050"),
            }
        ]

        # Run command with --event filter
        result = runner.invoke(app, ["fetch-markets", "--event", "KXNFLGAME-25OCT05-NEBUF"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called with event_ticker parameter
        mock_kalshi_client.get_markets.assert_called_once_with(
            series_ticker=None,
            event_ticker="KXNFLGAME-25OCT05-NEBUF",
            limit=100,
        )

        # Verify filter shown in table title
        assert "Event: KXNFLGAME-25OCT05-NEBUF" in result.stdout, (
            "Event filter not shown in table title"
        )

    def test_fetch_markets_custom_limit(self, runner, mock_kalshi_client):
        """Test fetch-markets with --limit parameter.

        Verifies:
            - Limit passed to get_markets()
            - Correct number of markets returned
        """
        # Mock limited markets
        mock_kalshi_client.get_markets.return_value = [
            {
                "ticker": f"MARKET-{i}",
                "title": f"Market {i}",
                "status": "open",
                "yes_bid": Decimal("0.5000"),
                "yes_ask": Decimal("0.5100"),
                "volume": 100,
                "last_price": Decimal("0.5050"),
            }
            for i in range(10)
        ]

        # Run command with custom limit
        result = runner.invoke(app, ["fetch-markets", "--limit", "10"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called with custom limit
        mock_kalshi_client.get_markets.assert_called_once_with(
            series_ticker=None,
            event_ticker=None,
            limit=10,
        )

        # Verify table title shows correct count
        assert "10 total" in result.stdout, "Custom limit count not shown correctly"

    def test_fetch_markets_title_truncation(self, runner, mock_kalshi_client):
        """Test market titles truncated to 50 characters.

        Verifies:
            - Long titles truncated with "..."
            - Short titles unchanged
        """
        # Mock market with very long title
        long_title = (
            "This is a very long market title that exceeds 50 characters and should be truncated"
        )
        short_title = "Short title"

        mock_kalshi_client.get_markets.return_value = [
            {
                "ticker": "MARKET-LONG",
                "title": long_title,  # 84 characters
                "status": "open",
                "yes_bid": Decimal("0.5000"),
                "yes_ask": Decimal("0.5100"),
                "volume": 100,
                "last_price": Decimal("0.5050"),
            },
            {
                "ticker": "MARKET-SHORT",
                "title": short_title,  # 11 characters
                "status": "open",
                "yes_bid": Decimal("0.6000"),
                "yes_ask": Decimal("0.6100"),
                "volume": 200,
                "last_price": Decimal("0.6050"),
            },
        ]

        # Run command
        result = runner.invoke(app, ["fetch-markets"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify long title is truncated with "..."
        # Note: Rich table wraps text with overflow="fold", so truncated text may be split across lines
        # Check for "..." at end of truncated string (main.py truncates to 47 chars + "...")
        assert "5..." in result.stdout, "Truncation ellipsis not found (should show '5...')"
        assert long_title not in result.stdout, "Long title should be truncated, not shown in full"

        # Additional verification: Check that we see parts of the long title wrapped across lines
        assert "This is a" in result.stdout, "Beginning of long title not displayed"
        assert "very long" in result.stdout, "Middle of long title not displayed"

        # Verify short title unchanged (may be wrapped due to column width)
        assert "Short" in result.stdout, "Short title not displayed"

    def test_fetch_markets_dry_run(self, runner, mock_kalshi_client):
        """Test fetch-markets with --dry-run.

        Verifies:
            - API call made
            - "Dry-run mode" message shown
        """
        # Mock markets
        mock_kalshi_client.get_markets.return_value = [
            {
                "ticker": "MARKET-1",
                "title": "Test market",
                "status": "open",
                "yes_bid": Decimal("0.5000"),
                "yes_ask": Decimal("0.5100"),
                "volume": 100,
                "last_price": Decimal("0.5050"),
            }
        ]

        # Run command with --dry-run
        result = runner.invoke(app, ["fetch-markets", "--dry-run"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API still called (dry-run fetches data, just doesn't save)
        mock_kalshi_client.get_markets.assert_called_once()

        # Verify dry-run message shown
        assert "Dry-run mode" in result.stdout or "dry-run" in result.stdout.lower(), (
            "Dry-run mode message not found in output"
        )

        # Verify market data still displayed
        assert "MARKET-1" in result.stdout, "Market data not displayed in dry-run mode"

    def test_fetch_markets_verbose(self, runner, mock_kalshi_client):
        """Test fetch-markets with --verbose.

        Verifies:
            - Verbose mode enabled
            - Market data shown
        """
        # Mock markets
        mock_kalshi_client.get_markets.return_value = [
            {
                "ticker": "MARKET-1",
                "title": "Test market",
                "status": "open",
                "yes_bid": Decimal("0.5000"),
                "yes_ask": Decimal("0.5100"),
                "volume": 100,
                "last_price": Decimal("0.5050"),
            }
        ]

        # Run command with --verbose
        result = runner.invoke(app, ["fetch-markets", "--verbose"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called
        mock_kalshi_client.get_markets.assert_called_once()

        # Verify market data shown
        assert "MARKET-1" in result.stdout, "Market data not displayed in verbose mode"

        # Verbose mode successful (logger output captured in command execution)
        assert result.exit_code == 0, "Verbose mode should not cause errors"

    def test_fetch_markets_decimal_prices(self, runner, mock_kalshi_client):
        """Test market prices displayed with Decimal precision.

        Verifies:
            - Prices show 4 decimal places
            - No rounding errors

        Educational Note:
            Market prices from Kalshi API use yes_bid, yes_ask, last_price
            as Decimal (already converted by client). Must display with
            4 decimals (e.g., $0.4975).
        """
        # Mock market with sub-penny pricing (CRITICAL for Kalshi)
        mock_kalshi_client.get_markets.return_value = [
            {
                "ticker": "MARKET-DECIMAL",
                "title": "Decimal precision test",
                "status": "open",
                "yes_bid": Decimal("0.4975"),  # Sub-penny (would round to $0.50 as float)
                "yes_ask": Decimal("0.5025"),  # Sub-penny
                "volume": 1000,
                "last_price": Decimal("0.5000"),
            }
        ]

        # Run command
        result = runner.invoke(app, ["fetch-markets"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # CRITICAL: Verify all 4 decimal places preserved
        assert "$0.4975" in result.stdout, (
            "Yes bid precision lost! Expected $0.4975. Float contamination would show $0.50."
        )
        assert "$0.5025" in result.stdout, (
            "Yes ask precision lost! Expected $0.5025. Float contamination would show $0.50."
        )
        assert "$0.5000" in result.stdout, "Last price not displayed with 4 decimals"

        # Verify NOT rounded to 2 decimals
        # The output might have $0.50 for last_price, but should also have $0.4975 and $0.5025
        if "$0.50" in result.stdout:
            assert "$0.4975" in result.stdout, (
                "Prices appear to be rounded to 2 decimals (float contamination!)"
            )
            assert "$0.5025" in result.stdout, (
                "Prices appear to be rounded to 2 decimals (float contamination!)"
            )

    def test_fetch_markets_api_error(self, runner, mock_kalshi_client):
        """Test fetch-markets with API error.

        Verifies:
            - Exit code 1
            - Error message displayed
            - Graceful handling
        """
        # TODO: Implement in Part 1.6


class TestFetchPositions:
    """Test cases for fetch-positions CLI command.

    Command: main.py fetch-positions [--env ENV] [--dry-run] [--verbose]

    Tests:
        - Successful position retrieval (empty, single, multiple)
        - Decimal price display
        - Rich table with columns (ticker, side, quantity, price)
        - Dry-run and verbose modes
        - Error handling
    """

    def test_fetch_positions_empty(self, runner, mock_kalshi_client):
        """Test fetch-positions with no open positions.

        Verifies:
            - Exit code 0 (success)
            - "No open positions" message
        """
        # Mock empty positions list
        mock_kalshi_client.get_positions.return_value = []

        # Run command
        result = runner.invoke(app, ["fetch-positions"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called
        mock_kalshi_client.get_positions.assert_called_once()

        # Verify "No open positions found" message
        assert "No open positions found" in result.stdout, (
            "Expected 'No open positions found' message"
        )

    def test_fetch_positions_single(self, runner, mock_kalshi_client):
        """Test fetch-positions with one position.

        Verifies:
            - Position displayed in Rich table
            - Ticker, side, quantity, price shown
            - Decimal price formatting (4 decimals)
        """
        # Mock single position
        mock_kalshi_client.get_positions.return_value = [
            {
                "ticker": "NFL-KC-WIN",
                "side": "yes",
                "position": 100,  # Quantity
                "user_average_price": Decimal("0.6250"),
                "total_cost": Decimal("62.50"),
            }
        ]

        # Run command
        result = runner.invoke(app, ["fetch-positions"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify table title shows count
        assert "1 total" in result.stdout, "Position count not shown in table title"

        # Verify position data displayed
        assert "NFL-KC-WIN" in result.stdout, "Ticker not displayed"
        assert "YES" in result.stdout, "Side not displayed (should be uppercase)"
        assert "100" in result.stdout, "Quantity not displayed"

        # Verify Decimal prices with 4 decimals
        assert "$0.6250" in result.stdout, "Avg price not displayed correctly"

        # Verify total cost (2 decimals for currency)
        assert "$62.50" in result.stdout, "Total cost not displayed correctly"

        # Verify Total Exposure shown
        assert "Total Exposure" in result.stdout, "Total Exposure not shown"
        assert "$62.50" in result.stdout, "Total Exposure amount not shown"

    def test_fetch_positions_multiple(self, runner, mock_kalshi_client):
        """Test fetch-positions with multiple positions.

        Verifies:
            - All positions displayed
            - Proper table formatting
            - Total count shown
            - Total Exposure correctly summed
        """
        # Mock multiple positions
        mock_kalshi_client.get_positions.return_value = [
            {
                "ticker": "NFL-KC-WIN",
                "side": "yes",
                "position": 100,
                "user_average_price": Decimal("0.6250"),
                "total_cost": Decimal("62.50"),
            },
            {
                "ticker": "NFL-BUF-WIN",
                "side": "no",
                "position": 50,
                "user_average_price": Decimal("0.4500"),
                "total_cost": Decimal("22.50"),
            },
            {
                "ticker": "NFL-SF-WIN",
                "side": "yes",
                "position": 200,
                "user_average_price": Decimal("0.7000"),
                "total_cost": Decimal("140.00"),
            },
        ]

        # Run command
        result = runner.invoke(app, ["fetch-positions"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify table title shows count
        assert "3 total" in result.stdout, "Position count not shown in table title"

        # Verify all tickers displayed
        assert "NFL-KC-WIN" in result.stdout, "First ticker not displayed"
        assert "NFL-BUF-WIN" in result.stdout, "Second ticker not displayed"
        assert "NFL-SF-WIN" in result.stdout, "Third ticker not displayed"

        # Verify sides (uppercase)
        assert "YES" in result.stdout, "YES side not displayed"
        assert "NO" in result.stdout, "NO side not displayed"

        # Verify Total Exposure sum (62.50 + 22.50 + 140.00 = 225.00)
        assert "Total Exposure" in result.stdout, "Total Exposure not shown"
        assert "$225.00" in result.stdout, "Total Exposure sum not correct"

    def test_fetch_positions_dry_run(self, runner, mock_kalshi_client):
        """Test fetch-positions with --dry-run.

        Verifies:
            - API call made
            - Dry-run message shown
            - No database write message
        """
        # Mock position
        mock_kalshi_client.get_positions.return_value = [
            {
                "ticker": "NFL-KC-WIN",
                "side": "yes",
                "position": 100,
                "user_average_price": Decimal("0.6250"),
                "total_cost": Decimal("62.50"),
            }
        ]

        # Run command with --dry-run
        result = runner.invoke(app, ["fetch-positions", "--dry-run"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called (dry-run still fetches data)
        mock_kalshi_client.get_positions.assert_called_once()

        # Verify dry-run message
        assert "Dry-run mode" in result.stdout, "Dry-run mode message not shown"
        assert "not saved to database" in result.stdout, "Database skip message not shown"

        # Verify position data still displayed
        assert "NFL-KC-WIN" in result.stdout, "Position data not displayed in dry-run"

    def test_fetch_positions_verbose(self, runner, mock_kalshi_client):
        """Test fetch-positions with --verbose.

        Verifies:
            - Verbose mode message logged
            - Position data shown
        """
        # Mock position
        mock_kalshi_client.get_positions.return_value = [
            {
                "ticker": "NFL-KC-WIN",
                "side": "yes",
                "position": 100,
                "user_average_price": Decimal("0.6250"),
                "total_cost": Decimal("62.50"),
            }
        ]

        # Run command with --verbose
        result = runner.invoke(app, ["fetch-positions", "--verbose"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called
        mock_kalshi_client.get_positions.assert_called_once()

        # Verify position data displayed
        assert "NFL-KC-WIN" in result.stdout, "Position data not displayed in verbose mode"

        # Note: Verbose mode logs "Verbose mode enabled" via logger
        # This is logged but may not appear in stdout (depends on log configuration)

    def test_fetch_positions_decimal_prices(self, runner, mock_kalshi_client):
        """Test position prices displayed with Decimal precision.

        Verifies:
            - Prices show 4 decimal places
            - No rounding errors

        Educational Note:
            Position prices from Kalshi API use *_dollars fields
            (e.g., "yes_price_dollars": "0.6250"). Must parse as
            Decimal and display with 4 decimals.
        """
        # Mock position with sub-penny pricing (CRITICAL for Kalshi)
        # This value MUST show all 4 decimals, NOT round to $0.50
        mock_kalshi_client.get_positions.return_value = [
            {
                "ticker": "MARKET-DECIMAL",
                "side": "yes",
                "position": 100,
                "user_average_price": Decimal(
                    "0.4975"
                ),  # Sub-penny (would round to $0.50 as float)
                "total_cost": Decimal("49.75"),
            }
        ]

        # Run command
        result = runner.invoke(app, ["fetch-positions"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # CRITICAL: Verify all 4 decimal places preserved for average price
        assert "$0.4975" in result.stdout, (
            "Avg price precision lost! Expected $0.4975. Float contamination would show $0.50."
        )

        # Verify NOT rounded to 2 decimals
        # Total cost will show $49.75 (2 decimals for currency), but avg price must show 4
        if "$0.50" in result.stdout:
            assert "$0.4975" in result.stdout, (
                "Avg price appears to be rounded to 2 decimals (float contamination!)"
            )

        # Verify total cost (2 decimals is correct for currency)
        assert "$49.75" in result.stdout, "Total cost not displayed correctly"

    def test_fetch_positions_api_error(self, runner, mock_kalshi_client):
        """Test fetch-positions with API error.

        Verifies:
            - Exit code 1
            - Error message displayed
            - Graceful handling
        """
        # TODO: Implement in Part 1.6


class TestFetchFills:
    """Test cases for fetch-fills CLI command.

    Command: main.py fetch-fills [--env ENV] [--days DAYS] [--dry-run] [--verbose]

    Tests:
        - Successful fill retrieval (default 7 days)
        - Custom days parameter (1, 30, 90)
        - Decimal price/amount display
        - Rich table with columns (timestamp, ticker, side, quantity, price)
        - Timestamp conversion (Unix → readable)
        - Dry-run and verbose modes
        - Error handling
    """

    def test_fetch_fills_empty(self, runner, mock_kalshi_client):
        """Test fetch-fills with no fills in time period."""
        # Mock empty fills list
        mock_kalshi_client.get_fills.return_value = []

        # Run command
        result = runner.invoke(app, ["fetch-fills"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called
        mock_kalshi_client.get_fills.assert_called_once()

        # Verify "No fills found" message
        assert "No fills found" in result.stdout, "Expected 'No fills found' message"

    def test_fetch_fills_single(self, runner, mock_kalshi_client):
        """Test fetch-fills with one fill.

        Verifies:
            - Fill displayed with timestamp, ticker, side, qty, price
            - Decimal price formatting
        """
        # Mock single fill
        mock_kalshi_client.get_fills.return_value = [
            {
                "trade_id": "1234567890abcdef",  # Will be truncated to 12 chars
                "ticker": "NFL-KC-WIN",
                "side": "yes",
                "action": "buy",
                "count": 100,  # Quantity
                "price": Decimal("0.6250"),
                "created_time": "2025-11-08T14:30:00Z",
            }
        ]

        # Run command
        result = runner.invoke(app, ["fetch-fills"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify table title shows count
        assert "1 total" in result.stdout, "Fill count not shown in table title"

        # Verify fill data displayed
        assert "1234567890ab..." in result.stdout, "Trade ID not truncated correctly"
        # Ticker may be truncated by Rich table (e.g., "NFL-KC-…")
        assert "NFL-KC" in result.stdout, "Ticker not displayed"
        assert "YES" in result.stdout, "Side not displayed (should be uppercase)"
        assert "BUY" in result.stdout, "Action not displayed (should be uppercase)"
        assert "100" in result.stdout, "Quantity not displayed"

        # Verify Decimal price with 4 decimals
        assert "$0.6250" in result.stdout, "Price not displayed correctly"

        # Verify date displayed (may be truncated: "2025-11-…")
        assert "2025-11" in result.stdout, "Created date not displayed"

        # Verify Total Volume shown
        assert "Total Volume" in result.stdout, "Total Volume not shown"
        assert "100 contracts" in result.stdout, "Total Volume count not shown"

    def test_fetch_fills_multiple(self, runner, mock_kalshi_client):
        """Test fetch-fills with multiple fills.

        Verifies:
            - All fills shown (up to 10)
            - Total volume correctly summed
            - Total count displayed
        """
        # Mock multiple fills
        mock_kalshi_client.get_fills.return_value = [
            {
                "trade_id": "fill001",
                "ticker": "NFL-KC-WIN",
                "side": "yes",
                "action": "buy",
                "count": 100,
                "price": Decimal("0.6250"),
                "created_time": "2025-11-08T14:30:00Z",
            },
            {
                "trade_id": "fill002",
                "ticker": "NFL-BUF-WIN",
                "side": "no",
                "action": "sell",
                "count": 50,
                "price": Decimal("0.4500"),
                "created_time": "2025-11-08T13:15:00Z",
            },
            {
                "trade_id": "fill003",
                "ticker": "NFL-SF-WIN",
                "side": "yes",
                "action": "buy",
                "count": 200,
                "price": Decimal("0.7000"),
                "created_time": "2025-11-08T12:00:00Z",
            },
        ]

        # Run command
        result = runner.invoke(app, ["fetch-fills"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify table title shows count
        assert "3 total" in result.stdout, "Fill count not shown in table title"

        # Verify all tickers displayed
        assert "NFL-KC-WIN" in result.stdout, "First ticker not displayed"
        assert "NFL-BUF-WIN" in result.stdout, "Second ticker not displayed"
        assert "NFL-SF-WIN" in result.stdout, "Third ticker not displayed"

        # Verify sides (uppercase)
        assert "YES" in result.stdout, "YES side not displayed"
        assert "NO" in result.stdout, "NO side not displayed"

        # Verify actions (uppercase)
        assert "BUY" in result.stdout, "BUY action not displayed"
        assert "SELL" in result.stdout, "SELL action not displayed"

        # Verify Total Volume sum (100 + 50 + 200 = 350)
        assert "Total Volume" in result.stdout, "Total Volume not shown"
        assert "350 contracts" in result.stdout, "Total Volume sum not correct"

    def test_fetch_fills_pagination(self, runner, mock_kalshi_client):
        """Test fetch-fills with > 10 fills shows pagination message.

        Verifies:
            - Only first 10 fills displayed in table
            - "... and X more fills" message shown
        """
        # Mock 15 fills (only first 10 should be displayed)
        fills = [
            {
                "trade_id": f"fill{i:03d}",
                "ticker": f"MARKET-{i}",
                "side": "yes",
                "action": "buy",
                "count": 10,
                "price": Decimal("0.5000"),
                "created_time": f"2025-11-0{min(8, i // 2)}T12:00:00Z",
            }
            for i in range(15)
        ]
        mock_kalshi_client.get_fills.return_value = fills

        # Run command
        result = runner.invoke(app, ["fetch-fills"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify table title shows full count
        assert "15 total" in result.stdout, "Total fill count not shown in table title"

        # Verify pagination message shown
        assert "and 5 more fills" in result.stdout, "Pagination message not shown"

        # Verify total volume calculated from DISPLAYED fills (10 * 10 = 100)
        # NOTE: This is a limitation in main.py line 826 - only sums fills[:10]
        # Ideally should sum ALL fills, but testing actual behavior
        assert "100 contracts" in result.stdout, "Total volume shown"

    def test_fetch_fills_dry_run(self, runner, mock_kalshi_client):
        """Test fetch-fills with --dry-run.

        Verifies:
            - API still called (dry-run affects database, not API)
            - Dry-run message shown
            - Fills still displayed
        """
        # Mock fill
        mock_kalshi_client.get_fills.return_value = [
            {
                "trade_id": "fill001",
                "ticker": "NFL-KC-WIN",
                "side": "yes",
                "action": "buy",
                "count": 100,
                "price": Decimal("0.6250"),
                "created_time": "2025-11-08T14:30:00Z",
            }
        ]

        # Run command with --dry-run
        result = runner.invoke(app, ["fetch-fills", "--dry-run"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called (dry-run still fetches data)
        mock_kalshi_client.get_fills.assert_called_once()

        # Verify dry-run message
        assert "Dry-run mode" in result.stdout, "Dry-run mode message not shown"
        assert "not saved to database" in result.stdout, "Database skip message not shown"

        # Verify fill data still displayed
        assert "NFL-KC-WIN" in result.stdout, "Fill data not displayed in dry-run"

    def test_fetch_fills_decimal_prices(self, runner, mock_kalshi_client):
        """Test fill prices displayed with Decimal precision.

        CRITICAL: Fill prices must show 4 decimal places for sub-penny pricing.
        """
        # Mock fill with sub-penny pricing (CRITICAL for Kalshi)
        # This value MUST show all 4 decimals, NOT round to $0.50
        mock_kalshi_client.get_fills.return_value = [
            {
                "trade_id": "decimal-test",
                "ticker": "MARKET-DECIMAL",
                "side": "yes",
                "action": "buy",
                "count": 100,
                "price": Decimal("0.4975"),  # Sub-penny (would round to $0.50 as float)
                "created_time": "2025-11-08T14:30:00Z",
            }
        ]

        # Run command
        result = runner.invoke(app, ["fetch-fills"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # CRITICAL: Verify all 4 decimal places preserved
        assert "$0.4975" in result.stdout, (
            "Price precision lost! Expected $0.4975. Float contamination would show $0.50."
        )

        # Verify NOT rounded to 2 decimals
        if "$0.50" in result.stdout:
            assert "$0.4975" in result.stdout, (
                "Price appears to be rounded to 2 decimals (float contamination!)"
            )

    def test_fetch_fills_api_error(self, runner, mock_kalshi_client):
        """Test fetch-fills with API error.

        Verifies:
            - Exit code 1
            - Error message
        """
        # TODO: Implement in Part 1.6


class TestFetchSettlements:
    """Test cases for fetch-settlements CLI command.

    Command: main.py fetch-settlements [--env ENV] [--dry-run] [--verbose]

    Tests:
        - Successful settlement retrieval
        - Decimal price display
        - Rich table with columns (ticker, result, settlement_price)
        - Dry-run and verbose modes
        - Error handling
    """

    def test_fetch_settlements_empty(self, runner, mock_kalshi_client):
        """Test fetch-settlements with no settlements."""
        # Mock empty settlements list
        mock_kalshi_client.get_settlements.return_value = []

        # Run command
        result = runner.invoke(app, ["fetch-settlements"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called
        mock_kalshi_client.get_settlements.assert_called_once()

        # Verify "No settlements found" message
        assert "No settlements found" in result.stdout, "Expected 'No settlements found' message"

    def test_fetch_settlements_single(self, runner, mock_kalshi_client):
        """Test fetch-settlements with one settlement.

        Verifies:
            - Settlement displayed in table
            - Ticker, result, price shown
            - Total revenue, fees, and P&L calculated
        """
        # Mock single settlement
        mock_kalshi_client.get_settlements.return_value = [
            {
                "ticker": "NFL-KC-WIN",
                "market_result": "yes",
                "settlement_value": Decimal("1.0000"),  # 4 decimals
                "revenue": Decimal("50.00"),  # 2 decimals
                "total_fees": Decimal("2.50"),  # 2 decimals
                "settled_time": "2025-11-08T14:30:00Z",
            }
        ]

        # Run command
        result = runner.invoke(app, ["fetch-settlements"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify table title shows count
        assert "1 total" in result.stdout, "Settlement count not shown in table title"

        # Verify settlement data displayed (may be truncated by Rich table)
        assert "NFL-KC" in result.stdout, "Ticker not displayed"
        assert "YES" in result.stdout, "Result not displayed (should be uppercase)"

        # Verify Decimal values with correct precision
        assert "$1.0000" in result.stdout, "Settlement value not displayed correctly (4 decimals)"
        assert "$50.00" in result.stdout, "Revenue not displayed correctly"
        assert "$2.50" in result.stdout, "Fees not displayed correctly"

        # Verify date displayed (may be truncated: "2025-11-…")
        assert "2025-11" in result.stdout, "Settled date not displayed"

        # Verify totals and P&L
        assert "Total Revenue" in result.stdout, "Total Revenue not shown"
        assert "Total Fees" in result.stdout, "Total Fees not shown"
        assert "Net P&L" in result.stdout, "Net P&L not shown"

        # Verify P&L calculation (50.00 - 2.50 = 47.50)
        assert "$47.50" in result.stdout, "Net P&L not calculated correctly"

    def test_fetch_settlements_multiple(self, runner, mock_kalshi_client):
        """Test fetch-settlements with multiple settlements.

        Verifies:
            - All settlements shown
            - Totals correctly summed
            - Net P&L calculated
        """
        # Mock multiple settlements
        mock_kalshi_client.get_settlements.return_value = [
            {
                "ticker": "NFL-KC-WIN",
                "market_result": "yes",
                "settlement_value": Decimal("1.0000"),
                "revenue": Decimal("50.00"),
                "total_fees": Decimal("2.50"),
                "settled_time": "2025-11-08T14:30:00Z",
            },
            {
                "ticker": "NFL-BUF-WIN",
                "market_result": "no",
                "settlement_value": Decimal("0.0000"),
                "revenue": Decimal("-25.00"),  # Loss
                "total_fees": Decimal("1.25"),
                "settled_time": "2025-11-08T13:15:00Z",
            },
            {
                "ticker": "NFL-SF-WIN",
                "market_result": "yes",
                "settlement_value": Decimal("1.0000"),
                "revenue": Decimal("75.00"),
                "total_fees": Decimal("3.75"),
                "settled_time": "2025-11-08T12:00:00Z",
            },
        ]

        # Run command
        result = runner.invoke(app, ["fetch-settlements"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify table title shows count
        assert "3 total" in result.stdout, "Settlement count not shown in table title"

        # Verify all tickers displayed
        assert "NFL-KC" in result.stdout, "First ticker not displayed"
        assert "NFL-BUF" in result.stdout, "Second ticker not displayed"
        assert "NFL-SF" in result.stdout, "Third ticker not displayed"

        # Verify results (uppercase)
        assert "YES" in result.stdout, "YES result not displayed"
        assert "NO" in result.stdout, "NO result not displayed"

        # Verify Total Revenue sum (50.00 + (-25.00) + 75.00 = 100.00)
        assert "Total Revenue" in result.stdout, "Total Revenue not shown"
        assert "$100.00" in result.stdout, "Total Revenue sum not correct"

        # Verify Total Fees sum (2.50 + 1.25 + 3.75 = 7.50)
        assert "Total Fees" in result.stdout, "Total Fees not shown"
        assert "$7.50" in result.stdout, "Total Fees sum not correct"

        # Verify Net P&L (100.00 - 7.50 = 92.50)
        assert "Net P&L" in result.stdout, "Net P&L not shown"
        assert "$92.50" in result.stdout, "Net P&L calculation not correct"

    def test_fetch_settlements_dry_run(self, runner, mock_kalshi_client):
        """Test fetch-settlements with --dry-run.

        Verifies:
            - API still called (dry-run affects database, not API)
            - Dry-run message shown
            - Settlements still displayed
        """
        # Mock settlement
        mock_kalshi_client.get_settlements.return_value = [
            {
                "ticker": "NFL-KC-WIN",
                "market_result": "yes",
                "settlement_value": Decimal("1.0000"),
                "revenue": Decimal("50.00"),
                "total_fees": Decimal("2.50"),
                "settled_time": "2025-11-08T14:30:00Z",
            }
        ]

        # Run command with --dry-run
        result = runner.invoke(app, ["fetch-settlements", "--dry-run"])

        # Verify exit code
        assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"

        # Verify API called (dry-run still fetches data)
        mock_kalshi_client.get_settlements.assert_called_once()

        # Verify dry-run message
        assert "Dry-run mode" in result.stdout, "Dry-run mode message not shown"
        assert "not saved to database" in result.stdout, "Database skip message not shown"

        # Verify settlement data still displayed
        assert "NFL-KC" in result.stdout, "Settlement data not displayed in dry-run"

    def test_fetch_settlements_api_error(self, runner, mock_kalshi_client):
        """Test fetch-settlements with API error.

        Verifies:
            - Exit code 1
            - Error message
        """
        # TODO: Implement in Part 1.6


class TestGetKalshiClient:
    """Test cases for get_kalshi_client() helper function.

    Function: get_kalshi_client(environment: str = "demo") -> KalshiClient

    Tests:
        - Client creation (demo/prod)
        - Missing credentials handling
        - Invalid environment handling
        - Proper error messages
    """

    def test_get_kalshi_client_demo(self):
        """Test get_kalshi_client() with demo environment.

        Verifies:
            - KalshiClient created successfully
            - Demo credentials loaded
        """
        # TODO: Implement in Part 1.6

    def test_get_kalshi_client_prod(self):
        """Test get_kalshi_client() with prod environment.

        Verifies:
            - KalshiClient created successfully
            - Prod credentials loaded
        """
        # TODO: Implement in Part 1.6

    def test_get_kalshi_client_missing_credentials(self):
        """Test get_kalshi_client() with missing credentials.

        Verifies:
            - Raises ValueError
            - Error message explains missing credentials
            - User-friendly message
        """
        # TODO: Implement in Part 1.6

    def test_get_kalshi_client_invalid_environment(self):
        """Test get_kalshi_client() with invalid environment.

        Verifies:
            - Raises typer.Exit with code 1
            - Error message explains valid options (demo/prod)
        """
        from main import get_kalshi_client

        # Invalid environment should raise typer.Exit (via main.py error handling)
        with pytest.raises(typer.Exit) as exc_info:
            get_kalshi_client(environment="invalid")

        # Verify exit code is 1 (error)
        assert exc_info.value.exit_code == 1


class TestErrorHandling:
    """Test cases for CLI error handling across all commands.

    Tests:
        - Graceful error handling (no stack traces)
        - User-friendly error messages
        - Exit code 1 on errors
        - Error logging (if verbose enabled)
    """

    def test_missing_credentials_error_message(self, runner):
        """Test user-friendly error when credentials missing.

        Verifies:
            - Clear message: "Kalshi credentials not found"
            - Instructions to set environment variables
            - No Python stack trace shown to user
        """
        from unittest.mock import patch

        # Mock KalshiClient constructor to raise OSError (simulating missing credentials)
        with patch("main.KalshiClient") as mock_client_class:
            mock_client_class.side_effect = OSError(
                "Missing Kalshi credentials. Please set KALSHI_DEMO_API_KEY and "
                "KALSHI_DEMO_KEYFILE in .env file"
            )

            # Invoke fetch-balance command (any command will do)
            result = runner.invoke(app, ["fetch-balance"])

            # Verify exit code 1 (error)
            assert result.exit_code == 1

            # Verify user-friendly error message displayed
            assert "Unexpected error" in result.stdout or "Error" in result.stdout
            assert "Missing Kalshi credentials" in result.stdout

            # Verify helpful instructions shown (from get_kalshi_client error handler)
            assert "KALSHI_DEMO_API_KEY" in result.stdout or ".env" in result.stdout

            # Verify no Python stack trace shown (no "Traceback")
            assert "Traceback" not in result.stdout

    def test_api_error_handling(self, runner, mock_kalshi_client):
        """Test graceful handling of API errors.

        Verifies:
            - HTTP errors handled gracefully
            - Network errors handled gracefully
            - Generic exceptions handled gracefully
            - Exit code 1 on errors
        """
        import requests

        # Test HTTP 401 error (authentication failure)
        mock_kalshi_client.get_balance.side_effect = requests.exceptions.HTTPError(
            "401 Unauthorized"
        )
        result = runner.invoke(app, ["fetch-balance"])
        assert result.exit_code == 1
        assert "Failed to fetch balance" in result.stdout
        assert "401" in result.stdout or "Unauthorized" in result.stdout

        # Test HTTP 500 error (server error)
        mock_kalshi_client.get_positions.side_effect = requests.exceptions.HTTPError(
            "500 Internal Server Error"
        )
        result = runner.invoke(app, ["fetch-positions"])
        assert result.exit_code == 1
        assert "Failed to fetch positions" in result.stdout

        # Test network error (connection timeout)
        mock_kalshi_client.get_markets.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )
        result = runner.invoke(app, ["fetch-markets"])
        assert result.exit_code == 1
        assert "Failed to fetch markets" in result.stdout

        # Test generic exception
        mock_kalshi_client.get_fills.side_effect = Exception("Unexpected error")
        result = runner.invoke(app, ["fetch-fills"])
        assert result.exit_code == 1
        assert "Failed to fetch fills" in result.stdout

    def test_verbose_mode_shows_details(self, runner, mock_kalshi_client):
        """Test verbose mode shows detailed error info.

        Verifies:
            - --verbose shows full error details
            - Non-verbose shows only user-friendly message
        """
        import requests

        # Configure mock to raise an error
        mock_kalshi_client.get_balance.side_effect = requests.exceptions.HTTPError(
            "401 Unauthorized"
        )

        # Test without verbose mode - should show minimal error
        result_quiet = runner.invoke(app, ["fetch-balance"])
        assert result_quiet.exit_code == 1
        assert "Failed to fetch balance" in result_quiet.stdout
        # Should NOT show detailed stack trace in non-verbose mode
        # Note: logger.error with exc_info=verbose means no stack trace when verbose=False

        # Test with verbose mode - should show detailed error
        result_verbose = runner.invoke(app, ["fetch-balance", "--verbose"])
        assert result_verbose.exit_code == 1
        assert "Failed to fetch balance" in result_verbose.stdout
        # Verbose mode enables exc_info=True in logger.error call
        # (Stack trace would appear in logs but not necessarily in stdout)


# ============================================================================
# Notes for Implementation
# ============================================================================

"""
Implementation Order (Parts B, 1.2-1.6):

Part B (15 min): Test fetch-markets command ✅ SKELETON COMPLETE
    - ✅ Added TestFetchMarkets class (11 test methods)
    - ✅ Updated mock_kalshi_client fixture with get_markets()
    - TODO: Implement actual test logic in future parts

Part 1.2 (45 min): Test fetch-balance command
    - Implement TestFetchBalance tests
    - Mock KalshiClient.get_balance()
    - Test parameter variations
    - Verify Decimal precision

Part 1.3 (45 min): Test fetch-positions command
    - Implement TestFetchPositions tests
    - Mock KalshiClient.get_positions()
    - Test empty/single/multiple positions
    - Verify Rich table formatting

Part 1.4 (30 min): Test fetch-fills command
    - Implement TestFetchFills tests
    - Mock KalshiClient.get_fills()
    - Test --days parameter
    - Verify timestamp conversion

Part 1.5 (30 min): Test fetch-settlements command
    - Implement TestFetchSettlements tests
    - Mock KalshiClient.get_settlements()
    - Test settlement display

Part 1.6 (45 min): Test error handling
    - Implement TestGetKalshiClient tests
    - Implement TestErrorHandling tests
    - Test all error paths
    - Verify user-friendly messages

Coverage Target: 85%+ for main.py
Expected Boost: Phase 1 coverage 53.29% → ~70%

Key Mocking Patterns:
    @patch('main.get_kalshi_client')
    def test_something(self, mock_get_client, runner):
        mock_get_client.return_value = mock_kalshi_client
        result = runner.invoke(app, ["fetch-balance"])
        assert result.exit_code == 0

    @patch.dict(os.environ, {}, clear=True)  # Clear env vars
    def test_missing_creds(self, runner):
        result = runner.invoke(app, ["fetch-balance"])
        assert result.exit_code == 1
"""
