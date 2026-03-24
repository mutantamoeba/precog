"""Unit tests for Kalshi event ticker parser.

Tests the parsing of Kalshi event tickers into structured game data:
    - League extraction from series prefix
    - Date parsing from ticker segments
    - Team code splitting with variable-length codes
    - Edge cases: invalid tickers, ambiguous splits, date boundaries

Related:
    - Issue #462: Event-to-game matching
    - src/precog/matching/ticker_parser.py
"""

from datetime import date

import pytest

from precog.matching.ticker_parser import (
    ParsedTicker,
    _extract_league,
    _parse_date_segment,
    parse_event_ticker,
    split_team_codes,
)

# =============================================================================
# Valid code sets for testing
# =============================================================================

# NFL Kalshi codes (verified from live API data)
NFL_CODES: set[str] = {
    "ARI",
    "ATL",
    "BAL",
    "BUF",
    "CAR",
    "CHI",
    "CIN",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GB",
    "HOU",
    "IND",
    "JAC",
    "KC",
    "LA",
    "LAC",
    "LV",
    "MIA",
    "MIN",
    "NE",
    "NYG",
    "NYJ",
    "NO",
    "PHI",
    "PIT",
    "SEA",
    "SF",
    "TB",
    "TEN",
    "WAS",
}

# NBA Kalshi codes
NBA_CODES: set[str] = {
    "ATL",
    "BOS",
    "BKN",
    "CHA",
    "CHI",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GSW",
    "HOU",
    "IND",
    "LAC",
    "LAL",
    "MEM",
    "MIA",
    "MIL",
    "MIN",
    "NOP",
    "NYK",
    "OKC",
    "ORL",
    "PHI",
    "PHX",
    "POR",
    "SAC",
    "SAS",
    "TOR",
    "UTA",
    "WAS",
}

# NHL Kalshi codes (subset for testing)
NHL_CODES: set[str] = {
    "BOS",
    "NYR",
    "TOR",
    "MTL",
    "DET",
    "CHI",
    "TB",
    "FLA",
    "CAR",
    "WSH",
}

# MLB Kalshi codes (subset for testing)
MLB_CODES: set[str] = {
    "NYY",
    "BOS",
    "LAD",
    "SF",
    "CHC",
    "STL",
    "HOU",
    "ATL",
    "NYM",
    "PHI",
}

# NCAAF codes (subset for testing variable-length)
NCAAF_CODES: set[str] = {
    "WAKE",
    "MSST",
    "ALA",
    "LSU",
    "OHIO",
    "MICH",
    "USC",
    "ND",
    "TXST",
    "RICE",
    "ARMY",
    "NAVY",
}


# =============================================================================
# League Extraction Tests
# =============================================================================


class TestExtractLeague:
    """Tests for _extract_league()."""

    def test_nfl_game(self) -> None:
        assert _extract_league("KXNFLGAME") == "nfl"

    def test_nba_game(self) -> None:
        assert _extract_league("KXNBAGAME") == "nba"

    def test_ncaaf_game(self) -> None:
        assert _extract_league("KXNCAAFGAME") == "ncaaf"

    def test_ncaaf_d3_game(self) -> None:
        """NCAAF Division 3 variant."""
        assert _extract_league("KXNCAAFD3GAME") == "ncaaf"

    def test_nba_2h_winner(self) -> None:
        """NBA second half winner series."""
        assert _extract_league("KXNBA2HWINNER") == "nba"

    def test_nhl_game(self) -> None:
        assert _extract_league("KXNHLGAME") == "nhl"

    def test_mlb_game(self) -> None:
        assert _extract_league("KXMLBGAME") == "mlb"

    def test_ncaab_game(self) -> None:
        assert _extract_league("KXNCAABGAME") == "ncaab"

    def test_unknown_series(self) -> None:
        assert _extract_league("KXPOLITICS") is None

    def test_empty_string(self) -> None:
        assert _extract_league("") is None

    def test_case_insensitive(self) -> None:
        """Series prefix matching should be case-insensitive."""
        assert _extract_league("kxnflgame") == "nfl"


# =============================================================================
# Date Parsing Tests
# =============================================================================


class TestParseDateSegment:
    """Tests for _parse_date_segment()."""

    def test_standard_date(self) -> None:
        result = _parse_date_segment("26JAN18HOUNE")
        assert result is not None
        parsed_date, remaining = result
        assert parsed_date == date(2026, 1, 18)
        assert remaining == "HOUNE"

    def test_december_31(self) -> None:
        """Year boundary: Dec 31."""
        result = _parse_date_segment("25DEC31DALNYG")
        assert result is not None
        parsed_date, remaining = result
        assert parsed_date == date(2025, 12, 31)
        assert remaining == "DALNYG"

    def test_january_01(self) -> None:
        """Year boundary: Jan 1."""
        result = _parse_date_segment("26JAN01KCBUF")
        assert result is not None
        parsed_date, remaining = result
        assert parsed_date == date(2026, 1, 1)
        assert remaining == "KCBUF"

    def test_february_date(self) -> None:
        result = _parse_date_segment("26FEB14MIANE")
        assert result is not None
        parsed_date, remaining = result
        assert parsed_date == date(2026, 2, 14)
        assert remaining == "MIANE"

    def test_invalid_month(self) -> None:
        result = _parse_date_segment("26XXX18HOUNE")
        assert result is None

    def test_invalid_day(self) -> None:
        """Feb 30 is not a valid date."""
        result = _parse_date_segment("26FEB30HOUNE")
        assert result is None

    def test_empty_remaining(self) -> None:
        """Date with no team codes after it."""
        result = _parse_date_segment("26JAN18")
        assert result is not None
        parsed_date, remaining = result
        assert parsed_date == date(2026, 1, 18)
        assert remaining == ""

    def test_empty_string(self) -> None:
        assert _parse_date_segment("") is None

    def test_no_date_prefix(self) -> None:
        assert _parse_date_segment("HOUNE") is None


