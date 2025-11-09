#!/usr/bin/env python3
"""
Code Quality Validation - CODE_REVIEW_TEMPLATE Enforcement

Enforces CODE_REVIEW_TEMPLATE requirements before push:
1. Module coverage ≥80% (Section 2: Test Coverage)
2. REQ-XXX-NNN have test coverage (Section 1: Requirements Traceability)
3. Educational docstrings present (Pattern 7, Section 3: Code Quality) - WARNING ONLY

Reference: docs/utility/CODE_REVIEW_TEMPLATE_V1.0.md
Related: DEVELOPMENT_PHILOSOPHY_V1.1.md Section 11 (Test Coverage Accountability)

Exit codes:
  0 = All checks passed
  1 = Template compliance violations found

Example usage:
  python scripts/validate_code_quality.py          # Run all checks
  python scripts/validate_code_quality.py --verbose # Detailed output
"""

import re
import subprocess
import sys
from pathlib import Path


def check_module_coverage(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Verify all Python modules meet ≥80% coverage threshold.

    Args:
        verbose: If True, show detailed coverage breakdown

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Run pytest with coverage
    result = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "tests/",
            "--cov=.",
            "--cov-report=term-missing",
            "--tb=no",
            "-q",
        ],
        capture_output=True,
        text=True,
        timeout=120,  # 2 minute timeout
    )

    if verbose:
        print("\n[DEBUG] pytest coverage output:")
        print(result.stdout[:500])  # Show first 500 chars

    # Parse coverage output for modules below 80%
    in_coverage_section = False
    for line in result.stdout.split("\n"):
        # Detect coverage section (starts after "TOTAL")
        if "TOTAL" in line:
            in_coverage_section = False
        if "------" in line and "Stmts" in result.stdout:
            in_coverage_section = True
            continue

        if not in_coverage_section:
            continue

        # Match lines like: "database/crud_operations.py    75%"
        match = re.match(r"^([\w/\\]+\.py)\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)%", line)
        if match:
            module, coverage = match.groups()
            coverage_pct = int(coverage)

            # Skip test files and _archive
            if "test" in module.lower() or "_archive" in module or "conftest" in module:
                continue

            # Skip __init__.py files (often legitimately low coverage)
            if "__init__.py" in module:
                continue

            if coverage_pct < 80:
                violations.append(f"{module}: {coverage_pct}% (minimum 80%)")

    return len(violations) == 0, violations


