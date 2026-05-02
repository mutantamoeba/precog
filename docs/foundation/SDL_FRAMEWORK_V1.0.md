# Strategy Development Lifecycle (SDL) Framework V1.0

<!-- FRESHNESS: alembic_head=N/A; last_session=88; last_audit=session-88; t_types=T43-T54; s_triggers=S83-S87; c_triggers=C32-C41 -->

**Document Type:** Foundation
**Status:** Active (V1.0 — initial canonicalization)
**Version:** 1.0
**Created:** 2026-05-02 (session 88)
**Last Updated:** 2026-05-02
**Origin:** GitHub issue [#1126](https://github.com/mutantamoeba/precog/issues/1126) — promotion of ad-hoc SDL stage map to canonical project process.

---

## 1. Purpose & Scope

### 1.1 Why SDL exists

The Strategy Development Lifecycle (SDL) is the canonical process for taking a new trading strategy from idea to live capital deployment to retirement post-mortem. Before this framework was canonicalized, strategy work followed two parallel paths:

- **Ad-hoc path** (T16/T17/T18/T19): research → design → implement → backtest, with no enforced gates and no formal post-mortem when strategies failed.
- **SDL-formal path** (T43-T47 + reused T18/T19): structured stages 1-5 with council-style design review, but stages 6-9 (implementation, validation, paper, live) reused the ad-hoc T-types without explicit gates.

Three industry-standard stages were missing: **out-of-sample / walk-forward validation**, **staged-capital rollout**, and **formal post-mortem after retirement**. SDL Framework V1.0 fills those gaps and elevates the structured path to the canonical default for all new strategies.

### 1.2 Scope

This document covers:

- The 9 SDL stages and 3 gates (Section 2)
- Targeted vs autonomous SDL framing modes (Section 3)
- Generalization across event types: sports / weather / politics / econ / entertainment / crypto / other (Section 4)
- Cross-references to canonical trigger definitions, ADRs, and the artifact directory (Section 5)
- Two complete walkthroughs — one autonomous, one targeted (Section 6)
- Out-of-scope items deferred to follow-on issues (Section 7)

### 1.3 Pattern 73 SSOT compliance

This document **references** trigger definitions; it does not duplicate them. Canonical trigger definitions live in `memory/roster_triggers.md`. This document cites trigger IDs (e.g., T52, S83, C40) and provides one-line summaries; full specifications stay in the roster file. Edits to trigger definitions go in the roster, not here.

### 1.4 Replaces / supersedes

- The ad-hoc T16-T19 path is **not retired** — it remains the path for iteration on existing strategies. SDL is the canonical path for **new** strategies.
- T43-T47 (existing SDL stages 1-5) are **retained unchanged** and now sit inside the larger 9-stage framework.

---

## 2. SDL Stages and Gates

The lifecycle has **9 stages** and **3 gates**. Stages 1-5 are design/analysis; stages 6-9 are implementation/operations. Gates fire between stages and are explicit go/no-go checkpoints.

```
Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5
(T43)     (T44)     (T45)     (T46)     (T47)
                                                 → [GATE 1: C32]
Stage 6 → Stage 7 → [GATE 2: C33] → Stage 8 → [GATE 3: C24] → Stage 9
(T18+T22) (T19+T52)                  (paper)                   (T49+T48+T50+T51+T54)
```

### Stage 1 — Research & Discovery

| Field | Value |
|---|---|
| **T-trigger** | T43 |
| **Primary agents** | Jorge (completeness audit), Joe Chip (assumption decay), Hari (data quality) |
| **Reviewer** | Librarian (cross-references) |
| **Artifact** | `docs/sdl/SDL-NNN/01_t43-research_YYYY-MM-DD.md` |
| **Goal** | Audit existing docs, identify data gaps, characterize market structure for the target event type/category. |

### Stage 2 — Ideation & Brainstorm

| Field | Value |
|---|---|
| **T-trigger** | T44 |
| **Primary agents** | Full Strategist Council (Thrawn lead) + Pilot + Louise (Modeler consultants) |
| **Reviewer** | Scorpius + Armitage (risk sketches) |
| **Artifact** | `docs/sdl/SDL-NNN/02_t44-ideation_YYYY-MM-DD.md` |
| **Goal** | Generate candidate strategy hypotheses; produce 3-7 distinct concepts for downstream challenge. |

### Stage 3 — Challenge & Red Team

| Field | Value |
|---|---|
| **T-trigger** | T45 |
| **Primary agents** | Tagomi (lead contrarian), Slartibartfast (metrics), Daneel (model feasibility) |
| **Reviewer** | Scorpius + Armitage + Marvin |
| **Artifact** | `docs/sdl/SDL-NNN/03_t45-redteam_YYYY-MM-DD.md` |
| **Goal** | Kill / merge / rank the hypotheses. The top 1-2 survive to Stage 4. |

### Stage 4 — Model-Strategy Co-Design

| Field | Value |
|---|---|
| **T-trigger** | T46 |
| **Primary agents** | Thrawn + Robin (strategy) + Full Modeler Council (Daneel lead) |
| **Reviewer** | Vader (architecture) |
| **Artifact** | `docs/sdl/SDL-NNN/05_t46-codesign_YYYY-MM-DD.md` |
| **Goal** | Define the model→strategy interface. What does the model output? What does the strategy consume? Will the interface survive new sports / event types / model classes? |

### Stage 5 — Formal Specification

| Field | Value |
|---|---|
| **T-trigger** | T47 |
| **Primary agents** | Scheherazade (write), Thrawn (strategy review), Daneel (model review) |
| **Reviewer** | Vader (architecture) |
| **Artifact** | `docs/sdl/SDL-NNN/06_t47-spec_YYYY-MM-DD.md` (cross-references `docs/foundation/ARCHITECTURE_DECISIONS.md` for the issued ADR) |
| **Goal** | Produce the canonical strategy spec, model spec, and ADR. This is the input to Gate 1. |

### **GATE 1 — SDL Feasibility Gate**

| Field | Value |
|---|---|
| **C-trigger** | C32 |
| **Council** | Deep Thought, Ghanima, Miles, Scorpius |
| **Artifact** | `docs/sdl/SDL-NNN/04_c32-gate1_YYYY-MM-DD.md` |
| **Decision** | Go / No-Go / Revise |
| **Question per agent** | Deep Thought: "Are we solving the right problem?" Ghanima: "Requirements complete?" Miles: "Can a 1-person team build AND maintain this?" Scorpius: "Ruin probability?" |

If Gate 1 returns Revise, the cycle loops back to Stage 4 or Stage 5. If No-Go, the cycle is **archived as `retired-pre-build`** in `docs/sdl/SDL-INDEX.md`. If Go, proceed to Stage 6.

### Stage 6 — Strategy & Model Implementation

| Field | Value |
|---|---|
| **T-triggers** | T18 (strategy code) + T22 (model training pipeline) |
| **Primary agents** | Samwise / Kassad (strategy), Nagilum / Case (model) |
| **Reviewer** | Glokta + Joe Chip |
| **Sentinel** | Hermione + Marvin |
| **Artifact** | Code in repo + `docs/sdl/SDL-NNN/07_t19-backtest_YYYY-MM-DD.md` precursor docs |
| **Goal** | Code the designed strategy and model per the Stage 5 spec. |

### Stage 7 — Backtest + OOS Validation

| Field | Value |
|---|---|
| **T-triggers** | T19 (backtest) + **T52 (out-of-sample / walk-forward — NEW V1.0)** |
| **Primary agents** | Nagilum / Amos (T19 framework), Daneel + Slartibartfast (T52) |
| **Reviewer** | Slartibartfast (right metric?) + Spock (T19); Joe Chip (T52) |
| **Sentinel** | Ripley |
| **Pre-work S-triggers** | **S83 (Look-ahead / data-leakage check — NEW V1.0)** fires on any backtest claim |
| **Artifacts** | `docs/sdl/SDL-NNN/07_t19-backtest_YYYY-MM-DD.md`, `docs/sdl/SDL-NNN/08_t52-oos_YYYY-MM-DD.md` |
| **Goal** | Backtest establishes in-sample edge; T52 validates that edge survives on held-out data with a walk-forward window and parameter sensitivity matrix. |

### **GATE 2 — SDL Deployment Gate**

| Field | Value |
|---|---|
| **C-trigger** | C33 |
| **Council** | 6 agents, hierarchical. **Sub-A Risk:** Scorpius + Armitage + Glokta. **Sub-B Readiness:** Ghanima + Miles + Hermione. |
| **Artifact** | `docs/sdl/SDL-NNN/09_c33-gate2_YYYY-MM-DD.md` |
| **Decision** | Go / No-Go / Revise |
| **Question per sub-council** | Sub-A: "Failure modes? Hidden risks? Security holes?" Sub-B: "Requirements met? Operationally feasible? Tests sufficient?" |

If Gate 2 returns Revise, loop to Stage 6 or Stage 7. If Go, proceed to Stage 8 (paper trading). The strategy is **paper status** after Gate 2.

### Stage 8 — Paper Trading

| Field | Value |
|---|---|
| **T-trigger** | (Continuous; no single T-trigger — supervised by recurring T49) |
| **Primary agents** | Strategy + position-management code, with operator monitoring. Slartibartfast + Joe Chip review weekly. |
| **Sentinel periodic** | T49 (weekly strategy performance review) fires at every weekly cadence |
| **Artifact** | `docs/sdl/SDL-NNN/10_paper-trading-log/` (subdirectory of weekly logs) |
| **Goal** | Verify live-vs-backtest deviation is within acceptable bounds before risking real capital. |

### **GATE 3 — Paper-to-Real-Money Gate**

| Field | Value |
|---|---|
| **C-trigger** | C24 |
| **Council** | Thrawn, Scorpius, Armitage, Glokta, Ghanima, Miles, Marvin |
| **Artifact** | `docs/sdl/SDL-NNN/11_c24-gate3_YYYY-MM-DD.md` |
| **Decision** | Go / No-Go / Revise |
| **Question per agent** | Thrawn: edge confirmed? Scorpius: failure modes characterized? Armitage: hidden assumptions audited (refuses to sign off until explained)? Glokta: order path adversarial-tested? Ghanima: requirements met? Miles: 1-person operationally feasible? Marvin: "37 ways it fails at 3 AM"? |

If Gate 3 returns Go, proceed to Stage 9 with a **staged-capital rollout** (T53 — NEW V1.0).

### Stage 9 — Live Trading + Operations

Stage 9 is itself a sub-pipeline because it spans the entire live lifetime of the strategy. It has the following components:

#### Stage 9a — Staged-Capital Rollout (T53 — NEW V1.0)

| Field | Value |
|---|---|
| **T-trigger** | T53 |
| **Primary agents** | Scorpius (ruin-prob at new tier), Miles (operational scale at new tier) |
| **Pre-work S-trigger** | **S84 (Capital-tier change — NEW V1.0)** fires on every tier ramp |
| **Artifact** | `docs/sdl/SDL-NNN/12_t53-capital-ramps/<tier>_YYYY-MM-DD.md` per ramp |
| **Goal** | Ramp capital exposure in stages: **5% → 25% → 50% → 100%**, with explicit duration gates (e.g., minimum N trading days at each tier before promotion). Each tier promotion is its own T53 instance. |

#### Stage 9b — Recurring Periodic Reviews

| T-trigger | Cadence | Primary agents |
|---|---|---|
| T48 (Model performance review) | Weekly/monthly | Hari + Armitage; Joe Chip reviewer |
| T49 (Strategy performance review) | Weekly/monthly | Slartibartfast + Joe Chip; Armitage reviewer |
| T50 (Model retraining cycle) | Per drift signal or scheduled | Daneel + Louise; Armitage + Scorpius reviewers; Hermione sentinel before promotion |

Pre-work S-triggers active during Stage 9:

- **S86 (Regime-change detection — NEW V1.0)**: fires when strategy/model performance shifts >2σ from baseline. Specialists: Cassandra + Anderton. **Pre-positioned**, activates when first strategy is live.
- **S87 (Cross-strategy correlation / book exposure — NEW V1.0)**: fires when adding strategy N≥2 to live book. Specialists: Pilot + Carter. **Dormant** in single-strategy phase.

Calendar-driven C-triggers active during Stage 9:

- **C34** (Quarterly Strategy Review) — full review of all live strategies every ~3 months.

#### Stage 9c — Strategy Retirement

| Field | Value |
|---|---|
| **T-trigger** | T51 |
| **Primary agents** | Thrawn (assessment), Tagomi (bear case for keeping) |
| **Reviewer** | Miles (operational impact) |
| **Artifact** | `docs/sdl/SDL-NNN/14_t51-retirement_YYYY-MM-DD.md` |
| **Goal** | Retire the strategy from live trading. Archive code + spec; update `SDL-INDEX.md` to status `retired`. |

#### Stage 9d — Retirement Post-Mortem (T54 — NEW V1.0)

| Field | Value |
|---|---|
| **T-trigger** | T54 |
| **Primary agents** | Deckard (forensic — trace what failed), Hari (statistical signal decay), Tagomi (counterfactual) |
| **Author** | Scheherazade |
| **Pre-work S-trigger** | **S85 (Retired-strategy autopsy — NEW V1.0)** fires on every T54 |
| **Artifact** | `docs/sdl/SDL-NNN/15_t54-postmortem_YYYY-MM-DD.md` |
| **Goal** | Capture the lessons. What signal decayed? Was the original edge real? What would we do differently? Feeds future SDL cycles. |

After T54 completes, **C41 (Post-retirement SDL trigger — NEW V1.0)** auto-queues a new T43 (Stage 1) if no replacement strategy is in the pipeline.

---

## 3. Targeted vs Autonomous SDL Framing

The framing mode is set at Stage 1 via the `SDL_MODE` parameter (recorded in `_CYCLE.md`). The mode affects how broad Stages 1-3 explore.

| Mode | Description | Use case | Council framing |
|---|---|---|---|
| **Autonomous** | Council brainstorms broadly across the project's full event-type taxonomy. Deep Thought + Tagomi premise-question heavy. | Periodic discovery (quarterly C40 kickoff). | Thrawn lead with full Strategist Council; Modelers consult on feasibility for each candidate. |
| **Targeted-by-market** | User constrains the cycle to a specific event type / market category (e.g., "weather strategies for Northeast US winter"). | User has a hypothesis about a market category. | Strategist Council scopes to the constrained market; data-quality (Hari) front-loaded. |
| **Targeted-by-strategy-type** | User constrains to a strategy genre (mean-reversion, momentum, news-arbitrage, calendar-arb, etc.). | User wants to expand a known strategy genre into new event types. | Strategist Council generates within the genre constraint; Tagomi adversarial on whether the genre fits. |
| **Hybrid (loose framing)** | User provides loose constraint; council explores within. | Most common manual-trigger mode. | Council interprets the constraint and produces 3-7 candidates spanning the constraint envelope. |

The framing **persists** as part of `_CYCLE.md` metadata. Default cadence: quarterly autonomous SDL via C40 + ad-hoc targeted SDL whenever a hypothesis emerges from operator monitoring.

---

## 4. Generalization Across Event Types

The SDL stages themselves are **event-type-agnostic**. The framework applies identically to:

| Event type | Examples |
|---|---|
| **Sports** | NFL, NCAAF, NBA, NHL, MLB, soccer, UFC, tennis, golf, esports |
| **Weather** | Hurricane landfall, hurricane category, snowfall thresholds, temperature records |
| **Politics** | Elections (federal/state/local), policy markets, polling-aggregator-driven |
| **Econ** | FRED-driven (rate decisions, jobs reports), BLS data, GDP releases |
| **Entertainment** | Box office, awards (Oscars/Emmys/Grammys), TV ratings |
| **Crypto** | Block-time markets, hash-rate, coin-listing, DeFi-specific |
| **Other** | Any future event class Kalshi or other platforms list |

Three explicit per-event-type-awareness points exist in the framework:

1. **C11 generalization** (V1.0 update): "First trade on a new event type" — the C-trigger now fires across the full taxonomy, not just sports. Specialists: Thrawn + Robin + Scorpius + Armitage + Cassandra + Hari (unchanged).
2. **Data connector inventory expanded**: weather (NWS, Open-Meteo, ECMWF), politics (polling aggregators, gov data), econ (FRED, BLS), entertainment (Variety, IMDB), crypto (block explorers, on-chain data, exchange APIs).
3. **T43 Research framing parameterized**: "research markets for `<event_type>`" — Hari and Cassandra adapt to the event type without code changes. Per-event-type specialist variants (e.g., "weather modeling specialist") are added on demand when the first non-sport SDL fires; not pre-built.

---

## 5. Cross-References

### 5.1 Canonical trigger definitions (Pattern 73 SSOT)

All trigger details — fire conditions, specialists, artifacts, NOT-triggered-for clauses — live in `memory/roster_triggers.md`. The triggers introduced or modified by SDL Framework V1.0 are:

| Trigger | Type | Status in V1.0 | Roster section |
|---|---|---|---|
| T52 | Task type | NEW | Strategy & Model Lifecycle |
| T53 | Task type | NEW | Strategy & Model Lifecycle |
| T54 | Task type | NEW | Strategy & Model Lifecycle |
| S83 | Specialist | NEW | Validation & Challenge |
| S84 | Specialist | NEW | Operations & Monitoring |
| S85 | Specialist | NEW | Operations & Monitoring |
| S86 | Specialist | NEW (pre-positioned) | Operations & Monitoring |
| S87 | Specialist | NEW (dormant) | Operations & Monitoring |
| C40 | Council/cadence | NEW | Strategy & Model |
| C41 | Council/cadence | NEW | Strategy & Model |
| C11 | Council | MODIFIED (event-type generalization) | Strategy & Model |

### 5.2 Architecture decisions

- `docs/foundation/ARCHITECTURE_DECISIONS.md` — issued ADRs cited per-cycle in Stage 5 (T47) artifact.
- ADR-118 — Canonical Layer Foundation (Schema Hardening Arc Phase B.5) — relevant to cycles whose strategies depend on canonical_* tables.

### 5.3 Artifact directory

- `docs/sdl/_README.md` — directory structure + naming convention.
- `docs/sdl/SDL-INDEX.md` — master list of cycles with status.
- `docs/sdl/_CYCLE_TEMPLATE.md` — template metadata for new cycles.
- `docs/sdl/SDL-NNN/` — one directory per cycle (NNN zero-padded sequence).

### 5.4 Companion process documents

- `memory/protocols.md` — session-end protocol covers cross-trigger checks; Step 7 covers Pipeline Completeness Gate.
- `memory/roster_agents.md` — 48 agent definitions, all referenced in this framework.

---

## 6. Worked Examples

### 6.1 Autonomous SDL walkthrough — quarterly broad-scan

**Scenario:** End of Q2; the project has 1 live strategy (NFL spread-edge mean-reversion). C40 fires per the quarterly cadence. Goal: discover candidate strategies across the full event-type taxonomy.

1. **C40 fires** (Periodic SDL ideation kickoff). PM creates `docs/sdl/SDL-002/` (the next sequence number after the live SDL-001).
2. **Stage 1 — T43 Research.** `_CYCLE.md` records `SDL_MODE: autonomous`. Jorge audits docs for data gaps; Hari surveys data quality across all event types; Joe Chip flags assumption decay in the existing strategy roster. Artifact: `01_t43-research_2026-06-30.md`.
3. **Stage 2 — T44 Ideation.** Full Strategist Council. Thrawn lead generates 5 candidates across NFL spread-momentum, NBA total-overs-fade, weather hurricane-landfall, election generic, and crypto block-time variance. Pilot + Louise review for model feasibility. Artifact: `02_t44-ideation_2026-06-30.md`.
4. **Stage 3 — T45 Challenge.** Tagomi kills 2 (NBA total-overs-fade — overfit to last season; election generic — mode collapse risk). Slartibartfast questions metrics on hurricane-landfall. Survivors: NFL spread-momentum, hurricane-landfall, crypto block-time variance. Artifact: `03_t45-redteam_2026-06-30.md`.
5. **GATE 1 — C32.** Council: Deep Thought / Ghanima / Miles / Scorpius. Decision: Go on NFL spread-momentum (#1 by simplicity); Revise on hurricane-landfall (data-source gap); No-Go on crypto block-time variance (Scorpius: ruin-prob too high in current capital tier). Artifact: `04_c32-gate1_2026-06-30.md`.
6. **Stage 4 — T46 Co-Design** (only NFL spread-momentum proceeds). Thrawn + Robin define edge logic; Daneel + Louise define model interface. Vader reviews interface for extensibility. Artifact: `05_t46-codesign_2026-07-04.md`.
7. **Stage 5 — T47 Spec.** Scheherazade authors ADR-NNN. Artifact: `06_t47-spec_2026-07-08.md` (cross-references the ADR).
8. **Stage 6 — T18 + T22 Implementation.** Code shipped over the next 2 sessions.
9. **Stage 7 — T19 + T52.** Backtest passes. **S83 fires** (look-ahead check) — caught one feature using same-game in-progress data, fixed before T52. T52 walk-forward holds. Artifacts: `07_t19-backtest_*.md`, `08_t52-oos_*.md`.
10. **GATE 2 — C33.** Pass. Move to Stage 8 paper.
11. **Stage 8 — paper trading** for ~6 weeks. T49 weekly reviews; logs in `10_paper-trading-log/`.
12. **GATE 3 — C24.** Pass. Move to Stage 9 with **T53 staged ramp**.
13. **Stage 9a — T53 ramps**: 5% (4 weeks) → 25% (4 weeks) → 50% (8 weeks) → 100%. **S84 fires** at each ramp. Artifacts: `12_t53-capital-ramps/<tier>_*.md`.
14. **Stage 9b — recurring**. T48 + T49 + T50 + S86 (regime change) actively monitored.

### 6.2 Targeted SDL walkthrough — operator hypothesis

**Scenario:** Operator notices anomalous Kalshi pricing on a recurring news-driven category and asks for a news-arbitrage strategy specifically. **Mode: Targeted-by-strategy-type = news-arbitrage.**

1. PM creates `docs/sdl/SDL-003/`. `_CYCLE.md` records `SDL_MODE: targeted-by-strategy-type` and `framing_constraint: news-arbitrage`.
2. **Stage 1 — T43 Research** scoped to news-arbitrage prior art. Hari front-loads on news-data quality (latency, completeness, source reliability).
3. **Stage 2 — T44 Ideation** stays inside the genre. Council generates 3 news-arbitrage variants (election-news-arb, sports-injury-news-arb, econ-data-release-arb).
4. **Stage 3 — T45 Challenge.** Tagomi: "Latency advantage assumption is the whole edge — does it actually hold in our infrastructure?" Survivors after challenge: 1 (sports-injury-news-arb) — the latency-advantage assumption holds for in-game injury reporting where Kalshi prices update slower than ESPN reports.
5. **GATE 1 — C32**: Pass.
6. Stages 4-9 follow the standard path from Section 6.1.

The targeted mode primarily compresses Stages 1-3 by constraining the search space.

---

## 7. Out of Scope / Deferred

The following are intentionally NOT in V1.0 and will be addressed in follow-on issues:

- **Per-event-type specialist variants** (e.g., "weather modeling specialist", "polling-data analyst") — added on demand when the first non-sport SDL fires.
- **Pattern 88+ promotion of "SDL artifact directory pattern"** to `DEVELOPMENT_PATTERNS.md` — defer until pattern has been exercised across N≥2 cycles.
- **Implementation of S86 regime-change detection runtime logic** — needs the first live strategy to be running first.
- **Implementation of S87 cross-strategy correlation runtime logic** — needs a second live strategy first.
- **Capital-tier duration gate parameter** (how many trading days at each ramp tier before promotion) — V1.0 specifies the 5/25/50/100 fractions but leaves duration gates per-strategy. Potential future amendment to standardize.
- **Decision matrix for when targeted vs autonomous is appropriate** — V1.0 enumerates the modes; V1.1+ may add a richer guidance heuristic.

---

## 8. Version History

| Version | Date | Summary |
|---|---|---|
| 1.0 | 2026-05-02 (session 88) | Initial canonicalization. 9 stages + 3 gates + 3 framing modes + 7-event-type taxonomy. T52/T53/T54 + S83-S87 + C40/C41 added; C11 generalized; T48 wording confirmed already-correct in canonical roster. C40/C41 numbering — initial proposal in [#1126](https://github.com/mutantamoeba/precog/issues/1126) used C36/C37; renumbered at session-88 implementation due to existing C36 (Migration batch retrospective) / C37 (Pre-council Prior Art audit) / C38 (Post-council Generalization Check) / C39 (Schema Hardening Arc cohort completion) collisions in canonical `roster_triggers.md`. Origin: GitHub issue [#1126](https://github.com/mutantamoeba/precog/issues/1126). |
