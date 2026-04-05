"""
Abstract storage backend interface.

All backup storage destinations implement this interface. The BackupOrchestrator
produces backup files locally (via pg_dump), then delegates storage to a backend.

Current implementations:
    - LocalStorageBackend (storage_local.py) — local/network filesystem
    - FilenStorageBackend (storage_filen.py) — Filen cloud storage

To add a new backend:
    1. Create storage_<name>.py implementing StorageBackend
    2. Register in _registry.py
    3. Add config block under backup.storage.<name> in system.yaml
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from precog.backup._types import BackupMetadata


class StorageBackend(ABC):
    """Abstract interface for backup storage destinations.

    Implementations handle the physical storage of backup files.
    The BackupOrchestrator produces backup files locally (via pg_dump),
    then delegates storage to a backend.

    Subclasses MUST implement: store, retrieve, list_backups, delete, exists.
    Subclasses MAY override: validate_config, get_storage_info.
    """

    @abstractmethod
    def store(self, local_path: Path, metadata: BackupMetadata) -> str:
        """Upload/copy a backup file to the storage destination.

        Args:
            local_path: Path to the local backup file (produced by pg_dump).
            metadata: Metadata about this backup.

        Returns:
            Storage identifier (path, object key, etc.) for retrieval.

        Raises:
            StorageError: If storage operation fails.
        """
        ...

    @abstractmethod
    def retrieve(self, storage_id: str, local_path: Path) -> Path:
        """Download/copy a backup from storage to local filesystem.

        Args:
            storage_id: Identifier returned by store().
            local_path: Local directory to place the retrieved file.

        Returns:
            Path to the retrieved local file.

        Raises:
            StorageError: If retrieval fails.
            BackupNotFoundError: If storage_id does not exist.
        """
        ...

    @abstractmethod
    def list_backups(self) -> list[BackupMetadata]:
        """List all available backups in this storage destination.

        Returns:
            List of BackupMetadata, sorted newest-first.
        """
        ...

    @abstractmethod
    def delete(self, storage_id: str) -> bool:
        """Delete a backup from storage. Used by retention policy.

        Args:
            storage_id: Identifier returned by store().

        Returns:
            True if deleted, False if not found.
        """
        ...

    @abstractmethod
    def exists(self, storage_id: str) -> bool:
        """Check if a backup exists in storage.

        Args:
            storage_id: Identifier returned by store().

        Returns:
            True if the backup exists.
        """
        ...

    def validate_config(self) -> None:  # noqa: B027
        """Validate backend-specific configuration.

        Called during initialization. Override to validate credentials,
        paths, connectivity.

        Raises:
            ConfigurationError: If configuration is invalid.
        """

    def get_storage_info(self) -> dict[str, str]:
        """Return human-readable info about this storage backend.

        Used by CLI 'backup list' and health reporting.

        Returns:
            Dict with keys like 'type', 'location', 'space_available'.
        """
        return {"type": self.__class__.__name__}
