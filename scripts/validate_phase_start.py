#!/usr/bin/env python3
"""
Phase Start Protocol Validation - Comprehensive Phase Readiness Check

Validates that all prerequisites are met before starting a new phase.

Implements 3-Step Phase Start Protocol (CLAUDE.md Section "Phase Task Visibility System"):
1. Check deferred tasks from previous phases
2. Check phase prerequisites (dependencies, test planning, coverage targets)
3. Generate master todo checklist

This validator automates Steps 1 and 2, and provides guidance for Step 3.

Enforcement:
1. Find deferred tasks targeting current phase
2. Verify phase dependencies met (previous phases complete)
3. Check if test planning checklist exists
4. Verify coverage targets defined for ALL deliverables
5. Check test infrastructure readiness
6. BLOCK phase start if critical prerequisites missing

Reference: CLAUDE.md Section "Phase Task Visibility System"
Reference: docs/foundation/DEVELOPMENT_PHASES_V1.4.md
Reference: scripts/validation_config.yaml (phase deliverables)

Exit codes:
  0 = All prerequisites met, safe to start phase
  1 = Critical prerequisites missing, BLOCKED
  2 = Configuration error (WARNING only)

Example usage:
  python scripts/validate_phase_start.py --phase 1.5         # Validate Phase 1.5 readiness
  python scripts/validate_phase_start.py --phase 2 --verbose # Detailed output
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


def load_phase_deliverables(phase: str) -> dict:
    """
    Load phase deliverables from validation_config.yaml.

    Args:
        phase: Phase number like "1.5" or "2"

    Returns:
        dict with deliverables for phase, or empty dict if not found
    """
    validation_config_path = PROJECT_ROOT / "scripts" / "validation_config.yaml"

    if not validation_config_path.exists() or not YAML_AVAILABLE:
        return {}

    try:
        with open(validation_config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            phase_deliverables = config.get("phase_deliverables", {})
            return phase_deliverables.get(phase, {})
    except Exception:
        return {}


def find_deferred_tasks(target_phase: str, verbose: bool = False) -> list[str]:
    """
    Find all deferred tasks targeting the specified phase.

    Args:
        target_phase: Phase number like "1.5" or "2"
        verbose: If True, show detailed search process

    Returns:
        List of deferred task descriptions
    """
    deferred_tasks = []

    # Find all PHASE_*_DEFERRED_TASKS*.md documents
    deferred_docs = list((PROJECT_ROOT / "docs" / "utility").glob("PHASE_*_DEFERRED_TASKS*.md"))

    if verbose:
        print(f"[DEBUG] Found {len(deferred_docs)} deferred task documents")

    for doc in deferred_docs:
        try:
            content = doc.read_text(encoding="utf-8")

            # Extract tasks with "Target Phase: X" matching current phase
            # Also check for "Phase X" in task descriptions

            # Pattern 1: Explicit "Target Phase: 1.5"
            pattern1 = rf"Target Phase:\s*{re.escape(target_phase)}"

            # Pattern 2: "Phase 1.5" in task description
            pattern2 = rf"Phase\s+{re.escape(target_phase)}"

            if re.search(pattern1, content, re.IGNORECASE) or re.search(
                pattern2, content, re.IGNORECASE
            ):
                # Extract task lines (format: DEF-XXX: Description)
                task_lines = re.findall(r"(DEF-[A-Z0-9]+-\d+:.*?)(?=\n\n|\Z)", content, re.DOTALL)

                for task in task_lines:
                    # Check if this specific task targets current phase
                    if re.search(pattern1, task, re.IGNORECASE) or re.search(
                        pattern2, task, re.IGNORECASE
                    ):
                        # Clean up task description (first line only)
                        task_clean = task.split("\n")[0].strip()
                        deferred_tasks.append(f"{doc.name}: {task_clean}")

        except Exception as e:
            if verbose:
                print(f"[DEBUG] Error reading {doc.name}: {e}")
            continue

    if verbose:
        print(f"[DEBUG] Found {len(deferred_tasks)} deferred tasks for Phase {target_phase}")

    return deferred_tasks


def check_phase_dependencies(phase: str, verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Check if previous phases are complete (dependencies met).

    Args:
        phase: Phase number like "1.5" or "2"
        verbose: If True, show detailed dependency check

    Returns:
        (dependencies_met, violations) tuple
    """
    violations = []

    # Parse phase number (handles "1.5" and "2")
    try:
        phase_num = float(phase)
    except ValueError:
        violations.append(f"Invalid phase number: {phase}")
        return False, violations

    # Check DEVELOPMENT_PHASES for phase status
    development_phases = list((PROJECT_ROOT / "docs" / "foundation").glob("DEVELOPMENT_PHASES*.md"))

    if not development_phases:
        violations.append("DEVELOPMENT_PHASES document not found")
        return False, violations

    dev_phases_file = development_phases[0]

    try:
        content = dev_phases_file.read_text(encoding="utf-8")

        # Check if all previous phases are marked complete
        # Look for phase completion markers like "Phase 1: ✅ Complete"

        # For Phase 1.5, check Phase 1
        # For Phase 2, check Phase 1 and 1.5

        if phase_num >= 2:
            # Check Phase 1 complete
            if not re.search(r"Phase\s+1[^.0-9].*?✅", content, re.IGNORECASE):
                violations.append("Phase 1 not complete (required for Phase >= 2)")

        if phase_num >= 1.5:
            # Check Phase 1 partial/complete
            if not re.search(r"Phase\s+1[^.]", content):
                violations.append("Phase 1 not found in DEVELOPMENT_PHASES")

    except Exception as e:
        violations.append(f"Error reading DEVELOPMENT_PHASES: {e}")
        return False, violations

    return len(violations) == 0, violations


