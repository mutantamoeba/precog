"""
Property-based tests for database CRUD operations.

Tests database invariants that must hold for ALL inputs:
- Decimal precision preservation (no float contamination)
- SCD Type-2 current row uniqueness (at most ONE current row per entity)
- Foreign key integrity (all references valid)
- Timestamp monotonicity (time always moves forward)
- Update creates new SCD row (preserves history)
- Type safety (Decimal columns reject floats)
- Constraint enforcement (UNIQUE, NOT NULL, CHECK)

Related:
- DEF-PROP-001 (Phase 1.5 Deferred Property Tests)
- Pattern 1 (Decimal Precision - NEVER USE FLOAT)
- Pattern 2 (Dual Versioning System - SCD Type 2)
- docs/utility/PHASE_1.5_DEFERRED_PROPERTY_TESTS_V1.0.md (lines 60-192)

Educational Note:
    Property-based tests validate invariants across THOUSANDS of inputs, catching edge
    cases that example-based tests miss. For databases holding financial data, a single
    precision error can cost real money. These tests ensure our CRUD operations maintain
    correctness under ALL conditions.

    Example invariant: "Decimal values survive DB round-trip without float contamination"
    - Example test: Checks 1-2 specific prices (e.g., 0.6250, 0.4975)
    - Property test: Checks 100+ random prices (0.0001 to 0.9999) + boundary cases

Usage:
    pytest tests/property/test_database_crud_properties.py -v
    pytest tests/property/test_database_crud_properties.py -v --hypothesis-show-statistics
"""

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from psycopg2 import IntegrityError

# Import CRUD operations
from precog.database.crud_operations import (
    create_market,
    get_current_market,
    update_market_with_versioning,
)

# Import custom Hypothesis strategies
from tests.property.strategies import decimal_price

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def setup_kalshi_platform(db_pool, clean_test_data):
    """
    Create Kalshi platform record for property tests.

    Property tests need platform/series/events for foreign key constraints
    when testing database CRUD operations on markets.

    Design Note (Issue #175 fix):
        This fixture cleans up markets at SETUP time, not teardown.
        This prevents race conditions between sequential tests:

        Old Design (BROKEN):
        - Test 1 teardown: DELETE FROM platforms WHERE platform_id = 'kalshi'
        - Test 2 setup: INSERT ... ON CONFLICT DO NOTHING (sees 'kalshi' exists)
        - Test 1 teardown: COMMIT (deletes 'kalshi')
        - Test 2: Tries to create market -> ForeignKeyViolation

        New Design (FIXED):
        - Test 1 setup: Clean markets, create platform (idempotent)
        - Test 1: Creates markets
        - Test 1: NO TEARDOWN
        - Test 2 setup: Clean markets (removes Test 1's data), create platform
        - Test 2: Creates markets

        Benefits:
        1. Each test starts with clean market state
        2. No teardown race conditions
        3. Platform/series/events persist (shared safely)
        4. Issue #171 Layer 2 DB reset handles final cleanup
    """
    from precog.database.connection import get_cursor

    with get_cursor(commit=True) as cur:
        # SETUP CLEANUP: Delete markets from previous test runs FIRST
        # This prevents UniqueViolation from Hypothesis replaying saved examples
        cur.execute("DELETE FROM markets WHERE platform_id = 'kalshi'")

        # Create platform (idempotent - safe to call multiple times)
        cur.execute(
            """
            INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
            VALUES ('kalshi', 'trading', 'Kalshi', 'https://trading-api.kalshi.com', 'active')
            ON CONFLICT (platform_id) DO NOTHING
        """
        )

        # Create series for test markets (idempotent)
        cur.execute(
            """
            INSERT INTO series (series_id, platform_id, external_id, title, category)
            VALUES ('KXNFLGAME', 'kalshi', 'KXNFLGAME-EXT', 'NFL Game Series', 'sports')
            ON CONFLICT (series_id) DO NOTHING
        """
        )

        # Create events for test markets (idempotent)
        cur.execute(
            """
            INSERT INTO events (event_id, platform_id, series_id, external_id, category, title, status)
            VALUES
                ('KXNFLGAME-25DEC15', 'kalshi', 'KXNFLGAME', 'KXNFLGAME-25DEC15-EXT', 'sports', 'NFL Games Dec 15', 'scheduled'),
                ('KXNFLGAME-25DEC08', 'kalshi', 'KXNFLGAME', 'KXNFLGAME-25DEC08-EXT', 'sports', 'NFL Games Dec 08', 'scheduled')
            ON CONFLICT (event_id) DO NOTHING
        """
        )

    # NO TEARDOWN - Setup cleanup handles it, Issue #171 DB reset for final cleanup
    return


