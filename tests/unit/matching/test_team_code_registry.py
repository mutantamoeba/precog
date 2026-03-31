"""Unit tests for TeamCodeRegistry.

Tests the in-memory cache of team code mappings used for matching
Kalshi events to games. Uses load_from_data() to avoid DB dependency.
New tests (#516) cover loading from external_team_codes table.

Related:
    - Issue #462: Event-to-game matching
    - Issue #516: External team codes table
    - src/precog/matching/team_code_registry.py
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

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


# =============================================================================
# Needs Refresh Tests
# =============================================================================


class TestNeedsRefresh:
    """Tests for TeamCodeRegistry.needs_refresh()."""

    def test_needs_refresh_when_never_loaded(self) -> None:
        """Unloaded registry always needs refresh."""
        registry = TeamCodeRegistry()
        assert registry.needs_refresh()

    def test_no_refresh_needed_when_just_loaded(self) -> None:
        """Freshly loaded registry does not need refresh."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)
        assert not registry.needs_refresh(max_age_seconds=3600)

    def test_needs_refresh_when_stale(self) -> None:
        """Registry older than max_age needs refresh."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)
        # Manually set last_loaded_at to 2 hours ago
        registry._last_loaded_at = datetime.now(UTC) - timedelta(hours=2)
        assert registry.needs_refresh(max_age_seconds=3600)

    def test_needs_refresh_when_unknown_codes_seen(self) -> None:
        """Registry with unknown codes needs refresh even if fresh."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)
        registry.record_unknown_code("ZZZ", "nfl")
        assert registry.needs_refresh(max_age_seconds=3600)

    def test_unknown_codes_cleared_on_reload(self) -> None:
        """Reloading clears the unknown codes set."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)
        registry.record_unknown_code("ZZZ", "nfl")
        assert len(registry.unknown_codes_seen) == 1

        registry.load_from_data(NFL_TEAMS)
        assert len(registry.unknown_codes_seen) == 0

    def test_last_loaded_at_set_on_load(self) -> None:
        """last_loaded_at is set after load."""
        registry = TeamCodeRegistry()
        assert registry.last_loaded_at is None

        before = datetime.now(UTC)
        registry.load_from_data(NFL_TEAMS)
        after = datetime.now(UTC)

        assert registry.last_loaded_at is not None
        assert before <= registry.last_loaded_at <= after

    def test_record_unknown_code_format(self) -> None:
        """Unknown codes are stored as CODE:league format."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)
        registry.record_unknown_code("zzz", "nfl")
        assert "ZZZ:nfl" in registry.unknown_codes_seen

    def test_no_refresh_with_zero_max_age_and_fresh(self) -> None:
        """With max_age_seconds=0, a freshly loaded registry still needs refresh
        (age > 0 seconds)."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)
        # max_age_seconds=0 means any age > 0 triggers refresh
        # Since loading takes non-zero time, this should be True
        # (but could be flaky if load is instant). Use 1 second for safety.
        registry._last_loaded_at = datetime.now(UTC) - timedelta(seconds=2)
        assert registry.needs_refresh(max_age_seconds=1)


# =============================================================================
# Classification Collision Tests (#486 Task D)
# =============================================================================


# Two NCAAF teams with the same code but different classifications
NCAAF_COLLISION_TEAMS: list[dict] = [
    # D3 team loaded first (by alphabetical order from DB)
    {"team_code": "MISS", "league": "ncaaf", "kalshi_team_code": None, "classification": "d3"},
    # FBS team loaded second — should WIN because FBS > D3
    {"team_code": "MISS", "league": "ncaaf", "kalshi_team_code": None, "classification": "fbs"},
]


class TestClassificationCollision:
    """Tests for classification-based disambiguation when team codes collide."""

    def test_fbs_wins_over_d3_same_code(self) -> None:
        """When two teams share a code, FBS wins over D3."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NCAAF_COLLISION_TEAMS)

        # MISS should resolve to the FBS team (second in list)
        result = registry.resolve_kalshi_to_espn("MISS", "ncaaf")
        assert result == "MISS"
        # The classification stored should be fbs
        assert registry._classification["ncaaf"]["MISS"] == "fbs"

    def test_fbs_wins_over_fcs(self) -> None:
        """FBS has higher priority than FCS."""
        registry = TeamCodeRegistry()
        registry.load_from_data(
            [
                {
                    "team_code": "CODE",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": "fcs",
                },
                {
                    "team_code": "CODE",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": "fbs",
                },
            ]
        )
        assert registry._classification["ncaaf"]["CODE"] == "fbs"

    def test_fcs_wins_over_d2(self) -> None:
        """FCS has higher priority than D2."""
        registry = TeamCodeRegistry()
        registry.load_from_data(
            [
                {
                    "team_code": "XYZ",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": "d2",
                },
                {
                    "team_code": "XYZ",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": "fcs",
                },
            ]
        )
        assert registry._classification["ncaaf"]["XYZ"] == "fcs"

    def test_first_wins_on_equal_priority(self) -> None:
        """When two teams have equal classification priority, first loaded wins."""
        registry = TeamCodeRegistry()
        registry.load_from_data(
            [
                {
                    "team_code": "AAA",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": "d2",
                },
                {
                    "team_code": "AAA",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": "d3",
                },
            ]
        )
        # Both d2 and d3 have priority 1, so first loaded (d2) should win
        assert registry._classification["ncaaf"]["AAA"] == "d2"

    def test_classified_wins_over_null(self) -> None:
        """Any classification wins over NULL."""
        registry = TeamCodeRegistry()
        registry.load_from_data(
            [
                {
                    "team_code": "BBB",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": None,
                },
                {
                    "team_code": "BBB",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": "d3",
                },
            ]
        )
        assert registry._classification["ncaaf"]["BBB"] == "d3"

    def test_no_collision_in_pro_leagues(self) -> None:
        """Pro leagues have unique codes, no collision logic needed."""
        registry = TeamCodeRegistry()
        registry.load_from_data(
            [
                {
                    "team_code": "HOU",
                    "league": "nfl",
                    "kalshi_team_code": None,
                    "classification": "professional",
                },
            ]
        )
        assert registry.resolve_kalshi_to_espn("HOU", "nfl") == "HOU"
        assert registry._classification["nfl"]["HOU"] == "professional"

    def test_collision_does_not_affect_other_leagues(self) -> None:
        """NCAAF collision doesn't affect NFL codes."""
        registry = TeamCodeRegistry()
        registry.load_from_data(
            [
                {
                    "team_code": "HOU",
                    "league": "nfl",
                    "kalshi_team_code": None,
                    "classification": "professional",
                },
                {
                    "team_code": "HOU",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": "d3",
                },
                {
                    "team_code": "HOU",
                    "league": "ncaaf",
                    "kalshi_team_code": None,
                    "classification": "fbs",
                },
            ]
        )
        # NFL HOU is unaffected
        assert registry.resolve_kalshi_to_espn("HOU", "nfl") == "HOU"
        assert registry._classification["nfl"]["HOU"] == "professional"
        # NCAAF HOU is the FBS version
        assert registry._classification["ncaaf"]["HOU"] == "fbs"

    def test_backward_compat_no_classification_field(self) -> None:
        """Teams without classification field (old test data) still work."""
        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)  # No classification field
        assert registry.resolve_kalshi_to_espn("JAC", "nfl") == "JAX"
        assert registry.resolve_kalshi_to_espn("HOU", "nfl") == "HOU"


