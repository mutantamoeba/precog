# Project Overview: Precog

---
**Version:** 1.4
**Last Updated:** 2025-10-19
**Status:** ✅ Current
**Changes in v1.4:** Added Phase 0.5 (Foundation Enhancement) and Phase 1.5 (Foundation Validation); updated system description to include strategy/model versioning and trailing stop loss; updated database schema to V1.4; added versioning system for A/B testing and trade attribution
**Changes in v1.3:** Updated terminology (odds → probability); updated system description to reference probability calculations instead of odds calculations
**Changes in v1.2:** Added testing/CI-CD section, budget estimates, phase dependencies table, clarified Phases 3/4 sequencing (live data Phase 2 → processing Phase 3 → odds/edges Phase 4), updated directory tree (data_storers/ → database/), merged comprehensive reqs.txt into Technology Stack.
---

## Executive Summary

**Precog** is an automated prediction market trading system that identifies statistical edges in live markets (primarily Kalshi, with Polymarket in Phase 10) by comparing market prices against historical probability models using **versioned strategies and models**. The system monitors markets in real-time, calculates true probabilities from 5+ years of historical data using versioned probability models, detects profitable opportunities (positive EV) via versioned trading strategies, and executes trades automatically with comprehensive risk management including **trailing stop losses** for profit protection.

**Core Value Proposition:** Markets sometimes misprice events. By using rigorous statistical analysis of historical data and versioned models/strategies with precise trade attribution, we can systematically identify and capitalize on these mispricings while continuously improving through A/B testing.

**Target ROI:** 15-25% annual return with conservative Kelly fractional sizing (0.25) and strict risk controls.

**Development Approach:** Documentation-first, phased implementation (Phase 0-10 with inserted Phase 0.5/1.5), part-time sustainable pace (~12h/week).

