-- Migration: Schema v1.3 → v1.4
-- Date: 2025-10-18
-- Purpose: Add versioning support for strategies and models, trailing stop state for positions
-- Phase: 0.5 (Foundation Enhancement)
--
-- CHANGES:
-- 1. Add strategy versioning columns
-- 2. Add probability_models table with versioning
-- 3. Add trailing_stop_state to positions
-- 4. Add strategy_id, model_id FKs to edges and trades
--
-- ROLLBACK: See schema_v1.4_to_v1.3_rollback.sql

BEGIN;

-- ============================================================================
-- 1. CREATE probability_models TABLE (if not exists)
-- ============================================================================

CREATE TABLE IF NOT EXISTS probability_models (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    category VARCHAR(50) NOT NULL CHECK (category IN ('sports', 'politics', 'entertainment', 'economics', 'weather', 'other')),
    subcategory VARCHAR(50),
    config JSONB NOT NULL,

    -- Training information
    training_start_date DATE,
    training_end_date DATE,
    training_sample_size INTEGER CHECK (training_sample_size IS NULL OR training_sample_size >= 0),

    -- Lifecycle management (IMMUTABLE: once created, status cannot change - create new version instead)
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'training', 'validating', 'active', 'deprecated')),
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    notes TEXT,

    -- Validation metrics
    validation_accuracy DECIMAL(6,4) CHECK (validation_accuracy IS NULL OR (validation_accuracy >= 0.0000 AND validation_accuracy <= 1.0000)),
    validation_calibration DECIMAL(6,4) CHECK (validation_calibration IS NULL OR validation_calibration >= 0.0000),
    validation_sample_size INTEGER CHECK (validation_sample_size IS NULL OR validation_sample_size >= 0),

    created_at TIMESTAMP DEFAULT NOW(),
    -- NO row_current_ind: Versions are IMMUTABLE for A/B testing integrity

    UNIQUE(model_name, model_version),
    CONSTRAINT model_activation_order CHECK (deactivated_at IS NULL OR activated_at IS NULL OR deactivated_at >= activated_at)
);

CREATE INDEX IF NOT EXISTS idx_probability_models_status ON probability_models(status);
CREATE INDEX IF NOT EXISTS idx_probability_models_category ON probability_models(category, subcategory);

COMMENT ON TABLE probability_models IS 'IMMUTABLE versioned probability models (Elo, Regression, Ensemble) - Phase 4. Versions never change once created - use semantic versioning for updates (v1.0 → v1.1 for bug fix, v1.0 → v2.0 for major change)';
COMMENT ON COLUMN probability_models.model_version IS 'Semantic version (e.g., 1.0, 1.1, 2.0) - IMMUTABLE';
COMMENT ON COLUMN probability_models.status IS 'Lifecycle: draft → training → validating → active → deprecated. Update status by changing this column in-place (exception to immutability for lifecycle management)';

-- ============================================================================
-- 2. CREATE strategies TABLE (if not exists)
-- ============================================================================

CREATE TABLE IF NOT EXISTS strategies (
    strategy_id SERIAL PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
    strategy_name VARCHAR(100) NOT NULL,
    strategy_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    category VARCHAR(50) NOT NULL CHECK (category IN ('sports', 'politics', 'entertainment', 'economics', 'weather', 'other')),
    subcategory VARCHAR(50),
    config JSONB NOT NULL,

    -- Lifecycle management (IMMUTABLE: config never changes - create new version instead)
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'testing', 'active', 'inactive', 'deprecated')),
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    notes TEXT,

    -- Performance tracking (MUTABLE: metrics update as trades execute)
    paper_trades_count INTEGER DEFAULT 0 CHECK (paper_trades_count >= 0),
    paper_roi DECIMAL(10,4),
    live_trades_count INTEGER DEFAULT 0 CHECK (live_trades_count >= 0),
    live_roi DECIMAL(10,4),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    -- NO row_current_ind: Config is IMMUTABLE, only status and metrics update

    UNIQUE(strategy_name, strategy_version),
    CONSTRAINT strategy_activation_order CHECK (deactivated_at IS NULL OR activated_at IS NULL OR deactivated_at >= activated_at)
);

CREATE INDEX IF NOT EXISTS idx_strategies_status ON strategies(status);
CREATE INDEX IF NOT EXISTS idx_strategies_platform ON strategies(platform_id);

