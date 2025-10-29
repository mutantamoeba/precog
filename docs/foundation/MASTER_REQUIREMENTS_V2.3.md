# Master Requirements Document

---
**Version:** 2.3
**Last Updated:** 2025-10-16
**Status:** ✅ Current - Authoritative Requirements
**Changes in v2.3:** Updated environment variable names to match actual env.template (KALSHI_API_KEY, KALSHI_API_SECRET, KALSHI_BASE_URL); updated directory structure (data_storers/ → database/)
**Changes in v2.2:** Updated terminology (odds → probability) in objectives, requirements, and module references; clarified probability calculations vs. market price comparisons
**Replaces:** Master Requirements v2.0
---

## Document Purpose
This is the **master requirements document** providing a high-level overview of the Precog prediction market trading system. Detailed technical specifications are maintained in supplementary documents (see Section 2.4).

**For new developers**: Start here to understand the project scope, then reference supplementary docs for implementation details.

---

## 1. Executive Summary

### 1.1 Project Overview
**Precog** is a modular, scalable Python application to identify and execute positive expected value (EV+) trading opportunities across multiple prediction market platforms, initially focused on Kalshi with NFL and NCAAF markets, with strategic expansion to other sports, non-sports markets, and additional platforms (Polymarket).

### 1.2 Core Objectives
- **Automate Data Collection**: Retrieve market data from multiple platforms and live game statistics
- **Calculate True Probabilities**: Compute win probabilities from historical data and live game states
- **Identify Edges**: Find EV+ opportunities by comparing true probabilities vs. market prices (minimum 5% threshold after transaction costs)
- **Execute Trades**: Place orders with robust error handling and compliance checks
- **Multi-Platform Strategy**: Abstract platform-specific logic for cross-platform opportunities
- **Scale Strategically**: Expand to additional sports, non-sports markets, and prediction platforms

### 1.3 Success Metrics
- **System Uptime**: 99%+ during market hours
- **Data Latency**: <5 seconds from API to database
- **Decimal Precision**: 100% accuracy in price handling (no float rounding errors)
- **Edge Detection Accuracy**: Validated through backtesting (target: 55%+ win rate)
- **Execution Success**: >95% of intended trades executed
- **ROI**: Positive returns after transaction costs over 6-month period

---

## 2. System Architecture

### 2.1 Technology Stack
- **Language**: Python 3.12
- **Database**: PostgreSQL (local dev → AWS RDS production)
- **ORM**: SQLAlchemy + psycopg2
- **API**: requests (sync), aiohttp (async)
- **Data Processing**: pandas, numpy
- **Decimal Precision**: Python Decimal library (NEVER float for prices)
- **Text Parsing**: Spacy
- **Testing**: pytest (target: >80% coverage)
- **Scheduling**: APScheduler
- **Logging**: Python logging library

### 2.2 High-Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface (CLI)                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────┐
│                    Application Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Trading    │  │  Analytics   │  │  Data Storers   │   │
│  │   Module     │  │    Engine    │  │                 │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────┐
│               Platform Abstraction Layer                     │
│  ┌──────────────────────┐  ┌──────────────────────────┐     │
│  │  Kalshi Platform     │  │  Polymarket Platform     │     │
│  │  (Phases 1-9)        │  │  (Phase 10)              │     │
│  └──────────────────────┘  └──────────────────────────┘     │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────┐
│                   API Connectors Layer                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Kalshi  │  │   ESPN   │  │Balldontlie│  │ Scrapers │   │
│  │   API    │  │   API    │  │   API    │  │          │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Polymarket│  │ Plus EV  │  │SportsRadar│  │  NCAAF   │   │
│  │   API    │  │   API    │  │   API    │  │   API    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                  ┌─────────┴─────────┐
                  │   PostgreSQL DB    │
                  │   (SQLAlchemy)     │
                  │ ALL PRICES: DECIMAL│
                  └────────────────────┘
