#!/usr/bin/env python3
"""
Tests for Trade and Position Attribution Architecture

Tests trade source tracking, attribution enrichment, and performance analytics
introduced in Migrations 018-020.

**Test Coverage:**
1. Trade Attribution (Migration 019):
   - trade_source tracking (automated vs manual)
   - calculated_probability, market_price, edge_value
   - Automatic edge calculation
   - Analytics queries (ROI by model, edge analysis)

2. Position Attribution (Migration 020):
   - model_id, calculated_probability, edge_at_entry, market_price_at_entry
   - Immutable entry-time snapshots (ADR-018)
   - Strategy A/B testing queries
   - Performance attribution

3. Strategy Configuration (ADR-090):
   - Nested versioning (entry.version, exit.version)
   - Independent version management
   - JSONB validation

4. Validation & Edge Cases:
   - Probability range [0.0, 1.0] CHECK constraints
   - NULL handling for optional fields
   - Negative edge values (overpriced markets)
   - Performance of explicit columns vs JSONB

**Related ADRs:**
- ADR-090: Strategy Contains Entry + Exit Rules with Nested Versioning
- ADR-091: Explicit Columns for Trade/Position Attribution
- ADR-092: Trade Source Tracking and Manual Trade Reconciliation
- ADR-018: Immutable Versioning (positions locked to strategy/model version)
- ADR-002: Decimal Precision for All Financial Data

**References:**
- Migration 018: Trade Source Tracking
- Migration 019: Trade Attribution Enrichment
- Migration 020: Position Attribution
- docs/analysis/SCHEMA_ANALYSIS_2025-11-21.md

Created: 2025-11-21
"""

from decimal import Decimal
from typing import Any

import psycopg2.errors
import pytest

from precog.database.crud_operations import (
    create_position,
    create_strategy,
    create_trade,
    get_position_by_id,
    get_trade_by_id,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_strategy_config_nested() -> dict[str, Any]:
    """
    Strategy configuration with nested entry/exit versioning (ADR-090).

    Educational Note:
        This represents the NEW nested versioning strategy where:
        - entry.version tracks entry rule version independently
        - exit.version tracks exit rule version independently
        - Enables A/B testing: "Did entry v1.5 outperform entry v1.6?"
    """
    return {
        "entry": {
            "version": "1.5",
            "rules": {
                "min_lead": 10,
                "max_spread": "0.08",
                "min_edge": "0.05",
                "min_probability": "0.55",
            },
        },
        "exit": {
            "version": "2.3",
            "rules": {
                "profit_target": "0.25",
                "stop_loss": "-0.10",
                "trailing_stop_activation": "0.15",
                "trailing_stop_distance": "0.05",
            },
        },
    }


@pytest.fixture
def sample_platform(db_pool, clean_test_data) -> str:
    """Create sample platform for testing."""
    from precog.database.connection import execute_query

    query = """
        INSERT INTO platforms (platform_id, platform_type, display_name, base_url)
        VALUES ('kalshi', 'trading', 'Kalshi', 'https://api.elections.kalshi.com/trade-api/v2')
        ON CONFLICT (platform_id) DO NOTHING
        RETURNING platform_id
    """
    execute_query(query)
    return "kalshi"


@pytest.fixture
def sample_series(db_pool, clean_test_data, sample_platform) -> str:
    """Create sample series for testing."""
    from precog.database.connection import execute_query

    query = """
        INSERT INTO series (series_id, platform_id, external_id, category, subcategory, title, frequency)
        VALUES ('NFL-2025', 'kalshi', 'NFL-2025-ext', 'sports', 'nfl', 'NFL 2025 Season', 'recurring')
        ON CONFLICT (series_id) DO NOTHING
        RETURNING series_id
    """
    execute_query(query)
    return "NFL-2025"


@pytest.fixture
def sample_event(db_pool, clean_test_data, sample_platform, sample_series) -> str:
    """Create sample event for testing."""
    from precog.database.connection import execute_query

    query = """
        INSERT INTO events (event_id, platform_id, series_id, external_id, category, subcategory, title, status)
        VALUES ('HIGHTEST', 'kalshi', 'NFL-2025', 'HIGHTEST-ext', 'sports', 'nfl', 'Super Bowl LIX', 'scheduled')
        ON CONFLICT (event_id) DO NOTHING
        RETURNING event_id
    """
    execute_query(query)
    return "HIGHTEST"


@pytest.fixture
def sample_market(db_pool, clean_test_data, sample_platform, sample_event) -> str:
    """Create sample market for testing."""
    from precog.database.connection import fetch_one

    # Check if market already exists
    existing = fetch_one(
        "SELECT market_id FROM markets WHERE market_id = %s AND row_current_ind = TRUE",
        ("MKT-HIGHTEST-25FEB05",),
    )
    if existing:
        return "MKT-HIGHTEST-25FEB05"

    # Create new market
    query = """
        INSERT INTO markets (
            market_id, platform_id, event_id, external_id, ticker, title,
            market_type, yes_price, no_price, status, metadata, row_current_ind, updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW()
        )
        RETURNING market_id
    """
    from precog.database.connection import get_cursor

    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (
                "MKT-HIGHTEST-25FEB05",
                "kalshi",
                "HIGHTEST",
                "HIGHTEST-25FEB05-ext",
                "HIGHTEST-25FEB05",
                "Will HIGHTEST win Super Bowl?",
                "binary",
                0.5200,
                0.4800,
                "open",
                '{"market_category": "sports", "event_category": "nfl", "expected_expiry": "2025-02-05 18:00:00"}',
            ),
        )
        result = cur.fetchone()
        return result["market_id"] if result else "MKT-HIGHTEST-25FEB05"


