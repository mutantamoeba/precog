# Incident Response Protocol

**Version:** 1.0
**Created:** 2026-04-02
**Scope:** Single-operator runbook for Precog service failures, data issues, and recovery.
**Related:** ADR-100 (Service Supervisor), C10 Council (Scorpius risk findings), Issue #520

---

## 1. Severity Levels

| Level | Name | Criteria | Response Time | Examples |
|-------|------|----------|---------------|----------|
| **P1** | Data Loss / Corruption | SCD integrity broken, rows missing or duplicated, migration partial-apply | Immediate (drop everything) | Orphaned `row_current_ind` rows, migration halfway applied, position data lost |
| **P2** | Service Degraded | Poller down, stale data accumulating, DB connection failing | Within 1 hour | Kalshi poller crashed, ESPN poller stalled, connection pool exhausted |
| **P3** | Cosmetic / Monitoring | Health check flapping, log noise, non-blocking warnings | Next session | Spurious circuit breaker entry, log rotation full, test flakiness |

**Escalation rule:** Any P2 that persists for 30+ minutes after first recovery attempt becomes P1.

---

## 2. Diagnostic Commands (Quick Reference)

Run these first to assess the situation.

### Service Health

```bash
# Are pollers running?
python main.py scheduler status

# Check system_health table
psql precog_dev -c "SELECT component, status, last_check, details FROM system_health ORDER BY last_check DESC;"

# Active circuit breakers (unresolved)
psql precog_dev -c "SELECT breaker_type, trigger_value, triggered_at, notes FROM circuit_breaker_events WHERE resolved_at IS NULL;"

# Scheduler registration
psql precog_dev -c "SELECT host_id, service_name, status, last_heartbeat FROM scheduler_status ORDER BY last_heartbeat DESC LIMIT 5;"
```

### Data Freshness

```bash
# Latest market snapshot age
psql precog_dev -c "SELECT NOW() - MAX(row_start_ts) AS staleness FROM market_snapshots WHERE row_current_ind = TRUE;"

# Latest game state age
psql precog_dev -c "SELECT NOW() - MAX(row_start_ts) AS staleness FROM game_states WHERE row_current_ind = TRUE;"

# Latest game_odds age
psql precog_dev -c "SELECT NOW() - MAX(row_start_ts) AS staleness FROM game_odds WHERE row_current_ind = TRUE;"
```

### SCD Integrity

```bash
# Duplicate current rows (should return 0 for each)
psql precog_dev -c "SELECT market_id, COUNT(*) FROM market_snapshots WHERE row_current_ind = TRUE GROUP BY market_id HAVING COUNT(*) > 1;"
psql precog_dev -c "SELECT espn_event_id, COUNT(*) FROM game_states WHERE row_current_ind = TRUE GROUP BY espn_event_id HAVING COUNT(*) > 1;"
psql precog_dev -c "SELECT edge_id, COUNT(*) FROM edges WHERE row_current_ind = TRUE GROUP BY edge_id HAVING COUNT(*) > 1;"

# Orphaned current rows (row_current_ind TRUE but row_end_ts set -- should be 0)
psql precog_dev -c "SELECT COUNT(*) FROM market_snapshots WHERE row_current_ind = TRUE AND row_end_ts IS NOT NULL;"

# Validate SCD queries in codebase
python scripts/validate_scd_queries.py --verbose
```

### Database

```bash
# Connection test
python scripts/test_db_connection.py

# Current migration version
cd src/precog/database && alembic current

# Active connections (pool health)
psql precog_dev -c "SELECT count(*), state FROM pg_stat_activity WHERE datname = 'precog_dev' GROUP BY state;"
```

---

## 3. Incident Runbooks

### 3.1 Service Failure (P2)

**Symptoms:** `scheduler status` shows service stopped, system_health shows `degraded` or `error`, data staleness growing.

**Step 1 -- Diagnose**
```bash
python main.py scheduler status
psql precog_dev -c "SELECT component, status, details FROM system_health WHERE status != 'healthy';"
psql precog_dev -c "SELECT * FROM circuit_breaker_events WHERE resolved_at IS NULL;"
```

**Step 2 -- Check for zombie processes**
```bash
# Windows
tasklist | grep -i python
# If stale scheduler_status rows exist:
psql precog_dev -c "UPDATE scheduler_status SET status = 'stopped' WHERE status = 'running' AND last_heartbeat < NOW() - INTERVAL '10 minutes';"
```

**Step 3 -- Restart**
```bash
python main.py scheduler stop          # Clean stop (may no-op if already dead)
python main.py scheduler start --supervised --foreground
```

