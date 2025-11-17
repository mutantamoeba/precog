#!/usr/bin/env python3
"""
Database Schema Validation Script

Validates that the actual PostgreSQL database schema matches the documented schema
in DATABASE_SCHEMA_SUMMARY_V1.8.md. Detects column mismatches, missing columns,
extra columns, and type differences.

Usage:
    python scripts/validate_schema.py                    # Validate all tables
    python scripts/validate_schema.py --table markets    # Validate specific table
    python scripts/validate_schema.py --ci               # CI mode (exit 1 on mismatch)

Exit Codes:
    0: Schema matches documentation
    1: Schema mismatches found (or database connection failed)

Educational Note:
    This script prevents "schema drift" where the actual database structure diverges
    from documentation. Schema drift causes:
    - Runtime errors when code expects columns that don't exist
    - Broken migrations when schema state is unknown
    - Developer confusion when docs don't match reality
    - Integration test failures when test database ≠ production database

    By running this in CI/CD, we catch schema drift BEFORE code reaches production.

Reference: docs/utility/PHASE_1_DEFERRED_TASKS_V1.0.md - DEF-P1-008
Related ADR: ADR-008 (Database Connection Strategy)
Related REQ: REQ-DB-001 (PostgreSQL 15+ Required)
"""

import argparse
import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor


def get_database_connection() -> psycopg2.extensions.connection:
    """
    Get database connection from environment variable.

    Returns:
        Database connection object

    Raises:
        EnvironmentError: If DATABASE_URL not set
        psycopg2.Error: If connection fails

    Educational Note:
        Always load connection strings from environment variables, NEVER hardcode.
        This allows different connections for dev/test/prod environments without
        code changes.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise OSError(
            "DATABASE_URL environment variable not set. "
            "Example: postgresql://user:pass@localhost:5432/precog"
        )

    try:
        return psycopg2.connect(database_url)
    except psycopg2.Error as e:
        print(f"[ERROR] Failed to connect to database: {e}", file=sys.stderr)
        raise


def get_actual_schema(table_name: str, conn: psycopg2.extensions.connection) -> dict[str, str]:
    """
    Query actual database schema for a table.

    Args:
        table_name: Name of table to query
        conn: Database connection

    Returns:
        Dictionary mapping column_name → data_type
        Example: {"model_id": "integer", "model_name": "character varying"}

    Educational Note:
        PostgreSQL's information_schema.columns is the ANSI SQL standard way to
        query schema metadata. It's portable across PostgreSQL versions and provides
        normalized type names.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = %s
              AND table_schema = 'public'
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        rows = cur.fetchall()

    if not rows:
        raise ValueError(f"Table '{table_name}' not found in database")

    # Build schema dictionary with normalized type names
    schema = {}
    for row in rows:
        col_name = row["column_name"]
        data_type = row["data_type"]

        # Normalize VARCHAR/CHAR types with length
        if data_type in ("character varying", "character"):
            if row["character_maximum_length"]:
                data_type = f"{data_type}({row['character_maximum_length']})"

        # Normalize NUMERIC/DECIMAL types with precision/scale
        elif data_type == "numeric" and row["numeric_precision"] and row["numeric_scale"]:
            data_type = f"numeric({row['numeric_precision']},{row['numeric_scale']})"

        schema[col_name] = data_type

    return schema


def get_documented_schema(table_name: str) -> dict[str, str]:
    """
    Get documented schema for a table from hardcoded definitions.

    Args:
        table_name: Name of table

    Returns:
        Dictionary mapping column_name → data_type

    Raises:
        ValueError: If table not found in documented schemas

    Educational Note:
        For now, we hardcode the documented schemas. In the future (Phase 2+),
        we could parse DATABASE_SCHEMA_SUMMARY_V1.8.md directly, but that adds
        complexity (Markdown parsing, SQL DDL parsing). Start simple, enhance later.
    """
    # TODO (Phase 2+): Parse DATABASE_SCHEMA_SUMMARY_V1.8.md instead of hardcoding
    # For now, hardcode the most critical tables for validation

    documented_schemas = {
        "probability_models": {
            "model_id": "integer",  # SERIAL → integer in information_schema
            "model_name": "character varying",
            "model_version": "character varying",
            "approach": "character varying",  # HOW the model works (elo, regression, value)
            "domain": "character varying",  # WHICH markets (nfl, elections, NULL=multi-domain)
            "config": "jsonb",
            "training_start_date": "date",
            "training_end_date": "date",
            "training_sample_size": "integer",
            "status": "character varying",
            "activated_at": "timestamp without time zone",
            "deactivated_at": "timestamp without time zone",
            "notes": "text",
            "validation_accuracy": "numeric",
            "validation_calibration": "numeric",
            "validation_sample_size": "integer",
            "created_at": "timestamp without time zone",
            "description": "text",
            "created_by": "character varying",
        },
        "strategies": {
            "strategy_id": "integer",
            "platform_id": "character varying",
            "strategy_name": "character varying",
            "strategy_version": "character varying",
            "approach": "character varying",  # HOW the strategy works (value, arbitrage, momentum)
            "domain": "character varying",  # WHICH markets (nfl, elections, NULL=multi-domain)
            "config": "jsonb",
            "status": "character varying",
            "activated_at": "timestamp without time zone",
            "deactivated_at": "timestamp without time zone",
            "notes": "text",
            "paper_trades_count": "integer",
            "paper_roi": "numeric",
            "live_trades_count": "integer",
            "live_roi": "numeric",
            "created_at": "timestamp without time zone",
            "updated_at": "timestamp without time zone",
            "description": "text",
            "created_by": "character varying",
        },
        # TODO: Add other critical tables (markets, positions, trades, etc.)
    }

    if table_name not in documented_schemas:
        raise ValueError(
            f"Table '{table_name}' not found in documented schemas. "
            f"Available tables: {', '.join(documented_schemas.keys())}"
        )

    return documented_schemas[table_name]


