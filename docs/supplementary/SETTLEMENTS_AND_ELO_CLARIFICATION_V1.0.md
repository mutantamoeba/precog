# Settlements Table & Elo Models - Deep Dive Clarification

**Date:** 2025-10-24
**Phase:** 1 (Foundation Complete)
**Purpose:** Answer critical questions about settlements table purpose and Elo model data storage

---

## Question 1: Features_historical Not Needed for Elo in Phase 4?

### Answer: **CORRECT - Elo Does NOT Need features_historical**

**Why Elo is Different:**

Elo is a **recursive** rating system that updates based ONLY on game results:

```python
# Elo calculation (pseudocode)
def update_elo(team_a_rating, team_b_rating, actual_outcome):
    expected_a = 1 / (1 + 10**((team_b_rating - team_a_rating) / 400))
    new_rating_a = team_a_rating + K * (actual_outcome - expected_a)
    return new_rating_a
```

**Elo Inputs:**
- Previous Elo ratings (stored in `probability_models.config`)
- Game outcome (win/loss from `settlements` table or `events.result`)
- K-factor, home advantage (config parameters)

**Elo Does NOT Need:**
- Pre-calculated features (DVOA, EPA, SP+)
- Historical stats (yards per game, turnovers)
- Player-level data
- Weather, injuries, etc.

---

## Tables Needed for Elo Models (Phase 4)

### Core Tables Already Exist

**1. probability_models** - Store Elo configurations
```sql
INSERT INTO probability_models (
    model_name, model_version, model_type, sport, config, status
) VALUES (
    'elo_nfl', 'v1.0', 'elo', 'nfl',
    '{
        "k_factor": 30,
        "initial_rating": 1500,
        "home_advantage": 65,
        "elo_ratings": {
            "KC": 1650,
            "SF": 1620,
            "BUF": 1610,
            ...
        }
    }'::JSONB,
    'active'
);
```

**Key Point:** `config.elo_ratings` is a JSONB object storing current Elo rating for each team

**2. events** - Game results for Elo updates
```sql
SELECT event_id, home_team, away_team, result
FROM events
WHERE sport = 'nfl'
AND status = 'final'
ORDER BY end_time;
```

**3. settlements** - Market outcomes for model validation
```sql
SELECT market_id, outcome, created_at
FROM settlements
WHERE market_id LIKE 'MKT-NFL-%'
ORDER BY created_at;
```

### Elo Workflow (Phase 4)

**Step 1: Initialize Elo Ratings**
```python
# Create elo_nfl_v1.0 model
config = {
    "k_factor": 30,
    "initial_rating": 1500,
    "home_advantage": 65,
    "elo_ratings": {
        # All NFL teams start at 1500
        "KC": 1500, "SF": 1500, ...
    }
}
insert_probability_model('elo_nfl', 'v1.0', config)
```

**Step 2: Update Elo After Each Game**
```python
# Game: Chiefs beat 49ers
event = get_event('EVT-NFL-KC-SF-2024-10-20')
model = get_model('elo_nfl', 'v1.0')

# Calculate new ratings
kc_new = update_elo(
    model.config['elo_ratings']['KC'],  # 1650
    model.config['elo_ratings']['SF'],  # 1620
    actual_outcome=1  # KC won
)
sf_new = update_elo(
    model.config['elo_ratings']['SF'],  # 1620
    model.config['elo_ratings']['KC'],  # 1650
    actual_outcome=0  # SF lost
)

# Create NEW model version with updated ratings
model.config['elo_ratings']['KC'] = kc_new  # 1658
model.config['elo_ratings']['SF'] = sf_new  # 1612
insert_probability_model('elo_nfl', 'v1.1', model.config)

# Mark v1.0 as superseded
update_model_status('elo_nfl', 'v1.0', 'deprecated')
```

**Step 3: Generate Probabilities for Markets**
```python
# Predict: Bills vs Dolphins
model = get_active_model('elo_nfl')
bills_rating = model.config['elo_ratings']['BUF']  # 1610
dolphins_rating = model.config['elo_ratings']['MIA']  # 1480

# Calculate win probability
prob_bills_win = 1 / (1 + 10**((dolphins_rating - bills_rating) / 400))
# = 1 / (1 + 10**(-130/400)) = 0.684 (68.4%)

# Insert edge if market is mispriced
if market_price < prob_bills_win - 0.05:  # 5% edge
    insert_edge(market_id, model.model_id, prob_bills_win, ...)
```

### Tables NOT Needed for Elo

