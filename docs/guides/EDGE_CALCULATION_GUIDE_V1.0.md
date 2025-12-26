# Edge Calculation Guide

---

**Version:** 1.0
**Created:** 2025-11-24
**Status:** 🔵 Planned (Phase 3+)
**Target Audience:** Developers implementing real-time edge calculation and trading opportunity identification
**Prerequisites:** MODEL_MANAGER_USER_GUIDE_V1.1.md, MODEL_TRAINING_GUIDE_V1.0.md
**Related Documents:**
- `docs/guides/MODEL_MANAGER_USER_GUIDE_V1.1.md` (Future Enhancements - Edge Calculation Integration)
- `docs/guides/STRATEGY_MANAGER_USER_GUIDE_V1.1.md` (min_edge threshold configuration)
- `docs/guides/ELO_COMPUTATION_GUIDE_V1.0.md` 🔵 **PLANNED** - Elo model predictions used in edge calculation
- `docs/supplementary/DATA_SOURCES_SPECIFICATION_V1.0.md` - Data sources for model training
- `docs/foundation/MASTER_REQUIREMENTS_V2.18.md` (REQ-MODEL-001 through REQ-MODEL-006)
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.32.md` (ADR-002: Decimal Precision)

---

## Table of Contents

1. [Overview](#overview)
2. [Edge Calculation Fundamentals](#edge-calculation-fundamentals)
3. [EdgeCalculator Implementation](#edgecalculator-implementation)
4. [Multi-Model Ensemble Predictions](#multi-model-ensemble-predictions)
5. [Confidence Intervals & Uncertainty](#confidence-intervals--uncertainty)
6. [Edge Thresholding & Filtering](#edge-thresholding--filtering)
7. [Historical Edge Tracking](#historical-edge-tracking)
8. [Integration with Trading System](#integration-with-trading-system)
9. [Performance Optimization](#performance-optimization)
10. [Testing & Validation](#testing--validation)

---

## 1. Overview

### What is Edge?

**Edge** is the difference between the **true win probability** (predicted by our models) and the **market price** (implied probability from Kalshi).

```python
edge = model_predicted_prob - market_price
```

**Positive edge (+)** = Trading opportunity (our model predicts higher win probability than market)
**Negative edge (-)** = Unfavorable trade (market price higher than our prediction)
**Zero edge (0)** = Fair price (model agrees with market)

### Why Edge Matters

- **EV+ Trading:** Only trade when edge > min_edge threshold (typically 5%)
- **Risk Management:** Larger edge = larger position size (Kelly Criterion)
- **Model Validation:** Edge trends indicate model calibration quality
- **A/B Testing:** Compare strategies by realized edge vs predicted edge

### Implementation Scope

**Phase 3+** - This guide documents the `EdgeCalculator` class for automated edge calculation.

**Key Features:**
- Real-time edge calculation for live markets
- Multi-model ensemble predictions (weighted average)
- Confidence intervals (95% CI for prediction uncertainty)
- Edge thresholding (filter opportunities where edge > min_edge)
- Historical edge tracking (log calculations for backtesting)

---

## 2. Edge Calculation Fundamentals

### Single Model Edge

**Formula:**
```python
edge = model_predicted_prob - market_price
```

**Example:**
```python
from decimal import Decimal

# Market: Bills vs Dolphins (Bills to win)
market_price = Decimal("0.52")  # Kalshi YES price (52%)
model_pred = Decimal("0.61")    # Elo model predicts 61% Bills win

# Calculate edge
edge = model_pred - market_price  # 0.61 - 0.52 = 0.09 (9% edge)

# Decision: 9% > 5% threshold → TRADE
```

### Multi-Model Ensemble Edge

**Formula:**
```python
ensemble_pred = sum(model_i_pred * weight_i for all models)
edge = ensemble_pred - market_price
```

**Example:**
```python
from decimal import Decimal

# Two Elo models with different k-factors
model_1_pred = Decimal("0.61")  # k=32 (aggressive)
model_2_pred = Decimal("0.58")  # k=24 (conservative)

# Ensemble weights (based on backtested performance)
weight_1 = Decimal("0.6")  # 60% weight to aggressive model
weight_2 = Decimal("0.4")  # 40% weight to conservative model

