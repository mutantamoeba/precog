"""Shared helpers for canonical_* CRUD unit-test modules.

Pattern 73 SSOT — extracted from the slot-0074 review (#1095 close-out
bundle, claude-review minor finding #2): two unit-test modules
(``test_crud_canonical_match_overrides_unit.py`` +
``test_crud_canonical_match_reviews_unit.py``) had byte-identical
``_wire_get_cursor_mock`` definitions.  Centralized here so a future
refinement (richer mock shape, additional fixture state, etc.) lands in
one place rather than drifting across sibling test modules.

Filename has the leading-underscore "internal-to-tests" convention
(``_crud_unit_helpers.py``) — pytest collects only files matching
``test_*.py`` by default, so this module is purely a sibling import
target and not itself a test file.

The same shape was extracted at the integration-test layer one slot
earlier via PR #1092 (closes #1089).  This file is the parallel
extraction at the unit-test layer.
"""

from __future__ import annotations

from unittest.mock import MagicMock


def wire_get_cursor_mock(mock_get_cursor_factory: MagicMock, returning_id: int = 99) -> MagicMock:
    """Wire a @patch-supplied ``get_cursor`` mock so it acts as a context manager.

    Returns the inner ``mock_cursor`` that the SUT sees as the yielded
    cursor object.  Pattern 43 fidelity: ``fetchone()`` returns a
    RealDictCursor-style dict (``{"id": <int>}``) matching the real
    INSERT ... RETURNING id shape.

    Public function name (no leading underscore) so sibling test modules
    can import without triggering ``private-name-import`` linter
    complaints.  The leading underscore is on the FILENAME (which marks
    the module as internal-to-tests) rather than each callable.

    Args:
        mock_get_cursor_factory: The ``MagicMock`` returned by
            ``@patch("...get_cursor")`` — the SUT's ``get_cursor()`` call
            site is patched at this object.
        returning_id: The integer the mock cursor's ``fetchone()`` will
            yield as ``{"id": <returning_id>}``.  Defaults to 99 to make
            test-vs-real-id collisions unlikely.

    Returns:
        The inner ``mock_cursor`` that the SUT receives as the yielded
        cursor object.  Tests assert against ``mock_cursor.execute`` /
        ``mock_cursor.fetchone`` to verify SQL shape + result handling.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"id": returning_id}
    mock_get_cursor_factory.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_cursor_factory.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor
