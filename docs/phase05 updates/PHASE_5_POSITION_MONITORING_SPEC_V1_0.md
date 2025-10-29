# Phase 5: Position Monitoring & Exit Management Specification
**Version:** 1.0  
**Date:** 2025-10-21  
**Status:** 🔵 Design Complete - Ready for Implementation  
**Phase:** 5a (Trading MVP)  
**Dependencies:** Phase 1-4 (Infrastructure, Data, Models)  
**Related:** ADR-021 (Method Abstraction), PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md

---

## Executive Summary

**Goal:** Continuously monitor open positions and execute exits based on predefined conditions.

**Key Components:**
1. **PositionMonitor** - Async loop monitoring all open positions
2. **ExitEvaluator** - Checks exit conditions with priority hierarchy
3. **ExitExecutor** - Executes exit orders with urgency-based strategies
4. **PartialExitHandler** - Manages scaling out of positions

**Design Principles:**
- **Rate limit aware**: Balances responsiveness with API limits
- **Priority-based**: Critical exits (stop loss) take precedence over opportunistic exits
- **Urgency-adaptive**: Execution strategy varies by exit urgency
- **Method-aware**: Exit rules pulled from Method configuration (ADR-021)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Position Monitoring Loop](#position-monitoring-loop)
3. [Exit Evaluation](#exit-evaluation)
4. [Exit Execution](#exit-execution)
5. [Partial Exits](#partial-exits)
6. [Database Schema](#database-schema)
7. [Configuration](#configuration)
8. [Testing Strategy](#testing-strategy)
9. [Performance Metrics](#performance-metrics)

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                   Trading Engine                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ on_trade_executed(trade)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              PositionMonitor (Main Loop)                     │
│  - Monitors all open positions                               │
│  - Frequency: 30s normal, 5s urgent                          │
│  - API rate limit management                                 │
└────────────┬───────────────────────┬────────────────────────┘
             │                       │
             │ check_exit            │ update_pnl
             ▼                       ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│  ExitEvaluator           │  │  P&L Calculator              │
│  - Checks all conditions │  │  - Unrealized P&L            │
│  - Returns exit trigger  │  │  - Peak tracking             │
│  - Priority resolution   │  │  - Trailing stop updates     │
└──────────┬───────────────┘  └──────────────────────────────┘
           │
           │ if exit_trigger
           ▼
┌────────────────────────────────────────────────────────────┐
│              ExitExecutor                                   │
│  - Determines execution strategy (market/limit)            │
│  - Handles unfilled orders (walk price, retry)            │
│  - Updates position status                                 │
└────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Trade Executed
    ↓
Position Created (status = "open")
    ↓
[Monitor Loop Starts]
    ↓
Every 30s (or 5s if urgent):
    1. Fetch current market price (API call)
    2. Calculate unrealized P&L (local)
    3. Update trailing stop state (local)
    4. Check exit conditions (local)
    5. If exit triggered → Execute exit order
    ↓
Exit Executed
    ↓
Position Closed (status = "closed")
    ↓
[Monitor Loop Ends]
```

---

## Position Monitoring Loop

### PositionMonitor Class

```python
# trading/position_monitor.py

import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from database.models import Position, Method
from trading.exit_evaluator import ExitEvaluator, ExitTrigger
from trading.exit_executor import ExitExecutor
from api.kalshi_client import KalshiClient

logger = logging.getLogger(__name__)


class PositionMonitor:
    """
    Continuously monitors open positions and triggers exits.
    
    Features:
    - Dynamic monitoring frequency (urgent vs normal)
    - Rate limit aware (API call management)
    - Priority-based exit handling
    - Trailing stop updates
    - Real-time P&L tracking
    """
    
    def __init__(
        self,
        kalshi_client: KalshiClient,
        exit_evaluator: ExitEvaluator,
        exit_executor: ExitExecutor
    ):
        self.kalshi_client = kalshi_client
        self.exit_evaluator = exit_evaluator
        self.exit_executor = exit_executor
        
        # Rate limiting
        self.api_calls_per_minute = 0
        self.api_call_reset_time = datetime.now() + timedelta(minutes=1)
        self.max_api_calls_per_minute = 60  # Conservative limit
        
        # State
        self.active_monitors: Dict[int, asyncio.Task] = {}  # position_id → task
        self.price_cache: Dict[str, tuple] = {}  # market_id → (price, timestamp)
        self.cache_ttl_seconds = 10  # Cache prices for 10s
    
    async def start_monitoring(self):
        """
        Main monitoring loop.
        Discovers all open positions and spawns monitor tasks.
        """
        logger.info("Starting position monitor...")
        
        while True:
            try:
                # Get all open positions
                open_positions = self._get_open_positions()
                
                # Start monitoring new positions
                for position in open_positions:
                    if position.position_id not in self.active_monitors:
                        task = asyncio.create_task(
                            self._monitor_single_position(position)
                        )
                        self.active_monitors[position.position_id] = task
                        logger.info(
                            f"Started monitoring position {position.position_id} "
                            f"({position.market_id} {position.side})"
                        )
                
                # Clean up completed monitors
                completed = [
                    pid for pid, task in self.active_monitors.items()
                    if task.done()
                ]
                for pid in completed:
                    del self.active_monitors[pid]
                
                # Check every 15 seconds for new positions
                await asyncio.sleep(15)
                
            except Exception as e:
                logger.error(f"Error in main monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(30)  # Back off on error
    
    async def _monitor_single_position(self, position: Position):
        """
        Monitor a single position until closed.
        
        Monitoring frequency:
        - Normal: Every 30 seconds (standard tracking)
        - Urgent: Every 5 seconds (near thresholds)
        
        Args:
            position: Position to monitor
        """
        logger.info(f"Monitoring position {position.position_id}")
        
        # Get method configuration
        method = self._get_method(position.method_id)
        
        monitoring_iterations = 0
        
        try:
            while True:
                # Check if position still open
                position = self._refresh_position(position.position_id)
                if position.status != "open":
                    logger.info(
                        f"Position {position.position_id} closed, "
                        f"stopping monitor"
                    )
                    break
                
                # Get current market price (with caching)
                current_price = await self._get_current_price(position.market_id)
                
                # Update unrealized P&L (local calculation, no DB write)
                self._update_unrealized_pnl(position, current_price)
                
                # Update trailing stop if needed
                self._update_trailing_stop(position, current_price, method)
                
                # Check exit conditions
                exit_trigger = self.exit_evaluator.check_exit_conditions(
                    position=position,
                    current_price=current_price,
                    method=method
                )
                
                # If exit triggered, execute it
                if exit_trigger:
                    logger.info(
                        f"Exit trigger for position {position.position_id}: "
                        f"{exit_trigger.reason} (Priority {exit_trigger.priority})"
                    )
                    
                    await self.exit_executor.execute_exit(
                        position=position,
                        trigger=exit_trigger
                    )
                    
                    # Exit monitor loop (position now closed)
                    break
                
                # Determine sleep interval based on urgency
                sleep_interval = self._calculate_sleep_interval(position, method)
                
                # Log periodic status (every 10 iterations or urgent checks)
                monitoring_iterations += 1
                if monitoring_iterations % 10 == 0 or sleep_interval < 10:
                    logger.info(
                        f"Position {position.position_id} status: "
                        f"P&L={position.unrealized_pnl_pct:.2%}, "
                        f"Price={current_price}, "
                        f"Next check in {sleep_interval}s"
                    )
                
                await asyncio.sleep(sleep_interval)
                
        except Exception as e:
            logger.error(
                f"Error monitoring position {position.position_id}: {e}",
                exc_info=True
            )
            # Don't crash the monitor, keep trying
            await asyncio.sleep(60)
    
    async def _get_current_price(self, market_id: str) -> Decimal:
        """
        Get current market price with caching to reduce API calls.
        
        Cache strategy:
        - Cache prices for 10 seconds
        - After 10s, make new API call
        - Reduces API load while staying reasonably current
        
        Args:
            market_id: Market ticker
            
        Returns:
            Current market price
        """
        now = datetime.now()
        
        # Check cache
        if market_id in self.price_cache:
            cached_price, cached_time = self.price_cache[market_id]
            age_seconds = (now - cached_time).total_seconds()
            
            if age_seconds < self.cache_ttl_seconds:
                # Cache hit - return cached price
                return cached_price
        
        # Cache miss or stale - fetch from API
        await self._check_rate_limit()
        
        market = await self.kalshi_client.get_market(market_id)
        
        # Cache the price
        self.price_cache[market_id] = (market.yes_bid, now)
        
        return market.yes_bid
    
    async def _check_rate_limit(self):
        """
        Ensure we don't exceed API rate limits.
        
        Kalshi limits: 100 requests per 10s = 600/minute
        Our limit: 60/minute (conservative)
        
        If approaching limit, sleep to avoid hitting it.
        """
        now = datetime.now()
        
        # Reset counter every minute
        if now >= self.api_call_reset_time:
            self.api_calls_per_minute = 0
            self.api_call_reset_time = now + timedelta(minutes=1)
        
        # Check if approaching limit
        if self.api_calls_per_minute >= self.max_api_calls_per_minute:
            # Sleep until next reset
            sleep_seconds = (self.api_call_reset_time - now).total_seconds()
            logger.warning(
                f"Rate limit approaching, sleeping {sleep_seconds:.1f}s"
            )
            await asyncio.sleep(sleep_seconds)
            
            # Reset counter
            self.api_calls_per_minute = 0
            self.api_call_reset_time = datetime.now() + timedelta(minutes=1)
        
        # Increment counter
        self.api_calls_per_minute += 1
    
    def _calculate_sleep_interval(
        self,
        position: Position,
        method: Method
    ) -> int:
        """
        Determine how long to sleep before next check.
        
        Strategy:
        - Urgent (5s): Within 2% of stop loss or profit target
        - Normal (30s): Everything else
        
        Args:
            position: Position being monitored
            method: Method configuration
            
        Returns:
            Sleep interval in seconds
        """
        config = method.position_mgmt_config
        
        # Check if near stop loss
        stop_loss_threshold = config.get('stop_loss', {}).get('threshold', -0.15)
        if position.unrealized_pnl_pct < (stop_loss_threshold + 0.02):
            return 5  # Urgent - near stop loss
        
        # Check if near profit target
        profit_target = config.get('profit_targets', {}).get('high_confidence', 0.25)
        if position.unrealized_pnl_pct > (profit_target - 0.02):
            return 5  # Urgent - near profit target
        
        # Check if near trailing stop
        if position.trailing_stop_active:
            distance_to_stop = (
                position.current_price - position.trailing_stop_price
            ) / position.current_price
            if distance_to_stop < 0.02:  # Within 2%
                return 5  # Urgent - near trailing stop
        
        # Normal monitoring
        return 30
    
    def _update_unrealized_pnl(
        self,
        position: Position,
        current_price: Decimal
    ):
        """
        Update position's unrealized P&L.
        
        This is a local calculation, no database write.
        P&L is persisted when position closes.
        
        Args:
            position: Position object (modified in place)
            current_price: Current market price
        """
        # Calculate P&L
        entry_cost = position.entry_price * position.count
        current_value = current_price * position.count
        unrealized_pnl = current_value - entry_cost
        unrealized_pnl_pct = unrealized_pnl / entry_cost
        
        # Update position (in-memory)
        position.current_price = current_price
        position.unrealized_pnl = unrealized_pnl
        position.unrealized_pnl_pct = unrealized_pnl_pct
        position.last_update = datetime.now()
    
    def _update_trailing_stop(
        self,
        position: Position,
        current_price: Decimal,
        method: Method
    ):
        """
        Update trailing stop if price moved favorably.
        
        Logic:
        1. Check if trailing stop activated (profit > threshold)
        2. Update peak price if current price is new high
        3. Calculate new trailing stop price
        4. Update position.trailing_stop_state
        
        Args:
            position: Position object (modified in place)
            current_price: Current market price
            method: Method configuration
        """
        config = method.position_mgmt_config.get('trailing_stop', {})
        
        if not config.get('enabled', False):
            return  # Trailing stops disabled
        
        # Check activation
        activation_threshold = Decimal(
            str(config.get('activation_threshold', 0.10))
        )
        
        if not position.trailing_stop_active:
            # Check if we should activate
            if position.unrealized_pnl_pct >= activation_threshold:
                position.trailing_stop_active = True
                position.peak_price = current_price
                
                distance = Decimal(str(config.get('initial_distance', 0.05)))
                position.trailing_stop_price = position.peak_price * (
                    Decimal('1.0') - distance
                )
                
                logger.info(
                    f"Trailing stop activated for position {position.position_id} "
                    f"at {position.peak_price} (stop: {position.trailing_stop_price})"
                )
        
        else:
            # Already active - update if price moved up
            if current_price > position.peak_price:
                position.peak_price = current_price
                
                # Calculate trailing stop distance (with tightening)
                distance = self._calculate_trailing_distance(
                    position=position,
                    config=config
                )
                
                position.trailing_stop_price = position.peak_price * (
                    Decimal('1.0') - distance
                )
                
                logger.debug(
                    f"Trailing stop updated for position {position.position_id}: "
                    f"Peak={position.peak_price}, Stop={position.trailing_stop_price}"
                )
    
    def _calculate_trailing_distance(
        self,
        position: Position,
        config: dict
    ) -> Decimal:
        """
        Calculate trailing stop distance with tightening.
        
        Example from config:
        - Initial distance: 5%
        - Tightening rate: 1% per 5% gain
        - Floor: 2%
        
        If profit is 15%:
        - Tightening: 15% / 5% = 3 steps
        - Reduction: 3 * 1% = 3%
        - Distance: 5% - 3% = 2% (at floor)
        
        Args:
            position: Position with current profit
            config: Trailing stop configuration
            
        Returns:
            Trailing stop distance as decimal
        """
        initial_distance = Decimal(str(config.get('initial_distance', 0.05)))
        tightening_rate = Decimal(str(config.get('tightening_rate', 0.01)))
        floor_distance = Decimal(str(config.get('floor_distance', 0.02)))
        
        # Calculate tightening
        profit_pct = position.unrealized_pnl_pct
        tightening_steps = int(profit_pct / Decimal('0.05'))  # Every 5% profit
        reduction = tightening_rate * tightening_steps
        
        # Apply floor
        distance = max(initial_distance - reduction, floor_distance)
        
        return distance
    
    def _get_open_positions(self) -> List[Position]:
        """Get all open positions from database."""
        # Implementation uses SQLAlchemy
        pass
    
    def _refresh_position(self, position_id: int) -> Position:
        """Reload position from database."""
        # Implementation uses SQLAlchemy
        pass
    
    def _get_method(self, method_id: int) -> Method:
        """Load method configuration."""
        # Implementation uses SQLAlchemy
        pass
```

---

## Exit Evaluation

See `PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md` for complete specification of:
- Exit condition checking
- Priority resolution
- Partial exit detection

---

## Exit Execution

See `PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md` for complete specification of:
- Urgency-based execution strategies
- Failed exit handling
- Progressive escalation

---

## Database Schema

### Positions Table Updates

```sql
-- Add real-time monitoring fields
ALTER TABLE positions ADD COLUMN IF NOT EXISTS current_price DECIMAL(10,4);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS unrealized_pnl DECIMAL(10,2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS unrealized_pnl_pct DECIMAL(6,4);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS last_update TIMESTAMP;

-- Trailing stop fields
ALTER TABLE positions ADD COLUMN IF NOT EXISTS trailing_stop_active BOOLEAN DEFAULT FALSE;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS peak_price DECIMAL(10,4);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS trailing_stop_price DECIMAL(10,4);

-- Exit tracking
ALTER TABLE positions ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(50);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS exit_priority VARCHAR(20);
```

### Position Exits Table

```sql
CREATE TABLE position_exits (
    exit_id SERIAL PRIMARY KEY,
    position_id INT NOT NULL REFERENCES positions(position_id),
    
    -- Exit details
    exit_reason VARCHAR(50) NOT NULL,  -- "stop_loss", "profit_target", etc.
    exit_priority VARCHAR(20) NOT NULL,  -- "CRITICAL", "HIGH", "MEDIUM", "LOW"
    exit_quantity INT NOT NULL,
    partial_exit BOOLEAN DEFAULT FALSE,
    
    -- Execution details
    exit_price DECIMAL(10,4) NOT NULL,
    execution_strategy VARCHAR(20),  -- "market", "limit", "aggressive_limit"
    
    -- Performance
    unrealized_pnl DECIMAL(10,2),
    unrealized_pnl_pct DECIMAL(6,4),
    
    -- Timestamps
    triggered_at TIMESTAMP DEFAULT NOW(),
    executed_at TIMESTAMP,
    
    -- For partial exits
    remaining_quantity INT,
    
    INDEX idx_position_exits_position (position_id),
    INDEX idx_position_exits_reason (exit_reason)
);
```

### Exit Attempts Table (For Debugging)

```sql
CREATE TABLE exit_attempts (
    attempt_id SERIAL PRIMARY KEY,
    position_id INT NOT NULL REFERENCES positions(position_id),
    exit_id INT REFERENCES position_exits(exit_id),
    
    -- Attempt details
    attempt_number INT NOT NULL,
    order_type VARCHAR(20),  -- "market", "limit"
    limit_price DECIMAL(10,4),
    quantity INT NOT NULL,
    
    -- Result
    status VARCHAR(20),  -- "pending", "filled", "partial", "cancelled", "failed"
    filled_quantity INT DEFAULT 0,
    filled_price DECIMAL(10,4),
    
    -- Timing
    placed_at TIMESTAMP DEFAULT NOW(),
    filled_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    
    -- Error tracking
    error_message TEXT,
    
    INDEX idx_exit_attempts_position (position_id),
    INDEX idx_exit_attempts_exit (exit_id)
);
```

---

## Configuration

### position_management.yaml Updates

```yaml
# config/position_management.yaml

monitoring:
  # Monitoring frequencies (seconds)
  normal_frequency: 30      # Standard monitoring
  urgent_frequency: 5       # Near thresholds
  
  # Urgency triggers
  urgent_conditions:
    near_stop_loss_pct: 0.02      # Within 2% of stop loss
    near_profit_target_pct: 0.02  # Within 2% of profit target
    near_trailing_stop_pct: 0.02  # Within 2% of trailing stop
  
  # Cache settings
  price_cache_ttl_seconds: 10
  
  # Rate limiting
  max_api_calls_per_minute: 60  # Conservative limit

# Exit priorities
exit_priorities:
  CRITICAL:
    - stop_loss
    - circuit_breaker
  
  HIGH:
    - trailing_stop
    - time_based_urgent  # <5min to settlement
    - liquidity_dried_up  # Spread >3¢
  
  MEDIUM:
    - profit_target
    - partial_exit_target
  
  LOW:
    - early_exit  # Edge < threshold
    - edge_disappeared  # Edge negative
    - rebalance

# Trailing stops
trailing_stop:
  enabled: true
  activation_threshold: 0.10  # Activate after 10% profit
  initial_distance: 0.05      # 5% trail distance
  tightening_rate: 0.01       # Tighten 1% per 5% gain
  floor_distance: 0.02        # Minimum 2% trail

# Exit execution strategies
exit_execution:
  CRITICAL:
    order_type: market
    timeout_seconds: 5
    retry_strategy: immediate_market
  
  HIGH:
    order_type: limit
    price_adjustment: aggressive  # Cross spread slightly
    timeout_seconds: 10
    retry_strategy: walk_then_market
    max_walks: 2
  
  MEDIUM:
    order_type: limit
    price_adjustment: fair  # Mid-spread
    timeout_seconds: 30
    retry_strategy: walk_price
    max_walks: 5
  
  LOW:
    order_type: limit
    price_adjustment: conservative  # Best ask
    timeout_seconds: 60
    retry_strategy: walk_slowly
    max_walks: 10
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_position_monitor.py

def test_monitoring_frequency_urgent():
    """Test that urgent positions check every 5s."""
    position = create_test_position(unrealized_pnl_pct=-0.13)  # Near stop loss
    method = create_test_method(stop_loss=-0.15)
    
    monitor = PositionMonitor(...)
    interval = monitor._calculate_sleep_interval(position, method)
    
    assert interval == 5  # Urgent

def test_monitoring_frequency_normal():
    """Test that normal positions check every 30s."""
    position = create_test_position(unrealized_pnl_pct=0.05)  # Stable
    method = create_test_method()
    
    monitor = PositionMonitor(...)
    interval = monitor._calculate_sleep_interval(position, method)
    
    assert interval == 30  # Normal

def test_trailing_stop_activation():
    """Test trailing stop activates at threshold."""
    position = create_test_position(
        entry_price=Decimal("0.60"),
        unrealized_pnl_pct=Decimal("0.10")  # At activation
    )
    method = create_test_method(
        trailing_stop_config={
            'enabled': True,
            'activation_threshold': 0.10,
            'initial_distance': 0.05
        }
    )
    
    monitor = PositionMonitor(...)
    monitor._update_trailing_stop(
        position,
        current_price=Decimal("0.66"),
        method=method
    )
    
    assert position.trailing_stop_active
    assert position.peak_price == Decimal("0.66")
    assert position.trailing_stop_price == Decimal("0.627")  # 0.66 * 0.95

def test_price_caching():
    """Test that prices are cached to reduce API calls."""
    monitor = PositionMonitor(...)
    
    # First call should hit API
    price1 = await monitor._get_current_price("TEST-MARKET")
    api_calls_1 = monitor.api_calls_per_minute
    
    # Second call (within 10s) should use cache
    price2 = await monitor._get_current_price("TEST-MARKET")
    api_calls_2 = monitor.api_calls_per_minute
    
    assert price1 == price2
    assert api_calls_2 == api_calls_1  # No new API call

def test_rate_limiting():
    """Test rate limit enforcement."""
    monitor = PositionMonitor(...)
    monitor.api_calls_per_minute = 59
    
    # This should work (at limit)
    await monitor._check_rate_limit()
    assert monitor.api_calls_per_minute == 60
    
    # This should sleep to avoid exceeding
    start = time.time()
    await monitor._check_rate_limit()
    elapsed = time.time() - start
    
    assert elapsed > 0.5  # Slept to reset counter
```

### Integration Tests

```python
# tests/integration/test_position_monitoring.py

@pytest.mark.asyncio
async def test_complete_monitoring_cycle():
    """Test complete cycle: monitor → detect exit → execute."""
    
    # Create test position
    position = create_test_position(
        entry_price=Decimal("0.60"),
        count=50
    )
    
    # Mock Kalshi API
    with patch('kalshi_client.get_market') as mock_market:
        mock_market.return_value = Market(
            market_id="TEST",
            yes_bid=Decimal("0.50")  # Down 16.7% - triggers stop loss
        )
        
        # Start monitoring
        monitor = PositionMonitor(...)
        task = asyncio.create_task(
            monitor._monitor_single_position(position)
        )
        
        # Wait for exit to trigger
        await asyncio.sleep(2)
        
        # Verify exit was executed
        position = refresh_position(position.position_id)
        assert position.status == "closed"
        assert position.exit_reason == "stop_loss"
```

---

## Performance Metrics

### Monitoring Performance

```sql
-- Average monitoring cycle time
SELECT
    AVG(EXTRACT(EPOCH FROM (next_check - this_check))) as avg_cycle_seconds,
    MIN(EXTRACT(EPOCH FROM (next_check - this_check))) as min_cycle_seconds,
    MAX(EXTRACT(EPOCH FROM (next_check - this_check))) as max_cycle_seconds
FROM (
    SELECT
        position_id,
        last_update as this_check,
        LEAD(last_update) OVER (PARTITION BY position_id ORDER BY last_update) as next_check
    FROM positions
    WHERE status = 'open'
    AND last_update >= NOW() - INTERVAL '1 day'
) cycles
WHERE next_check IS NOT NULL;

-- Expected: avg ~30s, min ~5s (urgent), max ~60s
```

### Exit Efficiency

```sql
-- Time from trigger to execution
SELECT
    exit_reason,
    exit_priority,
    AVG(EXTRACT(EPOCH FROM (executed_at - triggered_at))) as avg_execution_seconds,
    COUNT(*) as exit_count
FROM position_exits
WHERE executed_at IS NOT NULL
AND triggered_at >= NOW() - INTERVAL '7 days'
GROUP BY exit_reason, exit_priority
ORDER BY exit_priority, avg_execution_seconds;

-- Expected:
-- CRITICAL: <10s
-- HIGH: <20s
-- MEDIUM: <40s
-- LOW: <90s
```

### API Usage

```sql
-- API calls per hour (from monitoring)
SELECT
    DATE_TRUNC('hour', last_update) as hour,
    COUNT(DISTINCT position_id) as positions_monitored,
    COUNT(*) as total_checks,
    COUNT(*) / 60.0 as checks_per_minute
FROM positions
WHERE last_update >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', last_update)
ORDER BY hour DESC;

-- Expected: <60 calls/minute (rate limit safe)
```

---

## Risk Mitigation

### Risk 1: Missed Exit Triggers

**Risk:** Monitor loop crashes or falls behind, missing critical exits

**Mitigation:**
- Health check: Alert if no position updates in >2 minutes
- Supervisor process: Restart monitor on crash
- Fallback: Daily batch job closes positions at extreme losses

### Risk 2: Rate Limit Exceeded

**Risk:** Too many positions cause API rate limit hits

**Mitigation:**
- Conservative limit: 60 calls/minute vs 600 available
- Price caching: 10s TTL reduces calls by 66%
- Dynamic frequency: Only 5s checks for urgent cases

### Risk 3: Database Deadlocks

**Risk:** Multiple monitors updating same position causes deadlocks

**Mitigation:**
- Optimistic locking: Use position.version for updates
- Retry logic: Auto-retry on deadlock (max 3 attempts)
- Read-heavy design: Most ops are reads, writes only on exit

---

## Summary

**Position Monitoring System provides:**
- ✅ Continuous monitoring of all open positions
- ✅ Dynamic frequency (5s urgent, 30s normal)
- ✅ Rate limit awareness (price caching, throttling)
- ✅ Real-time P&L tracking
- ✅ Trailing stop updates
- ✅ Priority-based exit handling
- ✅ Comprehensive logging and metrics

**Implementation Order:**
1. PositionMonitor (core loop)
2. P&L calculator
3. Trailing stop updater
4. Integration with ExitEvaluator
5. Integration with ExitExecutor
6. Testing and validation

**Success Criteria:**
- [ ] All open positions monitored continuously
- [ ] Average monitoring cycle < 35s (normal)
- [ ] Urgent positions checked every 5-10s
- [ ] API usage < 60 calls/minute
- [ ] No missed exit triggers (0% miss rate)
- [ ] Trailing stops update within 30s of price movement

---

**Next Document:** See `PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md` for exit condition logic.
