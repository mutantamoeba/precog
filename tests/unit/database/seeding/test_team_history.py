"""
Unit Tests for Team History Mapping.

Tests the unified team relocation/renaming tracking system across
multiple sports (NFL, NBA, MLB, NHL).

Issue: #257 - Extend team mapping to support multi-sport historical relocations

Test Coverage:
    - resolve_team_code(): Main API for code normalization
    - get_team_timeline(): Franchise history lookup
    - get_team_code_at_year(): Year-specific code lookup
    - get_all_historical_codes(): All codes for a franchise
    - Backward compatibility with TEAM_CODE_MAPPING
"""

from precog.database.seeding.team_history import (
    SPORT_CODE_MAPPINGS,
    TEAM_CODE_MAPPING,
    TEAM_HISTORY,
    get_all_historical_codes,
    get_franchise_count,
    get_supported_sports,
    get_team_code_at_year,
    get_team_timeline,
    is_known_relocation,
    normalize_team_code,
    resolve_team_code,
)

# =============================================================================
# Test: resolve_team_code() - Primary API
# =============================================================================


class TestResolveTeamCode:
    """Tests for resolve_team_code() - the main API."""

    # -------------------------------------------------------------------------
    # NFL Relocations
    # -------------------------------------------------------------------------

    def test_resolve_oakland_raiders_to_las_vegas(self) -> None:
        """Oakland Raiders (OAK) should resolve to Las Vegas (LV)."""
        assert resolve_team_code("nfl", "OAK") == "LV"
        assert resolve_team_code("nfl", "OAK", 2019) == "LV"
        assert resolve_team_code("nfl", "OAK", 1985) == "LV"

    def test_resolve_san_diego_chargers_to_la(self) -> None:
        """San Diego Chargers (SD) should resolve to LA Chargers (LAC)."""
        assert resolve_team_code("nfl", "SD") == "LAC"
        assert resolve_team_code("nfl", "SD", 2015) == "LAC"

    def test_resolve_st_louis_rams_to_la(self) -> None:
        """St. Louis Rams (STL) should resolve to LA Rams (LAR)."""
        assert resolve_team_code("nfl", "STL") == "LAR"
        assert resolve_team_code("nfl", "STL", 2014) == "LAR"

    def test_resolve_houston_oilers_to_tennessee(self) -> None:
        """Houston Oilers (HOU) should resolve to Tennessee Titans (TEN)."""
        assert resolve_team_code("nfl", "HOU") == "TEN"
        assert resolve_team_code("nfl", "HOU", 1995) == "TEN"

    def test_resolve_la_raiders_to_las_vegas(self) -> None:
        """LA Raiders (LA) should resolve to Las Vegas (LV)."""
        # LA Raiders were in LA from 1982-1994
        assert resolve_team_code("nfl", "LA") == "LV"

    def test_resolve_phoenix_cardinals_to_arizona(self) -> None:
        """Phoenix Cardinals (PHO) should resolve to Arizona (ARI)."""
        assert resolve_team_code("nfl", "PHO") == "ARI"

    # -------------------------------------------------------------------------
    # NBA Relocations
    # -------------------------------------------------------------------------

    def test_resolve_seattle_supersonics_to_okc(self) -> None:
        """Seattle SuperSonics (SEA) should resolve to OKC Thunder."""
        assert resolve_team_code("nba", "SEA") == "OKC"
        assert resolve_team_code("nba", "SEA", 2007) == "OKC"

    def test_resolve_new_jersey_nets_to_brooklyn(self) -> None:
        """New Jersey Nets (NJN) should resolve to Brooklyn (BKN)."""
        assert resolve_team_code("nba", "NJN") == "BKN"
        assert resolve_team_code("nba", "NJN", 2011) == "BKN"

    def test_resolve_vancouver_grizzlies_to_memphis(self) -> None:
        """Vancouver Grizzlies (VAN) should resolve to Memphis (MEM)."""
        assert resolve_team_code("nba", "VAN") == "MEM"

    def test_resolve_kansas_city_kings_to_sacramento(self) -> None:
        """Kansas City Kings (KC) should resolve to Sacramento (SAC)."""
        assert resolve_team_code("nba", "KC") == "SAC"

    # -------------------------------------------------------------------------
    # MLB Relocations
    # -------------------------------------------------------------------------

    def test_resolve_montreal_expos_to_washington(self) -> None:
        """Montreal Expos (MON) should resolve to Washington Nationals (WAS)."""
        assert resolve_team_code("mlb", "MON") == "WAS"
        assert resolve_team_code("mlb", "MON", 2004) == "WAS"

    def test_resolve_brooklyn_dodgers_to_la(self) -> None:
        """Brooklyn Dodgers (BRO) should resolve to LA Dodgers (LAD)."""
        assert resolve_team_code("mlb", "BRO") == "LAD"

    def test_resolve_seattle_pilots_to_milwaukee(self) -> None:
        """Seattle Pilots (SEP) should resolve to Milwaukee Brewers (MIL)."""
        assert resolve_team_code("mlb", "SEP") == "MIL"

    # -------------------------------------------------------------------------
    # NHL Relocations
    # -------------------------------------------------------------------------

    def test_resolve_atlanta_thrashers_to_winnipeg(self) -> None:
        """Atlanta Thrashers (ATL) should resolve to Winnipeg Jets (WPG)."""
        assert resolve_team_code("nhl", "ATL") == "WPG"

    def test_resolve_hartford_whalers_to_carolina(self) -> None:
        """Hartford Whalers (HFD) should resolve to Carolina Hurricanes (CAR)."""
        assert resolve_team_code("nhl", "HFD") == "CAR"

    def test_resolve_quebec_nordiques_to_colorado(self) -> None:
        """Quebec Nordiques (QUE) should resolve to Colorado Avalanche (COL)."""
        assert resolve_team_code("nhl", "QUE") == "COL"

    def test_resolve_phoenix_coyotes_to_arizona(self) -> None:
        """Phoenix Coyotes (PHX) should resolve to Arizona (ARI)."""
        assert resolve_team_code("nhl", "PHX") == "ARI"

    # -------------------------------------------------------------------------
    # No Mapping Needed
    # -------------------------------------------------------------------------

    def test_current_code_unchanged(self) -> None:
        """Current team codes should pass through unchanged."""
        # NFL
        assert resolve_team_code("nfl", "KC") == "KC"
        assert resolve_team_code("nfl", "NE") == "NE"
        assert resolve_team_code("nfl", "DAL") == "DAL"

        # NBA
        assert resolve_team_code("nba", "LAL") == "LAL"
        assert resolve_team_code("nba", "BOS") == "BOS"

        # MLB
        assert resolve_team_code("mlb", "NYY") == "NYY"

        # NHL
        assert resolve_team_code("nhl", "TOR") == "TOR"

    def test_case_insensitive(self) -> None:
        """Team codes should be case-insensitive."""
        assert resolve_team_code("nfl", "oak") == "LV"
        assert resolve_team_code("nfl", "Oak") == "LV"
        assert resolve_team_code("NFL", "OAK") == "LV"
        assert resolve_team_code("Nfl", "oak") == "LV"

    def test_whitespace_stripped(self) -> None:
        """Whitespace should be stripped from codes."""
        assert resolve_team_code("nfl", " OAK ") == "LV"
        assert resolve_team_code(" nfl ", "OAK") == "LV"


