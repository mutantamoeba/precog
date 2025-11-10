# Strategic Work Roadmap - Precog Project

---
**Document:** STRATEGIC_WORK_ROADMAP_V1.0.md
**Version:** 1.0
**Created:** 2025-11-09
**Last Updated:** 2025-11-09
**Status:** ✅ Current
**Purpose:** Master roadmap of 25 strategic tasks organized by category with research dependencies
**Target Audience:** Product owner, development team, future contributors
**Related Documents:**
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.13.md` (ADR-076, ADR-077 open questions)
- `docs/foundation/DEVELOPMENT_PHASES_V1.7.md` (Phase 4.5 research phase)
- `docs/utility/PHASE_4_DEFERRED_TASKS_V1.0.md` (11 detailed research tasks)

---

## 📋 Table of Contents

1. [Introduction](#introduction)
2. [🚨 RESEARCH REQUIREMENTS (CRITICAL)](#-research-requirements-critical)
3. [Strategic Tasks by Category](#strategic-tasks-by-category)
   - [Architecture & Infrastructure (5 tasks)](#category-1-architecture--infrastructure-5-tasks)
   - [Modeling & Edge Detection (6 tasks)](#category-2-modeling--edge-detection-6-tasks)
   - [Strategy & Position Management (7 tasks)](#category-3-strategy--position-management-7-tasks)
   - [Analytics & Reporting (4 tasks)](#category-4-analytics--reporting-4-tasks)
   - [Platform & Deployment (3 tasks)](#category-5-platform--deployment-3-tasks)
4. [Timeline & Dependencies](#timeline--dependencies)
5. [Success Metrics](#success-metrics)

---

## Introduction

### Purpose

This document provides a **strategic roadmap** of 25 high-value tasks spanning Phases 1-10 of the Precog project. Unlike `DEVELOPMENT_PHASES_V1.7.md` (which provides chronological implementation details), this roadmap organizes work by **strategic category** and **priority**.

### Philosophy

**Precog is a research-driven project.** We prioritize:
1. **Research before implementation** - Gather data, conduct focused research, make informed decisions
2. **Profitability over features** - Build capabilities that directly improve edge detection and trading performance
3. **Architecture that enables experimentation** - Support rapid A/B testing and version comparison
4. **Long-term sustainability** - Invest in infrastructure that scales across platforms and markets

### How to Use This Document

**For Product Owners:**
- Review RESEARCH REQUIREMENTS section to understand open architectural questions
- Prioritize tasks within each category based on business value
- Track progress using task IDs (STRAT-001 through STRAT-025)

**For Developers:**
- Check task dependencies before starting work (many tasks depend on ADR-076/ADR-077 research)
- Cross-reference with `DEVELOPMENT_PHASES_V1.7.md` for implementation timing
- Use task descriptions as starting point for detailed design

**For Researchers:**
- Section 2 (RESEARCH REQUIREMENTS) identifies the three highest-priority research areas
- See `PHASE_4_DEFERRED_TASKS_V1.0.md` for detailed research task descriptions

---

## 🚨 RESEARCH REQUIREMENTS (CRITICAL)

**⚠️ READ THIS SECTION BEFORE PRIORITIZING STRATEGIC TASKS ⚠️**

### Why Research Matters

**Many strategic tasks CANNOT be implemented** until we resolve fundamental architectural questions. Rather than guess at solutions and potentially build the wrong thing, we will:

1. **Gather real-world data** from Phase 1-3 usage (6-9 months of development experience)
2. **Conduct focused research** in dedicated Phase 4.5 (6-8 weeks)
3. **Make informed architectural decisions** based on data, not speculation
4. **Implement solutions** in Phase 5+ with confidence

### Research Priority #1: STRATEGIES (MOST IMPORTANT) 🔴

**ADR-077: Strategy vs Method Separation (Phase 4.0 Research) - HIGHEST PRIORITY**

**Status:** 🔵 Open Question - **CRITICAL RESEARCH REQUIRED**

**Problem:**
Current architecture separates **strategies** (entry/exit logic) from **methods** (complete trading system bundles), but **boundaries are ambiguous**.

**Example:**
```yaml
# From trade_strategies.yaml
hedge_strategy:
  entry_logic: halftime_or_inplay       # Clearly "strategy"
  exit_conditions: [stop_loss, profit_target]  # Clearly "strategy"
  hedge_sizing_method: partial_lock     # Is this "strategy" or "position management"?
  partial_lock:
    profit_lock_percentage: "0.70"      # Is this "strategy parameter" or "position management parameter"?
```

**If boundaries are wrong:**
- Users can't customize strategies effectively (unclear what to change)
- A/B testing workflows break (can't isolate performance to specific changes)
- Version combinatorics explode (strategy × model × position × risk × execution)

**Research Tasks (CRITICAL PRIORITY):**
- **DEF-013:** Strategy Config Taxonomy (8-10h, 🔴 Critical)
- **DEF-014:** A/B Testing Workflows Validation (10-12h, 🔴 Critical)
- **DEF-015:** User Customization Patterns Research (6-8h, 🟡 High)
- **DEF-016:** Version Combinatorics Modeling (4-6h, 🟡 High)

**Detailed Documentation:** See `PHASE_4_DEFERRED_TASKS_V1.0.md` Section 1

**Strategic Tasks Blocked:**
- STRAT-008: Strategy vs Method Separation (⚠️ PENDING ADR-077)
- STRAT-013: Multi-Leg Strategies (⚠️ PENDING ADR-077)
- STRAT-016: Trade Attribution Analytics (⚠️ PENDING ADR-077)
- STRAT-018: Performance Comparison Framework (⚠️ PENDING ADR-077)

**Timeline:** Research in Phase 4.5 (April-May 2026), implementation in Phase 5+ (June 2026+)

---

### Research Priority #2: MODELS (High Priority) 🟡

**ADR-076: Dynamic Ensemble Weights Architecture (Phase 4.5 Research)**

**Status:** 🔵 Open Question - **RESEARCH REQUIRED**

**Problem:**
Current ensemble uses **STATIC weights** hardcoded in `probability_models.yaml`:
```yaml
ensemble:
  models: [elo, regression, ml]
  weights:
    elo: "0.40"        # STATIC - never changes
    regression: "0.35"  # STATIC - never changes
    ml: "0.25"         # STATIC - never changes
```

**This creates a fundamental architectural tension:**
1. **Versioning system requires immutability** (ADR-019: configs never change)
2. **Performance requires dynamic weights** (models improve/degrade over time)

**If architecture is wrong:**
- Stuck with suboptimal weights as model performance shifts
- OR break immutability and lose A/B testing attribution
- OR version explosion (ensemble_v1.0, ensemble_v1.1, ... ensemble_v52.0 for weekly updates)

**Research Tasks:**
- **DEF-009:** Backtest Static vs Dynamic Performance (15-20h, 🟡 High)
- **DEF-010:** Weight Calculation Methods Comparison (10-15h, 🟡 High)
- **DEF-011:** Version Explosion Analysis (5-8h, 🟢 Medium)
- **DEF-012:** Ensemble Versioning Strategy Documentation (6-8h, 🟢 Medium)

**Detailed Documentation:** See `PHASE_4_DEFERRED_TASKS_V1.0.md` Section 2

**Strategic Tasks Blocked:**
- STRAT-006: Dynamic Ensemble Weights Implementation (⚠️ PENDING ADR-076)

**Timeline:** Research in Phase 4.5 (April-May 2026), implementation in Phase 5+ (June 2026+)

---

### Research Priority #3: EDGE DETECTION (Medium Priority) 🟢

**Quick-Win Research Tasks** (not blocking major strategic initiatives)

**Problem:**
Current edge detection uses **simplified assumptions**:
- Fixed fee percentage (7%) - ignores fee tiers, maker rebates
- No confidence intervals - single-point edge estimates
- No market correlation analysis - treats markets as independent

**Research Tasks (Quick Wins):**
- **DEF-017:** Fee Impact Sensitivity Analysis (3-4h, 🟢 Medium)
- **DEF-018:** Confidence Interval Methods Research (4-5h, 🟢 Medium)
- **DEF-019:** Market Correlation Analysis (3-4h, 🟢 Medium)

**Detailed Documentation:** See `PHASE_4_DEFERRED_TASKS_V1.0.md` Section 3

**Strategic Tasks Affected:**
- STRAT-011: Advanced Edge Detection (not blocked, but enhanced by research)

**Timeline:** Research in Phase 4.5 (April-May 2026), implementation in Phase 5-6 (June-August 2026)

---

### Research Summary

| Research Priority | ADR | Tasks | Effort | Blocking Tasks |
|-------------------|-----|-------|--------|----------------|
| **#1: STRATEGIES** 🔴 | ADR-077 | 4 tasks (DEF-013 to DEF-016) | 28-36h | 4 strategic tasks |
| **#2: MODELS** 🟡 | ADR-076 | 4 tasks (DEF-009 to DEF-012) | 36-51h | 1 strategic task |
| **#3: EDGE DETECTION** 🟢 | N/A | 3 tasks (DEF-017 to DEF-019) | 10-13h | 0 strategic tasks (enhancements only) |
| **TOTAL** | | **11 tasks** | **74-92h** (6-8 weeks) | **5 strategic tasks blocked** |

**Decision Point:** After Phase 4.5 research complete (May 2026), we will update ADR-076 and ADR-077 with **final decisions** and unblock strategic tasks for Phase 5+ implementation.

---

## Strategic Tasks by Category

**Task Numbering:** STRAT-001 through STRAT-025

**Priority Levels:**
- 🔴 **Critical:** Must-have for profitable trading
- 🟡 **High:** Major performance improvement or risk reduction
- 🟢 **Medium:** Nice-to-have enhancements or efficiency improvements

**Dependency Markers:**
- ⚠️ **PENDING ADR-076:** Blocked until ensemble weights research complete (Phase 4.5)
- ⚠️ **PENDING ADR-077:** Blocked until strategy/method separation research complete (Phase 4.5)

---

## Category 1: Architecture & Infrastructure (5 tasks)

### STRAT-001: Database Performance Optimization (Phase 5-6, 🟡 High Priority)

**Task ID:** STRAT-001
**Priority:** 🟡 High
**Estimated Effort:** 15-20 hours
**Target Phase:** 5-6 (June-August 2026)
**Dependencies:** Phase 1-4 usage data (identify actual query patterns)
**Related Requirements:** REQ-SYS-004 (Database Performance)

#### Problem
Current database schema (V1.7) uses **minimal indexing** to avoid premature optimization. As trading volume increases (Phase 5+), query performance will degrade without optimization.

**Predicted bottlenecks:**
- **Position queries** (row_current_ind = TRUE filters across 100k+ rows)
- **Market lookups** (series_ticker filters, status filters)
- **Trade attribution** (complex joins across trades, strategies, models)
- **Historical analysis** (date range queries across millions of rows)

#### Research Objectives
1. **Profile actual query patterns** from Phase 1-4 usage logs
2. **Identify slow queries** (>100ms execution time)
3. **Design indexes** for frequently-used WHERE/JOIN clauses
4. **Benchmark improvements** (before/after index creation)

#### Implementation Tasks
**Task 1: Query Profiling (4-5 hours)**
- Enable PostgreSQL query logging (log queries >50ms)
- Run typical workload (1 week of Phase 4 usage)
- Extract top 20 slowest queries

**Task 2: Index Design (3-4 hours)**
- Create indexes for frequently-filtered columns
- Composite indexes for multi-column WHERE clauses
- Partial indexes for row_current_ind = TRUE queries

**Example indexes:**
```sql
-- Positions by current status (most common query)
CREATE INDEX idx_positions_current ON positions(row_current_ind, position_status)
  WHERE row_current_ind = TRUE;

-- Markets by series ticker and status
CREATE INDEX idx_markets_series_status ON markets(series_ticker, status)
  WHERE row_current_ind = TRUE;

-- Trades by strategy and timestamp (attribution queries)
CREATE INDEX idx_trades_strategy_time ON trades(strategy_id, created_at DESC);
```

**Task 3: Benchmark Testing (3-4 hours)**
- Run EXPLAIN ANALYZE on top 20 queries before indexes
- Create indexes
- Re-run EXPLAIN ANALYZE after indexes
- Document improvements (execution time reduction %)

**Task 4: Connection Pool Tuning (2-3 hours)**
- Configure pgBouncer or connection pooling
- Tune pool size based on concurrent workload
- Monitor connection usage

**Task 5: Vacuum & Maintenance Automation (3-4 hours)**
- Configure autovacuum settings (prevent table bloat)
- Set up weekly VACUUM ANALYZE jobs
- Monitor table/index bloat

#### Deliverable
- **Document:** `DATABASE_PERFORMANCE_REPORT_V1.0.md` (~150 lines)
  - Query profiling results
  - Index design rationale
  - Benchmark improvements (before/after)
  - Maintenance recommendations
- **Migration:** `database/migrations/0XX_add_performance_indexes.sql`

#### Success Criteria
- [ ] Top 20 queries profiled with execution times
- [ ] Indexes designed for 90%+ of slow queries
- [ ] Benchmark shows 50%+ average execution time reduction
- [ ] No degradation in write performance (<5% INSERT/UPDATE slowdown)
- [ ] Connection pooling configured and tested
- [ ] Autovacuum tuned for workload

---

### STRAT-002: Configuration Validation Automation (Phase 2-3, 🟢 Medium Priority)

**Task ID:** STRAT-002
**Priority:** 🟢 Medium
**Estimated Effort:** 8-10 hours
**Target Phase:** 2-3 (January-February 2026)
**Dependencies:** Phase 1 config loader complete
**Related Requirements:** REQ-VALIDATION-001 (Config Validation)

#### Problem
Current YAML configuration files (7 files, 396+ lines) use **manual validation** via `validate_docs.py`. This catches syntax errors but **does not validate schema** (required fields, valid ranges, cross-file consistency).

**Risk:**
- Missing required fields (e.g., `kelly_fraction` omitted) → runtime errors
- Invalid values (e.g., `kelly_fraction: "1.5"` > 1.0) → incorrect behavior
- Cross-file inconsistencies (e.g., `markets.yaml` references model not in `probability_models.yaml`)

#### Research Objectives
1. **Define YAML schema** for all 7 config files
2. **Implement schema validation** (library choice: Pydantic, Cerberus, or jsonschema)
3. **Automate validation** (pre-commit hook + startup check)
4. **Document validation rules** (what gets checked, why)

#### Implementation Tasks
**Task 1: Schema Definition (3-4 hours)**
- Review all 7 YAML config files
- Document required fields, optional fields, value ranges
- Define cross-file consistency rules

**Example schema (markets.yaml, NFL league):**
```python
from pydantic import BaseModel, Field
from decimal import Decimal

class NFLLeagueConfig(BaseModel):
    enabled: bool
    series_tickers: list[str]
    min_liquidity: int = Field(ge=0)
    max_spread: Decimal = Field(ge=0, le=1)
    kelly_fraction: Decimal = Field(ge=0, le=1)
    min_edge: Decimal = Field(ge=-1, le=1)

    # Cross-file validation (Phase 2.5)
    # Verify series_tickers exist in Kalshi API
    # Verify kelly_fraction matches trade_strategies.yaml
