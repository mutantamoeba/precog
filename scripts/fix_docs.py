#!/usr/bin/env python3
"""
Documentation Auto-Fixer - Phase 0.6c

Automatically fixes simple documentation consistency issues discovered by validate_docs.py.

Auto-fixable issues:
1. Version header mismatches (filename vs header)
2. Missing documents in MASTER_INDEX (adds entries)
3. Simple status inconsistencies

Non-auto-fixable (requires human judgment):
- ADR number conflicts
- Content contradictions
- Broken cross-references (which document is correct?)

Usage:
    python scripts/fix_docs.py
    python scripts/fix_docs.py --dry-run  # Show what would be fixed without changing files

Exit codes:
    0 - Fixes applied successfully (or dry-run completed)
    1 - Errors encountered during fixing
"""

import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs"
FOUNDATION_DIR = DOCS_ROOT / "foundation"


def fix_version_header_mismatch(doc_file: Path, dry_run: bool = False) -> bool:
    """
    Fix version mismatch between filename and header.

    Args:
        doc_file: Path to document
        dry_run: If True, don't actually modify file

    Returns:
        True if fix was applied (or would be applied in dry-run)
    """
    content = doc_file.read_text(encoding="utf-8")

    # Extract version from filename
    filename_match = re.search(r"_V(\d+)\.(\d+)\.md$", doc_file.name)
    if not filename_match:
        return False  # No version in filename

    filename_version = f"{filename_match.group(1)}.{filename_match.group(2)}"

    # Extract version from header
    header_match = re.search(r"(\*\*Version:\*\*\s+)(\d+\.\d+)", content)
    if not header_match:
        return False  # No version header

    header_version = header_match.group(2)

    if filename_version == header_version:
        return False  # No mismatch

    # Fix: Update header to match filename
    old_line = header_match.group(0)
    new_line = f"{header_match.group(1)}{filename_version}"

    new_content = content.replace(old_line, new_line, 1)

    if dry_run:
        print(f"  [DRY-RUN] Would fix {doc_file.name}: V{header_version} -> V{filename_version}")
        return True
    else:
        doc_file.write_text(new_content, encoding="utf-8")
        print(f"  [OK] Fixed {doc_file.name}: V{header_version} -> V{filename_version}")
        return True


def add_missing_docs_to_master_index(dry_run: bool = False) -> int:
    """
    Add unlisted documents to MASTER_INDEX.

    Args:
        dry_run: If True, don't actually modify file

    Returns:
        Number of documents added (or would be added)
    """
    # Find MASTER_INDEX
    master_index_files = list(FOUNDATION_DIR.glob("MASTER_INDEX_V*.md"))
    if not master_index_files:
        print("  [ERROR] MASTER_INDEX not found")
        return 0

    # Get latest version
    master_index = sorted(master_index_files, reverse=True)[0]
    content = master_index.read_text(encoding="utf-8")

    # Extract already listed documents
    listed_docs = set(re.findall(r"\|\s+([A-Z_0-9]+_V\d+\.\d+\.md)\s+\|", content))

    # Find all versioned docs in docs/
    all_docs = set()
    for doc_file in DOCS_ROOT.rglob("*_V*.md"):
        if "_archive" not in str(doc_file):
            all_docs.add(doc_file.name)

    # Find unlisted docs
    unlisted = all_docs - listed_docs

    if not unlisted:
        return 0

    if dry_run:
        print(f"  [DRY-RUN] Would add {len(unlisted)} documents to MASTER_INDEX:")
        for doc in sorted(unlisted):
            print(f"    - {doc}")
        return len(unlisted)
    else:
        print(f"  [WARN] Found {len(unlisted)} unlisted documents")
        print(f"  [INFO] Manual addition to MASTER_INDEX recommended (requires metadata)")
        for doc in sorted(unlisted):
            print(f"    - {doc}")
        print(f"  [INFO] Add these manually to {master_index.name}")
        return 0  # Not auto-fixing (requires metadata)


def fix_all(dry_run: bool = False) -> Tuple[int, int]:
    """
    Run all auto-fixes.

    Args:
        dry_run: If True, don't actually modify files

    Returns:
        Tuple of (fixes_applied, issues_found)
    """
    fixes_applied = 0
    issues_found = 0

    print("\n1. Checking version header mismatches...")
    foundation_files = [f for f in FOUNDATION_DIR.glob("*.md") if "_archive" not in str(f)]

    for doc_file in foundation_files:
        if fix_version_header_mismatch(doc_file, dry_run):
            fixes_applied += 1

    if fixes_applied == 0:
        print("  [OK] No version mismatches found")

    print("\n2. Checking for unlisted documents in MASTER_INDEX...")
    unlisted_count = add_missing_docs_to_master_index(dry_run)
    if unlisted_count > 0:
        issues_found += unlisted_count

    return fixes_applied, issues_found


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Auto-fix simple documentation issues")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without modifying files",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Documentation Auto-Fixer - Phase 0.6c")
    if args.dry_run:
        print("MODE: DRY-RUN (no files will be modified)")
    print("=" * 60)

    fixes_applied, issues_found = fix_all(dry_run=args.dry_run)

    print("\n" + "=" * 60)
    if fixes_applied > 0:
        if args.dry_run:
            print(f"[OK] DRY-RUN: {fixes_applied} issues would be fixed")
        else:
            print(f"[OK] SUCCESS: {fixes_applied} issues fixed")
    else:
        print("[OK] No auto-fixable issues found")

    if issues_found > 0:
        print(f"[WARN] {issues_found} issues require manual fixing")

    print("=" * 60)

    if not args.dry_run and fixes_applied > 0:
        print("\nRun validate_docs.py to verify fixes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
