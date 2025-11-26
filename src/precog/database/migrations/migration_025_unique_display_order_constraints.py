#!/usr/bin/env python3
"""
Migration 025: Add UNIQUE constraints on display_order per category for Lookup Tables

**Rationale:**
Lookup tables (strategy_types, model_classes) have display_order for UI sorting
but no constraint preventing duplicate display_order values within a category.
This could cause non-deterministic UI ordering.

**Schema Changes:**
1. ADD UNIQUE constraint on strategy_types(category, display_order)
2. ADD UNIQUE constraint on model_classes(category, display_order)

**Why This Matters:**
- Prevents: Two strategy_types with same category + display_order
- Ensures: Deterministic dropdown/list ordering in UI
- Catches: Data entry errors at INSERT/UPDATE time

**Example:**
```sql
-- Before constraint: Both rows allowed (broken UI ordering)
INSERT INTO strategy_types (strategy_type_code, category, display_order) VALUES ('value', 'statistical', 1);
INSERT INTO strategy_types (strategy_type_code, category, display_order) VALUES ('arbitrage', 'statistical', 1);

-- After constraint: Second INSERT fails with unique violation
```

**Migration Type:** Schema enhancement (non-breaking)

**References:**
- PR #94 Claude Code Review (L-03)
- Migration 023: Created lookup tables (strategy_types, model_classes)
- GitHub Issue #116

**Migration Safe:** YES
- Constraint only fails if duplicate data exists (should be none)
- Atomic transaction
- Rollback script included

**Estimated Time:** ~10ms (constraint creation)

Created: 2025-11-25
Phase: 1.5 (Foundation Validation)
GitHub Issue: #116
"""

import sys
from pathlib import Path

# Add project root to path for imports
# Using Path for cross-platform compatibility (Ruff PTH120)
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from precog.database.connection import fetch_all, fetch_one, get_cursor  # noqa: E402


def check_prerequisites() -> bool:
    """
    Check if migration can be applied.

    Returns:
        True if prerequisites are met, False otherwise
    """
    # Verify lookup tables exist
    tables = ["strategy_types", "model_classes"]
    for table in tables:
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = %s
            )
        """
        result = fetch_one(query, (table,))
        if not result or not result["exists"]:
            print(f"[ERROR] Table '{table}' does not exist")
            return False

    return True


def check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    """
    Check if a constraint already exists.

    Args:
        table_name: Table to check
        constraint_name: Name of constraint

    Returns:
        True if constraint exists, False otherwise
    """
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.table_constraints
            WHERE table_schema = 'public'
            AND table_name = %s
            AND constraint_name = %s
        )
    """
    result = fetch_one(query, (table_name, constraint_name))
    return result["exists"] if result else False


def check_duplicate_display_order(table_name: str) -> list[dict]:
    """
    Check for existing duplicate display_order values per category.

    Args:
        table_name: Table to check

    Returns:
        List of duplicates found (empty if none)
    """
    query = f"""
        SELECT category, display_order, COUNT(*) as cnt
        FROM {table_name}
        WHERE display_order IS NOT NULL
        GROUP BY category, display_order
        HAVING COUNT(*) > 1
    """
    result = fetch_all(query)
    return result if result else []


def run_migration() -> bool:
    """
    Execute migration 025: Add UNIQUE constraints on display_order.

    Returns:
        True if successful, False otherwise
    """
    print("=" * 60)
    print("Migration 025: Add UNIQUE Constraints on display_order")
    print("=" * 60)

    # Check prerequisites
    print("\n[1/4] Checking prerequisites...")
    if not check_prerequisites():
        print("[FAIL] Prerequisites not met")
        return False
    print("[OK] Prerequisites met")

    # Define constraints to create
    constraints = [
        {
            "table": "strategy_types",
            "name": "unique_strategy_types_display_order",
            "columns": "category, display_order",
        },
        {
            "table": "model_classes",
            "name": "unique_model_classes_display_order",
            "columns": "category, display_order",
        },
    ]

    # Check for duplicates before creating constraints
    print("\n[2/4] Checking for duplicate display_order values...")
    has_duplicates = False
    for c in constraints:
        duplicates = check_duplicate_display_order(c["table"])
        if duplicates:
            print(f"  [WARN] Duplicates found in {c['table']}:")
            for dup in duplicates:
                print(
                    f"         category={dup['category']}, display_order={dup['display_order']}, count={dup['cnt']}"
                )
            has_duplicates = True

    if has_duplicates:
        print("[ERROR] Cannot add UNIQUE constraints with existing duplicates")
        print("        Fix duplicates first, then re-run migration")
        return False
    print("[OK] No duplicate display_order values found")

    # Create constraints
    print("\n[3/4] Creating UNIQUE constraints...")
    created_count = 0
    skipped_count = 0

    with get_cursor(commit=True) as cursor:
        for c in constraints:
            if check_constraint_exists(c["table"], c["name"]):
                print(f"  [SKIP] {c['name']} already exists on {c['table']}")
                skipped_count += 1
                continue

            # Add UNIQUE constraint
            # Note: Using partial index to allow multiple NULLs (display_order can be NULL)
            create_sql = f"""
                CREATE UNIQUE INDEX {c["name"]}
                ON {c["table"]} ({c["columns"]})
                WHERE display_order IS NOT NULL
            """
            cursor.execute(create_sql)
            print(f"  [OK] Created {c['name']} on {c['table']}")
            created_count += 1

    # Verify constraints
    print("\n[4/4] Verifying constraints...")
    all_verified = True
    for c in constraints:
        # Check as index (we created partial unique index)
        query = """
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = %s
                AND indexname = %s
            )
        """
        result = fetch_one(query, (c["table"], c["name"]))
        if result and result["exists"]:
            print(f"  [OK] {c['name']} exists")
        else:
            print(f"  [FAIL] {c['name']} not found")
            all_verified = False

    if not all_verified:
        print("[FAIL] Some constraints failed to create")
        return False

    # Summary
    print("\n" + "=" * 60)
    print("[OK] Migration 025 completed successfully")
    print(f"     Created: {created_count} constraints")
    print(f"     Skipped: {skipped_count} constraints (already existed)")
    print("=" * 60)

    return True


def rollback_migration() -> bool:
    """
    Rollback migration 025: Remove UNIQUE constraints.

    Returns:
        True if successful, False otherwise
    """
    print("=" * 60)
    print("Rollback Migration 025: Remove UNIQUE Constraints")
    print("=" * 60)

    indexes_to_drop = [
        "unique_strategy_types_display_order",
        "unique_model_classes_display_order",
    ]

    dropped_count = 0
    with get_cursor(commit=True) as cursor:
        for index_name in indexes_to_drop:
            cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
            print(f"  [OK] Dropped {index_name}")
            dropped_count += 1

    print(f"\n[OK] Rollback complete. Dropped {dropped_count} indexes.")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Migration 025: UNIQUE Constraints on display_order"
    )
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")
    args = parser.parse_args()

    success = rollback_migration() if args.rollback else run_migration()

    sys.exit(0 if success else 1)
