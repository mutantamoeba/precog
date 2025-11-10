# Testing Strategy V2.0

**Document Type:** Foundation
**Status:** ✅ Active
**Version:** 2.0
**Created:** 2025-10-23
**Last Updated:** 2025-10-29
**Changes in V2.0:**
- **PHASE 0.6C:** Major expansion with implementation details
- Added Configuration section (pyproject.toml, ruff, mypy, pytest)
- Added Test Organization section (unit/integration/fixtures structure)
- Added Test Factories section (factory-boy patterns)
- Added Test Execution Scripts section (test_fast.sh, test_full.sh, validate_*.sh)
- Added Parallel Execution section (pytest-xdist)
- Added Debugging Tests section
- Added Future Enhancements section (Phase 0.7 CI/CD plans)
- Updated test structure to reflect new organization
- All V1.1 content preserved and enhanced

**Changes in V1.1:** Added error handling test section (Phase 1.5), updated test structure
**Owner:** Development Team
**Applies to:** All Phases (0.6c - 10)

---

## Executive Summary

This document defines the **comprehensive testing strategy** for the Precog trading system across all development phases. It covers both strategy (what/why) and implementation (how) for testing infrastructure.

**Key Requirements:**
- ✅ Minimum 80% code coverage
- ✅ All tests pass before merge/deploy
- ✅ Critical tests marked and monitored
- ✅ Automated testing in CI/CD pipeline (Phase 0.7)
- ✅ Test factories for consistent test data
- ✅ Organized test structure (unit/integration/fixtures)

---

## Table of Contents

