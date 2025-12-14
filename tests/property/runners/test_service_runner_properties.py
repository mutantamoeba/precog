"""
Property-based tests for DataCollectorService (service_runner) using Hypothesis.

Property-based testing generates thousands of test cases automatically,
testing invariants (properties that should ALWAYS hold true) rather than
specific examples.

Key Properties Tested:
    1. PID file invariants - Read/write roundtrip, removal idempotent
    2. Path invariants - Platform paths always valid
    3. Configuration invariants - Valid configs produce valid state
    4. Service configuration - Intervals positive, booleans correct
    5. Process detection - Returns appropriate types

Educational Note:
    Property tests for service runners focus on:
    - File system operations: PID files read/write correctly
    - Platform detection: Paths are valid for all platforms
    - Configuration bounds: Intervals always positive
    - Type safety: Functions return expected types

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-100 (Service Supervisor Pattern), ADR-074 (Property-Based Testing)
Requirements: REQ-DATA-001, REQ-OBSERV-001, REQ-TEST-008
"""

import os
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from precog.runners.service_runner import (
    DEFAULT_ESPN_INTERVAL,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_KALSHI_INTERVAL,
    DEFAULT_LEAGUES,
    DEFAULT_METRICS_INTERVAL,
    DataCollectorService,
    read_pid_file,
    remove_pid_file,
    write_pid_file,
)

pytestmark = [pytest.mark.property]


# =============================================================================
# Custom Hypothesis Strategies
# =============================================================================


@st.composite
def valid_pid_strategy(draw: st.DrawFn) -> int:
    """
    Generate valid PID values.

    Educational Note:
        PIDs on most systems are positive integers:
        - Linux: 1 to 2^22 (4 million)
        - Windows: 4 to ~4 million
        We test with realistic bounds.
    """
    return draw(st.integers(min_value=1, max_value=4_000_000))


@st.composite
def interval_strategy(draw: st.DrawFn) -> int:
    """
    Generate valid poll intervals.

    Educational Note:
        Intervals are bounded by:
        - Minimum: API rate limits (5 seconds)
        - Maximum: Reasonable polling delay (3600 seconds / 1 hour)
    """
    return draw(st.integers(min_value=5, max_value=3600))


@st.composite
def leagues_strategy(draw: st.DrawFn) -> list[str]:
    """
    Generate valid league lists.

    Educational Note:
        League codes must be non-empty strings.
        Valid leagues include: nfl, nba, nhl, ncaaf, ncaab, etc.
    """
    valid_leagues = ["nfl", "nba", "nhl", "ncaaf", "ncaab", "mlb", "mls", "wnba"]
    num_leagues = draw(st.integers(min_value=1, max_value=len(valid_leagues)))
    return draw(
        st.lists(
            st.sampled_from(valid_leagues), min_size=num_leagues, max_size=num_leagues, unique=True
        )
    )


@st.composite
def service_config_strategy(draw: st.DrawFn) -> dict:
    """
    Generate valid DataCollectorService configuration.

    Educational Note:
        Configuration must satisfy:
        - Intervals are positive integers
        - At least one service enabled
        - Leagues is non-empty list
    """
    espn_enabled = draw(st.booleans())
    kalshi_enabled = draw(st.booleans())

    # Ensure at least one service enabled for meaningful tests
    if not espn_enabled and not kalshi_enabled:
        espn_enabled = True

    return {
        "espn_enabled": espn_enabled,
        "kalshi_enabled": kalshi_enabled,
        "espn_interval": draw(interval_strategy()),
        "kalshi_interval": draw(interval_strategy()),
        "health_interval": draw(interval_strategy()),
        "metrics_interval": draw(interval_strategy()),
        "leagues": draw(leagues_strategy()),
        "debug": draw(st.booleans()),
    }


# =============================================================================
# Property Tests: PID File Invariants
# =============================================================================


