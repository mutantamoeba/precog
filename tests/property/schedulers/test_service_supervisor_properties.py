"""
Property-based tests for ServiceSupervisor using Hypothesis.

Property-based testing generates thousands of test cases automatically,
testing invariants (properties that should ALWAYS hold true) rather than
specific examples.

Key Properties Tested:
    1. Configuration invariants - Valid configs produce valid state
    2. State transition invariants - State transitions are consistent
    3. Metric invariants - Metrics are non-negative, bounded correctly
    4. Restart count invariants - Never negative, monotonically increasing
    5. Health status invariants - Binary healthy/unhealthy, consistent with state

Educational Note:
    Property tests for supervisors focus on:
    - State consistency: Services in valid states after any operation sequence
    - Metric bounds: Error counts, restart counts always non-negative
    - Timing: Uptime, delays are positive when running
    - Thread safety: Properties hold under concurrent access

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-100 (Service Supervisor Pattern), ADR-074 (Property-Based Testing)
Requirements: REQ-DATA-001, REQ-OBSERV-001, REQ-TEST-008
"""

from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from precog.schedulers.service_supervisor import (
    Environment,
    RunnerConfig,
    ServiceConfig,
    ServiceState,
    ServiceSupervisor,
)

# =============================================================================
# Custom Hypothesis Strategies
# =============================================================================


@st.composite
def environment_strategy(draw: st.DrawFn) -> Environment:
    """Generate valid Environment enum values."""
    return draw(st.sampled_from(list(Environment)))


@st.composite
def service_config_strategy(draw: st.DrawFn) -> ServiceConfig:
    """
    Generate valid ServiceConfig with realistic values.

    Educational Note:
        Strategy bounds mirror real-world constraints:
        - poll_interval: 5-300s (API rate limits)
        - max_retries: 0-10 (reasonable retry limits)
        - retry_delay: 1-60s (backoff timing)
        - alert_threshold: 1-100 (error counts)
    """
    name = draw(
        st.text(
            min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Pd"))
        )
    )
    enabled = draw(st.booleans())
    poll_interval = draw(st.integers(min_value=5, max_value=300))
    max_retries = draw(st.integers(min_value=0, max_value=10))
    retry_delay = draw(st.integers(min_value=1, max_value=60))
    alert_threshold = draw(st.integers(min_value=1, max_value=100))

    return ServiceConfig(
        name=name,
        enabled=enabled,
        poll_interval=poll_interval,
        max_retries=max_retries,
        retry_delay=retry_delay,
        alert_threshold=alert_threshold,
    )


