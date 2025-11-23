# Kalshi Client User Guide

---
**Version:** 1.0
**Created:** 2025-11-22
**Target Audience:** Developers integrating Kalshi prediction market API
**Purpose:** Comprehensive guide to using KalshiClient for fetching market data and account information
**Complement to:** API_INTEGRATION_GUIDE_V2.0.md (reference docs) and KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md

---

## Overview

### What is KalshiClient?

**KalshiClient** is Precog's high-level Python interface to the Kalshi prediction market API. It handles all the complexity of authentication, rate limiting, retries, and price conversion—so you can focus on trading logic.

**Think of it this way:**
- **API_INTEGRATION_GUIDE** = "What endpoints exist and what they return"
- **KALSHI_CLIENT_USER_GUIDE** = "How to use those endpoints in your Python code"

### Why KalshiClient?

**Problem:** Using Kalshi API directly is tedious and error-prone:
```python
# ❌ DON'T DO THIS (raw API calls)
import requests
response = requests.get('https://demo-api.kalshi.co/trade-api/v2/markets')
markets = response.json()['markets']
yes_ask = float(markets[0]['yes_ask'])  # WRONG! Float contamination!
```

**Solution:** KalshiClient handles all the complexity:
```python
# ✅ DO THIS (KalshiClient)
from precog.api_connectors import KalshiClient

client = KalshiClient(environment="demo")
markets = client.get_markets(series_ticker="KXNFLGAME")
yes_ask = markets[0]['yes_ask']  # Decimal("0.6500") - proper precision!
```

### Key Features

1. **RSA-PSS Authentication** - Automatic token generation and refresh (tokens expire after 30 minutes)
2. **Environment Switching** - Easy toggle between demo (fake money) and production (real money)
3. **Rate Limiting** - Automatic compliance with Kalshi's 100 requests/minute limit
4. **Decimal Precision** - All prices automatically converted to Decimal (Pattern 1)
5. **Retry Logic** - Exponential backoff for transient server errors (5xx)
6. **Error Handling** - Clear exceptions with detailed logging
7. **Connection Pooling** - Efficient HTTP connection reuse (requests.Session)
8. **TypedDict Responses** - Compile-time type safety with mypy

---

## Core Concepts

### 1. Demo vs Production Environments

**Kalshi provides two environments:**

| Environment | Purpose | Base URL | Money | Use When |
|-------------|---------|----------|-------|----------|
| **demo** | Testing | https://demo-api.kalshi.co | Fake ($10,000 starting balance) | Development, learning, testing strategies |
| **prod** | Live trading | https://api.elections.kalshi.com | Real | Production trading (after thorough testing!) |

**⚠️ CRITICAL:** Always develop and test against **demo** first!

**Environment Setup:**
```bash
# .env file
# Demo environment (safe for testing)
KALSHI_DEMO_KEY_ID=your-demo-api-key-id
KALSHI_DEMO_KEYFILE=_keys/kalshi_demo_private.pem

# Production environment (real money!)
KALSHI_PROD_KEY_ID=your-prod-api-key-id
KALSHI_PROD_KEYFILE=_keys/kalshi_prod_private.pem
```

**Python usage:**
```python
# Development: use demo
client = KalshiClient(environment="demo")

# Production: use prod (only when confident!)
if is_production():
    client = KalshiClient(environment="prod")
```

### 2. RSA-PSS Authentication (Automatic)

Kalshi uses **RSA-PSS cryptographic signatures** for authentication. KalshiClient handles this automatically—you don't need to understand the cryptography!

**How it works:**
1. You provide API key ID and private key file path in .env
2. KalshiClient generates signed authentication headers for each request
3. Kalshi server verifies signature and grants access
4. Tokens expire after 30 minutes → KalshiClient automatically refreshes

**You never see the tokens or signatures!**

**References:**
- REQ-API-002: RSA-PSS Authentication
- ADR-047: RSA-PSS Authentication Implementation
- `src/precog/api_connectors/kalshi_auth.py` (implementation details)

### 3. Rate Limiting (100 Requests/Minute)

Kalshi enforces **100 requests per minute** limit. KalshiClient prevents you from hitting this limit using a **token bucket algorithm**.

**How it works:**
1. Start with 100 tokens (requests allowed)
2. Each API call consumes 1 token
3. Tokens refill at rate of 100 per minute
4. If no tokens available → `wait_if_needed()` pauses until token available

**Example:**
```python
client = KalshiClient("demo")

# First 100 requests: instant
for i in range(100):
    client.get_balance()  # No delay

# 101st request: waits ~0.6 seconds (time for 1 token to refill)
client.get_balance()  # Automatic delay
```

**429 Rate Limit Errors:**
If you somehow exceed the limit, Kalshi returns HTTP 429. KalshiClient honors the `Retry-After` header:
```python
# Kalshi returns: 429 Too Many Requests, Retry-After: 60
# KalshiClient automatically waits 60 seconds before retry
```

**References:**
- REQ-API-005: API Rate Limit Management
- ADR-051: Token Bucket Rate Limiting
- `src/precog/api_connectors/rate_limiter.py` (implementation details)

### 4. Decimal Precision (Automatic Pattern 1 Enforcement)

