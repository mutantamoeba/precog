# Handoff Protocol

---
**Version:** 1.0  
**Last Updated:** 2025-10-12  
**Status:** ✅ Active - Reference Document  
**Purpose:** Comprehensive guide for session management, token budgeting, handoff process, and phase completion
---

## 🎯 Overview

**This protocol defines** the complete system for managing multi-session work on Precog, including:
- Version control standards
- Token management and checkpoints
- Session handoff process
- Document maintenance workflows
- Phase completion assessment
- Project knowledge strategy

**Result**: Efficient 3-upload system (<10 min session startup), comprehensive context preservation, zero data loss.

---

# Part 1: Version Control Standards

## Version Control Rules

**Follow VERSION_HEADERS_GUIDE_V2.1.md for complete details.**

### Major Documents (Filename Versioning)
- **Format:** `DOCUMENT_NAME_VX.Y.md`
- **Examples:** `MASTER_INDEX_V2.1.md`, `CONFIGURATION_GUIDE_V2.0.md`
- **When to use:** Reference docs, guides, specifications (updated monthly or less)
- **Versioning:** 
  - Major version (X): Significant restructure, breaking changes
  - Minor version (Y): Additions, clarifications, non-breaking updates

### Living Documents (Header Only Versioning)
- **Format:** `DOCUMENT_NAME.md` (no version in filename)
- **Examples:** `PROJECT_STATUS.md`, `DOCUMENT_MAINTENANCE_LOG.md`
- **When to use:** Status trackers, logs updated every session
- **Versioning:** Header shows "Living Document (header only vX.Y)"

### Session Documents (Session Number = Version)
- **Format:** `SESSION_N_HANDOFF.md` (session number is the version)
- **Examples:** `SESSION_7_HANDOFF.md`, `SESSION_8_HANDOFF.md`
- **When to use:** Per-session handoffs
- **Versioning:** Session number serves as version identifier

### Standard Headers

**Major Document Header:**
```markdown
---
**Version:** X.Y  
**Last Updated:** YYYY-MM-DD  
**Status:** [✅ Current / ⚠️ Needs Update / 🗄️ Archived]  
**Changes in vX.Y:** [Brief summary of changes in this version]
---
```

**Living Document Header:**
```markdown
---
**Version:** Living Document (header only vX.Y)  
**Last Updated:** YYYY-MM-DD  
**Status:** [✅ Active / ⚠️ Under Review]  
**Changes in vX.Y:** [What changed in this header version]
---
```

---

# Part 2: Token Management System

## Token Budget

| Metric | Value | Percentage | Checkpoint |
|--------|-------|------------|------------|
| **Total Budget** | 190,000 tokens | 100% | - |
| **Checkpoint 1** | 60,000 tokens | 32% | 🟢 Early progress |
| **Checkpoint 2** | 90,000 tokens | 47% | 🟡 Mid-session update |
| **Checkpoint 3** | 120,000 tokens | 63% | 🟠 Second backup |
| **Checkpoint 4** | 150,000 tokens | 79% | 🔴 Wrap-up mode |
| **Warning Zone** | 170,000 tokens | 89% | ⚠️ Critical warning |
| **Auto-End** | 180,000 tokens | 95% | 🛑 Session terminates |

## Checkpoint Actions

### 🟢 Checkpoint 1: 60K Tokens (32%)
**Status:** Early progress check  
**Actions:**
- ✅ Log current progress internally
- ✅ Note completed deliverables
- ✅ Continue work normally

**No document updates required.**

---

### 🟡 Checkpoint 2: 90K Tokens (47%)
**Status:** Mid-session backup  
**Actions:**
- ✅ Update PROJECT_STATUS.md with current state
- ✅ Update DOCUMENT_MAINTENANCE_LOG.md with changes so far
- ✅ Create draft SESSION_N_HANDOFF.md
- ✅ Verify all new documents saved