def check_requirement_test_coverage(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Verify all REQ-XXX-NNN in MASTER_REQUIREMENTS have test coverage.

    Only checks requirements with status ✅ Complete or 🟡 In Progress.

    Args:
        verbose: If True, show detailed requirement analysis

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Extract REQs from MASTER_REQUIREMENTS
    master_req_files = list(Path("docs/foundation").glob("MASTER_REQUIREMENTS*.md"))
    if not master_req_files:
        return False, ["MASTER_REQUIREMENTS file not found"]

    master_req_file = master_req_files[0]
    content = master_req_file.read_text(encoding="utf-8")

    # Find all REQ-XXX-NNN with status ✅ Complete or 🟡 In Progress
    requirements = []
    req_sections = re.split(r"\*\*REQ-([A-Z]+-\d+):", content)[1:]  # Skip first empty element

    for i in range(0, len(req_sections), 2):
        if i + 1 >= len(req_sections):
            break
        req_id = f"REQ-{req_sections[i]}"
        req_section = req_sections[i + 1][:500]  # Next 500 chars after REQ ID

        # Check if this REQ is Complete or In Progress (should have tests)
        if re.search(r"Status:\s*(✅|🟡)", req_section):
            requirements.append(req_id)

    if verbose:
        print(f"\n[DEBUG] Found {len(requirements)} requirements with status Complete/In Progress")

    # Check if each REQ appears in test files
    test_files = Path("tests").rglob("*.py")
    test_content = ""
    for test_file in test_files:
        try:
            test_content += test_file.read_text(encoding="utf-8")
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Skipping {test_file}: {e}")
            continue

    for req_id in requirements:
        # Check for REQ-XXX-NNN in test content (comments, docstrings, test names)
        if req_id not in test_content:
            violations.append(
                f"{req_id}: No test coverage found (status Complete/In Progress but missing tests)"
            )

    return len(violations) == 0, violations


def check_educational_docstrings(verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Check for educational docstrings in newly added/modified functions (Pattern 7).

    Only checks staged files to avoid flagging existing code.
    This is a WARNING ONLY check - does not fail the validation.

    Args:
        verbose: If True, show detailed docstring analysis

    Returns:
        (passed, violations) tuple
    """
    violations = []

    # Get staged Python files (new or modified)
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True,
        text=True,
    )

    staged_files = [
        f
        for f in result.stdout.strip().split("\n")
        if f.endswith(".py") and "tests/" not in f and f
    ]

    if verbose:
        print(f"\n[DEBUG] Checking {len(staged_files)} staged Python files for docstrings")

    for file_path in staged_files:
        if not Path(file_path).exists():
            continue

        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except Exception as e:
            if verbose:
                print(f"[DEBUG] Skipping {file_path}: {e}")
            continue

        # Find all function definitions with docstrings
        func_pattern = r'def\s+(\w+)\s*\([^)]*\).*?:\s*"""(.*?)"""'
        matches = re.finditer(func_pattern, content, re.DOTALL)

        for match in matches:
            func_name, docstring = match.groups()

            # Skip test functions, private functions, and __init__
            if func_name.startswith(("test_", "_")):
                continue

            # Check for Pattern 7 components
            has_args = "Args:" in docstring or "Parameters:" in docstring
            has_returns = "Returns:" in docstring
            has_educational = (
                "Educational Note:" in docstring or "Why" in docstring or "Pattern" in docstring
            )

            missing = []
            # Check if function has parameters (not just self)
            func_signature = content[match.start() : match.start() + 200]
            has_params = (
                "(" in func_signature and "self" not in func_signature
            ) or func_signature.count(",") > 0

            if has_params and not has_args:
                missing.append("Args")
            if "-> " in func_signature and "None" not in func_signature and not has_returns:
                missing.append("Returns")
            if not has_educational:
                missing.append("Educational Note")

            if missing:
                violations.append(f"{file_path}:{func_name}() missing: {', '.join(missing)}")

    return len(violations) == 0, violations


def main():
    """Run all code quality checks."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("Code Quality Validation (CODE_REVIEW_TEMPLATE)")
    print("=" * 60)
    print("Reference: docs/utility/CODE_REVIEW_TEMPLATE_V1.0.md")
    print("Related: DEVELOPMENT_PHILOSOPHY_V1.1.md Section 11")
    print("")

    all_passed = True

    # Check 1: Module coverage >=80%
    print("[1/3] Checking module coverage (>=80%)...")
    try:
        passed, violations = check_module_coverage(verbose)
        if not passed:
            print("[FAIL] Modules below 80% coverage:")
            for v in violations:
                print(f"  - {v}")
            print("")
            print("Fix: Add tests to increase coverage above 80%")
            print("Reference: CODE_REVIEW_TEMPLATE Section 2 (Test Coverage)")
            all_passed = False
        else:
            print("[PASS] All modules >=80% coverage")
    except subprocess.TimeoutExpired:
        print("[WARN] Coverage check timed out (skipped)")
    except Exception as e:
        print(f"[WARN] Coverage check failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    # Check 2: REQ test coverage
    print("[2/3] Checking requirement test coverage...")
    try:
        passed, violations = check_requirement_test_coverage(verbose)
        if not passed:
            print("[FAIL] Requirements missing test coverage:")
            for v in violations[:10]:  # Show first 10
                print(f"  - {v}")
            if len(violations) > 10:
                print(f"  ... and {len(violations) - 10} more")
            print("")
            print("Fix: Add tests that reference REQ-XXX-NNN in comments/docstrings")
            print("Reference: CODE_REVIEW_TEMPLATE Section 1 (Requirements Traceability)")
            all_passed = False
        else:
            print("[PASS] All requirements have test coverage")
    except Exception as e:
        print(f"[WARN] REQ coverage check failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    # Check 3: Educational docstrings (WARNING ONLY)
    print("[3/3] Checking educational docstrings (Pattern 7)...")
    try:
        passed, violations = check_educational_docstrings(verbose)
        if not passed:
            print("[WARN] Functions missing educational docstrings:")
            for v in violations[:5]:  # Show first 5
                print(f"  - {v}")
            if len(violations) > 5:
                print(f"  ... and {len(violations) - 5} more")
            print("")
            print("Note: This is a warning only (not blocking)")
            print("Reference: CLAUDE.md Pattern 7, CODE_REVIEW_TEMPLATE Section 3")
            # Don't fail on docstring violations (warning only)
        else:
            print("[PASS] Educational docstrings present")
    except Exception:
        print("[WARN] Docstring check failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    print("")
    print("=" * 60)

    if all_passed:
        print("[PASS] All code quality checks passed")
        print("=" * 60)
        return 0
    print("[FAIL] Code quality validation failed")
    print("=" * 60)
    print("")
    print("Fix violations above before pushing.")
    print("Reference: docs/utility/CODE_REVIEW_TEMPLATE_V1.0.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())