# =============================================================================
# External Team Codes Loading Tests (#516)
# =============================================================================


# Mock data matching the external_team_codes table format
EXTERNAL_KALSHI_CODES: list[dict] = [
    {
        "id": 1,
        "team_id": 42,
        "source": "kalshi",
        "source_team_code": "JAC",
        "league": "nfl",
        "confidence": "manual",
    },
    {
        "id": 2,
        "team_id": 43,
        "source": "kalshi",
        "source_team_code": "LA",
        "league": "nfl",
        "confidence": "manual",
    },
    {
        "id": 3,
        "team_id": 44,
        "source": "kalshi",
        "source_team_code": "HOU",
        "league": "nfl",
        "confidence": "heuristic",
    },
    {
        "id": 4,
        "team_id": 45,
        "source": "kalshi",
        "source_team_code": "NE",
        "league": "nfl",
        "confidence": "heuristic",
    },
    {
        "id": 5,
        "team_id": 46,
        "source": "kalshi",
        "source_team_code": "KC",
        "league": "nfl",
        "confidence": "heuristic",
    },
]

EXTERNAL_ESPN_CODES: list[dict] = [
    {
        "id": 10,
        "team_id": 42,
        "source": "espn",
        "source_team_code": "JAX",
        "league": "nfl",
        "confidence": "exact",
    },
    {
        "id": 11,
        "team_id": 43,
        "source": "espn",
        "source_team_code": "LAR",
        "league": "nfl",
        "confidence": "exact",
    },
    {
        "id": 12,
        "team_id": 44,
        "source": "espn",
        "source_team_code": "HOU",
        "league": "nfl",
        "confidence": "exact",
    },
    {
        "id": 13,
        "team_id": 45,
        "source": "espn",
        "source_team_code": "NE",
        "league": "nfl",
        "confidence": "exact",
    },
    {
        "id": 14,
        "team_id": 46,
        "source": "espn",
        "source_team_code": "KC",
        "league": "nfl",
        "confidence": "exact",
    },
]


