"""
Stress Tests for Seeding Manager.

Tests high volume operations and resource behavior under load.

Reference: TESTING_STRATEGY V3.2 - Stress tests for resource limits
Related Requirements: REQ-DATA-003, ADR-029

Usage:
    pytest tests/stress/database/seeding/test_seeding_manager_stress.py -v -m stress
"""

import gc
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

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
def temp_seeds_dir_large() -> Path:
    """Create a temporary directory with many mock SQL seed files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        seeds_path = Path(tmpdir)

        # Create many seed files for stress testing
        sports = ["nfl", "nba", "nhl", "ncaaf", "ncaab", "wnba", "ncaaw"]
        for i, sport in enumerate(sports):
            sql_file = seeds_path / f"{i:03d}_{sport}_teams.sql"
            sql_file.write_text(
                f"-- {sport.upper()} Teams\n"
                f"INSERT INTO teams (team_code, team_name, sport) "
                f"VALUES ('TEST', 'Test Team', '{sport}') ON CONFLICT DO NOTHING;"
            )

        yield seeds_path


# =============================================================================
# Stress Tests: Configuration Volume
# =============================================================================


@pytest.mark.stress
class TestConfigurationStress:
    """Stress tests for configuration handling."""

    def test_many_config_creations(self) -> None:
        """Test creating many config instances."""
        iterations = 1000

        start = time.perf_counter()
        configs = []
        for i in range(iterations):
            config = SeedingConfig(
                categories=list(SeedCategory),
                sports=["nfl", "nba"],
                seasons=[2024, 2025],
            )
            configs.append(config)
        elapsed = time.perf_counter() - start

        assert len(configs) == iterations
        assert elapsed < 2.0, f"1000 configs took {elapsed:.2f}s"

    def test_config_with_many_sports(self) -> None:
        """Test config with many sports listed."""
        # Duplicate sports to stress list handling
        sports = ["nfl", "nba", "nhl", "ncaaf", "ncaab", "wnba", "ncaaw"] * 100

        start = time.perf_counter()
        config = SeedingConfig(sports=sports)
        elapsed = time.perf_counter() - start

        assert len(config.sports) == 700
        assert elapsed < 1.0


# =============================================================================
# Stress Tests: Manager Instance Volume
# =============================================================================


@pytest.mark.stress
class TestManagerInstanceStress:
    """Stress tests for manager instance creation."""

    def test_many_manager_instances(self) -> None:
        """Test creating many manager instances."""
        iterations = 100

        start = time.perf_counter()
        managers = []
        for _ in range(iterations):
            config = SeedingConfig(use_api=False)
            manager = SeedingManager(config=config)
            managers.append(manager)
        elapsed = time.perf_counter() - start

        assert len(managers) == iterations
        assert elapsed < 5.0, f"100 managers took {elapsed:.2f}s"

    def test_manager_memory_cleanup(self) -> None:
        """Test manager instances are properly garbage collected."""
        gc.collect()

        # Create and discard many managers
        for _ in range(100):
            config = SeedingConfig(use_api=False)
            manager = SeedingManager(config=config)
            del manager

        gc.collect()
        # Should complete without memory error


# =============================================================================
# Stress Tests: Session Operations
# =============================================================================


@pytest.mark.stress
class TestSessionOperationsStress:
    """Stress tests for session operations."""

    def test_many_session_starts(self) -> None:
        """Test starting many sessions."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        iterations = 500
        start = time.perf_counter()

        for _ in range(iterations):
            manager._start_session()

        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"500 sessions took {elapsed:.2f}s"

    def test_rapid_session_cycles(self) -> None:
        """Test rapid session start/complete cycles."""
        config = SeedingConfig(
            categories=[SeedCategory.TEAMS],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            manager._start_session()
            manager._complete_session()

        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"100 cycles took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Statistics Tracking
# =============================================================================


@pytest.mark.stress
class TestStatisticsTrackingStress:
    """Stress tests for statistics tracking."""

    def test_many_stats_initializations(self) -> None:
        """Test initializing stats many times."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            for category in SeedCategory:
                manager._init_stats(category)

        elapsed = time.perf_counter() - start
        total_ops = iterations * len(SeedCategory)
        assert elapsed < 2.0, f"{total_ops} inits took {elapsed:.2f}s"

    def test_error_recording_volume(self) -> None:
        """Test recording many errors."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        manager._start_session()
        manager._category_stats[SeedCategory.TEAMS.value] = manager._init_stats(SeedCategory.TEAMS)

        iterations = 1000
        start = time.perf_counter()

        for i in range(iterations):
            manager._record_error(SeedCategory.TEAMS, f"Error {i}")

        elapsed = time.perf_counter() - start

        assert manager._category_stats[SeedCategory.TEAMS.value]["errors"] == iterations
        assert elapsed < 1.0, f"1000 errors took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: SQL File Processing
# =============================================================================


@pytest.mark.stress
class TestSQLFileProcessingStress:
    """Stress tests for SQL file processing."""

    def test_many_sql_files_dry_run(self, temp_seeds_dir_large: Path) -> None:
        """Test processing many SQL files in dry-run mode."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir_large,
            sports=["nfl", "nba", "nhl", "ncaaf", "ncaab", "wnba", "ncaaw"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        iterations = 50
        start = time.perf_counter()

        for _ in range(iterations):
            manager.seed_teams()

        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"50 dry runs took {elapsed:.2f}s"

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_many_sql_file_executions(
        self, mock_get_cursor: MagicMock, temp_seeds_dir_large: Path
    ) -> None:
        """Test executing many SQL files."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 32
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir_large,
            sports=["nfl", "nba", "nhl"],
            use_api=False,
        )
        manager = SeedingManager(config=config)

        iterations = 20
        start = time.perf_counter()

        for _ in range(iterations):
            manager.seed_teams()

        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"20 executions took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Report Generation
