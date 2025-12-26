"""Unit tests for elo_computation_service module.

This module tests the EloComputationService class that orchestrates
Elo rating computation from historical games, storing results in
elo_calculation_log for audit.

Reference: Phase 2C - Elo rating computation infrastructure
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from precog.analytics.elo_computation_service import (
    ComputationResult,
    EloComputationService,
    TeamRatingState,
)


class TestTeamRatingState:
    """Tests for TeamRatingState dataclass."""

    def test_initial_state(self) -> None:
        """Verify initial team rating state has correct defaults."""
        state = TeamRatingState(rating=Decimal("1500"))

        assert state.rating == Decimal("1500")
        assert state.games_played == 0
        assert state.peak_rating == Decimal("1500")
        assert state.lowest_rating == Decimal("1500")
        assert state.last_game_date is None

    def test_update_after_game_increases_games_played(self) -> None:
        """Verify games_played increments after update."""
        state = TeamRatingState(rating=Decimal("1500"))
        state.update_after_game(Decimal("1520"), date(2024, 1, 1))

        assert state.games_played == 1
        assert state.rating == Decimal("1520")
        assert state.last_game_date == date(2024, 1, 1)

    def test_update_after_game_tracks_peak(self) -> None:
        """Verify peak rating is tracked correctly."""
        state = TeamRatingState(rating=Decimal("1500"))
        state.update_after_game(Decimal("1600"), date(2024, 1, 1))
        state.update_after_game(Decimal("1550"), date(2024, 1, 8))

        assert state.peak_rating == Decimal("1600")
        assert state.rating == Decimal("1550")

    def test_update_after_game_tracks_lowest(self) -> None:
        """Verify lowest rating is tracked correctly."""
        state = TeamRatingState(rating=Decimal("1500"))
        state.update_after_game(Decimal("1400"), date(2024, 1, 1))
        state.update_after_game(Decimal("1450"), date(2024, 1, 8))

        assert state.lowest_rating == Decimal("1400")
        assert state.rating == Decimal("1450")


class TestComputationResult:
    """Tests for ComputationResult dataclass."""

    def test_result_initialization(self) -> None:
        """Verify result initializes with correct defaults."""
        result = ComputationResult(sport="nfl", seasons=[2020, 2021])

        assert result.sport == "nfl"
        assert result.seasons == [2020, 2021]
        assert result.games_processed == 0
        assert result.games_skipped == 0
        assert result.teams_updated == 0
        assert result.logs_inserted == 0
        assert result.duration_seconds == 0.0
        assert result.errors == []

    def test_result_tracks_games_processed(self) -> None:
        """Verify games_processed can be incremented."""
        result = ComputationResult(sport="nba", seasons=[2019])
        result.games_processed = 100

        assert result.games_processed == 100


class TestEloComputationService:
    """Tests for EloComputationService class."""

    def test_service_requires_connection(self) -> None:
        """Verify service requires a database connection."""
        mock_conn = MagicMock()
        service = EloComputationService(mock_conn)

        assert service.conn == mock_conn

    def test_service_stores_calculation_source(self) -> None:
        """Verify calculation_source is stored correctly."""
        mock_conn = MagicMock()
        service = EloComputationService(
            mock_conn,
            calculation_source="backfill",
            calculation_version="1.0",
        )

        assert service.calculation_source == "backfill"
        assert service.calculation_version == "1.0"

    def test_service_has_compute_ratings_method(self) -> None:
        """Verify service has compute_ratings method."""
        mock_conn = MagicMock()
        service = EloComputationService(mock_conn)

        assert hasattr(service, "compute_ratings")
        assert callable(service.compute_ratings)

    def test_get_or_create_rating_creates_new(self) -> None:
        """Verify get_or_create_rating creates new team state."""
        mock_conn = MagicMock()
        service = EloComputationService(mock_conn)

        state = service.get_or_create_rating("nfl", "KC")

        assert state.rating == Decimal("1500")  # Default initial rating
        # Verify team is now tracked via get_team_ratings
        ratings = service.get_team_ratings("nfl")
        assert "KC" in ratings

    def test_get_or_create_rating_returns_existing(self) -> None:
        """Verify get_or_create_rating returns existing state."""
        mock_conn = MagicMock()
        service = EloComputationService(mock_conn)

        # Create first
        state1 = service.get_or_create_rating("nfl", "KC")
        state1.rating = Decimal("1600")  # Modify rating

        # Get again - should return same object
        state2 = service.get_or_create_rating("nfl", "KC")

        assert state2.rating == Decimal("1600")
        assert state1 is state2

    def test_service_default_values(self) -> None:
        """Verify service has correct default values."""
        mock_conn = MagicMock()
        service = EloComputationService(mock_conn)

        assert service.initial_rating == Decimal("1500")
        assert service.apply_season_regression is True


class TestComputeEloRatingsHelper:
    """Tests for compute_elo_ratings helper function."""

    def test_helper_function_exists(self) -> None:
        """Verify compute_elo_ratings function is importable."""
        from precog.analytics.elo_computation_service import compute_elo_ratings

        assert callable(compute_elo_ratings)

    def test_get_elo_computation_stats_exists(self) -> None:
        """Verify get_elo_computation_stats function is importable."""
        from precog.analytics.elo_computation_service import get_elo_computation_stats

        assert callable(get_elo_computation_stats)


class TestAnalyticsModuleExports:
    """Tests for analytics module exports."""

    def test_exports_from_analytics_module(self) -> None:
        """Verify EloComputationService is exported from analytics module."""
        from precog.analytics import (
            ComputationResult,
            EloComputationService,
            TeamRatingState,
            compute_elo_ratings,
            get_elo_computation_stats,
        )

        assert EloComputationService is not None
        assert TeamRatingState is not None
        assert ComputationResult is not None
        assert compute_elo_ratings is not None
        assert get_elo_computation_stats is not None
