# QA → Architect: ROW 0g FIRES — Phase 1 gate is VOID, task 4.3 NOT run

**Author:** QA
**Date:** 2026-08-21 11:00:40Z (mechanically derived via `date -u`, HK-017)
**Runs:** `qa/rr-study/2026-08-21-1038-architect-to-qa-spec-b2-phase1-row0g-instrument-gain-check.md`
(task 4.4, the precondition on task 4.3)
**Harness (new):** `qa/rr-study/r2-coherent-llr-instrument/coherent_llr_ctypes.py`,
`row0g_instrument_gain_check.py`; results in `results/row0g_report.json` /
`results/row0g_run.log`
**Status:** 🔴 **ROW 0g FIRES (limb 0g-2). Per the pre-registration's own Sec.2.4
consequence: the Phase 1 gate is VOID. Task 4.3 was NOT run — no ROW 1/2/3/4 read from
any output. ROW 3 MUST NOT be declared. Route B2 MUST NOT be called dead.** No `src/`
touched, no DLL rebuilt, no Developer session — both limbs ran against the current
merged binary (shim 20260043, PR #128) exactly as the pre-registration specified.

---

## 0. Headline

The Captain's instruction to "include the check" was the right call. On **20 clean,
noise-free synthetic signals**, the coherent path performs at least as well as the
existing grid extractor (0g-1 PASSES in full, no stub degeneracy). But on **200 real
P-HIT rows** — real captured audio, same population and anchor Phase 1's own gate will
run on — the coherent path's bit-error count collapses to **near the pure-noise null**
(median n_err = 79, against a chance level of 87/174) while the grid path stays at its
usual **median n_err = 10**, consistent with Stage 2's own already-published numbers.
The paired difference is decisive: `d_real = -67 bits`, cluster-bootstrap CI95
`[-71, -65]` (190 clusters), nowhere near the `CI_hi < 0` firing threshold — this is not
a marginal call.

This is exactly the asymmetry ROW 0g was pre-registered to catch: a defect that is
invisible on a static, drift-free synthetic bench and only manifests on real signals.
Had ROW 0g not been added, task 4.3 would have measured a real `f_net` against a broken
coherent correlator and — per the code-read hazard already on the board — that failure
mode reads as **ROW 3, KILL**, exactly the verdict the precondition exists to prevent
from being trusted blindly.

---

## 1. Gate trace, strict order

| Row | Check | Measured | Result |
|---|---|---|---|
| — | HK-025 independent re-classification | VALIDITY, both branches differ, no refusal | concurs |
| — | DLL pin (current merged binary) | SHA256 `1889408787a2c7ea...`, shim 20260043 | confirmed |
| 0g-1a | `median(n_err_coh_min) ≤ 5` | measured **3.00** (at the floor-degeneracy rerun, see §2) | **PASS** |
| 0g-1b | `d_clean ≥ 0` (signed) | measured **+3.00** | **PASS** |
| — | stub degeneracy (≥95% bit-identical) | 0/20 comparable trials identical | clear |
| 0g-2 | `CI_hi(d_real) ≥ 0` | measured `d_real = -67.0`, CI95 `[-71.0, -65.0]` | **FIRES** |

**ROW 0g overall: FIRES**, on 0g-2 alone (0g-1 passed cleanly). Per the pre-registration,
one firing limb is sufficient — the gate is VOID regardless of 0g-1's result.

---

## 2. Limb 0g-1 — clean-signal ceiling (construction note, recorded per HK-018/HK-022)

The noiseless construction (`snr_db=None`) hit the **floor-degeneracy guard immediately
and completely**: both paths read exactly 0 errors on all 20 trials, every offset in the
49-point sweep considered. This is not a null result — it means the correlator is
comfortably good enough that a driftless synthetic tone can't discriminate it from the
existing grid extractor at all.

The contingency (re-run limb (b) with added noise until `median(n_err_grid_min)` lands
in `[5, 25]`) needed far more attenuation than an initial SNR ladder assumed. Each FT8
symbol integrates over ~0.16 s (≈1920 samples at 12 kHz); relative to the 2500 Hz
reference bandwidth `noise_sigma_for_snr`'s `snr_db` is defined against, that is roughly
20–25 dB of processing gain, so `snr_db` values in the range ROW 0c's own NOISE
sub-check used (0–30 dB) read as **effectively noiseless** here. The ladder that
actually lands in the target band sits around **-19 dB**, empirically probed and now
recorded in the harness's own comment rather than left to be rediscovered. At that
level: `median(n_err_grid_min) = 8.00`, `median(n_err_coh_min) = 6.00`,
`d_clean = +3.00` — **coherent modestly outperforms grid on synthetic data**, the
opposite direction from what real data shows below.

No stub degeneracy at any noise level tested (grid and coherent outputs were never
bit-identical, even where both read 0 errors) — the two paths are doing genuinely
different computation, just not equally well on real audio.

---

## 3. Limb 0g-2 — paired on real P-HIT data (the decisive limb)

200-row deterministic sample (seed 20260821) from a 25,411-row / 4,371-cluster P-HIT
population; 193/200 rows delivered (7 dropped, `no_true_codeword`), **190 distinct
clusters delivered** — comfortably clear of the 100-row/60-cluster floor.

Raw distributions (not gated on directly, reported for the record):

| path | median n_err | mean n_err | min | max |
|---|---|---|---|---|
| grid (existing `ft8_extract_llrs_at`) | 10 | 17.42 | 0 | 79 |
| coherent (`ft8_coherent_llr_at`) | **79** | 76.90 | 26 | 102 |

The grid numbers are unremarkable and in line with Stage 2's own already-published
figures on this population. The coherent numbers sit almost exactly at the
binomial(174, 0.5) null Phase 0's own ROW 0c measured (**mean 84.0** on pure noise) —
the coherent path is behaving, on real audio, close to indistinguishable from chance.

`d_real = median(n_err_grid - n_err_coh) = -67.0`, cluster-bootstrapped by `ts`
(2000 draws, 190 clusters): **CI95 `[-71.0, -65.0]`**. The bar fires at `CI_hi < 0`; here
`CI_hi = -65.0`, not a near-miss by any margin.

**This is a materially different shape from the code-read hazard already on the board.**
Sec.1 of the pre-registration described a *gain-reduced but correctly-signed* failure
mode (partial destructive combining from the rotator's advance-before-use convention at
`n_syms=2/3`) — a degradation, not a collapse to chance. What 0g-2 measures instead
looks more like a near-total loss of coherent gain on real signals specifically, while
the same correlator performs at least as well as the grid path on driftless synthetic
tones. A plausible (not yet verified) explanation: real captured audio carries genuine
frequency/phase drift over a message's ~12.6 s duration (propagation, local-oscillator
offset) that a static synthetic tone never exercises, and the coherent path's per-window
phase tracking may be far more sensitive to that than the grid path's single-symbol
magnitude-only extraction. **This is a new hypothesis, not a finding** — it is offered
so a future native investigation doesn't start from zero, exactly as the pre-registration's
own §1 reasoning was offered for the same purpose.

