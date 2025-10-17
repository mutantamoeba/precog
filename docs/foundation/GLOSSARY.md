# Glossary of Key Terms & Concepts

---
**Version:** 1.1
**Last Updated:** 2025-10-16
**Status:** ✅ Current
**Changes in v1.1:** Added comprehensive "CRITICAL: Probability vs. Odds vs. Price" section; clarified Edge and EV calculations
---

## CRITICAL: Probability vs. Odds vs. Price

**This distinction is FUNDAMENTAL to understanding Precog. Read carefully.**

---

### Probability

**Definition:** The likelihood of an event occurring, expressed as a decimal from 0.0000 to 1.0000.

**Example:**
- `probability = 0.6500` means 65% chance of event occurring
- `probability = 0.3500` means 35% chance of event NOT occurring

**Usage in Precog:**
- **What we calculate:** `true_probability`, `win_probability`, `model_probability`
- **Where stored:** `probability_matrices.win_probability`, `markets.calculated_probability`
- **Functions:** `calculate_win_probability()`, `adjust_probability_for_weather()`
- **Range:** 0.0000 (impossible) to 1.0000 (certain)

**Formula:** `probability = wins / total_games`

---

### Market Price

**Definition:** What Kalshi YES contracts trade for, expressed in dollars from $0.0001 to $0.9999.

**Example:**
- Kalshi shows: `yes_ask = $0.6000`
- Interpretation: Market thinks 60% probability
- If you buy at $0.60 and outcome is YES, you receive $1.00 (gain $0.40)

**Usage in Precog:**
- **What Kalshi returns:** `yes_bid`, `yes_ask`, `yes_price`
- **Where stored:** `markets.market_price_bid`, `markets.market_price_ask`
- **Interpretation:** Market price = implied probability for Kalshi
- **Range:** $0.0001 (market thinks <1% chance) to $0.9999 (market thinks >99% chance)

**Critical Note:** Kalshi prices ARE probabilities (unlike traditional bookmaker odds which need conversion)

---

### Odds

**Definition:** A ratio representation of probability, expressed in various formats.

**Formats:**
1. **Decimal Odds:** `odds_decimal = 1 / probability`
   - Example: probability = 0.65 → decimal odds = 1.54

2. **American Odds:** Negative for favorites, positive for underdogs
   - Example: probability = 0.65 → American odds ≈ -186

3. **Fractional Odds:** Common in UK sports betting
   - Example: probability = 0.65 → fractional odds ≈ 6/5

**Usage in Precog:**
- **Rarely used internally** (we use probabilities, not odds)
- **Use ONLY for:** User-facing displays, importing from traditional sportsbooks
- **Never use for:** Database fields, function parameters, internal calculations

**Why we avoid "odds":**
- Creates confusion (multiple formats exist)
- Kalshi uses probabilities/prices, not odds
- More intuitive to compare: `probability = 0.70` vs. `market_price = 0.60` (easy to see 10% edge)

---

### Edge

**Definition:** The difference between your calculated probability and the market's implied probability.

**Formula:** `edge = true_probability - market_price`

**Example:**
- You calculate: `true_probability = 0.7000` (70% chance)
- Kalshi shows: `market_price = 0.6000` ($0.60 for YES)
- Your edge: `edge = 0.7000 - 0.6000 = 0.1000` (10% edge)

**Interpretation:**
- **Positive edge** (`edge > 0`): You think event is MORE likely than market → Potential bet
- **Negative edge** (`edge < 0`): You think event is LESS likely than market → Avoid bet
- **Zero edge** (`edge = 0`): You agree with market → No advantage

**Usage in Precog:**
- **Where stored:** `opportunities.edge`
- **Minimum threshold:** Configurable (e.g., `min_edge = 0.05` = 5% minimum)
- **Used for:** Filtering profitable opportunities

---

### Expected Value (EV)

**Definition:** The average profit or loss per dollar wagered, accounting for both probability and payout.

**Formula (for Kalshi YES contracts):**
```
EV = (true_probability × payout) - cost
   = (true_probability × $1.00) - market_price
```