1. [Testing Framework](#testing-framework)
2. [Configuration](#configuration) ⭐ NEW
3. [Test Organization](#test-organization) ⭐ NEW
4. [Test Categories](#test-categories)
5. [Test Factories](#test-factories) ⭐ NEW
6. [Test Fixtures](#test-fixtures)
7. [Coverage Requirements](#coverage-requirements)
8. [Running Tests](#running-tests)
9. [Test Execution Scripts](#test-execution-scripts) ⭐ NEW
10. [Parallel Execution](#parallel-execution) ⭐ NEW
11. [Critical Test Scenarios](#critical-test-scenarios)
12. [Debugging Tests](#debugging-tests) ⭐ NEW
13. [Best Practices](#best-practices)
14. [CI/CD Integration](#cicd-integration)
15. [Future Enhancements](#future-enhancements) ⭐ NEW

---

## Testing Framework

### Core Tools

**Test Runner:** pytest 8.4+
- **Why:** Industry standard, powerful fixtures, excellent plugin ecosystem
- **Config:** `pyproject.toml` (Phase 0.6c+)
- **Plugins:** pytest-cov, pytest-asyncio, pytest-mock, pytest-xdist, pytest-html

**Coverage Tool:** pytest-cov 5.1+
- **Why:** Integrated with pytest, supports HTML reports
- **Minimum:** 80% coverage across all modules
- **Reports:** `htmlcov/` (HTML), `coverage.xml` (CI/CD)

**Test Data:** factory-boy 3.3+ + faker 30.8+
- **Why:** Consistent, realistic test data generation
- **Location:** `tests/fixtures/factories.py`

**Code Quality:** ruff 0.8+ (formatter + linter) + mypy 1.12+ (type checker)
- **Why:** Fast, comprehensive, modern tooling
- **Integration:** Runs before tests in validate_all.sh

---

## Configuration

### pyproject.toml

All test configuration centralized in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"

addopts = [
    "-v",                             # Verbose output
    "--strict-markers",               # Enforce marker registration
    "--cov=.",                        # Coverage on all code
    "--cov-report=term-missing",      # Show missing lines
    "--cov-report=html:htmlcov",      # HTML coverage report
    "--cov-fail-under=80",            # FAIL if coverage < 80%
    "--html=test_results/latest/pytest_report.html",
]

markers = [
    "unit: Fast unit tests",
    "integration: Integration tests",
    "slow: Slow tests",
    "critical: Critical tests",
    "database: Tests requiring database",
    "api: Tests requiring API access",
]

[tool.coverage.run]
source = ["."]
omit = [
    "tests/*",
    ".venv/*",
    "scripts/*",
    "*/migrations/*",
]
branch = true  # Measure branch coverage

[tool.coverage.report]
precision = 2
show_missing = true
fail_under = 80.0
```

**Benefits:**
- Single source of truth for test configuration
- No separate pytest.ini file
- Integrated with other tools (ruff, mypy)

---

## Test Organization

### Directory Structure (Phase 0.6c+)

```
tests/
├── unit/                  # Fast unit tests (no external dependencies)
│   ├── __init__.py
│   ├── test_decimal_precision.py
│   ├── test_versioning.py
│   └── test_utilities.py
│
├── integration/           # Integration tests (database, APIs, files)
│   ├── __init__.py
│   ├── test_database_crud.py
│   ├── test_api_client.py
│   └── test_position_lifecycle.py
│
├── fixtures/              # Shared fixtures and test data factories
│   ├── __init__.py
│   ├── factories.py       # factory-boy test data factories
│   └── sample_data.py     # Static sample data (if needed)
│
├── conftest.py            # Pytest configuration and shared fixtures
└── README.md              # Quick testing guide
```

**Migration from Flat Structure:**

Old (Phase 0-1):
```
tests/
├── test_database_connection.py
├── test_crud_operations.py
├── test_config_loader.py
└── ...
```

New (Phase 0.6c+):
- Move unit tests → `tests/unit/`
- Move integration tests → `tests/integration/`
- Create `tests/fixtures/` for test data

**Why This Structure:**
- ✅ Clear separation of test types
- ✅ Easier to run fast tests during development
- ✅ Scales better as test suite grows
- ✅ Standard industry pattern

---

## Test Categories

### 1. Unit Tests

**Purpose:** Test individual functions in isolation
**Location:** `tests/unit/`
**Marker:** `@pytest.mark.unit`
**Speed:** Fast (<0.1s per test)

**Characteristics:**
- No database connections
- No file I/O (use temp directories)
- No network calls
- Pure function testing

**Example:**
```python
# tests/unit/test_decimal_precision.py
import pytest
from decimal import Decimal
from utils.decimal_utils import decimal_to_string

@pytest.mark.unit
def test_decimal_serializer():
    """Test Decimal to string conversion preserves precision."""
    result = decimal_to_string(Decimal('0.5200'))
    assert result == '0.5200'
    assert isinstance(result, str)

@pytest.mark.unit
def test_decimal_edge_cases():
    """Test Decimal serialization with edge case values."""
    assert decimal_to_string(Decimal('0.0001')) == '0.0001'
    assert decimal_to_string(Decimal('0.9999')) == '0.9999'
    assert decimal_to_string(Decimal('0.4275')) == '0.4275'
```

**Run unit tests only:**
```bash
pytest tests/unit/ -v
# OR
pytest -m unit
```

---

### 2. Integration Tests

**Purpose:** Test components working together
**Location:** `tests/integration/`
**Marker:** `@pytest.mark.integration`
**Speed:** Medium (0.1s - 2s per test)

**Characteristics:**
- Database interactions allowed
- File system access allowed
- Tests real connections
- Verifies integration points

**Example:**
```python
# tests/integration/test_database_crud.py
import pytest
from decimal import Decimal
from database.crud_operations import create_market, get_current_market
from tests.fixtures.factories import MarketDataFactory

@pytest.mark.integration
@pytest.mark.database
def test_create_and_retrieve_market(db_connection, clean_test_data):
    """Test full CRUD cycle for markets."""
    # Arrange
    market_data = MarketDataFactory(
        ticker='TEST-NFL-KC-BUF-YES',
        yes_bid=Decimal('0.7500')
    )

    # Act
    market_id = create_market(**market_data)
    retrieved_market = get_current_market('TEST-NFL-KC-BUF-YES')

    # Assert
    assert retrieved_market is not None
    assert retrieved_market['ticker'] == 'TEST-NFL-KC-BUF-YES'
    assert retrieved_market['yes_bid'] == Decimal('0.7500')
```

**Run integration tests only:**
```bash
pytest tests/integration/ -v
# OR
pytest -m integration
```

---

### 3. Critical Tests

**Purpose:** Must-pass tests for core functionality
**Marker:** `@pytest.mark.critical`
**Monitoring:** Failures trigger alerts

**Critical Areas:**
- ✅ Decimal precision (NEVER use float for money/prices)
- ✅ SCD Type 2 versioning (historical data integrity)
- ✅ Trade attribution (strategy_id, model_id tracking)
- ✅ SQL injection prevention (parameterized queries)
- ✅ Connection pooling (resource management)

**Example:**
```python
@pytest.mark.integration
@pytest.mark.critical
def test_decimal_precision_not_float(db_connection, clean_test_data):
    """
    CRITICAL: Verify prices are Decimal, NOT float.

    Float errors cause incorrect trade calculations.
    This test ensures DECIMAL(10,4) type preserved end-to-end.
    """
    from tests.fixtures.factories import MarketDataFactory

    market_data = MarketDataFactory()
    market_id = create_market(**market_data)
    market = get_current_market(market_data['ticker'])

    # CRITICAL: Must be Decimal, NOT float
    assert isinstance(market['yes_bid'], Decimal)
    assert isinstance(market['yes_ask'], Decimal)
    assert isinstance(market['no_bid'], Decimal)
    assert isinstance(market['no_ask'], Decimal)
```

**Run critical tests only:**
```bash
pytest -m critical
```

---

### 4. Slow Tests

**Purpose:** Long-running tests (performance, stress tests)
**Marker:** `@pytest.mark.slow`
**Usage:** Skip during development, run in CI

**Example:**
```python
@pytest.mark.slow
def test_connection_pool_under_load():
    """Test pool behavior under heavy concurrent load."""
    # Simulate 1000 concurrent connections...
    pass
```

**Skip slow tests:**
```bash
pytest -m "not slow"
```

---

## Test Factories

### Using factory-boy for Test Data

Test factories provide consistent, realistic test data:

**Location:** `tests/fixtures/factories.py`

**Available Factories:**
- `MarketDataFactory` - Market data (prices, volume, status)
- `PositionDataFactory` - Position data (side, quantity, P&L)
- `TradeDataFactory` - Trade data (orders, executions)
- `StrategyDataFactory` - Strategy configurations
- `ProbabilityModelDataFactory` - Probability model configs
- `GameStateDataFactory` - Game state (scores, time, period)
- `DecimalEdgeCaseFactory` - Edge case decimal prices

### Basic Usage

```python
from tests.fixtures.factories import MarketDataFactory, PositionDataFactory

def test_position_pnl():
    """Test position P&L calculation."""
    # Create test market with defaults
    market = MarketDataFactory()

    # Create with custom values
    market = MarketDataFactory(
        ticker="TEST-NFL-KC-BUF-YES",
        yes_bid=Decimal("0.7500")
    )

    # Create multiple
    markets = MarketDataFactory.create_batch(5)

    # Create related data
    position = PositionDataFactory(
        ticker=market['ticker'],
        avg_entry_price=Decimal("0.5000"),
        current_price=market['yes_bid'],
        quantity=100
    )

    # Test
    expected_pnl = (Decimal("0.7500") - Decimal("0.5000")) * 100
    assert position['unrealized_pnl'] == expected_pnl
```

### Edge Case Testing

```python
from tests.fixtures.factories import DecimalEdgeCaseFactory

@pytest.mark.unit
def test_price_validation_edge_cases():
    """Test price validation with edge case values."""
    edge_cases = DecimalEdgeCaseFactory.edge_cases()

    for case in edge_cases:
        price = case['price']
        assert validate_price(price) is True
```

### Helper Functions

```python
from tests.fixtures.factories import (
    create_test_market_with_position,
    create_versioned_strategies
)

def test_market_and_position():
    """Test market with associated position."""
    market, position = create_test_market_with_position()
    assert position['ticker'] == market['ticker']

def test_strategy_versioning():
    """Test multiple versions of same strategy."""
    strategies = create_versioned_strategies("halftime_entry", 3)
    assert len(strategies) == 3
    assert strategies[0]['strategy_version'] == "v1.0"
    assert strategies[2]['strategy_version'] == "v1.2"
    assert strategies[2]['status'] == "active"  # Latest is active
    assert strategies[0]['status'] == "deprecated"  # Old is deprecated
```

---

## Test Fixtures

**Location:** `tests/conftest.py`

### Database Fixtures

**`db_connection` (session scope):**
- Creates connection pool once per test session
- Shared across all tests
- Cleanup after all tests complete

**`db_cursor` (function scope):**
- Provides fresh cursor for each test
- Auto-rollback after test (no pollution)
- Use for database tests

**`clean_test_data` (function scope):**
- Cleans up test records before/after each test
- Deletes records with ticker starting with 'TEST-'
- Ensures test isolation

### Config & Logger Fixtures

**`temp_config_dir`:**
- Temporary directory for test configs
- Auto-cleanup after test

**`test_logger`:**
- Logger instance writing to temp directory
- No pollution of production logs

---

## Coverage Requirements

### Minimum Coverage: 80%

**Enforced by:** pyproject.toml `fail_under = 80.0`
**Command:** `pytest --cov --cov-fail-under=80`

### Per-Module Targets

| Module | Target | Critical |
|--------|--------|----------|
| `database/connection.py` | 90%+ | ✅ Yes |
| `database/crud_operations.py` | 85%+ | ✅ Yes |
| `config/config_loader.py` | 85%+ | 🟡 Medium |
| `utils/logger.py` | 80%+ | 🟡 Medium |
| `api_connectors/*.py` | 85%+ | ✅ Yes |
| `trading/*.py` | 90%+ | ✅ Yes (Phase 5+) |

### Coverage Reports

```bash
# Terminal summary with missing lines
pytest --cov --cov-report=term-missing

# HTML report (browsable)
pytest --cov --cov-report=html
open htmlcov/index.html

# XML report (for CI/CD)
pytest --cov --cov-report=xml
# Generates coverage.xml
```

**Coverage enforcement:**
- ❌ Build fails if coverage < 80%
- ⚠️ Warning if coverage drops from previous run
- ✅ CI/CD uploads coverage to Codecov (Phase 0.7)

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_decimal_precision.py

# Run specific test
pytest tests/unit/test_decimal_precision.py::test_decimal_edge_cases

# Run with verbose output
pytest -v

# Run with extra verbose output (show full diff)
pytest -vv
```

### By Category

```bash
# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only critical tests
pytest -m critical

# Skip slow tests
pytest -m "not slow"

# Run database tests only
pytest -m database

# Combine markers
pytest -m "unit and not slow"
```

### By Directory

```bash
# Run all unit tests
pytest tests/unit/

# Run all integration tests
pytest tests/integration/

# Run specific directory
pytest tests/integration/database/
```

### With Coverage

```bash
# Run with coverage
pytest --cov

# Run with coverage report
pytest --cov --cov-report=html

# Run specific module coverage
pytest --cov=database tests/integration/
```

---

## Test Execution Scripts

### Quick Reference

| Script | Purpose | Duration | Use Case |
|--------|---------|----------|----------|
| `test_fast.sh` | Unit tests only | ~5 sec | During development |
| `test_full.sh` | All tests + coverage | ~30 sec | Before commit |
| `validate_quick.sh` | Code quality + docs | ~3 sec | Rapid feedback |
| `validate_all.sh` | Everything | ~60 sec | Before push |

### test_fast.sh

**Purpose:** Quick feedback during development
**Location:** `scripts/test_fast.sh`

```bash
./scripts/test_fast.sh
```

**What it runs:**
- Unit tests only (`tests/unit/`)
- No coverage report
- Fast (~5 seconds)

**When to use:**
- During active development
- After small code changes
- TDD workflow (red-green-refactor)

---

### test_full.sh

**Purpose:** Complete test suite with coverage
**Location:** `scripts/test_full.sh`

```bash
./scripts/test_full.sh
```

**What it runs:**
- All tests (unit + integration)
- Full coverage report (HTML + XML)
- Saves results to `test_results/TIMESTAMP/`
- ~30 seconds

**When to use:**
- Before committing
- Before creating pull request
- End of development session

**Output:**
- HTML report: `test_results/latest/pytest_report.html`
- Coverage: `htmlcov/index.html`
- Log: `test_results/latest/test_output.log`

---

### validate_quick.sh

**Purpose:** Fast code quality validation
**Location:** `scripts/validate_quick.sh`

```bash
./scripts/validate_quick.sh
```

**What it runs:**
1. Ruff linting
2. Ruff formatting check
3. Mypy type checking
4. Documentation validation
- ~3 seconds

**When to use:**
- Every few minutes during development
- Before running tests
- Quick sanity check

---

### validate_all.sh

**Purpose:** Complete validation suite
**Location:** `scripts/validate_all.sh`

```bash
./scripts/validate_all.sh
```

**What it runs:**
1. validate_quick.sh (code quality + docs)
2. test_full.sh (all tests + coverage)
3. Security scan (hardcoded credentials)
- ~60 seconds

**When to use:**
- Before committing (MANDATORY)
- Before pushing to remote
- Phase completion
- Pre-deployment

**Exit codes:**
- 0 = All checks passed
- 1 = Validation failed

---

## Parallel Execution

### Using pytest-xdist

Run tests in parallel for faster execution:

```bash
# Run on 4 CPUs
pytest -n 4

# Run on all available CPUs
pytest -n auto

# Parallel with coverage
pytest -n auto --cov
```

**Benefits:**
- 2-4x faster test execution
- Better CPU utilization
- Same test isolation

**When to use:**
- Large test suites (>100 tests)
- CI/CD pipelines
- Before major commits

**Note:** Some integration tests may need serialization (use `@pytest.mark.serial` if needed)

---

## Critical Test Scenarios

### 1. Decimal Precision Tests

**Why Critical:** Float errors cause incorrect trade calculations

**Test Coverage:**
- ✅ Market prices stored as Decimal
- ✅ Position prices stored as Decimal
- ✅ Config values converted to Decimal
- ✅ Logs serialize Decimal to string (not float)

**Example Test:**
```python
@pytest.mark.critical
def test_decimal_not_float(db_connection, clean_test_data):
    """
    CRITICAL: Verify prices are Decimal, NOT float.

    Float errors cause incorrect trade calculations.
    """
    from tests.fixtures.factories import MarketDataFactory

    market_data = MarketDataFactory()
    market_id = create_market(**market_data)
    market = get_current_market(market_data['ticker'])

    # CRITICAL: Must be Decimal, NOT float
    assert isinstance(market['yes_bid'], Decimal)
    assert not isinstance(market['yes_bid'], float)
```

---

### 2. SCD Type 2 Versioning Tests

**Why Critical:** Historical data integrity for auditing/compliance

**Test Coverage:**
- ✅ Old records marked `row_current_ind = FALSE`
- ✅ New records marked `row_current_ind = TRUE`
- ✅ `row_end_ts` set on old records
- ✅ History queryable

**Example Test:**
```python
@pytest.mark.critical
@pytest.mark.integration
def test_scd_type2_versioning(db_connection, clean_test_data):
    """Verify SCD Type 2 creates history correctly."""
    from tests.fixtures.factories import MarketDataFactory

    # Create initial market
    market_data = MarketDataFactory(ticker="TEST-NFL-VERSIONING")
    create_market(**market_data)

    # Update market (should create new version)
    update_market_with_versioning(
        ticker="TEST-NFL-VERSIONING",
        yes_bid=Decimal("0.6000")
    )

    # Verify history
    history = get_market_history("TEST-NFL-VERSIONING")
    assert len(history) == 2

    # Current version
    current = [m for m in history if m['row_current_ind'] is True][0]
    assert current['yes_bid'] == Decimal("0.6000")

    # Historical version
    historical = [m for m in history if m['row_current_ind'] is False][0]
    assert historical['yes_bid'] == Decimal("0.5000")  # Original
    assert historical['row_end_ts'] is not None
```

---

### 3. Error Handling Tests (Phase 1.5+)

**Why Critical:** System resilience under failure conditions
**Test File:** `tests/integration/test_error_handling.py`
**Impact:** +3% coverage (87% → 90%)

**Test Coverage:**
- ✅ Connection pool exhaustion
- ✅ Database connection loss/reconnection
- ✅ Transaction rollback on failure
- ✅ Invalid YAML syntax
- ✅ Missing config files
- ✅ Missing environment variables
- ✅ Invalid data types
- ✅ Logger file permission errors
- ✅ NULL constraint violations
- ✅ Foreign key violations

**Rationale:** Initial tests focused on happy paths. Error handling tests validate graceful degradation and clear error messages.

---

### 4. SQL Injection Prevention Tests

**Why Critical:** Security vulnerability could corrupt database

**Test Coverage:**
- ✅ Parameterized queries block injection
- ✅ User input safely escaped
- ✅ No string concatenation in SQL

**Example Test:**
```python
@pytest.mark.critical
@pytest.mark.integration
def test_sql_injection_blocked(db_connection):
    """Verify SQL injection attempts are blocked."""
    from database.crud_operations import fetch_one

    malicious = "'; DROP TABLE markets; --"

    # Attempt injection (should be safely escaped)
    result = fetch_one("SELECT %s as value", (malicious,))

    assert result['value'] == malicious  # Safely escaped

    # Verify table still exists
    tables = fetch_all(
        "SELECT * FROM information_schema.tables WHERE table_name='markets'"
    )
    assert len(tables) == 1  # Table not dropped
```

---

### 5. Trade Attribution Tests

**Why Critical:** Required for A/B testing and performance analysis

**Test Coverage:**
- ✅ Every trade has `strategy_id`
- ✅ Every trade has `model_id`
- ✅ Foreign keys enforced
- ✅ Attribution queryable

---

## Debugging Tests

### Show Detailed Output

```bash
# Extra verbose (show full diff)
pytest -vv

# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Show full traceback
pytest --tb=long
```

### Stop at First Failure

```bash
# Stop at first failure
pytest -x

# Stop after N failures
pytest --maxfail=3
```

### Drop into Debugger

```bash
# Drop into pdb on failure
pytest --pdb

# Drop into pdb at start of test
pytest --trace
```

### Show Test Duration

```bash
# Show slowest 10 tests
pytest --durations=10

# Show all test durations
pytest --durations=0
```

### Logging During Tests

```bash
# Show all log output
pytest --log-cli-level=DEBUG

# Show INFO and above
pytest --log-cli-level=INFO
```

### Run Specific Failed Tests

```bash
# Run only last failed tests
pytest --lf

# Run failed tests first, then others
pytest --ff
```

---

## Best Practices

### 1. Test Naming Convention

**Convention:** `test_<what>_<scenario>`

**Good:**
- ✅ `test_create_market_with_decimal_precision`
- ✅ `test_update_market_scd_type2_versioning`
- ✅ `test_sql_injection_blocked`

**Bad:**
- ❌ `test_1`
- ❌ `test_market`
- ❌ `test_it_works`

---

### 2. Test Isolation

**Principle:** Tests should not affect each other

**How:**
- Use `clean_test_data` fixture
- Use test data with 'TEST-' prefix
- Rollback transactions after test
- Use temporary directories

---

### 3. Test Documentation

**Every test needs a docstring:**

```python
def test_decimal_precision():
    """
    Test that market prices stored as Decimal, NOT float.

    CRITICAL: Float errors cause incorrect trade calculations.
    This test ensures DECIMAL(10,4) type preserved.
    """
    # Test code...
```

---

### 4. Arrange-Act-Assert Pattern

```python
def test_create_position():
    # ARRANGE: Set up test data
    market = MarketDataFactory(ticker="TEST-NFL")

    # ACT: Perform action
    position_id = create_position(
        ticker=market['ticker'],
        side="YES",
        quantity=100
    )

    # ASSERT: Verify results
    position = get_position(position_id)
    assert position is not None
    assert position['ticker'] == market['ticker']
```

---

### 5. Test Edge Cases

**Always test:**
- ✅ Minimum values (0.0001)
- ✅ Maximum values (0.9999)
- ✅ Sub-penny precision (0.4275)
- ✅ Empty inputs
- ✅ None values
- ✅ Error conditions

---

## CI/CD Integration

### Pre-Commit Checks (Local)

**Before every commit:**
```bash
./scripts/validate_all.sh
```

**What it checks:**
- Code linting (ruff)
- Code formatting (ruff)
- Type checking (mypy)
- Documentation validation
- All tests passing
- Coverage ≥80%
- No hardcoded credentials

---

### Pre-Push Checks (Local)

**Before every push:**
```bash
./scripts/validate_all.sh
pytest -m "not slow"  # Skip slow tests locally
```

---

### Automated CI/CD (Phase 0.7 - Planned)

**GitHub Actions workflow runs on:**
- Every push to main
- Every pull request
- Scheduled nightly

**Workflow:**
1. Install dependencies
2. Run `validate_all.sh`
3. Upload coverage to Codecov
4. Upload test results as artifacts
5. Block merge if validation fails

**See:** Phase 0.7 Future Enhancements

---

## Future Enhancements

### Phase 0.7: CI/CD Integration (Planned)

**GitHub Actions Workflow:**
- Automated validation on push/PR
- Coverage reporting to Codecov
- Branch protection enforcement
- Status badges on README

**Expected Benefits:**
- Zero manual validation errors
- Team collaboration ready
- Historical quality metrics
- Public quality signals (badges)

**Prerequisites:** Phase 0.6c validation suite operational

**Reference:** REQ-CICD-001, REQ-CICD-002, REQ-CICD-003

---

### Phase 0.7: Advanced Testing (Planned)

#### Performance Benchmarking

**Tool:** pytest-benchmark
**Purpose:** Detect performance regressions

**Example:**
```python
@pytest.mark.benchmark
def test_crud_create_performance(benchmark):
    """Benchmark market creation."""
    result = benchmark(create_market, **sample_market_data)
    assert result is not None
    # Baseline: <10ms
    # Regression threshold: +10%
```

**Target Operations:**
- Database CRUD operations (<10ms each)
- API client requests (<100ms)
- Complex queries (<50ms)

**Reference:** REQ-TEST-007, ADR-052

---

#### Security Testing

**Tools:**
- Bandit (Python security linter)
- Safety (dependency vulnerability scanner)

**Integration:** CI/CD pipeline blocks merge on critical findings

**Example:**
```bash
# In CI/CD workflow
bandit -r . -ll  # High/Medium severity only
safety check --full-report
```

**Reference:** REQ-TEST-008, ADR-053

---

#### Mutation Testing

**Tool:** mutpy
**Purpose:** Validate test suite quality

**Concept:** Mutpy changes code (e.g., `>` to `>=`). Good tests catch mutations.

**Example:**
```bash
# Run mutation testing on database module
mut.py --target database/ --unit-test tests/unit/test_database*.py
```

**Target:** >80% mutation score on critical modules

**Reference:** REQ-TEST-009, ADR-054

---

#### Property-Based Testing

**Tool:** Hypothesis
**Purpose:** Generate edge cases automatically

**Example:**
```python
from hypothesis import given
from hypothesis.strategies import decimals

@given(
    price1=decimals(min_value='0.0001', max_value='0.9999', places=4),
    price2=decimals(min_value='0.0001', max_value='0.9999', places=4)
)
def test_decimal_addition_commutative(price1, price2):
    """Decimal addition should be commutative."""
    assert price1 + price2 == price2 + price1
```

**Reference:** REQ-TEST-010, ADR-055

---

## Adding Tests for New Features

### Checklist

When adding new feature in any phase:

- [ ] Write unit tests for new functions
- [ ] Write integration tests for database interactions
- [ ] Add critical tests for trading logic
- [ ] Update factories if new models added
- [ ] Run full test suite: `pytest`
- [ ] Verify coverage: `pytest --cov`
- [ ] Update this document if new patterns emerge

---

### Example Workflow (TDD)

1. **Write failing test first**
```python
def test_new_feature():
    """Test new feature behavior."""
    result = new_function(input_data)
    assert result == expected_output
```

2. **Run test (should fail)**
```bash
pytest tests/unit/test_new_feature.py -v
```

3. **Implement feature**
```python
def new_function(input_data):
    # Implementation...
    return output
```

4. **Run test (should pass)**
```bash
pytest tests/unit/test_new_feature.py -v
```

5. **Verify coverage**
```bash
pytest --cov=module tests/unit/test_new_feature.py
```

6. **Refactor if needed**

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2025-10-29 | Major expansion with implementation details (Phase 0.6c) |
| 1.1 | 2025-10-24 | Added error handling test section (Phase 1.5) |
| 1.0 | 2025-10-23 | Initial testing strategy document |

---

## References

- **Configuration:** `pyproject.toml` - Test, coverage, ruff, mypy config
- **Fixtures:** `tests/conftest.py` - Shared fixtures
- **Factories:** `tests/fixtures/factories.py` - Test data factories
- **Scripts:** `scripts/test_*.sh`, `scripts/validate_*.sh` - Execution scripts
- **Requirements:** `docs/foundation/MASTER_REQUIREMENTS_V2.12.md` - REQ-TEST-* requirements
- **ADRs:** `docs/foundation/ARCHITECTURE_DECISIONS_V2.13.md` - ADR-048 through ADR-077
- **Validation:** `docs/foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md` - Overall quality infrastructure

---

**END OF TESTING_STRATEGY_V2.0.md**
