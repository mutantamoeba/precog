# Phase 0.6: Documentation Correction & Security Hardening

---
**Version:** 1.0
**Created:** 2025-10-28
**Status:** 🟡 In Progress
**Goal:** Systematically correct documentation issues, secure sensitive data, and prepare for Phase 1 implementation
**Duration:** 2-3 weeks
**Prerequisites:** Phase 0.5 Complete ✅, Phase 1 Schema Complete ✅
---

## Executive Summary

**Purpose:** This corrective phase addresses critical documentation inconsistencies, security vulnerabilities, and organizational issues discovered before proceeding with Phase 1 (API Integration). It ensures the foundation is solid, secure, and maintainable.

**Key Problems Identified:**
1. 🔴 **CRITICAL SECURITY**: Hardcoded passwords in 4 scripts, exposed in git history
2. 🔴 **CRITICAL**: Supplementary docs not properly referenced in foundational documents
3. 🟡 **HIGH**: Module structure misalignment between requirements and actual implementation
4. 🟡 **HIGH**: Phase tasks not aligned between MASTER_REQUIREMENTS and DEVELOPMENT_PHASES
5. 🟡 **HIGH**: Missing Phase 1 requirements (CLI, API, specific components)
6. 🟡 **MEDIUM**: Supplementary docs need renaming and reorganization for consistency
7. 🟡 **MEDIUM**: ADRs in ARCHITECTURAL_DECISIONS are out of order/missing numbers
8. 🟢 **LOW**: MASTER_INDEX needs accuracy verification

**Why Phase 0.6 (not Phase 0.5.1 or Phase 1.0):**
- More substantial than a patch (0.5.1)
- Critical foundation work before Phase 1 implementation
- Addresses security + documentation + process improvements
- Establishes patterns for future phase handoffs

---

## Success Criteria

### Must Complete (Blocking Phase 1)
- [ ] 🔒 All hardcoded passwords removed from code
- [ ] 🔒 Git history cleaned (Option C: fresh start)
- [ ] 🔒 PostgreSQL password rotated
- [ ] 🔒 `.gitignore` updated to prevent future exposures
- [ ] 📚 All supplementary docs properly referenced in foundational docs
- [ ] 📚 MASTER_INDEX 100% accurate (all docs exist or planned)
- [ ] 📚 ADRs properly numbered and ordered
- [ ] ✅ Phase 0.6 Completion Report created with all 8 steps passed

### Should Complete (Important but not blocking)
- [ ] Module structure aligned between docs and implementation
- [ ] Phase tasks aligned between MASTER_REQUIREMENTS and DEVELOPMENT_PHASES
- [ ] All Phase 1 requirements documented
- [ ] Supplementary docs renamed for consistency

### Nice to Have (Can defer to Phase 1.5)
- [ ] CLI requirements fully fleshed out
- [ ] Later-phase requirements more detailed

---

## Phase Structure

Phase 0.6 is organized into 3 sequential sub-phases:

### **Phase 0.6a: Security Hardening** (Week 1 - Days 1-3) 🔴 **CRITICAL**
Fix all security vulnerabilities before any other work.

### **Phase 0.6b: Documentation Correction** (Week 1-2 - Days 4-10)
Fix documentation inconsistencies and improve organization.

### **Phase 0.6c: Validation & Handoff** (Week 2-3 - Days 11-14)
Comprehensive validation and preparation for Phase 1.

---

# Phase 0.6a: Security Hardening (Days 1-3)

**Priority:** 🔴 **CRITICAL** - Must complete before any commits
**Duration:** 3 days
**Blocking:** All other work

## Day 1: Immediate Security Fixes

### Task 1.1: Fix Hardcoded Passwords in Scripts (2 hours)

**Files to Update:**
1. `scripts/test_db_simple.py` - Line 13
2. `scripts/apply_migration_v1.5.py` - Line 15
3. `scripts/apply_migration_v1.4.py` - Line 13
4. `scripts/apply_schema.py` - Line 13

**Pattern to Apply:**
```python
# ❌ BEFORE (INSECURE)
db_config = {
    'host': 'localhost',
    'database': 'precog_dev',
    'user': 'postgres',
    'password': 'suckbluefrogs'  # EXPOSED!
}

# ✅ AFTER (SECURE)
import os
from dotenv import load_dotenv

load_dotenv()

db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'precog_dev'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')
}

if not db_config['password']:
    raise ValueError("DB_PASSWORD environment variable not set")
```

**Verification:**
```bash
# After fixes, verify no hardcoded passwords remain
git grep -i "suckbluefrogs" -- '*.py'  # Should return nothing
git grep "password\s*=\s*['\"]" -- 'scripts/*.py'  # Should only show os.getenv lines
```

**Deliverable:** All 4 scripts updated to use environment variables

---

### Task 1.2: Update .gitignore (30 minutes)

**Add Missing Patterns:**

```gitignore
# Add to existing .gitignore

# Scripts with potential data
scripts/*.sql
scripts/*.dump
scripts/*.backup

# Database files
database/*.sql  # If folder contains scripts with data (verify first)

# Make _keys/ more specific
_keys/
*.pem
*.key
*.p12
*.pfx
*.cer
*.crt
```

**Verification:**
```bash
# Test .gitignore works
echo "test" > _keys/test.pem
git status | grep "test.pem"  # Should NOT appear

# Check all ignored files
git status --ignored
```

**Deliverable:** Updated `.gitignore` with comprehensive patterns

---

### Task 1.3: Verify No Other Secrets (1 hour)

**Comprehensive Scan:**
```bash
# Search all tracked files for potential secrets
git grep -E "(password|secret|key|token|api_key)" -- '*.py' '*.js' '*.yaml' '*.sql' '*.md'

# Search for connection strings
git grep -E "(postgres://|mysql://).*:.*@"

# Search for email addresses (might be test accounts)
git grep -E "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

# Check for hardcoded IPs
git grep -E "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b" -- '*.py' '*.yaml'
```

**Review Each Result:**
- Environment variables: ✅ Safe
- Documentation examples: ⚠️ Verify uses placeholders
- Comments: ⚠️ Check for exposed secrets
- Configuration templates: ✅ Safe if placeholders only

**Deliverable:** Security scan report with all findings addressed

---

## Day 2: Git History Cleanup

### Task 2.1: Backup Current Repository (30 minutes)

**Create Multiple Backups:**
```bash
# 1. Local filesystem backup
cd C:\users\emtol\repos
cp -r precog-repo precog-repo-backup-2025-10-28

# 2. Zip archive
tar -czf precog-repo-backup-2025-10-28.tar.gz precog-repo-backup-2025-10-28

# 3. Clone to external drive (if available)
# Copy to USB drive or cloud storage
```

**Verification:**
```bash
# Verify backup integrity
cd precog-repo-backup-2025-10-28
git log --oneline | head -10
git status
```

**Deliverable:** Verified backup with git history intact

---

### Task 2.2: Rewrite Git History (Option C) (2 hours)

**⚠️ WARNING:** This destroys all git history. Only proceed if:
- [ ] Backup verified complete
- [ ] No collaborators have cloned this repo
- [ ] You're comfortable starting fresh

**Procedure:**

```bash
cd C:\users\emtol\repos\precog-repo

# 1. Verify all security fixes are complete
git grep -i "suckbluefrogs"  # Should return NOTHING

# 2. Delete all git history
rm -rf .git

# 3. Verify .git is gone
ls -la .git  # Should error "No such file"

# 4. Reinitialize git repository
git init

# 5. Stage all files
git add .

# 6. Review what will be committed (verify no secrets)
git status

# 7. Create initial commit
git commit -m "Initial commit - Precog v0.6 Foundation

- Complete Phase 0, 0.5 documentation
- Database schema V1.7 with migrations 001-010
- Configuration system (YAML + .env.template)
- Security hardening complete
- 66/66 tests passing, 87% coverage

Previous git history removed for security reasons.
All secrets rotated and secured.

Co-authored-by: Claude <noreply@anthropic.com>"

# 8. Connect to remote (if exists)
git remote add origin https://github.com/yourusername/precog-repo.git

# 9. Force push to remote
git push -u --force origin main

# ALTERNATIVE: If remote doesn't exist yet, create it first on GitHub
```

**If Remote Repository Already Exists:**
```bash
# Delete and recreate on GitHub:
# 1. Go to https://github.com/yourusername/precog-repo/settings
# 2. Scroll to "Danger Zone"
# 3. Click "Delete this repository"
# 4. Create new repository with same name
# 5. Push fresh history
```

