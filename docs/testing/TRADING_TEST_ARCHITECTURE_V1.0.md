# Trading Module Test Architecture

**Version:** 1.0
**Created:** 2025-12-24
**Status:** Draft - For Review
**Context:** Kalshi DEMO 503 errors require alternative testing strategy

---

## Executive Summary

**Problem:** Kalshi DEMO environment returns 503 errors on order operations, making it impossible to test trading functionality against DEMO.

**Solution:** 4-layer testing architecture that separates business logic testing from API integration testing.

---

## The 503 Error Problem

### Root Cause Analysis (2025-12-24)

| Environment | GET Operations | POST/DELETE Orders |
|-------------|----------------|-------------------|
| DEMO | ✅ Works | ❌ 503 "exchange" service unavailable |
| PROD | ✅ Works | ✅ Works |

**Error Response:**
```json
{"error":{"code":"service_unavailable","message":"service_unavailable","service":"exchange"}}
```

### Impact on Testing

Without a working DEMO environment for orders, we cannot:
- Test order placement without real money
- Test order cancellation flows
- Test partial fill scenarios
- Test any Phase 5+ trading logic safely

---

## 4-Layer Testing Architecture

### Layer 1: Unit Tests (Mock Everything)

**Purpose:** Test business logic in complete isolation from external systems.

**What We Mock:**
- `KalshiClient` - Return predefined responses
- Database - Use in-memory SQLite or mocks
- Time - Control time for trailing stop tests
- Random - Control randomness for position sizing

**What We Test:**
- Trailing stop calculation logic
- Kelly criterion position sizing
- Exit condition evaluation (all 10 conditions)
- Order walking algorithm decisions
- P&L calculations
- Risk limit checks

**Example - Trailing Stop Unit Test:**
```python
class TestTrailingStopLogic:
    """Test trailing stop business logic with mocked dependencies."""

    def test_trailing_stop_triggers_at_threshold(self):
        """Trailing stop should trigger when price drops X% from peak."""
        # Setup - no real API calls
        mock_client = MockKalshiClient()
        mock_client.set_market_price("KXNFL-TEST", Decimal("0.70"))

        stop = TrailingStop(
            entry_price=Decimal("0.50"),
            peak_price=Decimal("0.80"),  # Market went up to 80 cents
            trail_percent=Decimal("0.10"),  # 10% trail
        )

        # Price dropped to 70 cents (12.5% from peak)
        current_price = Decimal("0.70")

        # Assert
        assert stop.should_exit(current_price) is True
        assert stop.exit_reason == "trailing_stop_triggered"

    def test_trailing_stop_updates_peak(self):
        """Peak price should update as market moves in our favor."""
        stop = TrailingStop(
            entry_price=Decimal("0.50"),
            peak_price=Decimal("0.60"),
            trail_percent=Decimal("0.10"),
        )

        # Market moves higher
        stop.update_peak(Decimal("0.75"))

        assert stop.peak_price == Decimal("0.75")
        assert stop.stop_price == Decimal("0.675")  # 75 - 10% = 67.5

    def test_kelly_criterion_position_size(self):
        """Kelly formula: f* = (bp - q) / b where b=odds, p=win prob, q=lose prob."""
        sizer = KellyPositionSizer(
            bankroll=Decimal("1000.00"),
            kelly_fraction=Decimal("0.25"),  # Quarter Kelly for safety
        )

        # Edge: 70% true prob at 60 cent market price
        position = sizer.calculate(
            true_probability=Decimal("0.70"),
            market_price=Decimal("0.60"),
        )

        # Full Kelly would be larger, but we use 1/4 Kelly
        assert position.size_dollars < Decimal("100.00")
        assert position.contracts > 0
```

**Coverage Target:** 95%+ for all trading logic classes

### Layer 2: Integration Tests (VCR Cassettes)

**Purpose:** Validate our code correctly handles real API responses.

**What We Record:**
- Order placement responses (PROD - one-time recording)
- Order cancellation responses
- Order status responses
- Market data responses
- Balance/position responses

**What We Test:**
- Response parsing (JSON → Python objects)
- Decimal conversion (string → Decimal)
- Error handling (4xx, 5xx responses)
- Rate limiting behavior

**Example - VCR Integration Test:**
```python
class TestKalshiOrderIntegration:
    """Test order operations against recorded API responses."""

    @pytest.mark.vcr("kalshi_order_lifecycle.yaml")
    def test_order_lifecycle_from_vcr(self, client):
        """Full order lifecycle using recorded responses."""
        # Place order (replays recorded 201 response)
        order = client.place_order(
            ticker="KXNFLGAME-25DEC27BALGB-GB",
            side="yes",
            action="buy",
            count=1,
            price=Decimal("0.02"),
            order_type="limit",
        )

        assert order["status"] == "resting"
        assert isinstance(order["yes_price_dollars"], Decimal)

        # Cancel (replays recorded 200 response)
        canceled = client.cancel_order(order["order_id"])
        assert canceled["status"] == "canceled"
```

**Coverage Target:** All API endpoints used by trading module

### Layer 3: Simulation Tests (Paper Trading)

