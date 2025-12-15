"""
Database Seeding Package.

Provides comprehensive seeding functionality for initializing and updating
static reference data in the database.

Key Components:
    - SeedingManager: Main class for orchestrating seeding operations
    - SeedCategory: Enum of data categories (teams, venues, Elo, etc.)
    - SeedingConfig: Configuration dataclass for customizing seeding
    - Historical Elo Loader: CSV loading for FiveThirtyEight and other sources

Usage:
    >>> from precog.database.seeding import SeedingManager, SeedCategory
    >>>
    >>> # Seed all data
    >>> manager = SeedingManager()
    >>> report = manager.seed_all()
    >>>
    >>> # Seed specific category
    >>> manager.seed_teams(sports=["nfl", "nba"])
    >>>
    >>> # Verify seeds exist
    >>> result = manager.verify_seeds()
    >>>
    >>> # Load historical Elo from CSV
    >>> from precog.database.seeding import load_fivethirtyeight_elo
    >>> result = load_fivethirtyeight_elo(Path("nfl_elo.csv"), seasons=[2023])

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Team Support)
GitHub Issue: #208 (Historical Data Seeding)
"""

from precog.database.seeding.historical_elo_loader import (
    HistoricalEloRecord,
    LoadResult,
    get_historical_elo_stats,
    load_csv_elo,
    load_fivethirtyeight_elo,
)
from precog.database.seeding.seeding_manager import (
    SeedCategory,
    SeedingConfig,
    SeedingManager,
    SeedingReport,
    SeedingStats,
    create_seeding_manager,
    seed_all_teams,
    verify_required_seeds,
)

__all__ = [
    "HistoricalEloRecord",
    "LoadResult",
    "SeedCategory",
    "SeedingConfig",
    "SeedingManager",
    "SeedingReport",
    "SeedingStats",
    "create_seeding_manager",
    "get_historical_elo_stats",
    "load_csv_elo",
    "load_fivethirtyeight_elo",
    "seed_all_teams",
    "verify_required_seeds",
]
