-- Migration: Schema v1.4 → v1.5
-- Date: 2025-10-21
-- Purpose: Add position monitoring and exit management for Phase 5
-- Phase: 0.5 (Foundation Enhancement)
--
-- CHANGES:
-- 1. Add position_exits table (track each exit event including partial exits)
-- 2. Add exit_attempts table (debug exit execution and price walking)
-- 3. Add monitoring fields to positions (current_price, unrealized_pnl_pct, last_update)
-- 4. Add exit tracking fields to positions (exit_reason, exit_priority)
--
-- ROLLBACK: See schema_v1.5_to_v1.4_rollback.sql

BEGIN;

-- ============================================================================
-- 1. CREATE position_exits TABLE
-- ============================================================================
-- Purpose: Track each exit event (including partial exits)
-- Pattern: Append-only (exits are immutable historical events)

CREATE TABLE IF NOT EXISTS position_exits (
    exit_id SERIAL PRIMARY KEY,
    position_id INTEGER NOT NULL REFERENCES positions(position_id) ON DELETE CASCADE,
    exit_condition VARCHAR(50) NOT NULL CHECK (exit_condition IN (
        'stop_loss', 'circuit_breaker', 'trailing_stop', 'time_based_urgent',
        'liquidity_dried_up', 'profit_target', 'partial_exit_target',
        'early_exit', 'edge_disappeared', 'rebalance'
    )),
    exit_priority VARCHAR(20) NOT NULL CHECK (exit_priority IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    quantity_exited INTEGER NOT NULL CHECK (quantity_exited > 0),
    exit_price DECIMAL(10,4) NOT NULL CHECK (exit_price >= 0.0000 AND exit_price <= 1.0000),
    unrealized_pnl_at_exit DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT NOW()
    -- ❌ NO row_current_ind (exits are immutable events)
);

CREATE INDEX IF NOT EXISTS idx_position_exits_position ON position_exits(position_id);
CREATE INDEX IF NOT EXISTS idx_position_exits_condition ON position_exits(exit_condition);
CREATE INDEX IF NOT EXISTS idx_position_exits_priority ON position_exits(exit_priority);
CREATE INDEX IF NOT EXISTS idx_position_exits_created ON position_exits(created_at);

COMMENT ON TABLE position_exits IS 'Track each exit event including partial exits - Phase 5. Append-only table for historical exit records.';
COMMENT ON COLUMN position_exits.exit_condition IS 'Which exit condition triggered: stop_loss, trailing_stop, profit_target, etc.';
COMMENT ON COLUMN position_exits.exit_priority IS 'Priority level when exit triggered: CRITICAL, HIGH, MEDIUM, LOW';
COMMENT ON COLUMN position_exits.quantity_exited IS 'Number of contracts exited (supports partial exits)';
COMMENT ON COLUMN position_exits.exit_price IS 'Actual fill price for this exit (0.0000-1.0000)';

-- ============================================================================
-- 2. CREATE exit_attempts TABLE
-- ============================================================================
-- Purpose: Debug exit execution - track price walking and order attempts
-- Pattern: Append-only (attempts are immutable logs)

CREATE TABLE IF NOT EXISTS exit_attempts (
    attempt_id SERIAL PRIMARY KEY,
    position_id INTEGER NOT NULL REFERENCES positions(position_id) ON DELETE CASCADE,
    exit_condition VARCHAR(50) NOT NULL CHECK (exit_condition IN (
        'stop_loss', 'circuit_breaker', 'trailing_stop', 'time_based_urgent',
        'liquidity_dried_up', 'profit_target', 'partial_exit_target',
        'early_exit', 'edge_disappeared', 'rebalance'
    )),
    priority_level VARCHAR(20) NOT NULL CHECK (priority_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('market', 'limit')),
    limit_price DECIMAL(10,4) CHECK (limit_price IS NULL OR (limit_price >= 0.0000 AND limit_price <= 1.0000)),
    fill_price DECIMAL(10,4) CHECK (fill_price IS NULL OR (fill_price >= 0.0000 AND fill_price <= 1.0000)),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    timeout_seconds INTEGER CHECK (timeout_seconds IS NULL OR timeout_seconds > 0),
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
    -- ❌ NO row_current_ind (attempts are immutable logs)
);

CREATE INDEX IF NOT EXISTS idx_exit_attempts_position ON exit_attempts(position_id);
CREATE INDEX IF NOT EXISTS idx_exit_attempts_condition ON exit_attempts(exit_condition);
CREATE INDEX IF NOT EXISTS idx_exit_attempts_success ON exit_attempts(success);
CREATE INDEX IF NOT EXISTS idx_exit_attempts_created ON exit_attempts(created_at);

COMMENT ON TABLE exit_attempts IS 'Debug exit execution - track price walking and order attempts - Phase 5. Answers "Why did not my exit fill?"';
COMMENT ON COLUMN exit_attempts.order_type IS 'market or limit order';
COMMENT ON COLUMN exit_attempts.limit_price IS 'Limit price if order_type = limit (NULL for market orders)';
COMMENT ON COLUMN exit_attempts.fill_price IS 'Actual fill price (NULL if did not fill)';
COMMENT ON COLUMN exit_attempts.attempt_number IS '1st attempt, 2nd walk, 3rd walk, etc.';
COMMENT ON COLUMN exit_attempts.timeout_seconds IS 'Timeout before next attempt (NULL if last attempt)';
COMMENT ON COLUMN exit_attempts.success IS 'Did this attempt result in fill?';

-- ============================================================================
-- 3. ALTER positions - Add monitoring fields
-- ============================================================================

DO $$
BEGIN
    -- Add current_price (updated by monitoring loop)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = 'current_price'
    ) THEN
        ALTER TABLE positions ADD COLUMN current_price DECIMAL(10,4) CHECK (current_price IS NULL OR (current_price >= 0.0000 AND current_price <= 1.0000));
        COMMENT ON COLUMN positions.current_price IS 'Latest market price from monitoring loop - Phase 5 (updated every 30s normal, 5s urgent)';
    END IF;

    -- Add unrealized_pnl_pct (calculated as percentage)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = 'unrealized_pnl_pct'
    ) THEN
        ALTER TABLE positions ADD COLUMN unrealized_pnl_pct DECIMAL(6,4);
        COMMENT ON COLUMN positions.unrealized_pnl_pct IS 'Unrealized P&L as percentage (e.g., 0.1234 = 12.34%) - Phase 5. Calculated as (current_price - entry_price) / entry_price';
    END IF;

    -- Add last_update (monitoring loop health check)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = 'last_update'
    ) THEN
        ALTER TABLE positions ADD COLUMN last_update TIMESTAMP;
        CREATE INDEX IF NOT EXISTS idx_positions_last_update ON positions(last_update);
        COMMENT ON COLUMN positions.last_update IS 'Last monitoring check timestamp - Phase 5. Alert if stale (>60s)';
    END IF;

    -- Add exit_reason (which exit condition triggered)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = 'exit_reason'
    ) THEN
        ALTER TABLE positions ADD COLUMN exit_reason VARCHAR(50) CHECK (exit_reason IS NULL OR exit_reason IN (
            'stop_loss', 'circuit_breaker', 'trailing_stop', 'time_based_urgent',
            'liquidity_dried_up', 'profit_target', 'partial_exit_target',
            'early_exit', 'edge_disappeared', 'rebalance'
        ));
        COMMENT ON COLUMN positions.exit_reason IS 'Which exit condition triggered: stop_loss, trailing_stop, profit_target, etc. - Phase 5';
    END IF;

    -- Add exit_priority (priority level when exit triggered)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = 'exit_priority'
    ) THEN
        ALTER TABLE positions ADD COLUMN exit_priority VARCHAR(20) CHECK (exit_priority IS NULL OR exit_priority IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW'));
        COMMENT ON COLUMN positions.exit_priority IS 'Priority level when exit triggered: CRITICAL, HIGH, MEDIUM, LOW - Phase 5';
    END IF;
END $$;

-- ============================================================================
-- 4. CREATE HELPER VIEWS FOR MONITORING
-- ============================================================================

-- Positions requiring urgent monitoring (near thresholds)
CREATE OR REPLACE VIEW positions_urgent_monitoring AS
SELECT
    p.*,
    CASE
        WHEN p.current_price IS NULL THEN FALSE
        WHEN p.trailing_stop_state->>'active' = 'true'
             AND ABS(p.current_price - CAST(p.trailing_stop_state->>'current_stop_price' AS DECIMAL(10,4))) / p.current_price < 0.02 THEN TRUE
        WHEN p.unrealized_pnl_pct IS NOT NULL
             AND p.unrealized_pnl_pct < -0.13 THEN TRUE  -- Within 2% of -15% stop loss
        ELSE FALSE
    END as is_urgent
FROM positions p
WHERE p.row_current_ind = TRUE AND p.status = 'open';

COMMENT ON VIEW positions_urgent_monitoring IS 'Positions requiring 5s monitoring frequency (within 2% of thresholds) - Phase 5';

-- Exit performance summary
CREATE OR REPLACE VIEW exit_performance_summary AS
SELECT
    pe.exit_condition,
    pe.exit_priority,
    COUNT(*) as total_exits,
    AVG(pe.unrealized_pnl_at_exit) as avg_pnl_at_exit,
    COUNT(DISTINCT pe.position_id) as unique_positions,
    AVG(ea.attempt_number) as avg_attempts_to_fill
FROM position_exits pe
LEFT JOIN exit_attempts ea ON pe.position_id = ea.position_id
    AND pe.exit_condition = ea.exit_condition
    AND ea.success = TRUE
GROUP BY pe.exit_condition, pe.exit_priority;

COMMENT ON VIEW exit_performance_summary IS 'Exit condition performance metrics - Phase 5. Shows avg P&L and fill attempts per exit type';

-- Stale position alerts (monitoring loop health)
CREATE OR REPLACE VIEW stale_position_alerts AS
SELECT
    p.position_id,
    p.market_id,
    p.side,
    p.quantity,
    p.entry_price,
    p.current_price,
    p.unrealized_pnl_pct,
    p.last_update,
    EXTRACT(EPOCH FROM (NOW() - p.last_update)) as seconds_since_update
FROM positions p
WHERE p.row_current_ind = TRUE
  AND p.status = 'open'
  AND p.last_update IS NOT NULL
  AND p.last_update < NOW() - INTERVAL '60 seconds';

COMMENT ON VIEW stale_position_alerts IS 'Positions with stale monitoring data (>60s since update) - Phase 5. Indicates monitoring loop issues';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Run these to verify migration succeeded:

-- 1. Check new tables exist
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('position_exits', 'exit_attempts');

-- 2. Check new columns added to positions
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'positions' AND column_name IN ('current_price', 'unrealized_pnl_pct', 'last_update', 'exit_reason', 'exit_priority');

-- 3. Check indexes created
-- SELECT indexname FROM pg_indexes WHERE schemaname = 'public'
-- AND indexname IN ('idx_position_exits_position', 'idx_exit_attempts_position', 'idx_positions_last_update');

-- 4. Check views created
-- SELECT viewname FROM pg_views WHERE schemaname = 'public'
-- AND viewname IN ('positions_urgent_monitoring', 'exit_performance_summary', 'stale_position_alerts');

-- 5. Verify CHECK constraints
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
-- WHERE conrelid = 'position_exits'::regclass AND contype = 'c';

-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

-- Example 1: Record a partial exit
-- INSERT INTO position_exits (position_id, exit_condition, exit_priority, quantity_exited, exit_price, unrealized_pnl_at_exit)
-- VALUES (123, 'partial_exit_target', 'MEDIUM', 50, 0.6900, 4.50);

-- Example 2: Record exit attempt (price walking)
-- INSERT INTO exit_attempts (position_id, exit_condition, priority_level, order_type, limit_price, quantity, attempt_number, timeout_seconds, success)
-- VALUES (123, 'stop_loss', 'CRITICAL', 'limit', 0.8500, 100, 1, 10, FALSE);

-- Example 3: Check for urgent monitoring positions
-- SELECT * FROM positions_urgent_monitoring WHERE is_urgent = TRUE;

-- Example 4: Exit condition performance
-- SELECT * FROM exit_performance_summary ORDER BY total_exits DESC;

-- Example 5: Check for stale monitoring data
-- SELECT * FROM stale_position_alerts;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
