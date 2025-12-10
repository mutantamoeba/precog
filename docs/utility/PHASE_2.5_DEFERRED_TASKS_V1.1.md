# Phase 2.5 Deferred Tasks

---
**Version:** 1.1
**Created:** 2025-12-07
**Last Updated:** 2025-12-09
**Phase:** Phase 2.5 (Live Data Collection)
**Status:** Active - Tasks Deferred to Future Phases
---

## Overview

This document tracks tasks identified during Phase 2.5 (Live Data Collection) that are important but not blocking for the current phase. These tasks are deferred to future phases with documented rationale and target timelines.

## Deferred Tasks Summary

| Task ID | Description | Priority | Target Phase | Estimated Hours |
|---------|-------------|----------|--------------|-----------------|
| DEF-P2.5-001 | CloudWatch Logs Integration | Medium | Phase 4 | 4-6 |
| DEF-P2.5-002 | ELK Stack Setup | Medium | Phase 4 | 8-12 |
| DEF-P2.5-003 | Alert Threshold Configuration | Medium | Phase 4 | 2-3 |
| DEF-P2.5-004 | Service Health Dashboard | Low | Phase 4 | 4-6 |
| DEF-P2.5-005 | NCAAW Team Seeding | Low | Phase 3 | 2-3 |
| DEF-P2.5-006 | Rate Limit YAML Integration | Low | Phase 3 | 2-4 |
| DEF-P2.5-007 | Two-Axis Environment Configuration | High | Phase 2 | 8-12 |

---

## Detailed Task Descriptions

### DEF-P2.5-001: CloudWatch Logs Integration

**Priority:** Medium
**Target Phase:** Phase 4
**Estimated Hours:** 4-6
**GitHub Issue:** #195
**Reference:** ADR-102, REQ-OBSERV-003

**Description:**
Integrate Service Supervisor logs with AWS CloudWatch for centralized log management.

**Implementation:**
- Create log group: `/precog/data-collector`
- Create log streams per service: `espn-poller`, `kalshi-poller`
- Configure IAM roles for log shipping
- Add CloudWatch handler to logging setup

**Rationale for Deferral:**
- File-based logging sufficient for Phase 2.5 development
- CloudWatch costs ($0.50/GB ingested) not justified until production
- Phase 4 trading requires production-grade observability

---

### DEF-P2.5-002: ELK Stack Setup

**Priority:** Medium
**Target Phase:** Phase 4
**Estimated Hours:** 8-12
**GitHub Issue:** #196
**Reference:** ADR-102, REQ-OBSERV-003

**Description:**
Set up Elasticsearch, Logstash, Kibana for log aggregation and analysis.

**Implementation:**
- Elasticsearch cluster (single node for dev, 3-node for prod)
- Logstash pipeline for JSON log processing
- Kibana dashboards for visualization
- Docker Compose configuration for local development

**Rationale for Deferral:**
- Significant infrastructure investment
- File-based logging sufficient for Phase 2.5
- ELK alternative to CloudWatch (choose one based on infrastructure)

---

### DEF-P2.5-003: Alert Threshold Configuration

**Priority:** Medium
**Target Phase:** Phase 4
**Estimated Hours:** 2-3
**GitHub Issue:** #197
**Reference:** ADR-100, scripts/run_data_collector.py

**Description:**
Configure production alert thresholds for Service Supervisor.

**Implementation:**
- Error rate threshold: >5 errors/minute
- Service down threshold: >60 seconds
- Slack webhook integration
- PagerDuty integration (optional)
- YAML configuration for thresholds

**Rationale for Deferral:**
- Alert callbacks already in place (just need to configure)
- No production traffic yet, alerts would be noise
- Phase 4 trading requires immediate error notification

---

### DEF-P2.5-004: Service Health Dashboard

**Priority:** Low
**Target Phase:** Phase 4
**Estimated Hours:** 4-6
**GitHub Issue:** #198
**Reference:** ADR-100

**Description:**
Create visual dashboard for service health metrics.

**Implementation:**
- Grafana dashboard with metrics from Service Supervisor
- Prometheus exporter for metrics scraping
- Panels: uptime, error rates, poll counts, latency
- Docker Compose for Grafana + Prometheus

