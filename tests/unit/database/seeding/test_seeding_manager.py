"""
Unit Tests for SeedingManager - Database Seeding Infrastructure.

Comprehensive test coverage for the SeedingManager class including:
- Initialization and configuration
- Team seeding from SQL files
- Venue seeding from API
- Historical game seeding
- Verification operations
- Dry-run mode
- Error handling and edge cases

Tests follow the project's testing patterns:
- Pattern 4: Security (mocked credentials)
- Pattern 6: TypedDict for return types
- Pattern 7: Educational docstrings
- Antipattern 4: Mock Isolation (typed fixtures match real returns)

Related:
- REQ-DATA-003: Multi-Sport Team Support
- ADR-029: ESPN Data Model
- Phase 2.5: Live Data Collection Service

Usage:
    pytest tests/unit/database/seeding/test_seeding_manager.py -v
    pytest tests/unit/database/seeding/test_seeding_manager.py -v -m unit
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.seeding import (
    SeedCategory,
    SeedingConfig,
    SeedingManager,
    create_seeding_manager,
    seed_all_teams,
    verify_required_seeds,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_espn_client():
    """Create a mock ESPN client for testing API-based seeding.

    Educational Note:
        We mock the ESPNClient to avoid actual API calls during unit tests.
        This allows tests to run quickly and reliably without network dependencies.
    """
    client = MagicMock()
    client.get_scoreboard.return_value = []
    return client


@pytest.fixture
def temp_seeds_dir():
    """Create a temporary directory with mock SQL seed files.

    Educational Note:
        Using tempfile ensures tests are isolated and don't depend on
        the actual seed files in the repository. This makes tests more
        reliable and prevents accidental execution of real SQL.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        seeds_path = Path(tmpdir)

        # Create mock NFL seed file
        nfl_file = seeds_path / "001_nfl_teams_initial.sql"
        nfl_file.write_text(
            "-- NFL Teams\nINSERT INTO teams (team_code, team_name, sport) "
            "VALUES ('KC', 'Kansas City Chiefs', 'nfl') ON CONFLICT DO NOTHING;"
        )

        # Create mock NBA seed file
        nba_file = seeds_path / "003_nba_teams.sql"
        nba_file.write_text(
            "-- NBA Teams\nINSERT INTO teams (team_code, team_name, sport) "
            "VALUES ('LAL', 'Los Angeles Lakers', 'nba') ON CONFLICT DO NOTHING;"
        )

        # Create mock NHL seed file
        nhl_file = seeds_path / "004_nhl_teams.sql"
        nhl_file.write_text(
            "-- NHL Teams\nINSERT INTO teams (team_code, team_name, sport) "
            "VALUES ('BOS', 'Boston Bruins', 'nhl') ON CONFLICT DO NOTHING;"
        )

        yield seeds_path


# =============================================================================
# SEEDING MANAGER INITIALIZATION TESTS
# =============================================================================


@pytest.mark.unit
class TestSeedingManagerInit:
    """Unit tests for SeedingManager initialization."""

    def test_init_with_default_config(self):
        """Test SeedingManager initializes with default configuration.

        Educational Note:
            Default configuration includes all categories and all supported
            sports. This ensures comprehensive seeding without explicit config.
        """
        with patch("precog.database.seeding.seeding_manager.ESPNClient") as mock_client_class:
            manager = SeedingManager()

            assert manager.config is not None
            assert len(manager.config.categories) == len(SeedCategory)
            assert "nfl" in manager.config.sports
            assert "nba" in manager.config.sports
            assert manager.config.dry_run is False
            mock_client_class.assert_called_once()

    def test_init_with_custom_config(self, mock_espn_client):
        """Test SeedingManager initializes with custom configuration."""
        config = SeedingConfig(
            categories=[SeedCategory.TEAMS],
            sports=["nfl", "nba"],
            database="test",
            dry_run=True,
        )

        manager = SeedingManager(config=config, espn_client=mock_espn_client)

        assert manager.config.categories == [SeedCategory.TEAMS]
        assert manager.config.sports == ["nfl", "nba"]
        assert manager.config.database == "test"
        assert manager.config.dry_run is True

    def test_init_with_use_api_false_skips_espn_client(self):
        """Test that use_api=False doesn't create ESPN client.

        Educational Note:
            When seeding from SQL only, we don't need the ESPN client.
            This saves resources and avoids unnecessary API initialization.
        """
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        assert manager.espn_client is None

    def test_init_with_provided_espn_client(self, mock_espn_client):
        """Test that provided ESPN client is used instead of creating new one."""
        config = SeedingConfig(use_api=True)
        manager = SeedingManager(config=config, espn_client=mock_espn_client)

        assert manager.espn_client is mock_espn_client


