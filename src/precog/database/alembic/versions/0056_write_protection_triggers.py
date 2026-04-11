"""Add write-protection triggers for immutability and append-only enforcement.

Revision ID: 0056
Revises: 0055
Create Date: 2026-04-10

Issues: #371, #723
Epic: #745 (Schema Hardening Arc, Cohort C1)

Council attribution (8 of 12 agents flagged #371 -- highest conviction):
    Mulder, Leto II, Holden, Vader, Elrond, Daneel, Cassandra, Leto II (C1+C2)

What this migration does:
    1. Creates enforce_strategy_immutability() trigger function
       - Blocks UPDATE on: config, strategy_version, strategy_name, strategy_type
       - Allows UPDATE on mutable columns: status, activated_at, deactivated_at,
         notes, description, paper_trades_count, paper_roi, live_trades_count,
         live_roi, updated_at, created_by, domain, platform_id
       - Columns intentionally NOT protected (mutable by design):
         domain (reclassification), platform_id (lifecycle), created_at (immutable
         by convention but NOT NULL DEFAULT NOW() prevents drift)
    2. Creates enforce_model_immutability() trigger function
       - Blocks UPDATE on: config, model_version, model_name, model_class
       - Allows UPDATE on mutable columns: status, activated_at, deactivated_at,
         notes, description, validation_accuracy, validation_calibration,
         validation_sample_size, created_by, domain, training_start_date,
         training_end_date, training_sample_size
       - Columns intentionally NOT protected: domain (reclassification),
         training_* (may be updated during retraining workflow)
    3. Creates prevent_append_only_update() trigger function
       - Blocks ALL UPDATE operations on append-only fact tables
    4. Applies triggers to 7 tables:
       - strategies (selective immutability)
       - probability_models (selective immutability)
       - trades (append-only)
       - settlements (append-only)
       - account_ledger (append-only)
       - position_exits (append-only)
       - exit_attempts (append-only)

Why DB-level enforcement matters:
    CLAUDE.md Rule 5 declares strategies and models immutable, but this was
    Python-only enforcement via StrategyManager.ImmutabilityError. A single
    stray UPDATE statement -- from a migration, manual SQL, or future code --
    silently breaks every downstream trade's provenance chain. DB triggers
    are the last line of defense and the only one that cannot be bypassed
    by application code.

    The 5 append-only tables (trades, settlements, account_ledger,
    position_exits, exit_attempts) record historical facts that must never
    be modified. No CRUD UPDATE functions exist for these tables, confirming
    append-only is the intended semantic.

IMPORTANT — Future migrations that backfill data:
    Any future migration that needs to UPDATE rows in the 5 append-only
    tables (e.g., backfilling a new column like migrations 0052-0055 did)
    MUST temporarily disable the trigger:

        ALTER TABLE trades DISABLE TRIGGER trg_trades_append_only;
        UPDATE trades SET new_column = 'value' WHERE ...;
        ALTER TABLE trades ENABLE TRIGGER trg_trades_append_only;

    Similarly, migrations that need to ALTER immutable columns on strategies
    or probability_models must drop and recreate the trigger function.

    Without this, the migration will fail with a RaiseException.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add write-protection triggers to 7 tables."""

    # =========================================================================
    # 1. IMMUTABILITY TRIGGER FUNCTION — strategies
    # =========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION enforce_strategy_immutability()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.config IS DISTINCT FROM OLD.config
               OR NEW.strategy_version IS DISTINCT FROM OLD.strategy_version
               OR NEW.strategy_name IS DISTINCT FROM OLD.strategy_name
               OR NEW.strategy_type IS DISTINCT FROM OLD.strategy_type
            THEN
                RAISE EXCEPTION
                    'Cannot modify immutable columns on strategies '
                    '(config, strategy_version, strategy_name, strategy_type). '
                    'Create a new version instead.';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        COMMENT ON FUNCTION enforce_strategy_immutability() IS
        'Blocks UPDATE on immutable columns (config, version, name, type). '
        'Mutable columns (status, timestamps, counters) remain updatable. '
        'Issue #371, ADR-018.'
    """)

    # =========================================================================
    # 2. IMMUTABILITY TRIGGER FUNCTION — probability_models
    # =========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION enforce_model_immutability()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.config IS DISTINCT FROM OLD.config
               OR NEW.model_version IS DISTINCT FROM OLD.model_version
               OR NEW.model_name IS DISTINCT FROM OLD.model_name
               OR NEW.model_class IS DISTINCT FROM OLD.model_class
            THEN
                RAISE EXCEPTION
                    'Cannot modify immutable columns on probability_models '
                    '(config, model_version, model_name, model_class). '
                    'Create a new version instead.';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        COMMENT ON FUNCTION enforce_model_immutability() IS
        'Blocks UPDATE on immutable columns (config, version, name, class). '
        'Mutable columns (status, timestamps, validation metrics) remain updatable. '
        'Issue #371, ADR-018.'
    """)

    # =========================================================================
    # 3. APPEND-ONLY TRIGGER FUNCTION — shared by 5 fact tables
    # =========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_append_only_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'Table % is append-only. UPDATE not permitted. '
                'Create a new row instead.',
                TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        COMMENT ON FUNCTION prevent_append_only_update() IS
        'Blocks ALL UPDATE operations on append-only fact tables. '
        'Applied to: trades, settlements, account_ledger, position_exits, exit_attempts. '
        'Issue #723.'
    """)

    # =========================================================================
    # 4. APPLY TRIGGERS — idempotent (DROP IF EXISTS before CREATE)
    # =========================================================================

    # --- strategies immutability ---
    op.execute("DROP TRIGGER IF EXISTS trg_strategies_immutability ON strategies")
    op.execute("""
        CREATE TRIGGER trg_strategies_immutability
            BEFORE UPDATE ON strategies
            FOR EACH ROW
            EXECUTE FUNCTION enforce_strategy_immutability()
    """)
    op.execute("""
        COMMENT ON TRIGGER trg_strategies_immutability ON strategies IS
        'Enforces immutability of config, version, name, type columns. Issue #371.'
    """)

    # --- probability_models immutability ---
    op.execute("DROP TRIGGER IF EXISTS trg_models_immutability ON probability_models")
    op.execute("""
        CREATE TRIGGER trg_models_immutability
            BEFORE UPDATE ON probability_models
            FOR EACH ROW
            EXECUTE FUNCTION enforce_model_immutability()
    """)
    op.execute("""
        COMMENT ON TRIGGER trg_models_immutability ON probability_models IS
        'Enforces immutability of config, version, name, class columns. Issue #371.'
    """)

    # --- trades append-only ---
    op.execute("DROP TRIGGER IF EXISTS trg_trades_append_only ON trades")
    op.execute("""
        CREATE TRIGGER trg_trades_append_only
            BEFORE UPDATE ON trades
            FOR EACH ROW
            EXECUTE FUNCTION prevent_append_only_update()
    """)
    op.execute("""
        COMMENT ON TRIGGER trg_trades_append_only ON trades IS
        'Prevents UPDATE on append-only trade records. Issue #723.'
    """)

    # --- settlements append-only ---
    op.execute("DROP TRIGGER IF EXISTS trg_settlements_append_only ON settlements")
    op.execute("""
        CREATE TRIGGER trg_settlements_append_only
            BEFORE UPDATE ON settlements
            FOR EACH ROW
            EXECUTE FUNCTION prevent_append_only_update()
    """)
    op.execute("""
        COMMENT ON TRIGGER trg_settlements_append_only ON settlements IS
        'Prevents UPDATE on append-only settlement records. Issue #723.'
    """)

    # --- account_ledger append-only ---
    op.execute("DROP TRIGGER IF EXISTS trg_account_ledger_append_only ON account_ledger")
    op.execute("""
        CREATE TRIGGER trg_account_ledger_append_only
            BEFORE UPDATE ON account_ledger
            FOR EACH ROW
            EXECUTE FUNCTION prevent_append_only_update()
    """)
    op.execute("""
        COMMENT ON TRIGGER trg_account_ledger_append_only ON account_ledger IS
        'Prevents UPDATE on append-only ledger entries. Issue #723.'
    """)

    # --- position_exits append-only ---
    op.execute("DROP TRIGGER IF EXISTS trg_position_exits_append_only ON position_exits")
    op.execute("""
        CREATE TRIGGER trg_position_exits_append_only
            BEFORE UPDATE ON position_exits
            FOR EACH ROW
            EXECUTE FUNCTION prevent_append_only_update()
    """)
    op.execute("""
        COMMENT ON TRIGGER trg_position_exits_append_only ON position_exits IS
        'Prevents UPDATE on append-only exit records. Issue #723.'
    """)

    # --- exit_attempts append-only ---
    op.execute("DROP TRIGGER IF EXISTS trg_exit_attempts_append_only ON exit_attempts")
    op.execute("""
        CREATE TRIGGER trg_exit_attempts_append_only
            BEFORE UPDATE ON exit_attempts
            FOR EACH ROW
            EXECUTE FUNCTION prevent_append_only_update()
    """)
    op.execute("""
        COMMENT ON TRIGGER trg_exit_attempts_append_only ON exit_attempts IS
        'Prevents UPDATE on append-only exit attempt records. Issue #723.'
    """)


def downgrade() -> None:
    """Remove all write-protection triggers and functions."""

    # Drop triggers (reverse order of creation)
    op.execute("DROP TRIGGER IF EXISTS trg_exit_attempts_append_only ON exit_attempts")
    op.execute("DROP TRIGGER IF EXISTS trg_position_exits_append_only ON position_exits")
    op.execute("DROP TRIGGER IF EXISTS trg_account_ledger_append_only ON account_ledger")
    op.execute("DROP TRIGGER IF EXISTS trg_settlements_append_only ON settlements")
    op.execute("DROP TRIGGER IF EXISTS trg_trades_append_only ON trades")
    op.execute("DROP TRIGGER IF EXISTS trg_models_immutability ON probability_models")
    op.execute("DROP TRIGGER IF EXISTS trg_strategies_immutability ON strategies")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS prevent_append_only_update()")
    op.execute("DROP FUNCTION IF EXISTS enforce_model_immutability()")
    op.execute("DROP FUNCTION IF EXISTS enforce_strategy_immutability()")
