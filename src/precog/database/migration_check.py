"""Migration parity check — detect when DB schema is behind alembic head.

Addresses a recurring failure mode where CRUD code references columns
from recent migrations but the local DB hasn't been upgraded.
Three documented occurrences: session 30, session 42f, session 54.

Issue: #792
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MigrationStatus:
    """Result of a migration parity check."""

    is_current: bool
    db_version: str | None
    head_version: str | None
    error: str | None = None

    @property
    def versions_behind(self) -> int | None:
        """Estimate how many migrations behind (None if unknown)."""
        if self.is_current or self.db_version is None or self.head_version is None:
            return 0 if self.is_current else None
        try:
            return int(self.head_version) - int(self.db_version)
        except (ValueError, TypeError):
            return None


def get_alembic_head() -> str | None:
    """Read the head revision from the alembic script directory.

    Uses ScriptDirectory to walk the migration chain — same logic
    alembic uses internally, so this is always consistent with
    `alembic heads`.

    Note: alembic.ini uses a relative script_location ("alembic"),
    resolved relative to the .ini file's parent directory.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    db_dir = Path(__file__).parent
    alembic_ini = db_dir / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("alembic.ini not found at %s", alembic_ini)
        return None

    cfg = Config(str(alembic_ini))
    # Resolve script_location relative to alembic.ini's directory,
    # not the process cwd (which may be the repo root).
    cfg.set_main_option("script_location", str(db_dir / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    return script.get_current_head()


def get_db_version() -> str | None:
    """Query the current alembic version from the database.

    Returns None if the alembic_version table doesn't exist or is empty.
    """
    from precog.database.connection import get_cursor

    try:
        with get_cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
            row = cur.fetchone()
            if row is None:
                return None
            # get_cursor returns RealDictCursor rows
            version: str = row["version_num"] if isinstance(row, dict) else row[0]
            return version
    except Exception as e:
        logger.debug("Could not read alembic_version: %s", e)
        return None


def check_migration_parity() -> MigrationStatus:
    """Check if the database schema matches the alembic head.

    Returns a MigrationStatus with:
    - is_current: True if DB version == head version
    - db_version: current DB migration version (or None)
    - head_version: latest migration in script directory (or None)
    - error: description if the check itself failed
    """
    try:
        head = get_alembic_head()
    except Exception as e:
        return MigrationStatus(
            is_current=False,
            db_version=None,
            head_version=None,
            error=f"Could not read alembic head: {e}",
        )

    try:
        db_ver = get_db_version()
    except Exception as e:
        return MigrationStatus(
            is_current=False,
            db_version=None,
            head_version=head,
            error=f"Could not read database version: {e}",
        )

    if head is None:
        return MigrationStatus(
            is_current=False,
            db_version=db_ver,
            head_version=None,
            error="No alembic head found — migration directory may be empty",
        )

    return MigrationStatus(
        is_current=(db_ver == head),
        db_version=db_ver,
        head_version=head,
    )
