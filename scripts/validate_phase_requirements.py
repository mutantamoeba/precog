#!/usr/bin/env python3
"""
Phase Requirement Validation Script.

This script validates that all requirements assigned to a specific phase
have been properly marked as Complete before the phase can be closed.

**WHY THIS EXISTS (Root Cause Analysis):**
    During Phase 1 completion, REQ-SEC-009 (Credential Masking) was discovered
    to still be marked as "Planned" even though Phase 1 was considered "complete".

    This gap occurred because:
    1. Phase Completion Protocol Step 1 didn't programmatically validate requirement statuses
    2. No automated check existed to catch "Phase X requirement still Planned"

    This script closes that gap by providing automated enforcement.

**USAGE:**
    # Check Phase 1 requirements
    python scripts/validate_phase_requirements.py --phase 1

    # Check all requirements (any phase)
    python scripts/validate_phase_requirements.py --all

    # Verbose output (shows each requirement)
    python scripts/validate_phase_requirements.py --phase 1 --verbose

**INTEGRATION:**
    Add to Phase Completion Protocol Step 1:
    ```bash
    python scripts/validate_phase_requirements.py --phase N
    ```

    Add to pre-push hooks for phase completion commits:
    ```bash
    if git log --oneline -1 | grep -q "Phase .* complete"; then
        python scripts/validate_phase_requirements.py --all
    fi
    ```

Related Issue: Phase 1 Completion Gap (REQ-SEC-009 still Planned)
Related Requirement: REQ-VALIDATION-011 (Phase Completion Protocol Automation)
Related Document: docs/utility/PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md
"""

import argparse
import re
import sys
from pathlib import Path


def parse_requirement_index(file_path: Path) -> list[dict]:
    """
    Parse REQUIREMENT_INDEX.md and extract all requirements.

    Returns:
        List of dicts with keys: id, title, phase, priority, status, document

    Educational Note:
        We parse markdown tables using regex patterns:
        | ID | Title | Phase | Priority | Status | Document |
        |----|----|-------|----------|--------|----------|
        | REQ-SEC-009 | Sensitive Data Masking | 1 | High | Planned | ... |

        Status values: Complete (checkmark), Planned (blue circle), In Progress (yellow circle)
    """
    requirements = []

    content = file_path.read_text(encoding="utf-8")

    # Pattern to match requirement table rows
    # | REQ-XXX-NNN | Title | Phase | Priority | Status | Document |
    table_row_pattern = re.compile(
        r"\|\s*(REQ-[A-Z]+-\d+)\s*\|"  # REQ ID
        r"\s*([^|]+)\s*\|"  # Title
        r"\s*([^|]+)\s*\|"  # Phase
        r"\s*([^|]+)\s*\|"  # Priority
        r"\s*([^|]+)\s*\|"  # Status
        r"\s*([^|]+)\s*\|",  # Document
        re.MULTILINE,
    )

    for match in table_row_pattern.finditer(content):
        req_id, title, phase, priority, status, document = match.groups()

        requirements.append(
            {
                "id": req_id.strip(),
                "title": title.strip(),
                "phase": phase.strip(),
                "priority": priority.strip(),
                "status": status.strip(),
                "document": document.strip(),
            }
        )

    return requirements


def normalize_phase(phase_str: str) -> list[str]:
    """
    Normalize phase string to list of phase numbers.

    Examples:
        "1" -> ["1"]
        "1-2" -> ["1", "2"]
        "0.6c" -> ["0.6c"]
        "1.5+" -> ["1.5", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        "4-5" -> ["4", "5"]

    Educational Note:
        Phase notation can be complex:
        - Single: "1", "0.6c", "1.5"
        - Range: "1-2", "4-5", "6-9"
        - Open-ended: "1.5+", "2+"
    """
    phase_str = phase_str.strip()

    # Handle "X+" notation (open-ended)
    if phase_str.endswith("+"):
        base = phase_str[:-1]
        # Include phases from base to 10
        try:
            base_num = float(base)
            return [
                str(i) if i == int(i) else f"{i:.1f}"
                for i in [base_num] + list(range(int(base_num) + 1, 11))
            ]
        except ValueError:
            return [base]

    # Handle "X-Y" notation (range)
    if "-" in phase_str and not phase_str.startswith("0."):
        parts = phase_str.split("-")
        if len(parts) == 2:
            try:
                start = int(parts[0])
                end = int(parts[1])
                return [str(i) for i in range(start, end + 1)]
            except ValueError:
                pass

    # Single phase
    return [phase_str]


def filter_requirements_by_phase(requirements: list[dict], target_phase: str) -> list[dict]:
    """
    Filter requirements that apply to a specific phase.

    Args:
        requirements: List of requirement dicts
        target_phase: Phase to filter for (e.g., "1", "1.5", "0.7")

    Returns:
        List of requirements that apply to the target phase
    """
    filtered = []

    for req in requirements:
        phases = normalize_phase(req["phase"])
        if target_phase in phases or any(p.startswith(target_phase) for p in phases):
            filtered.append(req)

    return filtered


