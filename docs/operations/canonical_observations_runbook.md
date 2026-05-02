# Canonical Observations Operator Runbook

**Component:** `canonical_observations_writer`
**Database table:** `canonical_observations` (partitioned parent, slot 0078)
**Cohort:** 4 (ADR-118 V2.43)
**Status:** Skeleton — feature flag `features.canonical_observations_writer.enabled` defaults to `false` until session 87 soak window opens.

---

## 1. Service overview

The canonical_observations writer is the canonical-tier ingest service for cross-domain observations. Every observation in the system — game state from ESPN, market snapshot from Kalshi, weather from NOAA in future cohorts, econ prints, news events, polls — eventually lands as one row in the `canonical_observations` partitioned parent table via the writer's restricted CRUD path (`crud_canonical_observations.append_observation_row()`).

**What slot 0078 ships:** the writer skeleton + the partitioned parent table + 4 monthly partitions (2026-05 through 2026-08) + 5 indexes + dedup UNIQUE + 3 CHECK constraints + BEFORE UPDATE trigger.

**What is NOT yet wired:** the source-observation read path. Cohort 5+ materializes that pipeline (Kalshi → canonical observation rows; ESPN → canonical observation rows; future weather feeds → canonical observation rows). Slot 0078 ships the destination + the registration shell; the source reads light up later.

**What reads from `canonical_observations`:**
- Cohort 4: nothing yet. The reconciler module (Cohort 4 separate slot/PR after writer soak per V2.43 micro-delta MD1) will be the first reader.
- Cohort 5+: per-kind projection tables (`weather_observations`, `poll_releases`, `econ_prints`, `news_events`, etc.) FK INTO `canonical_observations` via composite-FK shape `(canonical_observation_id, observation_ingested_at)`.

---

## 2. Health-check signals — `system_health` for `component='canonical_observations_writer'`

The writer registers with ServiceSupervisor at startup; its heartbeat lands one row in `system_health` keyed by component name. Read via:

```sql
SELECT component, status, details, last_check, alert_sent
FROM system_health
WHERE component = 'canonical_observations_writer'
ORDER BY last_check DESC
LIMIT 1;
```

**Status values** (per ServiceSupervisor `_determine_health()`):
- `healthy`: writer is running, error rate <5%, polls fresh.
- `degraded`: error rate 5-25% OR last poll > 2x interval.
- `down`: error rate >25% OR no poll for >5x interval.

**Cohort 4 baseline** (skeleton-only, feature flag disabled):
- The writer is NOT registered when feature flag is `false` — `system_health` will have NO row for `canonical_observations_writer` at slot-0078 deploy time. This is intentional: enabling the flag is the sole path to creating the heartbeat row.

**Cohort 4 native metrics on `scheduler_status.stats` JSONB** (build spec § 7):
- `canonical_observations_ingest_lag_seconds` (p50/p95/p99 + last-value gauge): writer-side per-row measurement, aggregated per heartbeat. Cohort 4 baseline established during session 87+ soak.
- Other metrics (`reconciliation_anomaly_count`, `temporal_alignment_query_latency_p99`) ship with their respective components in later slots.

```sql
SELECT host_id, status, started_at, stats, last_heartbeat
FROM scheduler_status
WHERE service_name = 'canonical_observations_writer'
ORDER BY last_heartbeat DESC;
```

---

## 3. Feature-flag toggle — `features.canonical_observations_writer.enabled`

**Default:** `false` at slot-0078 deploy time.

**Activation procedure** (session 87 soak window opening, or any future operator-driven enablement):

1. **Pre-flight check:** verify the writer's CRUD path is wired correctly by running the unit + integration test suites locally:
   ```powershell
   python -m pytest tests/unit/database/test_crud_canonical_observations_unit.py -v
   python -m pytest tests/integration/database/test_migration_0078_canonical_observations.py -v
   ```
   Both suites MUST pass before flipping the flag.

2. **Verify partition coverage:** the writer's `ingested_at` lands in whichever partition currently covers `now()`. Run:
   ```sql
   SELECT inhrelid::regclass AS partition_name,
          pg_get_expr(relpartbound, inhrelid) AS bounds
   FROM pg_inherits
   JOIN pg_class ON pg_class.oid = pg_inherits.inhrelid
   WHERE pg_inherits.inhparent = 'canonical_observations'::regclass
   ORDER BY partition_name;
   ```
   Confirm the partition covering today's date exists. If the latest partition expires within 7 days, run the partition-addition runbook (§ 4) FIRST.

3. **Enable the flag** in the active environment's `system.yaml`:
   ```yaml
   features:
     canonical_observations_writer:
       enabled: true
   ```

4. **Restart the supervisor** so the registration takes effect:
   ```powershell
   python main.py scheduler stop
   python main.py scheduler start --supervised --foreground
   ```

5. **Verify the writer is healthy** within 2 minutes (one heartbeat cycle):
   ```sql
   SELECT * FROM system_health WHERE component = 'canonical_observations_writer';
   ```
   Expected: one row with `status='healthy'` and `last_check` within the past 2 minutes.

**Safety considerations:**

- **Cohort 4 skeleton is no-op.** Activating the flag at slot-0078 deploy time produces heartbeat rows but zero observation rows in `canonical_observations` — the source-observation read path is Cohort 5+ work. This is the EXPECTED Cohort 4 baseline. Do not file bugs against zero-observation cycles.
- **Partition gap is a hard fail.** If the writer attempts to append a row whose `ingested_at` falls outside any pre-created partition, PG raises `no partition of relation "canonical_observations" found for row` and the INSERT fails. The writer logs + skips + emits a metric; downstream alert surfaces. The fix is to add the missing partition (§ 4).
- **Disabling the flag** is safe at any time: stop the supervisor, set `enabled: false`, restart. Existing observation rows persist (the table is not deleted); only the writer's heartbeat stops.

---

## 4. Partition addition runbook — when and how

**When to add the next month's partition:** ~7 days before the latest existing partition expires.

**Slot 0078 baseline coverage:** 2026-05-01 through 2026-09-01 (4 partitions: `canonical_observations_2026_05` / `_06` / `_07` / `_08`).

**Idempotent partition-creation template:**

```sql
-- Replace YYYY_MM with the target month and the bounds with month start/end.
-- Run during a low-traffic window if the writer is enabled (the CREATE TABLE
-- acquires AccessExclusiveLock on the parent for the duration of metadata
-- catalog updates — sub-second on empty parent table; bounded on populated).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class
        WHERE relname = 'canonical_observations_2026_09'
    ) THEN
        EXECUTE 'CREATE TABLE canonical_observations_2026_09 '
                'PARTITION OF canonical_observations '
                'FOR VALUES FROM (''2026-09-01'') TO (''2026-10-01'')';
    END IF;
END $$;
```

The `IF NOT EXISTS` guard makes the script idempotent — re-running on a database where the partition already exists is a no-op. This is intentional: the partition addition is operational, not a migration; multiple operators running the script should converge on the same state without crashes.

**Verification after partition addition:**

```sql
SELECT inhrelid::regclass AS partition_name,
       pg_get_expr(relpartbound, inhrelid) AS bounds
FROM pg_inherits
JOIN pg_class ON pg_class.oid = pg_inherits.inhrelid
WHERE pg_inherits.inhparent = 'canonical_observations'::regclass
ORDER BY partition_name;
```

Expected: the new partition row alongside the existing baseline set.

**Indexes propagate automatically.** PG12+ propagates parent-level indexes to new partitions on CREATE TABLE PARTITION OF. No additional CREATE INDEX statements are required.

---

## 5. Dedup-violation triage — `UniqueViolation` on `(source_id, payload_hash, ingested_at)`

The writer's `append_observation_row()` raises `psycopg2.errors.UniqueViolation` when the dedup UNIQUE fires. The constraint name is `uq_canonical_observations_dedup`.

**Common causes:**

1. **Source double-publication.** A source feed re-publishes the same payload within the same ingest tick (typically a retry-without-idempotency on the source side). The dedup is the correctness contract: the duplicate is rejected; the original row remains.
2. **Writer retry without offset advance.** If the writer crashes mid-cycle and restarts without advancing its source-side offset, it re-reads the same payload. Dedup catches it. The fix is to verify the writer's offset-tracking logic is durable.
3. **Test-fixture collision.** Tests using fixed `source_published_at` + `payload` combinations will collide if run twice within the same partition window without cleanup. Test-side fix: ensure each test's payload is unique (typically via a UUID suffix).

**Investigation query:**

```sql
SELECT id, ingested_at, source_id, payload_hash, payload, source_published_at
FROM canonical_observations
WHERE source_id = $1
  AND payload_hash = $2
ORDER BY ingested_at DESC
LIMIT 5;
```

If the duplicate is operationally legitimate (e.g., source genuinely intended to re-publish the observation as an update), the canonical fix is to mutate the payload (add a sequence number, a publication timestamp, etc.) so the second publication has a distinct `payload_hash`. **Never bypass the dedup UNIQUE** — the table is append-only, and silent overwrites would corrupt the audit trail.

---

## 6. Cross-environment parity check

Dev / test / prod databases MUST have aligned partition sets. Drift between environments produces "writer works locally but fails in prod" surprises.

**Parity check query** (run against each environment, compare results):

```sql
SELECT inhrelid::regclass::text AS partition_name,
       pg_get_expr(relpartbound, inhrelid) AS bounds
FROM pg_inherits
JOIN pg_class ON pg_class.oid = pg_inherits.inhrelid
WHERE pg_inherits.inhparent = 'canonical_observations'::regclass
ORDER BY partition_name;
```

**Expected (slot 0078 baseline):**

```
canonical_observations_2026_05  | FOR VALUES FROM ('2026-05-01 00:00:00+00') TO ('2026-06-01 00:00:00+00')
canonical_observations_2026_06  | FOR VALUES FROM ('2026-06-01 00:00:00+00') TO ('2026-07-01 00:00:00+00')
canonical_observations_2026_07  | FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00')
canonical_observations_2026_08  | FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00')
```

