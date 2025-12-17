"""
Chaos Tests for Seeding Manager.

Tests edge cases, malformed inputs, and unusual scenarios.

Reference: TESTING_STRATEGY V3.2 - Chaos tests for edge cases
Related Requirements: REQ-DATA-003, ADR-029

Usage:
    pytest tests/chaos/database/seeding/test_seeding_manager_chaos.py -v -m chaos
"""

import tempfile
from collections.abc import Iterator
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
def temp_seeds_dir() -> Iterator[Path]:
    """Create a temporary directory with mock SQL seed files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        seeds_path = Path(tmpdir)

        sql_file = seeds_path / "001_nfl_teams.sql"
        sql_file.write_text(
            "-- NFL Teams\nINSERT INTO teams (team_code, sport) VALUES ('KC', 'nfl');"
        )

        yield seeds_path


# =============================================================================
# Chaos Tests: Configuration Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestConfigurationEdgeCases:
    """Chaos tests for configuration edge cases."""

    def test_empty_sports_list(self) -> None:
        """Test config with empty sports list."""
        config = SeedingConfig(sports=[], use_api=False)
        assert config.sports == []

        manager = SeedingManager(config=config)
        report = manager.seed_all()
        # Should handle gracefully
        assert report["success"] is True

    def test_empty_categories_list(self) -> None:
        """Test config with empty categories list."""
        config = SeedingConfig(categories=[], use_api=False)
        assert config.categories == []

        manager = SeedingManager(config=config)
        report = manager.seed_all()
        # Should complete with empty stats
        assert report["category_stats"] == {}

    def test_empty_seasons_list(self) -> None:
        """Test config with empty seasons list."""
        config = SeedingConfig(seasons=[], use_api=False)
        assert config.seasons == []

    def test_duplicate_sports(self) -> None:
        """Test config with duplicate sports."""
        config = SeedingConfig(
            sports=["nfl", "nfl", "nba", "nba", "nba"],
            use_api=False,
        )
        # Should accept duplicates (validation elsewhere if needed)
        assert len(config.sports) == 5

    def test_duplicate_categories(self) -> None:
        """Test config with duplicate categories."""
        config = SeedingConfig(
            categories=[SeedCategory.TEAMS, SeedCategory.TEAMS],
            use_api=False,
        )
        assert len(config.categories) == 2

    def test_very_long_sports_list(self) -> None:
        """Test config with very long sports list."""
        sports = ["nfl"] * 1000
        config = SeedingConfig(sports=sports, use_api=False)
        assert len(config.sports) == 1000

    def test_very_long_seasons_list(self) -> None:
        """Test config with very long seasons list."""
        seasons = list(range(1900, 2100))
        config = SeedingConfig(seasons=seasons, use_api=False)
        assert len(config.seasons) == 200

    def test_negative_seasons(self) -> None:
        """Test config with negative season years."""
        config = SeedingConfig(seasons=[-1, 0, 2024], use_api=False)
        assert -1 in config.seasons
        assert 0 in config.seasons

    def test_future_seasons(self) -> None:
        """Test config with far future season years."""
        config = SeedingConfig(seasons=[3000, 9999], use_api=False)
        assert 3000 in config.seasons
        assert 9999 in config.seasons


# =============================================================================
# Chaos Tests: Seeds Path Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestSeedsPathEdgeCases:
    """Chaos tests for seeds path edge cases."""

    def test_nonexistent_path(self) -> None:
        """Test with nonexistent seeds path."""
        config = SeedingConfig(
            sql_seeds_path=Path("/nonexistent/path/to/seeds"),
            categories=[SeedCategory.TEAMS],
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        # Should handle gracefully
        report = manager.seed_all()
        assert report is not None

    def test_empty_directory(self) -> None:
        """Test with empty seeds directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SeedingConfig(
                sql_seeds_path=Path(tmpdir),
                categories=[SeedCategory.TEAMS],
                sports=["nfl"],
                dry_run=True,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()
            assert report["success"] is True

    def test_path_with_special_characters(self) -> None:
        """Test path with special characters in name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create subdir with special chars (where filesystem allows)
            special_dir = Path(tmpdir) / "seeds_test-123"
            special_dir.mkdir()

            config = SeedingConfig(
                sql_seeds_path=special_dir,
                categories=[SeedCategory.TEAMS],
                dry_run=True,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()
            assert report is not None


# =============================================================================
# Chaos Tests: SQL File Content Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestSQLFileContentEdgeCases:
    """Chaos tests for SQL file content edge cases."""

    def test_empty_sql_file(self) -> None:
        """Test handling of empty SQL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seeds_path = Path(tmpdir)
            sql_file = seeds_path / "001_empty.sql"
            sql_file.write_text("")

            config = SeedingConfig(
                sql_seeds_path=seeds_path,
                categories=[SeedCategory.TEAMS],
                dry_run=True,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()
            assert report is not None

    def test_sql_file_with_only_comments(self) -> None:
        """Test SQL file with only comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seeds_path = Path(tmpdir)
            sql_file = seeds_path / "001_comments.sql"
            sql_file.write_text("-- This is a comment\n-- Another comment\n/* Block comment */\n")

            config = SeedingConfig(
                sql_seeds_path=seeds_path,
                categories=[SeedCategory.TEAMS],
                dry_run=True,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()
            assert report is not None

    def test_sql_file_with_unicode(self) -> None:
        """Test SQL file with unicode characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seeds_path = Path(tmpdir)
            sql_file = seeds_path / "001_unicode.sql"
            sql_file.write_text(
                "-- Unicode test: こんにちは 🏈\nINSERT INTO teams (name) VALUES ('München');\n",
                encoding="utf-8",
            )

            config = SeedingConfig(
                sql_seeds_path=seeds_path,
                categories=[SeedCategory.TEAMS],
                dry_run=True,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()
            assert report is not None

    def test_very_large_sql_file(self) -> None:
        """Test handling of very large SQL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seeds_path = Path(tmpdir)
            sql_file = seeds_path / "001_large.sql"

            # Create large file
            content = "-- Large file\n" + "INSERT INTO teams (x) VALUES (1);\n" * 10000
            sql_file.write_text(content)

            config = SeedingConfig(
                sql_seeds_path=seeds_path,
                categories=[SeedCategory.TEAMS],
                dry_run=True,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()
            assert report is not None


# =============================================================================
# Chaos Tests: Database Error Scenarios
# =============================================================================


@pytest.mark.chaos
class TestDatabaseErrorScenarios:
    """Chaos tests for database error scenarios."""

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_database_connection_error(
        self, mock_get_cursor: MagicMock, temp_seeds_dir: Path
    ) -> None:
        """Test handling of database connection error."""
        mock_get_cursor.side_effect = ConnectionError("Database unavailable")

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            dry_run=False,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        # Should handle error gracefully
        report = manager.seed_all()
        assert report is not None

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_cursor_execute_timeout(self, mock_get_cursor: MagicMock, temp_seeds_dir: Path) -> None:
        """Test handling of cursor execute timeout."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = TimeoutError("Query timeout")
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            dry_run=False,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()
        assert report is not None

    @patch("precog.database.seeding.seeding_manager.get_cursor")
    def test_integrity_error(self, mock_get_cursor: MagicMock, temp_seeds_dir: Path) -> None:
        """Test handling of integrity constraint violation."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("UNIQUE constraint failed")
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            dry_run=False,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()
        assert report is not None


# =============================================================================
# Chaos Tests: Session State Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestSessionStateEdgeCases:
    """Chaos tests for session state edge cases."""

    def test_multiple_session_starts(self) -> None:
        """Test calling _start_session multiple times.

        Note: Session IDs use YYYYMMDD_HHMMSS format, so rapid calls
        within the same second will have the same ID.
        """
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        # Start multiple sessions
        manager._start_session()
        first_id = manager._session_id

        manager._start_session()
        second_id = manager._session_id

        # Both IDs should be valid format
        assert first_id is not None
        assert second_id is not None
        assert len(first_id) == 15
        assert len(second_id) == 15

    def test_complete_session_without_start(self) -> None:
        """Test completing session without starting."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        # Should handle gracefully
        manager._complete_session()

    def test_record_error_without_session(self) -> None:
        """Test recording error without active session."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        # Should handle gracefully (may error or no-op)
        try:
            manager._record_error(SeedCategory.TEAMS, "Test error")
        except (KeyError, AttributeError):
            pass  # Expected - no session active

    def test_access_stats_without_session(self) -> None:
        """Test accessing stats without active session."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        # Should be empty
        assert manager._category_stats == {}


# =============================================================================
# Chaos Tests: Category Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestCategoryEdgeCases:
    """Chaos tests for category edge cases."""

    def test_all_categories_single_sport(self, temp_seeds_dir: Path) -> None:
        """Test all categories with single sport.

        Note: Only teams and venues are currently implemented.
        Other categories log warnings but don't appear in stats.
        """
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=list(SeedCategory),
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        # Only implemented categories should be in stats
        assert len(report["category_stats"]) >= 1  # At least teams
        assert report["success"] is True

    def test_unsupported_sport_category_combination(self, temp_seeds_dir: Path) -> None:
        """Test category-sport combination that may not be supported."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAM_RANKINGS],
            sports=["wnba"],  # May have limited support
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()
        assert report is not None


# =============================================================================
# Chaos Tests: Report Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestReportEdgeCases:
    """Chaos tests for report edge cases."""

    def test_report_with_zero_records(self) -> None:
        """Test report when no records processed."""
        config = SeedingConfig(
            categories=[],  # No categories = no records
            sports=["nfl"],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        assert report["total_records_processed"] == 0
        assert report["total_records_created"] == 0
        assert report["success"] is True

    def test_report_with_all_errors(self) -> None:
        """Test report when all operations have errors."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        manager._start_session()
        manager._category_stats[SeedCategory.TEAMS.value] = manager._init_stats(SeedCategory.TEAMS)

        # Record many errors
        for i in range(100):
            manager._record_error(SeedCategory.TEAMS, f"Error {i}")

        # Stats should reflect errors
        assert manager._category_stats[SeedCategory.TEAMS.value]["errors"] == 100


# =============================================================================
# Chaos Tests: Concurrent Chaos
# =============================================================================


@pytest.mark.chaos
class TestConcurrentChaos:
    """Chaos tests for concurrent edge cases."""

    def test_rapid_manager_creation_destruction(self) -> None:
        """Test rapid creation and destruction of managers."""
        import gc

        for _ in range(100):
            config = SeedingConfig(use_api=False)
            manager = SeedingManager(config=config)
            manager._start_session()
            del manager

        gc.collect()
        # Should not leak memory or cause issues

    def test_manager_reuse_after_seeding(self, temp_seeds_dir: Path) -> None:
        """Test reusing manager after seeding completes."""
        config = SeedingConfig(
            sql_seeds_path=temp_seeds_dir,
            categories=[SeedCategory.TEAMS],
            dry_run=True,
            use_api=False,
        )
        manager = SeedingManager(config=config)

        # Run multiple times
        for _ in range(5):
            report = manager.seed_all()
            assert report["success"] is True


# =============================================================================
# Chaos Tests: Input Validation
# =============================================================================


@pytest.mark.chaos
class TestInputValidation:
    """Chaos tests for input validation."""

    def test_unusual_database_names(self) -> None:
        """Test unusual database environment names."""
        unusual_names = [
            "",
            " ",
            "test-db",
            "test_db_123",
            "UPPERCASE",
            "a" * 1000,
        ]

        for name in unusual_names:
            config = SeedingConfig(database=name, use_api=False)
            assert config.database == name

    def test_boolean_variations(self) -> None:
        """Test boolean field variations."""
        # Test with explicit True/False
        config1 = SeedingConfig(dry_run=True, use_api=True, overwrite=True)
        assert config1.dry_run is True
        assert config1.use_api is True
        assert config1.overwrite is True

        config2 = SeedingConfig(dry_run=False, use_api=False, overwrite=False)
        assert config2.dry_run is False
        assert config2.use_api is False
        assert config2.overwrite is False

    def test_none_values_where_unexpected(self) -> None:
        """Test None values in fields that might expect them."""
        # sql_seeds_path can be None - testing edge case intentionally
        config = SeedingConfig(sql_seeds_path=None, use_api=False)  # type: ignore[arg-type]
        assert config.sql_seeds_path is None


# =============================================================================
# Chaos Tests: File System Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestFileSystemEdgeCases:
    """Chaos tests for file system edge cases."""

    def test_many_small_sql_files(self) -> None:
        """Test directory with many small SQL files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seeds_path = Path(tmpdir)

            # Create many small files
            for i in range(100):
                sql_file = seeds_path / f"{i:03d}_test.sql"
                sql_file.write_text(f"-- File {i}\nSELECT 1;")

            config = SeedingConfig(
                sql_seeds_path=seeds_path,
                categories=[SeedCategory.TEAMS],
                dry_run=True,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()
            assert report is not None

    def test_nested_directory_structure(self) -> None:
        """Test nested directory structure in seeds path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seeds_path = Path(tmpdir)

            # Create nested structure
            nested = seeds_path / "level1" / "level2" / "level3"
            nested.mkdir(parents=True)

            sql_file = nested / "deep_file.sql"
            sql_file.write_text("SELECT 1;")

            config = SeedingConfig(
                sql_seeds_path=seeds_path,
                categories=[SeedCategory.TEAMS],
                dry_run=True,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()
            assert report is not None

    def test_mixed_file_types(self) -> None:
        """Test directory with mixed file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seeds_path = Path(tmpdir)

            # Create various file types
            (seeds_path / "readme.txt").write_text("Not SQL")
            (seeds_path / "data.json").write_text('{"key": "value"}')
            (seeds_path / "script.py").write_text("print('hello')")
            (seeds_path / "001_actual.sql").write_text("SELECT 1;")

            config = SeedingConfig(
                sql_seeds_path=seeds_path,
                categories=[SeedCategory.TEAMS],
                dry_run=True,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            # Should only process .sql files
            report = manager.seed_all()
            assert report is not None
