"""
ESPN API client for live game data.

This module provides a high-level interface to ESPN's public API for fetching
real-time NFL and NCAAF game data. No authentication required - ESPN's
scoreboard API is publicly accessible.

Key Features:
- NFL and NCAAF scoreboard fetching
- Game state parsing (scores, period, clock, possession)
- Rate limiting (500 requests/hour to be a good API citizen)
- Automatic retries with exponential backoff
- Comprehensive error handling
- TypedDict return types for type safety

Educational Notes:
------------------
ESPN API Design:
    ESPN provides public REST APIs for sports data. The scoreboard endpoint
    returns all games for a given date with detailed status information.

    Key concepts:
    - "events" = games
    - "competitions" = the matchup within an event
    - "competitors" = the two teams (home/away)
    - "status.type.state" = "pre", "in", or "post"

Rate Limiting Strategy:
    Unlike authenticated APIs, ESPN doesn't enforce strict rate limits.
    However, we implement 500 req/hour as a courtesy to:
    1. Avoid overwhelming their servers
    2. Prevent IP-based blocking
    3. Follow good API citizenship practices

Reference: docs/testing/PHASE_2_TEST_PLAN_V1.0.md
Related Requirements:
    - Phase 2: Live Data Integration
    - ESPN API Client deliverable
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, ClassVar, TypedDict

import requests

# Set up logging
logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================


class ESPNAPIError(Exception):
    """Base exception for ESPN API errors.

    Educational Note:
        Custom exceptions make error handling cleaner and more specific.
        Instead of catching generic Exception, callers can handle
        ESPNAPIError specifically for API-related issues.
    """


class RateLimitExceededError(ESPNAPIError):
    """Raised when rate limit is exceeded.

    Educational Note:
        Separate exception type allows callers to handle rate limiting
        differently (e.g., wait and retry vs. fail immediately).
    """


# Alias for backwards compatibility
RateLimitExceeded = RateLimitExceededError


# =============================================================================
# TypedDict Response Types - Normalized ESPN Data Model
# =============================================================================
# Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
# Related ADR: ADR-XXX (ESPN Data Model: Normalized Schema)
#
# Design Philosophy:
#   - Separate static metadata (teams, venue) from dynamic state (scores, clock)
#   - JSONB-ready situation data for sport-specific fields
#   - Clear ownership: ESPNTeamInfo describes a team, ESPNVenueInfo a venue
#   - Backward compatibility via GameState alias


class ESPNTeamInfo(TypedDict, total=False):
    """Static team information from ESPN API.

    Educational Note:
        This TypedDict captures team identity and performance context.
        Separate from game state because team info doesn't change during a game.

    Fields:
        espn_team_id: ESPN's internal team identifier
        team_code: Short abbreviation (e.g., "KC", "BUF")
        team_name: Full team name (e.g., "Kansas City Chiefs")
        display_name: Short display name (e.g., "Chiefs")
        record: Overall season record (e.g., "10-1")
        home_record: Record at home games (e.g., "5-0")
        away_record: Record in away games (e.g., "5-1")
        rank: AP/CFP ranking (college only, None for NFL)

    Reference: Phase 2 ESPN Data Model Plan
    """

    espn_team_id: str
    team_code: str
    team_name: str
    display_name: str
    record: str
    home_record: str
    away_record: str
    rank: int | None


class ESPNVenueInfo(TypedDict, total=False):
    """Venue/stadium information from ESPN API.

    Educational Note:
        Venue data is extracted separately for normalization.
        This allows us to build a venues table with unique stadium records.

    Fields:
        espn_venue_id: ESPN's internal venue identifier (may not always be present)
        venue_name: Full stadium name (e.g., "Highmark Stadium")
        city: City where venue is located
        state: State/province
        capacity: Seating capacity
        indoor: True if dome/indoor stadium

    Reference: Phase 2 ESPN Data Model Plan
    """

    espn_venue_id: str
    venue_name: str
    city: str
    state: str
    capacity: int
    indoor: bool


class ESPNGameMetadata(TypedDict, total=False):
    """Static game information that doesn't change during the game.

    Educational Note:
        Metadata is set when game is scheduled and rarely changes.
        Separating it from state allows efficient storage:
        - Metadata stored once per game
        - State stored every update (SCD Type 2)

    Fields:
        espn_event_id: Unique ESPN identifier for the game
        game_date: ISO 8601 formatted game date/time
        home_team: Home team information (ESPNTeamInfo)
        away_team: Away team information (ESPNTeamInfo)
        venue: Venue information (ESPNVenueInfo)
        broadcast: TV network (e.g., "CBS", "ESPN", "FOX")
        neutral_site: True if game is at neutral location
        season_type: Game type (preseason, regular, playoff, bowl, allstar)
        week_number: Week of the season (if applicable)

    Reference: Phase 2 ESPN Data Model Plan
    """

    espn_event_id: str
    game_date: str
    home_team: ESPNTeamInfo
    away_team: ESPNTeamInfo
    venue: ESPNVenueInfo
    broadcast: str
    neutral_site: bool
    season_type: str
    week_number: int | None


class ESPNSituationData(TypedDict, total=False):
    """Sport-specific situation data (stored as JSONB in database).

    Educational Note:
        Different sports have different in-game situations:
        - NFL/NCAAF: downs, distance, yard line, possession
        - NBA/NCAAB: fouls, bonus status, possession arrow
        - NHL: power plays, shots on goal

        Using JSONB allows sport-specific fields without schema changes.

    Common Fields:
        possession: Which team has the ball ("home" or "away")
        home_timeouts: Home team timeouts remaining
        away_timeouts: Away team timeouts remaining

    Football-specific (NFL/NCAAF):
        down: Current down (1-4)
        distance: Yards to first down
        yard_line: Current yard line (0-100)
        is_red_zone: Inside opponent's 20-yard line
        home_turnovers: Home team turnover count
        away_turnovers: Away team turnover count
        last_play: Description of last play
        drive_plays: Plays in current drive
        drive_yards: Yards in current drive

    Basketball-specific (NBA/NCAAB):
        home_fouls: Home team foul count
        away_fouls: Away team foul count
        bonus: Team in bonus ("home", "away", or None)
        possession_arrow: Next possession on jump ball

    Hockey-specific (NHL):
        home_powerplay: Home team on power play
        away_powerplay: Away team on power play
        powerplay_time: Time remaining in power play
        home_shots: Home team shots on goal
        away_shots: Away team shots on goal

    Reference: Phase 2 ESPN Data Model Plan
    """

    # Common
    possession: str | None
    home_timeouts: int
    away_timeouts: int

    # Football (NFL/NCAAF)
    down: int | None
    distance: int | None
    yard_line: int | None
    is_red_zone: bool
    home_turnovers: int
    away_turnovers: int
    last_play: str
    drive_plays: int
    drive_yards: int

    # Basketball (NBA/NCAAB)
    home_fouls: int
    away_fouls: int
    bonus: str | None
    possession_arrow: str | None

    # Hockey (NHL)
    home_powerplay: bool
    away_powerplay: bool
    powerplay_time: str
    home_shots: int
    away_shots: int


class ESPNGameState(TypedDict, total=False):
    """Dynamic game state that changes during live games.

    Educational Note:
        This captures the current state of a game at a point in time.
        With SCD Type 2 versioning, we store every state change for:
        - Live game tracking
        - Historical analysis
        - ML model training

    Fields:
        espn_event_id: Reference to the game (FK to metadata)
        home_score: Home team current score
        away_score: Away team current score
        period: Current period (1-4 for quarters, 5+ for OT)
        clock_seconds: Time remaining in period (seconds)
        clock_display: Formatted clock (e.g., "8:05")
        game_status: Current status (scheduled, in_progress, halftime, final)
        situation: Sport-specific situation data
        linescores: Quarter-by-quarter scores [[H1,A1], [H2,A2], ...]

    Reference: Phase 2 ESPN Data Model Plan
    """

    espn_event_id: str
    home_score: int
    away_score: int
    period: int
    clock_seconds: float
    clock_display: str
    game_status: str
    situation: ESPNSituationData
    linescores: list[list[int]]


class ESPNGameFull(TypedDict, total=False):
    """Complete game data combining metadata and current state.

    Educational Note:
        This is the "full picture" TypedDict returned by scoreboard endpoints.
        It combines static metadata with dynamic state for convenience.

        For database storage:
        - metadata -> game metadata + venues + teams tables
        - state -> game_states table (SCD Type 2)

    Fields:
        metadata: Static game information
        state: Current dynamic state

    Reference: Phase 2 ESPN Data Model Plan
    """

    metadata: ESPNGameMetadata
    state: ESPNGameState


# =============================================================================
# Backward Compatibility - GameState Alias
# =============================================================================
# The original GameState TypedDict is maintained for backward compatibility.
# New code should use ESPNGameFull, ESPNGameMetadata, or ESPNGameState.


class GameState(TypedDict, total=False):
    """Legacy game state format - DEPRECATED, use ESPNGameFull instead.

    Educational Note:
        This flattened format is maintained for backward compatibility with
        existing code and tests. New code should use the normalized TypeDicts:
        - ESPNGameFull: Complete game data
        - ESPNGameMetadata: Static game info
        - ESPNGameState: Dynamic game state
        - ESPNTeamInfo: Team details
        - ESPNVenueInfo: Venue details

    Migration Path:
        Old: game["home_team"]
        New: game["metadata"]["home_team"]["team_code"]

        Old: game["home_score"]
        New: game["state"]["home_score"]

    Reference: Phase 2 ESPN Data Model Plan - TypedDict Refactoring
    """

    # Core game identification
    espn_event_id: str
    game_date: str
    home_team: str
    away_team: str
    home_team_id: str
    away_team_id: str
    home_display_name: str
    away_display_name: str

    # Current score and time
    home_score: int
    away_score: int
    period: int
    clock_seconds: float
    clock_display: str
    game_status: str

    # Situation (in-game)
    possession: str | None
    down: int | None
    distance: int | None
    yard_line: int | None
    is_red_zone: bool
    home_timeouts: int
    away_timeouts: int

    # Model training features - Team performance
    home_record: str
    away_record: str
    home_home_record: str  # Home team's record at home
    away_away_record: str  # Away team's record on road

    # Model training features - Scoring progression
    linescores: list[list[int]]  # [[home_q1, away_q1], [home_q2, away_q2], ...]

    # Model training features - Venue
    venue_name: str
    venue_city: str
    venue_indoor: bool
    venue_capacity: int

    # Model training features - Context
    broadcast: str
    home_rank: int | None  # College football rankings
    away_rank: int | None


# =============================================================================
# ESPN Client
# =============================================================================


class ESPNClient:
    """
    High-level ESPN API client for live game data.

    Manages:
    - API requests with connection pooling
    - Rate limiting (500 req/hour)
    - Retry logic with exponential backoff
    - Response parsing

    Usage:
        >>> # Initialize
        >>> client = ESPNClient()
        >>>
        >>> # Get NFL scoreboard
        >>> games = client.get_nfl_scoreboard()
        >>>
        >>> # Get only live games
        >>> live_games = client.get_live_games(league="nfl")
        >>>
        >>> # Check rate limit status
        >>> remaining = client.get_remaining_requests()
        >>> print(f"{remaining} requests remaining this hour")

    Educational Note:
        This client uses a requests.Session for connection pooling,
        which reuses TCP connections for better performance when making
        multiple requests to the same host.

    Reference: docs/testing/PHASE_2_TEST_PLAN_V1.0.md Section 2.1
    """

    # API endpoints - Multi-sport support
    # All ESPN scoreboards use the same base pattern
    BASE_URL: ClassVar[str] = "https://site.api.espn.com/apis/site/v2/sports"

    ENDPOINTS: ClassVar[dict[str, str]] = {
        # Football
        "nfl": f"{BASE_URL}/football/nfl/scoreboard",
        "ncaaf": f"{BASE_URL}/football/college-football/scoreboard",
        # Basketball
        "nba": f"{BASE_URL}/basketball/nba/scoreboard",
        "ncaab": f"{BASE_URL}/basketball/mens-college-basketball/scoreboard",
        "wnba": f"{BASE_URL}/basketball/wnba/scoreboard",
        # Hockey
        "nhl": f"{BASE_URL}/hockey/nhl/scoreboard",
    }

    # Sport categories for situation parsing
    FOOTBALL_SPORTS: ClassVar[set[str]] = {"nfl", "ncaaf"}
    BASKETBALL_SPORTS: ClassVar[set[str]] = {"nba", "ncaab", "wnba"}
    HOCKEY_SPORTS: ClassVar[set[str]] = {"nhl"}

    # Game status mapping from ESPN to our internal format
    # ESPN states: pre, in, post -> our database values: pre, in_progress, final
    STATUS_MAP: ClassVar[dict[str, str]] = {
        "pre": "pre",  # Keep as 'pre' to match database constraint
        "in": "in_progress",
        "post": "final",
    }

    # Season type mapping from ESPN integers to our database strings
    # ESPN: 1=preseason, 2=regular, 3=postseason, 4=offseason
    SEASON_TYPE_MAP: ClassVar[dict[int, str]] = {
        1: "preseason",
        2: "regular",
        3: "playoff",  # postseason -> playoff in our schema
        4: "exhibition",  # offseason
        5: "allstar",  # all-star games
    }

    def __init__(
        self,
        rate_limit_per_hour: int = 500,
        timeout_seconds: float = 10,
        max_retries: int = 3,
    ):
        """
        Initialize ESPN client.

        Args:
            rate_limit_per_hour: Maximum requests allowed per hour (default 500)
            timeout_seconds: Request timeout in seconds (default 10, supports float for sub-second)
            max_retries: Maximum retry attempts for failed requests (default 3)

        Educational Note:
            Default values are chosen for production use:
            - 500 req/hour = 8.3 req/min (plenty for 15-second polling)
            - 10s timeout = reasonable for API responses
            - 3 retries = handles transient failures without excessive delays
        """
        self.rate_limit_per_hour = rate_limit_per_hour
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # Request tracking for rate limiting
        self.request_timestamps: list[datetime] = []

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Precog/1.0 (Sports Analytics)",
                "Accept": "application/json",
            }
        )

        logger.info(
            f"ESPN client initialized (rate_limit={rate_limit_per_hour}/hr, "
            f"timeout={timeout_seconds}s, max_retries={max_retries})"
        )

    # =========================================================================
    # Public API Methods
    # =========================================================================

    def get_nfl_scoreboard(self, date: datetime | None = None) -> list[ESPNGameFull]:
        """
        Fetch NFL scoreboard with all games for the specified date.

        Args:
            date: Target date for scoreboard (default: today)

        Returns:
            List of ESPNGameFull dicts for each game

        Raises:
            RateLimitExceeded: If rate limit would be exceeded
            ESPNAPIError: If API request fails after retries

        Usage:
            >>> games = client.get_nfl_scoreboard()
            >>> for game in games:
            ...     home = game["metadata"]["home_team"]["team_code"]
            ...     away = game["metadata"]["away_team"]["team_code"]
            ...     print(f"{away} @ {home}: {game['state']['away_score']}-{game['state']['home_score']}")
        """
        return self._get_scoreboard("nfl", date)

    def get_ncaaf_scoreboard(self, date: datetime | None = None) -> list[ESPNGameFull]:
        """
        Fetch NCAAF (college football) scoreboard for the specified date.

        Args:
            date: Target date for scoreboard (default: today)

        Returns:
            List of ESPNGameFull dicts for each game

        Raises:
            RateLimitExceeded: If rate limit would be exceeded
            ESPNAPIError: If API request fails after retries
        """
        return self._get_scoreboard("ncaaf", date)

    def get_nba_scoreboard(self, date: datetime | None = None) -> list[ESPNGameFull]:
        """
        Fetch NBA scoreboard for the specified date.

        Args:
            date: Target date for scoreboard (default: today)

        Returns:
            List of ESPNGameFull dicts for each game

        Raises:
            RateLimitExceeded: If rate limit would be exceeded
            ESPNAPIError: If API request fails after retries

        Educational Note:
            NBA games use 4 quarters like NFL, but have different situation
            data (fouls, bonus status) stored in the situation JSONB field.

        Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
        """
        return self._get_scoreboard("nba", date)

    def get_ncaab_scoreboard(self, date: datetime | None = None) -> list[ESPNGameFull]:
        """
        Fetch NCAAB (men's college basketball) scoreboard for the specified date.

        Args:
            date: Target date for scoreboard (default: today)

        Returns:
            List of ESPNGameFull dicts for each game

        Raises:
            RateLimitExceeded: If rate limit would be exceeded
            ESPNAPIError: If API request fails after retries

        Educational Note:
            College basketball has 2 halves instead of 4 quarters.
            Period values: 1 = first half, 2 = second half, 3+ = overtime.

        Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
        """
        return self._get_scoreboard("ncaab", date)

    def get_nhl_scoreboard(self, date: datetime | None = None) -> list[ESPNGameFull]:
        """
        Fetch NHL scoreboard for the specified date.

        Args:
            date: Target date for scoreboard (default: today)

        Returns:
            List of ESPNGameFull dicts for each game

        Raises:
            RateLimitExceeded: If rate limit would be exceeded
            ESPNAPIError: If API request fails after retries

        Educational Note:
            NHL games have 3 periods (not 4 quarters).
            Situation data includes power play status and shots on goal.

        Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
        """
        return self._get_scoreboard("nhl", date)

    def get_wnba_scoreboard(self, date: datetime | None = None) -> list[ESPNGameFull]:
        """
        Fetch WNBA scoreboard for the specified date.

        Args:
            date: Target date for scoreboard (default: today)

        Returns:
            List of ESPNGameFull dicts for each game

        Raises:
            RateLimitExceeded: If rate limit would be exceeded
            ESPNAPIError: If API request fails after retries

        Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
        """
        return self._get_scoreboard("wnba", date)

    def get_scoreboard(self, league: str, date: datetime | None = None) -> list[ESPNGameFull]:
        """
        Fetch scoreboard for any supported league.

        Returns ESPNGameFull with structured metadata/state sections,
        matching the database schema design.

        Args:
            league: One of "nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"
            date: Target date for scoreboard (default: today)

        Returns:
            List of ESPNGameFull dicts for each game

        Raises:
            ValueError: If league is not supported
            RateLimitExceeded: If rate limit would be exceeded
            ESPNAPIError: If API request fails after retries

        Example:
            >>> games = client.get_scoreboard("nfl")
            >>> for game in games:
            ...     home = game["metadata"]["home_team"]["team_code"]
            ...     away = game["metadata"]["away_team"]["team_code"]
            ...     score = f"{game['state']['home_score']}-{game['state']['away_score']}"
            ...     print(f"{away} @ {home}: {score}")

        Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
        Related: REQ-DATA-001 (Game State Data Collection)
        """
        if league not in self.ENDPOINTS:
            raise ValueError(
                f"Unsupported league: {league}. Supported: {list(self.ENDPOINTS.keys())}"
            )
        return self._get_scoreboard(league, date)

    def get_live_games(self, league: str = "nfl") -> list[ESPNGameFull]:
        """
        Get only games currently in progress (excludes scheduled and final).

        Args:
            league: "nfl", "ncaaf", "nba", "ncaab", "nhl", or "wnba"

        Returns:
            List of ESPNGameFull dicts for live games only

        Educational Note:
            "Live" includes games at halftime/intermission since they're not over yet.
            Only games with status "final" or "scheduled" are excluded.

        Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
        """
        all_games = self.get_scoreboard(league)

        # Filter to only in-progress games (includes halftime/intermission)
        live_statuses = {"in_progress", "halftime"}
        return [g for g in all_games if g.get("state", {}).get("game_status") in live_statuses]

    def get_remaining_requests(self) -> int:
        """
        Get number of requests remaining in current rate limit window.

        Returns:
            Number of requests that can be made before rate limit is hit

        Usage:
            >>> remaining = client.get_remaining_requests()
            >>> if remaining < 10:
            ...     print("Warning: Approaching rate limit!")
        """
        self._clean_old_timestamps()
        return self.rate_limit_per_hour - len(self.request_timestamps)

    def close(self) -> None:
        """
        Close the HTTP session and release resources.

        Should be called when the client is no longer needed to properly
        clean up connection pools and prevent resource leaks.

        Usage:
            >>> client = ESPNClient()
            >>> try:
            ...     games = client.get_nfl_scoreboard()
            ... finally:
            ...     client.close()

        Educational Note:
            Resource cleanup is important for long-running applications.
            The requests.Session maintains a connection pool that should
            be explicitly closed when no longer needed.

            For context managers, consider using:
            >>> with contextlib.closing(ESPNClient()) as client:
            ...     games = client.get_nfl_scoreboard()

        Reference: Pattern 11 (Resource Cleanup) - DEVELOPMENT_PATTERNS
        """
        if hasattr(self, "session") and self.session:
            self.session.close()
            logger.debug("ESPN client session closed")

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _get_scoreboard(self, league: str, date: datetime | None = None) -> list[ESPNGameFull]:
        """
        Internal method to fetch and parse scoreboard data.

        Args:
            league: League code (nfl, ncaaf, nba, etc.)
            date: Target date (default: today)

        Returns:
            List of parsed ESPNGameFull dicts with metadata/state structure
        """
        # Check rate limit before making request
        self._check_rate_limit()

        # Build URL with optional date parameter
        url = self.ENDPOINTS[league]
        params = {}
        if date:
            params["dates"] = date.strftime("%Y%m%d")

        # Make request with retries
        response_data = self._make_request(url, params)

        # Parse events from response
        events = response_data.get("events", [])
        if not events:
            return []

        # Parse each event into ESPNGameFull
        games: list[ESPNGameFull] = []
        for event in events:
            try:
                game_full = self._parse_event(event)
                if game_full:
                    games.append(game_full)
            except Exception as e:
                logger.warning(f"Failed to parse event {event.get('id', 'unknown')}: {e}")
                continue

        return games

    def _make_request(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Make HTTP request with retries and exponential backoff.

        Args:
            url: Request URL
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            ESPNAPIError: After all retries exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout_seconds,
                )

                # Track successful request
                self.request_timestamps.append(datetime.now())

                # Check for HTTP errors
                response.raise_for_status()

                # Parse JSON
                try:
                    result: dict[str, Any] = response.json()
                    return result
                except ValueError as e:
                    raise ESPNAPIError(f"Invalid JSON response: {e}") from e

            except requests.Timeout as e:
                last_exception = e
                logger.warning(f"Request timeout (attempt {attempt + 1}/{self.max_retries + 1})")

            except requests.ConnectionError as e:
                last_exception = e
                logger.warning(
                    f"Connection error (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )

            except requests.exceptions.ChunkedEncodingError as e:
                last_exception = e
                logger.warning(
                    f"Chunked encoding error (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )

            except requests.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if e.response else 0

                # Don't retry 4xx errors (client errors)
                if 400 <= status_code < 500:
                    raise ESPNAPIError(f"HTTP {status_code}: {e}") from e

                # Retry 5xx errors (server errors)
                logger.warning(
                    f"HTTP {status_code} error (attempt {attempt + 1}/{self.max_retries + 1})"
                )

            # Exponential backoff before retry
            if attempt < self.max_retries:
                backoff = 2**attempt  # 1, 2, 4 seconds
                logger.debug(f"Retrying in {backoff}s...")
                time.sleep(backoff)

        # All retries exhausted
        if isinstance(last_exception, requests.Timeout):
            raise ESPNAPIError(
                f"Request timeout after {self.max_retries + 1} attempts"
            ) from last_exception
        if isinstance(last_exception, requests.ConnectionError):
            raise ESPNAPIError(
                f"Connection error after {self.max_retries + 1} attempts"
            ) from last_exception
        if isinstance(last_exception, requests.exceptions.ChunkedEncodingError):
            raise ESPNAPIError(
                f"Chunked encoding error after {self.max_retries + 1} attempts"
            ) from last_exception
        raise ESPNAPIError(
            f"Request failed after {self.max_retries + 1} attempts"
        ) from last_exception

    def _parse_event(self, event: dict[str, Any]) -> ESPNGameFull | None:
        """
        Parse ESPN event into normalized ESPNGameFull structure.

        Returns a structured TypedDict with separate metadata and state sections,
        matching the database schema design.

        Args:
            event: Raw ESPN event dict

        Returns:
            Parsed ESPNGameFull or None if parsing fails

        Educational Note:
            ESPN's response structure is deeply nested:
            event -> competitions[0] -> competitors[0/1]

            This method normalizes the structure into:
            - metadata -> teams, venues, game metadata tables
            - state -> game_states table (SCD Type 2)

            This separation makes it easier to update each table independently
            and provides better type safety.

        Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
        """
        try:
            event_id = event.get("id", "")
            event_date = event.get("date", "")

            # Get first competition
            competitions = event.get("competitions", [])
            if not competitions:
                return None

            competition = competitions[0]

            # Get competitors
            competitors = competition.get("competitors", [])
            if len(competitors) < 2:
                return None

            # Find home and away teams
            home_team = None
            away_team = None
            for competitor in competitors:
                if competitor.get("homeAway") == "home":
                    home_team = competitor
                else:
                    away_team = competitor

            if not home_team or not away_team:
                return None

            # Parse team info
            home_team_info = home_team.get("team", {})
            away_team_info = away_team.get("team", {})

            # Parse records
            home_records = {
                r.get("name"): r.get("summary", "") for r in home_team.get("records", [])
            }
            away_records = {
                r.get("name"): r.get("summary", "") for r in away_team.get("records", [])
            }

            # Build home team TypedDict
            home_team_typed: ESPNTeamInfo = {
                "espn_team_id": home_team.get("id", ""),
                "team_code": home_team_info.get("abbreviation", ""),
                "team_name": home_team_info.get("name", ""),
                "display_name": home_team_info.get("displayName", ""),
                "record": home_records.get("overall", ""),
                "home_record": home_records.get("home", ""),
                "away_record": home_records.get("away", ""),
                "rank": home_team.get("curatedRank", {}).get("current"),
            }

            # Build away team TypedDict
            away_team_typed: ESPNTeamInfo = {
                "espn_team_id": away_team.get("id", ""),
                "team_code": away_team_info.get("abbreviation", ""),
                "team_name": away_team_info.get("name", ""),
                "display_name": away_team_info.get("displayName", ""),
                "record": away_records.get("overall", ""),
                "home_record": away_records.get("home", ""),
                "away_record": away_records.get("away", ""),
                "rank": away_team.get("curatedRank", {}).get("current"),
            }

            # Parse venue info
            venue = competition.get("venue", {})
            venue_address = venue.get("address", {})
            venue_typed: ESPNVenueInfo = {
                "espn_venue_id": str(venue.get("id", "")),
                "venue_name": venue.get("fullName", ""),
                "city": venue_address.get("city", ""),
                "state": venue_address.get("state", ""),
                "capacity": venue.get("capacity", 0),
                "indoor": venue.get("indoor", False),
            }

            # Parse broadcast
            broadcasts = competition.get("broadcasts", [])
            broadcast = ""
            if broadcasts:
                names = broadcasts[0].get("names", [])
                broadcast = names[0] if names else ""

            # Build metadata
            metadata: ESPNGameMetadata = {
                "espn_event_id": event_id,
                "game_date": event_date,
                "home_team": home_team_typed,
                "away_team": away_team_typed,
                "venue": venue_typed,
                "broadcast": broadcast,
                "neutral_site": competition.get("neutralSite", False),
                "season_type": self.SEASON_TYPE_MAP.get(
                    event.get("season", {}).get("type", 2), "regular"
                ),
                "week_number": event.get("week", {}).get("number"),
            }

            # Parse status
            status = competition.get("status", {})
            status_type = status.get("type", {})
            state = status_type.get("state", "pre")
            status_name = status_type.get("name", "")

            if status_name == "STATUS_HALFTIME":
                game_status = "halftime"
            else:
                game_status = self.STATUS_MAP.get(state, "unknown")

            # Parse scores
            home_score_str = home_team.get("score", "0")
            away_score_str = away_team.get("score", "0")
            home_score = int(home_score_str) if home_score_str else 0
            away_score = int(away_score_str) if away_score_str else 0

            # Parse clock
            clock_seconds = status.get("clock", 0.0)
            clock_display = status.get("displayClock", "0:00")
            period = status.get("period", 0)

            # Parse linescores
            home_linescores = [ls.get("value", 0) for ls in home_team.get("linescores", [])]
            away_linescores = [ls.get("value", 0) for ls in away_team.get("linescores", [])]
            linescores = (
                [list(qs) for qs in zip(home_linescores, away_linescores, strict=False)]
                if home_linescores
                else []
            )

            # Parse situation
            situation_raw = competition.get("situation", {})
            possession_id = situation_raw.get("possession")

            # Determine possession team code
            possession = None
            if possession_id:
                if possession_id == home_team.get("id"):
                    possession = home_team_typed["team_code"]
                elif possession_id == away_team.get("id"):
                    possession = away_team_typed["team_code"]

            # Build situation TypedDict
            situation: ESPNSituationData = {
                "possession": possession,
                "home_timeouts": situation_raw.get("homeTimeouts", 3),
                "away_timeouts": situation_raw.get("awayTimeouts", 3),
                "down": situation_raw.get("down"),
                "distance": situation_raw.get("distance"),
                "yard_line": situation_raw.get("yardLine"),
                "is_red_zone": situation_raw.get("isRedZone", False),
            }

            # Build state
            game_state: ESPNGameState = {
                "espn_event_id": event_id,
                "home_score": home_score,
                "away_score": away_score,
                "period": period,
                "clock_seconds": float(clock_seconds) if clock_seconds else 0.0,
                "clock_display": clock_display,
                "game_status": game_status,
                "situation": situation,
                "linescores": linescores,
            }

            # Combine into ESPNGameFull
            full_game: ESPNGameFull = {
                "metadata": metadata,
                "state": game_state,
            }

            return full_game

        except Exception as e:
            logger.warning(f"Error parsing event: {e}")
            return None

    def _check_rate_limit(self) -> None:
        """
        Check if request would exceed rate limit.

        Raises:
            RateLimitExceeded: If rate limit would be exceeded
        """
        self._clean_old_timestamps()

        if len(self.request_timestamps) >= self.rate_limit_per_hour:
            raise RateLimitExceeded(
                f"Rate limit exceeded ({self.rate_limit_per_hour} requests/hour). "
                f"Try again in a few minutes."
            )

    def _clean_old_timestamps(self) -> None:
        """
        Remove timestamps older than 1 hour from tracking list.

        Educational Note:
            This sliding window approach means the rate limit resets
            gradually over time rather than all at once on the hour.
        """
        cutoff = datetime.now() - timedelta(hours=1)
        self.request_timestamps = [ts for ts in self.request_timestamps if ts > cutoff]
