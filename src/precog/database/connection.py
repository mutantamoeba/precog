"""
Database connection management with connection pooling.

Connection Pooling Explained:
-----------------------------
Imagine a parking lot with 10 spots. Instead of building a new car (connection)
every time you want to drive (query), you borrow a car from the lot and return
it when done. This is MUCH faster than creating a new TCP connection to PostgreSQL
for every query.

Why This Matters:
- Creating a new connection: ~50-100ms overhead (TCP handshake, auth, session setup)
- Reusing pooled connection: <1ms overhead (just borrow from pool)
- For 1000 queries: 50 seconds wasted vs 1 second (50x faster!)

Thread Safety:
- psycopg2.pool.SimpleConnectionPool is thread-safe
- Multiple threads can call get_connection() simultaneously
- Pool ensures no two threads get the same connection object
- Lock-based implementation prevents race conditions

Performance Metrics:
- Min connections (minconn=2): Always 2 connections ready (warm pool)
- Max connections (maxconn=25): Pool grows up to 25 under heavy load
- Configurable via DB_POOL_MIN_CONN / DB_POOL_MAX_CONN env vars
- Idle behavior: Connections returned to pool immediately after use
- Connection lifetime: Reused indefinitely (until close_pool() called)

Architecture Pattern:
This module uses the **Singleton Pattern** for the connection pool.
Only ONE pool exists globally (_connection_pool), shared across all modules.
This prevents connection leaks and simplifies resource management.

Security Note:
- Credentials ALWAYS loaded from environment variables (.env file)
- NEVER hardcode passwords in this module
- See: docs/utility/SECURITY_REVIEW_CHECKLIST.md

Reference: docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
Related Requirements: REQ-DB-002 (Connection Pooling)
Related ADR: ADR-008 (PostgreSQL Connection Strategy)
"""

import os
from contextlib import contextmanager
from typing import cast

import psycopg2
from dotenv import load_dotenv
from psycopg2 import extras, pool

from precog.utils.logger import get_logger

logger = get_logger(__name__)

# Load environment variables from .env file
load_dotenv()

# Connection pool (global singleton)
_connection_pool: pool.SimpleConnectionPool | None = None

# Valid environments
VALID_ENVIRONMENTS = ("dev", "test", "staging", "prod")


def get_environment() -> str:
    """
    Determine current database environment.

    Priority:
    1. PRECOG_ENV environment variable (explicit)
    2. DB_NAME environment variable (inferred from name)
    3. Default to 'dev' (safe default)

    Returns:
        Environment name: 'dev', 'test', 'staging', or 'prod'

    Example:
        >>> os.environ["PRECOG_ENV"] = "test"
        >>> get_environment()
        'test'

    Educational Note:
        Environment detection ensures you don't accidentally run
        destructive operations against production. Always verify
        the environment before running migrations or bulk deletes.
    """
    # Explicit environment selection (highest priority)
    env = os.getenv("PRECOG_ENV")
    if env:
        if env not in VALID_ENVIRONMENTS:
            msg = f"Invalid PRECOG_ENV: {env}. Must be one of {VALID_ENVIRONMENTS}"
            raise ValueError(msg)
        return env

    # Infer from database name
    db_name = os.getenv("DB_NAME", "precog_dev")
    if "test" in db_name:
        return "test"
    if "staging" in db_name:
        return "staging"
    if "prod" in db_name:
        return "prod"
    return "dev"


def require_environment(required: str) -> None:
    """
    Ensure we're running in the expected environment.

    Use at the start of scripts that should only run in specific environments.

    Args:
        required: Expected environment ('dev', 'test', 'staging', 'prod')

    Raises:
        RuntimeError: If current environment doesn't match required

    Example:
        >>> require_environment("dev")  # Passes in dev
        >>> require_environment("prod")  # Raises if not prod

    Educational Note:
        This is a "safety guard" pattern. By failing fast when in the
        wrong environment, we prevent accidental data corruption or
        production outages from running dev scripts against prod.
    """
    if required not in VALID_ENVIRONMENTS:
        msg = f"Invalid required environment: {required}. Must be one of {VALID_ENVIRONMENTS}"
        raise ValueError(msg)

    current = get_environment()
    if current != required:
        msg = (
            f"This operation requires {required} environment, but current environment is {current}"
        )
        raise RuntimeError(msg)


