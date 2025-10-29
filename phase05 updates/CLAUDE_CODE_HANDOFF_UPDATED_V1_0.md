# Phase 0.5 Progress Summary for Claude Code
**Date:** 2025-10-21  
**Session:** Position Monitoring & Exit Management Design Complete  
**Status:** Ready for Documentation Updates + Phase 5 Specifications Added

---

## Quick Context

You're working through Phase 0.5 tasks. This session completed three major design specifications for Phase 5 position monitoring and exit management. These need to be integrated into project documentation alongside the existing ADR-020, ADR-021, and Phase 8 advanced execution work.

---

## New Deliverables (This Session)

### 1. PHASE_5_POSITION_MONITORING_SPEC_V1_0.md

**Purpose:** Complete specification for position monitoring system

**Key Contents:**
- PositionMonitor class (async loop architecture)
- Dynamic monitoring frequency (30s normal, 5s urgent)
- Rate limit management (API call throttling)
- Price caching strategy (10s TTL)
- Trailing stop updates
- Real-time P&L tracking
- Integration with ExitEvaluator and ExitExecutor

**Implementation Scope:** Phase 5a

**Database Changes Required:**
```sql
ALTER TABLE positions ADD COLUMN current_price DECIMAL(10,4);
ALTER TABLE positions ADD COLUMN unrealized_pnl DECIMAL(10,2);
ALTER TABLE positions ADD COLUMN unrealized_pnl_pct DECIMAL(6,4);
ALTER TABLE positions ADD COLUMN last_update TIMESTAMP;
ALTER TABLE positions ADD COLUMN trailing_stop_active BOOLEAN;
ALTER TABLE positions ADD COLUMN peak_price DECIMAL(10,4);
ALTER TABLE positions ADD COLUMN trailing_stop_price DECIMAL(10,4);
ALTER TABLE positions ADD COLUMN exit_reason VARCHAR(50);
ALTER TABLE positions ADD COLUMN exit_priority VARCHAR(20);
```

**Configuration Updates Required:**
```yaml
# position_management.yaml additions
monitoring:
  normal_frequency: 30
  urgent_frequency: 5
  urgent_conditions:
    near_stop_loss_pct: 0.02
    near_profit_target_pct: 0.02
    near_trailing_stop_pct: 0.02
  price_cache_ttl_seconds: 10
  max_api_calls_per_minute: 60
```

---

### 2. PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md

**Purpose:** Complete specification for exit condition evaluation and execution

**Key Contents:**
- Exit condition hierarchy (CRITICAL > HIGH > MEDIUM > LOW)
- 10 exit conditions (removed edge_reversal as redundant)
- Priority-based conflict resolution
- ExitEvaluator class implementation
- ExitExecutor class with urgency-based strategies
- Failed exit handling with progressive escalation
- Partial exit support

**Major Design Decision:** Removed `edge_reversal` exit condition as redundant with existing `early_exit` (absolute threshold) and `edge_disappeared` (negative edge) conditions.

**Exit Conditions (Final List):**

**CRITICAL (Priority 1):**
- stop_loss: Hard stop loss hit → Market order
- circuit_breaker: Daily loss limit → Market order all positions

**HIGH (Priority 2):**
- trailing_stop: Trailing stop hit → Aggressive limit
- time_based_urgent: <5 min to settlement → Aggressive limit
- liquidity_dried_up: Spread >3¢ or volume <50 → Aggressive limit

**MEDIUM (Priority 3):**
- profit_target: Target reached → Fair limit
- partial_exit_target: Partial exit threshold → Fair limit

**LOW (Priority 4):**
- early_exit: Edge < 2% threshold → Conservative limit
- edge_disappeared: Edge turned negative → Fair limit
- rebalance: Better opportunity exists → Conservative limit

