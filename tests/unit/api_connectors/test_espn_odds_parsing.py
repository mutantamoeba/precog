"""
Unit Tests for ESPN DraftKings Odds Parsing.

Tests the odds extraction functions added to espn_client.py for
parsing DraftKings betting lines from ESPN scoreboard responses.

Tests cover:
- American odds string -> int conversion
- Point spread line -> Decimal conversion
- Total (o/u) line -> Decimal conversion
- Full competition odds extraction
- Missing/malformed data handling

Related:
    - Issue #533: ESPN DraftKings odds extraction
    - Migration 0048: game_odds table with SCD Type 2
    - tests/cassettes/espn/espn_nba_scoreboard.yaml: Real data reference

Usage:
    pytest tests/unit/api_connectors/test_espn_odds_parsing.py -v
"""

from decimal import Decimal

from precog.api_connectors.espn_client import (
    extract_espn_odds,
    parse_american_odds,
    parse_spread_line,
    parse_total_line,
)

# =============================================================================
# parse_american_odds Tests
# =============================================================================


class TestParseAmericanOdds:
    """Test American odds string -> integer parsing."""

    def test_positive_odds(self) -> None:
        """Positive odds: '+130' -> 130."""
        assert parse_american_odds("+130") == 130

    def test_negative_odds(self) -> None:
        """Negative odds: '-155' -> -155."""
        assert parse_american_odds("-155") == -155

    def test_even_odds(self) -> None:
        """EVEN keyword: 'EVEN' -> 100."""
        assert parse_american_odds("EVEN") == 100

    def test_even_case_insensitive(self) -> None:
        """EVEN is case insensitive."""
        assert parse_american_odds("even") == 100
        assert parse_american_odds("Even") == 100

    def test_no_sign_positive(self) -> None:
        """Unsigned integer: '130' -> 130."""
        assert parse_american_odds("130") == 130

    def test_none_returns_none(self) -> None:
        """None input returns None."""
        assert parse_american_odds(None) is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert parse_american_odds("") is None

    def test_whitespace_only_returns_none(self) -> None:
        """Whitespace-only string returns None."""
        assert parse_american_odds("   ") is None

    def test_non_numeric_returns_none(self) -> None:
        """Non-numeric string returns None."""
        assert parse_american_odds("abc") is None

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        assert parse_american_odds(" +130 ") == 130
        assert parse_american_odds(" -155 ") == -155

    def test_large_odds(self) -> None:
        """Large odds values parse correctly."""
        assert parse_american_odds("+5000") == 5000
        assert parse_american_odds("-10000") == -10000

    def test_small_odds(self) -> None:
        """Small (close to even) odds."""
        assert parse_american_odds("+100") == 100
        assert parse_american_odds("-100") == -100
        assert parse_american_odds("-101") == -101

    def test_real_espn_values(self) -> None:
        """Values from actual ESPN NBA scoreboard cassette."""
        assert parse_american_odds("+130") == 130  # TOR home ML
        assert parse_american_odds("-155") == -155  # BOS away ML
        assert parse_american_odds("+114") == 114  # TOR home ML open
        assert parse_american_odds("-135") == -135  # BOS away ML open
        assert parse_american_odds("-112") == -112  # TOR spread odds
        assert parse_american_odds("-108") == -108  # BOS spread odds
        assert parse_american_odds("-115") == -115  # Over odds
        assert parse_american_odds("-105") == -105  # Under odds


# =============================================================================
# parse_spread_line Tests
# =============================================================================


class TestParseSpreadLine:
    """Test point spread line string -> Decimal parsing."""

    def test_positive_spread(self) -> None:
        """'+3.5' -> Decimal('3.5')."""
        assert parse_spread_line("+3.5") == Decimal("3.5")

    def test_negative_spread(self) -> None:
        """'-7.0' -> Decimal('-7.0')."""
        assert parse_spread_line("-7.0") == Decimal("-7.0")

    def test_pick_em(self) -> None:
        """'0' -> Decimal('0')."""
        assert parse_spread_line("0") == Decimal("0")

    def test_half_point(self) -> None:
        """Half-point spreads parse correctly."""
        assert parse_spread_line("+2.5") == Decimal("2.5")
        assert parse_spread_line("-2.5") == Decimal("-2.5")

    def test_whole_number(self) -> None:
        """Whole number spreads."""
        assert parse_spread_line("+3") == Decimal("3")
        assert parse_spread_line("-7") == Decimal("-7")

    def test_none_returns_none(self) -> None:
        """None returns None."""
        assert parse_spread_line(None) is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert parse_spread_line("") is None

    def test_invalid_returns_none(self) -> None:
        """Invalid string returns None."""
        assert parse_spread_line("abc") is None

    def test_real_espn_values(self) -> None:
        """Values from actual ESPN NBA scoreboard cassette."""
        assert parse_spread_line("+3.5") == Decimal("3.5")  # TOR home spread
        assert parse_spread_line("-3.5") == Decimal("-3.5")  # BOS away spread
        assert parse_spread_line("+2.5") == Decimal("2.5")  # Open spread
        assert parse_spread_line("-2.5") == Decimal("-2.5")  # Open spread


