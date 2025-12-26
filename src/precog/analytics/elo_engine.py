"""
Elo Rating Computation Engine.

Implements the FiveThirtyEight-style Elo rating system for sports prediction.
This is the core algorithm for computing team strength ratings based on game outcomes.

Key Features:
    - Expected score calculation using the standard Elo formula
    - Sport-specific K-factors for optimal convergence
    - Home-field advantage adjustments per sport
    - Margin-of-victory adjustments (optional enhancement)
    - Season carryover with mean regression
    - Support for all major sports (NFL, NBA, NHL, MLB, NCAAF, NCAAB)

Design Decisions:
    - All calculations use Decimal for precision (ADR-002)
    - Immutable configuration via dataclass
    - Pure functions for core calculations (testable, no side effects)
    - Sport-specific parameters loaded from configuration

Example Usage:
    >>> from decimal import Decimal
    >>> from precog.analytics.elo_engine import EloEngine
    >>>
    >>> engine = EloEngine(sport="nfl")
    >>>
    >>> # Calculate expected score
    >>> expected = engine.expected_score(
    ...     team_elo=Decimal("1600"),
    ...     opponent_elo=Decimal("1400")
    ... )
    >>> print(f"Expected: {expected:.4f}")  # ~0.7597
    >>>
    >>> # Update ratings after a game
    >>> result = engine.update_ratings(
    ...     home_elo=Decimal("1600"),
    ...     away_elo=Decimal("1400"),
    ...     home_score=28,
    ...     away_score=21
    ... )
    >>> print(f"Home new: {result.home_elo_after}")

Reference: docs/guides/ELO_COMPUTATION_GUIDE_V1.1.md
Related ADR: ADR-109 (Elo Rating Computation Engine)
Related Requirements: REQ-ELO-001 through REQ-ELO-007

Created: 2025-12-25
Phase: 2.6 (Elo Rating Computation)
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import ClassVar

# =============================================================================
# Constants
# =============================================================================

# Base Elo rating for new teams
DEFAULT_INITIAL_RATING = Decimal("1500")

# Divisor in the expected score formula (standard is 400)
ELO_DIVISOR = Decimal("400")

# Season carryover parameters
DEFAULT_CARRYOVER_WEIGHT = Decimal("0.75")
DEFAULT_REGRESSION_TARGET = Decimal("1505")  # Slightly above neutral


class Sport(str, Enum):
    """Supported sports for Elo computation.

    Educational Note:
        Each sport has different characteristics that affect Elo calibration:
        - NFL: Short season (17 games), high single-game variance
        - NBA: Long season (82 games), lower variance per game
        - NHL: Long season, low-scoring games reduce variance
        - MLB: Very long season (162 games), individual game variance low

    These differences drive the K-factor and home advantage choices.
    """

    NFL = "nfl"
    NCAAF = "ncaaf"
    NBA = "nba"
    NCAAB = "ncaab"
    WNBA = "wnba"
    NHL = "nhl"
    MLB = "mlb"
    MLS = "mls"


# =============================================================================
# Sport Configuration
# =============================================================================


@dataclass(frozen=True)
class SportConfig:
    """Configuration for sport-specific Elo parameters.

    Educational Note:
        K-Factor Selection:
        - Higher K = More volatile ratings, faster adaptation to recent results
        - Lower K = More stable ratings, better for long seasons

        Rule of thumb: K should be inversely proportional to season length.
        NFL (17 games) uses K=20, MLB (162 games) uses K=4.

    Attributes:
        k_factor: How much ratings change per game (higher = more volatile)
        home_advantage: Elo points added to home team's rating
        playoff_k_multiplier: K-factor multiplier for playoff games (more important)
        mov_enabled: Whether to use margin-of-victory adjustment
        mov_cap: Maximum multiplier for margin-of-victory (prevents runaway)
    """

    k_factor: int
    home_advantage: Decimal
    playoff_k_multiplier: Decimal = Decimal("1.25")
    mov_enabled: bool = False
    mov_cap: Decimal = Decimal("2.5")


# Default configurations following FiveThirtyEight methodology
# These values are calibrated for the pre-2020 era and validated against
# FiveThirtyEight data (2015-2020). For post-2020 games, use SPORT_CONFIGS_POST_2020.
SPORT_CONFIGS: dict[Sport, SportConfig] = {
    Sport.NFL: SportConfig(
        k_factor=20,
        home_advantage=Decimal("48"),
        mov_enabled=True,  # NFL uses margin of victory
    ),
    Sport.NCAAF: SportConfig(
        k_factor=20,
        home_advantage=Decimal("55"),  # College home advantage is stronger
        mov_enabled=True,
    ),
    Sport.NBA: SportConfig(
        k_factor=20,
        home_advantage=Decimal("100"),  # Strong home court in NBA
        mov_enabled=True,
    ),
    Sport.NCAAB: SportConfig(
        k_factor=20,
        home_advantage=Decimal("100"),
        mov_enabled=True,
    ),
    Sport.WNBA: SportConfig(
        k_factor=20,
        home_advantage=Decimal("80"),  # Slightly less than NBA
        mov_enabled=True,
    ),
    Sport.NHL: SportConfig(
        k_factor=6,  # Lower K for 82-game season
        home_advantage=Decimal("33"),
        mov_enabled=False,  # Low-scoring, MOV less predictive
    ),
    Sport.MLB: SportConfig(
        k_factor=4,  # Very low K for 162-game season
        home_advantage=Decimal("24"),
        mov_enabled=False,  # Run differential handled differently in baseball
    ),
    Sport.MLS: SportConfig(
        k_factor=32,  # Soccer typically uses higher K
        home_advantage=Decimal("65"),
        mov_enabled=False,
    ),
}


# Post-2020 configurations with reduced home advantage
# Research shows home advantage reduced 30-60% post-COVID due to:
# - Initially: Empty/limited-capacity stadiums (2020-2021)
# - Persistently: Changed crowd behavior, travel adaptations
# Reference: https://fivethirtyeight.com (home advantage analysis)
SPORT_CONFIGS_POST_2020: dict[Sport, SportConfig] = {
    Sport.NFL: SportConfig(
        k_factor=20,
        home_advantage=Decimal("30"),  # Reduced from 48 (~37% reduction)
        mov_enabled=True,
    ),
    Sport.NCAAF: SportConfig(
        k_factor=20,
        home_advantage=Decimal("40"),  # Reduced from 55 (~27% reduction)
        mov_enabled=True,
    ),
    Sport.NBA: SportConfig(
        k_factor=20,
        home_advantage=Decimal("40"),  # Reduced from 100 (~60% reduction)
        mov_enabled=True,
    ),
    Sport.NCAAB: SportConfig(
        k_factor=20,
        home_advantage=Decimal("50"),  # Reduced from 100 (~50% reduction)
        mov_enabled=True,
    ),
    Sport.WNBA: SportConfig(
        k_factor=20,
        home_advantage=Decimal("40"),  # Reduced from 80 (~50% reduction)
        mov_enabled=True,
    ),
    Sport.NHL: SportConfig(
        k_factor=6,
        home_advantage=Decimal("25"),  # Reduced from 33 (~24% reduction)
        mov_enabled=False,
    ),
    Sport.MLB: SportConfig(
        k_factor=4,
        home_advantage=Decimal("18"),  # Reduced from 24 (~25% reduction)
        mov_enabled=False,
    ),
    Sport.MLS: SportConfig(
        k_factor=32,
        home_advantage=Decimal("45"),  # Reduced from 65 (~31% reduction)
        mov_enabled=False,
    ),
}


# =============================================================================
# Era Registry - Date-Based Configuration Selection
# =============================================================================


@dataclass(frozen=True)
class Era:
    """An era defines a time period with specific sport configurations.

    Educational Note:
        Elo parameters (especially home advantage) change over time due to:
        - Rule changes (e.g., NFL overtime rules)
        - Cultural shifts (e.g., post-COVID crowd behavior)
        - Travel improvements (e.g., charter flights)

        The Era Registry pattern allows easy addition of new eras without
        modifying the core EloEngine class. Just add entries to ERA_REGISTRY.

    Example adding a hypothetical post-2025 era:
        >>> new_era = Era(
        ...     name="post_2025",
        ...     start_date=date(2025, 9, 1),
        ...     end_date=None,  # Current
        ...     sport_configs=SPORT_CONFIGS_POST_2025,
        ...     description="Post-2025 adjustments"
        ... )
        >>> ERA_REGISTRY.append(new_era)

    Attributes:
        name: Unique identifier for this era
        start_date: First day of this era (None = beginning of time)
        end_date: Last day of this era (None = present/ongoing)
        sport_configs: Sport-specific configurations for this era
        description: Human-readable description of why this era exists
    """

    name: str
    start_date: date | None
    end_date: date | None
    sport_configs: dict[Sport, SportConfig]
    description: str = ""


# Era Registry - ordered by start_date (oldest first)
# To add a new era: append to this list with appropriate date range
ERA_REGISTRY: list[Era] = [
    Era(
        name="historical",
        start_date=None,  # Beginning of time
        end_date=date(2020, 3, 11),  # Day before COVID shutdown
        sport_configs=SPORT_CONFIGS,
        description="Pre-COVID era with standard home advantages",
    ),
    Era(
        name="post_2020",
        start_date=date(2020, 3, 12),  # COVID shutdown began
        end_date=None,  # Current/ongoing
        sport_configs=SPORT_CONFIGS_POST_2020,
        description="Post-COVID era with reduced home advantages",
    ),
]


def get_era_for_date(game_date: date | None = None) -> Era:
    """Get the appropriate era for a game date.

    Educational Note:
        This function enables date-aware Elo computation. When processing
        a game from 2018, it automatically uses pre-COVID configs. When
        processing a game from 2023, it uses post-COVID configs.

        If no date is provided, returns the current era (most recent).

    Args:
        game_date: Date of the game. If None, returns current era.

    Returns:
        The Era that contains the given date.

    Example:
        >>> from datetime import date
        >>> era = get_era_for_date(date(2019, 12, 1))
        >>> era.name
        'historical'
        >>> era = get_era_for_date(date(2023, 9, 15))
        >>> era.name
        'post_2020'
    """
    if game_date is None:
        # Return most recent era (one with end_date=None, or latest end_date)
        for era in reversed(ERA_REGISTRY):
            if era.end_date is None:
                return era
        return ERA_REGISTRY[-1]  # Fallback to latest

    # Find era that contains this date
    for era in ERA_REGISTRY:
        start_ok = era.start_date is None or game_date >= era.start_date
        end_ok = era.end_date is None or game_date <= era.end_date
        if start_ok and end_ok:
            return era

    # Fallback: if date is before all eras, use first era
    # If date is after all eras, use last era
    if ERA_REGISTRY:
        first_era = ERA_REGISTRY[0]
        if first_era.start_date and game_date < first_era.start_date:
            return first_era
        return ERA_REGISTRY[-1]

    # Should never happen if ERA_REGISTRY is properly configured
    raise ValueError(f"No era found for date {game_date}")


def get_config_for_date(sport: Sport, game_date: date | None = None) -> SportConfig:
    """Get the appropriate sport configuration for a game date.

    This is a convenience function combining era lookup and config retrieval.

    Args:
        sport: The sport to get configuration for
        game_date: Date of the game. If None, returns current era config.

    Returns:
        SportConfig for the given sport and era.

    Example:
        >>> from datetime import date
        >>> config = get_config_for_date(Sport.NFL, date(2019, 9, 8))
        >>> config.home_advantage
        Decimal('48')
        >>> config = get_config_for_date(Sport.NFL, date(2023, 9, 10))
        >>> config.home_advantage
        Decimal('30')
    """
    era = get_era_for_date(game_date)
    return era.sport_configs[sport]


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class EloUpdateResult:
    """Result of an Elo rating update after a game.

    Educational Note:
        This captures the full calculation trace for auditing and debugging.
        Every field needed to reproduce the calculation is stored, enabling
        us to verify correctness and diagnose issues.

    The elo_calculation_log table (Migration 0013) stores these results.

    Attributes:
        home_elo_before: Home team's Elo rating before the game
        away_elo_before: Away team's Elo rating before the game
        home_elo_after: Home team's Elo rating after the game
        away_elo_after: Away team's Elo rating after the game
        home_expected: Home team's expected score (0.0-1.0)
        away_expected: Away team's expected score (0.0-1.0)
        home_actual: Home team's actual score (1=win, 0.5=tie, 0=loss)
        away_actual: Away team's actual score
        home_elo_change: Points gained/lost by home team
        away_elo_change: Points gained/lost by away team
        k_factor: K-factor used for this calculation
        home_advantage: Home advantage points applied
        mov_multiplier: Margin-of-victory multiplier (1.0 if disabled)
    """

    home_elo_before: Decimal
    away_elo_before: Decimal
    home_elo_after: Decimal
    away_elo_after: Decimal
    home_expected: Decimal
    away_expected: Decimal
    home_actual: Decimal
    away_actual: Decimal
    home_elo_change: Decimal
    away_elo_change: Decimal
    k_factor: int
    home_advantage: Decimal
    mov_multiplier: Decimal = Decimal("1.0")

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "home_elo_before": self.home_elo_before,
            "away_elo_before": self.away_elo_before,
            "home_elo_after": self.home_elo_after,
            "away_elo_after": self.away_elo_after,
            "home_expected": self.home_expected,
            "away_expected": self.away_expected,
            "home_actual": self.home_actual,
            "away_actual": self.away_actual,
            "home_elo_change": self.home_elo_change,
            "away_elo_change": self.away_elo_change,
            "k_factor": self.k_factor,
            "home_advantage": self.home_advantage,
            "mov_multiplier": self.mov_multiplier,
        }


@dataclass
class EloState:
    """Current Elo state for a team.

    Used for bootstrapping and tracking team ratings over time.

    Attributes:
        rating: Current Elo rating
        last_updated: Date of last rating update
        games_played: Total games played (for current season)
        peak_rating: Highest rating achieved
        lowest_rating: Lowest rating achieved
    """

    rating: Decimal
    last_updated: date
    games_played: int = 0
    peak_rating: Decimal = field(default_factory=lambda: Decimal("1500"))
    lowest_rating: Decimal = field(default_factory=lambda: Decimal("1500"))

    def __post_init__(self) -> None:
        """Initialize peak/lowest if not set."""
        if self.peak_rating < self.rating:
            self.peak_rating = self.rating
        if self.lowest_rating > self.rating:
            self.lowest_rating = self.rating


# =============================================================================
# Elo Engine
# =============================================================================


class EloEngine:
    """Core Elo rating computation engine.

    Educational Note:
        The Elo system was invented by Arpad Elo for chess ratings.
        It's based on the Bradley-Terry model of paired comparison.

        Key insight: The expected score equals the logistic function of
        the rating difference divided by 400.

        FiveThirtyEight adapted this for sports with:
        1. Sport-specific K-factors
        2. Home-field advantage
        3. Margin-of-victory adjustments
        4. Season regression to mean

    Example:
        >>> engine = EloEngine(sport="nfl")
        >>>
        >>> # Team A (1600) vs Team B (1400) at Team A's home
        >>> result = engine.update_ratings(
        ...     home_elo=Decimal("1600"),
        ...     away_elo=Decimal("1400"),
        ...     home_score=28,
        ...     away_score=21
        ... )
        >>>
        >>> # Team A expected to win ~76% but only won
        >>> # So modest Elo gain
        >>> print(f"Home change: {result.home_elo_change:+.1f}")

    Attributes:
        sport: The sport this engine is configured for
        config: Sport-specific configuration (K-factor, home advantage, etc.)
    """

    # Class-level precision settings
    DECIMAL_PLACES: ClassVar[int] = 2
    PROBABILITY_PLACES: ClassVar[int] = 4

    def __init__(
        self,
        sport: str | Sport,
        config: SportConfig | None = None,
        use_post_2020: bool = False,
        game_date: date | None = None,
    ) -> None:
        """Initialize Elo engine for a specific sport.

        Args:
            sport: Sport type (e.g., "nfl", "nba", or Sport enum)
            config: Optional custom configuration (overrides all other options)
            use_post_2020: DEPRECATED - Use game_date instead. If True, uses
                post-2020 config. Ignored if game_date is provided.
            game_date: Date of the game for automatic era selection.
                If provided, config is auto-selected based on the Era Registry.
                This is the recommended approach for new code.

        Raises:
            ValueError: If sport is not supported

        Educational Note:
            Configuration priority (first match wins):
            1. Explicit config parameter (full override)
            2. game_date parameter (auto-selects from Era Registry)
            3. use_post_2020 flag (legacy, deprecated)
            4. Default historical config (SPORT_CONFIGS)

            The Era Registry pattern makes it trivial to add new eras:
            just append an Era to ERA_REGISTRY with date range and configs.

        Example:
            >>> from datetime import date
            >>>
            >>> # Preferred: Date-based era selection
            >>> engine_2019 = EloEngine("nfl", game_date=date(2019, 9, 8))
            >>> engine_2019.home_advantage  # Decimal("48") - pre-COVID
            >>>
            >>> engine_2023 = EloEngine("nfl", game_date=date(2023, 9, 10))
            >>> engine_2023.home_advantage  # Decimal("30") - post-COVID
            >>>
            >>> # Legacy: Boolean flag (deprecated but still works)
            >>> engine = EloEngine("nfl", use_post_2020=True)
            >>> engine.home_advantage  # Decimal("30")
        """
        # Convert string to Sport enum if needed
        sport_enum: Sport
        if isinstance(sport, str):
            try:
                sport_enum = Sport(sport.lower())
            except ValueError as e:
                valid_sports = ", ".join(s.value for s in Sport)
                msg = f"Unknown sport '{sport}'. Valid options: {valid_sports}"
                raise ValueError(msg) from e
        else:
            sport_enum = sport  # type: ignore[unreachable]

        self.sport: Sport = sport_enum
        self.use_post_2020 = use_post_2020
        self.game_date = game_date

        # Priority: explicit config > game_date > use_post_2020 flag > default
        if config is not None:
            # 1. Explicit config always wins
            self.config = config
            self._era: Era | None = None
        elif game_date is not None:
            # 2. Date-based era selection (recommended approach)
            self._era = get_era_for_date(game_date)
            self.config = self._era.sport_configs[self.sport]
        elif use_post_2020:
            # 3. Legacy boolean flag (deprecated)
            self.config = SPORT_CONFIGS_POST_2020[self.sport]
            self._era = get_era_for_date(date(2023, 1, 1))  # Post-2020 era
        else:
            # 4. Default historical config
            self.config = SPORT_CONFIGS[self.sport]
            self._era = get_era_for_date(date(2019, 1, 1))  # Historical era

    @property
    def era(self) -> Era | None:
        """Get the era this engine is configured for."""
        return self._era

    @property
    def k_factor(self) -> int:
        """Get the K-factor for this sport."""
        return self.config.k_factor

    @property
    def home_advantage(self) -> Decimal:
        """Get the home-field advantage in Elo points."""
        return self.config.home_advantage

    def expected_score(
        self,
        team_elo: Decimal,
        opponent_elo: Decimal,
    ) -> Decimal:
        """Calculate the expected score (win probability) for a team.

        Educational Note:
            The expected score formula:
            E = 1 / (1 + 10^((opponent - team) / 400))

            This is the logistic function applied to the rating difference.
            A 400-point difference gives ~90% win probability.
            A 200-point difference gives ~76% win probability.

        Args:
            team_elo: The team's current Elo rating
            opponent_elo: The opponent's current Elo rating

        Returns:
            Expected score (probability) between 0 and 1

        Example:
            >>> engine = EloEngine("nfl")
            >>> expected = engine.expected_score(
            ...     team_elo=Decimal("1600"),
            ...     opponent_elo=Decimal("1400")
            ... )
            >>> print(f"{expected:.4f}")  # ~0.7597
        """
        # Calculate exponent: (opponent - team) / 400
        exponent = (opponent_elo - team_elo) / ELO_DIVISOR

        # Convert to float for power calculation, then back to Decimal
        # Note: Decimal doesn't support fractional exponents directly
        power = Decimal(str(10 ** float(exponent)))

        expected = Decimal("1") / (Decimal("1") + power)

        # Round to 4 decimal places for consistency
        return expected.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def win_probability(
        self,
        home_elo: Decimal,
        away_elo: Decimal,
        neutral_site: bool = False,
    ) -> tuple[Decimal, Decimal]:
        """Calculate win probabilities for both teams.

        This is a convenience wrapper around expected_score that:
        1. Applies home-field advantage
        2. Returns probabilities for both teams

        Args:
            home_elo: Home team's Elo rating
            away_elo: Away team's Elo rating
            neutral_site: If True, no home advantage is applied

        Returns:
            Tuple of (home_win_prob, away_win_prob)

        Example:
            >>> engine = EloEngine("nfl")
            >>> home_prob, away_prob = engine.win_probability(
            ...     home_elo=Decimal("1600"),
            ...     away_elo=Decimal("1400")
            ... )
            >>> print(f"Home: {home_prob:.1%}, Away: {away_prob:.1%}")
        """
        # Apply home advantage
        adjusted_home = home_elo if neutral_site else home_elo + self.home_advantage

        home_prob = self.expected_score(adjusted_home, away_elo)
        away_prob = Decimal("1") - home_prob

        return home_prob, away_prob

    def margin_of_victory_multiplier(
        self,
        winner_score: int,
        loser_score: int,
        winner_elo: Decimal,
        loser_elo: Decimal,
    ) -> Decimal:
        """Calculate margin-of-victory adjustment multiplier.

        Educational Note:
            FiveThirtyEight's MOV formula adjusts K to reward convincing wins
            while controlling for blowouts (diminishing returns).

            The formula also accounts for Elo difference:
            - Blowing out a weaker team is less impressive
            - Narrow wins over strong teams are more valuable

            MOV = ln(abs(score_diff) + 1) * (2.2 / (elo_diff * 0.001 + 2.2))

        Args:
            winner_score: Winning team's score
            loser_score: Losing team's score
            winner_elo: Winner's Elo rating
            loser_elo: Loser's Elo rating

        Returns:
            Multiplier >= 1.0 (or 1.0 if MOV disabled for this sport)
        """
        if not self.config.mov_enabled:
            return Decimal("1.0")

        import math

        score_diff = abs(winner_score - loser_score)
        elo_diff = float(winner_elo - loser_elo)

        # Log-based diminishing returns for score differential
        log_component = math.log(score_diff + 1)

        # Autocorrelation adjustment (reduce impact when favorite wins big)
        if elo_diff > 0:  # Favorite won
            autocorr = 2.2 / (elo_diff * 0.001 + 2.2)
        else:  # Underdog won
            autocorr = 2.2 / (-elo_diff * 0.001 + 2.2)

        multiplier = Decimal(str(log_component * autocorr))

        # Cap the multiplier to prevent extreme swings
        if multiplier > self.config.mov_cap:
            multiplier = self.config.mov_cap

        # Ensure minimum of 1.0
        if multiplier < Decimal("1"):
            multiplier = Decimal("1")

        return multiplier.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def update_ratings(
        self,
        home_elo: Decimal,
        away_elo: Decimal,
        home_score: int,
        away_score: int,
        is_playoff: bool = False,
        neutral_site: bool = False,
    ) -> EloUpdateResult:
        """Update Elo ratings after a game.

        Educational Note:
            The update formula:
            R_new = R_old + K * MOV * (S - E)

            Where:
            - R_new: New rating
            - R_old: Old rating
            - K: K-factor (sensitivity)
            - MOV: Margin-of-victory multiplier
            - S: Actual score (1=win, 0.5=tie, 0=loss)
            - E: Expected score

            The system is zero-sum: points gained by winner = points lost by loser.

        Args:
            home_elo: Home team's current Elo rating
            away_elo: Away team's current Elo rating
            home_score: Home team's final score
            away_score: Away team's final score
            is_playoff: If True, applies playoff K-factor multiplier
            neutral_site: If True, no home advantage applied

        Returns:
            EloUpdateResult with full calculation details

        Example:
            >>> engine = EloEngine("nfl")
            >>> result = engine.update_ratings(
            ...     home_elo=Decimal("1600"),
            ...     away_elo=Decimal("1400"),
            ...     home_score=28,
            ...     away_score=21
            ... )
            >>> print(f"Home: {result.home_elo_after:.0f} ({result.home_elo_change:+.1f})")
        """
        # Determine K-factor
        k = self.config.k_factor
        if is_playoff:
            k = int(k * float(self.config.playoff_k_multiplier))

        # Apply home advantage for expected score calculation
        home_advantage_applied = Decimal("0") if neutral_site else self.home_advantage
        adjusted_home_elo = home_elo + home_advantage_applied

        # Calculate expected scores
        home_expected = self.expected_score(adjusted_home_elo, away_elo)
        away_expected = Decimal("1") - home_expected

        # Determine actual scores (1=win, 0.5=tie, 0=loss)
        if home_score > away_score:
            home_actual = Decimal("1")
            away_actual = Decimal("0")
        elif away_score > home_score:
            home_actual = Decimal("0")
            away_actual = Decimal("1")
        else:  # Tie
            home_actual = Decimal("0.5")
            away_actual = Decimal("0.5")

        # Calculate margin-of-victory multiplier
        if home_score != away_score and self.config.mov_enabled:
            if home_score > away_score:
                mov_mult = self.margin_of_victory_multiplier(
                    home_score, away_score, home_elo, away_elo
                )
            else:
                mov_mult = self.margin_of_victory_multiplier(
                    away_score, home_score, away_elo, home_elo
                )
        else:
            mov_mult = Decimal("1.0")

        # Calculate Elo changes
        k_decimal = Decimal(str(k))
        home_elo_change = k_decimal * mov_mult * (home_actual - home_expected)
        away_elo_change = k_decimal * mov_mult * (away_actual - away_expected)

        # Round to 2 decimal places
        home_elo_change = home_elo_change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        away_elo_change = away_elo_change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Calculate new ratings
        home_elo_after = home_elo + home_elo_change
        away_elo_after = away_elo + away_elo_change

        return EloUpdateResult(
            home_elo_before=home_elo,
            away_elo_before=away_elo,
            home_elo_after=home_elo_after,
            away_elo_after=away_elo_after,
            home_expected=home_expected,
            away_expected=away_expected,
            home_actual=home_actual,
            away_actual=away_actual,
            home_elo_change=home_elo_change,
            away_elo_change=away_elo_change,
            k_factor=k,
            home_advantage=home_advantage_applied,
            mov_multiplier=mov_mult,
        )

    def apply_season_regression(
        self,
        current_rating: Decimal,
        carryover_weight: Decimal = DEFAULT_CARRYOVER_WEIGHT,
        regression_target: Decimal = DEFAULT_REGRESSION_TARGET,
    ) -> Decimal:
        """Apply season-to-season regression toward the mean.

        Educational Note:
            At the start of each season, ratings regress toward the mean to
            account for:
            1. Roster changes (players traded, drafted, retired)
            2. Coaching changes
            3. General uncertainty about team quality

            FiveThirtyEight uses 75% carryover, meaning:
            - A 1700-rated team → 1651.25 (75% * 1700 + 25% * 1505)
            - A 1300-rated team → 1351.25 (75% * 1300 + 25% * 1505)

            The target is slightly above 1500 (1505) to account for
            league-wide improvement over time.

        Args:
            current_rating: Team's current Elo rating
            carryover_weight: How much of current rating to keep (default 0.75)
            regression_target: Mean to regress toward (default 1505)

        Returns:
            Regressed rating for new season start
        """
        new_rating = current_rating * carryover_weight + regression_target * (
            Decimal("1") - carryover_weight
        )
        return new_rating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# =============================================================================
# Convenience Functions
# =============================================================================


def get_elo_engine(sport: str) -> EloEngine:
    """Get an Elo engine for the specified sport.

    This is the recommended way to get an EloEngine instance.

    Args:
        sport: Sport code (e.g., "nfl", "nba")

    Returns:
        Configured EloEngine for the sport

    Example:
        >>> engine = get_elo_engine("nfl")
        >>> prob = engine.expected_score(Decimal("1600"), Decimal("1400"))
    """
    return EloEngine(sport)


def elo_to_win_probability(
    team_elo: Decimal,
    opponent_elo: Decimal,
) -> Decimal:
    """Quick helper to convert Elo difference to win probability.

    This uses the standard formula without sport-specific adjustments.

    Args:
        team_elo: Team's Elo rating
        opponent_elo: Opponent's Elo rating

    Returns:
        Win probability as Decimal
    """
    exponent = (opponent_elo - team_elo) / ELO_DIVISOR
    power = Decimal(str(10 ** float(exponent)))
    return (Decimal("1") / (Decimal("1") + power)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def win_probability_to_elo_difference(probability: Decimal) -> Decimal:
    """Convert a win probability back to Elo difference.

    Educational Note:
        This inverts the expected score formula:
        elo_diff = 400 * log10(prob / (1 - prob))

        Useful for comparing model predictions to Elo-based predictions.

    Args:
        probability: Win probability (0-1)

    Returns:
        Elo difference that would produce that probability

    Example:
        >>> diff = win_probability_to_elo_difference(Decimal("0.75"))
        >>> print(f"~{diff:.0f} Elo")  # ~191 Elo
    """
    import math

    if probability <= Decimal("0") or probability >= Decimal("1"):
        msg = "Probability must be between 0 and 1 (exclusive)"
        raise ValueError(msg)

    # Convert to float for math.log10 (required for logarithm operation)
    # Result is immediately quantized back to Decimal with proper precision
    p = float(probability)
    elo_diff = 400 * math.log10(p / (1 - p))

    return Decimal(str(elo_diff)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
