# Decision #119/ADR-119: Business-Key Cleanup + Weather Phase 1 Non-Sport Foundation Validation

> **Draft status (2026-04-22):** Session 70 Task 5 sister deliverable. Ready for integration into `ARCHITECTURE_DECISIONS_V2.37.md` via Librarian Micro-ANNOUNCE (session 71). Complements ADR-118.

**Date:** April 22, 2026
**Status:** ✅ Accepted
**Phase:** Phase 1 — Canonical Identity & Event-State Layer (complements ADR-118)
**Priority:** 🟡 High (foundational cleanup + non-sport validation gate before 20+ canonical-layer migrations land)
**Supersedes:** None. Complements ADR-118. Refines ADR-117 by reclassifying `series.series_key` as Tier 3 and codifying SCD-2 exception to anti-formatted-PK rule. Refines ADR-116 by deleting three business-key columns violating "business key earns its uniqueness" rule.

---

## Context: Two findings converged into one decision

Round 2A of Task 5 (Isidore, postgres-dev MCP audit of 17 `*_key` columns) surfaced three distinct problems:

1. **Three formatted-PK decoration columns** — `games.game_key` (`GAM-{id}`), `markets.market_key` (`MKT-{id}`), `events.event_key` (`EVT-{id}`) — are `{PREFIX}-{id}` projections of SERIAL PK. No information beyond PK; never query predicates outside test assertions. Violate ADR-116 Rule 2. Combined blast radius ~144 refs / 34 files — all test fixtures or CRUD passthroughs, no production dispatch.

2. **One Tier misclassification** — `series.series_key` typed as Tier-2 internal actually stores Kalshi `series_ticker` (e.g., `KXNFLWINS`). Under ADR-117 must be Tier 3. Name actively misleading.

3. **Three SCD-2 version-stable surrogates look like decoration but aren't** — `game_states.game_state_key`, `positions.position_key`, `edges.edge_key` follow `{PREFIX}-{id}` shape. Naive "kill decoration" lint would sweep them up. They serve real architectural role: in SCD-2, each row's `id` changes per version; external reference to "this position" needs version-stable identifier across version history.

In parallel, user directive widened Phase 1 scope: **introduce weather data collection to validate canonical-layer foundations against non-sport domain BEFORE 20+ migrations land**. ADR-118 commits Phase 1 to canonical_observations + three-timestamp + locations + projection contract — all argued from sports case. Without second kind exercising contract, shape flaws surface when expensive to fix.

Weather is right second kind because it exercises what sports cannot:
- Append-only semantics (weather readings not corrections) — validates `canonical_observations` handles non-SCD
- Forecast-vs-reading is textbook three-timestamp case
- NOAA vs weather.gov overlap validates source-authority pattern
- `locations` graduates from stub to first real use

Weather markets are near-term Phase 2+ likelihood (Kalshi has listed hurricane/temperature markets prior seasons). Starting collection Phase 1 builds backtest depth.

---

## Decision summary

**Part 1** — DELETE three formatted-PK decoration columns; RENAME + RECLASSIFY `series.series_key`; DOCUMENT SCD-2 version-stable surrogate exception; COMMIT canonical layer to never introduce formatted-PK decoration.

**Part 2** — Ship weather observation collection Phase 1: NOAA adapter, `weather_observations` fact table per ADR-118 contract, real-data `locations`, weather poller + supervisor wiring, CRUD, 8-type test matrix. **No weather markets** (Phase 2+).

---

## Part 1 — Business-Key Cleanup

### Per-column classification

| Table | Column | Format | Decision | Rationale | Blast radius |
|---|---|---|---|---|---|
| `games` | `game_key` | `GAM-{id}` UNIQUE | **DELETE** | Pure PK decoration; `uq_games_matchup` is real natural key | ~57 refs / 10 files |
| `markets` | `market_key` | `MKT-{id}` UNIQUE | **DELETE** | `(platform_id, external_id)` + `ticker` already UNIQUE | ~58 refs / 16 files |
| `events` | `event_key` | `EVT-{id}` UNIQUE | **DELETE** | `uq_events_platform_external` covers natural-key lookup | ~29 refs / 8 files |
| `series` | `series_key` | Kalshi `series_ticker` | **RENAME + RECLASSIFY** | Actually Tier-3 external; rename to `external_series_ticker` | ~79 refs / 11 files |
| `game_states` | `game_state_key` | `GST-{id}` SCD-2 stable | **KEEP (exception)** | Version-stable surrogate required for cross-version external reference | — |
| `positions` | `position_key` | `POS-{id}` SCD-2 stable | **KEEP (exception)** | Same SCD-2 role | — |
| `edges` | `edge_key` | `{prefix}-{id}` SCD-2 stable | **KEEP (exception)** | Same SCD-2 role | — |
| `sports`, `leagues`, `config_overrides` | `sport_key`, `league_key`, `config_key` | human-readable | **KEEP** | Genuine natural-lookup identifiers | — |

### Migration order (0091-0094)

- `0091_drop_events_event_key.py` — smallest blast, template
- `0092_drop_markets_market_key.py` — heaviest, test-fixture sweep accompanies
- `0093_drop_games_game_key.py` — medium blast; historical_games_loader.py update
- `0094_rename_series_key_to_external_series_ticker.py` — rename column + index names + ADR-117 tier reclassification

Each independently reversible. Test-fixture updates accompany migration (not follow-up PR).

**Coordinated migration chosen over deprecation window.** No external consumers; deprecation pays real cost for zero safety benefit.

### SCD-2 version-stable surrogate pattern (documented exception)

`game_state_key`, `position_key`, `edge_key` follow `{PREFIX}-{id}` but serve different architectural purpose: SCD-2 tables represent logical entity as chain of rows (one per version), each with distinct `id`. External reference to "position 4821" must resolve to same logical position across version chain — changing `id` cannot provide. `_key` column supplies version-stable identity.

**Any automated lint must gate on `row_current_ind` column presence.** Tables without SCD-2 markers have no legitimate need for version-stable-over-PK identifier; SCD-2 tables do. This is Pattern 80 promotion candidate.

Future Phase 2+ migration will rename these to `version_stable_id` for self-documenting naming; semantics preserved; no blast-radius work blocked.

### Canonical layer commitment

ADR-118's `canonical_events`, `canonical_markets` will **not** carry `canonical_key` / `canonical_market_key` in `CAN-EVT-{id}` / `CAN-MKT-{id}` format. SERIAL PK sufficient. If external-facing readability matters later (Task 9 LLM): real composite natural key or derived view, not formatted-PK decoration. Closes the door on anti-pattern propagation.

---

## Part 2 — Weather Phase 1 Non-Sport Foundation Validation

### Data source — NOAA (OpenWeather fallback)

**Recommended:** NOAA NWS (`api.weather.gov`) + CDO (`www.ncei.noaa.gov/cdo-web/api/v2`).
- Free, no rate-limit fees, no key for NWS (CDO free token)
- Comprehensive US coverage matches current market platforms (Kalshi/Polymarket US-first)
- Publishes both forecast + observation streams → exercises three-timestamp pattern naturally
- Station metadata populates `locations` with real data

**Fallback:** OpenWeather for Phase 3+ international. Rejected for Phase 1 on (a) free-tier rate limits (60/min, 1M/month); (b) US-focus mismatch discourages scope creep.

`observation_source` registry records: `source_key='noaa_nws'`, `source_kind='api'`, `authoritative_for=['weather_observation']`.

### `weather_observations` DDL (Phase 1)

