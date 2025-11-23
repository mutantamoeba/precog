# Model Manager User Guide

---
**Version:** 1.0
**Created:** 2025-11-22
**Target Audience:** Developers implementing probability models for Precog
**Purpose:** Comprehensive guide to using Model Manager for creating, versioning, and managing probability models
**Related Guides:** STRATEGY_MANAGER_USER_GUIDE_V1.0.md, VERSIONING_GUIDE_V1.0.md

---

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Quick Start](#quick-start)
4. [Complete API Reference](#complete-api-reference)
5. [Configuration Structure](#configuration-structure)
6. [Lifecycle Management](#lifecycle-management)
7. [A/B Testing Workflows](#ab-testing-workflows)
8. [Validation & Calibration](#validation--calibration)
9. [Common Patterns](#common-patterns)
10. [Troubleshooting](#troubleshooting)
11. [Advanced Topics](#advanced-topics)
12. [References](#references)

---

## Overview

### What is Model Manager?

**Model Manager** is the core service for managing probability models in Precog. It handles creating, versioning, updating, and querying ML models that predict event probabilities.

**File:** `src/precog/analytics/model_manager.py` (738 lines)

### Why Use Model Manager?

**Problem Without Model Manager:**
```python
# ❌ WRONG: Direct database manipulation
cursor.execute("""
    INSERT INTO probability_models (model_name, config)
    VALUES ('elo_nfl', '{"k_factor": 32.0}')
""")
# Problems:
# - Floats in config (violates Pattern 1)
# - No versioning (can't track improvements)
# - No validation (invalid model_class accepted)
# - No calibration tracking
```

**Solution With Model Manager:**
```python
# ✅ CORRECT: Managed model lifecycle
from precog.analytics.model_manager import ModelManager
from decimal import Decimal

manager = ModelManager()

model = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    model_class="elo",
    config={
        "k_factor": Decimal("32.0"),
        "home_advantage": Decimal("55.0"),
        "mean_reversion": Decimal("0.33")
    },
    domain="nfl"
)
# Benefits:
# - Decimal precision enforced ✅
# - Immutable versioning for A/B testing ✅
# - FK validation (model_class must exist) ✅
# - Calibration metrics tracked separately ✅
```

### Key Features

1. **Immutable Versioning** - Model configs frozen after creation, changes require new version
2. **Semantic Versioning** - v1.0 → v1.1 (parameter tune) vs v1.0 → v2.0 (algorithm change)
3. **Status Lifecycle** - draft → testing → active → deprecated
4. **Model Class Validation** - FK constraint to `model_classes` lookup table
5. **Calibration Tracking** - Separate mutable metrics (accuracy, calibration, sample size)
6. **A/B Testing Support** - Multiple versions active simultaneously
7. **Decimal Precision** - All probabilities use `Decimal` type (Pattern 1)
8. **Type Safety** - TypedDict return types with compile-time checking

---

## Core Concepts

### 1. Immutable vs Mutable Fields

**IMMUTABLE (Cannot change after creation):**
- `model_name` - Model identifier (e.g., 'elo_nfl', 'logistic_nba')
- `model_version` - Semantic version (e.g., 'v1.0', 'v2.1')
- `model_class` - Algorithm type ('elo', 'logistic', 'ensemble', 'xgboost')
- `config` - Model parameters (JSONB dictionary)
- `domain` - Target markets ('nfl', 'nba', 'politics', etc.)
- `created_at` - Creation timestamp

**MUTABLE (Can change):**
- `status` - Lifecycle state ('draft', 'testing', 'active', 'deprecated')
- `description` - Human-readable explanation
- `notes` - Development notes, rationale
- `validation_calibration` - Calibration score (0.0-1.0, 1.0 = perfect)
- `validation_accuracy` - Prediction accuracy (0.0-1.0)
- `validation_sample_size` - Number of predictions evaluated
- `last_validated_at` - Last validation timestamp

**Why This Separation?**

```python
# ❌ WRONG: Modifying config breaks A/B testing
model = manager.get_model(model_id=42)
model['config']['k_factor'] = Decimal("40.0")  # Changes old version!
# Problem: Now we don't know which predictions came from k=32 vs k=40

# ✅ CORRECT: Create new version for config changes
v1_1 = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.1",  # New version
    model_class="elo",
    config={"k_factor": Decimal("40.0")},  # New config
    domain="nfl"
)
# Benefit: v1.0 predictions still traceable to k=32 config
```

### 2. Semantic Versioning

**Major Version (v1.0 → v2.0):**
- Algorithm change (Elo → Logistic Regression)
- Feature set change (add injuries, weather)
- Model architecture change (single model → ensemble)

**Minor Version (v1.0 → v1.1):**
- Parameter tuning (k_factor: 32 → 40)
- Hyperparameter optimization (learning rate adjustment)
- Small feature tweaks (add home field advantage)

**Patch Version (v1.0.0 → v1.0.1):**
- Bug fixes (incorrect calculation)
- Code refactoring (no behavior change)

**Examples:**
```python
# Major version: Algorithm change
v1_0 = manager.create_model(
    model_name="nfl_win_prob",
    model_version="v1.0",
    model_class="elo",  # Elo algorithm
    config={"k_factor": Decimal("32.0")}
)

v2_0 = manager.create_model(
    model_name="nfl_win_prob",
    model_version="v2.0",
    model_class="logistic",  # Different algorithm!
    config={"learning_rate": Decimal("0.01")}
)

# Minor version: Parameter tuning
v1_1 = manager.create_model(
    model_name="nfl_win_prob",
    model_version="v1.1",
    model_class="elo",  # Same algorithm
    config={"k_factor": Decimal("40.0")}  # Different parameter
)
```

### 3. Status Lifecycle

**State Machine:**
```
draft → testing → active → deprecated
  ↑         ↓
  └─────────┘ (can revert testing → draft)
```

**Status Definitions:**
- **draft**: Under development, not ready for predictions
- **testing**: Backtesting or paper trading (no real capital)
- **active**: Live predictions, used in production
- **deprecated**: Replaced by newer version, retained for audit

**Valid Transitions:**
```python
# Forward progression
"draft" → "testing" → "active" → "deprecated"

# Revert during testing
"testing" → "draft"  # Found bugs, back to development

# Invalid transitions
"deprecated" → *  # Terminal state, cannot reactivate
"active" → "testing"  # Cannot demote to testing (create new version instead)
```

### 4. Model Classes

**Lookup Table:** `model_classes` (Migration 023)

**Standard Model Classes:**
- **elo**: Elo rating system (chess-style ratings)
- **logistic**: Logistic regression (linear classifier)
- **ensemble**: Ensemble model (combines multiple models)
- **xgboost**: XGBoost gradient boosting (tree-based)
- **random_forest**: Random forest (tree ensemble)
- **neural_network**: Deep learning model (neural nets)

**Adding New Model Class:**
```sql
-- Migration file (e.g., Migration 024)
INSERT INTO model_classes (model_class, description) VALUES
    ('lightgbm', 'LightGBM gradient boosting (faster than XGBoost)'),
    ('prophet', 'Facebook Prophet time series model');
```

**Foreign Key Validation:**
```python
# ✅ Valid: model_class exists in lookup table
model = manager.create_model(
    model_class="elo",  # Exists in model_classes table
    ...
)

# ❌ Invalid: model_class not in lookup table
model = manager.create_model(
    model_class="custom_algo",  # FK constraint violation!
    ...
)
# Raises: psycopg2.errors.ForeignKeyViolation
```

---

## Quick Start

### Installation

```python
from precog.analytics.model_manager import ModelManager
from precog.database.connection import get_connection, release_connection
from decimal import Decimal
```

### Create Your First Model

```python
# 1. Initialize manager
manager = ModelManager()

# 2. Create Elo model for NFL
model = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    model_class="elo",
    config={
        "k_factor": Decimal("32.0"),        # Rating change per game
        "home_advantage": Decimal("55.0"),   # Home team Elo boost
        "mean_reversion": Decimal("0.33")    # Regression to mean (off-season)
    },
    domain="nfl",
    description="NFL Elo model with home field advantage",
    status="draft"
)

print(f"Created model: {model['model_name']} {model['model_version']}")
print(f"Model ID: {model['model_id']}")
print(f"Config: {model['config']}")
```

**Output:**
```
Created model: elo_nfl v1.0
Model ID: 1
Config: {'k_factor': Decimal('32.0'), 'home_advantage': Decimal('55.0'), 'mean_reversion': Decimal('0.33')}
```

### Progress Model to Testing

```python
# 3. Update status: draft → testing
testing_model = manager.update_status(
    model_id=model['model_id'],
    new_status="testing",
    notes="Starting backtest on 2023 NFL season (272 games)"
)

print(f"Status: {testing_model['status']}")
```

### Record Validation Metrics

```python
# 4. After backtesting, record calibration metrics
validated_model = manager.update_metrics(
    model_id=model['model_id'],
    validation_calibration=Decimal("0.92"),  # 92% calibrated
    validation_accuracy=Decimal("0.67"),      # 67% accuracy
    validation_sample_size=272                 # 272 predictions
)

print(f"Calibration: {validated_model['validation_calibration']}")
print(f"Accuracy: {validated_model['validation_accuracy']}")
print(f"Sample Size: {validated_model['validation_sample_size']}")
```

### Activate for Production

```python
# 5. Metrics look good, activate for live predictions
active_model = manager.update_status(
    model_id=model['model_id'],
    new_status="active",
    notes="Calibration 92%, accuracy 67%, sample size 272. Approved for production."
)

print(f"Status: {active_model['status']}")
print(f"Last validated: {active_model['last_validated_at']}")
```

---

## Complete API Reference

### Method 1: `create_model()`

**Create new model version with immutable configuration.**

```python
def create_model(
    self,
    model_name: str,
    model_version: str,
    model_class: str,
    config: dict[str, Any],
    domain: str | None = None,
    description: str | None = None,
    status: str = "draft",
    created_by: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
```

**Parameters:**
- `model_name` (str): Model identifier (e.g., 'elo_nfl', 'logistic_nba')
- `model_version` (str): Semantic version (e.g., 'v1.0', 'v1.1')
- `model_class` (str): FK to `model_classes` table ('elo', 'logistic', 'ensemble', 'xgboost', etc.)
- `config` (dict): Model parameters using Decimal for all numeric values (IMMUTABLE!)
- `domain` (str | None): Target markets ('nfl', 'nba', 'politics', etc.) or None for multi-domain
- `description` (str | None): Human-readable explanation
- `status` (str): Initial status ('draft', 'testing', 'active'). Default: 'draft'
- `created_by` (str | None): Creator identifier
- `notes` (str | None): Development notes, rationale

**Returns:**
- Dict with all model fields including generated `model_id`

**Raises:**
- `psycopg2.IntegrityError`: If `model_name` + `model_version` already exists (UNIQUE constraint)
- `psycopg2.ForeignKeyViolation`: If `model_class` not in `model_classes` lookup table
- `ValueError`: If config is empty or contains float values

**Example:**
```python
model = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    model_class="elo",
    config={
        "k_factor": Decimal("32.0"),
        "home_advantage": Decimal("55.0"),
        "mean_reversion": Decimal("0.33")
    },
    domain="nfl",
    description="NFL Elo model with home field advantage",
    status="draft",
    created_by="data_science_team",
    notes="Initial implementation using chess Elo algorithm"
)
```

---

### Method 2: `get_model()`

**Retrieve model by ID or name + version.**

```python
def get_model(
    self,
    model_id: int | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
) -> dict[str, Any] | None:
```

**Parameters:**
- `model_id` (int | None): Surrogate key (primary key)
- `model_name` (str | None): Model identifier (required if `model_id` not provided)
- `model_version` (str | None): Semantic version (required if `model_id` not provided)

**Returns:**
- Model dict if found, None if not found

**Raises:**
- `ValueError`: If neither (`model_id`) nor (`model_name` + `model_version`) provided

**Example:**
```python
# Retrieve by ID
model = manager.get_model(model_id=42)

# Retrieve by name + version
model = manager.get_model(
    model_name="elo_nfl",
    model_version="v1.0"
)

# Check if model exists
if model is None:
    print("Model not found")
else:
    print(f"Found: {model['model_name']} {model['model_version']}")
```

---

### Method 3: `get_active_models()`

**Retrieve all models with status='active'.**

```python
def get_active_models(
    self,
    domain: str | None = None,
) -> list[dict[str, Any]]:
```

**Parameters:**
- `domain` (str | None): Filter by domain ('nfl', 'nba', etc.). If None, returns all active models.

**Returns:**
- List of active model dicts (may be empty)

**Example:**
```python
# Get all active models
all_active = manager.get_active_models()
print(f"Active models: {len(all_active)}")

# Get active NFL models only
nfl_active = manager.get_active_models(domain="nfl")
for model in nfl_active:
    print(f"- {model['model_name']} {model['model_version']}")
```

---

### Method 4: `update_status()`

**Update model status (draft → testing → active → deprecated).**

```python
def update_status(
    self,
    model_id: int,
    new_status: str,
    notes: str | None = None,
) -> dict[str, Any]:
```

**Parameters:**
- `model_id` (int): Surrogate key
- `new_status` (str): Target status ('draft', 'testing', 'active', 'deprecated')
- `notes` (str | None): Reason for status change

**Returns:**
- Updated model dict

**Raises:**
- `InvalidStatusTransitionError`: If transition not allowed (e.g., 'deprecated' → 'active')
- `psycopg2.errors.InvalidParameterValue`: If status not in CHECK constraint

**Valid Transitions:**
```python
# Forward progression
"draft" → "testing" → "active" → "deprecated"

# Revert during testing
"testing" → "draft"

# Invalid
"deprecated" → *  # Terminal state
"active" → "testing"  # Cannot demote
```

**Example:**
```python
# Progress: draft → testing
model = manager.update_status(
    model_id=42,
    new_status="testing",
    notes="Starting backtest on 2023 season"
)

# Activate after successful testing
model = manager.update_status(
    model_id=42,
    new_status="active",
    notes="Backtest complete. Calibration: 92%, Accuracy: 67%"
)

# Deprecate when replaced
model = manager.update_status(
    model_id=42,
    new_status="deprecated",
    notes="Replaced by v2.0 with improved feature set"
)
```

---

### Method 5: `update_metrics()`

**Update validation metrics (calibration, accuracy, sample size).**

```python
def update_metrics(
    self,
    model_id: int,
    validation_calibration: Decimal | None = None,
    validation_accuracy: Decimal | None = None,
    validation_sample_size: int | None = None,
) -> dict[str, Any]:
```

**Parameters:**
- `model_id` (int): Surrogate key
- `validation_calibration` (Decimal | None): Calibration score (0.0-1.0, 1.0 = perfect)
- `validation_accuracy` (Decimal | None): Prediction accuracy (0.0-1.0)
- `validation_sample_size` (int | None): Number of predictions evaluated

**Returns:**
- Updated model dict with new metrics and `last_validated_at` timestamp

**Metric Definitions:**
- **Calibration**: Agreement between predicted probabilities and observed frequencies
  - Example: If model predicts 70% win probability 100 times, team should win ~70 times
  - Score 1.0 = perfect calibration, 0.0 = worst possible
- **Accuracy**: Percentage of correct predictions (winner correctly predicted)
  - Example: 67% accuracy = predicted winner was correct 67% of the time
- **Sample Size**: Number of predictions used for validation

**Example:**
```python
# After backtesting on 272 NFL games
model = manager.update_metrics(
    model_id=42,
    validation_calibration=Decimal("0.92"),  # 92% calibrated
    validation_accuracy=Decimal("0.67"),      # 67% accuracy
    validation_sample_size=272
)

print(f"Calibration: {model['validation_calibration']}")
print(f"Accuracy: {model['validation_accuracy']}")
print(f"Sample Size: {model['validation_sample_size']}")
print(f"Last Validated: {model['last_validated_at']}")
```

---

### Method 6: `list_model_versions()`

**List all versions of a specific model.**

```python
def list_model_versions(
    self,
    model_name: str,
) -> list[dict[str, Any]]:
```

**Parameters:**
- `model_name` (str): Model identifier

**Returns:**
- List of model dicts (all versions), ordered by creation date

**Example:**
```python
versions = manager.list_model_versions(model_name="elo_nfl")

print(f"Model: elo_nfl")
print(f"Versions: {len(versions)}")
for v in versions:
    print(f"- {v['model_version']}: {v['status']} (calibration: {v['validation_calibration']})")
```

**Output:**
```
Model: elo_nfl
Versions: 3
- v1.0: deprecated (calibration: 0.89)
- v1.1: active (calibration: 0.92)
- v2.0: testing (calibration: None)
```

---

## Configuration Structure

### Recommended Config Schema

**Decimal Precision (CRITICAL):**
```python
# ✅ CORRECT: All numeric values as Decimal
config = {
    "k_factor": Decimal("32.0"),
    "home_advantage": Decimal("55.0"),
    "mean_reversion": Decimal("0.33"),
    "max_rating": Decimal("2500.0"),
    "min_rating": Decimal("1000.0")
}

# ❌ WRONG: Float values
config = {
    "k_factor": 32.0,  # Float not allowed!
    "home_advantage": 55.0,
    "mean_reversion": 0.33
}
# Raises: ValueError from manager validation
```

### Example Configs by Model Class

**Elo Model:**
```python
config = {
    "k_factor": Decimal("32.0"),        # Rating change per game
    "home_advantage": Decimal("55.0"),   # Home team Elo boost
    "mean_reversion": Decimal("0.33"),   # Off-season regression
    "initial_rating": Decimal("1500.0")  # Starting Elo for new teams
}
```

**Logistic Regression:**
```python
config = {
    "learning_rate": Decimal("0.01"),
    "max_iterations": 1000,
    "regularization": Decimal("0.001"),
    "feature_list": ["elo_rating", "home_away", "rest_days", "injuries"]
}
```

**Ensemble Model:**
```python
config = {
    "models": [
        {"model_name": "elo_nfl", "weight": Decimal("0.40")},
        {"model_name": "logistic_nfl", "weight": Decimal("0.35")},
        {"model_name": "xgboost_nfl", "weight": Decimal("0.25")}
    ],
    "aggregation_method": "weighted_average"
}
```

**XGBoost:**
```python
config = {
    "n_estimators": 100,
    "max_depth": 6,
    "learning_rate": Decimal("0.1"),
    "subsample": Decimal("0.8"),
    "colsample_bytree": Decimal("0.8"),
    "min_child_weight": 1,
    "gamma": Decimal("0.0")
}
```

### Validation Best Practices

**Three-Layer Validation:**

1. **Database Layer (PostgreSQL enforces):**
   - `model_name` NOT NULL
   - `model_version` NOT NULL
   - UNIQUE constraint on (`model_name`, `model_version`)
   - FK constraint: `model_class` must exist in `model_classes` table
   - CHECK constraint: `status` IN ('draft', 'testing', 'active', 'deprecated')

2. **Manager Layer (Python enforces):**
   - Config not empty
   - Config uses Decimal for all numeric values (no floats)
   - Status transitions valid (state machine)
   - Calibration/accuracy in [0.0, 1.0] range

3. **Type Layer (Mypy enforces):**
   - `config` parameter type: `dict[str, Any]`
   - Return type: `dict[str, Any]` (TypedDict)
   - Compile-time type checking

**Example Validation:**
```python
# Manager validates config
try:
    model = manager.create_model(
        model_name="elo_nfl",
        model_version="v1.0",
        model_class="elo",
        config={}  # Empty config
    )
except ValueError as e:
    print(f"Validation error: {e}")
    # Output: Config cannot be empty
```

---

## Lifecycle Management

### Complete Lifecycle Example

**Scenario:** Create Elo model, test it, activate it, then replace with improved version.

```python
from precog.analytics.model_manager import ModelManager
from decimal import Decimal

manager = ModelManager()

# ============================================================================
# STEP 1: Create v1.0 (draft)
# ============================================================================
print("Step 1: Create v1.0 in draft status")

v1_0 = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    model_class="elo",
    config={
        "k_factor": Decimal("32.0"),
        "home_advantage": Decimal("55.0"),
        "mean_reversion": Decimal("0.33")
    },
    domain="nfl",
    description="NFL Elo model with home field advantage",
    status="draft",
    notes="Initial implementation"
)

print(f"Created: model_id={v1_0['model_id']}, status={v1_0['status']}")

# ============================================================================
# STEP 2: Progress to testing
# ============================================================================
print("\nStep 2: Progress to testing status")

v1_0 = manager.update_status(
    model_id=v1_0['model_id'],
    new_status="testing",
    notes="Starting backtest on 2023 NFL season (272 games)"
)

print(f"Updated: status={v1_0['status']}")

# ============================================================================
# STEP 3: Run backtesting (simulated)
# ============================================================================
print("\nStep 3: Run backtesting...")
print("(Simulating backtest execution...)")

# Simulate backtest results
calibration = Decimal("0.89")  # 89% calibrated
accuracy = Decimal("0.65")      # 65% accuracy
sample_size = 272                # 272 predictions

# ============================================================================
# STEP 4: Record validation metrics
# ============================================================================
print("\nStep 4: Record validation metrics")

v1_0 = manager.update_metrics(
    model_id=v1_0['model_id'],
    validation_calibration=calibration,
    validation_accuracy=accuracy,
    validation_sample_size=sample_size
)

print(f"Metrics: calibration={v1_0['validation_calibration']}, "
      f"accuracy={v1_0['validation_accuracy']}, "
      f"sample_size={v1_0['validation_sample_size']}")

# ============================================================================
# STEP 5: Activate for production
# ============================================================================
print("\nStep 5: Activate for production")

v1_0 = manager.update_status(
    model_id=v1_0['model_id'],
    new_status="active",
    notes=f"Backtest complete. Calibration: {calibration}, Accuracy: {accuracy}. Approved for production."
)

print(f"Activated: status={v1_0['status']}")

# ============================================================================
# STEP 6: Create improved v1.1 (parameter tuning)
# ============================================================================
print("\nStep 6: Create improved v1.1 with tuned parameters")

v1_1 = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.1",
    model_class="elo",
    config={
        "k_factor": Decimal("40.0"),        # Increased from 32.0
        "home_advantage": Decimal("60.0"),   # Increased from 55.0
        "mean_reversion": Decimal("0.33")    # Same
    },
    domain="nfl",
    description="NFL Elo model with tuned parameters",
    status="testing",
    notes="Hyperparameter optimization: increased k_factor and home_advantage"
)

print(f"Created v1.1: model_id={v1_1['model_id']}, status={v1_1['status']}")

# ============================================================================
# STEP 7: Validate v1.1 (simulated better metrics)
# ============================================================================
print("\nStep 7: Validate v1.1")

v1_1 = manager.update_metrics(
    model_id=v1_1['model_id'],
    validation_calibration=Decimal("0.92"),  # Better than v1.0
    validation_accuracy=Decimal("0.67"),      # Better than v1.0
    validation_sample_size=272
)

print(f"v1.1 Metrics: calibration={v1_1['validation_calibration']}, "
      f"accuracy={v1_1['validation_accuracy']}")

# ============================================================================
# STEP 8: Activate v1.1 and deprecate v1.0
# ============================================================================
print("\nStep 8: Activate v1.1 and deprecate v1.0")

# Activate v1.1
v1_1 = manager.update_status(
    model_id=v1_1['model_id'],
    new_status="active",
    notes="Improved calibration (0.89→0.92) and accuracy (0.65→0.67). Replacing v1.0."
)

# Deprecate v1.0
v1_0 = manager.update_status(
    model_id=v1_0['model_id'],
    new_status="deprecated",
    notes="Replaced by v1.1 with tuned parameters"
)

print(f"v1.1: status={v1_1['status']}")
print(f"v1.0: status={v1_0['status']}")

# ============================================================================
# STEP 9: List all versions
# ============================================================================
print("\nStep 9: List all versions of elo_nfl")

versions = manager.list_model_versions(model_name="elo_nfl")

for v in versions:
    print(f"- {v['model_version']}: {v['status']}, "
          f"calibration={v['validation_calibration']}, "
          f"accuracy={v['validation_accuracy']}")
```

**Output:**
```
Step 1: Create v1.0 in draft status
Created: model_id=1, status=draft

Step 2: Progress to testing status
Updated: status=testing

Step 3: Run backtesting...
(Simulating backtest execution...)

Step 4: Record validation metrics
Metrics: calibration=0.89, accuracy=0.65, sample_size=272

Step 5: Activate for production
Activated: status=active

Step 6: Create improved v1.1 with tuned parameters
Created v1.1: model_id=2, status=testing

Step 7: Validate v1.1
v1.1 Metrics: calibration=0.92, accuracy=0.67

Step 8: Activate v1.1 and deprecate v1.0
v1.1: status=active
v1.0: status=deprecated

Step 9: List all versions of elo_nfl
- v1.0: deprecated, calibration=0.89, accuracy=0.65
- v1.1: active, calibration=0.92, accuracy=0.67
```

---

## A/B Testing Workflows

### Scenario: Test k_factor Parameter

**Goal:** Compare Elo models with different k_factors (32 vs 40) to find optimal value.

**Step-by-Step Workflow:**

```python
from precog.analytics.model_manager import ModelManager
from decimal import Decimal

manager = ModelManager()

# ============================================================================
# STEP 1: Create baseline model (k_factor=32)
# ============================================================================
baseline = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    model_class="elo",
    config={"k_factor": Decimal("32.0")},
    domain="nfl",
    status="active",
    notes="Baseline: Standard chess Elo k_factor"
)

# ============================================================================
# STEP 2: Create variant model (k_factor=40)
# ============================================================================
variant = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.1",
    model_class="elo",
    config={"k_factor": Decimal("40.0")},
    domain="nfl",
    status="active",
    notes="Variant: Increased k_factor for faster rating changes"
)

# ============================================================================
# STEP 3: Run parallel backtesting (simulated)
# ============================================================================
print("Running parallel backtesting on 2023 NFL season...")

# Baseline results (k=32)
baseline = manager.update_metrics(
    model_id=baseline['model_id'],
    validation_calibration=Decimal("0.89"),
    validation_accuracy=Decimal("0.65"),
    validation_sample_size=272
)

# Variant results (k=40)
variant = manager.update_metrics(
    model_id=variant['model_id'],
    validation_calibration=Decimal("0.92"),
    validation_accuracy=Decimal("0.67"),
    validation_sample_size=272
)

# ============================================================================
# STEP 4: Compare metrics
# ============================================================================
print(f"\nBaseline (k=32): Calibration={baseline['validation_calibration']}, "
      f"Accuracy={baseline['validation_accuracy']}")
print(f"Variant (k=40): Calibration={variant['validation_calibration']}, "
      f"Accuracy={variant['validation_accuracy']}")

# ============================================================================
# STEP 5: Promote winner, deprecate loser
# ============================================================================
print("\nPromotion decision: Variant (k=40) is better!")

# Variant stays active (already active)
print(f"Keeping v1.1 active: calibration improved {baseline['validation_calibration']} → {variant['validation_calibration']}")

# Deprecate baseline
baseline = manager.update_status(
    model_id=baseline['model_id'],
    new_status="deprecated",
    notes="A/B test: v1.1 (k=40) outperformed v1.0 (k=32) by 3% calibration, 2% accuracy"
)

print(f"Deprecated v1.0: {baseline['status']}")
```

---

## Validation & Calibration

### Understanding Calibration

**What is Calibration?**

Calibration measures how well predicted probabilities match observed frequencies.

**Example:**
```
Model predicts team A has 70% win probability in 100 games.

Perfect Calibration:
- Team A wins 70 times (70%)
- Calibration score = 1.0

Poor Calibration:
- Team A wins 50 times (50%)
- Model is overconfident (predicted 70%, observed 50%)
- Calibration score < 1.0
```

**Why Calibration Matters:**

```python
# Model A: High accuracy, poor calibration
# - Predicts: 90% win probability
# - Observed: Team wins 60% of the time
# - Problem: Overconfident! Betting 90% odds loses money long-term

# Model B: Lower accuracy, good calibration
# - Predicts: 60% win probability
# - Observed: Team wins 58% of the time
# - Benefit: Accurate probability estimates enable profitable betting
```

**For trading:** Calibration matters MORE than accuracy. We need true probabilities to calculate edge!

### Calculating Calibration Score

**Brier Score (Most Common):**
```python
from decimal import Decimal

def brier_score(predictions: list[tuple[Decimal, bool]]) -> Decimal:
    """
    Calculate Brier score (lower is better, 0.0 = perfect).

    Parameters:
        predictions: List of (predicted_probability, actual_outcome) tuples

    Returns:
        Brier score (0.0 = perfect, 1.0 = worst)

    Example:
        >>> predictions = [
        ...     (Decimal("0.70"), True),   # Predicted 70%, team won
        ...     (Decimal("0.60"), False),  # Predicted 60%, team lost
        ...     (Decimal("0.80"), True),   # Predicted 80%, team won
        ... ]
        >>> score = brier_score(predictions)
        >>> print(score)  # Lower is better
    """
    n = len(predictions)
    total = Decimal("0.0")

    for pred_prob, actual_outcome in predictions:
        outcome_value = Decimal("1.0") if actual_outcome else Decimal("0.0")
        total += (pred_prob - outcome_value) ** 2

    return total / Decimal(str(n))

# Example usage
predictions = [
    (Decimal("0.70"), True),
    (Decimal("0.60"), False),
    (Decimal("0.80"), True),
    (Decimal("0.55"), True),
    (Decimal("0.45"), False),
]

brier = brier_score(predictions)
calibration_score = Decimal("1.0") - brier  # Convert to calibration (1.0 = perfect)

print(f"Brier Score: {brier}")
print(f"Calibration Score: {calibration_score}")
```

### Recording Metrics

```python
# After calculating calibration and accuracy
model = manager.update_metrics(
    model_id=42,
    validation_calibration=calibration_score,
    validation_accuracy=accuracy,
    validation_sample_size=len(predictions)
)
```

---

## Common Patterns

### Pattern 1: Load Config from YAML

```python
import yaml
from pathlib import Path
from decimal import Decimal

def load_model_config(yaml_path: Path) -> dict[str, Any]:
    """
    Load model config from YAML file with Decimal conversion.

    YAML files store numeric values as strings to avoid float contamination.
    Example YAML:
        k_factor: "32.0"  # String, not float!
    """
    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Convert string values to Decimal
    def str_to_decimal(obj):
        if isinstance(obj, str):
            try:
                return Decimal(obj)
            except:
                return obj
        if isinstance(obj, dict):
            return {k: str_to_decimal(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [str_to_decimal(item) for item in obj]
        return obj

    return str_to_decimal(config)

# Usage
config = load_model_config(Path("config/models/elo_nfl_v1.0.yaml"))
model = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    model_class="elo",
    config=config
)
```

### Pattern 2: Compare Model Versions

```python
def compare_models(
    manager: ModelManager,
    model_name: str,
    version1: str,
    version2: str,
) -> dict[str, Any]:
    """
    Compare two model versions side-by-side.

    Returns:
        Dict with comparison metrics
    """
    v1 = manager.get_model(model_name=model_name, model_version=version1)
    v2 = manager.get_model(model_name=model_name, model_version=version2)

    return {
        "model_name": model_name,
        "version1": {
            "version": v1['model_version'],
            "status": v1['status'],
            "calibration": v1['validation_calibration'],
            "accuracy": v1['validation_accuracy'],
            "sample_size": v1['validation_sample_size'],
        },
        "version2": {
            "version": v2['model_version'],
            "status": v2['status'],
            "calibration": v2['validation_calibration'],
            "accuracy": v2['validation_accuracy'],
            "sample_size": v2['validation_sample_size'],
        },
        "improvement": {
            "calibration": v2['validation_calibration'] - v1['validation_calibration'] if v1['validation_calibration'] and v2['validation_calibration'] else None,
            "accuracy": v2['validation_accuracy'] - v1['validation_accuracy'] if v1['validation_accuracy'] and v2['validation_accuracy'] else None,
        }
    }

# Usage
comparison = compare_models(
    manager=manager,
    model_name="elo_nfl",
    version1="v1.0",
    version2="v1.1"
)

print(f"Calibration improvement: {comparison['improvement']['calibration']}")
print(f"Accuracy improvement: {comparison['improvement']['accuracy']}")
```

### Pattern 3: Bulk Status Update

```python
def deprecate_all_except(
    manager: ModelManager,
    model_name: str,
    keep_version: str,
) -> int:
    """
    Deprecate all versions of a model except one.

    Returns:
        Number of models deprecated
    """
    versions = manager.list_model_versions(model_name=model_name)
    deprecated_count = 0

    for model in versions:
        # Skip the version we want to keep
        if model['model_version'] == keep_version:
            continue

        # Skip already deprecated models
        if model['status'] == 'deprecated':
            continue

        # Deprecate this version
        manager.update_status(
            model_id=model['model_id'],
            new_status='deprecated',
            notes=f"Bulk deprecation: keeping only {keep_version}"
        )
        deprecated_count += 1

    return deprecated_count

# Usage
count = deprecate_all_except(
    manager=manager,
    model_name="elo_nfl",
    keep_version="v1.1"
)
print(f"Deprecated {count} old versions")
```

### Pattern 4: Clone Model with Modified Config

```python
def clone_model_with_changes(
    manager: ModelManager,
    source_model_id: int,
    new_version: str,
    config_changes: dict[str, Any],
) -> dict[str, Any]:
    """
    Clone existing model with modified config parameters.

    Parameters:
        source_model_id: Model to clone
        new_version: Version for cloned model
        config_changes: Dict of config keys to change

    Returns:
        New model dict
    """
    # Get source model
    source = manager.get_model(model_id=source_model_id)

    # Merge config changes
    new_config = {**source['config'], **config_changes}

    # Create new version
    return manager.create_model(
        model_name=source['model_name'],
        model_version=new_version,
        model_class=source['model_class'],
        config=new_config,
        domain=source['domain'],
        description=f"Cloned from {source['model_version']} with modifications",
        status="draft",
        notes=f"Config changes: {list(config_changes.keys())}"
    )

# Usage: Clone v1.0 with increased k_factor
v1_1 = clone_model_with_changes(
    manager=manager,
    source_model_id=1,  # v1.0 model_id
    new_version="v1.1",
    config_changes={"k_factor": Decimal("40.0")}
)
```

---

## Troubleshooting

### Error 1: IntegrityError (Duplicate Version)

**Error:**
```python
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "uq_model_name_version"
DETAIL: Key (model_name, model_version)=(elo_nfl, v1.0) already exists.
```

**Cause:** Model with same name + version already exists.

**Solution:**
```python
# Check if version exists first
existing = manager.get_model(model_name="elo_nfl", model_version="v1.0")

if existing:
    print(f"Version v1.0 already exists: {existing['model_id']}")
    # Use different version number
    new_model = manager.create_model(
        model_name="elo_nfl",
        model_version="v1.1",  # Different version
        ...
    )
else:
    new_model = manager.create_model(
        model_name="elo_nfl",
        model_version="v1.0",
        ...
    )
```

### Error 2: ForeignKeyViolation (Invalid model_class)

**Error:**
```python
psycopg2.errors.ForeignKeyViolation: insert or update on table "probability_models" violates foreign key constraint "fk_model_class"
DETAIL: Key (model_class)=(custom_algo) is not present in table "model_classes".
```

**Cause:** `model_class` not in `model_classes` lookup table.

**Solution:**
```python
# Check valid model classes
conn = get_connection()
cursor = conn.cursor()

cursor.execute("SELECT model_class FROM model_classes ORDER BY model_class")
valid_classes = [row[0] for row in cursor.fetchall()]

print(f"Valid model classes: {valid_classes}")
# Output: ['elo', 'ensemble', 'logistic', 'neural_network', 'random_forest', 'xgboost']

release_connection(conn)

# Use valid model class
model = manager.create_model(
    model_class="elo",  # Valid!
    ...
)
```

### Error 3: InvalidStatusTransitionError

**Error:**
```python
InvalidStatusTransitionError: Cannot transition from 'deprecated' to 'active'
```

**Cause:** Invalid status transition (trying to reactivate deprecated model).

**Solution:**
```python
# Don't reactivate deprecated models - create new version instead
old_model = manager.get_model(model_id=42)

if old_model['status'] == 'deprecated':
    # Clone to new version
    new_model = manager.create_model(
        model_name=old_model['model_name'],
        model_version="v1.2",  # New version
        model_class=old_model['model_class'],
        config=old_model['config'],
        status="active"
    )
    print(f"Created new version: {new_model['model_version']}")
```

### Error 4: ValueError (Float in Config)

**Error:**
```python
ValueError: Config contains float values. Use Decimal instead.
```

**Cause:** Config contains float values (violates Pattern 1: Decimal Precision).

**Solution:**
```python
# ❌ WRONG
config = {"k_factor": 32.0}  # Float!

# ✅ CORRECT
from decimal import Decimal
config = {"k_factor": Decimal("32.0")}  # Decimal!

model = manager.create_model(
    config=config,
    ...
)
```

---

## Advanced Topics

### Dynamic Config Parameters

**Scenario:** Store formula for computing confidence threshold, not hardcoded value.

**Approach 1: Store Formula, Compute at Runtime (Recommended)**

```python
# Create model with formula in config
model = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    model_class="elo",
    config={
        "k_factor": Decimal("32.0"),
        "confidence_formula": "k_factor * 0.5"  # Formula as string
    }
)

# At prediction time, evaluate formula
def get_confidence_threshold(model: dict[str, Any]) -> Decimal:
    """Evaluate confidence_formula dynamically."""
    formula = model['config']['confidence_formula']
    k_factor = model['config']['k_factor']

    # Simple evaluation (for production, use ast.literal_eval or safer parser)
    return k_factor * Decimal("0.5")

threshold = get_confidence_threshold(model)
print(f"Confidence threshold: {threshold}")  # 16.0
```

**Approach 2: Pre-compute and Store (For Expensive Operations)**

```python
# Expensive computation: Optimize k_factor via grid search
from scipy.optimize import minimize

def optimize_k_factor(historical_data: list) -> Decimal:
    """Expensive optimization (takes 30 seconds)."""
    # ... grid search or Bayesian optimization ...
    return Decimal("38.5")  # Optimal k_factor

# Pre-compute once
optimal_k = optimize_k_factor(historical_data)

# Store result in config
model = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    model_class="elo",
    config={"k_factor": optimal_k},  # Precomputed value
    notes=f"k_factor optimized via grid search"
)
```

### Model Attribution Chain

**Linking Predictions to Models:**

```python
# prediction_id → model_id → config
# Enables: "Which config generated this prediction?"

# 1. Create model
model = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    model_class="elo",
    config={"k_factor": Decimal("32.0")}
)

# 2. Generate prediction (store model_id)
prediction = {
    "prediction_id": "PRED-12345",
    "model_id": model['model_id'],  # Attribution!
    "predicted_probability": Decimal("0.67"),
    "actual_outcome": None  # Will be updated later
}

# 3. Later: Look up config used for this prediction
prediction_model = manager.get_model(model_id=prediction['model_id'])
print(f"Prediction PRED-12345 used config: {prediction_model['config']}")
# Output: {'k_factor': Decimal('32.0')}

# Benefit: Even if model updated to v1.1, we know v1.0 config generated this prediction
```

---

## References

### Source Code
- **Model Manager:** `src/precog/analytics/model_manager.py` (738 lines)
- **Database Connection:** `src/precog/database/connection.py`
- **CRUD Operations:** `src/precog/database/crud_operations.py`

### Documentation
- **Versioning Guide:** `docs/guides/VERSIONING_GUIDE_V1.0.md`
- **Strategy Manager Guide:** `docs/guides/STRATEGY_MANAGER_USER_GUIDE_V1.0.md`
- **Database Schema:** `docs/database/DATABASE_SCHEMA_SUMMARY_V1.11.md`
- **Development Patterns:** `docs/guides/DEVELOPMENT_PATTERNS_V1.6.md`

### Requirements & ADRs
- **REQ-MODEL-001:** Probability Model Management
- **REQ-MODEL-002:** Model Versioning & Lifecycle
- **REQ-MODEL-003:** Calibration Tracking
- **ADR-021:** Model Immutability
- **ADR-022:** Model Lifecycle State Machine
- **ADR-023:** Lookup Table Foreign Keys
- **ADR-074:** Property-Based Testing for Model Validation

### Database Tables
- **probability_models:** Main model storage (immutable configs)
- **model_classes:** Lookup table (valid model types)
- **predictions:** Links to probability_models.model_id (attribution chain)

### Related Tools
- **Strategy Manager:** Manages trading strategies (similar versioning pattern)
- **Position Manager:** Manages open positions (uses models via predictions)

---

`★ Insight ─────────────────────────────────────`

**Model Manager vs Strategy Manager Architecture:**

1. **Same Immutability Pattern:** Both freeze configs after creation to enable rigorous A/B testing

2. **Different Metrics Tracking:**
   - Models track calibration/accuracy (prediction quality)
   - Strategies track Sharpe ratio/profit (trading performance)

3. **Shared Versioning Philosophy:** Semantic versions (v1.0 → v1.1 = parameter change, v1.0 → v2.0 = algorithm change)

4. **Attribution Chain:** Every trade traces back through: trade → position → strategy → model → exact configs

`─────────────────────────────────────────────────`

---

**END OF MODEL_MANAGER_USER_GUIDE_V1.0.md**
