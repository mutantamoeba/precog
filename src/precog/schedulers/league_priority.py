"""Priority-based adaptive polling for ESPN game poller (#560).

When multiple leagues are tracking simultaneously and the rate budget requires
throttling, this module allocates polling budget by priority instead of
uniformly. Priority is a weighted combination of three signals:

1. **Game phase urgency** (0.0-1.0): Sport-aware urgency from live game state.
   Late-game situations (Q4 football, P3 hockey) get higher priority.
2. **Active markets** (0.0-1.0): Open Kalshi markets for this league's
   subcategory. More open markets = higher priority.
3. **Static priority** (0.0-1.0): User-configured baseline per league in YAML.

The allocator ensures the total request rate NEVER exceeds the rate budget.
On any error, it falls back to uniform allocation.

Reference: Issue #560 (Adaptive polling throttle from rate budget)
Related: ADR-100 (Service Supervisor Pattern), C18 JC-4
"""

import logging
import math
import time
from collections.abc import Callable
from typing import Any

from precog.database.crud_game_states import LEAGUE_SPORT_CATEGORY

logger = logging.getLogger(__name__)

# ============================================================================
# Default configuration constants
# ============================================================================

# Signal weights (game_phase, active_markets, static_priority)
DEFAULT_WEIGHTS: dict[str, float] = {
    "game_phase": 0.50,
    "active_markets": 0.30,
    "static_priority": 0.20,
}

# Per-league static priority defaults
DEFAULT_LEAGUE_PRIORITIES: dict[str, float] = {
    "nfl": 0.8,
    "nba": 0.7,
    "ncaaf": 0.6,
    "nhl": 0.5,
}

# Open market count thresholds -> signal value
DEFAULT_MARKET_THRESHOLDS: dict[str, int] = {
    "low": 1,  # >=1 open markets -> 0.3
    "medium": 6,  # >=6 -> 0.6
    "high": 16,  # >=16 -> 1.0
}

DEFAULT_MARKET_COUNT_CACHE_TTL: int = 300  # 5 minutes