```

### 2.3 Module Structure
```
precog/
├── api_connectors/         # External API integrations
│   ├── kalshi_client.py
│   ├── espn_client.py
│   ├── balldontlie_client.py
│   ├── polymarket_client.py
│   ├── plus_ev_client.py
│   ├── sportsradar_client.py
│   └── scrapers/
├── platforms/              # Platform abstraction (Phase 10)
│   ├── base_platform.py
│   ├── kalshi_platform.py
│   ├── polymarket_platform.py
│   └── platform_factory.py
├── database/               # Database operations (renamed from data_storers/)
│   ├── models.py
│   ├── crud_operations.py
│   └── db_connection.py
├── analytics/              # Probability calculation & edge detection
│   ├── probability_calculator.py
│   ├── edge_detector.py
│   ├── historical_loader.py
│   └── risk_manager.py
├── trading/                # Order execution
│   ├── order_executor.py
│   └── compliance_checker.py
├── utils/                  # Shared utilities
│   ├── logger.py
│   ├── retry_handler.py
│   ├── pagination.py
│   ├── decimal_helpers.py  # ⚠️ CRITICAL - Decimal conversion
│   └── config.py
├── tests/                  # Test suite
├── data/                   # Historical odds JSON files
├── docs/                   # Supplementary documentation
├── config/                 # YAML configuration files
│   ├── trading.yaml
│   ├── trade_strategies.yaml
│   ├── position_management.yaml
│   ├── probability_models.yaml
│   ├── system.yaml
│   ├── markets.yaml
│   └── data_sources.yaml
├── main.py                 # CLI entry point
└── requirements.txt
```

### 2.4 Documentation Structure
- **This Document**: Master requirements (overview, phases, objectives)
- **Supplementary Documents** (in `docs/` folder):
  1. `API_INTEGRATION_GUIDE.md` - Detailed API specs with code examples
  2. `DATABASE_DESIGN.md` - Full schema, relationships, migration scripts
  3. `EDGE_DETECTION_SPEC.md` - Mathematical formulas, decision algorithms
  4. `TESTING_GUIDE.md` - Test cases, fixtures, mocking strategies
  5. `DEPLOYMENT_GUIDE.md` - Setup instructions, cloud migration
  6. `DEVELOPER_ONBOARDING.md` - Getting started guide for new developers
  7. `KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md` - ⚠️ **PRINT AND KEEP AT DESK**
  8. `CONFIGURATION_GUIDE.md` - YAML configuration reference
  9. `ARCHITECTURE_DECISIONS.md` - Design rationale and trade-offs

---

## 3. Core Concepts

### 3.1 Data Flow
1. **Fetch Market Data**: Platform APIs (Kalshi/Polymarket) → series, events, markets → PostgreSQL
2. **Fetch Live Stats**: ESPN/Balldontlie/SportsRadar APIs → game states → PostgreSQL
3. **Calculate Probabilities**: Historical data + live game state → true win probability
4. **Detect Edges**: Compare true probabilities vs. market prices → identify EV+
5. **Execute Trades**: EV+ opportunities → place orders → record fills
6. **Cross-Platform Selection**: Compare opportunities across platforms → execute on best price

### 3.2 Key Terminology
- **Series**: Kalshi's top-level grouping (e.g., KXNFLGAME = all NFL games)
- **Event**: Specific game instance (e.g., kxnflgame-25oct05nebuf = NE@BUF on Oct 5)
- **Market**: Binary outcome on an event (e.g., "Will NE win?" Yes/No)
- **Edge**: Positive expected value opportunity (market price < true probability)
- **EV+**: Expected Value above minimum threshold (default: 5%)
- **RowCurrentInd**: Database versioning flag (true = current, false = historical)
- **Platform**: Prediction market provider (Kalshi, Polymarket, etc.)
- **Decimal Pricing**: ALWAYS use `Decimal` type, NEVER float, for all prices

### 3.3 Trading Philosophy
- **Value Betting**: Only trade when true odds significantly differ from market prices
- **Risk Management**: Position sizing via Kelly Criterion (fractional for safety)
- **Diversification**: Limit exposure to correlated events
- **Transaction Costs**: Always factor in platform fees before identifying edges
- **Compliance**: Never trade on insider information; log all activity
- **Platform Arbitrage**: Exploit price differences across platforms when available

### 3.4 Decimal Pricing Philosophy ⚠️ CRITICAL

**Why Decimal Precision Matters:**
- Kalshi uses sub-penny pricing (e.g., $0.4975)
- Float arithmetic causes rounding errors that compound over thousands of trades
- Example: 0.4975 as float → 0.497500000000001 → incorrect edge calculations

**Mandatory Rules:**
1. **ALWAYS use `from decimal import Decimal`** in Python
2. **ALWAYS parse Kalshi `*_dollars` fields** (e.g., `yes_bid_dollars`)
3. **NEVER parse integer cents fields** (e.g., `yes_bid`) - deprecated
4. **ALWAYS use DECIMAL(10,4) in PostgreSQL** - never FLOAT, REAL, or NUMERIC
5. **ALWAYS convert strings to Decimal**: `Decimal("0.4975")` NOT `Decimal(0.4975)`

**See KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md for code examples**

---

## 4. Database Overview

### 4.1 Design Principles
- **Versioning**: All tables use `row_current_ind` for historical tracking
- **Timestamps**: `created_at` (immutable), `updated_at` (modified on change)
- **Relationships**: Foreign keys link markets → events → series
- **Indexing**: Optimized for time-series queries and joins
- **JSONB**: Flexible storage for metadata and API responses
- **Decimal Precision**: ALL price columns use DECIMAL(10,4) - **NO EXCEPTIONS**

### 4.2 Core Tables (Simplified)
| Table | Purpose | Key Columns | Price Columns |
|-------|---------|-------------|---------------|
| `series` | Kalshi series | ticker, category, tags | N/A |
| `events` | Game instances | series_id, start_date, final_state | N/A |
| `markets` | Binary outcomes | event_id, status, volume | yes_bid, yes_ask, no_bid, no_ask (ALL DECIMAL(10,4)) |
| `game_states` | Live stats | event_id, home_score, away_score, time_remaining | N/A |
| `probability_matrices` | Historical win probabilities | category, subcategory, state_descriptor, value_bucket | win_probability (DECIMAL(10,4)) |
| `edges` | EV+ opportunities | market_id, side | expected_value, true_win_probability (DECIMAL(10,4)) |
| `positions` | Open trades | market_id, position_qty, side | position_price (DECIMAL(10,4)) |
| `trades` | Executed orders | market_id, quantity, side | price, fees (DECIMAL(10,4)) |
| `platform_markets` | Multi-platform market linking | kalshi_market_id, polymarket_market_id | N/A |

**Detailed schema with indexes, constraints, and sample queries**: See `DATABASE_SCHEMA_SUMMARY.md`

### 4.3 Critical Database Rules

**ALWAYS include in queries:**
```sql
WHERE row_current_ind = TRUE
```

**NEVER query without this filter** - you'll get historical versions mixed with current data

**Price Column Declaration:**
```sql
yes_bid DECIMAL(10,4) NOT NULL,
yes_ask DECIMAL(10,4) NOT NULL,
no_bid DECIMAL(10,4) NOT NULL,
no_ask DECIMAL(10,4) NOT NULL
```

**Python ORM Definition:**
```python
from decimal import Decimal
from sqlalchemy import DECIMAL