**Database Changes Required:**
```sql
CREATE TABLE position_exits (
    exit_id SERIAL PRIMARY KEY,
    position_id INT REFERENCES positions(position_id),
    exit_reason VARCHAR(50) NOT NULL,
    exit_priority VARCHAR(20) NOT NULL,
    exit_quantity INT NOT NULL,
    partial_exit BOOLEAN DEFAULT FALSE,
    exit_price DECIMAL(10,4) NOT NULL,
    execution_strategy VARCHAR(20),
    unrealized_pnl DECIMAL(10,2),
    unrealized_pnl_pct DECIMAL(6,4),
    triggered_at TIMESTAMP DEFAULT NOW(),
    executed_at TIMESTAMP
);

CREATE TABLE exit_attempts (
    attempt_id SERIAL PRIMARY KEY,
    position_id INT REFERENCES positions(position_id),
    exit_id INT REFERENCES position_exits(exit_id),
    attempt_number INT NOT NULL,
    order_type VARCHAR(20),
    limit_price DECIMAL(10,4),
    quantity INT NOT NULL,
    status VARCHAR(20),
    filled_quantity INT DEFAULT 0,
    placed_at TIMESTAMP DEFAULT NOW()
);
```

---

### 3. PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md

**Purpose:** Complete architectural overview of trading event loop

**Key Contents:**
- Entry flow detailed (edge → risk → execute → monitor)
- Monitoring flow detailed (async loop with exit evaluation)
- Exit flow detailed (condition → evaluation → execution)
- Component interaction diagrams
- State transition diagrams
- Error handling and circuit breakers
- Comprehensive flowcharts (ASCII art)

**Use Case:** Reference document for understanding complete system architecture

---

## Configuration Updates Needed

### position_management.yaml Updates

**Add these sections:**

```yaml
# Monitoring configuration
monitoring:
  normal_frequency: 30      # seconds
  urgent_frequency: 5       # seconds
  urgent_conditions:
    near_stop_loss_pct: 0.02
    near_profit_target_pct: 0.02
    near_trailing_stop_pct: 0.02
  price_cache_ttl_seconds: 10
  max_api_calls_per_minute: 60

# Exit priorities (explicit hierarchy)
exit_priorities:
  CRITICAL:
    - stop_loss
    - circuit_breaker
  HIGH:
    - trailing_stop
    - time_based_urgent
    - liquidity_dried_up
  MEDIUM:
    - profit_target
    - partial_exit_target
  LOW:
    - early_exit
    - edge_disappeared
    - rebalance

# Exit execution strategies by priority
exit_execution:
  CRITICAL:
    order_type: market
    timeout_seconds: 5
    retry_strategy: immediate_market
  
  HIGH:
    order_type: limit
    price_strategy: aggressive
    timeout_seconds: 10
    retry_strategy: walk_then_market
    max_walks: 2
  
  MEDIUM:
    order_type: limit
    price_strategy: fair
    timeout_seconds: 30
    retry_strategy: walk_price
    max_walks: 5
  
  LOW:
    order_type: limit
    price_strategy: conservative
    timeout_seconds: 60
    retry_strategy: walk_slowly
    max_walks: 10

# Partial exits (add second stage)
partial_exits:
  enabled: true
  stages:
    - name: "first_target"
      profit_threshold: 0.15
      exit_percentage: 50
    - name: "second_target"      # NEW
      profit_threshold: 0.25      # NEW
      exit_percentage: 25         # NEW

# Liquidity checks (from Grok)
liquidity:
  max_spread: 0.03  # 3¢
  min_volume: 50    # contracts
```

**Note:** Remove any reference to `edge_reversal` if present - it's been removed as redundant.

---

## Previous Session Work (Still Needs Integration)

### From Session 6

**1. ADR-020: Deferred Advanced Execution**
- Decision: Defer Dynamic Depth Walker to Phase 8
- Rationale: Prove edge detection first, collect metrics
- Implementation: Phase 8 (conditional on metrics)

**2. ADR-021: Method Abstraction Layer**
- Decision: Bundle strategy + model + configs into "Method"
- Schema: methods table, method_templates table
- Implementation: Phase 4/5

**3. PHASE_8_ADVANCED_EXECUTION_SPEC.md**
- Full Dynamic Depth Walker specification
- Conditional implementation based on Phase 5-7 metrics
- Decision criteria: slippage >1.5%, thin markets >30%

---

## Documentation Update Tasks

### Priority 1: Update MASTER_REQUIREMENTS

**Add new requirements section:**

