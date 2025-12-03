-- Migration 009: Fix markets Table SCD Type 2 with Surrogate PRIMARY KEY
-- Date: 2025-10-24
-- Phase: 1 (Foundation Completion)
-- Purpose: Replace business key PRIMARY KEY with surrogate key to enable SCD Type 2 versioning

-- ============================================================================
-- BACKGROUND: The Problem
-- ============================================================================
-- Current state:
--   markets.market_id VARCHAR PRIMARY KEY
--
-- Problem:
--   SCD Type 2 requires multiple rows with same market_id (different versions)
--   PRIMARY KEY constraint prevents duplicate market_id values
--   Result: 4 failing tests (test_scd_type2_versioning, etc.)
--
-- Solution:
--   Add surrogate PRIMARY KEY (id SERIAL)
--   Make market_id a business key (non-unique, multiple versions allowed)
--   Add UNIQUE constraint: (market_id, row_current_ind) WHERE row_current_ind = TRUE
--   Update all FK references to use surrogate key

-- ============================================================================
-- STEP 1: Add surrogate PRIMARY KEY column
-- ============================================================================

-- Add id column (will become PRIMARY KEY)
ALTER TABLE markets
ADD COLUMN IF NOT EXISTS id SERIAL;

-- ============================================================================
-- STEP 2: Create temporary junction columns on FK tables
-- ============================================================================
-- These will store the new surrogate key (markets.id) while we transition

-- edges table
ALTER TABLE edges
ADD COLUMN IF NOT EXISTS market_uuid INT;

COMMENT ON COLUMN edges.market_uuid IS 'Surrogate FK to markets.id (replaces market_id business key)';

-- positions table (if it has market FK)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS market_uuid INT;

COMMENT ON COLUMN positions.market_uuid IS 'Surrogate FK to markets.id (replaces market_id business key)';

-- trades table (if it has market FK)
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS market_uuid INT;

COMMENT ON COLUMN trades.market_uuid IS 'Surrogate FK to markets.id (replaces market_id business key)';

-- settlements table
ALTER TABLE settlements
ADD COLUMN IF NOT EXISTS market_uuid INT;

COMMENT ON COLUMN settlements.market_uuid IS 'Surrogate FK to markets.id (replaces market_id business key)';

-- ============================================================================
-- STEP 3: Backfill surrogate FKs
-- ============================================================================
-- For existing data, populate market_uuid by looking up markets.id from market_id

-- edges: Join to markets on business key, get surrogate key
UPDATE edges e
SET market_uuid = m.id
FROM markets m
WHERE e.market_id = m.market_id
AND m.row_current_ind = TRUE  -- Link to current version
AND e.market_uuid IS NULL;

-- positions: Join to markets on business key, get surrogate key
UPDATE positions p
SET market_uuid = m.id
FROM markets m
WHERE p.market_id = m.market_id
AND m.row_current_ind = TRUE  -- Link to current version
AND p.market_uuid IS NULL;

-- trades: Join to markets on business key, get surrogate key
UPDATE trades t
SET market_uuid = m.id
FROM markets m
WHERE t.market_id = m.market_id
AND m.row_current_ind = TRUE  -- Link to current version
AND t.market_uuid IS NULL;

-- settlements: Join to markets on business key
UPDATE settlements s
SET market_uuid = m.id
FROM markets m
WHERE s.market_id = m.market_id
AND m.row_current_ind = TRUE
AND s.market_uuid IS NULL;

-- ============================================================================
-- STEP 4: Drop old PRIMARY KEY and FK constraints
-- ============================================================================

-- Drop FK constraints pointing to markets.market_id
DO $$
BEGIN
    -- edges FK
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'edges_market_id_fkey'
    ) THEN
        ALTER TABLE edges DROP CONSTRAINT edges_market_id_fkey;
    END IF;

    -- positions FK
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'positions_market_id_fkey'
    ) THEN
        ALTER TABLE positions DROP CONSTRAINT positions_market_id_fkey;
    END IF;

    -- trades FK
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'trades_market_id_fkey'
    ) THEN
        ALTER TABLE trades DROP CONSTRAINT trades_market_id_fkey;
    END IF;

    -- settlements FK
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'settlements_market_id_fkey'
    ) THEN
        ALTER TABLE settlements DROP CONSTRAINT settlements_market_id_fkey;
    END IF;
END $$;

-- Drop markets PRIMARY KEY
ALTER TABLE markets DROP CONSTRAINT IF EXISTS markets_pkey;

-- ============================================================================
-- STEP 5: Add new PRIMARY KEY and constraints
-- ============================================================================

-- Add surrogate PRIMARY KEY
ALTER TABLE markets ADD PRIMARY KEY (id);

-- Add UNIQUE constraint for current version of each business key
-- This ensures only ONE current version per market_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_markets_unique_current
ON markets(market_id)
WHERE row_current_ind = TRUE;

COMMENT ON INDEX idx_markets_unique_current IS 'Ensures only one current version per market_id (SCD Type 2 enforcement)';

-- ============================================================================
-- STEP 6: Add new FK constraints using surrogate key
-- ============================================================================

