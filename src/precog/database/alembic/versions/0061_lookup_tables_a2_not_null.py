"""0061: Lookup tables A2 — SET NOT NULL + drop redundant CHECK constraints.

Arc: #738 lookup tables (A1 nullable → A2 NOT NULL → B drop VARCHAR).

A1 (migration 0060) added nullable sport_id/league_id FK columns and
backfilled them from VARCHAR sport/league columns. A2 enforces NOT NULL
now that dual-write CRUD ensures all new rows populate the FK columns.

Steps:
    1. Backfill any remaining NULLs using the VARCHAR sport/league columns
       where they exist on the same table. Tables where the FK was resolved
       via a different path (e.g., game_odds.league_id via game lookup)
       are verified but not backfilled — they should already be clean.
    2. Verify zero NULLs on ALL FK columns (hard fail if any remain).
    3. SET NOT NULL on all 11 FK columns.
    4. DROP 9 redundant VARCHAR CHECK constraints.

The VARCHAR sport/league columns are NOT dropped here — that's arc B.

Issue: #738
Session: S58
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0061"
down_revision: str = "0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ── FK columns to enforce NOT NULL ──────────────────────────────────────
_FK_COLUMNS: list[tuple[str, str]] = [
    ("games", "sport_id"),
    ("games", "league_id"),
    ("teams", "sport_id"),
    ("teams", "league_id"),
    ("game_states", "league_id"),
    ("game_odds", "sport_id"),
    ("game_odds", "league_id"),
    ("external_team_codes", "league_id"),
    ("historical_stats", "sport_id"),
    ("historical_rankings", "sport_id"),
    ("historical_epa", "sport_id"),
    ("elo_calculation_log", "league_id"),
]

# ── Backfill pairs: (table, fk_col, varchar_col, lookup_table, lookup_key) ──
# Only tables that have the matching VARCHAR column on the SAME table.
# game_odds.league_id was resolved via game lookup in A1 — no VARCHAR league
# column exists on game_odds, so it's verify-only (not in this list).
_BACKFILL: list[tuple[str, str, str, str, str]] = [
    # sport_id backfills (from VARCHAR sport → sports.sport_key)
    ("games", "sport_id", "sport", "sports", "sport_key"),
    ("teams", "sport_id", "sport", "sports", "sport_key"),
    ("game_odds", "sport_id", "sport", "sports", "sport_key"),
    ("historical_stats", "sport_id", "sport", "sports", "sport_key"),
    ("historical_rankings", "sport_id", "sport", "sports", "sport_key"),
    ("historical_epa", "sport_id", "sport", "sports", "sport_key"),
    # league_id backfills (from VARCHAR league → leagues.league_key)
    ("games", "league_id", "league", "leagues", "league_key"),
    ("teams", "league_id", "league", "leagues", "league_key"),
    ("game_states", "league_id", "league", "leagues", "league_key"),
    ("external_team_codes", "league_id", "league", "leagues", "league_key"),
    ("elo_calculation_log", "league_id", "league", "leagues", "league_key"),
    # game_odds.league_id intentionally NOT here — no VARCHAR league column.
]

# ── CHECK constraints to drop ───────────────────────────────────────────
_CHECKS_TO_DROP: list[tuple[str, str]] = [
    ("games", "ck_games_sport"),
    ("teams", "teams_sport_check"),
    ("teams", "teams_league_check"),
    ("game_states", "game_states_league_check"),
    ("game_odds", "game_odds_sport_check"),
    ("historical_stats", "ck_historical_stats_sport"),
    ("historical_rankings", "ck_historical_rankings_sport"),
    ("historical_epa", "ck_historical_epa_sport"),
    ("elo_calculation_log", "ck_elo_log_sport"),
]


def upgrade() -> None:
    # ── Step 1: Backfill remaining NULLs ────────────────────────────────
    for table, fk_col, varchar_col, lookup_table, lookup_key in _BACKFILL:
        # safe: all values are from hardcoded constants above
        sql = (
            f"UPDATE {table} t SET {fk_col} = lk.id "  # noqa: S608
            f"FROM {lookup_table} lk "
            f"WHERE t.{varchar_col} = lk.{lookup_key} AND t.{fk_col} IS NULL"
        )
        op.execute(sa.text(sql))

    # ── Step 2: Verify zero NULLs ──────────────────────────────────────
    conn = op.get_bind()
    for table, col in _FK_COLUMNS:
        result = conn.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")  # noqa: S608
        ).scalar()
        if result and int(result) > 0:
            raise RuntimeError(
                f"Cannot SET NOT NULL: {table}.{col} still has {result} NULL rows. "
                f"Backfill did not resolve all values — check that the VARCHAR "
                f"column values match entries in the lookup table."
            )

    # ── Step 3: SET NOT NULL ────────────────────────────────────────────
    for table, col in _FK_COLUMNS:
        op.alter_column(table, col, nullable=False)

    # ── Step 4: DROP redundant CHECK constraints ────────────────────────
    for table, constraint_name in _CHECKS_TO_DROP:
        op.drop_constraint(constraint_name, table, type_="check")


def downgrade() -> None:
    # ── Reverse Step 4: CHECK constraints not recreated ─────────────────
    # Emergency rollback restores nullability only. The VARCHAR columns
    # still hold the original values, so the CHECKs are not load-bearing.

    # ── Reverse Step 3: restore nullable ────────────────────────────────
    for table, col in reversed(_FK_COLUMNS):
        op.alter_column(table, col, nullable=True)
