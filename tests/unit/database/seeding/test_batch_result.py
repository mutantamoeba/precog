"""
Unit tests for batch insert result types and error handling.

Tests cover:
    - ErrorHandlingMode enum values
    - FailedRecord dataclass
    - BatchInsertResult properties and methods
    - process_batch_with_error_handling utility

Reference:
    - Issue #255: Improve batch insert error handling with partial failure tracking
"""

from __future__ import annotations

from precog.database.seeding.batch_result import (
    BatchInsertResult,
    ErrorHandlingMode,
    FailedRecord,
    process_batch_with_error_handling,
)


class TestErrorHandlingMode:
    """Test ErrorHandlingMode enum."""

    def test_fail_mode_value(self) -> None:
        """FAIL mode should have value 'fail'."""
        assert ErrorHandlingMode.FAIL.value == "fail"

    def test_skip_mode_value(self) -> None:
        """SKIP mode should have value 'skip'."""
        assert ErrorHandlingMode.SKIP.value == "skip"

    def test_collect_mode_value(self) -> None:
        """COLLECT mode should have value 'collect'."""
        assert ErrorHandlingMode.COLLECT.value == "collect"

    def test_all_modes_have_unique_values(self) -> None:
        """All modes should have unique string values."""
        values = [mode.value for mode in ErrorHandlingMode]
        assert len(values) == len(set(values))


class TestFailedRecord:
    """Test FailedRecord dataclass."""

    def test_basic_creation(self) -> None:
        """Should create FailedRecord with required fields."""
        record = FailedRecord(
            record_index=5,
            record_data={"id": 123, "name": "test"},
            error_type="IntegrityError",
            error_message="Duplicate key violation",
        )
        assert record.record_index == 5
        assert record.record_data == {"id": 123, "name": "test"}
        assert record.error_type == "IntegrityError"
        assert record.error_message == "Duplicate key violation"
        assert record.context == ""  # Default empty

    def test_with_context(self) -> None:
        """Should accept optional context field."""
        record = FailedRecord(
            record_index=0,
            record_data={"team": "KC"},
            error_type="ForeignKeyError",
            error_message="Team not found",
            context="table: historical_elo",
        )
        assert record.context == "table: historical_elo"

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        record = FailedRecord(
            record_index=10,
            record_data={"value": 100},
            error_type="ValueError",
            error_message="Invalid value",
            context="validation",
        )
        d = record.to_dict()
        assert d["record_index"] == 10
        assert d["record_data"] == {"value": 100}
        assert d["error_type"] == "ValueError"
        assert d["error_message"] == "Invalid value"
        assert d["context"] == "validation"

    def test_str_representation(self) -> None:
        """Should have readable string representation."""
        record = FailedRecord(
            record_index=3,
            record_data={},
            error_type="Error",
            error_message="Something went wrong",
        )
        assert "Record #3" in str(record)
        assert "Error" in str(record)
        assert "Something went wrong" in str(record)

    def test_str_with_context(self) -> None:
        """String representation should include context if present."""
        record = FailedRecord(
            record_index=1,
            record_data={},
            error_type="Error",
            error_message="Failed",
            context="extra info",
        )
        assert "(extra info)" in str(record)