**Example:**
- You calculate: `true_probability = 0.7000`
- Kalshi shows: `market_price = $0.6000`
- Payout if win: `$1.00` (Kalshi standard)
- Cost: `$0.6000` (what you pay)

```
EV = (0.70 × $1.00) - $0.60
   = $0.70 - $0.60
   = $0.10 per $1.00 wagered (10% expected return)
```

**Interpretation:**
- **Positive EV** (`EV > 0`): Profitable bet on average
- **Negative EV** (`EV < 0`): Losing bet on average
- **Zero EV** (`EV = 0`): Break-even (no advantage)

**Usage in Precog:**
- **Where stored:** `opportunities.expected_value`
- **Minimum threshold:** Configurable (e.g., `min_ev = 0.03` = 3% minimum)
- **Used for:** Ranking opportunities, position sizing

---

### Summary Table

| Term | Range | What It Represents | Use In Precog |
|------|-------|-------------------|---------------|
| **Probability** | 0.0000 - 1.0000 | Likelihood of event | Our calculations (`true_probability`) |
| **Market Price** | $0.0001 - $0.9999 | Kalshi contract price | What we compare against (`market_price`) |
| **Odds** | Various formats | Ratio representation | Rarely used (display only) |
| **Edge** | -1.0000 - +1.0000 | Advantage vs. market | `true_probability - market_price` |
| **Expected Value** | Any decimal | Profit per $1 wagered | `(probability × payout) - cost` |

---

### Correct vs. Incorrect Terminology

✅ **CORRECT:**
```python
true_probability = Decimal("0.7000")  # We calculate 70% chance
market_price = Decimal("0.6000")      # Market trading at $0.60
edge = true_probability - market_price # 0.10 = 10% edge
ev = (true_probability * Decimal("1.00")) - market_price  # $0.10 EV
```

❌ **INCORRECT:**
```python
odds = 0.70  # ❌ Don't call it "odds"
implied_odds = 0.60  # ❌ It's "market_price" or "implied_probability"
calculate_odds()  # ❌ Should be calculate_win_probability()
odds_buckets  # ❌ Should be probability_buckets
```

---

### When to Use Each Term

**Use "Probability" for:**
- Our calculated likelihoods: `true_probability`, `win_probability`
- Historical data: `historical_win_probability`
- Database fields: `probability_matrices.win_probability`
- Function outputs: `calculate_win_probability()` returns probability
- Internal calculations

**Use "Market Price" for:**
- Kalshi API fields: `yes_bid`, `yes_ask`, `yes_price`
- What contracts trade for: `market_price`
- Database fields: `markets.market_price_ask`
- Comparison baseline

**Use "Odds" for:**
- User-facing displays with specific format: "Decimal Odds: 1.54"
- Importing from traditional sportsbooks
- NEVER for internal calculations or database storage

**Use "Edge" for:**
- Advantage measurement: `edge = true_probability - market_price`
- Filtering opportunities: `WHERE edge > 0.05`

**Use "Expected Value (EV)" for:**
- Profit calculations: `EV = (probability × payout) - cost`
- Ranking opportunities: `ORDER BY expected_value DESC`
- Position sizing: Kelly Criterion uses EV

---

**Why This Matters:**

1. **Technical Accuracy:** Probabilities and odds are mathematically different
2. **Code Clarity:** Clear terminology prevents bugs (especially with type hints)
3. **Kalshi Integration:** Kalshi uses prices/probabilities, not traditional odds
4. **Team Communication:** Everyone speaks the same language
5. **Educational Value:** You learn the correct concepts as you build

**If in doubt, ask:** "Is this a probability (0.0-1.0) or a price ($0.00-$1.00)?" Then name it accordingly.

---

## Prediction Market Terms

### Binary Market
A market with only two possible outcomes (Yes/No, Team A wins/Team B wins). Prices represent probability: $0.65 Yes price = 65% implied probability of Yes outcome.

### Categorical Market
A market with 3+ mutually exclusive outcomes. Example: "Which team wins the Super Bowl?" with 32 team options.

