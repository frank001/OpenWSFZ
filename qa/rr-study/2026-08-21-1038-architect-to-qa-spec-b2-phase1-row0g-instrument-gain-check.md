# Architect → QA — B2 Phase 1: ROW 0g, the instrument-gain check (pre-registration)

**Author:** Architect
**Date:** 2026-08-21 10:38Z (`date -u`, HK-017)
**Status:** PRE-REGISTRATION. Written before the check exists and before any Phase 1
number has been computed. Nothing in this document has been run.
**Amends:** `qa/rr-study/2026-08-19-1850-architect-to-qa-spec-b2-phase1-coherent-llr-kill-gate.md` §3 (ROW 0 table)
**Implements:** `openspec/changes/r2-coherent-llr-instrument/tasks.md` §4.3, additional precondition
**Authorised by:** the Captain, 2026-08-21 — "include the check"

---

## 0. What this adds and why, in one paragraph

Phase 1's gate can return **ROW 3 — KILL**, whose stated consequence is that Route B2 is
dead in full and *D-001 has no remaining identified route*. That verdict is only worth
having if a low `f_net` means "coherent LLRs don't help." **This document adds one
pre-registered precondition, ROW 0g, that separates that reading from "the coherent
correlator is defective."** It runs against the **current merged binary**, needs **no
native change and no Developer session**, and it runs **before** the gate, not after.

---

## 1. Why this is not paranoia — the code read that motivates it

🔴 **This section is REASONING FROM A CODE READ, not a measurement. It is recorded here
so that if ROW 0g fires, the diagnostic lead already exists — and so that if ROW 0g
passes, this reasoning is on the record as having been checked and found not to bite.
It is NOT a finding and must not be cited as one.**

QA's merge review (2026-08-21 10:22Z) carried one unresolved item: the rotator's
"advance-before-use" phase convention is proven magnitude-neutral for `n_syms=1` but
**unresolved for `n_syms=2/3`**. Reading `native/ft8_lib_vendor/refine/coherent_llr.c`
raises that from an open question to a specific, named hazard with two limbs.

**(a) The fusion selects on raw magnitude, and the window sizes are not on a common
scale.** `coh_window_metrics` computes `out_mag[j] = |sum|` where `sum` accumulates
coherently over `n_syms × ~32` samples, with **no normalisation by window length or
`n_syms` anywhere**. The fusion (`coherent_llr.c`, the `n_syms` loop) then keeps, per
bit, the largest-`|·|` candidate across every window of every size:

```c
if (n_syms == 1 || fabsf(candidate) > fabsf(out_log174[gb]))
    out_log174[gb] = candidate;
```

A 3-symbol coherent sum is ~3× the amplitude of a 1-symbol sum on the same signal *by
construction*. So this comparison is **systematically biased toward `n_syms=3` on scale
alone, independent of evidence quality.** If that is what is happening, the 1- and
2-symbol paths are decorative wherever a 3-symbol window is valid. That may be
harmless — if the 3-symbol metric is genuinely better, preferring it is correct — but
nothing I have read establishes the three sizes are comparable *before* they are
compared, and `coh_normalize_logl` runs **after** the fusion, too late to fix it.

**(b) The rotator's phase can drift across a symbol boundary, and (a) makes that
drift poisonous rather than harmless.** The rotator advances once per sample over
`[i0, i1)` where `i0 = floorf(sym_start_f)`, `i1 = floorf(sym_start_f + sps)`. The
number of samples in that half-open interval varies by ±1 depending on where the
fractional symbol boundary falls, while the *true* phase advance over the symbol is the
exact (fractional) duration. For `n_syms=1` any such error is a constant phase on the
whole sum and `sqrtf(re²+im²)` absorbs it — which is exactly why the neutrality proof
succeeds at `n_syms=1`. For `n_syms=2/3` the rotator is **not reset at the symbol
boundary**, so the error becomes a *relative* phase between symbols within the window ⇒
partial destructive combining ⇒ **magnitude reduced, sign structure largely preserved.**
That is precisely the "gain-reducing but correctly-signed" defect class QA flagged, and
precisely the class ROW 0c's sign test cannot see.

