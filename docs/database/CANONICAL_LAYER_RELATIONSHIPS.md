<!-- FRESHNESS: schema as of migration 0084 (V2.45 amendment), session 91 -->

# Canonical Layer Relationships

**Purpose:** the "pointer + map" reference for the canonical layer's relationship structure. Future-self reading this doc cold should be able to derive the architecture's design rationale without re-running the council.

**Pattern 73 SSOT discipline:** this doc is a *map*, not a *rules registry*. All architectural rules (Item 2 boundary test, Item 3 filter discipline, Item 5 view-naming convention, Item 7 `authoritative_for` discipline, Item 9 tagging-pipeline prerequisites, Item 10 framing) live in **ADR-118 V2.46** (`docs/foundation/ARCHITECTURE_DECISIONS.md`). This doc references those rules and depicts the schema shapes that realize them. **No rule text is duplicated here.** When in doubt about a rule, read V2.46.

**Schema authority:** Migration 0084 (V2.45 amendment, PR #1144) is the canonical schema-of-record at the time of writing. Live-DB-grounded shapes verified via `mcp__postgres-dev__query` at session 91. Future migrations may move schema; the freshness marker at top should be refreshed when this doc is re-synced.

---

## Why `canonical_observations` exists, and when the universal/typed split pays off

This section is the most important pedagogical anchor in the doc. The universal-layer / per-kind-table split is the design's most consequential commitment; understanding when it pays off (and when it doesn't) is the difference between V2.46 reading as obvious and V2.46 reading as overengineering.

### Why split (the problem)

If every observation kind kept its canonical-layer columns inline (`observation_kind`, `source_id`, `canonical_primary_event_id`, `payload_hash`, `event_occurred_at`, `source_published_at`, `ingested_at`, `valid_at`, `valid_until`, `created_at`, `updated_at`), each per-kind table would carry **N copies of the same cross-cutting metadata**. They would drift over time as cohorts amend each table independently — different audit columns, different timestamp semantics, different dedup hashes.

Two operations break worse without a universal layer:

1. **`temporal_alignment` cannot have a single FK target without polymorphic FKs (an anti-pattern).** Pre-V2.45 `temporal_alignment` was a sport-specific fat-row table because there was nowhere to point a generic "observation A vs observation B" relationship. With universal `canonical_observations.id`, both `observation_a_id` and `observation_b_id` point at *any* observation type via one consistent FK shape (composite per V2.43 Item 3 partition-key invariant — see Layer 4 below). One ID space; many kinds.

2. **`canonical_observation_event_links` cannot be a single table without a universal observation ID.** If news observations had to link to canonical_events via a `news_canonical_event_links` table, weather observations via `weather_canonical_event_links`, etc., cross-domain queries ("all observations linking to canonical_event 42") become N-way UNIONs. With one universal observation ID, the link table is N-to-M between universal observations and canonical_events — one query, one shape.

### Why split (the gain)

The universal layer enables **cross-kind queries, multi-event tagging, and cross-source dedup** that would otherwise require N-way UNIONs or per-kind link tables. The redesigned `temporal_alignment` (V2.45) is the canonical worked example: alignment edges between *any* two observations regardless of kind, with one schema.

### The trade-off (when it pays off vs when it's overhead)

The universal layer's overhead is paid at *write time* (one INSERT per layer — universal + per-kind projection). Per-domain reads do not pay; they read directly from the per-kind table and never touch `canonical_observations`. The split pays off the first time a query crosses kinds.

**Worked Example A — cross-domain ML feature (split pays off).** Question: *"For each market_snapshot, find the most recent same-game game_state, the latest weather observation within 50 miles of the venue, and the count of news observations about either team in the last hour."*

With the universal layer:

```sql
WITH ms AS (
    SELECT co.id AS obs_id, co.ingested_at, co.canonical_primary_event_id,
           ms.market_id, ms.yes_ask_price
    FROM canonical_observations co
    JOIN market_snapshots ms ON ms.observation_id = co.id  -- Cohort 5+ back-ref
    WHERE co.observation_kind = 'market_snapshot'
      AND co.ingested_at > NOW() - INTERVAL '1 hour'
)
SELECT
    ms.obs_id, ms.yes_ask_price,
    -- aligned game_state via temporal_alignment
    (SELECT gs.home_score - gs.away_score
     FROM temporal_alignment ta
     JOIN canonical_observations co_gs
        ON (ta.observation_b_id, ta.observation_b_ingested_at)
         = (co_gs.id, co_gs.ingested_at)
     JOIN game_states gs ON gs.observation_id = co_gs.id
     WHERE (ta.observation_a_id, ta.observation_a_ingested_at)
         = (ms.obs_id, ms.ingested_at)
       AND co_gs.observation_kind = 'game_state'
     ORDER BY ta.aligned_at DESC LIMIT 1) AS lead,
    -- weather via canonical_observation_event_links
    (SELECT w.temp_f
     FROM canonical_observation_event_links cel
     JOIN canonical_observations co_w
        ON (cel.observation_id, cel.observation_ingested_at)
         = (co_w.id, co_w.ingested_at)
     JOIN weather_observations w ON w.observation_id = co_w.id  -- Cohort 9
     WHERE cel.canonical_event_id = ms.canonical_primary_event_id
       AND co_w.observation_kind = 'weather'
     ORDER BY co_w.ingested_at DESC LIMIT 1) AS temp_f,
    -- news count
    (SELECT COUNT(*) FROM canonical_observation_event_links cel2
     JOIN canonical_observations co_n
        ON (cel2.observation_id, cel2.observation_ingested_at)
         = (co_n.id, co_n.ingested_at)
     WHERE cel2.canonical_event_id = ms.canonical_primary_event_id
       AND co_n.observation_kind = 'news'
       AND co_n.ingested_at > ms.ingested_at - INTERVAL '1 hour') AS news_ct
FROM ms;
```

~30 lines. Adding a 5th signal (a polling observation, an econ print) means adding one subquery — the `canonical_observations` + `canonical_observation_event_links` shape is reusable. Without the universal layer, this query becomes 4 UNION ALLs and a coalesce for "find the latest of any kind" — adding a 5th signal touches every consumer.

**Worked Example B — per-domain query (split is no-cost).** Question: *"Show me the latest game_state for game 42."*

```sql
SELECT * FROM game_states
WHERE game_id = 42 AND row_current_ind = TRUE
ORDER BY row_start_ts DESC LIMIT 1;
```

No `canonical_observations` involvement. The split's overhead is paid at *write time* (the writer also INSERTs a `canonical_observations` row); per-domain reads pay nothing. Operational queries that target a single kind are unchanged.

**Honest framing of the maturity curve.** With 2 active kinds (`game_state`, `market_snapshot`, both currently 0 rows because the writer is feature-flagged off), the split is currently mostly cost. It pays off as soon as a 3rd kind ingests (weather imminent per session 91 user direction) and the first cross-kind query lands. Per-kind table → `canonical_observations` back-reference (the `observation_id` FK on per-kind tables, deferred to Cohort 5+) lets queries go either direction: per-kind table → universal layer for cross-kind enrichment; universal layer → per-kind table for typed columns.

---

## The 5-layer relationship graph

