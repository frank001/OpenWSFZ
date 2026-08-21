# Architect -> QA: Phase B AMENDMENT 2 -- `ft8_get_last_snr_terms` diagnostic export

**Author:** Architect
**Date:** 2026-08-21 23:11Z (`date -u`, HK-017)
**Status:** SPEC ONLY. NOT BUILT. HK-011 engaged (native + `src/`).
**Captain's ruling:** fold into Phase B (given 2026-08-21, this session).
**Relationship to prior docs:** AMENDS the 1525Z Phase B spec as amended by the 1644Z
Amendment 1. Where this document and 1525Z conflict, **1525Z wins** -- this is a pointer,
not a rewrite.

---

## 0. What this is, and what it is NOT

This adds ONE read-only diagnostic export. It makes an already-computed quantity readable.

**It is an INSTRUMENT, not an arm.** It carries no hypothesis test, no threshold on the
mechanism, and no pre-registered direction. The arm that consumes it is specced separately,
AFTER we can see the variable. Pre-registering a gate on a mechanism nobody has observed
would be HK-021 theatre.

- **It does NOT reopen H5.** H5 (`FT8_SHIM_VERSION 20260011`) is a closed gate. The standing
prohibition on re-reading a closed gate with a better metric applies in full. Any change to
suppression, to `K_SOFT_SUPP_SNR_*`, or to the SNR formula earns its OWN pre-registration and
is NOT licensed here.

---

## 1. Why -- the evidence chain, each link independently verified

1. **The SNR formula's dominant term is unobservable.** Since `fix-d004-local-noise-floor`
   (`FT8_SHIM_VERSION 20260012`, commit `595d6ea`, landed 2026-06-14 00:25) the per-signal
   SNR is `signal_db - local_noise_db - 26.5` (`ft8_shim.c:1473-1474`), where `local_noise_db`
   comes from `compute_local_noise_floor_db`. **No getter exposes it.**
   `ft8_get_last_noise_floor_db()` returns the GLOBAL histogram-median floor, which stopped
   feeding the SNR formula at that same version. Four diagnostic getters exist; the one
   quantity that would explain reported-SNR behaviour has none.

2. **There is a large, conditional, measured error.** From the 2026-08-21 R&R sweep
   (`qa/rr-study/results/2026-08-21-7d36038/`), mean reported-minus-true SNR on matched
   decodes:

   | Scenario class | WSJT-X | OpenWSFZ |
   |---|---|---|
   | S1, S1b, S2, S3 (single signal) | +0.5 .. +0.9 dB | **+1.0 .. +1.2 dB** |
   | S4, S7, S8 (multi-signal) | +0.8 .. +1.0 dB | **-11.9 .. -14.6 dB** |

   WSJT-X is stable across all seven on the SAME audio, so this is our estimator, not the
   audio or the truth labels. n: S4 96, S7 147, S8 50.

3. **Two candidate mechanisms were proposed and BOTH were refuted against data.** Neighbour
   distance does not predict the error (2550 Hz, 400 Hz clear: -16.6 dB; 1650 Hz, neighbour at
   150 Hz: +1.2 dB). Two S8 stations at IDENTICAL true SNR (-3 dB) report -20 dB (650 Hz) and
   -2 dB (1650 Hz) -- an 18 dB split with no neighbour-structure explanation. **The mechanism
   is unidentified and cannot be identified from outside the shim.**

4. **The existing closure does not cover the current build.** `DEFECT-snr-reported-gain-error.md`
   section 3 records the under-suppression mechanism as "already tested and rejected" and
   cites H5. H5 is `20260011`; the local noise floor is `20260012`. **H5 ran one version
   before the estimator that produces the effect**, against the global-median floor it
   replaced. The doc (raised 2026-07-30) measured the post-D004 estimator but inherited a
   pre-D004 closure. This is HK-022: the result answered what it was pointed at.

**What is NOT claimed:** that this costs decodes; that fixing it improves D-001; that the
2026-06-14 boundary shows a trend step. That last was checked and is **negative and
unpowered** -- 3 runs before vs 7 after, the pre-side containing the first-ever run (S1 FAIL),
the post-side confounded by D-009 (+20 pp on S7 alone) and by the S4/S7 noise-floor mixer
redesign that Section 6's own caveat names. The trend table cannot answer it either way.

