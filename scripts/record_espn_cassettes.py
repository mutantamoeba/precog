#!/usr/bin/env python
"""
Record ESPN API cassettes for VCR-based integration tests.

This script captures REAL ESPN API responses during live games.
Run during an NFL game (e.g., Sunday afternoons) to capture:
- Live game data with situation (down, distance, possession)
- Score updates
- Game state transitions

Usage:
    python scripts/record_espn_cassettes.py

Output:
    tests/cassettes/espn/*.yaml

Educational Note:
    VCR (Video Cassette Recorder) Pattern:
    - Records HTTP interactions to YAML files
    - Tests replay cassettes (no network needed)
    - Deterministic: Same responses every run
    - CI-friendly: Works without external APIs

References:
    - Pattern 13: Real Fixtures, Not Mocks
    - tests/integration/api_connectors/test_kalshi_client_vcr.py
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vcr

from precog.api_connectors.espn_client import ESPNClient

# Configure VCR for recording
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes/espn",
    record_mode="new_episodes",  # Record new requests, replay existing
    match_on=["method", "scheme", "host", "port", "path", "query"],
    decode_compressed_response=True,
)


def record_nfl_scoreboard():
    """Record NFL scoreboard response."""
    print("\n[1/5] Recording NFL scoreboard...")
    with my_vcr.use_cassette("espn_nfl_scoreboard.yaml"):
        client = ESPNClient(rate_limit_per_hour=500)
        games = client.get_nfl_scoreboard()
        print(f"      -> Recorded {len(games)} NFL games")
        for g in games[:3]:  # Show first 3
            meta = g.get("metadata", {})
            home = meta.get("home_team", {}).get("display_name", "Unknown")
            away = meta.get("away_team", {}).get("display_name", "Unknown")
            print(f"         {away} @ {home}")
        return games


def record_ncaaf_scoreboard():
    """Record NCAAF scoreboard response."""
    print("\n[2/5] Recording NCAAF scoreboard...")
    with my_vcr.use_cassette("espn_ncaaf_scoreboard.yaml"):
        client = ESPNClient(rate_limit_per_hour=500)
        games = client.get_ncaaf_scoreboard()
        print(f"      -> Recorded {len(games)} NCAAF games")
        return games


def record_nfl_live_games():
    """Record NFL live games (in-progress only)."""
    print("\n[3/5] Recording NFL live games...")
    with my_vcr.use_cassette("espn_nfl_live_games.yaml"):
        client = ESPNClient(rate_limit_per_hour=500)
        games = client.get_live_games(league="nfl")
        print(f"      -> Recorded {len(games)} live NFL games")
        for g in games:
            meta = g.get("metadata", {})
            state = g.get("state", {})
            situation = state.get("situation", {})
            down = situation.get("down", "N/A")
            distance = situation.get("distance", "N/A")
            home = meta.get("home_team", {}).get("display_name", "Unknown")
            away = meta.get("away_team", {}).get("display_name", "Unknown")
            print(f"         {away} @ {home}: Down {down}, {distance} to go")
        return games


def record_nba_scoreboard():
    """Record NBA scoreboard response."""
    print("\n[4/5] Recording NBA scoreboard...")
    with my_vcr.use_cassette("espn_nba_scoreboard.yaml"):
        client = ESPNClient(rate_limit_per_hour=500)
        games = client.get_nba_scoreboard()
        print(f"      -> Recorded {len(games)} NBA games")
        return games


def record_all_leagues():
    """Record responses from all supported leagues."""
    print("\n[5/5] Recording all leagues scoreboard...")
    leagues = ["nfl", "college-football", "nba", "mens-college-basketball", "nhl", "wnba"]
    results = {}

    for league in leagues:
        cassette_name = f"espn_{league.replace('-', '_')}_scoreboard.yaml"
        with my_vcr.use_cassette(cassette_name):
            client = ESPNClient(rate_limit_per_hour=500)
            try:
                games = client.get_scoreboard(league)
                results[league] = len(games)
                print(f"      -> {league}: {len(games)} games")
            except Exception as e:
                print(f"      -> {league}: ERROR - {e}")
                results[league] = 0

    return results


def main():
    """Record all ESPN cassettes."""
    print("=" * 60)
    print("ESPN Cassette Recording Script")
    print("=" * 60)
    print(f"Recording time: {datetime.now(UTC).isoformat()}")
    print("Output directory: tests/cassettes/espn/")

    # Check if there are live games
    try:
        client = ESPNClient(rate_limit_per_hour=500)
        live = client.get_live_games(league="nfl")
        if live:
            print(f"\nLIVE GAMES DETECTED: {len(live)} NFL games in progress!")
            print("This is the ideal time to record situation data.")
        else:
            print("\nNo live NFL games right now.")
            print("Scoreboard data will still be recorded.")
    except Exception as e:
        print(f"\nWarning: Could not check live games: {e}")

    # Record all cassettes
    record_nfl_scoreboard()
    record_ncaaf_scoreboard()
    record_nfl_live_games()
    record_nba_scoreboard()

    print("\n" + "=" * 60)
    print("Recording complete!")
    print("=" * 60)
    print("\nCassettes saved to tests/cassettes/espn/:")

    cassette_dir = Path("tests/cassettes/espn")
    for f in sorted(cassette_dir.glob("*.yaml")):
        size = f.stat().st_size
        print(f"  - {f.name} ({size:,} bytes)")

    print("\nNext steps:")
    print("1. Create tests/integration/api_connectors/test_espn_client_vcr.py")
    print("2. Run: pytest tests/integration/api_connectors/test_espn_client_vcr.py -v")
    print("3. Commit cassettes and test file")


if __name__ == "__main__":
    main()
