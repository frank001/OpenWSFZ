## 1. Option A — Upstream ft8_lib Audit

- [x] 1.1 Check kgoba/ft8_lib repository for commits since the pinned v2.0 tag — look specifically for any multi-pass, SIC, or iterative-decode changes in the decode pipeline
- [x] 1.2 If meaningful improvements exist: evaluate whether the shim interface (ft8_shim.c) remains compatible and what rebuild effort is required; record findings in a short note in this change directory
- [x] 1.3 Record the audit verdict (upstream improvement available / not available / repository abandoned) and confirm whether to proceed with the upstream update or proceed directly to Option B

## 2. Option B — Soft SNR-Scaled Spectrogram Suppression

- [x] 2.1 Add `K_SOFT_SUPP_SNR_MIN_DB (−5.0f)` and `K_SOFT_SUPP_SNR_MAX_DB (+15.0f)` as named constants in `ft8_shim.c`; replace the hard-zero tile assignment with the linear attenuation formula from the design (`tile_value *= factor`)
- [x] 2.2 Increment `FT8_SHIM_VERSION` to `20260004` in `ft8_shim.c` and `ft8_shim.h`
- [x] 2.3 Rebuild `libft8.dll` (MSVC, Windows x64) and commit the binary; update `libft8.version.txt` with the new version, toolchain, and build date
- [x] 2.4 Rebuild `libft8.so` (GCC, Linux x64) and commit the binary; update `libft8.version.txt`
- [x] 2.5 Rebuild `libft8.dylib` (Clang, macOS ARM64) and commit the binary; update `libft8.version.txt`
- [x] 2.6 Update `ExpectedShimVersion` in `Ft8LibInterop.cs` from `20260002` to `20260004`; update the `MaxDecodePasses` comment if needed
- [x] 2.7 Update `iterative-subtraction` spec and `ft8lib-interop` spec in `openspec/specs/` to reflect soft attenuation and version `20260004` (archive the delta specs from this change)
- [x] 2.8 Add or update unit tests in `OpenWSFZ.Ft8.Tests`:
  - `SoftSuppression_StrongSignal_TilesAreZeroed` — decode with SNR ≥ +15 dB; assert attenuation factor = 0.0
  - `SoftSuppression_WeakSignal_TilesUnchanged` — decode with SNR ≤ −5 dB; assert attenuation factor = 1.0
  - `SoftSuppression_MidRangeSnr_TilesHalved` — decode with SNR = +5 dB; assert factor ≈ 0.5
  - Update `Ft8LibInteropTests` ABI version assertion from `20260002` to `20260004`
- [x] 2.9 Run `dotnet test OpenWSFZ.slnx -c Release` — all 314+ tests must pass (313 passing; 3 new tests added; 0 failures)
- [ ] 2.10 Run the full R&R study (S1–S7) — S1–S6 must remain PASS; record the S7 result for comparison with the baseline (46.2%)
- [x] 2.11 Run the 42-cycle ground-truth corpus — must be ≥ 69.1% (no regression from baseline) — RESULT: 69.2% (614/887) ✓

## 3. Option B Results Gate — Captain Review

- [ ] 3.1 Present Option A audit verdict and Option B R&R S7 result to the Captain
- [ ] 3.2 **CAPTAIN DECISION — choose one:**
  - **Proceed to Option C PoC** (if S7 improvement is insufficient and further effort is warranted)
  - **Proceed to Option D** (downgrade/close D-001 based on A+B results alone)
  - **Accept current state** (D-001 remains Open; no further action at this time)

## 4. Option C PoC — Python Proof-of-Concept (requires Captain approval from task 3.2)

- [ ] 4.1 Write `qa/rr-study/poc_amplitude_sic.py`: synthesise two equal-SNR co-channel FT8 signals using the existing synthesiser; sum in PCM; implement amplitude-tracked CP-FSK subtraction (per-symbol amplitude from waterfall magnitude + linear frequency trajectory across all 79 symbols); call `libft8.dll` on the residual; report recovery count
- [ ] 4.2 Run the PoC over ≥ 10 synthetic S7 P0 trial cases (2-stack, equal SNR); record recovery rate for baseline (no subtraction) and PoC (with subtraction)
- [ ] 4.3 Record PoC results in `qa/rr-study/POC-D001-amplitude-sic.md`

## 5. Option C PoC Results Gate — Captain Review

- [ ] 5.1 Present PoC results to the Captain:
  - If improvement ≥ +5 pp on synthetic S7 → request approval for production implementation
  - If improvement < +5 pp → recommend abandoning Option C and proceeding to Option D
- [ ] 5.2 **CAPTAIN DECISION — approve or reject Option C production implementation**

## 6. Option C Production — Amplitude-Tracked PCM-Domain SIC (requires Captain approval from task 5.2)

- [ ] 6.1 Implement `estimate_carrier_amplitude_envelope()` in `ft8_shim.c`: extract per-symbol magnitude from the waterfall at the decoded tone bin across all 79 symbols
- [ ] 6.2 Implement `estimate_carrier_frequency_trajectory()` in `ft8_shim.c`: fit a linear (first-order) frequency drift across all 79 decoded symbol positions using least-squares; return slope and intercept
- [ ] 6.3 Implement `synthesise_tracked_cp_fsk()` in `ft8_shim.c`: generate replica using per-symbol amplitude and instantaneous frequency from the linear trajectory; use heap-allocated `pcm_residual` (`malloc`/`free`); handle `malloc` failure with graceful fallback to single-pass decode
- [ ] 6.4 Increment `FT8_SHIM_VERSION` to `20260005`; rebuild all three platform binaries; commit; update `libft8.version.txt` and `ExpectedShimVersion`
- [ ] 6.5 Update `iterative-subtraction` and `ft8lib-interop` specs; add requirements for amplitude-tracked synthesis and heap allocation (per the spec delta added in this change)
- [ ] 6.6 Add unit tests: `PcmResidual_HeapAllocated_NoStackOverflow`, `FrequencyTrajectory_LinearFit_Correct`, `AmplitudeEnvelope_MatchesWaterfallMagnitudes`
- [ ] 6.7 Run full test suite — all tests must pass
- [ ] 6.8 Run full R&R study (S1–S7) — S1–S6 must remain PASS; S7 must show ≥ +5 pp vs Option B baseline
- [ ] 6.9 Run 42-cycle ground-truth corpus — must be ≥ 69.1%

## 7. Option D — D-001 Disposition (Captain decision required)

- [ ] 7.1 **CAPTAIN DECISION — choose one:**
  - **Close D-001** (mark as Won't Fix or Resolved with documented rationale)
  - **Downgrade D-001 to Informational** (gap acknowledged; not a priority; Option C noted as future research)
  - **Keep D-001 Open** (further iteration planned)
- [ ] 7.2 Update `openspec/specs/iterative-subtraction/spec.md` AC-IS-1 status to reflect the final outcome
- [ ] 7.3 Update GitHub issue frank001/OpenWSFZ#3 with the final verdict and close or relabel as appropriate
