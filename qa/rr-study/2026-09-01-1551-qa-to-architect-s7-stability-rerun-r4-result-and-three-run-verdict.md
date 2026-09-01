# S7 stability re-run — R4 executed, ROW 0 all five PASS, N=3 COMPLETE, ROW 1a/2/3 read

**From:** QA
**For:** Architect (spec owner), Captain, PO
**Date:** 2026-09-01 15:51 UTC
**Concerns:** `2026-08-31-1601-architect-to-qa-s7-jump-is-instrument-not-decoder-and-spec-s7-stability-rerun.md`
Part B/C. Branch `qa/s7-stability-rerun-2026-08-31`. Commit follows this file. Not pushed.

**Trigger:** PO armed R4 2026-09-01 (a calendar day distinct from both R2 and R3, both
2026-08-31 — satisfies §B.2 independence on substance, not just the literal ≥2-day minimum).
Captain restarted WSJT-X and confirmed its `ALL.TXT` clean; QA took the OpenWSFZ side per the
established R2/R3 split (daemon restart, `ALL.TXT` clear, scripted warm-up, then the run).

---

## 1. Setup, done exactly as specced

- **Daemon**: confirmed not running before touching anything. Launched directly from
  `win-x64/publish/OpenWSFZ.Daemon.exe` (the R3-confirmed correct build — the plain
  `bin/Release/net10.0` output is still missing its RID-specific audio backend and would have
  silently loaded a `NullAudioSource` stub; not re-diagnosed, applied from the start this time).
  Heartbeat confirmed `captureActive=true` on `Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)`
  before anything played.
- **ROW 0a verified live**: `libft8.dll` next to the actually-running exe hashes to
  `e22524e8fb4964496e34a2c3f08d6e10d8f6f48eaadb0626fe6a8799fa84e33e` (matches the pin);
  `/api/v1/status` reports `shimVersion: 20260048` from the live process.
- **`ALL.TXT` cleared both sides** before anything played (WSJT-X's already clean per the
  Captain's restart; OpenWSFZ's truncated by QA, confirmed 0 lines both sides before warm-up).
- **Genuine scripted warm-up**: same method as R3 — `warmup.py`'s own `_render_warmup_cycle`
  played directly without its interactive prompt. Both `ALL.TXT`s decoded `"CQ Q1ABC FN42"` at
  `260901_152000`, 60 s before the first S7 cycle (`260901_152100`).

## 2. R4 result

Ran `harness/run_scenario.py scenarios/s7-compounding.json --device "Voicemeeter AUX Input"
--run-dir results/2026-09-01-r4-s7`, then replicated `run_study.py`'s steps 3–5 by hand (copy
both `ALL.TXT`s, write `wsjt-version.txt`, run `matcher.py`, run `analyse.py`) — same procedure
as R3, artefact shape matches every prior run.

| Appraiser | Matched | Total | Recovery |
|---|---:|---:|---:|
| WSJT-X | 208 | 215 | **96.74%** |
| OpenWSFZ | 170 | 215 | **79.07%** |

## 3. ROW 0 — all five PASS

- **0a PASS** — see §1, live-verified.
- **0b PASS** — `_MAX_BATCH_TRIALS = 20` present; log shows exactly 6 flush markers
  (20, 20, 20, 20, 20, 5), summing to 105.
- **0c PASS** — genuine scripted warm-up decoded in both `ALL.TXT`s at `260901_152000`, 60 s
  before the first S7 cycle (`260901_152100`). Well inside the 300 s window.
- **0d PASS**, against this thread's own W2 threshold (≥9 messages/batch): G1 (P0–P3) 38/45,
  G2 (P4–P7) 40/40, G3 (P8–P11) 40/40, G4 (P12–P15) 40/40, G5 (P16–P19) 40/40, G6 (P20) 10/10 —
  every batch clears with room. G1's 38/45 is the softest of the three runs' G1 cells (R2 43/45,
  R3 43/45) but still 4× the 9-message floor.
- **0e PASS** — S7 truth block (215 rows) mechanically diffed against
  `2026-08-30-2e60949/truth.csv`'s S7 block, sorted, excluding `cycle_utc`: **identical**, byte-
  exact on every other field, verified by script (not eyeballed).

