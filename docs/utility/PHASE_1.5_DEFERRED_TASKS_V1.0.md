# Phase 1.5 Deferred Tasks

---
**Version:** 1.1
**Created:** 2025-11-22
**Updated:** 2025-11-22
**Phase:** Phase 1.5 - Foundation Validation (Codename: "Verify")
**Target Completion:** Phase 2 Week 1
**Total Tasks:** 2
**Total Time Estimate:** 11-14 hours
---

## Purpose

This document tracks non-blocking tasks deferred from Phase 1.5 to future phases. These tasks are **important but not critical** for Phase 2 to begin.

**Deferred Task Philosophy:**
- Tasks must be **non-blocking** (Phase 2 can start without them)
- Tasks should be **infrastructure/enhancement** (not core features)
- Tasks must be **formally documented** with clear success criteria
- Tasks must have **target phase** and **priority level**

**Reference:** CLAUDE.md Section "Phase Completion Protocol" Step 6 (Deferred Tasks Workflow)

---

## Task Summary

| Task ID | Description | Priority | Target Phase | Time Est. | Status |
|---------|-------------|----------|--------------|-----------|--------|
| DEF-P1.5-001 | Configuration System Enhancement | 🟡 High | Phase 2 Week 1 | 6-8h | 🔵 Pending |
| DEF-P1.5-002 | Fix 21 Validation Violations (19 SCD + 2 fixtures) | 🔴 Critical | Phase 2 Week 1 | 5-6h | 🔵 Pending |

---

## Critical Priority Tasks (🔴)

### DEF-P1.5-002: Fix 21 Validation Violations (19 SCD + 2 fixtures)

**Priority:** 🔴 Critical
**Target Phase:** Phase 2 Week 1
**Time Estimate:** 5-6 hours
**Category:** Code Quality / Pattern Compliance
**GitHub Issue:** #101

#### Rationale

These 21 violations were discovered by enhanced pre-push hooks during Phase 1.5 completion and deferred to Phase 2 because:

1. **Non-Blocking for Phase 2 Start:** These are existing code quality issues in Phase 1.5 deliverables, not blockers for Phase 2 ESPN integration
2. **Validation Enhancement Discovery:** New validation scripts (validate_scd_queries.py, validate_test_fixtures.py) discovered violations that existed before but weren't detected
3. **Pattern Compliance, Not Functionality:** Code works correctly but violates Pattern 2 (SCD Type 2 filtering) and Pattern 13 (Real Fixtures)
4. **Follows Pattern 18 (Avoid Technical Debt):** Formally tracked in GitHub Issue #101, scheduled for Phase 2 Week 1, documented in deferred tasks
5. **Testing Debt Workflow:** User explicitly chose this deferral to validate our technical debt tracking process

**Why Critical Priority:**
- Pattern 2 violations risk accidentally querying historical data (subtle bugs)
- Pattern 13 violations mean integration tests may pass with bugs (false confidence)
- Should be fixed BEFORE significant Phase 2 development to prevent propagation

#### Violations Detail

**Part 1: SCD Type 2 Query Violations (19 violations)**

Pattern 2 (Dual Versioning) requires all queries on SCD Type 2 tables to filter by `row_current_ind = TRUE`. The following production code queries are missing this filter:

```
1. src/precog/database/crud_operations.py:625
   Function: get_market_history()
   Issue: Intentionally fetches all versions for audit (legitimate exception)
   Fix: Add comment "# Historical audit query - intentionally fetches all versions"

2-19. [Additional violations with exact file:line references in GitHub Issue #101]
```

**Part 2: Test Fixture Violations (2 violations)**

Pattern 13 (Coverage Quality) requires integration tests to use real fixtures (db_pool, db_cursor), not mocks. The following tests are missing required fixtures:

```
1. tests/integration/test_strategy_manager_integration.py
   Missing: db_pool, db_cursor fixtures
   Fix: Add fixtures to test function signatures

2. tests/integration/test_model_manager_integration.py
   Missing: db_pool, db_cursor fixtures
   Fix: Add fixtures to test function signatures
```

#### Implementation Plan

**Phase 2 Week 1 Implementation (5-6 hours):**

