# ADR-020: Deferred Advanced Execution Optimization

**Status:** ✅ Accepted  
**Date:** 2025-10-21  
**Phase:** 0.5 (Design), 8 (Implementation)  
**Supersedes:** None  
**Related:** ADR-001 (Price Precision), ADR-002 (Versioning)

---

## Context

Grok proposed a sophisticated "Dynamic Depth Walker" execution algorithm that could improve fill rates by 20-25% in thin markets through:

1. **Order Book Depth Analysis**: Multi-level price/quantity data
2. **Order Splitting**: Distribute orders across 2-3 depth levels
3. **Momentum-Based Walking**: Adjust prices dynamically based on volume trends
4. **EMA Forecasting**: Predict slippage and liquidity dry-up

**Kalshi API Capability Confirmed:**
- Endpoint: `GET /markets/{ticker}/orderbook`
- Returns: Up to 100 price levels per side
- Format: `[["0.7100", 5000], ["0.7000", 2500], ...]`
- Available: REST and WebSocket

**Current Phase 5 Approach (Basic):**
```python
# Simple limit order execution
order = {
    "ticker": market_ticker,
    "side": "yes",
    "type": "limit",
    "yes_price": calculated_price,
    "count": position_size
}
kalshi_client.place_order(order)
```

**Pros of Basic:**
- ✅ Simple to implement
- ✅ Works well in liquid markets
- ✅ Fast to market (MVP)

**Cons of Basic:**
- ❌ Suboptimal fills in thin markets
- ❌ No price walking or adjustment
- ❌ Misses partial fill opportunities
- ❌ No depth analysis

---

## Decision

**DEFER advanced execution optimization to Phase 8.**

**Rationale:**

1. **Prove Edge Detection First**
   - Edge detection is the core value proposition
   - Must validate our probability models work before optimizing execution
   - 2-3% execution improvement is meaningless if edge detection fails

2. **Data-Driven Decision**
   - Phases 5-7 will generate real trading data
   - Measure actual slippage in our target markets
   - Quantify: Is 20-25% fill improvement worth the complexity?

3. **Market Liquidity Unknown**
   - Game outcome markets: Typically liquid (>100 contracts)
   - Derivative markets (lead amount, points): Less liquid (10-50 contracts)
   - Different strategies experience different liquidity conditions
   - Won't know true impact until we trade

4. **Complexity Cost**
   - Dynamic Depth Walker adds 3+ database tables
   - Execution state machine required
   - Per-split order tracking
   - Momentum calculations
   - 4-second monitoring loops
   - Higher API usage (could hit rate limits)

5. **Incremental Development**
   - Phase 5: Basic execution proves system works
   - Phase 6-7: Expansion to multiple sports with basic execution
   - Phase 8: Optimize execution based on Phase 5-7 learnings
   - Can implement if data shows significant need

---

## Phase 5 Basic Execution (MVP)

**Scope:**
```python
class OrderExecutor:
    def execute_trade(self, edge, market):
        """Simple, reliable execution."""
        # 1. Calculate position size (Kelly)
        size = self.calculate_position_size(edge)
        
        # 2. Determine order type
        if edge.expected_value > 0.15:
            order_type = "market"  # High conviction
        else:
            order_type = "limit"   # Default
        
        # 3. Place order
        order = {
            "ticker": market.ticker,
            "side": "yes" if edge.side == "yes" else "no",
            "type": order_type,
            "count": size,
            "yes_price": edge.target_price if order_type == "limit" else None
        }
        
        # 4. Track order
        result = self.kalshi_client.place_order(order)
        self.store_order(result)
        
        return result
```

**Features:**
- Simple limit/market choice
- Basic slippage control (max 2%)
- Order tracking in database
- Partial fill handling

**Success Metrics:**
- Track: Average slippage per trade
- Track: Fill rate (% of orders filled)
- Track: Time to fill
- Track: Market liquidity at execution time

---

## Phase 8 Advanced Execution (If Needed)

**Trigger Conditions for Implementation:**

Implement Phase 8 IF Phase 5-7 data shows:
- Average slippage > 1.5% in >25% of trades
- Fill failures in >10% of limit orders
- Thin markets (volume <100) represent >30% of opportunities

**If triggered, implement:**

### 1. Order Book Depth Tracking