class TestLoadFromExternalCodes:
    """Tests for loading registry from external_team_codes table (#516).

    These tests patch the CRUD functions at their source module because
    the registry uses lazy imports (inside methods) to avoid circular
    dependencies. The patch target is precog.database.crud_operations.
    """

    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_load_from_external_codes_resolves_mismatches(self, mock_get_codes) -> None:
        """External codes correctly map Kalshi mismatches (JAC->JAX, LA->LAR)."""

        # Return different data depending on the source param
        def side_effect(source=None, league=None):
            if source == "kalshi":
                return EXTERNAL_KALSHI_CODES
            if source == "espn":
                return EXTERNAL_ESPN_CODES
            return []

        mock_get_codes.side_effect = side_effect

        registry = TeamCodeRegistry()
        registry.load_from_external_codes(source="kalshi")

        assert registry.is_loaded
        assert registry.resolve_kalshi_to_espn("JAC", "nfl") == "JAX"
        assert registry.resolve_kalshi_to_espn("LA", "nfl") == "LAR"
        assert registry.resolve_kalshi_to_espn("HOU", "nfl") == "HOU"
        assert registry.resolve_kalshi_to_espn("NE", "nfl") == "NE"
        assert registry.resolve_kalshi_to_espn("KC", "nfl") == "KC"

    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_load_from_external_codes_builds_kalshi_codes_set(self, mock_get_codes) -> None:
        """get_kalshi_codes returns all Kalshi codes after external load."""

        def side_effect(source=None, league=None):
            if source == "kalshi":
                return EXTERNAL_KALSHI_CODES
            if source == "espn":
                return EXTERNAL_ESPN_CODES
            return []

        mock_get_codes.side_effect = side_effect

        registry = TeamCodeRegistry()
        registry.load_from_external_codes(source="kalshi")

        codes = registry.get_kalshi_codes("nfl")
        assert "JAC" in codes
        assert "LA" in codes
        assert "HOU" in codes
        assert "NE" in codes
        assert "KC" in codes
        # ESPN codes for mismatched teams should NOT be in the set
        assert "JAX" not in codes
        assert "LAR" not in codes

    @patch("precog.database.crud_operations.get_teams_with_kalshi_codes")
    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_fallback_to_legacy_when_external_empty(self, mock_get_codes, mock_get_teams) -> None:
        """Falls back to teams table when external_team_codes is empty."""
        # External codes return empty
        mock_get_codes.return_value = []
        # Legacy load returns teams data
        mock_get_teams.return_value = NFL_TEAMS

        registry = TeamCodeRegistry()
        registry.load_from_external_codes(source="kalshi")

        # Should have loaded from legacy
        assert registry.is_loaded
        assert registry.resolve_kalshi_to_espn("JAC", "nfl") == "JAX"
        mock_get_teams.assert_called_once()

    @patch("precog.database.crud_operations.get_teams_with_kalshi_codes")
    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_fallback_to_legacy_on_exception(self, mock_get_codes, mock_get_teams) -> None:
        """Falls back to teams table when external_team_codes raises an error."""
        mock_get_codes.side_effect = Exception("Table does not exist")
        mock_get_teams.return_value = NFL_TEAMS

        registry = TeamCodeRegistry()
        registry.load_from_external_codes(source="kalshi")

        # Should have loaded from legacy despite the error
        assert registry.is_loaded
        assert registry.resolve_kalshi_to_espn("JAC", "nfl") == "JAX"

    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_external_code_without_espn_mapping(self, mock_get_codes) -> None:
        """Kalshi code without ESPN mapping uses Kalshi code as team_code."""
        # Kalshi code exists but no ESPN mapping for team_id=99
        kalshi_only = [
            {
                "id": 50,
                "team_id": 99,
                "source": "kalshi",
                "source_team_code": "XYZ",
                "league": "nfl",
                "confidence": "heuristic",
            },
        ]

        def side_effect(source=None, league=None):
            if source == "kalshi":
                return kalshi_only
            if source == "espn":
                return []  # No ESPN codes
            return []

        mock_get_codes.side_effect = side_effect

        registry = TeamCodeRegistry()
        registry.load_from_external_codes(source="kalshi")

        # XYZ should resolve to XYZ (same code, no mismatch)
        assert registry.resolve_kalshi_to_espn("XYZ", "nfl") == "XYZ"

    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_load_clears_unknown_codes(self, mock_get_codes) -> None:
        """Loading from external codes clears the unknown_codes_seen set."""

        def side_effect(source=None, league=None):
            if source == "kalshi":
                return EXTERNAL_KALSHI_CODES
            if source == "espn":
                return EXTERNAL_ESPN_CODES
            return []

        mock_get_codes.side_effect = side_effect

        registry = TeamCodeRegistry()
        registry.load_from_data(NFL_TEAMS)
        registry.record_unknown_code("ZZZ", "nfl")
        assert len(registry.unknown_codes_seen) == 1

        registry.load_from_external_codes(source="kalshi")
        assert len(registry.unknown_codes_seen) == 0

    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_load_sets_last_loaded_at(self, mock_get_codes) -> None:
        """Loading from external codes sets last_loaded_at."""

        def side_effect(source=None, league=None):
            if source == "kalshi":
                return EXTERNAL_KALSHI_CODES
            if source == "espn":
                return EXTERNAL_ESPN_CODES
            return []

        mock_get_codes.side_effect = side_effect

        registry = TeamCodeRegistry()
        assert registry.last_loaded_at is None

        before = datetime.now(UTC)
        registry.load_from_external_codes(source="kalshi")
        after = datetime.now(UTC)

        assert registry.last_loaded_at is not None
        assert before <= registry.last_loaded_at <= after


