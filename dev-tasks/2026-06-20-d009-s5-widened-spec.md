# D-009 — Widened S5 Scenario Spec (statistically-powered FP-rate gate)

**Date:** 2026-06-20
**Author:** Architect
**For:** R5 handoff AC5 (`dev-tasks/2026-06-20-d009-fp-filter-r5.md`)
**Artefact:** `qa/rr-study/scenarios/s5-noise-wide.json` (created)
**Status:** Proposed; QA to fold into STUDY-SPEC §6 and NFR-023 §1/§2 framing.

---

## 1. Why the current S5 cannot support the "0 FP" claim

The R4/R5 target is "0 FP on S5, matching WSJT-X." The existing `s5-noise.json` is
**4 parts × 3 trials = 12 slots**. Observing 0 FPs on 12 slots is statistically weak: by the
**rule of three**, the 95 % one-sided upper bound on the true per-slot FP probability is
≈ 3 / 12 = **25 %**. In other words, "0 / 12" is consistent with a real FP rate as high as one
in four. It does not bound the FP rate to anything near WSJT-X parity.

To make "0 FP" meaningful we need enough **independent** signal-free slots that the rule-of-three
bound is small (≤ ~3 %). That requires ≥ 100 independent slots.

---

## 2. Two harness facts that constrain the design

Both discovered by reading `run_scenario.py::_render_noise` and `common.py::compute_seed`.

### Fact A — only AWGN slots are independent; carrier slots are deterministic

`_render_noise` uses the seeded RNG **only** in the `awgn` branch. `steady_carrier` and
`multi_carrier` are pure `sin()` sums with **no RNG** — every trial of a carrier part renders a
**bit-identical** buffer. Repeating carrier trials therefore adds **zero** independent samples.
Only AWGN parts produce a fresh realisation per trial (distinct seed →
`np.random.default_rng(seed)` → independent noise).

**Consequence:** the rate-estimation slots must be **AWGN**. Carrier/birdie parts are a
*coverage* check (does structured non-FT8 energy fool OSD?), not rate samples, and need only
**one** trial each.

### Fact B — `level_dbfs` is statistically inert for signal-free AWGN

Before playback, `_run` peak-normalises every buffer: `samples *= 0.9 / peak`. For pure AWGN,
`samples = randn · amplitude` and `peak = amplitude · max|randn|`, so the normalised buffer is
`randn · 0.9 / max|randn|` — **the amplitude (hence `level_dbfs`) cancels exactly.** Different
AWGN "levels" in S5 produce statistically identical normalised inputs; only the **seed** varies
the realisation.

**Consequence:** do **not** add multiple AWGN levels expecting more statistical power. Add
**trials**. (Capture this in MEMORY lessons — it is a non-obvious property of the post-2026-06-08
normalised playback path.)

> These two facts are *why* the widened scenario is "1 AWGN part × 120 trials" rather than the
> intuitive "more parts at more levels."

---

## 3. The widened scenario

**File:** `qa/rr-study/scenarios/s5-noise-wide.json` (id stays `"S5"` so `run_scenario.py` takes
the `is_s5` render path and `analyse.py` applies the S5 attribute logic).

- **1 AWGN part × `trials: 120` = 120 independent signal-free slots.**
- Rule-of-three 95 % upper bound at 0 observed FPs: ≈ 3 / 120 = **2.5 %**.
- Raise `trials` to tighten: 300 → ~1.0 %. Cost is linear real-time playback (~15 s/slot):
  120 slots ≈ **30–45 min** wall clock; 300 ≈ ~75 min.
- Carrier/birdie **coverage** stays in `s5-noise.json` (deterministic; one trial per part is
  sufficient — see Fact A).

Run command:

```
python harness/run_scenario.py scenarios/s5-noise-wide.json --run-dir results/<sha>-s5-wide
python harness/analyse.py     --run-dir results/<sha>-s5-wide --scenario s5
```

---

## 4. Metric definitions (NFR-023 §1 hypothesis / §2 thresholds)

Report **both** rates; the gate is on the event rate.

- **FP event rate** = (# slots with ≥ 1 OpenWSFZ decode) / N_slots. **Primary gate metric.**
- **FP decode rate** = (total OpenWSFZ decodes) / N_slots. Severity indicator (a slot can carry
  more than one false decode).
- **95 % upper confidence bound** (rule of three, valid when 0 events observed):
  `p_UB ≈ 3 / N_slots`. Report this number, not just "0".
- **WSJT-X cross-check:** both appraisers are fed the identical audio; WSJT-X FP event rate on
  the same slots is the parity reference (expected 0).

### Acceptance (replaces AC5 wording in R5)

| Gate | Requirement |
|---|---|
| AC5a | FP **event** rate = 0 over **N ≥ 120** independent AWGN slots |
| AC5b | Reported with the rule-of-three 95 % upper bound (≤ ~2.5 % at N = 120) |
| AC5c | WSJT-X FP event rate on the identical slots is also 0 (parity) |
| AC5d | Carrier/birdie coverage (`s5-noise.json`, 1 trial/part) shows 0 FP |

---

## 5. Required `analyse.py` adjustment (small)

`analyse.py` currently computes a *decode-style* FP rate with `THRESH_FP_PASS = 6.0` (PASS if
≤ 6 %). For this gate:

1. Also compute and print the **FP event rate** (slots-with-any-FP / slots), not only the
   decode-count rate.
2. Emit the **rule-of-three upper bound** (`3 / N`) alongside the point estimate.
3. For the D-009 gate the pass threshold is **0 events**, not 6 % — either parameterise the
   threshold or report the raw event count so QA applies the 0-event gate in §1/§5 of the report.

If the analyse change is out of scope for the dev pass, the matched CSV in the run directory
already contains per-slot decodes, so QA can compute event rate + bound by hand for the report.
This should be flagged in the result `report.md` §2.

---

## 6. Scope / non-goals

- **No `channel.py` change.** Pink/swept noise remain deferred (existing `channel_note`).
  Wideband AWGN is the correct and sufficient driver for the OSD-from-noise FP mechanism.
- Making carrier parts stochastic (adding a seeded AWGN floor under the tones) is a *possible*
  future refinement that would let a single file carry both rate and coverage, but it is a
  `_render_noise` change and is **not** required for this gate. Deferred.
- `s5-noise.json` is unchanged by this spec (optionally drop its AWGN parts later, since the
  wide file supersedes them, and reduce its `trials` to 1 for the deterministic carrier parts).

---

## 7. References

- `qa/rr-study/scenarios/s5-noise.json` (original 12-slot coverage scenario)
- `qa/rr-study/scenarios/s5-noise-wide.json` (this spec's artefact)
- `qa/rr-study/harness/run_scenario.py` — `_render_noise` (~363), peak-normalisation (~568)
- `qa/rr-study/harness/common.py` — `compute_seed` (~33)
- `qa/rr-study/harness/analyse.py` — `_fp_rate` (~553), `THRESH_FP_PASS` (~106)
- `dev-tasks/2026-06-20-d009-fp-filter-r5.md` — AC5 (widened S5)
- `dev-tasks/2026-06-20-d009-fp-filter-arch-design.md` — §6 statistical note
- STUDY-SPEC §6 (S5 definition); NFR-023 (report structure); NFR-024 (rule-of-three power)
