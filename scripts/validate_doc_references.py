"""
Document Reference Validation Script
Phase 0.6b Documentation Correction

This script validates that all document references in markdown files
have been updated to use the new standardized filenames.

Checks for:
1. References to old filenames (without V1.0 suffix)
2. References to old locations (/docs/guides/ instead of /docs/supplementary/)
3. Links to renamed files

Usage:
    python scripts/validate_doc_references.py

Returns:
    - Exit code 0 if all references are correct
    - Exit code 1 if any old references are found
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# Set UTF-8 encoding for stdout on Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')


# Old → New filename mappings
RENAMED_FILES = {
    "VERSIONING_GUIDE.md": "VERSIONING_GUIDE_V1.0.md",
    "TRAILING_STOP_GUIDE.md": "TRAILING_STOP_GUIDE_V1.0.md",
    "POSITION_MANAGEMENT_GUIDE.md": "POSITION_MANAGEMENT_GUIDE_V1.0.md",
    "Comprehensive sports win probabilities from three major betting markets.md": "SPORTS_PROBABILITIES_RESEARCH_V1.0.md",
    "ORDER_EXECUTION_ARCHITECTURE_ASSESSMENT_V1_0.md": "ORDER_EXECUTION_ARCHITECTURE_V1.0.md",
    "PHASE_8_ADVANCED_EXECUTION_SPEC.md": "ADVANCED_EXECUTION_SPEC_V1.0.md",
    "PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md": "EVENT_LOOP_ARCHITECTURE_V1.0.md",
    "PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md": "EXIT_EVALUATION_SPEC_V1.0.md",
    "PHASE_5_POSITION_MONITORING_SPEC_V1_0.md": "POSITION_MONITORING_SPEC_V1.0.md",
    "USER_CUSTOMIZATION_STRATEGY_V1_0.md": "USER_CUSTOMIZATION_STRATEGY_V1.0.md",
}

# Old location references to check
OLD_LOCATIONS = [
    "/docs/guides/VERSIONING_GUIDE",
    "/docs/guides/TRAILING_STOP_GUIDE",
    "/docs/guides/POSITION_MANAGEMENT_GUIDE",
]


def find_markdown_files(root_dir: Path) -> List[Path]:
    """Find all markdown files in the project."""
    return list(root_dir.glob("**/*.md"))


def check_file_references(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Check a single markdown file for old references.

    Returns:
        List of (line_number, old_reference, context) tuples
    """
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return issues

    for line_num, line in enumerate(lines, start=1):
        # Check for old filenames
        for old_name, new_name in RENAMED_FILES.items():
            # Only flag if old name appears but new name doesn't
            if old_name in line and new_name not in line:
                # Skip if this is a "RENAMED from" note
                if "RENAMED from" in line or "renamed from" in line:
                    continue

                issues.append((
                    line_num,
                    old_name,
                    line.strip()[:100]  # First 100 chars of context
                ))

        # Check for old location references
        for old_location in OLD_LOCATIONS:
            if old_location in line:
                issues.append((
                    line_num,
                    old_location,
                    line.strip()[:100]
                ))

    return issues


def main():
    """Main validation routine."""
    root_dir = Path(__file__).parent.parent  # Project root
    docs_dir = root_dir / "docs"

    print("=" * 80)
    print("DOCUMENT REFERENCE VALIDATION - Phase 0.6b")
    print("=" * 80)
    print(f"\nScanning directory: {docs_dir}")
    print(f"Checking for references to {len(RENAMED_FILES)} renamed files...\n")

    # Find all markdown files
    markdown_files = find_markdown_files(docs_dir)
    print(f"Found {len(markdown_files)} markdown files to check\n")

    # Check each file
    all_issues = {}
    for md_file in markdown_files:
        issues = check_file_references(md_file)
        if issues:
            all_issues[md_file] = issues

    # Report results
    if not all_issues:
        print("[SUCCESS] All document references are up to date!")
        print("\nNo references to old filenames or locations found.")
        return 0
    else:
        print("[ISSUES FOUND] Old references detected\n")
        print("=" * 80)

        total_issues = 0
        for file_path, issues in all_issues.items():
            print(f"\nFile: {file_path.relative_to(root_dir)}")
            print("-" * 80)
            for line_num, old_ref, context in issues:
                total_issues += 1
                print(f"  Line {line_num}: Reference to '{old_ref}'")
                print(f"    Context: {context}")
            print()

        print("=" * 80)
        print(f"\n[ERROR] Total issues: {total_issues} references in {len(all_issues)} files")
        print("\nAction required: Update these references to use new filenames")
        print("\nRenamed files:")
        for old_name, new_name in RENAMED_FILES.items():
            print(f"  {old_name} → {new_name}")

        return 1


if __name__ == "__main__":
    exit(main())