**New Database Tables:**
```sql
CREATE TABLE order_book_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),
    timestamp TIMESTAMP DEFAULT NOW(),
    
    -- Depth data
    yes_depth JSONB NOT NULL,
    -- [
    --   {"price": "0.7100", "quantity": 5000},
    --   {"price": "0.7000", "quantity": 2500},
    --   {"price": "0.6900", "quantity": 1000}
    -- ]
    
    no_depth JSONB NOT NULL,
    
    -- Liquidity metrics
    total_yes_volume INT,
    total_no_volume INT,
    spread DECIMAL(10,4),
    
    -- Index for time-series queries
    INDEX idx_orderbook_market_time (market_id, timestamp)
);

CREATE TABLE execution_state (
    execution_id SERIAL PRIMARY KEY,
    edge_id INT REFERENCES edges(edge_id),
    method_id INT REFERENCES methods(method_id),
    
    -- Algorithm selection
    algorithm VARCHAR NOT NULL,  -- "simple_limit" | "dynamic_depth_walker"
    
    -- Walker state (if applicable)
    walker_state JSONB,
    -- {
    --   "momentum": 0.15,
    --   "walk_count": 3,
    --   "max_walks": 10,
    --   "ema_slippage": 0.012
    -- }
    
    -- Split configurations
    split_configs JSONB,
    -- [
    --   {"level": 1, "target_price": "0.7100", "quantity": 30},
    --   {"level": 2, "target_price": "0.7000", "quantity": 20}
    -- ]
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE split_orders (
    split_id SERIAL PRIMARY KEY,
    execution_id INT REFERENCES execution_state(execution_id),
    
    -- Order details
    order_id VARCHAR,  -- Kalshi order ID
    level INT,         -- Which depth level (1, 2, 3)
    target_price DECIMAL(10,4),
    quantity INT,
    
    -- Status tracking
    status VARCHAR,  -- "pending", "filled", "partial", "cancelled"
    filled_quantity INT DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    filled_at TIMESTAMP
);
```

### 2. Dynamic Depth Walker Algorithm

**Implementation:**
```python
class DynamicDepthWalker:
    """
    Hybrid execution algorithm combining:
    - Dynamic Spread Walker (momentum-driven price adjustments)
    - Liquidity Depth Optimizer (multi-level order splitting)
    """
    
    def __init__(self):
        self.walk_interval = 4  # seconds
        self.max_walks = 10
        self.min_volume_threshold = 50
        
    def execute(self, edge, market, orderbook):
        """Execute trade using depth-aware order splitting."""
        
        # 1. Analyze depth
        depth_analysis = self.analyze_depth(orderbook, edge.target_price)
        
        if depth_analysis["total_liquidity"] < self.min_volume_threshold:
            # Fallback to simple execution
            return self.simple_execution(edge, market)
        
        # 2. Calculate optimal splits (2-3 levels)
        splits = self.calculate_splits(
            total_quantity=edge.position_size,
            depth_levels=depth_analysis["levels"],
            target_price=edge.target_price
        )
        
        # 3. Place initial orders at each split level
        split_orders = []
        for split in splits:
            order = self.place_split_order(market, split)
            split_orders.append(order)
        
        # 4. Monitor and walk prices
        execution_state = ExecutionState(
            algorithm="dynamic_depth_walker",
            split_configs=splits,
            walker_state={"momentum": 0, "walk_count": 0}
        )
        
        # Start monitoring loop
        asyncio.create_task(
            self.monitor_and_walk(execution_state, split_orders)
        )
        
        return execution_state
    
    async def monitor_and_walk(self, state, split_orders):
        """Monitor fills and walk prices if needed."""
        
        while state.walker_state["walk_count"] < self.max_walks:
            await asyncio.sleep(self.walk_interval)
            
            # Check fill status
            for split in split_orders:
                status = self.check_order_status(split.order_id)
                
                if status.filled_quantity == split.quantity:
                    continue  # Fully filled, no action
                
                # Calculate momentum
                momentum = self.calculate_momentum(split.market_id)
                
                # Walk price if momentum indicates
                if momentum > 0.10:  # Significant upward pressure
                    new_price = self.walk_price(
                        current=split.target_price,
                        direction="up",
                        momentum=momentum
                    )
                    
                    # Cancel and replace
                    self.cancel_order(split.order_id)
                    new_order = self.place_split_order(
                        market=split.market,
                        split={"price": new_price, "quantity": split.quantity}
                    )
                    split.order_id = new_order.order_id
                    state.walker_state["walk_count"] += 1
            
            # Check if all filled
            if all(self.is_fully_filled(s) for s in split_orders):
                break
    
    def analyze_depth(self, orderbook, target_price):
        """Analyze orderbook depth around target price."""
        
        # Find "sweet spot" - price level with sufficient cumulative liquidity
        cumulative_volume = 0
        levels = []
        
        for level in orderbook.yes_depth:
            if Decimal(level["price"]) <= target_price:
                cumulative_volume += level["quantity"]
                levels.append({
                    "price": Decimal(level["price"]),
                    "quantity": level["quantity"],
                    "cumulative": cumulative_volume
                })
        
        return {
            "levels": levels,
            "total_liquidity": cumulative_volume,
            "spread": self.calculate_spread(orderbook)
        }
    
    def calculate_splits(self, total_quantity, depth_levels, target_price):
        """Calculate optimal order splits across depth levels."""
        
        # Simple split: 60% at best price, 40% at second level
        if len(depth_levels) < 2:
            return [{"price": target_price, "quantity": total_quantity}]
        
        return [
            {
                "level": 1,
                "price": depth_levels[0]["price"],
                "quantity": int(total_quantity * 0.6)
            },
            {
                "level": 2,
                "price": depth_levels[1]["price"],
                "quantity": int(total_quantity * 0.4)
            }
        ]
    
    def calculate_momentum(self, market_id):
        """Calculate volume momentum (delta average)."""
        
        # Get recent volume changes
        recent_snapshots = self.get_recent_snapshots(market_id, minutes=2)
        
        if len(recent_snapshots) < 2:
            return 0
        
        # Simple momentum: (current_volume - avg_volume) / avg_volume
        volumes = [s.total_yes_volume for s in recent_snapshots]
        current = volumes[-1]
        average = sum(volumes[:-1]) / len(volumes[:-1])
        
        momentum = (current - average) / average if average > 0 else 0
        return momentum
    
    def walk_price(self, current, direction, momentum):
        """Adjust price based on momentum."""
        
        # Aggressive walk if high momentum
        adjustment = Decimal("0.01") if momentum > 0.20 else Decimal("0.005")
        
        if direction == "up":
            return current + adjustment
        else:
            return current - adjustment
```

