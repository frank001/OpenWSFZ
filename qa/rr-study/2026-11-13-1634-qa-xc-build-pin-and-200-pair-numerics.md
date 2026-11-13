# XC-BUILD: the DLL pin holds, and the Developer's detector reproduces the desk library on 200 real pairs

**Written:** 2026-11-13, `date -u` read 16:33:27Z. **Build:** `f82b6432b3eafab40a72b80ab1f294d9a8f1ea51` (APPROVED, QA `f3997937`), QA tree `_qa-scratch\xc-review\tree`. PC (Windows). Nothing pushed; no arm run.

## 1. Native-lib pin (Windows)

| item | value |
|---|---|
| pinned `libft8.dll` SHA-256 (CQ-AP arms, `bin_v2`, `59eb5a8f` records) | `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` |
| actual, `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` in the reviewed tree | `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` |
| actual, `bin_xc/libft8.dll` (the harness build used for the smokes) | `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` |
| `git diff --stat ce5734b6 f82b6432 -- native src/OpenWSFZ.Ft8/Native` | empty |

**Pin PASS (Windows).** The Linux `libft8.so` SHA-256 on sol is NOT yet read (owed at the sol build, with the A2.1 and K3 precondition B = A1 = A2).

## 2. The 200-pair numeric comparison (dev-task line 51)

- **Pairs:** 100 E1 rows (those with encodable tones) and 100 null tests, evenly spaced through the frozen lists (`_qa-scratch\xc-template\frozen\xt_tasks.json`, no random draw), each on the TRAIN night's residual buffer of arm B (`ta-res\cap_run\cap\buffers\<stamp>_R3|R2.f32`) at the row's prior position, the row's own 79 tones.
- **Instruments:** desk `qa/xc-template/xt_lib.py` (`search`, via `xt_score.run_tasks`) against the Developer's `CrossCycleTemplateDetector.Search` (`qa/xc-build/xcmp`, an `Ft8.FitProbe` assembly, which `InternalsVisibleTo` admits). Same buffer, centre, tones, dt in WSJT-X's convention.
- **Result:** max |ΔS_E\*| = **8.5e-11** (p50 5.5e-13, p95 6.1e-12; relative max 8.0e-11). **The argmax frequency and dt are identical in all 200** (0 differ). E1 S_E\* range 1.19 to 6.65; null 0.86 to 2.31, so the comparison is not on a flat region of the statistic (HK-026).
- **Reading:** the C# detector is the desk detector to floating-point rounding. **No numeric finding.**

Files: `qa/xc-build/xcmp/{Program.cs,Ft8.FitProbe.csproj,xcmp_desk.py}`. Working files (pair list with tones, per-pair scores) stay in `_qa-scratch\xc-review\xcmp\` (outside git, deleted at job close).

## 3. Still owed before a first arm

`pre_merge_check.py` before any push; the Replay81 reconciliation with the Developer's flag names; the sol setup (audio copy, two builds, `.so` SHAs) and the K4 gate, each on the Captain's go.
