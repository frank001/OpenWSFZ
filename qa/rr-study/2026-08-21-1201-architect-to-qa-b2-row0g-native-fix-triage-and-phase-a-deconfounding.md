# Architect → QA: Route B2 native-fix triage, and the Phase A de-confounding measurement

**Author:** Architect
**Date:** 2026-08-21 12:01 UTC (`date -u`, HK-017)
**Status:** SPEC for Phase A (diagnostic, no ROW). Phase B (native) is SHAPED, NOT SPECCED.
**Trigger:** Captain authorised "proceed with the native-fix option" following
`2026-08-21-1100-qa-to-architect-row0g-fires-phase1-gate-void.md`.
**Binary under test:** current merged `main` (`a420016`), shim 20260043, DLL SHA256 `1889408787…`.
Phase A requires **no** native change, **no** rebuild, **no** Developer session, **no** CI edit.

---

## 0. The one-paragraph version

The Captain authorised a native fix. Reading `coherent_llr.c` end to end first (HK-018) turned up
something that changes the *order* of that work, not the decision: **ROW 0g-2's contrast is
confounded three ways, and every one of the three confounds favours the limb that passed.** 0g-2
correctly voided the Phase 1 gate and that consequence stands — but it does **not** name the
defect, so a native fix written today would be aimed at a guess. The experiment that names the
defect is **pure Python against the already-merged export** and needs no native change at all,
because `ft8_coherent_llr_at`'s signature takes continuous physical units. Phase A below is that
experiment. Phase B is the native fix, specced once Phase A says which one to write.

**This is a sequencing correction inside the authorised work, not a request to reconsider it.**

---

## 1. What 0g-2 established, and what it did not

`d_real` = −67.0 bits, CI95 [−71.0, −65.0] over 190 clusters. The coherent path reads at
`n_err` = 79/174 against a pure-noise null of 84–87. That number is sound and the gate consequence
(task 4.3 VOID, ROW 1/2/3/4 unread, Route B2 **not** dead) stands unchanged.

What it cannot do is localise the fault, because the synth limb and the real limb differ in
**three** ways simultaneously — read out of the harness, not inferred:

| # | Term | 0g-1 (PASSED) | 0g-2 (FIRED) |
|---|------|---------------|--------------|
| 1 | Residual **frequency** error | **exactly 0** — see §1.1 | up to **±1.5625 Hz** (lattice) + integer-Hz reporting |
| 2 | Residual **timing** error | **minimised over a 49-point sweep, per path** (`row0g_instrument_gain_check.py:118-131`) | **one un-swept anchor**, `anchor_dt + 0.65` |
| 3 | **Channel** | clean AWGN synth | real HF: fading, Doppler spread, multipath |

Three causes moved together. Any of them, or all three, could produce the observed collapse.

### 1.1 The frequency confound is exact, not approximate

`_run_clean_trials` renders at `base_freq_hz=1500.0` and calls both exports at `BASE_FREQ_HZ`
(the same literal). 1500.0 Hz lands **exactly** on the production lattice — mechanically checked,
not asserted:

```
min_bin      = round(200.0 * 0.16)      = 32
raw_freq_bin = 1500.0 * 0.16 - 32       = 208.000000   (exact integer)
freq_hz_grid = (32 + 208) / 0.16        = 1500.000000 Hz
```

⇒ **0g-1 exercised the correlator at precisely zero frequency residual.** It could not have
detected frequency sensitivity of any magnitude. This is HK-022's own drafting question —
*"what error could this ROW NOT detect?"* — and the answer turns out to be exactly the error class
that 0g-2 then found.

### 1.2 The timing confound is structural, and Phase 0 already flagged half of it

0g-1 sweeps `TIME_ANCHOR_OFFSETS_S` (49 points) and takes **each path's own best**. 0g-2 uses a
single anchor. Two known, on-the-board uncertainties land entirely on the un-swept limb:

- `STAGE2_ANCHOR_OFFSET_S = 0.65` is on the board as **UNKNOWN-ACCURACY** — D2 measured
  0.531–0.674 across three DLLs, a ±0.07 s spread, i.e. up to **~44% of a 0.16 s symbol**.