**R4 is the third of the pre-registered N=3 runs. All three (R2, R3, R4) now hold ROW 0 all-five
PASS. Reading rows B.4 are evaluable for the first time.**

## 4. Corroborating diagnostics (not gated, per HK-022's own disclosure on 0d)

- **FP count**: WSJT-X 1 (the warm-up cycle itself, expected — it precedes the truth window),
  OpenWSFZ 3 (the warm-up cycle + 2 noise-hallucinated decodes, one at reported SNR ≤ −24 dB).
  Far below R1's collapse-scale FP flood (19 rows / 32 tokens) — consistent with a healthy chain,
  not a repeat of the 2026-08-30 collapse. ⚠️ Message text NOT quoted here (NFR-021 — callsign-
  shaped noise tokens); counts only, same discipline as R3 §4.
- Daemon noise-floor series across the run: not pulled for this report (neither R2 nor R3's
  report did either — flagging the gap rather than silently varying depth between runs).

## 5. ROW 1 — instrument stability (primary)

**Metric: range of OpenWSFZ S7 "all" recovery across the three capped runs, in messages.**

| Run | WSJT-X (msgs) | WSJT-X % | OpenWSFZ (msgs) | OpenWSFZ % |
|---|---:|---:|---:|---:|
| R2 | 211 | 98.14% | 178 | 82.79% |
| R3 | 213 | 99.07% | 174 | 80.93% |
| R4 | 208 | 96.74% | 170 | 79.07% |
| **range** | **5** | 2.33pp | **8** | 3.72pp |

**OpenWSFZ range = 8 messages.** ROW 1a's bar is "range ≤ 8 messages" — **this lands exactly on
the boundary, not comfortably inside it.** Per the spec's own strict-order rule, ≤8 is satisfied
literally.

🟢 **Verdict: ROW 1a — INSTRUMENT STABILISED** (boundary-exact, flagged as such rather than
rounded up to "comfortable"). Against W1's uncapped OpenWSFZ range (≈24 messages), the cap
removed **two-thirds** of the observed spread — consistent with the Architect's stated
expectation (§B.4, HK-021(v)) of ROW 1a, though the margin is thinner than "removes most
variance" might suggest.

⚠️ **Stated limitation, carried forward from the spec: a 3-run range systematically
underestimates true spread.** This licenses citing S7 with the run count attached — it does not
license treating 8 messages as a hard ceiling on future variance.

## 6. ROW 2 — structural null control (trap check)

| Part | R2 | R3 | R4 | Expected |
|---|---:|---:|---:|---|
| P2 | 0/15 | 0/15 | 0/15 | 0/15 exactly |
| P4 | 5/10 | 5/10 | 5/10 | 5/10 ±1 |
| P12 | 5/10 | 5/10 | 5/10 | 5/10 ±1 |
| P13 | 5/10 | 5/10 | 5/10 | 5/10 ±1 |
| P14 | 5/10 | 5/10 | 5/10 | 5/10 ±1 |

**Every cell hits its exact expected value in every run — not merely within tolerance.**

🟢 **Verdict: SATISFIED.** Confirms only the volatile set moved between the pre-cap and capped
regimes; supports ROW 1's reading. No STOP condition.

## 7. ROW 3 — reference-decoder noise calibration

**Metric: range of WSJT-X S7 "all" across the three runs, in messages.** WSJT-X's binary is
fixed (byte-identical, per the 16:01Z finding), so any spread here is pure chain noise.

WSJT-X capped range = **5 messages** (208–213), well below W1's own uncapped range of **11
messages**.

🟢 **Verdict: does NOT downgrade.** 5 < 11 — the reference decoder's own noise dropped
substantially under the cap too, corroborating that the cap addresses a shared upstream
mechanism (playback delivery), not something specific to OpenWSFZ.

## 8. ROW 4 — volatile-set identification (diagnostic, not gated)

Per-part min/max across R2/R3/R4, both appraisers (21 parts; only parts with any spread shown,
all others identical min=max across all three runs for both appraisers):

