"""
Sport-Specific Python Library Data Source Adapters.

This package contains adapters for sport-specific Python libraries
that provide historical data through their APIs.

Available Adapters:
    - nflreadpy: NFL schedules, play-by-play, EPA (nflreadpy_adapter.py) [RECOMMENDED]
    - nfl_data_py: NFL play-by-play, schedules, rosters (nfl_data_py_adapter.py) [DEPRECATED]
    - nba_api: NBA games, stats, player data (nba_api_adapter.py)
    - nhl_api: NHL games, stats, standings (nhl_api_adapter.py)
    - pybaseball: MLB stats, retrosheet data (pybaseball_adapter.py)
    - cfbd: College football data, rankings (cfbd_adapter.py)

Migration Note:
    nfl_data_py was archived September 2025. Use NFLReadPySource for new code.
    NFLReadPySource provides EPA metrics support via load_epa().

Design Note:
    These adapters use the APIBasedSourceMixin since they fetch data
    from external APIs (unlike FileBasedSourceMixin for CSV sources).

Related:
    - ADR-106: Historical Data Collection Architecture
    - ADR-109: Elo Rating Computation Engine
    - Issue #229: Expanded Historical Data Sources
    - Issue #273: Elo computation with EPA integration
"""

# Lazy imports to avoid importing unavailable libraries
__all__ = [
    "CFBDSource",
    "NBAApiSource",
    "NFLDataPySource",  # Deprecated, use NFLReadPySource
    "NFLReadPySource",  # Recommended for new code
    "NHLApiSource",
    "PybaseballSource",
]


def __getattr__(name: str):
    """Lazy import adapters to handle optional dependencies."""
    if name == "NFLReadPySource":
        from precog.database.seeding.sources.sports.nflreadpy_adapter import (
            NFLReadPySource,
        )

        return NFLReadPySource
    if name == "NFLDataPySource":
        from precog.database.seeding.sources.sports.nfl_data_py_adapter import (
            NFLDataPySource,
        )

        return NFLDataPySource
    if name == "NBAApiSource":
        from precog.database.seeding.sources.sports.nba_api_adapter import (
            NBAApiSource,
        )

        return NBAApiSource
    if name == "NHLApiSource":
        from precog.database.seeding.sources.sports.nhl_api_adapter import (
            NHLApiSource,
        )

        return NHLApiSource
    if name == "PybaseballSource":
        from precog.database.seeding.sources.sports.pybaseball_adapter import (
            PybaseballSource,
        )

        return PybaseballSource
    if name == "CFBDSource":
        from precog.database.seeding.sources.sports.cfbd_adapter import (
            CFBDSource,
        )

        return CFBDSource
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
