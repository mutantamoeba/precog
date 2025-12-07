#!/usr/bin/env python3
"""
Analyze pre-push test result history for debugging and trend analysis.

This script parses historical pre-push log files to provide:
- Pass/fail/skip trends over time
- Test phase performance breakdown
- Flaky test detection (tests that flip between pass/fail)
- Duration trend analysis

Reference: Issue #174 (Persist pre-push hook test results)
Related: DEVELOPMENT_PATTERNS Pattern 31 (Pre-Push Log Persistence)

Usage:
    # Show last 10 runs
    python scripts/analyze_test_history.py

    # Show last N runs
    python scripts/analyze_test_history.py --last 5

    # Show detailed view with per-phase breakdown
    python scripts/analyze_test_history.py --detailed

    # Export to JSON for external analysis
    python scripts/analyze_test_history.py --json

    # Show only flaky tests
    python scripts/analyze_test_history.py --flaky

Example output:
    $ python scripts/analyze_test_history.py --last 5

    Test Result Trends (last 5 runs)
    =================================
    Total Runs: 5
    Pass Rate: 100.0%
    Average Duration: 152.3s

    Phase Breakdown:
      Phase A (Unit):        409/409 (100%) - avg 22.1s
      Phase B (Integration): 341/341 (100%) - avg 31.2s
      Phase C (Property):    110/110 (100%) - avg 30.5s
      Phase D (Other):       233/233 (100%) - avg 68.5s

    Flaky Tests (passed sometimes, failed others):
      - None detected
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class PhaseResult:
    """Results from a single test phase."""

    name: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    duration_seconds: float = 0.0

    @property
    def total(self) -> int:
        """Total tests run in this phase."""
        return self.passed + self.failed + self.skipped + self.error

    @property
    def pass_rate(self) -> float:
        """Pass rate as percentage (0-100)."""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


@dataclass
class TestRunResult:
    """Results from a single pre-push test run."""

    timestamp: datetime
    branch: str = ""
    success: bool = False
    duration_seconds: float = 0.0
    phases: dict[str, PhaseResult] = field(default_factory=dict)
    failed_tests: list[str] = field(default_factory=list)
    log_file: str = ""

    @property
    def total_passed(self) -> int:
        """Total passed tests across all phases."""
        return sum(p.passed for p in self.phases.values())

    @property
    def total_failed(self) -> int:
        """Total failed tests across all phases."""
        return sum(p.failed for p in self.phases.values())

    @property
    def total_skipped(self) -> int:
        """Total skipped tests across all phases."""
        return sum(p.skipped for p in self.phases.values())

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "branch": self.branch,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "total_passed": self.total_passed,
            "total_failed": self.total_failed,
            "total_skipped": self.total_skipped,
            "phases": {
                name: {
                    "passed": p.passed,
                    "failed": p.failed,
                    "skipped": p.skipped,
                    "error": p.error,
                    "duration_seconds": p.duration_seconds,
                }
                for name, p in self.phases.items()
            },
            "failed_tests": self.failed_tests,
            "log_file": self.log_file,
        }


def find_log_directory() -> Path:
    """Find the pre-push logs directory."""
    # Try common locations
    candidates = [
        Path(".pre-push-logs"),
        Path.cwd() / ".pre-push-logs",
        Path(__file__).parent.parent / ".pre-push-logs",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    # Default to cwd/.pre-push-logs if nothing found
    return Path(".pre-push-logs")


def parse_log_file(log_path: Path) -> TestRunResult | None:
    """
    Parse a pre-push log file and extract test results.

    Handles both:
    - Plain text logs (current format)
    - JSON summary files (*.json)
    """
    if not log_path.exists():
        return None

    # Handle JSON summary files directly
    if log_path.suffix == ".json":
        return parse_json_summary(log_path)

    # Parse plain text log
    return parse_text_log(log_path)


def parse_json_summary(json_path: Path) -> TestRunResult | None:
    """Parse a JSON summary file."""
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        result = TestRunResult(
            timestamp=datetime.fromisoformat(data.get("timestamp", "")),
            branch=data.get("branch", ""),
            success=data.get("success", False),
            duration_seconds=data.get("duration_seconds", 0.0),
            failed_tests=data.get("failed_tests", []),
            log_file=str(json_path),
        )

        for phase_name, phase_data in data.get("phases", {}).items():
            result.phases[phase_name] = PhaseResult(
                name=phase_name,
                passed=phase_data.get("passed", 0),
                failed=phase_data.get("failed", 0),
                skipped=phase_data.get("skipped", 0),
                error=phase_data.get("error", 0),
                duration_seconds=phase_data.get("duration_seconds", 0.0),
            )

        return result
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def parse_text_log(log_path: Path) -> TestRunResult | None:
    """
    Parse a plain text pre-push log file.

    Extracts:
    - Timestamp from filename (pre-push-YYYYMMDD-HHMMSS.log)
    - Branch name from "Branch: xxx" line
    - Test counts from pytest output lines
    - Duration from summary lines
    """
    # Extract timestamp from filename
    # Format: pre-push-20251207-105506.log
    filename = log_path.name
    timestamp_match = re.search(r"pre-push-(\d{8})-(\d{6})", filename)
    if not timestamp_match:
        return None

    try:
        date_str = timestamp_match.group(1)
        time_str = timestamp_match.group(2)
        timestamp = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None

    result = TestRunResult(timestamp=timestamp, log_file=str(log_path))

    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Parse branch name
    branch_match = re.search(r"Branch:\s*(\S+)", content)
    if branch_match:
        result.branch = branch_match.group(1)

    # Check for overall success
    result.success = "All pre-push checks passed" in content

    # Parse phase results
    # Look for lines like: "409 passed in 22.15s"
    # Or: "337 passed, 4 failed, 2 skipped in 31.2s"
    phase_patterns = [
        (r"Phase A.*?(\d+) passed", "Phase A (Unit)"),
        (r"Phase B.*?(\d+) passed", "Phase B (Integration)"),
        (r"Phase C.*?(\d+) passed", "Phase C (Property)"),
        (r"Phase D.*?(\d+) passed", "Phase D (Other)"),
    ]

    for pattern, phase_name in phase_patterns:
        phase = PhaseResult(name=phase_name)
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            phase.passed = int(match.group(1))

        # Look for failed count
        failed_match = re.search(
            rf"{phase_name}.*?(\d+) failed",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if failed_match:
            phase.failed = int(failed_match.group(1))

        # Look for skipped count
        skipped_match = re.search(
            rf"{phase_name}.*?(\d+) skipped",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if skipped_match:
            phase.skipped = int(skipped_match.group(1))

        result.phases[phase_name] = phase

    # Parse failed test names
    # Look for lines starting with "FAILED" or in short test summary
    failed_pattern = re.compile(r"FAILED\s+(tests/\S+)", re.MULTILINE)
    result.failed_tests = failed_pattern.findall(content)

    # Parse total duration from final summary
    duration_match = re.search(r"in\s+([\d.]+)s", content)
    if duration_match:
        result.duration_seconds = float(duration_match.group(1))

    return result


def load_test_history(log_dir: Path, limit: int = 10) -> list[TestRunResult]:
    """
    Load and parse test history from log directory.

    Args:
        log_dir: Path to the log directory
        limit: Maximum number of runs to load (newest first)

    Returns:
        List of TestRunResult, sorted by timestamp descending
    """
    if not log_dir.exists():
        return []

    results = []

    # Find all log files
    log_files = list(log_dir.glob("pre-push-*.log"))
    json_files = list(log_dir.glob("pre-push-*.json"))

    all_files = log_files + json_files

    # Sort by filename (which contains timestamp) descending
    all_files.sort(key=lambda p: p.name, reverse=True)

    # Parse the most recent files
    for log_path in all_files[:limit]:
        result = parse_log_file(log_path)
        if result:
            results.append(result)

    return results


def detect_flaky_tests(history: Sequence[TestRunResult]) -> dict[str, dict]:
    """
    Detect flaky tests - tests that passed sometimes and failed other times.

    Returns:
        Dict mapping test name to {pass_count, fail_count, flakiness_score}
    """
    test_results: dict[str, dict] = {}

    for run in history:
        # Track failed tests
        for test in run.failed_tests:
            if test not in test_results:
                test_results[test] = {"passed": 0, "failed": 0}
            test_results[test]["failed"] += 1

    # A test is flaky if it appears in failed_tests for some runs but not others
    flaky = {}
    for test, counts in test_results.items():
        if counts["failed"] < len(history):
            # Test failed in some runs but not all
            counts["passed"] = len(history) - counts["failed"]
            counts["flakiness_score"] = min(counts["passed"], counts["failed"]) / len(history)
            flaky[test] = counts

    return flaky


def format_summary(
    history: Sequence[TestRunResult],
    *,
    detailed: bool = False,
) -> str:
    """Format test history as human-readable summary."""
    if not history:
        return "No test history found in .pre-push-logs/"

    lines = []
    lines.append(f"\nTest Result Trends (last {len(history)} runs)")
    lines.append("=" * 50)

    # Overall statistics
    total_runs = len(history)
    successful_runs = sum(1 for r in history if r.success)
    pass_rate = (successful_runs / total_runs) * 100 if total_runs > 0 else 0

    avg_duration = sum(r.duration_seconds for r in history) / total_runs

    lines.append(f"Total Runs: {total_runs}")
    lines.append(f"Pass Rate: {pass_rate:.1f}%")
    lines.append(f"Average Duration: {avg_duration:.1f}s")
    lines.append("")

    # Phase breakdown
    if detailed:
        lines.append("Phase Breakdown:")
        phase_names = [
            "Phase A (Unit)",
            "Phase B (Integration)",
            "Phase C (Property)",
            "Phase D (Other)",
        ]

        for phase_name in phase_names:
            total_passed = sum(
                r.phases.get(phase_name, PhaseResult(phase_name)).passed for r in history
            )
            total_tests = sum(
                r.phases.get(phase_name, PhaseResult(phase_name)).total for r in history
            )
            avg_phase_duration = (
                sum(
                    r.phases.get(phase_name, PhaseResult(phase_name)).duration_seconds
                    for r in history
                )
                / total_runs
            )

            if total_tests > 0:
                phase_rate = (total_passed / total_tests) * 100
                lines.append(
                    f"  {phase_name:25} {total_passed}/{total_tests} ({phase_rate:.1f}%) - avg {avg_phase_duration:.1f}s"
                )
        lines.append("")

    # Flaky tests
    flaky = detect_flaky_tests(history)
    lines.append("Flaky Tests (passed sometimes, failed others):")
    if flaky:
        for test, counts in sorted(flaky.items(), key=lambda x: -x[1]["flakiness_score"]):
            lines.append(f"  - {test} ({counts['passed']} passed, {counts['failed']} failed)")
    else:
        lines.append("  - None detected")
    lines.append("")

    # Recent failures
    recent_failures = []
    for run in history[:3]:  # Last 3 runs
        if run.failed_tests:
            recent_failures.extend(run.failed_tests)

    if recent_failures:
        lines.append("Recent Failures (last 3 runs):")
        for test in sorted(set(recent_failures)):
            count = recent_failures.count(test)
            lines.append(f"  - {test} (failed {count}x)")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze pre-push test result history",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/analyze_test_history.py              # Last 10 runs
    python scripts/analyze_test_history.py --last 5     # Last 5 runs
    python scripts/analyze_test_history.py --detailed   # With phase breakdown
    python scripts/analyze_test_history.py --json       # Export to JSON
    python scripts/analyze_test_history.py --flaky      # Show only flaky tests
        """,
    )

    parser.add_argument(
        "--last",
        type=int,
        default=10,
        help="Number of recent runs to analyze (default: 10)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed per-phase breakdown",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON for external analysis",
    )
    parser.add_argument(
        "--flaky",
        action="store_true",
        help="Show only flaky test detection",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Path to log directory (default: .pre-push-logs/)",
    )

    args = parser.parse_args()

    # Find log directory
    log_dir = args.log_dir or find_log_directory()

    if not log_dir.exists():
        print(f"Log directory not found: {log_dir}")
        print("Run pre-push hooks at least once to generate logs.")
        return 1

    # Load history
    history = load_test_history(log_dir, limit=args.last)

    if not history:
        print(f"No log files found in {log_dir}")
        return 1

    # Output based on format
    if args.json:
        output = {
            "analyzed_at": datetime.now().isoformat(),
            "total_runs": len(history),
            "runs": [r.to_dict() for r in history],
            "flaky_tests": detect_flaky_tests(history),
        }
        print(json.dumps(output, indent=2))
    elif args.flaky:
        flaky = detect_flaky_tests(history)
        if flaky:
            print(f"\nFlaky Tests Detected ({len(flaky)}):")
            print("=" * 50)
            for test, counts in sorted(flaky.items(), key=lambda x: -x[1]["flakiness_score"]):
                print(f"  {test}")
                print(f"    Passed: {counts['passed']}, Failed: {counts['failed']}")
                print(f"    Flakiness: {counts['flakiness_score']:.1%}")
        else:
            print(f"\nNo flaky tests detected in the last {len(history)} runs.")
    else:
        print(format_summary(history, detailed=args.detailed))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