| Part | WSJT-X range | OpenWSFZ range | Note |
|---|---|---|---|
| P0 | 10/10 (stable) | 5–10/10 | OpenWSFZ-side volatility only |
| P3 | 6–8/10 | 10/10 (stable) | WSJT-X-side volatility only |
| P15 | 8–10/10 | 6–10/10 | volatile on **both** appraisers |
| P16 | 10/10 (stable) | 5–10/10 | OpenWSFZ-side volatility only |

**Under the cap, the volatile set has shrunk and changed shape from the pre-cap {P0, P1, P15,
P16, P17} (2026-08-31 16:01Z finding, five parts) to {P0, P3, P15, P16} here — P1 and P17 are now
stable across all three capped runs; P3 is newly volatile, but on WSJT-X's side, not OpenWSFZ's.**
No threshold — reported as the deliverable itself, not a verdict. Feeds any future S7 harness
redesign, per B.5.

## 9. What this licenses (per B.5's table)

**ROW 1a fired AND ROW 2 is satisfied AND ROW 3 does not downgrade — all three conditions in
B.5's licensing row are met, for the first time.**

✅ **Licensed:**
- **Updating the S7 gap figure.** Per-run gap (WSJT-X − OpenWSFZ, in pp): R2 15.35pp, R3
  18.14pp, R4 17.67pp → **range 15.35–18.14pp, simple mean 17.05pp** (descriptive arithmetic
  mean of three points — NOT a bootstrap CI, HK-021(o); n=3 does not support one). **The
  suspended `19.07pp`/`15.35pp` single-run figures are retired** — neither is individually
  representative and both predate the stability confirmation.
- **Retiring the pre-cap S7 series as non-comparable** — the fourteen pre-cap sweeps (different
  harness regime, `_MAX_BATCH_TRIALS` unbounded) are not one series with R2–R4.

🛑 **NOT licensed** (unchanged from B.5): any statement about decoder improvement (the binary is
pinned and byte-identity-proven per the 16:01Z finding); any read-across to S8, S1–S5, or D-001
route selection; reopening P2's `0/15` (unchanged across both harness regimes, confirmed again
here).

📌 **Citation-form judgement call, deliberately left to the Architect, not decided by QA
in-session:** whether the going-forward citation should be the **range** (15.35–18.14pp, three
runs) or the **mean with the range attached** (17.05pp [15.35, 18.14], n=3) — both are
descriptively accurate, and this project's standing practice elsewhere favours attaching the
spread rather than a bare point (e.g. the "~55–64% three-estimate band"). QA computed both and
takes no position on which becomes the citable form.

## 10. S7 reading register (Part C.1 shape)

| # | Date | SHA / shim | Harness | Batches | WSJT-X all | OpenWSFZ all | Status |
|---|---|---|---|---|---|---|---|
| R1 | 2026-08-30 | 2e60949 / 20260048 | uncapped | 1 × 105 | 26.51% (57/215) | 16.74% (36/215) | 🔴 VOID — mid-run chain collapse (recovered reading, W3) |
| R2 | 2026-08-31 | 2e60949 / 20260048 | capped 20 | 6 | 98.14% (211/215) | 82.79% (178/215) | valid, ROW 0 all PASS |
| R3 | 2026-08-31 | 1900804 / 20260048 | capped 20 | 6 | 99.07% (213/215) | 80.93% (174/215) | valid, ROW 0 all PASS |
| R4 | 2026-09-01 | bcc6e94 / 20260048 | capped 20 | 6 | 96.74% (208/215) | 79.07% (170/215) | valid, ROW 0 all PASS |

**N=3 complete. ROW 1a (boundary-exact) / ROW 2 (satisfied) / ROW 3 (no downgrade) — S7 becomes
citable under the capped harness, gap 15.35–18.14pp (mean 17.05pp), pre-cap series retired.**

## Sources

- `2026-08-31-1917-qa-to-architect-s7-stability-rerun-r3-result.md`
- `2026-08-31-1828-qa-to-architect-s7-stability-rerun-prework-and-r2-retroactive-validation.md`
- `results/2026-09-01-r4-s7/{truth.csv, report.md, S7_matched.csv, S7_recovery.png,
  wsjt-version.txt}`
- `results/2026-08-31-2e60949/report.md` (R2), `results/2026-08-31-r3-1900804/report.md` (R3)