```

**Task 2: Validation Library Integration (2-3 hours)**
- Choose validation library (recommend Pydantic for type safety)
- Implement schema classes for all 7 config files
- Add validation to `config_loader.py` startup

**Task 3: Pre-Commit Hook (1-2 hours)**
- Add config validation to `.pre-commit-config.yaml`
- Run validation on YAML file changes
- Block commits if validation fails

**Task 4: Error Messaging (2-3 hours)**
- Improve error messages (show exact field, value, constraint)
- Add suggestions for common mistakes
- Document all validation rules in `CONFIGURATION_GUIDE_V3.2.md`

#### Deliverable
- **Code:** `config/schema_validators.py` (Pydantic schema classes)
- **Updated:** `config/config_loader.py` (add validation calls)
- **Updated:** `.pre-commit-config.yaml` (add validation hook)
- **Document:** `CONFIGURATION_GUIDE_V3.2.md` (validation rules section)

#### Success Criteria
- [ ] Schema defined for all 7 YAML config files
- [ ] Validation catches 100% of required field omissions
- [ ] Validation catches 100% of value range violations
- [ ] Pre-commit hook blocks invalid config commits
- [ ] Error messages clear and actionable
- [ ] Documentation updated with validation rules

---

### STRAT-003: Multi-Platform Abstraction Layer (Phase 10, 🟡 High Priority)

**Task ID:** STRAT-003
**Priority:** 🟡 High
**Estimated Effort:** 20-25 hours
**Target Phase:** 10 (Cross-Platform Trading, December 2026-January 2027)
**Dependencies:** Phase 1 Kalshi API complete, Polymarket API research
**Related Requirements:** REQ-API-005 (Multi-Platform Support)

#### Problem
Current API client (`api_connectors/kalshi_client.py`) is **Kalshi-specific**. When adding Polymarket (Phase 10), we risk code duplication and inconsistent interfaces.

**Without abstraction layer:**
- Duplicate authentication logic (RSA-PSS vs wallet signatures)
- Duplicate rate limiting (different limits per platform)
- Duplicate error handling (platform-specific error codes)
- Hard to add new platforms (Predictit, Manifold, etc.)

#### Research Objectives
1. **Define platform-agnostic interface** (abstract base class)
2. **Identify platform-specific vs common logic**
3. **Design authentication abstraction** (supports RSA-PSS, ECDSA, HMAC)
4. **Design rate limiter abstraction** (supports different limits per platform)

#### Implementation Tasks
**Task 1: Interface Design (4-5 hours)**
- Define `BasePlatformClient` abstract class
- Document required methods (get_markets, get_positions, place_order, cancel_order, etc.)
- Define standard return types (TypedDict or Pydantic models)

**Example interface:**
```python
from abc import ABC, abstractmethod
from typing import List
from decimal import Decimal

class BasePlatformClient(ABC):
    """Abstract base class for all platform API clients."""

    @abstractmethod
    def authenticate(self) -> None:
        """Authenticate with platform (implementation varies)."""
        pass

    @abstractmethod
    def get_markets(self, filters: dict) -> List[MarketData]:
        """Fetch markets matching filters.

        Returns:
            List of MarketData (standardized format across platforms)
        """
        pass

    @abstractmethod
    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        price: Decimal
    ) -> OrderResponse:
        """Place order (buy/sell).

        Returns:
            OrderResponse (standardized format across platforms)
        """
        pass
```

**Task 2: Kalshi Client Refactoring (6-8 hours)**
- Refactor `kalshi_client.py` to implement `BasePlatformClient`
- Extract Kalshi-specific logic to separate methods
- Ensure backward compatibility (all existing code still works)

**Task 3: Polymarket Client Stub (4-5 hours)**
- Implement `PolymarketClient(BasePlatformClient)`
- Wallet authentication (ECDSA signatures)
- CLOB API integration (limit orders, market orders)
- Gas estimation and transaction building

**Task 4: Platform Factory (2-3 hours)**
- Create `PlatformClientFactory` (factory pattern)
- Select client based on platform_id ("kalshi", "polymarket")
- Load platform-specific config from `markets.yaml`

**Example factory:**
```python
class PlatformClientFactory:
    @staticmethod
    def create(platform_id: str) -> BasePlatformClient:
        if platform_id == "kalshi":
            return KalshiClient()
        elif platform_id == "polymarket":
            return PolymarketClient()
        else:
            raise ValueError(f"Unknown platform: {platform_id}")
```

**Task 5: Cross-Platform Testing (4-5 hours)**
- Create mock responses for both platforms
- Test factory creates correct client
- Test interface consistency (same method signatures)
- Test error handling (platform errors → standardized exceptions)

#### Deliverable
- **Code:** `api_connectors/base_client.py` (abstract interface)
- **Updated:** `api_connectors/kalshi_client.py` (implements BasePlatformClient)
- **Code:** `api_connectors/polymarket_client.py` (implements BasePlatformClient)
- **Code:** `api_connectors/factory.py` (client factory)
- **Tests:** `tests/unit/api_connectors/test_platform_abstraction.py`
- **Document:** Updated `API_INTEGRATION_GUIDE_V2.1.md` (multi-platform section)

#### Success Criteria
- [ ] BasePlatformClient interface defined with 10+ abstract methods
- [ ] KalshiClient refactored to implement interface (all tests still pass)
- [ ] PolymarketClient stub implemented (basic authentication + get_markets)
- [ ] Factory pattern working (creates correct client based on platform_id)
- [ ] Interface consistency validated (same method signatures across platforms)
- [ ] Error handling standardized (platform exceptions → common exception types)

---

### STRAT-004: Real-Time Monitoring Dashboard (Phase 5-6, 🟡 High Priority)

**Task ID:** STRAT-004
**Priority:** 🟡 High
**Estimated Effort:** 25-30 hours
**Target Phase:** 5-6 (Position Monitoring, June-August 2026)
**Dependencies:** Phase 5 position monitoring complete, database schema stable
**Related Requirements:** REQ-OBSERV-002 (Real-Time Monitoring)

#### Problem
Current monitoring is **log-based only** (structured logs via `logger.py`). For active trading (Phase 5+), we need **real-time visibility** into:
- Open positions (P&L, risk exposure)
- Live trades (executions, fills, slippage)
- System health (API connectivity, database load)
- Alert conditions (stop loss triggered, position limits exceeded)

**Without dashboard:**
- Blind to position status until logs reviewed (too slow for trading)
- Can't quickly diagnose issues (database lag, API errors)
- No historical trends visualization (P&L over time, Sharpe ratio)

#### Research Objectives
1. **Choose dashboard technology** (Grafana, Streamlit, custom web app)
2. **Design dashboard layout** (what metrics, what visualizations)
3. **Implement data pipeline** (database → dashboard updates)
4. **Add alerting** (email/SMS when conditions met)

#### Implementation Tasks
**Task 1: Technology Selection (3-4 hours)**
- Evaluate 3 options: Grafana (industry standard), Streamlit (Python-native), custom web app (Flask/FastAPI)
- **Recommendation:** Grafana + PostgreSQL + Prometheus (industry standard, powerful querying)
- Document decision rationale (ADR-078)

**Task 2: Dashboard Layout Design (4-5 hours)**
- Sketch dashboard panels (P&L, positions, trades, system health)
- Define key metrics (total P&L, open positions count, Sharpe ratio, win rate)
- Choose visualizations (line charts for P&L, tables for positions, gauges for system health)

**Example dashboard panels:**
```
+------------------+------------------+
| Total P&L        | Open Positions   |
| $1,234.56        | 12 positions     |
| Line chart (24h) | Position table   |
+------------------+------------------+
| Recent Trades    | System Health    |
| Trade table      | API status: OK   |
| Last 20 trades   | DB latency: 15ms |
+------------------+------------------+
```

**Task 3: Grafana Setup (4-5 hours)**
- Install Grafana (Docker container recommended)
- Configure PostgreSQL data source
- Create initial dashboard with 4 panels

**Task 4: Metrics Queries (6-8 hours)**
- Write SQL queries for each metric
- Optimize queries (use indexes, materialized views if needed)
- Test query performance (<1s refresh)

**Example queries:**
```sql
-- Total P&L (realized + unrealized)
SELECT
    SUM(realized_pnl) + SUM(unrealized_pnl) AS total_pnl
FROM positions
WHERE row_current_ind = TRUE;

-- Open positions with P&L
SELECT
    ticker,
    position_status,
    quantity,
    entry_price,
    current_price,
    unrealized_pnl,
    (current_price - entry_price) / entry_price AS pnl_pct
FROM positions
WHERE row_current_ind = TRUE
  AND position_status = 'open'
ORDER BY unrealized_pnl DESC;
```

**Task 5: Alerting Configuration (4-5 hours)**
- Configure Grafana alerts (email/Slack notifications)
- Define alert conditions:
  - Stop loss triggered (position closed due to stop loss)
  - Position limit exceeded (>20 open positions)
  - Database lag (query latency >500ms)
  - API errors (>5 failed requests in 1 minute)
- Test alert delivery

**Task 6: Historical Trends (4-5 hours)**
- Add time-series panels (P&L over time, Sharpe ratio, win rate)
- Configure refresh intervals (1s for live data, 1min for historical)
- Add date range selector

#### Deliverable
- **Infrastructure:** Grafana instance (Docker container or cloud hosted)
- **Code:** `analytics/dashboard_queries.sql` (optimized metrics queries)
- **Config:** Grafana dashboard JSON export (for version control)
- **Document:** `MONITORING_DASHBOARD_GUIDE_V1.0.md` (~200 lines)
  - Dashboard layout and metrics definitions
  - Alert configuration
  - Query optimization notes
- **Optional:** Prometheus exporters for custom metrics (Phase 6+)

#### Success Criteria
- [ ] Grafana installed and accessible via web browser
- [ ] 4 dashboard panels implemented (P&L, positions, trades, system health)
- [ ] All metrics queries execute in <1s
- [ ] Real-time updates working (1s refresh for live data)
- [ ] Alerts configured for 4+ critical conditions
- [ ] Historical trends visible (P&L over time, Sharpe ratio)
- [ ] Documentation complete with screenshots

---

### STRAT-005: Disaster Recovery & Backup Automation (Phase 3-4, 🟢 Medium Priority)

**Task ID:** STRAT-005
**Priority:** 🟢 Medium
**Estimated Effort:** 10-12 hours
**Target Phase:** 3-4 (Data Pipeline Stability, March-April 2026)
**Dependencies:** Phase 1 database schema stable, Phase 2 data pipeline working
**Related Requirements:** REQ-SYS-005 (Disaster Recovery)

#### Problem
Current database has **no automated backups**. If database becomes corrupted or accidentally deleted:
- **Data loss:** All historical trades, positions, market data (unrecoverable)
- **Downtime:** Must rebuild from scratch (days of work)
- **Compliance risk:** Tax records lost (IRS issues)

#### Research Objectives
1. **Define backup strategy** (frequency, retention, storage location)
2. **Implement automated backups** (pg_dump, WAL archiving, or cloud backups)
3. **Test recovery procedures** (restore from backup, validate data integrity)
4. **Document runbooks** (how to recover from various failure scenarios)

#### Implementation Tasks
**Task 1: Backup Strategy Design (2-3 hours)**
- Choose backup method: pg_dump (simple), WAL archiving (point-in-time recovery), or cloud (AWS RDS automated backups)
- **Recommendation:** pg_dump daily + WAL archiving hourly (balance simplicity and recovery granularity)
- Define retention policy (keep 30 daily backups, 12 monthly backups)
- Choose storage location (local disk + cloud S3)

**Task 2: pg_dump Automation (3-4 hours)**
- Write backup script (`scripts/backup_database.sh`)
- Schedule daily backups via cron
- Compress backups (gzip to save space)
- Upload to S3 (optional, for off-site storage)

**Example backup script:**
```bash
#!/bin/bash
# Daily PostgreSQL backup

BACKUP_DIR="/var/backups/precog"
DATE=$(date +%Y-%m-%d)
DB_NAME="precog_db"

# Dump database
pg_dump -U precog_user -Fc $DB_NAME > "$BACKUP_DIR/precog_$DATE.dump"

# Compress (gzip)
gzip "$BACKUP_DIR/precog_$DATE.dump"

# Upload to S3 (optional)
aws s3 cp "$BACKUP_DIR/precog_$DATE.dump.gz" s3://precog-backups/daily/

# Delete backups older than 30 days
find "$BACKUP_DIR" -name "precog_*.dump.gz" -mtime +30 -delete
```

**Task 3: WAL Archiving (3-4 hours)**
- Configure PostgreSQL WAL archiving (continuous backup)
- Set up WAL archive directory
- Test WAL archiving (trigger checkpoint, verify WAL files created)

**Task 4: Recovery Testing (2-3 hours)**
- Simulate database failure (delete test database)
- Restore from pg_dump backup
- Validate data integrity (row counts, checksums)
- Document recovery time (target: <30 minutes)

**Task 5: Runbook Documentation (2-3 hours)**
- Document 5 failure scenarios:
  1. Accidental table deletion (restore from WAL)
  2. Database corruption (restore from pg_dump)
  3. Entire server loss (restore from S3 backup)
  4. Point-in-time recovery (restore to specific timestamp)
  5. Schema migration failure (rollback and restore)
- Include step-by-step recovery instructions
- Include validation checklists (how to verify data integrity)

#### Deliverable
- **Script:** `scripts/backup_database.sh` (automated backup script)
- **Config:** Cron job configuration (daily backups at 2 AM)
- **Config:** PostgreSQL WAL archiving configuration (`postgresql.conf` updates)
- **Document:** `DISASTER_RECOVERY_RUNBOOK_V1.0.md` (~300 lines)
  - Backup strategy and retention policy
  - Recovery procedures for 5 failure scenarios
  - Validation checklists
- **Optional:** S3 bucket configuration (for off-site backups)

#### Success Criteria
- [ ] Automated daily backups working (verified for 1 week)
- [ ] WAL archiving configured and tested
- [ ] Backups uploaded to S3 (off-site storage)
- [ ] Recovery tested from both pg_dump and WAL
- [ ] Recovery time <30 minutes (pg_dump restore)
- [ ] Runbook documented with 5 failure scenarios
- [ ] Retention policy automated (old backups deleted)

---

## Category 2: Modeling & Edge Detection (6 tasks)

### STRAT-006: Dynamic Ensemble Weights Implementation (Phase 5-6, 🔴 Critical Priority) ⚠️ PENDING ADR-076

**Task ID:** STRAT-006
**Priority:** 🔴 Critical
**Estimated Effort:** 20-25 hours
**Target Phase:** 5-6 (June-August 2026) **AFTER Phase 4.5 research complete**
**Dependencies:** ⚠️ **PENDING ADR-076** (Dynamic Ensemble Weights Research)
**Related Requirements:** REQ-MODEL-004 (Dynamic Ensemble Weights)

#### ⚠️ BLOCKED UNTIL RESEARCH COMPLETE

**This task CANNOT be implemented until ADR-076 research is complete** (Phase 4.5, April-May 2026).

**Research tasks that must complete first:**
- DEF-009: Backtest Static vs Dynamic Performance (15-20h)
- DEF-010: Weight Calculation Methods Comparison (10-15h)
- DEF-011: Version Explosion Analysis (5-8h)
- DEF-012: Ensemble Versioning Strategy Documentation (6-8h)

**See:** `PHASE_4_DEFERRED_TASKS_V1.0.md` Section 2 for detailed research task descriptions.

**After research complete (May 2026):**
- ADR-076 will be updated with **final decision** (Option A, B, or C)
- This task will be **unblocked** and implementation can begin

#### Problem (High-Level)
Current ensemble uses **STATIC weights** hardcoded in config. Models improve/degrade over time, but weights never adapt. This creates tension between:
1. **Immutability** (ADR-019: configs never change)
2. **Performance** (optimal weights change as models evolve)

#### Potential Solutions (Research Will Decide)
**Option A:** Keep static weights (if backtests show <5% improvement from dynamic)
**Option B:** Daily/weekly weight updates with new versions (if version explosion acceptable)
**Option C:** Mutable weight field + separate immutable config (if architectural change justified)

#### Implementation Tasks (Conditional on ADR-076 Decision)
**If Option A chosen:** No implementation needed (research validated current approach)

**If Option B chosen (Daily/Weekly Versioning):**
- Implement weight calculation script (daily cron job)
- Create new ensemble version automatically
- Migrate active positions to new version

**If Option C chosen (Mutable Weights):**
- Add `current_weights` JSONB field (mutable)
- Separate `config` (immutable) from `current_weights` (mutable)
- Update ensemble prediction logic to use `current_weights`

#### Deliverable (TBD based on ADR-076 decision)
- **Code:** Implementation varies based on Option A/B/C
- **Migration:** Database schema changes (if Option C)
- **Document:** Updated `VERSIONING_GUIDE_V1.1.md` (ensemble weights section)
- **Tests:** Unit tests for weight calculation and version migration

#### Success Criteria (TBD based on ADR-076 decision)
- Criteria depend on which option is chosen
- See ADR-076 (will be updated in Phase 4.5 with final decision)

---

### STRAT-007: Additional Model Types (Phase 6-7, 🟡 High Priority)

**Task ID:** STRAT-007
**Priority:** 🟡 High
**Estimated Effort:** 30-40 hours
**Target Phase:** 6-7 (Advanced Models, September-November 2026)
**Dependencies:** Phase 4 ensemble framework stable, Phase 5 data pipeline collecting features
**Related Requirements:** REQ-MODEL-005 (Additional Model Types)

#### Problem
Current models (Phase 4) use **traditional approaches**:
- **Elo ratings:** Simple, fast, but assumes constant skill
- **Logistic regression:** Linear, interpretable, but limited expressiveness
- **XGBoost:** Powerful, but requires feature engineering

**Modern ML approaches** (neural networks, transformers) may capture more complex patterns:
- Non-linear interactions (e.g., team performance depends on rest days × travel distance)
- Temporal dependencies (e.g., momentum effects, recency weighting)
- Multi-modal inputs (text data from injury reports, weather forecasts)

#### Research Objectives
1. **Identify candidate models** (neural networks, transformers, LSTMs, reinforcement learning)
2. **Feature engineering** (what inputs, how to encode)
3. **Benchmark performance** (compare to baseline models on same data)
4. **Integrate into ensemble** (add as 4th/5th model with weights)

#### Implementation Tasks
**Task 1: Model Research & Selection (6-8 hours)**
- Review recent papers (sports betting ML, prediction markets)
- Identify 2-3 promising model types
- **Candidates:**
  - **Neural networks:** Feedforward (simple), LSTMs (temporal), Transformers (attention)
  - **Ensemble methods:** CatBoost (categorical features), LightGBM (fast training)
  - **Probabilistic models:** Gaussian Processes (uncertainty quantification), Bayesian networks

**Task 2: Feature Engineering Pipeline (10-12 hours)**
- Extract features from database (team stats, player stats, historical outcomes)
- Encode categorical features (teams, venues, weather)
- Temporal features (rolling averages, momentum, recency weighting)
- Feature scaling (normalization, standardization)

**Example features:**
```python
# Team-level features
- elo_rating (current)
- elo_rating_7d_avg (momentum)
- home_win_pct_season
- avg_points_scored_L5 (last 5 games)
- avg_points_allowed_L5
- rest_days (days since last game)
- travel_distance (miles from home city)

