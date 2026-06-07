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
- [x] 2.10 Run the full R&R study (S1–S7) — S1–S6 must remain PASS; record the S7 result for comparison with the baseline (46.2%) — RESULT: S7 OpenWSFZ **57.0%** (+10.8 pp vs baseline); S1–S6 all PASS. Run `2026-06-07-15b220b`. See `QA-FINDINGS-rr-007.md`.
- [x] 2.11 Run the 42-cycle ground-truth corpus — must be ≥ 69.1% (no regression from baseline) — RESULT: 69.2% (614/887) ✓

## 3. Option B Results Gate — Captain Review

- [x] 3.1 Present Option A audit verdict and Option B R&R S7 result to the Captain — done (2026-06-07; see `QA-FINDINGS-rr-007.md`)
- [x] 3.2 **CAPTAIN DECISION — ~~Proceed to Option C PoC~~ / ~~Proceed to Option D~~ / **Accept current state** — Option B (+10.8 pp S7) lands in main; D-001 remains Open; Option C not pursued at this time. (2026-06-07)**

## 4. Option C PoC — Python Proof-of-Concept (NOT PURSUED — Captain decision task 3.2)

- [n/a] 4.1 Write `qa/rr-study/poc_amplitude_sic.py`
- [n/a] 4.2 Run the PoC over ≥ 10 synthetic S7 P0 trial cases
- [n/a] 4.3 Record PoC results in `qa/rr-study/POC-D001-amplitude-sic.md`

## 5. Option C PoC Results Gate — NOT PURSUED

- [n/a] 5.1 Present PoC results to the Captain
- [n/a] 5.2 **CAPTAIN DECISION — approve or reject Option C production implementation**

## 6. Option C Production — NOT PURSUED

- [n/a] 6.1–6.9 (all Option C production tasks — skipped; Option C not approved)

## 7. Option D — D-001 Disposition (Captain decision required)

- [x] 7.1 **CAPTAIN DECISION — ~~Close D-001~~ / ~~Downgrade to Informational~~ / **Keep D-001 Open** — improvement is real (+10.8 pp S7) but P0 and P8 cases remain unresolved; D-001 carried forward for future iteration. (2026-06-07)**
- [x] 7.2 Update `openspec/specs/iterative-subtraction/spec.md` AC-IS-1 status — updated to reflect R&R results and D-001 carried forward
- [x] 7.3 Update GitHub issue frank001/OpenWSFZ#3 — updated with Option B results; issue remains Open
