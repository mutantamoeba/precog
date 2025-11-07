# Advanced Execution Optimization
## Dynamic Depth Walker Implementation Specification

**Version:** 1.0
**Date:** 2025-10-21
**Last Updated:** 2025-10-28 (Phase 0.6b - Filename standardization)
**Status:** 🔵 Design Complete, Awaiting Implementation
**Dependencies:** Phase 5 (Basic Execution), Phase 7 (Multi-Sport Trading)
**Related:** ADR-020 (Deferred Execution), ADR-021 (Method Abstraction), ADR-037 (Order Walking)
**Filename Updated:** Renamed from PHASE_8_ADVANCED_EXECUTION_SPEC.md to ADVANCED_EXECUTION_SPEC_V1.0.md

---

## Executive Summary

**Goal:** Improve fill rates and reduce slippage in thin markets through sophisticated order execution.

**Algorithm:** Dynamic Depth Walker - hybrid approach combining:
- **Dynamic Spread Walker**: Momentum-driven price adjustments (walking)
- **Liquidity Depth Optimizer**: Multi-level order splitting based on depth analysis

**Expected Improvement:**
- 20-25% better fill rates in thin markets (volume <100)
- 50+ basis points slippage reduction
- Marginal improvement in liquid markets (already efficient)

**Conditional Implementation:**
- Review Phase 5-7 metrics at Week 16
- Implement only if data justifies complexity
- Estimated implementation: 20-30 hours

---

## Table of Contents

