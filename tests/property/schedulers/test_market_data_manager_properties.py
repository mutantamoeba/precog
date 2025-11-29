"""
Property-Based Tests for MarketDataManager Decimal Price Operations.

Tests mathematical invariants and precision guarantees for price handling:
1. Decimal precision is preserved through cache operations
2. YES + NO price sum constraints (Kalshi market invariant)
3. Price staleness detection correctness
4. Callback parameter type safety (always Decimal)

Uses Hypothesis to generate thousands of test cases automatically,
catching edge cases that example-based tests would miss.

Reference: Pattern 10 in CLAUDE.md - Property-Based Testing
Related Requirements:
    - REQ-TEST-008: Property-Based Testing Framework
    - REQ-DATA-005: Market Price Data Collection
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.property.strategies import decimal_price

# =============================================================================
# Helper Function (instead of fixture for Hypothesis compatibility)
# =============================================================================


def create_mock_manager():
    """Create a fresh MarketDataManager with mocked dependencies.

    Note: This is a function, not a fixture, because Hypothesis @given
    tests don't work well with pytest fixtures (fixture state is shared
    between generated inputs).
    """
    with patch("precog.schedulers.market_data_manager.KalshiMarketPoller") as mock_poller:
        with patch("precog.schedulers.market_data_manager.KalshiWebSocketHandler") as mock_ws:
            mock_poller.return_value = MagicMock()
            mock_poller.return_value.poll_once.return_value = {
                "markets_fetched": 0,
                "markets_updated": 0,
                "markets_created": 0,
            }
            mock_ws.return_value = MagicMock()

            from precog.schedulers.market_data_manager import MarketDataManager

            return MarketDataManager(
                environment="demo",
                enable_websocket=True,
                enable_polling=True,
            )


# =============================================================================
# Property Tests: Decimal Precision Preservation
# =============================================================================


class TestDecimalPrecisionPreservation:
    """
    Property: Decimal precision must be preserved through all cache operations.

    Why This Matters:
    - Trading uses sub-penny precision (4 decimal places)
    - Floating-point errors cause incorrect position sizing
    - Kalshi prices like $0.4975 must stay exact, not become 0.4974999...
    """

    @given(yes_price=decimal_price(), no_price=decimal_price())
    @settings(
        max_examples=100, deadline=None
    )  # deadline=None: first run slow due to module loading
    def test_price_precision_preserved_in_cache(self, yes_price: Decimal, no_price: Decimal):
        """
        Property: Stored prices maintain exact Decimal precision.

        Given: Any valid Decimal prices
        When: Stored in cache via _on_websocket_update
        Then: Retrieved prices are exactly equal (no floating-point drift)
        """
        manager = create_mock_manager()
        ticker = "TEST-PROP-001"

        # Store price via internal update method
        manager._on_websocket_update(ticker, yes_price, no_price)

        # Retrieve from cache
        cached = manager.get_current_price(ticker)

        # Precision preservation invariant
        assert cached is not None, "Price should be cached"
        assert cached["yes_price"] == yes_price, (
            f"YES price drift: {cached['yes_price']} != {yes_price}"
        )
        assert cached["no_price"] == no_price, f"NO price drift: {cached['no_price']} != {no_price}"
        assert isinstance(cached["yes_price"], Decimal), "YES price must be Decimal"
        assert isinstance(cached["no_price"], Decimal), "NO price must be Decimal"

    @given(price=decimal_price(places=4))
    @settings(max_examples=50, deadline=None)
    def test_sub_penny_precision_exact(self, price: Decimal):
        """
        Property: Sub-penny prices (4 decimal places) are preserved exactly.

        This is critical for Kalshi where prices like $0.4975 are common.
        """
        manager = create_mock_manager()
        ticker = "SUBPENNY-TEST"
        complement = Decimal("1") - price

        manager._on_websocket_update(ticker, price, complement)
        cached = manager.get_current_price(ticker)

        assert cached is not None
        # Check exact equality (not approximate)
        assert cached["yes_price"] == price
        assert cached["no_price"] == complement


# =============================================================================
# Property Tests: Price Sum Invariants
# =============================================================================


class TestPriceSumInvariants:
    """
    Property: YES + NO prices follow Kalshi market structure.

    Kalshi Market Economics:
    - YES + NO = 1.0 (in efficient markets)
    - YES + NO < 1.0 (with spread/fees)
    - YES + NO > 1.0 should never happen (arbitrage opportunity)

    Note: MarketDataManager STORES prices, it doesn't validate them.
    These tests verify STORAGE precision, not market validity.
    """

    @given(
        yes_price=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.95"), places=4),
        spread=st.decimals(min_value=Decimal("0"), max_value=Decimal("0.04"), places=4),
    )
    @settings(max_examples=100, deadline=None)
    def test_yes_no_sum_preserved_in_cache(self, yes_price: Decimal, spread: Decimal):
        """
        Property: Cache preserves YES + NO sum exactly.

        Given: Complementary prices (yes + no <= 1.0)
        When: Stored in cache
        Then: Retrieved sum equals original sum (no drift)

        Note: We generate valid market prices (sum <= 1.0) to simulate
        realistic inputs from WebSocket updates.
        """
        manager = create_mock_manager()
        # Generate NO price as complement with optional spread (ensures sum <= 1.0)
        no_price = Decimal("1") - yes_price - spread
        ticker = "SUM-TEST"

        original_sum = yes_price + no_price
        manager._on_websocket_update(ticker, yes_price, no_price)
        cached = manager.get_current_price(ticker)

        assert cached is not None
        cached_sum = cached["yes_price"] + cached["no_price"]

        # Precision preservation invariant: sum shouldn't drift
        assert cached_sum == original_sum, f"Sum drifted: {cached_sum} != {original_sum}"
        # Market validity invariant: should still satisfy <= 1.0
        assert cached_sum <= Decimal("1.0"), f"Price sum {cached_sum} exceeds 1.0"

    @given(yes_price=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=4))
    @settings(max_examples=100, deadline=None)
    def test_complement_price_calculation(self, yes_price: Decimal):
        """
        Property: If prices are complements, they sum to exactly 1.0.

        This tests the common case where YES and NO are perfect complements.
        """
        manager = create_mock_manager()
        no_price = Decimal("1") - yes_price
        ticker = "COMPLEMENT-TEST"

        manager._on_websocket_update(ticker, yes_price, no_price)
        cached = manager.get_current_price(ticker)

        assert cached is not None
        price_sum = cached["yes_price"] + cached["no_price"]

        # Perfect complement invariant
        assert price_sum == Decimal("1"), f"Complement sum {price_sum} != 1.0"


# =============================================================================
# Property Tests: Callback Type Safety
# =============================================================================


class TestCallbackTypeSafety:
    """
    Property: Callbacks always receive Decimal parameters, never float.

    This ensures type safety through the callback chain.
    """

    @given(yes_price=decimal_price(), no_price=decimal_price())
    @settings(max_examples=50, deadline=None)
    def test_callbacks_receive_decimal_types(self, yes_price: Decimal, no_price: Decimal):
        """
        Property: Callback parameters are always Decimal instances.

        Given: Any valid prices
        When: Price update fires callbacks
        Then: Callback receives Decimal types (not float)
        """
        manager = create_mock_manager()
        received_types = []

        def type_checking_callback(ticker: str, yes: Decimal, no: Decimal):
            received_types.append((type(yes).__name__, type(no).__name__))

        manager.add_price_callback(type_checking_callback)
        manager._on_websocket_update("TYPE-TEST", yes_price, no_price)

        assert len(received_types) == 1
        yes_type, no_type = received_types[0]
        assert yes_type == "Decimal", f"YES type is {yes_type}, expected Decimal"
        assert no_type == "Decimal", f"NO type is {no_type}, expected Decimal"

    @given(yes_price=decimal_price(), no_price=decimal_price())
    @settings(max_examples=50, deadline=None)
    def test_callback_receives_exact_values(self, yes_price: Decimal, no_price: Decimal):
        """
        Property: Callback values match what was set (no transformation).
        """
        manager = create_mock_manager()
        received_values = []

        def value_capture_callback(ticker: str, yes: Decimal, no: Decimal):
            received_values.append((yes, no))

        manager.add_price_callback(value_capture_callback)
        manager._on_websocket_update("VALUE-TEST", yes_price, no_price)

        assert len(received_values) == 1
        received_yes, received_no = received_values[0]
        assert received_yes == yes_price, "Callback YES value mismatch"
        assert received_no == no_price, "Callback NO value mismatch"


# =============================================================================
# Property Tests: Cache Consistency
# =============================================================================


class TestCacheConsistency:
    """
    Property: Cache operations maintain data consistency.
    """

    @given(
        prices=st.lists(
            st.tuples(
                st.text(
                    min_size=5,
                    max_size=20,
                    alphabet=st.characters(whitelist_categories=("Lu", "Nd", "Pd")),
                ),
                decimal_price(),
                decimal_price(),
            ),
            min_size=1,
            max_size=20,
            unique_by=lambda x: x[0],  # Unique by ticker name to avoid overwrites
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_multiple_tickers_independent(self, prices: list[tuple[str, Decimal, Decimal]]):
        """
        Property: Each ticker's price is independent in the cache.

        Given: Multiple UNIQUE tickers with different prices
        When: All are stored in cache
        Then: Each retrieves its own correct price (no cross-contamination)

        Note: unique_by=ticker ensures no duplicates that would overwrite.
        """
        manager = create_mock_manager()

        # Filter out empty tickers first
        valid_prices = [(t, y, n) for t, y, n in prices if t]

        # Store all prices
        for ticker, yes, no in valid_prices:
            manager._on_websocket_update(ticker, yes, no)

        # Verify each ticker has correct price
        for ticker, expected_yes, expected_no in valid_prices:
            cached = manager.get_current_price(ticker)
            assert cached is not None, f"{ticker}: not found in cache"
            assert cached["yes_price"] == expected_yes, f"{ticker}: YES mismatch"
            assert cached["no_price"] == expected_no, f"{ticker}: NO mismatch"

    @given(
        updates=st.lists(
            st.tuples(decimal_price(), decimal_price()),
            min_size=2,
            max_size=10,
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_latest_update_wins(self, updates: list[tuple[Decimal, Decimal]]):
        """
        Property: Multiple updates to same ticker keep only the latest.

        Given: Multiple price updates to the same ticker
        When: All updates are applied
        Then: Cache contains only the last update
        """
        manager = create_mock_manager()
        ticker = "UPDATE-TEST"

        for yes, no in updates:
            manager._on_websocket_update(ticker, yes, no)

        cached = manager.get_current_price(ticker)
        assert cached is not None

        expected_yes, expected_no = updates[-1]
        assert cached["yes_price"] == expected_yes, "Latest YES not cached"
        assert cached["no_price"] == expected_no, "Latest NO not cached"


# =============================================================================
# Property Tests: Statistics Tracking
# =============================================================================


class TestStatisticsTracking:
    """
    Property: Statistics counters maintain consistency.
    """

    @given(update_count=st.integers(min_value=1, max_value=50))
    @settings(max_examples=20, deadline=None)
    def test_websocket_update_counter_accuracy(self, update_count: int):
        """
        Property: WebSocket update counter matches actual update count.

        Given: N updates
        When: All updates processed
        Then: stats["websocket_updates"] == N
        """
        manager = create_mock_manager()
        initial_count = manager.stats["websocket_updates"]

        for i in range(update_count):
            manager._on_websocket_update(
                f"STATS-{i}",
                Decimal("0.50"),
                Decimal("0.50"),
            )

        final_count = manager.stats["websocket_updates"]
        assert final_count == initial_count + update_count, (
            f"Counter mismatch: expected {initial_count + update_count}, got {final_count}"
        )