- The change's own **design.md D3** records that the synth encoder's `dt_s` and
  `ft8_extract_llrs_at`'s `time_offset_s` conventions are offset by **~+0.1–0.2 s**, discovered in
  Phase 0 and explicitly left unsolved. **0g-1's per-path sweep absorbed that offset. 0g-2 had no
  such absorber.**

⇒ the synth limb structurally neutralised a timing-convention error that the real limb ate whole.

### 1.3 What 0g-1's PASS genuinely buys — this is real, and it narrows the search

A sign error, a bit-attribution error, or a wrong bit-ordering convention would have failed on
**synthetic** audio too. 0g-1 passed with `median(n_err_coh_min)` = 3.00 and signed
`d_clean` = +3.00. Therefore:

> **The formulation is correct. The defect is robustness to real-signal impairment, not
> correctness of the LLR derivation.**

That is a genuine result recovered out of a fired ROW, and it removes an entire class of fix from
Phase B before a single line of C is written.

---

## 2. Candidate defects, code-grounded

### C1 — Scale-incommensurate window fusion (a defect by arithmetic, no measurement needed)

`coherent_llr.c`, final fusion:

```c
if (n_syms == 1 || fabsf(candidate) > fabsf(out_log174[gb]))
    out_log174[gb] = candidate;
```

Every bit takes the **largest-magnitude** candidate across all valid 1-, 2- and 3-symbol windows
covering it. But a coherent sum's magnitude scales with window length — an n=3 window integrates
3× the samples of an n=1 window — so the three sizes produce LLRs **on different scales**, and the
comparison between them is not a reliability comparison at all. It is a near-constant structural
preference dressed as a fusion rule.

The file's own header calls this "an explicit, documented fusion choice." It is documented; it is
not safe. **No normalisation is applied before the magnitudes are compared.**

### C2 — No residual frequency estimation, and the preferred window is the most fragile one

The correlator integrates coherently at `freq_hz_grid` — the candidate's **snapped** lattice
frequency (3.125 Hz spacing ⇒ residual up to ±1.5625 Hz). Coherent integration loss over a window
of duration `T` at residual `Δf` is `|sinc(Δf·T)|`:

| Δf (Hz) | n=1 (0.16 s) | n=2 (0.32 s) | n=3 (0.48 s) |
|---------|--------------|--------------|--------------|
| 0.0000  | 0.0 dB | 0.0 dB | 0.0 dB |
| 0.7450  | −0.2 dB | −0.8 dB | **−1.9 dB** |
| 1.0000  | −0.4 dB | −1.5 dB | **−3.6 dB** |
| 1.5625  | −0.9 dB | −3.9 dB | **−10.5 dB** |
| 2.0833  | −1.6 dB | −7.7 dB | **null** |

🔴 **C1 and C2 compound, and that is the point.** C1 hands almost every bit to the n=3 window;
C2 says the n=3 window is the one destroyed first by frequency residual. At the worst lattice
residual the n=1 window loses under 1 dB while the n=3 window loses over 10 dB — and the fusion
rule takes the n=3 answer anyway.

**0.745 Hz in that table is not a guess** — it is H1a's measured mean `|Δf|` between our reported
frequency and the reference's (n = 1 563, cross-validated against T1's independently measured
`mean_r` = 0.7367 to 0.0085 Hz). The real-world residual is already on disk.

### C3 — Timing residual on a multi-symbol coherent window

Per §1.2, plausible real-limb timing error is a substantial fraction of a symbol. A magnitude-only
single-symbol FFT bin (the grid path) degrades gracefully: at δt = 0.04 s the correct tone still
carries ~75% of the window. A coherent 2–3-symbol window is far less forgiving — the misalignment
both contaminates each symbol with its neighbour *and* breaks the hypothesised continuous-phase
trajectory the correlator is matched to. That grid reads `n_err` = 10 at the same anchor where
coherent reads 79 is **consistent with** a shared timing error the two paths tolerate very
differently. Consistent with — not evidence for. That is what Phase A is for.

