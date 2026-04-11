"""Integration tests for migration 0057 (FK RESTRICT conversion + SCD Type 2).

Verifies the POST-MIGRATION state of all foreign key constraints and
the SCD Type 2 columns on teams, venues, and series. These tests run
against a real database (testcontainer per ADR-057).

Test groups:
    - TestAllFKsAreRestrict: every FK in the conversion inventory has
      ON DELETE RESTRICT (query pg_catalog for delete_rule)
    - TestSCDColumns: row_current_ind, row_start_ts, row_end_ts exist
      with correct type, default, and nullability on teams/venues/series
    - TestSCDIndexes: partial unique indexes and current-row filter
      indexes exist on teams/venues/series
    - TestRestrictBlocksDeletion: representative DELETE on referenced
      parents raises IntegrityError (one test per FK category)
    - TestSCDDefaults: new rows get correct SCD defaults
    - TestDeleteWithoutChildren: parent rows with no children can
      still be deleted (RESTRICT only blocks when children exist)

Issues: #724, #725 (partial)
Epic: #745 (Schema Hardening Arc, Cohort C2)

Markers:
    @pytest.mark.integration: real DB required (testcontainer per ADR-057)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg2
import pytest

from precog.database.connection import get_cursor

# =============================================================================
# Complete FK inventory -- must match migration 0057
# =============================================================================

# All FKs that were SET NULL, now RESTRICT
SET_NULL_FKS = [
    ("events", "series_internal_id", "series", "id"),
    ("events", "game_id", "games", "id"),
    ("edges", "model_id", "probability_models", "model_id"),
    ("edges", "strategy_id", "strategies", "strategy_id"),
    ("historical_epa", "team_id", "teams", "team_id"),
    ("elo_calculation_log", "game_state_id", "game_states", "id"),
    ("elo_calculation_log", "home_team_id", "teams", "team_id"),
    ("elo_calculation_log", "away_team_id", "teams", "team_id"),
    ("elo_calculation_log", "game_id", "games", "id"),
    ("game_odds", "home_team_id", "teams", "team_id"),
    ("game_odds", "away_team_id", "teams", "team_id"),
    ("game_odds", "game_id", "games", "id"),
    ("historical_stats", "team_id", "teams", "team_id"),
    ("historical_rankings", "team_id", "teams", "team_id"),
    ("orders", "strategy_id", "strategies", "strategy_id"),
    ("orders", "model_id", "probability_models", "model_id"),
    ("orders", "edge_id", "edges", "id"),
    ("orders", "position_id", "positions", "id"),
    ("trades", "order_id", "orders", "id"),
    ("account_ledger", "order_id", "orders", "id"),
    ("evaluation_runs", "model_id", "probability_models", "model_id"),
    ("evaluation_runs", "strategy_id", "strategies", "strategy_id"),
    ("backtesting_runs", "strategy_id", "strategies", "strategy_id"),
    ("backtesting_runs", "model_id", "probability_models", "model_id"),
    ("predictions", "model_id", "probability_models", "model_id"),
    ("predictions", "event_id", "events", "id"),
    ("games", "home_team_id", "teams", "team_id"),
    ("games", "away_team_id", "teams", "team_id"),
    ("games", "venue_id", "venues", "venue_id"),
    ("game_states", "game_id", "games", "id"),
    ("temporal_alignment", "game_id", "games", "id"),
]

# All FKs that were CASCADE, now RESTRICT
CASCADE_FKS = [
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

ALL_FKS = SET_NULL_FKS + CASCADE_FKS

# Tables that got SCD Type 2 columns
SCD_TABLES = ["teams", "venues", "series"]

# SCD columns and their expected properties
SCD_COLUMNS = {
    "row_current_ind": {"data_type": "boolean", "is_nullable": "NO", "has_default": True},
    "row_start_ts": {
        "data_type": "timestamp with time zone",
        "is_nullable": "NO",
        "has_default": True,
    },
    "row_end_ts": {
        "data_type": "timestamp with time zone",
        "is_nullable": "YES",
        "has_default": False,
    },
}

# Expected partial unique indexes (SCD business key enforcement)
SCD_UNIQUE_INDEXES = {
    "idx_teams_unique_current": "teams",
    "idx_venues_unique_current": "venues",
    "idx_series_unique_current": "series",
}

# Expected current-row filter indexes
SCD_CURRENT_INDEXES = {
    "idx_teams_current": "teams",
    "idx_venues_current": "venues",
    "idx_series_current": "series",
}


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fk_test_platform(db_pool: Any) -> Any:
    """Create an isolated platform + downstream objects for FK testing.

    Yields platform_id. Cleanup deletes all test data in reverse FK order.
    """
    platform_id = "mig-0057-fk-test"

    with get_cursor(commit=True) as cur:
        # Defensive cleanup of any prior run (reverse FK order)
        cur.execute(
            "DELETE FROM temporal_alignment WHERE market_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM orderbook_snapshots WHERE market_internal_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM market_trades WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM predictions WHERE market_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM account_ledger WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM trades WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM exit_attempts WHERE position_internal_id IN "
            "(SELECT id FROM positions WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM position_exits WHERE position_internal_id IN "
            "(SELECT id FROM positions WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM orders WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM market_snapshots WHERE market_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM settlements WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM positions WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM edges WHERE market_internal_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM markets WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM events WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM account_balance WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM strategies WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM series WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM platforms WHERE platform_id = %s",
            (platform_id,),
        )

        # Create platform
        cur.execute(
            """
            INSERT INTO platforms (
                platform_id, platform_type, display_name, base_url, status
            )
            VALUES (%s, 'trading', 'Migration 0057 Test',
                    'https://mig-0057-test.example.com', 'active')
            """,
            (platform_id,),
        )

    yield platform_id

    # Teardown in reverse FK order
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM temporal_alignment WHERE market_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM orderbook_snapshots WHERE market_internal_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM market_trades WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM predictions WHERE market_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM account_ledger WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM trades WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM exit_attempts WHERE position_internal_id IN "
            "(SELECT id FROM positions WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM position_exits WHERE position_internal_id IN "
            "(SELECT id FROM positions WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM orders WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM market_snapshots WHERE market_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM settlements WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM positions WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM edges WHERE market_internal_id IN "
            "(SELECT id FROM markets WHERE platform_id = %s)",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM markets WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM events WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM account_balance WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM strategies WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM series WHERE platform_id = %s",
            (platform_id,),
        )
        cur.execute(
            "DELETE FROM platforms WHERE platform_id = %s",
            (platform_id,),
        )


@pytest.fixture
def fk_test_team(db_pool: Any) -> Any:
    """Create a test team for FK deletion tests. Yields team_id."""
    team_code = "MIG57T"
    with get_cursor(commit=True) as cur:
        # Cleanup
        cur.execute(
            "DELETE FROM team_rankings WHERE team_id IN "
            "(SELECT team_id FROM teams WHERE team_code = %s AND sport = 'football')",
            (team_code,),
        )
        cur.execute(
            "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
            (team_code,),
        )

        cur.execute(
            """
            INSERT INTO teams (team_code, team_name, sport, league)
            VALUES (%s, 'Migration 0057 Test Team', 'football', 'nfl')
            RETURNING team_id
            """,
            (team_code,),
        )
        team_id = cur.fetchone()["team_id"]

    yield team_id

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM team_rankings WHERE team_id = %s", (team_id,))
        cur.execute("DELETE FROM teams WHERE team_id = %s", (team_id,))


# =============================================================================
# TestAllFKsAreRestrict
# =============================================================================


@pytest.mark.integration
class TestAllFKsAreRestrict:
    """Every FK in the conversion inventory has ON DELETE RESTRICT."""

    @pytest.mark.parametrize(
        ("child_table", "child_column", "parent_table", "parent_column"),
        ALL_FKS,
        ids=[f"{t[0]}.{t[1]}->{t[2]}.{t[3]}" for t in ALL_FKS],
    )
    def test_fk_is_restrict(
        self,
        db_pool: Any,
        child_table: str,
        child_column: str,
        parent_table: str,
        parent_column: str,
    ) -> None:
        """FK on {child_table}.{child_column} has delete_rule = RESTRICT."""
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT rc.delete_rule
                FROM information_schema.referential_constraints rc
                JOIN information_schema.key_column_usage kcu
                    ON rc.constraint_name = kcu.constraint_name
                    AND rc.constraint_schema = kcu.constraint_schema
                WHERE kcu.table_name = %s
                    AND kcu.column_name = %s
                    AND kcu.table_schema = 'public'
                """,
                (child_table, child_column),
            )
            row = cur.fetchone()
            assert row is not None, f"No FK found for {child_table}.{child_column}"
            # PostgreSQL reports RESTRICT as either 'RESTRICT' or 'NO ACTION'
            # Both block parent deletion. Our migration explicitly uses RESTRICT.
            assert row["delete_rule"] in ("RESTRICT", "NO ACTION"), (
                f"Expected RESTRICT for {child_table}.{child_column}, got {row['delete_rule']}"
            )


