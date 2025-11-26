"""
Migration Utilities - Reusable error handling and helper functions for database migrations.

This module provides comprehensive error handling for common migration operations:
- Table creation/modification with conflict handling
- Column operations (add, rename, drop) with existence checks
- Index management with idempotent creation
- Constraint management (FK, unique, check) with conflict resolution
- Data migration with FK violation handling

Usage:
    from precog.database.migrations.migration_utils import (
        MigrationError,
        safe_create_table,
        safe_add_column,
        safe_create_index,
        safe_add_constraint,
        table_exists,
        column_exists,
        index_exists,
        constraint_exists,
    )

Error Handling Philosophy:
    - Idempotent operations: Running migration twice should succeed
    - Graceful degradation: Skip operations that are already complete
    - Clear error messages: Tell user exactly what failed and why
    - Rollback safety: All operations can be reversed

References:
    - Issue #107: Add comprehensive error handling to migrations
    - PR #92 Claude Code Review (M-03)
    - ADR-019: Database Migration Strategy

Created: 2025-11-25
Phase: 1.5 (Foundation Validation)
"""

import sys
from collections.abc import Callable
from pathlib import Path

import psycopg2
from psycopg2 import errors as pg_errors

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from precog.database.connection import fetch_one, get_cursor  # noqa: E402


class MigrationError(Exception):
    """Base exception for migration errors with contextual information."""

    def __init__(self, message: str, operation: str | None = None, details: dict | None = None):
        """
        Initialize migration error with context.

        Args:
            message: Human-readable error message
            operation: The operation that failed (e.g., "CREATE TABLE", "ADD COLUMN")
            details: Additional context (table name, column name, etc.)
        """
        self.message = message
        self.operation = operation
        self.details = details or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context."""
        parts = [self.message]
        if self.operation:
            parts.append(f"Operation: {self.operation}")
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            parts.append(f"Details: {details_str}")
        return " | ".join(parts)


# ============================================================================
# Existence Check Functions
# ============================================================================


def table_exists(table_name: str, schema: str = "public") -> bool:
    """
    Check if a table exists in the database.

    Args:
        table_name: Name of the table to check
        schema: Schema to check in (default: public)

    Returns:
        True if table exists, False otherwise

    Example:
        >>> if not table_exists("markets"):
        ...     create_markets_table()
    """
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = %s
            AND table_name = %s
        )
    """
    result = fetch_one(query, (schema, table_name))
    return result["exists"] if result else False


def column_exists(table_name: str, column_name: str, schema: str = "public") -> bool:
    """
    Check if a column exists in a table.

    Args:
        table_name: Name of the table
        column_name: Name of the column to check
        schema: Schema to check in (default: public)

    Returns:
        True if column exists, False otherwise

    Example:
        >>> if not column_exists("positions", "trade_source"):
        ...     add_trade_source_column()
    """
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = %s
            AND table_name = %s
            AND column_name = %s
        )
    """
    result = fetch_one(query, (schema, table_name, column_name))
    return result["exists"] if result else False


def index_exists(index_name: str, schema: str = "public") -> bool:
    """
    Check if an index exists.

    Args:
        index_name: Name of the index to check
        schema: Schema to check in (default: public)

    Returns:
        True if index exists, False otherwise

    Example:
        >>> if not index_exists("idx_markets_history"):
        ...     create_history_index()
    """
    query = """
        SELECT EXISTS (
            SELECT FROM pg_indexes
            WHERE schemaname = %s
            AND indexname = %s
        )
    """
    result = fetch_one(query, (schema, index_name))
    return result["exists"] if result else False


def constraint_exists(table_name: str, constraint_name: str, schema: str = "public") -> bool:
    """
    Check if a constraint exists on a table.

    Args:
        table_name: Name of the table
        constraint_name: Name of the constraint to check
        schema: Schema to check in (default: public)

    Returns:
        True if constraint exists, False otherwise

    Example:
        >>> if not constraint_exists("positions", "fk_positions_strategy"):
        ...     add_foreign_key()
    """
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.table_constraints
            WHERE table_schema = %s
            AND table_name = %s
            AND constraint_name = %s
        )
    """
    result = fetch_one(query, (schema, table_name, constraint_name))
    return result["exists"] if result else False


