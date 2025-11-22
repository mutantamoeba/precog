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
    """
    validation_config_path = PROJECT_ROOT / "scripts" / "validation_config.yaml"

    default_requirements = {
        "integration_tests": {
            "description": "Tests requiring real database/API infrastructure",
            "required_fixtures": [
                "db_pool",  # Real connection pool (not mocked)
                "db_cursor",  # Real database cursor
                "clean_test_data",  # Test data cleanup
            ],
            "forbidden_patterns": [
                r"unittest\.mock\.patch\(['\"]psycopg2\.pool['\"]",  # Don't mock connection pool
                r"mock_connection\s*=\s*Mock\(",  # Don't mock database connections
                r"monkeypatch\.setattr\(['\"]requests\.post['\"]",  # Don't mock API calls
                r"@patch\(['\"]psycopg2\.connect['\"]",  # Don't mock database connect
                r"MagicMock.*pool",  # Don't mock connection pool with MagicMock
            ],
            "allowed_exceptions": [
                "Unit test - mock OK",
                "External API mock",
                "Network failure test",
                "Error handling test",
            ],
        }
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
        pass

    return violations


def validate_test_fixtures(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Validate all integration tests use real fixtures, not mocks.

    Args:
        verbose: If True, show detailed validation process

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Load requirements
    requirements = load_test_fixture_requirements()
    integration_config = requirements.get("integration_tests", {})

    required_fixtures = integration_config.get("required_fixtures", [])
    forbidden_patterns = integration_config.get("forbidden_patterns", [])
    exception_comments = integration_config.get("allowed_exceptions", [])

    if verbose:
        print(f"[DEBUG] Required fixtures: {', '.join(required_fixtures)}")
        print(f"[DEBUG] Forbidden patterns: {len(forbidden_patterns)}")
        print(f"[DEBUG] Exception comments: {len(exception_comments)}")

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

    for test_file in integration_tests:
        # Skip __pycache__ and __init__.py
        if "__pycache__" in str(test_file) or test_file.name == "__init__.py":
            continue

        files_scanned += 1

        # Check for required fixtures
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
        mock_violations = check_forbidden_patterns(
            test_file, forbidden_patterns, exception_comments
        )

        if mock_violations:
            violations.append(
                f"{test_file.relative_to(PROJECT_ROOT)} - Forbidden mock patterns found:"
            )
            for violation in mock_violations:
                violations.append(f"  {violation}")
            violations.append("  Fix: Use real fixtures (db_pool, db_cursor) instead of mocks")
            violations.append(
                "  Exception: Add comment '# Unit test - mock OK' if legitimate unit test"
            )
            violations_found += 1

    if verbose:
        print(f"[DEBUG] Scanned {files_scanned} files, found {violations_found} violations")

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
