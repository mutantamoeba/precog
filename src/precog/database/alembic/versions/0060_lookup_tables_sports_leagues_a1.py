"""#738 Migration A1 — sports + leagues lookup tables, nullable FK columns, backfill.

This is the FIRST of three migrations in the #738 lookup-tables arc:

    A1 (THIS MIGRATION): Create lookup tables + nullable FK columns + backfill.
    A2 (future):         Enforce NOT NULL + drop CHECK constraints + recreate views.
    B  (future):         Drop deprecated VARCHAR sport/league columns.

Scope of A1:
  * Create `sports` (6 seeds: football, basketball, hockey, baseball, soccer, mma).
  * Create `leagues` (11 seeds: nfl, ncaaf, nba, ncaab, ncaaw, wnba, nhl, mlb,
    mls, soccer, ufc — each linked to parent `sport_id`).
  * Add NULLABLE `sport_id` / `league_id` FK columns on 10 tables (12 columns
    total — `game_odds` gets both `sport_id` AND `league_id`), with partial
    indexes on non-NULL values (per-table set — see `_FK_COLUMN_SPEC`).
  * Backfill the new FK columns from existing VARCHAR values.  Supports the
    mixed-convention case (`game_odds.sport` holds either sport names OR
    league codes — both cases covered by a two-step UPDATE).
  * Assert zero NULLs post-backfill; RAISE if any row fails to resolve.

Explicitly OUT OF SCOPE for A1:
  * NOT NULL enforcement on the new FK columns (A2).
  * Dropping the 9 CHECK constraints (A2).
  * View recreation (A2 — existing views still reference the VARCHAR columns).
  * Dropping VARCHAR sport/league columns (B).
  * Test fixture updates (A2, once NOT NULL lands).
  * Seed SQL file updates (A2).

The dual-write pattern in the CRUD layer (every INSERT writes BOTH the VARCHAR
value AND the resolved FK id) lands in the same PR as this migration.  Reads
can continue to use either surface during the A1 -> A2 window; once A2 enforces
NOT NULL, callers flip to FK-primary, and B drops the VARCHAR.

Unblocks:
  * #795 (UFC readiness) — `ufc` seed row on `mma` sport.

Revision ID: 0060
Revises: 0058
Create Date: 2026-04-15

Issues: #738 (partial — A1 of 3)
Epic: #745 (Schema Hardening Arc)
Design review: Session 54 (Holden + Galadriel, design_738_lookup_tables.md)
Parent PR: TBD (opened by Samwise, S57)
ADR: #116 (ODS Schema Conventions)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0060"
down_revision: str = "0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# =========================================================================
# Seed data (pinned in the migration so dev/test/prod all get the same IDs
# when running fresh, and incremental upgrades don't drift).
# =========================================================================

# `sports` seed rows.  `id` is allocated by SERIAL in insertion order; we
# rely on insertion order (1..6) rather than hardcoding IDs, so downstream
# JOINs use the `sport_key` business key -- not the numeric id.
_SPORTS_SEED = [
    ("football", "Football"),
    ("basketball", "Basketball"),
    ("hockey", "Hockey"),
    ("baseball", "Baseball"),
    ("soccer", "Soccer"),
    ("mma", "MMA"),
]

# `leagues` seed rows.  `sport_id` resolved via subquery on `sport_key`.
_LEAGUES_SEED = [
    # (league_key, sport_key, display_name)
    ("nfl", "football", "NFL"),
    ("ncaaf", "football", "NCAA Football"),
    ("nba", "basketball", "NBA"),
    ("ncaab", "basketball", "NCAA Men's Basketball"),
    ("ncaaw", "basketball", "NCAA Women's Basketball"),
    ("wnba", "basketball", "WNBA"),
    ("nhl", "hockey", "NHL"),
    ("mlb", "baseball", "MLB"),
    ("mls", "soccer", "MLS"),
    ("soccer", "soccer", "Soccer (generic)"),
    ("ufc", "mma", "UFC"),
]


# =========================================================================
# FK column specification per table.
#
# Each tuple: (table, varchar_column, new_fk_column, lookup_kind)
#   - varchar_column: existing column holding the sport/league string
#   - new_fk_column: name of the new FK column to add
#   - lookup_kind: one of:
#       "sport_direct"        - varchar holds a sport_key, resolve to sports.id
#       "league_direct"       - varchar holds a league_key, resolve to leagues.id
#       "league_to_sport"     - varchar holds a league_key, resolve to
#                               leagues.sport_id (i.e., derive sport via join)
#       "sport_or_league"     - varchar holds EITHER a sport_key OR a
#                               league_key; try sport first, fall back to
#                               leagues.sport_id
#       "join_via_game"       - the table has no sport/league varchar of its
#                               own; resolve league_id by joining through
#                               game_id -> games.league -> leagues.id.
#                               Used for `game_odds.league_id`: schema
#                               symmetry with other multi-sport tables, but
#                               game_odds has no `league` varchar column.
#                               Allows NULL when game_id IS NULL (unmatched
#                               imports), since those rows have no game row
#                               to join through.
#
# Partial index name: idx_<table>_<new_fk_column>
# =========================================================================
_FK_COLUMN_SPEC = [
    # (table, varchar_col, new_fk_col, lookup_kind)
    # --- sport_id additions ------------------------------------------------
    ("teams", "sport", "sport_id", "sport_direct"),
    ("games", "sport", "sport_id", "sport_direct"),
    ("game_odds", "sport", "sport_id", "sport_or_league"),
    ("historical_stats", "sport", "sport_id", "league_to_sport"),
    ("historical_rankings", "sport", "sport_id", "league_to_sport"),
    ("historical_epa", "sport", "sport_id", "league_to_sport"),
    # --- league_id additions -----------------------------------------------
    ("teams", "league", "league_id", "league_direct"),
    ("games", "league", "league_id", "league_direct"),
    ("game_states", "league", "league_id", "league_direct"),
    ("elo_calculation_log", "league", "league_id", "league_direct"),
    ("external_team_codes", "league", "league_id", "league_direct"),
    # game_odds.league_id: no native VARCHAR `league` column on this table,
    # so resolve via JOIN through game_id -> games.league -> leagues.id.
    # Rows with NULL game_id are permitted to remain NULL in league_id (the
    # zero-NULL assertion explicitly filters those out).  Listed AFTER
    # games.league_id so the games row is guaranteed populated when this
    # backfill runs (although the backfill SQL joins via games.league
    # VARCHAR, which is independent of games.league_id).
    ("game_odds", None, "league_id", "join_via_game"),
]


def _insert_seeds(conn: sa.engine.Connection) -> None:
    """Insert the pinned `sports` and `leagues` seed rows."""
    # sports
    for sport_key, display_name in _SPORTS_SEED:
        conn.execute(
            sa.text(
                "INSERT INTO sports (sport_key, display_name) VALUES (:sport_key, :display_name)"
            ),
            {"sport_key": sport_key, "display_name": display_name},
        )
    # leagues (sport_id resolved via subquery on sport_key)
    for league_key, sport_key, display_name in _LEAGUES_SEED:
        conn.execute(
            sa.text(
                "INSERT INTO leagues (league_key, sport_id, display_name) "
                "VALUES ("
                "    :league_key,"
                "    (SELECT id FROM sports WHERE sport_key = :sport_key),"
                "    :display_name"
                ")"
            ),
            {
                "league_key": league_key,
                "sport_key": sport_key,
                "display_name": display_name,
            },
        )


def _backfill_fk_column(
    conn: sa.engine.Connection,
    table: str,
    varchar_col: str | None,
    new_fk_col: str,
    lookup_kind: str,
) -> None:
    """Backfill the new FK column for one table, then assert zero NULLs.

    The four lookup strategies handle the distinct value-shape cases in the
    source data.  See `_FK_COLUMN_SPEC` comments for per-strategy semantics.
    """
    # NOTE: table/column names are interpolated from the hardcoded
    # `_FK_COLUMN_SPEC` module-level constant, not user input.  The S608
    # suppressions on each UPDATE below reflect that these are safe
    # dynamic identifiers, not a SQL-injection surface.
    if lookup_kind == "sport_direct":
        conn.execute(
            sa.text(
                f"UPDATE {table} SET {new_fk_col} = "  # noqa: S608
                f"  (SELECT s.id FROM sports s WHERE s.sport_key = {table}.{varchar_col}) "
                f"WHERE {varchar_col} IS NOT NULL"
            )
        )
    elif lookup_kind == "league_direct":
        conn.execute(
            sa.text(
                f"UPDATE {table} SET {new_fk_col} = "  # noqa: S608
                f"  (SELECT l.id FROM leagues l WHERE l.league_key = {table}.{varchar_col}) "
                f"WHERE {varchar_col} IS NOT NULL"
            )
        )
    elif lookup_kind == "league_to_sport":
        # varchar holds a league code, but we want the parent sport_id
        conn.execute(
            sa.text(
                f"UPDATE {table} SET {new_fk_col} = "  # noqa: S608
                f"  (SELECT l.sport_id FROM leagues l WHERE l.league_key = {table}.{varchar_col}) "
                f"WHERE {varchar_col} IS NOT NULL"
            )
        )
    elif lookup_kind == "sport_or_league":
        # Step 1: try direct sport_key match
        conn.execute(
            sa.text(
                f"UPDATE {table} SET {new_fk_col} = "  # noqa: S608
                f"  (SELECT s.id FROM sports s WHERE s.sport_key = {table}.{varchar_col}) "
                f"WHERE {varchar_col} IS NOT NULL "
                f"  AND {new_fk_col} IS NULL "
                f"  AND {table}.{varchar_col} IN (SELECT sport_key FROM sports)"
            )
        )
        # Step 2: for remaining nulls, try league_key -> sport_id
        conn.execute(
            sa.text(
                f"UPDATE {table} SET {new_fk_col} = "  # noqa: S608
                f"  (SELECT l.sport_id FROM leagues l WHERE l.league_key = {table}.{varchar_col}) "
                f"WHERE {varchar_col} IS NOT NULL "
                f"  AND {new_fk_col} IS NULL "
                f"  AND {table}.{varchar_col} IN (SELECT league_key FROM leagues)"
            )
        )
    elif lookup_kind == "join_via_game":
        # No native VARCHAR column — resolve league_id by joining through
        # game_id -> games.league -> leagues.league_key.  Works regardless
        # of whether games.league_id has been backfilled yet (joins to the
        # VARCHAR games.league value directly).
        # Rows with NULL game_id are left NULL (no game to join through).
        conn.execute(
            sa.text(
                f"UPDATE {table} SET {new_fk_col} = "  # noqa: S608
                f"  (SELECT l.id FROM leagues l "
                f"   JOIN games g ON g.league = l.league_key "
                f"   WHERE g.id = {table}.game_id) "
                f"WHERE {table}.game_id IS NOT NULL"
            )
        )
    else:
        raise ValueError(f"Unknown lookup_kind for {table}.{new_fk_col}: {lookup_kind!r}")

    # Zero-NULL assertion: every row with a non-NULL source column must have
    # resolved to a FK.  If any row failed to backfill, the migration
    # raises here rather than silently leaving holes (per PM direction).
    #
    # For "join_via_game" (varchar_col is None), the source key is game_id:
    # any row with non-NULL game_id must have resolved; rows with NULL
    # game_id are allowed to remain NULL in the FK column (no game to join
    # through).
    if lookup_kind == "join_via_game":
        # Filter: only rows with a joinable game_id must have resolved.
        null_count_filter = f"WHERE game_id IS NOT NULL AND {new_fk_col} IS NULL"
        null_count_label = "game_id"
    else:
        null_count_filter = f"WHERE {varchar_col} IS NOT NULL AND {new_fk_col} IS NULL"
        null_count_label = str(varchar_col)

    null_count_row = conn.execute(
        sa.text(
            f"SELECT COUNT(*) AS c FROM {table} "  # noqa: S608
            f"{null_count_filter}"
        )
    ).fetchone()
    null_count = int(null_count_row[0]) if null_count_row else 0
    if null_count > 0:
        # Surface the unmatched distinct values so ops has actionable info.
        sample_col = "game_id" if lookup_kind == "join_via_game" else str(varchar_col)
        sample = conn.execute(
            sa.text(
                f"SELECT DISTINCT {sample_col} FROM {table} "  # noqa: S608
                f"{null_count_filter} "
                f"LIMIT 20"
            )
        ).fetchall()
        sample_vals = [row[0] for row in sample]
        raise RuntimeError(
            f"[0060] Backfill failure on {table}.{new_fk_col}: "
            f"{null_count} row(s) with non-NULL {null_count_label} did not resolve "
            f"to a lookup id (lookup_kind={lookup_kind!r}). "
            f"Unmatched values: {sample_vals!r}. "
            f"Add missing rows to the sports/leagues seeds or UPDATE the "
            f"offending rows to a known value before retrying."
        )


def upgrade() -> None:
    """Create lookup tables + seed + add nullable FK columns + backfill."""
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Step 1: Create lookup tables
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE sports (
            id SERIAL PRIMARY KEY,
            sport_key VARCHAR(20) NOT NULL UNIQUE,
            display_name VARCHAR(100) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE leagues (
            id SERIAL PRIMARY KEY,
            league_key VARCHAR(20) NOT NULL UNIQUE,
            sport_id INTEGER NOT NULL REFERENCES sports(id) ON DELETE RESTRICT,
            display_name VARCHAR(100) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # ------------------------------------------------------------------
    # Step 2: Seed 6 sports + 11 leagues
    # ------------------------------------------------------------------
    _insert_seeds(conn)

    # ------------------------------------------------------------------
    # Step 3: Add nullable FK columns + partial indexes
    # ------------------------------------------------------------------
    for table, _varchar_col, new_fk_col, _lookup_kind in _FK_COLUMN_SPEC:
        parent_table = "sports" if new_fk_col == "sport_id" else "leagues"
        op.execute(
            f"ALTER TABLE {table} "
            f"ADD COLUMN {new_fk_col} INTEGER "
            f"REFERENCES {parent_table}(id) ON DELETE RESTRICT"
        )
        index_name = f"idx_{table}_{new_fk_col}"
        op.execute(
            f"CREATE INDEX {index_name} ON {table}({new_fk_col}) WHERE {new_fk_col} IS NOT NULL"
        )

    # ------------------------------------------------------------------
    # Step 4: Backfill (with zero-NULL assertion per column)
    # ------------------------------------------------------------------
    for table, varchar_col, new_fk_col, lookup_kind in _FK_COLUMN_SPEC:
        _backfill_fk_column(conn, table, varchar_col, new_fk_col, lookup_kind)


def downgrade() -> None:
    """Reverse the A1 migration: drop FK columns, drop seeds, drop lookup tables."""
    # Step 1: Drop the FK columns + partial indexes (indexes drop with columns)
    for table, _varchar_col, new_fk_col, _lookup_kind in _FK_COLUMN_SPEC:
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_{new_fk_col}")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {new_fk_col}")

    # Step 2: Drop lookup tables (RESTRICT auto-enforced; child FK columns
    # already gone, so DROP is safe).
    op.execute("DROP TABLE IF EXISTS leagues")
    op.execute("DROP TABLE IF EXISTS sports")
