# Precog Documentation Master Index

---
**Version:** 2.24
**Last Updated:** 2025-11-16
**Status:** ✅ Current
**Changes in v2.24:**
- **PHASE 1.5 TEST PLAN DOCUMENTATION**: Added PHASE_1.5_TEST_PLAN_V1.0.md to testing & quality documents section
- Documents comprehensive test plan for Phase 1.5 deliverables (Strategy Manager, Model Manager, Position Manager enhancements)
- Includes test scenarios, success criteria, and coverage targets for versioned configuration managers
**Changes in v2.23:**
- **DEVELOPER ONBOARDING DOCUMENTATION**: Comprehensive setup guide for new developers
- Created DEVELOPER_SETUP_GUIDE_V1.0.md (500+ lines) - Complete developer onboarding (Python 3.12+, PostgreSQL 15+, Git, GitHub CLI, pre-commit hooks); platform-specific instructions (Windows/macOS/Linux); 6-step verification checklist; troubleshooting guide
- Updated scripts/reconcile_issue_tracking.sh - Added comprehensive dependency documentation (lines 27-39) for GitHub CLI requirement (installation, authentication, verification)
- Addresses gh CLI dependency risk identified in Phase Completion assessment Step 6
- **Context:** Issue tracking protocol (PR #81) requires GitHub CLI but lacked dependency documentation; no centralized developer setup guide existed
- **Impact:** Improved developer onboarding experience, documented gh CLI dependency risk, provided troubleshooting for common setup issues
**Changes in v2.22:**
- **CLAUDE.md SIZE REDUCTION (80%) + PR REVIEW DEFERRED TASK TRACKING**: Section 3 extraction + dual-tracking system for 45 deferred tasks from Phase 1 PR analysis
- Created SESSION_WORKFLOW_GUIDE_V1.0.md (extracted from CLAUDE.md V1.17 Section 3) - comprehensive session workflows including phase start protocol, recovery patterns, multi-session coordination
- Created PHASE_1_PR_REVIEW_DEFERRED_TASKS_V1.0.md - documents 45 actionable items from PRs #2-#21 with dual-tracking system (documentation + GitHub issues #29-#73)
- Updated CLAUDE.md V1.17 → V1.18 (condensed Section 3 from ~700 lines to ~140 lines, 80% reduction; frees ~7,000 tokens for code context)
- Created 45 GitHub issues (#29-#73) with bi-directional links (documentation → issue #, issue → doc line number)
- Created 8 custom GitHub labels for deferred task tracking (deferred-task, phase-1.5, priority-critical/high/medium/low, pattern-violation, security)
- Dual-tracking system prevents "4 out of 7 tasks lost" problem from Phase 0.7 (visibility + persistence)
- PR analysis identified 3 critical issues: float usage in property tests (Pattern 1 violation), zero test coverage for database/initialization.py (274 lines), path sanitization for security (CWE-22)
- **Context:** CLAUDE.md Section 3 had grown to ~700 lines (detailed workflows); Phase 1 PR analysis identified 45 actionable suggestions requiring formal tracking
- **Impact:** Context budget optimization (~7,000 tokens freed), comprehensive deferred task tracking with GitHub visibility, formal documentation of all Phase 1 PR review suggestions
**Changes in v2.21:**
- **REQUIREMENTS TRACEABILITY FIX + PHASE COMPLETION PROTOCOL ENHANCEMENTS**: Retroactive requirements creation for critical infrastructure + comprehensive protocol improvements to prevent future gaps
- Created REQ-CICD-004 (Pre-Commit Hooks Infrastructure) and REQ-CICD-005 (Pre-Push Hooks Infrastructure) retroactively for traceability
- Updated MASTER_REQUIREMENTS V2.14 → V2.15 (added REQ-CICD-004, REQ-CICD-005; updated REQ-CICD-003 status to Complete; 111 → 113 total requirements)
- Updated REQUIREMENT_INDEX V1.6 → V1.7 (added 2 new CI/CD requirements, updated statistics and cross-references)
- Updated PHASE_0.7_DEFERRED_TASKS V1.2 → V1.4 (linked REQ-CICD-004/005 to DEF-001/002, marked acceptance criteria complete)
- Enhanced PHASE_COMPLETION_ASSESSMENT_PROTOCOL V1.0 Step 6 with mandatory REQ creation decision tree (9 categories: Critical Infrastructure, Database, API, Testing, Security, Business Logic, Documentation)
- Enhanced PHASE_COMPLETION_ASSESSMENT_PROTOCOL V1.0 Step 7 with PR coverage verification (prevents recency bias - Phase 1 only analyzed 5/26 PRs = 19% coverage)
- Updated CLAUDE.md Section 9 (Phase Completion Protocol) with Step 6 and Step 7 enhancements
- Analyzed PRs #2-#21 for missed AI suggestions (80% coverage gap from Phase 1 completion) - identified 2 actionable items from PR #2 (verification script, ADR-054)
- **Context:** Phase 1 completion assessment gap - pre-commit/pre-push hooks (DEF-001/002) lacked formal requirements despite being critical infrastructure; branch protection (DEF-003) had REQ-CICD-003 creating inconsistency
- **Impact:** Complete requirements traceability for all Phase 0.7 infrastructure (audit-ready), prevents future gaps via mandatory decision tree, ensures 100% PR coverage in future phase completions
**Changes in v2.20:**
- **CODECOV + SENTRY INTEGRATION DOCUMENTATION**: Complete observability infrastructure documentation for pre-release coverage tracking and post-release error monitoring
- Created .codecov.yml (Codecov configuration for PR comments, 80% coverage thresholds, AI suggestions)
- Updated MASTER_REQUIREMENTS V2.13 → V2.14 (added REQ-OBSERV-002: Sentry Production Error Tracking with hybrid architecture)
- Updated ARCHITECTURE_DECISIONS V2.13 → V2.14 (added ADR-055: Sentry for Production Error Tracking - 380 lines documenting hybrid architecture integrating logger.py + Sentry + alerts table)
- Updated DEVELOPMENT_PHASES V1.8 → V1.9 (added Phase 2 Task #7: Sentry + Alert System Integration, 9.5h timeline)
- Updated PROJECT_OVERVIEW V1.4 → V1.5 (added Observability & Monitoring section to tech stack, sentry-sdk==2.0.0 to requirements)
- Updated REQUIREMENT_INDEX V1.5 → V1.6 (111 total requirements, added REQ-OBSERV-002 entry)
- Updated ADR_INDEX V1.8 → V1.9 (64 total ADRs, added Phase 2 Production Monitoring Infrastructure section with ADR-055)
- Hybrid architecture addresses orphaned infrastructure: logger.py (files only), alerts table (exists but unused), no real-time alerting
- 3-layer observability: Structured logging (audit trail) → Sentry (real-time) → alerts table (permanent record)
**Changes in v2.19:**
- **CLAUDE.MD SIZE REDUCTION (48.3%)**: Reduced CLAUDE.md from 3,723 to 1,924 lines (~60 KB saved)
- Created DEVELOPMENT_PATTERNS_V1.0.md (1,234 lines) - Extracted all 10 critical patterns with comprehensive examples
- Created DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md (858 lines) - Extracted document cohesion workflows and validation checklists
- Patterns extracted: Decimal precision, dual versioning, trade attribution, security, cross-platform, TypedDict, educational docstrings, config sync, warning governance, property-based testing
- Workflows extracted: Update Cascade Rules (6 scenarios), status field standards, consistency validation, document dependency map
- Total extraction: 2,092 lines from CLAUDE.md to dedicated guides (improved maintainability and navigation)
**Changes in v2.18:**
- **PHASES 6-9 IMPLEMENTATION GUIDES COMPLETE**: Added 4 comprehensive implementation guides (~2,100 lines total)
- Created PERFORMANCE_TRACKING_GUIDE_V1.0.md (487 lines, 8-level time-series aggregation with SQL/Python code)
- Created ANALYTICS_ARCHITECTURE_GUIDE_V1.0.md (625 lines, 4-layer architecture: Collection → Storage → Aggregation → Presentation)
- Created DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md (528 lines, React 18 + Next.js 14 + TypeScript + Socket.IO real-time integration)
- Created AB_TESTING_GUIDE_V1.0.md (460 lines, statistical methodology: Welch's t-test, Chi-square, sample size calculation)
- All guides support analytics infrastructure (ADR-078 through ADR-085) and strategic roadmap tasks
**Changes in v2.17:**
- **PHASES 6-9 ANALYTICS INFRASTRUCTURE DOCUMENTATION COMPLETE**: Added 8 ADRs (ADR-078 through ADR-085), 5 requirements (REQ-ANALYTICS-001-004, REQ-REPORTING-001), and MODEL_EVALUATION_GUIDE
- Updated ARCHITECTURE_DECISIONS V2.13 (same version, added 8 ADRs: model config storage, performance tracking, metrics collection, dashboard architecture, model evaluation, materialized views, A/B testing, hybrid JSONB strategy)
- Updated ADR_INDEX V1.7 → V1.8 (55 → 63 ADRs, added Phases 6-9 Analytics Infrastructure section)
- Updated REQUIREMENT_INDEX V1.4 → V1.5 (105 → 110 requirements, added ANALYTICS and REPORTING categories)
- Updated MASTER_REQUIREMENTS V2.12 → V2.13 (added analytics and reporting requirements)
- Updated DEVELOPMENT_PHASES V1.7 → V1.8 (added Phase 1.5 model evaluation framework tasks)
- Updated DATABASE_SCHEMA_SUMMARY V1.7 → V1.8 (25 → 34 tables, added 6 materialized views + 3 A/B testing tables)
- Updated STRATEGIC_WORK_ROADMAP V1.0 → V1.1 (added Phases 6-9 analytics tasks)
- Created MODEL_EVALUATION_GUIDE_V1.0.md (3-stage evaluation: backtesting, cross-validation, holdout validation)
- Total additions: ~7,150 lines of analytics infrastructure documentation
**Changes in v2.16:**
- **STRATEGIC RESEARCH PRIORITIES DOCUMENTED**: Open architectural questions requiring research before Phase 4+ implementation
- Updated ARCHITECTURE_DECISIONS V2.12 → V2.13 (added ADR-076 Dynamic Ensemble Weights, ADR-077 Strategy vs Method Separation - HIGHEST PRIORITY)
- Updated DEVELOPMENT_PHASES V1.6 → V1.7 (added CRITICAL RESEARCH PRIORITIES section, Phase 4.5 Ensemble Architecture Research)
- Created PHASE_4_DEFERRED_TASKS_V1.0.md (11 research tasks: DEF-009 to DEF-019, strategies #1 MOST IMPORTANT)
- Created STRATEGIC_WORK_ROADMAP_V1.0.md (25 strategic tasks organized by category, research dependencies documented)
- Research emphasis: Strategies (#1 MOST IMPORTANT), Models (#2), Edge Detection (#3)
- Data-driven approach: gather data (Phase 1-3) → research (Phase 4.5) → decide → implement (Phase 5+)
**Changes in v2.15:**
- **PHASE 0.7C COMPLETE**: Template enforcement automation implemented with Defense in Depth architecture
- Created scripts/validate_code_quality.py (314 lines) - enforces CODE_REVIEW_TEMPLATE (≥80% coverage, REQ test coverage, educational docstrings)
- Created scripts/validate_security_patterns.py (413 lines) - enforces SECURITY_REVIEW_CHECKLIST (API auth, hardcoded secrets, encryption, logging)
- Updated .pre-commit-config.yaml (2 new hooks: code-review-basics, decimal-precision-check)
- Updated .git/hooks/pre-push (2 new steps: Step 6/7 code quality, Step 7/7 security patterns)
- Updated MASTER_REQUIREMENTS V2.11 → V2.12 (added REQ-VALIDATION-005, REQ-VALIDATION-006)
- Updated REQUIREMENT_INDEX V1.3 → V1.4 (added 2 new validation requirements, total now 105 requirements)
- Updated DEVELOPMENT_PHASES V1.5 → V1.6 (added Phase 0.7c section with 8 success criteria)
- Updated CLAUDE.md V1.14 → V1.15 (updated pre-commit/pre-push hooks documentation with new validation steps)
- Cross-platform compatibility: All scripts use ASCII output for Windows cp1252 compatibility
- Defense in Depth: Pre-commit (~2-5s) → Pre-push (~60-90s) → CI/CD (~2-5min) multi-layer validation
**Changes in v2.14:**
- **PHASE 1.5 PROPERTY TESTING COMPLETE**: 40 property tests implemented (114% of 35-test target)
- Added PHASE_1.5_DEFERRED_PROPERTY_TESTS_V1.0.md (comprehensive roadmap for 74-91 additional property tests across Phases 1.5-4)
- Created tests/property/test_config_validation_properties.py (14 tests: Kelly fraction, edge thresholds, fees, loss/profit targets, correlation, Decimal conversion)
- Fixed ConfigLoader bug: Added 9 missing keys to Decimal conversion (default_fraction, min_edge_threshold, min_position_dollars, etc.)
- Phase 1.5 property testing status: Kelly Criterion (11 tests ✅), Edge Detection (15 tests ✅), Configuration Validation (14 tests ✅)
**Changes in v2.13:**
- **PYTHON 3.14 COMPATIBILITY**: Migrated from Bandit to Ruff security rules (--select S) for security scanning
- Added ADR-054 (Ruff Security Rules Instead of Bandit) to ARCHITECTURE_DECISIONS_V2.10 → V2.11
- Updated MASTER_REQUIREMENTS_V2.10 → V2.11 (REQ-TEST-006, REQ-CICD-001 updated for Ruff)
- Updated ADR_INDEX_V1.4 → V1.5 (added ADR-054, total ADRs: 52)
- Updated .git/hooks/pre-push (replaced Bandit with Ruff security scan)
- Updated .github/workflows/ci.yml (security-scan job now uses Ruff)
- Bandit 1.8.6 crashes on Python 3.14 (ast.Num removed), Ruff provides equivalent coverage with 10-100x better performance
**Changes in v2.12:**
- **PHASE 0.7 COMPLETE**: All 8 deferred tasks completed, comprehensive development philosophy documented
- Added DEVELOPMENT_PHILOSOPHY_V1.0.md (foundation document - TDD, DID, DDD, 9 core principles)
- Updated PHASE_0.7_DEFERRED_TASKS V1.1 → V1.2 (marked all 8 tasks complete: DEF-001 through DEF-008)
- Added validation script maintenance reminders to CLAUDE.md (Pattern 1, Pattern 2, SESSION_HANDOFF template)
- Updated PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md (8-step → 9-step: added validation scripts step)
- Updated DEVELOPMENT_PHASES_V1.5.md (added validation reminders to all 6 phase test planning checklists)
- Comprehensive Defense in Depth documentation (4-layer validation architecture)
- Phase 0.7 status: 100% complete (pre-commit hooks, pre-push hooks, branch protection, schema validation, all deferred tasks done)
**Changes in v2.11:**
- **PHASE 0.7 DEFERRED TASKS COMPLETION**: Marked DEF-003 and DEF-004 as complete
- Added GITHUB_BRANCH_PROTECTION_CONFIG.md (comprehensive branch protection documentation, completes DEF-003)
- Updated PHASE_0.7_DEFERRED_TASKS V1.0 → V1.1 (marked DEF-003 GitHub Branch Protection and DEF-004 Python 3.14 migration as complete)
- Added complete GitHub branch protection configuration with API reproduction commands, troubleshooting guide, and security implications
- Documents all 5 required status checks, admin enforcement, and verification procedures
**Changes in v2.10:**
- **VERSION MISMATCH CORRECTIONS**: Fixed all version discrepancies in foundation documents table
- Updated ARCHITECTURE_DECISIONS V2.9 → V2.10 (table showed V2.8, actual was V2.10)
- Updated ADR_INDEX V1.2 → V1.4 (table showed V1.2, actual was V1.4)
- Updated DATABASE_SCHEMA_SUMMARY V1.6 → V1.7 (table showed V1.6, actual was V1.7)
- Updated MASTER_INDEX self-reference from V2.7 to V2.10 (table entry for "THIS FILE")
- Corrected MASTER_REQUIREMENTS table entry to reflect existing V2.10 version
- **CODE QUALITY**: Fixed all CI failures - Mypy (6 errors → 0), Ruff (220 violations → 0)
- Installed types-PyYAML for complete type coverage
- Updated pyproject.toml to allow unused pytest fixtures (ARG002) in test files
**Changes in v2.9:**
- **GUIDES FOLDER CREATED**: Moved 5 implementation guides from supplementary/ and configuration/ to new docs/guides/ folder
- Moved CONFIGURATION_GUIDE_V3.1.md from `/docs/configuration/` to `/docs/guides/`
- Moved VERSIONING_GUIDE_V1.0.md from `/docs/supplementary/` to `/docs/guides/`
- Moved TRAILING_STOP_GUIDE_V1.0.md from `/docs/supplementary/` to `/docs/guides/`
- Moved POSITION_MANAGEMENT_GUIDE_V1.0.md from `/docs/supplementary/` to `/docs/guides/`
- Moved POSTGRESQL_SETUP_GUIDE.md from `/docs/supplementary/` to `/docs/guides/`
- Supplementary folder reduced from 16 to 11 documents (cleaner organization)
- Aligns documentation structure with CLAUDE.md Section 6 (Implementation Guides)
- Improves discoverability: guides no longer buried among specs/research/analysis docs
**Changes in v2.8:**
- **PHASE 1 API BEST PRACTICES**: Added ADRs and requirements for API integration best practices
- Updated ARCHITECTURE_DECISIONS V2.8 → V2.9 (added ADR-047 through ADR-052: Pydantic validation, circuit breaker, correlation IDs, connection pooling, log masking, YAML validation)
- Updated ADR_INDEX V1.2 → V1.3 (added 6 new ADRs, total now 50 ADRs)
- Updated MASTER_REQUIREMENTS V2.9 → V2.10 (added REQ-API-007, REQ-OBSERV-001, REQ-SEC-009, REQ-VALIDATION-004)
- Updated REQUIREMENT_INDEX V1.2 → V1.3 (added 4 new requirements in 3 categories: API, Observability, Security, Validation; total now 103 requirements)
- Added PHASE_1_TEST_PLAN_V1.0.md (testing & quality documents section)
- Added PHASE_0.7_DEFERRED_TASKS_V1.0.md (utility documents section)
- All foundation documents now reference updated versions (ADRs, REQs)
**Changes in v2.7:**
- **PHASE 0.6C COMPLETION**: Added validation and testing infrastructure
- Updated ARCHITECTURE_DECISIONS V2.7 → V2.8 (added ADR-038 through ADR-045 for validation, testing, and CI/CD)
- Updated ADR_INDEX V1.1 → V1.2 (added 8 new ADRs, total now 44 ADRs)
- Updated MASTER_REQUIREMENTS V2.8 → V2.9 (added REQ-TEST-005-008, REQ-VALIDATION-001-003, REQ-CICD-001-003)
- Updated REQUIREMENT_INDEX V1.1 → V1.2 (added 10 new requirements, total now 99 requirements)
- Updated DEVELOPMENT_PHASES V1.3 → V1.4 (added Phase 0.6b, Phase 0.6c complete, Phase 0.7 planned)
- Updated TESTING_STRATEGY V1.0 → V2.0 (added future enhancements: mutation testing, property-based testing, CI/CD integration)
- Added VALIDATION_LINTING_ARCHITECTURE_V1.0.md (new foundation document for code quality and documentation validation)
- All foundation documents now reflect Phase 0.6c completion and Phase 0.7 planning
**Changes in v2.6:**
- **PHASE 0.6B DOCUMENTATION CORRECTION**: Renamed 10 supplementary documents with standardized naming (removed PHASE_ prefixes, standardized V1.0 format)
- Updated MASTER_REQUIREMENTS V2.7 → V2.8 (added Section 4.10 CLI requirements, Phase 1 expansion to 6 weeks, updated supplementary doc references)
- Updated ARCHITECTURE_DECISIONS V2.6 → V2.7 (added ADR-035, ADR-036, ADR-037 for Phase 5 Trading Architecture)
- Updated ADR_INDEX V1.0 → V1.1 (added 3 new ADRs, updated doc references)
- Renamed 10 files: VERSIONING_GUIDE_V1.0.md, TRAILING_STOP_GUIDE_V1.0.md, POSITION_MANAGEMENT_GUIDE_V1.0.md, SPORTS_PROBABILITIES_RESEARCH_V1.0.md, ORDER_EXECUTION_ARCHITECTURE_V1.0.md, ADVANCED_EXECUTION_SPEC_V1.0.md, EVENT_LOOP_ARCHITECTURE_V1.0.md, EXIT_EVALUATION_SPEC_V1.0.md, POSITION_MONITORING_SPEC_V1.0.md, USER_CUSTOMIZATION_STRATEGY_V1.0.md
- All supplementary docs initially moved to `/docs/supplementary/` (guides/ folder created in v2.9)
- Added "RENAMED" notes for traceability
**Changes in v2.5:**
- **PHASE 1 FOUNDATION**: Updated documentation for alerts/notifications system and ML infrastructure planning
- Updated MASTER_REQUIREMENTS V2.6 → V2.7 (added 7 missing tables, REQ-METH-001 through REQ-METH-015, REQ-ALERT-001 through REQ-ALERT-015, REQ-ML-001 through REQ-ML-004)
- Updated REQUIREMENT_INDEX V1.0 → V1.1 (added 34 new requirements across 3 categories: Methods, Alerts, ML)
- Updated DATABASE_SCHEMA_SUMMARY V1.5 → V1.6 (added alerts table + 4 ML infrastructure placeholders for Phase 9)
- Updated system.yaml with comprehensive notifications configuration (email, SMS, Slack, webhook, alert_routing)
- Verified alerts migration SQL exists (002_add_alerts_table.sql)
- Added 4 planned ML documentation references (MACHINE_LEARNING_ROADMAP, PROBABILITY_PRIMER, ELO_IMPLEMENTATION_GUIDE, MODEL_EVALUATION_GUIDE)
- Updated document count: 35 → 39 documents (4 new planned ML docs)
- Updated table count: 18 → 25 tables (7 operational + 4 ML placeholders + alerts + methods/method_templates)

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
| **PROJECT_OVERVIEW_V1.5.md** | ✅ | v1.5 | `/docs/foundation/` | 0 | All phases | 🔴 Critical | System architecture, tech stack, directory tree - **UPDATED V1.5** (added Observability & Monitoring: Codecov + Sentry hybrid architecture, sentry-sdk==2.0.0) |
| **MASTER_REQUIREMENTS_V2.15.md** | ✅ | v2.15 | `/docs/foundation/` | 0 | All phases | 🔴 Critical | Complete requirements through Phase 10 with REQ IDs - **UPDATED V2.15** (added REQ-CICD-004: Pre-Commit Hooks, REQ-CICD-005: Pre-Push Hooks retroactively for Phase 0.7 traceability; updated REQ-CICD-003 status to Complete; 111 → 113 total requirements) |
| **MASTER_INDEX_V2.24.md** | ✅ | v2.24 | `/docs/foundation/` | 0 | All phases | 🔴 Critical | THIS FILE - complete document inventory - **UPDATED V2.24** (Added PHASE_1.5_TEST_PLAN_V1.0.md to testing & quality documents section) |
| **ARCHITECTURE_DECISIONS_V2.15.md** | ✅ | v2.15 | `/docs/foundation/` | 0 | Phases 1-10 | 🟡 High | Design rationale with ADR numbers (86 total) - **UPDATED V2.15** (ADR-046: Branch Protection Strategy added retroactively for Phase 0.7 traceability; ADR-055: Sentry Production Error Tracking) |
| **REQUIREMENT_INDEX.md** | ✅ | v1.7 | `/docs/foundation/` | 0 | All phases | 🔴 Critical | Systematic catalog of all 113 requirements (REQ-{CATEGORY}-{NUMBER}) - **UPDATED V1.7** (added REQ-CICD-004: Pre-Commit Hooks, REQ-CICD-005: Pre-Push Hooks; updated REQ-CICD-003 status to Complete) |
| **ADR_INDEX_V1.10.md** | ✅ | v1.10 | `/docs/foundation/` | 0 | All phases | 🔴 Critical | Systematic catalog of all 65 architecture decisions - **UPDATED V1.10** (ADR-046: Branch Protection Strategy added retroactively for Phase 0.7) |
| **GLOSSARY.md** | ✅ | n/a | `/docs/foundation/` | 0 | All phases | 🟢 Medium | Terminology reference (living document, no version) |
| **DEVELOPMENT_PHASES_V1.5.md** | ✅ | v1.5 | `/docs/foundation/` | 0 | All phases | 🟡 High | Complete roadmap Phase 0-10 - **CURRENT V1.5** |
| **TESTING_STRATEGY_V2.1.md** | ✅ | v2.1 | `/docs/foundation/` | 0.6c | Phases 1-10 | 🟡 High | **UPDATED V2.1** - Added Coverage Target Workflow: tier-based targets (Critical ≥90%, Business ≥85%, Infrastructure ≥80%), PR tracking template, acceptable gap criteria, phase completion validation checklist |
| **VALIDATION_LINTING_ARCHITECTURE_V1.0.md** | ✅ | v1.0 | `/docs/foundation/` | 0.6c | Phases 0.6c-0.7 | 🟡 High | **NEW** - Code quality and documentation validation architecture (Phase 0.6c) |
| **DEVELOPMENT_PHILOSOPHY_V1.2.md** | ✅ | v1.2 | `/docs/foundation/` | 0.7 | All phases | 🔴 Critical | **UPDATED V1.2** - Added Section 10: Security-First Testing (tests validate security works, not bypassed); renumbered Anti-Patterns → Section 11, Test Coverage Accountability → Section 12; cross-references Pattern 12 and PR #79 |

---

## API & Integration Documents

External API documentation, integration guides, and authentication specs.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **API_INTEGRATION_GUIDE_V2.0.md** | ✅ | v2.0 | `/docs/api-integration/` | 1 | Phases 1-2, 6, 10 | 🔴 Critical | **UPDATED V2.0** - Merged Kalshi/ESPN/Balldontlie, RSA-PSS auth examples, API best practices |
| **KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md** | ✅ | v1.0 | `/docs/api-integration/` | 1 | Phases 1-5 | 🔴 Critical | **PRINT & KEEP AT DESK** - Critical reference |
| **KALSHI_API_STRUCTURE_COMPREHENSIVE_V2.0.md** | ⚠️ | v2.0 | `/docs/api-integration/` | 1 | Phases 1-5 | 🟡 High | ⚠️ Merged into API_INTEGRATION_GUIDE, mark archived |
| **KALSHI_DATABASE_SCHEMA_CORRECTED_V1.0.md** | ✅ | v1.0 | `/docs/api-integration/` | 1 | Phase 1 | 🟢 Medium | Kalshi-specific schema corrections |

---

## Database & Data Documents

Schema design, data models, and database architecture.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **DATABASE_SCHEMA_SUMMARY_V1.8.md** | ✅ | v1.8 | `/docs/database/` | 0.5-1 | Phases 1-10 | 🔴 Critical | **UPDATED V1.8** - Complete schema with migrations 001-010, 34 tables (25 operational + 6 materialized views + 3 A/B testing tables) |
| **DATABASE_TABLES_REFERENCE.md** | ✅ | v1.0 | `/docs/database/` | 1 | Phases 1-10 | 🟡 High | Quick lookup for all tables, common queries (Phase 1) |
| **ODDS_RESEARCH_COMPREHENSIVE.md** | ✅ | v1.0 | `/docs/database/` | 4 | Phase 4, 9 | 🟡 High | Historical odds methodology, merged into models |
| **DATA_DICTIONARY.md** | 🔵 | - | `/docs/database/` | 6-7 | Phases 6-10 | 🟡 High | Comprehensive data dictionary - all columns documented (planned Phase 6-7) |

---

## Configuration Documents

YAML configuration files and configuration guides.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **CONFIGURATION_GUIDE_V3.1.md** | ✅ | v3.1 | `/docs/guides/` | 0.5 | Phases 1-10 | 🟡 High | **MOVED** from /configuration/ - Comprehensive update with all 7 YAMLs, versioning, method abstraction |
| **system.yaml** | ✅ | v1.0 | `/config/` | 1 | Phases 1-10 | 🔴 Critical | **UPDATED** - Added comprehensive notifications config (email, SMS, Slack, webhook, alert_routing) |
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
| **TESTING_STRATEGY_V2.1.md** | ✅ | v2.1 | `/docs/foundation/` | 0.6c | Phases 1-10 | 🟡 High | **UPDATED V2.1** - Added Coverage Target Workflow: tier-based targets, PR tracking template, acceptable gap criteria, phase completion validation |
| **PHASE_1_TEST_PLAN_V1.0.md** | ✅ | v1.0 | `/docs/testing/` | 1 | Phase 1 | 🟡 High | **NEW** - Comprehensive test plan for Phase 1 (database, API, CLI) with test cases, fixtures, and success criteria |
| **PHASE_1.5_TEST_PLAN_V1.0.md** | ✅ | v1.0 | `/docs/testing/` | 1.5 | Phase 1.5 | 🟡 High | **NEW** - Test plan for Phase 1.5 (Strategy Manager, Model Manager, Position Manager enhancements) with comprehensive test scenarios and success criteria |
| **HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md** | ✅ | v1.0 | `/docs/testing/` | 1.5 | Phase 1.5 | 🟡 High | **NEW** - Property-based testing strategy with Hypothesis framework (3 test suites: Kelly Criterion, Edge Detection, Configuration Validation; 35+ tests implemented) |
| **MODEL_VALIDATION_V1.0.md** | 🔵 | - | `/docs/testing/` | 4 | Phase 4 ✅ | 🟡 High | Elo vs. research, backtesting benchmarks |
| **BACKTESTING_PROTOCOL_V1.0.md** | 🔵 | - | `/docs/testing/` | 4 | Phase 4-5 ✅ | 🟡 High | Walk-forward validation, train/test splits |

---

## Phases & Planning Documents

Roadmap, timelines, and project management.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **DEVELOPMENT_PHASES_V1.5.md** | ✅ | v1.5 | `/docs/foundation/` | 0.5 | All phases | 🟡 High | Phase 0.5 complete, Phase 5 split into 5a/5b - UPDATED Phase 0.7 |
| **DEPLOYMENT_GUIDE_V1.0.md** | 🔵 | - | `/docs/deployment/` | 1 | Phase 1 ✅ | 🟡 High | Local/AWS deployment stubs |
| **USER_GUIDE_V1.0.md** | 🔵 | - | `/docs/guides/` | 5 | Phase 5 ✅ | 🟢 Medium | CLI examples (edges-list, trade-execute) |
| **DEVELOPER_ONBOARDING_V1.0.md** | 🔵 | - | `/docs/utility/` | 0 | Phase 0 ✅ | 🟡 High | Merged with ENVIRONMENT_CHECKLIST, onboarding steps |

---

## Implementation Guides

Phase-specific implementation guides created in Phase 0.5.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **VERSIONING_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 0.5 | Phases 4-9 | 🔴 Critical | **MOVED** from /supplementary/ - Immutable versioning for strategies and models |
| **TRAILING_STOP_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 0.5 | Phases 1, 4, 5 | 🔴 Critical | **MOVED** from /supplementary/ - Trailing stop loss implementation guide |
| **POSITION_MANAGEMENT_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 0.5 | Phase 5 | 🔴 Critical | **MOVED** from /supplementary/ - Position lifecycle, 10 exit conditions, monitoring, execution |
| **MODEL_EVALUATION_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 1.5 | Phases 1.5, 4, 9 | 🔴 Critical | **NEW** - 3-stage model evaluation framework: backtesting, cross-validation, holdout validation; calibration metrics (Brier score, ECE, log loss); systematic evaluation protocol |
| **PERFORMANCE_TRACKING_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 6 | Phase 6 | 🔴 Critical | **NEW** - 8-level time-series aggregation (trade→hourly→daily→weekly→monthly→quarterly→yearly→all_time), SQL UPSERT patterns, pg_cron scheduling, 158x-683x query speedup |
| **ANALYTICS_ARCHITECTURE_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 6-9 | Phases 6-9 | 🔴 Critical | **NEW** - End-to-end analytics architecture: 4-layer design (Collection→Storage→Aggregation→Presentation), dual processing (real-time <200ms + batch), 6 materialized views |
| **AB_TESTING_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 8 | Phase 8 | 🟡 High | **NEW** - Statistical methodology for strategy/model evaluation: Welch's t-test, Chi-square, sample size calculation (64 trades/variant), Bayesian analysis, experiment lifecycle |
| **DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 9 | Phase 9 | 🟡 High | **NEW** - React 18 + Next.js 14 trading dashboard: component library (MetricCard, PositionCard), Socket.IO real-time (<200ms), SWR data fetching, Plotly.js charts, deployment |
| **DEVELOPMENT_PATTERNS_V1.3.md** | ✅ | v1.3 | `/docs/guides/` | All | All phases | 🔴 Critical | **UPDATED V1.3** - Added Pattern 12: Test Fixture Security Compliance (project-relative fixtures for security-validated functions); documents Generator pattern, UUID for unique filenames, when to use project-relative vs tmp_path; real-world example from PR #79 (9/25 failing → 25/25 passing, 68.32% → 89.11% coverage) |
| **SENTRY_INTEGRATION_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 2 | Phase 2 | 🟡 High | **NEW** - 3-layer hybrid observability architecture: logger.py (audit trail) + Sentry (real-time) + alerts table (permanent record); implementation guide with code examples, testing procedures, troubleshooting |
| **POSTGRESQL_SETUP_GUIDE.md** | ✅ | v1.0 | `/docs/guides/` | 0 | Phase 1 | 🟡 High | **MOVED** from /supplementary/ - Database installation and configuration (Windows/Linux/Mac) |
| **DEVELOPER_SETUP_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/guides/` | 1 | Phase 1.5 | 🟡 High | **NEW** - Comprehensive developer onboarding guide (Python 3.12+, PostgreSQL 15+, Git, GitHub CLI, pre-commit hooks); platform-specific instructions (Windows/macOS/Linux); addresses gh CLI dependency risk from Phase Completion assessment |

---

## Utility Documents

Handoffs, logs, maintenance protocols, and project management utilities.

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **PROJECT_STATUS.md** | ✅ | v1.1 (header) | `/docs/utility/` | 0 | All phases | 🔴 Critical | **LIVING DOC** - upload every session, merged STATUS+README+QUICK_START |
| **DOCUMENT_MAINTENANCE_LOG.md** | ✅ | v1.1 (header) | `/docs/utility/` | 0 | All phases | 🔴 Critical | **LIVING DOC** - upload every session, tracks changes with upstream/downstream impacts |
| **SESSION_HANDOFF_TEMPLATE.md** | ✅ | template | `/docs/utility/` | 0 | All phases | 🔴 Critical | Streamlined ~1 page template, inline instructions |
| **CODE_REVIEW_TEMPLATE_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | 0.7b | All phases | 🔴 Critical | **NEW (Phase 0.7b)** - Code review template with 3 sections: Requirements Traceability, Test Coverage (≥80%), Code Quality (Pattern 7 docstrings); enforced by validate_code_quality.py |
| **SECURITY_REVIEW_CHECKLIST.md** | ✅ | v1.1 | `/docs/utility/` | 0.7b | All phases | 🔴 Critical | **NEW (Phase 0.7b)** - Security review checklist with 5 sections: Credential Management, Input Validation, API Security, Data Protection, Incident Response; enforced by validate_security_patterns.py |
| **DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | All | All phases | 🔴 Critical | **NEW** - Document cohesion & consistency workflows extracted from CLAUDE.md: Update Cascade Rules (6 scenarios), status field standards, consistency validation checklists, document dependency map; prevents documentation drift |
| **SESSION_WORKFLOW_GUIDE_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | All | All phases | 🔴 Critical | **NEW** - Comprehensive session workflows extracted from CLAUDE.md V1.17 Section 3 (9 sections): starting sessions, phase start protocol, git safety, recovery patterns, multi-session coordination, pre-commit/pre-push hooks, ending sessions, phase transitions, deferred task tracking; follows V1.16 extraction pattern |
| **SESSION_7_HANDOFF.md** | ✅ | - | `/docs/sessions/` | 0 | Session 7 | 🟡 High | Latest session handoff (session # is version) |
| **SESSION_6_HANDOFF.md** | ✅ | - | `/docs/sessions/` | 0 | Session 6 | 🟢 Medium | Previous session handoff |
| **Handoff_Protocol_V1_1.md** | ✅ | v1.1 | `/docs/utility/` | 0 | All phases | 🔴 Critical | **UPDATED V1.1** - Merged 4 docs: HANDOFF_PROCESS + TOKEN_MONITORING + PHASE_COMPLETION + KNOWLEDGE_STRATEGY (V1.0 archived) |
| **VERSION_HEADERS_GUIDE_V2_1.md** | ✅ | v2.1 | `/docs/utility/` | 0 | All phases | 🟡 High | Version control standards, references Handoff_Protocol (**FIXED** filename from V2.1 → V2_1) |
| **PHASE_0.7_DEFERRED_TASKS_V1.4.md** | ✅ | v1.4 | `/docs/utility/` | 0.7 | Phase 0.7 | 🟡 High | **PHASE 0.7 COMPLETE** - All 8/8 tasks complete (DEF-001 through DEF-008: pre-commit, pre-push, branch protection, schema validation, all hooks) - **UPDATED V1.4** (linked REQ-CICD-004/005 to DEF-001/002 for requirements traceability, marked acceptance criteria complete) |
| **GITHUB_BRANCH_PROTECTION_CONFIG.md** | ✅ | v1.0 | `/docs/utility/` | 0.7 | Phase 0.7 | 🟡 High | **NEW** - Complete GitHub branch protection configuration (completes DEF-003) |
| **PHASE_1_DEFERRED_TASKS_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | 1 | Phase 1 | 🟡 High | **NEW** - Tracks deferred enhancements from Phase 1 (extended docstrings, pre-commit hooks, branch protection) |
| **PHASE_1_PR_REVIEW_DEFERRED_TASKS_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | 1 | Phase 1.5 | 🔴 Critical | **NEW** - Dual-tracking system for 45 actionable items from PRs #2-#21 AI reviews: 3 critical (float usage/Pattern 1, zero test coverage, path sanitization), 8 high, 18 medium, 16 low priority; GitHub issues #29-#73 with bi-directional links; prevents "4 out of 7 tasks lost" problem |
| **PHASE_1.5_DEFERRED_PROPERTY_TESTS_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | 1.5 | Phase 1.5-4 | 🟡 High | **NEW** - Comprehensive property-based testing roadmap (74-91 tests deferred to Phases 1.5-4: database CRUD, strategy versioning, position lifecycle, async handling, ensemble predictions) |
| **PHASE_4_DEFERRED_TASKS_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | 4.5 | Phase 4.5 | 🔴 Critical | **NEW** - Comprehensive research task documentation (11 tasks: DEF-009 to DEF-019, strategies HIGHEST PRIORITY, models, edge detection) - ~2800 lines, 74-92 hour total effort |
| **STRATEGIC_WORK_ROADMAP_V1.1.md** | ✅ | v1.1 | `/docs/utility/` | 1-10 | All phases | 🔴 Critical | **UPDATED V1.1** - Master roadmap of 25 strategic tasks + Phases 6-9 analytics tasks (performance tracking, dashboards, A/B testing) organized by category |
| **ENVIRONMENT_CHECKLIST_V1.0.md** | ✅ | v1.0 | `/docs/utility/` | 0 | Phase 0 ✅ | 🔴 Critical | Windows 11 setup, Parts 1-7, dependencies verification (**FIXED** filename from V1.1 → V1.0) |
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

### Supplementary Guides (Phase 0.5/0.6)

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **USER_CUSTOMIZATION_STRATEGY_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 0.5 | Phases 1-10 | 🟡 High | User configuration and customization strategy |
| **SPORTS_PROBABILITIES_RESEARCH_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 4 | Phases 4, 9 | 🟡 High | **RENAMED** - Historical win probability benchmarks for NFL, NBA, tennis |

### Supplementary Specifications (Phase 5+)

| Document | Status | Version | Location | Phase | Phase Ties | Priority | Notes |
|----------|--------|---------|----------|-------|------------|----------|-------|
| **ORDER_EXECUTION_ARCHITECTURE_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5 | Phases 5-8 | 🟡 High | **RENAMED** from ORDER_EXECUTION_ARCHITECTURE_ASSESSMENT_V1_0.md - Order execution architecture |
| **ADVANCED_EXECUTION_SPEC_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5b | Phase 5b, 8 | 🟡 High | **RENAMED** from PHASE_8_ADVANCED_EXECUTION_SPEC.md - Dynamic depth walker implementation |
| **EVENT_LOOP_ARCHITECTURE_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5a | Phase 5a | 🟡 High | **RENAMED** from PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md - Trading event loop architecture |
| **EXIT_EVALUATION_SPEC_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5a | Phase 5a | 🟡 High | **RENAMED** from PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md - Exit evaluation strategy |
| **POSITION_MONITORING_SPEC_V1.0.md** | ✅ | v1.0 | `/docs/supplementary/` | 5a | Phase 5a | 🟡 High | **RENAMED** from PHASE_5_POSITION_MONITORING_SPEC_V1_0.md - Position monitoring specification |

### Other Supplementary Documents

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
| **PROBABILITY_PRIMER.md** | 🔵 | 4 | Phase 4 | 🟡 High | **NEW** - Intro to probability concepts for beginners (Phase 4) |
| **ELO_IMPLEMENTATION_GUIDE.md** | 🔵 | 4 | Phase 4, 6 | 🟡 High | **NEW** - Elo rating implementation and sport-specific tuning (Phase 4-6) |
| **MODEL_EVALUATION_GUIDE.md** | 🔵 | 9 | Phase 9 | 🟡 High | **NEW** - Model validation, backtesting, performance metrics (Phase 9) |
| **MACHINE_LEARNING_ROADMAP.md** | 🔵 | 9 | Phase 9 | 🟡 High | **NEW** - ML infrastructure evolution from Elo → XGBoost/LSTM (Phase 9) |
| **POLYMARKET_INTEGRATION_GUIDE.md** | 🔵 | 10 | Phase 10 | 🟡 High | Multi-platform Phase 10 |
| **CROSS_PLATFORM_ARBITRAGE.md** | 🔵 | 10 | Phase 10 | 🟡 High | Kalshi vs Polymarket |
| **WEB_DASHBOARD_GUIDE.md** | 🔵 | 10+ | Phase 10+ | 🟢 Medium | React + FastAPI monitoring |

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
- ✅ **Exists - Current:** 35 documents (includes 2 index documents, alerts migration, ML placeholders)
- ⚠️ **Exists - Needs Update:** 1 document (KALSHI_API_STRUCTURE → merge complete)
- 📝 **In Progress:** 0 documents
- ❌ **Missing - Critical:** 0 documents (Phase 0.5 complete + Standardization complete + Alerts/ML planning complete!)
- 🔵 **Missing - Planned:** 43+ documents (Phases 1-10, includes 4 new ML docs)
- 🗄️ **Archived:** 9 documents (7 from Session 7 streamline)

### Document Count by Phase
- **Phase 0 (Foundation):** 25 documents ✅ 100% complete
- **Phase 0.5 (Foundation Enhancement):** 8 documents ✅ 100% complete (3 guides + 3 YAML updates + 2 index documents)
- **Phase 1-3 (Core):** 15 documents planned
- **Phase 4-5 (Trading & Validation):** 12 documents planned
- **Phase 6-7 (Multi-Sport):** 8 documents planned
- **Phase 8-9 (Non-Sports & Advanced):** 10 documents planned
- **Phase 10+ (Multi-Platform & Dashboard):** 8 documents planned

### Phase 0.5 Status: ✅ 100% COMPLETE (Including Standardization + Alerts/ML Planning)

**All Phase 0.5 deliverables complete (Days 1-10 + Standardization + Phase 1 Foundation):**
- ✅ DATABASE_SCHEMA_SUMMARY_V1.6.md (added alerts table + 4 ML infrastructure placeholders)
- ✅ MASTER_REQUIREMENTS_V2.7.md (added 34 requirements: REQ-METH, REQ-ALERT, REQ-ML)
- ✅ REQUIREMENT_INDEX.md V1.1 (updated with 89 total requirements)
- ✅ ARCHITECTURE_DECISIONS_V2.5.md (ADR numbers added for all decisions)
- ✅ ADR_INDEX.md (systematic ADR catalog)
- ✅ PROJECT_OVERVIEW_V1.4.md
- ✅ DEVELOPMENT_PHASES_V1.5.md (Phase 5 split into 5a/5b)
- ✅ system.yaml (added comprehensive notifications configuration)
- ✅ position_management.yaml V2.0 (10 exit conditions)
- ✅ probability_models.yaml V2.0 (versioning)
- ✅ trade_strategies.yaml V2.0 (versioning)
- ✅ CONFIGURATION_GUIDE_V3.1.md (comprehensive)
- ✅ VERSIONING_GUIDE_V1.0.md (immutable versions)
- ✅ TRAILING_STOP_GUIDE_V1.0.md (trailing stop implementation)
- ✅ POSITION_MANAGEMENT_GUIDE_V1.0.md (complete position lifecycle)
- ✅ 002_add_alerts_table.sql (database migration)
- ✅ MASTER_INDEX_V2.5.md (this file)
- ✅ 4 ML documentation files planned (PROBABILITY_PRIMER, ELO_IMPLEMENTATION_GUIDE, MODEL_EVALUATION_GUIDE, MACHINE_LEARNING_ROADMAP)

**Ready for Phase 1 implementation**

### Phase 0 Status: ✅ 100% COMPLETE

**All critical blockers resolved:**
- ✅ MASTER_REQUIREMENTS_V2.6.md
- ✅ All 7 YAML configuration files
- ✅ .env.template
- ✅ ENVIRONMENT_CHECKLIST_V1.1.md
- ✅ DATABASE_SCHEMA_SUMMARY_V1.5.md
- ✅ Handoff system streamlined (73% doc reduction)
- ✅ Version control applied across all docs
- ✅ Phase alignment corrected (Phases 3/4 sequencing)
- ✅ Historical model integration complete
- ✅ Documentation standardization complete (REQ/ADR IDs)

---

## Project Knowledge Strategy

### ✅ Documents IN Project Knowledge
**Criteria:** Stable, reference documents, rarely change (monthly or less)

**Currently IN Project Knowledge:**
- MASTER_INDEX_V2.5.md (this file - navigation)
- PROJECT_OVERVIEW_V1.3.md (architecture)
- MASTER_REQUIREMENTS_V2.7.md (requirements with REQ IDs - includes methods, alerts, ML)
- ARCHITECTURE_DECISIONS_V2.5.md (design rationale with ADR numbers)
- REQUIREMENT_INDEX.md V1.1 (requirement catalog - 89 requirements)
- ADR_INDEX.md (ADR catalog)
- CONFIGURATION_GUIDE_V3.1.md (config patterns)
- DATABASE_SCHEMA_SUMMARY_V1.6.md (schema - 25 tables including alerts + ML placeholders)
- API_INTEGRATION_GUIDE_V1.0.md (API docs)
- KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md (critical reference)
- DEVELOPMENT_PHASES_V1.5.md (roadmap)
- GLOSSARY.md (terminology)
- Handoff_Protocol_V1.0.md (process reference)
- VERSIONING_GUIDE_V1.0.md (versioning patterns)
- TRAILING_STOP_GUIDE_V1.0.md (trailing stop implementation)
- POSITION_MANAGEMENT_GUIDE_V1.0.md (position lifecycle)

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
**Phase 0.5 Assessment:** ✅ Complete (all Days 1-10 finished + standardization, ready for Phase 1)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.5 | 2025-10-24 | **ALERTS & ML PLANNING**: Updated MASTER_REQUIREMENTS V2.6→V2.7 (34 new requirements), REQUIREMENT_INDEX V1.0→V1.1 (89 total reqs), DATABASE_SCHEMA_SUMMARY V1.5→V1.6 (alerts + 4 ML placeholders), system.yaml (notifications config); added 4 ML docs to planned (PROBABILITY_PRIMER, ELO_IMPLEMENTATION_GUIDE, MODEL_EVALUATION_GUIDE, MACHINE_LEARNING_ROADMAP); 25 total tables; ready for Phase 1 |
| 2.4 | 2025-10-22 | Added REQUIREMENT_INDEX.md and ADR_INDEX.md; updated MASTER_REQUIREMENTS V2.6, ARCHITECTURE_DECISIONS V2.5; updated document count 33 → 35; standardization complete |
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
