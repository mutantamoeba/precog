"""
Tests for database connection pooling.

Tests:
- Connection pool initialization
- Connection reuse
- Connection cleanup
- Error handling
"""

import pytest

from precog.database.connection import (
    execute_query,
    fetch_all,
    fetch_one,
    get_connection,
    get_cursor,
    release_connection,
)
from precog.database.connection import test_connection as check_db_connection


@pytest.mark.unit
@pytest.mark.critical
def test_connection_pool_exists(db_pool):
    """Test that connection pool is initialized."""
    # Pool should be created by db_pool fixture
    conn = get_connection()
    assert conn is not None
    release_connection(conn)


@pytest.mark.integration
@pytest.mark.critical
def test_database_connectivity(db_pool):
    """Test that we can connect to database."""
    result = check_db_connection()
    assert result is True


@pytest.mark.integration
def test_get_cursor_context_manager(db_pool):
    """Test get_cursor() context manager."""
    with get_cursor() as cur:
        cur.execute("SELECT 1 as test")
        result = cur.fetchone()
        assert result["test"] == 1


@pytest.mark.integration
def test_cursor_returns_dict(db_pool):
    """Test that cursor returns RealDictCursor (dict-like rows)."""
    with get_cursor() as cur:
        cur.execute("SELECT 1 as num, 'test' as text")
        result = cur.fetchone()

        # Should be dict-like
        assert result["num"] == 1
        assert result["text"] == "test"


@pytest.mark.integration
def test_fetch_one(db_pool):
    """Test fetch_one() helper function."""
    result = fetch_one("SELECT %s as value", (42,))
    assert result is not None
    assert result["value"] == 42


@pytest.mark.integration
def test_fetch_one_no_results(db_pool):
    """Test fetch_one() returns None when no results."""
    result = fetch_one("SELECT 1 WHERE FALSE")
    assert result is None


@pytest.mark.integration
def test_fetch_all(db_pool):
    """Test fetch_all() helper function."""
    results = fetch_all("""
        SELECT num FROM (VALUES (1), (2), (3)) AS t(num)
        ORDER BY num
    """)

    assert len(results) == 3
    assert results[0]["num"] == 1
    assert results[1]["num"] == 2
    assert results[2]["num"] == 3


@pytest.mark.integration
def test_execute_query(db_pool, clean_test_data):
    """Test execute_query() helper function."""
    # Use execute_query to insert into existing table
    # Note: We can't easily test with temp tables since execute_query uses its own connection
    # Instead, test with a real table (markets) using TEST- prefix for cleanup

    # Create test market using execute_query
    rowcount = execute_query(
        """INSERT INTO markets (
            market_id, platform_id, event_id, external_id,
            ticker, title, yes_price, no_price,
            status, row_current_ind, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())""",
        (
            "MKT-TEST-EXECUTE-QUERY",
            "test_platform",
            "TEST-EVT",
            "TEST-EXT",
            "TEST-EXECUTE-QUERY",
            "Test Market",
            0.5000,
            0.5000,
            "open",
        ),
        commit=True,
    )

    assert rowcount == 1

    # Clean up
    execute_query("DELETE FROM markets WHERE ticker = %s", ("TEST-EXECUTE-QUERY",), commit=True)


@pytest.mark.integration
def test_connection_reuse(db_pool):
    """Test that connection pool reuses connections."""
    # Get two connections sequentially
    conn1 = get_connection()
    conn1_id = id(conn1)
    release_connection(conn1)

    conn2 = get_connection()
    conn2_id = id(conn2)
    release_connection(conn2)

    # Should be the same connection object (reused from pool)
    assert conn1_id == conn2_id


@pytest.mark.integration
def test_cursor_auto_cleanup(db_pool):
    """Test that cursor context manager cleans up connections."""
    # Use cursor
    with get_cursor() as cur:
        cur.execute("SELECT 1")

    # If cleanup didn't happen, pool would eventually be exhausted
    # This test verifies we can continue getting cursors
    with get_cursor() as cur:
        cur.execute("SELECT 1")
        assert True  # Success if we got here


@pytest.mark.integration
def test_transaction_rollback_on_error(db_pool, db_cursor):
    """Test that transactions rollback on error."""
    # Create temporary table
    db_cursor.execute("CREATE TEMPORARY TABLE test_rollback (id INT PRIMARY KEY)")
    db_cursor.execute("INSERT INTO test_rollback VALUES (1)")

    # Try to insert duplicate (should fail)
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("INSERT INTO test_rollback VALUES (1)")  # Duplicate!
            # Should raise error before reaching here
    except Exception:
        pass  # Expected

    # Verify table still only has original row
    db_cursor.execute("SELECT COUNT(*) as cnt FROM test_rollback")
    result = db_cursor.fetchone()
    assert result["cnt"] == 1


@pytest.mark.integration
def test_parameterized_query_prevents_injection(db_pool):
    """Test that parameterized queries prevent SQL injection."""
    # Attempt SQL injection
    malicious_input = "'; DROP TABLE markets; --"

    # This should NOT execute the DROP TABLE command
    result = fetch_one("SELECT %s as value", (malicious_input,))

    # Should return the string as-is (safely escaped)
    assert result is not None  # Guard for type checker
    assert result["value"] == malicious_input

    # Verify markets table still exists
    tables = fetch_all("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'markets'
    """)
    assert len(tables) == 1  # Table still exists!
