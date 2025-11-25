# Model Training Guide

---
**Version:** 1.0
**Created:** 2025-11-25
**Status:** 🔵 Planned (Phase 3+)
**Target Audience:** Data scientists and ML engineers implementing automated model training
**Prerequisite Reading:**
- `MODEL_MANAGER_USER_GUIDE_V1.1.md` - Model lifecycle and CRUD operations
- `EVENT_LOOP_ARCHITECTURE_V1.0.md` - Weekly training schedule integration

**Related Requirements:**
- REQ-MODEL-004: Automated Model Training Pipelines
- REQ-MODEL-005: Hyperparameter Optimization
- REQ-MODEL-006: Model Serialization and Versioning

**Related ADRs:**
- ADR-110: Hyperparameter Tuning Methodology (Grid Search + Bayesian)
- ADR-111: Cross-Validation Strategy (5-Fold Time-Series Split)
- ADR-112: Model Serialization Format (Joblib for sklearn models)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Training Pipelines](#training-pipelines)
4. [Hyperparameter Tuning](#hyperparameter-tuning)
5. [Cross-Validation](#cross-validation)
6. [Model Serialization](#model-serialization)
7. [Training Metrics](#training-metrics)
8. [Scheduling](#scheduling)
9. [Implementation Examples](#implementation-examples)
10. [Testing Strategy](#testing-strategy)
11. [Cross-References](#cross-references)

---

## Overview

### Purpose

The **ModelTrainer** automates model training workflows, including data preparation, hyperparameter optimization, cross-validation, and model serialization.

**Key Benefits:**
- **Automated Retraining:** Weekly scheduled retraining with latest data
- **Hyperparameter Optimization:** Systematic parameter search (grid/Bayesian)
- **Overfitting Prevention:** K-fold cross-validation ensures generalization
- **Version Management:** Immutable model versions with metadata tracking

### Training Workflow

```
Data Collection → Feature Engineering → Hyperparameter Tuning → Cross-Validation → Model Serialization → Deployment
```

---

## Architecture

### ModelTrainer Class

**Location:** `src/precog/analytics/model_trainer.py` (~500 lines)

```python
class ModelTrainer:
    """
    Automated model training with hyperparameter tuning and cross-validation.

    Educational Note:
        Machine learning workflow:
        1. **Data Preparation:** Load training data (games, stats, outcomes)
        2. **Feature Engineering:** Transform raw data → model inputs
        3. **Hyperparameter Tuning:** Find best model parameters (grid/Bayesian search)
        4. **Cross-Validation:** Test on held-out folds (prevent overfitting)
        5. **Final Training:** Train on full dataset with best parameters
        6. **Serialization:** Save model to disk (.pkl file)
        7. **Registration:** Add to models table with metadata

        Why cross-validation?
        - Training on full dataset → high accuracy but may not generalize
        - Test on held-out data → estimates real-world performance
        - K-fold CV → average over K splits → robust estimate
    """

    def __init__(
        self,
        model_manager: ModelManager,
        logger: Logger
    ):
        self.model_manager = model_manager
        self.logger = logger

    def train_model(
        self,
        model_name: str,
        model_class: str,
        training_data_path: str,
        hyperparameter_grid: dict[str, list[Decimal]],
        cv_folds: int = 5
    ) -> dict[str, Any]:
        """
        Train model with hyperparameter tuning and cross-validation.

        Args:
            model_name: Model identifier (e.g., "elo_nfl")
            model_class: Model type ("elo", "logistic", "xgboost")
            training_data_path: Path to training dataset
            hyperparameter_grid: Parameters to search
            cv_folds: Number of cross-validation folds

        Returns:
            Training results with best parameters and metrics
        """
        self.logger.info(f"Starting model training: {model_name}")

        # Step 1: Load and prepare data
        X_train, y_train = self._load_training_data(training_data_path)

        # Step 2: Hyperparameter tuning
        best_params = self._tune_hyperparameters(
            model_class,
            X_train,
            y_train,
            hyperparameter_grid,
            cv_folds
        )

        # Step 3: Train final model with best parameters
        model = self._train_final_model(model_class, X_train, y_train, best_params)

        # Step 4: Calculate training metrics
        metrics = self._calculate_metrics(model, X_train, y_train)

        # Step 5: Serialize model to disk
        model_path = self._serialize_model(model, model_name)

        # Step 6: Register model in database
        model_id = self.model_manager.create_model(
            model_name=model_name,
            model_class=model_class,
            model_version=self._get_next_version(model_name),
            model_path=model_path,
            hyperparameters=best_params,
            training_accuracy=metrics['accuracy'],
            calibration_score=metrics['calibration'],
            log_loss=metrics['log_loss']
        )

        return {
            'model_id': model_id,
            'best_params': best_params,
            'cv_accuracy': metrics['cv_accuracy'],
            'accuracy': metrics['accuracy'],
            'calibration': metrics['calibration'],
            'log_loss': metrics['log_loss'],
            'model_path': model_path
        }
```

---

## Training Pipelines

### Pipeline Components

```python
def _load_training_data(self, training_data_path: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Load and prepare training data.

    Returns:
        (X_train, y_train) where:
        - X_train: Feature matrix (N x M)
        - y_train: Labels (N x 1)

    Educational Note:
        Feature engineering examples (NFL):
        - Team Elo ratings (continuous)
        - Home/Away indicator (binary)
        - Days of rest (continuous)
        - Weather conditions (categorical → one-hot)
        - Injury counts (discrete)

        Target variable:
        - Binary outcome: 1 = home team wins, 0 = away team wins
        - Model predicts P(home team wins)
    """
    import pandas as pd

    df = pd.read_csv(training_data_path)

    # Feature columns
    feature_cols = [
        'home_elo', 'away_elo', 'elo_diff',
        'home_rest_days', 'away_rest_days',
        'home_win_streak', 'away_win_streak',
        'is_divisional_game', 'is_conference_game'
    ]

    X_train = df[feature_cols].values
    y_train = df['home_team_won'].values

    self.logger.info(f"Loaded {len(X_train)} training samples with {X_train.shape[1]} features")

    return X_train, y_train
```

---

## Hyperparameter Tuning

### Grid Search

```python
def _tune_hyperparameters_grid_search(
    self,
    model_class: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    hyperparameter_grid: dict[str, list[Decimal]],
    cv_folds: int
) -> dict[str, Decimal]:
    """
    Tune hyperparameters using grid search with cross-validation.

    Educational Note:
        Grid search exhaustively tries all parameter combinations:
        - k_factor: [24, 32, 40] (3 values)
        - home_advantage: [50, 55, 60] (3 values)
        - mean_reversion: [0.25, 0.33, 0.50] (3 values)

        Total combinations: 3 × 3 × 3 = 27
        With 5-fold CV: 27 × 5 = 135 model training runs

        Pros: Guaranteed to find best combination in grid
        Cons: Exponential growth with parameters (10 params = 10^10 combinations!)
    """
    from sklearn.model_selection import GridSearchCV
    from sklearn.linear_model import LogisticRegression

    # Convert Decimal → float for sklearn
    param_grid = {
        k: [float(v) for v in vals]
        for k, vals in hyperparameter_grid.items()
    }

    # Initialize model
    if model_class == "logistic":
        base_model = LogisticRegression()
    # ... other model classes

    # Grid search with cross-validation
    grid_search = GridSearchCV(
        base_model,
        param_grid,
        cv=cv_folds,
        scoring='neg_log_loss',  # Optimize calibration
        n_jobs=-1  # Parallel execution
    )

    grid_search.fit(X_train, y_train)

    # Convert best params back to Decimal
    best_params = {
        k: Decimal(str(v))
        for k, v in grid_search.best_params_.items()
    }

    self.logger.info(f"Best parameters: {best_params}")
    self.logger.info(f"Best CV score: {-grid_search.best_score_:.4f}")

    return best_params
```

### Bayesian Optimization

```python
def _tune_hyperparameters_bayesian(
    self,
    model_class: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    hyperparameter_space: dict[str, tuple[Decimal, Decimal]],
    n_trials: int = 50
) -> dict[str, Decimal]:
    """
    Tune hyperparameters using Bayesian optimization.

    Args:
        hyperparameter_space: {param: (min, max)} bounds

    Educational Note:
        Bayesian optimization is smarter than grid search:
        1. Try initial random parameters
        2. Observe performance
        3. Build probabilistic model of parameter→performance mapping
        4. Use model to pick next best parameters to try
        5. Repeat until budget exhausted

        Advantage: Finds good parameters with fewer trials
        - Grid search: 27 trials for 3×3×3 grid
        - Bayesian: Often finds optimum in 20-30 trials

        Use when: >5 hyperparameters or continuous ranges
    """
    from optuna import create_study
    from optuna.samplers import TPESampler

    def objective(trial):
        # Sample parameters from space
        params = {}
        for param_name, (min_val, max_val) in hyperparameter_space.items():
            params[param_name] = trial.suggest_float(
                param_name,
                float(min_val),
                float(max_val)
            )

        # Train model with these parameters
        model = self._create_model(model_class, params)

        # Cross-validation score
        from sklearn.model_selection import cross_val_score
        scores = cross_val_score(
            model,
            X_train,
            y_train,
            cv=5,
            scoring='neg_log_loss'
        )

        return scores.mean()  # Return avg CV score

    # Run optimization
    study = create_study(
        direction='minimize',  # Minimize log loss
        sampler=TPESampler()
    )
    study.optimize(objective, n_trials=n_trials)

    # Best parameters
    best_params = {
        k: Decimal(str(v))
        for k, v in study.best_params.items()
    }

    return best_params
```

---

## Cross-Validation

### Time-Series Split

```python
def _cross_validate_time_series(
    self,
    model,
    X_train: np.ndarray,
    y_train: np.ndarray,
    n_splits: int = 5
) -> dict[str, float]:
    """
    Cross-validate using time-series splits (no data leakage).

    Educational Note:
        Standard K-Fold CV shuffles data randomly:
        - Train: [game1, game3, game5, ...], Test: [game2, game4, ...]
        - PROBLEM: Training on future data to predict past (data leakage!)

        Time-Series Split respects temporal order:
        - Split 1: Train on games 1-100, test on 101-120
        - Split 2: Train on games 1-120, test on 121-140
        - Split 3: Train on games 1-140, test on 141-160
        - ...

        Always train on past, test on future (realistic evaluation).
    """
    from sklearn.model_selection import TimeSeriesSplit

    tscv = TimeSeriesSplit(n_splits=n_splits)

    fold_scores = []
    for fold_idx, (train_idx, test_idx) in enumerate(tscv.split(X_train)):
        X_fold_train, X_fold_test = X_train[train_idx], X_train[test_idx]
        y_fold_train, y_fold_test = y_train[train_idx], y_train[test_idx]

        # Train on fold
        model.fit(X_fold_train, y_fold_train)

        # Evaluate on test fold
        y_pred_proba = model.predict_proba(X_fold_test)[:, 1]

        from sklearn.metrics import log_loss
        fold_log_loss = log_loss(y_fold_test, y_pred_proba)

        fold_scores.append(fold_log_loss)

        self.logger.debug(f"Fold {fold_idx + 1}/{n_splits}: log_loss={fold_log_loss:.4f}")

    avg_score = np.mean(fold_scores)
    std_score = np.std(fold_scores)

    return {
        'mean_log_loss': avg_score,
        'std_log_loss': std_score,
        'fold_scores': fold_scores
    }
```

---

## Model Serialization

### Save Model to Disk

```python
def _serialize_model(
    self,
    model: Any,
    model_name: str
) -> str:
    """
    Serialize trained model to disk.

    Returns:
        Path to saved model file

    Educational Note:
        Serialization formats:
        - pickle: Python-specific, smaller files, INSECURE (don't unpickle untrusted data)
        - joblib: Optimized for numpy arrays (sklearn models), faster for large models
        - ONNX: Cross-language (deploy in C++/Java), larger files

        We use joblib for sklearn models (standard choice).
    """
    import joblib
    from datetime import datetime

    # Generate versioned filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version = self._get_next_version(model_name)
    filename = f"{model_name}_v{version}_{timestamp}.pkl"
    model_path = f"models/{filename}"

    # Ensure directory exists
    import os
    os.makedirs("models", exist_ok=True)

    # Save model
    joblib.dump(model, model_path)

    file_size = os.path.getsize(model_path) / 1024  # KB
    self.logger.info(f"Model saved: {model_path} ({file_size:.1f} KB)")

    return model_path
```

### Load Model from Disk

```python
def load_model(self, model_path: str) -> Any:
    """
    Load serialized model from disk.

    Educational Note:
        Model loading workflow:
        1. Fetch model_path from models table
        2. Load .pkl file with joblib
        3. Model ready for predictions

        Security: NEVER load .pkl files from untrusted sources!
        Pickle can execute arbitrary code during deserialization.
    """
    import joblib

    model = joblib.load(model_path)

    self.logger.info(f"Model loaded: {model_path}")

    return model
```

---

## Training Metrics

### Calibration Metrics

```python
def _calculate_metrics(
    self,
    model: Any,
    X_train: np.ndarray,
    y_train: np.ndarray
) -> dict[str, float]:
    """
    Calculate model performance metrics.

    Returns:
        {
            'accuracy': Classification accuracy,
            'log_loss': Calibration metric (lower is better),
            'calibration': Calibration score (ECE),
            'brier_score': Brier score (lower is better)
        }

    Educational Note:
        Metrics for probability models:

        1. **Accuracy:** Correct predictions / total predictions
           - Example: 687/1000 = 68.7%
           - Problem: Ignores confidence (50.1% and 99.9% both counted as "correct")

        2. **Log Loss:** Penalizes confident wrong predictions
           - Lower is better (0 = perfect, ∞ = worst)
           - Example: Predict 90% home team wins, away team wins → log_loss = 2.30

        3. **Calibration (ECE):** Are predicted probabilities accurate?
           - Bin predictions: [0-10%, 10-20%, ..., 90-100%]
           - For 60-70% bin: Average prediction should be ~65%
           - ECE = average absolute error across bins

        4. **Brier Score:** Mean squared error of probabilities
           - (predicted_prob - actual_outcome)^2
           - Lower is better (0 = perfect, 1 = worst)

        For trading: Calibration is CRITICAL (need accurate edge calculations)
    """
    from sklearn.metrics import accuracy_score, log_loss, brier_score_loss

    # Predictions
    y_pred = model.predict(X_train)
    y_pred_proba = model.predict_proba(X_train)[:, 1]

    # Accuracy
    accuracy = accuracy_score(y_train, y_pred)

    # Log loss
    log_loss_value = log_loss(y_train, y_pred_proba)

    # Brier score
    brier = brier_score_loss(y_train, y_pred_proba)

    # Calibration (Expected Calibration Error)
    calibration = self._expected_calibration_error(y_train, y_pred_proba)

    return {
        'accuracy': accuracy,
        'log_loss': log_loss_value,
        'brier_score': brier,
        'calibration': calibration
    }
```

---

## Scheduling

### Weekly Training Schedule

```python
# Event loop integration (pseudo-code)
async def run_event_loop():
    """Main event loop with weekly model training."""

    while True:
        current_time = datetime.now()

        # Weekly training: Sunday 3:00 AM
        if current_time.weekday() == 6 and current_time.hour == 3:
            await train_all_models()

        await asyncio.sleep(60)


async def train_all_models():
    """Train all active models with latest data."""
    trainer = ModelTrainer(model_manager, logger)

    # NFL model
    nfl_result = trainer.train_model(
        model_name="elo_nfl",
        model_class="elo",
        training_data_path="data/nfl_games_latest.csv",
        hyperparameter_grid={
            "k_factor": [Decimal("24"), Decimal("32"), Decimal("40")],
            "home_advantage": [Decimal("50"), Decimal("55"), Decimal("60")]
        },
        cv_folds=5
    )

    logger.info(f"NFL model trained: {nfl_result['cv_accuracy']:.3f} accuracy")

    # NBA model
    # ...
```

---

## Implementation Examples

### Example: Full Training Workflow

```python
from precog.analytics.model_trainer import ModelTrainer
from decimal import Decimal

trainer = ModelTrainer(model_manager, logger)

# Train NFL Elo model with hyperparameter tuning
result = trainer.train_model(
    model_name="elo_nfl",
    model_class="elo",
    training_data_path="data/nfl_2024_season.csv",
    hyperparameter_grid={
        "k_factor": [Decimal("24.0"), Decimal("32.0"), Decimal("40.0")],
        "home_advantage": [Decimal("50.0"), Decimal("55.0"), Decimal("60.0")],
        "mean_reversion": [Decimal("0.25"), Decimal("0.33"), Decimal("0.50")]
    },
    cv_folds=5
)

print(f"✅ Model trained successfully!")
print(f"Model ID: {result['model_id']}")
print(f"Best Parameters: {result['best_params']}")
print(f"CV Accuracy: {result['cv_accuracy']:.3f}")
print(f"Log Loss: {result['log_loss']:.4f}")
print(f"Calibration (ECE): {result['calibration']:.4f}")
print(f"Model saved: {result['model_path']}")

# Output:
# ✅ Model trained successfully!
# Model ID: 42
# Best Parameters: {'k_factor': Decimal('32.0'), 'home_advantage': Decimal('55.0'), ...}
# CV Accuracy: 0.687
# Log Loss: 0.5421
# Calibration (ECE): 0.0234
# Model saved: models/elo_nfl_v2.0_20251124_030015.pkl
```

---

## Testing Strategy

### Unit Tests

```python
def test_hyperparameter_grid_search():
    """Test grid search finds optimal parameters."""
    trainer = ModelTrainer(...)

    result = trainer._tune_hyperparameters_grid_search(
        model_class="logistic",
        X_train=mock_features,
        y_train=mock_labels,
        hyperparameter_grid={"C": [Decimal("0.1"), Decimal("1.0"), Decimal("10.0")]},
        cv_folds=3
    )

    assert 'C' in result
    assert result['C'] in [Decimal("0.1"), Decimal("1.0"), Decimal("10.0")]


def test_model_serialization_round_trip():
    """Test model can be saved and loaded."""
    trainer = ModelTrainer(...)

    # Train simple model
    from sklearn.linear_model import LogisticRegression
    model = LogisticRegression()
    model.fit(X_train, y_train)

    # Save
    path = trainer._serialize_model(model, "test_model")

    # Load
    loaded_model = trainer.load_model(path)

    # Verify predictions match
    original_preds = model.predict_proba(X_test)
    loaded_preds = loaded_model.predict_proba(X_test)

    np.testing.assert_array_almost_equal(original_preds, loaded_preds)
```

---

## Cross-References

**Prerequisites:**
- `MODEL_MANAGER_USER_GUIDE_V1.1.md` - Model CRUD operations and lifecycle
- `EVENT_LOOP_ARCHITECTURE_V1.0.md` - Weekly training schedule

**Related Guides:**
- `EDGE_CALCULATION_GUIDE_V1.0.md` - Using trained models for edge calculation
- `DATA_COLLECTION_GUIDE_V1.0.md` - Collecting training data

**Requirements:**
- REQ-MODEL-004: Automated Model Training Pipelines
- REQ-MODEL-005: Hyperparameter Optimization
- REQ-MODEL-006: Model Serialization and Versioning

**Architecture Decisions:**
- ADR-110: Hyperparameter Tuning Methodology (Grid Search + Bayesian)
- ADR-111: Cross-Validation Strategy (5-Fold Time-Series Split)
- ADR-112: Model Serialization Format (Joblib for sklearn models)

---

**END OF MODEL_TRAINING_GUIDE_V1.0.md**
