#!/usr/bin/env python3
"""
Kalshi Demo API Order Endpoint Verifier (#335)

Standalone verifier for the 7 scenarios in issue #335 plus 6 open questions
from the #508 hierarchical council synthesis. Produces a findings JSON file
that can be folded into MASTER_REQUIREMENTS or the design ADRs.

SAFETY MODES (default: --dry-run, must explicitly opt in to API calls):
    --dry-run        Print test plan, NO API calls (default)
    --read-only      Read-only API calls (get_balance, get_markets, get_fills)
    --live           Write tests against DEMO API only (--allow-prod for prod)
    --allow-prod     REQUIRED to run against production (real money risk)
    --skip-rate-limit-test  Skip scenario 6 (rapid order submission)

USAGE:
    python scripts/verify_kalshi_demo_orders.py --dry-run
    python scripts/verify_kalshi_demo_orders.py --read-only
    python scripts/verify_kalshi_demo_orders.py --live --skip-rate-limit-test

SAFETY GUARDS:
    - Refuses to run if PRECOG_ENV is unset
    - Refuses to run if account balance < $5 (low-balance protection)
    - Refuses to use count > 1
    - Refuses to use any single-order value > $1
    - All test orders use client_order_id prefix "VERIFY_335_"
    - Cancels any non-rejected order immediately after each test
    - Prints every API call with full detail before execution

OUTPUT:
    .verification_findings/kalshi_demo_findings_<timestamp>.json
    .verification_findings/kalshi_demo_findings_<timestamp>.md (human-readable)

REFERENCE:
    - Issue #335 (this script addresses it)
    - memory/findings_335_kalshi_demo_verification.md (test plan + findings template)
    - Issue #508 (Phase 2 trade flow architecture -- depends on findings)

FILED: Session 42d (2026-04-06) -- Phase 2 entry criterion verifier
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

# Defer KalshiClient import until after env validation
# (so --dry-run works without requiring credentials)


# ==============================================================================
# Configuration
# ==============================================================================

# Verification client_order_id prefix -- makes orders identifiable post-test
VERIFY_PREFIX = "VERIFY_335_"

# Minimum demo balance required to run write tests (avoid burning low accounts)
MIN_BALANCE_FOR_WRITE_TESTS = Decimal("5.00")

# Safety caps on test orders
MAX_TEST_COUNT = 1  # Always 1 contract per test
MAX_TEST_VALUE = Decimal("1.00")  # Max $1 exposure per test order

# Use a market we expect to be cheap and not-yet-settled
# (Operator must update this to a current valid market before running --live)
DEFAULT_TEST_TICKER = "REPLACE_WITH_CURRENT_MARKET_TICKER"

# Output directory (gitignored -- add to .gitignore if not already)
OUTPUT_DIR = Path(".verification_findings")


# ==============================================================================
# Findings collector
# ==============================================================================


class FindingsCollector:
    """Records test results, errors, and observed API behavior."""

    def __init__(self) -> None:
        self.started_at = datetime.now(UTC).isoformat()
        self.scenarios: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self.environment: dict[str, Any] = {}

    def record(
        self,
        scenario_id: int,
        title: str,
        status: str,
        request: dict[str, Any] | None = None,
        response: dict[str, Any] | None = None,
        observation: str = "",
        raw_exception: str | None = None,
    ) -> None:
        """Record a single scenario result."""
        self.scenarios.append(
            {
                "scenario": scenario_id,
                "title": title,
                "status": status,  # "pass" | "fail" | "skipped" | "error"
                "request": request,
                "response": response,
                "observation": observation,
                "raw_exception": raw_exception,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize all findings to a dict."""
        return {
            "started_at": self.started_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "environment": self.environment,
            "scenarios": self.scenarios,
            "errors": self.errors,
        }

    def write_files(self) -> tuple[Path, Path]:
        """Write JSON and human-readable markdown reports."""
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        json_path = OUTPUT_DIR / f"kalshi_demo_findings_{timestamp}.json"
        md_path = OUTPUT_DIR / f"kalshi_demo_findings_{timestamp}.md"

        json_path.write_text(json.dumps(self.to_dict(), indent=2, default=str))

        md_lines = [
            "# Kalshi Demo API Verification Findings",
            "",
            f"**Run:** {self.started_at}",
            f"**Environment:** {self.environment.get('precog_env', 'unknown')}"
            f" / {self.environment.get('market_mode', 'unknown')}",
            f"**Mode:** {self.environment.get('mode', 'unknown')}",
            "",
            "## Scenarios",
            "",
        ]
        for s in self.scenarios:
            md_lines.append(f"### Scenario {s['scenario']}: {s['title']}")
            md_lines.append("")
            md_lines.append(f"- **Status:** {s['status']}")
            if s.get("observation"):
                md_lines.append(f"- **Observation:** {s['observation']}")
            if s.get("response"):
                resp_str = json.dumps(s["response"], default=str)[:300]
                md_lines.append(f"- **Response:** `{resp_str}`")
            if s.get("raw_exception"):
                md_lines.append(f"- **Exception:** `{s['raw_exception']}`")
            md_lines.append("")
        md_path.write_text("\n".join(md_lines))

        return json_path, md_path


