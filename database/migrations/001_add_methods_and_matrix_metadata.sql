-- Migration: Add methods table and enhance probability_matrices
-- Version: 001
-- Created: 2025-10-23
-- Phase: 1 (enhancement before Phase 4)
-- Purpose:
--   1. Create methods table for trading method versioning
--   2. Add matrix_name and description to probability_matrices for better documentation

-- ==============================================================================
-- PART 1: Create methods table
-- ==============================================================================

-- Methods bundle complete trading configurations: strategy + model + position management + risk
-- A "method" combines a specific strategy version with a specific model version plus
-- position management rules and risk parameters.
--
-- Example: "conservative_nfl_v1.0" might use:
--   - Strategy: halftime_entry_nfl_v1.1
--   - Model: elo_nfl_v1.1
--   - Position Mgmt: trailing stops enabled, 20% profit targets
--   - Risk: 0.15 Kelly fraction, $500 max position size
--
-- See VERSIONING_GUIDE.md for complete specification.
-- See ADR-021 for architecture decision.

CREATE TABLE IF NOT EXISTS methods (
    -- Primary Key
    method_id SERIAL PRIMARY KEY,

    -- Naming and Versioning (immutable once created)
    method_name VARCHAR NOT NULL,              -- 'conservative_nfl', 'aggressive_nba'
    method_version VARCHAR NOT NULL,           -- 'v1.0', 'v1.1', 'v2.0' (semantic versioning)

    -- Component References (immutable once created)
    strategy_id INT NOT NULL REFERENCES strategies(strategy_id),    -- Which strategy this method uses
    model_id INT NOT NULL REFERENCES probability_models(model_id),  -- Which model this method uses

    -- Configuration (immutable once created)
    position_mgmt_config JSONB,                -- Position management rules (trailing stops, profit targets, stop loss)
    risk_config JSONB,                         -- Risk parameters (Kelly fraction, max position size)

    -- Lifecycle Management (mutable)
    status VARCHAR DEFAULT 'draft',            -- 'draft', 'testing', 'active', 'inactive', 'deprecated'

    -- Documentation
    description TEXT,                          -- Human-readable description of this method
    notes TEXT,                                -- Additional notes, change rationale, etc.

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR,                        -- Who created this method

    -- Enforce unique versions per method name
    UNIQUE(method_name, method_version)
);

-- Indexes for methods table
CREATE INDEX idx_methods_name ON methods(method_name);
CREATE INDEX idx_methods_status ON methods(status);
CREATE INDEX idx_methods_active ON methods(status) WHERE status = 'active';
CREATE INDEX idx_methods_strategy ON methods(strategy_id);
CREATE INDEX idx_methods_model ON methods(model_id);

-- Comments for clarity
COMMENT ON TABLE methods IS 'Trading methods: bundles of strategy + model + position management + risk config. Uses immutable versioning pattern (see ADR-021).';
COMMENT ON COLUMN methods.method_name IS 'Method name without version, e.g., conservative_nfl, aggressive_nba';
COMMENT ON COLUMN methods.method_version IS 'Semantic version: v1.0, v1.1 (minor), v2.0 (major)';
COMMENT ON COLUMN methods.position_mgmt_config IS 'JSONB: trailing stop config, profit targets, stop loss rules';
COMMENT ON COLUMN methods.risk_config IS 'JSONB: Kelly fraction, max position size, other risk parameters';
COMMENT ON COLUMN methods.status IS 'Lifecycle state: draft, testing, active, inactive, deprecated';

-- ==============================================================================
-- PART 2: Enhance probability_matrices table
-- ==============================================================================

-- Add matrix_name for easier identification and querying
-- Add description for documentation of what this matrix represents
-- These were planned but not included in initial schema

ALTER TABLE probability_matrices
ADD COLUMN IF NOT EXISTS matrix_name VARCHAR;

ALTER TABLE probability_matrices
ADD COLUMN IF NOT EXISTS description TEXT;

-- Create index for matrix_name lookups
CREATE INDEX IF NOT EXISTS idx_probability_matrices_name ON probability_matrices(matrix_name);

-- Comments for new columns
COMMENT ON COLUMN probability_matrices.matrix_name IS 'Human-readable name for this probability matrix, e.g., nfl_halftime_comeback, nba_clutch_situations';
COMMENT ON COLUMN probability_matrices.description IS 'Detailed description of what this matrix represents and how it should be used';

-- ==============================================================================
-- Example data structure for methods table
-- ==============================================================================

-- Example 1: Conservative NFL method
-- INSERT INTO methods (
--     method_name,
--     method_version,
--     strategy_id,
--     model_id,
--     position_mgmt_config,
--     risk_config,
--     status,
--     description,
--     created_by
-- ) VALUES (
--     'conservative_nfl',
--     'v1.0',
--     1,  -- halftime_entry_nfl_v1.1
--     2,  -- elo_nfl_v1.1
--     '{
--         "trailing_stop": {
--             "enabled": true,
--             "activation_threshold": 0.10,
--             "stop_distance": 0.05
--         },
--         "profit_targets": {
--             "high_confidence": 0.20,
--             "medium_confidence": 0.15
--         },
--         "stop_loss": {
--             "high_confidence": -0.10,
--             "medium_confidence": -0.08
--         }
--     }'::jsonb,
--     '{
--         "kelly_fraction": 0.15,
--         "max_position_size_dollars": 500,
--         "max_total_exposure_dollars": 2000
--     }'::jsonb,
--     'draft',
--     'Conservative NFL trading method using halftime entry strategy with tight risk controls',
--     'system'
-- );

-- ==============================================================================
-- Example data for probability_matrices enhancements
-- ==============================================================================

-- Example: Update existing matrix with name and description
-- UPDATE probability_matrices
-- SET
--     matrix_name = 'nfl_halftime_comeback',
--     description = 'Probability matrix for NFL teams to win after being behind at halftime, based on point differential buckets and home/away status'
-- WHERE category = 'sports'
--   AND subcategory = 'nfl'
--   AND state_descriptor = 'halftime'
--   AND version = 'v1.0';

-- ==============================================================================
-- Migration verification queries
-- ==============================================================================

-- Verify methods table created
-- SELECT table_name, column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'methods'
-- ORDER BY ordinal_position;

-- Verify probability_matrices columns added
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'probability_matrices'
-- AND column_name IN ('matrix_name', 'description');

-- ==============================================================================
-- Rollback script (if needed)
-- ==============================================================================

-- To rollback this migration:
-- DROP TABLE IF EXISTS methods CASCADE;
-- ALTER TABLE probability_matrices DROP COLUMN IF EXISTS matrix_name;
-- ALTER TABLE probability_matrices DROP COLUMN IF EXISTS description;
