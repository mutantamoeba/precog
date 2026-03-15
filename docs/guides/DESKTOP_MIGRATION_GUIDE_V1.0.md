# Desktop Migration Guide V1.0

**Version:** 1.2
**Created:** 2026-03-13
**Status:** Part 1 (Code Fixes) Complete, Part 2 (Migration) Pending
**Issue:** #324
**Council:** C13 Deployment Quorum (7 agents)

---

## Overview

Precog moves from laptop-only development to a **dual-machine setup**:

| Aspect | Laptop (dev) | Desktop (production) |
|--------|-------------|---------------------|
| `PRECOG_ENV` | `dev` | `staging` (promote to `prod` for Phase 2 trading) |
| Database | `precog_dev` | `precog_staging` |
| Credential prefix | `DEV_*` | `STAGING_*` |
| Purpose | Development, testing, experiments | 24/7 data collection |
| Git | Push changes | Pull changes, restart services |
| Services | Run occasionally for testing | Run continuously |

**Phase 1 exit criteria:** 1 week at <1% error rate on desktop.

---

## Part 1: Code Fixes (COMPLETE)

These changes were made before migration:

### 1A. ThreadedConnectionPool (BLOCKER - Fixed)

`SimpleConnectionPool` from psycopg2 is NOT thread-safe. The `ServiceSupervisor` runs
multiple poller threads concurrently, making this a production crash risk.

**Change:** `src/precog/database/connection.py:272`
- `pool.SimpleConnectionPool` -> `pool.ThreadedConnectionPool`
- Updated type annotation for `_connection_pool`
- Fixed docstring (line 17) that falsely claimed `SimpleConnectionPool` was thread-safe

### 1B. TCP Keepalive (BLOCKER - Fixed)

PostgreSQL connections can silently die if network hiccups or firewall timeouts drop the
TCP session. Without keepalives, the pool holds dead connections.

**Change:** Added to pool constructor:
```python
keepalives=1,           # Enable TCP keepalive
keepalives_idle=300,    # Start probing after 5 min idle
keepalives_interval=30, # Probe every 30 seconds
keepalives_count=5,     # Give up after 5 probes (~150s total)
```

### 1C. Dead Code Removal

`service_runner.py` (772 lines) was dead code. The actual production path is:
```
python main.py scheduler start --supervised --foreground
```
This uses `ServiceSupervisor` directly via `cli/scheduler.py`.

**Deleted:**
- `src/precog/runners/service_runner.py` (772 lines)
- 8 test files across unit, integration, e2e, chaos, property, performance, stress, race

**Updated:**
- `src/precog/runners/__init__.py` - removed `DataCollectorService` export
- `CLAUDE.md` - replaced `run-services` commands with `scheduler` commands
- `scripts/audit_test_type_coverage.py` - removed deleted module from audit list
- `tests/security/test_connection_security.py` - updated mocks to `ThreadedConnectionPool`
- `tests/stress/database/test_connection_race.py` - updated docstring reference

**Kept:** `scripts/run_data_collector.py` (standalone production script, separate from deleted code)

### 1D. CLAUDE.md Quick Reference Update

```bash
# Old (dead):
python main.py run-services --start/--status/--stop

# New (actual production path):
python main.py scheduler start --supervised --foreground
python main.py scheduler status
python main.py scheduler stop
```

---

## Part 2: Migration Sequence

### Prerequisites

- PostgreSQL **18.x** on desktop (must match laptop version)
- Python 3.14
- Git + GitHub CLI
- USB drive for data transfer (no cloud/network - security requirement)

### Phase A: Pre-Migration (Laptop)

1. Stop services: `python main.py scheduler stop`
2. Verify clean shutdown
3. Capture SCD integrity baseline:
   ```sql
   -- Row counts per SCD table
   SELECT 'markets' as tbl, COUNT(*) as total, COUNT(*) FILTER (WHERE row_current_ind = TRUE) as current FROM markets
   UNION ALL SELECT 'game_states', COUNT(*), COUNT(*) FILTER (WHERE row_current_ind = TRUE) FROM game_states
   UNION ALL SELECT 'positions', COUNT(*), COUNT(*) FILTER (WHERE row_current_ind = TRUE) FROM positions;

   -- SCD uniqueness (should return 0 rows)
   SELECT ticker_name, COUNT(*) FROM markets WHERE row_current_ind = TRUE GROUP BY ticker_name HAVING COUNT(*) > 1;
   ```
