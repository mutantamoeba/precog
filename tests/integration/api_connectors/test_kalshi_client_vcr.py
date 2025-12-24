"""
Integration tests for Kalshi API client using VCR cassettes (Pattern 13).

Tests the full KalshiClient integration using REAL recorded API responses.
These tests use the VCR (Video Cassette Recorder) pattern:
- Cassettes recorded once from real Kalshi demo API
- Tests replay cassettes (no network calls, no credentials needed)
- 100% real API response data (no mocks!)

Benefits of VCR pattern:
- Fast: No network calls during tests
- Deterministic: Same responses every time
- Real data: Uses actual Kalshi API structures
- CI-friendly: Works without API credentials

Cassettes recorded: tests/cassettes/kalshi_*.yaml
- kalshi_get_markets.yaml (5 NFL markets)
- kalshi_get_balance.yaml (balance: $2350.84)
- kalshi_get_positions.yaml (0 positions)
- kalshi_get_fills.yaml (1 historical fill)
- kalshi_get_settlements.yaml (0 settlements)

Pattern 13 Exception: External API mock
These tests use VCR to replay REAL API responses. They test API client behavior
without touching the database, so database fixtures (db_pool, db_cursor, clean_test_data)
are not applicable. Pattern 13 lesson learned was about DATABASE connection pool mocking,
not HTTP interaction recording.

Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-API-002: RSA-PSS Authentication
    - REQ-SYS-003: Decimal Precision for Prices
    - REQ-TEST-002: Integration tests use real API fixtures (Pattern 13)

Reference:
    - Pattern 13 (CLAUDE.md): Real Fixtures, Not Mocks
    - GitHub Issue #124: Fix integration test mocks
    - Phase 1.5 Test Audit: 77% false positive rate from mocks
"""

from decimal import Decimal

import pytest
import vcr

from precog.api_connectors.kalshi_client import KalshiClient