**Verification:**
```bash
# Verify history is clean
git log --all --oneline  # Should show only 1 commit

# Verify no secrets in history
git log --all --full-history -- "*password*"  # Should return nothing

# Search entire history
git grep "suckbluefrogs" $(git rev-list --all)  # Should return nothing
```

**Deliverable:** Clean git history with zero security issues

---

### Task 2.3: Rotate Compromised Credentials (1 hour)

**PostgreSQL Password Rotation:**

```bash
# 1. Connect to PostgreSQL as superuser
psql -U postgres

# 2. Change password
ALTER USER postgres WITH PASSWORD 'new_secure_password_here';

# 3. Exit psql
\q

# 4. Update .env file
# Edit C:\users\emtol\repos\precog-repo\.env
# Change: DB_PASSWORD=new_secure_password_here

# 5. Test connection
python scripts/test_db_connection.py

# 6. Run a test query
python scripts/test_db_simple.py
```

**Generate Strong Password:**
```python
import secrets
import string

def generate_password(length=20):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

print(generate_password())
```

**Deliverable:** New PostgreSQL password set and verified

---

## Day 3: Security Documentation & Prevention

### Task 3.1: Document Security Incident (1 hour)

**Create Incident Report:**

File: `docs/utility/SECURITY_INCIDENT_2025-10-28.md`

```markdown
# Security Incident Report - 2025-10-28

## Incident Summary
**Date Discovered:** 2025-10-28
**Severity:** HIGH
**Type:** Credential Exposure
**Status:** ✅ Resolved

## What Happened
Hardcoded PostgreSQL password found in 4 Python scripts committed to git repository:
- scripts/test_db_simple.py
- scripts/apply_migration_v1.5.py
- scripts/apply_migration_v1.4.py
- scripts/apply_schema.py

**Exposed Credential:** PostgreSQL password "suckbluefrogs"
**Exposure Duration:** [First commit date] - 2025-10-28 ([X] days)
**Repository Visibility:** Private (not publicly accessible)

## Root Cause
1. Scripts written without security review
2. No pre-commit hooks to detect hardcoded credentials
3. Phase Completion Protocol lacked security review step

## Resolution Actions Taken
1. ✅ All 4 scripts updated to use environment variables (os.getenv)
2. ✅ Git history rewritten to remove exposed password (Option C)
3. ✅ PostgreSQL password rotated
4. ✅ .gitignore updated to prevent future exposures
5. ✅ Security Review Checklist created
6. ✅ Phase Completion Protocol updated with Step 8 (Security Review)

## Prevention Measures
1. ✅ Security Review Checklist (docs/utility/SECURITY_REVIEW_CHECKLIST.md)
2. ✅ Phase Completion Protocol updated (Step 8)
3. [ ] Pre-commit hooks installed (optional, recommended)
4. [ ] Monthly security audits scheduled

## Lessons Learned
1. ALWAYS use environment variables for credentials
2. ALWAYS run security scan before committing
3. ALWAYS include security in phase completion
4. Consider using git-secrets or pre-commit hooks

## Sign-Off
**Resolved By:** User + Claude
**Date Resolved:** 2025-10-28
**Verification:** All tests passing, no secrets in repository
```

**Deliverable:** Security incident documented for future reference

---

### Task 3.2: Run Full Security Audit (1 hour)

**Using SECURITY_REVIEW_CHECKLIST.md:**

```bash
# 1. Automated scans
git grep -E "(password|secret|api_key|token)" -- '*.py' '*.js' '*.yaml' '*.sql' '*.md'
git grep -E "(postgres://|mysql://).*:.*@"
git ls-files | grep "\.env$"

# 2. Manual review of results
# Document each finding in audit report

# 3. Verify .gitignore works
git status --ignored

# 4. Check all scripts use environment variables
grep -r "os.getenv\|os.environ" scripts/
```

**Create Audit Report:**

File: `docs/utility/SECURITY_AUDIT_2025-10-28.md`

```markdown
# Security Audit Report - Phase 0.6

## Audit Date
2025-10-28

## Scope
- All Python scripts
- All configuration files
- All documentation
- Git repository history

## Findings

### Critical (None)
✅ No critical security issues found

### High (None)
✅ No high-severity issues found

### Medium (None)
✅ No medium-severity issues found

### Low (None)
✅ No low-severity issues found

## Summary
Repository is secure. All credentials properly externalized to environment variables.

## Recommendations
1. Consider installing git-secrets for automated prevention
2. Schedule monthly security audits
3. Add security review to all PR checklists (when collaborating)

## Sign-Off
**Auditor:** Claude + User
**Date:** 2025-10-28
**Status:** ✅ PASSED
```

**Deliverable:** Clean security audit with zero findings

---

### Task 3.3: Install Git Hooks (Optional, 1 hour)

**Pre-commit Hook to Block Secrets:**

File: `.git/hooks/pre-commit`

```bash
#!/bin/bash

echo "🔒 Running security pre-commit checks..."

# Check for hardcoded passwords
if git diff --cached | grep -E "(password|secret|api_key)\s*=\s*['\"][^'\"]{8,}['\"]"; then
    echo "❌ ERROR: Hardcoded credentials detected!"
    echo "Please use environment variables instead."
    echo "See docs/utility/SECURITY_REVIEW_CHECKLIST.md"
    exit 1
fi

# Check for .env file
if git diff --cached --name-only | grep -E "^\.env$"; then
    echo "❌ ERROR: Attempting to commit .env file!"
    echo "Only .env.template should be committed."
    exit 1
fi

# Check for private keys
if git diff --cached --name-only | grep -E "\.(pem|key|p12|pfx)$"; then
    echo "❌ ERROR: Attempting to commit private key file!"
    echo "Private keys should never be committed."
    exit 1
fi

echo "✅ Security checks passed"
exit 0
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

**Test the Hook:**
```bash
# Try to commit a file with hardcoded password (should fail)
echo 'password = "test123"' > test_bad.py
git add test_bad.py
git commit -m "Test"  # Should be blocked

# Clean up
rm test_bad.py
git reset
```

**Deliverable:** Working pre-commit hook (optional but recommended)

---

## Phase 0.6a Completion Checklist

- [ ] All 4 scripts updated to use environment variables
- [ ] .gitignore updated with comprehensive patterns
- [ ] Comprehensive security scan completed with zero critical findings
- [ ] Repository backup created and verified
- [ ] Git history rewritten (Option C)
- [ ] PostgreSQL password rotated and verified
- [ ] Security incident report created
- [ ] Full security audit completed and documented
- [ ] Pre-commit hooks installed (optional)

**Sign-Off Required Before Phase 0.6b**

---

# Phase 0.6b: Documentation Correction (Days 4-10)

**Priority:** 🟡 **HIGH**
**Duration:** 7 days
**Dependencies:** Phase 0.6a complete

## Overview

Fix all documentation inconsistencies identified, ensuring foundational documents accurately reflect the project state and supplementary documents are properly organized and referenced.

## Day 4: Supplementary Document Audit

### Task 4.1: Inventory All Supplementary Docs (2 hours)

**Current Supplementary Docs (from Glob):**
```
docs/supplementary/
├── Comprehensive sports win probabilities from three major betting markets.md
├── ODDS_RESEARCH_COMPREHENSIVE.md
├── REQUIREMENTS_AND_DEPENDENCIES_V1.0.md
├── ORDER_EXECUTION_ARCHITECTURE_ASSESSMENT_V1_0.md
├── PHASE_8_ADVANCED_EXECUTION_SPEC.md
├── PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md
├── PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md
├── PHASE_5_POSITION_MONITORING_SPEC_V1_0.md
├── USER_CUSTOMIZATION_STRATEGY_V1_0.md
├── VERSIONING_GUIDE.md
├── TRAILING_STOP_GUIDE.md
└── POSITION_MANAGEMENT_GUIDE.md
```

**Issues Identified:**
1. ❌ "Comprehensive sports win probabilities..." - Non-standard naming
2. ❌ Files with "PHASE_X" in name - Should be phase-agnostic
3. ❌ Inconsistent versioning (some V1_0, some V1.0)
4. ⚠️ Some docs in wrong folder (guides vs supplementary)

**Create Tracking Spreadsheet:**

| Current Name | Issues | Proposed New Name | Folder | Referenced In |
|--------------|--------|-------------------|--------|---------------|
| Comprehensive sports... | Non-standard name | SPORTS_PROBABILITIES_RESEARCH_V1.0.md | supplementary | None ❌ |
| ODDS_RESEARCH_COMPREHENSIVE.md | Good | Keep | supplementary | MASTER_REQUIREMENTS ✅ |
| ORDER_EXECUTION_ARCHITECTURE_ASSESSMENT_V1_0.md | Underscore in version | ORDER_EXECUTION_ARCHITECTURE_V1.0.md | supplementary | None ❌ |
| PHASE_8_ADVANCED_EXECUTION_SPEC.md | Phase in name | ADVANCED_EXECUTION_SPEC_V1.0.md | supplementary | None ❌ |
| PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md | Phase in name, underscore | EVENT_LOOP_ARCHITECTURE_V1.0.md | supplementary | None ❌ |
| PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md | Phase in name, underscore | EXIT_EVALUATION_SPEC_V1.0.md | supplementary | None ❌ |
| PHASE_5_POSITION_MONITORING_SPEC_V1_0.md | Phase in name, underscore | POSITION_MONITORING_SPEC_V1.0.md | supplementary | None ❌ |
| USER_CUSTOMIZATION_STRATEGY_V1_0.md | Underscore in version | USER_CUSTOMIZATION_STRATEGY_V1.0.md | supplementary | None ❌ |
| VERSIONING_GUIDE.md | Missing version | VERSIONING_GUIDE_V1.0.md | guides | MASTER_REQUIREMENTS ✅ |
| TRAILING_STOP_GUIDE.md | Missing version | TRAILING_STOP_GUIDE_V1.0.md | guides | MASTER_REQUIREMENTS ✅ |
| POSITION_MANAGEMENT_GUIDE.md | Missing version | POSITION_MANAGEMENT_GUIDE_V1.0.md | guides | MASTER_REQUIREMENTS ✅ |

**Deliverable:** Complete inventory with renaming plan

---

### Task 4.2: Rename and Reorganize Supplementary Docs (3 hours)

**Renaming Strategy:**
1. Remove "PHASE_X" prefixes
2. Standardize version format (V1.0 not V1_0)
3. Add version if missing
4. Move guides to `/docs/guides/` folder
5. Keep specs in `/docs/supplementary/`

**Git Operations:**
```bash
cd C:\users\emtol\repos\precog-repo\docs