# Calculate ensemble prediction
ensemble_pred = (model_1_pred * weight_1) + (model_2_pred * weight_2)
# = (0.61 * 0.6) + (0.58 * 0.4)
# = 0.366 + 0.232
# = 0.598 (59.8% win probability)

# Calculate edge
market_price = Decimal("0.52")
edge = ensemble_pred - market_price  # 0.598 - 0.52 = 0.078 (7.8% edge)

# Decision: 7.8% > 5% threshold → TRADE
```

### Confidence Intervals

**Formula (95% CI):**
```python
ci_lower = ensemble_pred - 1.96 * std_error
ci_upper = ensemble_pred + 1.96 * std_error
```

**Interpretation:**
- **Narrow CI:** Models agree → High confidence prediction
- **Wide CI:** Models disagree → Low confidence prediction
- **CI includes market price:** Edge may not be statistically significant

**Example:**
```python
from decimal import Decimal
import statistics

# Model predictions
predictions = [Decimal("0.61"), Decimal("0.58"), Decimal("0.62")]

# Calculate ensemble prediction
ensemble_pred = statistics.mean(predictions)  # 0.603

# Calculate standard error
std_dev = statistics.stdev(predictions)  # 0.020
std_error = std_dev / (len(predictions) ** 0.5)  # 0.020 / √3 = 0.012

# Calculate 95% confidence interval
ci_lower = ensemble_pred - (Decimal("1.96") * std_error)  # 0.603 - 0.024 = 0.579
ci_upper = ensemble_pred + (Decimal("1.96") * std_error)  # 0.603 + 0.024 = 0.627

# Verify market price NOT in confidence interval
market_price = Decimal("0.52")
if ci_lower > market_price:
    print("✅ Edge is statistically significant (market price below CI)")
    # Output: ✅ Edge is statistically significant
else:
    print("⚠️ Edge may not be significant (market price within CI)")
```

---

## 3. EdgeCalculator Implementation

### Class Overview

**File:** `src/precog/analytics/edge_calculator.py` (~300 lines)

**Purpose:** Calculate real-time edge for trading opportunities using model predictions and market prices.

**Key Responsibilities:**
1. Fetch market prices from Kalshi API
2. Generate predictions from active models
3. Combine multi-model predictions (ensemble)
4. Calculate edge and confidence intervals
5. Filter opportunities by min_edge threshold
6. Log edge calculations for historical tracking

### Constructor

```python
"""
Edge Calculator for Trading Opportunities

Calculates edge (true_prob - market_price) using model predictions.
Supports single-model and multi-model ensemble predictions.

Educational Note:
    Edge calculation is the CORE of EV+ trading. Every trade decision
    starts with this calculation. If edge ≤ min_edge, we don't trade.

Related Requirements:
    - REQ-MODEL-001: Model prediction interface
    - REQ-MODEL-005: Ensemble prediction support
    - REQ-TRADING-001: Edge-based trade filtering

Reference:
    - docs/guides/STRATEGY_MANAGER_USER_GUIDE_V1.1.md (min_edge config)
    - docs/guides/MODEL_TRAINING_GUIDE_V1.0.md (model predictions)
"""
from decimal import Decimal
from typing import Any
import statistics
from datetime import datetime

from precog.api_connectors.kalshi_client import KalshiClient
from precog.managers.model_manager import ModelManager
from precog.database.crud_operations import CRUDOperations
from precog.utils.logger import get_logger


class EdgeCalculator:
    """
    Real-time edge calculation for trading opportunities.

    Calculates edge = model_predicted_prob - market_price
    Supports multi-model ensemble predictions with confidence intervals.
    """

    def __init__(
        self,
        kalshi_client: KalshiClient,
        model_manager: ModelManager,
        crud: CRUDOperations,
        min_edge_threshold: Decimal = Decimal("0.05")
    ):
        """
        Initialize EdgeCalculator.

        Args:
            kalshi_client: Kalshi API client for market prices
            model_manager: ModelManager for model predictions
            crud: Database CRUD operations for edge logging
            min_edge_threshold: Minimum edge to consider (default 5%)

        Educational Note:
            min_edge_threshold typically 5% (REQ-TRADING-002).
            Lower threshold → more trades, lower win rate.
            Higher threshold → fewer trades, higher win rate.
        """
        self.kalshi_client = kalshi_client
        self.model_manager = model_manager
        self.crud = crud
        self.min_edge_threshold = min_edge_threshold
        self.logger = get_logger(__name__)