### 3. Method Integration

**Methods table includes execution algorithm:**
```sql
-- Method specifies which execution to use
INSERT INTO methods (
    method_name,
    method_version,
    strategy_id,
    model_id,
    execution_algorithm,
    execution_config
) VALUES (
    'aggressive_nfl',
    'v1.0',
    1,  -- live_continuous strategy
    2,  -- ensemble_nfl model
    'dynamic_depth_walker',
    '{
        "walk_interval": 4,
        "max_walks": 10,
        "min_volume_threshold": 50,
        "split_strategy": "60_40"
    }'
);
```

### 4. Performance Metrics

**Track execution quality:**
```sql
CREATE TABLE execution_metrics (
    metric_id SERIAL PRIMARY KEY,
    execution_id INT REFERENCES execution_state(execution_id),
    
    -- Fill metrics
    target_quantity INT,
    filled_quantity INT,
    fill_rate DECIMAL(6,4),  -- filled / target
    
    -- Price metrics
    target_price DECIMAL(10,4),
    average_fill_price DECIMAL(10,4),
    slippage DECIMAL(10,4),  -- (avg_fill - target) / target
    
    -- Timing metrics
    time_to_first_fill INT,  -- seconds
    time_to_full_fill INT,   -- seconds
    
    -- Algorithm metrics
    walks_executed INT,
    splits_used INT,
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Implementation Phases

### Phase 5 (Weeks 9-12) - Basic Execution
**Deliverables:**
- Simple limit/market order execution
- Order tracking
- Partial fill handling
- Slippage measurement
- Fill rate tracking

**Success Criteria:**
- [ ] Orders placed successfully via Kalshi API
- [ ] All orders tracked in database
- [ ] Slippage measured and logged
- [ ] Partial fills handled correctly

### Phase 6-7 (Weeks 13-16) - Multi-Sport Expansion
**Focus:** Expand to NBA, MLB, Tennis
**Execution:** Use basic Phase 5 execution
**Data Collection:**
- [ ] Track slippage across different sports
- [ ] Track liquidity profiles by market type
- [ ] Identify which strategies hit thin markets most

### Phase 8 (Weeks 17-18) - Advanced Execution (Conditional)
**Decision Point:** Review Phase 5-7 metrics

**IF metrics show need, implement:**
- [ ] Order book depth tracking
- [ ] Dynamic Depth Walker algorithm
- [ ] Execution state machine
- [ ] Split order management
- [ ] Performance comparison (basic vs advanced)

**Success Criteria:**
- [ ] 20-25% improvement in fill rates (thin markets)
- [ ] Slippage reduced by >50 basis points
- [ ] No increase in failed orders
- [ ] Algorithm handles 100+ concurrent executions

---

## API Integration Requirements

**Phase 5 (Basic):**
```python
# Endpoints needed
POST /portfolio/orders          # Place order
GET  /portfolio/orders/{id}     # Check order status
GET  /portfolio/fills           # Get fill history
```

**Phase 8 (Advanced):**
```python
# Additional endpoints needed
GET  /markets/{ticker}/orderbook  # Get depth data
DELETE /portfolio/orders/{id}     # Cancel order (for walking)