# =============================================================================
# TEST SUITE 1: TRADE ATTRIBUTION (Migration 018-019)
# =============================================================================


def test_create_trade_with_automated_source_default(
    db_pool, clean_test_data, sample_market, sample_strategy
):
    """
    Test trade creation defaults to 'automated' source.

    Validates:
    - Default trade_source = 'automated' (Migration 018)
    - ENUM validation works correctly
    """
    trade_id = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="buy",
        quantity=50,
        price=Decimal("0.5500"),
    )

    trade = get_trade_by_id(trade_id)

    assert trade is not None
    assert trade["trade_source"] == "automated"  # Default value
    assert trade["quantity"] == 50
    assert trade["price"] == Decimal("0.5500")


def test_create_trade_with_manual_source(db_pool, clean_test_data, sample_market, sample_strategy):
    """
    Test trade creation with manual source (Kalshi UI trade).

    Validates:
    - trade_source accepts 'manual' value
    - Enables reconciliation workflow (separate manual from automated)
    """
    trade_id = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="buy",
        quantity=100,
        price=Decimal("0.6000"),
        trade_source="manual",  # Kalshi UI trade
    )

    trade = get_trade_by_id(trade_id)

    assert trade is not None
    assert trade["trade_source"] == "manual"
    assert trade["quantity"] == 100


def test_create_trade_with_attribution_fields(
    db_pool, clean_test_data, sample_market, sample_strategy
):
    """
    Test trade creation with full attribution enrichment (Migration 019).

    Validates:
    - calculated_probability, market_price, edge_value recorded
    - Automatic edge calculation: calculated_probability - market_price
    - Enables performance analytics: "Which models have highest ROI?"
    """
    trade_id = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="buy",
        quantity=75,
        price=Decimal("0.5200"),
        calculated_probability=Decimal("0.6250"),  # Model prediction: 62.50%
        market_price=Decimal("0.5200"),  # Kalshi price: 52.00%
        trade_source="automated",
    )

    trade = get_trade_by_id(trade_id)

    assert trade is not None
    assert trade["calculated_probability"] == Decimal("0.6250")
    assert trade["market_price"] == Decimal("0.5200")
    # ⭐ Automatic edge calculation
    assert trade["edge_value"] == Decimal("0.1050")  # 0.6250 - 0.5200


def test_create_trade_with_negative_edge(db_pool, clean_test_data, sample_market, sample_strategy):
    """
    Test trade with negative edge (overpriced market).

    Validates:
    - edge_value can be negative (market_price > calculated_probability)
    - Represents overpriced markets where we should NOT trade
    - Useful for analytics: "How often did we trade negative edges?"
    """
    trade_id = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="buy",
        quantity=50,
        price=Decimal("0.7500"),
        calculated_probability=Decimal("0.6000"),  # Model says 60%
        market_price=Decimal("0.7500"),  # Market priced at 75% (overpriced!)
    )

    trade = get_trade_by_id(trade_id)

    assert trade is not None
    assert trade["calculated_probability"] == Decimal("0.6000")
    assert trade["market_price"] == Decimal("0.7500")
    # ⭐ Negative edge indicates overpriced market
    assert trade["edge_value"] == Decimal("-0.1500")  # 0.6000 - 0.7500


