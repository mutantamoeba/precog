#!/usr/bin/env python3
"""
Phase Completion Protocol Validation - Automated Assessment

Automates critical steps from 10-Step Phase Completion Protocol.

Implements automated checks for:
- Step 1: Deliverable Completeness (coverage targets met)
- Step 5: Testing & Validation (all tests passing, coverage threshold)
- Step 9: Security Review (no hardcoded credentials)

Provides guidance for manual steps (2, 3, 4, 6, 7, 8, 10).

This validator focuses on automating the MOST CRITICAL and EASILY AUTOMATABLE steps,
providing immediate value while acknowledging that some steps (design consistency,
AI review analysis, technical debt assessment) require human judgment.

Reference: CLAUDE.md Section "Phase Completion Protocol" (10 steps, ~50 min total)
Reference: docs/foundation/DEVELOPMENT_PHASES_V1.4.md
Reference: scripts/validation_config.yaml (phase deliverables)

Exit codes:
  0 = All automated checks passed
  1 = Critical automated checks failed
  2 = Configuration error (WARNING only)

Example usage:
  python scripts/validate_phase_completion.py --phase 1.5         # Validate Phase 1.5 completion
  python scripts/validate_phase_completion.py --phase 2 --verbose # Detailed output
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def load_phase_deliverables(phase: str) -> dict:
    """
    Load phase deliverables from validation_config.yaml.

    Args:
        phase: Phase number like "1.5" or "2"

    Returns:
        dict with deliverables for phase, or empty dict if not found
    """
    validation_config_path = PROJECT_ROOT / "scripts" / "validation_config.yaml"

    if not validation_config_path.exists() or not YAML_AVAILABLE:
        return {}

    try:
        with open(validation_config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            phase_deliverables = config.get("phase_deliverables", {})
            return cast("dict[Any, Any]", phase_deliverables.get(phase, {}))
    except Exception:
        return {}


def step1_check_coverage_targets(phase: str, verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Step 1: Deliverable Completeness - Verify coverage targets met.

    Runs pytest with coverage and compares actual vs. target for each deliverable.

    Args:
        phase: Phase number like "1.5" or "2"
        verbose: If True, show detailed check

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Load phase deliverables
    deliverables_config = load_phase_deliverables(phase)

    if not deliverables_config:
        violations.append(f"No deliverables defined for Phase {phase}")
        return False, violations

    deliverables = deliverables_config.get("deliverables", [])

    if not deliverables:
        violations.append(f"Phase {phase} has no deliverables listed")
        return False, violations

    if verbose:
        print(f"[DEBUG] Checking coverage for {len(deliverables)} deliverables")

    # Run pytest with coverage
    try:
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "tests/",
                "--cov=.",
                "--cov-report=term-missing",
                "--tb=no",
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if verbose:
            print("[DEBUG] Coverage report generated")

        # Parse coverage output
        coverage_data = {}
        for line in result.stdout.split("\n"):
            # Match lines like: "src/precog/analytics/model_manager.py    100     10    91%"
            match = re.match(r"^([^\s]+\.py)\s+\d+\s+\d+\s+(\d+)%", line)
            if match:
                file_path, coverage_pct = match.groups()
                coverage_data[file_path] = int(coverage_pct)

        # Check each deliverable
        for deliverable in deliverables:
            name = deliverable.get("name", "UNKNOWN")
            file_path = deliverable.get("file", "")
            target = deliverable.get("coverage_target", 80)

            # Normalize file path for comparison
            file_normalized = file_path.replace("\\", "/")

            # Find matching coverage data
            actual_coverage = None
            for cov_file, cov_pct in coverage_data.items():
                if file_normalized in cov_file.replace("\\", "/"):
                    actual_coverage = cov_pct
                    break

            if actual_coverage is None:
                violations.append(f"{name}: No coverage data found (file: {file_path})")
            elif actual_coverage < target:
                violations.append(
                    f"{name}: {actual_coverage}% (target: {target}%, gap: {target - actual_coverage}%)"
                )
            elif verbose:
                print(f"[DEBUG] {name}: {actual_coverage}% >= {target}% ✅")

    except subprocess.TimeoutExpired:
        violations.append("Coverage check timed out (>2 minutes)")
        return False, violations
    except Exception as e:
        violations.append(f"Coverage check failed: {e}")
        return False, violations

    return len(violations) == 0, violations


def step5_testing_validation(verbose: bool = False) -> tuple[bool, list[str], dict]:
    """
    Step 5: Testing & Validation - Run all tests and check coverage threshold.

    Args:
        verbose: If True, show detailed check

    Returns:
        (passed, violations, stats) tuple
    """
    violations = []
    stats = {"tests_passed": 0, "tests_failed": 0, "coverage_pct": 0}

    try:
        # Run pytest
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v", "--cov=.", "--cov-report=term"],
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Parse test results
        # Look for line like: "=== 454 passed, 26 failed, 10 skipped in 45.23s ==="
        test_summary = re.search(
            r"(\d+)\s+passed(?:,\s+(\d+)\s+failed)?(?:,\s+\d+\s+skipped)?", result.stdout
        )

        if test_summary:
            stats["tests_passed"] = int(test_summary.group(1))
            stats["tests_failed"] = int(test_summary.group(2) or 0)

        # Parse coverage percentage
        # Look for line like: "TOTAL    1234    567    54%"
        coverage_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", result.stdout)
        if coverage_match:
            stats["coverage_pct"] = int(coverage_match.group(1))

        # Check for failures
        if stats["tests_failed"] > 0:
            violations.append(f"{stats['tests_failed']} tests failing")

        # Check coverage threshold (80%)
        if stats["coverage_pct"] < 80:
            violations.append(f"Coverage {stats['coverage_pct']}% below threshold (target: 80%)")

        if verbose:
            print(f"[DEBUG] Tests: {stats['tests_passed']} passed, {stats['tests_failed']} failed")
            print(f"[DEBUG] Coverage: {stats['coverage_pct']}%")

    except subprocess.TimeoutExpired:
        violations.append("Test suite timed out (>5 minutes)")
        return False, violations, stats
    except Exception as e:
        violations.append(f"Test execution failed: {e}")
        return False, violations, stats

    return len(violations) == 0, violations, stats


def step9_security_review(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Step 9: Security Review - Scan for hardcoded credentials.

    Args:
        verbose: If True, show detailed check

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Scan for hardcoded credentials
    try:
        result1 = subprocess.run(
            [
                "git",
                "grep",
                "-E",
                r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]",
                "--",
                "*.py",
                "*.yaml",
                "*.sql",
            ],
            capture_output=True,
            text=True,
        )

        # Scan for connection strings with passwords
        result2 = subprocess.run(
            [
                "git",
                "grep",
                "-E",
                r"(postgres://|mysql://).*:.*@",
                "--",
                "*",
            ],
            capture_output=True,
            text=True,
        )

        # Check results (exit code 0 = matches found, 1 = no matches)
        if result1.returncode == 0:
            matches = result1.stdout.strip().split("\n")
            # Filter out os.getenv() lines (those are OK)
            real_violations = [m for m in matches if "os.getenv" not in m and "getenv" not in m]

            if real_violations:
                violations.append(f"{len(real_violations)} hardcoded credentials found:")
                for match in real_violations[:5]:  # Show first 5
                    violations.append(f"  {match}")
                if len(real_violations) > 5:
                    violations.append(f"  ... and {len(real_violations) - 5} more")

        if result2.returncode == 0:
            violations.append("Connection strings with embedded passwords found")

        if verbose and not violations:
            print("[DEBUG] No hardcoded credentials found ✅")

    except Exception as e:
        violations.append(f"Security scan failed: {e}")
        return False, violations

    return len(violations) == 0, violations


def validate_phase_completion(phase: str, verbose: bool = False) -> tuple[int, dict]:
    """
    Comprehensive phase completion validation.

    Args:
        phase: Phase number like "1.5" or "2"
        verbose: If True, show detailed validation process

    Returns:
        (exit_code, results) tuple
    """
    results = {
        "step1_passed": False,
        "step1_violations": [],
        "step5_passed": False,
        "step5_violations": [],
        "step5_stats": {},
        "step9_passed": False,
        "step9_violations": [],
    }

    # Step 1: Deliverable Completeness (coverage targets)
    step1_passed, step1_violations = step1_check_coverage_targets(phase, verbose)
    results["step1_passed"] = step1_passed
    results["step1_violations"] = step1_violations

    # Step 5: Testing & Validation
    step5_passed, step5_violations, step5_stats = step5_testing_validation(verbose)
    results["step5_passed"] = step5_passed
    results["step5_violations"] = step5_violations
    results["step5_stats"] = step5_stats

    # Step 9: Security Review
    step9_passed, step9_violations = step9_security_review(verbose)
    results["step9_passed"] = step9_passed
    results["step9_violations"] = step9_violations

    # Determine exit code
    all_passed = step1_passed and step5_passed and step9_passed
    return (0 if all_passed else 1), results


def main():
    """Run phase completion validation."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    # Get phase number from args
    phase = None
    for i, arg in enumerate(sys.argv):
        if arg == "--phase" and i + 1 < len(sys.argv):
            phase = sys.argv[i + 1]
            break

    if not phase:
        print("Usage: python scripts/validate_phase_completion.py --phase <phase_number>")
        print("Example: python scripts/validate_phase_completion.py --phase 1.5")
        return 2

    print("=" * 60)
    print(f"Phase Completion Protocol - Phase {phase}")
    print("=" * 60)
    print("Reference: CLAUDE.md Section 'Phase Completion Protocol'")
    print("Automating Steps 1, 5, 9 (coverage, tests, security)")
    print("Manual steps (2, 3, 4, 6, 7, 8, 10) require human assessment")
    print("")

    # Check dependencies
    if not YAML_AVAILABLE:
        print("[WARN] PyYAML not available - deliverable validation skipped")
        print("")

    # Run validation
    print("[AUTOMATED] Step 1: Deliverable Completeness (coverage targets)...")
    print("[AUTOMATED] Step 5: Testing & Validation (tests + coverage)...")
    print("[AUTOMATED] Step 9: Security Review (credential scan)...")
    print("")

    exit_code, results = validate_phase_completion(phase, verbose)

    # Report results
    print("=" * 60)
    print("AUTOMATED VALIDATION RESULTS")
    print("=" * 60)
    print("")

    # Step 1 results
    if results["step1_passed"]:
        print("[PASS] Step 1: All deliverables meet coverage targets")
    else:
        print(f"[FAIL] Step 1: {len(results['step1_violations'])} deliverables below target:")
        for v in results["step1_violations"]:
            print(f"  - {v}")

    print("")

    # Step 5 results
    if results["step5_passed"]:
        stats = results["step5_stats"]
        print(
            f"[PASS] Step 5: {stats['tests_passed']} tests passing, "
            f"{stats['coverage_pct']}% coverage"
        )
    else:
        print("[FAIL] Step 5: Testing validation failed:")
        for v in results["step5_violations"]:
            print(f"  - {v}")
        if results["step5_stats"]:
            stats = results["step5_stats"]
            print(
                f"  Stats: {stats.get('tests_passed', 0)} passed, "
                f"{stats.get('tests_failed', 0)} failed, "
                f"{stats.get('coverage_pct', 0)}% coverage"
            )

    print("")

    # Step 9 results
    if results["step9_passed"]:
        print("[PASS] Step 9: No hardcoded credentials found")
    else:
        print("[FAIL] Step 9: Security violations found:")
        for v in results["step9_violations"]:
            print(f"  - {v}")

    print("")
    print("=" * 60)
    print("MANUAL STEPS CHECKLIST")
    print("=" * 60)
    print("")
    print("Complete these steps manually (see CLAUDE.md for full details):")
    print("  [ ] Step 2: Internal Consistency (5 min)")
    print("  [ ] Step 3: Dependency Verification (5 min)")
    print("  [ ] Step 4: Quality Standards (5 min)")
    print("  [ ] Step 6: Gaps & Risks + Deferred Tasks (2 min)")
    print("  [ ] Step 7: AI Code Review Analysis (10 min)")
    print("  [ ] Step 8: Archive & Version Management (5 min)")
    print("  [ ] Step 10: Performance Profiling (Phase 5+ only)")
    print("")
    print("=" * 60)

    if exit_code == 0:
        print(f"[PASS] Phase {phase} automated checks passed")
        print("=" * 60)
        print("")
        print("Complete manual steps above, then proceed to next phase.")
        return 0
    print(f"[FAIL] Phase {phase} automated checks failed")
    print("=" * 60)
    print("")
    print("Fix automated violations above before proceeding.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
