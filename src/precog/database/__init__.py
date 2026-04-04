"""
Database package for Precog trading system.

Uses raw SQL queries with psycopg2 for PostgreSQL interaction.
CRUD operations live in domain-specific modules (crud_*.py).
Import directly from the domain module, not from this package.

Example:
    from precog.database.crud_markets import create_market
    from precog.database.crud_teams import get_team_by_espn_id
    from precog.database.connection import get_cursor

Environment Safety (Issue #161):
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

__all__ = [
    "execute_query",
    "fetch_all",
    "fetch_one",
    "get_connection",
    "get_cursor",
    "get_environment",
    "protect_dangerous_operation",
    "require_environment",
]
