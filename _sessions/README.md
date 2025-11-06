# Session Archives (_sessions/)

**Purpose:** Local archive folder for SESSION_HANDOFF.md versions

**Status:** Excluded from git (in .gitignore)

---

## What This Folder Contains

This folder contains date-stamped copies of SESSION_HANDOFF.md from each development session. Session archives provide ephemeral context during active development but are less valuable long-term.

**Naming Convention:**
- `SESSION_HANDOFF_YYYY-MM-DD.md` - One session per day
- `SESSION_HANDOFF_YYYY-MM-DD_v0.md`, `_v1.md`, `_v2.md` - Multiple sessions per day

---

## Why Excluded from Git?

**Reasons:**
1. **Ephemeral Documentation** - Useful during active development, less valuable after 3-6 months
2. **Git History Provides Context** - Commit messages already document what was done and why
3. **Foundation Documents are Permanent** - MASTER_REQUIREMENTS, ARCHITECTURE_DECISIONS, ADRs provide long-term context
4. **Prevents Repository Bloat** - ~25KB per session = 1.2MB per 50 sessions

**Note:** Historical session archives (through 2025-11-05) were committed to `docs/sessions/` and remain in git history. This folder (_sessions/) is for future local archives only.

---

## Archiving Workflow

**At the end of each session** (per CLAUDE.md Section 3 - Ending a Session):

```bash
# Step 0: Archive current SESSION_HANDOFF.md before overwriting
cp SESSION_HANDOFF.md "_sessions/SESSION_HANDOFF_$(date +%Y-%m-%d).md"

# If multiple sessions per day, add version suffix manually:
# cp SESSION_HANDOFF.md "_sessions/SESSION_HANDOFF_2025-11-05_v1.md"
```

---

## Retention Policy

**Local archives are kept for reference but not backed up:**
- Archives in this folder are local-only (not in git)
- Can be safely deleted after 3-6 months
- Critical session information should be documented in:
  * Git commit messages (permanent)
  * Foundation documents (MASTER_REQUIREMENTS, ARCHITECTURE_DECISIONS)
  * CLAUDE.md updates (for major changes)

---

## Historical Archives

**Committed archives (2025-10-28 through 2025-11-05):**
- Located in `docs/sessions/` (committed to git history)
- 13 historical sessions preserved
- Excluded from future commits (docs/sessions/ added to .gitignore)

**View historical archives:**
```bash
git log --oneline docs/sessions/
```

---

**Created:** 2025-11-05
**Purpose:** Document local session archiving workflow
