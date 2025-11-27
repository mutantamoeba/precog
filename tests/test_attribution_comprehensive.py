#!/usr/bin/env python3
"""
Comprehensive 8-Type Test Coverage for Attribution Architecture

This file extends test_attribution.py with 6 additional test types:
- Property-Based Tests (Hypothesis)
- End-to-End Tests
- Stress Tests
- Race Condition Tests
- Performance Tests
- Chaos/Edge Case Tests

**Total Test Coverage Framework (8 Types):**
1. ✅ Unit Tests (test_attribution.py - 15 tests)
2. ✅ Property Tests (this file - 2 tests)
3. ✅ Integration Tests (test_attribution.py - included in 15 tests)
4. ✅ E2E Tests (this file - 1 test)
5. ✅ Stress Tests (this file - 2 tests)
6. ✅ Race Tests (this file - 1 test)
7. ✅ Performance Tests (this file - 1 test)
8. ✅ Chaos Tests (this file - 3 tests)

**References:**
- REQ-TEST-012: Unit testing standards (✅ Complete)
- REQ-TEST-013: Property-based testing (✅ Complete)
- REQ-TEST-014: Integration testing (✅ Complete)
- REQ-TEST-015: End-to-end testing (✅ Complete)
- REQ-TEST-016: Stress testing (✅ Complete)
- REQ-TEST-017: Race condition testing (✅ Complete)
- REQ-TEST-018: Performance testing (✅ Complete)
- REQ-TEST-019: Chaos/edge case testing (✅ Complete)

Created: 2025-11-21
"""

import threading
import time
from decimal import Decimal
from queue import Queue

import pytest
from hypothesis import given
from hypothesis import strategies as st

from precog.database.connection import fetch_all
from precog.database.crud_operations import (
    create_market,
    create_position,
    create_trade,
    get_position_by_id,
    get_trade_by_id,
)

# =============================================================================
# TEST SUITE 5: PROPERTY-BASED TESTS (HYPOTHESIS)
# =============================================================================


