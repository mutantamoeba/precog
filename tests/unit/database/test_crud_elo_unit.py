"""Unit tests for crud_elo module — minimum viable coverage to satisfy
audit_test_type_coverage.py 'experimental' tier requirement (1 unit test).

Filed as part of #1019 SKIP_TEST_TYPE_AUDIT bypass retirement (session 73 user
directive: "prioritize adding the missing tests so we can retire this skip").

Covers:
    - get_team_elo_rating: happy path (rating found), None (team not found),
      None (team found but rating is NULL).
    - get_team_elo_by_code: happy path with league filter, None when no match,
      ambiguous lookup warning when multiple rows match without league filter.

Out of scope (deferred):
    - update_team_elo_rating, update_team_classification, insert_elo_calculation_log,
      get_elo_calculation_logs — write paths and audit log functions. Cohort 2-style
      Pattern 14 5-step bundle would extend coverage; this PR ships the minimum to
      retire the audit bypass for this module.

Pattern 43 (mock fidelity): mocks of fetch_one / fetch_all return the EXACT shape
the real query returns (RealDictCursor dicts with the SELECT-projection keys, no
extras).

Reference:
    - src/precog/database/crud_elo.py
    - #1019 (SKIP_TEST_TYPE_AUDIT retirement priority)
    - feedback_test_audit_skip_retirement_priority.md
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from precog.database.crud_elo import get_team_elo_by_code, get_team_elo_rating

# =============================================================================
# get_team_elo_rating
# =============================================================================


@pytest.mark.unit
class TestGetTeamEloRating:
    """Unit tests for get_team_elo_rating — SELECT current_elo_rating by team_id."""

    @patch("precog.database.crud_elo.fetch_one")
    def test_returns_decimal_when_rating_found(self, mock_fetch_one):
        """Happy path: team found with non-NULL rating returns Decimal."""
        mock_fetch_one.return_value = {"current_elo_rating": "1523.4500"}

        result = get_team_elo_rating(team_id=42)

        assert result == Decimal("1523.4500")
        assert isinstance(result, Decimal)
        # Verify SQL queries the right column + filter
        sql = mock_fetch_one.call_args[0][0]
        assert "current_elo_rating" in sql
        assert "team_id = %s" in sql
        assert mock_fetch_one.call_args[0][1] == (42,)

    @patch("precog.database.crud_elo.fetch_one")
    def test_returns_none_when_team_not_found(self, mock_fetch_one):
        """fetch_one returns None when team_id has no row → function returns None."""
        mock_fetch_one.return_value = None

        result = get_team_elo_rating(team_id=99999)

        assert result is None

    @patch("precog.database.crud_elo.fetch_one")
    def test_returns_none_when_rating_is_null(self, mock_fetch_one):
        """Team found but current_elo_rating is NULL → function returns None.
        Pattern 45 None-preserving: don't conflate 'team has no rating' with 0.
        """
        mock_fetch_one.return_value = {"current_elo_rating": None}

        result = get_team_elo_rating(team_id=42)

        assert result is None

    @patch("precog.database.crud_elo.fetch_one")
    def test_returns_zero_decimal_when_rating_is_zero(self, mock_fetch_one):
        """Elo rating of 0 should return Decimal('0'), not None.

        Pattern 45 (None-preserving sanitization): falsy 0 must not be
        conflated with missing rating. Pinned via #1027.

        Pattern 43 (mock fidelity): RealDictCursor returns native Decimal
        objects for DECIMAL columns, so the mock returns Decimal('0') here.
        Decimal('0') is falsy in Python — that is what the buggy guard
        `if result and result.get("current_elo_rating"):` conflates with
        "missing rating".
        """
        mock_fetch_one.return_value = {"current_elo_rating": Decimal("0.0000")}

        result = get_team_elo_rating(team_id=42)

        assert result == Decimal("0")  # NOT None
        assert isinstance(result, Decimal)


# =============================================================================
# get_team_elo_by_code
# =============================================================================


@pytest.mark.unit
class TestGetTeamEloByCode:
    """Unit tests for get_team_elo_by_code — SELECT current_elo_rating by code+league."""

    @patch("precog.database.crud_elo.fetch_all")
    def test_returns_decimal_with_league_filter(self, mock_fetch_all):
        """Happy path: code + league lookup returns single row's Decimal rating."""
        mock_fetch_all.return_value = [{"current_elo_rating": "1610.7500"}]

        result = get_team_elo_by_code("KC", league="nfl")

        assert result == Decimal("1610.7500")
        # Verify SQL includes both filters
        sql = mock_fetch_all.call_args[0][0]
        assert "team_code = %s" in sql
        assert "league = %s" in sql
        assert mock_fetch_all.call_args[0][1] == ("KC", "nfl")

    @patch("precog.database.crud_elo.fetch_all")
    def test_returns_none_when_no_match(self, mock_fetch_all):
        """Empty result list → returns None."""
        mock_fetch_all.return_value = []

        result = get_team_elo_by_code("XXX", league="nfl")

        assert result is None

    @patch("precog.database.crud_elo.fetch_all")
    def test_ambiguous_lookup_logs_warning_and_returns_first(self, mock_fetch_all, caplog):
        """Multiple rows without league filter → warning logged + first result returned.
        Pattern 33 (cross-module): same team_code can collide across leagues
        (e.g., 'ATL' in NFL and MLS).
        """
        import logging

        mock_fetch_all.return_value = [
            {"current_elo_rating": "1500.0000"},
            {"current_elo_rating": "1450.0000"},
        ]

        with caplog.at_level(logging.WARNING, logger="precog.database.crud_elo"):
            result = get_team_elo_by_code("ATL")  # no league filter

        assert result == Decimal("1500.0000")  # first result
        assert any("Ambiguous team_code lookup" in rec.message for rec in caplog.records)

    @patch("precog.database.crud_elo.fetch_all")
    def test_returns_zero_decimal_when_rating_is_zero(self, mock_fetch_all):
        """Elo rating of 0 should return Decimal('0'), not None.

        Pattern 45 (None-preserving sanitization): falsy 0 must not be
        conflated with missing rating. Pinned via #1027.

        Pattern 43 (mock fidelity): RealDictCursor returns native Decimal
        objects for DECIMAL columns, so the mock returns Decimal('0') here.
        Decimal('0') is falsy in Python — that is what the buggy guard
        `if result and result.get("current_elo_rating"):` conflates with
        "missing rating".
        """
        mock_fetch_all.return_value = [{"current_elo_rating": Decimal("0.0000")}]

        result = get_team_elo_by_code("KC", league="nfl")

        assert result == Decimal("0")  # NOT None
        assert isinstance(result, Decimal)
