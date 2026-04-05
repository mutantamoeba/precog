"""
Unit Tests for League Priority Calculator (#560).

Tests priority-based adaptive polling: game phase urgency, market signal,
composite scoring, and budget allocation.

Reference: TESTING_STRATEGY V3.9 - Unit tests for isolated functionality
Related: Issue #560 (Adaptive polling throttle from rate budget)

Usage:
    pytest tests/unit/schedulers/test_league_priority_unit.py -v -m unit
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from precog.schedulers.league_priority import (
    DEFAULT_LEAGUE_PRIORITIES,
    DEFAULT_MARKET_THRESHOLDS,
    DEFAULT_WEIGHTS,
    LeaguePriorityCalculator,
)

# =============================================================================
# Fixtures
# =============================================================================


def _make_game(
    game_status: str = "in_progress",
    period: int = 1,
    clock_seconds: float = 600.0,
) -> dict[str, Any]:
    """Create a minimal ESPNGameFull-shaped dict for testing."""
    return {
        "metadata": {
            "espn_event_id": "401547417",
            "home_team": {"espn_team_id": "1", "team_code": "ATL"},
            "away_team": {"espn_team_id": "2", "team_code": "NO"},
        },
        "state": {
            "espn_event_id": "401547417",
            "home_score": 14,
            "away_score": 10,
            "period": period,
            "clock_seconds": clock_seconds,
            "clock_display": "10:00",
            "game_status": game_status,
            "situation": {},
            "linescores": [],
        },
    }


@pytest.fixture
def calculator() -> LeaguePriorityCalculator:
    """Default calculator with no market count function."""
    return LeaguePriorityCalculator()


@pytest.fixture
def calculator_with_markets() -> LeaguePriorityCalculator:
    """Calculator with a mock market count function."""
    mock_fn = MagicMock(return_value=10)
    return LeaguePriorityCalculator(market_count_fn=mock_fn)


# =============================================================================
# Test Game Phase Urgency
# =============================================================================


@pytest.mark.unit
class TestGamePhaseUrgency:
    """Sport-specific urgency calculations from game state."""

    # --- Football ---

    def test_football_q1_low_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Football Q1 should have low urgency (0.2)."""
        games = [_make_game(period=1, clock_seconds=600)]
        assert calculator.compute_game_phase_urgency("nfl", games) == 0.2

    def test_football_q2_low_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Football Q2 should have low urgency (0.2)."""
        games = [_make_game(period=2, clock_seconds=300)]
        assert calculator.compute_game_phase_urgency("nfl", games) == 0.2

    def test_football_q3_medium_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Football Q3 should have medium urgency (0.4)."""
        games = [_make_game(period=3, clock_seconds=600)]
        assert calculator.compute_game_phase_urgency("nfl", games) == 0.4

    def test_football_q4_early_high_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Football Q4 with >=5:00 remaining should have 0.7 urgency."""
        games = [_make_game(period=4, clock_seconds=500)]
        assert calculator.compute_game_phase_urgency("nfl", games) == 0.7

    def test_football_q4_late_max_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Football Q4 with <5:00 remaining should have max urgency (1.0)."""
        games = [_make_game(period=4, clock_seconds=299)]
        assert calculator.compute_game_phase_urgency("nfl", games) == 1.0

    def test_football_ot_max_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Football OT should have max urgency (1.0)."""
        games = [_make_game(period=5, clock_seconds=600)]
        assert calculator.compute_game_phase_urgency("nfl", games) == 1.0

    def test_ncaaf_uses_football_rules(self, calculator: LeaguePriorityCalculator) -> None:
        """NCAAF should use football urgency rules."""
        games = [_make_game(period=4, clock_seconds=100)]
        assert calculator.compute_game_phase_urgency("ncaaf", games) == 1.0

    # --- Basketball ---

    def test_basketball_q1_low_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Basketball Q1 should have low urgency (0.2)."""
        games = [_make_game(period=1, clock_seconds=500)]
        assert calculator.compute_game_phase_urgency("nba", games) == 0.2

    def test_basketball_q3_medium_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Basketball Q3 should have medium urgency (0.4)."""
        games = [_make_game(period=3, clock_seconds=400)]
        assert calculator.compute_game_phase_urgency("nba", games) == 0.4

    def test_basketball_q4_early_high_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Basketball Q4 with >=3:00 remaining should have 0.7 urgency."""
        games = [_make_game(period=4, clock_seconds=200)]
        assert calculator.compute_game_phase_urgency("nba", games) == 0.7

    def test_basketball_q4_late_max_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Basketball Q4 with <3:00 remaining should have max urgency (1.0)."""
        games = [_make_game(period=4, clock_seconds=179)]
        assert calculator.compute_game_phase_urgency("nba", games) == 1.0

    def test_basketball_ot_max_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Basketball OT should have max urgency (1.0)."""
        games = [_make_game(period=5, clock_seconds=120)]
        assert calculator.compute_game_phase_urgency("nba", games) == 1.0

    # --- Hockey ---

    def test_hockey_p1_low_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Hockey P1 should have low urgency (0.2)."""
        games = [_make_game(period=1, clock_seconds=600)]
        assert calculator.compute_game_phase_urgency("nhl", games) == 0.2

    def test_hockey_p2_medium_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Hockey P2 should have medium urgency (0.4)."""
        games = [_make_game(period=2, clock_seconds=600)]
        assert calculator.compute_game_phase_urgency("nhl", games) == 0.4

    def test_hockey_p3_early_high_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Hockey P3 with >=5:00 remaining should have 0.7 urgency."""
        games = [_make_game(period=3, clock_seconds=500)]
        assert calculator.compute_game_phase_urgency("nhl", games) == 0.7

    def test_hockey_p3_late_max_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Hockey P3 with <5:00 remaining should have max urgency (1.0)."""
        games = [_make_game(period=3, clock_seconds=100)]
        assert calculator.compute_game_phase_urgency("nhl", games) == 1.0

    def test_hockey_ot_max_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Hockey OT (period 4+) should have max urgency (1.0)."""
        games = [_make_game(period=4, clock_seconds=300)]
        assert calculator.compute_game_phase_urgency("nhl", games) == 1.0

    # --- Edge cases ---

    def test_empty_games_returns_zero(self, calculator: LeaguePriorityCalculator) -> None:
        """No games should return 0.0 urgency."""
        assert calculator.compute_game_phase_urgency("nfl", []) == 0.0

    def test_unknown_league_returns_zero(self, calculator: LeaguePriorityCalculator) -> None:
        """Unknown league code should return 0.0 urgency."""
        games = [_make_game(period=4, clock_seconds=100)]
        assert calculator.compute_game_phase_urgency("cricket", games) == 0.0

    def test_halftime_returns_low_urgency(self, calculator: LeaguePriorityCalculator) -> None:
        """Halftime status should return 0.1 urgency."""
        games = [_make_game(game_status="halftime", period=2, clock_seconds=0)]
        assert calculator.compute_game_phase_urgency("nfl", games) == 0.1

    def test_pre_game_returns_zero(self, calculator: LeaguePriorityCalculator) -> None:
        """Pre-game status should return 0.0 urgency."""
        games = [_make_game(game_status="pre", period=0, clock_seconds=0)]
        assert calculator.compute_game_phase_urgency("nfl", games) == 0.0

    def test_final_game_returns_zero(self, calculator: LeaguePriorityCalculator) -> None:
        """Final game status should return 0.0 urgency."""
        games = [_make_game(game_status="final", period=4, clock_seconds=0)]
        assert calculator.compute_game_phase_urgency("nfl", games) == 0.0

    def test_max_across_multiple_games(self, calculator: LeaguePriorityCalculator) -> None:
        """Should return max urgency across all games in the league."""
        games = [
            _make_game(period=1, clock_seconds=600),  # Q1 -> 0.2
            _make_game(period=4, clock_seconds=100),  # Q4 late -> 1.0
        ]
        assert calculator.compute_game_phase_urgency("nfl", games) == 1.0

    def test_missing_state_key(self, calculator: LeaguePriorityCalculator) -> None:
        """Game dict without 'state' key should not crash."""
        games = [{"metadata": {}}]
        # No 'state' key -> game_status defaults to 'pre' -> 0.0
        assert calculator.compute_game_phase_urgency("nfl", games) == 0.0

    def test_non_numeric_period(self, calculator: LeaguePriorityCalculator) -> None:
        """Non-numeric period should be handled gracefully."""
        game = _make_game(period=1)
        game["state"]["period"] = "invalid"
        assert calculator.compute_game_phase_urgency("nfl", [game]) == 0.2  # defaults to period 1


# =============================================================================
# Test Market Signal
# =============================================================================


@pytest.mark.unit
class TestMarketSignal:
    """Market activity signal from open market count."""

    def test_no_market_fn_returns_zero(self, calculator: LeaguePriorityCalculator) -> None:
        """No market count function -> always returns 0.0."""
        assert calculator.compute_market_signal("nfl") == 0.0

    def test_zero_markets_returns_zero(self) -> None:
        """0 open markets -> 0.0 signal."""
        calc = LeaguePriorityCalculator(market_count_fn=MagicMock(return_value=0))
        assert calc.compute_market_signal("nfl") == 0.0

    def test_low_markets_returns_low_signal(self) -> None:
        """1-5 open markets -> 0.3 signal."""
        calc = LeaguePriorityCalculator(market_count_fn=MagicMock(return_value=3))
        assert calc.compute_market_signal("nfl") == 0.3

    def test_medium_markets_returns_medium_signal(self) -> None:
        """6-15 open markets -> 0.6 signal."""
        calc = LeaguePriorityCalculator(market_count_fn=MagicMock(return_value=10))
        assert calc.compute_market_signal("nfl") == 0.6

    def test_high_markets_returns_max_signal(self) -> None:
        """16+ open markets -> 1.0 signal."""
        calc = LeaguePriorityCalculator(market_count_fn=MagicMock(return_value=20))
        assert calc.compute_market_signal("nfl") == 1.0

    def test_cache_returns_cached_value(self) -> None:
        """Second call within TTL should use cached value, not call DB."""
        mock_fn = MagicMock(return_value=10)
        calc = LeaguePriorityCalculator(
            market_count_fn=mock_fn,
            market_count_cache_ttl=300,
        )
        calc.compute_market_signal("nfl")
        calc.compute_market_signal("nfl")
        # Should only call DB once
        assert mock_fn.call_count == 1

    def test_db_error_fallback_to_cached(self) -> None:
        """DB error should fall back to last cached value."""
        mock_fn = MagicMock(side_effect=[10, Exception("DB error")])
        calc = LeaguePriorityCalculator(
            market_count_fn=mock_fn,
            market_count_cache_ttl=0,  # Force cache expiry
        )
        # First call succeeds
        first = calc.compute_market_signal("nfl")
        assert first == 0.6  # 10 markets -> 0.6

        # Second call fails -> uses cached value of 10
        second = calc.compute_market_signal("nfl")
        assert second == 0.6

    def test_db_error_no_cache_returns_zero(self) -> None:
        """DB error with no cached value should return 0.0."""
        mock_fn = MagicMock(side_effect=Exception("DB error"))
        calc = LeaguePriorityCalculator(market_count_fn=mock_fn)
        assert calc.compute_market_signal("nfl") == 0.0

    def test_custom_thresholds(self) -> None:
        """Custom market thresholds should be respected."""
        calc = LeaguePriorityCalculator(
            market_count_fn=MagicMock(return_value=3),
            market_thresholds={"low": 2, "medium": 4, "high": 10},
        )
        # 3 >= low(2) but < medium(4) -> 0.3
        assert calc.compute_market_signal("nfl") == 0.3

    def test_boundary_at_low_threshold(self) -> None:
        """Exactly at low threshold should return 0.3."""
        calc = LeaguePriorityCalculator(market_count_fn=MagicMock(return_value=1))
        assert calc.compute_market_signal("nfl") == 0.3

    def test_boundary_at_medium_threshold(self) -> None:
        """Exactly at medium threshold should return 0.6."""
        calc = LeaguePriorityCalculator(market_count_fn=MagicMock(return_value=6))
        assert calc.compute_market_signal("nfl") == 0.6

    def test_boundary_at_high_threshold(self) -> None:
        """Exactly at high threshold should return 1.0."""
        calc = LeaguePriorityCalculator(market_count_fn=MagicMock(return_value=16))
        assert calc.compute_market_signal("nfl") == 1.0


# =============================================================================
# Test Composite Score
# =============================================================================


@pytest.mark.unit
class TestCompositeScore:
    """Weighted combination of signals."""

    def test_default_weights(self) -> None:
        """Default weights should be 0.5/0.3/0.2."""
        calc = LeaguePriorityCalculator()
        assert calc._weights == DEFAULT_WEIGHTS

    def test_all_signals_max(self) -> None:
        """All signals at max (1.0) should produce composite of ~1.0 (weighted by static)."""
        mock_fn = MagicMock(return_value=20)  # -> 1.0 market signal
        calc = LeaguePriorityCalculator(
            market_count_fn=mock_fn,
            league_priorities={"nfl": 1.0},
        )
        # Q4 late game -> game_phase = 1.0
        games = [_make_game(period=4, clock_seconds=100)]
        score = calc.compute_composite_priority("nfl", games)
        assert abs(score - 1.0) < 0.01

    def test_all_signals_zero(self) -> None:
        """All signals at zero should produce composite of 0.0 (modulo static)."""
        calc = LeaguePriorityCalculator(
            league_priorities={"nfl": 0.0},
        )
        # No games, no market fn, static = 0.0
        score = calc.compute_composite_priority("nfl", [])
        assert score == 0.0

    def test_only_static_priority(self) -> None:
        """With no games and no market fn, only static priority contributes."""
        calc = LeaguePriorityCalculator(
            league_priorities={"nfl": 0.8},
        )
        score = calc.compute_composite_priority("nfl", [])
        # game_phase=0.0, markets=0.0, static=0.8
        # weighted: 0.5*0 + 0.3*0 + 0.2*0.8 = 0.16, normalized /1.0 = 0.16
        assert abs(score - 0.16) < 0.01

    def test_custom_weights(self) -> None:
        """Custom weights should be respected and normalized."""
        calc = LeaguePriorityCalculator(
            weights={"game_phase": 1.0, "active_markets": 0.0, "static_priority": 0.0},
            league_priorities={"nfl": 0.5},
        )
        games = [_make_game(period=4, clock_seconds=100)]
        score = calc.compute_composite_priority("nfl", games)
        # Only game_phase matters (weight 1.0), urgency = 1.0
        assert abs(score - 1.0) < 0.01

    def test_weight_normalization(self) -> None:
        """Weights that don't sum to 1.0 should be normalized."""
        calc = LeaguePriorityCalculator(
            weights={"game_phase": 2.0, "active_markets": 0.0, "static_priority": 0.0},
            league_priorities={"nfl": 0.0},
        )
        games = [_make_game(period=4, clock_seconds=100)]
        score = calc.compute_composite_priority("nfl", games)
        # 2.0 * 1.0 / 2.0 = 1.0
        assert abs(score - 1.0) < 0.01

    def test_zero_total_weight_returns_zero(self) -> None:
        """If all weights are zero, composite should return 0.0."""
        calc = LeaguePriorityCalculator(
            weights={"game_phase": 0.0, "active_markets": 0.0, "static_priority": 0.0},
        )
        games = [_make_game(period=4, clock_seconds=100)]
        assert calc.compute_composite_priority("nfl", games) == 0.0

    def test_unknown_league_default_static(self) -> None:
        """Unknown league should use default static priority of 0.5."""
        calc = LeaguePriorityCalculator()
        # Unknown league -> game_phase = 0.0, markets = 0.0, static defaults to 0.5
        # However, compute_game_phase_urgency returns 0.0 for unknown league
        score = calc.compute_composite_priority("cricket", [_make_game()])
        # 0.5*0.0 + 0.3*0.0 + 0.2*0.5 = 0.1
        assert abs(score - 0.1) < 0.01


