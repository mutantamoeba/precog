# Elo and Settlements Architecture Analysis

---
**Version:** 1.0
**Date:** 2025-10-24
**Status:** ✅ Analysis Complete
**Purpose:** Evaluate architecture decisions for Elo data sources, Elo ratings storage, and settlements table design
**Related:** [SETTLEMENTS_AND_ELO_CLARIFICATION_V1.0.md](SETTLEMENTS_AND_ELO_CLARIFICATION_V1.0.md), [DATABASE_SCHEMA_SUMMARY_V1.6.md](database/DATABASE_SCHEMA_SUMMARY_V1.6.md)

---

## Executive Summary

This document analyzes three key architecture questions:

1. **Elo Data Source**: Should we use `game_states` (ESPN/external) vs `settlements` (Kalshi API) vs `events.result` for determining game winners?
2. **Elo Ratings Storage**: Should we use `probability_models.config` (JSONB) vs dedicated `teams` table for storing Elo ratings?
3. **Settlements Architecture**: Should we keep `settlements` as separate table vs add columns to `markets` table?

**TL;DR Recommendations:**
- ✅ **Use `game_states` for Elo updates** (data independence, no API dependency)
- ✅ **Use `teams` table for Elo ratings** (simpler queries, better performance, clearer semantics)
- ✅ **Keep `settlements` as separate table** (normalization, historical tracking, multi-platform support)

---

## Question 1: Elo Data Source - Where Should We Get Game Results?

### Background
Elo rating systems need to know **who won each game** to update team ratings. We have three potential data sources:

1. **`game_states` table** - Live game data from ESPN/external feeds
2. **`settlements` table** - Market settlement data from Kalshi API
3. **`events.result` JSONB** - Event outcome data

### Option A: game_states (ESPN/External Feeds)

```sql
-- game_states schema
CREATE TABLE game_states (
    game_state_id SERIAL PRIMARY KEY,
    event_id VARCHAR REFERENCES events(event_id),
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INT,              -- Direct score access
    away_score INT,              -- Direct score access
    status VARCHAR,              -- 'final' = game complete
    row_current_ind BOOLEAN
);

-- Query to get game result
SELECT
    home_team,
    away_team,
    home_score,
    away_score,
    CASE
        WHEN home_score > away_score THEN 'home'
        WHEN away_score > home_score THEN 'away'
        ELSE 'tie'
    END AS winner
FROM game_states
WHERE event_id = 'EVT-NFL-KC-BUF-2025-01-26'
AND status = 'final'
AND row_current_ind = TRUE;
```

**Pros:**
- ✅ **Data independence** - Not dependent on Kalshi API or markets existing
- ✅ **Source of truth** - Direct score data from authoritative sports feeds (ESPN)
- ✅ **Works for all games** - Not limited to games we traded on
- ✅ **Faster availability** - Score available immediately when game ends
- ✅ **No market dependency** - Can calculate Elo even if no market was created
- ✅ **Clear semantics** - home_score vs away_score is unambiguous

**Cons:**
- ❌ **Additional data feed** - Need to maintain ESPN/external feed integration
- ❌ **Potential discrepancies** - Score feeds could disagree with Kalshi settlements (rare but possible)

### Option B: settlements (Kalshi API)

```sql
-- settlements schema
CREATE TABLE settlements (
    settlement_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),
    outcome VARCHAR NOT NULL,            -- 'yes', 'no'
    payout DECIMAL(10,4),
    external_settlement_id VARCHAR       -- NEW in migration 008
);

-- Query to get game result (COMPLEX)
-- Need to find "Will [team] win?" market and check outcome
SELECT
    m.title,
    s.outcome,
    -- Parse team name from market title
    -- Determine winner based on outcome
FROM settlements s
JOIN markets m ON s.market_id = m.market_id
WHERE m.event_id = 'EVT-NFL-KC-BUF-2025-01-26'
AND m.title LIKE '%win%';  -- Fragile string parsing
```

**Pros:**
- ✅ **Kalshi is authoritative** - Official settlement for betting purposes
- ✅ **Already integrated** - Already fetching settlement data for P&L

