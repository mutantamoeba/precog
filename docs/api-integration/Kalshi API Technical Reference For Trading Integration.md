# Kalshi API Technical Reference for Trading System Integration

Kalshi uses **RSA-PSS signature authentication** (not HMAC-SHA256) with comprehensive REST and WebSocket APIs for prediction market trading. Prices are denominated in **integer cents (0-100)**, orderbooks return only bids due to binary market structure, and the platform supports real-time data streaming via WebSocket channels. The API provides granular market data across sports, economics, politics, and other categories, with dedicated endpoints for trading, historical data, and portfolio management.

## Core authentication and connection infrastructure

Kalshi's authentication system requires three specific headers for every authenticated request: `KALSHI-ACCESS-KEY` containing your UUID-format API key, `KALSHI-ACCESS-TIMESTAMP` with the current POSIX timestamp in milliseconds, and `KALSHI-ACCESS-SIGNATURE` containing a Base64-encoded RSA signature. The signature construction follows a precise pattern: concatenate the timestamp, HTTP method, and path (like `1703123456789GET/trade-api/v2/portfolio/balance`) without delimiters, then sign using RSA-PSS with SHA256 hashing, PSS padding with MGF1(SHA256), and salt length set to DIGEST_LENGTH.

The private key is provided as an RSA_PRIVATE_KEY in PEM format, downloaded as a .key file during API key creation. This key **cannot be retrieved after initial generation**, so immediate secure storage is critical. Authentication tokens expire every **30 minutes**, requiring periodic re-login before expiration in production systems.

For production environments, the REST API base URL is `https://api.elections.kalshi.com/trade-api/v2` (despite the "elections" subdomain, this serves all Kalshi markets). The production WebSocket endpoint is `wss://trading-api.kalshi.com/trade-api/ws/v2`. Demo environments use `https://demo-api.kalshi.co/trade-api/v2` for REST and `wss://demo-api.kalshi.co/trade-api/ws/v2` for WebSocket connections, allowing risk-free testing without real funds.

Rate limits are tiered based on user classification. The Basic tier is available upon completing signup, with standard read and write limits. Advanced tier users complete a TypeForm application for enhanced limits. Premier tier requires 3.75% of monthly exchange traded volume plus technical competency demonstrations. Prime tier requires 7.5% monthly volume and the highest technical standards. Write limits apply only to order placement, modification, and cancellation endpoints, while read endpoints have separate limits. Specific numeric values vary by tier and are not publicly documented, but response headers include rate limit information to help gauge usage.

## WebSocket capabilities for real-time market data

WebSocket connections provide real-time streaming data for multiple channel types. Available channels include `orderbook_delta` for incremental order book updates, `ticker` for market price and volume changes, `trades` for public trade executions, `fills` for user-specific fill notifications, `orderbook_snapshot` for full order book snapshots, and channels for market lifecycle updates and portfolio position changes.

Authentication occurs during the WebSocket handshake using credentials obtained from REST API login. The subscription format uses JSON commands with `cmd` field specifying the operation. To subscribe, send: `{"id": 1, "cmd": "subscribe", "params": {"channels": ["orderbook_delta"], "market_ticker": "CPI-22DEC-TN0.1"}}`. To unsubscribe, send: `{"id": 124, "cmd": "unsubscribe", "params": {"sids": [1, 2]}}` using subscription IDs. You can update subscriptions to add or remove markets dynamically, and list all active subscriptions via the `list_subscriptions` command.

Success responses return subscription confirmations with assigned subscription IDs (sid values). Error responses include error codes and descriptive messages, such as code 6 for "Already subscribed." This real-time capability significantly reduces the need for REST API polling when monitoring active positions or market movements.

## Market data endpoints and response structures

The core market discovery endpoint is `GET /trade-api/v2/markets`, which accepts query parameters including `limit` (1-1000, default 100), `cursor` for pagination, `event_ticker` to filter by specific events, `series_ticker` to filter by series, `min_close_ts` and `max_close_ts` for timestamp filtering, `status` for market state filtering (unopened, open, closed, settled), and `tickers` for requesting specific markets by comma-separated list. Individual market details are retrieved via `GET /trade-api/v2/markets/{ticker}` without authentication required for public markets.

