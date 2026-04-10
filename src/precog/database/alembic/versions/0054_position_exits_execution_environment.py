"""Add execution_environment to position_exits (4-value tombstone).

Revision ID: 0054
Revises: 0053
Create Date: 2026-04-09

Phase A of Issue #691 -- finish the cross-environment-contamination
architecture. This migration closes the architecture gap for
position_exits, an append-only log of exit events.

Mulder surfaced this as a gap that the original #691 issue missed during
the design council: position_exits has the SAME failure mode as the
parent positions table, but is structurally harder to detect because the
join-only relationship means any aggregation query that forgets the
JOIN filter will silently mix environments.

What this migration does:
    1. ALTER TABLE position_exits ADD COLUMN execution_environment
       VARCHAR(20) NOT NULL DEFAULT 'unknown' (tombstone default)
    2. Explicit backfill of any pre-migration rows to 'unknown' (no-op
       in dev/test where the table is empty; belt-and-suspenders for
       prod)
    3. ADD CONSTRAINT chk_position_exits_exec_env CHECK (execution_environment
       IN ('live', 'paper', 'backtest', 'unknown'))  -- 4-value tombstone
    4. DROP the server_default. Phase B will make the CRUD REQUIRED.

Why the 4-value tombstone (Mulder's framing):
    position_exits is an APPEND-ONLY forensic record of exit events
    (close triggers, stop-loss fires, manual closes, etc.). The parent
    positions row is env-scoped via positions.execution_environment
    (added in migration 0008), but position_exits joins only on
    position_internal_id. An aggregation query like:

        SELECT SUM(realized_pnl) FROM position_exits
        WHERE created_at > '...'

    will silently mix live + paper + backtest exit P&L if the operator
    forgets to JOIN positions and filter on execution_environment. This
    is exactly the #662/#686 bug class applied to an append-only table.

    Defaulting historical rows to 'live' would silently assert every
    pre-migration exit was a real-money close. If that assertion is
    wrong, the error compounds into P&L reports and tax reconstruction
    with no way to detect it. Honesty > optimism on money-lineage data
    -- same framing as account_ledger.

    Forensic honesty trumps convenience for exit event provenance.

    Enforced at the Python boundary by
    VALID_EXECUTION_ENVIRONMENTS_BALANCE-style frozensets (Phase B will
    add a dedicated POSITION_EXITS constant or reuse the BALANCE one --
    PM decision).

Why NOT inherit from the parent positions row:
    Philosophically tempting: "just copy positions.execution_environment
    at insert time." But this creates a subtle invariant ("position_exits
    row must match its parent position's env") that Python code has to
    enforce, and any drift is silent. The explicit column is louder and
    matches the pattern PR #690 already established for sibling tables.

    A future integrity check could assert
    position_exits.execution_environment = parent.execution_environment,
    but that's Phase B / issue #694.

Dev DB state (forensic check at migration-authoring time):
    - rows: 0
    - view dependencies: 0
    - existing indexes: idx_position_exits_position
    - foreign keys: position_internal_id -> positions(id)
    - existing check constraints: position_exits_exit_price_check,
      position_exits_exit_priority_check,
      position_exits_quantity_exited_check
    No ordering concerns for downgrade.

Scope:
    PHASE A -- migration only. No CRUD signature changes, no read-path
    changes, no caller audits. Phase B (tracked in #691) will audit
    any crud_position_exits caller. DO NOT touch CRUD in this PR.

Round-trip:
    The downgrade drops the CHECK constraint and then the column. No
    view dependencies to reorder.

Related:
    - Issue #691 (Phase A: schema migrations; Phase B: CRUD/read paths)
    - Migration 0051 (account_balance.execution_environment, PR #690)
    - Migration 0052 (account_ledger.execution_environment, this PR)
    - Migration 0053 (settlements.execution_environment, this PR)
    - docs/database/RATIONALE_MIGRATION_0051.md (4-vs-3 asymmetry
      precedent, downgrade ordering lesson, design council synthesis)
    - ADR-107 (Single-Database Architecture with Execution Environments)
    - Migration 0001 (original position_exits creation, baseline schema)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0054"
down_revision: str = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add execution_environment column to position_exits with tombstone default."""
    # ------------------------------------------------------------------
    # Step 1: Add column with DEFAULT 'unknown' (tombstone)
    #
    # O(1) metadata-only in PG 11+. The 'unknown' default is Mulder's
    # forensic-honesty framing -- pre-migration exit events have
    # ambiguous provenance and must be distinguishable from post-migration
    # rows.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE position_exits
        ADD COLUMN execution_environment VARCHAR(20) NOT NULL DEFAULT 'unknown'
    """)

    # ------------------------------------------------------------------
    # Step 2: Explicit belt-and-suspenders backfill
    #
    # The ADD COLUMN DEFAULT in Step 1 already populates existing rows.
    # This explicit UPDATE is defensive for any row that somehow escapes
    # the DEFAULT (raw inserts during the migration window, replication
    # replay, etc.). Dev + test have 0 rows so this is a no-op.
    # ------------------------------------------------------------------
    op.execute("""
        UPDATE position_exits
        SET execution_environment = 'unknown'
        WHERE created_at < '2026-04-09 00:00:00+00'
    """)

    # ------------------------------------------------------------------
    # Step 3: Add CHECK constraint (4-value tombstone)
    #
    # 'unknown' is allowed here (matches account_balance and
    # account_ledger pattern). The asymmetry vs trades/positions/orders/
    # edges/settlements (3-value) is enforced at the Python boundary by
    # per-domain frozensets in crud_shared.py.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE position_exits
        ADD CONSTRAINT chk_position_exits_exec_env
        CHECK (execution_environment IN ('live', 'paper', 'backtest', 'unknown'))
    """)

    # ------------------------------------------------------------------
    # Step 4: Drop the server_default
    #
    # Phase B will make crud_position_exits REQUIRED for
    # execution_environment with no Python default, closing the
    # "optional-default" precedent.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE position_exits
        ALTER COLUMN execution_environment DROP DEFAULT
    """)

    # ------------------------------------------------------------------
    # Step 5: Document the column
    # ------------------------------------------------------------------
    op.execute("""
        COMMENT ON COLUMN position_exits.execution_environment IS
        'Execution context: live (production), paper (demo API), backtest (simulation), '
        'unknown (forensic tombstone for historical rows of unknown provenance). '
        'Append-only: REQUIRED parameter on all CRUD writes after Phase B of #691. '
        '4-value CHECK matches the tombstone pattern for money-lineage tables. '
        'See ADR-107 and docs/database/RATIONALE_MIGRATION_0051.md.'
    """)


def downgrade() -> None:
    """Reverse: drop CHECK constraint and execution_environment column.

    Lossy window: if the upgrade lands in prod and then is rolled back,
    any execution_environment values written between upgrade and downgrade
    are lost. A subsequent re-upgrade backfills all historical rows to
    'unknown' again -- distinguishing "really unknown" from "rolled back
    through" requires an out-of-band audit against git history. This is
    acceptable for a forensic append-only log (the tombstone IS the
    forensic signal, and the bisect is possible via created_at).

    No view dependencies to reorder (verified via information_schema.views
    grep at migration-authoring time). The column drop is safe without
    any recreation gymnastics.
    """
    # Step 1: Drop the CHECK constraint.
    op.execute("""
        ALTER TABLE position_exits
        DROP CONSTRAINT IF EXISTS chk_position_exits_exec_env
    """)

    # Step 2: Drop the column. No views depend on it.
    op.execute("""
        ALTER TABLE position_exits
        DROP COLUMN IF EXISTS execution_environment
    """)
