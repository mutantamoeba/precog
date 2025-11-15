# Phase 1: Task-Based Implementation Plan

---
**Version:** 1.1
**Created:** 2025-10-15
**Last Updated:** 2025-10-16
**Status:** 🟢 Ready to Execute
**Changes in v1.1:** Updated terminology (odds → probability); corrected table names and function names; updated document references
**Duration:** 6 weeks (72 hours @ 12 hours/week)
**Goal:** Build working Kalshi API client, database, config system, logging, CLI
---

## Quick Navigation

- [Success Criteria](#success-criteria)
- [Task List Overview](#task-list-overview)
- [Detailed Tasks](#detailed-tasks)
- [Critical Path](#critical-path)
- [Risk Mitigation](#risk-mitigation)
- [Week-by-Week Milestones](#week-by-week-milestones)

---

## Success Criteria

**Phase 1 is complete when ALL of these are true:**

- [x] Environment setup complete (Python, PostgreSQL, Git, Claude Code)
- [ ] Can authenticate with Kalshi demo environment
- [ ] Can fetch and store market data with DECIMAL precision
- [ ] Database stores versioned market updates (SCD Type 2)
- [ ] Config system loads YAML and applies DB overrides
- [ ] Logging captures all API calls and errors to file + database
- [ ] CLI commands work (`precog db-init`, `precog health-check`, etc.)
- [ ] Test coverage >80%
- [ ] **Zero float types for prices** (all DECIMAL)
- [ ] All code formatted (Black), linted (Pylint >9.0), type-checked (mypy)

---

## Task List Overview

**Total: 28 tasks across 6 categories**

| Category | Tasks | Est. Hours | Dependency Chain |
|----------|-------|------------|-----------------|
| **A. Database Foundation** | 6 tasks | 16 hours | None (start here) |
| **B. Configuration System** | 4 tasks | 8 hours | Depends on A1 |
| **C. Logging Infrastructure** | 3 tasks | 6 hours | Depends on A1, B1 |
| **D. Kalshi API Client** | 7 tasks | 20 hours | Depends on A1-A6, C1-C3 |
| **E. CLI Framework** | 4 tasks | 8 hours | Depends on all above |
| **F. Testing & Documentation** | 4 tasks | 14 hours | Ongoing + final phase |

**Total Estimated Hours:** 72 hours (matches 6-week timeline)

---

## Task Notation Guide

Each task follows this format:

```
[TASK_ID] Task Name (Duration)
├─ Depends on: [OTHER_TASK_IDs]
├─ Deliverables: What you'll create
├─ Success criteria: How to know it's done
├─ Testing: What tests to write
└─ Risks: Potential blockers
```

---

## Detailed Tasks

### Category A: Database Foundation (16 hours)

#### [A1] Database Schema Creation (3 hours)
**Priority:** 🔴 Critical - Start here
**Depends on:** None (foundational)

**Deliverables:**
- `database/schema.sql` - Complete SQL schema
- `database/models.py` - SQLAlchemy ORM models
- `.env` configured with database credentials

**Success Criteria:**
- All tables from `DATABASE_SCHEMA_SUMMARY.md` v1.2 created
- Specifically: `probability_matrices` table (NOT `odds_matrices`)
- All columns use DECIMAL(10,4) for prices (never Float)
- All CHECK constraints enforced (e.g., `CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999)`)
- Foreign key relationships established
- Indexes created on frequently queried columns
- No references to `odds_buckets` or `odds_matrices` in schema

**Implementation Steps:**
```sql
-- Critical: DECIMAL not Float
CREATE TABLE markets (
    ticker VARCHAR(100) PRIMARY KEY,
    yes_bid DECIMAL(10,4) NOT NULL,  -- ✅ DECIMAL
    yes_ask DECIMAL(10,4) NOT NULL,
    -- never: yes_bid FLOAT  ❌
    CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999),
    CHECK (yes_ask >= 0.0001 AND yes_ask <= 0.9999),
    CHECK (yes_ask > yes_bid)  -- Spread must be positive
);
```

**Testing:**
- [ ] Schema loads without errors
- [ ] Can insert Decimal values: `Decimal("0.4975")`
- [ ] CHECK constraints reject invalid data: `Decimal("1.5")` fails
- [ ] Foreign keys enforce referential integrity

**Risks:**
- ⚠️ Float vs. Decimal confusion (use cheat sheet!)
- ⚠️ PostgreSQL version <15 (check compatibility)

**Time Breakdown:**
- Schema design: 1 hour
- SQLAlchemy models: 1.5 hours
- Testing: 0.5 hours

---

#### [A2] Database Connection Pooling (2 hours)
**Priority:** 🔴 Critical
**Depends on:** [A1]

**Deliverables:**
- `database/connection.py` - Connection management
- Connection pool configured (pool_size=10, max_overflow=20)

**Success Criteria:**
- Can establish connection to PostgreSQL
- Connection pool reuses connections (no new connection per query)
- Handles connection failures gracefully (retry logic)
- Logs connection events (pool exhaustion, failures)

**Implementation:**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os

# ✅ Use connection pooling
engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}",
    poolclass=QueuePool,
    pool_size=10,          # 10 connections in pool
    max_overflow=20,       # Up to 30 total (10 + 20)
    pool_pre_ping=True,    # Verify connections before use
    echo=False             # Set True for debugging
)

SessionLocal = sessionmaker(bind=engine)

def get_db_session():
    """Get database session with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Testing:**
- [ ] Connection established successfully
- [ ] Multiple concurrent queries use pool (not new connections)
- [ ] Pool exhaustion handled (blocks until connection available)
- [ ] Failed connections retry with exponential backoff

**Risks:**
- ⚠️ Pool exhaustion under heavy load (monitor in Phase 2+)
- ⚠️ Stale connections (pool_pre_ping solves this)

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

#### [A3] CRUD Operations (4 hours)
**Priority:** 🔴 Critical
**Depends on:** [A1], [A2]

**Deliverables:**
- `database/crud_operations.py` - All CRUD functions
- Functions: `create_market()`, `read_market()`, `update_market()`, `delete_market()`, etc.

**Success Criteria:**
- All CRUD operations work for every table
- All functions accept/return Decimal for prices (never float)
- Transactions rollback on error (no partial writes)
- SCD Type 2 versioning works (RowCurrentInd=1 for current, 0 for historical)

**Critical Functions:**

```python
from decimal import Decimal
from sqlalchemy.orm import Session
from database.models import Market
from datetime import datetime

def create_market(
    db: Session,
    ticker: str,
    yes_bid: Decimal,  # ✅ Decimal not float
    yes_ask: Decimal,
    event_ticker: str
) -> Market:
    """Create new market record."""
    market = Market(
        ticker=ticker,
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        event_ticker=event_ticker,
        RowCurrentInd=1,
        RowStartDate=datetime.utcnow()
    )
    db.add(market)
    db.commit()
    db.refresh(market)
    return market

def update_market_with_versioning(
    db: Session,
    ticker: str,
    new_yes_bid: Decimal,
    new_yes_ask: Decimal
) -> Market:
    """
    Update market using SCD Type 2 versioning.
    - Set old record RowCurrentInd=0, RowEndDate=now
    - Insert new record with RowCurrentInd=1
    """
    # Find current record
    old_market = db.query(Market).filter(
        Market.ticker == ticker,
        Market.RowCurrentInd == 1
    ).first()

    if not old_market:
        raise ValueError(f"Market {ticker} not found")

    # Close old record
    old_market.RowCurrentInd = 0
    old_market.RowEndDate = datetime.utcnow()

    # Create new record
    new_market = Market(
        ticker=ticker,
        yes_bid=new_yes_bid,
        yes_ask=new_yes_ask,
        event_ticker=old_market.event_ticker,
        RowCurrentInd=1,
        RowStartDate=datetime.utcnow()
    )

    db.add(new_market)
    db.commit()
    return new_market

def get_current_market(db: Session, ticker: str) -> Market:
    """Get current market (RowCurrentInd=1)."""
    return db.query(Market).filter(
        Market.ticker == ticker,
        Market.RowCurrentInd == 1
    ).first()

def get_market_history(db: Session, ticker: str) -> list[Market]:
    """Get all historical versions of a market."""
    return db.query(Market).filter(
        Market.ticker == ticker
    ).order_by(Market.RowStartDate.desc()).all()
```

**Testing:**
- [ ] Create: Insert new market with DECIMAL prices
- [ ] Read: Fetch current market (RowCurrentInd=1)
- [ ] Update: SCD Type 2 versioning works (old record closed, new created)
- [ ] Delete: Soft delete or hard delete (depending on requirements)
- [ ] Decimal precision: Prices stored/retrieved with 4 decimal places
- [ ] Transaction rollback: Failed updates don't corrupt data

**Risks:**
- ⚠️ Decimal → Float conversion (always use `Decimal` type hints)
- ⚠️ Forgotten RowCurrentInd checks (always filter on RowCurrentInd=1)

**Time Breakdown:**
- Implementation: 2.5 hours
- Testing: 1.5 hours

---

#### [A4] Database Migrations with Alembic (3 hours)
**Priority:** 🟡 Important
**Depends on:** [A1], [A2], [A3]

**Deliverables:**
- `alembic.ini` - Alembic configuration
- `alembic/env.py` - Migration environment
- `alembic/versions/001_initial_schema.py` - Initial migration

**Success Criteria:**
- `alembic upgrade head` creates all tables
- `alembic downgrade -1` rolls back last migration
- Migrations are version-controlled (in Git)
- Future schema changes can be applied via migrations

**Implementation:**
```bash
# Initialize Alembic
alembic init alembic

# Configure alembic.ini
# Edit: sqlalchemy.url = postgresql+psycopg2://user:pass@localhost/precog

# Generate initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head

# Test rollback
alembic downgrade -1

# Re-apply
alembic upgrade head
```

**Testing:**
- [ ] Migration creates all tables
- [ ] Rollback removes tables
- [ ] Re-applying migration works (idempotent)
- [ ] DECIMAL types preserved in migration (not converted to Float)

**Risks:**
- ⚠️ Alembic auto-generate misses CHECK constraints (add manually)
- ⚠️ Data loss on rollback (expected - this is schema only)

**Time Breakdown:**
- Setup: 1 hour
- Initial migration: 1 hour
- Testing: 1 hour

---

#### [A5] Database Seeding & Test Data (2 hours)
**Priority:** 🟢 Nice to have
**Depends on:** [A1], [A2], [A3]

**Deliverables:**
- `scripts/seed_database.py` - Populate with sample data
- Sample markets, events, leagues for testing

**Success Criteria:**
- Can quickly populate dev database with realistic data
- Test data includes edge cases (spread=0.0001, prices near 0/1)
- Idempotent (can re-run without errors)

**Implementation:**
```python
from decimal import Decimal
from database.crud_operations import create_market, create_event
from database.connection import SessionLocal

def seed_markets():
    db = SessionLocal()

    # Sample NFL market
    create_market(
        db=db,
        ticker="NFL-KC-BUF-YES",
        yes_bid=Decimal("0.5200"),
        yes_ask=Decimal("0.5225"),
        event_ticker="NFL-KC-BUF"
    )

    # Edge case: very tight spread
    create_market(
        db=db,
        ticker="NBA-GSW-LAL-YES",
        yes_bid=Decimal("0.7550"),
        yes_ask=Decimal("0.7551"),  # Only 0.01¢ spread!
        event_ticker="NBA-GSW-LAL"
    )

    # Edge case: near extremes
    create_market(
        db=db,
        ticker="TENNIS-YES",
        yes_bid=Decimal("0.0500"),
        yes_ask=Decimal("0.0525"),
        event_ticker="TENNIS"
    )

    db.close()

if __name__ == "__main__":
    seed_markets()
    print("✅ Database seeded successfully")
```

**Testing:**
- [ ] Script runs without errors
- [ ] Data appears in database with correct DECIMAL precision
- [ ] Re-running script handles duplicates gracefully

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

#### [A6] Database Health Checks (2 hours)
**Priority:** 🟡 Important
**Depends on:** [A1], [A2]

**Deliverables:**
- `database/health.py` - Health check functions
- Functions: `check_connection()`, `check_table_exists()`, `check_decimal_precision()`

**Success Criteria:**
- Can verify database is reachable
- Can verify all tables exist
- Can verify DECIMAL precision is correct (not Float)
- Returns actionable error messages

**Implementation:**
```python
from sqlalchemy import inspect, text
from database.connection import engine
from decimal import Decimal

def check_connection() -> dict:
    """Verify database connection."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}

def check_tables_exist() -> dict:
    """Verify all required tables exist."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    required_tables = ['markets', 'events', 'leagues', 'trades', 'positions', 'logs']
    missing_tables = [t for t in required_tables if t not in existing_tables]

    if missing_tables:
        return {"status": "error", "message": f"Missing tables: {missing_tables}"}
    return {"status": "ok", "message": "All tables exist"}

def check_decimal_precision() -> dict:
    """Verify price columns use DECIMAL(10,4), not Float."""
    inspector = inspect(engine)
    columns = inspector.get_columns('markets')

    price_columns = ['yes_bid', 'yes_ask', 'no_bid', 'no_ask']
    for col in columns:
        if col['name'] in price_columns:
            col_type = str(col['type'])
            if 'NUMERIC' not in col_type and 'DECIMAL' not in col_type:
                return {
                    "status": "error",
                    "message": f"Column {col['name']} is {col_type}, should be DECIMAL(10,4)"
                }

    return {"status": "ok", "message": "All price columns use DECIMAL precision"}

def run_all_health_checks() -> dict:
    """Run all health checks and return summary."""
    checks = {
        "connection": check_connection(),
        "tables": check_tables_exist(),
        "decimal_precision": check_decimal_precision()
    }

    all_ok = all(check["status"] == "ok" for check in checks.values())

    return {
        "overall_status": "ok" if all_ok else "error",
        "checks": checks
    }
```

**Testing:**
- [ ] Health check passes on healthy database
- [ ] Health check fails on disconnected database
- [ ] Decimal precision check catches Float columns

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

### Category B: Configuration System (8 hours)

#### [B1] YAML Configuration Loader (3 hours)
**Priority:** 🔴 Critical
**Depends on:** [A1] (needs database models)

**Deliverables:**
- `config/config_loader.py` - YAML parser with Decimal support
- `config/*.yaml` - 7 YAML files (from CONFIGURATION_GUIDE.md v2.2)

**Success Criteria:**
- Can load all 7 YAML files
- Decimal values parsed correctly (not converted to float)
- Validation catches invalid configs (e.g., negative Kelly fraction)
- Config accessible throughout app: `from config import config`

**Implementation:**
```python
import yaml
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict
from pydantic import BaseModel, validator

# Register Decimal constructor for YAML
def decimal_constructor(loader, node):
    value = loader.construct_scalar(node)
    return Decimal(value)

yaml.add_constructor('!decimal', decimal_constructor)

class TradingConfig(BaseModel):
    """Pydantic model for trading.yaml validation."""
    min_ev_threshold: Decimal
    max_position_size: Decimal
    max_total_exposure: Decimal

    @validator('min_ev_threshold')
    def validate_min_ev(cls, v):
        if v < 0 or v > 1:
            raise ValueError("min_ev_threshold must be between 0 and 1")
        return v

    @validator('max_position_size', 'max_total_exposure')
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Must be positive")
        return v

class ConfigLoader:
    """Load and validate YAML configuration files."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.configs = {}

    def load_all(self) -> Dict[str, Any]:
        """Load all YAML config files."""
        yaml_files = [
            'trading.yaml',
            'trade_strategies.yaml',
            'position_management.yaml',
            'probability_models.yaml',
            'markets.yaml',
            'data_sources.yaml',
            'system.yaml'
        ]

        for filename in yaml_files:
            file_path = self.config_dir / filename
            with open(file_path, 'r') as f:
                self.configs[filename.replace('.yaml', '')] = yaml.safe_load(f)

        return self.configs

    def get(self, config_name: str) -> Dict[str, Any]:
        """Get specific config by name."""
        if config_name not in self.configs:
            self.load_all()
        return self.configs.get(config_name, {})

# Global config instance
config = ConfigLoader()
```

**Testing:**
- [ ] All 7 YAML files load without errors
- [ ] Decimal values remain Decimal (not converted to float)
- [ ] Invalid configs rejected (e.g., min_ev_threshold=1.5)
- [ ] Can access config globally: `config.get('trading')['min_ev_threshold']`

**Risks:**
- ⚠️ YAML parsing converts Decimal to float (use `!decimal` tag)
- ⚠️ Typos in YAML keys (use Pydantic validation)

**Time Breakdown:**
- YAML file creation: 1 hour
- Loader implementation: 1.5 hours
- Testing: 0.5 hours

---

#### [B2] Environment Variable Loading (1 hour)
**Priority:** 🔴 Critical
**Depends on:** None

**Deliverables:**
- `.env` file (from `.env.template`)
- `config/env.py` - Environment variable validation

**Success Criteria:**
- `.env` loaded at app startup
- All required variables validated (fail fast if missing)
- Sensitive values (API keys) never logged

**Implementation:**
```python
import os
from dotenv import load_dotenv
from typing import Optional

# Load .env at module import (runs once)
load_dotenv()

class Environment:
    """Validated environment variables."""

    @staticmethod
    def get_required(key: str) -> str:
        """Get required env var, raise if missing."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value

    @staticmethod
    def get_optional(key: str, default: Optional[str] = None) -> Optional[str]:
        """Get optional env var with default."""
        return os.getenv(key, default)

    # Database
    DB_HOST: str = get_required.__func__("DB_HOST")
    DB_PORT: int = int(get_optional.__func__("DB_PORT", "5432"))
    DB_NAME: str = get_required.__func__("DB_NAME")
    DB_USER: str = get_required.__func__("DB_USER")
    DB_PASSWORD: str = get_required.__func__("DB_PASSWORD")

    # Kalshi API
    KALSHI_API_KEY: str = get_required.__func__("KALSHI_API_KEY")
    KALSHI_PRIVATE_KEY_PATH: str = get_required.__func__("KALSHI_PRIVATE_KEY_PATH")

    # Trading
    TRADING_ENV: str = get_optional.__func__("TRADING_ENV", "PROD")

    @classmethod
    def validate_all(cls):
        """Validate all required env vars are set."""
        required = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'KALSHI_API_KEY']
        missing = [key for key in required if not os.getenv(key)]

        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")

        print("✅ All environment variables validated")

# Validate on import
Environment.validate_all()
```

**Testing:**
- [ ] Valid .env loads successfully
- [ ] Missing required var raises ValueError
- [ ] Optional vars use defaults

**Time Breakdown:**
- Implementation: 0.5 hours
- Testing: 0.5 hours

---

#### [B3] Database Configuration Overrides (2 hours)
**Priority:** 🟡 Important
**Depends on:** [A3], [B1]

**Deliverables:**
- `config/db_config.py` - Database-backed config overrides
- `config_overrides` table in database

**Success Criteria:**
- Can override YAML config with database values
- Precedence: Database > YAML > Defaults
- Config changes take effect without restart

**Implementation:**
```python
from sqlalchemy import Column, String, Text
from database.models import Base
from decimal import Decimal
import json

class ConfigOverride(Base):
    __tablename__ = 'config_overrides'

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)  # JSON string
    updated_by = Column(String(50))
    updated_at = Column(DateTime, default=datetime.utcnow)

def get_config_with_overrides(config_name: str) -> dict:
    """Get config with database overrides applied."""
    from config.config_loader import config
    from database.connection import SessionLocal

    # Start with YAML config
    base_config = config.get(config_name)

    # Apply database overrides
    db = SessionLocal()
    overrides = db.query(ConfigOverride).filter(
        ConfigOverride.key.startswith(f"{config_name}.")
    ).all()

    for override in overrides:
        # Parse JSON value
        value = json.loads(override.value)

        # Apply to config (supports nested keys: "trading.min_ev_threshold")
        keys = override.key.split('.')
        current = base_config
        for key in keys[1:-1]:  # Navigate to parent
            current = current[key]
        current[keys[-1]] = Decimal(value) if isinstance(value, (int, float, str)) else value

    db.close()
    return base_config
```

**Testing:**
- [ ] YAML config loads correctly
- [ ] Database override takes precedence
- [ ] Nested key overrides work (e.g., "trading.min_ev_threshold")

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

#### [B4] Configuration Validation (2 hours)
**Priority:** 🟡 Important
**Depends on:** [B1], [B3]

**Deliverables:**
- `config/validators.py` - Config validation functions

**Success Criteria:**
- Invalid configs rejected at startup (fail fast)
- Helpful error messages (e.g., "min_ev_threshold must be between 0 and 1")
- Validates cross-config constraints (e.g., max_position < max_exposure)

**Implementation:**
```python
from decimal import Decimal
from typing import Dict, List

def validate_trading_config(config: Dict) -> List[str]:
    """Validate trading.yaml config."""
    errors = []

    # Check min_ev_threshold
    if not (0 < config['min_ev_threshold'] < 1):
        errors.append("min_ev_threshold must be between 0 and 1")

    # Check max_position_size vs max_total_exposure
    if config['max_position_size'] > config['max_total_exposure']:
        errors.append("max_position_size cannot exceed max_total_exposure")

    # Check Kelly fractions
    for sport in ['nfl', 'nba', 'tennis']:
        key = f'kelly_fraction_{sport}'
        if key in config:
            if not (0 < config[key] <= 1):
                errors.append(f"{key} must be between 0 and 1")

    return errors

def validate_all_configs() -> bool:
    """Validate all config files."""
    from config.config_loader import config

    all_errors = []

    # Validate each config
    trading_errors = validate_trading_config(config.get('trading'))
    all_errors.extend(trading_errors)

    # Add more validators for other configs...

    if all_errors:
        print("❌ Configuration validation failed:")
        for error in all_errors:
            print(f"  - {error}")
        return False

    print("✅ All configurations valid")
    return True
```

**Testing:**
- [ ] Valid config passes validation
- [ ] Invalid min_ev_threshold rejected
- [ ] Cross-config validation works

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

### Category C: Logging Infrastructure (6 hours)

#### [C1] Structured Logging Setup (2 hours)
**Priority:** 🔴 Critical
**Depends on:** [A1] (for database logging)

**Deliverables:**
- `utils/logger.py` - Structured logger with file + database output

**Success Criteria:**
- All logs output as JSON (structured)
- Logs written to file: `logs/precog_YYYY-MM-DD.log`
- Critical logs also written to database
- Context binding works (request_id, user_id persist across logs)

**Implementation:**
```python
import structlog
from datetime import datetime
from pathlib import Path

def setup_logging():
    """Configure structlog for JSON logging."""

    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()

# Global logger instance
logger = setup_logging()

# Usage example:
# logger.info("order_placed", ticker="NFL-YES", quantity=10, price=Decimal("0.45"))
# Output: {"event": "order_placed", "ticker": "NFL-YES", "quantity": 10, "price": "0.45", "timestamp": "2025-10-15T12:00:00Z"}
```

**Testing:**
- [ ] Logs output as valid JSON
- [ ] File logging works (creates daily log files)
- [ ] Context binding persists across logs
- [ ] Decimal values logged as strings (not float)

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

#### [C2] Database Log Storage (2 hours)
**Priority:** 🟡 Important
**Depends on:** [A3], [C1]

**Deliverables:**
- `logs` table in database
- `utils/db_logger.py` - Database log handler

**Success Criteria:**
- Critical logs (ERROR, WARNING) written to database
- Can query logs: `SELECT * FROM logs WHERE level='ERROR' AND timestamp > '2025-10-15'`
- Log storage doesn't block application (async writes)

**Implementation:**
```python
from sqlalchemy import Column, Integer, String, Text, DateTime
from database.models import Base
from datetime import datetime

class Log(Base):
    __tablename__ = 'logs'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(10))  # DEBUG, INFO, WARNING, ERROR
    logger_name = Column(String(100))
    message = Column(Text)
    context = Column(Text)  # JSON string of additional context

def log_to_database(level: str, message: str, context: dict):
    """Write log to database (for ERROR/WARNING only)."""
    if level not in ['ERROR', 'WARNING']:
        return  # Only store critical logs

    from database.connection import SessionLocal
    import json

    db = SessionLocal()
    log_entry = Log(
        level=level,
        logger_name="precog",
        message=message,
        context=json.dumps(context)
    )
    db.add(log_entry)
    db.commit()
    db.close()
```

**Testing:**
- [ ] ERROR logs written to database
- [ ] INFO logs NOT written to database (file only)
- [ ] Can query logs by level, timestamp

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

#### [C3] Log Rotation & Cleanup (2 hours)
**Priority:** 🟢 Nice to have
**Depends on:** [C1]

**Deliverables:**
- Log rotation policy (daily, keep 30 days)
- `scripts/cleanup_logs.py` - Delete old logs

**Success Criteria:**
- Logs rotate daily (new file each day)
- Old logs deleted after 30 days
- Compressed logs archived (optional)

**Implementation:**
```python
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_old_logs(max_age_days: int = 30):
    """Delete log files older than max_age_days."""
    logs_dir = Path("logs")
    cutoff_date = datetime.now() - timedelta(days=max_age_days)

    deleted_count = 0
    for log_file in logs_dir.glob("precog_*.log"):
        # Extract date from filename: precog_2025-10-15.log
        file_date_str = log_file.stem.split('_')[1]
        file_date = datetime.strptime(file_date_str, "%Y-%m-%d")

        if file_date < cutoff_date:
            log_file.unlink()
            deleted_count += 1

    print(f"✅ Deleted {deleted_count} old log files")

if __name__ == "__main__":
    cleanup_old_logs()
```

**Testing:**
- [ ] Creates log file with today's date
- [ ] Cleanup script deletes old files
- [ ] Recent files preserved

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

### Category D: Kalshi API Client (20 hours)

#### [D1] RSA-PSS Authentication (4 hours)
**Priority:** 🔴 Critical - Most complex task
**Depends on:** [C1] (for logging)

**Deliverables:**
- `api/kalshi_auth.py` - RSA-PSS signature generation
- `api/kalshi_client.py` - Authenticated API client

**Success Criteria:**
- Can generate valid RSA-PSS signature
- Can authenticate with Kalshi demo API
- Token refresh works automatically (every 30 minutes)
- Authentication errors logged with details

**Implementation:**
```python
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from pathlib import Path

class KalshiAuth:
    """Handle RSA-PSS authentication for Kalshi API."""

    def __init__(self, api_key: str, private_key_path: str):
        self.api_key = api_key
        self.private_key = self._load_private_key(private_key_path)
        self.token = None
        self.token_expiry = 0

    def _load_private_key(self, path: str):
        """Load RSA private key from PEM file."""
        with open(path, 'rb') as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def _generate_signature(self, timestamp: int, method: str, path: str) -> str:
        """
        Generate RSA-PSS signature.
        Message format: timestamp + method + path (no delimiters)
        """
        message = f"{timestamp}{method}{path}".encode('utf-8')

        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )

        return base64.b64encode(signature).decode('utf-8')

    def get_headers(self, method: str, path: str) -> dict:
        """Get authenticated headers for API request."""
        timestamp = int(time.time() * 1000)  # Milliseconds
        signature = self._generate_signature(timestamp, method, path)

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": str(timestamp),
            "KALSHI-ACCESS-SIGNATURE": signature
        }

    def login(self) -> str:
        """
        Login to Kalshi API and get bearer token.
        Tokens expire after 30 minutes.
        """
        import requests

        path = "/trade-api/v2/login"
        headers = self.get_headers("POST", path)

        response = requests.post(
            f"https://demo-api.kalshi.co{path}",
            headers=headers,
            json={"email": "", "password": ""}  # Email/pass not needed with key auth
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data['token']
            self.token_expiry = time.time() + (30 * 60)  # 30 minutes
            return self.token
        else:
            raise Exception(f"Login failed: {response.status_code} {response.text}")

    def ensure_authenticated(self):
        """Ensure we have a valid token, refresh if needed."""
        if not self.token or time.time() > self.token_expiry:
            self.login()
```

**Testing:**
- [ ] Signature generation matches expected format
- [ ] Login succeeds with demo credentials
- [ ] Token refresh works automatically
- [ ] Authentication failures logged

**Risks:**
- ⚠️ RSA-PSS is complex (use `cryptography` library, not custom implementation)
- ⚠️ Token expiry handling (refresh before 30 min)
- ⚠️ Private key security (never commit to Git)

**Time Breakdown:**
- Research RSA-PSS: 1 hour
- Implementation: 2 hours
- Testing: 1 hour

---

#### [D2] Market Data Fetching (3 hours)
**Priority:** 🔴 Critical
**Depends on:** [D1]

**Deliverables:**
- `api/kalshi_client.py` - Methods: `get_markets()`, `get_market(ticker)`

**Success Criteria:**
- Can fetch list of markets
- Can fetch single market by ticker
- Prices parsed as Decimal (never float)
- Pagination handled (cursor-based)

**Implementation:**
```python
import requests
from decimal import Decimal
from typing import List, Dict, Optional

class KalshiClient:
    """Kalshi API client."""

    BASE_URL = "https://demo-api.kalshi.co"

    def __init__(self, auth: KalshiAuth):
        self.auth = auth

    def get_markets(
        self,
        status: str = "open",
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch markets from Kalshi API.

        Returns list of markets with DECIMAL prices.
        """
        self.auth.ensure_authenticated()

        params = {
            "status": status,
            "limit": limit
        }
        if cursor:
            params["cursor"] = cursor

        response = requests.get(
            f"{self.BASE_URL}/trade-api/v2/markets",
            headers={"Authorization": f"Bearer {self.auth.token}"},
            params=params
        )

        if response.status_code == 200:
            data = response.json()

            # ✅ CRITICAL: Parse prices as Decimal
            for market in data['markets']:
                market['yes_bid'] = Decimal(market['yes_bid_dollars'])
                market['yes_ask'] = Decimal(market['yes_ask_dollars'])
                market['no_bid'] = Decimal(market['no_bid_dollars'])
                market['no_ask'] = Decimal(market['no_ask_dollars'])

                # Remove _dollars fields (redundant)
                del market['yes_bid_dollars']
                del market['yes_ask_dollars']
                del market['no_bid_dollars']
                del market['no_ask_dollars']

            return data['markets']
        else:
            raise Exception(f"Failed to fetch markets: {response.status_code}")

    def get_market(self, ticker: str) -> Dict:
        """Fetch single market by ticker."""
        self.auth.ensure_authenticated()

        response = requests.get(
            f"{self.BASE_URL}/trade-api/v2/markets/{ticker}",
            headers={"Authorization": f"Bearer {self.auth.token}"}
        )

        if response.status_code == 200:
            market = response.json()['market']

            # Parse prices as Decimal
            market['yes_bid'] = Decimal(market['yes_bid_dollars'])
            market['yes_ask'] = Decimal(market['yes_ask_dollars'])

            return market
        else:
            raise Exception(f"Failed to fetch market: {response.status_code}")
```

**Testing:**
- [ ] Fetch markets returns list
- [ ] Prices are Decimal type (not float)
- [ ] Pagination works (fetch next page with cursor)
- [ ] Single market fetch works

**Time Breakdown:**
- Implementation: 2 hours
- Testing: 1 hour

---

#### [D3] Error Handling & Retry Logic (3 hours)
**Priority:** 🔴 Critical
**Depends on:** [D1], [D2]

**Deliverables:**
- Retry logic with exponential backoff
- Error handling for: network failures, rate limits, auth errors

**Success Criteria:**
- Transient errors (500, 503) retried automatically
- Rate limit errors (429) wait and retry
- Auth errors (401) trigger re-login
- Non-retryable errors (400, 404) fail immediately

**Implementation:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

class RetryableError(Exception):
    """Exception for errors that should be retried."""
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RetryableError)
)
def api_call_with_retry(method: str, url: str, **kwargs):
    """Make API call with automatic retry on transient errors."""
    response = requests.request(method, url, **kwargs)

    # Retryable errors
    if response.status_code in [429, 500, 502, 503, 504]:
        raise RetryableError(f"Transient error: {response.status_code}")

    # Auth error - re-login
    if response.status_code == 401:
        # Re-authenticate and retry
        raise RetryableError("Authentication expired")

    # Non-retryable errors
    if response.status_code >= 400:
        raise Exception(f"API error: {response.status_code} {response.text}")

    return response
```

**Testing:**
- [ ] 500 error retries 3 times
- [ ] 429 (rate limit) waits and retries
- [ ] 401 triggers re-authentication
- [ ] 404 fails immediately (no retry)

**Time Breakdown:**
- Implementation: 2 hours
- Testing: 1 hour

---

#### [D4] Market Data Storage (3 hours)
**Priority:** 🔴 Critical
**Depends on:** [A3], [D2]

**Deliverables:**
- `api/data_pipeline.py` - Fetch markets → store in database

**Success Criteria:**
- Fetched markets stored with SCD Type 2 versioning
- Price changes trigger new version (old record closed)
- No price data loss (all versions preserved)

**Implementation:**
```python
from api.kalshi_client import KalshiClient
from database.crud_operations import update_market_with_versioning, create_market

def sync_markets_to_database(client: KalshiClient, db_session):
    """Fetch markets from API and sync to database."""
    markets = client.get_markets(status="open")

    for market in markets:
        # Check if market exists
        existing = db_session.query(Market).filter(
            Market.ticker == market['ticker'],
            Market.RowCurrentInd == 1
        ).first()

        if existing:
            # Check if prices changed
            if (existing.yes_bid != market['yes_bid'] or
                existing.yes_ask != market['yes_ask']):
                # Update with versioning
                update_market_with_versioning(
                    db_session,
                    market['ticker'],
                    market['yes_bid'],
                    market['yes_ask']
                )
        else:
            # Create new market
            create_market(
                db_session,
                market['ticker'],
                market['yes_bid'],
                market['yes_ask'],
                market['event_ticker']
            )
```

**Testing:**
- [ ] New markets inserted
- [ ] Price changes create new version
- [ ] Old versions preserved (RowCurrentInd=0)
- [ ] No data loss

**Time Breakdown:**
- Implementation: 2 hours
- Testing: 1 hour

---

#### [D5] Rate Limiting & Throttling (2 hours)
**Priority:** 🟡 Important
**Depends on:** [D2]

**Deliverables:**
- Rate limit tracking (stay under Kalshi limits)
- Request throttling to avoid 429 errors

**Success Criteria:**
- Never exceed Kalshi rate limits
- Requests spread out over time (not all at once)
- Rate limit headers parsed and respected

**Implementation:**
```python
import time
from collections import deque

class RateLimiter:
    """Track API calls and enforce rate limits."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()  # Timestamps of recent requests

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()

        # Remove requests outside window
        while self.requests and self.requests[0] < now - self.window_seconds:
            self.requests.popleft()

        # If at limit, wait
        if len(self.requests) >= self.max_requests:
            sleep_time = self.requests[0] + self.window_seconds - now
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Record this request
        self.requests.append(time.time())

# Global rate limiter
rate_limiter = RateLimiter(max_requests=60, window_seconds=60)

def api_call_with_rate_limit(method: str, url: str, **kwargs):
    """Make API call with rate limiting."""
    rate_limiter.wait_if_needed()
    return requests.request(method, url, **kwargs)
```

**Testing:**
- [ ] 61st request in 60 seconds waits
- [ ] Requests spread out correctly

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

#### [D6] WebSocket Connection (Phase 1: Basic Setup) (3 hours)
**Priority:** 🟢 Nice to have (full implementation in Phase 2)
**Depends on:** [D1]

**Deliverables:**
- `api/websocket_client.py` - Basic WebSocket connection
- Can subscribe to market updates (implementation deferred to Phase 2)

**Success Criteria:**
- Can establish WebSocket connection
- Can subscribe to market ticker
- Receives heartbeat messages
- Full implementation in Phase 2

**Implementation:**
```python
import asyncio
import websockets
import json

async def connect_to_kalshi_websocket(token: str):
    """
    Basic WebSocket connection (full implementation in Phase 2).
    Phase 1: Just verify connection works.
    """
    uri = "wss://demo-api.kalshi.co/trade-api/ws/v2"

    async with websockets.connect(uri) as websocket:
        # Authenticate
        await websocket.send(json.dumps({
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["ticker"],
                "market_tickers": ["MARKET-YES"]
            }
        }))

        # Receive first message (proof of concept)
        message = await websocket.recv()
        print(f"Received: {message}")

# Test connection
if __name__ == "__main__":
    asyncio.run(connect_to_kalshi_websocket("token_here"))
```

**Testing:**
- [ ] Connection establishes successfully
- [ ] Heartbeat messages received
- [ ] Subscription works (defer full processing to Phase 2)

**Time Breakdown:**
- Research: 1 hour
- Basic implementation: 1.5 hours
- Testing: 0.5 hours

---

#### [D7] API Client Documentation (2 hours)
**Priority:** 🟢 Nice to have
**Depends on:** [D1], [D2], [D3], [D4]

**Deliverables:**
- `docs/API_CLIENT_USAGE.md` - Usage guide for KalshiClient

**Success Criteria:**
- Code examples for common operations
- Error handling patterns documented
- Rate limiting explained

**Implementation:**
Create comprehensive usage guide with examples:

```markdown
# Kalshi API Client Usage Guide

## Basic Usage

```python
from api.kalshi_auth import KalshiAuth
from api.kalshi_client import KalshiClient

# Initialize
auth = KalshiAuth(
    api_key=os.getenv("KALSHI_API_KEY"),
    private_key_path=os.getenv("KALSHI_PRIVATE_KEY_PATH")
)
client = KalshiClient(auth)

# Fetch markets
markets = client.get_markets(status="open", limit=100)

# Fetch single market
market = client.get_market("MARKET-YES")
```

## Error Handling

All API errors raise exceptions. Use try/except:

```python
try:
    market = client.get_market("INVALID")
except Exception as e:
    logger.error("Failed to fetch market", error=str(e))
```
```

**Time Breakdown:**
- Writing documentation: 2 hours

---

### Category E: CLI Framework (8 hours)

#### [E1] Click CLI Setup (2 hours)
**Priority:** 🟡 Important
**Depends on:** [A6], [B1], [C1]

**Deliverables:**
- `main.py` - Click CLI entry point
- Commands: `precog --help`, `precog version`

**Success Criteria:**
- CLI installed and accessible: `precog --help`
- Version command works: `precog version`
- Subcommands registered

**Implementation:**
```python
import click
from pathlib import Path

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Precog - Automated Prediction Market Trading System"""
    pass

@cli.command()
def version():
    """Show version information."""
    click.echo("Precog v1.0.0 (Phase 1)")
    click.echo("Database: PostgreSQL 15")
    click.echo("Python: 3.12+")

if __name__ == "__main__":
    cli()
```

**Install as CLI:**
```python
# setup.py
from setuptools import setup

setup(
    name="precog",
    version="1.0.0",
    py_modules=["main"],
    install_requires=["click"],
    entry_points={
        "console_scripts": [
            "precog=main:cli"
        ]
    }
)
```

```bash
# Install in editable mode
pip install -e .

# Test
precog --help
precog version
```

**Testing:**
- [ ] `precog --help` works
- [ ] `precog version` shows correct info

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

#### [E2] Database CLI Commands (3 hours)
**Priority:** 🔴 Critical
**Depends on:** [A6], [E1]

**Deliverables:**
- Commands: `precog db-init`, `precog db-health`, `precog db-seed`

**Success Criteria:**
- `precog db-init` creates all tables
- `precog db-health` runs health checks
- `precog db-seed` populates test data

**Implementation:**
```python
@cli.group()
def db():
    """Database management commands."""
    pass

@db.command("init")
def db_init():
    """Initialize database schema."""
    from database.connection import engine
    from database.models import Base

    click.echo("Creating database tables...")
    Base.metadata.create_all(engine)
    click.echo("✅ Database initialized successfully")

@db.command("health")
def db_health():
    """Check database health."""
    from database.health import run_all_health_checks

    click.echo("Running health checks...")
    results = run_all_health_checks()

    if results["overall_status"] == "ok":
        click.echo("✅ All health checks passed")
    else:
        click.echo("❌ Health check failed:")
        for check_name, result in results["checks"].items():
            click.echo(f"  {check_name}: {result['message']}")

@db.command("seed")
def db_seed():
    """Populate database with test data."""
    from scripts.seed_database import seed_markets

    click.echo("Seeding database...")
    seed_markets()
    click.echo("✅ Database seeded successfully")
```

**Testing:**
- [ ] `precog db-init` creates tables
- [ ] `precog db-health` reports status correctly
- [ ] `precog db-seed` populates data

**Time Breakdown:**
- Implementation: 2 hours
- Testing: 1 hour

---

#### [E3] API CLI Commands (2 hours)
**Priority:** 🟡 Important
**Depends on:** [D2], [E1]

**Deliverables:**
- Commands: `precog api-test`, `precog fetch-markets`

**Success Criteria:**
- `precog api-test` verifies API connectivity
- `precog fetch-markets` fetches and displays markets

**Implementation:**
```python
@cli.group()
def api():
    """Kalshi API commands."""
    pass

@api.command("test")
def api_test():
    """Test Kalshi API connectivity."""
    from api.kalshi_auth import KalshiAuth
    from api.kalshi_client import KalshiClient
    import os

    click.echo("Testing Kalshi API connection...")

    auth = KalshiAuth(
        api_key=os.getenv("KALSHI_API_KEY"),
        private_key_path=os.getenv("KALSHI_PRIVATE_KEY_PATH")
    )

    try:
        auth.login()
        click.echo("✅ Authentication successful")

        client = KalshiClient(auth)
        markets = client.get_markets(limit=1)
        click.echo(f"✅ Fetched {len(markets)} market")

    except Exception as e:
        click.echo(f"❌ API test failed: {str(e)}")

@api.command("fetch-markets")
@click.option("--limit", default=10, help="Number of markets to fetch")
def fetch_markets(limit):
    """Fetch and display markets."""
    from api.kalshi_client import KalshiClient
    from api.kalshi_auth import KalshiAuth
    import os

    auth = KalshiAuth(
        api_key=os.getenv("KALSHI_API_KEY"),
        private_key_path=os.getenv("KALSHI_PRIVATE_KEY_PATH")
    )
    client = KalshiClient(auth)

    markets = client.get_markets(limit=limit)

    for market in markets:
        click.echo(f"{market['ticker']}: Bid={market['yes_bid']}, Ask={market['yes_ask']}")
```

**Testing:**
- [ ] `precog api-test` passes with valid credentials
- [ ] `precog fetch-markets` displays markets

**Time Breakdown:**
- Implementation: 1 hour
- Testing: 1 hour

---

#### [E4] Configuration CLI Commands (1 hour)
**Priority:** 🟢 Nice to have
**Depends on:** [B1], [E1]

**Deliverables:**
- Commands: `precog config-show`, `precog config-validate`

**Success Criteria:**
- `precog config-show` displays current config
- `precog config-validate` checks config validity

**Implementation:**
```python
@cli.group()
def config():
    """Configuration management commands."""
    pass

@config.command("show")
@click.argument("config_name")
def config_show(config_name):
    """Show configuration."""
    from config.config_loader import config
    import json

    cfg = config.get(config_name)
    click.echo(json.dumps(cfg, indent=2, default=str))

@config.command("validate")
def config_validate():
    """Validate all configuration files."""
    from config.validators import validate_all_configs

    if validate_all_configs():
        click.echo("✅ All configurations valid")
    else:
        click.echo("❌ Configuration validation failed")
```

**Testing:**
- [ ] `precog config-show trading` displays config
- [ ] `precog config-validate` checks validity

**Time Breakdown:**
- Implementation: 0.5 hours
- Testing: 0.5 hours

---

### Category F: Testing & Documentation (14 hours)

#### [F1] Unit Tests (6 hours)
**Priority:** 🔴 Critical
**Depends on:** All previous tasks

**Deliverables:**
- `tests/test_database.py` - Database tests
- `tests/test_api_client.py` - API client tests
- `tests/test_config.py` - Config loader tests
- `tests/test_decimal_precision.py` - **Critical price tests**

**Success Criteria:**
- >80% code coverage
- All critical paths tested (DECIMAL handling, API auth, DB CRUD)
- Tests pass consistently

**Critical Test: Decimal Precision**
```python
import pytest
from decimal import Decimal
from database.crud_operations import create_market, get_current_market

def test_decimal_precision_preserved():
    """CRITICAL: Verify prices stored/retrieved with exact precision."""
    db = get_test_db_session()

    # Create market with sub-penny pricing
    ticker = "TEST-MARKET-YES"
    yes_bid = Decimal("0.4275")  # 42.75¢
    yes_ask = Decimal("0.4300")  # 43.00¢

    create_market(db, ticker, yes_bid, yes_ask, "TEST-EVENT")

    # Retrieve and verify
    market = get_current_market(db, ticker)

    # ✅ MUST pass: Exact precision preserved
    assert market.yes_bid == Decimal("0.4275")
    assert market.yes_ask == Decimal("0.4300")

    # ❌ MUST fail: No float conversion
    assert type(market.yes_bid) is Decimal
    assert type(market.yes_ask) is Decimal

    # ✅ Verify 4 decimal places
    assert str(market.yes_bid) == "0.4275"
    assert str(market.yes_ask) == "0.4300"

def test_no_float_arithmetic():
    """CRITICAL: Verify no float arithmetic used."""
    bid = Decimal("0.45")
    ask = Decimal("0.46")

    # ✅ CORRECT: Decimal arithmetic
    spread = ask - bid
    assert spread == Decimal("0.01")
    assert type(spread) is Decimal

    # ❌ This should NEVER happen in codebase:
    # bid_float = float(bid)  # NEVER DO THIS
    # ask_float = float(ask)
    # spread_float = ask_float - bid_float  # Rounding errors
```

**Testing:**
- [ ] All tests pass
- [ ] Coverage >80%
- [ ] No float types in price handling

**Time Breakdown:**
- Writing tests: 4 hours
- Debugging test failures: 2 hours

---

#### [F2] Integration Tests (4 hours)
**Priority:** 🟡 Important
**Depends on:** All previous tasks

**Deliverables:**
- `tests/test_integration.py` - End-to-end tests
- Test: API fetch → Database storage → Retrieval

**Success Criteria:**
- Full pipeline tested: API → DB → Query
- SCD Type 2 versioning tested
- Real API calls (or mocked if rate-limited)

**Implementation:**
```python
import pytest
from api.kalshi_client import KalshiClient
from api.data_pipeline import sync_markets_to_database

def test_full_pipeline():
    """Test complete pipeline: Fetch → Store → Retrieve."""
    # Setup
    client = get_test_client()
    db = get_test_db_session()

    # Fetch markets from API
    sync_markets_to_database(client, db)

    # Verify stored in database
    markets = db.query(Market).filter(Market.RowCurrentInd == 1).all()
    assert len(markets) > 0

    # Verify DECIMAL precision
    for market in markets:
        assert type(market.yes_bid) is Decimal
        assert type(market.yes_ask) is Decimal

def test_price_update_versioning():
    """Test SCD Type 2 versioning on price change."""
    # Create initial market
    create_market(db, "TEST-YES", Decimal("0.50"), Decimal("0.51"), "TEST")

    # Simulate price change
    update_market_with_versioning(db, "TEST-YES", Decimal("0.52"), Decimal("0.53"))

    # Verify old version closed
    old_version = db.query(Market).filter(
        Market.ticker == "TEST-YES",
        Market.RowCurrentInd == 0
    ).first()
    assert old_version is not None
    assert old_version.yes_bid == Decimal("0.50")

    # Verify new version current
    new_version = db.query(Market).filter(
        Market.ticker == "TEST-YES",
        Market.RowCurrentInd == 1
    ).first()
    assert new_version.yes_bid == Decimal("0.52")
```

**Testing:**
- [ ] Full pipeline test passes
- [ ] Versioning test passes

**Time Breakdown:**
- Writing tests: 2.5 hours
- Debugging: 1.5 hours

---

#### [F3] Code Quality Enforcement (2 hours)
**Priority:** 🟡 Important
**Depends on:** All code complete

**Deliverables:**
- Black formatting applied to all files
- Pylint score >9.0/10.0
- Mypy type checking passes

**Success Criteria:**
- All code formatted consistently
- No linting errors
- Type hints on all functions

**Implementation:**
```bash
# Format all code
black src/ tests/

# Check linting
pylint src/ --fail-under=9.0

# Type checking
mypy src/

# Run all checks
./scripts/quality_checks.sh
```

**Time Breakdown:**
- Formatting: 0.5 hours
- Fixing linting issues: 1 hour
- Adding type hints: 0.5 hours

---

#### [F4] Documentation & Deployment Guide (2 hours)
**Priority:** 🟡 Important
**Depends on:** All tasks complete

**Deliverables:**
- `docs/DEPLOYMENT_GUIDE_V1.0.md` - Local setup guide
- `docs/TESTING_GUIDE.md` - How to run tests
- `README.md` - Project overview

**Success Criteria:**
- New developer can set up environment in <2 hours following guide
- All CLI commands documented
- Testing procedures explained

**Time Breakdown:**
- Writing documentation: 2 hours

---

## Critical Path

**Critical path = longest dependency chain = 35 hours**

```
A1 (3h) → A2 (2h) → A3 (4h) → D1 (4h) → D2 (3h) → D3 (3h) → D4 (3h) → E2 (3h) → F1 (6h) → F2 (4h)
```

**Non-critical tasks can be done in parallel:**
- B1-B4 (Configuration) - 8 hours
- C1-C3 (Logging) - 6 hours
- A4-A6 (Database extras) - 7 hours
- E1, E3-E4 (CLI extras) - 5 hours

**Total: 72 hours (matches 6-week estimate)**

---

## Risk Mitigation

### High-Risk Tasks

| Task | Risk | Mitigation |
|------|------|------------|
| **[D1] RSA-PSS Auth** | Complex cryptography, hard to debug | Use `cryptography` library (battle-tested), follow Kalshi docs exactly, test with demo API first |
| **[A3] CRUD + Versioning** | SCD Type 2 complexity | Write extensive tests, manually verify old/new records in database |
| **[D4] Decimal Parsing** | Float conversion bugs | Use `KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md`, write tests that fail on float |
| **[F1] Test Coverage** | Hard to reach 80% | Focus on critical paths first (prices, auth), use `pytest-cov` to track progress |

### Blockers & Dependencies

| Blocker | Impact | Solution |
|---------|--------|----------|
| Kalshi API keys not obtained | Can't test D1-D7 | Get demo keys ASAP (kalshi.com/demo) |
| PostgreSQL not installed | Can't test A1-A6 | Follow `ENVIRONMENT_CHECKLIST_V1.1.md` Part 4 |
| Python packages missing | All tasks blocked | Run `pip install -r requirements.txt` |
| Database credentials wrong | A2-A6 blocked | Verify `.env` has correct DB_PASSWORD |

---

## Week-by-Week Milestones

### Week 1 (12 hours): Foundation
**Goal:** Database + Config + Logging working

**Tasks:**
- [x] A1: Database schema (3h)
- [x] A2: Connection pooling (2h)
- [x] A3: CRUD operations (4h)
- [x] B1: YAML loader (3h)

**Milestone:** Can create/read/update markets in database with DECIMAL precision

---

### Week 2 (12 hours): API Authentication
**Goal:** Can authenticate with Kalshi API

**Tasks:**
- [ ] D1: RSA-PSS authentication (4h)
- [ ] D2: Market data fetching (3h)
- [ ] C1: Structured logging (2h)
- [ ] B2: Environment variables (1h)
- [ ] A4: Alembic migrations (2h)

**Milestone:** Can fetch markets from Kalshi API, log operations

---

### Week 3 (12 hours): Data Pipeline
**Goal:** API → Database pipeline works

**Tasks:**
- [ ] D3: Error handling & retry (3h)
- [ ] D4: Market data storage (3h)
- [ ] D5: Rate limiting (2h)
- [ ] C2: Database logging (2h)
- [ ] A5: Database seeding (2h)

**Milestone:** Can fetch markets and store in database with versioning

---

### Week 4 (12 hours): CLI & Utilities
**Goal:** CLI commands working

**Tasks:**
- [ ] E1: Click CLI setup (2h)
- [ ] E2: Database CLI commands (3h)
- [ ] E3: API CLI commands (2h)
- [ ] E4: Config CLI commands (1h)
- [ ] B3: DB config overrides (2h)
- [ ] A6: Health checks (2h)

**Milestone:** `precog` CLI installed, all commands working

---

### Week 5 (12 hours): Testing
**Goal:** >80% test coverage

**Tasks:**
- [ ] F1: Unit tests (6h)
- [ ] F2: Integration tests (4h)
- [ ] B4: Config validation (2h)

**Milestone:** All tests passing, coverage >80%

---

### Week 6 (12 hours): Polish & Documentation
**Goal:** Phase 1 complete, ready for Phase 2

**Tasks:**
- [ ] F3: Code quality (2h)
- [ ] F4: Documentation (2h)
- [ ] D6: WebSocket basic setup (3h)
- [ ] D7: API documentation (2h)
- [ ] C3: Log rotation (2h)
- [ ] Final review & bug fixes (1h)

**Milestone:** Phase 1 complete assessment passed

---

## Task Completion Checklist

Use this to track progress:

```
Database Foundation:
[ ] A1: Database schema (3h)
[ ] A2: Connection pooling (2h)
[ ] A3: CRUD operations (4h)
[ ] A4: Alembic migrations (3h)
[ ] A5: Database seeding (2h)
[ ] A6: Health checks (2h)

Configuration System:
[ ] B1: YAML loader (3h)
[ ] B2: Environment variables (1h)
[ ] B3: DB config overrides (2h)
[ ] B4: Config validation (2h)

Logging Infrastructure:
[ ] C1: Structured logging (2h)
[ ] C2: Database logging (2h)
[ ] C3: Log rotation (2h)

Kalshi API Client:
[ ] D1: RSA-PSS authentication (4h)
[ ] D2: Market data fetching (3h)
[ ] D3: Error handling & retry (3h)
[ ] D4: Market data storage (3h)
[ ] D5: Rate limiting (2h)
[ ] D6: WebSocket basic setup (3h)
[ ] D7: API documentation (2h)

CLI Framework:
[ ] E1: Click CLI setup (2h)
[ ] E2: Database CLI commands (3h)
[ ] E3: API CLI commands (2h)
[ ] E4: Config CLI commands (1h)

Testing & Documentation:
[ ] F1: Unit tests (6h)
[ ] F2: Integration tests (4h)
[ ] F3: Code quality (2h)
[ ] F4: Documentation (2h)

Total: [ ] / 28 tasks complete (72 hours)
```

---

## Daily Development Routine (Recommended)

**Start of each session:**
1. Git pull latest changes
2. Activate virtual environment
3. Review task list, pick next task
4. Check dependencies (all upstream tasks complete?)

**During development:**
5. Write code for task
6. Write tests as you go (at least for critical functions)
7. Run tests frequently: `pytest tests/`
8. Format code: `black src/`
9. Commit frequently: `git add . && git commit -m "Complete task X"`

**End of each session:**
10. Run full test suite: `pytest --cov=src`
11. Check coverage: `pytest --cov=src --cov-report=html`
12. Update task checklist (mark tasks complete)
13. Git push: `git push origin main`

---

## Success Indicators

**You're on track if:**
- ✅ Week 1: Can create/query markets in database
- ✅ Week 2: Can authenticate with Kalshi API
- ✅ Week 3: API → DB pipeline working
- ✅ Week 4: CLI commands working
- ✅ Week 5: Tests passing, coverage >75%
- ✅ Week 6: All tasks complete, ready for Phase 2

**Warning signs:**
- ⚠️ Float types appearing in price handling (check immediately)
- ⚠️ Authentication failing repeatedly (verify keys, signature format)
- ⚠️ Test coverage <70% by Week 5 (dedicate more time to testing)
- ⚠️ Tasks taking 2x estimated time (may need to adjust scope or ask for help)

---

## Related Documents

- **PROJECT_STATUS.md**: Overall project status
- **MASTER_REQUIREMENTS.md** v2.2: Requirements this phase fulfills
- **API_INTEGRATION_GUIDE.md** v2.1: Kalshi API technical details
- **DATABASE_SCHEMA_SUMMARY.md** v1.2: Complete schema reference (includes `probability_matrices` table)
- **CONFIGURATION_GUIDE.md** v2.2: YAML file specifications (includes `probability_models.yaml`)
- **KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md**: **CRITICAL - Read before coding**
- **REQUIREMENTS_AND_DEPENDENCIES_V1.0.md**: Python package guide
- **ENVIRONMENT_CHECKLIST_V1.1.md**: Setup instructions

---

**Ready to start? Pick task [A1] and let's build!**

---

**END OF PHASE 1 TASK PLAN**
