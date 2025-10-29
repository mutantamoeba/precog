# Database Tables Reference - Quick Lookup

---
**Created:** 2025-10-23
**Database:** precog_dev
**Schema:** public
**Total Tables:** 18
**Purpose:** Quick reference for developers - detailed data dictionary planned for Phase 6-7
---

## Quick Summary: All 18 Tables in precog_dev

### Core Platform (4 tables)
1. **platforms** - Multi-platform support (Kalshi, Polymarket)
2. **series** - Market hierarchy
3. **events** - Game/event instances
4. **markets** - Binary outcomes with DECIMAL(10,4) prices

### Data & Analytics (4 tables)
5. **game_states** - Live game statistics
6. **probability_matrices** - Historical probabilities
7. **probability_models** - Immutable model versions (no row_current_ind)
8. **strategies** - Immutable strategy versions (no row_current_ind)

### Trading & Risk (7 tables)
9. **edges** - EV+ opportunities with strategy_id/model_id FKs
10. **positions** - Open positions with trailing_stop_state JSONB + monitoring fields
11. **trades** - Executed orders with strategy_id/model_id attribution
12. **position_exits** - Exit events (Phase 5, append-only)
13. **exit_attempts** - Order attempts for debugging (Phase 5, append-only)
14. **settlements** - Final outcomes
15. **account_balance** - Account balances with versioning

### System Utilities (3 tables)
16. **config_overrides** - Database config overrides
17. **circuit_breaker_events** - Risk management events
18. **system_health** - System monitoring

---

## Key Features

✅ **DECIMAL Precision** - All prices use numeric(10,4)
✅ **Two Versioning Patterns** - row_current_ind vs immutable versions
✅ **Trade Attribution** - Every trade links to strategy & model versions
✅ **Phase 5 Exit Management** - 10 exit conditions, partial exits, price walking

---

## Common Query Patterns

### Get Current Market Price
```sql
SELECT yes_price, no_price
FROM markets
WHERE ticker = 'NFL-KC-BUF-YES'
  AND row_current_ind = TRUE;
```

### Get Active Strategy Version
```sql
SELECT * FROM strategies
WHERE strategy_name = 'halftime_entry'
  AND status = 'active'
ORDER BY strategy_version DESC
LIMIT 1;
```

### Get Open Positions with Latest Prices
```sql
SELECT
    p.*,
    m.yes_price as current_market_price,
    (m.yes_price - p.entry_price) * p.quantity as unrealized_pnl
FROM positions p
JOIN markets m ON p.market_id = m.market_id
WHERE p.status = 'open'
  AND p.row_current_ind = TRUE
  AND m.row_current_ind = TRUE;
```

---

**For complete schema details:** See `DATABASE_SCHEMA_SUMMARY_V1.5.md`
**For comprehensive data dictionary:** Planned for Phase 6-7

**END OF REFERENCE**