# =============================================================================
# Test: get_team_timeline()
# =============================================================================


class TestGetTeamTimeline:
    """Tests for get_team_timeline() - franchise history lookup."""

    def test_raiders_timeline(self) -> None:
        """Raiders timeline should show Oakland -> LA -> Oakland -> LV."""
        timeline = get_team_timeline("nfl", "LV")
        assert timeline is not None
        assert len(timeline) == 4

        # First: Oakland 1960-1981
        assert timeline[0] == ("OAK", 1960, 1981)
        # Second: LA 1982-1994
        assert timeline[1] == ("LA", 1982, 1994)
        # Third: Oakland 1995-2019
        assert timeline[2] == ("OAK", 1995, 2019)
        # Fourth: Las Vegas 2020-present
        assert timeline[3] == ("LV", 2020, None)

    def test_supersonics_timeline(self) -> None:
        """Thunder timeline should show Seattle -> OKC."""
        timeline = get_team_timeline("nba", "OKC")
        assert timeline is not None
        assert len(timeline) == 2

        # Sonics last season: 2007-08 (year=2007), Thunder first: 2008-09 (year=2008)
        assert timeline[0] == ("SEA", 1967, 2007)
        assert timeline[1] == ("OKC", 2008, None)

    def test_unknown_team_returns_none(self) -> None:
        """Unknown team should return None."""
        assert get_team_timeline("nfl", "XYZ") is None
        assert get_team_timeline("unknown", "KC") is None


