"""
Security tests for SQL injection resistance.

This test suite verifies that parameterized queries prevent SQL injection attacks
across all CRUD operations. Uses malicious input patterns from OWASP testing guide.

Related Issue: GitHub Issue #129 (Security Tests)
Related Pattern: Pattern 4 (Security - NO CREDENTIALS IN CODE)
Related Requirement: REQ-SEC-009 (SQL Injection Prevention)

NOTE: These tests require Phase 1.5 Manager APIs and lookup table setup.
      Currently skipped until Phase 1.5 implementation.
"""

from decimal import Decimal

import pytest

from precog.database import crud_operations

# NOTE: Phase 1.5 Manager APIs and strategy_types lookup table are now implemented.
# Tests enabled - validating SQL injection resistance in CRUD operations.
pytestmark = pytest.mark.security

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
# Test 1: Strategy CRUD Operations
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
    Even if malicious SQL is provided, it's inserted as a string literal.

    Educational Note:
        Parameterized queries work by sending SQL and parameters separately:

        ❌ VULNERABLE (string concatenation):
            query = f"INSERT INTO strategies (name) VALUES ('{malicious_input}')"
            # Result: INSERT INTO strategies (name) VALUES (''; DROP TABLE strategies; --')
            # SQL sees: 3 statements (INSERT, DROP, comment)

        ✅ SAFE (parameterized):
            query = "INSERT INTO strategies (name) VALUES (%s)"
            params = (malicious_input,)
            # Database driver escapes input: ''; DROP TABLE strategies; --'
            # SQL sees: 1 INSERT with literal string containing SQL metacharacters

    Args:
        malicious_input: SQL injection payload from OWASP patterns
        db_cursor: Database cursor fixture
        clean_test_data: Cleans test data after test completes

    Expected Result:
        - Strategy created successfully (returns strategy_id)
        - Name field contains EXACT malicious input (treated as data)
        - strategies table still exists (DROP TABLE failed)
        - No SQL syntax errors
    """
    # Create strategy with malicious input
    strategy_id = crud_operations.create_strategy(
        strategy_name=malicious_input,  # Malicious SQL in name field
        strategy_version="v1.0",
        strategy_type="value",  # Use valid strategy type from lookup table
        config={"min_edge": str(Decimal("0.05"))},  # String for JSONB
    )

    # Verify strategy created successfully
    assert strategy_id is not None
    assert isinstance(strategy_id, int)

    # Verify name stored exactly as provided (not executed as SQL)
    strategy = crud_operations.get_strategy(strategy_id)
    assert strategy is not None
    assert strategy["strategy_name"] == malicious_input  # Exact match - SQL NOT executed

    # Verify strategies table still exists (DROP TABLE prevented)
    all_strategies = crud_operations.list_strategies()
    assert len(all_strategies) >= 1  # At least our test strategy exists


@pytest.mark.parametrize("malicious_input", SQL_INJECTION_PAYLOADS)
def test_get_market_history_rejects_sql_injection_in_ticker(
    malicious_input: str,
    db_cursor,
    clean_test_data,
) -> None:
    """
    Verify market history query with malicious SQL in ticker is safe.

    **Security Guarantee**: Parameterized WHERE clause prevents injection.

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
    # Query with malicious ticker
    history = crud_operations.get_market_history(malicious_input, limit=10)

    # Verify query executed safely
    assert isinstance(history, list)
    assert len(history) == 0  # No markets with this malicious ticker

    # Verify markets table still exists
    db_cursor.execute("SELECT COUNT(*) as count FROM markets")
    result = db_cursor.fetchone()
    assert result is not None  # Table exists and is queryable


@pytest.mark.parametrize("malicious_input", SQL_INJECTION_PAYLOADS)
def test_update_strategy_status_rejects_sql_injection(
    malicious_input: str,
    db_cursor,
    clean_test_data,
) -> None:
    """
    Verify strategy status update with malicious SQL in status field is safe.

    **Security Guarantee**: UPDATE statements with parameterized SET clause are safe.

    Educational Note:
        UPDATE statements are vulnerable to injection in both WHERE and SET clauses:

        ❌ VULNERABLE (SET clause):
            query = f"UPDATE strategies SET status = '{malicious_input}' WHERE id = {strategy_id}"
            # Attacker can inject: status = 'x', config = '{}' WHERE '1'='1

        ✅ SAFE:
            query = "UPDATE strategies SET status = %s WHERE strategy_id = %s"
            params = (malicious_input, strategy_id)
            # Both SET value and WHERE condition parameterized

        Defense in Depth (3 layers):
        1. Parameterized query - malicious input passed as DATA, not CODE
        2. CHECK constraint - only valid status values allowed (draft/testing/active/deprecated)
        3. VARCHAR(20) limit - long payloads rejected by database

        Security is PROVEN when malicious input is either:
        - Stored as data (not executed as SQL)
        - Rejected by database constraints (invalid value or too long)

        In both cases, the SQL injection FAILED - no code was executed.

    Args:
        malicious_input: SQL injection payload
        db_cursor: Database cursor fixture
        clean_test_data: Cleanup fixture

    Expected Result:
        - SQL injection NOT executed (proven by constraint error OR by data storage)
        - strategies table still exists regardless of outcome
    """
    import psycopg2.errors

    # First, create a test strategy
    strategy_id = crud_operations.create_strategy(
        strategy_name="SQL injection update test",
        strategy_version="v1.0",
        strategy_type="value",  # Use valid strategy type from lookup table
        config={"min_edge": str(Decimal("0.05"))},  # String for JSONB
    )

    assert strategy_id is not None

    # Try to update strategy status with malicious SQL payload
    # Defense in depth: either stored as data OR rejected by constraints
    try:
        result = crud_operations.update_strategy_status(
            strategy_id=strategy_id,
            new_status=malicious_input,  # Malicious SQL in status field
        )

        # If we get here, the malicious input was stored as DATA (not code)
        # This proves the parameterized query worked correctly
        assert result is True

        # Verify status stored exactly as provided (not executed as SQL)
        strategy = crud_operations.get_strategy(strategy_id)
        assert strategy is not None
        assert strategy["status"] == malicious_input  # Exact match - SQL NOT executed

        # Verify other fields unchanged (malicious UPDATE prevented)
        assert strategy["strategy_name"] == "SQL injection update test"
        assert strategy["strategy_version"] == "v1.0"
        assert strategy["config"]["min_edge"] == Decimal("0.05")

    except (
        psycopg2.errors.StringDataRightTruncation,  # VARCHAR(20) limit
        psycopg2.errors.CheckViolation,  # status CHECK constraint
    ):
        # This is ALSO a security success - database constraints rejected
        # the malicious input. The SQL injection was NOT executed.
        pass

    # CRITICAL: Regardless of success/constraint failure, strategies table must exist
    # If SQL injection had executed, the table might be dropped/corrupted
    all_strategies = crud_operations.list_strategies()
    assert len(all_strategies) >= 1, "strategies table was damaged by injection!"


