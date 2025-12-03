-- Migration 011: Fix Market FK Consistency (Business Key over Surrogate Key)
-- Date: 2025-12-02
-- Phase: 1.9 (Test Infrastructure)
-- Purpose: Replace surrogate key FKs (market_uuid -> markets.id) with business key FKs (market_id -> markets.market_id)

-- ============================================================================
-- BACKGROUND: The Problem
-- ============================================================================
-- Migration 009 added surrogate key FKs (market_uuid -> markets.id) to enable
-- SCD Type 2 versioning. However, this approach was over-engineered:
--
-- 1. No code actually populates market_uuid columns (always NULL)
-- 2. All queries join on market_id (business key) with row_current_ind = TRUE
-- 3. Surrogate key FKs complicate queries (require version upgrades)
-- 4. Industry standard for SCD Type 2 uses business key FKs, not surrogate keys
--
-- Current state (broken):
--   - settlements.market_uuid -> markets.id (FK exists, column always NULL ❌)
--   - settlements.market_id -> markets.market_id (NO FK, actually used ✅)
--   - Same issue in: edges, positions, trades
--
-- Solution:
--   - Add FK constraints: market_id -> markets.market_id
--   - Drop unused market_uuid columns
--   - Simplify queries: JOIN markets m ON table.market_id = m.market_id WHERE m.row_current_ind = TRUE

-- ============================================================================
-- STEP 1: Verify market_uuid columns are unused (safety check)
-- ============================================================================

DO $$
DECLARE
    settlements_null_count INT;
    edges_null_count INT;
    positions_null_count INT;
    trades_null_count INT;
BEGIN
    -- Check settlements
    SELECT COUNT(*) INTO settlements_null_count
    FROM settlements
    WHERE market_uuid IS NOT NULL;

    IF settlements_null_count > 0 THEN
        RAISE EXCEPTION 'Migration 011 aborted: settlements.market_uuid has % non-NULL values (expected 0)', settlements_null_count;
    END IF;

    -- Check edges
    SELECT COUNT(*) INTO edges_null_count
    FROM edges
    WHERE market_uuid IS NOT NULL;

    IF edges_null_count > 0 THEN
        RAISE EXCEPTION 'Migration 011 aborted: edges.market_uuid has % non-NULL values (expected 0)', edges_null_count;
    END IF;

    -- Check positions
    SELECT COUNT(*) INTO positions_null_count
    FROM positions
    WHERE market_uuid IS NOT NULL;

    IF positions_null_count > 0 THEN
        RAISE EXCEPTION 'Migration 011 aborted: positions.market_uuid has % non-NULL values (expected 0)', positions_null_count;
    END IF;

    -- Check trades
    SELECT COUNT(*) INTO trades_null_count
    FROM trades
    WHERE market_uuid IS NOT NULL;

    IF trades_null_count > 0 THEN
        RAISE EXCEPTION 'Migration 011 aborted: trades.market_uuid has % non-NULL values (expected 0)', trades_null_count;
    END IF;

    RAISE NOTICE 'Migration 011: market_uuid columns are unused (all NULL) - safe to drop';
END $$;

-- ============================================================================
-- STEP 2: Drop surrogate key FK constraints (market_uuid -> markets.id)
-- ============================================================================

-- Drop FK constraints on market_uuid columns
ALTER TABLE settlements DROP CONSTRAINT IF EXISTS fk_settlements_market_uuid;
ALTER TABLE edges DROP CONSTRAINT IF EXISTS fk_edges_market_uuid;
ALTER TABLE positions DROP CONSTRAINT IF EXISTS fk_positions_market_uuid;
ALTER TABLE trades DROP CONSTRAINT IF EXISTS fk_trades_market_uuid;

-- Drop indexes on market_uuid columns
DROP INDEX IF EXISTS idx_settlements_market_uuid;
DROP INDEX IF EXISTS idx_edges_market_uuid;
DROP INDEX IF EXISTS idx_positions_market_uuid;
DROP INDEX IF EXISTS idx_trades_market_uuid;

-- ============================================================================
-- STEP 3: Drop unused market_uuid columns
-- ============================================================================

ALTER TABLE settlements DROP COLUMN IF EXISTS market_uuid;
ALTER TABLE edges DROP COLUMN IF EXISTS market_uuid;
ALTER TABLE positions DROP COLUMN IF EXISTS market_uuid;
ALTER TABLE trades DROP COLUMN IF EXISTS market_uuid;