**Task 1: Fix SCD Type 2 Query Violations (3-4 hours)**

For each of the 19 violations:

1. **Review query context** - Determine if query should filter current versions or all versions
2. **Add row_current_ind filter** - Add `AND row_current_ind = TRUE` to WHERE clause
3. **OR add exception comment** - If intentionally querying all versions (audit/history functions), add comment explaining why
4. **Verify fix** - Re-run `python scripts/validate_scd_queries.py` to confirm violation resolved

**Example Fix (get_market_history):**
```python
# BEFORE:
def get_market_history(ticker: str, limit: int = 100) -> list[dict[str, Any]]:
    """Get price history for a market."""
    query = """
        SELECT *
        FROM markets
        WHERE ticker = %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    return fetch_all(query, (ticker, limit))

# AFTER:
def get_market_history(ticker: str, limit: int = 100) -> list[dict[str, Any]]:
    """Get price history for a market (all versions)."""
    # Historical audit query - intentionally fetches all versions for analysis
    query = """
        SELECT *
        FROM markets
        WHERE ticker = %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    return fetch_all(query, (ticker, limit))
```

**Task 2: Fix Test Fixture Violations (1-2 hours)**

For each of the 2 integration test files:

1. **Add db_pool and db_cursor fixtures** to test function signatures
2. **Replace mock connections** with real fixtures from conftest.py
3. **Update test setup** to use real database transactions
4. **Verify tests still pass** with real fixtures
5. **Re-run validation** - `python scripts/validate_test_fixtures.py`

**Example Fix (test_strategy_manager_integration.py):**
```python
# BEFORE:
def test_create_strategy_version():
    mock_pool = MagicMock()
    manager = StrategyManager(mock_pool)
    # ... test code

# AFTER:
def test_create_strategy_version(db_pool, db_cursor):
    """Test creating strategy version with real database."""
    manager = StrategyManager(db_pool)
    # ... test code using real fixtures
```

**Task 3: Validation and Documentation (30 min)**

1. Run all validation scripts to confirm fixes:
   ```bash
   python scripts/validate_scd_queries.py
   python scripts/validate_test_fixtures.py
   ```
2. Run full test suite to ensure no regressions:
   ```bash
   python -m pytest tests/ -v
   ```
3. Update this document (mark DEF-P1.5-002 as Complete)
4. Close GitHub Issue #101 with summary of fixes

#### Success Criteria

**Functional Requirements:**
- [  ] All 19 SCD Type 2 queries either include `row_current_ind = TRUE` filter OR have explicit exception comments
- [  ] All 2 integration test files use real fixtures (db_pool, db_cursor) instead of mocks
- [  ] All validation scripts pass (validate_scd_queries.py, validate_test_fixtures.py)
- [  ] All tests pass with real fixtures (no regressions)

**Testing Requirements:**
- [  ] Integration tests using real fixtures still pass
- [  ] SCD queries with exception comments tested and verified intentional
- [  ] Full test suite passes (all 348 tests)

**Documentation Requirements:**
- [  ] All exception comments documented with rationale (e.g., "Historical audit query")
- [  ] PHASE_1.5_DEFERRED_TASKS_V1.0.md updated (DEF-P1.5-002 marked Complete)
- [  ] GitHub Issue #101 closed with summary

**Quality Requirements:**
- [  ] No new violations introduced
- [  ] All pre-push hooks pass
- [  ] Pattern 2 and Pattern 13 compliance achieved

#### Dependencies

**Required Before Implementation:**
- ✅ Phase 2 Week 1 started (ESPN integration underway)
- ✅ GitHub Issue #101 created (formal tracking)
- ✅ PHASE_1.5_DEFERRED_TASKS_V1.0.md updated (documented)

**Required During Implementation:**
- Database connection available for integration test fixtures
- Access to production code (crud_operations.py, position_manager.py, etc.)
- Validation scripts working (validate_scd_queries.py, validate_test_fixtures.py)

#### Timeline

**Phase 2 Week 1 Schedule:**
- Day 1: Fix SCD Type 2 violations (3-4 hours)
  - Review all 19 violations
  - Add filters or exception comments
  - Validate fixes with script
