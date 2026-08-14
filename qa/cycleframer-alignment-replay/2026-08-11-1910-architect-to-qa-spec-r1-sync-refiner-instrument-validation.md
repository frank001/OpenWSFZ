# SPEC R1 — The sync refiner, built and validated as an instrument

**Author:** Architect → QA
**Date:** 2026-08-11 19:10:21Z (mechanically derived, HK-017)
**Programme:** `2026-08-11-1910-architect-to-qa-programme-d001-sync-refinement.md`
**Shim version:** **20260040** · **Depends on:** R0 PASS
**Type:** 🔴 **BUILD SPEC with acceptance criteria.** No ROW is read.
**Decode-path change:** 🛑 **NONE.** The refiner is built and exercised through a diagnostic
entry point only. It must not influence a single production decode in R1.

---

## 1. Why this spec exists separately from R2

🔴 **An implementation bug that produces no gain is indistinguishable from a falsified
hypothesis.** If refinement were wired straight into the decode path and recovery did not move, we
could not tell whether refinement doesn't help or whether our refiner is broken — and the
programme would have burned its largest engineering effort for an uninterpretable result.

**R1 validates the refiner against a synthetic oracle where the true answer is known by
construction.** Only an instrument that provably finds a known offset is allowed to touch the
corpus.

🛑 **Do not merge R1 into R2 to save a session.** If asked to, refuse and escalate (HK-025).

---

## 2. What to build

A per-candidate refinement stage, reimplemented **from the method** described below.

🛑 **LICENCE POLICY (Captain's ruling 2026-08-11 — see programme §2.1, which supersedes an earlier
incorrect statement in this spec): WSJT-X source may be READ for understanding of the method. NOT
ONE LINE may be copied, transliterated, or ported.** This is a prohibition, not a judgement call,
and it is not negotiable by QA or by a Developer session. ⚠️ Note the earlier draft of this spec
justified that on "ft8_lib is MIT and copying would relicense our decoder" — **that reasoning was
wrong** (OpenWSFZ is AGPL-3.0); the prohibition now rests on **policy**, and it is absolute either
way. Read the method, write our own.

**Input:** the cycle's PCM (12 kHz, 180 000 samples — already retained by `ft8_decode_all`) plus a
candidate's coarse `(freq_hz, time_offset)` from `ftx_find_candidates()`.
**Output:** a refined `(Δf, Δt)` relative to that coarse position, plus a sync quality score.