# =============================================================================
# Test Budget Allocation
# =============================================================================


@pytest.mark.unit
class TestBudgetAllocation:
    """Proportional budget allocation across tracking leagues."""

    def test_single_league_gets_full_budget(self, calculator: LeaguePriorityCalculator) -> None:
        """Single tracking league should get the full budget."""
        result = calculator.allocate_budget(
            tracking_leagues=["nfl"],
            budget_available=240,
            base_interval=30,
            max_throttled_interval=60,
            league_games={},
        )
        assert "nfl" in result
        # 240 req/hr -> 3600/240 = 15s, but base_interval is 30
        assert result["nfl"] == 30

    def test_empty_leagues_returns_empty(self, calculator: LeaguePriorityCalculator) -> None:
        """No tracking leagues should return empty dict."""
        result = calculator.allocate_budget(
            tracking_leagues=[],
            budget_available=240,
            base_interval=30,
            max_throttled_interval=60,
            league_games={},
        )
        assert result == {}

    def test_zero_budget_gives_max_interval(self, calculator: LeaguePriorityCalculator) -> None:
        """Zero budget should give all leagues max_throttled_interval."""
        result = calculator.allocate_budget(
            tracking_leagues=["nfl", "nba"],
            budget_available=0,
            base_interval=30,
            max_throttled_interval=60,
            league_games={},
        )
        assert result["nfl"] == 60
        assert result["nba"] == 60

    def test_equal_priority_uniform_allocation(self) -> None:
        """All leagues with equal priority -> uniform allocation."""
        calc = LeaguePriorityCalculator(
            league_priorities={"nfl": 0.5, "nba": 0.5, "nhl": 0.5},
        )
        result = calc.allocate_budget(
            tracking_leagues=["nfl", "nba", "nhl"],
            budget_available=180,
            base_interval=30,
            max_throttled_interval=60,
            league_games={},
        )
        # Equal priority -> uniform: 180/3 = 60 req/hr each -> 3600/60 = 60s
        assert result["nfl"] == result["nba"] == result["nhl"]

    def test_proportional_allocation_high_vs_low(self) -> None:
        """Higher priority league should get shorter interval."""
        mock_fn = MagicMock(return_value=0)
        calc = LeaguePriorityCalculator(
            market_count_fn=mock_fn,
            league_priorities={"nfl": 1.0, "nba": 0.1},
        )
        # NFL with live Q4 game, NBA with Q1 game
        league_games = {
            "nfl": [_make_game(period=4, clock_seconds=100)],  # urgency 1.0
            "nba": [_make_game(period=1, clock_seconds=600)],  # urgency 0.2
        }
        result = calc.allocate_budget(
            tracking_leagues=["nfl", "nba"],
            budget_available=180,
            base_interval=30,
            max_throttled_interval=60,
            league_games=league_games,
        )
        # NFL should have shorter interval (higher priority)
        assert result["nfl"] <= result["nba"]

    def test_never_exceeds_budget(self) -> None:
        """Total req/hr should never exceed budget_available."""
        mock_fn = MagicMock(return_value=10)
        calc = LeaguePriorityCalculator(
            market_count_fn=mock_fn,
            league_priorities={"nfl": 0.8, "nba": 0.7, "nhl": 0.5, "ncaaf": 0.6},
        )
        league_games = {
            "nfl": [_make_game(period=4, clock_seconds=100)],
            "nba": [_make_game(period=2, clock_seconds=300)],
            "nhl": [_make_game(period=1, clock_seconds=600)],
            "ncaaf": [_make_game(period=3, clock_seconds=400)],
        }
        result = calc.allocate_budget(
            tracking_leagues=["nfl", "nba", "nhl", "ncaaf"],
            budget_available=180,
            base_interval=30,
            max_throttled_interval=120,  # Higher cap so budget math works
            league_games=league_games,
        )
        total_req_hr = sum(3600 / iv for iv in result.values())
        assert total_req_hr <= 180 + 1  # +1 for rounding tolerance

    def test_interval_respects_base_minimum(self) -> None:
        """No interval should be below base_interval."""
        mock_fn = MagicMock(return_value=20)
        calc = LeaguePriorityCalculator(
            market_count_fn=mock_fn,
            league_priorities={"nfl": 1.0},
        )
        result = calc.allocate_budget(
            tracking_leagues=["nfl"],
            budget_available=1000,  # Very generous budget
            base_interval=30,
            max_throttled_interval=60,
            league_games={"nfl": [_make_game(period=4, clock_seconds=100)]},
        )
        assert result["nfl"] >= 30

    def test_interval_capped_at_max(self) -> None:
        """No interval should exceed max_throttled_interval."""
        calc = LeaguePriorityCalculator(
            league_priorities={"nfl": 0.01, "nba": 0.01},
        )
        result = calc.allocate_budget(
            tracking_leagues=["nfl", "nba"],
            budget_available=10,  # Very tight budget
            base_interval=30,
            max_throttled_interval=60,
            league_games={},
        )
        for iv in result.values():
            assert iv <= 60

    def test_all_zero_priority_fallback(self) -> None:
        """All-zero priorities should fall back to uniform allocation."""
        calc = LeaguePriorityCalculator(
            league_priorities={"nfl": 0.0, "nba": 0.0},
        )
        result = calc.allocate_budget(
            tracking_leagues=["nfl", "nba"],
            budget_available=120,
            base_interval=30,
            max_throttled_interval=60,
            league_games={},
        )
        # Both should get the same interval (uniform)
        assert result["nfl"] == result["nba"]

    def test_missing_games_uses_empty_list(self) -> None:
        """League not in league_games should use empty game list."""
        calc = LeaguePriorityCalculator(
            league_priorities={"nfl": 0.8},
        )
        result = calc.allocate_budget(
            tracking_leagues=["nfl"],
            budget_available=120,
            base_interval=30,
            max_throttled_interval=60,
            league_games={},  # No games for any league
        )
        assert "nfl" in result


