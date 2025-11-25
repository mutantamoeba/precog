"""
Security tests for SQL injection resistance.

This test suite verifies that parameterized queries prevent SQL injection attacks
across all CRUD operations. Uses malicious input patterns from OWASP testing guide.

Related Issue: GitHub Issue #129 (Security Tests)
Related Pattern: Pattern 4 (Security - NO CREDENTIALS IN CODE)
Related Requirement: REQ-SEC-009 (SQL Injection Prevention)
"""

from decimal import Decimal

import pytest

from precog.database import crud_operations

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
    strategy_id = crud_operations.create_strategy(  # type: ignore[call-arg]  # Strategy Manager API (Phase 1.5)
        name=malicious_input,  # Malicious SQL in name field
        description="SQL injection test strategy",
        config={"min_edge": Decimal("0.05")},
    )

    # Verify strategy created successfully
    assert strategy_id is not None
    assert isinstance(strategy_id, int)

    # Verify name stored exactly as provided (not executed as SQL)
    strategy = crud_operations.get_strategy(strategy_id)
    assert strategy is not None
    assert strategy["name"] == malicious_input  # Exact match - SQL NOT executed

    # Verify strategies table still exists (DROP TABLE prevented)
    all_strategies = crud_operations.list_strategies()  # type: ignore[attr-defined]  # Strategy Manager API (Phase 1.5)
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
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) as count FROM markets")
        result = cur.fetchone()
        assert result is not None  # Table exists and is queryable


@pytest.mark.parametrize("malicious_input", SQL_INJECTION_PAYLOADS)
def test_update_position_rejects_sql_injection_in_notes(
    malicious_input: str,
    db_cursor,
    clean_test_data,
) -> None:
    """
    Verify position update with malicious SQL in notes field is safe.

    **Security Guarantee**: UPDATE statements with parameterized SET clause are safe.

    Educational Note:
        UPDATE statements are vulnerable to injection in both WHERE and SET clauses:

        ❌ VULNERABLE (SET clause):
            query = f"UPDATE positions SET notes = '{malicious_input}' WHERE id = {position_id}"
            # Attacker can inject: notes = 'x', status = 'closed' WHERE '1'='1

        ✅ SAFE:
            query = "UPDATE positions SET notes = %s WHERE id = %s"
            params = (malicious_input, position_id)
            # Both SET value and WHERE condition parameterized

    Args:
        malicious_input: SQL injection payload
        db_cursor: Database cursor fixture
        clean_test_data: Cleanup fixture

    Expected Result:
        - Position notes updated with EXACT malicious input
        - Other position fields unchanged (malicious UPDATE prevented)
        - positions table still exists
    """
    # First, create a test position
    strategy_id = crud_operations.create_strategy(  # type: ignore[call-arg]  # Strategy Manager API (Phase 1.5)
        name="SQL injection test strategy",
        description="For testing position updates",
        config={"min_edge": Decimal("0.05")},
    )

    # Create market for position
    market_data = {
        "external_id": "test-market-sql-injection",
        "ticker": "TEST-SQL-YES",
        "title": "SQL Injection Test Market",
        "market_type": "binary",
        "yes_price": Decimal("0.5000"),
        "no_price": Decimal("0.5000"),
        "status": "open",
        "volume": Decimal("1000.00"),
        "open_interest": 100,
        "spread": Decimal("0.01"),
    }
    market_id = crud_operations.create_market(  # type: ignore[call-arg]  # Market Manager API (Phase 1.5)
        platform_name="kalshi",
        event_name="test-event",
        **market_data,  # type: ignore[arg-type]  # Dict unpacking validated at runtime
    )

    # Create position
    position_id = crud_operations.create_position(  # type: ignore[call-arg]  # Position Manager API (Phase 1.5)
        market_id=market_id,
        strategy_id=strategy_id,  # type: ignore[arg-type]  # Expects int from Strategy Manager
        model_id=1,  # Assuming model_id 1 exists
        side="YES",
        entry_price=Decimal("0.5000"),
        quantity=10,
        entry_reason="SQL injection test",
    )

    # Update position with malicious notes
    updated_id = crud_operations.update_position(  # type: ignore[attr-defined]  # Position Manager API (Phase 1.5)
        position_id=position_id,
        notes=malicious_input,  # Malicious SQL in notes field
    )

    # Verify update succeeded
    assert updated_id == position_id

    # Verify notes stored exactly as provided (not executed as SQL)
    position = crud_operations.get_position(position_id)  # type: ignore[attr-defined]  # Position Manager API (Phase 1.5)
    assert position is not None
    assert position["notes"] == malicious_input  # Exact match

    # Verify other fields unchanged (malicious UPDATE prevented)
    assert position["status"] == "open"  # Status not changed to 'closed'
    assert position["quantity"] == 10  # Quantity not modified
    assert position["entry_price"] == Decimal("0.5000")  # Price not modified


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
    """
    with pytest.raises((TypeError, ValueError)) as exc_info:
        # This should fail type validation BEFORE reaching database
        crud_operations.get_market_history("TEST-TICKER", limit=malicious_limit)  # type: ignore[arg-type]

    # Verify error message indicates type mismatch
    assert "int" in str(exc_info.value).lower() or "limit" in str(exc_info.value).lower()

    # Verify strategies table still exists
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) as count FROM strategies")
        result = cur.fetchone()
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

    # Create strategy with malicious JSON
    strategy_id = crud_operations.create_strategy(  # type: ignore[call-arg]  # Strategy Manager API (Phase 1.5)
        name="JSON injection test",
        description="Testing JSON field security",
        config=malicious_config,
    )

    # Verify strategy created
    assert strategy_id is not None

    # Verify config stored exactly (SQL NOT executed)
    strategy = crud_operations.get_strategy(strategy_id)
    assert strategy is not None
    assert strategy["config"]["malicious_key"] == "'; DROP TABLE strategies; --"
    assert strategy["config"]["nested"]["another_injection"] == "' OR '1'='1"

    # Verify strategies table still exists
    all_strategies = crud_operations.list_strategies()  # type: ignore[attr-defined]  # Strategy Manager API (Phase 1.5)
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
    with db_cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'strategies'
            ) as table_exists
        """)
        result = cur.fetchone()
        assert result is not None
        assert result["table_exists"] is True, "strategies table was dropped by injection!"

    # Verify CRUD still works
    strategy_id = crud_operations.create_strategy(  # type: ignore[call-arg]  # Strategy Manager API (Phase 1.5)
        name="Post-injection integrity test",
        description="Verify CRUD operations work after injection tests",
        config={"min_edge": Decimal("0.05")},
    )
    assert strategy_id is not None

    strategy = crud_operations.get_strategy(strategy_id)
    assert strategy is not None
    assert strategy["name"] == "Post-injection integrity test"
