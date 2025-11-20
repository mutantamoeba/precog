#!/usr/bin/env python3
"""
Migration 015: Add Surrogate Primary Key to positions Table (Enable SCD Type 2)

**Problem:**
positions table uses position_id SERIAL as PRIMARY KEY (business key = PK).
This prevents proper SCD Type 2 versioning - cannot insert multiple versions with same position_id.

Current BROKEN schema:
```sql
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,  -- ❌ Business key = PK (can't duplicate)
    ...
    row_current_ind BOOLEAN DEFAULT TRUE,  -- ⚠️ Present but unusable
    row_end_ts TIMESTAMP                   -- ⚠️ Present but unusable
);
```

Result: Cannot track position evolution - update_position_price() creates orphaned records, not versions.

**Solution:**
Implement dual-key structure (same proven pattern as markets table):
- id SERIAL PRIMARY KEY (surrogate key - always unique)
- position_id VARCHAR (business key - can repeat for versions)
- Partial UNIQUE index ensures only ONE current version per business key

Fixed schema (after migration):
```sql
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,               -- ✅ Surrogate key (always unique)
    position_id VARCHAR NOT NULL,        -- ✅ Business key (can repeat for versions)
    ...
    row_current_ind BOOLEAN DEFAULT TRUE,  -- ✅ Now functional!
    row_end_ts TIMESTAMP                   -- ✅ Now functional!
);

-- Ensure only ONE current version per business key:
CREATE UNIQUE INDEX idx_positions_unique_current
ON positions(position_id)
WHERE row_current_ind = TRUE;
```

**Changes:**
1. Add new surrogate id column (SERIAL PRIMARY KEY)
2. Rename current position_id → position_id_old (temp)
3. Add new position_id VARCHAR (business key)
4. Populate business keys from old IDs (POS-{id} format)
5. Update foreign keys in trades, position_exits tables
6. Drop old position_id_old column
7. Add partial UNIQUE index (ensures only ONE current version per position_id)

**Use Cases Enabled:**
- Position evolution tracking: "What was peak unrealized PnL?"
- Trailing stop analysis: "Why did my trailing stop trigger too early?"
- Strategy optimization: "Should I use tighter/looser stops?"
- Backtesting: Exact historical position states (not reconstructed estimates)

**References:**
- ADR-089: Fix SCD Type 2 Schema with Surrogate Keys
- ADR-202: Comprehensive SCD Type 2 Schema Fix Decision
- ADR-201: Position History Without SCD Type 2 (SUPERSEDED)
- REQ-DB-009: positions Table SCD Type 2 History Tracking
- DATABASE_SCHEMA_SUMMARY V1.9 (current), V1.10 (after migration)

**Migration Safe?:** YES
- ✅ No production data (empty tables)
- ✅ Foreign key updates cascaded
- ✅ Rollback script included
- ✅ Verification checks included

**Estimated Time:** ~5-10 seconds (metadata operations + data population)

Created: 2025-11-19
Phase: 1.5 (Manager Components)
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
    Apply migration: Add surrogate primary key to positions table.

    Args:
        conn: Database connection

    Educational Note:
        This migration transforms positions table from business-key-as-PK
        to dual-key structure (surrogate PK + business key). This enables
        proper SCD Type 2 versioning where multiple rows can have the same
        business key (position_id) but different surrogate keys (id).

        The partial UNIQUE index ensures data integrity: only ONE row can
        have row_current_ind = TRUE for any given position_id.
    """
    with conn.cursor() as cur:
        print("Starting Migration 015: Add Surrogate Primary Key to positions...")
        print()

        # ==============================================================================
        # Step 1: Add new surrogate id column
        # ==============================================================================
        print("[1/10] Adding positions.id (SERIAL, will become new PK)...")
        cur.execute("""
            ALTER TABLE positions
            ADD COLUMN id SERIAL
        """)
        print("        [OK] Surrogate id column added")
        print()

        # ==============================================================================
        # Step 2: Rename current position_id to position_id_old (temporary)
        # ==============================================================================
        print("[2/10] Renaming positions.position_id -> position_id_old (temp)...")
        cur.execute("""
            ALTER TABLE positions
            RENAME COLUMN position_id TO position_id_old
        """)
        print("        [OK] Renamed to position_id_old")
        print()

        # ==============================================================================
        # Step 3: Add new position_id VARCHAR column (business key)
        # ==============================================================================
        print("[3/10] Adding positions.position_id (VARCHAR, new business key)...")
        cur.execute("""
            ALTER TABLE positions
            ADD COLUMN position_id VARCHAR
        """)
        print("        [OK] New position_id VARCHAR column added")
        print()

        # ==============================================================================
        # Step 4: Populate new position_id with POS-{id} format
        # ==============================================================================
        print("[4/10] Populating position_id with POS-{id} format...")
        cur.execute("""
            UPDATE positions
            SET position_id = 'POS-' || id::TEXT
        """)
        rows_updated = cur.rowcount
        print(f"        [OK] {rows_updated} rows updated with business keys")
        print()

        # ==============================================================================
        # Step 5: Make new position_id NOT NULL
        # ==============================================================================
        print("[5/10] Adding NOT NULL constraint to position_id...")
        cur.execute("""
            ALTER TABLE positions
            ALTER COLUMN position_id SET NOT NULL
        """)
        print("        [OK] NOT NULL constraint added")
        print()

        # ==============================================================================
        # Step 6: Drop ALL foreign key constraints BEFORE dropping PRIMARY KEY
        # ==============================================================================
        print("[6/10] Dropping foreign key constraints from child tables...")

        # Drop trades FK
        cur.execute("""
            ALTER TABLE trades
            DROP CONSTRAINT IF EXISTS trades_position_id_fkey
        """)

        # Drop position_exits FK
        cur.execute("""
            ALTER TABLE position_exits
            DROP CONSTRAINT IF EXISTS position_exits_position_id_fkey
        """)

        # Drop exit_attempts FK
        cur.execute("""
            ALTER TABLE exit_attempts
            DROP CONSTRAINT IF EXISTS exit_attempts_position_id_fkey
        """)
        print("        [OK] Dropped FK constraints from trades, position_exits, exit_attempts")
        print()

        # ==============================================================================
        # Step 7: Drop old PRIMARY KEY constraint
        # ==============================================================================
        print("[7/10] Dropping old PRIMARY KEY constraint on position_id_old...")
        cur.execute("""
            ALTER TABLE positions
            DROP CONSTRAINT IF EXISTS positions_pkey
        """)
        print("        [OK] Dropped old PK constraint")
        print()

        # ==============================================================================
        # Step 8: Add new PRIMARY KEY on id column
        # ==============================================================================
        print("[8/10] Adding PRIMARY KEY on positions.id...")
        cur.execute("""
            ALTER TABLE positions
            ADD PRIMARY KEY (id)
        """)
        print("        [OK] PRIMARY KEY added to id column")
        print()

        # ==============================================================================
        # Step 9: Update foreign keys in trades table (reference surrogate id, not business key)
        # ==============================================================================
        print("[9/10] Updating foreign keys in child tables...")

        # Rename trades.position_id to position_internal_id (references surrogate id)
        cur.execute("""
            ALTER TABLE trades
            RENAME COLUMN position_id TO position_internal_id
        """)

        # Recreate FK constraint referencing surrogate id
        cur.execute("""
            ALTER TABLE trades
            ADD CONSTRAINT trades_position_internal_id_fkey
            FOREIGN KEY (position_internal_id) REFERENCES positions(id)
        """)
        print("        [OK] trades.position_internal_id -> positions.id")

        # Rename position_exits.position_id to position_internal_id (references surrogate id)
        cur.execute("""
            ALTER TABLE position_exits
            RENAME COLUMN position_id TO position_internal_id
        """)

        # Recreate FK constraint referencing surrogate id
        cur.execute("""
            ALTER TABLE position_exits
            ADD CONSTRAINT position_exits_position_internal_id_fkey
            FOREIGN KEY (position_internal_id) REFERENCES positions(id)
        """)
        print("        [OK] position_exits.position_internal_id -> positions.id")

        # Rename exit_attempts.position_id to position_internal_id (references surrogate id)
        cur.execute("""
            ALTER TABLE exit_attempts
            RENAME COLUMN position_id TO position_internal_id
        """)

        # Recreate FK constraint referencing surrogate id
        cur.execute("""
            ALTER TABLE exit_attempts
            ADD CONSTRAINT exit_attempts_position_internal_id_fkey
            FOREIGN KEY (position_internal_id) REFERENCES positions(id)
        """)
        print("        [OK] exit_attempts.position_internal_id -> positions.id")
        print()

        # ==============================================================================
        # Step 10: Drop old position_id_old column (CASCADE to drop dependent views)
        # ==============================================================================
        print("[10/10] Dropping positions.position_id_old column (CASCADE)...")
        cur.execute("""
            ALTER TABLE positions
            DROP COLUMN position_id_old CASCADE
        """)
        print("         [OK] Dropped position_id_old column and dependent views")
        print(
            "         [INFO] Dependent views dropped: open_positions, positions_urgent_monitoring, stale_position_alerts"
        )
        print(
            "         [INFO] Views can be recreated with updated schema referencing new surrogate id"
        )
        print()

        # ==============================================================================
        # Step 11: Add partial UNIQUE index (only ONE current version per position_id)
        # ==============================================================================
        print("[11/10] Creating partial UNIQUE index (ensures only ONE current version)...")
        cur.execute("""
            CREATE UNIQUE INDEX idx_positions_unique_current
            ON positions(position_id)
            WHERE row_current_ind = TRUE
        """)
        print("         [OK] Partial UNIQUE index created")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 015 applied successfully!")
        print()
        print("Summary:")
        print("  - Dual-key structure implemented:")
        print("    * id SERIAL PRIMARY KEY (surrogate key)")
        print("    * position_id VARCHAR (business key)")
        print("  - Foreign keys updated (3 tables):")
        print("    * trades.position_internal_id -> positions.id (surrogate)")
        print("    * position_exits.position_internal_id -> positions.id (surrogate)")
        print("    * exit_attempts.position_internal_id -> positions.id (surrogate)")
        print("  - Partial UNIQUE index ensures only ONE current version per position_id")
        print("  - SCD Type 2 versioning NOW ENABLED [OK]")
        print()
        print("Important:")
        print("  - Child tables reference surrogate id (positions.id), not business key")
        print("  - Business key (position_id) used for queries/filtering, not FK relationships")
        print(
            "  - This allows multiple position versions with same position_id (e.g., POS-123 v1, v2, v3)"
        )
        print()
        print("Next steps:")
        print("  1. Run migration_016 (game_states table)")
        print("  2. Run migration_017 (edges table)")
        print("  3. Rewrite update_position_price() to use proper SCD Type 2")