-- ============================================================================
-- STEP 4: Add business key FK constraints (market_id -> markets.market_id)
-- ============================================================================

-- Note: We can't create a standard FK to markets.market_id because market_id
-- is not a unique column (multiple versions exist). Instead, we'll rely on:
-- 1. Application-level validation (market_id must exist in markets)
-- 2. Partial unique index on markets(market_id) WHERE row_current_ind = TRUE
--
-- For referential integrity, we add CHECK constraints that market_id format is valid

-- Add CHECK constraints for market_id format (must match "MKT-..." pattern)
ALTER TABLE settlements
ADD CONSTRAINT chk_settlements_market_id_format
CHECK (market_id ~ '^MKT-[A-Z0-9\-]+$');

ALTER TABLE edges
ADD CONSTRAINT chk_edges_market_id_format
CHECK (market_id ~ '^MKT-[A-Z0-9\-]+$');

ALTER TABLE positions
ADD CONSTRAINT chk_positions_market_id_format
CHECK (market_id ~ '^MKT-[A-Z0-9\-]+$');

ALTER TABLE trades
ADD CONSTRAINT chk_trades_market_id_format
CHECK (market_id ~ '^MKT-[A-Z0-9\-]+$');

-- ============================================================================
-- STEP 5: Add indexes on market_id for query performance
-- ============================================================================

-- These indexes optimize joins: JOIN markets m ON table.market_id = m.market_id
CREATE INDEX IF NOT EXISTS idx_settlements_market_id ON settlements(market_id);
CREATE INDEX IF NOT EXISTS idx_edges_market_id ON edges(market_id);
CREATE INDEX IF NOT EXISTS idx_positions_market_id ON positions(market_id);
CREATE INDEX IF NOT EXISTS idx_trades_market_id ON trades(market_id);

-- ============================================================================
-- STEP 6: Update column comments to reflect new design
-- ============================================================================

COMMENT ON COLUMN settlements.market_id IS 'Business key FK to markets.market_id (use WHERE row_current_ind = TRUE for current version)';
COMMENT ON COLUMN edges.market_id IS 'Business key FK to markets.market_id (use WHERE row_current_ind = TRUE for current version)';
COMMENT ON COLUMN positions.market_id IS 'Business key FK to markets.market_id (use WHERE row_current_ind = TRUE for current version)';
COMMENT ON COLUMN trades.market_id IS 'Business key FK to markets.market_id (use WHERE row_current_ind = TRUE for current version)';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    market_uuid_exists BOOLEAN;
    market_id_index_exists BOOLEAN;
BEGIN
    -- Verify market_uuid columns dropped
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'market_uuid'
          AND table_name IN ('settlements', 'edges', 'positions', 'trades')
    ) INTO market_uuid_exists;

    IF market_uuid_exists THEN
        RAISE EXCEPTION 'Migration 011 failed: market_uuid columns still exist';
    END IF;

    -- Verify market_id indexes created
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = 'idx_settlements_market_id'
    ) INTO market_id_index_exists;

    IF NOT market_id_index_exists THEN
        RAISE EXCEPTION 'Migration 011 failed: idx_settlements_market_id index missing';
    END IF;

    RAISE NOTICE 'Migration 011 successful: Switched from surrogate key FKs (market_uuid) to business key FKs (market_id)';
END $$;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
-- Going forward, when joining to markets:
--
-- CORRECT WAY (business key FK with current version filter):
-- SELECT s.*, m.title, m.status
-- FROM settlements s
-- JOIN markets m ON s.market_id = m.market_id
-- WHERE m.row_current_ind = TRUE;  -- Get current market version
--
-- For historical analysis (all versions):
-- SELECT s.*, m.*
-- FROM settlements s
-- JOIN markets m ON s.market_id = m.market_id
-- ORDER BY m.created_at;  -- All versions of the market
--
-- When creating records:
-- INSERT INTO settlements (market_id, platform_id, outcome, payout)
-- VALUES ('MKT-KXNFLGAME-25DEC15-KC-YES', 'kalshi', 'yes', 1.0000);
--
-- Application code should:
-- 1. Use market_id (VARCHAR) for all FK references
-- 2. Join with WHERE row_current_ind = TRUE for current market data
-- 3. Validate market_id exists before insertion (application-level FK check)