Markets are organized hierarchically under events and series. The `GET /trade-api/v2/events` endpoint returns event data with parameters for `series_ticker`, `status`, and `with_nested_markets` to include market objects within event responses. Individual events are accessed via `GET /trade-api/v2/events/{event_ticker}`. The `GET /trade-api/v2/series` endpoint provides series template data filterable by `category`, `tags`, and `with_product_metadata`.

Market categories span nine major areas: Sports, Politics, Culture, Crypto, Climate, Economics, Financials, Health, and Tech & Science. Sports further subdivides into NFL, NBA, MLB, NHL, soccer, tennis, golf, F1, UFC, and college sports. Each category has distinct series tickers following the pattern `KX[CATEGORY][TYPE]`, such as `KXNFLGAME` for professional football games or `KXNBA` for NBA championships.

## Complete market data field structure

Market objects return comprehensive data with the following exact field names. Core identifiers include `ticker` (unique market identifier), `event_ticker` (parent event reference), `market_type`, `title` (human-readable question), `subtitle`, `yes_sub_title`, and `no_sub_title` describing each outcome side.

Timestamp fields use ISO 8601 format (RFC3339) like `2023-11-07T05:31:56Z`: `open_time` indicates when trading begins, `close_time` marks when trading stops, `expiration_time` targets settlement completion, `latest_expiration_time` provides the maximum settlement window, and `settlement_timer_seconds` estimates settlement duration.

Pricing fields represent the current orderbook state. **All prices are in integer cents from 0-100**, not decimal values. `yes_bid` shows the best YES bid price, `yes_ask` shows the best YES ask, `no_bid` and `no_ask` provide NO side pricing, and `last_price` records the most recent trade execution. Each price field has a corresponding dollar-denominated version like `yes_bid_dollars` showing the same value as a fixed-point decimal string (e.g., "0.4200").

Previous price fields track historical values: `previous_yes_bid`, `previous_yes_ask`, `previous_price`, each with dollar variants. Volume and liquidity metrics include `volume` (total contracts traded all-time), `volume_24h` (trailing 24-hour volume), `liquidity` (current market depth), and `open_interest` (total contracts currently held across all positions).

Settlement fields appear only after market resolution: `result` contains "yes" or "no" indicating the winning side, `settlement_value` shows payout in cents, `can_close_early` indicates early settlement possibility, and `expiration_value` captures the final determined value. The `status` field progresses through "unopened" → "open" → "closed" → "settled".

Configuration fields include `response_price_units`, `notional_value` (contract value in cents, typically 100), `tick_size` (minimum price increment), `risk_limit_cents` (position limits), and `category`. Rule documentation fields `rules_primary` and `rules_secondary` provide settlement determination procedures.

## Historical data and settlement tracking

Historical price data is available through the candlesticks endpoint: `GET /trade-api/v2/series/{series_ticker}/markets/{ticker}/candlesticks`. Required parameters include `start_ts` and `end_ts` as Unix timestamps, plus `period_interval` accepting only three values: **1 for one-minute candles, 60 for hourly, or 1440 for daily**. The response includes arrays of candlestick objects with `end_period_ts`, `volume`, `open_interest`, and nested OHLC data for both `price` (last trades) and `yes_bid`/`yes_ask` levels.

Each OHLC structure contains `open`, `high`, `low`, `close` values in cents, plus corresponding `_dollars` arrays. The `mean` field provides period average, and `previous` shows the preceding close. This enables backtesting, technical analysis, and historical performance evaluation.

Trade history is accessible via `GET /trade-api/v2/markets/trades` with filters for `ticker`, `min_ts`, `max_ts`, `limit` (1-1000, default 100), and `cursor` for pagination. Each trade object includes `trade_id`, `ticker`, `yes_price`, `no_price`, `count` (contracts), `taker_side`, and `created_time`. This provides tick-by-tick transaction data for all public trades.

