"""
Database Seeding Package.

Provides comprehensive seeding functionality for initializing and updating
static reference data in the database.

Key Components:
    - SeedingManager: Main class for orchestrating seeding operations
    - SeedCategory: Enum of data categories (teams, venues, Elo, etc.)
    - SeedingConfig: Configuration dataclass for customizing seeding
    - Historical Elo Loader: CSV loading for FiveThirtyEight and other sources
    - Historical Odds Loader: Betting odds from CSV and other sources
    - Source Adapters: Unified data source interfaces (FiveThirtyEight, betting CSV, Python libraries)

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
    >>>
    >>> # Load historical odds from source adapters
    >>> from precog.database.seeding import load_odds_from_source
    >>> from precog.database.seeding.sources import BettingCSVSource
    >>> source = BettingCSVSource(data_dir=Path("data/historical"))
    >>> result = load_odds_from_source(source, sport="nfl", seasons=[2023])

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-029 (ESPN Data Model), ADR-106 (Historical Data Collection), REQ-DATA-003-008
GitHub Issue: #208 (Historical Data Seeding), #229 (Expanded Historical Data Sources)
"""

from precog.database.seeding.historical_elo_loader import (
    HistoricalEloRecord,
    LoadResult,
    get_historical_elo_stats,
    load_csv_elo,
    load_fivethirtyeight_elo,
)
from precog.database.seeding.historical_odds_loader import (
    LoadResult as OddsLoadResult,
)
from precog.database.seeding.historical_odds_loader import (
    bulk_insert_historical_odds,
    get_historical_odds_stats,
    link_orphan_odds_to_games,
    load_odds_from_source,
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
    "OddsLoadResult",
    "SeedCategory",
    "SeedingConfig",
    "SeedingManager",
    "SeedingReport",
    "SeedingStats",
    "bulk_insert_historical_odds",
    "create_seeding_manager",
    "get_historical_elo_stats",
    "get_historical_odds_stats",
    "link_orphan_odds_to_games",
    "load_csv_elo",
    "load_fivethirtyeight_elo",
    "load_odds_from_source",
    "seed_all_teams",
    "verify_required_seeds",
]