class TestBatchInsertResult:
    """Test BatchInsertResult dataclass."""

    def test_default_values(self) -> None:
        """Should initialize with sensible defaults."""
        result = BatchInsertResult()
        assert result.total_records == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.failed_records == []
        assert result.elapsed_time == 0.0
        assert result.error_mode == ErrorHandlingMode.FAIL
        assert result.operation == ""

    def test_success_rate_empty(self) -> None:
        """Success rate should be 0 when no records processed."""
        result = BatchInsertResult()
        assert result.success_rate == 0.0

    def test_success_rate_all_successful(self) -> None:
        """Success rate should be 100% when all succeed."""
        result = BatchInsertResult(total_records=100, successful=100)
        assert result.success_rate == 100.0

    def test_success_rate_partial(self) -> None:
        """Success rate should calculate correctly for partial success."""
        result = BatchInsertResult(total_records=100, successful=75)
        assert result.success_rate == 75.0

    def test_success_rate_with_failures(self) -> None:
        """Success rate should reflect failures."""
        result = BatchInsertResult(total_records=10, successful=8, failed=2)
        assert result.success_rate == 80.0

    def test_has_failures_false(self) -> None:
        """has_failures should be False when no failures."""
        result = BatchInsertResult(total_records=10, successful=10)
        assert result.has_failures is False

    def test_has_failures_true(self) -> None:
        """has_failures should be True when failures exist."""
        result = BatchInsertResult(total_records=10, successful=8, failed=2)
        assert result.has_failures is True

    def test_all_succeeded_true(self) -> None:
        """all_succeeded should be True when no failures or skips."""
        result = BatchInsertResult(total_records=10, successful=10)
        assert result.all_succeeded is True

    def test_all_succeeded_false_with_failures(self) -> None:
        """all_succeeded should be False with failures."""
        result = BatchInsertResult(total_records=10, successful=9, failed=1)
        assert result.all_succeeded is False

    def test_all_succeeded_false_with_skips(self) -> None:
        """all_succeeded should be False with skips."""
        result = BatchInsertResult(total_records=10, successful=9, skipped=1)
        assert result.all_succeeded is False

    def test_add_failure(self) -> None:
        """add_failure should increment failed count and add record."""
        result = BatchInsertResult()
        error = ValueError("Test error")
        result.add_failure(
            record_index=0,
            record_data={"id": 1},
            error=error,
            context="test context",
        )
        assert result.failed == 1
        assert len(result.failed_records) == 1
        assert result.failed_records[0].error_type == "ValueError"
        assert result.failed_records[0].error_message == "Test error"
        assert result.failed_records[0].context == "test context"

    def test_add_success(self) -> None:
        """add_success should increment successful count."""
        result = BatchInsertResult()
        result.add_success()
        result.add_success()
        assert result.successful == 2

    def test_add_skip(self) -> None:
        """add_skip should increment skipped count."""
        result = BatchInsertResult()
        result.add_skip()
        assert result.skipped == 1

    def test_get_failure_summary_no_failures(self) -> None:
        """Failure summary should indicate no failures."""
        result = BatchInsertResult(total_records=10, successful=10)
        assert "No failures" in result.get_failure_summary()

    def test_get_failure_summary_with_failures(self) -> None:
        """Failure summary should include failure details."""
        result = BatchInsertResult(total_records=10, successful=8)
        result.add_failure(0, {"id": 1}, ValueError("Error 1"))
        result.add_failure(1, {"id": 2}, ValueError("Error 2"))

        summary = result.get_failure_summary()
        assert "Failed 2 of 10 records" in summary
        assert "ValueError" in summary
        assert "Error 1" in summary

    def test_get_failure_summary_max_errors(self) -> None:
        """Failure summary should respect max_errors limit."""
        result = BatchInsertResult(total_records=20, successful=5)
        for i in range(15):
            result.add_failure(i, {"id": i}, ValueError(f"Error {i}"))

        summary = result.get_failure_summary(max_errors=5)
        assert "and 10 more" in summary

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        result = BatchInsertResult(
            total_records=100,
            successful=95,
            failed=3,
            skipped=2,
            elapsed_time=1.5,
            error_mode=ErrorHandlingMode.COLLECT,
            operation="Test Insert",
        )
        result.add_failure(0, {"id": 1}, ValueError("Test"))

        d = result.to_dict()
        assert d["total_records"] == 100
        assert d["successful"] == 95  # Unchanged by add_failure
        assert d["failed"] == 4  # 3 + 1 from add_failure
        assert d["success_rate"] == 95.0  # 95/100 * 100
        assert d["error_mode"] == "collect"
        assert d["operation"] == "Test Insert"
        assert len(d["failed_records"]) == 1


class TestBatchInsertResultCompatibility:
    """Test backward compatibility properties with LoadResult field names."""

    def test_records_processed_alias(self) -> None:
        """records_processed should alias total_records."""
        result = BatchInsertResult(total_records=100)
        assert result.records_processed == 100

    def test_records_inserted_alias(self) -> None:
        """records_inserted should alias successful."""
        result = BatchInsertResult(successful=75)
        assert result.records_inserted == 75

    def test_records_skipped_alias(self) -> None:
        """records_skipped should alias skipped."""
        result = BatchInsertResult(skipped=10)
        assert result.records_skipped == 10

    def test_errors_alias(self) -> None:
        """errors should alias failed."""
        result = BatchInsertResult(failed=5)
        assert result.errors == 5

    def test_error_messages_returns_strings(self) -> None:
        """error_messages should return list of string representations."""
        result = BatchInsertResult()
        result.add_failure(0, {"id": 1}, ValueError("Error 1"))
        result.add_failure(1, {"id": 2}, TypeError("Error 2"))

        messages = result.error_messages
        assert len(messages) == 2
        assert "Record #0" in messages[0]
        assert "ValueError" in messages[0]
        assert "Error 1" in messages[0]
        assert "TypeError" in messages[1]

    def test_loadresult_usage_pattern(self) -> None:
        """Verify BatchInsertResult works with LoadResult access patterns."""
        # Simulates existing code that expects LoadResult
        result = BatchInsertResult(
            total_records=100,
            successful=90,
            skipped=5,
            failed=5,
        )

        # These patterns should work (LoadResult field names)
        assert result.records_processed == 100
        assert result.records_inserted == 90
        assert result.records_skipped == 5
        assert result.errors == 5

        # Common LoadResult usage patterns
        success_pct = result.records_inserted / result.records_processed * 100
        assert success_pct == 90.0


