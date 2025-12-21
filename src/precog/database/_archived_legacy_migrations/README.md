# ============================================================
# ARCHIVED - DO NOT USE - ARCHIVED - DO NOT USE - ARCHIVED
# ============================================================
#
# This folder contains LEGACY migrations that are NO LONGER USED.
# All new migrations MUST use Alembic: ../alembic/versions/
#
# See: docs/utility/SCHEMA_MIGRATION_WORKFLOW_V2.1.md
#
# ============================================================

# Legacy Migrations (Pre-Alembic) - ARCHIVED

---
**Status:** ARCHIVED (DO NOT USE)
**Superseded By:** Alembic migrations in `../alembic/versions/`
**Date Deprecated:** 2025-12-07
**Date Archived:** 2025-12-14

---

## DO NOT USE THESE FILES

The SQL and Python migration files in this folder are **legacy migrations** that were used before the project adopted Alembic as the exclusive migration tool.

### What Happened

1. **Original System (pre-2025-12-05):** Dual-migration system with:
   - SQL migrations (000-016): Direct SQL schema changes
   - Python migrations (011-029+): Python scripts with SQLAlchemy operations

2. **Alembic Baseline (2025-12-05):** Migration 0001 created as a baseline, capturing the complete schema state from all legacy migrations.

3. **Alembic Exclusive (2025-12-07):** All new migrations now use Alembic only.

### Current Migration System

**All new migrations go through Alembic:**

```bash
cd src/precog/database
DB_NAME=precog_test python -m alembic current    # Check version
DB_NAME=precog_test python -m alembic upgrade head   # Apply migrations
DB_NAME=precog_test python -m alembic revision -m "description"  # New migration
```

**Migration files location:** `src/precog/database/alembic/versions/`

### Why Keep These Files?

These files are kept for:
1. **Historical reference** - Understanding schema evolution
2. **Debugging** - If schema issues arise, history helps trace changes
3. **Documentation** - Shows the project's migration journey

### Do NOT

- Add new files to this folder
- Modify existing files
- Reference these files in application code
- Use the CI/CD migration scripts for these files

### For New Migrations

See: `docs/utility/SCHEMA_MIGRATION_WORKFLOW_V2.1.md`

---

## File Inventory

### SQL Migrations (000-016)

| File | Description | Status |
|------|-------------|--------|
| 000_base_schema.sql | Initial schema | Captured in Alembic 0001 |
| 001_add_methods_and_matrix_metadata.sql | Methods table | Captured in Alembic 0001 |
| 002_add_alerts_table.sql | Alerts table | Captured in Alembic 0001 |
| 003_add_strategy_model_attribution.sql | Attribution fields | Captured in Alembic 0001 |
| 004_add_exit_management_columns.sql | Exit columns | Captured in Alembic 0001 |
| 005_fix_scd_type2_and_trades.sql | SCD fixes | Captured in Alembic 0001 |
| 006_add_trade_metadata_and_fix_tests.sql | Trade metadata | Captured in Alembic 0001 |
| 007_add_row_end_ts_scd2_completion.sql | SCD completion | Captured in Alembic 0001 |
| 008_add_external_id_traceability.sql | External IDs | Captured in Alembic 0001 |
| 009_markets_surrogate_primary_key.sql | Market PK | Captured in Alembic 0001 |
| 010_create_teams_and_elo_tables.sql | Teams/Elo | Captured in Alembic 0001 |
| 011_create_venues_table.sql | Venues | Captured in Alembic 0001 |
| 011_fix_market_fk_consistency.sql | Market FKs | Captured in Alembic 0001 |
| 012_create_team_rankings_table.sql | Rankings | Captured in Alembic 0001 |
| 013_enhance_teams_table.sql | Team enhancements | Captured in Alembic 0001 |
| 014_create_game_states_table.sql | Game states | Captured in Alembic 0001 |
| 015_standardize_game_states_scd_columns.sql | SCD columns | Captured in Alembic 0001 |
| 016_create_strategies_and_models_tables.sql | Strategies/Models | Captured in Alembic 0001 |

### Python Migrations (011-029+)

| File | Description | Status |
|------|-------------|--------|
| migration_011_*.py | Classification fields | Captured in Alembic 0001 |
| migration_012_*.py | Approach constraint | Captured in Alembic 0001 |
| migration_013_*.py | Strategies constraint | Captured in Alembic 0001 |
| ... | (additional Python migrations) | Captured in Alembic 0001 |

---

**END OF README.md**