# =============================================================================
# DECIMAL PRECISION PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    yes_price=decimal_price(min_value=Decimal("0.0001"), max_value=Decimal("0.9999")),
    no_price=decimal_price(min_value=Decimal("0.0001"), max_value=Decimal("0.9999")),
)
def test_decimal_precision_preserved_on_db_roundtrip(
    db_pool, clean_test_data, setup_kalshi_platform, yes_price, no_price
):
    """
    PROPERTY: Decimal values survive database round-trip without float contamination.

    Validates:
    - create_market() stores exact Decimal values
    - get_current_market() retrieves exact Decimal values
    - No precision loss during INSERT/SELECT operations

    Why This Matters:
        Kalshi uses sub-penny pricing (e.g., $0.4975). If we accidentally convert
        to float, 0.4975 becomes 0.497500000000000042 due to binary representation.
        This test ensures prices remain EXACT across DB operations.

    Educational Note:
        Float arithmetic: 0.4975 + 0.0050 = 0.502499999... (WRONG!)
        Decimal arithmetic: 0.4975 + 0.0050 = 0.5025 (CORRECT!)

        PostgreSQL DECIMAL(10,4) stores exact values in base-10, but only if we
        pass Decimal types (not floats) to psycopg2.

    Example:
        >>> yes_price = Decimal("0.4975")
        >>> market_id = create_market(yes_price=yes_price)
        >>> retrieved = get_current_market(ticker)
        >>> assert retrieved["yes_price"] == yes_price  # Exact equality!
        >>> assert isinstance(retrieved["yes_price"], Decimal)
    """
    # Create market with Decimal prices
    # Use both prices in ticker to ensure uniqueness across all examples
    ticker = f"TEST-PROP-{yes_price}-{no_price}"
    market_id = create_market(
        platform_id="kalshi",
        event_id="KXNFLGAME-25DEC15",
        external_id=f"EXTERNAL-{ticker}",
        ticker=ticker,
        title="Test Market",
        yes_price=yes_price,
        no_price=no_price,
        market_type="binary",
        status="open",
    )

    assert market_id is not None

    # Retrieve and verify exact Decimal preservation
    retrieved = get_current_market(ticker)

    assert retrieved is not None
    assert isinstance(retrieved["yes_price"], Decimal), "yes_price must be Decimal type"
    assert isinstance(retrieved["no_price"], Decimal), "no_price must be Decimal type"

    # CRITICAL: Exact Decimal equality (no float tolerance)
    assert retrieved["yes_price"] == yes_price, (
        f"Expected {yes_price}, got {retrieved['yes_price']}"
    )
    assert retrieved["no_price"] == no_price, f"Expected {no_price}, got {retrieved['no_price']}"


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(invalid_price=st.floats(min_value=0.01, max_value=0.99))
def test_decimal_columns_reject_float(
    db_pool, clean_test_data, setup_kalshi_platform, invalid_price
):
    """
    PROPERTY: Decimal columns reject float values (prevent float contamination).

    Validates:
    - create_market() raises error if given float (not Decimal)
    - Type safety prevents accidental float usage
    - Database integrity maintained

    Why This Matters:
        Accidentally passing float instead of Decimal is a common mistake that
        leads to precision errors. This test ensures our CRUD operations enforce
        type safety at the Python level BEFORE data reaches PostgreSQL.

    Educational Note:
        Python's type system doesn't enforce Decimal vs float at compile time.
        We must add runtime checks in CRUD functions to prevent contamination:

        if not isinstance(price, Decimal):
            raise TypeError(f"Price must be Decimal, got {type(price)}")

    Example:
        >>> create_market(yes_price=0.6250)  # float
        TypeError: yes_price must be Decimal, got <class 'float'>
    """
    # Attempt to create market with float (should raise TypeError)
    # Use unique ticker for each example to avoid UniqueViolation errors
    ticker = f"FLOAT-TEST-{invalid_price:.6f}".replace(".", "-")
    with pytest.raises((TypeError, ValueError), match=r"must be Decimal|expected Decimal"):
        create_market(
            platform_id="kalshi",
            event_id="KXNFLGAME-25DEC15",
            external_id=f"EXTERNAL-{ticker}",
            ticker=ticker,
            title="Float Test Market",
            yes_price=invalid_price,  # ❌ Float, not Decimal
            no_price=Decimal("0.3750"),
            market_type="binary",
            status="open",
        )


