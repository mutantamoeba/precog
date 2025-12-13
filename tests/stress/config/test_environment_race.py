"""
Race condition tests for environment configuration.

Tests for race conditions between concurrent environment operations.

Reference: TESTING_STRATEGY_V3.2.md Section "Race Tests"
"""

import threading

import pytest

from precog.config.environment import (
    AppEnvironment,
    CombinationSafety,
    EnvironmentConfig,
    MarketMode,
    get_app_environment,
    get_market_mode,
)


@pytest.mark.race
class TestEnvironmentDetectionRace:
    """Race condition tests for environment detection."""

    def test_concurrent_env_detection_same_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test concurrent environment detection returns consistent results."""
        monkeypatch.setenv("PRECOG_ENV", "staging")

        results = []
        errors = []
        lock = threading.Lock()

        def detect() -> None:
            try:
                env = get_app_environment()
                with lock:
                    results.append(env)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=detect) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        assert all(r == AppEnvironment.STAGING for r in results)

    def test_concurrent_market_mode_detection_same_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test concurrent market mode detection returns consistent results."""
        monkeypatch.setenv("KALSHI_MODE", "live")

        results = []
        errors = []
        lock = threading.Lock()

        def detect() -> None:
            try:
                mode = get_market_mode("kalshi")
                with lock:
                    results.append(mode)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=detect) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        assert all(r == MarketMode.LIVE for r in results)


@pytest.mark.race
class TestEnvironmentConfigRace:
    """Race condition tests for EnvironmentConfig operations."""

    def test_concurrent_safety_check_no_race(self) -> None:
        """Test concurrent safety checks don't have race conditions."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_dev",
        )

        results = []
        errors = []
        lock = threading.Lock()

        def check_safety() -> None:
            try:
                safety = config.get_combination_safety()
                with lock:
                    results.append(safety)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=check_safety) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        assert all(r == CombinationSafety.ALLOWED for r in results)

    def test_concurrent_validation_no_race(self) -> None:
        """Test concurrent validation calls don't have race conditions."""
        config = EnvironmentConfig(
            app_env=AppEnvironment.DEVELOPMENT,
            kalshi_mode=MarketMode.DEMO,
            database_name="precog_dev",
        )

        errors = []
        lock = threading.Lock()

        def validate() -> None:
            try:
                config.validate()
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=validate) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"


@pytest.mark.race
class TestAppEnvironmentRace:
    """Race condition tests for AppEnvironment enum."""

    def test_concurrent_from_string_no_race(self) -> None:
        """Test concurrent from_string parsing doesn't have race conditions."""
        aliases = ["dev", "development", "test", "testing", "staging", "prod"]

        results = []
        errors = []
        lock = threading.Lock()

        def parse_all() -> None:
            try:
                for alias in aliases:
                    result = AppEnvironment.from_string(alias)
                    with lock:
                        results.append((alias, result))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=parse_all) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        # 50 threads * 6 aliases each
        assert len(results) == 300

    def test_concurrent_property_access_no_race(self) -> None:
        """Test concurrent property access doesn't have race conditions."""
        env = AppEnvironment.PRODUCTION

        results = []
        errors = []
        lock = threading.Lock()

        def access_properties() -> None:
            try:
                for _ in range(100):
                    db_name = env.database_name
                    is_prod = env.is_production
                    with lock:
                        results.append((db_name, is_prod))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=access_properties) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 2000
        # All should return same values
        for db_name, is_prod in results:
            assert db_name == "precog_prod"
            assert is_prod is True


@pytest.mark.race
class TestMarketModeRace:
    """Race condition tests for MarketMode enum."""

    def test_concurrent_from_string_no_race(self) -> None:
        """Test concurrent from_string parsing doesn't have race conditions."""
        aliases = ["demo", "sandbox", "live", "prod"]

        results = []
        errors = []
        lock = threading.Lock()

        def parse_all() -> None:
            try:
                for alias in aliases:
                    result = MarketMode.from_string(alias)
                    with lock:
                        results.append((alias, result))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=parse_all) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        # 50 threads * 4 aliases each
        assert len(results) == 200

    def test_concurrent_uses_real_money_no_race(self) -> None:
        """Test concurrent uses_real_money access doesn't have race conditions."""
        results = []
        errors = []
        lock = threading.Lock()

        def check_real_money() -> None:
            try:
                for mode in MarketMode:
                    real_money = mode.uses_real_money
                    with lock:
                        results.append((mode, real_money))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=check_real_money) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        # 100 threads * 2 modes each (DEMO, LIVE)
        assert len(results) == 200
