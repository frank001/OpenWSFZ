# Architect → QA: the one-symbol displacement is NAMED — the waterfall origin convention. Spec B-orig-A.

**Author:** Architect
**Date:** 2026-08-21 14:12 UTC (`date -u`, HK-017)
**Authorised by:** the Captain, 2026-08-21 — *"go with b for now"* (explain the one-symbol
displacement before fixing around it).
**Predecessors:** `2026-08-21-1201-…-triage-and-phase-a-deconfounding.md` ·
`2026-08-21-1242-qa-to-architect-phase-a-deconfounding-results.md` ·
`2026-08-21-1330-architect-to-qa-spec-b-pos-a-lattice-position-arm.md` ·
`2026-08-21-1351-qa-to-architect-b-pos-a-results.md`
**Binary under test:** current merged `main` (`a420016`), shim 20260043, DLL SHA256 `1889408787…`.
**Status:** FINDING (derivation + numerical verification) + SPEC for **B-orig-A** (diagnostic, ROW-gated).

---

## 0. Status, and what this is NOT

🔴 **The finding in §1–§2 is a DERIVATION plus a numerical check against a re-implementation. It is
NOT a measurement of the shipped binary.** That is exactly why §6 specs an arm rather than declaring
the question closed.

- 🛑 **ROW 0g is not re-read, re-metriced or amended.** FIRED, task 4.3 VOID, ROW 3 not declared,
  Route B2 not dead.
- 🛑 **This does not authorise changing design.md D1.** That ruling (1201 spec §5) is still the
  Captain's and still owed — though §5 below argues the ruling may no longer be needed at all.
- 🛑 **B3 (`out_diag`) stays HELD.**
- 🛑 **No `src/` or `native/` edit, no rebuild, no push, no merge.** HK-011 is **not** engaged:
  B-orig-A is synth + the two existing exports + a caller-side loop.

---

## 1. THE FINDING — the waterfall's time index is not raw-PCM time

`ft8_coherent_llr_at` and `ft8_extract_llrs_at` take the same two floats and mean **different
instants by them**. The gap is exactly one FT8 symbol, and it is structural.

### 1.1 The grid path lives in waterfall-index space

`ft8_extract_llrs_at` (`ft8_shim.c:1571-1613`) converts `time_offset_s` to a waterfall block index
and reads magnitudes:

```c
raw_time_bin = time_offset_s / mon.symbol_period;   /* -> block index    */
ftx_extract_likelihood_at(&mon.wf, (int16_t)time_offset, ...);
```

and `decode.c:377` reads block `cand->time_offset + sym_idx`. So the grid path never touches
raw-PCM time at all.

### 1.2 The coherent path lives in raw-PCM sample space

`coherent_llr.c:437`:

```c
float origin_sample_f = time_offset_s_grid * fs;   /* fs = 200 Hz baseband */
```

and `coh_window_metrics` places symbol `p` at `origin_sample_f + coh_sym_time_index(p) * sps`.
`downconvert_decimate` is centred (`idx = center + (t - half)`), so baseband sample `m` maps to
PCM sample `m * 60` with **no** group delay — verified this session. The coherent path therefore
treats waterfall block index `b` as **PCM sample `b * block_size`**.

### 1.3 Those two are not the same instant — the waterfall analysis window looks BACK

`monitor.c:74` — and this is the whole finding:

```c
me->nfft = me->block_size * cfg->freq_osr;     /* 1920 * 2 = 3840 samples = TWO symbol periods */
```

`monitor_process` maintains `last_frame` as a **sliding look-back buffer** of `nfft` samples,
shifting in `subblock_size` new samples per `time_sub` (`monitor.c:158-166`), and applies a Hann
window (`hann_i`, peak at `nfft/2`) across the whole thing. So waterfall cell `(block b, sub s)`
analyses PCM samples

```
[ b*B + (s+1)*B/T - B*F ,  b*B + (s+1)*B/T )          B=block_size, T=time_osr, F=freq_osr
```

whose window centre sits at symbol-time `b + (s+1)/T - F/2`.

A symbol truly occupying `[t, t+1)` has centre `t + 0.5`, so the cell that best captures it is the
one with `b + (s+1)/T - F/2 = t + 0.5`. Solving against the coherent path's own assumption
(`t_coh = b + s/T`) gives the displacement in symbols:

> ### `displacement = F/2 + 0.5 - 1/T`
>
> **At production's `K_FREQ_OSR = K_TIME_OSR = 2`: exactly `+1.000` symbol = 0.16 s = 2 quanta.**

It is independent of the row, the symbol index, the sub-index, the SNR and the channel. **A
constant.** That is why B-pos-A read a *concentrated* mode rather than a scattered one.

