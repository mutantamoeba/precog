"""
Add execution_environment to account_balance + drop dead per-mode views.

Revision ID: 0051
Revises: 0050
Create Date: 2026-04-07

This migration finishes the half-built ADR-107 cross-environment isolation
architecture from migration 0008. Migration 0008 added execution_environment
to trades and positions but never added it to account_balance, leaving the
money ledger structurally incapable of partitioning real-money rows from
demo-money rows. This is the root cause of the #622/#662/#686 bug class.

What this migration does (one atomic transaction):
    1. ALTER TABLE account_balance ADD COLUMN execution_environment VARCHAR(20)
       NOT NULL DEFAULT 'live'
    2. ADD CONSTRAINT chk_account_balance_exec_env CHECK (execution_environment
       IN ('live', 'paper', 'backtest', 'unknown'))
    3. DROP idx_balance_unique_current; CREATE composite unique partial index
       (platform_id, execution_environment) WHERE row_current_ind = TRUE
       (preserving the index name so the SCD retry helper continues to fire
       on the same constraint string)
    4. DROP VIEW current_balances (mode-blind, becomes a contamination trap
       post-migration; PM verified zero production consumers via grep)
    5. DROP VIEWs live_trades, paper_trades, backtest_trades, training_data_trades,
       live_positions, paper_positions, backtest_positions -- the 7 dead per-mode
       views from migration 0008. Recreated 3 times across 0008/0024/0025;
       zero production consumers verified by PM via grep on src/.

Reserved 4th value 'unknown':
    The CHECK constraint allows 'unknown' as a future tombstone for forensic
    backfills of historical rows of unknown provenance (Mulder's data-honesty
    framing in findings_622_686_mulder.md). No rows in this migration use it;
    dev's account_balance is empty per PM forensic check. If/when production
    has historical data of unknown provenance, the value is available without
    a schema change.

    Note: 'unknown' is allowed ONLY on account_balance. The trades and
    positions CHECK constraints (chk_trades_exec_env, chk_positions_exec_env
    from migration 0024) only allow the original 3 values. The Python
    validators in crud_positions / crud_account use per-domain frozensets
    (VALID_EXECUTION_ENVIRONMENTS_BALANCE vs
    VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION) to enforce this asymmetry
    at the function boundary so a Python caller passing 'unknown' to
    create_position fails LOUDLY at the function boundary instead of
    crashing on the DB CHECK constraint with a confusing message.

Why VARCHAR + CHECK instead of ENUM:
    Migration 0024 dropped the execution_environment ENUM TYPE after converting
    trades and positions to VARCHAR(20) + CHECK. Reusing VARCHAR + CHECK keeps
    account_balance consistent with trades/positions and avoids reintroducing
    a TYPE that was deliberately removed for ALTER flexibility.

Why a single transactional migration:
    Precog has no replicas, no rolling deploys. ACCESS EXCLUSIVE on a tiny
    table is fine. CREATE INDEX CONCURRENTLY cannot run inside a transaction
    and would lose atomicity. Drop+recreate of the unique index in one
    transaction guarantees rollback safety.

Why the index name is preserved:
    crud_account.update_account_balance_with_versioning wraps the close+insert
    in retry_on_scd_unique_conflict("idx_balance_unique_current", ...). The
    helper discriminates by constraint name. Renaming the index would silently
    disable the retry helper for first-insert races. The new index has the
    same name and a strictly tighter (composite) key, which is unique by
    construction (the old single-column constraint was already unique on
    platform_id WHERE row_current_ind, so adding execution_environment as a
    second column is also unique).

Round-trip:
    The downgrade recreates everything: the 7 per-mode views (with the same
    definitions migration 0024 used), current_balances, the original
    single-column unique index, and drops the column + check constraint.
    A round-trip integration test verifies upgrade head -> downgrade -1 ->
    upgrade head succeeds against a populated DB.

Related:
    - **docs/database/RATIONALE_MIGRATION_0051.md** -- the in-repo design
      rationale for this migration. READ THIS FIRST if you're trying to
      understand WHY this migration exists or what the architecture
      decisions were.
    - Issue #622 (account_balance missing column)
    - Issue #686 (PositionManager.open_position drops execution_environment)
    - Issue #662 (update_position_price drops execution_environment, fixed in #688)
    - ADR-107 (Single-Database Architecture with Execution Environments)
    - Migration 0008 (added execution_environment to trades/positions only)
    - Migration 0024 (dropped the ENUM type, converted to VARCHAR + CHECK)
    - Migration 0049 (added SCD temporal columns + idx_balance_unique_current)
    - Issue #691 (follow-up: finish account_ledger + settlements + read-path defaults)

For the deeper agent-by-agent design pass (Mulder data-model skepticism +
Holden schema safety review), see the synthesis files in the project
memory directory: ~/.claude/projects/.../memory/findings_622_686_*.md
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add execution_environment to account_balance + drop dead views."""
    # ------------------------------------------------------------------
    # Step 1: Add execution_environment column with DEFAULT 'live'
    #
    # In Postgres 11+, ADD COLUMN with a constant non-volatile DEFAULT is an
    # O(1) metadata-only operation; no table rewrite. ACCESS EXCLUSIVE lock is
    # held only briefly. The DEFAULT 'live' acts as a belt-and-suspenders
    # safety net for any raw-SQL caller that bypasses the CRUD layer; the
    # Python CRUD signature is REQUIRED with no default, so app callers
    # always pass the value explicitly.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE account_balance
        ADD COLUMN execution_environment VARCHAR(20) NOT NULL DEFAULT 'live'
    """)

    # ------------------------------------------------------------------
    # Step 2: Add CHECK constraint with 'unknown' reserved as 4th value
    #
    # 'unknown' is a future tombstone for forensic backfills of historical
    # rows of unknown provenance. No rows in this migration use it. Dev's
    # account_balance is empty (PM forensic check). The constraint is named
    # so the downgrade can drop it explicitly.
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE account_balance
        ADD CONSTRAINT chk_account_balance_exec_env
        CHECK (execution_environment IN ('live', 'paper', 'backtest', 'unknown'))
    """)

    # ------------------------------------------------------------------
    # Step 3: Drop and recreate the unique partial index
    #
    # Old: idx_balance_unique_current ON account_balance(platform_id)
    #      WHERE row_current_ind = TRUE
    # New: idx_balance_unique_current ON account_balance(platform_id,
    #      execution_environment) WHERE row_current_ind = TRUE
    #
    # The index name is preserved so the SCD retry helper
    # (retry_on_scd_unique_conflict in crud_shared.py) continues to fire on
    # the same constraint string. This operation runs inside the migration's
    # transaction; if the CREATE fails, the DROP rolls back and the old index
    # is restored. CREATE INDEX (NOT CONCURRENTLY) is intentional -- the table
    # is tiny and CONCURRENTLY cannot run inside a transaction, which would
    # lose atomicity.
    #
    # Cannot fail on backfilled data: after Step 1's DEFAULT, all old rows
    # have execution_environment='live'. The old single-column unique index
    # already guaranteed unique (platform_id) WHERE row_current_ind. The new
    # composite (platform_id, 'live') is also unique by construction.
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS idx_balance_unique_current")
    op.execute("""
        CREATE UNIQUE INDEX idx_balance_unique_current
        ON account_balance(platform_id, execution_environment)
        WHERE row_current_ind = TRUE
    """)

    # ------------------------------------------------------------------
    # Step 4: Drop the current_balances view
    #
    # Pre-migration: current_balances was a thin SCD-current convenience view
    # over account_balance. Post-migration it would silently aggregate live +
    # paper + backtest current rows for the same platform_id, which on a
    # money-touching path is the same #662/#686 bug class -- exactly what this
    # migration exists to prevent. PM verified zero production consumers via
    # grep on src/ and tests/ (only matches are the migration files
    # themselves). Drop without rewrite. Recreated in downgrade.
    # ------------------------------------------------------------------
    op.execute("DROP VIEW IF EXISTS current_balances")

    # ------------------------------------------------------------------
    # Step 5: Drop the 7 dead per-mode views from migration 0008
    #
    # These views were created in migration 0008 (ADR-107 scaffolding),
    # then RE-CREATED in migrations 0022, 0024, and 0025 -- pure maintenance
    # cost with zero production benefit. PM verified zero production
    # consumers: full grep for FROM (live|paper|backtest|training_data)_*
    # against src/ returns zero hits. The CRUD layer routes around them by
    # adding WHERE execution_environment = %s directly against the base
    # table, so the views are inert. Removing them eliminates ~150 lines of
    # dead recreation code from future migrations and removes the misleading
    # "look the system partitions by environment!" signal.
    #
    # If a future need arises, recreating them is a one-line CREATE VIEW.
    # The downgrade restores them to make this migration round-trippable.
    # ------------------------------------------------------------------
    op.execute("DROP VIEW IF EXISTS live_trades")
    op.execute("DROP VIEW IF EXISTS paper_trades")
    op.execute("DROP VIEW IF EXISTS backtest_trades")
    op.execute("DROP VIEW IF EXISTS training_data_trades")
    op.execute("DROP VIEW IF EXISTS live_positions")
    op.execute("DROP VIEW IF EXISTS paper_positions")
    op.execute("DROP VIEW IF EXISTS backtest_positions")

    # ------------------------------------------------------------------
    # Step 6: Document the new column for schema introspection
    # ------------------------------------------------------------------
    op.execute("""
        COMMENT ON COLUMN account_balance.execution_environment IS
        'Execution context: live (production), paper (demo API), backtest (simulation), '
        'unknown (forensic tombstone for historical rows of unknown provenance). '
        'REQUIRED parameter on all CRUD writes -- no Python default. See ADR-107 '
        'and findings_622_686_synthesis.md.'
    """)


