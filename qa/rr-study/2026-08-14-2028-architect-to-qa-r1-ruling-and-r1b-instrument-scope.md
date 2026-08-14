# Architect → QA: ruling on R1, and the scope of R1b

**Date (UTC):** 2026-08-14 20:28Z (`date -u`, mechanically derived — HK-017)
**Author:** Architect
**Ruling authority:** Captain, this session ("rule it and let qa write the specs" / "accepted with the unresolved instrument question")
**Input:** `qa/rr-study/2026-08-14-2003-qa-r1-sync-refiner-instrument-validation-report.md`
**Audience:** QA. QA authors the OpenSpec proposal for R1b from this document. The Architect writes no `tasks.md` (HK-015).

---

## 0. Ruling, up front

**R1 is ACCEPTED, with the AC-3 time-dimension question carried forward as an open INSTRUMENT question, not as a defect.** The branch `feat/r1-sync-refiner-instrument-validation` stands as-is. Nothing is reverted. Nothing is re-run before R1b is specced.

Four sub-rulings, in descending order of consequence:

| # | Subject | Ruling |
|---|---|---|
| R-1 | AC-1 frequency | **PASS stands, but is DOWNGRADED in meaning** — it measured the search grid, not the refiner (§2) |
| R-2 | AC-4 monotonicity | **VOID BY CONSTRUCTION** — the gate was diagnostic, and the fault is the Architect's (§3) |
| R-3 | AC-3 time | **FAIL stands as an observation; the ESCALATION is re-scoped** from "find the mechanism" to "fix the instrument" (§4) |
| R-4 | R2 | **Remains blocked**, but on R-3's instrument question only — not on a decode-path defect (§6) |

AC-2, AC-5, AC-6, the production-equality replay, and 309/309 are accepted without qualification. The two CPFSK defects found and fixed in §3 of the report are accepted as real architectural corrections and are the most valuable output of the session.

---

## 1. What I verified myself before ruling (HK-018)

I did not rule from the report's prose. Verified directly against `native/ft8_lib_vendor/refine/sync_refiner.c` and the committed `results/2026-08-14/run_a.json`:

| Claim | Verified how | Result |
|---|---|---|
| Frequency grid is 11 points at 0.5 Hz | `REFINE_FREQ_HALF_HZ 2.5f`, `REFINE_FREQ_STEP_HZ 0.5f` (L76–77) | **Confirmed** |
| No fine-frequency stage exists | `best_df` assigned only in the Stage A+B loop (L335); `*out_delta_freq_hz = best_df` (L403); Stage C searches time only (L390–401) | **Confirmed** |
| Both argmax loops break ties toward the most-negative index | `if (mag > best_score_ab)` (L335) and `if (mag > best_score_c)` (L396), both strict `>`, both looping from `d = -half` upward | **Confirmed** |
| Coarse time grid ±60 ms / 5 ms; fine ±10 ms / 0.5 ms | `REFINE_COARSE_TIME_HALF_SAMPLES 12` @ 200 Hz; `REFINE_FINE_TIME_HALF_MS 10.0f`, step `0.5f` | **Confirmed** — composite range ±70 ms, matching the report's 14 bins |
| Buffer-edge hypothesis (my own first candidate) | `downconvert_decimate` zero-pads via `if (idx < 0 \|\| idx >= n) continue;` (L132); coarse FIR half-width 60 samples ≈ 5 ms @ 12 kHz; earliest sample any noise trial reads is t₀−0.07 s ≥ 0.03 s | **REFUTED — my hypothesis was wrong.** The FIR edge is never reached. Recorded because a discarded hypothesis is evidence too. |
| `coarse_time_offset_s` / `coarse_freq_hz` are recorded per noise trial | `run_a.json` → `noise_results[*]` record keys | **Confirmed — stratification in §5 is identifiable from already-committed data** |
| `best_dt_samp` / `best_fine_samp` are recorded | Same | **ABSENT. This is the blocking gap — see §4.** |

---

## 2. R-1 — AC-1's frequency PASS measured the grid, not the refiner

The frequency search grid has step 0.5 Hz. The RMS of uniform quantisation error at step *h* is *h*/√12:

> 0.5 / √12 = **0.14434 Hz**

Measured RMS(Δf), all six SNR strata: 0.1442, 0.1416, 0.1432, 0.1428, 0.1473, 0.1386 — mean **0.1430 Hz**, flat within ±3% across **25 dB** of SNR.

That is the quantisation floor to three significant figures, and it does not move with SNR at all. **RMS(Δf) is therefore an estimate of `REFINE_FREQ_STEP_HZ`, not of the refiner's frequency accuracy.** It would read the same for any algorithm that lands in the correct coarse cell — the correlator's quality is invisible to it. This is HK-026 firing exactly where MEMORY.md predicted it would ("Fires NEXT on R1/R2"): the instrument's own output was used to characterise a bound that sits inside the instrument's own discretisation.

The PASS is not withdrawn — the refiner does land in the right cell, which is a real result. But two things follow and both bind R2:

1. 🔴 **The refiner has no sub-0.5 Hz frequency capability. None. There is no fine-frequency stage in the code.** R2 must not assume one exists. 0.5 Hz is 6.25× finer than the 3.125 Hz lattice and may well be sufficient for D-001 — but that is now an explicit design question to answer, not an established property.
2. The AC-1 frequency bar (0.30 Hz) sits only ~2× above the floor it was unknowingly measuring. Any successor bar must be stated relative to the grid step, or the grid must be refined first.

Δt is only partly floored: 1.515 ms at −20 dB falling to 1.109 ms at +5 dB, saturating by −10 dB. So the time dimension does carry some genuine SNR response. Frequency carries none.

**Action for R1b's spec:** carry this as a stated finding and a design question ("is 0.5 Hz sufficient for R2, or is a fine-frequency stage required?"). Do **not** silently add a fine-frequency stage in R1b — that is R2 scope and needs its own pre-registration.

---

## 3. R-2 — AC-4 was a broken gate, and it is mine

At n = 400 per stratum, the relative standard error of an RMS estimate is ≈ 1/√(2n) = **3.5%**. The observed spread across strata is ±3%. The three "violations" are +0.0016 Hz, +0.0045 Hz and +0.024 ms — all inside sampling noise, against a truth (§2) that is genuinely flat in frequency by construction.

Under a flat truth, each adjacent pair steps upward with probability ≈ ½. Five pairs × two dimensions = ten comparisons:

> P(zero violations) ≈ 2⁻¹⁰ ≈ **0.1%**

**AC-4 as I wrote it had a ~99.9% probability of returning FAIL for a flawless refiner.** It returns the same row regardless of the state of the world. That is the definition of a diagnostic gate under HK-021(k), and QA would have been entitled to refuse to run it under HK-025 before arming. It was not caught pre-arming; that is a process observation, not a criticism of QA — the gate reached QA with my name on it.

**Ruling: AC-4's verdict is recorded as VOID BY CONSTRUCTION, not FAIL.** A FAIL implies information the gate could not carry. The record must not show R1 failing a monotonicity criterion it was never given a fair chance to pass.

Per the standing rule — *never re-read a closed gate with a better metric; it earns a NEW pre-registration* — any successor is a fresh gate in R1b's proposal, not an amendment. My recommendation to QA for drafting it: a monotone **trend** statistic across the full SNR ladder with a pre-declared tolerance derived from the n-dependent RMS standard error, with an explicit ROW 0, drafted by writing the code that evaluates it first (HK-021). Note that per §2 the frequency dimension is floored and cannot show a trend at all — a frequency monotonicity gate is **unidentifiable** until the grid is refined, and should not be re-pre-registered at all.

---

## 4. R-3 — the AC-3 escalation is re-scoped: the gap is instrumentation, not mechanism

The report's conclusion (a selection-bias interaction between Stage A+B's argmax and Stage C's re-derivation on the same noise) is plausible and consistent with every control it ran. But it cannot currently be tested, and that — not the mechanism — is what blocks R2.

### 4.1 The blocking fact

`ft8_refine_candidate` returns only the **sum**. The committed JSON records `measured_delta_time_s` and nothing else about the decomposition. `best_dt_samp` and `best_fine_samp` — the two quantities the entire hypothesis is stated in terms of — **are not exported and are not recoverable from any committed artefact.**

Consequently §5's load-bearing claim, that "`best_dt_samp` and `best_df` each look individually close to uniform," is asserted from an unrecorded sample viewed by eye during debugging, not computed over the 1,200 trials. Under HK-021 that claim cannot support a conclusion. It is not wrong — it is untested.

### 4.2 Two structural facts that sharpen the question

**(a) Stage C re-searches territory Stage A+B already rejected.** Fine half-width is 10 ms; the coarse step is 5 ms. Stage C's window is **four coarse cells wide**, on the same PCM, against a differently-filtered score surface (900 Hz cutoff @ 2 kHz vs 90 Hz @ 200 Hz). That is the double-dipping, now quantified rather than described.

**(b) The entire FAIL lives in the two most fragile cells of the null.** Δt = 0 is reachable by many (coarse, fine) pairs; Δt = ±70 ms is reachable by exactly **one** (±60, ±10). That path-multiplicity is what makes the null trapezoidal — correctly modelled by the report *if* the two stages are independent. They are not, and any violation of that assumption concentrates its distortion precisely in the single-path extreme bins, which is exactly where the χ² is being driven (102 vs 32.8; 6 vs 32.8).

So the FAIL rests on a post-hoc instrument whose one load-bearing assumption is known to be false in the cells that produce the verdict.

### 4.3 What survives regardless

The **asymmetry** does. Any symmetric null — trapezoidal, uniform, or unknown — is symmetric about zero. A 102 : 6 imbalance between mirror-image extreme bins is a statement about the refiner that requires no grid model and no independence assumption at all.

🔴 **Ruling: AC-3's time sub-check is to be re-expressed as a shape-free symmetry test.** Compare the observed Δt distribution against its own reflection. No convolution, no independence assumption, no HK-026 exposure. That is the gate. It is mechanical, its metric is identifiable, and it evaluates both branches.

---

## 5. R1b scope — what QA writes the specs for