```

---

## 4. Multi-Model Ensemble Predictions

### calculate_edge() Method

```python
def calculate_edge(
    self,
    market_id: str,
    model_ids: list[int],
    weights: list[Decimal] | None = None
) -> dict[str, Any]:
    """
    Calculate edge for a market using single or multiple models.

    Args:
        market_id: Kalshi market ticker (e.g., "KXNFL-2024-11-24-BUF-MIA")
        model_ids: List of model IDs to use for predictions
        weights: Optional weights for ensemble (must sum to 1.0)
                If None, equal weights (1/N for each model)

    Returns:
        Edge calculation result:
        {
            'market_id': str,
            'market_price': Decimal,
            'model_pred': Decimal (ensemble prediction),
            'edge': Decimal,
            'ci_lower': Decimal,
            'ci_upper': Decimal,
            'meets_threshold': bool,
            'timestamp': datetime,
            'models_used': list[int]
        }

    Raises:
        ValueError: If weights don't sum to 1.0 or wrong length
        APIError: If Kalshi API call fails
        ModelNotFoundError: If model_id doesn't exist

    Educational Note:
        Ensemble Prediction Process:
        1. Fetch market price from Kalshi (YES price = implied probability)
        2. Generate predictions from each model
        3. Combine predictions using weighted average
        4. Calculate confidence interval (95% CI)
        5. Calculate edge = ensemble_pred - market_price
        6. Check if edge > min_edge_threshold
        7. Log calculation to database

        Multi-model ensembles reduce variance and improve calibration.
        If models disagree (wide CI), we trade smaller positions.

    Example:
        >>> edge_calc = EdgeCalculator()
        >>> result = edge_calc.calculate_edge(
        ...     market_id="KXNFL-2024-11-24-BUF-MIA",
        ...     model_ids=[42, 43],
        ...     weights=[Decimal("0.6"), Decimal("0.4")]
        ... )
        >>> print(f"Edge: {result['edge']:.3f}")
        Edge: 0.078
        >>> print(f"Meets Threshold: {result['meets_threshold']}")
        Meets Threshold: True
    """
    # Step 1: Validate inputs
    if weights is None:
        # Equal weights (1/N for each model)
        weights = [Decimal("1") / len(model_ids) for _ in model_ids]

    if len(weights) != len(model_ids):
        raise ValueError(
            f"Weights length ({len(weights)}) must match model_ids length ({len(model_ids)})"
        )

    if sum(weights) != Decimal("1"):
        raise ValueError(f"Weights must sum to 1.0, got {sum(weights)}")

    # Step 2: Fetch market price from Kalshi
    market = self.kalshi_client.get_market(market_id)
    market_price = market['yes_ask_dollars']  # Use ASK price (price we pay to buy YES)

    self.logger.info(
        f"Fetched market price for {market_id}: {market_price}",
        extra={'market_id': market_id, 'market_price': str(market_price)}
    )

    # Step 3: Generate predictions from each model
    predictions = []
    for model_id in model_ids:
        pred = self.model_manager.predict(
            model_id=model_id,
            market_id=market_id
        )
        predictions.append(pred['predicted_prob'])

        self.logger.debug(
            f"Model {model_id} prediction: {pred['predicted_prob']}",
            extra={'model_id': model_id, 'prediction': str(pred['predicted_prob'])}
        )

    # Step 4: Calculate ensemble prediction (weighted average)
    ensemble_pred = sum(
        pred * weight
        for pred, weight in zip(predictions, weights)
    )

    # Step 5: Calculate confidence interval
    std_dev = statistics.stdev(predictions) if len(predictions) > 1 else Decimal("0")
    std_error = std_dev / (len(predictions) ** 0.5)
    ci_lower = ensemble_pred - (Decimal("1.96") * std_error)
    ci_upper = ensemble_pred + (Decimal("1.96") * std_error)

    # Step 6: Calculate edge
    edge = ensemble_pred - market_price

    # Step 7: Check threshold
    meets_threshold = edge >= self.min_edge_threshold

    # Step 8: Log calculation to database
    edge_log_id = self.crud.create(
        table='edge_calculations',
        data={
            'market_id': market_id,
            'market_price': market_price,
            'ensemble_prediction': ensemble_pred,
            'edge': edge,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'models_used': model_ids,
            'weights_used': [str(w) for w in weights],
            'meets_threshold': meets_threshold,
            'calculated_at': datetime.utcnow()
        }
    )

    self.logger.info(
        f"Calculated edge for {market_id}: {edge:.4f} (threshold: {self.min_edge_threshold})",
        extra={
            'market_id': market_id,
            'edge': str(edge),
            'meets_threshold': meets_threshold,
            'edge_log_id': edge_log_id
        }
    )

    return {
        'market_id': market_id,
        'market_price': market_price,
        'model_pred': ensemble_pred,
        'edge': edge,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'meets_threshold': meets_threshold,
        'timestamp': datetime.utcnow(),
        'models_used': model_ids
    }
