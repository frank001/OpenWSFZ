# QA → Architect: Phase B wrap-up — B1 confirmed, ROW 0g still FIRES, gap closes 67→3

**2026-08-22 18:34Z.** `r2-coherent-llr-instrument`, `tasks.md` §13 (Reporting and
wrap-up — Phase B), covering §11 (Acceptance ordering, tasks 11.1–11.4) and restating
§9.4/§10.4 for the record. No `src`/`native` change made this session (HK-011 not
implicated) — this is QA re-running pre-registered acceptance checks against the
already-merged Phase B binary (shim `20260046`, `fix-negative-time-offset-snr-collapse`,
PR #130, merged to `main` `1f96be7`).

## 0. Summary

**§4.3 (the Phase 1 kill gate) stays VOID.** ROW 0g-2 still fires: `d_real = -3.000`,
CI95 `[-5.000, -2.000]`, `CI_hi < 0`. No ROW 1/2/3/4 may be read; Route B2 must not be
called dead. That is the formal, pre-registered answer, unchanged from before Phase B.

**But the number moved from −67.000 to −3.000 — a ~96% closure of the median bit-error
gap.** B1 (origin correction) is independently confirmed working via task 11.1's
control/treatment design. Per the pre-registered attribution rule (§11.4/spec §5.3),
since B1 is confirmed and ROW 0g still fires, the residual belongs to fusion/frequency,
not position — and that residual is now small, not catastrophic. This is evidence B2
(fusion normalisation) is doing real, substantial work, not proof it is sufficient.

The Architect's own recorded prediction (`design.md`, Risk section) was **~35% odds**
of ROW 0g passing after Phase B. It did not pass — the ~65% branch — but the margin by
which it missed shrank by two orders of magnitude, which the binary PASS/FAIL prediction
alone would not have surfaced.

## 1. Preconditions asserted before running

1. **Binary identity.** `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` hashed on disk:
   `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`, `FT8_SHIM_VERSION
   20260046` — confirmed via `tools/check_native_version.py` and matches
   `libft8.version.txt`'s recorded value byte-for-byte.
2. **Orthogonality of the intervening bumps.** `coherent_llr.c` (B1/B2's entire
   implementation) is byte-for-byte unchanged since the Phase B build commit `7ed8b0c`:
   `git diff 7ed8b0c HEAD -- native/ft8_lib_vendor/refine/coherent_llr.c` returns empty.
   The shim moved `20260044 → 20260045 → 20260046` since Phase B landed, but both
   intervening changes (Amendment 2/3's diagnostic `ft8_get_last_snr_terms` getter;
   `fix-negative-time-offset-snr-collapse`'s `signal_db` correction) are in `ft8_shim.c`,
   not `coherent_llr.c` — neither touches the origin/fusion code this arm exercises.
3. `qa/rr-study/r2-coherent-llr-instrument/coherent_llr_ctypes.py`'s
   `CURRENT_DLL_SHA256`/`CURRENT_SHIM_VERSION` re-pinned to the above (was still on the
   `20260045` Amendment-2/3 pin) — the four harnesses that import these constants
   (`row0g_instrument_gain_check.py`, `b_pos_a_lattice_position.py`,
   `b_orig_a_origin_convention.py`, `phase_a_deconfounding.py`) all pick up the new pin.

## 2. B1 — the waterfall-origin correction (task 7)

`native/ft8_lib_vendor/refine/coherent_llr.c`: after the existing lattice snap,
`correction_symbols = 1/time_osr − freq_osr/2 − 0.5` (derived at runtime from
`mon.wf.time_osr`/`mon.wf.freq_osr`/`mon.symbol_period`, never hardcoded — `== -1.0` at
production's own `K_TIME_OSR = K_FREQ_OSR = 2`), applied as
`origin_sample_f = (time_offset_s_grid + correction_symbols * symbol_period) * fs`.
Matches `n2-coherent-llr-extractor/coherent_extract.py`'s independently-calibrated
`TIME_ORIGIN_CORRECTION_SAMPLES_2K = -SPS_2K` (`-320` samples @ 2000 Hz = `-1` symbol)
exactly (task 7.3).

## 3. B2 — the fusion normalisation (task 8)

Before the cross-`n_syms` magnitude comparison (`coherent_llr.c:480`), each window's
per-bit LLRs are standardised to a common, window-size-independent scale
(`coh_window_scale(mag, n_tones)`, population stddev, guarded `scale > 0`) before being
compared/stored — `n_syms` unrestricted, all three window sizes (1/2/3-symbol) remain in
the fusion loop. Unit test (`test_b2_fusion_normalization.c`) constructs two windows with
equal discriminative information at a known 3.7× scale difference: pre-normalisation
LLRs disagree by exactly that factor (as required); post-normalisation LLRs agree to
float32 rounding.

## 4. B4 — `ft8_ldpc_decode_llrs` diagnostic export acceptance (task 9.4)

Restated for the record (unchanged this session, run 2026-08-21 against SHA256
`a3d32b7839a0fd73dcc8d35bd514d60f962f3267179fd77cbd8a1ebd6ecc8d45`, shim `20260044`):

| Check | Result |
|---|---|
| B4-a (positive control) | **PASS** — known message, exact codeword LLRs → `crc_ok=1`, payload matches bit-for-bit |
| B4-b (negative control) | **Reported honestly, not smoothed (HK-022)**: 1/20 on the literal spec run, not 0/20. 500-trial characterisation: BP alone never accepts noise (0/500); false accepts come exclusively from the OSD fallback at a measured ~1.2% rate — a genuine property of production's own OSD gate run against structureless noise with none of production's upstream candidate filtering, not a B4 defect. B4-a/c/d (the hard mandatory gate) all PASS regardless. |
| B4-c (buffer integrity) | **PASS** — caller's `llr174` buffer byte-identical before/after |
| B4-d (zero-variance input) | **PASS** — `rc=-2`, no crash, no NaN |
| B4-e (production agreement, HK-026 ground truth) | **92.8% (3,098/3,339 rows), CLEARS the 90% floor.** `crc_ok` (the spec-mandated primary metric) unaffected by the 317 message-text proxy mismatches, which are a known re-encode-oracle limitation (RR73-suffixed Type-1 round-trip), not a B4 defect. |

No STOP condition. B4 is inert (no production call site) — its result does not gate
ROW 0g and is restated here only because §13.1 asks for it.

## 5. Version, pin, cross-platform build (task 10, restated)

- Windows (`rebuild_shim.bat`, MSVC 19.44.35223): SHA256
  `a3d32b7839a0fd73dcc8d35bd514d60f962f3267179fd77cbd8a1ebd6ecc8d45` (Phase B build,
  shim `20260044`).
- Linux (`build_linux.sh`, WSL2 Debian, GCC 14.2.0): SHA256
  `13d9799d91388d9edd10e457cecf59a09c7a088caa09eb7c56cd40ea5ec5f894`.
- macOS: not rebuilt at Phase B time (no Mac available) — still not rebuilt as of
  today's `20260046`; this is the standing, previously-reported limitation, unchanged.
- Regression: 250 contiguous cycles, zero decode-output differences, both rebuilt
  platforms (task 10.3).
- Re-pin (task 10.4): done at Phase B time to the SHA above; this session's §11 re-run
  additionally re-pinned forward to `20260046` (§1.3 above) since the harnesses had not
  been touched since.

## 6. Task 11 — acceptance ordering, in order

### 11.1 — `b_orig_a_origin_convention.py` re-run (B1 acceptance)

| | pre-fix (2026-08-21 15:00Z, shim `20260043`) | post-Phase-B (today, shim `20260046`) |
|---|---|---|
| `mode(G)` | `+2` | `+2` (unchanged — **control intact**) |
| `frac_at_mode(G)` | 0.867 | 0.859 |
| `mode(C)` | `+0` | `+2` (**moved to agree with grid — B1 confirmed working**) |
| `frac_at_mode(C)` | 0.918 | 0.889 (a touch under 0.918 — flagged per the task's own instruction, not a stop condition) |

**PASS against this task's own stated criterion.** The script's own internal
ROW-evaluation logic printed `ROW 4 FIRES: NOT REPRODUCED... the convention explanation
is DEAD` — this is a false alarm, not a finding: that logic detects the *pre-fix*
diagnostic pattern (a nonzero `mode(G)−mode(C)` displacement). B1 closing that
displacement to zero is the success condition here, and trips the script's own
"not reproduced" branch precisely because the thing it was built to detect is now gone.
Judged against task 11.1's explicit written criterion, not the script's stale
self-narration (same discipline as HK-022 — verify what the result actually covers).

**Harness note:** this script writes to a fixed, unsuffixed path and clobbered its own
committed pre-fix baseline (`results/b_orig_a_run.log`/`.json`) on this re-run. Caught
via `git status`; original restored via `git checkout --`, today's output preserved at
`results/2026-08-22-1811-b_orig_a_*_task11_1_rerun.{log,json}`. Logged as
`openspec/qa-backlog.md` N14 (third occurrence of the same defect class already flagged
for `b_dt_c3_offline_negative_dt.py`).

### 11.2 — B2 unit test re-confirmation

Recompiled and ran `test_b2_fusion_normalization.c` fresh (MSVC 19.44.35223, `#include`s
the unchanged `coherent_llr.c` directly). Exit code 0, **ALL PASS**, arithmetic identical
to the 2026-08-21 confirmed run (ratio `3.7000` exactly pre-normalisation, `|diff| =
0.000000` post-normalisation on all 3 bits). Throwaway build artefacts removed after,
per the test file's own header instruction.

### 11.3 — ROW 0g re-run, exactly as pre-registered

Same seed (`20260821`), same population (25,411-row/4,371-cluster), same `+0.65s`
anchor, same bars, both limbs — not a variant, not a re-read of existing output with a
different metric. Floor clear: 193/200 rows measured, 190 clusters delivered (well
above the 100-row/60-cluster floor, HK-021(i)).

| | pre-Phase-B | post-Phase-B (today) |
|---|---|---|
| ROW 0g-1 (clean-signal ceiling) | PASS | **PASS** |
| ROW 0g-2 `d_real` (median, signed — HK-021(l)) | −67.000 | **−3.000** |
| ROW 0g-2 CI95 (cluster bootstrap, n_draws=2000) | [−71.000, −65.000] | **[−5.000, −2.000]** |
| ROW 0g-2 verdict | FIRES (`CI_hi < 0`) | **FIRES** (`CI_hi = −2.000 < 0`) |

**Consequence per the pre-registered rule: §4.3 stays VOID. No ROW 1/2/3/4 may be read.
Route B2 must not be called dead.** Stopping here per this task's own instruction — no
further ROW evaluation attempted, no re-read with a different metric.

**The magnitude is the finding that matters:** the median bit-error gap between grid
and coherent closed by **~96%** (67 → 3 bits) without closing entirely. A PASS was never
guaranteed — the Architect's own prediction gave it ~35% odds — but "3 bit-errors short"
and "67 bit-errors short" are very different states to hand back for a viability
judgement, even though both are formally the same VOID outcome.

**Harness note (same defect, second instance today):** `row0g_instrument_gain_check.py`
also clobbered its own committed baseline (`results/row0g_run.log`/`.json`). Same
recovery: today's output preserved at
`results/2026-08-22-1811-row0g_*_task11_3_rerun.{log,json}`, original restored.

### 11.4 — Attribution statement (spec §5.3)

11.1 passed (B1 confirmed working) and ROW 0g still fires at 11.3 — exactly the case
spec §5.3 names. **The residual belongs to fusion/frequency, not to position.** B1's
origin correction is not in question; whatever remains between grid and coherent lives
in B2's fusion arithmetic or in the frequency axis, not in where the extractor looks in
time. The residual's dramatic shrinkage (67 → 3 median bit-errors) is new evidence B2 is
doing large, real work — not evidence B2 (or the coherent path generally) is complete.

## 7. What this does NOT license

Per HK-011/HK-010/HK-006 and this project's standing discipline: does **not** authorise
any further `src`/`native` change; does **not** re-open §4.3 or license reading ROW
1/2/3/4; does **not** call Route B2 dead (explicitly prohibited by the FIRES branch);
does **not** amend `design.md` D1 (unaffected, unrelated); does **not** authorise C2 or
C3; does **not** constitute a merge decision — B1/B2/B4's code is already merged (PR
#130 carried it forward from the earlier Phase B session), this report only closes the
acceptance-verification loop that was left open around it.

## 8. Task 13.3 — Stop

**No push, no merge, no `pre_merge_check.py`** (HK-014/HK-010/HK-006). This task does
not declare readiness unprompted, and there is nothing pending to be "ready" for — the
code is already on `main`. What this report closes out is `r2-coherent-llr-instrument`'s
own outstanding acceptance-verification debt (§11) and its wrap-up report (§13.1/13.2),
so the change can be assessed for archiving on its actual merits rather than left with
an open "was this ever checked" question.

**The Captain reviews this and decides:**
- Whether ROW 0g still-FIRES-but-96%-closed is enough to authorise a further Phase
  (frequency-axis or fusion-arithmetic follow-up on B2), park it, or close the
  investigation here.
- Whether to archive `r2-coherent-llr-instrument` now (its own tasks.md is complete as
  of this report) or hold it for a decision on the above first.
- The N14 harness-gap backlog item, and whether it's worth a quick structural fix before
  the pattern claims a fourth script.

QA stops here.

## 9. Artefacts

- `qa/rr-study/r2-coherent-llr-instrument/results/2026-08-22-1811-b_orig_a_run_task11_1_rerun.log`
  / `..._report_task11_1_rerun.json`
- `qa/rr-study/r2-coherent-llr-instrument/results/2026-08-22-1811-row0g_run_task11_3_rerun.log`
  / `..._report_task11_3_rerun.json`
- `qa/rr-study/r2-coherent-llr-instrument/coherent_llr_ctypes.py` (re-pin to `20260046`)
- `openspec/changes/r2-coherent-llr-instrument/tasks.md` (§11.1–11.4 marked done, full
  results recorded in place)
- `openspec/qa-backlog.md` N14
