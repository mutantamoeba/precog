"""
Backup system type definitions.

Immutable dataclasses for backup metadata and enums for backup lifecycle.

Design:
    - BackupMetadata is frozen (immutable) — once created, metadata is a permanent record.
    - Metadata is serialized as JSON sidecar files alongside backup dumps.
    - Self-contained: if the DB is gone, metadata in storage is sufficient to identify
      and restore backups (you can't query the DB to find backup locations when the DB
      is the thing you're restoring).
"""

from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path  # noqa: TC003 — used at runtime in from_json_file/save_json


class BackupType(str, enum.Enum):
    """Type of backup schedule that triggered this backup."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MANUAL = "manual"


class BackupStatus(str, enum.Enum):
    """Current lifecycle status of a backup."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass(frozen=True)
class BackupMetadata:
    """Immutable metadata record for a database backup.

    Stored as a JSON sidecar alongside the backup file. Designed to be
    self-contained: if the database is gone, the metadata in storage is
    sufficient to identify and restore.

    Args:
        backup_id: Unique identifier (ISO timestamp + short suffix).
        database_name: Source database name (e.g., 'precog_dev').
        environment: PRECOG_ENV at time of backup (dev/test/staging/prod).
        backup_type: What triggered this backup (daily/weekly/monthly/manual).
        status: Current lifecycle status.
        created_at: When the backup was initiated (UTC).
        completed_at: When the backup finished (None if in-progress/failed).
        size_bytes: Size of the backup file in bytes.
        pg_version: PostgreSQL server version used for pg_dump.
        storage_id: Backend-specific location identifier.
        verified: Whether pg_restore --list succeeded.
        checksum_sha256: SHA-256 hash of the backup file.
        hostname: Machine that produced the backup.
        migration_head: Alembic migration revision at time of backup.
        row_counts: Table row counts at time of backup (for sanity checks).
    """

    backup_id: str
    database_name: str
    environment: str
    backup_type: BackupType
    status: BackupStatus
    created_at: datetime
    completed_at: datetime | None = None
    size_bytes: int = 0
    pg_version: str = ""
    storage_id: str = ""
    verified: bool = False
    checksum_sha256: str = ""
    hostname: str = ""
    migration_head: str = ""
    row_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        data = asdict(self)
        # Convert enums to strings
        data["backup_type"] = self.backup_type.value
        data["status"] = self.status.value
        # Convert datetimes to ISO format
        data["created_at"] = self.created_at.isoformat()
        data["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> BackupMetadata:
        """Deserialize from dict (loaded from JSON sidecar)."""
        return cls(
            backup_id=data["backup_id"],
            database_name=data["database_name"],
            environment=data["environment"],
            backup_type=BackupType(data["backup_type"]),
            status=BackupStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            size_bytes=data.get("size_bytes", 0),
            pg_version=data.get("pg_version", ""),
            storage_id=data.get("storage_id", ""),
            verified=data.get("verified", False),
            checksum_sha256=data.get("checksum_sha256", ""),
            hostname=data.get("hostname", ""),
            migration_head=data.get("migration_head", ""),
            row_counts=data.get("row_counts", {}),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> BackupMetadata:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_json_file(cls, path: Path) -> BackupMetadata:
        """Load metadata from a JSON sidecar file."""
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def save_json(self, path: Path) -> None:
        """Save metadata to a JSON sidecar file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


class BackupError(Exception):
    """Base exception for backup operations."""


class StorageError(BackupError):
    """Storage backend operation failed."""


class BackupNotFoundError(BackupError):
    """Requested backup does not exist in storage."""


class ConfigurationError(BackupError):
    """Backup configuration is invalid."""
