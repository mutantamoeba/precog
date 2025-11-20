#!/usr/bin/env python3
"""
Migration 016: game_states Table - Add Surrogate Primary Key for SCD Type 2

**Problem:**
game_states table uses business key (game_state_id) as PRIMARY KEY, preventing SCD Type 2.
Cannot insert multiple versions of same game state because PK must be unique.

**Root Cause:**
SCD Type 2 requires:
1. Surrogate PRIMARY KEY (id) - unique across ALL versions
2. Business key (game_state_id) - can duplicate across versions
3. Partial UNIQUE index - ensures only ONE current version per business key

Current schema violates this by using business key as PRIMARY KEY.

**Solution:**
Transform game_states table to dual-key structure:
- Add id SERIAL PRIMARY KEY (surrogate key)
- Convert game_state_id from PRIMARY KEY to VARCHAR business key
- Add partial UNIQUE index on (game_state_id) WHERE row_current_ind = TRUE

**Migration Steps:**
1. Add surrogate id column (SERIAL)
2. Rename old PK column (game_state_id -> game_state_id_old)
3. Add new business key column (game_state_id VARCHAR)
4. Populate business key with GS-{id} format
5. Set business key to NOT NULL
6. Drop old PRIMARY KEY constraint
7. Add new PRIMARY KEY on surrogate id
8. Drop old column
9. Add partial UNIQUE index

**Benefits:**
- Enables proper SCD Type 2 versioning (multiple game state snapshots)
- No child table updates needed (no FKs reference game_states)
- Simpler than positions migration (no dependent tables/views)

**Example After Migration:**
```
| id | game_state_id | event_id  | home_score | away_score | row_current_ind |
|----|---------------|-----------|------------|------------|-----------------|
| 1  | GS-1          | EVT-001   | 0          | 0          | FALSE           |
| 2  | GS-1          | EVT-001   | 7          | 3          | FALSE           |
| 3  | GS-1          | EVT-001   | 14         | 10         | TRUE            |
```
Same game state (GS-1) with 3 versions tracking score changes.

**References:**
- ADR-201: Position History Without SCD Type 2 (SUPERSEDED)
- SESSION_HANDOFF.md 2025-11-18: SCD Type 2 investigation
- Migration 015: positions table (same pattern)

**Migration Safe?:** YES
- ✅ No foreign key dependencies to update
- ✅ No views dependent on game_state_id
- ✅ Rollback script included
- ✅ Verification function validates changes

**Estimated Time:** ~2 seconds (no dependent tables to update)

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
    Apply migration: Convert game_states to dual-key structure for SCD Type 2.

    Args:
        conn: Database connection

    Educational Note:
        This migration is SIMPLER than Migration 015 (positions) because:
        - No child tables have FKs to game_states
        - No views depend on game_state_id column
        - No CASCADE operations needed

        The dual-key pattern:
        - id SERIAL: Surrogate primary key (unique across all versions)
        - game_state_id VARCHAR: Business key (can repeat across versions)
        - Partial UNIQUE index: Ensures only ONE current version per game
    """
    with conn.cursor() as cur:
        print("Starting Migration 016: game_states Table Surrogate Key...")
        print()

        # =============================================================================
        # Step 1: Add surrogate id column
        # =============================================================================
        print("[1/9] Adding surrogate id column (SERIAL)...")
        cur.execute("""
            ALTER TABLE game_states
            ADD COLUMN IF NOT EXISTS id SERIAL
        """)
        print("      [OK] Surrogate id column added")
        print()

        # =============================================================================
        # Step 2: Rename old PRIMARY KEY column
        # =============================================================================
        print("[2/9] Renaming old PRIMARY KEY (game_state_id -> game_state_id_old)...")
        cur.execute("""
            ALTER TABLE game_states
            RENAME COLUMN game_state_id TO game_state_id_old
        """)
        print("      [OK] Column renamed")
        print()

        # =============================================================================
        # Step 3: Add new business key column
        # =============================================================================
        print("[3/9] Adding new business key column (game_state_id VARCHAR)...")
        cur.execute("""
            ALTER TABLE game_states
            ADD COLUMN game_state_id VARCHAR
        """)
        print("      [OK] Business key column added")
        print()

        # =============================================================================
        # Step 4: Populate business key with GS-{id} format
        # =============================================================================
        print("[4/9] Populating business key (GS-{id} format)...")
        cur.execute("""
            UPDATE game_states
            SET game_state_id = 'GS-' || id::TEXT
        """)
        print("      [OK] Business key populated")
        print()

        # =============================================================================
        # Step 5: Set business key to NOT NULL
        # =============================================================================
        print("[5/9] Setting business key to NOT NULL...")
        cur.execute("""
            ALTER TABLE game_states
            ALTER COLUMN game_state_id SET NOT NULL
        """)
        print("      [OK] NOT NULL constraint added")
        print()

        # =============================================================================
        # Step 6: Drop old PRIMARY KEY constraint
        # =============================================================================
        print("[6/9] Dropping old PRIMARY KEY constraint...")
        cur.execute("""
            ALTER TABLE game_states
            DROP CONSTRAINT IF EXISTS game_states_pkey
        """)
        print("      [OK] Old PRIMARY KEY dropped")
        print()

        # =============================================================================
        # Step 7: Add new PRIMARY KEY on surrogate id
        # =============================================================================
        print("[7/9] Adding new PRIMARY KEY on surrogate id...")
        cur.execute("""
            ALTER TABLE game_states
            ADD PRIMARY KEY (id)
        """)
        print("      [OK] New PRIMARY KEY added")
        print()

        # =============================================================================
        # Step 8: Drop old column (CASCADE to drop dependent views)
        # =============================================================================
        print("[8/9] Dropping old column (game_state_id_old) with CASCADE...")
        cur.execute("""
            ALTER TABLE game_states
            DROP COLUMN game_state_id_old CASCADE
        """)
        print("      [OK] Old column dropped (views using old column also dropped)")
        print()

        # =============================================================================
        # Step 9: Add partial UNIQUE index
        # =============================================================================
        print("[9/9] Creating partial UNIQUE index (ensures only ONE current version)...")
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_game_states_unique_current
            ON game_states(game_state_id)
            WHERE row_current_ind = TRUE
        """)
        print("      [OK] Partial UNIQUE index created")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 016 applied successfully!")
        print()
        print("Summary:")
        print("  - Dual-key structure implemented:")
        print("    * id SERIAL PRIMARY KEY (surrogate key)")
        print("    * game_state_id VARCHAR (business key)")
        print("  - Partial UNIQUE index ensures only ONE current version per game_state_id")
        print("  - SCD Type 2 versioning NOW ENABLED [OK]")
        print()
        print("Important:")
        print("  - Business key (game_state_id) used for queries/filtering")
        print("  - Surrogate key (id) used for internal uniqueness")
        print("  - Can now track game state changes (score updates, period transitions)")
        print()
        print("Next steps:")
        print("  1. Run migration_017 (edges table)")
        print("  2. Rewrite update_position_price() for proper SCD Type 2")


def rollback_migration(conn):
    """
    Rollback migration: Revert to original schema (game_state_id SERIAL PRIMARY KEY).

    Args:
        conn: Database connection

    Warning:
        This rollback is DESTRUCTIVE if you have created SCD Type 2 versions!
        Only safe if no versioning has been used yet.
    """
    with conn.cursor() as cur:
        print("Rolling back Migration 016...")
        print()

        # Drop partial UNIQUE index
        print("[1/6] Dropping partial UNIQUE index...")
        cur.execute("""
            DROP INDEX IF EXISTS idx_game_states_unique_current
        """)
        print("      [OK] Index dropped")
        print()

        # Drop PRIMARY KEY on id
        print("[2/6] Dropping PRIMARY KEY on game_states.id...")
        cur.execute("""
            ALTER TABLE game_states
            DROP CONSTRAINT IF EXISTS game_states_pkey
        """)
        print("      [OK] PRIMARY KEY dropped")
        print()

        # Add back old column
        print("[3/6] Adding back game_state_id_old (SERIAL)...")
        cur.execute("""
            ALTER TABLE game_states
            ADD COLUMN game_state_id_old SERIAL
        """)
        print("      [OK] Column added")
        print()

        # Restore old PRIMARY KEY
        print("[4/6] Restoring PRIMARY KEY on game_state_id_old...")
        cur.execute("""
            ALTER TABLE game_states
            ADD PRIMARY KEY (game_state_id_old)
        """)
        print("      [OK] PRIMARY KEY restored")
        print()

        # Drop new columns (CASCADE to drop dependent views)
        print("[5/6] Dropping new columns (id, game_state_id) with CASCADE...")
        cur.execute("""
            ALTER TABLE game_states
            DROP COLUMN IF EXISTS id CASCADE,
            DROP COLUMN IF EXISTS game_state_id CASCADE
        """)
        print("      [OK] New columns dropped (views using columns also dropped)")
        print()

        # Rename back
        print("[6/6] Renaming game_state_id_old -> game_state_id...")
        cur.execute("""
            ALTER TABLE game_states
            RENAME COLUMN game_state_id_old TO game_state_id
        """)
        print("      [OK] Column renamed")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 016 rolled back successfully!")


def verify_migration(conn):
    """
    Verify migration was applied correctly.

    Args:
        conn: Database connection

    Returns:
        True if verification passed, False otherwise
    """
    with conn.cursor() as cur:
        print("Verifying Migration 016...")
        print()

        # Check game_states columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'game_states' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = {row[0]: {"type": row[1], "nullable": row[2]} for row in cur.fetchall()}

        # Check PRIMARY KEY
        cur.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = 'game_states'::regclass AND i.indisprimary
        """)
        pk_columns = [row[0] for row in cur.fetchall()]

        # Check partial UNIQUE index
        cur.execute("""
            SELECT indexdef
            FROM pg_indexes
            WHERE tablename = 'game_states' AND indexname = 'idx_game_states_unique_current'
        """)
        unique_index = cur.fetchone()

        # Verify structure
        errors = []

        # Check id column exists and is SERIAL
        if "id" not in columns:
            errors.append("[FAIL] game_states.id not found")
        elif columns["id"]["type"] != "integer":
            errors.append(f"[FAIL] game_states.id should be integer, got {columns['id']['type']}")

        # Check game_state_id exists and is VARCHAR
        if "game_state_id" not in columns:
            errors.append("[FAIL] game_states.game_state_id not found")
        elif "character varying" not in columns["game_state_id"]["type"]:
            errors.append(
                f"[FAIL] game_state_id should be VARCHAR, got {columns['game_state_id']['type']}"
            )
        elif columns["game_state_id"]["nullable"] != "NO":
            errors.append("[FAIL] game_state_id should be NOT NULL")

        # Check old column removed
        if "game_state_id_old" in columns:
            errors.append("[FAIL] game_state_id_old still exists (should be dropped)")

        # Check PRIMARY KEY
        if pk_columns != ["id"]:
            errors.append(f"[FAIL] PRIMARY KEY should be (id), got {pk_columns}")

        # Check partial UNIQUE index
        if not unique_index:
            errors.append("[FAIL] Partial UNIQUE index idx_game_states_unique_current not found")

        if errors:
            print("Verification FAILED:")
            for error in errors:
                print(f"  {error}")
            return False

        print("[SUCCESS] Verification passed!")
        print("  [OK] game_states.id SERIAL PRIMARY KEY (surrogate key)")
        print("  [OK] game_states.game_state_id VARCHAR NOT NULL (business key)")
        print("  [OK] Partial UNIQUE index ensures only ONE current version per game_state_id")
        print("  [OK] SCD Type 2 versioning ENABLED")
        return True


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Migration 016: game_states Table Surrogate Key")
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
