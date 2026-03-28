"""
Unit Tests for System Health CRUD Operations.

Tests the system_health table CRUD functions: upsert_system_health,
get_system_health, and get_system_health_summary.

The system_health table tracks component-level health status and is
written by the ServiceSupervisor health check loop. These tests verify
the CRUD layer in isolation with mocked database connections.

Related:
    - Migration 0001: system_health table schema
    - Issue #389: Wire system_health table
    - REQ-OBSERV-001: Observability Requirements

Usage:
    pytest tests/unit/database/test_crud_system_health.py -v
    pytest tests/unit/database/test_crud_system_health.py -v -m unit
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_operations import (
    VALID_SYSTEM_HEALTH_COMPONENTS,
    get_system_health,
    get_system_health_summary,
    upsert_system_health,
)

# =============================================================================
# UPSERT SYSTEM HEALTH TESTS
# =============================================================================


@pytest.mark.unit
class TestUpsertSystemHealth:
    """Unit tests for upsert_system_health with mocked database."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_healthy_component(self, mock_get_cursor: MagicMock) -> None:
        """Test upserting a healthy component returns True."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_system_health(
            component="kalshi_api",
            status="healthy",
        )

        assert result is True
        mock_get_cursor.assert_called_once_with(commit=True)
        # Should execute DELETE then INSERT
        assert mock_cursor.execute.call_count == 2

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_with_details(self, mock_get_cursor: MagicMock) -> None:
        """Test upserting with JSONB details payload."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        details = {"error_rate": "0.0200", "total_polls": 100, "total_errors": 2}
        result = upsert_system_health(
            component="espn_api",
            status="degraded",
            details=details,
            alert_sent=True,
        )

        assert result is True
        # Verify the INSERT call has the serialized JSON details
        insert_call = mock_cursor.execute.call_args_list[1]
        insert_params = insert_call[0][1]
        assert insert_params[0] == "espn_api"
        assert insert_params[1] == "degraded"
        assert json.loads(insert_params[2]) == details
        assert insert_params[3] is True  # alert_sent

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_with_none_details(self, mock_get_cursor: MagicMock) -> None:
        """Test upserting with no details passes None for JSONB column."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        upsert_system_health(component="database", status="healthy")

        insert_call = mock_cursor.execute.call_args_list[1]
        insert_params = insert_call[0][1]
        assert insert_params[2] is None  # details_json is None

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_delete_before_insert(self, mock_get_cursor: MagicMock) -> None:
        """Test that DELETE is executed before INSERT for upsert behavior."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        upsert_system_health(component="kalshi_api", status="healthy")

        calls = mock_cursor.execute.call_args_list
        # First call is DELETE
        assert "DELETE FROM system_health" in calls[0][0][0]
        assert calls[0][0][1] == ("kalshi_api",)
        # Second call is INSERT
        assert "INSERT INTO system_health" in calls[1][0][0]

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_returns_false_on_zero_rowcount(self, mock_get_cursor: MagicMock) -> None:
        """Test that zero rowcount returns False."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_system_health(component="kalshi_api", status="healthy")
        assert result is False

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_all_valid_statuses(self, mock_get_cursor: MagicMock) -> None:
        """Test all three valid status values pass through correctly."""
        for status in ("healthy", "degraded", "down"):
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

            result = upsert_system_health(component="kalshi_api", status=status)
            assert result is True

            insert_call = mock_cursor.execute.call_args_list[1]
            insert_params = insert_call[0][1]
            assert insert_params[1] == status

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_all_valid_components(self, mock_get_cursor: MagicMock) -> None:
        """Test all valid component names from VALID_SYSTEM_HEALTH_COMPONENTS.

        Validates against the app-layer enum (Migration 0043 dropped the DB
        CHECK constraint — see ADR-114 Part 2, R2).
        """
        for component in sorted(VALID_SYSTEM_HEALTH_COMPONENTS):
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

            result = upsert_system_health(component=component, status="healthy")
            assert result is True

            insert_call = mock_cursor.execute.call_args_list[1]
            insert_params = insert_call[0][1]
            assert insert_params[0] == component

    def test_upsert_invalid_component_raises_value_error(self) -> None:
        """Test that an unknown component raises ValueError before hitting the DB.

        Migration 0043 dropped the PostgreSQL CHECK constraint on component.
        App-layer validation in upsert_system_health() must catch invalid
        values early and raise a clear error with guidance on how to add new
        components.
        """
        with pytest.raises(ValueError, match="Invalid system_health component"):
            upsert_system_health(component="unknown_source", status="healthy")  # type: ignore[arg-type]

    def test_upsert_invalid_component_error_message_names_valid_set(self) -> None:
        """Test that the ValueError message includes valid component names."""
        with pytest.raises(ValueError) as exc_info:
            upsert_system_health(component="cfbd_api", status="healthy")  # type: ignore[arg-type]
        error_msg = str(exc_info.value)
        assert "cfbd_api" in error_msg
        assert "crud_operations.py" in error_msg


# =============================================================================
# GET SYSTEM HEALTH TESTS
# =============================================================================


@pytest.mark.unit
class TestGetSystemHealth:
    """Unit tests for get_system_health with mocked database."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_all_components(self, mock_fetch_all: MagicMock) -> None:
        """Test fetching all component health records."""
        mock_fetch_all.return_value = [
            {"health_id": 1, "component": "espn_api", "status": "healthy"},
            {"health_id": 2, "component": "kalshi_api", "status": "degraded"},
        ]

        result = get_system_health()

        assert len(result) == 2
        assert result[0]["component"] == "espn_api"
        assert result[1]["status"] == "degraded"
        # Called with just the query (no params tuple)
        mock_fetch_all.assert_called_once()
        call_args = mock_fetch_all.call_args
        assert len(call_args[0]) == 1  # Only query, no params

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_specific_component(self, mock_fetch_all: MagicMock) -> None:
        """Test fetching health for a specific component."""
        mock_fetch_all.return_value = [
            {"health_id": 1, "component": "kalshi_api", "status": "healthy"},
        ]

        result = get_system_health(component="kalshi_api")

        assert len(result) == 1
        assert result[0]["component"] == "kalshi_api"
        mock_fetch_all.assert_called_once()
        # Verify component was passed as param
        call_args = mock_fetch_all.call_args
        assert call_args[0][1] == ("kalshi_api",)

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_empty_result(self, mock_fetch_all: MagicMock) -> None:
        """Test fetching when no health records exist."""
        mock_fetch_all.return_value = []

        result = get_system_health()

        assert result == []

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_none_component_fetches_all(self, mock_fetch_all: MagicMock) -> None:
        """Test that component=None fetches all records."""
        mock_fetch_all.return_value = []

        get_system_health(component=None)

        # Should use the "all" query without WHERE clause
        query_arg = mock_fetch_all.call_args[0][0]
        assert "WHERE" not in query_arg