```sql
CREATE TABLE weather_observations (
  id BIGSERIAL PK,
  observation_id BIGINT NOT NULL REFERENCES canonical_observations(id),
  canonical_event_id BIGINT NULL REFERENCES canonical_events(id),
                             -- nullable Phase 1; most rows NULL until market lists
  location_id BIGINT NOT NULL REFERENCES locations(id),
  observed_at TIMESTAMPTZ NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_published_at TIMESTAMPTZ,
  temperature_c NUMERIC(5,2) CHECK (temperature_c BETWEEN -80 AND 60),
  humidity_pct NUMERIC(5,2) CHECK (humidity_pct BETWEEN 0 AND 100),
  pressure_hpa NUMERIC(7,2),
  wind_kph NUMERIC(6,2),
  wind_direction_deg NUMERIC(5,2),
  precipitation_mm NUMERIC(6,2),
  cloud_cover_pct NUMERIC(5,2),
  visibility_km NUMERIC(6,2),
  conditions_raw VARCHAR(128),
  payload_hash BYTEA NOT NULL,
  UNIQUE (location_id, observed_at, observation_id)
);

CREATE INDEX ix_weather_location_observed ON weather_observations (location_id, observed_at DESC);
CREATE INDEX ix_weather_canonical ON weather_observations (canonical_event_id, observed_at)
  WHERE canonical_event_id IS NOT NULL;
```

**Append-only, not SCD-2.** Weather readings are observations, not corrections. Corrections modeled via `canonical_observations.supersedes_observation_id` linkage, not SCD-2 versioning on `weather_observations`.

### Module scaffolding

- `src/precog/api_connectors/noaa_client.py` — follows kalshi_client/espn_client shape
- `src/precog/schedulers/weather_poller.py` — BasePoller subclass, `SERVICE_KEY='weather_state'`, 5-10 min cadence per station, dual-writes canonical_observations + weather_observations transactionally
- `src/precog/database/crud_weather_observations.py` — insert, get_latest, get_in_window
- `src/precog/schedulers/service_supervisor.py` — `create_weather_poller()` factory
- Seed migration for `locations` — ~20-50 NOAA stations covering NFL/NBA/MLB stadium cities

### Migration order (0095-0097)

- `0095_locations_seed_noaa_stations.py` — real NOAA station rows
- `0096_create_weather_observations.py` — table + indexes + CHECKs
- `0097_weather_source_registry_entry.py` — INSERT observation_source row for `noaa_nws`

### Test coverage (8-type matrix)

| Type | Focus |
|---|---|
| Unit | NOAAClient parsing, dataclass round-trip, rate-limiter, WeatherPoller tick logic (mock client) |
| Integration | Poller → canonical_observations + weather_observations dual-write consistency |
| E2E | Real NOAA sandbox call; observations land in both tables with matching observation_id |
| Property | Payload-hash dedup idempotent; append-only invariant; three-timestamp ordering |
| Stress | 50 stations × 10min cadence × 24h simulation; <5% CPU |
| Race | Concurrent pollers against overlapping stations produce no duplicates |
| Security | NOAA token in .env never logged; JSON sanitization; no SSRF |
| Performance | Poller tick <2s per station; dual-table insert <50ms |

### Kalshi weather markets IN Phase 1 (scope correction, session 70 user clarification)

User corrected an earlier misunderstanding: **Kalshi has comprehensive weather markets live today** (hurricane markets, temperature markets, precipitation markets). We are not blocked waiting for a platform to list them; we just haven't been polling them. Phase 1 scope includes:

- **Kalshi weather market polling** — reuse existing `kalshi_poller.py` infrastructure; extend series discovery to include weather series tickers (e.g., `KXHIGHNY`, `KXHURRICANE*`, etc.)
- **`canonical_events` created for each Kalshi weather market** via `manual_v1` algorithm at poll-time. Each market becomes a canonical_event with `domain='weather'`, appropriate `resolution_window`, and `metadata.location_id`.
- **Matching pipeline wiring — observation ↔ canonical_event** by `location_id` + `observed_at ∈ resolution_window`. Same `manual_v1` algorithm as sports matching, just with different feature extraction (location match + temporal window containment instead of team-name jaccard).
- **`weather_observations.canonical_event_id` populates from day one** as the matcher finds pairings, not NULL-until-market-lists as originally scoped.

**Significance:** this validates the canonical matching pipeline on live production data in a non-sport domain during Phase 1, not Phase 2+. Every one of ADR-118's architectural claims — three timestamps, observation-stream primitive, canonical-aware matching, trust_tier LLM surface, source attribution, resolution-rule fingerprinting — gets exercised against real Kalshi weather data and real NOAA weather readings before the other 20+ migrations build on top. Strongest possible foundation validation.

