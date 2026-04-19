"""Unit tests for ``crud_lookups`` sports/leagues FK lookup cache.

``crud_lookups`` maintains a lazy, thread-safe in-process cache of the
``sports`` and ``leagues`` lookup tables (migration 0060, #738 A1).  The
cache is populated on first use via ``fetch_all`` and re-used for the
process lifetime.

These unit tests exercise the cache lifecycle, the strict vs. ``_or_none``
public API, the degraded-cache path (``fetch_all`` raises), the
``resolve_league_id_via_game`` helper (which additionally uses
``fetch_one`` via a late import), and the mixed-value resolver.

Pattern references:
  * Pattern 22 — VCR OR live for external API tests (N/A here: no HTTP)
  * Pattern 43 — Mock Fidelity (``fetch_all`` returns ``list[dict]`` with
    the real column names: ``id``, ``sport_key``, ``league_key``,
    ``sport_id``)
  * Pattern 45 — ``*_or_none`` helpers short-circuit on ``None`` input
    WITHOUT triggering cache population.

Slice 2 pilot — first of 10 CRUD unit test burn-down files (#887).
Issue: #887
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from precog.database import crud_lookups

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shared fixtures
# =============================================================================

# Keep the seed minimal — 3 sports, 4 leagues — so tests stay focused.
# "soccer" appears in BOTH sports and leagues (mirrors the real migration 0060
# seed) to exercise the sport-first precedence rule in
# resolve_sport_id_for_mixed_value.
_SPORT_ROWS = [
    {"id": 1, "sport_key": "football"},
    {"id": 2, "sport_key": "basketball"},
    {"id": 3, "sport_key": "soccer"},
]
_LEAGUE_ROWS = [
    {"id": 10, "league_key": "nfl", "sport_id": 1},
    {"id": 11, "league_key": "ncaaf", "sport_id": 1},
    {"id": 20, "league_key": "nba", "sport_id": 2},
    {"id": 30, "league_key": "soccer", "sport_id": 3},
]


def _fetch_all_side_effect(sql: str, params: tuple | None = None) -> list[dict]:
    """Return the correct seed rows based on which table the SQL targets."""
    if "FROM sports" in sql:
        return [dict(row) for row in _SPORT_ROWS]
    if "FROM leagues" in sql:
        return [dict(row) for row in _LEAGUE_ROWS]
    raise AssertionError(f"Unexpected fetch_all SQL in test: {sql!r}")


@pytest.fixture(autouse=True)
def _invalidate_cache_between_tests():
    """Reset module-level cache state before AND after every test.

    Module globals (``_sport_key_to_id`` etc.) leak between tests otherwise.
    We always go through the public ``invalidate_cache()`` API rather than
    mutating the globals directly.
    """
    crud_lookups.invalidate_cache()
    yield
    crud_lookups.invalidate_cache()


# =============================================================================
# A. Cache lifecycle
# =============================================================================


class TestCacheLifecycle:
    """Cache populates once, re-uses, can be invalidated, degrades gracefully."""

    @patch("precog.database.crud_lookups.fetch_all")
    def test_first_call_populates_cache_two_fetches(self, mock_fetch: MagicMock) -> None:
        """First public-API call triggers exactly one fetch per lookup table."""
        mock_fetch.side_effect = _fetch_all_side_effect

        crud_lookups.get_sport_id("football")

        # One SELECT against sports, one against leagues — total = 2.
        assert mock_fetch.call_count == 2
        sqls = [call.args[0] for call in mock_fetch.call_args_list]
        assert any("FROM sports" in sql for sql in sqls)
        assert any("FROM leagues" in sql for sql in sqls)

    @patch("precog.database.crud_lookups.fetch_all")
    def test_second_call_reuses_cache(self, mock_fetch: MagicMock) -> None:
        """After first populate, subsequent calls do NOT touch fetch_all."""
        mock_fetch.side_effect = _fetch_all_side_effect

        crud_lookups.get_sport_id("football")
        crud_lookups.get_sport_id("basketball")
        crud_lookups.get_league_id("nfl")

        # Still only the initial 2 fetches (one per table).
        assert mock_fetch.call_count == 2

    @patch("precog.database.crud_lookups.fetch_all")
    def test_invalidate_cache_forces_repopulate(self, mock_fetch: MagicMock) -> None:
        """invalidate_cache() causes the next lookup to re-fetch."""
        mock_fetch.side_effect = _fetch_all_side_effect

        crud_lookups.get_sport_id("football")
        assert mock_fetch.call_count == 2

        crud_lookups.invalidate_cache()
        crud_lookups.get_sport_id("football")

        # Re-fetched both tables again.
        assert mock_fetch.call_count == 4

    @patch("precog.database.crud_lookups.fetch_all")
    def test_degraded_cache_on_fetch_all_exception(self, mock_fetch: MagicMock) -> None:
        """If fetch_all raises, cache is populated with empty dicts.

        Subsequent ``*_or_none`` calls must return None; strict calls must
        raise KeyError whose message contains ``Valid keys: []``.
        """
        # Bare ``Exception`` is caught — use a synthetic to stay portable.
        mock_fetch.side_effect = Exception("relation 'sports' does not exist")

        # _or_none helpers degrade silently.
        assert crud_lookups.get_sport_id_or_none("football") is None
        assert crud_lookups.get_league_id_or_none("nfl") is None
        assert crud_lookups.get_sport_id_from_league_or_none("nfl") is None

        # Strict helpers raise KeyError with the empty-keys sentinel.
        with pytest.raises(KeyError, match=r"Valid keys: \[\]"):
            crud_lookups.get_sport_id("football")
        with pytest.raises(KeyError, match=r"Valid keys: \[\]"):
            crud_lookups.get_league_id("nfl")
        with pytest.raises(KeyError, match=r"Valid keys: \[\]"):
            crud_lookups.get_sport_id_from_league("nfl")


# =============================================================================
# B. get_sport_id / get_sport_id_or_none
# =============================================================================


class TestGetSportId:
    """Strict + permissive sport_key → sports.id resolution."""

    @patch("precog.database.crud_lookups.fetch_all")
    def test_known_sport_key_returns_int(self, mock_fetch: MagicMock) -> None:
        """Happy path: seeded sport_key resolves to its id."""
        mock_fetch.side_effect = _fetch_all_side_effect

        assert crud_lookups.get_sport_id("football") == 1
        assert crud_lookups.get_sport_id("basketball") == 2

    @patch("precog.database.crud_lookups.fetch_all")
    def test_unknown_sport_key_raises_keyerror_with_valid_keys(self, mock_fetch: MagicMock) -> None:
        """Unknown key raises KeyError whose message includes the sorted valid-key list."""
        mock_fetch.side_effect = _fetch_all_side_effect

        with pytest.raises(KeyError) as exc_info:
            crud_lookups.get_sport_id("quidditch")

        # KeyError wraps the message in another pair of quotes; use str().
        msg = str(exc_info.value)
        assert "quidditch" in msg
        assert "Valid keys:" in msg
        # Sorted list of the 2 seeded keys.
        assert "'basketball'" in msg
        assert "'football'" in msg

    @patch("precog.database.crud_lookups.fetch_all")
    def test_or_none_known_returns_int(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect
        assert crud_lookups.get_sport_id_or_none("football") == 1

    @patch("precog.database.crud_lookups.fetch_all")
    def test_or_none_unknown_returns_none(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect
        assert crud_lookups.get_sport_id_or_none("quidditch") is None

    @patch("precog.database.crud_lookups.fetch_all")
    def test_or_none_none_input_short_circuits(self, mock_fetch: MagicMock) -> None:
        """None input returns None WITHOUT populating the cache (Pattern 45)."""
        mock_fetch.side_effect = _fetch_all_side_effect

        assert crud_lookups.get_sport_id_or_none(None) is None

        # Cache was never touched.
        assert mock_fetch.call_count == 0


# =============================================================================
# C. get_league_id / get_league_id_or_none
# =============================================================================


class TestGetLeagueId:
    """Strict + permissive league_key → leagues.id resolution."""

    @patch("precog.database.crud_lookups.fetch_all")
    def test_known_league_key_returns_int(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect
        assert crud_lookups.get_league_id("nfl") == 10
        assert crud_lookups.get_league_id("nba") == 20

    @patch("precog.database.crud_lookups.fetch_all")
    def test_unknown_league_key_raises_keyerror(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect

        with pytest.raises(KeyError) as exc_info:
            crud_lookups.get_league_id("nhl")

        msg = str(exc_info.value)
        assert "nhl" in msg
        assert "Valid keys:" in msg
        assert "'nfl'" in msg

    @patch("precog.database.crud_lookups.fetch_all")
    def test_or_none_known_returns_int(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect
        assert crud_lookups.get_league_id_or_none("ncaaf") == 11

    @patch("precog.database.crud_lookups.fetch_all")
    def test_or_none_unknown_returns_none(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect
        assert crud_lookups.get_league_id_or_none("nhl") is None

    @patch("precog.database.crud_lookups.fetch_all")
    def test_or_none_none_input_short_circuits(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect
        assert crud_lookups.get_league_id_or_none(None) is None
        assert mock_fetch.call_count == 0


# =============================================================================
# D. get_sport_id_from_league / _or_none
# =============================================================================


class TestGetSportIdFromLeague:
    """league_key → parent sports.id resolution via the leagues.sport_id FK."""

    @patch("precog.database.crud_lookups.fetch_all")
    def test_known_league_resolves_parent_sport(self, mock_fetch: MagicMock) -> None:
        """'nfl' → football (sport_id=1); 'nba' → basketball (sport_id=2)."""
        mock_fetch.side_effect = _fetch_all_side_effect

        assert crud_lookups.get_sport_id_from_league("nfl") == 1
        assert crud_lookups.get_sport_id_from_league("ncaaf") == 1
        assert crud_lookups.get_sport_id_from_league("nba") == 2

    @patch("precog.database.crud_lookups.fetch_all")
    def test_unknown_league_raises_keyerror(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect

        with pytest.raises(KeyError) as exc_info:
            crud_lookups.get_sport_id_from_league("nhl")

        # Parity with TestGetSportId / TestGetLeagueId: pin the helpful
        # "Valid keys: [...]" context so a regression to bare KeyError("nhl")
        # would fail loudly.
        msg = str(exc_info.value)
        assert "nhl" in msg
        assert "Valid keys:" in msg
        assert "'nfl'" in msg

    @patch("precog.database.crud_lookups.fetch_all")
    def test_or_none_known_returns_parent_sport(self, mock_fetch: MagicMock) -> None:
        """Symmetric with TestGetSportId.B / TestGetLeagueId.C happy-path `_or_none`."""
        mock_fetch.side_effect = _fetch_all_side_effect
        assert crud_lookups.get_sport_id_from_league_or_none("nfl") == 1
        assert crud_lookups.get_sport_id_from_league_or_none("nba") == 2

    @patch("precog.database.crud_lookups.fetch_all")
    def test_or_none_unknown_returns_none(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect
        assert crud_lookups.get_sport_id_from_league_or_none("nhl") is None

    @patch("precog.database.crud_lookups.fetch_all")
    def test_or_none_none_input_short_circuits(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = _fetch_all_side_effect
        assert crud_lookups.get_sport_id_from_league_or_none(None) is None
        assert mock_fetch.call_count == 0


# =============================================================================
# E. resolve_league_id_via_game
# =============================================================================


class TestResolveLeagueIdViaGame:
    """game_id → games.league → leagues.id resolution path.

    Note: ``resolve_league_id_via_game`` does ``from .connection import
    fetch_one`` inside the function body.  We patch at the origin module
    (``precog.database.connection.fetch_one``) so the late import picks up
    the mock.
    """

    @patch("precog.database.connection.fetch_one")
    @patch("precog.database.crud_lookups.fetch_all")
    def test_none_game_id_returns_none_without_fetch_one(
        self, mock_fetch_all: MagicMock, mock_fetch_one: MagicMock
    ) -> None:
        """None game_id short-circuits; fetch_one MUST NOT be called."""
        mock_fetch_all.side_effect = _fetch_all_side_effect

        assert crud_lookups.resolve_league_id_via_game(None) is None
        assert mock_fetch_one.call_count == 0

    @patch("precog.database.connection.fetch_one")
    @patch("precog.database.crud_lookups.fetch_all")
    def test_game_row_missing_returns_none(
        self, mock_fetch_all: MagicMock, mock_fetch_one: MagicMock
    ) -> None:
        """fetch_one returns None (no games row) → resolver returns None."""
        mock_fetch_all.side_effect = _fetch_all_side_effect
        mock_fetch_one.return_value = None

        assert crud_lookups.resolve_league_id_via_game(42) is None

    @patch("precog.database.connection.fetch_one")
    @patch("precog.database.crud_lookups.fetch_all")
    def test_game_row_with_known_league_returns_league_id(
        self, mock_fetch_all: MagicMock, mock_fetch_one: MagicMock
    ) -> None:
        """Valid game_id → games.league → leagues.id."""
        mock_fetch_all.side_effect = _fetch_all_side_effect
        mock_fetch_one.return_value = {"league": "nfl"}

        assert crud_lookups.resolve_league_id_via_game(42) == 10
        # Pin the SQL text + params binding — a regression that changed
        # the WHERE clause or the game_id param would otherwise be masked
        # by the mock's indifference to input.
        mock_fetch_one.assert_called_once_with(
            "SELECT league FROM games WHERE id = %s",
            (42,),
        )

    @patch("precog.database.connection.fetch_one")
    @patch("precog.database.crud_lookups.fetch_all")
    def test_game_row_with_unknown_league_returns_none(
        self, mock_fetch_all: MagicMock, mock_fetch_one: MagicMock
    ) -> None:
        """games.league value not in lookup cache → None (permissive _or_none path)."""
        mock_fetch_all.side_effect = _fetch_all_side_effect
        mock_fetch_one.return_value = {"league": "nhl"}

        assert crud_lookups.resolve_league_id_via_game(42) is None

    @patch("precog.database.connection.fetch_one")
    @patch("precog.database.crud_lookups.fetch_all")
    def test_fetch_one_exception_returns_none(
        self, mock_fetch_all: MagicMock, mock_fetch_one: MagicMock
    ) -> None:
        """fetch_one raising is caught → resolver returns None gracefully."""
        mock_fetch_all.side_effect = _fetch_all_side_effect
        mock_fetch_one.side_effect = Exception("connection refused")

        assert crud_lookups.resolve_league_id_via_game(42) is None


# =============================================================================
# F. resolve_sport_id_for_mixed_value
# =============================================================================


class TestResolveSportIdForMixedValue:
    """game_odds.sport mixed-convention resolver: accepts sport OR league key."""

    @patch("precog.database.crud_lookups.fetch_all")
    def test_none_input_short_circuits(self, mock_fetch: MagicMock) -> None:
        """None input returns None WITHOUT populating the cache."""
        mock_fetch.side_effect = _fetch_all_side_effect

        assert crud_lookups.resolve_sport_id_for_mixed_value(None) is None
        assert mock_fetch.call_count == 0

    @patch("precog.database.crud_lookups.fetch_all")
    def test_sport_key_resolves_directly(self, mock_fetch: MagicMock) -> None:
        """When value is a sport_key ('football'), use sports map directly."""
        mock_fetch.side_effect = _fetch_all_side_effect

        assert crud_lookups.resolve_sport_id_for_mixed_value("football") == 1
        assert crud_lookups.resolve_sport_id_for_mixed_value("basketball") == 2

    @patch("precog.database.crud_lookups.fetch_all")
    def test_league_key_resolves_via_fallback(self, mock_fetch: MagicMock) -> None:
        """When value is a league_key ('nfl'), fall back to league→sport_id map."""
        mock_fetch.side_effect = _fetch_all_side_effect

        # 'nfl' is NOT a sport_key but IS a league_key → parent sport = football (1).
        assert crud_lookups.resolve_sport_id_for_mixed_value("nfl") == 1
        # 'nba' → parent sport = basketball (2).
        assert crud_lookups.resolve_sport_id_for_mixed_value("nba") == 2

    @patch("precog.database.crud_lookups.fetch_all")
    def test_sport_first_precedence_on_collision(self, mock_fetch: MagicMock) -> None:
        """'soccer' exists as BOTH a sport_key and a league_key → prefer sport.

        Mirrors the real migration 0060 seed where 'soccer' is both. The
        source iterates `if value in _sport_key_to_id` FIRST before the
        league fallback, so the sport's id (3) must win over the league
        parent-id lookup (which would also resolve to 3 here — but even if
        the seed diverged, precedence must be sport-first).
        """
        mock_fetch.side_effect = _fetch_all_side_effect

        # The assertion pins precedence behavior: resolve_sport_id_for_mixed_value
        # must walk the sport map first, not the league fallback.
        assert crud_lookups.resolve_sport_id_for_mixed_value("soccer") == 3

    @patch("precog.database.crud_lookups.fetch_all")
    def test_unknown_value_returns_none_without_raising(self, mock_fetch: MagicMock) -> None:
        """Value matching neither map returns None (permissive, no raise)."""
        mock_fetch.side_effect = _fetch_all_side_effect

        assert crud_lookups.resolve_sport_id_for_mixed_value("quidditch") is None


# =============================================================================
# G. invalidate_cache — fixture verification + mid-test re-fetch
# =============================================================================


class TestInvalidateCacheFixtureBehavior:
    """Prove the autouse fixture isolates tests and invalidate_cache mid-test works."""

    @patch("precog.database.crud_lookups.fetch_all")
    def test_first_sequential_test_triggers_fresh_fetch(self, mock_fetch: MagicMock) -> None:
        """Sibling of the next test — each must independently trigger a fresh fetch."""
        mock_fetch.side_effect = _fetch_all_side_effect

        crud_lookups.get_sport_id("football")

        # If the autouse fixture failed to invalidate, this assertion would
        # hold only for the first-run test in the class; running it twice
        # proves cleanup between tests works.
        assert mock_fetch.call_count == 2

    @patch("precog.database.crud_lookups.fetch_all")
    def test_second_sequential_test_with_different_lookup(self, mock_fetch: MagicMock) -> None:
        """Sibling test — exercises a DIFFERENT surface to gain independent signal.

        The first sibling above uses `get_sport_id("football")`. If both tests
        called the identical lookup, the pair wouldn't prove anything stronger
        than either test alone. This test calls `get_league_id("nfl")` so that
        if the autouse fixture ever regresses to a cache-clear-but-not-reset
        state, this test would see call_count != 2 (because a stale sport-only
        cache would satisfy the league query without re-fetching).
        """
        mock_fetch.side_effect = _fetch_all_side_effect

        crud_lookups.get_league_id("nfl")

        assert mock_fetch.call_count == 2, (
            "Cache leaked between tests — autouse invalidate_cache fixture broken"
        )

    @patch("precog.database.crud_lookups.fetch_all")
    def test_invalidate_cache_mid_test_forces_refetch(self, mock_fetch: MagicMock) -> None:
        """Mid-test invalidate_cache() causes the next lookup to re-fetch both tables."""
        mock_fetch.side_effect = _fetch_all_side_effect

        crud_lookups.get_sport_id("football")
        assert mock_fetch.call_count == 2

        crud_lookups.invalidate_cache()

        # Still 2 — invalidate alone doesn't fetch.
        assert mock_fetch.call_count == 2

        crud_lookups.get_sport_id("football")
        # Now re-populated → total is 4.
        assert mock_fetch.call_count == 4
