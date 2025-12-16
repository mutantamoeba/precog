"""
Base Data Source Abstract Class for Historical Data Seeding.

This module provides the abstract base class for all historical data source
adapters, implementing a consistent interface across diverse data sources.

Architecture Pattern:
    Mirrors the BasePoller pattern (ADR-103) for live data polling.
    - BasePoller: Live data collection with APScheduler
    - BaseDataSource: Historical data seeding with batch imports

    Both share:
    - Template Method pattern
    - Consistent statistics tracking
    - Error handling with recovery
    - Configurable behavior via subclass implementation

Data Source Categories:
    1. CSV Sources (file-based):
       - FiveThirtyEight (Elo ratings + game results)
       - Betting CSV files (odds, spreads, totals)

    2. Python Library Sources (API-based):
       - nfl_data_py: NFL play-by-play, schedules, rosters
       - nba_api: NBA stats, games, player data
       - pybaseball: MLB stats, retrosheet data
       - cfbd: College football data, rankings

Record Types:
    - GameRecord: Historical game results (scores, date, teams)
    - OddsRecord: Historical betting lines (spreads, totals, moneylines)
    - EloRecord: Historical Elo ratings (team ratings over time)

Related:
    - ADR-106: Historical Data Collection Architecture
    - ADR-103: BasePoller Unified Design Pattern
    - Issue #229: Expanded Historical Data Sources
    - Migration 0006: historical_games table
    - Migration 0007: historical_odds table
"""

from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import date
    from decimal import Decimal

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class DataSourceError(Exception):
    """Base exception for data source errors.

    Raised when a data source encounters an error during loading,
    such as file not found, invalid data format, or API failure.
    """


class DataSourceConfigError(DataSourceError):
    """Configuration error for data sources.

    Raised when a data source is misconfigured, such as missing
    required parameters or invalid file paths.
    """


class DataSourceConnectionError(DataSourceError):
    """Connection error for API-based data sources.

    Raised when a data source cannot connect to its external API,
    such as network issues or authentication failures.
    """


# =============================================================================
# Record Type Definitions
# =============================================================================


class GameRecord(TypedDict):
    """Historical game record for database insertion.

    Represents a single completed game with final scores.
    Maps to the historical_games table (migration 0006).

    Fields:
        sport: Sport code (nfl, nba, mlb, etc.)
        season: Season year (e.g., 2023 for 2023-24 season)
        game_date: Date the game was played
        home_team_code: Home team abbreviation (e.g., "KC")
        away_team_code: Away team abbreviation (e.g., "LV")
        home_score: Home team final score (None if game not completed)
        away_score: Away team final score (None if game not completed)
        is_neutral_site: True for neutral site games (bowl games, etc.)
        is_playoff: True for playoff/postseason games
        game_type: Game type (regular, playoff, bowl, etc.)
        venue_name: Stadium/arena name (optional)
        source: Data source identifier (e.g., "fivethirtyeight")
        source_file: Source file name (for CSV sources)
        external_game_id: External ID from source system (optional)
    """

    sport: str
    season: int
    game_date: date
    home_team_code: str
    away_team_code: str
    home_score: int | None
    away_score: int | None
    is_neutral_site: bool
    is_playoff: bool
    game_type: str | None
    venue_name: str | None
    source: str
    source_file: str | None
    external_game_id: str | None


class OddsRecord(TypedDict):
    """Historical odds record for database insertion.

    Represents betting lines for a single game.
    Maps to the historical_odds table (migration 0007).

    Fields:
        sport: Sport code (nfl, nba, mlb, etc.)
        game_date: Date the game was played
        home_team_code: Home team abbreviation
        away_team_code: Away team abbreviation
        sportsbook: Sportsbook source (consensus, pinnacle, etc.)
        spread_home_open: Opening spread for home team (e.g., -3.5)
        spread_home_close: Closing spread for home team
        spread_home_odds_open: Opening odds for spread (e.g., -110)
        spread_home_odds_close: Closing odds for spread
        moneyline_home_open: Opening moneyline for home team
        moneyline_home_close: Closing moneyline for home team
        moneyline_away_open: Opening moneyline for away team
        moneyline_away_close: Closing moneyline for away team
        total_open: Opening total (over/under)
        total_close: Closing total
        over_odds_open: Opening odds for over
        over_odds_close: Closing odds for over
        home_covered: Did home team cover the spread? (result)
        game_went_over: Did total go over? (result)
        source: Data source identifier
        source_file: Source file name
    """

    sport: str
    game_date: date
    home_team_code: str
    away_team_code: str
    sportsbook: str | None
    spread_home_open: Decimal | None
    spread_home_close: Decimal | None
    spread_home_odds_open: int | None
    spread_home_odds_close: int | None
    moneyline_home_open: int | None
    moneyline_home_close: int | None
    moneyline_away_open: int | None
    moneyline_away_close: int | None
    total_open: Decimal | None
    total_close: Decimal | None
    over_odds_open: int | None
    over_odds_close: int | None
    home_covered: bool | None
    game_went_over: bool | None
    source: str
    source_file: str | None


