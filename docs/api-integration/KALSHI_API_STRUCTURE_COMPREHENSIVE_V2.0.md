# Kalshi API Technical Reference for Trading System Integration

**Version:** 2.0 (Comprehensive Merge)  
**Last Updated:** October 7, 2025  
**API Version:** v2  
**Official Documentation:** https://docs.kalshi.com

---

## Executive Summary

Kalshi provides a comprehensive RESTful API with WebSocket support for prediction market trading. **Critical correction: Kalshi uses RSA-PSS signature authentication (NOT HMAC-SHA256)**, prices are denominated in **integer cents (0-100)**, and orderbooks return only bids due to binary market structure. [Kalshi +3](https://docs.kalshi.com/api-reference/websockets/market-ticker) The platform supports real-time data streaming via WebSocket channels and provides granular market data across sports, economics, politics, and other categories. [Kalshi](https://help.kalshi.com/kalshi-api) [Sacra](https://sacra.com/c/kalshi/)

**Key Technical Specifications:**
- **Authentication**: RSA-PSS with SHA256 (30-minute token expiration)
- **Base URLs**: 
  - Production REST: `https://api.elections.kalshi.com/trade-api/v2`
  - Production WebSocket: `wss://trading-api.kalshi.com/trade-api/ws/v2`
  - Demo REST: `https://demo-api.kalshi.co/trade-api/v2`
  - Demo WebSocket: `wss://demo-api.kalshi.co/trade-api/ws/v2`
- **Rate Limits**: Tiered (Basic, Advanced, Premier, Prime)
- **Price Format**: ⚠️ **TRANSITIONING FROM INTEGER CENTS TO SUB-PENNY DECIMALS**
- **Market Structure**: Series → Events → Markets (YES/NO binary outcomes)
- **Contract Settlement**: 100 cents ($1.00)

### ⚠️ CRITICAL: Sub-Penny Pricing Transition

**Kalshi is transitioning from integer cents to sub-penny pricing.** This affects all price handling in your system.

**Current State (as of October 2025):**
- Minimum tick size: 1 cent
- Integer cents fields (`yes_bid`, `no_bid`) still work
- Decimal dollar fields (`yes_bid_dollars`, `no_bid_dollars`) also available

**Future State ("near future" per Kalshi):**
- Sub-penny pricing will be introduced (e.g., 42.75¢)
- Integer cents fields will be **DEPRECATED**
- Only decimal dollar fields will be supported

**Migration Requirements for Precog:**

1. ✅ **Always parse `_dollars` fields from API responses**
   ```python
   # ✅ CORRECT (future-proof):
   yes_bid = Decimal(market["yes_bid_dollars"])  # "0.4275"
   
   # ❌ WRONG (will break):
   yes_bid = market["yes_bid"]  # 43 (deprecated soon)
   ```

2. ✅ **Store prices as DECIMAL(10,4) in database**
   ```sql
   CREATE TABLE markets (
     ticker VARCHAR(100) PRIMARY KEY,
     yes_bid DECIMAL(10,4) NOT NULL,  -- Supports 0.4275
     yes_ask DECIMAL(10,4) NOT NULL,
     CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999)
   );
   ```

3. ✅ **Use decimal strings in order placement**
   ```json
   {
     "ticker": "MARKET-YES",
     "side": "yes",
     "action": "buy",
     "count": 10,
     "yes_price_dollars": "0.4275"
   }
   ```

4. ✅ **Update odds calculations for sub-penny precision**
   - Expected value calculations with 4 decimal places
   - Spread calculations: 0.4300 - 0.4275 = 0.0025 (0.25¢)

**Why This Matters:**
- **Tighter spreads**: 0.25¢ spreads possible (vs. 1¢ minimum now)
- **Better price discovery**: More granular pricing
- **Future-proof design**: No migration needed when Kalshi launches sub-penny

**Precog Implementation:**
- All Phase 0 documents use DECIMAL(10,4) for prices
- All Phase 2+ code parses `_dollars` fields exclusively
- Database schema supports sub-penny from Day 1

**Reference:** [Kalshi Sub-Penny Pricing Documentation](https://docs.kalshi.com/getting_started/subpenny_pricing)

---

## Table of Contents

1. [Authentication (RSA-PSS)](#authentication-rsa-pss)
2. [API Endpoints](#api-endpoints)
3. [Market Structure & Hierarchy](#market-structure--hierarchy)
4. [WebSocket Integration](#websocket-integration)
5. [Trading Operations](#trading-operations)
6. [Position & Portfolio Management](#position--portfolio-management)
7. [Historical Data & Analytics](#historical-data--analytics)
8. [Orderbook Structure](#orderbook-structure)
9. [Rate Limits & Best Practices](#rate-limits--best-practices)
10. [Error Handling](#error-handling)
11. [Database Schema Considerations](#database-schema-considerations)

---

## Authentication (RSA-PSS)

### Critical: RSA-PSS Not HMAC-SHA256

**Kalshi uses RSA-PSS signature authentication** with SHA256 hashing, PSS padding with MGF1(SHA256), and salt length set to DIGEST_LENGTH. [kalshi](https://docs.kalshi.com/getting_started/quick_start_authenticated_requests) [Zuplo](https://zuplo.com/learning-center/kalshi-api) This is fundamentally different from HMAC-SHA256 and requires RSA key handling.

### Required Headers

Every authenticated request must include three specific headers:

1. **`KALSHI-ACCESS-KEY`**: Your UUID-format API key
2. **`KALSHI-ACCESS-TIMESTAMP`**: Current POSIX timestamp in milliseconds
3. **`KALSHI-ACCESS-SIGNATURE`**: Base64-encoded RSA signature

### Signature Construction

The message to sign follows this exact pattern:
```
timestamp + method + path
```

**Example:**
```
1703123456789GET/trade-api/v2/portfolio/balance
```

Note: No delimiters, method must be uppercase, path includes everything after the domain.

### Python Implementation

```python
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

def generate_rsa_signature(private_key_path: str, timestamp: int, method: str, path: str) -> str:
    """
    Generate RSA-PSS signature for Kalshi API request.
    
    Args:
        private_key_path: Path to RSA private key (.pem file)
        timestamp: Current time in milliseconds (int(time.time() * 1000))
        method: HTTP method in UPPERCASE (GET, POST, DELETE)
        path: API endpoint path (e.g., '/trade-api/v2/markets')
    
    Returns:
        Base64-encoded signature string
    
    Example:
        >>> timestamp = int(time.time() * 1000)
        >>> sig = generate_rsa_signature(
        ...     private_key_path="./kalshi_private.pem",
        ...     timestamp=timestamp,
        ...     method="GET",
        ...     path="/trade-api/v2/markets"
        ... )
    """
    # Construct message
    message = f"{timestamp}{method.upper()}{path}"
    
    # Load private key
    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )
    
    # Sign with RSA-PSS
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )
    
    # Return base64-encoded signature
    return base64.b64encode(signature).decode('utf-8')

# Usage example
import requests

API_KEY = "your-uuid-api-key"
PRIVATE_KEY_PATH = "./kalshi_private.pem"
BASE_URL = "https://api.elections.kalshi.com"

timestamp = int(time.time() * 1000)
path = "/trade-api/v2/portfolio/balance"

signature = generate_rsa_signature(
    private_key_path=PRIVATE_KEY_PATH,
    timestamp=timestamp,
    method="GET",
    path=path
)

headers = {
    "KALSHI-ACCESS-KEY": API_KEY,
    "KALSHI-ACCESS-TIMESTAMP": str(timestamp),
    "KALSHI-ACCESS-SIGNATURE": signature,
    "Content-Type": "application/json"
}

response = requests.get(f"{BASE_URL}{path}", headers=headers)
print(response.json())
```

### Critical Security Notes

1. **Private key cannot be retrieved after initial generation** - store it immediately and securely [Kalshi](https://docs.kalshi.com/getting_started/quick_start_authenticated_requests)
2. **Tokens expire every 30 minutes** - implement automatic re-login [Zuplo](https://zuplo.com/learning-center/kalshi-api)
3. **Store keys in environment variables or secure vaults** - never hardcode
4. **Use separate keys for demo and production**
5. **Implement IP restrictions where available**

---

## API Endpoints

### Market Discovery

**Get Markets**
```
GET /trade-api/v2/markets
```

Query Parameters:
- `limit`: 1-1000 (default 100)
- `cursor`: Pagination token
- `event_ticker`: Filter by specific event
- `series_ticker`: Filter by series
- `min_close_ts`: Timestamp filter (milliseconds)
- `max_close_ts`: Timestamp filter (milliseconds)
- `status`: `unopened`, `open`, `closed`, `settled`
- `tickers`: Comma-separated list for specific markets

[kalshi +2](https://docs.kalshi.com/api-reference/market/get-markets)

**Get Single Market**
```
GET /trade-api/v2/markets/{ticker}
```

No authentication required for public markets. [Kalshi +2](https://docs.kalshi.com/api-reference/market/get-market)

**Get Events**
```
GET /trade-api/v2/events
```

Query Parameters:
- `series_ticker`: Filter by series
- `status`: Event status filter
- `with_nested_markets`: Include market objects (boolean)

[Kalshi](https://docs.kalshi.com/api-reference/market/get-events)

**Get Series**
```
GET /trade-api/v2/series
```

Query Parameters:
- `category`: Filter by category
- `tags`: Filter by tags
- `with_product_metadata`: Include metadata (boolean)

[Kalshi](https://docs.kalshi.com/api-reference/market/get-series)

### Trading Endpoints

**Place Order**
```
POST /trade-api/v2/portfolio/orders
```

Required fields:
- `ticker`: Market identifier
- `side`: "yes" or "no"
- `action`: "buy" or "sell"
- `count`: Number of contracts

Price specification (choose ONE):
- `yes_price`: Integer cents 1-99
- `no_price`: Integer cents 1-99
- `yes_price_dollars`: Decimal string
- `no_price_dollars`: Decimal string

Optional fields:
- `type`: "limit" (default) or "market"
- `client_order_id`: Max 64 alphanumeric + '_' + '-'
- `expiration_ts`: Time-limited orders (milliseconds)
- `time_in_force`: "fill_or_kill" or "immediate_or_cancel"
- `buy_max_cost`: Cap spending for market buy + FoK
- `post_only`: true (reject if crosses spread)
- `sell_position_capped`: true (prevent overselling with IoC)

[Kalshi](https://docs.kalshi.com/api-reference/portfolio/create-order)

**Get Order Status**
```
GET /trade-api/v2/portfolio/orders/{order_id}
```

Response includes:
- `status`: pending, resting, executed, canceled
- `initial_count`: Original size
- `fill_count`: Contracts executed
- `remaining_count`: Unfilled
- `queue_position`: Placement in orderbook
- Maker/taker fee breakdown

[Kalshi](https://docs.kalshi.com/api-reference/portfolio/get-orders)

**Cancel Order**
```
DELETE /trade-api/v2/portfolio/orders/{order_id}
```

**Decrease Order Size**
```
POST /trade-api/v2/portfolio/orders/{order_id}/decrease
```

Parameters:
- `reduce_by`: Decrement amount
- OR `reduce_to`: Target final count

[Kalshi](https://docs.kalshi.com/api-reference/portfolio/decrease-order)

**Batch Operations** (Advanced tier in production, all users in demo)
```
POST /trade-api/v2/portfolio/orders/batched
DELETE /trade-api/v2/portfolio/orders/batched
```

Maximum 20 orders per batch. [Kalshi](https://docs.kalshi.com/api-reference/portfolio/batch-create-orders)

---

## Market Structure & Hierarchy

### Hierarchical Organization

Kalshi markets follow a three-tier structure:

```
Series (Template)
├── Event (Specific Occurrence)
│   ├── Market 1 (Outcome A)
│   ├── Market 2 (Outcome B)
│   └── Market 3 (Outcome C)
```

**Example:**
```
Series: KXNFLGAME (All NFL games)
├── Event: kxnflgame-25oct05nebuf (Patriots @ Bills, Oct 5)
│   ├── Market: KXNFLGAME-25oct05nebuf-NE (Patriots win)
│   ├── Market: KXNFLGAME-25oct05nebuf-BUF (Bills win)
│   └── Market: KXNFLGAME-25oct05nebuf-O48 (Over 48 points)
```

### Ticker Conventions

**Series Tickers:** `KX[CATEGORY][TYPE]`
- NFL: `KXNFLGAME`, `KXSB` (Super Bowl)
- NBA: `KXNBA`, `KXNBAEAST`, `KXNBAWEST`
- Politics: `KXPRES`, `KXSENATE`, `KXHOUSE`
- Economics: `KXCPI`, `KXGDP`

**Event Tickers:** `[series]-[date][teams]`
- Format: lowercase, hyphen-separated
- Example: `kxnflgame-25oct05nebuf`

**Market Tickers:** `[event]-[outcome]`
- YES market: `KXNFLGAME-25oct05nebuf-NE-YES`
- NO market: Inverse pricing of YES

### Categories

Nine major categories with subdivisions:
1. **Sports**: NFL, NBA, MLB, NHL, soccer, tennis, golf, F1, UFC, college sports
2. **Politics**: Elections, appointments, legislation
3. **Culture**: Entertainment, awards, media
4. **Crypto**: Bitcoin, Ethereum, blockchain events
5. **Climate**: Weather, natural disasters, environmental
6. **Economics**: CPI, GDP, unemployment, Fed decisions
7. **Financials**: Stock prices, corporate events
8. **Health**: Medical breakthroughs, disease tracking
9. **Tech & Science**: Product launches, research milestones

[WTOPTV](https://wtop.com/sports/2025/07/kalshi-promo-code-wtop-heres-how-to-get-top-prediction-market-sign-up-bonus/)

---

## Market Data Field Structure

### Complete Field Reference

**Core Identifiers:**
- `ticker`: Unique market identifier
- `event_ticker`: Parent event reference
- `market_type`: Type classification
- `title`: Human-readable question
- `subtitle`: Additional context
- `yes_sub_title`: YES outcome description
- `no_sub_title`: NO outcome description

**Timestamps** (ISO 8601 format: `2023-11-07T05:31:56Z`):
- `open_time`: When trading begins
- `close_time`: When trading stops
- `expiration_time`: Target settlement completion
- `latest_expiration_time`: Maximum settlement window
- `settlement_timer_seconds`: Estimated settlement duration

**Pricing Fields** (ALL in integer cents 0-100):
- `yes_bid`: Best YES bid price
- `yes_ask`: Best YES ask price
- `no_bid`: Best NO bid price
- `no_ask`: Best NO ask price
- `last_price`: Most recent trade execution
- `previous_yes_bid`: Historical best bid
- `previous_yes_ask`: Historical best ask
- `previous_price`: Historical last trade

**Dollar Equivalents** (fixed-point decimal strings):
- `yes_bid_dollars`: e.g., "0.4200"
- `yes_ask_dollars`: e.g., "0.4400"
- Similar for all price fields

**Volume & Liquidity:**
- `volume`: Total contracts traded (all-time)
- `volume_24h`: Trailing 24-hour volume
- `liquidity`: Current market depth
- `open_interest`: Total contracts held

**Settlement Fields** (populated after resolution):
- `result`: "yes" or "no"
- `settlement_value`: Payout in cents
- `can_close_early`: Early settlement flag
- `expiration_value`: Final determined value

**Status Progression:**
- `unopened` → `open` → `closed` → `settled`

**Configuration:**
- `response_price_units`: Price unit format
- `notional_value`: Contract value (typically 100 cents)
- `tick_size`: Minimum price increment
- `risk_limit_cents`: Position limits
- `category`: Market category
- `rules_primary`: Settlement rules (primary)
- `rules_secondary`: Settlement rules (additional)

[Kalshi +4](https://docs.kalshi.com/api-reference/market/get-markets)

---

## WebSocket Integration

### Connection & Authentication

WebSocket URL: `wss://trading-api.kalshi.com/trade-api/ws/v2` (production)

Authentication occurs during handshake using credentials from REST API login. [Kalshi +3](https://docs.kalshi.com/api-reference/websockets/market-ticker)

### Available Channels

1. **orderbook_delta**: Incremental order book updates
2. **ticker**: Market price and volume changes
3. **trades**: Public trade executions
4. **fills**: User-specific fill notifications
5. **orderbook_snapshot**: Full order book snapshots
6. **market_lifecycle**: Market status changes
7. **portfolio_positions**: Position updates

[Kalshi](https://docs.kalshi.com/api-reference/websockets/market-ticker) [Zuplo](https://zuplo.com/learning-center/kalshi-api)

### Subscription Commands

**Subscribe:**
```json
{
  "id": 1,
  "cmd": "subscribe",
  "params": {
    "channels": ["orderbook_delta", "ticker"],
    "market_ticker": "CPI-22DEC-TN0.1"
  }
}
```

**Unsubscribe:**
```json
{
  "id": 124,
  "cmd": "unsubscribe",
  "params": {
    "sids": [1, 2]
  }
}
```

**List Subscriptions:**
```json
{
  "id": 3,
  "cmd": "list_subscriptions"
}
```

[Kalshi](https://docs.kalshi.com/api-reference/websockets/websocket-connection)

### Response Handling

**Success:**
```json
{
  "id": 1,
  "type": "subscribed",
  "sid": 12345
}
```

**Error:**
```json
{
  "id": 1,
  "type": "error",
  "code": 6,
  "msg": "Already subscribed"
}
```

[Kalshi](https://docs.kalshi.com/api-reference/websockets/websocket-connection)

---

## Trading Operations

### Order Types

**Limit Order** (default):
```json
{
  "ticker": "KXNFLGAME-25oct05nebuf-NE-YES",
  "side": "yes",
  "action": "buy",
  "count": 10,
  "yes_price": 42,
  "type": "limit"
}
```

**Market Order:**
```json
{
  "ticker": "KXNFLGAME-25oct05nebuf-BUF-YES",
  "side": "yes",
  "action": "buy",
  "count": 5,
  "type": "market",
  "buy_max_cost": 250
}
```

### Time-in-Force Options

**Fill-or-Kill (FoK):**
- Execute completely immediately or cancel
- Use `time_in_force: "fill_or_kill"`

**Immediate-or-Cancel (IoC):**
- Execute what's available, cancel remainder
- Use `time_in_force: "immediate_or_cancel"`

**Good-Till-Cancelled (GTC):**
- Default behavior for limit orders
- Remains in orderbook until filled or manually canceled

**Post-Only:**
- Reject if would cross spread (ensures maker status)
- Use `post_only: true`

### Idempotency

Use `client_order_id` to prevent duplicate orders:
```json
{
  "ticker": "MARKET-TICKER-YES",
  "side": "yes",
  "action": "buy",
  "count": 10,
  "yes_price": 50,
  "client_order_id": "my-unique-id-12345"
}
```

Max 64 characters: alphanumeric plus '_' and '-'. [Kalshi](https://docs.kalshi.com/api-reference/portfolio/create-order)

---

## Position & Portfolio Management

### Get Positions

```
GET /trade-api/v2/portfolio/positions
```

Filters:
- `ticker`: Specific market
- `event_ticker`: Specific event
- `settlement_status`: "settled" or "unsettled" (default: unsettled)
- `count_filter`: "position", "total_traded", "resting_order_count"

Response structure:
```json
{
  "market_positions": [
    {
      "ticker": "MARKET-YES",
      "position": 25,
      "market_exposure": 1250,
      "total_traded": 50,
      "fees_paid": 15,
      "realized_pnl": 125,
      "resting_orders_count": 2
    }
  ],
  "event_positions": [...]
}
```

[Kalshi](https://docs.kalshi.com/api-reference/portfolio/get-positions)

### Get Balance

```
GET /trade-api/v2/portfolio/balance
```

Returns:
```json
{
  "balance": 10000,
  "updated_ts": 1703123456789
}
```

Balance represents available, unallocated funds (not including unrealized P&L). [Kalshi +2](https://docs.kalshi.com/getting_started/quick_start_authenticated_requests)

### Get Fills (Trade History)

```
GET /trade-api/v2/portfolio/fills
```

Filters:
- `ticker`: Market filter
- `order_id`: Specific order
- `min_ts`, `max_ts`: Timestamp range
- `limit`, `cursor`: Pagination

Fill object:
```json
{
  "fill_id": "abc123",
  "order_id": "ord456",
  "trade_id": "trd789",
  "ticker": "MARKET-YES",
  "side": "yes",
  "action": "buy",
  "count": 5,
  "yes_price": 45,
  "is_taker": true,
  "created_time": "2025-10-07T12:34:56Z"
}
```

[Kalshi](https://docs.kalshi.com/typescript-sdk/api/PortfolioApi)

---

## Historical Data & Analytics

### Candlestick Data

```
GET /trade-api/v2/series/{series_ticker}/markets/{ticker}/candlesticks
```

Required parameters:
- `start_ts`: Unix timestamp (seconds)
- `end_ts`: Unix timestamp (seconds)
- `period_interval`: **1** (1-minute), **60** (hourly), or **1440** (daily)

⚠️ **Only these three intervals are supported**

Response structure:
```json
{
  "candlesticks": [
    {
      "end_period_ts": 1703123460,
      "volume": 1500,
      "open_interest": 5000,
      "price": {
        "open": 42,
        "high": 45,
        "low": 41,
        "close": 44,
        "mean": 43,
        "previous": 42,
        "open_dollars": "0.42",
        "high_dollars": "0.45",
        "low_dollars": "0.41",
        "close_dollars": "0.44"
      },
      "yes_bid": {...},
      "yes_ask": {...}
    }
  ]
}
```

[kalshi](https://docs.kalshi.com/api-reference/market/get-market-candlesticks)

### Trade History

```
GET /trade-api/v2/markets/trades
```

Filters:
- `ticker`: Market filter
- `min_ts`, `max_ts`: Timestamp range (milliseconds)
- `limit`: 1-1000 (default 100)
- `cursor`: Pagination

Trade object:
```json
{
  "trade_id": "trd123",
  "ticker": "MARKET-YES",
  "yes_price": 45,
  "no_price": 55,
  "count": 10,
  "taker_side": "yes",
  "created_time": "2025-10-07T12:34:56Z"
}
```

[Kalshi +2](https://docs.kalshi.com/api-reference/market/get-trades)

### Settlement Data

```
GET /trade-api/v2/portfolio/settlements
```

Filters:
- `ticker`, `event_ticker`: Market/event filters
- `min_ts`, `max_ts`: Timestamp range
- Pagination via `limit`, `cursor`

Settlement object:
```json
{
  "market_result": "yes",
  "settled_time": "2025-10-07T20:00:00Z",
  "yes_count": 25,
  "no_count": 0,
  "yes_total_cost": 1050,
  "no_total_cost": 0,
  "value": 2500,
  "revenue": 1450
}
```

[Kalshi](https://docs.kalshi.com/api-reference/portfolio/get-settlements)

---

## Orderbook Structure

### Critical: Bids Only, Not Asks

**Kalshi orderbooks return only bids, not asks**, due to binary market structure. A YES bid at 42¢ mathematically equals a NO ask at 58¢ (100 - 42). [Kalshi +2](https://docs.kalshi.com/api-reference/market/get-market-order-book)

### Get Orderbook

```
GET /trade-api/v2/markets/{ticker}/orderbook
```

Optional parameter:
- `depth`: Max 100 (price levels per side)

Response structure:
```json
{
  "yes": [
    [40, 100],
    [41, 250],
    [42, 500]
  ],
  "no": [
    [56, 150],
    [57, 300],
    [58, 450]
  ],
  "yes_dollars": [
    {"Dollars": "0.40", "Count": 100},
    {"Dollars": "0.41", "Count": 250},
    {"Dollars": "0.42", "Count": 500}
  ],
  "no_dollars": [...]
}
```

Arrays sorted from **worst to best prices** (lowest to highest). Best bid is the **last element**.

[Kalshi +2](https://docs.kalshi.com/getting_started/orderbook_responses)

### Calculating Spread and Best Prices

```python
def parse_orderbook(orderbook):
    """
    Calculate best prices and spread from Kalshi orderbook.
    
    Returns:
        dict with best_yes_bid, best_yes_ask, best_no_bid, best_no_ask, spread
    """
    # Best bids are last elements (highest price)
    best_yes_bid = orderbook["yes"][-1][0] if orderbook["yes"] else 0
    best_no_bid = orderbook["no"][-1][0] if orderbook["no"] else 0
    
    # Calculate asks using complement
    best_yes_ask = 100 - best_no_bid
    best_no_ask = 100 - best_yes_bid
    
    # Spread
    spread = best_yes_ask - best_yes_bid
    
    return {
        "best_yes_bid": best_yes_bid,
        "best_yes_ask": best_yes_ask,
        "best_no_bid": best_no_bid,
        "best_no_ask": best_no_ask,
        "spread": spread
    }

# Example
orderbook = {
    "yes": [[40, 100], [41, 250], [42, 500]],
    "no": [[56, 150], [57, 300], [58, 450]]
}

prices = parse_orderbook(orderbook)
# {
#   "best_yes_bid": 42,
#   "best_yes_ask": 44,  # 100 - 56
#   "best_no_bid": 58,
#   "best_no_ask": 58,    # 100 - 42
#   "spread": 2
# }
```

[Kalshi](https://docs.kalshi.com/getting_started/orderbook_responses)

---

## Rate Limits & Best Practices

### Rate Limit Tiers

Kalshi uses four tiers with distinct read/write limits:

1. **Basic**: Available upon signup completion
2. **Advanced**: TypeForm application for enhanced limits
3. **Premier**: Requires 3.75% monthly exchange volume + technical competency
4. **Prime**: Requires 7.5% monthly volume + highest technical standards

[Kalshi](https://docs.kalshi.com/getting_started/rate_limits)

Write limits apply only to order placement, modification, and cancellation. Read endpoints have separate limits. [kalshi](https://docs.kalshi.com/getting_started/rate_limits)

### Best Practices

**Polling Intervals:**
- Active trading: 1-5 seconds
- Passive monitoring: 30-60 seconds
- Balance/portfolio: 5-30 seconds during active trading
- Order status: 2-5 seconds until filled/canceled

**However:** **WebSocket connections strongly preferred** over REST polling for real-time updates. [Zuplo](https://zuplo.com/learning-center/kalshi-api)

**Connection Management:**
- Re-login before 30-minute token expiration
- Implement heartbeat mechanisms for WebSockets
- Automatic reconnection with exponential backoff
- Message buffering during brief disconnections

**Retry Strategies:**
- Start at 1 second, double each attempt
- Maximum 60-second backoff
- 5-10 maximum retries
- Retry 429 (rate limit) after waiting
- Retry 500/503 (server errors) with backoff
- Do NOT retry 401 (fix credentials first)
- Do NOT retry 400/404 (fix request parameters)

[Zuplo](https://zuplo.com/blog/2025/04/02/kalshi-api)

**Request Optimization:**
- Queue requests to spread load
- Cache static data (market metadata)
- Monitor rate limit headers
- Use batch operations where available

**Security:**
- Store credentials in environment variables/vaults
- Never hardcode API keys
- Exclude private keys from version control
- Rotate keys periodically
- Separate demo and production keys
- Configure IP restrictions
- Log all API requests for auditing

[Zuplo](https://zuplo.com/learning-center/kalshi-api)

### Pagination

Kalshi uses **cursor-based pagination** to prevent data drift.

Workflow:
1. Make initial request without cursor parameter
2. Extract `cursor` field from response
3. Pass cursor to next request
4. Repeat until cursor is empty/absent

Limits by endpoint:
- Markets: 1-1000 (default 100)
- Events: 1-200 (default 100)
- Trades: 1-1000 (default 100)

[Zuplo +2](https://zuplo.com/blog/2025/04/02/kalshi-api)

---

## Error Handling

### HTTP Status Codes

**Success:**
- 200: Data retrieval successful
- 201: Resource created successfully
- 204: Operation successful (no response body)

**Client Errors:**
- 400: Bad request (validation failure)
- 401: Authentication failure (invalid credentials)
- 403: Forbidden (insufficient permissions)
- 404: Resource not found
- 429: Rate limit exceeded

**Server Errors:**
- 500: Internal server error
- 503: Service unavailable (maintenance)

[GitHub](https://github.com/AndrewNolte/KalshiPythonClient/blob/main/docs/AuthApi.md)

### Error Response Structure

```json
{
  "code": "error_identifier",
  "message": "Human-readable description",
  "details": "Additional context",
  "service": "Originating service name"
}
```

[GitHub](https://github.com/AndrewNolte/KalshiPythonClient/blob/main/docs/AuthApi.md)

### Validation Checks

**Market Data:**
- YES bid + NO bid ≈ 100 (accounting for spread)
- Timestamp sequence logical (open < close < expiration)
- Price values within 0-100 range
- Volume/open interest consistency

**Orderbook:**
- YES bid at X + NO bid at Y ≈ 100
- Spread = (100 - NO bid) - YES bid
- Best bids are last elements in arrays
- Depth matches requested limits

**Cross-Endpoint Consistency:**
- Market listings match individual queries
- Event aggregations match constituent markets
- Position data reconciles with fills

[Zuplo](https://zuplo.com/learning-center/kalshi-api)

---

## Database Schema Considerations

### Market Tables

**String Fields:**
- `ticker` (PRIMARY KEY, VARCHAR(100))
- `event_ticker` (VARCHAR(100), FOREIGN KEY)
- `market_type` (VARCHAR(50))
- `title` (VARCHAR(500))
- `subtitle` (VARCHAR(500))
- `yes_sub_title` (VARCHAR(200))
- `no_sub_title` (VARCHAR(200))
- `category` (VARCHAR(50))
- `status` (VARCHAR(20))

**Timestamp Fields** (DATETIME, UTC):
- `open_time`
- `close_time`
- `expiration_time`
- `latest_expiration_time`
- `last_update_time`

Index on time-range queries.

**Price Fields** (INTEGER, 0-100 constraint):
- `yes_bid`
- `yes_ask`
- `no_bid`
- `no_ask`
- `last_price`
- `previous_price`

Optional DECIMAL(10,4) for dollar variants.

**Volume Metrics** (INTEGER or BIGINT):
- `volume`
- `volume_24h`
- `open_interest`
- `liquidity`

**Settlement Fields:**
- `result` (VARCHAR(3), CHECK: "yes" or "no", NULLABLE)
- `settlement_value` (INTEGER, NULLABLE)
- `can_close_early` (BOOLEAN)

**Configuration:**
- `notional_value` (INTEGER)
- `tick_size` (INTEGER)
- `risk_limit_cents` (INTEGER)
- `settlement_timer_seconds` (INTEGER)
- `rules_primary` (TEXT)
- `rules_secondary` (TEXT)

### Order Tables

**String Fields:**
- `order_id` (PRIMARY KEY, VARCHAR(100))
- `client_order_id` (VARCHAR(64), INDEX for idempotency)
- `ticker` (FOREIGN KEY to markets)
- `side` (VARCHAR(3))
- `action` (VARCHAR(4))
- `type` (VARCHAR(10))
- `status` (VARCHAR(20))

**Count Fields** (INTEGER):
- `initial_count`
- `fill_count`
- `remaining_count`
- `queue_position`

**Cost Tracking** (INTEGER cents):
- `maker_fees`
- `taker_fees`
- `maker_fill_cost`
- `taker_fill_cost`

**Timestamps:**
- `created_time`
- `expiration_time`
- `last_update_time`

### Position Tables

**String Fields:**
- `ticker` (FOREIGN KEY)

**Integer Fields:**
- `position` (can be negative)
- `market_exposure`
- `total_traded`
- `fees_paid`
- `realized_pnl`
- `resting_orders_count`

**Timestamp:**
- `last_updated_ts`

### Fill Tables

**String Fields:**
- `fill_id` (PRIMARY KEY)
- `order_id` (FOREIGN KEY)
- `trade_id`
- `ticker` (FOREIGN KEY)
- `side`
- `action`

**Integer Fields:**
- `count`
- `yes_price`
- `no_price`

**Boolean:**
- `is_taker`

**Timestamp:**
- `created_time`

### Series & Event Tables

**Series:**
- `ticker` (PRIMARY KEY)
- `title`
- `category`
- `frequency`
- `fee_type`
- `fee_multiplier` (INTEGER)
- URLs (TEXT)
- JSONB/JSON: `product_metadata`, `settlement_sources`, `tags`, `additional_prohibitions`

**Events:**
- `event_ticker` (PRIMARY KEY)
- `series_ticker` (FOREIGN KEY)
- `title`
- `category`
- Timestamps
- Optional nested markets

[Kalshi +2](https://docs.kalshi.com/api-reference/market/get-series)

---

## Configuration Values for platforms.yaml

| Configuration Item | Production Value | Demo Value |
|-------------------|------------------|------------|
| **REST Base URL** | `https://api.elections.kalshi.com/trade-api/v2` | `https://demo-api.kalshi.co/trade-api/v2` |
| **WebSocket URL** | `wss://trading-api.kalshi.com/trade-api/ws/v2` | `wss://demo-api.kalshi.co/trade-api/ws/v2` |
| **Authentication Method** | RSA-PSS with SHA256 | Same |
| **Signature Padding** | PSS with MGF1(SHA256), salt_length=DIGEST_LENGTH | Same |
| **Token Expiration** | 30 minutes | Same |
| **Price Format** | Integer cents (0-100) | Same |
| **Price Decimal Range** | 0.01 to 0.99 | Same |
| **Contract Settlement** | 100 cents ($1.00) | Same |
| **Timestamp Format (Auth)** | POSIX milliseconds | Same |
| **Timestamp Format (Response)** | RFC3339/ISO 8601 | Same |
| **Default Pagination Limit** | 100 | Same |
| **Max Pagination (Markets)** | 1000 | Same |
| **Max Pagination (Events)** | 200 | Same |
| **Max Batch Order Size** | 20 orders | Same |
| **Candlestick Intervals** | 1, 60, 1440 minutes | Same |

---

## Sports Market Structure

### NFL Markets

**Series Patterns:**
- `KXNFLGAME`: Individual games
- `KXSB`: Super Bowl
- `KXNFLMVP`: MVP awards

**Market Types:**
- Moneyline (team win/loss)
- Point spreads
- Totals (over/under)
- Touchdown props
- Statistical props (passing, rushing, receiving, kicking)
- Parlays (launched September 2025)

[Legal Sports Report](https://www.legalsportsreport.com/239558/kalshi-expanding-college-nfl-prediction-markets/)

**Lifecycle:**
- Futures: Open before season
- Game markets: ~1 week before kickoff
- Peak volume: 3-4 days before game (70%+ in game week)
- Close: At kickoff
- Settlement: After official results

**Volume Patterns:**
- Primetime games: 2-3x regular games
- Eagles-Cowboys Week 1: $4M
- Lions-Ravens MNF: $49.5M peak

[Odds Shark](https://www.oddsshark.com/industry-news/over-270M-traded-kalshi-nfl) [Covers](https://www.covers.com/industry/kalshi-nfl-week-1-prediction-markets-handle-eagles-cowboys-sept-2025)

### NBA Markets

**Series Patterns:**
- `KXNBA`: Championship futures
- `KXNBAEAST`, `KXNBAWEST`: Conference markets

**Launch Timeline:**
- Championship futures: Off-season
- Single-game markets: April 15, 2025 (playoffs)
- Regular season expansion: Later

[Substack](https://closingline.substack.com/p/the-early-line-understanding-kalshi-trading-volume)

---

## Conclusion: System Integration Readiness

Kalshi's API provides comprehensive access to prediction market data and trading with clear, well-documented endpoints. [Sacra](https://sacra.com/c/kalshi/) The critical architectural decisions are:

1. **Use RSA-PSS authentication** (not HMAC-SHA256)
2. **Handle all prices as integer cents** (0-100)
3. **Calculate asks from bids** (100 - bid)
4. **Prefer WebSocket over REST polling** for real-time data
5. **Implement 30-minute token refresh**
6. **Use batch operations** for efficiency (Advanced tier)
7. **Validate data consistency** across endpoints

The combination of REST endpoints, WebSocket feeds, historical data, and robust trading operations provides everything needed for sophisticated prediction market trading system development. [Zuplo](https://zuplo.com/learning-center/kalshi-api)

---

## Reference Implementation Checklist

✅ **Authentication**
- [ ] RSA-PSS signature generation
- [ ] Private key secure storage
- [ ] 30-minute token refresh
- [ ] Environment-based credentials

✅ **Market Data**
- [ ] REST polling with appropriate intervals
- [ ] WebSocket subscription for real-time updates
- [ ] Orderbook parsing (bid-only structure)
- [ ] Historical candlestick retrieval

✅ **Trading**
- [ ] Order placement with idempotency
- [ ] Order status monitoring
- [ ] Position tracking
- [ ] Fill history logging

✅ **Data Validation**
- [ ] Price consistency (YES + NO ≈ 100)
- [ ] Timestamp sequence validation
- [ ] Cross-endpoint reconciliation

✅ **Error Handling**
- [ ] Retry logic with exponential backoff
- [ ] Rate limit response handling
- [ ] Authentication error recovery
- [ ] Comprehensive logging

✅ **Database Schema**
- [ ] Market data tables (with versioning)
- [ ] Order/position tables
- [ ] Fill history tables
- [ ] Series/event hierarchy

---

**Document Status:** ✅ Comprehensive (Merged v1.0 + v2.0)  
**Last Validation:** October 7, 2025  
**Next Review:** Phase 2 implementation start  
**Maintainer:** Precog Architecture Team
