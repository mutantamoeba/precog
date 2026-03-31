"""Unit tests for EventGameMatcher.

Tests the full matching flow with mocked registry and CRUD functions.
No database required — all external dependencies are mocked.

Related:
    - Issue #462: Event-to-game matching
    - src/precog/matching/event_game_matcher.py
"""

from datetime import date
from unittest.mock import MagicMock, patch

from precog.matching.event_game_matcher import EventGameMatcher, MatchReason
from precog.matching.team_code_registry import TeamCodeRegistry

# =============================================================================
# Test Data
# =============================================================================

NFL_TEAMS: list[dict] = [
    {"team_code": "JAX", "league": "nfl", "kalshi_team_code": "JAC"},
    {"team_code": "LAR", "league": "nfl", "kalshi_team_code": "LA"},
    {"team_code": "HOU", "league": "nfl", "kalshi_team_code": None},
    {"team_code": "NE", "league": "nfl", "kalshi_team_code": None},
    {"team_code": "KC", "league": "nfl", "kalshi_team_code": None},
    {"team_code": "BUF", "league": "nfl", "kalshi_team_code": None},
    {"team_code": "SF", "league": "nfl", "kalshi_team_code": None},
    {"team_code": "BAL", "league": "nfl", "kalshi_team_code": None},
    {"team_code": "DAL", "league": "nfl", "kalshi_team_code": None},
    {"team_code": "NYG", "league": "nfl", "kalshi_team_code": None},
]


def _make_registry() -> TeamCodeRegistry:
    """Create a registry pre-loaded with test data."""
    registry = TeamCodeRegistry()
    registry.load_from_data(NFL_TEAMS)
    return registry


# =============================================================================
# Match Event Tests
# =============================================================================


class TestMatchEvent:
    """Tests for EventGameMatcher.match_event()."""

    @patch("precog.matching.event_game_matcher.EventGameMatcher._find_game")
    def test_successful_match(self, mock_find: MagicMock) -> None:
        """Successful ticker-based match returns game_id."""
        mock_find.return_value = 42

        matcher = EventGameMatcher(registry=_make_registry())
        result = matcher.match_event("KXNFLGAME-26JAN18HOUNE")

        assert result == 42
        mock_find.assert_called_once_with("nfl", date(2026, 1, 18), "NE", "HOU")

    @patch("precog.matching.event_game_matcher.EventGameMatcher._find_game")
    def test_match_with_kalshi_code_mismatch(self, mock_find: MagicMock) -> None:
        """Kalshi JAC resolves to ESPN JAX before game lookup."""
        mock_find.return_value = 99

        matcher = EventGameMatcher(registry=_make_registry())
        result = matcher.match_event("KXNFLGAME-26JAN18JACNE")

        assert result == 99
        # Should pass JAX (ESPN code) not JAC (Kalshi code)
        mock_find.assert_called_once_with("nfl", date(2026, 1, 18), "NE", "JAX")

    @patch("precog.matching.event_game_matcher.EventGameMatcher._find_game")
    def test_match_la_rams(self, mock_find: MagicMock) -> None:
        """Kalshi LA resolves to ESPN LAR for Rams."""
        mock_find.return_value = 55

        matcher = EventGameMatcher(registry=_make_registry())
        result = matcher.match_event("KXNFLGAME-26JAN18LASF")

        assert result == 55
        mock_find.assert_called_once_with("nfl", date(2026, 1, 18), "SF", "LAR")

    def test_no_match_non_sports(self) -> None:
        """Non-sports ticker returns None."""
        matcher = EventGameMatcher(registry=_make_registry())
        result = matcher.match_event("KXPOLITICS-PRES2028")
        assert result is None

    def test_no_match_empty_ticker(self) -> None:
        matcher = EventGameMatcher(registry=_make_registry())
        result = matcher.match_event("")
        assert result is None

    @patch("precog.matching.event_game_matcher.EventGameMatcher._find_game")
    def test_no_match_game_not_found(self, mock_find: MagicMock) -> None:
        """Ticker parses but no game exists in DB."""
        mock_find.return_value = None

        matcher = EventGameMatcher(registry=_make_registry())
        result = matcher.match_event("KXNFLGAME-26JAN18HOUNE")

        assert result is None

    def test_no_match_empty_registry(self) -> None:
        """Empty registry can't resolve any codes."""
        registry = TeamCodeRegistry()
        registry.load_from_data([])
        matcher = EventGameMatcher(registry=registry)
        result = matcher.match_event("KXNFLGAME-26JAN18HOUNE")
        assert result is None

    def test_title_fallback_stub_returns_none(self) -> None:
        """Title-based fallback is stubbed — always returns None."""
        matcher = EventGameMatcher(registry=_make_registry())
        # Even with a title, should return None since title parsing is TODO
        result = matcher.match_event(
            "KXUNKNOWNSERIES-26JAN18",
            title="Texans vs Patriots",
        )
        assert result is None


# =============================================================================
# Backfill Tests
# =============================================================================