If environments differ post-baseline, the operator who added the partition in environment X must replicate the addition to environments Y and Z via the partition-addition runbook (§ 4).

**Index parity check:**

```sql
SELECT indexname FROM pg_indexes
WHERE tablename = 'canonical_observations'
ORDER BY indexname;
```

Expected (slot 0078 baseline): 5 indexes —
- `idx_canonical_observations_currently_valid`
- `idx_canonical_observations_event_id`
- `idx_canonical_observations_event_occurred`
- `idx_canonical_observations_kind_ingested`
- `idx_canonical_observations_source_published`

Plus the parent's primary-key index `canonical_observations_pkey` and the dedup UNIQUE index `uq_canonical_observations_dedup`.

---

## 7. Reconciler runbook — TODO

**Status:** TODO until the Cohort 4 reconciler module ships (separate slot/PR after writer soak per V2.43 micro-delta MD1).

The reconciler will compare canonical observations against per-kind projection tables (when those land in Cohort 9+) and the source-of-truth feeds. Outcomes are tagged with `RECONCILIATION_OUTCOME_VALUES` (`match` / `drift` / `mismatch` / `missing_dim` / `missing_fact` / `ambiguous`); anomaly counts ride `system_health.details` JSONB until a typed `canonical_reconciliation_results` table lands (Cohort 5+, V2.43 Item 4).

**Forward-pointer:** when the reconciler ships, this section will document:
- How to invoke the manual-CLI (`python -m precog.canonical reconcile`) for ad-hoc checks.
- How to read the `reconciliation_anomaly_count` metric from `system_health.details`.
- How to triage each `RECONCILIATION_OUTCOME_VALUES` value.

---

## 8. Backfill runbook — TODO

**Status:** TODO until Cohort 5+ historical backfill design.

Cohort 4 ships current-only ingestion (`row_current_ind=true` style — only fresh source publications land in `canonical_observations`). Historical backfill (re-canonicalizing past Kalshi / ESPN data into the canonical-tier observation parent) is Cohort 5+ scope.

**Forward-pointer:** when the backfill design lands, this section will document:
- Source-of-truth identification (which Kalshi / ESPN snapshots get canonicalized).
- Partition-coverage extension (backfill spans many months; partitions must exist for every covered month).
- Throughput limits (ingest rate during backfill MUST NOT crowd out live writer cycles).

---

## 9. Per-kind-projection consumer-onboarding runbook — TODO

**Status:** TODO per consumer.

Cohort 9+ per-kind projections (`weather_observations`, `poll_releases`, `econ_prints`, `news_events`, etc.) FK INTO `canonical_observations` via composite-FK shape `(canonical_observation_id, observation_ingested_at)`. Each new consumer's onboarding is its own runbook section.

**Forward-pointer:** when the first per-kind projection ships, this section will document:
- Composite-FK invariant (V2.43 Item 3) — surrogate `id` alone is INSUFFICIENT; the partition key MUST appear in the FK.
- Consumer-side dedup checking (does the consumer write per-kind rows idempotently?).
- Consumer-side replay handling (if `canonical_observations` row's `valid_until` shifts, does the projection follow?).

---

## 10. Partition-rotation runbook — TODO

**Status:** TODO when partition retention policy is set (Cohort 6+ when storage measurements exist).

Cohort 4 keeps all partitions indefinitely. When storage growth justifies a retention policy (likely Cohort 6+), this section will document:
- How to drop expired partitions.
- How to archive expired-partition contents (e.g., to a separate analytics warehouse).
- How to verify the writer's `ingested_at` does not target an archived partition window.

---

## 11. Disaster-recovery runbook — TODO

**Status:** TODO; cross-references future MVP backup/restore drill (Epic #1071 #1066).

When the cross-cohort backup/restore drill lands, this section will document:
- How to back up the `canonical_observations` parent + partitions.
- How to restore from backup (composite-FK invariant must survive the restore).
- How to verify post-restore partition routing still works (a quick INSERT + SELECT round-trip suffices).

---

## References

- **Migration:** `src/precog/database/alembic/versions/0078_canonical_observations.py`
- **CRUD module:** `src/precog/database/crud_canonical_observations.py`
- **Writer skeleton:** `src/precog/schedulers/canonical_observations_writer.py`
- **Constants (Pattern 73 SSOT):** `src/precog/database/constants.py` — `OBSERVATION_KIND_VALUES` + `PARTITION_STRATEGY_VALUES` + `RECONCILIATION_OUTCOME_VALUES`
- **Build spec:** `memory/build_spec_0078_pm_memo.md`
- **S82 inherited memo:** `memory/s82_slot_0078_inherited_memo.md`
- **Cohort 4 council synthesis:** `memory/design_review_cohort4_synthesis.md`
- **ADR:** ADR-118 V2.43 Cohort 4 (`docs/foundation/ARCHITECTURE_DECISIONS.md`)
- **Epic:** #972 (Canonical Layer Foundation — Phase B.5)