# Situational features
- is_home (binary)
- is_primetime (binary)
- is_division_game (binary)
- temperature (continuous)
- precipitation (continuous)

# Opponent features
- opponent_elo_rating
- opponent_home_win_pct
- head_to_head_record_L3
```

**Task 3: Model Training & Validation (10-12 hours)**
- Implement 2-3 candidate models (PyTorch, scikit-learn, or TensorFlow)
- Walk-forward validation (train on historical, predict future)
- Hyperparameter tuning (grid search or Bayesian optimization)
- Compare to baseline models (Brier score, log loss, Sharpe ratio)

**Task 4: Ensemble Integration (4-6 hours)**
- Add new models to `probability_models.yaml`
- Update ensemble to include new models
- Determine optimal weights (equal, performance-weighted, or research from STRAT-006)
- Test ensemble predictions (validate output probabilities ∈ [0, 1])

**Task 5: Production Deployment (4-6 hours)**
- Serialize trained models (pickle, joblib, or ONNX)
- Add model loading to startup (lazy loading for performance)
- Monitor prediction latency (target: <100ms per market)
- Add model versioning (v1.0, v1.1, etc.)

#### Deliverable
- **Code:** `analytics/models/neural_network.py` (or lstm.py, transformer.py)
- **Code:** `analytics/feature_engineering.py` (feature extraction pipeline)
- **Config:** Updated `probability_models.yaml` (add new models to ensemble)
- **Models:** Serialized model files (e.g., `models/neural_net_v1.0.pkl`)
- **Document:** `MODEL_DEVELOPMENT_GUIDE_V1.0.md` (~400 lines)
  - Feature engineering rationale
  - Model architecture and hyperparameters
  - Validation results (Brier score, log loss, Sharpe ratio)
  - Deployment instructions
- **Tests:** Unit tests for feature engineering and model predictions

#### Success Criteria
- [ ] 2-3 new model types implemented and trained
- [ ] Walk-forward validation shows improvement over baseline (Brier score ≥5% better)
- [ ] Ensemble integrated with new models (predictions working)
- [ ] Prediction latency <100ms per market (acceptable for live trading)
- [ ] Model versioning working (can A/B test v1.0 vs v1.1)
- [ ] Documentation complete with validation results

---

### STRAT-008: Feature Engineering Pipeline Automation (Phase 3-4, 🟢 Medium Priority)

**Task ID:** STRAT-008
**Priority:** 🟢 Medium
**Estimated Effort:** 12-15 hours
**Target Phase:** 3-4 (Data Pipeline, February-April 2026)
**Dependencies:** Phase 2 live data integration complete, Phase 3 historical data collected
**Related Requirements:** REQ-DATA-003 (Feature Engineering)

#### Problem
Current data pipeline (Phase 2-3) ingests **raw data** (game scores, market prices, player stats). Models (Phase 4) require **engineered features** (rolling averages, momentum metrics, Elo deltas).

**Without automation:**
- Manual feature calculations (slow, error-prone)
- Feature drift (calculation logic changes over time)
- Hard to backtest (recreating historical features is tedious)

#### Research Objectives
1. **Define feature catalog** (list all features needed for models)
2. **Design pipeline** (raw data → engineered features → database storage)
3. **Automate calculation** (trigger on new data ingestion)
4. **Version features** (track calculation logic changes)

#### Implementation Tasks
**Task 1: Feature Catalog Definition (3-4 hours)**
- List all features used by models (Elo ratings, rolling averages, etc.)
- Document calculation logic (formulas, window sizes, aggregation methods)
- Identify dependencies (which features depend on others)

**Example catalog:**
```yaml
# Feature catalog (excerpt)
features:
  team_elo_rating:
    type: scalar
    calculation: "Elo rating formula (K=20)"
    update_trigger: after_game
    dependencies: []

  team_elo_7d_avg:
    type: scalar
    calculation: "Mean of elo_rating over last 7 days"
    update_trigger: daily
    dependencies: [team_elo_rating]

  home_win_pct_season:
    type: scalar
    calculation: "Home wins / Home games this season"
    update_trigger: after_game
    dependencies: []
```

**Task 2: Pipeline Design (3-4 hours)**
- Design data flow: raw data → feature calculation → database storage
- Choose trigger mechanism (event-driven, scheduled, or on-demand)
- Design feature versioning (track calculation logic changes)

**Example pipeline:**
```
[New game result] → Trigger feature recalculation
    ↓
[Calculate team features] (Elo update, rolling averages)
    ↓
[Calculate situational features] (rest days, travel distance)
    ↓
[Store features in database] (game_features table)
    ↓
[Models fetch features] (when predicting future games)
```

**Task 3: Feature Calculation Implementation (4-5 hours)**
- Implement feature calculation functions (`analytics/features/`)
- Vectorize calculations (use NumPy/Pandas for speed)
- Add unit tests (verify calculations match expected values)

**Example feature function:**
```python
import pandas as pd
from decimal import Decimal

def calculate_elo_7d_avg(team_id: int, current_date: date) -> Decimal:
    """Calculate 7-day moving average of team Elo rating."""
    # Fetch elo ratings for last 7 days
    df = pd.read_sql(
        "SELECT elo_rating FROM game_features "
        "WHERE team_id = %s AND game_date >= %s AND game_date <= %s",
        conn,
        params=(team_id, current_date - timedelta(days=7), current_date)
    )

    # Calculate mean
    return Decimal(str(df['elo_rating'].mean()))
```

**Task 4: Automation & Triggers (2-3 hours)**
- Add feature calculation to data ingestion pipeline
- Trigger after new game results ingested
- Log feature calculation (structured logging)
- Monitor calculation latency (target: <10s per game)

**Task 5: Feature Versioning (2-3 hours)**
- Add `feature_version` field to features table
- Track calculation logic changes (version bumps when formula changes)
- Support backfilling (recalculate historical features with new logic)

#### Deliverable
- **Code:** `analytics/features/` (feature calculation functions)
- **Code:** `analytics/feature_pipeline.py` (orchestration and triggers)
- **Database:** `game_features` table (stores calculated features)
- **Config:** `feature_catalog.yaml` (feature definitions and versioning)
- **Document:** `FEATURE_ENGINEERING_GUIDE_V1.0.md` (~250 lines)
  - Feature catalog and calculation logic
  - Pipeline architecture
  - Versioning strategy
- **Tests:** Unit tests for feature calculations

#### Success Criteria
- [ ] Feature catalog documented (20+ features)
- [ ] Pipeline automated (triggers on new data ingestion)
- [ ] Feature calculations vectorized (batch processing)
- [ ] Calculation latency <10s per game
- [ ] Feature versioning working (can backfill with new logic)
- [ ] Unit tests cover all feature calculations

---

### STRAT-009: Walk-Forward Validation Framework (Phase 4-5, 🟡 High Priority)

**Task ID:** STRAT-009
**Priority:** 🟡 High
**Estimated Effort:** 15-20 hours
**Target Phase:** 4-5 (Model Validation, May-July 2026)
**Dependencies:** Phase 3 historical data complete (2+ years), Phase 4 models trained
**Related Requirements:** REQ-TEST-007 (Walk-Forward Validation)

#### Problem
Current model validation (Phase 4) uses **simple train/test split**:
- Train on 2020-2022 data
- Test on 2023 data
- **Problem:** Single test period doesn't capture performance over time

**Walk-forward validation** simulates real trading:
- Train on expanding window (2020-2021)
- Test on next period (2022 Q1)
- Retrain with new data (2020-2022 Q1)
- Test on next period (2022 Q2)
- Repeat over entire historical data

**Why it matters:**
- Detects model degradation (performance decays over time)
- Validates retraining frequency (weekly, monthly, quarterly)
- Prevents overfitting (multiple test periods reduce luck)

#### Research Objectives
1. **Design validation framework** (window sizes, retraining frequency)
2. **Implement walk-forward loop** (train → test → retrain → test)
3. **Collect performance metrics** (Brier score, log loss, Sharpe ratio over time)
4. **Visualize degradation** (plot performance vs time)

#### Implementation Tasks
**Task 1: Framework Design (3-4 hours)**
- Choose window sizes:
  - Training window: 12 months (balance recency and data volume)
  - Test window: 1 month (simulate monthly retraining)
- Define metrics to track: Brier score, log loss, Sharpe ratio, calibration
- Design storage (save metrics per test period to database)

**Example walk-forward schedule:**
```
Period 1: Train 2020-01 to 2020-12 → Test 2021-01
Period 2: Train 2020-01 to 2021-01 → Test 2021-02
Period 3: Train 2020-01 to 2021-02 → Test 2021-03
...
Period 36: Train 2020-01 to 2023-12 → Test 2024-01
```

**Task 2: Validation Loop Implementation (6-8 hours)**
- Implement walk-forward loop (iterate over time periods)
- Train model on expanding window
- Predict on test period
- Calculate metrics (Brier score, log loss, Sharpe)
- Store results to database

**Example code:**
```python
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

def walk_forward_validate(model, data, train_months=12, test_months=1):
    """Run walk-forward validation."""
    results = []

    # Get min/max dates
    start_date = data['date'].min()
    end_date = data['date'].max()

    # Iterate over test periods
    current_date = start_date + pd.DateOffset(months=train_months)
    while current_date < end_date:
        # Define train/test windows
        train_end = current_date
        train_start = current_date - pd.DateOffset(months=train_months)
        test_start = current_date
        test_end = current_date + pd.DateOffset(months=test_months)

        # Split data
        train = data[(data['date'] >= train_start) & (data['date'] < train_end)]
        test = data[(data['date'] >= test_start) & (data['date'] < test_end)]

        # Train model
        model.fit(train[features], train['outcome'])

        # Predict
        predictions = model.predict_proba(test[features])[:, 1]

        # Calculate metrics
        brier = brier_score_loss(test['outcome'], predictions)
        logloss = log_loss(test['outcome'], predictions)

        # Store results
        results.append({
            'test_period': test_start,
            'brier_score': brier,
            'log_loss': logloss,
            'num_predictions': len(test)
        })

        # Move to next period
        current_date += pd.DateOffset(months=test_months)

    return pd.DataFrame(results)
```

**Task 3: Performance Metrics Collection (3-4 hours)**
- Implement Brier score, log loss, Sharpe ratio calculations
- Add calibration curve analysis (predicted prob vs actual outcome)
- Store metrics to database (`validation_results` table)

**Task 4: Visualization & Reporting (3-4 hours)**
- Plot performance over time (Brier score vs test period)
- Identify degradation trends (linear regression on performance)
- Compare models (Elo vs regression vs ML)
- Generate validation report (summary statistics, plots)

**Example plots:**
- Brier score over time (line chart)
- Calibration curve (scatter plot: predicted vs actual)
- Model comparison (bar chart: average Brier score per model)

**Task 5: Integration & Automation (2-3 hours)**
- Add walk-forward validation to model training pipeline
- Automate validation when new historical data added
- Alert if performance degrades >10% (trigger model retraining)

#### Deliverable
- **Code:** `analytics/validation/walk_forward.py` (validation framework)
- **Code:** `analytics/visualization/validation_plots.py` (performance visualization)
- **Database:** `validation_results` table (stores metrics per test period)
- **Document:** `WALK_FORWARD_VALIDATION_GUIDE_V1.0.md` (~300 lines)
  - Framework design and rationale
  - Metrics definitions
  - Interpretation guidelines (when to retrain)
- **Report:** Initial validation report (comparison of current models)

#### Success Criteria
- [ ] Walk-forward framework implemented (train → test → retrain loop)
- [ ] 36+ test periods validated (3 years monthly retraining simulation)
- [ ] Metrics collected for all models (Brier, log loss, Sharpe, calibration)
- [ ] Performance visualizations generated (plots over time)
- [ ] Degradation trends identified (know when to retrain)
- [ ] Validation automated (runs when new data added)

---

### STRAT-010: Model Drift Detection & Alerting (Phase 6-7, 🟢 Medium Priority)

**Task ID:** STRAT-010
**Priority:** 🟢 Medium
**Estimated Effort:** 10-12 hours
**Target Phase:** 6-7 (Production Monitoring, September-November 2026)
**Dependencies:** Phase 5 walk-forward validation framework complete, Phase 5 models in production
**Related Requirements:** REQ-OBSERV-003 (Model Drift Detection)

#### Problem
Models degrade over time (concept drift, data distribution shift). Without detection:
- Trading with stale models (poor performance)
- Silent degradation (no alert until losing money)
- Unclear when to retrain (reactive instead of proactive)

#### Research Objectives
1. **Define drift metrics** (what signals model degradation)
2. **Set alert thresholds** (when to trigger retraining)
3. **Implement monitoring** (track metrics in production)
4. **Automate alerting** (email/Slack when drift detected)

#### Implementation Tasks
**Task 1: Drift Metrics Definition (2-3 hours)**
- Choose drift detection methods:
  - **Performance drift:** Brier score increases >10% vs validation baseline
  - **Distribution drift:** Input feature distributions shift (KL divergence, PSI)
  - **Calibration drift:** Predicted probabilities poorly calibrated (ECE increases)
- Set alert thresholds (when to trigger retraining)

**Task 2: Monitoring Implementation (4-5 hours)**
- Track Brier score on recent predictions (rolling 7-day window)
- Compare to validation baseline (from walk-forward validation)
- Track feature distributions (daily snapshots)
- Calculate drift metrics (KL divergence, PSI, ECE)

**Example drift detection:**
```python
def detect_performance_drift(recent_brier: Decimal, baseline_brier: Decimal, threshold: Decimal = Decimal("0.10")) -> bool:
    """Detect if Brier score increased >10% vs baseline."""
    drift = (recent_brier - baseline_brier) / baseline_brier
    return drift > threshold

