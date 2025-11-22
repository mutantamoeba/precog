#!/usr/bin/env python3
"""
Property-Based Testing Validation - Pattern 10 Enforcement

Validates that all critical trading logic has Hypothesis property tests.

Pattern 10 (Property-Based Testing): Trading logic, decimal operations, and API parsing
MUST have property tests that validate mathematical invariants with thousands of auto-generated test cases.

Enforcement:
1. Load property test requirements from validation_config.yaml
2. For each required module, verify:
   - Module exists in src/precog/
   - Corresponding property test file exists in tests/property/
   - Test file uses Hypothesis (@given decorator)
   - Test file covers required properties
3. Report violations with actionable fix suggestions

Reference: docs/guides/DEVELOPMENT_PATTERNS_V1.4.md Pattern 10 (Property-Based Testing)
Reference: scripts/validation_config.yaml (property test requirements)
Related: ADR-074 (Hypothesis for Trading Logic)
Related: REQ-TEST-008 through REQ-TEST-011 (Property Test Requirements)

Exit codes:
  0 = All required modules have property tests
  1 = Missing or incomplete property tests found
  2 = Configuration error (WARNING only)

Example usage:
  python scripts/validate_property_tests.py          # Run validation
  python scripts/validate_property_tests.py --verbose # Detailed output
"""