🔴 **Why the two limbs compound into a false ROW 3.** Both plausible defect directions
land on the same verdict:

| if `n_syms=2/3` is… | fusion behaviour | effect on `f_net` | verdict |
|---|---|---|---|
| gain-reduced, sign correct | may still win max-`\|·\|` on the 3× scale advantage | degraded LLRs preferred over good ones | pushed toward **ROW 3** |
| gain-reduced enough to lose | `n_syms=1` wins; output ≈ magnitude-only | coherent ≈ grid, `f_net` ≈ 0 | **ROW 3** |
| correct | 2-/3-symbol evidence used | real signal | whatever is true |

**Two of the three rows above reach ROW 3 for instrument reasons.** A kill verdict on
this gate is therefore not self-validating, and ROW 0g exists to make it so.

---

## 2. ROW 0g — the check

**Placement:** ROW 0g is appended to the Phase 1 spec §3 ROW 0 table. It is evaluated
**after** 0a–0f and **before** any evaluation of `f_net`. `0f` is already taken
(determinism); this is `0g`.

🔴 **It is unconditional and runs FIRST.** It is *not* held in reserve for a bad
outcome. Running a validity check only when you dislike the answer is outcome-conditional
validation: it accepts good news uncritically and would make a ROW 1/ROW 2 "Phase 2
authorised" verdict rest on an instrument nobody checked. The asymmetry in §1 is about
which *consequence* is most costly, not about when to look.

### 2.1 HK-025 classification (recorded per Phase 0's own convention)

| field | value |
|---|---|
| **class** | **VALIDITY** — not precision |
| **reason** | a defective correlator produces a low `f_net` indistinguishable from a true null, and the gate's ROW 3 consequence is to declare D-001 routeless |
| **branch: PASS** | gate proceeds; ROW 1/2/3/4 evaluated as pre-registered, unchanged |
| **branch: FAIL** | gate is **VOID**; **no** ROW 1/2/3/4 may be read |
| **same row either way?** | **No** — the branches yield different verdicts ⇒ not diagnostic ⇒ survives HK-021(k)/HK-025 |

### 2.2 Limb 0g-1 — CLEAN-SIGNAL CEILING (synthetic, no native change)

**The argument this limb rests on:** on a **noise-free** signal, coherent combining
*cannot legitimately lose to* non-coherent magnitude-only extraction. There is no
channel effect to explain it. If it loses here, the implementation is at fault, and no
appeal to physics is available.

- **Signal.** `M = 20` clean synthetic FT8 signals via
  `qa/rr-study/synth/encoder.encode_message`, distinct messages (NFR-021: Q-prefix
  synthetic callsigns only), `snr_db=None` (noise-free), seeded, `base_freq_hz` fixed at
  the population's nominal 1500 Hz.
- 🔴 **The D3 landmine, handled explicitly.** Phase 0 established that
  `encoder.encode_message`'s `dt_s` and the extractors' `time_offset_s` conventions are
  offset by roughly **+0.1–0.2 s** (`r2_sign_test.py` header; the naive construction gave
  `n_err ≈ 70/174` on a *clean* signal). **Do not attempt to resolve that convention** —
  it is out of scope and unchased. Instead, **sweep** `time_offset_s` over
  `m3_common.TIME_ANCHOR_OFFSETS_S` (49 points, −1.20 s to +1.20 s, step 0.05 s — reused
  verbatim, HK-018) and take the **minimum `n_err` over the sweep**, independently, for
  each path. Frequency is held at nominal: the lattice-snap arithmetic is byte-identical
  between the two exports (QA verified at merge), so frequency convention is not in
  question here.
- 🔴 **Minimise each path independently.** `n_err_coh_min` uses the coherent path's own
  best sweep point; `n_err_grid_min` uses the magnitude path's own best sweep point. This
  gives each its best shot and is **conservative toward PASS** — the construction cannot
  manufacture a coherent failure.