# Example usage
recent_brier = calculate_brier_last_7_days()  # 0.220
baseline_brier = get_validation_baseline()     # 0.200
if detect_performance_drift(recent_brier, baseline_brier):
    send_alert("Model performance degraded 10%! Retrain recommended.")
```

**Task 3: Alerting Configuration (2-3 hours)**
- Configure email/Slack alerts (use Grafana alerts or custom script)
- Define alert messages (include metrics, severity, recommended action)
- Test alert delivery

**Task 4: Automated Retraining Trigger (2-3 hours)**
- Optional: Trigger automated retraining when drift detected
- Retrain model on latest data (last 12 months)
- Validate new model (walk-forward on last 3 months)
- Deploy if performance improves (else keep current model)

#### Deliverable
- **Code:** `analytics/monitoring/drift_detection.py` (drift metrics calculation)
- **Code:** `analytics/monitoring/alerts.py` (alert configuration)
- **Config:** Alert thresholds (in `probability_models.yaml`)
- **Document:** `MODEL_DRIFT_MONITORING_GUIDE_V1.0.md` (~200 lines)
  - Drift metrics definitions
  - Alert thresholds and rationale
  - Retraining workflow
- **Dashboard:** Grafana panel for model drift metrics

#### Success Criteria
- [ ] Drift metrics implemented (performance, distribution, calibration)
- [ ] Monitoring working (tracks metrics daily)
- [ ] Alerts configured (email/Slack when drift detected)
- [ ] Tested with simulated drift (artificial data distribution shift)
- [ ] Dashboard panel shows drift metrics
- [ ] Documentation complete with troubleshooting

---

### STRAT-011: Advanced Edge Detection (Phase 6-7, 🟡 High Priority)

**Task ID:** STRAT-011
**Priority:** 🟡 High
**Estimated Effort:** 12-15 hours
**Target Phase:** 6-7 (Advanced Trading, September-November 2026)
**Dependencies:** Phase 4 basic edge detection working, Phase 5 data pipeline collecting microstructure data
**Related Requirements:** REQ-EDGE-003 (Advanced Edge Detection)
**Research Enhancement:** DEF-017, DEF-018, DEF-019 (Phase 4.5 research will enhance but not block)

#### Problem
Current edge detection (Phase 4) uses **simplified assumptions**:
- **Fixed fees:** 7% taker fee (ignores fee tiers, maker rebates)
- **Point estimates:** Single edge value (no confidence intervals)
- **Independence:** Treats markets as independent (ignores correlations)

**Advanced edge detection** addresses these limitations:
- **Dynamic fees:** Account for maker rebates, fee tiers, slippage
- **Confidence intervals:** Quantify edge uncertainty (95% CI)
- **Correlation analysis:** Identify arbitrage opportunities (correlated markets)

**Note:** Phase 4.5 research (DEF-017, DEF-018, DEF-019) will enhance this task but is **not blocking**. Implementation can proceed with current knowledge, then be refined after research.

#### Research Objectives
1. **Fee impact modeling** (quantify how fees affect edge)
2. **Confidence interval methods** (bootstrap, Bayesian, or analytical)
3. **Correlation analysis** (identify pairs/groups of correlated markets)
4. **Arbitrage detection** (find risk-free profit opportunities)

#### Implementation Tasks
**Task 1: Dynamic Fee Modeling (3-4 hours)**
- Model fee tiers (volume-based rebates on Kalshi)
- Account for maker rebates (paid when providing liquidity)
- Include slippage estimates (from historical order book data)

**Example fee calculation:**
```python
def calculate_effective_fee(
    order_type: str,       # "market" or "limit"
    volume_30d: Decimal,   # 30-day trading volume
    spread: Decimal        # Current bid-ask spread
) -> Decimal:
    """Calculate effective fee including rebates and slippage."""

    # Base fees (Kalshi example)
    if order_type == "market":
        fee = Decimal("0.07")  # 7% taker fee
    else:  # limit order (maker)
        fee = Decimal("0.00")  # Maker rebate (paid to you)

    # Volume-based fee tiers (hypothetical)
    if volume_30d > Decimal("10000"):
        fee *= Decimal("0.80")  # 20% discount
    elif volume_30d > Decimal("5000"):
        fee *= Decimal("0.90")  # 10% discount

    # Slippage (for market orders, half the spread)
    if order_type == "market":
        slippage = spread / Decimal("2")
    else:
        slippage = Decimal("0")

    return fee + slippage
```

**Task 2: Confidence Interval Implementation (3-4 hours)**
- Choose method: Bootstrap (resampling), Bayesian (credible intervals), or analytical (normal approximation)
- **Recommendation:** Bootstrap (model-free, handles non-normal distributions)
- Calculate 95% CI for edge estimates
- Use CI to filter trades (only trade if lower bound > 0)

**Example bootstrap CI:**
```python
import numpy as np
from decimal import Decimal

def calculate_edge_confidence_interval(
    true_prob: Decimal,
    market_prob: Decimal,
    n_bootstrap: int = 1000,
    confidence: float = 0.95
) -> tuple[Decimal, Decimal, Decimal]:
    """Calculate edge with 95% confidence interval via bootstrap."""

    # Simulate outcomes (1000 bootstrap samples)
    edges = []
    for _ in range(n_bootstrap):
        # Resample outcomes (simulate prediction uncertainty)
        sampled_prob = np.random.beta(
            float(true_prob) * 100,      # Alpha (prior successes)
            (1 - float(true_prob)) * 100  # Beta (prior failures)
        )

        # Calculate edge for this sample
        edge = Decimal(str(sampled_prob)) - market_prob
        edges.append(edge)

    # Calculate percentiles (95% CI)
    lower = Decimal(str(np.percentile(edges, 2.5)))
    median = Decimal(str(np.percentile(edges, 50)))
    upper = Decimal(str(np.percentile(edges, 97.5)))

    return lower, median, upper

# Example usage
lower, median, upper = calculate_edge_confidence_interval(
    true_prob=Decimal("0.65"),
    market_prob=Decimal("0.60")
)
print(f"Edge: {median:.4f} (95% CI: [{lower:.4f}, {upper:.4f}])")
# Output: Edge: 0.0500 (95% CI: [0.0320, 0.0680])
```

**Task 3: Correlation Analysis (3-4 hours)**
- Calculate correlation matrix (historical market price movements)
- Identify highly correlated markets (correlation >0.7)
- Use for portfolio construction (avoid over-concentration in correlated markets)

**Task 4: Arbitrage Detection (3-4 hours)**
- Detect arbitrage opportunities:
  - **Single-market:** YES price + NO price < 1.00 (guaranteed profit)
  - **Cross-market:** Correlated markets with pricing discrepancies
- Calculate risk-free profit (after fees and slippage)
- Prioritize arbitrage over directional trades (risk-free > risky)

**Example arbitrage detection:**
```python
def detect_single_market_arbitrage(yes_ask: Decimal, no_ask: Decimal) -> Decimal:
    """Detect arbitrage: buy YES + NO for less than $1.00."""
    total_cost = yes_ask + no_ask
    if total_cost < Decimal("1.00"):
        # Guaranteed profit (one outcome must occur)
        profit = Decimal("1.00") - total_cost
        return profit
    return Decimal("0")

# Example
yes_ask = Decimal("0.48")
no_ask = Decimal("0.51")
profit = detect_single_market_arbitrage(yes_ask, no_ask)
if profit > 0:
    print(f"Arbitrage detected! Risk-free profit: ${profit:.4f}")
# Output: Arbitrage detected! Risk-free profit: $0.0100
```

#### Deliverable
- **Code:** `analytics/edge_detection/advanced_edge.py` (dynamic fees, CI, correlation, arbitrage)
- **Updated:** `analytics/edge_detection/detect_edges.py` (integrate advanced methods)
- **Document:** `ADVANCED_EDGE_DETECTION_GUIDE_V1.0.md` (~300 lines)
  - Dynamic fee modeling
  - Confidence interval methodology
  - Correlation analysis and portfolio construction
  - Arbitrage detection algorithms
- **Tests:** Unit tests for fee calculations, CI, arbitrage detection
- **Dashboard:** Grafana panel showing edge distributions and arbitrage opportunities

#### Success Criteria
- [ ] Dynamic fee modeling implemented (accounts for maker rebates, fee tiers, slippage)
- [ ] Confidence intervals calculated for all edges (95% CI)
- [ ] Correlation matrix updated daily (tracks market relationships)
- [ ] Arbitrage detection working (identifies risk-free opportunities)
- [ ] Backtests show CI filtering improves Sharpe ratio (only trade when lower bound > 0)
- [ ] Documentation complete with examples

---

## Category 3: Strategy & Position Management (7 tasks)

### STRAT-012: Strategy vs Method Separation (Phase 4-5, 🔴 Critical Priority) ⚠️ PENDING ADR-077

**Task ID:** STRAT-012
**Priority:** 🔴 Critical (**HIGHEST PRIORITY RESEARCH**)
**Estimated Effort:** 20-25 hours
**Target Phase:** 4-5 (May-July 2026) **AFTER Phase 4.5 research complete**
**Dependencies:** ⚠️ **PENDING ADR-077** (Strategy vs Method Separation Research)
**Related Requirements:** REQ-STRAT-006 (Strategy Architecture)

#### ⚠️ BLOCKED UNTIL RESEARCH COMPLETE

**This task CANNOT be implemented until ADR-077 research is complete** (Phase 4.5, April-May 2026).

**This is the HIGHEST PRIORITY research task.** Strategies research is **MOST IMPORTANT** (more important than models or edge detection).

**Research tasks that must complete first:**
- DEF-013: Strategy Config Taxonomy (8-10h, 🔴 Critical)
- DEF-014: A/B Testing Workflows Validation (10-12h, 🔴 Critical)
- DEF-015: User Customization Patterns Research (6-8h, 🟡 High)
- DEF-016: Version Combinatorics Modeling (4-6h, 🟡 High)

**See:** `PHASE_4_DEFERRED_TASKS_V1.0.md` Section 1 for detailed research task descriptions.

**After research complete (May 2026):**
- ADR-077 will be updated with **final decision** (Option A, B, or C)
- This task will be **unblocked** and implementation can begin

#### Problem (High-Level)
Current architecture separates **strategies** (entry/exit logic) from **methods** (complete trading system bundles), but **boundaries are ambiguous**.

**Example ambiguity:**
```yaml
# From trade_strategies.yaml
hedge_strategy:
  entry_logic: halftime_or_inplay       # Clearly "strategy"
  exit_conditions: [stop_loss, profit_target]  # Clearly "strategy"
  hedge_sizing_method: partial_lock     # Is this "strategy" or "position management"?
  partial_lock:
    profit_lock_percentage: "0.70"      # Is this "strategy parameter" or "position management parameter"?
```

**If boundaries are wrong:**
- Users can't customize strategies effectively (unclear what to change)
- A/B testing workflows break (can't isolate performance to specific changes)
- Version combinatorics explode (strategy × model × position × risk × execution)

#### Potential Solutions (Research Will Decide)
**Option A:** Merge strategy + position management into single config (simplify versioning)
**Option B:** Keep separate, document clear boundaries via taxonomy (current approach)
**Option C:** Introduce "method bundles" as top-level construct (bundle strategy + position + risk)

#### Implementation Tasks (Conditional on ADR-077 Decision)
**If Option A chosen (Merge Configs):**
- Merge `trade_strategies.yaml` + `position_management.yaml` → `trading_methods.yaml`
- Update database schema (remove strategies table, add methods table)
- Migrate existing strategies to methods

**If Option B chosen (Keep Separate with Taxonomy):**
- Document clear boundaries (decision tree: "Where does this parameter belong?")
- Reorganize configs based on taxonomy (move ambiguous parameters)
- Update versioning guide with examples

**If Option C chosen (Method Bundles):**
- Create `methods` table (links strategy_id + position_config_id + risk_config_id)
- Implement method versioning (method_v1.0 bundles specific versions of each component)
- Update trade attribution (attribute to method, not individual components)

#### Deliverable (TBD based on ADR-077 decision)
- **Code:** Implementation varies based on Option A/B/C
- **Migration:** Database schema changes (if Option A or C)
- **Config:** Updated YAML configs (reorganized based on taxonomy)
- **Document:** Updated `VERSIONING_GUIDE_V1.1.md` (strategy/method versioning)
- **Document:** `STRATEGY_CONFIG_TAXONOMY_V1.0.md` (clear boundaries documented)
- **Tests:** Unit tests for new architecture

#### Success Criteria (TBD based on ADR-077 decision)
- Criteria depend on which option is chosen
- See ADR-077 (will be updated in Phase 4.5 with final decision)

---

### STRAT-013: Advanced Entry Strategies (Phase 7-8, 🟡 High Priority)

**Task ID:** STRAT-013
**Priority:** 🟡 High
**Estimated Effort:** 15-20 hours
**Target Phase:** 7-8 (Advanced Strategies, November 2026-January 2027)
**Dependencies:** Phase 5 basic entry strategies working, Phase 6 advanced edge detection complete
**Related Requirements:** REQ-STRAT-007 (Advanced Entry Strategies)

#### Problem
Current entry strategies (Phase 1-4) use **simple timing**:
- **Pregame:** Enter before game starts
- **Halftime:** Enter at halftime
- **In-play:** Enter during game (manual triggers)

**Advanced strategies** use more sophisticated timing:
- **Market making:** Provide liquidity (place limit orders on both sides)
- **Contrarian:** Fade public sentiment (bet against crowd)
- **Momentum:** Follow price movements (chase strong trends)
- **Mean reversion:** Bet against extreme prices (regression to mean)

#### Research Objectives
1. **Identify profitable entry patterns** (from Phase 1-5 historical data)
2. **Backtest advanced strategies** (compare to baseline pregame/halftime)
3. **Implement top 2-3 strategies** (highest Sharpe ratio)
4. **Monitor live performance** (validate backtest results)

#### Implementation Tasks
**Task 1: Strategy Research (4-5 hours)**
- Analyze historical trades (identify patterns in profitable entries)
- Review academic literature (sports betting market microstructure)
- Shortlist 3-5 candidate strategies

**Candidate strategies:**
- **Market making:** Place limit orders at mid-price ± spread/2 (earn bid-ask spread)
- **Contrarian:** Bet against large price moves (fade sentiment)
- **Momentum:** Follow 15-min price trends (chase momentum)
- **Value betting:** Wait for prices to reach extreme values (0.05 or 0.95)

**Task 2: Backtesting (6-8 hours)**
- Implement candidate strategies (Python simulation)
- Backtest on historical data (2 years, 1000+ games)
- Compare Sharpe ratios (vs baseline pregame/halftime)
- Select top 2-3 strategies (highest risk-adjusted returns)

**Example backtest pseudocode:**
```python
# Market making strategy backtest
for game in historical_games:
    for minute in range(0, 240, 15):  # Every 15 minutes
        current_price = get_market_price(game, minute)
        spread = get_bid_ask_spread(game, minute)

        # Place limit orders at mid-price ± spread/2
        buy_limit = current_price - spread / 2
        sell_limit = current_price + spread / 2

        # Simulate fills (assume 50% fill rate for limit orders)
        if random() < 0.5:
            execute_trade(game, minute, "buy", buy_limit)
        if random() < 0.5:
            execute_trade(game, minute, "sell", sell_limit)

    # Calculate P&L at game end
    final_outcome = game.winner
    pnl = calculate_pnl(trades, final_outcome)
    record_results(game, "market_making", pnl)

