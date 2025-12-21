"""
Historical Data Source Adapters.

This package contains source adapters for importing historical data
from various external sources (FiveThirtyEight, Kaggle, Python libraries).

Architecture:
    - base_source.py: Abstract DataSource interface with TypedDict records
    - fivethirtyeight.py: FiveThirtyEight Elo + game data
    - betting_csv.py: Betting/odds CSV files
    - nfl_data_py_source.py: NFL player/team stats via nfl_data_py library

Record Types:
    - GameRecord: Historical game results
    - EloRecord: Team Elo ratings
    - OddsRecord: Betting odds (spreads, totals, moneylines)
    - StatsRecord: Player/team statistics (Issue #236)
    - RankingRecord: Team rankings (Issue #236)

Related:
    - ADR-106: Historical Data Collection Architecture
    - ADR-103: BasePoller Unified Design Pattern (parallel for live data)
    - Issue #229: Expanded Historical Data Sources
    - Issue #236: StatsRecord/RankingRecord Infrastructure
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
    RankingRecord,
    StatsRecord,
)
from precog.database.seeding.sources.betting_csv import BettingCSVSource
from precog.database.seeding.sources.fivethirtyeight import FiveThirtyEightSource
from precog.database.seeding.sources.nfl_data_py_source import NFLDataPySource

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
    "NFLDataPySource",
    "OddsRecord",
    "RankingRecord",
    "StatsRecord",
]