**Cons:**
- ❌ **Market dependency** - Can only update Elo for games we had markets on
- ❌ **Ambiguous mapping** - settlement.outcome='yes' doesn't directly tell us which team won
- ❌ **String parsing required** - Must parse market.title to determine which team
- ❌ **Fragile logic** - Market title format changes break Elo updates
- ❌ **Limited coverage** - Kalshi may not have markets for all games
- ❌ **Delayed availability** - Settlement happens after official result (additional lag)

### Option C: events.result JSONB

```sql
-- events schema
CREATE TABLE events (
    event_id VARCHAR PRIMARY KEY,
    status VARCHAR,              -- 'final'
    result JSONB,                -- Final outcome data
);

-- Query to get game result
SELECT
    result->>'winner' AS winner,
    result->>'home_score' AS home_score,
    result->>'away_score' AS away_score
FROM events
WHERE event_id = 'EVT-NFL-KC-BUF-2025-01-26'
AND status = 'final';
```

**Pros:**
- ✅ **Structured storage** - events.result designed for outcome data
- ✅ **Event-level semantics** - Result naturally belongs to event, not game_states version

**Cons:**
- ❌ **JSONB ambiguity** - Schema not enforced, field names could vary
- ❌ **Duplication** - Same data stored in both events.result and game_states
- ❌ **Less queryable** - JSONB harder to query than native columns

### Recommendation: ✅ Use game_states

**Rationale:**
1. **Data Independence** - Elo model works regardless of Kalshi market coverage
2. **Clear Semantics** - `home_score > away_score` is unambiguous, no string parsing
3. **Source of Truth** - ESPN feeds are authoritative for sports scores
4. **Scalability** - Can calculate Elo for all teams, not just games we traded on
5. **Future-proof** - If we add more platforms (Polymarket, etc.), game scores remain consistent

**Implementation:**
```sql
-- Elo update query (simple and clear)
SELECT
    gs.home_team,
    gs.away_team,
    gs.home_score,
    gs.away_score,
    e.event_id,
    e.start_time
FROM game_states gs
JOIN events e ON gs.event_id = e.event_id
WHERE gs.status = 'final'
AND gs.row_current_ind = TRUE
AND NOT EXISTS (
    -- Avoid duplicate processing
    SELECT 1 FROM elo_rating_history
    WHERE event_id = e.event_id
)
ORDER BY e.start_time;
```

**Cross-validation:**
- Use settlements data as a **validation check** (not primary source)
- Flag discrepancies between game_states winner and settlements outcome
- Alert if ESPN score disagrees with Kalshi settlement

---

## Question 2: Elo Ratings Storage - Where Should We Store Team Ratings?

### Background
Elo ratings are **mutable values** that change after every game. We have two storage options:

1. **`probability_models.config` JSONB** - Store ratings in model config
2. **`teams` table** - Dedicated table with current_elo_rating column

### Option A: probability_models.config JSONB (Current Design)

```sql
-- probability_models schema
CREATE TABLE probability_models (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR NOT NULL,         -- 'elo_nfl'
    model_version VARCHAR NOT NULL,      -- 'v1.0'
    config JSONB NOT NULL,               -- {"KC": 1580, "BUF": 1620, ...}
    status VARCHAR DEFAULT 'active'
);

-- Update Elo rating (REQUIRES NEW VERSION)
-- Option 1: Update existing version (violates immutability)
UPDATE probability_models
SET config = jsonb_set(config, '{KC}', '1590')
WHERE model_name = 'elo_nfl' AND model_version = 'v1.0';

-- Option 2: Create new version for every game (absurd)
INSERT INTO probability_models (model_name, model_version, config)
VALUES ('elo_nfl', 'v1.1', '{"KC": 1590, "BUF": 1610, ...}');
```

**Pros:**
- ✅ **Fits existing pattern** - Uses existing probability_models table
- ✅ **Versioning built-in** - Can track rating changes over time (if creating versions)

**Cons:**
- ❌ **Violates immutability** - `config` field supposed to be IMMUTABLE, but Elo ratings must change
- ❌ **Semantic mismatch** - probability_models designed for MODEL PARAMETERS (k_factor, initial_rating), not TEAM RATINGS
- ❌ **Version explosion** - Creating new version for every game = 256+ versions per NFL season
- ❌ **JSONB query complexity** - `config->>'KC'` harder than `teams.current_elo_rating`
- ❌ **No indexing** - Can't index JSONB values efficiently for range queries
- ❌ **Unclear ownership** - Elo ratings are TEAM attributes, not MODEL attributes