def is_status_complete(status: str) -> bool:
    """
    Check if status indicates completion.

    Educational Note:
        Status emojis in REQUIREMENT_INDEX:
        - Complete: checkmark emoji (various encodings)
        - Planned: blue_circle emoji
        - In Progress: yellow_circle emoji, star emoji
    """
    # Check for completion indicators (including emoji)
    complete_indicators = ["Complete", "complete", "COMPLETE", "Done", "done", "DONE", "\u2705"]
    incomplete_indicators = [
        "Planned",
        "planned",
        "PLANNED",
        "Draft",
        "draft",
        "DRAFT",
        "\U0001f535",
    ]

    for indicator in complete_indicators:
        if indicator in status:
            return True

    for indicator in incomplete_indicators:
        if indicator in status:
            return False

    # Default: assume incomplete if not explicitly complete
    return False


def sanitize_for_console(text: str) -> str:
    """
    Remove emojis and non-ASCII characters for Windows console compatibility.

    Educational Note:
        Windows cp1252 encoding doesn't support Unicode emojis.
        This function strips them to prevent UnicodeEncodeError.
    """
    # Remove common status emojis
    replacements = {
        "\u2705": "[OK]",  # checkmark
        "\u274c": "[X]",  # red X
        "\U0001f535": "[P]",  # blue circle (planned)
        "\U0001f7e1": "[IP]",  # yellow circle (in progress)
        "\u2b50": "[*]",  # star
    }
    for emoji, replacement in replacements.items():
        text = text.replace(emoji, replacement)

    # Strip any remaining non-ASCII characters
    return text.encode("ascii", "replace").decode("ascii")


def validate_phase_requirements(
    requirements: list[dict], target_phase: str, verbose: bool = False
) -> tuple[bool, list[dict], list[dict]]:
    """
    Validate all requirements for a phase are complete.

    Args:
        requirements: All requirements from REQUIREMENT_INDEX
        target_phase: Phase to validate
        verbose: Print detailed output

    Returns:
        Tuple of (all_complete, incomplete_reqs, complete_reqs)
    """
    phase_reqs = filter_requirements_by_phase(requirements, target_phase)

    incomplete = []
    complete = []

    for req in phase_reqs:
        if is_status_complete(req["status"]):
            complete.append(req)
            if verbose:
                title = sanitize_for_console(req["title"])
                print(f"  [PASS] {req['id']}: {title}")
        else:
            incomplete.append(req)
            if verbose:
                title = sanitize_for_console(req["title"])
                status = sanitize_for_console(req["status"])
                print(f"  [FAIL] {req['id']}: {title} (Status: {status})")

    all_complete = len(incomplete) == 0
    return all_complete, incomplete, complete


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate phase requirements are complete before phase closure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_phase_requirements.py --phase 1
  python scripts/validate_phase_requirements.py --phase 1.5 --verbose
  python scripts/validate_phase_requirements.py --all
        """,
    )
    parser.add_argument("--phase", "-p", help="Phase number to validate (e.g., 1, 1.5, 0.7c)")
    parser.add_argument(
        "--all", "-a", action="store_true", help="Show all requirements with their status"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output for each requirement"
    )

    args = parser.parse_args()

    if not args.phase and not args.all:
        parser.error("Either --phase or --all must be specified")

    # Find REQUIREMENT_INDEX file
    repo_root = Path(__file__).parent.parent
    req_index_files = list(repo_root.glob("docs/foundation/REQUIREMENT_INDEX_V*.md"))

    if not req_index_files:
        print("[ERROR] REQUIREMENT_INDEX file not found in docs/foundation/")
        sys.exit(1)

    # Use latest version
    req_index_file = sorted(req_index_files)[-1]
    print(f"Using: {req_index_file.name}")

    # Parse requirements
    requirements = parse_requirement_index(req_index_file)
    print(f"Found {len(requirements)} requirements\n")

    if args.all:
        # Show all requirements grouped by status
        complete = [r for r in requirements if is_status_complete(r["status"])]
        incomplete = [r for r in requirements if not is_status_complete(r["status"])]

        print(f"=== COMPLETE ({len(complete)}) ===")
        for req in complete:
            title = sanitize_for_console(req["title"])
            phase = sanitize_for_console(req["phase"])
            print(f"  {req['id']}: {title} (Phase {phase})")

        print(f"\n=== INCOMPLETE ({len(incomplete)}) ===")
        for req in incomplete:
            title = sanitize_for_console(req["title"])
            phase = sanitize_for_console(req["phase"])
            status = sanitize_for_console(req["status"])
            print(f"  {req['id']}: {title} (Phase {phase}) - {status}")

        print("\n=== SUMMARY ===")
        print(f"Complete: {len(complete)}")
        print(f"Incomplete: {len(incomplete)}")
        print(f"Total: {len(requirements)}")

        sys.exit(0)

    # Validate specific phase
    print(f"=== VALIDATING PHASE {args.phase} REQUIREMENTS ===\n")

    all_complete, incomplete, complete = validate_phase_requirements(
        requirements, args.phase, args.verbose
    )

    print(f"\n=== PHASE {args.phase} SUMMARY ===")
    print(f"Complete: {len(complete)}")
    print(f"Incomplete: {len(incomplete)}")

    if all_complete:
        print(f"\n[SUCCESS] All Phase {args.phase} requirements are complete!")
        sys.exit(0)
    else:
        print(f"\n[FAILURE] Phase {args.phase} has {len(incomplete)} incomplete requirements:")
        for req in incomplete:
            title = sanitize_for_console(req["title"])
            status = sanitize_for_console(req["status"])
            print(f"  - {req['id']}: {title} (Status: {status})")
        print(
            f"\nPhase {args.phase} CANNOT be marked complete until all requirements are implemented."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