```

---

## 5. Confidence Intervals & Uncertainty

### Why Confidence Intervals Matter

**Problem:** A single ensemble prediction (e.g., 59.8%) doesn't tell us model agreement.

**Solution:** Calculate 95% confidence interval to quantify prediction uncertainty.

**Interpretation:**
- **Narrow CI (±2%)** = Models agree → High confidence → Larger position size
- **Wide CI (±10%)** = Models disagree → Low confidence → Smaller position size or no trade

### Confidence Interval Calculation

```python
def calculate_confidence_interval(
    self,
    predictions: list[Decimal],
    confidence_level: Decimal = Decimal("0.95")
) -> tuple[Decimal, Decimal]:
    """
    Calculate confidence interval for ensemble predictions.

    Args:
        predictions: List of model predictions
        confidence_level: Confidence level (default 0.95 = 95%)

    Returns:
        Tuple of (ci_lower, ci_upper)

    Educational Note:
        95% confidence interval means:
        "We are 95% confident the true win probability is between ci_lower and ci_upper"

        If market_price < ci_lower:
            ✅ Edge is statistically significant (high confidence trade)

        If ci_lower < market_price < ci_upper:
            ⚠️ Edge may not be significant (models disagree, risky trade)

        If market_price > ci_upper:
            ❌ Negative edge (don't trade)

    Example:
        >>> predictions = [Decimal("0.61"), Decimal("0.58"), Decimal("0.62")]
        >>> ci_lower, ci_upper = calc.calculate_confidence_interval(predictions)
        >>> print(f"95% CI: [{ci_lower:.3f}, {ci_upper:.3f}]")
        95% CI: [0.579, 0.627]
        >>> market_price = Decimal("0.52")
        >>> if market_price < ci_lower:
        ...     print("✅ Edge is statistically significant")
        ✅ Edge is statistically significant
    """
    if len(predictions) == 1:
        # Single model → no variance
        return (predictions[0], predictions[0])

    # Calculate ensemble prediction (mean)
    ensemble_pred = statistics.mean(predictions)

    # Calculate standard error
    std_dev = statistics.stdev(predictions)
    std_error = std_dev / (len(predictions) ** 0.5)

    # Z-score for 95% confidence (1.96)
    # For 99% confidence, use 2.576
    # For 90% confidence, use 1.645
    z_score = Decimal("1.96")  # 95% CI

    # Calculate bounds
    ci_lower = ensemble_pred - (z_score * std_error)
    ci_upper = ensemble_pred + (z_score * std_error)

    # Clamp to [0, 1] (probabilities can't exceed bounds)
    ci_lower = max(ci_lower, Decimal("0"))
    ci_upper = min(ci_upper, Decimal("1"))

    return (ci_lower, ci_upper)