- **Statistics** (`_count_errors` and `ex.true_codeword`, reused verbatim from
  `r2_sign_test.py`):
  - `(a) ABSOLUTE`: `median over trials of n_err_coh_min`
  - `(b) PAIRED, signed`: `d_clean = median over trials of (n_err_grid_min − n_err_coh_min)`

**Bars — both must hold to PASS:**

| sub-bar | statistic | bar | fires if |
|---|---|---|---|
| 0g-1a | `median(n_err_coh_min)` | **≤ 5 bits** | `> 5` |
| 0g-1b | `d_clean` (signed) | **≥ 0 bits** | `< 0` |

HK-021(l): `d_clean` is **signed**. Never gate on `|d_clean|` — the direction is the
entire content of the check.

**Two-sided degenerate-limit guards (HK-021(n)):**

- **Floor degeneracy.** If `n_err_coh_min == 0` **and** `n_err_grid_min == 0` on every
  trial, sub-bar (b) is at the floor and cannot discriminate. **Consequence:** re-run
  limb (b) only, adding seeded noise (`snr_db`) until `median(n_err_grid_min)` lands in
  **[5, 25]**, then apply bar (b) unchanged. Report both runs.
- **Stub degeneracy.** If the coherent `out_log174` is **bit-identical** to the
  magnitude-only `log174` on ≥95% of trials, the coherent path is not distinct from the
  path it is supposed to improve on (mis-wire / stub). **ROW 0g FIRES.**

**Resolvable distance, stated while drafting (HK-021(m)):** the statistic is an integer
bit count, quantum **1 bit**. Bar (a) sits at 5; a broken correlator sits near the
binomial(174, 0.5) null, which Phase 0 measured at **mean 84, per-trial range [60, 114]**.
The bar is ~79 quanta from the null and ~5 from a perfect reading. **This limb resolves
what it is asked to resolve with very large margin.**

### 2.3 Limb 0g-2 — PAIRED ON REAL DATA (no synth dependency)

Independent corroboration on real captured audio, so 0g does not rest solely on the
synth path that already surprised us once.

- **Population.** Real **P-HIT** rows — `plive_population.build_p_hit_population`,
  sampled with `run_stage1r.deterministic_sample` (seeded, sort-stabilised; ⚠️ the
  hash-randomised-set trap is real on this project — do not construct the sample with
  raw `set` intersection), at Stage 2's own corrected **+0.65 s** anchor. All reused
  verbatim (HK-018).
- **Sample size:** `N = 200` rows, up from ROW 0c's 20. Compute is cheap (Phase 0
  measured the *full* 15,389-row population at 112 s for one call).
  🔴 **Floor:** if fewer than **100 rows** or **60 clusters** are delivered, **STOP and
  escalate** rather than running.
