"""
Unit Tests for External Team Codes CRUD Operations (Migration 0045).

Tests the CRUD lifecycle for external_team_codes: create, get (with filters),
find_by_external_code (JOIN lookup), upsert (insert + update), and delete.

All tests use mock DB cursors matching existing test patterns in this project.

Related:
    - Migration 0045: CREATE TABLE external_team_codes
    - Issue #516: External team codes table
    - crud_operations.py: Implementation

Usage:
    pytest tests/unit/database/test_external_team_codes_crud.py -v
    pytest tests/unit/database/test_external_team_codes_crud.py -v -m unit
"""

from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_teams import (
    create_external_team_code,
    delete_external_team_code,
    find_team_by_external_code,
    get_external_team_codes,
    upsert_external_team_code,
)

# =============================================================================
# HELPERS
# =============================================================================


def _mock_cursor_context(mock_get_cursor, mock_cursor=None):
    """Set up mock_get_cursor to return a context manager yielding mock_cursor."""
    if mock_cursor is None:
        mock_cursor = MagicMock()
    mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


# =============================================================================
# CREATE TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateExternalTeamCode:
    """Unit tests for create_external_team_code."""

    @patch("precog.database.crud_teams.get_cursor")
    def test_create_returns_id(self, mock_get_cursor):
        """Creating a new code returns the SERIAL PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = create_external_team_code(
            team_id=42,
            source="kalshi",
            source_team_code="JAC",
            league="nfl",
            confidence="manual",
            notes="Kalshi uses JAC for Jacksonville",
        )

        assert result == 1
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO external_team_codes" in sql
        assert "RETURNING id" in sql

    @patch("precog.database.crud_teams.get_cursor")
    def test_create_with_defaults(self, mock_get_cursor):
        """Creating with only required params uses default confidence='heuristic'."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 5}

        result = create_external_team_code(
            team_id=10,
            source="espn",
            source_team_code="HOU",
            league="nfl",
        )

        assert result == 5
        # Verify params passed include default confidence
        params = mock_cursor.execute.call_args[0][1]
        assert params[0] == 10  # team_id
        assert params[1] == "espn"  # source
        assert params[2] == "HOU"  # source_team_code
        assert params[3] == "nfl"  # league
        assert params[4] == "heuristic"  # default confidence
        assert params[5] is None  # verified_at
        assert params[6] is None  # notes

    @patch("precog.database.crud_teams.get_cursor")
    def test_create_with_verified_at(self, mock_get_cursor):
        """Creating with a verified_at timestamp passes it through."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 7}

        create_external_team_code(
            team_id=42,
            source="kalshi",
            source_team_code="JAC",
            league="nfl",
            confidence="exact",
            verified_at="2026-03-29T12:00:00Z",
        )

        params = mock_cursor.execute.call_args[0][1]
        assert params[4] == "exact"
        assert params[5] == "2026-03-29T12:00:00Z"


# =============================================================================
# GET (WITH FILTERS) TESTS
# =============================================================================


@pytest.mark.unit
class TestGetExternalTeamCodes:
    """Unit tests for get_external_team_codes."""

    @patch("precog.database.crud_teams.fetch_all")
    def test_get_all_no_filters(self, mock_fetch_all):
        """Getting all codes with no filters returns everything."""
        mock_fetch_all.return_value = [
            {"id": 1, "source": "kalshi", "source_team_code": "JAC", "league": "nfl"},
            {"id": 2, "source": "espn", "source_team_code": "JAX", "league": "nfl"},
        ]

        result = get_external_team_codes()

        assert len(result) == 2
        sql = mock_fetch_all.call_args[0][0]
        assert "WHERE" not in sql

    @patch("precog.database.crud_teams.fetch_all")
    def test_get_filtered_by_source(self, mock_fetch_all):
        """Filtering by source adds WHERE clause."""
        mock_fetch_all.return_value = [
            {"id": 1, "source": "kalshi", "source_team_code": "JAC", "league": "nfl"},
        ]

        get_external_team_codes(source="kalshi")

        sql = mock_fetch_all.call_args[0][0]
        assert "WHERE" in sql
        assert "source = %s" in sql
        params = mock_fetch_all.call_args[0][1]
        assert params == ("kalshi",)

    @patch("precog.database.crud_teams.fetch_all")
    def test_get_filtered_by_league(self, mock_fetch_all):
        """Filtering by league adds WHERE clause."""
        mock_fetch_all.return_value = []

        get_external_team_codes(league="nba")

        sql = mock_fetch_all.call_args[0][0]
        assert "league = %s" in sql
        params = mock_fetch_all.call_args[0][1]
        assert params == ("nba",)

    @patch("precog.database.crud_teams.fetch_all")
    def test_get_filtered_by_team_id(self, mock_fetch_all):
        """Filtering by team_id adds WHERE clause."""
        mock_fetch_all.return_value = []

        get_external_team_codes(team_id=42)

        sql = mock_fetch_all.call_args[0][0]
        assert "team_id = %s" in sql
        params = mock_fetch_all.call_args[0][1]
        assert params == (42,)

    @patch("precog.database.crud_teams.fetch_all")
    def test_get_multiple_filters(self, mock_fetch_all):
        """Multiple filters are combined with AND."""
        mock_fetch_all.return_value = []

        get_external_team_codes(source="kalshi", league="nfl", team_id=42)

        sql = mock_fetch_all.call_args[0][0]
        assert "source = %s" in sql
        assert "league = %s" in sql
        assert "team_id = %s" in sql
        assert "AND" in sql
        params = mock_fetch_all.call_args[0][1]
        assert params == ("kalshi", "nfl", 42)

    @patch("precog.database.crud_teams.fetch_all")
    def test_get_empty_result(self, mock_fetch_all):
        """No matching codes returns empty list."""
        mock_fetch_all.return_value = []

        result = get_external_team_codes(source="polymarket")

        assert result == []


# =============================================================================
# FIND BY EXTERNAL CODE (JOIN LOOKUP) TESTS
# =============================================================================


@pytest.mark.unit
class TestFindTeamByExternalCode:
    """Unit tests for find_team_by_external_code."""

    @patch("precog.database.crud_teams.fetch_one")
    def test_find_returns_team_with_confidence(self, mock_fetch_one):
        """Finding a team returns the full team row plus confidence."""
        mock_fetch_one.return_value = {
            "team_id": 42,
            "team_code": "JAX",
            "team_name": "Jacksonville Jaguars",
            "league": "nfl",
            "confidence": "manual",
            "external_code": "JAC",
        }

        result = find_team_by_external_code("kalshi", "JAC", "nfl")

        assert result is not None
        assert result["team_code"] == "JAX"
        assert result["confidence"] == "manual"
        assert result["external_code"] == "JAC"

    @patch("precog.database.crud_teams.fetch_one")
    def test_find_nonexistent_returns_none(self, mock_fetch_one):
        """Looking up a code that doesn't exist returns None."""
        mock_fetch_one.return_value = None

        result = find_team_by_external_code("kalshi", "ZZZ", "nfl")

        assert result is None

    @patch("precog.database.crud_teams.fetch_one")
    def test_find_uses_join_query(self, mock_fetch_one):
        """The query JOINs external_team_codes with teams."""
        mock_fetch_one.return_value = None

        find_team_by_external_code("kalshi", "JAC", "nfl")

        sql = mock_fetch_one.call_args[0][0]
        assert "JOIN teams" in sql
        assert "external_team_codes" in sql
        params = mock_fetch_one.call_args[0][1]
        assert params == ("kalshi", "JAC", "nfl")


