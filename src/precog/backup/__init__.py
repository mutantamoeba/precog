"""
Precog Backup System.

Automated database backup with pluggable storage backends.

Quick start:
    >>> from precog.backup import BackupOrchestrator, BackupType
    >>> orchestrator = BackupOrchestrator()
    >>> metadata = orchestrator.create_backup(backup_type=BackupType.MANUAL)

CLI usage:
    precog backup create              # Manual backup
    precog backup list                # List all backups
    precog backup restore <backup-id> # Restore from backup
    precog backup info                # Show storage backend info

Architecture:
    - BackupOrchestrator: Coordinates pg_dump, verification, storage, retention
    - StorageBackend (ABC): Pluggable storage interface
    - LocalStorageBackend: Local/network filesystem
    - FilenStorageBackend: Filen cloud (200GB lifetime)
    - Future: S3, Google Drive, OneDrive

See also:
    - system.yaml backup section for configuration
    - docs/guides/BACKUP_STRATEGY.md (planned)
"""

from precog.backup._base import StorageBackend
from precog.backup._registry import get_available_backends, get_storage_backend
from precog.backup._types import (
    BackupError,
    BackupMetadata,
    BackupNotFoundError,
    BackupStatus,
    BackupType,
    ConfigurationError,
    StorageError,
)
from precog.backup.orchestrator import BackupOrchestrator

__all__ = [
    "BackupError",
    "BackupMetadata",
    "BackupNotFoundError",
    "BackupOrchestrator",
    "BackupStatus",
    "BackupType",
    "ConfigurationError",
    "StorageBackend",
    "StorageError",
    "get_available_backends",
    "get_storage_backend",
]
