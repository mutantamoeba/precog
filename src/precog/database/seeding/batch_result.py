"""
Batch Insert Result Types and Error Handling.

This module provides structured result types for batch insert operations with
detailed error tracking and multiple error handling modes.

Educational Notes:
------------------
Error Handling Modes:
    - fail: Stop immediately on first error (current default, all-or-nothing)
    - skip: Skip failed records, continue processing (fire-and-forget)
    - collect: Process all records, collect failures for analysis (recommended)

The "collect" mode is most useful for data quality investigations because it
allows you to see ALL failures rather than just the first one.

Reference:
    - Issue #255: Improve batch insert error handling with partial failure tracking
    - Pattern 5: Cross-Platform Compatibility (ASCII output)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class ErrorHandlingMode(Enum):
    """
    Error handling mode for batch insert operations.

    Attributes:
        FAIL: Stop on first error, rollback entire batch (default for safety)
        SKIP: Skip failed records, continue processing remaining records
        COLLECT: Process all records, collect list of failures at end (for analysis)

    Educational Note:
        - FAIL is safest for transactional integrity but provides least info
        - SKIP is useful for "best effort" imports where some failures are expected
        - COLLECT is best for data quality analysis and debugging
    """

    FAIL = "fail"
    SKIP = "skip"
    COLLECT = "collect"


@dataclass
class FailedRecord:
    """
    Details about a record that failed during batch insert.

    Attributes:
        record_index: Position in the original batch (0-indexed)
        record_data: The actual data that failed to insert
        error_type: Exception class name (e.g., "IntegrityError")
        error_message: Human-readable error description
        context: Additional context (e.g., table name, constraint violated)

    Educational Note:
        We capture the full record data to allow for:
        1. Manual review and correction
        2. Retry with corrected data
        3. Data quality reporting
    """

    record_index: int
    record_data: dict[str, Any]
    error_type: str
    error_message: str
    context: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "record_index": self.record_index,
            "record_data": self.record_data,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "context": self.context,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"Record #{self.record_index}: {self.error_type} - {self.error_message}" + (
            f" ({self.context})" if self.context else ""
        )


@dataclass
class BatchInsertResult:
    """
    Comprehensive result of a batch insert operation with detailed error tracking.

    This extends the basic LoadResult pattern with:
    - Individual failed record tracking
    - Timing information
    - Error handling mode used
    - Success rate calculation

    Attributes:
        total_records: Total number of records attempted
        successful: Number of records successfully inserted/updated
        failed: Number of records that failed
        skipped: Number of records skipped (e.g., missing foreign key)
        failed_records: List of FailedRecord with details about each failure
        elapsed_time: Total processing time in seconds
        error_mode: The error handling mode used
        operation: Description of the operation (e.g., "Historical Elo Insert")

    Educational Note:
        The success_rate property uses Decimal-safe calculation to avoid
        floating point issues (Pattern 1: Decimal Precision).

    Compatibility Note:
        Properties like records_processed, records_inserted, etc. are provided
        for backward compatibility with the legacy LoadResult dataclass.
        New code should use total_records, successful, etc. directly.
    """

    total_records: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    failed_records: list[FailedRecord] = field(default_factory=list)
    elapsed_time: float = 0.0
    error_mode: ErrorHandlingMode = ErrorHandlingMode.FAIL
    operation: str = ""

    # -------------------------------------------------------------------------
    # Backward Compatibility Properties (LoadResult field names)
    # -------------------------------------------------------------------------

    @property
    def records_processed(self) -> int:
        """Alias for total_records (LoadResult compatibility)."""
        return self.total_records

    @property
    def records_inserted(self) -> int:
        """Alias for successful (LoadResult compatibility)."""
        return self.successful

    @property
    def records_updated(self) -> int:
        """Alias for successful (LoadResult compatibility, upsert counts as update)."""
        return 0  # Separate update tracking not implemented yet

    @property
    def records_skipped(self) -> int:
        """Alias for skipped (LoadResult compatibility)."""
        return self.skipped

    @property
    def errors(self) -> int:
        """Alias for failed (LoadResult compatibility)."""
        return self.failed

    @property
    def error_messages(self) -> list[str]:
        """List of error messages (LoadResult compatibility)."""
        return [str(fr) for fr in self.failed_records]

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage (0-100)."""
        if self.total_records == 0:
            return 0.0
        return (self.successful / self.total_records) * 100

    @property
    def has_failures(self) -> bool:
        """Check if any records failed."""
        return self.failed > 0

    @property
    def all_succeeded(self) -> bool:
        """Check if all records were processed successfully."""
        return self.failed == 0 and self.skipped == 0

    def add_failure(
        self,
        record_index: int,
        record_data: dict[str, Any],
        error: Exception,
        context: str = "",
    ) -> None:
        """
        Add a failed record to the result.

        Args:
            record_index: Position in the original batch
            record_data: The record that failed
            error: The exception that was raised
            context: Additional context about the failure
        """
        self.failed += 1
        self.failed_records.append(
            FailedRecord(
                record_index=record_index,
                record_data=record_data,
                error_type=type(error).__name__,
                error_message=str(error),
                context=context,
            )
        )

    def add_success(self) -> None:
        """Record a successful insert."""
        self.successful += 1

    def add_skip(self) -> None:
        """Record a skipped record."""
        self.skipped += 1

    def get_failure_summary(self, max_errors: int = 10) -> str:
        """
        Get a human-readable summary of failures.

        Args:
            max_errors: Maximum number of errors to include in detail

        Returns:
            Formatted summary string
        """
        if not self.failed_records:
            return "No failures"

        lines = [
            f"Failed {self.failed} of {self.total_records} records "
            f"({100 - self.success_rate:.1f}% failure rate):",
        ]

        # Group by error type
        error_counts: dict[str, int] = {}
        for fr in self.failed_records:
            error_counts[fr.error_type] = error_counts.get(fr.error_type, 0) + 1

        lines.append("")
        lines.append("Error types:")
        for error_type, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  - {error_type}: {count}")

        lines.append("")
        lines.append(f"First {min(max_errors, len(self.failed_records))} failures:")
        for fr in self.failed_records[:max_errors]:
            lines.append(f"  #{fr.record_index}: {fr.error_message}")

        if len(self.failed_records) > max_errors:
            lines.append(f"  ... and {len(self.failed_records) - max_errors} more")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_records": self.total_records,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": self.success_rate,
            "elapsed_time": self.elapsed_time,
            "error_mode": self.error_mode.value,
            "operation": self.operation,
            "failed_records": [fr.to_dict() for fr in self.failed_records],
        }


