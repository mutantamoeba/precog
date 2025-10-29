"""
Database package for Precog trading system.
Uses raw SQL queries with psycopg2 for PostgreSQL interaction.
"""

from .connection import get_connection, get_cursor, execute_query, fetch_one, fetch_all
from .crud_operations import (
    # Market operations
    create_market,
    get_current_market,
    update_market_with_versioning,
    get_market_history,

    # Position operations
    create_position,
    get_current_positions,
    update_position_price,
    close_position,

    # Trade operations
    create_trade,
    get_trades_by_market,
    get_recent_trades,
)

__all__ = [
    # Connection utilities
    'get_connection',
    'get_cursor',
    'execute_query',
    'fetch_one',
    'fetch_all',

    # Market CRUD
    'create_market',
    'get_current_market',
    'update_market_with_versioning',
    'get_market_history',

    # Position CRUD
    'create_position',
    'get_current_positions',
    'update_position_price',
    'close_position',

    # Trade CRUD
    'create_trade',
    'get_trades_by_market',
    'get_recent_trades',
]
