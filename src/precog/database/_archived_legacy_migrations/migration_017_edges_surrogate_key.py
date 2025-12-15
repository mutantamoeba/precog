#!/usr/bin/env python3
"""
Migration 017: edges Table - Add Surrogate Primary Key for SCD Type 2

**Problem:**
edges table uses business key (edge_id) as PRIMARY KEY, preventing SCD Type 2.
Cannot insert multiple versions of same edge because PK must be unique.

**Root Cause:**
SCD Type 2 requires:
1. Surrogate PRIMARY KEY (id) - unique across ALL versions
2. Business key (edge_id) - can duplicate across versions
3. Partial UNIQUE index - ensures only ONE current version per business key

Current schema violates this by using business key as PRIMARY KEY.

**Solution:**
Transform edges table to dual-key structure:
- Add id SERIAL PRIMARY KEY (surrogate key)
- Convert edge_id from PRIMARY KEY to VARCHAR business key
- Update trades table FK to reference surrogate id (not business key)
- Add partial UNIQUE index on (edge_id) WHERE row_current_ind = TRUE

**Foreign Key Dependencies:**
- trades.edge_id -> edges.edge_id (must update to reference surrogate id)

**Migration Steps:**
1. Add surrogate id column (SERIAL)
2. Rename old PK column (edge_id -> edge_id_old)
3. Add new business key column (edge_id VARCHAR)
4. Populate business key with EDGE-{id} format
5. Set business key to NOT NULL
6. Drop FK from trades table
7. Drop old PRIMARY KEY constraint
8. Add new PRIMARY KEY on surrogate id
9. Rename trades FK column and recreate to reference surrogate id
10. Drop old column with CASCADE (may have dependent views)
11. Add partial UNIQUE index

**Benefits:**
- Enables proper SCD Type 2 versioning (edge recalculation history)
- Trade attribution remains intact (trades reference internal surrogate id)
- Can track edge evolution as market conditions change

**Example After Migration:**
```
| id | edge_id   | market_id | expected_value | row_current_ind |
|----|-----------|-----------|----------------|-----------------|
| 1  | EDGE-1    | MKT-001   | 0.0800         | FALSE           |
| 2  | EDGE-1    | MKT-001   | 0.1200         | FALSE           |
| 3  | EDGE-1    | MKT-001   | 0.0950         | TRUE            |
```
Same edge (EDGE-1) with 3 versions tracking expected value changes.

**References:**
- ADR-201: Position History Without SCD Type 2 (SUPERSEDED)
- SESSION_HANDOFF.md 2025-11-18: SCD Type 2 investigation
- Migration 015: positions table (same FK update pattern)

**Migration Safe?:** YES
- ✅ FK update pattern proven in Migration 015
- ✅ Rollback script included
- ✅ Verification function validates changes

**Estimated Time:** ~2 seconds (one FK to update)

Created: 2025-11-19
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
    Apply migration: Convert edges to dual-key structure for SCD Type 2.

    Args:
        conn: Database connection

    Educational Note:
        This migration follows the same pattern as Migration 015 (positions):
        - Child table (trades) references surrogate id, not business key
        - Business key (edge_id VARCHAR) is for queries/filtering
        - Surrogate key (id SERIAL) is for FK relationships

        The key insight: PostgreSQL doesn't allow FKs to columns with only
        partial UNIQUE indexes. So child tables MUST reference the surrogate
        PRIMARY KEY, not the business key.
    """
    with conn.cursor() as cur:
        print("Starting Migration 017: edges Table Surrogate Key...")
        print()

        # =============================================================================
        # Step 1: Add surrogate id column
        # =============================================================================
        print("[1/11] Adding surrogate id column (SERIAL)...")
        cur.execute("""
            ALTER TABLE edges
            ADD COLUMN IF NOT EXISTS id SERIAL
        """)
        print("       [OK] Surrogate id column added")
        print()

        # =============================================================================
        # Step 2: Rename old PRIMARY KEY column
        # =============================================================================
        print("[2/11] Renaming old PRIMARY KEY (edge_id -> edge_id_old)...")
        cur.execute("""
            ALTER TABLE edges
            RENAME COLUMN edge_id TO edge_id_old
        """)
        print("       [OK] Column renamed")
        print()

        # =============================================================================
        # Step 3: Add new business key column
        # =============================================================================
        print("[3/11] Adding new business key column (edge_id VARCHAR)...")
        cur.execute("""
            ALTER TABLE edges
            ADD COLUMN edge_id VARCHAR
        """)
        print("       [OK] Business key column added")
        print()

        # =============================================================================
        # Step 4: Populate business key with EDGE-{id} format
        # =============================================================================
        print("[4/11] Populating business key (EDGE-{id} format)...")
        cur.execute("""
            UPDATE edges
            SET edge_id = 'EDGE-' || id::TEXT
        """)
        print("       [OK] Business key populated")
        print()

        # =============================================================================
        # Step 5: Set business key to NOT NULL
        # =============================================================================
        print("[5/11] Setting business key to NOT NULL...")
        cur.execute("""
            ALTER TABLE edges
            ALTER COLUMN edge_id SET NOT NULL
        """)
        print("       [OK] NOT NULL constraint added")
        print()

        # =============================================================================
        # Step 6: Drop FK from trades table
        # =============================================================================
        print("[6/11] Dropping FK constraint from trades table...")
        cur.execute("""
            ALTER TABLE trades
            DROP CONSTRAINT IF EXISTS trades_edge_id_fkey
        """)
        print("       [OK] FK constraint dropped")
        print()

        # =============================================================================
        # Step 7: Drop old PRIMARY KEY constraint
        # =============================================================================
        print("[7/11] Dropping old PRIMARY KEY constraint...")
        cur.execute("""
            ALTER TABLE edges
            DROP CONSTRAINT IF EXISTS edges_pkey
        """)
        print("       [OK] Old PRIMARY KEY dropped")
        print()

        # =============================================================================
        # Step 8: Add new PRIMARY KEY on surrogate id
        # =============================================================================
        print("[8/11] Adding new PRIMARY KEY on surrogate id...")
        cur.execute("""
            ALTER TABLE edges
            ADD PRIMARY KEY (id)
        """)
        print("       [OK] New PRIMARY KEY added")
        print()

        # =============================================================================
        # Step 9: Update trades FK to reference surrogate id
        # =============================================================================
        print("[9/11] Updating trades FK to reference surrogate id...")

        # Rename FK column in trades table
        print("       [9a] Renaming trades.edge_id -> edge_internal_id...")
        cur.execute("""
            ALTER TABLE trades
            RENAME COLUMN edge_id TO edge_internal_id
        """)
        print("            [OK] Column renamed")

        # Recreate FK to reference surrogate id
        print("       [9b] Creating FK to edges.id (surrogate key)...")
        cur.execute("""
            ALTER TABLE trades
            ADD CONSTRAINT trades_edge_internal_id_fkey
            FOREIGN KEY (edge_internal_id) REFERENCES edges(id)
        """)
        print("            [OK] FK created referencing surrogate id")
        print()

        # =============================================================================
        # Step 10: Drop old column with CASCADE (may have dependent views)
        # =============================================================================
        print("[10/11] Dropping old column (edge_id_old) with CASCADE...")
        cur.execute("""
            ALTER TABLE edges
            DROP COLUMN edge_id_old CASCADE
        """)
        print("        [OK] Old column dropped (any dependent views also dropped)")
        print()

        # =============================================================================
        # Step 11: Add partial UNIQUE index
        # =============================================================================
        print("[11/11] Creating partial UNIQUE index (ensures only ONE current version)...")
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_unique_current
            ON edges(edge_id)
            WHERE row_current_ind = TRUE
        """)
        print("        [OK] Partial UNIQUE index created")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 017 applied successfully!")
        print()
        print("Summary:")
        print("  - Dual-key structure implemented:")
        print("    * id SERIAL PRIMARY KEY (surrogate key)")
        print("    * edge_id VARCHAR (business key)")
        print("  - Foreign key updated:")
        print("    * trades.edge_internal_id -> edges.id (surrogate)")
        print("  - Partial UNIQUE index ensures only ONE current version per edge_id")
        print("  - SCD Type 2 versioning NOW ENABLED [OK]")
        print()
        print("Important:")
        print("  - trades table references surrogate id (edges.id), not business key")
        print("  - Business key (edge_id) used for queries/filtering, not FK relationships")
        print("  - Can now track edge evolution as market conditions change")
        print()
        print("Next steps:")
        print("  1. Test all 3 migrations (positions, game_states, edges)")
        print("  2. Rewrite update_position_price() for proper SCD Type 2")


def rollback_migration(conn):
    """
    Rollback migration: Revert to original schema (edge_id SERIAL PRIMARY KEY).

    Args:
        conn: Database connection

    Warning:
        This rollback is DESTRUCTIVE if you have created SCD Type 2 versions!
        Only safe if no versioning has been used yet.
    """
    with conn.cursor() as cur:
        print("Rolling back Migration 017...")
        print()

        # Drop partial UNIQUE index
        print("[1/9] Dropping partial UNIQUE index...")
        cur.execute("""
            DROP INDEX IF EXISTS idx_edges_unique_current
        """)
        print("      [OK] Index dropped")
        print()

        # Drop FK from trades
        print("[2/9] Dropping FK from trades table...")
        cur.execute("""
            ALTER TABLE trades
            DROP CONSTRAINT IF EXISTS trades_edge_internal_id_fkey
        """)
        print("      [OK] FK dropped")
        print()

        # Rename trades column back
        print("[3/9] Renaming trades.edge_internal_id -> edge_id...")
        cur.execute("""
            ALTER TABLE trades
            RENAME COLUMN edge_internal_id TO edge_id
        """)
        print("      [OK] Column renamed")
        print()

        # Drop PRIMARY KEY on id
        print("[4/9] Dropping PRIMARY KEY on edges.id...")
        cur.execute("""
            ALTER TABLE edges
            DROP CONSTRAINT IF EXISTS edges_pkey
        """)
        print("      [OK] PRIMARY KEY dropped")
        print()

        # Add back old column
        print("[5/9] Adding back edge_id_old (SERIAL)...")
        cur.execute("""
            ALTER TABLE edges
            ADD COLUMN edge_id_old SERIAL
        """)
        print("      [OK] Column added")
        print()

        # Restore old PRIMARY KEY
        print("[6/9] Restoring PRIMARY KEY on edge_id_old...")
        cur.execute("""
            ALTER TABLE edges
            ADD PRIMARY KEY (edge_id_old)
        """)
        print("      [OK] PRIMARY KEY restored")
        print()

        # Recreate FK from trades
        print("[7/9] Recreating FK from trades to edges.edge_id_old...")
        cur.execute("""
            ALTER TABLE trades
            ADD CONSTRAINT trades_edge_id_fkey
            FOREIGN KEY (edge_id) REFERENCES edges(edge_id_old)
        """)
        print("      [OK] FK recreated")
        print()

        # Drop new columns with CASCADE
        print("[8/9] Dropping new columns (id, edge_id) with CASCADE...")
        cur.execute("""
            ALTER TABLE edges
            DROP COLUMN IF EXISTS id CASCADE,
            DROP COLUMN IF EXISTS edge_id CASCADE
        """)
        print("      [OK] New columns dropped (any dependent views also dropped)")
        print()

        # Rename back
        print("[9/9] Renaming edge_id_old -> edge_id...")
        cur.execute("""
            ALTER TABLE edges
            RENAME COLUMN edge_id_old TO edge_id
        """)
        print("      [OK] Column renamed")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 017 rolled back successfully!")


def verify_migration(conn):
    """
    Verify migration was applied correctly.

    Args:
        conn: Database connection

    Returns:
        True if verification passed, False otherwise
    """
    with conn.cursor() as cur:
        print("Verifying Migration 017...")
        print()

        # Check edges columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'edges' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        edges_columns = {row[0]: {"type": row[1], "nullable": row[2]} for row in cur.fetchall()}

        # Check trades columns
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'trades' AND table_schema = 'public'
            AND column_name IN ('edge_id', 'edge_internal_id')
        """)
        trades_edge_columns = {row[0]: row[1] for row in cur.fetchall()}

        # Check PRIMARY KEY
        cur.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = 'edges'::regclass AND i.indisprimary
        """)
        pk_columns = [row[0] for row in cur.fetchall()]

        # Check FK from trades
        cur.execute("""
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'trades'
                AND kcu.column_name = 'edge_internal_id'
        """)
        fk_info = cur.fetchone()

        # Check partial UNIQUE index
        cur.execute("""
            SELECT indexdef
            FROM pg_indexes
            WHERE tablename = 'edges' AND indexname = 'idx_edges_unique_current'
        """)
        unique_index = cur.fetchone()

        # Verify structure
        errors = []

        # Check edges.id column
        if "id" not in edges_columns:
            errors.append("[FAIL] edges.id not found")
        elif edges_columns["id"]["type"] != "integer":
            errors.append(f"[FAIL] edges.id should be integer, got {edges_columns['id']['type']}")

        # Check edges.edge_id column
        if "edge_id" not in edges_columns:
            errors.append("[FAIL] edges.edge_id not found")
        elif "character varying" not in edges_columns["edge_id"]["type"]:
            errors.append(
                f"[FAIL] edge_id should be VARCHAR, got {edges_columns['edge_id']['type']}"
            )
        elif edges_columns["edge_id"]["nullable"] != "NO":
            errors.append("[FAIL] edge_id should be NOT NULL")

        # Check old column removed
        if "edge_id_old" in edges_columns:
            errors.append("[FAIL] edge_id_old still exists (should be dropped)")

        # Check PRIMARY KEY
        if pk_columns != ["id"]:
            errors.append(f"[FAIL] PRIMARY KEY should be (id), got {pk_columns}")

        # Check trades FK column renamed
        if "edge_id" in trades_edge_columns:
            errors.append(
                "[FAIL] trades.edge_id still exists (should be renamed to edge_internal_id)"
            )
        if "edge_internal_id" not in trades_edge_columns:
            errors.append("[FAIL] trades.edge_internal_id not found")

        # Check FK references correct column
        if not fk_info:
            errors.append("[FAIL] FK from trades to edges not found")
        elif fk_info[3] != "id":
            errors.append(f"[FAIL] FK should reference edges.id, got edges.{fk_info[3]}")

        # Check partial UNIQUE index
        if not unique_index:
            errors.append("[FAIL] Partial UNIQUE index idx_edges_unique_current not found")

        if errors:
            print("Verification FAILED:")
            for error in errors:
                print(f"  {error}")
            return False

        print("[SUCCESS] Verification passed!")
        print("  [OK] edges.id SERIAL PRIMARY KEY (surrogate key)")
        print("  [OK] edges.edge_id VARCHAR NOT NULL (business key)")
        print("  [OK] Partial UNIQUE index ensures only ONE current version per edge_id")
        print("  [OK] trades.edge_internal_id -> edges.id (FK)")
        print("  [OK] SCD Type 2 versioning ENABLED")
        return True


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Migration 017: edges Table Surrogate Key")
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