**Step 4 -- Verify recovery**
Wait 2-3 poll cycles, then:
```bash
python main.py scheduler status
psql precog_dev -c "SELECT NOW() - MAX(row_start_ts) AS staleness FROM market_snapshots WHERE row_current_ind = TRUE;"
```

**If restart fails repeatedly:** Check logs for root cause (auth failure, API down, config error). The ServiceSupervisor has a built-in circuit breaker -- after `max_retries` (default 3) it stops restarting. Fix the underlying issue before restarting.

**Gap:** No alerting exists. You must notice the problem manually. Future: health check endpoint or scheduled monitoring script.

---

### 3.2 Data Quality Issue (P1 or P2)

#### 3.2.1 SCD Integrity Violation (P1)

**Symptoms:** Duplicate current rows, orphaned versioning, queries returning stale data.

**Step 1 -- Identify scope**
```bash
# Which tables are affected?
psql precog_dev -c "SELECT 'market_snapshots' AS tbl, market_id::text AS key, COUNT(*) FROM market_snapshots WHERE row_current_ind = TRUE GROUP BY market_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'game_states', espn_event_id::text, COUNT(*) FROM game_states WHERE row_current_ind = TRUE GROUP BY espn_event_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'edges', edge_id, COUNT(*) FROM edges WHERE row_current_ind = TRUE GROUP BY edge_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'positions', position_id, COUNT(*) FROM positions WHERE row_current_ind = TRUE GROUP BY position_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'game_odds', (game_id::text || ':' || sportsbook), COUNT(*) FROM game_odds WHERE row_current_ind = TRUE GROUP BY game_id, sportsbook HAVING COUNT(*) > 1;"
```

**Step 2 -- Stop pollers** (prevent further corruption)
```bash
python main.py scheduler stop
```

**Step 3 -- Fix duplicates**
For each duplicate, keep the row with the latest `row_start_ts` and expire the others:
```sql
-- Example for market_snapshots (adapt table/key for others)
UPDATE market_snapshots
SET row_current_ind = FALSE, row_end_ts = NOW()
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (PARTITION BY market_id ORDER BY row_start_ts DESC) AS rn
        FROM market_snapshots WHERE row_current_ind = TRUE
    ) ranked WHERE rn > 1
);
```

**Step 4 -- Verify and restart**
Re-run the integrity queries from Section 2. When clean, restart pollers.

#### 3.2.2 NULL Propagation (P2)

**Symptoms:** Critical columns (prices, volumes) are NULL in current rows.

```bash
# Check for NULL prices in current market snapshots
psql precog_dev -c "SELECT COUNT(*) FROM market_snapshots WHERE row_current_ind = TRUE AND yes_ask_price IS NULL AND no_ask_price IS NULL;"
```

**Root cause investigation:** NULL propagation typically comes from API responses with missing fields being written without COALESCE protection. Check recent poller logs for parsing warnings.

**Gap:** No automated NULL detection on write path. Future: column-level NOT NULL constraints or write-time validation. See `feedback_coalesce_null_perpetuation.md`.

#### 3.2.3 Stale Data (P2)

**Symptoms:** Data freshness exceeds expected poll interval (default 15s for Kalshi, 30s for ESPN).

**Threshold:** Data older than 5 minutes during active market hours is stale.

```bash
psql precog_dev -c "SELECT component, status, details->>'last_poll_age_seconds' AS age_sec FROM system_health WHERE component IN ('kalshi_api', 'espn_api');"
```

If stale: follow Service Failure runbook (3.1). If pollers are running but data is stale, the API may be rate-limited or returning errors -- check poller logs.

**Gap:** No freshness validation in health checks. The `system_health` table tracks status but does not automatically flag staleness. Future: staleness threshold check in ServiceSupervisor health loop.

---

### 3.3 Database Issues (P1 or P2)

#### 3.3.1 Connection Failure (P2)

```bash
python scripts/test_db_connection.py
```

**If PostgreSQL is down:**
```bash
# Windows (check service)
sc query postgresql-x64-15    # or your service name
net start postgresql-x64-15   # restart if stopped
```

**If connection works but pool exhausted:**
```bash
psql precog_dev -c "SELECT count(*), state FROM pg_stat_activity WHERE datname = 'precog_dev' GROUP BY state;"
# If many 'idle' connections: stale connections from crashed processes
psql precog_dev -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'precog_dev' AND state = 'idle' AND query_start < NOW() - INTERVAL '30 minutes';"
```

Then restart pollers.

**Gap:** Connection pool is a SPOF. No pool size monitoring or automatic recovery. Future: pool health metric in system_health table.

#### 3.3.2 Migration Failure (P1)

**Symptoms:** Alembic reports partial migration, schema mismatch errors in poller logs.

