# Precog Documentation Master Index

---
**Version:** 2.3
**Last Updated:** 2025-10-21
**Status:** ✅ Current
**Changes in v2.3:**
- **MAJOR**: Phase 0.5 (Foundation Enhancement) complete - all Days 1-10 finished
- Updated core documents: MASTER_REQUIREMENTS V2.5, DATABASE_SCHEMA_SUMMARY V1.5, CONFIGURATION_GUIDE V3.1, DEVELOPMENT_PHASES V1.3
- Updated YAML configs: probability_models.yaml V2.0, position_management.yaml V2.0, trade_strategies.yaml V2.0
- Added 3 new implementation guides: VERSIONING_GUIDE, TRAILING_STOP_GUIDE, POSITION_MANAGEMENT_GUIDE
- Database schema V1.5 with position monitoring and exit management (position_exits, exit_attempts tables)
- 10 exit conditions documented with priority hierarchy (CRITICAL, HIGH, MEDIUM, LOW)
- Phase 5 split into 5a (Monitoring & Evaluation) and 5b (Execution & Walking)
- Ready for Phase 1 implementation

**Changes in v2.2:** Updated all document versions (Master Requirements v2.3, Architecture Decisions v2.3, Project Overview v1.3, Configuration Guide v3.0, Database Schema v1.2); renamed all files to match internal versions; added Phase 0 completion documents (CONSISTENCY_REVIEW, FILENAME_VERSION_REPORT, PHASE_0_COMPLETENESS, CLAUDE_CODE_INSTRUCTIONS); updated probability_models.yaml reference (was odds_models.yaml).

**Changes in v2.1:** Added "Location" and "Phase Ties" columns to all tables; updated to reflect Session 7 handoff streamline (7 docs archived, 4 consolidated); added Handoff_Protocol_V1.0.md; marked Phase 0 at 100%.
---

## Purpose

This is the **authoritative list of ALL project documents** - existing, planned, and future. Use this to:
- Find any document quickly by location
- Understand document status, versions, and phase dependencies
- Know what needs creating/updating
- Reference the correct version
- Navigate the `/docs/` directory structure

**Navigation:** Jump to section via links below
**Maintenance:** Update this file when ANY document is added, removed, version-bumped, or significantly changed

---

## Quick Navigation