class EloRecord(TypedDict):
    """Historical Elo rating record for database insertion.

    Represents a team's Elo rating at a point in time.
    Maps to the historical_elo table (existing, used by historical_elo_loader).

    Fields:
        sport: Sport code (nfl, nba, mlb, etc.)
        team_code: Team abbreviation (e.g., "KC")
        rating_date: Date of the rating
        elo_rating: Elo rating value (typically 1300-1700)
        season: Season year
        source: Data source identifier
        source_file: Source file name
    """

    sport: str
    team_code: str
    rating_date: date
    elo_rating: Decimal
    season: int
    source: str
    source_file: str | None


# =============================================================================
# Load Result Tracking
# =============================================================================


@dataclass
class LoadResult:
    """Result statistics from loading historical data.

    Mirrors the PollerStats pattern from BasePoller (ADR-103)
    but adapted for batch import operations.

    Attributes:
        records_processed: Total records read from source
        records_inserted: Records successfully inserted
        records_updated: Records updated (upsert matched existing)
        records_skipped: Records skipped (validation failure, etc.)
        errors: Count of errors encountered
        error_messages: List of error descriptions

    Example:
        >>> result = source.load_games(seasons=[2023])
        >>> print(f"Loaded {result.records_inserted} of {result.records_processed}")
        Loaded 272 of 285
    """

    records_processed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)

    def __add__(self, other: LoadResult) -> LoadResult:
        """Combine two LoadResults (for aggregating across sources)."""
        return LoadResult(
            records_processed=self.records_processed + other.records_processed,
            records_inserted=self.records_inserted + other.records_inserted,
            records_updated=self.records_updated + other.records_updated,
            records_skipped=self.records_skipped + other.records_skipped,
            errors=self.errors + other.errors,
            error_messages=self.error_messages + other.error_messages,
        )


# =============================================================================
# Abstract Base Class
# =============================================================================


