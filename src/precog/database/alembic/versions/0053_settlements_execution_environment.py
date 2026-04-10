"""Add execution_environment to settlements (3-value, default 'live').

Revision ID: 0053
Revises: 0052
Create Date: 2026-04-09

Phase A of Issue #691 -- finish the cross-environment-contamination
architecture. This migration closes the architecture gap for the
settlements table, the canonical ground-truth P&L signal when a market
resolves.

What this migration does:
    1. ALTER TABLE settlements ADD COLUMN execution_environment
       VARCHAR(20) NOT NULL DEFAULT 'live'
    2. Backfill explicitly runs via the ADD COLUMN DEFAULT (all historical
       rows are definitionally live; see rationale below). No explicit
       UPDATE needed because the default IS the correct historical value.
    3. ADD CONSTRAINT chk_settlements_exec_env CHECK (execution_environment
       IN ('live', 'paper', 'backtest'))  -- 3-value set, NO 'unknown'
    4. DROP the server_default after the column is populated. Phase B
       will make the CRUD signature REQUIRED with no Python default.

Why 'live' default and 3-value CHECK (NOT 4-value tombstone):
    Settlements come EXCLUSIVELY from Kalshi's live settlement feed when
    a market resolves. There is no "paper settlement" or "backtest
    settlement" code path in the current codebase -- Holden verified by
    reading create_settlement callers during the #691 design pass. Every
    historical row in this table is, by construction, a real Kalshi
    resolution payout, so defaulting them to 'live' is correct rather
    than optimistic.

    The 'unknown' tombstone is reserved for tables where pre-migration
    provenance is genuinely ambiguous (account_balance, account_ledger,
    position_exits, exit_attempts). settlements is structurally NOT in
    that class: it is closer in archetype to trades and positions, which
    use the 3-value CHECK (chk_trades_exec_env, chk_positions_exec_env
    from migration 0024).

    The 4-vs-3 asymmetry is enforced at the Python boundary by per-domain
    frozensets in crud_shared.py:
        VALID_EXECUTION_ENVIRONMENTS_BALANCE = 4 values (includes 'unknown')
        VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION = 3 values (no 'unknown')
    settlements belongs in the TRADE_POSITION domain.

    Future paper-settlement code path: if Phase 2 ever introduces a
    simulated settlement feed for paper-mode positions (e.g., to close
    paper positions when the live market resolves), the CRUD default
    must be updated to pass the caller's environment explicitly. The
    3-value CHECK already allows 'paper' and 'backtest' -- no schema
    change required.

Dev DB state (forensic check at migration-authoring time):
    - rows: 0
    - view dependencies: 0
    - existing indexes: idx_settlements_market (on market_internal_id
      post-migration 0022)
    - foreign keys: market_internal_id -> markets(id) (migration 0022),
      platform_id -> platforms
    - existing check constraints: settlements_payout_check
      (payout >= 0.0000)
    No ordering concerns for downgrade.

Scope:
    PHASE A -- migration only. No CRUD signature changes, no read-path
    changes, no caller audits. Phase B (tracked in #691) will audit
    create_settlement and any callers. DO NOT touch crud_settlements or
    any related CRUD in this PR.

Round-trip:
    The downgrade drops the CHECK constraint and then the column. No
    view dependencies to reorder. A round-trip integration test verifies
    upgrade head -> downgrade -1 -> upgrade head succeeds against a
    populated testcontainer.

Related:
    - Issue #691 (Phase A: schema migrations; Phase B: CRUD/read paths)
    - Migration 0051 (account_balance.execution_environment, PR #690)
    - Migration 0052 (account_ledger.execution_environment, this PR)
    - docs/database/RATIONALE_MIGRATION_0051.md (4-vs-3 asymmetry
      precedent, downgrade ordering lesson, design council synthesis)
    - ADR-107 (Single-Database Architecture with Execution Environments)
    - Migration 0022 (settlements.market_internal_id FK)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0053"
down_revision: str = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add execution_environment column to settlements with 'live' default."""
    # ------------------------------------------------------------------
    # Step 1: Add column with DEFAULT 'live'
    #
    # In Postgres 11+, ADD COLUMN with a constant non-volatile DEFAULT
    # is an O(1) metadata-only operation -- no table rewrite.
    #
    # 'live' is the correct historical default here (not a tombstone)
    # because every settlement row is, by construction, a real Kalshi
    # resolution payout. See the module docstring for the rationale.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE settlements
        ADD COLUMN execution_environment VARCHAR(20) NOT NULL DEFAULT 'live'
    """)

    # ------------------------------------------------------------------
    # Step 2: Add CHECK constraint (3-value, no tombstone)
    #
    # Matches VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION in
    # crud_shared.py. settlements is in the TRADE_POSITION domain.
    # A Python caller passing 'unknown' to create_settlement would fail
    # at the CRUD function boundary (via the frozenset check) before
    # ever hitting this CHECK -- but the CHECK is a belt-and-suspenders
    # guard for raw-SQL callers that bypass the CRUD layer.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE settlements
        ADD CONSTRAINT chk_settlements_exec_env
        CHECK (execution_environment IN ('live', 'paper', 'backtest'))
    """)

    # ------------------------------------------------------------------
    # Step 3: Drop the server_default
    #
    # The DEFAULT 'live' was a transitional belt-and-suspenders for any
    # raw-SQL caller during the Phase A window. Phase B will make
    # crud_settlements REQUIRED for execution_environment with no Python
    # default, closing the "optional-default 'live'" precedent.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE settlements
        ALTER COLUMN execution_environment DROP DEFAULT
    """)

    # ------------------------------------------------------------------
    # Step 4: Document the column for schema introspection
    # ------------------------------------------------------------------
    op.execute("""
        COMMENT ON COLUMN settlements.execution_environment IS
        'Execution context: live (production Kalshi settlement feed), paper (future '
        'simulated settlement path), backtest (simulation). REQUIRED parameter on '
        'all CRUD writes after Phase B of #691 -- no Python default. 3-value CHECK '
        'matches VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION. See ADR-107 and '
        'docs/database/RATIONALE_MIGRATION_0051.md.'
    """)


def downgrade() -> None:
    """Reverse: drop CHECK constraint and execution_environment column.

    Lossy window: if the upgrade lands in prod and then is rolled back,
    any execution_environment values written between upgrade and downgrade
    are lost. A subsequent re-upgrade backfills all historical rows to
    'live' again. Because every current settlement row is definitionally
    live (see module docstring), the re-upgrade's default is the correct
    value -- this is NOT a lossy re-upgrade in the same sense as the
    tombstone tables. The only lossy scenario is if a future Phase 2
    paper-settlement code path has been introduced and its rows get
    silently re-tagged as 'live' on re-upgrade. Document that before
    introducing the paper-settlement path.

    No view dependencies to reorder (verified via information_schema.views
    grep at migration-authoring time). The column drop is safe without
    any recreation gymnastics.
    """
    # Step 1: Drop the CHECK constraint.
    op.execute("""
        ALTER TABLE settlements
        DROP CONSTRAINT IF EXISTS chk_settlements_exec_env
    """)

    # Step 2: Drop the column. No views depend on it.
    op.execute("""
        ALTER TABLE settlements
        DROP COLUMN IF EXISTS execution_environment
    """)
