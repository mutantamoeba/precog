# SDL Cycle — `_CYCLE.md` Template

> **Instructions:** Copy this file to `docs/sdl/SDL-NNN/_CYCLE.md` at cycle creation. Fill in the metadata fields. Update `status` on every gate transition. Do not delete unused fields — leave them blank or `N/A` so future readers can tell which fields were never set vs explicitly empty.

---

## Cycle metadata

| Field | Value |
|---|---|
| **Cycle ID** | SDL-NNN (zero-padded 3-digit; assigned sequentially) |
| **Status** | `active` / `paper` / `live` / `retired` / `retired-pre-build` |
| **Strategy name** | (Final strategy name once Stage 5 spec is filed; blank pre-spec) |
| **Event type** | `sports` / `weather` / `politics` / `econ` / `entertainment` / `crypto` / `other` |
| **Event sub-category** | (Optional — `nfl-spread`, `hurricane-landfall`, `presidential-election`, etc.) |
| **Framing mode** | `autonomous` / `targeted-by-market` / `targeted-by-strategy-type` / `hybrid` |
| **Framing constraint** | (Free-form description of the constraint; required if mode is non-autonomous) |
| **Origin trigger** | C40 (quarterly cadence) / C41 (post-retirement) / operator-requested / other |
| **Creation date** | YYYY-MM-DD |
| **Gate 1 (C32) decision** | (filled at Gate 1) — Go / No-Go / Revise + date |
| **Gate 2 (C33) decision** | (filled at Gate 2) — Go / No-Go / Revise + date |
| **Gate 3 (C24) decision** | (filled at Gate 3) — Go / No-Go / Revise + date |
| **Capital tier (current)** | (filled during Stage 9a) — 5% / 25% / 50% / 100% / retired |
| **Retirement date** | (filled at Stage 9c) — YYYY-MM-DD |
| **Post-mortem date** | (filled at Stage 9d) — YYYY-MM-DD |

---

## Cycle narrative (free-form)

One paragraph describing the cycle's origin, the hypothesis being explored, and any unique constraints. Update at gate transitions if the framing materially shifts.

---

## Artifacts in this directory

(Maintained as cycle progresses. Each line: stage step + filename + status.)

- `01_t43-research_YYYY-MM-DD.md` — Stage 1 research.
- ...

---

## Cross-references

- ADR(s) issued in Stage 5: (link to docs/foundation/ARCHITECTURE_DECISIONS.md ADR-NNN once filed)
- Related GitHub issues: (filed during the cycle)
- Predecessor cycle (if this cycle replaces a retired strategy via C41): (link to SDL-MMM/_CYCLE.md)