**Output Format:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟡 CHECKPOINT 2 REACHED: 90K TOKENS (47%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTOMATIC UPDATES PERFORMED:
✅ PROJECT_STATUS.md updated
✅ DOCUMENT_MAINTENANCE_LOG.md updated
✅ Draft handoff created

📊 Session Progress:
   Completed: [X] items
   Remaining: [Y] items
   
💾 All work backed up to this point.
Status: Continue work, checkpoints will resume.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 🟠 Checkpoint 3: 120K Tokens (63%)
**Status:** Second comprehensive backup  
**Actions:**
- ✅ Update PROJECT_STATUS.md with latest state
- ✅ Update DOCUMENT_MAINTENANCE_LOG.md with all changes
- ✅ Update draft handoff with complete progress
- ✅ Calculate remaining capacity

**Output Format:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟠 CHECKPOINT 3 REACHED: 120K TOKENS (63%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTOMATIC UPDATES PERFORMED:
✅ PROJECT_STATUS.md updated (2nd update)
✅ DOCUMENT_MAINTENANCE_LOG.md updated (2nd update)
✅ Handoff draft updated with full progress

📊 Token Analysis:
   Used: 120K / 190K (63%)
   Remaining: 70K tokens
   Estimated capacity: [X more documents]

💾 All work backed up to this point.
Status: Beginning to prioritize critical items.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 🔴 Checkpoint 4: 150K Tokens (79%)
**Status:** Final working checkpoint - WRAP-UP MODE BEGINS  
**Actions:**
- ✅ Final update to PROJECT_STATUS.md
- ✅ Final update to DOCUMENT_MAINTENANCE_LOG.md
- ✅ Complete SESSION_N_HANDOFF.md (finalize all sections)
- 🚫 **Stop starting new major documents**
- ✅ Focus only on completing in-progress items

**Output Format:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 CHECKPOINT 4 REACHED: 150K TOKENS (79%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ ENTERING WRAP-UP MODE ⚠️

AUTOMATIC UPDATES PERFORMED:
✅ PROJECT_STATUS.md final update
✅ DOCUMENT_MAINTENANCE_LOG.md final update
✅ SESSION_N_HANDOFF.md completed

🚫 NO NEW DOCUMENTS STARTED
✅ Completing only: [in-progress items]

📊 Token Analysis:
   Used: 150K / 190K (79%)
   Remaining: 40K tokens
   
💾 ALL work fully backed up.
Status: Wrap-up mode - finishing current tasks only.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### ⚠️ Warning Zone: 170K Tokens (89%)
**Status:** Critical - immediate wrap-up required  
**Actions:**
- 🚨 Alert user immediately
- ✅ Verify all handoff documents complete
- 🚫 **Stop ALL new work**
- ✅ Create emergency backup handoff if needed

**Output Format:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ WARNING ZONE: 170K TOKENS (89%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 CRITICAL: APPROACHING TOKEN LIMIT 🚨

AUTOMATIC ACTIONS TAKEN:
✅ All handoff documents verified complete
✅ Emergency backup created
✅ Work stopped

📊 Token Status:
   Used: 170K / 190K (89%)
   Remaining: 20K tokens (~10 min of conversation)
   
⚠️ Session will AUTO-END at 180K tokens (10K away)

Status: Ready for next session, handoff complete.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 🛑 Auto-End: 180K Tokens (95%)
**Status:** Automatic session termination  
**Actions:**
- 🛑 Stop all work immediately
- ✅ Final handoff verification
- ✅ Create final session summary
- ✅ Provide clear next steps

**Output Format:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 AUTO-END TRIGGERED: 180K TOKENS (95%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SESSION ENDING AUTOMATICALLY IN 3... 2... 1...

✅ ALL WORK SAVED AND DOCUMENTED

📋 Handoff Documents Ready:
   ✅ PROJECT_STATUS.md
   ✅ DOCUMENT_MAINTENANCE_LOG.md
   ✅ SESSION_N_HANDOFF.md

📊 Final Token Count: 180K / 190K (95%)

🎯 Next Session Plan:
   [Clear instructions for continuation]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SESSION COMPLETE - START NEW SESSION TO CONTINUE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Token Estimation Guide

**Average token costs:**
- Small YAML file (~500 lines): ~3,000 tokens
- Medium document (2,000 words): ~3,500 tokens
- Large document (5,000 words): ~8,000 tokens
- Comprehensive guide (10,000 words): ~15,000 tokens
- Code discussion (100 lines): ~1,500 tokens
- Planning/strategy discussion: ~5,000 tokens

**Safe work estimates by remaining tokens:**

| Remaining | Can Safely Complete |
|-----------|---------------------|
| 70K tokens | 2-3 large docs or 5-7 YAMLs |
| 40K tokens | 1 large doc or 2-3 YAMLs |
| 20K tokens | 1 small doc or wrap-up only |
| 10K tokens | Handoff finalization only |

---

# Part 3: Session Handoff Process

## The 3-Upload System

**Every session starts with uploading exactly 3 documents:**

1. **PROJECT_STATUS.md** - Current state, stats, next goals
2. **DOCUMENT_MAINTENANCE_LOG.md** - Change history with impacts
3. **SESSION_[N-1]_HANDOFF.md** - Last session's handoff

**Result:** Full context in ~5 minutes (vs. 30 minutes with old system)

**Note:** Project knowledge is referenced automatically (no upload needed)

## Session Workflow

### Session Start (5 minutes)
```markdown
1. Upload 3 documents (STATUS + LOG + HANDOFF)
2. Claude auto-references project knowledge
3. Review next goals from PROJECT_STATUS
4. Clarify any questions
5. Begin work with full context
```

### During Session (Automatic Checkpoints)
```markdown
1. Work normally
2. Checkpoint at 60K → log progress
3. Continue work
4. Checkpoint at 90K → update docs
5. Continue work
6. Checkpoint at 120K → update docs
7. Continue work (prioritize critical)
8. Checkpoint at 150K → wrap-up mode
9. Complete only in-progress items
10. Warning at 170K → stop all work
11. Auto-end at 180K → session ends
```

### Session End (10 minutes)
```markdown
1. Verify all checkpoints completed
2. Review final SESSION_N_HANDOFF.md
3. Confirm next session plan in PROJECT_STATUS.md
4. User downloads new/updated documents
5. Update project knowledge if needed (major docs only)
```

## Document Roles

### PROJECT_STATUS.md (Living - Updated Every Session)
**Contains:**
- Quick stats (phase %, blockers, token budget)
- What is Precog (1-para description)
- Last session summary (3-5 bullets)
- Next goals (Option A/B with hours)
- User preferences (Kelly, time, philosophy)
- Token budget tracking table
- Critical technical reminders
- Essential docs list
- Quick start guide
- Session history

**NOT in Project Knowledge** (too dynamic)

---

### SESSION_N_HANDOFF.md (Per-Session - Created at End)
**Contains:**
- What happened (3-5 bullets)
- Changes table (Created/Updated/Archived)
- Next plan (Option A/B with tasks and hours)
- Blockers/reminders (3-5 max)
- Session checklist (uploads/updates)

**NOT in Project Knowledge** (session-specific)

---

### DOCUMENT_MAINTENANCE_LOG.md (Living - Append-Only)
**Contains:**
- Session-by-session major updates only
- Created/Updated/Archived tables per session
- Upstream/downstream impact analysis
- Maintenance statistics

**NOT in Project Knowledge** (too dynamic)

---

### Handoff_Protocol_V1.0.md (This Document - Reference Only)
**Contains:**
- Version control standards
- Token management system
- Session handoff process
- Document maintenance workflows
- Phase completion assessment
- Project knowledge strategy

**IN Project Knowledge** (stable reference, updated rarely)

---

# Part 4: Document Maintenance Workflows

## Mini-Assessment at Session End

**Before completing handoff, verify:**

✅ **Upstream OK?**
- [ ] Have all upstream dependencies been considered?
- [ ] Have we incorporated all relevant research/decisions?
- [ ] Are we building on solid foundations?

✅ **Downstream Updated?**
- [ ] Have all affected documents been updated?
- [ ] Have YAML configs been propagated?
- [ ] Have code stubs been adjusted?
- [ ] Are phase dependencies still correct?

✅ **Impacts Considered?**
- [ ] Has DOCUMENT_MAINTENANCE_LOG been updated?
- [ ] Have upstream/downstream impacts been logged?
- [ ] Has MASTER_INDEX been updated (if docs added/removed)?
- [ ] Have version headers been applied correctly?

## Impact Tracking Guidelines

### Upstream Analysis (What caused this change?)
- Research completion (e.g., historical odds study)
- User request (e.g., streamline handoff)
- Bug/issue discovery (e.g., decimal pricing)
- Dependency (e.g., API changes)
- Design evolution (e.g., multi-platform)

### Downstream Analysis (What must update as result?)
- **Direct dependencies:** Docs that reference this doc
- **Config propagation:** YAMLs that must reflect changes
- **Code implications:** Modules that must implement updates
- **Process changes:** Workflows that must adapt
- **Documentation:** Other docs that must stay consistent

### Example Log Entry
```markdown
| Document | Change | Impact | Status |
|----------|--------|--------|--------|
| odds_models.yaml | Added historical_lookup | Upstream: ODDS_RESEARCH merge; Downstream: trade_strategies (min_edge>0.05), position_mgmt (health_score weight 0.50), markets (gap_flag filter) | ✅ v1.1 |
```

## Archiving Process

**When to archive:**
- Document replaced by newer version
- Document merged into consolidated doc
- Document no longer relevant to current phase

**How to archive:**
1. Move to `/archive/v1.0/` (or appropriate version folder)
2. Add entry to DOCUMENT_MAINTENANCE_LOG "Archived" section
3. Update MASTER_INDEX with 🗄️ status
4. Ensure no active docs reference archived doc

---

# Part 5: Phase Completion Assessment

## When to Run Assessment

**Trigger:** At end of each phase (e.g., Phase 0 → Phase 1 transition)

**Time Required:** ~30 minutes

**Purpose:** Ensure phase is truly complete before advancing

## 7-Step Assessment Process

### Step 1: Deliverable Completeness (10 minutes)

**Checklist:**
- [ ] All planned documents created?
- [ ] All code stubs implemented?
- [ ] All configuration files complete?
- [ ] All schemas finalized?

**Questions:**
- What was planned for this phase? (Check DEVELOPMENT_PHASES.md)
- What actually exists? (Check MASTER_INDEX.md)
- Any gaps between plan and reality?

---

### Step 2: Internal Consistency (5 minutes)

**Checklist:**
- [ ] All documents reference same tech stack versions?
- [ ] All YAMLs follow same DECIMAL precision?
- [ ] All docs use consistent terminology?
- [ ] No contradictions between documents?

**Common Issues:**
- Decimal format inconsistency (0.05 vs 0.0500)
- Different package versions in requirements lists
- Terminology drift (e.g., "edge" vs "alpha" vs "EV")

---

### Step 3: Dependency Verification (5 minutes)

**Checklist:**
- [ ] Phase prerequisites met?
- [ ] All referenced external docs exist?
- [ ] All internal cross-references valid?
- [ ] No circular dependencies?

**Questions:**
- Does Phase N+1 depend on everything from Phase N?
- Are all "See X.md" references valid?
- Can you follow any reference chain without dead ends?

---

### Step 4: Quality Standards (5 minutes)

**Checklist:**
- [ ] All docs have version headers?
- [ ] All code has inline documentation?
- [ ] All configs have comments?
- [ ] All schemas have descriptions?
- [ ] Consistent formatting throughout?

**Standards:**
- Version headers follow VERSION_HEADERS_GUIDE_V2.1.md
- Code follows style guide (Black for Python)
- YAMLs have descriptive comments
- Tables are properly formatted

---

### Step 5: Testing & Validation (3 minutes)

**Checklist:**
- [ ] Sample data provided for next phase?
- [ ] Test scripts included?
- [ ] Validation functions defined?
- [ ] Edge cases documented?

**Examples:**
- Phase 0: Sample YAML values, test database connection script
- Phase 1: Mock API responses, test authentication flow
- Phase 4: Historical data sample, odds calculation test

---

### Step 6: Gaps & Risks (2 minutes)

**Checklist:**
- [ ] Any known technical debt?
- [ ] Any assumptions documented?
- [ ] Any TODOs flagged?
- [ ] Any risks to next phase?

**Common Gaps:**
- Placeholder values in configs
- Stubbed functions without implementation plans
- Missing extension points for planned features
- No sample/test data for next phase to use

---

### Step 7: Archive & Version Management (5 minutes)

**Checklist:**
- [ ] Old versions archived properly?
- [ ] Version numbers bumped correctly?
- [ ] All major docs have versions in filenames?
- [ ] Living docs have header-only versions?
- [ ] MASTER_INDEX updated?
- [ ] DOCUMENT_MAINTENANCE_LOG updated?

**Actions:**
- Move v1.0 docs to `/archive/v1.0/` when creating v1.1
- Update MASTER_INDEX with new versions
- Log all changes in MAINTENANCE_LOG with upstream/downstream

---

## Assessment Completion

**After completing 7 steps:**

1. Create `PHASE_[N]_COMPLETION_REPORT.md`
2. Document all gaps found
3. Create action plan for gaps
4. Get user sign-off before advancing
5. Update PROJECT_STATUS.md to next phase

**Report Format:**
```markdown
# Phase [N] Completion Report

## Assessment Date
YYYY-MM-DD

## Overall Status
[✅ Complete / ⚠️ Minor Gaps / 🔴 Major Gaps]

## Step-by-Step Results
[7 steps with ✅/⚠️/🔴 for each]

## Gaps Identified
[List with severity]

## Recommended Actions
[Before advancing to Phase N+1]

## Sign-Off
User approval: [Date]
```

---

# Part 6: Project Knowledge Strategy

## Core Rule

**Project Knowledge = Stable Reference Documents** (change monthly or less)  
**Fresh Uploads = Dynamic Status & Recent Changes** (change every session)

## ✅ IN Project Knowledge

**Foundation Documents:**
- MASTER_INDEX_V2.X.md (navigation)
- PROJECT_OVERVIEW_V1.X.md (architecture)
- MASTER_REQUIREMENTS_V2.X.md (requirements)
- ARCHITECTURE_DECISIONS_V2.X.md (design rationale)

**Technical References:**
- CONFIGURATION_GUIDE_V2.X.md (config patterns)
- DATABASE_SCHEMA_SUMMARY_V1.X.md (schema)
- API_INTEGRATION_GUIDE_V1.X.md (API docs)
- KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md (critical reference)

**Planning & Process:**
- DEVELOPMENT_PHASES_V1.X.md (roadmap)
- GLOSSARY_V1.X.md (terminology)
- Handoff_Protocol_V1.X.md (this document)

**Update Frequency:** Monthly or when major versions created

---

## ❌ NOT in Project Knowledge

**Living Status Documents:**
- PROJECT_STATUS.md (changes every session)
- DOCUMENT_MAINTENANCE_LOG.md (appended every session)

**Session Documents:**
- SESSION_N_HANDOFF.md (session-specific)
- Any document with "CURRENT_STATE" in name

**Temporary/Working Documents:**
- Draft documents
- Session notes
- Comparison tables
- Gap analyses

**Configuration Files:**
- .env files (contain secrets)
- YAML configs with actual values

**Why excluded:** These change too frequently; uploading fresh ensures latest version is used

---

## Decision Tree

```
Is document a status tracker? → ❌ NEVER in PK
Is document a session handoff? → ❌ NEVER in PK
Is document updated every session? → ❌ NEVER in PK
Is document a reference guide AND stable? → ✅ YES, in PK
Is document >20KB AND used frequently? → ✅ YES, in PK (caching benefit)
Is document < 3 months old? → ⚠️ Wait until stable
```

---

## Managing Project Knowledge

### When to Add
- Major document reaches v1.0 and is stable
- Document referenced frequently across sessions
- Document >20KB and worth caching
- Document won't change for 1+ month

### When to Update
- Major version bump (v1.0 → v2.0)
- Significant restructure or content addition
- Breaking changes to referenced patterns
- After completing full phase

### When to Remove
- Document deprecated/archived
- Document replaced by newer version
- Document no longer referenced
- Content merged into another PK document

---

# Part 7: Resolving Inconsistencies

## Threshold Consistency

**Standard thresholds across protocol:**
- **Warn:** 150K tokens (79%) - Draft handoff
- **Prep:** 170K tokens (89%) - Stop all work
- **End:** 180K tokens (95%) - Auto-end session

**All documents must use these exact thresholds.**

## User Preferences Integration

**Where to capture:**
- PROJECT_STATUS.md: "User Preferences" section
- Includes: Kelly fraction, time commitment, philosophy, risk tolerance

**Where to reference:**
- Handoff_Protocol (this doc): Points to PROJECT_STATUS for prefs
- YAMLs: Use conservative values matching prefs
- Code stubs: Include comments referencing prefs

## Document Impact Logging

**Required in:**
- DOCUMENT_MAINTENANCE_LOG.md: Upstream/downstream per change
- Handoff_Protocol: Mini-assessment at session end
- SESSION_N_HANDOFF: Critical findings that impact future

**Mandatory checks:**
- Upstream OK? (foundations solid?)
- Downstream updated? (propagation complete?)
- Impacts logged? (maintenance log entry added?)

---

# Part 8: Uniform Upload System

## The Trio System

**Every session uploads exactly these 3:**

1. **PROJECT_STATUS.md**
   - Living document (header only version)
   - Updated at Checkpoints 2, 3, 4
   - Contains current stats, last summary, next goals

2. **DOCUMENT_MAINTENANCE_LOG.md**
   - Living document (header only version)
   - Appended at Checkpoints 2, 3, 4
   - Contains change history with impacts

3. **SESSION_[N-1]_HANDOFF.md**
   - Last session's handoff
   - Not updated in current session
   - Provides immediate context

**Benefits:**
- Consistent startup every session
- <5 minute context loading
- No ambiguity about what to upload
- Full context from 3 files + project knowledge

## What NOT to Upload

❌ Individual YAMLs (unless actively editing)
❌ Code files (unless actively editing)
❌ Archive documents
❌ Template documents
❌ Old session handoffs (only upload N-1)

---

# Appendix: Quick Reference

## Session Start Checklist (5 min)
- [ ] Upload PROJECT_STATUS.md
- [ ] Upload DOCUMENT_MAINTENANCE_LOG.md
- [ ] Upload SESSION_[N-1]_HANDOFF.md
- [ ] Review next goals in STATUS
- [ ] Clarify any questions
- [ ] Begin work

## Session End Checklist (10 min)
- [ ] Complete SESSION_N_HANDOFF.md
- [ ] Update PROJECT_STATUS.md (final)
- [ ] Update DOCUMENT_MAINTENANCE_LOG.md (final)
- [ ] Run mini-assessment (Upstream/Downstream/Impacts)
- [ ] User downloads new/updated docs
- [ ] Update project knowledge (major docs only)

## Token Checkpoints Summary
- 60K (32%): 🟢 Log progress
- 90K (47%): 🟡 Update docs + draft handoff
- 120K (63%): 🟠 Update docs + full handoff
- 150K (79%): 🔴 Wrap-up mode + finalize handoff
- 170K (89%): ⚠️ Stop all work
- 180K (95%): 🛑 Auto-end

## Phase Completion Steps
1. Deliverable completeness (10 min)
2. Internal consistency (5 min)
3. Dependency verification (5 min)
4. Quality standards (5 min)
5. Testing & validation (3 min)
6. Gaps & risks (2 min)
7. Archive & version mgmt (5 min)

**Total: ~30 minutes per phase**

---

**END OF HANDOFF PROTOCOL**

**Reference this document** at session start for complete workflow guidance.  
**Update only when:** Process changes, major version bump, or protocol improvements needed.  
**Current version:** v1.0 (stable, in project knowledge)