# Calculate Sharpe ratio
sharpe = calculate_sharpe(pnl_history)
```

**Task 3: Implementation (4-5 hours)**
- Implement top 2-3 strategies in production code
- Add to `trade_strategies.yaml`
- Create strategy versions (e.g., market_making_v1.0)

**Task 4: Live Testing (2-3 hours)**
- Deploy strategies in demo environment (paper trading)
- Monitor performance for 2-4 weeks
- Compare to backtest results (validate assumptions)

#### Deliverable
- **Code:** `trading/strategies/market_making.py` (and other advanced strategies)
- **Config:** Updated `trade_strategies.yaml` (add advanced strategies)
- **Document:** `ADVANCED_ENTRY_STRATEGIES_GUIDE_V1.0.md` (~300 lines)
  - Strategy descriptions and rationale
  - Backtest results (Sharpe ratios, drawdowns)
  - Live performance monitoring
- **Report:** Backtest comparison (advanced vs baseline strategies)

#### Success Criteria
- [ ] 3-5 candidate strategies identified
- [ ] Backtests complete (2 years historical data)
- [ ] Top 2-3 strategies selected (Sharpe ratio ≥ baseline)
- [ ] Strategies implemented in production code
- [ ] Live testing complete (2-4 weeks paper trading)
- [ ] Live performance matches backtest (within ±20%)

---

### STRAT-014: Exit Optimization (Phase 6-7, 🟡 High Priority)

**Task ID:** STRAT-014
**Priority:** 🟡 High
**Estimated Effort:** 15-20 hours
**Target Phase:** 6-7 (Exit Optimization, September-November 2026)
**Dependencies:** Phase 5 basic exits working (10-condition priority hierarchy), Phase 5 trailing stops implemented
**Related Requirements:** REQ-EXIT-004 (Exit Optimization)

#### Problem
Current exit logic (Phase 5) uses **fixed rules**:
- Stop loss: -20% loss
- Profit target: +30% gain
- Trailing stop: 50% retracement from peak

**Exit optimization** tunes these parameters for maximum profit:
- **Adaptive stops:** Dynamic stop loss based on volatility
- **Partial exits:** Take partial profits at multiple targets
- **Time-based exits:** Exit before game end to reduce risk
- **Probability-based exits:** Exit when edge disappears

#### Research Objectives
1. **Identify optimal exit parameters** (backtest different stop/target combinations)
2. **Test adaptive methods** (volatility-based stops, dynamic targets)
3. **Implement partial exit logic** (take 50% profit at first target, 50% at second)
4. **Monitor live performance** (validate optimization results)

#### Implementation Tasks
**Task 1: Parameter Grid Search (6-8 hours)**
- Define parameter grid:
  - Stop loss: [-10%, -15%, -20%, -25%, -30%]
  - Profit target: [+15%, +20%, +25%, +30%, +40%]
  - Trailing stop: [30%, 40%, 50%, 60%, 70%]
- Backtest all combinations (5 × 5 × 5 = 125 backtests)
- Identify optimal parameters (highest Sharpe ratio)

**Example grid search pseudocode:**
```python
best_sharpe = -999
best_params = {}

for stop_loss in [-0.10, -0.15, -0.20, -0.25, -0.30]:
    for profit_target in [0.15, 0.20, 0.25, 0.30, 0.40]:
        for trailing_pct in [0.30, 0.40, 0.50, 0.60, 0.70]:
            # Run backtest with these parameters
            sharpe = backtest(stop_loss, profit_target, trailing_pct)

            # Track best parameters
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = {
                    'stop_loss': stop_loss,
                    'profit_target': profit_target,
                    'trailing_pct': trailing_pct
                }

print(f"Optimal parameters: {best_params} (Sharpe: {best_sharpe:.2f})")
```

**Task 2: Adaptive Exit Methods (4-5 hours)**
- Implement volatility-based stops (wider stops for volatile games)
- Implement probability-based exits (exit when edge < 1%)
- Implement time-based exits (exit 10 minutes before game end)

**Example adaptive stop:**
```python
def calculate_adaptive_stop_loss(
    entry_price: Decimal,
    historical_volatility: Decimal,
    base_stop_pct: Decimal = Decimal("0.20")
) -> Decimal:
    """Calculate stop loss adjusted for volatility."""
    # Wider stops for high-volatility games
    volatility_multiplier = Decimal("1.0") + historical_volatility
    adaptive_stop_pct = base_stop_pct * volatility_multiplier

    # Cap at -40% (max risk)
    adaptive_stop_pct = min(adaptive_stop_pct, Decimal("0.40"))

    stop_price = entry_price * (Decimal("1.0") - adaptive_stop_pct)
    return stop_price
```

**Task 3: Partial Exit Implementation (3-4 hours)**
- Add partial exit logic (close 50% at first target, 50% at second)
- Track position splits (original quantity vs remaining quantity)
- Update P&L calculations (realized + unrealized)

**Task 4: Live Testing & Validation (2-3 hours)**
- Deploy optimized exits in demo environment
- Monitor for 2-4 weeks
- Compare to baseline (fixed rules)

#### Deliverable
- **Code:** `trading/exits/adaptive_exits.py` (volatility-based stops, probability exits)
- **Code:** `trading/exits/partial_exits.py` (partial exit logic)
- **Updated:** `position_management.yaml` (optimal parameters from grid search)
- **Document:** `EXIT_OPTIMIZATION_GUIDE_V1.0.md` (~250 lines)
  - Grid search results
  - Adaptive methods and rationale
  - Partial exit workflows
- **Report:** Optimization results (Sharpe improvement vs baseline)

#### Success Criteria
- [ ] Grid search complete (125 parameter combinations)
- [ ] Optimal parameters identified (Sharpe ≥ baseline)
- [ ] Adaptive methods implemented (volatility stops, probability exits, time exits)
- [ ] Partial exit logic working (50/50 splits at multiple targets)
- [ ] Live testing validates optimization (Sharpe improvement ≥10%)
- [ ] Documentation complete with backtest results

---

### STRAT-015: Position Correlation Analysis & Limits (Phase 6-7, 🟢 Medium Priority)

**Task ID:** STRAT-015
**Priority:** 🟢 Medium
**Estimated Effort:** 10-12 hours
**Target Phase:** 6-7 (Risk Management, September-November 2026)
**Dependencies:** Phase 5 position monitoring working, Phase 6 correlation analysis (STRAT-011) complete
**Related Requirements:** REQ-RISK-004 (Correlation Limits)

#### Problem
Current position management (Phase 5) treats positions as **independent**. Correlated positions amplify risk:
- **Same game:** YES on Team A + NO on Team B (perfectly correlated)
- **Same division:** Multiple bets on NFC East teams (highly correlated)
- **Same sport:** 10 NFL bets (moderately correlated)

**Without correlation limits:**
- Over-concentration in correlated markets (all eggs in one basket)
- Amplified losses during adverse events (entire portfolio moves together)
- Violated diversification (effective exposure >> nominal exposure)

#### Research Objectives
1. **Calculate position correlations** (use market correlation data from STRAT-011)
2. **Define correlation limits** (max correlated exposure per category)
3. **Implement pre-trade checks** (reject trades that violate limits)
4. **Monitor portfolio correlation** (daily dashboard)

#### Implementation Tasks
**Task 1: Correlation Calculation (3-4 hours)**
- Fetch market correlation matrix (from STRAT-011)
- Calculate portfolio correlation (position-weighted average)
- Identify correlated clusters (groups of highly correlated markets)

**Example correlation calculation:**
```python
import pandas as pd
import numpy as np
from decimal import Decimal

def calculate_portfolio_correlation(positions, correlation_matrix):
    """Calculate effective portfolio correlation."""
    # Extract tickers and exposures
    tickers = [p['ticker'] for p in positions]
    exposures = [p['quantity'] * p['entry_price'] for p in positions]

    # Build position weight vector
    total_exposure = sum(exposures)
    weights = [e / total_exposure for e in exposures]

    # Calculate portfolio variance
    portfolio_variance = 0
    for i, ticker_i in enumerate(tickers):
        for j, ticker_j in enumerate(tickers):
            corr = correlation_matrix[ticker_i][ticker_j]
            portfolio_variance += weights[i] * weights[j] * corr

    # Effective correlation = (portfolio_variance - sum(weights^2)) / (1 - sum(weights^2))
    # (measures how much correlation adds to risk beyond individual position risks)
    avg_weight_sq = sum([w**2 for w in weights])
    effective_corr = (portfolio_variance - avg_weight_sq) / (1 - avg_weight_sq)

    return Decimal(str(effective_corr))
```

**Task 2: Correlation Limits Configuration (2-3 hours)**
- Define limits in `position_management.yaml`:
  - Max correlated exposure (same game): 2 positions
  - Max correlated exposure (same division): $500
  - Max correlated exposure (same sport): 70% of total portfolio
- Add correlation limit enforcement to trade validation

**Task 3: Pre-Trade Checks (3-4 hours)**
- Implement correlation check in trade execution pipeline
- Reject trades that violate limits
- Log rejection reason (structured logging)

**Example pre-trade check:**
```python
def validate_correlation_limits(new_trade, existing_positions, config):
    """Check if new trade violates correlation limits."""
    # Check same-game correlation
    same_game_positions = [
        p for p in existing_positions
        if p['game_id'] == new_trade['game_id']
    ]
    if len(same_game_positions) >= config['max_positions_per_game']:
        return False, "Same-game correlation limit exceeded"

    # Check same-division correlation
    same_division_exposure = sum([
        p['exposure'] for p in existing_positions
        if p['division'] == new_trade['division']
    ])
    if same_division_exposure + new_trade['exposure'] > config['max_division_exposure']:
        return False, "Same-division exposure limit exceeded"

    # Check same-sport correlation
    same_sport_exposure = sum([
        p['exposure'] for p in existing_positions
        if p['sport'] == new_trade['sport']
    ])
    total_portfolio = sum([p['exposure'] for p in existing_positions])
    if (same_sport_exposure + new_trade['exposure']) / total_portfolio > config['max_sport_pct']:
        return False, "Same-sport exposure % limit exceeded"

    return True, "OK"
```

**Task 4: Monitoring Dashboard (2-3 hours)**
- Add Grafana panel for portfolio correlation
- Show correlation matrix heatmap
- Alert if effective correlation >0.7 (high correlation warning)

#### Deliverable
- **Code:** `trading/risk/correlation_limits.py` (correlation calculation and validation)
- **Updated:** `position_management.yaml` (correlation limits configuration)
- **Updated:** `trading/execution/trade_validator.py` (add correlation checks)
- **Document:** `CORRELATION_LIMITS_GUIDE_V1.0.md` (~200 lines)
  - Correlation calculation methodology
  - Limit definitions and rationale
  - Pre-trade check workflow
- **Dashboard:** Grafana correlation monitoring panel

#### Success Criteria
- [ ] Portfolio correlation calculated correctly
- [ ] Correlation limits configured (same-game, same-division, same-sport)
- [ ] Pre-trade checks enforced (rejects trades violating limits)
- [ ] Dashboard shows portfolio correlation (updated daily)
- [ ] Alert triggers when correlation >0.7
- [ ] Documentation complete with examples

---

### STRAT-016: Dynamic Position Sizing (Phase 7-8, 🟡 High Priority)

**Task ID:** STRAT-016
**Priority:** 🟡 High
**Estimated Effort:** 12-15 hours
**Target Phase:** 7-8 (Advanced Risk Management, November 2026-January 2027)
**Dependencies:** Phase 4 Kelly criterion working, Phase 6 confidence intervals (STRAT-011) complete
**Related Requirements:** REQ-RISK-005 (Dynamic Position Sizing)

#### Problem
Current position sizing (Phase 4) uses **fixed Kelly fraction**:
- 25% of full Kelly bet (conservative)
- Same fraction for all trades (ignores confidence)

**Dynamic sizing** adjusts bet size based on:
- **Confidence:** Larger bets when edge is certain (narrow CI)
- **Volatility:** Smaller bets for volatile markets
- **Correlation:** Smaller bets when portfolio is concentrated
- **Drawdown:** Reduce sizing after losses (capital preservation)

#### Research Objectives
1. **Define sizing multipliers** (confidence, volatility, correlation, drawdown)
2. **Backtest dynamic sizing** (compare to fixed 25% Kelly)
3. **Implement adaptive Kelly** (adjust fraction based on multipliers)
4. **Monitor live performance** (validate backtest results)

#### Implementation Tasks
**Task 1: Sizing Multiplier Design (3-4 hours)**
- Define 4 multipliers (confidence, volatility, correlation, drawdown)
- Set ranges (e.g., confidence multiplier ∈ [0.5, 1.5])
- Combine multipliers (product or weighted average)

**Example multipliers:**
```python
def calculate_confidence_multiplier(edge_ci_width: Decimal) -> Decimal:
    """Larger bets when confidence interval is narrow."""
    # Narrow CI (0.01) → 1.5x Kelly
    # Wide CI (0.10) → 0.5x Kelly
    if edge_ci_width < Decimal("0.02"):
        return Decimal("1.5")
    elif edge_ci_width < Decimal("0.05"):
        return Decimal("1.0")
    else:
        return Decimal("0.5")

def calculate_volatility_multiplier(market_volatility: Decimal) -> Decimal:
    """Smaller bets for volatile markets."""
    # Low volatility (0.05) → 1.2x Kelly
    # High volatility (0.20) → 0.6x Kelly
    if market_volatility < Decimal("0.10"):
        return Decimal("1.2")
    elif market_volatility < Decimal("0.15"):
        return Decimal("1.0")
    else:
        return Decimal("0.6")

def calculate_correlation_multiplier(portfolio_correlation: Decimal) -> Decimal:
    """Smaller bets when portfolio is concentrated."""
    # Low correlation (0.3) → 1.0x Kelly
    # High correlation (0.8) → 0.5x Kelly
    if portfolio_correlation < Decimal("0.5"):
        return Decimal("1.0")
    elif portfolio_correlation < Decimal("0.7"):
        return Decimal("0.8")
    else:
        return Decimal("0.5")

def calculate_drawdown_multiplier(current_drawdown: Decimal) -> Decimal:
    """Reduce sizing during drawdowns."""
    # No drawdown → 1.0x Kelly
    # 20% drawdown → 0.5x Kelly
    if current_drawdown < Decimal("0.10"):
        return Decimal("1.0")
    elif current_drawdown < Decimal("0.20"):
        return Decimal("0.75")
    else:
        return Decimal("0.5")

# Combine multipliers (product)
def calculate_dynamic_kelly_fraction(base_fraction, edge_ci_width, volatility, correlation, drawdown):
    conf_mult = calculate_confidence_multiplier(edge_ci_width)
    vol_mult = calculate_volatility_multiplier(volatility)
    corr_mult = calculate_correlation_multiplier(correlation)
    draw_mult = calculate_drawdown_multiplier(drawdown)

    # Product of multipliers
    dynamic_fraction = base_fraction * conf_mult * vol_mult * corr_mult * draw_mult

    # Cap at 50% of Kelly (max risk limit)
    dynamic_fraction = min(dynamic_fraction, Decimal("0.50"))

    return dynamic_fraction
