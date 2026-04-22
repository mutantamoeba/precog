"""Demote games.espn_event_id partial UNIQUE index to a non-unique index.

Under the three-tier identity model (Epic #935), ``espn_event_id`` is an
EXTERNAL identifier — a read-only reference to the upstream ESPN system.
External identifiers MUST NEVER be UNIQUE on a dimension table: the upstream
system can re-use, re-assign, or drift its own identifiers, and our schema
must not crash on legitimate operational data.

The pre-0066 state was a partial UNIQUE index
(``idx_games_espn_event`` WHERE ``espn_event_id IS NOT NULL``), introduced
in migration 0035. This was a schema-safety bug: ESPN team-code drift
(e.g., ``MISS`` -> ``MS`` mid-season) causes the poller's business-key
ON CONFLICT (``uq_games_matchup``) to miss the existing row, which then
triggers a hard crash on the ``espn_event_id`` UNIQUE when the INSERT
proceeds. The result is a stall in market-data ingestion during active
NFL/NCAAF games.

After 0066:
    * ``idx_games_espn_event`` is a non-unique partial index (same name,
      same WHERE predicate) — retains lookup/query performance for the
      ~100% non-NULL rows written by the poller while NOT enforcing any
      cross-row uniqueness constraint.
    * Identity & uniqueness on ``games`` continue to be enforced by
      ``games_pkey`` (surrogate ``id``), ``uq_games_matchup``
      (sport + game_date + home + away — the business key), and
      ``idx_games_game_key`` (``GAM-{id}`` — a stable reference key).

Partial WHERE predicate preserved: historical imports
(FiveThirtyEight / Kaggle) intentionally leave ``espn_event_id`` NULL.
Indexing those NULLs would add zero lookup value and bloat the index.
The partiality was correct in 0035; only the UNIQUE qualifier was wrong.

Caller-side note: no ``src/`` code paths perform
``SELECT ... FROM games WHERE espn_event_id = %s`` lookups — the UNIQUE
index was crash-enforcement only (verified via repo-wide grep during
design review). No CRUD changes required for correctness; see the NOTE
comments added to ``crud_game_states.get_or_create_game`` and
``seeding/historical_games_loader._flush_games_batch`` for the rationale
that must carry forward.

Downgrade semantics (important):
    ``downgrade()`` attempts to restore the UNIQUE qualifier. If any
    non-NULL duplicate ``espn_event_id`` rows exist when the downgrade
    runs (the exact condition 0066 was introduced to tolerate), the
    ``CREATE UNIQUE INDEX`` statement will RAISE. This is the correct
    behavior — it alerts the operator to deduplicate manually before
    downgrading, rather than silently dropping conflicting rows. It is
    NOT a migration bug; it is the intentional failure mode per Alembic's
    reversibility contract.

Revision ID: 0066
Revises: 0065
Create Date: 2026-04-21

Issues: #933
Epic: #935 (Identity Semantics Audit & Hardening — three-tier identity)
Design review: Holden (session 67) — ``memory/design_review_933_holden_memo.md``
Cross-table audit follow-up: #937
ADR: #936 (three-tier identity model codification)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0066"
down_revision: str = "0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Demote ``idx_games_espn_event`` from partial UNIQUE to non-unique partial."""
    # Drop the pre-0066 partial UNIQUE index (from migration 0035).
    # Use IF EXISTS so the migration is idempotent across re-runs (e.g.,
    # repaired-rollback scenarios).  The subsequent CREATE has NO IF NOT
    # EXISTS — we want a loud failure if a residual index collides.
    op.execute("DROP INDEX IF EXISTS idx_games_espn_event")

    # Recreate as a non-unique partial btree.  Same name, same WHERE
    # predicate — schema doc / observability paths that refer to
    # ``idx_games_espn_event`` continue to resolve.
    op.execute(
        "CREATE INDEX idx_games_espn_event ON games (espn_event_id) WHERE espn_event_id IS NOT NULL"
    )


def downgrade() -> None:
    """Restore the pre-0066 partial UNIQUE index.

    NOTE: if any rows with duplicate non-NULL ``espn_event_id`` values
    were written while 0066 was in effect, the ``CREATE UNIQUE INDEX``
    statement below will RAISE ``duplicate key value violates unique
    constraint`` (or equivalent).  This is the intentional alert-on-
    downgrade behavior documented in the module docstring — the
    operator must dedupe manually before retrying the downgrade.

    To identify duplicates before retrying:
        SELECT espn_event_id, array_agg(id) AS duplicate_row_ids
        FROM games
        WHERE espn_event_id IS NOT NULL
        GROUP BY espn_event_id
        HAVING COUNT(*) > 1;
    """
    op.execute("DROP INDEX IF EXISTS idx_games_espn_event")
    op.execute(
        "CREATE UNIQUE INDEX idx_games_espn_event "
        "ON games (espn_event_id) "
        "WHERE espn_event_id IS NOT NULL"
    )