COMMENT ON TABLE strategies IS 'IMMUTABLE versioned trading strategies (halftime_entry, etc.) - Phase 5. Config never changes once created - use semantic versioning for updates (v1.0 → v1.1 for tweak, v1.0 → v2.0 for major change)';
COMMENT ON COLUMN strategies.strategy_version IS 'Semantic version (e.g., 1.0, 1.1, 2.0) - Config is IMMUTABLE';
COMMENT ON COLUMN strategies.status IS 'Lifecycle: draft → testing → active → inactive → deprecated. Status and performance metrics CAN update in-place';
COMMENT ON COLUMN strategies.paper_roi IS 'Performance metric - updates as paper trades execute';

-- ============================================================================
-- 3. ALTER positions - Add trailing_stop_state
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'positions' AND column_name = 'trailing_stop_state'
    ) THEN
        ALTER TABLE positions ADD COLUMN trailing_stop_state JSONB;

        COMMENT ON COLUMN positions.trailing_stop_state IS 'Trailing stop state: {is_activated, peak_price_seen, current_stop_price, last_updated} - Phase 5';
    END IF;
END $$;

-- ============================================================================
-- 4. ALTER edges - Add strategy_id, model_id FKs
-- ============================================================================

DO $$
BEGIN
    -- Add strategy_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'edges' AND column_name = 'strategy_id'
    ) THEN
        ALTER TABLE edges ADD COLUMN strategy_id INTEGER REFERENCES strategies(strategy_id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_edges_strategy ON edges(strategy_id);
        COMMENT ON COLUMN edges.strategy_id IS 'Links edge to strategy version that would trade it - Phase 5';
    END IF;

    -- Add model_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'edges' AND column_name = 'model_id'
    ) THEN
        ALTER TABLE edges ADD COLUMN model_id INTEGER REFERENCES probability_models(model_id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_edges_model ON edges(model_id);
        COMMENT ON COLUMN edges.model_id IS 'Links edge to model version that calculated it - Phase 4';
    END IF;
END $$;

-- ============================================================================
-- 5. ALTER trades - Add strategy_id, model_id FKs
-- ============================================================================

DO $$
BEGIN
    -- Add strategy_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trades' AND column_name = 'strategy_id'
    ) THEN
        ALTER TABLE trades ADD COLUMN strategy_id INTEGER REFERENCES strategies(strategy_id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
        COMMENT ON COLUMN trades.strategy_id IS 'Links trade to strategy version that executed it - Phase 5';
    END IF;

    -- Add model_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trades' AND column_name = 'model_id'
    ) THEN
        ALTER TABLE trades ADD COLUMN model_id INTEGER REFERENCES probability_models(model_id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_trades_model ON trades(model_id);
        COMMENT ON COLUMN trades.model_id IS 'Links trade to model version that calculated probability - Phase 4';
    END IF;
END $$;

-- ============================================================================
-- 6. CREATE HELPER VIEWS FOR VERSIONING
-- ============================================================================

-- Active strategies only (one per strategy_name)
CREATE OR REPLACE VIEW active_strategies AS
SELECT * FROM strategies WHERE status = 'active';

COMMENT ON VIEW active_strategies IS 'Currently active strategy versions';

-- Active models only
CREATE OR REPLACE VIEW active_models AS
SELECT * FROM probability_models WHERE status = 'active';

COMMENT ON VIEW active_models IS 'Currently active model versions';

-- Trade attribution summary (which strategy+model generated each trade)
CREATE OR REPLACE VIEW trade_attribution AS
SELECT
    t.trade_id,
    t.market_id,
    t.created_at,
    t.price,
    t.quantity,
    t.side,
    s.strategy_name,
    s.strategy_version,
    s.status AS strategy_status,
    m.model_name,
    m.model_version,
    m.status AS model_status
FROM trades t
LEFT JOIN strategies s ON t.strategy_id = s.strategy_id
LEFT JOIN probability_models m ON t.model_id = m.model_id;

COMMENT ON VIEW trade_attribution IS 'Links each trade to the strategy and model versions that generated it';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Run these to verify migration succeeded:

-- 1. Check new tables exist
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('strategies', 'probability_models');

-- 2. Check new columns added
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'positions' AND column_name = 'trailing_stop_state';

-- 3. Check FKs added to edges
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'edges' AND column_name IN ('strategy_id', 'model_id');

-- 4. Check FKs added to trades
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'trades' AND column_name IN ('strategy_id', 'model_id');

-- 5. Check views created
-- SELECT viewname FROM pg_views WHERE schemaname = 'public' AND viewname IN ('active_strategies', 'active_models', 'trade_attribution');

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