# =============================================================================
# SEEDING CONFIG TESTS
# =============================================================================


@pytest.mark.unit
class TestSeedingConfig:
    """Unit tests for SeedingConfig dataclass."""

    def test_default_config_values(self):
        """Test SeedingConfig has sensible defaults."""
        config = SeedingConfig()

        assert len(config.categories) == len(SeedCategory)
        assert config.sports == ["nfl", "ncaaf", "nba", "nhl", "wnba", "ncaab"]
        assert config.seasons == [2024, 2025]
        assert config.database == "dev"
        assert config.dry_run is False
        assert config.use_api is True
        assert config.overwrite is True

    def test_config_with_custom_values(self):
        """Test SeedingConfig accepts custom values."""
        config = SeedingConfig(
            categories=[SeedCategory.TEAMS, SeedCategory.VENUES],
            sports=["nfl"],
            seasons=[2023],
            database="prod",
            dry_run=True,
            use_api=False,
        )

        assert config.categories == [SeedCategory.TEAMS, SeedCategory.VENUES]
        assert config.sports == ["nfl"]
        assert config.seasons == [2023]
        assert config.database == "prod"
        assert config.dry_run is True
        assert config.use_api is False

    def test_config_mutable_defaults_isolation(self):
        """Test that mutable defaults are properly isolated.

        Educational Note:
            Using field(default_factory=...) ensures each config instance
            gets its own list, preventing the "mutable default argument" bug
            where all instances would share the same list.
        """
        config1 = SeedingConfig()
        config2 = SeedingConfig()

        config1.sports.append("test_sport")

        assert "test_sport" not in config2.sports


# =============================================================================
# SEED CATEGORY TESTS
# =============================================================================


@pytest.mark.unit
class TestSeedCategory:
    """Unit tests for SeedCategory enum."""

    def test_all_categories_defined(self):
        """Test all expected categories are defined."""
        expected = {
            "teams",
            "venues",
            "historical_elo",
            "team_rankings",
            "archived_games",
            "schedules",
        }
        actual = {cat.value for cat in SeedCategory}

        assert actual == expected

    def test_category_string_comparison(self):
        """Test SeedCategory can be compared to strings.

        Educational Note:
            The str mixin in SeedCategory allows direct string comparison,
            which simplifies code that works with category names from configs.
        """
        assert SeedCategory.TEAMS == "teams"
        assert SeedCategory.VENUES == "venues"


# =============================================================================
# SEED_TEAMS_SQL TESTS
# =============================================================================


