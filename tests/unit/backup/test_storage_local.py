"""Tests for local filesystem storage backend."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from precog.backup._types import (
    BackupMetadata,
    BackupNotFoundError,
    BackupStatus,
    BackupType,
)
from precog.backup.storage_local import LocalStorageBackend


@pytest.fixture
def storage_dir(tmp_path: Path) -> Path:
    """Create a temporary storage directory."""
    d = tmp_path / "backups"
    d.mkdir()
    return d


@pytest.fixture
def backend(storage_dir: Path) -> LocalStorageBackend:
    """Create a LocalStorageBackend pointing at tmp_path."""
    return LocalStorageBackend({"directory": str(storage_dir)})


@pytest.fixture
def sample_dump(tmp_path: Path) -> Path:
    """Create a fake pg_dump file."""
    dump = tmp_path / "precog_dev_20260405_030000_manual.dump"
    dump.write_bytes(b"PGDMP" + b"\x00" * 1000)  # Fake pg_dump header
    return dump


@pytest.fixture
def sample_metadata() -> BackupMetadata:
    """Create sample metadata matching the dump file."""
    return BackupMetadata(
        backup_id="precog_dev_20260405_030000_manual.dump",
        database_name="precog_dev",
        environment="dev",
        backup_type=BackupType.MANUAL,
        status=BackupStatus.VERIFIED,
        created_at=datetime(2026, 4, 5, 3, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 5, 3, 0, 45, tzinfo=UTC),
        size_bytes=1005,
        verified=True,
        checksum_sha256="abc123",
    )


class TestLocalStorageBackend:
    """Tests for LocalStorageBackend operations."""

    def test_validate_config_creates_directory(self, tmp_path: Path) -> None:
        """validate_config creates the directory if missing."""
        new_dir = tmp_path / "new_backups"
        backend = LocalStorageBackend({"directory": str(new_dir)})
        backend.validate_config()
        assert new_dir.exists()

    def test_validate_config_checks_write_access(self, tmp_path: Path) -> None:
        """validate_config succeeds on writable directory."""
        backend = LocalStorageBackend({"directory": str(tmp_path)})
        backend.validate_config()  # Should not raise

    def test_store_and_retrieve(
        self,
        backend: LocalStorageBackend,
        storage_dir: Path,
        sample_dump: Path,
        sample_metadata: BackupMetadata,
    ) -> None:
        """store copies file and saves metadata sidecar."""
        storage_id = backend.store(sample_dump, sample_metadata)

        # Verify backup file exists in storage
        stored_file = storage_dir / storage_id
        assert stored_file.exists()
        assert stored_file.stat().st_size == sample_dump.stat().st_size

        # Verify metadata sidecar exists
        meta_file = storage_dir / f"{storage_id}.meta.json"
        assert meta_file.exists()

        # Retrieve to a different location
        retrieve_dir = storage_dir.parent / "restored"
        retrieved = backend.retrieve(storage_id, retrieve_dir)
        assert retrieved.exists()
        assert retrieved.stat().st_size == sample_dump.stat().st_size

    def test_list_backups(
        self,
        backend: LocalStorageBackend,
        sample_dump: Path,
        sample_metadata: BackupMetadata,
    ) -> None:
        """list_backups reads metadata from sidecar files."""
        backend.store(sample_dump, sample_metadata)
        backups = backend.list_backups()
        assert len(backups) == 1
        assert backups[0].backup_id == sample_metadata.backup_id
        assert backups[0].database_name == "precog_dev"

    def test_list_backups_empty(self, backend: LocalStorageBackend) -> None:
        """list_backups returns empty list when no backups exist."""
        assert backend.list_backups() == []

    def test_delete(
        self,
        backend: LocalStorageBackend,
        storage_dir: Path,
        sample_dump: Path,
        sample_metadata: BackupMetadata,
    ) -> None:
        """delete removes both backup file and metadata sidecar."""
        storage_id = backend.store(sample_dump, sample_metadata)
        assert backend.exists(storage_id)

        result = backend.delete(storage_id)
        assert result is True
        assert not backend.exists(storage_id)
        assert not (storage_dir / f"{storage_id}.meta.json").exists()

    def test_delete_nonexistent(self, backend: LocalStorageBackend) -> None:
        """delete returns False for nonexistent backup."""
        assert backend.delete("nonexistent.dump") is False

    def test_exists(
        self,
        backend: LocalStorageBackend,
        sample_dump: Path,
        sample_metadata: BackupMetadata,
    ) -> None:
        """exists returns True for stored backups, False otherwise."""
        assert backend.exists("nonexistent.dump") is False
        storage_id = backend.store(sample_dump, sample_metadata)
        assert backend.exists(storage_id) is True

    def test_retrieve_nonexistent_raises(
        self, backend: LocalStorageBackend, tmp_path: Path
    ) -> None:
        """retrieve raises BackupNotFoundError for missing backup."""
        with pytest.raises(BackupNotFoundError):
            backend.retrieve("nonexistent.dump", tmp_path / "restore")

    def test_get_storage_info(self, backend: LocalStorageBackend) -> None:
        """get_storage_info returns type and directory."""
        info = backend.get_storage_info()
        assert info["type"] == "local"
        assert "directory" in info


class TestPathResolution:
    """Tests for path resolution (relative, absolute, UNC)."""

    def test_relative_path(self) -> None:
        """Relative paths are resolved against CWD."""
        backend = LocalStorageBackend({"directory": "backups"})
        assert backend.directory == Path.cwd() / "backups"

    def test_absolute_path(self, tmp_path: Path) -> None:
        """Absolute paths are used as-is."""
        backend = LocalStorageBackend({"directory": str(tmp_path / "abs")})
        assert backend.directory == tmp_path / "abs"

    def test_unc_path_forward_slashes(self) -> None:
        """UNC paths with forward slashes are preserved."""
        backend = LocalStorageBackend({"directory": "//server/share/backups"})
        # Should start with UNC prefix (OS-dependent separator)
        dir_str = str(backend.directory)
        assert "server" in dir_str
        assert "backups" in dir_str

    def test_default_directory(self) -> None:
        """Default directory is 'backups' relative to CWD."""
        backend = LocalStorageBackend({})
        assert backend.directory == Path.cwd() / "backups"