**Sign:** the waterfall block index runs **one symbol AHEAD** of raw-PCM symbol time. Handed grid's
`time_offset_s`, the coherent path places every symbol one symbol **LATE**, and must move **EARLIER
by one symbol = −0.16 s = m = −2 quanta** to correct.

🔴 **B-pos-A measured coherent's own-best cell at exactly `m = -2`.** Sign, magnitude and constancy
all match a derivation that was not fitted to them.

---

## 2. Numerical verification (Architect, this session — a re-implementation, not the binary)

I re-implemented `monitor_process`'s block/subblock/window indexing in numpy and planted a pure tone
occupying exactly one symbol slot, PCM symbol index 40:

```
top waterfall cells by energy:  block=41 sub=0  (6.17e5)   <- peak
                                block=41 sub=1  (2.30e5)
                                block=40 sub=1  (2.30e5)
=> waterfall block index EXCEEDS true PCM symbol index by +1 symbol
```

Peak at `(41, sub 0)`, i.e. window centre `41 - 0.5 = 40.5 = t + 0.5` — the derivation's own
prediction, to the cell. Sweeping the parameters:

| time_osr | freq_osr | predicted `F/2+0.5-1/T` | measured |
|---:|---:|---:|---:|
| 1 | 1 | +0.000 | +0.000 |
| 1 | 2 | +0.500 | +1.000 ⚠ |
| 2 | 1 | +0.500 | +0.500 |
| **2** | **2** | **+1.000** | **+1.000** |
| 4 | 1 | +0.750 | +0.750 |
| 4 | 2 | +1.250 | +1.250 |

⚠ The single apparent miss is **readout quantisation, not a failed prediction**: at `time_osr = 1`
the lattice quantum is a full symbol, so `+0.5` cannot be represented and lands on a neighbour.
HK-021(o) applies to my own check as much as to a gate.

Displacement also held at `+1.000` symbol (to within the 0.5-symbol cell quantum) as the true signal
was slid across a full symbol in 6 sub-symbol steps — **it does not track the signal, which is the
signature of a convention offset rather than a DSP or channel effect.**

---

## 3. Why §2.2's two "benign causes" were the wrong suspects

Both code-reads in the B-pos-A spec were **correct and remain correct** — they simply pointed at the
wrong two places:

- `coh_sym_time_index` vs `decode.c:373` — identical, and my derivation **requires** them to be
  identical. The offset is not in the symbol map.
- `downconvert_decimate`'s FIR is centred — correct, and again **required**: an uncompensated group
  delay would have *added* to the offset, not caused it.

Both checks examined the **coherent** path. The convention gap lives in the **grid** path's
inheritance from `monitor.c`, which neither check looked at. Recorded as an Architect drafting miss:
I searched the new code and not the code it was being compared against.

---

## 4. Three existing measurements now line up (HK-018 — all already on disk)

| source | measurement | fits? |
|---|---|---|
| **B-pos-A §1** | coherent's own-best cell `m = -2`, mode-concentrated | ✔ sign, magnitude, constancy |
| **Phase A §2** | grid/coherent plateaus displaced ~0.12–0.15 s | ✔ = 2 quanta once quantisation is applied |
| **Phase A §0.2** | synth rendered at `dt_s=0`; grid's best shared anchor **+0.150 s**, coherent's **≈0.030 s** | ✔ **grid is the displaced path; coherent agrees with the synth's own truth** |
| **design.md D3** | unexplained synth-`dt_s` ↔ extractor-`time_offset_s` gap of "~+0.1–0.2 s" | ✔ 0.16 s sits inside it |

🔴 **The fourth row is the important one.** D3 has been an open, unexplained convention gap since
Phase 0. If this finding is right, **D3 and the B-pos-A displacement are the same root cause** — the
waterfall index→seconds mapping is not a raw-PCM time origin, so *everything* that speaks raw-PCM
seconds (the synth's `dt_s`, the coherent correlator's origin) disagrees with the grid path by one
symbol. One defect, not two.

⚠️ Phase A §0.2 is **confirmatory evidence I have already seen**, which compromises blinding — see §7.

---

## 5. What this means for the D1 ruling still owed to the Captain

**Probably that it is not needed.** design.md D1 binds the coherent path to *"the EXISTING grid
position; no dependence on `ft8_refine_candidate()`'s position estimate."*

If §1 is right, the fix is **a unit conversion, not a position search**: convert the waterfall index
to the correct raw-PCM instant by subtracting the `F/2 + 0.5 - 1/T` symbol offset before using it as
a correlation origin. That reads the *same* grid candidate, at the *same* lattice cell, with *no*
search, *no* refinement and *no* new degree of freedom — it just stops mis-reading the units.

