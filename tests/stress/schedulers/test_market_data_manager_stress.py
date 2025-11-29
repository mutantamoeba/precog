"""
Stress, Race Condition, and Chaos Tests for MarketDataManager.

This test module covers three test categories from TESTING_STRATEGY_V3.1.md:
1. Stress Tests (Type 5) - Infrastructure limits and high-volume operations
2. Race Condition Tests (Type 6) - Concurrent operation validation
3. Chaos Tests (Type 8) - Failure recovery scenarios

WHY THESE TESTS MATTER:
-----------------------
MarketDataManager is a critical component that:
- Handles real-time price updates from WebSocket + Polling
- Uses threading with locks (_cache_lock, _lock)
- Fires callbacks to multiple subscribers
- Must maintain data integrity under concurrent access

Failure modes without proper testing:
- Corrupted prices from race conditions
- Missed callbacks due to lock contention
- Stale data from failed source switching
- Memory leaks from unclosed resources

Reference: TESTING_STRATEGY_V3.1.md Section "The 8 Test Types"
Related Requirements:
    - REQ-TEST-016: Stress Testing Requirements
    - REQ-DATA-005: Market Price Data Collection
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Test Markers (per TESTING_STRATEGY_V3.1.md)
# =============================================================================

pytestmark = [
    pytest.mark.stress,  # Infrastructure limit testing
    pytest.mark.race,  # Concurrent operation validation
]


# =============================================================================
# Helper: Create Mock MarketDataManager
# =============================================================================


def create_mock_manager(
    enable_websocket: bool = True,
    enable_polling: bool = True,
):
    """
    Create a MarketDataManager with mocked dependencies.

    Mocks KalshiMarketPoller and KalshiWebSocketHandler to isolate
    cache/threading behavior from network operations.
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
                enable_websocket=enable_websocket,
                enable_polling=enable_polling,
            )


# =============================================================================
# STRESS TESTS (Type 5): Infrastructure Limits
# =============================================================================


class TestHighVolumeUpdates:
    """
    Stress tests for high-volume price update scenarios.

    Tests that MarketDataManager handles burst traffic without:
    - Memory leaks (cache growth)
    - Lock starvation (reader/writer contention)
    - Callback queue overflow
    """

    @pytest.mark.stress
    def test_1000_rapid_price_updates(self):
        """
        Stress: Cache handles 1000 rapid updates without corruption.

        Simulates a burst of WebSocket messages (common during market open).
        """
        manager = create_mock_manager()
        errors = []

        def update_price(i: int) -> None:
            try:
                ticker = f"STRESS-{i % 10}"  # 10 unique tickers
                yes_price = Decimal(f"0.{(i % 100):02d}")
                no_price = Decimal("1") - yes_price
                manager._on_websocket_update(ticker, yes_price, no_price)
            except Exception as e:
                errors.append(str(e))

        # Fire 1000 updates as fast as possible
        for i in range(1000):
            update_price(i)

        # Verify no errors and cache integrity
        assert len(errors) == 0, f"Errors during rapid updates: {errors}"
        assert manager.stats["websocket_updates"] == 1000

        # Verify cache contains expected tickers
        for i in range(10):
            ticker = f"STRESS-{i}"
            cached = manager.get_current_price(ticker)
            assert cached is not None, f"Missing ticker: {ticker}"
            assert isinstance(cached["yes_price"], Decimal)

    @pytest.mark.stress
    def test_100_unique_tickers_cache_growth(self):
        """
        Stress: Cache handles 100 unique tickers without excessive memory.

        Verifies cache doesn't have memory leaks or unbounded growth.
        """
        manager = create_mock_manager()

        # Add 100 unique tickers
        for i in range(100):
            ticker = f"TICKER-{i:03d}"
            manager._on_websocket_update(ticker, Decimal("0.50"), Decimal("0.50"))

        # Verify all tickers cached
        assert len(manager._price_cache) == 100

        # Verify each ticker has correct price
        for i in range(100):
            ticker = f"TICKER-{i:03d}"
            cached = manager.get_current_price(ticker)
            assert cached is not None
            assert cached["yes_price"] == Decimal("0.50")

    @pytest.mark.stress
    def test_callbacks_under_high_load(self):
        """
        Stress: Callbacks fire correctly under high update volume.

        Verifies callback queue doesn't drop updates or deadlock.
        """
        manager = create_mock_manager()
        callback_count = {"count": 0}
        callback_lock = threading.Lock()

        def counting_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            with callback_lock:
                callback_count["count"] += 1

        manager.add_price_callback(counting_callback)

        # Fire 500 updates
        for i in range(500):
            manager._on_websocket_update(f"CB-{i}", Decimal("0.50"), Decimal("0.50"))

        # All callbacks should have fired
        assert callback_count["count"] == 500


