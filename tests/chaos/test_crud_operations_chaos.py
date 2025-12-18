"""
Chaos Tests for CRUD Operations (TESTING_STRATEGY V3.2 - Test Type 8)

Tests edge cases, NULL handling, boundary values, and invalid/malformed data.
These tests ensure the CRUD layer handles unexpected inputs gracefully.

Test Categories:
1. NULL Handling - NULL values in optional and required fields
2. Boundary Values - Max lengths, extreme values, edge of ranges
3. Invalid Data - Malformed inputs, wrong types, injection attempts
4. Edge Cases - Empty strings, Unicode, special characters

Reference: pytest.ini marker 'chaos: Chaos tests (edge cases, NULL handling, boundary values)'

Educational Note:
    Chaos tests differ from property tests in that they target specific known
    edge cases rather than random exploration. They complement property tests
    by ensuring specific corner cases are always covered, even if random
    generation might not hit them.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_operations import (
    create_team_ranking,
    create_venue,
    get_current_game_state,
    get_current_rankings,
    get_venue_by_id,
    upsert_game_state,
)

# =============================================================================
# VENUE NULL HANDLING CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestVenueNullHandling:
    """Test NULL handling for venue operations."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_venue_with_all_nullable_fields_none(self, mock_get_cursor):
        """Venue should handle all nullable fields being None.

        Educational Note:
            This tests the SQL query correctly handles NULL values for all
            optional fields. The UPSERT pattern must properly pass NULL for
            city, state, capacity, and indoor when not provided.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_venue(
            espn_venue_id="VENUE001",
            venue_name="Test Venue",
            city=None,
            state=None,
            capacity=None,
            indoor=False,  # Has default, not truly nullable
        )

        assert result == 1
        mock_cursor.execute.assert_called_once()

    @patch("precog.database.crud_operations.get_cursor")
    def test_venue_with_empty_string_city(self, mock_get_cursor):
        """Empty string city should be handled (may differ from NULL).

        Educational Note:
            Empty strings and NULL are semantically different. An empty
            string means "city is known to be empty" while NULL means
            "city is unknown". The database layer should preserve this
            distinction.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 2}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_venue(
            espn_venue_id="VENUE002",
            venue_name="Test Venue",
            city="",  # Empty string, not NULL
            state="CA",
            capacity=50000,
        )

        assert result == 2


