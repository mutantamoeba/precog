**Document:** HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md
**Version:** 1.0
**Created:** 2025-11-08
**Last Updated:** 2025-11-08
**Purpose:** Comprehensive property-based testing implementation plan for Precog trading platform
**Target Audience:** Development team, QA, architects
**Status:** 🔵 Planned (Phase 1.5+)

---

# Hypothesis Property-Based Testing Implementation Plan

## Executive Summary

This document outlines the comprehensive integration of Hypothesis property-based testing across the entire Precog trading platform. Property-based testing validates mathematical invariants across thousands of automatically-generated test cases, catching edge cases that traditional example-based tests miss.

**Why This Matters:**
> "Remember that the quality of the models, edge detection and methods are core to the success of the project." — User, 2025-11-08

Property-based testing is **critical** for trading systems because:
- **Edge detection errors** → losing trades
- **Model validation gaps** → poor probability estimates
- **Position sizing bugs** → risk management failures
- **Backtesting flaws** → false confidence in strategies

**Current Status:**
- ✅ **Proof-of-Concept Complete** (2025-11-08): 26 property tests, 2600+ generated test cases
- ✅ **Kelly Criterion Properties** (11 tests): Position sizing invariants validated
- ✅ **Edge Detection Properties** (15 tests): Core trading logic validated
- 🔵 **Next Steps**: Expand to 12 additional domains (Phase 1.5 through Phase 5)

**Implementation Timeline:**
- **Phase 1.5** (6-8 hours): Core trading logic (edge detection, Kelly, config validation)
- **Phase 2** (8-10 hours): Data validation, model testing, strategy versioning
- **Phase 3** (6-8 hours): Order book analysis, entry optimization, liquidity
- **Phase 4** (8-10 hours): Model ensemble, A/B testing, backtesting validation
- **Phase 5** (10-12 hours): Position management, exit optimization, reporting

