"""Add audit columns to lookup tables.

This migration adds updated_at and updated_by columns to lookup tables
(strategy_types, model_classes) and creates auto-update triggers.

GitHub Issue: #121 (DEF-P1.5-022)

Key Changes:
- Add updated_at column (TIMESTAMP, auto-updated by trigger)
- Add updated_by column (VARCHAR(100), populated by application)
- Create update_updated_at_column() trigger function
- Create triggers for both lookup tables

Revision ID: 0002
Revises: 0001
Create Date: 2025-12-07

References:
- ADR-018: Versioned Strategy/Model Immutability
- Pattern 2: SCD Type 2 / Dual Versioning
- DEVELOPMENT_PATTERNS_V1.19.md
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add audit columns and triggers to lookup tables."""

    # =========================================================================
    # 1. ADD AUDIT COLUMNS TO STRATEGY_TYPES
    # =========================================================================

    # Add updated_at column (auto-updated by trigger)
    op.execute("""
        ALTER TABLE strategy_types
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    """)

    # Add updated_by column (populated by application)
    op.execute("""
        ALTER TABLE strategy_types
        ADD COLUMN IF NOT EXISTS updated_by VARCHAR(100)
    """)

    # Add column comments
    op.execute("""
        COMMENT ON COLUMN strategy_types.updated_at IS
        'Timestamp of last modification (auto-updated by trigger)'
    """)
    op.execute("""
        COMMENT ON COLUMN strategy_types.updated_by IS
        'Username or system identifier that last updated this record'
    """)

    # =========================================================================
    # 2. ADD AUDIT COLUMNS TO MODEL_CLASSES
    # =========================================================================

    # Add updated_at column (auto-updated by trigger)
    op.execute("""
        ALTER TABLE model_classes
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    """)

    # Add updated_by column (populated by application)
    op.execute("""
        ALTER TABLE model_classes
        ADD COLUMN IF NOT EXISTS updated_by VARCHAR(100)
    """)

    # Add column comments
    op.execute("""
        COMMENT ON COLUMN model_classes.updated_at IS
        'Timestamp of last modification (auto-updated by trigger)'
    """)
    op.execute("""
        COMMENT ON COLUMN model_classes.updated_by IS
        'Username or system identifier that last updated this record'
    """)

    # =========================================================================
    # 3. CREATE REUSABLE TRIGGER FUNCTION
    # =========================================================================

    # Create or replace the trigger function for auto-updating updated_at
    # This function is reusable across all tables that need this behavior
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        COMMENT ON FUNCTION update_updated_at_column() IS
        'Trigger function to auto-update updated_at timestamp on row modification'
    """)

    # =========================================================================
    # 4. CREATE TRIGGERS FOR LOOKUP TABLES
    # =========================================================================

    # Drop existing triggers if they exist (idempotent)
    op.execute("DROP TRIGGER IF EXISTS update_strategy_types_updated_at ON strategy_types")
    op.execute("DROP TRIGGER IF EXISTS update_model_classes_updated_at ON model_classes")

    # Create trigger for strategy_types
    op.execute("""
        CREATE TRIGGER update_strategy_types_updated_at
            BEFORE UPDATE ON strategy_types
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """)

    # Create trigger for model_classes
    op.execute("""
        CREATE TRIGGER update_model_classes_updated_at
            BEFORE UPDATE ON model_classes
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """)

    # Add trigger comments
    op.execute("""
        COMMENT ON TRIGGER update_strategy_types_updated_at ON strategy_types IS
        'Auto-updates updated_at timestamp when strategy_types row is modified'
    """)
    op.execute("""
        COMMENT ON TRIGGER update_model_classes_updated_at ON model_classes IS
        'Auto-updates updated_at timestamp when model_classes row is modified'
    """)


def downgrade() -> None:
    """Remove audit columns and triggers from lookup tables."""

    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_strategy_types_updated_at ON strategy_types")
    op.execute("DROP TRIGGER IF EXISTS update_model_classes_updated_at ON model_classes")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE")

    # Remove columns from strategy_types
    op.execute("ALTER TABLE strategy_types DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE strategy_types DROP COLUMN IF EXISTS updated_by")

    # Remove columns from model_classes
    op.execute("ALTER TABLE model_classes DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE model_classes DROP COLUMN IF EXISTS updated_by")
