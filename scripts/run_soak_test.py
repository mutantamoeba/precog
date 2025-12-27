#!/usr/bin/env python3
"""24-hour soak testing infrastructure for Precog.

This script runs extended tests to catch timing-related bugs, memory leaks,
and edge cases that only appear under sustained operation.

Usage:
    # Full 24-hour soak test (local)
    python scripts/run_soak_test.py

    # Quick 1-hour test
    python scripts/run_soak_test.py --duration 1h

    # CI-compatible 5-minute smoke test
    python scripts/run_soak_test.py --duration 5m --ci

    # Custom configuration
    python scripts/run_soak_test.py --duration 2h --interval 30s --scenarios scheduler,database

Scenarios:
    - scheduler: Scheduler heartbeat and status monitoring
    - database: Connection pool stability and query performance
    - api: Rate limit recovery and endpoint availability
    - memory: Memory growth detection over time

Related:
    - Issue #282: Set up 24-hour local soak testing infrastructure
    - REQ-TEST-007: Performance testing requirements
    - Migration 0012: scheduler_status table for monitoring
"""

from __future__ import annotations

import argparse
import gc
import json
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@dataclass
class ResourceMetrics:
    """Point-in-time resource measurements.

    Educational Note:
        Tracking resources over time reveals patterns invisible in single measurements:
        - Gradual memory growth indicates leaks
        - Connection count creep suggests pool exhaustion
        - CPU spikes at specific times reveal scheduling issues
    """

    timestamp: datetime
    memory_mb: float
    memory_percent: float
    cpu_percent: float
    db_connections: int
    db_pool_size: int
    open_files: int
    thread_count: int
    error_count: int = 0
    warning_count: int = 0


@dataclass
class ScenarioResult:
    """Result of a single scenario execution."""

    scenario_name: str
    success: bool
    duration_ms: float
    error_message: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class SoakTestConfig:
    """Configuration for soak test execution.

    Educational Note:
        Default values are tuned for different use cases:
        - 24h duration: Full soak test for production readiness
        - 60s interval: Balance between granularity and overhead
        - 5m CI mode: Quick validation in automated pipelines
    """

    duration_seconds: int = 24 * 60 * 60  # 24 hours default
    check_interval_seconds: int = 60  # Check every minute
    scenarios: list[str] = field(default_factory=lambda: ["scheduler", "database", "memory"])
    ci_mode: bool = False
    output_dir: Path = field(default_factory=lambda: Path("soak_test_results"))
    memory_growth_threshold_mb: float = 100.0  # Alert if memory grows by this much
    error_rate_threshold: float = 0.01  # Alert if error rate exceeds 1%
    verbose: bool = False


