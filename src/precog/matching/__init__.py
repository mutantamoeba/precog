"""
Event-to-game matching module for Precog.

Matches Kalshi prediction market events to ESPN games by parsing event
tickers for team codes and game dates, then looking up the corresponding
game in the games dimension table.

Public API:
    - ParsedTicker: Structured result from ticker parsing
    - parse_event_ticker(): Parse a Kalshi event ticker into components
    - TeamCodeRegistry: In-memory cache of team code mappings
    - EventGameMatcher: Orchestrates the full matching flow

Example:
    >>> from precog.matching import EventGameMatcher
    >>> matcher = EventGameMatcher()
    >>> matcher.registry.load()
    >>> game_id = matcher.match_event("KXNFLGAME-26JAN18HOUNE")

Related:
    - Issue #462: Event-to-game matching
    - Migration 0038: events.game_id FK to games(id)
    - Migration 0041: teams.kalshi_team_code column
"""

from precog.matching.event_game_matcher import EventGameMatcher
from precog.matching.team_code_registry import TeamCodeRegistry
from precog.matching.ticker_parser import ParsedTicker, parse_event_ticker

__all__ = [
    "EventGameMatcher",
    "ParsedTicker",
    "TeamCodeRegistry",
    "parse_event_ticker",
]