# =============================================================================
# parse_total_line Tests
# =============================================================================


class TestParseTotalLine:
    """Test total (over/under) line string -> Decimal parsing."""

    def test_over_prefix(self) -> None:
        """'o224.5' -> Decimal('224.5')."""
        assert parse_total_line("o224.5") == Decimal("224.5")

    def test_under_prefix(self) -> None:
        """'u224.5' -> Decimal('224.5')."""
        assert parse_total_line("u224.5") == Decimal("224.5")

    def test_uppercase_prefix(self) -> None:
        """'O224.5' and 'U224.5' also work."""
        assert parse_total_line("O224.5") == Decimal("224.5")
        assert parse_total_line("U224.5") == Decimal("224.5")

    def test_no_prefix(self) -> None:
        """'224.5' -> Decimal('224.5')."""
        assert parse_total_line("224.5") == Decimal("224.5")

    def test_whole_number(self) -> None:
        """Whole number totals."""
        assert parse_total_line("o45") == Decimal("45")

    def test_none_returns_none(self) -> None:
        """None returns None."""
        assert parse_total_line(None) is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert parse_total_line("") is None

    def test_invalid_returns_none(self) -> None:
        """Invalid string returns None."""
        assert parse_total_line("xyz") is None

    def test_real_espn_values(self) -> None:
        """Values from actual ESPN NBA scoreboard cassette."""
        assert parse_total_line("o224.5") == Decimal("224.5")  # Close over
        assert parse_total_line("u224.5") == Decimal("224.5")  # Close under
        assert parse_total_line("o227.5") == Decimal("227.5")  # Open over
        assert parse_total_line("u227.5") == Decimal("227.5")  # Open under


# =============================================================================
# extract_espn_odds Tests
# =============================================================================


# Real DraftKings odds data from ESPN NBA scoreboard cassette (BOS @ TOR)
SAMPLE_COMPETITION_WITH_ODDS: dict = {
    "odds": [
        {
            "provider": {"id": "100", "priority": 1},
            "details": "BOS -3.5",
            "overUnder": 224.5,
            "spread": 3.5,
            "awayTeamOdds": {
                "favorite": True,
                "underdog": False,
                "favoriteAtOpen": True,
            },
            "homeTeamOdds": {
                "favorite": False,
                "underdog": True,
                "favoriteAtOpen": False,
            },
            "moneyline": {
                "home": {
                    "close": {"odds": "+130"},
                    "open": {"odds": "+114"},
                },
                "away": {
                    "close": {"odds": "-155"},
                    "open": {"odds": "-135"},
                },
            },
            "pointSpread": {
                "home": {
                    "close": {"line": "+3.5", "odds": "-112"},
                    "open": {"line": "+2.5", "odds": "-115"},
                },
                "away": {
                    "close": {"line": "-3.5", "odds": "-108"},
                    "open": {"line": "-2.5", "odds": "-105"},
                },
            },
            "total": {
                "over": {
                    "close": {"line": "o224.5", "odds": "-115"},
                    "open": {"line": "o227.5", "odds": "-112"},
                },
                "under": {
                    "close": {"line": "u224.5", "odds": "-105"},
                    "open": {"line": "u227.5", "odds": "-108"},
                },
            },
        }
    ]
}


