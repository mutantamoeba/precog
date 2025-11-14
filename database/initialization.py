"""
Database initialization and schema management module.

This module provides functions for setting up and validating the Precog database
schema. It separates business logic from CLI presentation for better testability
and reusability.

Educational Note:
    This module demonstrates separation of concerns - business logic (what to do)
    is separated from presentation logic (how to display it). This makes functions
    easier to test because you can test "does schema validation work?" without
    needing to test "does the CLI output look correct?".

Reference:
    docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md - Complete schema documentation
    main.py:db_init() - CLI command that uses these functions
"""

import os
import subprocess
from pathlib import Path


def validate_schema_file(schema_path: str) -> bool:
    """Validate that schema file exists and is readable.

    Args:
        schema_path: Path to SQL schema file (e.g., "database/precog_schema_v1.7.sql")

    Returns:
        True if file exists and is readable, False otherwise

    Educational Note:
        We check both existence (os.path.exists) and readability (os.access)
        because a file might exist but not have read permissions. This prevents
        confusing error messages like "file not found" when the real issue is
        "permission denied".

    Example:
        >>> validate_schema_file("database/precog_schema_v1.7.sql")
        True
        >>> validate_schema_file("nonexistent.sql")
        False
    """
    return os.path.exists(schema_path) and os.access(schema_path, os.R_OK)


