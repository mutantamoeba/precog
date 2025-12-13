#!/usr/bin/env python3
"""
Test Type Coverage Audit Script

Audits the codebase to verify that all modules have required test types
per TESTING_STRATEGY_V3.1.md:

The 8 Test Types:
1. Unit Tests        - Isolated function logic (tests/unit/)
2. Property Tests    - Mathematical invariants (tests/property/)
3. Integration Tests - REAL infrastructure (tests/integration/)
4. End-to-End Tests  - Complete workflows (tests/e2e/)
5. Stress Tests      - Infrastructure limits (tests/stress/)
6. Race Tests        - Concurrent operation validation (tests/stress/ with @pytest.mark.race)
7. Performance Tests - Latency/throughput benchmarks (tests/performance/)
8. Chaos Tests       - Failure recovery scenarios (tests/stress/ with @pytest.mark.chaos)

Usage:
    python scripts/audit_test_type_coverage.py           # Full audit
    python scripts/audit_test_type_coverage.py --summary # Summary only
    python scripts/audit_test_type_coverage.py --json    # JSON output for CI

Exit Codes:
    0 - All required test types present
    1 - Missing required test types (blocks PR)

Reference: TESTING_STRATEGY_V3.1.md Section "The 8 Test Types"
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# =============================================================================
# Configuration
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "precog"
TESTS_DIR = PROJECT_ROOT / "tests"

# The 8 test types and their locations
# Note: Some test types can exist in multiple directories (e.g., chaos in both stress/ and chaos/)
TEST_TYPES = {
    "unit": {"dirs": ["unit"], "markers": ["unit"]},
    "property": {"dirs": ["property"], "markers": ["property"]},
    "integration": {"dirs": ["integration"], "markers": ["integration"]},
    "e2e": {"dirs": ["e2e"], "markers": ["e2e"]},
    "stress": {"dirs": ["stress"], "markers": ["stress"]},
    "race": {"dirs": ["stress", "race"], "markers": ["race"]},
    "performance": {"dirs": ["performance"], "markers": ["performance"]},
    "chaos": {"dirs": ["stress", "chaos"], "markers": ["chaos"]},
}

# Module tiers determine REQUIRED test types
# Critical Path (90%+ coverage) needs ALL 8 types
# Business Logic (85%+) needs 6 types (skip performance, chaos)
# Infrastructure (80%+) needs 4 types (unit, integration, stress, race)
#
# Issue #217: Added missing modules (2025-12-13)
# - Fixed analytics/ -> trading/ path errors
# - Added service_supervisor, service_runner, kelly_criterion (critical)
# - Added espn_game_poller, seeding_manager, espn_validation (business)
# - Added base_poller, rate_limiter, environment, initialization, lookup_helpers (infra)
MODULE_TIERS = {
    # Critical Path (90%+) - ALL 8 test types required
    # API & Authentication
    "api_connectors/kalshi_client": "critical",
    "api_connectors/kalshi_auth": "critical",
    # Schedulers & Service Management
    "schedulers/market_data_manager": "critical",
    "schedulers/kalshi_poller": "critical",
    "schedulers/kalshi_websocket": "critical",
    "schedulers/service_supervisor": "critical",
    "runners/service_runner": "critical",
    # Trading Logic
    "trading/kelly_criterion": "critical",
    # Business Logic (85%+) - 6 types required
    # Analytics & Strategy
    "analytics/model_manager": "business",
    "trading/strategy_manager": "business",
    "trading/position_manager": "business",
    # Data Operations
    "database/crud_operations": "business",
    "database/seeding/seeding_manager": "business",
    # Schedulers
    "schedulers/espn_game_poller": "business",
    # Validation
    "validation/espn_validation": "business",
    # Infrastructure (80%+) - 4 types required
    # API Clients
    "api_connectors/espn_client": "infrastructure",
    "api_connectors/rate_limiter": "infrastructure",
    # Configuration
    "config/config_loader": "infrastructure",
    "config/environment": "infrastructure",
    # Database
    "database/connection": "infrastructure",
    "database/initialization": "infrastructure",
    "database/lookup_helpers": "infrastructure",
    # Schedulers Base
    "schedulers/base_poller": "infrastructure",
    # Utilities
    "utils/logger": "infrastructure",
}

# Required test types per tier
# V3.2 UPDATE: ALL 8 test types required for ALL tiers
# Rationale: Cost of fixing bugs increases exponentially per phase
ALL_8_TYPES = ["unit", "property", "integration", "e2e", "stress", "race", "performance", "chaos"]

TIER_REQUIREMENTS = {
    "critical": ALL_8_TYPES,
    "business": ALL_8_TYPES,
    "infrastructure": ALL_8_TYPES,
}


# =============================================================================
# Discovery Functions
# =============================================================================


def discover_modules() -> list[str]:
    """Discover all Python modules in src/precog/."""
    modules = []
    for py_file in SRC_DIR.rglob("*.py"):
        if py_file.name.startswith("_"):
            continue
        relative = py_file.relative_to(SRC_DIR)
        module_path = str(relative.with_suffix("")).replace(os.sep, "/")
        modules.append(module_path)
    return sorted(modules)


def discover_tests_for_module(module_path: str) -> dict[str, list[str]]:
    """
    Discover all tests for a given module across test type directories.

    Returns dict mapping test_type -> list of test files

    Search strategy:
    1. Type-specific directories (tests/unit/, tests/property/, etc.)
    2. Root tests/ directory (legacy location, treated as unit tests)
    3. Alternate naming patterns (e.g., test_database_crud_* for crud_operations)
    """
    module_name = Path(module_path).stem
    parent_dir = Path(module_path).parent

    tests_found: dict[str, list[str]] = defaultdict(list)

    # Build search patterns for this module
    # E.g., "crud_operations" -> ["crud_operations", "crud", "operations", "database_crud"]
    search_patterns = [module_name]
    if "_" in module_name:
        # Also search for parts
        parts = module_name.split("_")
        if len(parts) >= 2:
            search_patterns.append(parts[0])  # e.g., "crud" from "crud_operations"
            search_patterns.append(parts[-1])  # e.g., "operations" from "crud_operations"
    # Add parent directory as prefix pattern (e.g., "database_crud" for database/crud_operations)
    parent_name = str(parent_dir).replace("/", "_").replace("\\", "_")
    if parent_name:
        search_patterns.append(f"{parent_name}_{module_name}")

    for test_type, config in TEST_TYPES.items():
        for test_dir in config["dirs"]:
            test_path = TESTS_DIR / test_dir

            if not test_path.exists():
                continue

            # Search for test files matching any pattern
            for pattern in search_patterns:
                for test_file in test_path.rglob(f"test_*{pattern}*.py"):
                    rel_path = str(test_file.relative_to(TESTS_DIR))
                    if rel_path in tests_found[test_type]:
                        continue  # Already found

                    # Check for markers in the file
                    content = test_file.read_text(errors="ignore")
                    marker_found = False
                    for marker in config["markers"]:
                        if (
                            f"@pytest.mark.{marker}" in content
                            or f"pytest.mark.{marker}" in content
                        ):
                            tests_found[test_type].append(rel_path)
                            marker_found = True
                            break

                    # For test types that share directories (race, chaos in stress/),
                    # ONLY count if explicit marker is found.
                    # For test types with unique directories (unit, property, etc.),
                    # count based on directory if no marker found.
                    if not marker_found:
                        unique_dir_types = {"unit", "property", "integration", "e2e", "performance"}
                        if test_type in unique_dir_types:
                            # These types have dedicated directories, safe to count by location
                            tests_found[test_type].append(rel_path)

    # Also search root tests/ directory (legacy location, treat as unit tests)
    for pattern in search_patterns:
        for test_file in TESTS_DIR.glob(f"test_*{pattern}*.py"):
            if not test_file.is_file():
                continue
            rel_path = str(test_file.relative_to(TESTS_DIR))

            # Check for explicit markers to categorize
            content = test_file.read_text(errors="ignore")
            categorized = False
            for test_type, config in TEST_TYPES.items():
                for marker in config["markers"]:
                    if f"@pytest.mark.{marker}" in content or f"pytest.mark.{marker}" in content:
                        if rel_path not in tests_found[test_type]:
                            tests_found[test_type].append(rel_path)
                        categorized = True
                        break
                if categorized:
                    break

            # If no markers, treat root-level tests as unit tests
            if not categorized and rel_path not in tests_found["unit"]:
                tests_found["unit"].append(rel_path)

    return dict(tests_found)


def check_test_file_for_types(test_file: Path) -> list[str]:
    """Check which test type markers are present in a test file."""
    types_found = []
    try:
        content = test_file.read_text(errors="ignore")
        for test_type, config in TEST_TYPES.items():
            for marker in config["markers"]:
                if f"@pytest.mark.{marker}" in content or f"pytest.mark.{marker}" in content:
                    types_found.append(test_type)
                    break
    except (OSError, UnicodeDecodeError):
        # Skip files that can't be read - return empty list
        return []
    return types_found


def analyze_coverage_gaps(module: str, tests: dict[str, list[str]]) -> dict:
    """
    Analyze test type coverage gaps for a module.

    Returns dict with:
    - tier: Module tier (critical/business/infrastructure)
    - required: List of required test types
    - present: List of test types with tests
    - missing: List of missing test types
    - status: PASS or FAIL
    """
    # Determine tier (default to infrastructure)
    tier = "infrastructure"
    for mod_path, mod_tier in MODULE_TIERS.items():
        if mod_path in module:
            tier = mod_tier
            break

    required = TIER_REQUIREMENTS.get(tier, [])
    # Only count test types that actually have tests (non-empty lists)
    present = [t for t, files in tests.items() if files]
    missing = [t for t in required if t not in present]

    return {
        "module": module,
        "tier": tier,
        "required": required,
        "present": present,
        "missing": missing,
        "status": "PASS" if not missing else "FAIL",
        "tests": tests,
    }


# =============================================================================
# Reporting Functions
# =============================================================================


def print_summary(results: list[dict]) -> tuple[int, int]:
    """Print summary report of test type coverage."""
    passing = sum(1 for r in results if r["status"] == "PASS")
    failing = sum(1 for r in results if r["status"] == "FAIL")

    print("\n" + "=" * 70)
    print("TEST TYPE COVERAGE AUDIT SUMMARY")
    print("=" * 70)
    print(f"\nModules analyzed: {len(results)}")
    print(f"Passing: {passing}")
    print(f"Failing: {failing}")

    if failing > 0:
        print("\n" + "-" * 70)
        print("MODULES WITH MISSING TEST TYPES:")
        print("-" * 70)
        for r in results:
            if r["status"] == "FAIL":
                print(f"\n  {r['module']} (tier: {r['tier']})")
                print(f"    Required: {', '.join(r['required'])}")
                print(f"    Present:  {', '.join(r['present']) or 'None'}")
                print(f"    Missing:  {', '.join(r['missing'])}")

    return passing, failing


def print_full_report(results: list[dict]) -> None:
    """Print full detailed report."""
    print("\n" + "=" * 70)
    print("TEST TYPE COVERAGE AUDIT - FULL REPORT")
    print("=" * 70)

    # Group by tier
    by_tier = defaultdict(list)
    for r in results:
        by_tier[r["tier"]].append(r)

    for tier in ["critical", "business", "infrastructure"]:
        if tier not in by_tier:
            continue

        modules = by_tier[tier]
        print(f"\n{'=' * 70}")
        print(f"TIER: {tier.upper()} ({len(TIER_REQUIREMENTS.get(tier, []))} test types required)")
        print("=" * 70)

        for r in modules:
            status_icon = "[PASS]" if r["status"] == "PASS" else "[FAIL]"
            print(f"\n  {status_icon} {r['module']}")

            # Show test type matrix
            print("    Test Types:")
            for test_type in TEST_TYPES:
                if test_type in r["required"]:
                    status = "[x]" if test_type in r["present"] else "[ ]"
                else:
                    status = "[-]"  # Not required
                tests = r["tests"].get(test_type, [])
                test_count = f"({len(tests)} tests)" if tests else ""
                print(f"      {status} {test_type:12} {test_count}")


def output_json(results: list[dict]) -> None:
    """Output results as JSON for CI integration."""
    output = {
        "summary": {
            "total": len(results),
            "passing": sum(1 for r in results if r["status"] == "PASS"),
            "failing": sum(1 for r in results if r["status"] == "FAIL"),
        },
        "modules": results,
    }
    print(json.dumps(output, indent=2))


# =============================================================================
# Main
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Audit test type coverage")
    parser.add_argument("--summary", action="store_true", help="Summary only")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any modules missing required types",
    )
    args = parser.parse_args()

    # Discover and analyze
    results = []
    for module in discover_modules():
        tests = discover_tests_for_module(module)
        analysis = analyze_coverage_gaps(module, tests)
        results.append(analysis)

    # Filter to only tracked modules (those with tier assignments)
    tracked_results = [
        r
        for r in results
        if r["tier"] != "infrastructure" or any(m in r["module"] for m in MODULE_TIERS)
    ]

    # Output
    if args.json:
        output_json(tracked_results)
    elif args.summary:
        print_summary(tracked_results)
    else:
        print_full_report(tracked_results)
        print_summary(tracked_results)

    # Exit code
    _, failing = (
        print_summary(tracked_results)
        if not args.json
        else (0, sum(1 for r in tracked_results if r["status"] == "FAIL"))
    )

    if args.strict and failing > 0:
        print(f"\n[ERROR] {failing} modules missing required test types!")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
