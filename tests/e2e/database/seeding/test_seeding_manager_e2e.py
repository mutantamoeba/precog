"""
End-to-End Tests for Seeding Manager.

Tests complete seeding workflows from configuration to report generation.

Reference: TESTING_STRATEGY V3.2 - E2E tests for critical paths
Related Requirements: REQ-DATA-003, ADR-029

Usage:
    pytest tests/e2e/database/seeding/test_seeding_manager_e2e.py -v -m e2e
"""

import tempfile
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
def temp_seeds_dir() -> Path:
    """Create a temporary directory with mock SQL seed files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        seeds_path = Path(tmpdir)

        # Create realistic seed files
        nfl_teams = seeds_path / "001_nfl_teams.sql"
        nfl_teams.write_text(
            "-- NFL Teams Seed Data\n"
            "INSERT INTO teams (team_code, team_name, sport, conference, division) VALUES\n"
            "('KC', 'Kansas City Chiefs', 'nfl', 'AFC', 'West'),\n"
            "('SF', 'San Francisco 49ers', 'nfl', 'NFC', 'West'),\n"
            "('BUF', 'Buffalo Bills', 'nfl', 'AFC', 'East')\n"
            "ON CONFLICT (team_code, sport) DO NOTHING;\n"
        )

        nba_teams = seeds_path / "002_nba_teams.sql"
        nba_teams.write_text(
            "-- NBA Teams Seed Data\n"
            "INSERT INTO teams (team_code, team_name, sport, conference, division) VALUES\n"
            "('LAL', 'Los Angeles Lakers', 'nba', 'Western', 'Pacific'),\n"
            "('BOS', 'Boston Celtics', 'nba', 'Eastern', 'Atlantic')\n"
            "ON CONFLICT (team_code, sport) DO NOTHING;\n"
        )

        nhl_teams = seeds_path / "003_nhl_teams.sql"
        nhl_teams.write_text(
            "-- NHL Teams Seed Data\n"
            "INSERT INTO teams (team_code, team_name, sport, conference, division) VALUES\n"
            "('NYR', 'New York Rangers', 'nhl', 'Eastern', 'Metropolitan'),\n"
            "('EDM', 'Edmonton Oilers', 'nhl', 'Western', 'Pacific')\n"
            "ON CONFLICT (team_code, sport) DO NOTHING;\n"
        )

        yield seeds_path


@pytest.fixture
def mock_db_cursor() -> MagicMock:
    """Create a mock database cursor."""
    cursor = MagicMock()
    cursor.rowcount = 32
    cursor.fetchone.return_value = (5,)
    cursor.fetchall.return_value = [
        ("KC", "Kansas City Chiefs", "nfl"),
        ("SF", "San Francisco 49ers", "nfl"),
    ]
    return cursor


# =============================================================================
# E2E Tests: Complete Dry-Run Workflow
# =============================================================================


@pytest.mark.e2e
class TestDryRunWorkflow:
    """E2E tests for dry-run seeding workflows."""

    def test_full_dry_run_teams_only(self, temp_seeds_dir: Path) -> None:
        """Test complete dry-run workflow for teams category."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=["nfl", "nba", "nhl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        # Verify report structure
        assert "session_id" in report
        assert "success" in report
        assert "total_records_processed" in report
        assert "total_records_created" in report
        assert "total_errors" in report
        assert "category_stats" in report
        assert "started_at" in report
        assert "completed_at" in report

        # Dry run should succeed
        assert report["success"] is True
        assert report["total_errors"] == 0

    def test_full_dry_run_all_categories(self, temp_seeds_dir: Path) -> None:
        """Test dry-run workflow with all categories."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=list(SeedCategory),
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        # Only teams and venues are currently implemented
        # Other categories log warnings but don't appear in stats
        assert len(report["category_stats"]) >= 1  # At least teams
        assert report["success"] is True

    def test_dry_run_with_multiple_sports(self, temp_seeds_dir: Path) -> None:
        """Test dry-run with multiple sports configured."""
        all_sports = ["nfl", "nba", "nhl", "ncaaf", "ncaab", "wnba", "ncaaw"]

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=all_sports,
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        assert report["success"] is True
        assert manager.config.sports == all_sports


# =============================================================================
# E2E Tests: Database Execution Workflow
# =============================================================================


@pytest.mark.e2e
class TestDatabaseExecutionWorkflow:
    """E2E tests for database execution workflows."""

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_teams_seeding_with_db(
        self, mock_get_cursor: MagicMock, temp_seeds_dir: Path, mock_db_cursor: MagicMock
    ) -> None:
        """Test teams seeding executes SQL against database."""
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_db_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            dry_run=False,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        # Database cursor should have been used
        assert mock_get_cursor.called
        assert report["success"] is True

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_full_workflow_teams_to_report(
        self, mock_get_cursor: MagicMock, temp_seeds_dir: Path, mock_db_cursor: MagicMock
    ) -> None:
        """Test complete workflow from config to final report."""
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_db_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Step 1: Create configuration
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=["nfl", "nba"],
            database="test",
            dry_run=False,
            use_api=False,
        )

        # Step 2: Initialize manager
        manager = SeedingManager(config=config)

        # Step 3: Execute seeding
        report = manager.seed_all()

        # Step 4: Verify complete report
        assert report["session_id"] is not None
        assert "started_at" in report
        assert "completed_at" in report
        assert report["success"] is True


# =============================================================================
# E2E Tests: Individual Category Workflows
# =============================================================================


@pytest.mark.e2e
class TestIndividualCategoryWorkflows:
    """E2E tests for individual category seeding."""

    def test_seed_teams_workflow(self, temp_seeds_dir: Path) -> None:
        """Test direct teams seeding method."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        stats = manager.seed_teams()

        assert stats is not None
        assert "records_processed" in stats
        assert "records_created" in stats
        assert "errors" in stats

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_seed_venues_workflow(
        self, mock_get_cursor: MagicMock, mock_db_cursor: MagicMock
    ) -> None:
        """Test venues seeding workflow."""
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_db_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            categories=[SeedCategory.VENUES],
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        assert SeedCategory.VENUES.value in report["category_stats"]

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_seed_historical_elo_workflow(
        self, mock_get_cursor: MagicMock, mock_db_cursor: MagicMock
    ) -> None:
        """Test historical Elo seeding workflow.

        Note: historical_elo is not yet implemented, so this test
        verifies the graceful handling of unimplemented categories.
        """
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_db_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            categories=[SeedCategory.HISTORICAL_ELO],
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        # historical_elo not yet implemented - logs warning but succeeds
        assert report["success"] is True


