"""
Database package for Precog trading system.
Uses raw SQL queries with psycopg2 for PostgreSQL interaction.
"""

from .connection import execute_query, fetch_all, fetch_one, get_connection, get_cursor
from .crud_operations import (
    close_position,
    # Account balance operations
    create_account_balance,
    # Market operations
    create_market,
    # Position operations
    create_position,
    create_settlement,
    create_strategy,
    # Trade operations
    create_trade,
    get_current_market,
    get_current_positions,
    get_market_history,
    get_recent_trades,
    get_strategy_by_name_and_version,
    get_trades_by_market,
    update_account_balance_with_versioning,
    update_market_with_versioning,
    update_position_price,
)

__all__ = [
    "close_position",
    # Account balance CRUD
    "create_account_balance",
    # Market CRUD
    "create_market",
    # Position CRUD
    "create_position",
    "create_settlement",
    "create_strategy",
    # Trade CRUD
    "create_trade",
    "execute_query",
    "fetch_all",
    "fetch_one",
    # Connection utilities
    "get_connection",
    "get_current_market",
    "get_current_positions",
    "get_cursor",
    "get_market_history",
    "get_recent_trades",
    "get_strategy_by_name_and_version",
    "get_trades_by_market",
    "update_account_balance_with_versioning",
    "update_market_with_versioning",
    "update_position_price",
]
