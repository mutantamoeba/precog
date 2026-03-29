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
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# Classification priority for code collision disambiguation.
# FBS/FCS win over D2/D3/NULL because Kalshi only trades FBS/FCS markets.
# Higher number = higher priority.
CLASSIFICATION_PRIORITY: dict[str | None, int] = {
    "fbs": 5,
    "fcs": 4,
    "professional": 3,
    "d1": 2,
    "d2": 1,
    "d3": 1,
    None: 0,
}


class TeamCodeRegistry:
    """Cache of team code mappings for fast lookup during matching.

    Attributes:
        _kalshi_to_espn: dict[league, dict[kalshi_code, espn_team_code]]
            Maps Kalshi team codes to canonical ESPN team codes per league.
        _kalshi_codes: dict[league, set[str]]
            All valid Kalshi codes per league (for ticker splitting).
        _classification: dict[league, dict[kalshi_code, str|None]]
            Tracks classification per code for disambiguation logging.
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
        self._classification: dict[str, dict[str, str | None]] = {}
        self._loaded: bool = False
        self._last_loaded_at: datetime | None = None
        self._unknown_codes_seen: set[str] = set()

    @property
    def is_loaded(self) -> bool:
        """Whether the registry has been loaded from the database."""
        return self._loaded

    @property
    def last_loaded_at(self) -> datetime | None:
        """UTC timestamp of the last successful load. None if never loaded."""
        return self._last_loaded_at

    @property
    def unknown_codes_seen(self) -> set[str]:
        """Set of team codes that failed lookup since last load.

        Format: "CODE:league" (e.g., "ZZZ:nfl"). Cleared on each reload.
        Used by the poller to decide when a registry refresh might help.
        """
        return self._unknown_codes_seen

    def needs_refresh(self, max_age_seconds: int = 3600) -> bool:
        """Check whether the registry should be reloaded.

        Returns True if:
        - Registry has never been loaded
        - Registry is older than max_age_seconds
        - Unknown codes have accumulated (possible new teams)

        Args:
            max_age_seconds: Maximum age in seconds before a refresh is
                recommended. Default: 3600 (1 hour).

        Returns:
            True if a refresh is recommended.

        Example:
            >>> registry = TeamCodeRegistry()
            >>> registry.needs_refresh()  # True (never loaded)
            >>> registry.load()
            >>> registry.needs_refresh(max_age_seconds=3600)  # False (just loaded)
        """
        if not self._loaded or self._last_loaded_at is None:
            return True

        age = (datetime.now(UTC) - self._last_loaded_at).total_seconds()
        if age > max_age_seconds:
            return True

        # If we've seen unknown codes, a refresh might resolve them
        # (new teams added to DB since last load)
        return bool(self._unknown_codes_seen)

    def record_unknown_code(self, code: str, league: str) -> None:
        """Record a team code that failed lookup for monitoring.

        Args:
            code: The Kalshi team code that was not found.
            league: The league context for the lookup.
        """
        self._unknown_codes_seen.add(f"{code.upper()}:{league}")

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
        collisions = self._build_cache(teams, league)
        self._loaded = True
        self._last_loaded_at = datetime.now(UTC)
        self._unknown_codes_seen.clear()

        total_codes = sum(len(codes) for codes in self._kalshi_codes.values())
        if collisions:
            logger.info(
                "TeamCodeRegistry loaded: %d leagues, %d total codes (%d code collisions resolved, see DEBUG for details)",
                len(self._kalshi_codes),
                total_codes,
                collisions,
            )
        else:
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
        self._last_loaded_at = datetime.now(UTC)
        self._unknown_codes_seen.clear()

    def _build_cache(self, teams: list[dict[str, Any]], league: str | None) -> int:
        """Build internal cache from team data.

        When multiple teams share the same Kalshi code within a league
        (common in college sports), the team with the higher classification
        priority wins. FBS/FCS are preferred because Kalshi only trades
        those divisions.

        Args:
            teams: List of team dicts from DB or test data.
            league: If provided, only clear/rebuild that league's data.

        Returns:
            Number of code collisions resolved.
        """
        collisions = 0
        if league:
            # Clear only the specified league
            self._kalshi_to_espn.pop(league, None)
            self._kalshi_codes.pop(league, None)
            self._classification.pop(league, None)
        else:
            # Clear all
            self._kalshi_to_espn.clear()
            self._kalshi_codes.clear()
            self._classification.clear()

        for team in teams:
            team_code = team.get("team_code", "")
            team_league = team.get("league", "")
            kalshi_code = team.get("kalshi_team_code")
            classification = team.get("classification")

            if not team_code or not team_league:
                continue

            # Initialize league dicts if needed
            if team_league not in self._kalshi_to_espn:
                self._kalshi_to_espn[team_league] = {}
                self._kalshi_codes[team_league] = set()
                self._classification[team_league] = {}

            # Determine the effective Kalshi code for this team
            effective_code = kalshi_code.upper() if kalshi_code else team_code.upper()

            # Check for code collision
            existing_cls = self._classification[team_league].get(effective_code)
            new_priority = CLASSIFICATION_PRIORITY.get(classification, 0)
            existing_priority = CLASSIFICATION_PRIORITY.get(existing_cls, 0)

            if effective_code in self._kalshi_to_espn[team_league]:
                if new_priority <= existing_priority:
                    # Existing team has equal or higher priority — skip
                    logger.debug(
                        "Code collision: %s:%s — keeping %s (%s) over %s (%s)",
                        team_league,
                        effective_code,
                        self._kalshi_to_espn[team_league][effective_code],
                        existing_cls or "unclassified",
                        team_code,
                        classification or "unclassified",
                    )
                    continue
                # New team has higher priority — replace
                collisions += 1
                old_code = self._kalshi_to_espn[team_league][effective_code]
                logger.debug(
                    "Code collision resolved: %s:%s — %s (%s) replaces %s (%s)",
                    team_league,
                    effective_code,
                    team_code,
                    classification or "unclassified",
                    old_code,
                    existing_cls or "unclassified",
                )

            self._kalshi_to_espn[team_league][effective_code] = team_code
            self._kalshi_codes[team_league].add(effective_code)
            self._classification[team_league][effective_code] = classification

        return collisions

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
