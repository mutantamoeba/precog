# Phase 1.5 Test Plan

**Version:** 1.0
**Created:** 2025-11-16
**Phase:** Phase 1.5 (Foundation Validation)
**Status:** 🔵 Approved - Ready for Implementation
**Purpose:** Comprehensive test planning for Strategy Manager, Model Manager, Position Manager (trailing stops), and Config System enhancements

---

## Document Purpose

This document provides a complete test plan for Phase 1.5 deliverables, created BEFORE implementation begins (following CLAUDE.md mandate: "DO NOT write production code until test planning complete").

**Reference Documents:**
- `docs/foundation/DEVELOPMENT_PHASES_V1.5.md` (Phase 1.5 specification, lines 786-915)
- `docs/foundation/MASTER_REQUIREMENTS_V2.16.md` (REQ-VER-001 through REQ-VER-005, REQ-TRAIL-001 through REQ-TRAIL-004)
- `docs/guides/VERSIONING_GUIDE_V1.0.md` (Immutable version pattern)
- `docs/guides/TRAILING_STOP_GUIDE_V1.0.md` (Trailing stop implementation)
- `docs/database/DATABASE_SCHEMA_SUMMARY_V1.8.md` (strategies, probability_models, positions tables)

---

## Table of Contents

1. [Requirements Analysis](#1-requirements-analysis)
2. [Test Categories](#2-test-categories)
3. [Test Infrastructure](#3-test-infrastructure)
4. [Critical Test Scenarios](#4-critical-test-scenarios)
5. [Edge Cases](#5-edge-cases)
6. [Success Criteria](#6-success-criteria)
7. [Test Execution Plan](#7-test-execution-plan)

---

## 1. Requirements Analysis

### Relevant Requirements

**Versioning Requirements:**
- **REQ-VER-001:** Immutable Version Configs (Status: ✅ Complete - Schema ready)
  - Config field is IMMUTABLE once created
  - To change: Create new version (v1.0 → v1.1)

- **REQ-VER-002:** Semantic Versioning (Phase 1.5)
  - Version format: v1.0, v1.1, v2.0 (MAJOR.MINOR)
  - MAJOR: Breaking changes, MINOR: Bug fixes/enhancements

- **REQ-VER-003:** Trade Attribution (100% of trades linked to exact versions)
  - Every trade must reference strategy_id and model_id
  - Enable A/B testing and performance analysis

- **REQ-VER-004:** Version Lifecycle Management
  - Strategies: draft → testing → active → inactive → deprecated
  - Models: draft → training → validating → active → deprecated

- **REQ-VER-005:** A/B Testing Support
  - Multiple versions can coexist with different statuses
  - Compare performance across versions (paper_roi, live_roi, validation_accuracy)

**Trailing Stop Requirements:**
- **REQ-TRAIL-001:** Dynamic Trailing Stops
  - Stops move with favorable price movement
  - One-way ratchet: Stops tighten but NEVER loosen

- **REQ-TRAIL-002:** JSONB State Management
  - Flexible storage for trailing stop state
  - Required fields: active, peak_price, current_stop_price, current_distance

- **REQ-TRAIL-003:** Stop Price Updates
  - Update stop price when current price > peak_price
  - Stop price = peak_price * (1 - distance)

- **REQ-TRAIL-004:** Peak Price Tracking
  - Track highest price reached since position opened
  - Peak price monotonically increases (never decreases)

**Supporting Requirements:**
- **REQ-SYS-003:** Decimal Precision (ALWAYS use Decimal, NEVER float for prices/probabilities)
- **REQ-KELLY-001:** Fractional Kelly Position Sizing
- **REQ-KELLY-002:** Default Kelly Fraction 0.25

### Module Coverage Targets

| Module | Coverage Target | Rationale |
|--------|----------------|-----------|
| `trading/strategy_manager.py` | ≥85% | Business logic tier (CRUD + validation) |
| `analytics/model_manager.py` | ≥85% | Business logic tier (CRUD + validation) |
| `trading/position_manager.py` | ≥85% | Business logic tier (lifecycle + trailing stops) |
| `utils/config.py` | ≥85% | Critical infrastructure (YAML loading + version resolution) |
| **Overall Phase 1.5** | **≥85%** | Minimum acceptable for production readiness |

---

## 2. Test Categories

### Strategy Manager (`trading/strategy_manager.py`)

**Unit Tests** (target: ≥85% coverage)
1. `test_create_strategy()` - Create new strategy version
2. `test_create_strategy_version()` - Create v1.1 from v1.0
3. `test_get_strategy()` - Retrieve by ID
4. `test_get_active_strategies()` - Filter by status='active'
5. `test_update_strategy_status()` - draft → testing → active
6. `test_update_strategy_metrics()` - Update paper_roi, live_roi
7. `test_immutability_enforcement()` - ⚠️ CRITICAL: Prevent config changes
8. `test_unique_constraint()` - No duplicate (name, version) pairs
9. `test_decimal_precision_in_config()` - All prices/probabilities as Decimal
10. `test_invalid_status_transitions()` - deprecated → active should fail

**Integration Tests**
1. `test_strategy_lifecycle_end_to_end()` - Create → test → activate → deprecate
2. `test_multiple_versions_coexist()` - v1.0, v1.1, v2.0 all in database

**Property-Based Tests** (Hypothesis)
- ✅ Already complete! (`tests/property/test_strategy_versioning_properties.py`)
- 14 properties covering version precedence, semantic versioning

---

### Model Manager (`analytics/model_manager.py`)

**Unit Tests** (target: ≥85% coverage)
1. `test_create_model()` - Create new model version
2. `test_create_model_version()` - Create v1.1 from v1.0
3. `test_get_model()` - Retrieve by ID
4. `test_get_active_models()` - Filter by status='active'
5. `test_update_model_status()` - draft → training → validating → active
6. `test_update_validation_metrics()` - Update validation_accuracy
7. `test_immutability_enforcement()` - ⚠️ CRITICAL: Prevent config changes
8. `test_unique_constraint()` - No duplicate (model_name, model_version) pairs
9. `test_decimal_precision_in_config()` - All metrics as Decimal
10. `test_validation_lifecycle()` - Training → validating → active with metrics

**Integration Tests**
1. `test_model_lifecycle_end_to_end()` - Create → train → validate → activate
2. `test_multiple_model_versions()` - elo_nfl v1.0, v1.1, v2.0

---

### Position Manager (`trading/position_manager.py`)

**Unit Tests** (target: ≥85% coverage)
1. `test_initialize_trailing_stop()` - Set initial state on position creation
2. `test_update_trailing_stop_favorable()` - Price increases → stop tightens
3. `test_update_trailing_stop_unfavorable()` - Price decreases → stop unchanged
4. `test_detect_stop_trigger()` - Current price < stop_price → trigger=True
5. `test_jsonb_state_validation()` - Valid JSONB schema
6. `test_peak_price_tracking()` - Track highest price reached
7. `test_stop_never_loosens()` - ⚠️ CRITICAL: One-way ratchet property
8. `test_inactive_trailing_stop()` - active=False → updates ignored
9. `test_decimal_precision_in_state()` - All JSONB prices as Decimal strings
10. `test_stop_at_boundary()` - price == stop_price → triggered

**Property-Based Tests** (Hypothesis) - NEW for Phase 1.5
**File:** `tests/property/test_trailing_stop_properties.py`

⚠️ **CRITICAL:** Trailing stops are THE core feature of Phase 1.5. Property tests validate mathematical invariants across hundreds of random price sequences.

**5 Properties to Implement (~2-3 hours):**

1. **test_trailing_stop_never_loosens** - ONE-WAY RATCHET INVARIANT
   ```python
   @given(
       initial_price=price_decimal(min_value=0.10, max_value=0.90),
       price_movements=st.lists(
           price_decimal(min_value=0.10, max_value=0.90),
           min_size=1,
           max_size=20
       )
   )
   def test_trailing_stop_never_loosens(position_manager, initial_price, price_movements):
       """Property: Trailing stop stop_price never decreases.

       INVARIANT: For ANY sequence of price movements,
                  stop_price[i+1] >= stop_price[i]

       This is the most critical property - if violated, we lose money!
       """
   ```

2. **test_trailing_stop_tightens_on_price_increase** - FAVORABLE MOVEMENT
   ```python
   @given(
       initial_price=price_decimal(min_value=0.10, max_value=0.80),
       price_increase=st.decimals(min_value=0.01, max_value=0.20, places=4)
   )
   def test_trailing_stop_tightens_on_price_increase(
       position_manager, initial_price, price_increase
   ):
       """Property: When price increases, stop increases or stays same.

       INVARIANT: If new_price > old_price, then new_stop >= old_stop

       Note: Stop might stay same if price increase is small
       """
   ```

3. **test_stop_price_calculation_formula** - FORMULA CORRECTNESS
   ```python
   @given(
       peak_price=price_decimal(min_value=0.10, max_value=1.00),
       distance=st.decimals(min_value=0.01, max_value=0.30, places=4)
   )
   def test_stop_price_calculation_formula(peak_price, distance):
       """Property: Stop price = peak_price * (1 - distance).

       INVARIANT: stop_price == peak_price * (Decimal("1") - distance)

       Validates the trailing stop calculation is always correct.
       """
   ```

4. **test_peak_price_monotonically_increases** - PEAK TRACKING
   ```python
   @given(
       initial_price=price_decimal(min_value=0.10, max_value=0.90),
       price_movements=st.lists(
           price_decimal(min_value=0.10, max_value=0.90),
           min_size=2,
           max_size=20
       )
   )
   def test_peak_price_monotonically_increases(
       position_manager, initial_price, price_movements
   ):
       """Property: Peak price never decreases.

       INVARIANT: peak_price[i+1] >= peak_price[i]

       Peak represents the highest price ever reached.
       """
   ```

5. **test_stop_always_below_or_equal_peak** - STOP-PEAK RELATIONSHIP
   ```python
   @given(
       initial_price=price_decimal(min_value=0.10, max_value=0.90),
       price_movements=st.lists(
           price_decimal(min_value=0.10, max_value=0.90),
           min_size=1,
           max_size=20
       ),
       distance=st.decimals(min_value=0.01, max_value=0.30, places=4)
   )
   def test_stop_always_below_or_equal_peak(
       position_manager, initial_price, price_movements, distance
   ):
       """Property: Stop price always <= peak price.

       INVARIANT: stop_price <= peak_price (for all time t)

       By definition, stop is distance% below peak.
       """
   ```

**Custom Hypothesis Strategy Needed:**
```python
# tests/property/strategies.py (add this)

@st.composite
def price_decimal(draw, min_value=0.01, max_value=1.00):
    """Generate valid Decimal price values (4 decimal places)."""
    return draw(
        st.decimals(
            min_value=min_value,
            max_value=max_value,
            places=4,
            allow_nan=False,
            allow_infinity=False
        )
    )
```

**Why These 5 Properties?**
- **Property 1 (never loosens):** THE critical invariant - prevents financial losses
- **Property 2 (tightens on increase):** Validates favorable movement logic
- **Property 3 (formula):** Ensures calculation is always correct
- **Property 4 (peak monotonic):** Validates peak tracking logic
- **Property 5 (stop <= peak):** Validates relationship between stop and peak

**Expected Coverage:**
- ~500-1000 test cases generated per property (5000 total)
- Execution time: ~2-3 seconds (all 5 properties)
- Catches edge cases example tests would miss

---

### Config System (`utils/config.py`)

**Unit Tests** (target: ≥85% coverage)
1. `test_load_yaml_config()` - Load all 7 YAML files
2. `test_get_active_strategy_version()` - Resolve active version
3. `test_get_active_model_version()` - Resolve active version
4. `test_get_trailing_stop_config()` - Retrieve stop configuration
5. `test_config_override_priority()` - Environment > YAML > defaults
6. `test_decimal_conversion()` - All prices/probabilities as Decimal
7. `test_missing_yaml_file()` - Handle FileNotFoundError gracefully
8. `test_malformed_yaml()` - Clear error on syntax error
9. `test_nested_yaml_decimals()` - Decimals converted at all nesting levels
10. `test_no_active_version()` - Handle case when all versions deprecated

**Property-Based Tests** (Hypothesis)
- ✅ Already complete! (`tests/property/test_config_validation_properties.py`)
- 14 properties covering kelly_fraction, edge_threshold, fee validation

---

## 3. Test Infrastructure

### Database Schema (Status: ✅ Ready)

**Tables (Already Exist):**
1. **strategies** table:
   - Columns: strategy_id, strategy_name, strategy_version, strategy_type, sport, config (JSONB, IMMUTABLE), status (MUTABLE), paper_roi, live_roi, paper_trades_count, live_trades_count
   - Indexes: idx_strategies_name, idx_strategies_status, idx_strategies_active

2. **probability_models** table:
   - Columns: model_id, model_name, model_version, model_type, sport, config (JSONB, IMMUTABLE), status (MUTABLE), validation_accuracy, validation_calibration, validation_sample_size
   - Indexes: idx_probability_models_name, idx_probability_models_status, idx_probability_models_active

3. **positions** table (with trailing_stop_state):
   - Has: strategy_id, model_id foreign keys (migration 003)
   - Has: trailing_stop_state JSONB column

**No migrations needed** - Schema complete from Phase 0.5

### Test Fixtures (To Be Created)

**1. strategy_factory**
```python
@pytest.fixture
def strategy_factory(db_session):
    """Factory for creating strategy instances in tests."""
    def _create_strategy(
        strategy_name="test_strategy",
        strategy_version="v1.0",
        config=None,
        status="draft"
    ):
        if config is None:
            config = {"min_edge": Decimal("0.05")}
        # Create strategy using Strategy Manager
        # Return strategy object
    return _create_strategy
```

**2. model_factory**
```python
@pytest.fixture
def model_factory(db_session):
    """Factory for creating model instances in tests."""
    def _create_model(
        model_name="test_model",
        model_version="v1.0",
        config=None,
        status="draft"
    ):
        if config is None:
            config = {"k_factor": 28, "initial_rating": 1500}
        # Create model using Model Manager
        # Return model object
    return _create_model
```

**3. position_factory**
```python
@pytest.fixture
def position_factory(db_session):
    """Factory for creating position instances with trailing stops."""
    def _create_position(
        market_id=123,
        position_qty=Decimal("10"),
        position_price=Decimal("0.50"),
        trailing_stop_state=None
    ):
        # Create position using Position Manager
        # Initialize trailing stop state if not provided
        # Return position object
    return _create_position
```

**4. Trailing Stop State Builder**
```python
def build_trailing_stop_state(
    active=True,
    peak_price=Decimal("0.75"),
    current_stop_price=Decimal("0.70"),
    current_distance=Decimal("0.05")
) -> dict:
    """Build valid JSONB trailing stop state.

    Note: All Decimal values converted to strings for JSONB storage.
    """
    return {
        "active": active,
        "peak_price": str(peak_price),
        "current_stop_price": str(current_stop_price),
        "current_distance": str(current_distance)
    }
```

### Reusable Test Helpers

**1. assert_immutable() - Verify config can't be changed**
```python
def assert_immutable(manager, object_id, new_config):
    """Assert that config update raises ImmutabilityError."""
    with pytest.raises(ImmutabilityError):
        manager.update_config(object_id, new_config)
```

**2. assert_decimal_fields() - Verify all prices are Decimal**
```python
def assert_decimal_fields(obj, field_names):
    """Assert that specified fields are Decimal type."""
    for field in field_names:
        value = getattr(obj, field)
        assert isinstance(value, Decimal), f"{field} must be Decimal, got {type(value)}"
```

**3. assert_version_format() - Verify semantic versioning**
```python
def assert_version_format(version_str):
    """Assert version string matches v1.0 or v1.1 format."""
    assert re.match(r"v\d+\.\d+", version_str), f"Invalid version: {version_str}"
```

### Existing Fixtures (Reusable from Phase 1)

- ✅ `db_session` - Database connection fixture
- ✅ `clean_test_data` - Cleanup between tests
- ✅ `mock_kalshi_api` - Mocked Kalshi API responses (if needed)

---

## 4. Critical Test Scenarios

### Strategy Manager - MUST TEST

#### 1. Immutability Enforcement ⚠️ CRITICAL
**Scenario:** Create strategy v1.0 → Attempt to change config → Must FAIL

```python
def test_strategy_config_immutability(strategy_manager, db_session):
    """Verify strategy config cannot be changed after creation."""
    # Create strategy
    strategy = strategy_manager.create_strategy(
        strategy_name="test",
        strategy_version="v1.0",
        config={"min_edge": Decimal("0.05")}
    )

    # Attempt to change config
    with pytest.raises(ImmutabilityError):
        strategy_manager.update_config(
            strategy.strategy_id,
            {"min_edge": Decimal("0.10")}
        )

    # Verify config unchanged
    updated = strategy_manager.get_strategy(strategy.strategy_id)
    assert updated.config["min_edge"] == Decimal("0.05")
```

#### 2. Version Creation
**Scenario:** Create v1.0 → Create v1.1 with different config → Both exist independently

```python
def test_multiple_strategy_versions_coexist(strategy_manager, db_session):
    """Verify multiple versions of same strategy can coexist."""
    # Create v1.0
    v1_0 = strategy_manager.create_strategy(
        strategy_name="test",
        strategy_version="v1.0",
        config={"min_edge": Decimal("0.05")}
    )

    # Create v1.1 with different config
    v1_1 = strategy_manager.create_strategy(
        strategy_name="test",
        strategy_version="v1.1",
        config={"min_edge": Decimal("0.10")}
    )

    # Verify v1.0 unchanged
    v1_0_check = strategy_manager.get_strategy(v1_0.strategy_id)
    assert v1_0_check.config["min_edge"] == Decimal("0.05")

    # Verify v1.1 has new config
    assert v1_1.config["min_edge"] == Decimal("0.10")
```

#### 3. Active Version Lookup
**Scenario:** Multiple versions exist → Only return status='active'

```python
def test_get_active_strategies_filters_correctly(strategy_manager, strategy_factory, db_session):
    """Verify get_active_strategies() returns only active versions."""
    # Create 3 versions with different statuses
    strategy_factory("test", "v1.0", status="deprecated")
    strategy_factory("test", "v1.1", status="active")
    strategy_factory("test", "v2.0", status="testing")

    # Get active strategies
    active = strategy_manager.get_active_strategies()

    # Verify only v1.1 returned
    assert len(active) == 1
    assert active[0].strategy_version == "v1.1"
    assert active[0].status == "active"
```

### Position Manager - MUST TEST

#### 1. Trailing Stop Initialization
**Scenario:** Create position with entry price → Trailing stop state initialized

```python
def test_trailing_stop_initialization(position_manager, db_session):
    """Verify trailing stop state initializes correctly on position creation."""
    position = position_manager.create_position(
        market_id=123,
        position_price=Decimal("0.50"),
        position_qty=Decimal("10")
    )

    state = position.trailing_stop_state
    assert state["active"] == True
    assert Decimal(state["peak_price"]) == Decimal("0.50")
    # Assuming 10% trailing stop distance
    assert Decimal(state["current_stop_price"]) == Decimal("0.45")
    assert Decimal(state["current_distance"]) == Decimal("0.05")
```

#### 2. Trailing Stop Tightens on Favorable Movement ⚠️ CRITICAL
**Scenario:** Price increases → Stop tightens

```python
def test_trailing_stop_tightens_on_favorable_movement(position_manager, position_factory, db_session):
    """Verify trailing stop tightens when price moves favorably."""
    # Create position: price=0.50, stop=0.45
    position = position_factory(position_price=Decimal("0.50"))

    # Price increases to 0.60
    position_manager.update_trailing_stop(
        position.position_id,
        current_price=Decimal("0.60")
    )

    # Verify stop tightened
    updated = position_manager.get_position(position.position_id)
    state = updated.trailing_stop_state
    assert Decimal(state["peak_price"]) == Decimal("0.60")  # Updated
    assert Decimal(state["current_stop_price"]) == Decimal("0.54")  # 10% below new peak
```

#### 3. Trailing Stop NEVER Loosens ⚠️ CRITICAL
**Scenario:** Price decreases → Stop unchanged (one-way ratchet)

```python
def test_trailing_stop_never_loosens(position_manager, position_factory, db_session):
    """Verify trailing stop never loosens (one-way ratchet property)."""
    # Create position at 0.50, update to 0.60 (stop=0.54)
    position = position_factory(position_price=Decimal("0.50"))
    position_manager.update_trailing_stop(position.position_id, Decimal("0.60"))

    # Price drops to 0.55 (unfavorable movement)
    position_manager.update_trailing_stop(
        position.position_id,
        current_price=Decimal("0.55")
    )

    # Verify stop unchanged (did NOT loosen!)
    updated = position_manager.get_position(position.position_id)
    state = updated.trailing_stop_state
    assert Decimal(state["peak_price"]) == Decimal("0.60")  # Unchanged
    assert Decimal(state["current_stop_price"]) == Decimal("0.54")  # Unchanged
```

---

## 5. Edge Cases

### Strategy/Model Manager Edge Cases

1. **Empty Config**
   - Test: `config = {}` → Should fail validation (missing required fields)

2. **Null Config**
   - Test: `config = None` → Should fail (config is NOT NULL in schema)

3. **Very Long Version Strings**
   - Test: `version = "v999.999.999"` → Should work (VARCHAR supports it)

4. **Special Characters in Names**
   - Test: `strategy_name = "test-strategy_v1.0"` → Should work (hyphens, underscores allowed)

5. **Concurrent Version Creation**
   - Test: Two sessions create same (name, version) simultaneously → Only one succeeds (UNIQUE constraint)

6. **Invalid Status Transitions**
   - Test: `deprecated → active` → Should fail (can't reactivate deprecated versions)
   - Test: `active → testing` → Should fail (backwards transition)

7. **Decimal Precision Edge Cases**
   - Test: `config = {"min_edge": "0.123456789"}` → Verify DECIMAL(10,4) precision handling

### Position Manager / Trailing Stops Edge Cases

1. **Zero Price**
   - Test: `position_price = Decimal("0.00")` → Invalid, should fail

2. **Price = 1.00 (Maximum)**
   - Test: `position_price = Decimal("1.00")` → Trailing stop can't tighten above 1.00

3. **Negative Prices**
   - Test: `current_price = Decimal("-0.10")` → Invalid, should fail

4. **Price Exactly at Stop**
   - Test: `current_price == current_stop_price` → Define boundary condition (triggered or not?)

5. **Rapid Price Fluctuations**
   - Test sequence: 0.50 → 0.60 → 0.55 → 0.70 → 0.65
   - Expected stops: 0.45 → 0.54 → 0.54 (no change) → 0.63 → 0.63 (no change)

6. **Inactive Trailing Stop**
   - Test: `trailing_stop_state.active = False` → Updates ignored

7. **Missing JSONB Fields**
   - Test: State missing "peak_price" → ValidationError

8. **Stop Distance = 0**
   - Test: Trailing stop with 0% distance → Stop = peak_price (immediate trigger)

### Config System Edge Cases

1. **Missing YAML File**
   - Test: Load "nonexistent.yaml" → FileNotFoundError with clear message

2. **Malformed YAML**
   - Test: YAML syntax error → yaml.YAMLError with line number

3. **Type Mismatches**
   - Test: `min_edge: "five percent"` (string) → ValidationError

4. **Nested YAML Structures**
   - Test: Deeply nested dicts → All Decimals converted at all levels

5. **Environment Variable Overrides**
   - Test: ENV=0.10, YAML=0.05 → ENV wins (precedence)

6. **No Active Version**
   - Test: Request active strategy when all deprecated → Return None

---

## 6. Success Criteria

### Coverage Targets (MANDATORY)
- ✅ Strategy Manager: ≥85% coverage
- ✅ Model Manager: ≥85% coverage
- ✅ Position Manager: ≥85% coverage
- ✅ Config System: ≥85% coverage
- ✅ Overall Phase 1.5 modules: ≥85% average

### Test Execution (MANDATORY)
- ✅ All unit tests passing (0 failures)
- ✅ All integration tests passing (0 failures)
- ✅ Property-based tests passing (45 tests total: 40 existing + 5 new trailing stop tests, ~9000+ cases)
- ✅ Test suite execution time: <10 seconds (fast feedback loop)

### Functional Requirements (MANDATORY)

**Strategy Manager:**
- ✅ Can create strategy versions (v1.0, v1.1, v2.0)
- ✅ Strategy config is immutable (cannot change after creation)
- ✅ Can update strategy status (draft → testing → active → deprecated)
- ✅ Can update strategy metrics (paper_roi, live_roi) without changing config
- ✅ Can retrieve active strategies (status='active' filter)

**Model Manager:**
- ✅ Can create model versions (v1.0, v1.1, v2.0)
- ✅ Model config is immutable (cannot change after creation)
- ✅ Can update model status (draft → training → validating → active → deprecated)
- ✅ Can update validation metrics (validation_accuracy) without changing config
- ✅ Can retrieve active models (status='active' filter)

**Position Manager:**
- ✅ Trailing stop initializes correctly on position creation
- ✅ Trailing stop tightens on favorable price movement
- ✅ Trailing stop NEVER loosens (one-way ratchet validated)
- ✅ Stop trigger detection works correctly (price < stop_price)
- ✅ JSONB state validates correctly (all required fields present)

**Config System:**
- ✅ All 7 YAML files load successfully
- ✅ Version resolution returns correct active versions
- ✅ Decimal conversion works for all price/probability fields
- ✅ Environment variable overrides work correctly

### Code Quality (MANDATORY)
- ✅ All code passes Ruff linting (0 errors)
- ✅ All code passes Mypy type checking (0 errors)
- ✅ Educational docstrings on all public methods (Pattern 7 from CLAUDE.md)
- ✅ No hardcoded credentials (security scan passes)
- ✅ All prices/probabilities use Decimal (Pattern 1 from CLAUDE.md)

### Documentation (MANDATORY)
- ✅ All requirements marked complete in MASTER_REQUIREMENTS
- ✅ REQUIREMENT_INDEX updated
- ✅ DEVELOPMENT_PHASES Phase 1.5 marked complete
- ✅ Code includes references to relevant REQs and ADRs

### Integration Validation (MANDATORY)
- ✅ End-to-end workflow works: Create strategy → Create model → Create position → Update trailing stop → Check trigger
- ✅ Version attribution works: Edges/trades link to correct strategy_id and model_id
- ✅ Config system integrates with managers (get active versions)

### Performance Baselines (OPTIONAL for Phase 1.5)
- ⚠️ **DEFER to Phase 5+** per CLAUDE.md Section 9 Step 10
- Reason: Manager CRUD operations not performance-critical
- Focus: Correctness, immutability, type safety

### Security (MANDATORY)
- ✅ No SQL injection vulnerabilities (parameterized queries)
- ✅ No hardcoded credentials in manager code
- ✅ JSONB validation prevents injection attacks
- ✅ Input sanitization for all user-provided strings

---

## 7. Test Execution Plan

### Phase 1: Infrastructure Setup (1-2 hours)
1. Create test fixtures (strategy_factory, model_factory, position_factory)
2. Create test helpers (assert_immutable, assert_decimal_fields, assert_version_format)
3. Create JSONB state builder (build_trailing_stop_state)

### Phase 2: Strategy Manager Tests (2-3 hours)
1. Write 10 unit tests (create, version, status, metrics, immutability, etc.)
2. Write 2 integration tests (lifecycle, multiple versions)
3. Run tests, achieve ≥85% coverage

### Phase 3: Model Manager Tests (2-3 hours)
1. Write 10 unit tests (same pattern as strategy manager)
2. Write 2 integration tests
3. Run tests, achieve ≥85% coverage

### Phase 4: Position Manager Tests (3-4 hours)
1. Write 10 unit tests (trailing stop logic)
2. Focus on critical scenarios: never loosens, tightens correctly, trigger detection
3. Run tests, achieve ≥85% coverage

### Phase 5: Trailing Stop Property Tests (2-3 hours) ⚠️ NEW
1. Create `tests/property/test_trailing_stop_properties.py`
2. Add `price_decimal()` strategy to `tests/property/strategies.py`
3. Write 5 property tests:
   - test_trailing_stop_never_loosens (ONE-WAY RATCHET - CRITICAL)
   - test_trailing_stop_tightens_on_price_increase
   - test_stop_price_calculation_formula
   - test_peak_price_monotonically_increases
   - test_stop_always_below_or_equal_peak
4. Run property tests, verify ~5000 cases execute in <3 seconds
5. Validate invariants hold across hundreds of random price sequences

### Phase 6: Config System Tests (1-2 hours)
1. Write 10 unit tests (YAML loading, version resolution, decimal conversion)
2. Test edge cases (missing files, malformed YAML, etc.)
3. Run tests, achieve ≥85% coverage

### Phase 7: Integration Validation (1-2 hours)
1. Write end-to-end workflow tests
2. Test version attribution
3. Test config system integration with managers

### Phase 8: Edge Case Testing (1-2 hours)
1. Test all identified edge cases
2. Verify error handling and validation
3. Document any edge cases deferred to future phases

### Total Estimated Time: 13-21 hours
**Breakdown:**
- Infrastructure: 1-2 hours
- Strategy Manager: 2-3 hours
- Model Manager: 2-3 hours
- Position Manager: 3-4 hours
- **Trailing Stop Properties: 2-3 hours** (NEW)
- Config System: 1-2 hours
- Integration: 1-2 hours
- Edge Cases: 1-2 hours

---

## Test Planning Sign-Off

**Test Planning Complete:** ✅ 2025-11-16
**Approved By:** Claude Code AI Assistant
**Next Step:** Begin Phase 1.5 implementation (create feature branch, implement Strategy Manager)

**Critical Reminder:**
⚠️ **DO NOT write production code until all test planning tasks complete!** (CLAUDE.md mandate)

---

**END OF PHASE_1.5_TEST_PLAN_V1.0.md**
