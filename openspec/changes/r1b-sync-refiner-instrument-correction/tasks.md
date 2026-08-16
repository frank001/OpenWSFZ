## 1. D3 — stratify the existing noise population (no new run — do this first)

- [x] 1.1 Write `qa/rr-study/r1-sync-refiner/stratify_noise.py`: reads a results file's
      `noise_results`, computes the correlation between `coarse_time_offset_s` (raw, and its
      fractional position within its own 5 ms coarse cell) and `Δt`, the correlation between
      `coarse_freq_hz` and `Δt`, and a decile table of mean `Δt` by cell-position decile.
- [x] 1.2 Run it against the already-committed `run_a.json` and confirm the numbers reproduce this
      proposal's Impact section (mean `Δt` negative in every decile, negligible correlation to
      either field). If they do not reproduce, STOP and re-derive design.md's D3 reasoning before
      continuing — the rest of this plan's sequencing assumes that finding holds.
      **Reproduced exactly** on the first pass EXCEPT the decile table required a fix: fixed-width
      `[0,1)` bins on cell-position put unequal counts per bin and flipped decile 0's sign
      (+0.39 ms) relative to proposal.md's claimed range; switching to quantile-based (equal-count)
      deciles reproduces −1.96 ms .. −14.06 ms exactly. All other numbers (mean −5.416 ms, median
      −5.000 ms, sign test 637 neg/555 pos p=0.0189, KS p=4.94e-7, r=−0.0672/−0.0333/−0.0070)
      matched on the first run. See
      `qa/rr-study/r1-sync-refiner/results/2026-08-14/stratify_report_run_a.json`.
- [x] 1.3 Record the reproduced numbers (not re-asserted from this proposal) in the eventual QA
      report.

## 2. D1 — export the (coarse, fine) time decomposition (native + managed)

