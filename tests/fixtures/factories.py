"""
Test Data Factories - Phase 0.6c

Factory patterns for creating test data using factory-boy.

Usage:
    from tests.fixtures.factories import MarketFactory, PositionFactory

    # Create a test market with defaults
    market = MarketFactory()

    # Create with custom values
    market = MarketFactory(
        ticker="TEST-NFL-KC-BUF-YES",
        yes_bid=Decimal("0.6000")
    )

    # Create multiple
    markets = MarketFactory.create_batch(5)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import factory
from faker import Faker

# Note: Actual model imports will be added when models are implemented
# from database.models import Market, Position, Trade, Strategy, ProbabilityModel

fake = Faker()


# ==============================================================================
# Base Factories
# ==============================================================================


class BaseFactory(factory.Factory):
    """Base factory with common settings."""

    class Meta:
        abstract = True


# ==============================================================================
# Market Data Factories
# ==============================================================================


class MarketDataFactory(BaseFactory):
    """
    Factory for market test data (dict format for testing CRUD operations).

    Use this when database models aren't available yet.
    """

    class Meta:
        model = dict

    ticker = factory.Sequence(lambda n: f"TEST-NFL-GAME{n:03d}-YES")
    event_ticker = factory.Sequence(lambda n: f"TEST-NFL-GAME{n:03d}")
    series_ticker = "TEST-NFL-2025"

    yes_bid = Decimal("0.5000")
    yes_ask = Decimal("0.5100")
    no_bid = Decimal("0.4900")
    no_ask = Decimal("0.5000")

    last_price = Decimal("0.5050")
    volume = 1000
    open_interest = 5000

    status = "active"
    close_time = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(days=1))
    expiration_time = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(days=2))

    subtitle = factory.LazyAttribute(lambda obj: f"Will {obj.event_ticker} resolve YES?")


class PositionDataFactory(BaseFactory):
    """Factory for position test data (dict format)."""

    class Meta:
        model = dict

    ticker = factory.Sequence(lambda n: f"TEST-NFL-GAME{n:03d}-YES")
    side = "YES"
    quantity = 100
    avg_entry_price = Decimal("0.5050")
    current_price = Decimal("0.5500")

    unrealized_pnl = factory.LazyAttribute(
        lambda obj: (obj.current_price - obj.avg_entry_price) * obj.quantity
    )

    position_status = "open"
    entry_time = factory.LazyFunction(lambda: datetime.utcnow() - timedelta(hours=2))


class TradeDataFactory(BaseFactory):
    """Factory for trade test data (dict format)."""

    class Meta:
        model = dict

    ticker = factory.Sequence(lambda n: f"TEST-NFL-GAME{n:03d}-YES")
    side = "YES"
    action = "BUY"
    quantity = 100
    price = Decimal("0.5050")

    total_cost = factory.LazyAttribute(lambda obj: obj.price * obj.quantity)

    order_type = "LIMIT"
    time_in_force = "GTC"
    status = "FILLED"

    created_at = factory.LazyFunction(datetime.utcnow)
    filled_at = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(seconds=5))


# ==============================================================================
# Strategy & Model Factories
# ==============================================================================


class StrategyDataFactory(BaseFactory):
    """Factory for strategy test data (dict format)."""

    class Meta:
        model = dict

    strategy_name = factory.Sequence(lambda n: f"test_strategy_{n}")
    strategy_version = "v1.0"

    config = factory.LazyFunction(
        lambda: {
            "min_edge": 0.05,
            "max_position_size": 1000,
            "entry_timing": "halftime",
            "risk_multiplier": 1.0,
        }
    )

    status = "active"  # active, testing, deprecated
    description = factory.LazyAttribute(
        lambda obj: f"Test strategy {obj.strategy_name} {obj.strategy_version}"
    )


class ProbabilityModelDataFactory(BaseFactory):
    """Factory for probability model test data (dict format)."""

    class Meta:
        model = dict

    model_name = factory.Sequence(lambda n: f"test_model_{n}")
    model_version = "v1.0"

    config = factory.LazyFunction(
        lambda: {
            "model_type": "elo_based",
            "confidence_threshold": 0.75,
            "adjustment_factor": 1.0,
        }
    )

    status = "active"
    description = factory.LazyAttribute(
        lambda obj: f"Test model {obj.model_name} {obj.model_version}"
    )


# ==============================================================================
# Edge Case Factories
# ==============================================================================


class DecimalEdgeCaseFactory(BaseFactory):
    """Factory for decimal edge case prices."""

    class Meta:
        model = dict

    @classmethod
    def min_price(cls):
        """Minimum allowed price."""
        return {"price": Decimal("0.0001")}

    @classmethod
    def max_price(cls):
        """Maximum allowed price."""
        return {"price": Decimal("0.9999")}

    @classmethod
    def sub_penny(cls):
        """Sub-penny precision price."""
        return {"price": Decimal("0.4275")}

    @classmethod
    def rounded_penny(cls):
        """Rounded penny price."""
        return {"price": Decimal("0.5000")}

    @classmethod
    def edge_cases(cls):
        """All edge case prices."""
        return [
            cls.min_price(),
            cls.max_price(),
            cls.sub_penny(),
            cls.rounded_penny(),
        ]


# ==============================================================================
# Game State Factories
# ==============================================================================


class GameStateDataFactory(BaseFactory):
    """Factory for game state test data (dict format)."""

    class Meta:
        model = dict

    event_ticker = factory.Sequence(lambda n: f"TEST-NFL-GAME{n:03d}")

    home_team = factory.Faker("city")
    away_team = factory.Faker("city")

    home_score = factory.Faker("random_int", min=0, max=35)
    away_score = factory.Faker("random_int", min=0, max=35)

    period = "Q2"
    time_remaining = "08:45"

    possession = factory.LazyAttribute(lambda obj: obj.home_team)

    game_status = "in_progress"
    updated_at = factory.LazyFunction(datetime.utcnow)


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_test_market_with_position() -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Create a test market with an associated position.

    Returns:
        Tuple of (market_data, position_data)
    """
    market = cast("dict[str, Any]", MarketDataFactory())
    position = cast(
        "dict[str, Any]",
        PositionDataFactory(
            ticker=market["ticker"],
            current_price=market["yes_bid"],
        ),
    )
    return market, position


