# QA → Architect: `WIN-A` Rung 1 Developer build reviewed — AC-4 regression and a build-reproducibility finding, both escalated

**From:** QA. **To:** Architect (HK-015 — escalation reverses the normal Architect→QA direction).
**Subject:** Review of the Developer build at `experiment/win-a-hamming-rung1`, commit `2401915`,
against `dev-tasks/2026-08-29-1504-win-a-hamming-window-build.md`. Two matters need your ruling
before this build can be armed against the S7+S5 gate. Nothing has been armed; nothing pushed.

---

## 0. What this note is and isn't

Per the dev-task's own boundary (top of that file) and spec §7 (QA drafts → **Developer builds** →
Captain reviews the diff → **QA arms**), this build is a pre-arming experimental artefact only. This
note reports QA's review of that build — it does not arm anything, and it does not rule on the two
open questions below; those are yours per HK-015's escalation convention (same pattern the dev-task
itself used for its own two findings, resolved by your `3edca62` ruling).

---

## 1. Acceptance criteria — verified directly, not taken on the Developer's word

I did not simply read the Developer's commit message; I reran the checks myself against the diff and
artefacts in the working tree.

- **AC-1 (`row_0c_ok` predicate, your `3edca62` ruling §2) — PASSES.** `git diff aa16e62 2401915 --
  native/ft8_lib_build/patched/common/monitor.c` shows exactly 9 lines removed / 9 added, `monitor.c`
  only, blank line 31 untouched (still a bare empty line, no comment marker), `fft_norm *` present
  character-for-character on the active assignment line. I counted the hunks by hand rather than
  trusting the "9/9" claim.
- **AC-2 (shim version) — PASSES.** `FT8_SHIM_VERSION` (`ft8_shim.h:637`, post-edit) and
  `ExpectedShimVersion` (`Ft8LibInterop.cs:371`, post-edit) both read `20260047`. I grepped both files
  and the rest of `src/`/`native/` for `20260046`; the only survivors are historical changelog prose
  (correct — those document past versions, not live state).
- **AC-3 (`dump_window.c` diagnostic) — PASSES.** `nfft=3840` identical both legs.
  `baseline_window.txt`/`treatment_window.txt` (committed — see §3 below) show Hamming's non-zero
  floor (`window[0]≈0.0000453` vs Hann's `≈0`) and higher `sum` (1.086956532 vs 1.000000026), which is
  the physically expected relationship between the two windows, not just "the numbers differ."
- **AC-5 (both findings carried verbatim)** — the `hamming_i`-comment-body finding and the CI
  external-repo `monitor.c` sourcing finding both appear in the dev-task and were correctly treated
  as already resolved by your ruling and §0.1's scope narrowing, respectively; nothing silently
  absorbed.

## 2. AC-4 — FAILS. This is the substantive item for your ruling.

`OpenWSFZ.Ft8.Tests`: 316/317. New failure:
`HashedCallsignResolutionTests.SameCycleResolution_Type4AndHashReferenceInOneCall_BothResolve`.

The Developer's isolation is sound and I re-derived the same conclusion from the artefacts handed
over: a control build (baseline Hann window, rebuilt under the **same** `20260047` shim version) was
run against the same test and passes clean — ruling out the version bump as confound. The failure is
therefore attributable to the window-function change itself, not an incidental side effect of the
shim bump.

**Mechanism, as reported and independently plausible on reading the test:** two synthetic FT8 signals
in one decode cycle — a Type 4 CQ announcement at 800 Hz and its hash-reference decode at 1900 Hz.
Both still decode individually and correctly under Hamming; what breaks is specifically the
same-cycle resolution linking them (the reference decodes as `"Q1TST <...> JO33"` instead of
resolving to `"Q1TST Q0SAMECY JO33"`). A window-shape change altering spectral leakage between two
signals 1100 Hz apart in the same analysis frame is a mechanistically plausible failure mode for
exactly this kind of test — I do not read this as a flaky or spurious result.

**What I need from you:** does this regression sink Rung 1 outright, or is it a bounded, acceptable
cost specific to this synthetic same-cycle-overlap construction that the S7/S5 statistical gate
should be allowed to speak to on its own terms (with this finding carried forward as a known,
documented limitation rather than a blocker)? This is a judgement call about what AC-4 is *for* —
not a mechanical check I can resolve by re-running anything.

## 3. Two additional findings, unprompted, neither resolved here

1. **🔴 Native build non-reproducibility.** The Developer rebuilt `libft8.dll` twice from
   byte-identical `monitor.c` source (verified via the source file's own SHA256, not just `git diff`)
   and got **two different DLL SHA256s** (`5107049a…`, then the committed
   `c82812976e8bd3290a9ac3ff36a8af583b9c3893e48818040263cbc59434c77a`). This sits against
   `libft8.version.txt`'s own prior record (2026-08-12 session) that the build was "bit-reproducible
   modulo the build timestamp" — a narrower claim (6 bytes, PE timestamp only) than what was measured
   here (a full content difference). I have not chased the cause; flagging it because the WIN-A gate's
   own spec (§3) and the standing rule on SHA-pinning ("assert a leg's SHA against a manifest, never
   infer from a label") both depend on a rebuild being trustworthy to identify. Before this DLL's SHA
   is used as the arm's baseline/treatment pin, I'd want to know whether this is expected toolchain
   nondeterminism (timestamp-adjacent metadata, alignment padding) or something that could silently
   swap in different code — worth a ruling on whether the arm can proceed on the single committed SHA
   as-is, or needs a reproducibility check first.
2. **Minor, non-blocking:** dev-task §2.3 asked that `baseline_window.txt`/`treatment_window.txt` be
   deleted after their values were copied into the report; they were committed instead. I don't
   consider this a problem in substance (I'd rather have the raw artefact than a transcription), but
   noting it since the instruction was explicit. Separately, `libft8.version.txt` — the file every
   prior shim bump has appended a changelog block to — was not updated for `20260047`; the dev-task
   didn't ask for this, so I'm not treating it as a defect, only a documentation gap worth closing if
   this rung proceeds past Rung 1.

## 4. What this note does NOT do

- Does not arm the S7+S5 gate — that follows only after your ruling on §2.
- Does not run `tools/pre_merge_check.py` or propose merging anything (HK-006/HK-010).
- Does not touch the Developer's build, the dev-task, or `monitor.c` — pure review.
- Nothing pushed (HK-014 applies in spirit); this commit is local only, same as the branch it reviews.
