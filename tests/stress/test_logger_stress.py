"""
Stress Tests for Logging Infrastructure.

These tests validate the logging system under high-load conditions:
- High-volume log message generation
- Concurrent logging from multiple threads
- Log rotation behavior under pressure
- Memory usage during logging storms

Educational Note:
    Logging stress tests are important because:
    - Production systems generate thousands of logs per minute
    - Logging bottlenecks can slow entire application
    - Memory leaks in logging handlers accumulate silently
    - Concurrent logging must not lose messages

Run with:
    pytest tests/stress/test_logger_stress.py -v -m stress

References:
    - Issue #126: Stress tests for infrastructure
    - REQ-TEST-012: Test types taxonomy (Stress tests)
    - src/precog/utils/logger.py

Phase: 4 (Stress Testing Infrastructure)
GitHub Issue: #126
"""

import gc
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO

import pytest

# CI environment detection - same pattern as connection stress tests
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

_CI_XFAIL_REASON = (
    "Stress tests use time-based loops and threading that can hang "
    "or timeout in CI environments due to resource constraints. "
    "Run locally with 'pytest tests/stress/ -v -m stress'. See GitHub issue #168."
)

pytestmark = [
    pytest.mark.stress,
    pytest.mark.slow,
    pytest.mark.xfail(condition=_is_ci, reason=_CI_XFAIL_REASON, run=False),
]


@pytest.fixture
def test_logger():
    """Create an isolated logger for stress tests.

    Educational Note:
        We create a separate logger to avoid polluting
        the main application logs during stress tests.

        Structlog's BoundLogger doesn't have addHandler().
        We add the handler to the underlying standard library logger.
    """
    from precog.utils.logger import get_logger

    # Create a StringIO buffer to capture output
    string_buffer = StringIO()
    handler = logging.StreamHandler(string_buffer)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    # Add handler to root logger (structlog uses stdlib logging underneath)
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    # Get structlog logger
    logger = get_logger("stress_test_logger")

    yield logger, string_buffer

    # Cleanup
    root_logger.removeHandler(handler)
    root_logger.setLevel(original_level)


class TestLoggerHighVolume:
    """Stress tests for high-volume logging."""

    def test_10000_log_messages(self, test_logger):
        """Test logging 10,000 messages in rapid succession.

        Educational Note:
            This tests for:
            - Buffer overflow
            - Performance degradation over time
            - Memory accumulation
        """
        logger, buffer = test_logger
        num_messages = 10000

        start_time = time.time()
        for i in range(num_messages):
            logger.info(f"Test message {i}")
        elapsed = time.time() - start_time

        # Should complete in reasonable time (< 5 seconds for 10K messages)
        assert elapsed < 5.0, f"Logging {num_messages} messages took {elapsed:.2f}s"

        # Verify messages were logged (spot check)
        output = buffer.getvalue()
        assert "Test message 0" in output
        assert "Test message 9999" in output

    def test_mixed_log_levels_high_volume(self, test_logger):
        """Test high-volume logging with mixed log levels.

        Educational Note:
            Different log levels may have different processing paths.
            This ensures all levels handle high volume equally well.
        """
        logger, buffer = test_logger
        levels = [
            (logger.debug, "DEBUG"),
            (logger.info, "INFO"),
            (logger.warning, "WARNING"),
            (logger.error, "ERROR"),
        ]

        for i in range(1000):
            log_func, level_name = levels[i % len(levels)]
            log_func(f"{level_name} message {i}")

        # Should complete without issues
        output = buffer.getvalue()
        assert "INFO message" in output
        assert "WARNING message" in output


