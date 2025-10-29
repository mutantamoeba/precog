# Testing Strategy V1.1

**Document Type:** Foundation
**Status:** ✅ Active
**Version:** 1.1
**Created:** 2025-10-23
**Last Updated:** 2025-10-24
**Changes in V1.1:** Added error handling test section (Phase 1.5), updated test structure
**Owner:** Development Team
**Applies to:** All Phases (1-10)

---

## Executive Summary

This document defines the **standard testing strategy** for the Precog trading system across all development phases. All code must meet minimum coverage requirements and pass automated tests before deployment.

**Key Requirements:**
- ✅ Minimum 80% code coverage
- ✅ All tests pass before merge/deploy
- ✅ Critical tests marked and monitored
- ✅ Automated testing in CI/CD pipeline

---

## Testing Framework

### Core Tools

**Test Runner:** pytest 8.4+
- **Why:** Industry standard, powerful fixtures, excellent plugin ecosystem
- **Config:** `pytest.ini` in project root

**Coverage Tool:** pytest-cov 7.0+
- **Why:** Integrated with pytest, supports HTML reports
- **Minimum:** 80% coverage across all modules
- **Reports:** `tests/coverage_html/`

**Test Structure:**
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_database_connection.py
├── test_crud_operations.py
├── test_config_loader.py
├── test_logger.py
├── test_error_handling.py   # Error paths & edge cases (Phase 1.5)
└── coverage_html/           # Coverage reports (generated)
```

---

## Test Categories

### 1. Unit Tests

**Purpose:** Test individual functions in isolation
**Marker:** `@pytest.mark.unit`
**Speed:** Fast (<0.1s per test)

**Characteristics:**
- No database connections
- No file I/O (use temp directories)
- No network calls
- Pure function testing

**Example:**
```python
@pytest.mark.unit
def test_decimal_serializer():
    """Test Decimal serialization."""
    result = decimal_serializer(Decimal('0.5200'))
    assert result == '0.5200'
    assert type(result) == str
```

### 2. Integration Tests

**Purpose:** Test components working together
**Marker:** `@pytest.mark.integration`
**Speed:** Medium (0.1s - 2s per test)

**Characteristics:**
- Database interactions allowed
- File system access allowed
- Tests real connections
- Verifies integration points

**Example:**
```python
@pytest.mark.integration
def test_create_market_and_retrieve(db_pool, clean_test_data):
    """Test creating market and retrieving it."""
    market_id = create_market(ticker='TEST-NFL', ...)
    market = get_current_market('TEST-NFL')
    assert market is not None
```

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
def test_decimal_precision_not_float(db_pool, sample_market_data):
    """CRITICAL: Verify prices are Decimal, NOT float."""
    market_id = create_market(**sample_market_data)
    market = get_current_market(sample_market_data['ticker'])

    assert type(market['yes_price']) == Decimal
    assert type(market['no_price']) == Decimal
```

### 4. Slow Tests

**Purpose:** Long-running tests (performance, stress tests)
**Marker:** `@pytest.mark.slow`
**Usage:** Skip during development, run in CI

**Example:**
```python
@pytest.mark.slow
def test_connection_pool_exhaustion():
    """Test pool behavior under heavy load."""
    # Simulate 1000 concurrent connections...
```

---

## Test Fixtures

**Location:** `tests/conftest.py`

### Database Fixtures

**`db_pool` (session scope):**
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

### Test Data Fixtures

**`sample_market_data`:**
- Standard market data for testing
- Ticker: 'TEST-NFL-KC-BUF-YES'
- Prices: Decimal('0.5200'), Decimal('0.4800')

**`sample_position_data`:**
- Standard position data for testing
- Quantity: 100 contracts
- Entry price: Decimal('0.5200')

**`decimal_prices`:**
- Edge case prices for testing
- Includes: min (0.0001), max (0.9999), sub-penny (0.4275)

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

**Enforced by:** `pytest.ini` line 28
**Command:** `pytest --cov --cov-fail-under=80`

**Per-Module Targets:**
| Module | Target | Critical |
|--------|--------|----------|
| `database/connection.py` | 90%+ | ✅ Yes |
| `database/crud_operations.py` | 85%+ | ✅ Yes |
| `config/config_loader.py` | 85%+ | 🟡 Medium |
| `utils/logger.py` | 80%+ | 🟡 Medium |

**Coverage Reports:**
```bash
# Terminal summary
pytest --cov --cov-report=term-missing

# HTML report (browsable)
pytest --cov --cov-report=html
# Open tests/coverage_html/index.html
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_database_connection.py

# Run specific test
pytest tests/test_database_connection.py::test_connection_pool_exists

# Run with verbose output
pytest -v

# Run only unit tests (fast)
pytest -m unit

# Run only critical tests
pytest -m critical

# Skip slow tests
pytest -m "not slow"

# Run with coverage
pytest --cov
```

### Test Output

**Success:**
```
tests/test_database_connection.py::test_connection_pool_exists PASSED [10%]
tests/test_database_connection.py::test_database_connectivity PASSED [20%]
...
======================== 42 passed in 5.23s ========================
```

**Failure:**
```
tests/test_crud_operations.py::test_decimal_precision FAILED [50%]
________________________________ FAILURES _________________________________
_________________ test_decimal_precision _________________
    def test_decimal_precision():
>       assert type(price) == Decimal
E       AssertionError: assert <class 'float'> == <class 'decimal.Decimal'>
```

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
def test_decimal_not_float(db_pool, sample_market_data):
    market_id = create_market(**sample_market_data)
    market = get_current_market(sample_market_data['ticker'])

    # CRITICAL: Must be Decimal, NOT float
    assert type(market['yes_price']) == Decimal
