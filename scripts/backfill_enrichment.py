#!/usr/bin/env python3
"""
Backfill enrichment data for events and markets.

Fills NULL enrichment columns on events (start_time, end_time, status, result)
and markets (settlement_value) that were created before enrichment code was
deployed.  Idempotent -- safe to run multiple times.

Operations (all pure SQL unless --skip-api is omitted):
    1. Event times    -- derive start_time/end_time from child market timestamps
    2. Event status   -- set 'final' when all children settled, 'live' otherwise
    3. Market settlement_value -- re-fetch from Kalshi API (skipped with --skip-api)
    4. Event result   -- build JSONB result from child markets' settlement values
       (runs AFTER market settlement_value so JSONB contains populated values)

Usage:
    # Dry run (shows what would change, no writes):
    python scripts/backfill_enrichment.py --dry-run

    # SQL-only backfills (no Kalshi API calls):
    python scripts/backfill_enrichment.py --skip-api

    # Full backfill including API re-fetch:
    python scripts/backfill_enrichment.py

    # Dry run + skip API:
    python scripts/backfill_enrichment.py --dry-run --skip-api

Prerequisites:
    - Database credentials in .env (DB_HOST, DB_USER, etc.)
    - For market settlement_value backfill: DEV_KALSHI_API_KEY + key path in .env

Reference:
    - Issue #513: Enrichment data gaps
    - PR #515: settlement_value_dollars from API
    - events table is NOT SCD Type 2 (direct UPDATE)
    - markets dimension table is NOT SCD Type 2 (direct UPDATE on dimension)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from precog.database.connection import (
    fetch_all,
    fetch_one,
    get_cursor,
    initialize_pool,
)
from precog.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 1. Event times backfill
# ---------------------------------------------------------------------------


def backfill_event_times(*, dry_run: bool = False) -> int:
    """Derive event start_time/end_time from child market timestamps.

    Sets start_time = MIN(markets.open_time) and end_time = MAX(markets.expiration_time)
    for events where these columns are NULL.

    Args:
        dry_run: If True, only count affected rows without writing.

    Returns:
        Number of events updated (or that would be updated in dry-run).
    """
    if dry_run:
        count_query = """
            SELECT COUNT(*) AS cnt
            FROM events e
            WHERE (e.start_time IS NULL OR e.end_time IS NULL)
              AND EXISTS (
                  SELECT 1 FROM markets m
                  WHERE m.event_internal_id = e.id
                    AND (m.open_time IS NOT NULL OR m.expiration_time IS NOT NULL)
              )
        """
        row = fetch_one(count_query)
        return int(row["cnt"]) if row else 0

    update_query = """
        UPDATE events SET
            start_time = COALESCE(events.start_time, sub.min_open),
            end_time = COALESCE(events.end_time, sub.max_exp),
            updated_at = NOW()
        FROM (
            SELECT event_internal_id,
                   MIN(open_time) AS min_open,
                   MAX(expiration_time) AS max_exp
            FROM markets
            WHERE open_time IS NOT NULL OR expiration_time IS NOT NULL
            GROUP BY event_internal_id
        ) sub
        WHERE events.id = sub.event_internal_id
          AND (events.start_time IS NULL OR events.end_time IS NULL)
    """
    with get_cursor(commit=True) as cur:
        cur.execute(update_query)
        return cur.rowcount or 0


# ---------------------------------------------------------------------------
# 2. Event status backfill
# ---------------------------------------------------------------------------


def backfill_event_status(*, dry_run: bool = False) -> dict[str, int]:
    """Set event status based on child market settlement state.

    - status='final' when ALL child markets are settled
    - status='live'  when at least one child market is NOT settled

    Only touches events where status IS NULL.

    Args:
        dry_run: If True, only count affected rows without writing.

    Returns:
        Dict with keys 'final' and 'live' giving counts per status.
    """
    if dry_run:
        count_query = """
            SELECT
                SUM(CASE WHEN total = settled THEN 1 ELSE 0 END) AS final_cnt,
                SUM(CASE WHEN total != settled THEN 1 ELSE 0 END) AS live_cnt
            FROM (
                SELECT e.id,
                       COUNT(m.id) AS total,
                       COUNT(m.id) FILTER (WHERE m.status = 'settled') AS settled
                FROM events e
                JOIN markets m ON m.event_internal_id = e.id
                WHERE e.status IS NULL
                GROUP BY e.id
                HAVING COUNT(m.id) > 0
            ) sub
        """
        row = fetch_one(count_query)
        if row is None:
            return {"final": 0, "live": 0}
        return {
            "final": int(row["final_cnt"] or 0),
            "live": int(row["live_cnt"] or 0),
        }

    # Set 'final' for fully settled events
    final_query = """
        UPDATE events SET status = 'final', updated_at = NOW()
        WHERE status IS NULL
          AND id IN (
              SELECT event_internal_id
              FROM markets
              GROUP BY event_internal_id
              HAVING COUNT(*) = COUNT(*) FILTER (WHERE status = 'settled')
                 AND COUNT(*) > 0
          )
    """
    # Set 'live' for partially settled / open events
    live_query = """
        UPDATE events SET status = 'live', updated_at = NOW()
        WHERE status IS NULL
          AND id IN (
              SELECT event_internal_id
              FROM markets
              GROUP BY event_internal_id
              HAVING COUNT(*) > COUNT(*) FILTER (WHERE status = 'settled')
                 AND COUNT(*) > 0
          )
    """
    with get_cursor(commit=True) as cur:
        cur.execute(final_query)
        final_count = cur.rowcount or 0
        cur.execute(live_query)
        live_count = cur.rowcount or 0

    return {"final": final_count, "live": live_count}


# ---------------------------------------------------------------------------
# 3. Event result backfill
# ---------------------------------------------------------------------------


def backfill_event_results(*, dry_run: bool = False) -> int:
    """Build JSONB result for final events with NULL result.

    For each event with status='final' and result IS NULL, assembles a result
    dict from child markets' tickers and settlement_values, then writes it.

    Args:
        dry_run: If True, only count affected rows without writing.

    Returns:
        Number of events updated (or that would be updated in dry-run).
    """
    # Find events needing result population
    find_query = """
        SELECT e.id AS event_id
        FROM events e
        WHERE e.status = 'final'
          AND e.result IS NULL
          AND EXISTS (SELECT 1 FROM markets m WHERE m.event_internal_id = e.id)
    """
    events = fetch_all(find_query)

    if dry_run:
        return len(events)

    updated = 0
    for event_row in events:
        eid = event_row["event_id"]
        # Fetch child markets
        market_query = """
            SELECT ticker, settlement_value, status
            FROM markets
            WHERE event_internal_id = %s
            ORDER BY ticker
        """
        markets = fetch_all(market_query, (eid,))
        markets_total = len(markets)
        markets_settled = sum(1 for m in markets if m["status"] == "settled")

        outcomes: dict[str, dict[str, str | None]] = {}
        for mkt in markets:
            sv = mkt["settlement_value"]
            outcomes[mkt["ticker"]] = {
                "settlement_value": str(sv) if sv is not None else None,
            }

        result_json = {
            "markets_total": markets_total,
            "markets_settled": markets_settled,
            "outcomes": outcomes,
        }

        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE events SET result = %s, updated_at = NOW() WHERE id = %s",
                (json.dumps(result_json), eid),
            )
            if cur.rowcount and cur.rowcount > 0:
                updated += 1

    return updated


# ---------------------------------------------------------------------------
# 4. Market settlement_value backfill (requires Kalshi API)
# ---------------------------------------------------------------------------


def backfill_market_settlement_values(
    *, dry_run: bool = False, kalshi_env: str | None = None
) -> dict[str, int]:
    """Re-fetch settlement_value for settled markets with NULL settlement_value.

    Groups markets by event_ticker and uses the Kalshi API to re-fetch market
    data for each event.  Falls back to price-based derivation for binary
    markets when the API value is unavailable.

    Args:
        dry_run: If True, only count affected rows without writing.

    Returns:
        Dict with 'updated' and 'still_null' counts.
    """
    # Find settled markets with NULL settlement_value
    find_query = """
        SELECT m.id, m.ticker, m.status, m.metadata,
               e.external_id AS event_ticker
        FROM markets m
        LEFT JOIN events e ON e.id = m.event_internal_id
        WHERE m.status = 'settled'
          AND m.settlement_value IS NULL
    """
    markets = fetch_all(find_query)

    if not markets:
        return {"updated": 0, "still_null": 0}

    if dry_run:
        # Optimistic estimate: assumes all API lookups succeed
        return {"updated": len(markets), "still_null": 0}

    # Lazy-import Kalshi client (only needed for API backfill)
    from precog.api_connectors.kalshi_client import KalshiClient

    # Resolve environment: explicit arg > PRECOG_ENV > default "demo".
    if kalshi_env is None:
        env = os.getenv("PRECOG_ENV", "dev")
        kalshi_env = "prod" if env == "prod" else "demo"
    try:
        client = KalshiClient(environment=kalshi_env)
    except Exception:
        logger.warning("Could not initialize KalshiClient -- skipping API backfill")
        return {"updated": 0, "still_null": len(markets)}

    # Group by event_ticker for batch API calls
    event_groups: dict[str, list[dict[str, Any]]] = {}
    for mkt in markets:
        et = mkt.get("event_ticker") or "UNKNOWN"
        event_groups.setdefault(et, []).append(mkt)

    updated = 0
    still_null = 0

    for event_ticker, group in event_groups.items():
        # Fetch fresh data from Kalshi API
        api_markets: dict[str, Any] = {}
        if event_ticker != "UNKNOWN":
            try:
                api_data = client.get_markets(event_ticker=event_ticker)
                for am in api_data:
                    api_markets[am.get("ticker", "")] = dict(am)
                # Rate limiting: be polite to API
                time.sleep(0.2)
            except Exception:
                logger.warning("Failed to fetch markets for event %s from API", event_ticker)

        for mkt in group:
            ticker = mkt["ticker"]
            sv: Decimal | None = None

            # Try API data first
            api_mkt = api_markets.get(ticker, {})
            if api_mkt:
                sv = api_mkt.get("settlement_value_dollars")
                # Fallback: cents format
                if sv is None:
                    sv_cents = api_mkt.get("settlement_value")
                    if sv_cents is not None:
                        sv = Decimal(str(sv_cents)) / Decimal("100")

            if sv is not None:
                with get_cursor(commit=True) as cur:
                    cur.execute(
                        "UPDATE markets SET settlement_value = %s, updated_at = NOW() WHERE id = %s",
                        (sv, mkt["id"]),
                    )
                updated += 1
            else:
                still_null += 1

    return {"updated": updated, "still_null": still_null}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run enrichment backfill operations."""
    parser = argparse.ArgumentParser(
        description="Backfill enrichment data for events and markets.",
        epilog=(
            "Examples:\n"
            "  python scripts/backfill_enrichment.py --dry-run\n"
            "  python scripts/backfill_enrichment.py --skip-api\n"
            "  python scripts/backfill_enrichment.py\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing to database.",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip market settlement_value backfill (requires Kalshi API).",
    )
    parser.add_argument(
        "--kalshi-env",
        choices=["demo", "prod"],
        default=None,
        help="Override Kalshi API environment (default: auto from PRECOG_ENV).",
    )
    args = parser.parse_args()

    mode_label = "[DRY RUN] " if args.dry_run else ""

    print(f"{mode_label}Backfill enrichment starting...")
    print("=" * 60)

    # Initialize database pool
    initialize_pool()

    # 1. Event times
    print(f"\n{mode_label}1. Backfilling event times from child markets...")
    times_count = backfill_event_times(dry_run=args.dry_run)
    print(f"   {mode_label}{times_count} events {'would be ' if args.dry_run else ''}updated")

    # 2. Event status
    print(f"\n{mode_label}2. Backfilling event status from child market settlement...")
    status_counts = backfill_event_status(dry_run=args.dry_run)
    print(
        f"   {mode_label}{status_counts['final']} events -> 'final', "
        f"{status_counts['live']} events -> 'live'"
    )

    # 3. Market settlement_value (API) — runs BEFORE event results so that
    #    the JSONB assembled in step 4 contains populated settlement_values,
    #    not NULLs.  (Glokta review finding: step ordering matters because
    #    event result is only written once per event — WHERE result IS NULL.)
    if args.skip_api:
        print("\n3. Market settlement_value backfill SKIPPED (--skip-api)")
    else:
        print(f"\n{mode_label}3. Backfilling market settlement_value from Kalshi API...")
        sv_counts = backfill_market_settlement_values(
            dry_run=args.dry_run, kalshi_env=args.kalshi_env
        )
        print(
            f"   {mode_label}{sv_counts['updated']} markets updated, "
            f"{sv_counts['still_null']} still NULL"
        )

    # 4. Event results — must run AFTER market settlement_value backfill
    print(f"\n{mode_label}4. Backfilling event results (JSONB) for final events...")
    results_count = backfill_event_results(dry_run=args.dry_run)
    print(f"   {mode_label}{results_count} events {'would be ' if args.dry_run else ''}updated")

    print("\n" + "=" * 60)
    print(f"{mode_label}Backfill enrichment complete.")


if __name__ == "__main__":
    main()
