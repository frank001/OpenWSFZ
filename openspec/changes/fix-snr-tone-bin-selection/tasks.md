## 1. Shim Source Edit

- [x] 1.1 In `ft8_shim.c`, before the `signal_db` computation block, call `ft8_encode(msg.payload, tones)` to obtain the 79-symbol tone sequence
- [x] 1.2 Replace the inner `max(row[0..7])` loop with a single read of `row[tones[b - b0]]` for each symbol `b` in `[b0, b1)`
- [x] 1.3 Verify the `fi` index calculation is unchanged and `row[tones[b - b0]]` correctly addresses the active tone bin relative to `cand->freq_offset`

## 2. Native Binary Rebuild

- [x] 2.1 Rebuild `libft8.dll` for win-x64 and update `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`
- [x] 2.2 Rebuild `libft8.so` for linux-x64 and update `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`
- [ ] 2.3 Rebuild `libft8.dylib` for osx-arm64 and update `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib`

## 3. Test Validation

- [x] 3.1 Run `dotnet test` — confirm all existing tests pass, especially `Ft8DecoderPlausibilityTests` (decode correctness must be unaffected)
- [x] 3.2 Run `dotnet test` against the G6 gate fixture corpus — confirm message sets are identical to pre-fix (message text unchanged, only SNR values change)
- [x] 3.3 If any test asserts a specific SNR value or range, update tolerance to allow [−2, +0.5] dB from injected SNR per the updated spec

## 4. R&R Verification

- [ ] 4.1 With both applications running and ALL.TXT cleared, re-run the full R&R study via `python run_study.py` from `qa/rr-study/`
- [ ] 4.2 Confirm S1 mean bias (OpenWSFZ) lies within [−2.0, +0.5] dB
- [ ] 4.3 Confirm S1 R² (OpenWSFZ) ≥ 0.50
- [ ] 4.4 Confirm %GR&R (S1) shows improvement over the pre-fix value of 45.8%
- [ ] 4.5 Commit R&R results and updated `trend.csv`

## 5. Change Closure

- [x] 5.1 Commit shim source edit and rebuilt binaries with message referencing R&R-001
- [ ] 5.2 Push to main and confirm CI passes on all three matrix legs (win-x64, linux-x64, osx-arm64)