1. [When to Implement](#when-to-implement)
2. [Algorithm Overview](#algorithm-overview)
3. [Architecture Design](#architecture-design)
4. [Database Schema](#database-schema)
5. [API Integration](#api-integration)
6. [Python Implementation](#python-implementation)
7. [Configuration](#configuration)
8. [Testing Strategy](#testing-strategy)
9. [Performance Metrics](#performance-metrics)
10. [Risk Mitigation](#risk-mitigation)

---

## When to Implement

### Decision Criteria (Review at Week 16)

**Implement Phase 8 IF Phase 5-7 data shows:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Average slippage | > 1.5% | Basic execution underperforming |
| Slippage in thin markets | > 2.5% | Advanced execution would help significantly |
| Fill failures | > 10% of limit orders | Need better liquidity analysis |
| Thin market frequency | > 30% of trades | Worth optimizing for common case |
| Cumulative slippage cost | > $500 | ROI justifies 20-30 hour investment |

**Don't Implement IF:**
- Average slippage < 1.0% (basic execution sufficient)
- Thin markets < 20% of trades (optimize elsewhere)
- System not yet profitable (fix edge detection first)

### Metrics Collection (Phase 5-7)

**Add to every trade:**
```python
class Trade:
    # Execution quality metrics
    target_price: Decimal        # Price we wanted
    filled_price: Decimal        # Price we got
    slippage_percent: Decimal    # (filled - target) / target
    fill_time_seconds: int       # Time to fill
    market_volume_at_entry: int  # Liquidity when we traded
    market_spread_at_entry: Decimal

    # Categorization
    liquidity_category: str      # "liquid", "moderate", "thin"
```

**Query for decision:**
```sql
-- Average slippage by liquidity category
SELECT
    CASE
        WHEN market_volume_at_entry >= 100 THEN 'liquid'
        WHEN market_volume_at_entry >= 50 THEN 'moderate'
        ELSE 'thin'
    END as category,
    COUNT(*) as trade_count,
    AVG(slippage_percent) as avg_slippage,
    STDDEV(slippage_percent) as slippage_volatility,
    SUM(CASE WHEN filled_price IS NULL THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as fail_rate
FROM trades
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY category;

-- Expected output (example):
-- category  | trade_count | avg_slippage | slippage_volatility | fail_rate
-- liquid    | 245         | 0.008        | 0.003               | 0.02
-- moderate  | 112         | 0.015        | 0.008               | 0.05
-- thin      | 87          | 0.028        | 0.015               | 0.12
--
-- Decision: thin markets have 2.8% slippage and 12% fail rate → IMPLEMENT PHASE 8
```

---

## Algorithm Overview

### Core Concept

**Problem:** Simple limit orders don't adapt to:
- Changing liquidity (orderbook depth fluctuates)
- Price momentum (other traders moving price)
- Partial fills (some quantity filled, rest stuck)

**Solution:** Dynamic Depth Walker

1. **Analyze Depth**: Query orderbook, find "sweet spot" with sufficient liquidity
2. **Split Order**: Distribute quantity across 2-3 price levels
3. **Monitor Fills**: Check every 4 seconds
4. **Calculate Momentum**: Track volume changes (is price moving away?)
5. **Walk Price**: If not filling, adjust price incrementally
6. **Cap Walks**: Stop after 10 adjustments to prevent runaway

### Comparison to Basic Execution

**Basic (Phase 5):**
```python
# Place single limit order at calculated price
order = place_order(
    ticker=market.ticker,
    side="yes",
    type="limit",
    price=target_price,
    count=total_quantity
)

# Wait for fill (or timeout after 30 seconds)
# No adjustments
```

**Advanced (Phase 8):**
```python
# 1. Analyze depth
depth = get_orderbook(market.ticker)
levels = analyze_depth(depth, target_price)

# 2. Split across levels
split_1 = place_order(price=levels[0], count=60% of total)
split_2 = place_order(price=levels[1], count=40% of total)

# 3. Monitor loop (every 4 seconds)
for i in range(10):  # Max 10 walks
    await asyncio.sleep(4)

    # 4. Check momentum
    momentum = calculate_momentum(market.ticker)

    # 5. Walk if needed
    if not_filling and momentum > 0.10:
        cancel_and_replace_at_better_price(split_1)
        cancel_and_replace_at_better_price(split_2)
```

### Key Parameters

```python
WALK_INTERVAL = 4           # seconds between checks
MAX_WALKS = 10              # maximum price adjustments
MIN_VOLUME_THRESHOLD = 50   # fallback to basic if < 50 contracts
SPLIT_RATIO = [0.6, 0.4]    # 60% at level 1, 40% at level 2
MOMENTUM_THRESHOLD = 0.10   # 10% volume increase triggers walk
```

---

## Architecture Design

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Trading Engine                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ execute_trade(edge, method)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Order Executor (Router)                         │
│  - Checks method.execution_config["algorithm"]              │
│  - Routes to SimpleExecutor or DynamicDepthWalker           │
└────────────┬────────────────────────┬────────────────────────┘
             │                        │
             │ simple_limit           │ dynamic_depth_walker
             ▼                        ▼
┌─────────────────────┐   ┌──────────────────────────────────┐
│  SimpleExecutor     │   │  DynamicDepthWalker             │
│  (Phase 5)          │   │  (Phase 8)                      │
│                     │   │                                  │
│  - Single order     │   │  1. OrderbookAnalyzer           │
│  - No depth check   │   │  2. OrderSplitter               │
│  - No walking       │   │  3. MomentumCalculator          │
└─────────────────────┘   │  4. PriceWalker                 │
                          │  5. ExecutionStateManager        │
                          └──────────────┬───────────────────┘
                                         │
                                         │ orderbook data
                                         ▼
                          ┌──────────────────────────────────┐
                          │  Kalshi API                      │
                          │  - GET /orderbook/{ticker}       │
                          │  - POST /orders                  │
                          │  - DELETE /orders/{id}           │
                          └──────────────────────────────────┘
```

### Class Hierarchy

```python
class OrderExecutor(ABC):
    """Base class for all executors."""
    @abstractmethod
    def execute(self, edge, method, market) -> ExecutionResult:
        pass

class SimpleExecutor(OrderExecutor):
    """Phase 5 basic execution."""
    def execute(self, edge, method, market) -> ExecutionResult:
        # Single order, no walking
        pass

class DynamicDepthWalker(OrderExecutor):
    """Phase 8 advanced execution."""

    def __init__(self):
        self.analyzer = OrderbookAnalyzer()
        self.splitter = OrderSplitter()
        self.momentum = MomentumCalculator()
        self.walker = PriceWalker()
        self.state_mgr = ExecutionStateManager()

    def execute(self, edge, method, market) -> ExecutionResult:
        # Multi-level order splitting with walking
        pass

# Factory pattern
def get_executor(method: Method) -> OrderExecutor:
    algorithm = method.execution_config["algorithm"]

    if algorithm == "simple_limit":
        return SimpleExecutor()
    elif algorithm == "dynamic_depth_walker":
        return DynamicDepthWalker()
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
```

---

## Database Schema

### New Tables

```sql
-- ============================================
-- ORDER BOOK SNAPSHOTS
-- ============================================
CREATE TABLE order_book_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),

    -- Snapshot time
    timestamp TIMESTAMP DEFAULT NOW(),

    -- Orderbook depth (up to 10 levels each side)
    yes_depth JSONB NOT NULL,
    /* Format:
    [
        {"price": "0.7100", "quantity": 5000, "order_count": 12},
        {"price": "0.7000", "quantity": 2500, "order_count": 8},
        {"price": "0.6900", "quantity": 1000, "order_count": 3}
    ]
    */

    no_depth JSONB NOT NULL,

    -- Aggregate metrics
    yes_total_volume INT,
    no_total_volume INT,
    spread DECIMAL(10,4),

    -- Best bid/ask
    yes_best_bid DECIMAL(10,4),
    no_best_bid DECIMAL(10,4),

    -- Indexes
    INDEX idx_orderbook_market_time (market_id, timestamp DESC),
    INDEX idx_orderbook_time (timestamp DESC)
);

-- Retention: Keep 7 days, aggregate to hourly averages for history
-- Partition by week for performance

-- ============================================
-- EXECUTION STATE
-- ============================================
CREATE TABLE execution_state (
    execution_id SERIAL PRIMARY KEY,
    edge_id INT NOT NULL REFERENCES edges(edge_id),
    method_id INT NOT NULL REFERENCES methods(method_id),
    market_id VARCHAR NOT NULL REFERENCES markets(market_id),

    -- Algorithm selection
    algorithm VARCHAR(50) NOT NULL,
    -- 'simple_limit' | 'dynamic_depth_walker' | 'twap' | 'adaptive_limit'

    -- Target execution
    target_price DECIMAL(10,4) NOT NULL,
    target_quantity INT NOT NULL,

    -- Current status
    status VARCHAR(20) NOT NULL DEFAULT 'executing',
    -- 'executing' | 'completed' | 'failed' | 'cancelled'
    CHECK (status IN ('executing', 'completed', 'failed', 'cancelled')),

    -- Fill progress
    filled_quantity INT DEFAULT 0,
    filled_value DECIMAL(10,4) DEFAULT 0,  -- Total cost
    average_fill_price DECIMAL(10,4),

    -- Walker state (if applicable)
    walker_state JSONB,
    /* Format:
    {
        "walk_count": 3,
        "max_walks": 10,
        "momentum": 0.15,
        "ema_slippage": 0.012,
        "last_walk_at": "2025-10-21T14:30:15Z"
    }
    */

    -- Split configurations (if applicable)
    split_configs JSONB,
    /* Format:
    [
        {
            "level": 1,
            "target_price": "0.7100",
            "quantity": 60,
            "order_id": "kalshi_order_123",
            "status": "filled",
            "filled_quantity": 60
        },
        {
            "level": 2,
            "target_price": "0.7000",
            "quantity": 40,
            "order_id": "kalshi_order_124",
            "status": "partial",
            "filled_quantity": 25
        }
    ]
    */

    -- Orderbook snapshot reference (for analysis)
    initial_snapshot_id INT REFERENCES order_book_snapshots(snapshot_id),

    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- Error handling
    error_message TEXT,

    -- Indexes
    INDEX idx_execution_status (status),
    INDEX idx_execution_method (method_id),
    INDEX idx_execution_market (market_id),
    INDEX idx_execution_created (created_at DESC)
);

-- ============================================
-- SPLIT ORDERS (Detailed tracking)
-- ============================================
CREATE TABLE split_orders (
    split_id SERIAL PRIMARY KEY,
    execution_id INT NOT NULL REFERENCES execution_state(execution_id),

    -- Order identification
    order_id VARCHAR,  -- Kalshi order ID (after placement)
    level INT NOT NULL,  -- Which depth level (1, 2, 3)

    -- Order details
    target_price DECIMAL(10,4) NOT NULL,
    quantity INT NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'yes' | 'no'

    -- Fill status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 'pending' | 'placed' | 'partial' | 'filled' | 'cancelled' | 'failed'
    CHECK (status IN ('pending', 'placed', 'partial', 'filled', 'cancelled', 'failed')),

    filled_quantity INT DEFAULT 0,
    average_fill_price DECIMAL(10,4),

    -- Walk history
    walk_count INT DEFAULT 0,
    price_walk_history JSONB,
    /* Format:
    [
        {"timestamp": "2025-10-21T14:30:15Z", "old_price": "0.7100", "new_price": "0.7150", "reason": "high_momentum"},
        {"timestamp": "2025-10-21T14:30:19Z", "old_price": "0.7150", "new_price": "0.7200", "reason": "high_momentum"}
    ]
    */

    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    placed_at TIMESTAMP,
    filled_at TIMESTAMP,
    cancelled_at TIMESTAMP,

    -- Error handling
    error_message TEXT,

    -- Indexes
    INDEX idx_split_execution (execution_id),
    INDEX idx_split_order (order_id),
    INDEX idx_split_status (status)
);

-- ============================================
-- EXECUTION METRICS (Post-execution analysis)
-- ============================================
CREATE TABLE execution_metrics (
    metric_id SERIAL PRIMARY KEY,
    execution_id INT NOT NULL REFERENCES execution_state(execution_id),

    -- Target vs Actual
    target_price DECIMAL(10,4) NOT NULL,
    target_quantity INT NOT NULL,
    filled_quantity INT NOT NULL,
    average_fill_price DECIMAL(10,4) NOT NULL,

    -- Quality metrics
    fill_rate DECIMAL(6,4),  -- filled / target
    slippage_percent DECIMAL(10,4),  -- (avg_fill - target) / target
    slippage_basis_points INT,  -- slippage * 10000

    -- Timing metrics
    time_to_first_fill INT,  -- seconds
    time_to_full_fill INT,   -- seconds (NULL if partial)
    total_execution_time INT,  -- seconds

    -- Algorithm-specific metrics
    algorithm VARCHAR(50),
    walks_executed INT,
    splits_used INT,
    momentum_at_execution DECIMAL(10,4),

    -- Market conditions
    market_volume_at_entry INT,
    market_spread_at_entry DECIMAL(10,4),
    liquidity_category VARCHAR(20),  -- 'liquid' | 'moderate' | 'thin'

    -- Comparison to basic execution (estimated)
    estimated_basic_slippage DECIMAL(10,4),
    improvement_over_basic DECIMAL(10,4),

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),

    -- Indexes
    INDEX idx_metrics_execution (execution_id),
    INDEX idx_metrics_algorithm (algorithm),
    INDEX idx_metrics_liquidity (liquidity_category),
    INDEX idx_metrics_date (created_at DESC)
);
```

### Schema Updates to Existing Tables

```sql
-- Add execution_id to trades for linking
ALTER TABLE trades ADD COLUMN execution_id INT REFERENCES execution_state(execution_id);
CREATE INDEX idx_trades_execution ON trades(execution_id);

-- Update trades to track execution quality
ALTER TABLE trades ADD COLUMN target_price DECIMAL(10,4);
ALTER TABLE trades ADD COLUMN slippage_percent DECIMAL(10,4);
ALTER TABLE trades ADD COLUMN fill_time_seconds INT;
ALTER TABLE trades ADD COLUMN market_volume_at_entry INT;
ALTER TABLE trades ADD COLUMN liquidity_category VARCHAR(20);
```

---

## API Integration

### Required Endpoints

**Orderbook Depth (New in Phase 8):**
```python
def get_orderbook(ticker: str, depth: int = 10) -> Dict:
    """
    Get orderbook depth for market.

    Args:
        ticker: Market ticker
        depth: Number of levels per side (max 100)

    Returns:
        {
            "orderbook": {
                "yes": [
                    [71, 5000],  # cents, quantity (deprecated format)
                    [70, 2500]
                ],
                "yes_dollars": [
                    ["0.7100", 5000],  # Use this format
                    ["0.7000", 2500]
                ],
                "no_dollars": [
                    ["0.2900", 10000],
                    ["0.3000", 5000]
                ]
            }
        }
    """
    response = self.kalshi_client.get(
        f"/markets/{ticker}/orderbook",
        params={"depth": depth}
    )
    return response.json()
```

**Order Management:**
```python
# Place order (existing)
POST /portfolio/orders
{
    "ticker": "MARKET-YES",
    "action": "buy",
    "side": "yes",
    "type": "limit",
    "yes_price_dollars": "0.7100",
    "count": 60
}

# Cancel order (existing)
DELETE /portfolio/orders/{order_id}

# Batch cancel (if available)
DELETE /portfolio/orders
{
    "order_ids": ["order_1", "order_2", "order_3"]
}

# Get order status (existing)
GET /portfolio/orders/{order_id}
```

**WebSocket (Optional - for real-time updates):**
```python
# Subscribe to orderbook updates
ws://kalshi/orderbook/MARKET-YES

# Message format:
{
    "type": "orderbook_update",
    "ticker": "MARKET-YES",
    "yes_dollars": [["0.7100", 5000], ["0.7000", 2500]],
    "no_dollars": [["0.2900", 10000], ["0.3000", 5000]],
    "timestamp": "2025-10-21T14:30:15Z"
}
```

### Rate Limiting

**Phase 8 API Usage:**
```python
# Per execution:
# - 1 orderbook fetch (initial)
# - 2-3 order placements (splits)
# - ~10 orderbook fetches (monitoring, every 4 seconds for 40 seconds)
# - ~10 cancel + replace operations (if walking)
#
# Total: ~25 API calls per execution

# With 10 concurrent executions:
# = 250 API calls over ~40 seconds
# = ~6 calls/second average
# = ~360 calls/minute

# Kalshi limit: 100 calls/minute
# Risk: HIGH - need throttling
```

**Mitigation:**
```python
class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, max_calls=90, window=60):  # 90/min (buffer below 100)
        self.max_calls = max_calls
        self.window = window
        self.tokens = max_calls
        self.last_update = time.time()

    async def acquire(self, calls=1):
        """Wait if needed to stay under rate limit."""
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens
        self.tokens = min(
            self.max_calls,
            self.tokens + (elapsed / self.window) * self.max_calls
        )
        self.last_update = now

        # Wait if not enough tokens
        if self.tokens < calls:
            wait_time = ((calls - self.tokens) / self.max_calls) * self.window
            await asyncio.sleep(wait_time)
            self.tokens = 0
        else:
            self.tokens -= calls

# Global rate limiter
rate_limiter = RateLimiter(max_calls=90, window=60)

# Use before API calls
await rate_limiter.acquire(calls=1)
response = kalshi_client.get_orderbook(ticker)
```

---

## Python Implementation

### 1. Orderbook Analyzer

```python
# execution/orderbook_analyzer.py

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict

@dataclass
class DepthLevel:
    """Single level in orderbook."""
    price: Decimal
    quantity: int
    cumulative_quantity: int
    order_count: int

@dataclass
class DepthAnalysis:
    """Analysis of orderbook depth."""
    levels: List[DepthLevel]
    total_liquidity: int
    spread: Decimal
    liquidity_category: str  # 'liquid', 'moderate', 'thin'
    sweet_spot_price: Decimal
    sweet_spot_quantity: int

class OrderbookAnalyzer:
    """Analyze orderbook depth for optimal execution."""

    def __init__(self):
        self.liquid_threshold = 100
        self.moderate_threshold = 50

    def analyze(
        self,
        orderbook: Dict,
        target_price: Decimal,
        side: str
    ) -> DepthAnalysis:
        """
        Analyze orderbook depth around target price.

        Args:
            orderbook: Kalshi orderbook response
            target_price: Our desired price
            side: 'yes' or 'no'

        Returns:
            DepthAnalysis with liquidity profile
        """
        # Extract relevant side
        if side == "yes":
            depth_data = orderbook["orderbook"]["yes_dollars"]
        else:
            depth_data = orderbook["orderbook"]["no_dollars"]

        # Parse levels
        levels = []
        cumulative = 0

        for price_str, quantity in depth_data:
            price = Decimal(price_str)

            # Only consider levels at or better than target
            if (side == "yes" and price <= target_price) or \
               (side == "no" and price >= target_price):

                cumulative += quantity
                levels.append(DepthLevel(
                    price=price,
                    quantity=quantity,
                    cumulative_quantity=cumulative,
                    order_count=0  # Not provided by Kalshi
                ))

        # Calculate metrics
        total_liquidity = cumulative
        spread = self._calculate_spread(orderbook)
        category = self._categorize_liquidity(total_liquidity)

        # Find sweet spot (level with enough cumulative liquidity)
        sweet_spot = self._find_sweet_spot(levels, target_price)

        return DepthAnalysis(
            levels=levels,
            total_liquidity=total_liquidity,
            spread=spread,
            liquidity_category=category,
            sweet_spot_price=sweet_spot.price if sweet_spot else target_price,
            sweet_spot_quantity=sweet_spot.cumulative_quantity if sweet_spot else 0
        )

    def _calculate_spread(self, orderbook: Dict) -> Decimal:
        """Calculate bid-ask spread."""
        yes_best = Decimal(orderbook["orderbook"]["yes_dollars"][0][0])
        no_best = Decimal(orderbook["orderbook"]["no_dollars"][0][0])

        # Yes ask = 1.0 - No bid
        yes_ask = Decimal("1.0000") - no_best

        return yes_ask - yes_best

    def _categorize_liquidity(self, total_volume: int) -> str:
        """Categorize market liquidity."""
        if total_volume >= self.liquid_threshold:
            return "liquid"
        elif total_volume >= self.moderate_threshold:
            return "moderate"
        else:
            return "thin"

    def _find_sweet_spot(
        self,
        levels: List[DepthLevel],
        target_price: Decimal
    ) -> Optional[DepthLevel]:
        """
        Find "sweet spot" - price level with sufficient cumulative liquidity.

        Strategy: Find first level where cumulative >= 50% of what we need
        """
        if not levels:
            return None

        # Prefer levels close to target price with good liquidity
        for level in levels:
            if level.price <= target_price and level.cumulative_quantity >= 50:
                return level

        # Fallback to best available
        return levels[0] if levels else None
```

### 2. Order Splitter

```python
# execution/order_splitter.py

from typing import List, Tuple
from decimal import Decimal

@dataclass
class OrderSplit:
    """Configuration for a split order."""
    level: int
    price: Decimal
    quantity: int

class OrderSplitter:
    """Split orders across depth levels."""

    def __init__(self, split_ratios: List[float] = [0.6, 0.4]):
        """
        Initialize splitter.

        Args:
            split_ratios: How to distribute quantity across levels
                          Default: 60% at level 1, 40% at level 2
        """
        self.split_ratios = split_ratios

    def calculate_splits(
        self,
        depth_analysis: DepthAnalysis,
        total_quantity: int,
        target_price: Decimal
    ) -> List[OrderSplit]:
        """
        Calculate optimal order splits.

        Strategy:
        - If insufficient depth: Single order at target price
        - If good depth: Split across 2-3 levels proportional to liquidity

        Args:
            depth_analysis: Orderbook analysis
            total_quantity: Total contracts to buy
            target_price: Desired price

        Returns:
            List of OrderSplit configs
        """
        # Insufficient depth: Use single order
        if depth_analysis.liquidity_category == "thin":
            return [OrderSplit(
                level=1,
                price=target_price,
                quantity=total_quantity
            )]

        # Good depth: Split across levels
        splits = []
        levels_to_use = min(len(depth_analysis.levels), len(self.split_ratios))

        for i in range(levels_to_use):
            level = depth_analysis.levels[i]
            ratio = self.split_ratios[i]
            quantity = int(total_quantity * ratio)

            if quantity > 0:
                splits.append(OrderSplit(
                    level=i + 1,
                    price=level.price,
                    quantity=quantity
                ))

        # Adjust last split to account for rounding
        if splits:
            assigned = sum(s.quantity for s in splits)
            remainder = total_quantity - assigned
            splits[-1].quantity += remainder

        return splits
```

### 3. Momentum Calculator

```python
# execution/momentum_calculator.py

from typing import List
from decimal import Decimal
from datetime import datetime, timedelta

class MomentumCalculator:
    """Calculate volume momentum for price walking decisions."""

    def __init__(self, lookback_minutes: int = 2):
        """
        Initialize calculator.

        Args:
            lookback_minutes: How far back to look for momentum
        """
        self.lookback_minutes = lookback_minutes

    def calculate(self, market_id: str) -> Decimal:
        """
        Calculate momentum score.

        Momentum = (current_volume - average_volume) / average_volume

        Positive momentum: Volume increasing (price pressure up)
        Negative momentum: Volume decreasing (price pressure down)

        Args:
            market_id: Market to analyze

        Returns:
            Momentum score (e.g., 0.15 = 15% above average)
        """
        # Get recent orderbook snapshots
        cutoff = datetime.now() - timedelta(minutes=self.lookback_minutes)

        snapshots = db.query(OrderBookSnapshot)\
            .filter(OrderBookSnapshot.market_id == market_id)\
            .filter(OrderBookSnapshot.timestamp >= cutoff)\
            .order_by(OrderBookSnapshot.timestamp.asc())\
            .all()

        if len(snapshots) < 2:
            return Decimal("0")  # Not enough data

        # Extract volumes
        volumes = [s.yes_total_volume + s.no_total_volume for s in snapshots]

        current = volumes[-1]
        average = sum(volumes[:-1]) / len(volumes[:-1])

        if average == 0:
            return Decimal("0")

        momentum = (current - average) / average
        return Decimal(str(momentum))

    def calculate_ema_slippage(
        self,
        market_id: str,
        alpha: Decimal = Decimal("0.3")
    ) -> Decimal:
        """
        Calculate exponential moving average of recent slippage.

        Used to predict future slippage.

        Args:
            market_id: Market to analyze
            alpha: EMA smoothing factor (0.3 = 30% weight on recent)

        Returns:
            EMA of slippage
        """
        # Get recent executions
        cutoff = datetime.now() - timedelta(minutes=10)

        recent_metrics = db.query(ExecutionMetrics)\
            .join(ExecutionState)\
            .filter(ExecutionState.market_id == market_id)\
            .filter(ExecutionMetrics.created_at >= cutoff)\
            .order_by(ExecutionMetrics.created_at.asc())\
            .all()

        if not recent_metrics:
            return Decimal("0.01")  # Default 1% estimate

        # Calculate EMA
        ema = recent_metrics[0].slippage_percent

        for metric in recent_metrics[1:]:
            ema = alpha * metric.slippage_percent + (1 - alpha) * ema

        return ema
```

### 4. Price Walker

```python
# execution/price_walker.py

from decimal import Decimal
from typing import Optional

class PriceWalker:
    """Walk price incrementally based on momentum."""

    def __init__(
        self,
        base_increment: Decimal = Decimal("0.005"),  # 0.5 cents
        aggressive_increment: Decimal = Decimal("0.01")  # 1 cent
    ):
        """
        Initialize walker.

        Args:
            base_increment: Normal price adjustment
            aggressive_increment: High momentum price adjustment
        """
        self.base_increment = base_increment
        self.aggressive_increment = aggressive_increment

    def calculate_walk_price(
        self,
        current_price: Decimal,
        momentum: Decimal,
        direction: str = "up"
    ) -> Decimal:
        """
        Calculate new price after walking.

        Args:
            current_price: Current order price
            momentum: Momentum score
            direction: 'up' or 'down'

        Returns:
            New price to use
        """
        # Choose increment based on momentum
        if abs(momentum) > 0.20:
            increment = self.aggressive_increment
        else:
            increment = self.base_increment

        # Walk price
        if direction == "up":
            new_price = current_price + increment
        else:
            new_price = current_price - increment

        # Clamp to valid range
        return max(Decimal("0.0001"), min(Decimal("0.9999"), new_price))

    def should_walk(
        self,
        split_order: 'SplitOrder',
        momentum: Decimal,
        momentum_threshold: Decimal = Decimal("0.10")
    ) -> bool:
        """
        Decide if order should walk.

        Args:
            split_order: Order to check
            momentum: Current momentum
            momentum_threshold: Minimum momentum to trigger walk

        Returns:
            True if should walk
        """
        # Don't walk if already filled
        if split_order.status == "filled":
            return False

        # Don't walk if at max walks
        if split_order.walk_count >= 10:
            return False

        # Walk if high momentum
        if abs(momentum) >= momentum_threshold:
            return True

        # Don't walk if some quantity filled (wait for more fills)
        if split_order.filled_quantity > 0:
            return False

        return False
```

### 5. Dynamic Depth Walker (Main Algorithm)

```python
# execution/dynamic_depth_walker.py

import asyncio
from typing import Dict, List
from decimal import Decimal
from datetime import datetime

class DynamicDepthWalker(OrderExecutor):
    """
    Hybrid execution algorithm.

    Combines:
    - Liquidity Depth Optimizer: Multi-level splitting
    - Dynamic Spread Walker: Momentum-based price adjustments
    """

    def __init__(self):
        self.analyzer = OrderbookAnalyzer()
        self.splitter = OrderSplitter()
        self.momentum = MomentumCalculator()
        self.walker = PriceWalker()

        # Config
        self.walk_interval = 4  # seconds
        self.max_walks = 10
        self.min_volume_threshold = 50
        self.momentum_threshold = Decimal("0.10")

    async def execute(
        self,
        edge: Edge,
        method: Method,
        market: Market
    ) -> ExecutionResult:
        """
        Execute trade using depth-aware splitting and walking.

        Args:
            edge: Trade signal
            method: Method config
            market: Market info

        Returns:
            ExecutionResult with fill details
        """
        # 1. Get orderbook
        orderbook = await self.get_orderbook(market.ticker)

        # 2. Analyze depth
        depth_analysis = self.analyzer.analyze(
            orderbook=orderbook,
            target_price=edge.target_price,
            side=edge.side
        )

        # 3. Check if sufficient liquidity
        if depth_analysis.total_liquidity < self.min_volume_threshold:
            # Fallback to simple execution
            logger.info(f"Insufficient liquidity, using simple execution")
            return await self.simple_fallback(edge, method, market)

        # 4. Calculate splits
        splits = self.splitter.calculate_splits(
            depth_analysis=depth_analysis,
            total_quantity=edge.position_size,
            target_price=edge.target_price
        )

        # 5. Create execution state
        execution_state = ExecutionState(
            edge_id=edge.edge_id,
            method_id=method.method_id,
            market_id=market.market_id,
            algorithm="dynamic_depth_walker",
            target_price=edge.target_price,
            target_quantity=edge.position_size,
            status="executing",
            walker_state={
                "walk_count": 0,
                "max_walks": self.max_walks,
                "momentum": 0,
                "ema_slippage": 0
            },
            split_configs=[]
        )
        db.add(execution_state)
        db.commit()

        # 6. Place split orders
        split_orders = []
        for split in splits:
            order = await self.place_split_order(
                execution_state=execution_state,
                split=split,
                market=market,
                side=edge.side
            )
            split_orders.append(order)

        # 7. Monitor and walk
        await self.monitor_and_walk(execution_state, split_orders, market)

        # 8. Compile results
        result = self.compile_results(execution_state, split_orders)

        return result

    async def place_split_order(
        self,
        execution_state: ExecutionState,
        split: OrderSplit,
        market: Market,
        side: str
    ) -> SplitOrder:
        """Place individual split order."""

        # Create split_order record
        split_order = SplitOrder(
            execution_id=execution_state.execution_id,
            level=split.level,
            target_price=split.price,
            quantity=split.quantity,
            side=side,
            status="pending"
        )
        db.add(split_order)
        db.commit()

        # Place order via Kalshi API
        try:
            api_order = await self.kalshi_client.place_order(
                ticker=market.ticker,
                side=side,
                action="buy",
                type="limit",
                yes_price_dollars=str(split.price) if side == "yes" else None,
                no_price_dollars=str(split.price) if side == "no" else None,
                count=split.quantity
            )

            # Update with order ID
            split_order.order_id = api_order["order_id"]
            split_order.status = "placed"
            split_order.placed_at = datetime.now()
            db.commit()

        except Exception as e:
            split_order.status = "failed"
            split_order.error_message = str(e)
            db.commit()
            logger.error(f"Failed to place split order: {e}")

        return split_order

    async def monitor_and_walk(
        self,
        execution_state: ExecutionState,
        split_orders: List[SplitOrder],
        market: Market
    ):
        """
        Monitor fills and walk prices if needed.

        Runs until:
        - All orders filled
        - Max walks reached
        - Timeout (40 seconds default)
        """
        start_time = datetime.now()
        timeout = 40  # seconds

        while True:
            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                logger.info(f"Execution timeout reached")
                break

            # Check if all filled
            all_filled = all(
                s.status == "filled" for s in split_orders
            )
            if all_filled:
                logger.info(f"All splits filled")
                break

            # Check if max walks reached
            total_walks = sum(s.walk_count for s in split_orders)
            if total_walks >= self.max_walks * len(split_orders):
                logger.info(f"Max walks reached")
                break

            # Wait for interval
            await asyncio.sleep(self.walk_interval)

            # Refresh split orders from DB
            for split_order in split_orders:
                db.refresh(split_order)

                # Check order status via API
                await self.update_split_status(split_order)

            # Calculate momentum
            momentum = self.momentum.calculate(market.market_id)

            # Update execution state
            execution_state.walker_state["momentum"] = float(momentum)
            db.commit()

            # Walk prices if needed
            for split_order in split_orders:
                if self.walker.should_walk(split_order, momentum, self.momentum_threshold):
                    await self.walk_split_price(
                        split_order=split_order,
                        momentum=momentum,
                        market=market
                    )

        # Mark execution complete
        execution_state.status = "completed"
        execution_state.completed_at = datetime.now()

        # Calculate final metrics
        filled_qty = sum(s.filled_quantity for s in split_orders)
        total_qty = execution_state.target_quantity

        execution_state.filled_quantity = filled_qty
        execution_state.fill_rate = filled_qty / total_qty if total_qty > 0 else 0

        db.commit()

    async def update_split_status(self, split_order: SplitOrder):
        """Check order status via Kalshi API."""
        if split_order.status in ["filled", "cancelled", "failed"]:
            return  # Already terminal state

        try:
            order_status = await self.kalshi_client.get_order(split_order.order_id)

            # Update fill info
            if order_status["status"] == "filled":
                split_order.status = "filled"
                split_order.filled_quantity = order_status["filled_count"]
                split_order.average_fill_price = Decimal(
                    order_status["average_fill_price_dollars"]
                )
                split_order.filled_at = datetime.now()

            elif order_status["status"] == "partial":
                split_order.status = "partial"
                split_order.filled_quantity = order_status["filled_count"]
                split_order.average_fill_price = Decimal(
                    order_status["average_fill_price_dollars"]
                )

            db.commit()

        except Exception as e:
            logger.error(f"Error checking order status: {e}")

    async def walk_split_price(
        self,
        split_order: SplitOrder,
        momentum: Decimal,
        market: Market
    ):
        """
        Walk (adjust) price for a split order.

        Process:
        1. Calculate new price
        2. Cancel existing order
        3. Place new order at better price
        4. Update split_order record
        """
        # Calculate new price
        new_price = self.walker.calculate_walk_price(
            current_price=split_order.target_price,
            momentum=momentum,
            direction="up"  # Always walk up (better price for us)
        )

        logger.info(
            f"Walking split {split_order.split_id}: "
            f"{split_order.target_price} → {new_price} "
            f"(momentum: {momentum})"
        )

        # Cancel existing order
        try:
            await self.kalshi_client.cancel_order(split_order.order_id)

            # Place new order
            api_order = await self.kalshi_client.place_order(
                ticker=market.ticker,
                side=split_order.side,
                action="buy",
                type="limit",
                yes_price_dollars=str(new_price) if split_order.side == "yes" else None,
                no_price_dollars=str(new_price) if split_order.side == "no" else None,
                count=split_order.quantity - split_order.filled_quantity  # Remaining quantity
            )

            # Update record
            old_price = split_order.target_price
            split_order.target_price = new_price
            split_order.order_id = api_order["order_id"]
            split_order.walk_count += 1

            # Add to walk history
            if not split_order.price_walk_history:
                split_order.price_walk_history = []

            split_order.price_walk_history.append({
                "timestamp": datetime.now().isoformat(),
                "old_price": str(old_price),
                "new_price": str(new_price),
                "momentum": float(momentum)
            })

            db.commit()

        except Exception as e:
            logger.error(f"Error walking price: {e}")
            split_order.error_message = str(e)
            db.commit()

    def compile_results(
        self,
        execution_state: ExecutionState,
        split_orders: List[SplitOrder]
    ) -> ExecutionResult:
        """Compile execution results."""

        filled_quantity = sum(s.filled_quantity for s in split_orders)
        total_cost = sum(
            s.filled_quantity * s.average_fill_price
            for s in split_orders
            if s.average_fill_price
        )

        average_fill_price = (
            total_cost / filled_quantity if filled_quantity > 0 else None
        )

        # Calculate slippage
        slippage = None
        if average_fill_price:
            slippage = (average_fill_price - execution_state.target_price) / \
                       execution_state.target_price

        # Create metrics record
        metrics = ExecutionMetrics(
            execution_id=execution_state.execution_id,
            target_price=execution_state.target_price,
            target_quantity=execution_state.target_quantity,
            filled_quantity=filled_quantity,
            average_fill_price=average_fill_price or Decimal("0"),
            fill_rate=filled_quantity / execution_state.target_quantity,
            slippage_percent=slippage or Decimal("0"),
            algorithm="dynamic_depth_walker",
            walks_executed=sum(s.walk_count for s in split_orders),
            splits_used=len(split_orders)
        )
        db.add(metrics)
        db.commit()

        return ExecutionResult(
            execution_id=execution_state.execution_id,
            filled_quantity=filled_quantity,
            average_fill_price=average_fill_price,
            slippage_percent=slippage,
            total_walks=sum(s.walk_count for s in split_orders)
        )
```

---

## Configuration

### Method Configuration

```python
# In methods table
method = Method(
    method_name="aggressive_nfl_advanced",
    method_version="v1.0",
    strategy_id=3,  # live_continuous
    model_id=4,     # ensemble_nfl
    execution_config={
        "algorithm": "dynamic_depth_walker",
        "max_slippage_percent": 0.025,
        "order_timeout_seconds": 40,

        # Dynamic Depth Walker specific params
        "dynamic_depth_walker": {
            "enabled": True,
            "walk_interval_seconds": 4,
            "max_walks": 10,
            "min_volume_threshold": 50,
            "split_ratios": [0.6, 0.4],
            "momentum_threshold": 0.10,
            "base_increment": "0.005",
            "aggressive_increment": "0.010"
        }
    }
)
```

### Trading Engine Integration

```python
# trading/engine.py

def execute_trade(edge: Edge, method: Method):
    """Execute trade using method's execution algorithm."""

    # Get executor based on method config
    executor = get_executor(method)

    # Execute
    result = executor.execute(edge, method, edge.market)

    # Record trade
    trade = Trade(
        edge_id=edge.edge_id,
        method_id=method.method_id,
        execution_id=result.execution_id,
        strategy_id=method.strategy_id,
        model_id=method.model_id,
        market_id=edge.market_id,
        side=edge.side,
        quantity=result.filled_quantity,
        price=result.average_fill_price,
        slippage_percent=result.slippage_percent
    )
    db.add(trade)
    db.commit()

    return trade
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_dynamic_depth_walker.py

def test_orderbook_analyzer():
    """Test orderbook analysis."""
    orderbook = {
        "orderbook": {
            "yes_dollars": [
                ["0.7100", 5000],
                ["0.7000", 2500],
                ["0.6900", 1000]
            ]
        }
    }

    analyzer = OrderbookAnalyzer()
    analysis = analyzer.analyze(
        orderbook=orderbook,
        target_price=Decimal("0.7050"),
        side="yes"
    )

    assert analysis.total_liquidity == 7500
    assert analysis.liquidity_category == "liquid"

def test_order_splitter():
    """Test order splitting logic."""
    analysis = DepthAnalysis(
        levels=[
            DepthLevel(Decimal("0.71"), 5000, 5000, 0),
            DepthLevel(Decimal("0.70"), 2500, 7500, 0)
        ],
        total_liquidity=7500,
        spread=Decimal("0.03"),
        liquidity_category="liquid",
        sweet_spot_price=Decimal("0.71"),
        sweet_spot_quantity=5000
    )

    splitter = OrderSplitter()
    splits = splitter.calculate_splits(
        depth_analysis=analysis,
        total_quantity=100,
        target_price=Decimal("0.7050")
    )

    assert len(splits) == 2
    assert splits[0].quantity == 60
    assert splits[1].quantity == 40

def test_momentum_calculator():
    """Test momentum calculation."""
    # Create mock snapshots
    for i in range(5):
        snapshot = OrderBookSnapshot(
            market_id="TEST-YES",
            yes_total_volume=1000 + i * 100,  # Increasing volume
            timestamp=datetime.now() - timedelta(seconds=i*30)
        )
        db.add(snapshot)
    db.commit()

    calc = MomentumCalculator()
    momentum = calc.calculate("TEST-YES")

    assert momentum > 0  # Should be positive (volume increasing)

def test_price_walker():
    """Test price walking logic."""
    walker = PriceWalker()

    new_price = walker.calculate_walk_price(
        current_price=Decimal("0.7000"),
        momentum=Decimal("0.15"),  # High momentum
        direction="up"
    )

    assert new_price > Decimal("0.7000")
    assert new_price == Decimal("0.7050")  # Should use base increment
```

### Integration Tests

```python
# tests/integration/test_execution_flow.py

@pytest.mark.asyncio
async def test_dynamic_depth_walker_execution():
    """Test complete execution flow."""

    # Setup
    method = create_test_method(algorithm="dynamic_depth_walker")
    edge = create_test_edge(target_price=Decimal("0.70"))
    market = create_test_market()

    # Mock Kalshi API
    with patch('kalshi_client.get_orderbook') as mock_orderbook, \
         patch('kalshi_client.place_order') as mock_place, \
         patch('kalshi_client.get_order') as mock_status:

        mock_orderbook.return_value = get_mock_orderbook()
        mock_place.return_value = {"order_id": "test_order_123"}
        mock_status.return_value = {"status": "filled", "filled_count": 60}

        # Execute
        executor = DynamicDepthWalker()
        result = await executor.execute(edge, method, market)

        # Verify
        assert result.filled_quantity > 0
        assert result.average_fill_price is not None
        assert mock_place.call_count >= 2  # At least 2 splits
```

### Performance Tests

```python
# tests/performance/test_execution_speed.py

def test_execution_speed():
    """Ensure execution completes within reasonable time."""

    start = time.time()

    # Execute with Dynamic Depth Walker
    result = execute_trade(edge, method)

    elapsed = time.time() - start

    assert elapsed < 45  # Should complete within 45 seconds
    assert result.filled_quantity > 0

def test_api_rate_limiting():
    """Verify rate limiting works."""

    # Execute 10 concurrent trades
    results = asyncio.run(execute_concurrent_trades(count=10))

    # Check that we didn't hit rate limits
    for result in results:
        assert not result.error_message
        assert "rate_limit" not in str(result.error_message).lower()
```

---

## Performance Metrics

### Success Metrics (Phase 8 Goals)

| Metric | Phase 5 (Basic) | Phase 8 (Target) | Improvement |
|--------|-----------------|-------------------|-------------|
| **Slippage (liquid markets)** | 0.8% | 0.5% | 37% reduction |
| **Slippage (thin markets)** | 2.5% | 1.2% | 52% reduction |
| **Fill rate (liquid)** | 95% | 97% | +2pp |
| **Fill rate (thin)** | 85% | 96% | +11pp |
| **Time to fill** | 15s | 25s | +10s (acceptable) |
| **API calls per trade** | 3-5 | 20-25 | +5x (monitor limits) |

### Monitoring Queries

```sql
-- Compare basic vs advanced execution
SELECT
    em.algorithm,
    em.liquidity_category,
    COUNT(*) as executions,
    AVG(em.slippage_percent) * 100 as avg_slippage_pct,
    AVG(em.fill_rate) * 100 as avg_fill_rate,
    AVG(em.time_to_full_fill) as avg_time_seconds,
    AVG(em.walks_executed) as avg_walks
FROM execution_metrics em
WHERE em.created_at >= NOW() - INTERVAL '7 days'
GROUP BY em.algorithm, em.liquidity_category
ORDER BY em.liquidity_category, em.algorithm;

-- Expected output:
-- algorithm              | liquidity_category | executions | avg_slippage_pct | avg_fill_rate | avg_time_seconds | avg_walks
-- simple_limit           | liquid             | 150        | 0.8              | 95            | 15               | 0
-- dynamic_depth_walker   | liquid             | 120        | 0.5              | 97            | 22               | 2.1
-- simple_limit           | thin               | 50         | 2.5              | 85            | 18               | 0
-- dynamic_depth_walker   | thin               | 45         | 1.2              | 96            | 28               | 4.8
```

---

## Risk Mitigation

### Risk 1: API Rate Limits

**Risk:** Phase 8 uses 5-6x more API calls than Phase 5

**Mitigation:**
```python
# 1. Global rate limiter (already implemented)
rate_limiter = RateLimiter(max_calls=90, window=60)

# 2. Concurrent execution limits
max_concurrent_executions = 5  # Limit simultaneous dynamic walkers

# 3. Fallback to simple execution if rate limit hit
if await rate_limiter.would_exceed_limit(calls=15):
    logger.warning("Rate limit risk, using simple execution")
    return await simple_executor.execute(edge, method, market)
```

### Risk 2: Complexity Bugs

**Risk:** State machine errors, race conditions, order cancellation failures

**Mitigation:**
- Extensive unit tests (>90% coverage target)
- Integration tests with mocked Kalshi API
- Paper trading validation (1 week minimum)
- Gradual rollout (10% of trades → 50% → 100%)
- Fallback to simple execution on errors

### Risk 3: Market Impact

**Risk:** Our walking could move prices against us

**Mitigation:**
- Cap max walks at 10
- Only walk in direction of momentum (not counter)
- Monitor slippage - disable if worse than simple execution

### Risk 4: Over-Optimization

**Risk:** Algorithm optimized for historical data, performs poorly live

**Mitigation:**
- Compare to simple execution continuously
- Disable if 3+ consecutive days of worse performance
- Keep simple execution as default, opt-in to advanced

---

## Documentation References

- **ADR-020**: Deferred Advanced Execution Optimization (rationale)
- **ADR-021**: Method Abstraction Layer (configuration integration)
- **DATABASE_SCHEMA_SUMMARY_V1.5**: Complete schema with execution tables
- **API_INTEGRATION_GUIDE_V2.0**: Kalshi orderbook endpoint details
- **MASTER_REQUIREMENTS_V2.5**: Requirements for Phase 8

---

## Approval & Timeline

**Designed By:** Project Lead
**Date:** 2025-10-21
**Review Date:** Week 16 (after Phase 7 complete)
**Conditional Implementation:** Week 17-18 (if metrics justify)

---

## Summary

**Dynamic Depth Walker** is a sophisticated execution algorithm that can improve fill rates by 20-25% in thin markets. However, it adds significant complexity and API usage. **Defer implementation to Phase 8** and make data-driven decision based on Phase 5-7 metrics.

**Decision Criteria:** Implement only if average slippage > 1.5% and thin markets represent >30% of opportunities.

**Fallback:** Simple limit order execution is sufficient for most cases. Don't prematurely optimize.
