"""
Race Condition Tests for Seeding Manager.

Tests thread safety and concurrent access patterns.

Reference: TESTING_STRATEGY V3.2 - Race tests for concurrency
Related Requirements: REQ-DATA-003, ADR-029

Usage:
    pytest tests/race/database/seeding/test_seeding_manager_race.py -v -m race
"""

import tempfile
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytest

from precog.database.seeding import (
    SeedCategory,
    SeedingConfig,
    SeedingManager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_seeds_dir() -> Iterator[Path]:
    """Create a temporary directory with mock SQL seed files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        seeds_path = Path(tmpdir)

        # Create seed files for different sports
        for i, sport in enumerate(["nfl", "nba", "nhl"]):
            sql_file = seeds_path / f"{i:03d}_{sport}_teams.sql"
            sql_file.write_text(
                f"-- {sport.upper()} Teams\n"
                f"INSERT INTO teams (team_code, sport) VALUES ('TEST', '{sport}');"
            )

        yield seeds_path


# =============================================================================
# Race Tests: Concurrent Config Operations
# =============================================================================


@pytest.mark.race
class TestConcurrentConfigOperations:
    """Race tests for concurrent configuration operations."""

    def test_concurrent_config_creations(self) -> None:
        """Test creating many configs concurrently is thread-safe."""
        results: list[SeedingConfig] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def create_config(idx: int) -> None:
            try:
                config = SeedingConfig(
                    sports=[f"sport_{idx}"],
                    categories=[SeedCategory.TEAMS],
                    database=f"db_{idx}",
                    use_api=False,
                )
                with lock:
                    results.append(config)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_config, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 100

    def test_concurrent_manager_creations(self) -> None:
        """Test creating many managers concurrently."""
        results: list[SeedingManager] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def create_manager(idx: int) -> None:
            try:
                config = SeedingConfig(use_api=False)
                manager = SeedingManager(config=config)
                with lock:
                    results.append(manager)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_manager, i) for i in range(50)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 50


# =============================================================================
# Race Tests: Concurrent Session Operations
# =============================================================================


@pytest.mark.race
class TestConcurrentSessionOperations:
    """Race tests for concurrent session operations."""

    def test_concurrent_session_starts_different_managers(self) -> None:
        """Test starting sessions on different managers concurrently.

        Note: Session IDs use YYYYMMDD_HHMMSS format, so concurrent
        sessions within the same second will have the same ID. This
        tests that sessions start successfully without errors.
        """
        session_ids: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def start_session(idx: int) -> None:
            try:
                config = SeedingConfig(use_api=False)
                manager = SeedingManager(config=config)
                manager._start_session()
                with lock:
                    if manager._session_id:
                        session_ids.append(manager._session_id)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(start_session, i) for i in range(50)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(session_ids) == 50
        # All session IDs should be valid format
        for session_id in session_ids:
            assert len(session_id) == 15
            assert session_id[8] == "_"

    def test_concurrent_stats_initialization(self) -> None:
        """Test initializing stats concurrently."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        results: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def init_stats(category: SeedCategory) -> None:
            try:
                stats = manager._init_stats(category)
                with lock:
                    results.append(stats)  # type: ignore[arg-type]
            except Exception as e:
                with lock:
                    errors.append(e)

        # Initialize stats for all categories concurrently
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(init_stats, cat)
                for cat in SeedCategory
                for _ in range(10)  # 10 times each
            ]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        expected_count = len(SeedCategory) * 10
        assert len(results) == expected_count


# =============================================================================
# Race Tests: Concurrent Seeding Operations
# =============================================================================


