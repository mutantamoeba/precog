# Desktop Deployment Guide V2.0

**Version:** 2.0
**Created:** 2026-04-05
**Replaces:** DESKTOP_MIGRATION_GUIDE_V1.0.md (data migration approach, now obsolete)
**Phase:** Phase 1 Completion (environment validation)

---

## Overview

Deploy Precog on a desktop PC for 24/7 data collection. This is a **clean install** — no data migration needed. The database starts fresh with `alembic upgrade head`.

| Aspect | Laptop (dev) | Desktop (production) |
|--------|-------------|---------------------|
| `PRECOG_ENV` | `dev` | `staging` (promote to `prod` for Phase 2) |
| Database | `precog_dev` | `precog_staging` |
| Credential prefix | `DEV_*` | `STAGING_*` |
| Purpose | Development, testing | 24/7 data collection |
| Git workflow | Push changes | Pull changes, restart services |

**Phase 1 exit criteria:** Desktop collecting data 24/7 for 1 week with <1% error rate.

---

## Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Windows 11 | Any | AMD Radeon 7900XT desktop |
| Python | 3.14 | `python --version` to verify |
| PostgreSQL | 15+ | Match laptop version |
| Git | Latest | + GitHub CLI (`gh`) |
| Kalshi API key | Live | Demo API returns synthetic data — useless for collection |
| Kalshi RSA key | PEM file | `_keys/kalshi_private.pem` |

---

## Step 1: Install & Configure PostgreSQL

```powershell
# After PostgreSQL installer finishes:

# Verify installation
psql -U postgres -c "SELECT version();"

# Create database
createdb -U postgres precog_staging
```

**Security hardening (MANDATORY):**

1. Edit `pg_hba.conf`:
   - Set all local connections to `scram-sha-256` (NEVER `trust`)

2. Edit `postgresql.conf`:
   ```
   listen_addresses = 'localhost'    # NOT '*'
   max_connections = 30
   ```

3. Windows Firewall: Block inbound port 5432
   ```powershell
   New-NetFirewallRule -DisplayName "Block PostgreSQL External" -Direction Inbound -LocalPort 5432 -Protocol TCP -Action Block
   ```

4. Set a **new, unique password** (not same as laptop)

5. Configure autovacuum for high-write SCD tables:
   ```sql
   -- Run after database exists and tables are created (Step 4)
   ALTER TABLE game_states SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02);
   ALTER TABLE market_snapshots SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02);
   ```

---

## Step 2: Clone & Install Precog

```powershell
cd C:\Users\<user>\repos
git clone https://github.com/mutantamoeba/precog.git precog-repo
cd precog-repo

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install with all dependencies
pip install -e ".[test]"
```

---

## Step 3: Configure Environment

Create `.env` in the repo root:

```env
# Environment
PRECOG_ENV=staging
KALSHI_MODE=live
PRECOG_DANGEROUS_CONFIRMED=yes

# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=<your_desktop_password>
DB_NAME=precog_staging

# Kalshi API (staging prefix)
STAGING_KALSHI_API_KEY=<your_api_key>
STAGING_KALSHI_PRIVATE_KEY_PATH=C:\Users\<user>\repos\precog-repo\_keys\kalshi_private.pem
```

**Important notes:**
- Use **absolute paths** for key file (relative paths break Task Scheduler)
- `KALSHI_MODE=live` is required — demo API returns synthetic markets with no real sport data
- `staging` environment prevents accidental trades at the application level
- `PRECOG_DANGEROUS_CONFIRMED=yes` acknowledges the staging+live combination

**Copy Kalshi credentials:**
- Copy `_keys/kalshi_private.pem` from laptop via USB drive (not cloud/network)
- Delete from USB after copy

**Lock down file permissions:**
```powershell
icacls .env /inheritance:r /grant:r "%USERNAME%:F"
icacls _keys /inheritance:r /grant:r "%USERNAME%:F"
```

---

## Step 4: Initialize Database

```powershell
# Test connection
python scripts/test_db_connection.py

# Apply all migrations (47 migrations, creates 42 tables + 8 views)
cd src/precog/database
alembic upgrade head

# Verify
alembic current
# Should show: 0048 (head)
```

**Seed initial data:**
```powershell
# Seed teams, classifications, external codes
python main.py db seed --all
```

**Configure autovacuum** (from Step 1, now that tables exist):
```sql
psql -U postgres -d precog_staging -c "
ALTER TABLE game_states SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02);
ALTER TABLE market_snapshots SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02);
"
```

---

## Step 5: Verify Setup

```powershell
# Run quick validation
python -m pytest tests/unit/ -q --no-cov -x

# Test Kalshi API connectivity
python main.py kalshi status

# Test ESPN API connectivity
python main.py espn games --league nba
```

All three should succeed before proceeding.

---

## Step 6: Start Services