class TestProcessBatchWithErrorHandling:
    """Test process_batch_with_error_handling utility."""

    def test_all_succeed(self) -> None:
        """Should track all successful records."""
        records = [{"id": i} for i in range(5)]

        def process(record: dict) -> bool:
            return True

        result = process_batch_with_error_handling(
            records=iter(records),
            process_func=process,
            operation="Test",
        )

        assert result.total_records == 5
        assert result.successful == 5
        assert result.failed == 0
        assert result.all_succeeded is True

    def test_collect_mode_continues_on_error(self) -> None:
        """COLLECT mode should process all records despite errors."""
        records = [{"id": i} for i in range(5)]

        def process(record: dict) -> bool:
            if record["id"] == 2:
                raise ValueError("Failure on record 2")
            return True

        result = process_batch_with_error_handling(
            records=iter(records),
            process_func=process,
            error_mode=ErrorHandlingMode.COLLECT,
        )

        assert result.total_records == 5
        assert result.successful == 4
        assert result.failed == 1
        assert len(result.failed_records) == 1
        assert result.failed_records[0].record_index == 2

    def test_skip_mode_continues_on_error(self) -> None:
        """SKIP mode should skip failed records and continue."""
        records = [{"id": i} for i in range(5)]

        def process(record: dict) -> bool:
            if record["id"] == 1:
                raise ValueError("Skip this")
            return True

        result = process_batch_with_error_handling(
            records=iter(records),
            process_func=process,
            error_mode=ErrorHandlingMode.SKIP,
        )

        assert result.total_records == 5
        assert result.successful == 4
        assert result.skipped == 1
        assert result.failed == 0  # SKIP mode doesn't track as failures

    def test_fail_mode_stops_on_first_error(self) -> None:
        """FAIL mode should stop processing on first error."""
        records = [{"id": i} for i in range(5)]
        processed_ids: list[int] = []

        def process(record: dict) -> bool:
            processed_ids.append(record["id"])
            if record["id"] == 2:
                raise ValueError("Stop here")
            return True

        import pytest

        with pytest.raises(ValueError, match="Stop here"):
            process_batch_with_error_handling(
                records=iter(records),
                process_func=process,
                error_mode=ErrorHandlingMode.FAIL,
            )

        # Should have processed 0, 1, 2 then stopped
        assert processed_ids == [0, 1, 2]

    def test_tracks_elapsed_time(self) -> None:
        """Should track elapsed time."""
        records = [{"id": 1}]

        def process(record: dict) -> bool:
            import time

            time.sleep(0.01)  # Small delay
            return True

        result = process_batch_with_error_handling(
            records=iter(records),
            process_func=process,
        )

        assert result.elapsed_time >= 0.01

    def test_tracks_skips_from_process_func(self) -> None:
        """Should track skips when process_func returns False."""
        records = [{"id": i} for i in range(5)]

        def process(record: dict) -> bool:
            # Skip even IDs
            return record["id"] % 2 != 0

        result = process_batch_with_error_handling(
            records=iter(records),
            process_func=process,
        )

        assert result.total_records == 5
        assert result.successful == 2  # 1, 3
        assert result.skipped == 3  # 0, 2, 4

    def test_multiple_error_types_collected(self) -> None:
        """COLLECT mode should capture different error types."""
        records = [{"id": i} for i in range(4)]

        def process(record: dict) -> bool:
            if record["id"] == 1:
                raise ValueError("Value error")
            if record["id"] == 2:
                raise TypeError("Type error")
            return True

        result = process_batch_with_error_handling(
            records=iter(records),
            process_func=process,
            error_mode=ErrorHandlingMode.COLLECT,
        )

        assert result.failed == 2
        error_types = {fr.error_type for fr in result.failed_records}
        assert "ValueError" in error_types
        assert "TypeError" in error_types

    def test_empty_records(self) -> None:
        """Should handle empty record iterator."""

        def process(record: dict) -> bool:
            return True

        result = process_batch_with_error_handling(
            records=iter([]),
            process_func=process,
        )

        assert result.total_records == 0
        assert result.successful == 0
        assert result.success_rate == 0.0
