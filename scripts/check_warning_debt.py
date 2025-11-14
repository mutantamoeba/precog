#!/usr/bin/env python
"""
Warning Debt Validation Script (Multi-Source)

Compares current warning count against baseline across THREE validation systems:
1. pytest test warnings (Hypothesis, ResourceWarning, pytest-asyncio, etc.)
2. validate_docs.py warnings (YAML floats, MASTER_INDEX issues, ADR gaps)
3. Code quality (Ruff linting, Mypy type checking)

Prevents warning regression by enforcing zero-tolerance policy for new warnings.

Usage:
    python scripts/check_warning_debt.py                # Check against baseline
    python scripts/check_warning_debt.py --update       # Update baseline (requires manual approval)
    python scripts/check_warning_debt.py --report       # Generate detailed warning report

Exit Codes:
    0 - Warnings within baseline (pass)
    1 - Warnings exceed baseline (fail - regression detected)
    2 - Script error (baseline file missing, validation tools failed, etc.)

Integration:
    - Pre-push hook: Run before every push to prevent warning regression
    - CI/CD: GitHub Actions job to enforce zero-warning policy
    - Local development: Run before committing warning-prone changes

Example Output:
    [OK] Warning count: 429/429 (baseline maintained)
    [FAIL] Warning count: 432/429 (+3 new warnings - regression detected)
    [INFO] Breakdown by Source:
      - pytest: 41
      - validate_docs: 388 (YAML: 111, MASTER_INDEX: 38, ADR gaps: 231)
      - code_quality: 0 (Ruff: 0, Mypy: 0)

Related:
    - docs/utility/WARNING_DEBT_TRACKER.md - Warning categorization and deferred fixes
    - scripts/warning_baseline.json - Baseline configuration (429 warnings)
    - Pattern 9 in CLAUDE.md - Multi-Source Warning Governance
    - ADR-054 in ARCHITECTURE_DECISIONS - Warning Governance Architecture
"""

import json
import re
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


def load_baseline() -> dict:
    """Load warning baseline from JSON file."""
    baseline_path = Path("scripts/warning_baseline.json")

    if not baseline_path.exists():
        print("[ERROR] Baseline file not found: scripts/warning_baseline.json")
        print(
            "[INFO] Run 'python scripts/check_warning_debt.py --create-baseline' to create initial baseline"
        )
        sys.exit(2)

    try:
        with open(baseline_path, encoding="utf-8") as f:
            result: dict = json.load(f)
            return result
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in baseline file: {e}")
        sys.exit(2)


def run_pytest_with_warnings() -> tuple[str, int]:
    """Run pytest with warning capture enabled."""
    print("[INFO] Running pytest with warning detection...")

    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v", "-W", "default", "--tb=no"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        output = result.stdout + result.stderr
        return output, result.returncode

    except subprocess.TimeoutExpired:
        print("[ERROR] Pytest timed out after 5 minutes")
        sys.exit(2)
    except FileNotFoundError:
        print("[ERROR] pytest not found - is it installed?")
        print("[FIX] Run: pip install pytest")
        sys.exit(2)


def run_validate_docs() -> tuple[str, int]:
    """Run validate_docs.py to check documentation warnings."""
    print("[INFO] Running validate_docs.py...")

    try:
        result = subprocess.run(
            ["python", "scripts/validate_docs.py"],
            capture_output=True,
            text=True,
            timeout=60,  # 1 minute timeout
        )

        output = result.stdout + result.stderr
        return output, result.returncode

    except subprocess.TimeoutExpired:
        print("[ERROR] validate_docs.py timed out after 1 minute")
        sys.exit(2)
    except FileNotFoundError:
        print("[ERROR] validate_docs.py not found")
        sys.exit(2)


def run_ruff() -> tuple[str, int]:
    """Run Ruff linting check."""
    print("[INFO] Running Ruff linting...")

    try:
        result = subprocess.run(
            ["python", "-m", "ruff", "check", "."],
            capture_output=True,
            text=True,
            timeout=60,  # 1 minute timeout
        )

        output = result.stdout + result.stderr
        return output, result.returncode

    except subprocess.TimeoutExpired:
        print("[ERROR] Ruff timed out after 1 minute")
        sys.exit(2)
    except FileNotFoundError:
        print("[ERROR] Ruff not found - is it installed?")
        print("[FIX] Run: pip install ruff")
        sys.exit(2)


def run_mypy() -> tuple[str, int]:
    """Run Mypy type checking."""
    print("[INFO] Running Mypy type checking...")

    try:
        result = subprocess.run(
            ["python", "-m", "mypy", "."],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout (increased from 60s due to frequent timeouts on large codebases)
        )

        output = result.stdout + result.stderr
        return output, result.returncode

    except subprocess.TimeoutExpired:
        print("[ERROR] Mypy timed out after 2 minutes")
        sys.exit(2)
    except FileNotFoundError:
        print("[ERROR] Mypy not found - is it installed?")
        print("[FIX] Run: pip install mypy")
        sys.exit(2)


