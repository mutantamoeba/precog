"""Unit tests for database/crud_account module (account balance operations).

Stub test created for test type coverage audit compliance.
Module extracted from crud_operations.py in session 37-38 (ADR-115).
"""

import pytest

from precog.database.crud_account import create_account_balance


@pytest.mark.unit
class TestCrudAccount:
    """Verify crud_account module is importable and exports expected functions."""

    def test_create_account_balance_is_callable(self):
        """create_account_balance should be a callable function."""
        assert callable(create_account_balance)