```

---

## 6. Edge Thresholding & Filtering

### Minimum Edge Threshold

**Configuration:** `min_edge` in strategy config (typically 5%)

**Purpose:** Filter out low-edge opportunities to reduce false positives.

**Rationale:**
- **Edge < 5%:** May be noise (model miscalibration, market efficiency)
- **Edge ≥ 5%:** Likely genuine mispricing (worth trading)

### find_opportunities() Method

```python
def find_opportunities(
    self,
    market_ids: list[str],
    model_ids: list[int],
    weights: list[Decimal] | None = None
) -> list[dict[str, Any]]:
    """
    Find trading opportunities across multiple markets.

    Args:
        market_ids: List of Kalshi market tickers
        model_ids: Model IDs to use for predictions
        weights: Ensemble weights (optional, default equal weights)

    Returns:
        List of opportunities with edge ≥ min_edge_threshold,
        sorted by edge (descending).

    Educational Note:
        Opportunity Discovery Process:
        1. Calculate edge for ALL markets in parallel
        2. Filter opportunities where edge ≥ min_edge_threshold
        3. Sort by edge (largest first)
        4. Return top N opportunities

        This is called HOURLY by the event loop to find live trades.

    Example:
        >>> edge_calc = EdgeCalculator(min_edge_threshold=Decimal("0.05"))
        >>> markets = [
        ...     "KXNFL-2024-11-24-BUF-MIA",
        ...     "KXNFL-2024-11-24-KC-LV",
        ...     "KXNFL-2024-11-24-SF-GB"
        ... ]
        >>> opportunities = edge_calc.find_opportunities(
        ...     market_ids=markets,
        ...     model_ids=[42, 43]
        ... )
        >>> print(f"Found {len(opportunities)} opportunities")
        Found 2 opportunities
        >>> for opp in opportunities:
        ...     print(f"{opp['market_id']}: {opp['edge']:.3f} edge")
        KXNFL-2024-11-24-BUF-MIA: 0.078 edge
        KXNFL-2024-11-24-SF-GB: 0.062 edge
    """
    opportunities = []

    for market_id in market_ids:
        try:
            edge_result = self.calculate_edge(
                market_id=market_id,
                model_ids=model_ids,
                weights=weights
            )

            if edge_result['meets_threshold']:
                opportunities.append(edge_result)

        except Exception as e:
            self.logger.error(
                f"Failed to calculate edge for {market_id}: {e}",
                extra={'market_id': market_id, 'error': str(e)}
            )
            continue

    # Sort by edge (descending)
    opportunities.sort(key=lambda x: x['edge'], reverse=True)

    self.logger.info(
        f"Found {len(opportunities)} opportunities with edge ≥ {self.min_edge_threshold}",
        extra={
            'opportunities_count': len(opportunities),
            'markets_scanned': len(market_ids),
            'min_edge_threshold': str(self.min_edge_threshold)
        }
    )

    return opportunities
```

---

## 7. Historical Edge Tracking

### Purpose

Track edge calculations over time to:
1. **Backtest Models:** Compare predicted edge vs realized edge
2. **Model Calibration:** Identify systematic over/underestimation
3. **Strategy Evaluation:** Verify strategies trade when edge exists
4. **Performance Attribution:** Correlate realized P&L with predicted edge

### Database Schema

**Table:** `edge_calculations`

```sql
CREATE TABLE edge_calculations (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(100) NOT NULL,
    market_price DECIMAL(10,4) NOT NULL,  -- Kalshi YES price
    ensemble_prediction DECIMAL(10,4) NOT NULL,  -- Model prediction
    edge DECIMAL(10,4) NOT NULL,  -- ensemble_pred - market_price
    ci_lower DECIMAL(10,4) NOT NULL,  -- 95% CI lower bound
    ci_upper DECIMAL(10,4) NOT NULL,  -- 95% CI upper bound
    models_used INTEGER[] NOT NULL,  -- Array of model_ids
    weights_used TEXT[] NOT NULL,  -- Array of weights as strings
    meets_threshold BOOLEAN NOT NULL,  -- edge >= min_edge
    calculated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Indexes for querying
    INDEX idx_edge_market (market_id),
    INDEX idx_edge_timestamp (calculated_at),
    INDEX idx_edge_threshold (meets_threshold)
);
```

### Query Historical Edge

```python
def get_edge_history(
    self,
    market_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    meets_threshold_only: bool = False
) -> list[dict[str, Any]]:
    """
    Query historical edge calculations.

    Args:
        market_id: Filter by market (optional, all markets if None)
        start_date: Start of date range (optional)
        end_date: End of date range (optional)
        meets_threshold_only: Only return edges >= min_edge_threshold

    Returns:
        List of edge calculation records.

    Example:
        >>> # Get all edges for BUF-MIA market
        >>> history = edge_calc.get_edge_history(
        ...     market_id="KXNFL-2024-11-24-BUF-MIA"
        ... )
        >>> print(f"Calculated edge {len(history)} times")
        Calculated edge 24 times

        >>> # Get edges that met threshold in last 7 days
        >>> from datetime import datetime, timedelta
        >>> history = edge_calc.get_edge_history(
        ...     start_date=datetime.utcnow() - timedelta(days=7),
        ...     meets_threshold_only=True
        ... )
        >>> print(f"Found {len(history)} trading opportunities")
        Found 142 trading opportunities
    """
    filters = []

    if market_id:
        filters.append(f"market_id = '{market_id}'")

    if start_date:
        filters.append(f"calculated_at >= '{start_date}'")

    if end_date:
        filters.append(f"calculated_at <= '{end_date}'")

    if meets_threshold_only:
        filters.append("meets_threshold = TRUE")

    where_clause = " AND ".join(filters) if filters else "1=1"

    query = f"""
        SELECT *
        FROM edge_calculations
        WHERE {where_clause}
        ORDER BY calculated_at DESC
    """

    return self.crud.execute_query(query)