```

### 2. SCD Type 2 Versioning Tests

**Why Critical:** Historical data integrity for auditing/compliance
**Test Coverage:**
- ✅ Old records marked row_current_ind = FALSE
- ✅ New records marked row_current_ind = TRUE
- ✅ row_end_ts set on old records
- ✅ History queryable

### 3. Error Handling Tests (NEW - Phase 1.5)

**Why Critical:** System resilience under failure conditions
**Test File:** `tests/test_error_handling.py`
**Added:** 2025-10-24
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

**Rationale:** Initial tests focused on happy paths (87% coverage). Error handling tests validate graceful degradation and clear error messages under failure conditions.

**Example Test:**
```python
@pytest.mark.critical
def test_scd_type2_versioning(db_pool, sample_market_data):
    create_market(**sample_market_data)
    update_market_with_versioning(ticker=..., yes_price=...)

    history = get_market_history(ticker)
    assert len(history) == 2
    assert history[0]['row_current_ind'] is True
    assert history[1]['row_current_ind'] is False
```

### 3. SQL Injection Prevention Tests

**Why Critical:** Security vulnerability could corrupt database
**Test Coverage:**
- ✅ Parameterized queries block injection
- ✅ User input safely escaped
- ✅ No string concatenation in SQL

**Example Test:**
```python
@pytest.mark.critical
def test_sql_injection_blocked(db_pool):
    malicious = "'; DROP TABLE markets; --"
    result = fetch_one("SELECT %s as value", (malicious,))

    assert result['value'] == malicious  # Safely escaped
    # Verify table still exists
    tables = fetch_all("SELECT * FROM information_schema.tables WHERE table_name='markets'")
    assert len(tables) == 1
```

### 4. Trade Attribution Tests

**Why Critical:** Required for A/B testing and performance analysis
**Test Coverage:**
- ✅ Every trade has strategy_id
- ✅ Every trade has model_id
- ✅ Foreign keys enforced
- ✅ Attribution queryable

---

## Logging During Tests

### Pytest Log Capture

**Automatic:** Pytest captures all logs
**View on failure:** Logs displayed when test fails
**View always:** Use `pytest --log-cli-level=INFO`

**Example:**
```bash
pytest --log-cli-level=DEBUG
```

### Test Logs Location

**Production Logs:** `logs/precog_YYYY-MM-DD.log`
**Test Logs:** Captured by pytest, displayed in terminal

**Isolation:** Tests use `temp_log_dir` fixture (no pollution)

### Verifying Logs in Tests

```python
def test_logging_works(test_logger, caplog):
    """Test that logging produces expected output."""
    test_logger.info("test_event", value=42)

    # Check logs captured
    assert "test_event" in caplog.text
```

---

## Best Practices

### 1. Test Naming

**Convention:** `test_<what>_<scenario>`

**Good:**
- ✅ `test_create_market_with_decimal_precision`
- ✅ `test_update_market_scd_type2_versioning`
- ✅ `test_sql_injection_blocked`

**Bad:**
- ❌ `test_1`
- ❌ `test_market`
- ❌ `test_it_works`

### 2. Test Isolation

**Principle:** Tests should not affect each other

**How:**
- Use `clean_test_data` fixture
- Use test data with 'TEST-' prefix
- Rollback transactions after test
- Use temporary directories

### 3. Test Documentation

**Every test needs:**
```python
def test_decimal_precision():
    """
    Test that market prices stored as Decimal, NOT float.

    CRITICAL: Float errors cause incorrect trade calculations.
    This test ensures DECIMAL(10,4) type preserved.
    """
```

### 4. Arrange-Act-Assert Pattern

```python
def test_create_and_retrieve_market():
    # ARRANGE: Set up test data
    market_data = {'ticker': 'TEST-NFL', ...}

    # ACT: Perform action
    market_id = create_market(**market_data)
    market = get_current_market('TEST-NFL')

    # ASSERT: Verify results
    assert market is not None
    assert market['ticker'] == 'TEST-NFL'
```

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

### Pre-Commit Checks

**Before every commit:**
```bash
# Run critical tests
pytest -m critical

# Check coverage
pytest --cov --cov-fail-under=80
```

### Pre-Deploy Checks

**Before every deployment:**
```bash
# Run ALL tests
pytest

# Verify coverage
pytest --cov --cov-fail-under=80

# Run slow tests
pytest -m slow
```

### Automated Alerts

**Test failure triggers:**
- 🔴 Slack notification
- 🔴 Email to dev team
- 🔴 Block deployment

**Coverage drop triggers:**
- 🟡 Warning if < 85%
- 🔴 Block if < 80%

---

## Adding Tests for New Features

### Checklist

When adding new feature in any phase:

- [ ] Write unit tests for new functions
- [ ] Write integration tests for database interactions
- [ ] Add critical tests for trading logic
- [ ] Update fixtures if needed (conftest.py)
- [ ] Run full test suite: `pytest`
- [ ] Verify coverage: `pytest --cov`
- [ ] Update this document if new patterns emerge

### Example Workflow

1. **Write failing test first** (TDD)
```python
def test_new_feature():
    result = new_function(input)
    assert result == expected
```

2. **Implement feature**
```python
def new_function(input):
    # Implementation...
    return output
```

3. **Run tests**
```bash
pytest tests/test_new_feature.py -v
```

4. **Verify coverage**
```bash
pytest --cov=module tests/test_new_feature.py
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-23 | Initial testing strategy document |

---

## References

- `pytest.ini` - Test configuration
- `tests/conftest.py` - Shared fixtures
- Phase 1 Task Plan - Testing tasks
- MASTER_REQUIREMENTS_V2.6.md - REQ-TEST-001 through REQ-TEST-006

---

**END OF DOCUMENT**
