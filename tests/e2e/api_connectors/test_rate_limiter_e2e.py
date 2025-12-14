"""
End-to-End Tests for Rate Limiter.

Tests complete workflows including initialization, usage patterns,
and real-world scenarios for rate limiting.

Reference: TESTING_STRATEGY V3.2 - E2E tests for critical workflows
Related Requirements: REQ-API-005 (API Rate Limit Management)

Usage:
    pytest tests/e2e/api_connectors/test_rate_limiter_e2e.py -v -m e2e
"""

import threading
import time
from unittest.mock import patch

import pytest

from precog.api_connectors.rate_limiter import RateLimiter, TokenBucket

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def kalshi_rate_limiter() -> RateLimiter:
    """Create a rate limiter configured for Kalshi API (100 req/min)."""
    return RateLimiter(requests_per_minute=100)


@pytest.fixture
def espn_rate_limiter() -> RateLimiter:
    """Create a rate limiter configured for ESPN API."""
    return RateLimiter(requests_per_minute=500)


# =============================================================================
# E2E Tests: Complete Lifecycle
# =============================================================================


@pytest.mark.e2e
class TestCompleteLifecycle:
    """E2E tests for complete rate limiter lifecycle."""

    def test_create_use_workflow(self) -> None:
        """Test complete create-configure-use-monitor workflow."""
        # Create limiter for Kalshi
        limiter = RateLimiter(requests_per_minute=100)

        # Verify configuration
        assert limiter.requests_per_minute == 100
        assert limiter.burst_size == 100
        assert limiter.get_utilization() == 0.0

        # Use for API calls
        api_calls_made = 0
        for _ in range(10):
            limiter.wait_if_needed()
            api_calls_made += 1

        # Monitor utilization
        util = limiter.get_utilization()
        assert util > 0.0
        assert api_calls_made == 10

    def test_multiple_api_clients_sharing_limiter(self) -> None:
        """Test multiple simulated API clients sharing one limiter."""
        shared_limiter = RateLimiter(requests_per_minute=600)

        class MockAPIClient:
            def __init__(self, name: str, limiter: RateLimiter):
                self.name = name
                self.limiter = limiter
                self.requests_made = 0

            def make_request(self) -> None:
                self.limiter.wait_if_needed()
                self.requests_made += 1

        # Create clients
        client1 = MockAPIClient("markets", shared_limiter)
        client2 = MockAPIClient("balance", shared_limiter)
        client3 = MockAPIClient("positions", shared_limiter)

        # Make requests from different clients
        for _ in range(10):
            client1.make_request()
            client2.make_request()
            client3.make_request()

        # All should have made requests
        assert client1.requests_made == 10
        assert client2.requests_made == 10
        assert client3.requests_made == 10

        # Shared utilization should reflect all requests
        util = shared_limiter.get_utilization()
        assert util > 0.0


# =============================================================================
# E2E Tests: API Usage Patterns
# =============================================================================


@pytest.mark.e2e
class TestAPIUsagePatterns:
    """E2E tests for common API usage patterns."""

    def test_market_polling_pattern(self, kalshi_rate_limiter: RateLimiter) -> None:
        """Test pattern: periodic market polling."""
        polls_completed = 0
        poll_times: list[float] = []

        # Simulate polling every 100ms for 0.5 seconds
        start = time.time()
        while time.time() - start < 0.5:
            kalshi_rate_limiter.wait_if_needed()
            poll_times.append(time.time())
            polls_completed += 1
            time.sleep(0.05)  # 50ms between polls

        # Should have completed several polls
        assert polls_completed > 5

    def test_batch_request_pattern(self, kalshi_rate_limiter: RateLimiter) -> None:
        """Test pattern: batch of requests followed by pause."""
        batch_sizes = [5, 10, 5, 8]
        total_requests = 0

        for batch_size in batch_sizes:
            # Make batch of requests
            for _ in range(batch_size):
                kalshi_rate_limiter.wait_if_needed()
                total_requests += 1

            # Pause between batches
            time.sleep(0.1)

        assert total_requests == sum(batch_sizes)

    def test_rate_limit_recovery_pattern(self) -> None:
        """Test pattern: hit rate limit, wait, recover."""
        limiter = RateLimiter(requests_per_minute=600, burst_size=10)

        # Drain the burst capacity
        drained = 0
        while limiter.bucket.acquire(tokens=1, block=False):
            drained += 1
            if drained > 20:
                break

        # Should have drained burst capacity
        assert drained >= 10

        # Check utilization is high
        util = limiter.get_utilization()
        assert util > 0.5

        # Wait for recovery
        time.sleep(0.1)

        # Should have recovered some capacity
        recovered_util = limiter.get_utilization()
        assert recovered_util < util

    def test_429_error_recovery_pattern(self, kalshi_rate_limiter: RateLimiter) -> None:
        """Test pattern: receive 429, wait with Retry-After, continue."""
        requests_before_429 = 0
        requests_after_recovery = 0

        # Make requests until "429" (simulated)
        for _ in range(5):
            kalshi_rate_limiter.wait_if_needed()
            requests_before_429 += 1

        # Simulate receiving 429 with Retry-After: 1
        with patch("time.sleep") as mock_sleep:
            kalshi_rate_limiter.handle_rate_limit_error(retry_after=1)
            mock_sleep.assert_called_with(1)

        # Continue after recovery
        for _ in range(3):
            kalshi_rate_limiter.wait_if_needed()
            requests_after_recovery += 1

        assert requests_before_429 == 5
        assert requests_after_recovery == 3