❌ **feature_definitions** - Elo doesn't use features
❌ **features_historical** - Elo doesn't use historical stats
❌ **training_datasets** - Elo has no training phase (recursive updates)
❌ **model_training_runs** - Elo has no training runs

### New Tables Needed for Elo (Phase 4)

**teams table** - Team metadata for Elo tracking

```sql
CREATE TABLE teams (
    team_id VARCHAR PRIMARY KEY,         -- 'KC', 'SF', 'BUF', etc.
    team_name VARCHAR NOT NULL,          -- 'Kansas City Chiefs'
    sport VARCHAR NOT NULL,              -- 'nfl', 'nba', 'mlb'
    conference VARCHAR,                  -- 'AFC', 'NFC'
    division VARCHAR,                    -- 'AFC West'
    external_espn_id VARCHAR,            -- ESPN team ID for data fetching
    external_kalshi_id VARCHAR,          -- Kalshi team ID
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_teams_sport ON teams(sport);
```

**Why needed:**
- Elo ratings are keyed by team_id
- Provides team metadata for display and lookups
- Links to external APIs (ESPN, Kalshi) for data fetching

**players table** - NOT needed for Elo (Phase 9 for ML models)

---

## Question 2: Settlements Table - Deep Dive

### What is settlements Table?

**settlements = Market Truth Table**

One row per market when it officially settles (final outcome determined).

**Schema:**
```sql
CREATE TABLE settlements (
    settlement_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),
    platform_id VARCHAR REFERENCES platforms(platform_id),
    outcome VARCHAR NOT NULL,            -- 'yes' or 'no'
    payout DECIMAL(10,4),                -- $1.00 for winners, $0.00 for losers
    external_settlement_id VARCHAR,      -- Kalshi settlement event ID
    settlement_timestamp TIMESTAMP,      -- When Kalshi settled it
    api_response JSONB,                  -- Raw Kalshi response
    created_at TIMESTAMP DEFAULT NOW()
);
```

### outcome vs. payout - What's the Difference?

**outcome** - Which side won the market

- Values: `'yes'` or `'no'`
- Determines WHO won (not HOW MUCH)
- Example: Market "Will Chiefs win?" → `outcome = 'yes'` (Chiefs won)

**payout** - How much each winning contract pays

- Values: Usually `$1.00` for winners, `$0.00` for losers
- Could vary for exotic markets (e.g., scalar markets)
- Example: Binary market → `payout = 1.00` per winning contract

**Why both?**
- `outcome` tells you WHICH side won
- `payout` tells you HOW MUCH each contract is worth

**Example:**
```sql
-- Market: "Will Chiefs beat Bills?"
INSERT INTO settlements (market_id, outcome, payout)
VALUES ('MKT-NFL-KC-BUF-YES', 'yes', 1.00);

-- Interpretation:
-- outcome='yes' → Chiefs won (YES side won the market)
-- payout=1.00 → Each YES contract pays $1.00
```

---

## Question 3: Does settlements Store MY Trade Results?

### Answer: **NO - settlements Stores MARKET Results Only**

**settlements is NOT:**
- ❌ A log of your trades
- ❌ A record of your P&L
- ❌ Position-specific data

**settlements IS:**
- ✅ Official market outcomes from Kalshi API
- ✅ One row per market (regardless of how many positions you have)
- ✅ Truth table for calculating P&L of positions held to settlement

### Example Scenarios

**Scenario 1: You NEVER Entered the Market**

```sql
-- Market: "Will Dolphins win Super Bowl?"
INSERT INTO settlements (market_id, outcome, payout)
VALUES ('MKT-NFL-MIA-SUPERBOWL', 'no', 0.00);
```