# =============================================================================
# Test 2: LIMIT/OFFSET Injection
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

    Educational Note (Defense in Depth):
        This test demonstrates multiple security layers:
        1. Python type hints (may not catch everything in dynamic code)
        2. Parameterized query (passes value safely to database)
        3. PostgreSQL type enforcement (rejects invalid LIMIT value)

        Even if malicious input bypasses Python type checking, PostgreSQL
        rejects it as invalid input for BIGINT type. The injection FAILS
        because the malicious string is passed as a parameter value,
        not executed as SQL code.
    """
    import psycopg2.errors

    # Either Python raises TypeError/ValueError OR database rejects invalid BIGINT
    with pytest.raises((TypeError, ValueError, psycopg2.errors.InvalidTextRepresentation)):
        # This should fail - either at Python level or database level
        crud_operations.get_market_history("TEST-TICKER", limit=malicious_limit)  # type: ignore[arg-type]

    # Verify strategies table still exists
    db_cursor.execute("SELECT COUNT(*) as count FROM strategies")
    result = db_cursor.fetchone()
    assert result is not None  # Table exists and is queryable


# =============================================================================
# Test 3: JSON Field Injection
# =============================================================================


def test_create_strategy_rejects_sql_injection_in_json_config(
    db_cursor,
    clean_test_data,
) -> None:
    """
    Verify JSON config field with SQL injection payloads is safe.

    **Security Guarantee**: JSON fields stored as JSONB type, not executed as SQL.

    Educational Note:
        JSON fields are potential injection vectors if improperly handled:

        ❌ VULNERABLE:
            query = f"INSERT INTO strategies (config) VALUES ('{json.dumps(config)}')"
            # If config contains: {"key": "'; DROP TABLE strategies; --"}
            # SQL sees: VALUES ('{"key": "'; DROP TABLE strategies; --"}')
            # The closing quote breaks out of JSON string into SQL context

        ✅ SAFE:
            query = "INSERT INTO strategies (config) VALUES (%s::jsonb)"
            params = (json.dumps(config),)
            # Database casts to JSONB type, validates JSON structure
            # SQL metacharacters inside JSON remain as JSON data

    Args:
        db_cursor: Database cursor fixture
        clean_test_data: Cleanup fixture

    Expected Result:
        - Strategy created with malicious JSON config
        - Config stored exactly as provided
        - SQL injection in JSON values NOT executed
    """
    malicious_config = {
        "min_edge": Decimal("0.05"),
        "malicious_key": "'; DROP TABLE strategies; --",
        "nested": {
            "another_injection": "' OR '1'='1",
        },
    }

    # Convert Decimal to string for JSON serialization
    serializable_config = {
        "min_edge": str(malicious_config["min_edge"]),
        "malicious_key": malicious_config["malicious_key"],
        "nested": malicious_config["nested"],
    }

    # Create strategy with malicious JSON
    strategy_id = crud_operations.create_strategy(
        strategy_name="JSON injection test",
        strategy_version="v1.0",
        strategy_type="value",  # Use valid strategy type from lookup table
        config=serializable_config,
    )

    # Verify strategy created
    assert strategy_id is not None

    # Verify config stored exactly (SQL NOT executed)
    strategy = crud_operations.get_strategy(strategy_id)
    assert strategy is not None
    assert strategy["config"]["malicious_key"] == "'; DROP TABLE strategies; --"
    assert strategy["config"]["nested"]["another_injection"] == "' OR '1'='1"

    # Verify strategies table still exists
    all_strategies = crud_operations.list_strategies()
    assert len(all_strategies) >= 1


# =============================================================================
# Test 4: Verify Strategies Table Integrity (Final Check)
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
    # Verify table exists
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

    # Verify CRUD still works
    strategy_id = crud_operations.create_strategy(
        strategy_name="Post-injection integrity test",
        strategy_version="v1.0",
        strategy_type="value",  # Use valid strategy type from lookup table
        config={"min_edge": str(Decimal("0.05"))},
    )
    assert strategy_id is not None

    strategy = crud_operations.get_strategy(strategy_id)
    assert strategy is not None
    assert strategy["strategy_name"] == "Post-injection integrity test"