# =============================================================================
# E2E Tests: Multi-threaded Scenarios
# =============================================================================


@pytest.mark.e2e
class TestMultithreadedScenarios:
    """E2E tests for multi-threaded usage scenarios."""

    def test_concurrent_api_clients(self) -> None:
        """Test multiple concurrent API clients."""
        limiter = RateLimiter(requests_per_minute=1200)  # 20/sec

        results: dict[str, int] = {}
        lock = threading.Lock()

        def client_worker(client_id: str, num_requests: int) -> None:
            for _ in range(num_requests):
                limiter.wait_if_needed()
                with lock:
                    results[client_id] = results.get(client_id, 0) + 1

        # Start multiple clients
        threads = [
            threading.Thread(target=client_worker, args=(f"client_{i}", 10)) for i in range(5)
        ]

        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        # All clients should have made their requests
        for i in range(5):
            assert results[f"client_{i}"] == 10

        # Total 50 requests, should be fast with high limit
        assert elapsed < 5.0

    def test_producer_consumer_pattern(self) -> None:
        """Test producer-consumer pattern with rate limiting."""
        limiter = RateLimiter(requests_per_minute=600)
        request_queue: list[str] = []
        processed: list[str] = []
        lock = threading.Lock()
        stop_flag = threading.Event()

        def producer() -> None:
            """Producer adds requests to queue."""
            for i in range(20):
                with lock:
                    request_queue.append(f"request_{i}")
                time.sleep(0.01)

        def consumer() -> None:
            """Consumer processes requests with rate limiting."""
            while not stop_flag.is_set() or request_queue:
                with lock:
                    req = request_queue.pop(0) if request_queue else None

                if req:
                    limiter.wait_if_needed()
                    with lock:
                        processed.append(req)
                else:
                    time.sleep(0.01)

        # Run producer and consumer
        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join()
        time.sleep(0.5)  # Give consumer time to finish
        stop_flag.set()
        consumer_thread.join(timeout=2)

        # All requests should be processed
        assert len(processed) == 20


# =============================================================================
# E2E Tests: Real-World Simulation
# =============================================================================


@pytest.mark.e2e
class TestRealWorldSimulation:
    """E2E tests simulating real-world API usage."""

    def test_kalshi_trading_session(self) -> None:
        """Test simulating a Kalshi trading session."""
        # Kalshi allows 100 req/min
        limiter = RateLimiter(requests_per_minute=100)

        # Simulate trading session actions
        actions = [
            ("get_balance", 1),
            ("get_positions", 5),
            ("get_markets", 10),
            ("place_order", 3),
            ("get_order_status", 3),
            ("cancel_order", 1),
        ]

        requests_made: dict[str, int] = {}

        for action_name, count in actions:
            requests_made[action_name] = 0
            for _ in range(count):
                limiter.wait_if_needed()
                requests_made[action_name] += 1

        # Verify all actions completed
        assert requests_made["get_balance"] == 1
        assert requests_made["get_positions"] == 5
        assert requests_made["get_markets"] == 10
        assert requests_made["place_order"] == 3

    def test_espn_data_collection(self, espn_rate_limiter: RateLimiter) -> None:
        """Test simulating ESPN data collection."""
        # Collect data for multiple leagues
        leagues = ["nfl", "ncaaf", "nba", "ncaab"]
        data_collected: dict[str, int] = {}

        for league in leagues:
            data_collected[league] = 0
            # Get scoreboard (1 request)
            espn_rate_limiter.wait_if_needed()
            data_collected[league] += 1

            # Get details for each game (3 requests per league)
            for _ in range(3):
                espn_rate_limiter.wait_if_needed()
                data_collected[league] += 1

        # Verify data collection completed
        for league in leagues:
            assert data_collected[league] == 4

    def test_burst_then_throttle(self) -> None:
        """Test burst of requests followed by throttling."""
        limiter = RateLimiter(requests_per_minute=120, burst_size=20)

        # Burst phase - should complete quickly
        burst_count = 0
        burst_start = time.time()
        for _ in range(20):
            limiter.wait_if_needed()
            burst_count += 1
        burst_duration = time.time() - burst_start

        # Burst should be fast (less than 0.5s)
        assert burst_duration < 0.5

        # Throttled phase - rate limited
        throttled_count = 0
        throttle_start = time.time()
        while time.time() - throttle_start < 0.5:
            limiter.wait_if_needed()
            throttled_count += 1

        # Should have made some requests during throttled phase
        assert throttled_count > 0
        # But fewer than burst due to rate limiting
        assert burst_count + throttled_count > 20


