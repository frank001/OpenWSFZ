# Architect → QA — HAND-OFF: three workstreams out of the three-decoder run
# Start with T1. It is cheap, and it decides how much the Captain's Angle 1 decision is worth.

**Author:** Architect, 2026-08-02 (18:13 UTC, `date -u`, per HK-017). Repo at `852b1e0`.
**For:** QA. **This is the single entry point** — the three companion notes below carry the detail.
**Status of the run:** analysis complete and corrected. What remains is one `src/` fix, three
record corrections, and one authorised measurement.

| companion note | what it is |
|---|---|
| `…-1813-architect-design-cycleframer-grid-realignment.md` | the drift fix + the corrected oracle |
| `…-1813-architect-corrections-to-record-drift-controls-and-my-own-errors.md` | six corrections, three of them project ground truth |
| `…-1813-architect-prereg-angle1-baseline-deficit-decomposition.md` | pre-registration, not authorised yet |

---

## Where the run ended up, in five lines

- 8080's capture **window** drifts at 48.0 ppm; PR #118 fixed only the **label**. Defect reopened.
- 8081 drifts too, at 4.7 ppm — **there is no zero-drift control** in this corpus.
- Drift cost ~9% of achievable decodes. **It does not explain D-001** (~48% gap vs WSJT-X).
- Both of QA's "void" tables were sound — mislabelled, not miscomputed. **No QA work was lost.**
- The +0s stratum is now a **drift-free, same-device OpenWSFZ-vs-WSJT-X population**. That is what
  Angle 1 has wanted since the beginning and never had.

---

## Tasks

### T1 — Check whether WSJT-X's own WAVs survive for this run  ⏱ minutes  ▸ do this first

The Angle 1 pre-registration's null **N3** calibrates jt9 against live WSJT-X by re-decoding
WSJT-X's *own* WAVs. If they exist, Angle 1 returns a **MEASURED** verdict. If not, it returns
**INDICATIVE** — still useful, materially weaker.

**The Captain is deciding whether to authorise Angle 1 and should know which one they are buying.**
Report presence/absence and cycle coverage against the +0s stratum. Nothing else in T1.

### T2 — Fold the design into the existing dev-task  ▸ not blocked

`dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-after-pr118.md` already exists
and is well-framed. It predates the design note and needs three things folded in:

1. **The fix** — per-cycle sample-level re-anchoring to the nearest grid line, `MaxCorrection`
   clamp for clock steps, correction absorbed in FT8's ~2.36 s guard interval. Design note §3.
2. **⚠️ The corrected oracle** — design note §4. `CycleFramerClockDriftOracleTests.cs:117-131`
   computes ground truth as the *drift-inclusive* open time, so it tests label honesty and passes
   green against this defect by construction. **Without this change the fix ships and the test
   stays green either way.** It must be RED against current `main` first (~4.1 s vs 0.2 s tolerance).
3. **The acceptance bar** — `|offset from grid| < 0.2 s`, set from measured loss (−3.8% at 1 s,
   −29.8% at 2 s), not from taste.

Per HK-011 this is `src/`: **a separate Developer session and Captain sign-off before push.**
The dev-task is yours to author; the design is mine. I have not edited it.

### T3 — Record corrections  ▸ not blocked; partly Captain's

Corrections note §1–3 are **project ground truth that is currently wrong**:

| # | record | who |
|---|---|---|
| 1 | "#118 fixed and merged" → partially addressed, reopened | **Captain** (memory) |
| 2 | "Voicemeeter ~0 ppm, cannot drift" → 4.7 ppm, crosses 1 s at 59.6 h | **Captain** (memory) |
| 3 | ~12 h cap lift → reinstate ~6 h on FT-991A until fixed | **Captain** |
| 4 | ratio-of-sums as the standing estimator | **QA** — note it in `anova_common.py` |

You reported having no memory-write tool; they are not mine to enact unilaterally either. **Both
of us surfacing them is what stops them lapsing (HK-012)** — please carry 1–3 forward in your next
handoff until the Captain closes them.

Item 3 is the live one: until the fix lands, uptime beyond ~6 h on the FT-991A chain is
quietly costing decodes on every future run.

### T4 — Angle 1  ▸ BLOCKED on Captain authorisation

Execute the pre-registration exactly as written. Do not begin before authorisation, and do not
compute the primary statistic `F_dec` in the course of any other work — including as a by-product
of T1.

Two things I want to flag rather than bury:

- **I reversed my own recommendation.** I advised against the jt9 leg in `…-1714-…` §8.4 and the
  Captain agreed. That was right for the whole corpus and wrong for the +0s stratum, where the
  WAVs are grid-aligned. jt9 goes from worthless to decisive. Pre-reg §2.
- **§6's AP confound is the one most likely to produce a wrong answer.** WSJT-X's a-priori
  decoding inflates leg C with decodes that are a *feature* difference, not a *sensitivity*
  difference. If that is folded into "decoder-attributable" the entire B.3 menu gets mis-costed.
  The sensitivity analysis in §6 is not optional.

### T5 — Density penalty  ▸ not now

Your 1702 §6.3 asked whether this run can finally answer *"does WSJT-X suffer the same density
penalty we do?"* — the brief's original purpose. It can, on the same drift-free stratum, but it
needs its own pre-registration and it should follow T4 rather than run beside it. I will write
that design when T4 reports.

---

## Ordering

```
T1 ─────────────────▶ (informs Captain's T4 decision)
T2 ─────────────────▶ Developer session ──▶ Captain sign-off ──▶ push
T3 ─────────────────▶ Captain (1-3) / QA (4)
                          │
T4 ── blocked on Captain authorisation ────▶ T5 design
```

T1, T2 and T3 are independent and can proceed in any order. **T4 blocks T5.**

## One standing note

Two of my four errors this session were caught by you reporting a discrepancy against my numbers
instead of smoothing it into agreement — the recall gap (raw message key vs
`normalize_hash_tokens`) and the +1 s sign flip (mean-of-ratios vs ratio-of-sums). The second one
changed the acceptance bar in T2 from 2 s to 0.2 s. **Keep doing exactly that.** Where my
predicted figures and your measured ones disagree, yours are the measurement and mine are the
hypothesis.

## Cross-references

- The three companion notes listed at the top.
- `2026-08-02-1741-qa-to-architect-grid-snapped-anova-rerun-result.md` — the work this follows.
- `src/OpenWSFZ.Ft8/CycleFramer.cs:118-149`, `tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs:117-131` — T2's two edit sites.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — reopened by you; T2 closes it.

---

*Per HK-015 Architect → QA: tasks scoped for QA, `dev-tasks/` yours to author, escalation reverses.
Per HK-014/HK-010 committed locally, no push, no merge, and I do not ask for one. Per HK-011 T2 is
`src/` and needs a separate Developer session plus Captain sign-off. Per HK-017 real `date -u` UTC.
Per HK-012 T3's items 1–3 are surfaced explicitly so they do not lapse for want of an owner. Per
HK-004 T1 exists because checking is cheaper than recommending that someone check.*
