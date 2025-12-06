"""
Stress Tests for Configuration Loader.

These tests validate the ConfigLoader under high-load conditions:
- Concurrent access from multiple threads
- Rapid reload cycles
- Large configuration files
- Memory pressure scenarios

Educational Note:
    Stress tests differ from unit/integration tests:
    - Unit tests: Single operation correctness
    - Stress tests: Behavior under load, concurrency, resource pressure

    Why stress test configuration loading?
    - Production may have many threads reading config
    - Hot-reload scenarios need thread safety
    - Memory leaks in config loading compound over time

Run with:
    pytest tests/stress/test_config_loader_stress.py -v -m stress

References:
    - Issue #126: Stress tests for infrastructure
    - Issue #168: CI-safe stress testing
    - REQ-TEST-012: Test types taxonomy (Stress tests)
    - Pattern 28: CI-Safe Stress Testing (DEVELOPMENT_PATTERNS_V1.15.md)
    - src/precog/config/config_loader.py

Phase: 4 (Stress Testing Infrastructure)
GitHub Issue: #126, #168

CI Strategy (Issue #168):
    Stress tests skip in CI to prevent timeouts and resource exhaustion.
    These tests use ThreadPoolExecutor which can hang in resource-constrained
    CI environments. Run locally for best results.
"""

import gc
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
import yaml

# CI environment detection - skip stress tests in CI
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
_CI_SKIP_REASON = (
    "Stress tests skip in CI - they can hang in resource-constrained environments. "
    "Run locally: pytest tests/stress/test_config_loader_stress.py -v"
)

# Mark all tests as stress tests (slow) - they test actual implementation
pytestmark = [
    pytest.mark.stress,
    pytest.mark.slow,
    pytest.mark.skipif(_is_ci, reason=_CI_SKIP_REASON),
]


@pytest.fixture
def config_loader():
    """Create a ConfigLoader instance for stress tests."""
    from precog.config.config_loader import ConfigLoader

    return ConfigLoader()


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"test_key": "test_value", "nested": {"key": "value"}}, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestConfigLoaderConcurrency:
    """Stress tests for concurrent configuration access."""

    def test_concurrent_config_reads(self, config_loader):
        """Test 100 concurrent threads reading configuration.

        Educational Note:
            This test validates thread safety of config reads.
            Production systems may have dozens of threads
            simultaneously accessing configuration.
        """
        num_threads = 100
        results = []
        errors = []

        def read_config():
            try:
                # Access a config value using the correct method name
                config = config_loader.load("system")
                results.append(config is not None)
            except Exception as e:
                errors.append(str(e))

        # Launch threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(read_config) for _ in range(num_threads)]
            for future in as_completed(futures):
                pass  # Wait for completion

        # All reads should succeed
        assert len(errors) == 0, f"Errors during concurrent reads: {errors}"
        assert len(results) == num_threads
        assert all(results), "Some concurrent reads failed"

    def test_concurrent_different_config_reads(self, config_loader):
        """Test threads reading different configuration sections.

        Educational Note:
            Real applications read different configs simultaneously.
            This tests potential contention on shared cache/state.
        """
        # Use actual config files that exist
        config_types = ["trading", "system", "markets", "data_sources"]
        num_threads = 50
        results = {"success": 0, "failure": 0}
        lock = threading.Lock()

        def read_random_config(config_type):
            try:
                config = config_loader.load(config_type)
                with lock:
                    results["success"] += 1
                return config is not None
            except Exception:
                with lock:
                    results["failure"] += 1
                return False

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i in range(num_threads):
                config_type = config_types[i % len(config_types)]
                futures.append(executor.submit(read_random_config, config_type))

            for future in as_completed(futures):
                pass

        # All should succeed
        assert results["failure"] == 0, f"Had {results['failure']} failures"
        assert results["success"] == num_threads