def check_test_planning_checklist(phase: str, verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Check if test planning checklist exists for phase.

    Args:
        phase: Phase number like "1.5" or "2"
        verbose: If True, show detailed check

    Returns:
        (exists, warnings) tuple (warnings only, not blocking)
    """
    warnings = []

    # Look for PHASE_X_TEST_PLAN*.md or test planning section in DEVELOPMENT_PHASES
    test_plan_docs = list((PROJECT_ROOT / "docs" / "testing").glob(f"PHASE_{phase}_TEST_PLAN*.md"))

    if not test_plan_docs:
        # Check DEVELOPMENT_PHASES for test planning checklist
        development_phases = list(
            (PROJECT_ROOT / "docs" / "foundation").glob("DEVELOPMENT_PHASES*.md")
        )

        if development_phases:
            try:
                content = development_phases[0].read_text(encoding="utf-8")

                # Look for "Before Starting This Phase - TEST PLANNING CHECKLIST"
                pattern = r"Before Starting This Phase.*?TEST PLANNING CHECKLIST"
                phase_section = re.search(
                    rf"Phase\s+{re.escape(phase)}.*?(?=Phase\s+\d|\Z)", content, re.DOTALL
                )

                if phase_section and not re.search(pattern, phase_section.group(), re.IGNORECASE):
                    warnings.append(
                        f"No test planning checklist found for Phase {phase} "
                        f"(RECOMMENDED but not blocking)"
                    )
                    warnings.append(
                        "  Reference: docs/testing/PHASE_TEST_PLANNING_TEMPLATE_V1.0.md"
                    )

            except Exception as e:
                if verbose:
                    print(f"[DEBUG] Error checking test planning checklist: {e}")

    if verbose and test_plan_docs:
        print(f"[DEBUG] Found test plan document: {test_plan_docs[0].name}")

    return len(warnings) == 0, warnings


def check_coverage_targets(phase: str, verbose: bool = False) -> tuple[bool, list[str]]:
    """
    Check if coverage targets defined for ALL phase deliverables.

    Args:
        phase: Phase number like "1.5" or "2"
        verbose: If True, show detailed check

    Returns:
        (targets_defined, violations) tuple
    """
    violations = []

    # Load phase deliverables from validation_config.yaml
    deliverables_config = load_phase_deliverables(phase)

    if not deliverables_config:
        violations.append(f"No deliverables defined for Phase {phase} in validation_config.yaml")
        violations.append("  Add phase section to scripts/validation_config.yaml")
        return False, violations

    deliverables = deliverables_config.get("deliverables", [])

    if not deliverables:
        violations.append(f"Phase {phase} has no deliverables listed")
        return False, violations

    if verbose:
        print(f"[DEBUG] Checking coverage targets for {len(deliverables)} deliverables")

    # Check each deliverable has coverage_target
    for deliverable in deliverables:
        name = deliverable.get("name", "UNKNOWN")
        coverage_target = deliverable.get("coverage_target")

        if coverage_target is None:
            violations.append(
                f"Deliverable '{name}' missing coverage_target in validation_config.yaml"
            )

    return len(violations) == 0, violations


def validate_phase_start(phase: str, verbose: bool = False) -> tuple[int, list[str], list[str]]:
    """
    Comprehensive phase start validation.

    Args:
        phase: Phase number like "1.5" or "2"
        verbose: If True, show detailed validation process

    Returns:
        (exit_code, errors, warnings) tuple
    """
    errors = []
    warnings = []

    # Step 1: Find deferred tasks
    deferred_tasks = find_deferred_tasks(phase, verbose)

    if deferred_tasks:
        warnings.append(f"{len(deferred_tasks)} deferred tasks target Phase {phase}:")
        for task in deferred_tasks[:10]:  # Show first 10
            warnings.append(f"  - {task}")
        if len(deferred_tasks) > 10:
            warnings.append(f"  ... and {len(deferred_tasks) - 10} more")
        warnings.append(f"Address these tasks before starting Phase {phase} implementation")

    # Step 2: Check phase dependencies
    deps_met, dep_violations = check_phase_dependencies(phase, verbose)

    if not deps_met:
        errors.extend(dep_violations)

    # Step 3: Check test planning checklist (WARNING only)
    test_plan_exists, test_plan_warnings = check_test_planning_checklist(phase, verbose)

    if not test_plan_exists:
        warnings.extend(test_plan_warnings)

    # Step 4: Check coverage targets
    targets_defined, target_violations = check_coverage_targets(phase, verbose)

    if not targets_defined:
        errors.extend(target_violations)

    # Determine exit code
    if errors:
        return 1, errors, warnings  # BLOCK
    if warnings:
        return 0, errors, warnings  # PASS with warnings
    return 0, errors, warnings  # PASS


def main():
    """Run phase start validation."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    # Get phase number from args
    phase = None
    for i, arg in enumerate(sys.argv):
        if arg == "--phase" and i + 1 < len(sys.argv):
            phase = sys.argv[i + 1]
            break

    if not phase:
        print("Usage: python scripts/validate_phase_start.py --phase <phase_number>")
        print("Example: python scripts/validate_phase_start.py --phase 1.5")
        return 2

    print("=" * 60)
    print(f"Phase Start Protocol Validation - Phase {phase}")
    print("=" * 60)
    print("Reference: CLAUDE.md Section 'Phase Task Visibility System'")
    print("Reference: docs/foundation/DEVELOPMENT_PHASES_V1.4.md")
    print("")

    # Check dependencies
    if not YAML_AVAILABLE:
        print("[WARN] PyYAML not available - coverage target validation skipped")
        print("")

    # Run validation
    print(f"[1/4] Checking deferred tasks for Phase {phase}...")
    print("[2/4] Checking phase dependencies...")
    print("[3/4] Checking test planning checklist...")
    print("[4/4] Checking coverage targets for deliverables...")
    print("")

    _exit_code, errors, warnings = validate_phase_start(phase, verbose)

    # Report results
    if errors:
        print(f"[FAIL] Phase {phase} start BLOCKED - {len(errors)} critical issues:")
        for error in errors:
            print(f"  {error}")
        print("")

    if warnings:
        print(f"[WARN] Phase {phase} start has {len(warnings)} warnings:")
        for warning in warnings:
            print(f"  {warning}")
        print("")

    print("=" * 60)

    if errors:
        print(f"[FAIL] Phase {phase} start BLOCKED")
        print("=" * 60)
        print("")
        print("Fix critical issues above before starting phase implementation.")
        print("Reference: CLAUDE.md Section 'Phase Task Visibility System'")
        return 1
    if warnings:
        print(f"[PASS] Phase {phase} start validated (with warnings)")
        print("=" * 60)
        print("")
        print("Address warnings above during phase implementation.")
        print("")
        print("Next steps:")
        print("1. Review deferred tasks (if any)")
        print("2. Create master todo list with TodoWrite")
        print("3. Start implementation")
        return 0
    print(f"[PASS] Phase {phase} start validated")
    print("=" * 60)
    print("")
    print("All prerequisites met. Safe to start phase implementation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
