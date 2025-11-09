"""
Validation Results Logger

Logs validation results from all validation sources (pytest, Ruff, Mypy, validate_docs)
to a persistent log file with timestamps and structured data.

Usage:
    python scripts/log_validation_results.py --source pytest --warnings 32 --passed 322 --failed 1
    python scripts/log_validation_results.py --source ruff --warnings 0 --passed True
    python scripts/log_validation_results.py --source mypy --warnings 0 --passed True
    python scripts/log_validation_results.py --source validate_docs --warnings 0 --passed False --failures 2
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "validation_history.jsonl"


def log_validation_result(
    source: str,
    warnings: int,
    passed: bool,
    **extra_data: Any,
) -> None:
    """
    Log validation results to JSONL file with timestamp.

    Args:
        source: Validation source name ("pytest", "ruff", "mypy", "validate_docs")
        warnings: Number of warnings detected
        passed: Whether validation passed (True/False)
        **extra_data: Additional metadata (e.g., test_count, failures, errors)

    Example:
        >>> log_validation_result("pytest", warnings=32, passed=True, test_count=323)
        >>> log_validation_result("ruff", warnings=0, passed=True)
    """
    # Ensure logs directory exists
    LOG_DIR.mkdir(exist_ok=True)

    # Create log entry
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "source": source,
        "warnings": warnings,
        "passed": passed,
        **extra_data,
    }

    # Append to JSONL file (one JSON object per line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"[INFO] Logged {source} validation result: {warnings} warnings, passed={passed}")


def main():
    """CLI interface for logging validation results."""
    import argparse

    parser = argparse.ArgumentParser(description="Log validation results")
    parser.add_argument(
        "--source", required=True, help="Validation source (pytest, ruff, mypy, validate_docs)"
    )
    parser.add_argument("--warnings", type=int, required=True, help="Number of warnings")
    parser.add_argument(
        "--passed", type=lambda x: x.lower() == "true", required=True, help="Passed (True/False)"
    )
    parser.add_argument("--test-count", type=int, help="Number of tests (pytest only)")
    parser.add_argument("--failed", type=int, help="Number of failed tests (pytest only)")
    parser.add_argument("--skipped", type=int, help="Number of skipped tests (pytest only)")
    parser.add_argument(
        "--failures", type=int, help="Number of validation failures (validate_docs only)"
    )
    parser.add_argument("--errors", type=int, help="Number of errors")

    args = parser.parse_args()

    # Build extra_data from optional args
    extra_data = {}
    if args.test_count is not None:
        extra_data["test_count"] = args.test_count
    if args.failed is not None:
        extra_data["failed"] = args.failed
    if args.skipped is not None:
        extra_data["skipped"] = args.skipped
    if args.failures is not None:
        extra_data["failures"] = args.failures
    if args.errors is not None:
        extra_data["errors"] = args.errors

    log_validation_result(args.source, args.warnings, args.passed, **extra_data)


if __name__ == "__main__":
    main()