yes_bid = Column(DECIMAL(10, 4), nullable=False)
```

---

## 5. Development Phases

### Phase 0: Foundation & Documentation (CURRENT)
**Goal**: Complete all planning, documentation, and configuration before writing code.

**Key Deliverables**:
- ✅ All architectural decisions documented
- ✅ Database schema finalized
- ✅ Configuration system designed
- 🔄 All YAML configuration files created
- 🔄 Environment setup guide complete
- 🔄 Master requirements v2.0 (this document)
- ✅ Decimal pricing strategy documented

**Documentation**: All `docs/` files, all `config/` YAML files, `.env.template`

---

### Phase 1: Core Foundation (Weeks 1-2)
**Goal**: Establish project structure, Kalshi API connectivity, and account management.

**Key Deliverables**:
- Project setup with .env configuration
- Kalshi API client with HMAC-SHA256 authentication
- Database connection and ORM models for account data
- **Decimal conversion utilities** in `utils/decimal_helpers.py`
- CRUD operations with versioning (RowCurrentInd)
- CLI to fetch/store balance, positions, fills, settlements
- Unit tests for API client, database operations, and decimal conversion
- **Verify all prices stored as DECIMAL(10,4)**

**Critical**: Parse `*_dollars` fields from Kalshi API, NEVER integer cents

**Documentation**: `API_INTEGRATION_GUIDE.md` (Kalshi section), `DEVELOPER_ONBOARDING.md`, `KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md`

---

### Phase 2: Football Market Data (Weeks 3-4)
**Goal**: Fetch and store NFL/NCAAF series, events, and markets with decimal precision.

**Key Deliverables**:
- ORM models for series, events, markets tables (all prices DECIMAL(10,4))
- Pagination handling for large API responses
- Scripts to fetch series (filter: category=football, tags=NFL/NCAAF)
- Scripts to fetch events (by series_ticker) with final_state capture
- Scripts to fetch markets (by event_ticker) with live price updates
- **Decimal price validation** - reject any non-DECIMAL values
- CLI commands: `main.py fetch-series`, `fetch-events`, `fetch-markets`
- Unit tests for pagination, market data CRUD, and decimal precision

**Documentation**: `API_INTEGRATION_GUIDE.md` (Kalshi pagination), `DATABASE_SCHEMA_SUMMARY.md` (relationships)

---

### Phase 3: Live Game Stats (Weeks 5-6)
**Goal**: Retrieve and store live statistics from ESPN, Balldontlie, SportsRadar APIs.

**Key Deliverables**:
- ORM model for game_states table
- ESPN API client for NFL/NCAAF scoreboards
- Balldontlie API client (fallback for NFL)
- SportsRadar API client (premium data, optional)
- NCAAF API client for college football stats
- Script to poll live stats every 30 seconds during games
- Link game_states to events via event_id
- CLI command: `main.py fetch-live-stats`
- Unit tests for stat parsers and API clients

**Documentation**: `API_INTEGRATION_GUIDE.md` (ESPN, Balldontlie, SportsRadar sections)

---

### Phase 4: Probability Calculation & Edge Detection (Weeks 7-9)
**Goal**: Generate historical probabilities, compute true probabilities, and identify EV+ opportunities.

**Key Deliverables**:
- Historical data loader (query ESPN/Balldontlie 2019-2024 archives)
- Generate probability matrices with win probabilities (DECIMAL precision)
- Load probability data into probability_matrices table
- Probability calculator: map game_states → state descriptors/value buckets → lookup win probability
- Edge detector: compare true probabilities vs. market prices, calculate EV with DECIMAL math
- Risk manager: Kelly Criterion position sizing, exposure limits
- **Decimal-safe EV calculations** - no float rounding errors
- ORM models for edges table
- CLI command: `main.py compute-edges`
- Unit tests for odds calculation, edge detection, and decimal arithmetic

**Documentation**: `EDGE_DETECTION_SPEC.md` (formulas, buckets, EV calculation with Decimal)

---

### Phase 5: Live Trading (Weeks 10-12)
**Goal**: Execute trades on EV+ opportunities with confirmation and logging.

**Key Deliverables**:
- Kalshi order creation endpoint integration
- Compliance checker (verify market status, user eligibility)
- Order executor (calculate position size with DECIMAL, generate orders, execute via API)
- Trade logging (all orders and fills recorded in trades table with DECIMAL prices)
- Manual trading mode with confirmation prompts
- Automated trading scheduler (APScheduler, optional)
- **Decimal price validation** before order submission
- CLI commands: `main.py execute-trades --manual`, `--auto`
- Unit tests for compliance, order execution, and price accuracy

**Documentation**: `API_INTEGRATION_GUIDE.md` (Kalshi orders), `TESTING_GUIDE.md` (trade mocking)

---

### Phase 6: Expand to Other Sports (Weeks 13-14)
**Goal**: Add NBA, MLB, Tennis, and other sports markets.

**Key Deliverables**:
- Identify Kalshi series for new sports
- API clients for NBA/MLB/Tennis stats (ESPN or alternatives)
- Generate historical probability matrices for new sports (DECIMAL precision)
- Add new sport data to probability_matrices table
- Extend edge detector to support multiple sports
- **Sport-specific Kelly fractions** (NFL: 0.25, NBA: 0.22, Tennis: 0.18)
- CLI command: `main.py fetch-markets --sport NBA`

**Documentation**: `API_INTEGRATION_GUIDE.md` (new sport APIs), update `EDGE_DETECTION_SPEC.md`

---

### Phase 7: Live Trading for Other Sports (Weeks 15-16)
**Goal**: Enable automated trading across all supported sports.

**Key Deliverables**:
- Validate probability accuracy for new sports via backtesting
- Sport-specific risk calibration (adjust volatility parameters, max spreads)
- Enable multi-sport automated scheduler
- **Cross-sport exposure tracking** to prevent over-concentration
- CLI command: `main.py trade --sport all --auto`

**Documentation**: Update `EDGE_DETECTION_SPEC.md` (sport-specific adjustments)

---

### Phase 8: Non-Sports Markets (Weeks 17-20)
**Goal**: Explore political, entertainment, and culture markets.

**Phase 8a: Political Markets**
- Web scraper for RealClearPolling
- Poll aggregation and trend analysis
- Generate political probability matrices from historical poll-to-outcome data (DECIMAL)
- Extend edge detector for political markets

**Phase 8b: Entertainment Markets**
- Web scraper for BoxOfficeMojo
- Opening weekend prediction models
- Generate entertainment probability matrices (DECIMAL)
- Extend edge detector for box office markets

**Phase 8c: Culture Markets** (Future)
- Scrapers for social media mentions, speeches
- Sentiment analysis with NLP
- Extend edge detector for culture markets

**Documentation**: `WEB_SCRAPING_GUIDE.md` (BeautifulSoup/Scrapy examples, rate limiting)

---

### Phase 9: MCPs & Advanced Integrations (Weeks 21-24)
**Goal**: Integrate Model Context Protocols and advanced data sources.

**Key Deliverables**:
- Plus EV API integration for line shopping
- SportsRadar API for advanced metrics
- MCP integrations for Claude Code assistance
- Advanced team performance metrics (DVOA, SP+, Elo ratings)
- Cross-platform data aggregation
- Enhanced edge detection with premium data

**Documentation**: `MCP_INTEGRATION_GUIDE.md`, update `API_INTEGRATION_GUIDE.md`

---

### Phase 10: Multi-Platform Expansion - Polymarket (Weeks 25-28)
**Goal**: Abstract platform-specific logic and add Polymarket support.

**Key Deliverables**:
- Platform abstraction layer (`platforms/base_platform.py`)
- Kalshi platform adapter (`platforms/kalshi_platform.py`)
- Polymarket platform adapter (`platforms/polymarket_platform.py`)
- Platform factory for selecting execution venue
- Cross-platform market linking (`platform_markets` table)
- **Cross-platform price comparison** - find best execution venue
- **Unified decimal handling** across platforms
- Multi-platform position tracking
- CLI command: `main.py trade --platform polymarket`

**Platform Selection Strategy**:
1. Detect same event/market across platforms
2. Compare prices (net of fees) using DECIMAL precision
3. Execute on platform with best price
4. Track positions across all platforms

**Critical Considerations**:
- Different fee structures per platform
- Different settlement mechanisms
- Different API authentication methods
- Unified compliance checking
- Cross-platform exposure limits

**Documentation**: `POLYMARKET_INTEGRATION_GUIDE.md`, `PLATFORM_ABSTRACTION_DESIGN.md`, update `ARCHITECTURE_DECISIONS.md`

---

## 6. Configuration & Environment

### 6.1 Environment Variables (.env.template)
```bash
# Kalshi Authentication
KALSHI_API_KEY=your_kalshi_api_key_here
KALSHI_API_SECRET=your_kalshi_api_secret_here
KALSHI_BASE_URL=https://demo-api.kalshi.co  # Use demo for testing
# KALSHI_BASE_URL=https://trading-api.kalshi.com  # Production URL