class BaseDataSource(ABC):  # noqa: B024 - Template method pattern, subclasses override specific methods
    """Abstract base class for historical data sources.

    Provides a consistent interface for loading historical data from
    various sources (CSV files, Python libraries, APIs).

    Subclass Implementation:
        Each subclass must implement at least one of:
        - load_games(): For game result data
        - load_odds(): For betting line data
        - load_elo(): For Elo rating data

        Not all sources provide all data types. The base implementation
        raises NotImplementedError for unsupported methods.

    Design Pattern:
        Template Method pattern - subclasses implement specific loading
        logic while base class handles common operations like logging,
        error handling, and result aggregation.

    Example:
        >>> class FiveThirtyEightSource(BaseDataSource):
        ...     def load_games(self, **kwargs) -> Iterator[GameRecord]:
        ...         # Parse CSV and yield GameRecord objects
        ...         pass
        ...
        ...     def load_elo(self, **kwargs) -> Iterator[EloRecord]:
        ...         # Parse CSV and yield EloRecord objects
        ...         pass

    Related:
        - ADR-106: Historical Data Collection Architecture
        - ADR-103: BasePoller (parallel pattern for live data)
        - BasePoller in src/precog/schedulers/base_poller.py
    """

    # Subclass should override these
    source_name: str = "unknown"
    supported_sports: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the data source.

        Args:
            **kwargs: Source-specific configuration options
        """
        self._config = kwargs
        self._logger = logging.getLogger(f"{__name__}.{self.source_name}")

    @property
    def name(self) -> str:
        """Return the source name for logging and identification."""
        return self.source_name

    def supports_sport(self, sport: str) -> bool:
        """Check if this source supports the given sport.

        Args:
            sport: Sport code (e.g., "nfl", "nba")

        Returns:
            True if sport is supported, False otherwise
        """
        return sport.lower() in [s.lower() for s in self.supported_sports]

    # -------------------------------------------------------------------------
    # Data Loading Methods (override in subclasses)
    # -------------------------------------------------------------------------

    def load_games(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        **kwargs: Any,
    ) -> Iterator[GameRecord]:
        """Load historical game records from this source.

        Args:
            sport: Sport code to load
            seasons: Filter to specific seasons (None = all available)
            **kwargs: Source-specific options

        Yields:
            GameRecord for each game

        Raises:
            NotImplementedError: If source doesn't support game data
            DataSourceError: If loading fails
        """
        raise NotImplementedError(f"{self.source_name} does not support game data loading")

    def load_odds(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        **kwargs: Any,
    ) -> Iterator[OddsRecord]:
        """Load historical odds records from this source.

        Args:
            sport: Sport code to load
            seasons: Filter to specific seasons (None = all available)
            **kwargs: Source-specific options

        Yields:
            OddsRecord for each game's odds

        Raises:
            NotImplementedError: If source doesn't support odds data
            DataSourceError: If loading fails
        """
        raise NotImplementedError(f"{self.source_name} does not support odds data loading")

    def load_elo(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        **kwargs: Any,
    ) -> Iterator[EloRecord]:
        """Load historical Elo rating records from this source.

        Args:
            sport: Sport code to load
            seasons: Filter to specific seasons (None = all available)
            **kwargs: Source-specific options

        Yields:
            EloRecord for each team's rating at each date

        Raises:
            NotImplementedError: If source doesn't support Elo data
            DataSourceError: If loading fails
        """
        raise NotImplementedError(f"{self.source_name} does not support Elo data loading")

    # -------------------------------------------------------------------------
    # Capability Discovery
    # -------------------------------------------------------------------------

    def supports_games(self) -> bool:
        """Check if this source can load game data."""
        try:
            # Try to call load_games - if NotImplementedError, not supported
            iter(self.load_games())
            return True
        except NotImplementedError:
            return False
        except Exception:
            # Other errors mean it's supported but failed
            return True

    def supports_odds(self) -> bool:
        """Check if this source can load odds data."""
        try:
            iter(self.load_odds())
            return True
        except NotImplementedError:
            return False
        except Exception:
            return True

    def supports_elo(self) -> bool:
        """Check if this source can load Elo data."""
        try:
            iter(self.load_elo())
            return True
        except NotImplementedError:
            return False
        except Exception:
            return True

    def get_capabilities(self) -> dict[str, bool]:
        """Return dictionary of this source's capabilities.

        Returns:
            Dict with keys 'games', 'odds', 'elo' and boolean values
        """
        return {
            "games": self.supports_games(),
            "odds": self.supports_odds(),
            "elo": self.supports_elo(),
        }

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_sport(self, sport: str) -> None:
        """Validate that sport is supported by this source.

        Args:
            sport: Sport code to validate

        Raises:
            DataSourceConfigError: If sport not supported
        """
        if not self.supports_sport(sport):
            raise DataSourceConfigError(
                f"Sport '{sport}' not supported by {self.source_name}. "
                f"Supported: {', '.join(self.supported_sports)}"
            )

    def _validate_file_path(self, file_path: Path) -> None:
        """Validate that file exists and is readable.

        Args:
            file_path: Path to validate

        Raises:
            DataSourceConfigError: If file doesn't exist
        """
        if not file_path.exists():
            raise DataSourceConfigError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise DataSourceConfigError(f"Path is not a file: {file_path}")


# =============================================================================
# File-Based Source Mixin
# =============================================================================


class FileBasedSourceMixin:
    """Mixin for data sources that read from local files.

    Provides common functionality for CSV and other file-based sources:
    - File path management
    - File existence validation
    - Source file tracking for provenance

    Usage:
        class FiveThirtyEightSource(FileBasedSourceMixin, BaseDataSource):
            def __init__(self, data_dir: Path):
                super().__init__(data_dir=data_dir)
    """

    def __init__(self, data_dir: Path | None = None, **kwargs: Any) -> None:
        """Initialize file-based source.

        Args:
            data_dir: Directory containing data files
            **kwargs: Additional configuration
        """
        self._data_dir = data_dir or Path("data/historical")
        super().__init__(**kwargs)

    @property
    def data_dir(self) -> Path:
        """Return the data directory path."""
        return self._data_dir

    def get_file_path(self, filename: str) -> Path:
        """Get full path to a data file.

        Args:
            filename: Name of file in data directory

        Returns:
            Full Path to the file
        """
        return self._data_dir / filename


# =============================================================================
# API-Based Source Mixin
# =============================================================================


class APIBasedSourceMixin:
    """Mixin for data sources that fetch from external APIs.

    Provides common functionality for Python library sources:
    - Rate limiting awareness
    - Connection error handling
    - Retry logic

    Usage:
        class NFLDataPySource(APIBasedSourceMixin, BaseDataSource):
            def __init__(self):
                super().__init__(rate_limit=60)  # 60 requests/minute
    """

    def __init__(self, rate_limit: int = 60, **kwargs: Any) -> None:
        """Initialize API-based source.

        Args:
            rate_limit: Maximum requests per minute
            **kwargs: Additional configuration
        """
        self._rate_limit = rate_limit
        super().__init__(**kwargs)

    @property
    def rate_limit(self) -> int:
        """Return the rate limit (requests per minute)."""
        return self._rate_limit