### C4 — Channel (fading / Doppler spread / multipath)

Real HF only, and the board's own recorded hypothesis. It cannot be excluded. It should be the
**last** explanation reached for, not the first, because C1–C3 are all present *by construction*
and all cost nothing to test. Reaching for C4 first would mean assuming the expensive cause while
three cheap ones sit unmeasured.

---

## 3. PHASE A — de-confounding (QA, pure Python, no native change)

**Purpose:** name which term collapses the coherent path, by dialling the impairments into
*synthetic* audio one at a time until the real-audio failure reproduces — or does not.

🔴 **Phase A is explicitly DIAGNOSTIC. It defines no ROW, returns no verdict, and can neither
revive nor kill the Phase 1 gate.** ROW 0g stands exactly as pre-registered and as run. Phase A
does not re-read it, re-metric it, or amend it (⇒ the standing "never re-read a closed gate with a
better metric" prohibition is not engaged: this is a new question with its own purpose).

**Method.** The impairment is applied to the **signal**, never to the call — the export snaps
whatever `freq_hz` you pass onto the lattice, so the correlator's assumed position cannot be
dithered from outside. Render the synth off-nominal and call the export at the nominal position.

- **A1 — frequency.** Render at `1500.0 + δf`, `δf ∈ [−1.5625, +1.5625]` in ≥13 steps. Call both
  exports at `1500.0`. Retain 0g-1's 49-point time sweep with per-path minimisation, so the
  timing term stays neutralised — this is what makes A1 a *clean* single-variable curve. Report
  `median(n_err)` vs `δf` per path, with the same trial structure 0g-1 used (M = 20, same `SEED`
  discipline).
- **A2 — timing.** Render at nominal frequency with `dt_s = δt`, and call at a **fixed** offset
  rather than the per-path best, sweeping `δt` across ≥ ±0.06 s. ⚠️ **design.md D3 applies:** the
  synth `dt_s` convention is itself uncalibrated by ~+0.1–0.2 s, so **the absolute zero of this
  axis is not meaningful — only the curve's SHAPE is.** Report degradation per 10 ms of timing
  error relative to each path's own minimum. Do not report an absolute optimal `δt`.
- **A3 — joint, at realistic residuals.** `δf` drawn to match H1a's measured residual distribution
  (mean `|Δf|` ≈ 0.745 Hz), `δt` at the plausible anchor error from §1.2. Report `d_clean` under
  those conditions and compare its magnitude to 0g-2's `d_real` = −67.0 [−71.0, −65.0].

**The discriminating question, stated before the data:** does A3 reproduce a `d` of the order of
−67 bits on *clean synthetic audio* carrying only frequency and timing residual?

- **Reproduces** ⇒ C1/C2/C3 are the mechanism; C4 is not needed; Phase B is well-specified.
- **Does not reproduce** ⇒ the residual terms are insufficient, and C4 (channel) moves from last
  resort to leading candidate — a materially different and more expensive Phase B.

**Cost:** hours, not days. No `src/`, no `native/`, no rebuild, no HK-011, no CI recipe.
**Reuse (HK-018):** `coherent_llr_ctypes.py`, `row0g_instrument_gain_check.py`'s trial scaffolding,
`m3_common.TIME_ANCHOR_OFFSETS_S`, `synth/encoder`. Build no new population machinery.
⚠️ **`compute_matched_hit_control(..., limit=N)` truncates in file order** — if any real-row
population is touched in A3, report CLUSTER counts, never row counts (HK-021(i)).

---

## 4. PHASE B — the native fix (shaped, NOT specced; HK-011 Developer session)

Not written until Phase A reports. Expected shape, in the order the evidence would justify:

- **B1 — fusion normalisation (C1).** Justified on arithmetic alone, independent of Phase A; the
  cheapest and safest of the three. Normalise each window's LLRs to a common scale before the
  cross-`n_syms` comparison, or select a fixed `n_syms`. **B1 is the only item I would consider
  authorising ahead of Phase A**, and even then only bundled with B3.
- **B2 — residual frequency handling (C2).** Only if A1/A3 confirm. 🔴 **See §5 — this collides
  with a binding design decision and needs a ruling before a Developer touches it.**
- **B3 — `out_diag` (enables 0g-3).** Per-`n_syms` selection share. This is the check that would
  have caught C1 directly, and it is currently UNBUILT/UNAUTHORISED. It needs a native change,
  HK-011, **and** `.github/workflows/ci.yml`'s fourth build recipe updated again.

**After any Phase B change: ROW 0g re-runs AS PRE-REGISTERED, both limbs.** Not a variant of it.

---

## 5. 🔴 The D1 collision — an architectural ruling is needed BEFORE any Developer session

**design.md D1 is binding:** *"Phase 1 forms coherent LLRs at the EXISTING grid position; no
dependence on `ft8_refine_candidate()`'s position estimate."* Its rationale is interpretability —
limb 1 is dead three times over (M4 ROW 2, N1 ROW 2, P-LIVE Stage 2 ROW 3/HARM), and stacking
limb 2 on a dead limb 1 makes a limb-2 null ambiguous between "coherent LLRs don't help" and
"the position was already wrong."

**B2 walks straight into this.** A residual-frequency estimator internal to the coherent path is
arguably *not* `ft8_refine_candidate()`'s position estimate — but it is close enough that it must
not be settled by a Developer mid-session, and it changes what the Phase 1 gate measures.

⚠️ **The stakes make this worse, not lighter.** ROW 3 = KILL means Route B2 is dead and D-001 has
no remaining identified route. A gate that has quietly acquired a position-search dependency
cannot carry that verdict.

**I am not ruling on this yet — I want Phase A's answer first,** because if A1 comes back flat then
B2 never gets written and the question is moot. If A1 fires, I will bring the Captain an explicit
choice between (a) amending D1 with its rationale re-argued, or (b) a narrower fix that stays
inside D1 (e.g. B1 alone, or restricting `n_syms` so the fragile window is never selected).

---

## 6. Prohibitions for this thread

- 🛑 ROW 0g is **not** re-read, re-metriced or amended. Phase A is a separate question.
- 🛑 No `src/` or `native/` edit, no DLL rebuild, no push, no merge in Phase A (HK-011, HK-014).
- 🛑 Route B2 is **not** to be called dead, and ROW 3 is **not** to be declared — the gate is VOID,
  which is not the same as failed.
- 🛑 Phase A produces no `f_net` and nothing that may be quoted as a Phase 1 outcome.
- ⚠️ Do not report an absolute optimal `δt` from A2 (design.md D3 — the axis zero is uncalibrated).

## 7. Blind predictions (Architect, recorded before Phase A runs — calibration)

My directional record is poor (2.5/5.5) and I got 0g-2 outright wrong last round at ~70% stated.
Weight these accordingly.

- **A1 fires — coherent degrades markedly faster than grid with `δf`:** ~80%.
- **A3 reproduces `|d|` ≥ 30 bits on clean synth from residuals alone:** ~55%. Genuinely uncertain;
  this is the one that decides whether C4 matters.
- **A3 reproduces the full `|d|` ≈ 67:** ~30%. I expect residuals to explain much, not all.
- **C1 (fusion) is a contributing term rather than incidental:** ~75%, but note this is
  near-unfalsifiable from Phase A alone — it needs B3/0g-3 to measure directly.

## 8. What I have NOT established

- I have **not** shown C1/C2/C3 cause the 0g-2 collapse. I have shown they are present by
  construction, that 0g-1 could not have detected them, and that the arithmetic is unfavourable.
  The mechanism is unproven until Phase A runs.
- I have **not** excluded C4. It is deprioritised on cost, not on evidence.
- The `|sinc(Δf·T)|` table is standard coherent-integration arithmetic applied to this file's own
  window durations. It is **not** a measurement of this correlator.
- I have not re-derived whether GFSK pulse shaping (vs the hard-switching CPFSK reference the
  rotator implements) contributes. 0g-1's PASS on GFSK synth suggests it is second-order, but that
  test was at zero frequency residual and the two effects may not be separable.