**Step 1 -- Assess state**
```bash
cd src/precog/database && alembic current
cd src/precog/database && alembic history --verbose | head -20
```

**Step 2 -- If migration partially applied, rollback**
```bash
cd src/precog/database && alembic downgrade -1
```

**Step 3 -- Fix the migration script, then re-apply**
```bash
cd src/precog/database && alembic upgrade head
```

**Step 4 -- Verify schema consistency**
```bash
python scripts/validate_schema_consistency.py
```

**Critical rule:** Never manually edit tables to "fix" a failed migration. Always go through Alembic so the version history stays consistent. If a migration is truly broken, write a corrective migration.

**For test database:** Same process but set `DB_NAME=precog_test` or use:
```bash
python scripts/test_db_connection_test_env.py
```

---

### 3.4 Trading Safety (P1) -- Phase 2 Preparation

**No live trading exists yet.** These runbooks are documented now so they are ready when trade execution is built.

#### 3.4.1 Stale Prices in Edge Calculation

**Risk:** Edge detector uses stale market prices, calculates false edges, triggers bad trades.

**Future mitigation:** Before any trade execution, validate that the market snapshot `row_start_ts` is within an acceptable freshness window (e.g., < 60 seconds). Reject edge if data is stale.

**Relevant tables:**
```sql
-- Check edge data freshness
SELECT e.edge_id, e.expected_value, e.row_start_ts,
       ms.row_start_ts AS snapshot_ts,
       NOW() - ms.row_start_ts AS snapshot_age
FROM edges e
JOIN market_snapshots ms ON e.market_internal_id = ms.market_id AND ms.row_current_ind = TRUE
WHERE e.row_current_ind = TRUE;
```

#### 3.4.2 Wrong Team Matching

**Risk:** ESPN game linked to wrong Kalshi market via team matching error. Edge calculated against wrong game.

**Diagnostic:**
```sql
-- Verify matching integrity (markets → events → games → game_states)
SELECT m.ticker, e.external_id, g.home_team_code, g.away_team_code, g.sport
FROM markets m
JOIN events e ON m.event_internal_id = e.id
JOIN games g ON e.game_id = g.id
WHERE g.game_date > CURRENT_DATE - INTERVAL '7 days'
ORDER BY g.game_date DESC LIMIT 20;
```

**Gap:** Circuit breaker table exists (`circuit_breaker_events`) but has no trigger logic. Breaker entries must be created manually or by the ServiceSupervisor's health check. No automated response to tripped breakers. Future: wire breaker triggers to halt trade execution.

---

## 4. Recovery Verification Checklist

After any incident, verify all of these before considering the incident resolved:

- [ ] All pollers running: `python main.py scheduler status` shows healthy
- [ ] system_health clean: no components in `degraded` or `down` status
- [ ] No active circuit breakers: `circuit_breaker_events WHERE resolved_at IS NULL` returns 0
- [ ] Data flowing: market_snapshots and game_states staleness < 2 minutes
- [ ] SCD integrity: no duplicate `row_current_ind = TRUE` rows
- [ ] No zombie schedulers: `scheduler_status` has no stale `running` entries

---

## 5. Post-Incident

### What to Document

After resolving any P1 or P2, record:

1. **What broke** -- one sentence
2. **Root cause** -- what triggered the failure
3. **Resolution** -- what commands/changes fixed it
4. **Duration** -- time from detection to resolution
5. **Prevention** -- what would catch this earlier next time

Record this as a comment on the relevant GitHub issue, or create a new issue if none exists.

### What to Check Afterward

- Run validation suite: `./scripts/validate_quick.sh`
- Run SCD validation: `python scripts/validate_scd_queries.py`
- Check recent data for gaps (missing poll cycles during outage)
- If a migration was involved: verify both `precog_dev` and `precog_test` are at the same Alembic revision

### Known Gaps Summary

These are documented honestly so the operator knows where automation does not yet exist:

| Gap | Impact | Tracking |
|-----|--------|----------|
| No alerting / notifications | Must notice problems manually | Future: health check endpoint |
| Circuit breakers have no trigger logic | Breakers must be created manually | Issue #390 |
| No data freshness validation in health checks | Stale data not auto-detected | Scorpius C10 finding |
| No connection pool monitoring | Pool exhaustion not detected until failure | Scorpius C10 finding |
| No automated NULL detection on writes | NULL propagation not caught at write time | `feedback_coalesce_null_perpetuation.md` |
| No trade-halt on breaker trip | Breaker table is passive, not enforced | Phase 2 prerequisite |

---

*This is a living document. Update it when new failure modes are discovered or automation closes a gap.*
