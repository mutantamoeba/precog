"""
Type definitions for Analytics module responses.

Provides TypedDict definitions for all analytics-related data structures
including performance metrics, portfolio snapshots, and model evaluation results.

All monetary and percentage fields use Decimal for precision (ADR-002).
All timestamps use ISO 8601 string format for consistency.

Design Pattern:
    TypedDict provides compile-time type checking without runtime overhead.
    This is the standard pattern for API/database response types in Precog.
    See api_connectors/types.py for the same pattern with Kalshi API responses.

Why TypedDict over Pydantic:
    - Zero runtime overhead (type hints are ignored at runtime)
    - Simpler for read-only data structures
    - Better IDE autocomplete
    - Easier to maintain
    Pydantic may be used in Phase 5+ for validation-heavy use cases.

Reference: docs/guides/DEVELOPMENT_PATTERNS_V1.5.md Pattern 6 (TypedDict)
Related ADR: ADR-002 (Decimal Precision for Monetary Values)
Related ADR: ADR-050 (TypedDict for API Responses)

Created: 2025-11-25
Phase: 1.5 (Foundation Validation)
GitHub Issue: #47
"""

from decimal import Decimal
from typing import Literal, TypedDict

# =============================================================================
# Strategy Performance Types
# =============================================================================


class StrategyPerformanceMetrics(TypedDict):
    """
    Performance metrics for a single strategy.

    Used by: StrategyManager.get_performance_metrics()
    Source: Aggregated from trades, positions, and markets tables

    Example:
        >>> metrics = manager.get_performance_metrics(strategy_id=1)
        >>> print(f"Win rate: {metrics['win_rate']:.2%}")
        Win rate: 65.00%
    """

    strategy_id: int
    strategy_name: str
    strategy_version: str
    status: Literal["active", "inactive", "deprecated", "testing"]

    # Trade counts
    total_trades: int
    winning_trades: int
    losing_trades: int
    open_trades: int

    # P&L metrics (all Decimal for precision)
    total_pnl: Decimal  # Sum of all realized P&L
    unrealized_pnl: Decimal  # Current value of open positions - cost basis
    gross_profit: Decimal  # Sum of winning trades
    gross_loss: Decimal  # Sum of losing trades (negative)
    max_drawdown: Decimal  # Maximum peak-to-trough decline
    max_drawdown_pct: Decimal  # Max drawdown as percentage of peak

    # Performance ratios
    win_rate: Decimal  # Winning trades / total trades
    avg_win: Decimal  # Average profit on winning trades
    avg_loss: Decimal  # Average loss on losing trades
    profit_factor: Decimal  # Gross profit / |gross loss|
    expectancy: Decimal  # Average P&L per trade
    sharpe_ratio: Decimal  # Risk-adjusted return

    # Time-based metrics
    avg_hold_time_hours: Decimal  # Average time position held
    trades_per_day: Decimal  # Average trades executed per day

    # Metadata
    first_trade_at: str  # ISO 8601 timestamp
    last_trade_at: str  # ISO 8601 timestamp
    calculated_at: str  # When these metrics were calculated


class StrategyComparisonResult(TypedDict):
    """
    Result of comparing two strategy versions (A/B testing).

    Used by: StrategyManager.compare_versions()
    Purpose: Determine which strategy version performs better

    Example:
        >>> result = manager.compare_versions(v1_id=1, v2_id=2)
        >>> if result['winner'] == 'v2':
        ...     print("New version outperforms!")
    """

    strategy_name: str
    v1_id: int
    v1_version: str
    v2_id: int
    v2_version: str

    # Direct comparisons
    pnl_difference: Decimal  # v2.total_pnl - v1.total_pnl
    win_rate_difference: Decimal  # v2.win_rate - v1.win_rate
    sharpe_difference: Decimal  # v2.sharpe - v1.sharpe

    # Statistical significance
    p_value: Decimal | None  # If significance testing performed
    confidence_interval: tuple[Decimal, Decimal] | None
    statistically_significant: bool

    # Recommendation
    winner: Literal["v1", "v2", "tie", "insufficient_data"]
    recommendation: str  # Human-readable recommendation
    sample_size_v1: int
    sample_size_v2: int


# =============================================================================
# Model Performance Types
# =============================================================================


class ModelPerformanceMetrics(TypedDict):
    """
    Performance metrics for a probability model.

    Used by: ModelManager.get_performance_metrics()
    Source: Aggregated from model predictions vs actual outcomes

    Example:
        >>> metrics = manager.get_performance_metrics(model_id=1)
        >>> print(f"Accuracy: {metrics['accuracy']:.2%}")
        Accuracy: 72.50%
    """

    model_id: int
    model_name: str
    model_version: str
    model_class: str  # e.g., "elo", "ensemble", "ml"
    status: Literal["active", "inactive", "deprecated", "testing"]

    # Prediction counts
    total_predictions: int
    correct_predictions: int
    incorrect_predictions: int
    pending_predictions: int  # Market not yet settled

    # Accuracy metrics
    accuracy: Decimal  # Correct / total
    precision: Decimal  # TP / (TP + FP)
    recall: Decimal  # TP / (TP + FN)
    f1_score: Decimal  # Harmonic mean of precision and recall

    # Calibration metrics
    brier_score: Decimal  # Mean squared error of probability predictions
    log_loss: Decimal  # Cross-entropy loss
    calibration_error: Decimal  # Expected calibration error

    # Value metrics (when used with trading)
    edge_captured: Decimal  # Average (predicted_prob - market_prob) * outcome
    roi_if_followed: Decimal  # Simulated ROI if all predictions traded

    # Metadata
    first_prediction_at: str
    last_prediction_at: str
    calculated_at: str


