"""
Validation Results Logger

Logs validation results from all validation sources (pytest, Ruff, Mypy, validate_docs)
to a persistent log file with timestamps, structured data, and runtime metrics.

Usage:
    # Basic usage (without runtime tracking)
    python scripts/log_validation_results.py --source pytest --warnings 32 --passed True

    # With runtime tracking
    python scripts/log_validation_results.py --source pytest --warnings 32 --passed True --duration-seconds 87.4 --timeout-seconds 300
    python scripts/log_validation_results.py --source ruff --warnings 0 --passed True --duration-seconds 0.07 --timeout-seconds 60
    python scripts/log_validation_results.py --source mypy --warnings 36 --passed True --duration-seconds 4.01 --timeout-seconds 60
    python scripts/log_validation_results.py --source validate_docs --warnings 0 --passed True --duration-seconds 0.34 --timeout-seconds 60

    # With additional metadata
    python scripts/log_validation_results.py --source pytest --warnings 32 --passed True --test-count 323 --failed 1 --skipped 9 --duration-seconds 87.4
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
    duration_seconds: float | None = None,
    timeout_seconds: float | None = None,
    timed_out: bool = False,
    **extra_data: Any,
) -> None:
    """
    Log validation results to JSONL file with timestamp and runtime metrics.

    Args:
        source: Validation source name ("pytest", "ruff", "mypy", "validate_docs")
        warnings: Number of warnings detected
        passed: Whether validation passed (True/False)
        duration_seconds: Time taken to run validation (seconds)
        timeout_seconds: Configured timeout for this validation source (seconds)
        timed_out: Whether the validation hit the timeout limit
        **extra_data: Additional metadata (e.g., test_count, failures, errors)

    Example:
        >>> log_validation_result("pytest", warnings=32, passed=True, duration_seconds=87.4, test_count=323)
        >>> log_validation_result("ruff", warnings=0, passed=True, duration_seconds=0.07, timeout_seconds=60)
    """
    # Ensure logs directory exists
    LOG_DIR.mkdir(exist_ok=True)

    # Create log entry with runtime metrics
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "source": source,
        "warnings": warnings,
        "passed": passed,
        **extra_data,
    }

    # Add runtime tracking fields if provided
    if duration_seconds is not None:
        entry["duration_seconds"] = round(duration_seconds, 2)
    if timeout_seconds is not None:
        entry["timeout_seconds"] = round(timeout_seconds, 2)
    if timed_out:
        entry["timed_out"] = timed_out

    # Append to JSONL file (one JSON object per line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    timing_info = f", duration={duration_seconds:.2f}s" if duration_seconds else ""
    print(
        f"[INFO] Logged {source} validation result: {warnings} warnings, passed={passed}{timing_info}"
    )


def main():
    """CLI interface for logging validation results."""
    import argparse

    parser = argparse.ArgumentParser(description="Log validation results with runtime metrics")
    parser.add_argument(
        "--source", required=True, help="Validation source (pytest, ruff, mypy, validate_docs)"
    )
    parser.add_argument("--warnings", type=int, required=True, help="Number of warnings")
    parser.add_argument(
        "--passed", type=lambda x: x.lower() == "true", required=True, help="Passed (True/False)"
    )

    # Runtime tracking arguments
    parser.add_argument(
        "--duration-seconds", type=float, help="Time taken to run validation (seconds)"
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        help="Configured timeout for this validation source (seconds)",
    )
    parser.add_argument(
        "--timed-out", action="store_true", help="Whether the validation hit the timeout limit"
    )

    # Source-specific metadata arguments
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

    log_validation_result(
        args.source,
        args.warnings,
        args.passed,
        duration_seconds=args.duration_seconds,
        timeout_seconds=args.timeout_seconds,
        timed_out=args.timed_out,
        **extra_data,
    )


if __name__ == "__main__":
    main()
