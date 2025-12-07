"""
Database package for Precog trading system.
Uses raw SQL queries with psycopg2 for PostgreSQL interaction.

Environment Safety (Issue #161):
    This module exports environment safety functions for preventing
    accidental operations against production databases:
    - get_environment(): Detect current environment
    - require_environment(): Enforce specific environment
    - protect_dangerous_operation(): Guard DROP/TRUNCATE/DELETE

    See: docs/guides/DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
"""

from .connection import (
    execute_query,
    fetch_all,
    fetch_one,
    get_connection,
    get_cursor,
    get_environment,
    protect_dangerous_operation,
    require_environment,
)
from .crud_operations import (
    close_position,
    # Account balance operations
    create_account_balance,
    # Game state operations (ESPN, SCD Type 2)
    create_game_state,
    # Market operations
    create_market,
    # Position operations
    create_position,
    create_settlement,
    create_strategy,
    # Team ranking operations (ESPN)
    create_team_ranking,
    # Trade operations
    create_trade,
    # Venue operations (ESPN)
    create_venue,
    get_current_game_state,
    get_current_market,
    get_current_positions,
    get_current_rankings,
    get_game_state_history,
    get_games_by_date,
    get_live_games,
    get_market_history,
    get_recent_trades,
    get_strategy_by_name_and_version,
    get_team_rankings,
    get_trades_by_market,
    get_venue_by_espn_id,
    get_venue_by_id,
    update_account_balance_with_versioning,
    update_market_with_versioning,
    update_position_price,
    upsert_game_state,
)

__all__ = [
    "close_position",
    # Account balance CRUD
    "create_account_balance",
    # Game state CRUD (ESPN, SCD Type 2)
    "create_game_state",
    # Market CRUD
    "create_market",
    # Position CRUD
    "create_position",
    "create_settlement",
    "create_strategy",
    # Team ranking CRUD (ESPN)
    "create_team_ranking",
    # Trade CRUD
    "create_trade",
    # Venue CRUD (ESPN)
    "create_venue",
    "execute_query",
    "fetch_all",
    "fetch_one",
    # Connection utilities
    "get_connection",
    "get_current_game_state",
    "get_current_market",
    "get_current_positions",
    "get_current_rankings",
    "get_cursor",
    # Environment safety (Issue #161)
    "get_environment",
    "get_game_state_history",
    "get_games_by_date",
    "get_live_games",
    "get_market_history",
    "get_recent_trades",
    "get_strategy_by_name_and_version",
    "get_team_rankings",
    "get_trades_by_market",
    "get_venue_by_espn_id",
    "get_venue_by_id",
    "protect_dangerous_operation",
    "require_environment",
    "update_account_balance_with_versioning",
    "update_market_with_versioning",
    "update_position_price",
    "upsert_game_state",
]