# Rename with git mv (preserves history)
git mv "supplementary/Comprehensive sports win probabilities from three major betting markets.md" \
       "supplementary/SPORTS_PROBABILITIES_RESEARCH_V1.0.md"

git mv supplementary/ORDER_EXECUTION_ARCHITECTURE_ASSESSMENT_V1_0.md \
       supplementary/ORDER_EXECUTION_ARCHITECTURE_V1.0.md

git mv supplementary/PHASE_8_ADVANCED_EXECUTION_SPEC.md \
       supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md

git mv supplementary/PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md \
       supplementary/EVENT_LOOP_ARCHITECTURE_V1.0.md

git mv supplementary/PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md \
       supplementary/EXIT_EVALUATION_SPEC_V1.0.md

git mv supplementary/PHASE_5_POSITION_MONITORING_SPEC_V1_0.md \
       supplementary/POSITION_MONITORING_SPEC_V1.0.md

git mv supplementary/USER_CUSTOMIZATION_STRATEGY_V1_0.md \
       supplementary/USER_CUSTOMIZATION_STRATEGY_V1.0.md

# Move guides to correct folder
mkdir -p guides  # If doesn't exist

git mv supplementary/VERSIONING_GUIDE.md guides/VERSIONING_GUIDE_V1.0.md
git mv supplementary/TRAILING_STOP_GUIDE.md guides/TRAILING_STOP_GUIDE_V1.0.md
git mv supplementary/POSITION_MANAGEMENT_GUIDE.md guides/POSITION_MANAGEMENT_GUIDE_V1.0.md
```

**Update Internal Version Headers:**

For each renamed file, update the version header:
```markdown
---
**Version:** 1.0
**Last Updated:** 2025-10-28
**Status:** ✅ Current
**Filename Updated:** Renamed from PHASE_X_... to phase-agnostic name
---
```

**Deliverable:** All supplementary docs renamed and reorganized

---

## Day 5-6: Update Foundational Document References

### Task 5.1: Update MASTER_REQUIREMENTS References (3 hours)

**Current Issues:**
- Advanced Execution Spec insufficiently referenced (only mentioned in ADR-020)
- Not referenced at all in supplemental docs section

**Fixes Required:**

File: `docs/foundation/MASTER_REQUIREMENTS_V2.7.md`

**Section 2.4 Documentation Structure - Update:**
```markdown
### Supplementary Documents (in `docs/` folder):
1. `API_INTEGRATION_GUIDE_V1.0.md` - Detailed API specs
2. `DATABASE_SCHEMA_SUMMARY_V1.7.md` - Complete schema
3. `EDGE_DETECTION_SPEC_V1.0.md` - Mathematical formulas
4. `TESTING_STRATEGY_V1.1.md` - Test cases and coverage
5. `DEPLOYMENT_GUIDE_V1.0.md` - Setup instructions
6. `KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md` - Critical reference
7. `CONFIGURATION_GUIDE_V3.1.md` - YAML reference
8. `ARCHITECTURE_DECISIONS_V2.6.md` - Design rationale
9. `VERSIONING_GUIDE_V1.0.md` - Strategy versioning patterns
10. `TRAILING_STOP_GUIDE_V1.0.md` - Trailing stop implementation
11. `POSITION_MANAGEMENT_GUIDE_V1.0.md` - Position lifecycle
12. `REQUIREMENT_INDEX.md` - Requirement catalog
13. `ADR_INDEX.md` - Architecture decision index

### Supplementary Specifications:
14. `supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md` - Phase 5 execution strategies
15. `supplementary/EVENT_LOOP_ARCHITECTURE_V1.0.md` - Event loop design
16. `supplementary/EXIT_EVALUATION_SPEC_V1.0.md` - Exit condition evaluation
17. `supplementary/POSITION_MONITORING_SPEC_V1.0.md` - Position monitoring
18. `supplementary/ORDER_EXECUTION_ARCHITECTURE_V1.0.md` - Order execution
19. `supplementary/ODDS_RESEARCH_COMPREHENSIVE.md` - Historical odds
20. `supplementary/SPORTS_PROBABILITIES_RESEARCH_V1.0.md` - Sports probabilities
21. `supplementary/USER_CUSTOMIZATION_STRATEGY_V1.0.md` - User customization
```

**Add Requirement References:**

```markdown
## 5.X Advanced Execution (Phase 5b - Weeks 13-14)

**REQ-EXEC-006: Advanced Order Walking**

**Phase:** 5b
**Priority:** High
**Status:** 🔵 Planned
**Description:** Implement sophisticated price walking algorithms with urgency-based execution

**Reference:** See `supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md` for complete specification including:
- Price walking algorithm details
- Urgency-based execution strategies (CRITICAL, HIGH, MEDIUM, LOW)
- Order timeout management
- Execution success tracking
- Fill rate optimization strategies

**REQ-EXEC-007: Event Loop Integration**

**Phase:** 5
**Priority:** Critical
**Status:** 🔵 Planned
**Description:** Integrate position monitoring and exit execution into unified event loop

**Reference:** See `supplementary/EVENT_LOOP_ARCHITECTURE_V1.0.md` for complete architecture
```

**Version Bump:**
```markdown
**Version:** 2.8
**Changes in v2.8:**
- Added comprehensive references to supplementary specification documents
- Updated supplementary doc list with correct filenames and versions
- Added REQ-EXEC-006, REQ-EXEC-007 for advanced execution
- Reorganized supplementary docs section for clarity
```

**Deliverable:** MASTER_REQUIREMENTS V2.8 with complete supplementary doc references

---

### Task 5.2: Update ARCHITECTURAL_DECISIONS References (2 hours)

**Current Issues:**
- ADRs out of order
- Missing ADR numbers on some decisions
- Incomplete references to supplementary specs

**Fixes Required:**

File: `docs/foundation/ARCHITECTURE_DECISIONS_V2.6.md`

**Renumber All ADRs (Currently ADR-029-034, need to verify numbering):**

1. Create ADR inventory
2. Ensure sequential numbering
3. Add missing ADR numbers
4. Cross-reference to supplementary docs

**Add References to Supplementary Specs:**

```markdown
### ADR-035: Event Loop Architecture

**Decision #35**

**Decision:** Use single-threaded event loop with async/await for position monitoring

**Rationale:**
- Simplifies state management (no race conditions)
- Sufficient performance for <200 concurrent positions
- Python async/await well-suited for I/O-bound tasks

**Reference:** See `supplementary/EVENT_LOOP_ARCHITECTURE_V1.0.md` for detailed architecture

### ADR-036: Exit Evaluation Strategy

**Decision #36**

**Decision:** Evaluate all exit conditions on every price update, select highest priority

