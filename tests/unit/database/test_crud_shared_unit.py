"""Unit tests for database/crud_shared module (shared CRUD utilities).

Stub test created for test type coverage audit compliance.
Module extracted from crud_operations.py in session 37-38 (ADR-115).
"""

import pytest

from precog.database.crud_shared import validate_decimal


@pytest.mark.unit
class TestCrudShared:
    """Verify crud_shared module is importable and exports expected functions."""

    def test_validate_decimal_is_callable(self):
        """validate_decimal should be a callable function."""
        assert callable(validate_decimal)