4. Full backup: `pg_dump -U postgres -Fc --verbose -f precog_dev_migration.dump precog_dev 2>&1 | tee pg_dump.log`
5. Verify dump: `pg_restore --list precog_dev_migration.dump | head -20`
6. Transfer dump + `_keys/*.pem` to desktop via **USB drive only**
7. Delete files from USB after copy

### Phase B: Desktop Setup

8. Install Python 3.14, PostgreSQL 18.x, Git, GitHub CLI
9. Configure PostgreSQL:
   - `pg_hba.conf`: **`scram-sha-256` only -- NEVER `trust`**
   - `postgresql.conf`: `listen_addresses = 'localhost'` (verify not `*`)
   - `max_connections >= 30`
   - **New, unique password** (not same as laptop)
10. Windows Firewall: block inbound port 5432
11. Create database: `createdb -U postgres precog_staging`
12. Clone repo, create venv, `pip install -e ".[test]"`
13. Configure `.env`:
    ```
    PRECOG_ENV=staging
    KALSHI_MODE=live
    PRECOG_DANGEROUS_CONFIRMED=yes
    DB_HOST=localhost
    DB_PORT=5432
    DB_USER=postgres
    DB_PASSWORD=<new_desktop_password>
    DB_NAME=precog_staging
    STAGING_KALSHI_API_KEY=<your_api_key>
    STAGING_KALSHI_PRIVATE_KEY_PATH=C:\Users\<user>\repos\precog-repo\_keys\kalshi_private.pem
    ```
    **Use absolute paths** for key file (relative paths break Task Scheduler).

    **Why `KALSHI_MODE=live`?** The Kalshi demo API returns synthetic markets with no real
    sport data — no prices, no volume, no structured tickers. Data collection requires the
    live API. The `staging` environment prevents accidental trades at the application level.
    `PRECOG_DANGEROUS_CONFIRMED=yes` acknowledges the staging+live combination. See Issue #355.
14. Set NTFS ACLs:
    ```cmd
    icacls .env /inheritance:r /grant:r "%USERNAME%:F"
    icacls _keys /inheritance:r /grant:r "%USERNAME%:F"
    ```
15. Test DB connection: `python scripts/test_db_connection.py`

### Phase C: Data Migration

16. Restore: `pg_restore -U postgres -d precog_staging --no-owner --no-privileges --verbose precog_dev_migration.dump 2>&1 | tee pg_restore.log`
17. Post-restore verification:
    - SCD uniqueness (no duplicate current rows per entity)
    - SCD consistency (current rows have NULL `row_end_ts`)
    - Row counts match laptop baseline
    - DECIMAL precision (numeric_precision=10, numeric_scale=4)
    - Partial indexes survived
    - ENUM types survived
    - `alembic_version` shows `0017`
18. Clean stale scheduler_status: `DELETE FROM scheduler_status;`
19. Pre-0018 backup: `pg_dump -U postgres -Fc -f precog_staging_pre_0018.dump precog_staging`
20. Apply migration: `cd src/precog/database && alembic upgrade head`
21. Verify 0018 applied
22. Configure autovacuum:
    ```sql
    ALTER TABLE game_states SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02);
    ALTER TABLE markets SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02);
    ```

### Phase D: Service Validation

23. Run post-migration tests:
    ```bash
    python -m pytest tests/e2e/config/ -v
    python -m pytest tests/e2e/database/ -v
    python scripts/test_db_connection.py
    python -m pytest tests/integration/schedulers/ -v
    ```
24. Single poll test: `python main.py scheduler poll-once`
25. Start supervised: `python main.py scheduler start --supervised --foreground`
26. Watch 10 minutes for zero errors
27. Verify data writes + SCD integrity after first polls

### Phase E: Production Hardening

28. Windows power settings: sleep=Never, hibernate=Never
29. Windows Defender exclusions: Python executable, precog-repo dir, logs dir, PostgreSQL data dir
30. Verify NTP enabled (Kalshi auth timestamps depend on clock accuracy)
31. Create backup script (`~/.precog/backup_precog.bat`):
    - `pg_dump -Fc` to `~/.precog/backups/`
    - `pg_restore --list` verification
    - 7-day retention auto-cleanup
