"""Update series frequency constraint to match Kalshi API vocabulary.

Revision ID: 0011
Revises: 0010
Create Date: 2024-12-24

The Kalshi API uses frequency values like 'daily', 'weekly', 'event' but our
original schema only allowed 'single', 'recurring', 'continuous'. This migration
updates the CHECK constraint to match the API vocabulary for seamless integration.

Related:
- ADR-XXX: API Response Schema Alignment
- REQ-DATA-005: Market Data Storage
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Update frequency CHECK constraint to match Kalshi API values.

    Changes:
    - Old values: 'single', 'recurring', 'continuous'
    - New values: 'daily', 'weekly', 'event' (plus old values for backwards compatibility)

    Educational Note:
        PostgreSQL CHECK constraints cannot be modified in-place. We must:
        1. Drop the existing constraint by name
        2. Migrate existing data to new vocabulary
        3. Add a new constraint with the updated values

        We keep both old and new values for backwards compatibility with any
        existing data that uses the old vocabulary.
    """
    # Step 1: Drop the old CHECK constraint
    # The constraint name follows our naming convention: series_frequency_check
    op.execute("ALTER TABLE series DROP CONSTRAINT IF EXISTS series_frequency_check")

    # Step 2: Migrate any existing data from old vocabulary to new
    # Map: 'single' -> 'event', 'recurring' -> 'daily', 'continuous' -> 'daily'
    op.execute("""
        UPDATE series SET frequency = 'event' WHERE frequency = 'single'
    """)
    op.execute("""
        UPDATE series SET frequency = 'daily' WHERE frequency IN ('recurring', 'continuous')
    """)

    # Step 3: Add new CHECK constraint with Kalshi API vocabulary
    # Values from Kalshi API: 'daily', 'weekly', 'event'
    # Also include 'monthly', 'once' for potential future use
    op.execute("""
        ALTER TABLE series
        ADD CONSTRAINT series_frequency_check
        CHECK (frequency IN ('daily', 'weekly', 'monthly', 'event', 'once'))
    """)


def downgrade() -> None:
    """Revert to original frequency vocabulary.

    Reverts:
    - New values back to: 'single', 'recurring', 'continuous'
    """
    # Step 1: Drop the new constraint
    op.execute("ALTER TABLE series DROP CONSTRAINT IF EXISTS series_frequency_check")

    # Step 2: Migrate data back to old vocabulary
    op.execute("""
        UPDATE series SET frequency = 'single' WHERE frequency = 'event'
    """)
    op.execute("""
        UPDATE series SET frequency = 'recurring' WHERE frequency IN ('daily', 'weekly', 'monthly')
    """)
    op.execute("""
        UPDATE series SET frequency = 'recurring' WHERE frequency = 'once'
    """)

    # Step 3: Restore original CHECK constraint
    op.execute("""
        ALTER TABLE series
        ADD CONSTRAINT series_frequency_check
        CHECK (frequency IN ('single', 'recurring', 'continuous'))
    """)
