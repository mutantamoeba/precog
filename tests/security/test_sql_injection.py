"""
Security tests for SQL injection resistance.

This test suite verifies that parameterized queries prevent SQL injection attacks
across all CRUD operations. Uses malicious input patterns from OWASP testing guide.

**TDD NOTICE**: Tests marked with @PHASE_1_5_SKIP are designed for Phase 1.5 Manager APIs
that don't exist yet (StrategyManager, PositionManager, MarketManager with simplified APIs).
When Phase 1.5 Manager APIs are complete, remove the skip decorators.

Tests that use existing crud_operations functions run against current implementation.

Related Issue: GitHub Issue #129 (Security Tests)
Related Pattern: Pattern 4 (Security - NO CREDENTIALS IN CODE)
Related Requirement: REQ-SEC-009 (SQL Injection Prevention)
"""

from decimal import Decimal

import pytest

from precog.database import crud_operations

# Import manager APIs
from precog.trading.strategy_manager import StrategyManager

# Fixtures (db_cursor, db_pool, clean_test_data) auto-discovered from tests/conftest.py


# =============================================================================
# SQL Injection Payloads (OWASP Testing Patterns)
# =============================================================================

SQL_INJECTION_PAYLOADS = [
    # Classic SQL injection
    "'; DROP TABLE strategies; --",
    "' OR '1'='1",
    "' OR '1'='1' --",
    "' OR 1=1 --",
    # Union-based injection
    "' UNION SELECT * FROM users --",
    "' UNION SELECT NULL, NULL, NULL --",
    # Time-based blind injection
    "'; WAITFOR DELAY '00:00:05' --",
    "'; SELECT pg_sleep(5) --",
    # Boolean-based blind injection
    "' AND 1=1 --",
    "' AND 1=2 --",
    # Stacked queries
    "'; DELETE FROM strategies WHERE '1'='1",
    "'; UPDATE strategies SET config = '{}'",
    # Comment injection
    "admin'--",
    "admin'/*",
    # Special characters
    "test'; SELECT * FROM strategies; --",
    "test\\'; DROP TABLE strategies; --",
]


# =============================================================================
# Test 1: Strategy CRUD Operations (Uses StrategyManager API - ENABLED)
# =============================================================================


@pytest.mark.parametrize("malicious_input", SQL_INJECTION_PAYLOADS)
def test_create_strategy_rejects_sql_injection_in_name(
    malicious_input: str,
    db_cursor,
    clean_test_data,
) -> None:
    """
    Verify strategy creation with malicious SQL in name field is safe.

    **Security Guarantee**: Parameterized queries treat input as DATA, not CODE.

    This test injects SQL payloads into the strategy_name field and verifies
    the database treats them as literal strings, not executable SQL.

    Educational Note:
        The StrategyManager uses parameterized queries via psycopg2:
        - cursor.execute("INSERT INTO strategies (name) VALUES (%s)", (malicious_name,))
        - The %s placeholder ensures the input is quoted and escaped properly
        - Even if input contains "'; DROP TABLE" it becomes a literal string

    Args:
        malicious_input: SQL injection payload from OWASP testing guide
        db_cursor: Database cursor fixture (Pattern 13)
        clean_test_data: Cleanup fixture

    Expected Result:
        - Strategy created with malicious string as LITERAL name
        - No SQL syntax errors
        - strategies table still exists and queryable
    """
    from decimal import Decimal

    manager = StrategyManager()

    # Inject malicious SQL into strategy_name - should be treated as literal string
    try:
        result = manager.create_strategy(
            strategy_name=malicious_input,
            strategy_version="v1.0",
            strategy_type="value",  # Must be valid type from strategy_types table
            config={"min_edge": Decimal("0.05")},
        )
        # If creation succeeds, verify it created a strategy with literal malicious name
        assert result is not None
        assert result.get("strategy_name") == malicious_input

    except Exception as e:
        # FK violation for invalid strategy_type is OK (not SQL injection)
        # Unique constraint violation is OK (duplicate name)
        # Only SQL syntax error indicates injection vulnerability
        error_str = str(e).lower()
        assert "syntax error" not in error_str, f"SQL injection may have occurred: {e}"

    # CRITICAL: Verify strategies table still exists (wasn't dropped)
    db_cursor.execute("SELECT COUNT(*) as count FROM strategies")
    result = db_cursor.fetchone()
    assert result is not None, "strategies table was dropped by SQL injection!"


