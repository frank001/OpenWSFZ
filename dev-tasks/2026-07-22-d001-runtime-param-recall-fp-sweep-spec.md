# D-001 — Runtime-Parameter Recall/False-Positive Pareto Sweep: Analysis Spec

**Date:** 2026-07-22
**Author:** QA (self-directed)
**Audience:** Architect, Captain
**Decision context:** `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` (Option B) — F=29.6% (mixed), ≤18.4 pp recoverable-recall ceiling, and the open H7 (MMSE joint demodulation) go/no-go at 3–6 months' cost. This pass asks whether a **zero-rebuild, runtime-only** decoder reconfiguration recovers meaningful D-001 recall *before* that expensive decision is made.
**Defect ID:** D-001 — weak-signal / co-channel decode recall gap vs WSJT-X (open, issue #3). Directly touches the D-009 false-positive boundary (the two defects are in tension on the same knobs).
**Status:** Proposed. Third of three bounded groundwork passes offered ahead of the Captain's H7 decision — the Captain has stated the H7 call will be made once these three are done. This is the only one of the three that can *directly* close some of the gap rather than only describing it.

---

## 0. Executive summary

The other two passes describe the gap (Δf shape) and try to locate it (isolated-miss pipeline
stage). This one **tests a fix that costs nothing to try**: OpenWSFZ already exposes three
decode parameters at runtime via `ft8_set_decode_params(k, corr, nhard)` (shim 20260030+, wired
through `IFt8NativeInterop.SetDecodeParams` and already covered by `SetDecodeParamsTests`). No
native rebuild, no code change to the product — set a value, re-decode, measure.

But two of those three knobs are the **exact false-positive gates D-009 was calibrated on**
(`osd_corr_threshold`, `osd_nhard_max`), and the third (`k_min_score_pass2`) is the pass-1
candidate-admission floor that D-009 raised 1 → 10 specifically to cut a 94% FP rate. So loosening
any of them to chase D-001 recall directly re-opens D-009. This is therefore not a one-way
sensitivity dial but a **recall-vs-false-positive Pareto sweep**: does any runtime operating point
recover D-001 recall *without* regressing the S5/S7 false-positive rate past the current
D-009-calibrated baseline of `(k=10, corr=0.10, nhard=60)`?

**Two possible outcomes, both decision-grade for the H7 call:**
- **A Pareto-dominating point exists** → a fraction of the D-001 gap closes for the price of a
  settings change. That materially shrinks what H7 would have to justify, and may reset the whole
  cost/benefit.
- **No point dominates the baseline** → the runtime knobs are provably tapped out. That is the
  strongest possible evidence that closing the residual gap needs *either* the compile-time levers
  (LDPC depth, OSD `ndeep`, pass-0 candidate limits — a rebuild, Phase 2) *or* H7 — and the Captain
  can weigh H7 knowing the cheap options are genuinely exhausted, not merely untried.

**Effort:** a few days — most of it the one-time offline decode harness (small C# console project,
the `diag-fp-engagement-survival` pattern) plus grid runtime. **Not** a live capture. **No** product
or native code change — this drives *existing* runtime setters against *already-retained* audio.

---

## 1. The precise question this answers

> Across the three runtime-configurable decode parameters, does any operating point recover a
> meaningful fraction of the D-001 low-SNR recall gap (measured as agreement with WSJT-X on the
> 07-07 off-air corpus) **without** regressing the D-009 false-positive rate (measured on the
> synthetic S5 noise-only and S7 co-channel scenarios) beyond the current calibrated baseline?

This is the same two-sided calibration D-009 itself used — S5 FP + S7 recovery (see shim 20260029:
"K=10 cuts S5 FP by 94% while improving S7 co-channel recovery +8.5 pp"). The novelty here is
sweeping all three knobs jointly against the *D-001* recall population rather than re-confirming a
single production point, and breaking recovery down **by Option B miss class** (Tight / Partial /
Isolated) so we see *which* knob moves *which* class:

- Lowering `k_min_score_pass2` (5…10) admits more pass-1 candidates — a **candidate-generation**
  lever. The 06-17 probe found candidate generation is *not* the Tight-class bottleneck, so this is
  predicted **not** to help Tight — but it is exactly the lever that would recover **Isolated**
  misses *if* their failure is candidate-generation (the open question the isolated-miss pipeline
  spec asks). This sweep therefore also **empirically probes that spec's question** as a side
  effect: if low-`k` recovers Isolated misses, candidate admission was a bottleneck for them.
- Loosening the two OSD gates (`corr`, `nhard`) lets more marginal LDPC/OSD candidates through — a
  **convergence-acceptance** lever, the one 06-17 diagnosed as the Tight-class bottleneck. If a
  *tighter* pairing of the gates lets a *lower* `k` through without FP cost, that is the
  non-obvious Pareto win worth finding.

---

## 2. Inputs (data-availability check already performed)

| Input | Status | Detail |
|---|---|---|
| Runtime parameter setter | **Confirmed wired and tested** | `ft8_set_decode_params(k_min_score_pass2, osd_corr_threshold, osd_nhard_max)` — shim 20260030, exposed via `IFt8NativeInterop.SetDecodeParams` / `Ft8NativeInteropAdapter`, covered by `tests/OpenWSFZ.Ft8.Tests/SetDecodeParamsTests.cs`. Documented valid ranges: `k ∈ [5,30]` (default 10), `corr ∈ [0.05,0.40]` (default 0.10), `nhard ∈ [30,100]` (default 60). Baseline `(10, 0.10, 60)` reproduces shim-20260029 behaviour exactly. |
| Recall-arm corpus (off-air, real signals) | **Confirmed present** | `artefacts/20260706_live_run_2308/save/*.wav` — 4,075 per-slot 12 kHz mono WAVs, plus `OpenWSFZ ALL.TXT` / `WSJT-X ALL.TXT` for the same session. WSJT-X's low-SNR decodes are the recall reference. (07-06 / 06-22 have ALL.TXT but **no WAVs** — they cannot feed the offline decoder; see §4.4 held-out caveat.) |
| FP-arm scenarios (synthetic, injected truth) | **Confirmed present** | The R&R study's **S5** (signal-free / noise-only) and **S7** (co-channel) scenarios (`qa/rr-study/`, `STUDY-SPEC.md`) — the exact scenarios D-009 was calibrated against. `truth.csv` + `matcher.py` give a definitive FP count (any uncorroborated decode against injected truth is a real FP, which the off-air corpus can never establish). |
| Offline in-process decode harness | **Pattern exists; must be written for this pass** | `qa/rr-study/diag-fp-engagement-survival-2026-07-18/Program.cs` establishes the model: a small C# console project that `ProjectReference`s the real OpenWSFZ assemblies and drives them in-process. The sweep harness is the analogue: `ProjectReference` `OpenWSFZ.Ft8`, call `SetDecodeParams(...)` then `DecodeAll(pcm)` on each WAV's raw 12 kHz float32 (180 000 samples — no VB-CABLE, no resampling, no live app). |
| Scoring | **Confirmed present** | Recall arm reuses `classify_cochannel.py`'s WSJT-X-agreement logic (per-class Tight/Partial/Isolated). FP arm reuses `matcher.py` (truth-vs-decode, `false_positive` column). |

**Gate 0 verdict: PASS.** Everything needed is on disk or already wired. The one thing to build is
an offline decode harness, and its pattern already exists.

**Why offline, not `corpus_replay.py`.** The existing corpus harness plays through VB-CABLE into
the *live* apps at ~30 s wall-clock per WAV — fine for a single baseline, prohibitive for a grid
(a 3-knob grid × thousands of slots would run for weeks and couldn't reconfigure params
per-slot cleanly). Calling `DecodeAll` in-process is deterministic, reconfigurable per-decode, and
runs the whole corpus per parameter point in minutes.

---

## 3. Method

### 3.1 Parameter grid (start coarse, refine only if a ridge appears)

Baseline (locked reference, never removed from the grid): **`(k=10, corr=0.10, nhard=60)`**.

Coarse grid, all within the documented valid ranges:

| Knob | Swept values | Direction of interest |
|---|---|---|
| `k_min_score_pass2` | {5, 7, 10, 15, 20} | ↓ = more candidates (sensitivity ↑, FP ↑) |
| `osd_corr_threshold` | {0.10, 0.15, 0.25} | ↑ = stricter OSD accept (FP ↓, recall ↓) |
| `osd_nhard_max` | {40, 60, 80} | ↑ = looser Hamming accept (recall ↑, FP ↑) |

That is 5 × 3 × 3 = **45 points** (one is the baseline). Deliberately coarse: the goal is to find
whether a *region* Pareto-dominates the baseline, not to over-resolve a surface from one session's
data (§4.3). Refine to a finer local grid **only** around a point that already beats the baseline on
both arms.

### 3.2 Offline decode harness (write once, reuse)

A C# console project under `qa/rr-study/d001-param-sweep-<date>/` that:

1. Loads each corpus WAV as raw 12 kHz mono float32 (180 000 samples — the `ft8_decode_all`
   contract; **no** resample — that is a playback concern, not a decode concern).
2. For each of the 45 parameter points: `adapter.SetDecodeParams(k, corr, nhard)`, then
   `adapter.DecodeAll(pcm)` per WAV, writing the decodes to a per-point `OpenWSFZ ALL.TXT`-format
   file (so the existing scorers ingest it unchanged).
3. Emits nothing but `ts / freq / snr / message`-shaped decode lines — the same data already in
   ALL.TXT (NFR-021 handling per §4.5).

Determinism note: `DecodeAll` is pure w.r.t. its PCM input and the current param values (no live
audio, no timing), so each point is exactly reproducible from its `(seed-free)` grid coordinates.

### 3.3 Recall arm (07-07 off-air corpus)

For each parameter point, score the harness's decodes against **WSJT-X's** `ALL.TXT` for the 07-07
session using `classify_cochannel.py`'s existing agreement logic, restricted to the two primary
low-SNR bands. Report, per point:

- Overall recall = (WSJT-X low-SNR decodes also produced by OpenWSFZ) / (WSJT-X low-SNR decodes).
- **Broken down by Option B miss class** (Tight / Partial / Isolated) — so we see which knob moves
  which class, and whether any recovery is concentrated in the Isolated class (the
  candidate-generation signal that also answers the isolated-miss pipeline spec's question).
- Recall delta vs the baseline point, in recall percentage points (the same unit as Option B's
  ≤18.4 pp ceiling, so the two are directly comparable).

### 3.4 False-positive arm (synthetic S5 + S7)

For each parameter point, run the same harness over the **S5** (noise-only) and **S7**
(co-channel) synthetic scenarios and score with `matcher.py`. Report, per point:

- S5 FP rate (FP per slot) — the pure-noise OSD-manufacture rate D-009 exists to hold down.
- S7 FP rate and S7 recovery — co-channel FP vs recovery, the D-009 calibration trade.
- FP delta vs the baseline point.

A point is **only** admissible as a "win" if **both** S5 and S7 FP rates are `≤` the baseline's.
Any recall gain bought with an FP regression is not a win — it is re-opening D-009, and is reported
as such, not buried in an averaged score.

### 3.5 The Pareto verdict

Plot every point as (recall-Δpp, S5-FP-Δ, S7-FP-Δ) and identify the Pareto frontier against the
baseline. Three headline outcomes:

- **Dominating point(s) exist** (recall ↑, both FP arms flat-or-down): report the best, with the
  per-class recall breakdown, as a **candidate production reconfiguration** — cost: a settings
  change. Recommend a confirmatory live A/B before it ships (§4.4).
- **Frontier is a strict trade** (recall only buyable with FP cost): report the trade curve so the
  Captain can see the exchange rate, but recommend **no change** — D-009 stands, and the runtime
  knobs cannot help D-001 without hurting D-009.
- **Baseline already dominates** (nothing beats `(10,0.10,60)`): the runtime knobs are exhausted;
  the residual gap is a compile-time (Phase 2) or H7 question. This is the cleanest possible input
  to the H7 decision.

---

## 4. Rigour controls

1. **Two-sided, always.** No recall number is ever reported without its paired S5/S7 FP number from
   the *same* parameter point. The failure mode this guards against is exactly D-009's origin:
   OSD manufacturing plausible-looking callsigns from noise. Recall alone is a vanity metric here.
2. **Baseline locked and always present.** `(10,0.10,60)` is in every grid and every plot as the
   reference; all deltas are against it, not against an idealised zero.
3. **Coarse grid first; refine only around a confirmed win.** 45 points is deliberately low-
   resolution. Over-resolving a recall surface from a *single session's* audio would invite
   overfitting; we resolve finely only where a coarse point already clears both bars.
4. **Held-out / overfitting caveat, stated plainly.** The recall arm can only run on 07-07 (the one
   session with retained WAVs) — 07-06 and 06-22 have no audio to re-decode. So a "winning" point is
   tuned and measured on the same session, and must be treated as a **candidate, not a shipped
   result**. Two mitigations: (a) split the 07-07 corpus temporally (first half tune, second half
   validate) as a within-session overfitting guard; (b) recommend a fresh **live A/B** (baseline vs
   candidate params, both running against live off-air signal via the existing dual-app harness)
   before any production change — the honest confirmation the single-session sweep cannot itself
   provide. The FP arm has no such limit: S5/S7 are synthetic and fully reproducible.
5. **WSJT-X is a recall *reference*, not ground truth.** It has its own low-SNR misses and its own
   FPs; agreement with it inherits the same downward bias Option B documented (§3.3 of that report).
   Restate it; do not re-derive it. This is why the recall arm measures *agreement*, and why the
   *definitive* FP measurement lives entirely in the synthetic arm.
6. **Runtime-only scope is a real boundary, not a limitation to paper over.** These three knobs
   touch pass-1 candidate admission and OSD acceptance only. Pass-0 candidate generation
   (`K_MIN_SCORE`, `K_MAX_CANDIDATES`), LDPC iteration count, and OSD depth (`ndeep=2`) are
   compile-time constants — genuinely out of reach without a rebuild. If §3.5 returns
   "baseline dominates," that is the trigger to scope a Phase 2 (compile-time) sweep, **not** a
   reason to quietly widen this one past its no-rebuild guarantee.

---

## 5. Scope guardrails — what this is NOT

- **Not** a new on-air capture — recall arm is retained 07-07 audio; FP arm is synthetic scenarios
  already in the study.
- **Not** a product or native/decoder code change. It drives the *existing* `ft8_set_decode_params`
  runtime setter and reads decodes. The offline harness is throwaway QA tooling under `qa/`, not a
  change to `src/`.
- **Not** a compile-time / algorithm sweep. LDPC depth, OSD `ndeep`, and pass-0 candidate limits are
  explicitly out of scope (they need a rebuild — Phase 2 if and only if this pass shows the runtime
  knobs exhausted).
- **Not** a reopening of Option B's F=29.6% verdict — it is orthogonal: Option B measured *what
  fraction is co-channel*; this measures *what fraction a cheap reconfiguration recovers*, across
  all classes.
- **Not** a shippable production change on its own. A Pareto-dominating point is a **candidate**
  requiring live-A/B confirmation (§4.4) before it touches the default operating point — the
  single-session recall arm cannot by itself justify changing a D-009-calibrated default.

---

## 6. Deliverables

1. `qa/rr-study/results/<date>-<sha>-d001-param-sweep/report.md` (QA authors Sections 1/5 per
   HK-001) — the 45-point grid as a recall/FP table, the Pareto frontier, the per-class recall
   breakdown for the best point(s), the §3.5 verdict (dominating / trade / baseline-dominates), and
   a recommendation: ship-after-A/B, no-change, or scope-Phase-2. Where recovery concentrates in the
   Isolated class, cross-reference the isolated-miss pipeline spec (this arm empirically corroborates
   or refutes its candidate-generation hypothesis).
2. The offline decode harness (C# console project) + the sweep/scoring driver, committed
   (NFR-021: emits only `ts/freq/snr/candidate-count`-shaped values; the S5/S7 truth and off-air
   ALL.TXT stay local/git-ignored exactly as Option B and the existing study handle them).

---

## 7. References

| Reference | Content |
|---|---|
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` | Option B — the F/F′ verdict and ≤18.4 pp ceiling this sweep is measured against, and the Tight/Partial/Isolated classes it breaks recovery down by |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.h` (`ft8_set_decode_params`, shim 20260030) | The three runtime knobs, their valid ranges, and the D-009-calibrated defaults |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c` (D-009 history, shims 20260025–20260030) | Why two of the three knobs are FP gates; the original S5/S7 calibration this sweep must not regress |
| `tests/OpenWSFZ.Ft8.Tests/SetDecodeParamsTests.cs` | Confirms `SetDecodeParams` is wired end-to-end through the interop adapter |
| `qa/rr-study/diag-fp-engagement-survival-2026-07-18/Program.cs` | The in-process C# harness pattern the offline decode driver reuses |
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/classify_cochannel.py` | Recall-arm scorer (WSJT-X agreement, per miss class) |
| `qa/rr-study/harness/matcher.py` + `STUDY-SPEC.md` (S5, S7) | FP-arm scorer and the synthetic scenarios that provide a definitive false-positive oracle |
| `qa/rr-study/results/2026-06-17-abd6190/report.md` §5 | Prior finding that candidate generation is *not* the Tight-class bottleneck — the basis for the per-knob predictions in §1 |
| `dev-tasks/2026-07-22-d001-isolated-miss-pipeline-diagnosis-spec.md` | Companion pass whose candidate-generation question this sweep empirically probes via the Isolated-class recall breakdown |