Settlement data for user positions is retrieved through authenticated endpoint `GET /trade-api/v2/portfolio/settlements`. It accepts filters for `ticker`, `event_ticker`, timestamp ranges, and pagination parameters. Settlement objects show `market_result` (winning side), `settled_time`, position counts (`yes_count`, `no_count`), costs (`yes_total_cost`, `no_total_cost`), final `value` received, and net `revenue` (profit/loss). This enables comprehensive profit/loss tracking and performance analysis.

## Trading operations and order management

Order placement uses `POST /trade-api/v2/portfolio/orders` with required fields: `ticker` (market identifier), `side` ("yes" or "no"), `action` ("buy" or "sell"), and `count` (number of contracts). Exactly one price specification is required, choosing between `yes_price` (integer cents 1-99), `no_price`, `yes_price_dollars`, or `no_price_dollars`.

Optional fields customize order behavior. Set `type` to "limit" (default) or "market" for execution style. The `client_order_id` field (max 64 alphanumeric characters plus '_' and '-') provides idempotency, preventing duplicate order creation if the same identifier is resubmitted. Set `expiration_ts` for time-limited orders, or use `time_in_force` with "fill_or_kill" or "immediate_or_cancel" for specific execution requirements. For market buy orders with FoK, specify `buy_max_cost` to cap spending. Set `post_only: true` to reject orders that would cross the spread, ensuring maker status. Use `sell_position_capped: true` with IoC orders to prevent selling beyond current holdings.

Order status checking uses `GET /trade-api/v2/portfolio/orders/{order_id}` returning comprehensive order state. Response fields include `status` (pending, resting, executed, canceled), `initial_count` (original size), `fill_count` (contracts executed), `remaining_count` (unfilled), and `queue_position` (placement in orderbook). Cost tracking fields separate maker and taker activity: `maker_fees`, `taker_fees`, `maker_fill_cost`, and `taker_fill_cost` all denominate in cents. The `is_taker` boolean in fill records indicates whether you removed liquidity.

Listing all orders uses `GET /trade-api/v2/portfolio/orders` with filters for `ticker`, `event_ticker`, `status`, timestamp ranges (`min_ts`, `max_ts`), plus pagination via `limit` and `cursor`. This enables monitoring all active and historical orders across your portfolio.

## Position and account management

Current positions are retrieved via `GET /trade-api/v2/portfolio/positions` with optional filters: `ticker` for specific markets, `event_ticker` for events, `settlement_status` ("settled" or "unsettled", defaults to unsettled), and `count_filter` accepting comma-separated values from "position", "total_traded", "resting_order_count" to show only non-zero positions.

The response separates `market_positions` and `event_positions`. Market position objects include `ticker`, `position` (net contracts held), `market_exposure` (risk in cents), `total_traded` (lifetime volume), `fees_paid`, `realized_pnl` (locked-in profit/loss), and `resting_orders_count`. Each monetary field includes both cents and dollars variants. Event positions aggregate exposure across all markets in an event, useful for multi-market strategies.

Account balance retrieval uses the simple `GET /trade-api/v2/portfolio/balance` endpoint requiring no parameters. It returns `balance` in cents representing available, unallocated funds ready for trading, plus an optional `updated_ts` Unix timestamp. This balance reflects settled cash and does not include unrealized gains or losses from open positions.

Trade history (fills) is accessed via `GET /trade-api/v2/portfolio/fills` with filters for `ticker`, `order_id`, timestamp ranges, and pagination. Fill objects include `fill_id`, `order_id`, `trade_id`, `ticker`, `side`, `action`, `count`, `yes_price`, `no_price`, `is_taker` (liquidity removal indicator), and `created_time`. Since single orders may generate multiple fills as they execute against different counterparties, this granular data enables precise execution analysis.

## Batch operations and order modification

Batch order creation uses `POST /trade-api/v2/portfolio/orders/batched` accepting an `orders` array with each element following the single order format. This endpoint is available to Advanced tier users in production and all users in demo environments. Maximum batch size is 20 orders, with each counting individually against rate limits. Batch cancel operations use `DELETE /trade-api/v2/portfolio/orders/batched`, with BatchCancelOrders counting as 0.2 transactions per cancellation against write limits.