```markdown
## Phase 5: Position Monitoring & Exit Management

**REQ-MON-001:** System SHALL monitor all open positions continuously
**REQ-MON-002:** Monitoring frequency SHALL be dynamic (30s normal, 5s urgent)
**REQ-MON-003:** System SHALL cache prices for 10s to reduce API calls
**REQ-MON-004:** API usage SHALL stay below 60 calls/minute
**REQ-MON-005:** System SHALL track unrealized P&L in-memory (not persisted every check)

**REQ-EXIT-001:** System SHALL evaluate 10 distinct exit conditions
**REQ-EXIT-002:** Exit conditions SHALL have priority hierarchy (CRITICAL > HIGH > MEDIUM > LOW)
**REQ-EXIT-003:** Multiple exit triggers SHALL resolve to highest priority
**REQ-EXIT-004:** CRITICAL exits SHALL use market orders
**REQ-EXIT-005:** HIGH/MEDIUM/LOW exits SHALL use limit orders with escalation
**REQ-EXIT-006:** Unfilled limit orders SHALL escalate progressively (walk → market)
**REQ-EXIT-007:** System SHALL support partial exits (50% then 25%)
**REQ-EXIT-008:** All exits SHALL log reason, priority, and execution details
**REQ-EXIT-009:** System SHALL NOT use edge_reversal condition (redundant)
**REQ-EXIT-010:** Exit execution SHALL vary by urgency (market/aggressive/fair/conservative)
```

---

### Priority 2: Update DATABASE_SCHEMA_SUMMARY

**Add to Phase 5 section:**

```markdown
### Phase 5: Position Monitoring Fields

ALTER TABLE positions ADD COLUMN IF NOT EXISTS current_price DECIMAL(10,4);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS unrealized_pnl DECIMAL(10,2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS unrealized_pnl_pct DECIMAL(6,4);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS last_update TIMESTAMP;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS trailing_stop_active BOOLEAN DEFAULT FALSE;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS peak_price DECIMAL(10,4);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS trailing_stop_price DECIMAL(10,4);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(50);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS exit_priority VARCHAR(20);

### Phase 5: Exit Tracking Tables

CREATE TABLE position_exits (...);  -- Full schema in PHASE_5_EXIT_EVALUATION_SPEC
CREATE TABLE exit_attempts (...);   -- Full schema in PHASE_5_EXIT_EVALUATION_SPEC
```

---

### Priority 3: Update DEVELOPMENT_PHASES

**Update Phase 5a section:**

```markdown
### Phase 5a: Trading MVP (Weeks 9-12)

**Goal:** Live trading with basic execution + comprehensive position monitoring

**Core Deliverables:**

1. **Entry System** (existing)
   - Edge detection
   - Risk management
   - Order execution (simple limit orders)

2. **Position Monitoring System** (NEW)
   - PositionMonitor async loop
   - Dynamic frequency (30s normal, 5s urgent)
   - API rate limiting and price caching
   - Real-time P&L tracking
   - Trailing stop updates

3. **Exit Evaluation System** (NEW)
   - ExitEvaluator (10 conditions, priority-based)
   - Exit condition hierarchy
   - Conflict resolution
   - Partial exit detection

4. **Exit Execution System** (NEW)
   - ExitExecutor (urgency-based strategies)
   - Market orders for CRITICAL exits
   - Limit orders with escalation for others
   - Progressive price walking
   - Failed exit handling

**Success Criteria:**
- [ ] All open positions monitored continuously
- [ ] Exit conditions trigger correctly with priority resolution
- [ ] CRITICAL exits fill within 10 seconds
- [ ] API usage stays below 60 calls/minute
- [ ] No orphaned positions (all closed properly)
- [ ] Trailing stops update within 30s of price movement
```

---

### Priority 4: Update CONFIGURATION_GUIDE

**Add section on Position Monitoring:**

