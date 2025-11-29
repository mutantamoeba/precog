"""
Validation Execution Monitor

Tracks validation script runtimes, detects inefficiencies, and logs results.
Provides historical analysis to identify performance degradation.

Usage:
    # Run with timing and logging
    python scripts/validation_monitor.py --run validate_quick.sh

    # View historical performance
    python scripts/validation_monitor.py --history

    # Check for inefficiencies
    python scripts/validation_monitor.py --analyze

    # Run as pre-push wrapper (recommended)
    python scripts/validation_monitor.py --prepush

Reference: docs/guides/DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
Related ADR: ADR-TBD (Validation Infrastructure Monitoring)
Related REQ: REQ-CICD-010 (Validation Execution Monitoring)
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Thresholds for performance warnings (seconds)
THRESHOLDS = {
    "validate_quick.sh": 10,  # Should complete in <10s
    "validate_all.sh": 120,  # Should complete in <2min
    "test_fast.sh": 30,  # Should complete in <30s
    "test_full.sh": 120,  # Should complete in <2min
    "pre-push": 180,  # Total pre-push should complete in <3min
    "individual_test": 60,  # Individual test timeout (per-test)
}

# Performance degradation threshold (percentage above historical average)
DEGRADATION_THRESHOLD = 50  # Warn if 50% slower than historical average

# Log file location
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "validation_runs.json"
SUMMARY_FILE = LOG_DIR / "validation_summary.txt"


def ensure_log_dir():
    """Create logs directory if it doesn't exist."""
    LOG_DIR.mkdir(exist_ok=True)


def load_history() -> list[dict]:
    """Load historical validation runs from JSON file."""
    if LOG_FILE.exists():
        with open(LOG_FILE, encoding="utf-8") as f:
            data: list[dict] = json.load(f)
            return data
    return []


def save_history(history: list[dict]):
    """Save historical validation runs to JSON file."""
    ensure_log_dir()
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, default=str)


def log_run(script: str, duration: float, success: bool, output: str = ""):
    """Log a validation run result."""
    history = load_history()

    run_record = {
        "timestamp": datetime.now().isoformat(),
        "script": script,
        "duration_seconds": round(duration, 2),
        "success": success,
        "output_lines": len(output.splitlines()) if output else 0,
    }

    history.append(run_record)

    # Keep last 100 runs per script to prevent unbounded growth
    script_runs = [r for r in history if r["script"] == script]
    if len(script_runs) > 100:
        # Remove oldest runs for this script
        oldest_timestamps = sorted(r["timestamp"] for r in script_runs)[:-100]
        history = [
            r
            for r in history
            if not (r["script"] == script and r["timestamp"] in oldest_timestamps)
        ]

    save_history(history)

    # Also append to human-readable summary
    ensure_log_dir()
    with open(SUMMARY_FILE, "a", encoding="utf-8") as f:
        status = "PASS" if success else "FAIL"
        f.write(f"{run_record['timestamp']} | {script:25} | {duration:7.2f}s | {status}\n")


def get_historical_average(script: str) -> float | None:
    """Get the historical average runtime for a script."""
    history = load_history()
    script_runs = [r for r in history if r["script"] == script and r["success"]]

    if len(script_runs) < 3:
        return None  # Not enough data

    durations: list[float] = [
        r["duration_seconds"] for r in script_runs[-20:]
    ]  # Last 20 successful runs
    return float(sum(durations) / len(durations))


def check_performance(script: str, duration: float) -> list[str]:
    """Check for performance issues and return warnings."""
    warnings = []

    # Check against absolute threshold
    threshold = THRESHOLDS.get(script, 300)  # Default 5min
    if duration > threshold:
        warnings.append(f"SLOW: {script} took {duration:.1f}s (threshold: {threshold}s)")

    # Check against historical average
    avg = get_historical_average(script)
    if avg:
        degradation = ((duration - avg) / avg) * 100
        if degradation > DEGRADATION_THRESHOLD:
            warnings.append(
                f"DEGRADATION: {script} is {degradation:.0f}% slower than average "
                f"({duration:.1f}s vs {avg:.1f}s historical)"
            )

    return warnings


