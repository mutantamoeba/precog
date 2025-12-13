"""
Performance tests for environment configuration.

Validates latency and throughput requirements for configuration operations.

Reference: TESTING_STRATEGY_V3.2.md Section "Performance Tests"
"""

import time

import pytest

from precog.config.environment import (
    AppEnvironment,
    EnvironmentConfig,
    MarketMode,
    get_app_environment,
    get_market_mode,
    load_environment_config,
)


@pytest.mark.performance
class TestAppEnvironmentPerformance:
    """Performance benchmarks for AppEnvironment operations."""

    def test_from_string_latency(self) -> None:
        """Test that from_string parsing is fast (<0.1ms)."""
        aliases = ["dev", "development", "test", "staging", "prod", "production"]

        latencies = []
        for _ in range(100):
            for alias in aliases:
                start = time.perf_counter()
                AppEnvironment.from_string(alias)
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Should be very fast - enum lookup
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"
        assert max_latency < 0.001, f"Max latency {max_latency * 1000:.3f}ms too high"

    def test_property_access_latency(self) -> None:
        """Test that property access is fast."""
        env = AppEnvironment.DEVELOPMENT

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            _ = env.database_name
            _ = env.is_production
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_from_string_throughput(self) -> None:
        """Test throughput of from_string operations."""
        start = time.perf_counter()
        count = 0
        for _ in range(10000):
            AppEnvironment.from_string("development")
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 100k ops/sec
        assert throughput > 100000, f"Throughput {throughput:.0f} ops/sec too low"


@pytest.mark.performance
class TestMarketModePerformance:
    """Performance benchmarks for MarketMode operations."""

    def test_from_string_latency(self) -> None:
        """Test that from_string parsing is fast (<0.1ms)."""
        aliases = ["demo", "live", "sandbox", "prod"]

        latencies = []
        for _ in range(100):
            for alias in aliases:
                start = time.perf_counter()
                MarketMode.from_string(alias)
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_property_access_latency(self) -> None:
        """Test that uses_real_money access is fast."""
        mode = MarketMode.DEMO

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            _ = mode.uses_real_money
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"


@pytest.mark.performance
class TestEnvironmentConfigPerformance:
    """Performance benchmarks for EnvironmentConfig operations."""

    def test_config_creation_latency(self) -> None:
        """Test that config creation is fast."""
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            EnvironmentConfig(
                app_env=AppEnvironment.DEVELOPMENT,
                kalshi_mode=MarketMode.DEMO,
                database_name="precog_dev",
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_get_combination_safety_latency(self) -> None:
        """Test that safety calculation is fast."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_dev",
        )

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            config.get_combination_safety()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_validation_latency(self) -> None:
        """Test that validation is fast for allowed combinations."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_dev",
        )

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            config.validate()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Validation may log, so allow slightly more time
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"


@pytest.mark.performance
class TestEnvironmentDetectionPerformance:
    """Performance benchmarks for environment detection functions."""

    def test_get_app_environment_latency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment detection is fast."""
        monkeypatch.setenv("PRECOG_ENV", "development")

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            get_app_environment()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Env lookup may be slightly slower
        assert avg_latency < 0.0005, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_get_market_mode_latency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that market mode detection is fast."""
        monkeypatch.setenv("KALSHI_MODE", "demo")

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            get_market_mode("kalshi")
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0005, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_load_environment_config_latency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that full config loading is reasonably fast."""
        monkeypatch.setenv("PRECOG_ENV", "development")
        monkeypatch.setenv("KALSHI_MODE", "demo")
        monkeypatch.delenv("DB_NAME", raising=False)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            load_environment_config(validate=False)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Full config loading should still be under 1ms
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"
