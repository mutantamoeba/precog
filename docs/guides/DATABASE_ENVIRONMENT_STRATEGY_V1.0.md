# Database Environment Strategy

**Version:** 1.0
**Date:** 2025-11-29
**Status:** ✅ Active
**Purpose:** Define database environment usage, migration workflow, and test isolation
**Related:** ADR-008 (PostgreSQL Connection Strategy), REQ-DB-002 (Connection Pooling)

---

## Overview

Precog uses **4 PostgreSQL database environments** to ensure safe development, testing, and deployment:

| Environment | Database Name | Purpose | Risk Level |
|-------------|---------------|---------|------------|
| **dev** | `precog_dev` | Local development, experimentation | 🟢 Low |
| **test** | `precog_test` | Automated testing (CI/CD, pre-push) | 🟢 Low |
| **staging** | `precog_staging` | Pre-production validation, UAT | 🟡 Medium |
| **prod** | `precog_prod` | Live trading, real money | 🔴 Critical |

---

## 1. Environment Usage Guidelines

### When to Use Each Environment

```
Developer Workflow:
┌─────────────────────────────────────────────────────────────────┐
│  Local Development                                               │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐ │
│  │   dev   │ ───► │  test   │ ───► │ staging │ ───► │  prod   │ │
│  │ (local) │      │  (CI)   │      │  (UAT)  │      │ (live)  │ │
│  └─────────┘      └─────────┘      └─────────┘      └─────────┘ │
│       │                │                │                │       │
│  Write code       Run tests       Validate         Deploy        │
│  Debug            Pre-push        Integration      Go live        │
│  Experiment       PR checks       Stakeholder                    │
└─────────────────────────────────────────────────────────────────┘
```

### Environment Details

#### DEV Environment (`precog_dev`)
```bash
# .env.dev
DB_HOST=localhost
DB_PORT=5432
DB_NAME=precog_dev
DB_USER=precog_dev_user
DB_PASSWORD=<dev_password>
DB_POOL_MIN_CONN=2
DB_POOL_MAX_CONN=10
```

**Usage:**
- ✅ Local development and debugging
- ✅ Schema experimentation
- ✅ Manual testing
- ✅ Data exploration
- ❌ NOT for automated tests (use test)
- ❌ NOT for production data

**Who Uses:** Individual developers on their local machines

---

#### TEST Environment (`precog_test`)
```bash
# .env.test
DB_HOST=localhost  # or CI-provided host
DB_PORT=5432
DB_NAME=precog_test
DB_USER=precog_test_user
DB_PASSWORD=<test_password>
DB_POOL_MIN_CONN=2
DB_POOL_MAX_CONN=25
```

**Usage:**
- ✅ Pre-push hook tests
- ✅ CI/CD pipeline tests
- ✅ Integration tests
- ✅ Property-based tests
- ✅ Stress tests
- ❌ NOT for manual debugging (use dev)
- ❌ NOT for real data

**Who Uses:** CI/CD system, developers running pre-push

**Test Isolation Rules:**
1. Each test runs in a transaction that rolls back
2. `clean_test_data` fixture ensures clean slate
3. Tests must be idempotent (can run in any order)
4. No persistent state between tests

---

#### STAGING Environment (`precog_staging`)
```bash
# .env.staging
DB_HOST=staging.db.example.com
DB_PORT=5432
DB_NAME=precog_staging
DB_USER=precog_staging_user
DB_PASSWORD=<staging_password>
DB_POOL_MIN_CONN=5
DB_POOL_MAX_CONN=25
```

**Usage:**
- ✅ Pre-production validation
- ✅ User acceptance testing (UAT)
- ✅ Integration with staging APIs
- ✅ Performance benchmarking
- ✅ Migration dry-runs
- ❌ NOT for active development
- ❌ NOT for real money

**Who Uses:** QA team, stakeholders, release manager

---

#### PROD Environment (`precog_prod`)
```bash
# .env.prod (NEVER COMMIT!)
DB_HOST=prod.db.example.com
DB_PORT=5432
DB_NAME=precog_prod
DB_USER=precog_app_user
DB_PASSWORD=<prod_password>  # Use secrets manager in production
DB_POOL_MIN_CONN=10
DB_POOL_MAX_CONN=50
```

**Usage:**
- ✅ Live trading operations
- ✅ Real market data
- ✅ Real money positions
- ❌ NEVER for testing
- ❌ NEVER for development
- ❌ NEVER run DELETE without WHERE

**Who Uses:** Application only (no direct human access for routine operations)

**Production Safety Rules:**
1. Never connect directly from development machine
2. All changes through migrations only
3. No ad-hoc queries without approval
4. Audit logging enabled
5. Backups before any migration

---

## 2. Environment Selection Mechanism