**Rationale:**
- Ensures no exit opportunity missed
- Priority hierarchy handles multiple triggers
- Simple to reason about and test

**Reference:** See `supplementary/EXIT_EVALUATION_SPEC_V1.0.md` for complete evaluation logic

### ADR-037: Advanced Order Walking

**Decision #37**

**Decision:** Implement multi-stage price walking with urgency-based escalation

**Rationale:**
- Balances execution speed vs. price improvement
- Urgency-based strategy adapts to market conditions
- Walking algorithm optimizes fill rates

**Reference:** See `supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md` for walking algorithm details
```

**Version Bump:**
```markdown
**Version:** 2.7
**Changes in v2.7:**
- Added ADR-035, ADR-036, ADR-037 for Phase 5 execution
- Renumbered all ADRs to be sequential
- Added cross-references to supplementary specification documents
- Fixed missing ADR numbers on historical decisions
```

**Deliverable:** ARCHITECTURE_DECISIONS V2.7 with complete ADR numbering and supplementary references

---

### Task 5.3: Update MASTER_INDEX (2 hours)

**Verify Every Document:**

1. Check if file exists at specified location
2. Verify version number matches filename
3. Ensure status is accurate (exists/planned/archived)
4. Update references to renamed files

**Example Updates:**

```markdown
## Supplementary Documents

Additional guides, references, and supporting documentation.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **VERSIONING_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 0.5 | Phases 4-9 | 🔴 Critical | **MOVED** from /supplementary/ - Immutable versioning patterns |
| **TRAILING_STOP_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 0.5 | Phases 1, 4, 5 | 🔴 Critical | **MOVED** from /supplementary/ - Trailing stop implementation |
| **POSITION_MANAGEMENT_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 0.5 | Phase 5 | 🔴 Critical | **MOVED** from /supplementary/ - Position lifecycle |
| **ADVANCED_EXECUTION_SPEC_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5 | Phase 5b | 🟡 High | **RENAMED** from PHASE_8_... - Order walking algorithms |
| **EVENT_LOOP_ARCHITECTURE_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5 | Phase 5 | 🟡 High | **RENAMED** from PHASE_5_... - Event loop design |
| **EXIT_EVALUATION_SPEC_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5 | Phase 5a | 🟡 High | **RENAMED** from PHASE_5_... - Exit condition logic |
| **POSITION_MONITORING_SPEC_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5 | Phase 5a | 🟡 High | **RENAMED** from PHASE_5_... - Monitoring strategies |
| **ORDER_EXECUTION_ARCHITECTURE_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5 | Phases 5-8 | 🟡 High | **RENAMED** from ..._ASSESSMENT_V1_0 - Execution architecture |
| **SPORTS_PROBABILITIES_RESEARCH_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 4 | Phase 4 | 🟢 Medium | **RENAMED** from "Comprehensive sports..." - Sports win probability research |
| **USER_CUSTOMIZATION_STRATEGY_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 10+ | Phase 10+ | 🟢 Medium | User-facing customization options |
```

**Version Bump:**
```markdown
**Version:** 2.6
**Changes in v2.6:**
- **REORGANIZATION**: Moved 3 guides from /supplementary/ to /guides/
- **RENAMING**: Renamed 7 supplementary docs for consistency (removed PHASE_ prefixes)
- Updated all document locations and versions
- Added "MOVED" and "RENAMED" notes for traceability
- Verified all documents exist at specified locations
```

**Deliverable:** MASTER_INDEX V2.6 with 100% accurate document inventory

---

## Day 7-8: Align Module Structure and Phase Tasks

### Task 7.1: Align Module Structure (3 hours)

**Issue:** MASTER_REQUIREMENTS shows different directory structure than actual implementation

**Current in MASTER_REQUIREMENTS V2.7:**
```
precog/
├── api_connectors/
├── platforms/
├── database/         # Documented as "database/"
├── analytics/
├── trading/
├── utils/
```

**Actual on Filesystem:**
```
precog-repo/
├── database/         # Exists
├── config/           # Exists
├── tests/            # Exists
├── scripts/          # Exists
├── docs/             # Exists
├── utils/            # Exists (has logger.py)
├── (other modules not yet created)
```

**Decision:**
- Phase 1 not yet implemented, so discrepancy is expected
- Update MASTER_REQUIREMENTS to clarify what EXISTS vs. PLANNED

**Fix in MASTER_REQUIREMENTS V2.8:**

```markdown
### 2.3 Module Structure

**LEGEND:**
- ✅ = Implemented (Phase 0-1)
- 🔵 = Planned (Phase 1+)
- 📁 = Directory exists but empty/partial

```
precog/
├── ✅ database/              # Phase 1 - Database operations (COMPLETE)
│   ├── ✅ connection.py
│   ├── ✅ crud_operations.py
│   ├── ✅ migrations/       # Migrations 001-010
│   └── ✅ seeds/            # NFL team Elo ratings
├── ✅ config/               # Phase 0 - Configuration files (COMPLETE)
│   ├── ✅ system.yaml
│   ├── ✅ trading.yaml
│   ├── ✅ position_management.yaml
│   ├── ✅ probability_models.yaml
│   ├── ✅ trade_strategies.yaml
│   ├── ✅ markets.yaml
│   └── ✅ data_sources.yaml
├── ✅ utils/                # Phase 1 - Utilities (PARTIAL)
│   ├── ✅ logger.py         # Complete
│   ├── 🔵 config_loader.py  # Planned Phase 1
│   ├── 🔵 retry_handler.py
│   ├── 🔵 pagination.py
│   └── 🔵 decimal_helpers.py
├── ✅ tests/                # Phase 1 - Test suite (66/66 passing)
│   ├── ✅ conftest.py
│   ├── ✅ test_database_connection.py
│   ├── ✅ test_crud_operations.py
│   ├── ✅ test_error_handling.py
│   └── ✅ test_logger.py
├── ✅ scripts/              # Phase 1 - Utility scripts
│   ├── ✅ test_db_connection.py
│   ├── ✅ test_db_simple.py
│   ├── ✅ apply_schema.py
│   ├── ✅ apply_migration_v1.4.py
│   └── ✅ apply_migration_v1.5.py
├── 🔵 api_connectors/       # Phase 1-2 (PLANNED)
│   ├── kalshi_client.py
│   ├── espn_client.py
│   ├── balldontlie_client.py
│   └── ...
├── 🔵 platforms/            # Phase 10 (PLANNED)
├── 🔵 analytics/            # Phase 4 (PLANNED)
├── 🔵 trading/              # Phase 5 (PLANNED)
├── 🔵 main.py               # Phase 1 (PLANNED)
└── ✅ docs/                 # Phase 0 (COMPLETE)
```

**Implementation Status:**
- **Phase 0-0.5:** Documentation, configuration, database schema ✅ COMPLETE
- **Phase 1 (Partial):** Database operations, tests, migrations ✅ COMPLETE
- **Phase 1 (Remaining):** API integration, CLI, managers ❌ NOT STARTED

**Deliverable:** Clear differentiation between implemented and planned modules

---

### Task 7.2: Align Phase Tasks (4 hours)

**Issue:** Tasks listed in MASTER_REQUIREMENTS don't match DEVELOPMENT_PHASES

**Example Discrepancy:**

**MASTER_REQUIREMENTS Phase 1:**
```
- Project setup with .env configuration
- Kalshi API client with HMAC-SHA256 authentication
- Database connection and ORM models
- CRUD operations
- CLI commands
```

**DEVELOPMENT_PHASES Phase 1:**
```
Week 1: Environment Setup
Week 1-2: Database Implementation
Week 2-4: Kalshi API Integration
Week 4: Configuration System
Week 5: CLI Development
Week 6: Testing
```

**Resolution:**

1. **Use DEVELOPMENT_PHASES as source of truth** (more detailed)
2. **Update MASTER_REQUIREMENTS to match**

**Updated MASTER_REQUIREMENTS Phase 1:**

