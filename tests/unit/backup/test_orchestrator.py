"""Tests for BackupOrchestrator — core backup/restore logic.

Mocks pg_dump/pg_restore subprocess calls and storage backend.
Tests the orchestration flow, not the external tools.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — used at runtime in fixtures
from unittest.mock import patch

import pytest

from precog.backup._types import (
    BackupError,
    BackupMetadata,
    BackupStatus,
    BackupType,
    ConfigurationError,
)
from precog.backup.orchestrator import BackupOrchestrator
from precog.backup.storage_local import LocalStorageBackend


@pytest.fixture
def backup_dir(tmp_path: Path) -> Path:
    """Create a temporary backup directory."""
    d = tmp_path / "backups"
    d.mkdir()
    return d


@pytest.fixture
def mock_config(backup_dir: Path) -> dict:
    """Backup config with local storage pointing at tmp_path."""
    return {
        "storage_backend": "local",
        "storage": {
            "local": {"directory": str(backup_dir)},
        },
        "verify_after_backup": True,
        "format": "custom",
        "schedule": {
            "daily": {"retention_days": 7},
            "weekly": {"retention_weeks": 4},
            "monthly": {"retention_months": 12},
        },
    }


@pytest.fixture
def mock_db_params() -> dict:
    return {
        "host": "localhost",
        "port": "5432",
        "dbname": "precog_test",
        "user": "postgres",
        "password": "test_password",
    }


class TestBackupOrchestrator:
    """Tests for BackupOrchestrator creation and config."""

    def test_init_with_config(self, mock_config: dict) -> None:
        """Orchestrator initializes with explicit config."""
        orchestrator = BackupOrchestrator(config=mock_config)
        assert isinstance(orchestrator.backend, LocalStorageBackend)

    def test_init_unknown_backend(self, backup_dir: Path) -> None:
        """Orchestrator raises for unknown backend."""
        config = {
            "storage_backend": "nonexistent",
            "storage": {"nonexistent": {}},
        }
        with pytest.raises(ConfigurationError, match="Unknown"):
            BackupOrchestrator(config=config)


class TestCreateBackup:
    """Tests for the create_backup flow."""

    @patch("precog.backup.orchestrator.BackupOrchestrator._get_db_params")
    @patch("precog.backup.orchestrator.BackupOrchestrator._get_pg_version")
    @patch("precog.backup.orchestrator.BackupOrchestrator._get_migration_head")
    @patch("precog.backup.orchestrator.BackupOrchestrator._get_row_counts")
    @patch("precog.backup.orchestrator.BackupOrchestrator._run_pg_dump")
    @patch("precog.backup.orchestrator.BackupOrchestrator._verify_backup")
    @patch("precog.backup.orchestrator.BackupOrchestrator._record_health")
    def test_create_backup_full_flow(
        self,
        mock_health,
        mock_verify,
        mock_pg_dump,
        mock_row_counts,
        mock_migration,
        mock_pg_version,
        mock_db_params,
        mock_config: dict,
    ) -> None:
        """Full backup flow: dump -> checksum -> verify -> store -> health."""
        mock_db_params.return_value = {
            "host": "localhost",
            "port": "5432",
            "dbname": "precog_test",
            "user": "postgres",
            "password": "test",
        }
        mock_pg_version.return_value = "PostgreSQL 15.4"
        mock_migration.return_value = "0050_test"
        mock_row_counts.return_value = {"markets": 100}
        mock_verify.return_value = True

        # Make pg_dump create a real file in the temp directory
        def fake_pg_dump(db_params, output_path):
            output_path.write_bytes(b"FAKE_DUMP_DATA" * 100)

        mock_pg_dump.side_effect = fake_pg_dump

        orchestrator = BackupOrchestrator(config=mock_config)
        metadata = orchestrator.create_backup(backup_type=BackupType.MANUAL)

        assert metadata.status == BackupStatus.VERIFIED
        assert metadata.database_name == "precog_test"
        assert metadata.backup_type == BackupType.MANUAL
        assert metadata.verified is True
        assert metadata.size_bytes > 0
        assert metadata.checksum_sha256 != ""
        assert metadata.pg_version == "PostgreSQL 15.4"
        assert metadata.row_counts == {"markets": 100}

        # Verify it was stored in the backend
        backups = orchestrator.list_backups()
        assert len(backups) == 1
        assert backups[0].backup_id == metadata.backup_id

        # Verify health was recorded
        mock_health.assert_called()

    @patch("precog.backup.orchestrator.BackupOrchestrator._get_db_params")
    @patch("precog.backup.orchestrator.BackupOrchestrator._run_pg_dump")
    @patch("precog.backup.orchestrator.BackupOrchestrator._record_health")
    def test_create_backup_failure_records_health(
        self,
        mock_health,
        mock_pg_dump,
        mock_db_params_fn,
        mock_config: dict,
    ) -> None:
        """Failed backup records degraded health status."""
        mock_db_params_fn.return_value = {
            "host": "localhost",
            "port": "5432",
            "dbname": "precog_test",
            "user": "postgres",
            "password": "test",
        }
        mock_pg_dump.side_effect = BackupError("pg_dump crashed")

        orchestrator = BackupOrchestrator(config=mock_config)
        with pytest.raises(BackupError, match="pg_dump crashed"):
            orchestrator.create_backup()

        # Should have recorded "degraded" health
        mock_health.assert_called()
        call_args = mock_health.call_args
        assert call_args[0][0] == "degraded"


class TestRestoreBackup:
    """Tests for the restore_backup flow."""

    @patch("precog.backup.orchestrator.BackupOrchestrator._get_db_params")
    @patch("precog.backup.orchestrator.BackupOrchestrator._run_pg_restore")
    @patch("precog.backup.orchestrator.BackupOrchestrator._get_environment")
    def test_restore_verifies_checksum(
        self,
        mock_env,
        mock_pg_restore,
        mock_db_params_fn,
        mock_config: dict,
        backup_dir: Path,
    ) -> None:
        """Restore verifies checksum before restoring."""
        mock_env.return_value = "dev"
        mock_db_params_fn.return_value = {
            "host": "localhost",
            "port": "5432",
            "dbname": "precog_test",
            "user": "postgres",
            "password": "test",
        }

        # Create a fake backup in storage
        backup_file = backup_dir / "test.dump"
        backup_file.write_bytes(b"FAKE_DATA")

        import hashlib

        checksum = hashlib.sha256(b"FAKE_DATA").hexdigest()

        metadata = BackupMetadata(
            backup_id="test.dump",
            database_name="precog_test",
            environment="dev",
            backup_type=BackupType.MANUAL,
            status=BackupStatus.VERIFIED,
            created_at=datetime.now(UTC),
            storage_id="test.dump",
            checksum_sha256=checksum,
        )
        metadata.save_json(backup_dir / "test.dump.meta.json")

        orchestrator = BackupOrchestrator(config=mock_config)
        orchestrator.restore_backup("test.dump", force=True)

        mock_pg_restore.assert_called_once()

    @patch("precog.backup.orchestrator.BackupOrchestrator._get_environment")
    def test_restore_blocks_cross_env(
        self,
        mock_env,
        mock_config: dict,
        backup_dir: Path,
    ) -> None:
        """Restore blocks cross-environment restore without --force."""
        mock_env.return_value = "prod"

        # Create a dev backup
        backup_file = backup_dir / "dev.dump"
        backup_file.write_bytes(b"DATA")
        metadata = BackupMetadata(
            backup_id="dev.dump",
            database_name="precog_dev",
            environment="dev",  # Different from current "prod"
            backup_type=BackupType.MANUAL,
            status=BackupStatus.COMPLETED,
            created_at=datetime.now(UTC),
            storage_id="dev.dump",
        )
        metadata.save_json(backup_dir / "dev.dump.meta.json")

        orchestrator = BackupOrchestrator(config=mock_config)
        with pytest.raises(BackupError, match="Cross-environment"):
            orchestrator.restore_backup("dev.dump")


class TestRetention:
    """Tests for retention policy enforcement."""

    def test_manual_backups_never_deleted(self, mock_config: dict, backup_dir: Path) -> None:
        """Manual backups are exempt from retention policy."""
        # Create old manual backup (100 days old)
        old_time = datetime(2026, 1, 1, tzinfo=UTC)
        metadata = BackupMetadata(
            backup_id="old_manual.dump",
            database_name="precog_dev",
            environment="dev",
            backup_type=BackupType.MANUAL,
            status=BackupStatus.COMPLETED,
            created_at=old_time,
            storage_id="old_manual.dump",
        )
        (backup_dir / "old_manual.dump").write_bytes(b"DATA")
        metadata.save_json(backup_dir / "old_manual.dump.meta.json")

        orchestrator = BackupOrchestrator(config=mock_config)
        orchestrator._enforce_retention()

        # Manual backup should still exist
        assert (backup_dir / "old_manual.dump").exists()