def trigger_exists(trigger_name: str, table_name: str, schema: str = "public") -> bool:
    """
    Check if a trigger exists on a table.

    Args:
        trigger_name: Name of the trigger to check
        table_name: Name of the table
        schema: Schema to check in (default: public)

    Returns:
        True if trigger exists, False otherwise
    """
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.triggers
            WHERE trigger_schema = %s
            AND event_object_table = %s
            AND trigger_name = %s
        )
    """
    result = fetch_one(query, (schema, table_name, trigger_name))
    return result["exists"] if result else False


# ============================================================================
# Safe DDL Operations
# ============================================================================


def safe_create_table(
    table_name: str,
    create_sql: str,
    if_not_exists: bool = True,
) -> tuple[bool, str]:
    """
    Safely create a table with error handling.

    Args:
        table_name: Name of the table to create
        create_sql: SQL CREATE TABLE statement
        if_not_exists: If True, skip if table already exists

    Returns:
        Tuple of (success, message)

    Example:
        >>> success, msg = safe_create_table(
        ...     "markets",
        ...     "CREATE TABLE markets (id SERIAL PRIMARY KEY, name TEXT)"
        ... )
        >>> print(msg)
        "Table 'markets' created successfully"
    """
    if if_not_exists and table_exists(table_name):
        return True, f"[SKIP] Table '{table_name}' already exists"

    try:
        with get_cursor(commit=True) as cursor:
            cursor.execute(create_sql)
        return True, f"[OK] Table '{table_name}' created successfully"

    except pg_errors.DuplicateTable:
        return True, f"[SKIP] Table '{table_name}' already exists (race condition)"

    except pg_errors.DuplicateObject as e:
        return False, f"[ERROR] Duplicate object when creating '{table_name}': {e}"

    except psycopg2.Error as e:
        raise MigrationError(
            f"Failed to create table '{table_name}'",
            operation="CREATE TABLE",
            details={"table": table_name, "error": str(e)},
        ) from e


def safe_add_column(
    table_name: str,
    column_name: str,
    column_def: str,
    if_not_exists: bool = True,
) -> tuple[bool, str]:
    """
    Safely add a column to a table with error handling.

    Args:
        table_name: Name of the table
        column_name: Name of the column to add
        column_def: Column definition (e.g., "TEXT NOT NULL DEFAULT ''")
        if_not_exists: If True, skip if column already exists

    Returns:
        Tuple of (success, message)

    Example:
        >>> success, msg = safe_add_column(
        ...     "positions",
        ...     "trade_source",
        ...     "VARCHAR(50) DEFAULT 'manual'"
        ... )
    """
    if if_not_exists and column_exists(table_name, column_name):
        return True, f"[SKIP] Column '{table_name}.{column_name}' already exists"

    try:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
        with get_cursor(commit=True) as cursor:
            cursor.execute(sql)
        return True, f"[OK] Column '{table_name}.{column_name}' added successfully"

    except pg_errors.DuplicateColumn:
        return True, f"[SKIP] Column '{table_name}.{column_name}' already exists (race condition)"

    except pg_errors.UndefinedTable:
        return False, f"[ERROR] Table '{table_name}' does not exist"

    except psycopg2.Error as e:
        raise MigrationError(
            f"Failed to add column '{column_name}' to '{table_name}'",
            operation="ADD COLUMN",
            details={"table": table_name, "column": column_name, "error": str(e)},
        ) from e


def safe_drop_column(
    table_name: str,
    column_name: str,
    if_exists: bool = True,
) -> tuple[bool, str]:
    """
    Safely drop a column from a table.

    Args:
        table_name: Name of the table
        column_name: Name of the column to drop
        if_exists: If True, skip if column doesn't exist

    Returns:
        Tuple of (success, message)
    """
    if if_exists and not column_exists(table_name, column_name):
        return True, f"[SKIP] Column '{table_name}.{column_name}' does not exist"

    try:
        sql = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        with get_cursor(commit=True) as cursor:
            cursor.execute(sql)
        return True, f"[OK] Column '{table_name}.{column_name}' dropped successfully"

    except pg_errors.UndefinedColumn:
        return True, f"[SKIP] Column '{table_name}.{column_name}' does not exist (race condition)"

    except psycopg2.Error as e:
        raise MigrationError(
            f"Failed to drop column '{column_name}' from '{table_name}'",
            operation="DROP COLUMN",
            details={"table": table_name, "column": column_name, "error": str(e)},
        ) from e


def safe_rename_column(
    table_name: str,
    old_name: str,
    new_name: str,
) -> tuple[bool, str]:
    """
    Safely rename a column with migration-safe pattern.

    Handles:
    - Column doesn't exist (old name) → error
    - Column already renamed → skip
    - Both exist → error (manual intervention needed)

    Args:
        table_name: Name of the table
        old_name: Current column name
        new_name: New column name

    Returns:
        Tuple of (success, message)
    """
    old_exists = column_exists(table_name, old_name)
    new_exists = column_exists(table_name, new_name)

    if new_exists and not old_exists:
        return True, f"[SKIP] Column '{table_name}.{old_name}' already renamed to '{new_name}'"

    if new_exists and old_exists:
        return False, (
            f"[ERROR] Both '{old_name}' and '{new_name}' exist in '{table_name}'. "
            "Manual intervention required."
        )

    if not old_exists:
        return False, f"[ERROR] Column '{table_name}.{old_name}' does not exist"

    try:
        sql = f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}"
        with get_cursor(commit=True) as cursor:
            cursor.execute(sql)
        return True, f"[OK] Column '{table_name}.{old_name}' renamed to '{new_name}'"

    except psycopg2.Error as e:
        raise MigrationError(
            f"Failed to rename column '{old_name}' to '{new_name}' in '{table_name}'",
            operation="RENAME COLUMN",
            details={"table": table_name, "old": old_name, "new": new_name, "error": str(e)},
        ) from e


def safe_create_index(
    index_name: str,
    table_name: str,
    columns: str,
    unique: bool = False,
    where_clause: str | None = None,
    if_not_exists: bool = True,
) -> tuple[bool, str]:
    """
    Safely create an index with error handling.

    Args:
        index_name: Name of the index
        table_name: Table to create index on
        columns: Column specification (e.g., "created_at DESC")
        unique: If True, create UNIQUE index
        where_clause: Optional WHERE clause for partial index
        if_not_exists: If True, skip if index already exists

    Returns:
        Tuple of (success, message)

    Example:
        >>> success, msg = safe_create_index(
        ...     "idx_markets_history",
        ...     "markets",
        ...     "row_current_ind, created_at DESC"
        ... )
    """
    if if_not_exists and index_exists(index_name):
        return True, f"[SKIP] Index '{index_name}' already exists"

    try:
        unique_str = "UNIQUE " if unique else ""
        where_str = f" WHERE {where_clause}" if where_clause else ""
        sql = f"CREATE {unique_str}INDEX {index_name} ON {table_name} ({columns}){where_str}"

        with get_cursor(commit=True) as cursor:
            cursor.execute(sql)
        return True, f"[OK] Index '{index_name}' created on '{table_name}'"

    except pg_errors.DuplicateTable:
        # Index names conflict with table namespace in PostgreSQL
        return True, f"[SKIP] Index '{index_name}' already exists (race condition)"

    except pg_errors.UndefinedTable:
        return False, f"[ERROR] Table '{table_name}' does not exist"

    except pg_errors.UndefinedColumn as e:
        return False, f"[ERROR] Column not found when creating index: {e}"

    except psycopg2.Error as e:
        raise MigrationError(
            f"Failed to create index '{index_name}'",
            operation="CREATE INDEX",
            details={"index": index_name, "table": table_name, "error": str(e)},
        ) from e


def safe_drop_index(
    index_name: str,
    if_exists: bool = True,
) -> tuple[bool, str]:
    """
    Safely drop an index.

    Args:
        index_name: Name of the index to drop
        if_exists: If True, skip if index doesn't exist

    Returns:
        Tuple of (success, message)
    """
    if if_exists and not index_exists(index_name):
        return True, f"[SKIP] Index '{index_name}' does not exist"

    try:
        sql = f"DROP INDEX {index_name}"
        with get_cursor(commit=True) as cursor:
            cursor.execute(sql)
        return True, f"[OK] Index '{index_name}' dropped"

    except pg_errors.UndefinedObject:
        return True, f"[SKIP] Index '{index_name}' does not exist (race condition)"

    except psycopg2.Error as e:
        raise MigrationError(
            f"Failed to drop index '{index_name}'",
            operation="DROP INDEX",
            details={"index": index_name, "error": str(e)},
        ) from e


def safe_add_constraint(
    table_name: str,
    constraint_name: str,
    constraint_def: str,
    if_not_exists: bool = True,
) -> tuple[bool, str]:
    """
    Safely add a constraint to a table.

    Args:
        table_name: Name of the table
        constraint_name: Name for the constraint
        constraint_def: Constraint definition (e.g., "FOREIGN KEY (x) REFERENCES y(id)")
        if_not_exists: If True, skip if constraint already exists

    Returns:
        Tuple of (success, message)

    Example:
        >>> success, msg = safe_add_constraint(
        ...     "positions",
        ...     "fk_positions_strategy",
        ...     "FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)"
        ... )
    """
    if if_not_exists and constraint_exists(table_name, constraint_name):
        return True, f"[SKIP] Constraint '{constraint_name}' already exists on '{table_name}'"

    try:
        sql = f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} {constraint_def}"
        with get_cursor(commit=True) as cursor:
            cursor.execute(sql)
        return True, f"[OK] Constraint '{constraint_name}' added to '{table_name}'"

    except pg_errors.DuplicateObject:
        return True, f"[SKIP] Constraint '{constraint_name}' already exists (race condition)"

    except pg_errors.ForeignKeyViolation as e:
        return False, (
            f"[ERROR] FK violation when adding constraint '{constraint_name}': {e}\n"
            f"[FIX] Ensure all referenced values exist before adding constraint"
        )

    except pg_errors.UndefinedTable:
        return False, f"[ERROR] Table '{table_name}' does not exist"

    except psycopg2.Error as e:
        raise MigrationError(
            f"Failed to add constraint '{constraint_name}' to '{table_name}'",
            operation="ADD CONSTRAINT",
            details={"table": table_name, "constraint": constraint_name, "error": str(e)},
        ) from e


def safe_drop_constraint(
    table_name: str,
    constraint_name: str,
    if_exists: bool = True,
) -> tuple[bool, str]:
    """
    Safely drop a constraint from a table.

    Args:
        table_name: Name of the table
        constraint_name: Name of the constraint to drop
        if_exists: If True, skip if constraint doesn't exist

    Returns:
        Tuple of (success, message)
    """
    if if_exists and not constraint_exists(table_name, constraint_name):
        return True, f"[SKIP] Constraint '{constraint_name}' does not exist on '{table_name}'"

    try:
        sql = f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}"
        with get_cursor(commit=True) as cursor:
            cursor.execute(sql)
        return True, f"[OK] Constraint '{constraint_name}' dropped from '{table_name}'"

    except pg_errors.UndefinedObject:
        return True, f"[SKIP] Constraint '{constraint_name}' does not exist (race condition)"

    except psycopg2.Error as e:
        raise MigrationError(
            f"Failed to drop constraint '{constraint_name}' from '{table_name}'",
            operation="DROP CONSTRAINT",
            details={"table": table_name, "constraint": constraint_name, "error": str(e)},
        ) from e


# ============================================================================
# Data Migration Helpers
# ============================================================================


def safe_data_migration(
    description: str,
    migration_func: Callable[[], int],
    rollback_func: Callable[[], None] | None = None,
) -> tuple[bool, str, int]:
    """
    Safely execute a data migration with error handling.

    Args:
        description: Human-readable description of the migration
        migration_func: Function that performs the migration, returns rows affected
        rollback_func: Optional function to rollback on failure

    Returns:
        Tuple of (success, message, rows_affected)

    Example:
        >>> def migrate_prices():
        ...     cursor.execute("UPDATE markets SET price = price * 100")
        ...     return cursor.rowcount
        >>>
        >>> success, msg, rows = safe_data_migration(
        ...     "Convert prices to cents",
        ...     migrate_prices
        ... )
    """
    try:
        rows = migration_func()
        return True, f"[OK] {description}: {rows} rows affected", rows

    except pg_errors.ForeignKeyViolation as e:
        if rollback_func:
            try:
                rollback_func()
            except Exception as rollback_err:
                return (
                    False,
                    f"[ERROR] {description} failed AND rollback failed: {e}, {rollback_err}",
                    0,
                )
        return False, f"[ERROR] {description} failed with FK violation: {e}", 0

    except pg_errors.UniqueViolation as e:
        return False, f"[ERROR] {description} failed with unique constraint violation: {e}", 0

    except pg_errors.CheckViolation as e:
        return False, f"[ERROR] {description} failed with check constraint violation: {e}", 0

    except psycopg2.Error as e:
        if rollback_func:
            try:
                rollback_func()
            except Exception:
                pass
        raise MigrationError(
            f"Data migration failed: {description}",
            operation="DATA MIGRATION",
            details={"description": description, "error": str(e)},
        ) from e


# ============================================================================
# Migration Execution Wrapper
# ============================================================================


def run_migration_step(
    step_num: int,
    total_steps: int,
    description: str,
    operation_func: Callable[[], tuple[bool, str]],
) -> bool:
    """
    Execute a single migration step with consistent logging.

    Args:
        step_num: Current step number
        total_steps: Total number of steps
        description: Step description
        operation_func: Function that performs the operation

    Returns:
        True if step succeeded, False otherwise

    Example:
        >>> def create_index():
        ...     return safe_create_index("idx_foo", "bar", "baz")
        >>>
        >>> run_migration_step(1, 5, "Create foo index", create_index)
    """
    print(f"\n[{step_num}/{total_steps}] {description}...")

    try:
        success, message = operation_func()
        print(f"  {message}")
        return success

    except MigrationError as e:
        print(f"  [FAIL] {e.message}")
        if e.details:
            for key, value in e.details.items():
                print(f"         {key}: {value}")
        return False

    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}")
        return False


def verify_prerequisites(checks: list[tuple[str, Callable[[], bool]]]) -> bool:
    """
    Verify all prerequisites before running migration.

    Args:
        checks: List of (description, check_function) tuples

    Returns:
        True if all prerequisites pass, False otherwise

    Example:
        >>> checks = [
        ...     ("Table 'markets' exists", lambda: table_exists("markets")),
        ...     ("Column 'price' exists", lambda: column_exists("markets", "price")),
        ... ]
        >>> if verify_prerequisites(checks):
        ...     run_migration()
    """
    print("\n[PREREQ] Verifying prerequisites...")
    all_passed = True

    for description, check_func in checks:
        try:
            if check_func():
                print(f"  [OK] {description}")
            else:
                print(f"  [FAIL] {description}")
                all_passed = False
        except Exception as e:
            print(f"  [FAIL] {description}: {e}")
            all_passed = False

    return all_passed