```powershell
# Start supervised pollers (foreground for initial verification)
python main.py scheduler start --supervised --foreground
```

**Expected output:**
- Kalshi poller starts, fetches market snapshots
- ESPN poller starts, fetches game states for active leagues
- Service supervisor monitors health, auto-restarts on failure

**Monitor for 15-30 minutes:**
```powershell
# In a separate terminal
python main.py scheduler status
```

Verify:
- Both pollers show `running` status
- No error rate > 1%
- Market snapshots and game states being created

---

## Step 7: Configure Background Service

For 24/7 operation, use Windows Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task: "Precog Data Collection"
3. Trigger: "At startup"
4. Action: Start a Program
   - Program: `C:\Users\<user>\repos\precog-repo\.venv\Scripts\python.exe`
   - Arguments: `main.py scheduler start --supervised --foreground`
   - Start in: `C:\Users\<user>\repos\precog-repo`
5. Properties:
   - Run whether user is logged on or not
   - Run with highest privileges
   - Do not stop if running longer than 3 days

**Alternative: nssm (Non-Sucking Service Manager)**
```powershell
nssm install PrecogCollector "C:\Users\<user>\repos\precog-repo\.venv\Scripts\python.exe" "main.py scheduler start --supervised --foreground"
nssm set PrecogCollector AppDirectory "C:\Users\<user>\repos\precog-repo"
nssm start PrecogCollector
```

---

## Step 8: Validate (1 Week)

Phase 1 exit criteria: 24/7 collection for 1 week with <1% error rate.

**Daily checks:**
```powershell
# Service status
python main.py scheduler status

# Quick DB health
python main.py db health

# Data growth
psql -U postgres -d precog_staging -c "
SELECT 'market_snapshots' as tbl, COUNT(*) FROM market_snapshots
UNION ALL SELECT 'game_states', COUNT(*) FROM game_states
UNION ALL SELECT 'game_odds', COUNT(*) FROM game_odds;
"
```

**After 1 week:**
```sql
-- Error rate check
SELECT component, status, COUNT(*)
FROM system_health
GROUP BY component, status;

-- SCD integrity (should return 0 rows)
SELECT espn_event_id, COUNT(*)
FROM game_states
WHERE row_current_ind = TRUE
GROUP BY espn_event_id
HAVING COUNT(*) > 1;
```

---

## Updating (Pull & Restart)

When changes are merged to main:

```powershell
# Stop services
python main.py scheduler stop

# Pull latest
git pull origin main

# Apply any new migrations
cd src/precog/database && alembic upgrade head && cd ../../..

# Restart
python main.py scheduler start --supervised --foreground
```

---

## Backup & Restore

### Scheduled Backups (Desktop)

Set up a daily backup via Task Scheduler:

```powershell
# Daily backup script — save as C:\Users\<user>\scripts\precog_backup.ps1
$date = Get-Date -Format "yyyy-MM-dd"
$backupDir = "C:\Users\<user>\backups\precog"
$backupFile = "$backupDir\precog_staging_$date.dump"

# Create backup directory if needed
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

# Custom-format dump (compressed, restorable)
pg_dump -U postgres -Fc --verbose -f $backupFile precog_staging 2>&1 | Tee-Object "$backupDir\backup_$date.log"

# Verify dump is valid
pg_restore --list $backupFile | Select-Object -First 5

# Retain last 14 days of backups
Get-ChildItem $backupDir -Filter "precog_staging_*.dump" | Sort-Object CreationTime | Select-Object -SkipLast 14 | Remove-Item -Force

Write-Host "Backup complete: $backupFile ($('{0:N1}' -f ((Get-Item $backupFile).Length / 1MB)) MB)"
```

Schedule in Task Scheduler: daily at 04:00 AM, run whether logged in or not.

### Restore from Backup

Restoring to the **same machine** (e.g., after corruption):

```powershell
# Stop services first
python main.py scheduler stop

# Drop and recreate database
dropdb -U postgres precog_staging
createdb -U postgres precog_staging

# Restore
pg_restore -U postgres -d precog_staging --no-owner --no-privileges --verbose <backup_file>.dump

# Verify migration level
cd src/precog/database && alembic current && cd ../../..

# Clear stale scheduler state
psql -U postgres -d precog_staging -c "DELETE FROM scheduler_status;"

# Restart
python main.py scheduler start --supervised --foreground
```

### Migrate Data to Another Machine

To move the database **with data** to a new machine (e.g., new desktop, Railway):

```powershell
# === On source machine ===
python main.py scheduler stop
pg_dump -U postgres -Fc --verbose -f precog_export.dump precog_staging

# Transfer via USB (not cloud — contains no secrets but may contain market positions)

# === On target machine ===
# Prerequisites: PostgreSQL installed, database created, repo cloned, .env configured
createdb -U postgres precog_staging  # or precog_prod

# Restore
pg_restore -U postgres -d precog_staging --no-owner --no-privileges --verbose precog_export.dump

# Apply any migrations the source didn't have
cd src/precog/database && alembic upgrade head && cd ../../..

# Clear scheduler state (different host)
psql -U postgres -d precog_staging -c "DELETE FROM scheduler_status;"

# Verify
python scripts/test_db_connection.py
python main.py scheduler start --supervised --foreground
```

