# Schema Migration Workflow Guide

---
**Version:** 2.1
**Created:** 2025-11-19
**Last Updated:** 2025-12-20
**Purpose:** Step-by-step workflow for database schema migrations using Alembic
**Target Audience:** Developers implementing database schema changes
**Companion Document:** Pattern 14 in DEVELOPMENT_PATTERNS_V1.20.md
**Status:** Current
**Changes in V2.1:**
- Updated "Current Migration State" table with migrations 0003-0008
- Added migration 0008 (execution_environment column, ADR-107)
**Changes in V2.0:**
- **BREAKING CHANGE:** Alembic is now the EXCLUSIVE migration tool
- Removed all references to legacy SQL/Python migration system
- Updated all commands to use Alembic workflow
- Added "Migration History" section documenting transition from dual-system
- Simplified workflow to single Alembic-based approach

---

## Table of Contents

1. [Introduction](#introduction)
2. [Alembic Overview](#alembic-overview)
3. [Migration History](#migration-history)
4. [Pre-Migration Checklist](#pre-migration-checklist)
5. [Step 1: Plan the Migration](#step-1-plan-the-migration)
6. [Step 2: Create Alembic Migration](#step-2-create-alembic-migration)
7. [Step 3: Apply and Verify Migration](#step-3-apply-and-verify-migration)
8. [Step 4: Update CRUD Operations](#step-4-update-crud-operations)
9. [Step 5: Update Tests](#step-5-update-tests)
10. [Step 6: Update Documentation](#step-6-update-documentation)
11. [Step 7: Commit and Deploy](#step-7-commit-and-deploy)
12. [Rollback Procedures](#rollback-procedures)
13. [Troubleshooting](#troubleshooting)

---

## Introduction

**What This Guide Covers:**

This guide provides a comprehensive workflow for database schema migrations using **Alembic** as the exclusive migration tool.

**Key Principles:**

1. **Alembic is the ONLY migration tool** - All schema changes go through Alembic
2. **Schema and Code Must Stay Synchronized** - Every schema change requires corresponding CRUD updates
3. **Tests Catch Issues Before Production** - Integration tests with real database prevent deployment bugs
4. **Documentation Prevents Future Confusion** - Updated docs ensure future developers understand the schema
5. **Rollback Plan Required** - Every migration needs a safe downgrade path

**Typical Timeline:**

| Step | Duration | Complexity |
|------|----------|------------|
| 1. Plan Migration | 15-30 min | Low-Medium |
| 2. Create Alembic Migration | 10-20 min | Low |
| 3. Apply and Verify | 5-10 min | Low |
| 4. Update CRUD | 30-90 min | Medium-High |
| 5. Update Tests | 30-60 min | Medium |
| 6. Update Docs | 10-20 min | Low |
| 7. Commit/Deploy | 10-20 min | Low |
| **Total** | **2-4 hours** | **Medium-High** |

---

## Alembic Overview

### What is Alembic?

Alembic is a database migration tool for SQLAlchemy. It provides:
- **Version control for schemas** - Track which migrations have been applied
- **Up/Down migrations** - Apply (upgrade) and revert (downgrade) changes
- **Revision dependency tracking** - Migrations form a linked chain
- **Autogeneration** (optional) - Can auto-generate migrations from model changes

### Alembic Configuration Location

```
src/precog/database/
├── alembic.ini              # Alembic configuration
└── alembic/
    ├── env.py               # Environment configuration
    ├── script.py.mako       # Migration template
    └── versions/
        ├── 0001_initial_baseline_schema.py
        ├── 0002_add_audit_columns_to_lookup_tables.py
        └── ... (future migrations)
```

### Key Alembic Commands

```bash
# IMPORTANT: Always run from src/precog/database/ directory

# Check current database version
cd src/precog/database
DB_NAME=precog_test python -m alembic current

# View migration history
DB_NAME=precog_test python -m alembic history

# Apply all pending migrations
DB_NAME=precog_test python -m alembic upgrade head

# Apply specific migration
DB_NAME=precog_test python -m alembic upgrade 0002

# Rollback one migration
DB_NAME=precog_test python -m alembic downgrade -1

# Rollback to specific version
DB_NAME=precog_test python -m alembic downgrade 0001

# Generate new migration (manual method preferred)
DB_NAME=precog_test python -m alembic revision -m "description"
```

### Environment Variable: DB_NAME

The database name is controlled by the `DB_NAME` environment variable:

| Environment | DB_NAME | Usage |
|-------------|---------|-------|
| Test | `precog_test` | CI, local testing |
| Development | `precog_dev` | Local development |
| Production | `precog` | Production (use with caution) |

---

## Migration History

### Historical Context

**Before 2025-12-07:** Precog used a dual-migration system:
- SQL migrations (000-016 in `src/precog/database/migrations/*.sql`)
- Python migrations (011-029+ in `src/precog/database/migrations/migration_*.py`)

This system was complex and caused schema drift issues between environments.

**2025-12-07 Onwards:** Alembic became the exclusive migration tool:
- Migration 0001: Baseline schema (captures state of SQL migrations 000-016)
- Migration 0002+: All new schema changes

### Legacy Migrations Folder

The `src/precog/database/migrations/` folder contains **legacy migrations** that:
- Were used to create the Alembic baseline
- Are NO LONGER EXECUTED by the application
- Are kept for historical reference only

**DO NOT ADD NEW FILES TO THIS FOLDER.** All new migrations go through Alembic.

### Current Migration State

| Alembic Version | Description | Date |
|-----------------|-------------|------|
| 0001 | Initial baseline schema (captures legacy migrations 000-016) | 2025-12-05 |
| 0002 | Add audit columns to lookup tables (Issue #121) | 2025-12-07 |
| 0003 | Fix teams composite unique constraint | 2025-12-10 |
| 0004 | Add NCAAW support | 2025-12-12 |
| 0005 | Create historical_elo table (Issue #229) | 2025-12-15 |
| 0006 | Create historical_games table (Issue #229) | 2025-12-15 |
| 0007 | Create historical_odds table (Issue #229) | 2025-12-15 |
| 0008 | Add execution_environment column (ADR-107, Issue #241) | 2025-12-20 |

To check current state:
```bash
cd src/precog/database
DB_NAME=precog_test python -m alembic current
# Output: 0008 (head)
```

---

## Pre-Migration Checklist

**Before starting ANY migration, verify:**

- [ ] **Database connection works**
  ```bash
  cd src/precog/database
  DB_NAME=precog_test python -m alembic current
  ```
- [ ] **Current version identified**
  ```bash
  DB_NAME=precog_test python -m alembic history --verbose
  ```
- [ ] **Branch created** - Feature branch for migration work
  ```bash
  git checkout -b feature/migration-NNNN
  ```
- [ ] **Tests passing** - All existing tests pass before changes
  ```bash
  python -m pytest tests/ -v
  ```
- [ ] **CRUD functions identified** - List all CRUD functions that touch the table
- [ ] **ADRs reviewed** - Understand relevant architecture decisions

---

## Step 1: Plan the Migration

**Time Estimate:** 15-30 minutes

**Goal:** Document what changes are needed and identify all affected code.

### 1.1 Document the Change

Create a migration plan:

```markdown
# Migration NNNN: [Brief Description]

**Date:** YYYY-MM-DD
**Author:** [Your Name]
**Related Issue:** #[issue-number]

## Summary
[1-2 sentences describing what's changing and why]

## Tables Affected
- `table_name` - [What's changing]

## Columns Added/Modified/Removed
- `column_name` TYPE - [Purpose]

## CRUD Functions Affected
- `crud_function_1()` - [How it's affected]

## Rollback Strategy
- [How to undo this migration]
```

### 1.2 Identify All CRUD Functions

```bash
# Find all CRUD functions for a specific table
grep -n "FROM table_name\|INTO table_name\|UPDATE table_name" src/precog/database/crud_operations.py

# Find business layer functions using these CRUDs
grep -n "open_position\|update_position\|close_position" src/precog/trading/*.py
```

---

## Step 2: Create Alembic Migration

**Time Estimate:** 10-20 minutes

**Goal:** Create an Alembic migration file with upgrade and downgrade functions.

### 2.1 Generate Migration File

```bash
cd src/precog/database
DB_NAME=precog_test python -m alembic revision -m "add_audit_columns_to_lookup_tables"
```

This creates a file like: `versions/0003_add_audit_columns_to_lookup_tables.py`

### 2.2 Edit Migration File

**Template:**

```python
"""Add audit columns to lookup tables.

Brief description of what this migration does.

GitHub Issue: #XXX (DEF-P1.5-YYY)

Key Changes:
- Change 1
- Change 2

Revision ID: 0003
Revises: 0002
Create Date: YYYY-MM-DD

References:
- ADR-XXX: Relevant architecture decision
- Pattern N: Relevant development pattern
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply schema changes."""

    # Add column
    op.execute("""
        ALTER TABLE table_name
        ADD COLUMN IF NOT EXISTS column_name TYPE DEFAULT default_value
    """)

    # Add column comment
    op.execute("""
        COMMENT ON COLUMN table_name.column_name IS
        'Description of what this column stores'
    """)

    # Add trigger (if needed)
    op.execute("""
        CREATE OR REPLACE FUNCTION function_name()
        RETURNS TRIGGER AS $$
        BEGIN
            -- trigger logic
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)


def downgrade() -> None:
    """Revert schema changes (MUST be reversible)."""

    # Drop trigger (if created)
    op.execute("DROP TRIGGER IF EXISTS trigger_name ON table_name")

    # Drop function (if created)
    op.execute("DROP FUNCTION IF EXISTS function_name() CASCADE")

    # Remove column
    op.execute("ALTER TABLE table_name DROP COLUMN IF EXISTS column_name")
```

### 2.3 Alembic Best Practices

1. **Use `IF NOT EXISTS` / `IF EXISTS`** - Makes migrations idempotent
2. **Always implement `downgrade()`** - Required for rollbacks
3. **Add column comments** - Documents schema intent
4. **Reference issues and ADRs** - Provides context in docstring
5. **Test both upgrade AND downgrade** - Verify rollback works

---

## Step 3: Apply and Verify Migration

**Time Estimate:** 5-10 minutes

**Goal:** Apply migration to test database and verify changes.

### 3.1 Apply Migration

```bash
cd src/precog/database

# Apply to test database
DB_NAME=precog_test python -m alembic upgrade head
```

### 3.2 Verify Migration Applied

```bash
# Check current version
DB_NAME=precog_test python -m alembic current
# Expected: 0003 (head)

# Verify column exists
PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d precog_test -c "\d table_name"

# Verify trigger exists (if applicable)
PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d precog_test -c "
SELECT trigger_name, event_manipulation, action_statement
FROM information_schema.triggers
WHERE event_object_table = 'table_name';"
```

### 3.3 Test Trigger (if applicable)

```bash
# Test trigger behavior
PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d precog_test -c "
-- Insert test record
INSERT INTO table_name (required_columns) VALUES ('test');

-- Check auto-populated columns
SELECT column_name, auto_column FROM table_name ORDER BY id DESC LIMIT 1;
"
```

### 3.4 Test Downgrade

```bash
# Test rollback
DB_NAME=precog_test python -m alembic downgrade -1

# Verify rollback
DB_NAME=precog_test python -m alembic current
# Expected: 0002

# Re-apply migration
DB_NAME=precog_test python -m alembic upgrade head
```

---

## Step 4: Update CRUD Operations

**Time Estimate:** 30-90 minutes

**Goal:** Update all CRUD functions to work with new schema.

### 4.1 Common CRUD Update Patterns

**Adding column to INSERT:**
```python
def create_record(..., new_column: str | None = None) -> int:
    cur.execute("""
        INSERT INTO table_name (existing_col, new_column)
        VALUES (%s, %s)
        RETURNING id
    """, (existing_value, new_column))
```

**Adding column to SELECT:**
```python
def get_record(id: int) -> dict:
    cur.execute("""
        SELECT id, existing_col, new_column
        FROM table_name
        WHERE id = %s
    """, (id,))
```

**Auto-populated columns (triggers):**
```python
# No CRUD change needed - trigger handles it
# Just add column to SELECT statements to return it
```

---

## Step 5: Update Tests

**Time Estimate:** 30-60 minutes

**Goal:** Create tests validating schema changes.

### 5.1 Test New Columns

```python
def test_new_column_exists(clean_test_data, db_cursor):
    """Verify new column exists in table."""
    db_cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'table_name'
        AND column_name = 'new_column'
    """)
    assert db_cursor.fetchone() is not None
```

### 5.2 Test Trigger Behavior

```python
def test_trigger_auto_updates(clean_test_data, db_cursor):
    """Verify trigger auto-updates timestamp."""
    # Insert record
    db_cursor.execute("INSERT INTO table_name (col) VALUES ('test')")

    # Get initial timestamp
    db_cursor.execute("SELECT updated_at FROM table_name")
    initial = db_cursor.fetchone()['updated_at']

    # Wait and update
    time.sleep(0.1)
    db_cursor.execute("UPDATE table_name SET col = 'updated'")

    # Verify timestamp changed
    db_cursor.execute("SELECT updated_at FROM table_name")
    final = db_cursor.fetchone()['updated_at']
    assert final > initial
```

---

## Step 6: Update Documentation

**Time Estimate:** 10-20 minutes

**Goal:** Update schema documentation.

### 6.1 Update DATABASE_SCHEMA_SUMMARY

Add new columns to table documentation:
```markdown
### table_name Table

| Column | Type | Description |
|--------|------|-------------|
| new_column | TYPE | Description |
```

### 6.2 Update ADR (if architectural change)

If the migration implements an ADR, update its status to "Implemented".

### 6.3 Update This Document

Add the migration to the "Current Migration State" table above.

---

## Step 7: Commit and Deploy

**Time Estimate:** 10-20 minutes

### 7.1 Stage Changes

```bash
git add src/precog/database/alembic/versions/0003_*.py
git add src/precog/database/crud_operations.py
git add tests/
git add docs/
```

### 7.2 Commit

```bash
git commit -m "feat: Add migration 0003 - [description]

- Added [column/trigger/etc]
- Updated CRUD operations
- Added tests for new schema

Closes #XXX"
```

### 7.3 Create PR

```bash
gh pr create --title "Migration 0003: [Description]" --body "
## Summary
[What this migration does]

## Changes
- Migration file: 0003_description.py
- CRUD updates: [list functions]
- Tests: [number] new tests

## Testing
- [ ] Migration applies successfully
- [ ] Downgrade works
- [ ] All tests pass
- [ ] Trigger behavior verified (if applicable)

Closes #XXX
"
```

---

## Rollback Procedures

### Quick Rollback

```bash
cd src/precog/database

# Rollback one migration
DB_NAME=precog_test python -m alembic downgrade -1

# Rollback to specific version
DB_NAME=precog_test python -m alembic downgrade 0002

# Verify rollback
DB_NAME=precog_test python -m alembic current
```

### Production Rollback Procedure

1. **Stop application** - Prevent new database operations
2. **Apply rollback** - `alembic downgrade -1`
3. **Deploy previous code** - Code that matches previous schema
4. **Verify database state** - Check schema and data integrity
5. **Restart application** - Resume operations
6. **Document incident** - Record what happened

---

## Troubleshooting

### Error: "Can't locate revision"

```bash
# Check alembic_version table
PGPASSWORD="$DB_PASSWORD" psql -d precog_test -c "SELECT * FROM alembic_version"

# If empty or wrong, stamp current version
DB_NAME=precog_test python -m alembic stamp head
```

### Error: "Column already exists"

Migration was partially applied. Options:
1. Use `IF NOT EXISTS` in migration
2. Manually drop column and re-run
3. Stamp to skip: `alembic stamp 0003`

### Error: "Tests fail after migration"

1. Check CRUD includes new columns
2. Verify test database has migration applied
3. Run: `DB_NAME=precog_test python -m alembic upgrade head`

### Database Out of Sync Between Environments

```bash
# Check each environment
DB_NAME=precog_dev python -m alembic current
DB_NAME=precog_test python -m alembic current

# Sync to head
DB_NAME=precog_test python -m alembic upgrade head
```

---

## Cross-References

**Related Patterns:**
- **Pattern 1:** Decimal Precision (use Decimal for price columns)
- **Pattern 2:** Dual Versioning System (SCD Type 2)
- **Pattern 14:** Schema Migration Workflow (condensed version)

**Architecture Decisions:**
- **ADR-089:** Dual-Key Schema Pattern for SCD Type 2 Tables
- **ADR-034:** SCD Type 2 for Slowly Changing Dimensions
- **ADR-018:** Versioned Strategy/Model Immutability

**Alembic Files:**
- **Config:** `src/precog/database/alembic.ini`
- **Environment:** `src/precog/database/alembic/env.py`
- **Migrations:** `src/precog/database/alembic/versions/`

---

**END OF SCHEMA_MIGRATION_WORKFLOW_V2.0.md**