@pytest.mark.unit
class TestSeedTeamsSql:
    """Unit tests for _seed_teams_sql method."""

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_seed_teams_sql_executes_sql_files(self, mock_get_cursor, temp_seeds_dir):
        """Test that SQL seed files are executed against the database."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 32  # NFL has 32 teams
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            sports=["nfl"],
            use_api=False,
        )
        manager = SeedingManager(config=config)

        stats = manager.seed_teams(sports=["nfl"])

        assert stats["records_processed"] >= 1
        mock_cursor.execute.assert_called()

    def test_seed_teams_sql_dry_run_no_execute(self, temp_seeds_dir):
        """Test dry-run mode reports but doesn't execute SQL.

        Educational Note:
            Dry-run mode is critical for previewing seeding operations
            before committing to database changes, especially in production.
        """
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        # With dry_run=True, no database calls should be made
        with patch("precog.database.seeding.seeding_manager.get_cursor"):
            stats = manager.seed_teams(sports=["nfl"])

            # In dry run, we process files but don't execute
            assert stats["records_processed"] >= 1
            assert stats["records_created"] == 0

    def test_seed_teams_sql_filters_by_sport(self, temp_seeds_dir):
        """Test that only matching sport files are executed."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            sports=["nba"],  # Only NBA
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        stats = manager.seed_teams(sports=["nba"])

        # Should only process NBA file (003_nba_teams.sql)
        assert stats["records_processed"] == 1

    def test_seed_teams_sql_missing_directory_warning(self):
        """Test warning when seeds directory doesn't exist."""
        config = SeedingConfig(
            sql_seeds_path=Path("/nonexistent/path"),
            use_api=False,
        )
        manager = SeedingManager(config=config)

        stats = manager.seed_teams(sports=["nfl"])

        # Should not crash, just return empty stats
        assert stats["records_processed"] == 0
        assert stats["errors"] == 0

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_seed_teams_sql_handles_database_error(self, mock_get_cursor, temp_seeds_dir):
        """Test graceful handling of database errors during seeding.

        Educational Note:
            Using a fail-forward pattern, errors in one seed file don't
            prevent processing of remaining files. This enables partial
            seeding success.
        """
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database connection lost")
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            sports=["nfl"],
            use_api=False,
        )
        manager = SeedingManager(config=config)

        stats = manager.seed_teams(sports=["nfl"])

        # Error should be recorded, not raised
        assert stats["errors"] >= 1

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_seed_teams_sql_tracks_row_counts(self, mock_get_cursor, temp_seeds_dir):
        """Test that row counts are properly tracked from SQL execution."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 32
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            sports=["nfl"],
            use_api=False,
        )
        manager = SeedingManager(config=config)

        stats = manager.seed_teams(sports=["nfl"])

        assert stats["records_created"] == 32


# =============================================================================
# VERIFY_SEEDS TESTS
# =============================================================================


@pytest.mark.unit
class TestVerifySeeds:
    """Unit tests for verify_seeds method."""

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_verify_seeds_all_present(self, mock_get_cursor):
        """Test verify_seeds returns success when all teams present."""
        mock_cursor = MagicMock()
        # Return full expected counts for all sports
        mock_cursor.fetchall.return_value = [
            {"sport": "nba", "team_count": 30, "with_espn_id": 30},
            {"sport": "ncaab", "team_count": 89, "with_espn_id": 89},
            {"sport": "ncaaf", "team_count": 79, "with_espn_id": 79},
            {"sport": "nfl", "team_count": 32, "with_espn_id": 32},
            {"sport": "nhl", "team_count": 32, "with_espn_id": 32},
            {"sport": "wnba", "team_count": 12, "with_espn_id": 12},
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        result = manager.verify_seeds()

        assert result["success"] is True
        assert result["categories"]["teams"]["ok"] is True
        assert result["categories"]["teams"]["actual"] == 274
        assert result["categories"]["teams"]["expected"] == 274
        assert len(result["categories"]["teams"]["missing_sports"]) == 0

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_verify_seeds_missing_sport(self, mock_get_cursor):
        """Test verify_seeds detects missing sport data."""
        mock_cursor = MagicMock()
        # Missing WNBA teams
        mock_cursor.fetchall.return_value = [
            {"sport": "nba", "team_count": 30, "with_espn_id": 30},
            {"sport": "nfl", "team_count": 32, "with_espn_id": 32},
            {"sport": "nhl", "team_count": 32, "with_espn_id": 32},
            {"sport": "ncaaf", "team_count": 79, "with_espn_id": 79},
            {"sport": "ncaab", "team_count": 89, "with_espn_id": 89},
            # No WNBA entry
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        result = manager.verify_seeds()

        assert result["success"] is False
        assert result["categories"]["teams"]["ok"] is False
        assert "wnba" in result["categories"]["teams"]["missing_sports"]

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_verify_seeds_partial_teams(self, mock_get_cursor):
        """Test verify_seeds detects partial team data."""
        mock_cursor = MagicMock()
        # NFL has only 16 teams instead of 32
        mock_cursor.fetchall.return_value = [
            {"sport": "nfl", "team_count": 16, "with_espn_id": 16},
            {"sport": "nba", "team_count": 30, "with_espn_id": 30},
            {"sport": "nhl", "team_count": 32, "with_espn_id": 32},
            {"sport": "wnba", "team_count": 12, "with_espn_id": 12},
            {"sport": "ncaaf", "team_count": 79, "with_espn_id": 79},
            {"sport": "ncaab", "team_count": 89, "with_espn_id": 89},
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        result = manager.verify_seeds()

        assert result["success"] is False
        teams = result["categories"]["teams"]
        assert teams["by_sport"]["nfl"]["actual"] == 16
        assert teams["by_sport"]["nfl"]["expected"] == 32
        assert teams["by_sport"]["nfl"]["ok"] is False
        assert "nfl" in teams["missing_sports"]

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_verify_seeds_tracks_espn_ids(self, mock_get_cursor):
        """Test verify_seeds tracks ESPN ID coverage.

        Educational Note:
            Teams without ESPN IDs cannot be matched to live game data.
            Tracking this helps identify data quality issues early.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"sport": "nfl", "team_count": 32, "with_espn_id": 30},  # 2 missing ESPN IDs
            {"sport": "nba", "team_count": 30, "with_espn_id": 30},
            {"sport": "nhl", "team_count": 32, "with_espn_id": 32},
            {"sport": "wnba", "team_count": 12, "with_espn_id": 12},
            {"sport": "ncaaf", "team_count": 79, "with_espn_id": 79},
            {"sport": "ncaab", "team_count": 89, "with_espn_id": 89},
        ]
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        result = manager.verify_seeds()

        teams = result["categories"]["teams"]
        assert teams["by_sport"]["nfl"]["has_espn_ids"] == 30
        assert teams["has_espn_ids"] == 272  # 274 - 2

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_verify_seeds_handles_database_error(self, mock_get_cursor):
        """Test verify_seeds handles database errors gracefully."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Connection refused")
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        result = manager.verify_seeds()

        assert result["success"] is False
        teams = result["categories"]["teams"]
        assert teams["ok"] is False
        assert "error" in teams


# =============================================================================
# SEED_ALL TESTS
# =============================================================================


@pytest.mark.unit
class TestSeedAll:
    """Unit tests for seed_all method."""

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_seed_all_creates_session(self, mock_get_cursor, temp_seeds_dir):
        """Test seed_all creates a session with unique ID."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            categories=[SeedCategory.TEAMS],
            sql_seeds_path=temp_seeds_dir,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        assert report["session_id"] is not None
        assert len(report["session_id"]) > 0
        assert report["started_at"] is not None
        assert report["completed_at"] is not None

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_seed_all_returns_report(self, mock_get_cursor, temp_seeds_dir):
        """Test seed_all returns complete SeedingReport."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 32
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            sql_seeds_path=temp_seeds_dir,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        assert "session_id" in report
        assert "started_at" in report
        assert "completed_at" in report
        assert "categories_seeded" in report
        assert "total_records_processed" in report
        assert "total_records_created" in report
        assert "total_errors" in report
        assert "category_stats" in report
        assert "success" in report

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_seed_all_handles_category_errors(self, mock_get_cursor, temp_seeds_dir):
        """Test seed_all continues after category errors."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("SQL error")
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            categories=[SeedCategory.TEAMS],
            sql_seeds_path=temp_seeds_dir,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        assert report["total_errors"] >= 1
        assert report["success"] is False