**Purpose:** Test complex multi-step scenarios without real money.

**Implementation: MockKalshiClient with Simulation Logic**

```python
class SimulatedKalshiClient:
    """
    Simulates Kalshi order behavior for comprehensive testing.

    Features:
    - Simulated order book with configurable depth
    - Simulated fills based on price/quantity
    - Simulated partial fills
    - Simulated market price movement
    - Configurable latency and failures

    Educational Note:
        This is NOT a mock that returns static data.
        It's a SIMULATION that models real market behavior.

        Key differences:
        - Mock: Returns exactly what you tell it
        - Simulation: Models behavior, outcomes depend on inputs
    """

    def __init__(self, initial_markets: dict[str, MarketState]):
        self.markets = initial_markets
        self.orders: dict[str, SimulatedOrder] = {}
        self.positions: dict[str, int] = {}
        self.balance = Decimal("10000.00")
        self.fills: list[SimulatedFill] = []
        self.time = SimulatedTime()

    def place_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int,
        price: Decimal | None,
        order_type: str,
    ) -> OrderData:
        """
        Simulate order placement with realistic behavior.

        Behavior:
        - Market orders: Fill immediately at current price + slippage
        - Limit orders: Fill if price is favorable, else rest in book
        - Partial fills: Based on simulated liquidity at price level
        """
        market = self.markets[ticker]
        order_id = f"sim_{uuid4()}"

        if order_type == "market":
            # Market order - fill immediately with slippage
            fill_price = self._calculate_market_fill_price(market, side, count)
            fill = self._execute_fill(order_id, ticker, side, action, count, fill_price)
            return self._order_response(order_id, "executed", fill)

        else:  # limit order
            # Check if limit price is favorable
            if self._is_immediately_fillable(market, side, price):
                fill = self._execute_fill(order_id, ticker, side, action, count, price)
                return self._order_response(order_id, "executed", fill)
            else:
                # Order rests in book
                self.orders[order_id] = SimulatedOrder(
                    order_id=order_id,
                    ticker=ticker,
                    side=side,
                    action=action,
                    count=count,
                    price=price,
                    status="resting",
                )
                return self._order_response(order_id, "resting", None)

    def simulate_market_move(self, ticker: str, new_price: Decimal):
        """
        Simulate market price movement.

        This triggers:
        - Resting order fills (if price crosses)
        - Trailing stop evaluations
        - P&L recalculations
        """
        market = self.markets[ticker]
        old_price = market.yes_bid_dollars
        market.yes_bid_dollars = new_price
        market.yes_ask_dollars = new_price + Decimal("0.01")

        # Check if any resting orders should fill
        for order in self.orders.values():
            if order.ticker == ticker and order.status == "resting":
                if self._should_fill_on_move(order, old_price, new_price):
                    self._execute_fill(
                        order.order_id,
                        order.ticker,
                        order.side,
                        order.action,
                        order.remaining_count,
                        order.price,
                    )

    def simulate_time_advance(self, seconds: int):
        """Advance simulated time for testing time-based logic."""
        self.time.advance(seconds)
```

**Simulation Test Examples:**

```python
class TestTrailingStopSimulation:
    """Test trailing stop behavior with simulated market."""

    def test_trailing_stop_exit_on_price_drop(self, simulated_client):
        """Full trailing stop scenario with simulated market movement."""
        # Setup: Enter position at $0.50
        position_manager = PositionManager(client=simulated_client)
        position = position_manager.open_position(
            ticker="KXNFL-SIM",
            side="yes",
            size=10,
            entry_price=Decimal("0.50"),
        )

        # Configure trailing stop
        position.set_trailing_stop(trail_percent=Decimal("0.10"))

        # Simulate market moving up (should update peak)
        simulated_client.simulate_market_move("KXNFL-SIM", Decimal("0.70"))
        position_manager.check_exits()

        assert position.status == "open"
        assert position.trailing_stop.peak_price == Decimal("0.70")

        # Simulate market dropping (should trigger stop at 63 cents)
        simulated_client.simulate_market_move("KXNFL-SIM", Decimal("0.62"))
        exit_result = position_manager.check_exits()

        assert position.status == "closed"
        assert exit_result.reason == "trailing_stop"
        assert exit_result.exit_price == Decimal("0.62")

    def test_partial_fill_position_sizing(self, simulated_client):
        """Test position sizing with partial fills."""
        # Configure thin liquidity
        simulated_client.set_liquidity("KXNFL-SIM", depth=50)  # Only 50 contracts available

        sizer = PositionSizer(client=simulated_client)

        # Try to buy 100 contracts
        result = sizer.execute_sized_entry(
            ticker="KXNFL-SIM",
            target_size=100,
            max_slippage=Decimal("0.02"),
        )

        # Should get partial fill due to liquidity
        assert result.filled_count < 100
        assert result.status == "partial"
        assert result.remaining_count > 0

    def test_order_walking_strategy(self, simulated_client):
        """Test order walking with simulated book updates."""
        walker = OrderWalker(
            client=simulated_client,
            max_walk_cents=5,
            walk_interval_seconds=4,
        )

        # Start walk at $0.50
        walk = walker.start_walk(
            ticker="KXNFL-SIM",
            side="yes",
            count=10,
            start_price=Decimal("0.50"),
        )

        # Simulate time passing without fill
        simulated_client.simulate_time_advance(4)
        walker.check_walks()

        # Should have walked up one cent
        assert walk.current_price == Decimal("0.51")

        # Simulate fill at $0.51
        simulated_client.simulate_market_move("KXNFL-SIM", Decimal("0.50"))
        walker.check_walks()

        assert walk.status == "filled"
```