def compare_schemas(
    table_name: str, actual: dict[str, str], documented: dict[str, str]
) -> tuple[bool, list[str]]:
    """
    Compare actual vs. documented schema and report mismatches.

    Args:
        table_name: Name of table being compared
        actual: Actual database schema
        documented: Documented schema

    Returns:
        Tuple of (is_match: bool, errors: list[str])

    Educational Note:
        Three types of mismatches to detect:
        1. **Column name mismatch**: Database has "category" but docs say "model_type"
        2. **Missing columns**: Docs define column but it's not in database
        3. **Extra columns**: Database has column not documented (may be OK if intentional)

        We report all three types because each has different implications:
        - Name mismatch = CRITICAL (code will fail)
        - Missing column = CRITICAL (code will fail)
        - Extra column = WARNING (may be intentional addition not yet documented)
    """
    errors = []
    is_match = True

    # Check for missing columns (in docs but not in database)
    missing_columns = set(documented.keys()) - set(actual.keys())
    if missing_columns:
        is_match = False
        for col in sorted(missing_columns):
            errors.append(f"[MISSING] Column '{col}' documented but not found in database")

    # Check for extra columns (in database but not in docs)
    extra_columns = set(actual.keys()) - set(documented.keys())
    if extra_columns:
        is_match = False
        for col in sorted(extra_columns):
            errors.append(f"[EXTRA] Column '{col}' found in database but not documented")

    # Check for type mismatches (column exists but wrong type)
    common_columns = set(actual.keys()) & set(documented.keys())
    for col in sorted(common_columns):
        if actual[col] != documented[col]:
            is_match = False
            errors.append(
                f"[TYPE MISMATCH] Column '{col}': "
                f"Database has '{actual[col]}' but docs say '{documented[col]}'"
            )

    return is_match, errors


def validate_table(
    table_name: str, conn: psycopg2.extensions.connection, ci_mode: bool = False
) -> bool:
    """
    Validate a single table's schema.

    Args:
        table_name: Name of table to validate
        conn: Database connection
        ci_mode: If True, print terse output for CI (otherwise verbose)

    Returns:
        True if schema matches, False otherwise

    Educational Note:
        CI mode provides machine-readable output that CI/CD systems can parse.
        Human-friendly mode provides detailed explanations for developers.
        This "dual mode" pattern is common in validation scripts.
    """
    try:
        actual = get_actual_schema(table_name, conn)
        documented = get_documented_schema(table_name)
    except ValueError as e:
        print(f"[ERROR] {table_name}: {e}", file=sys.stderr)
        return False

    is_match, errors = compare_schemas(table_name, actual, documented)

    if is_match:
        if not ci_mode:
            print(f"[OK] {table_name}: Schema matches documentation ({len(actual)} columns)")
        return True
    print(f"[FAIL] {table_name}: Schema mismatch ({len(errors)} issues)", file=sys.stderr)
    for error in errors:
        print(f"  {error}", file=sys.stderr)
    return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate database schema against documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_schema.py                    # Validate all tables
  python scripts/validate_schema.py --table markets    # Validate specific table
  python scripts/validate_schema.py --ci               # CI mode (exit 1 on mismatch)

Exit Codes:
  0: All tables match documentation
  1: Schema mismatches found (or connection failed)
        """,
    )
    parser.add_argument(
        "--table", help="Validate specific table (otherwise validate all documented tables)"
    )
    parser.add_argument(
        "--ci", action="store_true", help="CI mode: Terse output, exit 1 on any mismatch"
    )

    args = parser.parse_args()

    # Get database connection
    try:
        conn = get_database_connection()
    except (OSError, psycopg2.Error) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    try:
        # Determine which tables to validate
        # Validate all documented tables if no specific table specified
        tables_to_validate = [args.table] if args.table else ["probability_models", "strategies"]
        # TODO (Phase 2+): Add all other critical tables

        # Validate each table
        all_pass = True
        for table in tables_to_validate:
            passed = validate_table(table, conn, ci_mode=args.ci)
            if not passed:
                all_pass = False

        # Exit with appropriate code
        if all_pass:
            if not args.ci:
                print(f"\n[SUCCESS] All {len(tables_to_validate)} tables match documentation")
            sys.exit(0)
        else:
            if not args.ci:
                print("\n[FAILURE] Schema validation failed", file=sys.stderr)
            sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