# WebSocket channels
ws://kalshi/orderbook/{ticker}    # Real-time depth updates
ws://kalshi/fills                 # Real-time fill notifications
```

---

## Risk Mitigation

**Phase 5 Risks:**
- **Slippage too high:** Implement tighter max_slippage limits
- **Low fill rates:** Adjust order pricing or switch to market orders
- **API failures:** Implement retry logic and fallbacks

**Phase 8 Risks:**
- **Complexity:** Extensive testing required, start with paper trading
- **API rate limits:** Monitor usage, implement request throttling
- **State management bugs:** Comprehensive unit and integration tests
- **Over-optimization:** Compare performance to basic execution regularly

---

## Alternative Execution Algorithms

**If Dynamic Depth Walker proves too complex, consider simpler improvements:**

1. **Time-Weighted Average Price (TWAP)**
   - Split order into 5-10 smaller orders
   - Execute one every N seconds
   - Reduces market impact

2. **Adaptive Limit Orders**
   - Place limit order
   - If not filled in 30 seconds, adjust price by 0.5¢
   - Repeat up to 5 times

3. **Volume-Weighted Slicing**
   - Query orderbook once
   - Split order proportional to visible liquidity
   - Place all splits simultaneously

---

## Performance Expectations

**Phase 5 (Basic Execution):**
- Liquid markets (volume >100): 0.5-1.0% slippage
- Thin markets (volume <50): 2-3% slippage
- Fill rate: 85-90%

**Phase 8 (Advanced Execution):**
- Liquid markets: 0.3-0.7% slippage (marginal improvement)
- Thin markets: 0.8-1.5% slippage (significant improvement)
- Fill rate: 95-98%

**Break-Even Analysis:**
- Implementation cost: 20-30 hours
- Benefit: 1.5% average slippage reduction
- Trade volume needed: ~500 trades to justify
- Expected: Reach 500 trades by Week 20 (Phase 7 complete)

---

## Review Schedule

**After Phase 5 (Week 12):**
- Review: Average slippage by market type
- Review: Fill rates by strategy
- Decision: Proceed with Phase 8 or defer further?

**After Phase 7 (Week 16):**
- Review: Cumulative slippage impact on P&L
- Review: Thin market frequency by sport
- Decision: Implement Phase 8 in Week 17-18?

---

## Documentation References

- **KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md**: Price precision requirements
- **API_INTEGRATION_GUIDE_V2.0.md**: Kalshi API endpoints and authentication
- **DATABASE_SCHEMA_SUMMARY_V1.4.md**: Order and execution tables
- **PHASE_8_ADVANCED_EXECUTION_SPEC.md**: Full Dynamic Depth Walker specification (this ADR references)

---

## Approval

**Decided By:** Project Lead  
**Date:** 2025-10-21  
**Review Date:** After Phase 5 completion (Week 12)  
**Implementation:** Phase 8 (Weeks 17-18, conditional on Phase 5-7 metrics)

---

## Summary

**Defer advanced execution optimization to Phase 8.** Focus Phase 5-7 on proving edge detection and basic execution. Collect real-world data on slippage and fill rates. Implement Dynamic Depth Walker only if metrics justify the complexity.

**Key Principle:** Optimize execution after validating edge detection, not before.
