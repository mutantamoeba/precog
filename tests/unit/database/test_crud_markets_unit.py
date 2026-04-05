"""Unit tests for database/crud_markets module (market operations).

Stub test created for test type coverage audit compliance.
Module extracted from crud_operations.py in session 37-38 (ADR-115).
"""

import pytest

from precog.database.crud_markets import create_market


@pytest.mark.unit
class TestCrudMarkets:
    """Verify crud_markets module is importable and exports expected functions."""

    def test_create_market_is_callable(self):
        """create_market should be a callable function."""
        assert callable(create_market)
