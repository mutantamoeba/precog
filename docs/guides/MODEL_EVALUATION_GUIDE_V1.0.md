# Model Evaluation Guide V1.0

---
**Version:** 1.0
**Created:** 2025-11-10
**Status:** ✅ Current
**Phase:** 4 (Model Development & Ensemble)
**Target Audience:** Data scientists, ML engineers implementing probability models

**Related Documents:**
- **ADR-082:** Model Evaluation Framework (Architecture Decision)
- **REQ-MODEL-EVAL-001:** Backtesting Validation Requirements
- **REQ-MODEL-EVAL-002:** Holdout Validation Requirements
- **MASTER_REQUIREMENTS_V2.13.md:** Model evaluation requirements (REQ-MODEL-EVAL-*)
- **ARCHITECTURE_DECISIONS_V2.13.md:** Model evaluation architecture (ADR-082)

**Change History:**
| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-11-10 | Initial creation - Complete model evaluation workflow | Claude |

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Backtesting Walkthrough](#backtesting-walkthrough)
4. [Cross-Validation Implementation](#cross-validation-implementation)
5. [Holdout Validation](#holdout-validation)
6. [Calibration Metrics Deep Dive](#calibration-metrics-deep-dive)
7. [Reliability Diagrams](#reliability-diagrams)
8. [ModelEvaluator Class Usage](#modelevaluator-class-usage)
9. [Activation Criteria Checklist](#activation-criteria-checklist)
10. [Common Pitfalls](#common-pitfalls)
11. [Troubleshooting](#troubleshooting)

---

## 1. Overview

### What This Guide Covers

This guide provides **step-by-step instructions** for evaluating probability models before production deployment. You'll learn:

- **Backtesting:** Test models on 2023-2024 historical data (1,000+ games)
- **Cross-validation:** 5-fold temporal CV to prevent overfitting
- **Holdout validation:** Final activation test on unseen 2024 Q4 data
- **Calibration metrics:** Brier Score, Expected Calibration Error, Log Loss
- **Reliability diagrams:** Visual calibration analysis
- **Activation criteria:** 8-point checklist before production deployment

### Why Model Evaluation Matters

**Problem:** A model with 55% accuracy on training data might only achieve 48% on production data (below coin flip!).

**Root Causes:**
1. **Overfitting:** Model memorizes training data noise, fails to generalize
2. **Data leakage:** Using future information (e.g., final score) to predict game outcome
3. **Poor calibration:** Model predicts 70% win probability, but only 52% of those bets actually win
4. **Insufficient sample size:** 20 test games isn't enough (need ≥100 for statistical significance)

**Solution:** Rigorous 3-stage evaluation pipeline ensures models generalize to production:
- **Stage 1 (Backtesting):** Test on 2023-2024 historical data (1,000+ games)
- **Stage 2 (Cross-Validation):** 5-fold temporal CV to detect overfitting
- **Stage 3 (Holdout Validation):** Final test on unseen 2024 Q4 data before activation

**Educational Note:**
Model evaluation is NOT optional. Deploying an unevaluated model is like trading with a 45% win rate strategy - you'll lose money systematically. Always complete all 3 stages before production deployment.

---

## 2. Quick Start

### Prerequisites

**Required:**
- Python 3.12+
- PostgreSQL database with historical game data (2023-2024)
- Model implementation (e.g., `models/elo_model.py`)
- Dependencies: scikit-learn, numpy, pandas, matplotlib

**Install Dependencies:**
```bash
pip install scikit-learn numpy pandas matplotlib scipy
```

### 5-Minute Example: Evaluate Elo Model

```python
from analytics.model_evaluator import ModelEvaluator
from models.elo_model import EloModel
from database.connection import get_db_session

# 1. Initialize model and evaluator
model = EloModel(version="v2.0")
evaluator = ModelEvaluator(model=model, db_session=get_db_session())

# 2. Run backtesting (2023-2024 historical data)
backtest_results = evaluator.run_backtesting(
    start_date="2023-09-01",
    end_date="2024-12-31"
)
print(f"Backtesting: {backtest_results['accuracy']:.1%} accuracy, Brier={backtest_results['brier_score']:.4f}")

# 3. Run 5-fold cross-validation
cv_results = evaluator.run_cross_validation(n_folds=5)
print(f"Cross-Validation: {cv_results['avg_accuracy']:.1%} accuracy (±{cv_results['std_accuracy']:.1%})")

# 4. Run holdout validation (2024 Q4 unseen data)
holdout_results = evaluator.run_holdout_validation(
    holdout_start="2024-10-01",
    holdout_end="2024-12-31"
)
print(f"Holdout: {holdout_results['accuracy']:.1%} accuracy, Brier={holdout_results['brier_score']:.4f}")

# 5. Generate reliability diagram
evaluator.plot_reliability_diagram(
    predictions=holdout_results['predictions'],
    outcomes=holdout_results['outcomes'],
    save_path="outputs/elo_model_v2.0_reliability.png"
)

# 6. Check activation criteria
if evaluator.meets_activation_criteria(holdout_results):
    print("✅ Model meets activation criteria - ready for production!")
else:
    print("❌ Model does NOT meet activation criteria - needs improvement")
```

**Expected Output:**
```
Backtesting: 54.2% accuracy, Brier=0.1834
Cross-Validation: 53.8% accuracy (±1.2%)
Holdout: 54.5% accuracy, Brier=0.1801
✅ Model meets activation criteria - ready for production!
```

---

## 3. Backtesting Walkthrough

### What is Backtesting?

**Backtesting** tests a model on historical data (2023-2024 games) to simulate production performance.

**Example:** Elo model predicts Kansas City Chiefs have 72% win probability on 2023-09-07. Chiefs win. Did the model's 72% prediction align with actual outcomes across 1,000+ games?

### Step 1: Fetch Historical Game Data

```python
from database.connection import get_db_session
from database.crud_operations import fetch_games_for_backtesting
from datetime import datetime

db_session = get_db_session()

# Fetch all NFL games from 2023-2024 seasons
historical_games = fetch_games_for_backtesting(
    db_session=db_session,
    league="nfl",
    start_date=datetime(2023, 9, 1),
    end_date=datetime(2024, 12, 31),
    include_playoffs=True
)

print(f"Fetched {len(historical_games)} historical games")
# Expected: ~550 games (272 regular season games per year + playoffs)
```

**Query Implementation (crud_operations.py):**
```python
from sqlalchemy import and_
from database.schema import Game

def fetch_games_for_backtesting(
    db_session,
    league: str,
    start_date: datetime,
    end_date: datetime,
    include_playoffs: bool = True
) -> List[Game]:
    """
    Fetch games for backtesting (must be completed with final scores).

    Educational Note:
        Only fetch COMPLETED games (status='completed', final_score NOT NULL).
        Exclude in-progress or scheduled games (no ground truth outcome yet).
    """
    query = db_session.query(Game).filter(
        and_(
            Game.league == league,
            Game.game_date >= start_date,
            Game.game_date <= end_date,
            Game.status == 'completed',  # Only completed games
            Game.home_final_score.isnot(None),  # Must have final score
            Game.away_final_score.isnot(None)
        )
    )

    if not include_playoffs:
        query = query.filter(Game.is_playoff == False)

    return query.order_by(Game.game_date).all()
```

### Step 2: Generate Model Predictions

```python
from models.elo_model import EloModel
from decimal import Decimal

model = EloModel(version="v2.0")

predictions = []
outcomes = []

for game in historical_games:
    # Generate prediction (probability home team wins)
    home_win_prob = model.predict(
        home_team=game.home_team,
        away_team=game.away_team,
        game_date=game.game_date,
        is_neutral_site=game.is_neutral_site
    )

    # Determine actual outcome (1 = home win, 0 = away win)
    actual_outcome = 1 if game.home_final_score > game.away_final_score else 0

    predictions.append(home_win_prob)
    outcomes.append(actual_outcome)

print(f"Generated {len(predictions)} predictions")
```

**Educational Note:**
**CRITICAL:** Predictions must be generated WITHOUT using future information. The model should only use data available BEFORE the game (team Elos as of game_date - 1 day). Using final scores or post-game data = data leakage = invalid evaluation.

**Common Data Leakage Mistakes:**
```python
# ❌ WRONG - Using final score to predict winner (data leakage!)
home_win_prob = model.predict(home_score=game.home_final_score, away_score=game.away_final_score)

# ❌ WRONG - Using post-game Elo ratings (data leakage!)
home_win_prob = model.predict(home_elo=team_elos[game.home_team])  # Elo AFTER game

# ✅ CORRECT - Using pre-game Elo ratings only
home_win_prob = model.predict_from_historical_elos(
    home_team=game.home_team,
    away_team=game.away_team,
    as_of_date=game.game_date - timedelta(days=1)  # Elos from day before game
)
```

### Step 3: Calculate Backtesting Metrics

```python
from analytics.metrics import calculate_brier_score, calculate_log_loss, calculate_accuracy

# Accuracy: % of correct predictions
accuracy = calculate_accuracy(predictions, outcomes)

# Brier Score: Mean squared error of probabilities (lower = better)
brier_score = calculate_brier_score(predictions, outcomes)

# Log Loss: Penalizes confident wrong predictions (lower = better)
log_loss = calculate_log_loss(predictions, outcomes)

print(f"Backtesting Results (2023-2024):")
print(f"  Sample Size: {len(predictions)} games")
print(f"  Accuracy: {accuracy:.2%}")
print(f"  Brier Score: {brier_score:.4f}")
print(f"  Log Loss: {log_loss:.4f}")

# Example output:
# Backtesting Results (2023-2024):
#   Sample Size: 544 games
#   Accuracy: 54.23%
#   Brier Score: 0.1834
#   Log Loss: 0.6712
```

**Metrics Implementation (analytics/metrics.py):**
```python
import numpy as np
from typing import List
from decimal import Decimal

def calculate_accuracy(predictions: List[Decimal], outcomes: List[int]) -> float:
    """
    Calculate classification accuracy (% correct predictions).

    Args:
        predictions: Predicted probabilities [0, 1] (e.g., 0.65 = 65% home win prob)
        outcomes: Actual outcomes (1 = home win, 0 = away win)

    Returns:
        Accuracy as float [0, 1] (e.g., 0.542 = 54.2% accuracy)

    Example:
        >>> predictions = [Decimal("0.65"), Decimal("0.30"), Decimal("0.80")]
        >>> outcomes = [1, 0, 1]  # Home wins, away wins, home wins
        >>> accuracy = calculate_accuracy(predictions, outcomes)
        >>> print(f"{accuracy:.2%}")  # 100.00% (all predictions correct)
    """
    predictions_binary = [1 if p >= 0.5 else 0 for p in predictions]
    correct = sum(pred == actual for pred, actual in zip(predictions_binary, outcomes))
    return correct / len(outcomes)


def calculate_brier_score(predictions: List[Decimal], outcomes: List[int]) -> float:
    """
    Calculate Brier Score (mean squared error of probabilities).

    Formula: BS = (1/N) * Σ(predicted_prob - actual_outcome)²

    Range: [0, 1]
    - 0.00 = perfect calibration (predicted 60% → exactly 60% win)
    - 0.25 = coin flip (random guessing)
    - 1.00 = perfectly wrong (predicted 100% → 0% win)

    Interpretation:
        - Brier ≤ 0.20 = Excellent (sharper than betting markets)
        - Brier 0.20-0.25 = Good (competitive with markets)
        - Brier > 0.25 = Poor (worse than coin flip)

    Example:
        >>> predictions = [Decimal("0.70"), Decimal("0.60"), Decimal("0.80")]
        >>> outcomes = [1, 0, 1]
        >>> brier = calculate_brier_score(predictions, outcomes)
        >>> print(f"Brier Score: {brier:.4f}")
        Brier Score: 0.1767
    """
    predictions_float = [float(p) for p in predictions]
    squared_errors = [(pred - actual) ** 2 for pred, actual in zip(predictions_float, outcomes)]
    return np.mean(squared_errors)


def calculate_log_loss(predictions: List[Decimal], outcomes: List[int], epsilon: float = 1e-15) -> float:
    """
    Calculate Log Loss (cross-entropy loss).

    Formula: LL = -(1/N) * Σ[y*log(p) + (1-y)*log(1-p)]

    Range: [0, ∞]
    - 0.00 = perfect predictions
    - 0.693 = coin flip (random guessing, log(2))
    - Higher = worse predictions

    Penalizes confident wrong predictions heavily:
        - Predict 95% → wrong → Log Loss = 3.00 (massive penalty)
        - Predict 55% → wrong → Log Loss = 0.80 (small penalty)

    Args:
        epsilon: Small constant to prevent log(0) errors

    Example:
        >>> predictions = [Decimal("0.95"), Decimal("0.55")]
        >>> outcomes = [0, 0]  # Both wrong predictions
        >>> log_loss = calculate_log_loss(predictions, outcomes)
        >>> print(f"Log Loss: {log_loss:.4f}")
        Log Loss: 1.90  # High penalty for confident wrong prediction (0.95)
    """
    predictions_float = [float(p) for p in predictions]

    # Clip predictions to [epsilon, 1-epsilon] to prevent log(0)
    predictions_clipped = np.clip(predictions_float, epsilon, 1 - epsilon)

    # Calculate log loss
    log_losses = [
        -(actual * np.log(pred) + (1 - actual) * np.log(1 - pred))
        for pred, actual in zip(predictions_clipped, outcomes)
    ]

    return np.mean(log_losses)
```

### Step 4: Store Backtesting Results

```python
from database.crud_operations import store_model_validation_result
from datetime import datetime

# Store backtesting results in performance_metrics table
validation_id = store_model_validation_result(
    db_session=db_session,
    entity_type="model",
    entity_id=model.model_id,
    validation_type="backtesting",
    validation_dataset="2023-2024_nfl_regular_playoffs",
    sample_size=len(predictions),
    accuracy=accuracy,
    brier_score=brier_score,
    log_loss=log_loss,
    validation_timestamp=datetime.now()
)

print(f"Stored backtesting results: validation_id={validation_id}")
```

---

## 4. Cross-Validation Implementation

### What is Cross-Validation?

**Cross-validation** splits historical data into 5 folds (5 time periods), trains on 4 folds, tests on 1 fold, repeats 5 times. Detects overfitting by testing on multiple unseen time periods.

**Example:**
- **Fold 1:** Train on Sep-Dec 2023, Test on Jan-Mar 2024
- **Fold 2:** Train on Sep-Nov 2023 + Jan-Mar 2024, Test on Dec 2023
- **Fold 3:** Train on Sep-Oct 2023 + Dec 2023-Mar 2024, Test on Nov 2023
- ... (5 folds total)

**Why Temporal Splits?**
NFL data has temporal dependencies (teams improve/decline over season, injuries accumulate). Random shuffling violates time causality. Temporal splits preserve chronological order.

### Step 1: Generate 5-Fold Temporal Splits

```python
from sklearn.model_selection import TimeSeriesSplit
import numpy as np

def generate_temporal_folds(games: List[Game], n_folds: int = 5) -> List[Dict]:
    """
    Generate temporal cross-validation folds.

    Returns:
        List of dicts with keys: {train_indices, test_indices, train_games, test_games}

    Educational Note:
        TimeSeriesSplit creates EXPANDING train sets (not sliding windows).
        - Fold 1: Train on 20% of data, Test on 20%
        - Fold 2: Train on 40% of data, Test on 20%
        - Fold 3: Train on 60% of data, Test on 20%
        - Fold 4: Train on 80% of data, Test on 20%
        - Fold 5: Train on 80% of data, Test on 20%

        This prevents training on future data to predict past data.
    """
    tscv = TimeSeriesSplit(n_splits=n_folds)
    game_indices = np.arange(len(games))

    folds = []
    for fold_num, (train_idx, test_idx) in enumerate(tscv.split(game_indices), start=1):
        train_games = [games[i] for i in train_idx]
        test_games = [games[i] for i in test_idx]

        folds.append({
            "fold_number": fold_num,
            "train_indices": train_idx.tolist(),
            "test_indices": test_idx.tolist(),
            "train_games": train_games,
            "test_games": test_games,
            "train_start_date": train_games[0].game_date,
            "train_end_date": train_games[-1].game_date,
            "test_start_date": test_games[0].game_date,
            "test_end_date": test_games[-1].game_date
        })

    return folds


# Generate folds
games = fetch_games_for_backtesting(db_session, "nfl", datetime(2023, 9, 1), datetime(2024, 12, 31))
folds = generate_temporal_folds(games, n_folds=5)

for fold in folds:
    print(f"Fold {fold['fold_number']}:")
    print(f"  Train: {fold['train_start_date']} to {fold['train_end_date']} ({len(fold['train_games'])} games)")
    print(f"  Test:  {fold['test_start_date']} to {fold['test_end_date']} ({len(fold['test_games'])} games)")
```

**Expected Output:**
```
Fold 1:
  Train: 2023-09-07 to 2023-12-31 (218 games)
  Test:  2024-01-01 to 2024-04-30 (109 games)
Fold 2:
  Train: 2023-09-07 to 2024-04-30 (327 games)
  Test:  2024-05-01 to 2024-08-31 (109 games)
Fold 3:
  Train: 2023-09-07 to 2024-08-31 (436 games)
  Test:  2024-09-01 to 2024-12-31 (108 games)
...
```

### Step 2: Train and Evaluate on Each Fold

```python
from analytics.metrics import calculate_accuracy, calculate_brier_score, calculate_log_loss

fold_results = []

for fold in folds:
    # Train model on train_games
    model.train(games=fold['train_games'])

    # Generate predictions on test_games
    test_predictions = []
    test_outcomes = []

    for game in fold['test_games']:
        pred = model.predict(
            home_team=game.home_team,
            away_team=game.away_team,
            game_date=game.game_date,
            is_neutral_site=game.is_neutral_site
        )
        outcome = 1 if game.home_final_score > game.away_final_score else 0

        test_predictions.append(pred)
        test_outcomes.append(outcome)

    # Calculate metrics
    fold_result = {
        "fold_number": fold['fold_number'],
        "sample_size": len(test_predictions),
        "accuracy": calculate_accuracy(test_predictions, test_outcomes),
        "brier_score": calculate_brier_score(test_predictions, test_outcomes),
        "log_loss": calculate_log_loss(test_predictions, test_outcomes)
    }

    fold_results.append(fold_result)

    print(f"Fold {fold_result['fold_number']}: "
          f"Accuracy={fold_result['accuracy']:.2%}, "
          f"Brier={fold_result['brier_score']:.4f}")
```

### Step 3: Aggregate Cross-Validation Results

```python
import numpy as np

# Calculate mean and std dev across folds
cv_summary = {
    "n_folds": len(fold_results),
    "avg_accuracy": np.mean([f['accuracy'] for f in fold_results]),
    "std_accuracy": np.std([f['accuracy'] for f in fold_results]),
    "avg_brier_score": np.mean([f['brier_score'] for f in fold_results]),
    "std_brier_score": np.std([f['brier_score'] for f in fold_results]),
    "avg_log_loss": np.mean([f['log_loss'] for f in fold_results]),
    "std_log_loss": np.std([f['log_loss'] for f in fold_results]),
    "fold_results": fold_results
}

print(f"\nCross-Validation Summary ({cv_summary['n_folds']} folds):")
print(f"  Accuracy: {cv_summary['avg_accuracy']:.2%} ± {cv_summary['std_accuracy']:.2%}")
print(f"  Brier Score: {cv_summary['avg_brier_score']:.4f} ± {cv_summary['std_brier_score']:.4f}")
print(f"  Log Loss: {cv_summary['avg_log_loss']:.4f} ± {cv_summary['std_log_loss']:.4f}")

# Check for overfitting (high variance across folds)
if cv_summary['std_accuracy'] > 0.05:  # >5% std dev
    print("⚠️  WARNING: High variance across folds - possible overfitting!")
else:
    print("✅ Low variance across folds - model generalizes well")
```

**Expected Output:**
```
Cross-Validation Summary (5 folds):
  Accuracy: 53.84% ± 2.14%
  Brier Score: 0.1867 ± 0.0123
  Log Loss: 0.6834 ± 0.0456
✅ Low variance across folds - model generalizes well
```

**Interpreting Variance:**
- **Low variance (std < 3%):** Model generalizes well, consistent across time periods
- **High variance (std > 5%):** Model overfit to specific time periods, inconsistent

---

## 5. Holdout Validation

### What is Holdout Validation?

**Holdout validation** tests model on completely unseen data (2024 Q4 games) that was NEVER used during training or cross-validation. This simulates production deployment.

**Why Holdout Matters:**
Cross-validation can still overfit if you tune hyperparameters based on CV results. Holdout provides final unbiased estimate before activation.

### Step 1: Define Holdout Period

```python
from datetime import datetime

# Holdout period: 2024 Q4 (Oct-Dec 2024)
HOLDOUT_START = datetime(2024, 10, 1)
HOLDOUT_END = datetime(2024, 12, 31)

# Fetch holdout games (must be completed)
holdout_games = fetch_games_for_backtesting(
    db_session=db_session,
    league="nfl",
    start_date=HOLDOUT_START,
    end_date=HOLDOUT_END,
    include_playoffs=True
)

print(f"Holdout set: {len(holdout_games)} games (2024 Q4)")
# Expected: ~140 games (13 weeks * ~16 games/week)
```

### Step 2: Generate Holdout Predictions

```python
# Train model on ALL data BEFORE holdout period
train_games = fetch_games_for_backtesting(
    db_session=db_session,
    league="nfl",
    start_date=datetime(2023, 9, 1),
    end_date=HOLDOUT_START - timedelta(days=1)  # Train up to Sep 30, 2024
)

model.train(games=train_games)
print(f"Model trained on {len(train_games)} games (2023-09 to 2024-09)")

# Generate predictions on holdout set
holdout_predictions = []
holdout_outcomes = []

for game in holdout_games:
    pred = model.predict(
        home_team=game.home_team,
        away_team=game.away_team,
        game_date=game.game_date,
        is_neutral_site=game.is_neutral_site
    )
    outcome = 1 if game.home_final_score > game.away_final_score else 0

    holdout_predictions.append(pred)
    holdout_outcomes.append(outcome)
```

### Step 3: Calculate Holdout Metrics

```python
from analytics.metrics import calculate_accuracy, calculate_brier_score, calculate_log_loss, calculate_ece

holdout_results = {
    "sample_size": len(holdout_predictions),
    "accuracy": calculate_accuracy(holdout_predictions, holdout_outcomes),
    "brier_score": calculate_brier_score(holdout_predictions, holdout_outcomes),
    "log_loss": calculate_log_loss(holdout_predictions, holdout_outcomes),
    "expected_calibration_error": calculate_ece(holdout_predictions, holdout_outcomes, n_bins=10)
}

print(f"\nHoldout Validation Results (2024 Q4):")
print(f"  Sample Size: {holdout_results['sample_size']} games")
print(f"  Accuracy: {holdout_results['accuracy']:.2%}")
print(f"  Brier Score: {holdout_results['brier_score']:.4f}")
print(f"  Log Loss: {holdout_results['log_loss']:.4f}")
print(f"  ECE: {holdout_results['expected_calibration_error']:.4f}")
```

### Step 4: Check Activation Criteria

```python
def meets_activation_criteria(holdout_results: Dict) -> Dict:
    """
    Check if model meets all 8 activation criteria.

    Criteria:
        1. Sample size ≥ 100 games (statistical significance)
        2. Accuracy ≥ 52% (above coin flip + juice)
        3. Brier Score ≤ 0.20 (excellent calibration)
        4. ECE ≤ 0.10 (well-calibrated probabilities)
        5. Log Loss ≤ 0.50 (confident predictions)
        6. No major calibration gaps (reliability diagram)
        7. Consistent performance across leagues (NFL, NCAAF)
        8. Approved by data science lead

    Returns:
        {
            "meets_criteria": True/False,
            "passed_checks": ["sample_size", "accuracy", ...],
            "failed_checks": ["log_loss"],
            "notes": "Log Loss 0.52 exceeds threshold 0.50 (marginal failure)"
        }
    """
    passed = []
    failed = []
    notes = []

    # Check 1: Sample size
    if holdout_results['sample_size'] >= 100:
        passed.append("sample_size")
    else:
        failed.append("sample_size")
        notes.append(f"Sample size {holdout_results['sample_size']} < 100 (need more games)")

    # Check 2: Accuracy
    if holdout_results['accuracy'] >= 0.52:
        passed.append("accuracy")
    else:
        failed.append("accuracy")
        notes.append(f"Accuracy {holdout_results['accuracy']:.2%} < 52% (below breakeven)")

    # Check 3: Brier Score
    if holdout_results['brier_score'] <= 0.20:
        passed.append("brier_score")
    else:
        failed.append("brier_score")
        notes.append(f"Brier {holdout_results['brier_score']:.4f} > 0.20 (poor calibration)")

    # Check 4: ECE
    if holdout_results['expected_calibration_error'] <= 0.10:
        passed.append("ece")
    else:
        failed.append("ece")
        notes.append(f"ECE {holdout_results['expected_calibration_error']:.4f} > 0.10 (miscalibrated)")

    # Check 5: Log Loss
    if holdout_results['log_loss'] <= 0.50:
        passed.append("log_loss")
    else:
        failed.append("log_loss")
        notes.append(f"Log Loss {holdout_results['log_loss']:.4f} > 0.50 (overconfident predictions)")

    meets_criteria = len(failed) == 0

    return {
        "meets_criteria": meets_criteria,
        "passed_checks": passed,
        "failed_checks": failed,
        "notes": "; ".join(notes) if notes else "All automated checks passed"
    }


# Check activation criteria
activation_check = meets_activation_criteria(holdout_results)

if activation_check['meets_criteria']:
    print("\n✅ Model PASSED all activation criteria - ready for production!")
else:
    print(f"\n❌ Model FAILED activation criteria:")
    for check in activation_check['failed_checks']:
        print(f"  - {check}")
    print(f"\nNotes: {activation_check['notes']}")
```

---

## 6. Calibration Metrics Deep Dive

### Brier Score

**Formula:** `Brier Score = (1/N) * Σ(predicted_prob - actual_outcome)²`

**Interpretation:**
- **0.00:** Perfect calibration (predicted 60% → exactly 60% of those bets won)
- **0.20:** Excellent (sharper than betting markets, profitable edge)
- **0.25:** Coin flip (random guessing, no predictive power)
- **1.00:** Perfectly wrong (predicted 100% → 0% won)

**Example Calculation:**
```python
predictions = [0.70, 0.60, 0.80, 0.55]
outcomes =     [1,    0,    1,    0]

squared_errors = [
    (0.70 - 1)² = 0.09,
    (0.60 - 0)² = 0.36,
    (0.80 - 1)² = 0.04,
    (0.55 - 0)² = 0.3025
]

brier_score = (0.09 + 0.36 + 0.04 + 0.3025) / 4 = 0.1981
```

**Actionable Insights:**
- **Brier ≤ 0.18:** Elite model, sharper than Pinnacle sportsbook
- **Brier 0.18-0.20:** Excellent, competitive with betting markets
- **Brier 0.20-0.25:** Good, still profitable with proper Kelly sizing
- **Brier > 0.25:** Poor, unprofitable (worse than coin flip)

---

### Expected Calibration Error (ECE)

**What is ECE?**
ECE measures how well predicted probabilities match observed frequencies across probability bins.

**Formula:**
```
ECE = Σ(|n_bin / N|) * |accuracy_bin - avg_confidence_bin|

Where:
- n_bin = number of predictions in bin
- accuracy_bin = % of correct predictions in bin
- avg_confidence_bin = average predicted probability in bin
```

**Example:**
```python
# Bin 1: Predictions 50-60%
predictions_bin1 = [0.52, 0.55, 0.58, 0.53]
outcomes_bin1 = [1, 0, 1, 1]  # 75% win rate

accuracy_bin1 = 0.75  # 3/4 wins
avg_confidence_bin1 = 0.545  # (0.52+0.55+0.58+0.53)/4

calibration_error_bin1 = |0.75 - 0.545| = 0.205  # Overconfident by 20.5%

# Bin 2: Predictions 60-70%
predictions_bin2 = [0.62, 0.65, 0.68]
outcomes_bin2 = [1, 1, 0]  # 67% win rate

accuracy_bin2 = 0.67  # 2/3 wins
avg_confidence_bin2 = 0.65  # (0.62+0.65+0.68)/3

calibration_error_bin2 = |0.67 - 0.65| = 0.02  # Well-calibrated!

# ECE = weighted average
ECE = (4/7 * 0.205) + (3/7 * 0.02) = 0.125
```

**Implementation:**
```python
import numpy as np

def calculate_ece(predictions: List[Decimal], outcomes: List[int], n_bins: int = 10) -> float:
    """
    Calculate Expected Calibration Error (ECE).

    Args:
        n_bins: Number of probability bins (default 10: [0-0.1, 0.1-0.2, ..., 0.9-1.0])

    Returns:
        ECE as float [0, 1] (lower = better)

    Interpretation:
        - ECE ≤ 0.05: Excellently calibrated
        - ECE 0.05-0.10: Well-calibrated
        - ECE 0.10-0.15: Moderately calibrated (acceptable)
        - ECE > 0.15: Poorly calibrated (need recalibration)
    """
    predictions_float = np.array([float(p) for p in predictions])
    outcomes_array = np.array(outcomes)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        # Find predictions in this bin
        in_bin = (predictions_float > bin_lower) & (predictions_float <= bin_upper)
        n_in_bin = in_bin.sum()

        if n_in_bin > 0:
            # Calculate bin accuracy and confidence
            bin_accuracy = outcomes_array[in_bin].mean()
            bin_confidence = predictions_float[in_bin].mean()

            # Weighted calibration error
            ece += (n_in_bin / len(predictions)) * abs(bin_accuracy - bin_confidence)

    return ece
```

---

### Log Loss

**Formula:** `Log Loss = -(1/N) * Σ[y*log(p) + (1-y)*log(1-p)]`

**Why Log Loss Matters:**
Log Loss penalizes confident wrong predictions exponentially. A model that predicts 95% confidence and is wrong suffers a massive penalty.

**Example:**
```python
# Scenario 1: Confident wrong prediction
prediction = 0.95
outcome = 0  # Wrong!
log_loss_1 = -(0 * log(0.95) + 1 * log(0.05)) = -log(0.05) = 2.996

# Scenario 2: Modest wrong prediction
prediction = 0.55
outcome = 0  # Wrong
log_loss_2 = -(0 * log(0.55) + 1 * log(0.45)) = -log(0.45) = 0.798

# Confident wrong prediction penalized 3.7x more!
```

**Actionable Insights:**
- **Log Loss ≤ 0.50:** Excellent (confident and accurate predictions)
- **Log Loss 0.50-0.693:** Good (better than coin flip)
- **Log Loss > 0.693:** Poor (worse than random guessing, log(2) = 0.693)

---

## 7. Reliability Diagrams

### What is a Reliability Diagram?

A **reliability diagram** plots predicted probabilities (x-axis) vs. observed frequencies (y-axis). Perfect calibration = diagonal line.

**Example:**
- Model predicts 70% win probability for 100 games
- 70 of those games are wins (70% observed frequency)
- Point (0.70, 0.70) on diagonal = perfectly calibrated

**Implementation:**
```python
import matplotlib.pyplot as plt
import numpy as np

def plot_reliability_diagram(
    predictions: List[Decimal],
    outcomes: List[int],
    n_bins: int = 10,
    save_path: str = "reliability_diagram.png"
):
    """
    Generate reliability diagram (calibration plot).

    Args:
        predictions: Predicted probabilities [0, 1]
        outcomes: Actual outcomes (1 = event occurred, 0 = did not occur)
        n_bins: Number of bins for grouping predictions
        save_path: Path to save plot image

    Visual Interpretation:
        - Points on diagonal = well-calibrated
        - Points above diagonal = underconfident (predicted 60%, actually 75%)
        - Points below diagonal = overconfident (predicted 80%, actually 65%)
    """
    predictions_float = np.array([float(p) for p in predictions])
    outcomes_array = np.array(outcomes)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_centers = []
    observed_frequencies = []
    bin_counts = []

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        in_bin = (predictions_float > bin_lower) & (predictions_float <= bin_upper)
        n_in_bin = in_bin.sum()

        if n_in_bin > 0:
            bin_center = (bin_lower + bin_upper) / 2
            observed_freq = outcomes_array[in_bin].mean()

            bin_centers.append(bin_center)
            observed_frequencies.append(observed_freq)
            bin_counts.append(n_in_bin)

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot calibration curve
    ax.plot(bin_centers, observed_frequencies, 'o-', linewidth=2, markersize=8, label='Model Calibration')

    # Plot perfect calibration line (diagonal)
    ax.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Perfect Calibration')

    # Add bin counts as text labels
    for x, y, count in zip(bin_centers, observed_frequencies, bin_counts):
        ax.text(x, y + 0.03, f'n={count}', ha='center', fontsize=8)

    # Formatting
    ax.set_xlabel('Predicted Probability', fontsize=12)
    ax.set_ylabel('Observed Frequency', fontsize=12)
    ax.set_title('Reliability Diagram (Calibration Plot)', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])

    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    print(f"Reliability diagram saved to {save_path}")

    return fig, ax


# Example usage
from models.elo_model import EloModel
from analytics.model_evaluator import ModelEvaluator

model = EloModel(version="v2.0")
evaluator = ModelEvaluator(model=model, db_session=get_db_session())

holdout_results = evaluator.run_holdout_validation(
    holdout_start="2024-10-01",
    holdout_end="2024-12-31"
)

plot_reliability_diagram(
    predictions=holdout_results['predictions'],
    outcomes=holdout_results['outcomes'],
    n_bins=10,
    save_path="outputs/elo_model_v2.0_reliability.png"
)
```

**Example Output:**

```
Reliability Diagram:
  Bin [0.5-0.6]: Predicted 0.55, Observed 0.52 (n=42) ✅ Well-calibrated
  Bin [0.6-0.7]: Predicted 0.65, Observed 0.68 (n=38) ✅ Slightly underconfident
  Bin [0.7-0.8]: Predicted 0.75, Observed 0.71 (n=24) ⚠️ Slightly overconfident
  Bin [0.8-0.9]: Predicted 0.85, Observed 0.78 (n=12) ⚠️ Overconfident
```

---

## 8. ModelEvaluator Class Usage

### Complete Example: End-to-End Evaluation

```python
from analytics.model_evaluator import ModelEvaluator
from models.elo_model import EloModel
from database.connection import get_db_session
from datetime import datetime

# Initialize
model = EloModel(version="v2.0")
db_session = get_db_session()
evaluator = ModelEvaluator(model=model, db_session=db_session)

# Stage 1: Backtesting (2023-2024 historical data)
print("=== Stage 1: Backtesting ===")
backtest_results = evaluator.run_backtesting(
    start_date=datetime(2023, 9, 1),
    end_date=datetime(2024, 12, 31),
    league="nfl",
    include_playoffs=True
)

print(f"Sample Size: {backtest_results['sample_size']} games")
print(f"Accuracy: {backtest_results['accuracy']:.2%}")
print(f"Brier Score: {backtest_results['brier_score']:.4f}")
print(f"Log Loss: {backtest_results['log_loss']:.4f}")

# Stage 2: Cross-Validation (5-fold temporal)
print("\n=== Stage 2: Cross-Validation ===")
cv_results = evaluator.run_cross_validation(
    start_date=datetime(2023, 9, 1),
    end_date=datetime(2024, 12, 31),
    n_folds=5,
    league="nfl"
)

print(f"Avg Accuracy: {cv_results['avg_accuracy']:.2%} ± {cv_results['std_accuracy']:.2%}")
print(f"Avg Brier: {cv_results['avg_brier_score']:.4f} ± {cv_results['std_brier_score']:.4f}")

if cv_results['std_accuracy'] > 0.05:
    print("⚠️  WARNING: High variance - possible overfitting")
else:
    print("✅ Low variance - model generalizes well")

# Stage 3: Holdout Validation (2024 Q4 unseen data)
print("\n=== Stage 3: Holdout Validation ===")
holdout_results = evaluator.run_holdout_validation(
    holdout_start=datetime(2024, 10, 1),
    holdout_end=datetime(2024, 12, 31),
    league="nfl"
)

print(f"Sample Size: {holdout_results['sample_size']} games")
print(f"Accuracy: {holdout_results['accuracy']:.2%}")
print(f"Brier Score: {holdout_results['brier_score']:.4f}")
print(f"ECE: {holdout_results['ece']:.4f}")
print(f"Log Loss: {holdout_results['log_loss']:.4f}")

# Generate reliability diagram
evaluator.plot_reliability_diagram(
    predictions=holdout_results['predictions'],
    outcomes=holdout_results['outcomes'],
    save_path=f"outputs/{model.model_name}_{model.model_version}_reliability.png"
)

# Check activation criteria
print("\n=== Activation Criteria Check ===")
activation_check = evaluator.check_activation_criteria(holdout_results)

if activation_check['meets_criteria']:
    print("✅ Model PASSED all activation criteria!")
    print(f"Passed checks: {', '.join(activation_check['passed_checks'])}")

    # Store validation results in database
    evaluator.store_validation_results(
        backtest_results=backtest_results,
        cv_results=cv_results,
        holdout_results=holdout_results
    )

    print(f"\n✅ Model {model.model_name} {model.model_version} ready for production activation!")
else:
    print("❌ Model FAILED activation criteria:")
    for check in activation_check['failed_checks']:
        print(f"  - {check}")
    print(f"\nNotes: {activation_check['notes']}")
    print("\n⚠️  Model requires improvement before production deployment.")
```

---

## 9. Activation Criteria Checklist

### 8-Point Activation Checklist

Before deploying model to production, verify ALL 8 criteria:

#### 1. **Sample Size ≥ 100 games** ✅
- **Why:** Small samples have high variance (20 games = 45-65% accuracy range)
- **Check:** `holdout_results['sample_size'] >= 100`
- **If Failed:** Wait for more games, use larger holdout period

#### 2. **Accuracy ≥ 52%** ✅
- **Why:** 52% = breakeven with -110 odds (10% juice)
- **Check:** `holdout_results['accuracy'] >= 0.52`
- **If Failed:** Model unprofitable, retrain or add features

#### 3. **Brier Score ≤ 0.20** ✅
- **Why:** Brier > 0.20 = poor calibration, unprofitable edge
- **Check:** `holdout_results['brier_score'] <= 0.20`
- **If Failed:** Recalibrate probabilities, improve model

#### 4. **ECE ≤ 0.10** ✅
- **Why:** High ECE = miscalibrated probabilities (overconfident/underconfident)
- **Check:** `holdout_results['ece'] <= 0.10`
- **If Failed:** Apply Platt scaling or isotonic regression

#### 5. **Log Loss ≤ 0.50** ✅
- **Why:** Log Loss > 0.50 = overconfident wrong predictions
- **Check:** `holdout_results['log_loss'] <= 0.50`
- **If Failed:** Reduce model confidence, add regularization

#### 6. **No Major Calibration Gaps** ✅
- **Why:** Poor calibration in specific ranges = unprofitable bets
- **Check:** Review reliability diagram, no bins >15% off diagonal
- **If Failed:** Recalibrate specific probability ranges

#### 7. **Consistent Performance Across Leagues** ✅
- **Why:** Model might work for NFL but fail for NCAAF
- **Check:** Separate holdout validation for NFL and NCAAF, both meet criteria
- **If Failed:** Train separate models or add league-specific features

#### 8. **Data Science Lead Approval** ✅
- **Why:** Human review catches edge cases automated checks miss
- **Check:** Code review + approval from senior data scientist
- **If Failed:** Address reviewer feedback, re-validate

---

### Activation Decision Matrix

| Criteria | Threshold | Elo Model v2.0 | Ensemble v1.0 | Status |
|----------|-----------|----------------|---------------|--------|
| Sample Size | ≥100 | 142 games ✅ | 138 games ✅ | PASS |
| Accuracy | ≥52% | 54.2% ✅ | 56.1% ✅ | PASS |
| Brier Score | ≤0.20 | 0.1834 ✅ | 0.1721 ✅ | PASS |
| ECE | ≤0.10 | 0.0834 ✅ | 0.0712 ✅ | PASS |
| Log Loss | ≤0.50 | 0.4523 ✅ | 0.4189 ✅ | PASS |
| Calibration | No gaps >15% | ✅ | ✅ | PASS |
| NFL/NCAAF | Both ≥52% | 54.2%/53.8% ✅ | 56.1%/55.3% ✅ | PASS |
| Approval | Required | ✅ Approved | ⏳ Pending | PENDING |

**Decision:**
- **Elo Model v2.0:** ✅ ACTIVATE (all criteria met)
- **Ensemble v1.0:** ⏳ PENDING REVIEW (awaiting approval)

---

## 10. Common Pitfalls

### Pitfall 1: Data Leakage

**Problem:** Using future information to predict past outcomes (inflates accuracy artificially).

**Examples:**
```python
# ❌ WRONG - Using final score to predict winner
home_win_prob = model.predict(home_score=27, away_score=24)  # Data leakage!

# ❌ WRONG - Using post-game Elo ratings
home_win_prob = model.predict(home_elo=1650)  # Elo AFTER game, not before

# ❌ WRONG - Using game outcome in feature engineering
features = {
    "home_team_won_last_game": True,  # OK (past game)
    "home_team_will_win_this_game": True  # ❌ Data leakage! (future outcome)
}

# ✅ CORRECT - Only use pre-game information
home_win_prob = model.predict_from_historical_state(
    home_team="Kansas City Chiefs",
    away_team="Buffalo Bills",
    as_of_date=game_date - timedelta(days=1)  # Day before game
)
```

**How to Detect:**
- Backtesting accuracy >70% = suspiciously high (likely data leakage)
- Holdout accuracy 20% lower than backtesting = data leakage in backtesting

---

### Pitfall 2: Overfitting

**Problem:** Model memorizes training data noise, fails to generalize.

**Symptoms:**
- High training accuracy (65%), low test accuracy (48%)
- High variance across cross-validation folds (52% → 48% → 61% → 45%)

**Solutions:**
```python
# Solution 1: Regularization (L1/L2)
from sklearn.linear_model import LogisticRegression

model = LogisticRegression(penalty='l2', C=1.0)  # L2 regularization

# Solution 2: Reduce model complexity
# Before: 50 features → 15 features (feature selection)
# Remove correlated features (e.g., keep "home_elo", remove "home_wins")

# Solution 3: Early stopping (neural networks)
from tensorflow.keras.callbacks import EarlyStopping

early_stop = EarlyStopping(monitor='val_loss', patience=5)
model.fit(X_train, y_train, validation_split=0.2, callbacks=[early_stop])

# Solution 4: Cross-validation
# Use 5-fold CV to detect overfitting early
```

---

### Pitfall 3: P-Hacking

**Problem:** Testing 100 model variants, picking the best holdout result = false discovery.

**Example:**
```python
# ❌ WRONG - Testing 50 hyperparameter combinations on holdout set
for learning_rate in [0.001, 0.01, 0.1]:
    for n_estimators in [10, 50, 100, 500]:
        for max_depth in [3, 5, 10]:
            model = train_model(lr=learning_rate, n_est=n_estimators, depth=max_depth)
            holdout_accuracy = evaluate_on_holdout(model)
            if holdout_accuracy > best_accuracy:
                best_model = model  # ❌ Overfitting to holdout set!

# ✅ CORRECT - Tune hyperparameters on cross-validation, test once on holdout
best_hyperparams = tune_hyperparameters_cv(X_train, y_train, cv=5)
model = train_model(**best_hyperparams)
holdout_accuracy = evaluate_on_holdout(model)  # Only test ONCE on holdout
```

**Solution:** Treat holdout set as sacred - test only ONCE after hyperparameter tuning on CV.

---

### Pitfall 4: Insufficient Sample Size

**Problem:** 20 test games = 95% confidence interval of [35%, 75%] accuracy (too wide!).

**Example:**
```python
# 20 games, 12 wins = 60% accuracy
# Binomial 95% CI: [38.7%, 78.9%]
# Conclusion: Can't distinguish 60% model from 50% coin flip

# 100 games, 60 wins = 60% accuracy
# Binomial 95% CI: [50.4%, 69.0%]
# Conclusion: Likely better than 50% (CI excludes 50%)
```

**Solution:** Always require ≥100 games in holdout set before activation decision.

---

## 11. Troubleshooting

### Issue 1: Holdout Accuracy << Backtest Accuracy

**Symptom:** Backtesting 62% accuracy, Holdout 49% accuracy

**Diagnosis:** Data leakage in backtesting OR model overfit to 2023-2024 data

**Fix:**
1. Review backtesting code for data leakage (using final scores, post-game Elos)
2. Check cross-validation variance (high variance = overfitting)
3. Add regularization (L2 penalty, reduce features)
4. Use simpler model (logistic regression instead of deep neural network)

---

### Issue 2: Poor Calibration (ECE > 0.15)

**Symptom:** Model predicts 70% win probability, but only 52% of those bets win

**Diagnosis:** Model outputs not calibrated (logistic regression outputs ≠ true probabilities)

**Fix: Platt Scaling (Logistic Calibration)**
```python
from sklearn.calibration import CalibratedClassifierCV

# Train base model
base_model = LogisticRegression()
base_model.fit(X_train, y_train)

# Calibrate on validation set
calibrated_model = CalibratedClassifierCV(base_model, method='sigmoid', cv='prefit')
calibrated_model.fit(X_val, y_val)

# Now calibrated_model.predict_proba() gives calibrated probabilities
calibrated_probs = calibrated_model.predict_proba(X_test)[:, 1]
```

**Alternative: Isotonic Regression (Non-Parametric Calibration)**
```python
calibrated_model = CalibratedClassifierCV(base_model, method='isotonic', cv='prefit')
calibrated_model.fit(X_val, y_val)
```

---

### Issue 3: Cross-Validation High Variance

**Symptom:** CV results: [58%, 48%, 62%, 45%, 55%] (std = 6.5%)

**Diagnosis:** Model unstable across time periods (overfitting OR insufficient data in early folds)

**Fix:**
1. Check fold sizes (early folds might have only 50 games → high variance)
2. Increase training data (2021-2024 instead of 2023-2024)
3. Add regularization (prevent overfitting to specific time periods)
4. Use ensemble methods (Random Forest averages multiple models → lower variance)

---

### Issue 4: Model Works for NFL but Not NCAAF

**Symptom:** NFL holdout 56% accuracy, NCAAF holdout 48% accuracy

**Diagnosis:** Model features optimized for NFL (e.g., NFL Elo ratings don't transfer to NCAAF)

**Fix:**
1. Train separate models for NFL and NCAAF
2. Add league-specific features (recruiting rankings for NCAAF, playoff experience for NFL)
3. Use hierarchical model (shared base features + league-specific layers)

---

**END OF MODEL_EVALUATION_GUIDE_V1.0.md**

This guide provides comprehensive instructions for evaluating probability models before production deployment. Follow the 3-stage evaluation pipeline (backtesting → cross-validation → holdout), check all 8 activation criteria, and avoid common pitfalls (data leakage, overfitting, p-hacking). Always prioritize statistical rigor over convenience - unevaluated models lose money.
