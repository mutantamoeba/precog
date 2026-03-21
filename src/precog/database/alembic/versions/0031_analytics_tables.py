"""Create analytics infrastructure tables for Phase 4+.

Four tables enabling performance tracking for models, strategies, and
backtesting: evaluation_runs, backtesting_runs, predictions, and
performance_metrics. Together they form the foundation of the analytics
pipeline: run evaluations -> generate predictions -> track performance metrics.

Steps:
    1. CREATE TABLE evaluation_runs
    2. CREATE TABLE backtesting_runs
    3. CREATE TABLE predictions
    4. CREATE TABLE performance_metrics
    5. Add indexes for common query patterns

Revision ID: 0031
Revises: 0030
Create Date: 2026-03-21

Related:
- migration_batch_plan_v1.md: Migration 0031 spec
- ADR-002: Decimal Precision for All Financial Data
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031"
down_revision: str = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create four analytics tables for model/strategy evaluation tracking.

    Design intent:
        - evaluation_runs: tracks when models/strategies are evaluated
        - backtesting_runs: tracks backtesting experiments with result metrics
        - predictions: individual model predictions (live or evaluation)
        - performance_metrics: polymorphic metrics for any entity
        - All financial values use DECIMAL(10,4) per ADR-002
        - All timestamps use TIMESTAMP WITH TIME ZONE
        - VARCHAR + CHECK constraints for enum-like fields (no DB ENUM)
        - SERIAL surrogate PKs per project convention
    """
    # ------------------------------------------------------------------
    # Step 1: CREATE TABLE evaluation_runs
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE evaluation_runs (
            id SERIAL PRIMARY KEY,

            -- What was evaluated
            run_type VARCHAR(20) NOT NULL
                CHECK (run_type IN ('model', 'strategy', 'ensemble')),
            model_id INTEGER REFERENCES probability_models(model_id) ON DELETE SET NULL,
            strategy_id INTEGER REFERENCES strategies(strategy_id) ON DELETE SET NULL,

            -- Run configuration
            config JSONB,

            -- Results summary
            status VARCHAR(20) NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
            summary JSONB,
            error_message TEXT,

            -- Time tracking
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE,

            -- Metadata
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX idx_eval_runs_model ON evaluation_runs(model_id)")
    op.execute("CREATE INDEX idx_eval_runs_strategy ON evaluation_runs(strategy_id)")
    op.execute(
        "CREATE INDEX idx_eval_runs_status ON evaluation_runs(status) WHERE status = 'running'"
    )
    op.execute("CREATE INDEX idx_eval_runs_type ON evaluation_runs(run_type)")

    # ------------------------------------------------------------------
    # Step 2: CREATE TABLE backtesting_runs
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE backtesting_runs (
            id SERIAL PRIMARY KEY,

            -- What was backtested
            strategy_id INTEGER REFERENCES strategies(strategy_id) ON DELETE SET NULL,
            model_id INTEGER REFERENCES probability_models(model_id) ON DELETE SET NULL,

            -- Backtest configuration
            config JSONB NOT NULL,
            date_range_start DATE NOT NULL,
            date_range_end DATE NOT NULL,

            -- Results
            status VARCHAR(20) NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
            total_trades INTEGER DEFAULT 0,
            win_rate DECIMAL(10,4),
            total_pnl DECIMAL(10,4),
            max_drawdown DECIMAL(10,4),
            sharpe_ratio DECIMAL(10,4),
            results_detail JSONB,
            error_message TEXT,

            -- Time tracking
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE,

            -- Metadata
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX idx_backtest_runs_strategy ON backtesting_runs(strategy_id)")
    op.execute("CREATE INDEX idx_backtest_runs_model ON backtesting_runs(model_id)")
    op.execute(
        "CREATE INDEX idx_backtest_runs_status ON backtesting_runs(status) WHERE status = 'running'"
    )
    op.execute(
        "CREATE INDEX idx_backtest_runs_dates ON backtesting_runs(date_range_start, date_range_end)"
    )

    # ------------------------------------------------------------------
    # Step 3: CREATE TABLE predictions
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE predictions (
            id SERIAL PRIMARY KEY,

            -- Source
            evaluation_run_id INTEGER REFERENCES evaluation_runs(id) ON DELETE CASCADE,
            model_id INTEGER REFERENCES probability_models(model_id) ON DELETE SET NULL,

            -- What was predicted
            market_id INTEGER REFERENCES markets(id) ON DELETE CASCADE,
            event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,

            -- Prediction values
            predicted_probability DECIMAL(10,4) NOT NULL
                CHECK (predicted_probability >= 0.0000 AND predicted_probability <= 1.0000),
            confidence DECIMAL(10,4)
                CHECK (confidence IS NULL OR (confidence >= 0.0000 AND confidence <= 1.0000)),
            market_price_at_prediction DECIMAL(10,4)
                CHECK (market_price_at_prediction IS NULL OR
                       (market_price_at_prediction >= 0.0000
                        AND market_price_at_prediction <= 1.0000)),
            edge DECIMAL(10,4),

            -- Outcome (filled after settlement)
            actual_outcome DECIMAL(10,4)
                CHECK (actual_outcome IS NULL OR
                       (actual_outcome >= 0.0000 AND actual_outcome <= 1.0000)),
            is_correct BOOLEAN,

            -- Metadata
            predicted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            resolved_at TIMESTAMP WITH TIME ZONE,

            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX idx_predictions_eval_run ON predictions(evaluation_run_id)")
    op.execute("CREATE INDEX idx_predictions_model ON predictions(model_id)")
    op.execute("CREATE INDEX idx_predictions_market ON predictions(market_id)")
    op.execute(
        "CREATE INDEX idx_predictions_unresolved ON predictions(id) WHERE actual_outcome IS NULL"
    )
    op.execute("CREATE INDEX idx_predictions_time ON predictions(predicted_at DESC)")

    # ------------------------------------------------------------------
    # Step 4: CREATE TABLE performance_metrics
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE performance_metrics (
            id SERIAL PRIMARY KEY,

            -- What entity this metric describes (polymorphic)
            entity_type VARCHAR(20) NOT NULL
                CHECK (entity_type IN ('model', 'strategy', 'evaluation_run', 'backtest_run')),
            entity_id INTEGER NOT NULL,

            -- Metric identity
            metric_name VARCHAR(50) NOT NULL,
            metric_value DECIMAL(10,4) NOT NULL,

            -- Context
            period_start DATE,
            period_end DATE,
            sample_size INTEGER,
            metadata JSONB,

            -- Timestamps
            calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

            -- One metric per entity per name per period
            CONSTRAINT uq_perf_metric_entity_period
                UNIQUE (entity_type, entity_id, metric_name, period_start, period_end)
        )
    """)

    op.execute(
        "CREATE INDEX idx_perf_metrics_entity ON performance_metrics(entity_type, entity_id)"
    )
    op.execute("CREATE INDEX idx_perf_metrics_name ON performance_metrics(metric_name)")
    op.execute(
        "CREATE INDEX idx_perf_metrics_period ON performance_metrics(period_start, period_end)"
    )


def downgrade() -> None:
    """Reverse: drop indexes and all four analytics tables."""
    # Step 1: Drop performance_metrics indexes + table
    op.execute("DROP INDEX IF EXISTS idx_perf_metrics_period")
    op.execute("DROP INDEX IF EXISTS idx_perf_metrics_name")
    op.execute("DROP INDEX IF EXISTS idx_perf_metrics_entity")
    op.execute("DROP TABLE IF EXISTS performance_metrics")

    # Step 2: Drop predictions indexes + table
    op.execute("DROP INDEX IF EXISTS idx_predictions_time")
    op.execute("DROP INDEX IF EXISTS idx_predictions_unresolved")
    op.execute("DROP INDEX IF EXISTS idx_predictions_market")
    op.execute("DROP INDEX IF EXISTS idx_predictions_model")
    op.execute("DROP INDEX IF EXISTS idx_predictions_eval_run")
    op.execute("DROP TABLE IF EXISTS predictions")

    # Step 3: Drop backtesting_runs indexes + table
    op.execute("DROP INDEX IF EXISTS idx_backtest_runs_dates")
    op.execute("DROP INDEX IF EXISTS idx_backtest_runs_status")
    op.execute("DROP INDEX IF EXISTS idx_backtest_runs_model")
    op.execute("DROP INDEX IF EXISTS idx_backtest_runs_strategy")
    op.execute("DROP TABLE IF EXISTS backtesting_runs")

    # Step 4: Drop evaluation_runs indexes + table
    op.execute("DROP INDEX IF EXISTS idx_eval_runs_type")
    op.execute("DROP INDEX IF EXISTS idx_eval_runs_status")
    op.execute("DROP INDEX IF EXISTS idx_eval_runs_strategy")
    op.execute("DROP INDEX IF EXISTS idx_eval_runs_model")
    op.execute("DROP TABLE IF EXISTS evaluation_runs")