# =============================================================================
# Team Code Splitting Tests
# =============================================================================


class TestSplitTeamCodes:
    """Tests for split_team_codes()."""

    def test_3_char_plus_2_char(self) -> None:
        """HOU (3) + NE (2) = HOUNE."""
        result = split_team_codes("HOUNE", NFL_CODES)
        assert result == ("HOU", "NE")

    def test_2_char_plus_3_char(self) -> None:
        """KC (2) + BUF (3) = KCBUF."""
        result = split_team_codes("KCBUF", NFL_CODES)
        assert result == ("KC", "BUF")

    def test_2_char_plus_2_char(self) -> None:
        """NE (2) + SF (2) = NESF."""
        result = split_team_codes("NESF", NFL_CODES)
        assert result == ("NE", "SF")

    def test_2_char_plus_2_char_gb_kc(self) -> None:
        """GB (2) + KC (2) = GBKC."""
        result = split_team_codes("GBKC", NFL_CODES)
        assert result == ("GB", "KC")

    def test_3_char_plus_3_char(self) -> None:
        """OKC (3) + BOS (3) = OKCBOS."""
        result = split_team_codes("OKCBOS", NBA_CODES)
        assert result == ("OKC", "BOS")

    def test_4_char_plus_4_char_ncaaf(self) -> None:
        """WAKE (4) + MSST (4) = WAKEMSST."""
        result = split_team_codes("WAKEMSST", NCAAF_CODES)
        assert result == ("WAKE", "MSST")

    def test_4_char_plus_4_char_txst_rice(self) -> None:
        """TXST (4) + RICE (4) = TXSTRICE."""
        result = split_team_codes("TXSTRICE", NCAAF_CODES)
        assert result == ("TXST", "RICE")

    def test_3_char_plus_2_char_lv_tb(self) -> None:
        """LV (2) + TB (2) = LVTB."""
        result = split_team_codes("LVTB", NFL_CODES)
        assert result == ("LV", "TB")

    def test_no_valid_split(self) -> None:
        """No valid split found returns None."""
        result = split_team_codes("ZZZYY", NFL_CODES)
        assert result is None

    def test_too_short(self) -> None:
        """Fewer than 4 chars can't be split into two valid codes."""
        result = split_team_codes("ABC", NFL_CODES)
        assert result is None

    def test_empty_string(self) -> None:
        result = split_team_codes("", NFL_CODES)
        assert result is None

    def test_case_insensitive(self) -> None:
        """Should work regardless of input case."""
        result = split_team_codes("houne", NFL_CODES)
        assert result == ("HOU", "NE")

    def test_ambiguous_split_returns_none(self) -> None:
        """If multiple valid splits exist, return None (ambiguous).

        This is a contrived example. In practice, ambiguity is rare
        because real team code sets are designed to avoid collisions.
        """
        # Create a code set that makes "ABCDE" ambiguous:
        # AB + CDE and ABC + DE both valid
        ambiguous_codes = {"AB", "CDE", "ABC", "DE"}
        result = split_team_codes("ABCDE", ambiguous_codes)
        assert result is None


# =============================================================================
# Full Ticker Parsing Tests
# =============================================================================