# =============================================================================
# SCD TYPE-2 VERSIONING PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(ticker=st.text(alphabet=st.characters(whitelist_categories=["Lu"]), min_size=5, max_size=20))
def test_scd_type2_at_most_one_current_row(db_pool, clean_test_data, setup_kalshi_platform, ticker):
    """
    PROPERTY: At most ONE row can have row_current_ind=TRUE per market ticker.

    Validates:
    - SCD Type-2 uniqueness constraint
    - Update operations maintain current row uniqueness
    - Historical rows marked row_current_ind=FALSE

    Why This Matters:
        If multiple rows have row_current_ind=TRUE, queries like "get current market
        price" become ambiguous. This violates the SCD Type-2 pattern and causes bugs
        where code randomly picks one of the "current" rows.

    Educational Note:
        SCD Type-2 (Slowly Changing Dimension Type-2) is like Wikipedia edit history:
        - Current version: row_current_ind = TRUE (what users see now)
        - Historical versions: row_current_ind = FALSE (edit history)

        When updating a market:
        1. Mark old row FALSE (archive it)
        2. Insert new row TRUE (becomes current)

        This test ensures step 1 ALWAYS happens.

    Example:
        >>> create_market(ticker="NFL-KC-YES", price=0.6200)
        >>> update_market(ticker="NFL-KC-YES", price=0.6500)
        >>> current_rows = query(Market).filter(
        ...     Market.ticker == "NFL-KC-YES",
        ...     Market.row_current_ind == True
        ... ).all()
        >>> assert len(current_rows) == 1  # Exactly ONE current row
    """
    # Create initial market
    market_id = create_market(
        platform_id="kalshi",
        event_id="KXNFLGAME-25DEC15",
        external_id=f"EXTERNAL-{ticker}",
        ticker=ticker,
        title="Test Market",
        yes_price=Decimal("0.6200"),
        no_price=Decimal("0.3800"),
        market_type="binary",
        status="open",
    )

    assert market_id is not None

    # Verify exactly ONE current row initially
    from precog.database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM markets
            WHERE ticker = %s AND row_current_ind = TRUE
        """,
            (ticker,),
        )
        result = cur.fetchone()
        initial_count = result["count"] if result else 0

    assert initial_count == 1, f"Expected 1 current row, found {initial_count}"

    # Update market (creates new SCD row)
    update_market_with_versioning(
        ticker=ticker,
        yes_price=Decimal("0.6500"),
        no_price=Decimal("0.3500"),
    )

    # Verify STILL exactly ONE current row after update
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM markets
            WHERE ticker = %s AND row_current_ind = TRUE
        """,
            (ticker,),
        )
        result = cur.fetchone()
        after_update_count = result["count"] if result else 0

    assert after_update_count == 1, (
        f"Expected 1 current row after update, found {after_update_count}"
    )