32. Register backup in Task Scheduler (daily 3 AM)
33. Create startup script (`~/.precog/start_precog.bat`):
    - `cd /d C:\Users\<user>\repos\precog-repo` (explicit CWD)
    - Activate venv, start supervised services
34. Register auto-start in Task Scheduler (on boot, 30s delay, restart on failure)
35. Watchdog task: every 5 minutes, check if service is running, restart if dead
36. Verify PostgreSQL auto-starts on boot
37. Screen lock after 5 min inactivity
38. Test reboot survival

### Phase F: Post-Migration Validation

39. 1-hour check: services running, data growing, zero errors, SCD integrity
40. Begin 1-week monitoring for Phase 1 exit criteria

---

## Deploying New Code to Desktop

### Standard Code Update (No Schema Changes)

```bash
# On desktop:
cd C:\Users\<user>\repos\precog-repo
python main.py scheduler stop
git pull origin main
pip install -e .  # if deps changed
python main.py scheduler start --supervised --foreground
```

### Code Update WITH Schema Changes

When `git pull` includes new Alembic migrations (files in `src/precog/database/alembic/versions/`):

```bash
# 1. Stop services
python main.py scheduler stop

# 2. Pull code
git pull origin main
pip install -e .

# 3. Check what migrations are pending
cd src/precog/database
alembic current           # Shows current DB version
alembic heads             # Shows latest migration in code
alembic history --verbose # Full migration history

# 4. Preview migration SQL (dry-run)
alembic upgrade head --sql   # Shows SQL without applying

# 5. Backup BEFORE applying
pg_dump -U postgres -Fc -f "$HOME/.precog/backups/pre_migration_$(date +%Y%m%d_%H%M%S).dump" precog_staging

# 6. Apply migrations
alembic upgrade head

# 7. Verify
alembic current            # Should match alembic heads
cd ../../..
python main.py db status   # Critical tables check
python main.py db tables --verbose  # Row counts + sizes

# 8. Restart services
python main.py scheduler start --supervised --foreground
```

### How to Detect Schema Changes in a Pull

```bash
# After git pull, check if migrations changed:
git diff HEAD~1 --name-only -- src/precog/database/alembic/versions/
# If any files listed -> schema change, follow "WITH Schema Changes" workflow
```

### Keeping Dev and Production in Sync

Both machines should always be on the same Alembic head. To verify:

```bash
# On either machine:
cd src/precog/database
alembic current   # Shows: <revision_id> (head)
```

If desktop is behind:
```bash
# On desktop: pull code, then upgrade
git pull origin main
cd src/precog/database
alembic upgrade head
```

If you need to check without a database connection:
```bash
# Compare latest migration file in repo vs what's applied
ls -t src/precog/database/alembic/versions/*.py | head -1  # Latest in code
```

### Rollback a Migration

```bash
# Downgrade by one step:
cd src/precog/database
alembic downgrade -1

# Downgrade to specific revision:
alembic downgrade <revision_id>

# CAUTION: Downgrades may fail if data depends on new schema.
# Always backup before upgrading, and test downgrades in dev first.
```

---

## Backup & Rollback

### Automated Daily Backups

- **Schedule:** `pg_dump -Fc` at 3 AM via Task Scheduler, 7-day retention
- **Pre-migration:** Manual backup before any `alembic upgrade`
- **Rollback options:**
  1. Restore from `~/.precog/backups/` (full data recovery)
  2. `alembic downgrade -1` (schema-only rollback, may lose data in dropped columns)
  3. Restart laptop services as fallback (data gap = downtime duration)
- **Storage estimate:** ~600MB month 1, ~6GB year 1

### Manual Backup

```bash
# Full backup with timestamp
pg_dump -U postgres -Fc --verbose -f "$HOME/.precog/backups/precog_staging_$(date +%Y%m%d_%H%M%S).dump" precog_staging

# Verify backup integrity
pg_restore --list "$HOME/.precog/backups/precog_staging_<timestamp>.dump" | head -20

# Restore from backup (DESTRUCTIVE - drops existing data)
dropdb -U postgres precog_staging
createdb -U postgres precog_staging
pg_restore -U postgres -d precog_staging --no-owner --no-privileges "$HOME/.precog/backups/precog_staging_<timestamp>.dump"
```