- Day 2: Fix test fixture violations (1-2 hours)
  - Update 2 integration test files
  - Replace mocks with real fixtures
  - Validate tests pass
- Day 3: Validation and close (30 min)
  - Run all validation scripts
  - Run full test suite
  - Update documentation and close issue

**Total Time:** 5-6 hours (includes validation and documentation)

#### Acceptance Criteria

**Code Complete When:**
1. ✅ All 21 violations resolved (19 SCD + 2 fixtures)
2. ✅ Validation scripts pass (validate_scd_queries.py, validate_test_fixtures.py)
3. ✅ All tests passing (348 tests, ≥93% coverage maintained)
4. ✅ Pre-push hooks pass (no regressions)
5. ✅ Documentation updated (deferred tasks, GitHub issue)

**Definition of Done:**
- [  ] All SCD queries compliant with Pattern 2 (row_current_ind filter or documented exception)
- [  ] All integration tests compliant with Pattern 13 (real fixtures, no mocks)
- [  ] Validation scripts pass
- [  ] Tests pass
- [  ] Documentation updated
- [  ] GitHub Issue #101 closed
- [  ] DEF-P1.5-002 marked Complete in this document

#### References

**Patterns:**
- Pattern 2 (Dual Versioning): docs/guides/DEVELOPMENT_PATTERNS_V1.6.md
- Pattern 13 (Coverage Quality): docs/guides/DEVELOPMENT_PATTERNS_V1.6.md
- Pattern 18 (Avoid Technical Debt): To be created (SESSION 2.4c)

**Validation Scripts:**
- scripts/validate_scd_queries.py (SCD Type 2 validation)
- scripts/validate_test_fixtures.py (Real fixtures validation)
- scripts/validation_config.yaml (Validation configuration)

**Related Issues:**
- GitHub Issue #101: "Fix 21 validation violations discovered by Phase 1.5 pre-push hooks"

**Implementation:**
- src/precog/database/crud_operations.py (SCD queries)
- src/precog/trading/position_manager.py (SCD queries)
- tests/integration/test_strategy_manager_integration.py (fixtures)
- tests/integration/test_model_manager_integration.py (fixtures)

**Related Tasks:**
- DEF-P1.5-001: Configuration System Enhancement (parallel task in Phase 2 Week 1)

---

## High Priority Tasks (🟡)

### DEF-P1.5-001: Configuration System Enhancement

**Priority:** 🟡 High
**Target Phase:** Phase 2 Week 1
**Time Estimate:** 6-8 hours
**Category:** Infrastructure Enhancement

#### Rationale

The Configuration System Enhancement was deferred from Phase 1.5 because:

1. **Requires Live Database Integration:** Version resolution needs to query the database for active strategy/model versions, which is a Phase 2 capability
2. **Not Blocking Phase 2:** Current config_loader.py provides sufficient functionality for Phase 2 ESPN integration to start
3. **Can Be Completed in Parallel:** Configuration enhancements can be added during Phase 2 Week 1 alongside ESPN API client development
4. **Phase 1.5 Already 75% Complete:** 3/4 deliverables shipped with exceptional coverage (93.83%)

#### Original Requirements (DEVELOPMENT_PHASES_V1.5.md Lines 859-870)

**From Phase 1.5 Configuration System Enhancement deliverable:**

```markdown
#### 4. Configuration System Enhancement (Week 2)
- [  ] Update `utils/config.py`
  - YAML file loading for all 7 config files
  - Version resolution (get active version for strategy/model)
  - Trailing stop config retrieval
  - Override handling
- [  ] Unit tests for configuration
  - Test YAML loading
  - Test version resolution
  - Test trailing stop config retrieval
  - Test override priority
```

#### Current State

**What Exists (config_loader.py - 99.21% coverage):**
- ✅ YAML file loading for all 7 config files
- ✅ Trailing stop config retrieval via `load_trading_config()`
- ✅ Decimal conversion for financial values (Pattern 1 enforcement)
- ✅ Comprehensive error handling

