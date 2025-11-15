# Version Headers Guide

---
**Version:** 2.1
**Last Updated:** 2025-10-12
**Status:** ✅ Current
**Changes in v2.1:** Added reference to Handoff_Protocol_V1.0.md for version control enforcement and end-session workflow
---

## Purpose

**Establish consistent version tracking** across all major documentation files for better change management and archiving.

**Key Update (v2.1):** Version control enforcement is now integrated into **Handoff_Protocol_V1.0.md** (Part 1: Version Control Standards). This guide provides the standards; the Protocol enforces them at session end.

---

## Standard Version Header Template

Add this at the very top of each major document (after the title, before content):

```markdown
---
**Version:** X.Y
**Last Updated:** YYYY-MM-DD
**Status:** [✅ Current / ⚠️ Needs Update / 📝 Draft / 🗄️ Archived]
**Changes in vX.Y:** [Brief summary of what changed in this version]
---
```

**Example (from PROJECT_OVERVIEW_V1.2.md):**
```markdown
---
**Version:** 1.2
**Last Updated:** 2025-10-12
**Status:** ✅ Current
**Changes in v1.2:** Added testing/CI-CD section, budget estimates, phase dependencies table, clarified Phases 3/4 sequencing.
---
```

---

## Version Numbering Convention

**Format:** MAJOR.MINOR (X.Y)

### MAJOR Version (X.0) - Increment when:
- Fundamental redesign or restructure
- Breaking changes to architecture
- Major scope expansion or reduction
- Complete rewrite of document

**Examples:**
- v1.0 → v2.0: Complete redesign of configuration system
- v1.x → v2.0: Added entire new phase (Phase 10: Polymarket)

### MINOR Version (X.Y) - Increment when:
- Adding new sections or subsections
- Significant updates to existing content
- Corrections to important information
- Enhancements that don't change core structure

**Examples:**
- v1.0 → v1.1: Added missing tables to database schema
- v1.1 → v1.2: Added testing section and budget estimates

---

## Filename Versioning Convention

### YES - Include Version in Filename

**When to use:**
- Major reference documents (referenced across multiple sessions)
- Documents where version matters for tracking historical changes
- Stable documents in project knowledge
- Documents that rarely change (monthly or less frequently)

**Format:** `DOCUMENT_NAME_VX.Y.md`

**Examples:**
- `MASTER_INDEX_V2.1.md` (navigation reference)
- `MASTER_REQUIREMENTS_V2.1.md` (system requirements)
- `ARCHITECTURE_DECISIONS_V2.1.md` (design rationale)
- `CONFIGURATION_GUIDE_V2.1.md` (config patterns)
- `PROJECT_OVERVIEW_V1.2.md` (system architecture)
- `Handoff_Protocol_V1.0.md` (process reference)
- `API_INTEGRATION_GUIDE_V1.0.md` (API documentation)

---

### NO - Version in Header Only

**When to use:**
- Living/dynamic documents (change every session or frequently)
- Session handoffs (session number serves as version)
- Status trackers (continuously updated)
- Maintenance logs (append-only)

**Format:** `DOCUMENT_NAME.md` (version only in header as "Living Document (header only vX.Y)")

**Examples:**
- `PROJECT_STATUS.md` (updated every session)
- `DOCUMENT_MAINTENANCE_LOG.md` (appended every session)
- `SESSION_7_HANDOFF.md` (session number is version)
- `SESSION_8_HANDOFF.md` (next session)

**Header Format for Living Documents:**
```markdown
---
**Version:** Living Document (header only v1.1)
**Last Updated:** 2025-10-12
**Status:** ✅ Active
**Changes in v1.1:** [What changed in this header version]
---
```

---

## Version Update Process

### When Updating a Versioned Document (Filename Has Version)

**Steps:**
1. **Archive old version:**
   - Move old file to `/archive/v1.0/` (or appropriate version folder)
   - Example: `MASTER_INDEX_V2.0.md` → `/archive/v2.0/MASTER_INDEX_V2.0.md`

2. **Create new version:**
   - Create new file with updated version number
   - Example: Create `MASTER_INDEX_V2.1.md`

3. **Update header inside new document:**
   - Increment version number (2.0 → 2.1)
   - Update "Last Updated" date
   - Add "Changes in vX.Y" description

4. **Update references:**
   - Update MASTER_INDEX_VX.Y.md to show new version
   - Update any docs that reference this doc

5. **Log change:**
   - Add entry to DOCUMENT_MAINTENANCE_LOG.md with upstream/downstream impacts

---

### When Updating a Living Document (No Version in Filename)

**Steps:**
1. **Edit file in place** (same filename, no archiving)

2. **Update header:**
   - Increment header version if significant (v1.0 → v1.1)
   - Update "Last Updated" date
   - Add brief description of changes

3. **Log change:**
   - Add entry to DOCUMENT_MAINTENANCE_LOG.md

**Example:**
```markdown
# PROJECT_STATUS.md

---
**Version:** Living Document (header only v1.2)
**Last Updated:** 2025-10-12
**Status:** ✅ Active
**Changes in v1.2:** Updated Phase 0 to 100%, added Session 7 summary
---
```

---

## Status Indicators

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| ✅ **Current** | Up-to-date, accurate, safe to reference | None - use freely |
| ⚠️ **Needs Update** | Known issues or outdated sections | Review carefully, update soon |
| 📝 **Draft** | Work in progress, incomplete | Use for planning only |
| 🗄️ **Archived** | Superseded by newer version | Don't use, refer to replacement |

