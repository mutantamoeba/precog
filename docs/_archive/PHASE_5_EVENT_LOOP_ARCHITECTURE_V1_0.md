# Phase 5: Trading Event Loop Architecture
**Version:** 1.0
**Date:** 2025-10-21
**Status:** 🔵 Design Complete - Ready for Implementation
**Phase:** 5a (Trading MVP)
**Dependencies:** Phase 1-4 (Infrastructure, Data, Models)
**Related:** PHASE_5_POSITION_MONITORING_SPEC_V1_0.md, PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md

---

## Executive Summary

**Goal:** Document the complete trading event loop from edge detection through position exit.

**Key Flows:**
1. **Entry Flow**: Edge detected → Risk checks → Order execution → Position created
2. **Monitoring Flow**: Position monitoring loop with real-time P&L tracking
3. **Exit Flow**: Exit condition → Evaluation → Execution → Position closed

**Design Philosophy:**
- **Event-driven**: Async loops responding to market changes
- **Separation of concerns**: Entry, monitoring, and exit are distinct systems
- **Fail-safe**: Multiple safety layers and fallbacks

---

## Table of Contents

1. [Complete System Architecture](#complete-system-architecture)
2. [Entry Flow Detailed](#entry-flow-detailed)
3. [Monitoring Flow Detailed](#monitoring-flow-detailed)
4. [Exit Flow Detailed](#exit-flow-detailed)
5. [Component Interactions](#component-interactions)
6. [State Transitions](#state-transitions)
7. [Error Handling](#error-handling)

---

## Complete System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     TRADING EVENT LOOP                           │
│                                                                   │
│  ┌────────────┐     ┌──────────────┐     ┌─────────────┐       │
│  │   ENTRY    │────▶│  MONITORING  │────▶│    EXIT     │       │
│  │   FLOW     │     │     FLOW     │     │    FLOW     │       │
│  └────────────┘     └──────────────┘     └─────────────┘       │
│       │                    │                     │               │
│       │                    │                     │               │
│       ▼                    ▼                     ▼               │
│  Open Position      Track Position         Close Position       │
└─────────────────────────────────────────────────────────────────┘
```

### System Components

```
┌───────────────────────────────────────────────────────────────────┐
│                         COMPONENTS                                 │
└───────────────────────────────────────────────────────────────────┘

ENTRY SYSTEM
├── EdgeDetector ─────── Scans markets for trading opportunities
├── RiskManager ────────── Validates trades against risk limits
├── OrderExecutor ───────── Places entry orders (simple Phase 5)
└── PositionCreator ────── Creates position record in DB

MONITORING SYSTEM
├── PositionMonitor ────── Main monitoring loop (async)
├── PnLCalculator ──────── Updates unrealized P&L
├── TrailingStopManager ── Updates trailing stops
└── ExitEvaluator ──────── Checks exit conditions

EXIT SYSTEM
├── ExitEvaluator ──────── Determines when/why to exit
├── ExitExecutor ───────── Places exit orders
├── PartialExitHandler ─── Manages scaling out
└── FailedExitHandler ──── Handles unfilled orders

SUPPORTING SYSTEMS
├── KalshiClient ───────── API communication
├── Database ───────────── Position/trade persistence
├── ConfigManager ──────── Load method configurations
└── Logger ─────────────── Comprehensive audit trail
```

---

## Entry Flow Detailed

### Entry Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      ENTRY FLOW                              │
└─────────────────────────────────────────────────────────────┘

START: Edge Detected
    │
    ▼
┌─────────────────────┐
│  Edge Detector      │
│  - Calculate edge   │
│  - Check confidence │
│  - Assign to method │
└──────────┬──────────┘
           │
           ▼
    ┌────────────┐
    │ Edge > 5%? │───NO───▶ [Skip Trade]
    └─────┬──────┘
          │ YES
          ▼
┌─────────────────────┐
│  Risk Manager       │
│  Check:             │
│  - Position limits  │
│  - Exposure limits  │
│  - Daily loss limit │
│  - Correlation      │
└──────────┬──────────┘
           │
           ▼
    ┌────────────┐
    │ Risk OK?   │───NO───▶ [Reject Trade + Log]
    └─────┬──────┘
          │ YES
          ▼
┌─────────────────────┐
│  Position Sizer     │
│  - Kelly criterion  │
│  - Min/max limits   │
│  - Method config    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Order Executor     │
│  (Phase 5: Simple)  │
│  - Place limit ord  │
│  - Wait for fill    │
└──────────┬──────────┘
           │
           ▼
    ┌────────────┐
    │  Filled?   │───NO───▶ [Retry/Walk/Cancel]
    └─────┬──────┘
          │ YES
          ▼
┌─────────────────────┐
│  Position Creator   │
│  - Insert position  │
│  - Link to method   │
│  - Initialize state │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Start Monitoring   │
│  - Spawn async task │
│  - Track position   │
└─────────────────────┘
           │
           ▼
    [Position Open]
```

### Entry Flow Code Structure

```python
# trading/entry_flow.py

class EntryFlow:
    """Manages complete entry flow from edge to position."""

    async def execute_entry(self, edge: Edge):
        """
        Complete entry flow.

        Steps:
        1. Validate edge quality
        2. Check risk limits
        3. Calculate position size
        4. Place entry order
        5. Create position record
        6. Start monitoring
        """

        # 1. Validate edge
        if not self._validate_edge(edge):
            logger.info(f"Edge {edge.edge_id} failed validation")
            return

        # 2. Risk checks
        if not await self.risk_manager.can_trade(edge):
            logger.warning(f"Risk limits prevent trading {edge.market_id}")
            return

        # 3. Calculate size
        quantity = self.position_sizer.calculate_size(
            edge=edge,
            method=edge.method
        )

        # 4. Place order
        order = await self.order_executor.execute_entry(
            market_id=edge.market_id,
            side=edge.side,
            quantity=quantity,
            target_price=edge.target_price
        )

        if not order.filled:
            logger.warning(f"Entry order {order.order_id} not filled")
            return

        # 5. Create position
        position = self.position_creator.create_position(
            edge=edge,
            order=order,
            method=edge.method
        )

        # 6. Start monitoring
        await self.position_monitor.start_monitoring_position(position)

        logger.info(
            f"Entry complete: Position {position.position_id} "
            f"({quantity} @ {order.filled_price})"
        )
```

---

## Monitoring Flow Detailed

### Monitoring Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    MONITORING FLOW                           │
└─────────────────────────────────────────────────────────────┘

START: Position Opened
    │
    ▼
┌─────────────────────┐
│  Position Monitor   │
│  - Async loop       │
│  - Per-position task│
└──────────┬──────────┘
           │
           ▼
    [Sleep 30s or 5s depending on urgency]
           │
           ▼
┌─────────────────────┐
│  Fetch Price        │
│  - API call         │
│  - Cache for 10s    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Update P&L         │
│  - Calculate unreal │
│  - Update position  │
│  (In-memory only)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Update Trail Stop  │
│  - Check activated  │
│  - Update peak      │
│  - Calculate stop   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Exit Evaluator     │
│  - Check 10 conds   │
│  - Priority resolve │
└──────────┬──────────┘
           │
           ▼
    ┌────────────┐
    │ Exit Trig? │───NO───┐
    └─────┬──────┘        │
          │ YES            │
          ▼                │
┌─────────────────────┐   │
│  Exit Executor      │   │
│  - Place exit order │   │
│  - Monitor fill     │   │
│  - Handle failures  │   │
└──────────┬──────────┘   │
           │               │
           ▼               │
    [Position Closed]      │
           │               │
           │               │
           └───────────────┘
           │
           ▼
    [Loop continues until closed]
```

### Monitoring Loop Pseudo-Code

```python
# trading/position_monitor.py

async def monitor_single_position(position: Position):
    """
    Monitor one position until closed.

    This is the HEART of the trading system.
    Runs continuously in async loop.
    """

    while position.status == "open":

        # 1. Get current price (with caching)
        current_price = await get_current_price(position.market_id)

        # 2. Update unrealized P&L (local only)
        position.unrealized_pnl = calculate_pnl(position, current_price)
        position.unrealized_pnl_pct = position.unrealized_pnl / position.cost_basis

        # 3. Update trailing stop if needed
        if position.trailing_stop_enabled:
            update_trailing_stop(position, current_price)

        # 4. Check ALL exit conditions
        exit_trigger = exit_evaluator.check_exit_conditions(
            position=position,
            current_price=current_price,
            method=position.method
        )

        # 5. If exit triggered, execute it
        if exit_trigger:
            await exit_executor.execute_exit(
                position=position,
                trigger=exit_trigger
            )
            break  # Exit loop, position now closed

        # 6. Determine sleep interval
        if near_threshold(position):
            sleep_interval = 5  # Urgent
        else:
            sleep_interval = 30  # Normal

        # 7. Sleep before next check
        await asyncio.sleep(sleep_interval)
```

### Monitoring State Diagram

```
    Position
    Created
       │
       ▼
   ┌────────┐
   │ NORMAL │◄─────────────┐
   │  P&L   │              │
   └───┬────┘              │
       │                   │
       │ P&L > target-2%   │
       ▼                   │
   ┌────────┐              │
   │ URGENT │              │
   │Near Tgt│              │
   └───┬────┘              │
       │                   │
       │ Check every 5s    │
       │                   │
       │ Target hit?       │
       ├─YES─▶[EXIT]       │
       │                   │
       └─NO──────────────► │
                           │
    ┌──────────────────────┘
    │
    │ P&L < stop+2%
    ▼
   ┌────────┐
   │ URGENT │
   │Near SL │
   └───┬────┘
       │
       │ Stop hit?
       ├─YES─▶[EXIT]
       │
       └─NO──▶[Continue]
```

---

## Exit Flow Detailed

### Exit Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       EXIT FLOW                              │
└─────────────────────────────────────────────────────────────┘

START: Exit Condition Met
    │
    ▼
┌─────────────────────┐
│  Exit Evaluator     │
│  - Check priority   │
│  - Resolve conflicts│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Determine Quantity │
│  - Full?            │
│  - Partial?         │
│  - All positions?   │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────┐
    │ Priority?    │
    └──┬────┬───┬──┘
       │    │   │
  CRIT │    │HI │MED/LOW
       │    │   │
       ▼    ▼   ▼
    ┌────┐┌──┐┌────┐
    │Mkt ││Ag││Fair│
    │Ord ││Lim││Lim │
    └─┬──┘└┬─┘└─┬──┘
      │    │    │
      └────┴────┘
           │
           ▼
┌─────────────────────┐
│  Place Exit Order   │
│  - Calculate price  │
│  - Submit to Kalshi │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Monitor Fill       │
│  - Wait timeout     │
│  - Check status     │
└──────────┬──────────┘
           │
           ▼
    ┌────────────┐
    │  Filled?   │───YES───▶ [Update Position]
    └─────┬──────┘                    │
          │ NO                        │
          ▼                           │
┌─────────────────────┐               │
│  Escalation Handler │               │
│  Based on priority: │               │
│  - Walk price       │               │
│  - Walk then market │               │
│  - Immediate market │               │
└──────────┬──────────┘               │
           │                          │
           ▼                          │
    ┌────────────┐                    │
    │  Success?  │───YES──────────────┘
    └─────┬──────┘
          │ NO
          ▼
    [Log Failure]
          │
          ▼
    [Position Stays Open]
```

### Exit Decision Tree

```
Exit Condition Triggered
    │
    ├─── Is Multiple? ──YES──▶ Sort by Priority ──▶ Execute Highest
    │                                                     │
    └─── NO ──────────────────────────────────────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │ Determine     │
                            │ Execution     │
                            │ Strategy      │
                            └───┬───────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
            CRITICAL          HIGH           MED/LOW
                │               │               │
                ▼               ▼               ▼
          ┌─────────┐     ┌─────────┐    ┌─────────┐
          │ Market  │     │Aggressive│   │  Fair   │
          │ Order   │     │  Limit   │   │  Limit  │
          │ 5s TO   │     │  10s TO  │   │  30s TO │
          └────┬────┘     └────┬─────┘   └────┬────┘
               │               │              │
               │               │              │
               └───────┬───────┴──────┬───────┘
                       │              │
                       ▼              ▼
                  Fill?──YES──▶[Done]
                       │
                       NO
                       │
                       ▼
              ┌────────────────┐
              │   Escalation   │
              │   Strategy     │
              └────┬───────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
    immediate  walk_then  walk_price
    _market     _market
        │          │          │
        ▼          ▼          ▼
    [Market]  [Walk 2x  [Walk 5x
               →Market]  →Give Up]
```

### Exit Execution Code Flow

```python
# trading/exit_executor.py

async def execute_exit(position: Position, trigger: ExitTrigger):
    """
    Execute exit with urgency-based strategy.

    Flow depends on trigger priority:
    - CRITICAL: Market order immediately
    - HIGH: Aggressive limit, then market if needed
    - MEDIUM: Fair limit, walk if needed
    - LOW: Conservative limit, patient walking
    """

    # 1. Determine quantity
    quantity = determine_quantity(position, trigger)

    # 2. Get execution params
    params = trigger.execution_params

    # 3. Place order
    if params['order_type'] == 'market':
        # CRITICAL exit - market order
        order = await place_market_order(position, quantity)
        await wait_for_fill(order, timeout=5)

    else:
        # Limit order
        price = calculate_exit_price(position, params['price_strategy'])
        order = await place_limit_order(position, quantity, price)

        # Wait for fill
        filled = await wait_for_fill(order, timeout=params['timeout'])

        if not filled:
            # Escalate based on strategy
            if params['retry'] == 'immediate_market':
                await cancel_and_use_market(order, position)

            elif params['retry'] == 'walk_then_market':
                await walk_price_twice_then_market(order, position)

            elif params['retry'] == 'walk_price':
                await walk_price_up_to_max(order, position, params['max_walks'])

            elif params['retry'] == 'walk_slowly':
                await walk_slowly(order, position, params['max_walks'])

    # 4. Update position
    update_position_after_exit(position, order, trigger)

    logger.info(f"Exit complete: {position.position_id}")
```

---

## Component Interactions

### Entry-Monitoring-Exit Interaction

```
┌──────────────┐
│ EdgeDetector │
└──────┬───────┘
       │ edge detected
       ▼
┌──────────────┐
│ RiskManager  │
└──────┬───────┘
       │ risk approved
       ▼
┌──────────────┐
│OrderExecutor │
└──────┬───────┘
       │ order filled
       ▼
┌──────────────────┐
│PositionCreator  │ ◄───────┐
└──────┬───────────┘         │
       │ position created     │
       ▼                      │
┌──────────────────┐         │
│PositionMonitor  │         │
│  (async loop)    │         │
└──────┬───────────┘         │
       │ monitors             │
       ▼                      │
┌──────────────────┐         │
│ ExitEvaluator   │         │
└──────┬───────────┘         │
       │ trigger              │
       ▼                      │
┌──────────────────┐         │
│ ExitExecutor    │         │
└──────┬───────────┘         │
       │ exit complete        │
       ▼                      │
┌──────────────────┐         │
│Position: CLOSED │ ─────────┘
└──────────────────┘
    (updates DB)
```

### Data Flow Between Components

```
ENTRY FLOW DATA:
Edge {
    market_id, side, target_price,
    edge_value, confidence, method_id
} ──▶ Risk Check ──▶ Position Size ──▶ Order {
    order_id, filled_price, quantity
} ──▶ Position {
    position_id, entry_price, count,
    method_id, status="open"
}

MONITORING FLOW DATA:
Position (in-memory) {
    position_id, market_id, side, count,
    entry_price, current_price,
    unrealized_pnl, unrealized_pnl_pct,
    trailing_stop_active, peak_price,
    trailing_stop_price
}

EXIT FLOW DATA:
ExitTrigger {
    reason, priority, quantity,
    execution_params, metadata
} ──▶ Order {
    order_id, type, price, quantity
} ──▶ Position Update {
    status="closed", exit_price,
    realized_pnl, exit_reason
}
```

---

## State Transitions

### Position Lifecycle States

```
┌─────────┐
│  EDGE   │
│ DETECTED│
└────┬────┘
     │
     ▼
┌─────────┐
│  RISK   │──FAIL──▶[Rejected]
│ CHECKS  │
└────┬────┘
     │ PASS
     ▼
┌─────────┐
│ ORDER   │──UNFILL─▶[Cancelled]
│ PLACED  │
└────┬────┘
     │ FILLED
     ▼
┌─────────┐
│POSITION │◄─────┐
│  OPEN   │      │
└────┬────┘      │
     │           │
     │ Monitoring│
     │ Loop      │
     │           │
     ├───────────┘
     │
     │ Exit Trigger
     ▼
┌─────────┐
│  EXIT   │──FAIL──▶[Open+Alert]
│ ORDERED │
└────┬────┘
     │ FILLED
     ▼
┌─────────┐
│POSITION │
│ CLOSED  │
└─────────┘
```

### Exit Condition State Machine

```
    Normal
    Monitoring
       │
       ├── P&L < -15% ──▶ STOP_LOSS (CRITICAL) ──▶ Market Order
       │
       ├── Trail Active
       │   & Price < Stop ──▶ TRAILING_STOP (HIGH) ──▶ Aggressive Limit
       │
       ├── P&L > +25% ──▶ PROFIT_TARGET (MEDIUM) ──▶ Fair Limit
       │
       ├── Edge < 2% ──▶ EARLY_EXIT (LOW) ──▶ Conservative Limit
       │
       └── [Other conditions...]
```

---

## Error Handling

### Failure Points and Recovery

```
FAILURE POINT 1: Edge Detection Fails
├─ Error: Model throws exception
├─ Recovery: Log error, skip this cycle, continue
└─ Alert: If errors > 5 in 10 min

FAILURE POINT 2: Risk Check Fails
├─ Error: Database query timeout
├─ Recovery: Retry 3x with backoff, then skip trade
└─ Alert: If retries exhausted

FAILURE POINT 3: Order Placement Fails
├─ Error: Kalshi API returns error
├─ Recovery: Retry based on error code
│   ├─ Rate limit: Wait and retry
│   ├─ Invalid params: Log and skip
│   └─ Network error: Retry 3x
└─ Alert: If order fails after retries

FAILURE POINT 4: Position Monitoring Crashes
├─ Error: Monitor task throws unhandled exception
├─ Recovery: Supervisor restarts monitor
├─ Fallback: Health check alerts if no updates >2 min
└─ Alert: Critical - position could be orphaned

FAILURE POINT 5: Exit Order Fails
├─ Error: Limit order doesn't fill
├─ Recovery: Escalation strategy (walk/market)
├─ Fallback: If all escalations fail, alert user
└─ Alert: Position still open, manual intervention needed

FAILURE POINT 6: Database Write Fails
├─ Error: Cannot update position
├─ Recovery: Retry with exponential backoff
├─ Fallback: Log to file, manual reconciliation
└─ Alert: Critical - data integrity issue
```

### Circuit Breakers

```
CIRCUIT BREAKER 1: Daily Loss Limit
├─ Trigger: Daily loss > $500
├─ Action: Close ALL open positions (market orders)
└─ Recovery: Manual reset required

CIRCUIT BREAKER 2: API Failures
├─ Trigger: >5 API errors in 5 minutes
├─ Action: Pause new entries, continue monitoring
└─ Recovery: Auto-resume when errors clear

CIRCUIT BREAKER 3: Database Failures
├─ Trigger: >3 DB errors in 1 minute
├─ Action: Pause ALL trading (entry + exit)
└─ Recovery: Manual investigation required
```

---

## Summary

**Trading Event Loop provides:**
- ✅ Complete entry-to-exit lifecycle management
- ✅ Separation of concerns (entry/monitoring/exit)
- ✅ Async monitoring with dynamic frequency
- ✅ Priority-based exit handling
- ✅ Comprehensive error recovery
- ✅ Multiple safety layers (risk checks, circuit breakers)

**Key Architectural Principles:**
1. **Event-driven**: React to market changes, not polling
2. **Async by default**: Non-blocking operations throughout
3. **Fail-safe**: Multiple fallbacks at each failure point
4. **Auditable**: Comprehensive logging at each step
5. **Configurable**: All thresholds driven by Method config

**Implementation Order:**
1. Entry flow (Phases 1-4 → Phase 5a)
2. Monitoring loop (Phase 5a)
3. Exit evaluation (Phase 5a)
4. Exit execution (Phase 5a)
5. Error handling & circuit breakers (Phase 5a)
6. Integration testing (Phase 5b)

**Success Criteria:**
- [ ] Entry-to-monitoring handoff works reliably
- [ ] Monitoring loop runs continuously without crashes
- [ ] Exit conditions trigger correctly
- [ ] Exit execution completes within timeouts
- [ ] Circuit breakers prevent catastrophic losses
- [ ] System recovers gracefully from all failure points

---

**Related Documents:**
- `PHASE_5_POSITION_MONITORING_SPEC_V1_0.md` - Monitoring implementation
- `PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md` - Exit logic details
- `ADR_021_METHOD_ABSTRACTION.md` - Configuration structure
- `DEVELOPMENT_PHASES_V1_2.md` - Implementation timeline
