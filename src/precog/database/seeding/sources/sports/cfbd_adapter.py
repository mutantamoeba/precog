"""
College Football Data (CFBD) API Source Adapter.

Provides access to college football team data through the CFBD REST API.
Primary use case: fetching team classifications (FBS/FCS/D2/D3) for the
teams table, which enables correct market matching on Kalshi.

CFBD REST API:
    Base URL: https://api.collegefootballdata.com
    Auth: Bearer token via CFBD_API_KEY environment variable
    Docs: https://api.collegefootballdata.com/api/docs

Key Data Available:
    - Team info with classification (FBS, FCS, D2, D3)
    - Conference membership
    - Game schedules and results (2000-present)
    - Rankings, stats, betting lines
    - Recruiting data

Current Implementation:
    - get_team_classifications(): Team classification data (FBS/FCS/D2/D3)
    - load_games(): Stubbed for future implementation (#487)

CFBD Classification Values:
    The API returns lowercase classification strings:
    - "fbs" -> "fbs" (Football Bowl Subdivision, ~130 teams)
    - "fcs" -> "fcs" (Football Championship Subdivision, ~130 teams)
    - "ii"  -> "d2"  (Division II, ~170 teams)
    - "iii" -> "d3"  (Division III, ~240 teams)

    We map "ii" and "iii" to "d2" and "d3" for consistency with our
    database schema (migration 0042).

Related:
    - Issue #486: Team code collision fix + division classification
    - Issue #487: CFBD as historical game data source for Elo
    - Migration 0042: classification column on teams table
    - ADR-106: Historical Data Collection Architecture
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict

import requests

from precog.database.seeding.sources.base_source import (
    APIBasedSourceMixin,
    BaseDataSource,
    DataSourceConfigError,
    DataSourceConnectionError,
    DataSourceError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from precog.database.seeding.sources.base_source import GameRecord

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

CFBD_BASE_URL = "https://api.collegefootballdata.com"
CFBD_API_KEY_ENV = "CFBD_API_KEY"

# Default request timeout in seconds (connect, read)
REQUEST_TIMEOUT = (10, 30)


# =============================================================================
# Classification Mapping
# =============================================================================

# CFBD returns "ii" and "iii" for Division II and III respectively.
# We normalize to "d2" and "d3" for our database schema (migration 0042).
CFBD_CLASSIFICATION_MAP: dict[str, str] = {
    "fbs": "fbs",
    "fcs": "fcs",
    "ii": "d2",
    "iii": "d3",
}


# =============================================================================
# Type Definitions
# =============================================================================


class TeamClassification(TypedDict):
    """Team classification record from CFBD API.

    Represents a single team's division classification, used to populate
    the classification column on the teams table.

    Fields:
        school: Full school name (e.g., "Alabama")
        abbreviation: CFBD's team abbreviation (e.g., "ALA")
        conference: Conference name or None (e.g., "SEC")
        classification: Normalized classification string:
            "fbs", "fcs", "d2", "d3" (mapped from CFBD values)

    Example:
        >>> {"school": "Alabama", "abbreviation": "ALA",
        ...  "conference": "SEC", "classification": "fbs"}
    """

    school: str
    abbreviation: str | None
    conference: str | None
    classification: str


# =============================================================================
# CFBD Source Adapter
# =============================================================================


class CFBDSource(APIBasedSourceMixin, BaseDataSource):
    """College Football Data API source adapter.

    Fetches team classification data from the CFBD REST API using
    direct HTTP requests (no cfbd Python package dependency).

    Primary Method:
        get_team_classifications() - Returns FBS/FCS/D2/D3 classification
        for all college football teams. This is the main entry point for
        Task B of #486.

    Authentication:
        Requires a CFBD API key set in the CFBD_API_KEY environment variable.
        Get a free key at: https://collegefootballdata.com/key

    Usage:
        >>> source = CFBDSource()
        >>> teams = source.get_team_classifications()
        >>> fbs_teams = [t for t in teams if t["classification"] == "fbs"]
        >>> print(f"Found {len(fbs_teams)} FBS teams")

    Attributes:
        source_name: "cfbd"
        supported_sports: ["ncaaf"]

    Rate Limiting:
        CFBD allows ~60 requests/minute for free tier.
        Team classification only needs one request, so rate limiting
        is not a practical concern for the current use case.

    Related:
        - Issue #486: Team code collision fix + division classification
        - Issue #487: Historical game data loading (future)
        - Migration 0042: classification column
    """

    source_name = "cfbd"
    supported_sports: ClassVar[list[str]] = ["ncaaf"]

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        """Initialize CFBD API source.

        Args:
            api_key: CFBD API key. If None, reads from CFBD_API_KEY env var.
            **kwargs: Configuration options passed to base class.

        Raises:
            DataSourceConfigError: If no API key is available.

        Example:
            >>> source = CFBDSource()  # Uses env var
            >>> source = CFBDSource(api_key="YOUR_KEY")  # Explicit key
        """
        super().__init__(**kwargs)
        self._api_key = api_key or os.getenv(CFBD_API_KEY_ENV)
        self._session: requests.Session | None = None

    def _ensure_api_key(self) -> str:
        """Validate and return the API key.

        Returns:
            The CFBD API key string.

        Raises:
            DataSourceConfigError: If no API key is configured.
        """
        if not self._api_key:
            raise DataSourceConfigError(
                f"CFBD API key not configured. Set the {CFBD_API_KEY_ENV} "
                f"environment variable or pass api_key to constructor. "
                f"Get a free key at: https://collegefootballdata.com/key"
            )
        return self._api_key

    def _get_session(self) -> requests.Session:
        """Get or create a requests session with auth headers.

        Returns:
            Configured requests.Session with Bearer token auth.

        Raises:
            DataSourceConfigError: If no API key is available.

        Educational Note:
            We reuse sessions for connection pooling. The CFBD API
            uses Bearer token authentication in the Authorization header.
        """
        if self._session is None:
            api_key = self._ensure_api_key()
            self._session = requests.Session()
            self._session.headers.update(
                {
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                }
            )
        return self._session

    def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Make an authenticated GET request to the CFBD API.

        Args:
            endpoint: API endpoint path (e.g., "/teams")
            params: Optional query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            DataSourceConnectionError: If the request fails (network,
                auth, server error).

        Example:
            >>> data = self._request("/teams")
            >>> len(data)  # Number of teams returned
            800+
        """
        url = f"{CFBD_BASE_URL}{endpoint}"
        session = self._get_session()

        try:
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as e:
            raise DataSourceConnectionError(
                f"CFBD API request timed out for {endpoint}: {e}"
            ) from e
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "unknown"
            if status_code == 401:
                raise DataSourceConnectionError(
                    "CFBD API authentication failed. Check your CFBD_API_KEY."
                ) from e
            raise DataSourceConnectionError(
                f"CFBD API HTTP error {status_code} for {endpoint}: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise DataSourceConnectionError(f"CFBD API connection error for {endpoint}: {e}") from e

    def close(self) -> None:
        """Close the HTTP session and release resources.

        Should be called when done with the adapter to clean up
        connection pool resources.

        Example:
            >>> source = CFBDSource()
            >>> try:
            ...     teams = source.get_team_classifications()
            ... finally:
            ...     source.close()
        """
        if self._session is not None:
            self._session.close()
            self._session = None

    # -------------------------------------------------------------------------
    # Team Classification (Primary Method for #486)
    # -------------------------------------------------------------------------

    def get_team_classifications(self) -> list[TeamClassification]:
        """Fetch team classifications from the CFBD API.

        Calls GET /teams and maps each team's classification to our
        normalized values (fbs, fcs, d2, d3). Teams without a
        classification field are skipped.

        Returns:
            List of TeamClassification dicts, one per team.

        Raises:
            DataSourceConnectionError: If the API request fails.
            DataSourceConfigError: If the API key is not configured.
            DataSourceError: If the response cannot be parsed.

        Example:
            >>> source = CFBDSource()
            >>> teams = source.get_team_classifications()
            >>> for t in teams[:3]:
            ...     print(f"{t['school']} ({t['abbreviation']}): {t['classification']}")
            Alabama (ALA): fbs
            Abilene Christian (ACU): fcs
            Adams State (None): d2
        """
        self._logger.info("Fetching team classifications from CFBD API")

        raw_teams = self._request("/teams")

        if not isinstance(raw_teams, list):
            raise DataSourceError(
                f"CFBD /teams returned unexpected type: {type(raw_teams).__name__}. "
                f"Expected a list of team objects."
            )

        results: list[TeamClassification] = []
        skipped = 0

        for team in raw_teams:
            if not isinstance(team, dict):
                self._logger.warning("Skipping non-dict team entry: %s", type(team).__name__)
                skipped += 1
                continue

            raw_classification = team.get("classification")
            if raw_classification is None:
                # Some teams (club teams, etc.) have no classification
                skipped += 1
                continue

            # Normalize classification: "ii" -> "d2", "iii" -> "d3"
            raw_class_lower = str(raw_classification).lower().strip()
            classification = CFBD_CLASSIFICATION_MAP.get(raw_class_lower)

            if classification is None:
                self._logger.warning(
                    "Unknown CFBD classification '%s' for team '%s', skipping",
                    raw_classification,
                    team.get("school", "unknown"),
                )
                skipped += 1
                continue

            abbreviation = team.get("abbreviation")
            if abbreviation is not None:
                abbreviation = str(abbreviation).strip()
                if not abbreviation:
                    abbreviation = None

            record = TeamClassification(
                school=str(team.get("school", "")).strip(),
                abbreviation=abbreviation,
                conference=team.get("conference"),
                classification=classification,
            )
            results.append(record)

        self._logger.info(
            "CFBD team classifications: %d teams loaded, %d skipped",
            len(results),
            skipped,
        )

        return results

    # -------------------------------------------------------------------------
    # Game Data Loading (Stubbed for #487)
    # -------------------------------------------------------------------------

    def load_games(
        self,
        sport: str = "ncaaf",
        seasons: list[int] | None = None,
        **kwargs: Any,
    ) -> Iterator[GameRecord]:
        """Load historical NCAAF game data from CFBD.

        NOT YET IMPLEMENTED. This will be built in Issue #487:
        "CFBD as historical game data source for Elo."

        The CFBD API provides comprehensive game data including:
        - Regular season and postseason results
        - Neutral site indicators
        - Venue information
        - Conference game flags
        - Game type classification

        Args:
            sport: Must be "ncaaf"
            seasons: List of seasons to load (e.g., [2022, 2023])
            **kwargs: Additional options

        Yields:
            GameRecord for each completed game (when implemented)

        Raises:
            NotImplementedError: Always, until #487 is implemented.

        Related:
            - Issue #487: CFBD as historical game data source for Elo
            - CFBD endpoint: GET /games?year={year}
        """
        raise NotImplementedError(
            "CFBD game loading is not yet implemented. "
            "Planned for Issue #487: CFBD as historical game data source for Elo. "
            "Use get_team_classifications() for team classification data."
        )

    # -------------------------------------------------------------------------
    # Capability Overrides
    # -------------------------------------------------------------------------

    def supports_games(self) -> bool:
        """CFBD can provide games, but not yet implemented (#487)."""
        return False

    def supports_odds(self) -> bool:
        """CFBD has betting data but we don't load it."""
        return False

    def supports_elo(self) -> bool:
        """CFBD does NOT provide Elo ratings (we compute our own)."""
        return False

    def supports_stats(self) -> bool:
        """CFBD has stats but we haven't implemented loading."""
        return False

    def supports_rankings(self) -> bool:
        """CFBD has rankings but we haven't implemented loading."""
        return False
