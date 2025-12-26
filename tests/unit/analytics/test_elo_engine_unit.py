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

from datetime import date
from decimal import Decimal

import pytest

from precog.analytics.elo_engine import (
    DEFAULT_CARRYOVER_WEIGHT,
    DEFAULT_INITIAL_RATING,
    DEFAULT_REGRESSION_TARGET,
    ELO_DIVISOR,
    ERA_REGISTRY,
    SPORT_CONFIGS,
    SPORT_CONFIGS_POST_2020,
    EloEngine,
    EloState,
    EloUpdateResult,
    Sport,
    SportConfig,
    elo_to_win_probability,
    get_config_for_date,
    get_elo_engine,
    get_era_for_date,
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
# Unit Tests: Era Registry
# =============================================================================


@pytest.mark.unit
class TestEraRegistry:
    """Unit tests for the Era Registry pattern.

    Educational Note:
        The Era Registry pattern enables date-based configuration selection,
        making it trivial to add new eras without modifying the EloEngine class.
        This is more scalable than boolean flags like use_post_2020.
    """

    def test_era_registry_has_entries(self) -> None:
        """Test that ERA_REGISTRY has at least one era."""
        assert len(ERA_REGISTRY) >= 1

    def test_era_registry_covers_all_time(self) -> None:
        """Test that era registry covers from None (beginning) to None (current)."""
        # First era should have no start_date (beginning of time)
        assert ERA_REGISTRY[0].start_date is None

        # Last era should have no end_date (ongoing/current)
        assert ERA_REGISTRY[-1].end_date is None

    def test_eras_are_contiguous(self) -> None:
        """Test that eras don't overlap and have no gaps."""
        for i in range(len(ERA_REGISTRY) - 1):
            current_era = ERA_REGISTRY[i]
            next_era = ERA_REGISTRY[i + 1]

            # Current era's end should be one day before next era's start
            if current_era.end_date and next_era.start_date:
                gap = (next_era.start_date - current_era.end_date).days
                assert gap == 1, f"Gap of {gap} days between {current_era.name} and {next_era.name}"

    def test_get_era_for_date_historical(self) -> None:
        """Test getting era for a date before COVID."""
        era = get_era_for_date(date(2019, 12, 1))
        assert era.name == "historical"

    def test_get_era_for_date_post_2020(self) -> None:
        """Test getting era for a date after COVID."""
        era = get_era_for_date(date(2023, 9, 15))
        assert era.name == "post_2020"

    def test_get_era_for_date_covid_boundary(self) -> None:
        """Test era boundaries around COVID shutdown date."""
        # Day before COVID shutdown
        pre_covid = get_era_for_date(date(2020, 3, 11))
        assert pre_covid.name == "historical"

        # Day of COVID shutdown
        post_covid = get_era_for_date(date(2020, 3, 12))
        assert post_covid.name == "post_2020"

    def test_get_era_for_date_none_returns_current(self) -> None:
        """Test that None date returns the current/latest era."""
        era = get_era_for_date(None)
        # Should be the era with end_date=None (ongoing)
        assert era.end_date is None

    def test_get_config_for_date_returns_correct_config(self) -> None:
        """Test that get_config_for_date returns correct sport config."""
        # Pre-COVID: NFL home advantage = 48
        config_2019 = get_config_for_date(Sport.NFL, date(2019, 9, 8))
        assert config_2019.home_advantage == Decimal("48")

        # Post-COVID: NFL home advantage = 30
        config_2023 = get_config_for_date(Sport.NFL, date(2023, 9, 10))
        assert config_2023.home_advantage == Decimal("30")

    def test_all_eras_have_all_sports(self) -> None:
        """Test that each era has configs for all sports."""
        for era in ERA_REGISTRY:
            for sport in Sport:
                assert sport in era.sport_configs, f"Era '{era.name}' missing config for {sport}"

    def test_era_dataclass_is_frozen(self) -> None:
        """Test that Era is immutable (frozen dataclass)."""
        era = ERA_REGISTRY[0]
        with pytest.raises(AttributeError):
            era.name = "modified"  # type: ignore[misc]


@pytest.mark.unit
class TestEloEngineDateBasedConfig:
    """Unit tests for EloEngine date-based configuration.

    Educational Note:
        The game_date parameter enables automatic era selection based on when
        the game was played. This is more maintainable than boolean flags.
    """

    def test_game_date_selects_historical_era(self) -> None:
        """Test that pre-COVID game date selects historical config."""
        engine = EloEngine("nfl", game_date=date(2019, 9, 8))

        assert engine.home_advantage == Decimal("48")
        assert engine.era is not None
        assert engine.era.name == "historical"

    def test_game_date_selects_post_2020_era(self) -> None:
        """Test that post-COVID game date selects post-2020 config."""
        engine = EloEngine("nfl", game_date=date(2023, 9, 10))

        assert engine.home_advantage == Decimal("30")
        assert engine.era is not None
        assert engine.era.name == "post_2020"

    def test_game_date_overrides_use_post_2020_flag(self) -> None:
        """Test that game_date takes priority over use_post_2020 flag.

        Even if use_post_2020=True, game_date should determine config.
        """
        # Date is 2019 but flag says post_2020=True
        engine = EloEngine("nfl", use_post_2020=True, game_date=date(2019, 9, 8))

        # game_date wins: should be historical config
        assert engine.home_advantage == Decimal("48")
        assert engine.era.name == "historical"

    def test_explicit_config_overrides_game_date(self) -> None:
        """Test that explicit config overrides game_date."""
        custom_config = SportConfig(
            k_factor=50,
            home_advantage=Decimal("100"),
            mov_enabled=False,
        )
        engine = EloEngine("nfl", config=custom_config, game_date=date(2019, 9, 8))

        assert engine.home_advantage == Decimal("100")
        assert engine.era is None  # No era when explicit config

    def test_game_date_stored_on_engine(self) -> None:
        """Test that game_date is accessible on the engine."""
        game_day = date(2023, 10, 15)
        engine = EloEngine("nfl", game_date=game_day)

        assert engine.game_date == game_day


# =============================================================================
# Unit Tests: Post-2020 Era Configurations
# =============================================================================


@pytest.mark.unit
class TestPost2020Configs:
    """Unit tests for post-2020 era configurations with reduced home advantage.

    Educational Note:
        Post-2020 configurations account for reduced home field advantage
        observed after the COVID-19 pandemic. Empty stadiums during 2020
        and changed fan behavior afterward reduced home advantage by 30-60%.
        - NFL: 48 → 30 Elo points (37.5% reduction)
        - NBA: 100 → 40 Elo points (60% reduction)
        - NCAAF: 65 → 40 Elo points (38.5% reduction)

    Reference: FiveThirtyEight analysis of post-pandemic home advantage
    Related ADRs: ADR-ELO-001 (Era-based configuration)
    """

    def test_all_sports_have_post_2020_configs(self) -> None:
        """Test all Sport enum values have post-2020 configurations."""
        for sport in Sport:
            assert sport in SPORT_CONFIGS_POST_2020, f"Missing post-2020 config for {sport}"

    def test_default_uses_historical_config(self) -> None:
        """Test that default (use_post_2020=False) uses historical values."""
        engine = EloEngine("nfl")  # Default use_post_2020=False

        assert engine.home_advantage == Decimal("48")
        assert engine.config == SPORT_CONFIGS[Sport.NFL]

    def test_post_2020_flag_uses_reduced_home_advantage(self) -> None:
        """Test that use_post_2020=True uses reduced home advantage values."""
        engine = EloEngine("nfl", use_post_2020=True)

        assert engine.home_advantage == Decimal("30")
        assert engine.config == SPORT_CONFIGS_POST_2020[Sport.NFL]

    def test_nfl_post_2020_home_advantage(self) -> None:
        """Test NFL post-2020 home advantage is 30 (reduced from 48)."""
        config = SPORT_CONFIGS_POST_2020[Sport.NFL]
        assert config.home_advantage == Decimal("30")

    def test_nba_post_2020_home_advantage(self) -> None:
        """Test NBA post-2020 home advantage is 40 (reduced from 100)."""
        config = SPORT_CONFIGS_POST_2020[Sport.NBA]
        assert config.home_advantage == Decimal("40")

    def test_ncaaf_post_2020_home_advantage(self) -> None:
        """Test NCAAF post-2020 home advantage is 40 (reduced from 65)."""
        config = SPORT_CONFIGS_POST_2020[Sport.NCAAF]
        assert config.home_advantage == Decimal("40")

    def test_explicit_config_overrides_post_2020(self) -> None:
        """Test explicit config parameter overrides use_post_2020 flag."""
        custom_config = SportConfig(
            k_factor=50,
            home_advantage=Decimal("75"),
            mov_enabled=False,
        )
        # Even with use_post_2020=True, explicit config wins
        engine = EloEngine("nfl", config=custom_config, use_post_2020=True)

        assert engine.home_advantage == Decimal("75")
        assert engine.config == custom_config

    def test_post_2020_k_factors_unchanged(self) -> None:
        """Test K-factors are unchanged in post-2020 (only home advantage changed)."""
        for sport in Sport:
            historical = SPORT_CONFIGS[sport]
            post_2020 = SPORT_CONFIGS_POST_2020[sport]
            assert historical.k_factor == post_2020.k_factor, (
                f"{sport}: K-factor should be unchanged post-2020"
            )

    def test_post_2020_mov_settings_unchanged(self) -> None:
        """Test MOV settings are unchanged in post-2020."""
        for sport in Sport:
            historical = SPORT_CONFIGS[sport]
            post_2020 = SPORT_CONFIGS_POST_2020[sport]
            assert historical.mov_enabled == post_2020.mov_enabled, (
                f"{sport}: MOV setting should be unchanged post-2020"
            )

    def test_post_2020_home_advantages_are_lower(self) -> None:
        """Test all post-2020 home advantages are lower than historical."""
        for sport in Sport:
            historical = SPORT_CONFIGS[sport]
            post_2020 = SPORT_CONFIGS_POST_2020[sport]
            assert post_2020.home_advantage <= historical.home_advantage, (
                f"{sport}: Post-2020 home advantage should be <= historical"
            )

    def test_win_probability_different_between_eras(self) -> None:
        """Test win probability differs between era configurations.

        Educational Note:
            With equal Elo ratings, reduced home advantage means smaller
            win probability gap for home team vs away team.
        """
        historical_engine = EloEngine("nfl", use_post_2020=False)
        post_2020_engine = EloEngine("nfl", use_post_2020=True)

        home_elo = Decimal("1500")
        away_elo = Decimal("1500")

        hist_home_prob, _ = historical_engine.win_probability(home_elo, away_elo)
        post_home_prob, _ = post_2020_engine.win_probability(home_elo, away_elo)

        # Post-2020 should have smaller home advantage
        assert post_home_prob < hist_home_prob
        # Both should still favor home team
        assert post_home_prob > Decimal("0.5")
        assert hist_home_prob > Decimal("0.5")


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