**No major migration count change** — schema already supports this via ADR-118 + ADR-119 Part 2 core. Requires configuration additions (Kalshi weather series tickers in `config/markets.yaml`) + canonical_event seeding on weather market poll events.

### Explicitly NOT Phase 1 (updated)

- International weather coverage (Phase 3+)
- Forecast reasoning / nowcast models (Phase 4)
- Automated matcher for weather (Phase 3+ — weather uses `manual_v1` location+time matcher in Phase 1, same as sports uses manual_v1)
- Other non-sport kinds (poll_releases, econ_prints, news_events) — **weather is single Phase 1 foundation validator; it now exercises both observation collection AND live market matching**

---

## Alternatives considered

**Part 1:**
1. Deprecation window for DELETE (rejected — no external consumers)
2. Include SCD-2 keys in DELETE sweep + add new `version_stable_id` (rejected — doubles churn for identical semantics)
3. Keep formatted-PK `canonical_key` for LLM readability (rejected — `CAN-EVT-285815` not more readable than `285815`)

**Part 2:**
1. Defer all non-sport to Phase 3 (rejected — foundation validation discipline)
2. OpenWeather instead of NOAA (rejected for Phase 1 — rate limits + US-focus mismatch)
3. Ship weather_observations without poller (rejected — unused schema has unvalidated shape)
4. Ship all four non-sport kinds (rejected — overshoots "validation" into "Phase 3 done early")

---

## Consequences

**Positive:**
- Foundation validation before 20+ migrations lock in
- Append-only observation semantics explicitly validated
- Three-timestamp model exercised by forecast-vs-observation native case
- Source-authority pattern exercised by NOAA-vs-weather.gov overlap
- Backtest depth from day one for future weather markets
- Formatted-PK propagation prevented in canonical layer
- `_key` naming split sharpens (external vs internal clear)

**Trade-offs:**
- ~7 additional Phase 1 migrations (0091-0097)
- One additional production service (weather poller) with no current consumer
- Weather data accumulation with no Phase 1 consumer (small storage cost)
- Test-fixture sweep across 34 files for Part 1

**Neutral:**
- Part 1 blast concentrated in fixtures, not production
- Part 2 weather has no Phase 4 ML consumer yet (Phase 4 scope)

---

## Phase commitments

- **Phase 1:** Part 1 cleanup complete; Part 2 weather collection live; NOAA registered; locations populated; 8-type tests green
- **Phase 2+:** Weather markets added when platform lists; canonical_event_id population ramps
- **Phase 3+:** poll_releases, econ_prints, news_events, entertainment under same contract; international weather if needed
- **Phase 4+:** Weather feature projection; nowcast/forecast model construction

---

## Rollback

- Part 1 DELETEs: reversible via re-add column + backfill `'{PREFIX}-' || id::TEXT`
- Part 1 rename: reversible in one migration
- Part 2 weather: fully additive. Drop poller, drop weather_observations, delete noaa_nws row, preserve locations. Zero blast on existing sports ingestion

---

## Cross-references

- ADR-118 (sister) — canonical identity + matching + event-state foundation ADR-119 validates
- ADR-117 — series_key reclassification updates Tier taxonomy
- ADR-116 — Part 1 implements Rule 2; SCD-2 exception amends Rule 2
- ADR-089 — Dual-key pattern; SCD-2 surrogate is extension not contradiction
- Pattern 80 (promoted this session) — SCD-2 Version-Stable Surrogate Identifiers; lint gate on `row_current_ind`
- Isidore memo (`design_review_task5_isidore_memo.md`) — audit origin
- Round 3 synthesis (`design_review_task5_round3_synthesis.md`) — event-state architecture
- Issue #496 — `_key` suffix history
- Epic #935 — Part 1 is Phase 4 of identity-semantics arc

---

## Origin

Session 70 Task 5 Round 2A (Isidore postgres-dev MCP audit) surfaced Part 1. User directive for non-sport Phase 1 foundation validation + Phase 2+ weather market backtest depth prep introduced Part 2. Both landed as sister deliverables to ADR-118.