# =============================================================================
# Test: get_team_code_at_year()
# =============================================================================


class TestGetTeamCodeAtYear:
    """Tests for get_team_code_at_year() - year-specific lookups."""

    def test_raiders_at_different_years(self) -> None:
        """Raiders code should match the location at each year."""
        # Oakland era 1
        assert get_team_code_at_year("nfl", "LV", 1970) == "OAK"
        assert get_team_code_at_year("nfl", "LV", 1981) == "OAK"

        # LA era
        assert get_team_code_at_year("nfl", "LV", 1982) == "LA"
        assert get_team_code_at_year("nfl", "LV", 1990) == "LA"
        assert get_team_code_at_year("nfl", "LV", 1994) == "LA"

        # Oakland era 2
        assert get_team_code_at_year("nfl", "LV", 1995) == "OAK"
        assert get_team_code_at_year("nfl", "LV", 2019) == "OAK"

        # Las Vegas era
        assert get_team_code_at_year("nfl", "LV", 2020) == "LV"
        assert get_team_code_at_year("nfl", "LV", 2023) == "LV"

    def test_supersonics_at_different_years(self) -> None:
        """Thunder code should match Seattle before 2008."""
        assert get_team_code_at_year("nba", "OKC", 2007) == "SEA"
        assert get_team_code_at_year("nba", "OKC", 2008) == "OKC"
        assert get_team_code_at_year("nba", "OKC", 2023) == "OKC"

    def test_year_before_franchise_returns_none(self) -> None:
        """Year before franchise existed should return None."""
        # Thunder (originally Sonics 1967) didn't exist in 1950
        assert get_team_code_at_year("nba", "OKC", 1950) is None


# =============================================================================
# Test: get_all_historical_codes()
# =============================================================================


class TestGetAllHistoricalCodes:
    """Tests for get_all_historical_codes() - all franchise codes."""

    def test_raiders_all_codes(self) -> None:
        """Raiders should have OAK, LA, LV codes."""
        codes = get_all_historical_codes("nfl", "LV")
        assert "OAK" in codes
        assert "LA" in codes
        assert "LV" in codes
        # OAK appears twice in timeline but should only be in list once
        assert codes.count("OAK") == 1

    def test_supersonics_all_codes(self) -> None:
        """Thunder should have SEA and OKC codes."""
        codes = get_all_historical_codes("nba", "OKC")
        assert codes == ["SEA", "OKC"]

    def test_unknown_team_returns_code(self) -> None:
        """Unknown team should return the code itself."""
        codes = get_all_historical_codes("nfl", "KC")
        assert codes == ["KC"]


# =============================================================================
# Test: is_known_relocation()
# =============================================================================


class TestIsKnownRelocation:
    """Tests for is_known_relocation() - check if code is in history."""

    def test_known_relocations(self) -> None:
        """Known relocated teams should return True."""
        assert is_known_relocation("nfl", "OAK") is True
        assert is_known_relocation("nfl", "SD") is True
        assert is_known_relocation("nba", "SEA") is True
        assert is_known_relocation("mlb", "MON") is True
        assert is_known_relocation("nhl", "HFD") is True

    def test_current_teams_not_relocated(self) -> None:
        """Teams that haven't relocated return False."""
        assert is_known_relocation("nfl", "KC") is False
        assert is_known_relocation("nfl", "NE") is False
        assert is_known_relocation("nba", "LAL") is False


# =============================================================================
# Test: Utility Functions
# =============================================================================


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_supported_sports(self) -> None:
        """Should return all sports with data."""
        sports = get_supported_sports()
        assert "nfl" in sports
        assert "nba" in sports
        assert "mlb" in sports
        assert "nhl" in sports

    def test_get_franchise_count(self) -> None:
        """Should return count of franchises with history."""
        # NFL has several teams with relocation history
        nfl_count = get_franchise_count("nfl")
        assert nfl_count >= 5  # At minimum: LV, TEN, IND, LAC, LAR

        # Unknown sport should return 0
        assert get_franchise_count("cricket") == 0