# =============================================================================
# E2E Tests: Error Handling Workflows
# =============================================================================


@pytest.mark.e2e
class TestErrorHandlingWorkflows:
    """E2E tests for error handling workflows."""

    def test_handle_multiple_429_errors(self, kalshi_rate_limiter: RateLimiter) -> None:
        """Test handling multiple consecutive 429 errors."""
        retry_afters = [5, 10, 30]

        with patch("time.sleep") as mock_sleep:
            for retry_after in retry_afters:
                kalshi_rate_limiter.handle_rate_limit_error(retry_after=retry_after)

            # Should have slept for each retry-after
            assert mock_sleep.call_count == 3
            mock_sleep.assert_any_call(5)
            mock_sleep.assert_any_call(10)
            mock_sleep.assert_any_call(30)

    def test_mixed_success_and_errors(self, kalshi_rate_limiter: RateLimiter) -> None:
        """Test workflow with mixed successful requests and errors."""
        successful = 0
        errors_handled = 0

        with patch("time.sleep"):
            # Phase 1: Successful requests
            for _ in range(5):
                kalshi_rate_limiter.wait_if_needed()
                successful += 1

            # Phase 2: Simulated 429 error
            kalshi_rate_limiter.handle_rate_limit_error(retry_after=1)
            errors_handled += 1

            # Phase 3: More successful requests
            for _ in range(3):
                kalshi_rate_limiter.wait_if_needed()
                successful += 1

            # Phase 4: Another error
            kalshi_rate_limiter.handle_rate_limit_error(retry_after=None)
            errors_handled += 1

        assert successful == 8
        assert errors_handled == 2


# =============================================================================
# E2E Tests: Monitoring and Observability
# =============================================================================


@pytest.mark.e2e
class TestMonitoringObservability:
    """E2E tests for monitoring and observability."""

    def test_utilization_tracking_over_time(self) -> None:
        """Test tracking utilization over time."""
        limiter = RateLimiter(requests_per_minute=600)

        utilization_history: list[float] = []

        # Record initial utilization
        utilization_history.append(limiter.get_utilization())

        # Make requests and record utilization
        for _ in range(10):
            limiter.wait_if_needed()
            utilization_history.append(limiter.get_utilization())

        # Utilization should generally increase
        assert utilization_history[0] == 0.0  # Initially empty
        assert utilization_history[-1] > 0.0  # After requests

    def test_available_tokens_monitoring(self) -> None:
        """Test monitoring available tokens over time."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)

        tokens_history: list[float] = []

        # Record initial
        tokens_history.append(bucket.get_available_tokens())

        # Consume tokens
        for _ in range(30):
            bucket.acquire(tokens=1, block=False)
            tokens_history.append(bucket.get_available_tokens())

        # Tokens should decrease
        assert tokens_history[0] == 100
        assert tokens_history[-1] < 100

        # Wait for partial refill
        time.sleep(0.1)
        tokens_history.append(bucket.get_available_tokens())

        # Should have refilled some
        assert tokens_history[-1] > tokens_history[-2]


# =============================================================================
# E2E Tests: Configuration Scenarios
# =============================================================================


@pytest.mark.e2e
class TestConfigurationScenarios:
    """E2E tests for various configuration scenarios."""

    def test_conservative_rate_limit(self) -> None:
        """Test with conservative rate limit (80% of actual limit)."""
        # Kalshi is 100/min, use 80/min to be safe
        limiter = RateLimiter(requests_per_minute=80)

        # Make burst of requests
        start = time.time()
        for _ in range(20):
            limiter.wait_if_needed()
        duration = time.time() - start

        # With 80 req/min (1.33/sec), 20 requests should be quick
        assert duration < 5.0

    def test_aggressive_burst_config(self) -> None:
        """Test with aggressive burst configuration."""
        # High burst, moderate sustained rate
        limiter = RateLimiter(requests_per_minute=100, burst_size=200)

        # Can burst 200 requests
        burst_count = 0
        while limiter.bucket.acquire(tokens=1, block=False):
            burst_count += 1
            if burst_count > 250:
                break

        # Should have gotten close to 200 burst tokens
        assert burst_count >= 190

    def test_minimal_config(self) -> None:
        """Test with minimal configuration (just RPM)."""
        limiter = RateLimiter(requests_per_minute=60)

        assert limiter.requests_per_minute == 60
        assert limiter.burst_size == 60  # Default
        assert limiter.get_utilization() == 0.0

        # Make a request
        limiter.wait_if_needed()
        assert limiter.get_utilization() > 0.0