# =============================================================================
# Test Config Integration
# =============================================================================


@pytest.mark.unit
class TestConfigIntegration:
    """YAML config parsing and missing config fallback."""

    def test_default_weights_match_constants(self) -> None:
        """Default weights should match the module-level constants."""
        calc = LeaguePriorityCalculator()
        assert calc._weights == DEFAULT_WEIGHTS

    def test_default_league_priorities_match_constants(self) -> None:
        """Default league priorities should match the module-level constants."""
        calc = LeaguePriorityCalculator()
        assert calc._league_priorities == DEFAULT_LEAGUE_PRIORITIES

    def test_default_market_thresholds_match_constants(self) -> None:
        """Default market thresholds should match the module-level constants."""
        calc = LeaguePriorityCalculator()
        assert calc._market_thresholds == DEFAULT_MARKET_THRESHOLDS

    def test_custom_config_overrides_defaults(self) -> None:
        """Custom config should fully override defaults."""
        custom_weights = {"game_phase": 0.7, "active_markets": 0.2, "static_priority": 0.1}
        custom_priorities = {"nfl": 0.9, "nba": 0.5}
        custom_thresholds = {"low": 2, "medium": 10, "high": 25}

        calc = LeaguePriorityCalculator(
            weights=custom_weights,
            league_priorities=custom_priorities,
            market_thresholds=custom_thresholds,
        )
        assert calc._weights == custom_weights
        assert calc._league_priorities == custom_priorities
        assert calc._market_thresholds == custom_thresholds

    def test_yaml_string_weights_parsed_as_float(self) -> None:
        """Weights from YAML (as strings) should work when pre-parsed to float.

        In production, the YAML loader returns strings for Decimal safety.
        The caller is responsible for parsing to float before passing to
        the calculator. This test verifies the calculator works with floats.
        """
        # Simulate what the poller would do: parse YAML strings to float
        weights_from_yaml = {
            "game_phase": "0.50",
            "active_markets": "0.30",
            "static_priority": "0.20",
        }
        parsed_weights = {k: float(v) for k, v in weights_from_yaml.items()}

        calc = LeaguePriorityCalculator(weights=parsed_weights)
        assert abs(calc._weights["game_phase"] - 0.5) < 0.001

    def test_missing_weight_key_uses_default(self) -> None:
        """Missing weight key should use 0.0 from dict.get()."""
        calc = LeaguePriorityCalculator(
            weights={"game_phase": 1.0},  # Missing active_markets and static_priority
        )
        games = [_make_game(period=4, clock_seconds=100)]
        # Should not crash even with missing keys
        score = calc.compute_composite_priority("nfl", games)
        assert score >= 0.0


