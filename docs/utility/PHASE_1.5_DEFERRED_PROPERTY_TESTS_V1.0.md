# Phase 1.5+ Deferred Property Tests

---

**Version:** 1.0
**Created:** 2025-11-08
**Status:** ✅ Active
**Purpose:** Track property-based tests deferred to future phases due to dependencies or complexity
**Target Audience:** Development team, test planning

---

## Overview

This document tracks property-based tests that were identified during Phase 1.5 property testing implementation but deferred to future phases. Each deferred test includes rationale, target phase, priority, and estimated effort.

**Phase 1.5 Completion Status:**
- ✅ **Implemented:** 40 property tests across 3 test files
- ✅ **Target met:** Exceeded 35-test goal (114% completion)
- ⏸️ **Deferred:** 8 test categories deferred to future phases

**Deferral Strategy:**
- **Phase 1.5 Focus:** Core trading logic (Kelly, edge detection, configuration)
- **Phase 2+ Tests:** Require database, live data feeds, or complex integrations
- **Phase 3+ Tests:** Require async/concurrency infrastructure
- **Phase 4+ Tests:** Require ensemble models and backtesting framework

---

## Table of Contents

1. [Deferred Test Categories](#deferred-test-categories)
2. [Phase 1.5+ Tests (Database Required)](#phase-15-tests-database-required)
3. [Phase 2+ Tests (Live Data Required)](#phase-2-tests-live-data-required)
4. [Phase 3+ Tests (Async Infrastructure Required)](#phase-3-tests-async-infrastructure-required)
5. [Phase 4+ Tests (Ensemble Models Required)](#phase-4-tests-ensemble-models-required)
6. [Priority Matrix](#priority-matrix)
7. [Success Criteria](#success-criteria)

---

## Deferred Test Categories

| Category | Test Count | Target Phase | Priority | Blocker | Estimated Effort |
|----------|-----------|--------------|----------|---------|------------------|
| Database CRUD | 10-12 | 1.5 | 🔴 Critical | Database integration | 3-4 hours |
| Strategy Versioning | 8-10 | 1.5 | 🔴 Critical | Database schema | 2-3 hours |
| Position Lifecycle | 12-15 | 2 | 🟡 High | Live data + DB | 4-5 hours |
| Live Feed Integration | 8-10 | 2 | 🟡 High | ESPN/Kalshi feeds | 3-4 hours |
| Async Event Handling | 10-12 | 3 | 🟢 Medium | WebSocket infra | 4-5 hours |
| Concurrency Safety | 8-10 | 3 | 🔴 Critical | Async framework | 3-4 hours |
| Ensemble Predictions | 10-12 | 4 | 🟡 High | ML models | 5-6 hours |
| Backtesting Invariants | 8-10 | 4 | 🟢 Medium | Backtesting framework | 3-4 hours |
| **TOTAL** | **74-91** | **1.5-4** | **Mixed** | **Various** | **27-35 hours** |

---

## Phase 1.5+ Tests (Database Required)

### DEF-PROP-001: Database CRUD Property Tests

**Rationale:** CRUD operations must preserve invariants (Decimal precision, SCD Type-2, foreign keys).

**Target Phase:** 1.5 (Database Integration)

**Priority:** 🔴 Critical

**Estimated Effort:** 3-4 hours

**Dependencies:**
- Database connection established
- SQLAlchemy session management
- Test fixtures for database seeding

**Test Properties (10-12 tests):**

1. **Decimal Precision Preservation:**
   ```python
   @given(price=decimal_price(), quantity=st.integers(1, 1000))
   def test_crud_preserves_decimal_precision(db, price, quantity):
       """PROPERTY: Decimal values survive DB round-trip without float contamination."""
       trade = create_trade(price=price, quantity=quantity)
       retrieved = get_trade(trade.id)
       assert retrieved.price == price  # Exact Decimal equality
       assert isinstance(retrieved.price, Decimal)
   ```

2. **SCD Type-2 Current Row Uniqueness:**
   ```python
   @given(market_id=st.uuids())
   def test_only_one_current_row_per_market(db, market_id):
       """PROPERTY: At most ONE row can have row_current_ind=TRUE per market."""
       current_rows = query(Market).filter(
           Market.market_id == market_id,
           Market.row_current_ind == True
       ).all()
       assert len(current_rows) <= 1
   ```

3. **Foreign Key Integrity:**
   ```python
   @given(strategy_data=strategy_dict(), model_data=model_dict())
   def test_foreign_keys_never_orphan(db, strategy_data, model_data):
       """PROPERTY: Foreign keys always reference existing rows."""
       trade = create_trade(strategy_id=999999)  # Non-existent
       with pytest.raises(IntegrityError):
           db.commit()
   ```

4. **Timestamp Monotonicity:**
   ```python
   @given(events=st.lists(trade_event(), min_size=2, max_size=20))
   def test_timestamps_monotonically_increasing(db, events):
       """PROPERTY: created_at timestamps increase monotonically."""
       trades = [create_trade(e) for e in events]
       timestamps = [t.created_at for t in trades]
       assert timestamps == sorted(timestamps)
   ```

5. **Update Creates New SCD Row:**
   ```python
   @given(market_data=market_dict(), update_data=market_dict())
   def test_update_creates_new_scd_row(db, market_data, update_data):
       """PROPERTY: Updating SCD Type-2 table creates NEW row, marks old FALSE."""
       market = create_market(market_data)
       old_id = market.id

       update_market(market.market_id, update_data)

       old_row = get_market_by_id(old_id)
       assert old_row.row_current_ind == False

       current_rows = get_current_markets(market.market_id)
       assert len(current_rows) == 1
       assert current_rows[0].row_current_ind == True
       assert current_rows[0].id != old_id
   ```

6. **Decimal Column Type Safety:**
   ```python
   @given(invalid_price=st.floats())
   def test_decimal_columns_reject_float(db, invalid_price):
       """PROPERTY: Decimal columns reject float values (prevent contamination)."""
       with pytest.raises((TypeError, ValueError)):
           create_trade(price=invalid_price)  # float, not Decimal
   ```

7. **Cascade Delete Integrity:**
   ```python
   @given(strategy_id=st.uuids())
   def test_cascade_delete_removes_children(db, strategy_id):
       """PROPERTY: Deleting parent cascades to children (trades deleted with strategy)."""
       # NOT IMPLEMENTED - depends on cascade rules
       # Deferred until cascade delete strategy finalized (Phase 1.5)
   ```

8. **Unique Constraint Enforcement:**
   ```python
   @given(ticker=st.text(alphabet=st.characters(whitelist_categories=("Lu",)), min_size=3, max_size=20))
   def test_unique_constraints_enforced(db, ticker):
       """PROPERTY: Unique constraints prevent duplicates."""
       create_market(ticker=ticker)
       with pytest.raises(IntegrityError):
           create_market(ticker=ticker)  # Duplicate ticker
   ```

9. **Null Constraint Enforcement:**
   ```python
   @given(market_data=market_dict())
   def test_not_null_constraints_enforced(db, market_data):
       """PROPERTY: NOT NULL columns reject None values."""
       market_data["ticker"] = None  # Required field
       with pytest.raises(IntegrityError):
           create_market(market_data)
   ```

10. **Check Constraint Enforcement:**
    ```python
    @given(invalid_status=st.text().filter(lambda s: s not in ["open", "closed", "settled"]))
    def test_check_constraints_enforced(db, invalid_status):
        """PROPERTY: CHECK constraints reject invalid enum values."""
        with pytest.raises(IntegrityError):
            create_market(status=invalid_status)
    ```

**Success Metrics:**
- ✅ All 10 tests pass with 100 examples each
- ✅ Zero Decimal → float contamination detected
- ✅ SCD Type-2 invariants hold across all scenarios
- ✅ Foreign key integrity maintained
- ✅ Database constraints enforced

---

### DEF-PROP-002: Strategy Versioning Property Tests

**Rationale:** Strategy version immutability is CRITICAL for A/B testing and trade attribution.

**Target Phase:** 1.5 (Database Integration)

**Priority:** 🔴 Critical

**Estimated Effort:** 2-3 hours

**Dependencies:**
- Strategy table implemented
- Version creation workflow
- Trade attribution logic

**Test Properties (8-10 tests):**

1. **Config Immutability:**
   ```python
   @given(config=strategy_config_dict())
   def test_strategy_config_immutable(db, config):
       """PROPERTY: Strategy config NEVER changes after creation."""
       strategy = create_strategy(version="v1.0", config=config)
       original_config = strategy.config.copy()

       # Attempt to modify (should fail)
       with pytest.raises(ImmutableConfigError):
           strategy.config = {"min_lead": 20}  # Different config

       # Verify unchanged
       assert strategy.config == original_config
   ```

2. **Status Mutability:**
   ```python
   @given(status_sequence=st.lists(
       st.sampled_from(["draft", "testing", "active", "deprecated"]),
       min_size=2, max_size=5
   ))
   def test_strategy_status_mutable(db, status_sequence):
       """PROPERTY: Strategy status CAN change (draft → testing → active → deprecated)."""
       strategy = create_strategy(status="draft")

       for new_status in status_sequence:
           strategy.status = new_status
           db.commit()
           assert strategy.status == new_status
   ```

3. **Version Uniqueness:**
   ```python
   @given(version=semver_string())
   def test_strategy_version_unique(db, version):
       """PROPERTY: Strategy (name, version) combinations are unique."""
       create_strategy(name="halftime_entry", version=version)

       with pytest.raises(IntegrityError):
           create_strategy(name="halftime_entry", version=version)  # Duplicate
   ```

4. **Semantic Versioning:**
   ```python
   @given(versions=st.lists(semver_string(), min_size=3, max_size=10, unique=True))
   def test_semantic_versioning_ordering(versions):
       """PROPERTY: Semantic versions sort correctly (v1.0 < v1.1 < v2.0)."""
       sorted_versions = sorted(versions, key=lambda v: Version(v))

       for i in range(len(sorted_versions) - 1):
           v1 = Version(sorted_versions[i])
           v2 = Version(sorted_versions[i + 1])
           assert v1 < v2
   ```

5. **Trade Attribution Integrity:**
   ```python
   @given(trades=st.lists(trade_dict(), min_size=10, max_size=100))
   def test_all_trades_attributed_to_versions(db, trades):
       """PROPERTY: Every trade MUST link to a specific strategy version."""
       created_trades = [create_trade(t) for t in trades]

       for trade in created_trades:
           assert trade.strategy_id is not None
           strategy = get_strategy(trade.strategy_id)
           assert strategy is not None
           assert strategy.strategy_version is not None
   ```

6. **Config Change Requires New Version:**
   ```python
   @given(original_config=strategy_config_dict(), new_config=strategy_config_dict())
   def test_config_change_creates_new_version(db, original_config, new_config):
       """PROPERTY: Changing config requires creating NEW version, not modifying existing."""
       assume(original_config != new_config)  # Configs differ

       v1_0 = create_strategy(version="v1.0", config=original_config)

       # Can't modify v1.0's config
       with pytest.raises(ImmutableConfigError):
           v1_0.config = new_config

       # Must create v1.1
       v1_1 = create_strategy(version="v1.1", config=new_config)
       assert v1_1.config == new_config
       assert v1_0.config == original_config  # Unchanged
   ```

7. **Active Version Uniqueness:**
   ```python
   @given(strategy_name=st.text(min_size=3, max_size=30))
   def test_at_most_one_active_version(db, strategy_name):
       """PROPERTY: At most ONE version of a strategy can be 'active' simultaneously."""
       # Create multiple versions
       v1_0 = create_strategy(name=strategy_name, version="v1.0", status="active")
       v1_1 = create_strategy(name=strategy_name, version="v1.1", status="testing")

       # Activating v1.1 should deprecate v1.0 (or raise error)
       v1_1.status = "active"
       db.commit()

       active_versions = query(Strategy).filter(
           Strategy.strategy_name == strategy_name,
           Strategy.status == "active"
       ).all()

       assert len(active_versions) <= 1
   ```

8. **Version History Preservation:**
   ```python
   @given(num_versions=st.integers(1, 10))
   def test_all_versions_preserved(db, num_versions):
       """PROPERTY: Historical versions remain in database (never deleted)."""
       strategy_name = "halftime_entry"

       for i in range(num_versions):
           create_strategy(name=strategy_name, version=f"v1.{i}")

       all_versions = query(Strategy).filter(
           Strategy.strategy_name == strategy_name
       ).all()

       assert len(all_versions) == num_versions
   ```

**Success Metrics:**
- ✅ Config immutability enforced (cannot modify after creation)
- ✅ Status mutability verified (draft → testing → active → deprecated)
- ✅ Version uniqueness maintained
- ✅ Trade attribution integrity preserved
- ✅ No orphaned trades (all link to valid versions)

---

## Phase 2+ Tests (Live Data Required)

### DEF-PROP-003: Position Lifecycle Property Tests

**Rationale:** Position transitions must preserve invariants (P&L accuracy, state machine logic).

**Target Phase:** 2 (Live Data Integration)

**Priority:** 🟡 High

**Estimated Effort:** 4-5 hours

**Dependencies:**
- Live Kalshi API integration
- Position monitoring system
- Exit evaluation logic

**Test Properties (12-15 tests):**

1. **P&L Calculation Accuracy:**
   ```python
   @given(entry_price=decimal_price(0.01, 0.99), exit_price=decimal_price(0.01, 0.99), quantity=st.integers(1, 1000))
   def test_pnl_calculation_accuracy(entry_price, exit_price, quantity):
       """PROPERTY: P&L = (exit_price - entry_price) * quantity (exact Decimal math)."""
       expected_pnl = (exit_price - entry_price) * quantity
       calculated_pnl = calculate_pnl(entry_price, exit_price, quantity)
       assert calculated_pnl == expected_pnl
   ```

2. **Position State Machine:**
   ```python
   @given(state_transitions=st.lists(
       st.sampled_from(["pending", "open", "closing", "closed"]),
       min_size=2, max_size=5
   ))
   def test_position_state_machine_valid_transitions(state_transitions):
       """PROPERTY: Position transitions follow valid state machine paths."""
       valid_transitions = {
           "pending": ["open", "cancelled"],
           "open": ["closing", "stopped_out"],
           "closing": ["closed"],
           "closed": [],  # Terminal state
       }

       position = create_position(state="pending")

       for next_state in state_transitions:
           current_state = position.state
           if next_state in valid_transitions[current_state]:
               position.transition_to(next_state)
               assert position.state == next_state
           else:
               with pytest.raises(InvalidStateTransitionError):
                   position.transition_to(next_state)
   ```

3. **Stop-Loss Triggers:**
   ```python
   @given(entry_price=decimal_price(0.30, 0.70), loss_threshold=st.decimals(0.10, 0.50, places=2))
   def test_stop_loss_triggers_at_threshold(entry_price, loss_threshold):
       """PROPERTY: Position exits when loss >= threshold."""
       position = create_position(entry_price=entry_price, loss_threshold_pct=loss_threshold)

       # Price moves against position
       stop_loss_price = entry_price * (Decimal("1") - loss_threshold)
       current_price = stop_loss_price - Decimal("0.01")  # Breach threshold

       should_exit = evaluate_stop_loss(position, current_price)
       assert should_exit == True
   ```

4. **Profit Target Triggers:**
   ```python
   @given(entry_price=decimal_price(0.30, 0.70), gain_threshold=st.decimals(0.10, 2.00, places=2))
   def test_profit_target_triggers_at_threshold(entry_price, gain_threshold):
       """PROPERTY: Position exits when profit >= threshold."""
       position = create_position(entry_price=entry_price, gain_threshold_pct=gain_threshold)

       # Price moves in favor
       profit_target_price = entry_price * (Decimal("1") + gain_threshold)
       current_price = profit_target_price + Decimal("0.01")  # Reach target

       should_exit = evaluate_profit_target(position, current_price)
       assert should_exit == True
   ```

5. **Trailing Stop Activation:**
   ```python
   @given(entry_price=decimal_price(), activation_threshold=st.decimals(0.05, 0.20, places=2))
   def test_trailing_stop_activates_at_threshold(entry_price, activation_threshold):
       """PROPERTY: Trailing stop activates when profit >= activation_threshold."""
       position = create_position(entry_price=entry_price, trailing_stop_activation=activation_threshold)

       # Price moves enough to activate
       activation_price = entry_price * (Decimal("1") + activation_threshold)
       position.update_price(activation_price)

       assert position.trailing_stop_active == True
       assert position.trailing_stop_price == activation_price
   ```

6. **Edge Erosion Monitoring:**
   ```python
   @given(true_prob=probability(), market_price=probability(), fee=decimal_price(0.00, 0.10))
   def test_edge_recalculated_on_price_update(true_prob, market_price, fee):
       """PROPERTY: Edge = true_prob - market_price - fee (recalculated on every update)."""
       position = create_position(true_probability=true_prob)

       expected_edge = true_prob - market_price - fee
       position.update_price(market_price)

       assert position.current_edge == expected_edge
   ```

7. **Position Correlation Limits:**
   ```python
   @given(correlations=st.lists(st.decimals(0.0, 1.0, places=2), min_size=5, max_size=20))
   def test_high_correlation_rejects_new_position(portfolio, correlations):
       """PROPERTY: New positions rejected if correlation with existing positions > threshold."""
       max_correlation = Decimal("0.85")

       for corr in correlations:
           if corr > max_correlation:
               with pytest.raises(HighCorrelationError):
                   portfolio.add_position(correlation=corr)
           else:
               portfolio.add_position(correlation=corr)
   ```

8. **Position Sizing Constraints:**
   ```python
   @given(kelly_frac=kelly_fraction_value(), edge=st.decimals(0.01, 0.30, places=2), bankroll=st.decimals(1000, 100000, places=2))
   def test_position_size_never_exceeds_max(kelly_frac, edge, bankroll):
       """PROPERTY: Position size <= min(kelly_size, max_position_dollars, max_position_pct * bankroll)."""
       kelly_size = calculate_kelly_size(kelly_frac, edge, bankroll)
       max_position_dollars = Decimal("500.00")
       max_position_pct = Decimal("0.05")
       max_pct_size = bankroll * max_position_pct

       actual_size = calculate_position_size(kelly_frac, edge, bankroll, max_position_dollars, max_position_pct)

       assert actual_size <= kelly_size
       assert actual_size <= max_position_dollars
       assert actual_size <= max_pct_size
   ```

**Success Metrics:**
- ✅ P&L calculations exact (Decimal precision)
- ✅ State machine transitions valid
- ✅ Stop-loss/profit targets trigger correctly
- ✅ Trailing stops activate and tighten properly
- ✅ Edge recalculated accurately on price updates
- ✅ Correlation limits enforced
- ✅ Position sizing constraints respected

---

### DEF-PROP-004: Live Feed Integration Property Tests

**Rationale:** ESPN/Kalshi feed parsing must preserve data integrity and handle edge cases.

**Target Phase:** 2 (Live Data Integration)

**Priority:** 🟡 High

**Estimated Effort:** 3-4 hours

**Dependencies:**
- ESPN API client
- Kalshi WebSocket integration
- Feed parsing logic

**Test Properties (8-10 tests):**

1. **ESPN Score Parsing:**
   ```python
   @given(raw_score=st.text())
   def test_espn_score_parsing_robust(raw_score):
       """PROPERTY: ESPN score parser handles all input formats without crashing."""
       try:
           score = parse_espn_score(raw_score)
           assert isinstance(score, int)
           assert score >= 0
       except InvalidScoreFormatError:
           # Expected for invalid formats
           pass
   ```

2. **Kalshi Price Decimal Conversion:**
   ```python
   @given(kalshi_price_str=st.text(alphabet=st.characters(whitelist_categories=("Nd", "Po")), min_size=1, max_size=10))
   def test_kalshi_price_converts_to_decimal(kalshi_price_str):
       """PROPERTY: Kalshi price strings → Decimal (never float)."""
       try:
           price = parse_kalshi_price(kalshi_price_str)
           assert isinstance(price, Decimal)
           assert Decimal("0.0000") <= price <= Decimal("1.0000")
       except ValueError:
           # Expected for non-numeric strings
           pass
   ```

3. **Feed Timestamp Monotonicity:**
   ```python
   @given(events=st.lists(feed_event(), min_size=10, max_size=100))
   def test_feed_events_arrive_in_order(events):
       """PROPERTY: Feed events have monotonically increasing timestamps."""
       timestamps = [parse_timestamp(e["timestamp"]) for e in events]
       assert timestamps == sorted(timestamps)
   ```

4. **Market Data Completeness:**
   ```python
   @given(market_data=kalshi_market_response())
   def test_market_data_has_required_fields(market_data):
       """PROPERTY: Kalshi market responses contain all required fields."""
       required_fields = ["ticker", "yes_bid", "yes_ask", "no_bid", "no_ask", "status"]

       for field in required_fields:
           assert field in market_data, f"Missing required field: {field}"
   ```

5. **Duplicate Event Deduplication:**
   ```python
   @given(events=st.lists(feed_event(), min_size=5, max_size=20))
   def test_duplicate_events_deduplicated(events):
       """PROPERTY: Duplicate feed events (same event_id) deduplicated."""
       # Add some duplicates
       duplicates = events[:3]
       events_with_dupes = events + duplicates

       deduplicated = deduplicate_feed_events(events_with_dupes)
       unique_ids = {e["event_id"] for e in deduplicated}

       assert len(deduplicated) == len(unique_ids)
   ```

**Success Metrics:**
- ✅ Feed parsing robust to malformed input
- ✅ All prices converted to Decimal
- ✅ Timestamps monotonic
- ✅ Required fields validated
- ✅ Duplicates deduplicated

---

## Phase 3+ Tests (Async Infrastructure Required)

### DEF-PROP-005: Async Event Handling Property Tests

**Rationale:** WebSocket event handling must preserve ordering and handle concurrency correctly.

**Target Phase:** 3 (Async Processing)

**Priority:** 🟢 Medium

**Estimated Effort:** 4-5 hours

**Dependencies:**
- WebSocket infrastructure
- Async event loop
- Message queue

**Test Properties (10-12 tests):**

1. **Event Ordering Preservation:**
   ```python
   @given(events=st.lists(websocket_event(), min_size=10, max_size=100))
   async def test_events_processed_in_order(events):
       """PROPERTY: Events processed in arrival order (FIFO)."""
       queue = EventQueue()

       for event in events:
           await queue.put(event)

       processed = []
       while not queue.empty():
           processed.append(await queue.get())

       assert processed == events
   ```

2. **No Message Loss:**
   ```python
   @given(events=st.lists(websocket_event(), min_size=50, max_size=200))
   async def test_no_message_loss_under_load(events):
       """PROPERTY: All messages processed, zero loss (even under high load)."""
       handler = WebSocketHandler()

       # Send all events concurrently
       await asyncio.gather(*[handler.handle(e) for e in events])

       processed_count = handler.get_processed_count()
       assert processed_count == len(events)
   ```

3. **Backpressure Handling:**
   ```python
   @given(event_rate=st.integers(100, 1000), processing_rate=st.integers(50, 500))
   async def test_backpressure_prevents_memory_overflow(event_rate, processing_rate):
       """PROPERTY: Backpressure prevents unbounded memory growth."""
       assume(event_rate > processing_rate)  # Producer faster than consumer

       queue = BoundedEventQueue(max_size=1000)

       # Simulate high-rate producer
       async def producer():
           for i in range(5000):
               await queue.put({"id": i})
               await asyncio.sleep(1 / event_rate)

       # Simulate slow consumer
       async def consumer():
           while True:
               await queue.get()
               await asyncio.sleep(1 / processing_rate)

       # Run for limited time
       await asyncio.wait_for(
           asyncio.gather(producer(), consumer()),
           timeout=10.0
       )

       # Queue size should never exceed max_size
       assert queue.size() <= queue.max_size
   ```

**Success Metrics:**
- ✅ Event ordering preserved
- ✅ Zero message loss
- ✅ Backpressure prevents overflow
- ✅ Async tasks don't deadlock

---

### DEF-PROP-006: Concurrency Safety Property Tests

**Rationale:** Thread-safe data structures and race condition prevention.

**Target Phase:** 3 (Async Processing)

**Priority:** 🔴 Critical

**Estimated Effort:** 3-4 hours

**Dependencies:**
- Async infrastructure
- Shared state management
- Lock-free data structures

**Test Properties (8-10 tests):**

1. **Race-Free Counter Increment:**
   ```python
   @given(num_tasks=st.integers(10, 100), increments_per_task=st.integers(100, 1000))
   async def test_concurrent_counter_increment_safe(num_tasks, increments_per_task):
       """PROPERTY: Concurrent increments never lose updates (no race conditions)."""
       counter = ThreadSafeCounter()

       async def increment_task():
           for _ in range(increments_per_task):
               counter.increment()

       await asyncio.gather(*[increment_task() for _ in range(num_tasks)])

       expected = num_tasks * increments_per_task
       assert counter.value == expected
   ```

2. **Deadlock Freedom:**
   ```python
   @given(num_resources=st.integers(3, 10), num_tasks=st.integers(10, 50))
   async def test_resource_acquisition_deadlock_free(num_resources, num_tasks):
       """PROPERTY: Resource acquisition never deadlocks (ordered locking)."""
       resources = [Resource(i) for i in range(num_resources)]

       async def task():
           # Acquire resources in sorted order (prevents circular wait)
           acquired = sorted(random.sample(resources, k=min(3, num_resources)))
           for resource in acquired:
               await resource.acquire()

           # Simulate work
           await asyncio.sleep(0.01)

           # Release in reverse order
           for resource in reversed(acquired):
               resource.release()

       # All tasks should complete without deadlock
       await asyncio.wait_for(
           asyncio.gather(*[task() for _ in range(num_tasks)]),
           timeout=10.0
       )
   ```

**Success Metrics:**
- ✅ No race conditions
- ✅ No deadlocks
- ✅ Thread-safe data structures
- ✅ Atomic operations correct

---

## Phase 4+ Tests (Ensemble Models Required)

### DEF-PROP-007: Ensemble Prediction Property Tests

**Rationale:** Ensemble predictions must maintain mathematical properties (weighted averages, calibration).

**Target Phase:** 4 (Odds Detection & Ensemble)

**Priority:** 🟡 High

**Estimated Effort:** 5-6 hours

**Dependencies:**
- Ensemble model architecture
- Individual model implementations
- Backtesting framework

**Test Properties (10-12 tests):**

1. **Weighted Average Invariant:**
   ```python
   @given(
       predictions=st.lists(probability(), min_size=3, max_size=10),
       weights=st.lists(st.decimals(0.1, 1.0, places=2), min_size=3, max_size=10)
   )
   def test_ensemble_is_weighted_average(predictions, weights):
       """PROPERTY: Ensemble prediction = weighted average of individual predictions."""
       assume(len(predictions) == len(weights))

       # Normalize weights
       total_weight = sum(weights)
       normalized_weights = [w / total_weight for w in weights]

       ensemble_pred = ensemble_predict(predictions, normalized_weights)

       expected = sum(p * w for p, w in zip(predictions, normalized_weights))
       assert abs(ensemble_pred - expected) < Decimal("0.0001")
   ```

2. **Calibration Invariant:**
   ```python
   @given(
       predictions=st.lists(probability(), min_size=100, max_size=1000),
       outcomes=st.lists(st.booleans(), min_size=100, max_size=1000)
   )
   def test_ensemble_calibration_error_bounds(predictions, outcomes):
       """PROPERTY: Well-calibrated ensemble has low Expected Calibration Error (ECE)."""
       assume(len(predictions) == len(outcomes))

       ece = calculate_expected_calibration_error(predictions, outcomes, num_bins=10)

       # Well-calibrated model: ECE < 0.05
       assert ece < Decimal("0.05")
   ```

3. **Probability Bounds:**
   ```python
   @given(predictions=st.lists(st.decimals(-0.5, 1.5, places=4), min_size=3, max_size=10))
   def test_ensemble_predictions_in_valid_range(predictions):
       """PROPERTY: Ensemble predictions always in [0, 1] even if inputs invalid."""
       # Clamp invalid predictions
       clamped = [max(Decimal("0"), min(Decimal("1"), p)) for p in predictions]

       ensemble_pred = ensemble_predict(clamped, equal_weights(len(clamped)))

       assert Decimal("0") <= ensemble_pred <= Decimal("1")
   ```

**Success Metrics:**
- ✅ Weighted averages correct
- ✅ Calibration error < 5%
- ✅ Predictions in [0, 1]
- ✅ Ensemble outperforms individual models

---

### DEF-PROP-008: Backtesting Invariants Property Tests

**Rationale:** Backtesting must prevent lookahead bias and maintain temporal integrity.

**Target Phase:** 4 (Odds Detection & Ensemble)

**Priority:** 🟢 Medium

**Estimated Effort:** 3-4 hours

**Dependencies:**
- Backtesting framework
- Historical data loader
- Performance metrics

**Test Properties (8-10 tests):**

1. **No Lookahead Bias:**
   ```python
   @given(
       historical_data=st.lists(market_snapshot(), min_size=100, max_size=500),
       prediction_window=st.integers(1, 10)
   )
   def test_backtesting_no_lookahead_bias(historical_data, prediction_window):
       """PROPERTY: Backtest predictions only use data available at prediction time."""
       for i in range(len(historical_data) - prediction_window):
           past_data = historical_data[:i+1]
           future_data = historical_data[i+1:i+1+prediction_window]

           prediction = backtest_predict(past_data)

           # Verify prediction doesn't use future data
           # (Check that model inputs only come from past_data)
           model_inputs = extract_model_inputs(past_data)
           assert all(inp in past_data for inp in model_inputs)
   ```

2. **Temporal Ordering:**
   ```python
   @given(trades=st.lists(trade_event(), min_size=50, max_size=200))
   def test_backtest_trades_chronological(trades):
       """PROPERTY: Backtested trades execute in chronological order."""
       backtest_results = run_backtest(trades)

       trade_timestamps = [t.timestamp for t in backtest_results.trades]
       assert trade_timestamps == sorted(trade_timestamps)
   ```

3. **Realistic Execution:**
   ```python
   @given(
       order_size=st.integers(10, 500),
       available_liquidity=st.integers(5, 1000)
   )
   def test_backtest_respects_liquidity_constraints(order_size, available_liquidity):
       """PROPERTY: Backtest execution respects market liquidity (can't fill >liquidity)."""
       filled_size = simulate_order_fill(order_size, available_liquidity)

       assert filled_size <= available_liquidity
       assert filled_size <= order_size
   ```

**Success Metrics:**
- ✅ No lookahead bias detected
- ✅ Temporal ordering preserved
- ✅ Realistic execution constraints
- ✅ Backtest P&L matches forward test

---

## Priority Matrix

| Priority | Test Categories | Total Tests | Target Phases | Blocking For |
|----------|----------------|-------------|---------------|--------------|
| 🔴 Critical | Database CRUD, Strategy Versioning, Concurrency Safety | 26-32 | 1.5, 3 | Phase 2+ |
| 🟡 High | Position Lifecycle, Live Feed Integration, Ensemble Predictions | 30-37 | 2, 4 | Phase 3+ |
| 🟢 Medium | Async Event Handling, Backtesting Invariants | 18-22 | 3, 4 | Phase 5+ |

**Implementation Priority:**

1. **Phase 1.5 (Immediate):**
   - DEF-PROP-001: Database CRUD (🔴 Critical)
   - DEF-PROP-002: Strategy Versioning (🔴 Critical)

2. **Phase 2 (Next):**
   - DEF-PROP-003: Position Lifecycle (🟡 High)
   - DEF-PROP-004: Live Feed Integration (🟡 High)

3. **Phase 3 (After live data):**
   - DEF-PROP-006: Concurrency Safety (🔴 Critical)
   - DEF-PROP-005: Async Event Handling (🟢 Medium)

4. **Phase 4 (Final):**
   - DEF-PROP-007: Ensemble Predictions (🟡 High)
   - DEF-PROP-008: Backtesting Invariants (🟢 Medium)

---

## Success Criteria

### Overall Success Metrics

**Coverage:**
- ✅ **Phase 1.5:** 18-22 property tests (Database + Versioning)
- ✅ **Phase 2:** +16-20 property tests (Position + Live Feed)
- ✅ **Phase 3:** +18-22 property tests (Async + Concurrency)
- ✅ **Phase 4:** +18-22 property tests (Ensemble + Backtesting)
- ✅ **Total:** 70-86 additional property tests across phases

**Quality:**
- ✅ **100 examples per test:** All property tests run with Hypothesis max_examples=100
- ✅ **Zero flake:** Property tests deterministic (same seed → same result)
- ✅ **Fast execution:** <5 seconds per test file
- ✅ **Clear failure messages:** Educational error output on failure

**Integration:**
- ✅ **CI/CD:** All property tests run in CI pipeline
- ✅ **Pre-push hooks:** Property tests run locally before push
- ✅ **Coverage tracking:** Property test coverage >= 85%

### Phase-Specific Success Criteria

**Phase 1.5 (Database Integration):**
- ✅ 18-22 property tests passing
- ✅ Decimal precision verified across all CRUD operations
- ✅ SCD Type-2 invariants enforced
- ✅ Strategy config immutability proven
- ✅ Trade attribution integrity maintained

**Phase 2 (Live Data Integration):**
- ✅ 16-20 property tests passing
- ✅ P&L calculations exact (Decimal precision)
- ✅ Position state machine validated
- ✅ Feed parsing robust to malformed input
- ✅ Edge recalculation accurate

**Phase 3 (Async Processing):**
- ✅ 18-22 property tests passing
- ✅ Event ordering preserved
- ✅ Zero message loss under load
- ✅ No race conditions detected
- ✅ No deadlocks observed

**Phase 4 (Ensemble & Backtesting):**
- ✅ 18-22 property tests passing
- ✅ Ensemble predictions mathematically correct
- ✅ Calibration error < 5%
- ✅ No lookahead bias in backtesting
- ✅ Realistic execution constraints

---

## Conclusion

This document provides a comprehensive roadmap for 74-91 additional property tests across Phases 1.5-4. By deferring these tests strategically, we:

1. **Avoid Premature Complexity:** Don't build test infrastructure for features not yet implemented
2. **Maintain Momentum:** Focus Phase 1.5 on core trading logic (40 tests complete)
3. **Plan Systematically:** Each deferred test has clear rationale, dependencies, and success criteria
4. **Ensure Completeness:** 110-131 total property tests when all phases complete

**Next Steps:**
1. Implement DEF-PROP-001 (Database CRUD) in Phase 1.5
2. Implement DEF-PROP-002 (Strategy Versioning) in Phase 1.5
3. Review deferred test plan with user
4. Update test plan as new requirements emerge

---

**END OF PHASE_1.5_DEFERRED_PROPERTY_TESTS_V1.0.md**