### Option B: teams Table (Recommended)

```sql
-- NEW teams table
CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    team_code VARCHAR(10) NOT NULL,      -- 'KC', 'BUF', 'SF'
    team_name VARCHAR NOT NULL,          -- 'Kansas City Chiefs'
    sport VARCHAR NOT NULL,              -- 'nfl', 'nba'

    -- External IDs
    espn_team_id VARCHAR,
    kalshi_team_id VARCHAR,

    -- Current Elo Rating (MUTABLE)
    current_elo_rating DECIMAL(10,2),

    -- Metadata
    conference VARCHAR,                   -- 'AFC', 'NFC'
    division VARCHAR,                     -- 'West', 'East'
    metadata JSONB,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()

    -- ❌ NO row_current_ind (teams are mutable entities, not versioned)
);

CREATE INDEX idx_teams_code ON teams(team_code);
CREATE INDEX idx_teams_sport ON teams(sport);
CREATE INDEX idx_teams_elo_rating ON teams(current_elo_rating);

-- Historical ratings tracking (separate table)
CREATE TABLE elo_rating_history (
    history_id SERIAL PRIMARY KEY,
    team_id INT REFERENCES teams(team_id),
    event_id VARCHAR REFERENCES events(event_id),
    rating_before DECIMAL(10,2),
    rating_after DECIMAL(10,2),
    opponent_team_id INT REFERENCES teams(team_id),
    game_result VARCHAR,                  -- 'win', 'loss', 'tie'
    k_factor DECIMAL(10,2),               -- K-factor used for this update
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_elo_history_team ON elo_rating_history(team_id);
CREATE INDEX idx_elo_history_event ON elo_rating_history(event_id);
CREATE INDEX idx_elo_history_created ON elo_rating_history(created_at);
```

**Update Elo rating (clean and simple):**
```sql
-- Record historical rating
INSERT INTO elo_rating_history (team_id, event_id, rating_before, rating_after, opponent_team_id, game_result, k_factor)
VALUES (1, 'EVT-NFL-KC-BUF-2025-01-26', 1580, 1590, 2, 'win', 30);

-- Update current rating
UPDATE teams
SET current_elo_rating = 1590, updated_at = NOW()
WHERE team_code = 'KC';
```

**Query Elo ratings (simple):**
```sql
-- Get current ratings
SELECT team_code, team_name, current_elo_rating
FROM teams
WHERE sport = 'nfl'
ORDER BY current_elo_rating DESC;

-- Get rating history for team
SELECT
    h.created_at,
    h.rating_before,
    h.rating_after,
    h.game_result,
    e.title AS game
FROM elo_rating_history h
JOIN events e ON h.event_id = e.event_id
WHERE h.team_id = 1
ORDER BY h.created_at DESC;

-- Calculate edge using Elo
SELECT
    m.market_id,
    m.title,
    t_home.current_elo_rating AS home_elo,
    t_away.current_elo_rating AS away_elo,
    -- Elo formula: P(win) = 1 / (1 + 10^((Elo_opp - Elo_team)/400))
    1.0 / (1 + POW(10, (t_away.current_elo_rating - t_home.current_elo_rating) / 400.0)) AS elo_win_probability,
    m.yes_price AS market_price,
    (1.0 / (1 + POW(10, (t_away.current_elo_rating - t_home.current_elo_rating) / 400.0))) - m.yes_price AS edge
FROM markets m
JOIN events e ON m.event_id = e.event_id
JOIN game_states gs ON e.event_id = gs.event_id AND gs.row_current_ind = TRUE
JOIN teams t_home ON gs.home_team = t_home.team_code
JOIN teams t_away ON gs.away_team = t_away.team_code
WHERE m.status = 'open'
AND e.status = 'scheduled';
```

**Pros:**
- ✅ **Clear semantics** - Elo ratings are TEAM attributes, stored in teams table
- ✅ **Simple queries** - `teams.current_elo_rating` vs `config->>'team'`
- ✅ **Proper indexing** - Can index current_elo_rating for range queries
- ✅ **Mutable design** - No immutability conflict, designed for updates
- ✅ **Historical tracking** - elo_rating_history provides full audit trail
- ✅ **Extensibility** - Easy to add other team attributes (win_rate, recent_form, etc.)
- ✅ **Performance** - Native column faster than JSONB extraction
- ✅ **Foreign keys** - Can FK to teams from other tables

