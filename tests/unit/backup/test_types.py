"""Tests for backup type definitions — BackupMetadata serialization and lifecycle."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — used at runtime in fixtures

import pytest

from precog.backup._types import (
    BackupMetadata,
    BackupStatus,
    BackupType,
)


@pytest.fixture
def sample_metadata() -> BackupMetadata:
    """Create a sample BackupMetadata for testing."""
    return BackupMetadata(
        backup_id="precog_dev_20260405_030000_manual.dump",
        database_name="precog_dev",
        environment="dev",
        backup_type=BackupType.MANUAL,
        status=BackupStatus.VERIFIED,
        created_at=datetime(2026, 4, 5, 3, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 5, 3, 0, 45, tzinfo=UTC),
        size_bytes=1_234_567,
        pg_version="PostgreSQL 15.4",
        storage_id="precog_dev_20260405_030000_manual.dump",
        verified=True,
        checksum_sha256="a" * 64,
        hostname="DESKTOP-PRECOG",
        migration_head="0050_add_phase2_indexes",
        row_counts={"markets": 500, "game_states": 12000, "teams": 120},
    )


class TestBackupMetadata:
    """Tests for BackupMetadata dataclass."""

    def test_frozen(self, sample_metadata: BackupMetadata) -> None:
        """BackupMetadata is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_metadata.status = BackupStatus.FAILED  # type: ignore[misc]

    def test_to_dict(self, sample_metadata: BackupMetadata) -> None:
        """to_dict serializes enums and datetimes correctly."""
        d = sample_metadata.to_dict()
        assert d["backup_type"] == "manual"
        assert d["status"] == "verified"
        assert "2026-04-05T03:00:00" in d["created_at"]
        assert "2026-04-05T03:00:45" in d["completed_at"]
        assert d["row_counts"]["markets"] == 500

    def test_from_dict(self, sample_metadata: BackupMetadata) -> None:
        """from_dict round-trips correctly."""
        d = sample_metadata.to_dict()
        restored = BackupMetadata.from_dict(d)
        assert restored.backup_id == sample_metadata.backup_id
        assert restored.backup_type == BackupType.MANUAL
        assert restored.status == BackupStatus.VERIFIED
        assert restored.size_bytes == 1_234_567
        assert restored.row_counts["teams"] == 120

    def test_to_json_and_back(self, sample_metadata: BackupMetadata) -> None:
        """JSON serialization round-trips correctly."""
        json_str = sample_metadata.to_json()
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["backup_id"] == "precog_dev_20260405_030000_manual.dump"

        # Round-trip
        restored = BackupMetadata.from_json(json_str)
        assert restored.backup_id == sample_metadata.backup_id
        assert restored.verified is True

    def test_json_file_roundtrip(self, sample_metadata: BackupMetadata, tmp_path: Path) -> None:
        """Save to file and load back preserves all fields."""
        meta_file = tmp_path / "test.meta.json"
        sample_metadata.save_json(meta_file)

        assert meta_file.exists()
        loaded = BackupMetadata.from_json_file(meta_file)
        assert loaded.backup_id == sample_metadata.backup_id
        assert loaded.database_name == "precog_dev"
        assert loaded.migration_head == "0050_add_phase2_indexes"

    def test_from_dict_with_missing_optional_fields(self) -> None:
        """from_dict handles missing optional fields gracefully."""
        minimal = {
            "backup_id": "test.dump",
            "database_name": "test_db",
            "environment": "test",
            "backup_type": "manual",
            "status": "completed",
            "created_at": "2026-04-05T03:00:00+00:00",
        }
        metadata = BackupMetadata.from_dict(minimal)
        assert metadata.completed_at is None
        assert metadata.size_bytes == 0
        assert metadata.verified is False
        assert metadata.row_counts == {}

    def test_default_row_counts_is_independent(self) -> None:
        """Each instance gets its own row_counts dict (no mutable default sharing)."""
        m1 = BackupMetadata(
            backup_id="a.dump",
            database_name="db",
            environment="dev",
            backup_type=BackupType.DAILY,
            status=BackupStatus.COMPLETED,
            created_at=datetime.now(UTC),
        )
        m2 = BackupMetadata(
            backup_id="b.dump",
            database_name="db",
            environment="dev",
            backup_type=BackupType.DAILY,
            status=BackupStatus.COMPLETED,
            created_at=datetime.now(UTC),
        )
        assert m1.row_counts is not m2.row_counts


class TestBackupEnums:
    """Tests for BackupType and BackupStatus enums."""

    def test_backup_type_values(self) -> None:
        """All expected backup types exist."""
        assert BackupType.DAILY.value == "daily"
        assert BackupType.WEEKLY.value == "weekly"
        assert BackupType.MONTHLY.value == "monthly"
        assert BackupType.MANUAL.value == "manual"

    def test_backup_status_values(self) -> None:
        """All expected backup statuses exist."""
        assert BackupStatus.IN_PROGRESS.value == "in_progress"
        assert BackupStatus.COMPLETED.value == "completed"
        assert BackupStatus.VERIFIED.value == "verified"
        assert BackupStatus.FAILED.value == "failed"

    def test_backup_type_from_string(self) -> None:
        """BackupType can be created from string values."""
        assert BackupType("daily") == BackupType.DAILY
        with pytest.raises(ValueError):
            BackupType("invalid")