---

## 2. What to build

### 2.1 The symbol

```c
/* Returns the two terms of the per-signal SNR formula for every decode
 * returned by the most recent ft8_decode_all call on THIS thread.
 *
 *   snr = signal_db - local_noise_db - 26.5f      (ft8_shim.c:1474)
 *
 * out_signal_db[i] / out_local_noise_db[i] correspond to results[i] from
 * that same call -- INDEX-ALIGNED, same order.
 *
 * Either out pointer may be NULL to request only the other array.
 * Writes at most `capacity` entries; returns the number written.
 * Returns -1 if capacity < 0.
 *
 * Threading: same contract as ft8_get_last_pass_counts -- must be called
 * from the thread that called ft8_decode_all.
 */
int ft8_get_last_snr_terms(float* out_signal_db, float* out_local_noise_db, int capacity);
```

### 2.2 Three design decisions, with reasons

**(a) A parallel array, NOT a new field on `FT8Result`.** Adding a struct field changes the
layout, which is an ABI break with managed-marshalling consequences across every existing
call site. The parallel-array getter is the pattern `ft8_get_last_candidate_counts` and
`ft8_get_last_llr_stats` already establish (the latter already carries multiple output
arrays).

**(b) Per-decode, NOT a per-cycle aggregate.** **This is an identifiability requirement,
not a preference.** The open anomaly -- 650 Hz vs 1650 Hz at identical true SNR -- is a
BETWEEN-DECODE, WITHIN-CYCLE difference. Any aggregate (min/median/max per cycle) is
mathematically incapable of resolving it. An aggregate would ship an instrument that cannot
answer the question it was built for (HK-021(c)).

**(c) BOTH terms, not just the noise floor.** `signal_db` is nominally derivable as
`snr + local_noise_db + 26.5`, but `FT8Result.snr` is **rounded to int** (`ft8_shim.c:1479`),
so that recovery is only good to +/-0.5 dB and -- fatally -- it is not INDEPENDENT: it assumes
the very formula under test. Exporting both makes AC-N2 a real identifiability check, and
separates "the signal measurement is wrong" from "the noise measurement is wrong", which is
exactly the unresolved question in section 1.3. One run answers it; one array does not.

### 2.3 Storage

Two `_Thread_local` float arrays sized `K_MAX_DECODED`, plus a count, filled in the same
block that populates `FT8Result` (`ft8_shim.c:1473-1481`). Reset per `ft8_decode_all` call,
identically to the existing TLS diagnostic state.

**Read-only. It must not alter control flow, ordering, or any decode-path value.**

---

## 3. Version

**Bump `FT8_SHIM_VERSION` 20260044 -> 20260045**, and update the managed
`ExpectedShimVersion` pin in the same change.

Reasoning, stated because the 1525Z spec pinned Phase B to a SINGLE bump and this overrides
that: a new exported symbol IS an ABI change. Keeping 20260044 would put two distinct ABIs
under one version number -- the exact collision pattern already recorded twice on this
project (20260034/20260035). The cost is one constant and one pin; Phase B's own build has
already demonstrated the mismatch guard fires correctly.

**The version number is not the identity. Re-pin the SHA256 of BOTH rebuilt binaries in
the manifest and assert against it -- never infer a build from its label.** Every SHA256
recorded during the 2026-08-21 22:09Z review is VOID once this rebuilds.

---

## 4. Build and CI changes

- **Windows -- REQUIRED.** Add `/EXPORT:ft8_get_last_snr_terms ^` to the link block in
  `native/ft8_lib_build/rebuild_shim.bat` (the explicit list at lines 139-153).
- **Linux -- NONE.** `build_linux.sh:43` uses `gcc -shared` with default visibility.
- **Name the asymmetry, do not just act on it:** a missing `/EXPORT:` line builds and links
  **clean on Linux** and fails only on Windows, at P/Invoke time, at runtime. This is a silent
  cross-platform divergence class, not a one-off. Verify the export is present in the built
  DLL mechanically (`dumpbin /exports`), do not infer it from the build succeeding.