class TestParseEventTicker:
    """Tests for parse_event_ticker()."""

    def test_nfl_ticker(self) -> None:
        """Standard NFL game ticker."""
        result = parse_event_ticker("KXNFLGAME-26JAN18HOUNE", NFL_CODES)
        assert result is not None
        assert result == ParsedTicker(
            series="KXNFLGAME",
            league="nfl",
            game_date=date(2026, 1, 18),
            away_team_code="HOU",
            home_team_code="NE",
        )

    def test_nba_ticker(self) -> None:
        """Standard NBA game ticker."""
        result = parse_event_ticker("KXNBAGAME-26MAR25OKCBOS", NBA_CODES)
        assert result is not None
        assert result.league == "nba"
        assert result.game_date == date(2026, 3, 25)
        assert result.away_team_code == "OKC"
        assert result.home_team_code == "BOS"

    def test_ncaaf_ticker_variable_length(self) -> None:
        """NCAAF with 4-char codes."""
        result = parse_event_ticker("KXNCAAFGAME-26JAN02WAKEMSST", NCAAF_CODES)
        assert result is not None
        assert result.league == "ncaaf"
        assert result.game_date == date(2026, 1, 2)
        assert result.away_team_code == "WAKE"
        assert result.home_team_code == "MSST"

    def test_ncaaf_d3_series(self) -> None:
        """NCAAF Division 3 series variant."""
        result = parse_event_ticker("KXNCAAFD3GAME-26JAN02ARMYNAVY", NCAAF_CODES)
        assert result is not None
        assert result.league == "ncaaf"
        assert result.series == "KXNCAAFD3GAME"
        assert result.away_team_code == "ARMY"
        assert result.home_team_code == "NAVY"

    def test_nba_2h_winner_series(self) -> None:
        """NBA second-half winner series variant."""
        result = parse_event_ticker("KXNBA2HWINNER-26MAR25OKCBOS", NBA_CODES)
        assert result is not None
        assert result.league == "nba"
        assert result.series == "KXNBA2HWINNER"

    def test_year_boundary_dec31(self) -> None:
        """Dec 31 date parsing."""
        result = parse_event_ticker("KXNFLGAME-25DEC31DALNYG", NFL_CODES)
        assert result is not None
        assert result.game_date == date(2025, 12, 31)

    def test_year_boundary_jan01(self) -> None:
        """Jan 1 date parsing."""
        result = parse_event_ticker("KXNFLGAME-26JAN01KCBUF", NFL_CODES)
        assert result is not None
        assert result.game_date == date(2026, 1, 1)

    def test_two_char_codes(self) -> None:
        """Shortest possible team codes (2 + 2)."""
        result = parse_event_ticker("KXNFLGAME-26JAN18NESF", NFL_CODES)
        assert result is not None
        assert result.away_team_code == "NE"
        assert result.home_team_code == "SF"

    def test_empty_string(self) -> None:
        result = parse_event_ticker("", NFL_CODES)
        assert result is None

    def test_none_input(self) -> None:
        result = parse_event_ticker(None, NFL_CODES)  # type: ignore[arg-type]
        assert result is None

    def test_non_sports_ticker(self) -> None:
        """Non-sports ticker (politics, crypto, etc.)."""
        result = parse_event_ticker("KXPOLITICS-PRES2028", NFL_CODES)
        assert result is None

    def test_no_hyphen(self) -> None:
        """Ticker with no hyphen separator."""
        result = parse_event_ticker("KXNFLGAME26JAN18HOUNE", NFL_CODES)
        assert result is None

    def test_malformed_date(self) -> None:
        """Invalid date in ticker."""
        result = parse_event_ticker("KXNFLGAME-26XXX18HOUNE", NFL_CODES)
        assert result is None

    def test_no_team_segment(self) -> None:
        """Ticker with date but no team codes."""
        result = parse_event_ticker("KXNFLGAME-26JAN18", NFL_CODES)
        assert result is None

    def test_no_valid_codes_provided(self) -> None:
        """Without valid codes, can't split teams."""
        result = parse_event_ticker("KXNFLGAME-26JAN18HOUNE", None)
        assert result is None

    def test_empty_valid_codes(self) -> None:
        """Empty code set yields no match."""
        result = parse_event_ticker("KXNFLGAME-26JAN18HOUNE", set())
        assert result is None

    def test_nhl_ticker(self) -> None:
        """Standard NHL game ticker."""
        result = parse_event_ticker("KXNHLGAME-26JAN15BOSTOR", NHL_CODES)
        assert result is not None
        assert result == ParsedTicker(
            series="KXNHLGAME",
            league="nhl",
            game_date=date(2026, 1, 15),
            away_team_code="BOS",
            home_team_code="TOR",
        )

    def test_nhl_two_char_codes(self) -> None:
        """NHL ticker with short team codes (TB + 3-char)."""
        result = parse_event_ticker("KXNHLGAME-26FEB20TBFLA", NHL_CODES)
        assert result is not None
        assert result.league == "nhl"
        assert result.away_team_code == "TB"
        assert result.home_team_code == "FLA"

    def test_mlb_ticker(self) -> None:
        """Standard MLB game ticker."""
        result = parse_event_ticker("KXMLBGAME-26APR05NYYHOU", MLB_CODES)
        assert result is not None
        assert result == ParsedTicker(
            series="KXMLBGAME",
            league="mlb",
            game_date=date(2026, 4, 5),
            away_team_code="NYY",
            home_team_code="HOU",
        )

    def test_mlb_three_char_codes(self) -> None:
        """MLB ticker with two 3-char codes."""
        result = parse_event_ticker("KXMLBGAME-26JUN15LADNYM", MLB_CODES)
        assert result is not None
        assert result.league == "mlb"
        assert result.away_team_code == "LAD"
        assert result.home_team_code == "NYM"

    def test_parsed_ticker_is_frozen(self) -> None:
        """ParsedTicker should be immutable (frozen dataclass)."""
        result = parse_event_ticker("KXNFLGAME-26JAN18HOUNE", NFL_CODES)
        assert result is not None
        with pytest.raises(AttributeError):
            result.league = "nba"  # type: ignore[misc]