-- edges -> markets
ALTER TABLE edges
ADD CONSTRAINT fk_edges_market_uuid
FOREIGN KEY (market_uuid) REFERENCES markets(id);

CREATE INDEX IF NOT EXISTS idx_edges_market_uuid
ON edges(market_uuid);

-- positions -> markets
ALTER TABLE positions
ADD CONSTRAINT fk_positions_market_uuid
FOREIGN KEY (market_uuid) REFERENCES markets(id);

CREATE INDEX IF NOT EXISTS idx_positions_market_uuid
ON positions(market_uuid);

-- trades -> markets
ALTER TABLE trades
ADD CONSTRAINT fk_trades_market_uuid
FOREIGN KEY (market_uuid) REFERENCES markets(id);

CREATE INDEX IF NOT EXISTS idx_trades_market_uuid
ON trades(market_uuid);

-- settlements -> markets
ALTER TABLE settlements
ADD CONSTRAINT fk_settlements_market_uuid
FOREIGN KEY (market_uuid) REFERENCES markets(id);

CREATE INDEX IF NOT EXISTS idx_settlements_market_uuid
ON settlements(market_uuid);

-- ============================================================================
-- STEP 7: (Optional) Deprecate old market_id columns on FK tables
-- ============================================================================
-- Keep market_id columns for now (backward compatibility and human readability)
-- But mark as deprecated in comments

COMMENT ON COLUMN edges.market_id IS '[DEPRECATED] Business key - use market_uuid for FK joins. Kept for backward compatibility and human readability.';
COMMENT ON COLUMN positions.market_id IS '[DEPRECATED] Business key - use market_uuid for FK joins. Kept for backward compatibility and human readability.';
COMMENT ON COLUMN trades.market_id IS '[DEPRECATED] Business key - use market_uuid for FK joins. Kept for backward compatibility and human readability.';
COMMENT ON COLUMN settlements.market_id IS '[DEPRECATED] Business key - use market_uuid for FK joins. Kept for backward compatibility and human readability.';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    pk_column VARCHAR;
    unique_index_exists BOOLEAN;
BEGIN
    -- Check that markets.id is PRIMARY KEY
    SELECT a.attname INTO pk_column
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
    WHERE i.indrelid = 'markets'::regclass
    AND i.indisprimary
    LIMIT 1;

    IF pk_column IS NULL OR pk_column != 'id' THEN
        RAISE EXCEPTION 'Migration 009 failed: markets.id is not PRIMARY KEY';
    END IF;

    -- Check that UNIQUE constraint exists on (market_id WHERE row_current_ind = TRUE)
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'markets'
        AND indexname = 'idx_markets_unique_current'
    ) INTO unique_index_exists;

    IF NOT unique_index_exists THEN
        RAISE EXCEPTION 'Migration 009 failed: UNIQUE constraint on current market_id missing';
    END IF;

    -- Check FK columns exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'edges' AND column_name = 'market_uuid'
    ) THEN
        RAISE EXCEPTION 'Migration 009 failed: edges.market_uuid column missing';
    END IF;

    RAISE NOTICE 'Migration 009 successful: markets now uses surrogate PRIMARY KEY (id), FK tables updated';
END $$;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
-- Going forward, when creating/updating records:
--
-- OLD WAY (will fail on SCD Type 2 updates):
-- INSERT INTO markets (market_id, ...) VALUES ('MKT-NFL-KC-WIN', ...);
-- -- Later update fails: duplicate key violates PRIMARY KEY
--
-- NEW WAY (SCD Type 2 compatible):
-- 1. Create new market:
--    INSERT INTO markets (market_id, ...) VALUES ('MKT-NFL-KC-WIN', ...)
--    RETURNING id;  -- Get surrogate key
--
-- 2. Update market (creates new version):
--    -- Mark old version historical
--    UPDATE markets
--    SET row_current_ind = FALSE, row_end_ts = NOW()
--    WHERE market_id = 'MKT-NFL-KC-WIN' AND row_current_ind = TRUE;
--
--    -- Insert new version (same market_id, new surrogate id)
--    INSERT INTO markets (market_id, platform_id, ..., row_current_ind)
--    VALUES ('MKT-NFL-KC-WIN', ..., TRUE)
--    RETURNING id;  -- New surrogate key for new version
--
-- 3. Link edges/positions to market:
--    INSERT INTO edges (market_uuid, ...)
--    VALUES (123, ...);  -- Use surrogate id, not market_id
--
-- Queries:
-- -- Get current version of market
-- SELECT * FROM markets
-- WHERE market_id = 'MKT-NFL-KC-WIN' AND row_current_ind = TRUE;
--
-- -- Get all versions (historical)
-- SELECT * FROM markets
-- WHERE market_id = 'MKT-NFL-KC-WIN'
-- ORDER BY created_at;
--
-- -- Join edges to current market
-- SELECT e.*, m.*
-- FROM edges e
-- JOIN markets m ON e.market_uuid = m.id
-- WHERE m.row_current_ind = TRUE;
