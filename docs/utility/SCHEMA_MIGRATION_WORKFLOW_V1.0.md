# Schema Migration Workflow Guide

---
**Version:** 1.0
**Created:** 2025-11-19
**Last Updated:** 2025-11-19
**Purpose:** Comprehensive step-by-step workflow for database schema migrations and CRUD operation synchronization
**Target Audience:** Developers implementing database schema changes
**Companion Document:** Pattern 14 in DEVELOPMENT_PATTERNS_V1.5.md
**Status:** ✅ Current

---

## 📋 Table of Contents

1. [Introduction](#introduction)
2. [When to Use This Workflow](#when-to-use-this-workflow)
3. [Pre-Migration Checklist](#pre-migration-checklist)
4. [Step 1: Plan the Migration](#step-1-plan-the-migration)
5. [Step 2: Create Database Migration](#step-2-create-database-migration)
6. [Step 3: Update CRUD Operations](#step-3-update-crud-operations)
7. [Step 4: Update Tests](#step-4-update-tests)
8. [Step 5: Run Integration Tests](#step-5-run-integration-tests)
9. [Step 6: Update Documentation](#step-6-update-documentation)
10. [Step 7: Commit and Deploy](#step-7-commit-and-deploy)
11. [Rollback Procedures](#rollback-procedures)
12. [Common Scenarios](#common-scenarios)
13. [Troubleshooting](#troubleshooting)

---

## Introduction

**What This Guide Covers:**

This guide provides a comprehensive workflow for synchronizing database schema changes with CRUD operations, particularly for SCD Type 2 tables using the dual-key pattern.

**Key Principles:**

1. **Schema and Code Must Stay Synchronized** - Every schema change requires corresponding CRUD updates
2. **Tests Catch Issues Before Production** - Integration tests with real database prevent deployment bugs
3. **Documentation Prevents Future Confusion** - Updated docs ensure future developers understand the schema
4. **Rollback Plan Required** - Every migration needs a safe rollback strategy

**Typical Timeline:**

| Step | Duration | Complexity |
|------|----------|------------|
| 1. Plan Migration | 15-30 min | Low-Medium |
| 2. Create Migration | 10-30 min | Low-Medium |
| 3. Update CRUD | 30-90 min | Medium-High |
| 4. Update Tests | 30-60 min | Medium |
| 5. Run Tests | 5-10 min | Low |
| 6. Update Docs | 10-20 min | Low |
| 7. Commit/Deploy | 10-20 min | Low |
| **Total** | **2-4 hours** | **Medium-High** |

**When to Use:**
- Adding columns to SCD Type 2 tables
- Implementing dual-key schema pattern
- Changing column types
- Adding/modifying constraints
- Any schema change affecting CRUD operations

---

## When to Use This Workflow

### ✅ ALWAYS Use This Workflow For:

**SCD Type 2 Tables:**
- `positions` - Position lifecycle tracking
- `markets` - Market price history
- `trades` - Trade execution history
- `account_balance` - Balance snapshots
- `edges` - Edge calculation history
- `game_states` - Live game state updates

**Schema Changes:**
- Adding new columns (especially NOT NULL columns)
- Changing column types (VARCHAR → DECIMAL, INTEGER → BIGINT)
- Adding constraints (UNIQUE, FOREIGN KEY, CHECK)
- Implementing dual-key pattern (surrogate + business key)
- Modifying SCD Type 2 metadata columns

### ⚠️ Consider Using This Workflow For:

**Non-SCD Type 2 Tables:**
- `strategies` - If changing immutable config structure
- `probability_models` - If changing model metadata
- `platforms` - If adding required fields
- `events` - If changing FK relationships

**Simple Changes:**
- Adding nullable columns (simpler, but still needs CRUD updates)
- Adding indexes (usually doesn't affect CRUD)
- Adding comments (documentation only)

### ❌ DON'T Use This Workflow For:

- Seed data updates (no schema changes)
- Index optimization (no CRUD changes)
- Comment updates (documentation only)
- Performance tuning (no schema changes)
- Data migrations without schema changes

---

## Pre-Migration Checklist

**Before starting ANY migration, verify:**

- [ ] **Backup exists** - Recent database backup available
- [ ] **Migration number** - Next sequential number identified (check `src/precog/database/migrations/`)
- [ ] **Branch created** - Feature branch for migration work (`git checkout -b feature/migration-NNN`)
- [ ] **Tests passing** - All existing tests pass before changes
- [ ] **CRUD functions identified** - List of all CRUD functions that touch the table
- [ ] **Dual-key pattern understood** - If implementing dual-key, review ADR-089
- [ ] **SCD Type 2 pattern understood** - If SCD Type 2 table, review ADR-034

**Quick Verification Commands:**

```bash
# Check latest migration number
ls src/precog/database/migrations/ | tail -5

# List CRUD functions for a table (example: positions)
grep -n "def.*position" src/precog/database/crud_operations.py

# Verify all tests passing
python -m pytest tests/ -v

# Check current git branch
git branch --show-current
```

---

## Step 1: Plan the Migration

**Time Estimate:** 15-30 minutes

**Goal:** Document what changes are needed and why, identify all affected code.

### 1.1 Document the Change

Create a migration plan document:

```markdown
# Migration NNN: [Brief Description]

**Date:** YYYY-MM-DD
**Author:** [Your Name]
**Related Ticket:** [Issue/Task Number]

## Summary
[1-2 sentence description of what's changing and why]

## Tables Affected
- `table_name` - [What's changing]

## Columns Added/Modified/Removed
- `column_name` TYPE - [Purpose]

## CRUD Functions Affected
- `crud_function_1()` - [How it's affected]
- `crud_function_2()` - [How it's affected]

## Business Logic Affected
- [List of manager classes or business logic that uses these CRUD functions]

## Rollback Strategy
- [How to undo this migration if needed]

## Testing Requirements
- [What specific scenarios need testing]
```

### 1.2 Identify All CRUD Functions

**Search for all functions touching the table:**

```bash
# Find all CRUD functions for positions table
grep -n "FROM positions\|INTO positions\|UPDATE positions" src/precog/database/crud_operations.py

# Find all business layer functions using these CRUD operations
grep -n "open_position\|update_position\|close_position" src/precog/trading/*.py
```

**Create checklist of functions to update:**

```markdown
## CRUD Functions to Update

- [ ] `open_position()` - Adds position_id column to INSERT
- [ ] `update_position()` - Includes position_id in versioning
- [ ] `close_position()` - Includes position_id in final version
- [ ] `get_current_positions()` - Returns position_id in results
```

### 1.3 Review Related ADRs

**Read relevant architecture decisions:**

- **ADR-089:** Dual-Key Schema Pattern for SCD Type 2 Tables
- **ADR-034:** SCD Type 2 for Slowly Changing Dimensions
- **ADR-003:** Database Schema Versioning Strategy
- **ADR-088:** Test Type Categories and Coverage Standards

---

## Step 2: Create Database Migration

**Time Estimate:** 10-30 minutes

**Goal:** Create SQL migration file that safely applies schema changes.

### 2.1 Create Migration File

**File naming:** `NNN_descriptive_name.sql` (e.g., `011_add_positions_dual_key.sql`)

**Location:** `src/precog/database/migrations/`

**Template:**

```sql
-- Migration NNN: [Brief Description]
-- Date: YYYY-MM-DD
-- Author: [Your Name]
-- Related: [ADR/Issue number]
--
-- Summary:
-- [1-2 sentences describing what this migration does]
--
-- Rollback:
-- [How to undo this migration]

-- ===========================================================================
-- FORWARD MIGRATION
-- ===========================================================================

-- Step 1: Add new column (nullable initially for existing data)
ALTER TABLE table_name ADD COLUMN column_name TYPE;

-- Step 2: Populate existing rows (if NOT NULL required)
UPDATE table_name SET column_name = [default_value] WHERE column_name IS NULL;

-- Step 3: Make column NOT NULL (if required)
ALTER TABLE table_name ALTER COLUMN column_name SET NOT NULL;

-- Step 4: Add constraints (if needed)
CREATE UNIQUE INDEX index_name ON table_name (column_name) WHERE condition;

-- Step 5: Add comments (documentation)
COMMENT ON COLUMN table_name.column_name IS '[Description and format]';

-- ===========================================================================
-- VERIFICATION
-- ===========================================================================

-- Verify column exists
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'table_name' AND column_name = 'column_name';

-- Verify constraint created
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'table_name';
```

### 2.2 Dual-Key Pattern Migration (Specific Example)

**For SCD Type 2 tables needing dual-key pattern:**

```sql
-- Migration 011: Add dual-key schema to positions table
-- Implements ADR-089: Dual-Key Schema Pattern for SCD Type 2

-- Step 1: Add business key column (nullable initially)
ALTER TABLE positions ADD COLUMN position_id VARCHAR(50);

-- Step 2: Populate position_id from surrogate id
UPDATE positions SET position_id = 'POS-' || id::TEXT WHERE position_id IS NULL;

-- Step 3: Make position_id NOT NULL
ALTER TABLE positions ALTER COLUMN position_id SET NOT NULL;

-- Step 4: Create partial UNIQUE index (one current version per position_id)
CREATE UNIQUE INDEX positions_position_id_current_unique
ON positions (position_id)
WHERE row_current_ind = TRUE;

-- Step 5: Add comments documenting pattern
COMMENT ON COLUMN positions.position_id IS 'Business key (repeats across versions), format: POS-{id}';
COMMENT ON COLUMN positions.id IS 'Surrogate PRIMARY KEY (unique across all versions, used for FK references)';

-- Verification
SELECT
    COUNT(*) as total_positions,
    COUNT(DISTINCT id) as unique_surrogates,
    COUNT(DISTINCT position_id) as unique_business_keys,
    COUNT(*) FILTER (WHERE row_current_ind = TRUE) as current_versions
FROM positions;
```

### 2.3 Test Migration Locally

**Apply migration to local test database:**

```bash
# Option 1: Using psql
psql -U postgres -d precog_dev -f src/precog/database/migrations/011_add_positions_dual_key.sql

# Option 2: Using Python script (if available)
python scripts/apply_migration.py 011

# Verify migration applied
psql -U postgres -d precog_dev -c "\d positions"
```

**Check for errors:**
- Column type mismatches
- NULL constraint violations
- Index creation failures
- Foreign key violations

---

## Step 3: Update CRUD Operations

**Time Estimate:** 30-90 minutes (varies by complexity)

**Goal:** Update all CRUD functions to work with new schema.

### 3.1 Identify CRUD Functions to Update

From Step 1.2, you should have a checklist like:

```markdown
## CRUD Functions to Update

- [ ] `open_position()` - Lines 800-850
- [ ] `update_position()` - Lines 852-920
- [ ] `close_position()` - Lines 922-990
- [ ] `get_current_positions()` - Lines 992-1020
```

### 3.2 Update Pattern: Dual-Key on INSERT

**For new records with dual-key pattern:**

```python
def open_position(...) -> str:
    """Open new position with dual-key pattern."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Step 1: INSERT without business_id (generates surrogate id)
            cur.execute("""
                INSERT INTO positions (
                    market_id, strategy_id, model_id, side,
                    quantity, entry_price, current_price,
                    -- ... other columns ...
                    row_current_ind
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (market_id, strategy_id, model_id, side, quantity, entry_price, entry_price))

            surrogate_id = cur.fetchone()['id']

            # Step 2: UPDATE to set business_id from surrogate_id
            cur.execute("""
                UPDATE positions
                SET position_id = %s
                WHERE id = %s
                RETURNING position_id
            """, (f'POS-{surrogate_id}', surrogate_id))

            position_id = cur.fetchone()['position_id']
            conn.commit()
            return position_id  # Return business key
    finally:
        release_connection(conn)
```

### 3.3 Update Pattern: SCD Type 2 Versioning

**For updates creating new versions:**

```python
def update_position(position_id: int, current_price: Decimal) -> int:
    """Update position - creates new SCD Type 2 version."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Step 1: Get current version (MUST filter by row_current_ind!)
            cur.execute("""
                SELECT * FROM positions
                WHERE id = %s AND row_current_ind = TRUE
            """, (position_id,))

            current = cur.fetchone()
            if not current:
                raise ValueError(f"Position {position_id} not found or not current")

            # Step 2: Expire current version
            cur.execute("""
                UPDATE positions
                SET row_current_ind = FALSE, row_expiration_date = NOW()
                WHERE id = %s
            """, (position_id,))

            # Step 3: Insert new version (REUSE same position_id business key)
            cur.execute("""
                INSERT INTO positions (
                    position_id,  -- Reuse business key!
                    market_id, strategy_id, model_id, side,
                    quantity, entry_price, current_price,
                    -- ... ALL other columns from current version ...
                    entry_time,  -- Preserve from original
                    row_current_ind
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (
                current['position_id'],  # Reuse!
                current['market_id'], current['strategy_id'], current['model_id'],
                current['side'], current['quantity'], current['entry_price'],
                current_price,  # Updated field
                current['entry_time'],  # Preserve
            ))

            new_id = cur.fetchone()['id']
            conn.commit()
            return new_id  # Return new surrogate id
    finally:
        release_connection(conn)
```

### 3.4 Update Pattern: Queries with row_current_ind

**For all SELECT queries on SCD Type 2 tables:**

```python
def get_current_positions(status: str | None = None) -> list[dict]:
    """Get current positions (MUST filter by row_current_ind = TRUE)."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT
                    p.*,
                    m.ticker, m.yes_price, m.no_price
                FROM positions p
                JOIN markets m ON p.market_id = m.market_id
                    AND m.row_current_ind = TRUE  -- Filter markets too!
                WHERE p.row_current_ind = TRUE     -- ⚠️ CRITICAL!
            """
            params = []

            if status:
                query += " AND p.status = %s"
                params.append(status)

            query += " ORDER BY p.entry_time DESC"

            cur.execute(query, params)
            return cur.fetchall()
    finally:
        release_connection(conn)
```

### 3.5 CRUD Update Checklist

After updating each function, verify:

- [ ] **INSERT statements** - Include all new columns
- [ ] **UPDATE statements** - Handle new columns correctly
- [ ] **SELECT statements** - Return new columns (if needed)
- [ ] **Business key logic** - Set from surrogate id on initial INSERT
- [ ] **row_current_ind filter** - ALWAYS filter `= TRUE` for current versions
- [ ] **Business key reuse** - Reuse same business key when creating new versions
- [ ] **All columns included** - Don't forget new columns in INSERT statements
- [ ] **Error handling** - Appropriate exceptions for invalid states

---

## Step 4: Update Tests

**Time Estimate:** 30-60 minutes

**Goal:** Create integration tests validating schema changes and CRUD updates.

### 4.1 Test Requirements

**CRITICAL: Tests must use REAL database (Pattern 13):**

- ✅ Use `clean_test_data` fixture
- ✅ Use `db_pool` fixture for pool tests
- ✅ Use `db_cursor` for direct SQL tests
- ❌ NO mocks for `get_connection()`
- ❌ NO mocks for `ConfigLoader`
- ❌ NO mocks for internal CRUD operations

### 4.2 Test Template: Dual-Key Verification

```python
# tests/unit/trading/test_position_manager.py

def test_open_position_sets_business_id(clean_test_data, manager, position_params):
    """Verify open_position sets position_id from surrogate id.

    Educational Note:
        Dual-key pattern: business key (position_id) is set from
        surrogate key (id) after INSERT to guarantee uniqueness.

    Related:
        ADR-089: Dual-Key Schema Pattern for SCD Type 2 Tables
    """
    result = manager.open_position(**position_params)

    # Verify business_id format
    assert result['position_id'].startswith('POS-')
    assert result['id'] is not None  # Surrogate key

    # Verify business_id matches surrogate_id
    expected_position_id = f"POS-{result['id']}"
    assert result['position_id'] == expected_position_id
```

### 4.3 Test Template: SCD Type 2 Versioning

```python
def test_update_position_creates_new_version_with_same_business_id(
    clean_test_data, manager, position_params
):
    """Verify SCD Type 2: new version reuses same position_id.

    Educational Note:
        SCD Type 2 versioning: UPDATE expires old version (row_current_ind=FALSE),
        INSERT creates new version with same business key but new surrogate id.

    Related:
        ADR-034: SCD Type 2 for Slowly Changing Dimensions
    """
    # Open position
    position = manager.open_position(**position_params)
    original_id = position['id']
    original_position_id = position['position_id']

    # Update position (creates new SCD Type 2 version)
    updated = manager.update_position(
        position_id=original_id,
        current_price=Decimal("0.6000"),
    )

    # Verify new version has DIFFERENT surrogate id
    assert updated['id'] != original_id

    # Verify new version has SAME business key
    assert updated['position_id'] == original_position_id

    # Verify old version is expired (direct database check)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT row_current_ind FROM positions WHERE id = %s
            """, (original_id,))
            old_version = cur.fetchone()
            assert old_version['row_current_ind'] is False  # Expired
    finally:
        release_connection(conn)
```

### 4.4 Test Template: row_current_ind Filtering

```python
def test_get_current_positions_filters_by_row_current_ind(
    clean_test_data, manager, position_params
):
    """Verify get_current_positions only returns row_current_ind=TRUE.

    Educational Note:
        Critical for SCD Type 2: Queries MUST filter by row_current_ind=TRUE
        to return only current versions, not historical versions.
    """
    # Open position
    position = manager.open_position(**position_params)
    original_id = position['id']

    # Update twice (creates 2 new versions, expires 2 old versions)
    manager.update_position(original_id, Decimal("0.5500"))
    manager.update_position(original_id, Decimal("0.6000"))

    # Should return 1 position (only current version)
    current_positions = manager.get_open_positions()
    assert len(current_positions) == 1

    # Verify returned position is the latest version
    assert current_positions[0]['current_price'] == Decimal("0.6000")

    # Verify database has 3 versions total (1 current + 2 expired)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM positions WHERE position_id = %s
            """, (position['position_id'],))
            total_versions = cur.fetchone()[0]
            assert total_versions == 3
    finally:
        release_connection(conn)
```

### 4.5 Test Checklist

- [ ] Test business_id set correctly on INSERT
- [ ] Test SCD Type 2 versioning (UPDATE + INSERT pattern)
- [ ] Test row_current_ind filtering works
- [ ] Test ALL new columns populated correctly
- [ ] Test old versions expired (row_current_ind=FALSE)
- [ ] Test complete position lifecycle (open → update → close)
- [ ] Test edge cases (NULL values, boundary conditions)
- [ ] Test failure modes (invalid data, constraint violations)

---

## Step 5: Run Integration Tests

**Time Estimate:** 5-10 minutes

**Goal:** Verify all tests pass with real database.

### 5.1 Run Position Manager Tests

```bash
# Run specific test file
python -m pytest tests/unit/trading/test_position_manager.py -v

# Expected output: All tests passing
# Example: 23/23 tests passing
```

### 5.2 Run Full Test Suite

```bash
# Run all tests
python -m pytest tests/ -v

# Check for any failures
# All tests should pass before proceeding
```

### 5.3 Check Coverage

```bash
# Check coverage for CRUD operations
python -m pytest tests/ --cov=precog.database.crud_operations --cov-report=term-missing

# Check coverage for manager layer
python -m pytest tests/ --cov=precog.trading.position_manager --cov-report=term-missing

# Verify coverage meets targets:
# - CRUD operations: ≥85%
# - Manager layer: ≥85%
# - Critical path: ≥90%
```

### 5.4 Test Failure Troubleshooting

**If tests fail:**

1. **Read error message carefully** - SQL syntax errors, missing columns, type mismatches
2. **Check CRUD UPDATE statement** - Forgot to include new column?
3. **Check test fixture** - Missing required FK data?
4. **Check conftest.py cleanup** - Is cleanup removing test data correctly?
5. **Run single failing test** - `pytest tests/path/to/test.py::test_name -v`
6. **Add debug logging** - Print SQL statements, inspect returned data

**Common Test Failures:**

| Error | Cause | Fix |
|-------|-------|-----|
| `column "position_id" does not exist` | Forgot to add column to INSERT | Add column to INSERT statement |
| `null value in column "position_id" violates not-null constraint` | Forgot to set business_id | Add UPDATE after INSERT to set business_id |
| `AssertionError: assert None == Decimal('0.75')` | Forgot column in INSERT | Add missing column to INSERT statement |
| `ValueError: Position 123 not found or not current` | Missing row_current_ind filter | Add `AND row_current_ind = TRUE` to query |
| `ForeignKeyViolation` | Test fixture missing FK data | Add required FK records to fixture |

---

## Step 6: Update Documentation

**Time Estimate:** 10-20 minutes

**Goal:** Update schema documentation to reflect migration changes.

### 6.1 Update DATABASE_SCHEMA_SUMMARY

**File:** `docs/database/DATABASE_SCHEMA_SUMMARY_V*.md`

**Update table documentation:**

```markdown
### positions Table (Dual-Key SCD Type 2)

**Purpose:** Track position lifecycle with historical versioning

**Migration:** Migration 011 (2025-11-19) - Added dual-key pattern

**Dual-Key Pattern:**
- `id SERIAL PRIMARY KEY` - Surrogate key (unique across all versions, used for FK references)
- `position_id VARCHAR(50) NOT NULL` - Business key (repeats across versions, format: 'POS-{id}')
- Partial UNIQUE index: `CREATE UNIQUE INDEX ... ON positions (position_id) WHERE row_current_ind = TRUE`

**Key Columns:**
- `id` - Surrogate PRIMARY KEY
- `position_id` - Business key (user-facing, stable across versions)
- `market_id` - FK to markets (business key)
- `strategy_id` - FK to strategies
- `model_id` - FK to probability_models
- `entry_price DECIMAL(10,4)` - Original entry price
- `current_price DECIMAL(10,4)` - Latest market price
- `exit_price DECIMAL(10,4)` - Exit price (NULL until closed)
- `row_current_ind BOOLEAN` - TRUE = current version, FALSE = historical
- `row_effective_date TIMESTAMP` - Version start time
- `row_expiration_date TIMESTAMP` - Version end time (NULL for current)

**SCD Type 2 Behavior:**
- Updates create new row with same position_id, new surrogate id
- Old row: row_current_ind → FALSE, row_expiration_date → NOW()
- New row: row_current_ind → TRUE, row_effective_date → NOW()

**Queries:**
```sql
-- Get current positions only
SELECT * FROM positions WHERE row_current_ind = TRUE;

-- Get all versions for a position
SELECT * FROM positions WHERE position_id = 'POS-123' ORDER BY row_effective_date;

-- Get position history
SELECT * FROM positions WHERE position_id = 'POS-123' AND row_current_ind = FALSE;
```
```

### 6.2 Update ADR-089 (Dual-Key Pattern)

**File:** `docs/foundation/ARCHITECTURE_DECISIONS_V*.md`

**Add table to "Tables Using This Pattern" section:**

```markdown
**Tables Using This Pattern:**
- ✅ `positions` (Migration 011 - IMPLEMENTED 2025-11-19)
- ✅ `markets` (Migration 004 - IMPLEMENTED 2025-10-15)
- 📋 `trades` (Planned - Phase 2)
- 📋 `account_balance` (Planned - Phase 2)
```

### 6.3 Update MASTER_INDEX

**File:** `docs/foundation/MASTER_INDEX_V*.md`

**If new documents created, add to index:**

```markdown
### Utility Documents
- `SCHEMA_MIGRATION_WORKFLOW_V1.0.md` - Schema migration workflow guide
```

### 6.4 Documentation Checklist

- [ ] Updated DATABASE_SCHEMA_SUMMARY with new columns
- [ ] Updated ADR-089 table list
- [ ] Updated MASTER_INDEX if new docs created
- [ ] Added migration number and date to documentation
- [ ] Updated version numbers (V1.7 → V1.8, etc.)

---

## Step 7: Commit and Deploy

**Time Estimate:** 10-20 minutes

**Goal:** Commit changes, create PR, deploy to production.

### 7.1 Stage All Changes

```bash
# Check what changed
git status

# Stage migration file
git add src/precog/database/migrations/011_add_positions_dual_key.sql

# Stage CRUD updates
git add src/precog/database/crud_operations.py

# Stage manager updates
git add src/precog/trading/position_manager.py
git add src/precog/trading/__init__.py

# Stage test updates
git add tests/unit/trading/test_position_manager.py
git add tests/conftest.py
git add tests/database/test_initialization.py

# Stage documentation updates
git add docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
git add docs/foundation/ARCHITECTURE_DECISIONS_V2.20.md
git add docs/guides/DEVELOPMENT_PATTERNS_V1.5.md
git add docs/utility/SCHEMA_MIGRATION_WORKFLOW_V1.0.md
```

### 7.2 Commit with Detailed Message

```bash
git commit -m "feat: Implement Migration 011 - Positions dual-key schema

## Schema Changes (Migration 011)

**Added:**
- position_id VARCHAR(50) NOT NULL - Business key
- Partial UNIQUE index on (position_id) WHERE row_current_ind = TRUE

**Purpose:** Implement dual-key pattern for SCD Type 2 positions table

## CRUD Operation Updates

**Updated 4 functions in crud_operations.py:**
- open_position() - Sets business_id from surrogate_id on INSERT
- update_position() - Reuses business_id when creating new versions
- close_position() - Includes position_id in final version (+ fixed missing current_price)
- get_current_positions() - Returns position_id in results

## Testing

**Created 23 integration tests (all passing):**
- 4 tests for business_id logic
- 6 tests for SCD Type 2 versioning
- 5 tests for row_current_ind filtering
- 8 tests for complete position lifecycle

**Coverage:**
- Position Manager: 87.50% (target ≥85%)
- CRUD Operations: 91.26% (target ≥85%)
- initialization.py: 89.11% (target ≥90%, within 1% tolerance)

## Documentation Updates

**Created:**
- Pattern 14 in DEVELOPMENT_PATTERNS_V1.5.md (450 lines)
- SCHEMA_MIGRATION_WORKFLOW_V1.0.md (comprehensive workflow guide)

**Updated:**
- ADR-089: Dual-Key Schema Pattern for SCD Type 2 Tables (433 lines)
- DATABASE_SCHEMA_SUMMARY_V1.7.md (added positions dual-key documentation)
- ARCHITECTURE_DECISIONS V2.17 → V2.18

## Related

- ADR-089: Dual-Key Schema Pattern for SCD Type 2 Tables
- ADR-034: SCD Type 2 for Slowly Changing Dimensions
- Pattern 13: Test Coverage Quality (NO mocks for database/CRUD)
- Pattern 14: Schema Migration → CRUD Operations Update Workflow

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 7.3 Push to Remote

```bash
# Push feature branch
git push origin feature/migration-011

# Create PR
gh pr create --title "Migration 011: Positions dual-key schema + Position Manager" --body "
## Summary

Implements Migration 011 (dual-key schema for positions table) with complete Position Manager implementation and comprehensive testing.

## Schema Changes

- Added position_id business key to positions table
- Implemented dual-key pattern (surrogate id + business key)
- Created partial UNIQUE index for SCD Type 2 enforcement

## CRUD Operations

Updated 4 CRUD functions:
- ✅ open_position() - Sets business_id from surrogate_id
- ✅ update_position() - Reuses business_id for new versions
- ✅ close_position() - Fixed missing current_price bug
- ✅ get_current_positions() - Returns position_id

## Position Manager (NEW)

Created complete Position Manager with:
- 23 integration tests (all passing)
- 87.50% coverage (target ≥85%)
- Full position lifecycle support
- Margin validation
- P&L calculation

## Documentation

Created:
- Pattern 14: Schema Migration → CRUD Operations Update Workflow
- SCHEMA_MIGRATION_WORKFLOW_V1.0.md (comprehensive guide)

Updated:
- ADR-089: Dual-Key Schema Pattern
- DATABASE_SCHEMA_SUMMARY
- ARCHITECTURE_DECISIONS V2.17 → V2.18

## Testing

- ✅ 23/23 Position Manager tests passing
- ✅ initialization.py coverage 89.11% (target 90%, within tolerance)
- ✅ All integration tests use real database (NO mocks)
- ✅ Coverage targets met (≥85% for all modules)

## Checklist

- [x] Migration tested on local database
- [x] All CRUD functions updated
- [x] Integration tests created and passing
- [x] Coverage targets met
- [x] Documentation updated
- [x] Pre-commit hooks passing
- [x] Pre-push hooks passing

Closes #[issue-number]
"
```

### 7.4 Verify CI/CD

```bash
# Check PR status
gh pr view

# Monitor CI checks
gh pr checks

# Wait for all checks to pass
```

### 7.5 Merge PR

```bash
# After approval + CI passing, merge PR
gh pr merge --squash

# Delete feature branch
git checkout main
git pull
git branch -d feature/migration-011
```

---

## Rollback Procedures

### Emergency Rollback (If Migration Fails in Production)

**If migration causes production issues:**

**Step 1: Assess Impact**
```sql
-- Check how many records affected
SELECT COUNT(*) FROM positions WHERE position_id IS NOT NULL;

-- Check if any applications are failing
SELECT * FROM logs WHERE timestamp > NOW() - INTERVAL '10 minutes' AND level = 'ERROR';
```

**Step 2: Create Rollback Migration**

```sql
-- Migration 011_rollback: Remove dual-key schema from positions

-- Drop partial unique index
DROP INDEX IF EXISTS positions_position_id_current_unique;

-- Remove position_id column
ALTER TABLE positions DROP COLUMN IF EXISTS position_id;

-- Verify rollback
SELECT column_name FROM information_schema.columns WHERE table_name = 'positions';
```

**Step 3: Rollback CRUD Operations**

```bash
# Revert to previous commit
git revert [migration-commit-hash]

# Or checkout previous version
git checkout [previous-commit] -- src/precog/database/crud_operations.py

# Deploy immediately
git commit -m "HOTFIX: Rollback Migration 011"
git push
```

**Step 4: Notify Team**

```markdown
## ROLLBACK ALERT

**Migration:** 011 (Positions dual-key schema)
**Time:** YYYY-MM-DD HH:MM UTC
**Reason:** [Why rollback was needed]
**Action:** Reverted to previous schema
**Status:** System stable
**Next Steps:** [Investigation and re-attempt timeline]
```

### Partial Rollback (If Only CRUD Issues)

**If migration succeeded but CRUD operations have bugs:**

**Option 1: Hotfix CRUD Operations**
```python
# Fix CRUD bug (e.g., missing column)
def close_position(...):
    # ... existing code ...
    cur.execute("""
        INSERT INTO positions (
            position_id, ..., current_price, ...  # Add missing column
        )
        VALUES (%s, ..., %s, ...)
    """, (position_id, ..., exit_price, ...))
```

**Option 2: Temporary Workaround**
```python
# Add NULL check while fixing properly
def get_position_id(surrogate_id):
    """Get position_id, fallback to 'POS-{id}' if NULL."""
    cur.execute("SELECT position_id FROM positions WHERE id = %s", (surrogate_id,))
    result = cur.fetchone()
    return result['position_id'] or f'POS-{surrogate_id}'
```

---

## Common Scenarios

### Scenario 1: Adding Nullable Column

**Simpler workflow (no backfill needed):**

```sql
-- Migration: Add optional metadata column
ALTER TABLE positions ADD COLUMN notes TEXT;

-- Comment
COMMENT ON COLUMN positions.notes IS 'Optional notes about position entry/exit';
```

**CRUD Update:**
```python
# Just add column to INSERT (with NULL default)
cur.execute("""
    INSERT INTO positions (..., notes)
    VALUES (%s, %s)
""", (..., notes or None))
```

### Scenario 2: Changing Column Type

**Requires data migration:**

```sql
-- Migration: Change quantity from INTEGER to BIGINT

-- Step 1: Add new column
ALTER TABLE positions ADD COLUMN quantity_new BIGINT;

-- Step 2: Copy data
UPDATE positions SET quantity_new = quantity::BIGINT;

-- Step 3: Verify no data loss
SELECT COUNT(*) FROM positions WHERE quantity != quantity_new;

-- Step 4: Drop old column
ALTER TABLE positions DROP COLUMN quantity;

-- Step 5: Rename new column
ALTER TABLE positions RENAME COLUMN quantity_new TO quantity;

-- Step 6: Add NOT NULL constraint
ALTER TABLE positions ALTER COLUMN quantity SET NOT NULL;
```

### Scenario 3: Adding Foreign Key

**Requires parent records to exist:**

```sql
-- Migration: Add FK to new table

-- Step 1: Ensure parent table exists
CREATE TABLE IF NOT EXISTS exit_reasons (
    reason_code VARCHAR(20) PRIMARY KEY,
    description TEXT NOT NULL
);

-- Step 2: Add FK column (nullable initially)
ALTER TABLE positions ADD COLUMN exit_reason_code VARCHAR(20);

-- Step 3: Add FK constraint
ALTER TABLE positions
ADD CONSTRAINT fk_positions_exit_reason
FOREIGN KEY (exit_reason_code)
REFERENCES exit_reasons (reason_code);
```

---

## Troubleshooting

### Issue: Migration Fails with "column already exists"

**Cause:** Migration was run twice, or previous migration wasn't rolled back.

**Solution:**
```sql
-- Check if column exists
SELECT column_name FROM information_schema.columns
WHERE table_name = 'positions' AND column_name = 'position_id';

-- If exists, drop and re-run
ALTER TABLE positions DROP COLUMN IF EXISTS position_id;
-- Then re-run migration
```

### Issue: Tests Fail with "column does not exist"

**Cause:** Local test database doesn't have migration applied.

**Solution:**
```bash
# Apply migration to test database
psql -U postgres -d precog_test -f src/precog/database/migrations/011_add_positions_dual_key.sql

# Or reset test database
python scripts/reset_test_database.py
```

### Issue: "null value violates not-null constraint"

**Cause:** Migration didn't populate existing rows before adding NOT NULL.

**Solution:**
```sql
-- Fix migration to backfill before NOT NULL
ALTER TABLE positions ADD COLUMN position_id VARCHAR(50);  -- Nullable first
UPDATE positions SET position_id = 'POS-' || id::TEXT WHERE position_id IS NULL;  -- Backfill
ALTER TABLE positions ALTER COLUMN position_id SET NOT NULL;  -- Then NOT NULL
```

### Issue: Tests Pass Locally, Fail in CI

**Cause:** CI database state different from local.

**Solution:**
```bash
# Check CI logs for error message
gh run view [run-id] --log

# Common causes:
# 1. Migration not in git commit
# 2. Test fixture missing required data
# 3. Database timezone differences
# 4. Concurrent test execution issues
```

### Issue: High Coverage But Tests Don't Catch Bug

**Cause:** Using mocks instead of real database (Pattern 13 violation).

**Solution:**
```python
# ❌ WRONG - Mock hides SQL bugs
@patch("precog.database.connection.get_connection")
def test_open_position(mock_get_connection):
    # Test passes but doesn't validate SQL

# ✅ CORRECT - Real database catches SQL bugs
def test_open_position(clean_test_data, manager, position_params):
    # Test validates SQL syntax, constraints, everything
```

---

## Cross-References

**Related Patterns:**
- **Pattern 1:** Decimal Precision (use Decimal for all price columns)
- **Pattern 2:** Dual Versioning System (SCD Type 2 vs immutable versions)
- **Pattern 13:** Test Coverage Quality (NO mocks for database/CRUD)
- **Pattern 14:** Schema Migration → CRUD Operations Update Workflow (condensed version)

**Architecture Decisions:**
- **ADR-089:** Dual-Key Schema Pattern for SCD Type 2 Tables
- **ADR-034:** SCD Type 2 for Slowly Changing Dimensions
- **ADR-003:** Database Schema Versioning Strategy
- **ADR-088:** Test Type Categories and Coverage Standards

**Testing:**
- **tests/conftest.py:** Fixture infrastructure (clean_test_data, db_pool)
- **TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md:** Why mocks hide bugs
- **TEST_REQUIREMENTS_COMPREHENSIVE_V1.0.md:** REQ-TEST-012 through REQ-TEST-019

**Examples:**
- **Migration 011:** `src/precog/database/migrations/011_add_positions_dual_key.sql`
- **CRUD Operations:** `src/precog/database/crud_operations.py`
- **Position Manager:** `src/precog/trading/position_manager.py`
- **Integration Tests:** `tests/unit/trading/test_position_manager.py`

---

**END OF SCHEMA_MIGRATION_WORKFLOW_V1.0.md**
