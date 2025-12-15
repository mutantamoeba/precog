"""
Race Condition Tests for Historical Elo Loader.

Tests thread safety and concurrent access patterns.

Reference: TESTING_STRATEGY V3.2 - Race tests for concurrency
Related Requirements: REQ-DATA-003, Issue #208

Usage:
    pytest tests/race/database/seeding/test_historical_elo_loader_race.py -v -m race
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.seeding.historical_elo_loader import (
    HistoricalEloRecord,
    LoadResult,
    bulk_insert_historical_elo,
    normalize_team_code,
)

# =============================================================================
# Fixtures
# =============================================================================


def create_test_record(idx: int) -> HistoricalEloRecord:
    """Create a test record with unique values."""
    return HistoricalEloRecord(
        team_code=f"T{idx:02d}"[:3],  # Max 3 chars
        sport="nfl",
        season=2023,
        rating_date=date(2023, 9, (idx % 28) + 1),
        elo_rating=Decimal(f"1500.{idx:02d}"),
        qb_adjusted_elo=None,
        qb_name=None,
        qb_value=None,
        source="race_test",
        source_file=None,
    )


# =============================================================================
# Race Tests: Concurrent Normalization
# =============================================================================


@pytest.mark.race
class TestConcurrentNormalization:
    """Race tests for concurrent team code normalization."""

    def test_concurrent_normalize_calls(self) -> None:
        """Test normalizing team codes concurrently is thread-safe."""
        results: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()
        codes = ["KC", "WSH", "OAK", "SD", "STL", "BUF", "nyj", "det"]

        def normalize_code(idx: int) -> None:
            try:
                code = codes[idx % len(codes)]
                result = normalize_team_code(code)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(normalize_code, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()  # Raise any exceptions

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 100

    def test_normalize_same_code_concurrently(self) -> None:
        """Test normalizing the same code from multiple threads."""
        results: list[str] = []
        lock = threading.Lock()

        def normalize_wsh(_: int) -> None:
            result = normalize_team_code("WSH")
            with lock:
                results.append(result)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(normalize_wsh, i) for i in range(50)]
            for future in as_completed(futures):
                future.result()

        # All results should be the same
        assert all(r == "WAS" for r in results)


# =============================================================================
# Race Tests: Concurrent Record Creation
# =============================================================================


@pytest.mark.race
class TestConcurrentRecordCreation:
    """Race tests for concurrent record creation."""

    def test_create_records_concurrently(self) -> None:
        """Test creating HistoricalEloRecord instances concurrently."""
        results: list[HistoricalEloRecord] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def create_record(idx: int) -> None:
            try:
                record = create_test_record(idx)
                with lock:
                    results.append(record)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_record, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 100


# =============================================================================
# Race Tests: Concurrent LoadResult Updates
# =============================================================================


@pytest.mark.race
class TestConcurrentLoadResultUpdates:
    """Race tests for LoadResult updates."""

    def test_create_load_results_concurrently(self) -> None:
        """Test creating LoadResult instances concurrently."""
        results: list[LoadResult] = []
        lock = threading.Lock()

        def create_result(idx: int) -> None:
            result = LoadResult(
                records_processed=idx,
                records_inserted=idx // 2,
                records_skipped=idx // 4,
            )
            with lock:
                results.append(result)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_result, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 100


# =============================================================================
# Race Tests: Concurrent Bulk Insert Calls
# =============================================================================


@pytest.mark.race
class TestConcurrentBulkInsert:
    """Race tests for concurrent bulk insert operations."""

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_concurrent_bulk_inserts(self, mock_flush: MagicMock, mock_get_team: MagicMock) -> None:
        """Test calling bulk_insert from multiple threads."""
        mock_get_team.return_value = 1
        mock_flush.return_value = 10

        results: list[LoadResult] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def do_bulk_insert(idx: int) -> None:
            try:
                records = [create_test_record(i + idx * 10) for i in range(10)]
                result = bulk_insert_historical_elo(iter(records))
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(do_bulk_insert, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        # Each call processed 10 records
        for result in results:
            assert result.records_processed == 10