**Deliverables:**

- **D1 — export the decomposition.** `ft8_refine_candidate` gains out-parameters for the Stage A+B and Stage C selections (`best_dt_samp`, `best_fine_samp`, and `best_df` explicitly). Shim bump to **20260041**, ABI/interop delta, P/Invoke and adapter updated. Diagnostic-only; **no production call site**, exactly as R1. This is the precondition for everything else.
- **D2 — replace AC-3's time gate** with the shape-free symmetry statistic of §4.3, plus mechanically computed marginals for each stage separately over the full n = 1,200.
- **D3 — stratify** the noise results by `coarse_time_offset_s` and `coarse_freq_hz`. Both are already recorded (verified, §1), so this runs against **committed data with no new run**. Do this first; it is the cheapest thing in the plan.
- **D4 — replace AC-4** per §3, or explicitly retire it. Frequency monotonicity is unidentifiable (§2) and should not be re-pre-registered.
- **D5 — carry §2's finding** into R2's design inputs: 0.5 Hz is the refiner's frequency resolution, full stop.

**Non-gating diagnostic hypotheses.** These are mine, they are DIRECTIONAL, and my own calibration on directional predictions is **1.5/3.5** — the weakest class I have. 🛑 **No gate in R1b may turn on which of these is right.** They are offered as cheap discriminators to run *after* D1 lands, not as a conclusion to confirm:

- **H-A — argmax tie/plateau convention.** Both loops use strict `>` scanning from the most-negative index, so the earliest index wins any tie or plateau (verified, §1). Note this cuts against the report's constant-DC control: a *perfectly flat* score curve is all ties, and first-index argmax then returns the most negative offset every time — that control demonstrates the mechanism rather than excluding it. It is also inherited by the numpy replica (`np.argmax` returns first-max), so "the Python replica reproduces it" does **not** rule out a shared convention fault. *Discriminator:* flip to `>=` and see whether the pile-up moves to bin 13.
- **H-B — coarse-filter aliasing.** `REFINE_LP_CUTOFF_COARSE_HZ` is 90 Hz against a 100 Hz Nyquist at the 200 Hz coarse rate — a very tight transition band. Asymmetric leakage about the downconverted carrier gives the complex baseband an autocorrelation with a non-zero odd part, which can bias a magnitude-argmax over time lags directionally. Inherited by the replica (same filter), and vanishes when *d* is held fixed — consistent with every observation. *Discriminator:* lower the cutoff to ~60 Hz (still above the 50 Hz tone span) and/or raise the tap count; if the asymmetry shrinks, it is the filter.
- **H-C — genuine selection bias**, as the report concluded. Reach this only after H-A and H-B are excluded.

**Constraints binding the spec:**

- 🔴 **HK-026:** do not derive the acceptable-asymmetry bound from the refiner's own output. It must come from the grid geometry or an explicit pre-registered tolerance.
- 🔴 **HK-021:** every gate carries an explicit ROW 0; draft each by writing the evaluating code first; confirm each metric is identifiable from the data it runs on. D1 exists precisely because that check failed for AC-3.
- 🛑 **HK-011:** QA authors the proposal and stops. Implementation is a separate Developer session.
- ⚠️ **macOS is now two shim versions stale** (`osx-arm64/libft8.dylib`, unrebuilt through R0 and R1). Not blocking — CI rebuilds from source — but R1b bumps to 20260041 and the gap should be named in the proposal rather than inherited silently for a third round.

---

## 6. R-4 — R2 stays blocked, and why the distinction matters

R2 remains un-proposable until the symmetry question resolves. But the character of the block has changed: it is **not** evidence of a defect in a decode-path refiner (there is no decode-path refiner — R1's export has no production call site, and the 250-cycle replay confirms zero behavioural change). It is an unresolved question about a diagnostic instrument.

That matters for sequencing: D3 is an offline re-analysis of committed data, and D1+D2 are a narrow instrumentation change. If §4.3's symmetry test comes back clean once the decomposition is visible, R1b closes quickly. If it comes back asymmetric with the per-stage marginals in hand, the mechanism will be localised to one stage instead of being attributed to an interaction that cannot presently be observed.

---

## 7. What I am *not* ruling

- I am not ruling on the mechanism of the time asymmetry. I had one hypothesis, checked it against the source, and it was **refuted** (§1). I will not ship a second guess as a ruling.
- I am not ruling AC-3's frequency sub-check into question. χ² over 11 discrete categories against a flat null is the right instrument for a genuinely discrete output, and p = 0.94 is unremarkable in the good sense.
- I am not asking for any part of R1 to be reverted or re-run before R1b is specced.

---

## 8. Over to QA

Write the OpenSpec proposal for **`r1b-sync-refiner-instrument-correction`** covering D1–D5 above, with the ACs drafted mechanically per HK-021 and every gate carrying ROW 0. Run D3 first — it needs no new data and may reshape the rest.

If any gate in this document fails HK-025's two-step classification when you go to draft it, **refuse it and say so.** That applies to everything here, including §4.3's symmetry test. I have written one diagnostic gate into this programme already (§3); I would rather be told than have it run.