# Polymarket Authentication (Phase 10)
POLYMARKET_API_KEY=placeholder_for_phase_10
POLYMARKET_PRIVATE_KEY=placeholder_for_phase_10

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=precog
DB_USER=postgres
DB_PASSWORD=your_password

# API Keys
BALLDONTLIE_API_KEY=your_key
SPORTSRADAR_API_KEY=placeholder_for_phase_9
PLUS_EV_API_KEY=placeholder_for_phase_9

# Trading Parameters
MIN_EV_THRESHOLD=0.05      # 5% minimum edge (DECIMAL)
MAX_POSITION_SIZE=1000     # Max $ per position (DECIMAL)
MAX_TOTAL_EXPOSURE=10000   # Max $ at risk (DECIMAL)
KELLY_FRACTION_NFL=0.25    # NFL Kelly multiplier
KELLY_FRACTION_NBA=0.22    # NBA Kelly multiplier
KELLY_FRACTION_TENNIS=0.18 # Tennis Kelly multiplier

# Platform Configuration (Phase 10)
ENABLED_PLATFORMS=kalshi    # Comma-separated: kalshi,polymarket
DEFAULT_PLATFORM=kalshi

# Environment
TRADING_ENV=PROD           # PROD or DEMO
LOG_LEVEL=INFO             # DEBUG, INFO, WARNING, ERROR

