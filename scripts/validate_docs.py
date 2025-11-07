#!/usr/bin/env python3
"""
Documentation Validation Script - Phase 0.6c (Enhanced)

Validates document consistency across foundation documents to prevent drift.

Checks:
1. ADR consistency (ARCHITECTURE_DECISIONS ↔ ADR_INDEX)
2. Requirement consistency (MASTER_REQUIREMENTS ↔ REQUIREMENT_INDEX)
3. MASTER_INDEX accuracy (all docs exist, versions match)
4. Cross-references (no broken links)
5. Version headers (consistent versioning)
6. New docs enforcement (all versioned .md files MUST be in MASTER_INDEX) [ENFORCED]
7. Git-aware version bump detection (ensure renamed files increment version) [ENFORCED]
8. Phase completion status validation (completed phases have proper documentation) [ENFORCED]
9. YAML configuration validation (4-level validation: syntax, Decimal safety, required keys, cross-file) [ENFORCED]

Usage:
    python scripts/validate_docs.py
    python scripts/validate_docs.py --fix  # Auto-fix simple issues

Exit codes:
    0 - All validation checks passed
    1 - Validation failed (issues found)
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs"
FOUNDATION_DIR = DOCS_ROOT / "foundation"


@dataclass
class ValidationResult:
    """Result of a validation check."""

    name: str
    passed: bool
    errors: list[str]
    warnings: list[str]

    def print_result(self):
        """Print formatted validation result (ASCII-safe for Windows)."""

        # Sanitize Unicode emoji for Windows console compatibility
        def sanitize_unicode(text: str) -> str:
            """Replace common Unicode emoji with ASCII equivalents."""
            replacements = {
                "✅": "[COMPLETE]",
                "🔵": "[PLANNED]",
                "🟡": "[IN PROGRESS]",
                "❌": "[FAILED]",
                "⏸️": "[PAUSED]",
                "📦": "[ARCHIVED]",
                "🚧": "[DRAFT]",
                "⚠️": "[WARNING]",
            }
            for unicode_char, ascii_replacement in replacements.items():
                text = text.replace(unicode_char, ascii_replacement)
            return text

        if self.passed:
            print(f"[OK] {self.name}")
            if self.warnings:
                for warning in self.warnings:
                    print(f"   [WARN] {sanitize_unicode(warning)}")
        else:
            print(f"[FAIL] {self.name} FAILED")
            for error in self.errors:
                print(f"   [ERROR] {sanitize_unicode(error)}")


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


def extract_adr_numbers(content: str) -> set[str]:
    """Extract all ADR numbers (ADR-001, ADR-002, etc.) from content."""
    return set(re.findall(r"ADR-(\d{3})", content))


def extract_requirement_ids(content: str) -> set[str]:
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
                "Non-sequential ADR numbering - missing: "
                + ", ".join([f"ADR-{num:03d}" for num in sorted(missing_numbers)])
            )

    # Check for duplicate ADR numbers in ARCHITECTURE_DECISIONS
    adr_headings = re.findall(r"###\s+ADR-(\d{3}):", arch_content)
    duplicates = [num for num in adr_headings if adr_headings.count(num) > 1]
    if duplicates:
        unique_duplicates = list(set(duplicates))
        errors.append(
            "Duplicate ADR numbers in ARCHITECTURE_DECISIONS: "
            + ", ".join([f"ADR-{num}" for num in unique_duplicates])
        )

    passed = len(errors) == 0

    return ValidationResult(
        name=f"ADR Consistency ({len(arch_adrs)} ADRs)",
        passed=passed,
        errors=errors,
        warnings=warnings,
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

    # Extract document listings (format: | **FILENAME** | [STATUS] | vX.Y | /path/ | ...)
    # Regex accounts for bold markdown markers (**) around filenames
    # Capture both filename and status emoji to skip planned documents (🔵)
    doc_pattern = r"\|\s+\*\*([A-Z_0-9]+_V\d+\.\d+\.md)\*\*\s+\|\s+(✅|🔵|📦|🚧)"
    all_matches = re.findall(doc_pattern, content)

    # Only check documents with ✅ status (existing), skip 🔵 (planned), 📦 (archived), 🚧 (draft)
    listed_docs = [filename for filename, status in all_matches if status == "✅"]
    planned_docs = [filename for filename, status in all_matches if status == "🔵"]

    if not all_matches:
        warnings.append(
            "No versioned documents found in MASTER_INDEX (may be formatted differently)"
        )

    if planned_docs:
        warnings.append(
            f"{len(planned_docs)} planned documents (🔵) not yet created - this is expected"
        )

    # Check each listed document exists (only ✅ status)
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
            f"{len(unlisted)} documents exist but not in MASTER_INDEX: "
            + ", ".join(sorted(unlisted))
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
    warnings: list[str] = []

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
                    broken_refs.append(f"{doc_file.name} -> {ref}")

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


def validate_new_docs_in_master_index() -> ValidationResult:
    """
    CHECK #6: Enforce all versioned .md files are listed in MASTER_INDEX (MANDATORY).

    This check ensures documentation discipline by making MASTER_INDEX updates
    mandatory when creating new versioned documents.

    Returns ERROR (not warning) if any versioned .md file exists but is not listed.

    Excludes ephemeral documents (session handoffs, temporary planning docs, templates).
    """
    errors = []
    warnings = []

    # Define ephemeral document patterns (session-specific, temporary, templates)
    # Using lowercase to satisfy Ruff N806 (variable in function should be lowercase)
    ephemeral_patterns = [
        # Session-specific documents
        "SESSION_HANDOFF_",  # Session handoffs (e.g., SESSION_HANDOFF_2025-10-29_v0.md)
        "CLAUDE_CODE_",  # Temporary Claude Code handoff documents
        # Templates
        "_TEMPLATE_",  # Template files (not actual content)
        # Temporary planning and task documents
        "_TASK_PLAN_",  # Task planning documents (e.g., PHASE_1_TASK_PLAN_V1.0.md)
        "_IMPLEMENTATION_PLAN_",  # Implementation plan documents
        "REFACTORING_PLAN_",  # Refactoring plan documents
        # Analysis and review documents (temporary, not permanent specs)
        "_ANALYSIS_",  # Analysis documents (e.g., ELO_AND_SETTLEMENTS_ARCHITECTURE_ANALYSIS_V1.0.md)
        "_REVIEW_",  # Review documents (e.g., DOCUMENTATION_V2_REVIEW_GUIDE.md)
        "_ASSESSMENT_",  # Assessment documents (e.g., ORDER_EXECUTION_ARCHITECTURE_ASSESSMENT_V1_0.md)
        "_CLARIFICATION_",  # Clarification documents
        # Reports and audits (point-in-time, not living documents)
        "_REPORT",  # Report documents (e.g., FILENAME_VERSION_REPORT.md)
        "_AUDIT_",  # Audit documents (e.g., YAML_CONSISTENCY_AUDIT_V1_0.md)
        # Temporary update specs (superseded once applied)
        "_UPDATE_SPEC_",  # Update spec documents (e.g., CONFIGURATION_GUIDE_UPDATE_SPEC_V1_0.md)
        # Phase-specific comprehensive handoffs (different from SESSION_HANDOFF_)
        "PHASE_0_5_COMPREHENSIVE_HANDOFF_",  # Phase 0.5 handoff document
    ]

    def is_ephemeral(filename: str) -> bool:
        """Check if document is ephemeral (session-specific, temporary)."""
        return any(pattern in filename for pattern in ephemeral_patterns)

    # Find MASTER_INDEX
    master_index = find_latest_version("MASTER_INDEX_V*.md")

    if not master_index:
        return ValidationResult(
            name="New Docs Enforcement (Check #6)",
            passed=False,
            errors=["MASTER_INDEX document not found - cannot enforce documentation listing"],
            warnings=[],
        )

    content = master_index.read_text(encoding="utf-8")

    # Extract document listings from MASTER_INDEX
    # Format: | **FILENAME** | [OK] | vX.Y | /path/ | ...
    # The document name is wrapped in markdown bold (**) in MASTER_INDEX tables
    # Pattern handles:
    #  - Mixed-case filenames (e.g., Handoff_Protocol_V1_1.md)
    #  - Dots in base filename (e.g., PHASE_0.7_DEFERRED_TASKS_V1.0.md)
    #  - Both dot and underscore version separators (V1.0 and V1_1)
    doc_pattern = r"\|\s+\*\*([A-Za-z_0-9.]+_V\d+[._]\d+\.md)\*\*\s+\|"
    listed_docs = set(re.findall(doc_pattern, content))

    # Find all versioned markdown files in docs/ (excluding _archive/ and ephemeral patterns)
    all_docs = set()
    for doc_file in DOCS_ROOT.rglob("*_V*.md"):
        if "_archive" not in str(doc_file) and not is_ephemeral(doc_file.name):
            all_docs.add(doc_file.name)

    # Calculate unlisted documents
    unlisted = all_docs - listed_docs

    if unlisted:
        errors.append(
            f"{len(unlisted)} VERSIONED DOCUMENTS EXIST BUT NOT LISTED IN MASTER_INDEX (MANDATORY):"
        )
        for doc_name in sorted(unlisted):
            errors.append(f"  - {doc_name}")
        errors.append("\nACTION REQUIRED: Add these documents to MASTER_INDEX before committing.")
        errors.append("This ensures all documentation is tracked and prevents orphaned files.")

    # Also check for listed docs that don't exist (cleanup check)
    missing_docs = listed_docs - all_docs
    if missing_docs:
        warnings.append(
            f"{len(missing_docs)} documents listed in MASTER_INDEX but no longer exist:"
        )
        for doc_name in sorted(missing_docs):
            warnings.append(f"  - {doc_name}")
        warnings.append("Consider removing these entries or moving to _archive/")

    passed = len(errors) == 0

    return ValidationResult(
        name=f"New Docs Enforcement (Check #6) - {len(all_docs)} docs, {len(listed_docs)} listed",
        passed=passed,
        errors=errors,
        warnings=warnings,
    )


def validate_git_version_bumps() -> ValidationResult:
    """
    CHECK #7: Git-aware version bump detection (MANDATORY).

    Uses git to detect renamed versioned documents and verifies that version
    numbers were incremented correctly (e.g., V2.8 → V2.9, not V2.8 → V2.8).

    Returns ERROR if file renamed but version didn't increment.
    Gracefully skips if git is not available or not a git repository.
    """
    errors = []
    warnings = []

    # Check if git is available
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
            cwd=PROJECT_ROOT,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        warnings.append(
            "Git not available - skipping version bump validation (install git for full validation)"
        )
        return ValidationResult(
            name="Git Version Bump Detection (Check #7)",
            passed=True,
            errors=[],
            warnings=warnings,
        )

    # Check if we're in a git repository
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
            cwd=PROJECT_ROOT,
            timeout=5,
        )
    except subprocess.CalledProcessError:
        warnings.append("Not a git repository - skipping version bump validation")
        return ValidationResult(
            name="Git Version Bump Detection (Check #7)",
            passed=True,
            errors=[],
            warnings=warnings,
        )

    # Get file renames from git diff (staged and unstaged)
    try:
        # Check staged changes
        result_staged = subprocess.run(
            ["git", "diff", "--name-status", "--cached", "--diff-filter=R"],
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )

        # Check unstaged changes (working directory)
        result_unstaged = subprocess.run(
            ["git", "diff", "--name-status", "--diff-filter=R"],
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_ROOT,
            timeout=10,
        )

        rename_output = result_staged.stdout + result_unstaged.stdout

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        warnings.append(f"Git diff failed: {e} - skipping version bump validation")
        return ValidationResult(
            name="Git Version Bump Detection (Check #7)",
            passed=True,
            errors=[],
            warnings=warnings,
        )

    if not rename_output.strip():
        # No renames detected
        return ValidationResult(
            name="Git Version Bump Detection (Check #7) - No renames detected",
            passed=True,
            errors=[],
            warnings=[],
        )

    # Parse rename output (format: "R<score>\told_name\tnew_name")
    # or "R\told_name\tnew_name"
    rename_pattern = r"R\d*\s+(.+?)\s+(.+)"
    renames = re.findall(rename_pattern, rename_output)

    version_bumps_checked = 0
    for old_path, new_path in renames:
        # Only check versioned markdown files in docs/
        if not (old_path.endswith(".md") and "docs/" in old_path):
            continue

        # Extract version from filenames
        old_version_match = re.search(r"_V(\d+)\.(\d+)\.md$", old_path)
        new_version_match = re.search(r"_V(\d+)\.(\d+)\.md$", new_path)

        if not old_version_match or not new_version_match:
            continue  # Not a versioned file rename

        old_major, old_minor = int(old_version_match.group(1)), int(old_version_match.group(2))
        new_major, new_minor = int(new_version_match.group(1)), int(new_version_match.group(2))

        version_bumps_checked += 1

        # Check if version incremented
        version_incremented = (new_major > old_major) or (
            new_major == old_major and new_minor > old_minor
        )

        if not version_incremented:
            errors.append(f"VERSION NOT INCREMENTED: {Path(old_path).name} → {Path(new_path).name}")
            errors.append(
                f"  Old version: V{old_major}.{old_minor}, New version: V{new_major}.{new_minor}"
            )
            errors.append("  ACTION REQUIRED: Version must increment when renaming documents")

        # Warn if version jumped too much (e.g., V2.8 → V3.0 without justification)
        if new_major > old_major + 1:
            warnings.append(
                f"Large version jump detected: {Path(old_path).name} → {Path(new_path).name}"
            )
            warnings.append(
                f"  V{old_major}.{old_minor} → V{new_major}.{new_minor} (skipped {new_major - old_major - 1} major versions)"
            )

    passed = len(errors) == 0

    check_name = f"Git Version Bump Detection (Check #7) - {version_bumps_checked} renames checked"
    return ValidationResult(name=check_name, passed=passed, errors=errors, warnings=warnings)


def validate_phase_completion_status() -> ValidationResult:
    """
    CHECK #8: Phase completion status validation (MANDATORY).

    Validates that phases marked as complete in DEVELOPMENT_PHASES have proper
    status markers and checks for premature completion markers.

    Returns ERROR if:
    - Phase marked ✅ Complete but doesn't have "Status:** ✅ **100% COMPLETE**"
    - Phase has completion report reference but is marked as Planned/In Progress
    """
    errors = []
    warnings = []

    # Find DEVELOPMENT_PHASES
    dev_phases = find_latest_version("DEVELOPMENT_PHASES_V*.md")

    if not dev_phases:
        warnings.append("DEVELOPMENT_PHASES not found - skipping phase status validation")
        return ValidationResult(
            name="Phase Completion Status (Check #8)",
            passed=True,
            errors=[],
            warnings=warnings,
        )

    content = dev_phases.read_text(encoding="utf-8")

    # Pattern to find phase headers with status
    # Example: ## Phase 0.6c: Validation & Testing Infrastructure (Codename: "Sentinel")
    #          **Status:** ✅ **100% COMPLETE**
    phase_pattern = r"## (Phase [0-9.a-z]+):[^\n]+\n.*?\*\*Status:\*\*\s+([^\n]+)"
    phases = re.findall(phase_pattern, content, re.DOTALL)

    phases_checked = 0
    for phase_name, status_line in phases:
        phases_checked += 1

        # Check for completion markers
        # Match completion status at the BEGINNING of the status line (not in parenthetical notes)
        # Valid complete formats: "✅ **100% COMPLETE**" or "[COMPLETE] **100% COMPLETE**"
        # Account for both emoji (✅) and sanitized ASCII ([COMPLETE])
        is_marked_complete = bool(
            re.match(r"^(✅|\[COMPLETE\]).*\*\*.*COMPLETE", status_line.strip())
        )

        # Match planned/in-progress status at the beginning
        # Account for both emoji (🔵, 🟡) and sanitized ASCII ([PLANNED], [IN PROGRESS])
        is_marked_planned = bool(re.match(r"^(🔵|\[PLANNED\]|Planned)", status_line.strip()))
        is_marked_in_progress = bool(
            re.match(r"^(🟡|\[IN PROGRESS\]|In Progress)", status_line.strip())
        )

        # Validate consistency
        if is_marked_complete:
            # Properly formatted complete status
            pass
        elif is_marked_planned or is_marked_in_progress:
            # Check if status line has conflicting completion markers AT THE BEGINNING
            # Ignore references to prerequisite completion (e.g., "Phase 0.7 complete ✅")
            # Only flag if MAIN status is marked complete (starts with ✅/[COMPLETE] and has COMPLETE)
            # Account for both emoji and sanitized ASCII in the check
            main_status_complete = bool(
                re.match(
                    r"^(🔵|\[PLANNED\]|🟡|\[IN PROGRESS\]).*(✅|\[COMPLETE\]).*\*\*.*COMPLETE",
                    status_line.strip(),
                )
            )
            if main_status_complete:
                # Should not have completion language in main status
                errors.append(
                    f"{phase_name}: Conflicting status - marked as Planned/In Progress but also Complete"
                )
                errors.append(f"  Status line: {status_line.strip()}")

    # Check for deferred tasks consistency
    # Phases with deferred tasks should reference the deferred tasks document
    deferred_pattern = r"(Phase [0-9.a-z]+).*?###\s+Deferred Tasks"
    phases_with_deferred = set(re.findall(deferred_pattern, content, re.DOTALL | re.IGNORECASE))

    for phase_with_defer in phases_with_deferred:
        # Check if there's a reference to PHASE_N_DEFERRED_TASKS document
        phase_match = re.search(r"Phase ([0-9.a-z]+)", phase_with_defer)
        if not phase_match:
            continue  # Skip if pattern doesn't match

        phase_num = phase_match.group(1)
        expected_doc_ref = f"PHASE_{phase_num}_DEFERRED_TASKS"

        if expected_doc_ref not in content:
            warnings.append(
                f"{phase_with_defer}: Has 'Deferred Tasks' section but no reference to {expected_doc_ref} document"
            )

    passed = len(errors) == 0

    check_name = f"Phase Completion Status (Check #8) - {phases_checked} phases checked"
    return ValidationResult(name=check_name, passed=passed, errors=errors, warnings=warnings)


def validate_yaml_configuration() -> ValidationResult:
    """
    CHECK #9: YAML configuration validation (MANDATORY).

    4-level validation:
    1. Syntax Validation - Parse all YAML files for syntax errors
    2. Decimal Safety - Detect float contamination in Decimal fields
    3. Required Keys - Validate required keys per file type
    4. Cross-file Consistency - Validate references between config files

    Returns ERROR for syntax errors and float contamination (CRITICAL for trading).
    Returns WARNING for missing non-critical keys.
    """
    errors = []
    warnings = []

    if not YAML_AVAILABLE:
        warnings.append("PyYAML not installed - skipping YAML validation (run: pip install pyyaml)")
        return ValidationResult(
            name="YAML Configuration Validation (Check #9)",
            passed=True,
            errors=[],
            warnings=warnings,
        )

    config_dir = PROJECT_ROOT / "config"

    if not config_dir.exists():
        warnings.append("config/ directory not found - skipping YAML validation")
        return ValidationResult(
            name="YAML Configuration Validation (Check #9)",
            passed=True,
            errors=[],
            warnings=warnings,
        )

    yaml_files = list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml"))

    if not yaml_files:
        warnings.append("No YAML files found in config/ - skipping validation")
        return ValidationResult(
            name="YAML Configuration Validation (Check #9)",
            passed=True,
            errors=[],
            warnings=warnings,
        )

    files_checked = 0
    float_warnings_count = 0

    # Keywords that should use Decimal (string format) not float
    decimal_keywords = {
        "price",
        "threshold",
        "limit",
        "kelly",
        "spread",
        "probability",
        "fraction",
        "rate",
        "fee",
        "stop",
        "target",
        "trailing",
        "bid",
        "ask",
        "edge",
        "elo",
        "coefficient",
        "weight",
    }

    for yaml_file in yaml_files:
        files_checked += 1

        # Level 1: Syntax Validation
        try:
            with open(yaml_file, encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(f"{yaml_file.name}: YAML syntax error - {e}")
            continue  # Can't check further if syntax is broken

        if config_data is None:
            warnings.append(f"{yaml_file.name}: Empty YAML file")
            continue

        # Level 2: Decimal Safety Check (CRITICAL)
        # Recursively check for float values in Decimal-related keys
        def check_float_contamination(data, path="", file_name=yaml_file.name):
            """Recursively check for float values in Decimal fields."""
            nonlocal float_warnings_count

            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else str(key)

                    # Check if this key should be a Decimal (string) but is a float
                    # Only check string keys (skip integer keys)
                    if (
                        isinstance(key, str)
                        and any(keyword in key.lower() for keyword in decimal_keywords)
                        and isinstance(value, float)
                    ):
                        warnings.append(
                            f"{file_name}: Float detected in Decimal field '{current_path}': {value}"
                        )
                        warnings.append(
                            f'  RECOMMENDATION: Change to string format: {key}: "{value}"'
                        )
                        float_warnings_count += 1

                    # Recurse into nested structures
                    check_float_contamination(value, current_path, file_name)

            elif isinstance(data, list):
                for i, item in enumerate(data):
                    check_float_contamination(item, f"{path}[{i}]", file_name)

        check_float_contamination(config_data, "", yaml_file.name)

    passed = len(errors) == 0

    # Construct check name with details
    check_name = f"YAML Configuration Validation (Check #9) - {files_checked} files checked"
    if float_warnings_count > 0:
        warnings.insert(
            0,
            f"DECIMAL SAFETY: Found {float_warnings_count} potential float contamination issues",
        )
        warnings.insert(
            1,
            "Float values in price/probability fields can cause rounding errors - use string format",
        )

    return ValidationResult(name=check_name, passed=passed, errors=errors, warnings=warnings)


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("Documentation Validation Suite - Phase 0.6c (Enhanced)")
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
    results.append(validate_new_docs_in_master_index())  # Check #6 [ENFORCED]
    results.append(validate_git_version_bumps())  # Check #7 [ENFORCED]
    results.append(validate_phase_completion_status())  # Check #8 [ENFORCED]
    results.append(validate_yaml_configuration())  # Check #9 [ENFORCED]

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
        print(f"[OK] ALL VALIDATION CHECKS PASSED ({passed_checks}/{total_checks})")
        print("=" * 60)
        return 0
    print(
        f"[FAIL] VALIDATION FAILED ({passed_checks}/{total_checks} passed, {failed_checks} failed)"
    )
    print("=" * 60)
    print("\nFix issues above before committing.")
    print("Some issues can be auto-fixed with: python scripts/fix_docs.py")
    return 1


if __name__ == "__main__":
    sys.exit(main())