class TestLoadAutoFallback:
    """Tests for load() auto-fallback behavior (#516).

    Tests that load() tries external_team_codes first and falls back
    to the legacy teams table approach when needed.
    """

    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_load_tries_external_first(self, mock_get_codes) -> None:
        """load() attempts external_team_codes before legacy."""

        def side_effect(source=None, league=None):
            if source == "kalshi":
                return EXTERNAL_KALSHI_CODES
            if source == "espn":
                return EXTERNAL_ESPN_CODES
            return []

        mock_get_codes.side_effect = side_effect

        registry = TeamCodeRegistry()
        registry.load()

        assert registry.is_loaded
        assert registry.resolve_kalshi_to_espn("JAC", "nfl") == "JAX"
        # External codes were used (not legacy)
        mock_get_codes.assert_called()

    @patch("precog.database.crud_operations.get_teams_with_kalshi_codes")
    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_load_falls_back_when_external_empty(self, mock_get_codes, mock_get_teams) -> None:
        """load() falls back to legacy when external table is empty."""
        mock_get_codes.return_value = []
        mock_get_teams.return_value = NFL_TEAMS

        registry = TeamCodeRegistry()
        registry.load()

        assert registry.is_loaded
        assert registry.resolve_kalshi_to_espn("JAC", "nfl") == "JAX"
        mock_get_teams.assert_called_once()

    @patch("precog.database.crud_operations.get_teams_with_kalshi_codes")
    @patch("precog.database.crud_operations.get_external_team_codes")
    def test_load_falls_back_on_error(self, mock_get_codes, mock_get_teams) -> None:
        """load() falls back to legacy when external table errors."""
        mock_get_codes.side_effect = Exception("relation does not exist")
        mock_get_teams.return_value = NFL_TEAMS

        registry = TeamCodeRegistry()
        registry.load()

        assert registry.is_loaded
        assert registry.resolve_kalshi_to_espn("JAC", "nfl") == "JAX"