- **Statistic.** Per row `d_i = n_err_grid_i − n_err_coh_i` at the **same**
  `(freq_idx, time_idx)` (ROW 0e's candidate-identity requirement applies here too).
  `d_real = median(d_i)`, **cluster-bootstrapped 95% CI by `ts`**.
  🔴 **HK-021(i): P-HIT rows cluster by cycle — bootstrap by `ts` cluster, never treat
  rows as independent, and report CLUSTER counts alongside row counts.**

| statistic | bar | fires if |
|---|---|---|
| `d_real` (signed, cluster-bootstrapped) | `CI_hi(d_real) ≥ 0` | **`CI_hi(d_real) < 0`** |

⚠️ **Stated honestly: this limb is powered for a gross defect, not a subtle one.** At
N=200 rows the cluster-bootstrap half-width on a median bit-count difference is order
1–2 bits, so it will catch a correlator that is confidently worse and will *not* resolve
a sub-bit degradation. That is the correct sensitivity for a validity gate — 0g-1 is the
sharp instrument; 0g-2 exists so a synth-side artefact cannot void the gate on its own.

### 2.4 Consequence — as an assertion (HK-021)

- **ROW 0g PASSES** ⇒ the gate is evaluated exactly as pre-registered in the 2026-08-19
  spec §3. Nothing about ROW 1/2/3/4 changes.
- **ROW 0g FIRES** ⇒ **the Phase 1 gate is VOID. No ROW 1/2/3/4 may be read from the
  run. In particular, ROW 3 MUST NOT be declared and Route B2 MUST NOT be called dead.**
  QA reports the numbers, states which limb fired, and **STOPS**. The remedy is a native
  fix under HK-011, then a re-run — **not** a re-read of the same output with a
  different metric (standing prohibition).
- 🔴 **A PASS is not a certificate of correctness.** It says the correlator is not
  *grossly* defective in the ways named in §1. A ROW 3 after a 0g PASS is a verdict about
  the *method*, which is what we want it to be.

---

## 3. What this does NOT include, and why

**0g-3, selection share — SPECIFIED, NOT REQUIRED, NOT AUTHORISED.** The sharpest
diagnostic for §1(a) is: *what fraction of the 174 bits is sourced from each `n_syms`?*
If `n_syms=3` wins essentially every bit, the fusion is scale-driven rather than
evidence-driven.

🔴 **It cannot be run.** The shipped export is
`ft8_coherent_llr_at(pcm, pcm_len, freq_hz, time_offset_s, out_log174)` —
**there is no `out_diag` parameter**, despite `proposal.md` describing one, and there is
no way to restrict or introspect `n_syms` from outside. Obtaining it means a native
change ⇒ rebuilt binaries on three platforms ⇒ HK-011 Developer session ⇒ and
⚠️ **`.github/workflows/ci.yml`'s own fourth build recipe must be updated too** — the
defect that broke CI on 2026-08-21 and on r1 before it.

**Recommendation: do not build it now.** It diagnoses *why* the instrument is broken;
0g-1/0g-2 establish *whether* it is. Phase 1's entire value is being cheap. **If ROW 0g
fires, 0g-3 becomes the first thing to build** — the lead is §1(a), already written down.

---

## 4. Cost

| item | estimate |
|---|---|
| 0g-1 + 0g-2 harness | ~2 h on top of task 4.3 |
| 0g-1 compute (20 trials × 49 sweep points × 2 paths) | ~1 min |
| 0g-2 compute (200 rows × 2 calls + bootstrap) | ~1 min |
| task 4.3 gate itself (unchanged) | ~4 min compute; ~half a day of session |
| **native change required** | **none** |

---

## 5. Architect's recorded predictions (for calibration; HK-021 scoring)

Stated before any number exists:

1. **0g-1a** (`median(n_err_coh_min) ≤ 5`) — **PASS**, ~65% confident. The `n_syms=1`
   path is algebraically proven neutral and seeds the fusion, so a floor of
   roughly-magnitude-only quality should hold even if 2/3 are degraded.
2. **0g-1b** (`d_clean ≥ 0`) — **genuinely uncertain, ~50/50.** This is the sub-bar that
   §1's hazard attacks directly, and it is the reason to run the check. I am not going to
   manufacture confidence here.
3. **0g-2** — **PASS**, ~70% confident, chiefly because it is the less sensitive limb.
4. **If ROW 0g passes in full**, my prediction for the gate itself is unchanged from
   2026-08-19 and remains **low** — I expect `f_net` well under the 15% ROW 1 bar.
   ⚠️ **Read that as a prior, not as a result, and note it is the direction in which a
   defective instrument would also push. That is exactly why 0g goes first.**

⚠️ **Architect calibration to date: categorical 9/15, ranges 12/20, directional 2.5/5.5,
mechanical 3/5.** Weight the above accordingly.

---

## 6. QA's rights on this document

HK-025 applies as always: if any bar above is not mechanical, if a precondition does not
change the verdict, or if a row is not resolvable at the stated distance, **QA may refuse
to run it**, name the row and the evaluation, and stop. No Architect agreement is needed.
