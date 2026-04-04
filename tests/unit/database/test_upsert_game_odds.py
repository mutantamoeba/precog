"""
Unit Tests for upsert_game_odds CRUD function.

Tests the SCD Type 2 upsert logic for game_odds records, verifying:
- New row creation when no current row exists
- SCD versioning when tracked values change
- No new version when values are unchanged (just updated_at bump)
- Correct change detection field comparison

These tests mock the database cursor to verify SQL logic without
requiring a live database connection.

Related:
    - Issue #533: ESPN DraftKings odds extraction
    - Migration 0048: game_odds table with SCD Type 2
    - crud_operations.py: upsert_game_odds()

Usage:
    pytest tests/unit/database/test_upsert_game_odds.py -v
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_cursor():
    """Create a mock database cursor with standard behavior."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    cursor.rowcount = 1
    return cursor


@pytest.fixture
def mock_get_cursor(mock_cursor):
    """Patch get_cursor to return mock cursor."""
    with patch("precog.database.crud_game_states.get_cursor") as mock_gc:
        # Context manager returns cursor
        mock_gc.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_gc, mock_cursor


# =============================================================================
# New Row Creation Tests
# =============================================================================


class TestUpsertGameOddsNewRow:
    """Test creating a new game_odds row when none exists."""

    def test_creates_new_row_when_no_current(self, mock_get_cursor) -> None:
        """When no current row exists, INSERT a new one."""
        from precog.database.crud_operations import upsert_game_odds

        _, mock_cursor = mock_get_cursor

        # First query (SELECT current) returns None (no existing row)
        # Second query (INSERT) returns new id
        mock_cursor.fetchone.side_effect = [
            None,  # SELECT current row
            {"id": 42},  # INSERT RETURNING id
        ]

        result = upsert_game_odds(
            game_id=1,
            sport="basketball",
            sportsbook="draftkings",
            spread_home_close=Decimal("3.5"),
            moneyline_home_close=-155,
            moneyline_away_close=130,
            total_close=Decimal("224.5"),
            source="espn_poller",
        )

        assert result == 42
        # Should have been called twice: SELECT then INSERT
        assert mock_cursor.execute.call_count == 2

    def test_passes_all_fields_to_insert(self, mock_get_cursor) -> None:
        """All fields are passed through to the INSERT statement."""
        from precog.database.crud_operations import upsert_game_odds

        _, mock_cursor = mock_get_cursor
        mock_cursor.fetchone.side_effect = [None, {"id": 1}]

        from datetime import date

        upsert_game_odds(
            game_id=10,
            sport="football",
            sportsbook="draftkings",
            game_date=date(2026, 1, 15),
            home_team_code="KC",
            away_team_code="BUF",
            spread_home_open=Decimal("-3.5"),
            spread_home_close=Decimal("-3.0"),
            spread_home_odds_open=-110,
            spread_home_odds_close=-112,
            spread_away_odds_open=-110,
            spread_away_odds_close=-108,
            moneyline_home_open=-150,
            moneyline_home_close=-155,
            moneyline_away_open=125,
            moneyline_away_close=130,
            total_open=Decimal("47.5"),
            total_close=Decimal("48.0"),
            over_odds_open=-110,
            over_odds_close=-115,
            under_odds_open=-110,
            under_odds_close=-105,
            home_favorite=True,
            away_favorite=False,
            home_favorite_at_open=True,
            away_favorite_at_open=False,
            details_text="KC -3.0",
            source="espn_poller",
        )

        # Verify the INSERT was called with all values
        insert_call = mock_cursor.execute.call_args_list[1]
        params = insert_call[0][1]
        assert params[0] == 10  # game_id
        assert params[1] == "football"  # sport
        assert params[5] == "draftkings"  # sportsbook
        assert params[6] == "espn_poller"  # source


# =============================================================================
# SCD Versioning Tests
# =============================================================================