# =============================================================================
# Test 2: Market History Query (Uses EXISTING API - ENABLED)
# =============================================================================


@pytest.mark.parametrize("malicious_input", SQL_INJECTION_PAYLOADS)
def test_get_market_history_rejects_sql_injection_in_ticker(
    malicious_input: str,
    db_cursor,
    clean_test_data,
) -> None:
    """
    Verify market history query with malicious SQL in ticker is safe.

    **Security Guarantee**: Parameterized WHERE clause prevents injection.

    This test uses the EXISTING crud_operations.get_market_history(ticker, limit) API.

    Educational Note:
        This tests the most common injection vector: WHERE clauses.

        ❌ VULNERABLE:
            query = f"SELECT * FROM markets WHERE ticker = '{malicious_input}'"
            # Attacker controls WHERE condition, can add OR '1'='1' to bypass filter

        ✅ SAFE:
            query = "SELECT * FROM markets WHERE ticker = %s"
            params = (malicious_input,)
            # WHERE condition remains intact, malicious input treated as literal string

    Args:
        malicious_input: SQL injection payload
        db_cursor: Database cursor fixture
        clean_test_data: Cleanup fixture

    Expected Result:
        - Query completes without error
        - Returns empty list (no markets match malicious ticker)
        - No SQL syntax errors
        - markets table still exists
    """
    # Query with malicious ticker - should be safely parameterized
    history = crud_operations.get_market_history(malicious_input, limit=10)

    # Verify query executed safely
    assert isinstance(history, list)
    assert len(history) == 0  # No markets with this malicious ticker

    # Verify markets table still exists - use cursor directly, not as callable
    db_cursor.execute("SELECT COUNT(*) as count FROM markets")
    result = db_cursor.fetchone()
    assert result is not None  # Table exists and is queryable


# =============================================================================
# Test 3: Position Update - SKIPPED (No text field in current API)
# =============================================================================

# NOTE: PositionManager.update_position(position_id, current_price) only updates numeric
# fields. No text injection vector exists in current API. This is actually GOOD design -
# fewer text fields = fewer injection vectors.
#
# If a future API adds notes/comments field to positions, add SQL injection test here.


# =============================================================================
# Test 4: LIMIT/OFFSET Injection (Uses EXISTING API - ENABLED)
# =============================================================================


@pytest.mark.parametrize(
    "malicious_limit",
    [
        "10; DROP TABLE strategies; --",
        "10 UNION SELECT * FROM users",
        "10 OR 1=1",
    ],
)
def test_get_market_history_rejects_sql_injection_in_limit(
    malicious_limit: str,
    db_cursor,
    clean_test_data,
) -> None:
    """
    Verify LIMIT clause injection is prevented.

    **Security Guarantee**: LIMIT/OFFSET must be integers, not strings.
    Python type system enforces this at runtime.

    Educational Note:
        LIMIT clause injection attempts:
        - LIMIT 10; DROP TABLE strategies; --
        - LIMIT 10 UNION SELECT * FROM users

        Python's type hints (limit: int) provide first line of defense.
        If attacker bypasses type hints, database driver rejects non-integer LIMIT.

    Args:
        malicious_limit: SQL injection payload targeting LIMIT clause
        db_cursor: Database cursor fixture
        clean_test_data: Cleanup fixture

    Expected Result:
        - TypeError raised (limit must be int, not str)
        - OR psycopg2.DataError raised (invalid LIMIT value)
        - strategies table still exists
    """
    # This should fail at database level - psycopg2 will convert string to parameter
    # and PostgreSQL will reject non-integer LIMIT
    from psycopg2 import errors as psycopg_errors

    with pytest.raises((TypeError, ValueError, psycopg_errors.InvalidTextRepresentation)):
        # This should fail type validation BEFORE reaching database or at DB level
        crud_operations.get_market_history("TEST-TICKER", limit=malicious_limit)  # type: ignore[arg-type]

    # Verify strategies table still exists
    db_cursor.execute("SELECT COUNT(*) as count FROM strategies")
    result = db_cursor.fetchone()
    assert result is not None  # Table exists and is queryable


