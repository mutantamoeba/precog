#!/usr/bin/env python3
"""
Migration 011: Standardize Classification Fields Across Models and Strategies

**Problem:**
Three-way mismatch between documentation, database, and manager code:
- Documentation: model_type/sport, strategy_type/sport
- Database: category/subcategory
- Manager Code: Expects model_type/sport, strategy_type/sport

**Solution:**
Standardize on approach/domain (semantically superior to all options):
- approach: HOW the model/strategy works (elo, regression, value, arbitrage)
- domain: WHICH markets it applies to (nfl, elections, economics, NULL=multi-domain)

**Changes:**
1. Rename category → approach in probability_models and strategies
2. Rename subcategory → domain in probability_models and strategies
3. Add description TEXT to both tables (audit/documentation field)
4. Add created_by VARCHAR to both tables (audit trail)

**Why approach/domain?**
- Consistent meaning across tables (unlike category which means different things)
- Future-proof for Phase 2+ (elections, economics, etc.)
- More descriptive than generic "type" or "category"
- "domain" more precise than "market" (which refers to individual betting markets)

**Backwards Compatibility:**
- Field renames are transparent to application (SQL queries updated)
- New fields are nullable (won't break existing data)
- No data loss (rename preserves all values)

**References:**
- ADR-076: Standardize Classification Field Naming (approach/domain)
- DATABASE_SCHEMA_SUMMARY_V1.9.md (updated schema documentation)
- Phase 1.5: Schema Standardization

**Migration Safe?:** YES
- ✅ Renames preserve data
- ✅ New columns nullable (no NOT NULL constraint)
- ✅ No foreign key dependencies on renamed columns
- ✅ Rollback script included

**Estimated Time:** ~2 seconds (rename operations are instant, no data copying)

Created: 2025-11-16
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
    Apply migration: Rename category/subcategory → approach/domain, add description/created_by.

    Args:
        conn: Database connection

    Educational Note:
        ALTER TABLE ... RENAME COLUMN is a metadata-only operation in PostgreSQL.
        It does NOT rewrite the table or move data - just updates the catalog.
        This makes it extremely fast (~1ms) even on large tables.

        ADD COLUMN with no default value is also metadata-only (fast).
    """
    with conn.cursor() as cur:
        print("Starting Migration 011: Standardize Classification Fields...")
        print()

        # ==============================================================================
        # probability_models table
        # ==============================================================================
        print("[1/8] Renaming probability_models.category -> approach...")
        cur.execute("""
            ALTER TABLE probability_models
            RENAME COLUMN category TO approach
        """)
        print("      [OK] Renamed successfully")

        print("[2/8] Renaming probability_models.subcategory -> domain...")
        cur.execute("""
            ALTER TABLE probability_models
            RENAME COLUMN subcategory TO domain
        """)
        print("      [OK] Renamed successfully")

        print("[3/8] Adding probability_models.description (TEXT, nullable)...")
        cur.execute("""
            ALTER TABLE probability_models
            ADD COLUMN IF NOT EXISTS description TEXT
        """)
        print("      [OK] Column added")

        print("[4/8] Adding probability_models.created_by (VARCHAR, nullable)...")
        cur.execute("""
            ALTER TABLE probability_models
            ADD COLUMN IF NOT EXISTS created_by VARCHAR
        """)
        print("      [OK] Column added")
        print()

        # ==============================================================================
        # strategies table
        # ==============================================================================
        print("[5/8] Renaming strategies.category -> approach...")
        cur.execute("""
            ALTER TABLE strategies
            RENAME COLUMN category TO approach
        """)
        print("      [OK] Renamed successfully")

        print("[6/8] Renaming strategies.subcategory -> domain...")
        cur.execute("""
            ALTER TABLE strategies
            RENAME COLUMN subcategory TO domain
        """)
        print("      [OK] Renamed successfully")

        print("[7/8] Adding strategies.description (TEXT, nullable)...")
        cur.execute("""
            ALTER TABLE strategies
            ADD COLUMN IF NOT EXISTS description TEXT
        """)
        print("      [OK] Column added")

        print("[8/8] Adding strategies.created_by (VARCHAR, nullable)...")
        cur.execute("""
            ALTER TABLE strategies
            ADD COLUMN IF NOT EXISTS created_by VARCHAR
        """)
        print("      [OK] Column added")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 011 applied successfully!")
        print()
        print("Summary:")
        print("  - Renamed: category -> approach (both tables)")
        print("  - Renamed: subcategory -> domain (both tables)")
        print("  - Added: description TEXT (both tables)")
        print("  - Added: created_by VARCHAR (both tables)")


