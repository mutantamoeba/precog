# KALSHI API - Database Schema Considerations (CORRECTED)
**Version**: 2.1  
**Last Updated**: October 8, 2025  
**Changes**: Fixed integer cents → decimal pricing throughout

---

## ⚠️ CRITICAL: Sub-Penny Pricing Implementation

**Kalshi is transitioning to sub-penny pricing.** All database schemas MUST use decimal types.

### Migration Requirements

✅ **Always parse `_dollars` fields from API responses**
```python
# ✅ CORRECT (future-proof):
from decimal import Decimal

yes_bid = Decimal(market["yes_bid_dollars"])  # "0.4275"
no_bid = Decimal(market["no_bid_dollars"])    # "0.5700"

# ❌ WRONG (will break when integer fields deprecated):
yes_bid = market["yes_bid"]  # 43 cents (deprecated)
```

✅ **Store prices as DECIMAL(10,4) in database**

✅ **Use decimal strings in order placement**

✅ **Update odds calculations for sub-penny precision**

---

## Database Schema for Kalshi Markets

### Markets Table

**String Fields:**
```sql
ticker VARCHAR(100) PRIMARY KEY,
event_ticker VARCHAR(100) REFERENCES events(event_ticker),
market_type VARCHAR(50),
title VARCHAR(500) NOT NULL,
subtitle VARCHAR(500),
yes_sub_title VARCHAR(200),
no_sub_title VARCHAR(200),
category VARCHAR(50),
status VARCHAR(20)  -- 'unopened', 'open', 'closed', 'settled'
```

**Timestamp Fields** (DATETIME, UTC):
```sql
open_time TIMESTAMP,
close_time TIMESTAMP,
expiration_time TIMESTAMP,
latest_expiration_time TIMESTAMP,
last_update_time TIMESTAMP,
created_at TIMESTAMP DEFAULT NOW(),
updated_at TIMESTAMP DEFAULT NOW()
```

Create indexes on time-range queries:
```sql
CREATE INDEX idx_markets_close_time ON markets(close_time);
CREATE INDEX idx_markets_expiration ON markets(expiration_time);
```

**Price Fields** (DECIMAL(10,4), 0.0001-0.9999 constraint):
```sql
yes_bid DECIMAL(10,4) NOT NULL,
yes_ask DECIMAL(10,4) NOT NULL,
no_bid DECIMAL(10,4) NOT NULL,
no_ask DECIMAL(10,4) NOT NULL,
last_price DECIMAL(10,4),
previous_price DECIMAL(10,4),

-- Validation constraints
CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999),
CHECK (yes_ask >= 0.0001 AND yes_ask <= 0.9999),
CHECK (no_bid >= 0.0001 AND no_bid <= 0.9999),
CHECK (no_ask >= 0.0001 AND no_ask <= 0.9999)
```

**Why DECIMAL(10,4)?**
- 10 total digits, 4 after decimal point
- Supports values like 0.4275 (42.75¢)
- Allows for prices up to 9999.9999 (future-proof)
- Exact precision (no floating-point errors)

**Volume Metrics:**
```sql
volume BIGINT DEFAULT 0,
volume_24h BIGINT DEFAULT 0,
open_interest INT DEFAULT 0,
liquidity INT DEFAULT 0
```

**Settlement Fields:**
```sql
result VARCHAR(3) CHECK (result IN ('yes', 'no')),
settlement_value DECIMAL(10,4),  -- Payout amount
can_close_early BOOLEAN DEFAULT FALSE
```

**Configuration:**
```sql
notional_value DECIMAL(10,4) DEFAULT 1.0000,  -- Typically $1.00
tick_size DECIMAL(10,6) DEFAULT 0.0100,       -- Minimum price increment
risk_limit_cents INT,                         -- Position size limits
settlement_timer_seconds INT,
rules_primary TEXT,
rules_secondary TEXT
```

**Versioning:**
```sql
row_current_ind BOOLEAN DEFAULT TRUE  -- For price history tracking
```