---

## Monitoring & Maintenance

### Daily Operator Check-In

1. `python main.py scheduler status --verbose` -- per-service health + heartbeat freshness
2. Check log file for `ERROR`: `Get-Content ~/.precog/logs/precog.log -Tail 50 | Select-String "ERROR"`
3. Spot-check data freshness:
   ```sql
   -- Most recent data per table
   SELECT 'markets' as tbl, MAX(row_start_ts) as latest FROM markets
   UNION ALL SELECT 'game_states', MAX(row_start_ts) FROM game_states;

   -- SCD integrity (should return 0)
   SELECT COUNT(*) as duplicate_current_rows
   FROM markets WHERE row_current_ind = TRUE
   GROUP BY ticker_name HAVING COUNT(*) > 1;
   ```
4. Check disk space: `Get-PSDrive C | Select-Object Used, Free`

### Weekly Maintenance

1. **Database health:**
   ```sql
   -- Table sizes (watch for runaway growth)
   SELECT relname as table, pg_size_pretty(pg_total_relation_size(relid))
   FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;

   -- Dead tuple ratio (should be <10% for SCD tables)
   SELECT relname, n_live_tup, n_dead_tup,
          ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 1) as dead_pct
   FROM pg_stat_user_tables
   WHERE n_live_tup > 0
   ORDER BY n_dead_tup DESC;

   -- Check autovacuum is running
   SELECT relname, last_vacuum, last_autovacuum, last_analyze
   FROM pg_stat_user_tables WHERE schemaname = 'public'
   ORDER BY last_autovacuum DESC NULLS LAST;
   ```

2. **Log rotation:** Ensure log files aren't growing unbounded
3. **Backup verification:** Restore a recent backup to test DB to verify integrity
4. **Git status:** Verify desktop is on `main` and up to date: `git log --oneline -3`

### Error Rate Monitoring

Once validation alerting is wired (#386):
```sql
-- Recent alerts (if alerts table is populated)
SELECT alert_type, severity, message, created_at
FROM alerts
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

### Performance Monitoring

```sql
-- Slow queries (if pg_stat_statements enabled)
-- In postgresql.conf: shared_preload_libraries = 'pg_stat_statements'
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = 'precog_staging')
ORDER BY total_exec_time DESC LIMIT 10;

-- Connection pool usage
SELECT count(*) as active_connections, state
FROM pg_stat_activity
WHERE datname = 'precog_staging'
GROUP BY state;