**Cons:**
- ❌ **New table required** - Must create teams table (but we need it anyway for team metadata)
- ❌ **Two tables instead of one** - teams + elo_rating_history vs single probability_models

### Recommendation: ✅ Use teams Table

**Rationale:**
1. **Semantic Correctness** - Elo ratings are TEAM attributes, not MODEL attributes
2. **Immutability Preservation** - Keeps probability_models.config IMMUTABLE as designed
3. **Clear Separation** - probability_models stores MODEL PARAMETERS (k_factor=30), teams stores TEAM RATINGS (KC=1580)
4. **Simpler Queries** - Native columns easier than JSONB extraction
5. **Better Performance** - Indexed DECIMAL column faster than JSONB access
6. **Future Needs** - teams table needed anyway for team metadata, external IDs, conference/division

**probability_models.config should store:**
```json
{
  "k_factor": 30,
  "initial_rating": 1500,
  "home_field_advantage": 65,
  "regression_to_mean": 0.95
}
```

**teams.current_elo_rating should store:**
```
KC: 1580
BUF: 1620
SF: 1545
...
```

---

## Question 3: Settlements Architecture - Separate Table or Markets Columns?

### Background
Settlements represent the **final outcome** of a market. We have two architectural options:

1. **Separate `settlements` table** (current design)
2. **Add columns to `markets` table** (denormalized)

### Option A: Separate settlements Table (Current Design)

```sql
-- settlements schema
CREATE TABLE settlements (
    settlement_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),
    platform_id VARCHAR REFERENCES platforms(platform_id),
    outcome VARCHAR NOT NULL,            -- 'yes', 'no'
    payout DECIMAL(10,4),
    external_settlement_id VARCHAR,      -- NEW in migration 008
    settlement_timestamp TIMESTAMP,      -- NEW in migration 008
    api_response JSONB,                  -- NEW in migration 008
    created_at TIMESTAMP DEFAULT NOW()
);

-- markets schema (simplified)
CREATE TABLE markets (
    market_id VARCHAR PRIMARY KEY,
    status VARCHAR,                      -- 'open', 'closed', 'settled'
    settlement_value DECIMAL(10,4),      -- Final value (if settled)
    row_current_ind BOOLEAN
);
```

**Relationship:**
- One market can have **one settlement** (1:1 relationship after settlement)
- But during market lifecycle: markets row exists BEFORE settlement
- settlements record is append-only (created once, never updated)

**Pros:**
- ✅ **Normalization** - Settlement data stored once, no duplication
- ✅ **Clear lifecycle** - Market exists → settles → settlement record created
- ✅ **Historical tracking** - settlements table is append-only audit trail
- ✅ **Multi-platform support** - Different platforms may settle differently (see below)
- ✅ **Rich settlement data** - Can store external_settlement_id, api_response, settlement_timestamp
- ✅ **Query clarity** - `SELECT * FROM settlements` gets all settlements across all markets
- ✅ **Referential integrity** - FK ensures settlement references valid market

**Multi-platform scenario:**
```sql
-- Market exists on both Kalshi and Polymarket
INSERT INTO markets (market_id, platform_id, ticker, status)
VALUES
    ('KALSHI-NFL-KC-WIN', 'kalshi', 'NFL-KC-WIN', 'open'),
    ('POLY-NFL-KC-WIN', 'polymarket', 'nfl-kc-win', 'open');

-- Both settle (potentially at different times, different outcomes due to dispute/resolution differences)
INSERT INTO settlements (market_id, platform_id, outcome, settlement_timestamp)
VALUES
    ('KALSHI-NFL-KC-WIN', 'kalshi', 'yes', '2025-01-26 20:00:00'),
    ('POLY-NFL-KC-WIN', 'polymarket', 'yes', '2025-01-26 20:15:00');  -- 15 min delay
```

**Cons:**
- ❌ **Join required** - Must JOIN markets + settlements to get complete picture
- ❌ **Two tables** - More complex schema than single table

### Option B: Add Columns to markets Table

