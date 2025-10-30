#!/usr/bin/env python3
"""
Documentation Validation Script - Phase 0.6c

Validates document consistency across foundation documents to prevent drift.

Checks:
1. ADR consistency (ARCHITECTURE_DECISIONS ↔ ADR_INDEX)
2. Requirement consistency (MASTER_REQUIREMENTS ↔ REQUIREMENT_INDEX)
3. MASTER_INDEX accuracy (all docs exist, versions match)
4. Cross-references (no broken links)
5. Version headers (consistent versioning)

Usage:
    python scripts/validate_docs.py
    python scripts/validate_docs.py --fix  # Auto-fix simple issues

Exit codes:
    0 - All validation checks passed
    1 - Validation failed (issues found)
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs"
FOUNDATION_DIR = DOCS_ROOT / "foundation"


@dataclass
class ValidationResult:
    """Result of a validation check."""

    name: str
    passed: bool
    errors: List[str]
    warnings: List[str]

    def print_result(self):
        """Print formatted validation result."""
        if self.passed:
            print(f"✅ {self.name}")
            if self.warnings:
                for warning in self.warnings:
                    print(f"   ⚠️  {warning}")
        else:
            print(f"❌ {self.name} FAILED")
            for error in self.errors:
                print(f"   ❌ {error}")


def find_latest_version(pattern: str) -> Path | None:
    """Find latest version of a document matching pattern."""
    matching_files = list(FOUNDATION_DIR.glob(pattern))
    if not matching_files:
        return None

    # Extract version numbers and sort
    versioned = []
    for file in matching_files:
        match = re.search(r"V(\d+)\.(\d+)", file.name)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            versioned.append((major, minor, file))

    if not versioned:
        return matching_files[0]  # Return first if no version found

    # Sort by version (descending)
    versioned.sort(reverse=True)
    return versioned[0][2]


def extract_adr_numbers(content: str) -> Set[str]:
    """Extract all ADR numbers (ADR-001, ADR-002, etc.) from content."""
    return set(re.findall(r"ADR-(\d{3})", content))


def extract_requirement_ids(content: str) -> Set[str]:
    """Extract all requirement IDs (REQ-XXX-NNN) from content."""
    return set(re.findall(r"REQ-[A-Z]+-\d{3}", content))


def validate_adr_consistency() -> ValidationResult:
    """Validate ADR consistency between ARCHITECTURE_DECISIONS and ADR_INDEX."""
    errors = []
    warnings = []

    # Find latest versions
    arch_decisions = find_latest_version("ARCHITECTURE_DECISIONS_V*.md")
    adr_index = find_latest_version("ADR_INDEX_V*.md")

    if not arch_decisions:
        return ValidationResult(
            name="ADR Consistency",
            passed=False,
            errors=["ARCHITECTURE_DECISIONS document not found"],
            warnings=[],
        )

    if not adr_index:
        return ValidationResult(
            name="ADR Consistency",
            passed=False,
            errors=["ADR_INDEX document not found"],
            warnings=[],
        )

    # Read both files
    arch_content = arch_decisions.read_text(encoding="utf-8")
    index_content = adr_index.read_text(encoding="utf-8")

    # Extract ADR numbers
    arch_adrs = extract_adr_numbers(arch_content)
    index_adrs = extract_adr_numbers(index_content)

    # Check for mismatches
    missing_in_index = arch_adrs - index_adrs
    missing_in_arch = index_adrs - arch_adrs

    if missing_in_index:
        errors.append(
            f"{len(missing_in_index)} ADRs in ARCHITECTURE_DECISIONS but not in ADR_INDEX: "
            + ", ".join(sorted([f"ADR-{num}" for num in missing_in_index]))
        )

    if missing_in_arch:
        errors.append(
            f"{len(missing_in_arch)} ADRs in ADR_INDEX but not in ARCHITECTURE_DECISIONS: "
            + ", ".join(sorted([f"ADR-{num}" for num in missing_in_arch]))
        )

    # Check for sequential numbering (should be ADR-001, ADR-002, ADR-003, ...)
    if arch_adrs:
        adr_nums = sorted([int(num) for num in arch_adrs])
        expected_sequence = list(range(1, max(adr_nums) + 1))
        missing_numbers = set(expected_sequence) - set(adr_nums)

        if missing_numbers:
            warnings.append(
                f"Non-sequential ADR numbering - missing: "
                + ", ".join([f"ADR-{num:03d}" for num in sorted(missing_numbers)])
            )

    # Check for duplicate ADR numbers in ARCHITECTURE_DECISIONS
    adr_headings = re.findall(r"###\s+ADR-(\d{3}):", arch_content)
    duplicates = [num for num in adr_headings if adr_headings.count(num) > 1]
    if duplicates:
        unique_duplicates = list(set(duplicates))
        errors.append(
            f"Duplicate ADR numbers in ARCHITECTURE_DECISIONS: "
            + ", ".join([f"ADR-{num}" for num in unique_duplicates])
        )

    passed = len(errors) == 0

    return ValidationResult(
        name=f"ADR Consistency ({len(arch_adrs)} ADRs)", passed=passed, errors=errors, warnings=warnings
    )


def validate_requirement_consistency() -> ValidationResult:
    """Validate requirement consistency between MASTER_REQUIREMENTS and REQUIREMENT_INDEX."""
    errors = []
    warnings = []

    # Find latest versions
    master_reqs = find_latest_version("MASTER_REQUIREMENTS_V*.md")
    req_index = find_latest_version("REQUIREMENT_INDEX*.md")

    if not master_reqs:
        return ValidationResult(
            name="Requirement Consistency",
            passed=False,
            errors=["MASTER_REQUIREMENTS document not found"],
            warnings=[],
        )

    if not req_index:
        warnings.append("REQUIREMENT_INDEX not found (may not exist yet)")
        return ValidationResult(
            name="Requirement Consistency", passed=True, errors=[], warnings=warnings
        )

    # Read both files
    master_content = master_reqs.read_text(encoding="utf-8")
    index_content = req_index.read_text(encoding="utf-8")

    # Extract requirement IDs
    master_req_ids = extract_requirement_ids(master_content)
    index_req_ids = extract_requirement_ids(index_content)

    # Check for mismatches
    missing_in_index = master_req_ids - index_req_ids
    missing_in_master = index_req_ids - master_req_ids

    if missing_in_index:
        errors.append(
            f"{len(missing_in_index)} requirements in MASTER_REQUIREMENTS but not in REQUIREMENT_INDEX: "
            + ", ".join(sorted(missing_in_index))
        )

    if missing_in_master:
        errors.append(
            f"{len(missing_in_master)} requirements in REQUIREMENT_INDEX but not in MASTER_REQUIREMENTS: "
            + ", ".join(sorted(missing_in_master))
        )

    passed = len(errors) == 0

    return ValidationResult(
        name=f"Requirement Consistency ({len(master_req_ids)} requirements)",
        passed=passed,
        errors=errors,
        warnings=warnings,
    )


def validate_master_index() -> ValidationResult:
    """Validate MASTER_INDEX accuracy (all listed docs exist, versions match)."""
    errors = []
    warnings = []

    # Find MASTER_INDEX
    master_index = find_latest_version("MASTER_INDEX_V*.md")

    if not master_index:
        return ValidationResult(
            name="MASTER_INDEX Validation",
            passed=False,
            errors=["MASTER_INDEX document not found"],
            warnings=[],
        )

    content = master_index.read_text(encoding="utf-8")

    # Extract document listings (format: | FILENAME | ✅ | vX.Y | /path/ | ...)
    # Simple regex to find table rows with document names
    doc_pattern = r"\|\s+([A-Z_0-9]+_V\d+\.\d+\.md)\s+\|"
    listed_docs = re.findall(doc_pattern, content)

    if not listed_docs:
        warnings.append("No versioned documents found in MASTER_INDEX (may be formatted differently)")

    # Check each listed document exists
    for doc_name in listed_docs:
        # Search in all subdirectories of docs/
        found = False
        for doc_file in DOCS_ROOT.rglob(doc_name):
            found = True
            break

        if not found:
            errors.append(f"Document listed in MASTER_INDEX but not found: {doc_name}")

    # Check for documents not in MASTER_INDEX
    # Find all versioned markdown files in docs/
    all_docs = set()
    for doc_file in DOCS_ROOT.rglob("*_V*.md"):
        if "_archive" not in str(doc_file):  # Exclude archived docs
            all_docs.add(doc_file.name)

    listed_set = set(listed_docs)
    unlisted = all_docs - listed_set

    if unlisted:
        warnings.append(
            f"{len(unlisted)} documents exist but not in MASTER_INDEX: " + ", ".join(sorted(unlisted))
        )

    passed = len(errors) == 0

    return ValidationResult(
        name=f"MASTER_INDEX Validation ({len(listed_docs)} docs listed)",
        passed=passed,
        errors=errors,
        warnings=warnings,
    )


def validate_cross_references() -> ValidationResult:
    """Validate all .md cross-references point to existing files."""
    errors = []
    warnings = []

    # Check foundation documents for broken references
    foundation_files = list(FOUNDATION_DIR.glob("*.md"))

    broken_refs = []

    for doc_file in foundation_files:
        if "_archive" in str(doc_file):
            continue

        content = doc_file.read_text(encoding="utf-8")

        # Find references to other markdown files
        # Patterns: "docs/path/FILE.md", "supplementary/FILE.md", "foundation/FILE.md"
        ref_patterns = [
            r"docs/([a-z_/]+/[A-Z_0-9]+(?:_V\d+\.\d+)?\.md)",  # Full path
            r"([a-z_]+/[A-Z_0-9]+(?:_V\d+\.\d+)?\.md)",  # Relative path
            r"`([A-Z_0-9]+_V\d+\.\d+\.md)`",  # Inline code reference
        ]

        for pattern in ref_patterns:
            refs = re.findall(pattern, content)
            for ref in refs:
                # Try to find the referenced file
                ref_path = Path(ref)
                found = False

                # Search in docs/ directory
                for candidate in DOCS_ROOT.rglob(ref_path.name):
                    if "_archive" not in str(candidate):
                        found = True
                        break

                if not found:
                    broken_refs.append(f"{doc_file.name} → {ref}")

    if broken_refs:
        errors.append(f"{len(broken_refs)} broken cross-references found:")
        for ref in broken_refs[:10]:  # Limit to first 10
            errors.append(f"  - {ref}")
        if len(broken_refs) > 10:
            errors.append(f"  ... and {len(broken_refs) - 10} more")

    passed = len(errors) == 0

    return ValidationResult(
        name="Cross-Reference Validation", passed=passed, errors=errors, warnings=warnings
    )


def validate_version_headers() -> ValidationResult:
    """Validate all foundation docs have proper version headers."""
    errors = []
    warnings = []

    foundation_files = [f for f in FOUNDATION_DIR.glob("*.md") if "_archive" not in str(f)]

    for doc_file in foundation_files:
        content = doc_file.read_text(encoding="utf-8")

        # Check for version header (Version: X.Y or **Version:** X.Y)
        version_match = re.search(r"\*\*Version:\*\*\s+(\d+\.\d+)", content)
        if not version_match:
            warnings.append(f"{doc_file.name}: No version header found")
            continue

        header_version = version_match.group(1)

        # Check if version in filename matches header
        filename_match = re.search(r"_V(\d+)\.(\d+)\.md$", doc_file.name)
        if filename_match:
            filename_version = f"{filename_match.group(1)}.{filename_match.group(2)}"
            if header_version != filename_version:
                errors.append(
                    f"{doc_file.name}: Version mismatch - "
                    f"filename has V{filename_version}, header has {header_version}"
                )

    passed = len(errors) == 0

    return ValidationResult(
        name=f"Version Header Validation ({len(foundation_files)} docs checked)",
        passed=passed,
        errors=errors,
        warnings=warnings,
    )


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("Documentation Validation Suite - Phase 0.6c")
    print("=" * 60)
    print()

    results = []

    # Run all validation checks
    print("Running validation checks...\n")

    results.append(validate_adr_consistency())
    results.append(validate_requirement_consistency())
    results.append(validate_master_index())
    results.append(validate_cross_references())
    results.append(validate_version_headers())

    # Print results
    print()
    for result in results:
        result.print_result()
        print()

    # Summary
    total_checks = len(results)
    passed_checks = sum(1 for r in results if r.passed)
    failed_checks = total_checks - passed_checks

    print("=" * 60)
    if failed_checks == 0:
        print(f"✅ ALL VALIDATION CHECKS PASSED ({passed_checks}/{total_checks})")
        print("=" * 60)
        return 0
    else:
        print(f"❌ VALIDATION FAILED ({passed_checks}/{total_checks} passed, {failed_checks} failed)")
        print("=" * 60)
        print("\nFix issues above before committing.")
        print("Some issues can be auto-fixed with: python scripts/fix_docs.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
