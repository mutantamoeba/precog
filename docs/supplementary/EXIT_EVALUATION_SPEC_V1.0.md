# Exit Evaluation Logic Specification
**Version:** 1.0
**Date:** 2025-10-21
**Last Updated:** 2025-10-28 (Phase 0.6b - Filename standardization)
**Status:** 🔵 Design Complete - Ready for Implementation
**Phase:** 5a (Trading MVP)
**Dependencies:** Phase 1-4 (Infrastructure, Data, Models)
**Related:** ADR-021 (Method Abstraction), ADR-036, POSITION_MONITORING_SPEC_V1.0.md
**Filename Updated:** Renamed from PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md to EXIT_EVALUATION_SPEC_V1.0.md

---

## Executive Summary

**Goal:** Evaluate all exit conditions for open positions and determine when/how to exit.

**Key Components:**
1. **ExitEvaluator** - Checks all exit conditions with priority resolution
2. **ExitExecutor** - Executes exit orders with urgency-based strategies
3. **PartialExitHandler** - Manages scaling out of positions
4. **FailedExitHandler** - Handles unfilled orders with progressive escalation

**Design Principles:**
- **Priority-based**: Critical exits take precedence
- **Non-redundant**: Removed overlapping conditions (edge_reversal)
- **Method-aware**: Uses Method configuration for all thresholds
- **Urgency-adaptive**: Execution strategy varies by exit priority

---

## Table of Contents

