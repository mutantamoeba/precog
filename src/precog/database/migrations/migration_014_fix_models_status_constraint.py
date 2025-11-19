#!/usr/bin/env python3
"""
Migration 014: Fix probability_models Status CHECK Constraint

**Problem:**
The `probability_models_status_check` constraint has mismatched values between database and code.
- Current schema values: 'draft', 'training', 'validating', 'active', 'deprecated'
- Model Manager code values: 'draft', 'testing', 'active', 'deprecated'

The code uses 'testing' as a unified pre-production status, while the schema has separate
'training' and 'validating' stages. This causes CHECK constraint violations in tests.

**Solution:**
1. Drop the old `probability_models_status_check` constraint
2. Create new constraint with values matching Model Manager implementation
3. Align with strategies table pattern: 'draft' → 'testing' → 'active' → 'deprecated'

**Why These Values?**
- `draft` - Model under development, config not finalized
- `testing` - Model in backtesting/validation phase (unified stage)
- `active` - Model approved for production use
- `deprecated` - Model retired, no longer used

**Backwards Compatibility:**
- ⚠️ BREAKING: Any existing rows with 'training' or 'validating' status will FAIL constraint
- Mitigation: No existing data (Phase 1.5 fresh start)
- Future-proof: If you need separate training/validating stages, create new migration

**References:**
- Model Manager _validate_status_transition() method (lines 628-661)
- docs/guides/VERSIONING_GUIDE_V1.0.md (Model Lifecycle section)
- docs/database/DATABASE_SCHEMA_SUMMARY_V1.9.md

**Migration Safe?:** YES (assuming no existing invalid data)
- ✅ Drops old constraint (instant metadata operation)
- ✅ Creates new constraint (instant metadata operation)
- ⚠️ Will fail if existing data violates new constraint

**Estimated Time:** ~100ms (metadata-only operations)

Created: 2025-11-17
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
    Fix probability_models status CHECK constraint.

    Args:
        conn: Database connection

    Educational Note:
        DROP CONSTRAINT and ADD CONSTRAINT are metadata-only operations in PostgreSQL.
        They don't rewrite the table or scan data (unless validating existing rows).
        This makes constraint changes very fast (~1-100ms).
    """
    with conn.cursor() as cur:
        print("Starting Migration 014: Fix probability_models Status CHECK Constraint...")
        print()

        # ==============================================================================
        # probability_models table - Fix status constraint
        # ==============================================================================
        print("[1/2] Dropping old probability_models_status_check constraint...")
        cur.execute("""
            ALTER TABLE probability_models
            DROP CONSTRAINT IF EXISTS probability_models_status_check
        """)
        print("      [OK] Old constraint dropped")

        print("[2/2] Creating new probability_models_status_check constraint...")
        cur.execute("""
            ALTER TABLE probability_models
            ADD CONSTRAINT probability_models_status_check
            CHECK (status IN (
                'draft',        -- Under development
                'testing',      -- In backtesting/validation
                'active',       -- Approved for production
                'deprecated'    -- Retired
            ))
        """)
        print("      [OK] New constraint created with correct values")

        print()
        print("=" * 80)
        print("Migration 014 completed successfully!")
        print("=" * 80)


def rollback_migration(conn):
    """
    Rollback Migration 014: Restore old status_check constraint.

    Args:
        conn: Database connection

    Educational Note:
        Rollback recreates the old constraint with old values. This is safe
        because we're only changing metadata, not data.

        ⚠️ WARNING: Rollback will fail if data violates old constraint!
    """
    with conn.cursor() as cur:
        print("Rolling back Migration 014...")
        print()

        print("[1/2] Dropping new probability_models_status_check constraint...")
        cur.execute("""
            ALTER TABLE probability_models
            DROP CONSTRAINT IF EXISTS probability_models_status_check
        """)
        print("      [OK] New constraint dropped")

        print("[2/2] Recreating old probability_models_status_check constraint...")
        cur.execute("""
            ALTER TABLE probability_models
            ADD CONSTRAINT probability_models_status_check
            CHECK (status IN (
                'draft', 'training', 'validating', 'active', 'deprecated'
            ))
        """)
        print("      [OK] Old constraint recreated")

        print()
        print("=" * 80)
        print("Migration 014 rolled back successfully!")
        print("=" * 80)


def main():
    """Main migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migration 014: Fix probability_models Status CHECK Constraint"
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