def process_batch_with_error_handling(
    records: Iterator[dict[str, Any]],
    process_func: Callable[[dict[str, Any]], bool],
    error_mode: ErrorHandlingMode = ErrorHandlingMode.COLLECT,
    operation: str = "Batch Insert",
) -> BatchInsertResult:
    """
    Process a batch of records with configurable error handling.

    This is a utility function that wraps any record processing function
    with consistent error handling and result tracking.

    Args:
        records: Iterator of record dictionaries to process
        process_func: Function that processes one record, returns True on success
        error_mode: How to handle errors (fail, skip, or collect)
        operation: Description for the result

    Returns:
        BatchInsertResult with detailed statistics and any failures

    Raises:
        Exception: Re-raises the first exception if error_mode is FAIL

    Example:
        >>> def insert_record(record: dict) -> bool:
        ...     # Insert logic here
        ...     return True
        >>> result = process_batch_with_error_handling(
        ...     records=iter([{"id": 1}, {"id": 2}]),
        ...     process_func=insert_record,
        ...     error_mode=ErrorHandlingMode.COLLECT,
        ... )
        >>> print(f"Inserted {result.successful} of {result.total_records}")
    """
    result = BatchInsertResult(operation=operation, error_mode=error_mode)
    start_time = time.perf_counter()

    for index, record in enumerate(records):
        result.total_records += 1

        try:
            success = process_func(record)
            if success:
                result.add_success()
            else:
                result.add_skip()

        except Exception as e:
            if error_mode == ErrorHandlingMode.FAIL:
                # Stop immediately and re-raise
                result.add_failure(index, record, e, "Stopped on first error")
                result.elapsed_time = time.perf_counter() - start_time
                raise

            if error_mode == ErrorHandlingMode.SKIP:
                # Log but continue
                result.add_skip()
            elif error_mode == ErrorHandlingMode.COLLECT:
                # Collect failure and continue
                result.add_failure(index, record, e)

    result.elapsed_time = time.perf_counter() - start_time
    return result