**You:** Never traded this market
**settlements row:** Still created (market settled even though you didn't trade)
**Your positions:** Zero
**Your P&L:** $0 (didn't participate)

**Scenario 2: You Exited Early**

```sql
-- 1. You bought YES at $0.60
INSERT INTO positions (market_id, side, entry_price, quantity, status)
VALUES ('MKT-NFL-KC-WIN', 'yes', 0.60, 100, 'open');

-- 2. You sold YES at $0.75 (early exit, before game ends)
INSERT INTO trades (position_id, side, price, quantity)
VALUES (123, 'sell', 0.75, 100);

UPDATE positions SET status = 'closed', exit_price = 0.75
WHERE position_id = 123;

INSERT INTO position_exits (position_id, exit_condition, quantity_exited, exit_price)
VALUES (123, 'profit_target', 100, 0.75);

-- 3. Market settles later (Chiefs won)
INSERT INTO settlements (market_id, outcome, payout)
VALUES ('MKT-NFL-KC-WIN', 'yes', 1.00);
```

**settlements row:** Created (market outcome = yes, Chiefs won)
**Your position:** Already closed (exited at $0.75)
**Your P&L:** Calculated from **position_exits**, NOT settlements
  - Entry: 100 × $0.60 = $60
  - Exit: 100 × $0.75 = $75
  - Profit: $75 - $60 = **$15**

**Do you check settlements?** NO - You already have your P&L from the early exit trade

**Scenario 3: You Held to Settlement**

```sql
-- 1. You bought YES at $0.60
INSERT INTO positions (market_id, side, entry_price, quantity, status)
VALUES ('MKT-NFL-KC-WIN', 'yes', 0.60, 100, 'open');

-- 2. Game ends, market settles (Chiefs won)
INSERT INTO settlements (market_id, outcome, payout)
VALUES ('MKT-NFL-KC-WIN', 'yes', 1.00);

-- 3. Your position settles
UPDATE positions
SET status = 'settled',
    realized_pnl = (1.00 - 0.60) * 100  -- $40 profit
WHERE position_id = 123;
```

**settlements row:** Created (outcome = yes)
**Your position:** Held to settlement
**Your P&L:** Calculated from **settlements.outcome** + your entry price
  - Entry: 100 × $0.60 = $60
  - Settlement: 100 × $1.00 = $100 (you held YES, outcome = yes)
  - Profit: $100 - $60 = **$40**

**Do you check settlements?** YES - You need `settlements.outcome` to know if you won

---

## Question 4: Why Check position_exits if settlements Has Results?

### Answer: **Because Early Exits Don't Care About Settlement**

**Two P&L Calculation Paths:**

### Path 1: Early Exit (Use position_exits)

```python
def calculate_pnl_early_exit(position):
    """Position was closed before market settled"""
    exit_record = position_exits.get(position_id)

    cost_basis = position.quantity * position.entry_price
    exit_proceeds = exit_record.quantity_exited * exit_record.exit_price

    return exit_proceeds - cost_basis
```

**Data Sources:**
- `positions.entry_price` (what you paid)
- `position_exits.exit_price` (what you sold for)
- `settlements` table - **IGNORED** (you exited before settlement)

### Path 2: Held to Settlement (Use settlements)

```python
def calculate_pnl_held_to_settlement(position, settlement):
    """Position was held until market settled"""
    cost_basis = position.quantity * position.entry_price

    # Determine if you won based on settlement outcome
    if position.side == settlement.outcome:
        settlement_proceeds = position.quantity * settlement.payout  # Usually $1.00
    else:
        settlement_proceeds = 0  # Lost, contracts worth $0

    return settlement_proceeds - cost_basis
```

**Data Sources:**
- `positions.entry_price` (what you paid)
- `settlements.outcome` (did your side win?)
- `settlements.payout` (how much do winners get?)

### Why Both Paths?

**Example: Position Lifecycle**

```
Position 123: Buy 100 YES @ $0.60 on "Chiefs win?"

Path A (Early Exit):
  t=0:     Buy YES @ $0.60 → position_id=123, status='open'
  t=1hr:   Price moves to $0.75
  t=1hr:   Sell YES @ $0.75 → position_exits record, status='closed'
  P&L:     ($0.75 - $0.60) × 100 = $15 profit ✅

  [Market settles later → outcome='yes']
  → You DON'T get $1.00 payout (already exited!)
  → Your P&L stays $15 (from early exit)

Path B (Held to Settlement):
  t=0:     Buy YES @ $0.60 → position_id=124, status='open'
  t=1hr:   Price moves to $0.75
  t=1hr:   [You hold, don't sell]
  t=3hr:   Game ends, Chiefs win
  t=3hr:   Market settles → outcome='yes', payout=$1.00
  t=3hr:   Your position settles → status='settled'
  P&L:     ($1.00 - $0.60) × 100 = $40 profit ✅
```

**Key Insight:** Once you exit, settlements doesn't matter to YOUR P&L (but still created for market record)

---

## Question 5: What Does settlements Store in Different Scenarios?

### Scenario Matrix

| Market | You Entered? | You Held to Settlement? | settlements Row Created? | settlements.outcome | settlements.payout | How Your P&L Calculated |
|--------|--------------|-------------------------|--------------------------|---------------------|-------------------|------------------------|
| MKT-A | ❌ No | N/A | ✅ Yes | 'yes' | 1.00 | N/A (didn't trade) |
| MKT-B | ✅ Yes | ❌ No (exited early) | ✅ Yes | 'no' | 0.00 | position_exits.exit_price |
| MKT-C | ✅ Yes | ✅ Yes | ✅ Yes | 'yes' | 1.00 | settlements.outcome + payout |
| MKT-D | ✅ Yes (2 positions) | ⚠️ Mixed (1 exited, 1 held) | ✅ Yes | 'yes' | 1.00 | Position 1: exit_price, Position 2: settlement |

### Detailed Examples

**MKT-A: Market You Never Entered**

```sql
-- Market settles
INSERT INTO settlements (market_id, outcome, payout)
VALUES ('MKT-NFL-NYJ-WIN', 'no', 0.00);  -- Jets lost

-- Your positions table
SELECT * FROM positions WHERE market_id = 'MKT-NFL-NYJ-WIN';
-- Result: 0 rows (you didn't trade)

-- Your P&L: $0
```

**MKT-B: You Exited Early, Market Settles Later**

```sql
-- You bought NO at $0.40, sold at $0.50 (early exit)
-- Position is CLOSED

-- Market settles later
INSERT INTO settlements (market_id, outcome, payout)
VALUES ('MKT-NFL-DEN-WIN', 'no', 0.00);  -- Broncos lost, NO wins

-- Your P&L calculation:
-- Source: position_exits table (exit_price = $0.50)
-- P&L: ($0.50 - $0.40) × 100 = $10
-- settlements.outcome is IGNORED (you already exited)
```

**MKT-C: You Held to Settlement**

```sql
-- You bought YES at $0.65, held until game ends

-- Market settles
INSERT INTO settlements (market_id, outcome, payout)
VALUES ('MKT-NFL-KC-WIN', 'yes', 1.00);  -- Chiefs won

-- Your P&L calculation:
-- Source: settlements table (outcome='yes', you held YES)
-- P&L: ($1.00 - $0.65) × 100 = $35
```

**MKT-D: Mixed (2 Positions, 1 Exited, 1 Held)**

```sql
-- Position 1: Bought YES at $0.50, sold at $0.70 (early exit)
INSERT INTO position_exits (position_id, exit_price, quantity_exited)
VALUES (101, 0.70, 50);

-- Position 2: Bought YES at $0.60, held to settlement
-- (still open when market settles)

-- Market settles
INSERT INTO settlements (market_id, outcome, payout)
VALUES ('MKT-NFL-BUF-WIN', 'yes', 1.00);  -- Bills won

-- Your P&L calculation:
-- Position 1 P&L: ($0.70 - $0.50) × 50 = $10 (from exit_price)
-- Position 2 P&L: ($1.00 - $0.60) × 50 = $20 (from settlement)
-- Total P&L: $10 + $20 = $30
```

---

## Summary Table: Data Sources for P&L

| Position Status | P&L Source | Uses settlements? | Uses position_exits? |
|----------------|------------|-------------------|---------------------|
| **open** | Unrealized (current_price) | ❌ No | ❌ No |
| **closed** (exited early) | Realized (exit trades) | ❌ No | ✅ Yes |
| **settled** (held to end) | Realized (market outcome) | ✅ Yes | ❌ No |

---

## Key Takeaways

### 1. Elo Models (Phase 4)

✅ **DO need:**
- `probability_models` table (store Elo ratings in config JSONB)
- `events` table (game results for Elo updates)
- `settlements` table (validate Elo predictions)
- **NEW: `teams` table** (team metadata, Elo tracking)

❌ **DO NOT need:**
- `features_historical` (Elo doesn't use features)
- `feature_definitions` (Elo doesn't use features)
- `training_datasets` (Elo has no training)
- `model_training_runs` (Elo has no training)

### 2. settlements Table

**Purpose:** Market truth table (ONE row per market)

**NOT:** Position-specific P&L tracking

**Stores:**
- `outcome`: Which side won ('yes' or 'no')
- `payout`: How much winners get (usually $1.00)
- `external_settlement_id`: Kalshi's settlement event ID
- `settlement_timestamp`: When Kalshi settled it

**Created for:**
- ✅ Every market that settles (even if you didn't trade)
- ✅ Markets you exited early (still creates row)
- ✅ Markets you held to settlement

**Used for:**
- ✅ Calculating P&L for positions held to settlement
- ✅ Validating model predictions (accuracy, calibration)
- ❌ NOT used for positions closed early (use position_exits instead)

### 3. Two P&L Paths

**Early Exit:**
```
Entry Price → Exit Price → P&L
(from positions) (from position_exits)
```

**Held to Settlement:**
```
Entry Price → Settlement Outcome → Payout → P&L
(from positions) (from settlements) (from settlements)
```

---

**Questions answered. Ready to implement Elo models in Phase 4 and properly use settlements table!**
