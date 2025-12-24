# ADR-108: Hybrid Cloud Architecture for Live Data Collection

---
**Version:** 1.1
**Date:** December 22, 2025
**Status:** Accepted
**Phase:** Phase 2.5 (Live Data Collection Service)
**Drivers:** Data accumulation urgency, development flexibility, cost optimization
**GitHub Issue:** #247
**Related ADRs:** ADR-107 (Single-Database Architecture), ADR-105 (Two-Axis Environment Configuration)
---

## Context

With the NFL season ending soon (early February 2026), there's urgency to start collecting live market and game state data for model training. The question arises: how do we deploy to the cloud while maintaining efficient local development?

**Key Requirements:**
1. Start collecting live ESPN game states and Kalshi market data ASAP
2. Maintain fast local development and testing cycles
3. Enable model training with real production data
4. Deploy a React frontend for monitoring before Phase 5 execution work
5. Keep costs minimal during development phase

**Options Evaluated:**

| Option | Local Tests | Model Training | Data Collection | Complexity |
|--------|-------------|----------------|-----------------|------------|
| A. Full Cloud | Slow (network) | Cloud only | Cloud TimescaleDB | Low |
| B. Full Local | Fast | Local copy | Push to cloud | High (sync) |
| C. **Hybrid** | Fast (local) | Periodic sync | Cloud TimescaleDB | Medium |

## Decision

Implement a **Hybrid Cloud Architecture** with clear separation:

### 1. Local Development Environment

```
Local PostgreSQL (precog_dev)
├── Unit tests (fast, isolated)
├── Integration tests (database operations)
├── Property-based tests (Hypothesis)
└── Development experimentation
```

- **Database:** Local PostgreSQL 15+ on developer machine
- **Purpose:** Fast test execution (~seconds, not minutes)
- **Data:** Test fixtures only (no production data by default)
- **CI/CD:** GitHub Actions uses its own ephemeral PostgreSQL

### 2. Cloud Production Environment

```
Railway Platform
├── TimescaleDB (production data)
│   ├── ESPN game states (live collection)
│   ├── Kalshi market data (live collection)
│   ├── Historical seeded data
│   └── All trades/positions (with execution_environment)
├── FastAPI Backend (data collection service)
└── React Frontend (monitoring dashboard)
```

- **Database:** Railway-managed TimescaleDB
- **Purpose:** Live data collection, production trading (Phase 5+)
- **Data:** Real ESPN/Kalshi data, persisted permanently
- **Access:** HTTPS API, authenticated access

### 3. Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOCAL DEVELOPMENT                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ pytest       │    │ Local        │    │ Model Training   │  │
│  │ (unit/integ) │───▶│ PostgreSQL   │◀───│ (periodic sync)  │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│                             │                      ▲            │
│                             │ (dev/test only)      │ (read)     │
│                             ▼                      │            │
└─────────────────────────────────────────────────────────────────┘
                                                     │
                              ┌──────────────────────┘
                              │ Periodic data sync
                              │ (pg_dump → pg_restore)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RAILWAY CLOUD                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ FastAPI      │    │ TimescaleDB  │    │ React Frontend   │  │
│  │ Backend      │───▶│ Production   │◀───│ (monitoring UI)  │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│        │                    ▲                      │            │
│        │                    │                      │            │
│        ▼                    │                      ▼            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ ESPN API    │     │ Kalshi API  │     │ User Browser     │  │
│  │ (game data)  │     │ (markets)   │     │ (HTTPS)          │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Environment Configuration

### Environment Variables

| Variable | Local Dev | Railway Cloud | Purpose |
|----------|-----------|---------------|---------|
| `PRECOG_ENV` | `development` | `production` | Which database (local vs cloud) |
| `KALSHI_MODE` | `demo` | `live` | Which API endpoint (demo vs prod) |
| `DATABASE_URL` | `postgres://localhost/precog_dev` | `${{Postgres.DATABASE_URL}}` | Database connection |
| `RAILWAY_ENVIRONMENT` | (not set) | `production` | Railway-specific |

### Integration with ADR-107 (Single Database)

This architecture maintains ADR-107's single-database philosophy:

- **Cloud TimescaleDB** is the single source of truth for production data
- **execution_environment** column distinguishes live/paper/backtest trades
- Local PostgreSQL is for testing only (never contains real trades)

```sql
-- Cloud production example
SELECT * FROM trades WHERE execution_environment = 'live';  -- Real trades
SELECT * FROM trades WHERE execution_environment = 'paper'; -- Demo trades

-- Local development never has real trades
-- Only test fixtures with execution_environment = 'backtest'
```

## Data Sync Strategy (Model Training)

For model training, developers can sync production data to local:

```bash
# Option 1: Manual pg_dump/pg_restore (weekly/monthly)
railway run pg_dump -Fc -d $DATABASE_URL > precog_prod_backup.dump
pg_restore -d precog_dev precog_prod_backup.dump

# Option 2: Selective sync (specific tables only)
railway run psql -c "COPY game_states TO STDOUT CSV" > game_states.csv
psql -d precog_dev -c "COPY game_states FROM STDIN CSV" < game_states.csv

# Option 3: Read-only replica (future Phase 4+ if needed)
# Railway supports read replicas for high-traffic scenarios
```

**Sync Frequency:**
- **Model training:** Weekly sync of game_states, market_data tables
- **Backtesting:** On-demand sync before strategy evaluation
- **No sync needed:** For unit/integration tests (use fixtures)

## Frontend Before Phase 5

React frontend will be deployed to Railway before execution work begins:

**Phase 2.5-3:** Data collection monitoring
- Live game state display
- Market price tracking
- Scheduler status and health

**Phase 4:** Model and strategy monitoring
- Edge detection visualization
- Model performance comparison
- Backtest results display

**Phase 5:** Execution monitoring
- Position tracking
- P&L dashboard
- Trade history

## Deployment Strategy

### Initial Deployment (Phase 2.5)

1. **Create Railway project** with TimescaleDB service
2. **Configure environment variables** (API keys, database URL)
3. **Deploy data collection service** (FastAPI + APScheduler)
4. **Verify data collection** (ESPN games, Kalshi markets)

### Git-Based Deployment

```bash
# Development workflow
git checkout -b feature/new-feature
# ... make changes locally, run tests ...
git push origin feature/new-feature
# Create PR, wait for CI, merge

# Deployment to Railway (automatic on main branch merge)
git checkout main
git pull origin main
# Railway auto-deploys on push to main
```

## Cost Considerations

**Railway Pricing Model** (Usage-Based):
- **Memory:** $0.00000386/GB-second (~$10/GB/month for 24/7)
- **CPU:** $0.00000772/vCPU-second (~$20/vCPU/month for 24/7)
- Reference: https://railway.com/pricing

**Railway Trial Credits:**
- $5 one-time trial credit
- Sufficient for initial setup and testing

**Estimated Monthly Costs:**

| Scenario | TimescaleDB | FastAPI | Frontend | Total |
|----------|-------------|---------|----------|-------|
| **Development** (intermittent use) | ~$5-10 | ~$3-5 | ~$0 | **~$10-15/month** |
| **Production** (24/7 light) | ~$15-20 | ~$8-10 | ~$0 | **~$20-30/month** |
| **Production** (scaled) | ~$25-35 | ~$15-20 | ~$0 | **~$35-50/month** |

**Component Specifications:**
- TimescaleDB: 1GB RAM, 0.5 vCPU base (scales with usage)
- FastAPI Backend: 512MB RAM, 0.25 vCPU base (scales with load)
- React Frontend: Static hosting (~$0, or use Vercel/Netlify free tier)

**Cost Optimization Tips:**
1. Use Railway's auto-sleep for development environments
2. Scale down during off-peak hours (no NFL games)
3. Use scheduled jobs instead of continuous polling where possible

## Consequences

### Positive

1. **Fast local development:** Tests run in seconds, not minutes
2. **Real production data:** Models train on actual market behavior
3. **Urgent data collection:** Start gathering NFL data immediately
4. **Cost-effective:** Railway pricing is usage-based
5. **Simple deployment:** Git push triggers deployment
6. **Monitoring ready:** Frontend before Phase 5 execution

### Negative

1. **Data sync overhead:** Periodic manual sync for model training
2. **Network dependency:** Cloud database requires internet access
3. **Two databases:** Local and cloud must have compatible schemas

### Neutral

1. **Schema migrations:** Run on both local and cloud (standard practice)
2. **Test isolation:** Local tests never touch production data

## Implementation Checklist

### Phase 2.5 Tasks (Cloud Infrastructure)

- [ ] Create Railway project
- [ ] Provision TimescaleDB service
- [ ] Configure environment variables (KALSHI_MODE=live, etc.)
- [ ] Deploy FastAPI data collection service
- [ ] Verify ESPN data collection (game states)
- [ ] Verify Kalshi data collection (market prices)
- [ ] Set up health monitoring endpoint

### Phase 3.5 Tasks (Frontend)

- [ ] Create React frontend project
- [ ] Implement monitoring dashboard
- [ ] Deploy to Railway
- [ ] Connect to FastAPI backend

## References

- ADR-107: Single-Database Architecture with Execution Environments
- ADR-105: Two-Axis Environment Configuration
- ADR-100: Service Supervisor Pattern for Data Collection
- Phase 2.5: Live Data Collection Service
- Railway CLI Documentation: https://docs.railway.app/develop/cli