Kalshi API returns prices as **strings** (e.g., `"0.6250"`). KalshiClient **automatically converts to Decimal**:

**Price Fields Auto-Converted:**
- `yes_bid`, `yes_ask`, `no_bid`, `no_ask` - Current bid/ask prices
- `last_price` - Most recent trade price
- `price` - Fill price (in trade history)
- `user_average_price` - Your average entry price
- `settlement_value` - Market settlement ($1.00 or $0.00)
- `balance` - Account balance
- `realized_pnl` - Realized profit/loss
- `total_cost`, `fees_paid`, `revenue`, `total_fees` - Financial amounts

**Example:**
```python
client = KalshiClient("demo")
markets = client.get_markets(series_ticker="KXNFLGAME")

market = markets[0]
print(type(market['yes_ask']))  # <class 'decimal.Decimal'>
print(market['yes_ask'])        # Decimal('0.6500')

# ✅ CORRECT: Decimal arithmetic
profit = market['yes_ask'] - Decimal("0.50")  # Decimal('0.1500')

# ❌ WRONG: Float arithmetic (don't do this!)
profit_wrong = float(market['yes_ask']) - 0.50  # 0.15000000000000002 - precision error!
```

**Why This Matters:**
Financial calculations with float cause rounding errors (0.1 + 0.2 ≠ 0.3 with floats!). Decimal ensures exact precision.

**References:**
- REQ-SYS-003: Decimal Precision for Prices
- ADR-002: Decimal Precision for Financial Calculations
- CLAUDE.md Pattern 1 (Decimal Precision)
- KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md

### 5. Pagination (Cursors for Large Results)

Kalshi limits responses to **200 items maximum**. For larger result sets, use **cursor-based pagination**:

**How it works:**
1. First request: No cursor, returns first 100-200 items + cursor
2. Second request: Pass cursor, returns next 100-200 items + new cursor
3. Repeat until response has no cursor (you've fetched all results)

**Example:**
```python
client = KalshiClient("demo")

all_markets = []
cursor = None

while True:
    # Fetch page
    markets = client.get_markets(series_ticker="KXNFLGAME", limit=200, cursor=cursor)
    all_markets.extend(markets)

    # Check if more pages exist
    # (Note: cursor returned in response metadata, not in markets list)
    # For simplicity, assume get_markets returns all available
    if len(markets) < 200:
        break  # Last page (fewer than 200 results)

print(f"Fetched {len(all_markets)} total markets")
```

**Note:** Current KalshiClient implementation returns markets list without exposing cursor in return value. For full pagination support, you'd need to check `response.get('cursor')` in `_make_request()` return value.

### 6. Retry Logic and Error Handling

KalshiClient automatically retries **server errors (5xx)** using **exponential backoff**:

**Retry Strategy:**
```
Initial request fails with 503 Service Unavailable
└─ Retry 1: Wait 1 second (2^0), retry
   └─ Retry 2: Wait 2 seconds (2^1), retry
      └─ Retry 3: Wait 4 seconds (2^2), retry
         └─ If still fails: Raise exception
```

**Error Categories:**

| Error Type | HTTP Codes | Retry? | Example |
|------------|------------|--------|---------|
| **Server Errors** | 500, 502, 503, 504 | ✅ Yes (max 3 retries) | Kalshi server temporarily down |
| **Client Errors** | 400, 401, 403, 404 | ❌ No (fail immediately) | Invalid ticker, bad auth |
| **Rate Limit** | 429 | ⚠️ Special handling | Too many requests |
| **Timeout** | - | ❌ No (fail immediately) | Request took >30 seconds |

**Example Error Handling:**
```python
from precog.api_connectors import KalshiClient
import requests

client = KalshiClient("demo")

try:
    markets = client.get_markets(series_ticker="INVALID")
except requests.HTTPError as e:
    if e.response.status_code == 404:
        print("Series not found - check ticker symbol")
    elif e.response.status_code == 429:
        print("Rate limit exceeded - wait before retrying")
    elif 500 <= e.response.status_code < 600:
        print("Kalshi server error - already retried 3 times, still failed")
    else:
        print(f"API error: {e}")
except requests.Timeout:
    print("Request timed out after 30 seconds")
except requests.RequestException as e:
    print(f"Network error: {e}")
```

**References:**
- REQ-API-006: API Error Handling
- ADR-049: Retry Logic with Exponential Backoff
- ADR-050: Exponential Backoff Strategy

### 7. Connection Pooling (Automatic)

KalshiClient uses `requests.Session` for **connection pooling**:

**Benefits:**
- **Faster requests** - Reuses TCP connections instead of opening new ones
- **Lower overhead** - Reduces handshake time for subsequent requests
- **Better performance** - 10-20% faster for multiple requests

**Example Performance:**
```python
# Without connection pooling (slow)
import requests
for i in range(10):
    response = requests.get('https://demo-api.kalshi.co/trade-api/v2/markets')
    # Each request: TCP connect + TLS handshake + request (~200ms)

# With connection pooling (fast) - KalshiClient does this automatically
client = KalshiClient("demo")
for i in range(10):
    markets = client.get_markets()
    # First request: TCP connect + TLS handshake + request (~200ms)
    # Next 9 requests: Just request (~150ms) - connection reused!
```

**⚠️ IMPORTANT:** Always call `client.close()` when done to release connections:
```python
client = KalshiClient("demo")
try:
    markets = client.get_markets()
finally:
    client.close()  # Clean up connections
```

Or use context manager (if implemented in future):
```python
with KalshiClient("demo") as client:
    markets = client.get_markets()
# Automatically closes connection
```

---

## Quick Start

### Installation

KalshiClient is part of Precog, no separate installation needed:

```python
from precog.api_connectors import KalshiClient
```

### Setup (.env file)

Create `.env` file in project root:

```bash
# Demo environment (safe for testing)
KALSHI_DEMO_KEY_ID=your-demo-api-key-id
KALSHI_DEMO_KEYFILE=_keys/kalshi_demo_private.pem

# Production environment (real money!)
KALSHI_PROD_KEY_ID=your-prod-api-key-id
KALSHI_PROD_KEYFILE=_keys/kalshi_prod_private.pem
```

**Get API credentials:**
1. **Demo:** Sign up at https://demo-api.kalshi.co
2. **Production:** Sign up at https://kalshi.com (requires identity verification)

**Generate private key:**
```bash
# Kalshi provides key generation instructions in API docs
# Store private key in _keys/ folder (gitignored for security)
```

### Basic Usage (5 Common Patterns)

**1. Initialize client:**
```python
from precog.api_connectors import KalshiClient

# Demo environment (development)
client = KalshiClient(environment="demo")

# Production environment (live trading)
client = KalshiClient(environment="prod")
```

**2. Fetch markets:**
```python
# Get all NFL markets
nfl_markets = client.get_markets(series_ticker="KXNFLGAME")
print(f"Found {len(nfl_markets)} NFL markets")

# Get specific market
market = client.get_market("KXNFLGAME-25OCT05-NEBUF-B250")
print(f"Yes ask: ${market['yes_ask']}")  # Decimal("0.6500")
```

**3. Check account balance:**
```python
balance = client.get_balance()
print(f"Account balance: ${balance}")  # Decimal("10000.00") in demo
```

**4. Get current positions:**
```python
# Get all open positions
open_positions = client.get_positions(status="open")

for pos in open_positions:
    print(f"{pos['ticker']}: {pos['position']} contracts @ ${pos['user_average_price']}")
    # KXNFLGAME-25OCT05-NEBUF-B250: 10 contracts @ $0.6500
```

**5. Clean up when done:**
```python
try:
    markets = client.get_markets()
    # ... do work ...
finally:
    client.close()  # Release HTTP connections
```

---

## Complete API Reference

### KalshiClient Class

#### `__init__(environment: str = "demo")`

Initialize Kalshi client.

**Args:**
- `environment`: `"demo"` or `"prod"` (default: `"demo"`)

**Raises:**
- `ValueError`: If environment invalid (not "demo" or "prod")
- `EnvironmentError`: If required environment variables missing (`KALSHI_<ENV>_KEY_ID`, `KALSHI_<ENV>_KEYFILE`)

**Example:**
```python
# Demo environment (safe for testing)
client = KalshiClient(environment="demo")

# Production environment (real money!)
client = KalshiClient(environment="prod")

# Default is demo
client = KalshiClient()  # Same as environment="demo"
```

**Environment Variables:**
```bash
# Demo
KALSHI_DEMO_KEY_ID=abc123
KALSHI_DEMO_KEYFILE=_keys/kalshi_demo_private.pem

# Production
KALSHI_PROD_KEY_ID=xyz789
KALSHI_PROD_KEYFILE=_keys/kalshi_prod_private.pem
```

---

#### `get_markets(series_ticker=None, event_ticker=None, limit=100, cursor=None) -> list[ProcessedMarketData]`

Get list of markets with price data.

**Args:**
- `series_ticker`: Filter by series (e.g., `"KXNFLGAME"`, `"KXNCAAFGAME"`) - optional
- `event_ticker`: Filter by specific event (e.g., `"KXNFLGAME-25OCT05-NEBUF"`) - optional
- `limit`: Max markets to return (default 100, max 200)
- `cursor`: Pagination cursor for next page (optional)

**Returns:**
- List of market dictionaries with Decimal prices

**Market Dictionary Structure:**
```python
{
    "ticker": str,              # "KXNFLGAME-25OCT05-NEBUF-B250"
    "title": str,               # "Will Nebraska score 25+ points vs Buffalo?"
    "subtitle": str,            # "Buffalo @ Nebraska, Oct 5, 2025"
    "yes_bid": Decimal,         # Decimal("0.6400")
    "yes_ask": Decimal,         # Decimal("0.6500")
    "no_bid": Decimal,          # Decimal("0.3500")
    "no_ask": Decimal,          # Decimal("0.3600")
    "last_price": Decimal,      # Decimal("0.6450")
    "volume": int,              # 1250 (contracts traded)
    "open_interest": int,       # 500 (contracts currently held)
    "close_time": str,          # "2025-10-05T18:00:00Z"
    "status": str,              # "active", "closed", "settled"
    # ... more fields
}
```

**Example:**
```python
client = KalshiClient("demo")

# Get all NFL markets
nfl_markets = client.get_markets(series_ticker="KXNFLGAME")
print(f"Found {len(nfl_markets)} NFL markets")

# Get specific event markets (e.g., one NFL game)
game_markets = client.get_markets(event_ticker="KXNFLGAME-25OCT05-NEBUF")
print(f"Found {len(game_markets)} markets for this game")

# Limit results
recent_markets = client.get_markets(limit=10)

# Pagination (fetch all markets)
all_markets = []
cursor = None
while True:
    batch = client.get_markets(limit=200, cursor=cursor)
    all_markets.extend(batch)
    if len(batch) < 200:
        break  # Last page
```

**Use Cases:**
- **Market discovery:** Find tradable markets for NFL, NCAAF, etc.
- **Price monitoring:** Track bid/ask spreads across markets
- **Opportunity scanning:** Find markets with high edge

**References:**
- REQ-API-001: Kalshi API Integration
- ProcessedMarketData TypedDict in `types.py`

---

#### `get_market(ticker: str) -> ProcessedMarketData`

Get details for single market.

**Args:**
- `ticker`: Market ticker (e.g., `"KXNFLGAME-25OCT05-NEBUF-B250"`)

**Returns:**
- Market dictionary with Decimal prices (same structure as `get_markets()`)

**Raises:**
- `requests.HTTPError`: If ticker not found (404) or other API error

**Example:**
```python
client = KalshiClient("demo")

# Get specific market
market = client.get_market("KXNFLGAME-25OCT05-NEBUF-B250")

print(f"Title: {market['title']}")
print(f"Yes ask: ${market['yes_ask']}")  # Decimal("0.6500")
print(f"No bid: ${market['no_bid']}")    # Decimal("0.3500")
print(f"Spread: ${market['yes_ask'] - market['yes_bid']}")  # Decimal("0.0100") = 1¢

# Check if market open for trading
if market['status'] == 'active':
    print("Market is open for trading")
else:
    print(f"Market status: {market['status']}")  # "closed" or "settled"
```

**Use Cases:**
- **Price checks:** Get current prices for specific market before trading
- **Market status:** Check if market open/closed/settled
- **Detailed info:** Get full market details (volume, open interest, etc.)

**References:**
- REQ-API-001: Kalshi API Integration

---

#### `get_balance() -> Decimal`

Fetch account balance.

**Returns:**
- Account balance as Decimal

**Raises:**
- `requests.HTTPError`: If API request fails

**Example:**
```python
client = KalshiClient("demo")

balance = client.get_balance()
print(f"Account balance: ${balance}")  # Decimal("10000.00") in demo

# Check if sufficient funds for trade
position_cost = Decimal("650.00")  # Buying 10 YES @ $0.65
if balance >= position_cost:
    print("Sufficient funds for trade")
else:
    print(f"Insufficient funds (need ${position_cost}, have ${balance})")
```

**Demo vs Production:**
- **Demo:** Starts with $10,000 fake balance (can be reset in Kalshi demo console)
- **Production:** Shows real account balance (requires deposit to Kalshi account)

**Use Cases:**
- **Pre-trade check:** Ensure sufficient funds before placing order
- **Account monitoring:** Track balance over time
- **Risk management:** Prevent over-leveraging

**References:**
- REQ-CLI-002: Balance Fetch Command
- REQ-SYS-003: Decimal Precision

---

#### `get_positions(status=None, ticker=None) -> list[ProcessedPositionData]`

Get current positions.

**Args:**
- `status`: Filter by status (`"open"` or `"closed"`) - optional
- `ticker`: Filter by market ticker - optional

**Returns:**
- List of position dictionaries with Decimal prices

**Position Dictionary Structure:**
```python
{
    "ticker": str,                # "KXNFLGAME-25OCT05-NEBUF-B250"
    "position": int,              # 10 (number of contracts, positive for YES, negative for NO)
    "side": str,                  # "yes" or "no"
    "user_average_price": Decimal,# Decimal("0.6500") - your avg entry price
    "realized_pnl": Decimal,      # Decimal("0.00") if still open
    "total_cost": Decimal,        # Decimal("6.50") - 10 * $0.65
    "fees_paid": Decimal,         # Decimal("0.46") - Kalshi 7% commission
    # ... more fields
}
```

**Example:**
```python
client = KalshiClient("demo")

# Get all open positions
open_positions = client.get_positions(status="open")
print(f"You have {len(open_positions)} open positions")

for pos in open_positions:
    print(f"{pos['ticker']}: {pos['position']} contracts @ ${pos['user_average_price']}")
    # KXNFLGAME-25OCT05-NEBUF-B250: 10 contracts @ $0.6500

# Get closed positions (historical)
closed_positions = client.get_positions(status="closed")
for pos in closed_positions:
    print(f"{pos['ticker']}: Realized P&L = ${pos['realized_pnl']}")

# Get positions for specific market
specific_positions = client.get_positions(ticker="KXNFLGAME-25OCT05-NEBUF-B250")
```

**Use Cases:**
- **Portfolio monitoring:** Track all open positions
- **P&L calculation:** Calculate unrealized P&L by comparing `user_average_price` to current market price
- **Position limits:** Ensure not exceeding max positions per market
- **Historical analysis:** Review closed positions and realized P&L

**References:**
- REQ-CLI-003: Positions Fetch Command

---

#### `get_fills(ticker=None, min_ts=None, max_ts=None, limit=100, cursor=None) -> list[ProcessedFillData]`

Get trade fills (executed orders).

**Args:**
- `ticker`: Filter by market ticker - optional
- `min_ts`: Minimum timestamp (Unix milliseconds) - optional
- `max_ts`: Maximum timestamp (Unix milliseconds) - optional
- `limit`: Max fills to return (default 100)
- `cursor`: Pagination cursor - optional

**Returns:**
- List of fill dictionaries with Decimal prices

**Fill Dictionary Structure:**
```python
{
    "ticker": str,              # "KXNFLGAME-25OCT05-NEBUF-B250"
    "side": str,                # "yes" or "no"
    "action": str,              # "buy" or "sell"
    "count": int,               # 10 (contracts filled)
    "price": Decimal,           # Decimal("0.6500") - fill price
    "created_time": str,        # "2025-10-05T14:32:15Z"
    "trade_id": str,            # "abc123..."
    # ... more fields
}
```

**Example:**
```python
client = KalshiClient("demo")

# Get all recent fills
fills = client.get_fills(limit=20)
print(f"Last {len(fills)} fills:")

for fill in fills:
    print(f"{fill['created_time']}: {fill['action']} {fill['count']} {fill['side']} @ ${fill['price']}")
    # 2025-10-05T14:32:15Z: buy 10 yes @ $0.6500

# Get fills for specific market
market_fills = client.get_fills(ticker="KXNFLGAME-25OCT05-NEBUF-B250")

# Get fills in time range (last 24 hours)
import time
now_ms = int(time.time() * 1000)
day_ago_ms = now_ms - (24 * 60 * 60 * 1000)
recent_fills = client.get_fills(min_ts=day_ago_ms, max_ts=now_ms)

# Pagination
all_fills = []
cursor = None
while True:
    batch = client.get_fills(limit=200, cursor=cursor)
    all_fills.extend(batch)
    if len(batch) < 200:
        break
```

**Use Cases:**
- **Trade history:** Review all executed trades
- **Fill analysis:** Check average fill prices vs market prices
- **Audit trail:** Verify trades executed correctly
- **Performance attribution:** Track which trades profitable/unprofitable

**References:**
- REQ-CLI-004: Fills Fetch Command

---

#### `get_settlements(ticker=None, limit=100, cursor=None) -> list[ProcessedSettlementData]`

Get market settlements.

**Args:**
- `ticker`: Filter by market ticker - optional
- `limit`: Max settlements to return (default 100)
- `cursor`: Pagination cursor - optional

**Returns:**
- List of settlement dictionaries with Decimal values

**Settlement Dictionary Structure:**
```python
{
    "ticker": str,              # "KXNFLGAME-25OCT05-NEBUF-B250"
    "market_result": str,       # "yes" or "no" (which side won)
    "settlement_value": Decimal,# Decimal("1.00") for winners, Decimal("0.00") for losers
    "revenue": Decimal,         # Decimal("10.00") - your payout (if you won)
    "total_fees": Decimal,      # Decimal("0.70") - fees paid
    "settled_time": str,        # "2025-10-05T20:15:00Z"
    # ... more fields
}
```

**Example:**
```python
client = KalshiClient("demo")

# Get all recent settlements
settlements = client.get_settlements(limit=20)
print(f"Last {len(settlements)} settled markets:")

for settlement in settlements:
    print(f"{settlement['ticker']}: {settlement['market_result']} won, payout = ${settlement['revenue']}")
    # KXNFLGAME-25OCT05-NEBUF-B250: yes won, payout = $10.00

# Get settlement for specific market
market_settlement = client.get_settlements(ticker="KXNFLGAME-25OCT05-NEBUF-B250")

if market_settlement:
    settlement = market_settlement[0]
    if settlement['revenue'] > Decimal("0"):
        print(f"You won ${settlement['revenue']}!")
    else:
        print("You lost this market")
```

**Use Cases:**
- **P&L verification:** Confirm settled markets paid out correctly
- **Historical analysis:** Review past market outcomes
- **Strategy evaluation:** Check which predictions were accurate

**References:**
- REQ-CLI-005: Settlements Fetch Command

---

#### `close()`

Close the client and clean up resources.

**Example:**
```python
client = KalshiClient("demo")

try:
    markets = client.get_markets()
    balance = client.get_balance()
    # ... do work ...
finally:
    client.close()  # Release HTTP connections
```

**Best Practice:**
Always call `close()` when done to avoid resource leaks (open HTTP connections).

---

## Common Patterns

### Pattern 1: Safe Client Initialization with Context Manager

**Problem:** Forgetting to call `client.close()` causes resource leaks.

**Solution:** Use try/finally pattern:
```python
from precog.api_connectors import KalshiClient

def fetch_market_data():
    """Fetch market data with guaranteed cleanup."""
    client = KalshiClient("demo")
    try:
        markets = client.get_markets(series_ticker="KXNFLGAME")
        return markets
    finally:
        client.close()  # Always runs, even if exception occurs
```

**Better Solution (Future):** Implement context manager:
```python
# Future enhancement: add __enter__ and __exit__ to KalshiClient
with KalshiClient("demo") as client:
    markets = client.get_markets()
# Automatically calls close()
```

---

### Pattern 2: Environment-Specific Client

**Problem:** Need to toggle between demo and production based on environment.

**Solution:**
```python
from precog.config.config_loader import is_production
from precog.api_connectors import KalshiClient

def get_kalshi_client() -> KalshiClient:
    """Get Kalshi client for current environment."""
    if is_production():
        # Production: real money, real markets
        return KalshiClient(environment="prod")
    else:
        # Development/staging: demo environment
        return KalshiClient(environment="demo")

# Usage
client = get_kalshi_client()
try:
    markets = client.get_markets()
finally:
    client.close()
```

---

### Pattern 3: Paginated Market Fetching

**Problem:** Need to fetch all markets, but API limits to 200 per request.

**Solution:**
```python
from precog.api_connectors import KalshiClient

def fetch_all_markets(series_ticker: str) -> list:
    """Fetch all markets for a series with pagination."""
    client = KalshiClient("demo")
    all_markets = []
    cursor = None

    try:
        while True:
            # Fetch batch
            batch = client.get_markets(
                series_ticker=series_ticker,
                limit=200,  # Max per request
                cursor=cursor
            )

            all_markets.extend(batch)

            # Check if more pages
            if len(batch) < 200:
                break  # Last page (fewer than 200 results)

            # Note: Current implementation doesn't expose cursor in return value
            # For full pagination, you'd need cursor from response metadata

        return all_markets

    finally:
        client.close()

# Usage
nfl_markets = fetch_all_markets("KXNFLGAME")
print(f"Fetched {len(nfl_markets)} total NFL markets")
```

---

### Pattern 4: Error-Resilient API Calls

**Problem:** API calls can fail for various reasons (network, server errors, rate limits).

**Solution:**
```python
from precog.api_connectors import KalshiClient
import requests
import time
from decimal import Decimal

def fetch_balance_with_retry(max_attempts: int = 3) -> Decimal | None:
    """Fetch balance with custom retry logic."""
    client = KalshiClient("demo")

    for attempt in range(max_attempts):
        try:
            balance = client.get_balance()
            return balance

        except requests.HTTPError as e:
            status_code = e.response.status_code

            if status_code == 429:
                # Rate limit: wait and retry
                retry_after = int(e.response.headers.get("Retry-After", 60))
                print(f"Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            elif 500 <= status_code < 600:
                # Server error: already retried internally, log and continue
                print(f"Server error {status_code} on attempt {attempt + 1}/{max_attempts}")
                if attempt < max_attempts - 1:
                    time.sleep(5)  # Wait before retry
                    continue
                else:
                    print("Max retries exceeded")
                    return None

            else:
                # Client error (4xx): don't retry
                print(f"Client error {status_code}: {e}")
                return None

        except requests.Timeout:
            print(f"Timeout on attempt {attempt + 1}/{max_attempts}")
            if attempt < max_attempts - 1:
                continue
            else:
                return None

        except requests.RequestException as e:
            print(f"Network error: {e}")
            return None

        finally:
            client.close()

    return None

# Usage
balance = fetch_balance_with_retry()
if balance is not None:
    print(f"Balance: ${balance}")
else:
    print("Failed to fetch balance after retries")
```

---

### Pattern 5: Calculate Unrealized P&L

**Problem:** Need to calculate unrealized P&L for open positions.

**Solution:**
```python
from precog.api_connectors import KalshiClient
from decimal import Decimal

def calculate_unrealized_pnl(client: KalshiClient, position: dict) -> Decimal:
    """Calculate unrealized P&L for a position."""
    ticker = position['ticker']
    side = position['side']  # "yes" or "no"
    quantity = position['position']  # Number of contracts
    entry_price = position['user_average_price']  # Decimal

    # Get current market price
    market = client.get_market(ticker)

    if side == "yes":
        # For YES positions, we'd sell at current yes_bid
        current_price = market['yes_bid']
    else:  # "no"
        # For NO positions, we'd sell at current no_bid
        current_price = market['no_bid']

    # Calculate P&L
    pnl = quantity * (current_price - entry_price)
    return pnl

# Usage
client = KalshiClient("demo")
try:
    positions = client.get_positions(status="open")

    total_unrealized_pnl = Decimal("0")
    for pos in positions:
        pnl = calculate_unrealized_pnl(client, pos)
        total_unrealized_pnl += pnl
        print(f"{pos['ticker']}: ${pnl:+.4f} unrealized P&L")

    print(f"\nTotal unrealized P&L: ${total_unrealized_pnl:+.4f}")

finally:
    client.close()
```

---

### Pattern 6: Finding Best Prices Across Markets

**Problem:** Want to find markets with best YES ask prices (cheapest to buy).

**Solution:**
```python
from precog.api_connectors import KalshiClient
from decimal import Decimal

def find_best_yes_prices(series_ticker: str, top_n: int = 10):
    """Find markets with cheapest YES ask prices."""
    client = KalshiClient("demo")

    try:
        markets = client.get_markets(series_ticker=series_ticker, limit=200)

        # Filter to active markets only
        active_markets = [m for m in markets if m['status'] == 'active']

        # Sort by yes_ask (cheapest first)
        sorted_markets = sorted(active_markets, key=lambda m: m['yes_ask'])

        # Return top N
        return sorted_markets[:top_n]

    finally:
        client.close()

# Usage
cheap_markets = find_best_yes_prices("KXNFLGAME", top_n=5)

print("Top 5 cheapest YES markets:")
for market in cheap_markets:
    print(f"{market['title']}: ${market['yes_ask']}")
    # Will Nebraska score 10+ points?: $0.1500
    # Will Buffalo score 5+ points?: $0.2000
    # ...
```

---

## Troubleshooting

### Issue 1: "Missing Kalshi credentials" Error

**Error:**
```
OSError: Missing Kalshi credentials. Please set KALSHI_DEMO_KEY_ID and
KALSHI_DEMO_KEYFILE in .env file.
```

**Cause:** Environment variables not set or .env file not loaded.

**Solution:**
```bash
# 1. Verify .env file exists
ls .env
# If missing: cp .env.template .env

# 2. Verify .env has correct variables
cat .env
# Should contain:
# KALSHI_DEMO_KEY_ID=your-api-key-id
# KALSHI_DEMO_KEYFILE=_keys/kalshi_demo_private.pem

# 3. Verify private key file exists
ls _keys/kalshi_demo_private.pem
# If missing: download from Kalshi account settings

# 4. Verify environment variable loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('KALSHI_DEMO_KEY_ID'))"
# Should print: your-api-key-id
```

**Debug in Python:**
```python
import os
from dotenv import load_dotenv

load_dotenv()
print(f"KALSHI_DEMO_KEY_ID: {os.getenv('KALSHI_DEMO_KEY_ID')}")
print(f"KALSHI_DEMO_KEYFILE: {os.getenv('KALSHI_DEMO_KEYFILE')}")
```

---

### Issue 2: "401 Unauthorized" Error

**Error:**
```
requests.exceptions.HTTPError: 401 Client Error: Unauthorized for url: https://demo-api.kalshi.co/trade-api/v2/markets
```

**Cause:** Invalid API key or private key file.

**Solution:**
```bash
# 1. Verify API key ID is correct
# Check in Kalshi account settings

# 2. Verify private key file is correct
cat _keys/kalshi_demo_private.pem
# Should start with: -----BEGIN PRIVATE KEY-----

# 3. Try re-generating API credentials
# In Kalshi account settings, delete old API key and create new one

# 4. Verify environment matches credentials
# Demo credentials won't work with environment="prod"
```

**Python Debug:**
```python
from precog.api_connectors.kalshi_auth import KalshiAuth
import os

api_key = os.getenv('KALSHI_DEMO_KEY_ID')
keyfile = os.getenv('KALSHI_DEMO_KEYFILE')

print(f"API key: {api_key}")
print(f"Keyfile path: {keyfile}")
print(f"Keyfile exists: {os.path.exists(keyfile)}")

# Test authentication
auth = KalshiAuth(api_key, keyfile)
headers = auth.get_headers(method="GET", path="/markets")
print(f"Auth headers generated: {list(headers.keys())}")
# Should include: KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP
```

---

### Issue 3: "429 Rate Limit Exceeded" Error

**Error:**
```
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests for url: ...
```

**Cause:** Exceeded 100 requests per minute limit.

**Solution:**
```python
# Rate limiter should handle this automatically,
# but if you're still hitting it:

# 1. Check if making requests in parallel (DON'T DO THIS)
# ❌ WRONG: Parallel requests
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(client.get_market, ticker) for ticker in tickers]
# This bypasses rate limiter!

# ✅ CORRECT: Sequential requests
for ticker in tickers:
    market = client.get_market(ticker)
# Rate limiter works correctly

# 2. Add manual delays if needed
import time
for ticker in tickers:
    market = client.get_market(ticker)
    time.sleep(0.1)  # Extra 100ms delay (optional)
```

---

### Issue 4: Float Instead of Decimal

**Problem:**
```python
market = client.get_market("KXNFLGAME-25OCT05-NEBUF-B250")
print(type(market['yes_ask']))  # <class 'float'> - WRONG!
```

**Cause:** Decimal conversion failed or disabled.

**Solution:**
```python
# Check if conversion is working
from precog.api_connectors import KalshiClient

client = KalshiClient("demo")
market = client.get_market("KXNFLGAME-25OCT05-NEBUF-B250")

print(f"yes_ask type: {type(market['yes_ask'])}")
# Expected: <class 'decimal.Decimal'>

# If float, check _convert_prices_to_decimal() method
# Bug might be in kalshi_client.py line 322-368
```

**Manual conversion if needed:**
```python
from decimal import Decimal

# If auto-conversion failing, convert manually
yes_ask = Decimal(str(market['yes_ask']))
```

---

### Issue 5: "Request Timeout" Error

**Error:**
```
requests.exceptions.Timeout: Request timeout for /markets (attempt 1/1)
```

**Cause:** Kalshi server slow to respond or network issues.

**Solution:**
```python
# Timeout is hardcoded to 30 seconds in kalshi_client.py line 240
# If you need longer timeout, modify source code:

# kalshi_client.py line 234-241
response = self.session.request(
    method=method,
    url=url,
    params=params,
    json=json_data,
    headers=headers,
    timeout=60,  # ← Change from 30 to 60 seconds
)
```

---

## Advanced Topics

### Custom Rate Limiting

**Default:** 100 requests per minute (Kalshi's limit).

**Custom rate limit:**
```python
from precog.api_connectors import KalshiClient
from precog.api_connectors.rate_limiter import RateLimiter

# Initialize client
client = KalshiClient("demo")

# Replace rate limiter with custom one
client.rate_limiter = RateLimiter(requests_per_minute=50)  # More conservative

# Now all requests limited to 50/minute
markets = client.get_markets()
```

---

### TypedDict Response Types

KalshiClient uses **TypedDict** for compile-time type safety:

```python
from precog.api_connectors.types import ProcessedMarketData
from precog.api_connectors import KalshiClient

client = KalshiClient("demo")
markets: list[ProcessedMarketData] = client.get_markets()

# Mypy knows market structure at compile time
market = markets[0]
yes_ask = market['yes_ask']  # Mypy knows this is Decimal
ticker = market['ticker']    # Mypy knows this is str

# Typo caught by mypy:
# price = market['yess_ask']  # Error: Key 'yess_ask' does not exist
```

**Available TypedDicts:**
- `ProcessedMarketData` - Market structure
- `ProcessedPositionData` - Position structure
- `ProcessedFillData` - Fill structure
- `ProcessedSettlementData` - Settlement structure

**Reference:** `src/precog/api_connectors/types.py`

---

### Connection Pool Configuration

**Default:** Inherits from `requests.Session` defaults (10 connections per host).

**Custom pool size:**
```python
from precog.api_connectors import KalshiClient
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Initialize client
client = KalshiClient("demo")

# Custom connection pool
adapter = HTTPAdapter(
    pool_connections=20,  # Number of connection pools (usually 1)
    pool_maxsize=20,      # Max connections in pool
    max_retries=Retry(total=0)  # Disable adapter retries (we handle retries ourselves)
)

client.session.mount('https://', adapter)

# Now client uses custom pool size
markets = client.get_markets()
```

---

## References

### Documentation

- **API_INTEGRATION_GUIDE_V2.0.md** - Kalshi API reference docs
- **KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md** - Decimal pricing reference
- **KALSHI_MARKET_TERMINOLOGY_GUIDE_V1.0.md** - YES/NO vs BUY/SELL clarification
- **CONFIGURATION_GUIDE_V3.1.md** - Environment variable setup
- **CONFIG_LOADER_USER_GUIDE_V1.0.md** - Configuration loading API

### Requirements

- **REQ-API-001:** Kalshi API Integration
- **REQ-API-002:** RSA-PSS Authentication
- **REQ-API-005:** API Rate Limit Management
- **REQ-API-006:** API Error Handling
- **REQ-SYS-003:** Decimal Precision for Prices

### Architectural Decisions

- **ADR-002:** Decimal Precision for Financial Calculations
- **ADR-047:** RSA-PSS Authentication Implementation
- **ADR-048:** Decimal-First Response Parsing
- **ADR-049:** Retry Logic with Exponential Backoff
- **ADR-050:** Exponential Backoff Strategy
- **ADR-051:** Token Bucket Rate Limiting

### Development Patterns

- **Pattern 1:** Decimal Precision (NEVER USE FLOAT) - CLAUDE.md
- **Pattern 4:** Security (NO CREDENTIALS IN CODE) - CLAUDE.md
- **Pattern 6:** TypedDict for API Responses - CLAUDE.md

### Source Code

- **src/precog/api_connectors/kalshi_client.py** - KalshiClient implementation (642 lines, 97.91% coverage)
- **src/precog/api_connectors/kalshi_auth.py** - RSA-PSS authentication
- **src/precog/api_connectors/rate_limiter.py** - Token bucket rate limiting
- **src/precog/api_connectors/types.py** - TypedDict response types
- **tests/unit/api_connectors/test_kalshi_client.py** - KalshiClient tests (100% coverage)

---

## Summary

★ **Insight ─────────────────────────────────────**
**Key Takeaways:**

1. **Demo First, Always:**
   - ALWAYS develop against demo environment
   - Only use prod after thorough testing
   - Demo uses fake money, identical API

2. **Automatic Features (You Don't Think About):**
   - RSA-PSS authentication (tokens auto-refresh)
   - Rate limiting (100 req/min compliance)
   - Decimal conversion (all prices → Decimal)
   - Retry logic (exponential backoff for 5xx errors)
   - Connection pooling (faster requests)

3. **Common Operations:**
   ```python
   # Initialize
   client = KalshiClient("demo")

   # Get markets
   markets = client.get_markets(series_ticker="KXNFLGAME")

   # Get balance
   balance = client.get_balance()

   # Get positions
   positions = client.get_positions(status="open")

   # Clean up
   client.close()
   ```

4. **Error Handling:**
   - 5xx errors: Auto-retry with exponential backoff
   - 4xx errors: Fail immediately (client error)
   - 429 errors: Honor Retry-After header
   - Timeout: Fail after 30 seconds

5. **Best Practices:**
   - Always call `client.close()` (use try/finally)
   - Check environment (demo vs prod)
   - Handle exceptions (HTTPError, Timeout, RequestException)
   - Use Decimal for all price calculations
   - Paginate for large result sets (limit=200 max)

─────────────────────────────────────────────────

**END OF KALSHI_CLIENT_USER_GUIDE_V1.0.md**