def rollback_migration(conn):
    """
    Rollback migration: Rename approach/domain → category/subcategory, drop description/created_by.

    Args:
        conn: Database connection

    Educational Note:
        Rollback is safe ONLY if no data has been written to new columns.
        If description/created_by have been populated, rolling back loses that data!
    """
    with conn.cursor() as cur:
        print("Rolling back Migration 011...")
        print()

        # ==============================================================================
        # probability_models table
        # ==============================================================================
        print("[1/8] Renaming probability_models.approach -> category...")
        cur.execute("""
            ALTER TABLE probability_models
            RENAME COLUMN approach TO category
        """)
        print("      [OK] Renamed successfully")

        print("[2/8] Renaming probability_models.domain -> subcategory...")
        cur.execute("""
            ALTER TABLE probability_models
            RENAME COLUMN domain TO subcategory
        """)
        print("      [OK] Renamed successfully")

        print("[3/8] Dropping probability_models.description...")
        cur.execute("""
            ALTER TABLE probability_models
            DROP COLUMN IF EXISTS description
        """)
        print("      [OK] Column dropped")

        print("[4/8] Dropping probability_models.created_by...")
        cur.execute("""
            ALTER TABLE probability_models
            DROP COLUMN IF EXISTS created_by
        """)
        print("      [OK] Column dropped")
        print()

        # ==============================================================================
        # strategies table
        # ==============================================================================
        print("[5/8] Renaming strategies.approach -> category...")
        cur.execute("""
            ALTER TABLE strategies
            RENAME COLUMN approach TO category
        """)
        print("      [OK] Renamed successfully")

        print("[6/8] Renaming strategies.domain -> subcategory...")
        cur.execute("""
            ALTER TABLE strategies
            RENAME COLUMN domain TO subcategory
        """)
        print("      [OK] Renamed successfully")

        print("[7/8] Dropping strategies.description...")
        cur.execute("""
            ALTER TABLE strategies
            DROP COLUMN IF EXISTS description
        """)
        print("      [OK] Column dropped")

        print("[8/8] Dropping strategies.created_by...")
        cur.execute("""
            ALTER TABLE strategies
            DROP COLUMN IF EXISTS created_by
        """)
        print("      [OK] Column dropped")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 011 rolled back successfully!")


def verify_migration(conn):
    """
    Verify migration was applied correctly.

    Args:
        conn: Database connection

    Returns:
        True if verification passed, False otherwise
    """
    with conn.cursor() as cur:
        print("Verifying Migration 011...")
        print()

        # Check probability_models columns
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'probability_models' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        pm_columns = [row[0] for row in cur.fetchall()]

        # Check strategies columns
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'strategies' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        strat_columns = [row[0] for row in cur.fetchall()]

        # Verify renames
        errors = []

        # probability_models checks
        if "approach" not in pm_columns:
            errors.append("[FAIL] probability_models.approach not found")
        if "domain" not in pm_columns:
            errors.append("[FAIL] probability_models.domain not found")
        if "description" not in pm_columns:
            errors.append("[FAIL] probability_models.description not found")
        if "created_by" not in pm_columns:
            errors.append("[FAIL] probability_models.created_by not found")
        if "category" in pm_columns:
            errors.append("[FAIL] probability_models.category still exists (should be renamed)")
        if "subcategory" in pm_columns:
            errors.append("[FAIL] probability_models.subcategory still exists (should be renamed)")

        # strategies checks
        if "approach" not in strat_columns:
            errors.append("[FAIL] strategies.approach not found")
        if "domain" not in strat_columns:
            errors.append("[FAIL] strategies.domain not found")
        if "description" not in strat_columns:
            errors.append("[FAIL] strategies.description not found")
        if "created_by" not in strat_columns:
            errors.append("[FAIL] strategies.created_by not found")
        if "category" in strat_columns:
            errors.append("[FAIL] strategies.category still exists (should be renamed)")
        if "subcategory" in strat_columns:
            errors.append("[FAIL] strategies.subcategory still exists (should be renamed)")

        if errors:
            print("Verification FAILED:")
            for error in errors:
                print(f"  {error}")
            return False
        print("[SUCCESS] Verification passed!")
        print("  - probability_models: approach, domain, description, created_by present")
        print("  - strategies: approach, domain, description, created_by present")
        print("  - Old column names (category, subcategory) removed")
        return True


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Migration 011: Standardize Classification Fields")
    parser.add_argument(
        "--rollback", action="store_true", help="Rollback migration instead of applying"
    )
    parser.add_argument("--verify-only", action="store_true", help="Only verify migration")

    args = parser.parse_args()

    try:
        conn = get_connection()

        if args.verify_only:
            success = verify_migration(conn)
            sys.exit(0 if success else 1)
        elif args.rollback:
            rollback_migration(conn)
        else:
            apply_migration(conn)
            verify_migration(conn)

        conn.close()
        sys.exit(0)

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