**Post-migration verification:**
```sql
-- Row counts (compare with source)
SELECT 'market_snapshots' as tbl, COUNT(*) FROM market_snapshots
UNION ALL SELECT 'game_states', COUNT(*) FROM game_states
UNION ALL SELECT 'game_odds', COUNT(*) FROM game_odds
UNION ALL SELECT 'orders', COUNT(*) FROM orders;

-- SCD integrity (should return 0 rows)
SELECT 'game_states' as tbl, espn_event_id as key, COUNT(*)
FROM game_states WHERE row_current_ind = TRUE
GROUP BY espn_event_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'market_snapshots', market_id::text, COUNT(*)
FROM market_snapshots WHERE row_current_ind = TRUE
GROUP BY market_id HAVING COUNT(*) > 1;
```

---

## Dual-Machine Workflow (Laptop + Desktop)

### Development Loop

```
  Laptop (dev)                          Desktop (staging)
  ============                          =================
  1. Write code                         4. git pull origin main
  2. Run tests                          5. alembic upgrade head
  3. Push to main (via PR)              6. Restart services
       |                                     |
       +------ GitHub (main branch) ---------+
```

### When to Restart Desktop Services

| Change Type | Restart Needed? | Command |
|-------------|-----------------|---------|
| Schema migration (new alembic) | **YES** — stop, migrate, start | Full restart sequence |
| Poller code (schedulers/, api_connectors/) | **YES** — new code needs fresh import | `scheduler stop` then `start` |
| CRUD module changes (database/) | **YES** — runtime imports | Full restart |
| CLI-only changes (cli/) | **NO** — CLI is invoked fresh each time | No action needed |
| Config changes (YAML) | **YES** — config loaded at startup | `scheduler stop` then `start` |
| Documentation only | **NO** | No action needed |
| Test-only changes | **NO** | No action needed |

### Keeping Migrations in Sync

Both machines must be at the same Alembic head after every pull:

```powershell
# On desktop after git pull
cd src/precog/database
alembic current          # Check current migration
alembic upgrade head     # Apply any new migrations
alembic current          # Verify at head
cd ../../..
```

**If migrations diverge** (e.g., desktop is behind):
```powershell
# Check what's pending
alembic history --indicate-current

# Apply all pending
alembic upgrade head
```

**If you need to test a migration on laptop first:**
```powershell
# On laptop (dev DB)
PRECOG_ENV=dev alembic upgrade head

# Run tests
python -m pytest tests/unit/ tests/integration/ -q --no-cov

# If green, push to main, then pull on desktop
```

### Environment Isolation

| Item | Laptop | Desktop | Synced via |
|------|--------|---------|------------|
| Code | latest main or feature branch | main only | Git |
| .env | `PRECOG_ENV=dev` | `PRECOG_ENV=staging` | **NEVER synced** — local only |
| _keys/ | dev keys | staging/prod keys | **USB transfer** — never git |
| Database | `precog_dev` (expendable) | `precog_staging` (production data) | Independent — never synced |
| Migrations | same Alembic chain | same Alembic chain | Git (code) + `alembic upgrade head` |
| Config YAML | same files | same files | Git |

### Emergency: Bad Migration on Desktop

If a migration breaks the desktop database:

```powershell
# 1. Stop services immediately
python main.py scheduler stop

# 2. Check what happened
cd src/precog/database
alembic current
alembic history --indicate-current

# 3. Downgrade the bad migration
alembic downgrade -1

# 4. Verify
alembic current

# 5. On laptop: fix the migration, push fix, then re-pull on desktop
```

If downgrade fails or data is corrupted: restore from daily backup (see Backup & Restore above).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Connection refused" | PostgreSQL not running | `net start postgresql-x64-15` |
| "FATAL: password authentication failed" | Wrong password in .env | Update DB_PASSWORD |
| "No module named 'precog'" | Not installed in editable mode | `pip install -e ".[test]"` |
| Poller stops after sleep | Windows power settings | Set power plan to "High Performance", disable sleep |
| "rate limit exceeded" | Too many concurrent leagues | Check `data_sources.yaml` rate_budget_per_hour |
| Stale scheduler_status | Previous crash left stale rows | `DELETE FROM scheduler_status;` then restart |

---

## Version History

| Version | Date | Summary |
|---------|------|---------|
| 2.0 | 2026-04-05 | Complete rewrite as clean install guide. Replaces migration approach. |
| 1.0 | 2026-03-13 | Original migration guide (pg_dump laptop -> desktop). Obsolete. |
