# Precog Documentation Workflow Guide

---
**Version:** 1.0
**Created:** 2025-11-13
**Last Updated:** 2025-11-13
**Purpose:** Comprehensive guide for maintaining document cohesion and consistency across the Precog documentation system
**Extracted From:** CLAUDE.md V1.15 (Section: Document Cohesion & Consistency, Lines 2028-2847)
**Status:** ✅ Current
---

## 📋 Table of Contents

1. [Why Document Consistency Matters](#why-document-consistency-matters)
2. [Document Dependency Map](#document-dependency-map)
3. [Update Cascade Rules](#update-cascade-rules)
4. [Status Field Usage Standards](#status-field-usage-standards)
5. [Consistency Validation Checklist](#consistency-validation-checklist)
6. [Common Update Patterns](#common-update-patterns)
7. [Validation Script Template](#validation-script-template)
8. [Summary Workflow](#summary-workflow)

---

## Why Document Consistency Matters

⚠️ **CRITICAL** - Read carefully. Document drift causes bugs, confusion, and wasted time.

### The Problem

When you add a requirement, make an architecture decision, or complete a task, **multiple documents need updating**. Miss one, and documentation becomes inconsistent, leading to:

- Requirements in MASTER_REQUIREMENTS but not in REQUIREMENT_INDEX
- ADRs in ARCHITECTURE_DECISIONS but not in ADR_INDEX
- Phase tasks in DEVELOPMENT_PHASES but not aligned with MASTER_REQUIREMENTS
- Supplementary specs not referenced in foundation documents
- MASTER_INDEX listing documents that don't exist or have wrong names

### The Solution

Follow the **Update Cascade Rules** below. When you change one document, you MUST update its downstream dependencies.

---

## Document Dependency Map

Understanding Upstream → Downstream Flow:

```
┌─────────────────────────────────────────────────────────────┐
│                    MASTER_INDEX (V2.9)                       │
│          Master inventory of ALL documents                   │
│          Updates when ANY document added/removed/renamed     │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼───────┐        ┌───────▼────────┐
│ MASTER_       │        │ ARCHITECTURE_  │
│ REQUIREMENTS  │        │ DECISIONS      │
│ (V2.10)       │        │ (V2.10)        │
└───┬───────┬───┘        └───┬────────┬───┘
    │       │                │        │
    │       │                │        │
┌───▼───┐ ┌─▼─────────┐  ┌──▼────┐ ┌─▼────────┐
│ REQ   │ │ DEV       │  │ ADR   │ │ Supp     │
│ INDEX │ │ PHASES    │  │ INDEX │ │ Specs    │
│       │ │ (V1.8)    │  │       │ │          │
└───────┘ └───────────┘  └───────┘ └──────────┘
```

### Key Relationships

1. **MASTER_INDEX** depends on everything (always update last)
2. **MASTER_REQUIREMENTS** feeds into REQUIREMENT_INDEX and DEVELOPMENT_PHASES
3. **ARCHITECTURE_DECISIONS** feeds into ADR_INDEX and Supplementary Specs
4. **DEVELOPMENT_PHASES** must align with MASTER_REQUIREMENTS
5. **Supplementary Specs** must be referenced in MASTER_REQUIREMENTS or ARCHITECTURE_DECISIONS

---

## Update Cascade Rules

### Rule 1: Adding a New Requirement

**When you add REQ-XXX-NNN to MASTER_REQUIREMENTS, you MUST:**

1. ✅ **Add to MASTER_REQUIREMENTS** (primary source)
   ```markdown
   **REQ-CLI-006: Market Fetch Command**
   - Phase: 2
   - Priority: Critical
   - Status: 🔵 Planned
   - Description: Fetch markets from Kalshi API with DECIMAL precision
   ```

2. ✅ **Add to REQUIREMENT_INDEX** (for searchability)
   ```markdown
   | REQ-CLI-006 | Market Fetch Command | 2 | Critical | 🔵 Planned |
   ```

3. ✅ **Check DEVELOPMENT_PHASES alignment**
   - Is this requirement listed in the phase deliverables?
   - If not, add it to the phase's task list

4. ✅ **Update MASTER_REQUIREMENTS version** (V2.10 → V2.11)

5. ✅ **Update MASTER_INDEX** (if filename changes)
   ```markdown
   | MASTER_REQUIREMENTS_V2.11.md | ✅ | v2.11 | ... | UPDATED from V2.10 |
   ```

**Example Commit Message:**
```
Add REQ-CLI-006 for market fetch command

- Add to MASTER_REQUIREMENTS V2.10 → V2.11
- Add to REQUIREMENT_INDEX
- Verify alignment with DEVELOPMENT_PHASES Phase 2
- Update MASTER_INDEX
```

---

### Rule 2: Adding an Architecture Decision

**When you add ADR-XXX to ARCHITECTURE_DECISIONS, you MUST:**

1. ✅ **Add to ARCHITECTURE_DECISIONS** (primary source)
   ```markdown
   ### ADR-038: CLI Framework Choice

   **Decision #38**
   **Phase:** 1
   **Status:** ✅ Complete

   **Decision:** Use Typer for CLI framework

   **Rationale:** Type hints, auto-help, modern Python
   ```

2. ✅ **Add to ADR_INDEX** (for searchability)
   ```markdown
   | ADR-038 | CLI Framework (Typer) | Phase 1 | ✅ Complete | 🔴 Critical |
   ```

3. ✅ **Reference in related requirements**
   - Find related REQ-CLI-* requirements
   - Add cross-reference: "See ADR-038 for framework choice"

4. ✅ **Update ARCHITECTURE_DECISIONS version** (V2.9 → V2.10)

5. ✅ **Update ADR_INDEX version** (V1.1 → V1.2)

6. ✅ **Update MASTER_INDEX** (if filenames change)

**Example Commit Message:**
```
Add ADR-038 for CLI framework decision (Typer)

- Add to ARCHITECTURE_DECISIONS V2.9 → V2.10
- Add to ADR_INDEX V1.1 → V1.2
- Cross-reference in MASTER_REQUIREMENTS (REQ-CLI-001)
- Update MASTER_INDEX
```

---

### Rule 3: Creating Supplementary Specification

**When you create a new supplementary spec, you MUST:**

1. ✅ **Create the spec file**
   - Use consistent naming: `FEATURE_NAME_SPEC_V1.0.md`
   - Remove phase numbers from filename
   - Include version header

2. ✅ **Reference in MASTER_REQUIREMENTS**
   ```markdown
   **REQ-EXEC-008: Advanced Walking Algorithm**
   ...
   **Reference:** See `supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md` for detailed walking algorithm
   ```

3. ✅ **Reference in ARCHITECTURE_DECISIONS** (if applicable)
   ```markdown
   ### ADR-037: Order Walking Strategy
   ...
   **Reference:** See `supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md`
   ```

4. ✅ **Add to MASTER_INDEX**
   ```markdown
   | ADVANCED_EXECUTION_SPEC_V1.0.md | ✅ | v1.0 | `/docs/supplementary/` | 5 | Phase 5b | 🟡 High | Order walking algorithms |
   ```

5. ✅ **Update version numbers** on referencing documents

**Example Commit Message:**
```
Add Advanced Execution Spec V1.0

- Create supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md
- Reference in MASTER_REQUIREMENTS (REQ-EXEC-008)
- Reference in ARCHITECTURE_DECISIONS (ADR-037)
- Add to MASTER_INDEX
- Update MASTER_REQUIREMENTS V2.10 → V2.11
```

---

### Rule 4: Renaming or Moving Documents

**When you rename/move a document, you MUST:**

1. ✅ **Use `git mv` to preserve history**
   ```bash
   git mv old_name.md new_name.md
   ```

2. ✅ **Update MASTER_INDEX**
   ```markdown
   | NEW_NAME_V1.0.md | ✅ | v1.0 | `/new/location/` | ... | **RENAMED** from old_name |
   ```

3. ✅ **Update ALL references in other documents**
   ```bash
   # Find all references
   grep -r "old_name.md" docs/

   # Update each reference to new_name.md
   ```

4. ✅ **Add note in renamed file header**
   ```markdown
   **Filename Updated:** Renamed from old_name.md to NEW_NAME_V1.0.md on 2025-10-XX
   ```

5. ✅ **Validate no broken links**
   ```bash
   python scripts/validate_doc_references.py
   ```

**Example Commit Message:**
```
Rename PHASE_5_EXIT_SPEC to EXIT_EVALUATION_SPEC_V1.0

- Rename with git mv (preserves history)
- Update all 7 references in foundation docs
- Update MASTER_INDEX with "RENAMED" note
- Add filename update note to file header
- Validate no broken links
```

---

### Rule 5: Completing a Phase Task

**When you complete a task from DEVELOPMENT_PHASES, you MUST:**

1. ✅ **Mark complete in DEVELOPMENT_PHASES**
   ```markdown
   - [✅] Kalshi API client implementation
   ```

2. ✅ **Update related requirements status**
   ```markdown
   **REQ-API-001: Kalshi API Integration**
   - Status: ✅ Complete  # Changed from 🔵 Planned
   ```

3. ✅ **Update REQUIREMENT_INDEX status**
   ```markdown
   | REQ-API-001 | Kalshi API Integration | 1 | Critical | ✅ Complete |
   ```

4. ✅ **Update CLAUDE.md Current Status** (if major milestone)
   ```markdown
   **Phase 1 Status:** 50% → 65% complete
   ```

5. ✅ **Update SESSION_HANDOFF.md**
   ```markdown
   ## This Session Completed
   - ✅ Kalshi API client (REQ-API-001 complete)
   ```

**Example Commit Message:**
```
Complete REQ-API-001: Kalshi API client

- Mark complete in DEVELOPMENT_PHASES
- Update REQ-API-001 status to Complete in MASTER_REQUIREMENTS
- Update REQUIREMENT_INDEX
- Update CLAUDE.md (Phase 1: 50% → 65%)
- Update SESSION_HANDOFF
```

---

### Rule 6: Planning Future Work

**When you identify future enhancements during implementation, you MUST:**

1. ✅ **Add to DEVELOPMENT_PHASES**
   - Create new Phase section (e.g., Phase 0.7) if logical grouping
   - OR add to existing future phase section
   - Mark all tasks as `[ ]` (not started)
   ```markdown
   ### Phase 0.7: CI/CD Integration (Future)
   **Status:** 🔵 Planned
   - [ ] GitHub Actions workflow
   - [ ] Codecov integration
   ```

2. ✅ **Add to MASTER_REQUIREMENTS** (if formal requirements)
   ```markdown
   **REQ-CICD-001: GitHub Actions Integration**
   - Phase: 0.7 (Future)
   - Priority: High
   - Status: 🔵 Planned  # Not ✅ Complete or 🟡 In Progress
   - Description: ...
   ```

3. ✅ **Add to REQUIREMENT_INDEX** (if requirements added)
   ```markdown
   | REQ-CICD-001 | GitHub Actions | 0.7 | High | 🔵 Planned |
   ```

4. ✅ **Add to ARCHITECTURE_DECISIONS** (if design decisions needed)
   ```markdown
   ### ADR-052: CI/CD Pipeline Strategy (Planned)

   **Decision #52**
   **Phase:** 0.7 (Future)
   **Status:** 🔵 Planned

   **Decision:** Use GitHub Actions for CI/CD

   **Rationale:** (high-level, can be expanded when implementing)

   **Implementation:** (To be detailed in Phase 0.7)

   **Related Requirements:** REQ-CICD-001
   ```

5. ✅ **Add to ADR_INDEX** (if ADRs added)
   ```markdown
   | ADR-052 | CI/CD Pipeline (GitHub Actions) | 0.7 | 🔵 Planned | 🟡 High |
   ```

6. ✅ **Add "Future Enhancements" section** to technical docs
   - In TESTING_STRATEGY, VALIDATION_LINTING_ARCHITECTURE, etc.
   - Describes what's coming next
   - References related REQs and ADRs

7. ✅ **Update version numbers** on all modified docs

8. ✅ **Update MASTER_INDEX** (if filenames change)

**When to use this rule:**
- 🎯 During implementation, you discover logical next steps
- 🎯 User mentions future work they want documented
- 🎯 You create infrastructure that enables future capabilities
- 🎯 Phase completion reveals obvious next phase

**Example trigger:**
"We just built validation infrastructure. This enables CI/CD integration in the future. Should document CI/CD as planned work now."

**Example Commit Message:**
```
Implement Phase 0.6c validation suite + document Phase 0.7 CI/CD plans

Implementation (Phase 0.6c):
- Add validation suite (validate_docs.py, validate_all.sh)
- ... (current work)

Future Planning (Phase 0.7):
- Add REQ-CICD-001 to MASTER_REQUIREMENTS V2.10 → V2.11 (🔵 Planned)
- Add ADR-052 to ARCHITECTURE_DECISIONS V2.10 (🔵 Planned)
- Add Phase 0.7 to DEVELOPMENT_PHASES V1.7 → V1.8
- Add "Future Enhancements" sections to technical docs
- Update indexes (REQUIREMENT_INDEX, ADR_INDEX)

Phase 0.6c: ✅ Complete
Phase 0.7: 🔵 Planned and documented
```

---

## Status Field Usage Standards

Use consistent status indicators across all documentation:

### Requirement & ADR Status

| Status | Meaning | When to Use |
|--------|---------|-------------|
| 🔵 Planned | Documented but not started | Future work, identified but not implemented |
| 🟡 In Progress | Currently being worked on | Active development this session |
| ✅ Complete | Implemented and tested | Done, tests passing, committed |
| ⏸️ Paused | Started but blocked/deferred | Waiting on dependency or decision |
| ❌ Rejected | Considered but decided against | Document why NOT doing something |
| 📦 Archived | Was complete, now superseded | Old versions, deprecated approaches |

### Phase Status

| Status | Meaning |
|--------|---------|
| 🔵 Planned | Phase not yet started |
| 🟡 In Progress | Phase currently active (XX% complete) |
| ✅ Complete | Phase 100% complete, all deliverables done |

### Document Status (MASTER_INDEX)

| Status | Meaning |
|--------|---------|
| ✅ Current | Latest version, actively maintained |
| 🔵 Planned | Document listed but not yet created |
| 📦 Archived | Old version, moved to _archive/ |
| 🚧 Draft | Exists but incomplete/in revision |

### Consistency Rules

1. **Same status across paired documents**
   - REQ-API-001 is 🔵 Planned in MASTER_REQUIREMENTS
   - REQ-API-001 is 🔵 Planned in REQUIREMENT_INDEX
   - (Never: 🔵 in one, ✅ in other)

2. **Phase determines status**
   - Phase 0.6c work = ✅ Complete (this session)
   - Phase 0.7 work = 🔵 Planned (future)
   - Phase 1 in-progress work = 🟡 In Progress

3. **Status transitions**
   - 🔵 Planned → 🟡 In Progress (when starting work)
   - 🟡 In Progress → ✅ Complete (when done + tested)
   - ✅ Complete → 📦 Archived (when superseded)

4. **Never skip statuses**
   - ❌ BAD: 🔵 Planned → ✅ Complete (skip 🟡 In Progress)
   - ✅ GOOD: 🔵 Planned → 🟡 In Progress → ✅ Complete

---

## Todo List Best Practices for Documentation Updates

**Problem Identified:** Phase 1.5 (2025-11-17)

Creating requirements or ADRs without explicit todo items for EACH update location leads to orphaned documentation. Human memory alone is insufficient for tracking multi-location updates.

**Real-World Example:**

In Phase 1.5, when creating REQ-TEST-012 through REQ-TEST-019:
1. ✅ Created TEST_REQUIREMENTS_COMPREHENSIVE_V1.0.md with 8 detailed requirements
2. ✅ Marked todo as "Create REQ-TEST-012 through REQ-TEST-019" COMPLETE
3. ❌ **Nearly forgot** to add them to MASTER_REQUIREMENTS_V2.16
4. ❌ **Nearly forgot** to add them to REQUIREMENT_INDEX
5. ❌ **Nearly forgot** to update MASTER_INDEX
6. 🚨 **Caught by:** User question ("was master requirements updated?")
7. ✅ **Would have been caught by:** Pre-commit validation (Check #2: Requirement Consistency)

**Root Cause:** Single todo item covering multi-location update created false sense of completion.

### Solution: Granular Todo Items

When creating new requirements or ADRs, create **SEPARATE todo items** for EACH location requiring updates:

**✅ CORRECT Approach (Granular Todos):**

```markdown
Creating 8 new test requirements:
- [ ] Create REQ-TEST-012 through REQ-TEST-019 in TEST_REQUIREMENTS_COMPREHENSIVE
- [ ] Add REQ-TEST-012 through REQ-TEST-019 to MASTER_REQUIREMENTS (update V2.15→V2.16)
- [ ] Add REQ-TEST-012 through REQ-TEST-019 to REQUIREMENT_INDEX (update count 113→121)
- [ ] Update MASTER_INDEX entry for MASTER_REQUIREMENTS (V2.15→V2.16)
- [ ] Update MASTER_INDEX entry for REQUIREMENT_INDEX (113→121 requirements)
- [ ] Update cross-references in related documents (find all V2.15 references)
```

**❌ INCORRECT Approach (Single Todo):**

```markdown
Creating 8 new test requirements:
- [ ] Create REQ-TEST-012 through REQ-TEST-019
```

This single todo creates false completion when only the first step is done.

### Template: New Requirement Todos

Copy this template when creating new requirements:

```markdown
Creating [REQ-XXX-NNN through REQ-XXX-NNN]:
- [ ] Create detailed requirement specification in [DOCUMENT_NAME]
- [ ] Add to MASTER_REQUIREMENTS (update VX.Y→VX.Z)
- [ ] Add to REQUIREMENT_INDEX (update count N→M)
- [ ] Update MASTER_INDEX entry for MASTER_REQUIREMENTS (version change)
- [ ] Update MASTER_INDEX entry for REQUIREMENT_INDEX (count change)
- [ ] Update cross-references in related documents (grep for old version references)
- [ ] Update related ADRs if applicable
```

### Template: New ADR Todos

Copy this template when creating new ADRs:

```markdown
Creating ADR-XXX [Decision Name]:
- [ ] Create detailed ADR in ARCHITECTURE_DECISIONS (update VX.Y→VX.Z)
- [ ] Add to ADR_INDEX (update count N→M)
- [ ] Update MASTER_INDEX entry for ARCHITECTURE_DECISIONS (version change)
- [ ] Update MASTER_INDEX entry for ADR_INDEX (count change)
- [ ] Update related requirements in MASTER_REQUIREMENTS (add cross-reference)
- [ ] Update cross-references in related documents
```

### Why This Matters

**Multi-Layer Defense:**

1. **Layer 1: Human Planning** - Granular todos prevent forgetting steps
2. **Layer 2: Human Oversight** - User/reviewer questions ("was X updated?")
3. **Layer 3: Automated Validation** - Pre-commit hooks catch orphaned requirements/ADRs

**Validation would catch this, but prevention is better:**

Without granular todos, you rely on Layer 3 (validation failure) instead of Layer 1 (correct planning). Validation failures require:
- Interrupting commit flow
- Context switching back to documentation
- Re-running validation after fixes
- Lost momentum

**With granular todos:**
- All updates planned upfront
- No validation surprises
- Smooth commit workflow
- Clear progress tracking

### Common Mistake Patterns

**Mistake 1: Scope Creep in Single Todo**

```markdown
❌ BAD:
- [ ] Add test coverage requirements

This expands to:
- Create 8 requirements in detailed spec
- Add to MASTER_REQUIREMENTS
- Add to REQUIREMENT_INDEX
- Update MASTER_INDEX (2 entries)
- Update 7 cross-references

Marking this single todo "complete" after creating the spec leaves 80% of work undone.
```

**Mistake 2: "I'll remember to update X"**

```markdown
❌ BAD:
- [ ] Create REQ-TEST-012 in TEST_REQUIREMENTS_COMPREHENSIVE
  (I'll remember to add it to MASTER_REQUIREMENTS later)

REALITY:
- Session interrupted
- Context lost
- Requirement orphaned
- Validation catches it (or worse, it's missed)
```

**Mistake 3: Assuming Validation is Sufficient**

```markdown
❌ BAD MINDSET:
"Pre-commit validation will catch missing updates, so I don't need detailed todos"

PROBLEMS:
1. Validation interrupts flow (fix → re-run → fix → re-run)
2. Multiple validation failures = multiple interruptions
3. Context switching reduces productivity
4. Granular todos prevent the problem vs. detecting it
```

### Success Metrics

**You're doing it right if:**
- ✅ Each major documentation update has 3-6 separate todos
- ✅ Todos are marked complete only when THAT SPECIFIC update is done
- ✅ No validation failures due to missing updates
- ✅ Clear progress tracking (5/6 todos done = 83% progress)

**You're doing it wrong if:**
- ❌ Single todo covers multi-location updates
- ❌ Validation frequently catches missing updates
- ❌ You mark todos complete prematurely
- ❌ You frequently ask yourself "did I update X?"

### Integration with Update Cascade Rules

This best practice complements the **Update Cascade Rules** (Section 3):

- **Update Cascade Rules** = WHAT documents to update (the map)
- **Todo List Best Practices** = HOW to track those updates (the checklist)

Together, they prevent documentation drift:
1. Cascade rules tell you: "Adding REQ requires updating MASTER_REQUIREMENTS, REQUIREMENT_INDEX, MASTER_INDEX"
2. Todo best practices tell you: "Create separate todo for each of those 3 updates"

### Cross-References

- **Section 3: Update Cascade Rules** - Defines WHAT to update
- **Section 5: Consistency Validation Checklist** - Validates updates completed
- **CLAUDE.md Section 5** - Quick reference for document cohesion
- **Real-world example:** Phase 1.5 test requirements (REQ-TEST-012 through REQ-TEST-019)

---

## Consistency Validation Checklist

**Run this checklist BEFORE committing any documentation changes:**

### Level 1: Quick Checks (2 minutes)

- [ ] **Cross-references valid?**
  ```bash
  # Check all .md references in foundation docs
  grep -r "\.md" docs/foundation/*.md | grep -v "^#"
  # Verify each reference exists
  ```

- [ ] **Version numbers consistent?**
  - Header version matches filename? (e.g., V2.10 in MASTER_REQUIREMENTS_V2.10.md)
  - All references use correct version?

- [ ] **MASTER_INDEX accurate?**
  - Document exists at listed location?
  - Version matches?
  - Status correct (✅ exists, 🔵 planned)?

### Level 2: Requirement Consistency (5 minutes)

- [ ] **Requirements in both places?**
  ```bash
  # Extract REQ IDs from MASTER_REQUIREMENTS
  grep -E "REQ-[A-Z]+-[0-9]+" docs/foundation/MASTER_REQUIREMENTS*.md | sort -u

  # Compare with REQUIREMENT_INDEX
  grep -E "REQ-[A-Z]+-[0-9]+" docs/foundation/REQUIREMENT_INDEX.md | sort -u

  # Should match exactly
  ```

- [ ] **Requirements align with phases?**
  - Each Phase 1 requirement in DEVELOPMENT_PHASES Phase 1 section?
  - Each Phase 2 requirement in DEVELOPMENT_PHASES Phase 2 section?

- [ ] **Requirement statuses consistent?**
  - Same status in MASTER_REQUIREMENTS and REQUIREMENT_INDEX?
  - Completed requirements marked in DEVELOPMENT_PHASES?

### Level 3: ADR Consistency (5 minutes)

- [ ] **ADRs in both places?**
  ```bash
  # Extract ADR numbers from ARCHITECTURE_DECISIONS
  grep -E "ADR-[0-9]+" docs/foundation/ARCHITECTURE_DECISIONS*.md | sort -u

  # Compare with ADR_INDEX
  grep -E "ADR-[0-9]+" docs/foundation/ADR_INDEX.md | sort -u

  # Should match exactly
  ```

- [ ] **ADRs sequentially numbered?**
  - No gaps (ADR-001, ADR-002, ADR-003... no missing numbers)
  - No duplicates

- [ ] **ADRs referenced where needed?**
  - Critical ADRs referenced in MASTER_REQUIREMENTS?
  - Related ADRs cross-referenced?

### Level 4: Supplementary Spec Consistency (5 minutes)

- [ ] **All supplementary specs referenced?**
  ```bash
  # List all supplementary specs
  ls docs/supplementary/*.md

  # Check each is referenced in MASTER_REQUIREMENTS or ARCHITECTURE_DECISIONS
  for file in docs/supplementary/*.md; do
      basename="$(basename $file)"
      grep -r "$basename" docs/foundation/
  done
  ```

- [ ] **Specs match naming convention?**
  - Format: `FEATURE_NAME_SPEC_V1.0.md`
  - No phase numbers in filename
  - Version in filename matches header

- [ ] **Specs in MASTER_INDEX?**
  - All supplementary specs listed?
  - Correct location, version, status?

---

## Common Update Patterns

### Pattern 1: Adding a Complete Feature

**Scenario:** Adding CLI market fetch command

**Documents to Update (in order):**

1. **MASTER_REQUIREMENTS** (add requirement)
   ```markdown
   **REQ-CLI-006: Market Fetch Command**
   - Phase: 2
   - Priority: Critical
   - Status: 🔵 Planned
   ```

2. **REQUIREMENT_INDEX** (add to table)
   ```markdown
   | REQ-CLI-006 | Market Fetch Command | 2 | Critical | 🔵 Planned |
   ```

3. **DEVELOPMENT_PHASES** (add to Phase 2 tasks)
   ```markdown
   #### Phase 2: Football Market Data (Weeks 3-4)
   ...
   - [ ] CLI command: `main.py fetch-markets`
   ```

4. **ARCHITECTURE_DECISIONS** (if needed, add ADR)
   ```markdown
   ### ADR-039: Market Fetch Strategy
   ...
   ```

5. **ADR_INDEX** (if ADR added)
   ```markdown
   | ADR-039 | Market Fetch Strategy | 2 | 🔵 Planned | 🟡 High |
   ```

6. **Version bump** all modified docs
   - MASTER_REQUIREMENTS V2.10 → V2.11
   - ARCHITECTURE_DECISIONS V2.9 → V2.10 (if ADR added)
   - ADR_INDEX V1.1 → V1.2 (if ADR added)

7. **MASTER_INDEX** (if filenames changed)
   ```markdown
   | MASTER_REQUIREMENTS_V2.11.md | ✅ | v2.11 | ... | UPDATED from V2.10 |
   ```

8. **SESSION_HANDOFF** (document the changes)

**Commit Message:**
```
Add REQ-CLI-006 for market fetch command

Foundation Updates:
- Add REQ-CLI-006 to MASTER_REQUIREMENTS V2.10 → V2.11
- Add REQ-CLI-006 to REQUIREMENT_INDEX
- Add to DEVELOPMENT_PHASES Phase 2 tasks
- Add ADR-039 for fetch strategy to ARCHITECTURE_DECISIONS V2.9 → V2.10
- Add ADR-039 to ADR_INDEX V1.1 → V1.2
- Update MASTER_INDEX

Validates:
- ✅ Requirements consistent across docs
- ✅ ADRs properly indexed
- ✅ Phase tasks aligned
- ✅ All versions bumped
```

---

### Pattern 2: Implementing and Completing a Feature

**Scenario:** Just finished implementing Kalshi API client

**Documents to Update (in order):**

1. **MASTER_REQUIREMENTS** (update status)
   ```markdown
   **REQ-API-001: Kalshi API Integration**
   - Status: ✅ Complete  # Was 🔵 Planned
   ```

2. **REQUIREMENT_INDEX** (update status)
   ```markdown
   | REQ-API-001 | Kalshi API Integration | 1 | Critical | ✅ Complete |
   ```

3. **DEVELOPMENT_PHASES** (mark complete)
   ```markdown
   #### Phase 1: Core Foundation
   **Weeks 2-4: Kalshi API Integration**
   - [✅] RSA-PSS authentication implementation  # Was [ ]
   - [✅] REST endpoints: markets, events, series, balance, positions, orders
   - [✅] Error handling and exponential backoff retry logic
   ```

4. **CLAUDE.md** (update status if major milestone)
   ```markdown
   **Phase 1 Status:** 50% → 75% complete  # Significant progress
   ```

5. **SESSION_HANDOFF** (document completion)
   ```markdown
   ## This Session Completed
   - ✅ REQ-API-001: Kalshi API client fully implemented
   - ✅ 15 tests added (all passing)
   - ✅ Coverage increased 87% → 92%
   ```

6. **Version bump** modified docs
   - MASTER_REQUIREMENTS V2.10 → V2.11
   - DEVELOPMENT_PHASES V1.7 → V1.8 (if significant changes)

7. **MASTER_INDEX** (if filenames changed)

**Commit Message:**
```
Complete REQ-API-001: Kalshi API client implementation

Implementation:
- Add api_connectors/kalshi_client.py
- Add tests/test_kalshi_client.py (15 tests)
- All prices use Decimal precision
- RSA-PSS authentication working
- Rate limiting (100 req/min) implemented

Documentation Updates:
- Update REQ-API-001 status to Complete in MASTER_REQUIREMENTS V2.10 → V2.11
- Update REQUIREMENT_INDEX status
- Mark Phase 1 Kalshi tasks complete in DEVELOPMENT_PHASES
- Update CLAUDE.md (Phase 1: 50% → 75%)
- Update SESSION_HANDOFF

Tests: 66/66 → 81/81 passing (87% → 92% coverage)
Phase 1: 50% → 75% complete
```

---

### Pattern 3: Reorganizing Documentation

**Scenario:** Moving guides from `/supplementary/` to `/guides/` and renaming

**Documents to Update (in order):**

1. **Move files with git mv**
   ```bash
   git mv docs/supplementary/VERSIONING_GUIDE.md docs/guides/VERSIONING_GUIDE_V1.0.md
   git mv docs/supplementary/TRAILING_STOP_GUIDE.md docs/guides/TRAILING_STOP_GUIDE_V1.0.md
   ```

2. **Update file headers** (add rename note)
   ```markdown
   **Filename Updated:** Moved from supplementary/ to guides/ on 2025-10-28
   ```

3. **Find and update ALL references**
   ```bash
   # Find all references
   grep -r "supplementary/VERSIONING_GUIDE" docs/

   # Update each to: guides/VERSIONING_GUIDE_V1.0.md
   ```

4. **Update MASTER_INDEX**
   ```markdown
   | VERSIONING_GUIDE_V1.0.md | ✅ | v1.0 | `/docs/guides/` | ... | **MOVED** from /supplementary/ |
   ```

5. **Update MASTER_REQUIREMENTS** (references)
   ```markdown
   **Reference:** See `guides/VERSIONING_GUIDE_V1.0.md` for versioning patterns
   ```

6. **Validate no broken links**
   ```bash
   python scripts/validate_doc_references.py
   ```

7. **Version bump** all docs with references updated
   - MASTER_REQUIREMENTS V2.10 → V2.11
   - MASTER_INDEX V2.8 → V2.9

8. **SESSION_HANDOFF** (document reorganization)

**Commit Message:**
```
Reorganize guides: Move from supplementary to guides folder

File Operations:
- Move VERSIONING_GUIDE to guides/VERSIONING_GUIDE_V1.0.md
- Move TRAILING_STOP_GUIDE to guides/TRAILING_STOP_GUIDE_V1.0.md
- Move POSITION_MANAGEMENT_GUIDE to guides/POSITION_MANAGEMENT_GUIDE_V1.0.md

Documentation Updates:
- Update 12 references in MASTER_REQUIREMENTS V2.10 → V2.11
- Update 8 references in ARCHITECTURE_DECISIONS
- Update MASTER_INDEX V2.8 → V2.9 with new locations
- Add "MOVED" notes to file headers
- Validate all references (zero broken links)

Rationale: Separate implementation guides from supplementary specs
```

---

## Validation Script Template

**Create:** `scripts/validate_doc_consistency.py`

```python
"""
Validate document consistency across foundation documents.

Checks:
1. Requirements in both MASTER_REQUIREMENTS and REQUIREMENT_INDEX
2. ADRs in both ARCHITECTURE_DECISIONS and ADR_INDEX
3. All supplementary specs referenced
4. MASTER_INDEX accuracy
5. No broken document references
"""
import re
from pathlib import Path

def validate_requirements():
    """Validate requirement IDs match across documents."""
    # Extract REQ IDs from MASTER_REQUIREMENTS
    master_reqs = set()
    master_req_file = Path("docs/foundation/MASTER_REQUIREMENTS_V2.10.md")
    content = master_req_file.read_text()
    master_reqs = set(re.findall(r'REQ-[A-Z]+-\d+', content))

    # Extract REQ IDs from REQUIREMENT_INDEX
    index_reqs = set()
    index_file = Path("docs/foundation/REQUIREMENT_INDEX.md")
    content = index_file.read_text()
    index_reqs = set(re.findall(r'REQ-[A-Z]+-\d+', content))

    # Compare
    missing_in_index = master_reqs - index_reqs
    missing_in_master = index_reqs - master_reqs

    if missing_in_index:
        print(f"[FAIL] {len(missing_in_index)} requirements in MASTER_REQUIREMENTS but not in REQUIREMENT_INDEX:")
        for req in sorted(missing_in_index):
            print(f"   - {req}")

    if missing_in_master:
        print(f"[FAIL] {len(missing_in_master)} requirements in REQUIREMENT_INDEX but not in MASTER_REQUIREMENTS:")
        for req in sorted(missing_in_master):
            print(f"   - {req}")

    if not missing_in_index and not missing_in_master:
        print(f"[OK] All {len(master_reqs)} requirements consistent")

    return len(missing_in_index) + len(missing_in_master) == 0

def validate_adrs():
    """Validate ADR numbers match across documents."""
    # Similar to validate_requirements
    # Extract from ARCHITECTURE_DECISIONS and ADR_INDEX
    # Compare sets
    pass

def validate_references():
    """Validate all .md references point to existing files."""
    # Find all references in foundation docs
    # Check each file exists
    pass

if __name__ == "__main__":
    print("Validating document consistency...\n")

    req_ok = validate_requirements()
    adr_ok = validate_adrs()
    ref_ok = validate_references()

    if req_ok and adr_ok and ref_ok:
        print("\n[OK] All validation checks passed")
        exit(0)
    else:
        print("\n[FAIL] Validation failed - fix issues above")
        exit(1)
```

**Run before every major commit:**
```bash
python scripts/validate_doc_consistency.py
```

---

## Summary Workflow

**When making any documentation change:**

1. **Identify impact**: Which documents reference this?
2. **Update cascade**: Follow Update Cascade Rules for your change type
3. **Validate consistency**: Run consistency checklist
4. **Version bump**: Increment versions on all modified docs
5. **Update MASTER_INDEX**: Reflect any filename changes
6. **Validate links**: Run validation script
7. **Update SESSION_HANDOFF**: Document what you changed
8. **Commit atomically**: All related changes in one commit

**Key Principle:** Documentation is code. Treat it with the same rigor as your Python code. Every change must maintain consistency across the entire documentation set.

---

## Related Documents

- **MASTER_INDEX_V2.9.md** - Complete document inventory
- **DEVELOPMENT_PATTERNS_V1.0.md** - Technical implementation patterns (extracted from CLAUDE.md)
- **CLAUDE.md** - Main project context file (now references this guide)
- **SESSION_HANDOFF.md** - Session-specific updates
- **MASTER_REQUIREMENTS_V2.10.md** - Requirements database
- **ARCHITECTURE_DECISIONS_V2.10.md** - Architectural decisions
- **DEVELOPMENT_PHASES_V1.8.md** - Phase roadmap

---

**END OF DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md**