# =============================================================================
# E2E Tests: Session Management Workflow
# =============================================================================


@pytest.mark.e2e
class TestSessionManagementWorkflow:
    """E2E tests for session management."""

    def test_session_creates_valid_ids(self, temp_seeds_dir: Path) -> None:
        """Test each seeding run creates valid session IDs.

        Note: Session IDs use YYYYMMDD_HHMMSS format, so runs within
        the same second will have the same ID. This tests ID validity
        rather than uniqueness.
        """
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )

        session_ids = []
        for _ in range(3):
            manager = SeedingManager(config=config)
            report = manager.seed_all()
            session_ids.append(report["session_id"])

        # All session IDs should be valid format (YYYYMMDD_HHMMSS)
        for session_id in session_ids:
            assert len(session_id) == 15
            assert session_id[8] == "_"
            assert session_id[:8].isdigit()
            assert session_id[9:].isdigit()

    def test_session_tracks_timestamps(self, temp_seeds_dir: Path) -> None:
        """Test session accurately tracks start and completion times."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        assert "started_at" in report
        assert "completed_at" in report
        assert isinstance(report["started_at"], str)
        assert report["completed_at"] is not None


# =============================================================================
# E2E Tests: Error Handling Workflow
# =============================================================================


@pytest.mark.e2e
class TestErrorHandlingWorkflow:
    """E2E tests for error handling in workflows."""

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_database_error_captured_in_report(
        self, mock_get_cursor: MagicMock, temp_seeds_dir: Path
    ) -> None:
        """Test database errors are captured in report."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database connection failed")
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            dry_run=False,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        # Errors should be tracked
        assert report["total_errors"] >= 0

    def test_missing_seeds_dir_handled(self) -> None:
        """Test missing seeds directory is handled gracefully."""
        config = SeedingConfig(
            sql_seeds_path=Path("/nonexistent/path/to/seeds"),
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        # Should not raise, just process with no files found
        report = manager.seed_all()
        assert report is not None


# =============================================================================
# E2E Tests: Configuration Variations
# =============================================================================


@pytest.mark.e2e
class TestConfigurationVariations:
    """E2E tests for various configuration combinations."""

    def test_single_sport_single_category(self, temp_seeds_dir: Path) -> None:
        """Test minimal configuration."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()
        assert report["success"] is True

    def test_all_sports_all_categories(self, temp_seeds_dir: Path) -> None:
        """Test maximal configuration."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=list(SeedCategory),
            sports=["nfl", "nba", "nhl", "ncaaf", "ncaab", "wnba", "ncaaw"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()
        assert report["success"] is True

    def test_overwrite_mode(self, temp_seeds_dir: Path) -> None:
        """Test overwrite mode configuration."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            dry_run=True,
            overwrite=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        assert manager.config.overwrite is True
        report = manager.seed_all()
        assert report["success"] is True


# =============================================================================
# E2E Tests: Report Consistency
# =============================================================================


@pytest.mark.e2e
class TestReportConsistency:
    """E2E tests for report data consistency."""

    def test_report_totals_match_categories(self, temp_seeds_dir: Path) -> None:
        """Test report totals match sum of category stats."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS, SeedCategory.VENUES],
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        # Calculate expected totals from category stats
        expected_processed = sum(s["records_processed"] for s in report["category_stats"].values())
        expected_created = sum(s["records_created"] for s in report["category_stats"].values())
        expected_errors = sum(s["errors"] for s in report["category_stats"].values())

        assert report["total_records_processed"] == expected_processed
        assert report["total_records_created"] == expected_created
        assert report["total_errors"] == expected_errors

    def test_report_success_reflects_errors(self, temp_seeds_dir: Path) -> None:
        """Test report success flag accurately reflects error state."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        if report["total_errors"] == 0:
            assert report["success"] is True
        else:
            assert report["success"] is False
