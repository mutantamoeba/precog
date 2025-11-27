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

Note:
    ESPN factories use camelCase attribute names (displayName, homeAway, etc.)
    to match ESPN API response structure exactly. This is intentional - the
    factories generate mock data that must have the same keys as real API responses.
"""
# ruff: noqa: N815, RUF012

from datetime import datetime, timedelta
from decimal import Decimal

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
# ESPN API Response Factories (Phase 2)
# ==============================================================================


class ESPNTeamFactory(BaseFactory):
    """Factory for ESPN team data within competitor objects."""

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: str(n + 1))
    uid = factory.LazyAttribute(lambda obj: f"s:20~l:28~t:{obj.id}")
    location = factory.Faker("city")
    name = factory.Faker("last_name")
    abbreviation = factory.LazyAttribute(lambda obj: obj.name[:3].upper())
    displayName = factory.LazyAttribute(lambda obj: f"{obj.location} {obj.name}")
    shortDisplayName = factory.LazyAttribute(lambda obj: obj.name)
    color = factory.Faker("hex_color")
    alternateColor = factory.Faker("hex_color")
    logo = factory.LazyAttribute(
        lambda obj: f"https://a.espncdn.com/i/teamlogos/nfl/500/{obj.abbreviation.lower()}.png"
    )


class ESPNCompetitorFactory(BaseFactory):
    """Factory for ESPN competitor (team in a game) data."""

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: str(n + 1))
    uid = factory.LazyAttribute(lambda obj: f"s:20~l:28~t:{obj.id}")
    type = "team"
    order = 0  # 0 for home, 1 for away
    homeAway = "home"
    winner = False

    team = factory.SubFactory(ESPNTeamFactory)

    score = factory.LazyFunction(lambda: str(fake.random_int(min=0, max=42)))
    linescores = factory.LazyFunction(
        lambda: [{"value": fake.random_int(min=0, max=14)} for _ in range(4)]
    )
    statistics = []
    records = factory.LazyFunction(
        lambda: [
            {"name": "overall", "summary": f"{fake.random_int(0, 14)}-{fake.random_int(0, 14)}"},
            {"name": "home", "summary": f"{fake.random_int(0, 7)}-{fake.random_int(0, 7)}"},
        ]
    )


class ESPNGameStatusFactory(BaseFactory):
    """Factory for ESPN game status data."""

    class Meta:
        model = dict

    clock = factory.LazyFunction(lambda: float(fake.random_int(min=0, max=900)))
    displayClock = factory.LazyAttribute(
        lambda obj: f"{int(obj.clock // 60)}:{int(obj.clock % 60):02d}"
    )
    period = factory.Faker("random_int", min=1, max=4)

    type = factory.LazyFunction(
        lambda: {
            "id": "2",
            "name": "STATUS_IN_PROGRESS",
            "state": "in",
            "completed": False,
            "description": "In Progress",
            "detail": "In Progress",
            "shortDetail": "In Progress",
        }
    )

    @classmethod
    def pregame(cls):
        """Create a pre-game status."""
        return cls(
            clock=0.0,
            displayClock="0:00",
            period=0,
            type={
                "id": "1",
                "name": "STATUS_SCHEDULED",
                "state": "pre",
                "completed": False,
                "description": "Scheduled",
                "detail": "Scheduled",
                "shortDetail": "Scheduled",
            },
        )

    @classmethod
    def in_progress(cls, period: int = 2, clock: float = 720.0):
        """Create an in-progress status."""
        display_clock = f"{int(clock // 60)}:{int(clock % 60):02d}"
        return cls(
            clock=clock,
            displayClock=display_clock,
            period=period,
            type={
                "id": "2",
                "name": "STATUS_IN_PROGRESS",
                "state": "in",
                "completed": False,
                "description": "In Progress",
                "detail": f"Q{period} - {display_clock}",
                "shortDetail": f"Q{period} - {display_clock}",
            },
        )

    @classmethod
    def halftime(cls):
        """Create a halftime status."""
        return cls(
            clock=0.0,
            displayClock="0:00",
            period=2,
            type={
                "id": "23",
                "name": "STATUS_HALFTIME",
                "state": "in",
                "completed": False,
                "description": "Halftime",
                "detail": "Halftime",
                "shortDetail": "Halftime",
            },
        )

    @classmethod
    def final(cls):
        """Create a final (completed game) status."""
        return cls(
            clock=0.0,
            displayClock="0:00",
            period=4,
            type={
                "id": "3",
                "name": "STATUS_FINAL",
                "state": "post",
                "completed": True,
                "description": "Final",
                "detail": "Final",
                "shortDetail": "Final",
            },
        )


class ESPNSituationFactory(BaseFactory):
    """Factory for ESPN game situation (possession, down, etc.) data."""

    class Meta:
        model = dict

    down = factory.Faker("random_int", min=1, max=4)
    yardLine = factory.Faker("random_int", min=1, max=99)
    distance = factory.Faker("random_int", min=1, max=15)
    downDistanceText = factory.LazyAttribute(
        lambda obj: f"{obj.down}{'st' if obj.down == 1 else 'nd' if obj.down == 2 else 'rd' if obj.down == 3 else 'th'} & {obj.distance}"
    )
    shortDownDistanceText = factory.LazyAttribute(
        lambda obj: f"{obj.down}{'st' if obj.down == 1 else 'nd' if obj.down == 2 else 'rd' if obj.down == 3 else 'th'} & {obj.distance}"
    )
    possessionText = "Home Ball"
    isRedZone = factory.LazyAttribute(lambda obj: obj.yardLine <= 20)
    homeTimeouts = factory.Faker("random_int", min=0, max=3)
    awayTimeouts = factory.Faker("random_int", min=0, max=3)
    possession = "1"  # Team ID with possession


class ESPNCompetitionFactory(BaseFactory):
    """Factory for ESPN competition (a single game/matchup) data."""

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: str(401547400 + n))
    uid = factory.LazyAttribute(lambda obj: f"s:20~l:28~e:{obj.id}~c:{obj.id}")
    date = factory.LazyFunction(lambda: datetime.utcnow().isoformat() + "Z")
    attendance = factory.Faker("random_int", min=60000, max=82500)

    type = {"id": "1", "abbreviation": "STD"}
    timeValid = True
    neutralSite = False
    conferenceCompetition = False
    playByPlayAvailable = True
    recent = True

    venue = factory.LazyFunction(
        lambda: {
            "id": str(fake.random_int(min=1000, max=9999)),
            "fullName": f"{fake.city()} Stadium",
            "address": {"city": fake.city(), "state": fake.state_abbr()},
            "capacity": fake.random_int(min=60000, max=82500),
            "indoor": False,
        }
    )

    # Default: create home and away competitors
    competitors = factory.LazyFunction(
        lambda: [
            ESPNCompetitorFactory(order=0, homeAway="home"),
            ESPNCompetitorFactory(order=1, homeAway="away"),
        ]
    )

    status = factory.SubFactory(ESPNGameStatusFactory)

    broadcasts = factory.LazyFunction(
        lambda: [
            {"market": "national", "names": [fake.random_element(["CBS", "FOX", "NBC", "ESPN"])]}
        ]
    )

    situation = factory.SubFactory(ESPNSituationFactory)


class ESPNEventFactory(BaseFactory):
    """Factory for ESPN event (game) data - the top-level object."""

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: str(401547400 + n))
    uid = factory.LazyAttribute(lambda obj: f"s:20~l:28~e:{obj.id}")
    date = factory.LazyFunction(lambda: datetime.utcnow().isoformat() + "Z")

    name = factory.LazyFunction(
        lambda: f"{fake.city()} {fake.last_name()} at {fake.city()} {fake.last_name()}"
    )
    shortName = factory.LazyAttribute(lambda obj: " @ ".join(obj.name.split(" at ")[::-1][:2]))

    season = {"year": 2025, "type": 2, "slug": "regular-season"}
    week = {"number": factory.Faker("random_int", min=1, max=18)}

    competitions = factory.LazyAttribute(lambda obj: [ESPNCompetitionFactory(id=obj.id)])

    status = factory.SubFactory(ESPNGameStatusFactory)


class ESPNScoreboardFactory(BaseFactory):
    """
    Factory for ESPN scoreboard API response.

    This creates complete scoreboard responses for testing.

    Usage:
        # Create scoreboard with 3 games
        scoreboard = ESPNScoreboardFactory(num_events=3)

        # Create empty scoreboard (no games)
        empty = ESPNScoreboardFactory(num_events=0)
    """

    class Meta:
        model = dict

    leagues = factory.LazyFunction(
        lambda: [
            {
                "id": "28",
                "uid": "s:20~l:28",
                "name": "National Football League",
                "abbreviation": "NFL",
                "slug": "nfl",
                "season": {"year": 2025, "type": 2},
            }
        ]
    )

    season = {"type": 2, "year": 2025}
    week = {"number": factory.Faker("random_int", min=1, max=18)}

    events = factory.LazyFunction(lambda: [ESPNEventFactory() for _ in range(2)])

    @classmethod
    def with_events(cls, num_events: int = 2):
        """Create a scoreboard with a specific number of events."""
        return cls(events=[ESPNEventFactory() for _ in range(num_events)])

    @classmethod
    def empty(cls):
        """Create an empty scoreboard (no games today)."""
        return cls(events=[])

    @classmethod
    def ncaaf(cls, num_events: int = 2):
        """Create an NCAAF scoreboard."""
        return cls(
            leagues=[
                {
                    "id": "23",
                    "uid": "s:20~l:23",
                    "name": "NCAA - Football",
                    "abbreviation": "NCAAF",
                    "slug": "college-football",
                    "season": {"year": 2025, "type": 2},
                }
            ],
            events=[ESPNEventFactory() for _ in range(num_events)],
        )


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


def create_test_market_with_position() -> tuple[dict, dict]:
    """
    Create a test market with an associated position.

    Returns:
        Tuple of (market_data, position_data)
    """
    market: dict = MarketDataFactory()  # type: ignore[assignment]
    position: dict = PositionDataFactory(  # type: ignore[assignment]
        ticker=market["ticker"],
        current_price=market["yes_bid"],
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
    from typing import Any

    # Create a single market
    market: dict[str, Any] = MarketDataFactory()  # type: ignore[assignment]
    print(f"Market: {market['ticker']}")
    print(f"Yes bid: {market['yes_bid']}")

    # Create multiple markets
    markets = MarketDataFactory.create_batch(5)
    print(f"\nCreated {len(markets)} markets")

    # Create market with custom values
    custom_market: dict[str, Any] = MarketDataFactory(  # type: ignore[assignment]
        ticker="TEST-NFL-KC-BUF-YES",
        yes_bid=Decimal("0.7500"),
    )
    print(f"\nCustom market: {custom_market['ticker']}")
    print(f"Yes bid: {custom_market['yes_bid']}")

    # Create edge case prices
    edge_cases = DecimalEdgeCaseFactory.edge_cases()
    for case in edge_cases:
        print(f"Edge case price: {case['price']}")

    # Create market with position
    market_with_pos, position = create_test_market_with_position()
    print(f"\nMarket: {market_with_pos['ticker']}")
    print(f"Position PnL: {position['unrealized_pnl']}")

    # Create versioned strategies
    strategies = create_versioned_strategies("halftime_entry", 3)
    for strat in strategies:
        print(f"Strategy: {strat['strategy_name']} {strat['strategy_version']} - {strat['status']}")
