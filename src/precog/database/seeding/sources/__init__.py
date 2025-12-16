"""
Historical Data Source Adapters.

This package contains source adapters for importing historical data
from various external sources (FiveThirtyEight, Kaggle, Python libraries).

Architecture:
    - base_source.py: Abstract DataSource interface
    - fivethirtyeight.py: FiveThirtyEight Elo + game data
    - betting_csv.py: Betting/odds CSV files
    - sports/: Sport-specific Python library adapters

Related:
    - ADR-106: Historical Data Collection Architecture
    - ADR-103: BasePoller Unified Design Pattern (parallel for live data)
    - Issue #229: Expanded Historical Data Sources
"""

from precog.database.seeding.sources.base_source import (
    BaseDataSource,
    DataSourceConfigError,
    DataSourceConnectionError,
    DataSourceError,
    EloRecord,
    GameRecord,
    LoadResult,
    OddsRecord,
)
from precog.database.seeding.sources.betting_csv import BettingCSVSource
from precog.database.seeding.sources.fivethirtyeight import FiveThirtyEightSource

__all__ = [
    "BaseDataSource",
    "BettingCSVSource",
    "DataSourceConfigError",
    "DataSourceConnectionError",
    "DataSourceError",
    "EloRecord",
    "FiveThirtyEightSource",
    "GameRecord",
    "LoadResult",
    "OddsRecord",
]