# =============================================================================
# GET SYSTEM HEALTH SUMMARY TESTS
# =============================================================================


@pytest.mark.unit
class TestGetSystemHealthSummary:
    """Unit tests for get_system_health_summary convenience function."""

    @patch("precog.database.crud_operations.get_system_health")
    def test_summary_maps_components_to_status(self, mock_get_health: MagicMock) -> None:
        """Test summary returns component -> status mapping."""
        mock_get_health.return_value = [
            {"component": "kalshi_api", "status": "healthy"},
            {"component": "espn_api", "status": "degraded"},
            {"component": "websocket", "status": "down"},
        ]

        result = get_system_health_summary()

        assert result == {
            "kalshi_api": "healthy",
            "espn_api": "degraded",
            "websocket": "down",
        }

    @patch("precog.database.crud_operations.get_system_health")
    def test_summary_empty_when_no_records(self, mock_get_health: MagicMock) -> None:
        """Test summary returns empty dict when no health records."""
        mock_get_health.return_value = []

        result = get_system_health_summary()

        assert result == {}

    @patch("precog.database.crud_operations.get_system_health")
    def test_summary_delegates_to_get_system_health(self, mock_get_health: MagicMock) -> None:
        """Test summary calls get_system_health with no filter."""
        mock_get_health.return_value = []

        get_system_health_summary()

        mock_get_health.assert_called_once_with()