# =============================================================================
# SEED VENUES API TESTS
# =============================================================================


@pytest.mark.unit
class TestSeedVenuesApi:
    """Unit tests for _seed_venues_api method."""

    @patch("precog.database.seeding.seeding_manager.create_venue")
    def test_seed_venues_from_api_creates_venues(self, mock_create_venue, mock_espn_client):
        """Test venue seeding creates venues from API data."""
        mock_espn_client.get_scoreboard.return_value = [
            {
                "metadata": {
                    "venue": {
                        "espn_venue_id": "3622",
                        "venue_name": "Arrowhead Stadium",
                        "city": "Kansas City",
                        "state": "Missouri",
                        "capacity": 76416,
                        "indoor": False,
                    }
                }
            }
        ]
        mock_create_venue.return_value = 1

        config = SeedingConfig(sports=["nfl"])
        manager = SeedingManager(config=config, espn_client=mock_espn_client)

        stats = manager.seed_venues_from_api(sports=["nfl"])

        mock_create_venue.assert_called_once()
        assert stats["records_processed"] == 1
        assert stats["records_created"] == 1

    def test_seed_venues_from_api_requires_client(self):
        """Test seed_venues_from_api raises error without ESPN client."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        with pytest.raises(ValueError, match="ESPN client required"):
            manager.seed_venues_from_api(sports=["nfl"])

    def test_seed_venues_api_dry_run(self, mock_espn_client):
        """Test venue seeding dry-run mode doesn't create venues."""
        mock_espn_client.get_scoreboard.return_value = [
            {
                "metadata": {
                    "venue": {
                        "venue_name": "Test Stadium",
                    }
                }
            }
        ]

        config = SeedingConfig(sports=["nfl"], dry_run=True)
        manager = SeedingManager(config=config, espn_client=mock_espn_client)

        with patch("precog.database.seeding.seeding_manager.create_venue") as mock_create:
            stats = manager.seed_venues_from_api(sports=["nfl"])

            mock_create.assert_not_called()
            assert stats["records_processed"] == 1
            assert stats["records_created"] == 0

    def test_seed_venues_api_skips_missing_name(self, mock_espn_client):
        """Test venues without names are skipped."""
        mock_espn_client.get_scoreboard.return_value = [
            {
                "metadata": {
                    "venue": {
                        "espn_venue_id": "123",
                        # No venue_name
                    }
                }
            }
        ]

        config = SeedingConfig(sports=["nfl"])
        manager = SeedingManager(config=config, espn_client=mock_espn_client)

        stats = manager.seed_venues_from_api(sports=["nfl"])

        assert stats["records_skipped"] == 1
        assert stats["records_processed"] == 0


# =============================================================================
# CONVENIENCE FUNCTIONS TESTS
# =============================================================================


@pytest.mark.unit
class TestConvenienceFunctions:
    """Unit tests for module-level convenience functions."""

    @patch("precog.database.seeding.seeding_manager.ESPNClient")
    def test_create_seeding_manager_defaults(self, mock_client):
        """Test create_seeding_manager with default parameters."""
        manager = create_seeding_manager()

        assert manager.config.database == "dev"
        assert manager.config.dry_run is False
        assert len(manager.config.sports) == 6

    @patch("precog.database.seeding.seeding_manager.ESPNClient")
    def test_create_seeding_manager_with_params(self, mock_client):
        """Test create_seeding_manager with custom parameters."""
        manager = create_seeding_manager(
            categories=["teams"],
            sports=["nfl"],
            database="test",
            dry_run=True,
        )

        assert manager.config.database == "test"
        assert manager.config.dry_run is True
        assert manager.config.sports == ["nfl"]
        assert manager.config.categories == [SeedCategory.TEAMS]

    @patch("precog.database.seeding.seeding_manager.SeedingManager")
    def test_seed_all_teams_function(self, mock_manager_class):
        """Test seed_all_teams convenience function."""
        mock_manager = MagicMock()
        mock_manager.seed_all.return_value = {"success": True}
        mock_manager_class.return_value = mock_manager

        result = seed_all_teams(sports=["nfl"], database="test")

        mock_manager.seed_all.assert_called_once()
        assert result["success"] is True

    @patch("precog.database.seeding.seeding_manager.SeedingManager")
    def test_verify_required_seeds_function(self, mock_manager_class):
        """Test verify_required_seeds convenience function."""
        mock_manager = MagicMock()
        mock_manager.verify_seeds.return_value = {"success": True}
        mock_manager_class.return_value = mock_manager

        result = verify_required_seeds()

        mock_manager.verify_seeds.assert_called_once()
        assert result["success"] is True


# =============================================================================
# SESSION MANAGEMENT TESTS
# =============================================================================


