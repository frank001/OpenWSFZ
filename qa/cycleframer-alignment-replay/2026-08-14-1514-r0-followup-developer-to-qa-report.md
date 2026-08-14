# R0 review follow-up — Developer session report

**2026-08-14 15:14Z.** Implements `dev-tasks/2026-08-14-1504-r0-review-followup-stderr-log-noise.md`
on `feat/r0-reproducible-native-build`, on top of `3bc2b9d` (not yet pushed/merged at the time
this follow-up was folded in). Not pushed, not merged, `pre_merge_check.py` not run.

## §1 — `monitor.c` `LOG_LEVEL` fix

`native/ft8_lib_build/patched/common/monitor.c:4`: `#define LOG_LEVEL LOG_INFO` → `LOG_WARN`
(option (b), the dev-task's recommendation — `monitor.c` has zero `LOG_WARN`/`ERROR`/`FATAL` call
sites today, so this silences exactly the four `LOG_INFO` prints (`monitor_init`'s Block/
Subblock/N_FFT/N_iFFT sizes) while leaving `LOG()` live for any future `LOG_WARN`-or-above
diagnostic. `ft8/debug.h` untouched (genuinely vendored, correct as-is).

- **New DLL SHA256:** `897f81dda95b83b24156a905b3aeec4a1cb98c64e5243564e6d0eb6b60643cb3`
  (`FT8_SHIM_VERSION` stays `20260039` — folded in per the Captain's ruling below).
- **stderr confirmed quiet:** single-cycle decode captured 0 bytes of stderr output (previously
  4 lines/cycle). Full 250-cycle AC-1/AC-2 replay also captured 0 bytes of stderr across the
  entire run.
- **AC-1/AC-2 re-run, same 250-cycle range (`260808_004000`..`260808_014215`):**
  - Fixed build vs. pre-fix `20260039` build (`fa87bd97...`): **PASS, zero differences.**
  - Fixed build vs. original shipped baseline (`c559a049.../20260038`): **PASS, zero
    differences.**
  - Confirms the log-level change is exactly what it claims to be — log output only, no decode
    behaviour change.
- **Tests:** `dotnet build` (managed): 0 warnings, 0 errors. `dotnet test`: **306/306**, on the
  fixed `897f81dd...` DLL.

## §2 — Captain's rulings (all three obtained explicitly, none assumed)

1. **Shim version:** fold the fix into the same `20260039` rather than bumping to `20260040` —
   `3bc2b9d` was not yet pushed or merged, so this amends R0's own not-yet-shipped work. Recorded
   in `ft8_shim.h`'s and `Ft8LibInterop.cs`'s `20260039` changelog entries (new sub-entries, not a
   new version block).
2. **§2.1 (38 native-build warnings):** accepted as the new native-build warning-count baseline.
   No code change made. Zero C4013/C4047 among them, as previously reported — this ruling closes
   the item, it does not reopen it.
3. **§2.2 (spec scenario text):** corrected.
   `openspec/changes/r0-reproducible-native-build/specs/dependency-licence-policy/spec.md`'s
   requirement body and its "GPL/AGPL scan" scenario now state the actual measured result (zero
   hits total) instead of the originally anticipated "two flagged hits." `openspec validate
   r0-reproducible-native-build --strict` re-run after the edit: still valid.

## Definition of done (dev-task §4) — all items closed

- [x] `monitor.c`'s `LOG_LEVEL` lowered (option (b), `LOG_WARN`); DLL rebuilt; new SHA recorded
- [x] AC-1/AC-2 re-run on the same 250-cycle range; zero decode-output differences confirmed
- [x] `stderr` confirmed quiet on a normal decode cycle (and across the full 250-cycle replay)
- [x] §2.1 ruling obtained: 38 native warnings accepted as baseline, no code change
- [x] §2.2 spec scenario text corrected to match the measured zero-hit result
- [x] Build clean (managed layer, 0 warnings); `OpenWSFZ.Ft8.Tests` 306/306

Nothing else in `3bc2b9d` touched, per the dev-task's §3 explicit instruction.

Not pushed, not merged, `pre_merge_check.py` not run. Captain reviews the diff.
