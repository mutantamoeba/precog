# Precog Testing Suite

## Quick Start

```bash
# Run all tests
pytest

# Run only unit tests (fast)
pytest tests/unit/ -v

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/unit/test_crud_operations.py

# Run tests matching pattern
pytest -k "decimal"
```

## Test Organization

```
tests/
├── unit/                  # Fast unit tests (no external dependencies)
├── integration/           # Integration tests (database, APIs, files)
├── fixtures/              # Shared test fixtures and factories
│   ├── __init__.py
│   └── factories.py       # factory-boy test data factories
├── conftest.py            # Pytest configuration and shared fixtures
└── README.md              # This file
```

## Test Categories

### Unit Tests (`tests/unit/`)
- **Purpose:** Test individual functions in isolation
- **Speed:** Fast (<0.1s per test)
- **Dependencies:** None (pure functions, mocked externals)
- **Marker:** `@pytest.mark.unit`

**Example:**
```python
@pytest.mark.unit
def test_decimal_serialization():
    """Test Decimal to string conversion."""
    result = decimal_to_string(Decimal("0.5200"))
    assert result == "0.5200"
    assert isinstance(result, str)
```

### Integration Tests (`tests/integration/`)
- **Purpose:** Test components working together
- **Speed:** Medium (0.1s - 2s per test)
- **Dependencies:** Database, files, external services (test instances)
- **Marker:** `@pytest.mark.integration`

**Example:**
```python
@pytest.mark.integration
def test_create_and_retrieve_market(db_connection):
    """Test full CRUD cycle for markets."""
    market_id = create_market(ticker="TEST-NFL", ...)
    market = get_current_market("TEST-NFL")
    assert market is not None
    assert market["ticker"] == "TEST-NFL"
```

## Using Test Factories

Test factories (using `factory-boy`) provide consistent test data:

```python
from tests.fixtures.factories import MarketDataFactory, PositionDataFactory

def test_position_pnl():
    """Test position P&L calculation."""
    # Create test market
    market = MarketDataFactory(
        ticker="TEST-NFL-KC-BUF-YES",
        yes_bid=Decimal("0.6000")
    )

    # Create test position
    position = PositionDataFactory(
        ticker=market["ticker"],
        avg_entry_price=Decimal("0.5000"),
        current_price=market["yes_bid"],
        quantity=100
    )

    # Test P&L
    expected_pnl = (Decimal("0.6000") - Decimal("0.5000")) * 100
    assert position["unrealized_pnl"] == expected_pnl
```

**Available Factories:**
- `MarketDataFactory` - Market data (prices, volume, etc.)
- `PositionDataFactory` - Position data (side, quantity, P&L)
- `TradeDataFactory` - Trade data (orders, executions)
- `StrategyDataFactory` - Strategy configurations
- `ProbabilityModelDataFactory` - Probability model configs
- `GameStateDataFactory` - Game state (scores, time, etc.)
- `DecimalEdgeCaseFactory` - Edge case decimal prices

## Test Markers

Use markers to categorize and run specific tests:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run critical tests only
pytest -m critical

# Skip slow tests
pytest -m "not slow"

# Run database tests only
pytest -m database
```

**Available markers:**
- `unit` - Fast unit tests
- `integration` - Integration tests
- `slow` - Slow tests (performance, load)
- `critical` - Critical tests (must always pass)
- `database` - Tests requiring database
- `api` - Tests requiring API access

## Configuration

Test configuration is in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Fast unit tests",
    "integration: Integration tests",
    "critical: Critical tests",
]
```

## Coverage

Minimum coverage: **80%**

```bash
# Run tests with coverage
pytest --cov=. --cov-report=html

# View HTML report
open htmlcov/index.html  # (or start htmlcov/index.html on Windows)

# Coverage enforced by CI/CD
pytest --cov --cov-fail-under=80  # Fails if coverage < 80%
```

## Writing Good Tests

### Test Naming Convention

```python
# Good names
def test_create_market_with_decimal_precision():
def test_update_market_scd_type2_versioning():
def test_sql_injection_blocked():

# Bad names
def test_1():
def test_market():
def test_it_works():
```

### Arrange-Act-Assert Pattern

```python
def test_create_position():
    # ARRANGE: Set up test data
    market = MarketDataFactory(ticker="TEST-NFL")

    # ACT: Perform action
    position_id = create_position(
        ticker=market["ticker"],
        side="YES",
        quantity=100
    )

    # ASSERT: Verify results
    position = get_position(position_id)
    assert position is not None
    assert position["ticker"] == market["ticker"]
```

### Test Documentation

Every test needs a docstring:

```python
def test_decimal_not_float():
    """
    Test that market prices stored as Decimal, NOT float.

    CRITICAL: Float errors cause incorrect trade calculations.
    This test ensures DECIMAL(10,4) type is preserved.
    """
    # Test code...
```

## Running Tests in Parallel

Use `pytest-xdist` for parallel execution:

```bash
# Run tests on 4 CPUs
pytest -n 4

# Run tests on all available CPUs
pytest -n auto
```

## Test Scripts

Convenience scripts in `scripts/`:

```bash
# Fast unit tests only (~5 seconds)
./scripts/test_fast.sh

# Full test suite with coverage (~30 seconds)
./scripts/test_full.sh
```

## Debugging Failing Tests

```bash
# Show detailed output
pytest -vv

# Stop at first failure
pytest -x

# Drop into debugger on failure
pytest --pdb

# Show print statements
pytest -s

# Show full diff for assertions
pytest -vv --tb=long
```

## Test Isolation

Tests should not affect each other:

- ✅ Use `conftest.py` fixtures for setup/teardown
- ✅ Use test data with 'TEST-' prefix
- ✅ Rollback database transactions after tests
- ✅ Use temporary directories for file tests

## CI/CD Integration

Tests run automatically on:
- Every commit (fast tests)
- Every pull request (full test suite)
- Scheduled nightly (including slow tests)

## Additional Resources

- Full testing strategy: `docs/foundation/TESTING_STRATEGY_V2.0.md`
- Validation architecture: `docs/foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md`
- Coverage reports: `htmlcov/index.html` (after running tests)
- Test results: `test_results/latest/` (after running full suite)

---

**Questions?** See `TESTING_STRATEGY_V2.0.md` or ask in team chat.