```sql
-- markets schema (denormalized)
CREATE TABLE markets (
    market_id VARCHAR PRIMARY KEY,
    status VARCHAR,

    -- Settlement data (nullable until settled)
    settlement_outcome VARCHAR,          -- 'yes', 'no' (NULL before settlement)
    settlement_payout DECIMAL(10,4),     -- (NULL before settlement)
    settlement_external_id VARCHAR,      -- (NULL before settlement)
    settlement_timestamp TIMESTAMP,      -- (NULL before settlement)
    settlement_api_response JSONB,       -- (NULL before settlement)

    row_current_ind BOOLEAN
);
```

**Pros:**
- ✅ **No join required** - All market data in one table
- ✅ **Simpler schema** - One table instead of two
- ✅ **Atomic updates** - Can update market.status and settlement_* in one transaction

**Cons:**
- ❌ **Denormalization** - Settlement data duplicated if market has multiple versions (SCD Type 2)
- ❌ **Nullable columns** - 5 columns NULL for all unsettled markets (most markets)
- ❌ **SCD Type 2 conflict** - If market updates AFTER settlement, settlement_* copied to new version
- ❌ **Unclear semantics** - Is settlement_outcome part of market state or separate event?
- ❌ **Multi-platform complexity** - Hard to model same event settling differently on different platforms
- ❌ **Historical queries harder** - "All settlements last month" requires `WHERE settlement_timestamp IS NOT NULL`

**SCD Type 2 problem example:**
```sql
-- Market settles
UPDATE markets
SET status = 'settled', settlement_outcome = 'yes', settlement_payout = 1.00
WHERE market_id = 'MKT-NFL-KC-WIN' AND row_current_ind = TRUE;

-- Later, market metadata updated (e.g., Kalshi fixes title typo)
-- Must create new version due to SCD Type 2
UPDATE markets SET row_current_ind = FALSE, row_end_ts = NOW()
WHERE market_id = 'MKT-NFL-KC-WIN' AND row_current_ind = TRUE;

INSERT INTO markets (market_id, title, status, settlement_outcome, settlement_payout, row_current_ind)
VALUES ('MKT-NFL-KC-WIN', 'Corrected Title', 'settled', 'yes', 1.00, TRUE);
-- Settlement data duplicated across versions!
```

### Recommendation: ✅ Keep settlements as Separate Table

**Rationale:**
1. **Normalization** - Settlement is a distinct event, should be stored once
2. **SCD Type 2 compatibility** - Avoids duplicating settlement data across market versions
3. **Clear semantics** - "Settlement" is an EVENT that happens to a market, not market STATE
4. **Multi-platform support** - Can model same event settling differently on different platforms
5. **Audit trail** - settlements table is clean append-only log of all settlements
6. **Query clarity** - Easy to query "all settlements" or "unsettled markets"

**Current design is correct:**
- markets.status = 'settled' indicates market is settled
- markets.settlement_value stores final value for quick reference
- settlements table stores complete settlement details (outcome, payout, API response)

**Query patterns:**
```sql
-- Get complete settlement info
SELECT m.*, s.*
FROM markets m
LEFT JOIN settlements s ON m.market_id = s.market_id
WHERE m.market_id = 'MKT-NFL-KC-WIN'
AND m.row_current_ind = TRUE;

-- Get all unsettled markets
SELECT *
FROM markets m
WHERE m.status != 'settled'
AND m.row_current_ind = TRUE
AND NOT EXISTS (
    SELECT 1 FROM settlements s
    WHERE s.market_id = m.market_id
);

-- Calculate P&L using settlements
SELECT
    p.position_id,
    p.quantity,
    p.entry_price,
    s.payout,
    p.quantity * (s.payout - p.entry_price) AS realized_pnl
FROM positions p
JOIN settlements s ON p.market_id = s.market_id
WHERE p.position_id = 123;
```

---

## Implementation Plan

### Phase 4 (Elo Model - Next Phase)

#### 1. Create teams Table
```sql
-- database/migrations/010_create_teams_table.sql
CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    team_code VARCHAR(10) NOT NULL UNIQUE,
    team_name VARCHAR NOT NULL,
    sport VARCHAR NOT NULL,
    espn_team_id VARCHAR,
    kalshi_team_id VARCHAR,
    current_elo_rating DECIMAL(10,2),
    conference VARCHAR,
    division VARCHAR,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_teams_code ON teams(team_code);
CREATE INDEX idx_teams_sport ON teams(sport);
CREATE INDEX idx_teams_elo_rating ON teams(current_elo_rating);
```