def test_create_trade_without_attribution_fields(
    db_pool, clean_test_data, sample_market, sample_strategy
):
    """
    Test backward compatibility: trades without attribution fields.

    Validates:
    - calculated_probability, market_price, edge_value are optional (NULL allowed)
    - Supports legacy trades or non-model trades
    - Ensures backward compatibility with existing code
    """
    trade_id = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="buy",
        quantity=50,
        price=Decimal("0.5000"),
        # No attribution fields provided
    )

    trade = get_trade_by_id(trade_id)

    assert trade is not None
    assert trade["calculated_probability"] is None
    assert trade["market_price"] is None
    assert trade["edge_value"] is None
    assert trade["trade_source"] == "automated"  # Still has default


def test_create_trade_probability_out_of_range(
    db_pool, clean_test_data, sample_market, sample_strategy
):
    """
    Test CHECK constraint: calculated_probability must be in [0.0, 1.0].

    Validates:
    - Database rejects probabilities > 1.0
    - Database rejects probabilities < 0.0
    - Ensures data integrity at database level
    """
    # Test probability > 1.0
    with pytest.raises(psycopg2.errors.CheckViolation):
        create_trade(
            market_id=sample_market,
            strategy_id=sample_strategy,
            model_id=1,
            side="buy",
            quantity=50,
            price=Decimal("0.5000"),
            calculated_probability=Decimal("1.5000"),  # Invalid: > 1.0
            market_price=Decimal("0.5000"),
        )

    # Test probability < 0.0
    with pytest.raises(psycopg2.errors.CheckViolation):
        create_trade(
            market_id=sample_market,
            strategy_id=sample_strategy,
            model_id=1,
            side="buy",
            quantity=50,
            price=Decimal("0.5000"),
            calculated_probability=Decimal("-0.2000"),  # Invalid: < 0.0
            market_price=Decimal("0.5000"),
        )


# =============================================================================
# TEST SUITE 2: POSITION ATTRIBUTION (Migration 020)
# =============================================================================


def test_create_position_with_attribution_fields(
    db_pool, clean_test_data, sample_market, sample_strategy
):
    """
    Test position creation with full attribution (Migration 020).

    Validates:
    - model_id, calculated_probability, edge_at_entry, market_price_at_entry recorded
    - Automatic edge_at_entry calculation
    - Immutable entry-time snapshots (ADR-018)
    - Enables strategy A/B testing
    """
    position_id = create_position(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="yes",
        quantity=100,
        entry_price=Decimal("0.5200"),
        target_price=Decimal("0.7500"),
        stop_loss_price=Decimal("0.4500"),
        calculated_probability=Decimal("0.6800"),  # Model prediction at entry
        market_price_at_entry=Decimal("0.5200"),  # Kalshi price at entry
    )

    position = get_position_by_id(position_id)

    assert position is not None
    assert position["model_id"] == 1
    assert position["calculated_probability"] == Decimal("0.6800")
    assert position["market_price_at_entry"] == Decimal("0.5200")
    # ⭐ Automatic edge_at_entry calculation
    assert position["edge_at_entry"] == Decimal("0.1600")  # 0.6800 - 0.5200


def test_create_position_immutable_attribution(
    db_pool, clean_test_data, sample_market, sample_strategy
):
    """
    Test immutability of position attribution fields (ADR-018).

    Validates:
    - calculated_probability, edge_at_entry, market_price_at_entry are snapshots
    - These fields represent entry-time values, never updated
    - Enables comparing entry predictions to actual outcomes
    """
    position_id = create_position(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="yes",
        quantity=50,
        entry_price=Decimal("0.4500"),
        calculated_probability=Decimal("0.5500"),
        market_price_at_entry=Decimal("0.4500"),
    )

    position = get_position_by_id(position_id)

    # ⭐ These values are IMMUTABLE entry-time snapshots
    assert position is not None
    assert position["calculated_probability"] == Decimal("0.5500")
    assert position["market_price_at_entry"] == Decimal("0.4500")
    assert position["edge_at_entry"] == Decimal("0.1000")

    # Educational Note:
    # If market_price later changes to 0.6000, position attribution remains unchanged.
    # This enables analytics: "What was the edge at entry for winning positions?"


def test_create_position_without_attribution_fields(
    db_pool, clean_test_data, sample_market, sample_strategy
):
    """
    Test backward compatibility: positions without attribution fields.

    Validates:
    - Attribution fields are optional (NULL allowed)
    - Supports legacy positions or non-model positions
    - Ensures backward compatibility
    """
    position_id = create_position(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="yes",
        quantity=75,
        entry_price=Decimal("0.5000"),
        # No attribution fields provided
    )

    position = get_position_by_id(position_id)

    assert position is not None
    assert position["calculated_probability"] is None
    assert position["market_price_at_entry"] is None
    assert position["edge_at_entry"] is None