```markdown
### Phase 1: Core Foundation (Weeks 1-6)

**Goal**: Establish project structure, Kalshi API connectivity, and account management.

**Key Requirements:**
- **REQ-API-001: Kalshi API Integration**
- **REQ-API-002: RSA-PSS Authentication (Kalshi)**
- **REQ-API-005: API Rate Limit Management**
- **REQ-API-006: API Error Handling**
- **REQ-DB-008: Database Connection Pooling**
- **REQ-CLI-001: CLI Command Framework** (NEW)
- **REQ-CLI-002: Balance Fetch Command** (NEW)
- **REQ-CLI-003: Positions Fetch Command** (NEW)
- **REQ-CLI-004: Fills Fetch Command** (NEW)
- **REQ-CLI-005: Settlements Fetch Command** (NEW)

**Key Deliverables**:

**Week 1: Environment Setup**
- ✅ Python 3.12+ virtual environment
- ✅ PostgreSQL 15+ database installation
- ✅ Git repository initialization
- ✅ IDE configuration
- ✅ Install dependencies from requirements.txt

**Weeks 1-2: Database Implementation (COMPLETE)**
- ✅ All tables created with proper indexes
- ✅ SCD Type 2 versioning logic implemented
- ✅ Alembic migration scripts (001-010)
- ✅ CRUD operations in `database/crud_operations.py`
- ✅ Database connection pool in `database/connection.py`
- ✅ 66/66 tests passing, 87% coverage

**Weeks 2-4: Kalshi API Integration (NOT STARTED)**
- [ ] RSA-PSS authentication implementation
- [ ] Token refresh logic (30-minute cycle)
- [ ] REST endpoints: markets, events, series, balance, positions, orders
- [ ] Error handling and exponential backoff retry logic
- [ ] Rate limiting (100 req/min throttle)
- [ ] Parse `*_dollars` fields as DECIMAL
- [ ] API client with `api_connectors/kalshi_client.py`

**Week 4: Configuration System (PARTIAL)**
- ✅ YAML configuration files created
- [ ] YAML loader with validation (`utils/config_loader.py`)
- [ ] Environment variable integration
- [ ] Config override mechanism

**Week 5: CLI Development (NOT STARTED)**
- [ ] CLI framework with Typer
- [ ] `main.py fetch-balance` command
- [ ] `main.py fetch-positions` command
- [ ] `main.py fetch-fills` command
- [ ] `main.py fetch-settlements` command
- [ ] Type hints for all commands

**Week 6: Testing & Validation (PARTIAL)**
- ✅ Database tests (66/66 passing)
- [ ] API client unit tests (mock responses)
- [ ] Integration tests (live demo API)
- [ ] CLI command tests
- [ ] >80% code coverage maintained

**Critical**: All prices must use `Decimal` type and be stored as DECIMAL(10,4)

**Documentation**:
- `API_INTEGRATION_GUIDE_V1.0.md` (Kalshi section)
- `DEVELOPER_ONBOARDING.md`
- `KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md`
- `CLI_DEVELOPMENT_GUIDE.md` (to be created)
```

**Add Missing Requirements:**

```markdown
## 3.X CLI Requirements (Phase 1)

**REQ-CLI-001: CLI Command Framework**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: Implement CLI using Typer framework with type hints and help text

**REQ-CLI-002: Balance Fetch Command**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: Fetch and store account balance from Kalshi API

**REQ-CLI-003: Positions Fetch Command**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: Fetch and store open positions from Kalshi API

**REQ-CLI-004: Fills Fetch Command**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: Fetch and store trade fills from Kalshi API

**REQ-CLI-005: Settlements Fetch Command**
- Phase: 1
- Priority: High
- Status: 🔵 Planned
- Description: Fetch and store market settlements from Kalshi API
```

**Deliverable:** MASTER_REQUIREMENTS and DEVELOPMENT_PHASES fully aligned

---

## Day 9: ADR Renumbering and Organization

### Task 9.1: Audit All ADRs (2 hours)

**Create ADR Inventory:**

```bash
# Extract all ADR references from ARCHITECTURE_DECISIONS
grep -E "ADR-[0-9]+" docs/foundation/ARCHITECTURE_DECISIONS_V2.6.md | sort -u
```

**Expected Output:**
```
ADR-001: [Decision name]
ADR-002: Price Precision - DECIMAL(10,4)
...
ADR-034: SCD Type 2 Completion
```

**Check for Issues:**
1. Missing ADR numbers (gaps in sequence)
2. Duplicate ADR numbers
3. ADRs out of chronological order
4. Decisions without ADR numbers

**Create Tracking Sheet:**

| Current ADR | Decision Name | Section | Issues | Proposed ADR |
|-------------|---------------|---------|--------|--------------|
| None | Technology Stack | Section X | Missing ADR | ADR-001 |
| ADR-002 | Price Precision | Section Y | ✅ Good | ADR-002 |
| ... | ... | ... | ... | ... |

**Deliverable:** Complete ADR inventory with renumbering plan

---

### Task 9.2: Renumber and Reorder ADRs (3 hours)

**Strategy:**
1. Assign ADR-001 to ADR-XXX sequentially
2. Order chronologically (Phase 0 → Phase 10)
3. Group related decisions together
4. Update ADR_INDEX.md to match

**Renumbering Process:**

File: `docs/foundation/ARCHITECTURE_DECISIONS_V2.7.md`

1. Create new section at top with ADR numbering guide
2. Renumber all decisions sequentially
3. Ensure all cross-references updated
4. Add "See ADR-XXX" references throughout

**Example Structure:**

```markdown
# Architecture & Design Decisions

## ADR Numbering Guide

| ADR | Decision | Phase | Status |
|-----|----------|-------|--------|
| ADR-001 | Technology Stack | 0 | ✅ Complete |
| ADR-002 | Price Precision (DECIMAL) | 0 | ✅ Complete |
| ADR-003 | Database Versioning (SCD Type 2) | 0 | ✅ Complete |
| ... | ... | ... | ... |
| ADR-037 | Advanced Order Walking | 5 | 🔵 Planned |

**Total ADRs:** 37
**Complete:** 29
**Planned:** 8

---

## Critical Design Decisions

### ADR-001: Technology Stack

**Decision #1**
**Phase:** 0
**Status:** ✅ Complete

**Decision:** Use Python 3.12, PostgreSQL 15+, SQLAlchemy ORM

**Rationale:** ...

---

### ADR-002: Price Precision - DECIMAL(10,4) for All Prices

**Decision #2**
**Phase:** 0
**Status:** ✅ Complete

**Decision:** ALL price fields use `DECIMAL(10,4)` data type

**Rationale:** ...
**Reference:** KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md

[Continue for all 37 ADRs...]
```

**Deliverable:** All ADRs numbered sequentially and ordered logically

---

### Task 9.3: Update ADR_INDEX (1 hour)

**File:** `docs/foundation/ADR_INDEX.md`

**Update to match renumbered ADRs:**

```markdown
# Architecture Decision Records (ADR) Index

---
**Version:** 1.1
**Last Updated:** 2025-10-28
**Status:** ✅ Current
**Total ADRs:** 37
**Changes in v1.1:**
- Complete ADR renumbering (sequential 001-037)
- Added ADRs for Phase 5 execution (ADR-035, ADR-036, ADR-037)
- Updated all cross-references
- Added phase and status columns
---

## Purpose

This index provides a quick reference to all Architecture Decision Records (ADRs) in the Precog project. For complete details, see `ARCHITECTURE_DECISIONS_V2.7.md`.

---

## ADR Categories

### Phase 0: Foundation (ADR-001 to ADR-017)
Core architectural decisions for project foundation.

| ADR | Decision | Status | Priority |
|-----|----------|--------|----------|
| ADR-001 | Technology Stack | ✅ Complete | 🔴 Critical |
| ADR-002 | Price Precision (DECIMAL) | ✅ Complete | 🔴 Critical |
| ADR-003 | Database Versioning (SCD Type 2) | ✅ Complete | 🔴 Critical |
| ADR-004 | Configuration Management (YAML) | ✅ Complete | 🔴 Critical |
| ADR-005 | API Authentication (RSA-PSS) | ✅ Complete | 🔴 Critical |
... [Continue listing all]

### Phase 0.5: Foundation Enhancement (ADR-018 to ADR-023)
Versioning, trailing stops, position management.

| ADR | Decision | Status | Priority |
|-----|----------|--------|----------|
| ADR-018 | Immutable Versions | ✅ Complete | 🔴 Critical |
| ADR-019 | Strategy Versioning | ✅ Complete | 🔴 Critical |
| ADR-020 | Model Versioning | ✅ Complete | 🔴 Critical |
| ADR-021 | Trailing Stop Loss | ✅ Complete | 🟡 High |
... [Continue listing all]

### Phase 1: Schema Completion (ADR-024 to ADR-034)
Database schema finalization and Elo preparation.

### Phase 5: Position Monitoring & Execution (ADR-035 to ADR-037)
Event loop, exit evaluation, order walking.

---

## ADR Cross-Reference

**By Topic:**

**Database & Schema:**
- ADR-002 (Price Precision)
- ADR-003 (SCD Type 2)
- ADR-009 (Surrogate Keys)
- ADR-029 (Elo Data Source)
- ADR-030 (Elo Storage)
- ADR-032 (Markets PRIMARY KEY)
- ADR-033 (External ID Traceability)
- ADR-034 (SCD Type 2 Completion)

**Versioning:**
- ADR-018 (Immutable Versions)
- ADR-019 (Strategy Versioning)
- ADR-020 (Model Versioning)

**Position Management:**
- ADR-021 (Trailing Stops)
- ADR-036 (Exit Evaluation)
- ADR-035 (Event Loop)

**Execution:**
- ADR-037 (Order Walking)
- ADR-005 (API Authentication)

**Multi-Platform:**
- ADR-010 (Platform Abstraction)

---

## Quick Reference

**Most Referenced ADRs:**
1. ADR-002 (Price Precision) - Referenced in every module
2. ADR-003 (Database Versioning) - Referenced in all CRUD operations
3. ADR-018 (Immutable Versions) - Referenced in Phase 4-10

**Recently Added:**
- ADR-035 (Event Loop) - Phase 5a
- ADR-036 (Exit Evaluation) - Phase 5a
- ADR-037 (Order Walking) - Phase 5b

---

**END OF ADR INDEX V1.1**
```