```

**Task 2: Backtesting (4-5 hours)**
- Backtest dynamic sizing vs fixed 25% Kelly
- Compare Sharpe ratios, max drawdown, total return
- Validate multiplier ranges (tune if needed)

**Task 3: Implementation (3-4 hours)**
- Add multiplier calculations to position sizing logic
- Update `position_management.yaml` (dynamic sizing config)
- Test dynamic sizing (unit tests, integration tests)

**Task 4: Live Testing (2-3 hours)**
- Deploy in demo environment
- Monitor for 2-4 weeks
- Compare to baseline (fixed 25% Kelly)

#### Deliverable
- **Code:** `trading/position_sizing/dynamic_kelly.py` (multiplier calculations)
- **Updated:** `position_management.yaml` (dynamic sizing configuration)
- **Document:** `DYNAMIC_POSITION_SIZING_GUIDE_V1.0.md` (~250 lines)
  - Multiplier definitions and rationale
  - Backtest results (Sharpe improvement)
  - Live performance monitoring
- **Report:** Backtest comparison (dynamic vs fixed Kelly)

#### Success Criteria
- [ ] 4 multipliers defined (confidence, volatility, correlation, drawdown)
- [ ] Backtest complete (2 years historical data)
- [ ] Dynamic sizing improves Sharpe ratio ≥10% vs fixed Kelly
- [ ] Implementation complete (multipliers calculated per trade)
- [ ] Live testing validates backtest (Sharpe improvement confirmed)
- [ ] Documentation complete with multiplier tuning guide

---

### STRAT-017: Multi-Leg Strategies (Hedging & Arbitrage) (Phase 8-9, 🟡 High Priority) ⚠️ PENDING ADR-077

**Task ID:** STRAT-017
**Priority:** 🟡 High
**Estimated Effort:** 20-25 hours
**Target Phase:** 8-9 (Multi-Leg Strategies, January-April 2027)
**Dependencies:** ⚠️ **PENDING ADR-077** (Strategy vs Method Separation), Phase 7 advanced entry strategies working
**Related Requirements:** REQ-STRAT-008 (Multi-Leg Strategies)

#### ⚠️ PARTIALLY BLOCKED

**This task is PARTIALLY BLOCKED** until ADR-077 research complete (Phase 4.5).

**Why blocked:** Multi-leg strategies blur boundaries between strategy logic and position management. Need clear taxonomy before implementing.

**Can proceed with:** Basic arbitrage detection (from STRAT-011)
**Must wait for:** Complex hedging strategies (partial hedges, dynamic hedges)

#### Problem
Current strategies (Phase 1-7) are **single-leg** (one position per opportunity). Multi-leg strategies open **multiple positions simultaneously**:
- **Hedging:** Lock in profit by betting both sides
- **Arbitrage:** Risk-free profit from pricing discrepancies
- **Straddles:** Bet on volatility (not direction)

#### Research Objectives
1. **Identify multi-leg opportunities** (from historical data)
2. **Design hedging logic** (when to hedge, how much to hedge)
3. **Implement arbitrage detection** (from STRAT-011)
4. **Test multi-leg execution** (coordinate multiple orders)

#### Implementation Tasks
**Task 1: Arbitrage Implementation (4-5 hours)** ✅ CAN PROCEED NOW
- Use arbitrage detection from STRAT-011
- Implement simultaneous execution (buy YES + buy NO when total <$1)
- Test on demo API (verify both legs fill)

**Task 2: Hedging Logic Design (6-8 hours)** ⚠️ PENDING ADR-077
- Define hedging triggers (when to hedge)
  - Partial hedge: Lock 50% profit when up 20%
  - Full hedge: Lock 100% profit when up 40%
- Design hedge sizing (how much to bet on opposite side)

**Task 3: Multi-Leg Execution (6-8 hours)** ⚠️ PENDING ADR-077
- Coordinate multiple orders (send simultaneously)
- Handle partial fills (what if one leg fills but other doesn't?)
- Track multi-leg positions (link legs in database)

**Task 4: Testing & Validation (4-5 hours)** ⚠️ PENDING ADR-077
- Test on demo API (arbitrage, hedging)
- Validate P&L calculations (multi-leg accounting)
- Backtest historical hedging opportunities

#### Deliverable (Partial)
**Can deliver now:**
- **Code:** `trading/strategies/arbitrage.py` (from STRAT-011)

**Must wait for ADR-077:**
- **Code:** `trading/strategies/hedging.py` (hedging logic)
- **Code:** `trading/execution/multi_leg_executor.py` (coordinate multiple orders)
- **Updated:** `position_management.yaml` (hedging configuration)
- **Document:** `MULTI_LEG_STRATEGIES_GUIDE_V1.0.md` (~300 lines)

#### Success Criteria (Partial)
**Can validate now:**
- [ ] Arbitrage detection working (from STRAT-011)

**Must wait for ADR-077:**
- [ ] Hedging logic implemented
- [ ] Multi-leg execution working (both legs fill)
- [ ] Multi-leg positions tracked correctly
- [ ] Backtest shows hedging improves Sharpe ratio

---

### STRAT-018: Strategy Backtesting Framework (Phase 5-6, 🟡 High Priority)

**Task ID:** STRAT-018
**Priority:** 🟡 High
**Estimated Effort:** 18-22 hours
**Target Phase:** 5-6 (Strategy Validation, June-August 2026)
**Dependencies:** Phase 4 models complete, Phase 5 entry/exit strategies implemented
**Related Requirements:** REQ-TEST-008 (Strategy Backtesting)

#### Problem
Current strategy validation (Phase 4-5) uses **limited backtesting**:
- Model validation only (not strategy validation)
- No position sizing simulation (assume unlimited capital)
- No slippage modeling (assume perfect fills)

**Comprehensive backtesting** simulates:
- **Strategy execution:** Entry timing, exit conditions, position sizing
- **Market microstructure:** Slippage, partial fills, liquidity constraints
- **Portfolio effects:** Correlation, drawdowns, capital constraints

#### Research Objectives
1. **Design backtesting framework** (event-driven simulation)
2. **Model market microstructure** (slippage, partial fills)
3. **Simulate strategy execution** (entry/exit/sizing)
4. **Calculate performance metrics** (Sharpe, max drawdown, win rate)

#### Implementation Tasks
**Task 1: Framework Design (4-5 hours)**
- Choose architecture: Event-driven (recommended) vs vectorized (faster but less realistic)
- **Recommendation:** Event-driven (more realistic, supports multi-leg strategies)
- Design event types: MarketDataEvent, SignalEvent, OrderEvent, FillEvent
- Design backtest loop (process events chronologically)

**Example event-driven architecture:**
```python
class BacktestEngine:
    def __init__(self, strategy, data, initial_capital):
        self.strategy = strategy
        self.data = data
        self.portfolio = Portfolio(initial_capital)
        self.events = Queue()

    def run(self):
        # Load historical data
        for timestamp, market_data in self.data:
            # 1. Market data event
            self.events.put(MarketDataEvent(timestamp, market_data))

            # 2. Strategy generates signal
            signal = self.strategy.process(market_data)
            if signal:
                self.events.put(SignalEvent(timestamp, signal))

            # 3. Portfolio converts signal to order
            order = self.portfolio.signal_to_order(signal)
            if order:
                self.events.put(OrderEvent(timestamp, order))

            # 4. Execution handler simulates fill
            fill = self.execution.simulate_fill(order, market_data)
            if fill:
                self.events.put(FillEvent(timestamp, fill))
                self.portfolio.update(fill)

        # Calculate performance metrics
        return self.portfolio.calculate_metrics()
```

**Task 2: Market Microstructure Modeling (5-6 hours)**
- Model slippage (based on bid-ask spread and order size)
- Model partial fills (assume 80% fill rate for limit orders)
- Model liquidity constraints (reject orders if volume too low)

**Example slippage model:**
```python
def calculate_slippage(order_type, order_size, bid_ask_spread, market_volume):
    """Estimate slippage based on order characteristics."""
    if order_type == "market":
        # Market orders pay half the spread
        slippage = bid_ask_spread / 2

        # Large orders move price (>10% of volume)
        if order_size / market_volume > 0.10:
            price_impact = (order_size / market_volume) * bid_ask_spread
            slippage += price_impact
    else:  # limit order
        # Assume limit orders fill at limit price (no slippage)
        slippage = Decimal("0")

    return slippage
```

**Task 3: Strategy Simulation (5-6 hours)**
- Implement strategy execution (entry/exit/sizing logic)
- Track positions (open, close, P&L)
- Handle edge cases (position limits, capital constraints)

**Task 4: Performance Metrics (3-4 hours)**
- Calculate Sharpe ratio, Sortino ratio, Calmar ratio
- Calculate max drawdown, average drawdown duration
- Calculate win rate, profit factor, expectancy
- Generate performance report (text + plots)

**Example metrics:**
```python
# Sharpe ratio
sharpe = mean(returns) / std(returns) * sqrt(252)  # Annualized

# Max drawdown
cumulative = cumsum(returns)
running_max = cummax(cumulative)
drawdown = running_max - cumulative
max_drawdown = max(drawdown)

# Win rate
win_rate = count(returns > 0) / count(returns)

# Profit factor
profit_factor = sum(returns[returns > 0]) / abs(sum(returns[returns < 0]))
```

**Task 5: Integration & Automation (2-3 hours)**
- Add backtesting to strategy development workflow
- Automate backtests when strategy config changes
- Store backtest results to database (for comparison)

#### Deliverable
- **Code:** `analytics/backtesting/backtest_engine.py` (event-driven framework)
- **Code:** `analytics/backtesting/market_simulator.py` (slippage, fills, liquidity)
- **Code:** `analytics/backtesting/performance.py` (metrics calculation)
- **Document:** `STRATEGY_BACKTESTING_GUIDE_V1.0.md` (~400 lines)
  - Framework architecture
  - Market microstructure modeling
  - Performance metrics definitions
  - Interpretation guidelines
- **Report:** Example backtest report (pregame vs halftime strategy comparison)

#### Success Criteria
- [ ] Event-driven framework implemented
- [ ] Market microstructure modeled (slippage, partial fills, liquidity)
- [ ] Strategy simulation working (entry/exit/sizing)
- [ ] Performance metrics calculated (Sharpe, drawdown, win rate, profit factor)
- [ ] Backtest results match walk-forward validation (within ±10%)
- [ ] Documentation complete with example backtests

---

## Category 4: Analytics & Reporting (4 tasks)

### STRAT-019: Trade Attribution Analytics (Phase 6-7, 🔴 Critical Priority) ⚠️ PENDING ADR-077

**Task ID:** STRAT-019
**Priority:** 🔴 Critical
**Estimated Effort:** 15-20 hours
**Target Phase:** 6-7 (Attribution Analytics, September-November 2026)
**Dependencies:** ⚠️ **PENDING ADR-077** (Strategy vs Method Separation), Phase 5 position tracking complete
**Related Requirements:** REQ-OBSERV-004 (Trade Attribution)

#### ⚠️ BLOCKED UNTIL RESEARCH COMPLETE

**This task CANNOT be fully implemented until ADR-077 research is complete** (Phase 4.5, April-May 2026).

**Why blocked:** Attribution depends on knowing what to attribute to (strategy vs method vs position vs risk). Need clear taxonomy before implementing attribution.

**Can proceed with:** Basic attribution (P&L per strategy, P&L per model)
**Must wait for:** Advanced attribution (isolating specific parameter changes)

#### Problem (High-Level)
Current P&L tracking (Phase 5) shows **total portfolio performance** but doesn't answer:
- **Which strategy is best?** (pregame vs halftime vs in-play)
- **Which model is best?** (Elo vs regression vs ML)
- **Which parameter changes helped?** (stop loss -20% vs -25%)

**Trade attribution** isolates performance to specific components:
- **Strategy attribution:** P&L per strategy version
- **Model attribution:** P&L per model version
- **Parameter attribution:** P&L impact of specific parameter changes

#### Potential Solutions (Research Will Decide)
**Option A:** Attribute to individual components (strategy, model, position config)
**Option B:** Attribute to method bundles (strategy + model + position as single unit)
**Option C:** Hybrid (attribute to components when testing, methods when live trading)

#### Implementation Tasks (Conditional on ADR-077 Decision)
**Can implement now (basic attribution):**
- P&L per strategy (group trades by strategy_id)
- P&L per model (group trades by model_id)
- P&L per date (time series analysis)

**Must wait for ADR-077 (advanced attribution):**
- P&L per parameter change (requires taxonomy to know what changed)
- A/B test result analysis (requires knowing what was tested)
- Marginal contribution analysis (requires knowing component dependencies)

#### Deliverable (Partial)
**Can deliver now:**
- **Code:** `analytics/attribution/basic_attribution.py` (P&L per strategy/model)
- **Dashboard:** Grafana panels (P&L by strategy, P&L by model)

**Must wait for ADR-077:**
- **Code:** `analytics/attribution/parameter_attribution.py` (isolate parameter changes)
- **Document:** `TRADE_ATTRIBUTION_GUIDE_V1.0.md` (~300 lines)
- **Report:** Example A/B test analysis

#### Success Criteria (Partial)
**Can validate now:**
- [ ] P&L per strategy working
- [ ] P&L per model working
- [ ] Dashboard shows attribution breakdowns

**Must wait for ADR-077:**
- [ ] Parameter attribution working
- [ ] A/B test analysis automated
- [ ] Marginal contribution calculated

---

### STRAT-020: Risk Reporting Dashboard (Phase 5-6, 🟡 High Priority)

**Task ID:** STRAT-020
**Priority:** 🟡 High
**Estimated Effort:** 12-15 hours
**Target Phase:** 5-6 (Risk Monitoring, June-August 2026)
**Dependencies:** Phase 5 position monitoring complete, Phase 5 real-time dashboard (STRAT-004) complete
**Related Requirements:** REQ-OBSERV-005 (Risk Reporting)

#### Problem
Current monitoring (Phase 5) tracks **P&L and positions** but not **risk metrics**:
- No Value at Risk (VaR) calculation (potential loss at 95% confidence)
- No Sharpe ratio tracking (risk-adjusted performance)
- No drawdown monitoring (peak-to-trough decline)
- No exposure breakdown (by sport, league, strategy)

**Risk reporting** provides visibility into:
- **Portfolio risk:** VaR, Sharpe, max drawdown
- **Exposure concentration:** % portfolio in NFL, % in halftime strategy
- **Stress testing:** Simulated losses under adverse scenarios

#### Research Objectives
1. **Define risk metrics** (VaR, Sharpe, drawdown, exposure limits)
2. **Design dashboard layout** (what visualizations)
3. **Implement calculations** (SQL queries or Python)
4. **Add alerting** (email when VaR exceeds threshold)

#### Implementation Tasks
**Task 1: Risk Metrics Definition (3-4 hours)**
- Define metrics:
  - **VaR (95%):** Maximum loss at 95% confidence (historical simulation)
  - **Sharpe ratio:** (Return - risk-free rate) / std(returns)
  - **Max drawdown:** Largest peak-to-trough decline
  - **Exposure %:** % portfolio by sport, league, strategy
- Set alert thresholds (VaR >$500, drawdown >20%, etc.)

**Task 2: Calculation Implementation (4-5 hours)**
- Implement VaR calculation (historical simulation or parametric)
- Implement Sharpe ratio (rolling 30-day)
- Implement drawdown calculation (cumulative P&L)
- Implement exposure breakdown (group by sport, league, strategy)

**Example VaR calculation (historical simulation):**
```python
import numpy as np
from decimal import Decimal

def calculate_var_95(returns, confidence=0.95):
    """Calculate Value at Risk at 95% confidence (historical simulation)."""
    # Sort returns (worst to best)
    sorted_returns = sorted(returns)

    # Find 5th percentile (95% confidence = 5% worst outcomes)
    var_index = int(len(sorted_returns) * (1 - confidence))
    var_95 = sorted_returns[var_index]

    return Decimal(str(var_95))