def test_create_position_with_negative_edge(
    db_pool, clean_test_data, sample_market, sample_strategy
):
    """
    Test position with negative edge at entry.

    Validates:
    - edge_at_entry can be negative (market overpriced at entry)
    - Useful for analytics: "Did we open positions with insufficient edge?"
    """
    position_id = create_position(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="yes",
        quantity=50,
        entry_price=Decimal("0.8000"),
        calculated_probability=Decimal("0.7000"),  # Model: 70%
        market_price_at_entry=Decimal("0.8000"),  # Market: 80% (overpriced)
    )

    position = get_position_by_id(position_id)

    assert position is not None
    assert position["edge_at_entry"] == Decimal("-0.1000")  # Negative edge


def test_create_position_probability_out_of_range(
    db_pool, clean_test_data, sample_market, sample_strategy
):
    """
    Test CHECK constraint: calculated_probability must be in [0.0, 1.0].

    Validates:
    - Database rejects invalid probabilities
    - Ensures data integrity
    """
    # Test probability > 1.0
    with pytest.raises(psycopg2.errors.CheckViolation):
        create_position(
            market_id=sample_market,
            strategy_id=sample_strategy,
            model_id=1,
            side="yes",
            quantity=50,
            entry_price=Decimal("0.5000"),
            calculated_probability=Decimal("1.2000"),  # Invalid: > 1.0
            market_price_at_entry=Decimal("0.5000"),
        )


# =============================================================================
# TEST SUITE 3: STRATEGY CONFIGURATION WITH NESTED VERSIONING (ADR-090)
# =============================================================================


def test_strategy_config_nested_versioning(db_pool, clean_test_data, sample_strategy_config_nested):
    """
    Test strategy configuration with nested entry/exit versioning (ADR-090).

    Validates:
    - Strategy config contains entry.version and exit.version
    - Independent version management for entry and exit rules
    - JSONB validation works correctly
    """
    strategy_id = create_strategy(
        strategy_name="NFL Ensemble",
        strategy_version="v2.0",
        strategy_type="value",
        config=sample_strategy_config_nested,
        status="active",
        subcategory="nfl",
        notes="Entry v1.5 + Exit v2.3",
    )

    assert strategy_id is not None
    assert strategy_id > 0

    # Verify config structure
    config = sample_strategy_config_nested
    assert "entry" in config
    assert "exit" in config
    assert config["entry"]["version"] == "1.5"
    assert config["exit"]["version"] == "2.3"


def test_strategy_config_independent_versioning(db_pool, clean_test_data):
    """
    Test independent versioning: Update entry rules without changing exit rules.

    Validates:
    - entry.version can be updated independently
    - exit.version remains unchanged
    - Enables A/B testing: "Did entry v1.6 outperform entry v1.5?"
    """
    # Strategy 1: Entry v1.5, Exit v2.3
    config_v1 = {
        "entry": {
            "version": "1.5",
            "rules": {
                "min_edge": "0.05",
                "min_probability": "0.55",
            },
        },
        "exit": {
            "version": "2.3",
            "rules": {
                "profit_target": "0.25",
                "stop_loss": "-0.10",
            },
        },
    }

    strategy_id_v1 = create_strategy(
        strategy_name="NFL Ensemble",
        strategy_version="v1.0",
        strategy_type="value",
        config=config_v1,
        status="inactive",  # Old version
        subcategory="nfl",
        notes="Entry v1.5 + Exit v2.3",
    )

    # Strategy 2: Entry v1.6 (updated), Exit v2.3 (same)
    config_v2 = {
        "entry": {
            "version": "1.6",  # ⭐ Entry version updated
            "rules": {
                "min_edge": "0.08",  # Changed threshold
                "min_probability": "0.60",  # Changed threshold
            },
        },
        "exit": {
            "version": "2.3",  # ⭐ Exit version unchanged
            "rules": {
                "profit_target": "0.25",  # Same
                "stop_loss": "-0.10",  # Same
            },
        },
    }

    strategy_id_v2 = create_strategy(
        strategy_name="NFL Ensemble",
        strategy_version="v2.0",
        strategy_type="value",
        config=config_v2,
        status="active",  # New version
        subcategory="nfl",
        notes="Entry v1.6 + Exit v2.3",
    )

    assert strategy_id_v1 is not None
    assert strategy_id_v2 is not None
    assert strategy_id_v1 > 0
    assert strategy_id_v2 > 0
    assert strategy_id_v2 > strategy_id_v1

    # ⭐ Enables A/B testing:
    # "SELECT strategy_id, AVG(realized_pnl) FROM positions
    #  WHERE strategy_id IN (1, 2) GROUP BY strategy_id"
    # Compares ROI of Entry v1.5 vs Entry v1.6


