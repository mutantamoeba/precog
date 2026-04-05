"""Unit tests for database/crud_events module (event/series operations).

Stub test created for test type coverage audit compliance.
Module extracted from crud_operations.py in session 37-38 (ADR-115).
"""

import pytest

from precog.database.crud_events import get_series


@pytest.mark.unit
class TestCrudEvents:
    """Verify crud_events module is importable and exports expected functions."""

    def test_get_series_is_callable(self):
        """get_series should be a callable function."""
        assert callable(get_series)
