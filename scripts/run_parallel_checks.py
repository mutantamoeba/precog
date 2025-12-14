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
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from concurrent.futures import Future

# Repository root (script is in scripts/)
REPO_ROOT = Path(__file__).parent.parent

# Timeout for individual checks (8 minutes - allows for full test suite)
CHECK_TIMEOUT = 480

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
    (
        "Phase B",
        "Integration + E2E Tests",
        ["tests/integration/", "tests/e2e/"],
        None,  # No marker filter
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


def run_tests_in_phases(timeout: int = CHECK_TIMEOUT) -> CheckResult:
    """
    Run all tests in optimized phases with DB pool reset between DB-heavy phases.

    This is the optimized 4-phase test strategy that:
    1. Runs non-DB tests in parallel (Phase A+C1: unit + non-DB property tests)
    2. Prevents database connection pool exhaustion for DB-heavy phases
    3. Saves ~43s by parallelizing tests that don't need DB

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
    """
    start_time = time.time()
    total_passed = 0
    total_failed = 0
    total_errors = 0
    all_stdout = []
    all_stderr = []
    phase_results = []

    print("  Running tests in optimized phases (A+C1 parallel, DB phases sequential)...")
    print()

    for phase_id, phase_name, test_dirs, marker_filter in TEST_PHASES:
        phase_start = time.time()

        # Check if test directories exist (skip if empty)
        existing_dirs = [d for d in test_dirs if (REPO_ROOT / d).exists()]
        if not existing_dirs:
            print(f"    [{phase_id}] {phase_name}: SKIPPED (no test directories)")
            continue

        # Build pytest command for this phase
        dirs_arg = " ".join(existing_dirs)
        command = f"python -m pytest {dirs_arg} --no-cov --tb=line -q"

        # Add marker filter if specified (e.g., "-m 'not database'" or "-m 'database'")
        if marker_filter:
            command = f"{command} {marker_filter}"

        print(f"    [{phase_id}] {phase_name}: Running...")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=timeout,
                cwd=str(REPO_ROOT),
                text=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

            phase_duration = time.time() - phase_start

            # Parse pytest output for pass/fail counts
            stdout_lines = result.stdout.strip().split("\n")
            last_line = stdout_lines[-1] if stdout_lines else ""

            # Extract counts from pytest summary (e.g., "970 passed, 2 skipped")
            passed = failed = errors = 0
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

            total_passed += passed
            total_failed += failed
            total_errors += errors

            status = "PASSED" if result.returncode == 0 else "FAILED"
            print(
                f"    [{phase_id}] {phase_name}: {status} ({passed} passed, {failed} failed, {errors} errors) [{phase_duration:.1f}s]"
            )

            all_stdout.append(f"=== {phase_id}: {phase_name} ===\n{result.stdout}")
            if result.stderr:
                all_stderr.append(f"=== {phase_id}: {phase_name} ===\n{result.stderr}")

            phase_results.append((phase_id, result.returncode))

            # If phase failed, continue to next phase but record failure
            # This allows us to see ALL failures, not just the first

        except subprocess.TimeoutExpired:
            phase_duration = time.time() - phase_start
            print(f"    [{phase_id}] {phase_name}: TIMEOUT after {timeout}s")
            all_stderr.append(f"=== {phase_id}: {phase_name} ===\nTIMEOUT after {timeout}s")
            phase_results.append((phase_id, -1))
            total_errors += 1

        # Reset DB pool between phases (except after last phase)
        if phase_id != "Phase D":
            reset_db_pool()
            print("    [DB] Connection pool reset")

    print()

    # Aggregate results
    total_duration = time.time() - start_time
    any_failed = any(rc != 0 for _, rc in phase_results)

    return CheckResult(
        step=2,
        name="All 8 Test Types (optimized A+C1 parallel)",
        command="optimized-phase test strategy",
        exit_code=1 if any_failed else 0,
        stdout="\n\n".join(all_stdout),
        stderr="\n\n".join(all_stderr),
        duration=total_duration,
        timed_out=False,
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
    # Step 5: Warning Governance
    (
        5,
        "Warning Governance",
        "python scripts/check_warning_debt.py",
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
        # Run the command with timeout
        # shell=True is needed for complex commands with pipes/redirects
        # We're running our own trusted scripts, so this is safe
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
            text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        duration = time.time() - start_time

        return CheckResult(
            step=step,
            name=name,
            command=command,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration=duration,
        )

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return CheckResult(
            step=step,
            name=name,
            command=command,
            exit_code=-1,
            stdout="",
            stderr=f"TIMEOUT: Check exceeded {timeout}s limit",
            duration=duration,
            timed_out=True,
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

    print()
    print("=" * 60)
    print("Pre-Push Parallel Check Runner (Python)")
    print("=" * 60)
    print(f"Repository: {REPO_ROOT}")
    print(f"Workers: {args.workers}")
    print(f"Check timeout: {CHECK_TIMEOUT}s per check")
    print(f"Total timeout: {TOTAL_TIMEOUT}s")
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

    if all_passed:
        print()
        print("=" * 60)
        print("[OK] All pre-push checks passed!")
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
