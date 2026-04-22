"""Unit tests for crud_schedulers module — extracted from test_crud_operations_unit.py (split per #893 Option 1).

Covers scheduler IPC status CRUD (migration 0012, issue #255):
- upsert_scheduler_status / get_scheduler_status / list_scheduler_services
- cleanup_stale_schedulers / delete_scheduler_status

Note: these classes import from precog.database.crud_schedulers inside each test
method (preserved verbatim from the original file).
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestUpsertSchedulerStatusUnit:
    """Unit tests for upsert_scheduler_status function."""

    @patch("precog.database.crud_schedulers.get_cursor")
    def test_upsert_scheduler_status_minimal_params(self, mock_get_cursor):
        """Test upsert with only required parameters (host_id, service_name)."""
        from precog.database.crud_schedulers import upsert_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_scheduler_status(
            host_id="DESKTOP-TEST",
            service_name="espn",
        )

        assert result is True
        mock_cursor.execute.assert_called_once()
        # Verify SQL contains UPSERT pattern
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO scheduler_status" in sql
        assert "ON CONFLICT" in sql
        assert "DO UPDATE SET" in sql

    @patch("precog.database.crud_schedulers.get_cursor")
    def test_upsert_scheduler_status_all_params(self, mock_get_cursor):
        """Test upsert with all parameters.

        Educational Note:
            This tests the full scheduler status update including:
            - status: Service state transition
            - pid: Process ID for monitoring
            - started_at: Service start timestamp
            - stats: JSON metrics (polls, errors, etc.)
            - config: JSON configuration
            - error_message: For failed status
        """
        from precog.database.crud_schedulers import upsert_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_scheduler_status(
            host_id="DESKTOP-TEST",
            service_name="espn",
            status="running",
            pid=12345,
            started_at=datetime(2024, 12, 24, 10, 0, 0),
            stats={"polls": 100, "errors": 0},
            config={"poll_interval": 60},
            error_message=None,
        )

        assert result is True
        # Verify all columns are in the INSERT
        sql = mock_cursor.execute.call_args[0][0]
        assert "status" in sql
        assert "pid" in sql
        assert "started_at" in sql
        assert "stats" in sql
        assert "config" in sql

    @patch("precog.database.crud_schedulers.get_cursor")
    def test_upsert_scheduler_status_with_error(self, mock_get_cursor):
        """Test upsert with error message for failed status."""
        from precog.database.crud_schedulers import upsert_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_scheduler_status(
            host_id="DESKTOP-TEST",
            service_name="kalshi_rest",
            status="failed",
            error_message="Connection timeout after 30s",
        )

        assert result is True
        params = mock_cursor.execute.call_args[0][1]
        assert "failed" in params
        assert "Connection timeout after 30s" in params


@pytest.mark.unit
class TestGetSchedulerStatusUnit:
    """Unit tests for get_scheduler_status function."""

    @patch("precog.database.crud_schedulers.fetch_one")
    def test_get_scheduler_status_found(self, mock_fetch_one):
        """Test get_scheduler_status returns service status when found."""
        from precog.database.crud_schedulers import get_scheduler_status

        mock_fetch_one.return_value = {
            "host_id": "DESKTOP-TEST",
            "service_name": "espn",
            "status": "running",
            "pid": 12345,
            "last_heartbeat": datetime(2024, 12, 24, 10, 5, 0),
            "stats": {"polls": 50},
            "config": {"poll_interval": 60},
        }

        result = get_scheduler_status("DESKTOP-TEST", "espn")

        assert result is not None
        assert result["status"] == "running"
        assert result["pid"] == 12345
        mock_fetch_one.assert_called_once()

    @patch("precog.database.crud_schedulers.fetch_one")
    def test_get_scheduler_status_not_found(self, mock_fetch_one):
        """Test get_scheduler_status returns None when service not found."""
        from precog.database.crud_schedulers import get_scheduler_status

        mock_fetch_one.return_value = None

        result = get_scheduler_status("NONEXISTENT-HOST", "unknown_service")

        assert result is None


@pytest.mark.unit
class TestListSchedulerServicesUnit:
    """Unit tests for list_scheduler_services function."""

    @patch("precog.database.crud_schedulers.fetch_all")
    def test_list_scheduler_services_all(self, mock_fetch_all):
        """Test listing all scheduler services."""
        from precog.database.crud_schedulers import list_scheduler_services

        mock_fetch_all.return_value = [
            {"host_id": "HOST-1", "service_name": "espn", "status": "running"},
            {"host_id": "HOST-1", "service_name": "kalshi_rest", "status": "stopped"},
            {"host_id": "HOST-2", "service_name": "espn", "status": "running"},
        ]

        result = list_scheduler_services()

        assert len(result) == 3
        assert result[0]["service_name"] == "espn"

    @patch("precog.database.crud_schedulers.fetch_all")
    def test_list_scheduler_services_by_host(self, mock_fetch_all):
        """Test filtering services by host_id."""
        from precog.database.crud_schedulers import list_scheduler_services

        mock_fetch_all.return_value = [
            {"host_id": "HOST-1", "service_name": "espn", "status": "running"},
            {"host_id": "HOST-1", "service_name": "kalshi_rest", "status": "stopped"},
        ]

        result = list_scheduler_services(host_id="HOST-1")

        assert len(result) == 2
        # Verify host_id filter was applied
        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "host_id = %s" in sql

    @patch("precog.database.crud_schedulers.fetch_all")
    def test_list_scheduler_services_by_status(self, mock_fetch_all):
        """Test filtering services by status."""
        from precog.database.crud_schedulers import list_scheduler_services

        mock_fetch_all.return_value = [
            {"host_id": "HOST-1", "service_name": "espn", "status": "running"},
        ]

        result = list_scheduler_services(status_filter="running")

        assert len(result) == 1
        # Verify status filter was applied
        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "status = %s" in sql

    @patch("precog.database.crud_schedulers.fetch_all")
    def test_list_scheduler_services_includes_stale_detection(self, mock_fetch_all):
        """Test that is_stale field is included when requested.

        Educational Note:
            The is_stale field helps detect crashed services. If a service
            status is 'running' but last_heartbeat is >2 minutes old, the
            service likely crashed without graceful shutdown.
        """
        from precog.database.crud_schedulers import list_scheduler_services

        mock_fetch_all.return_value = [
            {"host_id": "HOST-1", "service_name": "espn", "status": "running", "is_stale": False},
        ]

        result = list_scheduler_services(include_stale=True, stale_threshold_seconds=120)

        # Verify stale detection is in the query
        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "is_stale" in sql
        # Verify result contains the expected service
        assert len(result) == 1
        assert result[0]["host_id"] == "HOST-1"


@pytest.mark.unit
class TestCleanupStaleSchedulersUnit:
    """Unit tests for cleanup_stale_schedulers function."""

    @patch("precog.database.crud_schedulers.get_cursor")
    def test_cleanup_stale_schedulers_marks_as_failed(self, mock_get_cursor):
        """Test that stale services are marked as failed."""
        from precog.database.crud_schedulers import cleanup_stale_schedulers

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2  # 2 stale services cleaned up
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = cleanup_stale_schedulers(stale_threshold_seconds=120)

        assert result == 2
        # Verify SQL updates status to 'failed'
        sql = mock_cursor.execute.call_args[0][0]
        assert "SET status = 'failed'" in sql
        assert "IN ('running', 'starting')" in sql

    @patch("precog.database.crud_schedulers.get_cursor")
    def test_cleanup_stale_schedulers_by_host(self, mock_get_cursor):
        """Test cleanup only affects specified host."""
        from precog.database.crud_schedulers import cleanup_stale_schedulers

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = cleanup_stale_schedulers(
            stale_threshold_seconds=120,
            host_id="DESKTOP-TEST",
        )

        assert result == 1
        # Verify host_id filter was applied
        sql = mock_cursor.execute.call_args[0][0]
        assert "host_id = %s" in sql

    @patch("precog.database.crud_schedulers.get_cursor")
    def test_cleanup_stale_schedulers_no_stale_services(self, mock_get_cursor):
        """Test cleanup when no stale services exist."""
        from precog.database.crud_schedulers import cleanup_stale_schedulers

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # No stale services
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = cleanup_stale_schedulers(stale_threshold_seconds=120)

        assert result == 0


@pytest.mark.unit
class TestDeleteSchedulerStatusUnit:
    """Unit tests for delete_scheduler_status function."""

    @patch("precog.database.crud_schedulers.get_cursor")
    def test_delete_scheduler_status_found(self, mock_get_cursor):
        """Test delete returns True when record found and deleted."""
        from precog.database.crud_schedulers import delete_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = delete_scheduler_status("DESKTOP-TEST", "old_service")

        assert result is True
        # Verify DELETE SQL
        sql = mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM scheduler_status" in sql

    @patch("precog.database.crud_schedulers.get_cursor")
    def test_delete_scheduler_status_not_found(self, mock_get_cursor):
        """Test delete returns False when record not found."""
        from precog.database.crud_schedulers import delete_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # No record deleted
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = delete_scheduler_status("NONEXISTENT-HOST", "unknown_service")

        assert result is False
