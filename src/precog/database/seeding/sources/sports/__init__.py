"""
Sport-Specific Python Library Data Source Adapters.

This package contains adapters for sport-specific Python libraries
that provide historical data through their APIs.

Available Adapters:
    - nfl_data_py: NFL play-by-play, schedules, rosters (nfl_data_py_adapter.py)
    - nba_api: NBA games, stats, player data (nba_api_adapter.py)
    - pybaseball: MLB stats, retrosheet data (pybaseball_adapter.py)
    - cfbd: College football data, rankings (cfbd_adapter.py)

Design Note:
    These adapters use the APIBasedSourceMixin since they fetch data
    from external APIs (unlike FileBasedSourceMixin for CSV sources).

Related:
    - ADR-106: Historical Data Collection Architecture
    - Issue #229: Expanded Historical Data Sources
"""

# Lazy imports to avoid importing unavailable libraries
__all__ = [
    "CFBDSource",
    "NBAApiSource",
    "NFLDataPySource",
    "PybaseballSource",
]


def __getattr__(name: str):
    """Lazy import adapters to handle optional dependencies."""
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