# =============================================================================
# Test 5: JSON Field Injection (Uses StrategyManager API - ENABLED)
# =============================================================================


def test_create_strategy_rejects_sql_injection_in_json_config(
    db_cursor,
    clean_test_data,
) -> None:
    """
    Verify JSON config field with SQL injection payloads is safe.

    **Security Guarantee**: JSON fields are serialized, not interpolated into SQL.

    This test injects SQL payloads into config dictionary keys/values and verifies
    they are stored as literal JSON data, not executed as SQL.

    Educational Note:
        JSON fields in PostgreSQL (JSONB type) are handled differently than strings:
        - JSON is serialized to text BEFORE being passed to SQL
        - psycopg2 uses Json() adapter for proper serialization
        - Injection attempts become literal string values in the JSON document

    Expected Result:
        - Strategy created with malicious JSON stored literally
        - No SQL syntax errors
        - strategies table still exists
    """
    from decimal import Decimal

    manager = StrategyManager()

    # Inject malicious SQL into JSON config keys and values
    malicious_config = {
        "'; DROP TABLE strategies; --": Decimal("0.05"),
        "min_edge": "'; DELETE FROM strategies; --",
        "' OR '1'='1": Decimal("0.10"),
        "UNION SELECT * FROM users": "injection_attempt",
    }

    try:
        result = manager.create_strategy(
            strategy_name="json_injection_test",
            strategy_version="v1.0",
            strategy_type="value",
            config=malicious_config,
        )
        # If creation succeeds, the malicious strings are stored as literals
        assert result is not None

    except Exception as e:
        # Only SQL syntax error indicates injection vulnerability
        error_str = str(e).lower()
        assert "syntax error" not in error_str, f"SQL injection may have occurred: {e}"

    # CRITICAL: Verify strategies table still exists
    db_cursor.execute("SELECT COUNT(*) as count FROM strategies")
    result = db_cursor.fetchone()
    assert result is not None, "strategies table was dropped by SQL injection!"


# =============================================================================
# Test 6: Table Integrity Check (Uses EXISTING infrastructure - ENABLED)
# =============================================================================


def test_strategies_table_survives_all_injection_attempts(
    db_cursor,
    clean_test_data,
) -> None:
    """
    Verify strategies table remains intact after all SQL injection tests.

    **Security Guarantee**: If ANY injection succeeded, this test would fail.

    This is a "canary test" - if strategies table was dropped by any
    previous injection attempt, this test catches it.

    Args:
        db_cursor: Database cursor fixture
        clean_test_data: Cleanup fixture

    Expected Result:
        - strategies table exists
        - strategies table has expected schema
        - CRUD operations still work
    """
    # Verify table exists - use cursor directly
    db_cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'strategies'
        ) as table_exists
    """)
    result = db_cursor.fetchone()
    assert result is not None
    assert result["table_exists"] is True, "strategies table was dropped by injection!"

    # Verify CRUD still works - use existing API with correct parameters
    strategy_id = crud_operations.create_strategy(
        strategy_name="Post-injection integrity test",
        strategy_version="v1.0",
        strategy_type="value",
        config={"min_edge": Decimal("0.05")},
        status="draft",
    )
    assert strategy_id is not None

    strategy = crud_operations.get_strategy(strategy_id)
    assert strategy is not None
    assert strategy["strategy_name"] == "Post-injection integrity test"