class TestExtractEspnOdds:
    """Test full competition odds extraction."""

    def test_extracts_moneyline(self) -> None:
        """Moneyline values are correctly extracted."""
        result = extract_espn_odds(SAMPLE_COMPETITION_WITH_ODDS)
        assert result is not None
        assert result["moneyline_home_close"] == 130
        assert result["moneyline_home_open"] == 114
        assert result["moneyline_away_close"] == -155
        assert result["moneyline_away_open"] == -135

    def test_extracts_spread(self) -> None:
        """Point spread values are correctly extracted."""
        result = extract_espn_odds(SAMPLE_COMPETITION_WITH_ODDS)
        assert result is not None
        assert result["spread_home_close"] == Decimal("3.5")
        assert result["spread_home_open"] == Decimal("2.5")
        assert result["spread_home_odds_close"] == -112
        assert result["spread_home_odds_open"] == -115
        assert result["spread_away_odds_close"] == -108
        assert result["spread_away_odds_open"] == -105

    def test_extracts_totals(self) -> None:
        """Total (over/under) values are correctly extracted."""
        result = extract_espn_odds(SAMPLE_COMPETITION_WITH_ODDS)
        assert result is not None
        assert result["total_close"] == Decimal("224.5")
        assert result["total_open"] == Decimal("227.5")
        assert result["over_odds_close"] == -115
        assert result["over_odds_open"] == -112
        assert result["under_odds_close"] == -105
        assert result["under_odds_open"] == -108

    def test_extracts_details(self) -> None:
        """Details text is extracted."""
        result = extract_espn_odds(SAMPLE_COMPETITION_WITH_ODDS)
        assert result is not None
        assert result["details"] == "BOS -3.5"

    def test_extracts_top_level_spread(self) -> None:
        """Top-level spread and overUnder are extracted as Decimal."""
        result = extract_espn_odds(SAMPLE_COMPETITION_WITH_ODDS)
        assert result is not None
        assert result["spread"] == Decimal("3.5")
        assert result["over_under"] == Decimal("224.5")

    def test_extracts_favorite_flags(self) -> None:
        """Favorite flags are correctly extracted."""
        result = extract_espn_odds(SAMPLE_COMPETITION_WITH_ODDS)
        assert result is not None
        assert result["home_favorite"] is False
        assert result["away_favorite"] is True
        assert result["home_favorite_at_open"] is False
        assert result["away_favorite_at_open"] is True

    def test_empty_odds_returns_none(self) -> None:
        """Competition with no odds returns None."""
        result = extract_espn_odds({"odds": []})
        assert result is None

    def test_no_odds_key_returns_none(self) -> None:
        """Competition with no odds key returns None."""
        result = extract_espn_odds({})
        assert result is None

    def test_empty_competition_returns_none(self) -> None:
        """Empty dict returns None."""
        result = extract_espn_odds({})
        assert result is None

    def test_partial_odds_still_extracts(self) -> None:
        """Competition with only moneyline (no spread/total) still works."""
        partial = {
            "odds": [
                {
                    "provider": {"id": "100"},
                    "details": "KC -3",
                    "moneyline": {
                        "home": {
                            "close": {"odds": "-150"},
                        },
                        "away": {
                            "close": {"odds": "+125"},
                        },
                    },
                }
            ]
        }
        result = extract_espn_odds(partial)
        assert result is not None
        assert result["moneyline_home_close"] == -150
        assert result["moneyline_away_close"] == 125
        assert result["details"] == "KC -3"
        # Spread/total fields should not be present (total=False TypedDict)
        assert result.get("spread_home_close") is None
        assert result.get("total_close") is None

    def test_falls_back_to_first_provider(self) -> None:
        """If DraftKings (id 100) not found, falls back to first provider."""
        other_provider = {
            "odds": [
                {
                    "provider": {"id": "999", "priority": 1},
                    "details": "Team -2.5",
                    "moneyline": {
                        "home": {"close": {"odds": "+110"}},
                        "away": {"close": {"odds": "-130"}},
                    },
                }
            ]
        }
        result = extract_espn_odds(other_provider)
        assert result is not None
        assert result["moneyline_home_close"] == 110

    def test_malformed_odds_values_handled_gracefully(self) -> None:
        """Malformed odds strings don't crash extraction."""
        malformed = {
            "odds": [
                {
                    "provider": {"id": "100"},
                    "moneyline": {
                        "home": {"close": {"odds": "not-a-number"}},
                        "away": {"close": {"odds": ""}},
                    },
                    "pointSpread": {
                        "home": {"close": {"line": "bad", "odds": "bad"}},
                    },
                    "total": {
                        "over": {"close": {"line": "o-bad", "odds": "bad"}},
                    },
                }
            ]
        }
        result = extract_espn_odds(malformed)
        # Malformed values should not crash — result may be partial or None
        # but the function must not raise
        assert result is None or isinstance(result, dict)

    def test_none_values_in_nested_dicts(self) -> None:
        """None values at various nesting levels don't crash."""
        partial = {
            "odds": [
                {
                    "provider": {"id": "100"},
                    "details": None,
                    "spread": None,
                    "overUnder": None,
                    "moneyline": None,
                    "pointSpread": None,
                    "total": None,
                    "homeTeamOdds": None,
                    "awayTeamOdds": None,
                }
            ]
        }
        # Should not raise
        result = extract_espn_odds(partial)
        # May return None or empty dict - either is fine
        assert result is None or isinstance(result, dict)
