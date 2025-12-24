#!/usr/bin/env python
"""
Record VCR cassettes from live Kalshi API.

This script records HTTP interactions as VCR cassettes for use in
integration tests. Cassettes allow tests to replay API responses
without needing network access or credentials.

IMPORTANT: Order operations use PROD (not DEMO) because Kalshi's DEMO
environment has intermittent 503 errors on its "exchange" service.
Order tests place very low-price orders ($0.02) that won't fill, then
immediately cancel them. See ADR-TBD for analysis.

Usage:
    python scripts/record_kalshi_cassettes.py [endpoint]

Examples:
    python scripts/record_kalshi_cassettes.py series   # Record get_series (DEMO)
    python scripts/record_kalshi_cassettes.py orders   # Record orders (PROD)
    python scripts/record_kalshi_cassettes.py all      # Record all endpoints

Prerequisites:
    - DEV_KALSHI_API_KEY set in .env (for DEMO)
    - DEV_KALSHI_PRIVATE_KEY_PATH set in .env
    - KALSHI_API_KEY set in .env (for PROD order testing)
    - KALSHI_PRIVATE_KEY_PATH set in .env

Output:
    Cassettes saved to tests/cassettes/kalshi_*.yaml

Educational Note:
    VCR (Video Cassette Recorder) Pattern:
    - Record real API responses ONCE
    - Replay in tests (fast, no network, no credentials needed)
    - Tests use 100% real data structures
    - Catches API contract changes

    DEMO vs PROD for Testing:
    - DEMO: Safe for GET operations (markets, balance, series)
    - PROD: Required for order operations (503 errors in DEMO)
    - Always use unfillable prices ($0.02) and cancel immediately

Reference:
    - tests/integration/api_connectors/test_kalshi_client_vcr.py
    - Phase 1.5 Test Audit: 77% false positive rate from mocks
"""

import os
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import vcr

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from precog.api_connectors.kalshi_client import KalshiClient


def setup_vcr(cassette_name: str) -> vcr.VCR:
    """
    Configure VCR for recording cassettes.

    Args:
        cassette_name: Name of cassette file (without .yaml extension)

    Returns:
        Configured VCR instance
    """
    return vcr.VCR(
        cassette_library_dir="tests/cassettes",
        record_mode="new_episodes",  # Record new interactions
        match_on=["method", "scheme", "host", "port", "path", "query"],
        filter_headers=[
            "KALSHI-ACCESS-KEY",
            "KALSHI-ACCESS-SIGNATURE",
            "KALSHI-ACCESS-TIMESTAMP",
        ],
        decode_compressed_response=True,
    )


def record_get_series():
    """
    Record VCR cassette for get_series() endpoint.

    Records:
    - First 10 series (no category filter)
    - Sports category series (category filter test)
    - Full response structure for testing

    Output: tests/cassettes/kalshi_get_series.yaml
    """
    print("Recording get_series() cassette...")
    print("-" * 50)

    my_vcr = setup_vcr("kalshi_get_series")

    with my_vcr.use_cassette("kalshi_get_series.yaml"):
        client = KalshiClient(environment="demo")

        # Record 1: Series without category filter
        print("Fetching series (limit=10, no filter)...")
        series = client.get_series(limit=10)

        print(f"Received {len(series)} series")
        if series:
            print(f"First series: {series[0].get('ticker', 'N/A')}")
            print(f"  Title: {series[0].get('title', 'N/A')}")
            print(f"  Category: {series[0].get('category', 'N/A')}")

        # Collect all categories from unfiltered results
        categories_found = set()
        for s in series:
            cat = s.get("category")
            if cat:
                categories_found.add(cat)
        print(f"Categories in response: {sorted(categories_found)}")

        time.sleep(1)  # Rate limit safety

        # Record 2: Series WITH Sports category filter
        print("\nFetching series with category=Sports filter...")
        sports_series = client.get_series(category="Sports", limit=5)

        print(f"Received {len(sports_series)} Sports series")
        for s in sports_series[:3]:  # Show first 3
            print(f"  - {s.get('ticker', 'N/A')}: {s.get('title', 'N/A')}")

    print("-" * 50)
    print("SUCCESS: Cassette saved to tests/cassettes/kalshi_get_series.yaml")
    print()
    return True