class TestUpsertGameOddsSCDVersioning:
    """Test SCD Type 2 versioning behavior."""

    def test_creates_new_version_when_spread_changes(self, mock_get_cursor) -> None:
        """When spread_home_close changes, close current and insert new."""
        from precog.database.crud_operations import upsert_game_odds

        _, mock_cursor = mock_get_cursor

        # Current row has spread_home_close = 3.5
        mock_cursor.fetchone.side_effect = [
            {
                "id": 100,
                "spread_home_close": Decimal("3.5"),
                "moneyline_home_close": -155,
                "moneyline_away_close": 130,
                "total_close": Decimal("224.5"),
            },
            {"id": 101},  # New row id from INSERT
        ]

        result = upsert_game_odds(
            game_id=1,
            sport="basketball",
            sportsbook="draftkings",
            spread_home_close=Decimal("4.0"),  # Changed from 3.5 to 4.0
            moneyline_home_close=-155,
            moneyline_away_close=130,
            total_close=Decimal("224.5"),
        )

        assert result == 101
        # Should be 3 calls: SELECT, UPDATE (close), INSERT (new)
        assert mock_cursor.execute.call_count == 3

        # Verify the UPDATE closed the old row
        close_call = mock_cursor.execute.call_args_list[1]
        close_sql = close_call[0][0]
        assert "row_current_ind = FALSE" in close_sql
        assert "row_end_ts = NOW()" in close_sql

    def test_creates_new_version_when_moneyline_changes(self, mock_get_cursor) -> None:
        """When moneyline_home_close changes, create new version."""
        from precog.database.crud_operations import upsert_game_odds

        _, mock_cursor = mock_get_cursor

        mock_cursor.fetchone.side_effect = [
            {
                "id": 100,
                "spread_home_close": Decimal("3.5"),
                "moneyline_home_close": -155,
                "moneyline_away_close": 130,
                "total_close": Decimal("224.5"),
            },
            {"id": 102},
        ]

        result = upsert_game_odds(
            game_id=1,
            sport="basketball",
            sportsbook="draftkings",
            spread_home_close=Decimal("3.5"),  # Same
            moneyline_home_close=-160,  # Changed from -155 to -160
            moneyline_away_close=130,  # Same
            total_close=Decimal("224.5"),  # Same
        )

        assert result == 102
        assert mock_cursor.execute.call_count == 3  # SELECT + UPDATE + INSERT

    def test_creates_new_version_when_total_changes(self, mock_get_cursor) -> None:
        """When total_close changes, create new version."""
        from precog.database.crud_operations import upsert_game_odds

        _, mock_cursor = mock_get_cursor

        mock_cursor.fetchone.side_effect = [
            {
                "id": 100,
                "spread_home_close": Decimal("3.5"),
                "moneyline_home_close": -155,
                "moneyline_away_close": 130,
                "total_close": Decimal("224.5"),
            },
            {"id": 103},
        ]

        result = upsert_game_odds(
            game_id=1,
            sport="basketball",
            sportsbook="draftkings",
            spread_home_close=Decimal("3.5"),
            moneyline_home_close=-155,
            moneyline_away_close=130,
            total_close=Decimal("225.0"),  # Changed from 224.5 to 225.0
        )

        assert result == 103
        assert mock_cursor.execute.call_count == 3

    def test_no_new_version_when_unchanged(self, mock_get_cursor) -> None:
        """When all tracked values are the same, just update updated_at."""
        from precog.database.crud_operations import upsert_game_odds

        _, mock_cursor = mock_get_cursor

        mock_cursor.fetchone.side_effect = [
            {
                "id": 100,
                "spread_home_close": Decimal("3.5"),
                "moneyline_home_close": -155,
                "moneyline_away_close": 130,
                "total_close": Decimal("224.5"),
            },
        ]

        result = upsert_game_odds(
            game_id=1,
            sport="basketball",
            sportsbook="draftkings",
            spread_home_close=Decimal("3.5"),  # Same
            moneyline_home_close=-155,  # Same
            moneyline_away_close=130,  # Same
            total_close=Decimal("224.5"),  # Same
        )

        # Should return existing row id
        assert result == 100
        # Only 2 calls: SELECT + UPDATE updated_at (no INSERT)
        assert mock_cursor.execute.call_count == 2

        # Verify the update was just for updated_at
        update_call = mock_cursor.execute.call_args_list[1]
        update_sql = update_call[0][0]
        assert "updated_at = NOW()" in update_sql
        assert "row_current_ind" not in update_sql

    def test_none_vs_none_is_unchanged(self, mock_get_cursor) -> None:
        """When both DB and new values are None, that's unchanged."""
        from precog.database.crud_operations import upsert_game_odds

        _, mock_cursor = mock_get_cursor

        mock_cursor.fetchone.side_effect = [
            {
                "id": 100,
                "spread_home_close": None,
                "moneyline_home_close": None,
                "moneyline_away_close": None,
                "total_close": None,
            },
        ]

        result = upsert_game_odds(
            game_id=1,
            sport="basketball",
            sportsbook="draftkings",
            spread_home_close=None,
            moneyline_home_close=None,
            moneyline_away_close=None,
            total_close=None,
        )

        assert result == 100
        assert mock_cursor.execute.call_count == 2  # SELECT + UPDATE updated_at

    def test_none_to_value_is_changed(self, mock_get_cursor) -> None:
        """When DB has None and new value is set, that's a change."""
        from precog.database.crud_operations import upsert_game_odds

        _, mock_cursor = mock_get_cursor

        mock_cursor.fetchone.side_effect = [
            {
                "id": 100,
                "spread_home_close": None,
                "moneyline_home_close": None,
                "moneyline_away_close": None,
                "total_close": None,
            },
            {"id": 104},
        ]

        result = upsert_game_odds(
            game_id=1,
            sport="basketball",
            sportsbook="draftkings",
            spread_home_close=Decimal("3.5"),  # Was None, now has value
            moneyline_home_close=None,
            moneyline_away_close=None,
            total_close=None,
        )

        assert result == 104
        assert mock_cursor.execute.call_count == 3  # SELECT + UPDATE + INSERT

    def test_value_to_none_is_changed(self, mock_get_cursor) -> None:
        """When DB has a value and new is None, that's a change."""
        from precog.database.crud_operations import upsert_game_odds

        _, mock_cursor = mock_get_cursor

        mock_cursor.fetchone.side_effect = [
            {
                "id": 100,
                "spread_home_close": Decimal("3.5"),
                "moneyline_home_close": -155,
                "moneyline_away_close": 130,
                "total_close": Decimal("224.5"),
            },
            {"id": 105},
        ]

        result = upsert_game_odds(
            game_id=1,
            sport="basketball",
            sportsbook="draftkings",
            spread_home_close=None,  # Was 3.5, now None
            moneyline_home_close=-155,
            moneyline_away_close=130,
            total_close=Decimal("224.5"),
        )

        assert result == 105
        assert mock_cursor.execute.call_count == 3