🔴 **That is squarely inside D1, not an amendment to it** — which, if ROW 1 fires, would discharge
the 1201 §5 collision without the Captain having to weaken an interpretability guarantee that three
dead-limb-1 results were the reason for.

🛑 I am **not** ruling that now. It depends on B-orig-A firing ROW 1, and the ruling is the
Captain's either way.

---

## 6. SPEC — B-orig-A: does the displacement reproduce against KNOWN GROUND TRUTH?

### 6.1 The question B-pos-A structurally could not answer

B-pos-A ran on **real** rows, where no true `dt` exists. It could measure the *difference* between
the two paths' optima — it could **not** say which path is displaced. §1 makes an asymmetric,
falsifiable claim: **grid is the displaced one.** Synthetic audio with a known true `dt` tests
exactly that.

### 6.2 Design

Synthetic only. Reuse `phase_a_deconfounding.py`'s trial scaffolding, its SNR ladder calibration,
`synth/encoder`, and `coherent_llr_ctypes.py` **verbatim** (HK-018). Build no new population
machinery. **No real-row population helper is touched, so `limit=` cannot bite (HK-021(i)); trials
are independent by construction — no clustering, and do not import one.**

- **N_TRIALS = 100**, distinct messages and independent noise draws, fixed seed, recorded.
- Commanded `dt_cmd` drawn across a **full symbol** (≥8 distinct sub-symbol values) so
  dt-independence is tested, not assumed.
- For each trial, sweep the **absolute** call offset `q * 0.08 s` for integer `q` spanning
  `k_true ± 4` quanta. **Frequency axis fixed at the nominal lattice point (`n = 0`)** — the
  derivation is purely about time; do not sweep frequency and do not spend the budget.
- Per trial record `g_i` = the `q` minimising `n_err_grid`, `c_i` = the `q` minimising `n_err_coh`.

**Statistics (all signed — HK-021(l); all in QUANTA — HK-021(o)):**

```
k_i = round(t_true_i / 0.08)        truth, in quanta, from ROW 0b's measured PCM onset
G_i = g_i - k_i                     grid path's displacement from truth
C_i = c_i - k_i                     coherent path's displacement from truth
```

Report `mode(G)`, `mode(C)`, `frac_at_mode` for each, and the full histograms.
**Derivation predicts `G = +2`, `C = 0`.**

### 6.3 Preconditions (mechanical; each changes the verdict, HK-021(k))

- **ROW 0a — argmin resolvable.** A trial is *undecidable* if its grid or coherent `n_err` argmin is
  tied across ≥2 cells. **If >10% of trials are undecidable ⇒ VOID, escalate, no verdict.**
  Pre-specified remedy (do not improvise): re-run the SNR ladder search of Phase A §0.1 to place the
  grid path's median `n_err` in `[5, 25]`, then repeat once. This is the floor degeneracy both 0g-1
  and Phase A already hit — expect it, don't rediscover it.
- **ROW 0b — the truth axis is measured, not asserted (HK-026).** Do **not** take the synth's
  `dt_cmd` as truth. Measure `t_true` from the **rendered PCM itself** (energy-onset detection,
  decoder-independent). **If <95% of trials agree with `dt_cmd` to within ±0.5 quantum ⇒ VOID,
  escalate** — the truth axis is not identifiable and every downstream number is meaningless.
- **ROW 0c — optima interior.** If `|mode(G)|` or `|mode(C)|` > 3 (i.e. at the ±4 boundary), widen
  the sweep by 2 quanta and re-run **once**; if still at the boundary ⇒ VOID, escalate.

### 6.4 ROWs — strictly ordered, mutually exclusive, exhaustive

| ROW | Condition | Assertion / consequence |
|---|---|---|
| **1** | `mode(G) = +2` **and** `mode(C) = 0` **and** both `frac_at_mode ≥ 0.80` | **CONFIRMED.** The one-symbol displacement is the waterfall origin convention; the **grid** path is the displaced one; coherent is correct in raw-PCM terms. The displacement is no longer unexplained. A narrow, **D1-compatible** origin correction becomes the named Phase B fix; B3 stays HELD; Architect brings the Captain the §5 ruling with numbers. |
| **2** | `mode(G) - mode(C) = +2`, ROW 1's per-path conditions fail | **GAP CONFIRMED, ATTRIBUTION WRONG.** One symbol reproduces against truth, but not with the derived per-path attribution. The convention explanation is incomplete ⇒ escalate; **no fix is specced on this row.** |
| **3** | `mode(G) - mode(C) ∈ {+1, +3}` | **QUANTITATIVELY WRONG.** A displacement reproduces but not at one symbol ⇒ the derivation is wrong in magnitude ⇒ escalate. |
| **4** | `mode(G) - mode(C) ∉ {+1, +2, +3}` | **NOT REPRODUCED.** The displacement is not a property of the synthetic chain ⇒ it is signal- or population-dependent (C4 or unnamed) ⇒ the convention explanation is **dead**; B3 returns as the leading candidate; escalate hard. |