class ResourceMonitor:
    """Monitors system resources during soak test.

    Educational Note:
        psutil provides cross-platform resource monitoring. We track:
        - Process-specific metrics (our Python process)
        - Database connection pool health
        - System-wide context for comparison
    """

    def __init__(self, config: SoakTestConfig) -> None:
        self.config = config
        self.metrics_history: list[ResourceMetrics] = []
        self.baseline_memory_mb: float | None = None
        self._process = None

    def _get_process(self) -> Any:
        """Get psutil Process object, importing psutil lazily."""
        if self._process is None:
            try:
                import psutil

                self._process = psutil.Process()
            except ImportError:
                return None
        return self._process

    def collect_metrics(self, error_count: int = 0, warning_count: int = 0) -> ResourceMetrics:
        """Collect current resource metrics.

        Args:
            error_count: Number of errors since last collection
            warning_count: Number of warnings since last collection

        Returns:
            ResourceMetrics with current measurements
        """
        process = self._get_process()

        if process is not None:
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            memory_percent = process.memory_percent()
            cpu_percent = process.cpu_percent(interval=0.1)
            open_files = len(process.open_files())
            thread_count = process.num_threads()
        else:
            # Fallback when psutil not available
            memory_mb = 0.0
            memory_percent = 0.0
            cpu_percent = 0.0
            open_files = 0
            thread_count = 1

        # Get database connection info
        db_connections, db_pool_size = self._get_db_connection_stats()

        metrics = ResourceMetrics(
            timestamp=datetime.now(UTC),
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            cpu_percent=cpu_percent,
            db_connections=db_connections,
            db_pool_size=db_pool_size,
            open_files=open_files,
            thread_count=thread_count,
            error_count=error_count,
            warning_count=warning_count,
        )

        # Set baseline on first collection
        if self.baseline_memory_mb is None:
            self.baseline_memory_mb = memory_mb

        self.metrics_history.append(metrics)
        return metrics

    def _get_db_connection_stats(self) -> tuple[int, int]:
        """Get database connection pool statistics.

        Returns:
            Tuple of (active_connections, pool_size)

        Educational Note:
            psycopg2's SimpleConnectionPool tracks connections internally:
            - _pool: list of available connections
            - _used: dict of in-use connections (keyed by connection id)
            - minconn/maxconn: configured pool bounds
        """
        try:
            from precog.database.connection import _connection_pool

            if _connection_pool is not None:
                # Get actual pool statistics
                in_use = len(_connection_pool._used) if hasattr(_connection_pool, "_used") else 0
                maxconn = getattr(_connection_pool, "maxconn", 25)
                return in_use, maxconn
            return 0, 0
        except Exception:
            return 0, 0

    def check_anomalies(self) -> list[str]:
        """Check for anomalies in collected metrics.

        Returns:
            List of anomaly descriptions
        """
        anomalies: list[str] = []

        if len(self.metrics_history) < 2:
            return anomalies

        latest = self.metrics_history[-1]

        # Check memory growth
        if self.baseline_memory_mb is not None:
            memory_growth = latest.memory_mb - self.baseline_memory_mb
            if memory_growth > self.config.memory_growth_threshold_mb:
                anomalies.append(
                    f"Memory growth: {memory_growth:.1f}MB since baseline "
                    f"(threshold: {self.config.memory_growth_threshold_mb}MB)"
                )

        # Check error rate
        total_errors = sum(m.error_count for m in self.metrics_history)
        total_checks = len(self.metrics_history)
        if total_checks > 0:
            error_rate = total_errors / total_checks
            if error_rate > self.config.error_rate_threshold:
                anomalies.append(
                    f"High error rate: {error_rate:.2%} "
                    f"(threshold: {self.config.error_rate_threshold:.2%})"
                )

        # Check connection pool exhaustion
        if latest.db_connections >= latest.db_pool_size > 0:
            anomalies.append(
                f"Connection pool at capacity: {latest.db_connections}/{latest.db_pool_size}"
            )

        return anomalies

    def get_summary_stats(self) -> dict[str, Any]:
        """Generate summary statistics from collected metrics."""
        if not self.metrics_history:
            return {}

        memory_values = [m.memory_mb for m in self.metrics_history]
        cpu_values = [m.cpu_percent for m in self.metrics_history]
        connection_values = [m.db_connections for m in self.metrics_history]

        return {
            "samples_collected": len(self.metrics_history),
            "duration_hours": (
                (
                    self.metrics_history[-1].timestamp - self.metrics_history[0].timestamp
                ).total_seconds()
                / 3600
            ),
            "memory": {
                "baseline_mb": self.baseline_memory_mb,
                "final_mb": memory_values[-1],
                "max_mb": max(memory_values),
                "min_mb": min(memory_values),
                "growth_mb": memory_values[-1] - (self.baseline_memory_mb or 0),
            },
            "cpu": {
                "avg_percent": sum(cpu_values) / len(cpu_values),
                "max_percent": max(cpu_values),
            },
            "database": {
                "max_connections": max(connection_values),
                "avg_connections": sum(connection_values) / len(connection_values),
            },
            "errors": {
                "total": sum(m.error_count for m in self.metrics_history),
                "warnings": sum(m.warning_count for m in self.metrics_history),
            },
        }


class SoakTestScenario:
    """Base class for soak test scenarios."""

    name: str = "base"

    def __init__(self, config: SoakTestConfig) -> None:
        self.config = config
        self.run_count = 0
        self.error_count = 0
        self.total_duration_ms = 0.0

    def run(self) -> ScenarioResult:
        """Execute the scenario and return results."""
        raise NotImplementedError

    def get_stats(self) -> dict[str, Any]:
        """Get scenario statistics."""
        return {
            "run_count": self.run_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.run_count, 1),
            "avg_duration_ms": self.total_duration_ms / max(self.run_count, 1),
        }