# =============================================================================
# Test Poller Integration (priority calculator in ESPNGamePoller)
# =============================================================================


@pytest.mark.unit
class TestPollerPriorityIntegration:
    """Verify ESPNGamePoller uses priority calculator when present."""

    def test_no_calculator_uniform_allocation(self) -> None:
        """Without priority calculator, all tracking leagues get same interval."""
        from precog.schedulers.espn_game_poller import (
            LEAGUE_STATE_TRACKING,
            ESPNGamePoller,
        )

        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_client,
            rate_budget_per_hour=250,
            priority_calculator=None,
        )
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_states["nba"] = LEAGUE_STATE_TRACKING
        poller._league_states["nhl"] = LEAGUE_STATE_TRACKING

        poller._recalculate_league_intervals()

        # All tracking leagues should have the same interval (uniform)
        tracking_intervals = [poller._league_intervals[lg] for lg in ["nfl", "nba", "nhl"]]
        assert len(set(tracking_intervals)) == 1

    def test_with_calculator_priority_allocation(self) -> None:
        """With priority calculator, tracking leagues get different intervals."""
        from precog.schedulers.espn_game_poller import (
            LEAGUE_STATE_TRACKING,
            ESPNGamePoller,
        )

        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []

        # Create a mock calculator that returns fixed intervals
        mock_calculator = MagicMock()
        mock_calculator.allocate_budget.return_value = {
            "nfl": 30,
            "nba": 45,
            "nhl": 60,
        }

        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_client,
            rate_budget_per_hour=250,
            priority_calculator=mock_calculator,
        )
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_states["nba"] = LEAGUE_STATE_TRACKING
        poller._league_states["nhl"] = LEAGUE_STATE_TRACKING

        poller._recalculate_league_intervals()

        # Should use priority-based intervals
        assert poller._league_intervals["nfl"] == 30
        assert poller._league_intervals["nba"] == 45
        assert poller._league_intervals["nhl"] == 60

    def test_calculator_error_falls_back_to_uniform(self) -> None:
        """If calculator raises, fall back to uniform allocation."""
        from precog.schedulers.espn_game_poller import (
            LEAGUE_STATE_TRACKING,
            ESPNGamePoller,
        )

        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []

        mock_calculator = MagicMock()
        mock_calculator.allocate_budget.side_effect = RuntimeError("calculator broke")

        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_client,
            rate_budget_per_hour=250,
            priority_calculator=mock_calculator,
        )
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_states["nba"] = LEAGUE_STATE_TRACKING
        poller._league_states["nhl"] = LEAGUE_STATE_TRACKING

        # Should not raise
        poller._recalculate_league_intervals()

        # All tracking leagues should have the same interval (uniform fallback)
        tracking_intervals = [poller._league_intervals[lg] for lg in ["nfl", "nba", "nhl"]]
        assert len(set(tracking_intervals)) == 1

    def test_no_throttle_needed_skips_calculator(self) -> None:
        """When within budget, calculator should not be called."""
        from precog.schedulers.espn_game_poller import (
            LEAGUE_STATE_DISCOVERY,
            LEAGUE_STATE_TRACKING,
            ESPNGamePoller,
        )

        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []

        mock_calculator = MagicMock()

        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_client,
            rate_budget_per_hour=500,  # Enough for 2 at full speed
            priority_calculator=mock_calculator,
        )
        # Only 1 tracking -> no throttle needed
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_states["nba"] = LEAGUE_STATE_DISCOVERY
        poller._league_states["nhl"] = LEAGUE_STATE_DISCOVERY

        poller._recalculate_league_intervals()

        # Calculator should not have been called
        mock_calculator.allocate_budget.assert_not_called()

    def test_league_last_games_stored(self) -> None:
        """_evaluate_league_state should store games in _league_last_games."""
        from precog.schedulers.espn_game_poller import ESPNGamePoller

        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_client,
        )

        games = [_make_game(game_status="in_progress", period=2, clock_seconds=300)]
        poller._evaluate_league_state("nfl", games)

        assert poller._league_last_games["nfl"] == games

    def test_priority_recalculates_during_tracking(self) -> None:
        """Intervals should recalculate on every poll when priority calculator
        is active, not just on state transitions. This verifies the fix for the
        bug where game-phase urgency had zero effect after initial TRACKING entry.
        """
        from precog.schedulers.espn_game_poller import (
            LEAGUE_STATE_TRACKING,
            ESPNGamePoller,
        )

        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []

        mock_calculator = MagicMock()
        mock_calculator.allocate_budget.return_value = {"nfl": 20, "nba": 45, "nhl": 60}

        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_client,
            rate_budget_per_hour=250,
            priority_calculator=mock_calculator,
        )
        # All already TRACKING — no state transition will occur
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_states["nba"] = LEAGUE_STATE_TRACKING
        poller._league_states["nhl"] = LEAGUE_STATE_TRACKING

        # Simulate a poll with live games (has_live=True, same state)
        live_games = [_make_game(game_status="in_progress", period=4, clock_seconds=120)]
        poller._evaluate_league_state("nfl", live_games)

        # The calculator should have been called even though no state transition
        assert mock_calculator.allocate_budget.called, (
            "Priority calculator should be called on every poll during TRACKING, "
            "not just on state transitions"
        )

    def test_league_last_games_cleared_on_discovery(self) -> None:
        """_league_last_games should be cleaned up when transitioning to DISCOVERY."""
        from precog.schedulers.espn_game_poller import (
            LEAGUE_STATE_TRACKING,
            ESPNGamePoller,
        )

        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_client,
        )
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_last_games["nfl"] = [_make_game()]

        # Transition to DISCOVERY (no live games)
        poller._evaluate_league_state("nfl", [])

        assert "nfl" not in poller._league_last_games, (
            "Stale game data should be cleaned on TRACKING -> DISCOVERY"
        )
