"""
Backup orchestrator — coordinates pg_dump, verification, storage, and retention.

The orchestrator is the core backup engine. It:
    1. Runs pg_dump to create a compressed backup
    2. Computes checksum for integrity verification
    3. Optionally verifies via pg_restore --list
    4. Delegates storage to a StorageBackend
    5. Records status in system_health table
    6. Enforces retention policy (deletes old backups)

Usage:
    >>> from precog.backup.orchestrator import BackupOrchestrator
    >>> orchestrator = BackupOrchestrator()
    >>> metadata = orchestrator.create_backup()
    >>> orchestrator.restore_backup("precog_dev_20260405_030000.dump")
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from precog.backup._registry import get_storage_backend

if TYPE_CHECKING:
    from precog.backup._base import StorageBackend
from precog.backup._types import (
    BackupError,
    BackupMetadata,
    BackupStatus,
    BackupType,
    ConfigurationError,
)

logger = logging.getLogger(__name__)

# Timeout for pg_dump/pg_restore operations (seconds)
_PG_TIMEOUT = 1800  # 30 minutes


class BackupOrchestrator:
    """Coordinates backup creation, restoration, and lifecycle management.

    The orchestrator is storage-agnostic — it produces backup files
    locally, then delegates storage to a pluggable StorageBackend.

    Args:
        config: Full backup config dict from system.yaml backup section.
            If None, loads from ConfigLoader.

    Example:
        >>> orchestrator = BackupOrchestrator()
        >>> meta = orchestrator.create_backup(backup_type=BackupType.MANUAL)
        >>> print(f"Backup {meta.backup_id}: {meta.size_bytes} bytes")
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        if config is None:
            config = self._load_config()

        self._config = config
        self._verify_after = config.get("verify_after_backup", True)
        self._format = config.get("format", "custom")

        # Initialize storage backend
        backend_name = config.get("storage_backend", "local")
        storage_config = config.get("storage", {}).get(backend_name, {})
        self._backend: StorageBackend = get_storage_backend(backend_name, storage_config)

    @staticmethod
    def _load_config() -> dict[str, Any]:
        """Load backup config from system.yaml."""
        from precog.config.config_loader import ConfigLoader

        loader = ConfigLoader()
        return cast("dict[str, Any]", loader.load("system").get("backup", {}))

    @property
    def backend(self) -> StorageBackend:
        """The active storage backend."""
        return self._backend

    def _get_db_params(self) -> dict[str, str]:
        """Get database connection parameters from environment.

        Returns:
            Dict with host, port, dbname, user, password.

        Raises:
            ConfigurationError: If required params are missing.
        """
        from precog.config.environment import get_database_name, get_prefixed_env

        password = get_prefixed_env("DB_PASSWORD", "")
        if not password:
            raise ConfigurationError(
                "Database password not set. Set {PRECOG_ENV}_DB_PASSWORD environment variable."
            )

        return {
            "host": get_prefixed_env("DB_HOST", "localhost"),
            "port": get_prefixed_env("DB_PORT", "5432"),
            "dbname": get_database_name(),
            "user": get_prefixed_env("DB_USER", "postgres"),
            "password": password,
        }

    def _get_pg_version(self) -> str:
        """Query PostgreSQL server version."""
        try:
            from precog.database.connection import fetch_all

            rows = fetch_all("SELECT version()")
            if rows:
                return str(rows[0].get("version", "unknown"))
        except Exception as e:
            logger.debug("Could not determine PG version: %s", e)
        return "unknown"

    def _get_migration_head(self) -> str:
        """Get current Alembic migration revision.

        Uses the database/ directory as CWD since that's where alembic.ini lives.
        Returns "unknown" if alembic is not available or the command fails.
        """
        try:
            result = subprocess.run(
                ["python", "-m", "alembic", "current"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Path(__file__).parent.parent / "database"),
            )
            if result.returncode == 0:
                # Parse "abc123 (head)" format
                for line in result.stdout.strip().splitlines():
                    if "head" in line or line.strip():
                        return line.strip().split()[0]
        except Exception as e:
            logger.debug("Could not determine migration head: %s", e)
        return "unknown"

    def _get_row_counts(self) -> dict[str, int]:
        """Get row counts for critical tables (sanity check metadata).

        Table names are from a hardcoded list — no external input is interpolated
        into the SQL query. The f-string is safe here (noqa: S608).
        """
        from precog.database.connection import fetch_all

        # Safety: this list is hardcoded. Never populate from config or user input.
        critical_tables = [
            "markets",
            "market_prices",
            "games",
            "game_states",
            "positions",
            "teams",
            "orders",
            "account_balance",
        ]
        counts: dict[str, int] = {}
        for table in critical_tables:
            try:
                rows = fetch_all(
                    f"SELECT COUNT(*) as cnt FROM {table}"  # noqa: S608
                )
                counts[table] = rows[0]["cnt"] if rows else 0
            except Exception as e:
                logger.debug("Could not count rows in %s: %s", table, e)
                counts[table] = -1  # Table may not exist yet
        return counts

    @staticmethod
    def _compute_checksum(file_path: Path) -> str:
        """Compute SHA-256 checksum of a file (streaming, memory-safe)."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _generate_backup_id(self, db_params: dict[str, str], backup_type: BackupType) -> str:
        """Generate a unique backup ID.

        Format: {dbname}_{YYYYMMDD}_{HHMMSS}_{type}.dump
        Example: precog_dev_20260405_030000_daily.dump
        """
        now = datetime.now(UTC)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        return f"{db_params['dbname']}_{timestamp}_{backup_type.value}.dump"

    def create_backup(
        self,
        backup_type: BackupType = BackupType.MANUAL,
    ) -> BackupMetadata:
        """Create a database backup.

        Runs pg_dump, verifies, stores via backend, records health status,
        and enforces retention.

        Args:
            backup_type: What triggered this backup.

        Returns:
            BackupMetadata for the completed backup.

        Raises:
            BackupError: If any step fails.
        """
        db_params = self._get_db_params()
        backup_id = self._generate_backup_id(db_params, backup_type)
        now = datetime.now(UTC)

        logger.info(
            "Starting %s backup: %s (database: %s)",
            backup_type.value,
            backup_id,
            db_params["dbname"],
        )

        # Create initial metadata
        metadata = BackupMetadata(
            backup_id=backup_id,
            database_name=db_params["dbname"],
            environment=self._get_environment(),
            backup_type=backup_type,
            status=BackupStatus.IN_PROGRESS,
            created_at=now,
            pg_version=self._get_pg_version(),
            hostname=platform.node(),
            migration_head=self._get_migration_head(),
            row_counts=self._get_row_counts(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / backup_id

            try:
                # Step 1: Run pg_dump
                self._run_pg_dump(db_params, dump_path)

                # Step 2: Compute checksum
                checksum = self._compute_checksum(dump_path)
                size_bytes = dump_path.stat().st_size

                # Step 3: Verify if configured
                verified = False
                if self._verify_after:
                    verified = self._verify_backup(dump_path)

                # Update metadata with results
                metadata = BackupMetadata(
                    backup_id=metadata.backup_id,
                    database_name=metadata.database_name,
                    environment=metadata.environment,
                    backup_type=metadata.backup_type,
                    status=(BackupStatus.VERIFIED if verified else BackupStatus.COMPLETED),
                    created_at=metadata.created_at,
                    completed_at=datetime.now(UTC),
                    size_bytes=size_bytes,
                    pg_version=metadata.pg_version,
                    verified=verified,
                    checksum_sha256=checksum,
                    hostname=metadata.hostname,
                    migration_head=metadata.migration_head,
                    row_counts=metadata.row_counts,
                )

                # Step 4: Store via backend
                storage_id = self._backend.store(dump_path, metadata)
                metadata = BackupMetadata(
                    **{
                        **metadata.to_dict(),
                        "storage_id": storage_id,
                        "backup_type": metadata.backup_type,
                        "status": metadata.status,
                        "created_at": metadata.created_at,
                        "completed_at": metadata.completed_at,
                    }
                )

                logger.info(
                    "Backup complete: %s (%d bytes, checksum=%s, verified=%s)",
                    backup_id,
                    size_bytes,
                    checksum[:12],
                    verified,
                )

                # Step 5: Record health status
                self._record_health("healthy", metadata)

                # Step 6: Enforce retention
                self._enforce_retention()

                return metadata

            except Exception as e:
                logger.error("Backup failed: %s — %s", backup_id, e)
                failed_metadata = BackupMetadata(
                    backup_id=metadata.backup_id,
                    database_name=metadata.database_name,
                    environment=metadata.environment,
                    backup_type=metadata.backup_type,
                    status=BackupStatus.FAILED,
                    created_at=metadata.created_at,
                    completed_at=datetime.now(UTC),
                    hostname=metadata.hostname,
                )
                self._record_health("degraded", failed_metadata, error=str(e))
                raise BackupError(f"Backup failed: {e}") from e

    def restore_backup(
        self,
        backup_id: str,
        *,
        force: bool = False,
    ) -> None:
        """Restore a database from backup.

        Downloads the backup from storage, verifies checksum, and runs
        pg_restore. Includes safety checks for cross-environment restores.

        Args:
            backup_id: The backup_id (filename) to restore.
            force: Skip environment safety check.

        Raises:
            BackupError: If restore fails.
        """
        # Find the backup metadata
        backups = self._backend.list_backups()
        metadata = None
        for b in backups:
            if b.backup_id == backup_id:
                metadata = b
                break

        if metadata is None:
            raise BackupError(
                f"Backup '{backup_id}' not found. "
                f"Use 'precog backup list' to see available backups."
            )

        # Safety check: cross-environment restore
        current_env = self._get_environment()
        if metadata.environment != current_env and not force:
            raise BackupError(
                f"Cross-environment restore blocked. "
                f"Backup is from '{metadata.environment}', "
                f"current environment is '{current_env}'. "
                f"Use --force to override."
            )

        db_params = self._get_db_params()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Download from storage
            storage_id = metadata.storage_id or metadata.backup_id
            local_path = self._backend.retrieve(storage_id, Path(tmpdir))

            # Verify checksum if available
            if metadata.checksum_sha256:
                actual_checksum = self._compute_checksum(local_path)
                if actual_checksum != metadata.checksum_sha256:
                    raise BackupError(
                        f"Checksum mismatch! Expected {metadata.checksum_sha256[:12]}..., "
                        f"got {actual_checksum[:12]}... "
                        f"Backup may be corrupted."
                    )
                logger.info("Checksum verified: %s", actual_checksum[:12])

            # Run pg_restore
            self._run_pg_restore(db_params, local_path)
            logger.info("Restore complete from backup: %s", backup_id)

    def list_backups(self) -> list[BackupMetadata]:
        """List all available backups from the active storage backend.

        Returns:
            List of BackupMetadata, sorted newest-first.
        """
        return self._backend.list_backups()

    def _run_pg_dump(self, db_params: dict[str, str], output_path: Path) -> None:
        """Run pg_dump to create a compressed backup.

        Uses custom format (-Fc) by default for compression and
        parallel restore support.

        Raises:
            BackupError: If pg_dump fails.
        """
        pg_dump = shutil.which("pg_dump")
        if not pg_dump:
            raise ConfigurationError(
                "pg_dump not found on PATH. Install PostgreSQL client tools. "
                "On Windows: add PostgreSQL bin/ to PATH."
            )

        format_flag = {
            "custom": "-Fc",
            "directory": "-Fd",
            "plain": "-Fp",
        }.get(self._format, "-Fc")

        cmd = [
            pg_dump,
            "-h",
            db_params["host"],
            "-p",
            db_params["port"],
            "-U",
            db_params["user"],
            "-d",
            db_params["dbname"],
            format_flag,
            "-f",
            str(output_path),
        ]

        env = {
            **os.environ,
            "PGPASSWORD": db_params["password"],
        }

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_PG_TIMEOUT,
                env=env,
                check=True,
            )
            logger.info(
                "pg_dump completed: %s (%d bytes)",
                output_path.name,
                output_path.stat().st_size,
            )
        except FileNotFoundError as e:
            raise ConfigurationError(
                f"pg_dump not found at '{pg_dump}'. Install PostgreSQL client tools."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise BackupError(
                f"pg_dump timed out after {_PG_TIMEOUT}s. "
                f"Database may be too large for the configured timeout."
            ) from e
        except subprocess.CalledProcessError as e:
            raise BackupError(f"pg_dump failed:\n  stdout: {e.stdout}\n  stderr: {e.stderr}") from e

    def _verify_backup(self, dump_path: Path) -> bool:
        """Verify backup integrity via pg_restore --list.

        Returns:
            True if verification succeeded.
        """
        pg_restore = shutil.which("pg_restore")
        if not pg_restore:
            logger.warning(
                "pg_restore not found — skipping verification. "
                "Install PostgreSQL client tools for backup verification."
            )
            return False

        try:
            result = subprocess.run(
                [pg_restore, "--list", str(dump_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                # Count objects in the backup
                lines = [
                    line
                    for line in result.stdout.splitlines()
                    if line.strip() and not line.startswith(";")
                ]
                logger.info("Backup verified: %d objects in dump", len(lines))
                return True
            logger.warning("Backup verification failed: %s", result.stderr)
            return False
        except Exception as e:
            logger.warning("Backup verification error: %s", e)
            return False

    def _run_pg_restore(self, db_params: dict[str, str], dump_path: Path) -> None:
        """Run pg_restore to restore a backup.

        Uses --clean to drop existing objects before restoring.

        Raises:
            BackupError: If pg_restore fails.
        """
        pg_restore = shutil.which("pg_restore")
        if not pg_restore:
            raise ConfigurationError(
                "pg_restore not found on PATH. Install PostgreSQL client tools."
            )

        cmd = [
            pg_restore,
            "-h",
            db_params["host"],
            "-p",
            db_params["port"],
            "-U",
            db_params["user"],
            "-d",
            db_params["dbname"],
            "--clean",
            "--if-exists",
            str(dump_path),
        ]

        env = {
            **os.environ,
            "PGPASSWORD": db_params["password"],
        }

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_PG_TIMEOUT,
                env=env,
            )
            # pg_restore returns non-zero for warnings too, so check stderr
            if result.returncode != 0 and "ERROR" in result.stderr:
                raise BackupError(f"pg_restore errors:\n{result.stderr}")
            if result.stderr:
                logger.warning("pg_restore warnings: %s", result.stderr[:500])
            logger.info("pg_restore completed successfully")
        except subprocess.TimeoutExpired as e:
            raise BackupError(f"pg_restore timed out after {_PG_TIMEOUT}s.") from e
        except subprocess.CalledProcessError as e:
            raise BackupError(f"pg_restore failed:\n  stderr: {e.stderr}") from e

    def _record_health(
        self,
        status: str,
        metadata: BackupMetadata,
        error: str | None = None,
    ) -> None:
        """Record backup status in system_health table."""
        try:
            from precog.database.crud_system import upsert_system_health

            details: dict[str, Any] = {
                "backup_id": metadata.backup_id,
                "backup_type": metadata.backup_type.value,
                "size_bytes": metadata.size_bytes,
                "verified": metadata.verified,
                "storage_backend": type(self._backend).__name__,
            }
            if error:
                details["error"] = error
            if metadata.completed_at:
                duration = (metadata.completed_at - metadata.created_at).total_seconds()
                details["duration_seconds"] = round(duration, 1)

            upsert_system_health(
                component="backup",
                status=status,
                details=details,
                alert_sent=status != "healthy",
            )
        except Exception as e:
            # Don't fail the backup if health recording fails
            logger.warning("Failed to record backup health: %s", e)

    def _enforce_retention(self) -> None:
        """Delete backups exceeding retention policy.

        Retention rules from config:
            - daily: retention_days (default 7)
            - weekly: retention_weeks (default 4)
            - monthly: retention_months (default 12)
            - manual: never auto-deleted
        """
        schedule = self._config.get("schedule", {})
        retention = {
            BackupType.DAILY: schedule.get("daily", {}).get("retention_days", 7),
            BackupType.WEEKLY: (schedule.get("weekly", {}).get("retention_weeks", 4) * 7),
            BackupType.MONTHLY: (schedule.get("monthly", {}).get("retention_months", 12) * 30),
        }

        backups = self._backend.list_backups()
        now = datetime.now(UTC)
        deleted_count = 0

        for backup in backups:
            if backup.backup_type == BackupType.MANUAL:
                continue  # Never auto-delete manual backups

            max_age_days = retention.get(backup.backup_type)
            if max_age_days is None:
                continue

            age_days = (now - backup.created_at).days
            if age_days > max_age_days:
                storage_id = backup.storage_id or backup.backup_id
                if self._backend.delete(storage_id):
                    logger.info(
                        "Retention: deleted %s (%d days old, max %d)",
                        backup.backup_id,
                        age_days,
                        max_age_days,
                    )
                    deleted_count += 1

        if deleted_count > 0:
            logger.info("Retention policy: deleted %d old backups", deleted_count)

    @staticmethod
    def _get_environment() -> str:
        """Get current PRECOG_ENV."""
        return os.getenv("PRECOG_ENV", "dev")