---

## 4. Consequence (as an assertion, per the pre-registration's own Sec.2.4)

**ROW 0g FIRES ⇒ the Phase 1 gate is VOID.** No ROW 1/2/3/4 may be read from any output
this session. In particular:

- **ROW 3 (KILL) MUST NOT be declared.**
- **Route B2 MUST NOT be called dead.**
- Task 4.3 was **not run** — there is no `f_net`/`C_ber` number to report, and none
  should be inferred from the numbers above (they are `n_err` counts, not `f_net`).
- The remedy is a **native fix under HK-011**, then a **re-run** of ROW 0g — not a
  re-read of this output with a different metric (standing prohibition, restated in the
  pre-registration itself).

`0g-3` (the per-`n_syms` selection-share diagnostic) is **not built and not authorised** —
the shipped export has no `out_diag` parameter. Per the pre-registration's own Sec.3,
now that 0g has fired, **0g-3 becomes the first thing to consider building**, since it
would show directly whether the fusion is scale-driven (as Sec.1(a) hypothesised) or
something else entirely (as §3 above speculates). That is a native change requiring a
Developer session and, per the same section, an update to `.github/workflows/ci.yml`'s
own fourth build recipe (the defect class that has now recurred twice).

---

## 5. Calibration against the Architect's recorded predictions

| prediction | stated confidence | outcome |
|---|---|---|
| 0g-1a PASS | ~65% | **correct** |
| 0g-1b (genuinely 50/50) | no confidence claimed | **PASS** (+3.00) |
| 0g-2 PASS | ~70% | **wrong — FIRES, decisively** |

Recorded for the standing calibration ledger, not adjudicated here.

---

## 6. Stop

No `src/`/`native/` touched. No DLL rebuilt. No Developer session opened. No push, no
merge. Task 4.3 remains **BLOCKED** on task 4.4 — which has now run and fired, so the
block is not lifted; it is confirmed. QA stops here and awaits the Architect/Captain's
direction on whether to pursue a native fix (HK-011 Developer session) or hold Route B2
pending further triage.