**Deliverable:** ADR_INDEX V1.1 with complete cross-references

---

## Day 10: Final Documentation Validation

### Task 10.1: Cross-Reference Validation (2 hours)

**Check All Document References:**

```bash
# Find all markdown file references
grep -r "\.md" docs/foundation/*.md | grep -v "^#"

# Check each reference exists
# Create validation script
```

**Validation Script:**

File: `scripts/validate_doc_references.py`

```python
"""
Validate all markdown document references in foundation docs.
"""
import os
import re
from pathlib import Path

def find_md_references(file_path):
    """Extract all .md file references from a markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: *.md or path/*.md
    pattern = r'([A-Z_]+(?:_V\d+\.\d+)?\.md|[a-z_/]+/[A-Z_]+(?:_V\d+\.\d+)?\.md)'
    references = re.findall(pattern, content)
    return references

def validate_references():
    """Validate all markdown references in foundation docs."""
    repo_root = Path(r"C:\users\emtol\repos\precog-repo")
    foundation_docs = repo_root / "docs" / "foundation"

    all_references = {}

    # Find all references
    for doc in foundation_docs.glob("*.md"):
        refs = find_md_references(doc)
        if refs:
            all_references[doc.name] = refs

    # Validate each reference
    broken_refs = []
    for doc_name, refs in all_references.items():
        for ref in refs:
            # Try to find the file
            possible_paths = [
                repo_root / "docs" / "foundation" / ref,
                repo_root / "docs" / "guides" / ref,
                repo_root / "docs" / "supplementary" / ref,
                repo_root / "docs" / ref,
                repo_root / ref
            ]

            if not any(p.exists() for p in possible_paths):
                broken_refs.append((doc_name, ref))

    # Report results
    if broken_refs:
        print(f"❌ Found {len(broken_refs)} broken references:\n")
        for doc, ref in broken_refs:
            print(f"  {doc} → {ref}")
        return False
    else:
        print(f"✅ All {sum(len(refs) for refs in all_references.values())} references valid")
        return True

if __name__ == "__main__":
    success = validate_references()
    exit(0 if success else 1)
```

**Run Validation:**
```bash
python scripts/validate_doc_references.py
```

**Fix All Broken References**

**Deliverable:** All document references validated and corrected

---

### Task 10.2: Update DOCUMENT_MAINTENANCE_LOG (1 hour)

**Log All Changes Made in Phase 0.6:**

File: `docs/utility/DOCUMENT_MAINTENANCE_LOG.md`

```markdown
## 2025-10-28: Phase 0.6 Documentation Correction

### Changes Made

#### Security
1. Created `SECURITY_REVIEW_CHECKLIST.md` v1.0
2. Created `SECURITY_INCIDENT_2025-10-28.md`
3. Created `SECURITY_AUDIT_2025-10-28.md`
4. Updated `Handoff_Protocol_V1.0.md` → V1.1 (added Step 8: Security Review)

#### Supplementary Documents Reorganized
1. Renamed 7 supplementary docs (removed PHASE_ prefixes)
   - `PHASE_8_ADVANCED_EXECUTION_SPEC.md` → `ADVANCED_EXECUTION_SPEC_V1.0.md`
   - `PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md` → `EVENT_LOOP_ARCHITECTURE_V1.0.md`
   - `PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md` → `EXIT_EVALUATION_SPEC_V1.0.md`
   - `PHASE_5_POSITION_MONITORING_SPEC_V1_0.md` → `POSITION_MONITORING_SPEC_V1.0.md`
   - `ORDER_EXECUTION_ARCHITECTURE_ASSESSMENT_V1_0.md` → `ORDER_EXECUTION_ARCHITECTURE_V1.0.md`
   - `"Comprehensive sports..."` → `SPORTS_PROBABILITIES_RESEARCH_V1.0.md`
   - `USER_CUSTOMIZATION_STRATEGY_V1_0.md` → `USER_CUSTOMIZATION_STRATEGY_V1.0.md`

2. Moved 3 guides from `/supplementary/` to `/guides/`:
   - `VERSIONING_GUIDE.md` → `guides/VERSIONING_GUIDE_V1.0.md`
   - `TRAILING_STOP_GUIDE.md` → `guides/TRAILING_STOP_GUIDE_V1.0.md`
   - `POSITION_MANAGEMENT_GUIDE.md` → `guides/POSITION_MANAGEMENT_GUIDE_V1.0.md`

#### Foundation Documents Updated
1. `MASTER_REQUIREMENTS_V2.7.md` → V2.8
   - Added comprehensive supplementary doc references
   - Added REQ-CLI-001 through REQ-CLI-005 (CLI requirements)
   - Updated module structure to show implemented vs. planned
   - Aligned Phase 1 deliverables with DEVELOPMENT_PHASES

2. `ARCHITECTURE_DECISIONS_V2.6.md` → V2.7
   - Renumbered all ADRs sequentially (ADR-001 to ADR-037)
   - Added ADR-035 (Event Loop), ADR-036 (Exit Evaluation), ADR-037 (Order Walking)
   - Updated all cross-references to supplementary specs
   - Fixed out-of-order ADRs

3. `ADR_INDEX.md` v1.0 → V1.1
   - Updated to match ARCHITECTURE_DECISIONS V2.7 renumbering
   - Added cross-reference section
   - Added phase categorization

4. `MASTER_INDEX_V2.5.md` → V2.6
   - Updated all document locations after reorganization
   - Added "MOVED" and "RENAMED" notes for traceability
   - Verified 100% accuracy of document inventory

### Upstream Impact
- All references to supplementary docs now correct
- DEVELOPMENT_PHASES aligned with MASTER_REQUIREMENTS
- Module structure clarified (implemented vs. planned)

### Downstream Impact
- Phase 1 implementation can proceed with clear requirements
- CLI requirements now documented
- All ADR references consistent

### Validation
- ✅ All document references validated
- ✅ No broken links
- ✅ All files exist at specified locations
- ✅ Version numbers consistent
```

**Deliverable:** Complete change log for Phase 0.6

---

### Task 10.3: Create Phase 0.6 Summary (1 hour)

**File:** `docs/sessions/PHASE_0.6_COMPLETION_SUMMARY.md`

```markdown
# Phase 0.6 Completion Summary

---
**Completion Date:** 2025-10-28 (or actual date)
**Duration:** [X] days
**Status:** ✅ Complete
---

## Overview

Phase 0.6 successfully addressed critical security vulnerabilities, corrected documentation inconsistencies, and prepared the project for Phase 1 implementation.

## Achievements

### 🔒 Security Hardening
- ✅ Removed hardcoded passwords from 4 scripts
- ✅ Cleaned git history (fresh start)
- ✅ Rotated PostgreSQL password
- ✅ Created comprehensive security checklist
- ✅ Updated Phase Completion Protocol with security review step
- ✅ Installed pre-commit hooks (optional)

### 📚 Documentation Correction
- ✅ Renamed 7 supplementary docs for consistency
- ✅ Reorganized 3 guides to correct folder
- ✅ Updated MASTER_REQUIREMENTS V2.7 → V2.8
- ✅ Updated ARCHITECTURE_DECISIONS V2.6 → V2.7
- ✅ Updated ADR_INDEX v1.0 → V1.1
- ✅ Updated MASTER_INDEX V2.5 → V2.6
- ✅ Aligned module structure documentation
- ✅ Aligned phase tasks between docs
- ✅ Added 5 missing CLI requirements

### ✅ Validation
- ✅ All document references validated
- ✅ No broken links
- ✅ Security audit passed
- ✅ 8-step phase completion assessment passed

## Metrics

**Documents Updated:** 8 foundation docs
**Documents Created:** 3 security docs
**Documents Renamed:** 7 supplementary docs
**Documents Moved:** 3 guides
**Security Issues Fixed:** 4 critical
**ADRs Renumbered:** 37 total
**New Requirements Added:** 5 CLI requirements

## Phase Completion Assessment

### Step 1: Deliverable Completeness - ✅ PASS
All planned deliverables complete.

### Step 2: Internal Consistency - ✅ PASS
All documents use consistent terminology and versions.

### Step 3: Dependency Verification - ✅ PASS
All cross-references validated.

### Step 4: Quality Standards - ✅ PASS
All docs have version headers, consistent formatting.

### Step 5: Testing & Validation - ✅ PASS
Validation scripts created and passed.

### Step 6: Gaps & Risks - ✅ PASS
No critical gaps. Some nice-to-haves deferred to Phase 1.5.

### Step 7: Archive & Version Management - ✅ PASS
All versions updated, MASTER_INDEX accurate.

### Step 8: Security Review - ✅ PASS
Zero security issues remaining.

## Ready for Phase 1

✅ **Foundation is secure, organized, and ready for API implementation.**

---

**Sign-Off:**
**User:** _______________
**Date:** _______________
```

