"""
Orchestrates matching Kalshi events to ESPN games.

The matcher combines ticker parsing (extracting team codes and dates from
Kalshi event tickers) with game lookups (finding the corresponding game in
the games dimension table) to populate the events.game_id FK.

Matching Phases:
    Phase 1 (this module): Parse event_ticker for date + team codes
    Phase 2 (TODO): Parse event title for team names (fallback)
    Phase 3 (batch): backfill_unlinked_events() for historical data

Flow:
    1. Parse ticker -> league, date, away_code, home_code (Kalshi codes)
    2. Resolve Kalshi codes to ESPN codes via TeamCodeRegistry
    3. Look up sport from LEAGUE_SPORT_CATEGORY mapping
    4. Query games table by (sport, game_date, home_team_code, away_team_code)
    5. Return games.id or None

Educational Note:
    The games table natural key is (sport, game_date, home_team_code,
    away_team_code) where sport is "football"/"basketball"/etc. and
    team codes are ESPN codes. The matching module bridges the gap between
    Kalshi's league-specific codes and the games table's sport-level codes.

Related:
    - Issue #462: Event-to-game matching
    - Migration 0038: events.game_id FK to games(id)
    - crud_operations.find_game_by_matchup(): Game lookup
    - crud_operations.LEAGUE_SPORT_CATEGORY: League-to-sport mapping
"""

import logging
from datetime import date
from enum import Enum

from precog.matching.team_code_registry import TeamCodeRegistry
from precog.matching.ticker_parser import ParsedTicker, parse_event_ticker

logger = logging.getLogger(__name__)


class MatchReason(str, Enum):
    """Categorized result of an event-to-game matching attempt.

    Used for production monitoring: operators can see why events fail
    to match (parse failures vs missing codes vs no game in DB).

    Values:
        matched: Successfully matched event to a game.
        parse_fail: Could not parse the event ticker (non-sports, bad format).
        no_code: Parsed ticker but team code(s) not found in registry.
        no_game: Resolved team codes but no matching game found in DB.
    """

    MATCHED = "matched"
    PARSE_FAIL = "parse_fail"
    NO_CODE = "no_code"
    NO_GAME = "no_game"


