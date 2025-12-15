-- Migration 003: Add Strategy and Model Attribution Columns
-- Version: 003
-- Created: 2025-10-24
-- Phase: 1 (Foundation Completion)
-- Purpose: Add strategy_id and model_id foreign keys to positions and trades for attribution tracking
-- Related: DATABASE_SCHEMA_SUMMARY_V1.5, REQ-METH-008 (Trade Attribution)

-- ==============================================================================
-- POSITIONS TABLE - ADD ATTRIBUTION COLUMNS
-- ==============================================================================

-- Add strategy_id column (nullable to support historical records)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS strategy_id INT REFERENCES strategies(strategy_id);

-- Add model_id column (nullable to support historical records)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS model_id INT REFERENCES probability_models(model_id);

-- Add indexes for query performance
CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy_id);
CREATE INDEX IF NOT EXISTS idx_positions_model ON positions(model_id);

-- ==============================================================================
-- TRADES TABLE - ADD ATTRIBUTION COLUMNS
-- ==============================================================================

-- Add strategy_id column (nullable to support historical records)
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS strategy_id INT REFERENCES strategies(strategy_id);

-- Add model_id column (nullable to support historical records)
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS model_id INT REFERENCES probability_models(model_id);

-- Add indexes for query performance
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_model ON trades(model_id);

-- ==============================================================================
-- COMMENTS
-- ==============================================================================

COMMENT ON COLUMN positions.strategy_id IS 'FK to strategies - which strategy created this position';
COMMENT ON COLUMN positions.model_id IS 'FK to probability_models - which model was used for edge detection';
COMMENT ON COLUMN trades.strategy_id IS 'FK to strategies - which strategy triggered this trade';
COMMENT ON COLUMN trades.model_id IS 'FK to probability_models - which model was used for probability estimation';

-- ==============================================================================
-- VERIFICATION QUERIES
-- ==============================================================================

-- Verify columns added to positions
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'positions' AND column_name IN ('strategy_id', 'model_id');

-- Verify columns added to trades
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'trades' AND column_name IN ('strategy_id', 'model_id');

-- Verify indexes created
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('positions', 'trades')
--   AND indexname LIKE '%strategy%' OR indexname LIKE '%model%';

-- ==============================================================================
-- NOTES
-- ==============================================================================

-- Why nullable?
-- - Backward compatibility: Existing records won't have strategy/model attribution
-- - Phase 4-5: These become required for new records when methods system is active
-- - REQ-METH-012: Nullable FKs ensure historical data remains queryable

-- When to make NOT NULL?
-- - Phase 4-5: After methods system is fully implemented
-- - After backfilling historical records with default strategy/model
-- - Migration 00X will add NOT NULL constraint + defaults

-- Performance impact:
-- - Indexes added for common queries (filter by strategy, group by model)
-- - Foreign keys add constraint validation overhead (minimal)
-- - Expected query patterns: "Show all trades for strategy X", "Model Y performance"

-- ==============================================================================
-- ROLLBACK SCRIPT
-- ==============================================================================

-- To rollback this migration:
-- DROP INDEX IF EXISTS idx_positions_strategy;
-- DROP INDEX IF EXISTS idx_positions_model;
-- DROP INDEX IF EXISTS idx_trades_strategy;
-- DROP INDEX IF EXISTS idx_trades_model;
-- ALTER TABLE positions DROP COLUMN IF EXISTS strategy_id;
-- ALTER TABLE positions DROP COLUMN IF EXISTS model_id;
-- ALTER TABLE trades DROP COLUMN IF EXISTS strategy_id;
-- ALTER TABLE trades DROP COLUMN IF EXISTS model_id;
