"""Unit tests for crud_canonical_event_links module — Pattern 14 step 4 of the
Cohort 3 slot-0072 bundle.

Parallel test module to ``test_crud_canonical_market_links_unit.py`` per
L12-L13 (parallelism IS the contract).  Same coverage shape, same
fidelity discipline; only column names + table name + FK target differ.

Covers (function-by-function):
    - get_active_link_for_platform_event: happy path, None.
    - get_link_by_id: happy path, None.
    - list_links_for_canonical_event: multiple rows, empty list, ORDER BY shape.
    - retire_link: True + retire_reason, False, retire_reason=None passthrough,
      does NOT write updated_at directly.

Pattern 43 (mock fidelity) discipline: mocks return the EXACT shape that
the real query returns — full row dicts with all 12 canonical_event_links
columns.

Reference:
    - ``src/precog/database/crud_canonical_event_links.py``
    - ``src/precog/database/alembic/versions/0072_canonical_link_tables.py``
    - ``tests/unit/database/test_crud_canonical_market_links_unit.py``
      (parallel test module — structural template)
    - ADR-118 v2.41 amendment Cohort 3 + S82 build spec § 8 step 4b
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_canonical_event_links import (
    get_active_link_for_platform_event,
    get_link_by_id,
    list_links_for_canonical_event,
    retire_link,
)


def _full_row_dict(
    *,
    id: int = 7,
    canonical_event_id: int = 42,
    platform_event_id: int = 100,
    link_state: str = "active",
    confidence: Decimal | None = None,
    algorithm_id: int = 1,
    decided_by: str = "system:test",
    decided_at: datetime | None = None,
    retired_at: datetime | None = None,
    retire_reason: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> dict:
    """Build a full canonical_event_links row dict matching the real query shape.

    Pattern 43 fidelity: every key the real RETURNING / SELECT projection
    emits is present, with no extras.
    """
    if confidence is None:
        confidence = Decimal("1.000")
    if decided_at is None:
        decided_at = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)
    if created_at is None:
        created_at = decided_at
    if updated_at is None:
        updated_at = decided_at
    return {
        "id": id,
        "canonical_event_id": canonical_event_id,
        "platform_event_id": platform_event_id,
        "link_state": link_state,
        "confidence": confidence,
        "algorithm_id": algorithm_id,
        "decided_by": decided_by,
        "decided_at": decided_at,
        "retired_at": retired_at,
        "retire_reason": retire_reason,
        "created_at": created_at,
        "updated_at": updated_at,
    }


_ALL_COLUMNS = (
    "id",
    "canonical_event_id",
    "platform_event_id",
    "link_state",
    "confidence",
    "algorithm_id",
    "decided_by",
    "decided_at",
    "retired_at",
    "retire_reason",
    "created_at",
    "updated_at",
)


# =============================================================================
# get_active_link_for_platform_event
# =============================================================================


@pytest.mark.unit
class TestGetActiveLinkForPlatformEvent:
    """Unit tests for get_active_link_for_platform_event — partial-active SELECT."""

    @patch("precog.database.crud_canonical_event_links.fetch_one")
    def test_returns_row_dict_when_active_link_exists(self, mock_fetch_one):
        """Returns the full row dict when an active link exists."""
        expected_row = _full_row_dict(platform_event_id=100, link_state="active")
        mock_fetch_one.return_value = expected_row

        result = get_active_link_for_platform_event(100)

        assert result == expected_row
        mock_fetch_one.assert_called_once()
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_event_links" in sql
        assert "WHERE platform_event_id = %s" in sql
        assert "link_state = 'active'" in sql
        assert params == (100,)

    @patch("precog.database.crud_canonical_event_links.fetch_one")
    def test_returns_none_when_no_active_link(self, mock_fetch_one):
        """Returns None when no active link exists for the platform event."""
        mock_fetch_one.return_value = None

        result = get_active_link_for_platform_event(99999)

        assert result is None
        params = mock_fetch_one.call_args[0][1]
        assert params == (99999,)

    @patch("precog.database.crud_canonical_event_links.fetch_one")
    def test_query_selects_all_canonical_event_links_columns(self, mock_fetch_one):
        """Pattern 43 fidelity: SELECT projection must include all 12 columns."""
        mock_fetch_one.return_value = None

        get_active_link_for_platform_event(100)

        sql = mock_fetch_one.call_args[0][0]
        for col in _ALL_COLUMNS:
            assert col in sql, f"Column {col!r} missing from SELECT projection"


# =============================================================================
# get_link_by_id
# =============================================================================


@pytest.mark.unit
class TestGetLinkById:
    """Unit tests for get_link_by_id — SELECT by surrogate PK."""

    @patch("precog.database.crud_canonical_event_links.fetch_one")
    def test_returns_row_dict_when_found(self, mock_fetch_one):
        """Returns the full row dict when a row matches the id."""
        expected_row = _full_row_dict(id=7)
        mock_fetch_one.return_value = expected_row

        result = get_link_by_id(7)

        assert result == expected_row
        mock_fetch_one.assert_called_once()
        sql, params = mock_fetch_one.call_args[0]
        assert "FROM canonical_event_links" in sql
        assert "WHERE id = %s" in sql
        assert params == (7,)

    @patch("precog.database.crud_canonical_event_links.fetch_one")
    def test_returns_none_when_not_found(self, mock_fetch_one):
        """Returns None when no row matches the id."""
        mock_fetch_one.return_value = None

        result = get_link_by_id(99999)

        assert result is None
        assert mock_fetch_one.call_count == 1
        assert mock_fetch_one.call_args[0][1] == (99999,)

    @patch("precog.database.crud_canonical_event_links.fetch_one")
    def test_query_selects_all_canonical_event_links_columns(self, mock_fetch_one):
        """Pattern 43 fidelity: SELECT projection must include all 12 columns."""
        mock_fetch_one.return_value = None

        get_link_by_id(7)

        sql = mock_fetch_one.call_args[0][0]
        for col in _ALL_COLUMNS:
            assert col in sql, f"Column {col!r} missing from SELECT projection"


# =============================================================================
# list_links_for_canonical_event
# =============================================================================


@pytest.mark.unit
class TestListLinksForCanonicalEvent:
    """Unit tests for list_links_for_canonical_event — fetch_all by FK."""

    @patch("precog.database.crud_canonical_event_links.fetch_all")
    def test_returns_list_when_links_exist(self, mock_fetch_all):
        """Returns a list of full row dicts when links exist for the canonical event."""
        active_row = _full_row_dict(id=7, link_state="active")
        retired_row = _full_row_dict(
            id=6,
            link_state="retired",
            retired_at=datetime(2026, 4, 25, 0, 0, 0, tzinfo=UTC),
            retire_reason="platform_delisted",
        )
        mock_fetch_all.return_value = [active_row, retired_row]

        result = list_links_for_canonical_event(42)

        assert result == [active_row, retired_row]
        sql, params = mock_fetch_all.call_args[0]
        assert "FROM canonical_event_links" in sql
        assert "WHERE canonical_event_id = %s" in sql
        # Per the docstring: ORDER BY decided_at DESC so most-recent first.
        assert "ORDER BY decided_at DESC" in sql
        assert params == (42,)

    @patch("precog.database.crud_canonical_event_links.fetch_all")
    def test_returns_empty_list_when_no_links(self, mock_fetch_all):
        """Returns an empty list when no links exist for the canonical event."""
        mock_fetch_all.return_value = []

        result = list_links_for_canonical_event(99999)

        assert result == []
        assert mock_fetch_all.call_args[0][1] == (99999,)

    @patch("precog.database.crud_canonical_event_links.fetch_all")
    def test_query_selects_all_canonical_event_links_columns(self, mock_fetch_all):
        """Pattern 43 fidelity: SELECT projection must include all 12 columns."""
        mock_fetch_all.return_value = []

        list_links_for_canonical_event(42)

        sql = mock_fetch_all.call_args[0][0]
        for col in _ALL_COLUMNS:
            assert col in sql, f"Column {col!r} missing from SELECT projection"


# =============================================================================
# retire_link
# =============================================================================


@pytest.mark.unit
class TestRetireLink:
    """Unit tests for retire_link — UPDATE link_state + retired_at + retire_reason."""

    @patch("precog.database.crud_canonical_event_links.get_cursor")
    def test_returns_true_when_row_updated(self, mock_get_cursor):
        """Returns True when a row was matched and updated (rowcount=1)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = retire_link(7, retire_reason="platform_delisted")

        assert result is True
        mock_get_cursor.assert_called_once_with(commit=True)
        sql, params = mock_cursor.execute.call_args[0]
        assert "UPDATE canonical_event_links" in sql
        assert "link_state = 'retired'" in sql
        assert "retired_at = now()" in sql
        assert "retire_reason = %s" in sql
        assert "WHERE id = %s" in sql
        assert params == ("platform_delisted", 7)

    @patch("precog.database.crud_canonical_event_links.get_cursor")
    def test_returns_false_when_no_row_matched(self, mock_get_cursor):
        """Returns False when no row matched the given id (rowcount=0)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = retire_link(99999, retire_reason="platform_delisted")

        assert result is False

    @patch("precog.database.crud_canonical_event_links.get_cursor")
    def test_retire_reason_none_passes_through_as_null(self, mock_get_cursor):
        """retire_reason=None is forwarded as NULL (not the string 'None')."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        retire_link(7)  # retire_reason omitted → None default

        params = mock_cursor.execute.call_args[0][1]
        assert params == (None, 7)

    @patch("precog.database.crud_canonical_event_links.get_cursor")
    def test_does_not_write_updated_at_directly(self, mock_get_cursor):
        """retire_link does NOT explicitly write updated_at.

        The BEFORE UPDATE trigger ``trg_canonical_event_links_updated_at``
        refreshes ``updated_at`` automatically.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        retire_link(7, retire_reason="duplicate_canonical")

        sql = mock_cursor.execute.call_args[0][0]
        assert "updated_at" not in sql, (
            "retire_link must NOT write updated_at directly — the BEFORE "
            "UPDATE trigger handles it (Pattern 73 SSOT discipline)."
        )

    @patch("precog.database.crud_canonical_event_links.get_cursor")
    def test_uses_commit_true(self, mock_get_cursor):
        """retire_link is a write — get_cursor(commit=True) must be used."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        retire_link(7)

        mock_get_cursor.assert_called_once_with(commit=True)