# =============================================================================


@pytest.mark.stress
class TestReportGenerationStress:
    """Stress tests for report generation."""

    def test_many_report_generations(self) -> None:
        """Test generating many reports."""
        config = SeedingConfig(
            categories=[SeedCategory.TEAMS],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        iterations = 100
        reports = []
        start = time.perf_counter()

        for _ in range(iterations):
            report = manager.seed_all()
            reports.append(report)

        elapsed = time.perf_counter() - start

        assert len(reports) == iterations
        assert elapsed < 10.0, f"100 reports took {elapsed:.2f}s"

    def test_report_with_many_categories(self) -> None:
        """Test report generation with all categories."""
        config = SeedingConfig(
            categories=list(SeedCategory),
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        iterations = 50
        start = time.perf_counter()

        for _ in range(iterations):
            manager.seed_all()

        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"50 full reports took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Memory Behavior
# =============================================================================


@pytest.mark.stress
class TestMemoryBehaviorStress:
    """Stress tests for memory behavior."""

    def test_stats_no_memory_leak(self) -> None:
        """Test that stats tracking doesn't leak memory."""
        gc.collect()

        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        # Track many operations
        for _ in range(1000):
            manager._start_session()
            for category in SeedCategory:
                manager._category_stats[category.value] = manager._init_stats(category)
            manager._complete_session()

        gc.collect()
        # Should complete without memory error

    def test_report_memory_cleanup(self) -> None:
        """Test that reports are properly cleaned up."""
        gc.collect()

        config = SeedingConfig(
            categories=[SeedCategory.TEAMS],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        reports = []
        for _ in range(500):
            report = manager.seed_all()
            reports.append(report)

        # Clear references
        reports.clear()
        gc.collect()
        # Should complete without memory error


# =============================================================================
# Stress Tests: Category Enumeration
# =============================================================================


@pytest.mark.stress
class TestCategoryEnumerationStress:
    """Stress tests for category enumeration operations."""

    def test_category_iteration_volume(self) -> None:
        """Test iterating categories many times."""
        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            for category in SeedCategory:
                _ = category.value

        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"10000 iterations took {elapsed:.2f}s"

    def test_category_comparison_volume(self) -> None:
        """Test category comparisons at volume."""
        iterations = 10000
        categories = list(SeedCategory)

        start = time.perf_counter()
        for _ in range(iterations):
            for cat in categories:
                _ = cat == "teams"

        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Comparisons took {elapsed:.2f}s"
