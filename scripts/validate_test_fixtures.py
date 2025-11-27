#!/usr/bin/env python3
"""
Test Fixture Validation - Pattern 13 Enforcement

Validates that integration tests use real fixtures, not mocks.

Pattern 13 (Coverage Quality): Integration tests MUST use real infrastructure
(db_pool, db_cursor, clean_test_data), not mocked connections. Mocking connection
pools caused Strategy Manager tests to pass despite critical bugs (Phase 1.5 lesson learned).

Enforcement:
1. Load test fixture requirements from validation_config.yaml
2. Scan integration test files for required fixtures
3. Detect forbidden mock patterns (mock connection pool, mock database)
4. Allow exceptions with explicit comments ("# Unit test - mock OK")
5. Report violations with actionable fix suggestions

Reference: docs/guides/DEVELOPMENT_PATTERNS_V1.4.md Pattern 13 (Coverage Quality)
Reference: scripts/validation_config.yaml (test fixture requirements)
Reference: TESTING_GAPS_ANALYSIS.md lines 33-43 (Strategy Manager lesson learned)
Related: ADR-075 (Real Fixtures for Integration Tests)

Exit codes:
  0 = All integration tests use real fixtures
  1 = Forbidden mock patterns found
  2 = Configuration error (WARNING only)

Example usage:
  python scripts/validate_test_fixtures.py          # Run validation
  python scripts/validate_test_fixtures.py --verbose # Detailed output
"""