1. [Exit Conditions Hierarchy](#exit-conditions-hierarchy)
2. [ExitEvaluator Class](#exitevaluator-class)
3. [ExitExecutor Class](#exitexecutor-class)
4. [Partial Exit Handling](#partial-exit-handling)
5. [Failed Exit Handling](#failed-exit-handling)
6. [Configuration](#configuration)
7. [Testing Strategy](#testing-strategy)

---

## Exit Conditions Hierarchy

### Priority Levels

```python
class ExitPriority(IntEnum):
    """Exit priority levels (lower number = higher priority)."""
    CRITICAL = 1    # Immediate, capital protection
    HIGH = 2        # Fast exit needed
    MEDIUM = 3      # Normal exit
    LOW = 4         # Opportunistic exit
```

### Complete Exit Conditions

**Note:** `edge_reversal` was REMOVED as redundant with `early_exit` and `edge_disappeared`.

```python
EXIT_CONDITIONS = {
    # ==================
    # CRITICAL (Priority 1) - Capital Protection
    # ==================

    "stop_loss": {
        "priority": ExitPriority.CRITICAL,
        "description": "Hard stop loss hit",
        "check": lambda pos, method: (
            pos.unrealized_pnl_pct < method.position_mgmt_config['stop_loss']['threshold']
        ),
        "quantity": "full",  # Exit entire position
        "execution": {
            "order_type": "market",
            "timeout": 5,
            "retry": "immediate_market"
        }
    },

    "circuit_breaker": {
        "priority": ExitPriority.CRITICAL,
        "description": "Account-level risk limit breached",
        "check": lambda: daily_loss_exceeds_limit(),
        "quantity": "all_positions",  # Close ALL open positions
        "execution": {
            "order_type": "market",
            "timeout": 5,
            "retry": "immediate_market"
        }
    },

    # ==================
    # HIGH (Priority 2) - Risk Management
    # ==================

    "trailing_stop": {
        "priority": ExitPriority.HIGH,
        "description": "Trailing stop activated and hit",
        "check": lambda pos: (
            pos.trailing_stop_active and
            pos.current_price <= pos.trailing_stop_price
        ),
        "quantity": "full",
        "execution": {
            "order_type": "limit",
            "price_strategy": "aggressive",  # Cross spread
            "timeout": 10,
            "retry": "walk_then_market",
            "max_walks": 2
        }
    },

    "time_based_urgent": {
        "priority": ExitPriority.HIGH,
        "description": "Market closing soon",
        "check": lambda pos: time_to_settlement(pos) < timedelta(minutes=5),
        "quantity": "full",
        "execution": {
            "order_type": "limit",
            "price_strategy": "aggressive",
            "timeout": 10,
            "retry": "walk_then_market",
            "max_walks": 2
        }
    },

    "liquidity_dried_up": {
        "priority": ExitPriority.HIGH,
        "description": "Market became illiquid (from Grok)",
        "check": lambda pos, market: (
            market.spread > Decimal("0.03") or  # Spread >3¢
            market.volume < 50  # Volume <50 contracts
        ),
        "quantity": "full",
        "execution": {
            "order_type": "limit",
            "price_strategy": "aggressive",
            "timeout": 15,
            "retry": "walk_then_market",
            "max_walks": 3
        }
    },

    # ==================
    # MEDIUM (Priority 3) - Profit Taking
    # ==================

    "profit_target": {
        "priority": ExitPriority.MEDIUM,
        "description": "Profit target reached",
        "check": lambda pos, method: (
            pos.unrealized_pnl_pct >=
            method.position_mgmt_config['profit_targets']['threshold']
        ),
        "quantity": "full_or_partial",  # Check partial exit config
        "execution": {
            "order_type": "limit",
            "price_strategy": "fair",  # Mid-spread
            "timeout": 30,
            "retry": "walk_price",
            "max_walks": 5
        }
    },

    "partial_exit_target": {
        "priority": ExitPriority.MEDIUM,
        "description": "Partial exit threshold reached",
        "check": lambda pos, method: check_partial_exit_conditions(pos, method),
        "quantity": "partial",  # From partial_exits config
        "execution": {
            "order_type": "limit",
            "price_strategy": "fair",
            "timeout": 30,
            "retry": "walk_price",
            "max_walks": 5
        }
    },

    # ==================
    # LOW (Priority 4) - Optimization
    # ==================

    "early_exit": {
        "priority": ExitPriority.LOW,
        "description": "Edge dropped below minimum threshold",
        "check": lambda pos, method: (
            calculate_current_edge(pos) <
            method.position_mgmt_config['early_exit']['threshold']
        ),
        "quantity": "full",
        "execution": {
            "order_type": "limit",
            "price_strategy": "conservative",  # Best ask
            "timeout": 60,
            "retry": "walk_slowly",
            "max_walks": 10
        }
    },

    "edge_disappeared": {
        "priority": ExitPriority.LOW,
        "description": "Edge turned negative",
        "check": lambda pos: calculate_current_edge(pos) < 0,
        "quantity": "full",
        "execution": {
            "order_type": "limit",
            "price_strategy": "fair",
            "timeout": 30,
            "retry": "walk_price",
            "max_walks": 5
        }
    },

    "rebalance": {
        "priority": ExitPriority.LOW,
        "description": "Portfolio rebalancing needed",
        "check": lambda pos: (
            check_better_opportunity_exists() and
            pos.unrealized_pnl_pct > 0  # Don't sell losers for rebalancing
        ),
        "quantity": "full",
        "execution": {
            "order_type": "limit",
            "price_strategy": "conservative",
            "timeout": 60,
            "retry": "walk_slowly",
            "max_walks": 10
        }
    }
}
```

### Why Edge Reversal Was Removed

**Original Proposal:** Exit if model probability shifts >10% against position

**Removed Because:** Redundant with existing conditions

**Scenarios:**

| Scenario | Edge Change | Existing Condition | Redundancy |
|----------|------------|-------------------|------------|
| Prob drops 10%, edge negative | -10pp | `edge_disappeared` triggers | ✅ Covered |
| Prob drops 10%, edge = 2% | -10pp | `early_exit` likely triggers | ✅ Covered |
| Prob drops 10%, still profitable | -10pp | Trailing stop or profit target handles | ✅ Covered |
| Massive prob drop, losing money | -20pp | `stop_loss` triggers | ✅ Covered |

**Conclusion:** The combination of `stop_loss`, `early_exit`, and `edge_disappeared` covers all cases where edge deteriorates significantly.

---

## ExitEvaluator Class

```python
# trading/exit_evaluator.py

import logging
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass

from database.models import Position, Method, Market

logger = logging.getLogger(__name__)


@dataclass
class ExitTrigger:
    """
    Represents a triggered exit condition.

    Attributes:
        reason: Exit condition name (e.g., "stop_loss")
        priority: Exit priority level
        quantity: How much to exit ("full", "partial", or int)
        execution_params: How to execute the exit
        metadata: Additional context for logging
    """
    reason: str
    priority: int  # ExitPriority value
    quantity: str | int  # "full", "partial", or specific count
    execution_params: dict
    metadata: dict
    timestamp: datetime = datetime.now()


class ExitEvaluator:
    """
    Evaluates all exit conditions and determines when to exit.

    Features:
    - Checks all conditions in priority order
    - Resolves conflicts (multiple triggers)
    - Calculates partial exit quantities
    - Logs all decisions for analysis
    """

    def __init__(self, kalshi_client):
        self.kalshi_client = kalshi_client

    def check_exit_conditions(
        self,
        position: Position,
        current_price: Decimal,
        method: Method
    ) -> Optional[ExitTrigger]:
        """
        Check all exit conditions for a position.

        Priority resolution:
        - If multiple conditions trigger, execute highest priority
        - Log all triggered conditions for analysis

        Args:
            position: Position to evaluate
            current_price: Current market price
            method: Method configuration with exit rules

        Returns:
            ExitTrigger if exit should occur, None otherwise
        """
        all_triggers: List[ExitTrigger] = []

        # Update position with current price (for checks)
        position.current_price = current_price

        # Get current market data (for liquidity checks)
        market = self._get_cached_market(position.market_id)

        # Check each condition

        # CRITICAL: Stop Loss
        trigger = self._check_stop_loss(position, method)
        if trigger:
            all_triggers.append(trigger)

        # CRITICAL: Circuit Breaker
        trigger = self._check_circuit_breaker()
        if trigger:
            all_triggers.append(trigger)

        # HIGH: Trailing Stop
        trigger = self._check_trailing_stop(position)
        if trigger:
            all_triggers.append(trigger)

        # HIGH: Time-Based Urgent
        trigger = self._check_time_based_urgent(position)
        if trigger:
            all_triggers.append(trigger)

        # HIGH: Liquidity Dried Up
        trigger = self._check_liquidity(position, market)
        if trigger:
            all_triggers.append(trigger)

        # MEDIUM: Profit Target
        trigger = self._check_profit_target(position, method)
        if trigger:
            all_triggers.append(trigger)

        # MEDIUM: Partial Exit
        trigger = self._check_partial_exit(position, method)
        if trigger:
            all_triggers.append(trigger)

        # LOW: Early Exit (Edge Threshold)
        trigger = self._check_early_exit(position, method)
        if trigger:
            all_triggers.append(trigger)

        # LOW: Edge Disappeared
        trigger = self._check_edge_disappeared(position)
        if trigger:
            all_triggers.append(trigger)

        # LOW: Rebalance
        trigger = self._check_rebalance(position)
        if trigger:
            all_triggers.append(trigger)

        # Resolve if multiple triggers
        if not all_triggers:
            return None

        return self._resolve_multiple_triggers(all_triggers, position)

    def _check_stop_loss(
        self,
        position: Position,
        method: Method
    ) -> Optional[ExitTrigger]:
        """Check if hard stop loss hit."""

        config = method.position_mgmt_config.get('stop_loss', {})
        threshold = Decimal(str(config.get('threshold', -0.15)))

        if position.unrealized_pnl_pct < threshold:
            return ExitTrigger(
                reason="stop_loss",
                priority=ExitPriority.CRITICAL,
                quantity="full",
                execution_params={
                    "order_type": "market",
                    "timeout": 5,
                    "retry": "immediate_market"
                },
                metadata={
                    "threshold": float(threshold),
                    "current_pnl": float(position.unrealized_pnl_pct),
                    "loss_amount": float(position.unrealized_pnl)
                }
            )

        return None

    def _check_circuit_breaker(self) -> Optional[ExitTrigger]:
        """Check if account-level circuit breaker triggered."""

        # Query daily loss
        daily_loss = self._calculate_daily_loss()
        daily_limit = Decimal(str(config.get('daily_loss_limit', 500)))

        if abs(daily_loss) > daily_limit:
            return ExitTrigger(
                reason="circuit_breaker",
                priority=ExitPriority.CRITICAL,
                quantity="all_positions",
                execution_params={
                    "order_type": "market",
                    "timeout": 5,
                    "retry": "immediate_market"
                },
                metadata={
                    "daily_loss": float(daily_loss),
                    "daily_limit": float(daily_limit),
                    "message": "Account daily loss limit exceeded"
                }
            )

        return None

    def _check_trailing_stop(
        self,
        position: Position
    ) -> Optional[ExitTrigger]:
        """Check if trailing stop hit."""

        if not position.trailing_stop_active:
            return None

        if position.current_price <= position.trailing_stop_price:
            return ExitTrigger(
                reason="trailing_stop",
                priority=ExitPriority.HIGH,
                quantity="full",
                execution_params={
                    "order_type": "limit",
                    "price_strategy": "aggressive",
                    "timeout": 10,
                    "retry": "walk_then_market",
                    "max_walks": 2
                },
                metadata={
                    "peak_price": float(position.peak_price),
                    "stop_price": float(position.trailing_stop_price),
                    "current_price": float(position.current_price),
                    "locked_profit": float(
                        (position.trailing_stop_price - position.entry_price) /
                        position.entry_price
                    )
                }
            )

        return None

    def _check_time_based_urgent(
        self,
        position: Position
    ) -> Optional[ExitTrigger]:
        """Check if market closing soon."""

        time_to_close = self._get_time_to_settlement(position.market_id)

        if time_to_close and time_to_close < timedelta(minutes=5):
            return ExitTrigger(
                reason="time_based_urgent",
                priority=ExitPriority.HIGH,
                quantity="full",
                execution_params={
                    "order_type": "limit",
                    "price_strategy": "aggressive",
                    "timeout": 10,
                    "retry": "walk_then_market",
                    "max_walks": 2
                },
                metadata={
                    "time_to_settlement_seconds": time_to_close.total_seconds(),
                    "message": "Market closing in <5 minutes"
                }
            )

        return None

    def _check_liquidity(
        self,
        position: Position,
        market: Market
    ) -> Optional[ExitTrigger]:
        """Check if market liquidity dried up (from Grok)."""

        # Check spread
        if market.spread > Decimal("0.03"):
            return ExitTrigger(
                reason="liquidity_dried_up",
                priority=ExitPriority.HIGH,
                quantity="full",
                execution_params={
                    "order_type": "limit",
                    "price_strategy": "aggressive",
                    "timeout": 15,
                    "retry": "walk_then_market",
                    "max_walks": 3
                },
                metadata={
                    "spread": float(market.spread),
                    "spread_threshold": 0.03,
                    "reason": "Spread too wide"
                }
            )

        # Check volume
        if market.volume < 50:
            return ExitTrigger(
                reason="liquidity_dried_up",
                priority=ExitPriority.HIGH,
                quantity="full",
                execution_params={
                    "order_type": "limit",
                    "price_strategy": "aggressive",
                    "timeout": 15,
                    "retry": "walk_then_market",
                    "max_walks": 3
                },
                metadata={
                    "volume": market.volume,
                    "volume_threshold": 50,
                    "reason": "Volume too low"
                }
            )

        return None

    def _check_profit_target(
        self,
        position: Position,
        method: Method
    ) -> Optional[ExitTrigger]:
        """Check if profit target reached."""

        config = method.position_mgmt_config.get('profit_targets', {})

        # Get confidence-adjusted target
        confidence = self._get_edge_confidence(position)
        target_key = f"{confidence}_confidence"
        threshold = Decimal(str(config.get(target_key, 0.20)))

        if position.unrealized_pnl_pct >= threshold:
            # Check if partial exits configured
            partial_config = method.position_mgmt_config.get('partial_exits', {})

            if partial_config.get('enabled', False):
                quantity = "partial"  # Let partial handler determine amount
            else:
                quantity = "full"

            return ExitTrigger(
                reason="profit_target",
                priority=ExitPriority.MEDIUM,
                quantity=quantity,
                execution_params={
                    "order_type": "limit",
                    "price_strategy": "fair",
                    "timeout": 30,
                    "retry": "walk_price",
                    "max_walks": 5
                },
                metadata={
                    "target_threshold": float(threshold),
                    "current_profit": float(position.unrealized_pnl_pct),
                    "confidence": confidence,
                    "profit_amount": float(position.unrealized_pnl)
                }
            )

        return None

    def _check_partial_exit(
        self,
        position: Position,
        method: Method
    ) -> Optional[ExitTrigger]:
        """Check if partial exit threshold reached."""

        config = method.position_mgmt_config.get('partial_exits', {})

        if not config.get('enabled', False):
            return None

        # Check each stage
        for stage in config.get('stages', []):
            # Skip if already executed
            if self._stage_already_executed(position, stage['name']):
                continue

            # Check if threshold reached
            threshold = Decimal(str(stage['profit_threshold']))
            if position.unrealized_pnl_pct >= threshold:
                # Calculate quantity
                exit_pct = stage['exit_percentage'] / 100
                exit_quantity = int(position.count * exit_pct)

                return ExitTrigger(
                    reason=f"partial_exit_{stage['name']}",
                    priority=ExitPriority.MEDIUM,
                    quantity=exit_quantity,
                    execution_params={
                        "order_type": "limit",
                        "price_strategy": "fair",
                        "timeout": 30,
                        "retry": "walk_price",
                        "max_walks": 5
                    },
                    metadata={
                        "stage": stage['name'],
                        "threshold": float(threshold),
                        "exit_percentage": stage['exit_percentage'],
                        "exit_quantity": exit_quantity,
                        "remaining_quantity": position.count - exit_quantity
                    }
                )

        return None

    def _check_early_exit(
        self,
        position: Position,
        method: Method
    ) -> Optional[ExitTrigger]:
        """Check if edge dropped below minimum threshold."""

        config = method.position_mgmt_config.get('early_exit', {})

        if not config.get('enabled', True):
            return None

        threshold = Decimal(str(config.get('edge_threshold', 0.02)))

        # Calculate current edge
        current_edge = self._calculate_current_edge(position)

        if current_edge < threshold:
            return ExitTrigger(
                reason="early_exit",
                priority=ExitPriority.LOW,
                quantity="full",
                execution_params={
                    "order_type": "limit",
                    "price_strategy": "conservative",
                    "timeout": 60,
                    "retry": "walk_slowly",
                    "max_walks": 10
                },
                metadata={
                    "edge_threshold": float(threshold),
                    "current_edge": float(current_edge),
                    "message": "Edge dropped below minimum threshold"
                }
            )

        return None

    def _check_edge_disappeared(
        self,
        position: Position
    ) -> Optional[ExitTrigger]:
        """Check if edge turned negative."""

        current_edge = self._calculate_current_edge(position)

        if current_edge < 0:
            return ExitTrigger(
                reason="edge_disappeared",
                priority=ExitPriority.LOW,
                quantity="full",
                execution_params={
                    "order_type": "limit",
                    "price_strategy": "fair",
                    "timeout": 30,
                    "retry": "walk_price",
                    "max_walks": 5
                },
                metadata={
                    "current_edge": float(current_edge),
                    "message": "Edge turned negative"
                }
            )

        return None

    def _check_rebalance(
        self,
        position: Position
    ) -> Optional[ExitTrigger]:
        """Check if portfolio rebalancing needed."""

        # Only rebalance profitable positions
        if position.unrealized_pnl_pct <= 0:
            return None

        # Check if better opportunity exists
        if not self._better_opportunity_exists(position):
            return None

        return ExitTrigger(
            reason="rebalance",
            priority=ExitPriority.LOW,
            quantity="full",
            execution_params={
                "order_type": "limit",
                "price_strategy": "conservative",
                "timeout": 60,
                "retry": "walk_slowly",
                "max_walks": 10
            },
            metadata={
                "current_profit": float(position.unrealized_pnl_pct),
                "message": "Better opportunity available"
            }
        )

    def _resolve_multiple_triggers(
        self,
        all_triggers: List[ExitTrigger],
        position: Position
    ) -> ExitTrigger:
        """
        Resolve conflicts when multiple exit conditions trigger.

        Resolution strategy:
        1. Sort by priority (lowest number = highest priority)
        2. Execute highest priority trigger
        3. Log all triggered conditions for analysis

        Args:
            all_triggers: List of all triggered exit conditions
            position: Position being evaluated

        Returns:
            The exit trigger to execute
        """
        # Sort by priority (CRITICAL=1 first)
        all_triggers.sort(key=lambda t: t.priority)

        highest_priority = all_triggers[0]

        # Log conflict if multiple triggers
        if len(all_triggers) > 1:
            reasons = [t.reason for t in all_triggers]
            logger.info(
                f"Multiple exit triggers for position {position.position_id}: "
                f"{reasons}. Executing: {highest_priority.reason} "
                f"(Priority {highest_priority.priority})"
            )

            # Store all triggers in metadata for analysis
            highest_priority.metadata['conflicting_triggers'] = [
                {"reason": t.reason, "priority": t.priority}
                for t in all_triggers[1:]
            ]

        return highest_priority

    def _calculate_current_edge(self, position: Position) -> Decimal:
        """
        Calculate current edge for position.

        Edge = Model Probability - Market Implied Probability

        This requires re-running the probability model with current
        game state / market conditions.
        """
        # TODO: Implement probability model re-calculation
        # For now, placeholder
        return Decimal("0.05")

    def _get_cached_market(self, market_id: str) -> Market:
        """Get cached market data (price caching handled by PositionMonitor)."""
        # Implementation
        pass

    def _get_time_to_settlement(self, market_id: str) -> Optional[timedelta]:
        """Calculate time remaining until market settles."""
        # Implementation
        pass

    def _get_edge_confidence(self, position: Position) -> str:
        """Get confidence level of edge (high/medium/low)."""
        # Implementation
        pass

    def _stage_already_executed(self, position: Position, stage_name: str) -> bool:
        """Check if partial exit stage already executed."""
        # Implementation
        pass

    def _calculate_daily_loss(self) -> Decimal:
        """Calculate total P&L for today."""
        # Implementation
        pass

    def _better_opportunity_exists(self, position: Position) -> bool:
        """Check if better opportunity available for rebalancing."""
        # Implementation
        pass
```

---

## ExitExecutor Class

```python
# trading/exit_executor.py

import asyncio
import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime

from database.models import Position, Order
from trading.exit_evaluator import ExitTrigger
from api.kalshi_client import KalshiClient

logger = logging.getLogger(__name__)


class ExitExecutor:
    """
    Executes exit orders based on exit triggers.

    Features:
    - Urgency-based execution (market vs limit)
    - Failed order handling with escalation
    - Price walking for unfilled limits
    - Comprehensive logging
    """

    def __init__(self, kalshi_client: KalshiClient):
        self.kalshi_client = kalshi_client

    async def execute_exit(
        self,
        position: Position,
        trigger: ExitTrigger
    ):
        """
        Execute position exit based on trigger.

        Flow:
        1. Determine quantity to exit
        2. Calculate exit price (if limit order)
        3. Place order
        4. Monitor fill status
        5. Handle unfilled orders (escalation)
        6. Update position

        Args:
            position: Position to exit
            trigger: Exit trigger with execution params
        """
        logger.info(
            f"Executing exit for position {position.position_id}: "
            f"{trigger.reason} (Priority {trigger.priority})"
        )

        # Determine quantity
        exit_quantity = self._determine_exit_quantity(position, trigger)

        # Get execution parameters
        exec_params = trigger.execution_params
        order_type = exec_params['order_type']

        # Place order
        if order_type == "market":
            order = await self._place_market_order(position, exit_quantity)
        else:
            # Limit order
            price_strategy = exec_params.get('price_strategy', 'fair')
            exit_price = self._calculate_exit_price(
                position,
                price_strategy
            )
            order = await self._place_limit_order(
                position,
                exit_quantity,
                exit_price
            )

        # Monitor and handle unfilled
        await self._monitor_and_escalate(
            position=position,
            order=order,
            trigger=trigger
        )

        # Update position
        self._update_position_after_exit(
            position=position,
            order=order,
            trigger=trigger
        )

        logger.info(
            f"Exit completed for position {position.position_id}: "
            f"{exit_quantity} @ {order.filled_price}"
        )

    async def _place_market_order(
        self,
        position: Position,
        quantity: int
    ) -> Order:
        """Place market order for immediate execution."""

        order = await self.kalshi_client.place_order(
            ticker=position.market_id,
            side=position.side,  # "yes" or "no"
            action="sell",  # Always sell for exit
            type="market",
            count=quantity
        )

        logger.info(
            f"Market order placed: {quantity} {position.side} "
            f"@ market (Order ID: {order.order_id})"
        )

        return order

    async def _place_limit_order(
        self,
        position: Position,
        quantity: int,
        price: Decimal
    ) -> Order:
        """Place limit order at calculated price."""

        order = await self.kalshi_client.place_order(
            ticker=position.market_id,
            side=position.side,
            action="sell",
            type="limit",
            count=quantity,
            price=price
        )

        logger.info(
            f"Limit order placed: {quantity} {position.side} "
            f"@ {price} (Order ID: {order.order_id})"
        )

        return order

    async def _monitor_and_escalate(
        self,
        position: Position,
        order: Order,
        trigger: ExitTrigger
    ):
        """
        Monitor order fill and escalate if needed.

        Escalation strategies:
        - immediate_market: Use market order immediately
        - walk_then_market: Walk price, then market
        - walk_price: Walk price up to max walks
        - walk_slowly: Patient walking

        Args:
            position: Position being exited
            order: Order that was placed
            trigger: Exit trigger with retry strategy
        """
        if order.type == "market":
            # Market orders fill immediately (or fail fast)
            await self._wait_for_fill(order, timeout_seconds=5)
            return

        # Limit order - may need escalation
        exec_params = trigger.execution_params
        timeout = exec_params.get('timeout', 30)
        retry_strategy = exec_params.get('retry', 'walk_price')
        max_walks = exec_params.get('max_walks', 5)

        # Wait for initial fill
        filled = await self._wait_for_fill(order, timeout_seconds=timeout)

        if filled:
            return  # Success!

        # Order didn't fill - escalate
        logger.warning(
            f"Order {order.order_id} not filled in {timeout}s, "
            f"escalating with strategy: {retry_strategy}"
        )

        if retry_strategy == "immediate_market":
            await self._escalate_to_market(order, position)

        elif retry_strategy == "walk_then_market":
            await self._walk_then_market(order, position, max_walks=2)

        elif retry_strategy == "walk_price":
            await self._walk_price(order, position, max_walks=max_walks)

        elif retry_strategy == "walk_slowly":
            await self._walk_slowly(order, position, max_walks=max_walks)

    async def _wait_for_fill(
        self,
        order: Order,
        timeout_seconds: int
    ) -> bool:
        """
        Wait for order to fill.

        Args:
            order: Order to monitor
            timeout_seconds: How long to wait

        Returns:
            True if filled, False if timeout
        """
        start_time = datetime.now()

        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            # Check order status
            updated_order = await self.kalshi_client.get_order(order.order_id)

            if updated_order.status == "filled":
                logger.info(f"Order {order.order_id} filled")
                order.status = "filled"
                order.filled_price = updated_order.filled_price
                order.filled_quantity = updated_order.filled_quantity
                return True

            elif updated_order.status == "cancelled":
                logger.warning(f"Order {order.order_id} was cancelled")
                return False

            # Check every 2 seconds
            await asyncio.sleep(2)

        logger.warning(f"Order {order.order_id} timeout after {timeout_seconds}s")
        return False

    async def _escalate_to_market(
        self,
        old_order: Order,
        position: Position
    ):
        """Cancel limit and use market order."""

        # Cancel old order
        await self.kalshi_client.cancel_order(old_order.order_id)

        # Place market order
        market_order = await self._place_market_order(
            position,
            old_order.quantity
        )

        # Wait for fill (fast)
        await self._wait_for_fill(market_order, timeout_seconds=5)

        logger.info(
            f"Escalated to market order: {market_order.order_id} "
            f"filled @ {market_order.filled_price}"
        )

    async def _walk_then_market(
        self,
        old_order: Order,
        position: Position,
        max_walks: int
    ):
        """Try walking price, then fallback to market."""

        for walk_num in range(max_walks):
            # Walk price
            new_order = await self._walk_price_once(
                old_order,
                position,
                aggressiveness=1.5 + (walk_num * 0.5)
            )

            # Wait for fill
            filled = await self._wait_for_fill(new_order, timeout_seconds=10)
            if filled:
                return

            old_order = new_order

        # Still not filled - use market
        logger.warning(f"Position {position.position_id}: walks failed, using market")
        await self._escalate_to_market(old_order, position)

    async def _walk_price(
        self,
        old_order: Order,
        position: Position,
        max_walks: int
    ):
        """Walk price up to max_walks times."""

        for walk_num in range(max_walks):
            # Walk price
            new_order = await self._walk_price_once(
                old_order,
                position,
                aggressiveness=1.0 + (walk_num * 0.5)
            )

            # Wait for fill
            filled = await self._wait_for_fill(new_order, timeout_seconds=15)
            if filled:
                return

            old_order = new_order

        # After max walks, give up (position stays open)
        logger.warning(
            f"Position {position.position_id}: "
            f"exit not filled after {max_walks} walks"
        )

    async def _walk_slowly(
        self,
        old_order: Order,
        position: Position,
        max_walks: int
    ):
        """Patient walking for LOW priority exits."""

        for walk_num in range(max_walks):
            # Walk price slowly
            new_order = await self._walk_price_once(
                old_order,
                position,
                aggressiveness=1.0 + (walk_num * 0.3)
            )

            # Wait longer for fill
            filled = await self._wait_for_fill(new_order, timeout_seconds=30)
            if filled:
                return

            old_order = new_order

    async def _walk_price_once(
        self,
        old_order: Order,
        position: Position,
        aggressiveness: float
    ) -> Order:
        """
        Walk price by one step.

        Args:
            old_order: Order to replace
            position: Position being exited
            aggressiveness: How much to walk (1.0 = 1¢, 2.0 = 2¢)

        Returns:
            New order at walked price
        """
        # Cancel old order
        await self.kalshi_client.cancel_order(old_order.order_id)

        # Calculate new price (more aggressive)
        market = await self.kalshi_client.get_market(position.market_id)
        walk_amount = Decimal("0.01") * Decimal(str(aggressiveness))

        if position.side == "yes":
            # Selling yes: reduce price to fill faster
            new_price = old_order.price - walk_amount
            # Floor at best bid minus spread
            new_price = max(new_price, market.yes_bid - market.spread)
        else:
            # Selling no: reduce price
            new_price = old_order.price - walk_amount
            new_price = max(new_price, market.no_bid - market.spread)

        # Place new order
        new_order = await self._place_limit_order(
            position,
            old_order.quantity,
            new_price
        )

        logger.info(
            f"Walked price: {old_order.price} → {new_price} "
            f"(aggressiveness={aggressiveness})"
        )

        return new_order

    def _calculate_exit_price(
        self,
        position: Position,
        strategy: str
    ) -> Decimal:
        """
        Calculate exit price based on strategy.

        Strategies:
        - aggressive: Cross spread (fast fill)
        - fair: Mid-spread (balanced)
        - conservative: Best ask (best price)

        Args:
            position: Position being exited
            strategy: Price strategy

        Returns:
            Exit price
        """
        market = self.kalshi_client.get_market_cached(position.market_id)

        if position.side == "yes":
            bid = market.yes_bid
            ask = market.yes_ask
        else:
            bid = market.no_bid
            ask = market.no_ask

        if strategy == "aggressive":
            # Cross spread slightly for fast fill
            return max(bid - Decimal("0.01"), bid * Decimal("0.98"))

        elif strategy == "fair":
            # Mid-spread
            return (bid + ask) / 2

        elif strategy == "conservative":
            # Try to get ask price
            return ask

        else:
            # Default to fair
            return (bid + ask) / 2

    def _determine_exit_quantity(
        self,
        position: Position,
        trigger: ExitTrigger
    ) -> int:
        """
        Determine how many contracts to exit.

        Args:
            position: Position being exited
            trigger: Exit trigger with quantity spec

        Returns:
            Number of contracts to exit
        """
        if isinstance(trigger.quantity, int):
            return trigger.quantity

        elif trigger.quantity == "full":
            return position.count

        elif trigger.quantity == "partial":
            # Use quantity from trigger metadata
            return trigger.metadata.get('exit_quantity', position.count)

        elif trigger.quantity == "all_positions":
            # Circuit breaker - handled separately
            return position.count

        else:
            logger.warning(
                f"Unknown quantity spec: {trigger.quantity}, "
                f"defaulting to full exit"
            )
            return position.count

    def _update_position_after_exit(
        self,
        position: Position,
        order: Order,
        trigger: ExitTrigger
    ):
        """
        Update position in database after exit.

        Args:
            position: Position that was exited
            order: Exit order
            trigger: Exit trigger
        """
        # Implementation uses SQLAlchemy
        pass
```

---

## Configuration

### position_management.yaml

```yaml
# config/position_management.yaml

# Exit condition thresholds
exit_conditions:
  # CRITICAL exits
  stop_loss:
    threshold: -0.15  # -15% loss

  circuit_breaker:
    daily_loss_limit: 500  # $500 daily loss

  # HIGH priority exits
  trailing_stop:
    enabled: true
    activation_threshold: 0.10
    initial_distance: 0.05
    tightening_rate: 0.01
    floor_distance: 0.02

  time_based_urgent:
    threshold_minutes: 5  # Exit if <5min to settlement

  liquidity:
    max_spread: 0.03  # 3¢ spread
    min_volume: 50    # 50 contracts

  # MEDIUM priority exits
  profit_targets:
    high_confidence: 0.25  # 25%
    medium_confidence: 0.20
    low_confidence: 0.15

  partial_exits:
    enabled: true
    stages:
      - name: "first_target"
        profit_threshold: 0.15
        exit_percentage: 50
      - name: "second_target"
        profit_threshold: 0.25
        exit_percentage: 25

  # LOW priority exits
  early_exit:
    enabled: true
    edge_threshold: 0.02  # 2% minimum edge

  # Note: edge_reversal REMOVED (redundant)

# Exit execution parameters
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
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_exit_evaluator.py

def test_stop_loss_triggers():
    """Test stop loss triggers at threshold."""
    position = create_test_position(unrealized_pnl_pct=-0.16)
    method = create_test_method(stop_loss_threshold=-0.15)

    evaluator = ExitEvaluator(...)
    trigger = evaluator.check_exit_conditions(position, ..., method)

    assert trigger is not None
    assert trigger.reason == "stop_loss"
    assert trigger.priority == ExitPriority.CRITICAL

def test_multiple_triggers_priority():
    """Test priority resolution when multiple conditions trigger."""
    position = create_test_position(
        unrealized_pnl_pct=-0.16,  # Triggers stop loss
        trailing_stop_active=True,
        current_price=Decimal("0.55"),  # Also triggers trailing stop
        trailing_stop_price=Decimal("0.56")
    )
    method = create_test_method()

    evaluator = ExitEvaluator(...)
    trigger = evaluator.check_exit_conditions(position, ..., method)

    # Stop loss (CRITICAL) should take priority over trailing stop (HIGH)
    assert trigger.reason == "stop_loss"
    assert trigger.priority == ExitPriority.CRITICAL
    assert 'conflicting_triggers' in trigger.metadata

def test_edge_reversal_removed():
    """Verify edge_reversal was removed as redundant."""
    evaluator = ExitEvaluator(...)

    # Check that evaluator doesn't have edge_reversal method
    assert not hasattr(evaluator, '_check_edge_reversal')

    # Verify early_exit covers absolute threshold
    position = create_test_position()
    method = create_test_method(early_exit_threshold=0.02)

    # Mock edge calculation to return 1% (below 2% threshold)
    with patch.object(evaluator, '_calculate_current_edge', return_value=Decimal("0.01")):
        trigger = evaluator.check_exit_conditions(position, ..., method)

        assert trigger.reason == "early_exit"  # Not edge_reversal

def test_partial_exit_stages():
    """Test partial exit stages trigger correctly."""
    position = create_test_position(
        unrealized_pnl_pct=0.16,  # +16% profit
        count=100
    )
    method = create_test_method(
        partial_exits={
            'enabled': True,
            'stages': [
                {'name': 'first', 'profit_threshold': 0.15, 'exit_percentage': 50}
            ]
        }
    )

    evaluator = ExitEvaluator(...)
    trigger = evaluator.check_exit_conditions(position, ..., method)

    assert trigger.reason == "partial_exit_first"
    assert trigger.quantity == 50  # 50% of 100

def test_exit_execution_market_order():
    """Test market order execution for CRITICAL exits."""
    position = create_test_position()
    trigger = ExitTrigger(
        reason="stop_loss",
        priority=ExitPriority.CRITICAL,
        quantity="full",
        execution_params={
            "order_type": "market",
            "timeout": 5,
            "retry": "immediate_market"
        },
        metadata={}
    )

    executor = ExitExecutor(...)
    await executor.execute_exit(position, trigger)

    # Verify market order was placed
    assert mock_kalshi.place_order.called
    call_args = mock_kalshi.place_order.call_args
    assert call_args[1]['type'] == 'market'

def test_price_walking_escalation():
    """Test that unfilled limit orders walk price."""
    position = create_test_position()
    trigger = ExitTrigger(
        reason="profit_target",
        priority=ExitPriority.MEDIUM,
        quantity="full",
        execution_params={
            "order_type": "limit",
            "price_strategy": "fair",
            "timeout": 30,
            "retry": "walk_price",
            "max_walks": 3
        },
        metadata={}
    )

    # Mock order not filling
    with patch.object(executor, '_wait_for_fill', return_value=False):
        executor = ExitExecutor(...)
        await executor.execute_exit(position, trigger)

    # Verify walking occurred
    assert mock_kalshi.cancel_order.call_count == 3  # 3 walks
    assert mock_kalshi.place_order.call_count == 4  # Initial + 3 walks
```

---

## Summary

**Exit Evaluation System provides:**
- ✅ Comprehensive exit condition checking
- ✅ Priority-based conflict resolution
- ✅ Non-redundant condition set (removed edge_reversal)
- ✅ Urgency-adaptive execution
- ✅ Progressive escalation for unfilled orders
- ✅ Partial exit support
- ✅ Method-aware configuration

**Key Improvements from Original Design:**
1. **Removed edge_reversal**: Redundant with early_exit and edge_disappeared
2. **Simplified condition set**: 10 exit conditions (was 11)
3. **Clear priority hierarchy**: CRITICAL > HIGH > MEDIUM > LOW
4. **Comprehensive escalation**: Walk → walk → market (for urgent)

**Implementation Order:**
1. ExitEvaluator (condition checking)
2. Priority resolution logic
3. ExitExecutor (order placement)
4. Failed exit handling (escalation)
5. Partial exit handler
6. Testing and validation

**Success Criteria:**
- [ ] All exit conditions trigger correctly
- [ ] Priority resolution works as expected
- [ ] Market orders fill within 10s (CRITICAL)
- [ ] Limit orders fill within timeouts or escalate properly
- [ ] No redundant conditions (edge_reversal removed)
- [ ] Partial exits execute at correct thresholds

---

**Related Documents:**
- `POSITION_MONITORING_SPEC_V1.0.md` - Main monitoring loop
- `EVENT_LOOP_ARCHITECTURE_V1.0.md` - Complete system flow
- `ADR_021_METHOD_ABSTRACTION.md` - Method configuration structure
