"""
Filen cloud storage backend.

Stores backups in Filen cloud storage via the Filen CLI tool.

Filen offers 200GB lifetime storage and provides a CLI (`filen`) for
file operations. This backend shells out to the Filen CLI rather than
using a Python SDK, since the CLI is the most stable interface.

Prerequisites:
    - Filen CLI installed and on PATH: https://github.com/nicholasgasior/filen-cli
    - Authenticated: run `filen login` once before use
    - Or set environment variables: {PRECOG_ENV}_FILEN_EMAIL, {PRECOG_ENV}_FILEN_PASSWORD

Configuration (system.yaml):
    backup:
      storage_backend: "filen"
      storage:
        filen:
          remote_directory: "/precog-backups"
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from precog.backup._base import StorageBackend
from precog.backup._types import (
    BackupMetadata,
    BackupNotFoundError,
    ConfigurationError,
    StorageError,
)

logger = logging.getLogger(__name__)

# Timeout for Filen CLI operations (seconds)
_FILEN_TIMEOUT = 600  # 10 minutes for large uploads


class FilenStorageBackend(StorageBackend):
    """Store backups in Filen cloud storage via the Filen CLI.

    The backend uploads both the backup file and its JSON metadata
    sidecar to the configured remote directory.

    Args:
        config: Dict from backup.storage.filen in system.yaml.
            Required keys: remote_directory (str).

    Example:
        >>> backend = FilenStorageBackend({"remote_directory": "/precog-backups"})
        >>> backend.validate_config()
    """

    def __init__(self, config: dict) -> None:
        self._remote_dir = config.get("remote_directory", "/precog-backups")
        # Ensure remote dir starts with /
        if not self._remote_dir.startswith("/"):
            self._remote_dir = "/" + self._remote_dir

    def _run_filen(
        self,
        args: list[str],
        *,
        timeout: int = _FILEN_TIMEOUT,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a Filen CLI command.

        Args:
            args: Arguments to pass after 'filen'.
            timeout: Command timeout in seconds.
            check: Raise on non-zero exit code.

        Returns:
            CompletedProcess result.

        Raises:
            StorageError: If the command fails.
        """
        cmd = ["filen", *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check,
            )
            return result  # noqa: RET504
        except FileNotFoundError as e:
            raise StorageError(
                "Filen CLI not found. Install from: "
                "https://github.com/nicholasgasior/filen-cli "
                "and run 'filen login' to authenticate."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise StorageError(
                f"Filen CLI command timed out after {timeout}s: {' '.join(cmd)}"
            ) from e
        except subprocess.CalledProcessError as e:
            raise StorageError(
                f"Filen CLI command failed: {' '.join(cmd)}\n"
                f"  stdout: {e.stdout}\n"
                f"  stderr: {e.stderr}"
            ) from e

    def validate_config(self) -> None:
        """Validate Filen CLI is available and authenticated.

        Checks:
            1. filen CLI is installed and on PATH
            2. filen is authenticated (can list root)
            3. Remote directory exists or can be created

        Raises:
            ConfigurationError: If validation fails.
        """
        # Check CLI availability
        if not shutil.which("filen"):
            raise ConfigurationError(
                "Filen CLI not found on PATH. Install from: "
                "https://github.com/nicholasgasior/filen-cli "
                "and run 'filen login' to authenticate."
            )

        # Check authentication by listing root
        try:
            self._run_filen(["ls", "/"], timeout=30)
        except StorageError as e:
            raise ConfigurationError(
                f"Filen CLI authentication failed. Run 'filen login' first. Error: {e}"
            ) from e

        # Ensure remote directory exists
        try:
            result = self._run_filen(["ls", self._remote_dir], timeout=30, check=False)
            if result.returncode != 0:
                # Directory doesn't exist — create it
                self._run_filen(["mkdir", self._remote_dir], timeout=30)
                logger.info("Created Filen remote directory: %s", self._remote_dir)
        except StorageError as e:
            raise ConfigurationError(
                f"Cannot access or create Filen directory '{self._remote_dir}': {e}"
            ) from e

    def store(self, local_path: Path, metadata: BackupMetadata) -> str:
        """Upload backup file and metadata to Filen.

        Args:
            local_path: Path to backup file.
            metadata: Backup metadata.

        Returns:
            Remote path as storage_id.

        Raises:
            StorageError: If upload fails.
        """
        filename = local_path.name
        remote_path = f"{self._remote_dir}/{filename}"

        # Upload backup file
        logger.info("Uploading %s to Filen: %s", filename, remote_path)
        self._run_filen(["upload", str(local_path), self._remote_dir])

        # Upload metadata sidecar — must be named {filename}.meta.json
        # so delete() and list_backups() can find it by convention.
        meta_filename = f"{filename}.meta.json"
        tmp_meta = Path(tempfile.gettempdir()) / meta_filename
        try:
            tmp_meta.write_text(metadata.to_json(), encoding="utf-8")
            self._run_filen(["upload", str(tmp_meta), self._remote_dir])
        finally:
            tmp_meta.unlink(missing_ok=True)

        logger.info("Uploaded backup to Filen: %s", remote_path)
        return remote_path

    def retrieve(self, storage_id: str, local_path: Path) -> Path:
        """Download backup file from Filen.

        Args:
            storage_id: Remote path returned by store().
            local_path: Local directory for the download.

        Returns:
            Path to the downloaded file.

        Raises:
            BackupNotFoundError: If the remote file doesn't exist.
            StorageError: If download fails.
        """
        Path(local_path).mkdir(parents=True, exist_ok=True)

        try:
            self._run_filen(["download", storage_id, str(local_path)])
        except StorageError as e:
            if "not found" in str(e).lower() or "no such" in str(e).lower():
                raise BackupNotFoundError(f"Backup not found in Filen: {storage_id}") from e
            raise

        filename = Path(storage_id).name
        dest = Path(local_path) / filename
        logger.info("Downloaded backup from Filen: %s -> %s", storage_id, dest)
        return dest

    def list_backups(self) -> list[BackupMetadata]:
        """List backups by reading metadata sidecars from Filen.

        Downloads and parses all .meta.json files from the remote
        directory. This is a somewhat expensive operation — consider
        caching for frequent calls.

        Returns:
            List of BackupMetadata, sorted newest-first.
        """
        try:
            result = self._run_filen(["ls", self._remote_dir], timeout=60)
        except StorageError:
            return []

        # Parse ls output for .meta.json files
        meta_files = []
        for line in result.stdout.strip().splitlines():
            name = line.strip().split()[-1] if line.strip() else ""
            if name.endswith(".meta.json"):
                meta_files.append(f"{self._remote_dir}/{name}")

        backups: list[BackupMetadata] = []
        for remote_meta in meta_files:
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    self._run_filen(["download", remote_meta, tmpdir], timeout=30)
                    meta_name = Path(remote_meta).name
                    meta_path = Path(tmpdir) / meta_name
                    if meta_path.exists():
                        metadata = BackupMetadata.from_json_file(meta_path)
                        backups.append(metadata)
                except (StorageError, KeyError, ValueError) as e:
                    logger.warning(
                        "Skipping corrupt metadata from Filen %s: %s",
                        remote_meta,
                        e,
                    )

        # Sort newest first
        backups.sort(key=lambda m: m.created_at, reverse=True)
        return backups

    def delete(self, storage_id: str) -> bool:
        """Delete backup and metadata from Filen.

        Args:
            storage_id: Remote path returned by store().

        Returns:
            True if deleted, False if not found.
        """
        meta_remote = f"{storage_id}.meta.json"
        deleted = False

        for remote_path in [storage_id, meta_remote]:
            try:
                self._run_filen(["rm", remote_path], timeout=30)
                logger.info("Deleted from Filen: %s", remote_path)
                deleted = True
            except StorageError:
                pass  # File may not exist

        return deleted

    def exists(self, storage_id: str) -> bool:
        """Check if a backup exists in Filen."""
        try:
            result = self._run_filen(["ls", storage_id], timeout=30, check=False)
            return result.returncode == 0
        except StorageError:
            return False

    def get_storage_info(self) -> dict[str, str]:
        """Return info about the Filen storage backend."""
        return {
            "type": "filen",
            "remote_directory": self._remote_dir,
        }
