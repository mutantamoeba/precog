# Precog

[![CI/CD Pipeline](https://github.com/mutantamoeba/precog/actions/workflows/ci.yml/badge.svg)](https://github.com/mutantamoeba/precog/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/mutantamoeba/precog/branch/main/graph/badge.svg)](https://codecov.io/gh/mutantamoeba/precog)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: TBD](https://img.shields.io/badge/license-TBD-lightgrey.svg)](LICENSE)

**Automated prediction market trading system** that identifies statistical edges in live markets by comparing market prices against probability models built from historical data.

**Status:** Phase 1.5 Complete | Phase 2 In Progress

---

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 15+
- Git

### Installation

```bash
# 1. Clone repository
git clone https://github.com/mutantamoeba/precog.git
cd precog

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install package in development mode (required for src/ layout)
pip install -e .

# 5. Set up database
createdb precog_dev

# 6. Configure environment
cp .env.template .env
# Edit .env with your database credentials and API keys

# 7. Run database migrations
python -m alembic upgrade head
```

### Running the CLI

```bash
# Show available commands
python main.py --help

# Check database connection
python scripts/test_db_connection.py

# Run tests
python -m pytest tests/ -v
```

---

## Installation Options

### Option 1: Local Development

Best for development and testing:

```bash
# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

# Set up environment
cp .env.template .env
# Configure: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, KALSHI_API_KEY, etc.

# Initialize database
python -m alembic upgrade head
```

### Option 2: Docker

Build and run in a container:

```bash
# Build image
docker build -t precog .

# Run with environment variables
docker run -e DATABASE_URL=postgresql://user:pass@host:5432/precog precog python main.py --help
```

### Option 3: Railway Deployment

The repository includes Railway configuration for cloud deployment:

1. Connect your GitHub repository to Railway
2. Railway auto-detects `Dockerfile` and builds
3. Configure environment variables in Railway dashboard:
   - `DATABASE_URL` (Railway provides this for PostgreSQL addon)
   - `KALSHI_API_KEY`
   - `KALSHI_API_SECRET`
   - `PRECOG_ENV=production`

See `railway.toml` for deployment configuration.

---

## Project Structure

```
precog/
├── src/precog/              # Main package (src layout - PEP 517/518)
│   ├── api_connectors/      # API clients (Kalshi, ESPN)
│   ├── config/              # YAML configuration files
│   ├── database/            # Database layer, migrations, CRUD
│   └── utils/               # Utilities (logger, etc.)
├── tests/                   # Test suite (3,200+ tests)
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── property/            # Property-based tests (Hypothesis)
├── scripts/                 # Utility scripts
├── docs/                    # Documentation
│   ├── foundation/          # Core requirements, architecture
│   ├── guides/              # Implementation guides
│   └── database/            # Database documentation
├── main.py                  # CLI entry point
├── pyproject.toml           # Package configuration
├── Dockerfile               # Container build
├── railway.toml             # Railway deployment config
└── README.md                # This file
```

---

## Configuration

### Environment Variables

Required environment variables (set in `.env`):

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=precog_dev
DB_USER=your_user
DB_PASSWORD=your_password

# Kalshi API (get from https://demo.kalshi.co)
KALSHI_API_KEY=your_key
KALSHI_API_SECRET=your_secret
KALSHI_BASE_URL=https://demo-api.kalshi.co

# Optional
PRECOG_ENV=development  # development, test, staging, production
```

### YAML Configuration

Configuration files in `src/precog/config/`:
- `system.yaml` - Database, logging, environment settings
- `trading.yaml` - Risk management, position sizing
- `trade_strategies.yaml` - Entry strategies
- `position_management.yaml` - Exit rules, stop loss
- `probability_models.yaml` - Model configurations
- `markets.yaml` - Platform settings, market filters
- `data_sources.yaml` - API endpoints, polling intervals

See [Configuration Guide](docs/guides/CONFIGURATION_GUIDE_V3.1.md) for details.

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src/precog --cov-report=term-missing

# Run specific test types
python -m pytest tests/unit/ -v           # Unit tests only
python -m pytest tests/integration/ -v    # Integration tests
python -m pytest tests/property/ -v       # Property-based tests

# Run pre-commit checks
pre-commit run --all-files
```

**Test Coverage:** 85%+ across all modules
**Test Count:** 3,200+ tests across 8 test types

---

## Development

### Pre-commit Hooks

Install pre-commit hooks for automatic code quality checks:

```bash
pip install pre-commit
pre-commit install
```

Hooks include:
- Ruff linting and formatting
- Mypy type checking
- Security scanning
- Trailing whitespace / line ending fixes

### Code Style

- **Formatter:** Ruff
- **Linter:** Ruff
- **Type Checker:** Mypy
- **Import Order:** Managed by Ruff

```bash
# Format code
python -m ruff format .

# Lint code
python -m ruff check --fix .

# Type check
python -m mypy src/
```

---

## Documentation

**Key Documents:**
- [Master Index](docs/foundation/MASTER_INDEX_V2.2.md) - Complete document inventory
- [Master Requirements](docs/foundation/MASTER_REQUIREMENTS_V2.3.md) - All requirements
- [Architecture Decisions](docs/foundation/ARCHITECTURE_DECISIONS_V2.3.md) - Design rationale
- [API Integration Guide](docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md) - Kalshi, ESPN APIs
- [Database Schema](docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md) - PostgreSQL schema
- [Configuration Guide](docs/guides/CONFIGURATION_GUIDE_V3.1.md) - YAML configuration

---

## Key Principles

### 1. Decimal Precision
**Always use `Decimal` for prices, never `float`**

```python
from decimal import Decimal

# Correct
price = Decimal('0.6500')

# Wrong - float precision issues
price = 0.65
```

### 2. Conservative Risk Management
- Kelly 0.25 fractional sizing
- Minimum 5% edge for trades
- Daily loss limits
- Position limits (max 15% per market)

### 3. Test-Driven Development
- 80%+ code coverage required
- Property-based testing for edge cases
- Integration tests for APIs

---

## Current Status

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 0-0.7 | Foundation & Infrastructure | Complete | Documentation, CI/CD, testing |
| 1 | Database & API Connectivity | Complete | PostgreSQL, Kalshi client |
| 1.5 | Manager Layer | Complete | Strategy, Model, Position managers |
| 2 | Live Data Integration | In Progress | ESPN API, schedulers |
| 3+ | Trading Engine & Beyond | Planned | See DEVELOPMENT_PHASES |

---

## License

[To be determined]

---

**Project:** Precog - Automated Prediction Market Trading
**Last Updated:** 2025-12-21