def rollback_migration(conn):
    """
    Rollback migration: Revert to original schema (position_id SERIAL PRIMARY KEY).

    Args:
        conn: Database connection

    Warning:
        This rollback is DESTRUCTIVE if you have created SCD Type 2 versions!
        Only safe if no versioning has been used yet.
    """
    with conn.cursor() as cur:
        print("Rolling back Migration 015...")
        print()

        # Drop partial UNIQUE index
        print("[1/8] Dropping partial UNIQUE index...")
        cur.execute("""
            DROP INDEX IF EXISTS idx_positions_unique_current
        """)
        print("      [OK] Index dropped")
        print()

        # Drop PRIMARY KEY on id
        print("[2/8] Dropping PRIMARY KEY on positions.id...")
        cur.execute("""
            ALTER TABLE positions
            DROP CONSTRAINT IF EXISTS positions_pkey
        """)
        print("      [OK] PK dropped")
        print()

        # Add temporary position_id_int column
        print("[3/8] Adding temporary position_id_int (INTEGER) column...")
        cur.execute("""
            ALTER TABLE positions
            ADD COLUMN position_id_int INTEGER
        """)
        print("      [OK] Column added")

        # Populate position_id_int from id
        print("[4/8] Populating position_id_int from id...")
        cur.execute("""
            UPDATE positions
            SET position_id_int = id
        """)
        print(f"      [OK] {cur.rowcount} rows updated")
        print()

        # Drop FK constraints from child tables
        print("[5/8] Updating foreign keys in trades and position_exits...")
        cur.execute("""
            ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_position_id_fkey
        """)
        cur.execute("""
            ALTER TABLE position_exits DROP CONSTRAINT IF EXISTS position_exits_position_id_fkey
        """)

        # Update child tables to use INTEGER IDs
        cur.execute("""
            UPDATE trades t
            SET position_id = p.position_id_int::VARCHAR
            FROM positions p
            WHERE t.position_id = p.position_id
        """)
        cur.execute("""
            ALTER TABLE trades
            ALTER COLUMN position_id TYPE INTEGER USING position_id::INTEGER
        """)

        cur.execute("""
            UPDATE position_exits pe
            SET position_id = p.position_id_int::VARCHAR
            FROM positions p
            WHERE pe.position_id = p.position_id
        """)
        cur.execute("""
            ALTER TABLE position_exits
            ALTER COLUMN position_id TYPE INTEGER USING position_id::INTEGER
        """)
        print("      [OK] Foreign keys updated")
        print()

        # Drop old position_id VARCHAR
        print("[6/8] Dropping position_id VARCHAR column...")
        cur.execute("""
            ALTER TABLE positions
            DROP COLUMN position_id
        """)
        print("      [OK] Column dropped")
        print()

        # Rename position_id_int back to position_id
        print("[7/8] Renaming position_id_int -> position_id...")
        cur.execute("""
            ALTER TABLE positions
            RENAME COLUMN position_id_int TO position_id
        """)
        print("      [OK] Renamed")
        print()

        # Add back PRIMARY KEY on position_id
        print("[8/8] Adding PRIMARY KEY on position_id...")
        cur.execute("""
            ALTER TABLE positions
            ADD PRIMARY KEY (position_id)
        """)
        print("      [OK] PK added")

        # Recreate foreign keys
        cur.execute("""
            ALTER TABLE trades
            ADD CONSTRAINT trades_position_id_fkey
            FOREIGN KEY (position_id) REFERENCES positions(position_id)
        """)
        cur.execute("""
            ALTER TABLE position_exits
            ADD CONSTRAINT position_exits_position_id_fkey
            FOREIGN KEY (position_id) REFERENCES positions(position_id)
        """)
        print("      [OK] FK constraints recreated")

        # Drop id column
        cur.execute("""
            ALTER TABLE positions
            DROP COLUMN id
        """)
        print("      [OK] id column dropped")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 015 rolled back successfully!")