def downgrade() -> None:
    """Restore the pre-migration state.

    Lossy window: if multiple current rows exist per platform across
    environments (which the new composite index allows), the downgrade's
    CREATE UNIQUE INDEX (platform_id) WHERE row_current_ind = TRUE will
    fail. Manual repair query before downgrade::

        UPDATE account_balance SET row_current_ind = FALSE
        WHERE platform_id = '<x>'
          AND row_current_ind = TRUE
          AND execution_environment != 'live';

    Test the rollback against a populated dev DB BEFORE landing the PR.
    The round-trip integration test exercises this path on a populated
    testcontainer.
    """
    # Step 1: Recreate the 7 per-mode views with the exact definitions
    # from migration 0024's upgrade (the canonical "kept alive" copies).
    op.execute(
        "CREATE OR REPLACE VIEW live_trades AS "
        "SELECT * FROM trades WHERE execution_environment = 'live'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW paper_trades AS "
        "SELECT * FROM trades WHERE execution_environment = 'paper'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW backtest_trades AS "
        "SELECT * FROM trades WHERE execution_environment = 'backtest'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW training_data_trades AS "
        "SELECT * FROM trades WHERE execution_environment IN ('paper', 'backtest')"
    )
    op.execute(
        "CREATE OR REPLACE VIEW live_positions AS "
        "SELECT * FROM positions WHERE execution_environment = 'live' AND row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW paper_positions AS "
        "SELECT * FROM positions WHERE execution_environment = 'paper' AND row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW backtest_positions AS "
        "SELECT * FROM positions "
        "WHERE execution_environment = 'backtest' AND row_current_ind = TRUE"
    )

    # Step 2: Restore the original single-column unique partial index.
    # This will FAIL if multiple environments have current rows for the
    # same platform_id. See manual repair query in the docstring above.
    op.execute("DROP INDEX IF EXISTS idx_balance_unique_current")
    op.execute("""
        CREATE UNIQUE INDEX idx_balance_unique_current
        ON account_balance(platform_id)
        WHERE row_current_ind = TRUE
    """)

    # Step 3: Drop the CHECK constraint and the column.
    #
    # IMPORTANT: current_balances must NOT exist at this point, otherwise
    # PostgreSQL refuses to drop the column with "DependentObjectsStillExist"
    # because SELECT * FROM ... captures the column list at view creation
    # time. We recreate current_balances in Step 4 AFTER the column drop
    # so its SELECT * captures the post-downgrade column set. (The PM
    # caught this round-trip bug in dev during application of this
    # migration: an earlier draft recreated the view BEFORE dropping the
    # column and downgrade failed loudly. The fix is the ordering below.)
    op.execute("""
        ALTER TABLE account_balance
        DROP CONSTRAINT IF EXISTS chk_account_balance_exec_env
    """)
    op.execute("""
        ALTER TABLE account_balance
        DROP COLUMN IF EXISTS execution_environment
    """)

    # Step 4: Recreate current_balances view with its original mode-blind
    # definition from migration 0001 line 805. This MUST happen AFTER the
    # column drop so the view's SELECT * captures the post-downgrade
    # column list (no execution_environment).
    op.execute("""
        CREATE OR REPLACE VIEW current_balances AS
        SELECT * FROM account_balance WHERE row_current_ind = TRUE
    """)