**Complete Table Definition:**
```sql
CREATE TABLE markets (
    ticker VARCHAR(100) PRIMARY KEY,
    event_ticker VARCHAR(100) REFERENCES events(event_ticker),
    market_type VARCHAR(50),
    title VARCHAR(500) NOT NULL,
    subtitle VARCHAR(500),
    yes_sub_title VARCHAR(200),
    no_sub_title VARCHAR(200),
    category VARCHAR(50),
    status VARCHAR(20),
    
    -- Timestamps
    open_time TIMESTAMP,
    close_time TIMESTAMP,
    expiration_time TIMESTAMP,
    latest_expiration_time TIMESTAMP,
    last_update_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Prices (DECIMAL for sub-penny support)
    yes_bid DECIMAL(10,4) NOT NULL,
    yes_ask DECIMAL(10,4) NOT NULL,
    no_bid DECIMAL(10,4) NOT NULL,
    no_ask DECIMAL(10,4) NOT NULL,
    last_price DECIMAL(10,4),
    previous_price DECIMAL(10,4),
    
    -- Volume
    volume BIGINT DEFAULT 0,
    volume_24h BIGINT DEFAULT 0,
    open_interest INT DEFAULT 0,
    liquidity INT DEFAULT 0,
    
    -- Settlement
    result VARCHAR(3) CHECK (result IN ('yes', 'no')),
    settlement_value DECIMAL(10,4),
    can_close_early BOOLEAN DEFAULT FALSE,
    
    -- Configuration
    notional_value DECIMAL(10,4) DEFAULT 1.0000,
    tick_size DECIMAL(10,6) DEFAULT 0.0100,
    risk_limit_cents INT,
    settlement_timer_seconds INT,
    rules_primary TEXT,
    rules_secondary TEXT,
    
    -- Versioning
    row_current_ind BOOLEAN DEFAULT TRUE,
    
    -- Constraints
    CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999),
    CHECK (yes_ask >= 0.0001 AND yes_ask <= 0.9999),
    CHECK (no_bid >= 0.0001 AND no_bid <= 0.9999),
    CHECK (no_ask >= 0.0001 AND no_ask <= 0.9999),
    CHECK (status IN ('unopened', 'open', 'closed', 'settled'))
);

-- Indexes
CREATE INDEX idx_markets_event ON markets(event_ticker);
CREATE INDEX idx_markets_category ON markets(category);
CREATE INDEX idx_markets_status ON markets(status);
CREATE INDEX idx_markets_current ON markets(row_current_ind) WHERE row_current_ind = TRUE;
CREATE INDEX idx_markets_close_time ON markets(close_time);
```

---

## Orders Table

**String Fields:**
```sql
order_id VARCHAR(100) PRIMARY KEY,
client_order_id VARCHAR(64),  -- For idempotency
ticker VARCHAR(100) REFERENCES markets(ticker),
side VARCHAR(3) CHECK (side IN ('yes', 'no')),
action VARCHAR(4) CHECK (action IN ('buy', 'sell')),
type VARCHAR(10) CHECK (type IN ('limit', 'market')),
status VARCHAR(20)  -- 'pending', 'resting', 'executed', 'canceled'
```

**Count Fields:**
```sql
initial_count INT NOT NULL,
fill_count INT DEFAULT 0,
remaining_count INT,
queue_position INT  -- Position in orderbook
```

**Price Fields (DECIMAL for sub-penny):**
```sql
yes_price DECIMAL(10,4),
no_price DECIMAL(10,4)
```

**Cost Tracking (DECIMAL for sub-penny fees):**
```sql
maker_fees DECIMAL(10,4) DEFAULT 0,
taker_fees DECIMAL(10,4) DEFAULT 0,
maker_fill_cost DECIMAL(10,4) DEFAULT 0,
taker_fill_cost DECIMAL(10,4) DEFAULT 0
```

**Timestamps:**
```sql
created_time TIMESTAMP DEFAULT NOW(),
expiration_time TIMESTAMP,
last_update_time TIMESTAMP DEFAULT NOW()
```

**Complete Table Definition:**
```sql
CREATE TABLE orders (
    order_id VARCHAR(100) PRIMARY KEY,
    client_order_id VARCHAR(64),
    ticker VARCHAR(100) REFERENCES markets(ticker),
    
    -- Order details
    side VARCHAR(3) CHECK (side IN ('yes', 'no')),
    action VARCHAR(4) CHECK (action IN ('buy', 'sell')),
    type VARCHAR(10) CHECK (type IN ('limit', 'market')),
    status VARCHAR(20),
    
    -- Quantities
    initial_count INT NOT NULL,
    fill_count INT DEFAULT 0,
    remaining_count INT,
    queue_position INT,
    
    -- Prices (DECIMAL)
    yes_price DECIMAL(10,4),
    no_price DECIMAL(10,4),
    
    -- Costs (DECIMAL)
    maker_fees DECIMAL(10,4) DEFAULT 0,
    taker_fees DECIMAL(10,4) DEFAULT 0,
    maker_fill_cost DECIMAL(10,4) DEFAULT 0,
    taker_fill_cost DECIMAL(10,4) DEFAULT 0,
    
    -- Timestamps
    created_time TIMESTAMP DEFAULT NOW(),
    expiration_time TIMESTAMP,
    last_update_time TIMESTAMP DEFAULT NOW(),
    
    CHECK (status IN ('pending', 'resting', 'executed', 'canceled'))
);

-- Indexes
CREATE INDEX idx_orders_ticker ON orders(ticker);
CREATE INDEX idx_orders_client ON orders(client_order_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created ON orders(created_time);
```

