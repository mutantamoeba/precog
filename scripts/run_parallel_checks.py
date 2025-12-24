#!/usr/bin/env python3
"""
Parallel Pre-Push Check Runner (Windows-Safe).

This script runs pre-push validation checks in parallel with proper timeout
handling. It's designed to replace bash background processes on Windows,
where MSYS2/Cygwin has unreliable signal handling.

Why This Exists:
    Windows Git Bash uses MSYS2 which imperfectly emulates Unix signals.
    Background processes spawned with `{ ... } &` and collected with `wait`
    can hang indefinitely because:
    - SIGCHLD notifications are unreliable
    - Process termination events may be lost
    - File descriptor inheritance behaves differently

    Python's subprocess module with concurrent.futures provides reliable
    cross-platform parallel execution with proper timeout support.

Usage:
    Called by .git/hooks/pre-push on Windows:
        python scripts/run_parallel_checks.py

    Or run directly for testing:
        python scripts/run_parallel_checks.py --dry-run

Exit Codes:
    0: All checks passed
    1: One or more checks failed
    2: Timeout occurred

Reference:
    - Issue #202: Two-Axis Environment Configuration (discovered the hang)
    - Pattern 5: Cross-Platform Compatibility (DEVELOPMENT_PATTERNS)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from concurrent.futures import Future

# Repository root (script is in scripts/)
REPO_ROOT = Path(__file__).parent.parent

# Artifacts directory for test reports (aligned with CI)
ARTIFACTS_DIR = REPO_ROOT / ".pre-push-artifacts"

# Timeout for individual checks (8 minutes - allows for full test suite)
CHECK_TIMEOUT = 480


def run_subprocess_with_file_capture(
    command: str,
    timeout: int,
    cwd: str | Path,
) -> tuple[int, str, str, bool]:
    """
    Run a subprocess with file-based output capture to avoid Windows pipe deadlock.

    On Windows, subprocess.run() with capture_output=True can deadlock when the
    subprocess outputs more data than the pipe buffer can hold (~4KB). This happens
    because:
    1. The subprocess writes to stdout/stderr pipes
    2. When buffers fill, the subprocess blocks waiting for the parent to read
    3. But subprocess.run() doesn't read until the process completes
    4. Result: deadlock where child waits for parent to read, parent waits for child to exit

    This function avoids the deadlock by redirecting output to temporary files instead
    of pipes. Files have no buffer limit, so the subprocess never blocks.

    Args:
        command: Shell command to execute
        timeout: Maximum seconds to wait
        cwd: Working directory for the subprocess

    Returns:
        Tuple of (exit_code, stdout, stderr, timed_out)

    Educational Note:
        This is a well-known Windows issue. Python's subprocess documentation
        recommends using Popen.communicate() for large output, but even that
        can have issues on Windows. File-based capture is the most reliable
        cross-platform solution for commands that produce significant output.

    Reference:
        - https://docs.python.org/3/library/subprocess.html#subprocess.Popen.communicate
        - Issue #238: Pre-push hook intermittent timeouts
    """
    # Create temporary files for stdout and stderr using mkstemp
    # NamedTemporaryFile has Windows issues with reopening, so we use mkstemp
    # which gives us a file descriptor and path that we fully control
    stdout_fd, stdout_path = tempfile.mkstemp(suffix=".stdout.txt", text=True)
    stderr_fd, stderr_path = tempfile.mkstemp(suffix=".stderr.txt", text=True)

    # Close the file descriptors immediately - we'll reopen with proper encoding
    os.close(stdout_fd)
    os.close(stderr_fd)

    try:
        # Open files for subprocess to write to
        with open(stdout_path, "w", encoding="utf-8") as stdout_f:
            with open(stderr_path, "w", encoding="utf-8") as stderr_f:
                try:
                    # Build environment with reduced log noise but preserving test output
                    # Issue #255: JUnit XML parsing is primary source for counts (immune to
                    # stdout pollution), but we keep stdout for debugging failures
                    test_env = {
                        **os.environ,
                        "PYTHONUNBUFFERED": "1",
                        # Reduce structlog noise (only errors) - warnings were polluting stdout
                        # but keep failure output visible for debugging
                        "STRUCTLOG_LOG_LEVEL": "WARNING",
                        # Set precog logger to WARNING to reduce integration test noise
                        "LOG_LEVEL": "WARNING",
                    }
                    result = subprocess.run(
                        command,
                        shell=True,
                        stdout=stdout_f,
                        stderr=stderr_f,
                        timeout=timeout,
                        cwd=str(cwd),
                        text=True,
                        env=test_env,
                    )
                    exit_code = result.returncode
                    timed_out = False

                except subprocess.TimeoutExpired:
                    exit_code = -1
                    timed_out = True

        # Read output from files
        with open(stdout_path, encoding="utf-8", errors="replace") as f:
            stdout = f.read()
        with open(stderr_path, encoding="utf-8", errors="replace") as f:
            stderr = f.read()

        return exit_code, stdout, stderr, timed_out

    finally:
        # Clean up temporary files
        try:
            os.unlink(stdout_path)
        except OSError:
            pass
        try:
            os.unlink(stderr_path)
        except OSError:
            pass


# Timeout for the entire parallel phase (15 minutes)
TOTAL_TIMEOUT = 900

# 5-Phase Test Strategy Configuration (Optimized with A+C1 Parallelization)
# This prevents database connection pool exhaustion by running tests in phases
# with DB pool reset between phases. See Issue #202 for discovery context.
#
# Optimization (2025-12-13): Non-DB property tests run in PARALLEL with unit tests
# - Phase A + C1 run together (neither needs DB) -> saves ~43s
# - DB property tests (28 tests with @pytest.mark.database) run after pool reset
# - See TESTING_STRATEGY V3.7 Section 12 for pattern documentation
#
# Test marker convention:
# - Property tests WITH database access: add `pytestmark = pytest.mark.database`
# - Property tests WITHOUT database: no marker needed (default)
# - Slow tests (scheduler integration): add `pytestmark = pytest.mark.slow`
#
# Performance Optimization (2025-12-20):
# - Local pre-push: Skip slow tests (saves ~5-10 min from scheduler tests)
# - CI: Runs ALL tests including slow ones (full validation)
# - Use --run-slow to include slow tests locally if needed
SKIP_SLOW_TESTS = True  # Default: skip slow tests in local pre-push for faster feedback

TEST_PHASES: list[tuple[str, str, list[str], str | None]] = [
    # Phase A+C1: Unit tests + Non-DB property tests (PARALLEL - neither needs DB)
    # This saves ~43s by running these concurrently
    (
        "Phase A+C1",
        "Unit + Non-DB Property Tests (parallel)",
        ["tests/unit/", "tests/property/"],
        '-m "not database"',  # Exclude DB-dependent property tests (double quotes for Windows)
    ),
    # Phase B: Integration + E2E tests (heavy DB usage)
    # NOTE: Slow tests (scheduler integration) skipped by default - see SKIP_SLOW_TESTS
    (
        "Phase B",
        "Integration + E2E Tests",
        ["tests/integration/", "tests/e2e/"],
        '-m "not slow"' if SKIP_SLOW_TESTS else None,  # Skip slow scheduler tests locally
    ),
    # Phase C2: DB-dependent property tests (need pool reset)
    # Only 28 tests across 3 files with @pytest.mark.database
    (
        "Phase C2",
        "DB Property Tests",
        ["tests/property/"],
        '-m "database"',  # Only DB-dependent property tests (double quotes for Windows)
    ),
    # Phase D: Remaining tests (stress, race_condition, performance)
    (
        "Phase D",
        "Stress/Race/Performance Tests",
        ["tests/stress/", "tests/race_condition/", "tests/performance/"],
        None,  # No marker filter
    ),
]


@dataclass
class PhaseResult:
    """Result of a single test phase (for detailed tracking)."""

    phase_id: str
    phase_name: str
    test_dirs: list[str]
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration: float = 0.0
    exit_code: int = 0
    failed_tests: list[str] = field(default_factory=list)
    junit_file: str | None = None


@dataclass
class CheckResult:
    """Result of a single validation check."""

    step: int
    name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False
    # Enhanced fields for CI parity
    phase_results: list[PhaseResult] = field(default_factory=list)
    total_passed: int = 0
    total_failed: int = 0
    total_errors: int = 0
    total_skipped: int = 0


def reset_db_pool() -> bool:
    """
    Reset database connection pool between test phases.

    This prevents connection exhaustion when running many test phases.
    Calls the precog database module to close and reinitialize the pool.

    Returns:
        True if reset succeeded (or no pool to reset), False on error

    Educational Note:
        PostgreSQL has limited connections (default 100). When tests don't
        properly release connections, the pool gets exhausted. This reset
        ensures each phase starts with a fresh pool.
    """
    try:
        # Import inside function to avoid import errors if DB not configured
        from precog.database.connection import close_pool, initialize_pool

        try:
            close_pool()
        except Exception:
            pass  # Pool might not be initialized yet

        initialize_pool()
        return True

    except ImportError:
        # DB module not available - that's OK, tests may not need it
        return True
    except Exception as e:
        print(f"  Warning: DB pool reset failed: {e}")
        return False


def parse_junit_xml(junit_path: Path) -> tuple[int, int, int, int] | None:
    """
    Parse JUnit XML file to extract test counts.

    This is more reliable than parsing stdout because:
    1. JUnit XML is a structured format with defined attributes
    2. Not affected by log output, warnings, or other stdout pollution
    3. Used by CI systems (GitHub Actions, Jenkins) for reporting

    Args:
        junit_path: Path to the JUnit XML file

    Returns:
        Tuple of (passed, failed, errors, skipped) or None if parsing fails

    Educational Note:
        JUnit XML format has a <testsuite> root element with these attributes:
        - tests: Total number of tests
        - failures: Tests that failed assertions
        - errors: Tests that raised exceptions
        - skipped: Tests that were skipped
        - Passed tests = tests - failures - errors - skipped

    Reference:
        - Issue #255: Pre-push stdout parsing vulnerability
        - JUnit XML Schema: https://llg.cubic.org/docs/junit/
    """
    if not junit_path.exists():
        return None

    try:
        # Note: We're parsing our own generated JUnit XML files from pytest,
        # not untrusted external data. These files are created by pytest's
        # --junitxml flag in the same process flow.
        tree = ET.parse(junit_path)
        root = tree.getroot()

        # Handle both single testsuite and testsuites container
        if root.tag == "testsuites":
            # Sum up all testsuites
            total_tests = 0
            total_failures = 0
            total_errors = 0
            total_skipped = 0
            for testsuite in root.findall("testsuite"):
                total_tests += int(testsuite.get("tests", 0))
                total_failures += int(testsuite.get("failures", 0))
                total_errors += int(testsuite.get("errors", 0))
                total_skipped += int(testsuite.get("skipped", 0))
        else:
            # Single testsuite (pytest default)
            total_tests = int(root.get("tests", 0))
            total_failures = int(root.get("failures", 0))
            total_errors = int(root.get("errors", 0))
            total_skipped = int(root.get("skipped", 0))

        # Calculate passed tests
        passed = total_tests - total_failures - total_errors - total_skipped

        return (passed, total_failures, total_errors, total_skipped)

    except ET.ParseError as e:
        print(f"  Warning: Failed to parse JUnit XML {junit_path}: {e}")
        return None
    except Exception as e:
        print(f"  Warning: Error reading JUnit XML {junit_path}: {e}")
        return None


def run_tests_in_phases(timeout: int = CHECK_TIMEOUT) -> CheckResult:
    """
    Run all tests in optimized phases with DB pool reset between DB-heavy phases.

    This is the optimized 4-phase test strategy that:
    1. Runs non-DB tests in parallel (Phase A+C1: unit + non-DB property tests)
    2. Prevents database connection pool exhaustion for DB-heavy phases
    3. Saves ~43s by parallelizing tests that don't need DB
    4. Generates JUnit XML reports for each phase (CI parity - Issue #238)

    Args:
        timeout: Maximum seconds per phase

    Returns:
        CheckResult with aggregated results from all phases

    Educational Note:
        Running all tests in a single pytest invocation can exhaust the
        database connection pool because:
        1. Integration tests hold connections during setup/teardown
        2. Stress tests intentionally test pool limits
        3. Property tests run hundreds of iterations
        4. Connections may not be released between test classes

        Optimization (2025-12-13): Non-DB property tests are marked with
        `pytestmark = pytest.mark.database` and filtered using `-m database`
        or `-m 'not database'` to enable parallel execution with unit tests.

        CI Parity (2025-12-24): JUnit XML reports generated per phase for
        consistent reporting between local pre-push and CI pipeline.
    """
    start_time = time.time()
    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_skipped = 0
    all_stdout = []
    all_stderr = []
    phase_results: list[PhaseResult] = []
    exit_codes: list[tuple[str, int]] = []

    # Ensure artifacts directory exists for JUnit XML files
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    print("  Running tests in optimized phases (A+C1 parallel, DB phases sequential)...")
    print(f"  JUnit XML reports will be saved to: {ARTIFACTS_DIR}")
    print()

    for phase_id, phase_name, test_dirs, marker_filter in TEST_PHASES:
        phase_start = time.time()

        # Check if test directories exist (skip if empty)
        existing_dirs = [d for d in test_dirs if (REPO_ROOT / d).exists()]
        if not existing_dirs:
            print(f"    [{phase_id}] {phase_name}: SKIPPED (no test directories)")
            continue

        # Generate JUnit XML filename for this phase (CI parity)
        junit_filename = f"prepush-{phase_id.lower().replace(' ', '-')}-results.xml"
        junit_path = ARTIFACTS_DIR / junit_filename

        # Build pytest command for this phase with JUnit XML output
        dirs_arg = " ".join(existing_dirs)
        command = f"python -m pytest {dirs_arg} --no-cov --tb=line -q --junitxml={junit_path}"

        # Add marker filter if specified (e.g., "-m 'not database'" or "-m 'database'")
        if marker_filter:
            command = f"{command} {marker_filter}"

        print(f"    [{phase_id}] {phase_name}: Running...")

        # Use file-based capture to avoid Windows pipe deadlock (Issue #238)
        exit_code, stdout, stderr, phase_timed_out = run_subprocess_with_file_capture(
            command=command,
            timeout=timeout,
            cwd=REPO_ROOT,
        )

        phase_duration = time.time() - phase_start

        if phase_timed_out:
            print(f"    [{phase_id}] {phase_name}: TIMEOUT after {timeout}s")
            all_stderr.append(f"=== {phase_id}: {phase_name} ===\nTIMEOUT after {timeout}s")
            exit_codes.append((phase_id, -1))
            total_errors += 1
            phase_results.append(
                PhaseResult(
                    phase_id=phase_id,
                    phase_name=phase_name,
                    test_dirs=existing_dirs,
                    errors=1,
                    duration=phase_duration,
                    exit_code=-1,
                )
            )
        else:
            # Parse test counts from JUnit XML (primary) or stdout (fallback)
            # JUnit XML is more reliable because it's not affected by log output
            # pollution from structlog or other libraries (Issue #255)
            passed = failed = errors = skipped = 0

            junit_counts = parse_junit_xml(junit_path)
            if junit_counts:
                # Use JUnit XML counts (most reliable)
                passed, failed, errors, skipped = junit_counts
            else:
                # Fallback to stdout parsing (legacy behavior)
                # This may be unreliable if logs corrupt stdout
                stdout_lines = stdout.strip().split("\n")
                last_line = stdout_lines[-1] if stdout_lines else ""

                # Extract counts from pytest summary (e.g., "970 passed, 2 skipped")
                if "passed" in last_line:
                    match = re.search(r"(\d+) passed", last_line)
                    if match:
                        passed = int(match.group(1))
                if "failed" in last_line:
                    match = re.search(r"(\d+) failed", last_line)
                    if match:
                        failed = int(match.group(1))
                if "error" in last_line:
                    match = re.search(r"(\d+) error", last_line)
                    if match:
                        errors = int(match.group(1))
                if "skipped" in last_line:
                    match = re.search(r"(\d+) skipped", last_line)
                    if match:
                        skipped = int(match.group(1))

            total_passed += passed
            total_failed += failed
            total_errors += errors
            total_skipped += skipped

            # Extract failed test names from output for immediate visibility
            failed_tests = []
            for line in stdout.split("\n"):
                # Match lines like "tests/...py::TestClass::test_name FAILED"
                if line.strip().endswith(" FAILED"):
                    failed_tests.append(line.strip().replace(" FAILED", ""))
                # Also match lines starting with "FAILED tests/..." (pytest summary format)
                elif line.strip().startswith("FAILED tests/"):
                    # Extract just the test path, stop at " - " if present
                    test_path = line.strip().replace("FAILED ", "").split(" - ")[0]
                    if test_path not in failed_tests:  # Deduplicate
                        failed_tests.append(test_path)

            status = "PASSED" if exit_code == 0 else "FAILED"
            print(
                f"    [{phase_id}] {phase_name}: {status} ({passed} passed, {failed} failed, {errors} errors) [{phase_duration:.1f}s]"
            )

            # Print failed test names immediately for easy identification
            if failed_tests:
                print(f"    [!] Failed tests in {phase_id}:")
                for test_name in failed_tests:
                    print(f"        - {test_name}")

            all_stdout.append(f"=== {phase_id}: {phase_name} ===\n{stdout}")
            if stderr:
                all_stderr.append(f"=== {phase_id}: {phase_name} ===\n{stderr}")

            exit_codes.append((phase_id, exit_code))

            # Track detailed phase result (CI parity)
            phase_results.append(
                PhaseResult(
                    phase_id=phase_id,
                    phase_name=phase_name,
                    test_dirs=existing_dirs,
                    passed=passed,
                    failed=failed,
                    errors=errors,
                    skipped=skipped,
                    duration=phase_duration,
                    exit_code=exit_code,
                    failed_tests=failed_tests,
                    junit_file=str(junit_path) if junit_path.exists() else None,
                )
            )

            # If phase failed, continue to next phase but record failure
            # This allows us to see ALL failures, not just the first

        # Reset DB pool between phases (except after last phase)
        if phase_id != "Phase D":
            reset_db_pool()
            print("    [DB] Connection pool reset")

    print()

    # Aggregate results
    total_duration = time.time() - start_time
    any_failed = any(rc != 0 for _, rc in exit_codes)

    return CheckResult(
        step=2,
        name="All 8 Test Types (optimized A+C1 parallel)",
        command="optimized-phase test strategy",
        exit_code=1 if any_failed else 0,
        stdout="\n\n".join(all_stdout),
        stderr="\n\n".join(all_stderr),
        duration=total_duration,
        timed_out=False,
        # Enhanced fields for CI parity
        phase_results=phase_results,
        total_passed=total_passed,
        total_failed=total_failed,
        total_errors=total_errors,
        total_skipped=total_skipped,
    )


# Define all parallel checks (steps 2-11)
# Each tuple: (step_number, name, command)
#
# NOTE: Tests (Step 2) are run SEQUENTIALLY in 4 phases with DB pool reset
# between phases to prevent connection exhaustion. The other checks (3-11)
# run in PARALLEL since they don't share database state.
PARALLEL_CHECKS: list[tuple[int, str, str]] = [
    # Step 2 is handled separately by run_tests_in_phases() - see below
    # This placeholder is kept for step numbering consistency but skipped in execution
    # Step 3: Type Checking (with incremental caching)
    # Mypy caches analysis results in .mypy_cache/ for faster subsequent runs
    # First run: ~20-30s, subsequent runs: ~5-10s (only re-checks changed files)
    (
        3,
        "Type Checking (Mypy, incremental)",
        "python -m mypy . --incremental --cache-dir .mypy_cache --exclude tests/ --exclude _archive/ --exclude venv/ --exclude .venv/ --ignore-missing-imports",
    ),
    # Step 4: Security Scan
    (
        4,
        "Security Scan (Ruff S-rules)",
        "python -m ruff check --select S --ignore S101,S110,S112,S607,S603,S602 --exclude tests/ --exclude _archive/ --exclude venv/ --quiet .",
    ),
    # Step 5: Warning Governance (--skip-pytest since tests already ran in Step 2)
    (
        5,
        "Warning Governance",
        "python scripts/check_warning_debt.py --skip-pytest",
    ),
    # Step 6: Code Quality
    (
        6,
        "Code Quality (CODE_REVIEW_TEMPLATE)",
        "python scripts/validate_code_quality.py",
    ),
    # Step 7: Security Patterns
    (
        7,
        "Security Patterns (SECURITY_REVIEW_CHECKLIST)",
        "python scripts/validate_security_patterns.py",
    ),
    # Step 8: SCD Type 2 Queries
    (
        8,
        "SCD Type 2 Queries (Pattern 2)",
        "python scripts/validate_scd_queries.py",
    ),
    # Step 9: Property Test Coverage
    (
        9,
        "Property Tests (Pattern 10)",
        "python scripts/validate_property_tests.py",
    ),
    # Step 10: Test Fixture Validation
    (
        10,
        "Test Fixtures (Pattern 13)",
        "python scripts/validate_test_fixtures.py",
    ),
    # Step 11: Test Type Coverage
    (
        11,
        "Test Type Coverage STRICT (TESTING_STRATEGY V3.2)",
        "python scripts/audit_test_type_coverage.py --strict",
    ),
]


def run_check(step: int, name: str, command: str, timeout: int = CHECK_TIMEOUT) -> CheckResult:
    """
    Run a single validation check with timeout.

    Uses file-based output capture to avoid Windows pipe deadlock issues.
    See run_subprocess_with_file_capture() for details on the deadlock problem.

    Args:
        step: Step number (2-11)
        name: Human-readable name of the check
        command: Shell command to execute
        timeout: Maximum seconds to wait

    Returns:
        CheckResult with exit code, output, and timing
    """
    start_time = time.time()

    try:
        # Use file-based capture to avoid Windows pipe deadlock (Issue #238)
        exit_code, stdout, stderr, timed_out = run_subprocess_with_file_capture(
            command=command,
            timeout=timeout,
            cwd=REPO_ROOT,
        )

        duration = time.time() - start_time

        if timed_out:
            return CheckResult(
                step=step,
                name=name,
                command=command,
                exit_code=-1,
                stdout=stdout,
                stderr=f"TIMEOUT: Check exceeded {timeout}s limit\n{stderr}",
                duration=duration,
                timed_out=True,
            )

        return CheckResult(
            step=step,
            name=name,
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration=duration,
        )

    except Exception as e:
        duration = time.time() - start_time
        return CheckResult(
            step=step,
            name=name,
            command=command,
            exit_code=-2,
            stdout="",
            stderr=f"ERROR: {e}",
            duration=duration,
        )


def run_all_checks_parallel(
    checks: list[tuple[int, str, str]],
    max_workers: int = 10,
    dry_run: bool = False,
) -> list[CheckResult]:
    """
    Run all checks in parallel using ThreadPoolExecutor.

    Args:
        checks: List of (step, name, command) tuples
        max_workers: Maximum concurrent checks
        dry_run: If True, just print what would run

    Returns:
        List of CheckResult objects
    """
    if dry_run:
        print("DRY RUN - would execute these checks in parallel:")
        for step, name, command in checks:
            print(f"  [{step}/11] {name}")
            print(f"          {command[:80]}...")
        return []

    results: list[CheckResult] = []
    start_time = time.time()

    print(f"Starting {len(checks)} checks in parallel (max {max_workers} concurrent)...")
    print()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all checks
        future_to_check: dict[Future[CheckResult], tuple[int, str]] = {}
        for step, name, command in checks:
            future = executor.submit(run_check, step, name, command)
            future_to_check[future] = (step, name)

        # Collect results as they complete
        for future in as_completed(future_to_check, timeout=TOTAL_TIMEOUT):
            step, name = future_to_check[future]
            try:
                result = future.result()
                results.append(result)

                # Print progress
                status = "PASSED" if result.exit_code == 0 else "FAILED"
                if result.timed_out:
                    status = "TIMEOUT"
                symbol = "[OK]" if result.exit_code == 0 else "[X]"
                print(
                    f"  {symbol} [{result.step}/11] {result.name} - {status} ({result.duration:.1f}s)"
                )

            except TimeoutError:
                print(f"  [X] [{step}/11] {name} - TIMEOUT (>{TOTAL_TIMEOUT}s)")
                results.append(
                    CheckResult(
                        step=step,
                        name=name,
                        command="",
                        exit_code=-1,
                        stdout="",
                        stderr=f"Global timeout exceeded ({TOTAL_TIMEOUT}s)",
                        duration=TOTAL_TIMEOUT,
                        timed_out=True,
                    )
                )

    total_duration = time.time() - start_time
    print()
    print(f"All checks completed in {total_duration:.1f}s")

    # Sort by step number for consistent output
    results.sort(key=lambda r: r.step)
    return results


def cleanup_old_logs(log_dir: Path, keep_count: int = 10) -> int:
    """
    Remove old log files, keeping only the most recent ones.

    Args:
        log_dir: Directory containing log files
        keep_count: Number of recent logs to keep (default: 10)

    Returns:
        Number of files deleted

    Educational Note:
        Pre-push logs can accumulate rapidly (20-25MB per run). Without cleanup,
        a developer running 100 test cycles would accumulate ~2GB of logs.
        This function maintains a rolling window of recent logs for debugging
        while preventing unbounded disk usage.
    """
    if not log_dir.exists():
        return 0

    deleted = 0

    # Clean up both .log and .json files (legacy format)
    for pattern in ["pre-push-*.log", "pre-push-*.json"]:
        log_files = sorted(log_dir.glob(pattern), key=lambda f: f.stat().st_mtime)

        # Calculate how many to delete
        files_to_delete = len(log_files) - keep_count
        if files_to_delete > 0:
            for log_file in log_files[:files_to_delete]:
                try:
                    log_file.unlink()
                    deleted += 1
                except OSError:
                    pass  # Ignore errors (file in use, permissions, etc.)

    return deleted


def generate_json_summary(
    results: list[CheckResult],
    branch: str,
    start_time: float,
    success: bool,
) -> Path:
    """
    Generate a machine-readable JSON summary of test results.

    This provides CI parity for local pre-push validation, enabling:
    1. Trend analysis over time (scripts/analyze_prepush_history.py)
    2. Consistent reporting format between local and CI
    3. Easy parsing by external tools (IDEs, dashboards)

    Args:
        results: List of CheckResult objects from all checks
        branch: Current git branch name
        start_time: Unix timestamp when validation started
        success: Whether all checks passed

    Returns:
        Path to the generated JSON file

    Educational Note:
        This JSON format mirrors the structure used in CI artifacts (Issue #238).
        Fields are intentionally verbose to support future analysis needs.
        The "phases" array provides drill-down capability for test failures.

    Reference:
        - CI parity: .github/workflows/ci.yml uses mikepenz/action-junit-report
        - Issue #238: JUnit enhancements for CI
        - Issue #174: Pre-push history analysis
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()
    duration = time.time() - start_time

    # Find the test result (step 2) for detailed phase info
    test_result = next((r for r in results if r.step == 2), None)

    # Build phase summary
    phases = []
    if test_result and test_result.phase_results:
        for pr in test_result.phase_results:
            phases.append(
                {
                    "phase_id": pr.phase_id,
                    "phase_name": pr.phase_name,
                    "test_dirs": pr.test_dirs,
                    "passed": pr.passed,
                    "failed": pr.failed,
                    "errors": pr.errors,
                    "skipped": pr.skipped,
                    "duration_seconds": round(pr.duration, 2),
                    "exit_code": pr.exit_code,
                    "failed_tests": pr.failed_tests,
                    "junit_file": pr.junit_file,
                }
            )

    # Build check summary (steps 3-11)
    other_checks = []
    for r in results:
        if r.step != 2:
            other_checks.append(
                {
                    "step": r.step,
                    "name": r.name,
                    "passed": r.exit_code == 0,
                    "duration_seconds": round(r.duration, 2),
                    "timed_out": r.timed_out,
                }
            )

    # Aggregate test counts
    total_passed = test_result.total_passed if test_result else 0
    total_failed = test_result.total_failed if test_result else 0
    total_errors = test_result.total_errors if test_result else 0
    total_skipped = test_result.total_skipped if test_result else 0

    # Collect all failed test names across phases
    all_failed_tests = []
    if test_result and test_result.phase_results:
        for pr in test_result.phase_results:
            all_failed_tests.extend(pr.failed_tests)

    summary = {
        "timestamp": timestamp.isoformat(),
        "branch": branch,
        "success": success,
        "duration_seconds": round(duration, 2),
        "tests": {
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_errors": total_errors,
            "total_skipped": total_skipped,
            "total": total_passed + total_failed + total_errors,
        },
        "phases": phases,
        "other_checks": other_checks,
        "failed_tests": all_failed_tests[:50],  # Limit to avoid huge files
        "junit_files": [p["junit_file"] for p in phases if p.get("junit_file")],
        "artifacts_dir": str(ARTIFACTS_DIR),
    }

    # Write JSON summary
    json_filename = f"prepush-summary-{timestamp.strftime('%Y%m%d-%H%M%S')}.json"
    json_path = ARTIFACTS_DIR / json_filename

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Also write a "latest" symlink/copy for easy access
    latest_path = ARTIFACTS_DIR / "prepush-summary-latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"  JSON summary: {json_path}")
    return json_path


def print_summary(results: list[CheckResult], log_dir: Path | None = None) -> bool:
    """
    Print summary of all check results.

    Args:
        results: List of CheckResult objects
        log_dir: Optional directory to save detailed logs

    Returns:
        True if all checks passed, False otherwise
    """
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = []
    failed = []

    for result in results:
        if result.exit_code == 0:
            passed.append(result)
            print(f"  [OK] [{result.step}/11] {result.name}")
        else:
            failed.append(result)
            status = "TIMEOUT" if result.timed_out else "FAILED"
            print(f"  [X]  [{result.step}/11] {result.name} - {status}")

    print()
    print(f"Passed: {len(passed)}/{len(results)}")
    print(f"Failed: {len(failed)}/{len(results)}")

    if failed:
        print()
        print("=" * 60)
        print("FAILURE DETAILS")
        print("=" * 60)

        for result in failed:
            print()
            print(f"--- [{result.step}/11] {result.name} ---")
            print(f"Command: {result.command}")
            print(f"Exit code: {result.exit_code}")
            if result.timed_out:
                print("Status: TIMEOUT")
            if result.stderr:
                print("STDERR (last 30 lines):")
                stderr_lines = result.stderr.strip().split("\n")
                for line in stderr_lines[-30:]:
                    print(f"  {line}")
            if result.stdout:
                print("STDOUT (last 30 lines):")
                stdout_lines = result.stdout.strip().split("\n")
                for line in stdout_lines[-30:]:
                    print(f"  {line}")

        # Save detailed logs
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            log_file = log_dir / f"pre-push-{timestamp}.log"

            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Pre-push validation failed at {datetime.now()}\n")
                f.write(f"Passed: {len(passed)}, Failed: {len(failed)}\n\n")

                for result in failed:
                    f.write("=" * 60 + "\n")
                    f.write(f"[{result.step}/11] {result.name}\n")
                    f.write(f"Command: {result.command}\n")
                    f.write(f"Exit code: {result.exit_code}\n")
                    f.write(f"Duration: {result.duration:.1f}s\n")
                    f.write(f"Timed out: {result.timed_out}\n")
                    f.write("\nSTDOUT:\n")
                    f.write(result.stdout or "(empty)")
                    f.write("\n\nSTDERR:\n")
                    f.write(result.stderr or "(empty)")
                    f.write("\n\n")

            print()
            print(f"Detailed logs saved to: {log_file}")

    return len(failed) == 0


def get_current_branch() -> str:
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run pre-push validation checks in parallel (Windows-safe)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be executed without running",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Maximum concurrent workers (default: 10)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=REPO_ROOT / ".pre-push-logs",
        help="Directory for detailed failure logs",
    )

    args = parser.parse_args()

    # Record start time for JSON summary (CI parity)
    validation_start_time = time.time()

    # Get branch name for reporting
    branch = get_current_branch()

    # Clean up old logs before running (keep last 10)
    deleted = cleanup_old_logs(args.log_dir, keep_count=10)

    # Also clean old artifacts (keep last 20 runs for each type)
    # Clean JSON summaries
    artifact_patterns = [
        "prepush-summary-*.json",  # JSON summaries
        "prepush-*.xml",  # JUnit XML reports
    ]
    artifacts_deleted = 0
    for pattern in artifact_patterns:
        if ARTIFACTS_DIR.exists():
            old_files = sorted(ARTIFACTS_DIR.glob(pattern), key=lambda f: f.stat().st_mtime)
            for old_file in old_files[:-20]:  # Keep last 20 of each type
                try:
                    old_file.unlink()
                    artifacts_deleted += 1
                except OSError:
                    pass

    print()
    print("=" * 60)
    print("Pre-Push Parallel Check Runner (Python)")
    print("=" * 60)
    print(f"Repository: {REPO_ROOT}")
    print(f"Branch: {branch}")
    print(f"Workers: {args.workers}")
    print(f"Check timeout: {CHECK_TIMEOUT}s per check")
    print(f"Total timeout: {TOTAL_TIMEOUT}s")
    print(f"Artifacts: {ARTIFACTS_DIR}")
    if deleted > 0 or artifacts_deleted > 0:
        cleanup_msg = []
        if deleted > 0:
            cleanup_msg.append(f"{deleted} old logs")
        if artifacts_deleted > 0:
            cleanup_msg.append(f"{artifacts_deleted} old artifacts")
        print(f"Cleanup: Removed {', '.join(cleanup_msg)} (keeping last 10/20)")
    print()

    if args.dry_run:
        print("DRY RUN - would execute:")
        print()
        print("Step 2: Run tests in optimized phases (A+C1 parallel, DB phases sequential)")
        for phase_id, phase_name, test_dirs, marker_filter in TEST_PHASES:
            filter_str = f" ({marker_filter})" if marker_filter else ""
            print(f"  [{phase_id}] {phase_name}: {', '.join(test_dirs)}{filter_str}")
        print()
        print("Steps 3-11: Run in parallel:")
        for step, name, command in PARALLEL_CHECKS:
            print(f"  [{step}/11] {name}")
        return 0

    # Step 2: Run all tests in optimized phases (A+C1 parallel, DB sequential)
    # This prevents connection pool exhaustion while saving ~43s
    print("[2/11] Running All 8 Test Types (optimized A+C1 parallel)")
    print("-" * 60)
    test_result = run_tests_in_phases()
    print("-" * 60)

    # Steps 3-11: Run other checks in parallel
    print()
    print("[3-11/11] Running other checks in parallel...")
    print("-" * 60)
    parallel_results = run_all_checks_parallel(
        PARALLEL_CHECKS,
        max_workers=args.workers,
        dry_run=False,
    )
    print("-" * 60)

    # Combine results
    results = [test_result] + parallel_results

    # Print summary
    all_passed = print_summary(results, args.log_dir)

    # Generate JSON summary for CI parity and trend analysis
    print()
    print("-" * 60)
    print("Generating artifacts (CI parity)...")
    generate_json_summary(
        results=results,
        branch=branch,
        start_time=validation_start_time,
        success=all_passed,
    )
    print("-" * 60)

    if all_passed:
        print()
        print("=" * 60)
        print("[OK] All pre-push checks passed!")
        print(f"     Artifacts: {ARTIFACTS_DIR}")
        print("=" * 60)
        return 0

    print()
    print("=" * 60)
    print("[X] Pre-push validation FAILED")
    print("    Fix the issues above and try again.")
    print("    To bypass (NOT RECOMMENDED): git push --no-verify")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