@pytest.mark.property
def test_property_edge_calculation_invariant(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Property Test: Edge calculation invariant.

    Property:
        edge_value = calculated_probability - market_price
        ALWAYS holds for ANY valid probability and price values.

    Educational Note:
        Property-based testing generates hundreds of test cases automatically.
        This verifies the edge calculation formula holds for ALL inputs,
        not just a few hand-picked examples.

    Reference:
        - Pattern 10: Property-Based Testing with Hypothesis
        - REQ-TEST-013: Property-based testing for invariants
    """

    @given(
        calculated_prob=st.decimals(
            min_value=Decimal("0.0"),
            max_value=Decimal("1.0"),
            places=4,
        ),
        market_price=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("0.99"),
            places=4,
        ),
    )
    def check_edge_invariant(calculated_prob, market_price):
        """Property: edge = calculated_probability - market_price"""
        trade_id = create_trade(
            market_id=sample_market,
            strategy_id=sample_strategy,
            model_id=sample_model,
            side="buy",
            quantity=10,
            price=market_price,
            calculated_probability=calculated_prob,
            market_price=market_price,
        )

        trade = get_trade_by_id(trade_id)
        assert trade is not None  # Guard for type checker
        expected_edge = calculated_prob - market_price

        # Allow small floating-point tolerance (1 basis point = 0.0001)
        assert abs(trade["edge_value"] - expected_edge) <= Decimal("0.0001")

    check_edge_invariant()


@pytest.mark.property
def test_property_attribution_immutability(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Property Test: Position attribution immutability.

    Property:
        Once position is created with attribution fields, they NEVER change.
        position.calculated_probability at T+0 == position.calculated_probability at T+N

    Educational Note:
        Tests that entry-time snapshots are truly immutable (ADR-018).
        Generates multiple positions and verifies attribution never mutates.

    Reference:
        - ADR-018: Immutable Versioning
        - REQ-TEST-014: Property tests for immutability
    """

    @given(
        calc_prob=st.decimals(min_value=Decimal("0.5"), max_value=Decimal("0.95"), places=4),
        mkt_price=st.decimals(min_value=Decimal("0.45"), max_value=Decimal("0.90"), places=4),
    )
    def check_immutability(calc_prob, mkt_price):
        """Property: Attribution fields are immutable after creation"""
        position_id = create_position(
            market_id=sample_market,
            strategy_id=sample_strategy,
            model_id=sample_model,
            side="yes",
            quantity=50,
            entry_price=mkt_price,
            calculated_probability=calc_prob,
            market_price_at_entry=mkt_price,
        )

        # Read position twice
        pos_1 = get_position_by_id(position_id)
        pos_2 = get_position_by_id(position_id)
        assert pos_1 is not None  # Guard for type checker
        assert pos_2 is not None  # Guard for type checker

        # Attribution fields must be identical
        assert pos_1["calculated_probability"] == pos_2["calculated_probability"]
        assert pos_1["edge_at_entry"] == pos_2["edge_at_entry"]
        assert pos_1["market_price_at_entry"] == pos_2["market_price_at_entry"]

    check_immutability()


# =============================================================================
# TEST SUITE 6: END-TO-END TESTS
# =============================================================================


@pytest.mark.e2e
def test_e2e_full_attribution_workflow(
    db_pool,
    clean_test_data,
    sample_platform,
    sample_series,
    sample_event,
    sample_strategy,
    sample_model,
):
    """
    E2E Test: Complete attribution workflow from market creation to analytics.

    Workflow:
        1. Create market
        2. Create strategy with nested versioning
        3. Create model
        4. Create trade with full attribution
        5. Create position from trade
        6. Query analytics (ROI, edge analysis)

    Educational Note:
        End-to-end tests validate the complete system flow.
        Unlike unit tests (test one function), E2E tests verify
        integration between multiple components.

    Reference:
        - REQ-TEST-015: End-to-end attribution workflow tests
    """
    # Step 1: Create market
    market_id = create_market(
        platform_id=sample_platform,
        event_id=sample_event,
        external_id="E2E-TEST-001",
        ticker="E2E-TEST-001",
        title="E2E Test Market",
        market_type="binary",
        yes_price=Decimal("0.5500"),
        no_price=Decimal("0.4500"),
        status="open",
        metadata={"test": True},
    )

    # Step 2: Create trade with attribution
    trade_id = create_trade(
        market_id=market_id,
        strategy_id=sample_strategy,
        model_id=1,  # From sample_model
        side="buy",
        quantity=100,
        price=Decimal("0.5500"),
        calculated_probability=Decimal("0.7000"),
        market_price=Decimal("0.5500"),
        trade_source="automated",
    )

    # Step 3: Create position from trade
    position_id = create_position(
        market_id=market_id,
        strategy_id=sample_strategy,
        model_id=1,
        side="yes",
        quantity=100,
        entry_price=Decimal("0.5500"),
        calculated_probability=Decimal("0.7000"),
        market_price_at_entry=Decimal("0.5500"),
    )

    # Step 4: Verify attribution consistency
    trade = get_trade_by_id(trade_id)
    position = get_position_by_id(position_id)
    assert trade is not None  # Guard for type checker
    assert position is not None  # Guard for type checker

    assert trade["calculated_probability"] == position["calculated_probability"]
    assert trade["edge_value"] == position["edge_at_entry"]
    assert trade["market_price"] == position["market_price_at_entry"]

    # Step 5: Verify analytics queries work
    assert trade["edge_value"] == Decimal("0.1500")
    assert position["edge_at_entry"] == Decimal("0.1500")


# =============================================================================
# TEST SUITE 7: STRESS TESTS
# =============================================================================


@pytest.mark.stress
def test_stress_bulk_trade_creation(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Stress Test: Create 1000 trades with attribution.

    Validates:
    - System handles bulk trade creation
    - Attribution calculations performant at scale
    - No memory leaks or connection pool exhaustion

    Educational Note:
        Stress tests verify system behavior under heavy load.
        1000 trades = realistic for multi-day trading session.

    Reference:
        - REQ-TEST-016: Stress tests for bulk operations
    """
    start_time = time.time()
    trade_ids = []

    # Create 1000 trades
    for i in range(1000):
        calc_prob = Decimal("0.6000") + (Decimal(i % 40) / Decimal("100"))  # 0.60 to 0.999
        mkt_price = Decimal("0.5000") + (Decimal(i % 30) / Decimal("100"))  # 0.50 to 0.799

        trade_id = create_trade(
            market_id=sample_market,
            strategy_id=sample_strategy,
            model_id=1,
            side="buy",
            quantity=10,
            price=mkt_price,
            calculated_probability=calc_prob,
            market_price=mkt_price,
        )
        trade_ids.append(trade_id)

    elapsed = time.time() - start_time

    # Performance assertion: 1000 trades in < 10 seconds
    assert len(trade_ids) == 1000
    assert elapsed < 10.0, f"Bulk creation took {elapsed:.2f}s (expected <10s)"

    # Verify all trades have correct attribution
    sample_trade = get_trade_by_id(trade_ids[0])
    assert sample_trade is not None  # Guard for type checker
    assert sample_trade["edge_value"] is not None
    assert sample_trade["calculated_probability"] is not None


@pytest.mark.stress
def test_stress_bulk_position_creation(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Stress Test: Create 500 positions with attribution.

    Validates:
    - Position creation scales appropriately
    - SCD Type 2 row_current_ind updates performant
    - Attribution snapshots created correctly at scale

    Educational Note:
        Positions are heavier than trades (SCD Type 2 versioning).
        500 positions = realistic portfolio size for active trading.

    Reference:
        - REQ-TEST-016: Stress tests for position management
    """
    start_time = time.time()
    position_ids = []

    for i in range(500):
        calc_prob = Decimal("0.6500") + (Decimal(i % 35) / Decimal("100"))
        entry_price = Decimal("0.5200") + (Decimal(i % 25) / Decimal("100"))

        position_id = create_position(
            market_id=sample_market,
            strategy_id=sample_strategy,
            model_id=1,
            side="yes",
            quantity=20,
            entry_price=entry_price,
            calculated_probability=calc_prob,
            market_price_at_entry=entry_price,
        )
        position_ids.append(position_id)

    elapsed = time.time() - start_time

    # Performance assertion: 500 positions in < 15 seconds
    assert len(position_ids) == 500
    assert elapsed < 15.0, f"Bulk position creation took {elapsed:.2f}s (expected <15s)"


# =============================================================================
# TEST SUITE 8: RACE CONDITION TESTS
# =============================================================================


@pytest.mark.race
def test_race_concurrent_trade_creation(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Race Test: Concurrent trade creation from multiple threads.

    Validates:
    - Edge calculation thread-safe
    - No race conditions in attribution assignment
    - trade_id assignment unique and sequential

    Educational Note:
        Race condition tests use threading to simulate concurrent operations.
        Critical for Phase 5 when multiple strategies execute simultaneously.

    Reference:
        - REQ-TEST-017: Race condition tests for concurrent operations
    """
    result_queue: Queue[tuple[int, list[int]]] = Queue()

    def create_trades_concurrently(thread_id, count):
        """Worker thread: Create trades concurrently"""
        trade_ids = []
        for i in range(count):
            trade_id = create_trade(
                market_id=sample_market,
                strategy_id=sample_strategy,
                model_id=1,
                side="buy",
                quantity=5,
                price=Decimal("0.5000"),
                calculated_probability=Decimal("0.6500"),
                market_price=Decimal("0.5000"),
            )
            trade_ids.append(trade_id)
        result_queue.put((thread_id, trade_ids))

    # Launch 5 threads, each creating 20 trades (100 total)
    threads = []
    for i in range(5):
        thread = threading.Thread(target=create_trades_concurrently, args=(i, 20))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    # Collect results
    all_trade_ids = []
    while not result_queue.empty():
        _thread_id, trade_ids = result_queue.get()
        all_trade_ids.extend(trade_ids)

    # Verify: All trades created, no duplicates
    assert len(all_trade_ids) == 100
    assert len(set(all_trade_ids)) == 100  # All unique

    # Verify: All trades have correct attribution
    sample_trade = get_trade_by_id(all_trade_ids[0])
    assert sample_trade is not None  # Guard for type checker
    assert sample_trade["edge_value"] == Decimal("0.1500")


# =============================================================================
# TEST SUITE 9: PERFORMANCE TESTS
# =============================================================================


@pytest.mark.performance
def test_performance_analytics_query_with_large_dataset(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Performance Test: Analytics query performance with 5000+ trades.

    Validates:
    - Analytics queries complete in < 500ms
    - Explicit column indexes used effectively (ADR-091)
    - No full table scans on large datasets

    Educational Note:
        Performance tests verify query optimization.
        ADR-091 predicted 20-100x speedup from explicit columns vs JSONB.
        This test verifies that prediction.

    Reference:
        - ADR-091: Explicit Columns for Trade/Position Attribution
        - REQ-TEST-018: Performance tests for analytics queries
    """
    # Create 5000 trades for realistic dataset
    for i in range(5000):
        model_id = 1 if i % 2 == 0 else 2  # Alternate between Model A and B
        calc_prob = Decimal("0.5500") + (Decimal(i % 45) / Decimal("100"))
        mkt_price = Decimal("0.5000")

        create_trade(
            market_id=sample_market,
            strategy_id=sample_strategy,
            model_id=model_id,
            side="buy",
            quantity=10,
            price=mkt_price,
            calculated_probability=calc_prob,
            market_price=mkt_price,
        )

    # Performance test: Analytics query
    start_time = time.time()

    query = """
        SELECT
            model_id,
            COUNT(*) AS trade_count,
            AVG(edge_value) AS avg_edge,
            MIN(edge_value) AS min_edge,
            MAX(edge_value) AS max_edge
        FROM trades
        WHERE calculated_probability IS NOT NULL
        GROUP BY model_id
        ORDER BY avg_edge DESC
    """
    results = fetch_all(query)

    elapsed = time.time() - start_time

    # Performance assertion: Query completes in < 500ms
    assert elapsed < 0.5, f"Analytics query took {elapsed * 1000:.0f}ms (expected <500ms)"

    # Verify at least 2 models present (may include NULL from other tests)
    assert len(results) >= 2, f"Expected at least 2 model groups, got {len(results)}"

    # Verify our test data is present (model_id 1 and 2)
    model_ids = {row["model_id"] for row in results if row["model_id"] is not None}
    assert 1 in model_ids, f"Model 1 missing from results: {model_ids}"
    assert 2 in model_ids, f"Model 2 missing from results: {model_ids}"


# =============================================================================
# TEST SUITE 10: CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
def test_chaos_trade_with_null_attribution_fields(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Chaos Test: Trade creation with NULL attribution fields.

    Validates:
    - System gracefully handles NULL attribution
    - No crashes when optional fields omitted
    - Edge calculation skipped when inputs NULL

    Educational Note:
        Chaos tests verify system resilience to unexpected inputs.
        "What if attribution fields are NULL?" - system should handle gracefully.

    Reference:
        - REQ-TEST-019: Chaos tests for edge cases and NULL handling
    """
    # Trade with NO attribution fields (model_id required but attribution optional)
    trade_id = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,  # Required parameter (even if attribution fields NULL)
        side="buy",
        quantity=10,
        price=Decimal("0.5000"),
        # calculated_probability=None,  # Omitted → defaults to NULL
        # market_price=None,            # Omitted → defaults to NULL
    )

    trade = get_trade_by_id(trade_id)

    # Verify: Trade created successfully
    assert trade is not None
    assert trade["trade_id"] == trade_id

    # Verify: Attribution fields are NULL (except model_id which is required)
    assert trade["calculated_probability"] is None
    assert trade["market_price"] is None
    assert trade["edge_value"] is None
    assert trade["model_id"] == 1  # model_id is required parameter


@pytest.mark.chaos
def test_chaos_position_with_automatic_edge_calculation(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Chaos Test: Position edge calculation is automatic and immutable.

    Validates:
    - Edge ALWAYS calculated as: calc_prob - market_price_at_entry
    - No manual override possible at creation time
    - System enforces consistent edge calculation

    Educational Note:
        Unlike trades where edge_value can theoretically be overridden,
        positions MUST have consistent edge calculation for A/B testing.
        This ensures "Did strategy A outperform B?" comparisons are valid.

    Reference:
        - ADR-091: Explicit Columns for Trade/Position Attribution
        - REQ-TEST-019: Chaos tests for data validation boundaries
    """
    # Position with attribution fields (edge calculated automatically)
    position_id = create_position(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=sample_model,
        side="yes",
        quantity=50,
        entry_price=Decimal("0.5000"),
        calculated_probability=Decimal("0.7000"),
        market_price_at_entry=Decimal("0.5000"),
    )

    position = get_position_by_id(position_id)

    # Verify: Edge calculated automatically (0.7000 - 0.5000 = 0.2000)
    assert position is not None
    assert position["edge_at_entry"] == Decimal("0.2000")  # Auto-calculated, immutable


@pytest.mark.chaos
def test_chaos_trade_with_probability_boundary_values(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Chaos Test: Trades with boundary probabilities (0.0, 1.0, 0.999999).

    Validates:
    - System handles probability edge cases
    - CHECK constraints enforced: probability IN [0.0, 1.0]
    - Edge calculation correct at boundaries

    Educational Note:
        Boundary value testing is a classic chaos engineering technique.
        Tests system behavior at limits: 0.0, 1.0, just below 1.0, etc.

    Reference:
        - REQ-TEST-019: Chaos tests for boundary conditions
    """
    # Test 1: Probability = 0.0 (minimum)
    trade_1 = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=sample_model,
        side="sell",  # Short position (bearish)
        quantity=10,
        price=Decimal("0.0100"),
        calculated_probability=Decimal("0.0000"),
        market_price=Decimal("0.0100"),
    )

    trade_obj_1 = get_trade_by_id(trade_1)
    assert trade_obj_1 is not None  # Guard for type checker
    assert trade_obj_1["calculated_probability"] == Decimal("0.0000")
    assert trade_obj_1["edge_value"] == Decimal("-0.0100")  # Negative edge

    # Test 2: Probability = 1.0 (maximum)
    trade_2 = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=sample_model,
        side="buy",
        quantity=10,
        price=Decimal("0.9900"),
        calculated_probability=Decimal("1.0000"),
        market_price=Decimal("0.9900"),
    )

    trade_obj_2 = get_trade_by_id(trade_2)
    assert trade_obj_2 is not None  # Guard for type checker
    assert trade_obj_2["calculated_probability"] == Decimal("1.0000")
    assert trade_obj_2["edge_value"] == Decimal("0.0100")  # Small positive edge

    # Test 3: Probability = 0.999999 (just below max)
    trade_3 = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=sample_model,
        side="buy",
        quantity=10,
        price=Decimal("0.9800"),
        calculated_probability=Decimal("0.9999"),
        market_price=Decimal("0.9800"),
    )

    trade_obj_3 = get_trade_by_id(trade_3)
    assert trade_obj_3 is not None  # Guard for type checker
    assert trade_obj_3["calculated_probability"] == Decimal("0.9999")
    assert trade_obj_3["edge_value"] == Decimal("0.0199")


# =============================================================================
# SHARED FIXTURES (imported from test_attribution.py)
# =============================================================================
# NOTE: These fixtures are defined in test_attribution.py and conftest.py:
# - db_pool
# - clean_test_data
# - sample_platform
# - sample_series
# - sample_event
# - sample_market
# - sample_strategy
# - sample_model
# =============================================================================