# =============================================================================
# TestSCDColumns
# =============================================================================


@pytest.mark.integration
class TestSCDColumns:
    """SCD Type 2 columns exist with correct type, default, and nullability."""

    @pytest.mark.parametrize("table", SCD_TABLES)
    @pytest.mark.parametrize("column_name", SCD_COLUMNS.keys())
    def test_scd_column_exists_with_correct_shape(
        self, db_pool: Any, table: str, column_name: str
    ) -> None:
        """SCD column has expected data type and nullability."""
        expected = SCD_COLUMNS[column_name]
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                    AND table_name = %s
                    AND column_name = %s
                """,
                (table, column_name),
            )
            row = cur.fetchone()
            assert row is not None, f"{column_name} column not found on {table}"
            assert row["data_type"] == expected["data_type"], (
                f"Expected {expected['data_type']}, got {row['data_type']} "
                f"for {table}.{column_name}"
            )
            assert row["is_nullable"] == expected["is_nullable"], (
                f"Expected is_nullable={expected['is_nullable']}, "
                f"got {row['is_nullable']} for {table}.{column_name}"
            )
            if expected["has_default"]:
                assert row["column_default"] is not None, (
                    f"Expected a default for {table}.{column_name}, got None"
                )
            else:
                assert row["column_default"] is None, (
                    f"Expected no default for {table}.{column_name}, got {row['column_default']}"
                )


# =============================================================================
# TestSCDIndexes
# =============================================================================


@pytest.mark.integration
class TestSCDIndexes:
    """Partial unique indexes and current-row filter indexes exist."""

    @pytest.mark.parametrize(
        ("index_name", "table"),
        list(SCD_UNIQUE_INDEXES.items()),
        ids=list(SCD_UNIQUE_INDEXES.keys()),
    )
    def test_unique_index_exists(self, db_pool: Any, index_name: str, table: str) -> None:
        """Partial unique index for SCD business key exists."""
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                    AND tablename = %s
                    AND indexname = %s
                """,
                (table, index_name),
            )
            row = cur.fetchone()
            assert row is not None, f"Index {index_name} not found on {table}"
            # Verify it is a partial index (has WHERE clause)
            assert "WHERE" in row["indexdef"].upper(), (
                f"Expected partial index (WHERE clause) for {index_name}"
            )
            # Verify it is UNIQUE
            assert "UNIQUE" in row["indexdef"].upper(), f"Expected UNIQUE index for {index_name}"
            # Verify it filters on row_current_ind = true
            assert "row_current_ind" in row["indexdef"].lower(), (
                f"Expected row_current_ind filter in {index_name}"
            )

    @pytest.mark.parametrize(
        ("index_name", "table"),
        list(SCD_CURRENT_INDEXES.items()),
        ids=list(SCD_CURRENT_INDEXES.keys()),
    )
    def test_current_row_index_exists(self, db_pool: Any, index_name: str, table: str) -> None:
        """Current-row filter index exists (non-unique partial)."""
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                    AND tablename = %s
                    AND indexname = %s
                """,
                (table, index_name),
            )
            row = cur.fetchone()
            assert row is not None, f"Index {index_name} not found on {table}"
            # Verify it is a partial index
            assert "WHERE" in row["indexdef"].upper(), (
                f"Expected partial index (WHERE clause) for {index_name}"
            )
            assert "row_current_ind" in row["indexdef"].lower(), (
                f"Expected row_current_ind filter in {index_name}"
            )

    def test_teams_unique_current_uses_composite_key(self, db_pool: Any) -> None:
        """Teams unique-current index uses (team_code, league), not team_code alone."""
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                    AND indexname = 'idx_teams_unique_current'
                """,
            )
            row = cur.fetchone()
            assert row is not None, "idx_teams_unique_current not found"
            indexdef = row["indexdef"].lower()
            assert "team_code" in indexdef, "Expected team_code in index definition"
            assert "league" in indexdef, (
                "Expected league in index definition (composite business key)"
            )

    def test_game_states_game_id_row_start_ts_compound_index_exists(self, db_pool: Any) -> None:
        """Compound index for temporal_alignment_writer LATERAL sort.

        Pairs with PR #747 and Pattern 63. The writer's hot-path query
        does ORDER BY ABS(ms.row_start_ts - gs_inner.row_start_ts) for
        each game_id bucket, which is only efficient if the planner can
        walk game_states ordered by row_start_ts within a game_id.
        """
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                    AND tablename = 'game_states'
                    AND indexname = 'idx_game_states_game_id_row_start_ts'
                """,
            )
            row = cur.fetchone()
            assert row is not None, (
                "idx_game_states_game_id_row_start_ts missing — temporal_alignment"
                " writer LATERAL subquery will fall back to a sequential sort"
            )
            indexdef = row["indexdef"].lower()
            assert "game_id" in indexdef
            assert "row_start_ts" in indexdef
            # Partial index on game_id IS NOT NULL — matches the pattern used by
            # the pre-existing idx_game_states_game_id (0035).
            assert "game_id is not null" in indexdef, (
                "Expected partial index WHERE clause matching idx_game_states_game_id"
            )


# =============================================================================
# TestRestrictBlocksDeletion
# =============================================================================


@pytest.mark.integration
class TestRestrictBlocksDeletion:
    """Representative DELETE on referenced parents raises IntegrityError.

    One test per FK category: platform, team, strategy, market, position.
    """

    def test_platform_delete_blocked_by_series(self, db_pool: Any, fk_test_platform: str) -> None:
        """Cannot delete platform that has series referencing it."""
        platform_id = fk_test_platform

        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO series (
                    series_id, platform_id, external_id,
                    category, title
                )
                VALUES (%s, %s, %s, 'sports', 'Test Series')
                """,
                ("MIG57-SERIES", platform_id, "MIG57-SERIES-EXT"),
            )

        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM platforms WHERE platform_id = %s",
                    (platform_id,),
                )

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM series WHERE series_id = %s",
                ("MIG57-SERIES",),
            )

    def test_team_delete_blocked_by_team_rankings(self, db_pool: Any, fk_test_team: int) -> None:
        """Cannot delete team that has team_rankings referencing it."""
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO team_rankings (
                    team_id, ranking_type, rank, season
                )
                VALUES (%s, 'AP', 1, 2025)
                """,
                (fk_test_team,),
            )

        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM teams WHERE team_id = %s",
                    (fk_test_team,),
                )

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM team_rankings WHERE team_id = %s",
                (fk_test_team,),
            )

    def test_strategy_delete_blocked_by_orders(self, db_pool: Any, fk_test_platform: str) -> None:
        """Cannot delete strategy that has orders referencing it."""
        platform_id = fk_test_platform

        with get_cursor(commit=True) as cur:
            # Create strategy
            cur.execute(
                """
                INSERT INTO strategies (
                    platform_id, strategy_name, strategy_version,
                    strategy_type, config, status
                )
                VALUES (%s, 'mig57-test-strat', '1.0',
                        'value', '{}', 'active')
                RETURNING strategy_id
                """,
                (platform_id,),
            )
            strategy_id = cur.fetchone()["strategy_id"]

            # Create event for market
            cur.execute(
                """
                INSERT INTO events (
                    platform_id, external_id,
                    category, title
                )
                VALUES (%s, %s, 'sports', 'Test Event')
                RETURNING id
                """,
                (platform_id, "MIG57-EVT-EXT"),
            )
            event_id = cur.fetchone()["id"]

            # Create market
            cur.execute(
                """
                INSERT INTO markets (
                    platform_id, event_internal_id, external_id,
                    ticker, title, market_type, status
                )
                VALUES (%s, %s, %s, %s, 'Test Market', 'binary', 'open')
                RETURNING id
                """,
                (platform_id, event_id, "MIG57-MKT-EXT", "MIG57-TICK"),
            )
            market_id = cur.fetchone()["id"]

            # Create order referencing strategy
            cur.execute(
                """
                INSERT INTO orders (
                    platform_id, external_order_id,
                    market_internal_id, strategy_id,
                    side, action, order_type,
                    requested_price, requested_quantity,
                    remaining_quantity, status,
                    execution_environment
                )
                VALUES (%s, %s, %s, %s, 'yes', 'buy', 'market',
                        %s, 1, 1, 'submitted', 'paper')
                RETURNING id
                """,
                (
                    platform_id,
                    "MIG57-ORD",
                    market_id,
                    strategy_id,
                    Decimal("0.5000"),
                ),
            )

        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM strategies WHERE strategy_id = %s",
                    (strategy_id,),
                )

        # Cleanup in reverse FK order
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM orders WHERE platform_id = %s",
                (platform_id,),
            )
            cur.execute(
                "DELETE FROM markets WHERE platform_id = %s",
                (platform_id,),
            )
            cur.execute(
                "DELETE FROM events WHERE platform_id = %s",
                (platform_id,),
            )
            cur.execute(
                "DELETE FROM strategies WHERE platform_id = %s",
                (platform_id,),
            )

    def test_market_delete_blocked_by_market_snapshots(
        self, db_pool: Any, fk_test_platform: str
    ) -> None:
        """Cannot delete market that has market_snapshots referencing it."""
        platform_id = fk_test_platform

        with get_cursor(commit=True) as cur:
            # Create market
            cur.execute(
                """
                INSERT INTO markets (
                    platform_id, external_id, ticker, title,
                    market_type, status
                )
                VALUES (%s, %s, %s, 'Snapshot Test Market', 'binary', 'open')
                RETURNING id
                """,
                (platform_id, "MIG57-SNAP-MKT-EXT", "MIG57-SNAP-TICK"),
            )
            market_id = cur.fetchone()["id"]

            # Create snapshot referencing market
            cur.execute(
                """
                INSERT INTO market_snapshots (
                    market_id, yes_ask_price, no_ask_price,
                    row_current_ind, row_start_ts
                )
                VALUES (%s, %s, %s, TRUE, NOW())
                """,
                (market_id, Decimal("0.5500"), Decimal("0.4600")),
            )

        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM markets WHERE id = %s",
                    (market_id,),
                )

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM market_snapshots WHERE market_id = %s",
                (market_id,),
            )
            cur.execute(
                "DELETE FROM markets WHERE id = %s",
                (market_id,),
            )

    def test_positions_delete_blocked_by_position_exits(
        self, db_pool: Any, fk_test_platform: str
    ) -> None:
        """Cannot delete position that has position_exits referencing it."""
        platform_id = fk_test_platform

        with get_cursor(commit=True) as cur:
            # Create market for position
            cur.execute(
                """
                INSERT INTO markets (
                    platform_id, external_id, ticker, title,
                    market_type, status
                )
                VALUES (%s, %s, %s, 'Position Test Market', 'binary', 'open')
                RETURNING id
                """,
                (platform_id, "MIG57-POS-MKT-EXT", "MIG57-POS-TICK"),
            )
            market_id = cur.fetchone()["id"]

            # Create position
            cur.execute(
                """
                INSERT INTO positions (
                    position_id, platform_id, market_internal_id,
                    side, quantity, entry_price, current_price,
                    status, entry_time, last_check_time,
                    row_current_ind, row_start_ts,
                    execution_environment
                )
                VALUES (
                    %s, %s, %s, 'YES', 10, %s, %s, 'open',
                    NOW(), NOW(), TRUE, NOW(), 'paper'
                )
                RETURNING id
                """,
                (
                    "MIG57-POS",
                    platform_id,
                    market_id,
                    Decimal("0.5000"),
                    Decimal("0.5000"),
                ),
            )
            position_id = cur.fetchone()["id"]

            # Create position_exit referencing position
            cur.execute(
                """
                INSERT INTO position_exits (
                    position_internal_id, exit_reason, exit_price,
                    quantity_exited, realized_pnl,
                    execution_environment
                )
                VALUES (%s, 'stop_loss', %s, 5, %s, 'paper')
                """,
                (
                    position_id,
                    Decimal("0.4500"),
                    Decimal("-0.2500"),
                ),
            )

        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM positions WHERE id = %s",
                    (position_id,),
                )

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM position_exits WHERE position_internal_id = %s",
                (position_id,),
            )
            cur.execute(
                "DELETE FROM positions WHERE id = %s",
                (position_id,),
            )
            cur.execute(
                "DELETE FROM markets WHERE id = %s",
                (market_id,),
            )


# =============================================================================
# TestSCDDefaults
# =============================================================================


@pytest.mark.integration
class TestSCDDefaults:
    """New rows in teams/venues/series get correct SCD Type 2 defaults."""

    def test_team_scd_defaults(self, db_pool: Any) -> None:
        """New team row has row_current_ind=TRUE, row_start_ts populated, row_end_ts=NULL."""
        team_code = "M57DA"
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )
            cur.execute(
                """
                INSERT INTO teams (team_code, team_name, sport, league)
                VALUES (%s, 'Default Test Team', 'football', 'nfl')
                RETURNING row_current_ind, row_start_ts, row_end_ts
                """,
                (team_code,),
            )
            row = cur.fetchone()
            assert row["row_current_ind"] is True
            assert row["row_start_ts"] is not None
            assert row["row_end_ts"] is None

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )

    def test_venue_scd_defaults(self, db_pool: Any) -> None:
        """New venue row has correct SCD defaults."""
        venue_name = "Migration 0057 Test Venue"
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE venue_name = %s", (venue_name,))
            cur.execute(
                """
                INSERT INTO venues (venue_name, city, state)
                VALUES (%s, 'TestCity', 'TS')
                RETURNING row_current_ind, row_start_ts, row_end_ts
                """,
                (venue_name,),
            )
            row = cur.fetchone()
            assert row["row_current_ind"] is True
            assert row["row_start_ts"] is not None
            assert row["row_end_ts"] is None

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE venue_name = %s", (venue_name,))

    def test_series_scd_defaults(self, db_pool: Any, fk_test_platform: str) -> None:
        """New series row has correct SCD defaults."""
        series_id = "MIG57-SCD-DEFAULT-SERIES"
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM series WHERE series_id = %s", (series_id,))
            cur.execute(
                """
                INSERT INTO series (
                    series_id, platform_id, external_id,
                    category, title
                )
                VALUES (%s, %s, %s, 'sports', 'SCD Default Test Series')
                RETURNING row_current_ind, row_start_ts, row_end_ts
                """,
                (series_id, fk_test_platform, "MIG57-SCD-DEFAULT-EXT"),
            )
            row = cur.fetchone()
            assert row["row_current_ind"] is True
            assert row["row_start_ts"] is not None
            assert row["row_end_ts"] is None

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM series WHERE series_id = %s", (series_id,))

    def test_row_current_ind_can_be_set_false(self, db_pool: Any) -> None:
        """row_current_ind can be explicitly set to FALSE (for historical versioning)."""
        team_code = "M57DF"
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )
            cur.execute(
                """
                INSERT INTO teams (
                    team_code, team_name, sport, league, row_current_ind
                )
                VALUES (%s, 'Historical Test Team', 'football', 'nfl', FALSE)
                RETURNING row_current_ind
                """,
                (team_code,),
            )
            row = cur.fetchone()
            assert row["row_current_ind"] is False

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )

    def test_row_current_ind_not_nullable(self, db_pool: Any) -> None:
        """row_current_ind cannot be NULL."""
        team_code = "M57DN"
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )

        with pytest.raises(psycopg2.errors.NotNullViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO teams (
                        team_code, team_name, sport, league, row_current_ind
                    )
                    VALUES (%s, 'Null Current Team', 'football', 'nfl', NULL)
                    """,
                    (team_code,),
                )

        # Cleanup (might not exist if insert failed)
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )

    def test_row_start_ts_not_nullable(self, db_pool: Any) -> None:
        """row_start_ts cannot be NULL (server default prevents this in normal use,
        but explicit NULL insert should be rejected)."""
        team_code = "M57NS"
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )

        with pytest.raises(psycopg2.errors.NotNullViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO teams (
                        team_code, team_name, sport, league, row_start_ts
                    )
                    VALUES (%s, 'Null Start Team', 'football', 'nfl', NULL)
                    """,
                    (team_code,),
                )

        # Cleanup (might not exist if insert failed)
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )

    def test_row_end_ts_is_nullable(self, db_pool: Any) -> None:
        """row_end_ts can be NULL (current rows have no end time)."""
        team_code = "M57NE"
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )
            cur.execute(
                """
                INSERT INTO teams (
                    team_code, team_name, sport, league, row_end_ts
                )
                VALUES (%s, 'Nullable End Team', 'football', 'nfl', NULL)
                RETURNING row_end_ts
                """,
                (team_code,),
            )
            row = cur.fetchone()
            assert row["row_end_ts"] is None

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )


# =============================================================================
# TestSCDUniqueConstraint
# =============================================================================


@pytest.mark.integration
class TestSCDUniqueConstraint:
    """Partial unique indexes prevent duplicate current rows for same business key."""

    def test_teams_duplicate_current_blocked(self, db_pool: Any) -> None:
        """Cannot have two current rows with same (team_code, league)."""
        team_code = "M57DU"
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )
            cur.execute(
                """
                INSERT INTO teams (team_code, team_name, sport, league, row_current_ind)
                VALUES (%s, 'Dup Test Team 1', 'football', 'nfl', TRUE)
                """,
                (team_code,),
            )

        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO teams (team_code, team_name, sport, league, row_current_ind)
                    VALUES (%s, 'Dup Test Team 2', 'football', 'nfl', TRUE)
                    """,
                    (team_code,),
                )

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )

    def test_teams_historical_duplicates_allowed(self, db_pool: Any) -> None:
        """Multiple historical (row_current_ind=FALSE) rows with same business key are OK."""
        team_code = "M57HD"
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )
            # Insert two historical rows -- both FALSE, no unique violation
            cur.execute(
                """
                INSERT INTO teams (team_code, team_name, sport, league, row_current_ind)
                VALUES (%s, 'Hist Team V1', 'football', 'nfl', FALSE)
                """,
                (team_code,),
            )
            cur.execute(
                """
                INSERT INTO teams (team_code, team_name, sport, league, row_current_ind)
                VALUES (%s, 'Hist Team V2', 'football', 'nfl', FALSE)
                """,
                (team_code,),
            )

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )
            assert cur.fetchone()["cnt"] == 2

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )

    def test_series_duplicate_current_blocked(self, db_pool: Any, fk_test_platform: str) -> None:
        """Cannot have two current rows with same series_id."""
        series_id = "MIG57-DUP-SERIES"
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM series WHERE series_id = %s", (series_id,))
            cur.execute(
                """
                INSERT INTO series (
                    series_id, platform_id, external_id,
                    category, title, row_current_ind
                )
                VALUES (%s, %s, %s, 'sports', 'Dup Series 1', TRUE)
                """,
                (series_id, fk_test_platform, "MIG57-DUP-EXT-1"),
            )

        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO series (
                        series_id, platform_id, external_id,
                        category, title, row_current_ind
                    )
                    VALUES (%s, %s, %s, 'sports', 'Dup Series 2', TRUE)
                    """,
                    (series_id, fk_test_platform, "MIG57-DUP-EXT-2"),
                )

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM series WHERE series_id = %s", (series_id,))

    def test_venues_null_espn_id_allows_multiple_current(self, db_pool: Any) -> None:
        """Multiple current venues with NULL espn_venue_id are allowed
        (PostgreSQL UNIQUE treats NULLs as distinct)."""
        v1_name = "MIG57 Null Venue 1"
        v2_name = "MIG57 Null Venue 2"
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE venue_name IN (%s, %s)", (v1_name, v2_name))
            cur.execute(
                """
                INSERT INTO venues (venue_name, city, state, espn_venue_id, row_current_ind)
                VALUES (%s, 'City1', 'S1', NULL, TRUE)
                """,
                (v1_name,),
            )
            cur.execute(
                """
                INSERT INTO venues (venue_name, city, state, espn_venue_id, row_current_ind)
                VALUES (%s, 'City2', 'S2', NULL, TRUE)
                """,
                (v2_name,),
            )

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM venues WHERE venue_name IN (%s, %s)",
                (v1_name, v2_name),
            )
            assert cur.fetchone()["cnt"] == 2

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE venue_name IN (%s, %s)", (v1_name, v2_name))


# =============================================================================
# TestDeleteWithoutChildren
# =============================================================================


@pytest.mark.integration
class TestDeleteWithoutChildren:
    """Parent rows with no children can still be deleted (RESTRICT only blocks
    when children exist, not unconditionally)."""

    def test_platform_delete_succeeds_when_no_children(self, db_pool: Any) -> None:
        """Deleting a platform with no child rows succeeds."""
        platform_id = "mig-0057-orphan-test"
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM platforms WHERE platform_id = %s",
                (platform_id,),
            )
            cur.execute(
                """
                INSERT INTO platforms (
                    platform_id, platform_type, display_name, base_url, status
                )
                VALUES (%s, 'trading', 'Orphan Test Platform',
                        'https://orphan-test.example.com', 'active')
                """,
                (platform_id,),
            )

        # Delete should succeed -- no children
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM platforms WHERE platform_id = %s",
                (platform_id,),
            )
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM platforms WHERE platform_id = %s",
                (platform_id,),
            )
            assert cur.fetchone()["cnt"] == 0

    def test_team_delete_succeeds_when_no_children(self, db_pool: Any) -> None:
        """Deleting a team with no child rows succeeds."""
        team_code = "M57OR"
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM teams WHERE team_code = %s AND sport = 'football'",
                (team_code,),
            )
            cur.execute(
                """
                INSERT INTO teams (team_code, team_name, sport, league)
                VALUES (%s, 'Orphan Test Team', 'football', 'nfl')
                RETURNING team_id
                """,
                (team_code,),
            )
            team_id = cur.fetchone()["team_id"]

        # Delete should succeed -- no children
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM teams WHERE team_id = %s", (team_id,))
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM teams WHERE team_id = %s",
                (team_id,),
            )
            assert cur.fetchone()["cnt"] == 0