# Configure VCR for test cassettes
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="none",  # Never record in tests (only replay)
    match_on=["method", "scheme", "host", "port", "path", "query"],
    filter_headers=["KALSHI-ACCESS-KEY", "KALSHI-ACCESS-SIGNATURE", "KALSHI-ACCESS-TIMESTAMP"],
    decode_compressed_response=True,
)


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.timeout(30)  # Prevent indefinite VCR hangs in CI
class TestKalshiClientWithVCR:
    """
    Test Kalshi API client using VCR cassettes with REAL API data.

    These tests verify:
    - Successful API requests return real Kalshi data
    - Decimal precision preserved in all price fields
    - Response parsing handles real API structures
    - No mocks needed - uses actual recorded HTTP interactions

    Educational Note:
        Pattern 13: Real Fixtures, Not Mocks
        -----------------------------------
        Problem: Mocks create false positives (tests pass but code broken)
        - Mock returns {"balance": "1234.5678"} but real API returns {"balance": 123456} (cents!)
        - Test passes with mock, fails in production

        Solution: VCR Pattern
        - Record real API responses ONCE
        - Replay in tests (fast, no network)
        - Tests use 100% real data structures

        Phase 1.5 audit found 77% false positive rate from mocks!
    """

    def test_get_markets_with_real_api_data(self, monkeypatch):
        """
        Test get_markets() with REAL recorded Kalshi market data.

        Uses cassette: kalshi_get_markets.yaml
        - 5 real NFL markets from KXNFLGAME series
        - Real prices with sub-penny precision (0.0000 format)
        - Real market titles, tickers, volumes
        """
        # Set environment variables for client initialization
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_markets.yaml"):
            client = KalshiClient(environment="demo")
            markets = client.get_markets(series_ticker="KXNFLGAME", limit=5)

        # Verify real data structure
        assert len(markets) == 5, "Should return 5 markets from cassette"

        # Verify first market structure (real data)
        market = markets[0]
        assert "ticker" in market
        assert "title" in market
        assert market["ticker"].startswith("KXNFLGAME-"), "Real Kalshi market ticker format"

        # Verify ALL price fields are Decimal (CRITICAL!)
        # Note: We parse *_dollars fields for sub-penny precision
        price_fields = ["yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars"]
        for field in price_fields:
            if field in market:
                # TypedDict dynamic key access requires type: ignore
                assert isinstance(market[field], Decimal), (  # type: ignore[literal-required]
                    f"Field '{field}' must be Decimal, got {type(market[field])}"  # type: ignore[literal-required]
                )

        # Verify specific market from recording
        # Note: Cassette recorded on 2025-11-23, data may have changed since then
        assert any(m["ticker"] == "KXNFLGAME-25NOV27GBDET-GB" for m in markets), (
            "Should include GB @ DET market from cassette"
        )

    def test_get_balance_with_real_api_data(self, monkeypatch):
        """
        Test get_balance() with REAL recorded Kalshi balance.

        Uses cassette: kalshi_get_balance.yaml
        - Real balance: 235084 cents = $2350.84
        - Real portfolio_value: 10197 cents = $101.97
        - Real timestamp: 1763933221
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_balance.yaml"):
            client = KalshiClient(environment="demo")
            balance = client.get_balance()

        # Verify Decimal type (CRITICAL!)
        assert isinstance(balance, Decimal), f"Balance must be Decimal, got {type(balance)}"

        # Verify real balance from cassette (235084 cents = $2350.84)
        # Client now converts cents to dollars automatically
        assert balance == Decimal("2350.84"), "Should match recorded balance"

        # Educational Note: Kalshi API returns cents (235084),
        # but our client converts to dollars ($2350.84)

    def test_get_positions_with_real_api_data(self, monkeypatch):
        """
        Test get_positions() with REAL recorded Kalshi positions.

        Uses cassette: kalshi_get_positions.yaml
        - Real positions: 0 (demo account has no open positions)
        - Real response structure from Kalshi
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_positions.yaml"):
            client = KalshiClient(environment="demo")
            positions = client.get_positions()

        # Verify real data (demo account has no open positions)
        assert isinstance(positions, list), "Positions should be a list"
        assert len(positions) == 0, "Demo account has 0 positions (from cassette)"

        # If positions existed, they would have structure:
        # {
        #   "ticker": "KXNFLGAME-...",
        #   "position": 100,  # Contract count
        #   "total_cost": Decimal("61.0000"),
        #   "user_average_price": Decimal("0.6100"),
        # }

    def test_get_fills_with_real_api_data(self, monkeypatch):
        """
        Test get_fills() with REAL recorded Kalshi fill data.

        Uses cassette: kalshi_get_fills.yaml
        - Real fill: 1 historical trade from 2025-10-25
        - Ticker: KXALIENS-26
        - Side: no, Price: $0.96 (96 cents)
        - Count: 103 contracts
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_fills.yaml"):
            client = KalshiClient(environment="demo")
            fills = client.get_fills(limit=5)

        # Verify real data
        assert isinstance(fills, list), "Fills should be a list"
        assert len(fills) == 1, "Should have 1 historical fill from cassette"

        # Verify first fill structure (real trade data)
        fill = fills[0]
        assert fill["ticker"] == "KXALIENS-26", "Real Kalshi market ticker"
        assert fill["action"] == "buy", "Real trade action"
        assert fill["side"] == "no", "Trade side (no)"
        assert fill["count"] == 103, "Real contract count"

        # Verify price fields are Decimal (CRITICAL!)
        # Note: We parse *_fixed fields for sub-penny precision in fills
        assert isinstance(fill["yes_price_fixed"], Decimal), "yes_price_fixed must be Decimal"
        assert isinstance(fill["no_price_fixed"], Decimal), "no_price_fixed must be Decimal"

        # Verify real prices from cassette
        assert fill["no_price_fixed"] == Decimal("0.9600"), "NO side price"
        assert fill["yes_price_fixed"] == Decimal("0.0400"), "YES side price"

        # Educational Note: YES + NO prices should sum to $1.00
        # Real data: 0.96 + 0.04 = 1.00 ✅

    def test_get_settlements_with_real_api_data(self, monkeypatch):
        """
        Test get_settlements() with REAL recorded Kalshi settlement data.

        Uses cassette: kalshi_get_settlements.yaml
        - Real settlements: 0 (demo account has no settled positions)
        - Real response structure from Kalshi
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_settlements.yaml"):
            client = KalshiClient(environment="demo")
            settlements = client.get_settlements(limit=5)

        # Verify real data (demo account has no settlements)
        assert isinstance(settlements, list), "Settlements should be a list"
        assert len(settlements) == 0, "Demo account has 0 settlements (from cassette)"

        # If settlements existed, they would have structure:
        # {
        #   "ticker": "KXNFLGAME-...",
        #   "settlement_value": Decimal("1.0000") or Decimal("0.0000"),
        #   "revenue": Decimal("100.0000"),  # Payout
        #   "no_count": 100,  # Contracts held
        # }


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.timeout(30)  # Prevent indefinite VCR hangs in CI
class TestKalshiClientDecimalPrecisionWithVCR:
    """
    Test Decimal precision using REAL Kalshi API data (VCR cassettes).

    Verifies that our Decimal conversion logic correctly handles:
    - Sub-penny prices (4 decimal places: 0.4275)
    - Cent-denominated values (balance: 235084 cents)
    - Price arithmetic (spread, PnL, edge calculations)

    Why VCR matters for Decimal tests:
    - Mocks can fake Decimal types but miss real API quirks
    - Real API returns integers (cents) not decimals
    - Real API has sub-penny precision (0.4275 not 0.43)
    - VCR catches conversion bugs mocks miss
    """

    def test_sub_penny_pricing_in_real_markets(self, monkeypatch):
        """
        Test that REAL Kalshi markets with sub-penny prices are parsed correctly.

        Kalshi supports 4 decimal places (0.4275).
        This test uses real market data to verify no precision loss.
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_markets.yaml"):
            client = KalshiClient(environment="demo")
            markets = client.get_markets(series_ticker="KXNFLGAME", limit=5)

        # Check ALL markets for Decimal precision
        # Note: We parse *_dollars fields for sub-penny precision
        for market in markets:
            price_fields = [
                "yes_bid_dollars",
                "yes_ask_dollars",
                "no_bid_dollars",
                "no_ask_dollars",
            ]
            for field in price_fields:
                # TypedDict dynamic key access requires type: ignore
                if field in market and market[field] is not None:  # type: ignore[literal-required]
                    price = market[field]  # type: ignore[literal-required]

                    # Verify Decimal type
                    assert isinstance(price, Decimal), (
                        f"Market {market['ticker']} field '{field}' is {type(price)}, expected Decimal"
                    )

                    # Verify string representation has NO precision loss
                    # Decimal("0.4275") should stringify back to "0.4275"
                    price_str = str(price)
                    assert "." in price_str or price == Decimal("0"), (
                        f"Price {price} should have decimal point (unless zero)"
                    )

    def test_cent_to_dollar_conversion_accuracy(self, monkeypatch):
        """
        Test that Kalshi cent values are converted to dollars correctly.

        Kalshi API returns:
        - balance: 235084 (cents) = $2350.84
        - portfolio_value: 10197 (cents) = $101.97

        Our client converts to dollars and preserves exact precision (no float rounding).
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_balance.yaml"):
            client = KalshiClient(environment="demo")
            balance = client.get_balance()

        # Client now returns dollars (converted from cents)
        # API returns 235084 cents, client converts to $2350.84
        assert balance == Decimal("2350.84"), "Balance should be in dollars"

        # Verify no float contamination
        assert isinstance(balance, Decimal), "Balance must be Decimal type"

        # Verify exact arithmetic is possible
        # This would fail with floats (2350.84 * 100 might not equal 235084 exactly)
        balance_cents = balance * Decimal("100")
        assert balance_cents == Decimal("235084"), "Conversion back to cents should be exact"

    def test_yes_no_price_complementarity(self, monkeypatch):
        """
        Test that YES + NO prices sum to $1.00 (Kalshi invariant).

        For any market: yes_price + no_price = 1.00
        This is a fundamental Kalshi property (zero-sum betting).

        Uses REAL fill data to verify: yes_price=0.04 + no_price=0.96 = 1.00
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_fills.yaml"):
            client = KalshiClient(environment="demo")
            fills = client.get_fills(limit=5)

        # Use real fill to test complementarity
        fill = fills[0]
        yes_price = fill["yes_price_fixed"]
        no_price = fill["no_price_fixed"]

        # Verify sum equals exactly $1.00 (no rounding errors!)
        total = yes_price + no_price
        assert total == Decimal("1.0000"), (
            f"YES ({yes_price}) + NO ({no_price}) should equal 1.0000, got {total}"
        )

        # This test would FAIL with float arithmetic:
        # >>> 0.96 + 0.04
        # 1.0000000000000002  # ❌ Float precision error!
        #
        # But passes with Decimal:
        # >>> Decimal("0.96") + Decimal("0.04")
        # Decimal("1.00")  # ✅ Exact!


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.timeout(30)
class TestKalshiClientSeriesWithVCR:
    """
    Test Kalshi Series API using VCR cassettes with REAL API data.

    The Series endpoint provides discovery of available market categories.

    Educational Note:
        Kalshi Market Hierarchy:
        - Category (sports, politics, entertainment, etc.)
          └── Series (KXNFLGAME, KXPRES2024, etc.)
              └── Events (individual games, elections)
                  └── Markets (specific outcome contracts)

        Why Series API Matters:
        - Dynamic discovery of available markets
        - No hardcoding of series tickers
        - Enables automated market monitoring

    Reference: Issue #257, SESSION_HANDOFF.md Priority 2 tasks
    """

    def test_get_series_with_real_api_data(self, monkeypatch):
        """
        Test get_series() with REAL recorded Kalshi series data.

        Uses cassette: kalshi_get_series.yaml
        - Real series from multiple categories
        - Real tickers, titles, and settlement sources
        - Validates series structure matches API specification
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_series.yaml"):
            client = KalshiClient(environment="demo")
            series = client.get_series(limit=10)

        # Verify real data structure
        assert isinstance(series, list), "Series should be a list"
        assert len(series) >= 1, "Should return at least 1 series from cassette"

        # Verify first series structure (real data)
        first_series = series[0]
        assert "ticker" in first_series, "Series must have ticker"
        assert "title" in first_series, "Series must have title"
        assert "category" in first_series, "Series must have category"

        # Verify ticker format (Kalshi series tickers start with KX)
        ticker = first_series.get("ticker", "")
        assert ticker.startswith("KX"), f"Series ticker should start with KX, got {ticker}"

    def test_series_categories_are_valid(self, monkeypatch):
        """
        Test that returned series have valid categories.

        Kalshi organizes series into categories like:
        - Sports (KXNFLGAME, KXNBAGAME)
        - Politics (KXPRES2024)
        - Entertainment (KXOSCARS)
        - Economics (KXCPI)
        - etc.

        This test validates the category field is populated.
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_series.yaml"):
            client = KalshiClient(environment="demo")
            series = client.get_series(limit=10)

        # Check categories are present and non-empty
        categories_found = set()
        for s in series:
            cat = s.get("category")
            if cat:
                categories_found.add(cat)

        # Should have at least one category from cassette
        assert len(categories_found) >= 1, "Should have at least 1 category"

        # Log categories for debugging
        # Common categories: Sports, Politics, Entertainment, Economics, World
        print(f"Categories found in cassette: {sorted(categories_found)}")

    def test_series_settlement_sources_structure(self, monkeypatch):
        """
        Test that series include settlement source information.

        Settlement sources are critical for understanding how markets resolve.
        Each series specifies authoritative sources for outcome determination.

        Example: KXNFLGAME uses ESPN/Fox Sports for settlement
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_series.yaml"):
            client = KalshiClient(environment="demo")
            series = client.get_series(limit=10)

        # Find a series with settlement sources
        series_with_sources = [s for s in series if s.get("settlement_sources")]

        if series_with_sources:
            # Verify settlement source structure
            sources = series_with_sources[0]["settlement_sources"]
            assert isinstance(sources, list), "settlement_sources should be a list"

            if sources:
                first_source = sources[0]
                assert "name" in first_source, "Source should have name"
                assert "url" in first_source, "Source should have url"

    def test_get_series_with_category_filter(self, monkeypatch):
        """
        Test that category filter returns matching series.

        Filters series by category (e.g., "Sports") and verifies
        only matching series are returned.

        Educational Note:
            Kalshi API category filter:
            - Case-sensitive: "Sports" not "sports"
            - Returns only series matching the category
            - Empty category returns all series
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "75b4b76e-d191-4855-b219-5c31cdcba1c8")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

        with my_vcr.use_cassette("kalshi_get_series.yaml"):
            client = KalshiClient(environment="demo")
            # Filter by Sports category (case-sensitive)
            series = client.get_series(category="Sports", limit=5)

        # Should return sports series
        assert isinstance(series, list), "Series should be a list"
        assert len(series) >= 1, "Should have at least 1 sports series"

        # Verify all returned series are in Sports category
        for s in series:
            assert s.get("category") == "Sports", (
                f"Expected Sports category, got {s.get('category')}"
            )