# =============================================================================
# UPSERT TESTS
# =============================================================================


@pytest.mark.unit
class TestUpsertExternalTeamCode:
    """Unit tests for upsert_external_team_code."""

    @patch("precog.database.crud_teams.get_cursor")
    def test_upsert_returns_id(self, mock_get_cursor):
        """Upsert returns the row id (new or existing)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = upsert_external_team_code(
            team_id=42,
            source="kalshi",
            source_team_code="JAC",
            league="nfl",
            confidence="manual",
        )

        assert result == 1

    @patch("precog.database.crud_teams.get_cursor")
    def test_upsert_uses_on_conflict(self, mock_get_cursor):
        """Upsert SQL uses ON CONFLICT for idempotency."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        upsert_external_team_code(
            team_id=42,
            source="kalshi",
            source_team_code="JAC",
            league="nfl",
        )

        sql = mock_cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql
        assert "source, source_team_code, league" in sql
        assert "DO UPDATE SET" in sql
        assert "updated_at = NOW()" in sql

    @patch("precog.database.crud_teams.get_cursor")
    def test_upsert_updates_team_id_on_conflict(self, mock_get_cursor):
        """On conflict, team_id is updated (handles reassignment)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        upsert_external_team_code(
            team_id=99,
            source="kalshi",
            source_team_code="JAC",
            league="nfl",
            confidence="exact",
        )

        sql = mock_cursor.execute.call_args[0][0]
        assert "team_id = EXCLUDED.team_id" in sql
        assert "confidence = EXCLUDED.confidence" in sql

    @patch("precog.database.crud_teams.get_cursor")
    def test_upsert_with_notes(self, mock_get_cursor):
        """Notes are passed through to the upsert."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 3}

        upsert_external_team_code(
            team_id=42,
            source="kalshi",
            source_team_code="JAC",
            league="nfl",
            notes="Verified manually",
        )

        params = mock_cursor.execute.call_args[0][1]
        assert "Verified manually" in params


# =============================================================================
# DELETE TESTS
# =============================================================================


@pytest.mark.unit
class TestDeleteExternalTeamCode:
    """Unit tests for delete_external_team_code."""

    @patch("precog.database.crud_teams.get_cursor")
    def test_delete_existing_returns_true(self, mock_get_cursor):
        """Deleting an existing row returns True."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        result = delete_external_team_code(42)

        assert result is True
        sql = mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM external_team_codes" in sql
        assert "WHERE id = %s" in sql

    @patch("precog.database.crud_teams.get_cursor")
    def test_delete_nonexistent_returns_false(self, mock_get_cursor):
        """Deleting a non-existent row returns False."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0

        result = delete_external_team_code(999)

        assert result is False
