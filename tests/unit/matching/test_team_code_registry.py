"""Unit tests for TeamCodeRegistry.

Tests the in-memory cache of team code mappings used for matching
Kalshi events to games. Uses load_from_data() to avoid DB dependency.

Related:
    - Issue #462: Event-to-game matching
    - src/precog/matching/team_code_registry.py
"""

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
]

NBA_TEAMS: list[dict] = [
    {"team_code": "BOS", "league": "nba", "kalshi_team_code": None},
    {"team_code": "OKC", "league": "nba", "kalshi_team_code": None},
    {"team_code": "LAL", "league": "nba", "kalshi_team_code": None},
]

# NCAAF teams with 4-char Kalshi codes
NCAAF_TEAMS: list[dict] = [
    {"team_code": "WF", "league": "ncaaf", "kalshi_team_code": "WAKE"},
    {"team_code": "MSST", "league": "ncaaf", "kalshi_team_code": None},
    {"team_code": "TXST", "league": "ncaaf", "kalshi_team_code": None},
    {"team_code": "RICE", "league": "ncaaf", "kalshi_team_code": None},
]


class TestTeamCodeRegistry:
    """Tests for TeamCodeRegistry."""

    def test_load_from_data(self) -> None:
        """Registry loads data and reports as loaded."""
        registry = TeamCodeRegistry()
        assert not registry.is_loaded

        registry.load_from_data(NFL_TEAMS + NBA_TEAMS)
        assert registry.is_loaded

    def test_resolve_known_mismatch_jac(self) -> None:
        """JAC (Kalshi) resolves to JAX (ESPN)."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)

        result = registry.resolve_kalshi_to_espn("JAC", "nfl")
        assert result == "JAX"

    def test_resolve_known_mismatch_la(self) -> None:
        """LA (Kalshi) resolves to LAR (ESPN)."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)

        result = registry.resolve_kalshi_to_espn("LA", "nfl")
        assert result == "LAR"

    def test_resolve_matching_code(self) -> None:
        """HOU resolves to HOU (same on both platforms)."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)

        result = registry.resolve_kalshi_to_espn("HOU", "nfl")
        assert result == "HOU"

    def test_resolve_two_char_code(self) -> None:
        """NE and KC (2-char codes) resolve correctly."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)

        assert registry.resolve_kalshi_to_espn("NE", "nfl") == "NE"
        assert registry.resolve_kalshi_to_espn("KC", "nfl") == "KC"

    def test_resolve_unknown_code(self) -> None:
        """Unknown code returns None."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)

        result = registry.resolve_kalshi_to_espn("ZZZ", "nfl")
        assert result is None

    def test_resolve_wrong_league(self) -> None:
        """Code from wrong league returns None."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)

        # HOU exists in NFL but we ask for NBA
        result = registry.resolve_kalshi_to_espn("HOU", "nba")
        assert result is None

    def test_resolve_case_insensitive(self) -> None:
        """Lookup should work regardless of input case."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)

        assert registry.resolve_kalshi_to_espn("hou", "nfl") == "HOU"
        assert registry.resolve_kalshi_to_espn("jac", "nfl") == "JAX"

    def test_get_kalshi_codes_nfl(self) -> None:
        """Get all valid Kalshi codes for NFL."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)

        codes = registry.get_kalshi_codes("nfl")
        # Explicit mismatches use Kalshi code
        assert "JAC" in codes  # Kalshi code for Jacksonville
        assert "LA" in codes  # Kalshi code for Rams
        # Matching codes are in the set as-is
        assert "HOU" in codes
        assert "NE" in codes
        assert "KC" in codes
        assert "BUF" in codes
        assert "SF" in codes
        # ESPN codes for mismatched teams are NOT in the set
        assert "JAX" not in codes
        assert "LAR" not in codes

    def test_get_kalshi_codes_nba(self) -> None:
        """Get all valid Kalshi codes for NBA."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS + NBA_TEAMS)

        codes = registry.get_kalshi_codes("nba")
        assert "BOS" in codes
        assert "OKC" in codes
        assert "LAL" in codes
        assert len(codes) == 3

    def test_get_kalshi_codes_unknown_league(self) -> None:
        """Unknown league returns empty set."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)

        codes = registry.get_kalshi_codes("mlb")
        assert codes == set()

    def test_multi_league_isolation(self) -> None:
        """Codes for different leagues don't interfere."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS + NBA_TEAMS)

        nfl_codes = registry.get_kalshi_codes("nfl")
        nba_codes = registry.get_kalshi_codes("nba")

        # NFL has JAC, NBA doesn't
        assert "JAC" in nfl_codes
        assert "JAC" not in nba_codes

        # NBA has BOS, NFL doesn't (in our test data)
        assert "BOS" in nba_codes
        assert "BOS" not in nfl_codes

    def test_empty_data(self) -> None:
        """Loading empty data yields empty registry."""
        registry = TeamCodeRegistry()
        registry.load_from_data([])
        assert registry.is_loaded
        assert registry.get_kalshi_codes("nfl") == set()

    def test_teams_without_league_skipped(self) -> None:
        """Teams with missing league are skipped."""
        registry = TeamCodeRegistry()
        registry.load_from_data(
            [
                {"team_code": "TST", "league": "", "kalshi_team_code": None},
                {"team_code": "HOU", "league": "nfl", "kalshi_team_code": None},
            ]
        )
        assert registry.resolve_kalshi_to_espn("TST", "") is None
        assert registry.resolve_kalshi_to_espn("HOU", "nfl") == "HOU"

    def test_ncaaf_four_char_kalshi_code_resolves(self) -> None:
        """NCAAF 4-char Kalshi code (WAKE) resolves to ESPN code (WF)."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NCAAF_TEAMS)

        result = registry.resolve_kalshi_to_espn("WAKE", "ncaaf")
        assert result == "WF"

    def test_ncaaf_matching_code_resolves(self) -> None:
        """NCAAF team where Kalshi code matches ESPN code."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NCAAF_TEAMS)

        assert registry.resolve_kalshi_to_espn("MSST", "ncaaf") == "MSST"
        assert registry.resolve_kalshi_to_espn("TXST", "ncaaf") == "TXST"
        assert registry.resolve_kalshi_to_espn("RICE", "ncaaf") == "RICE"

    def test_get_kalshi_codes_ncaaf(self) -> None:
        """Get all valid Kalshi codes for NCAAF including 4-char codes."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NCAAF_TEAMS)

        codes = registry.get_kalshi_codes("ncaaf")
        assert "WAKE" in codes  # 4-char Kalshi code
        assert "MSST" in codes  # 4-char matching code
        assert "TXST" in codes
        assert "RICE" in codes
        assert len(codes) == 4
        # ESPN code for mismatched team should NOT be in the set
        assert "WF" not in codes

    def test_ncaaf_codes_isolated_from_nfl(self) -> None:
        """NCAAF codes don't leak into NFL results and vice versa."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS + NCAAF_TEAMS)

        nfl_codes = registry.get_kalshi_codes("nfl")
        ncaaf_codes = registry.get_kalshi_codes("ncaaf")

        # NCAAF-only codes should not appear in NFL
        assert "WAKE" not in nfl_codes
        assert "MSST" not in nfl_codes
        assert "TXST" not in nfl_codes
        assert "RICE" not in nfl_codes

        # NFL-only codes should not appear in NCAAF
        assert "JAC" not in ncaaf_codes
        assert "LA" not in ncaaf_codes

    def test_ncaaf_resolve_wrong_league_returns_none(self) -> None:
        """NCAAF Kalshi code queried with NFL league returns None."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS + NCAAF_TEAMS)

        # WAKE is NCAAF, not NFL
        assert registry.resolve_kalshi_to_espn("WAKE", "nfl") is None
        # JAC is NFL, not NCAAF
        assert registry.resolve_kalshi_to_espn("JAC", "ncaaf") is None

    def test_reload_replaces_data(self) -> None:
        """Loading new data replaces old data."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)
        assert "JAC" in registry.get_kalshi_codes("nfl")

        # Reload with only NBA data
        registry.load_from_data(NBA_TEAMS)
        # NFL data should be gone
        assert registry.get_kalshi_codes("nfl") == set()
        assert "BOS" in registry.get_kalshi_codes("nba")