---

## Positions Table

**String Fields:**
```sql
position_id SERIAL PRIMARY KEY,
ticker VARCHAR(100) REFERENCES markets(ticker)
```

**Position Data (use DECIMAL for prices):**
```sql
position INT NOT NULL,  -- Can be negative (short)
market_exposure DECIMAL(10,4),
total_traded INT,
fees_paid DECIMAL(10,4),
realized_pnl DECIMAL(10,4),
resting_orders_count INT DEFAULT 0
```

**Timestamp:**
```sql
last_updated_ts TIMESTAMP DEFAULT NOW()
```

**Complete Table Definition:**
```sql
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    ticker VARCHAR(100) REFERENCES markets(ticker),
    
    -- Position details
    position INT NOT NULL,  -- Quantity (can be negative)
    market_exposure DECIMAL(10,4),
    total_traded INT,
    fees_paid DECIMAL(10,4),
    realized_pnl DECIMAL(10,4),
    resting_orders_count INT DEFAULT 0,
    
    -- Timestamp
    last_updated_ts TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_positions_ticker ON positions(ticker);
CREATE INDEX idx_positions_updated ON positions(last_updated_ts);
```

---

## Fills Table

**String Fields:**
```sql
fill_id VARCHAR(100) PRIMARY KEY,
order_id VARCHAR(100) REFERENCES orders(order_id),
trade_id VARCHAR(100),  -- Platform's trade ID
ticker VARCHAR(100) REFERENCES markets(ticker),
side VARCHAR(3),
action VARCHAR(4)
```

**Fill Data (DECIMAL for prices):**
```sql
count INT NOT NULL,
yes_price DECIMAL(10,4),
no_price DECIMAL(10,4),
is_taker BOOLEAN
```

**Timestamp:**
```sql
created_time TIMESTAMP DEFAULT NOW()
```

**Complete Table Definition:**
```sql
CREATE TABLE fills (
    fill_id VARCHAR(100) PRIMARY KEY,
    order_id VARCHAR(100) REFERENCES orders(order_id),
    trade_id VARCHAR(100),
    ticker VARCHAR(100) REFERENCES markets(ticker),
    
    -- Fill details
    side VARCHAR(3) CHECK (side IN ('yes', 'no')),
    action VARCHAR(4) CHECK (action IN ('buy', 'sell')),
    count INT NOT NULL,
    
    -- Prices (DECIMAL)
    yes_price DECIMAL(10,4),
    no_price DECIMAL(10,4),
    
    is_taker BOOLEAN,
    
    -- Timestamp
    created_time TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_fills_order ON fills(order_id);
CREATE INDEX idx_fills_ticker ON fills(ticker);
CREATE INDEX idx_fills_created ON fills(created_time);
```

---

## Series & Events Tables

**Series:**
```sql
CREATE TABLE series (
    ticker VARCHAR(100) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    category VARCHAR(50),
    frequency VARCHAR(20),
    fee_type VARCHAR(20),
    fee_multiplier DECIMAL(6,4),  -- e.g., 0.0700 for 7%
    
    -- JSONB fields
    product_metadata JSONB,
    settlement_sources JSONB,
    tags JSONB,
    additional_prohibitions JSONB,
    
    -- URLs
    rules_url TEXT,
    about_url TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_series_category ON series(category);
```

**Events:**
```sql
CREATE TABLE events (
    event_ticker VARCHAR(100) PRIMARY KEY,
    series_ticker VARCHAR(100) REFERENCES series(ticker),
    title VARCHAR(500) NOT NULL,
    category VARCHAR(50),
    
    -- Timestamps
    strike_date DATE,
    settlement_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_events_series ON events(series_ticker);
CREATE INDEX idx_events_category ON events(category);
CREATE INDEX idx_events_settlement ON events(settlement_date);
```