# Decimal Precision
DECIMAL_PRECISION=4        # Always 4 for sub-penny pricing
```

### 6.2 YAML Configuration Files

**All YAML files in `config/` directory:**

1. **trading.yaml** - Trading execution parameters
2. **trade_strategies.yaml** - Strategy-specific settings
3. **position_management.yaml** - Risk limits and Kelly fractions
4. **probability_models.yaml** - Probability calculation model definitions
5. **markets.yaml** - Market filtering and sport configurations
6. **data_sources.yaml** - All API endpoints and authentication
7. **system.yaml** - Logging, scheduling, system-level settings

**See CONFIGURATION_GUIDE.md for detailed YAML specifications**

### 6.3 Dependencies (requirements.txt)
```
python-dotenv==1.0.0
requests==2.31.0
aiohttp==3.9.1
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
pandas==2.1.4
numpy==1.26.2
spacy==3.7.2
pytest==7.4.3
apscheduler==3.10.4
beautifulsoup4==4.12.2
pyyaml==6.0.1

# ⚠️ CRITICAL - Never use these for prices
# decimal is built-in, no installation needed
# NEVER: from numpy import float64  # Will cause rounding errors
# NEVER: price = float(...)          # Will cause rounding errors
# ALWAYS: from decimal import Decimal
# ALWAYS: price = Decimal("0.4975")
```

**Detailed setup instructions**: See `ENVIRONMENT_CHECKLIST.md`, `DEPLOYMENT_GUIDE.md`

---

## 7. Testing Strategy

### 7.1 Test Coverage Goals
- **Unit Tests**: >80% code coverage
- **Integration Tests**: All API → DB workflows
- **End-to-End Tests**: Full pipeline (fetch → calculate → trade)
- **Decimal Precision Tests**: Verify no float rounding in price handling

### 7.2 Test Categories
1. **API Client Tests**: Mock responses, test pagination, retry logic, decimal parsing
2. **Database Tests**: CRUD operations, versioning, constraint validation, DECIMAL storage
3. **Analytics Tests**: Odds calculation accuracy, edge detection logic, decimal arithmetic
4. **Trading Tests**: Order generation, compliance checks, execution simulation, price precision
5. **Decimal Tests**: Conversion accuracy, arithmetic precision, no float contamination

### 7.3 Test Fixtures
- Mock Kalshi API responses (series, events, markets with decimal prices)
- Mock ESPN/Balldontlie game data
- Sample historical odds JSON (DECIMAL values)
- Mock database with seed data (all prices DECIMAL)
- Decimal edge cases (sub-penny prices, large calculations)

### 7.4 Critical Decimal Tests

**Must include tests for:**
```python
def test_decimal_price_parsing():
    """Verify Kalshi *_dollars fields parsed as Decimal"""
    api_response = {"yes_bid_dollars": "0.4975"}
    price = parse_price(api_response["yes_bid_dollars"])
    assert isinstance(price, Decimal)
    assert price == Decimal("0.4975")

