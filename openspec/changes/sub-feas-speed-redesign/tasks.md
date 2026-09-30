## 1. Pre-implementation decisions (record in `design.md` before writing code)

- [x] 1.1 M1 consumer precondition (QA, 2026-09-30): four QA scripts parse the LDPC-fail Debug line; the Captain
      chose **defer M1**. Recorded in `design.md` D7. **Do not implement M1.**
- [ ] 1.2 Base: branch `feat/sub-feas-speed-redesign` off `feat/sub-feas-native-subtraction` (`ab95bea1`, code
      `2b39cf18`). Confirm `libft8.dll` SHA-256 of the base is `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5`
      before changing anything, and keep that DLL: E1 needs it.
- [x] 1.3 Workspace ownership is **decided** (Architect, Amendment 1; `design.md` D2): a bounded, locked pool of heap
      workspaces, size = effective `subtractionMaxThreads`, leased per fit and returned in a `finally`, no native
      thread-local state, freed at decoder dispose. The Developer records only the pool API shape and how a changed
      thread count resizes it (at the next cycle boundary, nothing in flight).
- [ ] 1.4 Record the exact ABI shape of the cancel flag (D3) and of the M2 diagnostics switch.
- [ ] 1.5 Pick the next `FT8_SHIM_VERSION` literal after checking `main` (`20260051`), `decoding_improvement`
      (`20260054`), the base branch (`20260055`) and any live branch's pin. Do not assume.