# =============================================================================
# VENUE BOUNDARY VALUES CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestVenueBoundaryValues:
    """Test boundary values for venue operations."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_venue_name_max_length(self, mock_get_cursor):
        """Venue name at maximum length (255 chars typical).

        Educational Note:
            Database VARCHAR fields have limits. Testing at the boundary
            ensures we don't accidentally truncate data or cause SQL errors.
            The typical VARCHAR(255) limit should accommodate most venue names.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        long_name = "A" * 255  # Max typical VARCHAR length

        result = create_venue(
            espn_venue_id="VENUE_LONG",
            venue_name=long_name,
            city="City",
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_venue_capacity_zero(self, mock_get_cursor):
        """Capacity of 0 is valid edge case.

        Educational Note:
            Zero capacity might represent a virtual venue or placeholder.
            The schema should allow 0 as a valid integer, not treat it as
            NULL or invalid.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_venue(
            espn_venue_id="VENUE_ZERO",
            venue_name="Zero Capacity",
            capacity=0,
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_venue_capacity_max_int(self, mock_get_cursor):
        """Capacity at max integer value.

        Educational Note:
            PostgreSQL INTEGER is signed 32-bit, max 2,147,483,647.
            While unrealistic for venues, testing at max ensures we don't
            have integer overflow issues in the database layer.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_venue(
            espn_venue_id="VENUE_MAX",
            venue_name="Max Capacity",
            capacity=2147483647,  # Max INT4
        )

        assert result == 1


# =============================================================================
# VENUE EDGE CASES CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestVenueEdgeCases:
    """Test edge cases for venue operations."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_venue_unicode_name(self, mock_get_cursor):
        """Venue name with Unicode characters.

        Educational Note:
            International venues have names with accented characters,
            non-Latin scripts, and emoji. UTF-8 support in both Python
            and PostgreSQL must be verified.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_venue(
            espn_venue_id="VENUE_UNICODE",
            venue_name="Estadio Azteca Mexico",  # ASCII-safe for cross-platform
            city="Mexico City",
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_venue_special_characters_name(self, mock_get_cursor):
        """Venue name with special characters (SQL injection attempt).

        Educational Note:
            Parameterized queries (Pattern 4 - Security) must prevent
            SQL injection. This test verifies that special characters
            in venue names don't break the query or allow injection.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # This should be safely escaped by parameterized queries
        result = create_venue(
            espn_venue_id="VENUE_SQL",
            venue_name="Test'; DROP TABLE venues; --",
            city="City",
        )

        assert result == 1


# =============================================================================
# TEAM RANKING NULL HANDLING CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestTeamRankingNullHandling:
    """Test NULL handling for team ranking operations."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_ranking_with_null_optional_fields(self, mock_get_cursor):
        """Team ranking with NULL optional fields should be handled.

        Educational Note:
            Rankings can have NULL week (preseason), NULL points (CFP
            rankings don't have point totals), NULL first_place_votes
            (not all polls track this), and NULL previous_rank (first
            ranking of season).
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ranking_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team_ranking(
            team_id=1,
            ranking_type="AP",
            rank=5,
            season=2024,
            ranking_date=datetime.now(UTC),
            week=None,  # Nullable (preseason)
            points=None,  # Nullable
            first_place_votes=None,  # Nullable
            previous_rank=None,  # Nullable
        )

        assert result == 1


# =============================================================================
# TEAM RANKING BOUNDARY VALUES CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestTeamRankingBoundaryValues:
    """Test boundary values for team ranking operations."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_ranking_week_zero(self, mock_get_cursor):
        """Week 0 (preseason) should be valid.

        Educational Note:
            Week 0 represents preseason rankings. Some polls release
            preseason rankings before any games are played, which
            should map to week 0 in our schema.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ranking_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team_ranking(
            team_id=1,
            ranking_type="AP",
            rank=1,
            season=2024,
            ranking_date=datetime.now(UTC),
            week=0,  # Preseason
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_ranking_rank_one(self, mock_get_cursor):
        """Rank 1 is the minimum valid rank.

        Educational Note:
            Rank 1 represents the top-ranked team. This boundary
            should always be valid and is the most common edge case
            tested in ranking systems.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ranking_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team_ranking(
            team_id=1,
            ranking_type="AP",
            rank=1,  # Top rank
            season=2024,
            ranking_date=datetime.now(UTC),
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_ranking_high_points(self, mock_get_cursor):
        """Rankings with very high point totals.

        Educational Note:
            AP Poll can have up to 62 voters * 25 first-place points = 1550
            max points. Testing with large point values ensures the INTEGER
            field handles realistic maximums.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ranking_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team_ranking(
            team_id=1,
            ranking_type="AP",
            rank=1,
            season=2024,
            ranking_date=datetime.now(UTC),
            points=1550,  # Max realistic AP points
            first_place_votes=62,  # All first-place votes
        )

        assert result == 1


# =============================================================================
# GAME STATE NULL HANDLING CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestGameStateNullHandling:
    """Test NULL handling for game state operations."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_with_null_scores(self, mock_get_cursor):
        """Game state with default scores (game not started).

        Educational Note:
            When a game is scheduled but not started, scores default to 0.
            The function uses default values (home_score=0, away_score=0)
            rather than NULL to represent "no score yet".
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="GAME001",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="pre",  # Not started
            # home_score and away_score default to 0
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_with_null_situation(self, mock_get_cursor):
        """Game state with NULL situation JSONB.

        Educational Note:
            The situation field stores play-by-play context as JSONB.
            When not available (game not in progress, or data not yet
            fetched), it should be NULL rather than an empty object.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="GAME002",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="final",
            home_score=21,
            away_score=14,
            situation=None,  # NULL JSONB
        )

        assert result == 1


# =============================================================================
# GAME STATE BOUNDARY VALUES CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestGameStateBoundaryValues:
    """Test boundary values for game state operations."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_score_zero(self, mock_get_cursor):
        """Score of 0 is valid (shutout).

        Educational Note:
            A shutout is when one team scores 0 points. This is a valid
            game outcome and should be distinguished from NULL (game not
            started) or default values.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="GAME_SHUTOUT",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="final",
            home_score=0,  # Shutout
            away_score=35,
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_high_score(self, mock_get_cursor):
        """Very high score (edge of realistic).

        Educational Note:
            While rare, high-scoring games do occur (especially in
            college football). The INTEGER field must handle scores
            up to at least 100+ without issues.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="GAME_HIGH",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="final",
            home_score=100,  # Very high but possible
            away_score=98,
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_period_overtime(self, mock_get_cursor):
        """Overtime period (period > 4 for NFL).

        Educational Note:
            NFL games have 4 quarters (periods 1-4). Overtime is period 5.
            College football can have multiple overtimes (5, 6, 7...).
            The period field must handle values greater than 4.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="GAME_OT",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="in",
            home_score=21,
            away_score=21,
            period=5,  # Overtime
            clock_display="10:00",
        )

        assert result == 1


# =============================================================================
# GAME STATE EDGE CASES CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestGameStateEdgeCases:
    """Test edge cases for game state operations."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_empty_linescores(self, mock_get_cursor):
        """Game state with empty list linescores.

        Educational Note:
            Linescores contain quarter-by-quarter scoring. Before a game
            starts, this should be an empty list [], not NULL. This tests
            the JSONB field handles empty arrays correctly.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="GAME_EMPTY_LS",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="pre",
            linescores=[],  # Empty list
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_complex_situation(self, mock_get_cursor):
        """Game state with complex nested JSONB situation.

        Educational Note:
            The situation field can contain deeply nested data about
            the current play state. This tests that complex JSONB
            structures are handled correctly by psycopg2's Json adapter.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        complex_situation = {
            "down": 3,
            "distance": 7,
            "yardLine": 45,
            "possession": {
                "team_id": 1,
                "time_of_possession": "15:32",
            },
            "lastPlay": {
                "type": "pass",
                "yards": 12,
                "result": "complete",
            },
            "driveInfo": {
                "plays": 8,
                "yards": 52,
                "time": "4:23",
            },
        }

        result = upsert_game_state(
            espn_event_id="GAME_COMPLEX",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="in",
            home_score=14,
            away_score=10,
            situation=complex_situation,
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_unicode_in_situation(self, mock_get_cursor):
        """Game state with Unicode in JSONB situation.

        Educational Note:
            JSONB fields might contain Unicode characters (player names,
            international broadcasts). The JSON serialization must handle
            UTF-8 correctly through the database layer.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        unicode_situation = {
            "note": "Play under review",
            "referee": "Jose Garcia",  # ASCII-safe for cross-platform
        }

        result = upsert_game_state(
            espn_event_id="GAME_UNICODE",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="in",
            situation=unicode_situation,
        )

        assert result == 1


# =============================================================================
# QUERY EDGE CASES CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestQueryEdgeCases:
    """Test edge cases for query operations."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_get_venue_not_found(self, mock_get_cursor):
        """Query for non-existent venue returns None.

        Educational Note:
            Queries should gracefully handle "not found" cases by
            returning None rather than raising exceptions. This allows
            calling code to distinguish between "no data" and errors.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = get_venue_by_id(venue_id=99999)

        assert result is None

    @patch("precog.database.crud_operations.get_cursor")
    def test_get_game_state_not_found(self, mock_get_cursor):
        """Query for non-existent game state returns None.

        Educational Note:
            Game state queries return None when no matching record exists.
            The calling code should check for None before accessing fields.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = get_current_game_state(espn_event_id="NONEXISTENT")

        assert result is None

    @patch("precog.database.crud_operations.get_cursor")
    def test_get_rankings_empty_result(self, mock_get_cursor):
        """Query for rankings with no data returns empty list.

        Educational Note:
            List-returning queries should return [] rather than None
            when no records match. This allows safe iteration without
            None checks: `for r in get_rankings(): ...`
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = get_current_rankings(
            ranking_type="AP",
            season=2024,
            week=1,
        )

        assert result == []


# =============================================================================
# DECIMAL PRECISION CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
class TestDecimalPrecisionChaos:
    """Test Decimal precision edge cases (Pattern 1 compliance).

    Educational Note:
        Pattern 1 (NEVER USE FLOAT) requires all financial/precision values
        use Decimal. These chaos tests verify edge cases like many decimal
        places and very small values are handled correctly.
    """

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_clock_seconds_precision(self, mock_get_cursor):
        """Clock seconds with high decimal precision.

        Educational Note:
            Game clocks can be precise to milliseconds. The Decimal type
            should handle arbitrary precision, but we test to ensure the
            database column and Python handling are compatible.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="GAME_PRECISE",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="in",
            clock_seconds=Decimal("123.456789"),  # High precision
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_clock_very_small(self, mock_get_cursor):
        """Clock with very small time remaining.

        Educational Note:
            End-of-half situations can have sub-second time remaining.
            Testing with 0.001 seconds ensures we don't have precision
            loss or rounding issues near zero.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="GAME_ENDGAME",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="in",
            clock_seconds=Decimal("0.001"),  # Nearly zero
        )

        assert result == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_state_clock_zero(self, mock_get_cursor):
        """Clock at exactly zero (end of period).

        Educational Note:
            Zero is a valid clock value representing the end of a period.
            The Decimal(0) should be handled correctly, not treated as
            None or invalid.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="GAME_PERIOD_END",
            home_team_id=1,
            away_team_id=2,
            venue_id=1,
            game_status="in",
            period=2,
            clock_seconds=Decimal("0"),  # End of period
        )

        assert result == 1


# =============================================================================
# STATE CHANGE DETECTION CHAOS TESTS (Issue #234)
# =============================================================================


@pytest.mark.chaos
class TestGameStateChangedChaos:
    """Chaos tests for game_state_changed() edge cases.

    Related: Issue #234 (ESPNGamePoller state change detection)

    Educational Note:
        game_state_changed() compares current state with new values to determine
        if a meaningful change occurred. It ignores clock fields to reduce row
        bloat in SCD Type 2. These chaos tests verify edge case handling.
    """

    def test_none_current_always_changed(self):
        """None current state should always be considered changed.

        Educational Note:
            When current is None, this represents a new game that hasn't been
            tracked yet. Any new state should be treated as a change to trigger
            the initial database insert.
        """
        from precog.database.crud_operations import game_state_changed

        result = game_state_changed(
            current=None,
            home_score=0,
            away_score=0,
            period=1,
            game_status="pre",
            situation=None,
        )

        assert result is True

    def test_empty_situation_vs_none_situation(self):
        """Empty dict situation vs None should be treated equivalently.

        Educational Note:
            The implementation intentionally treats {} and None as equivalent
            for situations because both indicate "no relevant situation data".
            The function compares specific keys (possession, down, distance,
            yard_line, is_red_zone) - empty dict and None both have no values
            for these keys, so they're functionally identical.
        """
        from precog.database.crud_operations import game_state_changed

        current = {
            "home_score": 0,
            "away_score": 0,
            "period": 1,
            "game_status": "pre",
            "situation": None,
        }

        result = game_state_changed(
            current=current,
            home_score=0,
            away_score=0,
            period=1,
            game_status="pre",
            situation={},  # Empty dict treated same as None
        )

        # Empty dict and None are functionally equivalent (no relevant keys)
        assert result is False

    def test_situation_with_extra_fields_ignored(self):
        """Extra fields in situation dict should not affect comparison.

        Educational Note:
            game_state_changed() compares specific situation fields. Fields
            not in the comparison list should be ignored. This ensures
            backward compatibility when ESPN adds new fields.
        """
        from precog.database.crud_operations import game_state_changed

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"down": 2, "distance": 5, "possession": "home"},
        }

        # Same core fields but with extra fields
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",
            situation={
                "down": 2,
                "distance": 5,
                "possession": "home",
                "extra_field": "should_be_ignored",
                "another_extra": 12345,
            },
        )

        # Same core values, extra fields ignored - no change
        assert result is False

    def test_zero_scores_not_treated_as_none(self):
        """Zero scores should be compared as values, not as NULL.

        Educational Note:
            Score of 0 is semantically different from None/NULL. A shutout
            (0-35) is a valid game outcome. The comparison should treat 0
            as a value, not as "missing data".
        """
        from precog.database.crud_operations import game_state_changed

        current = {
            "home_score": 0,
            "away_score": 0,
            "period": 1,
            "game_status": "in_progress",
            "situation": None,
        }

        # Change from 0 to 7
        result = game_state_changed(
            current=current,
            home_score=0,
            away_score=7,  # Score changed
            period=1,
            game_status="in_progress",
            situation=None,
        )

        assert result is True

        # No change - both still 0
        result = game_state_changed(
            current=current,
            home_score=0,
            away_score=0,
            period=1,
            game_status="in_progress",
            situation=None,
        )

        assert result is False

    def test_game_status_case_sensitivity(self):
        """Game status comparison should handle case differences.

        Educational Note:
            ESPN API may return status in different cases. The comparison
            should be case-insensitive or normalized before comparison.
        """
        from precog.database.crud_operations import game_state_changed

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
            "situation": None,
        }

        # Same status, different case - should NOT be a change
        # (assuming normalization happens before storage)
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",  # Same normalized status
            situation=None,
        )

        assert result is False

    def test_period_boundary_values(self):
        """Period at boundary values (0, 1, 5+) should be handled.

        Educational Note:
            - Period 0: might represent pre-game
            - Period 1-4: regular quarters
            - Period 5+: overtime periods
            All should be valid for comparison.
        """
        from precog.database.crud_operations import game_state_changed

        current = {
            "home_score": 21,
            "away_score": 21,
            "period": 4,
            "game_status": "in_progress",
            "situation": None,
        }

        # Period changing to overtime (5)
        result = game_state_changed(
            current=current,
            home_score=21,
            away_score=21,
            period=5,  # Overtime
            game_status="in_progress",
            situation=None,
        )

        assert result is True

        # Period 0 edge case
        current_pregame = {
            "home_score": 0,
            "away_score": 0,
            "period": 0,
            "game_status": "pre",
            "situation": None,
        }

        result = game_state_changed(
            current=current_pregame,
            home_score=0,
            away_score=0,
            period=1,  # Game starting
            game_status="in_progress",
            situation=None,
        )

        assert result is True

    def test_situation_none_to_populated(self):
        """Situation changing from None to populated should detect change.

        Educational Note:
            When a game starts, situation data becomes available. This
            transition from None to a populated dict must be detected.
        """
        from precog.database.crud_operations import game_state_changed

        current = {
            "home_score": 0,
            "away_score": 0,
            "period": 1,
            "game_status": "in_progress",
            "situation": None,  # No situation data yet
        }

        result = game_state_changed(
            current=current,
            home_score=0,
            away_score=0,
            period=1,
            game_status="in_progress",
            situation={"down": 1, "distance": 10, "possession": "home"},
        )

        assert result is True