def verify_migration(conn):
    """
    Verify migration was applied correctly.

    Args:
        conn: Database connection

    Returns:
        True if verification passed, False otherwise
    """
    with conn.cursor() as cur:
        print("Verifying Migration 015...")
        print()

        errors = []

        # Check positions table columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'positions' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = {row[0]: {"type": row[1], "nullable": row[2]} for row in cur.fetchall()}

        # Verify id column exists and is INTEGER
        if "id" not in columns:
            errors.append("[FAIL] positions.id column not found")
        elif columns["id"]["type"] != "integer":
            errors.append(f"[FAIL] positions.id is {columns['id']['type']}, expected integer")

        # Verify position_id is VARCHAR and NOT NULL
        if "position_id" not in columns:
            errors.append("[FAIL] positions.position_id column not found")
        elif columns["position_id"]["type"] != "character varying":
            errors.append(
                f"[FAIL] positions.position_id is {columns['position_id']['type']}, expected character varying"
            )
        elif columns["position_id"]["nullable"] == "YES":
            errors.append("[FAIL] positions.position_id is nullable, should be NOT NULL")

        # Verify old position_id_old column is gone
        if "position_id_old" in columns:
            errors.append("[FAIL] positions.position_id_old still exists (should be dropped)")

        # Verify PRIMARY KEY
        cur.execute("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'positions' AND table_schema = 'public' AND constraint_type = 'PRIMARY KEY'
        """)
        pk_constraints = cur.fetchall()
        if not pk_constraints:
            errors.append("[FAIL] No PRIMARY KEY found on positions table")

        # Verify partial UNIQUE index exists
        cur.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'positions' AND indexname = 'idx_positions_unique_current'
        """)
        unique_index = cur.fetchone()
        if not unique_index:
            errors.append("[FAIL] Partial UNIQUE index idx_positions_unique_current not found")

        # Verify trades FK constraint (renamed to position_internal_id)
        cur.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'trades'
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'trades_position_internal_id_fkey'
        """)
        trades_fk = cur.fetchone()
        if not trades_fk:
            errors.append("[FAIL] trades.position_internal_id FK constraint not found")

        # Verify position_exits FK constraint (renamed to position_internal_id)
        cur.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'position_exits'
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'position_exits_position_internal_id_fkey'
        """)
        exits_fk = cur.fetchone()
        if not exits_fk:
            errors.append("[FAIL] position_exits.position_internal_id FK constraint not found")

        # Verify exit_attempts FK constraint (renamed to position_internal_id)
        cur.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'exit_attempts'
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'exit_attempts_position_internal_id_fkey'
        """)
        attempts_fk = cur.fetchone()
        if not attempts_fk:
            errors.append("[FAIL] exit_attempts.position_internal_id FK constraint not found")

        if errors:
            print("Verification FAILED:")
            for error in errors:
                print(f"  {error}")
            return False

        print("[SUCCESS] Verification passed!")
        print("  [OK] positions.id SERIAL PRIMARY KEY (surrogate key)")
        print("  [OK] positions.position_id VARCHAR NOT NULL (business key)")
        print("  [OK] Partial UNIQUE index ensures only ONE current version per position_id")
        print("  [OK] trades.position_internal_id -> positions.id (FK)")
        print("  [OK] position_exits.position_internal_id -> positions.id (FK)")
        print("  [OK] exit_attempts.position_internal_id -> positions.id (FK)")
        print("  [OK] SCD Type 2 versioning ENABLED")
        return True


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migration 015: Add Surrogate Primary Key to positions"
    )
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