**Rationale for Deferral:**
- Console output sufficient for development
- Infrastructure investment for nice-to-have feature
- Phase 4/5 would benefit from visual monitoring

---

### DEF-P2.5-005: NCAAW Team Seeding

**Priority:** Low
**Target Phase:** Phase 3
**Estimated Hours:** 2-3
**GitHub Issue:** #194 (created)
**Reference:** Issue #187

**Description:**
Add NCAAW (Women's College Basketball) teams to database seed files.

**Implementation:**
- Create 008_ncaaw_teams.sql
- ~350 teams (all D1 women's basketball)
- Use ESPN team IDs

**Rationale for Deferral:**
- NCAAW not initial focus sport
- Market availability on Kalshi unclear
- Can add when expanding to NCAAW markets

---

### DEF-P2.5-006: Rate Limit YAML Integration

**Priority:** Low
**Target Phase:** Phase 3
**Estimated Hours:** 2-4
**GitHub Issue:** #199

**Description:**
Integrate ConfigLoader with rate limiter for YAML-configurable rate limits.

**Implementation:**
- Read rate limits from data_sources.yaml
- Runtime adjustment without restart
- Per-API configurable limits
- Metrics for rate limit utilization

**Rationale for Deferral:**
- Current hardcoded limits working fine
- Not blocking data collection
- Nice-to-have for operational flexibility

---

### DEF-P2.5-007: Two-Axis Environment Configuration

**Priority:** High
**Target Phase:** Phase 2
**Estimated Hours:** 8-12
**GitHub Issue:** #202
**Reference:** ADR-105 (Planned)

**Description:**
Implement a two-axis environment configuration model that independently controls:
1. **PRECOG_ENV:** Application environment (dev/test/staging/prod) -> controls database
2. **{MARKET}_MODE:** Per-market API mode (demo/live) -> controls API endpoints

**Problem Statement:**
Current environment configuration has multiple issues:
- `.env` has `ENVIRONMENT=development` but code checks `PRECOG_ENV` (not set)
- Code falls back to `DB_NAME=precog_test`, causing confusion
- No differentiation between API environments and database environments
- Phase 1.5 TODO "Update connection.py to use environment-aware config" was never completed

**Proposed Solution:**
```bash
# Axis 1: Application environment (controls database)
PRECOG_ENV=staging  # -> uses precog_staging database

# Axis 2: Market API modes (independent per market)
KALSHI_MODE=demo         # -> uses demo-api.kalshi.co
POLYMARKET_MODE=live     # -> uses production Polymarket API (future)
```

**Implementation Plan:**
1. **Core Architecture (4-6h):** Create `src/precog/config/environment.py` with environment and market mode resolution
2. **Safety Guardrails (2-3h):** Block dangerous combinations (e.g., test database + live API)
3. **CLI Integration (2-3h):** Add `--env` and `--market-mode` CLI parameters

**Rationale for Deferral:**
- Current workaround: manually set `DB_NAME` in `.env` for each database
- Not blocking live data collection (seeds work once applied to correct database)
- Requires careful design for multi-market extensibility
- Full implementation should wait until after Phase 2.5 core tasks complete

**Acceptance Criteria:**
- [ ] `PRECOG_ENV` consistently controls database selection
- [ ] `{MARKET}_MODE` independently controls API endpoints per market
- [ ] CLI `--env` parameter works for environment override
- [ ] Dangerous combinations blocked with clear error messages
- [ ] Documentation updated with new configuration approach

---

## Cross-References

- **ADR-100:** Service Supervisor Pattern
- **ADR-101:** ESPN Status/Season Type Mapping
- **ADR-102:** CloudWatch/ELK Log Aggregation (Deferred)
- **ADR-105:** Two-Axis Environment Configuration (Planned)
- **REQ-SCHED-001:** APScheduler-based Live Data Polling
- **REQ-SCHED-002:** Service Supervisor Pattern
- **REQ-OBSERV-003:** Log Aggregation (Deferred)
- **REQ-CONFIG-TBD:** Environment Configuration Requirements (to be created)

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2025-12-09 | Added DEF-P2.5-007: Two-Axis Environment Configuration (Issue #202) |
| 1.0 | 2025-12-07 | Initial creation with 6 deferred tasks |

---

**END OF PHASE_2.5_DEFERRED_TASKS_V1.1.md**