**Deliverable:** Phase 0.6 completion documented

---

## Phase 0.6b Completion Checklist

- [ ] All supplementary docs inventoried
- [ ] 7 supplementary docs renamed
- [ ] 3 guides moved to correct folder
- [ ] MASTER_REQUIREMENTS updated to V2.8
- [ ] ARCHITECTURE_DECISIONS updated to V2.7
- [ ] ADR_INDEX updated to V1.1
- [ ] MASTER_INDEX updated to V2.6
- [ ] Module structure documentation aligned
- [ ] Phase tasks aligned between documents
- [ ] 5 CLI requirements added
- [ ] All ADRs renumbered sequentially
- [ ] All document references validated
- [ ] DOCUMENT_MAINTENANCE_LOG updated
- [ ] Phase 0.6 completion summary created

**Sign-Off Required Before Phase 0.6c**

---

# Phase 0.6c: Validation & Handoff (Days 11-14)

**Priority:** 🟢 **MEDIUM**
**Duration:** 4 days
**Dependencies:** Phase 0.6a, 0.6b complete

## Day 11-12: Comprehensive Validation

### Task 11.1: Run Full 8-Step Assessment (3 hours)

**Follow Handoff_Protocol_V1.1.md:**

1. **Deliverable Completeness (10 min)**
   - [ ] All Phase 0.6 deliverables complete
   - [ ] Security docs created
   - [ ] Documentation corrections complete

2. **Internal Consistency (5 min)**
   - [ ] All docs reference same versions
   - [ ] Terminology consistent
   - [ ] No contradictions

3. **Dependency Verification (5 min)**
   - [ ] All cross-references valid
   - [ ] No broken links
   - [ ] Phase 1 can start with current docs

4. **Quality Standards (5 min)**
   - [ ] All docs have version headers
   - [ ] Consistent formatting
   - [ ] Professional presentation

5. **Testing & Validation (3 min)**
   - [ ] Validation scripts passing
   - [ ] Database tests still passing (66/66)
   - [ ] No regressions

6. **Gaps & Risks (2 min)**
   - [ ] No critical gaps
   - [ ] Risks documented
   - [ ] Mitigation plans in place

7. **Archive & Version Management (5 min)**
   - [ ] All versions bumped correctly
   - [ ] MASTER_INDEX accurate
   - [ ] DOCUMENT_MAINTENANCE_LOG updated

8. **Security Review (5 min)**
   - [ ] Zero security issues
   - [ ] Pre-commit hooks working
   - [ ] Credentials secured

**Create:** `PHASE_0.6_COMPLETION_REPORT.md` with assessment results

**Deliverable:** Complete 8-step assessment with all steps passing

---

### Task 11.2: Regression Testing (2 hours)

**Verify No Breakage:**

```bash
# 1. Database tests still pass
python -m pytest tests/ -v

# Expected: 66/66 passing

# 2. Database connection works
python scripts/test_db_connection.py

# 3. CRUD operations work
python scripts/test_db_simple.py

# 4. No hardcoded passwords
git grep -i "password\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py'

# Expected: Only os.getenv lines

# 5. Security scan clean
python scripts/validate_doc_references.py
```

**If Any Failures:**
1. Investigate root cause
2. Fix immediately
3. Re-run all tests
4. Document in completion report

**Deliverable:** All tests passing, no regressions

---

## Day 13: Perplexity AI Review Preparation

### Task 13.1: Create Architectural Summary (2 hours)

**Purpose:** Prepare concise summary for Perplexity AI review

**File:** `docs/sessions/ARCHITECTURE_SUMMARY_FOR_REVIEW.md`

```markdown
# Precog Architecture Summary (For External Review)

---
**Version:** 1.0
**Date:** 2025-10-28
**Purpose:** Summary for Perplexity AI architectural review
---

## Project Overview

**Precog** is a modular Python system for identifying and executing positive expected value (EV+) trades on prediction markets (initially Kalshi, expanding to Polymarket).

**Current Status:** Phase 1 (50% complete)
- ✅ Database schema complete (V1.7, migrations 001-010)
- ✅ Configuration system complete (7 YAML files)
- ✅ Tests passing (66/66, 87% coverage)
- ❌ API integration not started
- ❌ CLI not started

## Core Architecture

### 1. Technology Stack
- **Language:** Python 3.12
- **Database:** PostgreSQL 15+ with DECIMAL(10,4) precision
- **ORM:** SQLAlchemy
- **Testing:** pytest (80%+ coverage target)
- **Configuration:** YAML + .env

### 2. Data Flow
```
Kalshi API → api_connectors → database (SCD Type 2)
ESPN API → api_connectors → game_states → analytics
game_states + historical_data → probability_calculator → edges
edges + versioned_strategy → trading_engine → orders
positions + trailing_stops → position_manager → exits
```

### 3. Key Architectural Patterns

**Pattern 1: Dual Versioning**
- **SCD Type 2** for frequently-changing data (markets, positions, game_states)
  - Uses `row_current_ind` flag
  - Historical queries supported

- **Immutable Versions** for strategies and models (v1.0, v1.1, v2.0)
  - Config NEVER changes
  - Trade attribution to exact versions
  - A/B testing integrity

**Pattern 2: Decimal Precision**
- ALL prices use Python `Decimal` type
- ALL database columns use `DECIMAL(10,4)`
- NEVER use float for prices
- Parse Kalshi `*_dollars` fields

**Pattern 3: Position Management**
- Dynamic trailing stops (JSONB state)
- 10 exit conditions with priority hierarchy
- Urgency-based execution (CRITICAL, HIGH, MEDIUM, LOW)
- Price walking algorithm

**Pattern 4: Platform Abstraction** (Phase 10)
- Base platform interface
- Platform-specific adapters (Kalshi, Polymarket)
- Cross-platform price comparison

### 4. Database Schema (25 tables)

**Core Tables:**
- `markets` - Binary outcomes (yes/no)
- `positions` - Open trades with trailing stops
- `trades` - Executed orders (append-only)
- `edges` - EV+ opportunities
- `strategies` - Versioned trading strategies (immutable)
- `probability_models` - Versioned ML models (immutable)

**Key Design Decisions:**
- Surrogate PRIMARY KEYs (id SERIAL) for SCD Type 2 tables
- UNIQUE constraint on (business_key WHERE row_current_ind = TRUE)
- Foreign keys for trade attribution (strategy_id, model_id)
- JSONB for flexible metadata (trailing_stop_state, trade_metadata)

### 5. Risk Management
- Kelly Criterion position sizing (fractional: 0.25 for NFL)
- Circuit breakers (5 consecutive losses, 10% daily loss)
- Position limits ($1,000/market, $10,000 total)
- Stop losses (-15%) with trailing
- Compliance checks before every trade

## Key Requirements

**Functional:**
1. Fetch and store market data from Kalshi API
2. Calculate true win probabilities using versioned models
3. Identify EV+ opportunities (min 5% after fees)
4. Execute trades using versioned strategies
5. Monitor positions with dynamic trailing stops
6. Exit positions based on priority hierarchy

**Non-Functional:**
1. 99%+ uptime during market hours
2. <5s data latency (API → database)
3. 100% price precision (no rounding errors)
4. >95% execution success rate
5. >80% test coverage

## Phased Implementation

**Phase 0-0.5:** Documentation and foundation ✅ COMPLETE
**Phase 1:** Database + API + CLI (50% complete)
**Phase 1.5:** Managers (strategy, model, position) - PLANNED
**Phase 2-3:** Market data + live stats - PLANNED
**Phase 4:** Probability calculation + edge detection - PLANNED
**Phase 5:** Position monitoring + exit management - PLANNED
**Phase 6-7:** Multi-sport expansion - PLANNED
**Phase 8-9:** Non-sports markets + advanced ML - PLANNED
**Phase 10:** Multi-platform (Polymarket) - PLANNED

## Critical Design Constraints

1. **Immutability:** Strategy and model configs NEVER change after creation
2. **Precision:** ALL prices must use Decimal type, no exceptions
3. **Versioning:** ALL trades must link to exact strategy and model versions
4. **Security:** NO credentials in code, only environment variables
5. **Testing:** 80%+ coverage required before production

## Questions for Architectural Review

1. **Versioning Approach:** Is dual versioning pattern (SCD Type 2 + immutable versions) over-engineered or appropriately separated concerns?

2. **Database Schema:** Are 25 tables with complex relationships appropriate, or should we simplify?

3. **Position Management:** Is 10-exit-condition priority hierarchy too complex for Phase 1? Should we start simpler?

4. **Platform Abstraction:** Is Phase 10 multi-platform planning premature? Should we optimize for Kalshi first?

5. **Testing Strategy:** Is 80% coverage sufficient for a financial system? Should we require 90%+?

6. **Risk Management:** Are Kelly fractions and circuit breakers appropriate for prediction markets?

7. **Technology Choices:** Is Python + PostgreSQL + SQLAlchemy appropriate for real-time trading system? Should we consider async/await more extensively?

8. **Decimal Precision:** Is DECIMAL(10,4) over-engineering for a system that might only need 2-3 decimal places?

## References

**Key Documents:**
- `MASTER_REQUIREMENTS_V2.8.md` - Complete requirements
- `ARCHITECTURE_DECISIONS_V2.7.md` - All 37 ADRs
- `DATABASE_SCHEMA_SUMMARY_V1.7.md` - Complete schema
- `PROJECT_OVERVIEW_V1.3.md` - System architecture

---

**Please provide:**
1. Validation of architectural approach
2. Identification of potential issues or anti-patterns
3. Recommendations for improvements
4. Assessment of alignment with project goals
```