# =============================================================================
# Test: Backward Compatibility
# =============================================================================


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing code."""

    def test_team_code_mapping_dict(self) -> None:
        """TEAM_CODE_MAPPING legacy dict should have safe cross-sport mappings."""
        # Legacy dict is now minimal - only safe cross-sport mappings
        assert TEAM_CODE_MAPPING["WSH"] == "WAS"

    def test_sport_code_mappings_dict(self) -> None:
        """SPORT_CODE_MAPPINGS should have sport-specific mappings."""
        # NFL-specific mappings
        assert SPORT_CODE_MAPPINGS["nfl"]["OAK"] == "LV"
        assert SPORT_CODE_MAPPINGS["nfl"]["SD"] == "LAC"
        assert SPORT_CODE_MAPPINGS["nfl"]["STL"] == "LAR"

        # NBA-specific mappings
        assert SPORT_CODE_MAPPINGS["nba"]["SEA"] == "OKC"
        assert SPORT_CODE_MAPPINGS["nba"]["NJN"] == "BKN"

        # MLB-specific mappings
        assert SPORT_CODE_MAPPINGS["mlb"]["MON"] == "WAS"
        assert SPORT_CODE_MAPPINGS["mlb"]["BRO"] == "LAD"

        # NHL-specific mappings
        assert SPORT_CODE_MAPPINGS["nhl"]["ATL"] == "WPG"
        assert SPORT_CODE_MAPPINGS["nhl"]["VEG"] == "VGK"

    def test_no_cross_sport_contamination(self) -> None:
        """Bug fix: SEA should not map to OKC in NHL (only NBA).

        Issue: #257 - Seattle Kraken (NHL) was incorrectly mapping to
        Oklahoma City Thunder (NBA) due to sport-agnostic mapping.
        """
        # NHL SEA (Seattle Kraken) should stay as SEA
        assert resolve_team_code("nhl", "SEA") == "SEA"

        # NBA SEA (Seattle SuperSonics) should map to OKC
        assert resolve_team_code("nba", "SEA") == "OKC"

        # NHL ATL (Atlanta Thrashers) should map to WPG
        assert resolve_team_code("nhl", "ATL") == "WPG"

        # NFL ATL (Atlanta Falcons) should stay as ATL
        assert resolve_team_code("nfl", "ATL") == "ATL"

    def test_normalize_team_code_legacy(self) -> None:
        """normalize_team_code() should work for backward compatibility."""
        assert normalize_team_code("OAK") == "LV"
        assert normalize_team_code("SD") == "LAC"
        assert normalize_team_code("KC") == "KC"  # No mapping needed


# =============================================================================
# Test: Data Integrity
# =============================================================================


class TestDataIntegrity:
    """Tests for data structure integrity."""

    def test_all_timelines_have_entries(self) -> None:
        """Every team in TEAM_HISTORY should have at least one timeline entry."""
        for sport, teams in TEAM_HISTORY.items():
            for code, timeline in teams.items():
                assert len(timeline) >= 1, f"{sport}/{code} has empty timeline"

    def test_timeline_years_are_valid(self) -> None:
        """Timeline years should be reasonable (1870-2100)."""
        for sport, teams in TEAM_HISTORY.items():
            for code, timeline in teams.items():
                for hist_code, start, end in timeline:
                    assert 1870 <= start <= 2100, f"Invalid start year for {sport}/{code}: {start}"
                    if end is not None:
                        assert 1870 <= end <= 2100, f"Invalid end year for {sport}/{code}: {end}"
                        assert start <= end, f"Start > end for {sport}/{code}: {start} > {end}"

    def test_timeline_entries_are_chronological(self) -> None:
        """Timeline entries should be in chronological order."""
        for sport, teams in TEAM_HISTORY.items():
            for code, timeline in teams.items():
                prev_end = None
                for _, start, end in timeline:
                    if prev_end is not None:
                        # Allow 1-year gap for transitions
                        assert start >= prev_end - 1, f"Timeline overlap for {sport}/{code}"
                    prev_end = end if end else 9999

    def test_no_empty_codes(self) -> None:
        """Historical codes should not be empty strings."""
        for sport, teams in TEAM_HISTORY.items():
            for code, timeline in teams.items():
                for hist_code, _, _ in timeline:
                    assert hist_code, f"Empty code in {sport}/{code} timeline"
                    assert hist_code.strip() == hist_code, f"Whitespace in {sport}/{code}"