def create_test_trade_sequence(ticker: str, num_trades: int = 3):
    """
    Create a sequence of trades for the same market.

    Args:
        ticker: Market ticker
        num_trades: Number of trades to create

    Returns:
        List of trade data dicts
    """
    return TradeDataFactory.create_batch(num_trades, ticker=ticker)


def create_versioned_strategies(base_name: str, num_versions: int = 3):
    """
    Create multiple versions of the same strategy.

    Args:
        base_name: Strategy base name
        num_versions: Number of versions to create

    Returns:
        List of strategy data dicts (v1.0, v1.1, v1.2, ...)
    """
    strategies = []
    for i in range(num_versions):
        version = f"v1.{i}"
        status = "deprecated" if i < num_versions - 1 else "active"
        strategies.append(
            StrategyDataFactory(
                strategy_name=base_name,
                strategy_version=version,
                status=status,
            )
        )
    return strategies


# ==============================================================================
# Example Usage (for documentation)
# ==============================================================================

if __name__ == "__main__":
    """Example usage of factories."""

    # Create a single market
    market = cast("dict[str, Any]", MarketDataFactory())
    print(f"Market: {market['ticker']}")
    print(f"Yes bid: {market['yes_bid']}")

    # Create multiple markets
    markets = MarketDataFactory.create_batch(5)
    print(f"\nCreated {len(markets)} markets")

    # Create market with custom values
    custom_market = cast(
        "dict[str, Any]",
        MarketDataFactory(
            ticker="TEST-NFL-KC-BUF-YES",
            yes_bid=Decimal("0.7500"),
        ),
    )
    print(f"\nCustom market: {custom_market['ticker']}")
    print(f"Yes bid: {custom_market['yes_bid']}")

    # Create edge case prices
    edge_cases = DecimalEdgeCaseFactory.edge_cases()
    for case in edge_cases:
        print(f"Edge case price: {case['price']}")

    # Create market with position
    market, position = create_test_market_with_position()
    print(f"\nMarket: {market['ticker']}")
    print(f"Position PnL: {position['unrealized_pnl']}")

    # Create versioned strategies
    strategies = create_versioned_strategies("halftime_entry", 3)
    for strat in strategies:
        print(f"Strategy: {strat['strategy_name']} {strat['strategy_version']} - {strat['status']}")