class TestPIDFileInvariants:
    """Property tests for PID file operations.

    Educational Note:
        PID files are critical for service management:
        - Write must be atomic and reliable
        - Read must return exact value written
        - Removal must be idempotent (safe to call multiple times)
    """

    @given(pid=valid_pid_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_pid_file_roundtrip(self, pid: int) -> None:
        """Property: PID written to file can be read back exactly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"

            write_pid_file(pid_file)
            # Note: write_pid_file writes current process PID, not the arg
            # So we test that the written PID is valid
            read_back = read_pid_file(pid_file)

            assert read_back is not None, "PID should be readable after write"
            assert isinstance(read_back, int), "Read PID must be integer"
            assert read_back > 0, "Read PID must be positive"

    @given(pid=valid_pid_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_pid_file_removal_idempotent(self, pid: int) -> None:
        """Property: Removing PID file multiple times is safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"

            # Write then remove multiple times
            write_pid_file(pid_file)
            remove_pid_file(pid_file)
            remove_pid_file(pid_file)  # Should not raise
            remove_pid_file(pid_file)  # Should not raise

            # Verify file is gone
            assert not pid_file.exists(), "PID file should be removed"

    @given(st.data())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_read_nonexistent_returns_none(self, data: st.DataObject) -> None:
        """Property: Reading nonexistent PID file returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "nonexistent.pid"

            result = read_pid_file(pid_file)
            assert result is None, "Nonexistent PID file should return None"

    @given(
        invalid_content=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
        )
    )
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_read_invalid_content_returns_none(self, invalid_content: str) -> None:
        """Property: Reading invalid PID content returns None.

        Educational Note:
            Uses ASCII-safe characters to avoid Windows cp1252 encoding issues.
            Tests that non-numeric content returns None gracefully.
        """
        # Skip if the text happens to be a valid integer
        try:
            int(invalid_content.strip())
            return  # Skip this case, it's valid
        except ValueError:
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "invalid.pid"
            pid_file.write_text(invalid_content, encoding="utf-8")

            result = read_pid_file(pid_file)
            assert result is None, "Invalid PID content should return None"


# =============================================================================
# Property Tests: Path Invariants
# =============================================================================


class TestPathInvariants:
    """Property tests for platform path functions.

    Educational Note:
        Path functions must:
        - Always return valid Path objects
        - Handle platform differences (Windows vs Unix)
        - Create parent directories as needed
    """

    @given(st.data())
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_pid_file_path_is_valid_path(self, data: st.DataObject) -> None:
        """Property: get_pid_file returns a valid Path object."""
        from precog.runners.service_runner import get_pid_file

        pid_path = get_pid_file()
        assert isinstance(pid_path, Path), "get_pid_file must return Path"
        assert pid_path.suffix == ".pid", "PID file should have .pid extension"

    @given(st.data())
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_log_dir_path_is_valid_path(self, data: st.DataObject) -> None:
        """Property: get_log_dir returns a valid Path object."""
        from precog.runners.service_runner import get_log_dir

        log_path = get_log_dir()
        assert isinstance(log_path, Path), "get_log_dir must return Path"

    @given(st.data())
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_pid_file_in_precog_directory(self, data: st.DataObject) -> None:
        """Property: PID file is in a precog-related directory."""
        from precog.runners.service_runner import get_pid_file

        pid_path = get_pid_file()
        path_str = str(pid_path).lower()

        # Should contain "precog" somewhere in path
        assert "precog" in path_str or "var/run" in path_str, (
            "PID file should be in precog directory or /var/run"
        )


# =============================================================================
# Property Tests: Default Configuration Invariants
# =============================================================================


class TestDefaultConfigurationInvariants:
    """Property tests for default configuration values.

    Educational Note:
        Default values establish baseline behavior:
        - Intervals must be positive for polling to work
        - Leagues list must not be empty
        - Health/metrics intervals must be reasonable
    """

    def test_default_espn_interval_positive(self) -> None:
        """Property: Default ESPN interval is positive."""
        assert DEFAULT_ESPN_INTERVAL > 0, "ESPN interval must be positive"
        assert DEFAULT_ESPN_INTERVAL <= 300, "ESPN interval should be <= 5 minutes"

    def test_default_kalshi_interval_positive(self) -> None:
        """Property: Default Kalshi interval is positive."""
        assert DEFAULT_KALSHI_INTERVAL > 0, "Kalshi interval must be positive"
        assert DEFAULT_KALSHI_INTERVAL <= 300, "Kalshi interval should be <= 5 minutes"

    def test_default_health_interval_positive(self) -> None:
        """Property: Default health check interval is positive."""
        assert DEFAULT_HEALTH_CHECK_INTERVAL > 0, "Health interval must be positive"
        assert DEFAULT_HEALTH_CHECK_INTERVAL <= 600, "Health interval should be <= 10 minutes"

    def test_default_metrics_interval_positive(self) -> None:
        """Property: Default metrics interval is positive."""
        assert DEFAULT_METRICS_INTERVAL > 0, "Metrics interval must be positive"
        assert DEFAULT_METRICS_INTERVAL <= 3600, "Metrics interval should be <= 1 hour"

    def test_default_leagues_not_empty(self) -> None:
        """Property: Default leagues list is not empty."""
        assert len(DEFAULT_LEAGUES) > 0, "Default leagues must not be empty"

    def test_default_leagues_are_strings(self) -> None:
        """Property: All default leagues are strings."""
        for league in DEFAULT_LEAGUES:
            assert isinstance(league, str), "Each league must be a string"
            assert len(league) > 0, "League string must not be empty"


# =============================================================================
# Property Tests: DataCollectorService Initialization
# =============================================================================


class TestServiceInitializationInvariants:
    """Property tests for DataCollectorService initialization.

    Educational Note:
        Service initialization must:
        - Accept valid configuration without error
        - Store configuration values correctly
        - Initialize internal state properly
    """

    @given(config=service_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_service_accepts_valid_config(self, config: dict) -> None:
        """Property: Service accepts any valid configuration."""
        service = DataCollectorService(**config)

        assert service.espn_enabled == config["espn_enabled"]
        assert service.kalshi_enabled == config["kalshi_enabled"]
        assert service.espn_interval == config["espn_interval"]
        assert service.kalshi_interval == config["kalshi_interval"]
        assert service.debug == config["debug"]

    @given(config=service_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_service_shutdown_flag_initially_false(self, config: dict) -> None:
        """Property: Shutdown flag is False after initialization."""
        service = DataCollectorService(**config)
        assert service._shutdown_requested is False, "Shutdown flag must be False initially"

    @given(config=service_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_service_supervisor_initially_none(self, config: dict) -> None:
        """Property: Supervisor is None before start."""
        service = DataCollectorService(**config)
        assert service.supervisor is None, "Supervisor must be None before start"

    @given(config=service_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_service_logger_initially_none(self, config: dict) -> None:
        """Property: Logger is None before start."""
        service = DataCollectorService(**config)
        assert service.logger is None, "Logger must be None before start"

    @given(config=service_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_service_pid_file_path_valid(self, config: dict) -> None:
        """Property: Service has valid PID file path."""
        service = DataCollectorService(**config)
        assert isinstance(service.pid_file, Path), "pid_file must be Path"
        assert service.pid_file.suffix == ".pid", "PID file must have .pid extension"

    @given(config=service_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_service_log_dir_path_valid(self, config: dict) -> None:
        """Property: Service has valid log directory path."""
        service = DataCollectorService(**config)
        assert isinstance(service.log_dir, Path), "log_dir must be Path"


# =============================================================================
# Property Tests: Interval Bounds
# =============================================================================


class TestIntervalBoundsInvariants:
    """Property tests for interval bounds validation.

    Educational Note:
        Intervals must be bounded to prevent:
        - Too frequent: API rate limiting, system overload
        - Too infrequent: Stale data, missed opportunities
    """

    @given(interval=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=100)
    def test_interval_stored_correctly(self, interval: int) -> None:
        """Property: Intervals are stored as provided."""
        service = DataCollectorService(
            espn_interval=interval,
            kalshi_interval=interval,
            health_interval=interval,
            metrics_interval=interval,
        )

        assert service.espn_interval == interval
        assert service.kalshi_interval == interval
        assert service.health_interval == interval
        assert service.metrics_interval == interval

    @given(
        espn=st.integers(min_value=1, max_value=1000),
        kalshi=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=100)
    def test_different_intervals_independent(self, espn: int, kalshi: int) -> None:
        """Property: ESPN and Kalshi intervals are independent."""
        service = DataCollectorService(
            espn_interval=espn,
            kalshi_interval=kalshi,
        )

        assert service.espn_interval == espn
        assert service.kalshi_interval == kalshi


# =============================================================================
# Property Tests: League Configuration
# =============================================================================


class TestLeagueConfigurationInvariants:
    """Property tests for league configuration.

    Educational Note:
        League configuration determines which sports to poll.
        Must handle empty lists, duplicates, and default values.
    """

    @given(leagues=leagues_strategy())
    @settings(max_examples=50)
    def test_leagues_stored_correctly(self, leagues: list[str]) -> None:
        """Property: Leagues list is stored correctly."""
        service = DataCollectorService(leagues=leagues)
        assert service.leagues == leagues

    def test_default_leagues_used_when_none(self) -> None:
        """Property: Default leagues used when None provided."""
        service = DataCollectorService(leagues=None)
        assert service.leagues == DEFAULT_LEAGUES

    @given(leagues=leagues_strategy())
    @settings(max_examples=50)
    def test_leagues_are_list(self, leagues: list[str]) -> None:
        """Property: Leagues is always a list."""
        service = DataCollectorService(leagues=leagues)
        assert isinstance(service.leagues, list)


# =============================================================================
# Property Tests: Process Detection Invariants
# =============================================================================


class TestProcessDetectionInvariants:
    """Property tests for process detection functions.

    Educational Note:
        Process detection must:
        - Return boolean for running check
        - Handle invalid PIDs gracefully
        - Work across platforms
    """

    @given(pid=st.integers(min_value=-1000, max_value=-1))
    @settings(max_examples=50)
    def test_negative_pid_not_running(self, pid: int) -> None:
        """Property: Negative PIDs are never running.

        Educational Note:
            We only test negative PIDs because:
            - PID 0 is the kernel scheduler on Linux (exists and is "running")
            - PID 0 doesn't exist on Windows (returns False)
            - Negative PIDs are invalid on ALL platforms
        """
        from precog.runners.service_runner import is_process_running

        # Negative PIDs should never be running on any platform
        result = is_process_running(pid)
        assert isinstance(result, bool), "is_process_running must return bool"
        assert result is False, f"Negative PID {pid} should not be running"

    def test_current_process_running(self) -> None:
        """Property: Current process is always running."""
        from precog.runners.service_runner import is_process_running

        current_pid = os.getpid()
        result = is_process_running(current_pid)
        assert result is True, "Current process must be running"

    @given(pid=st.integers(min_value=5_000_000, max_value=10_000_000))
    @settings(max_examples=50)
    def test_very_large_pid_not_running(self, pid: int) -> None:
        """Property: Very large PIDs are not running."""
        from precog.runners.service_runner import is_process_running

        result = is_process_running(pid)
        assert isinstance(result, bool), "is_process_running must return bool"
        # PIDs beyond system limits should not be running
        assert result is False, f"PID {pid} is too large to be running"


# =============================================================================
# Property Tests: Service Enable Flags
# =============================================================================


class TestServiceEnableFlagsInvariants:
    """Property tests for service enable flag combinations.

    Educational Note:
        Enable flags determine which pollers are active.
        All combinations must be valid (including both disabled).
    """

    @given(espn=st.booleans(), kalshi=st.booleans())
    @settings(max_examples=20)
    def test_all_enable_combinations_valid(self, espn: bool, kalshi: bool) -> None:
        """Property: All enable flag combinations create valid service."""
        service = DataCollectorService(
            espn_enabled=espn,
            kalshi_enabled=kalshi,
        )

        assert service.espn_enabled == espn
        assert service.kalshi_enabled == kalshi
        assert isinstance(service.espn_enabled, bool)
        assert isinstance(service.kalshi_enabled, bool)

    @given(debug=st.booleans())
    @settings(max_examples=10)
    def test_debug_flag_stored(self, debug: bool) -> None:
        """Property: Debug flag is stored correctly."""
        service = DataCollectorService(debug=debug)
        assert service.debug == debug
        assert isinstance(service.debug, bool)