### Market Price
The current trading price for an outcome. On Kalshi, prices range from $0.01 to $0.99 (1¢ to 99¢). The price represents the market's implied probability.

### Yes/No Price
In binary markets:
- **Yes Price:** Cost to buy a contract that pays $1 if outcome occurs
- **No Price:** Cost to buy a contract that pays $1 if outcome doesn't occur
- **Relationship:** Yes Price + No Price ≈ $1.00 (sometimes slightly more due to fees/spread)

### Spread
The difference between ask and bid prices. Example:
- Best bid (buyers): $0.58
- Best ask (sellers): $0.63
- Spread: $0.63 - $0.58 = $0.05 (5¢)

Tight spreads (1-3¢) indicate liquid markets. Wide spreads (>5¢) indicate less liquidity or higher uncertainty.

### Liquidity
How easy it is to buy/sell contracts without moving the price. Measured by:
- **Volume:** Total contracts traded
- **Open Interest:** Total outstanding contracts not yet settled

### Series
A collection of related events. Example: "NFL Games" series contains all individual NFL game events.

### Event
A specific occurrence within a series. Example: "Cowboys vs Giants - Week 7" is an event within the "NFL Games" series.

### Settlement
When the market outcome is determined and contracts pay out. Yes contracts pay $1, No contracts pay $0.

---

## Trading Strategy Terms

### Edge
The advantage a trader has over the market. Measured as **Expected Value (EV)**.

**Formula:** EV = (True Probability × Profit if Win) - (False Probability × Loss if Lose)

**Example:**
- True probability: 70%
- Market price: $0.60
- EV = (0.70 × $0.40) - (0.30 × $0.60) = $0.28 - $0.18 = $0.10 per contract (10% edge)

### Expected Value (EV)
The average amount you expect to win/lose per bet over the long run.
- **EV+ (Positive EV):** Good bet, take it
- **EV- (Negative EV):** Bad bet, avoid it
- **EV = 0:** Fair bet, no advantage

### Implied Probability
What the market price suggests is the probability of an outcome.

**Calculation:** Implied Probability = Market Price (for Yes side)

**Example:** 
- Market price: $0.65
- Implied probability: 65%

### True Probability
The actual probability of an outcome based on historical data, models, or analysis. The goal is to find situations where true probability differs from implied probability.

### Positive EV (EV+)
When your calculated true probability is higher than the market's implied probability. This is your edge.

**Example:**
- True probability: 75%
- Market price: $0.68 (implied 68%)
- You have a 7% edge (75% - 68%)

### Confidence Level
How certain you are about your probability estimate:
- **High Confidence:** Large sample size (500+ games), narrow confidence interval (<10%), recent data
- **Medium Confidence:** Moderate sample (200-500 games), wider interval (10-15%)
- **Low Confidence:** Small sample (<200 games), wide interval (>15%), older data

### Confidence Interval
A range around your probability estimate showing uncertainty.

**Example:** Win probability = 72% with 95% CI [68%, 76%]
- You're 95% confident the true probability is between 68% and 76%
- Narrower intervals = more confidence

---

## Position Management Terms

### Position
An open bet on a market. Contains:
- Entry price (what you paid)
- Quantity (how many contracts)
- Side (Yes or No)
- Unrealized P&L (current value vs. cost)

### Position Sizing
How much to bet on each opportunity. Common methods:
- **Fixed amount:** $100 per bet
- **Percentage of bankroll:** 5% of total capital
- **Kelly Criterion:** Mathematically optimal based on edge and odds

### Kelly Criterion
A formula for optimal bet sizing that maximizes long-term growth.

**Formula:** Bet Size = (Edge / Odds)

**Conservative Kelly:** Use fraction of Kelly (e.g., 25%) to reduce volatility

**Example:**
- Bankroll: $10,000
- Edge: 10% (EV = 0.10)
- Odds: 1.67 (paying $0.40 on $0.60 bet)
- Full Kelly: (0.10 / 0.67) × $10,000 = $1,490
- 25% Kelly: $372.50 (safer)