#### 2. Create elo_rating_history Table
```sql
-- database/migrations/010_create_teams_table.sql (continued)
CREATE TABLE elo_rating_history (
    history_id SERIAL PRIMARY KEY,
    team_id INT REFERENCES teams(team_id),
    event_id VARCHAR REFERENCES events(event_id),
    rating_before DECIMAL(10,2) NOT NULL,
    rating_after DECIMAL(10,2) NOT NULL,
    opponent_team_id INT REFERENCES teams(team_id),
    game_result VARCHAR NOT NULL,  -- 'win', 'loss', 'tie'
    k_factor DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_elo_history_team ON elo_rating_history(team_id);
CREATE INDEX idx_elo_history_event ON elo_rating_history(event_id);
CREATE INDEX idx_elo_history_created ON elo_rating_history(created_at);
```

#### 3. Seed NFL Teams with Initial Elo Ratings
```sql
-- database/seeds/nfl_teams_initial_elo.sql
INSERT INTO teams (team_code, team_name, sport, current_elo_rating, conference, division) VALUES
('KC', 'Kansas City Chiefs', 'nfl', 1650, 'AFC', 'West'),
('BUF', 'Buffalo Bills', 'nfl', 1620, 'AFC', 'East'),
('SF', 'San Francisco 49ers', 'nfl', 1580, 'NFC', 'West'),
('BAL', 'Baltimore Ravens', 'nfl', 1575, 'AFC', 'North'),
-- ... all 32 teams
('CAR', 'Carolina Panthers', 'nfl', 1350, 'NFC', 'South');
```

#### 4. Create Elo Update Service
```python
# services/elo_service.py
from typing import Tuple
from database.crud_operations import get_connection

class EloService:
    def __init__(self, k_factor: float = 30, initial_rating: float = 1500):
        self.k_factor = k_factor
        self.initial_rating = initial_rating

    def calculate_expected_score(self, rating_a: float, rating_b: float) -> float:
        """Calculate expected score (win probability) for team A."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))

    def update_ratings(
        self,
        winner_rating: float,
        loser_rating: float
    ) -> Tuple[float, float]:
        """
        Update Elo ratings after a game.
        Returns: (new_winner_rating, new_loser_rating)
        """
        expected_winner = self.calculate_expected_score(winner_rating, loser_rating)
        expected_loser = 1.0 - expected_winner

        new_winner_rating = winner_rating + self.k_factor * (1.0 - expected_winner)
        new_loser_rating = loser_rating + self.k_factor * (0.0 - expected_loser)

        return (round(new_winner_rating, 2), round(new_loser_rating, 2))

    def process_game_result(self, event_id: str) -> None:
        """Process a completed game and update team Elo ratings."""
        conn = get_connection()
        cur = conn.cursor()

        # Get game result from game_states
        cur.execute("""
            SELECT
                gs.home_team,
                gs.away_team,
                gs.home_score,
                gs.away_score,
                t_home.team_id AS home_team_id,
                t_home.current_elo_rating AS home_elo,
                t_away.team_id AS away_team_id,
                t_away.current_elo_rating AS away_elo
            FROM game_states gs
            JOIN teams t_home ON gs.home_team = t_home.team_code
            JOIN teams t_away ON gs.away_team = t_away.team_code
            WHERE gs.event_id = %s
            AND gs.status = 'final'
            AND gs.row_current_ind = TRUE
        """, (event_id,))

        result = cur.fetchone()
        if not result:
            raise ValueError(f"Game {event_id} not found or not final")

        (home_team, away_team, home_score, away_score,
         home_team_id, home_elo, away_team_id, away_elo) = result

        # Determine winner
        if home_score > away_score:
            winner_id, winner_elo = home_team_id, home_elo
            loser_id, loser_elo = away_team_id, away_elo
            game_result_home, game_result_away = 'win', 'loss'
        elif away_score > home_score:
            winner_id, winner_elo = away_team_id, away_elo
            loser_id, loser_elo = home_team_id, home_elo
            game_result_home, game_result_away = 'loss', 'win'
        else:
            # Tie - both teams get 0.5 score
            # (simplified - could use draw-adjusted Elo)
            raise NotImplementedError("Tie games not yet supported")

        # Calculate new ratings
        new_winner_elo, new_loser_elo = self.update_ratings(winner_elo, loser_elo)

        # Record history for winner
        cur.execute("""
            INSERT INTO elo_rating_history
            (team_id, event_id, rating_before, rating_after, opponent_team_id, game_result, k_factor)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (winner_id, event_id, winner_elo, new_winner_elo, loser_id,
              'win' if winner_id == home_team_id else 'win', self.k_factor))

        # Record history for loser
        cur.execute("""
            INSERT INTO elo_rating_history
            (team_id, event_id, rating_before, rating_after, opponent_team_id, game_result, k_factor)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (loser_id, event_id, loser_elo, new_loser_elo, winner_id,
              'loss' if loser_id == home_team_id else 'loss', self.k_factor))

        # Update current ratings
        cur.execute("""
            UPDATE teams
            SET current_elo_rating = %s, updated_at = NOW()
            WHERE team_id = %s
        """, (new_winner_elo, winner_id))

        cur.execute("""
            UPDATE teams
            SET current_elo_rating = %s, updated_at = NOW()
            WHERE team_id = %s
        """, (new_loser_elo, loser_id))

        conn.commit()
        cur.close()
        conn.close()
```

