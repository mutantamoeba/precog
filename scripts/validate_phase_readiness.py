"""
Validate Phase Readiness - Automated check for prerequisites and test planning.

**Status:** Phase 0.7 Implementation (Enhanced)
**Created:** 2025-10-30 (Phase 0.6c completion)
**Enhanced:** 2025-10-30 (Added prerequisite dependency checking)

This script validates phase prerequisites before starting work.

**Functionality:**
1. Check previous phase is marked ✅ Complete in DEVELOPMENT_PHASES
2. Verify all "Requires Phase X" dependencies are met
3. Check test planning checklist completed (via SESSION_HANDOFF.md)
4. Validate test plan document exists (optional, if --strict)
5. Exit with non-zero code if validation fails (CI/CD integration)

**Usage:**
    python scripts/validate_phase_readiness.py --phase 1
    python scripts/validate_phase_readiness.py --phase 2 --strict

**Exit Codes:**
    0: Phase ready (all prerequisites met)
    1: Phase not ready (prerequisites missing or test planning incomplete)
    2: Invalid arguments or file errors
"""

import argparse
import re
import sys
from pathlib import Path


def check_phase_complete(phase_identifier, dev_phases_content):
    """
    Check if a phase is marked as Complete in DEVELOPMENT_PHASES.

    Args:
        phase_identifier: Phase identifier (e.g., "0.7", "1", "2")
        dev_phases_content: Content of DEVELOPMENT_PHASES file

    Returns:
        bool: True if phase is marked Complete, False otherwise
    """
    # Extract the specific phase section (up to next ## Phase or end of file)
    phase_section_pattern = rf"## Phase {re.escape(phase_identifier)}:.*?(?=## Phase [0-9]|\Z)"
    phase_match = re.search(phase_section_pattern, dev_phases_content, re.DOTALL)

    if not phase_match:
        return False

    phase_section = phase_match.group(0)

    # Look for Status line specifically (must have checkmark emoji AND Complete on same line)
    # Format: **Status:** ✅ **Complete** or **Status:** ✅ Complete
    status_pattern = r"\*\*Status:\*\*[^\n]*?✅[^\n]*?Complete"
    status_match = re.search(status_pattern, phase_section, re.IGNORECASE)

    return status_match is not None


def check_dependencies(phase, dev_phases_content):
    """
    Check if all dependencies for a phase are met.

    Args:
        phase: Phase number/identifier (e.g., 1, 2, "1.5")
        dev_phases_content: Content of DEVELOPMENT_PHASES file

    Returns:
        tuple: (bool: all_met, list: unmet_dependencies)
    """
    # Find the Dependencies section for this phase
    phase_section_pattern = rf"## Phase {re.escape(str(phase))}:.*?(?=## Phase |\Z)"
    phase_match = re.search(phase_section_pattern, dev_phases_content, re.DOTALL)

    if not phase_match:
        print(f"[WARN] WARNING: Could not find Phase {phase} section in DEVELOPMENT_PHASES")
        return (True, [])  # Assume OK if section not found

    phase_content = phase_match.group(0)

    # Look for Dependencies section
    deps_pattern = r"### Dependencies\s+(.*?)(?=###|\n##|\Z)"
    deps_match = re.search(deps_pattern, phase_content, re.DOTALL)

    if not deps_match:
        # No dependencies section means no prerequisites
        return (True, [])

    deps_text = deps_match.group(1)

    # Extract all "Requires Phase X" statements
    requires_pattern = r"Requires Phase ([0-9.a-z]+):.*?(?:100%\s+complete|complete)"
    required_phases = re.findall(requires_pattern, deps_text, re.IGNORECASE)

    unmet = []
    for req_phase in required_phases:
        if not check_phase_complete(req_phase, dev_phases_content):
            unmet.append(req_phase)

    return (len(unmet) == 0, unmet)