Individual order cancellation uses `DELETE /trade-api/v2/portfolio/orders/{order_id}`, returning the updated order object with "canceled" status and a `reduced_by` field showing contracts removed. The `POST /trade-api/v2/portfolio/orders/{order_id}/decrease` endpoint reduces order size without full cancellation, accepting either `reduce_by` (decrement amount) or `reduce_to` (target final count). Order amendment via `POST /trade-api/v2/portfolio/orders/{order_id}/amend` allows modifying certain order parameters while maintaining queue position.

## Understanding orderbook structure and pricing

Kalshi orderbooks return only bids, not asks, due to the binary market structure. A YES bid at 42¢ mathematically equals a NO ask at 58¢ (100 - 42), eliminating redundancy. The `GET /trade-api/v2/markets/{ticker}/orderbook` endpoint accepts an optional `depth` parameter (max 100) limiting price levels returned per side.

Orderbook responses contain `yes` and `no` arrays, each holding two-element arrays of `[price_in_cents, quantity]`. Arrays are sorted from worst to best prices (lowest to highest), so the best bid is the last element. Additional `yes_dollars` and `no_dollars` arrays provide dollar-denominated equivalents as objects with `Dollars` and `Count` fields.

To calculate the spread and best prices: best YES bid is the last element of the `yes` array, best NO bid is the last element of the `no` array, best YES ask equals 100 minus best NO bid, and best NO ask equals 100 minus best YES bid. The spread is calculated as best YES ask minus best YES bid. For example, with YES bid at 42¢ and NO bid at 56¢, the YES ask is 44¢, NO ask is 58¢, and the spread is 2¢.

## Sports market structure and ticker conventions

Sports markets follow a hierarchical organization: Series templates (like `KXNFLGAME` for all NFL games) contain Events (specific games), which contain multiple Markets (different outcomes for that game). The ticker pattern is `[KX][SPORT][TYPE]` for series identifiers. NFL uses `KXNFLGAME` for individual games and `KXSB` for Super Bowl futures. NBA uses `KXNBA` for championship markets, `KXNBAEAST` for Eastern Conference, and similar patterns for other conferences.

Market types within sports include moneyline markets (binary win/loss for each team), point spreads (will team X cover spread Y), totals/over-under (will total points exceed threshold), touchdown props (will player X score), and expanding statistical props covering passing, rushing, receiving, and kicking statistics. Parlays launched September 2025 for multi-leg combinations. Each market type maintains the binary YES/NO structure with prices representing implied probabilities.

NFL market lifecycle follows predictable patterns: futures markets (Super Bowl, MVP) open before the season starts, weekly game markets list approximately one week before kickoff, trading volume accelerates 3-4 days before the game with 70%+ occurring in game week, markets close at kickoff, and settlement occurs after official game results. Volume patterns show primetime games (Thursday, Sunday, Monday night) consistently generating the highest volume, often 2-3x regular afternoon games. The Eagles-Cowboys Week 1 opener generated $4M in volume, while the Lions-Ravens Monday Night Football peaked at $49.5M.

NBA markets include championship futures available in the off-season, single-game markets launched April 15, 2025 for playoffs, and later expansion to regular season games. The market lifecycle mirrors NFL patterns with futures available far in advance and single-game markets opening days before tip-off.

## Response formats, timestamps, and error handling

All API responses use standard JSON with conventional HTTP status codes. Success responses return 200 for data retrieval, 201 for resource creation, and 204 for successful operations without response bodies. Client errors include 400 for bad requests with validation failures, 401 for authentication failures with invalid credentials, 403 for forbidden access with insufficient permissions, 404 for resources not found, and 429 for rate limit exceeded.

Server errors use 500 for internal server errors and 503 for service unavailable during maintenance. Error responses follow the JSONError structure with `code` (error identifier), `message` (human-readable description), `details` (additional context), and `service` (originating service name).