def run_script(script_path: str, capture_output: bool = True) -> tuple[bool, float, str]:
    """
    Run a script with timing and capture output.

    Returns:
        Tuple of (success, duration_seconds, output)
    """
    start_time = time.perf_counter()

    try:
        if script_path.endswith(".sh"):
            cmd = ["bash", script_path]
        elif script_path.endswith(".py"):
            cmd = [sys.executable, script_path]
        else:
            cmd = [script_path]

        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=600,  # 10 minute absolute max
        )

        duration = time.perf_counter() - start_time
        success = result.returncode == 0
        output = result.stdout + result.stderr

        return success, duration, output

    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - start_time
        return False, duration, "TIMEOUT: Script exceeded 600s limit"

    except Exception as e:
        duration = time.perf_counter() - start_time
        return False, duration, f"ERROR: {e}"


def run_with_monitoring(script: str) -> int:
    """Run a validation script with full monitoring."""
    script_name = Path(script).name

    print(f"\n{'=' * 60}")
    print(f"VALIDATION MONITOR: Running {script_name}")
    print(f"{'=' * 60}\n")

    # Run the script
    success, duration, output = run_script(script)

    # Log the run
    log_run(script_name, duration, success, output)

    # Check for performance issues
    warnings = check_performance(script_name, duration)

    # Print output
    print(output)

    # Print timing and warnings
    print(f"\n{'=' * 60}")
    print("EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Script: {script_name}")
    print(f"Duration: {duration:.2f}s")
    print(f"Status: {'PASS' if success else 'FAIL'}")

    if warnings:
        print("\n*** PERFORMANCE WARNINGS ***")
        for w in warnings:
            print(f"  - {w}")

    # Show historical context
    avg = get_historical_average(script_name)
    if avg:
        print(f"\nHistorical average: {avg:.2f}s")
        print(f"Variance: {((duration - avg) / avg) * 100:+.0f}%")

    print(f"{'=' * 60}\n")

    return 0 if success else 1


def show_history():
    """Display historical validation runs."""
    history = load_history()

    if not history:
        print("No validation history found.")
        print(f"Run some validations first, or check {LOG_FILE}")
        return

    print(f"\n{'=' * 70}")
    print("VALIDATION HISTORY (last 20 runs per script)")
    print(f"{'=' * 70}\n")

    # Group by script
    scripts = {r["script"] for r in history}

    for script in sorted(scripts):
        runs = [r for r in history if r["script"] == script][-20:]

        print(f"\n{script}:")
        print("-" * 50)

        success_runs = [r for r in runs if r["success"]]
        fail_runs = [r for r in runs if not r["success"]]

        if success_runs:
            durations = [r["duration_seconds"] for r in success_runs]
            avg = sum(durations) / len(durations)
            min_d = min(durations)
            max_d = max(durations)
            print(f"  Successful runs: {len(success_runs)}")
            print(f"  Average duration: {avg:.2f}s")
            print(f"  Range: {min_d:.2f}s - {max_d:.2f}s")

        if fail_runs:
            print(f"  Failed runs: {len(fail_runs)}")

        # Show recent trend
        recent = runs[-5:]
        print("  Recent runs:")
        for r in recent:
            status = "PASS" if r["success"] else "FAIL"
            ts = r["timestamp"][:16]  # Truncate to minute
            print(f"    {ts} | {r['duration_seconds']:6.2f}s | {status}")