---

## Enforcement via Handoff Protocol

**As of v2.1, version control is enforced via Handoff_Protocol_V1.0.md:**

### End-of-Session Mini-Assessment (Protocol Part 4)

**Before completing each session, verify:**

✅ **Version Headers Applied?**
- [ ] All new documents have proper version headers?
- [ ] All updated documents have incremented versions?
- [ ] All headers follow this guide's format?

✅ **Filename Versioning Correct?**
- [ ] Major docs have version in filename (vX.Y)?
- [ ] Living docs have NO version in filename?
- [ ] Session handoffs use session number only?

✅ **Archiving Complete?**
- [ ] Old versions moved to `/archive/vX.Y/`?
- [ ] MASTER_INDEX updated with new versions?
- [ ] No broken references to old versions?

✅ **Changes Logged?**
- [ ] DOCUMENT_MAINTENANCE_LOG updated?
- [ ] Upstream/downstream impacts noted?
- [ ] MASTER_INDEX reflects current state?

**See Handoff_Protocol_V1.0.md Part 1 for complete version control standards and Part 4 for end-session workflow.**

---

## Archive Structure

**Archive organization:**
```
/archive/
├── v1.0/
│   ├── PROJECT_OVERVIEW_V1.0.md
│   ├── PROJECT_OVERVIEW_V1.1.md
│   └── MASTER_INDEX_V1.0.md
├── v2.0/
│   ├── MASTER_INDEX_V2.0.md
│   └── CONFIGURATION_GUIDE_V2.0.md
└── README.md (explains what's archived and why)
```

**Archive README.md should contain:**
- Date archived
- Reason for archiving
- Replacement document
- Notable changes in new version

---

## Quick Reference

### For New Documents
1. Determine if major (versioned filename) or living (header only)
2. Add appropriate version header at top
3. Set version to 1.0 for new documents
4. Add to MASTER_INDEX_VX.Y.md
5. Log in DOCUMENT_MAINTENANCE_LOG.md

### For Updated Documents
1. Check if filename has version (major) or not (living)
2. If major: Archive old, create new with incremented version
3. If living: Edit in place, increment header version
4. Update header with changes description
5. Update MASTER_INDEX_VX.Y.md
6. Log in DOCUMENT_MAINTENANCE_LOG.md with impacts

### At Session End
1. Run mini-assessment from Handoff_Protocol Part 4
2. Verify all version headers applied correctly
3. Confirm archiving complete
4. Check MASTER_INDEX is current
5. Ensure MAINTENANCE_LOG updated

---

## Common Mistakes to Avoid

❌ **Don't:**
- Put version in filename for living documents (e.g., `PROJECT_STATUS_V1.2.md`)
- Forget to archive old versions before creating new
- Skip updating MASTER_INDEX when versions change
- Leave "Changes in vX.Y" blank or generic
- Mix version formats (be consistent across project)
- Reference old versions in active documents

✅ **Do:**
- Follow major vs. living document rules strictly
- Write meaningful "Changes in vX.Y" descriptions
- Update MASTER_INDEX immediately when creating new versions
- Archive old versions systematically
- Log all version changes with upstream/downstream impacts
- Reference Handoff_Protocol for enforcement workflow

---

## Examples of Good Version Headers

### Example 1: Major Document (Versioned Filename)
```markdown
# Master Requirements

---
**Version:** 2.1
**Last Updated:** 2025-10-12
**Status:** ✅ Current
**Changes in v2.1:** Added Phase 4 historical model requirements, updated tech stack to latest packages, clarified Phases 3/4 data flow sequencing.
---
```

### Example 2: Living Document (Header Only)
```markdown
# Project Status

---
**Version:** Living Document (header only v1.2)
**Last Updated:** 2025-10-12
**Status:** ✅ Active
**Changes in v1.2:** Merged with QUICK_START_GUIDE and README_STREAMLINED, condensed to ~1 page format, added token budget tracking table.
---
```

### Example 3: Session Handoff (No Version in Header)
```markdown
# Session 7 Handoff

---
**Session Number:** 7
**Date:** 2025-10-12
**Token Usage:** 63K / 190K (33%)
**Status:** ✅ Complete
---
```

---

## Integration with Other Processes

**This guide integrates with:**
- **Handoff_Protocol_V1.0.md** - Part 1 (Version Control Standards) references this guide
- **DOCUMENT_MAINTENANCE_LOG.md** - Logs all version changes with impacts
- **MASTER_INDEX_VX.Y.md** - Tracks current versions of all documents
- **PROJECT_STATUS.md** - Lists essential docs with current versions

**Workflow:**
1. Use this guide when creating/updating documents
2. Follow Handoff_Protocol Part 1 for standards
3. Log changes in MAINTENANCE_LOG with impacts
4. Update MASTER_INDEX with new versions
5. Run mini-assessment at session end (Protocol Part 4)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2025-10-12 | Added reference to Handoff_Protocol_V1.0.md for enforcement, expanded examples, added end-session mini-assessment checklist |
| 2.0 | 2025-10-08 | Added filename versioning convention (Session 5), separated major vs. living documents |
| 1.0 | Earlier | Initial version with basic header template |

---

**Template Version:** 2.1
**Last Updated:** 2025-10-12
**Maintained By:** Claude & User
**Reference in:** Handoff_Protocol_V1.0.md Part 1

---

**END OF VERSION HEADERS GUIDE**
