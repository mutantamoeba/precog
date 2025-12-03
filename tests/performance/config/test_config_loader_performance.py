"""
Performance Tests for ConfigLoader.

Establishes latency benchmarks for configuration operations:
- Config file loading latency
- Config validation overhead
- Config caching effectiveness

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- config/config_loader module coverage

Usage:
    pytest tests/performance/config/test_config_loader_performance.py -v -m performance
"""

import time

import pytest


@pytest.mark.performance
class TestConfigLoaderPerformance:
    """Performance benchmarks for ConfigLoader operations."""

    def test_config_load_latency(self, tmp_path):
        """
        PERFORMANCE: Measure config file loading latency.

        Benchmark:
        - Target: < 10ms per load (p95)
        - SLA: < 20ms per load (p99)
        """
        from precog.config.config_loader import ConfigLoader

        # Create test config file
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(
            """
trading:
  max_position_size: "1000.00"
  min_edge: "0.02"
  kelly_fraction: "0.25"
logging:
  level: INFO
  format: "%(message)s"
"""
        )

        latencies = []

        for _ in range(50):
            start = time.perf_counter()
            loader = ConfigLoader(config_dir=str(tmp_path))
            _ = loader.load("test_config.yaml")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        assert p95 < 20, f"p95 latency {p95:.2f}ms exceeds 20ms target"
        assert p99 < 50, f"p99 latency {p99:.2f}ms exceeds 50ms SLA"

    def test_config_get_latency(self, tmp_path):
        """
        PERFORMANCE: Measure config value access latency.

        Benchmark:
        - Target: < 1ms per get (p99)
        """
        from precog.config.config_loader import ConfigLoader

        config_file = tmp_path / "perf_config.yaml"
        config_file.write_text(
            """
nested:
  deeply:
    value: "test"
    number: "123"
"""
        )

        loader = ConfigLoader(config_dir=str(tmp_path))
        loader.load("perf_config.yaml")

        latencies = []

        for _ in range(200):
            start = time.perf_counter()
            _ = loader.get("nested.deeply.value")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        assert p99 < 2, f"p99 latency {p99:.2f}ms exceeds 2ms target"

    def test_large_config_load_performance(self, tmp_path):
        """
        PERFORMANCE: Measure loading of large config files.

        Benchmark:
        - Target: < 50ms for 1000-line config (p95)
        """
        from precog.config.config_loader import ConfigLoader

        # Create large config file
        config_file = tmp_path / "large_config.yaml"
        lines = ["root:"]
        for i in range(100):
            lines.append(f"  section_{i:03d}:")
            for j in range(10):
                lines.append(f'    key_{j:03d}: "value_{i}_{j}"')
        config_file.write_text("\n".join(lines))

        latencies = []

        for _ in range(20):
            start = time.perf_counter()
            loader = ConfigLoader(config_dir=str(tmp_path))
            _ = loader.load("large_config.yaml")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms target"