class ModelCalibrationBucket(TypedDict):
    """
    Single bucket for model calibration analysis.

    Used by: ModelManager.get_calibration_curve()
    Purpose: Show how well predicted probabilities match actual outcomes

    Example:
        For predictions between 60-70%:
        - predicted_prob_mean: 0.65 (average predicted probability)
        - actual_outcome_rate: 0.63 (63% actually occurred)
        - count: 150 (150 predictions in this bucket)
    """

    bucket_start: Decimal  # e.g., 0.60
    bucket_end: Decimal  # e.g., 0.70
    predicted_prob_mean: Decimal  # Average predicted probability
    actual_outcome_rate: Decimal  # Actual win rate in this bucket
    count: int  # Number of predictions in bucket
    standard_error: Decimal  # Standard error of actual rate


# =============================================================================
# Portfolio Types
# =============================================================================


class PortfolioSnapshot(TypedDict):
    """
    Point-in-time snapshot of portfolio state.

    Used by: PositionManager.get_portfolio_snapshot()
    Purpose: Track portfolio value over time for charting/analysis

    Example:
        >>> snapshot = manager.get_portfolio_snapshot()
        >>> print(f"Total value: ${snapshot['total_value']:.2f}")
        Total value: $12,345.67
    """

    snapshot_id: int
    timestamp: str  # ISO 8601

    # Value breakdown
    cash_balance: Decimal  # Available cash
    positions_value: Decimal  # Market value of all positions
    total_value: Decimal  # cash_balance + positions_value

    # Position summary
    total_positions: int
    long_positions: int  # YES positions
    short_positions: int  # NO positions

    # Risk metrics
    total_exposure: Decimal  # Sum of position costs
    exposure_pct: Decimal  # Exposure / total_value
    max_single_position_pct: Decimal  # Largest position / total_value

    # P&L for period
    unrealized_pnl: Decimal
    realized_pnl_today: Decimal
    realized_pnl_total: Decimal

    # Comparison to previous
    value_change_1h: Decimal | None
    value_change_24h: Decimal | None
    value_change_7d: Decimal | None


class PositionSummary(TypedDict):
    """
    Summary of a single position with calculated metrics.

    Used by: PositionManager.get_position_summary()
    Source: positions table + current market prices

    Example:
        >>> summary = manager.get_position_summary(position_id=1)
        >>> print(f"P&L: ${summary['unrealized_pnl']:.2f}")
        P&L: $12.50
    """

    position_id: int
    market_id: int
    ticker: str
    title: str

    # Position details
    side: Literal["yes", "no"]
    quantity: int
    entry_price: Decimal
    current_price: Decimal
    cost_basis: Decimal  # quantity * entry_price

    # P&L
    unrealized_pnl: Decimal  # (current_price - entry_price) * quantity
    unrealized_pnl_pct: Decimal  # unrealized_pnl / cost_basis
    realized_pnl: Decimal  # From partial closes

    # Risk management
    stop_loss_price: Decimal | None
    trailing_stop_price: Decimal | None
    target_price: Decimal | None

    # Attribution
    strategy_id: int
    strategy_name: str
    model_id: int
    model_name: str

    # Timestamps
    opened_at: str
    last_updated_at: str


# =============================================================================
# Daily/Period Aggregate Types
# =============================================================================


class DailyPnLSummary(TypedDict):
    """
    Daily P&L summary for portfolio.

    Used by: Analytics dashboards, reporting
    Source: Aggregated from trades and portfolio snapshots

    Example:
        >>> daily = get_daily_pnl("2025-11-25")
        >>> print(f"Net P&L: ${daily['net_pnl']:.2f}")
        Net P&L: $45.67
    """

    date: str  # YYYY-MM-DD format
    starting_value: Decimal
    ending_value: Decimal

    # P&L breakdown
    realized_pnl: Decimal  # From closed positions
    unrealized_pnl_change: Decimal  # Change in unrealized P&L
    net_pnl: Decimal  # realized + unrealized_change
    net_pnl_pct: Decimal  # net_pnl / starting_value

    # Trading activity
    trades_executed: int
    positions_opened: int
    positions_closed: int
    fees_paid: Decimal

    # Market context
    markets_settled: int
    settlements_won: int
    settlements_lost: int


class PeriodPerformanceSummary(TypedDict):
    """
    Performance summary for any time period.

    Used by: Weekly/monthly/yearly reports
    Flexible period definition via start_date and end_date

    Example:
        >>> monthly = get_period_summary("2025-11-01", "2025-11-30")
        >>> print(f"Total return: {monthly['total_return_pct']:.2%}")
        Total return: 8.50%
    """

    start_date: str
    end_date: str
    trading_days: int

    # Returns
    starting_value: Decimal
    ending_value: Decimal
    total_return: Decimal
    total_return_pct: Decimal

    # Risk metrics
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    volatility: Decimal  # Standard deviation of daily returns
    sharpe_ratio: Decimal

    # Trading summary
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal

    # Best/worst days
    best_day_date: str
    best_day_pnl: Decimal
    worst_day_date: str
    worst_day_pnl: Decimal