# Example usage
daily_returns = get_daily_returns_last_30_days()  # [-50, 20, -30, 40, ...]
var = calculate_var_95(daily_returns)
print(f"VaR (95%): ${var:.2f}")
# Output: VaR (95%): $-78.00 (95% chance daily loss ≤ $78)
```

**Task 3: Dashboard Design & Implementation (3-4 hours)**
- Add Grafana panels:
  - VaR gauge (current VaR vs threshold)
  - Sharpe ratio line chart (30-day rolling)
  - Drawdown chart (cumulative P&L with peak markers)
  - Exposure breakdown (pie chart by sport, bar chart by strategy)
- Configure refresh intervals (1min for live metrics)

**Task 4: Alerting Configuration (2-3 hours)**
- Configure Grafana alerts:
  - VaR exceeds $500 (high risk)
  - Sharpe ratio <0.5 (poor risk-adjusted performance)
  - Drawdown >20% (significant loss)
  - Exposure >70% in single sport (concentration risk)
- Test alert delivery (email/Slack)

#### Deliverable
- **Code:** `analytics/risk/var_calculation.py` (VaR, Sharpe, drawdown)
- **Code:** `analytics/risk/exposure_breakdown.py` (group by sport/league/strategy)
- **Dashboard:** Grafana risk reporting panels (VaR, Sharpe, drawdown, exposure)
- **Document:** `RISK_REPORTING_GUIDE_V1.0.md` (~250 lines)
  - Risk metrics definitions
  - Dashboard layout and interpretation
  - Alert thresholds and response procedures

#### Success Criteria
- [ ] VaR (95%) calculated correctly (historical simulation)
- [ ] Sharpe ratio tracked (30-day rolling)
- [ ] Drawdown calculated (peak-to-trough)
- [ ] Exposure breakdown working (by sport, league, strategy)
- [ ] Dashboard implemented (4+ panels)
- [ ] Alerts configured (VaR, Sharpe, drawdown, exposure)
- [ ] Documentation complete with interpretation guide

---

### STRAT-021: Performance Comparison Framework (Phase 6-7, 🟡 High Priority) ⚠️ PENDING ADR-077

**Task ID:** STRAT-021
**Priority:** 🟡 High
**Estimated Effort:** 12-15 hours
**Target Phase:** 6-7 (A/B Testing, September-November 2026)
**Dependencies:** ⚠️ **PENDING ADR-077** (Strategy vs Method Separation), Phase 5 versioning system working
**Related Requirements:** REQ-TEST-009 (A/B Testing Framework)

#### ⚠️ PARTIALLY BLOCKED

**This task is PARTIALLY BLOCKED** until ADR-077 research complete (Phase 4.5).

**Why blocked:** A/B testing depends on knowing what to compare (strategy v1.0 vs v1.1? method v1.0 vs v1.1? parameter change only?). Need clear taxonomy before implementing comparison framework.

**Can proceed with:** Basic version comparison (strategy v1.0 vs v1.1 P&L comparison)
**Must wait for:** Advanced A/B testing (isolate specific parameter changes, statistical significance)

#### Problem (High-Level)
Current versioning system (Phase 1-5) tracks versions but doesn't **compare performance**:
- Can't easily answer: "Did strategy v1.1 improve vs v1.0?"
- No statistical significance testing (is improvement real or luck?)
- No automated reports (manual queries required)

**Performance comparison** automates:
- **Version comparison:** v1.0 vs v1.1 P&L, Sharpe, win rate
- **Statistical testing:** t-tests, bootstrapping, Bayesian analysis
- **Automated reports:** Weekly A/B test results

#### Potential Solutions (Research Will Decide)
**Option A:** Compare strategy versions in isolation (ignore other changes)
**Option B:** Compare method bundles (strategy + model + position as unit)
**Option C:** Isolate individual parameter changes (requires detailed taxonomy)

#### Implementation Tasks (Conditional on ADR-077 Decision)
**Can implement now (basic comparison):**
- Compare strategy v1.0 vs v1.1 (P&L, Sharpe, win rate)
- Generate comparison report (tables, plots)

**Must wait for ADR-077 (advanced comparison):**
- Isolate parameter changes (e.g., stop loss -20% vs -25%)
- Statistical significance testing (t-test, bootstrap)
- Automated A/B test reports (weekly email)

#### Deliverable (Partial)
**Can deliver now:**
- **Code:** `analytics/comparison/version_comparison.py` (basic P&L comparison)
- **Report:** Example version comparison (strategy v1.0 vs v1.1)

**Must wait for ADR-077:**
- **Code:** `analytics/comparison/statistical_tests.py` (t-test, bootstrap)
- **Code:** `analytics/comparison/ab_test_report.py` (automated report generation)
- **Document:** `AB_TESTING_GUIDE_V1.0.md` (~300 lines)

#### Success Criteria (Partial)
**Can validate now:**
- [ ] Basic version comparison working (P&L, Sharpe, win rate)
- [ ] Comparison report generated (tables, plots)

**Must wait for ADR-077:**
- [ ] Statistical significance testing working
- [ ] Automated reports working (weekly email)
- [ ] Interpretation guidelines documented

---

### STRAT-022: Tax Reporting & Accounting Integration (Phase 9-10, 🟢 Medium Priority)

**Task ID:** STRAT-022
**Priority:** 🟢 Medium
**Estimated Effort:** 10-12 hours
**Target Phase:** 9-10 (Production Trading, May-July 2027)
**Dependencies:** Phase 7+ real trading complete (6+ months of live data)
**Related Requirements:** REQ-OBSERV-006 (Tax Reporting)

#### Problem
Prediction market winnings are **taxable income** (IRS requires reporting). Without automated tax reporting:
- Manual transaction export (error-prone)
- Unclear cost basis (FIFO, LIFO, specific identification?)
- Missing wash sale tracking (can't claim losses on repurchased positions)

**Tax reporting** automates:
- **Transaction export:** CSV/Excel for tax software (TurboTax, etc.)
- **Cost basis calculation:** FIFO, LIFO, or specific identification
- **Wash sale tracking:** Identify disallowed losses
- **1099-MISC generation:** Summary of taxable income

#### Research Objectives
1. **Review tax treatment** (consult tax professional - prediction markets treated as gambling income?)
2. **Define cost basis method** (FIFO recommended for simplicity)
3. **Implement transaction export** (CSV with required fields)
4. **Add wash sale detection** (if applicable)

#### Implementation Tasks
**Task 1: Tax Treatment Research (2-3 hours)**
- Consult tax professional (CPA familiar with prediction markets)
- Document tax treatment (ordinary income vs capital gains?)
- Identify required reporting (1099-MISC, Schedule C, etc.)

**Task 2: Transaction Export (3-4 hours)**
- Query all trades for tax year (SELECT * FROM trades WHERE YEAR(created_at) = ?)
- Calculate realized P&L (closed positions only)
- Export to CSV with required fields:
  - Date acquired, Date sold, Description, Proceeds, Cost basis, Gain/Loss

**Example CSV format:**
```csv
Date Acquired,Date Sold,Description,Proceeds,Cost Basis,Gain/Loss
2026-09-15,2026-09-15,KXNFLGAME-TB-DET YES,130.00,100.00,30.00
2026-09-22,2026-09-22,KXNFLGAME-KC-LAC YES,85.00,100.00,-15.00
```

**Task 3: Cost Basis Calculation (2-3 hours)**
- Implement FIFO cost basis (first in, first out)
- Track partial position closes (if sold 50 of 100 shares, which 50?)
- Calculate adjusted cost basis (include fees)

**Example FIFO:**
```python
def calculate_fifo_cost_basis(position_id):
    """Calculate cost basis using FIFO method."""
    # Get all buys for this position (chronological)
    buys = get_buys(position_id, order_by='created_at ASC')

    # Get all sells for this position (chronological)
    sells = get_sells(position_id, order_by='created_at ASC')

    # Match sells to buys (FIFO)
    cost_basis = []
    buy_queue = list(buys)

    for sell in sells:
        remaining_sell_qty = sell['quantity']

        while remaining_sell_qty > 0 and buy_queue:
            buy = buy_queue[0]

            if buy['quantity'] <= remaining_sell_qty:
                # Entire buy consumed
                cost_basis.append({
                    'sell_id': sell['id'],
                    'buy_id': buy['id'],
                    'quantity': buy['quantity'],
                    'cost_basis': buy['price'] * buy['quantity']
                })
                remaining_sell_qty -= buy['quantity']
                buy_queue.pop(0)
            else:
                # Partial buy consumed
                cost_basis.append({
                    'sell_id': sell['id'],
                    'buy_id': buy['id'],
                    'quantity': remaining_sell_qty,
                    'cost_basis': buy['price'] * remaining_sell_qty
                })
                buy['quantity'] -= remaining_sell_qty
                remaining_sell_qty = 0

    return cost_basis
```

**Task 4: Wash Sale Detection (Optional, 2-3 hours)**
- Detect wash sales (sell at loss, rebuy within 30 days)
- Mark disallowed losses (can't claim on taxes)
- Adjust cost basis for repurchased position

**Task 5: Report Generation (2-3 hours)**
- Generate annual tax report (PDF or CSV)
- Include summary statistics (total proceeds, total cost basis, net gain/loss)
- Optional: Generate 1099-MISC (if platform doesn't provide)

#### Deliverable
- **Code:** `analytics/tax/transaction_export.py` (CSV export)
- **Code:** `analytics/tax/cost_basis.py` (FIFO calculation)
- **Code:** `analytics/tax/wash_sale.py` (wash sale detection - optional)
- **Document:** `TAX_REPORTING_GUIDE_V1.0.md` (~200 lines)
  - Tax treatment overview (consult CPA disclaimer)
  - Cost basis methodology (FIFO)
  - Export instructions (how to import into TurboTax)
- **Report:** Example 2026 tax summary (proceeds, cost basis, net gain/loss)

#### Success Criteria
- [ ] Tax treatment researched (CPA consulted)
- [ ] Transaction export working (CSV with required fields)
- [ ] Cost basis calculated correctly (FIFO)
- [ ] Wash sale detection implemented (if applicable)
- [ ] Annual tax report generated (2026 summary)
- [ ] Documentation complete with CPA consultation notes

---

## Category 5: Platform & Deployment (3 tasks)

### STRAT-023: Polymarket Integration (Phase 10, 🟡 High Priority)

**Task ID:** STRAT-023
**Priority:** 🟡 High
**Estimated Effort:** 30-40 hours
**Target Phase:** 10 (Cross-Platform Trading, December 2026-January 2027)
**Dependencies:** Phase 1 Kalshi API complete, Phase 1-9 infrastructure stable, multi-platform abstraction (STRAT-003) complete
**Related Requirements:** REQ-API-006 (Polymarket Integration)

#### Problem
Current trading (Phase 1-9) is **Kalshi-only**. Polymarket offers:
- **Different markets:** Crypto, politics (broader than Kalshi)
- **Higher liquidity:** Some markets have $1M+ volume
- **Different fee structure:** 2% protocol fee (vs 7% Kalshi taker fee)

**Polymarket integration** enables:
- **Platform arbitrage:** Profit from pricing differences between platforms
- **Market diversification:** Access markets not available on Kalshi
- **Liquidity optimization:** Trade on platform with better liquidity

#### Research Objectives
1. **Understand Polymarket architecture** (CLOB API, Polygon blockchain)
2. **Implement wallet management** (ECDSA signatures, gas estimation)
3. **Integrate CLOB API** (limit orders, market orders, order book)
4. **Test on Mumbai testnet** (before mainnet deployment)

#### Implementation Tasks
**Task 1: Polymarket Research (4-5 hours)**
- Review Polymarket documentation (CLOB API, Gamma API)
- Understand order types (limit, market, FOK, IOC)
- Review fee structure (2% protocol fee + gas fees)
- Set up Mumbai testnet wallet (Polygon testnet)

**Task 2: Wallet Management (6-8 hours)**
- Generate Ethereum wallet (ECDSA key pair)
- Implement signature generation (sign API requests)
- Implement nonce management (prevent replay attacks)
- Store private key securely (encrypted at rest)

**Example wallet setup:**
```python
from eth_account import Account
import os

# Generate new wallet (one-time setup)
account = Account.create()
private_key = account.key.hex()
address = account.address

# CRITICAL: Store private key securely
# NEVER hardcode or commit to git
encrypted_key = encrypt_private_key(private_key, os.getenv('ENCRYPTION_PASSWORD'))
save_to_file('_keys/polymarket_wallet.enc', encrypted_key)

# Load wallet (runtime)
encrypted_key = load_from_file('_keys/polymarket_wallet.enc')
private_key = decrypt_private_key(encrypted_key, os.getenv('ENCRYPTION_PASSWORD'))
account = Account.from_key(private_key)
```

**Task 3: CLOB API Integration (10-12 hours)**
- Implement authentication (ECDSA signatures)
- Implement market data fetching (order book, recent trades)
- Implement order placement (limit orders, market orders)
- Implement order cancellation
- Implement position tracking

**Example order placement:**
```python
from web3 import Web3
from eth_account.messages import encode_defunct

def place_polymarket_order(
    market_id: str,
    side: str,          # "BUY" or "SELL"
    price: Decimal,
    quantity: int,
    order_type: str = "LIMIT"
):
    """Place order on Polymarket CLOB."""
    # Build order payload
    order = {
        "market": market_id,
        "side": side,
        "price": str(price),
        "size": quantity,
        "orderType": order_type,
        "feeRateBps": 200,  # 2% protocol fee
        "nonce": get_next_nonce(),
        "expiration": int(time.time()) + 3600  # 1 hour expiration
    }

    # Sign order
    message = encode_defunct(text=json.dumps(order))
    signed = account.sign_message(message)

    # Submit to CLOB
    response = requests.post(
        "https://clob.polymarket.com/order",
        json={
            "order": order,
            "signature": signed.signature.hex()
        },
        headers={"Authorization": f"Bearer {api_key}"}
    )

    return response.json()
