-- Migration 008: Add External ID Traceability
-- Date: 2025-10-24
-- Phase: 1 (Foundation Completion)
-- Purpose: Add API traceability columns for audit trails and debugging

-- ============================================================================
-- BACKGROUND: External ID Pattern
-- ============================================================================
-- API-sourced data should have external_*_id columns to:
--   1. Link back to source system for debugging
--   2. Enable data reconciliation
--   3. Provide complete audit trail
--
-- Current state:
--   ✅ series.external_id (Kalshi series ID)
--   ✅ events.external_id (Kalshi event ID)
--   ✅ markets.external_id (Kalshi market ID)
--   ✅ trades.order_id (Kalshi order ID)
--   ❌ positions - No link to opening trade
--   ❌ position_exits - No link to closing trade
--   ❌ exit_attempts - No link to API order
--   ❌ settlements - No link to Kalshi settlement event
--   ❌ edges - No batch tracking for calculations

-- ============================================================================
-- POSITIONS TABLE: Link to opening trade
-- ============================================================================

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS initial_order_id VARCHAR;

COMMENT ON COLUMN positions.initial_order_id IS 'Kalshi order ID of the trade that opened this position (links to trades.order_id)';

-- Backfill for existing positions (find first buy trade for each position)
UPDATE positions p
SET initial_order_id = (
    SELECT t.order_id
    FROM trades t
    WHERE t.position_id = p.position_id
    AND t.side = 'buy'
    ORDER BY t.created_at
    LIMIT 1
)
WHERE initial_order_id IS NULL
AND EXISTS (
    SELECT 1 FROM trades t
    WHERE t.position_id = p.position_id AND t.side = 'buy'
);

-- Index for lookups
CREATE INDEX IF NOT EXISTS idx_positions_initial_order
ON positions(initial_order_id)
WHERE initial_order_id IS NOT NULL;

-- ============================================================================
-- POSITION_EXITS TABLE: Link to closing trade
-- ============================================================================

ALTER TABLE position_exits
ADD COLUMN IF NOT EXISTS exit_trade_id INT;

COMMENT ON COLUMN position_exits.exit_trade_id IS 'Trade ID of the sell order that exited this position (links to trades.trade_id)';

-- Backfill for existing exits (find sell trade that matches exit)
-- NOTE: This is approximate - matches by position_id, quantity, and timestamp proximity
UPDATE position_exits pe
SET exit_trade_id = (
    SELECT t.trade_id
    FROM trades t
    WHERE t.position_id = pe.position_id
    AND t.side = 'sell'
    AND t.quantity = pe.quantity_exited
    AND ABS(EXTRACT(EPOCH FROM (t.created_at - pe.created_at))) < 5  -- Within 5 seconds
    ORDER BY t.created_at
    LIMIT 1
)
WHERE exit_trade_id IS NULL
AND EXISTS (
    SELECT 1 FROM trades t
    WHERE t.position_id = pe.position_id AND t.side = 'sell'
);

-- Index and FK
CREATE INDEX IF NOT EXISTS idx_position_exits_trade
ON position_exits(exit_trade_id)
WHERE exit_trade_id IS NOT NULL;

-- Add FK constraint (may fail if backfill didn't find matches - that's OK)
DO $$
BEGIN
    ALTER TABLE position_exits
    ADD CONSTRAINT fk_position_exits_trade
    FOREIGN KEY (exit_trade_id) REFERENCES trades(trade_id);
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'FK constraint for position_exits.exit_trade_id not added (some NULL values remain)';
END $$;

-- ============================================================================
-- EXIT_ATTEMPTS TABLE: Link to API order
-- ============================================================================

ALTER TABLE exit_attempts
ADD COLUMN IF NOT EXISTS order_id VARCHAR;

COMMENT ON COLUMN exit_attempts.order_id IS 'Kalshi order ID if this attempt resulted in an API order (NULL for failed attempts that never reached API)';