```markdown
### Position Monitoring Configuration

**Monitoring Frequency:**
- Normal: 30 seconds (standard tracking)
- Urgent: 5 seconds (near thresholds)

**Urgency Triggers:**
- Within 2% of stop loss
- Within 2% of profit target
- Within 2% of trailing stop

**Price Caching:**
- TTL: 10 seconds
- Purpose: Reduce API calls while staying current

**Rate Limiting:**
- Maximum: 60 API calls/minute
- Kalshi limit: 600 calls/minute
- Safety margin: 90%

### Exit Priority Configuration

**CRITICAL Priority:**
- Use for: stop_loss, circuit_breaker
- Execution: Market orders
- Timeout: 5 seconds
- Retry: immediate_market (no limit attempts)

**HIGH Priority:**
- Use for: trailing_stop, time_based_urgent, liquidity_dried_up
- Execution: Aggressive limit orders
- Timeout: 10 seconds
- Retry: walk_then_market (2 walks max)

**MEDIUM Priority:**
- Use for: profit_target, partial_exit_target
- Execution: Fair limit orders
- Timeout: 30 seconds
- Retry: walk_price (5 walks max)

**LOW Priority:**
- Use for: early_exit, edge_disappeared, rebalance
- Execution: Conservative limit orders
- Timeout: 60 seconds
- Retry: walk_slowly (10 walks max)
```

---

### Priority 5: Update MASTER_INDEX

**Add new documents:**

```markdown
### Phase 5 Specifications

| Document | Version | Purpose |
|----------|---------|---------|
| PHASE_5_POSITION_MONITORING_SPEC_V1_0.md | 1.0 | Position monitoring implementation |
| PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md | 1.0 | Exit condition evaluation & execution |
| PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md | 1.0 | Complete trading event loop overview |
```

---

## Key Design Decisions (This Session)

### Decision 1: Monitoring Frequency

**Choice:** 30s normal, 5s urgent (dynamic)

**Rationale:**
- Balances responsiveness with rate limits
- Urgent checks (5s) for positions near thresholds
- API usage: <20% of rate limit even with 20 positions

**Rejected Alternatives:**
- Every 4 seconds (too aggressive, rate limit risk)
- Every 60 seconds (too slow for urgent situations)

---

### Decision 2: Exit Condition Set

**Choice:** 10 conditions with priority hierarchy

**Removed:** edge_reversal (redundant)

**Rationale:**
- edge_reversal overlaps with early_exit (absolute threshold) and edge_disappeared (negative edge)
- Scenario analysis showed all cases covered by remaining conditions
- Simpler system with no functionality loss

**Exit Hierarchy:**
1. CRITICAL: Capital protection (stop loss, circuit breaker)
2. HIGH: Risk management (trailing stop, time urgency, liquidity)
3. MEDIUM: Profit taking (targets, partials)
4. LOW: Optimization (early exit, rebalance)

---

### Decision 3: Urgency-Based Execution

**Choice:** Different execution strategies by exit priority

**Rationale:**
- CRITICAL exits (stop loss) need immediate fill → market orders
- HIGH exits need fast fill but reduce slippage → aggressive limits
- MEDIUM exits balance price and speed → fair limits
- LOW exits optimize for best price → conservative limits

**Implementation:**
- CRITICAL: Market order, 5s timeout, immediate
- HIGH: Aggressive limit, 10s timeout, walk 2x then market
- MEDIUM: Fair limit, 30s timeout, walk 5x
- LOW: Conservative limit, 60s timeout, walk 10x

---

### Decision 4: Partial Exits

**Choice:** 2-stage partial exits (50% at +15%, 25% at +25%)

**Rationale:**
- Reduces risk while maintaining upside exposure
- Standard trading practice
- Relatively simple to implement

**Configuration:**
```yaml
partial_exits:
  stages:
    - name: "first_target"
      profit_threshold: 0.15
      exit_percentage: 50
    - name: "second_target"
      profit_threshold: 0.25
      exit_percentage: 25
# Remaining 25% rides with trailing stop
```

---

### Decision 5: Price Caching

**Choice:** Cache prices for 10 seconds

**Rationale:**
- Reduces API calls by ~66% (30s check / 10s cache = 3 checks per API call)
- Acceptable staleness for monitoring (not execution)
- API usage: 20 positions × 2 calls/min = 40 calls/min (well under limit)

---

## Integration with Previous Work

### ADR-021 Integration