def extract_warning_count(output: str) -> int:
    """Extract warning count from pytest output."""
    # Look for pattern: "248 passed, 8 skipped, 41 warnings in 12.75s"
    match = re.search(r"(\d+) warnings? in", output)
    if match:
        return int(match.group(1))

    # If no warnings found, check if tests passed with 0 warnings
    if "0 warnings" in output or ("passed" in output and "warning" not in output):
        return 0

    print("[WARNING] Could not extract warning count from pytest output")
    print("[INFO] Assuming 0 warnings")
    return 0


def extract_validate_docs_warnings(output: str) -> dict[str, int]:
    """Extract warning counts from validate_docs.py output."""
    warnings = {
        "yaml_float_literals": 0,
        "master_index_missing": 0,
        "master_index_deleted": 0,
        "master_index_planned": 0,
        "adr_non_sequential": 0,
    }

    for line in output.split("\n"):
        if "Float detected in Decimal field" in line:
            warnings["yaml_float_literals"] += 1
        elif (
            "Document exists but not in index" in line
            or "Document exists but not in MASTER_INDEX" in line
        ):
            warnings["master_index_missing"] += 1
        elif "Document in index but does not exist" in line or "does not exist" in line:
            warnings["master_index_deleted"] += 1
        elif "Planned document" in line or "Status: Planned" in line:
            warnings["master_index_planned"] += 1
        elif "ADR gap detected" in line:
            warnings["adr_non_sequential"] += 1

    return warnings


def extract_ruff_errors(output: str) -> int:
    """Extract error count from Ruff output."""
    # Look for pattern: "Found X errors." or check for "All checks passed!"
    if "All checks passed!" in output or len(output.strip()) == 0:
        return 0

    match = re.search(r"Found (\d+) error", output)
    if match:
        return int(match.group(1))

    # Count individual error lines (format: "file.py:123:45: E001 Error message")
    error_lines = [line for line in output.split("\n") if re.match(r".*:\d+:\d+: [A-Z]\d+", line)]
    return len(error_lines)


def extract_mypy_errors(output: str) -> int:
    """Extract error count from Mypy output."""
    # Look for pattern: "Found X errors in Y files"
    match = re.search(r"Found (\d+) error", output)
    if match:
        return int(match.group(1))

    # If "Success: no issues found"
    if "Success: no issues found" in output:
        return 0

    # Count individual error lines (format: "file.py:123: error: Message")
    error_lines = [line for line in output.split("\n") if ": error:" in line]
    return len(error_lines)


def run_pytest_timed() -> tuple[str, int, int, dict[str, int], float]:
    """Run pytest with timing measurement.

    Returns:
        tuple: (output, returncode, warning_count, categories, duration_seconds)
    """
    start_time = time.time()
    output, returncode = run_pytest_with_warnings()
    duration = time.time() - start_time

    warning_count = extract_warning_count(output)
    categories = categorize_warnings(output)

    return output, returncode, warning_count, categories, duration


def run_validate_docs_timed() -> tuple[str, int, dict[str, int], float]:
    """Run validate_docs with timing measurement.

    Returns:
        tuple: (output, returncode, warnings_dict, duration_seconds)
    """
    start_time = time.time()
    output, returncode = run_validate_docs()
    duration = time.time() - start_time

    warnings = extract_validate_docs_warnings(output)

    return output, returncode, warnings, duration


def run_ruff_timed() -> tuple[str, int, int, float]:
    """Run Ruff with timing measurement.

    Returns:
        tuple: (output, returncode, error_count, duration_seconds)
    """
    start_time = time.time()
    output, returncode = run_ruff()
    duration = time.time() - start_time

    errors = extract_ruff_errors(output)

    return output, returncode, errors, duration


def run_mypy_timed() -> tuple[str, int, int, float]:
    """Run Mypy with timing measurement.

    Returns:
        tuple: (output, returncode, error_count, duration_seconds)
    """
    start_time = time.time()
    output, returncode = run_mypy()
    duration = time.time() - start_time

    errors = extract_mypy_errors(output)

    return output, returncode, errors, duration


