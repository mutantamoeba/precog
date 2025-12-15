-- Migration 006: Add trade_metadata column
-- Date: 2025-10-24
-- Phase: 1 (Foundation Completion)
-- Purpose: Add missing trade_metadata column to trades table

-- ============================================================================
-- TRADES TABLE: Add trade_metadata column
-- ============================================================================

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS trade_metadata JSONB;

COMMENT ON COLUMN trades.trade_metadata IS 'Additional flexible metadata for trades as JSON';

-- Create GIN index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_trades_metadata
ON trades USING GIN (trade_metadata)
WHERE trade_metadata IS NOT NULL;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trades' AND column_name = 'trade_metadata'
    ) THEN
        RAISE EXCEPTION 'Migration 006 failed: trade_metadata column missing';
    ELSE
        RAISE NOTICE 'Migration 006 successful: trade_metadata column added to trades table';
    END IF;
END $$;