The Position Monitoring and Exit systems use Method configurations (from ADR-021):

```python
# Exit evaluation uses Method config
method = get_method(position.method_id)
config = method.position_mgmt_config

# Check stop loss from Method
if position.unrealized_pnl_pct < config['stop_loss']['threshold']:
    trigger_exit("stop_loss", priority=CRITICAL)

# Check profit target from Method
if position.unrealized_pnl_pct >= config['profit_targets']['high_confidence']:
    trigger_exit("profit_target", priority=MEDIUM)
```

### ADR-020 Integration

Phase 5 uses **simple execution only** (consistent with ADR-020):
- Basic limit orders for entries
- Market orders for CRITICAL exits
- Limit orders with simple walking for other exits
- Dynamic Depth Walker deferred to Phase 8

### Phase 8 Integration

If Phase 8 is implemented (conditional on metrics), exits could optionally use Dynamic Depth Walker for LOW priority exits:

```python
if exit_priority == Priority.LOW and phase8_enabled:
    # Use Dynamic Depth Walker for patient exits
    walker = DynamicDepthWalker(...)
    result = await walker.execute_exit(position, trigger)
else:
    # Use simple limit order (Phase 5)
    result = await simple_limit_exit(position, trigger)
```

---

## Testing Requirements

### Unit Tests (Phase 5a)

**Position Monitoring:**
- test_monitoring_frequency_urgent()
- test_monitoring_frequency_normal()
- test_trailing_stop_activation()
- test_trailing_stop_update()
- test_price_caching()
- test_rate_limiting()

**Exit Evaluation:**
- test_stop_loss_triggers()
- test_trailing_stop_triggers()
- test_profit_target_triggers()
- test_partial_exit_triggers()
- test_multiple_triggers_priority()
- test_edge_reversal_removed()  # Verify removed

**Exit Execution:**
- test_market_order_critical_exits()
- test_limit_order_execution()
- test_price_walking_escalation()
- test_failed_exit_handling()

### Integration Tests (Phase 5b)

- test_complete_monitoring_cycle()
- test_entry_to_exit_flow()
- test_circuit_breaker_triggers()
- test_concurrent_position_monitoring()

---

## Files to Update (Summary)

1. **MASTER_REQUIREMENTS_V2.4 → V2.5**
   - Add REQ-MON-001 through REQ-MON-005
   - Add REQ-EXIT-001 through REQ-EXIT-010
   - Note removal of edge_reversal

2. **DATABASE_SCHEMA_SUMMARY_V1.4 → V1.5**
   - Add positions table updates (monitoring fields)
   - Add position_exits table
   - Add exit_attempts table

3. **DEVELOPMENT_PHASES_V1.2 → V1.3**
   - Expand Phase 5a with position monitoring & exit systems
   - Update success criteria

4. **CONFIGURATION_GUIDE_V3.0 → V3.1**
   - Add position monitoring configuration section
   - Add exit priority configuration section
   - Document urgency-based execution strategies

5. **MASTER_INDEX_V2.2 → V2.3**
   - Add 3 new Phase 5 specification documents

6. **position_management.yaml**
   - Add monitoring configuration
   - Add exit_priorities section
   - Add exit_execution section
   - Add second partial exit stage
   - Add liquidity thresholds

---

## Questions for User (If Any)

All design decisions have been made with clear rationale. The specifications are ready for implementation. No blocking questions remain.

---

## Summary

This session designed the complete position monitoring and exit management system for Phase 5:

**Deliverables Created:**
1. PHASE_5_POSITION_MONITORING_SPEC_V1_0.md (full monitoring system)
2. PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md (exit logic & execution)
3. PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md (complete architecture overview)

**Key Improvements:**
- Removed redundant edge_reversal condition
- Designed priority-based exit hierarchy
- Specified urgency-based execution strategies
- Added comprehensive error handling
- Integrated with ADR-021 Method abstraction

**Next Steps:**
1. Update documentation (MASTER_REQUIREMENTS, DATABASE_SCHEMA, etc.)
2. Implement Phase 5a monitoring system
3. Test with paper trading
4. Collect metrics for Phase 8 decision

**All specifications are implementation-ready.** 🚀