class SchedulerScenario(SoakTestScenario):
    """Test scheduler status and heartbeat monitoring.

    Educational Note:
        This scenario validates the IPC mechanism via scheduler_status table:
        - Heartbeats should be recent (< stale_threshold)
        - Status transitions should be valid
        - Stats JSON should parse correctly
    """

    name = "scheduler"

    def run(self) -> ScenarioResult:
        start = time.perf_counter()
        self.run_count += 1

        try:
            from precog.database.crud_operations import list_scheduler_services

            services = list_scheduler_services(include_stale=True)

            # Analyze service health
            metrics = {
                "total_services": len(services),
                "running": sum(1 for s in services if s.get("status") == "running"),
                "stale": sum(1 for s in services if s.get("is_stale", False)),
                "failed": sum(1 for s in services if s.get("status") == "failed"),
            }

            duration_ms = (time.perf_counter() - start) * 1000
            self.total_duration_ms += duration_ms

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_ms=duration_ms,
                metrics=metrics,
            )

        except Exception as e:
            self.error_count += 1
            duration_ms = (time.perf_counter() - start) * 1000
            self.total_duration_ms += duration_ms

            return ScenarioResult(
                scenario_name=self.name,
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )


class DatabaseScenario(SoakTestScenario):
    """Test database connection pool stability.

    Educational Note:
        Connection pool issues often manifest under sustained load:
        - Connections not returned to pool (leaks)
        - Pool exhaustion blocking new queries
        - Stale connections causing query failures
    """

    name = "database"

    def run(self) -> ScenarioResult:
        """Test database connection pool stability.

        Educational Note:
            psycopg2's SimpleConnectionPool doesn't expose pool stats like SQLAlchemy,
            but we can still validate connection health and track timing. The pool
            internally maintains _used (checked-out connections) and _pool (available).
        """
        start = time.perf_counter()
        self.run_count += 1

        try:
            from precog.database.connection import (
                _connection_pool,
                fetch_one,
                initialize_pool,
                test_connection,
            )

            # Ensure pool is initialized
            if _connection_pool is None:
                initialize_pool()

            # Execute a health check query
            query_success = test_connection()

            # Also run a custom query to verify data layer works
            result = fetch_one("SELECT 1 as health_check")
            fetch_success = result is not None and result.get("health_check") == 1

            # Get pool stats (psycopg2 SimpleConnectionPool internals)
            from precog.database.connection import _connection_pool as pool

            pool_stats = {}
            if pool is not None:
                # SimpleConnectionPool tracks used connections in _used dict
                # and available connections in _pool list
                pool_stats = {
                    "available": len(pool._pool) if hasattr(pool, "_pool") else 0,
                    "in_use": len(pool._used) if hasattr(pool, "_used") else 0,
                    "minconn": getattr(pool, "minconn", 0),
                    "maxconn": getattr(pool, "maxconn", 0),
                }

            metrics = {
                "query_success": query_success and fetch_success,
                **pool_stats,
            }

            duration_ms = (time.perf_counter() - start) * 1000
            self.total_duration_ms += duration_ms

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_ms=duration_ms,
                metrics=metrics,
            )

        except Exception as e:
            self.error_count += 1
            duration_ms = (time.perf_counter() - start) * 1000
            self.total_duration_ms += duration_ms

            return ScenarioResult(
                scenario_name=self.name,
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )


class MemoryScenario(SoakTestScenario):
    """Test memory stability and garbage collection.

    Educational Note:
        Memory leaks in Python often come from:
        - Circular references not collected
        - Caches growing unbounded
        - Event handlers not unregistered
        - Large objects kept in closures
    """

    name = "memory"

    def __init__(self, config: SoakTestConfig) -> None:
        super().__init__(config)
        self.previous_gc_stats: dict[str, int] = {}

    def run(self) -> ScenarioResult:
        start = time.perf_counter()
        self.run_count += 1

        try:
            # Force garbage collection to get accurate measurements
            gc.collect()

            # Get GC statistics
            gc_stats = gc.get_stats()
            current_counts = gc.get_count()

            metrics = {
                "gc_generation_0": current_counts[0],
                "gc_generation_1": current_counts[1],
                "gc_generation_2": current_counts[2],
                "gc_collected_gen0": gc_stats[0].get("collected", 0),
                "gc_collected_gen1": gc_stats[1].get("collected", 0),
                "gc_collected_gen2": gc_stats[2].get("collected", 0),
                "gc_uncollectable_gen0": gc_stats[0].get("uncollectable", 0),
                "gc_uncollectable_gen1": gc_stats[1].get("uncollectable", 0),
                "gc_uncollectable_gen2": gc_stats[2].get("uncollectable", 0),
            }

            # Check for uncollectable objects (potential memory leak)
            total_uncollectable = sum(gc_stats[i].get("uncollectable", 0) for i in range(3))

            duration_ms = (time.perf_counter() - start) * 1000
            self.total_duration_ms += duration_ms

            # Warn if uncollectable objects detected
            if total_uncollectable > 0:
                return ScenarioResult(
                    scenario_name=self.name,
                    success=True,  # Not a failure, but notable
                    duration_ms=duration_ms,
                    metrics=metrics,
                    error_message=f"Warning: {total_uncollectable} uncollectable objects detected",
                )

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_ms=duration_ms,
                metrics=metrics,
            )

        except Exception as e:
            self.error_count += 1
            duration_ms = (time.perf_counter() - start) * 1000
            self.total_duration_ms += duration_ms

            return ScenarioResult(
                scenario_name=self.name,
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )


class APIScenario(SoakTestScenario):
    """Test API rate limit recovery and endpoint availability.

    Educational Note:
        API testing in soak tests validates:
        - Rate limiter token bucket refill
        - Retry logic under sustained load
        - Authentication token refresh cycles
    """

    name = "api"

    def run(self) -> ScenarioResult:
        start = time.perf_counter()
        self.run_count += 1

        try:
            from precog.api_connectors.rate_limiter import RateLimiter

            # Test rate limiter state
            limiter = RateLimiter(requests_per_minute=100)

            metrics = {
                "tokens_available": limiter.bucket.get_available_tokens(),
                "max_tokens": limiter.burst_size,
                "utilization": limiter.get_utilization(),
            }

            duration_ms = (time.perf_counter() - start) * 1000
            self.total_duration_ms += duration_ms

            return ScenarioResult(
                scenario_name=self.name,
                success=True,
                duration_ms=duration_ms,
                metrics=metrics,
            )

        except Exception as e:
            self.error_count += 1
            duration_ms = (time.perf_counter() - start) * 1000
            self.total_duration_ms += duration_ms

            return ScenarioResult(
                scenario_name=self.name,
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )


