"""
Local filesystem storage backend.

Stores backup files on local disk, mapped drives, or UNC network paths.

Supports:
    - Relative paths (resolved against CWD)
    - Absolute paths (e.g., D:/precog-backups)
    - UNC network paths (e.g., //server/share/precog-backups)
    - Mapped network drives (e.g., Z:/precog-backups)

Configuration (system.yaml):
    backup:
      storage_backend: "local"
      storage:
        local:
          directory: "backups"  # or UNC path, absolute path, etc.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from precog.backup._base import StorageBackend
from precog.backup._types import (
    BackupMetadata,
    BackupNotFoundError,
    ConfigurationError,
    StorageError,
)

logger = logging.getLogger(__name__)


class LocalStorageBackend(StorageBackend):
    """Store backups on local or network filesystem.

    The backup file and its JSON metadata sidecar are stored together
    in the configured directory. The storage_id is the backup filename
    (without the .meta.json suffix).

    Args:
        config: Dict from backup.storage.local in system.yaml.
            Required keys: directory (str).

    Example:
        >>> backend = LocalStorageBackend({"directory": "backups"})
        >>> backend.validate_config()
        >>> storage_id = backend.store(Path("/tmp/dump.sql"), metadata)
    """

    def __init__(self, config: dict) -> None:
        raw_directory = config.get("directory", "backups")
        self._directory = self._resolve_path(raw_directory)

    @staticmethod
    def _resolve_path(raw_path: str) -> Path:
        """Resolve a path string, handling UNC and network paths.

        UNC paths (//server/share/...) are preserved as-is.
        Relative paths are resolved against CWD.
        Absolute paths are used directly.

        Args:
            raw_path: Path string from config. Forward slashes recommended
                (YAML interprets backslashes as escape sequences).

        Returns:
            Resolved Path object.
        """
        # Normalize forward slashes (YAML-safe) to OS separators
        normalized = raw_path.replace("/", os.sep)

        # Detect UNC paths (//server/share or \\server\share)
        if raw_path.startswith(("//", "\\\\")):
            # UNC path — use as-is, don't resolve() which can fail on
            # disconnected shares
            return Path(normalized)

        path = Path(normalized)
        if path.is_absolute():
            return path

        # Relative path — resolve against CWD
        return Path.cwd() / path

    @property
    def directory(self) -> Path:
        """The resolved backup storage directory."""
        return self._directory

    def validate_config(self) -> None:
        """Validate the backup directory is accessible.

        Creates the directory if it doesn't exist.
        Verifies write access by creating a test file.

        Raises:
            ConfigurationError: If directory cannot be created or is not writable.
        """
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ConfigurationError(
                f"Cannot create backup directory '{self._directory}': {e}. "
                f"Check path exists and permissions are correct. "
                f"For network paths, verify the share is accessible."
            ) from e

        # Verify write access
        test_file = self._directory / ".backup_write_test"
        try:
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
        except OSError as e:
            raise ConfigurationError(
                f"Backup directory '{self._directory}' is not writable: {e}"
            ) from e

    def _backup_path(self, storage_id: str) -> Path:
        """Get the full path for a backup file."""
        return self._directory / storage_id

    def _metadata_path(self, storage_id: str) -> Path:
        """Get the full path for a backup's metadata sidecar."""
        return self._directory / f"{storage_id}.meta.json"

    def store(self, local_path: Path, metadata: BackupMetadata) -> str:
        """Copy backup file to the storage directory.

        Also saves the metadata JSON sidecar alongside the backup.

        Args:
            local_path: Path to the backup file produced by pg_dump.
            metadata: Backup metadata to store as sidecar.

        Returns:
            Storage ID (the backup filename in the storage directory).

        Raises:
            StorageError: If copy or metadata write fails.
        """
        filename = local_path.name
        dest_path = self._backup_path(filename)
        meta_path = self._metadata_path(filename)

        try:
            # Ensure directory exists (may have been deleted since validate)
            self._directory.mkdir(parents=True, exist_ok=True)

            # Copy backup file (preserves timestamps)
            shutil.copy2(str(local_path), str(dest_path))
            logger.info(
                "Stored backup %s -> %s (%d bytes)",
                local_path.name,
                dest_path,
                dest_path.stat().st_size,
            )

            # Save metadata sidecar
            metadata.save_json(meta_path)

            return filename

        except OSError as e:
            # Clean up partial writes
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            if meta_path.exists():
                meta_path.unlink(missing_ok=True)
            raise StorageError(
                f"Failed to store backup '{filename}' to '{self._directory}': {e}"
            ) from e

    def retrieve(self, storage_id: str, local_path: Path) -> Path:
        """Copy backup file from storage to a local directory.

        Args:
            storage_id: Filename returned by store().
            local_path: Local directory to copy the backup into.

        Returns:
            Path to the copied backup file.

        Raises:
            BackupNotFoundError: If the backup doesn't exist in storage.
            StorageError: If the copy fails.
        """
        src_path = self._backup_path(storage_id)

        if not src_path.exists():
            raise BackupNotFoundError(f"Backup '{storage_id}' not found in '{self._directory}'")

        dest = Path(local_path) / storage_id
        try:
            Path(local_path).mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_path), str(dest))
            logger.info("Retrieved backup %s -> %s", storage_id, dest)
            return dest
        except OSError as e:
            raise StorageError(f"Failed to retrieve backup '{storage_id}': {e}") from e

    def list_backups(self) -> list[BackupMetadata]:
        """List all backups in the storage directory.

        Reads metadata from JSON sidecar files. Backups without sidecars
        are logged as warnings and skipped.

        Returns:
            List of BackupMetadata, sorted newest-first.
        """
        if not self._directory.exists():
            return []

        backups: list[BackupMetadata] = []
        for meta_file in sorted(self._directory.glob("*.meta.json"), reverse=True):
            try:
                metadata = BackupMetadata.from_json_file(meta_file)
                backups.append(metadata)
            except (OSError, KeyError, ValueError) as e:
                logger.warning("Skipping corrupt metadata file %s: %s", meta_file, e)

        return backups

    def delete(self, storage_id: str) -> bool:
        """Delete a backup and its metadata sidecar.

        Args:
            storage_id: Filename returned by store().

        Returns:
            True if deleted, False if not found.
        """
        backup_path = self._backup_path(storage_id)
        meta_path = self._metadata_path(storage_id)

        if not backup_path.exists() and not meta_path.exists():
            return False

        if backup_path.exists():
            backup_path.unlink()
            logger.info("Deleted backup file: %s", backup_path)

        if meta_path.exists():
            meta_path.unlink()
            logger.info("Deleted metadata file: %s", meta_path)

        return True

    def exists(self, storage_id: str) -> bool:
        """Check if a backup exists in storage."""
        return self._backup_path(storage_id).exists()

    def get_storage_info(self) -> dict[str, str]:
        """Return info about the local storage backend."""
        info = {
            "type": "local",
            "directory": str(self._directory),
        }
        try:
            usage = shutil.disk_usage(str(self._directory))
            info["total_gb"] = f"{usage.total / (1024**3):.1f}"
            info["free_gb"] = f"{usage.free / (1024**3):.1f}"
            info["used_percent"] = f"{(usage.used / usage.total) * 100:.1f}%"
        except OSError:
            info["space"] = "unavailable (network path?)"
        return info
