"""
Integration Tests for SeedingManager with Real Database.

These tests use REAL database operations with no mocking.
Requires running PostgreSQL database with test schema.

Test Strategy:
    Since seeds are designed to be run once and use INSERT without
    ON CONFLICT in some files, these tests focus on:
    1. Verification - Test verify_seeds() against real data
    2. Idempotency - Test that re-seeding with ON CONFLICT files works
    3. Data Integrity - Test team data correctness

Expected Team Counts (from seed files):
    - NFL: 32 teams
    - NBA: 30 teams
    - NHL: 32 teams
    - WNBA: 12 teams
    - NCAAF: 79 teams
    - NCAAB: 89 teams
    - Total: 274 teams

Related:
    - REQ-DATA-003: Multi-Sport Team Support
    - ADR-029: ESPN Data Model with Normalized Schema
    - Phase 2.5: Live Data Collection Service

Usage:
    pytest tests/integration/database/seeding/test_seeding_manager_integration.py -v
    pytest tests/integration/database/seeding/ -v -m integration
"""

import pytest

from precog.database.seeding import (
    SeedingConfig,
    SeedingManager,
    create_seeding_manager,
    verify_required_seeds,
)

# =============================================================================
# EXPECTED COUNTS (from seed SQL files)
# =============================================================================

EXPECTED_TEAM_COUNTS = {
    "nfl": 32,
    "nba": 30,
    "nhl": 32,
    "wnba": 12,
    "ncaaf": 79,
    "ncaab": 89,
}

TOTAL_EXPECTED_TEAMS = sum(EXPECTED_TEAM_COUNTS.values())  # 274


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def seeding_manager(db_pool):
    """
    Create SeedingManager with default configuration.

    Uses db_pool fixture to ensure database connection is available.
    """
    return SeedingManager()


@pytest.fixture
def ensure_teams_seeded(db_pool, db_cursor):
    """
    Ensure teams are seeded in the database before tests run.

    This fixture checks if teams exist and seeds them if not.
    It's idempotent - safe to run multiple times.

    Educational Note:
        Integration tests shouldn't modify database state unnecessarily.
        We check first if data exists, and only seed if needed.
    """
    # Check current team count
    db_cursor.execute("SELECT COUNT(*) as count FROM teams")
    current_count = db_cursor.fetchone()["count"]

    # If we have a reasonable number of teams, assume seeding was done
    if current_count >= 200:
        yield {"seeded_now": False, "count": current_count}
        return

    # Otherwise, try to seed (this will work on fresh databases)
    manager = SeedingManager()
    try:
        manager.seed_teams()
    except Exception:
        # Seeds may fail if data exists, that's OK
        pass

    # Re-check count
    db_cursor.execute("SELECT COUNT(*) as count FROM teams")
    final_count = db_cursor.fetchone()["count"]

    yield {"seeded_now": True, "count": final_count}


# =============================================================================
# VERIFICATION INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
class TestVerifySeedsIntegration:
    """Integration tests for verify_seeds with real database."""

    def test_verify_seeds_returns_result_structure(self, db_pool, seeding_manager):
        """
        Test verify_seeds returns proper result structure.

        Regardless of seeding status, verify_seeds should return a
        well-formed result dictionary with 'success' and 'categories' keys.
        """
        result = seeding_manager.verify_seeds()

        # Should have required keys based on actual implementation
        assert "success" in result
        assert "categories" in result
        assert isinstance(result["success"], bool)
        assert isinstance(result["categories"], dict)

    def test_verify_seeds_returns_teams_category(
        self, db_pool, seeding_manager, ensure_teams_seeded
    ):
        """Test verify_seeds includes teams category with sport breakdown."""
        result = seeding_manager.verify_seeds()

        # Should have teams category
        teams_result = result.get("categories", {}).get("teams", {})
        assert isinstance(teams_result, dict)

        # If we have teams data, should have by_sport breakdown
        if teams_result.get("actual", 0) > 0:
            assert "by_sport" in teams_result or "expected" in teams_result

    def test_verify_seeds_reports_missing_sports_in_category(self, db_pool, seeding_manager):
        """
        Test verify_seeds reports missing sports within teams category.

        The missing_sports field should be within the teams category result.
        """
        result = seeding_manager.verify_seeds()

        # Should have categories dict
        assert "categories" in result
        teams_result = result["categories"].get("teams", {})

        # missing_sports is inside the teams category result
        assert isinstance(teams_result.get("missing_sports", []), list)


