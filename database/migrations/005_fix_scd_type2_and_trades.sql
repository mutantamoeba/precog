-- Migration 005: Fix SCD Type 2 Tracking and Trades Schema
-- Date: 2025-10-24
-- Phase: 1 (Foundation Completion)
-- Purpose: Add row_end_ts for SCD Type 2, order_type/execution_time for trades, fix CHECK constraints

-- ============================================================================
-- MARKETS TABLE: Add SCD Type 2 tracking column
-- ============================================================================

ALTER TABLE markets
ADD COLUMN IF NOT EXISTS row_end_ts TIMESTAMP;

COMMENT ON COLUMN markets.row_end_ts IS 'Timestamp when this row version became invalid (SCD Type 2)';

-- Create index for historical queries
CREATE INDEX IF NOT EXISTS idx_markets_row_end_ts
ON markets(row_end_ts)
WHERE row_end_ts IS NOT NULL;

-- ============================================================================
-- POSITIONS TABLE: Add SCD Type 2 tracking column
-- ============================================================================

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS row_end_ts TIMESTAMP;

COMMENT ON COLUMN positions.row_end_ts IS 'Timestamp when this row version became invalid (SCD Type 2)';

-- Create index for historical queries
CREATE INDEX IF NOT EXISTS idx_positions_row_end_ts
ON positions(row_end_ts)
WHERE row_end_ts IS NOT NULL;

-- ============================================================================
-- POSITIONS TABLE: Fix CHECK constraint for case-insensitive side values
-- ============================================================================

-- Drop old constraint
ALTER TABLE positions
DROP CONSTRAINT IF EXISTS positions_side_check;

-- Add new constraint accepting both uppercase and lowercase
ALTER TABLE positions
ADD CONSTRAINT positions_side_check
CHECK (LOWER(side) IN ('yes', 'no', 'long', 'short'));

COMMENT ON CONSTRAINT positions_side_check ON positions IS 'Case-insensitive side validation';

-- ============================================================================
-- TRADES TABLE: Add missing columns
-- ============================================================================

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS order_type VARCHAR DEFAULT 'market',
ADD COLUMN IF NOT EXISTS execution_time TIMESTAMP DEFAULT NOW();

COMMENT ON COLUMN trades.order_type IS 'Order type: market, limit, stop, etc.';
COMMENT ON COLUMN trades.execution_time IS 'Timestamp when trade was executed';

-- Add CHECK constraint for order_type
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'trades_order_type_check'
    ) THEN
        ALTER TABLE trades
        ADD CONSTRAINT trades_order_type_check
        CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit'));
    END IF;
END $$;

-- Backfill execution_time from created_at for existing trades
UPDATE trades
SET execution_time = created_at
WHERE execution_time IS NULL AND created_at IS NOT NULL;

-- Create index for execution time queries
CREATE INDEX IF NOT EXISTS idx_trades_execution_time
ON trades(execution_time);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    missing_count INT := 0;
    error_msg TEXT := '';
BEGIN
    -- Check markets.row_end_ts
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'markets' AND column_name = 'row_end_ts'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'markets.row_end_ts, ';
    END IF;

    -- Check positions.row_end_ts
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = 'row_end_ts'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'positions.row_end_ts, ';
    END IF;

    -- Check trades.order_type
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trades' AND column_name = 'order_type'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'trades.order_type, ';
    END IF;

    -- Check trades.execution_time
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trades' AND column_name = 'execution_time'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'trades.execution_time, ';
    END IF;

    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Migration 005 failed: Missing columns - %', error_msg;
    ELSE
        RAISE NOTICE 'Migration 005 successful: Added row_end_ts (2 tables), order_type, execution_time; Fixed positions CHECK constraint';
    END IF;
END $$;