Timestamps appear in two formats depending on context. Authentication uses **POSIX timestamps in milliseconds** since epoch (like 1703123456789). API response datetime fields use **RFC3339/ISO 8601 format** with timezone designators (like `2023-12-21T12:34:56.789Z` or `2023-12-21T12:34:56+00:00`). This dual format is critical for correct timestamp handling.

All monetary values default to integer cents unless explicitly marked with `_dollars` suffix. Balance fields, price fields, costs, fees, and profit/loss all use cent denomination. The notional value of winning contracts is **100 cents ($1.00)**, so a YES contract purchased at 42¢ yields 58¢ profit if it wins (100 - 42).

## Best practices for production systems

For polling-based market data collection, use intervals of 1-5 seconds for active trading, 30-60 seconds for passive monitoring, and 5-30 seconds for balance and portfolio checks during active trading. Order status should be polled immediately after placement, then every 2-5 seconds until filled or canceled. However, **WebSocket connections are strongly preferred** over REST polling for real-time updates, significantly reducing API call volume and providing lower latency.

Connection management requires attention to token expiration. Since authentication tokens expire every 30 minutes, implement automatic re-login well before expiration. WebSocket connections need heartbeat mechanisms to detect stale connections, automatic reconnection with exponential backoff on failure, message buffering during brief disconnections, and continuous connection health monitoring.

Retry strategies should implement exponential backoff starting at 1 second, doubling for each subsequent attempt up to a 60-second maximum, with 5-10 maximum retries. Different error types require different approaches: retry 429 rate limit errors after waiting, retry 500/503 server errors with backoff, do not retry 401 authentication errors (fix credentials first), and do not retry 400/404 parameter errors (fix the request). Rate limit handling should include request queuing to spread load over time, caching frequently accessed static data like market metadata, monitoring rate limit response headers, and using exponential backoff when approaching limits.

Security practices mandate storing credentials in environment variables or secure vaults, never hardcoding API keys, excluding private keys from version control, implementing periodic key rotation, using separate keys for production and demo environments, configuring IP address restrictions where available, and logging all API requests for security auditing.

Pagination uses cursor-based navigation to prevent data drift during iteration. The workflow is: make an initial request without a cursor parameter, extract the `cursor` field from the response, pass this cursor to the next request, and repeat until the cursor is empty or absent, indicating no more pages remain. Different endpoints have varying limits: markets support 1-1000 (default 100), events support 1-200 (default 100), and trades support 1-1000 (default 100).

## Data validation and consistency checks

For market data validation, verify that YES bid plus NO bid approximately equals 100 cents (accounting for spread), confirm that timestamp sequences are logical (open_time before close_time before expiration_time), validate that price values fall within 0-100 cent range, and cross-reference volume and open_interest for consistency. Compare data across multiple endpoints to verify consistency, particularly checking that market listings match individual market detail queries and that event-level aggregations match constituent market data.

When handling orderbook data, confirm the reciprocal relationship: YES bid at X plus NO bid at Y should equal approximately 100. The spread is calculated as (100 - NO bid) - YES bid for the YES side. Best bid prices are always the last elements in sorted bid arrays. Validate that orderbook depth matches requested limits.

## Key configuration values for platforms.yaml

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
| **Max Pagination Limit (Markets)** | 1000 | Same |
| **Max Pagination Limit (Events)** | 200 | Same |
| **Max Batch Order Size** | 20 orders | Same |
| **Candlestick Intervals** | 1, 60, 1440 minutes | Same |

## Database schema considerations

Market data tables should include string fields for `ticker` (primary key), `event_ticker`, `market_type`, `title`, `subtitle`, `yes_sub_title`, `no_sub_title`, `category`, and `status` with appropriate string length limits. Timestamp fields require datetime columns for `open_time`, `close_time`, `expiration_time`, `latest_expiration_time`, and `last_update_time`, stored as UTC and potentially indexed for time-range queries.

