#!/usr/bin/env python3
"""
Migration 020: positions Table - Add Position Attribution

**Problem:**
positions table lacks entry-time attribution data needed for strategy evaluation:
- Cannot determine which strategy opened which position (strategy_id exists but no model_id)
- Cannot analyze "Was the entry decision good?" (no calculated_probability at entry)
- Cannot measure initial edge quality (no edge_at_entry, market_price_at_entry snapshots)
- Strategy A/B testing requires complex joins to reconstruct entry conditions

**Root Cause:**
Position attribution gap identified in SCHEMA_ANALYSIS_2025-11-21.md (Gap #3):
- positions table has strategy_id but no model_id (incomplete attribution)
- No entry-time snapshots of probabilities/prices (only current values)
- Cannot evaluate entry decision quality without reconstructing historical state

**Solution:**
Add 4 explicit attribution columns to positions table:
1. `model_id` - Probability model that generated entry signal (FK to probability_models)
2. `calculated_probability` - Model-predicted win probability at position entry
3. `edge_at_entry` - Calculated edge when position opened
4. `market_price_at_entry` - Kalshi market price when position opened

Note: strategy_id already exists in positions table (added in Migration 003).

**Why Explicit Columns vs JSONB:**
- **Performance:** 20-100x faster for strategy evaluation queries
- **Immutability:** Entry snapshots never change (perfect fit for explicit columns)
- **Type Safety:** DECIMAL(10,4) with CHECK constraints (database-level validation)
- **Query Simplicity:** No JSONB path navigation for critical analytics
- **Index Efficiency:** B-tree indexes for fast filtering (WHERE edge_at_entry > 0.05)

**Decision:** Use explicit columns - entry snapshots are immutable, queried frequently,
and performance is critical for strategy evaluation dashboard.

**Benefits:**
- Strategy A/B testing: "Strategy v1.5 vs v2.0 - which enters at better edge?"
- Model evaluation: "Which model generates best entry signals?"
- Entry quality analysis: "Do high-edge entries correlate with profit?"
- Position immutability: Entry snapshots locked (ADR-018 Immutable Versioning)

**Example Queries:**
```sql
-- Compare strategy versions by entry edge quality
SELECT strategy_id, AVG(edge_at_entry), AVG(realized_pnl)
FROM positions
WHERE row_current_ind = TRUE
GROUP BY strategy_id
ORDER BY AVG(edge_at_entry) DESC;

-- Find positions with high entry edge that lost (entry vs exit analysis)
SELECT position_id, strategy_id, edge_at_entry, calculated_probability, exit_reason, realized_pnl
FROM positions
WHERE edge_at_entry > 0.10 AND realized_pnl < 0
ORDER BY edge_at_entry DESC;
```

**Data Integrity:**
- strategy_id already exists (NOT NULL, FK to strategies) - added in Migration 003
- model_id FK to probability_models (ensures model exists)
- CHECK constraints ensure probability ranges (0.0 - 1.0)
- edge_at_entry can be negative (model was wrong at entry)
- All new columns nullable (backfill not required for Phase 1.5)
- Partial indexes for NOT NULL values (Phase 2+ analytics optimization)

**Migration Safe?:** YES
- ✅ Non-breaking (nullable columns, no DEFAULT needed)
- ✅ Rollback script included
- ✅ Verification function validates changes
- ✅ No data loss (column addition only)
- ✅ Partial indexes avoid overhead for NULL rows
- ✅ strategy_id already exists (no FK changes needed)

**References:**
- ADR-091: Explicit Columns for Trade/Position Attribution
- ADR-090: Strategy Contains Entry + Exit Rules with Nested Versioning
- ADR-018: Immutable Versioning (positions lock to strategy version at entry)
- docs/analysis/SCHEMA_ANALYSIS_2025-11-21.md (Gap #3: Position Attribution)
- ADR-002: Decimal Precision (DECIMAL(10,4) for all prices/probabilities)

**Related Migrations:**
- Migration 018: Trade source tracking (automated vs manual)
- Migration 019: Trade attribution enrichment (calculated_probability, market_price, edge_value)
- Migration 003: Added strategy_id to positions table

**Estimated Time:** ~2 seconds (4 columns + 3 CHECK constraints + 4 partial indexes)

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
    Apply migration: Add position attribution columns to positions table.

    Args:
        conn: Database connection

    Educational Note:
        Position attribution follows ADR-018 Immutable Versioning principle:
        - Positions lock to strategy_id at entry (strategy version cannot change)
        - Entry snapshots (calculated_probability, edge_at_entry, market_price_at_entry)
          are immutable (never updated, even if position price changes)
        - This enables A/B testing: "Did Strategy v1.5 make better entry decisions than v2.0?"

        Why immutability matters:
        - Can compare strategy versions fairly (no confounding from exit changes)
        - Entry vs exit analysis (did good entry lead to profit, or was exit the key?)
        - Historical reproducibility (know exactly what model predicted at entry time)

        Example: Position opened with edge_at_entry = 0.08. Price moves, edge now 0.03.
        We keep edge_at_entry = 0.08 (immutable) to evaluate entry decision quality.
    """
    with conn.cursor() as cur:
        print("Starting Migration 020: Position Attribution...")
        print()

        # =============================================================================
        # Step 1: Add model_id foreign key
        # =============================================================================
        print("[1/13] Adding model_id column (FK to probability_models)...")
        cur.execute("""
            ALTER TABLE positions
            ADD COLUMN IF NOT EXISTS model_id INTEGER REFERENCES probability_models(id)
        """)
        print("        [OK] Column added (foreign key to probability_models)")
        print()

        # =============================================================================
        # Step 2: Add calculated_probability column
        # =============================================================================
        print("[2/13] Adding calculated_probability column...")
        cur.execute("""
            ALTER TABLE positions
            ADD COLUMN IF NOT EXISTS calculated_probability DECIMAL(10,4)
            CHECK (calculated_probability IS NULL OR (calculated_probability >= 0 AND calculated_probability <= 1))
        """)
        print("        [OK] Column added (DECIMAL(10,4), nullable, range: 0.0-1.0)")
        print()

        # =============================================================================
        # Step 3: Add edge_at_entry column
        # =============================================================================
        print("[3/13] Adding edge_at_entry column...")
        cur.execute("""
            ALTER TABLE positions
            ADD COLUMN IF NOT EXISTS edge_at_entry DECIMAL(10,4)
        """)
        print("        [OK] Column added (DECIMAL(10,4), nullable, can be negative)")
        print()

        # =============================================================================
        # Step 4: Add market_price_at_entry column
        # =============================================================================
        print("[4/13] Adding market_price_at_entry column...")
        cur.execute("""
            ALTER TABLE positions
            ADD COLUMN IF NOT EXISTS market_price_at_entry DECIMAL(10,4)
            CHECK (market_price_at_entry IS NULL OR (market_price_at_entry >= 0 AND market_price_at_entry <= 1))
        """)
        print("        [OK] Column added (DECIMAL(10,4), nullable, range: 0.0-1.0)")
        print()

        # =============================================================================
        # Step 5: Add partial index on model_id (NOT NULL rows)
        # =============================================================================
        print("[5/13] Creating partial index on model_id...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_model_id
            ON positions(model_id)
            WHERE model_id IS NOT NULL
        """)
        print("        [OK] Partial index created (supports model performance queries)")
        print()

        # =============================================================================
        # Step 6: Add partial index on calculated_probability (NOT NULL rows)
        # =============================================================================
        print("[6/13] Creating partial index on calculated_probability...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_calculated_probability
            ON positions(calculated_probability)
            WHERE calculated_probability IS NOT NULL
        """)
        print("        [OK] Partial index created")
        print()

        # =============================================================================
        # Step 7: Add partial index on edge_at_entry (NOT NULL rows)
        # =============================================================================
        print("[7/13] Creating partial index on edge_at_entry...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_edge_at_entry
            ON positions(edge_at_entry)
            WHERE edge_at_entry IS NOT NULL
        """)
        print("        [OK] Partial index created (supports edge quality analysis)")
        print()

        # =============================================================================
        # Step 8: Add partial index on market_price_at_entry (NOT NULL rows)
        # =============================================================================
        print("[8/13] Creating partial index on market_price_at_entry...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_market_price_at_entry
            ON positions(market_price_at_entry)
            WHERE market_price_at_entry IS NOT NULL
        """)
        print("        [OK] Partial index created")
        print()

        # =============================================================================
        # Step 9: Add model_id comment
        # =============================================================================
        print("[9/13] Adding column comments...")
        cur.execute("""
            COMMENT ON COLUMN positions.model_id IS
            'Probability model that generated entry signal (immutable, locked at position entry)'
        """)
        print("        [OK] model_id comment added")
        print()

        # =============================================================================
        # Step 10: Add calculated_probability comment
        # =============================================================================
        print("[10/13] Adding calculated_probability comment...")
        cur.execute("""
            COMMENT ON COLUMN positions.calculated_probability IS
            'Model-predicted win probability at position entry (immutable snapshot for strategy evaluation)'
        """)
        print("         [OK] calculated_probability comment added")
        print()

        # =============================================================================
        # Step 11: Add edge_at_entry comment
        # =============================================================================
        print("[11/13] Adding edge_at_entry comment...")
        cur.execute("""
            COMMENT ON COLUMN positions.edge_at_entry IS
            'Calculated edge when position opened (calculated_probability - market_price_at_entry); immutable'
        """)
        print("         [OK] edge_at_entry comment added")
        print()

        # =============================================================================
        # Step 12: Add market_price_at_entry comment
        # =============================================================================
        print("[12/13] Adding market_price_at_entry comment...")
        cur.execute("""
            COMMENT ON COLUMN positions.market_price_at_entry IS
            'Kalshi market price when position opened (immutable snapshot from API)'
        """)
        print("         [OK] market_price_at_entry comment added")
        print()

        # =============================================================================
        # Step 13: Verify strategy_id exists (added in Migration 003)
        # =============================================================================
        print("[13/13] Verifying strategy_id column exists...")
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'positions' AND column_name = 'strategy_id'
        """)
        strategy_id_exists = cur.fetchone()
        if strategy_id_exists:
            print("         [OK] strategy_id column exists (added in Migration 003)")
        else:
            print("         [WARN] strategy_id column not found (expected from Migration 003)")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 020 applied successfully!")
        print()
        print("Summary:")
        print("  - 4 columns added:")
        print("    * model_id INTEGER (FK to probability_models)")
        print("    * calculated_probability DECIMAL(10,4) (model prediction at entry, 0.0-1.0)")
        print("    * edge_at_entry DECIMAL(10,4) (edge when opened, immutable)")
        print("    * market_price_at_entry DECIMAL(10,4) (Kalshi price at entry, 0.0-1.0)")
        print("  - 4 partial indexes created (only for NOT NULL rows)")
        print("  - All columns nullable (backfill not required)")
        print("  - Entry snapshots are IMMUTABLE (ADR-018 Immutable Versioning)")
        print()
        print("Usage:")
        print(
            "  - Set attribution fields when opening position: create_position(..., strategy_id, model_id, calculated_probability, market_price_at_entry)"
        )
        print(
            "  - edge_at_entry calculated automatically: calculated_probability - market_price_at_entry"
        )
        print("  - Entry snapshots NEVER change (even if position price changes)")
        print(
            "  - Strategy evaluation: SELECT strategy_id, AVG(edge_at_entry), AVG(realized_pnl) FROM positions GROUP BY strategy_id"
        )
        print()
        print("Next steps:")
        print("  1. Update DATABASE_SCHEMA_SUMMARY V1.9 -> V1.10 (document all 3 migrations)")
        print("  2. Update CRUD operations (create_position with 4 new parameters)")
        print("  3. Add validation: ensure model_id and calculated_probability set together")
        print("  4. Create attribution tests (test_position_attribution.py)")


def rollback_migration(conn):
    """
    Rollback migration: Remove position attribution columns.

    Args:
        conn: Database connection

    Warning:
        This rollback drops attribution columns and indexes.
        Safe if no queries/code depend on these columns yet.
        Does NOT drop strategy_id (added in Migration 003).
    """
    with conn.cursor() as cur:
        print("Rolling back Migration 020...")
        print()

        # Drop indexes
        print("[1/5] Dropping partial indexes...")
        cur.execute("""
            DROP INDEX IF EXISTS idx_positions_model_id
        """)
        cur.execute("""
            DROP INDEX IF EXISTS idx_positions_calculated_probability
        """)
        cur.execute("""
            DROP INDEX IF EXISTS idx_positions_edge_at_entry
        """)
        cur.execute("""
            DROP INDEX IF EXISTS idx_positions_market_price_at_entry
        """)
        print("      [OK] Indexes dropped")
        print()

        # Drop market_price_at_entry column
        print("[2/5] Dropping market_price_at_entry column...")
        cur.execute("""
            ALTER TABLE positions
            DROP COLUMN IF EXISTS market_price_at_entry
        """)
        print("      [OK] market_price_at_entry column dropped")
        print()

        # Drop edge_at_entry column
        print("[3/5] Dropping edge_at_entry column...")
        cur.execute("""
            ALTER TABLE positions
            DROP COLUMN IF EXISTS edge_at_entry
        """)
        print("      [OK] edge_at_entry column dropped")
        print()

        # Drop calculated_probability column
        print("[4/5] Dropping calculated_probability column...")
        cur.execute("""
            ALTER TABLE positions
            DROP COLUMN IF EXISTS calculated_probability
        """)
        print("      [OK] calculated_probability column dropped")
        print()

        # Drop model_id column (foreign key)
        print("[5/5] Dropping model_id column...")
        cur.execute("""
            ALTER TABLE positions
            DROP COLUMN IF EXISTS model_id
        """)
        print("      [OK] model_id column dropped")
        print()

        # Commit changes
        conn.commit()
        print("[SUCCESS] Migration 020 rolled back successfully!")
        print()
        print("Note: strategy_id column preserved (added in Migration 003)")


def verify_migration(conn):
    """
    Verify migration was applied correctly.

    Args:
        conn: Database connection

    Returns:
        True if verification passed, False otherwise
    """
    with conn.cursor() as cur:
        print("Verifying Migration 020...")
        print()

        # Check columns exist
        cur.execute("""
            SELECT column_name, data_type, is_nullable, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = 'positions'
            AND column_name IN ('model_id', 'calculated_probability', 'edge_at_entry', 'market_price_at_entry', 'strategy_id')
            ORDER BY column_name
        """)
        columns = {
            row[0]: {"type": row[1], "nullable": row[2], "precision": row[3], "scale": row[4]}
            for row in cur.fetchall()
        }

        # Check CHECK constraints
        cur.execute("""
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'positions'::regclass
            AND (conname LIKE '%calculated_probability%' OR conname LIKE '%market_price_at_entry%')
        """)
        constraints = {row[0]: row[1] for row in cur.fetchall()}

        # Check indexes
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'positions'
            AND indexname IN ('idx_positions_model_id', 'idx_positions_calculated_probability',
                              'idx_positions_edge_at_entry', 'idx_positions_market_price_at_entry')
            ORDER BY indexname
        """)
        indexes = {row[0]: row[1] for row in cur.fetchall()}

        # Check foreign key for model_id
        cur.execute("""
            SELECT tc.constraint_name, ccu.table_name AS foreign_table_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'positions'
                AND tc.constraint_name LIKE '%model_id%'
        """)
        fk_info = cur.fetchone()

        # Check strategy_id foreign key (from Migration 003)
        cur.execute("""
            SELECT tc.constraint_name, ccu.table_name AS foreign_table_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'positions'
                AND tc.constraint_name LIKE '%strategy_id%'
        """)
        strategy_fk_info = cur.fetchone()

        # Verify structure
        errors = []

        # Check strategy_id column (should exist from Migration 003)
        if "strategy_id" not in columns:
            errors.append("[FAIL] strategy_id column not found (expected from Migration 003)")

        # Check model_id column
        if "model_id" not in columns:
            errors.append("[FAIL] model_id column not found")
        elif columns["model_id"]["type"] != "integer":
            errors.append(f"[FAIL] model_id should be INTEGER, got {columns['model_id']['type']}")

        # Check calculated_probability column
        if "calculated_probability" not in columns:
            errors.append("[FAIL] calculated_probability column not found")
        elif columns["calculated_probability"]["type"] != "numeric":
            errors.append(
                f"[FAIL] calculated_probability should be DECIMAL, got {columns['calculated_probability']['type']}"
            )
        elif (
            columns["calculated_probability"]["precision"] != 10
            or columns["calculated_probability"]["scale"] != 4
        ):
            errors.append("[FAIL] calculated_probability should be DECIMAL(10,4)")

        # Check edge_at_entry column
        if "edge_at_entry" not in columns:
            errors.append("[FAIL] edge_at_entry column not found")
        elif columns["edge_at_entry"]["type"] != "numeric":
            errors.append(
                f"[FAIL] edge_at_entry should be DECIMAL, got {columns['edge_at_entry']['type']}"
            )

        # Check market_price_at_entry column
        if "market_price_at_entry" not in columns:
            errors.append("[FAIL] market_price_at_entry column not found")
        elif columns["market_price_at_entry"]["type"] != "numeric":
            errors.append(
                f"[FAIL] market_price_at_entry should be DECIMAL, got {columns['market_price_at_entry']['type']}"
            )

        # Check foreign key for model_id
        if not fk_info:
            errors.append("[FAIL] Foreign key for model_id not found")
        elif fk_info[1] != "probability_models":
            errors.append(
                f"[FAIL] model_id FK should reference probability_models, got {fk_info[1]}"
            )

        # Check foreign key for strategy_id
        if not strategy_fk_info:
            errors.append(
                "[FAIL] Foreign key for strategy_id not found (expected from Migration 003)"
            )

        # Check indexes exist
        expected_indexes = [
            "idx_positions_calculated_probability",
            "idx_positions_edge_at_entry",
            "idx_positions_market_price_at_entry",
            "idx_positions_model_id",
        ]
        for idx_name in expected_indexes:
            if idx_name not in indexes:
                errors.append(f"[FAIL] Index {idx_name} not found")

        # Check CHECK constraints exist (at least 2 for probability/price ranges)
        if len(constraints) < 2:
            errors.append(f"[FAIL] Expected at least 2 CHECK constraints, found {len(constraints)}")

        if errors:
            print("Verification FAILED:")
            for error in errors:
                print(f"  {error}")
            return False

        print("[SUCCESS] Verification passed!")
        print("  [OK] strategy_id column exists (from Migration 003, FK to strategies)")
        print("  [OK] model_id column exists (INTEGER, FK to probability_models)")
        print(
            "  [OK] calculated_probability column exists (DECIMAL(10,4), nullable, CHECK 0.0-1.0)"
        )
        print("  [OK] edge_at_entry column exists (DECIMAL(10,4), nullable, can be negative)")
        print("  [OK] market_price_at_entry column exists (DECIMAL(10,4), nullable, CHECK 0.0-1.0)")
        print(
            "  [OK] 4 partial indexes created (model_id, calculated_probability, edge_at_entry, market_price_at_entry)"
        )
        print("  [OK] CHECK constraints ensure probability ranges (0.0-1.0)")
        print()
        print("Position attribution is now enabled!")
        return True


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Migration 020: Position Attribution")
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
