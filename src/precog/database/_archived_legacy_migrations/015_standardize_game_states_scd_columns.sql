-- Migration 015: Standardize game_states SCD Type 2 Column Names
-- Date: 2025-11-30
-- Phase: 1.9 (Test Infrastructure & Process Hardening)
-- Purpose: Rename SCD Type 2 columns in game_states to match other tables
-- Related: Issue #165 (Phase 1.9), test_scd_type2_columns_exist failure

-- ============================================================================
-- BACKGROUND: Schema Naming Consistency
-- ============================================================================
-- Current state:
--   - markets, positions, edges use: row_end_ts
--   - game_states uses: row_start_timestamp, row_end_timestamp
--
-- Target state (consistent naming):
--   - All tables use: row_end_ts
--   - game_states will drop row_start_timestamp (not used by other tables)
--
-- Note: row_start_timestamp provides additional tracking but is not part of
-- the standard SCD Type 2 implementation in this codebase. The row_start_ts
-- functionality can be inferred from the row's creation timestamp or prior
-- version's row_end_ts.

-- ============================================================================
-- STEP 1: Rename row_end_timestamp to row_end_ts
-- ============================================================================

ALTER TABLE game_states
RENAME COLUMN row_end_timestamp TO row_end_ts;

-- ============================================================================
-- STEP 2: Keep row_start_timestamp but add alias comment
-- ============================================================================
-- Note: We keep row_start_timestamp for now as it contains data.
-- A future migration could drop it if the column is truly unused.
-- For now, we just ensure row_end_ts exists for consistency.

COMMENT ON COLUMN game_states.row_end_ts IS 'When this version was superseded (NULL for current row) - standardized SCD Type 2 naming';
COMMENT ON COLUMN game_states.row_start_timestamp IS 'When this version became current - NOTE: This column is game_states-specific, other tables do not have row_start_ts';

-- ============================================================================
-- STEP 3: Update indexes if any reference the old column name
-- ============================================================================
-- Check if any indexes need updating (none found that reference row_end_timestamp directly)

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    column_exists BOOLEAN;
BEGIN
    -- Check row_end_ts exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'game_states'
        AND column_name = 'row_end_ts'
    ) INTO column_exists;

    IF NOT column_exists THEN
        RAISE EXCEPTION 'Migration 015 failed: row_end_ts column not found in game_states';
    END IF;

    RAISE NOTICE 'Migration 015 successful: Renamed row_end_timestamp to row_end_ts in game_states';
END $$;

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================
-- ALTER TABLE game_states RENAME COLUMN row_end_ts TO row_end_timestamp;