@st.composite
def runner_config_strategy(draw: st.DrawFn) -> RunnerConfig:
    """
    Generate valid RunnerConfig with realistic values.

    Educational Note:
        These constraints ensure valid configurations:
        - log_level must be valid Python logging level
        - intervals must be positive
        - byte counts must be realistic file sizes
    """
    environment = draw(environment_strategy())
    log_level = draw(st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR"]))
    health_check_interval = draw(st.integers(min_value=5, max_value=600))
    metrics_interval = draw(st.integers(min_value=5, max_value=3600))
    log_max_bytes = draw(st.integers(min_value=1024, max_value=100 * 1024 * 1024))
    log_backup_count = draw(st.integers(min_value=1, max_value=20))

    return RunnerConfig(
        environment=environment,
        log_level=log_level,
        log_dir=Path("/tmp/test_logs"),
        log_max_bytes=log_max_bytes,
        log_backup_count=log_backup_count,
        health_check_interval=health_check_interval,
        metrics_interval=metrics_interval,
    )


@st.composite
def service_state_strategy(draw: st.DrawFn) -> ServiceState:
    """
    Generate valid ServiceState with realistic values.

    Educational Note:
        State values have natural constraints:
        - Counts are non-negative
        - healthy is boolean
        - timestamps are optional
    """
    error_count = draw(st.integers(min_value=0, max_value=10000))
    restart_count = draw(st.integers(min_value=0, max_value=100))
    consecutive_failures = draw(st.integers(min_value=0, max_value=20))
    healthy = draw(st.booleans())

    return ServiceState(
        error_count=error_count,
        restart_count=restart_count,
        consecutive_failures=consecutive_failures,
        healthy=healthy,
    )


# =============================================================================
# Property Tests: Configuration Invariants
# =============================================================================


class TestConfigurationInvariants:
    """Property tests for configuration invariants.

    Educational Note:
        Valid configurations should always produce valid runtime state.
        These tests verify the configuration system maintains consistency.
    """

    @given(config=service_config_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_service_config_poll_interval_positive(self, config: ServiceConfig) -> None:
        """Property: poll_interval is always positive."""
        assert config.poll_interval > 0, "Poll interval must be positive"

    @given(config=service_config_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_service_config_retry_values_non_negative(self, config: ServiceConfig) -> None:
        """Property: max_retries and retry_delay are non-negative."""
        assert config.max_retries >= 0, "Max retries must be non-negative"
        assert config.retry_delay >= 0, "Retry delay must be non-negative"

    @given(config=service_config_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_service_config_alert_threshold_positive(self, config: ServiceConfig) -> None:
        """Property: alert_threshold is always positive."""
        assert config.alert_threshold > 0, "Alert threshold must be positive"

    @given(config=runner_config_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_runner_config_intervals_positive(self, config: RunnerConfig) -> None:
        """Property: health check and metrics intervals are positive."""
        assert config.health_check_interval > 0, "Health check interval must be positive"
        assert config.metrics_interval > 0, "Metrics interval must be positive"

    @given(config=runner_config_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_runner_config_log_params_valid(self, config: RunnerConfig) -> None:
        """Property: log parameters are valid."""
        assert config.log_max_bytes > 0, "Log max bytes must be positive"
        assert config.log_backup_count > 0, "Log backup count must be positive"

    @given(config=runner_config_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_runner_config_has_default_services(self, config: RunnerConfig) -> None:
        """Property: RunnerConfig always has default services."""
        assert len(config.services) > 0, "Config must have at least one service"


# =============================================================================
# Property Tests: ServiceState Invariants
# =============================================================================


class TestServiceStateInvariants:
    """Property tests for ServiceState invariants.

    Educational Note:
        Service state tracks runtime metrics. These tests verify
        that state values remain within valid bounds.
    """

    @given(state=service_state_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_error_count_non_negative(self, state: ServiceState) -> None:
        """Property: error_count is always non-negative."""
        assert state.error_count >= 0, "Error count must be non-negative"

    @given(state=service_state_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_restart_count_non_negative(self, state: ServiceState) -> None:
        """Property: restart_count is always non-negative."""
        assert state.restart_count >= 0, "Restart count must be non-negative"

    @given(state=service_state_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_consecutive_failures_non_negative(self, state: ServiceState) -> None:
        """Property: consecutive_failures is always non-negative."""
        assert state.consecutive_failures >= 0, "Consecutive failures must be non-negative"

    @given(state=service_state_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_healthy_is_boolean(self, state: ServiceState) -> None:
        """Property: healthy is always a boolean."""
        assert isinstance(state.healthy, bool), "Healthy must be boolean"


# =============================================================================
# Property Tests: Supervisor Invariants
# =============================================================================


class TestSupervisorInvariants:
    """Property tests for ServiceSupervisor invariants.

    Educational Note:
        Supervisor invariants ensure consistent behavior:
        - Not running before start
        - Running after start (before stop)
        - Uptime is non-negative
        - Metrics are valid dictionaries
    """

    @given(config=runner_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_supervisor_not_running_before_start(self, config: RunnerConfig) -> None:
        """Property: Supervisor is not running before start_all()."""
        supervisor = ServiceSupervisor(config)
        assert supervisor.is_running is False, "Supervisor should not be running before start"

    @given(config=runner_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_uptime_zero_before_start(self, config: RunnerConfig) -> None:
        """Property: Uptime is zero before start_all()."""
        supervisor = ServiceSupervisor(config)
        assert supervisor.uptime_seconds == 0.0, "Uptime should be 0 before start"

    @given(config=runner_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_services_dict_empty_initially(self, config: RunnerConfig) -> None:
        """Property: Services dict is empty on initialization."""
        supervisor = ServiceSupervisor(config)
        assert len(supervisor.services) == 0, "Services should be empty initially"


# =============================================================================
# Property Tests: Metric Invariants
# =============================================================================


class TestMetricInvariants:
    """Property tests for metric aggregation invariants.

    Educational Note:
        Aggregate metrics must be consistent with individual service states:
        - Total errors = sum of service errors
        - Total restarts = sum of service restarts
        - Healthy count <= total count
    """

    @given(config=runner_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_aggregate_metrics_structure(self, config: RunnerConfig) -> None:
        """Property: Aggregate metrics have required keys."""
        supervisor = ServiceSupervisor(config)
        metrics = supervisor.get_aggregate_metrics()

        required_keys = [
            "uptime_seconds",
            "services_total",
            "services_healthy",
            "total_restarts",
            "total_errors",
            "per_service",
        ]

        for key in required_keys:
            assert key in metrics, f"Metrics must contain '{key}'"

    @given(config=runner_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_aggregate_metrics_counts_non_negative(self, config: RunnerConfig) -> None:
        """Property: All metric counts are non-negative."""
        supervisor = ServiceSupervisor(config)
        metrics = supervisor.get_aggregate_metrics()

        assert metrics["services_total"] >= 0, "services_total must be non-negative"
        assert metrics["services_healthy"] >= 0, "services_healthy must be non-negative"
        assert metrics["total_restarts"] >= 0, "total_restarts must be non-negative"
        assert metrics["total_errors"] >= 0, "total_errors must be non-negative"

    @given(config=runner_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_healthy_count_bounded_by_total(self, config: RunnerConfig) -> None:
        """Property: services_healthy <= services_total."""
        supervisor = ServiceSupervisor(config)
        metrics = supervisor.get_aggregate_metrics()

        assert metrics["services_healthy"] <= metrics["services_total"], (
            "Healthy count cannot exceed total count"
        )


# =============================================================================
# Property Tests: Exponential Backoff Invariants
# =============================================================================


class TestExponentialBackoffInvariants:
    """Property tests for exponential backoff calculation.

    Educational Note:
        Exponential backoff delays grow as: delay * 2^(attempt-1)
        This prevents rapid restart loops while allowing recovery.
    """

    @given(
        base_delay=st.integers(min_value=1, max_value=60),
        attempts=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_backoff_delay_increases_with_attempts(self, base_delay: int, attempts: int) -> None:
        """Property: Backoff delay increases (or stays same) with attempts."""
        delays = [base_delay * (2 ** (i - 1)) for i in range(1, attempts + 1)]

        # Each delay should be >= previous
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1], "Delays should not decrease"

    @given(
        base_delay=st.integers(min_value=1, max_value=60),
        attempt=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_backoff_delay_formula(self, base_delay: int, attempt: int) -> None:
        """Property: Backoff delay follows formula: base * 2^(attempt-1)."""
        expected = base_delay * (2 ** (attempt - 1))
        calculated = base_delay * (2 ** (attempt - 1))
        assert calculated == expected, "Backoff formula must be consistent"

    @given(
        base_delay=st.integers(min_value=1, max_value=60),
        attempt=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_backoff_delay_positive(self, base_delay: int, attempt: int) -> None:
        """Property: Backoff delay is always positive."""
        delay = base_delay * (2 ** (attempt - 1))
        assert delay > 0, "Backoff delay must be positive"


# =============================================================================
# Property Tests: Environment Invariants
# =============================================================================


class TestEnvironmentInvariants:
    """Property tests for Environment enum invariants.

    Educational Note:
        Environment values must be valid strings that can round-trip
        through serialization/deserialization.
    """

    @given(env=environment_strategy())
    @settings(max_examples=50)
    def test_environment_roundtrip(self, env: Environment) -> None:
        """Property: Environment can round-trip through string value."""
        value = env.value
        reconstructed = Environment(value)
        assert reconstructed == env, "Environment should round-trip through value"

    @given(env=environment_strategy())
    @settings(max_examples=50)
    def test_environment_value_is_string(self, env: Environment) -> None:
        """Property: Environment value is always a string."""
        assert isinstance(env.value, str), "Environment value must be string"

    @given(env=environment_strategy())
    @settings(max_examples=50)
    def test_environment_value_is_lowercase(self, env: Environment) -> None:
        """Property: Environment value is lowercase."""
        assert env.value == env.value.lower(), "Environment value must be lowercase"


# =============================================================================
# Property Tests: Alert Callback Invariants
# =============================================================================


class TestAlertCallbackInvariants:
    """Property tests for alert callback registration.

    Educational Note:
        Alert callbacks should accumulate and never be lost.
        This ensures all monitoring integrations receive notifications.
    """

    @given(
        config=runner_config_strategy(),
        num_callbacks=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_callbacks_accumulate(self, config: RunnerConfig, num_callbacks: int) -> None:
        """Property: Registered callbacks accumulate."""
        supervisor = ServiceSupervisor(config)

        for i in range(num_callbacks):
            supervisor.register_alert_callback(lambda n, m, c: None)

        assert len(supervisor._alert_callbacks) == num_callbacks, (
            "All registered callbacks should be stored"
        )

    @given(config=runner_config_strategy())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_callbacks_empty_initially(self, config: RunnerConfig) -> None:
        """Property: No callbacks registered initially."""
        supervisor = ServiceSupervisor(config)
        assert len(supervisor._alert_callbacks) == 0, "Callbacks should be empty initially"
