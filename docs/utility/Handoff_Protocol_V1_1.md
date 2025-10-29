# Handoff Protocol

---
**Version:** 1.1  
**Last Updated:** 2025-10-15  
**Status:** ✅ Current  
**Changes in v1.1:** Added Part 7 (Context Management Strategy) to address conversation length limits discovered in Session 7-8
---

## Purpose

**Establish comprehensive session management protocols** including version control, token monitoring, handoff procedures, phase assessment, and context management to ensure seamless work continuity across sessions.

**Key Update (v1.1):** Added context management strategies to extend session length and prevent early termination due to context complexity limits.

---

## Table of Contents

1. [Version Control Standards](#part-1-version-control-standards)
2. [Token Budget Monitoring](#part-2-token-budget-monitoring)
3. [Session Handoff Process](#part-3-session-handoff-process)
4. [End-of-Session Workflow](#part-4-end-of-session-workflow)
5. [Phase Completion Assessment](#part-5-phase-completion-assessment)
6. [Project Knowledge Strategy](#part-6-project-knowledge-strategy)
7. **[Context Management Strategy](#part-7-context-management-strategy)** ← NEW in v1.1

---

## Part 1: Version Control Standards

### Document Versioning Rules

**Follow VERSION_HEADERS_GUIDE_V2.1.md for complete standards.**

**Quick Reference:**
- Major docs: Include version in filename (`DOC_VX.Y.md`)
- Living docs: Version in header only (`DOC.md`)
- Session handoffs: Session number is version (`SESSION_N_HANDOFF.md`)

**Version Incrementing:**
- Major (X.0): Fundamental redesign, breaking changes
- Minor (X.Y): New sections, significant updates

**Version Header Template:**
```markdown
---
**Version:** X.Y  
**Last Updated:** YYYY-MM-DD  
**Status:** [✅ Current / ⚠️ Needs Update / 📝 Draft / 🗄️ Archived]  
**Changes in vX.Y:** [Brief description]  
---
```

### Archiving Process

**When creating new version:**
1. Archive old version to `/archive/vX.Y/`
2. Create new file with incremented version
3. Update MASTER_INDEX_VX.Y.md
4. Log in DOCUMENT_MAINTENANCE_LOG.md
5. Update cross-references in other docs

---

## Part 2: Token Budget Monitoring

### Token Budget Overview

| Checkpoint | Tokens | Percentage | Status | Action |
|-----------|--------|------------|--------|--------|
| **Start** | 0K | 0% | 🟢 Fresh | Begin work |
| **Checkpoint 1** | 60K | 32% | 🟢 Normal | Log progress |
| **Checkpoint 2** | 90K | 47% | 🟡 Mid-session | Update docs |
| **Checkpoint 3** | 120K | 63% | 🟠 Monitoring | Update docs |
| **Checkpoint 4** | 150K | 79% | 🔴 Wrap-up | Complete items |
| **Warning** | 170K | 89% | ⚠️ Critical | Stop work |
| **Auto-End** | 180K | 95% | 🛑 End | Auto-terminate |

### Automatic Checkpoint Actions

**At each checkpoint:**
1. Update PROJECT_STATUS.md with current progress
2. Update DOCUMENT_MAINTENANCE_LOG.md with changes
3. Create/update session handoff draft
4. Verify all new files saved
5. Calculate remaining capacity

**Wrap-up Mode (150K+):**
- Stop starting new major documents
- Complete only in-progress items
- Ensure all handoff docs current
- Prepare for graceful end

**Warning Zone (170K+):**
- Alert user immediately
- Verify handoff complete
- Stop ALL new work
- Create emergency backup if needed

---

## Part 3: Session Handoff Process

### The Trio System

**At START of each session, upload these 3 files:**
1. **PROJECT_STATUS.md** - Current state, goals, blockers
2. **DOCUMENT_MAINTENANCE_LOG.md** - Recent changes with impacts
3. **SESSION_N_HANDOFF.md** - Previous session summary

**Claude auto-references project knowledge** (no upload needed)

**Total startup time:** ~5 minutes to full context

### Handoff Document Format

Use **SESSION_HANDOFF_TEMPLATE.md** for consistent structure.

**Essential sections:**
- What happened (3-5 bullets)
- Documents changed (created/updated/archived)
- Critical findings
- Next session plan (options + recommendation)
- Blockers & dependencies
- Token budget summary
- Success indicators

**Keep to 1-2 pages maximum**

---

## Part 4: End-of-Session Workflow

### Mini-Assessment Checklist

**Run before completing each session:**

#### Version Headers Applied?
- [ ] All new documents have proper version headers
- [ ] All updated documents have incremented versions
- [ ] All headers follow VERSION_HEADERS_GUIDE format

#### Filename Versioning Correct?
- [ ] Major docs have version in filename (vX.Y)
- [ ] Living docs have NO version in filename
- [ ] Session handoffs use session number only

#### Archiving Complete?
- [ ] Old versions moved to `/archive/vX.Y/`
- [ ] MASTER_INDEX updated with new versions
- [ ] No broken references to old versions

#### Changes Logged?
- [ ] DOCUMENT_MAINTENANCE_LOG updated
- [ ] Upstream/downstream impacts noted
- [ ] MASTER_INDEX reflects current state

#### Handoff Ready?
- [ ] SESSION_N_HANDOFF.md created
- [ ] PROJECT_STATUS.md updated
- [ ] DOCUMENT_MAINTENANCE_LOG.md current
- [ ] All deliverables documented

**Time required:** ~10 minutes

---

## Part 5: Phase Completion Assessment

### 7-Step Assessment Protocol

**Run at the end of each phase before starting next phase:**

#### 1. Deliverable Completeness (10 min)
- [ ] All planned documents for phase created?
- [ ] All documents have correct version headers?
- [ ] All documents have correct filenames (with versions)?
- [ ] All cross-references working?
- [ ] All code examples tested?

#### 2. Internal Consistency (5 min)
- [ ] Terminology consistent across all docs? (check GLOSSARY)
- [ ] Technical details match? (e.g., decimal pricing everywhere)
- [ ] Design decisions aligned?
- [ ] No contradictions between documents?
- [ ] Version numbers logical and sequential?

#### 3. Dependency Verification (5 min)
- [ ] All document cross-references valid?
- [ ] All external dependencies identified?
- [ ] Next phase blockers identified?
- [ ] API contracts documented?
- [ ] Data flow diagrams current?

#### 4. Quality Standards (5 min)
- [ ] Spell check completed?
- [ ] Grammar check completed?
- [ ] Format consistency (headers, bullets, tables)?
- [ ] Code syntax highlighting correct?
- [ ] Links all working?

#### 5. Testing & Validation (3 min)
- [ ] Sample data provided where relevant?
- [ ] Configuration examples included?
- [ ] Error handling documented?
- [ ] Edge cases identified?

#### 6. Gaps & Risks (2 min)
- [ ] Technical debt documented?
- [ ] Known issues logged?
- [ ] Future improvements identified?
- [ ] Risk mitigation strategies noted?

#### 7. Archive & Version Management (5 min)
- [ ] Old versions archived properly?
- [ ] MASTER_INDEX updated?
- [ ] PROJECT_STATUS updated?
- [ ] MAINTENANCE_LOG complete?

**Total time:** ~35 minutes per phase

**Output:** Create `PHASE_N_COMPLETION_REPORT.md` with assessment results

---

## Part 6: Project Knowledge Strategy

### What Goes IN Project Knowledge

**Criteria:** Stable reference documents, change monthly or less

**Currently IN Project Knowledge:**
- MASTER_INDEX_V2.1.md (navigation)
- PROJECT_OVERVIEW_V1.2.md (architecture)
- MASTER_REQUIREMENTS_V2.1.md (requirements)
- ARCHITECTURE_DECISIONS_V2.1.md (design rationale)
- CONFIGURATION_GUIDE_V2.1.md (config patterns)
- DATABASE_SCHEMA_SUMMARY_V1.1.md (schema)
- API_INTEGRATION_GUIDE_V1.0.md (API docs)
- KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md (critical reference)
- DEVELOPMENT_PHASES_V1.1.md (roadmap)
- GLOSSARY_V1.0.md (terminology)
- Handoff_Protocol_V1.1.md (this file - process reference)
- CLAUDE_CODE_STRATEGY_V1.0.md (implementation strategy)

### What Stays OUT of Project Knowledge

**Criteria:** Change frequently, uploaded fresh each session

**Never in Project Knowledge:**
- PROJECT_STATUS.md (living document)
- DOCUMENT_MAINTENANCE_LOG.md (appended every session)
- SESSION_N_HANDOFF.md (session-specific)
- Any document with "CURRENT_STATE" in name
- Configuration files with actual values (.env, populated YAMLs)

### Decision Tree

```
Is document a status tracker? → ❌ NEVER in project knowledge
Is document a session handoff? → ❌ NEVER in project knowledge
Is document updated every session? → ❌ NEVER in project knowledge
Is document a reference guide AND stable? → ✅ YES, in project knowledge
Is document >20KB AND used frequently? → ✅ YES, in project knowledge
```

---

## Part 7: Context Management Strategy

### NEW in v1.1: Addressing Context Complexity Limits

**Problem Discovered:** Sessions can terminate after only 7-20 message exchanges even with token budget available (e.g., 63K/190K used = 33%), due to context complexity rather than raw token exhaustion.

**Cause:** Dense cross-referencing, large artifacts, and extensive project knowledge create high "context weight" per message exchange.

### Context Weight Factors

**Normal conversation:** ~500-1000 tokens/exchange  
**Your project:** ~5000-9000 tokens/exchange

**Why?**
- Project knowledge baseline: ~50K tokens
- Each document reference: +2-5K context load
- Creating artifacts: +3-10K tokens each
- Cross-document validation: +2K per reference
- Version control metadata: +500 tokens

### Strategies to Extend Session Length

#### Strategy 1: Explicit Context Boundaries

**Instead of:**
```
"Review all documents and tell me about X"
```

**Do:**
```
"Based on PROJECT_OVERVIEW_V1.2.md section 3 ONLY, 
tell me about X (don't reference other docs)"
```

**Impact:** Reduces context loading by 80%

---

#### Strategy 2: Batch Related Requests

**Instead of:** Multiple separate exchanges
```
Message 1: "Create MASTER_INDEX"
Message 2: "Create PROJECT_OVERVIEW"
Message 3: "Create VERSION_HEADERS"
```
= 3 exchanges with full context loading each time

**Do:**
```
"Create these 3 documents in one response:
1. MASTER_INDEX_V2.1.md (structure: ...)
2. PROJECT_OVERVIEW_V1.2.md (structure: ...)
3. VERSION_HEADERS_GUIDE_V2.1.md (structure: ...)"
```
= 1 exchange

**Impact:** 3x fewer exchanges, ~40% token savings

---

#### Strategy 3: Pre-Plan Session Scope

**Start sessions with:**
```
"Session goal: Update 3 specific documents (listed below).
Don't reference other docs unless critical.
Create artifacts progressively.

Today's scope:
- Update: DOC_A, DOC_B, DOC_C
- Create: DOC_D
- Reference only: DOC_E, DOC_F"
```

**Impact:** Keeps Claude focused, reduces exploratory context loading

---

#### Strategy 4: Avoid Exploratory Queries

**Exploratory queries load massive context:**
```
❌ "What should I do next?"
❌ "Review the project and suggest improvements"
❌ "What's the current state of everything?"
```

**These load ALL project knowledge to answer!**

**Instead:**
```
✅ "What's next per DEVELOPMENT_PHASES_V1.1.md Phase 1?"
✅ "Review kalshi_client.py against API_INTEGRATION_GUIDE section 3"
✅ "Update PROJECT_STATUS.md with today's progress: [specific items]"
```

**Impact:** Focused queries load 1-2 docs, not entire project

---

#### Strategy 5: Defer Non-Critical Tasks

**If approaching 60K tokens (Checkpoint 1):**
- Defer documentation updates to end of session
- Focus on critical deliverables first
- Save reviews and polish for separate session if needed

**Impact:** Prioritizes essential work within session limits

---

### Pre-Message Checklist

**Before sending each message, ask:**
1. **Do I need full project knowledge?**
   - No → Specify exact docs to reference
   - Yes → Is this truly necessary?

2. **Can I batch this with other requests?**
   - Yes → Combine into single message
   - No → Proceed

3. **Is this exploratory?**
   - Yes → Rephrase to be specific, or start new session
   - No → Proceed

4. **Will this create multiple artifacts?**
   - Yes → Consider splitting across multiple sessions
   - No → Proceed

---

### Session Length Targets

**With Context Management:**
- **Target:** 15-20 message exchanges minimum
- **Stretch:** 25-30 exchanges for simple tasks
- **Realistic:** Phase 1+ implementation may still hit 10-15 (use Claude Code)

**Indicators of approaching limit:**
- Creating 3+ large artifacts (>5K each)
- Referencing 5+ documents per exchange
- ~60K token usage with <10 exchanges
- → **Action:** Prepare handoff proactively, don't push limits

---

### Transition to Claude Code

**Ultimate Solution for Phase 1+:**

Claude Code has **no context complexity limits** (each command independent).

**Transition Point:** Phase 1 kickoff

**See CLAUDE_CODE_STRATEGY_V1.0.md for:**
- Installation instructions
- Usage patterns
- Hybrid workflow (Chat for design, Code for implementation)
- When to use which tool

**Expected Improvement:**
- Current Chat: 7-20 exchanges (context limited)
- With strategies: 15-25 exchanges (improved)
- With Claude Code: Unlimited exchanges (each command independent)

---

## Integration & Workflow

### Session Startup (5 min)

1. **Upload The Trio:**
   - PROJECT_STATUS.md
   - DOCUMENT_MAINTENANCE_LOG.md
   - Last SESSION_N_HANDOFF.md

2. **Set Session Scope:**
   ```
   "Session N goal: [Specific, narrow task]
   
   Context boundaries:
   - Reference only: [specific docs]
   - Create: [specific outputs]
   - Don't explore other areas
   
   Use context management strategies for 15+ exchanges."
   ```

3. **Begin Work** with focused, batched requests

---

### During Session

1. Work normally with context awareness
2. Monitor token checkpoints (automatic)
3. Batch related requests
4. Specify document references explicitly
5. Avoid exploratory queries
6. Prepare handoff when approaching limits

---

### Session End (10 min)

1. Run end-of-session mini-assessment (Part 4)
2. Verify handoff document complete
3. Update PROJECT_STATUS.md
4. Update DOCUMENT_MAINTENANCE_LOG.md
5. Confirm next session plan clear

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2025-10-15 | Added Part 7 (Context Management Strategy) to address conversation length limits, added pre-message checklist, session length targets |
| 1.0 | 2025-10-12 | Initial creation consolidating 6 separate protocol documents (TOKEN_MONITORING, HANDOFF_PROCESS, PHASE_ASSESSMENT, PROJECT_KNOWLEDGE, VERSION_CONTROL, SESSION_TEMPLATE) |

---

**Maintained By:** Project Lead  
**Review Frequency:** Update after discovering process improvements  
**Next Review:** After Phase 1 completion (evaluate effectiveness)

---

**This protocol is active for ALL sessions.**  
**Follow all 7 parts for optimal session management.**

---

**END OF HANDOFF PROTOCOL**