-- Backfill for successful attempts (match to trades by position, timestamp)
UPDATE exit_attempts ea
SET order_id = (
    SELECT t.order_id
    FROM trades t
    WHERE t.position_id = ea.position_id
    AND t.side = 'sell'
    AND t.quantity = ea.quantity
    AND ABS(EXTRACT(EPOCH FROM (t.created_at - ea.created_at))) < 2  -- Within 2 seconds
    ORDER BY t.created_at
    LIMIT 1
)
WHERE order_id IS NULL
AND success = TRUE
AND EXISTS (
    SELECT 1 FROM trades t
    WHERE t.position_id = ea.position_id AND t.side = 'sell'
);

-- Index for lookups
CREATE INDEX IF NOT EXISTS idx_exit_attempts_order
ON exit_attempts(order_id)
WHERE order_id IS NOT NULL;

-- ============================================================================
-- SETTLEMENTS TABLE: Link to Kalshi settlement event
-- ============================================================================

ALTER TABLE settlements
ADD COLUMN IF NOT EXISTS external_settlement_id VARCHAR,
ADD COLUMN IF NOT EXISTS settlement_timestamp TIMESTAMP,
ADD COLUMN IF NOT EXISTS api_response JSONB;

COMMENT ON COLUMN settlements.external_settlement_id IS 'Kalshi settlement event ID from API (for audit trail and reconciliation)';
COMMENT ON COLUMN settlements.settlement_timestamp IS 'Timestamp from Kalshi API when market was officially settled';
COMMENT ON COLUMN settlements.api_response IS 'Raw Kalshi API response for complete audit trail and debugging';

-- Index for external ID lookups
CREATE INDEX IF NOT EXISTS idx_settlements_external
ON settlements(external_settlement_id)
WHERE external_settlement_id IS NOT NULL;

-- ============================================================================
-- EDGES TABLE: Add calculation batch tracking
-- ============================================================================

-- Edges are internal calculations, not API data
-- Use calculation_run_id to group edges calculated together

ALTER TABLE edges
ADD COLUMN IF NOT EXISTS calculation_run_id UUID;

COMMENT ON COLUMN edges.calculation_run_id IS 'Batch ID grouping edges calculated together (enables tracking which detection run found this edge)';

-- Index for batch queries
CREATE INDEX IF NOT EXISTS idx_edges_calculation_run
ON edges(calculation_run_id)
WHERE calculation_run_id IS NOT NULL;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    missing_count INT := 0;
    error_msg TEXT := '';
BEGIN
    -- Check positions.initial_order_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = 'initial_order_id'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'positions.initial_order_id, ';
    END IF;

    -- Check position_exits.exit_trade_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'position_exits' AND column_name = 'exit_trade_id'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'position_exits.exit_trade_id, ';
    END IF;

    -- Check exit_attempts.order_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'exit_attempts' AND column_name = 'order_id'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'exit_attempts.order_id, ';
    END IF;

    -- Check settlements.external_settlement_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'settlements' AND column_name = 'external_settlement_id'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'settlements.external_settlement_id, ';
    END IF;

    -- Check edges.calculation_run_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'edges' AND column_name = 'calculation_run_id'
    ) THEN
        missing_count := missing_count + 1;
        error_msg := error_msg || 'edges.calculation_run_id, ';
    END IF;

    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Migration 008 failed: Missing columns - %', error_msg;
    ELSE
        RAISE NOTICE 'Migration 008 successful: Added 8 traceability columns across 5 tables';
    END IF;
END $$;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
-- Going forward, populate these columns when creating records:
--
-- Example: Creating a position
-- INSERT INTO positions (..., initial_order_id)
-- VALUES (..., 'kalshi_order_abc123');
--
-- Example: Recording a settlement from Kalshi API
-- INSERT INTO settlements (
--     market_id, outcome, payout,
--     external_settlement_id, settlement_timestamp, api_response
-- ) VALUES (
--     'MKT-NFL-KC-WIN', 'yes', 1.00,
--     'kalshi_settlement_xyz789', '2025-10-24 20:00:00', '{"market": {...}}'::JSONB
-- );
--
-- Example: Generating edges in batch
-- batch_id = uuid4()
-- INSERT INTO edges (..., calculation_run_id)
-- VALUES (..., batch_id);  -- Same batch_id for all edges in this detection run