### Current Implementation (connection.py)

The database connection is determined by environment variables:

```python
# src/precog/database/connection.py
database = database or os.getenv("DB_NAME", "precog_dev")
```

### Recommended Enhancement: Explicit Environment Selection

```python
# Add to connection.py
import os

def get_environment() -> str:
    """
    Determine current database environment.

    Priority:
    1. PRECOG_ENV environment variable (explicit)
    2. DB_NAME environment variable (implicit from name)
    3. Default to 'dev' (safe default)

    Returns:
        Environment name: 'dev', 'test', 'staging', or 'prod'
    """
    # Explicit environment selection
    env = os.getenv("PRECOG_ENV")
    if env:
        if env not in ("dev", "test", "staging", "prod"):
            raise ValueError(f"Invalid PRECOG_ENV: {env}")
        return env

    # Infer from database name
    db_name = os.getenv("DB_NAME", "precog_dev")
    if "test" in db_name:
        return "test"
    elif "staging" in db_name:
        return "staging"
    elif "prod" in db_name:
        return "prod"
    else:
        return "dev"


def require_environment(required: str) -> None:
    """
    Ensure we're running in the expected environment.

    Use this at the start of scripts that should only run in specific environments.

    Example:
        # In a migration script
        require_environment("staging")  # Fails if not staging
    """
    current = get_environment()
    if current != required:
        raise RuntimeError(
            f"This operation requires {required} environment, "
            f"but current environment is {current}"
        )
```

### Usage Examples

```bash
# Run tests against test database
PRECOG_ENV=test python -m pytest tests/

# Run migration against staging
PRECOG_ENV=staging python scripts/apply_migration.py

# Explicitly prevent accidental production access
PRECOG_ENV=dev python scripts/dangerous_script.py
```

---

## 3. Migration Workflow

### Migration Order (NEVER Skip!)

```
dev ──► test ──► staging ──► prod
  │       │         │          │
  │       │         │          └─ Production deployment
  │       │         └─ Final validation, stakeholder approval
  │       └─ CI/CD tests pass
  └─ Local development and testing
```

### Migration Checklist

#### Before Creating Migration
- [ ] Schema change documented in ADR
- [ ] Backwards compatibility considered
- [ ] Rollback script prepared
- [ ] Data migration plan (if needed)

#### DEV Environment
```bash
# 1. Create migration file
python scripts/create_migration.py "Add column to markets"

# 2. Apply to dev
PRECOG_ENV=dev python scripts/apply_migration.py

# 3. Test manually
psql -d precog_dev -c "SELECT * FROM markets LIMIT 5"

# 4. Run local tests
python -m pytest tests/integration/database/
```

#### TEST Environment (CI/CD)
```bash
# Automatically in CI pipeline
PRECOG_ENV=test python scripts/apply_migration.py
python -m pytest tests/
```

#### STAGING Environment
```bash
# 1. Notify team
echo "Applying migration to staging"

# 2. Backup staging (optional but recommended)
pg_dump precog_staging > backup_$(date +%Y%m%d).sql

# 3. Apply migration
PRECOG_ENV=staging python scripts/apply_migration.py

# 4. Validate
python scripts/validate_schema.py

# 5. Run staging tests
PRECOG_ENV=staging python -m pytest tests/e2e/
```

#### PROD Environment
```bash
# 1. Get approval (PR merged, stakeholder sign-off)

# 2. Schedule maintenance window (if needed)

# 3. Backup production
pg_dump precog_prod > backup_prod_$(date +%Y%m%d_%H%M%S).sql

# 4. Apply migration
PRECOG_ENV=prod python scripts/apply_migration.py

# 5. Validate immediately
python scripts/validate_schema.py

# 6. Monitor for errors
tail -f /var/log/precog/app.log
```

---

## 4. Test Isolation Strategy

### Fixture-Based Isolation

```python
# tests/conftest.py

@pytest.fixture(scope="session")
def db_pool():
    """
    Session-scoped database pool.

    Created once per test session (all tests share same pool).
    Ensures we're using test database.
    """
    # Force test environment
    os.environ["PRECOG_ENV"] = "test"
    os.environ["DB_NAME"] = "precog_test"

    initialize_pool()
    yield _connection_pool
    close_pool()


@pytest.fixture(scope="function")
def db_cursor(db_pool):
    """
    Function-scoped cursor with automatic rollback.

    Each test gets fresh cursor, changes rolled back after test.
    """
    conn = db_pool.getconn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    yield cursor

    conn.rollback()  # Undo any changes from this test
    cursor.close()
    db_pool.putconn(conn)


@pytest.fixture(scope="function")
def clean_test_data(db_cursor):
    """
    Ensure clean database state for each test.

    Truncates test tables before each test.
    """
    # Clean up tables in dependency order (children first)
    tables = [
        "trades",
        "positions",
        "market_history",
        "markets",
        "strategies",
        "models",
    ]

    for table in tables:
        db_cursor.execute(f"TRUNCATE TABLE {table} CASCADE")

    db_cursor.connection.commit()
    yield
    # Rollback handled by db_cursor fixture
```