def apply_schema(db_url: str, schema_file: str, timeout: int = 30) -> tuple[bool, str]:
    """Apply database schema using psql subprocess.

    This function executes the SQL schema file using the psql command-line tool.
    It's tolerant of "already exists" errors (for idempotency) but fails on
    other errors like permission denied or syntax errors.

    Args:
        db_url: PostgreSQL connection URL (postgresql://user:pass@host:port/dbname)
        schema_file: Path to SQL schema file
        timeout: Maximum seconds to wait for psql command (default: 30)

    Returns:
        Tuple of (success: bool, error_message: str)
        - (True, "") if schema applied successfully
        - (False, error_message) if schema application failed

    Educational Note:
        We use subprocess.run() instead of executing SQL directly through Python
        because psql has better handling of complex SQL scripts (comments,
        multi-statement transactions, etc.). The downside is we need psql installed.

        Security: We validate db_url format and schema_file existence before
        passing to subprocess to prevent command injection attacks.

    Example:
        >>> success, error = apply_schema("postgresql://localhost/precog", "schema.sql")
        >>> if success:
        ...     print("Schema applied")
        ... else:
        ...     print(f"Failed: {error}")
    """
    # Security validation: Ensure db_url is a valid PostgreSQL URL
    if not db_url or not db_url.startswith(("postgresql://", "postgres://")):
        return False, "Invalid database URL format (must start with postgresql://)"

    # Security validation: Ensure schema_file exists and is a .sql file
    if not schema_file.endswith(".sql"):
        return False, "Schema file must be a .sql file"

    if not os.path.exists(schema_file):
        return False, f"Schema file not found: {schema_file}"

    try:
        result = subprocess.run(
            ["psql", db_url, "-f", schema_file],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Check for errors (but ignore "already exists" - that's OK for idempotency)
        if result.returncode != 0 and "already exists" not in result.stderr:
            return False, result.stderr

        return True, ""

    except FileNotFoundError:
        return False, "psql command not found - please install PostgreSQL client tools"

    except subprocess.TimeoutExpired:
        return False, f"Schema application timed out after {timeout} seconds"


def apply_migrations(
    db_url: str, migration_dir: str = "database/migrations", timeout: int = 30
) -> tuple[int, list[str]]:
    """Apply all pending database migrations.

    Migrations are applied in alphabetical order (expected naming: 001_name.sql, 002_name.sql, etc.).
    Each migration is idempotent (can be run multiple times safely).

    Args:
        db_url: PostgreSQL connection URL
        migration_dir: Directory containing migration SQL files (default: "database/migrations")
        timeout: Maximum seconds per migration (default: 30)

    Returns:
        Tuple of (migrations_applied: int, failed_migrations: List[str])
        - (10, []) means 10 migrations applied successfully
        - (5, ["006_add_index.sql"]) means 5 succeeded, 1 failed

    Educational Note:
        Migrations should be numbered sequentially (001, 002, 003...) so they
        apply in the correct order. Each migration should be idempotent using
        "IF NOT EXISTS" clauses or "CREATE OR REPLACE" to avoid errors on re-runs.

        Security: We validate db_url format and migration file paths before
        passing to subprocess to prevent command injection attacks.

    Example:
        >>> applied, failed = apply_migrations("postgresql://localhost/precog")
        >>> print(f"{applied} migrations applied, {len(failed)} failed")
        10 migrations applied, 0 failed
    """
    # Security validation: Ensure db_url is a valid PostgreSQL URL
    if not db_url or not db_url.startswith(("postgresql://", "postgres://")):
        return 0, []

    if not os.path.exists(migration_dir):
        return 0, []

    migration_path = Path(migration_dir)
    migration_files = sorted([f.name for f in migration_path.iterdir() if f.suffix == ".sql"])

    if not migration_files:
        return 0, []

    applied = 0
    failed = []

    for migration_file in migration_files:
        # Security validation: Ensure migration file is .sql and exists
        if not migration_file.endswith(".sql"):
            failed.append(migration_file)
            continue

        migration_file_path = os.path.join(migration_dir, migration_file)
        if not os.path.exists(migration_file_path):
            failed.append(migration_file)
            continue

        try:
            result = subprocess.run(
                ["psql", db_url, "-f", migration_file_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0 and "already exists" not in result.stderr:
                failed.append(migration_file)
            else:
                applied += 1

        except (FileNotFoundError, subprocess.TimeoutExpired):
            failed.append(migration_file)

    return applied, failed


def validate_critical_tables(required_tables: list[str] | None = None) -> list[str]:
    """Check which critical tables are missing from the database.

    This function queries the database information_schema to verify that all
    critical tables exist. It's used during database initialization to ensure
    the schema was applied correctly.

    Args:
        required_tables: List of table names to check. If None, uses default
                        critical tables (platforms, series, events, markets,
                        strategies, probability_models, positions, trades)

    Returns:
        List of missing table names (empty list if all tables exist)

    Educational Note:
        We use information_schema.tables instead of pg_catalog because
        information_schema is SQL standard (works across PostgreSQL, MySQL, etc.)
        while pg_catalog is PostgreSQL-specific. For a single-database project
        this doesn't matter, but it's good practice for portability.

    Example:
        >>> missing = validate_critical_tables()
        >>> if missing:
        ...     print(f"Missing tables: {missing}")
        ... else:
        ...     print("All critical tables exist")
        All critical tables exist

    Reference:
        docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md - Complete table documentation
    """
    from database.connection import fetch_all

    if required_tables is None:
        required_tables = [
            "platforms",
            "series",
            "events",
            "markets",
            "strategies",
            "probability_models",
            "positions",
            "trades",
        ]

    missing_tables = []

    for table in required_tables:
        result = fetch_all(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = %s
            );
            """,
            (table,),
        )

        if not result or not result[0]["exists"]:
            missing_tables.append(table)

    return missing_tables


def get_database_url() -> str | None:
    """Get database connection URL from environment.

    Returns:
        Database URL string, or None if not set

    Educational Note:
        We centralize environment variable access in one place so if we ever
        need to change how we get the DB URL (e.g., from a config file instead),
        we only need to update this one function instead of searching through
        all the code.

    Example:
        >>> url = get_database_url()
        >>> if url:
        ...     print(f"Connected to: {url}")
        ... else:
        ...     print("DATABASE_URL not set")
    """
    return os.getenv("DATABASE_URL")
