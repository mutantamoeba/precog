# Decision #118/ADR-118: Canonical Identity, Matching Infrastructure, and Event-State Layer

> **Draft status (2026-04-22):** Session 70 Task 5 output. Ready for integration into `ARCHITECTURE_DECISIONS_V2.37.md` via Librarian Micro-ANNOUNCE (session 71). This draft is the authoritative design artifact; the integration step is mechanical.

**Date:** April 22, 2026
**Status:** ✅ Accepted
**Phase:** Epic (sibling to #935) — Canonical Layer Foundation (multi-session arc, Phase 1 ships in sessions 71-74)
**Priority:** 🔴 Critical (foundational cross-platform identity + ML causal-correctness commitment — governs every downstream feature store, arbitrage scan, LLM entity export, and backtest pipeline)
**Supersedes:** Extends ADR-089 (Dual-Key Schema Pattern) and ADR-117 (Three-Tier Identity Model) into cross-platform canonical identity + matching + observation primitives. Subsumes Issue #937 (cross-table external-key UNIQUE audit) as a landing site for the audit's demotions. Folds the Epic #935 "OT-rule-divergence ghost" (Mulder's next-#935 prediction) into the matching-ledger design by making resolution-rule fingerprinting a first-class match feature rather than a silent natural-key assumption.

---

## Terminology (glossary — read this first)

This ADR introduces several terms that can be confusing without careful definition. Future engineers (and future-self) reading this ADR should refer here first.

| Term | Definition | Example |
|---|---|---|
| **Platform market** / **Platform event** | A row in `markets` / `events` representing a single venue's listing. Tied to a specific platform (Kalshi, Polymarket). Holds Tier-3 external IDs. | Kalshi ticker `KXNFLGAME-25SBWIN-KC`; Polymarket condition_id `0x1234...` |
| **Canonical market** / **Canonical event** | A row in `canonical_markets` / `canonical_events` representing the **ontological** market/event independent of any venue. Tier 1 PK + Tier 2 natural-key hash. No external source. | `canonical_event_id=42` = "Chiefs vs Bills on 2026-01-12 (game_id=285815)" |
| **Canonical entity** | Polymorphic participant (team, fighter, candidate, storm, location) referenced by canonical_events via participants table | `canonical_entity.entity_kind='team', entity_key='KC'` |
| **Canonical observation** | A row in `canonical_observations` — the universal fact table carrying cross-kind observation invariants (3 timestamps, source, payload_hash, canonical_event_id). | NOAA temperature reading at NYC Central Park 2026-07-04T14:00Z from station ABC |
| **Per-kind projection** | Type-specific fact table (`game_states`, `weather_observations`, future `poll_releases`/`econ_prints`/`news_events`) with typed columns. Each row links to a canonical_observation via `observation_id`. **PEER of canonical_observations, NOT INHERITANCE CHILD.** | `game_states` row with typed `home_score`, `away_score`, `period` columns |
| **Level A entity** (ADR-117 amendment) | Platform-scoped entity — `platform_market`, `platform_event`. Its Tier 1 PK is unique only within its platform. | `markets.id=1337` |
| **Level B entity** (ADR-117 amendment) | Canonical entity — `canonical_market`, `canonical_event`. Its Tier 1 PK is the project's durable identity across platforms. No Tier 3 (no external source). | `canonical_markets.id=7` |
| **Entity-framed canonical** | Canonical_event created from a pre-existing real-world entity (e.g., a game). Exists regardless of market coverage. | Sports |
| **Market-framed canonical** | Canonical_event created when a platform market lists. No market = no canonical_event. | Weather, polls, econ, news |
| **Matching ledger** | Collective term for `canonical_market_links` (current state) + `canonical_match_log` (append-only history) + `canonical_match_reviews` (human review state) + `canonical_match_overrides` (policy). Every match decision is first-class audited data. | — |
| **Match algorithm** | A named, versioned matching policy referenced by every link + log row. Seeded Phase 1 with `manual_sports_v1` (human-decided sports links) and `weather_location_time_v1` (deterministic rule for NOAA observations → weather canonical_events). | — |
| **Resolver** | Code in `src/precog/matching/` that attaches a platform_market to a canonical_market at write time (or returns NULL to defer). Implements the `CanonicalResolution` contract. | `resolve_or_attach_canonical_market(platform_market_row) → CanonicalResolution` |
| **Trust tier** | LLM-facing categorical confidence derived from `(min active-link confidence, review_state, domain)`. Three values: `high` / `medium` / `provisional`. LLM never sees raw confidence numbers. | `trust_tier='high'` = auto-confirmed at ≥0.95 AND human-reviewed |
| **Observation kind** | Enum on `canonical_observations` — `'sport_game_state'`, `'market_snapshot'`, `'weather'`, `'poll_release'`, `'econ_print'`, `'news_event'`. Expands per new domain. | — |
| **Three timestamps** | Non-negotiable model: `event_occurred_at` (world time) + `source_published_at` (when source made available) + `ingested_at` (when we learned). Prevents Phase 4 ML causal leakage. | NOAA reading: occurred=14:00Z, published=14:02Z, ingested=14:02.5Z |
| **Temporal alignment** | The operation of pairing canonical_observations by canonical_event_id (market↔state pairs) or canonical_market_id (cross-platform market pairs) within a time window. Implemented as `v_temporal_alignment` view (or future physical table behind same interface). | — |
| **Live path vs batch path** | Live-path consumers (edge detection, arbitrage scan) query `v_temporal_alignment` expecting ≤30s stale data. Batch-path consumers (ML training, backtest) may use separate materialized views with slower refresh. | — |

---

## Context: three tiers of identity we do not yet express

Precog today has one tier of identity in production: **platform-scoped rows**. `markets`, `events`, `games`, `market_snapshots`, `temporal_alignment` — all identify a row by the platform that listed it and the vendor IDs that platform assigned. ADR-117 hardened this tier by distinguishing internal surrogates (Tier 1), internal business keys (Tier 2), and external keys (Tier 3), and by forbidding `UNIQUE` on Tier 3. That work is complete within a venue. It is nothing like complete across venues.

Four converging pressures force the question now:

1. **@Whatsonyourmind's production experience (#496).** 5-30% of cross-platform market pairs require manual override even after good automated matching. Two platforms can list "Chiefs win Super Bowl LX" with identical-looking natural keys but different resolution rules, different outcome enumerations, different OT handling. Precog's schema currently has no place to put that disagreement — or the decisions we make about it — other than a nullable FK column that would destroy history on every re-match.

2. **Epic #935's successor failure mode (Mulder's Round 2B audit).** Issue #935 was "we asserted uniqueness on a key that wasn't unique." The next failure in the same family is "we asserted natural-key identity on a tuple that wasn't stable under the domain's real semantics." Two markets settling with different OT rules matched on `(domain, entities, window)` — the matcher unifies them, a user hedges across both sides expecting offset, settlement diverges because the rules differ.

3. **Phase 4 ML causal correctness.** Independent convergence from Cassandra (temporal-invariants memo) and Mulder (observation-stream memo) during Round 3 identified that a single `observation_ts` column on state tables silently means different things per source — source-asserted event time vs source-published time vs ingestion time — and that collapsing the three into one guarantees feature leakage in backtests. This was the highest-confidence signal in the entire three-round review.

4. **Task 9 (MCP/LLM Epic) alignment.** The LLM surface needs a stable natural-language referent — "show me all Chiefs markets" must resolve to one entity, not a per-platform re-scan. That referent cannot be a platform row, and it cannot be a matching view derived on the fly from confidence scores the LLM isn't allowed to see.

The monoculture audit (Round 2B, Mulder) landed an equal-and-opposite caution: 100% of today's corpus is Kalshi, 100% binary, 100% sports. Any design that over-commits to non-sport polymorphism before a non-sport market exists is speculation. ADR-118's shape is the reconciliation: **commit Phase 1 to the cross-venue primitives that cannot be retrofitted cheaply; defer per-kind projection tables until a second kind actually ships.**

---

## Decision summary

1. **Canonical identity tier** as new tables — `canonical_events`, `canonical_markets`, `canonical_event_participants`, polymorphic `canonical_entity` — expressing cross-platform identity independent of any venue.

2. **Matching decisions live in a first-class ledger**, not as a nullable FK column on `markets`. Canonical-to-platform linkage is many-to-many via `canonical_market_links` / `canonical_event_links` gated by `EXCLUDE` partial-unique (enforces N-to-1 today; preserves M:N evolvability). Every linkage appends a row to `canonical_match_log` (append-only, algorithm_id + confidence + features + decided_by). Reviews in `canonical_match_reviews`; overrides in `canonical_match_overrides` with `MUST_MATCH`/`MUST_NOT_MATCH` polarity.

3. **Event-state as three-layer construct, hybrid D+B pattern.** `canonical_observations` is a thin fact table carrying cross-kind invariants only (canonical_event, source, three timestamps, sequence_no, payload_hash, revision semantics). Per-kind projection tables — `game_states` today; `weather_observations`, `poll_releases`, `econ_prints`, `news_events` when domains land — are **peers** of the fact, not inheritance children. Typed columns, typed FKs, kind-specific CHECKs stay in projections.

4. **Dim + fact canonical linkage is BOTH.** Dimension tables (`games`, `markets`) carry canonical FKs as source of truth. Fact tables (`game_states`, `market_snapshots`, `temporal_alignment`) denormalize the linkage for hot-path query performance. Consistency via triggers/writers at write time + periodic reconciliation job. Dim is authoritative; fact is a denormalized cache with a documented drift-detection contract.

5. **`temporal_alignment` rewired in Phase 1, not deferred to Phase 4.** We are not in production. Two implementation options endorsed at ADR level (details below); implementation session picks.

6. **Universal + type-specific is complementary, not replacing.** `canonical_observations` universal across kinds; per-kind projection tables are type-specific. Rich domains (sports) get both dim + fact projections; thin domains (weather, polls) get fact projection only; dormant domains get neither.

7. **`canonical_events.game_id` is a nullable FK, preserved deliberately.** Canonical is a superset of games; never NOT NULL.

8. **No formatted-PK canonical_key columns.** Surrogate PK + content-addressable `natural_key_hash` is identity. Per ADR-119 sibling.

9. **LLM `trust_tier` is first-class schema surface.** Derived view collapses `(min active-link confidence, review_state, domain)` into `{high, medium, provisional}`. LLM never sees raw confidence.

---

## Key components

### Canonical identity tier

```sql
CREATE TABLE canonical_events (
  id                 BIGSERIAL PRIMARY KEY,
  domain             VARCHAR(32)  NOT NULL,             -- 'sports'|'politics'|'weather'|'econ'|'news'|'entertainment'
  event_type         VARCHAR(64)  NOT NULL,
  entities_sorted    INTEGER[]    NOT NULL,             -- sorted FKs into canonical_entity
  resolution_window  TSTZRANGE    NOT NULL,
  resolution_rule_fp BYTEA        NULL,                 -- sha256 of normalized resolution criteria; #935-ghost mitigation
  natural_key_hash   BYTEA        NOT NULL,             -- sha256(domain||event_type||entities||window||rule_fp)
  title              VARCHAR      NOT NULL,
  description        TEXT,
  game_id            INTEGER      NULL REFERENCES games(id),    -- sports path; NULL for non-sport. NEVER SET NOT NULL.
  series_id          INTEGER      NULL REFERENCES series(id),
  lifecycle_phase    VARCHAR(32)  NOT NULL DEFAULT 'proposed',
  metadata           JSONB,
  created_at, updated_at, retired_at,
  CONSTRAINT uq_canonical_events_nk UNIQUE (natural_key_hash)
);

CREATE TABLE canonical_markets (
  id                    BIGSERIAL PRIMARY KEY,
  canonical_event_id    BIGINT NOT NULL REFERENCES canonical_events(id) ON DELETE RESTRICT,
  market_type_general   VARCHAR(32) NOT NULL,           -- 'binary'|'categorical'|'scalar' (pmxt #964 shape)
  outcome_label         VARCHAR(255),
  natural_key_hash      BYTEA NOT NULL,
  metadata JSONB, created_at, retired_at,
  CONSTRAINT uq_canonical_markets_nk UNIQUE (natural_key_hash)
);

CREATE TABLE canonical_entity (
  id BIGSERIAL PK,
  entity_kind VARCHAR(32) NOT NULL,    -- 'team'|'fighter'|'candidate'|'storm'|'company'|'location'
  entity_key VARCHAR NOT NULL,
  display_name VARCHAR NOT NULL,
  metadata JSONB,
  CONSTRAINT uq_canonical_entity_kind_key UNIQUE (entity_kind, entity_key)
);

CREATE TABLE canonical_event_participants (
  id BIGSERIAL PK,
  canonical_event_id BIGINT NOT NULL REFERENCES canonical_events(id) ON DELETE CASCADE,
  entity_id BIGINT NOT NULL REFERENCES canonical_entity(id) ON DELETE RESTRICT,
  role VARCHAR(32) NOT NULL,           -- 'home'|'away'|'fighter_a'|'fighter_b'|'yes_side'|future
  CONSTRAINT uq_cep_event_role UNIQUE (canonical_event_id, role)
);
```

`entities_sorted` denormalizes participant set for natural-key hashing; `canonical_event_participants` is the typed relation. Both ship.

### Matching infrastructure

```sql
CREATE TABLE match_algorithm (
  id BIGSERIAL PK,
  name VARCHAR(64) NOT NULL,
  version VARCHAR(16) NOT NULL,
  code_ref VARCHAR, created_at, retired_at,
  CONSTRAINT uq_match_algorithm UNIQUE (name, version)
);
-- Phase 1 seeds exactly one row: ('manual_v1', '1.0.0')

CREATE TABLE canonical_market_links (
  id BIGSERIAL PK,
  canonical_market_id BIGINT NOT NULL REFERENCES canonical_markets(id) ON DELETE RESTRICT,
  platform_market_id INTEGER NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
  link_state VARCHAR(16) NOT NULL,                     -- 'active'|'retired'|'quarantined'
  confidence NUMERIC(4,3) NOT NULL,
  algorithm_id BIGINT NOT NULL REFERENCES match_algorithm(id),
  decided_by VARCHAR(64) NOT NULL,
  decided_at, retired_at, retire_reason,
  CONSTRAINT uq_active EXCLUDE USING btree (platform_market_id WITH =) WHERE (link_state = 'active')
);

CREATE TABLE canonical_event_links (-- parallel shape for event tier);

CREATE TABLE canonical_match_log (
  id BIGSERIAL PK,
  link_id BIGINT REFERENCES canonical_market_links(id) ON DELETE SET NULL,
  platform_market_id INTEGER NOT NULL,                 -- NO FK: survives market deletion
  canonical_market_id BIGINT,
  action VARCHAR(16) NOT NULL,                         -- 'link'|'unlink'|'relink'|'quarantine'|'override'
  confidence NUMERIC(4,3),
  algorithm_id BIGINT NOT NULL REFERENCES match_algorithm(id),
  features JSONB, prior_link_id BIGINT, decided_by, decided_at, note
);

CREATE TABLE canonical_match_reviews (
  id BIGSERIAL PK,
  link_id BIGINT NOT NULL REFERENCES canonical_market_links(id) ON DELETE CASCADE,
  review_state VARCHAR(16) NOT NULL,                   -- 'pending'|'approved'|'rejected'|'needs_info'
  reviewer, reviewed_at, flagged_reason, created_at
);

CREATE TABLE canonical_match_overrides (
  id BIGSERIAL PK,
  platform_market_id INTEGER NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
  canonical_market_id BIGINT NULL REFERENCES canonical_markets(id) ON DELETE RESTRICT,
  polarity VARCHAR(16) NOT NULL,                       -- 'MUST_MATCH'|'MUST_NOT_MATCH'
  reason TEXT NOT NULL, created_by, created_at,
  CONSTRAINT uq_override UNIQUE (platform_market_id),
  CONSTRAINT ck_polarity CHECK (
    (polarity = 'MUST_NOT_MATCH' AND canonical_market_id IS NULL)
 OR (polarity = 'MUST_MATCH'     AND canonical_market_id IS NOT NULL))
);
```

**Load-bearing invariants:** Manual overrides are algorithm-independent and consulted FIRST. The matcher must honor outstanding overrides as hard constraints regardless of algorithm version. Match log is append-only from migration 0090 (trigger-enforced after 30-day soak).

**Phase 1 matching policy:** one seeded algorithm (`manual_v1`). Every canonical row's linkage is written manually. No automated matcher. Schema fully deployed; policy degenerate. Phase 3 adds `keyword_jaccard_v1`; Phase 5 adds ML — zero schema migration between generations.

### Event-state layer: observations as primitive

**"State" is a sports-ism.** `game_states` is a 30-second SCD-2 stream of a continuously-evolving object with bounded shape; weather is sensor readings you never correct; polls are sparse releases with methodology; econ prints are revisable publications; news is discrete shocks. Forcing four distinct data physics under one "state" abstraction shoehorns. The honest primitive is **observation of a resolution-relevant signal**.

```sql
CREATE TABLE canonical_observations (
  id BIGSERIAL,
  canonical_event_id BIGINT NOT NULL REFERENCES canonical_events(id),
  observation_kind VARCHAR(32) NOT NULL,               -- 'sport_game_state'|'market_snapshot'|'weather'|'poll_release'|'econ_print'|'news_event'
  source_id BIGINT NOT NULL REFERENCES observation_source(id),
  source_event_ref VARCHAR,
  event_occurred_at TIMESTAMPTZ,                       -- source-asserted world time
  source_published_at TIMESTAMPTZ,                     -- when source made available
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_at TIMESTAMPTZ NOT NULL,
  valid_until TIMESTAMPTZ,
  sequence_no BIGINT,
  payload_hash BYTEA NOT NULL,
  raw_payload JSONB,
  supersedes_observation_id BIGINT REFERENCES canonical_observations(id),
  revision_reason VARCHAR,
  ingest_run_id BIGINT,
  PRIMARY KEY (id, ingested_at)                        -- composite PK enables future partitioning
) PARTITION BY RANGE (ingested_at);

CREATE INDEX idx_obs_canonical_valid ON canonical_observations (canonical_event_id, valid_at DESC);
CREATE INDEX idx_obs_source_ingested ON canonical_observations (source_id, ingested_at);
CREATE INDEX idx_obs_kind_valid      ON canonical_observations (observation_kind, valid_at);

CREATE TABLE observation_source (
  id BIGSERIAL PK,
  source_key VARCHAR UNIQUE NOT NULL,                  -- 'espn'|'kalshi'|'manual'|'noaa'|'bls'|'fivethirtyeight'
  source_kind VARCHAR NOT NULL,                        -- 'api'|'scrape'|'manual'|'derived'
  authoritative_for JSONB,                             -- array of observation_kind values
  created_at, retired_at
);

CREATE TABLE canonical_event_phase_log (
  id BIGSERIAL PK,
  canonical_event_id BIGINT NOT NULL REFERENCES canonical_events(id),
  phase VARCHAR(32) NOT NULL,                          -- 'proposed'|'listed'|'pre_event'|'live'|'suspended'|'settling'|'resolved'|'voided'
  entered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_id BIGINT NOT NULL REFERENCES observation_source(id),
  evidence_observation_id BIGINT REFERENCES canonical_observations(id),
  note TEXT
);

CREATE TABLE locations (
  id BIGSERIAL PK,
  location_kind VARCHAR NOT NULL,                      -- 'stadium'|'city'|'station'|'region'|'abstract'
  name, code, lat NUMERIC, lon NUMERIC, timezone, metadata JSONB, external_refs JSONB
);
```

**Per-kind projection tables are PEERS, not INHERITANCE CHILDREN.** `game_states` gains nullable `canonical_event_id` + `observation_id` (FK into `canonical_observations`). It is NOT migrated into the fact table as row data. The fact carries cross-kind invariants; projections carry typed columns + typed FKs + CHECKs + kind-specific query patterns.

**Decisive arguments:**
- D+B over pure D: **B→A is lossy, A→B is not** (Holden). Typed projections are supersets of JSONB; reconstructing typed columns from JSONB risks CHECK violations.
- Against (C) joined inheritance: psycopg2 CRUD at 30s cadence makes two-table-join-per-read operationally regrettable (Galadriel + Holden concurred).

### Universal + type-specific: domain-to-table matrix

| Domain | Universal dim (`canonical_events`) | Universal fact (`canonical_observations`) | Type-specific dim | Type-specific fact | Ships |
|---|---|---|---|---|---|
| Sports | ✓ | ✓ | `games` (existing) | `game_states` (existing) | Phase 1 |
| Markets (cross-venue) | N/A | ✓ | `canonical_markets` | `market_snapshots` (linked) | Phase 1 |
| Weather | ✓ | ✓ | — (no entity dim) | `weather_observations` | **Phase 1 (ADR-119)** |
| Polls | ✓ | ✓ | — | `poll_releases` | Phase 3 |
| Econ | ✓ | ✓ | — | `econ_prints` | Phase 3 |
| News | ✓ | ✓ | — | `news_events` | Phase 3 |
| Entertainment | ✓ | ✓ | — | deferred | Phase 4+ |

**Decision rule:** universal always; type-specific dim when domain has rich entity structure; type-specific fact when domain has typed measurements worth indexing.

### Dim + fact canonical linkage: both, with reconciliation

- `games.canonical_event_id` — dim, source of truth; populated by async enricher
- `game_states.canonical_event_id` — fact, denormalized; populated by writer-side trigger on INSERT
- `markets.canonical_market_id` — expressed as `canonical_market_links` (link table IS the source of truth)
- `market_snapshots.canonical_market_id` — fact, denormalized from active link at snapshot write
- `temporal_alignment.canonical_event_id` — fact, denormalized

**Reconciliation contract:** nightly `reconcile_canonical_linkage` job asserts fact/dim agreement, surfaces disagreements as data-quality anomalies. Idempotent; safe during active writes; reads-only for comparison.

**Why both:** dim is authoritative; fact denormalization is hot-path optimization at Phase 4 ML scale. The reason not to denormalize alone: silent copy of authoritative value is drift hazard without reconciliation. ADR-118 commits to both + reconciliation.

### `temporal_alignment` rewire: Phase 1, not Phase 4

We are not in production. Rewiring now costs less than rewiring later.

**CRITICAL FRESHNESS REQUIREMENT:** `temporal_alignment` serves **live edge detection** which queries the DB continuously to identify arbitrage and prediction opportunities. Any implementation with staleness > ~30s fails the live-trading-signal bar. Materialized views with hourly/daily refresh cadence are **not an option** for the live path; they can only serve separate batch-analytics consumers.

**Option A — Canonical-native writer with platform-path fallback (eager materialization, always-fresh).**
- Writer reads `canonical_event_id` from `games` via enricher-populated column
- `canonical_event_id IS NULL` rows fall back to `game_id` join path
- Partial index `(canonical_event_id, snapshot_time DESC) WHERE canonical_event_id IS NOT NULL`
- Deprecate fallback once coverage stabilizes (>99%)
- **Freshness: real-time (writer runs at 30s cadence matching pollers)**

**Option B — Plain (non-materialized) view over `canonical_observations` (always-fresh, query-time compute).**
- Replace physical table with view
- LATERAL subquery pairs market_snapshot + game_state observations within alignment window
- 5-table join dissolves; single canonical_observations source of truth
- **Freshness: real-time by construction (re-computes on every query)**
- Cost concern: query latency at Phase 4 scale — mitigated by partition pruning + partial indexes

**NOT an option for live path — batch-refresh materialized view.** A materialized view with hourly/daily refresh would serve backtest/ML-training workloads, not live edge detection. If Phase 4 introduces dedicated batch-analytics needs, that gets a *separate* materialized view; it does not replace the live-query path.

Implementation session chooses A or B based on latency benchmarks at representative scale. Decision criterion: **both options are always-fresh.** The choice is between eager (Option A: writer) vs lazy (Option B: plain view) materialization, not between fresh and stale. ADR rejects "keep writer on platform-FK path, add view on top" as Phase-4-deferral in disguise AND rejects any materialized-view-with-slow-refresh as a solution to the live path.

### Stable consumer contract (the key architectural commitment)

**`v_temporal_alignment` (or `temporal_alignment` as a physical table) is the stable interface that consumer code queries.** Whether it is backed by:
- a plain view over canonical_observations (Option B, Phase 1 recommended), OR
- a physical table populated by a writer (Option A, Phase 1 alternative), OR
- a future physical table migrated from B at Phase 4 scale

...is an **implementation detail invisible to consumers.** Every strategy, every ML feature extractor, every arbitrage scanner queries `v_temporal_alignment` by its columns; the storage backing may migrate without breaking consumers.

**Throw-away concern addressed:** if Phase 1 ships Option B (plain view) and Phase 4 benchmarks show view latency is untenable, the migration path is:
1. Create physical `temporal_alignment` table with same columns as view
2. Write backfill migration to populate from canonical_observations via the view's logic
3. Install writer that maintains the table going forward (Option A shape)
4. Swap the view definition to a simple `SELECT * FROM temporal_alignment` (preserving consumer queries)
5. Drop writer dependency on the view

Net throw-away: ~100 LOC of original view definition + Phase 4 re-tuned indexes. The ~500 LOC of writer is **new work whenever we write it** — deferred, not redundant. The preserved investments (canonical_observations, canonical FKs, resolver, matching ledger) are the overwhelming bulk of Phase 1 work.

### Phase 1 benchmark commitment (Cohort 5 deliverable)

To de-risk the Option B → Option A migration decision, Cohort 5 ships a **benchmark suite** that:
- Simulates representative query loads against `v_temporal_alignment` (point-in-time lookups, windowed scans, cross-platform arbitrage joins)
- Reports p50/p95/p99 query latency across growing canonical_observations row counts (1K, 10K, 100K, 1M scale)
- Establishes a baseline for Phase 4 re-benchmarking

**Threshold for migration trigger:** if live-path query p99 > 500ms at representative scale (Phase 4 cutover), migrate from B to A. Below threshold, B remains the live-path backing.

### View-to-table migration plan (for future implementation session, Phase 4)

Documented here so a future engineer doesn't re-derive:

1. Run Phase-4 benchmark; if p99 exceeds threshold, proceed
2. Create `temporal_alignment` physical table with view's column schema
3. Migration `NNNN_materialize_temporal_alignment.py`:
   - Backfill from `canonical_observations` via view logic
   - Partial indexes matching view's implicit query patterns
4. Install writer service (shape like existing `temporal_alignment_writer.py` adapted to read canonical_observations not platform FKs)
5. Alter view: `CREATE OR REPLACE VIEW v_temporal_alignment AS SELECT * FROM temporal_alignment;`
6. Consumers continue to query view name; zero application code changes
7. Decommission the plain-view computation path (safe once writer verified caught up)

Rollback path: drop table, revert view to canonical_observations-backed SELECT. Reversible.

### LLM trust_tier surface

```sql
CREATE VIEW v_canonical_market_llm AS
SELECT
  cm.id AS canonical_market_id,
  ce.title, ce.domain,
  jsonb_agg(jsonb_build_object('platform_id', pm.platform_id, 'ticker', pm.ticker, 'last_price', ms.price))
    FILTER (WHERE cml.link_state = 'active') AS platform_markets,
  CASE
    WHEN MIN(cml.confidence) FILTER (WHERE cml.link_state = 'active') >= 0.95
         AND bool_and(cmr.review_state = 'approved') THEN 'high'
    WHEN MIN(cml.confidence) FILTER (WHERE cml.link_state = 'active') >= 0.70 THEN 'medium'
    ELSE 'provisional'
  END AS trust_tier,
  bool_and(cmr.review_state = 'approved') AS human_reviewed
FROM canonical_markets cm
JOIN canonical_events ce ON ce.id = cm.canonical_event_id
LEFT JOIN canonical_market_links cml ON cml.canonical_market_id = cm.id
LEFT JOIN markets pm ON pm.id = cml.platform_market_id
LEFT JOIN market_snapshots ms ON ms.market_id = pm.id AND ms.is_current
LEFT JOIN canonical_match_reviews cmr ON cmr.link_id = cml.id
GROUP BY cm.id, ce.title, ce.domain;
```

LLM queries `WHERE trust_tier = 'high'` by default. Confidence never exposed as numeric surface.

---

## The three-timestamp causal-correctness commitment

**Strongest signal in entire three-round review.** Cassandra and Mulder independently arrived at this without seeing each other's argument.

**The lie in waiting:** single `observation_ts` silently means different things per source. ESPN's game_state `observation_ts` = when scraper returned; Kalshi's market_snapshot `observation_ts` = when trade printed; NOAA weather `observation_ts` = when sensor sampled. Collapsing guarantees Phase 4 backtest using "observation_ts <= feature_cutoff" will sometimes leak future information.

**The mitigation:** three timestamps from day one.

| Column | Meaning | Nullability |
|---|---|---|
| `event_occurred_at` | Source-asserted world time | Nullable (sources may not assert) |
| `source_published_at` | When source made it available | Nullable (only when publication lag measurable) |
| `ingested_at` | When we actually learned | NOT NULL |

Phase 4 backtest filters on `source_published_at <= feature_cutoff` for causal correctness, not `event_occurred_at`. These are not interchangeable.

**Non-negotiable.** Cannot be retrofitted from collapsed data.

---

## Alternatives considered and rejected

1. **Views only, no canonical tables.** Rejected — identity must be stable across platform add/remove; views can't be FK targets; LLM surface requires persistent canonical_ids.

2. **Application-layer types, no DB representation.** Rejected — pushes matching into every consumer; forbids audit properties.

3. **Single-tier merge with `is_canonical` boolean on `events`.** Rejected — destroys invariant that every `events` row has platform_id FK; schema reads as lying.

4. **Joined inheritance (Option C) for state.** Rejected — Postgres INHERITS semi-deprecated; psycopg2 CRUD at 30s cadence makes two-table operations regrettable.

5. **Polymorphic JSONB only (Option A) for state.** Rejected — surrenders typed FK/CHECK; A→B migration is lossy (B→A not).

6. **Per-kind sibling tables only (Option B), no fact table.** Rejected — cross-kind queries become UNION; shared invariants drift; Phase 4 rebuilds fact table in application code.

7. **Nullable `markets.canonical_market_id` direct FK.** Rejected (revised from Vader Round 1) — @Whatsonyourmind production data decisive; cannot express M:N, superseded, shadow, quarantined cases.

8. **Resolution-as-canonical (Mulder alternative).** Adopted partially — `resolution_rule_fp` anchors natural-key hash; identity is event+rule together, not event alone.

9. **Rename `markets` → `platform_markets` in Phase 1.** Deferred to post-Phase-3. Prose/ADR text uses `platform_market` naming starting now.

---

## Consequences

**Positive:**
- Phase 4 ML readiness becomes Phase 1 schema property — three timestamps, canonical-event granularity, source attribution, cross-source preservation all expressed now
- Mulder's #935-ghost structurally prevented via `resolution_rule_fp`
- Cross-platform extensibility free at canonical tier (Polymarket, Limitless, pmxt add platform_id values, no canonical migrations)
- Matching decisions first-class audited data — Galadriel's double-counting concern dissolved
- LLM trust_tier lands with schema, not as Task 9 retrofit

**Trade-offs:**
- 22-24 Phase 1 migrations (bundleable to ~15 practical PRs)
- Operational surface area increases (new CRUD, reconciliation job, trust-tier view)
- Dim + fact denormalization introduces drift-detection burden — reconciliation is Phase 1 scope

**Neutral:**
- Non-sport per-kind tables deferred to Phase 3 (except weather Phase 1 prototype per ADR-119)
- `canonical_event_state_consensus` materialized view deferred to Phase 3

---

## Phase commitments

**Phase 1 ships (sessions 71-74):**
- Tables: canonical_events, canonical_markets, canonical_entity, canonical_event_participants, match_algorithm, canonical_market_links, canonical_event_links, canonical_match_log, canonical_match_reviews, canonical_match_overrides, canonical_observations (partitioned), observation_source, canonical_event_phase_log, locations
- Columns: `canonical_events.lifecycle_phase`; nullable `canonical_event_id` on `games`, `game_states`, `temporal_alignment`; `observation_id` on `game_states`
- Views: v_market_canonical, v_temporal_alignment_canonical (if Option A), v_canonical_market_llm, v_unmatched_markets, v_low_confidence_links, v_matching_disagreements
- Seeds: match_algorithm(`manual_v1`), observation_source(`espn`, `kalshi`, `manual`)

**Phase 3 deferred:** weather_observations (moved to Phase 1 via ADR-119), poll_releases, econ_prints, news_events; canonical_event_state_consensus materialized view; keyword_jaccard_v1 algorithm row

**Phase 4+ deferred:** feature-store projection; sub-second alignment; automated matcher; physical rename markets → platform_markets

---

## Implementation order / migration sequence

| # | Intent |
|---|---|
| 0067 | canonical_events + natural_key_hash unique |
| 0068 | canonical_entity + canonical_event_participants |
| 0069 | canonical_markets + natural_key_hash unique |
| 0070 | match_algorithm; seed manual_v1 |
| 0071 | canonical_market_links, canonical_event_links with EXCLUDE |
| 0072 | canonical_match_log (append-only enforcement deferred to 0090) |
| 0073 | canonical_match_reviews, canonical_match_overrides |
| 0074 | observation_source registry; seed espn, kalshi, manual |
| 0075 | locations stub |
| 0076 | canonical_events.lifecycle_phase column |
| 0077 | canonical_event_phase_log |
| 0078 | canonical_observations (partitioned by ingested_at monthly) + indexes |
| 0079 | games.canonical_event_id (nullable) + index |
| 0080 | game_states.canonical_event_id + observation_id (nullable) + async enricher scaffold |
| 0081 | temporal_alignment.canonical_event_id (nullable) + partial index |
| 0082 | temporal_alignment rewire (Option A or B — implementation-session choice) |
| 0083 | Views: v_market_canonical, v_temporal_alignment_canonical, v_canonical_market_llm |
| 0084 | Advisory views: v_unmatched_markets, v_low_confidence_links, v_matching_disagreements |
| 0085 | Seed canonical_events 1:1 from **games** (ESPN-derived, ~3,487 rows — NOT from Kalshi events); seed canonical_markets 1:1 from Kalshi markets; seed canonical_market_links via manual_sports_v1. Sports canonical is entity-framed (every game gets canonical regardless of market coverage); non-sport canonical is market-framed (created when market lists). |
| 0086 | Demote events.uq_events_platform_external → non-unique (#937 folded) |
| 0087 | Demote markets.markets_platform_id_external_id_key |
| 0088 | Demote markets.markets_ticker_key |
| 0089 | Demote idx_series_platform_external_current (preserve SCD-2 partial) |
| 0090 | Trigger-enforce canonical_match_log append-only (after 30-day soak) |

Bundleable to ~6 PR cohorts. Each reversible independently.

ADR-119 continues with 0091-0093 (weather Phase 1).

---

## Rollback plan

Every migration independently reversible. Aggregate rollback path: reverse migration order to 0066. Only data loss is canonical row data and match-log rows (by construction, platform tables retain pre-Phase-1 contracts).

One-way-door inventory: **Option B** for `temporal_alignment` is the only Phase-1 migration rewiring a hot-path writer. If chosen and later regretted, rollback is "re-create table + restore writer + backfill from view output" — non-trivial but non-lossy. Option A rollback is trivial.

---

## Cross-references

- Issue #496 — @Whatsonyourmind production experience (matching ledger founding evidence)
- Epic #935 — ADR-118 subsumes Phase 3 cross-table audit via migrations 0086-0089
- Issue #937 — folded into 0086-0089 (no separate arc)
- Issue #964 — pmxt reference; `market_type_general` adopts NormalizedMarket shape
- ADR-089, ADR-117 — foundational; ADR-118 extends
- ADR-119 — sibling (business-key cleanup + weather Phase 1)
- ADR-120 (future) — Level A vs Level B entity abstraction axis codification
- Pattern 79 — Tier-3 demotion idiom reused in 0086-0089
- Pattern 80 (promotion candidate) — "Level A/B entity abstraction (Additive Canonical Introduction)"

---

## Origin

**Session 70 Task 5**, three rounds of architect council + Mulder's Round 2B skeptical audit + @Whatsonyourmind's #496 production experience.

- **Round 1:** canonical-tier architecture (Holden + Galadriel + Vader; PM synthesis)
- **Round 2B:** matching-schema cardinality; M:N via link table (+ Mulder)
- **Round 3:** event-state layer; three-timestamp convergence (Cassandra + Mulder independent)

PM synthesis preserved highest-signal findings; user directional calls resolved remaining tensions (long-term foundations over velocity; rewire temporal_alignment Phase 1; dim+fact both; universal+type-specific complementary; preserve game_id nullable FK).

Stories told only once, never written down, are stories that die. This one is written down.