**What's Missing:**
- ❌ Version resolution (get active version for strategy/model from database)
- ❌ Override handling (strategy-level overrides > config-level defaults)
- ❌ Unit tests for version resolution and override priority

#### Implementation Plan

**Phase 2 Week 1 Implementation (6-8 hours):**

**Task 1: Add Version Resolution Methods (3-4 hours)**

Create `src/precog/config/version_resolver.py`:

```python
"""
Configuration Version Resolution

Provides version resolution for strategies and models.
Integrates with database to retrieve active versions.

Reference: ADR-018 (Immutable Strategy Versions), ADR-019 (Immutable Model Versions)
Related: src/precog/trading/strategy_manager.py, src/precog/analytics/model_manager.py
"""
from typing import Optional
from precog.database.crud_operations import (
    get_active_strategy_version,
    get_active_model_version,
)
from precog.utils.logger import get_logger

logger = get_logger(__name__)

class VersionResolver:
    """Resolves active strategy and model versions from database."""

    def get_active_strategy_config(self, strategy_name: str) -> dict:
        """
        Get active strategy version configuration.

        Educational Note:
            Strategies are versioned immutably (ADR-018). This method queries
            the database for the active version and returns its config.

        Args:
            strategy_name: Strategy name (e.g., "value_betting_v1")

        Returns:
            Strategy configuration dict with version metadata

        Raises:
            ValueError: If no active version found

        Example:
            >>> resolver = VersionResolver()
            >>> config = resolver.get_active_strategy_config("value_betting_v1")
            >>> config["version"]  # "v1.2"
            >>> config["min_edge"]  # Decimal("0.05")

        Reference:
            - ADR-018 (Immutable Strategy Versions)
            - VERSIONING_GUIDE_V1.0.md Section 2.1
        """
        strategy = get_active_strategy_version(strategy_name)
        if not strategy:
            raise ValueError(f"No active version found for strategy: {strategy_name}")

        logger.info(
            f"Resolved active strategy version",
            extra={
                "strategy_name": strategy_name,
                "version": strategy["version"],
                "status": strategy["status"],
            },
        )
        return strategy

    def get_active_model_config(self, model_name: str) -> dict:
        """
        Get active model version configuration.

        Educational Note:
            Models are versioned immutably (ADR-019). This method queries
            the database for the active version and returns its config.

        Args:
            model_name: Model name (e.g., "elo_nfl", "ensemble_v1")

        Returns:
            Model configuration dict with version metadata

        Raises:
            ValueError: If no active version found

        Example:
            >>> resolver = VersionResolver()
            >>> config = resolver.get_active_model_config("elo_nfl")
            >>> config["version"]  # "v2.0"
            >>> config["config"]["initial_elo"]  # 1500

        Reference:
            - ADR-019 (Immutable Model Versions)
            - VERSIONING_GUIDE_V1.0.md Section 2.2
        """
        model = get_active_model_version(model_name)
        if not model:
            raise ValueError(f"No active version found for model: {model_name}")

        logger.info(
            f"Resolved active model version",
            extra={
                "model_name": model_name,
                "version": model["version"],
                "model_type": model["model_type"],
            },
        )
        return model
```

**Task 2: Add Override Handling (2-3 hours)**

Update `src/precog/config/config_loader.py`:

```python
def get_config_with_overrides(
    self, config_type: str, strategy_name: Optional[str] = None
) -> dict:
    """
    Load configuration with strategy-level overrides applied.

    Override Priority (highest to lowest):
    1. Strategy-level overrides (from strategy config JSONB)
    2. Config file values (YAML files)
    3. System defaults (hardcoded fallbacks)

    Educational Note:
        This allows per-strategy customization without modifying global
        config files. For example, one strategy might use min_edge=0.03
        while another uses min_edge=0.05.

    Args:
        config_type: Configuration type ("trading", "position_management", etc.)
        strategy_name: Optional strategy name for strategy-level overrides

    Returns:
        Configuration dict with overrides applied

    Example:
        >>> loader = ConfigLoader()
        >>> # Get global trading config
        >>> global_config = loader.get_config_with_overrides("trading")
        >>> global_config["min_edge"]  # Decimal("0.05") from trading.yaml
        >>>
        >>> # Get strategy-specific config with overrides
        >>> strategy_config = loader.get_config_with_overrides(
        ...     "trading", strategy_name="aggressive_v1"
        ... )
        >>> strategy_config["min_edge"]  # Decimal("0.03") from strategy override

    Reference:
        - CONFIGURATION_GUIDE_V3.1.md Section 4 (Override Hierarchy)
        - ADR-018 (Strategy Versioning and Configuration)
    """
    # Load base config from YAML
    base_config = self._load_config(config_type)

    # If no strategy specified, return base config
    if not strategy_name:
        return base_config

    # Get strategy-level overrides from database
    from precog.config.version_resolver import VersionResolver

    resolver = VersionResolver()
    try:
        strategy = resolver.get_active_strategy_config(strategy_name)
        overrides = strategy.get("config", {}).get("overrides", {})

        # Apply overrides (strategy overrides > base config)
        config_with_overrides = {**base_config, **overrides}

        logger.info(
            f"Applied strategy overrides",
            extra={
                "strategy_name": strategy_name,
                "override_count": len(overrides),
                "overridden_keys": list(overrides.keys()),
            },
        )

        return config_with_overrides

    except ValueError as e:
        # No active version found, return base config
        logger.warning(
            f"Strategy version not found, using base config",
            extra={"strategy_name": strategy_name, "error": str(e)},
        )
        return base_config
```

**Task 3: Unit Tests (1-2 hours)**

Create `tests/unit/config/test_version_resolver.py`:

```python
"""
Unit Tests for Configuration Version Resolution

Tests version resolution from database and override handling.

Reference: DEF-P1.5-001, CONFIGURATION_GUIDE_V3.1.md Section 4
"""
import pytest
from precog.config.version_resolver import VersionResolver
from precog.config.config_loader import ConfigLoader

# Test fixtures for active strategy/model versions
# Test version resolution (active version retrieval)
# Test override priority (strategy > config > defaults)
# Test error handling (no active version, invalid strategy name)
# Test integration with ConfigLoader

# Target: 100% coverage for new methods
```

#### Success Criteria

**Functional Requirements:**
- [  ] Can retrieve active strategy version from database
- [  ] Can retrieve active model version from database
- [  ] Override priority correctly applied (strategy > config > defaults)
- [  ] Error handling for missing active versions
- [  ] Integration with existing ConfigLoader

**Testing Requirements:**
- [  ] 100% test coverage for new methods
- [  ] Unit tests for version resolution (10+ tests)
- [  ] Unit tests for override handling (8+ tests)
- [  ] Integration tests for end-to-end config loading with overrides (5+ tests)

**Documentation Requirements:**
- [  ] Update CONFIGURATION_GUIDE_V3.1.md with version resolution section
- [  ] Add override hierarchy documentation with examples
- [  ] Update VERSIONING_GUIDE_V1.0.md with config integration
- [  ] Add educational docstrings to all new methods (Pattern 7)

**Quality Requirements:**
- [  ] All tests passing
- [  ] No linting errors (Ruff)
- [  ] No type errors (Mypy)
- [  ] Educational docstrings on all public methods

#### Dependencies

**Required Before Implementation:**
- ✅ Phase 2 database integration (live connection pool)
- ✅ Strategy Manager CRUD operations (get_active_strategy_version)
- ✅ Model Manager CRUD operations (get_active_model_version)
- ✅ Phase 1.5 completion (manager layer implemented)

**Required During Implementation:**
- Database connection available for testing
- Test fixtures for active strategy/model versions
- Integration with ConfigLoader

#### Timeline

**Phase 2 Week 1 Schedule:**
- Day 1-2: Implementation (6-8 hours)
  - Version resolution methods (3-4 hours)
  - Override handling (2-3 hours)
  - Unit tests (1-2 hours)
- Day 3: Testing and validation (2 hours)
  - Integration testing
  - Coverage verification
  - Documentation updates
- Day 4: Code review and merge (1 hour)

**Total Time:** 9-11 hours (including testing and documentation)

#### Acceptance Criteria

