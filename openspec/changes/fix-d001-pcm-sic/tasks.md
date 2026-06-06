## 1. Branch & baseline

- [x] 1.1 Create branch `fix/d001-pcm-sic` from `main`
- [x] 1.2 Confirm build is green: `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings
- [x] 1.3 Confirm test baseline: `dotnet test OpenWSFZ.slnx -c Release` — 310 passed, 0 failures

## 2. Native shim — carrier estimation

- [x] 2.1 In `ft8_shim.c`, add helper function `estimate_carrier_hz_offset(const float* pcm_buf, int pcm_len, const ftx_candidate_t* cand, const monitor_t* mon, float snr_db, float bin_width_hz)` that returns the sub-Hz carrier offset via Costas-column DFT parabolic interpolation; gate on `snr_db >= -10.0f`; return 0.0f (no correction) for signals below the threshold
- [x] 2.2 Validate `estimate_carrier_hz_offset` with a synthetic signal: inject a CP-FSK tone at a known off-bin carrier (e.g. 850.4 Hz), confirm estimated offset is within ±0.5 Hz

## 3. Native shim — CP-FSK waveform synthesis

- [x] 3.1 Add helper function `synthesise_cp_fsk(float* out_buf, int buf_len, const uint8_t* tones, int n_symbols, float carrier_hz, float dt_s, float amplitude, int sample_rate)` in `ft8_shim.c`; use `double` phase accumulator; place waveform at `max(0, round(dt_s * sample_rate))`; fill only samples within `[0, buf_len)`, clamp at buffer edges
- [x] 3.2 Validate synthesis: synthesise a known message, decode it through the existing shim, confirm original message is recovered

## 4. Native shim — PCM subtraction loop and waterfall rebuild

- [x] 4.1 In `ft8_decode_all()`, after pass 0 completes and before pass 1, declare `float pcm_residual[FT8_EXPECTED_SAMPLES]`; if any signals were decoded in pass 0, `memcpy` the original PCM into `pcm_residual`; skip allocation and subtraction if pass 0 decoded nothing
- [x] 4.2 For each pass-0 decoded signal: call `ft8_encode` to get the tone sequence; call `estimate_carrier_hz_offset` with the original PCM buffer; call `synthesise_cp_fsk` to produce the replica; subtract the replica from `pcm_residual` in-place
- [x] 4.3 After all subtractions: call `monitor_free(&mon)`, then re-run `monitor_init` and the full `monitor_process` loop on `pcm_residual` to rebuild the waterfall; recompute `noise_floor_db` and `noise_raw` from the rebuilt waterfall
- [x] 4.4 Confirm original `pcm` buffer is unchanged after a call with multiple decoded signals (verified by computing a checksum of `pcm` before and after the call in a test harness)

## 5. Native shim — three-pass loop restructure

- [x] 5.1 Change `K_MAX_PASSES` from 2 to 3 in `ft8_shim.c`
- [x] 5.2 Update the `k_pass_cfg` table to add a third row (pass 2): `{ K_MIN_SCORE_PASS2, K_MAX_CANDIDATES_PASS2, K_LDPC_ITERATIONS_PASS2 }` (same as current pass 1 parameters — it is the spectrogram-suppression pass operating on the PCM-cleaned waterfall)
- [x] 5.3 Confirm `ft8_get_max_passes()` returns 3; confirm `ft8_get_last_pass_counts(capacity=3)` returns length 3 and the sum equals total decoded messages
- [x] 5.4 Bump `FT8_SHIM_VERSION` to `20260003` in `ft8_shim.h` and `ft8_shim.c`

## 6. Native binaries rebuild

- [x] 6.1 Rebuild `libft8.dll` for Windows x64 per `BUILD.md` instructions; update `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` and `libft8.version.txt` with new SHA, build date, and `FT8_SHIM_VERSION = 20260003`
- [x] 6.2 Rebuild `libft8.so` for Linux x64 (cross-compile or native CI runner); update `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` and version entry
- [ ] 6.3 Rebuild `libft8.dylib` for macOS ARM64; update `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib` and version entry

## 7. Managed-layer constant updates

- [x] 7.1 In `Ft8LibInterop.cs`: change `ExpectedShimVersion` from `20260002` to `20260003`
- [x] 7.2 In `Ft8LibInterop.cs`: change `MaxDecodePasses` from `2` to `3`
- [x] 7.3 In `Ft8LibInterop.cs`: change `MaxResults` from `340` to `480` (140 + 200 + 140); update the summary comment
- [x] 7.4 In `Ft8Decoder.cs`: update the `ExpectedShimVersion` history comment in the file header

## 8. Tests

- [x] 8.1 Add a unit test `PcmSubtractionDoesNotMutateInputBuffer` in `OpenWSFZ.Ft8.Tests`: decode a multi-signal synthetic fixture, checksum the input PCM before and after `DecodeAsync`, assert equality
- [x] 8.2 Add a unit test `ThreePassCountsSumToTotalDecodes` in `OpenWSFZ.Ft8.Tests`: call `DecodeAsync` on a fixture with multiple signals, call `Ft8LibInterop.GetLastPassCounts(3)`, assert length == 3 and sum == result count
- [x] 8.3 Add a unit test `PassCountsLoggedAtDebug` in `OpenWSFZ.Ft8.Tests`: assert the Ft8Decoder logs exactly 3 "Iterative subtraction: pass N of 3" messages per cycle when ILogger is at Debug level
- [x] 8.4 Run `dotnet test OpenWSFZ.slnx -c Release` — confirm all prior tests still pass and new tests pass

## 9. Spec file updates (archive-time merge targets)

- [x] 9.1 Update `openspec/specs/iterative-subtraction/spec.md` by merging delta requirements from `openspec/changes/fix-d001-pcm-sic/specs/iterative-subtraction/spec.md` — replace existing requirements with the MODIFIED versions and append the ADDED requirements
- [x] 9.2 Update `openspec/specs/ft8lib-interop/spec.md` by merging MODIFIED requirements from `openspec/changes/fix-d001-pcm-sic/specs/ft8lib-interop/spec.md`
- [x] 9.3 Update `ABI self-test` expected version in `openspec/specs/ft8lib-interop/spec.md` from `20260002` to `20260003`

## 10. R&R S7 verification

- [x] 10.1 Run the R&R S7 scenario against the new build: `python harness/run_scenario.py scenarios/s7-compounding.json --dry-run` to confirm scenario loads; then run live (requires WSJT-X and OpenWSFZ monitoring VB-CABLE) — dry-run PASS; live run: CAPTAIN task (requires WSJT-X + VB-CABLE)
- [ ] 10.2 Run `matcher.py` and `analyse.py` on the new S7 run results; confirm improvement on P0 (co_channel 2-stack equal SNR: OpenWSFZ was 0/6, target ≥ 1/6) and P8 (time_freq co-freq dt 0.5 s: was 0/6, target ≥ 1/6) versus `6bab388` baseline
- [ ] 10.3 Commit results directory to `qa/rr-study/results/<date>-<sha>/`

## 11. Final integration

- [ ] 11.1 Run full build and test suite one final time on the implementation branch — 0 errors, 0 warnings, all tests pass
- [ ] 11.2 Push `fix/d001-pcm-sic` branch to `origin`; open PR against `main`
- [ ] 11.3 Verify CI passes on all three matrix legs (Windows, Linux, macOS)