#### 5. Store Elo Model Config in probability_models
```sql
-- Elo model configuration (IMMUTABLE parameters)
INSERT INTO probability_models (model_name, model_version, model_type, sport, config, status)
VALUES (
    'elo_nfl',
    'v1.0',
    'elo',
    'nfl',
    '{
        "k_factor": 30,
        "initial_rating": 1500,
        "home_field_advantage": 65,
        "regression_to_mean": 0.95,
        "season_adjustment": 0.33
    }'::JSONB,
    'active'
);
```

**Key Point:** probability_models stores MODEL PARAMETERS (how to calculate Elo), teams table stores TEAM RATINGS (current Elo values).

---

## Summary of Recommendations

| Question | Recommendation | Rationale |
|----------|---------------|-----------|
| **Elo Data Source** | ✅ Use `game_states` (ESPN feeds) | Data independence, clear semantics, no API dependency |
| **Elo Ratings Storage** | ✅ Use `teams` table | Semantic correctness, simpler queries, preserves immutability |
| **Settlements Architecture** | ✅ Keep separate `settlements` table | Normalization, SCD Type 2 compatibility, multi-platform support |

---

## Appendix: Cross-Validation Strategy

### Validate game_states Against settlements

To ensure data integrity, implement cross-validation:

```sql
-- Find discrepancies between game_states and settlements
SELECT
    gs.event_id,
    gs.home_team,
    gs.away_team,
    gs.home_score,
    gs.away_score,
    CASE
        WHEN gs.home_score > gs.away_score THEN gs.home_team
        ELSE gs.away_team
    END AS game_states_winner,
    m.title AS market_title,
    s.outcome AS settlement_outcome,
    'DISCREPANCY' AS flag
FROM game_states gs
JOIN events e ON gs.event_id = e.event_id
JOIN markets m ON e.event_id = m.event_id
JOIN settlements s ON m.market_id = s.market_id
WHERE gs.status = 'final'
AND gs.row_current_ind = TRUE
AND (
    -- Home team won but settlement says 'no' on home team market
    (gs.home_score > gs.away_score AND m.title LIKE CONCAT('%', gs.home_team, '%win%') AND s.outcome = 'no')
    OR
    -- Away team won but settlement says 'no' on away team market
    (gs.away_score > gs.home_score AND m.title LIKE CONCAT('%', gs.away_team, '%win%') AND s.outcome = 'no')
);
```

**Alert on discrepancies:**
- Flag for manual review
- Could indicate score feed error, settlement error, or market title parsing issue
- Log to alerts table with severity='high'

---

**Document Status:** ✅ Complete
**Next Steps:**
1. User approval of recommendations
2. Create migration 010 (teams + elo_rating_history tables)
3. Seed NFL teams with initial Elo ratings
4. Implement EloService in Phase 4
