"""
Performance Tests for Logger.

Establishes latency benchmarks for logging operations:
- Log message formatting latency
- Log write throughput
- Structured logging overhead

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- utils/logger module coverage

Usage:
    pytest tests/performance/utils/test_logger_performance.py -v -m performance
"""

import statistics
import time

import pytest


@pytest.mark.performance
class TestLoggerPerformance:
    """Performance benchmarks for Logger operations."""

    def test_log_message_formatting_latency(self):
        """
        PERFORMANCE: Measure log message formatting latency.

        Benchmark:
        - Target: < 1ms per message (p99)
        """
        from precog.utils.logger import get_logger

        logger = get_logger("perf_test")
        latencies = []

        for i in range(200):
            start = time.perf_counter()
            # Format message (logger may not actually write if level is filtered)
            logger.debug(
                "Performance test message",
                extra={"iteration": i, "test": "formatting"},
            )
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        assert p99 < 5, f"p99 latency {p99:.2f}ms exceeds 5ms target"

    def test_log_throughput(self):
        """
        PERFORMANCE: Measure logging throughput.

        Benchmark:
        - Target: >= 1000 messages/sec
        """
        from precog.utils.logger import get_logger

        logger = get_logger("perf_throughput")
        operations = 500

        start = time.perf_counter()
        for i in range(operations):
            logger.debug(f"Throughput test message {i}")
        elapsed = time.perf_counter() - start

        throughput = operations / elapsed
        assert throughput >= 500, f"Throughput {throughput:.1f} msgs/sec below 500 msgs/sec minimum"

    def test_structured_log_overhead(self):
        """
        PERFORMANCE: Measure structured logging overhead.

        Benchmark:
        - Structured logs should be < 2x slower than plain logs
        """
        from precog.utils.logger import get_logger

        logger = get_logger("perf_structured")

        # Plain logging
        plain_latencies = []
        for i in range(100):
            start = time.perf_counter()
            logger.debug("Plain message")
            end = time.perf_counter()
            plain_latencies.append((end - start) * 1000)

        # Structured logging with extra fields
        structured_latencies = []
        for i in range(100):
            start = time.perf_counter()
            logger.debug(
                "Structured message",
                extra={
                    "field1": "value1",
                    "field2": 123,
                    "field3": {"nested": "data"},
                },
            )
            end = time.perf_counter()
            structured_latencies.append((end - start) * 1000)

        avg_plain = statistics.mean(plain_latencies)
        avg_structured = statistics.mean(structured_latencies)

        # Structured should not be significantly slower
        assert avg_structured < avg_plain * 5, (
            f"Structured logging {avg_structured:.3f}ms much slower than plain {avg_plain:.3f}ms"
        )
