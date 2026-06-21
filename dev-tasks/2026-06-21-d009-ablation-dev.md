# D-009 — Developer Handoff: Gate-Isolation Ablation

**Date:** 2026-06-21
**Raised by:** Architect (`dev-tasks/2026-06-21-d009-ablation-decision-arch.md`)
**Defect ID:** D-009 — OSD false-positive manufacture in noise
**Type:** Measurement (4-config factorial). Produces the data to either ship one
config or escalate to the Captain. **Do NOT pick the winner or merge** — the
architect applies the §3 pre-committed rule to your table.

---

## 1. Context

The K=10 confirmation gate failed (co_channel_sweep 86.67% < 89%). Investigation
showed the failure comparison was confounded: it changed both the pass-1 score floor
**and** the whole D-009 gating stack (corr 0.10 + nhard 60) at once. Two hypotheses
must be isolated:

1. **The pass-1 floor (`K_MIN_SCORE_PASS2`), not the corr/nhard gates, is what
   suppresses false positives** (sweep: FP stays 0.675/slot with gates ON at K=1;
   only collapses at K=10).
2. **The corr/nhard gates cost ~20 pp of genuine co-channel recovery** (co_channel
   P0–P2: 48.57% pre-gating → 28.6% with gating, both at K=1).

This ablation measures FP **and** co-channel recovery for 4 configurations that
cross the floor against the gates, so each lever's contribution is isolated.

---

## 2. Branch & builds

```
fix/d009-fp-callsign-filter
```

These are **diagnostic builds for measurement** — do **not** commit any of them and
do **not** bump the shim. The committed win-x64 DLL stays at shim 20260029.

Two `#define`s are in play:

- `native/ft8_lib_build/patched/ft8/decode.c` (~lines 55–56):
  ```c
  #define OSD_CORR_THRESHOLD 0.10f   // gates ON value
  #define OSD_NHARD_MAX      60      // gates ON value
  ```
  **Gates OFF** = set `OSD_CORR_THRESHOLD -1.1f` and `OSD_NHARD_MAX 174` (both become
  no-ops; corr/norm ∈ [−1,+1] so −1.1 never rejects; max nhard is 174). No logic
  change — only these two constants.

- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` (~line 385):
  ```c
  #define K_MIN_SCORE_PASS2  1       // the pass-1 floor
  ```

**Text Rules A/B/C (C# `IsPlausibleMessage`) stay ON in all configs** — they are
zero-FN structural rules, not part of this ablation. Do not touch them.

### The four builds

| Config | `K_MIN_SCORE_PASS2` | `OSD_CORR_THRESHOLD` | `OSD_NHARD_MAX` |
|---|---|---|---|
| 1 | 1 | −1.1f (off) | 174 (off) |
| 2 | 10 | −1.1f (off) | 174 (off) |
| 3 | 10 | 0.10f (on) | 60 (on) |
| 4 | 5 | −1.1f (off) | 174 (off) |

> Config 3 == current shim 20260029. If a clean `d009-k10-confirm` result already
> exists for it, you may reuse those numbers instead of rebuilding — but re-run if
> there is any doubt the corpora/seeds match the other three.

Rebuild **win-x64 Release** per config (production flags, **no `-DNHARD_DIAG`**).

---

## 3. Actions

### Action 1 — For each of the 4 configs, measure both axes

**S7 (co-channel benefit) — full 21 parts, K=5 trials:**
```
python harness/run_scenario.py scenarios/s7-compounding.json \
    --run-dir results/d009-ablation-2026-06-21/cfg<N>-s7
```
Record **both** overlap families: `co_channel` (P0–P2 equal-stack) **and**
`co_channel_sweep` (P15–P20 offset), plus the P15/P16 per-part rates.

**S5 (FP cost) — widened noise, ≥100 slots:**
```
python harness/run_scenario.py scenarios/s5-noise-wide.json \
    --run-dir results/d009-ablation-2026-06-21/cfg<N>-s5
```
Record FP/slot and FP count / slots.

Separate result subdir per config (MEMORY Lesson 14). Do not reuse a directory
across configs.

### Action 2 — Produce the ablation table, then STOP

Write `results/d009-ablation-2026-06-21/ablation.md`:

| Config | K | corr/nhard | co_channel % | co_channel_sweep % | P15 | P16 | S5 FP/slot |
|---|---|---|---|---|---|---|---|
| 1 | 1 | off | | | | | |
| 2 | 10 | off | | | | | |
| 3 | 10 | on | | | | | |
| 4 | 5 | off | | | | | |

Add 3–5 sentences: (a) does removing corr/nhard recover co_channel (compare cfg2 vs
cfg3)? (b) does the floor alone hold FP down without the gates (cfg2 FP)? (c) which
configs, if any, meet **all three** of: co_channel_sweep ≥ 89%, co_channel ≥ 45%,
S5 FP ≤ 0.10/slot.

**Then stop.** Hand `ablation.md` to the architect, who applies the pre-committed
decision rule. **Do not select a winner, edit production defaults, bump the shim, or
merge.**

---

## 4. Acceptance Criteria

| # | Criterion |
|---|---|
| AC1 | All 4 configs built exactly per §2 table; only the three named `#define`s vary; text rules untouched |
| AC2 | Each config: full 21-part S7 with **both** co_channel and co_channel_sweep reported, plus P15/P16 |
| AC3 | Each config: widened S5 (≥100 slots) FP/slot |
| AC4 | `ablation.md` table complete + the (a)/(b)/(c) reading |
| AC5 | No diagnostic build committed; committed DLL stays shim 20260029; no shim bump |
| AC6 | No winner selected, no production default changed — architect decides |
| AC7 | NFR-021: S5 ALL.TXT (AWGN CRC-coincidence callsigns) **not** committed; numeric metrics only |

---

## 5. References

- `dev-tasks/2026-06-21-d009-ablation-decision-arch.md` — why this ablation, the pre-committed §3 rule
- `dev-tasks/2026-06-21-d009-k10-gate-fail-arch.md` — the gate failure that triggered it
- `qa/rr-study/results/diag-pass1-sweep-2026-06-21/pass1_sweep.md` — K sweep (gating fixed)
- `qa/rr-study/results/d009-k10-confirm-s7-clean/` — Config 3 reference result
- `native/ft8_lib_build/patched/ft8/decode.c` — `OSD_CORR_THRESHOLD`/`OSD_NHARD_MAX` (~55–56)
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — `K_MIN_SCORE_PASS2` (~385)
- MEMORY Lesson 14 (separate result dirs); Lesson 1 (committed-binary staleness — N/A, nothing committed)