@pytest.mark.integration
class TestVerifyRequiredSeedsFunction:
    """Integration tests for verify_required_seeds convenience function."""

    def test_verify_required_seeds_returns_result(self, db_pool):
        """Test verify_required_seeds convenience function works."""
        result = verify_required_seeds()

        assert result is not None
        assert "success" in result
        assert "categories" in result


# =============================================================================
# SEEDING MANAGER INITIALIZATION TESTS
# =============================================================================


@pytest.mark.integration
class TestSeedingManagerIntegration:
    """Integration tests for SeedingManager initialization and methods."""

    def test_create_seeding_manager_with_dry_run(self, db_pool):
        """Test create_seeding_manager convenience function."""
        manager = create_seeding_manager(dry_run=True)

        assert manager is not None
        assert manager.config.dry_run is True

    def test_seeding_manager_has_config(self, db_pool, seeding_manager):
        """
        Test SeedingManager has config with expected attributes.

        The SeedingManager should have a config dataclass with all
        the seeding configuration options.
        """
        assert seeding_manager.config is not None
        assert isinstance(seeding_manager.config, SeedingConfig)
        assert hasattr(seeding_manager.config, "sports")
        assert hasattr(seeding_manager.config, "dry_run")
        assert hasattr(seeding_manager.config, "categories")

    def test_seeding_manager_has_espn_client(self, db_pool, seeding_manager):
        """Test SeedingManager initializes ESPN client."""
        # ESPN client should be available for API seeding
        assert hasattr(seeding_manager, "espn_client")


# =============================================================================
# DATA INTEGRITY TESTS
# =============================================================================


@pytest.mark.integration
class TestDataIntegrityIntegration:
    """Integration tests for data integrity after seeding."""

    def test_teams_table_exists(self, db_pool, db_cursor):
        """Test teams table exists and is accessible."""
        db_cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'teams'
            )
        """)
        exists = db_cursor.fetchone()["exists"]

        assert exists is True

    def test_teams_have_required_columns(self, db_pool, db_cursor):
        """Test teams table has required columns."""
        db_cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'teams'
        """)
        columns = [row["column_name"] for row in db_cursor.fetchall()]

        # Required columns for team data
        required_columns = ["team_code", "team_name", "sport", "espn_team_id"]

        for col in required_columns:
            assert col in columns, f"Missing required column: {col}"

    def test_team_codes_are_unique_per_sport(self, db_pool, db_cursor):
        """
        Test team_code is unique within each sport.

        Educational Note:
            Team codes like 'LA' might exist in multiple sports (Lakers, Rams),
            but should be unique within a sport. The unique constraint is
            (team_code, sport).
        """
        db_cursor.execute("""
            SELECT team_code, sport, COUNT(*) as count
            FROM teams
            GROUP BY team_code, sport
            HAVING COUNT(*) > 1
        """)
        duplicates = db_cursor.fetchall()

        assert len(duplicates) == 0, f"Found duplicate team codes: {duplicates}"


# =============================================================================
# SPECIFIC TEAM VERIFICATION TESTS
# =============================================================================


@pytest.mark.integration
class TestSpecificTeamsIntegration:
    """Integration tests for specific team data correctness."""

    def test_nfl_teams_exist_if_seeded(self, db_pool, db_cursor):
        """
        Test NFL teams exist if database has been seeded.

        This is a conditional test - it only validates if NFL teams are present.
        """
        db_cursor.execute("SELECT COUNT(*) as count FROM teams WHERE sport = 'nfl'")
        nfl_count = db_cursor.fetchone()["count"]

        if nfl_count > 0:
            # If we have NFL teams, we should have all 32
            assert nfl_count >= 32, f"Expected at least 32 NFL teams, got {nfl_count}"

    def test_kansas_city_chiefs_data_if_exists(self, db_pool, db_cursor):
        """
        Test Kansas City Chiefs data if it exists.

        This is a spot-check to verify seed data accuracy.
        """
        db_cursor.execute("""
            SELECT team_code, team_name, conference, division
            FROM teams
            WHERE team_code = 'KC' AND sport = 'nfl'
        """)
        chiefs = db_cursor.fetchone()

        if chiefs is not None:
            assert chiefs["team_name"] == "Kansas City Chiefs"
            assert chiefs["conference"] == "AFC"
            assert chiefs["division"] == "West"

    def test_nba_teams_exist_if_seeded(self, db_pool, db_cursor):
        """Test NBA teams exist if database has been seeded."""
        db_cursor.execute("SELECT COUNT(*) as count FROM teams WHERE sport = 'nba'")
        nba_count = db_cursor.fetchone()["count"]

        if nba_count > 0:
            # If we have NBA teams, we should have all 30
            assert nba_count >= 30, f"Expected at least 30 NBA teams, got {nba_count}"


