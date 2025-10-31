# Precog

[![CI/CD Pipeline](https://github.com/mutantamoeba/precog/actions/workflows/ci.yml/badge.svg)](https://github.com/mutantamoeba/precog/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/mutantamoeba/precog/branch/main/graph/badge.svg)](https://codecov.io/gh/mutantamoeba/precog)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: TBD](https://img.shields.io/badge/license-TBD-lightgrey.svg)](LICENSE)

**Automated prediction market trading system** that identifies statistical edges in live markets by comparing market prices against probability models built from historical data.

**Status:** [DONE] Phase 0.6c Complete | [ACTIVE] Phase 0.7 In Progress (CI/CD & Advanced Testing)

---

## Quick Links

**Start Here:**
- [Project Overview](docs/foundation/PROJECT_OVERVIEW_V1.3.md) - System architecture, tech stack, phases
- [Master Index](docs/foundation/MASTER_INDEX_V2.2.md) - Complete document inventory
- [Phase 1 Task Plan](docs/utility/PHASE_1_TASK_PLAN_V1.0.md) - Next implementation steps

**Key Documentation:**
- [Master Requirements](docs/foundation/MASTER_REQUIREMENTS_V2.3.md) - Complete requirements (Phase 0-10)
- [Architecture Decisions](docs/foundation/ARCHITECTURE_DECISIONS_V2.3.md) - Design rationale and ADRs
- [Configuration Guide](docs/configuration/CONFIGURATION_GUIDE_V3.0.md) - YAML configuration system
- [API Integration Guide](docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md) - Kalshi, ESPN, Weather APIs
- [Database Schema](docs/database/DATABASE_SCHEMA_SUMMARY_V1.2.md) - PostgreSQL schema with SCD Type 2

---

## Phase 0 Deliverables [DONE]

### Documentation (100% Complete)
- [DONE] **15+ core documents** - Foundation, API integration, database, configuration
- [DONE] **All documents validated** - Consistent terminology, versions, and cross-references
- [DONE] **Phase 0 completion reports** - CONSISTENCY_REVIEW, FILENAME_VERSION_REPORT, PHASE_0_COMPLETENESS

### Configuration (100% Complete)
- [DONE] **7 YAML configuration files:**
  - `config/system.yaml` - Database, logging, environment settings
  - `config/trading.yaml` - Risk management, position sizing, circuit breakers
  - `config/trade_strategies.yaml` - Entry strategies (pre-game, halftime, settlement)
  - `config/position_management.yaml` - Exit rules, stop loss, profit targets
  - `config/probability_models.yaml` - Model configurations (Elo, regression, ensemble)
  - `config/markets.yaml` - Platform settings, market filters
  - `config/data_sources.yaml` - API endpoints, polling intervals

- [DONE] **Environment template** - `config/env.template` with all required variables

### Architecture Decisions
- [DONE] **DECIMAL(10,4) pricing** - Never float for financial calculations
- [DONE] **RSA-PSS authentication** - Kalshi API (not HMAC-SHA256)
- [DONE] **SCD Type 2 versioning** - Historical accuracy in database
- [DONE] **Three-tier configuration** - Env vars -> YAML -> DB overrides
- [DONE] **Conservative risk management** - Kelly 0.25 fractional, strict circuit breakers

---

## System Overview

### Core Value Proposition
Markets sometimes misprice events. By using rigorous statistical analysis of historical data, we can systematically identify and capitalize on these mispricings.

### How It Works
1. **Monitor Markets** - Track Kalshi prediction markets in real-time
2. **Calculate True Probabilities** - Use historical data (5+ years) and Elo ratings
3. **Detect Edges** - Compare our probabilities vs. market prices
4. **Execute Trades** - Automatically trade when edge > threshold (5%+)
5. **Manage Risk** - Kelly criterion sizing, position limits, circuit breakers

### Target Performance
- **ROI:** 15-25% annual return
- **Position Sizing:** Kelly 0.25 fractional (conservative)
- **Risk Controls:** Daily loss limits, max exposure caps, correlation monitoring

---

## Technology Stack

**Language & Runtime:**
- Python 3.12+ (type hints, async/await)
- Virtual environment (venv)

**Database:**
- PostgreSQL 15+ (ACID compliance, SCD Type 2 versioning)
- SQLAlchemy 2.0+ ORM
- Alembic for migrations

**Key Libraries:**
- `aiohttp` - Async HTTP clients for APIs
- `cryptography` - RSA-PSS authentication for Kalshi
- `pandas`, `numpy` - Data processing
- `pyyaml` - Configuration management
- `pytest` - Testing (>80% coverage target)

**APIs:**
- Kalshi (prediction markets)
- ESPN (live game data)
- OpenWeatherMap (weather conditions)
- Balldontlie (NBA backup data)

---

## Development Phases

| Phase | Name | Status | Deliverables |
|-------|------|--------|--------------|
| **0** | Foundation & Documentation | [DONE] 100% | All docs, YAML configs, schema design |
| **1** | Core Infrastructure | 🔵 Planned | Kalshi API, database, config system |
| **2** | Live Data Integration | 🔵 Planned | ESPN API, schedulers, WebSocket handlers |
| **3** | Data Processing | 🔵 Planned | Async processing pipelines |
| **4** | Probability & Edge Detection | 🔵 Planned | Elo models, edge calculation |
| **5** | Trading Engine | 🔵 Planned | Order execution, risk management |
| **6** | Multi-Sport Expansion | 🔵 Planned | NBA, MLB, Tennis, UFC |
| **7** | Web Dashboard | 🔵 Planned | FastAPI + React monitoring UI |
| **8** | Sentiment Analysis | 🔵 Planned | NLP integration |
| **9** | Advanced Analytics | 🔵 Planned | XGBoost/LSTM models |
| **10** | Multi-Platform | 🔵 Planned | Polymarket integration |

---

## Phase 1: Getting Started

### Prerequisites
- Python 3.12+
- PostgreSQL 15+
- Git

### Environment Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd precog

# 2. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up database
createdb precog_dev

# 5. Configure environment
cp config/env.template .env
# Edit .env with your API keys and database credentials
```

### Required API Keys

**Kalshi (Demo):**
- Sign up: https://demo.kalshi.co
- Get API key and secret from account settings
- Use demo environment for testing (free)

**ESPN:**
- Public API, no key required
- Rate limit: ~60 requests/minute

**OpenWeatherMap:**
- Sign up: https://openweathermap.org/api
- Free tier: 1000 calls/day

### Configuration

All configuration is in YAML files (`config/*.yaml`):
- Edit YAML files for system-wide settings
- Use `.env` for secrets (API keys, passwords)
- See [Configuration Guide](docs/configuration/CONFIGURATION_GUIDE_V3.0.md) for details

---

## Key Principles

### 1. DECIMAL Precision
**Always use `Decimal` for prices, never `float`**

```python
from decimal import Decimal

# [DONE] CORRECT
price = Decimal('0.6500')

# ❌ WRONG
price = 0.65
```

### 2. Conservative Risk Management
- Kelly 0.25 fractional sizing (quarter Kelly)
- Minimum 5% edge for trades
- Daily loss limits ($500)
- Position limits (max 15% per market)
- Circuit breakers on anomalies

### 3. Test-Driven Development
- >80% code coverage required
- Unit tests for all core functions
- Integration tests for APIs
- Backtesting before live trading

### 4. Documentation-First
- Design before code
- Update docs with code changes
- Living documentation approach

---

## Project Structure

```
precog/
├── config/                  # YAML configuration files
├── docs/                    # All project documentation
│   ├── foundation/          # Core architecture & requirements
│   ├── api-integration/     # API guides
│   ├── database/            # Schema documentation
│   ├── configuration/       # Configuration guides
│   └── utility/             # Task plans, handoffs, checklists
├── src/                     # Source code (Phase 1+)
│   ├── api_connectors/      # API clients
│   ├── database/            # Database layer
│   ├── models/              # Probability models
│   ├── trading/             # Trading engine
│   └── utils/               # Utilities
├── tests/                   # Test suite (Phase 1+)
├── .env                     # Environment variables (not in git)
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

---

## Contributing

### Development Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Write tests first (TDD approach)
3. Implement feature
4. Run tests: `pytest`
5. Format code: `black .`
6. Type check: `mypy src/`
7. Commit with descriptive message
8. Push and create pull request

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

**Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

**Example:**
```
feat: Add halftime edge detection for NFL games

- Implement possession-adjusted probability calculations
- Add weather impact assessment
- Include 8 new unit tests

Closes #42
```

---

## Resources

**Documentation:**
- [Master Index](docs/foundation/MASTER_INDEX_V2.2.md) - All project documents
- [Glossary](docs/foundation/GLOSSARY.md) - Terminology reference

**External:**
- [Kalshi API Docs](https://docs.kalshi.com) - Prediction market API
- [PostgreSQL Docs](https://www.postgresql.org/docs/) - Database documentation
- [pytest Docs](https://docs.pytest.org/) - Testing framework

**Learning:**
- "Thinking in Bets" by Annie Duke
- "The Signal and the Noise" by Nate Silver
- "Superforecasting" by Philip Tetlock

---

## License

[To be determined]

---

## Status

**Phase 0:** [DONE] COMPLETE (2025-10-17)
**Phase 1:** 🔵 Ready to begin
**Next Task:** Kalshi RSA-PSS authentication implementation

See [Phase 1 Task Plan](docs/utility/PHASE_1_TASK_PLAN_V1.0.md) for detailed implementation roadmap.

---

**Project:** Precog - Automated Prediction Market Trading
**Version:** Phase 0 Complete
**Last Updated:** 2025-10-17