**Total Estimated Investment:** 38-48 hours
**Expected Coverage Increase:** +15-20% (from property tests discovering untested paths)
**Bug Prevention:** Potentially **catastrophic** (negative edge trades, oversized positions, broken trailing stops)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Proof-of-Concept Results](#proof-of-concept-results)
3. [Domain Coverage Plan](#domain-coverage-plan)
4. [Implementation Roadmap](#implementation-roadmap)
5. [Custom Hypothesis Strategies](#custom-hypothesis-strategies)
6. [Testing Infrastructure Updates](#testing-infrastructure-updates)
7. [Documentation Integration](#documentation-integration)
8. [Success Metrics](#success-metrics)
9. [Future Enhancements](#future-enhancements)

---

## 1. Introduction

### What is Property-Based Testing?

**Traditional Example-Based Testing:**
```python
def test_kelly_sizing():
    """Test Kelly criterion with specific examples."""
    edge = Decimal("0.10")
    kelly_fraction = Decimal("0.25")
    bankroll = Decimal("10000")

    position = calculate_kelly_size(edge, kelly_fraction, bankroll)

    assert position == Decimal("250")  # Expected: 10000 * 0.10 * 0.25
```

**Problem:** What if edge = 0.9999999? What if bankroll = $999,999,999.99? What if kelly_fraction = 0.00000001? We can't test every scenario manually.

**Property-Based Testing:**
```python
@given(
    edge=st.decimals(min_value=0, max_value=0.5, places=4),
    kelly_frac=st.decimals(min_value=0, max_value=1, places=2),
    bankroll=st.decimals(min_value=100, max_value=100000, places=2),
)
def test_position_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    """PROPERTY: Position size MUST NEVER exceed bankroll (for ALL inputs)."""
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll
```

**Benefits:**
- Tests **mathematical invariants** that MUST hold for ALL inputs
- Hypothesis **automatically generates** thousands of test cases (including edge cases)
- Finds bugs humans wouldn't think to test (probability = 0.00000001, spread = 0.4999)
- **Self-maintaining** - tests adapt as implementation changes

### Why Hypothesis for Trading Systems?

Trading systems are **mathematical** in nature. Every component has **invariants**:

| Component | Invariant | Consequence if Violated |
|-----------|-----------|-------------------------|
| Kelly Criterion | position ≤ bankroll | Margin call, rejected order |
| Edge Detection | negative edge → don't trade | Guaranteed losses over time |
| Trailing Stops | stop only tightens, never loosens | Risk management failure |
| Model Probabilities | output ∈ [0, 1] | Invalid bet sizing |
| Spread Calculation | ask ≥ bid | Crossed market, arbitrage detection failure |
| Position Correlation | correlation ≤ max_threshold | Portfolio concentration risk |
| Backtest Equity Curve | monotonically decreasing drawdown from peak | Invalid performance metrics |

Property-based testing validates these invariants across **billions** of input combinations.

---

## 2. Proof-of-Concept Results

### What We Built (2025-11-08)

Created two comprehensive property test suites:

1. **`tests/property/test_kelly_criterion_properties.py`**
   - 11 properties tested
   - 1100+ generated test cases
   - Mathematical properties validated:
     - Position size never exceeds bankroll
     - Position size always non-negative
     - Zero edge → zero position
     - Negative edge → zero position (critical!)
     - Kelly fraction scales position linearly
     - Bankroll scales position linearly
     - Edge increases position monotonically
     - Max position constraint respected
     - Invalid inputs raise errors

2. **`tests/property/test_edge_detection_properties.py`**
   - 15 properties tested
   - 1500+ generated test cases
   - Mathematical properties validated:
     - Edge formula correctness
     - Fees always reduce edge (critical!)
     - Zero edge boundary condition
     - Negative edge never recommends trade (critical!)
     - Edge bounded by [-1.15, 1.0]
     - Edge monotonicity with probability and price
     - Spread reduces realizable edge
     - Realizable edge uses ask price (not bid)
     - Threshold logic correctness
     - Invalid inputs raise errors

### Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-8.4.2, pluggy-1.6.0
hypothesis profile 'default'
plugins: hypothesis-6.146.0
collecting ... collected 26 items

tests/property/test_edge_detection_properties.py::test_edge_formula_correctness PASSED
tests/property/test_edge_detection_properties.py::test_fees_always_reduce_edge PASSED
tests/property/test_edge_detection_properties.py::test_negative_edge_never_recommends_trade PASSED
... [26 total tests] ...

======================= 26 passed in 3.32s =======================
```

**Performance:**
- **2600+ test cases** generated automatically
- **3.32 seconds** total execution time (~0.13s per property)
- **Zero bugs found** (all invariants hold in simplified implementations)

### Key Insights

1. **Fast Execution:** Property tests are **fast** (~1ms per example). 100 examples per property = still <1 second.
2. **Comprehensive Coverage:** Testing 2600 scenarios manually would take **weeks**. Hypothesis did it in **3 seconds**.
3. **Self-Documenting:** Property tests **explain** what the code should do ("position never exceeds bankroll") better than example tests.
4. **Regression Prevention:** If future code changes violate an invariant, Hypothesis **immediately** finds a counterexample.

---

## 3. Domain Coverage Plan

### Phase 1.5: Core Trading Logic (6-8 hours)

**Priority:** 🔴 Critical (before Phase 2 live trading)

#### 3.1 Kelly Criterion Position Sizing

**File:** `tests/property/test_kelly_criterion_properties.py` ✅ **COMPLETE**

**Properties:** (11 tests)
- Position size never exceeds bankroll
- Position size always non-negative
- Zero edge → zero position
- Negative edge → zero position
- Kelly fraction scales position linearly
- Bankroll scales position linearly
- Edge increases position monotonically
- Max position constraint respected
- Invalid inputs raise errors
- Position size reasonable bounds (heuristic)

**Status:** ✅ Proof-of-concept complete

---

#### 3.2 Edge Detection

**File:** `tests/property/test_edge_detection_properties.py` ✅ **COMPLETE**

**Properties:** (15 tests)
- Edge formula correctness
- Fees always reduce edge
- Zero edge boundary condition
- Negative edge never recommends trade
- Edge bounded by valid range
- Edge monotonicity with probability and price
- Spread impact on realizable edge
- Realizable edge uses ask price
- Threshold logic correctness
- Invalid inputs raise errors

**Status:** ✅ Proof-of-concept complete

---

#### 3.3 Configuration Validation

**File:** `tests/property/test_config_validation_properties.py` (NEW)

**Properties:** (8-10 tests)
- Kelly fraction in [0, 1]
- Min edge threshold in [0, 1]
- Fees in [0, 0.50] (50% max reasonable fee)
- Max position ≤ bankroll
- Trailing stop activation threshold > 0
- Profit target > 0
- Stop loss < 1 (can't lose more than 100%)
- Correlation threshold in [0, 1]
- YAML Decimal values parse correctly (no float contamination)
- Required config fields present

**Estimated Time:** 2 hours

**Why This Matters:** Invalid config values cause silent failures or catastrophic losses. Property tests catch typos (kelly_fraction: 2.5 instead of 0.25) before production.

---

### Phase 2: Data Validation & Model Testing (8-10 hours)

**Priority:** 🟡 High (before Phase 3 live data)

#### 3.4 Historical Data Validation

**File:** `tests/property/test_historical_data_properties.py` (NEW)

**Properties:** (10-12 tests)
- Game timestamps monotonically increasing
- Score differentials valid (score_home - score_away)
- Scores non-negative
- Final scores ≥ halftime scores (monotonic)
- Time remaining decreases monotonically
- Possession percentage in [0, 100]
- Elo ratings in valid range (800-2200 typical)
- Market prices in [0, 1]
- Settlement timestamps after game timestamps
- No duplicate game IDs in time series data
- Missing data percentage below threshold

**Estimated Time:** 3 hours

**Why This Matters:** Bad historical data → bad model training → poor predictions. Property tests validate data integrity BEFORE model training.

**Example Property:**
```python
@given(
    game_timeline=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=3600),  # Time remaining
            st.integers(min_value=0, max_value=100),   # Score
        ),
        min_size=5,
        max_size=20,
    )
)
def test_scores_monotonically_increase(game_timeline):
    """PROPERTY: Scores should only increase (never decrease) as game progresses."""
    sorted_timeline = sorted(game_timeline, key=lambda x: -x[0])  # Sort by time remaining (descending)

    for i in range(len(sorted_timeline) - 1):
        current_time, current_score = sorted_timeline[i]
        next_time, next_score = sorted_timeline[i + 1]

        assert next_score >= current_score, "Score decreased during game!"
```

---

#### 3.5 Model Validation

**File:** `tests/property/test_model_validation_properties.py` (NEW)

**Properties:** (12-15 tests)
- Model output probabilities in [0, 1]
- Probabilities sum to 1 for multi-class (YES + NO = 1)
- Model predictions deterministic (same input → same output)
- Ensemble weights sum to 1
- Model version immutability (config never changes for same version)
- Feature extraction produces finite values (no NaN, no Inf)
- Model confidence scores in [0, 1]
- Calibration error bounded (predicted vs actual within tolerance)
- Model performance metrics monotonic (accuracy, log-loss, Brier score)
- Model retraining improves metrics (or raises alert)
- A/B test statistical significance validation

**Estimated Time:** 4 hours

**Why This Matters:** Model bugs propagate to edge detection, position sizing, and ultimately profits/losses. Property tests validate model mathematical correctness.

**Example Property:**
```python
@given(
    elo_home=st.integers(min_value=800, max_value=2200),
    elo_away=st.integers(min_value=800, max_value=2200),
    home_advantage=st.integers(min_value=0, max_value=200),
)
def test_model_outputs_valid_probability(elo_home, elo_away, home_advantage):
    """PROPERTY: Model must ALWAYS output probability in [0, 1]."""
    features = extract_features(elo_home, elo_away, home_advantage)
    probability = model.predict(features)

    assert Decimal("0") <= probability <= Decimal("1"), f"Invalid probability: {probability}"
```

---

#### 3.6 Strategy Versioning

**File:** `tests/property/test_strategy_versioning_properties.py` (NEW)

**Properties:** (6-8 tests)
- Strategy version immutability (config never changes)
- Status transitions valid (draft → testing → active → deprecated, never backwards)
- Semantic versioning correctness (v1.0 → v1.1 = minor, v1.0 → v2.0 = major)
- Trade attribution links to exact version
- Active strategy count ≤ max_active_strategies
- No duplicate strategy names + versions
- Version comparison logic (v1.1 > v1.0)

**Estimated Time:** 2 hours

**Why This Matters:** Strategy version bugs break A/B testing and trade attribution. Can't evaluate performance if config changes mid-test.

---

### Phase 3: Order Book & Entry Optimization (6-8 hours)

**Priority:** 🟡 High (before Phase 4 live execution)

#### 3.7 Order Book Depth Analysis

**File:** `tests/property/test_order_book_properties.py` (NEW)

**Properties:** (10-12 tests)
- Bid prices ≤ ask prices (no crossed market)
- Order book prices sorted (descending bids, ascending asks)
- Quantities positive
- Total liquidity at each level correct
- Spread = ask - bid ≥ 0
- Mid-price = (bid + ask) / 2
- Volume-weighted average price (VWAP) within bid-ask range
- Order book depth sufficient for position size (liquidity check)
- Price impact calculation correctness (slippage estimation)
- Liquidity evaporates correctly (orders filled reduce depth)

**Estimated Time:** 3 hours

**Why This Matters:** Order book analysis determines entry price and slippage. Bugs cause poor executions ("bought at ask when bid had liquidity").

**Example Property:**
```python
@given(
    bids=st.lists(
        st.tuples(
            st.decimals(min_value=0.01, max_value=0.99, places=4),  # Price
            st.integers(min_value=1, max_value=10000),              # Quantity
        ),
        min_size=3,
        max_size=10,
    ),
    asks=st.lists(
        st.tuples(
            st.decimals(min_value=0.01, max_value=0.99, places=4),  # Price
            st.integers(min_value=1, max_value=10000),              # Quantity
        ),
        min_size=3,
        max_size=10,
    ),
)
def test_order_book_no_crossed_market(bids, asks):
    """PROPERTY: Best bid must be < best ask (no arbitrage opportunity)."""
    sorted_bids = sorted(bids, key=lambda x: -x[0])  # Descending
    sorted_asks = sorted(asks, key=lambda x: x[0])   # Ascending

    best_bid_price = sorted_bids[0][0] if sorted_bids else Decimal("0")
    best_ask_price = sorted_asks[0][0] if sorted_asks else Decimal("1")

    assert best_bid_price < best_ask_price, "Crossed market detected!"
```

---

#### 3.8 Entry Optimization

**File:** `tests/property/test_entry_optimization_properties.py` (NEW)

**Properties:** (8-10 tests)
- Optimal entry price ≤ ask (can't buy below market)
- Entry size ≤ available liquidity at price level
- Price improvement (optimal entry < worst-case ask) when depth available
- Slippage estimation accuracy (predicted vs actual < tolerance)
- Order splitting correctness (sum of splits = total size)
- Execution urgency vs price impact trade-off
- No entry when liquidity insufficient
- Entry price accounting for fees (total cost calculation)

**Estimated Time:** 3 hours

**Why This Matters:** Entry optimization saves 0.5-2% per trade. On $100K capital, that's $500-$2000 per trade.

---

### Phase 4: Model Ensemble & Backtesting (8-10 hours)

**Priority:** 🟢 Medium (before Phase 5 live trading)

#### 3.9 Ensemble Model Properties

**File:** `tests/property/test_ensemble_properties.py` (NEW)

**Properties:** (8-10 tests)
- Ensemble weights sum to 1
- Ensemble output is weighted average of component models
- Ensemble output in [0, 1] (even if individual models output extreme values)
- Adding model with weight 0 doesn't change ensemble output
- Ensemble confidence bounded by component confidences
- Ensemble variance calculation correctness
- Ensemble performance ≥ best individual model (or within tolerance)
- Model correlation matrix symmetric and positive semi-definite

**Estimated Time:** 3 hours

**Why This Matters:** Ensemble bugs cause poor probability estimates. If weights don't sum to 1, output probabilities invalid.

---

#### 3.10 Backtesting Validation

**File:** `tests/property/test_backtesting_properties.py` (NEW)

**Properties:** (12-15 tests)
- Equity curve monotonically non-decreasing (with wins) or decreasing (with losses)
- Drawdown ≤ peak equity at all times
- Sharpe ratio calculation correctness
- Win rate in [0, 1]
- Profit factor ≥ 0 (total wins / total losses)
- Max drawdown ≤ initial capital (can't lose more than 100%)
- Trade count = sum of wins + losses + breakevens
- PnL = sum of all trade PnLs
- Commission deducted from PnL
- Backtest timestamps chronological (no lookahead bias)
- Position sizes valid at all timestamps
- No trades executed when market closed
- Forward test results ≈ backtest results (within tolerance, accounting for variance)

**Estimated Time:** 4 hours

**Why This Matters:** Backtest bugs give false confidence. "Strategy is profitable!" → Reality: "Lost 50% in first month."

**Example Property:**
```python
@given(
    trades=st.lists(
        st.tuples(
            st.decimals(min_value=-1000, max_value=1000, places=2),  # PnL
            st.decimals(min_value=0, max_value=100, places=2),        # Commission
        ),
        min_size=10,
        max_size=100,
    )
)
def test_backtest_total_pnl_matches_sum_of_trades(trades):
    """PROPERTY: Total PnL = sum of (trade_pnl - commission) for all trades."""
    total_pnl = sum(pnl - commission for pnl, commission in trades)

    backtest_result = run_backtest(trades)

    tolerance = Decimal("0.01")
    assert abs(backtest_result["total_pnl"] - total_pnl) <= tolerance
```

---

#### 3.11 A/B Testing Validation

**File:** `tests/property/test_ab_testing_properties.py` (NEW)

**Properties:** (6-8 tests)
- Sample size sufficient for statistical power
- p-value in [0, 1]
- Confidence interval contains sample mean
- Statistical significance threshold validation (alpha = 0.05)
- Effect size calculation correctness (Cohen's d)
- Test duration sufficient (avoid peeking)
- Randomization correctness (no bias in assignment)
- Multiple testing correction (Bonferroni, Benjamini-Hochberg)

**Estimated Time:** 2 hours

**Why This Matters:** A/B test bugs lead to wrong strategy selection. "Strategy A is better!" → Reality: "Just got lucky."

---

### Phase 5: Position Management & Exit Optimization (10-12 hours)

**Priority:** 🔴 Critical (before Phase 5b live exits)

#### 3.12 Position Management

**File:** `tests/property/test_position_management_properties.py` (NEW)

**Properties:** (15-18 tests)
- Total position value ≤ bankroll
- Individual position size ≤ max_position_size
- Correlation matrix limits respected
- Position health score in [0, 1]
- Profit/loss calculation correctness
- Unrealized PnL = (current_price - entry_price) * quantity
- Realized PnL updated on position close
- Position rebalancing maintains total exposure
- Hedge position sizes offset original position
- No over-leveraging (sum of position values ≤ bankroll * max_leverage)
- Position lifecycle state transitions valid
- Trailing stop updates correct (tightens but never loosens)
- Profit target triggers at correct price
- Stop loss triggers at correct price
- Partial exit maintains position integrity

**Estimated Time:** 5 hours

**Why This Matters:** Position management bugs cause catastrophic losses. "Stop loss didn't trigger" → "Lost 80% on single position."

**Example Property:**
```python
@given(
    entry_price=st.decimals(min_value=0.10, max_value=0.90, places=4),
    quantity=st.integers(min_value=1, max_value=10000),
    price_sequence=st.lists(
        st.decimals(min_value=0.01, max_value=0.99, places=4),
        min_size=10,
        max_size=50,
    ),
)
def test_trailing_stop_only_tightens(entry_price, quantity, price_sequence):
    """PROPERTY: Trailing stop MUST ONLY tighten, never loosen."""
    position = create_position(entry_price, quantity, side="YES")
    trailing_stop = TrailingStop(
        entry_price=entry_price,
        activation_threshold=Decimal("0.10"),
        trail_percent=Decimal("0.05"),
    )

    for price in price_sequence:
        old_stop_level = trailing_stop.stop_level
        trailing_stop.update(price)
        new_stop_level = trailing_stop.stop_level

        # For YES position, stop level should only increase (tighten)
        assert new_stop_level >= old_stop_level, "Trailing stop loosened!"
```

---

#### 3.13 Exit Management

**File:** `tests/property/test_exit_management_properties.py` (NEW)

**Properties:** (12-15 tests)
- Exit price ≥ bid (can't sell above market)
- Exit size ≤ current position size (can't sell more than you have)
- Partial exit reduces position correctly
- Exit priority hierarchy respected (mandatory exits execute first)
- Profit target exit price ≥ entry price (for profitable exit)
- Stop loss exit price ≤ entry price (for loss exit)
- Exit conditions evaluated correctly (10-condition hierarchy)
- Order walking doesn't overshoot target exit size
- Price improvement when liquidity available
- Slippage calculation correctness
- Exit PnL = (exit_price - entry_price) * quantity - fees
- No exit when liquidity insufficient
- Exit urgency vs price impact trade-off

**Estimated Time:** 4 hours

**Why This Matters:** Exit optimization is **more important** than entry. "I bought at good price but sold at terrible price" → losses.

---

#### 3.14 Reporting & Metrics

**File:** `tests/property/test_reporting_properties.py` (NEW)

**Properties:** (8-10 tests)
- Performance metrics bounded (win rate ∈ [0, 1], Sharpe ratio ∈ ℝ)
- Metrics internally consistent (total_pnl = sum of trade_pnls)
- Daily PnL sum = total PnL
- Trade count = wins + losses + breakevens
- Portfolio value = sum of position values + cash
- Drawdown calculation correctness
- Risk-adjusted returns calculation (Sharpe, Sortino, Calmar)
- Attribution reporting correctness (strategy, model version)
- Time-weighted returns vs money-weighted returns
- Benchmark comparison calculations

**Estimated Time:** 2 hours

**Why This Matters:** Reporting bugs hide problems. "Sharpe ratio = 3.0!" → Reality: "Calculation bug, actual Sharpe = 0.5."

---

## 4. Implementation Roadmap

### Timeline Overview

| Phase | Duration | Properties | Test Cases | Priority | Dependencies |
|-------|----------|------------|------------|----------|--------------|
| **Phase 1.5** | 6-8 hours | ~35 | 3500+ | 🔴 Critical | Phase 1 complete |
| **Phase 2** | 8-10 hours | ~35 | 3500+ | 🟡 High | Phase 1.5 complete |
| **Phase 3** | 6-8 hours | ~22 | 2200+ | 🟡 High | Phase 2 complete |
| **Phase 4** | 8-10 hours | ~28 | 2800+ | 🟢 Medium | Phase 3 complete |
| **Phase 5** | 10-12 hours | ~45 | 4500+ | 🔴 Critical | Phase 4 complete |
| **TOTAL** | **38-48 hours** | **~165** | **16,500+** | — | — |

### Phase 1.5: Core Trading Logic (6-8 hours) - **NEXT STEPS**

**Target Completion:** 1-2 weeks after CLI implementation

**Tasks:**
1. ✅ **Kelly Criterion Properties** (COMPLETE - 2 hours)
   - Already implemented: `tests/property/test_kelly_criterion_properties.py`
   - 11 properties, 1100+ test cases
   - Status: ✅ All passing

2. ✅ **Edge Detection Properties** (COMPLETE - 2 hours)
   - Already implemented: `tests/property/test_edge_detection_properties.py`
   - 15 properties, 1500+ test cases
   - Status: ✅ All passing

3. 🔵 **Configuration Validation Properties** (NEW - 2 hours)
   - Create: `tests/property/test_config_validation_properties.py`
   - 8-10 properties for YAML config validation
   - Test Decimal conversion, range validation, required fields
   - Integrate with `config/config_loader.py`

**Acceptance Criteria:**
- ✅ All Phase 1.5 property tests passing
- ✅ Coverage increase ≥ 3% (property tests discover new paths)
- ✅ CI integration complete (property tests run on every PR)
- ✅ Documentation updated (Pattern 9 in CLAUDE.md)

**Deliverables:**
- 3 property test files (2 complete, 1 new)
- ~35 total properties
- ~3500 auto-generated test cases
- Updated `pyproject.toml` Hypothesis config
- Updated CLAUDE.md with Pattern 9

---

### Phase 2: Data & Model Testing (8-10 hours)

**Target Completion:** 2-3 weeks after Phase 1.5

**Tasks:**
1. 🔵 **Historical Data Validation** (3 hours)
2. 🔵 **Model Validation** (4 hours)
3. 🔵 **Strategy Versioning** (2 hours)

**Dependencies:**
- Phase 1 data ingestion complete (ESPN API, Balldontlie API)
- Model training infrastructure (Phase 2+)

---

### Phase 3: Order Book & Entry (6-8 hours)

**Target Completion:** 1-2 weeks after Phase 2

**Tasks:**
1. 🔵 **Order Book Depth Analysis** (3 hours)
2. 🔵 **Entry Optimization** (3 hours)

**Dependencies:**
- Order book data access (Kalshi API WebSocket - Phase 3+)
- Entry optimization algorithm (Phase 3+)

---

### Phase 4: Ensemble & Backtesting (8-10 hours)

**Target Completion:** 2-3 weeks after Phase 3

**Tasks:**
1. 🔵 **Ensemble Model Properties** (3 hours)
2. 🔵 **Backtesting Validation** (4 hours)
3. 🔵 **A/B Testing Validation** (2 hours)

**Dependencies:**
- Ensemble model implementation (Phase 4)
- Backtesting framework (Phase 4+)

---

### Phase 5: Position & Exit Management (10-12 hours)

**Target Completion:** 2-3 weeks after Phase 4

**Tasks:**
1. 🔵 **Position Management** (5 hours)
2. 🔵 **Exit Management** (4 hours)
3. 🔵 **Reporting & Metrics** (2 hours)

**Dependencies:**
- Position monitoring (Phase 5a)
- Exit execution (Phase 5b)
- Reporting infrastructure (Phase 5+)

**Acceptance Criteria:**
- ✅ All position management invariants validated
- ✅ Trailing stop logic 100% correct (property tests prove it)
- ✅ Exit optimization verified mathematically
- ✅ No edge case bugs in production

---

## 5. Custom Hypothesis Strategies

### Reusable Strategy Library

Create `tests/property/strategies.py` with domain-specific generators:

```python
"""
Custom Hypothesis Strategies for Precog Trading Platform
=========================================================
Reusable generators for trading-domain types.

Usage:
    from tests.property.strategies import probability, market_price, edge_value

    @given(prob=probability(), price=market_price())
    def test_edge_calculation(prob, price):
        ...
"""

from decimal import Decimal
from hypothesis import strategies as st

# ==============================================================================
# Price & Probability Strategies
# ==============================================================================

@st.composite
def probability(draw, min_value=0, max_value=1, places=4):
    """Generate valid probabilities in [0, 1]."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def market_price(draw, min_value=0, max_value=1, places=4):
    """Generate valid market prices in [0, 1]."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def edge_value(draw, min_value=-0.5, max_value=0.5, places=4):
    """Generate edge values (positive or negative)."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def spread(draw, min_value=0, max_value=0.5, places=4):
    """Generate bid-ask spreads."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


# ==============================================================================
# Financial Strategies
# ==============================================================================

@st.composite
def fee_percent(draw, min_value=0, max_value=0.15, places=4):
    """Generate fee percentages (0-15%)."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def kelly_fraction(draw, min_value=0, max_value=1, places=2):
    """Generate Kelly fractions (0-1)."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def bankroll_amount(draw, min_value=100, max_value=100000, places=2):
    """Generate bankroll amounts ($100-$100,000)."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def position_size(draw, min_value=1, max_value=10000, places=2):
    """Generate position sizes (1-10,000 contracts)."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


# ==============================================================================
# Sports Data Strategies
# ==============================================================================

@st.composite
def elo_rating(draw, min_value=800, max_value=2200):
    """Generate Elo ratings (800-2200)."""
    return draw(st.integers(min_value=min_value, max_value=max_value))


@st.composite
def game_score(draw, min_value=0, max_value=100):
    """Generate game scores (0-100)."""
    return draw(st.integers(min_value=min_value, max_value=max_value))


@st.composite
def possession_percent(draw, min_value=0, max_value=100, places=1):
    """Generate possession percentages (0-100%)."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def time_remaining(draw, min_value=0, max_value=3600):
    """Generate time remaining in seconds (0-3600 for NFL)."""
    return draw(st.integers(min_value=min_value, max_value=max_value))


# ==============================================================================
# Order Book Strategies
# ==============================================================================

@st.composite
def order_book_level(draw):
    """
    Generate order book level (price, quantity).

    Returns:
        Tuple[Decimal, int]: (price, quantity)
    """
    price = draw(st.decimals(min_value=0.01, max_value=0.99, places=4))
    quantity = draw(st.integers(min_value=1, max_value=10000))
    return (price, quantity)


@st.composite
def order_book(draw, min_levels=3, max_levels=10):
    """
    Generate full order book (bids and asks).

    Returns:
        Dict with 'bids' and 'asks' lists
    """
    num_bids = draw(st.integers(min_value=min_levels, max_value=max_levels))
    num_asks = draw(st.integers(min_value=min_levels, max_value=max_levels))

    bids = [draw(order_book_level()) for _ in range(num_bids)]
    asks = [draw(order_book_level()) for _ in range(num_asks)]

    # Sort bids descending, asks ascending
    bids = sorted(bids, key=lambda x: -x[0])
    asks = sorted(asks, key=lambda x: x[0])

    # Ensure no crossed market
    if bids and asks and bids[0][0] >= asks[0][0]:
        # Adjust to ensure bid < ask
        mid_price = (bids[0][0] + asks[0][0]) / Decimal("2")
        bids = [(max(Decimal("0.01"), mid_price - Decimal("0.01")), q) for p, q in bids]
        asks = [(min(Decimal("0.99"), mid_price + Decimal("0.01")), q) for p, q in asks]

    return {"bids": bids, "asks": asks}


# ==============================================================================
# Time Series Strategies
# ==============================================================================

@st.composite
def game_timeline(draw, min_events=5, max_events=20):
    """
    Generate chronological game timeline (time_remaining, score).

    Returns:
        List[Tuple[int, int]]: [(time_remaining, score), ...]
    """
    num_events = draw(st.integers(min_value=min_events, max_value=max_events))

    events = []
    current_score = 0
    for i in range(num_events):
        time_remaining = draw(st.integers(min_value=0, max_value=3600 - i * 60))
        score_increase = draw(st.integers(min_value=0, max_value=7))  # Typical score increment
        current_score += score_increase
        events.append((time_remaining, current_score))

    # Sort by time_remaining descending (game progresses forward)
    events = sorted(events, key=lambda x: -x[0])

    return events
```

**Usage Example:**

```python
from tests.property.strategies import probability, market_price, fee_percent

@given(
    prob=probability(),
    price=market_price(),
    fee=fee_percent(),
)
def test_edge_calculation(prob, price, fee):
    edge = calculate_edge(prob, price, fee)
    assert edge == prob - (price * (Decimal("1") + fee))
```

---

## 6. Testing Infrastructure Updates

### 6.1 Update `pyproject.toml` Configuration

Add optimized Hypothesis settings:

```toml
# ==============================================================================
# HYPOTHESIS CONFIGURATION (Property-Based Testing)
# Phase 1.5+: Comprehensive property-based testing
# ==============================================================================

[tool.hypothesis]
# Maximum number of examples to try per test
# Default: 100
# Increase for critical properties (edge detection, Kelly criterion)
max_examples = 1000  # 10x more thorough testing for trading system

# Verbosity (quiet, normal, verbose, debug)
verbosity = "normal"

# Database directory for test results (Hypothesis caches examples)
database = ".hypothesis/examples"

# Derandomize tests (use fixed seed for reproducibility)
# Set to true for debugging specific failures
derandomize = false

# Deadline for each test example (ms)
# Prevents infinite loops, allows time for complex calculations
deadline = 400  # 400ms per example (default)

# Suppress health check warnings
# (Can enable specific warnings if needed)
suppress_health_check = []

# Seed for random number generation (for reproducibility)
# Leave unset for random seed each run (default)
# seed = 12345

# Profile for CI/CD (faster, less thorough)
# Switch profiles with: pytest --hypothesis-profile=ci
[tool.hypothesis.profiles.ci]
max_examples = 100  # Faster for CI
deadline = 200      # Stricter deadline

# Profile for local development (thorough)
[tool.hypothesis.profiles.dev]
max_examples = 1000  # More thorough locally
deadline = 400       # More lenient deadline

# Profile for stress testing (exhaustive)
[tool.hypothesis.profiles.stress]
max_examples = 10000  # Exhaustive testing
deadline = 1000       # Very lenient deadline
```

**Usage:**
```bash
# Default (dev profile)
pytest tests/property/ -v

# CI profile (faster)
pytest tests/property/ -v --hypothesis-profile=ci

# Stress test (exhaustive)
pytest tests/property/ -v --hypothesis-profile=stress
```

---

### 6.2 CI/CD Integration

**Update `.github/workflows/ci.yml`:**

```yaml
  property-tests:
    name: Property-Based Tests (Hypothesis)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'
          allow-prereleases: true

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install hypothesis

      - name: Run property-based tests
        run: |
          # Use CI profile (100 examples per property, faster)
          pytest tests/property/ -v \
            --hypothesis-profile=ci \
            --hypothesis-show-statistics \
            --tb=short \
            --no-cov

      - name: Archive Hypothesis database (failures)
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: hypothesis-failures
          path: .hypothesis/examples
```

**Why No Coverage:**
Property tests test **mathematical invariants**, not line coverage. They complement (not replace) unit tests.

---

### 6.3 Pre-Push Hook Integration

**Update `.git/hooks/pre-push`:**

```bash
# 5. Run property-based tests (fast subset)
echo "🔬 [4/5] Running property-based tests..."
if python -m pytest tests/property/ \
    --hypothesis-profile=ci \
    -x \
    --tb=short \
    --no-cov \
    -q; then
    echo "✅ Property tests passed"
else
    echo "❌ Property tests failed"
    echo ""
    echo "Fix property test failures, then try pushing again."
    echo "To bypass (NOT RECOMMENDED): git push --no-verify"
    exit 1
fi
```

**Why Pre-Push:**
Property tests catch invariant violations **before CI**. If a property fails locally, fix it before pushing.

---

## 7. Documentation Integration

### 7.1 Update Foundation Documents

#### MASTER_REQUIREMENTS (Add Property Testing Requirements)

**New Requirements:**

```markdown
### Testing Requirements (Continued)

**REQ-TEST-008: Property-Based Testing Framework**
- **Phase:** 1.5
- **Priority:** 🔴 Critical
- **Status:** 🟡 In Progress
- **Description:** Implement comprehensive property-based testing using Hypothesis framework for all critical trading logic
- **Rationale:** Property-based tests validate mathematical invariants across thousands of auto-generated test cases, catching edge cases that example-based tests miss
- **Acceptance Criteria:**
  - Hypothesis framework integrated in Phase 1.5
  - ≥35 properties tested in Phase 1.5 (Kelly criterion, edge detection, config validation)
  - ≥3500 auto-generated test cases per PR
  - Property tests run in CI/CD pipeline
  - Property tests documented in Pattern 9 (CLAUDE.md)
- **Reference:** `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md`
- **Related ADRs:** ADR-074

**REQ-TEST-009: Property Coverage for Core Trading Logic**
- **Phase:** 1.5
- **Priority:** 🔴 Critical
- **Status:** 🟡 In Progress
- **Description:** All critical trading calculations (Kelly criterion, edge detection, position sizing) must have property-based tests validating mathematical correctness
- **Rationale:** Bugs in core trading logic cause catastrophic losses (negative edge trades, oversized positions)
- **Acceptance Criteria:**
  - Kelly criterion: 11 properties tested (position bounds, zero/negative edge handling, linearity)
  - Edge detection: 15 properties tested (formula correctness, fee impact, spread impact, monotonicity)
  - Configuration validation: 8-10 properties tested (range validation, Decimal safety)
- **Reference:** `tests/property/test_kelly_criterion_properties.py`, `tests/property/test_edge_detection_properties.py`
- **Related ADRs:** ADR-074

**REQ-TEST-010: Property Coverage for Model Validation**
- **Phase:** 2
- **Priority:** 🟡 High
- **Status:** 🔵 Planned
- **Description:** All model outputs (probabilities, confidence scores, ensemble weights) must have property-based tests validating mathematical correctness
- **Rationale:** Model bugs propagate to edge detection and position sizing
- **Acceptance Criteria:**
  - Model output probabilities in [0, 1]
  - Ensemble weights sum to 1
  - Model performance metrics monotonic
  - Feature extraction produces finite values (no NaN, no Inf)
- **Reference:** `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` Section 3.5
- **Related ADRs:** ADR-074

**REQ-TEST-011: Property Coverage for Position Management**
- **Phase:** 5
- **Priority:** 🔴 Critical
- **Status:** 🔵 Planned
- **Description:** All position management logic (trailing stops, profit targets, correlation limits) must have property-based tests
- **Rationale:** Position management bugs cause risk management failures and catastrophic losses
- **Acceptance Criteria:**
  - Trailing stop only tightens (never loosens)
  - Total position value ≤ bankroll
  - Correlation limits respected
  - Stop loss/profit target triggers correct
- **Reference:** `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` Section 3.12
- **Related ADRs:** ADR-074
```

---

#### ARCHITECTURE_DECISIONS (Add Hypothesis ADR)

**New ADR:**

```markdown
### ADR-074: Property-Based Testing with Hypothesis

**Decision #74**
**Phase:** 1.5+
**Status:** 🟡 In Progress
**Date:** 2025-11-08

**Decision:** Adopt Hypothesis property-based testing framework for all critical trading logic, supplementing (not replacing) traditional example-based unit tests.

**Context:**

Trading systems have **mathematical invariants** that must hold for ALL inputs:
- Kelly criterion: position ≤ bankroll (for ALL edges, fractions, bankrolls)
- Edge detection: negative edge → don't trade (for ALL probabilities, prices, fees)
- Trailing stops: stop only tightens, never loosens (for ALL price sequences)

Traditional example-based tests check specific scenarios:
```python
def test_kelly_sizing():
    edge = Decimal("0.10")
    kelly_fraction = Decimal("0.25")
    bankroll = Decimal("10000")
    position = calculate_kelly_size(edge, kelly_fraction, bankroll)
    assert position == Decimal("250")
```

**Problem:** What if edge = 0.9999999? What if bankroll = $999,999,999.99? Can't test every scenario manually.

**Property-based testing** validates invariants across thousands of generated examples:
```python
@given(
    edge=st.decimals(min_value=0, max_value=0.5, places=4),
    kelly_frac=st.decimals(min_value=0, max_value=1, places=2),
    bankroll=st.decimals(min_value=100, max_value=100000, places=2),
)
def test_position_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll  # Must hold for ALL inputs
```

Hypothesis generates extreme edge cases (probability = 0.00000001, spread = 0.4999) that humans wouldn't think to test.

**Alternatives Considered:**

1. **Fuzz Testing (AFL, libFuzzer):**
   - **Pros:** Finds crashes and memory corruption
   - **Cons:** Not designed for mathematical properties, requires C/C++ integration
   - **Verdict:** Rejected - Overkill for Python trading system

2. **QuickCheck (Haskell):**
   - **Pros:** Original property-based testing framework
   - **Cons:** Requires Haskell, can't test Python code directly
   - **Verdict:** Rejected - Language barrier

3. **Hypothesis (Python):**
   - **Pros:** Native Python, excellent Decimal support, shrinking (finds minimal failing example), integrates with pytest
   - **Cons:** Slightly slower than example-based tests (~1ms per example vs ~0.1ms)
   - **Verdict:** ✅ **SELECTED** - Best fit for Python trading system

4. **Manual Boundary Testing:**
   - **Pros:** Simple, no new framework
   - **Cons:** Humans forget edge cases, doesn't scale to complex scenarios
   - **Verdict:** Rejected - Insufficient coverage

**Decision:**

Adopt Hypothesis for **all critical trading logic**:
- ✅ Core calculations (Kelly criterion, edge detection, position sizing)
- ✅ Model validation (probability bounds, ensemble weights)
- ✅ Data validation (historical data integrity, order book sanity checks)
- ✅ Position management (trailing stops, correlation limits)
- ✅ Backtest validation (equity curve, drawdown, Sharpe ratio)

**Example-based tests still used for:**
- Integration tests (API clients, database CRUD)
- Specific regression tests (known bugs)
- Complex setup scenarios (mock data fixtures)

**Implementation Plan:**
- Phase 1.5: Kelly criterion, edge detection, config validation (35 properties, 3500+ test cases)
- Phase 2: Model validation, historical data, strategy versioning (35 properties, 3500+ test cases)
- Phase 3: Order book, entry optimization (22 properties, 2200+ test cases)
- Phase 4: Ensemble, backtesting, A/B testing (28 properties, 2800+ test cases)
- Phase 5: Position management, exit optimization (45 properties, 4500+ test cases)

**Total:** ~165 properties, 16,500+ auto-generated test cases (38-48 hours implementation)

**Consequences:**

**Positive:**
- ✅ **Catches edge cases humans miss** (probability = 0.9999999, spread = 0.0001)
- ✅ **Self-documenting** ("position never exceeds bankroll" is clearer than example test)
- ✅ **Regression prevention** (if future change violates invariant, Hypothesis immediately finds counterexample)
- ✅ **Fast feedback** (~1ms per example, 100 examples per property = ~100ms total)
- ✅ **Shrinking** (Hypothesis finds **minimal** failing example, not first failure)
- ✅ **Saves QA time** (automated testing of billions of scenarios)

**Negative:**
- ❌ **Slightly slower than example tests** (1ms vs 0.1ms per test case)
- ❌ **Learning curve** (team must learn property-based thinking)
- ❌ **False positives possible** (may find "failures" in unrealistic scenarios - use `assume()` to filter)
- ❌ **Non-deterministic failures** (same test may pass/fail on different runs - use `derandomize=True` for debugging)

**Mitigation:**
- Use `hypothesis-profile=ci` for faster CI builds (100 examples vs 1000 locally)
- Document property-based patterns in Pattern 9 (CLAUDE.md)
- Use `assume()` to filter unrealistic scenarios
- Use `derandomize=True` when debugging failures

**Success Metrics:**
- ✅ Coverage increase ≥ 15% (property tests discover untested code paths)
- ✅ Critical bug prevention (no negative edge trades, no oversized positions in production)
- ✅ CI build time increase ≤ 2 minutes (property tests run fast with CI profile)
- ✅ Developer adoption ≥ 80% (team writes properties for new critical code)

**References:**
- `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md`
- `tests/property/test_kelly_criterion_properties.py` (proof-of-concept)
- `tests/property/test_edge_detection_properties.py` (proof-of-concept)
- Pattern 9: Property-Based Testing (CLAUDE.md)
- REQ-TEST-008, REQ-TEST-009, REQ-TEST-010, REQ-TEST-011

**Related ADRs:**
- ADR-002: Decimal-Only Financial Calculations (property tests validate Decimal precision)
- ADR-048: Decimal-First Response Parsing (property tests validate parsing correctness)
```

---

#### DEVELOPMENT_PHASES (Integrate Property Testing)

**Update Phase 1.5 Section:**

```markdown
### Phase 1.5: Testing Infrastructure Enhancement (Weeks 5-6)

**Duration:** 1-2 weeks
**Status:** 🔵 Planned
**Priority:** 🔴 Critical (before Phase 2 live trading)

**Deliverables:**
1. ✅ Property-based testing framework (Hypothesis)
   - Kelly criterion properties (11 tests, 1100+ examples)
   - Edge detection properties (15 tests, 1500+ examples)
   - Configuration validation properties (8-10 tests, 800-1000+ examples)
2. Integration testing suite expansion
   - Kalshi API integration tests (live demo environment)
   - ESPN API integration tests
   - Database integration tests (CRUD operations, SCD Type 2)
3. Test coverage improvements (goal: 90%+ for Phase 1 modules)
4. CI/CD enhancements (property tests in pipeline)

**Dependencies:**
- Phase 1 complete (API clients, database, config loader)

**Property Testing Coverage:**
- Kelly Criterion: Position sizing invariants
  - Position ≤ bankroll
  - Zero/negative edge handling
  - Linearity properties
- Edge Detection: Trading logic invariants
  - Formula correctness
  - Fee impact validation
  - Spread impact validation
  - Monotonicity properties
- Configuration: YAML validation invariants
  - Range validation (kelly_fraction ∈ [0, 1])
  - Decimal safety (no float contamination)
  - Required fields present

**Acceptance Criteria:**
- ✅ All Phase 1.5 property tests passing (35 properties, 3500+ examples)
- ✅ Coverage ≥ 90% for Phase 1 modules (API clients, database, config)
- ✅ CI integration complete (property tests run on every PR)
- ✅ Documentation updated (Pattern 9 in CLAUDE.md, REQ-TEST-008/009 in MASTER_REQUIREMENTS)

**Time Estimate:** 6-8 hours (property testing) + 4-6 hours (integration testing) = 10-14 hours total
```

---

### 7.2 Update CLAUDE.md (Add Pattern 9)

**Add New Pattern to CLAUDE.md:**

```markdown
### Pattern 9: Property-Based Testing (ALWAYS)

**WHY:** Traditional example-based tests miss edge cases. Property-based testing validates mathematical invariants across thousands of auto-generated test cases.

**WHEN TO USE:**
- Mathematical calculations (Kelly criterion, edge detection, Sharpe ratio)
- Business rules that must ALWAYS hold (position ≤ bankroll, trailing stop only tightens)
- Data validation (probabilities ∈ [0, 1], order book bids < asks)
- Model validation (ensemble weights sum to 1, no NaN/Inf in features)

**ALWAYS:**
```python
from hypothesis import given, strategies as st
from tests.property.strategies import probability, market_price, fee_percent

@given(
    true_prob=probability(),
    price=market_price(),
    fee=fee_percent(),
)
def test_negative_edge_never_recommends_trade(true_prob, price, fee):
    """
    PROPERTY: If edge < 0, we should NEVER trade.

    This is CRITICAL. Negative edge means expected loss.

    Hypothesis will test 1000+ combinations of (true_prob, price, fee)
    to ensure this invariant ALWAYS holds.
    """
    edge = calculate_edge(true_prob, price, fee)

    if edge < Decimal("0"):
        recommendation = should_trade(edge)
        assert not recommendation, f"Recommended trade with negative edge {edge}!"
```

**NEVER:**
```python
# ❌ Testing only specific examples
def test_negative_edge():
    edge = Decimal("-0.05")
    assert not should_trade(edge)
    # What if edge = -0.0000001? What if edge = -0.4999?
```

**Key Patterns:**

1. **Use Custom Strategies (from `tests/property/strategies.py`):**
```python
from tests.property.strategies import (
    probability, market_price, edge_value, fee_percent,
    kelly_fraction, bankroll_amount, elo_rating, order_book
)

@given(prob=probability(), price=market_price(), fee=fee_percent())
def test_edge_calculation(prob, price, fee):
    # All generated values are valid Decimals in correct ranges
    edge = calculate_edge(prob, price, fee)
    assert isinstance(edge, Decimal)
```

2. **Test Mathematical Invariants (not specific values):**
```python
# ✅ CORRECT - Test invariant
@given(bankroll=bankroll_amount(), kelly_frac=kelly_fraction(), edge=edge_value())
def test_position_never_exceeds_bankroll(bankroll, kelly_frac, edge):
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll  # Must hold for ALL inputs

# ❌ WRONG - Test specific value
def test_kelly_sizing():
    position = calculate_kelly_size(Decimal("0.10"), Decimal("0.25"), Decimal("10000"))
    assert position == Decimal("250")  # Only tests ONE scenario
```

3. **Use `assume()` to Filter Unrealistic Scenarios:**
```python
from hypothesis import assume

@given(bid=market_price(), ask=market_price())
def test_spread_positive(bid, ask):
    assume(bid < ask)  # Skip examples where bid >= ask (unrealistic)

    spread = calculate_spread(bid, ask)
    assert spread > Decimal("0")
```

4. **Document WHY Property Matters:**
```python
@given(edge=edge_value())
def test_zero_edge_means_zero_position(edge):
    """
    PROPERTY: Zero edge → zero position size.

    Educational Note:
        If there's no edge (fair bet), Kelly criterion says don't bet.
        This ensures we're not taking positions when expected value is zero.

        Why it matters:
        - Zero edge bets are break-even in expectation
        - Transaction fees make them losers in practice
        - Capital tied up in zero-EV positions has opportunity cost

    Related:
        - REQ-TRADE-001: Kelly Criterion Position Sizing
        - ADR-074: Property-Based Testing with Hypothesis
    """
    if edge == Decimal("0"):
        position = calculate_position_size(edge)
        assert position == Decimal("0"), "Non-zero position with zero edge!"
```

5. **Run Property Tests in CI:**
```bash
# pyproject.toml
[tool.hypothesis]
max_examples = 1000  # Locally: 1000 examples per property (thorough)

[tool.hypothesis.profiles.ci]
max_examples = 100   # CI: 100 examples per property (faster)

# .github/workflows/ci.yml
- name: Run property-based tests
  run: pytest tests/property/ --hypothesis-profile=ci
```

**When to Use Example-Based Tests vs Property-Based Tests:**

| Scenario | Use Example-Based | Use Property-Based |
|----------|-------------------|-------------------|
| Mathematical invariant (position ≤ bankroll) | ❌ | ✅ |
| Business rule that ALWAYS holds | ❌ | ✅ |
| Specific regression (known bug) | ✅ | ❌ |
| Complex setup (mock API responses) | ✅ | ❌ |
| Integration test (database CRUD) | ✅ | ❌ |
| Data validation (prices ∈ [0, 1]) | ❌ | ✅ |
| Edge case exploration (what if edge = 0.9999?) | ❌ | ✅ |

**Reference:**
- `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` - Comprehensive implementation plan
- `tests/property/test_kelly_criterion_properties.py` - Proof-of-concept (11 properties)
- `tests/property/test_edge_detection_properties.py` - Proof-of-concept (15 properties)
- ADR-074: Property-Based Testing with Hypothesis
- REQ-TEST-008, REQ-TEST-009, REQ-TEST-010, REQ-TEST-011

---

## 8. Success Metrics

### Quantitative Metrics

| Metric | Baseline | Target (Phase 1.5) | Target (All Phases) | Measurement |
|--------|----------|-------------------|---------------------|-------------|
| **Property Tests** | 1 (Decimal properties) | 35 | 165 | Count of @given tests |
| **Auto-Generated Test Cases** | 100 | 3,500 | 16,500 | 100 examples × properties |
| **Coverage Increase** | — | +3-5% | +15-20% | pytest --cov (property tests discover new paths) |
| **Critical Bug Prevention** | — | ≥1 | ≥5 | Bugs found by property tests |
| **CI Build Time** | ~2 min | +30 sec | +2 min | Property tests with CI profile |
| **Developer Adoption** | 0% | 50% | 80% | % of critical code with properties |

### Qualitative Metrics

| Metric | Success Criteria | Measurement |
|--------|------------------|-------------|
| **Invariant Coverage** | All critical invariants tested | Manual audit of properties |
| **Documentation Quality** | All properties have educational docstrings | Code review |
| **False Positive Rate** | <5% of property tests fail on unrealistic scenarios | Track `assume()` usage |
| **Bug Severity Reduction** | Zero critical bugs in production (edge detection, Kelly criterion) | Production monitoring |
| **Team Confidence** | ≥80% of team confident in trading logic correctness | Quarterly survey |

### Critical Invariants Validated

**Phase 1.5 (Core Trading Logic):**
- ✅ Position size ≤ bankroll (Kelly criterion)
- ✅ Negative edge → don't trade (edge detection)
- ✅ Fees always reduce edge (edge detection)
- ✅ Configuration values in valid ranges

**Phase 2 (Data & Models):**
- Model output probabilities ∈ [0, 1]
- Ensemble weights sum to 1
- Historical data monotonicity (scores increase, time decreases)
- Strategy version immutability

**Phase 5 (Position Management):**
- Trailing stop only tightens (never loosens)
- Total position value ≤ bankroll
- Correlation limits respected
- Stop loss/profit target triggers correct

---

## 9. Future Enhancements

### Phase 6+: Advanced Property Testing

1. **Stateful Testing (Game State Transitions):**
   ```python
   from hypothesis.stateful import RuleBasedStateMachine, rule

   class GameStateTransitions(RuleBasedStateMachine):
       """Test valid game state transitions."""

       @rule()
       def start_game(self):
           self.game = create_game()
           assert self.game.status == "scheduled"

       @rule()
       def kickoff(self):
           assume(self.game.status == "scheduled")
           self.game.kickoff()
           assert self.game.status == "in_progress"

       @rule()
       def score_touchdown(self):
           assume(self.game.status == "in_progress")
           old_score = self.game.score
           self.game.score_touchdown()
           assert self.game.score == old_score + 6
   ```

2. **Ghostwriter (Auto-Generate Properties):**
   ```bash
   # Hypothesis can auto-generate property tests!
   hypothesis write tests.property.test_kelly --style=pytest
   ```

3. **Coverage-Guided Fuzzing:**
   ```python
   # Combine Hypothesis with coverage.py to find uncovered paths
   pytest tests/property/ --hypothesis-seed=auto --cov-report=html
   ```

4. **Performance Property Testing:**
   ```python
   @given(data=st.data())
   def test_edge_calculation_performance(data):
       """PROPERTY: Edge calculation should complete in <1ms."""
       prob = data.draw(probability())
       price = data.draw(market_price())

       start_time = time.perf_counter()
       edge = calculate_edge(prob, price)
       end_time = time.perf_counter()

       assert end_time - start_time < 0.001, "Edge calculation too slow!"
   ```

---

## Conclusion

This implementation plan provides a **comprehensive roadmap** for integrating Hypothesis property-based testing across the entire Precog trading platform.

**Key Takeaways:**
1. ✅ **Proof-of-Concept Complete** (26 properties, 2600+ test cases, 3.32 seconds)
2. 🔵 **Phase 1.5 Next** (config validation, 35 total properties, 6-8 hours)
3. 🎯 **Long-Term Goal** (165 properties, 16,500+ test cases, 38-48 hours total)
4. 🔴 **Critical** for trading system correctness (edge detection, Kelly criterion, position management)

**Remember:**
> "The quality of the models, edge detection and methods are core to the success of the project."

Property-based testing ensures mathematical correctness for **ALL inputs**, not just the examples we think to test.

---

**Document History:**

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-11-08 | Initial creation (comprehensive implementation plan) | Claude Code |

**END OF DOCUMENT**