```

---

## 8. Integration with Trading System

### Event Loop Integration

**Schedule:** Edge calculation runs **hourly** via event loop.

**Workflow:**
1. Event loop triggers `calculate_edges_for_all_markets()` every hour
2. EdgeCalculator fetches all active markets from Kalshi
3. Calculate edge for each market using active models
4. Log opportunities (edge ≥ min_edge) to database
5. TradingEngine fetches opportunities and executes trades

**Event Loop Code (Phase 5a):**
```python
# src/precog/event_loop/trading_loop.py

async def hourly_edge_calculation(edge_calculator: EdgeCalculator):
    """
    Calculate edge for all active markets (runs hourly).

    Educational Note:
        This is the FIRST step in the trading workflow:
        1. Calculate edge (hourly) ← YOU ARE HERE
        2. Execute trades (when edge found)
        3. Monitor positions (continuous)
        4. Evaluate exit conditions (continuous)

        Hourly frequency balances:
        - Fresh data (market prices update constantly)
        - API rate limits (Kalshi 100 req/min)
        - Trading costs (don't overtrade on small edge changes)
    """
    logger.info("Starting hourly edge calculation")

    # Fetch all active NFL markets from Kalshi
    markets = kalshi_client.get_markets(series_ticker="KXNFLGAME", status="active")

    market_ids = [m['ticker'] for m in markets]
    logger.info(f"Fetched {len(market_ids)} active markets")

    # Get active models for ensemble
    active_models = model_manager.list_models(status='active')
    model_ids = [m['model_id'] for m in active_models]

    # Calculate edge for all markets
    opportunities = edge_calculator.find_opportunities(
        market_ids=market_ids,
        model_ids=model_ids
    )

    logger.info(f"Found {len(opportunities)} trading opportunities")

    # Opportunities logged to database, TradingEngine will execute trades
    return opportunities
```

### TradingEngine Integration

```python
# src/precog/trading/trading_engine.py

def execute_opportunities(self):
    """
    Execute trades for all current opportunities.

    Educational Note:
        TradingEngine queries edge_calculations table for
        opportunities where:
        - edge >= min_edge_threshold
        - calculated_at within last hour (fresh data)
        - market still active (not settled/expired)

        For each opportunity, calculate position size using
        Kelly Criterion: f* = edge / variance
    """
    # Query opportunities from last hour
    opportunities = self.edge_calculator.get_edge_history(
        start_date=datetime.utcnow() - timedelta(hours=1),
        meets_threshold_only=True
    )

    for opp in opportunities:
        # Check if we already have position on this market
        existing_position = self.position_manager.get_position(
            market_id=opp['market_id']
        )

        if existing_position:
            logger.info(f"Already have position on {opp['market_id']}, skipping")
            continue

        # Calculate position size using Kelly Criterion
        position_size = self._calculate_kelly_size(
            edge=opp['edge'],
            confidence_interval=(opp['ci_lower'], opp['ci_upper'])
        )

        # Execute trade
        self.execute_trade(
            market_id=opp['market_id'],
            side='yes',
            quantity=position_size,
            price=opp['market_price']
        )
```

---

## 9. Performance Optimization

### Caching Market Prices

**Problem:** Fetching market prices from Kalshi API for 100+ markets is slow (10+ seconds).

**Solution:** Cache market prices for 5 minutes (prices don't change that fast).

```python
from functools import lru_cache
from datetime import datetime, timedelta