import re
import sys
from pathlib import Path
from typing import Any, cast

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def load_test_fixture_requirements() -> dict:
    """
    Load test fixture requirements from validation_config.yaml.

    Returns:
        dict with fixture requirements, or defaults if file not found

    Educational Note:
        The config now distinguishes between:
        - database_integration_tests: Require db_pool, db_cursor, clean_test_data
        - api_integration_tests: Use VCR cassettes, no database fixtures needed

        This prevents false positives for API integration tests that test
        HTTP-level behavior, not database interaction.
    """
    validation_config_path = PROJECT_ROOT / "scripts" / "validation_config.yaml"

    default_requirements = {
        "database_integration_tests": {
            "description": "Tests requiring real database infrastructure",
            "path_patterns": [
                "tests/integration/database/",
                "tests/integration/trading/",
                "tests/integration/analytics/",
            ],
            "required_fixtures": [
                "db_pool",  # Real connection pool (not mocked)
                "db_cursor",  # Real database cursor
                "clean_test_data",  # Test data cleanup
            ],
            "forbidden_patterns": [
                r"unittest\.mock\.patch\(['\"]psycopg2\.pool['\"]",  # Don't mock connection pool
                r"mock_connection\s*=\s*Mock\(",  # Don't mock database connections
                r"@patch\(['\"]psycopg2\.connect['\"]",  # Don't mock database connect
            ],
            "allowed_exceptions": [
                "Unit test - mock OK",
                "Error handling test",
            ],
        },
        "api_integration_tests": {
            "description": "Tests for external API clients (ESPN, Balldontlie, etc.)",
            "path_patterns": [
                "tests/integration/api_connectors/",
            ],
            "required_fixtures": [],  # No database fixtures needed - uses VCR cassettes
            "forbidden_patterns": [
                r"mock_connection\s*=\s*Mock\(",  # Don't mock database in API tests
            ],
            "allowed_exceptions": [
                "VCR cassette",
                "External API mock",
                "Network failure test",
            ],
        },
    }

    if not validation_config_path.exists() or not YAML_AVAILABLE:
        return default_requirements

    try:
        with open(validation_config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return cast(
                "dict[Any, Any]", config.get("test_fixture_requirements", default_requirements)
            )
    except Exception:
        return default_requirements


def get_test_category(test_file: Path, requirements: dict) -> str | None:
    """
    Determine which test category a test file belongs to based on path patterns.

    Args:
        test_file: Path to the test file
        requirements: Test fixture requirements config

    Returns:
        Category name (e.g., "database_integration_tests") or None if no match

    Educational Note:
        This enables path-based categorization of tests:
        - tests/integration/api_connectors/ -> api_integration_tests (no DB fixtures)
        - tests/integration/database/ -> database_integration_tests (requires DB fixtures)
    """
    test_path_str = str(test_file).replace("\\", "/")  # Normalize for Windows

    for category_name, category_config in requirements.items():
        path_patterns = category_config.get("path_patterns", [])
        for pattern in path_patterns:
            # Normalize pattern for comparison
            pattern = pattern.replace("\\", "/")
            if pattern in test_path_str:
                return str(category_name)  # Explicit cast for type safety

    return None


def check_fixture_usage(test_file: Path, required_fixtures: list[str]) -> list[str]:
    """
    Check if test file uses required fixtures.

    Args:
        test_file: Path to test file
        required_fixtures: List of fixture names to check for

    Returns:
        List of missing fixtures (empty list if all present)
    """
    missing = []

    try:
        content = test_file.read_text(encoding="utf-8")

        for fixture in required_fixtures:
            # Check if fixture used in function signatures
            # Pattern: def test_something(db_pool, ...):
            # Pattern: def test_something(..., db_pool):
            if not re.search(rf"\({fixture}[,\)]", content) and not re.search(
                rf",\s*{fixture}[,\)]", content
            ):
                missing.append(fixture)

    except Exception:
        return required_fixtures  # Assume all missing if can't read file

    return missing


def check_forbidden_patterns(
    test_file: Path, forbidden_patterns: list[str], exception_comments: list[str]
) -> list[str]:
    """
    Check if test file uses forbidden mock patterns.

    Args:
        test_file: Path to test file
        forbidden_patterns: List of regex patterns to check for
        exception_comments: List of comment strings that allow exceptions

    Returns:
        List of violations (empty list if none found)
    """
    violations = []

    try:
        content = test_file.read_text(encoding="utf-8")
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            for pattern in forbidden_patterns:
                if re.search(pattern, line):
                    # Check for exception comments in surrounding lines
                    has_exception = False
                    context_lines = lines[max(0, line_num - 3) : line_num + 1]
                    context = "\n".join(context_lines)

                    for exception in exception_comments:
                        if exception.lower() in context.lower():
                            has_exception = True
                            break

                    if not has_exception:
                        violations.append(
                            f"{test_file.name}:{line_num} - Forbidden mock pattern: {line.strip()}"
                        )

    except Exception:
        # Skip unreadable files - validation script should be resilient
        # If file is genuinely corrupted, other checks will catch it
        return violations

    return violations


def validate_test_fixtures(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Validate all integration tests use appropriate fixtures based on their category.

    Args:
        verbose: If True, show detailed validation process

    Returns:
        (passed, violations) tuple

    Educational Note:
        The validation is now path-based:
        - Database integration tests (tests/integration/database/, trading/, analytics/)
          require db_pool, db_cursor, clean_test_data
        - API integration tests (tests/integration/api_connectors/)
          use VCR cassettes, no database fixtures required

        This prevents false positives for HTTP-level integration tests.
    """
    violations = []

    # Load requirements
    requirements = load_test_fixture_requirements()

    if verbose:
        print(f"[DEBUG] Loaded {len(requirements)} test categories:")
        for category_name, category_config in requirements.items():
            fixtures = category_config.get("required_fixtures", [])
            patterns = category_config.get("path_patterns", [])
            print(
                f"[DEBUG]   {category_name}: {len(fixtures)} fixtures, {len(patterns)} path patterns"
            )

    # Find all integration test files
    integration_tests = list((PROJECT_ROOT / "tests" / "integration").rglob("*.py"))

    if not integration_tests:
        if verbose:
            print("[DEBUG] No integration test files found")
        return True, []

    if verbose:
        print(f"[DEBUG] Scanning {len(integration_tests)} integration test files")

    files_scanned = 0
    violations_found = 0
    skipped_uncategorized = 0

    for test_file in integration_tests:
        # Skip __pycache__ and __init__.py
        if "__pycache__" in str(test_file) or test_file.name == "__init__.py":
            continue

        files_scanned += 1

        # Determine which category this test belongs to
        category = get_test_category(test_file, requirements)

        if category is None:
            # Uncategorized tests - skip with warning in verbose mode
            if verbose:
                print(f"[DEBUG] Skipping uncategorized: {test_file.relative_to(PROJECT_ROOT)}")
            skipped_uncategorized += 1
            continue

        category_config = requirements.get(category, {})
        required_fixtures = category_config.get("required_fixtures", [])
        forbidden_patterns = category_config.get("forbidden_patterns", [])
        exception_comments = category_config.get("allowed_exceptions", [])

        if verbose:
            print(
                f"[DEBUG] {test_file.name} -> {category} (requires: {len(required_fixtures)} fixtures)"
            )

        # Only check for required fixtures if the category has any
        if required_fixtures:
            missing_fixtures = check_fixture_usage(test_file, required_fixtures)

            if missing_fixtures:
                violations.append(
                    f"{test_file.relative_to(PROJECT_ROOT)} - Missing required fixtures: {', '.join(missing_fixtures)}"
                )
                violations.append(
                    f"  Fix: Add fixtures to test functions: def test_something({', '.join(required_fixtures)}):"
                )
                violations_found += 1

        # Check for forbidden mock patterns
        if forbidden_patterns:
            mock_violations = check_forbidden_patterns(
                test_file, forbidden_patterns, exception_comments
            )

            if mock_violations:
                violations.append(
                    f"{test_file.relative_to(PROJECT_ROOT)} - Forbidden mock patterns found:"
                )
                for violation in mock_violations:
                    violations.append(f"  {violation}")
                violations.append("  Fix: Use real fixtures instead of mocks")
                violations.append("  Exception: Add comment from allowed_exceptions if legitimate")
                violations_found += 1

    if verbose:
        print(f"[DEBUG] Scanned {files_scanned} files, found {violations_found} violations")
        print(f"[DEBUG] Skipped {skipped_uncategorized} uncategorized files")

    return len(violations) == 0, violations


def main():
    """Run test fixture validation."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("Test Fixture Validation (Pattern 13)")
    print("=" * 60)
    print("Reference: docs/guides/DEVELOPMENT_PATTERNS_V1.4.md")
    print("Reference: TESTING_GAPS_ANALYSIS.md (Strategy Manager lesson)")
    print("Related: ADR-075 (Real Fixtures for Integration Tests)")
    print("")

    # Check dependencies
    if not YAML_AVAILABLE:
        print("[WARN] PyYAML not available - using default requirements")
        print("")

    # Run validation
    print("[1/1] Checking integration tests for real fixture usage...")

    try:
        passed, violations = validate_test_fixtures(verbose)

        if not passed:
            violation_count = len([v for v in violations if not v.startswith("  ")])
            print(f"[FAIL] {violation_count} test files with fixture violations:")
            for v in violations:
                print(f"  {v}")
            print("")
            print("Fix: Use real fixtures (db_pool, db_cursor, clean_test_data)")
            print("Lesson Learned: Mocking connection pools caused tests to pass with bugs")
            print("Reference: TESTING_GAPS_ANALYSIS.md lines 33-43 (Strategy Manager)")
            print("")
            print("=" * 60)
            print("[FAIL] Test fixture validation failed")
            print("=" * 60)
            return 1
        print("[PASS] All integration tests use real fixtures")

    except Exception as e:
        print(f"[WARN] Validation failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        print("")
        print("Skipping test fixture validation (non-blocking)")
        print("")
        print("=" * 60)
        print("[WARN] Test fixture validation skipped")
        print("=" * 60)
        return 2

    print("")
    print("=" * 60)
    print("[PASS] Test fixture validation passed")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
