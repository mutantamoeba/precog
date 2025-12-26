"""
Unified Cache Configuration Module.

Centralizes all cache path definitions for historical data sources.
Supports reproducibility, backtesting, and TimescaleDB migration.

Directory Structure:
    data/historical/
    ├── *.csv                    # FiveThirtyEight Elo data
    ├── espn/{sport}/           # ESPN game cache
    ├── kalshi/{type}/          # Kalshi API cache
    └── python_libs/            # External library documentation

Educational Note:
    This module provides a single source of truth for cache paths.
    All caching modules (ESPN, Kalshi, etc.) should import from here
    rather than defining paths inline. This enables:
    - Easy path changes during production migration
    - Consistent structure across all data sources
    - Centralized cache statistics aggregation

Related:
    - data/historical/README.md: Full documentation
    - kalshi_historical_cache.py: Kalshi-specific caching
    - historical_games_loader.py: ESPN-specific caching
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# =============================================================================
# Base Cache Directory
# =============================================================================

CACHE_BASE_DIR = Path("data/historical")


# =============================================================================
# FiveThirtyEight CSV Files
# =============================================================================

FIVETHIRTYEIGHT_DIR = CACHE_BASE_DIR
FIVETHIRTYEIGHT_FILES = {
    "nfl_elo": FIVETHIRTYEIGHT_DIR / "nfl_elo.csv",
    "nba_elo": FIVETHIRTYEIGHT_DIR / "nba_elo.csv",
    "mlb_elo": FIVETHIRTYEIGHT_DIR / "mlb_elo.csv",
    "mlb_elo_new": FIVETHIRTYEIGHT_DIR / "mlb_elo_new.csv",
    "nhl_elo_new": FIVETHIRTYEIGHT_DIR / "nhl_elo_new.csv",
    "nfl_betting": FIVETHIRTYEIGHT_DIR / "nfl_betting.csv",
}


# =============================================================================
# ESPN API Cache
# =============================================================================

ESPN_CACHE_DIR = CACHE_BASE_DIR / "espn"
ESPN_SPORTS = ["nfl", "nba", "mlb", "nhl", "cfb", "cbb"]


def get_espn_cache_dir(sport: str) -> Path:
    """Get ESPN cache directory for a sport.

    Args:
        sport: Sport code (nfl, nba, mlb, nhl, cfb, cbb)

    Returns:
        Path to sport-specific cache directory
    """
    return ESPN_CACHE_DIR / sport.lower()


# =============================================================================
# Kalshi API Cache
# =============================================================================

KALSHI_CACHE_DIR = CACHE_BASE_DIR / "kalshi"
KALSHI_CACHE_TYPES = ["markets", "series", "positions", "orders"]


def get_kalshi_cache_dir(cache_type: str) -> Path:
    """Get Kalshi cache directory for a data type.

    Args:
        cache_type: Data type (markets, series, positions, orders)

    Returns:
        Path to type-specific cache directory
    """
    return KALSHI_CACHE_DIR / cache_type.lower()


# =============================================================================
# Python Library External Caches
# =============================================================================

# These libraries manage their own caches - we document locations for reference
PYTHON_LIB_CACHES = {
    "pybaseball": {
        "description": "MLB statistics from Statcast, Baseball Reference, FanGraphs",
        "cache_location": "~/.pybaseball/cache",
        "data_coverage": "MLB stats since 2008 (Statcast since 2015)",
        "rate_limit": "None (data is cached locally)",
    },
    "nfl_data_py": {
        "description": "NFL play-by-play, roster, schedule data",
        "cache_location": "Auto-managed by library",
        "data_coverage": "NFL since 1999",
        "rate_limit": "None (nflverse GitHub data)",
    },
    "nflreadpy": {
        "description": "NFL advanced stats and next-gen metrics",
        "cache_location": "Auto-managed by library",
        "data_coverage": "NFL advanced stats since 2016",
        "rate_limit": "None (nflverse GitHub data)",
    },
    "nba_api": {
        "description": "Official NBA stats from stats.nba.com",
        "cache_location": "~/.nba_api/",
        "data_coverage": "NBA since 1946-47 season",
        "rate_limit": "~60 requests/minute (throttled by API)",
    },
}


# =============================================================================
# Unified Cache Statistics
# =============================================================================


def get_all_cache_stats() -> dict[str, Any]:
    """Get unified cache statistics across all sources.

    Returns:
        Dictionary with per-source statistics:
        - fivethirtyeight: {files_present: list, total_size_mb: float}
        - espn: {sports: dict, total_dates: int, total_size_mb: float}
        - kalshi: {types: dict, total_dates: int, total_size_mb: float}
        - python_libs: {info: dict} (external cache locations)

    Educational Note:
        This aggregates statistics from individual cache modules.
        Import the specific modules for detailed stats:
        - get_espn_cache_stats() from historical_games_loader
        - get_kalshi_cache_stats() from kalshi_historical_cache
    """
    stats: dict[str, Any] = {
        "fivethirtyeight": _get_fivethirtyeight_stats(),
        "espn": _get_espn_stats_summary(),
        "kalshi": _get_kalshi_stats_summary(),
        "python_libs": PYTHON_LIB_CACHES,
    }
    return stats


def _get_fivethirtyeight_stats() -> dict[str, Any]:
    """Get FiveThirtyEight file statistics."""
    files_present = []
    total_size = 0

    for name, path in FIVETHIRTYEIGHT_FILES.items():
        if path.exists():
            files_present.append(name)
            total_size += path.stat().st_size

    return {
        "files_present": files_present,
        "files_missing": [name for name in FIVETHIRTYEIGHT_FILES if name not in files_present],
        "total_size_mb": total_size / (1024 * 1024),
    }


def _get_espn_stats_summary() -> dict[str, Any]:
    """Get ESPN cache statistics summary."""
    if not ESPN_CACHE_DIR.exists():
        return {"sports": {}, "total_dates": 0, "total_size_mb": 0}

    sports_stats = {}
    total_dates = 0
    total_size = 0

    for sport_dir in ESPN_CACHE_DIR.iterdir():
        if sport_dir.is_dir():
            cache_files = list(sport_dir.glob("*.json"))
            size = sum(f.stat().st_size for f in cache_files)
            sports_stats[sport_dir.name] = {
                "cached_dates": len(cache_files),
                "size_mb": size / (1024 * 1024),
            }
            total_dates += len(cache_files)
            total_size += size

    return {
        "sports": sports_stats,
        "total_dates": total_dates,
        "total_size_mb": total_size / (1024 * 1024),
    }


def _get_kalshi_stats_summary() -> dict[str, Any]:
    """Get Kalshi cache statistics summary."""
    if not KALSHI_CACHE_DIR.exists():
        return {"types": {}, "total_dates": 0, "total_size_mb": 0}

    types_stats = {}
    total_dates = 0
    total_size = 0

    for type_dir in KALSHI_CACHE_DIR.iterdir():
        if type_dir.is_dir():
            cache_files = list(type_dir.glob("*.json"))
            size = sum(f.stat().st_size for f in cache_files)
            types_stats[type_dir.name] = {
                "cached_dates": len(cache_files),
                "size_mb": size / (1024 * 1024),
            }
            total_dates += len(cache_files)
            total_size += size

    return {
        "types": types_stats,
        "total_dates": total_dates,
        "total_size_mb": total_size / (1024 * 1024),
    }


# =============================================================================
# Cache Initialization
# =============================================================================


def ensure_cache_structure() -> None:
    """Create all cache directories if they don't exist.

    Call this during application initialization to ensure
    the full cache structure is ready for use.
    """
    # ESPN directories
    for sport in ESPN_SPORTS:
        (ESPN_CACHE_DIR / sport).mkdir(parents=True, exist_ok=True)

    # Kalshi directories
    for cache_type in KALSHI_CACHE_TYPES:
        (KALSHI_CACHE_DIR / cache_type).mkdir(parents=True, exist_ok=True)

    # Python libs documentation directory
    (CACHE_BASE_DIR / "python_libs").mkdir(parents=True, exist_ok=True)
