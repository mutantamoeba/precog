"""Add execution_environment to exit_attempts (4-value tombstone).

Revision ID: 0055
Revises: 0054
Create Date: 2026-04-09

Phase A of Issue #691 -- finish the cross-environment-contamination
architecture. This migration closes the architecture gap for
exit_attempts, an append-only log of FAILED exit attempts. Mulder also
surfaced this as a gap during the #691 design council.

What this migration does:
    1. ALTER TABLE exit_attempts ADD COLUMN execution_environment
       VARCHAR(20) NOT NULL DEFAULT 'unknown' (tombstone default)
    2. Explicit backfill of any pre-migration rows to 'unknown' (no-op
       in dev/test where the table is empty)
    3. ADD CONSTRAINT chk_exit_attempts_exec_env CHECK (execution_environment
       IN ('live', 'paper', 'backtest', 'unknown'))  -- 4-value tombstone
    4. DROP the server_default. Phase B will make the CRUD REQUIRED.

Why the 4-value tombstone (and arguably MORE important than position_exits):
    exit_attempts is the forensic record of FAILED exit attempts. Mulder's
    framing during the design council: a failed live-exit that then
    succeeds in paper is exactly the kind of cross-mode event a user
    needs to reconstruct for audit -- imagine a live stop-loss that
    failed because the market was suspended, followed by a paper-mode
    re-test that succeeded. Without the execution_environment column,
    these two rows look identical in any aggregation.

    Same archetype as position_exits: append-only, joins to positions
    only via position_internal_id, aggregations without JOIN will
    silently mix environments. Historical rows have ambiguous
    provenance and MUST be distinguishable from post-migration rows --
    Mulder's honesty-over-optimism framing applies with extra weight
    here because the rows are specifically about things that WENT
    WRONG, which is exactly the forensic class where precision matters
    most.

    Defaulting historical rows to 'live' would silently assert every
    pre-migration failed attempt was a real-money incident. That's a
    high-consequence claim to bake into a forensic log without
    verification.

    4-value CHECK matches account_balance, account_ledger, and
    position_exits. 3-value CHECK (trades/positions/orders/edges/
    settlements) would be wrong for the same Mulder-forensic-honesty
    reason.

Dev DB state (forensic check at migration-authoring time):
    - rows: 0
    - view dependencies: 0
    - existing indexes: idx_exit_attempts_position
    - foreign keys: position_internal_id -> positions(id)
    - existing check constraints: (none)
    No ordering concerns for downgrade.

Scope:
    PHASE A -- migration only. No CRUD signature changes, no read-path
    changes, no caller audits. Phase B (tracked in #691) will audit any
    CRUD that inserts into exit_attempts. DO NOT touch CRUD in this PR.

Round-trip:
    The downgrade drops the CHECK constraint and then the column. No
    view dependencies to reorder.

Related:
    - Issue #691 (Phase A: schema migrations; Phase B: CRUD/read paths)
    - Migration 0051 (account_balance.execution_environment, PR #690)
    - Migration 0052 (account_ledger.execution_environment, this PR)
    - Migration 0053 (settlements.execution_environment, this PR)
    - Migration 0054 (position_exits.execution_environment, this PR)
    - docs/database/RATIONALE_MIGRATION_0051.md (4-vs-3 asymmetry
      precedent, downgrade ordering lesson, design council synthesis)
    - ADR-107 (Single-Database Architecture with Execution Environments)
    - Migration 0001 (original exit_attempts creation, baseline schema)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0055"
down_revision: str = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add execution_environment column to exit_attempts with tombstone default."""
    # ------------------------------------------------------------------
    # Step 1: Add column with DEFAULT 'unknown' (tombstone)
    #
    # O(1) metadata-only in PG 11+. 'unknown' is Mulder's
    # forensic-honesty framing -- exit_attempts are the forensic record
    # of things that WENT WRONG, which is the class where silently
    # baking in an optimistic 'live' default has the highest downstream
    # consequence.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE exit_attempts
        ADD COLUMN execution_environment VARCHAR(20) NOT NULL DEFAULT 'unknown'
    """)

    # ------------------------------------------------------------------
    # Step 2: Explicit belt-and-suspenders backfill
    # ------------------------------------------------------------------
    op.execute("""
        UPDATE exit_attempts
        SET execution_environment = 'unknown'
        WHERE created_at < '2026-04-09 00:00:00+00'
    """)

    # ------------------------------------------------------------------
    # Step 3: Add CHECK constraint (4-value tombstone)
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE exit_attempts
        ADD CONSTRAINT chk_exit_attempts_exec_env
        CHECK (execution_environment IN ('live', 'paper', 'backtest', 'unknown'))
    """)

    # ------------------------------------------------------------------
    # Step 4: Drop the server_default
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE exit_attempts
        ALTER COLUMN execution_environment DROP DEFAULT
    """)

    # ------------------------------------------------------------------
    # Step 5: Document the column
    # ------------------------------------------------------------------
    op.execute("""
        COMMENT ON COLUMN exit_attempts.execution_environment IS
        'Execution context: live (production), paper (demo API), backtest (simulation), '
        'unknown (forensic tombstone for historical rows of unknown provenance). '
        'Append-only forensic record of FAILED exit attempts. REQUIRED parameter on '
        'all CRUD writes after Phase B of #691. 4-value CHECK matches the tombstone '
        'pattern for money-lineage tables. See ADR-107 and '
        'docs/database/RATIONALE_MIGRATION_0051.md.'
    """)


def downgrade() -> None:
    """Reverse: drop CHECK constraint and execution_environment column.

    Lossy window: if the upgrade lands in prod and then is rolled back,
    any execution_environment values written between upgrade and downgrade
    are lost. A subsequent re-upgrade backfills all historical rows to
    'unknown' again. Bisect via created_at is possible if an operator
    needs to distinguish "rolled-back-through" rows from truly-unknown
    rows.

    No view dependencies to reorder (verified via information_schema.views
    grep at migration-authoring time). The column drop is safe without
    any recreation gymnastics.
    """
    # Step 1: Drop the CHECK constraint.
    op.execute("""
        ALTER TABLE exit_attempts
        DROP CONSTRAINT IF EXISTS chk_exit_attempts_exec_env
    """)

    # Step 2: Drop the column. No views depend on it.
    op.execute("""
        ALTER TABLE exit_attempts
        DROP COLUMN IF EXISTS execution_environment
    """)
