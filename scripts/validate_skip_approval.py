#!/usr/bin/env python3
"""
Validate Test Skips - Require Explicit Approval for Skipped Tests.

Per user request: "validation checks should not automatically skip tests -
it should require explicit confirmation to either skip tests or use --no-verify"

This script:
1. Runs pytest to collect skip reasons
2. Compares against an approved skip list
3. Fails with details if there are unapproved skips

Usage:
    python scripts/validate_skip_approval.py [--update-approved]

Flags:
    --update-approved: Update the approved skip list with current skips
                       (requires explicit approval - use only when skips are intentional)

Exit codes:
    0: All skips are approved
    1: Unapproved skips found (requires explicit approval)

Related:
- Phase 1.9: Fix skipped tests rather than auto-skip
- TESTING_STRATEGY V3.2: All 8 test types required
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Approved skip list file (relative to repo root)
APPROVED_SKIP_FILE = Path(__file__).parent.parent / "config" / "approved_test_skips.json"


def get_current_skips() -> list[dict[str, str]]:
    """Run pytest to collect current skip reasons.

    Returns:
        List of skip dictionaries with 'test' and 'reason' keys.
    """
    # Run pytest with short summary for skipped tests
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--tb=no",
            "-q",
            "-rs",
            "--no-header",
            "--co",
            "-q",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )

    # Actually run the tests to get skip reasons
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--tb=no", "-q", "-rs"],
        capture_output=True,
        text=True,
        timeout=600,  # 10 minute timeout
        cwd=Path(__file__).parent.parent,
    )

    # Parse skip lines from output
    skips = []
    in_skip_section = False

    for line in result.stdout.split("\n"):
        line = line.strip()

        # Look for skip summary section
        if "short test summary info" in line.lower():
            in_skip_section = True
            continue

        # Parse SKIPPED lines
        if in_skip_section and line.startswith("SKIPPED"):
            # Format: SKIPPED [N] tests/path.py::test_name: reason
            parts = line.split(": ", 1)
            if len(parts) == 2:
                test_path = parts[0].replace("SKIPPED ", "").split("] ", 1)[-1]
                reason = parts[1]
                skips.append({"test": test_path, "reason": reason})

    return skips


def load_approved_skips() -> list[dict[str, str]]:
    """Load the approved skip list.

    Returns:
        List of approved skip dictionaries.
    """
    if not APPROVED_SKIP_FILE.exists():
        return []

    try:
        with open(APPROVED_SKIP_FILE, encoding="utf-8") as f:
            data = json.load(f)
            approved_skips: list[dict[str, str]] = data.get("approved_skips", [])
            return approved_skips
    except (json.JSONDecodeError, KeyError):
        return []


def save_approved_skips(skips: list[dict[str, str]]) -> None:
    """Save the approved skip list.

    Args:
        skips: List of skip dictionaries to approve.
    """
    APPROVED_SKIP_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "description": "Approved test skips - each skip here has been explicitly reviewed and approved",
        "approved_skips": skips,
        "last_updated": __import__("datetime").datetime.now().isoformat(),
    }

    with open(APPROVED_SKIP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated approved skip list: {APPROVED_SKIP_FILE}")


def normalize_skip(skip: dict[str, str]) -> str:
    """Normalize a skip for comparison.

    Args:
        skip: Skip dictionary with 'test' and 'reason' keys.

    Returns:
        Normalized string for comparison.
    """
    # Just compare test path (reasons may vary slightly)
    test_path: str = skip.get("test", "")
    return test_path.strip()


def validate_skips(
    current: list[dict[str, str]], approved: list[dict[str, str]]
) -> tuple[bool, list[dict[str, str]]]:
    """Validate that all current skips are approved.

    Args:
        current: List of current skip dictionaries.
        approved: List of approved skip dictionaries.

    Returns:
        Tuple of (all_approved, unapproved_list).
    """
    approved_tests = {normalize_skip(s) for s in approved}
    unapproved = []

    for skip in current:
        test_path = normalize_skip(skip)
        if test_path and test_path not in approved_tests:
            unapproved.append(skip)

    return len(unapproved) == 0, unapproved


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for unapproved skips).
    """
    parser = argparse.ArgumentParser(description="Validate test skips require explicit approval")
    parser.add_argument(
        "--update-approved",
        action="store_true",
        help="Update approved skip list with current skips (requires confirmation)",
    )
    parser.add_argument(
        "--show-current", action="store_true", help="Show current skips without validation"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Test Skip Validation (Require Explicit Approval)")
    print("=" * 60)
    print()

    # Get current skips
    print("Collecting current test skips...")
    current_skips = get_current_skips()
    print(f"Found {len(current_skips)} skipped tests")
    print()

    if args.show_current:
        print("Current skips:")
        for skip in current_skips:
            print(f"  - {skip['test']}")
            print(f"    Reason: {skip['reason']}")
        return 0

    if args.update_approved:
        print("WARNING: You are about to approve all current skips.")
        print("Only do this if you have reviewed each skip and confirmed it is intentional.")
        print()
        print("Current skips to be approved:")
        for skip in current_skips:
            print(f"  - {skip['test']}: {skip['reason']}")
        print()

        # In non-interactive mode, always require explicit approval
        if not os.isatty(sys.stdin.fileno()):
            print("ERROR: Cannot update approved skips in non-interactive mode.")
            print("Run this command manually with --update-approved to approve skips.")
            return 1

        response = input("Type 'APPROVE' to confirm: ")
        if response.strip().upper() != "APPROVE":
            print("Aborted - skips not approved.")
            return 1

        save_approved_skips(current_skips)
        print("Skip list updated successfully.")
        return 0

    # Load approved skips
    approved_skips = load_approved_skips()
    print(f"Approved skips in list: {len(approved_skips)}")
    print()

    # Validate
    all_approved, unapproved = validate_skips(current_skips, approved_skips)

    if all_approved:
        print("[OK] All skipped tests are approved")
        return 0

    # Report unapproved skips
    print("=" * 60)
    print(f"[FAIL] {len(unapproved)} UNAPPROVED SKIPPED TESTS FOUND")
    print("=" * 60)
    print()
    print("The following tests are skipped but NOT in the approved list:")
    print()
    for skip in unapproved:
        print(f"  - {skip['test']}")
        print(f"    Reason: {skip['reason']}")
        print()

    print("=" * 60)
    print("ACTION REQUIRED:")
    print("=" * 60)
    print()
    print("Option 1 (PREFERRED): Fix the skipped tests")
    print("  - Remove the skip decorator and fix the underlying issue")
    print("  - Implement missing functionality")
    print("  - Add proper platform/environment detection")
    print()
    print("Option 2: Approve the skips explicitly")
    print("  python scripts/validate_skip_approval.py --update-approved")
    print("  (Requires manual confirmation)")
    print()
    print("Option 3: Bypass (NOT RECOMMENDED)")
    print("  git push --no-verify")
    print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
