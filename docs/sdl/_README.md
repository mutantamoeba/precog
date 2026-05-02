# SDL Cycles — Directory Structure & Naming Convention

**Companion to:** `docs/foundation/SDL_FRAMEWORK_V1.0.md` (canonical SDL spec).
**Purpose:** This directory holds the artifact trail for every SDL cycle the project runs.

---

## Directory shape

```
docs/sdl/
├── _README.md          (this file)
├── SDL-INDEX.md        (master list of cycles + status)
├── _CYCLE_TEMPLATE.md  (template for new cycle metadata)
└── SDL-NNN/            (one directory per cycle; NNN is zero-padded sequence)
    ├── _CYCLE.md
    ├── 01_t43-research_YYYY-MM-DD.md
    ├── 02_t44-ideation_YYYY-MM-DD.md
    ├── 03_t45-redteam_YYYY-MM-DD.md
    ├── 04_c32-gate1_YYYY-MM-DD.md
    ├── 05_t46-codesign_YYYY-MM-DD.md
    ├── 06_t47-spec_YYYY-MM-DD.md  (cross-references docs/foundation/ARCHITECTURE_DECISIONS.md ADR-NNN)
    ├── 07_t19-backtest_YYYY-MM-DD.md
    ├── 08_t52-oos_YYYY-MM-DD.md
    ├── 09_c33-gate2_YYYY-MM-DD.md
    ├── 10_paper-trading-log/
    ├── 11_c24-gate3_YYYY-MM-DD.md
    ├── 12_t53-capital-ramps/
    ├── 13_t49-weekly-perf/
    ├── 14_t51-retirement_YYYY-MM-DD.md
    └── 15_t54-postmortem_YYYY-MM-DD.md
```

## Naming rules

| Rule | Detail |
|---|---|
| Sequence prefix | `NN_` two-digit, sortable (the visible "stage step" within the cycle). |
| Trigger ID | `tNN-` or `cNN-` lowercase, identifies which trigger produced the artifact. |
| Artifact slug | Free-form short name (`research`, `ideation`, `redteam`, `gate1`, `codesign`, `spec`, `backtest`, `oos`, `gate2`, `gate3`, `retirement`, `postmortem`). |
| Date | `YYYY-MM-DD` time of authoring (single-day artifacts) at the end of the filename. |
| Subdirectories | `10_paper-trading-log/`, `12_t53-capital-ramps/`, `13_t49-weekly-perf/` for ongoing logs that span weeks/months — kept as subdirs so weekly entries don't pollute the cycle-level listing. |

## Cycle ID

The `SDL-NNN` cycle ID is zero-padded 3-digit and assigned sequentially at cycle creation. The first SDL cycle is `SDL-001`. The cycle ID does NOT encode the event type or framing mode — those live in `_CYCLE.md` (Pattern 73 SSOT — one source of truth per cycle, in the metadata file).

## Status lifecycle

A cycle has one of these statuses, recorded in both `_CYCLE.md` and `SDL-INDEX.md`:

| Status | Meaning |
|---|---|
| `active` | In Stages 1-7 (pre-paper). |
| `paper` | Through Gate 2; in Stage 8 paper trading. |
| `live` | Through Gate 3; in Stage 9 (live capital, any tier). |
| `retired` | Stage 9c complete (T51 retirement done; T54 post-mortem may or may not be filed yet). |
| `retired-pre-build` | Cycle killed at Gate 1 (C32 No-Go) — no implementation work was started. |

## When to create a new cycle directory

A new `SDL-NNN/` is created when:

- C40 fires (periodic SDL ideation kickoff — quarterly or when fewer than N live strategies).
- C41 fires (post-retirement SDL trigger — a strategy retired and no replacement is in pipeline).
- Operator requests a targeted SDL with a specific framing constraint.

Update `SDL-INDEX.md` at cycle creation AND at every status transition.