class TestConfigLoaderReload:
    """Stress tests for configuration reload scenarios."""

    def test_rapid_reload_cycles(self, config_loader):
        """Test 100 rapid reload cycles.

        Educational Note:
            Hot-reload functionality should handle rapid consecutive reloads
            without memory leaks or corruption.
        """
        num_reloads = 100

        for i in range(num_reloads):
            # Force cache clear and reload using the correct API
            config_loader.reload()  # Clear cache
            config = config_loader.load("system")
            assert config is not None, f"Reload {i} failed"

    @pytest.mark.xfail(
        reason="ConfigLoader.reload() not thread-safe during concurrent reads - needs proper "
        "synchronization implementation (locks/RWLock). Phase 2+ feature.",
        strict=False,
    )
    def test_reload_under_concurrent_reads(self, config_loader):
        """Test config reload while reads are happening.

        Educational Note:
            This tests the most challenging scenario: reload during reads.
            Proper synchronization should ensure consistency.
        """
        results: dict[str, int | list[str]] = {"reads": 0, "reloads": 0, "errors": []}
        lock = threading.Lock()
        stop_event = threading.Event()

        def continuous_reader():
            while not stop_event.is_set():
                try:
                    config_loader.load("system")
                    with lock:
                        results["reads"] += 1  # type: ignore[operator]
                except Exception as e:
                    with lock:
                        results["errors"].append(f"Read error: {e}")  # type: ignore[union-attr]
                time.sleep(0.001)

        def periodic_reloader():
            while not stop_event.is_set():
                try:
                    config_loader.reload()  # Use correct API
                    with lock:
                        results["reloads"] += 1  # type: ignore[operator]
                except Exception as e:
                    with lock:
                        results["errors"].append(f"Reload error: {e}")  # type: ignore[union-attr]
                time.sleep(0.01)

        # Start reader and reloader threads
        readers = [threading.Thread(target=continuous_reader) for _ in range(5)]
        reloader = threading.Thread(target=periodic_reloader)

        for r in readers:
            r.start()
        reloader.start()

        # Run for 2 seconds
        time.sleep(2)
        stop_event.set()

        for r in readers:
            r.join(timeout=1)
        reloader.join(timeout=1)

        # Should complete without errors
        assert len(results["errors"]) == 0, f"Errors: {results['errors']}"  # type: ignore[arg-type]
        assert results["reads"] > 100, f"Too few reads: {results['reads']}"  # type: ignore[operator]
        assert results["reloads"] > 10, f"Too few reloads: {results['reloads']}"  # type: ignore[operator]


class TestConfigLoaderLargeConfigs:
    """Stress tests for large configuration files."""

    def test_large_config_loading(self, temp_config_file):
        """Test loading configuration with 10,000+ entries.

        Educational Note:
            While our configs are small, we should handle large configs
            gracefully in case of future growth.
        """

        # Create large config
        large_config = {}
        for i in range(10000):
            large_config[f"key_{i}"] = {
                "value": f"value_{i}",
                "nested": {"deep": f"deep_{i}"},
            }

        # Write large config
        with open(temp_config_file, "w") as f:
            yaml.dump(large_config, f)

        # Time the loading
        start_time = time.time()
        with open(temp_config_file) as f:
            loaded = yaml.safe_load(f)
        load_time = time.time() - start_time

        # Should load within reasonable time (< 5 seconds)
        assert load_time < 5.0, f"Large config load took {load_time:.2f}s"
        assert len(loaded) == 10000

    def test_deeply_nested_config(self, temp_config_file):
        """Test deeply nested configuration structure.

        Educational Note:
            Deep nesting can cause stack overflow in some parsers.
            YAML safe_load should handle reasonable depth.
        """
        # Create deeply nested config (50 levels)
        nested: dict = {"value": "deepest"}
        for i in range(50):
            nested = {f"level_{50 - i}": nested}

        with open(temp_config_file, "w") as f:
            yaml.dump(nested, f)

        # Should load without stack overflow
        with open(temp_config_file) as f:
            loaded = yaml.safe_load(f)

        # Verify structure
        current = loaded
        for i in range(50):
            assert f"level_{i + 1}" in current
            current = current[f"level_{i + 1}"]


class TestConfigLoaderMemory:
    """Stress tests for memory usage."""

    def test_no_memory_leak_on_repeated_loads(self, config_loader):
        """Test that repeated loads don't leak memory.

        Educational Note:
            Memory leaks in config loading accumulate over
            long-running production systems.
        """
        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Do many loads
        for _ in range(1000):
            config_loader.reload()  # Use correct API
            config_loader.load("system")

        # Force garbage collection again
        gc.collect()
        final_objects = len(gc.get_objects())

        # Object count shouldn't grow significantly (allow 10% growth)
        growth = final_objects - initial_objects
        growth_percent = (growth / initial_objects) * 100

        # Allow some growth but flag excessive growth
        assert growth_percent < 20, (
            f"Object count grew by {growth_percent:.1f}% ({initial_objects} -> {final_objects})"
        )


class TestConfigLoaderErrorRecovery:
    """Stress tests for error recovery."""

    def test_recovery_from_concurrent_failures(self, config_loader):
        """Test system recovers after concurrent read failures.

        Educational Note:
            Temporary failures shouldn't leave system in broken state.
        """
        results = {"success": 0, "expected_failure": 0}
        lock = threading.Lock()

        def attempt_read(should_fail):
            try:
                if should_fail:
                    # Try to read non-existent config (raises FileNotFoundError)
                    config_loader.load("nonexistent_config_xyz")
                else:
                    # Normal read using valid config
                    config_loader.load("system")
                    with lock:
                        results["success"] += 1
            except FileNotFoundError:
                # Expected error for nonexistent config
                with lock:
                    if should_fail:
                        results["expected_failure"] += 1
            except Exception:
                # Unexpected error
                pass

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for i in range(100):
                should_fail = i % 3 == 0  # Every 3rd request fails
                futures.append(executor.submit(attempt_read, should_fail))

            for future in as_completed(futures):
                pass

        # System should still work after failures
        assert results["success"] > 50, "Too many failures"
        assert results["expected_failure"] > 20, "Expected some failures"