class EdgeCalculator:
    def __init__(self, ...):
        # ... existing init ...
        self._price_cache = {}
        self._cache_ttl = timedelta(minutes=5)

    def _get_market_price_cached(self, market_id: str) -> Decimal:
        """
        Get market price with 5-minute cache.

        Educational Note:
            Kalshi market prices update every ~30 seconds.
            Caching for 5 minutes reduces API calls by 10x
            while staying reasonably fresh.
        """
        now = datetime.utcnow()

        # Check cache
        if market_id in self._price_cache:
            cached_price, cached_time = self._price_cache[market_id]
            if now - cached_time < self._cache_ttl:
                return cached_price

        # Cache miss or expired, fetch fresh price
        market = self.kalshi_client.get_market(market_id)
        price = market['yes_ask_dollars']

        # Update cache
        self._price_cache[market_id] = (price, now)

        return price
```

### Parallel Edge Calculation

**Problem:** Calculating edge for 100 markets sequentially takes 100+ seconds.

**Solution:** Use `asyncio` to calculate edges in parallel.

```python
import asyncio

async def calculate_edge_async(
    self,
    market_id: str,
    model_ids: list[int],
    weights: list[Decimal] | None = None
) -> dict[str, Any]:
    """
    Async version of calculate_edge() for parallel execution.

    Educational Note:
        Parallel execution reduces total time:
        - Sequential: 100 markets × 1 sec = 100 seconds
        - Parallel (10 workers): 100 markets ÷ 10 = 10 seconds

        Limited to 10 workers to respect Kalshi rate limit (100 req/min).
    """
    # Same logic as calculate_edge(), but uses await for API calls
    market = await self.kalshi_client.get_market_async(market_id)
    # ... rest of calculation ...

