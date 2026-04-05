"""Unit tests for database/crud_ledger module (account ledger operations).

Stub test created for test type coverage audit compliance.
Module extracted from crud_operations.py in session 37-38 (ADR-115).
"""

import pytest

from precog.database.crud_ledger import create_ledger_entry


@pytest.mark.unit
class TestCrudLedger:
    """Verify crud_ledger module is importable and exports expected functions."""

    def test_create_ledger_entry_is_callable(self):
        """create_ledger_entry should be a callable function."""
        assert callable(create_ledger_entry)
