"""
Database connection management with connection pooling.

Uses psycopg2 with connection pooling for efficient database access.
Loads credentials from .env file.
"""

import os
from typing import Optional, List, Tuple, Any
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool, extras
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Connection pool (global singleton)
_connection_pool: Optional[pool.SimpleConnectionPool] = None


def initialize_pool(
    minconn: int = 2,
    maxconn: int = 10,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None
):
    """
    Initialize PostgreSQL connection pool.

    Args:
        minconn: Minimum number of connections in pool
        maxconn: Maximum number of connections in pool
        host: Database host (defaults to .env DB_HOST)
        port: Database port (defaults to .env DB_PORT)
        database: Database name (defaults to .env DB_NAME)
        user: Database user (defaults to .env DB_USER)
        password: Database password (defaults to .env DB_PASSWORD)

    Returns:
        Connection pool instance

    Example:
        >>> initialize_pool()
        >>> conn = get_connection()
    """
    global _connection_pool

    if _connection_pool is not None:
        print("WARNING: Connection pool already initialized")
        return _connection_pool

    # Use environment variables if parameters not provided
    host = host or os.getenv('DB_HOST', 'localhost')
    port = port or int(os.getenv('DB_PORT', '5432'))
    database = database or os.getenv('DB_NAME', 'precog_dev')
    user = user or os.getenv('DB_USER', 'postgres')
    password = password or os.getenv('DB_PASSWORD')

    if not password:
        raise ValueError("Database password not found in environment variables")

    try:
        _connection_pool = pool.SimpleConnectionPool(
            minconn,
            maxconn,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        print(f"[OK] Database connection pool initialized ({minconn}-{maxconn} connections)")
        print(f"     Connected to: {user}@{host}:{port}/{database}")
        return _connection_pool

    except psycopg2.Error as e:
        print(f"[ERROR] Failed to initialize connection pool: {e}")
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
        Database cursor

    Example:
        >>> with get_cursor(commit=True) as cur:
        >>>     cur.execute("INSERT INTO markets (...) VALUES (%s, %s)", (val1, val2))
        # Connection automatically returned to pool
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


def execute_query(
    query: str,
    params: Optional[Tuple] = None,
    commit: bool = True
) -> int:
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
        return cur.rowcount


def fetch_one(query: str, params: Optional[Tuple] = None) -> Optional[dict]:
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
        return cur.fetchone()


def fetch_all(query: str, params: Optional[Tuple] = None) -> List[dict]:
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
        return cur.fetchall()


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
        print("[OK] Connection pool closed")


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
            if result and result['test'] == 1:
                print("[OK] Database connection test successful")
                return True
    except Exception as e:
        print(f"[ERROR] Database connection test failed: {e}")
        return False

    return False


# Initialize pool on module import
try:
    initialize_pool()
except Exception as e:
    print(f"[WARNING] Connection pool not initialized on import: {e}")
    print("          Call initialize_pool() manually with correct credentials")
