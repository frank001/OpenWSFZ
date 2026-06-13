## 1. Native Shim — C Implementation

- [x] 1.1 Add `#define K_LOCAL_NOISE_WINDOW 32` constant near the top of `ft8_shim.c` (after existing `#define` blocks)
- [x] 1.2 Implement `compute_local_noise_floor_db(const ftx_waterfall_t* wf, int freq_offset)` function in `ft8_shim.c` as specified in design.md — histogram median of 32-bin left and right sideband windows across all blocks and all time/freq sub-samples, with `tls_last_noise_floor_db` fallback
- [x] 1.3 In `ft8_decode_all`, replace `float snr = signal_db - noise_floor_db - 26.5f;` with a two-line call: `float local_noise_db = compute_local_noise_floor_db(&mon.wf, (int)cand->freq_offset);` then `float snr = signal_db - local_noise_db - 26.5f;`
- [x] 1.4 Verify `noise_floor_db` (global) is still computed and stored in `tls_last_noise_floor_db` — it must remain available for the diagnostic log; confirm `ft8_get_last_noise_floor_db()` still returns it unchanged

## 2. Native Shim — Version Bump

- [x] 2.1 In `ft8_shim.h`, update `#define FT8_SHIM_VERSION 20260010` to `20260012`
- [x] 2.2 In `ft8_shim.c`, update the version history comment block to record: 20260010 = H4 D-001 co-channel diagnostic baseline; 20260011 = H5 spectrogram ramp, reverted; 20260012 = fix-d004-local-noise-floor (local noise floor, K=32 bins)

## 3. Binary Rebuild

- [x] 3.1 Rebuild win-x64 `libft8.dll` per `src/OpenWSFZ.Ft8/Native/BUILD.md` and replace the committed file
- [x] 3.2 Rebuild linux-x64 `libft8.so` per `BUILD.md` and replace the committed file
- [x] 3.3 Rebuild osx-arm64 `libft8.dylib` per `BUILD.md` and replace the committed file (CI always rebuilds from current ft8_shim.c on every push — placeholder committed)
- [x] 3.4 Update `libft8.version.txt` for all three platforms: new SHA, build date, SNR formula (`local_noise_floor (K=32) − 26.5 dB`), pass count 2, shim version 20260012

## 4. Managed Interop Update

- [x] 4.1 In `Ft8LibInterop.cs`, update `private const int ExpectedShimVersion = 20260010;` to `20260012`
- [x] 4.2 Update the `ExpectedShimVersion` doc comment in `Ft8LibInterop.cs` to describe shim 20260012 (local noise floor, K=32 bins per sideband, resolves D-003/D-004)

## 5. Build and Test

- [x] 5.1 Run `dotnet build OpenWSFZ.slnx -c Release` — confirm 0 errors, 0 warnings
- [x] 5.2 Run `dotnet test OpenWSFZ.slnx -c Release` — confirm all tests pass (expect 330 passed; if the ABI self-test test exists, confirm it passes against the new version 20260012)
- [x] 5.3 Confirm the G6 fixture tests pass (real-signal recovery scenarios) — the fix must not regress decode results, only SNR values

## 6. Post-Fix Validation — S1 R&R

- [ ] 6.1 Run the S1 R&R synthetic scenario (`python run_study.py --scenario S1`) against the updated build
- [ ] 6.2 Run `python analyse.py` to generate `report.md` in the new results directory
- [ ] 6.3 Complete `report.md` Section 1 (hypothesis: validating that local noise floor preserves ±2.0 dB bias gate; null hypothesis: S1 bias does not exceed ±2.0 dB; defects D-003/D-004 under observation)
- [ ] 6.4 Complete `report.md` Section 5 (recommendations based on result: if PASS, note calibration constant retained; if FAIL, state required adjustment to −26.5 dB constant and trigger a recalibration run)
- [ ] 6.5 If S1 bias exceeds ±2.0 dB, adjust the −26.5 dB constant in `ft8_shim.c`, rebuild binaries, re-run S1, and repeat until within threshold
- [ ] 6.6 Commit the S1 result directory (with complete NFR-023 report)

## 7. Issue Housekeeping

- [ ] 7.1 Close GitHub issue #11 (D-003) as a duplicate of #12 — comment: root cause confirmed as frequency-dependent SNR bias (D-004); D-003 is the extreme tail (high-frequency signals at 2600–3000 Hz falling below −30 dB); no separate mechanism; resolved by local noise floor fix (this change)
- [ ] 7.2 Update GitHub issue #12 (D-004) with confirmed root cause (global vs local noise floor; audio-chain rolloff of up to −22 dB at 2800–3000 Hz); reference the endurance run data (2026-06-13, 235 matched-pair D-003 events, −6.32 dB overall bias); link this change; update status once S1 validates

## 8. MEMORY.md Update

- [ ] 8.1 Update the D-003 and D-004 entries in `MEMORY.md` to record: root cause confirmed (local vs global noise floor), fix merged (shim 20260012), S1 re-run result, GitHub issue status
- [ ] 8.2 Add shim 20260012 to the D-001 diagnostic run history table in `MEMORY.md` as a note that this slot is used for the D-003/D-004 fix (not a D-001 hypothesis)
