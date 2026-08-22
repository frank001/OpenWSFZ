# Architect → QA: SPEC — Phase B native fix (origin + fusion), then ROW 0g re-run AS PRE-REGISTERED

**Author:** Architect
**Date:** 2026-08-21 15:25 UTC (`date -u`, HK-017)
**Authorised by:** the Captain, 2026-08-21 — *"take the fix and re-run ROW 0g"*, then, on the
B-pos-A arithmetic below, **origin + C1 fusion in one Developer session**.
**Predecessors:** `2026-08-21-1412-…-origin-convention-finding-and-spec-b-orig-a.md` (the finding) ·
`2026-08-21-1500-qa-to-architect-b-orig-a-results.md` (ROW 1 CONFIRMED) ·
`2026-08-21-1201-…-triage-and-phase-a-deconfounding.md` §2 (C1/C2 defined) ·
`2026-08-21-1038-…-row0g-instrument-gain-check.md` (ROW 0g, the pre-registration being re-run)
**Current binary:** `main` `a420016`, shim **20260043**, DLL SHA256 `1889408787a2c7ea…`.

---

## 0. Status and chain of custody

🔴 **AMENDMENT 1 (2026-08-21 16:44Z) — POINTER, NOT A REWRITE. Everything in this spec stands unchanged.** On the Captain's ruling the Phase B Developer session ALSO builds **B4 — `ft8_ldpc_decode_llrs`, a diagnostic-only export** that decodes a caller-supplied LLR vector through production's own `ftx_normalize_logl` → `bp_decode` → OSD → CRC-14 sequence, so limb 2's numbers become CRC-verified message counts instead of B50 crossings; and QA carries the **C1 cascade pin** into `design.md`. **B4 is INERT and does NOT change §5's ordering or §6's ROW 0g pre-registration** — a B4 test failure is reported, not a stop for ROW 0g. Spec: `qa/rr-study/2026-08-21-1644-architect-to-qa-phase-b-amendment-1-ldpc-decode-llrs-export-and-cascade-pin.md`. Motivation: `qa/rr-study/2026-08-21-1634-architect-to-qa-ruling-stage1re-n5-fbreak-and-null-calibration.md` §3 (`f_net` has no null; the threshold geometry is positive on its own). ⚠️ **If the amendment appears to conflict with anything below, THIS spec wins and QA escalates.**

🔴 **This is a `native/` change. HK-011 IS engaged.** The chain, in order, no step skipped:

1. **QA** authors the OpenSpec change + `dev-tasks/*.md` from this spec (HK-015 — the dev-task is
   QA's to write, not mine) and **STOPS**. QA does not build, does not edit `native/`.
2. **A separate Developer session** runs `opsx:apply` — **build and tests only, never
   `pre_merge_check.py`** (HK-011, HK-006).
3. **The Captain** reviews the diff. Nothing is pushed or merged without his explicit sign-off
   (HK-010, HK-014).
4. **QA** then runs the acceptance sequence in §5, in the stated order, and ROW 0g in §6.

🛑 ROW 0g stands FIRED and task 4.3 stays VOID until §6 re-runs it and reports. **ROW 3 is not
declared and Route B2 is not dead** at any point in this document.
🛑 **B3 (`out_diag`) remains HELD.** This spec does not build it.
🛑 This spec does **not** amend design.md D1 — see §1.3.

---

## 1. What changes, and the justification for each

### 1.1 B1 — the waterfall-origin correction (justified by B-orig-A, ROW 1 CONFIRMED)

`ft8_coherent_llr_at` converts a waterfall block index to seconds and then uses it as a **raw-PCM
correlation origin**. Those are not the same instant: `monitor.c:74` makes the analysis window span
`freq_osr` symbol periods and `last_frame` is a look-back buffer, so cell `(b,s)`'s window centre
sits at symbol-time `b + (s+1)/T - F/2`.

B-orig-A measured this against known ground truth: `mode(G) = +2` (frac 0.867), `mode(C) = 0`
(frac 0.918), both clearing the 0.80 bar, all three preconditions clear on the first attempt.
**The grid path's own-best cell sits 2 quanta above truth; the coherent path's sits at truth.**

### 1.2 B2 — C1 fusion normalisation (justified on ARITHMETIC, not on measurement)

`coherent_llr.c:480`:

```c
if (n_syms == 1 || fabsf(candidate) > fabsf(out_log174[gb]))
    out_log174[gb] = candidate;
```

Every bit takes the largest-magnitude candidate across 1-, 2- and 3-symbol windows. **A coherent
sum's magnitude scales with window length**, so the three sizes produce LLRs on different scales and
the comparison is not a reliability comparison — it is a near-constant structural preference for the
longest window. C2 says that same window is the one frequency residual destroys first.

🔴 **Stated honestly: that C1 is THE cause of B-pos-A's residual `-6.0` is UNPROVEN.** The
selection-share measurement that would prove it is B3, which is HELD. C1 is being fixed because the
arithmetic is indefensible on its own terms, not because it has been measured. **Do not write the
dev-task or the report as though C1 were a diagnosed cause.**

### 1.3 Why neither change touches design.md D1

D1 binds the coherent path to *"the EXISTING grid position; no dependence on
`ft8_refine_candidate()`'s position estimate."* B1 is a **unit conversion** — same candidate, same
lattice cell, no search, no new degree of freedom. B2 touches only how already-formed LLRs are
compared. **Neither introduces a position estimate.** The 1201 §5 ruling remains the Captain's and
remains owed; this spec does not pre-empt it and does not need it.

---

## 2. B1 — the origin correction, exactly

In `ft8_coherent_llr_at`, after the existing lattice snap produces `time_offset_s_grid`:

```
correction (symbols) = 1/time_osr - freq_osr/2 - 0.5        == -1.0 at K_TIME_OSR = K_FREQ_OSR = 2
origin_sample_f = (time_offset_s_grid + correction * symbol_period) * fs
```

🔴 **Derive it from `mon.wf.time_osr`, `mon.wf.freq_osr` and `mon.symbol_period` — all three are
already read in that function. DO NOT hardcode `-0.16f` or `-1.0f`.** A literal silently becomes
wrong if `K_TIME_OSR`/`K_FREQ_OSR` ever change; the derived form stays correct and documents itself.
Capture the three values before `monitor_free(&mon)`.

**Comment requirement.** The correction must carry a comment naming *why* it exists — the look-back
window and the `b + (s+1)/T - F/2` centre — with a pointer to the 1412Z finding document. A bare
constant with no rationale is how this defect survived the C port in the first place (§8).

⚠️ **Prior art, and it is load-bearing:** `qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py:227`
has carried `TIME_ORIGIN_CORRECTION_SAMPLES_2K = -SPS_2K` (exactly −1 symbol) since the N2 session,
calibrated empirically and recorded as unexplained. **The Python prototype has been correct all
along; the C port dropped it.** The new C code should agree with that constant at production OSR —
if it does not, stop and escalate.

---

## 3. B2 — the fusion normalisation

**Requirement (this is what must be true, and it is the part that is binding):** before the
cross-`n_syms` magnitude comparison, each window's per-bit LLRs must be expressed on a **common,
window-size-independent scale**, so that the comparison selects the *most reliable* candidate rather
than the *longest* window.

**Recommended rule** (Architect's recommendation; a better-justified alternative is acceptable if
the dev-task records the reasoning): standardise each window by its **own** magnitude spread before
comparing — e.g. for a window with `n_tones` magnitudes in `mag[]`, divide that window's `bit_llr[]`
by `scale = stddev(mag[0..n_tones))`, guarding `scale > 0` and leaving the window's LLRs unscaled
(or excluding the window) if it is not.

Two notes that make this safe:

- **Absolute scale does not matter.** `coh_normalize_logl()` renormalises the whole 174-vector at the
  end regardless, so only the *relative* scale between windows during the comparison is load-bearing.
- **Do not fix this by restricting `n_syms`.** Forcing `n_syms = 1` would remove the multi-symbol
  coherence that is the entire premise of Route B2 — it would convert the gate into a test of
  something we are not proposing. The windows stay; only the comparison is corrected.

**Mandatory unit test (C-side or Python-side, QA's choice of placement):** construct two windows
whose magnitudes carry *equal* discriminative information but differ in absolute scale by a known
factor; assert their normalised per-bit LLRs agree to a stated tolerance, and assert the
pre-normalisation values do **not**. This tests the arithmetic directly and needs no B3.

---

## 4. Version, pin and CI mechanics — the easy things to get wrong

- **Bump `FT8_SHIM_VERSION`** (`ft8_shim.h:488`) from `20260043` to **`20260044`**, with a header
  history entry in the established style. 🔴 **Assert mechanically that `20260044` is unused across
  all branches before adopting it** — the board records two existing collisions across five unmerged
  `d001-*` branches. Do not infer freedom from the number being the next integer.
- 🔴 **Re-pin the harnesses.** `qa/rr-study/r2-coherent-llr-instrument/coherent_llr_ctypes.py:40-41`
  holds `CURRENT_DLL_SHA256` / `CURRENT_SHIM_VERSION`, and **four** harnesses import them
  (`row0g_instrument_gain_check.py`, `b_pos_a_lattice_position.py`, `b_orig_a_origin_convention.py`,
  `phase_a_deconfounding.py`). After the rebuild, **every one of them fails its pin check until this
  single file is updated.** Update it in one place, from the rebuilt DLL's actual SHA256 — read it,
  do not copy it from a report.
- **CI:** this change adds no new source file, so `.github/workflows/ci.yml`'s fourth build recipe
  should need no edit. ⚠️ **Verify that mechanically rather than assuming it** — that recipe has
  needed updating before.
- 🛑 The Developer session runs **build + tests only**. `pre_merge_check.py` is the Captain's
  initiative alone (HK-006).

---

## 5. Acceptance — in this order, and the order is the whole point

Two changes are landing together, which normally destroys attribution. **This ordering restores it:
B1 has an independent, near-deterministic acceptance test that runs before ROW 0g.**

### 5.1 FIRST — re-run B-orig-A unchanged (acceptance test for B1 alone)

Re-run `b_orig_a_origin_convention.py` exactly as it ran at 15:00Z — same seed, same N, same spec.

| statistic | before fix | **required after fix** | meaning |
|---|---:|---:|---|
| `mode(G)` | +2 | **+2, unchanged** | control — the grid path is untouched by both changes |
| `mode(C)` | 0 | **+2** | B1 works: coherent now agrees with grid's own cell |

🔴 **If `mode(C)` does not move to +2, B1 is wrong or mis-applied — STOP, do not run ROW 0g, escalate.**
🔴 **If `mode(G)` moves at all, something has touched the grid path that should not have — STOP and
escalate.** This is a genuine control, not a formality.

Report `frac_at_mode` for both. A drop in `frac_at_mode(C)` well below 0.918 is worth flagging even
if the mode is right (it would suggest B2 has added variance), but it is **not** a stop condition.

### 5.2 SECOND — the B2 unit test of §3 must pass.

### 5.3 THIRD — and only if 5.1 and 5.2 both pass — run ROW 0g per §6.

**Attribution rule, stated before the data:** if 5.1 passes and ROW 0g still fires, **B1 is
confirmed working and the residual belongs to fusion/frequency, not to position.** That is the
inference this ordering buys, and it is why 5.1 is not optional.

---

## 6. ROW 0g — re-run AS PRE-REGISTERED

🔴 **Re-run the 1038Z spec verbatim — both limbs, same population, same sample, same seed, same
anchor, same bars.** Not a variant, not a better metric, not a re-read of existing output
(standing prohibition: *never re-read a closed gate with a better metric*). The 1201 spec §4 requires
exactly this after any Phase B change.

Bars, restated so they are not re-derived from memory:

| limb | statistic | PASS bar | FIRES if |
|---|---|---|---|
| 0g-1a | `median(n_err_coh_min)` | ≤ 5 bits | > 5 |
| 0g-1b | `d_clean` (signed) | ≥ 0 bits | < 0 |
| 0g-2 | `d_real` (signed, cluster-bootstrapped by `ts`) | `CI_hi(d_real) ≥ 0` | `CI_hi(d_real) < 0` |

- **HK-021(i):** P-HIT rows cluster by cycle — bootstrap by `ts`, report CLUSTER counts alongside
  row counts, never pass `limit=` to a population helper.
- **HK-021(l):** `d_clean` and `d_real` are **signed**. Never gate on `|d|`.
- **Floor:** fewer than 100 rows or 60 clusters delivered ⇒ STOP and escalate rather than run.
- **Consequence, unchanged:** ROW 0g PASSES ⇒ the Phase 1 gate is evaluated exactly as
  pre-registered in the 2026-08-19 spec §3. ROW 0g FIRES ⇒ the gate is VOID, no ROW 1/2/3/4 may be
  read, **ROW 3 must not be declared, Route B2 must not be called dead**, QA reports which limb fired
  and **STOPS**.
- 🔴 **A PASS is not a certificate of correctness.** It says the correlator is not grossly defective
  in the ways ROW 0g names.

---

## 7. Predictions (Architect, recorded before the run)

- **5.1 `mode(C)` moves 0 → +2: ~93%.** Near-deterministic — I verified the arithmetic that calling
  0.16 s earlier and correcting after the snap are the same operation. The residual doubt is
  implementation, not theory.
- **ROW 0g-2 PASSES (`CI_hi(d_real) ≥ 0`): ~35%.** This is the real question. Without B2 it would be
  near-zero — B-pos-A's `d_global = -6.0`, CI95 `[-7,-4]`, is what an origin-only fix reproduces, and
  `CI_hi = -4 < 0` fires. Whether B2 closes a 6-bit median gap is genuinely unknown, and I am not
  confident it does.
- **ROW 0g-1 still passes both sub-bars: ~85%.** 0g-1 minimises each path independently over 49
  offsets, so a constant origin offset was always invisible to it (HK-022 / B-pos-A §2.5) — B1 should
  barely move it. B2 could, in either direction.

⚠️ My directional record is 2.5/5.5 and I got 0g-2 outright wrong at ~70% stated. Weight accordingly.

---

## 8. What I have NOT established

- **That C1 causes the `-6.0` residual.** Unproven, and only B3 would prove it. B2 is justified on
  arithmetic alone. If ROW 0g still fires after this session, that is evidence *about* the residual,
  not a refutation of B2's justification.
- **That fixing both makes Route B2 viable.** It does not follow, and the standing scale arithmetic
  cuts against it: misses sit at BER median 44.0% against BP+OSD's ~11.3% correction threshold, so
  converting a miss needs ~57 of 174 bits, while the measured difference between the two methods at
  correct position is 6. **This session makes the gate runnable. It does not make it winnable.**
- **That N5's null is overturned.** It is not. N5 ran `coherent_extract_ext`, which carries the −1
  symbol correction, so N5's `f_cross = 0.00%` was measured on a correctly-aligned extractor. The
  origin finding makes N5 *more* credible, not less. ⚠️ N5 remains thin (67 clusters) and its V3_cum
  is not the full Route B2 front end.
- **Recorded as a process hazard, not a finding:** the −1 symbol correction existed in the Python
  prototype and did not survive the C port. **Check a prototype's own empirical constants before
  porting it.**

---

## 9. Prohibitions

- 🛑 QA proposes and STOPS; a separate Developer session applies; the Captain reviews the diff
  (HK-011). No push, no merge, no `pre_merge_check.py` on QA's or the Developer's initiative.
- 🛑 ROW 0g is re-run **as pre-registered**, never re-metriced, never re-read with a better metric.
- 🛑 ROW 3 is not declared and Route B2 is not called dead by this document or by a ROW 0g FIRE.
- 🛑 B3 (`out_diag`) stays HELD — do not build it, do not pre-empt it, even though it is the thing
  that would settle C1.
- 🛑 Do not hardcode the origin correction as a literal (§2), and do not "fix" C1 by restricting
  `n_syms` (§3).
- ⚠️ Report offsets in QUANTA, seconds secondary (HK-021(o)); report CLUSTER counts, never bare row
  counts (HK-021(i)).
- ⚠️ HK-025 is available on every pre-registered check here: classify, evaluate both branches, and
  refuse the run rather than run it partially.
