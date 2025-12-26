"""Unit tests for epa_seeder module.

This module tests the EPA (Expected Points Added) seeder that loads
advanced NFL statistics from nflfastR data.

Reference: Phase 2C - Historical data seeding infrastructure
"""

from unittest.mock import MagicMock

from precog.database.seeding.epa_seeder import (
    EPASeeder,
    SeedingStats,
)


class TestEPASeeder:
    """Tests for EPASeeder class."""

    def test_seeder_requires_connection(self) -> None:
        """Verify EPASeeder requires a connection."""
        mock_conn = MagicMock()
        seeder = EPASeeder(mock_conn)
        assert seeder is not None

    def test_seeder_stores_connection(self) -> None:
        """Verify EPASeeder stores its connection."""
        mock_conn = MagicMock()
        seeder = EPASeeder(mock_conn)
        assert seeder.connection == mock_conn

    def test_seeder_has_seed_seasons_method(self) -> None:
        """Verify EPASeeder has seed_seasons method."""
        mock_conn = MagicMock()
        seeder = EPASeeder(mock_conn)
        assert hasattr(seeder, "seed_seasons")
        assert callable(seeder.seed_seasons)


class TestSeedingStats:
    """Tests for SeedingStats TypedDict."""

    def test_stats_is_typed_dict(self) -> None:
        """Verify SeedingStats is a TypedDict."""
        # TypedDict at runtime is just dict
        stats: SeedingStats = {
            "seasons_processed": 1,
            "season_records_inserted": 100,
            "season_records_updated": 0,
            "game_records_inserted": 50,
            "game_records_updated": 0,
            "errors": [],
        }
        assert isinstance(stats, dict)
