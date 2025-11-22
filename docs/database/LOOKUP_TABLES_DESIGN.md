# Lookup Tables Design - Strategy Types & Model Classes

---
**Version:** 1.0
**Created:** 2025-11-21
**Status:** 🔵 Planned
**Purpose:** Replace CHECK constraints with lookup tables for strategy_type and model_class
**Migrations:** 021 (strategies.approach→strategy_type), 022 (probability_models.approach→model_class), 023 (create lookup tables)

---

## 1. Rationale

**Problem with CHECK Constraints:**
- Adding new values requires migrations
- No metadata storage (descriptions, categories)
- Not UI-friendly (values hardcoded in constraint)
- Limited flexibility (can't disable values, add fields)

**Solution: Lookup Tables**
- Add values via INSERT (no migration)
- Store rich metadata (display_name, description, category)
- Query for UI dropdowns: `SELECT * FROM strategy_types WHERE is_active = TRUE ORDER BY display_order`
- Extensible: Add tags, icons, help_text without schema changes

---

## 2. Schema Design

### 2.1 strategy_types Lookup Table

```sql
CREATE TABLE strategy_types (
    strategy_type_code VARCHAR(50) PRIMARY KEY,  -- 'value', 'arbitrage', 'momentum', 'mean_reversion'
    display_name VARCHAR(100) NOT NULL,          -- 'Value Trading', 'Arbitrage'
    description TEXT NOT NULL,                   -- 'Exploit market mispricing by identifying...'
    category VARCHAR(50) NOT NULL,               -- 'directional', 'arbitrage', 'risk_management'
    is_active BOOLEAN DEFAULT TRUE NOT NULL,     -- Allow disabling without deleting
    display_order INT DEFAULT 999 NOT NULL,      -- UI sort order (lower = first)
    icon_name VARCHAR(50),                       -- Icon identifier for UI (optional)
    help_text TEXT,                              -- Extended help for UI tooltips (optional)
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_strategy_types_active ON strategy_types(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_strategy_types_category ON strategy_types(category);
CREATE INDEX idx_strategy_types_order ON strategy_types(display_order);
```

**Categories for strategy_type:**
- `directional` - Strategies that take directional bets (value, momentum, mean_reversion, contrarian)
- `arbitrage` - Exploit price differences (arbitrage, cross_platform, cross_market)
- `risk_management` - Hedging and risk reduction (hedging, stop_loss, portfolio_balance)
- `event_driven` - News/event-based (event_driven, catalyst, sentiment)

### 2.2 model_classes Lookup Table

```sql
CREATE TABLE model_classes (
    model_class_code VARCHAR(50) PRIMARY KEY,   -- 'elo', 'ensemble', 'ml', 'neural_net', etc.
    display_name VARCHAR(100) NOT NULL,         -- 'Elo Rating System', 'Neural Network'
    description TEXT NOT NULL,                  -- 'Elo rating system based on...'
    category VARCHAR(50) NOT NULL,              -- 'statistical', 'machine_learning', 'hybrid', 'baseline'
    complexity_level VARCHAR(20) NOT NULL,      -- 'simple', 'moderate', 'advanced'
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    display_order INT DEFAULT 999 NOT NULL,
    icon_name VARCHAR(50),                      -- Icon identifier for UI (optional)
    help_text TEXT,                             -- Extended help for UI tooltips (optional)
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_model_classes_active ON model_classes(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_model_classes_category ON model_classes(category);
CREATE INDEX idx_model_classes_complexity ON model_classes(complexity_level);
CREATE INDEX idx_model_classes_order ON model_classes(display_order);
```

**Categories for model_class:**
- `statistical` - Statistical methods (elo, regression, poisson)
- `machine_learning` - ML algorithms (ml, neural_net, random_forest, xgboost)
- `hybrid` - Combines multiple approaches (hybrid, ensemble)
- `baseline` - Simple benchmarks (baseline, market_consensus, random)

**Complexity Levels:**
- `simple` - Easy to understand/implement (elo, baseline)
- `moderate` - Requires some expertise (regression, ensemble)
- `advanced` - Complex algorithms (neural_net, xgboost)

---

## 3. Migration Plan

### Migration 023: Create Lookup Tables and Migrate Constraints

**Step 1: Create lookup tables**
- `CREATE TABLE strategy_types`
- `CREATE TABLE model_classes`

**Step 2: Seed with existing values**

**strategy_types (4 initial values):**
```sql
INSERT INTO strategy_types (strategy_type_code, display_name, description, category, display_order) VALUES
('value', 'Value Trading', 'Exploit market mispricing by identifying edges where true probability exceeds market price', 'directional', 10),
('arbitrage', 'Arbitrage', 'Cross-platform arbitrage opportunities with identical event outcomes priced differently', 'arbitrage', 20),
('momentum', 'Momentum Trading', 'Trend following strategies that capitalize on sustained price movements', 'directional', 30),
('mean_reversion', 'Mean Reversion', 'Capitalize on temporary deviations from fundamental value', 'directional', 40);
```

**model_classes (7 initial values):**
```sql
INSERT INTO model_classes (model_class_code, display_name, description, category, complexity_level, display_order) VALUES
('elo', 'Elo Rating System', 'Dynamic rating system tracking team/competitor strength over time', 'statistical', 'simple', 10),
('ensemble', 'Ensemble Model', 'Weighted combination of multiple models for robust predictions', 'hybrid', 'moderate', 20),
('ml', 'Machine Learning', 'General machine learning algorithms (decision trees, SVM, etc.)', 'machine_learning', 'moderate', 30),
('hybrid', 'Hybrid Approach', 'Combines multiple modeling approaches (statistical + ML)', 'hybrid', 'moderate', 40),
('regression', 'Statistical Regression', 'Linear/logistic regression with feature engineering', 'statistical', 'simple', 50),
('neural_net', 'Neural Network', 'Deep learning models with multiple hidden layers', 'machine_learning', 'advanced', 60),
('baseline', 'Baseline Model', 'Simple heuristic for benchmarking (moving average, market consensus)', 'baseline', 'simple', 70);
```

**Step 3: Drop CHECK constraints**
```sql
ALTER TABLE strategies DROP CONSTRAINT strategies_strategy_type_check;
ALTER TABLE probability_models DROP CONSTRAINT probability_models_model_class_check;
```

**Step 4: Add foreign key constraints**
```sql
ALTER TABLE strategies
    ADD CONSTRAINT fk_strategies_strategy_type
    FOREIGN KEY (strategy_type)
    REFERENCES strategy_types(strategy_type_code);

ALTER TABLE probability_models
    ADD CONSTRAINT fk_probability_models_model_class
    FOREIGN KEY (model_class)
    REFERENCES model_classes(model_class_code);
```

**Step 5: Create indexes on FK columns (if not exist)**
```sql
CREATE INDEX IF NOT EXISTS idx_strategies_strategy_type ON strategies(strategy_type);
CREATE INDEX IF NOT EXISTS idx_probability_models_model_class ON probability_models(model_class);
```

**Migration Safe:** YES
- Lookup tables created with existing values before dropping constraints
- No data loss (FK constraint validates existing data)
- Rollback: Drop FK, recreate CHECK constraints

**Estimated Time:** ~500ms (metadata operations + 11 row inserts)

---

## 4. Future Extensibility Examples

### Adding New Strategy Types (No Migration!)

```sql
-- Add hedging strategy (Phase 2)
INSERT INTO strategy_types (strategy_type_code, display_name, description, category, display_order)
VALUES ('hedging', 'Hedging Strategy', 'Risk management through offsetting positions', 'risk_management', 50);

-- Add contrarian strategy (Phase 3)
INSERT INTO strategy_types (strategy_type_code, display_name, description, category, display_order)
VALUES ('contrarian', 'Contrarian Trading', 'Fade public sentiment when market overreacts', 'directional', 45);
```

### Adding New Model Classes (No Migration!)

```sql
-- Add XGBoost model (Phase 4)
INSERT INTO model_classes (model_class_code, display_name, description, category, complexity_level, display_order)
VALUES ('xgboost', 'XGBoost', 'Gradient boosting decision trees with regularization', 'machine_learning', 'advanced', 65);

-- Add market consensus baseline (Phase 2)
INSERT INTO model_classes (model_class_code, display_name, description, category, complexity_level, display_order)
VALUES ('market_consensus', 'Market Consensus', 'Aggregate market prices as probability estimate', 'baseline', 'simple', 75);
```

### Disabling Values (No Deletion!)

```sql
-- Disable deprecated strategy type
UPDATE strategy_types
SET is_active = FALSE, updated_at = NOW()
WHERE strategy_type_code = 'momentum';
```

### Adding Metadata Fields (Migration, but existing data unaffected)

```sql
-- Add tags for filtering (Phase 5)
ALTER TABLE strategy_types ADD COLUMN tags TEXT[];

-- Add risk level (Phase 5)
ALTER TABLE model_classes ADD COLUMN risk_level VARCHAR(20);  -- 'low', 'medium', 'high'
```

---

## 5. UI Integration Examples

### Dropdown Population

```python
# Fetch active strategy types for UI dropdown
def get_strategy_type_options():
    query = """
        SELECT strategy_type_code, display_name, description, category
        FROM strategy_types
        WHERE is_active = TRUE
        ORDER BY display_order
    """
    return fetch_all(query)

# Result:
# [
#   {'strategy_type_code': 'value', 'display_name': 'Value Trading', 'description': '...', 'category': 'directional'},
#   {'strategy_type_code': 'arbitrage', 'display_name': 'Arbitrage', 'description': '...', 'category': 'arbitrage'},
#   ...
# ]
```

### Category Grouping

```python
# Group by category for organized UI
def get_strategy_types_by_category():
    query = """
        SELECT category, json_agg(
            json_build_object(
                'code', strategy_type_code,
                'name', display_name,
                'description', description
            ) ORDER BY display_order
        ) as strategies
        FROM strategy_types
        WHERE is_active = TRUE
        GROUP BY category
        ORDER BY category
    """
    return fetch_all(query)

# Result:
# [
#   {'category': 'arbitrage', 'strategies': [{'code': 'arbitrage', 'name': 'Arbitrage', ...}]},
#   {'category': 'directional', 'strategies': [{'code': 'value', ...}, {'code': 'momentum', ...}]}
# ]
```

---

## 6. Code Changes Required

### 6.1 StrategyManager (Minimal Changes)

**Before (with CHECK constraint):**
```python
# Validation in docstring only
def create_strategy(self, strategy_type: str, ...):
    """
    Args:
        strategy_type: MUST be one of: 'value', 'arbitrage', 'momentum', 'mean_reversion'
    """
```

**After (with lookup table):**
```python
def create_strategy(self, strategy_type: str, ...):
    """
    Args:
        strategy_type: Valid strategy type code from strategy_types table

    Raises:
        psycopg2.ForeignKeyViolation: If strategy_type is not in strategy_types table
    """
    # Optional: Add validation method for better error messages
    if not self._is_valid_strategy_type(strategy_type):
        raise ValueError(
            f"Invalid strategy_type '{strategy_type}'. "
            f"Valid types: {self._get_valid_strategy_types()}"
        )

def _is_valid_strategy_type(self, strategy_type: str) -> bool:
    query = "SELECT EXISTS(SELECT 1 FROM strategy_types WHERE strategy_type_code = %s AND is_active = TRUE)"
    result = fetch_one(query, (strategy_type,))
    return result[0] if result else False

def _get_valid_strategy_types(self) -> list[str]:
    query = "SELECT strategy_type_code FROM strategy_types WHERE is_active = TRUE ORDER BY display_order"
    return [row[0] for row in fetch_all(query)]
```

### 6.2 ModelManager (Similar Changes)

```python
def create_model(self, model_class: str, ...):
    """
    Args:
        model_class: Valid model class code from model_classes table

    Raises:
        psycopg2.ForeignKeyViolation: If model_class is not in model_classes table
    """
```

### 6.3 New Helper Module (Optional)

```python
# src/precog/database/lookup_helpers.py
"""Helper functions for lookup table validation."""

def get_strategy_types(active_only: bool = True) -> list[dict]:
    """Get all strategy types with metadata."""
    where_clause = "WHERE is_active = TRUE" if active_only else ""
    query = f"""
        SELECT strategy_type_code, display_name, description, category, display_order
        FROM strategy_types
        {where_clause}
        ORDER BY display_order
    """
    return fetch_all(query)

def get_model_classes(active_only: bool = True) -> list[dict]:
    """Get all model classes with metadata."""
    where_clause = "WHERE is_active = TRUE" if active_only else ""
    query = f"""
        SELECT model_class_code, display_name, description, category, complexity_level, display_order
        FROM model_classes
        {where_clause}
        ORDER BY display_order
    """
    return fetch_all(query)

def validate_strategy_type(strategy_type: str) -> bool:
    """Check if strategy_type is valid and active."""
    query = "SELECT EXISTS(SELECT 1 FROM strategy_types WHERE strategy_type_code = %s AND is_active = TRUE)"
    result = fetch_one(query, (strategy_type,))
    return result[0] if result else False

def validate_model_class(model_class: str) -> bool:
    """Check if model_class is valid and active."""
    query = "SELECT EXISTS(SELECT 1 FROM model_classes WHERE model_class_code = %s AND is_active = TRUE)"
    result = fetch_one(query, (model_class,))
    return result[0] if result else False
```

---

## 7. Documentation Updates Required

### 7.1 DATABASE_SCHEMA_SUMMARY_V1.10 → V1.11
- Add Section 2.X: Lookup Tables (strategy_types, model_classes)
- Update strategies table documentation (CHECK → FK)
- Update probability_models table documentation (CHECK → FK)

### 7.2 MASTER_REQUIREMENTS
- Add REQ-DB-015: Strategy Type Lookup Table
- Add REQ-DB-016: Model Class Lookup Table

### 7.3 ARCHITECTURE_DECISIONS
- Add ADR-093: Lookup Tables for Business Enums

---

## 8. Testing Requirements

### 8.1 Lookup Table Tests

```python
def test_strategy_types_table_contains_all_initial_values():
    """Verify all 4 initial strategy types exist."""
    query = "SELECT strategy_type_code FROM strategy_types ORDER BY display_order"
    result = fetch_all(query)
    codes = [row[0] for row in result]

    assert codes == ['value', 'arbitrage', 'momentum', 'mean_reversion']

def test_model_classes_table_contains_all_initial_values():
    """Verify all 7 initial model classes exist."""
    query = "SELECT model_class_code FROM model_classes ORDER BY display_order"
    result = fetch_all(query)
    codes = [row[0] for row in result]

    assert codes == ['elo', 'ensemble', 'ml', 'hybrid', 'regression', 'neural_net', 'baseline']

def test_invalid_strategy_type_raises_foreign_key_error():
    """Verify FK constraint prevents invalid strategy_type."""
    manager = StrategyManager()

    with pytest.raises(psycopg2.ForeignKeyViolation):
        manager.create_strategy(
            strategy_name='test',
            strategy_version='v1.0',
            strategy_type='invalid_type',  # ← Not in lookup table
            config={'test': True}
        )
```

### 8.2 Integration Tests

```python
def test_create_strategy_with_all_valid_types():
    """Test creating strategies with each valid strategy_type."""
    manager = StrategyManager()

    for strategy_type in ['value', 'arbitrage', 'momentum', 'mean_reversion']:
        strategy = manager.create_strategy(
            strategy_name=f'test_{strategy_type}',
            strategy_version='v1.0',
            strategy_type=strategy_type,
            domain='nfl',
            config={'test': True}
        )
        assert strategy['strategy_type'] == strategy_type
```

---

## 9. Rollback Plan

```sql
-- Migration 023 Rollback

-- Step 1: Recreate CHECK constraints
ALTER TABLE strategies
    ADD CONSTRAINT strategies_strategy_type_check
    CHECK (strategy_type IN ('value', 'arbitrage', 'momentum', 'mean_reversion'));

ALTER TABLE probability_models
    ADD CONSTRAINT probability_models_model_class_check
    CHECK (model_class IN ('elo', 'ensemble', 'ml', 'hybrid', 'regression', 'neural_net', 'baseline'));

-- Step 2: Drop foreign key constraints
ALTER TABLE strategies DROP CONSTRAINT fk_strategies_strategy_type;
ALTER TABLE probability_models DROP CONSTRAINT fk_probability_models_model_class;

-- Step 3: Drop lookup tables
DROP TABLE strategy_types;
DROP TABLE model_classes;
```

---

## 10. Summary

**Benefits:**
- ✅ Add new values via INSERT (no migration)
- ✅ Store rich metadata (descriptions, categories, help text)
- ✅ UI-friendly (query for dropdowns)
- ✅ Extensible (add fields without schema changes)
- ✅ Better error messages (FK violation includes table name)

**Tradeoffs:**
- ⚠️ Slightly more complex (FK instead of CHECK)
- ⚠️ Two more tables to maintain
- ⚠️ Join overhead (negligible - tiny tables with indexes)

**Implementation Effort:**
- Migration: ~1 hour (schema + seeds + tests)
- Code updates: ~2 hours (StrategyManager, ModelManager, helper module)
- Documentation: ~1 hour (DATABASE_SCHEMA_SUMMARY, ADR, REQ)
- Testing: ~1 hour (lookup tests, integration tests)
- **Total: ~5 hours**

**Recommendation:** ✅ Implement in Phase 1.5 (foundation validation)

---

**END OF LOOKUP_TABLES_DESIGN.md**
