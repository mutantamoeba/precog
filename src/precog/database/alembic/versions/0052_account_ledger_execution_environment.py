"""Add execution_environment to account_ledger (4-value tombstone).

Revision ID: 0052
Revises: 0051
Create Date: 2026-04-09

Phase A of Issue #691 -- finish the cross-environment-contamination
architecture that PR #690 / migration 0051 explicitly deferred. Migration
0051 closed the architecture gap for account_balance; this migration
closes the same gap for the sibling append-only log table account_ledger.

What this migration does:
    1. ALTER TABLE account_ledger ADD COLUMN execution_environment
       VARCHAR(20) NOT NULL DEFAULT 'unknown' (tombstone default)
    2. Explicit backfill of any pre-migration rows to 'unknown' (no-op in
       dev/test where the table is empty; belt-and-suspenders for prod)
    3. ADD CONSTRAINT chk_account_ledger_exec_env CHECK (execution_environment
       IN ('live', 'paper', 'backtest', 'unknown'))  -- 4-value tombstone set
    4. DROP the server_default after the column is populated. Phase B will
       make the CRUD signature REQUIRED with no Python default; the DDL
       default is only a transitional belt-and-suspenders for raw-SQL
       callers during the Phase A window.

Why the 4-value tombstone (matches account_balance, not trades/positions):
    account_ledger is an APPEND-ONLY forensic audit trail explaining WHY
    balances changed (deposit, withdrawal, trade_pnl, fee, rebate,
    adjustment). Mulder's framing from the #622/#686 council: defaulting
    historical rows to 'live' would silently assert every pre-migration
    entry was real-money. If that assertion is wrong, the error compounds
    into P&L reports and tax reconstruction with no way to detect it.
    Honesty > optimism on money-lineage data.

    In contrast, trades and positions (chk_trades_exec_env,
    chk_positions_exec_env from migration 0024) allow only the original 3
    values ('live', 'paper', 'backtest'). The 4-vs-3 asymmetry is
    intentional and enforced at the Python boundary by per-domain
    frozensets (VALID_EXECUTION_ENVIRONMENTS_BALANCE vs
    VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION in crud_shared.py).

    account_ledger belongs in the BALANCE domain (4-value) because it
    describes cash-flow events on the same ledger as account_balance,
    not trade-level P&L events.

Why VARCHAR + CHECK instead of ENUM:
    Migration 0024 dropped the execution_environment ENUM TYPE after
    converting trades and positions to VARCHAR(20) + CHECK. Reusing
    VARCHAR + CHECK keeps account_ledger consistent with
    account_balance/trades/positions and avoids reintroducing a TYPE that
    was deliberately removed for ALTER flexibility.

Dev DB state (forensic check at migration-authoring time):
    - rows: 0
    - view dependencies: 0
    - existing indexes: idx_ledger_platform_date, idx_ledger_type,
      idx_ledger_order, idx_ledger_reference
    - foreign keys: platform_id -> platforms, order_id -> orders
    No ordering concerns for the downgrade path.

Scope:
    PHASE A -- migration only. No CRUD signature changes, no read-path
    changes, no caller audits. Phase B (tracked in #691) will make
    execution_environment REQUIRED on crud_ledger.create_ledger_entry,
    audit callers, and fix mode-blind read paths. DO NOT touch
    crud_ledger.py in this PR.

Round-trip:
    The downgrade drops the CHECK constraint and then the column. No view
    dependencies to reorder (verified via information_schema.views grep).
    A round-trip integration test verifies upgrade head -> downgrade -1
    -> upgrade head succeeds against a populated testcontainer.

Related:
    - Issue #691 (Phase A: schema migrations; Phase B: CRUD/read paths)
    - Migration 0051 (account_balance.execution_environment, PR #690)
    - docs/database/RATIONALE_MIGRATION_0051.md (4-vs-3 asymmetry
      precedent, downgrade ordering lesson, design council synthesis)
    - ADR-107 (Single-Database Architecture with Execution Environments)
    - Migration 0026 (original account_ledger creation, 2026-03-21)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0052"
down_revision: str = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add execution_environment column to account_ledger with tombstone default."""
    # ------------------------------------------------------------------
    # Step 1: Add column with DEFAULT 'unknown' (tombstone)
    #
    # In Postgres 11+, ADD COLUMN with a constant non-volatile DEFAULT is
    # an O(1) metadata-only operation -- no table rewrite. ACCESS EXCLUSIVE
    # is held only briefly. The 'unknown' default matches Mulder's
    # forensic-honesty framing: any pre-migration row has ambiguous
    # provenance and must be distinguishable from post-migration rows.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE account_ledger
        ADD COLUMN execution_environment VARCHAR(20) NOT NULL DEFAULT 'unknown'
    """)

    # ------------------------------------------------------------------
    # Step 2: Explicit backfill of pre-migration rows to 'unknown'
    #
    # Step 1's DEFAULT already populates existing rows with 'unknown' as
    # part of the ADD COLUMN metadata update. This explicit UPDATE is
    # belt-and-suspenders for any row that somehow escaped the DEFAULT
    # (raw inserts during the migration window, logical replication
    # replay, etc.). Dev + test DBs have 0 rows so this is a no-op; the
    # statement is still included for prod-readiness.
    # ------------------------------------------------------------------
    op.execute("""
        UPDATE account_ledger
        SET execution_environment = 'unknown'
        WHERE created_at < '2026-04-09 00:00:00+00'
    """)

    # ------------------------------------------------------------------
    # Step 3: Add CHECK constraint (4-value tombstone set)
    #
    # Matches VALID_EXECUTION_ENVIRONMENTS_BALANCE in crud_shared.py.
    # account_ledger belongs in the BALANCE domain because it describes
    # cash-flow events on the same ledger as account_balance.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE account_ledger
        ADD CONSTRAINT chk_account_ledger_exec_env
        CHECK (execution_environment IN ('live', 'paper', 'backtest', 'unknown'))
    """)

    # ------------------------------------------------------------------
    # Step 4: Drop the server_default after the column is populated
    #
    # The DEFAULT was only for the ADD COLUMN + transitional safety.
    # Going forward, Phase B will make crud_ledger.create_ledger_entry
    # REQUIRED for execution_environment with no Python default, mirroring
    # the 6 CRUD functions PR #690 touched (create_position, create_trade,
    # create_account_balance, update_account_balance_with_versioning,
    # create_order, create_edge). Dropping the server_default here closes
    # the "optional-default 'live'" precedent that was the literal cause
    # of the #622/#686 bug class.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE account_ledger
        ALTER COLUMN execution_environment DROP DEFAULT
    """)

    # ------------------------------------------------------------------
    # Step 5: Document the column for schema introspection
    # ------------------------------------------------------------------
    op.execute("""
        COMMENT ON COLUMN account_ledger.execution_environment IS
        'Execution context: live (production), paper (demo API), backtest (simulation), '
        'unknown (forensic tombstone for historical rows of unknown provenance). '
        'REQUIRED parameter on all CRUD writes after Phase B of #691 -- no Python default. '
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
    forensic signal).

    No view dependencies to reorder (verified via information_schema.views
    grep at migration-authoring time). The column drop is safe without
    any recreation gymnastics.
    """
    # Step 1: Drop the CHECK constraint (named, so IF EXISTS is defensive).
    op.execute("""
        ALTER TABLE account_ledger
        DROP CONSTRAINT IF EXISTS chk_account_ledger_exec_env
    """)

    # Step 2: Drop the column. No views depend on it.
    op.execute("""
        ALTER TABLE account_ledger
        DROP COLUMN IF EXISTS execution_environment
    """)