The canonical layer comprises 5 layers (4 main + a sub-layer for audit ledgers introduced via Galadriel's session 91 review). Reading the diagram top-down: identity → typed data → universal observation fact → linkage verbs → audit history.

### ASCII layer diagram (all 5 layers)

```
+---------------------------------------------------------------------------+
| LAYER 1 — Canonical universal (cross-platform, cross-source identity)     |
+---------------------------------------------------------------------------+
| canonical_entity ----+  canonical_event_types     canonical_event_domains |
| (teams, players,     |  (lookup; slot 0071-style) (lookup)                |
|  weather stations,   |        ^                       ^                   |
|  candidates)         |        |                       |                   |
|       ^              |        |                       |                   |
|       |              v        v                       |                   |
|       |   canonical_events  ----------- canonical_event_links             |
|       |   (a football game, an              (binds canonical_events <->  |
|       |    election, a poll release,         platform events;            |
|       |    a weather event,                  source-of-truth for         |
|       |    a news event)                     matcher event-to-platform   |
|       |                                      event binds — Layer 1 ↔     |
|       |                                      Layer 2 connector)          |
|       |        ^                                       ^                 |
|       |        |                                       |                 |
|       v        |                                       v                 |
| canonical_event_participants               canonical_markets             |
| (link table — many-to-many                 (a "Buccaneers win" market   |
|  via canonical_participant_roles            that exists across Kalshi/  |
|  lookup)                                    Polymarket/etc.)            |
|                                                       ^                 |
|                                                       |                 |
|                                                       | canonical_      |
|                                                       | market_links    |
|                                                       | (many-to-many   |
|                                                       v  to platform    |
|                                                                markets) |
+---------------------------------------------------------------------------+

+---------------------------------------------------------------------------+
| LAYER 2 — Per-source typed dim/fact (platform-specific)                   |
+---------------------------------------------------------------------------+
| games (sports dim)               markets (Kalshi dim)                     |
|   - canonical_event_id FK        - canonical_market_id (via _links)       |
|   - typed: home_team_id,         - typed: ticker, title, market_type,     |
|     away_team_id, league,         status, open_time, close_time,          |
|     venue, scheduled_start        expiration_time, outcome_label          |
|        ^                                ^                                 |
|        |                                |                                 |
|        v                                v                                 |
| game_states (SCD-2 fact)          market_snapshots (SCD-2 fact)           |
|   - game_id FK                     - market_id FK                         |
|   - canonical_event_id FK          - typed: yes_ask_price, no_ask_price,  |
|     (slot 0080)                      spread, volume                       |
|   - typed: home_score,             - SCD-2: row_current_ind,              |
|     away_score, period, clock,       row_start_ts, row_end_ts             |
|     game_status                                                           |
|   - JSONB residue: situation,                                             |
|     linescores                                                            |
|   - SCD-2: row_current_ind,                                               |
|     row_start_ts, row_end_ts                                              |
|                                                                           |
| market_trades (Kalshi exhaust — SIBLING OUTSIDE canonical_observations)   |
|   - external_trade_id, market_id, count, yes_price, no_price,             |
|     taker_side, trade_time                                                |
|   - **NOT** an observation_kind per V2.46 Item 2 + path (d) (issue N4):   |
|     gains direct canonical_event_id FK in Cohort 5+ alongside trade       |
|     poller activation (mirrors slot 0080 pattern)                         |
|                                                                           |
| Future Layer 2 siblings (Cohort 5+ / 9):                                  |
|   weather_observations + (location-association mechanism TBD)             |
|   poll_releases, econ_prints, news_events                                 |
|   *(table names above are placeholders matching V2.45 narrative shape;    |
|    final per-kind projection-table names belong to per-cohort design)*    |
+---------------------------------------------------------------------------+

+---------------------------------------------------------------------------+
| LAYER 3 — Universal observation fact (cross-source, cross-kind)           |
+---------------------------------------------------------------------------+
| canonical_observations (RANGE-partitioned by ingested_at; 4 monthly       |
|                          partitions May-Aug 2026; composite PK            |
|                          (id, ingested_at) per V2.43 Item 3)              |
|   - id BIGSERIAL                                                          |
|   - observation_kind VARCHAR (CHECK: 'game_state'|'weather'|'poll'|       |
|                                       'econ'|'news'|'market_snapshot')    |
|   - source_id BIGINT FK -> observation_source                             |
|   - canonical_primary_event_id BIGINT NULLABLE                            |
|     (denormalized "primary tag" — mirrors link_kind='primary' row in      |
|      canonical_observation_event_links; reconciler asserts agreement)     |
|   - payload_hash BYTEA (dedup; no payload column post-V2.45)              |
|   - event_occurred_at, source_published_at, ingested_at, valid_at,        |
|     valid_until, created_at, updated_at                                   |
|        ^                                       ^                          |
|        | composite FK                          | composite FK             |
|        | (observation_id,                      | (observation_id,         |
|        |  observation_ingested_at)             |  observation_ingested_at)|
|        v                                       v                          |
| canonical_observation_event_links            (Cohort 5+) per-kind tables  |
| (slot 0084 NEW — many-to-many tagging)         get observation_id back-   |
|   - observation_id BIGINT                      ref FK (-> canonical_      |
|   - observation_ingested_at TZ                 observations)              |
|   - canonical_event_id BIGINT                                             |
|     -> canonical_events (ON DELETE RESTRICT)                              |
|   - link_kind VARCHAR (CHECK: 'primary'|'secondary'|'derived'|            |
|                                'speculative')                             |
|   - confidence NUMERIC(5,4) (NULL or 0..1)                                |
|   - linked_at, linked_by                                                  |
|   - PK: (observation_id, observation_ingested_at, canonical_event_id)     |
|     [composite per V2.43 Item 3 invariant flow-through]                   |
|   - partial UNIQUE: (observation_id, observation_ingested_at)             |
|       WHERE link_kind = 'primary'                                         |
|         (one primary per observation, mirrors                             |
|          canonical_primary_event_id invariant)                            |
+---------------------------------------------------------------------------+

+---------------------------------------------------------------------------+
| LAYER 4 — Linkage / relationship verbs                                    |
+---------------------------------------------------------------------------+
| temporal_alignment (V2.45 redesigned — pure linkage; no domain typed cols)|
|   - id BIGSERIAL PK                                                       |
|   - observation_a_id BIGINT, observation_a_ingested_at TZ                 |
|     [composite FK -> canonical_observations(id, ingested_at);             |
|      ON DELETE NO ACTION default — see N3 deferred for harmonization]     |
|   - observation_b_id BIGINT, observation_b_ingested_at TZ                 |
|     [composite FK; same shape as observation_a]                           |
|   - canonical_event_id BIGINT NULLABLE -> canonical_events                |
|     (ON DELETE SET NULL; denormalized hot-path lookup)                    |
|   - time_delta_seconds NUMERIC(10,3)                                      |
|   - alignment_quality VARCHAR (CHECK: 'exact'|'good'|'fair'|'poor'|       |
|                                        'stale')                           |
|   - aligned_at, created_at                                                |
|   - UNIQUE: (observation_a_id, observation_a_ingested_at,                 |
|              observation_b_id, observation_b_ingested_at)                 |
|     [4-column composite per V2.43 Item 3 invariant flow-through]          |
|   - CHECK ck_distinct_observations:                                       |
|       NOT (observation_a_id = observation_b_id                            |
|            AND observation_a_ingested_at = observation_b_ingested_at)     |
|                                                                           |
| Views (Cohort 5+):                                                        |
|   v_temporal_alignment            — base view, no typed cols              |
|   v_temporal_alignment_sports     — JOINs to game_states + market_        |
|                                      snapshots for typed sports cols     |
|   v_temporal_alignment_weather    — when weather lands (ADR-119 P1)       |
|   v_temporal_alignment_election   — Phase 3+                              |
+---------------------------------------------------------------------------+

+---------------------------------------------------------------------------+
| LAYER 4.5 — Audit ledgers (Galadriel session 91 sub-layer carve-out)      |
+---------------------------------------------------------------------------+
| canonical_match_log (slot 0073)                                           |
|   - audit ledger of matcher decisions                                     |
|   - per-decision: observation evidence, match_algorithm, action,          |
|     confidence, evidence                                                  |
|                                                                           |
| canonical_match_overrides + canonical_match_reviews (slot 0074)           |
|   - human-in-the-loop: operator overrides + matcher review queue          |
|                                                                           |
| canonical_event_phase_log (slot 0079)                                     |
|   - audit ledger of canonical_event lifecycle phase transitions           |
|   - shipped columns: id, canonical_event_id, previous_phase, new_phase,   |
|     transition_at, changed_by, note, created_at                           |
|   - (Cohort 5+ N3 future addition: evidence_observation_id BIGINT NULL FK |
|     to canonical_observations with ON DELETE SET NULL — preserves         |
|     session-90 input-memo intent; not yet present on the live table)      |
|                                                                           |
| Forward-growth notes (Cohort 5+):                                         |
|   reconciler-results audit table (per V2.43 Item 4 commitment;            |
|     canonical_reconciliation_results dedicated table — Cohort 5+ alongside|
|     reconciler manual-CLI slot)                                           |
|   observation-projection-audit (if reconciler discovers per-kind          |
|     projection drift — speculative)                                       |
+---------------------------------------------------------------------------+
```

### Layer commentary

- **Layer 1** is *identity*: the canonical-layer answer to "what entity / event / market are we talking about, regardless of which platform talks about it?" Lookup tables (`canonical_entity_kinds`, `canonical_event_types`, `canonical_event_domains`, `canonical_participant_roles`) are Pattern 81 SSOT homes for vocabulary. Verb tables here (`canonical_event_links`, `canonical_market_links`, `canonical_event_participants`) connect the canonical entities/events/markets to each other and (via the platform-specific side) to Layer 2.
- **Layer 2** is *typed data*: per-source dim + fact pairs. Dim tables (`games`, `markets`) get a single row per platform-specific entity; fact tables (`game_states`, `market_snapshots`) get SCD-2-versioned rows per state-change. `market_trades` is a Layer-2 sibling **outside** the `canonical_observations` vocabulary per V2.46 Item 2 + path (d) — the principle "not every Layer-2 typed-table participates in the canonical_observations vocabulary" is load-bearing for Item 2's boundary discipline.
- **Layer 3** is *universal observation fact*: one ID space across kinds, partitioned by ingest time, composite PK to enable partition routing. Two FK back-edges (multi-event tagging via `canonical_observation_event_links`; per-kind back-references via Cohort 5+ `observation_id` columns on per-kind tables).
- **Layer 4** is *linkage*: pure relationship verbs, no domain typed columns. Pure-linkage discipline established by V2.45's `temporal_alignment` redesign.
- **Layer 4.5** is *audit*: ledgers of decisions and lifecycle transitions. Carved out from Layer 4 because audit ledgers are *cross-cutting metadata about other layers' operations*, not relationship verbs between entities. Naming the sub-layer keeps Layer 4's verb category tight and gives audit ledgers a natural home for future expansion (e.g., reconciler-results table per V2.43 Item 4).

---

## Three example query traversals

Three worked examples, ordered by frequency-of-use. Examples 1 + 3 demonstrate canonical-layer reads against currently-empty tables — the queries are correctly-shaped against Migration 0084 schema, and will return rows once writers activate post-Cohort-5+. Example 2 is forward-looking + illustrative-only.

### Example 1 — Cross-kind alignment query

> *"Find all market prices when the home team was up by 14+, for canonical_event 42."*

This exercises Layer 1 → Layer 4 → Layer 3 → Layer 2 in a non-trivial multi-domain JOIN. The composite-FK shape (V2.43 Item 3 invariant) is the load-bearing detail.

```sql
-- 1. Start: canonical_event 42 (Layer 1)
-- 2. canonical_event_links -> which platform markets does this event touch?
-- 3. For each, find market_snapshots (Layer 2)
-- 4. For each market_snapshot, find aligned game_states via temporal_alignment (Layer 4)
-- 5. Filter where home_score - away_score >= 14
-- 6. Return prices + scores at those alignment moments
SELECT
    co_ms.ingested_at AS snapshot_at,
    ms.yes_ask_price,
    gs.home_score, gs.away_score, gs.period, gs.clock,
    ta.time_delta_seconds, ta.alignment_quality
FROM canonical_event_links cel
JOIN canonical_markets cm ON cm.id = cel.canonical_market_id
JOIN canonical_market_links cml ON cml.canonical_market_id = cm.id
JOIN markets m ON m.id = cml.platform_market_id
JOIN market_snapshots ms ON ms.market_id = m.id
JOIN canonical_observations co_ms
    ON co_ms.id = ms.observation_id  -- Cohort 5+ back-ref FK
JOIN temporal_alignment ta
    ON (ta.observation_a_id, ta.observation_a_ingested_at)
     = (co_ms.id, co_ms.ingested_at)            -- composite FK shape
JOIN canonical_observations co_gs
    ON (co_gs.id, co_gs.ingested_at)
     = (ta.observation_b_id, ta.observation_b_ingested_at)  -- composite FK shape
JOIN game_states gs ON gs.observation_id = co_gs.id  -- Cohort 5+ back-ref FK
WHERE cel.canonical_event_id = 42
  AND co_gs.observation_kind = 'game_state'
  AND (gs.home_score - gs.away_score) >= 14
ORDER BY co_ms.ingested_at;
```

Notes:

- The JOINs at lines 11-13 + 15-16 use **composite-FK syntax** `(id, ingested_at)` against the partitioned `canonical_observations` PK. Single-column JOINs against the universal-layer ID alone would not match the composite PK and would fail at query-plan time — this is the load-bearing schema-truth detail Holden's D1 finding caught.
- `ms.observation_id` and `gs.observation_id` are **Cohort 5+ back-reference FKs** (not yet shipped at session 91). Until they ship, the query has to JOIN through `canonical_primary_event_id` or use `ingested_at` proximity heuristics. The Cohort 5+ back-reference simplifies the query.
- `temporal_alignment.canonical_event_id` is the denormalized hot-path lookup — when present, queries can pre-filter alignments by `WHERE ta.canonical_event_id = 42` to avoid joining through the full Layer-1 chain. Example 3 demonstrates this hot path.

### Example 2 — Multi-event tagging query (illustrative-only)

> *"What news fired in the 5 minutes before this market move?"*

**Caveat (V2.46 + Galadriel review):** this example is *illustrative only*. The news tagging pipeline does not exist yet (Item 9 cohort sequencing places news last per tagging-complexity ramp). The example shows the *shape that will work once tagging ships*. Future readers should not treat this as a binding contract for the news pipeline's implementation.

```sql
-- 1. Start: market_snapshot showing the move (canonical_observation id = 7891)
-- 2. JOIN through canonical layer to find related canonical_events
-- 3. Query canonical_observations for news kind in 5-min window pre-move
-- 4. Multi-event semantics via canonical_observation_event_links
-- 5. JOIN news_events for typed news columns (Cohort 5+ projection table)
WITH market_move AS (
    SELECT id, ingested_at, canonical_primary_event_id
    FROM canonical_observations
    WHERE id = 7891 AND observation_kind = 'market_snapshot'
)
SELECT
    co_n.id, co_n.ingested_at, co_n.source_id,
    ne.headline, ne.body, ne.entities_mentioned,
    cel.confidence
FROM market_move mm
JOIN canonical_observation_event_links cel
    ON cel.canonical_event_id = mm.canonical_primary_event_id
JOIN canonical_observations co_n
    ON (co_n.id, co_n.ingested_at)
     = (cel.observation_id, cel.observation_ingested_at)  -- composite FK
JOIN news_events ne ON ne.observation_id = co_n.id  -- Cohort 5+ projection
WHERE co_n.observation_kind = 'news'
  AND co_n.ingested_at BETWEEN mm.ingested_at - INTERVAL '5 minutes'
                           AND mm.ingested_at
ORDER BY co_n.ingested_at;
```

The multi-event semantics via `canonical_observation_event_links` is what makes news traversal work: a single news observation about "Buccaneers" can link to canonical_events for every Buccaneers game scheduled in the next week (one row per link). The denormalized `canonical_primary_event_id` on `canonical_observations` mirrors the `link_kind = 'primary'` row enforced by the partial UNIQUE index `idx_link_one_primary_per_observation`. The full operational semantic of the 4 `link_kind` values (`primary` / `secondary` / `derived` / `speculative`) is deferred to per-cohort tagger design — V2.46 ships the CHECK constraint vocabulary but does not codify per-value meaning beyond `primary`'s mirror invariant.

### Example 3 — Within-event temporal alignment (the hot path)

> *"Find all aligned game_state + market_snapshot pairs for canonical_event 42 in the last 5 minutes."*

This exercises the denormalized `canonical_event_id` on `temporal_alignment` — the V2.45 redesign's most pedagogically central design choice. Without the denormalized column, this query has to JOIN through Layer 1 + Layer 3; with it, the index `idx_alignment_canonical_event(canonical_event_id, aligned_at DESC)` makes it a single-table scan.

```sql
-- Hot path: pre-filter by denormalized canonical_event_id, then resolve
-- typed columns from per-kind projection tables.
SELECT
    ta.aligned_at, ta.time_delta_seconds, ta.alignment_quality,
    gs.home_score, gs.away_score, gs.period, gs.clock,
    ms.yes_ask_price, ms.no_ask_price
FROM temporal_alignment ta
-- resolve observation A (game_state)
JOIN canonical_observations co_a
    ON (co_a.id, co_a.ingested_at)
     = (ta.observation_a_id, ta.observation_a_ingested_at)
JOIN game_states gs ON gs.observation_id = co_a.id  -- Cohort 5+ back-ref
-- resolve observation B (market_snapshot)
JOIN canonical_observations co_b
    ON (co_b.id, co_b.ingested_at)
     = (ta.observation_b_id, ta.observation_b_ingested_at)
JOIN market_snapshots ms ON ms.observation_id = co_b.id  -- Cohort 5+ back-ref
WHERE ta.canonical_event_id = 42
  AND ta.aligned_at > NOW() - INTERVAL '5 minutes'
  AND co_a.observation_kind = 'game_state'
  AND co_b.observation_kind = 'market_snapshot'
ORDER BY ta.aligned_at DESC;
```

Index hits: `idx_alignment_canonical_event(canonical_event_id, aligned_at DESC)` answers `WHERE ta.canonical_event_id = 42 AND ta.aligned_at > ...` in one index scan, returning a small candidate set. The composite-FK JOINs to `canonical_observations` then resolve each candidate's typed columns via the per-kind projection tables. **This is why the split pays off:** the same shape works for sports (game_state × market_snapshot), weather (weather × market_snapshot), election (poll × market_snapshot) — one universal query plan, multiple typed projections.

The without-split alternative (separate `temporal_alignment_sports`, `_weather`, `_election` tables, each with sport/weather/election-specific typed columns inline) requires consumers to either know which alignment-table to query, or write a UNION ALL across all of them. Adding a 4th domain (election polls × prediction markets) is one new alignment-table; with the universal layer, it's one new per-kind projection back-reference and zero new query shapes.

---

## Verb-table catalog

The canonical layer's relationship-verb tables, separated from the audit-ledger sub-layer per Galadriel's session 91 review.

### Layer 4 — Verb tables (5 tables)

| Verb table | Connects | Multiplicity | Source of truth for |
|---|---|---|---|
| `canonical_event_participants` | `canonical_entity` ↔ `canonical_events` (via `canonical_participant_roles` lookup) | many-to-many | which entities participate in which events, and in what role |
| `canonical_event_links` | `canonical_events` ↔ platform events (`platform_event_id`) | many-to-many | matcher-confirmed event-to-platform-event binding (Layer 1 ↔ Layer 2 connector; canonical_events ↔ canonical_markets is reached transitively via this table → `markets` → `canonical_market_links`) |
| `canonical_market_links` | `canonical_markets` ↔ `markets` (platform) | many-to-many | matcher-confirmed market-platform binding |
| `canonical_observation_event_links` (slot 0084 NEW) | `canonical_observations` ↔ `canonical_events` (composite FK) | many-to-many | multi-event tagging (news fans out; econ prints span markets) |
| `temporal_alignment` (slot 0084 redesigned) | `canonical_observations` ↔ `canonical_observations` (composite FKs both sides) | many-to-many (via observation_a × observation_b) | continuous-stream pairing by time proximity within a tolerance window |

### Layer 4.5 — Audit ledgers (4 tables)

| Audit ledger | Records | Lifecycle |
|---|---|---|
| `canonical_match_log` (slot 0073) | matcher decisions (per-decision evidence, algorithm, action, confidence) | append-only |
| `canonical_match_overrides` (slot 0074) | operator overrides of matcher decisions | append-only with `superseded_at` semantics |
| `canonical_match_reviews` (slot 0074) | matcher review queue entries (human-in-the-loop) | mutable status field |
| `canonical_event_phase_log` (slot 0079) | canonical_event lifecycle phase transitions (transition_at, previous_phase, new_phase, changed_by, note) | append-only (N3 future ADD: evidence_observation_id FK) |

### Forward growth notes (Cohort 5+ candidates)

These are *possible* future additions, not commitments. Naming convention is illustrative; real names belong in per-cohort design.

- **`canonical_event_resolution_evidence`** (Phase 4-5 candidate) — linking events to the observations that finally resolve them. Sits in Layer 4 if treated as a verb table (event ↔ resolution-evidence-observation), or Layer 4.5 if treated as an audit ledger of resolution decisions. Cohort design adjudicates.
- **Per-domain participant-role refinements** (e.g., `canonical_event_role_participants` for richer entity-event participation than the current `canonical_participant_roles` lookup admits) — Layer 4 verb table. Speculative.
- **`canonical_reconciliation_results`** (already committed per V2.43 Item 4; ships in Cohort 5+ alongside reconciler manual-CLI slot) — Layer 4.5 audit ledger. Carries reconciler outputs (anomaly count, severity, source/projection hashes, reconciled_at).

The catalog stays **tight on current state** rather than carrying placeholder rows. New additions get cataloged when they ship.

---

## Cross-references

- **Architectural rules:** ADR-118 V2.46 § "Changes in v2.46:" (Items 2/3/5/7/9/10 + cross-cutting findings CC1/CC2/CC3 + N1-N5 deferred backlog) — `docs/foundation/ARCHITECTURE_DECISIONS.md`
- **Schema authority:** Migration 0084 (V2.45 ratified, PR #1144) — `src/precog/database/alembic/versions/0084_canonical_layer_redesign.py`
- **Schema summary:** `docs/database/DATABASE_SCHEMA_SUMMARY_V2.4.md` (post-Migration 0084 refresh; canonical home for table-by-table shape inventory)
- **V2.46 design-review pipeline:** `memory/design_review_v246_synthesis.md` (PM synthesis + user adjudications, binding) + `memory/design_review_v246_galadriel_memo.md` + `memory/design_review_v246_holden_memo.md` + `memory/design_review_v246_input_memo.md` (session 90 architectural reasoning capture)
- **Patterns referenced:** Pattern 6 (Immutable Versioning — by analogy for Item 9e re-tagging), Pattern 73 (SSOT — Items 7 + 9 + CC2), Pattern 84 (NOT VALID + VALIDATE — N4 future migration shape), Pattern 86 (Living-Doc Freshness Markers — top of this doc), Pattern 87 (Append-only Migrations — V2.46 ships zero edits to migrations 0001-0084)

---

**END OF CANONICAL_LAYER_RELATIONSHIPS.md**
