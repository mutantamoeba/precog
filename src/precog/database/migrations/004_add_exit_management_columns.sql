-- Migration 004: Add Exit Management and Position Tracking Columns
-- Date: 2025-10-24
-- Phase: 1 (Foundation Completion)
-- Purpose: Sync database schema with DATABASE_SCHEMA_SUMMARY V1.6 and CRUD operations

-- ============================================================================
-- POSITIONS TABLE: Add missing exit management and tracking columns
-- ============================================================================

-- Exit Management Columns (for risk management)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS target_price DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS stop_loss_price DECIMAL(10,4);

-- Time Tracking Columns (replace generic created_at/updated_at)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS entry_time TIMESTAMP DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS exit_time TIMESTAMP,
ADD COLUMN IF NOT EXISTS last_check_time TIMESTAMP;

-- Exit Price Column (for closed positions)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS exit_price DECIMAL(10,4);

-- Position Metadata (flexible JSONB storage)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS position_metadata JSONB;

-- ============================================================================
-- COMMENTS (Documentation)
-- ============================================================================

COMMENT ON COLUMN positions.target_price IS 'Target exit price for profit taking';
COMMENT ON COLUMN positions.stop_loss_price IS 'Stop loss price for risk management';
COMMENT ON COLUMN positions.entry_time IS 'Timestamp when position was entered (replaces created_at)';
COMMENT ON COLUMN positions.exit_time IS 'Timestamp when position was exited/closed';
COMMENT ON COLUMN positions.last_check_time IS 'Last time position was checked by monitoring loop';
COMMENT ON COLUMN positions.exit_price IS 'Actual exit price when position was closed';
COMMENT ON COLUMN positions.position_metadata IS 'Additional flexible metadata as JSON';

-- ============================================================================
-- INDEXES (Query Performance)
-- ============================================================================

-- Index for positions with profit targets
CREATE INDEX IF NOT EXISTS idx_positions_target_price
ON positions(target_price)
WHERE target_price IS NOT NULL AND status = 'open';

-- Index for positions with stop losses
CREATE INDEX IF NOT EXISTS idx_positions_stop_loss
ON positions(stop_loss_price)
WHERE stop_loss_price IS NOT NULL AND status = 'open';

-- Index for monitoring queries (find stale positions)
CREATE INDEX IF NOT EXISTS idx_positions_last_check
ON positions(last_check_time)
WHERE status = 'open' AND row_current_ind = TRUE;

-- ============================================================================
-- DATA MIGRATION (Backfill existing records)
-- ============================================================================

-- Backfill entry_time from created_at for existing records
UPDATE positions
SET entry_time = created_at
WHERE entry_time IS NULL AND created_at IS NOT NULL;

-- Backfill exit_time from updated_at for closed positions
UPDATE positions
SET exit_time = updated_at
WHERE exit_time IS NULL AND status = 'closed' AND updated_at IS NOT NULL;

-- Backfill last_check_time from last_update for existing records
UPDATE positions
SET last_check_time = last_update
WHERE last_check_time IS NULL AND last_update IS NOT NULL;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify all columns exist
DO $$
DECLARE
    missing_count INT;
BEGIN
    SELECT COUNT(*) INTO missing_count
    FROM (
        SELECT 'target_price' AS col
        UNION SELECT 'stop_loss_price'
        UNION SELECT 'entry_time'
        UNION SELECT 'exit_time'
        UNION SELECT 'last_check_time'
        UNION SELECT 'exit_price'
        UNION SELECT 'position_metadata'
    ) required
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = required.col
    );

    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Migration 004 failed: % columns still missing', missing_count;
    ELSE
        RAISE NOTICE 'Migration 004 successful: All 7 columns added to positions table';
    END IF;
END $$;

-- Display final schema
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'positions'
ORDER BY ordinal_position;