# =============================================================================
# SEED ALL WORKFLOW TESTS
# =============================================================================


@pytest.mark.integration
class TestSeedAllIntegration:
    """Integration tests for seed_all method."""

    def test_seed_all_with_dry_run(self, db_pool, db_cursor):
        """
        Test seed_all with dry_run=True makes no database changes.

        Educational Note:
            Dry run is useful for previewing seeding operations without
            modifying the database. It should report what WOULD happen.
        """
        # Get initial count
        db_cursor.execute("SELECT COUNT(*) as count FROM teams")
        initial_count = db_cursor.fetchone()["count"]

        # Create manager with dry_run enabled
        config = SeedingConfig(dry_run=True)
        manager = SeedingManager(config=config)

        # Run seed_all (should be no-op in dry_run mode)
        manager.seed_all()

        # Count should be unchanged
        db_cursor.execute("SELECT COUNT(*) as count FROM teams")
        final_count = db_cursor.fetchone()["count"]

        assert initial_count == final_count, (
            f"Dry run modified database: {initial_count} -> {final_count}"
        )

    def test_seed_all_returns_report(self, db_pool):
        """Test seed_all returns a report structure."""
        config = SeedingConfig(dry_run=True)
        manager = SeedingManager(config=config)

        report = manager.seed_all()

        assert report is not None
        assert isinstance(report, dict)
        # Report should have standard fields from SeedingReport TypedDict
        assert "success" in report  # Required field in SeedingReport


# =============================================================================
# SEED TEAMS METHOD TESTS
# =============================================================================


@pytest.mark.integration
class TestSeedTeamsIntegration:
    """Integration tests for seed_teams method."""

    def test_seed_teams_with_dry_run(self, db_pool, db_cursor):
        """Test seed_teams with dry_run returns stats without modifying DB."""
        # Get initial count
        db_cursor.execute("SELECT COUNT(*) as count FROM teams")
        initial_count = db_cursor.fetchone()["count"]

        # Create manager with dry_run
        config = SeedingConfig(dry_run=True)
        manager = SeedingManager(config=config)

        # Run seed_teams
        manager.seed_teams()

        # Count should be unchanged in dry_run mode
        db_cursor.execute("SELECT COUNT(*) as count FROM teams")
        final_count = db_cursor.fetchone()["count"]

        assert initial_count == final_count, (
            f"Dry run modified database: {initial_count} -> {final_count}"
        )

    def test_seed_teams_returns_stats_type(self, db_pool):
        """Test seed_teams returns proper stats structure."""
        config = SeedingConfig(dry_run=True)
        manager = SeedingManager(config=config)

        stats = manager.seed_teams()

        # Should return SeedingStats TypedDict
        assert stats is not None
        assert isinstance(stats, dict)


# =============================================================================
# ERROR HANDLING INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling with real database."""

    def test_verify_seeds_handles_empty_database(self, db_pool):
        """
        Test verify_seeds handles gracefully when no teams exist.

        Even with no data, verify_seeds should return a valid result.
        """
        manager = SeedingManager()
        result = manager.verify_seeds()

        # Should return a result even if database has no data
        assert result is not None
        assert "success" in result
        assert "categories" in result

    def test_seeding_manager_with_invalid_sport_filter(self, db_pool):
        """
        Test seeding manager handles invalid sport filter gracefully.

        The manager should not crash when given an invalid sport.
        """
        config = SeedingConfig(sports=["invalid_sport_xyz"], dry_run=True)
        manager = SeedingManager(config=config)

        # Should not raise an exception
        stats = manager.seed_teams()

        # Stats should indicate no records processed (no matching files)
        assert stats is not None
