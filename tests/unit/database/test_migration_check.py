"""Unit tests for migration parity check (#792).

Tests the check_migration_parity() function that detects when the
database schema is behind the alembic head. This is the function
called by `scheduler start` and `scheduler poll-once` before
starting services.
"""

from unittest.mock import patch

from precog.database.migration_check import (
    MigrationStatus,
    check_migration_parity,
)


class TestMigrationStatus:
    """Test MigrationStatus dataclass."""

    def test_versions_behind_numeric(self):
        s = MigrationStatus(is_current=False, db_version="0055", head_version="0057")
        assert s.versions_behind == 2

    def test_versions_behind_when_current(self):
        s = MigrationStatus(is_current=True, db_version="0057", head_version="0057")
        assert s.versions_behind == 0

    def test_versions_behind_none_when_unknown(self):
        s = MigrationStatus(is_current=False, db_version=None, head_version="0057")
        assert s.versions_behind is None

    def test_versions_behind_non_numeric(self):
        s = MigrationStatus(is_current=False, db_version="abc", head_version="0057")
        assert s.versions_behind is None


class TestCheckMigrationParity:
    """Test check_migration_parity() integration."""

    @patch("precog.database.migration_check.get_db_version")
    @patch("precog.database.migration_check.get_alembic_heads")
    def test_current_when_versions_match(self, mock_head, mock_db):
        mock_head.return_value = ["0057"]
        mock_db.return_value = "0057"

        result = check_migration_parity()

        assert result.is_current is True
        assert result.db_version == "0057"
        assert result.head_version == "0057"
        assert result.error is None

    @patch("precog.database.migration_check.get_db_version")
    @patch("precog.database.migration_check.get_alembic_heads")
    def test_behind_when_db_older(self, mock_head, mock_db):
        mock_head.return_value = ["0057"]
        mock_db.return_value = "0055"

        result = check_migration_parity()

        assert result.is_current is False
        assert result.db_version == "0055"
        assert result.head_version == "0057"
        assert result.versions_behind == 2

    @patch("precog.database.migration_check.get_db_version")
    @patch("precog.database.migration_check.get_alembic_heads")
    def test_behind_when_db_empty(self, mock_head, mock_db):
        mock_head.return_value = ["0057"]
        mock_db.return_value = None

        result = check_migration_parity()

        assert result.is_current is False
        assert result.db_version is None

    @patch("precog.database.migration_check.get_db_version")
    @patch("precog.database.migration_check.get_alembic_heads")
    def test_error_on_head_failure(self, mock_head, mock_db):
        mock_head.side_effect = RuntimeError("Script dir broken")

        result = check_migration_parity()

        assert result.is_current is False
        assert "Script dir broken" in result.error

    @patch("precog.database.migration_check.get_db_version")
    @patch("precog.database.migration_check.get_alembic_heads")
    def test_error_on_db_failure(self, mock_head, mock_db):
        mock_head.return_value = ["0057"]
        mock_db.side_effect = RuntimeError("DB unreachable")

        result = check_migration_parity()

        assert result.is_current is False
        assert "DB unreachable" in result.error

    @patch("precog.database.migration_check.get_db_version")
    @patch("precog.database.migration_check.get_alembic_heads")
    def test_error_when_no_head(self, mock_head, mock_db):
        mock_head.return_value = []
        mock_db.return_value = "0057"

        result = check_migration_parity()

        assert result.is_current is False
        assert result.error is not None
        assert "empty" in result.error.lower()
