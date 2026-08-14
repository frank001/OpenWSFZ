## 1. D3 — stratify the existing noise population (no new run — do this first)

- [ ] 1.1 Write `qa/rr-study/r1-sync-refiner/stratify_noise.py`: reads a results file's
      `noise_results`, computes the correlation between `coarse_time_offset_s` (raw, and its
      fractional position within its own 5 ms coarse cell) and `Δt`, the correlation between
      `coarse_freq_hz` and `Δt`, and a decile table of mean `Δt` by cell-position decile.
- [ ] 1.2 Run it against the already-committed `run_a.json` and confirm the numbers reproduce this
      proposal's Impact section (mean `Δt` negative in every decile, negligible correlation to
      either field). If they do not reproduce, STOP and re-derive design.md's D3 reasoning before
      continuing — the rest of this plan's sequencing assumes that finding holds.
- [ ] 1.3 Record the reproduced numbers (not re-asserted from this proposal) in the eventual QA
      report.

## 2. D1 — export the (coarse, fine) time decomposition (native + managed)

- [ ] 2.1 Add `out_coarse_dt_samp` (`int*`) and `out_fine_dt_samp` (`int*`) to
      `ft8_refine_candidate`'s signature in `ft8_shim.h` and `native/ft8_lib_vendor/refine/
      sync_refiner.c`. Populate them from the existing `best_dt_samp` / `best_fine_samp` locals —
      no change to the search/correlation logic itself (design.md Context).
- [ ] 2.2 Confirm via `dumpbin /exports` (or platform equivalent) that the exported symbol's
      signature reflects the two new parameters and no other exported symbol changed.
- [ ] 2.3 Add the two new parameters to `Ft8LibInterop.RefineCandidate`'s P/Invoke declaration and
      `IFt8NativeInterop.RefineCandidate`'s signature; update all 8 existing `IFt8NativeInterop`
      test-double implementations (same count R1's task 2.1 established) with the extended stub.
- [ ] 2.4 Extend `RefineCandidateTests.cs` (or add new tests) to assert the decomposition-sums-to-
      total scenario from the `ft8-sync-refiner` spec delta, and that the two new out-parameters are
      populated on a real-binary smoke test.
- [ ] 2.5 Extend `qa/rr-study/r1-sync-refiner/refiner_ctypes.py` and `run_harness.py` to read and
      record the two new fields into the results schema (additive fields, existing fields
      unchanged — confirm AC-1/AC-2/AC-5/AC-6 evaluator code does not need to change).

## 3. D2 — reflection-symmetry evaluator (combined + per-stage)

- [ ] 3.1 Implement `reflection_symmetry_test()` in `qa/rr-study/r1-sync-refiner/evaluate_acs.py`
      exactly as drafted in design.md D2 (two-sample KS test of a sample against its own negation;
      `instrument_failure` result on zero variance).
- [ ] 3.2 Replace the existing `evaluate_ac3` time-dimension logic with three calls to this
      function — combined `Δt`, `best_dt_samp` (coarse-only), `best_fine_samp` (fine-only) — each
      at `α = 0.01/3`. Leave AC-3's frequency-dimension χ² logic untouched (still gates at
      `α = 0.01`, unaffected by this change per the spec delta).
- [ ] 3.3 Confirm the new evaluator's per-sub-test statistics are written to the report JSON
      individually, not just an aggregate pass/fail.

## 4. D4 — pooled SNR trend evaluator (time dimension only)

- [ ] 4.1 Implement `snr_trend_test()` in `evaluate_acs.py` exactly as drafted in design.md D4
      (one-sided Spearman correlation between SNR and per-trial absolute time error, pooled across
      all in-power strata; underpowered-stratum exclusion reported by name).
- [ ] 4.2 Replace `evaluate_ac4`'s time-dimension logic with this function. Retain the existing
      per-stratum RMS(Δf) table as informational output only — confirm it no longer contributes to
      any pass/fail field in the report.
- [ ] 4.3 Delete (not merely stop calling) the old any-adjacent-pair-increases-fails logic for both
      dimensions — it is retired per the ruling, not superseded silently while the code still exists
      to be accidentally reused.

## 5. D5 — carry the frequency-floor finding forward (no code)

- [ ] 5.1 Confirm design.md's D5 section states the finding in terms usable directly by whoever
      proposes R2 (no code change; verify this task is satisfied by design.md as written, not by
      any new artefact).

## 6. Re-run, shim version, and cross-platform build

- [ ] 6.1 Bump `FT8_SHIM_VERSION` (`ft8_shim.h`) and `ExpectedShimVersion` (`Ft8LibInterop.cs`) to
      `20260041`.
- [ ] 6.2 Rebuild Windows x64 and Linux x64 binaries (same toolchain access R1 used); record each
      new SHA256. Record macOS ARM64 as remaining stale (three consecutive shim versions now,
      proposal.md Impact) unless a Mac/toolchain has become available.
- [ ] 6.3 Re-run the full validation harness three independent times against the SAME population R1
      used (do not regenerate the population — determinism and comparability both depend on this),
      now capturing the two new D1 fields. Byte-diff pairwise (AC-5, unaffected requirement, must
      still hold with the extended results schema).
- [ ] 6.4 Run `evaluate_acs.py` (now including D2's three sub-tests and D4's pooled test) against
      the new run. Record every AC's result — including AC-1/AC-2/AC-5/AC-6, which should reproduce
      R1's numbers unchanged since the underlying algorithm is untouched; a difference in any of
      those four would itself be a finding requiring investigation before proceeding.
- [ ] 6.5 Re-run R1's production-decode-equality replay (≥200 contiguous cycles, pinned 20m corpus,
      pre-change `20260040` vs. new `20260041`) to confirm zero decode-output differences.
- [ ] 6.6 `dotnet build`: 0 warnings. `dotnet test`: full suite green, including the extended
      `RefineCandidateTests`.

## 7. Reporting and wrap-up

- [ ] 7.1 Write the QA→Architect report: D3's reproduced stratification numbers; D1's export
      confirmed against the sum-consistency scenario; D2's three sub-test results with the
      Bonferroni-corrected verdict and, if any sub-test fails, which stage(s) it implicates; D4's
      pooled trend result; whether the non-gating H-A/H-B/H-C discriminators were run and what they
      showed (still non-gating regardless of outcome, per design.md Non-Goals); AC-1/AC-2/AC-5/AC-6
      reproduction; new DLL SHA256s and shim `20260041`.
- [ ] 7.2 State plainly whether R2 is now unblocked (all of AC-1/AC-2/AC-5/AC-6 reproduce AND D2's
      combined+per-stage symmetry tests all PASS AND D4's pooled trend test PASSes) or remains
      blocked, and on what specifically.
- [ ] 7.3 Stop. No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006) — the Captain
      reviews the diff and decides on merge; this task does not declare readiness unprompted.