**Coverage Target:** All trading scenarios documented in specs

### Layer 4: Smoke Tests (Minimal PROD)

**Purpose:** Validate critical paths work against real PROD API.

**Constraints:**
- Use unfillable prices ($0.02 for YES, $0.98 for NO)
- Cancel immediately after placement
- Maximum 1-2 contracts
- Run infrequently (not on every commit)

**What We Test:**
- Authentication still works
- API contract hasn't changed
- Response parsing still valid
- Rate limiting respected

**Example:**
```python
class TestProdSmokeTests:
    """
    Minimal PROD API validation.

    WARNING: These tests use REAL money!
    - Only run manually or on release branches
    - All orders placed at unfillable prices
    - All orders canceled immediately
    """

    @pytest.mark.prod
    @pytest.mark.slow
    def test_prod_order_lifecycle_smoke(self, prod_client):
        """Verify PROD order API still works as expected."""
        # Place at unfillable price
        order = prod_client.place_order(
            ticker="KXNFLGAME-25DEC27BALGB-GB",
            side="yes",
            action="buy",
            count=1,
            price=Decimal("0.02"),  # Won't fill
            order_type="limit",
        )

        assert order["status"] == "resting"

        # Immediately cancel
        time.sleep(1)
        canceled = prod_client.cancel_order(order["order_id"])
        assert canceled["status"] == "canceled"
```

---

## Test Organization

```
tests/
├── unit/                           # Layer 1: Pure logic tests
│   ├── trading/
│   │   ├── test_trailing_stop.py   # Trailing stop logic
│   │   ├── test_position_sizer.py  # Kelly criterion
│   │   ├── test_exit_evaluator.py  # 10 exit conditions
│   │   ├── test_order_walker.py    # Walking algorithm
│   │   └── test_pnl_calculator.py  # P&L math
│   └── ...
├── integration/                    # Layer 2: VCR tests
│   ├── api_connectors/
│   │   └── test_kalshi_client_vcr.py
│   └── ...
├── simulation/                     # Layer 3: Paper trading
│   ├── conftest.py                 # SimulatedKalshiClient fixtures
│   ├── test_trailing_stop_sim.py
│   ├── test_position_lifecycle_sim.py
│   ├── test_order_walking_sim.py
│   └── test_strategy_execution_sim.py
├── smoke/                          # Layer 4: Minimal PROD
│   └── test_prod_smoke.py          # Manual only
└── fixtures/
    ├── simulated_client.py         # SimulatedKalshiClient
    ├── simulated_market.py         # Market state simulation
    └── api_responses.py            # Static mock responses
```

---

## Coverage Matrix

| Trading Feature | Unit | VCR | Simulation | Smoke |
|-----------------|------|-----|------------|-------|
| Trailing Stop Logic | ✅ | - | ✅ | - |
| Stop Loss Logic | ✅ | - | ✅ | - |
| Position Sizing (Kelly) | ✅ | - | ✅ | - |
| Exit Evaluation (10 conditions) | ✅ | - | ✅ | - |
| Order Walking | ✅ | - | ✅ | - |
| Order Placement | ✅ | ✅ | ✅ | ✅ |
| Order Cancellation | ✅ | ✅ | ✅ | ✅ |
| Partial Fills | ✅ | - | ✅ | - |
| Market Price Movement | - | - | ✅ | - |
| API Authentication | - | ✅ | - | ✅ |
| Rate Limiting | - | ✅ | - | - |
| Decimal Precision | ✅ | ✅ | ✅ | - |

---

## When to Run Each Layer

| Layer | Trigger | Duration | CI? |
|-------|---------|----------|-----|
| Unit | Every commit | ~5 sec | ✅ |
| VCR | Every commit | ~10 sec | ✅ |
| Simulation | Every PR | ~30 sec | ✅ |
| Smoke | Release only | ~60 sec | ❌ Manual |

---

## Implementation Priority

1. **Phase 1 (Now):** VCR cassettes for existing API client ✅ DONE
2. **Phase 5a:** SimulatedKalshiClient for trading logic testing
3. **Phase 5a:** Unit tests for trailing stop, position sizing
4. **Phase 5b:** Simulation tests for order walking
5. **Release:** Smoke tests for PROD validation

---

## References

- ADR-TBD: Kalshi DEMO 503 Error Mitigation
- TRAILING_STOP_GUIDE_V1.0.md
- POSITION_MANAGEMENT_GUIDE_V1.0.md
- EXIT_EVALUATION_SPEC_V1.0.md
- ADVANCED_EXECUTION_SPEC_V1.0.md
