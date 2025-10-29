-- Migration 007: Complete SCD Type 2 Implementation (row_end_ts)
-- Date: 2025-10-24
-- Phase: 1 (Foundation Completion)
-- Purpose: Add row_end_ts to remaining SCD Type 2 tables for complete temporal tracking

-- ============================================================================
-- BACKGROUND: SCD Type 2 Pattern Requirements
-- ============================================================================
-- SCD Type 2 (Slowly Changing Dimension Type 2) requires TWO columns:
--   1. row_current_ind BOOLEAN - Which version is current? ✅ (all tables have)
--   2. row_end_ts TIMESTAMP - When did this version become invalid? ❌ (3 tables missing)
--
-- Without row_end_ts:
--   - Cannot query "What was the value at 2pm yesterday?"
--   - Cannot calculate "How long did each version last?"
--   - Incomplete audit trail for historical analysis
--
-- Tables already with row_end_ts (from migration 005):
--   - markets ✅
--   - positions ✅
--
-- Tables MISSING row_end_ts (this migration):
--   - edges ❌
--   - game_states ❌
--   - account_balance ❌

-- ============================================================================
-- EDGES TABLE: Add row_end_ts
-- ============================================================================

ALTER TABLE edges
ADD COLUMN IF NOT EXISTS row_end_ts TIMESTAMP;

COMMENT ON COLUMN edges.row_end_ts IS 'Timestamp when this edge version became invalid (SCD Type 2)';

-- Index for historical queries
CREATE INDEX IF NOT EXISTS idx_edges_row_end_ts
ON edges(row_end_ts)
WHERE row_end_ts IS NOT NULL;

-- ============================================================================
-- GAME_STATES TABLE: Add row_end_ts
-- ============================================================================

ALTER TABLE game_states
ADD COLUMN IF NOT EXISTS row_end_ts TIMESTAMP;

COMMENT ON COLUMN game_states.row_end_ts IS 'Timestamp when this game state became invalid (SCD Type 2)';

-- Index for historical queries
CREATE INDEX IF NOT EXISTS idx_game_states_row_end_ts
ON game_states(row_end_ts)
WHERE row_end_ts IS NOT NULL;

-- ============================================================================
-- ACCOUNT_BALANCE TABLE: Add row_end_ts
-- ============================================================================

ALTER TABLE account_balance
ADD COLUMN IF NOT EXISTS row_end_ts TIMESTAMP;

COMMENT ON COLUMN account_balance.row_end_ts IS 'Timestamp when this balance record became invalid (SCD Type 2)';

-- Index for historical queries
CREATE INDEX IF NOT EXISTS idx_account_balance_row_end_ts
ON account_balance(row_end_ts)
WHERE row_end_ts IS NOT NULL;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    missing_count INT := 0;
    error_msg TEXT := '';
BEGIN
    -- Check edges.row_end_ts
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'edges' AND column_name = 'row_end_ts'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'edges.row_end_ts, ';
    END IF;

    -- Check game_states.row_end_ts
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'game_states' AND column_name = 'row_end_ts'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'game_states.row_end_ts, ';
    END IF;

    -- Check account_balance.row_end_ts
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'account_balance' AND column_name = 'row_end_ts'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'account_balance.row_end_ts, ';
    END IF;

    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Migration 007 failed: Missing columns - %', error_msg;
    ELSE
        RAISE NOTICE 'Migration 007 successful: Added row_end_ts to 3 tables (edges, game_states, account_balance)';
    END IF;
END $$;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
-- CRUD operations must now set row_end_ts when marking rows historical:
--
-- Example: update_edge() function
-- UPDATE edges
-- SET row_current_ind = FALSE,
--     row_end_ts = NOW()
-- WHERE edge_id = %s AND row_current_ind = TRUE;
--
-- Historical Queries:
-- -- Get edge value at specific time
-- SELECT * FROM edges
-- WHERE edge_id = 42
-- AND created_at <= '2025-10-24 14:00:00'
-- AND (row_end_ts > '2025-10-24 14:00:00' OR row_end_ts IS NULL);
--
-- -- Calculate how long each version lasted
-- SELECT
--     edge_id,
--     created_at,
--     row_end_ts,
--     row_end_ts - created_at AS duration
-- FROM edges
-- WHERE edge_id = 42
-- ORDER BY created_at;
