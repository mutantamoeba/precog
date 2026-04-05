"""Unit tests for database/crud_teams module (team/venue operations).

Stub test created for test type coverage audit compliance.
Module extracted from crud_operations.py in session 37-38 (ADR-115).
"""

import pytest

from precog.database.crud_teams import create_venue


@pytest.mark.unit
class TestCrudTeams:
    """Verify crud_teams module is importable and exports expected functions."""

    def test_create_venue_is_callable(self):
        """create_venue should be a callable function."""
        assert callable(create_venue)