### Stop Loss
Automatic exit when position reaches a certain loss threshold.

**Example:** -15% stop loss means sell if position drops 15% below entry price

### Profit Target
Automatic exit when position reaches a certain gain threshold.

**Example:** +20% profit target means sell if position rises 20% above entry price

### Unrealized P&L
Profit or loss on open positions (not yet closed).

**Calculation:** (Current Value - Cost Basis) = Unrealized P&L

### Realized P&L
Profit or loss on closed positions (actual money made/lost).

### Early Exit
Closing a position before the market settles. Done when:
- Edge disappears (probability changes)
- Stop loss triggered
- Profit target reached
- Risk reduction needed

### Scale In/Out
Adjusting position size as the edge changes:
- **Scale In:** Add to position when edge increases
- **Scale Out:** Reduce position when edge decreases

---

## Risk Management Terms

### Circuit Breaker
An automatic safety mechanism that stops trading when certain conditions are met.

**Examples:**
- Daily loss limit (-$500)
- Hourly trade limit (10 trades)
- API failure threshold (5 consecutive failures)

### Defense in Depth
Multiple layers of safety checks:
1. Pre-trade validation (balance, limits, liquidity)
2. Circuit breakers (automatic stops)
3. Position monitoring (alerts, early exits)
4. Daily reconciliation (verify accuracy)

### Correlation
How much two markets move together. High correlation = risky to hold both.

**Example:** "Cowboys win" and "Cowboys score 30+ points" are highly correlated

### Exposure
Total amount at risk across all positions.
- **Single Position Exposure:** Amount in one bet
- **Total Exposure:** Sum across all positions
- **Correlated Exposure:** Sum of correlated positions

### Maximum Drawdown
The largest peak-to-trough decline in account value.

**Example:** 
- Peak: $10,000
- Trough: $8,500
- Max Drawdown: $1,500 (15%)

### Sharpe Ratio
Measures risk-adjusted returns. Higher is better.

**Formula:** (Average Return - Risk-Free Rate) / Standard Deviation of Returns

**Interpretation:**
- Sharpe > 1.0: Good
- Sharpe > 2.0: Very good
- Sharpe > 3.0: Excellent

---

## Technical Terms

### Versioned Table
A database table that keeps history by adding new rows instead of updating.

**Method:** Each row has `row_current_ind` (TRUE = current, FALSE = historical)

**Example:** Market price changes from $0.60 → $0.65 → $0.70
- 3 rows in database (one per price)
- Can query historical prices

### Append-Only Table
A database table where rows are never updated, only inserted. Used for immutable data like trades.

### Material Change
A change significant enough to warrant creating a new database row.

**Criteria:**
- Price change ≥ 1¢ (absolute)
- OR price change ≥ 2% (percentage)
- OR volume change ≥ 10 contracts
- OR status change

### RSA-PSS
Authentication method used by Kalshi API. Requires:
- Private key (kept secret)
- Public key (shared with Kalshi)
- Signature generation for each request

### WebSocket
Real-time bidirectional communication protocol. Used for:
- Live market price updates
- Instant notifications
- Reduced latency vs. polling

### REST API
Request/response protocol. Client requests data, server responds.
- **Polling:** Repeatedly asking for updates (every 15-60 seconds)
- **Endpoints:** Specific URLs for different data (markets, events, positions)

### Rate Limiting
Restrictions on how many API requests you can make:
- **Per minute:** 100 requests/minute (Kalshi)
- **Per day:** Often unlimited for authenticated users

### Async/Asynchronous
Non-blocking code execution. Program can do other work while waiting for API responses.

**Benefits:**
- Multiple API calls simultaneously
- Better resource utilization
- Faster overall execution

---

## Sports Statistics Terms

### DVOA (Defense-adjusted Value Over Average)
Football stat measuring team efficiency compared to league average, adjusted for opponent strength. Used to enhance odds models.

### EPA (Expected Points Added)
Football stat measuring how much a play changes expected points. Positive EPA = good play.

### SP+ (Success Rate Plus)
College football rating system combining efficiency and explosiveness.

