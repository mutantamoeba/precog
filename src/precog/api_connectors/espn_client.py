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
# TypedDict Response Types
# =============================================================================


class GameState(TypedDict, total=False):
    """Parsed game state from ESPN API.

    Educational Note:
        TypedDict provides compile-time type checking without runtime overhead.
        Using total=False makes all fields optional (some may be missing for
        pre-game or final states).

    Core Fields (always present):
        espn_event_id: Unique ESPN identifier for the game
        home_team: Home team abbreviation (e.g., "BUF")
        away_team: Away team abbreviation (e.g., "KC")
        home_score: Home team score (integer)
        away_score: Away team score (integer)
        period: Current period (1-4 for quarters, 5+ for OT)
        clock_seconds: Time remaining in period (seconds)
        clock_display: Formatted clock display (e.g., "8:05")
        game_status: Status string ("scheduled", "in_progress", "halftime", "final")

    Situation Fields (in-game only):
        possession: Which team has the ball ("home", "away", or None)
        down: Current down (1-4) or None
        distance: Yards to go for first down
        yard_line: Current yard line
        is_red_zone: True if offense is inside the 20
        home_timeouts: Home team timeouts remaining
        away_timeouts: Away team timeouts remaining

    Model Training Features (for edge detection):
        home_record: Home team record (e.g., "11-3")
        away_record: Away team record (e.g., "10-4")
        home_home_record: Home team record at home (e.g., "6-1")
        away_away_record: Away team record on road (e.g., "5-2")
        linescores: Quarter-by-quarter scores [[H1,A1], [H2,A2], ...]
        venue_name: Stadium name
        venue_city: Stadium city
        venue_indoor: True if dome/indoor stadium
        venue_capacity: Stadium capacity
        game_date: ISO format game date
        broadcast: TV network broadcasting
        home_rank: Home team ranking (college only, None for NFL)
        away_rank: Away team ranking (college only, None for NFL)
        home_team_id: ESPN team ID (for lookups)
        away_team_id: ESPN team ID (for lookups)
        home_display_name: Full team name (e.g., "Buffalo Bills")
        away_display_name: Full team name (e.g., "Kansas City Chiefs")
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

    # API endpoints
    ENDPOINTS: ClassVar[dict[str, str]] = {
        "nfl": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        "ncaaf": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
    }

    # Game status mapping from ESPN to our internal format
    STATUS_MAP: ClassVar[dict[str, str]] = {
        "pre": "scheduled",
        "in": "in_progress",
        "post": "final",
    }

    def __init__(
        self,
        rate_limit_per_hour: int = 500,
        timeout_seconds: int = 10,
        max_retries: int = 3,
    ):
        """
        Initialize ESPN client.

        Args:
            rate_limit_per_hour: Maximum requests allowed per hour (default 500)
            timeout_seconds: Request timeout in seconds (default 10)
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

    def get_nfl_scoreboard(self, date: datetime | None = None) -> list[GameState]:
        """
        Fetch NFL scoreboard with all games for the specified date.

        Args:
            date: Target date for scoreboard (default: today)

        Returns:
            List of GameState dicts for each game

        Raises:
            RateLimitExceeded: If rate limit would be exceeded
            ESPNAPIError: If API request fails after retries

        Usage:
            >>> games = client.get_nfl_scoreboard()
            >>> for game in games:
            ...     print(f"{game['away_team']} @ {game['home_team']}: "
            ...           f"{game['away_score']}-{game['home_score']}")
        """
        return self._get_scoreboard("nfl", date)

    def get_ncaaf_scoreboard(self, date: datetime | None = None) -> list[GameState]:
        """
        Fetch NCAAF (college football) scoreboard for the specified date.

        Args:
            date: Target date for scoreboard (default: today)

        Returns:
            List of GameState dicts for each game

        Raises:
            RateLimitExceeded: If rate limit would be exceeded
            ESPNAPIError: If API request fails after retries
        """
        return self._get_scoreboard("ncaaf", date)

    def get_live_games(self, league: str = "nfl") -> list[GameState]:
        """
        Get only games currently in progress (excludes scheduled and final).

        Args:
            league: "nfl" or "ncaaf"

        Returns:
            List of GameState dicts for live games only

        Educational Note:
            "Live" includes games at halftime since they're not over yet.
            Only games with status "final" or "scheduled" are excluded.
        """
        all_games = self.get_nfl_scoreboard() if league == "nfl" else self.get_ncaaf_scoreboard()

        # Filter to only in-progress games (includes halftime)
        live_statuses = {"in_progress", "halftime"}
        return [g for g in all_games if g.get("game_status") in live_statuses]

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

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _get_scoreboard(self, league: str, date: datetime | None = None) -> list[GameState]:
        """
        Internal method to fetch and parse scoreboard data.

        Args:
            league: "nfl" or "ncaaf"
            date: Target date (default: today)

        Returns:
            List of parsed GameState dicts
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

        # Parse each event into GameState
        games = []
        for event in events:
            try:
                game_state = self._parse_event(event)
                if game_state:
                    games.append(game_state)
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
        raise ESPNAPIError(
            f"Request failed after {self.max_retries + 1} attempts"
        ) from last_exception

    def _parse_event(self, event: dict[str, Any]) -> GameState | None:
        """
        Parse ESPN event into GameState.

        Args:
            event: Raw ESPN event dict

        Returns:
            Parsed GameState or None if parsing fails

        Educational Note:
            ESPN's response structure is deeply nested:
            event -> competitions[0] -> competitors[0/1]

            We flatten this into a clean GameState dict for easier use,
            extracting both core game info and model training features.
        """
        try:
            event_id = event.get("id", "")
            event_date = event.get("date", "")

            # Get first competition (there's usually only one)
            competitions = event.get("competitions", [])
            if not competitions:
                return None

            competition = competitions[0]

            # Get competitors (home and away teams)
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

            # Parse status
            status = competition.get("status", {})
            status_type = status.get("type", {})
            state = status_type.get("state", "pre")
            status_name = status_type.get("name", "")

            # Map ESPN status to our internal format
            if status_name == "STATUS_HALFTIME":
                game_status = "halftime"
            else:
                game_status = self.STATUS_MAP.get(state, "unknown")

            # Parse scores (convert from string, handle None)
            home_score_str = home_team.get("score", "0")
            away_score_str = away_team.get("score", "0")
            home_score = int(home_score_str) if home_score_str else 0
            away_score = int(away_score_str) if away_score_str else 0

            # Parse clock
            clock_seconds = status.get("clock", 0.0)
            clock_display = status.get("displayClock", "0:00")
            period = status.get("period", 0)

            # Parse team info
            home_team_info = home_team.get("team", {})
            away_team_info = away_team.get("team", {})
            home_abbr = home_team_info.get("abbreviation", "")
            away_abbr = away_team_info.get("abbreviation", "")

            # Parse situation (possession, down, etc.)
            situation = competition.get("situation", {})
            possession_id = situation.get("possession")

            # Determine possession (home or away)
            possession = None
            if possession_id:
                if possession_id == home_team.get("id"):
                    possession = "home"
                elif possession_id == away_team.get("id"):
                    possession = "away"

            # Parse records for model training
            home_records = {
                r.get("name"): r.get("summary", "") for r in home_team.get("records", [])
            }
            away_records = {
                r.get("name"): r.get("summary", "") for r in away_team.get("records", [])
            }

            # Parse linescores (quarter-by-quarter scores)
            home_linescores = [ls.get("value", 0) for ls in home_team.get("linescores", [])]
            away_linescores = [ls.get("value", 0) for ls in away_team.get("linescores", [])]
            # Combine into [[home_q1, away_q1], [home_q2, away_q2], ...]
            # Note: strict=False since linescores may have different lengths during game
            linescores = (
                list(zip(home_linescores, away_linescores, strict=False)) if home_linescores else []
            )

            # Parse venue info
            venue = competition.get("venue", {})
            venue_address = venue.get("address", {})

            # Parse broadcast info
            broadcasts = competition.get("broadcasts", [])
            broadcast = ""
            if broadcasts:
                names = broadcasts[0].get("names", [])
                broadcast = names[0] if names else ""

            # Parse rankings (college football)
            home_rank = home_team.get("curatedRank", {}).get("current")
            away_rank = away_team.get("curatedRank", {}).get("current")

            # Build GameState with all features
            game_state: GameState = {
                # Core identification
                "espn_event_id": event_id,
                "game_date": event_date,
                "home_team": home_abbr,
                "away_team": away_abbr,
                "home_team_id": home_team.get("id", ""),
                "away_team_id": away_team.get("id", ""),
                "home_display_name": home_team_info.get("displayName", ""),
                "away_display_name": away_team_info.get("displayName", ""),
                # Current state
                "home_score": home_score,
                "away_score": away_score,
                "period": period,
                "clock_seconds": float(clock_seconds) if clock_seconds else 0.0,
                "clock_display": clock_display,
                "game_status": game_status,
                # Situation
                "possession": possession,
                "down": situation.get("down"),
                "distance": situation.get("distance"),
                "yard_line": situation.get("yardLine"),
                "is_red_zone": situation.get("isRedZone", False),
                "home_timeouts": situation.get("homeTimeouts", 3),
                "away_timeouts": situation.get("awayTimeouts", 3),
                # Model training features - Records
                "home_record": home_records.get("overall", ""),
                "away_record": away_records.get("overall", ""),
                "home_home_record": home_records.get("home", ""),
                "away_away_record": away_records.get("away", ""),
                # Model training features - Scoring progression
                "linescores": [list(qs) for qs in linescores],  # Convert tuples to lists
                # Model training features - Venue
                "venue_name": venue.get("fullName", ""),
                "venue_city": venue_address.get("city", ""),
                "venue_indoor": venue.get("indoor", False),
                "venue_capacity": venue.get("capacity", 0),
                # Model training features - Context
                "broadcast": broadcast,
                "home_rank": home_rank,
                "away_rank": away_rank,
            }

            return game_state

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