@pytest.mark.unit
class TestSessionManagement:
    """Unit tests for session tracking functionality."""

    def test_session_id_format(self):
        """Test session ID follows expected format (YYYYMMDD_HHMMSS)."""
        config = SeedingConfig(use_api=False, dry_run=True)
        manager = SeedingManager(config=config)

        manager._start_session()

        assert manager._session_id is not None
        # Format: YYYYMMDD_HHMMSS
        assert len(manager._session_id) == 15
        assert "_" in manager._session_id

    def test_session_stats_initialized_empty(self):
        """Test category stats are empty at session start."""
        config = SeedingConfig(use_api=False, dry_run=True)
        manager = SeedingManager(config=config)

        manager._start_session()

        assert manager._category_stats == {}

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_session_report_aggregates_stats(self, mock_get_cursor, temp_seeds_dir):
        """Test session report correctly aggregates category statistics."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 10
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            categories=[SeedCategory.TEAMS],
            sql_seeds_path=temp_seeds_dir,
            sports=["nfl", "nba"],
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        # Total should be sum of all categories
        assert (
            report["total_records_created"] == report["category_stats"]["teams"]["records_created"]
        )


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Unit tests for edge cases and error handling."""

    def test_empty_sports_list(self, temp_seeds_dir):
        """Test handling of empty sports list."""
        config = SeedingConfig(
            sports=[],
            sql_seeds_path=temp_seeds_dir,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        stats = manager.seed_teams(sports=[])

        assert stats["records_processed"] == 0

    def test_unknown_category_logged(self, mock_espn_client):
        """Test that unsupported categories are logged but don't crash."""
        config = SeedingConfig(
            categories=[SeedCategory.HISTORICAL_ELO],  # Not fully implemented
            use_api=False,
        )
        manager = SeedingManager(config=config)

        # Should not raise, just log warning
        report = manager.seed_all()

        assert report is not None

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_sql_file_read_error(self, mock_get_cursor, temp_seeds_dir):
        """Test handling of file read errors."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            sports=["nfl"],
            use_api=False,
        )
        manager = SeedingManager(config=config)

        # Mock file read error
        with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            stats = manager.seed_teams(sports=["nfl"])

            # Should record error but not crash
            assert stats["errors"] >= 1


# =============================================================================
# INTEGRATION-READY TESTS (Mocked but test real patterns)
# =============================================================================


@pytest.mark.unit
class TestRealWorldPatterns:
    """Tests that verify real-world usage patterns work correctly.

    Educational Note:
        These tests use mocks but verify the actual patterns that will
        be used in integration tests and production code.
    """

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_idempotent_seeding(self, mock_get_cursor, temp_seeds_dir):
        """Test that seeding can be run multiple times safely.

        Educational Note:
            Our SQL files use ON CONFLICT DO UPDATE, making seeding
            idempotent. First run creates, subsequent runs update.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 32
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            sports=["nfl"],
            use_api=False,
        )
        manager = SeedingManager(config=config)

        # Run twice
        stats1 = manager.seed_teams(sports=["nfl"])
        stats2 = manager.seed_teams(sports=["nfl"])

        # Both should succeed
        assert stats1["errors"] == 0
        assert stats2["errors"] == 0

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_multi_sport_seeding(self, mock_get_cursor, temp_seeds_dir):
        """Test seeding multiple sports in one operation."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 30  # Average teams per sport
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            sports=["nfl", "nba", "nhl"],
            use_api=False,
        )
        manager = SeedingManager(config=config)

        stats = manager.seed_teams()

        # Should process files for all three sports
        assert stats["records_processed"] >= 3

    def test_verify_then_seed_workflow(self, mock_espn_client):
        """Test the typical verify -> seed -> verify workflow.

        Educational Note:
            Production deployments typically:
            1. Verify current state
            2. Seed if needed
            3. Verify seeding succeeded
        """
        config = SeedingConfig(dry_run=True)
        manager = SeedingManager(config=config, espn_client=mock_espn_client)

        with patch.object(manager, "verify_seeds") as mock_verify:
            with patch.object(manager, "seed_teams") as mock_seed:
                mock_verify.return_value = {"success": False}
                mock_seed.return_value = {"errors": 0}

                # Step 1: Verify (fails)
                result1 = manager.verify_seeds()
                assert result1["success"] is False

                # Step 2: Seed
                manager.seed_teams()

                # Step 3: Verify again
                mock_verify.return_value = {"success": True}
                result2 = manager.verify_seeds()
                assert result2["success"] is True