-- Index usage (unused indexes waste space)
SELECT relname as table, indexrelname as index, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
```

### PostgreSQL Configuration Tuning

For a desktop with 32GB+ RAM running Precog as primary workload:

```ini
# postgresql.conf recommended settings
shared_buffers = 4GB              # 25% of RAM
effective_cache_size = 12GB       # 75% of RAM
maintenance_work_mem = 1GB        # For VACUUM, CREATE INDEX
work_mem = 256MB                  # Per-query sort/hash
wal_buffers = 64MB
max_connections = 30              # Precog uses ~5-10
checkpoint_completion_target = 0.9
random_page_cost = 1.1            # SSD (default 4.0 is for HDD)
effective_io_concurrency = 200    # SSD
```

After changing `postgresql.conf`, restart PostgreSQL:
```powershell
Restart-Service postgresql-x64-18
```

---

## First-Week Follow-Up Items

| Item | Source Agent | Priority |
|------|-------------|----------|
| Fix logging handler accumulation | Marvin | Medium |
| Human-readable uptime + timestamps | Uhura | Low |
| Connection pool health check / reconnection | Vader + Marvin | Medium |
| Close ESPN session on stop | Marvin | Low |
| Credential rotation (separate staging keys) | Glokta | Medium |

## Before Phase 2

| Item | Source Agent | Priority |
|------|-------------|----------|
| SCD archival / partitioning strategy | Holden + Marvin | High |
| `precog health` single check-in command | Uhura | Medium |
| Passphrase-encrypt Kalshi RSA key | Glokta | Medium |

---

## Remote Development Setup

The desktop is where data, GPU, and production services live. The laptop is for writing
code. Set up remote access so you can run training jobs and monitor services from the laptop.

### SSH Server (Windows OpenSSH)

1. Install OpenSSH Server:
   ```powershell
   # Run as Administrator
   Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
   ```
2. Start and enable the service:
   ```powershell
   Start-Service sshd
   Set-Service -Name sshd -StartupType Automatic
   ```
3. Windows Firewall will auto-create a rule for port 22. Verify:
   ```powershell
   Get-NetFirewallRule -Name *ssh*
   ```
4. Test from laptop:
   ```bash
   ssh <user>@<desktop-ip>
   ```
5. Set up SSH key auth (optional but recommended):
   ```bash
   # On laptop:
   ssh-copy-id <user>@<desktop-ip>
   ```

### VS Code Remote-SSH

1. Install "Remote - SSH" extension in VS Code on the laptop
2. Add SSH host: `Ctrl+Shift+P` → "Remote-SSH: Add New SSH Host"
   ```
   ssh <user>@<desktop-ip>
   ```
3. Connect: `Ctrl+Shift+P` → "Remote-SSH: Connect to Host"
4. Open the precog-repo folder on the desktop — full IDE experience, execution on desktop

### PostgreSQL Remote Access (Read-Only, for Laptop)

If you need to query production data from the laptop for debugging:

1. On desktop, create a read-only database user:
   ```sql
   CREATE USER precog_reader WITH PASSWORD '<reader_password>';
   GRANT CONNECT ON DATABASE precog_staging TO precog_reader;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO precog_reader;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO precog_reader;
   ```
2. Update `postgresql.conf`:
   ```
   listen_addresses = 'localhost, <desktop-ip>'
   ```
3. Add to `pg_hba.conf` (laptop IP only, scram-sha-256):
   ```
   host  precog_staging  precog_reader  <laptop-ip>/32  scram-sha-256
   ```
4. Restart PostgreSQL and verify from laptop:
   ```bash
   psql -h <desktop-ip> -U precog_reader -d precog_staging
   ```

**Security notes:**
- Read-only user cannot modify production data even if compromised
- Restrict `pg_hba.conf` to laptop's specific IP, not a subnet
- Consider SSH tunnel instead of direct access for additional encryption:
  ```bash
  ssh -L 5433:localhost:5432 <user>@<desktop-ip>
  psql -h localhost -p 5433 -U precog_reader -d precog_staging
  ```

---

## GPU Setup for Model Training

The desktop has an AMD Radeon RX 7900 XT — all model training and backtesting runs here,
co-located with the production database (no data transfer needed).

### ROCm + PyTorch Installation

1. Install AMD ROCm drivers for Windows (or use WSL2 with Linux ROCm for better ML stability):
   - Download from [AMD ROCm](https://rocm.docs.amd.com/)
   - Verify: `rocminfo` should list the 7900 XT
2. Install PyTorch with ROCm backend:
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.2
   ```
3. Verify GPU access:
   ```python
   import torch
   print(torch.cuda.is_available())       # True (ROCm uses CUDA compatibility layer)
   print(torch.cuda.get_device_name(0))   # AMD Radeon RX 7900 XT
   ```

### Development Workflow

| Activity | Machine | Method |
|----------|---------|--------|
| Write model/strategy code | Laptop | IDE, push to GitHub |
| Run unit tests | Laptop | `pytest tests/unit/` |
| Pull code + train model | Desktop | `git pull` then training script (GPU + data co-located) |
| Run backtests | Desktop | Needs historical SCD data + GPU compute |
| Evaluate model performance | Desktop | Reads from production database directly |
| Monitor training jobs remotely | Laptop | SSH or VS Code Remote-SSH |

### Training Data Access

Models train directly against the production database — no data export or replication needed.
The training code connects to `precog_staging` (or `precog_prod` after promotion) on localhost.
This eliminates data staleness and transfer overhead.

---

## Version History

| Version | Date | Summary |
|---------|------|---------|
| 1.2 | 2026-03-15 | Added: schema migration sync workflow, migration detection, rollback procedures, comprehensive monitoring (daily/weekly/performance), PostgreSQL tuning for desktop. |
| 1.1 | 2026-03-13 | Added: GPU/ROCm setup, remote dev (SSH, VS Code), read-only DB access. Fixed: KALSHI_MODE=live (demo API unusable for data, #355). |
| 1.0 | 2026-03-13 | Initial creation. Part 1 code fixes complete. |
