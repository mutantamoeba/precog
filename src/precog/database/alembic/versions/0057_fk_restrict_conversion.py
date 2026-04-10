"""Convert all SET NULL and CASCADE foreign keys to ON DELETE RESTRICT.

Prevents silent data orphaning (SET NULL) and silent cascade deletion
(CASCADE) across the entire schema. Every FK should block parent deletion
instead of silently destroying provenance or child data. Also adds
SCD Type 2 columns (row_current_ind, row_start_ts, row_end_ts) to
teams, venues, and series for versioned soft-delete lifecycle management.

Revision ID: 0057
Revises: 0056
Create Date: 2026-04-10

Issues: #724, #725 (partial)
Epic: #745 (Schema Hardening Arc, Cohort C2)

Council attribution (Session 44):
    17 SET NULL FKs -> RESTRICT flagged by Holden, Vader, Cassandra (C1)
    9 CASCADE FKs -> RESTRICT flagged by Elrond, Mulder, Leto II (C1+C2)

Part A: FK RESTRICT Conversion (59 FKs)
    Every SET NULL and CASCADE FK converted to ON DELETE RESTRICT.
    Dynamic constraint name discovery via information_schema.
    Pre-flight orphan check + fix before constraint tightening.

Part B: SCD Type 2 Columns on teams, venues, series (3 tables)
    Same pattern as markets (0001), game_states (0001), positions (0001),
    edges (0001), account_balance (0001+0049):
        row_current_ind BOOLEAN NOT NULL DEFAULT TRUE
        row_start_ts    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        row_end_ts      TIMESTAMPTZ (nullable)
    Plus partial unique indexes on business keys and current-row indexes.

    Business key decisions:
        teams:  (team_code, league) -- team_code alone is NOT unique across
                sports (PHI = Eagles in NFL, 76ers in NBA; "WES" = 5 NCAAF
                teams). Uses league (not sport) for granularity -- sport
                groups NFL+NCAAF as 'football'. Matches the existing
                idx_teams_code_league_pro constraint (0039), which is
                dropped in this migration (it lacks row_current_ind filter).
        venues: espn_venue_id -- nullable, so NULL venues are not uniqueness-
                protected (PostgreSQL treats each NULL as distinct in UNIQUE).
        series: series_id -- unique business key (constraint uq_series_series_id
                from migration 0019).

FK INVENTORY (verified against migration files, phantoms removed):

SET NULL -> RESTRICT (31):
  1.  events.series_internal_id -> series(id)                     [0019]
  2.  edges.model_id -> probability_models(model_id)              [0001]
  3.  edges.strategy_id -> strategies(strategy_id)                [0023]
  4.  historical_epa.team_id -> teams(team_id)                    [0013]
  5.  elo_calculation_log.game_state_id -> game_states(id)        [0013]
  6.  elo_calculation_log.home_team_id -> teams(team_id)          [0013]
  7.  elo_calculation_log.away_team_id -> teams(team_id)          [0013]
  8.  elo_calculation_log.game_id -> games(id)                    [0035]
  9.  game_odds.home_team_id -> teams(team_id)                    [0013]
  10. game_odds.away_team_id -> teams(team_id)                    [0013]
  11. game_odds.game_id -> games(id)                              [0035]
  12. historical_stats.team_id -> teams(team_id)                  [0013]
  13. historical_rankings.team_id -> teams(team_id)               [0013]
  14. orders.strategy_id -> strategies(strategy_id)               [0025]
  15. orders.model_id -> probability_models(model_id)             [0025]
  16. orders.edge_id -> edges(id)                                 [0025]
  17. orders.position_id -> positions(id)                         [0025]
  18. trades.order_id -> orders(id)                               [0025]
  19. account_ledger.order_id -> orders(id)                       [0026]
  20. evaluation_runs.model_id -> probability_models(model_id)    [0031]
  21. evaluation_runs.strategy_id -> strategies(strategy_id)      [0031]
  22. backtesting_runs.strategy_id -> strategies(strategy_id)     [0031]
  23. backtesting_runs.model_id -> probability_models(model_id)   [0031]
  24. predictions.model_id -> probability_models(model_id)        [0031]
  25. predictions.event_id -> events(id)                          [0031]
  26. games.home_team_id -> teams(team_id)                        [0035]
  27. games.away_team_id -> teams(team_id)                        [0035]
  28. games.venue_id -> venues(venue_id)                          [0035]
  29. game_states.game_id -> games(id)                            [0035]
  30. events.game_id -> games(id)                                 [0038]
  31. temporal_alignment.game_id -> games(id)                     [0035]

CASCADE -> RESTRICT (28):
  Platform CASCADEs (11):
  32. series.platform_id -> platforms(platform_id)                [0001]
  33. events.platform_id -> platforms(platform_id)                [0001]
  34. markets.platform_id -> platforms(platform_id)               [0021]
  35. strategies.platform_id -> platforms(platform_id)            [0001]
  36. positions.platform_id -> platforms(platform_id)             [0001]
  37. trades.platform_id -> platforms(platform_id)                [0001]
  38. settlements.platform_id -> platforms(platform_id)           [0001]
  39. account_balance.platform_id -> platforms(platform_id)       [0001]
  40. orders.platform_id -> platforms(platform_id)                [0025]
  41. account_ledger.platform_id -> platforms(platform_id)        [0026]
  42. market_trades.platform_id -> platforms(platform_id)         [0028]
  Non-platform CASCADEs (17):
  43. markets.event_internal_id -> events(id)                     [0020]
  44. team_rankings.team_id -> teams(team_id)                     [0001]
  45. position_exits.position_internal_id -> positions(id)        [0001]
  46. exit_attempts.position_internal_id -> positions(id)         [0001]
  47. market_snapshots.market_id -> markets(id)                   [0021]
  48. orders.market_internal_id -> markets(id)                    [0022]
  49. market_trades.market_internal_id -> markets(id)             [0022/0028]
  50. predictions.evaluation_run_id -> evaluation_runs(id)        [0031]
  51. predictions.market_id -> markets(id)                        [0031]
  52. orderbook_snapshots.market_internal_id -> markets(id)       [0034]
  53. temporal_alignment.market_id -> markets(id)                 [0027]
  54. temporal_alignment.market_snapshot_id -> market_snapshots(id)[0027]
  55. temporal_alignment.game_state_id -> game_states(id)         [0027]
  56. edges.market_internal_id -> markets(id)                     [0022]
  57. positions.market_internal_id -> markets(id)                 [0022]
  58. trades.market_internal_id -> markets(id)                    [0022]
  59. settlements.market_internal_id -> markets(id)               [0022]

SCD Type 2 columns + indexes (3 tables):
  60. teams:  row_current_ind, row_start_ts, row_end_ts
            + idx_teams_current (partial on row_current_ind)
            + idx_teams_unique_current (partial unique on team_code, sport)
  61. venues: row_current_ind, row_start_ts, row_end_ts
            + idx_venues_current (partial on row_current_ind)
            + idx_venues_unique_current (partial unique on espn_venue_id)
  62. series: row_current_ind, row_start_ts, row_end_ts
            + idx_series_current (partial on row_current_ind)
            + idx_series_unique_current (partial unique on series_id)

PHANTOM FKs EXCLUDED (verified absent from current schema):
  - elo_rating_history.team_id (table dropped in 0015)
  - historical_games.home_team_id / away_team_id (table dropped in 0035)
  - elo_calculation_log.historical_game_id (column dropped in 0035)
  - trades.edge_internal_id (column dropped in 0025)
  - trades.position_internal_id (column dropped in 0025)
  - market_snapshots.game_snapshot_id (column never existed)

DISCREPANCIES vs original task brief:
  - trades.position_internal_id: PHANTOM (column dropped in migration 0025,
    replaced by trades.order_id -> orders(id))
  - game_odds.game_id: MISSING from original inventory (SET NULL, from 0035)
  - temporal_alignment.game_id: MISSING from original inventory (SET NULL, from 0035)
  - temporal_alignment.market_id: MISSING from original inventory (CASCADE, from 0027)
  - temporal_alignment.market_snapshot_id: MISSING from original inventory (CASCADE, from 0027)
  - temporal_alignment.game_state_id: MISSING from original inventory (CASCADE, from 0027)
  - edges/positions/trades/settlements.market_internal_id: MISSING from original
    inventory (CASCADE, from 0022, explicitly named constraints)
  - teams business key: task brief said team_code alone, but team_code is NOT
    unique (migration 0003 changed to UNIQUE(team_code, sport), 0018 relaxed to
    pro leagues only). Using (team_code, sport) to match existing uniqueness.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0057"
down_revision: str = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# =============================================================================
# FK conversion specification
# =============================================================================
# Each tuple: (child_table, child_column, parent_table, parent_column, old_behavior)
# Constraint names follow PostgreSQL auto-naming: {table}_{column}_fkey
# unless explicitly named in the migration that created them.

SET_NULL_FKS: list[tuple[str, str, str, str]] = [
    # events
    ("events", "series_internal_id", "series", "id"),
    ("events", "game_id", "games", "id"),
    # edges
    ("edges", "model_id", "probability_models", "model_id"),
    ("edges", "strategy_id", "strategies", "strategy_id"),
    # historical_epa
    ("historical_epa", "team_id", "teams", "team_id"),
    # elo_calculation_log
    ("elo_calculation_log", "game_state_id", "game_states", "id"),
    ("elo_calculation_log", "home_team_id", "teams", "team_id"),
    ("elo_calculation_log", "away_team_id", "teams", "team_id"),
    ("elo_calculation_log", "game_id", "games", "id"),
    # game_odds (renamed from historical_odds in 0048)
    ("game_odds", "home_team_id", "teams", "team_id"),
    ("game_odds", "away_team_id", "teams", "team_id"),
    ("game_odds", "game_id", "games", "id"),
    # historical_stats
    ("historical_stats", "team_id", "teams", "team_id"),
    # historical_rankings
    ("historical_rankings", "team_id", "teams", "team_id"),
    # orders
    ("orders", "strategy_id", "strategies", "strategy_id"),
    ("orders", "model_id", "probability_models", "model_id"),
    ("orders", "edge_id", "edges", "id"),
    ("orders", "position_id", "positions", "id"),
    # trades
    ("trades", "order_id", "orders", "id"),
    # account_ledger
    ("account_ledger", "order_id", "orders", "id"),
    # evaluation_runs
    ("evaluation_runs", "model_id", "probability_models", "model_id"),
    ("evaluation_runs", "strategy_id", "strategies", "strategy_id"),
    # backtesting_runs
    ("backtesting_runs", "strategy_id", "strategies", "strategy_id"),
    ("backtesting_runs", "model_id", "probability_models", "model_id"),
    # predictions
    ("predictions", "model_id", "probability_models", "model_id"),
    ("predictions", "event_id", "events", "id"),
    # games
    ("games", "home_team_id", "teams", "team_id"),
    ("games", "away_team_id", "teams", "team_id"),
    ("games", "venue_id", "venues", "venue_id"),
    # game_states
    ("game_states", "game_id", "games", "id"),
    # temporal_alignment
    ("temporal_alignment", "game_id", "games", "id"),
]

CASCADE_FKS: list[tuple[str, str, str, str]] = [
    # Platform CASCADEs
    ("series", "platform_id", "platforms", "platform_id"),
    ("events", "platform_id", "platforms", "platform_id"),
    ("markets", "platform_id", "platforms", "platform_id"),
    ("strategies", "platform_id", "platforms", "platform_id"),
    ("positions", "platform_id", "platforms", "platform_id"),
    ("trades", "platform_id", "platforms", "platform_id"),
    ("settlements", "platform_id", "platforms", "platform_id"),
    ("account_balance", "platform_id", "platforms", "platform_id"),
    ("orders", "platform_id", "platforms", "platform_id"),
    ("account_ledger", "platform_id", "platforms", "platform_id"),
    ("market_trades", "platform_id", "platforms", "platform_id"),
    # Non-platform CASCADEs
    ("markets", "event_internal_id", "events", "id"),
    ("team_rankings", "team_id", "teams", "team_id"),
    ("position_exits", "position_internal_id", "positions", "id"),
    ("exit_attempts", "position_internal_id", "positions", "id"),
    ("market_snapshots", "market_id", "markets", "id"),
    ("orders", "market_internal_id", "markets", "id"),
    ("market_trades", "market_internal_id", "markets", "id"),
    ("predictions", "evaluation_run_id", "evaluation_runs", "id"),
    ("predictions", "market_id", "markets", "id"),
    ("orderbook_snapshots", "market_internal_id", "markets", "id"),
    ("temporal_alignment", "market_id", "markets", "id"),
    ("temporal_alignment", "market_snapshot_id", "market_snapshots", "id"),
    ("temporal_alignment", "game_state_id", "game_states", "id"),
    ("edges", "market_internal_id", "markets", "id"),
    ("positions", "market_internal_id", "markets", "id"),
    ("trades", "market_internal_id", "markets", "id"),
    ("settlements", "market_internal_id", "markets", "id"),
]

# Explicitly named constraints (not following {table}_{column}_fkey pattern)
NAMED_CONSTRAINTS: dict[tuple[str, str], str] = {
    ("events", "series_internal_id"): "fk_events_series_internal",
    ("markets", "event_internal_id"): "fk_markets_event_internal",
    ("orders", "market_internal_id"): "orders_market_internal_id_fkey",
    ("market_trades", "market_internal_id"): "market_trades_market_internal_id_fkey",
    ("edges", "market_internal_id"): "edges_market_internal_id_fkey",
    ("positions", "market_internal_id"): "positions_market_internal_id_fkey",
    ("trades", "market_internal_id"): "trades_market_internal_id_fkey",
    ("settlements", "market_internal_id"): "settlements_market_internal_id_fkey",
}


def _get_constraint_name(table: str, column: str) -> str:
    """Return the constraint name for a given table+column FK.

    Uses explicitly named constraints where known, otherwise falls
    back to PostgreSQL auto-naming convention: {table}_{column}_fkey.
    """
    return NAMED_CONSTRAINTS.get((table, column), f"{table}_{column}_fkey")


def _fix_orphans_and_convert(
    conn: sa.engine.Connection,
    child_table: str,
    child_column: str,
    parent_table: str,
    parent_column: str,
) -> None:
    """Pre-flight orphan check, fix orphans, then convert FK to RESTRICT.

    Steps:
        1. Find the actual constraint name from information_schema
           (handles cases where auto-naming assumptions are wrong)
        2. Check for orphaned rows (child FK value pointing to
           non-existent parent)
        3. If orphans exist, SET NULL those specific rows
        4. Drop old constraint
        5. Add new constraint with ON DELETE RESTRICT
    """
    # Step 1: Discover actual constraint name from information_schema
    result = conn.execute(
        sa.text("""
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_name = :table_name
                AND kcu.column_name = :column_name
                AND tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'
        """),
        {"table_name": child_table, "column_name": child_column},
    )
    row = result.fetchone()
    if row is None:
        # FK does not exist -- skip silently (may have been dropped in
        # a later migration that we didn't account for)
        return
    actual_constraint_name = row[0]

    # Step 2: Pre-flight orphan check
    orphan_count = conn.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {child_table} c "  # noqa: S608
            f"LEFT JOIN {parent_table} p ON c.{child_column} = p.{parent_column} "
            f"WHERE c.{child_column} IS NOT NULL AND p.{parent_column} IS NULL"
        )
    ).scalar()

    # Step 3: Fix orphans if any exist
    if orphan_count and orphan_count > 0:
        # Use NOT EXISTS instead of NOT IN to avoid NULL pitfall
        # (NOT IN with NULLs in the subquery returns no rows)
        conn.execute(
            sa.text(
                f"UPDATE {child_table} SET {child_column} = NULL "  # noqa: S608
                f"WHERE {child_column} IS NOT NULL "
                f"AND NOT EXISTS ("
                f"SELECT 1 FROM {parent_table} "
                f"WHERE {parent_table}.{parent_column} = {child_table}.{child_column}"
                f")"
            )
        )

    # Step 4: Drop old constraint
    conn.execute(sa.text(f"ALTER TABLE {child_table} DROP CONSTRAINT {actual_constraint_name}"))

    # Step 5: Add new constraint with ON DELETE RESTRICT
    conn.execute(
        sa.text(
            f"ALTER TABLE {child_table} "
            f"ADD CONSTRAINT {actual_constraint_name} "
            f"FOREIGN KEY ({child_column}) REFERENCES {parent_table}({parent_column}) "
            f"ON DELETE RESTRICT"
        )
    )


def upgrade() -> None:
    """Convert all SET NULL and CASCADE FKs to RESTRICT; add SCD Type 2 columns."""
    conn = op.get_bind()

    # =========================================================================
    # Phase 1: Convert SET NULL FKs to RESTRICT (31 FKs)
    # =========================================================================
    for child_table, child_column, parent_table, parent_column in SET_NULL_FKS:
        _fix_orphans_and_convert(
            conn,
            child_table,
            child_column,
            parent_table,
            parent_column,
        )

    # =========================================================================
    # Phase 2: Convert CASCADE FKs to RESTRICT (28 FKs)
    # =========================================================================
    for child_table, child_column, parent_table, parent_column in CASCADE_FKS:
        _fix_orphans_and_convert(
            conn,
            child_table,
            child_column,
            parent_table,
            parent_column,
        )

    # =========================================================================
    # Phase 3: Add SCD Type 2 columns to dimension tables (3 tables)
    # Pattern match: markets, game_states, positions, edges, account_balance
    # all use (row_current_ind, row_start_ts, row_end_ts) from migration 0001.
    # =========================================================================
    for table in ("teams", "venues", "series"):
        op.execute(f"""
            ALTER TABLE {table}
            ADD COLUMN row_current_ind BOOLEAN NOT NULL DEFAULT TRUE,
            ADD COLUMN row_start_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ADD COLUMN row_end_ts TIMESTAMPTZ
        """)

        # Backfill row_start_ts from created_at for existing rows
        op.execute(
            f"UPDATE {table} SET row_start_ts = created_at "  # noqa: S608
            f"WHERE created_at IS NOT NULL"
        )

    # ── Drop existing UNIQUE constraints that conflict with SCD versioning ──
    # SCD Type 2 requires multiple rows with the same business key (one
    # current, N historical). Full UNIQUE constraints block this.
    # The partial unique indexes below provide equivalent current-row
    # protection.

    # series: drop global UNIQUE on series_id and (platform_id, external_id)
    # from migration 0019 — SCD versioning needs multiple rows per series_id
    op.execute("ALTER TABLE series DROP CONSTRAINT IF EXISTS uq_series_series_id")
    op.execute("ALTER TABLE series DROP CONSTRAINT IF EXISTS uq_series_platform_external")

    # venues: drop global UNIQUE on espn_venue_id from migration 0001
    op.execute("ALTER TABLE venues DROP CONSTRAINT IF EXISTS venues_espn_venue_id_key")

    # teams: drop partial unique index on (team_code, league) for pro leagues
    # from migration 0039 — it doesn't filter on row_current_ind so it
    # blocks SCD historical rows
    op.execute("DROP INDEX IF EXISTS idx_teams_code_league_pro")

    # teams: drop global unique index on (espn_team_id, league) from
    # migration 0017 — also blocks SCD historical rows (no row_current_ind)
    op.execute("DROP INDEX IF EXISTS idx_teams_espn_id_league_unique")

    # ── Current-row filter indexes (same pattern as idx_markets_current) ──
    op.execute("""
        CREATE INDEX idx_teams_current
        ON teams(row_current_ind) WHERE row_current_ind = TRUE
    """)
    op.execute("""
        CREATE INDEX idx_venues_current
        ON venues(row_current_ind) WHERE row_current_ind = TRUE
    """)
    op.execute("""
        CREATE INDEX idx_series_current
        ON series(row_current_ind) WHERE row_current_ind = TRUE
    """)

    # ── Partial unique indexes on business keys (SCD Type 2 enforcement) ──
    # Only ONE current row per business entity.

    # teams: business key is (team_code, league) -- team_code alone is not
    # unique (PHI = Eagles in NFL, 76ers in NBA). league is more granular
    # than sport (sport='football' covers both NFL and NCAAF). Matches the
    # existing idx_teams_code_league_pro constraint granularity (0039).
    op.execute("""
        CREATE UNIQUE INDEX idx_teams_unique_current
        ON teams(team_code, league) WHERE row_current_ind = TRUE
    """)

    # venues: business key is espn_venue_id -- nullable, so multiple
    # venues without ESPN IDs are permitted (PostgreSQL treats each NULL
    # as distinct in UNIQUE indexes).
    op.execute("""
        CREATE UNIQUE INDEX idx_venues_unique_current
        ON venues(espn_venue_id) WHERE row_current_ind = TRUE
    """)

    # teams: ESPN ID + league uniqueness (replaces idx_teams_espn_id_league_unique
    # from 0017 which lacked row_current_ind filter)
    op.execute("""
        CREATE UNIQUE INDEX idx_teams_espn_id_league_current
        ON teams(espn_team_id, league) WHERE row_current_ind = TRUE
    """)

    # series: business key is series_id -- replaces uq_series_series_id
    # from migration 0019.
    op.execute("""
        CREATE UNIQUE INDEX idx_series_unique_current
        ON series(series_id) WHERE row_current_ind = TRUE
    """)

    # series: platform + external_id composite -- replaces
    # uq_series_platform_external from 0019. Prevents two current series
    # from the same platform with the same external identifier.
    op.execute("""
        CREATE UNIQUE INDEX idx_series_platform_external_current
        ON series(platform_id, external_id) WHERE row_current_ind = TRUE
    """)

    # ── Helper views (same pattern as current_markets, current_game_states) ──
    op.execute("""
        CREATE OR REPLACE VIEW current_teams AS
        SELECT * FROM teams WHERE row_current_ind = TRUE
    """)
    op.execute("""
        CREATE OR REPLACE VIEW current_venues AS
        SELECT * FROM venues WHERE row_current_ind = TRUE
    """)
    op.execute("""
        CREATE OR REPLACE VIEW current_series AS
        SELECT * FROM series WHERE row_current_ind = TRUE
    """)

    # Column comments
    op.execute("""
        COMMENT ON COLUMN teams.row_current_ind IS
        'SCD Type 2: TRUE = current version, FALSE = historical. '
        'Always filter by row_current_ind = TRUE for current data.'
    """)
    op.execute("""
        COMMENT ON COLUMN venues.row_current_ind IS
        'SCD Type 2: TRUE = current version, FALSE = historical. '
        'Always filter by row_current_ind = TRUE for current data.'
    """)
    op.execute("""
        COMMENT ON COLUMN series.row_current_ind IS
        'SCD Type 2: TRUE = current version, FALSE = historical. '
        'Always filter by row_current_ind = TRUE for current data.'
    """)


def downgrade() -> None:
    """Reverse: drop SCD columns + indexes, re-create FKs with original ON DELETE."""
    conn = op.get_bind()

    # =========================================================================
    # Phase 1: Drop SCD Type 2 views, indexes, columns, restore constraints
    # =========================================================================
    # Drop helper views first
    op.execute("DROP VIEW IF EXISTS current_series")
    op.execute("DROP VIEW IF EXISTS current_venues")
    op.execute("DROP VIEW IF EXISTS current_teams")

    # Drop SCD indexes (they depend on the columns)
    op.execute("DROP INDEX IF EXISTS idx_series_platform_external_current")
    op.execute("DROP INDEX IF EXISTS idx_series_unique_current")
    op.execute("DROP INDEX IF EXISTS idx_venues_unique_current")
    op.execute("DROP INDEX IF EXISTS idx_teams_espn_id_league_current")
    op.execute("DROP INDEX IF EXISTS idx_teams_unique_current")
    op.execute("DROP INDEX IF EXISTS idx_series_current")
    op.execute("DROP INDEX IF EXISTS idx_venues_current")
    op.execute("DROP INDEX IF EXISTS idx_teams_current")

    # Drop SCD columns
    for table in ("series", "venues", "teams"):
        op.execute(f"""
            ALTER TABLE {table}
            DROP COLUMN IF EXISTS row_end_ts,
            DROP COLUMN IF EXISTS row_start_ts,
            DROP COLUMN IF EXISTS row_current_ind
        """)

    # Restore the original UNIQUE constraints dropped in upgrade
    op.execute("ALTER TABLE series ADD CONSTRAINT uq_series_series_id UNIQUE (series_id)")
    op.execute(
        "ALTER TABLE series ADD CONSTRAINT uq_series_platform_external "
        "UNIQUE (platform_id, external_id)"
    )
    op.execute("ALTER TABLE venues ADD CONSTRAINT venues_espn_venue_id_key UNIQUE (espn_venue_id)")
    # Restore ESPN ID + league unique index from migration 0017
    op.execute("""
        CREATE UNIQUE INDEX idx_teams_espn_id_league_unique
        ON teams(espn_team_id, league)
    """)
    # Restore pro-league partial unique index from migration 0039
    op.execute("""
        CREATE UNIQUE INDEX idx_teams_code_league_pro
        ON teams(team_code, league)
        WHERE league IN ('nfl', 'nba', 'nhl', 'wnba', 'mlb', 'mls')
    """)

    # =========================================================================
    # Phase 2: Revert CASCADE FKs (currently RESTRICT -> back to CASCADE)
    # =========================================================================
    for child_table, child_column, parent_table, parent_column in CASCADE_FKS:
        # Discover actual constraint name
        result = conn.execute(
            sa.text("""
                SELECT tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_name = :table_name
                    AND kcu.column_name = :column_name
                    AND tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
            """),
            {"table_name": child_table, "column_name": child_column},
        )
        row = result.fetchone()
        if row is None:
            continue
        actual_constraint_name = row[0]

        conn.execute(sa.text(f"ALTER TABLE {child_table} DROP CONSTRAINT {actual_constraint_name}"))
        conn.execute(
            sa.text(
                f"ALTER TABLE {child_table} "
                f"ADD CONSTRAINT {actual_constraint_name} "
                f"FOREIGN KEY ({child_column}) "
                f"REFERENCES {parent_table}({parent_column}) "
                f"ON DELETE CASCADE"
            )
        )

    # =========================================================================
    # Phase 3: Revert SET NULL FKs (currently RESTRICT -> back to SET NULL)
    # =========================================================================
    for child_table, child_column, parent_table, parent_column in SET_NULL_FKS:
        # Discover actual constraint name
        result = conn.execute(
            sa.text("""
                SELECT tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_name = :table_name
                    AND kcu.column_name = :column_name
                    AND tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
            """),
            {"table_name": child_table, "column_name": child_column},
        )
        row = result.fetchone()
        if row is None:
            continue
        actual_constraint_name = row[0]

        conn.execute(sa.text(f"ALTER TABLE {child_table} DROP CONSTRAINT {actual_constraint_name}"))
        conn.execute(
            sa.text(
                f"ALTER TABLE {child_table} "
                f"ADD CONSTRAINT {actual_constraint_name} "
                f"FOREIGN KEY ({child_column}) "
                f"REFERENCES {parent_table}({parent_column}) "
                f"ON DELETE SET NULL"
            )
        )