def record_order_lifecycle():
    """
    Record VCR cassette for order operations from PROD.

    IMPORTANT: Uses PROD because Kalshi DEMO has 503 errors on orders.
    Places a very low-price order that won't fill, then cancels.

    Records:
    - GET /markets (find a valid market)
    - POST /portfolio/orders (place order)
    - GET /portfolio/orders/{id} (get order)
    - DELETE /portfolio/orders/{id} (cancel order)

    Output: tests/cassettes/kalshi_order_lifecycle.yaml

    Risk Assessment:
    - Order placed at $0.02 (2 cents) - will NOT fill
    - Immediately canceled after recording
    - Total financial risk: $0 (order never fills)
    """
    print("Recording order lifecycle cassette from PROD...")
    print("(Using PROD because DEMO has 503 errors on orders)")
    print("-" * 50)

    # Check for PROD credentials
    prod_key = os.getenv("KALSHI_API_KEY") or os.getenv("PROD_KALSHI_API_KEY")
    if not prod_key:
        print("ERROR: PROD credentials not configured")
        print("Required: KALSHI_API_KEY or PROD_KALSHI_API_KEY in .env")
        return False

    my_vcr = setup_vcr("kalshi_order_lifecycle")

    with my_vcr.use_cassette("kalshi_order_lifecycle.yaml"):
        client = KalshiClient(environment="prod")

        # Step 1: Get a valid market
        print("Step 1: Finding a valid market...")
        markets = client.get_markets(series_ticker="KXNFLGAME", limit=1)
        if not markets:
            print("  ERROR: No NFL markets found")
            return False

        market = markets[0]
        ticker = market["ticker"]
        print(f"  Found: {ticker}")
        print(f"  Current YES bid: ${market.get('yes_bid_dollars', 'N/A')}")

        time.sleep(1)  # Rate limit safety

        # Step 2: Place order at unfillable price
        print("Step 2: Placing test order at $0.02 (unfillable)...")
        order = client.place_order(
            ticker=ticker,
            side="yes",
            action="buy",
            count=1,
            price=Decimal("0.02"),  # $0.02 - won't fill
            order_type="limit",
            client_order_id=f"vcr-test-{int(time.time())}",
        )
        order_id = order.get("order_id", "unknown")
        print(f"  Order placed: {order_id}")
        print(f"  Status: {order.get('status', 'N/A')}")

        time.sleep(1)

        # Step 3: Get order details
        print("Step 3: Getting order details...")
        order_details = client.get_order(order_id)
        print(f"  Order status: {order_details.get('status', 'N/A')}")
        print(f"  Remaining: {order_details.get('remaining_count', 'N/A')}")

        time.sleep(1)

        # Step 4: Cancel order
        print("Step 4: Canceling test order...")
        canceled = client.cancel_order(order_id)
        print(f"  Cancel status: {canceled.get('status', 'N/A')}")

        client.close()

    print("-" * 50)
    print("SUCCESS: Cassette saved to tests/cassettes/kalshi_order_lifecycle.yaml")
    print()
    return True


def record_get_series_all():
    """
    Record VCR cassette for get_series() with all categories.

    Records:
    - All series (no filter, limit 100)
    - Includes category and tag information

    Output: tests/cassettes/kalshi_get_series_all.yaml
    """
    print("Recording get_series() all categories cassette...")
    print("-" * 50)

    my_vcr = setup_vcr("kalshi_get_series_all")

    with my_vcr.use_cassette("kalshi_get_series_all.yaml"):
        client = KalshiClient(environment="demo")

        # Record all series (first 100)
        print("Fetching all series (limit=100)...")
        series = client.get_series(limit=100)

        print(f"Received {len(series)} series")

        # Show category breakdown
        categories: dict[str, int] = {}
        for s in series:
            cat = s.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        print("Categories found:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")

    print("-" * 50)
    print("SUCCESS: Cassette saved to tests/cassettes/kalshi_get_series_all.yaml")
    print()
    return True


def main():
    """
    Main entry point for cassette recording.

    Supports:
    - 'series': Record get_series (DEMO)
    - 'series_all': Record get_series with all categories (DEMO)
    - 'orders': Record order lifecycle (PROD - required due to DEMO 503 errors)
    - 'all': Record all endpoints (DEMO for series, PROD for orders)
    """
    # Check for DEMO credentials
    demo_key = os.getenv("DEV_KALSHI_API_KEY")
    demo_key_path = os.getenv("DEV_KALSHI_PRIVATE_KEY_PATH")

    # Check for PROD credentials (needed for orders)
    prod_key = os.getenv("KALSHI_API_KEY") or os.getenv("PROD_KALSHI_API_KEY")

    if not demo_key or not demo_key_path:
        print("ERROR: DEMO Kalshi credentials not configured")
        print("Required environment variables:")
        print("  DEV_KALSHI_API_KEY")
        print("  DEV_KALSHI_PRIVATE_KEY_PATH")
        print()
        print("Set these in your .env file")
        sys.exit(1)

    # Parse command line
    endpoint = sys.argv[1] if len(sys.argv) > 1 else "all"

    print("=" * 60)
    print("Kalshi VCR Cassette Recorder")
    print(f"Recording: {endpoint}")
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print()
    print("Environment Status:")
    print(f"  DEMO credentials: {'OK' if demo_key else 'MISSING'}")
    print(f"  PROD credentials: {'OK' if prod_key else 'MISSING (needed for orders)'}")
    print("=" * 60)
    print()

    success = True

    if endpoint == "series":
        success = record_get_series()
    elif endpoint == "series_all":
        success = record_get_series_all()
    elif endpoint == "orders":
        if not prod_key:
            print("ERROR: PROD credentials required for order recording")
            print("Set KALSHI_API_KEY in .env")
            sys.exit(1)
        success = record_order_lifecycle()
    elif endpoint == "all":
        success = record_get_series()
        success = record_get_series_all() and success
        if prod_key:
            success = record_order_lifecycle() and success
        else:
            print("WARNING: Skipping orders (PROD credentials not set)")
    else:
        print(f"Unknown endpoint: {endpoint}")
        print("Available options: series, series_all, orders, all")
        sys.exit(1)

    if success:
        print("=" * 60)
        print("All cassettes recorded successfully!")
        print("=" * 60)
    else:
        print("=" * 60)
        print("Some recordings failed. Check output above.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
