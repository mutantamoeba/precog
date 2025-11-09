"""
View Validation Logs Summary

Displays validation results in a user-friendly format with trends and statistics.

Usage:
    python scripts/view_validation_logs.py                    # Show latest results
    python scripts/view_validation_logs.py --history 10       # Show last 10 results per source
    python scripts/view_validation_logs.py --source pytest    # Show pytest history only
    python scripts/view_validation_logs.py --trend            # Show warning trend over time
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

LOG_FILE = Path("logs/validation_history.jsonl")


def load_validation_logs() -> list[dict]:
    """Load all validation logs from JSONL file."""
    if not LOG_FILE.exists():
        return []

    logs = []
    with LOG_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            logs.append(json.loads(line))
    return logs


def show_latest(logs: list[dict]) -> None:
    """Show latest validation result from each source."""
    if not logs:
        print("No validation logs found.")
        return

    # Group by source and get latest
    by_source = defaultdict(list)
    for log in logs:
        by_source[log["source"]].append(log)

    print("=" * 80)
    print("LATEST VALIDATION RESULTS")
    print("=" * 80)
    print()

    total_warnings = 0
    all_passed = True

    for source in sorted(by_source.keys()):
        latest = by_source[source][-1]
        timestamp = latest["timestamp"]
        warnings = latest["warnings"]
        passed = latest["passed"]

        # Format status
        status = "[OK]" if passed else "[FAIL]"

        print(f"{source:15s} {status:8s} {warnings:3d} warnings   {timestamp}")

        # Show additional details
        if source == "pytest" and "test_count" in latest:
            print(
                f"{'':15s} Tests: {latest.get('test_count', 0)} total, "
                f"{latest.get('failed', 0)} failed, {latest.get('skipped', 0)} skipped"
            )
        if "failures" in latest:
            print(f"{'':15s} Failures: {latest['failures']}")

        total_warnings += warnings
        all_passed = all_passed and passed

    print()
    print("=" * 80)
    print(f"TOTAL WARNINGS: {total_warnings}")
    print(
        f"OVERALL STATUS: {'[OK] All checks passed' if all_passed else '[FAIL] Some checks failed'}"
    )
    print("=" * 80)


def show_history(logs: list[dict], limit: int = 10, source: str | None = None) -> None:
    """Show validation history (last N results per source)."""
    if not logs:
        print("No validation logs found.")
        return

    # Filter by source if specified
    if source:
        logs = [log for log in logs if log["source"] == source]
        if not logs:
            print(f"No logs found for source: {source}")
            return

    # Group by source
    by_source = defaultdict(list)
    for log in logs:
        by_source[log["source"]].append(log)

    print("=" * 80)
    print(f"VALIDATION HISTORY (last {limit} results per source)")
    print("=" * 80)
    print()

    for src in sorted(by_source.keys()):
        print(f"\n{src.upper()}")
        print("-" * 80)
        print(f"{'Timestamp':<30s} {'Warnings':<10s} {'Status':<10s}")
        print("-" * 80)

        for log in by_source[src][-limit:]:
            timestamp = log["timestamp"][:19]  # Trim to YYYY-MM-DDTHH:MM:SS
            warnings = log["warnings"]
            status = "PASS" if log["passed"] else "FAIL"

            print(f"{timestamp:<30s} {warnings:<10d} {status:<10s}")

        print()


def show_trend(logs: list[dict]) -> None:
    """Show warning count trend over time."""
    if not logs:
        print("No validation logs found.")
        return

    print("=" * 80)
    print("WARNING TREND (Total warnings per validation run)")
    print("=" * 80)
    print()

    # Group by timestamp (aggregate all sources at same time)
    by_timestamp: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"warnings": 0, "sources": set()}
    )

    for log in logs:
        timestamp = log["timestamp"][:19]  # Group by minute
        by_timestamp[timestamp]["warnings"] += log["warnings"]
        by_timestamp[timestamp]["sources"].add(log["source"])

    print(f"{'Timestamp':<30s} {'Total Warnings':<15s} {'Sources'}")
    print("-" * 80)

    for timestamp in sorted(by_timestamp.keys()):
        data = by_timestamp[timestamp]
        warnings = data["warnings"]
        sources = ", ".join(sorted(data["sources"]))

        print(f"{timestamp:<30s} {warnings:<15d} {sources}")


def main():
    """CLI interface for viewing validation logs."""
    import argparse

    parser = argparse.ArgumentParser(description="View validation logs")
    parser.add_argument("--history", type=int, metavar="N", help="Show last N results per source")
    parser.add_argument("--source", help="Filter by source (pytest, ruff, mypy, validate_docs)")
    parser.add_argument("--trend", action="store_true", help="Show warning trend over time")

    args = parser.parse_args()

    logs = load_validation_logs()

    if args.trend:
        show_trend(logs)
    elif args.history:
        show_history(logs, limit=args.history, source=args.source)
    else:
        show_latest(logs)


if __name__ == "__main__":
    main()