### Net Rating
Basketball stat: points scored per 100 possessions minus points allowed per 100 possessions.

### Elo Rating
Universal rating system tracking team strength over time. Higher Elo = stronger team.

---

## System Architecture Terms

### Repository Pattern
Code pattern separating data access from business logic.

**Example:**
```python
market_repo.get_active_markets()  # Data access
edge_service.calculate_edge()     # Business logic
```

### Factory Pattern
Code pattern for creating objects without specifying exact class.

**Example:** PlatformFactory creates KalshiPlatform or PolymarketPlatform based on config

### Configuration Injection
Passing configuration to objects instead of hardcoding values.

**Benefit:** Easy to change behavior without modifying code

### Event-Driven Architecture
System reacts to events (price changes, game updates) rather than polling on schedule.

**Benefits:**
- Lower latency (instant reaction)
- More efficient (only work when needed)

---

## Backtesting Terms

### Backtesting
Testing a strategy on historical data to estimate how it would have performed.

### Monte Carlo Simulation
Running thousands of simulations with randomness to estimate range of outcomes.

**Example:** Run 10,000 simulated NFL seasons to see profit distribution

### Walk-Forward Analysis
Train model on past data, test on future data, repeat sliding forward through time.

**Example:**
- Train: 2019-2020 data
- Test: 2021 data
- Train: 2019-2021 data  
- Test: 2022 data
- Etc.

### Overfitting
When model performs great on historical data but fails on new data. Avoided by:
- Simple models
- Cross-validation
- Holding out test data

---

## Measurement Terms

### ROI (Return on Investment)
Percentage profit/loss on invested capital.

**Formula:** (Profit / Initial Investment) × 100%

**Example:** 
- Invested: $1,000
- Profit: $150
- ROI: 15%

### Win Rate
Percentage of profitable trades.

**Formula:** (Winning Trades / Total Trades) × 100%

**Example:**
- 45 winning trades out of 100
- Win rate: 45%

Note: Win rate alone doesn't indicate profitability. A 40% win rate can be profitable if wins are bigger than losses.

### Average Win / Average Loss
Used to calculate expected value.

**Example:**
- Average win: $60
- Average loss: $40
- Win rate: 40%
- Expected value: (0.40 × $60) - (0.60 × $40) = $24 - $24 = $0 (break-even)

### Brier Score
Measure of probability forecast accuracy. Lower is better.

**Formula:** Average of (forecast - outcome)² across all predictions

**Example:**
- Predicted 70%, outcome was Yes (1): (0.70 - 1)² = 0.09
- Predicted 30%, outcome was No (0): (0.30 - 0)² = 0.09
- Brier = 0.09 (lower = better)

### Calibration
How well your probability estimates match reality.

**Example:** Of all bets you gave 70% probability, did 70% actually happen?
- Well-calibrated: Your percentages match outcomes
- Overconfident: Events happen less often than you predicted
- Underconfident: Events happen more often than you predicted

---

## Project-Specific Terms

### Prescient
The name of this prediction market trading system. Also called "Precog" informally.

### Phase Codenames
Fun sci-fi inspired names for development phases:
- Phase 0: Genesis
- Phase 1: Bootstrap
- Phase 2: Observer
- Phase 3: Nexus
- Phase 4: Oracle
- Phase 5a: Dealer
- Phase 5b: Guardian
- Phase 6: Constellation
- Phase 7: Augment
- Phase 8: Multiverse
- Phase 9: Singularity
- Phase 10: Nexus Prime

### Hot/Warm/Cold Storage
Data retention strategy:
- **Hot:** Last 18 months in active database (fast access)
- **Warm:** 18-42 months in compressed database (slower access)
- **Cold:** 42+ months in S3/Parquet files (archival)

### Demo/Prod/Test Environments
- **Demo:** Kalshi demo API, fake money, safe testing
- **Prod:** Real money trading
- **Test:** Automated testing, auto-rollback

---

**Document Version:** 1.0  
**Last Updated:** October 8, 2025  
**Purpose:** Reference for terminology used throughout the project
