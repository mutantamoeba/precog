#!/usr/bin/env python3
"""
Migration 013: Fix strategies Approach CHECK Constraint

**Problem:**
The `strategies_category_check` constraint has incorrect semantics after Migration 011.
- Current values: 'sports', 'politics', 'entertainment', 'economics', 'weather', 'other'
- Correct values: 'value', 'arbitrage', 'momentum', 'mean_reversion'

The constraint name still references the old column name (category_check) and has wrong
semantic values. Migration 011 renamed the column but didn't update the constraint.

**Solution:**
1. Drop the old `strategies_category_check` constraint
2. Create new `strategies_approach_check` constraint with correct values

**Why These Values?**
- `approach` describes HOW the strategy works (trading methodology)
- Examples: 'value' (exploit mispricing), 'arbitrage' (cross-platform),
  'momentum' (trend following), 'mean_reversion' (reversion to fundamentals)

**Backwards Compatibility:**
- ⚠️ BREAKING: Any existing rows with invalid approach values will FAIL constraint
- Mitigation: No existing data (Phase 1.5 fresh start)
- Future-proof: Add values as needed (ALTER CONSTRAINT not supported, so new migration required)

**References:**
- Migration 011: Standardized category -> approach renaming
- Migration 012: Fixed probability_models approach constraint (same pattern)
- DATABASE_SCHEMA_SUMMARY_V1.9.md: approach field documentation
- ADR-076: Standardize Classification Field Naming

**Migration Safe?:** YES (assuming no existing invalid data)
- ✅ Drops old constraint (instant metadata operation)
- ✅ Creates new constraint (instant metadata operation)
- ⚠️ Will fail if existing data violates new constraint

**Estimated Time:** ~100ms (metadata-only operations)

Created: 2025-11-16
Phase: 1.5 (Foundation Validation)
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_connection():
    """Get database connection from environment variables."""
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "precog_dev")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD")

    if not db_password:
        raise ValueError("DB_PASSWORD environment variable not set")

    return psycopg2.connect(
        host=db_host, port=db_port, database=db_name, user=db_user, password=db_password
    )


def apply_migration(conn):
    """
    Fix strategies approach CHECK constraint.

    Args:
        conn: Database connection

    Educational Note:
        DROP CONSTRAINT and ADD CONSTRAINT are metadata-only operations in PostgreSQL.
        They don't rewrite the table or scan data (unless validating existing rows).
        This makes constraint changes very fast (~1-100ms).
    """
    with conn.cursor() as cur:
        print("Starting Migration 013: Fix Strategies Approach CHECK Constraint...")
        print()

        # ==============================================================================
        # strategies table - Fix approach constraint
        # ==============================================================================
        print("[1/2] Dropping old strategies_category_check constraint...")
        cur.execute("""
            ALTER TABLE strategies
            DROP CONSTRAINT IF EXISTS strategies_category_check
        """)
        print("      [OK] Old constraint dropped")

        print("[2/2] Creating new strategies_approach_check constraint...")
        cur.execute("""
            ALTER TABLE strategies
            ADD CONSTRAINT strategies_approach_check
            CHECK (approach IN (
                'value',            -- Exploit market mispricing
                'arbitrage',        -- Cross-platform arbitrage
                'momentum',         -- Trend following
                'mean_reversion'    -- Reversion to fundamental value
            ))
        """)
        print("      [OK] New constraint created with correct values")

        print()
        print("=" * 80)
        print("Migration 013 completed successfully!")
        print("=" * 80)


def rollback_migration(conn):
    """
    Rollback Migration 013: Restore old category_check constraint.

    Args:
        conn: Database connection

    Educational Note:
        Rollback recreates the old constraint with old values. This is safe
        because we're only changing metadata, not data.

        ⚠️ WARNING: Rollback will fail if data violates old constraint!
    """
    with conn.cursor() as cur:
        print("Rolling back Migration 013...")
        print()

        print("[1/2] Dropping new strategies_approach_check constraint...")
        cur.execute("""
            ALTER TABLE strategies
            DROP CONSTRAINT IF EXISTS strategies_approach_check
        """)
        print("      [OK] New constraint dropped")

        print("[2/2] Recreating old strategies_category_check constraint...")
        cur.execute("""
            ALTER TABLE strategies
            ADD CONSTRAINT strategies_category_check
            CHECK (approach IN (
                'sports', 'politics', 'entertainment',
                'economics', 'weather', 'other'
            ))
        """)
        print("      [OK] Old constraint recreated")

        print()
        print("=" * 80)
        print("Migration 013 rolled back successfully!")
        print("=" * 80)


def main():
    """Main migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migration 013: Fix Strategies Approach CHECK Constraint"
    )
    parser.add_argument("--rollback", action="store_true", help="Rollback this migration")
    args = parser.parse_args()

    try:
        conn = get_connection()
        print(f"Connected to: {conn.info.dbname}@{conn.info.host}:{conn.info.port}")
        print()

        if args.rollback:
            rollback_migration(conn)
        else:
            apply_migration(conn)

        conn.commit()
        print()
        print("Transaction committed.")

    except psycopg2.Error as e:
        print(f"\n[FAIL] Migration failed: {e}")
        if conn:
            conn.rollback()
            print("Transaction rolled back.")
        sys.exit(1)

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