class EventGameMatcher:
    """Matches Kalshi events to ESPN games.

    Attributes:
        registry: TeamCodeRegistry for resolving team codes.

    Usage:
        >>> matcher = EventGameMatcher()
        >>> matcher.registry.load()
        >>> game_id = matcher.match_event("KXNFLGAME-26JAN18HOUNE")
        >>> if game_id:
        ...     update_event_game_id(event_pk, game_id)

    Educational Note:
        The matcher uses dependency injection for the registry, making it
        testable without a database. In production, the registry is loaded
        from DB at poller startup. In tests, use load_from_data() with
        mock team data.
    """

    def __init__(self, registry: TeamCodeRegistry | None = None) -> None:
        """Initialize matcher with optional pre-configured registry.

        Args:
            registry: Pre-configured TeamCodeRegistry. If None, creates
                      a new empty one (caller must call registry.load()
                      before matching).
        """
        self.registry = registry or TeamCodeRegistry()

    def match_event(self, event_ticker: str, title: str | None = None) -> int | None:
        """Try to match an event to a game. Returns games.id or None.

        Phase 1: Parse event_ticker for date + team codes, look up game.
        Phase 2: If Phase 1 fails, parse title for team names (TODO).

        Args:
            event_ticker: Kalshi event ticker (e.g., "KXNFLGAME-26JAN18HOUNE")
            title: Optional event title for fallback parsing (not yet implemented)

        Returns:
            games.id (integer) if a matching game is found, None otherwise.

        Example:
            >>> matcher = EventGameMatcher()
            >>> matcher.registry.load()
            >>> game_id = matcher.match_event("KXNFLGAME-26JAN18HOUNE")
            >>> game_id  # e.g., 42 or None
        """
        # Phase 1: Ticker-based matching
        game_id = self._match_via_ticker(event_ticker)
        if game_id is not None:
            return game_id

        # Phase 2: Title-based fallback (TODO — stub)
        if title:
            game_id = self._match_via_title(title, event_ticker)
            if game_id is not None:
                return game_id

        return None

    def match_event_with_reason(
        self, event_ticker: str, title: str | None = None
    ) -> tuple[int | None, MatchReason]:
        """Try to match an event to a game, returning the reason for the outcome.

        Same logic as match_event() but returns a (game_id, reason) tuple
        so callers can categorize failures for monitoring stats.

        Args:
            event_ticker: Kalshi event ticker (e.g., "KXNFLGAME-26JAN18HOUNE")
            title: Optional event title for fallback parsing (not yet implemented)

        Returns:
            Tuple of (games.id or None, MatchReason).

        Example:
            >>> matcher = EventGameMatcher()
            >>> matcher.registry.load()
            >>> game_id, reason = matcher.match_event_with_reason("KXNFLGAME-26JAN18HOUNE")
            >>> reason  # MatchReason.MATCHED or MatchReason.NO_GAME, etc.
        """
        game_id, reason = self._match_via_ticker_with_reason(event_ticker)
        if game_id is not None:
            return game_id, MatchReason.MATCHED

        # If ticker parse succeeded but no game, reason is already set
        if reason != MatchReason.PARSE_FAIL:
            return None, reason

        # Phase 2: Title-based fallback (TODO — stub)
        if title:
            game_id = self._match_via_title(title, event_ticker)
            if game_id is not None:
                return game_id, MatchReason.MATCHED

        return None, reason

    def _match_via_ticker_with_reason(self, event_ticker: str) -> tuple[int | None, MatchReason]:
        """Attempt to match using parsed ticker data, returning reason.

        Args:
            event_ticker: Kalshi event ticker string.

        Returns:
            Tuple of (games.id or None, MatchReason).
        """
        parsed = self._parse_ticker(event_ticker)
        if parsed is None:
            logger.debug("Could not parse ticker: %s", event_ticker)
            return None, MatchReason.PARSE_FAIL

        away_espn = self.registry.resolve_kalshi_to_espn(parsed.away_team_code, parsed.league)
        home_espn = self.registry.resolve_kalshi_to_espn(parsed.home_team_code, parsed.league)

        if away_espn is None or home_espn is None:
            logger.debug(
                "Could not resolve team codes for %s: away=%s->%s, home=%s->%s",
                event_ticker,
                parsed.away_team_code,
                away_espn,
                parsed.home_team_code,
                home_espn,
            )
            # Track which codes failed so the registry can self-heal
            if away_espn is None:
                self.registry.record_unknown_code(parsed.away_team_code, parsed.league)
            if home_espn is None:
                self.registry.record_unknown_code(parsed.home_team_code, parsed.league)
            return None, MatchReason.NO_CODE

        game_id = self._find_game(parsed.league, parsed.game_date, home_espn, away_espn)
        if game_id is None:
            return None, MatchReason.NO_GAME
        return game_id, MatchReason.MATCHED

    def _match_via_ticker(self, event_ticker: str) -> int | None:
        """Attempt to match using parsed ticker data.

        Delegates to _match_via_ticker_with_reason() and discards the reason.
        This ensures the backfill path also records unknown codes for
        self-healing (Brawne review finding #1, session 24).

        Args:
            event_ticker: Kalshi event ticker string.

        Returns:
            games.id or None.
        """
        game_id, _reason = self._match_via_ticker_with_reason(event_ticker)
        return game_id

    def _parse_ticker(self, event_ticker: str) -> ParsedTicker | None:
        """Parse ticker with league-appropriate valid codes.

        Extracts league from ticker first to select the correct code set,
        then re-parses with those codes for team splitting.

        Args:
            event_ticker: Kalshi event ticker string.

        Returns:
            ParsedTicker or None.
        """
        # First pass: parse without codes to extract league
        # We need the league to get the right code set
        from precog.matching.ticker_parser import _extract_league

        parts = event_ticker.split("-", 1)
        if len(parts) != 2:
            return None

        league = _extract_league(parts[0])
        if league is None:
            return None

        # Get valid codes for this league
        valid_codes = self.registry.get_kalshi_codes(league)
        if not valid_codes:
            logger.debug(
                "No valid codes in registry for league '%s' (ticker: %s)",
                league,
                event_ticker,
            )
            return None

        # Full parse with valid codes for team splitting
        return parse_event_ticker(event_ticker, valid_codes)

    def _match_via_title(self, _title: str, _event_ticker: str) -> int | None:
        """Attempt to match using event title text.

        TODO: Implement title-based matching as a fallback for tickers
        that can't be parsed (non-standard formats, ambiguous splits).

        Args:
            _title: Event title text (e.g., "Chiefs vs Seahawks - Jan 18")
            _event_ticker: Original ticker for logging context.

        Returns:
            games.id or None (always None until implemented).
        """
        # TODO(#462): Implement title-based fallback matching
        # Parse team names from title, resolve to codes, look up game
        return None

    def _find_game(
        self,
        league: str,
        game_date: date,
        home_team_code: str,
        away_team_code: str,
    ) -> int | None:
        """Look up a game in the games dimension table.

        Uses the CRUD function find_game_by_matchup() which queries by
        the natural key: (league, game_date, home_team_code, away_team_code).

        Args:
            league: League code (e.g., "nfl")
            game_date: Game date
            home_team_code: ESPN/canonical home team code
            away_team_code: ESPN/canonical away team code

        Returns:
            games.id or None.
        """
        from precog.database.crud_operations import find_game_by_matchup

        return find_game_by_matchup(
            league=league,
            game_date=game_date,
            home_team_code=home_team_code,
            away_team_code=away_team_code,
        )

    def backfill_unlinked_events(self, league: str | None = None) -> int:
        """Find events with game_id=NULL and attempt matching.

        Queries for unlinked sports events, attempts ticker-based matching
        for each, and updates events.game_id where matches are found.

        Args:
            league: Optional league filter. If None, processes all leagues.

        Returns:
            Count of newly linked events.

        Example:
            >>> matcher = EventGameMatcher()
            >>> matcher.registry.load()
            >>> linked = matcher.backfill_unlinked_events("nfl")
            >>> print(f"Linked {linked} events to games")
        """
        from precog.database.crud_operations import (
            find_unlinked_sports_events,
            update_event_game_id,
        )

        unlinked = find_unlinked_sports_events(league=league)
        linked_count = 0

        for event in unlinked:
            event_ticker = event.get("event_id", "")
            title = event.get("title")
            event_id = event.get("id")

            if not event_ticker or event_id is None:
                continue

            game_id = self.match_event(event_ticker, title=title)
            if game_id is not None:
                success = update_event_game_id(event_id, game_id)
                if success:
                    linked_count += 1
                    logger.info(
                        "Linked event %s (id=%d) to game_id=%d",
                        event_ticker,
                        event_id,
                        game_id,
                    )

        logger.info(
            "Backfill complete: %d/%d events linked (league=%s)",
            linked_count,
            len(unlinked),
            league or "all",
        )
        return linked_count
