# Handoff — Update BUILD.md for shim 20260030 export list

**Date:** 2026-06-24
**QA review:** R3 (decoder-settings-page pre-merge inspection)
**Branch:** `feat/decoder-settings-page`

---

## Context

Task 1.4 of the decoder-settings-page change required updating both `libft8.version.txt`
and `BUILD.md`. The version.txt was updated correctly. BUILD.md was not modified.

BUILD.md is the manual-rebuild reference document at
`src/OpenWSFZ.Ft8/Native/BUILD.md`. It contains three stale items that must be
corrected before the branch is merged.

---

## Branch

No new branch required. Fix directly on `feat/decoder-settings-page`.

---

## Actions

**1. Replace the Windows link command (lines 108–111) with the current export list.**

Find the block:
```
:: Link into DLL
link /DLL /OUT:libft8.dll /EXPORT:ft8_lib_version_check /EXPORT:ft8_decode_all /EXPORT:ft8_get_last_pass_counts /EXPORT:ft8_get_max_passes /EXPORT:ft8_get_last_noise_floor_db ^
   constants.obj crc.obj decode.obj encode.obj ldpc.obj message.obj text.obj ^
   monitor.obj kiss_fft.obj kiss_fftr.obj ft8_shim.obj
```

Replace with (export list must match `native/ft8_lib_build/rebuild_shim.bat` exactly):
```
:: Link into DLL
:: Note: use rebuild_shim.bat at native/ft8_lib_build/ for local Windows builds.
:: The exports below must stay in sync with that script.
link /DLL /OUT:libft8.dll ^
   /EXPORT:ft8_lib_version_check ^
   /EXPORT:ft8_decode_all ^
   /EXPORT:ft8_get_last_pass_counts ^
   /EXPORT:ft8_get_max_passes ^
   /EXPORT:ft8_get_last_noise_floor_db ^
   /EXPORT:ft8_encode_message ^
   /EXPORT:ft8_get_last_candidate_counts ^
   /EXPORT:ft8_get_last_llr_stats ^
   /EXPORT:ft8_set_ap_bits ^
   /EXPORT:ft8_set_decode_params ^
   constants.obj crc.obj decode.obj encode.obj ldpc.obj message.obj text.obj ^
   monitor.obj kiss_fft.obj kiss_fftr.obj ft8_shim.obj
```

**2. Update the Linux "verify exports" comment (line ~150).**

Change:
```
Verify exports (all five symbols must appear):
```
To:
```
Verify exports (all ten symbols must appear):
```

**3. Update the macOS "verify exports" comment (line ~200).**

Change:
```
Verify exports (`nm -gU` on macOS prefixes exported symbols with an underscore; all five symbols must appear):
```
To:
```
Verify exports (`nm -gU` on macOS prefixes exported symbols with an underscore; all ten symbols must appear):
```

**4. Update the Decode Parameters table (lines 62–68).**

Replace the stale table:
```
| Parameter | Value | Source |
|---|---|---|
| `kMin_score` | 10 | demo/decode_ft8.c default |
| `kMax_candidates` | 140 | demo/decode_ft8.c default |
| `kLDPC_iterations` | 25 | demo/decode_ft8.c default |
| `kMax_decoded_messages` | 50 | demo/decode_ft8.c default |
```

With current values (two-pass, runtime-configurable K):
```
| Parameter | Value | Source |
|---|---|---|
| Pass-0 `kMin_score` | 10 | `K_MIN_SCORE` in ft8_shim.c |
| Pass-1 `kMin_score` | 10 (default) | `s_k_min_score_pass2` — runtime-configurable via `ft8_set_decode_params`; default calibrated by D-009 R&R study (shim 20260029) |
| Pass-0 `kMax_candidates` | 140 | `K_MAX_CANDIDATES` in ft8_shim.c |
| Pass-1 `kMax_candidates` | 200 | `K_MAX_CANDIDATES_PASS2` in ft8_shim.c |
| `kLDPC_iterations` | 50 | `K_LDPC_ITERATIONS` — raised from 25 at shim 20260025 (H_ITER diagnostic) |
| `OSD_CORR_THRESHOLD` | 0.10f (default) | `s_osd_corr_threshold` — runtime-configurable; default calibrated by D-009 R4 (shim 20260028) |
| `OSD_NHARD_MAX` | 60 (default) | `s_osd_nhard_max` — runtime-configurable; default calibrated by D-009 R5 (shim 20260028) |
```

---

## Acceptance Criteria

- `src/OpenWSFZ.Ft8/Native/BUILD.md` changed on `feat/decoder-settings-page`
- Windows link command lists all ten exports; matches `rebuild_shim.bat`
- Both "five symbols" comments read "ten symbols"
- Decode Parameters table reflects the two-pass architecture and runtime-configurable values
- `dotnet test OpenWSFZ.slnx -c Release` — 0 failures (no test changes required)

---

## References

- OpenSpec change: `openspec/changes/decoder-settings-page/`
- Task 1.4 in `openspec/changes/decoder-settings-page/tasks.md`
- Authoritative build script: `native/ft8_lib_build/rebuild_shim.bat`
- Current exported symbols: `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`