- [ ] 1.6 Confirm how the new config key survives the in-flight config-save work (#193): the config POST is a
      full replace (HK-035). Coordinate with whichever session owns that workstream.

## 2. Measure first: make the cost map checkable (test-only, no product-path change)

- [ ] 2.1 In a test-only console tool under `tests/` (`Ft8.FitProbe` or similar; **not** in the product path),
      time one `ft8_subfeas_compute_analytic` call and, for a fixed set of signals, each fit phase (Δt search, ḟ
      search, final template, Δt refine, envelope) and one residual `DecodeAll`, on the base DLL. Write **integers
      and stamps only**; never message text (HK-037/NFR-021).
- [ ] 2.2 Report the per-phase milliseconds and the **longest single uninterruptible stretch a cancel flag would
      have to wait through** (feeds `design.md` D3 and D5).

## 3. E1 hash probe (before any optimisation)

- [ ] 3.1 Build the E1 probe in `tests/` (test-only): given a `libft8.dll` path and a list of cycle WAV files, it
      decodes pass-0 **through that DLL**, encodes each re-encodable decode, fits with **no deadline**, and writes
      one CSV row per (stamp, signal index): `rc`, `sha256(out_shat)`, plus the pass-0 decode **count** and the
      flag-OFF decode outcome fields (never text). Assert 180 000 samples per file in code.
- [ ] 3.2 Run it once on the base DLL over a small synthetic/fixture set and commit the resulting hashes as data
      (hashes and integers only). This is the golden the optimisations are checked against during development.
      QA runs the real-corpus E1 at acceptance (§10).

## 4. Native: exact optimisations (A1, A2, A3)

- [ ] 4.1 **A1.** In `subfeas_fit.c` compute the smoothed tone track **once per signal**; `r_fit_drift` applies only
      the ḟ-dependent drift term and the cos/sin. Hold the smoothed track at the precision the old code held it
      (`design.md` D1). Re-run the golden hashes.
- [ ] 4.2 **A2.** FFT the Gaussian pulse and the Hann window once per workspace and reuse their spectra in
      `fft_convolve_same`. Re-run the golden hashes.
- [ ] 4.3 **A3.** Implement the bounded, locked workspace pool (§1.3): each workspace holds both
      `kiss_fft_alloc(262144)` plans, the cached spectra and `gaussian_pulse`, built once and reused; leased per fit,
      returned in a `finally` (a cancelled or failed fit still returns its lease). Heap only, no stack array above
      100 KB anywhere reachable from P/Invoke (base change task 3.3 self-review applies). **No native thread-local
      state.** Bounded by the thread count; freed at decoder dispose, which cannot free a leased workspace;
      allocation failure falls back to pass-0-only as today.
- [ ] 4.4 Build flags are **unchanged**. No `/fp:fast`, no `/arch:AVX2`, no vectorised sin/cos. If a change here
      is tempting, it is Stage B (§11), not this change.
- [ ] 4.5 After each of 4.1–4.3, run the E1 probe against the base DLL's golden. Any difference: revert that item.

## 5. Native and managed: hard deadline (A5)

- [ ] 5.1 Add the cancellation flag parameter to `ft8_subfeas_fit_signal` per §1.4; check it at entry and at the top
      of every Δt candidate, every ḟ candidate and each envelope iteration; on non-zero, zero `out_shat`, free
      nothing that is pooled, return `-4`. NULL flag means no deadline (the no-deadline path stays identical).
- [ ] 5.2 Managed: allocate the flag (unmanaged or pinned) for the whole of `RunCoreUnguarded`, free it only after
      `Parallel.For` returns; set it with a volatile write at `budget − reserve`. Introduce the named constant
      `SubtractionResidualDecodeReserve` = **1 500 ms** (Architect's Amendment 1; no literal).
- [ ] 5.3 Do not start the residual `DecodeAll` when less than the reserve remains; abandon as a deadline outcome.
- [ ] 5.4 Map `-4` to a deadline abandon inside the interop/`SubtractionPass` (`design.md` D4): **not** an exception,
      not `containedException`. `deadlineAbandoned=true`, `containedException=false`, `ResidualDecodes=0`.
- [ ] 5.5 Confirm the existing `Sub-feas residual pass:` line still carries exactly its current fields
      (`residualDecodes`, `elapsedMs`, `deadlineAbandoned`, `containedException`, `fittedSignals`). It is the R4/R4′ instrument.

## 6. Config: thread count (A4)

- [ ] 6.1 Add `decoder.subtractionMaxThreads` to the decoder settings model: **`0` = auto = `max(1, ProcessorCount − 2)`,
      and `0` is the default**; any other value clamped to `[1, ProcessorCount]` (negative becomes 1); read per cycle,
      no settings-page control. Replace the `Math.Min(Environment.ProcessorCount, 4)` at `Ft8Decoder.cs:63`.
- [ ] 6.2 Until the config-save fix (#193, Engineer) lands, a Settings save resets this key to 0 = auto and the flag
      to OFF; both are safe. Confirm that, and re-confirm after that fix lands that a save neither drops nor
      corrupts the key (§1.6).
- [ ] 6.3 Add the `REQUIREMENTS.md` FR entry for the key, following base change task 9.4.

## 7. Monitoring on the hot path (M2, M3). M1 is NOT in scope.

- [ ] 7.1 **M2.** The residual `DecodeAll` (`SubtractionPass.cs`) runs with pass-0 diagnostics disabled (a flag
      parameter or a separate export, per §1.4), computing nothing only a TLS getter would read. It must not change
      any decode output field. **Keep** `compute_noise_floor` (feeds the local-noise SNR fallback).
- [ ] 7.2 **M3.** Guard the Debug-only per-pass log loops (`Ft8Decoder.cs`, the counts and stats logging) with
      `logger.IsEnabled(LogLevel.Debug)`.
- [ ] 7.3 Do not touch the LDPC-fail LLR statistics (`ftx_compute_candidate_llr_stats`, `tls_llr_*`,
      `ft8_get_last_llr_stats`, `GetLastLlrStats`). M1 is deferred (`design.md` D7).

## 8. Tests

- [ ] 8.1 `Fit_NoDeadline_OutputBitIdenticalToBase` (real DLL, golden hashes from §3.2, several fixture signals).
- [ ] 8.2 `Fit_CancelFlagPresetReturnsMinus4Promptly` and `Fit_CancelFlagSetMidFitReturnsMinus4WithinOneIteration`
      (native, real DLL): `out_shat` zeroed, no leak, other in-flight fits undisturbed.
- [ ] 8.3 `SubtractionPass_DeadlineDuringFits_AbandonsAsDeadlineNotException`: a slow fake fit; assert
      `deadlineAbandoned=true`, `containedException=false`, pass-0 results kept, whole call within budget.
- [ ] 8.4 `SubtractionPass_LessThanReserveLeft_SkipsResidualDecode`.
- [ ] 8.5 `MaxThreads_ZeroIsAutoAndClamp`: a table over `ProcessorCount` ∈ {1, 2, 4, 16} and values {absent, 0 (both = auto),
      −1, 1, 999}; and `MaxThreads_ChangeTakesEffectNextCycle`.
- [ ] 8.6 `Fit_ManyWorkersManyCycles_DeterministicAndNoInterference`: N workers, many cycles, forced cancels mixed
      in; each signal's hash equals its single-thread hash. This is the stress test for §1.3.
- [ ] 8.7a `Workspace_LeaseReturnedWhenFitCancelledFailsOrThrows`, and `Workspace_PoolNeverExceedsBound_NeverBlocksAtMatchingParallelism`.
- [ ] 8.7 `Workspace_NoGrowthAfterWarmup_AndFreedAtDispose`: plateau of fit-attributable private memory over
      hundreds of cycles; released at shutdown; decode still works after re-initialisation. State in the test how
      it measures (private bytes, or a counter export if `design.md` allows one).
- [ ] 8.8 `ResidualDecode_DiagnosticsOff_OutputFieldsEqualDiagnosticsOn` (real DLL, fixtures) and
      `NoiseFloorFallback_SnrUnchanged`.
- [ ] 8.9 `DebugLogLoops_NotRun_WhenDebugDisabled`: a logger reporting Debug off; assert no formatting, no calls.
- [ ] 8.10 Existing `SubtractionFlagOff_DecodeOutputUnchanged`, the AV-containment and `MaxPassesUnaffectedBySubtractionFlag`
      tests still pass on the new native build.
- [ ] 8.11 Full `dotnet test`, no `--filter`, green; **quote the exact command line and the total in the report**
      (a filtered-out suite is silent, not green: HK-022).

## 9. Shim, version and documentation

- [ ] 9.1 Bump `FT8_SHIM_VERSION` to the literal chosen in §1.5; update the managed ABI self-test expectation and
      `libft8.version.txt` per the project's standard shim-change convention (all platform entries).
- [ ] 9.2 Rebuild the native library on every platform the project builds, per `BUILD.md`; `build_linux.sh` also
      compiles `subfeas_fit.c`. Pin the new `libft8.dll` SHA-256 in the report (actual and pinned; note that no
      independent pin exists, as before).
- [ ] 9.3 Update `BUILD.md`/export lists for any new export (shutdown, M2 switch).
- [ ] 9.4 Archive this change's spec delta into `openspec/specs/iterative-subtraction/spec.md` per the normal flow
      (after the base change has merged).

## 10. QA acceptance (QA-owned, after the build exists; **not** Developer tasks)

- [ ] 10.1 **E1 on real cycles**: the 60 pilot cycles plus every 9th `(run, stamp)` of the sorted pooled H ∪ M
      list (about 100 cycles), through the base DLL and the candidate DLL, no deadline; 100 % identical
      `(rc, sha256(out_shat))`, and identical flag-OFF outcome fields. **If not 100 %, stop; read nothing else.**
- [ ] 10.2 R0 as §8.1 (via each archive's producing DLL). Then R1′, R2′, R3, R4′ (a BAR: abandon over H ≤ 5 %), R6
      (13 000 ms, no allowance), R7 (descriptive) on the frozen `selection.json`, harness updated only for the new
      config key, **WSJT-X closed**, machine state recorded.
- [ ] 10.3 R5′: flag-OFF median on the new build ≤ 1.05 × the base build's, per run, with the base build
      **re-measured in the same session** on the same cycles (`design.md` D8; accepted by the Architect, Amendment 1).
      Report the change either way. M1 is absent: P4 is scored on M2 + M3 alone and nothing here may be credited to M1.
- [ ] 10.4 Row T (report only): R1′/R2′ at `subtractionMaxThreads = 4` on the H stratum, to separate the thread
      effect from the code effect.
- [ ] 10.5 Flag-OFF control re-run on the new native build (same predicate as the base ruling 2); the merge gate.
- [ ] 10.6 Report in the standard format with both DLL SHA pins, the selection SHA, the harness commit, the exact
      command lines, the blind spot (no real cycle above 32 signals; other hardware not covered), and the
      Architect's predictions P1–P4 scored by the Architect at the acceptance ruling, not by QA.

## 11. Stage B gate: **not authorised unless Stage A fails R2′ or R4′**

- [ ] 11.1 Only if §10.2 fails R2′ or R4′: return to the Architect and the Captain. Stage B items (B1 faster FFT,
      B2 pruned frequency search, B3 coarse-to-fine Δt) are built one at a time, each re-measured before the next,
      each accepted on E2 (equivalence within tolerance, ≥ 99 % of signals) and E3 (residual decodes ≥ 0.98 × Stage
      A), never on speed. B1 licence: permissive only (pocketfft-C, BSD-3, qualifies); **FFTW is GPL and prohibited**.
      A separate handoff and a spec amendment are written at that point.

## 12. Review and sign-off

- [ ] 12.1 QA reviews the diff against this `tasks.md` and `design.md` (HK-002/HK-006). §4.3 (workspace ownership),
      §5 (deadline and flag lifetime) and §8.6/8.7 (concurrency and growth) are hard blockers, not advisory.
- [ ] 12.2 `git diff --stat main -- src/ native/` non-empty and scoped to this change's Impact list; no unrelated
      changes folded in.
- [ ] 12.3 **CAPTAIN DECISION**: merge sign-off (HK-010) and push (HK-033). The flag remains OFF by default
      regardless; any live use is a separate Captain decision after the base change's §7 and §8.2/§8.3.