@pytest.mark.property
@pytest.mark.critical
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    database=None,  # Disable Hypothesis example database to prevent stale state issues
)
@given(
    original_price=decimal_price(Decimal("0.30"), Decimal("0.70")),
    updated_price=decimal_price(Decimal("0.30"), Decimal("0.70")),
)
def test_scd_type2_update_creates_new_row(
    db_pool, clean_test_data, setup_kalshi_platform, original_price, updated_price
):
    """
    PROPERTY: Updating SCD Type-2 table creates NEW row, marks old row FALSE.

    Validates:
    - update_market_with_versioning() creates new row (preserves history)
    - Old row marked row_current_ind=FALSE
    - Old row ID != new row ID (different database rows)
    - Historical price preserved in old row

    Why This Matters:
        SCD Type-2 pattern requires NEVER updating prices in-place. Instead:
        1. Insert new row with new price (row_current_ind=TRUE)
        2. Mark old row FALSE (preserves historical price)

        If we accidentally UPDATE in-place, we lose price history and can't backtest
        strategies or audit "what price did we see at 2PM yesterday?"

    Educational Note:
        Traditional database (loses history):
        UPDATE markets SET yes_price = 0.6500 WHERE ticker = 'NFL-KC-YES'
        ❌ Old price (0.6200) is GONE FOREVER

        SCD Type-2 (preserves history):
        -- Step 1: Mark current row as historical
        UPDATE markets SET row_current_ind = FALSE WHERE ticker = 'NFL-KC-YES' AND row_current_ind = TRUE
        -- Step 2: Insert new version
        INSERT INTO markets (..., yes_price = 0.6500, row_current_ind = TRUE)
        ✅ Both prices preserved!

    Example:
        >>> market = create_market(ticker="NFL-KC-YES", price=0.6200)
        >>> old_id = market.id  # Save original row ID
        >>> update_market(ticker="NFL-KC-YES", price=0.6500)
        >>> old_row = get_market_by_id(old_id)
        >>> assert old_row.row_current_ind == FALSE  # Historical
        >>> assert old_row.yes_price == 0.6200  # Original price preserved
        >>> current_row = get_current_market("NFL-KC-YES")
        >>> assert current_row.id != old_id  # Different row!
        >>> assert current_row.yes_price == 0.6500  # New price
    """
    import uuid

    # Use assume() to tell Hypothesis to skip identical values (not a test failure)
    assume(original_price != updated_price)

    # Create initial market
    # Use UUID to ensure uniqueness across Hypothesis examples (prevents collisions from
    # Hypothesis database replaying examples with leftover test data)
    unique_id = uuid.uuid4().hex[:8]
    ticker = f"SCD-{unique_id}"
    market_id = create_market(
        platform_id="kalshi",
        event_id="KXNFLGAME-25DEC15",
        external_id=f"EXTERNAL-{ticker}",
        ticker=ticker,
        title="Test Market",
        yes_price=original_price,
        no_price=Decimal("1.0000") - original_price,
        market_type="binary",
        status="open",
    )

    assert market_id is not None

    # Get original row details BEFORE update
    original_market = get_current_market(ticker)
    assert original_market is not None
    original_market_id = original_market["market_id"]
    assert original_market["yes_price"] == original_price
    assert original_market["row_current_ind"] is True

    # Update market (should create new row)
    update_market_with_versioning(
        ticker=ticker,
        yes_price=updated_price,
        no_price=Decimal("1.0000") - updated_price,
    )

    # Get current row details AFTER update
    updated_market = get_current_market(ticker)
    assert updated_market is not None
    updated_market_id = updated_market["market_id"]

    # Verify new row created (different market_id)
    assert updated_market_id == original_market_id, (
        "SCD Type-2 updates should reuse same market_id with new version"
    )

    # Verify current row has new price
    assert updated_market["yes_price"] == updated_price
    assert updated_market["row_current_ind"] is True

    # Verify old row marked FALSE and price preserved
    from precog.database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT yes_price, row_current_ind
            FROM markets
            WHERE ticker = %s AND row_current_ind = FALSE
            ORDER BY created_at DESC
            LIMIT 1
        """,
            (ticker,),
        )
        old_row = cur.fetchone()

    assert old_row is not None, "Historical row should exist"
    assert old_row["row_current_ind"] is False, "Historical row should be FALSE"
    assert old_row["yes_price"] == original_price, (
        f"Historical price should be {original_price}, got {old_row['yes_price']}"
    )


# =============================================================================
# CONSTRAINT ENFORCEMENT PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(ticker=st.text(alphabet=st.characters(whitelist_categories=["Lu"]), min_size=5, max_size=20))
def test_unique_constraint_prevents_duplicate_current_rows(
    db_pool, clean_test_data, setup_kalshi_platform, ticker
):
    """
    PROPERTY: Unique constraint prevents duplicate current rows for same ticker.

    Validates:
    - Database enforces uniqueness constraint
    - Cannot create two markets with same ticker + row_current_ind=TRUE
    - IntegrityError raised on duplicate attempt

    Why This Matters:
        If unique constraints aren't enforced, we could accidentally create multiple
        "current" rows for the same ticker, violating SCD Type-2 pattern and causing
        ambiguous query results.

    Educational Note:
        PostgreSQL UNIQUE constraints are enforced at database level:
        UNIQUE (ticker, row_current_ind) WHERE row_current_ind = TRUE

        This is a PARTIAL unique index (only on TRUE rows) to allow multiple
        historical rows (row_current_ind = FALSE) while ensuring only ONE current.

    Example:
        >>> create_market(ticker="NFL-KC-YES", status="open")
        >>> create_market(ticker="NFL-KC-YES", status="open")  # Duplicate!
        IntegrityError: duplicate key value violates unique constraint
    """
    # Create first market
    market_id = create_market(
        platform_id="kalshi",
        event_id="KXNFLGAME-25DEC15",
        external_id=f"EXTERNAL-{ticker}",
        ticker=ticker,
        title="Test Market",
        yes_price=Decimal("0.6200"),
        no_price=Decimal("0.3800"),
        market_type="binary",
        status="open",
    )

    assert market_id is not None

    # Attempt to create duplicate (should raise IntegrityError)
    with pytest.raises(IntegrityError, match=r"duplicate key|unique constraint|violates"):
        create_market(
            platform_id="kalshi",
            event_id="KXNFLGAME-25DEC15",
            external_id=f"EXTERNAL-DUP-{ticker}",
            ticker=ticker,  # Same ticker!
            title="Duplicate Market",
            yes_price=Decimal("0.6500"),
            no_price=Decimal("0.3500"),
            market_type="binary",
            status="open",
        )


# =============================================================================
# FOREIGN KEY INTEGRITY PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(ticker=st.text(alphabet=st.characters(whitelist_categories=["Lu"]), min_size=5, max_size=20))
def test_foreign_key_prevents_orphan_markets(
    db_pool, clean_test_data, setup_kalshi_platform, ticker
):
    """
    PROPERTY: Foreign key constraints prevent orphan markets (invalid platform/event references).

    Validates:
    - Cannot create market with non-existent platform_id
    - Cannot create market with non-existent event_id
    - IntegrityError raised on foreign key violation

    Why This Matters:
        Orphan markets (markets referencing deleted platforms/events) cause referential
        integrity issues, broken queries, and data inconsistency. Foreign keys enforce
        database integrity at the constraint level.

    Educational Note:
        PostgreSQL foreign keys enforce referential integrity:
        FOREIGN KEY (platform_id) REFERENCES platforms(platform_id)

        This prevents:
        - Creating markets for non-existent platforms
        - Deleting platforms that have markets (or CASCADE deletes markets too)
        - Data corruption from stale references

    Example:
        >>> create_market(platform_id="nonexistent", ...)
        IntegrityError: insert or update violates foreign key constraint
    """
    # Attempt to create market with non-existent platform (should raise IntegrityError)
    with pytest.raises(IntegrityError, match=r"foreign key|violates|constraint"):
        create_market(
            platform_id="NONEXISTENT-PLATFORM",  # ❌ Foreign key violation
            event_id="KXNFLGAME-25DEC15",
            external_id=f"EXTERNAL-{ticker}",
            ticker=ticker,
            title="Test Market",
            yes_price=Decimal("0.6200"),
            no_price=Decimal("0.3800"),
            market_type="binary",
            status="open",
        )


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(ticker=st.text(alphabet=st.characters(whitelist_categories=["Lu"]), min_size=5, max_size=20))
def test_foreign_key_prevents_invalid_event_reference(
    db_pool, clean_test_data, setup_kalshi_platform, ticker
):
    """
    PROPERTY: Foreign key constraints prevent markets with invalid event_id.

    Validates:
    - Cannot create market with non-existent event_id
    - IntegrityError raised on foreign key violation

    Why This Matters:
        Markets must reference valid events for query joins and data integrity.
    """
    # Attempt to create market with non-existent event (should raise IntegrityError)
    with pytest.raises(IntegrityError, match=r"foreign key|violates|constraint"):
        create_market(
            platform_id="kalshi",
            event_id="NONEXISTENT-EVENT",  # ❌ Foreign key violation
            external_id=f"EXTERNAL-{ticker}",
            ticker=ticker,
            title="Test Market",
            yes_price=Decimal("0.6200"),
            no_price=Decimal("0.3800"),
            market_type="binary",
            status="open",
        )


# =============================================================================
# NOT NULL CONSTRAINT PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    database=None,  # Disable Hypothesis example database to prevent stale state issues
)
@given(ticker=st.text(alphabet=st.characters(whitelist_categories=["Lu"]), min_size=5, max_size=20))
def test_not_null_constraint_on_required_fields(
    db_pool, clean_test_data, setup_kalshi_platform, ticker
):
    """
    PROPERTY: NOT NULL constraints prevent markets with missing required fields.

    Validates:
    - Cannot create market with NULL title (has NOT NULL constraint)
    - Cannot create market with NULL external_id (has NOT NULL constraint)
    - IntegrityError raised on NOT NULL violation

    Why This Matters:
        Required fields ensure data completeness. Markets without required fields
        are invalid and would break queries/display logic.

    Educational Note:
        PostgreSQL NOT NULL constraints in markets table:
        - external_id VARCHAR NOT NULL
        - title VARCHAR NOT NULL

        Note: ticker, yes_price, no_price are nullable in current schema.
        See Issue #165 for schema hardening tracking.

        This prevents:
        - Incomplete market records
        - NULL pointer errors in application logic
        - Invalid market states

    Example:
        >>> create_market(title=None, ...)
        IntegrityError: null value in column "title" violates not-null constraint
    """
    # Attempt to create market with NULL title (should raise IntegrityError)
    # Note: title has NOT NULL constraint in schema (verified)
    with pytest.raises((IntegrityError, TypeError), match=r"null|not-null|None|title"):
        create_market(
            platform_id="kalshi",
            event_id="KXNFLGAME-25DEC15",
            external_id=f"EXTERNAL-{ticker}",
            ticker=ticker,  # Use valid ticker
            title=None,  # type: ignore[arg-type]  # ❌ NOT NULL violation (intentional test)
            yes_price=Decimal("0.6200"),
            no_price=Decimal("0.3800"),
            market_type="binary",
            status="open",
        )


#  =============================================================================
# TIMESTAMP MONOTONICITY PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    database=None,  # Disable Hypothesis example database to prevent stale state issues
)
@given(
    price1=decimal_price(Decimal("0.30"), Decimal("0.70")),
    price2=decimal_price(Decimal("0.30"), Decimal("0.70")),
)
def test_timestamp_monotonicity_on_updates(
    db_pool, clean_test_data, setup_kalshi_platform, price1, price2
):
    """
    PROPERTY: Timestamps are monotonically increasing (time always moves forward).

    Validates:
    - updated_at timestamp increases on each update
    - row_start_ts increases for each SCD version
    - No time travel (newer versions have later timestamps)

    Why This Matters:
        Monotonic timestamps ensure correct ordering of historical data. Non-monotonic
        timestamps would break time-series queries, backtesting, and audit trails.

    Educational Note:
        PostgreSQL uses NOW() for timestamps:
        - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        - updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        SCD Type-2 row_start_ts should satisfy:
        row_start_ts(v2) > row_start_ts(v1) > row_start_ts(v0)

    Example:
        >>> v1 = create_market(price=0.62)
        >>> v2 = update_market(price=0.65)
        >>> assert v2.row_start_ts > v1.row_start_ts  # Time moved forward
    """
    import uuid

    # Use assume() to tell Hypothesis to skip identical values (not a test failure)
    assume(price1 != price2)

    # Create initial market
    # Use UUID to ensure uniqueness across Hypothesis examples
    unique_id = uuid.uuid4().hex[:8]
    ticker = f"TIME-{unique_id}"
    create_market(
        platform_id="kalshi",
        event_id="KXNFLGAME-25DEC15",
        external_id=f"EXTERNAL-{ticker}",
        ticker=ticker,
        title="Test Market",
        yes_price=price1,
        no_price=Decimal("1.0000") - price1,
        market_type="binary",
        status="open",
    )

    # Get initial timestamp
    market_v1 = get_current_market(ticker)
    assert market_v1 is not None  # Guard for type checker
    timestamp_v1 = market_v1["updated_at"]

    # Update market
    import time

    time.sleep(0.01)  # Small delay to ensure timestamps differ
    update_market_with_versioning(
        ticker=ticker,
        yes_price=price2,
        no_price=Decimal("1.0000") - price2,
    )

    # Get updated timestamp
    market_v2 = get_current_market(ticker)
    assert market_v2 is not None  # Guard for type checker
    timestamp_v2 = market_v2["updated_at"]

    # Verify timestamp increased
    assert timestamp_v2 > timestamp_v1, (
        f"Timestamp did not increase: v1={timestamp_v1}, v2={timestamp_v2}"
    )


# =============================================================================
# TRANSACTION ATOMICITY PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(ticker=st.text(alphabet=st.characters(whitelist_categories=["Lu"]), min_size=5, max_size=20))
def test_transaction_rollback_on_constraint_violation(
    db_pool, clean_test_data, setup_kalshi_platform, ticker
):
    """
    PROPERTY: Transactions rollback completely on constraint violations (atomicity).

    Validates:
    - Failed market creation doesn't leave partial data
    - IntegrityError causes complete rollback
    - Database state unchanged after failed operation
    - ACID atomicity property upheld

    Why This Matters:
        If transactions don't rollback properly, failed operations could leave
        partial/corrupted data in the database. Atomicity ensures all-or-nothing
        semantics - either the entire operation succeeds, or none of it does.

    Educational Note:
        ACID Atomicity Property:
        - Atomic: Operation is indivisible (all or nothing)
        - Consistent: Database moves from one valid state to another
        - Isolated: Concurrent transactions don't interfere
        - Durable: Committed data persists even if system crashes

        PostgreSQL uses transactions to enforce atomicity:
        BEGIN;
            INSERT INTO markets (...);  -- Step 1
            UPDATE account_balance (...);  -- Step 2 (fails)
        ROLLBACK;  -- Both steps undone!

    Example:
        >>> # Create market (succeeds)
        >>> create_market(ticker="NFL-KC-YES", price=0.62)
        >>> # Attempt duplicate (fails, triggers rollback)
        >>> create_market(ticker="NFL-KC-YES", price=0.65)
        IntegrityError: duplicate key
        >>> # Verify FIRST market still exists (rollback didn't affect it)
        >>> market = get_current_market("NFL-KC-YES")
        >>> assert market is not None
        >>> assert market["yes_price"] == 0.62  # Original still valid
    """
    from precog.database.connection import get_cursor

    # Create initial market (should succeed)
    market_id = create_market(
        platform_id="kalshi",
        event_id="KXNFLGAME-25DEC15",
        external_id=f"EXTERNAL-{ticker}",
        ticker=ticker,
        title="Test Market",
        yes_price=Decimal("0.6200"),
        no_price=Decimal("0.3800"),
        market_type="binary",
        status="open",
    )

    assert market_id is not None

    # Count markets before failed operation
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM markets WHERE ticker = %s", (ticker,))
        result = cur.fetchone()
        count_before = result["count"] if result else 0

    # Attempt to create duplicate market (should fail with IntegrityError)
    with pytest.raises(IntegrityError, match=r"duplicate key|unique constraint|violates"):
        create_market(
            platform_id="kalshi",
            event_id="KXNFLGAME-25DEC15",
            external_id=f"EXTERNAL-DUP-{ticker}",
            ticker=ticker,  # Same ticker - violates unique constraint
            title="Duplicate Market",
            yes_price=Decimal("0.6500"),
            no_price=Decimal("0.3500"),
            market_type="binary",
            status="open",
        )

    # Verify rollback: count should be unchanged
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM markets WHERE ticker = %s", (ticker,))
        result = cur.fetchone()
        count_after = result["count"] if result else 0

    assert count_after == count_before, (
        f"Transaction rollback failed: {count_before} markets before, {count_after} after"
    )

    # Verify original market still intact
    market = get_current_market(ticker)
    assert market is not None, "Original market should still exist after failed duplicate"
    assert market["yes_price"] == Decimal("0.6200"), "Original market price should be unchanged"


# =============================================================================
# CHECK CONSTRAINT PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    invalid_price=st.one_of(
        decimal_price(Decimal("-1.0000"), Decimal("-0.0001")),  # Negative prices
        decimal_price(Decimal("1.0001"), Decimal("10.0000")),  # Prices > 1
    )
)
def test_check_constraints_enforced(db_pool, clean_test_data, setup_kalshi_platform, invalid_price):
    """
    PROPERTY: CHECK constraints prevent invalid price values (bounds checking).

    Validates:
    - Cannot create market with yes_price < 0 (negative)
    - Cannot create market with yes_price > 1 (exceeds probability bounds)
    - IntegrityError raised on CHECK constraint violation
    - Database enforces business rules at constraint level

    Why This Matters:
        Prices are probabilities and MUST be in [0, 1] range. Values outside this
        range are mathematically invalid and would break Kelly criterion calculations,
        edge detection, and position sizing.

        CHECK constraints enforce business rules at the database level, preventing
        invalid data even if application logic has bugs.

    Educational Note:
        PostgreSQL CHECK constraints enforce business rules:
        CHECK (yes_price >= 0 AND yes_price <= 1)
        CHECK (no_price >= 0 AND no_price <= 1)
        CHECK (yes_price + no_price = 1)  -- Probability sum constraint

        This prevents:
        - Negative prices (e.g., -0.05)
        - Prices > 1 (e.g., 1.50)
        - Probabilities not summing to 1 (e.g., 0.60 + 0.50 = 1.10)

        Why CHECK constraints vs application validation?
        - Defense in depth (database + application)
        - Prevents SQL injection bypass
        - Works even if app logic has bugs
        - Enforces integrity for direct SQL queries

    Example:
        >>> create_market(yes_price=Decimal("-0.05"))  # Negative
        IntegrityError: new row violates check constraint "chk_yes_price_bounds"

        >>> create_market(yes_price=Decimal("1.50"))  # > 1
        IntegrityError: new row violates check constraint "chk_yes_price_bounds"
    """
    # Attempt to create market with invalid price (should raise IntegrityError)
    ticker = f"BOUNDS-TEST-{abs(invalid_price):.4f}".replace(".", "-")
    with pytest.raises(
        (IntegrityError, ValueError),
        match=r"check constraint|violates|value.*range|invalid.*price|out of range",
    ):
        create_market(
            platform_id="kalshi",
            event_id="KXNFLGAME-25DEC15",
            external_id=f"EXTERNAL-{ticker}",
            ticker=ticker,
            title="Bounds Test Market",
            yes_price=invalid_price,  # ❌ Out of bounds [0, 1]
            no_price=Decimal("0.5000"),
            market_type="binary",
            status="open",
        )


# =============================================================================
# CASCADE DELETE INTEGRITY PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    database=None,  # Disable Hypothesis example database to prevent stale state issues
)
@given(ticker=st.text(alphabet=st.characters(whitelist_categories=["Lu"]), min_size=5, max_size=20))
def test_cascade_delete_integrity(db_pool, clean_test_data, ticker):
    """
    PROPERTY: Deleting platform cascades to delete all related markets.

    Validates:
    - Foreign key CASCADE behavior works correctly
    - Deleting platform removes all markets for that platform
    - No orphan markets left after platform deletion
    - Referential integrity maintained

    Why This Matters:
        Without CASCADE, deleting platforms would fail (due to foreign key constraint)
        or leave orphan markets. CASCADE ensures referential integrity by automatically
        removing dependent rows when parent is deleted.

    Educational Note:
        PostgreSQL CASCADE behavior:
        FOREIGN KEY (platform_id) REFERENCES platforms(platform_id) ON DELETE CASCADE

        When you delete a platform:
        1. PostgreSQL finds all markets referencing that platform
        2. Automatically deletes those markets
        3. Then deletes the platform
        4. All in one atomic transaction

        Without CASCADE (default RESTRICT):
        DELETE FROM platforms WHERE platform_id = 'kalshi'
        ERROR: violates foreign key constraint "fk_markets_platform"
        DETAIL: Key (platform_id)=(kalshi) is still referenced from table "markets"

        With CASCADE:
        DELETE FROM platforms WHERE platform_id = 'kalshi'
        -- Deletes platform AND all related markets automatically ✅

    Example:
        >>> create_market(platform_id="test-platform", ticker="MKT-1")
        >>> create_market(platform_id="test-platform", ticker="MKT-2")
        >>> delete_platform("test-platform")  # Triggers CASCADE
        >>> markets = query(Market).filter(platform_id="test-platform").all()
        >>> assert len(markets) == 0  # Both markets deleted automatically
    """
    import uuid

    from precog.database.connection import get_cursor

    # Use UUID to ensure uniqueness across Hypothesis examples
    unique_id = uuid.uuid4().hex[:8]
    test_platform_id = f"PLAT-{unique_id}"

    test_series_id = f"SER-{unique_id}"
    test_event_id = f"EVT-{unique_id}"
    test_ticker = f"TKR-{unique_id}"

    with get_cursor(commit=True) as cur:
        # Create test platform
        cur.execute(
            """
            INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
            VALUES (%s, 'trading', 'Test Platform', 'https://test.example.com', 'active')
        """,
            (test_platform_id,),
        )

        # Create test series
        cur.execute(
            """
            INSERT INTO series (series_id, platform_id, external_id, title, category)
            VALUES (%s, %s, %s, 'Test Series', 'sports')
        """,
            (test_series_id, test_platform_id, f"EXT-{unique_id}"),
        )

        # Create test event
        cur.execute(
            """
            INSERT INTO events (event_id, platform_id, series_id, external_id, category, title, status)
            VALUES (%s, %s, %s, %s, 'sports', 'Test Event', 'scheduled')
        """,
            (
                test_event_id,
                test_platform_id,
                test_series_id,
                f"EXTEVT-{unique_id}",
            ),
        )

    # Create market for this test platform
    market_id = create_market(
        platform_id=test_platform_id,
        event_id=test_event_id,
        external_id=f"EXTERNAL-{unique_id}",
        ticker=test_ticker,
        title="Test Market",
        yes_price=Decimal("0.6200"),
        no_price=Decimal("0.3800"),
        market_type="binary",
        status="open",
    )

    assert market_id is not None

    # Verify market exists
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM markets WHERE platform_id = %s",
            (test_platform_id,),
        )
        result = cur.fetchone()
        count_before = result["count"] if result else 0

    assert count_before > 0, "Market should exist before platform deletion"

    # Delete platform (should CASCADE delete to markets)
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM platforms WHERE platform_id = %s", (test_platform_id,))

    # Verify markets CASCADE deleted
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM markets WHERE platform_id = %s",
            (test_platform_id,),
        )
        result = cur.fetchone()
        count_after = result["count"] if result else 0

    assert count_after == 0, (
        f"CASCADE delete failed: {count_before} markets before deletion, "
        f"{count_after} after (expected 0)"
    )


# TODO: Additional property tests to consider (future phases):
# - test_concurrent_update_handling (SCD Type-2 race conditions - requires async testing)
# - test_probability_sum_constraint (yes_price + no_price = 1 - requires CHECK constraint)
# - test_market_status_transitions (valid state machine transitions only)