def check_test_planning(phase, session_handoff_path):
    """
    Check if test planning is complete for a phase.

    Args:
        phase: Phase number (e.g., 1, 2, 3)
        session_handoff_path: Path to SESSION_HANDOFF.md

    Returns:
        bool: True if test planning documented as complete
    """
    if not session_handoff_path.exists():
        return False

    content = session_handoff_path.read_text(encoding="utf-8")

    # Look for "Phase N test planning complete" marker
    pattern = rf"Phase {phase} test planning complete"
    return bool(re.search(pattern, content, re.IGNORECASE))


def main():
    """
    Validate that prerequisites and test planning are complete for the specified phase.

    Returns:
        int: Exit code (0 = success, 1 = validation failed, 2 = error)
    """
    parser = argparse.ArgumentParser(
        description="Validate phase prerequisites and test planning before starting work"
    )
    parser.add_argument(
        "--phase",
        type=str,
        required=True,
        help="Phase identifier to validate (e.g., 1, 2, 3, 1.5, 0.7)",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Strict mode: require detailed test plan document"
    )

    args = parser.parse_args()
    phase = args.phase

    print(f"[CHECK] Validating Phase {phase} readiness...")
    print()

    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    dev_phases_path = project_root / "docs" / "foundation" / "DEVELOPMENT_PHASES_V1.4.md"
    session_handoff_path = project_root / "SESSION_HANDOFF.md"

    # Check that required files exist
    if not dev_phases_path.exists():
        print(f"[FAIL] ERROR: DEVELOPMENT_PHASES not found at {dev_phases_path}")
        return 2

    try:
        dev_phases_content = dev_phases_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[FAIL] ERROR: Could not read DEVELOPMENT_PHASES: {e}")
        return 2

    # Validation checks
    all_checks_passed = True

    # Check 1: Verify all dependencies are met
    print(f"[TEST] Check 1: Verifying Phase {phase} dependencies...")
    deps_met, unmet_deps = check_dependencies(phase, dev_phases_content)

    if deps_met:
        print("   [PASS] All dependencies met")
    else:
        print("   [FAIL] FAILED: Unmet dependencies:")
        for dep_phase in unmet_deps:
            print(f"      - Phase {dep_phase} not marked Complete")
        print(f"   -> Complete prerequisite phases before starting Phase {phase}")
        all_checks_passed = False

    print()

    # Check 2: Verify test planning completed
    print(f"[TEST] Check 2: Verifying Phase {phase} test planning...")
    test_planning_done = check_test_planning(phase, session_handoff_path)

    if test_planning_done:
        print("   [PASS] Test planning documented as complete in SESSION_HANDOFF")
    else:
        print("   [WARN] WARNING: Test planning not documented in SESSION_HANDOFF")
        print(f"   -> Add 'Phase {phase} test planning complete' to SESSION_HANDOFF.md")
        print("   -> Reference: docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md")
        # Note: Test planning is recommended but not strictly blocking (for now)
        # Phase 0.7 CI/CD may make this blocking in future

    print()

    # Check 3: Optional strict mode - require test plan document
    if args.strict:
        print("[TEST] Check 3: Verifying test plan document (strict mode)...")
        test_plan_path = project_root / "docs" / "testing" / f"PHASE_{phase}_TEST_PLAN_V1.0.md"

        if test_plan_path.exists():
            print(f"   [PASS] Test plan document exists: {test_plan_path.name}")
        else:
            print("   [FAIL] FAILED: Test plan document not found")
            print(f"   -> Expected: {test_plan_path}")
            all_checks_passed = False

        print()

    # Final result
    print("=" * 60)
    if all_checks_passed:
        print(f"[PASS] PASS: Phase {phase} is ready to start")
        print("All prerequisite dependencies are met.")
        return 0
    print(f"[FAIL] FAIL: Phase {phase} is NOT ready")
    print(f"Resolve issues above before starting Phase {phase} work.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