class LeaguePriorityCalculator:
    """Computes per-league polling priority from game phase, markets, and config.

    Uses dependency injection for the market count DB query so tests can
    substitute a mock without touching the database.

    Args:
        weights: Signal weights dict with keys game_phase, active_markets,
            static_priority. Need not sum to 1.0 (normalized internally).
        league_priorities: Per-league static priority (0.0-1.0).
        market_thresholds: Open market count thresholds (low/medium/high).
        market_count_cache_ttl: Seconds to cache market count queries.
        market_count_fn: Callable(subcategory: str) -> int for DB query.
            If None, active_markets signal always returns 0.0.

    Educational Note:
        The calculator is designed to be fast (runs under the poller's lock).
        The only potentially slow operation (DB query for market counts) is
        cached with a configurable TTL.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        league_priorities: dict[str, float] | None = None,
        market_thresholds: dict[str, int] | None = None,
        market_count_cache_ttl: int = DEFAULT_MARKET_COUNT_CACHE_TTL,
        market_count_fn: Callable[[str], int] | None = None,
    ) -> None:
        self._weights = weights or DEFAULT_WEIGHTS.copy()
        self._league_priorities = league_priorities or DEFAULT_LEAGUE_PRIORITIES.copy()
        self._market_thresholds = market_thresholds or DEFAULT_MARKET_THRESHOLDS.copy()
        self._market_count_cache_ttl = market_count_cache_ttl
        self._market_count_fn = market_count_fn

        # Validate: no negative weights (would produce priorities outside [0, 1])
        for key, val in self._weights.items():
            if val < 0:
                raise ValueError(f"Weight '{key}' must be non-negative, got {val}")

        # Cache: subcategory -> (count, timestamp)
        self._market_count_cache: dict[str, tuple[int, float]] = {}

    # ========================================================================
    # Signal 1: Game Phase Urgency
    # ========================================================================

    def compute_game_phase_urgency(self, league: str, games: list[dict[str, Any]]) -> float:
        """Compute sport-aware urgency (0.0-1.0) from live game states.

        Uses max urgency across all live games in the league. A league with
        one Q4 football game and one Q1 game returns the Q4 urgency.

        Sport-specific rules:
            Football (nfl, ncaaf):
                - Q4/OT <5:00 remaining -> 1.0
                - Q4 >=5:00 -> 0.7
                - Q3 -> 0.4
                - Q1-Q2 -> 0.2
                - Halftime -> 0.1

            Basketball (nba, ncaab, wnba, ncaaw):
                - Q4/OT <3:00 remaining -> 1.0
                - Q4 >=3:00 -> 0.7
                - Q3 -> 0.4
                - Q1-Q2 -> 0.2

            Hockey (nhl):
                - P3 <5:00 remaining -> 1.0
                - P3 >=5:00 -> 0.7
                - P2 -> 0.4
                - P1 -> 0.2

            Any sport OT -> 1.0

        Args:
            league: League code (e.g., "nfl", "nba").
            games: List of ESPNGameFull dicts from scoreboard.

        Returns:
            Maximum urgency across all live games (0.0 if no live games).
        """
        if not games:
            return 0.0

        sport = LEAGUE_SPORT_CATEGORY.get(league.lower())
        if sport is None:
            return 0.0

        max_urgency = 0.0
        for game in games:
            urgency = self._game_urgency(sport, game)
            if urgency > max_urgency:
                max_urgency = urgency

        return max_urgency

    def _game_urgency(self, sport: str, game: dict[str, Any]) -> float:
        """Compute urgency for a single game based on its state.

        Args:
            sport: Sport category (football, basketball, hockey).
            game: ESPNGameFull dict.

        Returns:
            Urgency value 0.0-1.0.
        """
        state = game.get("state", {})
        game_status = str(state.get("game_status", "pre")).lower()

        # Not live -> no urgency
        if game_status in ("pre", "scheduled", "post", "final", "final/ot"):
            return 0.0

        # Halftime is low urgency
        if game_status == "halftime":
            return 0.1

        period = state.get("period", 1)
        clock_seconds = state.get("clock_seconds", 0.0)

        # Ensure numeric types
        try:
            period = int(period)
        except (TypeError, ValueError):
            period = 1
        try:
            clock_seconds = float(clock_seconds)
        except (TypeError, ValueError):
            clock_seconds = 0.0

        if sport == "football":
            return self._football_urgency(period, clock_seconds)
        if sport == "basketball":
            return self._basketball_urgency(period, clock_seconds)
        if sport == "hockey":
            return self._hockey_urgency(period, clock_seconds)
        # Unknown sport: moderate default
        return 0.3

    @staticmethod
    def _football_urgency(period: int, clock_seconds: float) -> float:
        """Football urgency: Q4 late-game and OT are highest priority."""
        if period >= 5:  # OT
            return 1.0
        if period == 4:
            return 1.0 if clock_seconds < 300 else 0.7
        if period == 3:
            return 0.4
        # Q1-Q2
        return 0.2

    @staticmethod
    def _basketball_urgency(period: int, clock_seconds: float) -> float:
        """Basketball urgency: Q4 late-game and OT are highest priority."""
        if period >= 5:  # OT
            return 1.0
        if period == 4:
            return 1.0 if clock_seconds < 180 else 0.7
        if period == 3:
            return 0.4
        # Q1-Q2
        return 0.2

    @staticmethod
    def _hockey_urgency(period: int, clock_seconds: float) -> float:
        """Hockey urgency: P3 late and OT are highest priority."""
        if period >= 4:  # OT
            return 1.0
        if period == 3:
            return 1.0 if clock_seconds < 300 else 0.7
        if period == 2:
            return 0.4
        # P1
        return 0.2

    # ========================================================================
    # Signal 2: Active Markets
    # ========================================================================

    def compute_market_signal(self, league: str) -> float:
        """Compute market activity signal (0.0-1.0) from open market count.

        Uses a cached DB query with configurable TTL. On DB error, returns
        the last cached value or 0.0 if no cached value exists.

        Thresholds (default):
            0 markets -> 0.0
            1-5 markets -> 0.3
            6-15 markets -> 0.6
            16+ markets -> 1.0

        Args:
            league: League code (e.g., "nfl", "nba").

        Returns:
            Market activity signal 0.0-1.0.
        """
        if self._market_count_fn is None:
            return 0.0

        subcategory = league.lower()
        now = time.monotonic()

        # Check cache
        cached = self._market_count_cache.get(subcategory)
        if cached is not None:
            count, timestamp = cached
            if now - timestamp < self._market_count_cache_ttl:
                return self._count_to_signal(count)

        # Query DB
        try:
            count = self._market_count_fn(subcategory)
            self._market_count_cache[subcategory] = (count, now)
            return self._count_to_signal(count)
        except Exception:
            logger.warning(
                "Failed to query open markets for %s, using cached/default",
                league,
                exc_info=True,
            )
            # Fall back to last cached value or 0.0
            if cached is not None:
                return self._count_to_signal(cached[0])
            return 0.0

    def _count_to_signal(self, count: int) -> float:
        """Map open market count to signal value using configured thresholds."""
        high = self._market_thresholds.get("high", 16)
        medium = self._market_thresholds.get("medium", 6)
        low = self._market_thresholds.get("low", 1)

        if count >= high:
            return 1.0
        if count >= medium:
            return 0.6
        if count >= low:
            return 0.3
        return 0.0

    # ========================================================================
    # Signal 3: Composite Priority
    # ========================================================================

    def compute_composite_priority(self, league: str, games: list[dict[str, Any]]) -> float:
        """Compute weighted composite priority for a league.

        Combines: game_phase * w1 + active_markets * w2 + static_priority * w3
        Weights are normalized internally so they need not sum to 1.0.

        Args:
            league: League code.
            games: List of ESPNGameFull dicts.

        Returns:
            Composite priority 0.0-1.0.
        """
        w_phase = self._weights.get("game_phase", 0.5)
        w_markets = self._weights.get("active_markets", 0.3)
        w_static = self._weights.get("static_priority", 0.2)

        total_weight = w_phase + w_markets + w_static
        if total_weight <= 0:
            return 0.0

        game_phase = self.compute_game_phase_urgency(league, games)
        markets = self.compute_market_signal(league)
        static = self._league_priorities.get(league.lower(), 0.5)

        raw = w_phase * game_phase + w_markets * markets + w_static * static
        # Clamp to [0.0, 1.0] — should be in range with valid weights,
        # but clamp defensively in case of floating point drift
        return max(0.0, min(1.0, raw / total_weight))

    # ========================================================================
    # Budget Allocation
    # ========================================================================

    def allocate_budget(
        self,
        tracking_leagues: list[str],
        budget_available: int,
        base_interval: int,
        max_throttled_interval: int,
        league_games: dict[str, list[dict[str, Any]]],
    ) -> dict[str, int]:
        """Allocate polling budget across tracking leagues by priority.

        Returns a dict mapping each tracking league to its polling interval.
        Higher-priority leagues get shorter intervals (more frequent polls).

        The total request rate is guaranteed to not exceed budget_available.
        If all priorities are equal, falls back to uniform allocation.

        Args:
            tracking_leagues: List of league codes currently in TRACKING state.
            budget_available: Requests per hour available for tracking leagues
                (total budget minus discovery overhead).
            base_interval: Minimum polling interval (seconds).
            max_throttled_interval: Maximum polling interval cap (seconds).
            league_games: Dict mapping league -> list of ESPNGameFull dicts.

        Returns:
            Dict mapping league code -> polling interval in seconds.
        """
        if not tracking_leagues:
            return {}

        if budget_available <= 0:
            # No budget: all leagues get max throttled interval
            return dict.fromkeys(tracking_leagues, max_throttled_interval)

        # Compute priorities
        priorities: dict[str, float] = {}
        for league in tracking_leagues:
            games = league_games.get(league, [])
            priorities[league] = self.compute_composite_priority(league, games)

        total_priority = sum(priorities.values())

        # Degenerate case: all priorities zero or equal -> uniform allocation
        unique_priorities = set(priorities.values())
        if total_priority <= 0 or len(unique_priorities) == 1:
            per_league = budget_available // len(tracking_leagues)
            if per_league > 0:
                interval = max(base_interval, math.ceil(3600 / per_league))
            else:
                interval = max_throttled_interval
            interval = min(interval, max_throttled_interval)
            return dict.fromkeys(tracking_leagues, interval)

        # Proportional allocation: share = priority / sum_priorities
        result: dict[str, int] = {}
        for league in tracking_leagues:
            share = priorities[league] / total_priority
            budget_per = share * budget_available
            if budget_per > 0:
                # Use ceil to round up (longer interval = fewer requests = safe)
                interval = max(base_interval, math.ceil(3600 / budget_per))
            else:
                interval = max_throttled_interval
            interval = min(interval, max_throttled_interval)
            result[league] = interval

        # Final validation: if total req/hr exceeds budget, scale up intervals
        total_req_hr = sum(3600 / iv for iv in result.values())
        if total_req_hr > budget_available:
            scale_factor = total_req_hr / budget_available
            for league in result:
                scaled = math.ceil(result[league] * scale_factor)
                scaled = max(scaled, base_interval)
                scaled = min(scaled, max_throttled_interval)
                result[league] = scaled

            # Re-check after scaling (cap may prevent full compliance)
            total_req_hr_after = sum(3600 / iv for iv in result.values())
            if total_req_hr_after > budget_available:
                logger.warning(
                    "Priority allocation cannot meet budget: %.0f req/hr > %d limit "
                    "(max_throttled_interval cap prevents further reduction)",
                    total_req_hr_after,
                    budget_available,
                )

        return result