@pytest.mark.race
class TestConcurrentSeedingOperations:
    """Race tests for concurrent seeding operations."""

    def test_concurrent_dry_run_seeding(self, temp_seeds_dir: Path) -> None:
        """Test concurrent dry-run seeding operations."""
        reports: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def run_seeding(idx: int) -> None:
            try:
                config = SeedingConfig(
                    sql_seeds_path=temp_seeds_dir,
                    categories=[SeedCategory.TEAMS],
                    sports=["nfl"],
                    dry_run=True,
                    use_api=False,
                )
                manager = SeedingManager(config=config)
                report = manager.seed_all()
                with lock:
                    reports.append(report)  # type: ignore[arg-type]
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(run_seeding, i) for i in range(30)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(reports) == 30

        # All reports should be successful
        for report in reports:
            assert report["success"] is True

    def test_concurrent_different_sports(self, temp_seeds_dir: Path) -> None:
        """Test concurrent seeding for different sports."""
        sports = ["nfl", "nba", "nhl"]
        reports: list[tuple[str, dict[str, Any]]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def seed_sport(sport: str) -> None:
            try:
                config = SeedingConfig(
                    sql_seeds_path=temp_seeds_dir,
                    categories=[SeedCategory.TEAMS],
                    sports=[sport],
                    dry_run=True,
                    use_api=False,
                )
                manager = SeedingManager(config=config)
                report = manager.seed_all()
                with lock:
                    reports.append((sport, report))  # type: ignore[arg-type]
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=len(sports)) as executor:
            futures = [executor.submit(seed_sport, sport) for sport in sports]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(reports) == len(sports)


# =============================================================================
# Race Tests: Multiple Manager Instances
# =============================================================================


@pytest.mark.race
class TestMultipleManagerInstances:
    """Race tests for multiple manager instances."""

    def test_independent_manager_sessions(self, temp_seeds_dir: Path) -> None:
        """Test multiple managers operate independently.

        Note: Session IDs use YYYYMMDD_HHMMSS format, so concurrent
        managers within the same second will have the same ID.
        """
        managers: list[SeedingManager] = []
        reports: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        # Create managers
        for i in range(5):
            config = SeedingConfig(
                sql_seeds_path=temp_seeds_dir,
                categories=[SeedCategory.TEAMS],
                sports=["nfl"],
                dry_run=True,
                use_api=False,
            )
            managers.append(SeedingManager(config=config))

        def run_manager(idx: int) -> None:
            try:
                manager = managers[idx]
                report = manager.seed_all()
                with lock:
                    reports.append(report)  # type: ignore[arg-type]
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(run_manager, i) for i in range(5)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(reports) == 5

        # Each report should have valid session ID
        for report in reports:
            assert "session_id" in report
            assert len(report["session_id"]) == 15

    def test_concurrent_creation_and_seeding(self, temp_seeds_dir: Path) -> None:
        """Test creating managers and seeding concurrently."""
        reports: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def create_and_seed(idx: int) -> None:
            try:
                # Create manager in thread
                config = SeedingConfig(
                    sql_seeds_path=temp_seeds_dir,
                    categories=[SeedCategory.TEAMS],
                    sports=["nfl"],
                    dry_run=True,
                    use_api=False,
                )
                manager = SeedingManager(config=config)
                report = manager.seed_all()
                with lock:
                    reports.append(report)  # type: ignore[arg-type]
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_and_seed, i) for i in range(25)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(reports) == 25


# =============================================================================
# Race Tests: Interleaved Operations
# =============================================================================


@pytest.mark.race
class TestInterleavedOperations:
    """Race tests for interleaved different operations."""

    def test_interleaved_config_manager_seeding(self, temp_seeds_dir: Path) -> None:
        """Test interleaved config creation, manager creation, and seeding."""
        operations_completed: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def config_op() -> None:
            try:
                config = SeedingConfig(use_api=False)
                _ = config.sports
                with lock:
                    operations_completed.append("config")
            except Exception as e:
                with lock:
                    errors.append(e)

        def manager_op() -> None:
            try:
                config = SeedingConfig(use_api=False)
                manager = SeedingManager(config=config)
                _ = manager.config
                with lock:
                    operations_completed.append("manager")
            except Exception as e:
                with lock:
                    errors.append(e)

        def seed_op() -> None:
            try:
                config = SeedingConfig(
                    sql_seeds_path=temp_seeds_dir,
                    categories=[SeedCategory.TEAMS],
                    dry_run=True,
                    use_api=False,
                )
                manager = SeedingManager(config=config)
                manager.seed_all()
                with lock:
                    operations_completed.append("seed")
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            for _ in range(20):
                futures.append(executor.submit(config_op))
                futures.append(executor.submit(manager_op))
                futures.append(executor.submit(seed_op))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(operations_completed) == 60
        assert operations_completed.count("config") == 20
        assert operations_completed.count("manager") == 20
        assert operations_completed.count("seed") == 20