def initialize_pool(
    minconn: int | None = None,
    maxconn: int | None = None,
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
):
    """
    Initialize PostgreSQL connection pool.

    Args:
        minconn: Minimum connections (defaults to DB_POOL_MIN_CONN env or 2)
        maxconn: Maximum connections (defaults to DB_POOL_MAX_CONN env or 25)
        host: Database host (defaults to .env DB_HOST)
        port: Database port (defaults to .env DB_PORT)
        database: Database name (defaults to .env DB_NAME)
        user: Database user (defaults to .env DB_USER)
        password: Database password (defaults to .env DB_PASSWORD)

    Returns:
        Connection pool instance

    Educational Note:
        Pool sizing guidelines:
        - minconn=2: Keeps 2 connections warm (avoids cold start latency)
        - maxconn=25: Handles concurrent operations (trading + monitoring + data fetch)
        - PostgreSQL overhead: ~5-10MB RAM per connection
        - Increase maxconn for heavy parallelism (50+ concurrent operations)

    Example:
        >>> initialize_pool()  # Uses env defaults
        >>> initialize_pool(maxconn=50)  # High-concurrency production
        >>> conn = get_connection()
    """
    global _connection_pool

    if _connection_pool is not None:
        logger.warning("Connection pool already initialized")
        return _connection_pool

    # Use environment variables if parameters not provided
    # Pool size configurable via env for different environments
    minconn = minconn if minconn is not None else int(os.getenv("DB_POOL_MIN_CONN", "2"))
    maxconn = maxconn if maxconn is not None else int(os.getenv("DB_POOL_MAX_CONN", "25"))
    host = host or os.getenv("DB_HOST", "localhost")
    port = port or int(os.getenv("DB_PORT", "5432"))
    database = database or os.getenv("DB_NAME", "precog_dev")
    user = user or os.getenv("DB_USER", "postgres")
    password = password or os.getenv("DB_PASSWORD")

    if not password:
        msg = "Database password not found in environment variables"
        raise ValueError(msg)

    try:
        _connection_pool = pool.SimpleConnectionPool(
            minconn, maxconn, host=host, port=port, database=database, user=user, password=password
        )
        logger.info(f"Database connection pool initialized ({minconn}-{maxconn} connections)")
        logger.info(f"Connected to: {user}@{host}:{port}/{database}")
        return _connection_pool

    except psycopg2.Error as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise


def get_connection():
    """
    Get a connection from the pool.

    IMPORTANT: Must call putconn() when done, or use get_cursor() context manager.

    Returns:
        Database connection from pool

    Example:
        >>> conn = get_connection()
        >>> cursor = conn.cursor()
        >>> cursor.execute("SELECT 1")
        >>> _connection_pool.putconn(conn)  # Return to pool!
    """
    global _connection_pool

    if _connection_pool is None:
        initialize_pool()

    assert _connection_pool is not None, "Connection pool initialization failed"
    return _connection_pool.getconn()


def release_connection(conn):
    """
    Return connection to pool.

    Args:
        conn: Connection to return to pool

    Example:
        >>> conn = get_connection()
        >>> # ... use connection ...
        >>> release_connection(conn)
    """
    global _connection_pool

    if _connection_pool is not None:
        _connection_pool.putconn(conn)