def categorize_warnings(output: str) -> dict[str, int]:
    """Categorize warnings by type."""
    categories = {
        "hypothesis": 0,
        "pytest_asyncio": 0,
        "resource_warning": 0,
        "structlog": 0,
        "coverage": 0,
        "other": 0,
    }

    # Count each warning type
    for line in output.split("\n"):
        if "HypothesisDeprecationWarning" in line:
            categories["hypothesis"] += 1
        elif "pytest_asyncio" in line and "DeprecationWarning" in line:
            categories["pytest_asyncio"] += 1
        elif "ResourceWarning: unclosed file" in line:
            categories["resource_warning"] += 1
        elif "structlog" in line and "UserWarning" in line:
            categories["structlog"] += 1
        elif "CoverageWarning" in line:
            categories["coverage"] += 1
        elif any(
            w in line for w in ["Warning:", "DeprecationWarning", "UserWarning", "RuntimeWarning"]
        ) and not any(
            [
                "Hypothesis" in line,
                "pytest_asyncio" in line,
                "Resource" in line,
                "structlog" in line,
                "Coverage" in line,
            ]
        ):
            # Avoid double counting - only count if not already categorized
            categories["other"] += 1

    return {k: v for k, v in categories.items() if v > 0}


def check_baseline(
    current_counts: dict[str, int],
    baseline: dict,
    show_report: bool = False,
    timings: dict[str, float] | None = None,
) -> bool:
    """Check if current warning counts exceed baseline across all sources."""
    baseline_count = baseline["total_warnings"]
    max_allowed = baseline["governance_policy"]["max_warnings_allowed"]

    # Calculate total current warnings
    total_current = sum(current_counts.values())

    print(f"\n{'=' * 70}")
    print("WARNING DEBT CHECK (MULTI-SOURCE)")
    print(f"{'=' * 70}")
    print(f"Baseline Date: {baseline['baseline_date']}")
    print(f"Baseline Total: {baseline_count}")
    print(f"Current Total: {total_current}")
    print(f"Max Allowed: {max_allowed}")
    print(f"{'=' * 70}")

    # Show timing breakdown if provided
    if timings:
        total_time = sum(timings.values())
        print("\nPerformance Timing:")
        for source, duration in sorted(timings.items(), key=lambda x: x[1], reverse=True):
            percent = (duration / total_time * 100) if total_time > 0 else 0
            print(f"  {source:15s}: {duration:6.2f}s ({percent:5.1f}%)")
        print(f"  {'Total':15s}: {total_time:6.2f}s")
        print(f"{'=' * 70}")

    # Show breakdown by source
    print("\nBreakdown by Source:")
    print(f"  pytest: {current_counts.get('pytest', 0)}")
    print("  validate_docs:")
    print(f"    - YAML float literals: {current_counts.get('yaml_float_literals', 0)}")
    print(f"    - MASTER_INDEX missing: {current_counts.get('master_index_missing', 0)}")
    print(f"    - MASTER_INDEX deleted: {current_counts.get('master_index_deleted', 0)}")
    print(f"    - MASTER_INDEX planned: {current_counts.get('master_index_planned', 0)}")
    print(f"    - ADR non-sequential: {current_counts.get('adr_non_sequential', 0)}")
    print("  code_quality:")
    print(f"    - Ruff: {current_counts.get('ruff', 0)}")
    print(f"    - Mypy: {current_counts.get('mypy', 0)}")
    print(f"{'=' * 70}\n")

    if total_current <= max_allowed:
        delta = max_allowed - total_current
        print(f"[OK] Warning count: {total_current}/{max_allowed}")
        if delta > 0:
            print(f"[GOOD] {delta} warnings below baseline!")
            print("[ACTION] Consider updating baseline to lock in improvement")
        else:
            print("[OK] At baseline (no regression)")
        return True
    delta = total_current - max_allowed
    print(f"[FAIL] Warning count: {total_current}/{max_allowed} (+{delta} new warnings)")
    print("\n[ERROR] Warning regression detected!")
    print("[FIX] Options:")
    print("  1. Fix new warnings before merging")
    print("  2. Update baseline with approval (document in WARNING_DEBT_TRACKER.md)")
    print("\n[COMMAND] To see warnings:")
    print("  python -m pytest tests/ -v -W default --tb=no")
    print("  python scripts/validate_docs.py")
    print("  python -m ruff check .")
    print("  python -m mypy .")
    return False


def print_warning_report(categories: dict[str, int], baseline: dict):
    """Print detailed warning breakdown."""
    print(f"\n{'=' * 70}")
    print("WARNING BREAKDOWN")
    print(f"{'=' * 70}")

    baseline_categories = baseline["warning_categories"]

    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        # Get baseline count for this category
        baseline_count = 0
        for cat_name, cat_data in baseline_categories.items():
            if category in cat_name.lower():
                baseline_count = cat_data["count"]
                break

        delta_str = ""
        if baseline_count > 0:
            delta = count - baseline_count
            if delta > 0:
                delta_str = f" (+{delta} WORSE)"
            elif delta < 0:
                delta_str = f" ({delta} BETTER)"

        print(f"  - {category.replace('_', ' ').title()}: {count}{delta_str}")

    print(f"{'=' * 70}\n")


