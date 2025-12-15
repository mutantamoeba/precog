-- Migration 016: Create Strategies and Probability Models Tables
-- Version: 1.0
-- Date: 2025-12-03
--
-- FIXES BUG: Migrations 001 and 003 reference strategies and probability_models
-- tables via foreign keys, but these tables were never created in any migration.
-- This migration creates the missing tables to fix CI/local database parity.
--
-- Tables created (in FK dependency order):
-- 1. strategy_types - Reference table for strategy types
-- 2. model_classes - Reference table for model classes
-- 3. strategies - Main strategies table
-- 4. probability_models - Main probability models table
--
-- Related:
-- - ADR-018 (Versioned Strategy/Model Immutability)
-- - REQ-TRADE-001 (Strategy Execution)
-- - REQ-MODEL-001 (Probability Model Management)

-- ============================================================================
-- 1. STRATEGY TYPES (Reference Table)
-- ============================================================================

CREATE TABLE IF NOT EXISTS strategy_types (
    strategy_type_code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER NOT NULL DEFAULT 999,
    icon_name VARCHAR(50),
    help_text TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for strategy_types
CREATE INDEX IF NOT EXISTS idx_strategy_types_active ON strategy_types(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_strategy_types_category ON strategy_types(category);
CREATE INDEX IF NOT EXISTS idx_strategy_types_order ON strategy_types(display_order);

-- Seed data for strategy_types
INSERT INTO strategy_types (strategy_type_code, display_name, description, category, display_order)
VALUES
    ('value', 'Value Trading', 'Exploit market mispricing by identifying edges where true probability exceeds market price', 'directional', 10),
    ('arbitrage', 'Arbitrage', 'Cross-platform arbitrage opportunities with identical event outcomes priced differently', 'arbitrage', 20),
    ('momentum', 'Momentum Trading', 'Trend following strategies that capitalize on sustained price movements', 'directional', 30),
    ('mean_reversion', 'Mean Reversion', 'Capitalize on temporary deviations from fundamental value by betting on reversion to mean', 'directional', 40)
ON CONFLICT (strategy_type_code) DO NOTHING;

-- ============================================================================
-- 2. MODEL CLASSES (Reference Table)
-- ============================================================================

CREATE TABLE IF NOT EXISTS model_classes (
    model_class_code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    complexity_level VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER NOT NULL DEFAULT 999,
    icon_name VARCHAR(50),
    help_text TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for model_classes
CREATE INDEX IF NOT EXISTS idx_model_classes_active ON model_classes(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_model_classes_category ON model_classes(category);
CREATE INDEX IF NOT EXISTS idx_model_classes_complexity ON model_classes(complexity_level);
CREATE INDEX IF NOT EXISTS idx_model_classes_order ON model_classes(display_order);

-- Seed data for model_classes
INSERT INTO model_classes (model_class_code, display_name, description, category, complexity_level, display_order)
VALUES
    ('elo', 'Elo Rating System', 'Dynamic rating system tracking team/competitor strength over time based on game outcomes', 'statistical', 'simple', 10),
    ('ensemble', 'Ensemble Model', 'Weighted combination of multiple models for more robust and accurate predictions', 'hybrid', 'moderate', 20),
    ('ml', 'Machine Learning', 'General machine learning algorithms (decision trees, random forests, SVM, etc.)', 'machine_learning', 'moderate', 30),
    ('hybrid', 'Hybrid Approach', 'Combines multiple modeling approaches (statistical + machine learning) for best of both worlds', 'hybrid', 'moderate', 40),
    ('regression', 'Statistical Regression', 'Linear or logistic regression models with feature engineering and interaction terms', 'statistical', 'simple', 50),
    ('neural', 'Neural Network', 'Deep learning models including feedforward, recurrent, and transformer architectures', 'machine_learning', 'complex', 60)
ON CONFLICT (model_class_code) DO NOTHING;

-- ============================================================================
-- 3. STRATEGIES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS strategies (
    strategy_id SERIAL PRIMARY KEY,
    platform_id VARCHAR(50) REFERENCES platforms(platform_id) ON DELETE CASCADE,
    strategy_name VARCHAR(100) NOT NULL,
    strategy_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    strategy_type VARCHAR(50) NOT NULL,
    domain VARCHAR(50),
    config JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    notes TEXT,
    paper_trades_count INTEGER DEFAULT 0,
    paper_roi NUMERIC(10,4),
    live_trades_count INTEGER DEFAULT 0,
    live_roi NUMERIC(10,4),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    description TEXT,
    created_by VARCHAR,

    -- Unique constraint: (name, version) must be unique for immutability
    UNIQUE (strategy_name, strategy_version),

    -- Check constraints
    CONSTRAINT strategies_status_check CHECK (status IN ('draft', 'testing', 'active', 'inactive', 'deprecated')),
    CONSTRAINT strategies_paper_trades_count_check CHECK (paper_trades_count >= 0),
    CONSTRAINT strategies_live_trades_count_check CHECK (live_trades_count >= 0),
    CONSTRAINT strategy_activation_order CHECK (deactivated_at IS NULL OR activated_at IS NULL OR deactivated_at >= activated_at)
);

-- Add FK to strategy_types (separate to allow table creation first)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_strategies_strategy_type'
    ) THEN
        ALTER TABLE strategies
        ADD CONSTRAINT fk_strategies_strategy_type
        FOREIGN KEY (strategy_type) REFERENCES strategy_types(strategy_type_code);
    END IF;
END $$;

-- Indexes for strategies
CREATE INDEX IF NOT EXISTS idx_strategies_platform ON strategies(platform_id);
CREATE INDEX IF NOT EXISTS idx_strategies_status ON strategies(status);
CREATE INDEX IF NOT EXISTS idx_strategies_strategy_type ON strategies(strategy_type);

-- ============================================================================
-- 4. PROBABILITY MODELS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS probability_models (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    model_class VARCHAR(50) NOT NULL,
    domain VARCHAR(50),
    config JSONB NOT NULL,
    training_start_date DATE,
    training_end_date DATE,
    training_sample_size INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    notes TEXT,
    validation_accuracy NUMERIC(6,4),
    validation_calibration NUMERIC(6,4),
    validation_sample_size INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    description TEXT,
    created_by VARCHAR,

    -- Unique constraint: (name, version) must be unique for immutability
    UNIQUE (model_name, model_version),

    -- Check constraints
    CONSTRAINT probability_models_status_check CHECK (status IN ('draft', 'testing', 'active', 'deprecated')),
    CONSTRAINT probability_models_training_sample_size_check CHECK (training_sample_size IS NULL OR training_sample_size >= 0),
    CONSTRAINT probability_models_validation_accuracy_check CHECK (validation_accuracy IS NULL OR (validation_accuracy >= 0.0000 AND validation_accuracy <= 1.0000)),
    CONSTRAINT probability_models_validation_calibration_check CHECK (validation_calibration IS NULL OR validation_calibration >= 0.0000),
    CONSTRAINT probability_models_validation_sample_size_check CHECK (validation_sample_size IS NULL OR validation_sample_size >= 0),
    CONSTRAINT model_activation_order CHECK (deactivated_at IS NULL OR activated_at IS NULL OR deactivated_at >= activated_at)
);

-- Add FK to model_classes (separate to allow table creation first)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_probability_models_model_class'
    ) THEN
        ALTER TABLE probability_models
        ADD CONSTRAINT fk_probability_models_model_class
        FOREIGN KEY (model_class) REFERENCES model_classes(model_class_code);
    END IF;
END $$;

-- Indexes for probability_models
CREATE INDEX IF NOT EXISTS idx_probability_models_model_class ON probability_models(model_class);
CREATE INDEX IF NOT EXISTS idx_probability_models_status ON probability_models(status);
CREATE INDEX IF NOT EXISTS idx_probability_models_category ON probability_models(model_class, domain);

-- ============================================================================
-- 5. COMMENTS
-- ============================================================================

COMMENT ON TABLE strategy_types IS 'Reference table for strategy type codes (value, arbitrage, momentum, mean_reversion)';
COMMENT ON TABLE model_classes IS 'Reference table for model class codes (elo, ensemble, ml, hybrid, regression, neural)';
COMMENT ON TABLE strategies IS 'Immutable strategy definitions with versioning. Each (name, version) pair is unique.';
COMMENT ON TABLE probability_models IS 'Immutable probability model definitions with versioning. Each (name, version) pair is unique.';

COMMENT ON COLUMN strategies.config IS 'JSONB configuration - immutable after activation. Contains all strategy parameters.';
COMMENT ON COLUMN probability_models.config IS 'JSONB configuration - immutable after activation. Contains model hyperparameters.';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- This migration fixes the database parity issue between local and CI environments.
-- The strategies and probability_models tables are required by migrations 001 and 003
-- which add foreign key references to them from the positions and trades tables.