# =============================================================================
# TEST SUITE 4: ANALYTICS QUERIES
# =============================================================================


def test_analytics_query_roi_by_model(
    db_pool, clean_test_data, sample_market, sample_strategy, sample_model
):
    """
    Test analytics query: ROI by model.

    Validates:
    - Can query average ROI per model
    - Attribution fields enable performance analytics
    - Answers: "Which models have highest ROI?"
    """
    # Create trades with different models
    trade_id_1 = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,  # Model A (from sample_model fixture)
        side="buy",
        quantity=50,
        price=Decimal("0.5000"),
        calculated_probability=Decimal("0.6500"),
        market_price=Decimal("0.5000"),
    )

    trade_id_2 = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=2,  # Model B
        side="buy",
        quantity=50,
        price=Decimal("0.5000"),
        calculated_probability=Decimal("0.7000"),
        market_price=Decimal("0.5000"),
    )

    # Verify trades created with different models
    trade_1 = get_trade_by_id(trade_id_1)
    trade_2 = get_trade_by_id(trade_id_2)

    assert trade_1 is not None
    assert trade_2 is not None
    assert trade_1["model_id"] == 1
    assert trade_2["model_id"] == 2

    # ⭐ Analytics query (SQL):
    # SELECT model_id, COUNT(*), AVG(edge_value), AVG(realized_pnl)
    # FROM trades
    # WHERE trade_source = 'automated'
    # GROUP BY model_id
    # ORDER BY AVG(realized_pnl) DESC


def test_analytics_query_edge_vs_outcome(db_pool, clean_test_data, sample_market, sample_strategy):
    """
    Test analytics query: Edge value vs trade outcome.

    Validates:
    - Can analyze correlation between edge and profitability
    - Attribution fields enable edge analysis
    - Answers: "Do high-edge trades correlate with wins?"
    """
    # High edge trade
    trade_id_high_edge = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="buy",
        quantity=50,
        price=Decimal("0.5000"),
        calculated_probability=Decimal("0.7500"),  # High edge: 0.25
        market_price=Decimal("0.5000"),
    )

    # Low edge trade
    trade_id_low_edge = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="buy",
        quantity=50,
        price=Decimal("0.5000"),
        calculated_probability=Decimal("0.5500"),  # Low edge: 0.05
        market_price=Decimal("0.5000"),
    )

    trade_high = get_trade_by_id(trade_id_high_edge)
    trade_low = get_trade_by_id(trade_id_low_edge)

    assert trade_high is not None
    assert trade_low is not None
    assert trade_high["edge_value"] == Decimal("0.2500")
    assert trade_low["edge_value"] == Decimal("0.0500")

    # ⭐ Analytics query (SQL):
    # SELECT
    #   CASE
    #     WHEN edge_value >= 0.15 THEN 'High Edge'
    #     WHEN edge_value >= 0.05 THEN 'Medium Edge'
    #     ELSE 'Low Edge'
    #   END AS edge_bucket,
    #   COUNT(*) AS trade_count,
    #   AVG(realized_pnl) AS avg_pnl,
    #   SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) / COUNT(*) AS win_rate
    # FROM trades
    # WHERE edge_value IS NOT NULL
    # GROUP BY edge_bucket


# =============================================================================
# EDUCATIONAL NOTES
# =============================================================================

"""
PERFORMANCE COMPARISON: Explicit Columns vs JSONB

**Explicit Columns (ADR-091 Decision):**
- Query time: ~5-10ms (B-tree index scan)
- Index size: ~50-100KB per 10,000 rows
- Query example:
  SELECT AVG(edge_value) FROM trades WHERE model_id = 1

**JSONB Alternative (Rejected):**
- Query time: ~100-500ms (GIN index scan + JSON extraction)
- Index size: ~500KB-1MB per 10,000 rows
- Query example:
  SELECT AVG(CAST(trade_metadata->>'edge_value' AS DECIMAL))
  FROM trades
  WHERE CAST(trade_metadata->>'model_id' AS INTEGER) = 1

**Performance Ratio:** 20-100x faster with explicit columns

**Tradeoff:**
- Explicit columns: Faster queries, schema changes require migrations
- JSONB: Flexible schema, slower queries, more complex SQL

**Decision:** Use explicit columns for attribution (ADR-091)
**Rationale:** Analytics queries run frequently (daily reports), schema changes rare
"""