async def find_opportunities_async(
    self,
    market_ids: list[str],
    model_ids: list[int],
    weights: list[Decimal] | None = None,
    max_workers: int = 10
) -> list[dict[str, Any]]:
    """
    Find opportunities in parallel using asyncio.

    Educational Note:
        Uses asyncio.Semaphore to limit concurrent requests
        to 10 (respects Kalshi 100 req/min rate limit).
    """
    semaphore = asyncio.Semaphore(max_workers)

    async def calculate_with_limit(market_id: str):
        async with semaphore:
            return await self.calculate_edge_async(market_id, model_ids, weights)

    # Calculate all edges in parallel
    tasks = [calculate_with_limit(mid) for mid in market_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter successful results and check threshold
    opportunities = [
        r for r in results
        if not isinstance(r, Exception) and r['meets_threshold']
    ]

    return sorted(opportunities, key=lambda x: x['edge'], reverse=True)
```

---

## 10. Testing & Validation

### Unit Tests

**File:** `tests/unit/analytics/test_edge_calculator.py`

```python
"""
Unit tests for EdgeCalculator.

Tests the edge calculation logic in isolation using mocked API responses.
"""
from decimal import Decimal
import pytest
from unittest.mock import Mock, patch

from precog.analytics.edge_calculator import EdgeCalculator


class TestEdgeCalculator:
    """Test EdgeCalculator edge calculation logic."""

    def test_calculate_edge_single_model(self, mock_kalshi_client, mock_model_manager):
        """
        Test edge calculation with single model.

        Scenario:
            - Market price: 0.52 (52% implied probability)
            - Model prediction: 0.61 (61% win probability)
            - Expected edge: 0.09 (9%)
        """
        # Setup mocks
        mock_kalshi_client.get_market.return_value = {
            'ticker': 'KXNFL-2024-11-24-BUF-MIA',
            'yes_ask_dollars': Decimal("0.52")
        }

        mock_model_manager.predict.return_value = {
            'predicted_prob': Decimal("0.61")
        }

        # Execute
        edge_calc = EdgeCalculator(
            kalshi_client=mock_kalshi_client,
            model_manager=mock_model_manager,
            crud=Mock(),
            min_edge_threshold=Decimal("0.05")
        )

        result = edge_calc.calculate_edge(
            market_id='KXNFL-2024-11-24-BUF-MIA',
            model_ids=[42]
        )

        # Verify
        assert result['market_price'] == Decimal("0.52")
        assert result['model_pred'] == Decimal("0.61")
        assert result['edge'] == Decimal("0.09")
        assert result['meets_threshold'] is True  # 9% > 5% threshold

    def test_calculate_edge_ensemble(self, mock_kalshi_client, mock_model_manager):
        """
        Test edge calculation with multi-model ensemble.

        Scenario:
            - Market price: 0.52
            - Model 1 prediction: 0.61 (weight 0.6)
            - Model 2 prediction: 0.58 (weight 0.4)
            - Expected ensemble: 0.598 (59.8%)
            - Expected edge: 0.078 (7.8%)
        """
        mock_kalshi_client.get_market.return_value = {
            'yes_ask_dollars': Decimal("0.52")
        }

        # Two different predictions
        mock_model_manager.predict.side_effect = [
            {'predicted_prob': Decimal("0.61")},  # Model 42
            {'predicted_prob': Decimal("0.58")}   # Model 43
        ]

        edge_calc = EdgeCalculator(
            kalshi_client=mock_kalshi_client,
            model_manager=mock_model_manager,
            crud=Mock(),
            min_edge_threshold=Decimal("0.05")
        )

        result = edge_calc.calculate_edge(
            market_id='KXNFL-2024-11-24-BUF-MIA',
            model_ids=[42, 43],
            weights=[Decimal("0.6"), Decimal("0.4")]
        )

        # Verify ensemble calculation
        expected_ensemble = (Decimal("0.61") * Decimal("0.6")) + (Decimal("0.58") * Decimal("0.4"))
        assert result['model_pred'] == expected_ensemble  # 0.598
        assert result['edge'] == expected_ensemble - Decimal("0.52")  # 0.078
        assert result['meets_threshold'] is True  # 7.8% > 5%

    def test_calculate_edge_below_threshold(self, mock_kalshi_client, mock_model_manager):
        """
        Test edge calculation below min_edge_threshold.

        Scenario:
            - Market price: 0.52
            - Model prediction: 0.55 (only 3% edge)
            - Expected: meets_threshold = False
        """
        mock_kalshi_client.get_market.return_value = {
            'yes_ask_dollars': Decimal("0.52")
        }

        mock_model_manager.predict.return_value = {
            'predicted_prob': Decimal("0.55")  # Only 3% edge
        }

        edge_calc = EdgeCalculator(
            kalshi_client=mock_kalshi_client,
            model_manager=mock_model_manager,
            crud=Mock(),
            min_edge_threshold=Decimal("0.05")  # 5% threshold
        )

        result = edge_calc.calculate_edge(
            market_id='KXNFL-2024-11-24-BUF-MIA',
            model_ids=[42]
        )

        assert result['edge'] == Decimal("0.03")  # 3% edge
        assert result['meets_threshold'] is False  # 3% < 5% threshold
```

---

`★ Insight ─────────────────────────────────────`
**Edge Calculation: The Core of EV+ Trading**

1. **Edge = True Probability - Market Price:** Every profitable trade starts with positive edge. If edge ≤ 0, don't trade (market is efficient or we're wrong).

2. **Multi-Model Ensembles Reduce Variance:** Combining multiple models (weighted average) produces more reliable predictions than any single model. The confidence interval quantifies model disagreement.

3. **Threshold Filtering Prevents False Positives:** Only trading when edge ≥ 5% filters out noise from model miscalibration. Lower thresholds = more trades but lower win rate.
`─────────────────────────────────────────────────`

I've created the EDGE_CALCULATION_GUIDE_V1.0.md (~410 lines). Now let me create the final guide: DATA_COLLECTION_GUIDE_V1.0.md.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[
  {"content": "Create STRATEGY_EVALUATION_SPEC_V1.0.md (~400 lines)", "status": "completed", "activeForm": "Creating STRATEGY_EVALUATION_SPEC_V1.0.md"},
  {"content": "Create AB_TESTING_FRAMEWORK_SPEC_V1.0.md (~350 lines)", "status": "completed", "activeForm": "Creating AB_TESTING_FRAMEWORK_SPEC_V1.0.md"},
  {"content": "Create MODEL_TRAINING_GUIDE_V1.0.md (~500 lines)", "status": "completed", "activeForm": "Creating MODEL_TRAINING_GUIDE_V1.0.md"},
  {"content": "Create EDGE_CALCULATION_GUIDE_V1.0.md (~400 lines)", "status": "completed", "activeForm": "Creating EDGE_CALCULATION_GUIDE_V1.0.md"},
  {"content": "Create DATA_COLLECTION_GUIDE_V1.0.md (~450 lines)", "status": "in_progress", "activeForm": "Creating DATA_COLLECTION_GUIDE_V1.0.md"},
  {"content": "Update MASTER_INDEX V2.33 → V2.34 with 5 new specs", "status": "pending", "activeForm": "Updating MASTER_INDEX"}
]