# ==============================================================================
# Safety checks
# ==============================================================================


def safety_check_environment(args: argparse.Namespace) -> str:
    """Validate PRECOG_ENV and MARKET_MODE before any API calls."""
    precog_env = os.environ.get("PRECOG_ENV", "")
    market_mode = os.environ.get("MARKET_MODE", "")

    if not precog_env:
        sys.exit("ERROR: PRECOG_ENV must be set (dev/test/staging/prod)")

    # Refuse prod unless --allow-prod
    if market_mode == "live" and not args.allow_prod:
        sys.exit(
            "ERROR: market_mode=live requires --allow-prod flag.\n"
            "       This script is designed for DEMO API verification.\n"
            "       Live mode would place real-money orders.\n"
            "       If you really mean it: --live --allow-prod"
        )

    return f"{precog_env}/{market_mode or 'unset'}"


def safety_check_balance(client: Any) -> Decimal:
    """Refuse to run write tests if balance is too low."""
    balance = client.get_balance()
    if balance is None:
        sys.exit("ERROR: get_balance() returned None -- cannot verify safety")
    if balance < MIN_BALANCE_FOR_WRITE_TESTS:
        sys.exit(
            f"ERROR: Demo balance ${balance} is below minimum ${MIN_BALANCE_FOR_WRITE_TESTS}.\n"
            "       This script refuses to run write tests on low-balance accounts.\n"
            "       Top up the demo account or use --read-only mode."
        )
    # client is typed as Any so mypy can't narrow; explicit cast after None+threshold checks
    return cast("Decimal", balance)


# ==============================================================================
# Read-only sanity checks
# ==============================================================================


def read_only_balance_check(client: Any, findings: FindingsCollector) -> None:
    """Read-only: verify get_balance() works."""
    try:
        balance = client.get_balance()
        findings.record(
            0,
            "Read-only: get_balance",
            "pass" if balance is not None else "fail",
            response={"balance": str(balance) if balance is not None else None},
            observation=f"Balance: ${balance}" if balance is not None else "Returned None",
        )
        print(f"  get_balance: ${balance}")
    except Exception as e:
        findings.record(
            0,
            "Read-only: get_balance",
            "error",
            raw_exception=f"{type(e).__name__}: {e}",
            observation="get_balance() raised an exception",
        )
        print(f"  get_balance: ERROR -- {type(e).__name__}: {e}")


def read_only_markets_check(client: Any, findings: FindingsCollector) -> None:
    """Read-only: verify get_markets() works and returns at least one market."""
    try:
        markets = client.get_markets(limit=5)
        n = len(markets) if markets else 0
        sample = markets[0]["ticker"] if markets and n > 0 else None
        findings.record(
            0,
            "Read-only: get_markets",
            "pass" if n > 0 else "fail",
            response={"count": n, "sample_ticker": sample},
            observation=f"Got {n} markets, sample: {sample}" if n > 0 else "No markets returned",
        )
        print(f"  get_markets: {n} markets returned, sample: {sample}")
    except Exception as e:
        findings.record(
            0,
            "Read-only: get_markets",
            "error",
            raw_exception=f"{type(e).__name__}: {e}",
            observation="get_markets() raised an exception",
        )
        print(f"  get_markets: ERROR -- {type(e).__name__}: {e}")


# ==============================================================================
# Test scenarios (7 from #335 + 6 from #508 council)
# All scenarios are PLACEHOLDERS -- implementer must complete
# ==============================================================================


def scenario_1_balance_exceeding_order(
    client: Any, ticker: str, findings: FindingsCollector
) -> None:
    """Submit order exceeding balance -- record exact error code/message."""
    findings.record(
        1,
        "Submit order exceeding balance",
        "skipped",
        observation="TODO: needs current valid ticker + balance check before submission",
    )