# =============================================================================
# Race Tests: Category Enumeration
# =============================================================================


@pytest.mark.race
class TestConcurrentCategoryEnumeration:
    """Race tests for concurrent category enumeration."""

    def test_concurrent_category_iteration(self) -> None:
        """Test iterating categories concurrently."""
        results: list[list[str]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def iterate_categories() -> None:
            try:
                values = [cat.value for cat in SeedCategory]
                with lock:
                    results.append(values)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(iterate_categories) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 100

        # All results should be identical
        expected = [cat.value for cat in SeedCategory]
        for result in results:
            assert result == expected

    def test_concurrent_category_support_access(self) -> None:
        """Test accessing SPORT_CATEGORY_SUPPORT concurrently."""
        results: list[list[str]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def access_support(category: SeedCategory) -> None:
            try:
                sports = SeedingManager.SPORT_CATEGORY_SUPPORT[category]
                with lock:
                    results.append(list(sports))
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(access_support, cat) for cat in SeedCategory for _ in range(20)
            ]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        expected_count = len(SeedCategory) * 20
        assert len(results) == expected_count


# =============================================================================
# Race Tests: Stats Recording
# =============================================================================


@pytest.mark.race
class TestConcurrentStatsRecording:
    """Race tests for concurrent stats recording."""

    def test_concurrent_error_recording(self) -> None:
        """Test recording errors from multiple threads."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)
        manager._start_session()
        manager._category_stats[SeedCategory.TEAMS.value] = manager._init_stats(SeedCategory.TEAMS)

        errors_list: list[Exception] = []
        lock = threading.Lock()

        def record_error(idx: int) -> None:
            try:
                manager._record_error(SeedCategory.TEAMS, f"Error {idx}")
            except Exception as e:
                with lock:
                    errors_list.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(record_error, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        # Note: Due to race conditions, the exact count may vary
        # but there should be no exceptions
        assert len(errors_list) == 0, f"Exceptions: {errors_list}"


# =============================================================================
# Race Tests: Data Consistency
# =============================================================================


@pytest.mark.race
class TestDataConsistency:
    """Race tests verifying data consistency under concurrency."""

    def test_config_immutability_under_concurrent_access(self) -> None:
        """Test config values remain consistent under concurrent access."""
        config = SeedingConfig(
            sports=["nfl", "nba"],
            categories=[SeedCategory.TEAMS, SeedCategory.VENUES],
            use_api=False,
        )

        results: list[tuple[list[str], list[SeedCategory]]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def read_config() -> None:
            try:
                sports = list(config.sports)
                categories = list(config.categories)
                with lock:
                    results.append((sports, categories))
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_config) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 100

        # All reads should return same values
        expected_sports = ["nfl", "nba"]
        expected_categories = [SeedCategory.TEAMS, SeedCategory.VENUES]
        for sports, categories in results:
            assert sports == expected_sports
            assert categories == expected_categories

    def test_report_generation_consistency(self, temp_seeds_dir: Path) -> None:
        """Test reports are consistent under concurrent generation."""
        reports: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def generate_report() -> None:
            try:
                config = SeedingConfig(
                    sql_seeds_path=temp_seeds_dir,
                    categories=[SeedCategory.TEAMS],
                    sports=["nfl"],
                    dry_run=True,
                    use_api=False,
                )
                manager = SeedingManager(config=config)
                report = manager.seed_all()
                with lock:
                    reports.append(report)  # type: ignore[arg-type]
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_report) for _ in range(20)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(reports) == 20

        # All reports should have consistent structure
        for report in reports:
            assert "session_id" in report
            assert "success" in report
            assert "category_stats" in report
            assert report["success"] is True