def update_baseline(current_count: int, categories: dict[str, int]):
    """Update baseline file (requires manual confirmation)."""
    baseline_path = Path("scripts/warning_baseline.json")

    # Load existing baseline
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    old_count = baseline["total_warnings"]
    delta = current_count - old_count

    print(f"\n[WARNING] Updating baseline: {old_count} → {current_count} ({delta:+d} warnings)")
    print("[ACTION] You MUST document this change in WARNING_DEBT_TRACKER.md")
    print("[ACTION] Include:")
    print("  1. Reason for new warnings")
    print("  2. Target phase for fixing them")
    print("  3. Estimated fix time")

    confirm = input("\nAre you sure you want to update the baseline? (yes/no): ")
    if confirm.lower() != "yes":
        print("[ABORTED] Baseline not updated")
        sys.exit(1)

    # Update baseline
    from datetime import datetime

    baseline["total_warnings"] = current_count
    baseline["governance_policy"]["max_warnings_allowed"] = current_count
    baseline["tracking"]["last_measured"] = datetime.now().isoformat() + "Z"

    # Save updated baseline
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)

    print(f"[OK] Baseline updated: {old_count} → {current_count}")
    print("[NEXT] Update docs/utility/WARNING_DEBT_TRACKER.md with new warnings")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check warning count against baseline (multi-source)"
    )
    parser.add_argument("--update", action="store_true", help="Update baseline (requires approval)")
    parser.add_argument("--report", action="store_true", help="Show detailed warning report")
    parser.add_argument("--create-baseline", action="store_true", help="Create initial baseline")
    args = parser.parse_args()

    # Run all validation sources in parallel
    print("\n[INFO] Running multi-source validation (parallel execution)...\n")

    # Initialize result variables
    pytest_count = 0
    pytest_categories = {}
    docs_warnings = {}
    ruff_errors = 0
    mypy_errors = 0
    timings = {}

    # Run all 4 validation sources concurrently
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all validation tasks
        future_to_source: dict[Future[Any], str] = {
            executor.submit(run_pytest_timed): "pytest",
            executor.submit(run_validate_docs_timed): "validate_docs",
            executor.submit(run_ruff_timed): "ruff",
            executor.submit(run_mypy_timed): "mypy",
        }

        # Collect results as they complete
        future: Future[Any]
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                if source == "pytest":
                    _output, _returncode, pytest_count, pytest_categories, duration = (
                        future.result()
                    )
                    timings["pytest"] = duration
                elif source == "validate_docs":
                    _output, _returncode, docs_warnings, duration = future.result()
                    timings["validate_docs"] = duration
                elif source == "ruff":
                    _output, _returncode, ruff_errors, duration = future.result()
                    timings["ruff"] = duration
                elif source == "mypy":
                    _output, _returncode, mypy_errors, duration = future.result()
                    timings["mypy"] = duration
            except Exception as e:
                print(f"[ERROR] {source} validation failed: {e}")
                sys.exit(2)

    # Combine all counts
    current_counts = {
        "pytest": pytest_count,
        "yaml_float_literals": docs_warnings.get("yaml_float_literals", 0),
        "master_index_missing": docs_warnings.get("master_index_missing", 0),
        "master_index_deleted": docs_warnings.get("master_index_deleted", 0),
        "master_index_planned": docs_warnings.get("master_index_planned", 0),
        "adr_non_sequential": docs_warnings.get("adr_non_sequential", 0),
        "ruff": ruff_errors,
        "mypy": mypy_errors,
    }

    total_current = sum(current_counts.values())

    # Load baseline
    try:
        baseline = load_baseline()
    except SystemExit:
        if args.create_baseline:
            print("[INFO] Creating initial baseline...")
            # Create minimal baseline
            baseline = {
                "baseline_date": "2025-11-08",
                "total_warnings": total_current,
                "warning_categories": {},
                "governance_policy": {
                    "max_warnings_allowed": total_current,
                    "new_warning_policy": "fail",
                    "regression_tolerance": 0,
                },
            }
            Path("scripts/warning_baseline.json").write_text(
                json.dumps(baseline, indent=2), encoding="utf-8"
            )
            print(f"[OK] Created baseline with {total_current} warnings")
            sys.exit(0)
        else:
            sys.exit(2)

    # Show report if requested
    if args.report or args.update:
        print_warning_report(pytest_categories, baseline)

    # Update baseline if requested
    if args.update:
        update_baseline(total_current, pytest_categories)
        sys.exit(0)

    # Check against baseline
    passed = check_baseline(current_counts, baseline, show_report=args.report, timings=timings)

    # Print recommendation based on result
    if not passed:
        print("\n[RECOMMENDATION] Run with --report to see detailed breakdown:")
        print("  python scripts/check_warning_debt.py --report\n")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