def test_no_float_contamination():
    """Verify floats never enter price calculations"""
    price1 = Decimal("0.4975")
    price2 = Decimal("0.5025")
    spread = price2 - price1
    assert isinstance(spread, Decimal)
    assert spread == Decimal("0.0050")

def test_ev_calculation_precision():
    """Verify EV calculated with Decimal precision"""
    true_prob = Decimal("0.5500")
    market_price = Decimal("0.4975")
    ev = (true_prob - market_price) / market_price
    assert isinstance(ev, Decimal)
    assert ev > Decimal("0.05")  # 5% threshold
```

**Detailed test cases and fixtures**: See `TESTING_GUIDE.md`

---

## 8. Error Handling & Logging

### 8.1 Error Categories
- **API Errors**: 4xx/5xx responses, timeouts, rate limits
- **Database Errors**: Connection failures, constraint violations
- **Trading Errors**: Order rejections, insufficient balance
- **Data Errors**: Missing fields, stale data
- **Decimal Errors**: Float contamination, precision loss

### 8.2 Logging Levels
- **DEBUG**: API request/response details, SQL queries, decimal conversions
- **INFO**: Normal operations (markets fetched, edges calculated)
- **WARNING**: Recoverable errors (API retry, missing data, float detected in prices)
- **ERROR**: Critical failures (DB connection lost, trade failed, decimal precision lost)

### 8.3 Audit Trail
- All API calls logged with timestamp, endpoint, parameters
- All trades logged with market_id, side, price (DECIMAL), quantity
- All edge calculations logged with EV (DECIMAL), confidence level
- All decimal conversions logged in DEBUG mode
- Log rotation: 7 days retention, compressed archives

### 8.4 Decimal Error Detection

**Log WARNING if:**
- Float detected in price variable: `if isinstance(price, float): log.warning(...)`
- Decimal precision loss: `if price.as_tuple().exponent < -4: log.warning(...)`
- String→Decimal conversion fails: `except InvalidOperation: log.error(...)`

**Implementation details**: See `API_INTEGRATION_GUIDE.md` (retry logic), `utils/logger.py`, `utils/decimal_helpers.py`

---

## 9. Compliance & Risk Management

### 9.1 Kalshi Prohibitions
- No trading by league insiders (players, coaches, officials)
- No market manipulation or coordinated trading
- Adhere to Terms of Service

### 9.2 Polymarket Considerations (Phase 10)
- Verify regulatory compliance in user's jurisdiction
- Understand blockchain transaction finality
- Account for gas fees in EV calculations
- Follow Polymarket Terms of Service

### 9.3 Risk Limits (Configurable in YAML)
- **Max Position Size**: $1,000 per market (DECIMAL)
- **Max Total Exposure**: $10,000 across all markets
- **Max Correlated Exposure**: $5,000 (e.g., multiple games in same slate)
- **Kelly Fraction**: 25% of full Kelly for NFL (conservative sizing)
- **Sport-Specific Kelly**: NFL=0.25, NBA=0.22, Tennis=0.18
- **Cross-Platform Limits**: Aggregate positions across Kalshi + Polymarket

### 9.4 Circuit Breakers
- Stop trading if daily loss exceeds 10% of capital
- Pause if API connectivity fails for >5 minutes
- Alert if >3 consecutive trade rejections
- Halt if decimal precision error detected

**Detailed risk formulas**: See `EDGE_DETECTION_SPEC.md` (Kelly Criterion, exposure calculations with DECIMAL)

---

## 10. Performance Targets

- **Market Update Latency**: <2 seconds API → DB
- **Decimal Conversion**: <1ms per price (negligible overhead)
- **Edge Calculation**: <5 seconds for all active markets
- **Order Execution**: <10 seconds from edge detection to order placement
- **Database Queries**: <500ms for time-series lookups
- **Concurrent Markets**: Support 200+ markets simultaneously
- **Cross-Platform Comparison**: <3 seconds to compare prices across platforms

---

## 11. Future Enhancements

### Short-Term (6 months)
- Machine learning models for probability estimation (Phase 5+)
- Advanced team metrics (DVOA, SP+, Elo ratings) (Phase 9)
- Web dashboard for monitoring (React + FastAPI)
- Mobile alerts for high-confidence edges
- Live price streaming (WebSockets)

### Long-Term (12+ months)
- Multi-leg arbitrage detection (cross-market)
- Portfolio optimization algorithms with Decimal precision
- Cloud deployment (AWS ECS/Lambda)
- Additional prediction market platforms (PredictIt, Manifold)
- Machine learning for optimal Kelly fraction tuning
- Cross-platform automated arbitrage execution

---

## 12. Key Resources

### External Documentation
- **Kalshi API Docs**: https://docs.kalshi.com/api-reference/
- **Kalshi Sample Code**: https://github.com/Kalshi/kalshi-starter-code-python
- **Polymarket Docs**: https://docs.polymarket.com/ (Phase 10)
- **ESPN API Guide**: https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b
- **Balldontlie NFL API**: https://nfl.balldontlie.io/
- **NCAAF API**: https://github.com/henrygd/ncaa-api
- **Python Decimal Documentation**: https://docs.python.org/3/library/decimal.html

### Internal Documentation (docs/ folder)

**Critical - Read First:**
1. **KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md** ⚠️ **PRINT AND KEEP AT DESK**
2. **DEVELOPER_ONBOARDING.md** - Getting started guide

**Reference Documentation:**
3. `API_INTEGRATION_GUIDE.md` - Detailed API specifications
4. `DATABASE_SCHEMA_SUMMARY.md` - Full schema and queries
5. `EDGE_DETECTION_SPEC.md` - Mathematical formulas
6. `CONFIGURATION_GUIDE.md` - YAML configuration reference
7. `ARCHITECTURE_DECISIONS.md` - Design rationale and trade-offs

**Development Guides:**
8. `TESTING_GUIDE.md` - Test cases and fixtures
9. `DEPLOYMENT_GUIDE.md` - Setup and deployment
10. `ENVIRONMENT_CHECKLIST.md` - Windows 11 setup guide

**Phase 10 Documentation:**
11. `POLYMARKET_INTEGRATION_GUIDE.md` - Multi-platform strategy
12. `PLATFORM_ABSTRACTION_DESIGN.md` - Architecture for multiple platforms

---

## 13. Critical Reminders

### ⚠️ Decimal Pricing (ALWAYS)
1. `from decimal import Decimal` in every file handling prices
2. Parse Kalshi `*_dollars` fields (e.g., `yes_bid_dollars`)
3. NEVER parse integer cents fields (deprecated)
4. Store all prices as DECIMAL(10,4) in PostgreSQL
5. Convert strings to Decimal: `Decimal("0.4975")` NOT `Decimal(0.4975)`
6. Print and reference KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md

### ⚠️ Database Queries (ALWAYS)
1. Include `WHERE row_current_ind = TRUE` in all queries
2. Never query without versioning filter
3. Use DECIMAL types in SQLAlchemy models

### ⚠️ Configuration (ALWAYS)
1. Load settings from YAML files in `config/` directory
2. Use `.env` only for secrets and environment-specific values
3. Validate all configuration on startup

### ⚠️ Testing (ALWAYS)
1. Mock external APIs in tests
2. Test decimal precision explicitly
3. Verify no float contamination in price handling
4. Achieve >80% code coverage

---

## 14. Contact & Support

**Project Lead**: [Your Name]
**Development Team**: [Team Members]
**Repository**: [GitHub URL when available]

For questions or issues:
1. Check supplementary docs in `docs/` folder
2. Review KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md for pricing issues
3. Review test cases for implementation examples
4. Submit GitHub issues for bugs or feature requests

---

## 15. Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.9 | 2025-10-08 | Initial draft (Session 5) |
| 2.0 | 2025-10-09 | Added decimal pricing, Phase 10 (Polymarket), updated tech stack, multi-platform architecture |
| 2.2 | 2025-10-16 | Updated terminology (odds → probability); renamed odds_models.yaml → probability_models.yaml; clarified probability vs. market price; updated table names (odds_matrices → probability_matrices) |
| 2.3 | 2025-10-16 | Updated environment variable names to match env.template; updated directory structure (data_storers/ → database/) |

---

**NEXT**: Create remaining Phase 0 documents (2 YAML files, environment checklist)

---

**END OF MASTER REQUIREMENTS V2.3**