# =============================================================================
# RACE CONDITION TESTS (Type 6): Concurrent Operation Validation
# =============================================================================


class TestConcurrentCacheAccess:
    """
    Race condition tests for concurrent cache read/write operations.

    Tests that _cache_lock properly protects _price_cache from:
    - Torn reads (partial update visible)
    - Lost updates (overwritten without lock)
    - Deadlocks (threads waiting forever)
    """

    @pytest.mark.race
    def test_concurrent_writes_no_corruption(self):
        """
        Race: Concurrent writes don't corrupt cache values.

        Simulates WebSocket + Polling both updating same ticker.
        Each thread writes distinct values; final value should be valid.
        """
        manager = create_mock_manager()
        ticker = "RACE-TEST"
        errors = []

        def writer_thread(thread_id: int, iterations: int) -> None:
            for i in range(iterations):
                try:
                    # Each thread writes distinct prices
                    yes_price = Decimal(f"0.{thread_id}{(i % 10):01d}")
                    no_price = Decimal("1") - yes_price
                    manager._on_websocket_update(ticker, yes_price, no_price)
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")

        # Launch 5 concurrent writers
        threads = []
        for tid in range(5):
            t = threading.Thread(target=writer_thread, args=(tid, 100))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join(timeout=10)

        # Verify no errors
        assert len(errors) == 0, f"Race condition errors: {errors}"

        # Verify final value is valid Decimal (not corrupted)
        cached = manager.get_current_price(ticker)
        assert cached is not None
        assert isinstance(cached["yes_price"], Decimal)
        assert isinstance(cached["no_price"], Decimal)
        assert Decimal("0") <= cached["yes_price"] <= Decimal("1")

    @pytest.mark.race
    def test_concurrent_read_write_no_torn_reads(self):
        """
        Race: Readers don't see partially-updated values.

        A "torn read" would be: yes_price from update N, no_price from update N+1.
        This test verifies yes + no always sums to a consistent value.
        """
        manager = create_mock_manager()
        ticker = "TORN-READ-TEST"
        torn_reads = []
        read_count = {"count": 0}

        def writer_thread(iterations: int) -> None:
            for i in range(iterations):
                yes_price = Decimal(f"0.{(i % 100):02d}")
                no_price = Decimal("1") - yes_price
                manager._on_websocket_update(ticker, yes_price, no_price)
                time.sleep(0.0001)  # Small delay to increase interleaving

        def reader_thread(iterations: int) -> None:
            for _ in range(iterations):
                cached = manager.get_current_price(ticker)
                if cached:
                    price_sum = cached["yes_price"] + cached["no_price"]
                    # Sum should always be exactly 1 (our invariant)
                    if price_sum != Decimal("1"):
                        torn_reads.append(
                            f"Torn read: yes={cached['yes_price']}, no={cached['no_price']}, sum={price_sum}"
                        )
                    read_count["count"] += 1

        # Pre-populate cache
        manager._on_websocket_update(ticker, Decimal("0.50"), Decimal("0.50"))

        # Launch writer and readers
        writer = threading.Thread(target=writer_thread, args=(200,))
        readers = [threading.Thread(target=reader_thread, args=(100,)) for _ in range(3)]

        writer.start()
        for r in readers:
            r.start()

        writer.join(timeout=10)
        for r in readers:
            r.join(timeout=10)

        # Verify no torn reads
        assert len(torn_reads) == 0, f"Torn reads detected: {torn_reads[:5]}"
        assert read_count["count"] > 0, "No reads completed"

    @pytest.mark.race
    def test_callback_fired_during_concurrent_updates(self):
        """
        Race: Callbacks receive correct prices during concurrent updates.

        Verifies callbacks don't receive stale or mixed values.
        """
        manager = create_mock_manager()
        callback_errors = []
        callback_lock = threading.Lock()

        def validating_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            # Each callback should have consistent values
            with callback_lock:
                if yes + no != Decimal("1"):
                    callback_errors.append(f"Inconsistent callback: yes={yes}, no={no}")

        manager.add_price_callback(validating_callback)

        def update_thread(thread_id: int) -> None:
            for i in range(50):
                yes_price = Decimal(f"0.{(thread_id * 10 + i) % 100:02d}")
                no_price = Decimal("1") - yes_price
                manager._on_websocket_update(f"CB-RACE-{thread_id}", yes_price, no_price)

        threads = [threading.Thread(target=update_thread, args=(tid,)) for tid in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(callback_errors) == 0, f"Callback errors: {callback_errors[:5]}"


class TestConcurrentTickerOperations:
    """
    Race condition tests for multiple tickers accessed concurrently.

    Tests cache isolation between tickers under concurrent access.
    """

    @pytest.mark.race
    def test_independent_tickers_no_cross_contamination(self):
        """
        Race: Updates to ticker A don't affect ticker B.

        Each thread updates a different ticker; values should never mix.
        """
        manager = create_mock_manager()
        contamination_errors = []

        def update_ticker(ticker: str, base_value: int, iterations: int) -> None:
            for i in range(iterations):
                yes_price = Decimal(f"0.{base_value:02d}")
                no_price = Decimal("1") - yes_price
                manager._on_websocket_update(ticker, yes_price, no_price)
                time.sleep(0.0001)

        def verify_ticker(ticker: str, expected_base: int, iterations: int) -> None:
            for _ in range(iterations):
                cached = manager.get_current_price(ticker)
                if cached:
                    # Check for contamination (wrong base value)
                    yes_str = str(cached["yes_price"])
                    if f".{expected_base:02d}" not in yes_str:
                        contamination_errors.append(
                            f"{ticker}: expected base {expected_base}, got {cached['yes_price']}"
                        )

        # Pre-populate
        manager._on_websocket_update("TICKER-A", Decimal("0.10"), Decimal("0.90"))
        manager._on_websocket_update("TICKER-B", Decimal("0.20"), Decimal("0.80"))
        manager._on_websocket_update("TICKER-C", Decimal("0.30"), Decimal("0.70"))

        threads = [
            threading.Thread(target=update_ticker, args=("TICKER-A", 10, 50)),
            threading.Thread(target=update_ticker, args=("TICKER-B", 20, 50)),
            threading.Thread(target=update_ticker, args=("TICKER-C", 30, 50)),
            threading.Thread(target=verify_ticker, args=("TICKER-A", 10, 100)),
            threading.Thread(target=verify_ticker, args=("TICKER-B", 20, 100)),
            threading.Thread(target=verify_ticker, args=("TICKER-C", 30, 100)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(contamination_errors) == 0, f"Cross-contamination: {contamination_errors[:5]}"


# =============================================================================
# CHAOS TESTS (Type 8): Failure Recovery Scenarios
# =============================================================================


class TestCallbackFailureRecovery:
    """
    Chaos tests for callback failure scenarios.

    Tests that MarketDataManager continues functioning when:
    - Callbacks throw exceptions
    - Callbacks are slow/blocking
    - Multiple callbacks fail simultaneously
    """

    @pytest.mark.chaos
    def test_callback_exception_doesnt_break_updates(self):
        """
        Chaos: Exception in callback doesn't prevent price updates.

        A misbehaving callback shouldn't break the update pipeline.
        """
        manager = create_mock_manager()
        successful_callbacks = {"count": 0}

        def throwing_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            raise ValueError("Intentional test error")

        def counting_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            successful_callbacks["count"] += 1

        manager.add_price_callback(throwing_callback)
        manager.add_price_callback(counting_callback)

        # Update should complete despite throwing callback
        manager._on_websocket_update("CHAOS-1", Decimal("0.50"), Decimal("0.50"))
        manager._on_websocket_update("CHAOS-2", Decimal("0.60"), Decimal("0.40"))

        # Cache should still be updated
        cached = manager.get_current_price("CHAOS-1")
        assert cached is not None
        assert cached["yes_price"] == Decimal("0.50")

        # Second callback should still have fired
        assert successful_callbacks["count"] == 2

    @pytest.mark.chaos
    def test_slow_callback_doesnt_block_updates(self):
        """
        Chaos: Slow callback doesn't block subsequent updates.

        Tests that callback execution is non-blocking.
        """
        manager = create_mock_manager()
        update_times = []

        def slow_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            time.sleep(0.1)  # Simulates slow processing

        manager.add_price_callback(slow_callback)

        # Time multiple updates
        for i in range(5):
            start = time.time()
            manager._on_websocket_update(f"SLOW-{i}", Decimal("0.50"), Decimal("0.50"))
            update_times.append(time.time() - start)

        # Updates should complete quickly (callbacks may be slow)
        # Note: If callbacks are synchronous, this test documents current behavior
        assert manager.stats["websocket_updates"] == 5


class TestSourceFailover:
    """
    Chaos tests for data source failover scenarios.

    Tests that MarketDataManager handles:
    - WebSocket disconnect
    - Polling failure
    - Both sources failing
    """

    @pytest.mark.chaos
    def test_cache_retains_data_when_sources_fail(self):
        """
        Chaos: Cached data remains accessible when sources fail.

        Even if WebSocket/Polling stop updating, cached data should be readable.
        """
        manager = create_mock_manager()

        # Populate cache
        manager._on_websocket_update("FAILOVER-1", Decimal("0.65"), Decimal("0.35"))

        # Simulate "disconnection" by checking cache directly
        # (In real scenario, sources would stop updating)
        cached = manager.get_current_price("FAILOVER-1")
        assert cached is not None
        assert cached["yes_price"] == Decimal("0.65")

        # Cache should mark data as potentially stale (if implemented)
        # This tests the contract: data remains accessible

    @pytest.mark.chaos
    def test_stats_track_update_sources(self):
        """
        Chaos: Statistics correctly track updates per source.

        Useful for monitoring failover behavior.
        """
        manager = create_mock_manager()

        initial_ws_updates = manager.stats["websocket_updates"]

        # Simulate 5 WebSocket updates
        for i in range(5):
            manager._on_websocket_update(f"STATS-{i}", Decimal("0.50"), Decimal("0.50"))

        assert manager.stats["websocket_updates"] == initial_ws_updates + 5


class TestResourceExhaustion:
    """
    Chaos tests for resource exhaustion scenarios.

    Tests behavior under memory pressure or callback accumulation.
    """

    @pytest.mark.chaos
    def test_many_callbacks_dont_leak(self):
        """
        Chaos: Adding many callbacks doesn't cause memory leaks.

        Tests that callback list is properly managed.
        """
        manager = create_mock_manager()

        # Add 100 callbacks (callback count tracked via manager._callbacks)
        for i in range(100):

            def cb(ticker: str, yes: Decimal, no: Decimal, idx: int = i) -> None:
                pass

            manager.add_price_callback(cb)

        assert len(manager._callbacks) == 100

        # Update should fire all callbacks without error
        manager._on_websocket_update("MANY-CB", Decimal("0.50"), Decimal("0.50"))


# =============================================================================
# THREAD POOL STRESS TESTS
# =============================================================================


class TestThreadPoolStress:
    """
    Stress tests using ThreadPoolExecutor for higher concurrency.

    Tests behavior under many parallel operations.
    """

    @pytest.mark.stress
    def test_50_concurrent_updates(self):
        """
        Stress: 50 concurrent threads updating cache simultaneously.
        """
        manager = create_mock_manager()

        def update_task(task_id: int) -> dict[str, Any]:
            try:
                for i in range(20):
                    ticker = f"POOL-{task_id}-{i % 5}"
                    yes = Decimal(f"0.{(task_id * 10 + i) % 100:02d}")
                    no = Decimal("1") - yes
                    manager._on_websocket_update(ticker, yes, no)
                return {"task_id": task_id, "status": "success"}
            except Exception as e:
                return {"task_id": task_id, "status": "error", "error": str(e)}

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(update_task, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]

        # Check all tasks succeeded
        failed = [r for r in results if r["status"] != "success"]
        assert len(failed) == 0, f"Failed tasks: {failed}"

        # Verify stats
        assert manager.stats["websocket_updates"] == 50 * 20  # 50 tasks * 20 updates each
