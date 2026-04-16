"""CRUD operations for edges, evaluations, backtesting, predictions, and performance.

Extracted from crud_operations.py during Phase 1c domain split.

Tables covered:
    - edges: Identified trading edge records
    - evaluation_runs: Model evaluation session records
    - backtesting_runs: Strategy backtesting session records
    - predictions: Individual model predictions within evaluation runs
    - performance_metrics: Aggregated strategy/model performance metrics
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

from .connection import fetch_all, fetch_one, get_cursor
from .crud_shared import (
    VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION,
    ExecutionEnvironment,
    validate_decimal,
)

logger = logging.getLogger(__name__)

_VALID_RUN_TYPES = frozenset({"model", "strategy", "ensemble"})
_VALID_RUN_STATUSES = frozenset({"running", "completed", "failed", "cancelled"})
_VALID_ENTITY_TYPES = frozenset({"model", "strategy", "evaluation_run", "backtest_run"})


# =============================================================================
# EDGE OPERATIONS
# =============================================================================
#
# Migration 0023: edges table enriched with analytics-ready columns.
#   - probability_matrix_id dropped (dead FK)
#   - New columns: actual_outcome, settlement_value, resolved_at, strategy_id,
#     edge_status, yes_ask_price, no_ask_price, spread, volume, open_interest,
#     last_price, liquidity, category, subcategory, execution_environment
#   - New views: current_edges (recreated), edge_lifecycle (computed P&L)
#
# SCD Type 2: edges use row_current_ind versioning.
#   - create_edge: sets row_current_ind = TRUE
#   - update_edge_outcome / update_edge_status: direct updates (lifecycle
#     events, not version changes)
# =============================================================================


def create_edge(
    market_id: int,
    model_id: int,
    expected_value: Decimal,
    true_win_probability: Decimal,
    market_implied_probability: Decimal,
    market_price: Decimal,
    execution_environment: ExecutionEnvironment,
    yes_ask_price: Decimal | None = None,
    no_ask_price: Decimal | None = None,
    spread: Decimal | None = None,
    volume: int | None = None,
    open_interest: int | None = None,
    last_price: Decimal | None = None,
    liquidity: Decimal | None = None,
    strategy_id: int | None = None,
    confidence_level: str | None = None,
    confidence_metrics: dict | None = None,
    recommended_action: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
) -> int:
    """
    Create a new edge record with SCD Type 2 row_current_ind = TRUE.

    An edge represents a detected positive expected value opportunity: the
    difference between the model's predicted probability and the market's
    implied probability. This function captures the full market microstructure
    snapshot at the moment of edge detection.

    Args:
        market_id: Integer FK to markets(id) surrogate PK
        model_id: FK to probability_models(model_id) that detected this edge
        expected_value: Expected value of the edge as DECIMAL(10,4)
        true_win_probability: Model's predicted probability [0, 1]
        market_implied_probability: Market-implied probability [0, 1]
        market_price: Market price at detection [0, 1]
        yes_ask_price: Kalshi YES ask price snapshot at detection
        no_ask_price: Kalshi NO ask price snapshot at detection
        spread: Bid-ask spread as DECIMAL(10,4)
        volume: Trading volume at detection
        open_interest: Open interest at detection
        last_price: Last traded price at detection
        liquidity: Market liquidity metric
        strategy_id: FK to strategies(strategy_id) for attribution
        confidence_level: 'high', 'medium', or 'low'
        confidence_metrics: Additional confidence data as JSONB
        recommended_action: 'auto_execute', 'alert', or 'ignore'
        category: Market category (e.g., 'sports', 'politics')
        subcategory: Market subcategory (e.g., 'nfl', 'ncaaf')
        execution_environment: Execution context — REQUIRED, no default. Must
            be one of 'live', 'paper', or 'backtest'. Note: 'unknown' is
            reserved for ``account_balance`` only and is not valid here.
            Edges are signal sources for trading; tagging an edge with the
            wrong environment contaminates analytics queries that filter by
            environment. The optional-default precedent removed in the
            #622+#686 synthesis PR was the literal cause of the
            #622/#662/#686 bug class. See findings_622_686_synthesis.md.

    Returns:
        Integer surrogate PK (edges.id) of the newly created edge.

    Educational Note:
        Dual-Key Structure (Migration 017):
        - id SERIAL (surrogate key) - returned by this function
        - edge_key VARCHAR (business key) - auto-generated as EDGE-{id}
        - Enables SCD Type 2 versioning (multiple versions of same edge)

        Edge Lifecycle (Migration 0023):
        - Edges start as 'detected' and progress through:
          detected -> recommended -> acted_on -> settled/expired/void
        - Outcome tracking via actual_outcome + settlement_value
        - P&L computed in edge_lifecycle view

    Example:
        >>> edge_pk = create_edge(
        ...     market_id=42,
        ...     model_id=2,
        ...     expected_value=Decimal("0.0500"),
        ...     true_win_probability=Decimal("0.5700"),
        ...     market_implied_probability=Decimal("0.5200"),
        ...     market_price=Decimal("0.5200"),
        ...     yes_ask_price=Decimal("0.5300"),
        ...     no_ask_price=Decimal("0.4800"),
        ...     strategy_id=1,
        ...     confidence_level='high',
        ...     execution_environment='paper',
        ... )
        >>> # Returns surrogate id (e.g., 1), edge_key auto-set to 'EDGE-1'

    References:
        - Migration 0023: edges enrichment and cleanup
        - ADR-002: Decimal Precision for All Financial Data
    """
    # Validate execution_environment before any DB interaction. Typo defense
    # (Marvin's recommendation from #662). Edges follow the trade/position
    # 3-value rule, not the 4-value account_balance rule.
    if execution_environment not in VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION:
        msg = (
            f"Invalid execution_environment: {execution_environment!r}. "
            f"Must be one of {sorted(VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION)}. "
            f"Note: 'unknown' is reserved for account_balance only."
        )
        raise ValueError(msg)

    # Runtime type validation (enforces Decimal precision)
    expected_value = validate_decimal(expected_value, "expected_value")
    true_win_probability = validate_decimal(true_win_probability, "true_win_probability")
    market_implied_probability = validate_decimal(
        market_implied_probability, "market_implied_probability"
    )
    market_price = validate_decimal(market_price, "market_price")

    if yes_ask_price is not None:
        yes_ask_price = validate_decimal(yes_ask_price, "yes_ask_price")
    if no_ask_price is not None:
        no_ask_price = validate_decimal(no_ask_price, "no_ask_price")
    if spread is not None:
        spread = validate_decimal(spread, "spread")
    if last_price is not None:
        last_price = validate_decimal(last_price, "last_price")
    if liquidity is not None:
        liquidity = validate_decimal(liquidity, "liquidity")

    insert_query = """
        INSERT INTO edges (
            edge_key, market_id, model_id,
            expected_value, true_win_probability,
            market_implied_probability, market_price,
            yes_ask_price, no_ask_price, spread,
            volume, open_interest, last_price, liquidity,
            strategy_id, confidence_level, confidence_metrics,
            recommended_action, category, subcategory,
            execution_environment, edge_status,
            row_current_ind, row_start_ts
        )
        VALUES (
            'TEMP', %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, 'detected',
            TRUE, NOW()
        )
        RETURNING id
    """

    params = (
        market_id,
        model_id,
        expected_value,
        true_win_probability,
        market_implied_probability,
        market_price,
        yes_ask_price,
        no_ask_price,
        spread,
        volume,
        open_interest,
        last_price,
        liquidity,
        strategy_id,
        confidence_level,
        json.dumps(confidence_metrics) if confidence_metrics is not None else None,
        recommended_action,
        category,
        subcategory,
        execution_environment,
    )

    with get_cursor(commit=True) as cur:
        # Get surrogate id
        cur.execute(insert_query, params)
        result = cur.fetchone()
        surrogate_id = cast("int", result["id"])

        # Update to set correct edge_key (EDGE-{id} format)
        cur.execute(
            "UPDATE edges SET edge_key = %s WHERE id = %s",
            (f"EDGE-{surrogate_id}", surrogate_id),
        )

        return surrogate_id


def update_edge_outcome(
    edge_pk: int,
    actual_outcome: str,
    settlement_value: Decimal,
    resolved_at: datetime | None = None,
) -> bool:
    """
    Record settlement outcome for an edge.

    This is a lifecycle event (not an SCD version change), so we update
    the current row directly rather than creating a new SCD version.
    Also sets edge_status to 'settled'.

    Args:
        edge_pk: Surrogate PK (edges.id), NOT the edge_key business key
        actual_outcome: Settlement result - 'yes', 'no', 'void', or 'unresolved'
        settlement_value: Actual settlement price as DECIMAL(10,4)
            (0.0000 or 1.0000 for binary markets)
        resolved_at: Resolution timestamp (defaults to NOW())

    Returns:
        True if the edge was found and updated, False otherwise.

    Educational Note:
        Why direct update instead of SCD version?
        Outcome resolution is a lifecycle event on an existing edge -- it
        doesn't change the edge's identity or detection parameters. The
        edge_lifecycle view computes realized_pnl from settlement_value
        minus market_price, so we need these on the same row.

    Example:
        >>> success = update_edge_outcome(
        ...     edge_pk=42,
        ...     actual_outcome='yes',
        ...     settlement_value=Decimal("1.0000"),
        ... )
        >>> # Edge 42 now has edge_status='settled', actual_outcome='yes'

    References:
        - Migration 0023: edges enrichment
        - edge_lifecycle view: computes realized_pnl from outcome
    """
    settlement_value = validate_decimal(settlement_value, "settlement_value")

    valid_outcomes = ("yes", "no", "void", "unresolved")
    if actual_outcome not in valid_outcomes:
        raise ValueError(f"actual_outcome must be one of {valid_outcomes}, got '{actual_outcome}'")

    query = """
        UPDATE edges
        SET actual_outcome = %s,
            settlement_value = %s,
            resolved_at = COALESCE(%s, NOW()),
            edge_status = 'settled'
        WHERE id = %s AND row_current_ind = TRUE
    """

    with get_cursor(commit=True) as cur:
        cur.execute(query, (actual_outcome, settlement_value, resolved_at, edge_pk))
        return int(cur.rowcount or 0) > 0


def update_edge_status(
    edge_pk: int,
    new_status: str,
) -> bool:
    """
    Transition an edge's lifecycle status.

    This is a direct update (not an SCD version change) because status
    transitions track lifecycle progression, not identity changes.

    Args:
        edge_pk: Surrogate PK (edges.id), NOT the edge_key business key
        new_status: New lifecycle status. Valid values:
            'detected', 'recommended', 'acted_on', 'expired', 'settled', 'void'

    Returns:
        True if the edge was found and updated, False otherwise.

    Example:
        >>> success = update_edge_status(edge_pk=42, new_status='recommended')
        >>> # Edge 42 status changed from 'detected' to 'recommended'

    References:
        - Migration 0023: edge_status column with CHECK constraint
    """
    valid_statuses = (
        "detected",
        "recommended",
        "acted_on",
        "expired",
        "settled",
        "void",
    )
    if new_status not in valid_statuses:
        raise ValueError(f"new_status must be one of {valid_statuses}, got '{new_status}'")

    query = """
        UPDATE edges
        SET edge_status = %s
        WHERE id = %s AND row_current_ind = TRUE
    """

    with get_cursor(commit=True) as cur:
        cur.execute(query, (new_status, edge_pk))
        return int(cur.rowcount or 0) > 0


def get_edges_by_strategy(
    strategy_id: int,
    edge_status: str | None = None,
    execution_environment: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query current edges for a specific strategy.

    Only returns rows with row_current_ind = TRUE (SCD Type 2 pattern).

    Args:
        strategy_id: FK to strategies(strategy_id)
        edge_status: Optional filter by lifecycle status
            ('detected', 'recommended', 'acted_on', 'expired', 'settled', 'void')
        execution_environment: Optional filter ('live', 'paper', 'backtest')
        limit: Maximum rows to return (default 100)

    Returns:
        List of edge dictionaries, ordered by created_at DESC.

    Example:
        >>> edges = get_edges_by_strategy(strategy_id=1, edge_status='detected')
        >>> for edge in edges:
        ...     print(f"Edge {edge['edge_key']}: EV={edge['expected_value']}")

    References:
        - Migration 0023: strategy_id column + idx_edges_strategy index
    """
    query = """
        SELECT id, edge_key, market_id, model_id, strategy_id,
               expected_value, true_win_probability, market_implied_probability,
               market_price, yes_ask_price, no_ask_price, spread,
               volume, open_interest, last_price, liquidity,
               edge_status, actual_outcome, settlement_value,
               confidence_level, recommended_action,
               category, subcategory, execution_environment,
               created_at, resolved_at
        FROM edges
        WHERE row_current_ind = TRUE AND strategy_id = %s
    """
    params: list = [strategy_id]

    if edge_status is not None:
        query += " AND edge_status = %s"
        params.append(edge_status)

    if execution_environment is not None:
        query += " AND execution_environment = %s"
        params.append(execution_environment)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))


