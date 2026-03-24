"""
In-memory cache of team code mappings for fast lookup during matching.

The registry loads team codes from the database at poller startup and
provides fast in-memory lookups for:
    1. Resolving Kalshi codes to canonical ESPN/DB team codes
    2. Getting all valid Kalshi codes for a league (for ticker splitting)

Mapping Strategy:
    - Teams WITH kalshi_team_code: Kalshi uses a different code than ESPN
      (e.g., JAC -> JAX, LA -> LAR)
    - Teams WITHOUT kalshi_team_code: Kalshi code is assumed to be the
      same as team_code (true for ~95% of teams)

The registry is designed to be loaded once at startup and refreshed
periodically (e.g., daily) rather than queried per-event.

Educational Note:
    Why an in-memory cache instead of DB lookups per event?
    The poller processes hundreds of events per cycle. A DB lookup per
    event would add ~100ms * N latency. The registry loads all codes in
    one query (~5ms) and provides O(1) lookups thereafter.

Related:
    - Issue #462: Event-to-game matching
    - Migration 0041: teams.kalshi_team_code column
    - crud_operations.get_teams_with_kalshi_codes(): Data source
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TeamCodeRegistry:
    """Cache of team code mappings for fast lookup during matching.

    Attributes:
        _kalshi_to_espn: dict[league, dict[kalshi_code, espn_team_code]]
            Maps Kalshi team codes to canonical ESPN team codes per league.
        _kalshi_codes: dict[league, set[str]]
            All valid Kalshi codes per league (for ticker splitting).
        _loaded: Whether the registry has been loaded from DB.

    Usage:
        >>> registry = TeamCodeRegistry()
        >>> registry.load()  # One-time at startup
        >>> espn_code = registry.resolve_kalshi_to_espn("JAC", "nfl")
        >>> espn_code  # "JAX"
        >>> codes = registry.get_kalshi_codes("nfl")
        >>> "JAC" in codes  # True (Kalshi code)
        >>> "JAX" in codes  # False (ESPN code, not in Kalshi set)
    """

    def __init__(self) -> None:
        """Initialize empty registry. Call load() before use."""
        self._kalshi_to_espn: dict[str, dict[str, str]] = {}
        self._kalshi_codes: dict[str, set[str]] = {}
        self._loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Whether the registry has been loaded from the database."""
        return self._loaded

    def load(self, league: str | None = None) -> None:
        """Load team codes from DB into in-memory cache.

        Queries the teams table for all teams (or a specific league) and
        builds the mapping dictionaries. Safe to call multiple times
        (replaces existing data for reloaded leagues).

        Args:
            league: Optional league filter. If None, loads all leagues.

        Example:
            >>> registry = TeamCodeRegistry()
            >>> registry.load()           # Load all leagues
            >>> registry.load("nfl")      # Refresh NFL only
        """
        # Import here to avoid circular imports at module level
        from precog.database.crud_operations import get_teams_with_kalshi_codes

        teams = get_teams_with_kalshi_codes(league=league)
        self._build_cache(teams, league)
        self._loaded = True

        total_codes = sum(len(codes) for codes in self._kalshi_codes.values())
        logger.info(
            "TeamCodeRegistry loaded: %d leagues, %d total codes",
            len(self._kalshi_codes),
            total_codes,
        )

    def load_from_data(self, teams: list[dict[str, Any]]) -> None:
        """Load registry from pre-fetched team data (for testing).

        Args:
            teams: List of team dicts with keys: team_code, league,
                   kalshi_team_code (optional).

        Example:
            >>> registry = TeamCodeRegistry()
            >>> registry.load_from_data([
            ...     {"team_code": "JAX", "league": "nfl", "kalshi_team_code": "JAC"},
            ...     {"team_code": "KC", "league": "nfl", "kalshi_team_code": None},
            ... ])
        """
        self._build_cache(teams, league=None)
        self._loaded = True

    def _build_cache(self, teams: list[dict[str, Any]], league: str | None) -> None:
        """Build internal cache from team data.

        Args:
            teams: List of team dicts from DB or test data.
            league: If provided, only clear/rebuild that league's data.
        """
        if league:
            # Clear only the specified league
            self._kalshi_to_espn.pop(league, None)
            self._kalshi_codes.pop(league, None)
        else:
            # Clear all
            self._kalshi_to_espn.clear()
            self._kalshi_codes.clear()

        for team in teams:
            team_code = team.get("team_code", "")
            team_league = team.get("league", "")
            kalshi_code = team.get("kalshi_team_code")

            if not team_code or not team_league:
                continue

            # Initialize league dicts if needed
            if team_league not in self._kalshi_to_espn:
                self._kalshi_to_espn[team_league] = {}
                self._kalshi_codes[team_league] = set()

            if kalshi_code:
                # Explicit Kalshi code differs from ESPN code
                upper_kalshi = kalshi_code.upper()
                self._kalshi_to_espn[team_league][upper_kalshi] = team_code
                self._kalshi_codes[team_league].add(upper_kalshi)
            else:
                # Kalshi code is same as ESPN code (most teams)
                upper_code = team_code.upper()
                self._kalshi_to_espn[team_league][upper_code] = team_code
                self._kalshi_codes[team_league].add(upper_code)

    def resolve_kalshi_to_espn(self, kalshi_code: str, league: str) -> str | None:
        """Resolve a Kalshi team code to the canonical ESPN/DB team_code.

        Args:
            kalshi_code: Team code as used by Kalshi (e.g., "JAC", "HOU")
            league: League code (e.g., "nfl", "nba")

        Returns:
            Canonical team_code from the teams table, or None if unknown.

        Example:
            >>> registry.resolve_kalshi_to_espn("JAC", "nfl")
            'JAX'
            >>> registry.resolve_kalshi_to_espn("HOU", "nfl")
            'HOU'
            >>> registry.resolve_kalshi_to_espn("ZZZ", "nfl")
            None
        """
        league_map = self._kalshi_to_espn.get(league, {})
        return league_map.get(kalshi_code.upper())

    def get_kalshi_codes(self, league: str) -> set[str]:
        """Get all known Kalshi codes for a league.

        Used by the ticker parser to determine valid split points when
        parsing concatenated team codes from event tickers.

        Args:
            league: League code (e.g., "nfl", "nba")

        Returns:
            Set of uppercase Kalshi team codes. Empty set if league unknown.

        Example:
            >>> codes = registry.get_kalshi_codes("nfl")
            >>> "JAC" in codes   # True (Kalshi's code for Jacksonville)
            >>> "JAX" in codes   # False (ESPN's code, not in Kalshi set)
            >>> "HOU" in codes   # True (same on both platforms)
        """
        return self._kalshi_codes.get(league, set())