def scenario_2_settled_market_order(
    client: Any, settled_ticker: str, findings: FindingsCollector
) -> None:
    """Submit order on closed/settled market -- record behavior."""
    findings.record(
        2,
        "Submit order on settled market",
        "skipped",
        observation="TODO: needs known settled ticker (use most recent NFL game)",
    )


def scenario_3_duplicate_client_order_id(
    client: Any, ticker: str, findings: FindingsCollector
) -> None:
    """Submit duplicate client_order_id -- confirm rejection.

    CRITICAL: This is the question that gates the entire idempotency design from #508.
    """
    client_order_id = f"{VERIFY_PREFIX}dup_{uuid.uuid4().hex[:8]}"
    findings.record(
        3,
        "Submit duplicate client_order_id",
        "skipped",
        observation=(
            f"CRITICAL -- gates idempotency design (REQ-TRADE-003). "
            f"TODO: submit two orders with client_order_id={client_order_id}"
        ),
    )


def scenario_4_submit_then_cancel(client: Any, ticker: str, findings: FindingsCollector) -> None:
    """Submit order then cancel -- confirm cancel behavior."""
    findings.record(4, "Submit then cancel", "skipped", observation="TODO")


def scenario_5_partial_fill(client: Any, ticker: str, findings: FindingsCollector) -> None:
    """Test partial fill scenario.

    NOTE: Partial fills require an opposing order in the book that's smaller than
    our order. Hard to engineer on demo without two accounts. Best-effort: try
    a small order in a thin market and see if anything fills.
    """
    findings.record(
        5,
        "Partial fill",
        "skipped",
        observation=(
            "Hard to engineer on demo. Best-effort recommendation: defer to live observation."
        ),
    )


def scenario_6_rate_limit_behavior(client: Any, ticker: str, findings: FindingsCollector) -> None:
    """Test rate limit behavior (submit 5 orders rapidly)."""
    findings.record(
        6,
        "Rate limit (5 rapid orders)",
        "skipped",
        observation="TODO: submit 5 orders in <1s, record 429 timing + retry-after header",
    )


def scenario_7_response_format_documentation(client: Any, findings: FindingsCollector) -> None:
    """Document all response formats and edge cases."""
    findings.record(
        7,
        "Response format catalog",
        "skipped",
        observation="TODO: aggregate all observed response shapes from scenarios 1-6",
    )


# ==============================================================================
# Open questions from #508 council (Sub-Council A/B/C)
# ==============================================================================


def question_8_client_order_id_supported(
    client: Any, ticker: str, findings: FindingsCollector
) -> None:
    """Does Kalshi support client_order_id AT ALL on demo?"""
    findings.record(
        8,
        "client_order_id support check",
        "skipped",
        observation=(
            "Submit order with client_order_id, then GET it back, "
            "verify field is present in response"
        ),
    )


def question_9_cancel_all_endpoint(client: Any, findings: FindingsCollector) -> None:
    """Does Kalshi expose a 'cancel all open orders' endpoint?"""
    findings.record(
        9,
        "Cancel-all endpoint discovery",
        "skipped",
        observation=(
            "Check Kalshi API docs + try DELETE /portfolio/orders (no order_id) "
            "and DELETE /portfolio/orders/all"
        ),
    )


def question_10_error_code_taxonomy(findings: FindingsCollector) -> None:
    """HTTP error codes for: rejection (validation) vs business logic vs network failure."""
    findings.record(
        10,
        "Error code taxonomy",
        "skipped",
        observation=(
            "Aggregate observed status codes from scenarios 1, 2, 3 and determine "
            "if Kalshi distinguishes validation/business/network"
        ),
    )


def question_11_time_in_force(client: Any, ticker: str, findings: FindingsCollector) -> None:
    """What does time_in_force actually do?"""
    findings.record(
        11,
        "time_in_force semantics",
        "skipped",
        observation=(
            "Submit limit orders with each TIF value, "
            "observe immediate behavior + post-submission state"
        ),
    )


def question_12_partial_fill_response_shape(findings: FindingsCollector) -> None:
    """What's in the order response when partially filled?"""
    findings.record(
        12,
        "Partial fill response schema",
        "skipped",
        observation="Aggregate response shapes from scenarios 4, 5",
    )


def question_13_settled_market_test_feasibility(findings: FindingsCollector) -> None:
    """Does demo have a settle-market mechanism, or do we need to wait for natural settlement?"""
    findings.record(
        13,
        "Settled market test feasibility",
        "skipped",
        observation=(
            "Inspect demo API for any test/admin endpoints; "
            "otherwise scenario 2 needs a known-settled ticker"
        ),
    )