---

## Python Implementation Example

```python
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

class KalshiMarketStore:
    """
    Store Kalshi market data with proper decimal handling.
    """
    
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def insert_market(self, market_data: dict):
        """
        Insert market data from Kalshi API.
        
        Args:
            market_data: Raw market data from Kalshi API
        """
        # Extract prices from _dollars fields (future-proof)
        yes_bid = Decimal(market_data.get("yes_bid_dollars", "0"))
        yes_ask = Decimal(market_data.get("yes_ask_dollars", "0"))
        no_bid = Decimal(market_data.get("no_bid_dollars", "0"))
        no_ask = Decimal(market_data.get("no_ask_dollars", "0"))
        
        # Validation
        self._validate_prices(yes_bid, yes_ask, no_bid, no_ask)
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO markets (
                    ticker, event_ticker, title, status,
                    yes_bid, yes_ask, no_bid, no_ask,
                    volume, open_interest,
                    created_at, row_current_ind
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    NOW(), TRUE
                )
                ON CONFLICT (ticker) DO UPDATE
                SET 
                    yes_bid = EXCLUDED.yes_bid,
                    yes_ask = EXCLUDED.yes_ask,
                    no_bid = EXCLUDED.no_bid,
                    no_ask = EXCLUDED.no_ask,
                    volume = EXCLUDED.volume,
                    open_interest = EXCLUDED.open_interest,
                    updated_at = NOW()
            """, (
                market_data["ticker"],
                market_data["event_ticker"],
                market_data["title"],
                market_data["status"],
                yes_bid, yes_ask, no_bid, no_ask,
                market_data.get("volume", 0),
                market_data.get("open_interest", 0)
            ))
        
        self.conn.commit()
    
    def _validate_prices(self, yes_bid, yes_ask, no_bid, no_ask):
        """Validate price constraints."""
        if not (0.0001 <= yes_bid <= 0.9999):
            raise ValueError(f"Invalid yes_bid: {yes_bid}")
        if not (0.0001 <= yes_ask <= 0.9999):
            raise ValueError(f"Invalid yes_ask: {yes_ask}")
        if not (0.0001 <= no_bid <= 0.9999):
            raise ValueError(f"Invalid no_bid: {no_bid}")
        if not (0.0001 <= no_ask <= 0.9999):
            raise ValueError(f"Invalid no_ask: {no_ask}")
        
        # YES + NO should approximately equal 1.0 (accounting for spread)
        total = yes_bid + no_ask
        if not (0.95 <= total <= 1.05):
            raise ValueError(f"Price consistency check failed: {total}")
```

---

## Migration from Integer Cents

If you have existing code using integer cents:

```python
# OLD CODE (will break):
yes_bid_cents = market_data["yes_bid"]  # 43
yes_bid_dollars = yes_bid_cents / 100   # 0.43

# NEW CODE (future-proof):
yes_bid = Decimal(market_data["yes_bid_dollars"])  # "0.4275"
```

**Database Migration:**
```sql
-- If you have existing tables with INTEGER prices
ALTER TABLE markets 
    ALTER COLUMN yes_bid TYPE DECIMAL(10,4) USING (yes_bid::DECIMAL / 100),
    ALTER COLUMN yes_ask TYPE DECIMAL(10,4) USING (yes_ask::DECIMAL / 100),
    ALTER COLUMN no_bid TYPE DECIMAL(10,4) USING (no_bid::DECIMAL / 100),
    ALTER COLUMN no_ask TYPE DECIMAL(10,4) USING (no_ask::DECIMAL / 100);

-- Update constraints
ALTER TABLE markets 
    DROP CONSTRAINT IF EXISTS markets_yes_bid_check,
    ADD CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999);
```

---

## Key Takeaways

✅ **Use DECIMAL(10,4) for all price fields**  
✅ **Use DECIMAL(10,4) for all fee/cost fields**  
✅ **Always parse `_dollars` fields from API**  
✅ **Never use integer cent fields (deprecated)**  
✅ **Use Python's `decimal.Decimal` type**  
✅ **Validate price constraints in application code**

**Reference:** [Kalshi Sub-Penny Pricing Documentation](https://docs.kalshi.com/getting_started/subpenny_pricing)

---

**Document Version**: 2.1  
**Last Updated**: October 8, 2025  
**Changes**: Converted all INTEGER cents to DECIMAL(10,4) throughout