def get_edge_lifecycle(
    market_id: int | None = None,
    strategy_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query the edge_lifecycle view for analytics.

    The view includes computed fields:
    - realized_pnl: settlement_value - market_price (for 'yes' outcomes)
      or market_price - settlement_value (for 'no' outcomes)
    - hours_to_resolution: time from edge creation to resolution in hours

    Args:
        market_id: Optional filter by market
        strategy_id: Optional filter by strategy
        limit: Maximum rows to return (default 100)

    Returns:
        List of edge lifecycle dictionaries with computed fields.

    Example:
        >>> lifecycle = get_edge_lifecycle(strategy_id=1)
        >>> for edge in lifecycle:
        ...     if edge['realized_pnl'] is not None:
        ...         print(f"Edge {edge['edge_key']}: P&L={edge['realized_pnl']}")

    References:
        - Migration 0023: edge_lifecycle view definition
    """
    query = """
        SELECT id, edge_key, market_id, model_id, strategy_id,
               expected_value, true_win_probability, market_implied_probability,
               market_price, yes_ask_price, no_ask_price,
               edge_status, actual_outcome, settlement_value,
               confidence_level, execution_environment,
               created_at, resolved_at,
               realized_pnl, hours_to_resolution
        FROM edge_lifecycle
        WHERE 1=1
    """
    params: list = []

    if market_id is not None:
        query += " AND market_id = %s"
        params.append(market_id)

    if strategy_id is not None:
        query += " AND strategy_id = %s"
        params.append(strategy_id)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))


# =============================================================================
# ORDER OPERATIONS: MOVED to crud_orders.py
# Re-exported above for backward compatibility.
# =============================================================================


# =============================================================================
# ACCOUNT LEDGER + TEMPORAL ALIGNMENT + MARKET TRADES: MOVED to crud_ledger.py
# Re-exported above for backward compatibility.
# =============================================================================


# NOTE: The following function definitions have been removed:
#   create_order, get_order_by_id, get_order_by_external_id,
#   update_order_status, update_order_fill, cancel_order, get_open_orders
#   create_ledger_entry, get_ledger_entries, get_running_balance,
#   insert_temporal_alignment, insert_temporal_alignment_batch,
#   get_alignments_by_market, upsert_market_trade, upsert_market_trades_batch,
#   get_market_trades, get_latest_trade_time
# They now live in crud_orders.py and crud_ledger.py respectively.
# All are re-exported from this module for backward compatibility.


# =============================================================================
# ANALYTICS OPERATIONS (Migration 0031 - Analytics Tables)
# =============================================================================

_VALID_RUN_TYPES = frozenset({"model", "strategy", "ensemble"})
_VALID_RUN_STATUSES = frozenset({"running", "completed", "failed", "cancelled"})
_VALID_ENTITY_TYPES = frozenset({"model", "strategy", "evaluation_run", "backtest_run"})


# -----------------------------------------------------------------------------
# Evaluation Runs
# -----------------------------------------------------------------------------


def create_evaluation_run(
    run_type: str,
    model_id: int | None = None,
    strategy_id: int | None = None,
    config: dict | None = None,
) -> int:
    """
    Create an evaluation run record to track model/strategy evaluation.

    Args:
        run_type: One of 'model', 'strategy', 'ensemble'
        model_id: FK to probability_models(model_id) (optional)
        strategy_id: FK to strategies(strategy_id) (optional)
        config: JSONB run configuration (optional)

    Returns:
        Integer surrogate PK (evaluation_runs.id) of the newly created run.

    Raises:
        ValueError: If run_type is invalid

    Example:
        >>> run_id = create_evaluation_run(
        ...     run_type='model',
        ...     model_id=1,
        ...     config={'threshold': '0.05'},
        ... )
    """
    if run_type not in _VALID_RUN_TYPES:
        raise ValueError(f"run_type must be one of {_VALID_RUN_TYPES}, got '{run_type}'")

    insert_query = """
        INSERT INTO evaluation_runs (
            run_type, model_id, strategy_id, config
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """

    params = (
        run_type,
        model_id,
        strategy_id,
        json.dumps(config) if config is not None else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def complete_evaluation_run(
    run_id: int,
    summary: dict | None = None,
    error_message: str | None = None,
    status: str = "completed",
) -> bool:
    """
    Mark an evaluation run as completed (or failed/cancelled).

    Args:
        run_id: PK of the evaluation run
        summary: JSONB results summary (optional)
        error_message: Error details if failed (optional)
        status: Final status -- one of 'completed', 'failed', 'cancelled'

    Returns:
        True if the run was updated, False if run_id not found.

    Raises:
        ValueError: If status is invalid

    Example:
        >>> complete_evaluation_run(
        ...     run_id=1,
        ...     summary={'accuracy': '0.82', 'brier_score': '0.15'},
        ...     status='completed',
        ... )
    """
    if status not in _VALID_RUN_STATUSES:
        raise ValueError(f"status must be one of {_VALID_RUN_STATUSES}, got '{status}'")

    update_query = """
        UPDATE evaluation_runs
        SET status = %s,
            summary = %s,
            error_message = %s,
            completed_at = NOW()
        WHERE id = %s
        RETURNING id
    """

    params = (
        status,
        json.dumps(summary) if summary is not None else None,
        error_message,
        run_id,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(update_query, params)
        result = cur.fetchone()
        return result is not None


def get_evaluation_run(run_id: int) -> dict[str, Any] | None:
    """
    Get an evaluation run by its surrogate PK.

    Args:
        run_id: PK of the evaluation run

    Returns:
        Dictionary with run data, or None if not found.

    Example:
        >>> run = get_evaluation_run(1)
        >>> if run:
        ...     print(f"Run {run['id']}: {run['status']}")
    """
    query = "SELECT * FROM evaluation_runs WHERE id = %s"
    return fetch_one(query, (run_id,))


# -----------------------------------------------------------------------------
# Backtesting Runs
# -----------------------------------------------------------------------------


def create_backtesting_run(
    strategy_id: int | None,
    model_id: int | None,
    config: dict,
    date_range_start: date,
    date_range_end: date,
) -> int:
    """
    Create a backtesting run record to track a backtest experiment.

    Args:
        strategy_id: FK to strategies(strategy_id) (optional)
        model_id: FK to probability_models(model_id) (optional)
        config: JSONB backtest configuration (required)
        date_range_start: Start of backtest date range
        date_range_end: End of backtest date range

    Returns:
        Integer surrogate PK (backtesting_runs.id) of the newly created run.

    Example:
        >>> from datetime import date
        >>> run_id = create_backtesting_run(
        ...     strategy_id=1,
        ...     model_id=2,
        ...     config={'min_edge': '0.05'},
        ...     date_range_start=date(2025, 9, 1),
        ...     date_range_end=date(2026, 1, 31),
        ... )
    """
    insert_query = """
        INSERT INTO backtesting_runs (
            strategy_id, model_id, config,
            date_range_start, date_range_end
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        strategy_id,
        model_id,
        json.dumps(config),
        date_range_start,
        date_range_end,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def complete_backtesting_run(
    run_id: int,
    total_trades: int = 0,
    win_rate: Decimal | None = None,
    total_pnl: Decimal | None = None,
    max_drawdown: Decimal | None = None,
    sharpe_ratio: Decimal | None = None,
    results_detail: dict | None = None,
    error_message: str | None = None,
    status: str = "completed",
) -> bool:
    """
    Mark a backtesting run as completed with result metrics.

    Args:
        run_id: PK of the backtesting run
        total_trades: Total number of simulated trades
        win_rate: Win rate as DECIMAL(10,4)
        total_pnl: Total profit/loss as DECIMAL(10,4)
        max_drawdown: Maximum drawdown as DECIMAL(10,4)
        sharpe_ratio: Sharpe ratio as DECIMAL(10,4)
        results_detail: JSONB with detailed results breakdown
        error_message: Error details if failed
        status: Final status -- one of 'completed', 'failed', 'cancelled'

    Returns:
        True if the run was updated, False if run_id not found.

    Raises:
        TypeError: If Decimal fields are not Decimal type
        ValueError: If status is invalid

    Example:
        >>> complete_backtesting_run(
        ...     run_id=1,
        ...     total_trades=150,
        ...     win_rate=Decimal("0.5800"),
        ...     total_pnl=Decimal("125.5000"),
        ...     max_drawdown=Decimal("-45.2000"),
        ...     sharpe_ratio=Decimal("1.3200"),
        ...     status='completed',
        ... )
    """
    if status not in _VALID_RUN_STATUSES:
        raise ValueError(f"status must be one of {_VALID_RUN_STATUSES}, got '{status}'")

    # Validate Decimal fields when provided
    if win_rate is not None:
        win_rate = validate_decimal(win_rate, "win_rate")
    if total_pnl is not None:
        total_pnl = validate_decimal(total_pnl, "total_pnl")
    if max_drawdown is not None:
        max_drawdown = validate_decimal(max_drawdown, "max_drawdown")
    if sharpe_ratio is not None:
        sharpe_ratio = validate_decimal(sharpe_ratio, "sharpe_ratio")

    update_query = """
        UPDATE backtesting_runs
        SET status = %s,
            total_trades = %s,
            win_rate = %s,
            total_pnl = %s,
            max_drawdown = %s,
            sharpe_ratio = %s,
            results_detail = %s,
            error_message = %s,
            completed_at = NOW()
        WHERE id = %s
        RETURNING id
    """

    params = (
        status,
        total_trades,
        win_rate,
        total_pnl,
        max_drawdown,
        sharpe_ratio,
        json.dumps(results_detail) if results_detail is not None else None,
        error_message,
        run_id,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(update_query, params)
        result = cur.fetchone()
        return result is not None


def get_backtesting_run(run_id: int) -> dict[str, Any] | None:
    """
    Get a backtesting run by its surrogate PK.

    Args:
        run_id: PK of the backtesting run

    Returns:
        Dictionary with run data, or None if not found.

    Example:
        >>> run = get_backtesting_run(1)
        >>> if run:
        ...     print(f"Backtest {run['id']}: {run['total_trades']} trades, PnL={run['total_pnl']}")
    """
    query = "SELECT * FROM backtesting_runs WHERE id = %s"
    return fetch_one(query, (run_id,))


# -----------------------------------------------------------------------------
# Predictions
# -----------------------------------------------------------------------------


def create_prediction(
    model_id: int | None,
    market_id: int,
    predicted_probability: Decimal,
    confidence: Decimal | None = None,
    market_price_at_prediction: Decimal | None = None,
    edge: Decimal | None = None,
    evaluation_run_id: int | None = None,
    event_id: int | None = None,
) -> int:
    """
    Create a prediction record (live or as part of an evaluation run).

    Args:
        model_id: FK to probability_models(model_id) (optional)
        market_id: FK to markets(id) (required)
        predicted_probability: Model output as DECIMAL(10,4) in [0, 1]
        confidence: Model confidence as DECIMAL(10,4) in [0, 1] (optional)
        market_price_at_prediction: Market price when predicted, DECIMAL(10,4) in [0, 1]
        edge: predicted_probability - market_price (can be negative)
        evaluation_run_id: FK to evaluation_runs(id) (NULL for live predictions)
        event_id: FK to events(id) (optional)

    Returns:
        Integer surrogate PK (predictions.id) of the newly created prediction.

    Raises:
        TypeError: If Decimal fields are not Decimal type
        ValueError: If predicted_probability is out of [0, 1] range

    Example:
        >>> pred_id = create_prediction(
        ...     model_id=1,
        ...     market_id=42,
        ...     predicted_probability=Decimal("0.6500"),
        ...     market_price_at_prediction=Decimal("0.5500"),
        ...     edge=Decimal("0.1000"),
        ... )
    """
    predicted_probability = validate_decimal(predicted_probability, "predicted_probability")
    if predicted_probability < Decimal("0") or predicted_probability > Decimal("1"):
        raise ValueError(
            f"predicted_probability must be between 0 and 1, got {predicted_probability}"
        )

    if confidence is not None:
        confidence = validate_decimal(confidence, "confidence")
        if confidence < Decimal("0") or confidence > Decimal("1"):
            raise ValueError(f"confidence must be between 0 and 1, got {confidence}")

    if market_price_at_prediction is not None:
        market_price_at_prediction = validate_decimal(
            market_price_at_prediction, "market_price_at_prediction"
        )
        if market_price_at_prediction < Decimal("0") or market_price_at_prediction > Decimal("1"):
            raise ValueError(
                f"market_price_at_prediction must be between 0 and 1, "
                f"got {market_price_at_prediction}"
            )

    if edge is not None:
        edge = validate_decimal(edge, "edge")

    insert_query = """
        INSERT INTO predictions (
            evaluation_run_id, model_id,
            market_id, event_id,
            predicted_probability, confidence,
            market_price_at_prediction, edge
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        evaluation_run_id,
        model_id,
        market_id,
        event_id,
        predicted_probability,
        confidence,
        market_price_at_prediction,
        edge,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def resolve_prediction(
    prediction_id: int,
    actual_outcome: Decimal,
    is_correct: bool,
) -> bool:
    """
    Resolve a prediction by recording the actual outcome.

    Args:
        prediction_id: PK of the prediction
        actual_outcome: Actual outcome as DECIMAL(10,4) in [0, 1]
        is_correct: Whether the prediction was correct

    Returns:
        True if the prediction was updated, False if prediction_id not found.

    Raises:
        TypeError: If actual_outcome is not Decimal
        ValueError: If actual_outcome is out of [0, 1] range

    Example:
        >>> resolve_prediction(
        ...     prediction_id=1,
        ...     actual_outcome=Decimal("1.0000"),
        ...     is_correct=True,
        ... )
    """
    actual_outcome = validate_decimal(actual_outcome, "actual_outcome")
    if actual_outcome < Decimal("0") or actual_outcome > Decimal("1"):
        raise ValueError(f"actual_outcome must be between 0 and 1, got {actual_outcome}")

    update_query = """
        UPDATE predictions
        SET actual_outcome = %s,
            is_correct = %s,
            resolved_at = NOW()
        WHERE id = %s
        RETURNING id
    """

    params = (actual_outcome, is_correct, prediction_id)

    with get_cursor(commit=True) as cur:
        cur.execute(update_query, params)
        result = cur.fetchone()
        return result is not None


def get_predictions_by_run(
    evaluation_run_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Get predictions for a specific evaluation run.

    Args:
        evaluation_run_id: FK to evaluation_runs(id)
        limit: Maximum number of predictions to return (default 100)

    Returns:
        List of prediction dictionaries ordered by predicted_at DESC.

    Example:
        >>> preds = get_predictions_by_run(evaluation_run_id=1)
        >>> for p in preds:
        ...     print(f"Market {p['market_id']}: {p['predicted_probability']}")
    """
    query = """
        SELECT * FROM predictions
        WHERE evaluation_run_id = %s
        ORDER BY predicted_at DESC, id DESC
        LIMIT %s
    """
    return fetch_all(query, (evaluation_run_id, limit))


def get_unresolved_predictions(
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Get predictions that have not yet been resolved (actual_outcome IS NULL).

    Args:
        limit: Maximum number of predictions to return (default 100)

    Returns:
        List of unresolved prediction dictionaries ordered by predicted_at DESC.

    Example:
        >>> unresolved = get_unresolved_predictions(limit=50)
        >>> print(f"{len(unresolved)} predictions awaiting resolution")
    """
    query = """
        SELECT * FROM predictions
        WHERE actual_outcome IS NULL
        ORDER BY predicted_at DESC, id DESC
        LIMIT %s
    """
    return fetch_all(query, (limit,))


# -----------------------------------------------------------------------------
# Performance Metrics
# -----------------------------------------------------------------------------


def upsert_performance_metric(
    entity_type: str,
    entity_id: int,
    metric_name: str,
    metric_value: Decimal,
    period_start: date | None = None,
    period_end: date | None = None,
    sample_size: int | None = None,
    metadata: dict | None = None,
) -> int:
    """
    Insert or update a performance metric (upsert on unique constraint).

    Args:
        entity_type: One of 'model', 'strategy', 'evaluation_run', 'backtest_run'
        entity_id: PK of the entity
        metric_name: Name of the metric (e.g., 'accuracy', 'brier_score')
        metric_value: Metric value as DECIMAL(10,4)
        period_start: Start of measurement period (optional)
        period_end: End of measurement period (optional)
        sample_size: Number of samples in calculation (optional)
        metadata: Additional context as JSONB (optional)

    Returns:
        Integer surrogate PK (performance_metrics.id).

    Raises:
        TypeError: If metric_value is not Decimal
        ValueError: If entity_type is invalid

    Example:
        >>> metric_id = upsert_performance_metric(
        ...     entity_type='model',
        ...     entity_id=1,
        ...     metric_name='brier_score',
        ...     metric_value=Decimal("0.1500"),
        ...     period_start=date(2026, 1, 1),
        ...     period_end=date(2026, 3, 31),
        ...     sample_size=500,
        ... )
    """
    if entity_type not in _VALID_ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {_VALID_ENTITY_TYPES}, got '{entity_type}'")
    metric_value = validate_decimal(metric_value, "metric_value")

    upsert_query = """
        INSERT INTO performance_metrics (
            entity_type, entity_id, metric_name, metric_value,
            period_start, period_end, sample_size, metadata,
            calculated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (entity_type, entity_id, metric_name, period_start, period_end)
        DO UPDATE SET
            metric_value = EXCLUDED.metric_value,
            sample_size = EXCLUDED.sample_size,
            metadata = EXCLUDED.metadata,
            calculated_at = NOW()
        RETURNING id
    """

    params = (
        entity_type,
        entity_id,
        metric_name,
        metric_value,
        period_start,
        period_end,
        sample_size,
        json.dumps(metadata) if metadata is not None else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(upsert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def get_performance_metrics(
    entity_type: str,
    entity_id: int,
    metric_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get performance metrics for a specific entity.

    Args:
        entity_type: One of 'model', 'strategy', 'evaluation_run', 'backtest_run'
        entity_id: PK of the entity
        metric_name: Optional filter by metric name

    Returns:
        List of metric dictionaries ordered by calculated_at DESC.

    Raises:
        ValueError: If entity_type is invalid

    Example:
        >>> metrics = get_performance_metrics('model', entity_id=1)
        >>> for m in metrics:
        ...     print(f"{m['metric_name']}: {m['metric_value']}")
    """
    if entity_type not in _VALID_ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {_VALID_ENTITY_TYPES}, got '{entity_type}'")

    query = "SELECT * FROM performance_metrics WHERE entity_type = %s AND entity_id = %s"
    params: list = [entity_type, entity_id]

    if metric_name is not None:
        query += " AND metric_name = %s"
        params.append(metric_name)

    query += " ORDER BY calculated_at DESC, id DESC"

    return fetch_all(query, tuple(params))


# =============================================================================
# ORDERBOOK SNAPSHOT OPERATIONS (Migration 0034)
# =============================================================================
