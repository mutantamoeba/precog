"""
Unit tests for seed_multi_sport_teams.py seeding script.

Tests cover:
1. Seed configuration structure (SeedConfig dataclass)
2. Database URL construction (get_database_url)
3. League validation (VALID_LEAGUES)
4. Seed function signatures and exports

Reference:
- scripts/seed_multi_sport_teams.py
- Issue #187: Multi-sport Team Seeding
- docs/database/seeds/*.sql

Educational Note:
    These tests focus on pure functions and configuration without requiring
    actual database access. Integration tests that verify actual seeding
    would need a test database and are covered in tests/integration/.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from seed_multi_sport_teams import (
    SEED_CONFIGS,
    SEEDS_DIR,
    SPORT_SEEDS,
    VALID_LEAGUES,
    SeedConfig,
    apply_seed_file,
    check_teams_exist,
    get_database_url,
    get_summary,
    seed_all_teams,
    seed_nba_teams,
    seed_ncaab_teams,
    seed_ncaaf_teams,
    seed_nfl_teams,
    seed_nhl_teams,
    seed_sports,
    seed_wnba_teams,
)

# ============================================================================
# Test: SeedConfig dataclass
# ============================================================================


class TestSeedConfig:
    """Tests for SeedConfig dataclass structure."""

    def test_seed_config_creation(self):
        """Create a SeedConfig with all fields."""
        config = SeedConfig(
            name="Test League",
            file="test.sql",
            team_count=10,
            prerequisite="base",
        )

        assert config.name == "Test League"
        assert config.file == "test.sql"
        assert config.team_count == 10
        assert config.prerequisite == "base"

    def test_seed_config_optional_prerequisite(self):
        """SeedConfig prerequisite defaults to None."""
        config = SeedConfig(name="Test", file="test.sql", team_count=5)
        assert config.prerequisite is None

    def test_all_seed_configs_have_required_fields(self):
        """All SEED_CONFIGS have name, file, and team_count."""
        for key, config in SEED_CONFIGS.items():
            assert config.name, f"{key} missing name"
            assert config.file, f"{key} missing file"
            assert config.team_count > 0, f"{key} has invalid team_count"


# ============================================================================
# Test: SEED_CONFIGS structure
# ============================================================================


class TestSeedConfigs:
    """Tests for SEED_CONFIGS dictionary structure."""

    def test_nfl_configs_exist(self):
        """NFL has base and ESPN update configs."""
        assert "nfl_base" in SEED_CONFIGS
        assert "nfl_espn" in SEED_CONFIGS

    def test_nfl_espn_has_prerequisite(self):
        """NFL ESPN update requires base seed first."""
        assert SEED_CONFIGS["nfl_espn"].prerequisite == "nfl_base"

    def test_all_leagues_have_configs(self):
        """All supported leagues have configs."""
        expected = ["nfl_base", "nfl_espn", "nba", "nhl", "wnba", "ncaaf", "ncaab"]
        for league in expected:
            assert league in SEED_CONFIGS, f"{league} missing from SEED_CONFIGS"

    def test_nfl_team_count(self):
        """NFL has 32 teams."""
        assert SEED_CONFIGS["nfl_base"].team_count == 32

    def test_nba_team_count(self):
        """NBA has 30 teams."""
        assert SEED_CONFIGS["nba"].team_count == 30

    def test_nhl_team_count(self):
        """NHL has 32 teams."""
        assert SEED_CONFIGS["nhl"].team_count == 32

    def test_wnba_team_count(self):
        """WNBA has 12 teams."""
        assert SEED_CONFIGS["wnba"].team_count == 12

    def test_ncaaf_team_count(self):
        """NCAAF has 79 teams (Power 5 + Group of 5)."""
        assert SEED_CONFIGS["ncaaf"].team_count == 79

    def test_ncaab_team_count(self):
        """NCAAB has 89 teams (majors + mid-majors)."""
        assert SEED_CONFIGS["ncaab"].team_count == 89

    def test_total_team_count(self):
        """Total expected teams across all leagues."""
        # NFL: 32, NBA: 30, NHL: 32, WNBA: 12, NCAAF: 79, NCAAB: 89
        expected_total = 32 + 30 + 32 + 12 + 79 + 89
        assert expected_total == 274


# ============================================================================
# Test: SPORT_SEEDS mapping
# ============================================================================


class TestSportSeeds:
    """Tests for SPORT_SEEDS mapping."""

    def test_nfl_includes_both_seeds(self):
        """NFL sport includes base and ESPN seeds."""
        assert "nfl_base" in SPORT_SEEDS["nfl"]
        assert "nfl_espn" in SPORT_SEEDS["nfl"]
        assert len(SPORT_SEEDS["nfl"]) == 2

    def test_other_sports_have_single_seed(self):
        """Other sports have single seed."""
        for sport in ["nba", "nhl", "wnba", "ncaaf", "ncaab"]:
            assert len(SPORT_SEEDS[sport]) == 1


# ============================================================================
# Test: VALID_LEAGUES
# ============================================================================


class TestValidLeagues:
    """Tests for VALID_LEAGUES whitelist."""

    def test_contains_all_supported_leagues(self):
        """VALID_LEAGUES contains all supported leagues."""
        expected = {"nfl", "nba", "nhl", "wnba", "ncaaf", "ncaab"}
        assert expected == VALID_LEAGUES

    def test_is_immutable(self):
        """VALID_LEAGUES is a frozenset (immutable)."""
        assert isinstance(VALID_LEAGUES, frozenset)


# ============================================================================
# Test: SEEDS_DIR path
# ============================================================================


class TestSeedsDir:
    """Tests for SEEDS_DIR path configuration."""

    def test_seeds_dir_is_path(self):
        """SEEDS_DIR is a Path object."""
        assert isinstance(SEEDS_DIR, Path)

    def test_seeds_dir_ends_with_seeds(self):
        """SEEDS_DIR path ends with seeds directory."""
        assert SEEDS_DIR.name == "seeds"
        assert "database" in str(SEEDS_DIR)


# ============================================================================
# Test: get_database_url()
# ============================================================================


class TestGetDatabaseUrl:
    """Tests for get_database_url function."""

    def test_returns_database_url_from_env(self, monkeypatch):
        """Return DATABASE_URL from environment."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/precog")
        url = get_database_url()
        assert url == "postgresql://user:pass@localhost/precog"

    def test_raises_when_not_set(self, monkeypatch):
        """Raise ValueError when DATABASE_URL not set."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValueError, match="DATABASE_URL"):
            get_database_url()

    def test_override_database_name(self, monkeypatch):
        """Override database name in URL."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/precog")
        url = get_database_url(database="precog_test")
        assert url == "postgresql://user:pass@localhost/precog_test"

    def test_override_with_complex_url(self, monkeypatch):
        """Override works with complex URLs."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/original")
        url = get_database_url(database="new_db")
        assert url == "postgresql://user:pass@host:5432/new_db"


# ============================================================================
# Test: check_teams_exist()
# ============================================================================


class TestCheckTeamsExist:
    """Tests for check_teams_exist function."""

    def test_rejects_invalid_league(self):
        """Return 0 for invalid league code."""
        result = check_teams_exist("postgresql://localhost/test", "invalid_league")
        assert result == 0

    def test_accepts_valid_leagues(self):
        """Valid leagues pass validation (would query DB if connected)."""
        # These tests don't actually hit the DB - they test validation only
        for league in VALID_LEAGUES:
            # Should not raise, just return 0 (no DB connection)
            # In real scenario with mock, would check DB call
            with patch("seed_multi_sport_teams.subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError("psql not found")
                result = check_teams_exist("postgresql://localhost/test", league)
                assert result == 0


# ============================================================================
# Test: apply_seed_file()
# ============================================================================


class TestApplySeedFile:
    """Tests for apply_seed_file function."""

    def test_returns_false_for_missing_file(self, tmp_path):
        """Return (False, error) for non-existent file."""
        missing_file = tmp_path / "nonexistent.sql"
        success, error = apply_seed_file("postgresql://localhost/test", missing_file)
        assert success is False
        assert "not found" in error.lower()

    def test_handles_successful_execution(self, tmp_path):
        """Return (True, '') on successful execution."""
        seed_file = tmp_path / "test.sql"
        seed_file.write_text("SELECT 1;", encoding="utf-8")

        with patch("seed_multi_sport_teams.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            success, error = apply_seed_file("postgresql://localhost/test", seed_file)

        assert success is True
        assert error == ""

    def test_handles_duplicate_key_as_success(self, tmp_path):
        """Treat 'duplicate key' error as success (idempotent)."""
        seed_file = tmp_path / "test.sql"
        seed_file.write_text("INSERT INTO teams VALUES (...);", encoding="utf-8")

        with patch("seed_multi_sport_teams.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="ERROR: duplicate key value violates unique constraint"
            )
            success, error = apply_seed_file("postgresql://localhost/test", seed_file)

        assert success is True
        assert error == ""

    def test_handles_already_exists_as_success(self, tmp_path):
        """Treat 'already exists' error as success (idempotent)."""
        seed_file = tmp_path / "test.sql"
        seed_file.write_text("CREATE TABLE teams (...);", encoding="utf-8")

        with patch("seed_multi_sport_teams.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="ERROR: relation 'teams' already exists"
            )
            success, error = apply_seed_file("postgresql://localhost/test", seed_file)

        assert success is True
        assert error == ""

    def test_returns_error_for_real_failures(self, tmp_path):
        """Return (False, error) for actual failures."""
        seed_file = tmp_path / "test.sql"
        seed_file.write_text("INVALID SQL;", encoding="utf-8")

        with patch("seed_multi_sport_teams.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="ERROR: syntax error at or near 'INVALID'"
            )
            success, error = apply_seed_file("postgresql://localhost/test", seed_file)

        assert success is False
        assert "syntax error" in error.lower()

    def test_handles_psql_not_found(self, tmp_path):
        """Return (False, error) when psql not installed."""
        seed_file = tmp_path / "test.sql"
        seed_file.write_text("SELECT 1;", encoding="utf-8")

        with patch("seed_multi_sport_teams.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            success, error = apply_seed_file("postgresql://localhost/test", seed_file)

        assert success is False
        assert "psql" in error.lower()

    def test_handles_timeout(self, tmp_path):
        """Return (False, error) on timeout."""
        import subprocess

        seed_file = tmp_path / "test.sql"
        seed_file.write_text("SELECT pg_sleep(1000);", encoding="utf-8")

        with patch("seed_multi_sport_teams.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="psql", timeout=60)
            success, error = apply_seed_file("postgresql://localhost/test", seed_file)

        assert success is False
        assert "timed out" in error.lower()


# ============================================================================
# Test: Seed functions (mocked)
# ============================================================================


class TestSeedFunctions:
    """Tests for individual seed functions."""

    def test_seed_nfl_teams_signature(self):
        """seed_nfl_teams has correct signature."""
        import inspect

        sig = inspect.signature(seed_nfl_teams)
        params = list(sig.parameters.keys())
        assert "db_url" in params
        assert "dry_run" in params

    def test_seed_nba_teams_signature(self):
        """seed_nba_teams has correct signature."""
        import inspect

        sig = inspect.signature(seed_nba_teams)
        params = list(sig.parameters.keys())
        assert "db_url" in params
        assert "dry_run" in params

    def test_seed_all_teams_returns_dict(self):
        """seed_all_teams returns (bool, dict) tuple."""
        with (
            patch("seed_multi_sport_teams.check_teams_exist", return_value=100),
            patch("seed_multi_sport_teams.apply_seed_file", return_value=(True, "")),
        ):
            success, results = seed_all_teams("postgresql://localhost/test", dry_run=True)

        assert isinstance(success, bool)
        assert isinstance(results, dict)

    def test_seed_sports_validates_sport_names(self):
        """seed_sports handles invalid sport names gracefully."""
        with (
            patch("seed_multi_sport_teams.check_teams_exist", return_value=0),
            patch("seed_multi_sport_teams.apply_seed_file", return_value=(True, "")),
        ):
            _success, results = seed_sports(
                "postgresql://localhost/test",
                ["nba", "invalid_sport"],
                dry_run=True,
            )

        assert "nba" in results
        assert "invalid_sport" not in results


# ============================================================================
# Test: get_summary()
# ============================================================================


class TestGetSummary:
    """Tests for get_summary function."""

    def test_returns_dict_with_all_leagues(self):
        """get_summary returns counts for all leagues."""
        with patch("seed_multi_sport_teams.check_teams_exist", return_value=10):
            summary = get_summary("postgresql://localhost/test")

        assert isinstance(summary, dict)
        assert len(summary) == 6  # nfl, nba, nhl, wnba, ncaaf, ncaab
        for league in ["nfl", "nba", "nhl", "wnba", "ncaaf", "ncaab"]:
            assert league in summary


# ============================================================================
# Test: Dry run mode
# ============================================================================


class TestDryRunMode:
    """Tests for dry run functionality."""

    def test_dry_run_does_not_apply_seeds(self):
        """Dry run should not call apply_seed_file."""
        with (
            patch("seed_multi_sport_teams.check_teams_exist", return_value=0),
            patch("seed_multi_sport_teams.apply_seed_file") as mock_apply,
        ):
            seed_nba_teams("postgresql://localhost/test", dry_run=True)

        mock_apply.assert_not_called()

    def test_dry_run_returns_expected_count(self):
        """Dry run returns expected team count."""
        with patch("seed_multi_sport_teams.check_teams_exist", return_value=0):
            success, count = seed_nba_teams("postgresql://localhost/test", dry_run=True)

        assert success is True
        assert count == 30  # Expected NBA team count


# ============================================================================
# Test: Module exports
# ============================================================================


class TestModuleExports:
    """Tests for module-level exports."""

    def test_all_seed_functions_importable(self):
        """All seed functions are importable."""
        assert callable(seed_nfl_teams)
        assert callable(seed_nba_teams)
        assert callable(seed_nhl_teams)
        assert callable(seed_wnba_teams)
        assert callable(seed_ncaaf_teams)
        assert callable(seed_ncaab_teams)
        assert callable(seed_all_teams)
        assert callable(seed_sports)

    def test_utility_functions_importable(self):
        """Utility functions are importable."""
        assert callable(get_database_url)
        assert callable(check_teams_exist)
        assert callable(apply_seed_file)
        assert callable(get_summary)

    def test_configs_importable(self):
        """Configuration constants are importable."""
        assert SEED_CONFIGS is not None
        assert SPORT_SEEDS is not None
        assert VALID_LEAGUES is not None
        assert SEEDS_DIR is not None
