# Column Rename Deprecation Pattern

---
**Version:** 1.0
**Created:** 2025-11-25
**Purpose:** Best practices for renaming database columns in production without breaking changes
**Target Audience:** Developers making schema changes
**Related ADRs:** ADR-018, ADR-019, ADR-020 (Dual Versioning)
**Source:** PR #93 Claude Code Review (M-10)
---

## Overview

Renaming database columns in a production system requires a **phased approach** to avoid breaking changes. This guide documents the "expand-contract" pattern used in Precog for safe column renames.

### Why Not Just Rename?

```sql
-- ❌ DANGEROUS: Immediate rename breaks all code using old name
ALTER TABLE strategies RENAME COLUMN sport TO domain;
```

**Problems with immediate rename:**
1. Application code using `sport` column breaks instantly
2. No rollback window (can't un-rename without data loss)
3. Running queries fail mid-flight
4. ORM mappings become invalid
5. Reports and analytics break

---

## The 3-Phase Deprecation Pattern

### Phase 1: Expand (Add New Column)

**Goal:** Add new column while keeping old column functional.

**Migration (e.g., migration_025_add_domain_column.py):**
```sql
-- Step 1: Add new column (nullable initially)
ALTER TABLE strategies ADD COLUMN domain VARCHAR(100);

-- Step 2: Copy existing data to new column
UPDATE strategies SET domain = sport WHERE sport IS NOT NULL;

-- Step 3: Update any non-null constraint (if needed)
-- Only after verifying data migration success
ALTER TABLE strategies ALTER COLUMN domain SET NOT NULL;
```

**Application Code (during Phase 1):**
```python
# Read from BOTH columns (prefer new, fallback to old)
def get_strategy_domain(strategy: dict) -> str:
    return strategy.get("domain") or strategy.get("sport") or "unknown"

# Write to BOTH columns (maintain consistency)
def create_strategy(domain: str, ...):
    execute_query(
        "INSERT INTO strategies (domain, sport, ...) VALUES (%s, %s, ...)",
        (domain, domain, ...)  # Write same value to both
    )
```

**Duration:** 1-2 weeks (until all code paths updated)

---

### Phase 2: Deprecate (Warn on Old Column)

**Goal:** Identify and migrate all code using old column name.

**Add deprecation warnings:**
```python
# In model/ORM layer
class Strategy:
    @property
    def sport(self) -> str:
        """DEPRECATED: Use 'domain' instead. Will be removed in v2.0."""
        import warnings
        warnings.warn(
            "'sport' column is deprecated, use 'domain' instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.domain
```

**Add logging to track old column usage:**
```python
# In query functions
def get_strategy_by_sport(sport: str):
    """DEPRECATED: Use get_strategy_by_domain() instead."""
    logger.warning(
        "Deprecated: get_strategy_by_sport() called. "
        "Use get_strategy_by_domain() instead. "
        f"Caller: {inspect.stack()[1].filename}:{inspect.stack()[1].lineno}"
    )
    return get_strategy_by_domain(domain=sport)
```

**Monitor deprecation warnings:**
```bash
# Run tests with deprecation warnings visible
python -W default::DeprecationWarning -m pytest tests/

# Search codebase for old column references
grep -r "sport" --include="*.py" src/ tests/ | grep -v "# DEPRECATED"
```

**Duration:** 2-4 weeks (until no warnings in logs/tests)

---

### Phase 3: Contract (Remove Old Column)

**Goal:** Remove deprecated column after all code migrated.

**Pre-removal checklist:**
- [ ] No deprecation warnings in production logs for 1+ weeks
- [ ] All tests pass without deprecation warnings
- [ ] Code search finds no references to old column (except comments)
- [ ] All external consumers notified (if applicable)

**Migration (e.g., migration_030_remove_sport_column.py):**
```sql
-- Final cleanup: Remove deprecated column
ALTER TABLE strategies DROP COLUMN sport;

-- Optional: Add comment documenting the rename history
COMMENT ON COLUMN strategies.domain IS 'Category domain. Renamed from "sport" in v1.5.';
```

**Update documentation:**
- Remove old column from DATABASE_SCHEMA_SUMMARY
- Update API documentation
- Add to CHANGELOG: "BREAKING: Removed deprecated 'sport' column"

---

## Real Example: strategies.approach → strategy_type

**Precog Migration History:**

| Phase | Migration | Action | Duration |
|-------|-----------|--------|----------|
| 1 | migration_013 | Added `approach` column (CHECK constraint) | Week 1-2 |
| 1 | migration_021 | Renamed `approach` → `strategy_type` | Week 3-4 |
| 2 | (code) | Added deprecation warnings | Week 5-8 |
| 3 | (future) | Remove old column references | Week 9+ |

**Key Files Changed:**
- `src/precog/trading/strategy_manager.py` - Updated column references
- `tests/unit/trading/test_strategy_manager.py` - Updated test fixtures
- `docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md` - Updated schema docs

---

## Quick Reference

### When to Use This Pattern

✅ **Use 3-phase pattern when:**
- Renaming columns in production tables
- Multiple applications use the same database
- You have external API consumers
- You need zero-downtime deployments

❌ **Skip pattern when:**
- Column is in development-only table
- No production data exists yet
- Single-developer project with no consumers

### Timeline Guidelines

| Scenario | Phase 1 | Phase 2 | Phase 3 |
|----------|---------|---------|---------|
| Internal tool | 1 day | 3 days | 1 day |
| Production app | 1 week | 2-4 weeks | 1 week |
| Public API | 2 weeks | 1-3 months | 1 week |

### Common Mistakes

1. **Forgetting to copy data:**
   ```sql
   -- ❌ Wrong: New column is NULL for existing rows
   ALTER TABLE strategies ADD COLUMN domain VARCHAR;

   -- ✅ Correct: Copy existing data
   ALTER TABLE strategies ADD COLUMN domain VARCHAR;
   UPDATE strategies SET domain = sport;
   ```

2. **Not writing to both columns:**
   ```python
   # ❌ Wrong: Old column gets stale
   def create_strategy(domain: str):
       execute_query("INSERT ... (domain) VALUES (%s)", (domain,))

   # ✅ Correct: Both columns stay synchronized
   def create_strategy(domain: str):
       execute_query("INSERT ... (domain, sport) VALUES (%s, %s)", (domain, domain))
   ```

3. **Removing column too early:**
   ```sql
   -- ❌ Wrong: Removed after 1 day
   ALTER TABLE strategies DROP COLUMN sport;  -- Code still using it!

   -- ✅ Correct: Wait for deprecation period (weeks, not days)
   ```

---

## References

- **ADR-018:** SCD Type 2 for Markets/Positions
- **ADR-019:** Immutable Versioning for Strategies
- **ADR-020:** Dual Versioning Strategy
- **PR #93:** Claude Code Review recommending this pattern
- **migrations/021, 022:** Real examples of column renames

---

**END OF GUIDE V1.0**