**Code Complete When:**
1. ✅ All success criteria met (functional, testing, documentation, quality)
2. ✅ Tests passing with 100% coverage for new code
3. ✅ Code review completed (AI + manual review)
4. ✅ Documentation updated (CONFIGURATION_GUIDE, VERSIONING_GUIDE)
5. ✅ No regressions in existing config loading functionality

**Definition of Done:**
- [  ] Version resolution working (active strategy/model configs retrieved)
- [  ] Override handling working (priority correctly applied)
- [  ] 100% test coverage for new code
- [  ] All tests passing (unit + integration)
- [  ] Documentation updated
- [  ] Code reviewed and merged to main
- [  ] DEF-P1.5-001 closed in GitHub issues

#### References

**ADRs:**
- ADR-018: Immutable Strategy Versions
- ADR-019: Immutable Model Versions

**Guides:**
- docs/guides/CONFIGURATION_GUIDE_V3.1.md
- docs/guides/VERSIONING_GUIDE_V1.0.md

**Implementation:**
- src/precog/config/config_loader.py (existing, 99.21% coverage)
- src/precog/trading/strategy_manager.py (Phase 1.5, 86.59% coverage)
- src/precog/analytics/model_manager.py (Phase 1.5, 92.66% coverage)

**Related Tasks:**
- None (standalone enhancement)

---

## Medium Priority Tasks (🟢)

**None**

---

## Low Priority Tasks (🔵)

**None**

---

## Completed Tasks (✅)

**None** (this is the initial version)

---

## Task Workflow

**When Adding New Deferred Task:**
1. Assign sequential ID (DEF-P1.5-XXX)
2. Document rationale (why deferred, why not blocking)
3. Create implementation plan with time estimate
4. Define success criteria and acceptance criteria
5. Update task summary table
6. Create GitHub issue if task is infrastructure (REQ-XXX-NNN)

**When Completing Deferred Task:**
1. Move task from priority section to "Completed Tasks"
2. Add completion date and final stats (time spent, coverage)
3. Update DEVELOPMENT_PHASES_V1.5.md (mark task complete)
4. Update MASTER_INDEX if new documents created
5. Close GitHub issue if applicable

**When Deferring Task Further:**
1. Update "Target Phase" field
2. Document reason for additional deferral
3. Update priority if changed
4. Notify in SESSION_HANDOFF.md

---

## Statistics

**Phase 1.5 Deferred Tasks:**
- Total: 2
- Critical Priority: 1 (DEF-P1.5-002)
- High Priority: 1 (DEF-P1.5-001)
- Medium Priority: 0
- Low Priority: 0
- Completed: 0

**Time Estimates:**
- Total Deferred: 11-14 hours
- Target Phase 2 Week 1: 11-14 hours
- Expected Completion: Phase 2 Week 1 (January 2026)

**Deferral Rate:**
- Phase 1.5 Deliverables: 4 planned
- Completed: 3 (75%)
- Deferred: 2 (50%)
- Deferral justified:
  - Configuration requires Phase 2 database integration (DEF-P1.5-001)
  - Validation violations discovered post-implementation (DEF-P1.5-002)

---

## Related Documents

**Foundation:**
- docs/foundation/DEVELOPMENT_PHASES_V1.5.md (Phase 1.5 deliverables)
- docs/foundation/MASTER_REQUIREMENTS_V2.10.md (configuration requirements)
- docs/foundation/ARCHITECTURE_DECISIONS_V2.9.md (ADR-018, ADR-019)

**Guides:**
- docs/guides/CONFIGURATION_GUIDE_V3.1.md (configuration system)
- docs/guides/VERSIONING_GUIDE_V1.0.md (strategy/model versioning)

**Phase Completion:**
- docs/phase-completion/PHASE_1.5_COMPLETION_REPORT.md (assessment results)

**Process:**
- CLAUDE.md Section "Phase Completion Protocol" Step 6 (Deferred Tasks Workflow)

---

**Document Status:** ✅ Active
**Maintenance:** Update when tasks completed or deferred further
**Owner:** Development team
**Review Frequency:** At phase completion

---

**END OF PHASE_1.5_DEFERRED_TASKS_V1.0.md**
