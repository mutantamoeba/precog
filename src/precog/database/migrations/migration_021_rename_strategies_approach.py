#!/usr/bin/env python3
"""
Migration 021: Rename strategies.approach -> strategies.strategy_type

**Rationale:**
- Terminology clarity: "approach" is ambiguous (used in both strategies and probability_models)
- Domain-specific naming: strategy_type is explicit and self-documenting
- Prevents confusion: strategies.strategy_type vs probability_models.model_class

**Schema Change:**
- Column rename: strategies.approach -> strategies.strategy_type
- CHECK constraint rename: strategies_approach_check -> strategies_strategy_type_check
- Index rename (if exists): idx_strategies_approach -> idx_strategies_strategy_type

**Migration Type:** Schema refactoring (non-breaking if done atomically)

**Related Migrations:**
- Migration 013: Created strategies.approach column (category -> approach)
- Migration 022: Renames probability_models.approach -> model_class

**Reference:**
- Pattern 16: Schema-Code Alignment (avoid backward compatibility tech debt)
- User request 2025-11-21: "rename approach to domain-specific terms"

Created: 2025-11-21
Author: Claude Code
"""

import os

import psycopg2


def apply_migration(connection_string: str | None = None) -> None:
    """
    Apply migration: Rename strategies.approach -> strategies.strategy_type

    Args:
        connection_string: PostgreSQL connection string (defaults to DATABASE_URL env var)
    """
    conn_str = connection_string or os.getenv("DATABASE_URL")
    if not conn_str:
        raise ValueError("DATABASE_URL environment variable not set")

    conn = psycopg2.connect(conn_str)
    conn.autocommit = False  # Use transaction

    try:
        with conn.cursor() as cur:
            print("Starting Migration 021: Rename strategies.approach -> strategy_type")

            # Step 1: Rename column
            print("  [1/3] Renaming column strategies.approach -> strategy_type...")
            cur.execute("""
                ALTER TABLE strategies
                RENAME COLUMN approach TO strategy_type
            """)

            # Step 2: Rename CHECK constraint
            print("  [2/3] Renaming CHECK constraint...")
            cur.execute("""
                ALTER TABLE strategies
                RENAME CONSTRAINT strategies_approach_check TO strategies_strategy_type_check
            """)

            # Step 3: Rename index (if exists)
            print("  [3/3] Renaming index (if exists)...")
            # Check if index exists
            cur.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'strategies'
                  AND indexname = 'idx_strategies_approach'
            """)
            if cur.fetchone():
                cur.execute("""
                    ALTER INDEX idx_strategies_approach
                    RENAME TO idx_strategies_strategy_type
                """)
                print("      [OK] Index renamed")
            else:
                print("      - No index to rename (idx_strategies_approach not found)")

            # Commit transaction
            conn.commit()
            print("[OK] Migration 021 applied successfully")

            # Verification
            print("\nVerification:")
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'strategies'
                  AND column_name IN ('strategy_type', 'approach')
                ORDER BY column_name
            """)
            columns = cur.fetchall()
            for col_name, col_type in columns:
                print(f"  - {col_name}: {col_type}")

            if not any(col[0] == "strategy_type" for col in columns):
                raise ValueError("VERIFICATION FAILED: strategy_type column not found!")
            if any(col[0] == "approach" for col in columns):
                raise ValueError("VERIFICATION FAILED: approach column still exists!")

            print("  [OK] Verification passed")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Migration 021 failed: {e}")
        raise
    finally:
        conn.close()


def rollback_migration(connection_string: str | None = None) -> None:
    """
    Rollback migration: Rename strategies.strategy_type -> strategies.approach

    Args:
        connection_string: PostgreSQL connection string
    """
    conn_str = connection_string or os.getenv("DATABASE_URL")
    if not conn_str:
        raise ValueError("DATABASE_URL environment variable not set")

    conn = psycopg2.connect(conn_str)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            print("Rolling back Migration 021: Rename strategy_type -> approach")

            cur.execute("ALTER TABLE strategies RENAME COLUMN strategy_type TO approach")
            cur.execute(
                "ALTER TABLE strategies RENAME CONSTRAINT strategies_strategy_type_check TO strategies_approach_check"
            )

            # Rename index if exists
            cur.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'strategies'
                  AND indexname = 'idx_strategies_strategy_type'
            """)
            if cur.fetchone():
                cur.execute(
                    "ALTER INDEX idx_strategies_strategy_type RENAME TO idx_strategies_approach"
                )

            conn.commit()
            print("[OK] Migration 021 rolled back successfully")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Rollback failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback_migration()
    else:
        apply_migration()