**Deliverable:** Architectural summary ready for external review

---

## Day 14: Final Documentation and Handoff

### Task 14.1: Create CLAUDE.md (Will be created separately - see below)

### Task 14.2: Update PROJECT_STATUS (1 hour)

**File:** `docs/utility/PROJECT_STATUS.md`

Update to reflect Phase 0.6 completion:

```markdown
## Current Phase: Phase 1 (Ready to Continue)

**Last Completed:** Phase 0.6 (Documentation Correction & Security Hardening)
**Status:** ✅ Phase 0.6 Complete
**Next:** Phase 1 API Integration

### Phase 0.6 Summary

**Completed:**
- ✅ Security hardening (credentials secured, git history cleaned)
- ✅ Documentation correction (7 docs renamed, 3 moved, 4 updated)
- ✅ ADR renumbering (37 ADRs sequential)
- ✅ MASTER_INDEX accuracy verification (100%)
- ✅ Cross-reference validation (all links working)

**Key Achievements:**
- Zero security issues remaining
- Foundation documents 100% consistent
- Ready for Phase 1 implementation

### Phase 1 Status: 50% Complete

**Completed:**
- ✅ Database schema V1.7 (migrations 001-010)
- ✅ CRUD operations (87% coverage)
- ✅ Configuration system (7 YAML files)
- ✅ Tests passing (66/66)

**Remaining:**
- [ ] Kalshi API client (RSA-PSS authentication)
- [ ] CLI commands (Typer framework)
- [ ] Config loader (YAML + .env)
- [ ] API rate limiting
- [ ] Integration tests (live demo API)

**Estimated Completion:** [X] weeks from today

---

## Immediate Next Steps

1. **Continue Phase 1:** Implement Kalshi API client
2. **Review Perplexity Feedback:** Incorporate architectural recommendations
3. **Begin Phase 1.5 Planning:** Managers (strategy, model, position)
```

**Deliverable:** PROJECT_STATUS updated for current state

---

### Task 14.3: Final Git Commit (1 hour)

**Commit All Phase 0.6 Changes:**

```bash
cd C:\users\emtol\repos\precog-repo

# Review all changes
git status

# Stage all changes
git add .

# Create comprehensive commit
git commit -m "Phase 0.6 Complete: Documentation Correction & Security Hardening

## Security Hardening (Phase 0.6a)
- Remove hardcoded passwords from 4 scripts
- Clean git history (fresh start via Option C)
- Rotate PostgreSQL credentials
- Create SECURITY_REVIEW_CHECKLIST.md v1.0
- Update Handoff_Protocol v1.0 → v1.1 (add Step 8: Security Review)
- Add comprehensive .gitignore patterns

## Documentation Correction (Phase 0.6b)
- Rename 7 supplementary docs (remove PHASE_ prefixes, standardize versions)
- Move 3 guides to /docs/guides/ folder
- Update MASTER_REQUIREMENTS v2.7 → v2.8 (add CLI reqs, align with phases)
- Update ARCHITECTURE_DECISIONS v2.6 → v2.7 (renumber all 37 ADRs)
- Update ADR_INDEX v1.0 → v1.1 (match ADR renumbering)
- Update MASTER_INDEX v2.5 → v2.6 (100% accuracy verification)

## Validation & Handoff (Phase 0.6c)
- Complete 8-step phase completion assessment (all steps ✅ PASS)
- Validate all document cross-references (zero broken links)
- Regression testing (66/66 tests passing)
- Create Phase 0.6 completion report
- Prepare architectural summary for external review
- Update PROJECT_STATUS

## Deliverables
- Zero security issues remaining
- Foundation documentation 100% consistent and accurate
- All ADRs numbered sequentially (ADR-001 to ADR-037)
- Complete traceability (MOVED/RENAMED notes in MASTER_INDEX)
- Ready for Phase 1 API implementation

## Metrics
- Documents updated: 8 foundation docs
- Documents created: 3 security docs + 2 validation docs
- Documents renamed: 7 supplementary docs
- Documents moved: 3 guides
- Security issues resolved: 4 critical
- Test coverage: 87.16% (66/66 passing)

Co-authored-by: Claude <noreply@anthropic.com>"

# Push to remote
git push origin main
```

**Deliverable:** Phase 0.6 changes committed to git

---

## Phase 0.6 Final Completion Checklist

### Phase 0.6a: Security Hardening
- [ ] All hardcoded passwords removed
- [ ] Git history rewritten (clean)
- [ ] PostgreSQL password rotated
- [ ] Security checklist created
- [ ] Phase Completion Protocol updated
- [ ] .gitignore comprehensive
- [ ] Security audit passed (zero issues)

### Phase 0.6b: Documentation Correction
- [ ] 7 supplementary docs renamed
- [ ] 3 guides moved to correct folder
- [ ] MASTER_REQUIREMENTS updated to V2.8
- [ ] ARCHITECTURE_DECISIONS updated to V2.7
- [ ] ADR_INDEX updated to V1.1
- [ ] MASTER_INDEX updated to V2.6
- [ ] Module structure aligned
- [ ] Phase tasks aligned
- [ ] CLI requirements added
- [ ] All ADRs renumbered

### Phase 0.6c: Validation & Handoff
- [ ] 8-step assessment complete (all ✅)
- [ ] Regression testing passed
- [ ] All document references validated
- [ ] Architectural summary created
- [ ] Phase 0.6 completion report created
- [ ] PROJECT_STATUS updated
- [ ] Final git commit made

### Sign-Off

**Phase 0.6 Complete:** ☐ Yes  ☐ No

**Ready for Phase 1:** ☐ Yes  ☐ No

**User Approval:**
**Name:** _______________
**Date:** _______________
**Signature:** _______________

---

## What's Next: Phase 1 Continuation

**Immediate Tasks:**
1. **Review Perplexity AI architectural feedback**
2. **Create corrective plan** for any valid concerns
3. **Begin Kalshi API client implementation**
4. **Implement CLI commands with Typer**
5. **Add config loader** (YAML + .env integration)

**Phase 1 Timeline:**
- Weeks 1-2: Kalshi API client (RSA-PSS auth, endpoints, rate limiting)
- Weeks 3-4: CLI commands (balance, positions, fills, settlements)
- Weeks 5-6: Integration testing and Phase 1 completion

---

**END OF PHASE 0.6 CORRECTIVE PLAN V1.0**