### Parallel Test Safety

```python
# tests/conftest.py

@pytest.fixture(scope="function")
def unique_test_id():
    """
    Generate unique ID for test isolation in parallel runs.

    Use this to create unique test data that won't conflict
    with other parallel tests.
    """
    import uuid
    return str(uuid.uuid4())[:8]


# Usage in tests
def test_create_market(clean_test_data, unique_test_id):
    ticker = f"TEST-{unique_test_id}"  # Unique per test
    market = create_market(ticker=ticker, ...)
    assert market["ticker"] == ticker
```

---

## 5. Environment Configuration Files

### Directory Structure

```
precog-repo/
├── .env                    # Current environment (gitignored)
├── .env.template           # Template with placeholders (committed)
├── config/
│   ├── .env.dev.template   # Dev environment template
│   ├── .env.test.template  # Test environment template
│   └── .env.staging.template  # Staging template (no prod!)
```

### .env.template (Committed)

```bash
# Database Configuration
# Copy to .env and fill in values

PRECOG_ENV=dev  # dev, test, staging, prod

# Database Connection
DB_HOST=localhost
DB_PORT=5432
DB_NAME=precog_dev
DB_USER=<your_user>
DB_PASSWORD=<your_password>

# Connection Pool
DB_POOL_MIN_CONN=2
DB_POOL_MAX_CONN=10

# API Keys (if needed)
KALSHI_API_KEY=<your_key>
KALSHI_API_SECRET=<your_secret>
```

### Switching Environments

```bash
# Option 1: Copy environment file
cp config/.env.test.template .env
source .env

# Option 2: Set PRECOG_ENV directly
export PRECOG_ENV=test
python -m pytest tests/

# Option 3: Inline for single command
PRECOG_ENV=test python scripts/run_migration.py
```

---

## 6. Safety Guards

### Production Protection

```python
# src/precog/database/connection.py

def initialize_pool(...):
    """Initialize pool with production safety checks."""

    env = get_environment()

    # Production safety checks
    if env == "prod":
        # Require explicit confirmation
        if os.getenv("PRECOG_PROD_CONFIRMED") != "yes":
            raise RuntimeError(
                "Production database access requires "
                "PRECOG_PROD_CONFIRMED=yes environment variable"
            )

        # Log production access
        logger.warning("⚠️ PRODUCTION DATABASE ACCESS INITIATED")
        logger.warning(f"User: {os.getenv('USER', 'unknown')}")
        logger.warning(f"Host: {host}:{port}/{database}")

    # Continue with normal initialization...
```

### Dangerous Operation Warnings

```python
# src/precog/database/crud_operations.py

def delete_all_positions():
    """
    Delete all positions (DANGEROUS).

    Protected: Only allowed in dev/test environments.
    """
    env = get_environment()

    if env in ("staging", "prod"):
        raise RuntimeError(
            f"delete_all_positions() is not allowed in {env} environment. "
            "Use specific deletion with WHERE clause instead."
        )

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM positions")
        return cur.rowcount
```

---

## 7. Quick Reference

### Daily Development

```bash
# Start of day
source .env  # or: export $(cat .env | xargs)

# Verify environment
echo $PRECOG_ENV  # Should be 'dev'

# Run local tests
python -m pytest tests/unit/

# Full test suite (uses test DB)
PRECOG_ENV=test python -m pytest tests/
```

### Before Committing

```bash
# Pre-push will automatically use test environment
git push  # Triggers pre-push hook with all 8 test types
```

### Migration Day

```bash
# 1. Apply to staging first
PRECOG_ENV=staging python scripts/apply_migration.py

# 2. Validate staging
PRECOG_ENV=staging python scripts/validate_schema.py

# 3. Get approval, then prod
PRECOG_PROD_CONFIRMED=yes PRECOG_ENV=prod python scripts/apply_migration.py
```

---

## References

- **DATABASE_ENVIRONMENT_GUIDE_V1.0.md**: Data seeding, categories, cloud strategy, scheduling (companion guide)
- **ADR-008:** PostgreSQL Connection Strategy
- **REQ-DB-002:** Connection Pooling Requirements
- **docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md:** Schema documentation
- **docs/guides/POSTGRESQL_SETUP_GUIDE.md:** Initial setup instructions

---

**END OF DATABASE_ENVIRONMENT_STRATEGY_V1.0.md**
