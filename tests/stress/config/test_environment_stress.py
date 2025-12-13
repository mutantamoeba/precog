"""
Stress tests for environment configuration.

Tests high-volume concurrent access patterns to validate thread safety
and configuration loading behavior under load.

Reference: TESTING_STRATEGY_V3.2.md Section "Stress Tests"
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from precog.config.environment import (
    AppEnvironment,
    CombinationSafety,
    EnvironmentConfig,
    MarketMode,
    get_app_environment,
    get_market_mode,
    load_environment_config,
)


@pytest.mark.stress
class TestEnvironmentConfigStress:
    """Stress tests for concurrent environment configuration access."""

    def test_concurrent_environment_detection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify thread-safe environment detection under concurrent load."""
        monkeypatch.setenv("PRECOG_ENV", "development")

        results = []
        lock = threading.Lock()

        def detect_env() -> AppEnvironment:
            env = get_app_environment()
            with lock:
                results.append(env)
            return env

        # Run 50 threads concurrently
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(detect_env) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        # All should detect the same environment
        assert len(results) == 100
        assert all(r == AppEnvironment.DEVELOPMENT for r in results)

    def test_concurrent_market_mode_detection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify thread-safe market mode detection under concurrent load."""
        monkeypatch.setenv("KALSHI_MODE", "demo")

        results = []
        lock = threading.Lock()

        def detect_mode() -> MarketMode:
            mode = get_market_mode("kalshi")
            with lock:
                results.append(mode)
            return mode

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(detect_mode) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 100
        assert all(r == MarketMode.DEMO for r in results)

    def test_concurrent_config_loading(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test concurrent loading of environment configuration."""
        monkeypatch.setenv("PRECOG_ENV", "development")
        monkeypatch.setenv("KALSHI_MODE", "demo")
        monkeypatch.delenv("DB_NAME", raising=False)

        configs = []
        lock = threading.Lock()

        def load_config() -> EnvironmentConfig:
            config = load_environment_config(validate=True)
            with lock:
                configs.append(config)
            return config

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(load_config) for _ in range(60)]
            for future in as_completed(futures):
                future.result()

        assert len(configs) == 60
        # All configs should have same values
        for config in configs:
            assert config.app_env == AppEnvironment.DEVELOPMENT
            assert config.kalshi_mode == MarketMode.DEMO

    def test_sustained_config_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test sustained validation calls don't degrade."""
        monkeypatch.setenv("PRECOG_ENV", "development")
        monkeypatch.setenv("KALSHI_MODE", "demo")

        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_dev",
        )

        # Validate 1000 times
        for _ in range(1000):
            config.validate()
            safety = config.get_combination_safety()
            assert safety == CombinationSafety.ALLOWED


@pytest.mark.stress
class TestAppEnvironmentStress:
    """Stress tests for AppEnvironment enum operations."""

    def test_concurrent_from_string_parsing(self) -> None:
        """Test concurrent parsing of environment strings."""
        aliases = ["dev", "development", "test", "staging", "prod", "production"]
        results = []
        lock = threading.Lock()

        def parse_many() -> None:
            for alias in aliases * 10:
                result = AppEnvironment.from_string(alias)
                with lock:
                    results.append((alias, result))

        threads = [threading.Thread(target=parse_many) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be valid
        assert len(results) == 20 * 60  # 20 threads * 6 aliases * 10 iterations
        for alias, result in results:
            assert isinstance(result, AppEnvironment)

    def test_rapid_property_access(self) -> None:
        """Test rapid access to enum properties."""
        envs = list(AppEnvironment)

        for _ in range(1000):
            for env in envs:
                _ = env.database_name
                _ = env.is_production
                _ = env.value


@pytest.mark.stress
class TestMarketModeStress:
    """Stress tests for MarketMode enum operations."""

    def test_concurrent_from_string_parsing(self) -> None:
        """Test concurrent parsing of market mode strings."""
        aliases = ["demo", "sandbox", "test", "live", "prod", "production"]
        results = []
        lock = threading.Lock()

        def parse_many() -> None:
            for alias in aliases * 10:
                result = MarketMode.from_string(alias)
                with lock:
                    results.append((alias, result))

        threads = [threading.Thread(target=parse_many) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20 * 60
        for alias, result in results:
            assert isinstance(result, MarketMode)

    def test_rapid_property_access(self) -> None:
        """Test rapid access to mode properties."""
        modes = list(MarketMode)

        for _ in range(1000):
            for mode in modes:
                _ = mode.uses_real_money
                _ = mode.value