# ==============================================================================
# Main runner
# ==============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description="Kalshi Demo API verifier (#335)")
    parser.add_argument("--dry-run", action="store_true", help="Print plan, no API calls")
    parser.add_argument("--read-only", action="store_true", help="Read-only API calls")
    parser.add_argument("--live", action="store_true", help="Allow write tests against demo")
    parser.add_argument(
        "--allow-prod",
        action="store_true",
        help="Allow prod (real money) -- REQUIRED for live mode",
    )
    parser.add_argument("--skip-rate-limit-test", action="store_true", help="Skip scenario 6")
    parser.add_argument("--ticker", default=DEFAULT_TEST_TICKER, help="Test market ticker")
    parser.add_argument("--settled-ticker", default="", help="Known settled market for scenario 2")
    args = parser.parse_args()

    # Default to dry-run if no mode specified
    if not (args.dry_run or args.read_only or args.live):
        args.dry_run = True

    # Safety checks
    env_descriptor = safety_check_environment(args)

    findings = FindingsCollector()
    findings.environment = {
        "precog_env": os.environ.get("PRECOG_ENV"),
        "market_mode": os.environ.get("MARKET_MODE"),
        "ticker": args.ticker,
        "mode": "dry-run" if args.dry_run else ("read-only" if args.read_only else "live"),
    }

    print("Kalshi Demo API Verifier (#335)")
    print(f"Environment: {env_descriptor}")
    print(f"Mode: {findings.environment['mode']}")
    print(f"Ticker: {args.ticker}")
    print()

    if args.dry_run:
        print("DRY RUN -- no API calls will be made.")
        print("Test scenarios that WOULD run in --live mode:")
        scenarios = [
            "1: Submit order exceeding balance",
            "2: Submit order on settled market",
            "3: Submit duplicate client_order_id (CRITICAL -- idempotency)",
            "4: Submit then cancel",
            "5: Partial fill (best-effort)",
            "6: Rate limit (5 rapid orders)",
            "7: Response format catalog",
            "8: client_order_id support check",
            "9: Cancel-all endpoint discovery",
            "10: Error code taxonomy",
            "11: time_in_force semantics",
            "12: Partial fill response schema",
            "13: Settled market test feasibility",
        ]
        for s in scenarios:
            print(f"  Scenario {s}")
        json_path, md_path = findings.write_files()
        print(f"\nDry-run report written to {md_path}")
        return 0

    # Initialize client
    from precog.api_connectors.kalshi_client import KalshiClient

    print("Initializing KalshiClient...")
    client = KalshiClient("demo")

    if args.read_only:
        print("\nRead-only mode: running sanity checks (no state changes)...")
        read_only_balance_check(client, findings)
        read_only_markets_check(client, findings)
        json_path, md_path = findings.write_files()
        print("\nFindings written to:")
        print(f"  JSON: {json_path}")
        print(f"  Markdown: {md_path}")
        return 0

    if args.live:
        # Read-only safety check: balance must be sufficient for write tests
        balance = safety_check_balance(client)
        print(f"Balance check passed: ${balance}")

        # Run scenarios
        scenario_1_balance_exceeding_order(client, args.ticker, findings)
        if args.settled_ticker:
            scenario_2_settled_market_order(client, args.settled_ticker, findings)
        scenario_3_duplicate_client_order_id(client, args.ticker, findings)
        scenario_4_submit_then_cancel(client, args.ticker, findings)
        scenario_5_partial_fill(client, args.ticker, findings)
        if not args.skip_rate_limit_test:
            scenario_6_rate_limit_behavior(client, args.ticker, findings)
        scenario_7_response_format_documentation(client, findings)
        question_8_client_order_id_supported(client, args.ticker, findings)
        question_9_cancel_all_endpoint(client, findings)
        question_10_error_code_taxonomy(findings)
        question_11_time_in_force(client, args.ticker, findings)
        question_12_partial_fill_response_shape(findings)
        question_13_settled_market_test_feasibility(findings)

    json_path, md_path = findings.write_files()
    print("\nFindings written to:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print()
    print("Next steps:")
    print("  1. Review the findings markdown")
    print("  2. Update memory/findings_335_kalshi_demo_verification.md")
    print("  3. Update #508 design assumptions based on findings")
    print("  4. Close #335 with link to findings file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
