#!/usr/bin/env python3
"""
Test Type Coverage Audit Script

Audits the codebase to verify that all modules have required test types
per TESTING_STRATEGY_V3.2.md:

The 8 Test Types:
1. Unit Tests        - Isolated function logic (tests/unit/)
2. Property Tests    - Mathematical invariants (tests/property/)
3. Integration Tests - REAL infrastructure (tests/integration/)
4. End-to-End Tests  - Complete workflows (tests/e2e/)
5. Stress Tests      - Infrastructure limits (tests/stress/)
6. Race Tests        - Concurrent operation validation (tests/race/)
7. Performance Tests - Latency/throughput benchmarks (tests/performance/)
8. Chaos Tests       - Failure recovery scenarios (tests/chaos/)

Usage:
    python scripts/audit_test_type_coverage.py           # Full audit
    python scripts/audit_test_type_coverage.py --summary # Summary only
    python scripts/audit_test_type_coverage.py --json    # JSON output for CI
    python scripts/audit_test_type_coverage.py --check-untracked  # Warn about untracked modules

Exit Codes:
    0 - All required test types present
    1 - Missing required test types (blocks PR)
    2 - Untracked modules found (with --check-untracked --strict)

Reference: TESTING_STRATEGY_V3.2.md Section "The 8 Test Types"

IMPORTANT FIX (2025-12-13):
    Previously, modules not in MODULE_TIERS were silently ignored, causing test
    gaps to go undetected. Now the script warns about untracked modules and can
    optionally fail if any are found (--check-untracked --strict).
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
# Issue #234: Added CLI modules (2025-12-16)
# - Added cli/scheduler (critical), cli/kalshi, cli/espn, cli/db, cli/data (business)
# - Added cli/config, cli/system (infrastructure)
# - Added cli/_future/* modules (experimental - not implemented yet)
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
    "database/seeding/historical_elo_loader": "business",
    # Progress bar utilities (Issue #254) - New utility, tests will be expanded
    "database/seeding/progress": "experimental",
    # Team History (Issue #257) - New unified team relocation tracking
    "database/seeding/team_history": "experimental",
    # Data Sources (Issue #229) - Experimental tier until full test suite built
    # These are new modules; tests will be expanded incrementally
    "database/seeding/historical_games_loader": "experimental",
    "database/seeding/historical_odds_loader": "experimental",
    "database/seeding/sources/base_source": "experimental",
    "database/seeding/sources/fivethirtyeight": "experimental",
    "database/seeding/sources/betting_csv": "experimental",
    "database/seeding/sources/sports/nfl_data_py_adapter": "experimental",
    # Issue #236: NFLDataPySource for stats loading
    "database/seeding/sources/nfl_data_py_source": "experimental",
    # Schedulers
    "schedulers/espn_game_poller": "business",
    # Validation
    "validation/espn_validation": "business",
    "validation/kalshi_validation": "business",
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
    # CLI Modules (Issue #234)
    # Critical - manages service scheduling
    "cli/scheduler": "critical",
    # Business - API and data operations
    "cli/kalshi": "business",
    "cli/espn": "business",
    "cli/db": "business",
    "cli/data": "business",
    # Infrastructure - utility and config
    "cli/config": "infrastructure",
    "cli/system": "infrastructure",
    # Experimental - future features not yet implemented
    "cli/_future/model": "experimental",
    "cli/_future/position": "experimental",
    "cli/_future/strategy": "experimental",
    "cli/_future/trade": "experimental",
}

# Required test types per tier
# V3.2 UPDATE: ALL 8 test types required for ALL tiers
# Rationale: Cost of fixing bugs increases exponentially per phase
ALL_8_TYPES = ["unit", "property", "integration", "e2e", "stress", "race", "performance", "chaos"]

# Experimental tier: for new modules still in development (Issue #229)
# Only requires unit tests - other test types added incrementally
EXPERIMENTAL_TYPES = ["unit"]

TIER_REQUIREMENTS = {
    "critical": ALL_8_TYPES,
    "business": ALL_8_TYPES,
    "infrastructure": ALL_8_TYPES,
    "experimental": EXPERIMENTAL_TYPES,  # New modules in development
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


def discover_testable_modules() -> list[str]:
    """
    Discover all TESTABLE Python modules in src/precog/.

    Excludes:
    - __init__.py files
    - Files starting with underscore
    - types.py files (TypedDict definitions only)
    - Migration files (database/migrations/*, database/alembic/*)
    - Seed data files

    Returns:
        List of module paths that should have test coverage.
    """
    modules = []
    exclude_patterns = [
        "types",  # TypedDict definition files
        "migrations/",  # Database migrations
        "alembic/",  # Alembic migrations
        "seeds/",  # Seed data
    ]

    for py_file in SRC_DIR.rglob("*.py"):
        if py_file.name.startswith("_"):
            continue

        relative = py_file.relative_to(SRC_DIR)
        module_path = str(relative.with_suffix("")).replace(os.sep, "/")

        # Skip excluded patterns
        should_exclude = False
        for pattern in exclude_patterns:
            if pattern in module_path or module_path.endswith("types"):
                should_exclude = True
                break

        if not should_exclude:
            modules.append(module_path)

    return sorted(modules)


def find_untracked_modules() -> list[str]:
    """
    Find modules that exist but are NOT in MODULE_TIERS.

    This is critical for preventing test gaps - any module not in MODULE_TIERS
    will be silently ignored by the audit, potentially missing required tests.

    Returns:
        List of module paths that should be added to MODULE_TIERS.
    """
    testable = set(discover_testable_modules())
    tracked = set(MODULE_TIERS.keys())

    # Find modules that exist but aren't tracked
    untracked = []
    for module in testable:
        # Check if this module or any parent path is tracked
        is_tracked = False
        for tracked_path in tracked:
            if module == tracked_path or module.startswith(tracked_path + "/"):
                is_tracked = True
                break
            # Also check if tracked path matches this module
            if tracked_path in module:
                is_tracked = True
                break

        if not is_tracked:
            untracked.append(module)

    return sorted(untracked)


def discover_tests_for_module(module_path: str) -> dict[str, list[str]]:
    """
    Discover all tests for a given module across test type directories.

    Returns dict mapping test_type -> list of test files

    Search strategy (STRICT matching to avoid false positives):
    1. Exact module name match in test filename (e.g., test_config_loader*.py)
    2. Directory structure match (e.g., tests/unit/config/test_config_loader.py)
    3. Parent-prefixed name (e.g., test_database_crud_operations.py for database/crud_operations)

    Educational Note (Issue #217 fix):
        Previous implementation used loose partial matching (e.g., "manager" would match
        all *_manager modules). This caused false positives where tests for strategy_manager
        would count for position_manager, model_manager, etc.

        The fix uses STRICT matching:
        - Only exact module name matches count
        - No partial word matching (no splitting on underscores)
        - Tests must be in matching directory structure OR have exact module name in filename
    """
    module_name = Path(module_path).stem
    parent_dir = Path(module_path).parent

    tests_found: dict[str, list[str]] = defaultdict(list)

    # STRICT search patterns - only exact matches, no partial word matching
    # E.g., "config_loader" -> ["config_loader"] (NOT ["config", "loader"])
    search_patterns = [module_name]
    # Add parent-prefixed pattern for disambiguation (e.g., "database_crud_operations")
    parent_name = str(parent_dir).replace("/", "_").replace("\\", "_")
    if parent_name and parent_name != ".":
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


def output_json(results: list[dict], untracked: list[str] | None = None) -> None:
    """Output results as JSON for CI integration."""
    output = {
        "summary": {
            "total": len(results),
            "passing": sum(1 for r in results if r["status"] == "PASS"),
            "failing": sum(1 for r in results if r["status"] == "FAIL"),
            "untracked": len(untracked) if untracked else 0,
        },
        "modules": results,
    }
    if untracked:
        output["untracked_modules"] = untracked
    print(json.dumps(output, indent=2))


def print_untracked_modules(untracked: list[str], as_error: bool = True) -> None:
    """Print error/warning about untracked modules.

    Args:
        untracked: List of untracked module paths
        as_error: If True, print as ERROR (blocking). If False, print as WARNING.
    """
    if not untracked:
        print("\n[OK] All testable modules are tracked in MODULE_TIERS")
        return

    severity = "ERROR" if as_error else "WARNING"
    print("\n" + "=" * 70)
    print(f"{severity}: UNTRACKED MODULES FOUND")
    print("=" * 70)
    print(f"\nFound {len(untracked)} module(s) NOT in MODULE_TIERS:")
    if as_error:
        print("BLOCKING: Untracked modules MUST be added to MODULE_TIERS!\n")
    else:
        print("These modules are SILENTLY IGNORED by the audit!\n")

    for module in untracked:
        print(f"  - {module}")

    print("\nTo fix: Add these to MODULE_TIERS in audit_test_type_coverage.py:")
    print("  MODULE_TIERS = {")
    for module in untracked:
        # Suggest appropriate tier based on path
        if "trading" in module or "analytics" in module:
            tier = "business"
        elif "api_connectors" in module or "scheduler" in module:
            tier = "critical"
        else:
            tier = "infrastructure"
        print(f'      "{module}": "{tier}",')
    print("  }")


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
    parser.add_argument(
        "--check-untracked",
        action="store_true",
        help="Check for and warn about modules not in MODULE_TIERS",
    )
    args = parser.parse_args()

    # Check for untracked modules first (critical for preventing silent gaps)
    untracked = find_untracked_modules()

    # Discover and analyze ONLY tracked modules
    results = []
    for module_path in MODULE_TIERS:
        tests = discover_tests_for_module(module_path)
        analysis = analyze_coverage_gaps(module_path, tests)
        results.append(analysis)

    # Output
    if args.json:
        output_json(results, untracked if args.check_untracked else None)
    elif args.summary:
        _passing, failing = print_summary(results)
        if args.check_untracked:
            print_untracked_modules(untracked)
    else:
        print_full_report(results)
        _passing, failing = print_summary(results)
        if args.check_untracked:
            print_untracked_modules(untracked)

    # Calculate exit code
    if args.json:
        failing = sum(1 for r in results if r["status"] == "FAIL")

    exit_code = 0

    # ALWAYS fail on untracked modules (prevent silent test gaps)
    # This is a blocking error, not a warning that gets ignored
    if untracked:
        print(f"\n[ERROR] {len(untracked)} untracked modules found - BLOCKING!")
        print("       Add them to MODULE_TIERS in audit_test_type_coverage.py")
        exit_code = 2

    if args.strict and failing > 0:
        print(f"\n[ERROR] {failing} modules missing required test types!")
        exit_code = 1 if exit_code == 0 else exit_code

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