**Method (three stages, mirroring WSJT-X's structure without its code):**

1. **Downconvert to complex baseband.** Mix the PCM to baseband at the candidate frequency,
   low-pass, and decimate. FT8 occupies 8 × 6.25 Hz = 50 Hz, so a baseband rate around **200 Hz
   (32 samples per 0.16 s symbol)** gives ample margin — this is also WSJT-X's working point
   (`cd0(0:3199)`). 🔴 **Phase must be retained. This is the entire point of the stage** — the
   existing `uint8_t` magnitude waterfall (`decode.h:21`, `WATERFALL_USE_PHASE` commented out and
   with **zero `#ifdef` branches in `decode.c`**) cannot support refinement, and enabling that
   macro does nothing.
2. **Coherent sync metric.** Correlate the complex baseband against the **three Costas 7×7 arrays**
   (pattern `3,1,4,0,6,5,2` at symbol offsets 0, 36, 72) at trial offsets. 🔴 **Coherent — sum the
   complex values, then take magnitude.** ⚠️ **`ft8_decode_multi_symbols()` in `decode.c:1059` is
   dead code AND does the wrong thing** (`WF_ELEM_MAG(a) + WF_ELEM_MAG(b)`, adding dB magnitudes).
   **Do not use it as a model.**
3. **Two-dimensional search.** Coarse time, then frequency, then fine time — re-deriving the
   baseband at the refined frequency before the fine time pass. WSJT-X's working ranges, offered as
   **a starting point to be tuned by AC-1, not as a requirement to copy**: frequency ±2.5 Hz in
   0.5 Hz steps; fine time ±4 baseband samples at ~5 ms.

**Wiring:** expose via a new diagnostic export (e.g. `ft8_refine_candidate`) callable from the
harness. `ftx_decode_candidate()` must remain untouched in R1.

---

## 3. The validation oracle

Use the existing QA synth (`qa/rr-study/synth/`): `encoder.py` → `symbols.py` → `modulator.py`
(GFSK) → `channel.py` → `wavio.py`. ✅ It is an **encoder-only** oracle, which is exactly what is
needed — truth is known by construction and the decoder side is never involved.

**Generate a test population with offsets placed deliberately, not randomly-only:**
- **frequency offsets** spanning a full lattice cell: at minimum the set
  `{0, ±0.4, ±0.8, ±1.2, ±1.5} Hz` relative to a lattice point, plus uniform-random draws;
- **time offsets** spanning a full cell: `{0, ±0.01, ±0.02, ±0.03, ±0.039} s`, plus uniform-random;
- **SNR strata** covering the operating range, at minimum `{+5, 0, −5, −10, −15, −20} dB`;
- ⚠️ **distinct messages per buffer are mandatory** (standing synth requirement);
- **n ≥ 200 signals per (SNR × offset-class) cell.** If any cell falls short, that cell is
  **underpowered — an instrument failure, not a null** (HK-021(i)); report it as such.

🔴 **Fix strata boundaries GLOBALLY before generating** (HK-021(g)). Do not re-derive per stratum.

---

## 4. Acceptance criteria

All are mechanical. **Bars are derived from the lattice being replaced, not from my expectation.**

**Derivation of the baseline to beat.** The existing scheme picks a lattice cell and uses its
centre: worst case ±1.5625 Hz and ±0.04 s, giving uniform-quantisation RMS of
`3.125/√12 = 0.902 Hz` and `0.08/√12 = 0.0231 s`. **The refiner must beat that by at least 3×**,
which is also roughly where WSJT-X's own 0.5 Hz / 5 ms step sizes land.

| # | criterion | bar | why |
|---|---|---|---|
| **AC-1** | RMS error vs truth, at **SNR ≥ −10 dB** | `RMS(Δf) ≤ 0.30 Hz` **and** `RMS(Δt) ≤ 7.7 ms` | 3× better than the lattice quantisation it replaces. Below this the stage cannot pay for itself. |
| **AC-2** | 🔴 **Systematic bias** | `\|mean(Δf error)\| ≤ 0.10 Hz` and `\|mean(Δt error)\| ≤ 2 ms`, at SNR ≥ −10 dB | **Catches sign-convention bugs in the mixer.** See §5 — this is the highest-probability defect and a sign error makes refinement actively *harmful*. |
| **AC-3** | 🔴 **Noise-only control** | On pure-noise input with no signal, recovered offsets must be **statistically indistinguishable from uniform** across the search range (report the test and its p-value) | A refiner that "locks" on noise manufactures false positives in R2. This is the FP precursor and it must be cleared **before** R2 runs. |
| **AC-4** | Monotonicity in SNR | RMS error must not *increase* as SNR increases, across the six strata | Sanity. A non-monotone curve means a bug, not a physics result. |
| **AC-5** | Determinism | Three independent process runs, results **mechanically byte-diffed** identical | 🔴 *"Two runs, byte-identical" must be MECHANICALLY DIFFED, never asserted.* Depends on R0's `p23_common.py` fix. |
| **AC-6** | Cost | Report wall-clock per candidate and projected full-corpus runtime | Informational — **no fail bar.** See §6. |

**HK-021(k) — both branches evaluated, for every criterion:**
- **AC-1/AC-2/AC-4 FAIL** ⇒ our implementation is wrong. **Fix and re-run. This says NOTHING about
  D-001** and must not be reported as evidence about it.
- **AC-3 FAIL** ⇒ 🔴 **STOP. Do not proceed to R2.** A refiner that locks on noise would inflate
  FP in R2 and the result would be uninterpretable. Escalate.
- **All PASS** ⇒ R2 is armed with a validated instrument, and an R2 null becomes a genuine finding
  about D-001 rather than a suspected bug.

Both outcomes change what happens next in every case, so these are gates and not diagnostics.

---

## 5. 🔴 The specific bug to hunt, stated in advance

**A sign error in the downconversion mixer.** It is the highest-probability defect in this build
and it is nearly invisible: the refiner would still converge, still report plausible offsets, and
still pass a casual eyeball — while moving every candidate in the **wrong direction**, making R2
*worse* than baseline and looking like a falsified hypothesis.

**AC-2 exists precisely to catch it, and it is why bias is gated separately from RMS.** A sign
error inflates RMS only modestly while driving mean error hard away from zero.

⚠️ **This programme has been bitten by exactly this class before:** using `ALL.TXT` field `[5]`
(DT) as frequency instead of `[6]` produced a result that was not merely wrong but *exactly
inverted*, and it cost a near-miss on a published finding. Treat sign and index conventions as
adversarial. **Assert them with a test, never by reading the code twice.**

---

## 6. Cost, and why it is reported but not gated

Per-candidate downconversion is the expensive part. With candidate caps of 140/200 over two passes,
a cycle can present a few hundred candidates, each needing a mix-and-decimate over the buffer.
Existing replay arms run 2 529 cycles in **36–44 minutes**; R2 could be substantially slower.

**Report the number; do not fail on it.** WSJT-X performs this work in real time on far weaker
hardware, so a runtime that looks prohibitive is much more likely to indicate a naive
implementation (e.g. re-deriving the full baseband per trial offset instead of once per candidate,
or a time-domain mixer where an FFT-domain one is available) than a fundamental cost. 🔴 **If the
projected full-corpus runtime exceeds ~8 hours, escalate rather than optimise ad hoc** — the
Captain may prefer to re-scope R2's corpus.

---

## 7. Reporting

Standard QA→Architect report, carrying: the six AC results with their measured values; the
error-vs-SNR curve as a table (not a fitted slope — 🛑 **no parameter is fit or quoted**); per-cell
`n` with any underpowered cell named; the AC-3 null test and its statistic; the byte-diff evidence
for AC-5; measured cost; and the new DLL's SHA256 + shim 20260040.

## 8. Constraints

🔴 **HK-011 in full** — QA authors `dev-tasks/*.md` and STOPS; separate Developer session; Captain
reviews the diff. 🔴 **HK-014/HK-010** — no push, no merge without sign-off.
🛑 **No production decode behaviour may change in R1.** If achieving AC-1 appears to require
touching `ftx_decode_candidate()`, that is R2's scope — stop and say so.
🛑 **subtract-and-resynthesise is DEAD** and is not in scope here or anywhere in this programme.

## 9. Architect predictions (scored on report)

- **AC-3 (noise control): PASS.** Coherent Costas correlation over 21 sync symbols has a
  well-behaved null. Recorded as a **magnitude-free categorical call**, my least-bad category
  (5/7).
- 🛑 **No prediction on AC-1's achieved RMS, and none on AC-6's runtime.** My last four magnitude
  calls all missed with the interval right and the implication wrong. **Nothing in this spec gates
  on any prediction of mine** — every bar above is derived from the lattice or from a null.
- ⚠️ **I expect AC-2 to be the criterion that fails first, if any does.** Recorded as a
  DIRECTIONAL call, which is my weakest category at **1/3** — so it is written as a hunt in §5,
  **not** as a gate.