**Database:** PostgreSQL with schema V1.4 (strategies, probability_models tables with immutable versioning pattern, trailing_stop_state JSONB, trade attribution FKs).

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Technology Stack](#technology-stack)
3. [Directory Structure](#directory-structure)
4. [Data Flow](#data-flow)
5. [Phase Dependencies](#phase-dependencies)
6. [Testing & CI/CD](#testing--cicd)
7. [Budget Estimates](#budget-estimates)
8. [Key Design Decisions](#key-design-decisions)
9. [Risk Management](#risk-management)
10. [Development Philosophy](#development-philosophy)

---

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         PRECOG SYSTEM                           │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Market Monitor  │───▶│  Live Game Data  │───▶│   Processing     │
│    (Kalshi)      │    │  (Phase 2: ESPN) │    │ (Phase 3: Async/ │
│                  │    │                  │    │   WebSocket)     │
└──────────────────┘    └──────────────────┘    └──────────────────┘
         │                                                │
         │                                                ▼
         │                                    ┌──────────────────────┐
         │                                    │  Odds & Edge Calc    │
         │                                    │ (Phase 4: Historical │
         │                                    │    + Elo Models)     │
         │                                    └──────────────────────┘
         │                                                │
         ▼                                                ▼
┌──────────────────┐                          ┌──────────────────────┐
│   PostgreSQL     │◀────────────────────────│   Trading Engine     │
│   (SCD Type 2)   │                         │  (Phase 5: Orders)   │
└──────────────────┘                          └──────────────────────┘
         │                                                │
         ▼                                                ▼
┌──────────────────┐                          ┌──────────────────────┐
│  Analytics &     │                          │   Risk Management    │
│  Reporting       │                          │   & Circuit Breaker  │
└──────────────────┘                          └──────────────────────┘
```

**Key Data Flow (Clarified Phases 3/4 Sequencing):**
1. **Phase 1:** Kalshi API client monitors markets (prices, liquidity, metadata)
2. **Phase 2:** ESPN API fetches live game data (scores, stats, game state) every 15s
3. **Phase 3:** Async processing & WebSocket handlers ingest data (NO edge detection yet)
4. **Phase 4:** Odds calculation using historical loader + Elo → Edge detection → Trade signals
5. **Phase 5:** Trading engine executes orders with risk checks

**Critical:** Phase 3 is pure data processing/ingestion. Phase 4 adds probability models and edge detection. This sequencing ensures Phase 2 data is available for Phase 4's historical loader.

---

## Technology Stack

### Core Technologies

**Language & Runtime:**
- Python 3.12+ (type hints, async/await, modern features)
- Virtual environment (venv) for dependency isolation

**Database:**
- PostgreSQL 15+ (ACID compliance, JSON support, advanced indexing)
- psycopg2 3.x (connection pooling, async support)
- Slowly Changing Dimensions (SCD Type 2) for historical accuracy

**Web Framework & APIs:**
- aiohttp 3.9+ (async HTTP client for API calls)
- Click 8.1+ (command-line interface)
- FastAPI 0.104+ (Phase 7+ web dashboard, optional)

**Data & Analytics:**
- pandas 2.1+ (data manipulation)
- numpy 1.26+ (numerical computing)
- scikit-learn 1.3+ (Phase 9: ML models)

**Task Scheduling:**
- APScheduler 3.10+ (cron-like job scheduling)

**NLP & Sentiment (Phase 8):**
- spacy 3.7+ with en_core_web_sm model
- transformers 4.35+ (Hugging Face models)

**Authentication & Security:**
- cryptography 42.0+ (RSA-PSS signing for Kalshi API, not HMAC-SHA256)
- python-dotenv 1.0+ (environment variable management)

**Testing & Quality:**
- pytest 7.4+ (unit & integration tests)
- pytest-asyncio 0.21+ (async test support)
- coverage 7.3+ (code coverage reports)
- black 23.12+ (code formatting)
- flake8 6.1+ (linting)
- mypy 1.7+ (static type checking)
- pre-commit 3.5+ (git hooks for quality checks)

**Phase-Specific:**
- Phase 4: XGBoost 2.0+, statsmodels 0.14+
- Phase 9: TensorFlow 2.15+ / PyTorch 2.1+ (LSTM models)
- Phase 10: Additional Polymarket SDK (TBD)

---

### Complete Dependencies (requirements.txt)

**See REQUIREMENTS_AND_DEPENDENCIES_V1.0.md for comprehensive comparison table (Part 7 sample vs. full production).**

**Core Dependencies (Phase 1-5):**
```
# Database & ORM
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1

# API & HTTP
aiohttp==3.9.1
requests==2.31.0
websockets==12.0

# CLI & Configuration
click==8.1.7
python-dotenv==1.0.0
pyyaml==6.0.1

# Data Processing
pandas==2.1.4
numpy==1.26.2

# Authentication & Security
cryptography==42.0.5

# Task Scheduling
apscheduler==3.10.4

# Utilities
python-dateutil==2.8.2
pytz==2023.3
```

**Development & Testing:**
```
# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
coverage==7.3.2

# Code Quality
black==23.12.1
flake8==6.1.0
mypy==1.7.1
pre-commit==3.5.0
```

**NLP & Sentiment (Phase 8):**
```
spacy==3.7.2
transformers==4.35.2
torch==2.1.1  # For transformers
```

**Advanced Analytics (Phase 9):**
```
xgboost==2.0.2
scikit-learn==1.3.2
statsmodels==0.14.0
tensorflow==2.15.0  # Or pytorch==2.1.1
```

**Installation Commands:**
```bash
# Core dependencies
pip install -r requirements.txt

# Spacy language model
spacy download en_core_web_sm

# Verify installation
pip list | grep -E "(sqlalchemy|cryptography|click)"
python -c "import spacy; nlp = spacy.load('en_core_web_sm')"
```

**Rationale for Version Choices:** As of October 2025, these are the latest stable versions with security patches, async support improvements, and DECIMAL precision fixes in SQLAlchemy 2.0.23.

---

## Directory Structure

```
precog/
├── main.py                      # CLI entry point (Click commands)
├── requirements.txt             # Core + dev dependencies
├── .env.template                # Environment variable template
├── README.md                    # Project README
│
├── config/                      # Configuration files
│   ├── system.yaml              # System-wide settings
│   ├── trading.yaml             # Trading parameters
│   ├── probability_models.yaml  # Model configurations
│   ├── position_management.yaml # Position sizing rules
│   ├── trade_strategies.yaml    # Entry/exit strategies
│   ├── markets.yaml             # Market filtering
│   └── data_sources.yaml        # API endpoint configs
│
├── api_connectors/              # External API clients
│   ├── kalshi_client.py         # Kalshi API (RSA-PSS auth)
│   ├── espn_client.py           # ESPN scoreboard API
│   ├── balldontlie_client.py    # NBA stats API (Phase 6)
│   └── polymarket_client.py     # Polymarket API (Phase 10)
│
├── database/                    # Database layer (renamed from data_storers/)
│   ├── models.py                # SQLAlchemy ORM models (DECIMAL(10,4) prices)
│   ├── crud_operations.py       # Database CRUD (e.g., get_active_edges())
│   └── connection.py            # Connection pool (psycopg2, pool_size:5)
│
├── schedulers/                  # Task scheduling
│   └── market_updater.py        # APScheduler tasks (Phase 2: ESP fetch every 15s)
│
├── models/                      # Odds calculation models
│   ├── elo.py                   # Elo rating system
│   ├── regression.py            # Logistic regression
│   ├── historical_lookup.py     # Historical data interpolation (Phase 4)
│   └── ensemble.py              # Model ensemble (weights: elo 0.40, reg 0.35, ml 0.25, hist 0.30)
│
├── analytics/                   # Analytics & ML (Phase 9)
│   ├── ml/
│   │   ├── __init__.py          # XGBoost/LSTM stubs
│   │   └── train.py
│   └── reporting.py
│
├── utils/                       # Utility functions
│   ├── decimal_helpers.py       # DECIMAL precision helpers (e.g., is_material_change())
│   ├── text_parser.py           # Spacy sentiment analysis (Phase 8)
│   └── logger.py                # Structured logging
│
├── tests/                       # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── docs/                        # Documentation
    ├── foundation/              # Core architecture docs
    ├── api-integration/         # API guides
    ├── database/                # Schema docs
    ├── configuration/           # Config guides
    ├── utility/                 # Handoffs, logs, maintenance
    └── sessions/                # Session handoffs
```

**Key Directory Notes:**
- `database/` (renamed from `data_storers/`) contains all DB logic
- `models/` contains probability calculation models (not ML training)
- `analytics/ml/` contains ML training code (Phase 9)
- `config/` contains all 7 YAML files for system configuration
- All prices use `DECIMAL(10,4)` format (never float/int)

---

## Data Flow

### Market Monitoring → Edge Detection → Trade Execution

**Phase 1-2: Data Ingestion**
1. `kalshi_client.py`: Poll Kalshi REST API every 5s for market updates
2. `espn_client.py`: Fetch live game data every 15s (scores, stats, game state)
3. Store raw data in PostgreSQL with timestamps

**Phase 3: Processing (No Edge Detection)**
4. `market_updater.py` (APScheduler): Async WebSocket handlers process incoming data
5. Update `game_states` table with latest scores and stats
6. **NO probability calculation or edge detection in Phase 3**

**Phase 4: Probability Calculation & Edge Detection**
7. `historical_lookup.py`: Load historical probability matrices (nflfastR data)
8. `ensemble.py`: Calculate ensemble probabilities (elo 0.40, regression 0.35, ml 0.25, historical 0.30)
9. Compare ensemble probability vs. market price → Calculate edge
10. If edge > threshold (0.0500), generate trade signal

**Phase 5: Trade Execution**
11. `trading_engine.py`: Validate trade signal (balance, liquidity, risk checks)
12. Calculate position size (Kelly 0.25 fractional)
13. Place order via Kalshi API
14. Log trade and update positions

**Phase 4 Data Flow Diagram (ASCII):**
```
Live Game Data (ESPN) → game_states table
                              ↓
                    Historical Loader (nflfastR)
                              ↓
                    Odds Calculation (Elo + Historical)
                              ↓
                    Ensemble Model (weighted average)
                              ↓
                    Edge Detection (ensemble - market price)
                              ↓
                    Trade Signals (if edge > 0.0500)
```

---

## Phase Dependencies

### Phase Dependency Table

| Phase | Name | Depends On | Deliverables | Status |
|-------|------|------------|--------------|--------|
| **0** | Foundation | - | All docs, YAMLs, schema V1.3, handoff system | ✅ 100% |
| **0.5** | Foundation Enhancement | Phase 0 | Schema V1.4 (versioning, trailing stops), updated docs | 🟢 75% |
| **1** | Core Infrastructure | Phase 0.5 | Kalshi API client, database ops, logging | 🔵 Planned |
| **1.5** | Foundation Validation | Phase 1 | strategy_manager, model_manager, version tests | 🔵 Planned |
| **2** | Live Data Integration | Phase 1.5 | ESPN API client, schedulers (market_updater.py) | 🔵 Planned |
| **3** | Data Processing | Phase 2 | Async/WebSocket handlers, NO probability calc yet | 🔵 Planned |
| **4** | Probability & Edge Detection | Phases 2-3 | Historical loader, versioned models, edge calc | 🔵 Planned |
| **5** | Trading Engine | Phases 1.5, 4 | Versioned strategies, orders, position mgmt, trailing stops | 🔵 Planned |
| **6** | Multi-Sport Expansion | Phases 1-5 | NBA, MLB, Tennis, UFC support | 🔵 Planned |
| **7** | Web Dashboard | Phase 5 | FastAPI + React UI for monitoring | 🔵 Planned |
| **8** | Sentiment Analysis | Phase 5 | NLP sentiment integration (Spacy) | 🔵 Planned |
| **9** | Advanced Analytics | Phases 4-8 | XGBoost/LSTM training, backtesting, versioned models | 🔵 Planned |
| **10** | Multi-Platform | All phases | Polymarket integration, arbitrage | 🔵 Planned |

**Critical Dependencies:**
- **Phase 0.5** must complete BEFORE Phase 1 (schema V1.4 must exist before code written)
- **Phase 1.5** validates versioning system before Phase 2 complexity
- Phase 4 **requires** Phase 2 (live game data for historical loader context) and implements **model versioning**
- Phase 5 **requires** Phase 4 (edge detection for trade signals) and implements **strategy versioning**
- Phase 3 is pure processing (async handlers), **NO probability calc/edges**

**Phase 0.5/1.5 Rationale:**
- **Phase 0.5:** Added database versioning (strategies, probability_models) BEFORE implementation
- **Phase 1.5:** Validates versioning system works (manager classes, version tests) BEFORE Phase 2
- Prevents costly refactoring - versioning is fundamental, must be in foundation

**Sequencing Rationale:**
- Phase 2 provides live game states → Phase 3 processes/ingests → Phase 4 leverages for probability calc with versioned models
- Separating processing (3) from probability calc (4) allows data pipeline testing without model complexity
- Phase 4 creates versioned models, Phase 5 creates versioned strategies, Phase 9 uses the system

---

## Testing & CI/CD

### Testing Strategy

**Unit Tests (Phase 1+):**
- Test individual functions in isolation
- Mock external APIs (Kalshi, ESPN)
- DECIMAL precision validation
- Coverage target: >80%

**Integration Tests (Phase 2+):**
- Test API client integration with live endpoints (sandbox mode)
- Database operations with test fixtures
- End-to-end data flow (ingestion → processing → storage)

**Backtesting (Phase 4+):**
- Historical walk-forward validation
- 2019-2024 data for NFL/NCAAF
- Compare model predictions vs. actual outcomes
- Track hypothetical PnL

**Continuous Integration:**
```yaml
# .github/workflows/ci.yml (GitHub Actions)
name: CI Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python 3.12
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          spacy download en_core_web_sm
      - name: Run tests
        run: pytest --cov=precog --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

**Pre-Commit Hooks:**
- Black formatting
- Flake8 linting
- mypy type checking
- pytest unit tests (fast only)

**Quality Gates:**
- All tests must pass
- Coverage >80%
- No linting errors
- Type checking passes

---

## Budget Estimates

### Development Phase Costs (Phase 0-5 MVP)

| Phase | Time Estimate | At 12h/week | Cost (if contracting @$50/h) |
|-------|---------------|-------------|-------------------------------|
| Phase 0 | 50 hours | 4 weeks | $2,500 |
| Phase 0.5 | 30 hours | 2.5 weeks | $1,500 |
| Phase 1 | 60 hours | 5 weeks | $3,000 |
| Phase 1.5 | 20 hours | 1.5 weeks | $1,000 |
| Phase 2 | 40 hours | 3 weeks | $2,000 |
| Phase 3 | 40 hours | 3 weeks | $2,000 |
| Phase 4 | 80 hours | 7 weeks | $4,000 |
| Phase 5 | 60 hours | 5 weeks | $3,000 |
| **Total MVP** | **380 hours** | **32 weeks (~8 months)** | **$19,000** |

**Note:** These are internal development hour estimates, not external costs. If self-building part-time at ~12h/week, MVP completion estimated May 2026. Phase 0.5/1.5 added for versioning system and validation.

### Operational Costs (Monthly, Post-MVP)

| Item | Monthly Cost | Annual Cost | Notes |
|------|--------------|-------------|-------|
| **Database (AWS RDS PostgreSQL)** | $30-50 | $360-600 | db.t3.micro, 20GB storage |
| **Compute (AWS EC2)** | $10-20 | $120-240 | t3.micro, spot instances |
| **API Costs (Kalshi)** | $0 | $0 | Free tier sufficient Phase 1-5 |
| **Data Storage (S3)** | $5-10 | $60-120 | Historical data, logs |
| **Monitoring (CloudWatch)** | $5 | $60 | Basic metrics |
| **Domain & SSL** | $2 | $24 | Route53, Let's Encrypt |
| **Total (MVP)** | **$52-87** | **$624-1,044** | Estimated |
| **Total (Production)** | **$100-200** | **$1,200-2,400** | With redundancy, backups |

**Trading Capital:**
- Minimum: $500-1,000 (testing, small positions)
- Recommended: $5,000-10,000 (meaningful positions, diversification)
- Scale: Based on proven profitability

**Phase 6+ Additional Costs:**
- Phase 6 (Multi-Sport): +$20/month (additional API calls, data storage)
- Phase 7 (Web Dashboard): +$30/month (front-end hosting, SSL)
- Phase 10 (Polymarket): +$50/month (multi-platform hosting, increased compute)

---

## Key Design Decisions

### 1. DECIMAL Precision (Critical)
**Decision:** Use `DECIMAL(10,4)` for all prices (never float/int)
**Rationale:** Avoid floating-point errors in financial calculations
**Implementation:** SQLAlchemy DECIMAL columns, Python `Decimal` type, parse `*_dollars` API fields

### 2. RSA-PSS Authentication (Phase 1)
**Decision:** Use RSA-PSS with SHA256 (not HMAC-SHA256) for Kalshi API
**Rationale:** Kalshi API updated to RSA-PSS in 2025
**Implementation:** `cryptography` library, sign requests with private key

### 3. SCD Type 2 for Historical Accuracy
**Decision:** Implement Slowly Changing Dimensions Type 2 in database
**Rationale:** Track all historical changes to market prices, positions, odds
**Implementation:** `row_current_ind` flag, `row_effective_date`, `row_expiration_date`

### 4. Ensemble Model with Historical Lookup
**Decision:** Combine Elo (0.40) + Regression (0.35) + ML (0.25) + Historical (0.30)
**Rationale:** Diversify model risk, leverage historical research
**Implementation:** Weighted average in `ensemble.py`, Phase 4+

### 5. Conservative Risk Management
**Decision:** Kelly 0.25 fractional, max 15% per market, circuit breakers
**Rationale:** User preference for safety, avoid ruin risk
**Implementation:** `position_management.yaml`, pre-trade validation

### 6. Phase 3/4 Sequencing
**Decision:** Separate data processing (Phase 3) from odds calculation (Phase 4)
**Rationale:** Test data pipeline independently, leverage Phase 2 data in Phase 4
**Implementation:** Phase 3 = async handlers only, Phase 4 = historical loader + odds

**See ARCHITECTURE_DECISIONS_V2.1.md for complete ADR list (15+ decisions).**

---

## Risk Management

### Trading Risks
- **Daily loss limit:** $500 (circuit breaker triggers)
- **Position limits:** Max 15% portfolio per market
- **Edge threshold:** Minimum 5.00% edge for auto-execution
- **Liquidity check:** Minimum $1,000 available liquidity per market

### Technical Risks
- **API failures:** Exponential backoff, retry logic, fallback modes
- **Stale data:** Timestamp validation, data freshness checks
- **Database failures:** Connection pooling, automatic reconnection
- **Model errors:** Multiple model validation, confidence scoring

### Operational Risks
- **Manual override:** Admin dashboard (Phase 7) for emergency stops
- **Audit trail:** Comprehensive logging of all trades and decisions
- **Alerts:** Email/SMS notifications for critical events
- **Backup capital:** Reserve fund for drawdowns

---

## Development Philosophy

### Part-Time Sustainable
- **Time Commitment:** ~12 hours/week
- **Pace:** Quality over speed, no burnout
- **Flexibility:** Adjust estimates as implementation reveals complexity

### Documentation-First
- **Approach:** Design before code
- **Benefit:** Catch issues early, clear roadmap
- **Living Docs:** Update documentation as system evolves

### Conservative Trading
- **Philosophy:** Preserve capital, avoid ruin risk
- **Position Sizing:** Kelly 0.25 fractional (conservative)
- **Risk Checks:** Multiple validation layers before trades

### Test-Driven
- **Coverage:** >80% unit test coverage
- **Integration:** Test all external API integrations
- **Backtest:** Validate models on historical data before live trading

---

## Next Steps

1. ✅ **Phase 0 Complete** (100% - documentation, YAMLs, schema, handoff system)
2. **Phase 1 Kickoff** (Core Infrastructure):
   - Set up development environment (ENVIRONMENT_CHECKLIST_V1.1.md)
   - Create database schema (DATABASE_SCHEMA_SUMMARY_V1.1.md)
   - Implement Kalshi API client with RSA-PSS auth (API_INTEGRATION_GUIDE_V1.0.md)
   - Write comprehensive tests (>80% coverage)
3. **Iterate:** Adjust design as implementation reveals needs

---

## Document Status

**Version:** 1.2
**Last Updated:** 2025-10-12
**Status:** ✅ Current
**Next Review:** Phase 1 kickoff (after Phase 0 completion)
**Maintainer:** Project lead

**Related Documents:**
- [Master Requirements](MASTER_REQUIREMENTS_V2.1.md) - Complete requirements Phase 0-10
- [Master Index](MASTER_INDEX_V2.1.md) - All project documents with locations
- [Development Phases](DEVELOPMENT_PHASES_V1.1.md) - Detailed roadmap and timelines
- [Database Schema](DATABASE_SCHEMA_SUMMARY_V1.1.md) - Complete schema with SCD Type 2
- [Architecture Decisions](ARCHITECTURE_DECISIONS_V2.1.md) - ADRs 1-15+
- [Configuration Guide](CONFIGURATION_GUIDE_V2.1.md) - YAML config patterns
- [API Integration Guide](API_INTEGRATION_GUIDE_V1.0.md) - Kalshi/ESPN/etc APIs
- [Handoff Protocol](Handoff_Protocol_V1.0.md) - Session management and version control
- [Project Status](PROJECT_STATUS.md) - Current state and next goals

---

**END OF PROJECT_OVERVIEW**