@contextmanager
def get_cursor(commit: bool = False):
    """
    Context manager for database cursor with automatic cleanup.

    This is the RECOMMENDED way to interact with the database.
    Automatically handles connection pooling and cleanup.

    Args:
        commit: Whether to commit transaction on success (default: False)

    Yields:
        Database cursor (RealDictCursor - returns rows as dictionaries)

    Example (Read-only query):
        >>> with get_cursor() as cur:
        >>>     cur.execute("SELECT * FROM markets WHERE ticker = %s", ("NFL-KC-YES",))
        >>>     market = cur.fetchone()
        >>>     print(market['yes_price'])  # Dict access!
        # Connection automatically returned to pool

    Example (Write query with commit):
        >>> with get_cursor(commit=True) as cur:
        >>>     cur.execute(
        >>>         "INSERT INTO markets (ticker, yes_price) VALUES (%s, %s)",
        >>>         ("NFL-KC-YES", Decimal("0.5200"))
        >>>     )
        # Transaction committed, connection returned to pool

    Educational Notes:
        Context Manager Pattern:
        - Ensures cleanup happens even if exception occurs
        - No need to manually call cursor.close() or release_connection()
        - Python's `with` statement guarantees cleanup (like try/finally)

        RealDictCursor:
        - Returns rows as dictionaries instead of tuples
        - Access columns by name: row['ticker'] vs row[0]
        - Much more readable and less error-prone

        Commit Behavior:
        - commit=False (default): SELECT queries, no changes saved
        - commit=True: INSERT/UPDATE/DELETE queries, changes saved
        - On exception: Automatic rollback (changes discarded)

        Thread Safety:
        - Each call gets a different connection from the pool
        - Safe to use from multiple threads simultaneously
        - Connections never shared between threads

    Performance Note:
        This is slower than reusing a connection across multiple queries
        (pool overhead ~1ms per call). For bulk operations with 1000+ queries,
        consider using get_connection() directly and reusing the same connection.
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        release_connection(conn)


def execute_query(query: str, params: tuple | None = None, commit: bool = True) -> int:
    """
    Execute a query that doesn't return results (INSERT, UPDATE, DELETE).

    Args:
        query: SQL query with %s placeholders
        params: Parameters to substitute (prevents SQL injection)
        commit: Whether to commit transaction (default: True)

    Returns:
        Number of rows affected

    Example:
        >>> execute_query(
        ...     "INSERT INTO markets (ticker, yes_price) VALUES (%s, %s)",
        ...     ("NFL-KC-YES", Decimal("0.5200")),
        ...     commit=True
        ... )
        1
    """
    with get_cursor(commit=commit) as cur:
        cur.execute(query, params)
        return cast("int", cur.rowcount)


def fetch_one(query: str, params: tuple | None = None) -> dict | None:
    """
    Fetch single row from database.

    Args:
        query: SQL query with %s placeholders
        params: Parameters to substitute

    Returns:
        Dictionary of column:value pairs, or None if no rows

    Example:
        >>> market = fetch_one(
        ...     "SELECT * FROM markets WHERE ticker = %s AND row_current_ind = TRUE",
        ...     ("NFL-KC-YES",)
        ... )
        >>> print(market['yes_price'])  # Decimal('0.5200')
    """
    with get_cursor() as cur:
        cur.execute(query, params)
        return cast("dict | None", cur.fetchone())


def fetch_all(query: str, params: tuple | None = None) -> list[dict]:
    """
    Fetch all rows from database.

    Args:
        query: SQL query with %s placeholders
        params: Parameters to substitute

    Returns:
        List of dictionaries (column:value pairs)

    Example:
        >>> markets = fetch_all(
        ...     "SELECT * FROM markets WHERE status = %s AND row_current_ind = TRUE",
        ...     ("open",)
        ... )
        >>> for market in markets:
        ...     print(market['ticker'], market['yes_price'])
    """
    with get_cursor() as cur:
        cur.execute(query, params)
        return cast("list[dict]", cur.fetchall())


def close_pool():
    """
    Close all connections in the pool.

    Call this when shutting down the application.

    Example:
        >>> close_pool()
        ✅ Connection pool closed
    """
    global _connection_pool

    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Connection pool closed")


def test_connection():
    """
    Test database connection.

    Returns:
        True if connection successful, False otherwise

    Example:
        >>> if test_connection():
        ...     print("Database connected!")
    """
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1 as test")
            result = cur.fetchone()
            if result and result["test"] == 1:
                logger.info("Database connection test successful")
                return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

    return False


# Initialize pool on module import
try:
    initialize_pool()
except Exception as e:
    logger.warning(f"Connection pool not initialized on import: {e}")
    logger.warning("Call initialize_pool() manually with correct credentials")
