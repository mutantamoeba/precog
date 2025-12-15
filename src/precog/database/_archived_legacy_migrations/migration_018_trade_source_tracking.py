#!/usr/bin/env python3
"""
Migration 018: trades Table - Add Trade Source Tracking

**Problem:**
Cannot distinguish automated trades (app-executed) from manual trades (Kalshi UI).
Performance analytics require separating automated strategy performance from manual interventions.

**Root Cause:**
trades table lacks source tracking mechanism:
- All trades look identical regardless of origin
- Cannot filter performance reports by trade source
- Manual trade reconciliation requires comparing timestamps (unreliable)

**Solution:**
Add trade source tracking with PostgreSQL ENUM:
1. Create ENUM type: `trade_source_type AS ENUM ('automated', 'manual')`
2. Add column: `trades.trade_source trade_source_type NOT NULL DEFAULT 'automated'`
3. Add index for analytics queries: `idx_trades_source ON trades(trade_source)`
4. Add descriptive comment

**Why ENUM over VARCHAR or BOOLEAN:**
- **ENUM advantages:**
  - Database-enforced validation (only 2 valid values)
  - Storage efficient (1 byte vs 4+ bytes for VARCHAR)
  - Self-documenting schema (valid values visible in schema)
  - Type-safe (prevents typos: 'Automated' vs 'automated')
- **ENUM disadvantages:**
  - Harder to add new values (requires ALTER TYPE)
  - Not as flexible as VARCHAR for extensibility
- **Decision:** Use ENUM - trade source is stable domain (unlikely to expand beyond automated/manual)

**Benefits:**
- Separate automated strategy performance from manual interventions
- Support reconciliation workflow (download Kalshi trades, mark manual trades)
- Enable analytics queries: "What's ROI of automated vs manual trades?"
- Performance attribution analysis (which strategies generate profits)

**Example Queries:**
```sql
-- Get automated trade performance only
SELECT strategy_id, COUNT(*), AVG(realized_pnl)
FROM trades
WHERE trade_source = 'automated'
GROUP BY strategy_id;

-- Find manual trades for reconciliation
SELECT trade_id, executed_at, quantity, price
FROM trades
WHERE trade_source = 'manual'
ORDER BY executed_at DESC;
```

**Migration Safe?:** YES
- ✅ Non-breaking (DEFAULT 'automated' for existing rows)
- ✅ Rollback script included
- ✅ Verification function validates changes
- ✅ No data loss (column addition only)

**References:**
- ADR-092: Trade Source Tracking and Manual Trade Reconciliation
- ADR-091: Explicit Columns for Trade/Position Attribution
- docs/analysis/SCHEMA_ANALYSIS_2025-11-21.md (Gap #4: Trade Source Tracking)

**Related Migrations:**
- Migration 019: Trade attribution enrichment (calculated_probability, market_price, edge_value)
- Migration 020: Position attribution (strategy_id, model_id, probabilities)

**Estimated Time:** ~1 second (ENUM creation + column addition)

Created: 2025-11-21
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
    Apply migration: Add trade source tracking to trades table.

    Args:
        conn: Database connection

    Educational Note:
        PostgreSQL ENUMs provide type-safe domain constraints at the database level.
        Unlike CHECK constraints with VARCHAR, ENUMs:
        - Are visible in schema (SELECT unnest(enum_range(NULL::trade_source_type)))
        - Prevent typos ('Automated' vs 'automated')
        - Use minimal storage (1 byte vs 4+ bytes for VARCHAR)
        - Are self-documenting (valid values encoded in type definition)

        Trade-off: ENUMs are harder to extend (ALTER TYPE required) vs VARCHAR
        (just update CHECK constraint). For stable domains like trade_source,
        ENUMs are the better choice.
    """
    with conn.cursor() as cur:
        print("Starting Migration 018: Trade Source Tracking...")
        print()

        # =============================================================================
        # Step 1: Create ENUM type for trade source
        # =============================================================================
        print("[1/4] Creating ENUM type (trade_source_type)...")
        cur.execute("""
            DO $$ BEGIN
                CREATE TYPE trade_source_type AS ENUM ('automated', 'manual');
            EXCEPTION
                WHEN duplicate_object THEN
                    RAISE NOTICE 'ENUM type trade_source_type already exists, skipping';
            END $$;
        """)
        print("       [OK] ENUM type created (automated, manual)")
        print()

        # =============================================================================
        # Step 2: Add trade_source column with DEFAULT
        # =============================================================================
        print("[2/4] Adding trade_source column to trades table...")
        cur.execute("""
            ALTER TABLE trades
            ADD COLUMN IF NOT EXISTS trade_source trade_source_type NOT NULL DEFAULT 'automated'
        """)
        print("       [OK] Column added (DEFAULT 'automated' for existing rows)")
        print()

        # =============================================================================
        # Step 3: Add index for analytics queries
        # =============================================================================
        print("[3/4] Creating index on trade_source for analytics...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_source
            ON trades(trade_source)
        """)
        print("       [OK] Index created (supports filtering by source)")
        print()

        # =============================================================================
        # Step 4: Add descriptive comment
        # =============================================================================
        print("[4/4] Adding column comment...")
        cur.execute("""
            COMMENT ON COLUMN trades.trade_source IS 'Trade origin: automated (app-executed) or manual (Kalshi UI)'
        """)
        print("       [OK] Comment added")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 018 applied successfully!")
        print()
        print("Summary:")
        print("  - ENUM type created: trade_source_type ('automated', 'manual')")
        print("  - Column added: trades.trade_source (NOT NULL, DEFAULT 'automated')")
        print("  - Index created: idx_trades_source (supports analytics queries)")
        print("  - All existing rows default to 'automated'")
        print()
        print("Usage:")
        print("  - Automated trades: trade_source = 'automated' (default)")
        print("  - Manual trades: trade_source = 'manual' (set during reconciliation)")
        print()
        print("Next steps:")
        print("  1. Run Migration 019 (trade attribution enrichment)")
        print("  2. Update CRUD operations (create_trade with trade_source parameter)")
        print("  3. Implement Kalshi trade reconciliation workflow")


def rollback_migration(conn):
    """
    Rollback migration: Remove trade source tracking.

    Args:
        conn: Database connection

    Warning:
        This rollback drops the trade_source column and ENUM type.
        Safe if no queries/code depend on this column yet.
    """
    with conn.cursor() as cur:
        print("Rolling back Migration 018...")
        print()

        # Drop index
        print("[1/3] Dropping index idx_trades_source...")
        cur.execute("""
            DROP INDEX IF EXISTS idx_trades_source
        """)
        print("      [OK] Index dropped")
        print()

        # Drop column (must happen before dropping ENUM type)
        print("[2/3] Dropping trade_source column...")
        cur.execute("""
            ALTER TABLE trades
            DROP COLUMN IF EXISTS trade_source
        """)
        print("      [OK] Column dropped")
        print()

        # Drop ENUM type
        print("[3/3] Dropping ENUM type trade_source_type...")
        cur.execute("""
            DROP TYPE IF EXISTS trade_source_type
        """)
        print("      [OK] ENUM type dropped")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 018 rolled back successfully!")


def verify_migration(conn):
    """
    Verify migration was applied correctly.

    Args:
        conn: Database connection

    Returns:
        True if verification passed, False otherwise
    """
    with conn.cursor() as cur:
        print("Verifying Migration 018...")
        print()

        # Check ENUM type exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'trade_source_type'
            )
        """)
        enum_exists = cur.fetchone()[0]

        # Get ENUM values
        if enum_exists:
            cur.execute("""
                SELECT unnest(enum_range(NULL::trade_source_type))::text
            """)
            enum_values = sorted([row[0] for row in cur.fetchall()])
        else:
            enum_values = []

        # Check trades.trade_source column
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'trades' AND column_name = 'trade_source'
        """)
        column_info = cur.fetchone()

        # Check index exists
        cur.execute("""
            SELECT indexdef
            FROM pg_indexes
            WHERE tablename = 'trades' AND indexname = 'idx_trades_source'
        """)
        index_info = cur.fetchone()

        # Verify structure
        errors = []

        # Check ENUM type
        if not enum_exists:
            errors.append("[FAIL] ENUM type trade_source_type not found")
        elif enum_values != ["automated", "manual"]:
            errors.append(
                f"[FAIL] ENUM values should be ['automated', 'manual'], got {enum_values}"
            )

        # Check column
        if not column_info:
            errors.append("[FAIL] trades.trade_source column not found")
        else:
            _col_name, data_type, is_nullable, column_default = column_info
            if data_type != "USER-DEFINED":
                errors.append(f"[FAIL] trade_source should be USER-DEFINED (ENUM), got {data_type}")
            if is_nullable != "NO":
                errors.append("[FAIL] trade_source should be NOT NULL")
            if "'automated'" not in (column_default or ""):
                errors.append(
                    f"[FAIL] trade_source should DEFAULT 'automated', got {column_default}"
                )

        # Check index
        if not index_info:
            errors.append("[FAIL] Index idx_trades_source not found")

        if errors:
            print("Verification FAILED:")
            for error in errors:
                print(f"  {error}")
            return False

        print("[SUCCESS] Verification passed!")
        print("  [OK] ENUM type trade_source_type exists with values: ['automated', 'manual']")
        print(
            "  [OK] trades.trade_source column exists (trade_source_type NOT NULL DEFAULT 'automated')"
        )
        print("  [OK] Index idx_trades_source created")
        print()
        print("Trade source tracking is now enabled!")
        return True


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Migration 018: Trade Source Tracking")
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
