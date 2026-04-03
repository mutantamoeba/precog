"""
Historical Odds Data Loader - BACKWARD COMPATIBILITY SHIM.

This module re-exports all symbols from game_odds_loader.py.
The historical_odds table was renamed to game_odds in migration 0048.

New code should import from precog.database.seeding.game_odds_loader directly.

Reference:
    - Issue #533: ESPN DraftKings odds extraction
    - Migration 0048: Rename historical_odds -> game_odds
"""

from precog.database.seeding.game_odds_loader import (
    SOURCE_NAME_MAPPING,
    LoadResult,
    bulk_insert_game_odds,
    get_game_odds_stats,
    insert_game_odds,
    link_orphan_odds_to_games,
    load_odds_from_source,
    lookup_game_id,
    normalize_source_name,
)
from precog.database.seeding.game_odds_loader import (
    bulk_insert_game_odds as bulk_insert_historical_odds,
)
from precog.database.seeding.game_odds_loader import (
    get_game_odds_stats as get_historical_odds_stats,
)
from precog.database.seeding.game_odds_loader import (
    insert_game_odds as insert_historical_odds,
)

__all__ = [
    "SOURCE_NAME_MAPPING",
    "LoadResult",
    "bulk_insert_game_odds",
    "bulk_insert_historical_odds",
    "get_game_odds_stats",
    "get_historical_odds_stats",
    "insert_game_odds",
    "insert_historical_odds",
    "link_orphan_odds_to_games",
    "load_odds_from_source",
    "lookup_game_id",
    "normalize_source_name",
]