def analyze_inefficiencies():
    """Analyze validation runs for inefficiencies."""
    history = load_history()

    if len(history) < 10:
        print("Not enough history for analysis (need at least 10 runs).")
        return

    print(f"\n{'=' * 70}")
    print("INEFFICIENCY ANALYSIS")
    print(f"{'=' * 70}\n")

    scripts = {r["script"] for r in history}
    issues_found = False

    for script in sorted(scripts):
        runs = [r for r in history if r["script"] == script]
        success_runs = [r for r in runs if r["success"]]

        if len(success_runs) < 5:
            continue

        durations = [r["duration_seconds"] for r in success_runs]

        # Check for increasing trend (last 10 runs)
        recent = durations[-10:]
        if len(recent) >= 5:
            first_half = sum(recent[: len(recent) // 2]) / (len(recent) // 2)
            second_half = sum(recent[len(recent) // 2 :]) / (len(recent) - len(recent) // 2)

            if second_half > first_half * 1.2:
                issues_found = True
                print(f"TREND WARNING: {script}")
                print("  Recent runs are getting slower!")
                print(f"  First half avg: {first_half:.2f}s")
                print(f"  Second half avg: {second_half:.2f}s")
                print(f"  Increase: {((second_half - first_half) / first_half) * 100:.0f}%")
                print()

        # Check for high variance (inconsistent performance)
        if len(durations) >= 5:
            avg = sum(durations) / len(durations)
            variance = sum((d - avg) ** 2 for d in durations) / len(durations)
            std_dev = variance**0.5
            cv = (std_dev / avg) * 100  # Coefficient of variation

            if cv > 30:  # >30% variation is concerning
                issues_found = True
                print(f"VARIANCE WARNING: {script}")
                print(f"  Inconsistent performance (CV: {cv:.0f}%)")
                print(f"  Average: {avg:.2f}s, Std Dev: {std_dev:.2f}s")
                print("  This may indicate flaky tests or resource contention")
                print()

        # Check threshold violations
        threshold = THRESHOLDS.get(script, 300)
        violations = [d for d in durations if d > threshold]
        if violations:
            issues_found = True
            print(f"THRESHOLD VIOLATIONS: {script}")
            print(f"  {len(violations)} runs exceeded {threshold}s threshold")
            print(f"  Worst: {max(violations):.2f}s")
            print()

    if not issues_found:
        print("No inefficiencies detected!")
        print("All scripts running within normal parameters.")


def run_prepush_monitored() -> int:
    """Run pre-push validation with full monitoring."""
    print(f"\n{'=' * 70}")
    print("PRE-PUSH VALIDATION (MONITORED)")
    print(f"{'=' * 70}\n")

    total_start = time.perf_counter()
    all_success = True
    step_timings = []

    # Define validation steps (mirrors pre-push hook)
    steps = [
        ("Quick Validation", "scripts/validate_quick.sh"),
        ("Unit Tests", "python -m pytest tests/unit/ -v --no-cov --tb=short -x --timeout=60"),
        (
            "Property Tests",
            "python -m pytest tests/property/ -v --no-cov --tb=short -x --timeout=60",
        ),
        ("Type Checking", "python -m mypy . --exclude tests/ --exclude _archive/ --exclude venv/"),
        (
            "Security Scan",
            "python -m ruff check --select S --ignore S101,S112,S607,S603 --exclude tests/ --quiet .",
        ),
    ]

    for step_name, cmd in steps:
        print(f"\n--- {step_name} ---")
        step_start = time.perf_counter()

        try:
            if cmd.startswith("python"):
                # Python command
                result = subprocess.run(
                    cmd.split(),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            else:
                # Shell script
                result = subprocess.run(
                    ["bash", cmd],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

            step_duration = time.perf_counter() - step_start
            success = result.returncode == 0

            if not success:
                print(result.stdout)
                print(result.stderr)
                all_success = False

            step_timings.append((step_name, step_duration, success))
            status = "PASS" if success else "FAIL"
            print(f"  {status} ({step_duration:.1f}s)")

        except subprocess.TimeoutExpired:
            step_duration = time.perf_counter() - step_start
            step_timings.append((step_name, step_duration, False))
            all_success = False
            print(f"  TIMEOUT after {step_duration:.1f}s")

    total_duration = time.perf_counter() - total_start

    # Log the run
    log_run("pre-push", total_duration, all_success)

    # Print summary
    print(f"\n{'=' * 70}")
    print("PRE-PUSH SUMMARY")
    print(f"{'=' * 70}")
    print("\nStep Timings:")
    for name, duration, success in step_timings:
        status = "PASS" if success else "FAIL"
        bar = "#" * int(duration / 2)  # Visual bar
        print(f"  {name:20} | {duration:6.1f}s | {status} | {bar}")

    print(f"\nTotal: {total_duration:.1f}s")
    print(f"Status: {'ALL PASSED' if all_success else 'FAILED'}")

    # Check for performance issues
    warnings = check_performance("pre-push", total_duration)
    if warnings:
        print("\n*** PERFORMANCE WARNINGS ***")
        for w in warnings:
            print(f"  - {w}")

    return 0 if all_success else 1


def main():
    parser = argparse.ArgumentParser(
        description="Validation Execution Monitor - Track and analyze validation performance"
    )

    parser.add_argument(
        "--run",
        metavar="SCRIPT",
        help="Run a validation script with monitoring (e.g., validate_quick.sh)",
    )

    parser.add_argument(
        "--history",
        action="store_true",
        help="Show historical validation runs",
    )

    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze for inefficiencies and performance issues",
    )

    parser.add_argument(
        "--prepush",
        action="store_true",
        help="Run pre-push validation with full monitoring",
    )

    args = parser.parse_args()

    if args.run:
        return run_with_monitoring(args.run)
    if args.history:
        show_history()
        return 0
    if args.analyze:
        analyze_inefficiencies()
        return 0
    if args.prepush:
        return run_prepush_monitored()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
