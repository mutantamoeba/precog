# Requirements and Dependencies Guide

---
**Version:** 1.0
**Created:** 2025-10-15
**Status:** ✅ Active
**Purpose:** Map Python packages to system requirements and provide dependency management guidance
**Depends On:** MASTER_REQUIREMENTS_V2.1.md, ENVIRONMENT_CHECKLIST_V1.1.md
**Referenced By:** Phase 1+ implementation
---

## Document Purpose

This guide bridges the gap between **conceptual requirements** (what the system must do) and **implementation dependencies** (which packages enable those capabilities). It provides:

1. **Requirement-to-Package Mapping**: Which dependencies fulfill which requirements
2. **Version Rationale**: Why specific versions are chosen
3. **Critical Exclusions**: Packages/patterns to NEVER use
4. **Installation Guidance**: Special considerations for setup
5. **Dependency Evolution**: How dependencies change across phases

---

## Table of Contents

1. [Quick Reference: Minimal vs. Full Dependencies](#quick-reference)
2. [Requirement-to-Package Mapping](#requirement-to-package-mapping)
3. [Core Dependencies (Phase 1)](#core-dependencies-phase-1)
4. [Data Processing Dependencies (Phase 2-3)](#data-processing-dependencies-phase-2-3)
5. [Advanced Dependencies (Phase 4+)](#advanced-dependencies-phase-4)
6. [Development & Testing Dependencies](#development--testing-dependencies)
7. [Critical Exclusions](#critical-exclusions)
8. [Version Selection Rationale](#version-selection-rationale)
9. [Installation Considerations](#installation-considerations)
10. [Dependency Evolution by Phase](#dependency-evolution-by-phase)

---

## Quick Reference

### Minimal Starter (Phase 1 Week 1)
```txt
# Minimal requirements.txt - ~8 packages
python-dotenv==1.0.0          # Environment variables
pyyaml==6.0.1                 # Configuration files
psycopg2-binary==2.9.9        # PostgreSQL driver
sqlalchemy==2.0.25            # Database ORM
requests==2.31.0              # HTTP client
pytest==7.4.3                 # Testing
black==23.12.1                # Code formatting
pylint==3.0.3                 # Code linting
```

**Use case**: Initial setup, basic API connectivity testing, database schema creation

---

### Full Production (Phase 1-3 Complete)
```txt
# Complete requirements.txt - ~30+ packages

# ========================================
# CORE DEPENDENCIES (Required Phase 1)
# ========================================
python-dotenv==1.0.0          # Load .env variables
pyyaml==6.0.1                 # Parse YAML configs
psycopg2-binary==2.9.9        # PostgreSQL driver
sqlalchemy==2.0.25            # ORM for database operations
alembic==1.13.0               # Database migrations

# ========================================
# API CLIENT DEPENDENCIES (Required Phase 1-2)
# ========================================
requests==2.31.0              # Synchronous HTTP client
httpx==0.25.2                 # Async HTTP client (alternative)
aiohttp==3.9.1                # Async HTTP with WebSocket support
websockets==12.0              # Dedicated WebSocket client
cryptography==41.0.7          # RSA-PSS authentication for Kalshi

# ========================================
# DATA PROCESSING (Required Phase 2-3)
# ========================================
pandas==2.1.4                 # DataFrame operations
numpy==1.26.2                 # ⚠️ USE ONLY FOR CALCULATIONS, NEVER FOR PRICES
python-dateutil==2.8.2        # Date/time parsing
pytz==2023.3                  # Timezone handling
scipy==1.11.4                 # Statistical functions (Phase 3)

# ========================================
# ASYNC & SCHEDULING (Required Phase 2+)
# ========================================
asyncio==3.4.3                # Async framework (built-in Python 3.12+)
apscheduler==3.10.4           # Task scheduling

# ========================================
# LOGGING & MONITORING (Required Phase 1)
# ========================================
structlog==23.2.0             # Structured logging
python-json-logger==2.0.7     # JSON log formatting

# ========================================
# DEVELOPMENT TOOLS (Required All Phases)
# ========================================
pytest==7.4.3                 # Testing framework
pytest-asyncio==0.21.1        # Async test support
pytest-cov==4.1.0             # Code coverage
pytest-mock==3.12.0           # Mocking utilities
black==23.12.1                # Code formatter
pylint==3.0.3                 # Code linter
mypy==1.7.1                   # Type checker
flake8==6.1.0                 # Style guide enforcement

# ========================================
# UTILITIES (Optional but Recommended)
# ========================================
click==8.1.7                  # CLI framework
rich==13.7.0                  # Terminal formatting
tenacity==8.2.3               # Retry logic
pydantic==2.5.3               # Data validation
python-dotenv-vault==0.6.0    # Secret management (production)

# ========================================
# CRITICAL OMISSIONS (NEVER INCLUDE)
# ========================================
# ❌ DO NOT INCLUDE:
# - Any package that uses float for financial calculations
# - pandas-ta (uses float internally)
# - numpy.float64 for prices (use Decimal only)
```

**Use case**: Full production deployment with all features through Phase 3

---

## Requirement-to-Package Mapping

### Functional Requirements (FR)

| Requirement | Description | Primary Packages | Why These Packages |
|-------------|-------------|------------------|-------------------|
| **FR-1.1** | Fetch market data from Kalshi API | `requests`, `aiohttp`, `cryptography` | `requests` for sync calls, `aiohttp` for async, `cryptography` for RSA-PSS auth |
| **FR-1.2** | Parse market data with DECIMAL precision | `python-stdlib` (Decimal) | Built-in `Decimal` type - NO EXTERNAL PACKAGE NEEDED |
| **FR-1.3** | Store market data in PostgreSQL | `psycopg2-binary`, `sqlalchemy` | `psycopg2` is PostgreSQL driver, `sqlalchemy` provides ORM |
| **FR-2.1** | Calculate historical odds from stats | `pandas`, `scipy` | `pandas` for data manipulation, `scipy` for statistical distributions |
| **FR-2.2** | Fetch ESPN/sports API data | `requests`, `aiohttp` | Same as FR-1.1, reused for sports APIs |
| **FR-3.1** | Calculate expected value (EV) | `python-stdlib` (Decimal) | All EV calculations use `Decimal` arithmetic - NO NUMPY FOR PRICES |
| **FR-3.2** | Implement Kelly Criterion | `python-stdlib` (Decimal, math) | Kelly formula implemented with `Decimal` and `math.log` |
| **FR-4.1** | Place orders via Kalshi API | `requests`, `cryptography` | Same as FR-1.1 for authenticated requests |
| **FR-4.2** | Validate orders pre-submission | `pydantic` | Data validation with type checking |
| **FR-5.1** | Track positions in database | `sqlalchemy` | ORM for position CRUD operations |
| **FR-5.2** | Calculate portfolio exposure | `pandas`, `python-stdlib` | `pandas` for aggregation, `Decimal` for summation |
| **FR-6.1** | Load YAML configuration | `pyyaml` | Parse YAML config files |
| **FR-6.2** | Load .env variables | `python-dotenv` | Parse and load environment variables |
| **FR-7.1** | Log all operations | `structlog`, `python-json-logger` | Structured logging with JSON output |
| **FR-7.2** | Store logs in database | `sqlalchemy` | Log records stored as database rows |
| **FR-8.1** | WebSocket real-time updates | `websockets`, `aiohttp` | `websockets` for Kalshi, `aiohttp` supports WebSocket too |

### Non-Functional Requirements (NFR)

| Requirement | Description | Primary Packages | Why These Packages |
|-------------|-------------|------------------|-------------------|
| **NFR-1.1** | Sub-penny precision (4 decimals) | `python-stdlib` (Decimal) | Built-in `Decimal(10,4)` precision |
| **NFR-1.2** | No float arithmetic for prices | `python-stdlib` (Decimal) | Enforced by using ONLY `Decimal` type |
| **NFR-2.1** | Retry logic for API failures | `tenacity`, `aiohttp` retry | `tenacity` provides decorators, `aiohttp` has built-in retry |
| **NFR-2.2** | Exponential backoff | `tenacity` | Configurable backoff strategies |
| **NFR-3.1** | Database connection pooling | `sqlalchemy` | Built-in connection pool (QueuePool) |
| **NFR-3.2** | Async database operations | `sqlalchemy` (async) | SQLAlchemy 2.0+ has native async support |
| **NFR-4.1** | Unit test coverage >80% | `pytest`, `pytest-cov` | Testing framework + coverage reporting |
| **NFR-4.2** | Integration testing | `pytest`, `pytest-asyncio` | Test framework + async test support |
| **NFR-5.1** | Code formatting | `black` | Opinionated formatter (PEP 8 compliant) |
| **NFR-5.2** | Code linting | `pylint`, `flake8` | Static analysis tools |
| **NFR-5.3** | Type checking | `mypy` | Static type checker for Python |
| **NFR-6.1** | Task scheduling | `apscheduler` | Cron-like job scheduling |
| **NFR-6.2** | Async task execution | `asyncio`, `aiohttp` | Python's async framework |

---

## Core Dependencies (Phase 1)

### 1. python-dotenv (1.0.0)
**Requirement Mapping**: FR-6.2, NFR-7.1
**Purpose**: Load environment variables from `.env` file

**Why This Version**:
- 1.0.0 is stable and widely adopted
- Full support for multi-line values
- Compatible with Python 3.12+

**Usage Pattern**:
```python
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("KALSHI_API_KEY")
```

**Critical Notes**:
- ✅ Load `.env` at application startup (before any config loading)
- ✅ Never commit `.env` to version control (use `.env.template`)
- ⚠️ Validate that required variables exist after loading

---

### 2. pyyaml (6.0.1)
**Requirement Mapping**: FR-6.1
**Purpose**: Parse YAML configuration files

**Why This Version**:
- 6.0.1 is latest stable (addresses all known security vulnerabilities)
- Native support for Python 3.12+
- Backward compatible with older YAML files

**Usage Pattern**:
```python
import yaml
from decimal import Decimal

def decimal_constructor(loader, node):
    value = loader.construct_scalar(node)
    return Decimal(value)

# Register custom Decimal constructor
yaml.add_constructor('!decimal', decimal_constructor)

with open('config/trading.yaml', 'r') as f:
    config = yaml.safe_load(f)
```

**Critical Notes**:
- ✅ ALWAYS use `yaml.safe_load()` (never `yaml.load()` - security risk)
- ✅ Register custom constructor for Decimal types
- ⚠️ Validate schema after loading (use Pydantic models)

---

### 3. psycopg2-binary (2.9.9)
**Requirement Mapping**: FR-1.3, FR-5.1, FR-7.2
**Purpose**: PostgreSQL database driver

**Why This Version**:
- 2.9.9 is latest stable with Python 3.12 support
- `-binary` variant includes compiled C library (easier installation on Windows)
- Native support for PostgreSQL 15+ features

**Usage Pattern**:
```python
import psycopg2
from decimal import Decimal

# Register Decimal adapter
psycopg2.extensions.register_adapter(Decimal, psycopg2._psycopg.Decimal)

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="precog",
    user="precog_trader",
    password=os.getenv("DB_PASSWORD")
)
```

**Critical Notes**:
- ✅ Use `psycopg2-binary` for development (easier)
- ⚠️ Consider `psycopg2` (source build) for production (better performance)
- ✅ Always register Decimal adapter for price columns
- ⚠️ Use connection pooling via SQLAlchemy (don't manage connections manually)

---

### 4. sqlalchemy (2.0.25)
**Requirement Mapping**: FR-1.3, FR-5.1, FR-7.2, NFR-3.1, NFR-3.2
**Purpose**: ORM for database operations, connection pooling, migrations

**Why This Version**:
- 2.0.25 is latest stable (2.0+ series is major rewrite)
- Native async support (`AsyncEngine`, `async_sessionmaker`)
- Improved type hints for better IDE support
- Breaking changes from 1.x (don't use older versions)

**Usage Pattern**:
```python
from sqlalchemy import create_engine, Column, DECIMAL, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from decimal import Decimal

Base = declarative_base()

class Market(Base):
    __tablename__ = 'markets'

    ticker = Column(String(100), primary_key=True)
    yes_bid = Column(DECIMAL(10, 4), nullable=False)  # ✅ DECIMAL not Float

engine = create_engine(
    "postgresql+psycopg2://user:pass@localhost/precog",
    pool_size=10,  # Connection pool
    max_overflow=20
)

SessionLocal = sessionmaker(bind=engine)
```

**Critical Notes**:
- ✅ ALWAYS use `DECIMAL(10,4)` for price columns (NEVER `Float`)
- ✅ Use connection pooling (default QueuePool with pool_size=5)
- ⚠️ SQLAlchemy 2.0+ requires `select()` instead of `query()` (breaking change)
- ✅ Use `async_sessionmaker` for async operations (Phase 2+)

---

### 5. alembic (1.13.0)
**Requirement Mapping**: FR-1.3 (database migrations)
**Purpose**: Database schema version control and migrations

**Why This Version**:
- 1.13.0 is latest stable with SQLAlchemy 2.0 support
- Auto-generates migration scripts from model changes
- Supports both online and offline migrations

**Usage Pattern**:
```bash
# Initialize Alembic
alembic init alembic

# Create migration after model changes
alembic revision --autogenerate -m "Add markets table"

# Apply migration
alembic upgrade head

# Rollback last migration
alembic downgrade -1
```

**Critical Notes**:
- ✅ ALWAYS review auto-generated migrations before applying
- ✅ Test migrations on dev database before production
- ⚠️ Alembic doesn't detect all changes (e.g., CHECK constraints)
- ✅ Use offline mode for generating SQL scripts for manual review

---

### 6. requests (2.31.0)
**Requirement Mapping**: FR-1.1, FR-2.2, FR-4.1
**Purpose**: Synchronous HTTP client for API calls

**Why This Version**:
- 2.31.0 is latest stable and battle-tested
- Simple, intuitive API
- Wide ecosystem support (mocking, testing)
- Best for synchronous operations (Phase 1)

**Usage Pattern**:
```python
import requests
from decimal import Decimal

response = requests.get(
    "https://trading-api.kalshi.com/trade-api/v2/markets",
    headers={"Authorization": f"Bearer {token}"},
    timeout=10
)

data = response.json()
# ✅ Parse price as Decimal
yes_bid = Decimal(data["yes_bid_dollars"])
```

**Critical Notes**:
- ✅ ALWAYS set timeouts (avoid hanging forever)
- ✅ Use session objects for connection pooling
- ⚠️ Synchronous - blocks execution (use `aiohttp` for async in Phase 2+)
- ✅ Excellent for simple REST API calls

---

### 7. cryptography (41.0.7)
**Requirement Mapping**: FR-1.1, FR-4.1 (Kalshi RSA-PSS authentication)
**Purpose**: RSA-PSS signature generation for Kalshi API

**Why This Version**:
- 41.0.7 is latest stable
- Native support for RSA-PSS with MGF1(SHA256)
- Required for Kalshi authentication (HMAC-SHA256 won't work)

**Usage Pattern**:
```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64

def sign_request(private_key_path, timestamp, method, path):
    with open(private_key_path, 'rb') as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    message = f"{timestamp}{method}{path}".encode('utf-8')

    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )

    return base64.b64encode(signature).decode('utf-8')
```

**Critical Notes**:
- ✅ Must use PSS padding (not PKCS1v15)
- ✅ Salt length must be `DIGEST_LENGTH`
- ⚠️ Different from HMAC-SHA256 (common mistake)
- ✅ See `API_INTEGRATION_GUIDE_V1.0.md` for complete implementation

---

### 8. structlog (23.2.0)
**Requirement Mapping**: FR-7.1, NFR-5.4
**Purpose**: Structured logging with context

**Why This Version**:
- 23.2.0 is latest stable
- JSON output for log aggregation
- Context binding (attach user/request IDs to all logs)
- Performance optimized

**Usage Pattern**:
```python
import structlog

logger = structlog.get_logger()

# Bind context that persists across logs
logger = logger.bind(user_id=123, session="abc")

logger.info("order_placed", ticker="MARKET-YES", quantity=10, price=Decimal("0.45"))
# Output: {"event": "order_placed", "ticker": "MARKET-YES", "quantity": 10, "price": "0.45", "user_id": 123, "session": "abc"}
```

**Critical Notes**:
- ✅ Use structured logging (never f-strings in logs)
- ✅ Bind context early (request ID, user ID)
- ✅ Log Decimal as string (JSON serialization)
- ⚠️ Configure processors for timezone, stack traces

---

## Data Processing Dependencies (Phase 2-3)

### 9. pandas (2.1.4)
**Requirement Mapping**: FR-2.1, FR-5.2
**Purpose**: DataFrame operations for historical data analysis

**Why This Version**:
- 2.1.4 is latest stable with Python 3.12 support
- Improved memory efficiency vs. 1.x
- Native support for nullable dtypes

**Usage Pattern**:
```python
import pandas as pd
from decimal import Decimal

# ✅ CORRECT: Load data without converting prices to float
df = pd.read_sql(
    "SELECT ticker, yes_bid, no_bid FROM markets",
    engine,
    dtype={'yes_bid': 'object', 'no_bid': 'object'}  # Keep as Decimal
)

# ❌ WRONG: This converts to float64
# df = pd.read_sql("SELECT ...", engine)  # Defaults to float64

# ✅ CORRECT: Aggregate with Decimal
total_exposure = sum(Decimal(str(x)) for x in df['position_size'])

# ❌ WRONG: This uses float arithmetic
# total_exposure = df['position_size'].sum()  # NEVER DO THIS FOR PRICES
```

**Critical Notes**:
- ⚠️ **CRITICAL**: Pandas defaults to float64 for numeric columns
- ✅ ALWAYS specify `dtype='object'` for price columns when loading from SQL
- ✅ Use `Decimal` for all price calculations (not pandas native operations)
- ✅ Pandas is ONLY for data manipulation, NOT for price arithmetic
- ⚠️ Consider Polars (future) for better Decimal support

---

### 10. numpy (1.26.2)
**Requirement Mapping**: FR-2.1 (statistical calculations ONLY)
**Purpose**: Array operations for non-price calculations

**Why This Version**:
- 1.26.2 is latest stable with Python 3.12 support
- Core dependency for scipy, pandas

**CRITICAL USAGE RESTRICTIONS**:
```python
import numpy as np
from decimal import Decimal

# ✅ CORRECT: Use numpy for statistics (not prices)
historical_scores = np.array([21, 28, 14, 35])
avg_score = np.mean(historical_scores)  # OK - these are counts, not prices

# ❌ WRONG: NEVER use numpy for prices
prices = np.array([0.45, 0.46, 0.47])  # NEVER - these will be float64
avg_price = np.mean(prices)             # NEVER - rounding errors

# ✅ CORRECT: Use Decimal for prices
prices = [Decimal("0.45"), Decimal("0.46"), Decimal("0.47")]
avg_price = sum(prices) / len(prices)   # Exact arithmetic
```

**Critical Notes**:
- ⚠️ **DO NOT USE NUMPY FOR PRICES** - it uses float64 (rounding errors)
- ✅ Use numpy for: counts, scores, statistical distributions
- ❌ NEVER use numpy for: prices, odds, probabilities, EV calculations
- ✅ See `KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md` for examples

---

### 11. scipy (1.11.4)
**Requirement Mapping**: FR-2.1 (statistical distributions)
**Purpose**: Advanced statistics for odds modeling

**Why This Version**:
- 1.11.4 is latest stable
- Required for probability distributions (normal, binomial)

**Usage Pattern**:
```python
from scipy import stats
from decimal import Decimal

# Calculate probability from historical scores
mean_score = 24.5
std_score = 7.2

# Probability team scores > 28 points
prob_over_28 = 1 - stats.norm.cdf(28, loc=mean_score, scale=std_score)

# ✅ Convert to Decimal for price calculations
implied_odds = Decimal(str(prob_over_28))
```

**Critical Notes**:
- ✅ Use scipy for probability distributions
- ⚠️ scipy returns float - convert to Decimal immediately
- ✅ Good for: normal dist, binomial, poisson distributions

---

## Advanced Dependencies (Phase 4+)

### 12. aiohttp (3.9.1)
**Requirement Mapping**: FR-8.1, NFR-3.2, NFR-6.2
**Purpose**: Async HTTP client and WebSocket support

**Why This Version**:
- 3.9.1 is latest stable
- Native WebSocket support
- Connection pooling
- Used in Phase 2+ for real-time data

**Usage Pattern**:
```python
import aiohttp
import asyncio

async def fetch_markets():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.kalshi.com/v2/markets") as response:
            return await response.json()

# Run async function
asyncio.run(fetch_markets())
```

**Critical Notes**:
- ✅ Use for Phase 2+ (real-time data ingestion)
- ✅ Supports WebSocket for Kalshi live updates
- ⚠️ More complex than `requests` (async/await syntax)
- ✅ Better performance for concurrent API calls

---

### 13. websockets (12.0)
**Requirement Mapping**: FR-8.1
**Purpose**: Dedicated WebSocket client (alternative to aiohttp)

**Why This Version**:
- 12.0 is latest stable
- Simpler API than aiohttp WebSocket
- Better for dedicated WebSocket connections

**Usage Pattern**:
```python
import websockets
import asyncio

async def listen_to_market_updates():
    uri = "wss://api.kalshi.com/v2/websocket"
    async with websockets.connect(uri) as websocket:
        await websocket.send('{"action": "subscribe", "ticker": "MARKET-YES"}')

        async for message in websocket:
            data = json.loads(message)
            # Process market update
```

**Critical Notes**:
- ✅ Use for Phase 2+ WebSocket connections
- ✅ Simpler than aiohttp for WebSocket-only use cases
- ⚠️ Requires async/await (same as aiohttp)

---

### 14. apscheduler (3.10.4)
**Requirement Mapping**: NFR-6.1
**Purpose**: Task scheduling (cron-like jobs)

**Why This Version**:
- 3.10.4 is latest stable
- Supports async jobs
- Multiple job stores (memory, database, Redis)

**Usage Pattern**:
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

# Run every hour at minute 0
scheduler.add_job(
    fetch_market_updates,
    CronTrigger(minute=0),
    id='hourly_market_fetch'
)

scheduler.start()
```

**Critical Notes**:
- ✅ Use for Phase 2+ (automated data fetching)
- ✅ Supports async functions (important for I/O-bound tasks)
- ⚠️ Use database job store for persistence (survive restarts)

---

## Development & Testing Dependencies

### 15. pytest (7.4.3)
**Requirement Mapping**: NFR-4.1
**Purpose**: Testing framework

**Why This Version**:
- 7.4.3 is latest stable
- Rich plugin ecosystem
- Better error messages than unittest

**Usage Pattern**:
```python
import pytest
from decimal import Decimal
from myapp.trading import calculate_kelly_size

def test_kelly_calculation():
    edge = Decimal("0.10")  # 10% edge
    odds = Decimal("0.45")
    kelly_fraction = Decimal("0.25")

    size = calculate_kelly_size(edge, odds, kelly_fraction)

    assert isinstance(size, Decimal)
    assert size > 0
    assert size <= 1  # Never bet more than 100% of bankroll
```

**Critical Notes**:
- ✅ Test coverage goal: >80%
- ✅ Use fixtures for database setup/teardown
- ✅ Mock API calls (use `pytest-mock`)
- ✅ Test Decimal precision explicitly

---

### 16. pytest-asyncio (0.21.1)
**Requirement Mapping**: NFR-4.2
**Purpose**: Async test support for pytest

**Usage Pattern**:
```python
import pytest

@pytest.mark.asyncio
async def test_async_market_fetch():
    result = await fetch_market_data("MARKET-YES")
    assert result is not None
```

**Critical Notes**:
- ✅ Required for testing async functions
- ✅ Fixtures can be async too

---

### 17. pytest-cov (4.1.0)
**Requirement Mapping**: NFR-4.1
**Purpose**: Code coverage reporting

**Usage Pattern**:
```bash
# Run tests with coverage
pytest --cov=src --cov-report=html

# View report
open htmlcov/index.html
```

**Critical Notes**:
- ✅ Generate coverage reports after every test run
- ✅ Target: >80% coverage before moving to next phase

---

### 18. black (23.12.1)
**Requirement Mapping**: NFR-5.1
**Purpose**: Code formatter (PEP 8 compliant)

**Usage Pattern**:
```bash
# Format all Python files
black src/

# Check formatting (CI/CD)
black --check src/
```

**Critical Notes**:
- ✅ Run before every commit
- ✅ Configure line length: 100 characters
- ✅ Use in pre-commit hooks

---

### 19. pylint (3.0.3)
**Requirement Mapping**: NFR-5.2
**Purpose**: Code linter (static analysis)

**Usage Pattern**:
```bash
# Lint all files
pylint src/

# Lint with custom config
pylint --rcfile=.pylintrc src/
```

**Critical Notes**:
- ✅ Fix all errors before merging
- ⚠️ Some warnings can be ignored (disable selectively)
- ✅ Target: >9.0/10.0 score

---

### 20. mypy (1.7.1)
**Requirement Mapping**: NFR-5.3
**Purpose**: Static type checker

**Usage Pattern**:
```python
from decimal import Decimal
from typing import Optional

def calculate_ev(prob: Decimal, odds: Decimal) -> Decimal:
    return (prob * odds) - (Decimal("1") - prob)

# mypy will catch type errors
result: Decimal = calculate_ev(Decimal("0.60"), Decimal("0.45"))
```

**Critical Notes**:
- ✅ Add type hints to all function signatures
- ✅ Use `Decimal` type for prices (not `float`)
- ⚠️ mypy strict mode may be too strict initially

---

## Critical Exclusions

### ❌ NEVER USE These Packages

| Package | Why Excluded | Alternative |
|---------|-------------|-------------|
| **numpy (for prices)** | Uses float64 - rounding errors | `Decimal` from stdlib |
| **pandas (for price calculations)** | Defaults to float64 | `Decimal` arithmetic |
| **pandas-ta** | Uses float internally | Custom `Decimal`-based functions |
| **floating-point types** | Rounding errors accumulate | Always use `Decimal` |
| **yaml.load()** | Security vulnerability (arbitrary code execution) | `yaml.safe_load()` |
| **pickle (for untrusted data)** | Security risk | JSON with `json.loads()` |
| **requests (without timeout)** | Hangs indefinitely | Always set `timeout` |

---

### ⚠️ Conditional Exclusions

| Package | When NOT to Use | When OK to Use |
|---------|-----------------|----------------|
| **numpy** | Price calculations, odds, probabilities | Score statistics, counts |
| **pandas** | Price arithmetic | Data loading, filtering, aggregation (with Decimal columns) |
| **sqlite3** | Production database | Testing, prototyping |
| **threading** | I/O-bound tasks | CPU-bound tasks (rare in this project) |

---

## Version Selection Rationale

### Why Specific Versions Matter

1. **Security**: Older versions may have known vulnerabilities
2. **Compatibility**: Python 3.12+ requires compatible versions
3. **Breaking Changes**: Some packages (SQLAlchemy 2.0) have major API changes
4. **Stability**: Latest stable avoids bleeding-edge bugs

### Version Selection Criteria

| Criteria | Weight | Example |
|----------|--------|---------|
| **Security** | High | pyyaml 6.0.1 (fixes CVE-2020-14343) |
| **Compatibility** | High | psycopg2-binary 2.9.9 (Python 3.12 support) |
| **Stability** | Medium | requests 2.31.0 (battle-tested) |
| **Features** | Low | structlog 23.2.0 (context binding) |

---

### When to Update Dependencies

**Do update when:**
- ✅ Security vulnerability announced (check GitHub Security Advisories)
- ✅ Python version upgrade requires it
- ✅ New feature needed from newer version

**Don't update when:**
- ❌ "Latest is always better" mentality
- ❌ Mid-phase (wait until phase complete)
- ❌ No clear benefit

---

## Installation Considerations

### Windows-Specific Issues

| Package | Issue | Solution |
|---------|-------|----------|
| **psycopg2** | Requires C compiler | Use `psycopg2-binary` instead |
| **cryptography** | Build dependencies | Pre-compiled wheels work (usually) |
| **numpy/scipy** | Large downloads | Be patient (300MB+ total) |

---

### Linux-Specific Issues

| Package | Issue | Solution |
|---------|-------|----------|
| **psycopg2** | Missing libpq-dev | `apt install libpq-dev` (Debian/Ubuntu) |
| **cryptography** | Missing OpenSSL | `apt install libssl-dev` |

---

### Mac-Specific Issues

| Package | Issue | Solution |
|---------|-------|----------|
| **psycopg2** | Missing PostgreSQL headers | `brew install postgresql@15` |
| **cryptography** | Missing OpenSSL | `brew install openssl` |

---

## Dependency Evolution by Phase

### Phase 1: Core Infrastructure
```txt
✅ Required NOW:
- python-dotenv
- pyyaml
- psycopg2-binary
- sqlalchemy
- alembic
- requests
- cryptography
- structlog
- pytest
- black
- pylint

❌ Not needed yet:
- aiohttp
- websockets
- apscheduler
- pandas
- numpy
- scipy
```

---

### Phase 2: Data Processing
```txt
✅ Add in Phase 2:
- pandas
- numpy (limited use)
- python-dateutil
- pytz

✅ Still need from Phase 1:
- Everything from Phase 1
```

---

### Phase 3: Analytics & Odds Modeling
```txt
✅ Add in Phase 3:
- scipy
- pydantic (data validation)

✅ Still need from Phase 1-2:
- Everything from Phase 1-2
```

---

### Phase 4: Live Trading
```txt
✅ Add in Phase 4:
- aiohttp
- websockets
- apscheduler
- tenacity (retry logic)

✅ Still need from Phase 1-3:
- Everything from Phase 1-3
```

---

## Summary: Key Takeaways

### ✅ DO:
1. **Always use `Decimal` for prices** - NEVER float, NEVER numpy.float64
2. **Pin versions in requirements.txt** - Exact versions for reproducibility
3. **Update dependencies cautiously** - Test thoroughly after updates
4. **Use `psycopg2-binary` for development** - Easier installation
5. **Load .env early** - Before any configuration loading
6. **Validate dependencies match requirements** - Cross-reference this doc with MASTER_REQUIREMENTS_V2.1.md

### ❌ DON'T:
1. **Don't use float for financial calculations** - Rounding errors compound
2. **Don't use `yaml.load()`** - Security vulnerability
3. **Don't omit timeouts on requests** - Hangs indefinitely
4. **Don't update mid-phase** - Wait until phase complete
5. **Don't use pandas for price arithmetic** - Only for data manipulation
6. **Don't install everything at once** - Start minimal (Phase 1), add as needed

---

## Related Documents

- **MASTER_REQUIREMENTS_V2.1.md**: Requirements that these dependencies fulfill
- **ENVIRONMENT_CHECKLIST_V1.1.md**: Step-by-step setup instructions
- **KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md**: Critical guidance on Decimal vs. float
- **API_INTEGRATION_GUIDE_V1.0.md**: How to use `requests`, `aiohttp` for API calls
- **CONFIGURATION_GUIDE_V2.1.md**: How to use `pyyaml`, `python-dotenv`

---

**END OF REQUIREMENTS AND DEPENDENCIES GUIDE**