- [x] 2.1 Add `out_coarse_dt_samp` (`int*`) and `out_fine_dt_samp` (`int*`) to
      `ft8_refine_candidate`'s signature in `ft8_shim.h` and `native/ft8_lib_vendor/refine/
      sync_refiner.c`. Populate them from the existing `best_dt_samp` / `best_fine_samp` locals —
      no change to the search/correlation logic itself (design.md Context).
- [x] 2.2 Confirm via `dumpbin /exports` (or platform equivalent) that the exported symbol's
      signature reflects the two new parameters and no other exported symbol changed.
      (verified after rebuild in section 6 — see task 6.2's note)
- [x] 2.3 Add the two new parameters to `Ft8LibInterop.RefineCandidate`'s P/Invoke declaration and
      `IFt8NativeInterop.RefineCandidate`'s signature; update all 8 existing `IFt8NativeInterop`
      test-double implementations (same count R1's task 2.1 established) with the extended stub.
      Confirmed 8: WorkedBeforeLookupTests, D011NonstandardCallsignFpGuardTests, D009FpFilterTests,
      D005MessageTrimTests, RegionLookupTests, SetDecodeParamsTests, HashTableRejectCountLoggingTests,
      AvContainmentTests — plus `Ft8NativeInteropAdapter` (production) and `RefineCandidateTests`'
      own `CapturingInterop` (R1-added, the 9th/10th implementers) updated alongside.
- [x] 2.4 Extend `RefineCandidateTests.cs` (or add new tests) to assert the decomposition-sums-to-
      total scenario from the `ft8-sync-refiner` spec delta, and that the two new out-parameters are
      populated on a real-binary smoke test.
- [x] 2.5 Extend `qa/rr-study/r1-sync-refiner/refiner_ctypes.py` and `run_harness.py` to read and
      record the two new fields into the results schema (additive fields, existing fields
      unchanged — confirm AC-1/AC-2/AC-5/AC-6 evaluator code does not need to change).
      Confirmed: evaluate_acs.py's AC-1/AC-2/AC-4 read only measured_delta_freq_hz /
      measured_delta_time_s / sync_score; AC-5 byte-diffs the whole file so the new fields are
      covered automatically — no evaluator code change required for those four.

## 3. D2 — reflection-symmetry evaluator (combined + per-stage)

- [x] 3.1 Implement `reflection_symmetry_test()` in `qa/rr-study/r1-sync-refiner/evaluate_acs.py`
      exactly as drafted in design.md D2 (two-sample KS test of a sample against its own negation;
      `instrument_failure` result on zero variance).
- [x] 3.2 Replace the existing `evaluate_ac3` time-dimension logic with three calls to this
      function — combined `Δt`, `best_dt_samp` (coarse-only), `best_fine_samp` (fine-only) — each
      at `α = 0.01/3`. Leave AC-3's frequency-dimension χ² logic untouched (still gates at
      `α = 0.01`, unaffected by this change per the spec delta).
- [x] 3.3 Confirm the new evaluator's per-sub-test statistics are written to the report JSON
      individually, not just an aggregate pass/fail. (`time_subtests` dict, one entry per
      sub-test, each with its own `ks_statistic`/`p_value`/`pass`)

## 4. D4 — pooled SNR trend evaluator (time dimension only)

- [x] 4.1 Implement `snr_trend_test()` in `evaluate_acs.py` exactly as drafted in design.md D4
      (one-sided Spearman correlation between SNR and per-trial absolute time error, pooled across
      all in-power strata; underpowered-stratum exclusion reported by name).
- [x] 4.2 Replace `evaluate_ac4`'s time-dimension logic with this function. Retain the existing
      per-stratum RMS(Δf) table as informational output only — confirm it no longer contributes to
      any pass/fail field in the report. (`per_stratum_note` states this explicitly in the report)
- [x] 4.3 Delete (not merely stop calling) the old any-adjacent-pair-increases-fails logic for both
      dimensions — it is retired per the ruling, not superseded silently while the code still exists
      to be accidentally reused. (old `broken_pairs` loop removed entirely, verified by grep —
      zero remaining references)

## 5. D5 — carry the frequency-floor finding forward (no code)

- [x] 5.1 Confirm design.md's D5 section states the finding in terms usable directly by whoever
      proposes R2 (no code change; verify this task is satisfied by design.md as written, not by
      any new artefact).

## 6. Re-run, shim version, and cross-platform build

- [x] 6.1 Bump `FT8_SHIM_VERSION` (`ft8_shim.h`) and `ExpectedShimVersion` (`Ft8LibInterop.cs`) to
      `20260041`.
- [x] 6.2 Rebuild Windows x64 and Linux x64 binaries (same toolchain access R1 used); record each
      new SHA256. Record macOS ARM64 as remaining stale (three consecutive shim versions now,
      proposal.md Impact) unless a Mac/toolchain has become available.
      Windows SHA256 `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf`; Linux
      SHA256 `6f0c541964b17f71b820937c887a63df10db6adb4831ec08ee137b767ad91edd`; macOS confirmed
      stale (third consecutive version, no Mac available). `dumpbin /exports` and `nm -D` both
      confirm all 12 symbols present, unchanged set. Found and fixed en route: `build_linux.sh`
      had CRLF line endings that silently broke it under WSL2 (fixed to LF; see
      `libft8.version.txt`'s new entry). Details recorded in
      `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`.
- [x] 6.3 Re-run the full validation harness three independent times against the SAME population R1
      used (do not regenerate the population — determinism and comparability both depend on this),
      now capturing the two new D1 fields. Byte-diff pairwise (AC-5, unaffected requirement, must
      still hold with the extended results schema).
      Same seed (20260815, `population.py`'s `P.SEED` default, unchanged) as R1 — same 2,400
      signal + 1,200 noise trials. Three independent `run_harness.py` invocations against shim
      20260041 →
      `qa/rr-study/r1-sync-refiner/results/2026-08-14/{run_a,run_b,run_c}_20260041.json`. AC-5
      confirms all three byte-identical (see 6.4).
- [x] 6.4 Run `evaluate_acs.py` (now including D2's three sub-tests and D4's pooled test) against
      the new run. Record every AC's result — including AC-1/AC-2/AC-5/AC-6, which should reproduce
      R1's numbers unchanged since the underlying algorithm is untouched; a difference in any of
      those four would itself be a finding requiring investigation before proceeding.
      **AC-1 PASS** (RMS(df)=0.1430 Hz, RMS(dt)=1.135 ms — byte-for-byte identical to R1's own
      numbers, confirming the underlying algorithm is genuinely untouched). **AC-2 PASS**
      (mean(df)=-0.0019 Hz, mean(dt)=0.429 ms — also identical to R1). **AC-3 FAIL** — but now
      LOCALISED by D2's per-stage sub-tests: combined FAIL (p=4.9e-7, matches R1's original
      finding and this session's `stratify_noise.py` cross-check exactly), **coarse_stage PASS**
      (p=0.454, ks=0.035 — Stage A+B's own selection is clean/symmetric), **fine_stage FAIL**
      (p≈0, ks=0.973 — Stage C alone carries nearly all the asymmetry: 1183/1200 noise trials
      (98.6%) select a NEGATIVE `fine_dt_samp`, piled at the search range's own extreme -20
      (115 trials, the single largest bin) and decaying smoothly toward 0). **AC-4 PASS**
      (rho=-0.0754, p=0.00011 < 0.01, n=2,400 pooled, zero underpowered strata — the new pooled
      trend test is no longer marginal/void-by-construction; a genuine SNR-time trend is
      confirmed). **AC-5 PASS** (three runs byte-identical). **AC-6** measured (20.33 ms/candidate,
      not gated). Full report:
      `qa/rr-study/r1-sync-refiner/results/2026-08-14/ac_evaluation_report_20260041.json`.
- [x] 6.5 Re-run R1's production-decode-equality replay (≥200 contiguous cycles, pinned 20m corpus,
      pre-change `20260040` vs. new `20260041`) to confirm zero decode-output differences.
      Used the identical tooling and range R1/R0 established
      (`qa/cycleframer-alignment-replay/r0_ac1_ac2_replay.py` + `r0_ac1_ac2_diff.py`), 250
      contiguous cycles, `artefacts/20260808_live_run_0016-8080/wsjt-x/wav`,
      `260808_004000`..`260808_014215`. Pre-change binary extracted from git commit `af2f466`
      (SHA256 `fe0b7d534e…` confirmed to match R1's own shipped pin exactly) vs. the freshly
      built `20260041`. **`RESULT: PASS — zero differences across 250 cycles`.** Confirms D1's
      instrumentation did not alter `ft8_decode_all`'s production output by a single byte.
- [x] 6.6 `dotnet build`: 0 warnings. `dotnet test`: full suite green, including the extended
      `RefineCandidateTests`. `dotnet build` on `OpenWSFZ.Ft8.csproj` and
      `OpenWSFZ.Ft8.Tests.csproj`: 0 Warning(s), 0 Error(s). `dotnet test`: 310/310 passed
      (including the `RequiresNativeBinary`-tagged real-binary smoke tests against the new
      20260041 DLL — `CoarseDtSamp`/`FineDtSamp` populated and sum-consistent).

## 7. Reporting and wrap-up

- [x] 7.1 Write the QA→Architect report: D3's reproduced stratification numbers; D1's export
      confirmed against the sum-consistency scenario; D2's three sub-test results with the
      Bonferroni-corrected verdict and, if any sub-test fails, which stage(s) it implicates; D4's
      pooled trend result; whether the non-gating H-A/H-B/H-C discriminators were run and what they
      showed (still non-gating regardless of outcome, per design.md Non-Goals); AC-1/AC-2/AC-5/AC-6
      reproduction; new DLL SHA256s and shim `20260041`.
      Written to `qa/rr-study/2026-08-14-2117-qa-r1b-sync-refiner-instrument-correction-report.md`.
- [x] 7.2 State plainly whether R2 is now unblocked (all of AC-1/AC-2/AC-5/AC-6 reproduce AND D2's
      combined+per-stage symmetry tests all PASS AND D4's pooled trend test PASSes) or remains
      blocked, and on what specifically.
      **R2 remains BLOCKED** — AC-1/AC-2/AC-5/AC-6 reproduce and AC-4 now PASSes, but D2's
      fine-stage sub-test FAILs outright (KS=0.973, p≈0). Report §8 states this plainly and
      also states the forward progress: the defect is now precisely localised to Stage C alone
      (Stage A+B's own selection is clean, p=0.454), not diffuse across both stages as R1 left it.
- [x] 7.3 Stop. No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006) — the Captain
      reviews the diff and decides on merge; this task does not declare readiness unprompted.
      Stopping here. No push, no merge, no `pre_merge_check.py` run.