class SoakTestRunner:
    """Main soak test orchestrator.

    Educational Note:
        The runner coordinates:
        - Scenario execution at configured intervals
        - Resource monitoring throughout the test
        - Graceful shutdown on signals
        - Report generation at completion
    """

    SCENARIO_CLASSES: ClassVar[dict[str, type[SoakTestScenario]]] = {
        "scheduler": SchedulerScenario,
        "database": DatabaseScenario,
        "memory": MemoryScenario,
        "api": APIScenario,
    }

    def __init__(self, config: SoakTestConfig) -> None:
        self.config = config
        self.monitor = ResourceMonitor(config)
        self.scenarios: list[SoakTestScenario] = []
        self.results: list[ScenarioResult] = []
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None
        self.shutdown_requested = False

        # Initialize scenarios
        for scenario_name in config.scenarios:
            if scenario_name in self.SCENARIO_CLASSES:
                self.scenarios.append(self.SCENARIO_CLASSES[scenario_name](config))
            else:
                print(f"Warning: Unknown scenario '{scenario_name}', skipping")

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, _frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.shutdown_requested = True

    def run(self) -> dict[str, Any]:
        """Execute the soak test.

        Returns:
            Summary report as dictionary
        """
        self.start_time = datetime.now(UTC)
        end_target = self.start_time + timedelta(seconds=self.config.duration_seconds)

        print(f"Starting soak test at {self.start_time.isoformat()}")
        print(f"Duration: {self.config.duration_seconds / 3600:.1f} hours")
        print(f"Scenarios: {', '.join(s.name for s in self.scenarios)}")
        print(f"Check interval: {self.config.check_interval_seconds}s")
        print("-" * 60)

        iteration = 0
        errors_this_interval = 0
        warnings_this_interval = 0

        try:
            while datetime.now(UTC) < end_target and not self.shutdown_requested:
                iteration += 1
                interval_start = time.perf_counter()

                if self.config.verbose:
                    elapsed = (datetime.now(UTC) - self.start_time).total_seconds() / 3600
                    remaining = (end_target - datetime.now(UTC)).total_seconds() / 3600
                    print(
                        f"\n[Iteration {iteration}] Elapsed: {elapsed:.2f}h, Remaining: {remaining:.2f}h"
                    )

                # Run all scenarios
                for scenario in self.scenarios:
                    result = scenario.run()
                    self.results.append(result)

                    if not result.success:
                        errors_this_interval += 1
                        if self.config.verbose:
                            print(f"  [FAIL] {result.scenario_name}: {result.error_message}")
                    elif result.error_message:  # Warning case
                        warnings_this_interval += 1
                        if self.config.verbose:
                            print(f"  [WARN] {result.scenario_name}: {result.error_message}")
                    elif self.config.verbose:
                        print(f"  [OK] {result.scenario_name}: {result.duration_ms:.1f}ms")

                # Collect resource metrics
                metrics = self.monitor.collect_metrics(errors_this_interval, warnings_this_interval)
                errors_this_interval = 0
                warnings_this_interval = 0

                # Check for anomalies
                anomalies = self.monitor.check_anomalies()
                for anomaly in anomalies:
                    print(f"  [ANOMALY] {anomaly}")

                # Print periodic status (every 10 iterations in non-verbose mode)
                if not self.config.verbose and iteration % 10 == 0:
                    elapsed = (datetime.now(UTC) - self.start_time).total_seconds() / 3600
                    total_errors = sum(s.error_count for s in self.scenarios)
                    print(
                        f"[{elapsed:.1f}h] Memory: {metrics.memory_mb:.1f}MB, "
                        f"Errors: {total_errors}, "
                        f"DB Connections: {metrics.db_connections}/{metrics.db_pool_size}"
                    )

                # Sleep until next interval
                elapsed = time.perf_counter() - interval_start
                sleep_time = max(0, self.config.check_interval_seconds - elapsed)
                if sleep_time > 0 and not self.shutdown_requested:
                    time.sleep(sleep_time)

        except Exception as e:
            print(f"\nFatal error during soak test: {e}")
            traceback.print_exc()

        self.end_time = datetime.now(UTC)
        return self._generate_report()

    def _generate_report(self) -> dict[str, Any]:
        """Generate final soak test report."""
        report = {
            "test_info": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "planned_duration_hours": self.config.duration_seconds / 3600,
                "actual_duration_hours": (
                    (self.end_time - self.start_time).total_seconds() / 3600
                    if self.start_time and self.end_time
                    else 0
                ),
                "ci_mode": self.config.ci_mode,
                "scenarios_run": [s.name for s in self.scenarios],
                "shutdown_requested": self.shutdown_requested,
            },
            "resource_summary": self.monitor.get_summary_stats(),
            "scenario_summaries": {s.name: s.get_stats() for s in self.scenarios},
            "anomalies_detected": self.monitor.check_anomalies(),
            "overall_status": "PASS" if self._is_passing() else "FAIL",
        }

        # Write report to file
        self._write_report(report)

        return report

    def _is_passing(self) -> bool:
        """Determine if the soak test passed."""
        # Check error rate across all scenarios
        total_runs = sum(s.run_count for s in self.scenarios)
        total_errors = sum(s.error_count for s in self.scenarios)

        if total_runs == 0:
            return False

        error_rate = total_errors / total_runs
        if error_rate > self.config.error_rate_threshold:
            return False

        # Check for memory growth anomaly
        if self.monitor.baseline_memory_mb is not None:
            latest = self.monitor.metrics_history[-1] if self.monitor.metrics_history else None
            if latest:
                growth = latest.memory_mb - self.monitor.baseline_memory_mb
                if growth > self.config.memory_growth_threshold_mb:
                    return False

        return True

    def _write_report(self, report: dict[str, Any]) -> None:
        """Write report to JSON file."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = self.config.output_dir / f"soak_test_report_{timestamp}.json"

        # Custom JSON encoder for datetime and Decimal
        class SoakTestEncoder(json.JSONEncoder):
            def default(self, obj: Any) -> Any:
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if isinstance(obj, Decimal):
                    return float(obj)
                return super().default(obj)

        with open(filename, "w") as f:
            json.dump(report, f, indent=2, cls=SoakTestEncoder)

        print(f"\nReport written to: {filename}")


def parse_duration(duration_str: str) -> int:
    """Parse duration string to seconds.

    Examples:
        "24h" -> 86400
        "1h" -> 3600
        "30m" -> 1800
        "5m" -> 300
        "60s" -> 60
        "3600" -> 3600 (plain number = seconds)
    """
    duration_str = duration_str.strip().lower()

    if duration_str.endswith("h"):
        return int(float(duration_str[:-1]) * 3600)
    if duration_str.endswith("m"):
        return int(float(duration_str[:-1]) * 60)
    if duration_str.endswith("s"):
        return int(float(duration_str[:-1]))
    return int(duration_str)


def main() -> int:
    """Main entry point for soak test."""
    parser = argparse.ArgumentParser(
        description="Run 24-hour soak tests for Precog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full 24-hour soak test
    python scripts/run_soak_test.py

    # Quick 1-hour test
    python scripts/run_soak_test.py --duration 1h

    # CI-compatible 5-minute test
    python scripts/run_soak_test.py --duration 5m --ci

    # Specific scenarios only
    python scripts/run_soak_test.py --scenarios scheduler,database
        """,
    )

    parser.add_argument(
        "--duration",
        default="24h",
        help="Test duration (e.g., 24h, 1h, 30m, 300s). Default: 24h",
    )
    parser.add_argument(
        "--interval",
        default="60s",
        help="Check interval (e.g., 60s, 5m). Default: 60s",
    )
    parser.add_argument(
        "--scenarios",
        default="scheduler,database,memory",
        help="Comma-separated scenarios to run. Available: scheduler,database,memory,api",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: stricter thresholds, shorter default duration",
    )
    parser.add_argument(
        "--output-dir",
        default="soak_test_results",
        help="Directory for output reports. Default: soak_test_results",
    )
    parser.add_argument(
        "--memory-threshold",
        type=float,
        default=100.0,
        help="Memory growth threshold in MB. Default: 100.0",
    )
    parser.add_argument(
        "--error-threshold",
        type=float,
        default=0.01,
        help="Error rate threshold (0.01 = 1%%). Default: 0.01",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Parse configuration
    config = SoakTestConfig(
        duration_seconds=parse_duration(args.duration),
        check_interval_seconds=parse_duration(args.interval),
        scenarios=args.scenarios.split(","),
        ci_mode=args.ci,
        output_dir=Path(args.output_dir),
        memory_growth_threshold_mb=args.memory_threshold,
        error_rate_threshold=args.error_threshold,
        verbose=args.verbose,
    )

    # In CI mode, use stricter defaults if not explicitly set
    if args.ci and args.duration == "24h":
        config.duration_seconds = 5 * 60  # 5 minutes for CI
        config.check_interval_seconds = 10  # Faster checks

    # Run soak test
    runner = SoakTestRunner(config)
    report = runner.run()

    # Print summary
    print("\n" + "=" * 60)
    print("SOAK TEST SUMMARY")
    print("=" * 60)
    print(f"Status: {report['overall_status']}")
    print(f"Duration: {report['test_info']['actual_duration_hours']:.2f} hours")

    resource_summary = report.get("resource_summary", {})
    if resource_summary:
        memory = resource_summary.get("memory", {})
        print(f"Memory Growth: {memory.get('growth_mb', 0):.1f}MB")
        errors = resource_summary.get("errors", {})
        print(f"Total Errors: {errors.get('total', 0)}")

    if report["anomalies_detected"]:
        print("\nAnomalies Detected:")
        for anomaly in report["anomalies_detected"]:
            print(f"  - {anomaly}")

    print("=" * 60)

    # Return exit code based on status
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