- Managed binding: one `DllImport` in `Ft8LibInterop.cs`.

---

## 5. Acceptance -- mechanical, evaluated in this order

**AC-N1 -- INERTNESS. GATES.** Re-run the AC1/AC2 replay diff (`r0_ac1_ac2_diff.py`), 250
cycles, BOTH platforms, against the pre-Amendment-2 Phase B binary.
**Required: ZERO decode differences.** Any non-zero difference => **STOP and escalate** -- a
read-only getter changed decode behaviour, which means it is not read-only.

**AC-N2 -- IDENTIFIABILITY. GATES.** Over >= 100 cycles, for EVERY decode:
`abs((signal_db[i] - local_noise_db[i] - 26.5) - snr[i]) <= 0.5 dB`
(0.5 = the int-rounding quantum of `FT8Result.snr`; resolved against the READOUT QUANTUM,
HK-021(o)). Any violation => **STOP** -- the arrays are not the formula's terms and every
downstream reading is void.

**AC-N3 -- COUNT CONTRACT. GATES.** Returned count == the decode count from the same
`ft8_decode_all` call, every cycle. Mismatch => **STOP** (index alignment is the whole
contract; without it the arrays cannot be joined to decodes).

**AC-N4 -- CAPACITY. GATES.** With `capacity` 0, 1, and (count-1): writes exactly `capacity`
entries, returns `capacity`, no overrun. Negative capacity returns -1.

**AC-N5 -- THE MEASUREMENT. REPORTED, NOT GATED.** Run S1 (single signal) and S8 (12
signals); report per-decode `signal_db` and `local_noise_db`, and which of the two carries
the isolated-vs-crowded difference and the 650/1650 Hz split.
**No threshold, no direction, no pass/fail.** We do not yet know what we are looking for.
A gate here would be unfalsifiable decoration (HK-022's drafting question: what error could
this row NOT detect?).

---

## 6. What this does NOT license

- Does NOT reopen H5, or license ANY change to suppression or `K_SOFT_SUPP_SNR_*`.
- Does NOT change the SNR formula or authorise a fix for
  `DEFECT-snr-reported-gain-error.md`. That doc's section 4 (the correction SHAPE) remains the
  open decision. This instrument locates the error; it does not choose the fix.
- Does NOT bear on ROW 0g (still FIRED), task 4.3 (still VOID), Route B2 (NOT dead), or B3
  (HELD). Unchanged.
- Does NOT license C2 or C3.
- Its output must NOT be used to bound its own blind spot (HK-026). If the mechanism lands
  where this instrument is flat, say so and name a wider-aperture instrument.

---

## 7. Sequencing consequence -- flagged, because it moves QA's schedule

This rides the SAME rebuild as the `ftx_ldpc_decode_llrs` degenerate-variance guard fix
(`decode.c:940`, `variance == 0.0f` -> `!(variance > 0.0f)`). One rebuild, not two.

**`tasks.md` section 11 must run on the FINAL binary**, so its order is now:

1. Developer session: guard fix + this getter + `/EXPORT:` line + version bump + managed pin.
2. Rebuild both platforms; re-pin both SHA256s in the manifest.
3. AC-N1 .. AC-N4 (this doc) + the standing Phase B AC1/AC2.
4. **THEN** `tasks.md` 11.1 -> 11.2 -> 11.3 as already written, unchanged.

Running section 11 before step 3 would pin pre-registered acceptance results to a binary that
never ships -- the `39aa1031...` confound, which is already on the board once.

---

## 8. Architect predictions (calibration, recorded before the run)

| Prediction | Confidence |
|---|---|
| AC-N1 zero-diff, first attempt | 95% |
| AC-N2 passes, first attempt | 85% |
| The isolated-vs-crowded difference localises to `local_noise_db`, not `signal_db` | 75% |
| The 650/1650 Hz split localises to `local_noise_db`, not `signal_db` | 60% |
| A third mechanism proposal is needed after AC-N5 (the data does not immediately explain it) | 40% |

**Two mechanism proposals from this Architect have already been refuted against this same
dataset (section 1.3). Read the bottom two rows with that record in mind.**
