"""
Unit Tests for EloEngine.

Tests the core Elo rating computation engine including:
- Expected score calculations
- Rating updates with various outcomes
- Sport-specific configurations
- Margin-of-victory adjustments
- Season regression

Reference: TESTING_STRATEGY V3.2 - Unit tests for isolated component testing
Reference: docs/guides/ELO_COMPUTATION_GUIDE_V1.1.md
Related Requirements: REQ-ELO-001 through REQ-ELO-007

Usage:
    pytest tests/unit/analytics/test_elo_engine_unit.py -v -m unit
"""

from decimal import Decimal

import pytest

from precog.analytics.elo_engine import (
    DEFAULT_CARRYOVER_WEIGHT,
    DEFAULT_INITIAL_RATING,
    DEFAULT_REGRESSION_TARGET,
    ELO_DIVISOR,
    SPORT_CONFIGS,
    EloEngine,
    EloState,
    EloUpdateResult,
    Sport,
    SportConfig,
    elo_to_win_probability,
    get_elo_engine,
    win_probability_to_elo_difference,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def nfl_engine() -> EloEngine:
    """Create an NFL EloEngine for testing."""
    return EloEngine("nfl")


@pytest.fixture
def nba_engine() -> EloEngine:
    """Create an NBA EloEngine for testing."""
    return EloEngine("nba")


@pytest.fixture
def nhl_engine() -> EloEngine:
    """Create an NHL EloEngine for testing."""
    return EloEngine("nhl")


# =============================================================================
# Unit Tests: Engine Initialization
# =============================================================================


@pytest.mark.unit
class TestEloEngineInit:
    """Unit tests for EloEngine initialization."""

    def test_init_with_string_sport(self) -> None:
        """Test initialization with lowercase sport string."""
        engine = EloEngine("nfl")
        assert engine.sport == Sport.NFL
        assert engine.k_factor == 20
        assert engine.home_advantage == Decimal("48")

    def test_init_with_uppercase_sport(self) -> None:
        """Test initialization with uppercase sport string is normalized."""
        engine = EloEngine("NFL")
        assert engine.sport == Sport.NFL

    def test_init_with_sport_enum(self) -> None:
        """Test initialization with Sport enum directly."""
        engine = EloEngine(Sport.NBA)
        assert engine.sport == Sport.NBA

    def test_init_with_invalid_sport_raises_error(self) -> None:
        """Test initialization with invalid sport raises ValueError."""
        with pytest.raises(ValueError, match="Unknown sport 'invalid'"):
            EloEngine("invalid")

    def test_init_with_custom_config(self) -> None:
        """Test initialization with custom configuration."""
        custom_config = SportConfig(
            k_factor=50,
            home_advantage=Decimal("100"),
            mov_enabled=False,
        )
        engine = EloEngine("nfl", config=custom_config)
        assert engine.k_factor == 50
        assert engine.home_advantage == Decimal("100")

    def test_all_sports_have_configs(self) -> None:
        """Test all Sport enum values have configurations."""
        for sport in Sport:
            assert sport in SPORT_CONFIGS
            engine = EloEngine(sport)
            assert engine.config is not None


# =============================================================================
# Unit Tests: Expected Score Calculation
# =============================================================================


@pytest.mark.unit
class TestExpectedScore:
    """Unit tests for expected score (win probability) calculation."""

    def test_equal_ratings_gives_50_percent(self, nfl_engine: EloEngine) -> None:
        """Test that equal ratings give 50% expected score."""
        expected = nfl_engine.expected_score(
            team_elo=Decimal("1500"),
            opponent_elo=Decimal("1500"),
        )
        assert expected == Decimal("0.5")

    def test_higher_rating_gives_higher_expected(self, nfl_engine: EloEngine) -> None:
        """Test that higher rating gives expected score > 50%."""
        expected = nfl_engine.expected_score(
            team_elo=Decimal("1600"),
            opponent_elo=Decimal("1400"),
        )
        # 200 point difference should give ~76% expected
        assert expected > Decimal("0.75")
        assert expected < Decimal("0.78")

    def test_lower_rating_gives_lower_expected(self, nfl_engine: EloEngine) -> None:
        """Test that lower rating gives expected score < 50%."""
        expected = nfl_engine.expected_score(
            team_elo=Decimal("1400"),
            opponent_elo=Decimal("1600"),
        )
        # Should be complement of 200 point favorite
        assert expected > Decimal("0.22")
        assert expected < Decimal("0.25")

    def test_expected_scores_sum_to_one(self, nfl_engine: EloEngine) -> None:
        """Test that expected scores for both teams sum to 1."""
        team_a = Decimal("1650")
        team_b = Decimal("1350")

        expected_a = nfl_engine.expected_score(team_a, team_b)
        expected_b = nfl_engine.expected_score(team_b, team_a)

        total = expected_a + expected_b
        assert Decimal("0.9999") <= total <= Decimal("1.0001")

    def test_400_point_difference_gives_90_percent(self, nfl_engine: EloEngine) -> None:
        """Test that 400 point difference gives ~90% expected score.

        Educational Note:
            The Elo formula is designed so that a 400-point difference
            corresponds to approximately 10:1 odds (90.9% win probability).
        """
        expected = nfl_engine.expected_score(
            team_elo=Decimal("1700"),
            opponent_elo=Decimal("1300"),
        )
        # Should be approximately 90.9%
        assert Decimal("0.90") <= expected <= Decimal("0.92")

    def test_expected_score_precision(self, nfl_engine: EloEngine) -> None:
        """Test expected score returns 4 decimal places."""
        expected = nfl_engine.expected_score(
            team_elo=Decimal("1550"),
            opponent_elo=Decimal("1450"),
        )
        # Check precision (should have at most 4 decimal places)
        as_str = str(expected)
        if "." in as_str:
            decimal_places = len(as_str.split(".")[1])
            assert decimal_places <= 4


# =============================================================================
# Unit Tests: Win Probability
# =============================================================================


@pytest.mark.unit
class TestWinProbability:
    """Unit tests for win probability calculation with home advantage."""

    def test_home_advantage_increases_home_probability(self, nfl_engine: EloEngine) -> None:
        """Test home advantage increases home team's win probability."""
        home_elo = Decimal("1500")
        away_elo = Decimal("1500")

        home_prob, away_prob = nfl_engine.win_probability(home_elo, away_elo, neutral_site=False)

        # With home advantage, home team should be favored
        assert home_prob > Decimal("0.5")
        assert away_prob < Decimal("0.5")
        # NFL home advantage is 48 Elo points
        assert home_prob > Decimal("0.53")

    def test_neutral_site_no_home_advantage(self, nfl_engine: EloEngine) -> None:
        """Test neutral site gives equal probabilities for equal ratings."""
        home_prob, away_prob = nfl_engine.win_probability(
            home_elo=Decimal("1500"),
            away_elo=Decimal("1500"),
            neutral_site=True,
        )

        assert home_prob == Decimal("0.5")
        assert away_prob == Decimal("0.5")

    def test_probabilities_sum_to_one(self, nfl_engine: EloEngine) -> None:
        """Test probabilities always sum to 1."""
        home_prob, away_prob = nfl_engine.win_probability(
            home_elo=Decimal("1700"),
            away_elo=Decimal("1300"),
        )

        total = home_prob + away_prob
        assert Decimal("0.9999") <= total <= Decimal("1.0001")


# =============================================================================
# Unit Tests: Rating Updates
# =============================================================================


@pytest.mark.unit
class TestRatingUpdates:
    """Unit tests for Elo rating updates after games."""

    def test_home_win_expected_increases_home_rating(self, nfl_engine: EloEngine) -> None:
        """Test that expected home win increases home rating."""
        result = nfl_engine.update_ratings(
            home_elo=Decimal("1600"),
            away_elo=Decimal("1400"),
            home_score=28,
            away_score=14,
        )

        # Home team was favored and won, so modest increase
        assert result.home_elo_change > Decimal("0")
        assert result.home_elo_after > result.home_elo_before

    def test_upset_causes_large_rating_swing(self, nfl_engine: EloEngine) -> None:
        """Test that upsets cause larger rating changes."""
        # Underdog wins
        result = nfl_engine.update_ratings(
            home_elo=Decimal("1600"),
            away_elo=Decimal("1400"),
            home_score=14,
            away_score=28,
        )

        # Favorite lost, should have significant decrease
        assert result.home_elo_change < Decimal("-10")
        assert result.away_elo_change > Decimal("10")

    def test_zero_sum_updates(self, nfl_engine: EloEngine) -> None:
        """Test that rating changes sum to zero (zero-sum system)."""
        result = nfl_engine.update_ratings(
            home_elo=Decimal("1500"),
            away_elo=Decimal("1500"),
            home_score=21,
            away_score=17,
        )

        total_change = result.home_elo_change + result.away_elo_change
        assert abs(total_change) < Decimal("0.01")

    def test_tie_causes_no_change_for_equal_teams(self, nfl_engine: EloEngine) -> None:
        """Test that a tie between equal teams causes minimal change."""
        result = nfl_engine.update_ratings(
            home_elo=Decimal("1500"),
            away_elo=Decimal("1500"),
            home_score=21,
            away_score=21,
            neutral_site=True,
        )

        # Equal teams tying at neutral site = no change expected
        assert abs(result.home_elo_change) < Decimal("1")

    def test_playoff_multiplier_increases_change(self, nfl_engine: EloEngine) -> None:
        """Test playoff games cause larger rating changes."""
        regular_result = nfl_engine.update_ratings(
            home_elo=Decimal("1500"),
            away_elo=Decimal("1500"),
            home_score=28,
            away_score=21,
        )

        playoff_result = nfl_engine.update_ratings(
            home_elo=Decimal("1500"),
            away_elo=Decimal("1500"),
            home_score=28,
            away_score=21,
            is_playoff=True,
        )

        # Playoff change should be larger
        assert abs(playoff_result.home_elo_change) > abs(regular_result.home_elo_change)

    def test_result_contains_all_fields(self, nfl_engine: EloEngine) -> None:
        """Test that result object contains all expected fields."""
        result = nfl_engine.update_ratings(
            home_elo=Decimal("1500"),
            away_elo=Decimal("1500"),
            home_score=21,
            away_score=14,
        )

        assert isinstance(result, EloUpdateResult)
        assert hasattr(result, "home_elo_before")
        assert hasattr(result, "home_elo_after")
        assert hasattr(result, "home_expected")
        assert hasattr(result, "home_actual")
        assert hasattr(result, "k_factor")
        assert hasattr(result, "mov_multiplier")

    def test_actual_scores_win_loss_tie(self, nfl_engine: EloEngine) -> None:
        """Test actual scores are set correctly for win/loss/tie."""
        # Win
        win_result = nfl_engine.update_ratings(Decimal("1500"), Decimal("1500"), 28, 14)
        assert win_result.home_actual == Decimal("1")
        assert win_result.away_actual == Decimal("0")

        # Loss
        loss_result = nfl_engine.update_ratings(Decimal("1500"), Decimal("1500"), 14, 28)
        assert loss_result.home_actual == Decimal("0")
        assert loss_result.away_actual == Decimal("1")

        # Tie
        tie_result = nfl_engine.update_ratings(Decimal("1500"), Decimal("1500"), 21, 21)
        assert tie_result.home_actual == Decimal("0.5")
        assert tie_result.away_actual == Decimal("0.5")


# =============================================================================
# Unit Tests: Margin of Victory
# =============================================================================


@pytest.mark.unit
class TestMarginOfVictory:
    """Unit tests for margin-of-victory adjustments."""

    def test_mov_enabled_for_nfl(self, nfl_engine: EloEngine) -> None:
        """Test MOV is enabled for NFL."""
        assert nfl_engine.config.mov_enabled is True

    def test_mov_disabled_for_nhl(self, nhl_engine: EloEngine) -> None:
        """Test MOV is disabled for NHL."""
        assert nhl_engine.config.mov_enabled is False

    def test_larger_margin_gives_higher_multiplier(self, nfl_engine: EloEngine) -> None:
        """Test larger victory margins give higher multipliers."""
        small_margin = nfl_engine.margin_of_victory_multiplier(
            winner_score=21,
            loser_score=14,
            winner_elo=Decimal("1500"),
            loser_elo=Decimal("1500"),
        )

        large_margin = nfl_engine.margin_of_victory_multiplier(
            winner_score=42,
            loser_score=7,
            winner_elo=Decimal("1500"),
            loser_elo=Decimal("1500"),
        )

        assert large_margin > small_margin

    def test_mov_minimum_is_one(self, nfl_engine: EloEngine) -> None:
        """Test MOV multiplier is at least 1.0."""
        mult = nfl_engine.margin_of_victory_multiplier(
            winner_score=21,
            loser_score=20,
            winner_elo=Decimal("1500"),
            loser_elo=Decimal("1500"),
        )

        assert mult >= Decimal("1.0")

    def test_mov_capped_at_config_max(self, nfl_engine: EloEngine) -> None:
        """Test MOV multiplier is capped at config.mov_cap."""
        # Extreme blowout
        mult = nfl_engine.margin_of_victory_multiplier(
            winner_score=100,
            loser_score=0,
            winner_elo=Decimal("1500"),
            loser_elo=Decimal("1500"),
        )

        assert mult <= nfl_engine.config.mov_cap

    def test_mov_returns_one_when_disabled(self, nhl_engine: EloEngine) -> None:
        """Test MOV returns 1.0 when disabled for sport."""
        mult = nhl_engine.margin_of_victory_multiplier(
            winner_score=7,
            loser_score=1,
            winner_elo=Decimal("1500"),
            loser_elo=Decimal("1500"),
        )

        assert mult == Decimal("1.0")

    def test_blowout_win_gives_larger_rating_change(self, nfl_engine: EloEngine) -> None:
        """Test blowout wins cause larger rating changes than close games."""
        close_result = nfl_engine.update_ratings(
            home_elo=Decimal("1500"),
            away_elo=Decimal("1500"),
            home_score=21,
            away_score=20,
        )

        blowout_result = nfl_engine.update_ratings(
            home_elo=Decimal("1500"),
            away_elo=Decimal("1500"),
            home_score=42,
            away_score=7,
        )

        assert abs(blowout_result.home_elo_change) > abs(close_result.home_elo_change)


# =============================================================================
# Unit Tests: Season Regression
# =============================================================================


@pytest.mark.unit
class TestSeasonRegression:
    """Unit tests for season-to-season regression."""

    def test_regression_pulls_toward_target(self, nfl_engine: EloEngine) -> None:
        """Test regression pulls ratings toward target."""
        high_rating = Decimal("1700")
        low_rating = Decimal("1300")

        high_regressed = nfl_engine.apply_season_regression(high_rating)
        low_regressed = nfl_engine.apply_season_regression(low_rating)

        # Both should be closer to target (1505)
        assert high_regressed < high_rating
        assert low_regressed > low_rating

    def test_default_carryover_is_75_percent(self, nfl_engine: EloEngine) -> None:
        """Test default carryover weight is 75%."""
        current = Decimal("1700")
        regressed = nfl_engine.apply_season_regression(current)

        # Expected: 1700 * 0.75 + 1505 * 0.25 = 1275 + 376.25 = 1651.25
        expected = Decimal("1651.25")
        assert abs(regressed - expected) < Decimal("0.01")

    def test_custom_carryover_weight(self, nfl_engine: EloEngine) -> None:
        """Test custom carryover weight is applied."""
        current = Decimal("1600")
        regressed = nfl_engine.apply_season_regression(current, carryover_weight=Decimal("0.50"))

        # Expected: 1600 * 0.50 + 1505 * 0.50 = 800 + 752.5 = 1552.5
        expected = Decimal("1552.50")
        assert abs(regressed - expected) < Decimal("0.01")

    def test_at_target_no_regression(self, nfl_engine: EloEngine) -> None:
        """Test rating at target doesn't change significantly."""
        at_target = DEFAULT_REGRESSION_TARGET
        regressed = nfl_engine.apply_season_regression(at_target)

        assert abs(regressed - at_target) < Decimal("0.01")


# =============================================================================
# Unit Tests: Sport Configurations
# =============================================================================


@pytest.mark.unit
class TestSportConfigs:
    """Unit tests for sport-specific configurations."""

    def test_nfl_config(self) -> None:
        """Test NFL configuration matches FiveThirtyEight methodology."""
        config = SPORT_CONFIGS[Sport.NFL]
        assert config.k_factor == 20
        assert config.home_advantage == Decimal("48")
        assert config.mov_enabled is True

    def test_nba_has_high_home_advantage(self) -> None:
        """Test NBA has higher home court advantage than NFL."""
        nba_config = SPORT_CONFIGS[Sport.NBA]
        nfl_config = SPORT_CONFIGS[Sport.NFL]

        assert nba_config.home_advantage > nfl_config.home_advantage
        assert nba_config.home_advantage == Decimal("100")

    def test_mlb_has_low_k_factor(self) -> None:
        """Test MLB has lower K-factor due to long season."""
        mlb_config = SPORT_CONFIGS[Sport.MLB]
        nfl_config = SPORT_CONFIGS[Sport.NFL]

        assert mlb_config.k_factor < nfl_config.k_factor
        assert mlb_config.k_factor == 4

    def test_nhl_mov_disabled(self) -> None:
        """Test NHL has MOV disabled."""
        nhl_config = SPORT_CONFIGS[Sport.NHL]
        assert nhl_config.mov_enabled is False


# =============================================================================
# Unit Tests: Convenience Functions
# =============================================================================


@pytest.mark.unit
class TestConvenienceFunctions:
    """Unit tests for module-level convenience functions."""

    def test_get_elo_engine(self) -> None:
        """Test get_elo_engine factory function."""
        engine = get_elo_engine("nfl")
        assert isinstance(engine, EloEngine)
        assert engine.sport == Sport.NFL

    def test_elo_to_win_probability(self) -> None:
        """Test direct Elo to probability conversion."""
        prob = elo_to_win_probability(
            team_elo=Decimal("1600"),
            opponent_elo=Decimal("1400"),
        )

        # 200 point difference ~76%
        assert Decimal("0.75") < prob < Decimal("0.78")

    def test_win_probability_to_elo_difference(self) -> None:
        """Test probability to Elo difference conversion."""
        # 75% should be ~191 Elo
        diff = win_probability_to_elo_difference(Decimal("0.75"))
        assert Decimal("180") < diff < Decimal("200")

    def test_probability_conversion_roundtrip(self) -> None:
        """Test converting Elo -> prob -> Elo is consistent."""
        original_diff = Decimal("200")
        team_elo = Decimal("1600")
        opponent_elo = Decimal("1400")

        prob = elo_to_win_probability(team_elo, opponent_elo)
        recovered_diff = win_probability_to_elo_difference(prob)

        # Should be close to original 200-point difference
        assert abs(recovered_diff - original_diff) < Decimal("5")

    def test_win_probability_bounds_error(self) -> None:
        """Test probability conversion rejects out-of-bounds values."""
        with pytest.raises(ValueError, match="between 0 and 1"):
            win_probability_to_elo_difference(Decimal("0"))

        with pytest.raises(ValueError, match="between 0 and 1"):
            win_probability_to_elo_difference(Decimal("1"))


# =============================================================================
# Unit Tests: EloState Dataclass
# =============================================================================


@pytest.mark.unit
class TestEloState:
    """Unit tests for EloState dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic EloState creation."""
        from datetime import date

        state = EloState(
            rating=Decimal("1550"),
            last_updated=date(2024, 12, 1),
            games_played=10,
        )

        assert state.rating == Decimal("1550")
        assert state.games_played == 10

    def test_peak_rating_initialized(self) -> None:
        """Test peak rating is initialized correctly."""
        from datetime import date

        state = EloState(
            rating=Decimal("1650"),
            last_updated=date(2024, 12, 1),
        )

        assert state.peak_rating >= state.rating


# =============================================================================
# Unit Tests: EloUpdateResult
# =============================================================================


@pytest.mark.unit
class TestEloUpdateResult:
    """Unit tests for EloUpdateResult dataclass."""

    def test_to_dict(self, nfl_engine: EloEngine) -> None:
        """Test EloUpdateResult.to_dict() method."""
        result = nfl_engine.update_ratings(
            home_elo=Decimal("1500"),
            away_elo=Decimal("1500"),
            home_score=21,
            away_score=14,
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "home_elo_before" in result_dict
        assert "home_elo_after" in result_dict
        assert "k_factor" in result_dict
        assert result_dict["k_factor"] == 20


# =============================================================================
# Unit Tests: Constants
# =============================================================================


@pytest.mark.unit
class TestConstants:
    """Unit tests for module constants."""

    def test_default_initial_rating(self) -> None:
        """Test default initial rating is 1500."""
        assert Decimal("1500") == DEFAULT_INITIAL_RATING

    def test_elo_divisor_is_400(self) -> None:
        """Test Elo divisor is 400 (standard)."""
        assert Decimal("400") == ELO_DIVISOR

    def test_default_carryover_is_75_percent(self) -> None:
        """Test default carryover is 75%."""
        assert Decimal("0.75") == DEFAULT_CARRYOVER_WEIGHT

    def test_default_regression_target(self) -> None:
        """Test default regression target is 1505."""
        assert Decimal("1505") == DEFAULT_REGRESSION_TARGET