**HK-021(m), resolvable distance stated while drafting:** `mode(·)` is an integer count of quanta;
the readout quantum **is** the gate's own unit, and the thresholds `+2` / `0` are exact lattice
points a full quantum (0.08 s) from the nearest alternative. This is the ideal HK-021(o) case — the
gate cannot land between two resolvable values. `frac_at_mode` at N=100 has quantum 0.01, and the
0.80 bar sits 0.20 (20 trials) above the 0.60 actually observed on real rows in B-pos-A.
**HK-021(n):** ROW 4 is two-sided by construction — it catches displacement in either direction.

### 6.5 Secondary readout (NOT gated, report only)

Per-bit **sign-agreement rate** between `coherent @ (k+2+m)` and `grid @ (k+2)` as a function of `m`.
The derivation predicts a sharp peak at `m = -2`. ⚠️ **Confounded by C1:** the exported LLRs are
fused across `n_syms` 1/2/3, so this is *not* a clean test of the documented `n_syms=1` ↔
`ft8_extract_symbol` identity — isolating that needs B3, which is HELD. Report the curve, draw no
conclusion from it, and do not let it influence the ROW.

### 6.6 Cost

~100 trials × 9 cells × 2 paths × ~12.5 ms ≈ **25 s of compute.** Budget generously; there is no
reason to truncate the sample or economise anywhere in this arm.

---

## 7. Predictions — and a disclosure that they are NOT blind

🔴 **Blinding is COMPROMISED and prediction scoring is SUSPENDED for this arm.** Phase A §0.2 already
reported, for synth rendered at `dt_s = 0`, that grid's best shared anchor was `+0.150 s` and
coherent's `≈0.030 s`. That is this arm's own measurement at lower resolution, taken for a different
purpose, and I have read it. Recording expectations anyway, marked **non-scoring**, per the X1/X2
scoping-run precedent:

- ROW 1 fires: **~80%** (non-scoring).
- If ROW 1 fires, the residual `d_global = -6.0` from B-pos-A is **unchanged** by any origin fix:
  **~85%** — it is C1/C2, not position, and this arm does not address it.

---

## 8. What I have NOT established

- I have **not** measured the shipped binary. §2 verifies a **re-implementation** of `monitor.c`'s
  indexing. A mis-read of the real code, or an additional compensating term elsewhere in the shipped
  path, would both survive my check and be caught by B-orig-A. **That is the point of running it.**
- I have **not** shown this is a defect in the **production decoder**. It is very likely *not*:
  production is self-consistent, because `ftx_find_candidates()` and `ft8_extract_likelihood()` both
  live in waterfall-index space, so the offset cancels. It bites only when an index is converted to
  seconds and used as a raw-PCM origin. 🛑 **Do not let this finding be quoted as "the decoder has a
  one-symbol bug."**
- I have **not** established that this explains the reported-DT convention offset
  (`wsjt_dt_correction_s: 0.55`, UNKNOWN-ACCURACY on the board). 0.16 s is a *candidate contributor*
  to it and nothing more. **Earn that its own pre-registration; do not fold it into this arm.**
- I have **not** explained B-pos-A's residual `-6.0` gap. Out of scope here; it stays with C1/C2.
- §2's parameter table is arithmetic against my own re-implementation, **not** a measurement of the
  shipped waterfall.

---

## 9. Prohibitions for this arm

- 🛑 ROW 0g is not re-read, re-metriced or amended.
- 🛑 No `src/`/`native/` edit, no rebuild, no push, no merge (HK-011, HK-014). If the arm seems to
  need one, **stop and escalate** rather than widen it.
- 🛑 Produces no `f_net` and nothing quotable as a Phase 1 outcome.
- 🛑 Does not authorise changing D1, and does not pre-empt B3.
- ⚠️ **Report offsets in QUANTA, seconds secondary (HK-021(o)).** Never report a requested offset as
  though it were the resolved one.
- ⚠️ HK-025 is available: if any ROW here is diagnostic-only under the classify-and-evaluate-both-
  branches test, **refuse the run and say so** — no partial execution.
