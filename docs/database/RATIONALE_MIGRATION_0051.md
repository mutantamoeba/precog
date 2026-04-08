# Rationale: Migration 0051 — `account_balance.execution_environment`

**Migration:** `src/precog/database/alembic/versions/0051_account_balance_execution_environment.py`
**PR:** #690
**Closes:** #622 (account_balance schema gap), #686 (PositionManager.open_position caller-layer drop)
**Related (already fixed):** #662 (update_position_price SCD drop, fixed in PR #688)
**Date:** 2026-04-07

This document captures the design rationale for migration 0051 and the
sibling code changes in PR #690. It is the in-repo, version-controlled
record of the cross-agent design council that produced the migration. The
fuller agent-by-agent findings (Mulder, Holden, synthesis) live in the
project memory directory at `~/.claude/projects/.../memory/findings_622_686_*.md`.

---

## The bug class

Three sibling bugs:

| Issue | Layer | Symptom |
|---|---|---|
| #622 | Schema | `account_balance` was missing `execution_environment` column entirely |
| #662 | CRUD | `update_position_price` dropped `execution_environment` on every SCD version |
| #686 | Caller | `PositionManager.open_position` never accepted or passed `execution_environment` |

All three were symptoms of one root cause: **the cross-environment-contamination architecture from migration 0008 (ADR-107) was half-built.** Migration 0008 added the `execution_environment` column to `trades` and `positions`, plus 7 per-mode views (`live_trades`, `paper_positions`, etc.). But the runtime layer that should populate it never connected:

- The CRUD default was `'live'`, which meant any caller that forgot to pass it silently produced live-tagged rows.
- The canonical `PositionManager.open_position` entry point never passed it.
- `account_balance` and `account_ledger` were left out of migration 0008 entirely.
- The 7 per-mode views had **zero production consumers** for ~2 years (verified via grep).
- The `trading.yaml` `environment:` field and `system.yaml` `environment:` block were dead config — nothing in `src/` ever read them.
- No translator function existed to map `(PRECOG_ENV, KALSHI_MODE)` to `execution_environment`. The mapping lived only in human memory.

The design council framed this as: **"the architecture is half-built; what's the right way to FINISH it, given that the data layer is partially in place but the runtime layer never connected?"**

## The five unreconciled vocabularies

Pre-PR-#690, the codebase had **five different vocabularies for the same concept**, with no translator between them:

1. `PRECOG_ENV` = `dev | test | staging | prod` (app env, from `.env`)
2. `MarketMode` enum = `DEMO | LIVE` (API endpoint kind)
3. `execution_environment` DB column = `live | paper | backtest`
4. `trading.yaml environment:` = `demo | prod` (DEAD CODE — deleted in #690)
5. `KalshiClient.environment` attribute = `demo | prod`

The mapping (`KALSHI_MODE=demo` -> `execution_environment='paper'`) existed only as an implicit human assumption. No source file contained the translation logic. The result was the #622/#662/#686 bug class.

## The seven decisions in PR #690

### 1. Required parameter, no Python default

`create_position`, `create_trade`, `create_account_balance`,
`update_account_balance_with_versioning`, `create_order`, `create_edge`
all require `execution_environment` as a positional parameter with NO
Python default.

**Why:** The optional-default `'live'` precedent was the literal cause of
the bug class. Cost of miss with required = TypeError (loud). Cost of miss
with default = silent contamination (indistinguishable from correct
behavior on a money table).

### 2. New translator function — single line of truth

`derive_execution_environment(app_env, market_mode)` in
`config/environment.py` is the SINGLE function in the codebase that maps
the two-axis runtime state to a single `execution_environment` value.
Every CRUD caller MUST obtain its value from this function or pass an
explicit literal — never construct it inline, never read from YAML.

**Mapping:**
- `MarketMode.LIVE` -> `'live'`
- `MarketMode.DEMO` -> `'paper'`
- `'backtest'` is set explicitly by backtest entry points only, never
  derived from runtime axes
- BLOCKED combinations (`test+live`, `prod+demo`) raise `ValueError`
  before any DB write

### 3. Per-domain validator constants

`crud_shared.py` defines:
- `VALID_EXECUTION_ENVIRONMENTS_BALANCE` = 4 values (`live, paper, backtest, unknown`)
- `VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION` = 3 values (no `'unknown'`)

The 4-vs-3 asymmetry is **intentional**: only `account_balance` reserves
`'unknown'` as a forensic tombstone for future backfills of historical
rows of unknown provenance. Trades, positions, orders, and edges follow
the 3-value rule. Per-domain frozensets enforce this at the function
boundary so a Python caller passing `'unknown'` to `create_position`
fails LOUDLY at the function boundary, not on the DB CHECK constraint
with a confusing message.

### 4. Composite unique partial index on `account_balance`

Old: `idx_balance_unique_current ON account_balance(platform_id) WHERE row_current_ind`
New: `idx_balance_unique_current ON account_balance(platform_id, execution_environment) WHERE row_current_ind`

**The index name is preserved** so the SCD retry helper
(`crud_shared.retry_on_scd_unique_conflict`) continues to discriminate by
constraint string. The new index is strictly tighter (composite key),
unique by construction (the old single-column constraint was already
unique on `platform_id WHERE row_current_ind`, so `(platform_id, 'live')`
is also unique after the DEFAULT backfill).

This means **live and paper balances can coexist as parallel current rows
for the same platform_id** post-migration. Queries that need a single
environment MUST filter on both `row_current_ind = TRUE` AND
`execution_environment = %s`. Mode-blind queries are a money-contamination
risk.

### 5. The 8 dropped views

PR #690 drops:
- `current_balances` (from migration 0001) — mode-blind, would silently
  aggregate live + paper + backtest current rows post-migration. PM
  verified zero production consumers via grep.
- `live_trades`, `paper_trades`, `backtest_trades`, `training_data_trades`,
  `live_positions`, `paper_positions`, `backtest_positions` (from
  migration 0008) — recreated 3 times across migrations 0008/0024/0025
  with zero production consumers. Pure maintenance debt.

The 7 per-mode views existed as scaffolding for an analytics layer that
was never built. Future analytics work should use `WHERE
execution_environment = %s` directly against the base tables, mirroring
the existing CRUD pattern. If the views are ever genuinely needed, they
can be re-created in a future migration.

### 6. Why `VARCHAR(20) + CHECK`, not ENUM

Migration 0024 dropped the `execution_environment` ENUM type after
converting `trades` and `positions` to `VARCHAR(20) + CHECK`. The new
column on `account_balance` uses the same pattern for consistency and
to avoid reintroducing a TYPE that was deliberately removed for ALTER
flexibility.

### 7. Single transactional migration, no `CREATE INDEX CONCURRENTLY`

The migration runs as a single transaction. ACCESS EXCLUSIVE on a tiny
table is fine (account_balance has O(platforms × versions) rows, dozens
in any real deployment). `CREATE INDEX CONCURRENTLY` cannot run inside a
transaction and would lose atomicity, so it's intentionally avoided.

## The downgrade ordering bug (caught during local round-trip testing)

The original downgrade recreated `current_balances` view BEFORE dropping
the `execution_environment` column. PostgreSQL refused with
`DependentObjectsStillExist` because `SELECT *` captures the column list
at view creation time, so the view depended on a column that was about
to be dropped.

**Fix:** the downgrade now recreates `current_balances` AFTER the column
drop, so the view's `SELECT *` captures the post-downgrade column list.
Documented in the migration's downgrade docstring with the manual repair
query for the lossy window (when both live and paper current rows exist
for the same platform_id, the downgrade's recreation of the single-column
unique index will fail until the operator collapses one of them).

## What's NOT in this PR (deferred)

PR #690 finishes ~70% of the cross-environment-contamination architecture.
The following gaps were identified by the parallel reviewer pass and
filed as follow-up issues:

| Gap | Issue | Why deferred |
|---|---|---|
| `account_ledger` missing `execution_environment` column | #691 | Same archetype, separate table, schema migration |
| `settlements` missing `execution_environment` column | #691 | Same archetype, ground-truth P&L signal |
| `get_current_positions(execution_environment=None)` mode-blind read default | #691 | Read-path rules, separate from write-path fix |
| `cli/kalshi.py` BLOCKED-ValueError swallow | #692 | CLI safety surface hardening |
| `derive_execution_environment` should log on WARNING combos | #692 | Observability for debug-mode |
| Stale docstring examples in crud_account.py + position_manager.py | #693 | Documentation polish |
| Test invariants for the 4-vs-3 asymmetry | #694 | Future-proofing |
| Type-system alias asymmetry (mypy is permissive) | #695 | Type-system tightening |
| P41 audit gaps (no operator CLI for env introspection) | #696 | Operability follow-up |

**The bug class is closed BY CONSTRUCTION for the 6 functions PR #690
touched.** It is NOT yet closed for `account_ledger`, `settlements`, and
the read-path defaults. Issue #691 tracks the remaining ~30%.

## How a future developer should use this document

If you're reading this because you're looking at migration 0051 in `git
log` or `git blame`: this is the design rationale. The migration docstring
should link here. The CRUD function docstrings should link here. The PR
#690 description links here.

If you're reading this because you found a similar bug class in another
table: the fix shape is in PR #690's commit history. Mirror it.

If you're reading this because you want to add a 5th `MarketMode` value or
a 5th `AppEnvironment` value: update the `EnvironmentConfig.SAFETY_RULES`
dict in `config/environment.py`, the `derive_execution_environment`
function in the same file, and the CHECK constraint on `account_balance`
in a new migration. The runtime validators in `crud_shared.py` should be
updated in sync. Issue #694 tracks adding an automated assertion for this.

If you're reading this because you want to recreate one of the 8 dropped
views: don't, unless you have a real production consumer. Add `WHERE
execution_environment = %s` to your queries instead.

## References

- ADR-107: Single-Database Architecture with Execution Environments (the
  original design that this PR finished implementing)
- ADR-105: Two-Axis Environment Model
- Migration 0008: original ADR-107 scaffolding (added column to trades +
  positions, created the now-dropped views)
- Migration 0024: ENUM -> VARCHAR conversion, dropped the ENUM type
- Migration 0049: account_balance SCD temporal columns + the original
  single-column unique partial index
- Migration 0050: Phase 2 indexes
- Migration 0051: this migration
- PR #688: fixed #662 (update_position_price)
- PR #690: this PR — fixed #622 + #686 + the create_*_default precedent
  for 6 CRUD functions
- Issue #691: follow-up — finish account_ledger + settlements + read paths
- Issue #693: follow-up — documentation including this file's existence
