# Phase 1.5 Deferred Tasks

---
**Version:** 1.0
**Created:** 2025-11-22
**Phase:** Phase 1.5 - Foundation Validation (Codename: "Verify")
**Target Completion:** Phase 2 Week 1
**Total Tasks:** 1
**Total Time Estimate:** 6-8 hours
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
- Total: 1
- High Priority: 1 (DEF-P1.5-001)
- Medium Priority: 0
- Low Priority: 0
- Completed: 0

**Time Estimates:**
- Total Deferred: 6-8 hours
- Target Phase 2 Week 1: 6-8 hours
- Expected Completion: Phase 2 Week 1 (January 2026)

**Deferral Rate:**
- Phase 1.5 Deliverables: 4 planned
- Completed: 3 (75%)
- Deferred: 1 (25%)
- Deferral justified: Configuration requires Phase 2 database integration

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