class TestBackfillUnlinkedEvents:
    """Tests for EventGameMatcher.backfill_unlinked_events()."""

    @patch("precog.database.crud_operations.update_event_game_id")
    @patch("precog.database.crud_operations.find_unlinked_sports_events")
    def test_backfill_links_events(
        self,
        mock_find_unlinked: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Backfill finds unlinked events and links them."""
        mock_find_unlinked.return_value = [
            {
                "id": 1,
                "external_id": "KXNFLGAME-26JAN18HOUNE",
                "title": "HOU @ NE",
                "subcategory": "nfl",
            },
            {
                "id": 2,
                "external_id": "KXNFLGAME-26JAN18KCBUF",
                "title": "KC @ BUF",
                "subcategory": "nfl",
            },
        ]
        mock_update.return_value = True

        matcher = EventGameMatcher(registry=_make_registry())

        with patch.object(matcher, "_find_game", return_value=42):
            count = matcher.backfill_unlinked_events("nfl")

        assert count == 2
        assert mock_update.call_count == 2

    @patch("precog.database.crud_operations.update_event_game_id")
    @patch("precog.database.crud_operations.find_unlinked_sports_events")
    def test_backfill_no_unlinked(
        self,
        mock_find_unlinked: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """No unlinked events means zero linked."""
        mock_find_unlinked.return_value = []

        matcher = EventGameMatcher(registry=_make_registry())
        count = matcher.backfill_unlinked_events("nfl")

        assert count == 0
        mock_update.assert_not_called()

    @patch("precog.database.crud_operations.update_event_game_id")
    @patch("precog.database.crud_operations.find_unlinked_sports_events")
    def test_backfill_partial_match(
        self,
        mock_find_unlinked: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Some events match, some don't."""
        mock_find_unlinked.return_value = [
            {"id": 1, "external_id": "KXNFLGAME-26JAN18HOUNE", "title": None, "subcategory": "nfl"},
            {
                "id": 2,
                "external_id": "KXPOLITICS-UNKNOWN",
                "title": None,
                "subcategory": "politics",
            },
        ]
        mock_update.return_value = True

        matcher = EventGameMatcher(registry=_make_registry())

        # Only the first event will parse successfully
        with patch.object(matcher, "_find_game", return_value=42):
            count = matcher.backfill_unlinked_events()

        # Only 1 match (the NFL event), politics ticker won't parse
        assert count == 1


# =============================================================================
# Match Event With Reason Tests
# =============================================================================


class TestMatchEventWithReason:
    """Tests for EventGameMatcher.match_event_with_reason()."""

    @patch("precog.matching.event_game_matcher.EventGameMatcher._find_game")
    def test_matched_returns_game_id_and_matched_reason(self, mock_find: MagicMock) -> None:
        """Successful match returns game_id and MATCHED reason."""
        mock_find.return_value = 42

        matcher = EventGameMatcher(registry=_make_registry())
        game_id, reason = matcher.match_event_with_reason("KXNFLGAME-26JAN18HOUNE")

        assert game_id == 42
        assert reason == MatchReason.MATCHED

    def test_parse_fail_for_non_sports_ticker(self) -> None:
        """Non-sports ticker returns None and PARSE_FAIL reason."""
        matcher = EventGameMatcher(registry=_make_registry())
        game_id, reason = matcher.match_event_with_reason("KXPOLITICS-PRES2028")

        assert game_id is None
        assert reason == MatchReason.PARSE_FAIL

    def test_no_code_for_unknown_team(self) -> None:
        """Unknown team code returns None and NO_CODE reason."""
        # Use a registry that has NFL codes but the ticker has an unknown code
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)
        matcher = EventGameMatcher(registry=registry)

        # ZZZ is not a known code -- but we need a ticker that parses the league
        # but fails code resolution. Use a ticker with codes not in registry.
        # The ticker parser needs valid_codes to split, so an unresolvable
        # pair won't parse at all. Instead, test with a registry missing one team.
        small_registry = TeamCodeRegistry()
        small_registry.load_from_data(
            [
                {"team_code": "HOU", "league": "nfl", "kalshi_team_code": None},
            ]
        )
        matcher = EventGameMatcher(registry=small_registry)
        # "HOUNE" - HOU is known but NE is not in this small registry
        # However, the ticker parser needs NE in valid_codes to split.
        # With only HOU in valid codes, "HOUNE" won't split properly.
        # So this will actually be a parse_fail. Let's use a different approach.

        # Better test: registry has both codes for parsing, but resolve fails
        # This happens when the parser has valid codes but resolve returns None.
        # Simulate by having codes in _kalshi_codes but not in _kalshi_to_espn.
        # Simplest: use full registry but patch resolve to return None for one.
        matcher = EventGameMatcher(registry=_make_registry())
        with patch.object(matcher.registry, "resolve_kalshi_to_espn", side_effect=[None, "NE"]):
            game_id, reason = matcher.match_event_with_reason("KXNFLGAME-26JAN18HOUNE")

        assert game_id is None
        assert reason == MatchReason.NO_CODE

    @patch("precog.matching.event_game_matcher.EventGameMatcher._find_game")
    def test_no_game_when_db_returns_none(self, mock_find: MagicMock) -> None:
        """Parsed and resolved but no game in DB returns NO_GAME reason."""
        mock_find.return_value = None

        matcher = EventGameMatcher(registry=_make_registry())
        game_id, reason = matcher.match_event_with_reason("KXNFLGAME-26JAN18HOUNE")

        assert game_id is None
        assert reason == MatchReason.NO_GAME

    def test_empty_ticker_returns_parse_fail(self) -> None:
        """Empty ticker returns PARSE_FAIL."""
        matcher = EventGameMatcher(registry=_make_registry())
        game_id, reason = matcher.match_event_with_reason("")

        assert game_id is None
        assert reason == MatchReason.PARSE_FAIL

    @patch("precog.matching.event_game_matcher.EventGameMatcher._find_game")
    def test_backward_compat_match_event_unchanged(self, mock_find: MagicMock) -> None:
        """Original match_event() still works and returns just game_id."""
        mock_find.return_value = 42
        matcher = EventGameMatcher(registry=_make_registry())

        result = matcher.match_event("KXNFLGAME-26JAN18HOUNE")
        assert result == 42  # Returns int, not tuple
