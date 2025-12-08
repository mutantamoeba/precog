# Phase 2.5 Deferred Tasks

---
**Version:** 1.0
**Created:** 2025-12-07
**Last Updated:** 2025-12-07
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

## Cross-References

- **ADR-100:** Service Supervisor Pattern
- **ADR-101:** ESPN Status/Season Type Mapping
- **ADR-102:** CloudWatch/ELK Log Aggregation (Deferred)
- **REQ-SCHED-001:** APScheduler-based Live Data Polling
- **REQ-SCHED-002:** Service Supervisor Pattern
- **REQ-OBSERV-003:** Log Aggregation (Deferred)

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-07 | Initial creation with 6 deferred tasks |

---

**END OF PHASE_2.5_DEFERRED_TASKS_V1.0.md**