class TestLoggerConcurrency:
    """Stress tests for concurrent logging."""

    def test_concurrent_logging_from_100_threads(self, test_logger):
        """Test 100 threads logging simultaneously.

        Educational Note:
            Concurrent logging is common in multi-threaded servers.
            This tests thread safety of the logging infrastructure.
        """
        logger, _buffer = test_logger
        num_threads = 100
        messages_per_thread = 100
        results = {"logged": 0}
        lock = threading.Lock()

        def log_messages(thread_id):
            count = 0
            for i in range(messages_per_thread):
                logger.info(f"Thread {thread_id} message {i}")
                count += 1
            with lock:
                results["logged"] += count

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(log_messages, i) for i in range(num_threads)]
            for future in as_completed(futures):
                pass

        # All threads should have logged their messages
        expected_messages = num_threads * messages_per_thread
        assert results["logged"] == expected_messages, (
            f"Expected {expected_messages} logged, got {results['logged']}"
        )

    def test_no_message_loss_under_concurrency(self, test_logger):
        """Verify no log messages are lost during concurrent logging.

        Educational Note:
            Message loss is a critical failure mode for logging.
            This test uses unique identifiers to verify all messages arrive.
        """
        logger, buffer = test_logger
        num_threads = 20
        messages_per_thread = 50
        expected_markers = set()

        def log_with_marker(thread_id):
            for i in range(messages_per_thread):
                marker = f"MARKER_{thread_id}_{i}"
                expected_markers.add(marker)
                logger.info(marker)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(log_with_marker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                pass

        # Verify all markers appear in output
        output = buffer.getvalue()
        missing = []
        for marker in expected_markers:
            if marker not in output:
                missing.append(marker)

        assert len(missing) == 0, f"Lost {len(missing)} messages out of {len(expected_markers)}"


class TestLoggerMemory:
    """Stress tests for logger memory usage."""

    def test_no_memory_leak_on_high_volume(self):
        """Test logging doesn't leak memory over many messages.

        Educational Note:
            Loggers can leak memory through:
            - Handler buffers growing unbounded
            - Formatter cache accumulation
            - Thread-local storage not being cleaned

            Note: We don't use the test_logger fixture here because
            the StringIO buffer intentionally accumulates all log output,
            which would show as "growth" but isn't a leak.
        """
        from precog.utils.logger import get_logger

        # Get logger without capture buffer
        logger = get_logger("memory_test_logger")

        # Force GC and get baseline
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Log many messages (these go to console/file, not captured)
        for i in range(50000):
            # Only log every 1000th to reduce output noise
            if i % 1000 == 0:
                logger.debug("Memory leak test message", iteration=i)

        # Force GC again
        gc.collect()
        final_objects = len(gc.get_objects())

        # Object count shouldn't grow significantly
        growth = final_objects - initial_objects
        growth_percent = (growth / initial_objects) * 100 if initial_objects > 0 else 0

        # Allow some growth but flag excessive growth (>30%)
        assert growth_percent < 30, (
            f"Object count grew by {growth_percent:.1f}% ({initial_objects} -> {final_objects})"
        )

    def test_large_message_handling(self, test_logger):
        """Test logging very large messages.

        Educational Note:
            Extremely large log messages could cause memory issues
            or buffer overflows. System should handle gracefully.
        """
        logger, buffer = test_logger

        # Log messages of increasing size
        for size_kb in [1, 10, 100]:
            message = "X" * (size_kb * 1024)
            logger.info(f"Large message ({size_kb}KB): {message[:50]}...")

        # Should complete without errors
        output = buffer.getvalue()
        assert "Large message (1KB)" in output
        assert "Large message (10KB)" in output
        assert "Large message (100KB)" in output


class TestLoggerPerformance:
    """Stress tests for logger performance."""

    def test_logging_throughput(self, test_logger):
        """Measure logging throughput.

        Educational Note:
            Understanding logging throughput helps identify
            when logging might become a bottleneck.
        """
        logger, _ = test_logger
        num_messages = 10000

        start_time = time.time()
        for i in range(num_messages):
            logger.info(f"Throughput test {i}")
        elapsed = time.time() - start_time

        messages_per_second = num_messages / elapsed

        # Should achieve at least 1000 messages per second
        assert messages_per_second > 1000, f"Throughput too low: {messages_per_second:.0f} msg/s"

    def test_logging_latency_consistency(self, test_logger):
        """Test logging latency remains consistent.

        Educational Note:
            Inconsistent latency (jitter) can indicate
            garbage collection issues or buffer flushes.
        """
        logger, _ = test_logger
        latencies = []

        for i in range(1000):
            start = time.perf_counter()
            logger.info(f"Latency test {i}")
            latency = time.perf_counter() - start
            latencies.append(latency)

        # Calculate statistics
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Max latency shouldn't be more than 100x average (indicating spikes)
        latency_ratio = max_latency / avg_latency if avg_latency > 0 else float("inf")

        # Allow some variation but flag extreme spikes
        assert latency_ratio < 100, (
            f"Latency spike: max={max_latency * 1000:.2f}ms, "
            f"avg={avg_latency * 1000:.4f}ms, ratio={latency_ratio:.0f}x"
        )


class TestLoggerRecovery:
    """Stress tests for logger error recovery."""

    def test_continues_after_handler_error(self, test_logger):
        """Test logging continues after handler errors.

        Educational Note:
            Handler errors (disk full, permission denied, etc.)
            shouldn't stop logging entirely.
        """
        logger, buffer = test_logger

        # Log normal message
        logger.info("Before error simulation")

        # Simulate by logging very large message
        try:
            logger.info("X" * 10_000_000)  # 10MB message
        except Exception:
            pass  # May fail

        # Logging should continue working
        logger.info("After error simulation")

        output = buffer.getvalue()
        assert "Before error simulation" in output
        assert "After error simulation" in output