- [Foundation Documents](#foundation-documents) - Core architecture & requirements
- [API & Integration](#api--integration-documents) - External systems
- [Database & Data](#database--data-documents) - Schema and data design
- [Configuration](#configuration-documents) - YAML configs and settings
- [Trading & Risk](#trading--risk-documents) - Strategy and risk management
- [Testing & Quality](#testing--quality-documents) - Test specs and validation
- [Phases & Planning](#phases--planning-documents) - Roadmap and project management
- [Implementation Guides](#implementation-guides) - Phase-specific implementation details
- [Utility Documents](#utility-documents) - Handoffs, logs, maintenance
- [Supplementary](#supplementary-documents) - Guides and references
- [Future/Archived](#future--archived-documents) - Planned and deprecated

---

## Document Status Legend

| Symbol | Status | Meaning |
|--------|--------|---------|
| ✅ | **Exists - Current** | Document exists and is up-to-date |
| ⚠️ | **Exists - Needs Update** | Document exists but has known issues or pending updates |
| 📝 | **In Progress** | Currently being created/updated |
| ❌ | **Missing - Critical** | Needed for current phase, blocking progress |
| 🔵 | **Missing - Planned** | Planned for future phase |
| 🗄️ | **Archived** | Superseded, deprecated, or merged into another doc |

---

## Column Definitions

| Column | Description |
|--------|-------------|
| **Document** | Document name (with version if applicable) |
| **Status** | Current state (see legend above) |
| **Version** | Current version number (X.Y format) |
| **Location** | File path in `/docs/` or `/config/` directory |
| **Phase** | Primary phase this document supports |
| **Phase Ties** | Which phases depend on or reference this doc |
| **Priority** | Importance level (🔴 Critical / 🟡 High / 🟢 Medium / 🔵 Low) |
| **Notes** | Additional context or usage notes |

---

## Foundation Documents

Core architecture, requirements, and system design documents.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **PROJECT_OVERVIEW_V1.3.md** | ✅ | v1.3 | `/docs/foundation/` | 0 | All phases | 🔴 Critical | System architecture, tech stack, directory tree - UPDATED |
| **MASTER_REQUIREMENTS_V2.5.md** | ✅ | v2.5 | `/docs/foundation/` | 0 | All phases | 🔴 Critical | Complete requirements through Phase 10 - UPDATED Phase 0.5 |
| **MASTER_INDEX_V2.3.md** | ✅ | v2.3 | `/docs/foundation/` | 0 | All phases | 🔴 Critical | THIS FILE - complete document inventory - UPDATED Phase 0.5 |
| **ARCHITECTURE_DECISIONS_V2.3.md** | ✅ | v2.3 | `/docs/foundation/` | 0 | Phases 1-10 | 🟡 High | Design rationale, ADRs 1-15+ - UPDATED |
| **GLOSSARY.md** | ✅ | n/a | `/docs/foundation/` | 0 | All phases | 🟢 Medium | Terminology reference (living document, no version) |
| **DEVELOPMENT_PHASES_V1.3.md** | ✅ | v1.3 | `/docs/foundation/` | 0 | All phases | 🟡 High | Complete roadmap Phase 0-10, Phase 5 split into 5a/5b - UPDATED Phase 0.5 |

---

## API & Integration Documents

External API documentation, integration guides, and authentication specs.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **API_INTEGRATION_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/api-integration/` | 1 | Phases 1-2, 6, 10 | 🔴 Critical | Merged Kalshi/ESPN/Balldontlie, RSA-PSS auth examples |
| **KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md** | ✅ | v1.0 | `/docs/api-integration/` | 1 | Phases 1-5 | 🔴 Critical | **PRINT & KEEP AT DESK** - Critical reference |
| **KALSHI_API_STRUCTURE_COMPREHENSIVE_V2.0.md** | ⚠️ | v2.0 | `/docs/api-integration/` | 1 | Phases 1-5 | 🟡 High | ⚠️ Merged into API_INTEGRATION_GUIDE, mark archived |
| **KALSHI_DATABASE_SCHEMA_CORRECTED_V1.0.md** | ✅ | v1.0 | `/docs/api-integration/` | 1 | Phase 1 | 🟢 Medium | Kalshi-specific schema corrections |

---

## Database & Data Documents

Schema design, data models, and database architecture.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **DATABASE_SCHEMA_SUMMARY_V1.5.md** | ✅ | v1.5 | `/docs/database/` | 0.5 | Phases 1-10 | 🔴 Critical | Position monitoring, exit management, 10 exit conditions - UPDATED Phase 0.5 |
| **ODDS_RESEARCH_COMPREHENSIVE.md** | ✅ | v1.0 | `/docs/database/` | 4 | Phase 4, 9 | 🟡 High | Historical odds methodology, merged into models |

---

## Configuration Documents

YAML configuration files and configuration guides.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **CONFIGURATION_GUIDE_V3.1.md** | ✅ | v3.1 | `/docs/configuration/` | 0.5 | Phases 1-10 | 🟡 High | Comprehensive update with all 7 YAMLs, versioning, method abstraction - UPDATED Phase 0.5 |
| **system.yaml** | ✅ | v1.0 | `/config/` | 1 | Phases 1-10 | 🔴 Critical | System-wide settings (DB, logging, API) |
| **trading.yaml** | ✅ | v1.0 | `/config/` | 1 | Phases 1-10 | 🔴 Critical | Trading parameters, Kelly fractions, DECIMAL examples |
| **probability_models.yaml** | ✅ | v2.0 | `/config/` | 4 | Phases 4-9 | 🔴 Critical | Versioning support, immutable configs, educational docstrings - UPDATED Phase 0.5 |
| **position_management.yaml** | ✅ | v2.0 | `/config/` | 1 | Phases 1-10 | 🔴 Critical | 10 exit conditions, priority hierarchy, trailing stops - UPDATED Phase 0.5 |
| **trade_strategies.yaml** | ✅ | v2.0 | `/config/` | 1 | Phases 1-10 | 🔴 Critical | Versioning support, halftime_entry updates - UPDATED Phase 0.5 |
| **markets.yaml** | ✅ | v1.1 | `/config/` | 1 | Phases 1-10 | 🔴 Critical | Market filtering, platform configs, research_gap_flag |
| **data_sources.yaml** | ✅ | v1.1 | `/config/` | 2 | Phases 2-10 | 🔴 Critical | API endpoints, ESPN/Balldontlie/nflfastR configs |
| **.env.template** | ✅ | template | `/config/` | 1 | Phases 1-10 | 🔴 Critical | All API keys Phase 1-10 placeholders |

---

## Trading & Risk Documents

Trading logic, risk management, and position management specs.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **RISK_MANAGEMENT_PLAN_V1.0.md** | 🔵 | - | `/docs/trading/` | 1 | Phases 1-10 | 🟡 High | Circuit breakers, position limits, Kelly fractions |
| **KELLY_CRITERION_GUIDE_V1.0.md** | 🔵 | - | `/docs/trading/` | 1 | Phases 1-10 | 🟢 Medium | Kelly math, fractional Kelly, sport-specific |
| **EDGE_DETECTION_ALGORITHM_V1.0.md** | 🔵 | - | `/docs/trading/` | 4 | Phases 4-5 | 🟡 High | Efficiency threshold, confidence scoring |

---

## Testing & Quality Documents

Test specifications, validation protocols, and quality assurance.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **TESTING_STRATEGY_V1.0.md** | 🔵 | - | `/docs/testing/` | 1 | Phases 1-10 | 🟡 High | Unit, integration, end-to-end test plans |
| **MODEL_VALIDATION_V1.0.md** | 🔵 | - | `/docs/testing/` | 4 | Phase 4 ✅ | 🟡 High | Elo vs. research, backtesting benchmarks |
| **BACKTESTING_PROTOCOL_V1.0.md** | 🔵 | - | `/docs/testing/` | 4 | Phase 4-5 ✅ | 🟡 High | Walk-forward validation, train/test splits |

---

## Phases & Planning Documents

Roadmap, timelines, and project management.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **DEVELOPMENT_PHASES_V1.3.md** | ✅ | v1.3 | `/docs/foundation/` | 0.5 | All phases | 🟡 High | Phase 0.5 complete, Phase 5 split into 5a/5b - UPDATED Phase 0.5 |
| **DEPLOYMENT_GUIDE_V1.0.md** | 🔵 | - | `/docs/deployment/` | 1 | Phase 1 ✅ | 🟡 High | Local/AWS deployment stubs |
| **USER_GUIDE_V1.0.md** | 🔵 | - | `/docs/guides/` | 5 | Phase 5 ✅ | 🟢 Medium | CLI examples (edges-list, trade-execute) |
| **DEVELOPER_ONBOARDING_V1.0.md** | 🔵 | - | `/docs/utility/` | 0 | Phase 0 ✅ | 🟡 High | Merged with ENVIRONMENT_CHECKLIST, onboarding steps |

---

## Implementation Guides

Phase-specific implementation guides created in Phase 0.5.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **VERSIONING_GUIDE.md** | ✅ | v1.0 | `/docs/guides/` | 0.5 | Phases 4-9 | 🔴 Critical | **NEW** - Immutable versioning for strategies and models - CREATED Phase 0.5 |
| **TRAILING_STOP_GUIDE.md** | ✅ | v1.0 | `/docs/guides/` | 0.5 | Phases 1, 4, 5 | 🔴 Critical | **NEW** - Trailing stop loss implementation guide - CREATED Phase 0.5 |
| **POSITION_MANAGEMENT_GUIDE.md** | ✅ | v1.0 | `/docs/guides/` | 0.5 | Phase 5 | 🔴 Critical | **NEW** - Position lifecycle, 10 exit conditions, monitoring, execution - CREATED Phase 0.5 |

---

## Utility Documents

Handoffs, logs, maintenance protocols, and project management utilities.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **PROJECT_STATUS.md** | ✅ | v1.1 (header) | `/docs/utility/` | 0 | All phases | 🔴 Critical | **LIVING DOC** - upload every session, merged STATUS+README+QUICK_START |
| **DOCUMENT_MAINTENANCE_LOG.md** | ✅ | v1.1 (header) | `/docs/utility/` | 0 | All phases | 🔴 Critical | **LIVING DOC** - upload every session, tracks changes with upstream/downstream impacts |
| **SESSION_HANDOFF_TEMPLATE.md** | ✅ | template | `/docs/utility/` | 0 | All phases | 🔴 Critical | Streamlined ~1 page template, inline instructions |
| **SESSION_7_HANDOFF.md** | ✅ | - | `/docs/sessions/` | 0 | Session 7 | 🟡 High | Latest session handoff (session # is version) |
| **SESSION_6_HANDOFF.md** | ✅ | - | `/docs/sessions/` | 0 | Session 6 | 🟢 Medium | Previous session handoff |
| **Handoff_Protocol_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | 0 | All phases | 🔴 Critical | Merged 4 docs: HANDOFF_PROCESS + TOKEN_MONITORING + PHASE_COMPLETION + KNOWLEDGE_STRATEGY |
| **VERSION_HEADERS_GUIDE_V2.1.md** | ✅ | v2.1 | `/docs/utility/` | 0 | All phases | 🟡 High | Version control standards, references Handoff_Protocol |
| **ENVIRONMENT_CHECKLIST_V1.1.md** | ✅ | v1.1 | `/docs/utility/` | 0 | Phase 0 ✅ | 🔴 Critical | Windows 11 setup, Parts 1-7, dependencies verification |
| **CONSISTENCY_REVIEW.md** | ✅ | n/a | `/docs/phase-0-completion/` | 0 | Phase 0 ✅ | 🟡 High | Phase 0 consistency validation, all discrepancies fixed |
| **FILENAME_VERSION_REPORT.md** | ✅ | n/a | `/docs/phase-0-completion/` | 0 | Phase 0 ✅ | 🟡 High | Filename-version consistency validation |
| **PHASE_0_COMPLETENESS.md** | ✅ | n/a | `/docs/phase-0-completion/` | 0 | Phase 0 ✅ | 🔴 Critical | Phase 0 completion checklist, 100% complete |
| **PHASE_0_GIT_COMMIT_CHECKLIST.md** | ✅ | n/a | `/docs/phase-0-completion/` | 0 | Phase 0 ✅ | 🟡 High | Git commit guidance and checklist |
| **GIT_COMMIT_SUMMARY.md** | ✅ | n/a | `/docs/phase-0-completion/` | 0 | Phase 0 ✅ | 🟡 High | Comprehensive git commit summary |
| **CLAUDE_CODE_INSTRUCTIONS.md** | ✅ | n/a | `/docs/phase-0-completion/` | 0 | Phase 0-1 | 🔴 Critical | Instructions for Phase 0 completion and Phase 1 kickoff |
| **CLAUDE_CODE_INSTRUCTIONS_ERRATA.md** | ✅ | n/a | `/docs/phase-0-completion/` | 0 | Phase 0-1 | 🟡 High | Corrections to instructions for Phase 1 |
| **TERMINOLOGY_UPDATE_SUMMARY.md** | ✅ | n/a | `/docs/phase-0-completion/` | 0 | Phase 0 ✅ | 🟡 High | Terminology change from "odds" to "probability" |

---

## Supplementary Documents

Additional guides, references, and supporting documentation.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **REQUIREMENTS_AND_DEPENDENCIES_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | 1 | Phase 1 ✅ | 🟡 High | Comparison table: Part 7 sample vs. comprehensive reqs.txt |
| **HANDOFF_STREAMLINE_RATIONALE.md** | ✅ | v1.0 | `/docs/sessions/` | 0 | Session 7 | 🟢 Medium | Documents 73% doc reduction, goals achievement |
| **DOCUMENTATION_AUDIT_REPORT.md** | ✅ | v1.0 | `/docs/utility/` | 0 | Session 2-3 | 🟢 Medium | Quality analysis from earlier sessions |

---

## Future & Archived Documents

### Planned (Future Phases)

| Document | Status | Phase | Phase Ties | Priority | Notes |
|----------|--------|-------|------------|----------|-------|
| **POLYMARKET_INTEGRATION_GUIDE.md** | 🔵 | 10 | Phase 10 | 🟡 High | Multi-platform Phase 10 |
| **CROSS_PLATFORM_ARBITRAGE.md** | 🔵 | 10 | Phase 10 | 🟡 High | Kalshi vs Polymarket |
| **WEB_DASHBOARD_GUIDE.md** | 🔵 | 10+ | Phase 10+ | 🟢 Medium | React + FastAPI monitoring |
| **ML_MODEL_TRAINING_GUIDE.md** | 🔵 | 9 | Phase 9 | 🟡 High | XGBoost/LSTM training protocols |

---

### Archived (Session 7 - Handoff Streamline)

**Archived to `/archive/v1.0/` on 2025-10-12:**

| Document | Replaced By | Reason | Original Location |
|----------|-------------|--------|-------------------|
| **README_STREAMLINED.md** | PROJECT_STATUS.md (v1.1 "What is Precog" section) | Consolidation | `/docs/` |
| **QUICK_START_GUIDE.md** | PROJECT_STATUS.md (v1.1 "Quick Start" section) | Consolidation | `/docs/utility/` |
| **TOKEN_MONITORING_PROTOCOL.md** | Handoff_Protocol_V1.0.md (Part 2: Token Management) | Consolidation | `/docs/utility/` |
| **HANDOFF_PROCESS_UPDATED.md** | Handoff_Protocol_V1.0.md (Part 3: Session Handoff) | Consolidation | `/docs/utility/` |
| **PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md** | Handoff_Protocol_V1.0.md (Part 5: Phase Assessment) | Consolidation | `/docs/utility/` |
| **PROJECT_KNOWLEDGE_STRATEGY_V1.0.md** | Handoff_Protocol_V1.0.md (Part 6: PK Strategy) | Consolidation | `/docs/utility/` |
| **SESSION_HANDOFF_TEMPLATE_V1.0.md** | SESSION_HANDOFF_TEMPLATE.md (integrated format) | Consolidation | `/docs/utility/` |

**Additional Archived (Earlier Sessions):**

| Document | Status | Replaced By | Notes |
|----------|--------|-------------|-------|
| **CURRENT_STATE_UPDATED_V2.md** | 🗄️ | PROJECT_STATUS.md | Too many versions created |
| **SESSION_5_STATUS.md** | 🗄️ | SESSION_5_HANDOFF.md | Redundant info |

---

## Statistics

### Document Count by Status
- ✅ **Exists - Current:** 31 documents (Phase 0.5 at 100%)
- ⚠️ **Exists - Needs Update:** 1 document (KALSHI_API_STRUCTURE → merge complete)
- 📝 **In Progress:** 0 documents
- ❌ **Missing - Critical:** 0 documents (Phase 0.5 complete!)
- 🔵 **Missing - Planned:** 40+ documents (Phases 1-10)
- 🗄️ **Archived:** 9 documents (7 from Session 7 streamline)

### Document Count by Phase
- **Phase 0 (Foundation):** 25 documents ✅ 100% complete
- **Phase 0.5 (Foundation Enhancement):** 6 new documents ✅ 100% complete (3 guides + 3 YAML updates)
- **Phase 1-3 (Core):** 15 documents planned
- **Phase 4-5 (Trading & Validation):** 12 documents planned
- **Phase 6-7 (Multi-Sport):** 8 documents planned
- **Phase 8-9 (Non-Sports & Advanced):** 10 documents planned
- **Phase 10+ (Multi-Platform & Dashboard):** 8 documents planned

### Phase 0.5 Status: ✅ 100% COMPLETE

**All Phase 0.5 deliverables complete (Days 1-10):**
- ✅ DATABASE_SCHEMA_SUMMARY_V1.5.md (position_exits, exit_attempts tables)
- ✅ MASTER_REQUIREMENTS_V2.5.md (REQ-MON-*, REQ-EXIT-*, REQ-EXEC-*)
- ✅ ARCHITECTURE_DECISIONS_V2.4.md (ADRs 18-23)
- ✅ PROJECT_OVERVIEW_V1.4.md
- ✅ DEVELOPMENT_PHASES_V1.3.md (Phase 5 split into 5a/5b)
- ✅ position_management.yaml V2.0 (10 exit conditions)
- ✅ probability_models.yaml V2.0 (versioning)
- ✅ trade_strategies.yaml V2.0 (versioning)
- ✅ CONFIGURATION_GUIDE_V3.1.md (comprehensive)
- ✅ VERSIONING_GUIDE.md (immutable versions)
- ✅ TRAILING_STOP_GUIDE.md (trailing stop implementation)
- ✅ POSITION_MANAGEMENT_GUIDE.md (complete position lifecycle)
- ✅ schema_v1.4_to_v1.5_migration.sql (database migration)
- ✅ MASTER_INDEX_V2.3.md (this file)

**Ready for Phase 1 implementation**

### Phase 0 Status: ✅ 100% COMPLETE

**All critical blockers resolved:**
- ✅ MASTER_REQUIREMENTS_V2.1.md
- ✅ All 7 YAML configuration files
- ✅ .env.template
- ✅ ENVIRONMENT_CHECKLIST_V1.1.md
- ✅ DATABASE_SCHEMA_SUMMARY_V1.1.md
- ✅ Handoff system streamlined (73% doc reduction)
- ✅ Version control applied across all docs
- ✅ Phase alignment corrected (Phases 3/4 sequencing)
- ✅ Historical model integration complete

---

## Project Knowledge Strategy

### ✅ Documents IN Project Knowledge
**Criteria:** Stable, reference documents, rarely change (monthly or less)

**Currently IN Project Knowledge:**
- MASTER_INDEX_V2.3.md (this file - navigation)
- PROJECT_OVERVIEW_V1.3.md (architecture)
- MASTER_REQUIREMENTS_V2.5.md (requirements)
- ARCHITECTURE_DECISIONS_V2.3.md (design rationale)
- CONFIGURATION_GUIDE_V3.1.md (config patterns)
- DATABASE_SCHEMA_SUMMARY_V1.5.md (schema)
- API_INTEGRATION_GUIDE_V1.0.md (API docs)
- KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md (critical reference)
- DEVELOPMENT_PHASES_V1.3.md (roadmap)
- GLOSSARY.md (terminology)
- Handoff_Protocol_V1.0.md (process reference)
- VERSIONING_GUIDE.md (versioning patterns)
- TRAILING_STOP_GUIDE.md (trailing stop implementation)
- POSITION_MANAGEMENT_GUIDE.md (position lifecycle)

### ❌ Documents NOT in Project Knowledge
**Criteria:** Change frequently, uploaded fresh each session**

**Always upload fresh (The Trio):**
- PROJECT_STATUS.md (living document)
- DOCUMENT_MAINTENANCE_LOG.md (appended every session)
- SESSION_N_HANDOFF.md (session-specific)

**Never in project knowledge:**
- Any document with "CURRENT_STATE" in name
- Session-specific documents
- Configuration files with actual values (.env, populated YAMLs)

**See Handoff_Protocol_V1.0.md Part 6 for complete PK strategy.**

---

## Maintenance Protocol

### When Adding a Document
1. Add entry to this MASTER_INDEX_V2.X.md (with Location and Phase Ties)
2. Add version header (use VERSION_HEADERS_GUIDE_V2.1.md)
3. Update PROJECT_STATUS.md
4. Log in DOCUMENT_MAINTENANCE_LOG.md (with upstream/downstream impacts)
5. Determine if it goes in project knowledge (see Handoff_Protocol Part 6)

### When Updating a Document
1. Increment version (major doc: archive old, create new; living: edit in place)
2. Update "Last Updated" date and "Changes in vX.Y"
3. Update status/version in this MASTER_INDEX
4. Log change in DOCUMENT_MAINTENANCE_LOG with upstream/downstream
5. Update PROJECT_STATUS.md if significant

### When Archiving a Document
1. Change status to 🗄️ in this MASTER_INDEX
2. Move file to `/archive/v1.0/` (or appropriate version folder)
3. Note replacement in "Replaced By" column
4. Remove from project knowledge if present
5. Update references in other documents

**Detailed process in Handoff_Protocol_V1.0.md Part 4 (Document Maintenance Workflows)**

---

## Quick Reference

### Starting a New Session (The Trio System)
**Upload these 3 files:**
1. PROJECT_STATUS.md (current state, last summary, next goals)
2. DOCUMENT_MAINTENANCE_LOG.md (change history with impacts)
3. Last SESSION_N_HANDOFF.md (previous session summary)

**Claude auto-references project knowledge** (no upload needed)

**Total read time:** ~5 minutes to get fully caught up

### Finding a Specific Document
1. Use Ctrl+F in this file (search by name or keyword)
2. Navigate by section (Quick Navigation at top)
3. Search by Phase Ties (e.g., "Phase 4" finds all Phase 4 docs)
4. Check Location column for file path

### Understanding Document Status
- ✅ = Safe to reference, current and accurate
- ⚠️ = Use with caution, has known issues or pending updates
- 📝 = Work in progress, incomplete
- ❌ = Doesn't exist yet, blocking if Critical priority
- 🔵 = Planned for future phase
- 🗄️ = Don't use, archived/deprecated

---

## Phase Completion Assessment

**At the end of each phase, run the 7-step assessment from Handoff_Protocol_V1.0.md Part 5:**

1. **Deliverable Completeness** (10 min) - All planned documents created?
2. **Internal Consistency** (5 min) - Terminology and tech stack consistent?
3. **Dependency Verification** (5 min) - All cross-references valid?
4. **Quality Standards** (5 min) - Version headers, formatting correct?
5. **Testing & Validation** (3 min) - Sample data provided?
6. **Gaps & Risks** (2 min) - Technical debt documented?
7. **Archive & Version Management** (5 min) - Old versions archived properly?

**Create PHASE_[N]_COMPLETION_REPORT.md after assessment.**

**Phase 0 Assessment:** ✅ Complete (see SESSION_7_HANDOFF.md for results)
**Phase 0.5 Assessment:** ✅ Complete (all Days 1-10 finished, ready for Phase 1)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.3 | 2025-10-21 | Phase 0.5 complete: added 3 implementation guides (VERSIONING, TRAILING_STOP, POSITION_MANAGEMENT), updated 6 core docs (MASTER_REQUIREMENTS V2.5, DATABASE_SCHEMA V1.5, CONFIGURATION_GUIDE V3.1, DEVELOPMENT_PHASES V1.3, 3 YAML V2.0), added schema migration V1.5, Phase 5 split into 5a/5b |
| 2.2 | 2025-10-17 | Updated all document versions (Master Requirements v2.3, Architecture Decisions v2.3, Project Overview v1.3, Configuration Guide v3.0, Database Schema v1.2); renamed all files to match internal versions; added Phase 0 completion documents |
| 2.1 | 2025-10-12 | Added "Location" and "Phase Ties" columns; Session 7 handoff streamline (7 docs archived, 4 consolidated); added Handoff_Protocol_V1.0.md; marked Phase 0 at 100% |
| 2.0 | 2025-10-08 | Complete document inventory through Phase 10, added YAML configs, utility docs, project knowledge strategy, maintenance protocols, statistics (Session 5) |
| 1.1 | Earlier | Enhanced with token sizes and use-when guidance |
| 1.0 | Earlier | Initial version with basic document list |

---

**Maintained By:** Claude & User
**Review Frequency:** Every session (update as documents added/removed/versioned)
**Next Review:** Next session (Phase 1 kickoff preparation)

---

**END OF MASTER INDEX**
