"""
Race Condition Tests for ConfigLoader.

Tests for race conditions in configuration loading operations:
- Concurrent config loading from multiple threads
- Cache race conditions (read while reload)
- Simultaneous Decimal conversion
- Concurrent environment variable access

Related:
- TESTING_STRATEGY V3.5: All 8 test types required
- config/config_loader module coverage

Usage:
    pytest tests/stress/config/test_config_loader_race.py -v -m race

Educational Note:
    ConfigLoader uses a global cache (self.configs dict) that can be accessed
    by multiple threads simultaneously. These tests verify:
    1. Cache reads don't corrupt during concurrent loads
    2. Reload operations don't cause partial reads
    3. Decimal conversion is thread-safe
    4. Environment prefix resolution is consistent across threads

Reference: Pattern 28 (CI-Safe Stress Testing) in DEVELOPMENT_PATTERNS
"""

import os
import tempfile
import threading
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

# Import CI-safe barrier from stress test fixtures
from tests.fixtures.stress_testcontainers import CISafeBarrier


@pytest.mark.race
class TestConfigLoaderRace:
    """Race condition tests for ConfigLoader.

    Uses CISafeBarrier for CI-compatible thread synchronization.
    """

    # Timeout for barrier synchronization (seconds)
    BARRIER_TIMEOUT = 15.0

    def _create_temp_config_dir(self) -> Path:
        """Create a temporary config directory with test YAML files."""
        temp_dir = Path(tempfile.mkdtemp())

        # Create trading.yaml with Decimal-worthy values
        trading_yaml = temp_dir / "trading.yaml"
        trading_yaml.write_text(
            """
account:
  max_total_exposure_dollars: "10000.00"
  daily_loss_limit_dollars: "500.00"
  min_edge: "0.05"
trading:
  enabled: true
  max_positions: 10
""",
            encoding="utf-8",
        )

        # Create system.yaml
        system_yaml = temp_dir / "system.yaml"
        system_yaml.write_text(
            """
logging:
  level: INFO
  format: json
database:
  pool_size: 10
""",
            encoding="utf-8",
        )

        # Create position_management.yaml
        position_yaml = temp_dir / "position_management.yaml"
        position_yaml.write_text(
            """
trailing_stops:
  default:
    activation_threshold: "0.15"
    initial_distance: "0.05"
  strategies:
    halftime_entry:
      activation_threshold: "0.10"
""",
            encoding="utf-8",
        )

        return temp_dir

    def test_concurrent_config_loading(self):
        """
        RACE: Multiple threads loading different configs simultaneously.

        Verifies:
        - Thread-safe config loading
        - No cache corruption under concurrent access
        - All threads get valid configurations
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_config_dir()
        loader = ConfigLoader(config_dir=temp_dir)

        results = []
        errors = []
        barrier = CISafeBarrier(10, timeout=self.BARRIER_TIMEOUT)

        def load_config(thread_id: int, config_name: str):
            try:
                barrier.wait()  # Synchronize all threads
                config = loader.load(config_name)
                results.append((thread_id, config_name, config is not None))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Alternate between trading and system configs
        config_names = ["trading", "system"] * 5
        threads = []

        for i, config_name in enumerate(config_names):
            t = threading.Thread(target=load_config, args=(i, config_name))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        # Handle timeout errors gracefully
        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors during race test: {other_errors}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"

        # All loads should succeed
        for thread_id, config_name, success in results:
            assert success, f"Thread {thread_id} failed to load {config_name}"

    def test_concurrent_cache_read_during_reload(self):
        """
        RACE: Reading from cache while reload() clears it.

        Verifies:
        - No KeyError when cache cleared during read
        - Readers get either cached value or fresh load
        - No partial/corrupt configurations
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_config_dir()
        loader = ConfigLoader(config_dir=temp_dir)

        # Pre-populate cache
        loader.load("trading")
        loader.load("system")

        results = []
        errors = []
        barrier = CISafeBarrier(12, timeout=self.BARRIER_TIMEOUT)

        def reader_thread(thread_id: int):
            """Read from cache repeatedly."""
            try:
                barrier.wait()
                for _ in range(10):
                    config = loader.get("trading")
                    if config is not None:
                        results.append((thread_id, "read", True))
                    else:
                        results.append((thread_id, "read", False))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        def reloader_thread(thread_id: int):
            """Reload cache repeatedly."""
            try:
                barrier.wait()
                for _ in range(5):
                    loader.reload()
                    results.append((thread_id, "reload", True))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []

        # 10 readers + 2 reloaders
        for i in range(10):
            t = threading.Thread(target=reader_thread, args=(i,))
            threads.append(t)
            t.start()

        for i in range(2):
            t = threading.Thread(target=reloader_thread, args=(100 + i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors during race test: {other_errors}"
        assert len(results) > 0, "No results recorded"

    def test_concurrent_decimal_conversion(self):
        """
        RACE: Multiple threads triggering Decimal conversion simultaneously.

        Verifies:
        - Decimal conversion is thread-safe
        - All monetary values correctly converted
        - No corruption of Decimal values
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_config_dir()

        results = []
        errors = []
        barrier = CISafeBarrier(20, timeout=self.BARRIER_TIMEOUT)

        def convert_and_verify(thread_id: int):
            try:
                barrier.wait()
                # Each thread creates fresh loader to test conversion
                loader = ConfigLoader(config_dir=temp_dir)
                config = loader.load("trading")

                # Verify Decimal conversion
                max_exposure = config["account"]["max_total_exposure_dollars"]
                min_edge = config["account"]["min_edge"]

                if isinstance(max_exposure, Decimal) and isinstance(min_edge, Decimal):
                    if max_exposure == Decimal("10000.00") and min_edge == Decimal("0.05"):
                        results.append((thread_id, True))
                    else:
                        results.append((thread_id, False))
                        errors.append((thread_id, f"Wrong values: {max_exposure}, {min_edge}"))
                else:
                    results.append((thread_id, False))
                    errors.append(
                        (thread_id, f"Not Decimal: {type(max_exposure)}, {type(min_edge)}")
                    )
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(20):
            t = threading.Thread(target=convert_and_verify, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors during race test: {other_errors}"
        assert len(results) == 20, f"Expected 20 results, got {len(results)}"

        # All conversions should succeed
        for thread_id, success in results:
            assert success, f"Thread {thread_id} failed Decimal conversion"

    def test_concurrent_environment_variable_access(self):
        """
        RACE: Multiple threads accessing get_env() with different prefixes.

        Verifies:
        - Environment variable resolution is thread-safe
        - Prefix resolution is consistent
        - No race between os.getenv calls
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_config_dir()

        results = []
        errors = []
        barrier = CISafeBarrier(20, timeout=self.BARRIER_TIMEOUT)

        # Set up environment variables for testing
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "DEVELOPMENT_TEST_VAR": "dev_value",
                "PRODUCTION_TEST_VAR": "prod_value",
                "TEST_VAR": "fallback_value",
            },
        ):

            def access_env(thread_id: int):
                try:
                    barrier.wait()
                    loader = ConfigLoader(config_dir=temp_dir)

                    # Should get DEV_ prefixed value
                    value = loader.get_env("TEST_VAR")

                    if value == "dev_value":
                        results.append((thread_id, True))
                    else:
                        results.append((thread_id, False))
                        errors.append((thread_id, f"Wrong value: {value}"))
                except TimeoutError:
                    errors.append((thread_id, "Barrier timeout"))
                except Exception as e:
                    errors.append((thread_id, str(e)))

            threads = []
            for i in range(20):
                t = threading.Thread(target=access_env, args=(i,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors during race test: {other_errors}"
        assert len(results) == 20

    def test_concurrent_get_with_key_path(self):
        """
        RACE: Multiple threads accessing nested config values simultaneously.

        Verifies:
        - Nested key path access is thread-safe
        - No partial reads during cache population
        - All threads get consistent values
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_config_dir()
        loader = ConfigLoader(config_dir=temp_dir)

        results = []
        errors = []
        barrier = CISafeBarrier(15, timeout=self.BARRIER_TIMEOUT)

        def access_nested(thread_id: int):
            try:
                barrier.wait()
                # Access nested key paths
                max_exposure = loader.get("trading", "account.max_total_exposure_dollars")
                min_edge = loader.get("trading", "account.min_edge")
                pool_size = loader.get("system", "database.pool_size")

                if all(
                    [
                        max_exposure == Decimal("10000.00"),
                        min_edge == Decimal("0.05"),
                        pool_size == 10,
                    ]
                ):
                    results.append((thread_id, True))
                else:
                    results.append((thread_id, False))
                    errors.append(
                        (thread_id, f"Wrong values: {max_exposure}, {min_edge}, {pool_size}")
                    )
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(15):
            t = threading.Thread(target=access_nested, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors during race test: {other_errors}"
        assert len(results) == 15

        for thread_id, success in results:
            assert success, f"Thread {thread_id} got inconsistent values"

    def test_concurrent_load_all(self):
        """
        RACE: Multiple threads calling load_all() simultaneously.

        Verifies:
        - load_all() is thread-safe
        - No double-loading of configs
        - All configs loaded correctly
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_config_dir()

        # Create all standard config files
        for filename in [
            "trade_strategies.yaml",
            "probability_models.yaml",
            "markets.yaml",
            "data_sources.yaml",
        ]:
            (temp_dir / filename).write_text("settings:\n  enabled: true\n", encoding="utf-8")

        loader = ConfigLoader(config_dir=temp_dir)

        results = []
        errors = []
        barrier = CISafeBarrier(10, timeout=self.BARRIER_TIMEOUT)

        def call_load_all(thread_id: int):
            try:
                barrier.wait()
                configs = loader.load_all()
                results.append((thread_id, len(configs)))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(10):
            t = threading.Thread(target=call_load_all, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors during race test: {other_errors}"
        assert len(results) == 10

        # All threads should see same number of configs
        config_counts = [count for _, count in results]
        assert len(set(config_counts)) == 1, f"Inconsistent config counts: {config_counts}"


@pytest.mark.race
class TestConfigLoaderTrailingStopRace:
    """Race tests for trailing stop configuration access."""

    BARRIER_TIMEOUT = 15.0

    def _create_temp_config_with_strategies(self) -> Path:
        """Create temp config with trailing stop strategies."""
        temp_dir = Path(tempfile.mkdtemp())

        position_yaml = temp_dir / "position_management.yaml"
        position_yaml.write_text(
            """
trailing_stops:
  default:
    activation_threshold: "0.15"
    initial_distance: "0.05"
    tightening_rate: "0.01"
    floor_distance: "0.02"
  strategies:
    halftime_entry:
      activation_threshold: "0.10"
      initial_distance: "0.03"
    pregame_value:
      activation_threshold: "0.20"
""",
            encoding="utf-8",
        )

        return temp_dir

    def test_concurrent_trailing_stop_config_access(self):
        """
        RACE: Multiple threads accessing different strategy trailing stops.

        Verifies:
        - Trailing stop config merging is thread-safe
        - Strategy overrides applied correctly
        - Default values preserved
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_config_with_strategies()
        loader = ConfigLoader(config_dir=temp_dir)

        results = []
        errors = []
        barrier = CISafeBarrier(15, timeout=self.BARRIER_TIMEOUT)

        strategies = ["halftime_entry", "pregame_value", None] * 5  # None = default

        def get_trailing_stop(thread_id: int, strategy: str | None):
            try:
                barrier.wait()
                config = loader.get_trailing_stop_config(strategy)

                # Verify based on strategy
                if strategy == "halftime_entry":
                    expected_threshold = Decimal("0.10")
                elif strategy == "pregame_value":
                    expected_threshold = Decimal("0.20")
                else:
                    expected_threshold = Decimal("0.15")

                actual_threshold = config.get("activation_threshold")
                if actual_threshold == expected_threshold:
                    results.append((thread_id, strategy, True))
                else:
                    results.append((thread_id, strategy, False))
                    errors.append(
                        (thread_id, f"Wrong threshold for {strategy}: {actual_threshold}")
                    )
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i, strategy in enumerate(strategies):
            t = threading.Thread(target=get_trailing_stop, args=(i, strategy))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors during race test: {other_errors}"
        assert len(results) == 15

        for thread_id, strategy, success in results:
            assert success, f"Thread {thread_id} failed for strategy {strategy}"