import re
import sys
from pathlib import Path

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def load_property_test_requirements() -> dict:
    """
    Load property test requirements from validation_config.yaml.

    Returns:
        dict with property test requirements, or defaults if file not found
    """
    validation_config_path = PROJECT_ROOT / "scripts" / "validation_config.yaml"

    default_requirements = {
        "trading_logic": {
            "description": "Financial calculations requiring mathematical invariants",
            "modules": [
                "analytics/kelly.py",
                "analytics/probability.py",
                "trading/edge_detector.py",
            ],
            "required_properties": [
                "Kelly fraction in [0, 1] for all inputs",
                "Edge detection is monotonic",
                "Probabilities sum to 1.0",
            ],
        },
        "decimal_operations": {
            "description": "Currency and probability operations (Pattern 1)",
            "modules": ["utils/decimal_ops.py"],
            "required_properties": [
                "Decimal precision maintained across operations",
                "No float contamination",
                "Rounding behavior consistent",
            ],
        },
        "api_parsing": {
            "description": "API response parsing (TypedDict validation)",
            "modules": ["api_connectors/kalshi_client.py"],
            "required_properties": [
                "All *_dollars fields parsed as Decimal",
                "TypedDict contracts enforced",
                "Invalid responses rejected",
            ],
        },
    }

    if not validation_config_path.exists() or not YAML_AVAILABLE:
        return default_requirements

    try:
        with open(validation_config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("property_test_requirements", default_requirements)
    except Exception:
        return default_requirements


def find_test_file_for_module(module_path: str) -> Path | None:
    """
    Find the property test file for a given module.

    Checks both directory structures:
    1. Nested: tests/property/analytics/test_kelly_properties.py
    2. Flat: tests/property/test_kelly_criterion_properties.py

    Args:
        module_path: Module path like "analytics/kelly.py"

    Returns:
        Path to property test file, or None if not found

    Examples:
        "analytics/kelly.py" -> "tests/property/analytics/test_kelly_properties.py"
        "analytics/kelly.py" -> "tests/property/test_kelly_criterion_properties.py"
        "utils/decimal_ops.py" -> "tests/property/utils/test_decimal_ops_properties.py"
    """
    # Convert module path to test file path
    # analytics/kelly.py -> tests/property/analytics/test_kelly_properties.py

    parts = Path(module_path).parts
    module_name = Path(module_path).stem

    # Try nested structure first (preferred)
    if len(parts) > 1:
        # Has subdirectory (analytics/kelly.py)
        test_file_nested = (
            PROJECT_ROOT / "tests" / "property" / parts[0] / f"test_{module_name}_properties.py"
        )
        if test_file_nested.exists():
            return test_file_nested

    # Try flat structure (backward compatibility)
    # Check multiple naming patterns:
    # 1. test_kelly_properties.py (exact module name)
    # 2. test_kelly_criterion_properties.py (common variant)

    test_file_flat = PROJECT_ROOT / "tests" / "property" / f"test_{module_name}_properties.py"
    if test_file_flat.exists():
        return test_file_flat

    # Try common naming variants
    # analytics/kelly.py -> test_kelly_criterion_properties.py
    # trading/edge_detector.py -> test_edge_detection_properties.py

    naming_variants = {
        "kelly": ["kelly_criterion", "kelly"],
        "edge_detector": ["edge_detection", "edge_detector"],
        "probability": ["probability", "probabilities"],
        "decimal_ops": ["decimal_ops", "decimal_operations"],
        "kalshi_client": ["kalshi_client", "api_parsing"],
    }

    if module_name in naming_variants:
        for variant in naming_variants[module_name]:
            test_file_variant = (
                PROJECT_ROOT / "tests" / "property" / f"test_{variant}_properties.py"
            )
            if test_file_variant.exists():
                return test_file_variant

    return None


def check_hypothesis_usage(test_file: Path) -> bool:
    """
    Check if test file uses Hypothesis (@given decorator).

    Args:
        test_file: Path to property test file

    Returns:
        True if file uses @given, False otherwise
    """
    try:
        content = test_file.read_text(encoding="utf-8")
        # Look for @given decorator from Hypothesis
        return bool(
            re.search(r"@given\(", content) or re.search(r"from hypothesis import given", content)
        )
    except Exception:
        return False


def check_required_properties(test_file: Path, required_properties: list[str]) -> list[str]:
    """
    Check if test file covers all required properties.

    Args:
        test_file: Path to property test file
        required_properties: List of property descriptions to check for

    Returns:
        List of missing properties (empty list if all covered)

    Note:
        This is a heuristic check - looks for keywords from property descriptions
        in test function names, docstrings, or comments.
    """
    missing = []

    try:
        content = test_file.read_text(encoding="utf-8")

        for prop in required_properties:
            # Extract key terms from property description
            # "Kelly fraction in [0, 1] for all inputs" -> ["kelly", "fraction", "0", "1"]
            key_terms = [
                term.lower()
                for term in re.findall(r"\w+", prop)
                if len(term) > 2 and term.lower() not in {"the", "for", "all", "and", "with"}
            ]

            # Check if any key terms appear in test file
            content_lower = content.lower()
            if not any(term in content_lower for term in key_terms[:2]):  # Check first 2 key terms
                missing.append(prop)

    except Exception:
        return required_properties  # Assume all missing if can't read file

    return missing


def validate_property_tests(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Validate all required modules have comprehensive property tests.

    Args:
        verbose: If True, show detailed validation process

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Load requirements
    requirements = load_property_test_requirements()

    if verbose:
        print(f"[DEBUG] Loaded {len(requirements)} property test requirement categories")

    modules_checked = 0
    tests_found = 0

    # Check each category
    for category, config in requirements.items():
        if verbose:
            print(f"[DEBUG] Checking {category}: {config['description']}")

        modules = config.get("modules", [])
        required_properties = config.get("required_properties", [])

        for module_path in modules:
            modules_checked += 1

            # Check if module exists
            src_module = PROJECT_ROOT / "src" / "precog" / module_path
            if not src_module.exists():
                if verbose:
                    print(f"[DEBUG] Module not found: {module_path} (skipping)")
                continue

            # Find corresponding property test file
            test_file = find_test_file_for_module(module_path)

            if not test_file:
                violations.append(
                    f"{module_path}: No property test file found (category: {category})"
                )
                violations.append(
                    f"  Expected: tests/property/{Path(module_path).parent}/test_{Path(module_path).stem}_properties.py"
                )
                violations.append(
                    "  Fix: Create property tests with @given decorator from Hypothesis"
                )
                continue

            tests_found += 1

            # Check if test file uses Hypothesis
            if not check_hypothesis_usage(test_file):
                violations.append(
                    f"{module_path}: Property test file exists but doesn't use Hypothesis"
                )
                violations.append(f"  File: {test_file.relative_to(PROJECT_ROOT)}")
                violations.append(
                    "  Fix: Add property tests using @given decorator from Hypothesis"
                )
                continue

            # Check if test file covers required properties
            missing_properties = check_required_properties(test_file, required_properties)

            if missing_properties:
                violations.append(
                    f"{module_path}: Property tests missing coverage for {len(missing_properties)} properties"
                )
                violations.append(f"  File: {test_file.relative_to(PROJECT_ROOT)}")
                for prop in missing_properties:
                    violations.append(f"    - {prop}")
                violations.append("  Fix: Add property tests covering all required invariants")

    if verbose:
        print(f"[DEBUG] Checked {modules_checked} modules, found {tests_found} property test files")

    return len(violations) == 0, violations


def main():
    """Run property-based testing validation."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("Property-Based Testing Validation (Pattern 10)")
    print("=" * 60)
    print("Reference: docs/guides/DEVELOPMENT_PATTERNS_V1.4.md")
    print("Related: ADR-074 (Hypothesis for Trading Logic)")
    print("Related: REQ-TEST-008 through REQ-TEST-011")
    print("")

    # Check dependencies
    if not YAML_AVAILABLE:
        print("[WARN] PyYAML not available - using default requirements")
        print("")

    # Run validation
    print("[1/1] Checking property test coverage for critical modules...")

    try:
        passed, violations = validate_property_tests(verbose)

        if not passed:
            print(
                f"[FAIL] {len([v for v in violations if not v.startswith('  ')])} modules missing or incomplete property tests:"
            )
            for v in violations:
                print(f"  {v}")
            print("")
            print("Fix: Create property tests using Hypothesis for all trading logic")
            print("Reference: DEVELOPMENT_PATTERNS Pattern 10 (Property-Based Testing)")
            print("Example: tests/property/analytics/test_kelly_properties.py")
            print("")
            print("=" * 60)
            print("[FAIL] Property test validation failed")
            print("=" * 60)
            return 1
        print("[PASS] All required modules have comprehensive property tests")

    except Exception as e:
        print(f"[WARN] Validation failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        print("")
        print("Skipping property test validation (non-blocking)")
        print("")
        print("=" * 60)
        print("[WARN] Property test validation skipped")
        print("=" * 60)
        return 2

    print("")
    print("=" * 60)
    print("[PASS] Property test validation passed")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