```

**Task 4: Gas Estimation & Transaction Building (6-8 hours)**
- Estimate gas fees (Polygon gas prices)
- Build transactions (approve, swap, settle)
- Submit transactions to Polygon network
- Monitor transaction status (pending, confirmed, failed)

**Task 5: Testing & Validation (4-5 hours)**
- Test on Mumbai testnet (all operations)
- Validate order placement (limit orders, market orders)
- Validate position tracking (balances, P&L)
- Test error handling (insufficient balance, gas estimation failures)

#### Deliverable
- **Code:** `api_connectors/polymarket_client.py` (implements BasePlatformClient)
- **Code:** `api_connectors/polymarket_auth.py` (wallet management, signatures)
- **Config:** Updated `markets.yaml` (enable Polymarket categories)
- **Document:** Updated `API_INTEGRATION_GUIDE_V2.1.md` (Polymarket section)
- **Tests:** `tests/unit/api_connectors/test_polymarket_client.py`

#### Success Criteria
- [ ] Polymarket client implements BasePlatformClient interface
- [ ] Wallet management working (key generation, signatures)
- [ ] CLOB API integration complete (get_markets, place_order, cancel_order)
- [ ] Gas estimation working (accurate estimates)
- [ ] Tested on Mumbai testnet (all operations successful)
- [ ] Documentation complete with examples

---

### STRAT-024: Cross-Platform Arbitrage Detection (Phase 10, 🟡 High Priority)

**Task ID:** STRAT-024
**Priority:** 🟡 High
**Estimated Effort:** 12-15 hours
**Target Phase:** 10 (Cross-Platform Trading, December 2026-January 2027)
**Dependencies:** Phase 10 Polymarket integration complete (STRAT-023), multi-platform abstraction (STRAT-003) complete
**Related Requirements:** REQ-EDGE-004 (Cross-Platform Arbitrage)

#### Problem
Same markets often trade at **different prices** on different platforms. Without cross-platform arbitrage:
- Missing risk-free profit opportunities (price discrepancies)
- Suboptimal execution (trading on platform with worse price)

**Cross-platform arbitrage** identifies:
- **Price discrepancies:** Same market priced differently on Kalshi vs Polymarket
- **Risk-free profit:** Buy on cheaper platform, sell on expensive platform
- **Execution optimization:** Route orders to platform with best price

#### Research Objectives
1. **Identify common markets** (same event on both platforms)
2. **Match market IDs** (map Kalshi tickers to Polymarket market IDs)
3. **Detect price discrepancies** (real-time comparison)
4. **Calculate risk-free profit** (after fees and gas)

#### Implementation Tasks
**Task 1: Market Matching (4-5 hours)**
- Identify common events (NFL games, political events)
- Map Kalshi tickers to Polymarket market IDs
- Store mappings in database (cross_platform_markets table)

**Example mapping:**
```sql
CREATE TABLE cross_platform_markets (
    id SERIAL PRIMARY KEY,
    kalshi_ticker VARCHAR(50) NOT NULL,
    polymarket_market_id VARCHAR(100) NOT NULL,
    event_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Example entry
INSERT INTO cross_platform_markets (kalshi_ticker, polymarket_market_id, event_description)
VALUES (
    'KXNFLGAME-2026-09-15-TB-DET',
    '0x1234...abcd',
    '2026 NFL: Tampa Bay Buccaneers vs Detroit Lions - Winner'
);
```

**Task 2: Price Comparison (3-4 hours)**
- Fetch prices from both platforms (concurrent requests)
- Calculate price discrepancy (absolute difference)
- Filter for significant discrepancies (>2% difference)

**Example price comparison:**
```python
async def detect_cross_platform_arbitrage():
    """Detect arbitrage opportunities across platforms."""
    # Fetch common markets
    common_markets = get_cross_platform_markets()

    # Fetch prices concurrently
    for market in common_markets:
        kalshi_price = await kalshi_client.get_market_price(market['kalshi_ticker'])
        poly_price = await polymarket_client.get_market_price(market['polymarket_market_id'])

        # Calculate discrepancy
        price_diff = abs(kalshi_price - poly_price)

        # Filter for significant discrepancies (>2%)
        if price_diff > Decimal("0.02"):
            # Calculate risk-free profit (after fees)
            profit = calculate_arbitrage_profit(
                kalshi_price, poly_price,
                kalshi_fee=Decimal("0.07"),
                poly_fee=Decimal("0.02"),
                gas_fee_usd=Decimal("0.50")  # Polygon gas estimate
            )

            if profit > Decimal("5.00"):  # Minimum profit threshold
                yield {
                    'kalshi_ticker': market['kalshi_ticker'],
                    'polymarket_id': market['polymarket_market_id'],
                    'kalshi_price': kalshi_price,
                    'polymarket_price': poly_price,
                    'price_diff': price_diff,
                    'profit': profit
                }
```

**Task 3: Profit Calculation (2-3 hours)**
- Calculate risk-free profit (after fees and gas)
- Account for slippage (assume 0.5% slippage)
- Set minimum profit threshold ($5 minimum)

**Task 4: Execution Workflow (3-4 hours)**
- Implement simultaneous execution (place orders on both platforms)
- Handle partial fills (what if one platform fills but other doesn't?)
- Monitor execution (ensure both legs fill)

**Task 5: Monitoring & Alerting (2-3 hours)**
- Add dashboard panel (show arbitrage opportunities)
- Alert when large opportunities detected (>$50 profit)
- Track historical arbitrage (frequency, average profit)

#### Deliverable
- **Code:** `analytics/arbitrage/cross_platform_arbitrage.py` (detection and execution)
- **Database:** `cross_platform_markets` table (market mappings)
- **Updated:** `trading/execution/arbitrage_executor.py` (cross-platform execution)
- **Document:** `CROSS_PLATFORM_ARBITRAGE_GUIDE_V1.0.md` (~200 lines)
  - Market matching methodology
  - Profit calculation (after fees and gas)
  - Execution workflow
- **Dashboard:** Grafana panel for arbitrage opportunities

#### Success Criteria
- [ ] Market matching working (10+ common markets mapped)
- [ ] Price comparison working (real-time discrepancy detection)
- [ ] Profit calculation accurate (after fees and gas)
- [ ] Execution workflow tested (simultaneous orders on both platforms)
- [ ] Dashboard shows arbitrage opportunities
- [ ] Documentation complete with examples

---

### STRAT-025: Production Deployment Automation (Phase 9-10, 🟢 Medium Priority)

**Task ID:** STRAT-025
**Priority:** 🟢 Medium
**Estimated Effort:** 15-20 hours
**Target Phase:** 9-10 (Production Deployment, May-July 2027)
**Dependencies:** Phase 8 infrastructure stable, Phase 9 real trading complete (demo → prod transition)
**Related Requirements:** REQ-SYS-006 (Production Deployment)

#### Problem
Current deployment (Phase 0-8) is **manual**:
- Manual code deployment (copy files to production server)
- Manual environment setup (install dependencies, configure database)
- Manual database migrations (run SQL scripts manually)
- No rollback plan (if deployment fails)

**Production deployment automation** enables:
- **CI/CD pipeline:** Automated deployment on git push
- **Zero-downtime deployments:** Rolling updates, blue-green deployments
- **Automated rollback:** Revert to previous version if deployment fails
- **Health checks:** Verify deployment success

#### Research Objectives
1. **Choose deployment strategy** (Docker, Kubernetes, or VM-based)
2. **Design CI/CD pipeline** (GitHub Actions, GitLab CI, or Jenkins)
3. **Implement automated deployment** (deploy on merge to main)
4. **Add health checks** (verify system is operational)

#### Implementation Tasks
**Task 1: Deployment Strategy (3-4 hours)**
- Choose infrastructure: Docker (recommended), Kubernetes (overkill for single app), or VM-based
- **Recommendation:** Docker Compose (simple, sufficient for Phase 9-10)
- Design architecture: Application container, PostgreSQL container, Grafana container

**Example Docker Compose:**
```yaml
version: '3.8'

services:
  app:
    build: .
    container_name: precog_app
    environment:
      - DB_HOST=postgres
      - DB_PASSWORD=${DB_PASSWORD}
      - KALSHI_API_KEY=${KALSHI_API_KEY}
    depends_on:
      - postgres
    restart: unless-stopped

  postgres:
    image: postgres:15
    container_name: precog_db
    environment:
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: precog_grafana
    ports:
      - "3000:3000"
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
```

**Task 2: CI/CD Pipeline Design (4-5 hours)**
- Choose CI/CD platform: GitHub Actions (recommended, free for public repos)
- Design pipeline stages:
  1. Test (run pytest, check coverage ≥80%)
  2. Build (build Docker image)
  3. Deploy (push image to registry, update production server)
- Add manual approval step (for production deployments)

**Example GitHub Actions workflow:**
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=. --cov-fail-under=80

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: docker/build-push-action@v4
        with:
          push: true
          tags: ghcr.io/precog/precog:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval
    steps:
      - name: Deploy to production server
        run: |
          ssh production-server "docker pull ghcr.io/precog/precog:latest && \
                                   docker compose up -d"
```

**Task 3: Automated Deployment (4-5 hours)**
- Implement deployment script (SSH to production, pull image, restart containers)
- Add database migration step (run migrations before deployment)
- Add health check (verify app is responding after deployment)

**Task 4: Rollback Strategy (2-3 hours)**
- Tag Docker images with version (precog:v1.0, precog:v1.1)
- Implement rollback script (revert to previous image)
- Test rollback (simulate failed deployment)

**Task 5: Health Checks & Monitoring (2-3 hours)**
- Add health check endpoint (/health returns 200 if app is operational)
- Monitor deployment status (alert if health check fails)
- Add deployment logs (track deployments in database)

#### Deliverable
- **Infrastructure:** `docker-compose.yml` (application, database, Grafana)
- **Config:** `.github/workflows/deploy.yml` (CI/CD pipeline)
- **Script:** `scripts/deploy.sh` (deployment automation)
- **Script:** `scripts/rollback.sh` (rollback to previous version)
- **Document:** `DEPLOYMENT_GUIDE_V1.0.md` (~300 lines)
  - Deployment strategy and architecture
  - CI/CD pipeline stages
  - Rollback procedures
  - Health check implementation

#### Success Criteria
- [ ] Docker Compose working (all services start)
- [ ] CI/CD pipeline working (automated deployment on merge to main)
- [ ] Automated deployment tested (deploy to staging environment)
- [ ] Rollback tested (revert to previous version)
- [ ] Health checks working (verify app is operational)
- [ ] Documentation complete with runbooks

---

## Timeline & Dependencies

### High-Level Timeline

**Phases 1-3 (January-April 2026):**
- STRAT-002: Configuration Validation (Phase 2-3)
- STRAT-008: Feature Engineering Pipeline (Phase 3-4)
- STRAT-005: Disaster Recovery & Backup (Phase 3-4)

**Phase 4 (April-May 2026):**
- Model development (Elo, regression, ML)
- Ensemble framework implementation

**Phase 4.5 (April-May 2026) - RESEARCH PHASE:**
- **DEF-013 to DEF-016:** Strategy research (HIGHEST PRIORITY)
- **DEF-009 to DEF-012:** Model research (dynamic ensemble weights)
- **DEF-017 to DEF-019:** Edge detection research (quick wins)

**Phases 5-6 (June-August 2026):**
- STRAT-001: Database Performance (Phase 5-6)
- STRAT-004: Real-Time Dashboard (Phase 5-6)
- STRAT-006: Dynamic Ensemble Weights (⚠️ PENDING ADR-076, Phase 5-6)
- STRAT-009: Walk-Forward Validation (Phase 4-5)
- STRAT-012: Strategy vs Method Separation (⚠️ PENDING ADR-077, Phase 4-5)
- STRAT-014: Exit Optimization (Phase 6-7)
- STRAT-015: Position Correlation (Phase 6-7)
- STRAT-018: Strategy Backtesting (Phase 5-6)
- STRAT-019: Trade Attribution (⚠️ PENDING ADR-077, Phase 6-7)
- STRAT-020: Risk Reporting (Phase 5-6)
- STRAT-021: Performance Comparison (⚠️ PENDING ADR-077, Phase 6-7)

**Phases 7-8 (September 2026-January 2027):**
- STRAT-007: Additional Model Types (Phase 6-7)
- STRAT-010: Model Drift Detection (Phase 6-7)
- STRAT-011: Advanced Edge Detection (Phase 6-7)
- STRAT-013: Advanced Entry Strategies (Phase 7-8)
- STRAT-016: Dynamic Position Sizing (Phase 7-8)
- STRAT-017: Multi-Leg Strategies (⚠️ PENDING ADR-077, Phase 8-9)

**Phases 9-10 (February-July 2027):**
- STRAT-022: Tax Reporting (Phase 9-10)
- STRAT-023: Polymarket Integration (Phase 10)
- STRAT-024: Cross-Platform Arbitrage (Phase 10)
- STRAT-025: Production Deployment (Phase 9-10)

**Phase 11+ (Future):**
- STRAT-003: Multi-Platform Abstraction (Phase 10+, enables additional platforms)

---

### Dependency Diagram

**Critical Path (blocks other tasks):**
```
Phase 4.5 Research (ADR-076, ADR-077)
    ↓
STRAT-006 (Dynamic Ensemble) ⚠️ PENDING ADR-076
STRAT-012 (Strategy Separation) ⚠️ PENDING ADR-077
    ↓
STRAT-017 (Multi-Leg Strategies) ⚠️ PENDING ADR-077
STRAT-019 (Trade Attribution) ⚠️ PENDING ADR-077
STRAT-021 (Performance Comparison) ⚠️ PENDING ADR-077
```

**Parallel Work (can proceed independently):**
```
Infrastructure:
- STRAT-001 (Database Performance)
- STRAT-002 (Config Validation)
- STRAT-003 (Multi-Platform Abstraction)
- STRAT-004 (Real-Time Dashboard)
- STRAT-005 (Disaster Recovery)

Modeling:
- STRAT-007 (Additional Models)
- STRAT-008 (Feature Engineering)
- STRAT-009 (Walk-Forward Validation)
- STRAT-010 (Model Drift Detection)
- STRAT-011 (Advanced Edge Detection)

Strategy:
- STRAT-013 (Advanced Entry)
- STRAT-014 (Exit Optimization)
- STRAT-015 (Position Correlation)
- STRAT-016 (Dynamic Sizing)
- STRAT-018 (Strategy Backtesting)

Analytics:
- STRAT-020 (Risk Reporting)
- STRAT-022 (Tax Reporting)

Platform:
- STRAT-023 (Polymarket Integration)
- STRAT-024 (Cross-Platform Arbitrage)
- STRAT-025 (Production Deployment)
```

---

### Blocked Tasks Summary

**5 tasks blocked by Phase 4.5 research:**

1. **STRAT-006:** Dynamic Ensemble Weights ⚠️ PENDING ADR-076
   - **Blocker:** Must choose Option A/B/C for ensemble weights architecture
   - **Research tasks:** DEF-009, DEF-010, DEF-011, DEF-012 (36-51 hours)

2. **STRAT-012:** Strategy vs Method Separation ⚠️ PENDING ADR-077 (**HIGHEST PRIORITY**)
   - **Blocker:** Must define clear taxonomy (what is strategy vs position management)
   - **Research tasks:** DEF-013, DEF-014, DEF-015, DEF-016 (28-36 hours)

3. **STRAT-017:** Multi-Leg Strategies ⚠️ PENDING ADR-077 (partial block)
   - **Blocker:** Hedging logic spans strategy and position management
   - **Can proceed:** Basic arbitrage detection
   - **Must wait:** Complex hedging strategies

4. **STRAT-019:** Trade Attribution ⚠️ PENDING ADR-077 (partial block)
   - **Blocker:** Attribution depends on knowing what to attribute to
   - **Can proceed:** Basic P&L per strategy/model
   - **Must wait:** Parameter attribution, A/B test analysis

5. **STRAT-021:** Performance Comparison ⚠️ PENDING ADR-077 (partial block)
   - **Blocker:** Comparison framework depends on what to compare
   - **Can proceed:** Basic version comparison
   - **Must wait:** Statistical significance testing, automated reports

---

## Success Metrics

### Project-Level Metrics

**Overall Goal:** Build profitable, sustainable prediction market trading system

**Key Performance Indicators (KPIs):**
1. **Profitability:** Cumulative P&L > $0 (break-even minimum, >$10k target by Phase 10)
2. **Risk-Adjusted Returns:** Sharpe ratio >1.0 (decent risk-adjusted performance)
3. **Reliability:** System uptime >99% (max 7 hours downtime per month)
4. **Test Coverage:** ≥80% coverage (maintain quality as codebase grows)

### Category-Level Metrics

**Category 1: Architecture & Infrastructure**
- **Performance:** Database query latency <100ms (P95)
- **Reliability:** Zero data loss incidents (backups working)
- **Scalability:** Support 100+ concurrent positions (no slowdown)

**Category 2: Modeling & Edge Detection**
- **Accuracy:** Brier score ≤0.20 (better than market consensus)
- **Edge Detection:** Identify 10+ edges per week (profitable opportunities)
- **Model Performance:** Walk-forward validation Sharpe >0.5 (profitable backtests)

**Category 3: Strategy & Position Management**
- **Strategy Performance:** Sharpe ratio >1.0 per strategy version
- **Exit Optimization:** Exit optimization improves Sharpe ≥10% vs fixed rules
- **Risk Management:** Max drawdown <20% (capital preservation)

**Category 4: Analytics & Reporting**
- **Attribution Accuracy:** P&L attribution reconciles to 100% (no missing P&L)
- **Risk Reporting:** VaR (95%) accuracy within ±10% (validated via backtesting)
- **Tax Reporting:** Zero discrepancies with platform 1099-MISC (accurate reporting)

**Category 5: Platform & Deployment**
- **Cross-Platform:** Polymarket integration complete (10+ markets mapped)
- **Deployment:** Zero-downtime deployments (no service interruptions)
- **Monitoring:** Alert response time <15 minutes (proactive issue resolution)

---

## Conclusion

This roadmap organizes **25 strategic tasks** across 5 categories, spanning Phases 1-10 (January 2026-July 2027).

**Key Takeaways:**

1. **Research before implementation:** Phase 4.5 research (11 tasks, 74-92 hours) must complete before implementing 5 strategic tasks
2. **Strategies research is MOST IMPORTANT:** ADR-077 (Strategy vs Method Separation) is HIGHEST PRIORITY
3. **Many tasks can proceed in parallel:** 20 of 25 tasks are NOT blocked by research
4. **Comprehensive scope:** Infrastructure, modeling, strategy, analytics, platform

**Next Steps:**

1. **Complete Phase 0.7c** (infrastructure work in progress)
2. **Begin Phase 1** (Database & API Connectivity)
3. **Implement unblocked tasks** (STRAT-002, STRAT-005, STRAT-008 in Phases 2-3)
4. **Conduct Phase 4.5 research** (April-May 2026) to unblock critical tasks
5. **Implement blocked tasks** (June 2026+) after research decisions finalized

**Success:** By Phase 10 (July 2027), we will have a profitable, multi-platform trading system with comprehensive analytics, robust risk management, and automated deployment.

---

**END OF STRATEGIC_WORK_ROADMAP_V1.0.md**
