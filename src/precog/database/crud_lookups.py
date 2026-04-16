"""Cached lookup helpers for the `sports` and `leagues` lookup tables.

These tables are populated by migration 0060 (#738 A1) and hold at most 6 + 11
rows.  Since the values are effectively immutable during a process lifetime
(new sports/leagues only land via migration or a deliberate INSERT), we cache
the full maps at first use and serve subsequent lookups from memory.

Consumers (CRUD dual-write callers) should call:

    sport_id = get_sport_id("football")   # returns int, raises on unknown
    league_id = get_league_id("nfl")      # returns int, raises on unknown

... or the *`_or_none` variants if the caller wants to tolerate missing keys
(e.g., when the incoming VARCHAR value predates the lookup seed).

The module is thread-safe for read-after-first-populate: cache population is
gated by a single lock, and subsequent reads are dict lookups only.

Related:
  * Migration 0060 (#738 A1) — creates the tables and seeds 6 + 11 rows.
  * `crud_teams.py`, `crud_game_states.py`, `crud_historical.py`, `crud_elo.py`
    — primary consumers via dual-write pattern.
  * Design memo: `memory/design_738_lookup_tables.md`
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from .connection import fetch_all

logger = logging.getLogger(__name__)


# =============================================================================
# CACHE STATE
# =============================================================================
# Populated lazily on first lookup, then re-used for the process lifetime.
# Call `invalidate_cache()` from tests to force a refresh between scenarios.

_sport_key_to_id: dict[str, int] | None = None
_league_key_to_id: dict[str, int] | None = None
_league_key_to_sport_id: dict[str, int] | None = None
_cache_lock = threading.Lock()


def _populate_cache() -> None:
    """Load the sports + leagues tables into the module-level caches.

    Safe to call multiple times; re-runs overwrite prior state.  Callers
    should hold `_cache_lock` or be okay with the race (the worst-case
    outcome is a double-load, not incorrect data).

    If the lookup tables do not yet exist (e.g., a test DB that has not
    been upgraded past migration 0060), the cache is populated with empty
    dicts.  All `*_or_none` helpers then return None and the `_direct`
    variants raise KeyError — exactly the same surface as if a caller
    passes an unknown key.  This keeps unit tests that mock `get_cursor`
    but not `fetch_all` from blowing up on import-time DB access.
    """
    global _sport_key_to_id, _league_key_to_id, _league_key_to_sport_id
    try:
        sport_rows: list[dict[str, Any]] = fetch_all("SELECT id, sport_key FROM sports")
        league_rows: list[dict[str, Any]] = fetch_all(
            "SELECT id, league_key, sport_id FROM leagues"
        )
    except Exception as exc:
        # UndefinedTable (pre-0060 DB), connection errors, etc. — degrade
        # gracefully to empty cache.  Dual-write callers use the
        # `*_or_none` variants, which return None on missing keys, so the
        # INSERT still succeeds with NULL in the new FK column.  A2 will
        # enforce NOT NULL and surface any lingering gap.
        logger.debug(
            "Lookup cache could not be populated (likely pre-0060 schema): %s",
            exc,
        )
        _sport_key_to_id = {}
        _league_key_to_id = {}
        _league_key_to_sport_id = {}
        return
    _sport_key_to_id = {row["sport_key"]: int(row["id"]) for row in sport_rows}
    _league_key_to_id = {row["league_key"]: int(row["id"]) for row in league_rows}
    _league_key_to_sport_id = {row["league_key"]: int(row["sport_id"]) for row in league_rows}
    logger.debug(
        "Lookup cache populated: %d sports, %d leagues",
        len(_sport_key_to_id),
        len(_league_key_to_id),
    )


def _ensure_cache() -> None:
    """Populate the cache on first call; no-op thereafter."""
    if _sport_key_to_id is not None and _league_key_to_id is not None:
        return
    with _cache_lock:
        if _sport_key_to_id is None or _league_key_to_id is None:
            _populate_cache()


def invalidate_cache() -> None:
    """Force the next lookup to re-fetch from the database.

    Use from test fixtures that mutate lookup-table contents between scenarios.
    Production code does not need this — the tables are effectively immutable.
    """
    global _sport_key_to_id, _league_key_to_id, _league_key_to_sport_id
    with _cache_lock:
        _sport_key_to_id = None
        _league_key_to_id = None
        _league_key_to_sport_id = None


# =============================================================================
# PUBLIC LOOKUP API
# =============================================================================


def get_sport_id(sport_key: str) -> int:
    """Resolve a sport_key string to its sports.id FK value.

    Args:
        sport_key: Sport key string ('football', 'basketball', 'hockey',
            'baseball', 'soccer', 'mma').

    Returns:
        The sports.id integer for that key.

    Raises:
        KeyError: If sport_key is not present in the `sports` table.
            Callers that want to tolerate unknown keys should use
            `get_sport_id_or_none()` instead.

    Example:
        >>> get_sport_id("football")
        1
    """
    _ensure_cache()
    assert _sport_key_to_id is not None  # _ensure_cache() guarantees this
    try:
        return _sport_key_to_id[sport_key]
    except KeyError:
        raise KeyError(
            f"Unknown sport_key: {sport_key!r}. Valid keys: {sorted(_sport_key_to_id.keys())!r}"
        ) from None


def get_sport_id_or_none(sport_key: str | None) -> int | None:
    """Same as `get_sport_id` but returns None for unknown or None input.

    Useful during the A1 -> A2 window where CRUD callers may legitimately
    pass `sport=None` (column is still nullable) or pass a league code into
    the `sport` slot (the dual-write then populates only the VARCHAR column,
    not the FK).
    """
    if sport_key is None:
        return None
    _ensure_cache()
    assert _sport_key_to_id is not None
    return _sport_key_to_id.get(sport_key)


def get_league_id(league_key: str) -> int:
    """Resolve a league_key string to its leagues.id FK value.

    Args:
        league_key: League key string ('nfl', 'ncaaf', 'nba', 'ncaab',
            'ncaaw', 'wnba', 'nhl', 'mlb', 'mls', 'soccer', 'ufc').

    Returns:
        The leagues.id integer for that key.

    Raises:
        KeyError: If league_key is not present in the `leagues` table.
    """
    _ensure_cache()
    assert _league_key_to_id is not None
    try:
        return _league_key_to_id[league_key]
    except KeyError:
        raise KeyError(
            f"Unknown league_key: {league_key!r}. Valid keys: {sorted(_league_key_to_id.keys())!r}"
        ) from None


def get_league_id_or_none(league_key: str | None) -> int | None:
    """Same as `get_league_id` but returns None for unknown or None input."""
    if league_key is None:
        return None
    _ensure_cache()
    assert _league_key_to_id is not None
    return _league_key_to_id.get(league_key)


def get_sport_id_from_league(league_key: str) -> int:
    """Resolve a league_key to its parent sports.id (via the leagues table).

    Used in the dual-write path for tables like `historical_stats` where the
    VARCHAR `sport` column actually holds league codes ('nfl', 'ncaaf', ...)
    but the new FK column we're populating is `sport_id`.

    Args:
        league_key: League key string.

    Returns:
        The `sports.id` integer for the league's parent sport.

    Raises:
        KeyError: If league_key is not present in the `leagues` table.
    """
    _ensure_cache()
    assert _league_key_to_sport_id is not None
    try:
        return _league_key_to_sport_id[league_key]
    except KeyError:
        raise KeyError(
            f"Unknown league_key: {league_key!r}. "
            f"Valid keys: {sorted(_league_key_to_sport_id.keys())!r}"
        ) from None


def get_sport_id_from_league_or_none(league_key: str | None) -> int | None:
    """Same as `get_sport_id_from_league` but returns None for unknown input."""
    if league_key is None:
        return None
    _ensure_cache()
    assert _league_key_to_sport_id is not None
    return _league_key_to_sport_id.get(league_key)


def resolve_sport_id_for_mixed_value(value: str | None) -> int | None:
    """Handle the `game_odds.sport` mixed-convention case.

    The `game_odds.sport` VARCHAR column historically accepts EITHER a sport
    name ('football', 'basketball') OR a league code ('nfl', 'nba') due to
    the expanded CHECK constraint in migration 0048.  This helper resolves
    either shape to a canonical `sports.id`:

      1. First try direct `sport_key` lookup.
      2. Fall back to `league_key` -> `leagues.sport_id`.
      3. Return None if the value matches neither.

    Returns None (rather than raising) for unknown values so that dual-write
    callers don't break on a value that slipped past the backfill.  The
    backfill itself enforces zero-NULL at migration time, but incremental
    writes during the A1 -> A2 window should be permissive.
    """
    if value is None:
        return None
    _ensure_cache()
    assert _sport_key_to_id is not None
    assert _league_key_to_sport_id is not None
    if value in _sport_key_to_id:
        return _sport_key_to_id[value]
    if value in _league_key_to_sport_id:
        return _league_key_to_sport_id[value]
    return None