Price fields should use integer columns for cent-denominated values: `yes_bid`, `yes_ask`, `no_bid`, `no_ask`, `last_price`, `previous_price`, with constraints ensuring values between 0-100. Optional decimal fields for dollar variants can use DECIMAL(10,4) for four decimal places. Volume metrics require integer or bigint columns for `volume`, `volume_24h`, `open_interest`, and `liquidity`.

Settlement fields include a nullable string for `result` (limited to "yes" or "no" values), integer for `settlement_value`, and boolean for `can_close_early`. Configuration integers include `notional_value`, `tick_size`, `risk_limit_cents`, and `settlement_timer_seconds`. Rule documentation uses text fields for `rules_primary` and `rules_secondary`.

Order tables need string columns for `order_id` (primary key), `client_order_id` (indexed for idempotency checks), `ticker` (foreign key to markets), `side`, `action`, `type`, and `status`. Integer columns track counts: `initial_count`, `fill_count`, `remaining_count`, `queue_position`. Price integers mirror market price fields. Cost tracking requires integer columns for `maker_fees`, `taker_fees`, `maker_fill_cost`, `taker_fill_cost`. Timestamp fields capture `created_time`, `expiration_time`, and `last_update_time`.

Position tables should include string `ticker` (foreign key), integer `position` for net contracts (can be negative), integer `market_exposure`, integer `total_traded`, integer `fees_paid`, integer `realized_pnl`, integer `resting_orders_count`, and timestamp `last_updated_ts`. Event position tables aggregate similar fields at the event level.

Fill tables require strings for `fill_id` (primary key), `order_id` (foreign key), `trade_id`, `ticker` (foreign key), `side`, and `action`. Integer `count` stores contracts filled, integer price fields track execution prices, boolean `is_taker` identifies liquidity role, and timestamp `created_time` records execution time.

Series and event tables maintain the hierarchical relationships. Series tables need `ticker` (primary key), `title`, `category`, `frequency`, `fee_type`, integer `fee_multiplier`, and text fields for URLs and rules. JSONB or JSON columns store `product_metadata`, `settlement_sources`, `tags`, and `additional_prohibitions` arrays. Event tables link to series via `series_ticker` foreign key and include `event_ticker` primary key, `title`, `category`, timestamps, and optional nested market relationships.

## Conclusion: System integration readiness

Kalshi's API provides comprehensive access to prediction market data and trading capabilities with clear, well-documented endpoints. The critical architectural decision is authentication method: use RSA-PSS signature scheme with SHA256 hashing, not HMAC-SHA256. Price handling must consistently treat all monetary values as integer cents, not decimals, with 100 cents representing $1.00 contract settlement value.

Real-time data requirements strongly favor WebSocket implementation over REST polling. WebSocket channels provide orderbook deltas, ticker updates, trade feeds, and user-specific fills with lower latency and reduced API load. For systems requiring sub-second data freshness, WebSocket integration is essential.

The orderbook structure returning only bids requires calculated ask prices using the 100-cent complement formula. Database schemas must accommodate this binary market structure with appropriate price validation constraints. Historical data via candlesticks supports only three specific intervals (1, 60, 1440 minutes), constraining backtest granularity.

Sports markets represent 90% of platform volume during football season, with NFL and NBA following predictable lifecycle patterns. Ticker parsing for sports requires understanding the `KX[SPORT][TYPE]` series structure and extracting team information from title fields rather than ticker components. Market metadata includes comprehensive settlement rules, fee structures, and timing information critical for automated trading systems.

Rate limiting varies by tier without public numeric thresholds, requiring response header monitoring and adaptive throttling. Batch operations enable efficient multi-order submission for Advanced tier users, with specific counting rules (BatchCancelOrders = 0.2 transactions per cancel). Idempotency via client_order_id prevents duplicate order creation during retry scenarios.

The combination of comprehensive REST endpoints, real-time WebSocket feeds, granular market metadata, historical data access, and robust trading operations provides everything needed for sophisticated prediction market trading system development. Authentication complexity is manageable with proper RSA key handling, and the tiered rate limit structure accommodates scaling from initial development through high-frequency production trading.
