# R0 (reproducible-native-build) — Developer session report

**2026-08-14 14:52Z.** Branch `feat/r0-reproducible-native-build` off `main` (`4eb2b70`). All
`tasks.md` items complete (§1–§6). Not pushed, not merged, `pre_merge_check.py` not run — per
HK-011/HK-014/HK-010, the Captain reviews the diff and decides on merge.

## D1 — Vendored source tree

- **Upstream remote:** `https://github.com/frank001/ft8_lib.git`, branch `msvc-compat`
- **HEAD SHA:** `d18ed84f058290b36652f50db41875f2cafbaa4c`
- **Content-identity check**, re-run independently (not copied from a prior run):
  ```
  git diff --ignore-cr-at-eol
  ```
  Output: **0 bytes, exit 0.** `git status --short` reports every tracked path as modified, but
  every one is CRLF/LF line-ending noise only — confirmed by capturing the diff's stdout
  separately from its stderr warnings and measuring `wc -c` = 0.
- **File list:** 22 files traced by full include-graph analysis from `decode.c`/`monitor.c`/
  `ft8_shim.c` (not copied from the design doc's "~24" estimate) — matches the spec's minimum
  list exactly, confirmed complete by the clean build succeeding with no missing-header errors.
- **Byte-for-byte copy verification:** every file `cmp`'d against its upstream source at copy
  time — zero mismatches.
- **Committed size:** 159 KB, 22 files, 115,705 bytes.
- **D5 (decode.c/monitor.c placement):** left in place at `native/ft8_lib_build/patched/`. Keeps
  the vendored tree byte-identical to upstream (its whole provenance guarantee) and is minimal
  churn to a script that already correctly pointed there.

Full detail: `native/ft8_lib_vendor/PROVENANCE.md`.

## D2 — Rebuild script

`native/ft8_lib_build/rebuild_shim.bat` extended with 9 new `cl` steps (all pointing at
`native/ft8_lib_vendor/`), an `obj\*.obj` clear-before-build step, and repointed `decode.c`/
`ft8_shim.c` `/I` flags off `C:\Temp\ft8_lib_headers` onto the vendored tree. Link step's
`/EXPORT:` list unchanged — confirmed via `dumpbin /exports` on the built DLL: exactly the same
eleven symbols as before.

## Finding 1 (surfaced during 2.3, escalated to the Captain, fixed per the Captain's ruling)

Compiling vendored `ft8/message.c` with the same flags the other files use produced:

```
message.c(953): warning C4013: 'stpcpy' undefined; assuming extern returning int
message.c(953): warning C4047: '=': 'char *' differs in levels of indirection from 'int'
```

Mechanically confirmed (not just reasoned about) to reproduce **D-006's exact root cause**: the
process-terminating access violation fixed at shim `20260015` by hand-patching a single opcode
byte directly in the pre-built `message.obj` (`0x63` MOVSXD → `0x8B` MOV at offset `0x01B27`), with
**no source-level fix ever written**, because `message.c` was never recompiled by
`rebuild_shim.bat` until this change (only linked as an opaque pre-built object). MSVC's
`<string.h>` never declares `stpcpy` (POSIX/GNU-only); with no prototype in scope, MSVC assumes
`int` return and truncates the 64-bit pointer.

**Fix, per the Captain's ruling:** `native/ft8_lib_build/patched/stpcpy_msvc_compat.h`, force-
included via `/FI` only on `message.c`'s compile step. **Zero bytes of the vendored tree are
touched.** Verified at two levels:
1. Warning gone on recompile (isolated test, then in the full build).
2. **Disassembly** (`dumpbin /disasm`): both `call stpcpy` sites now follow with a full 64-bit
   `mov` (`48 8B D8` / `4C 8B D0`), not the truncating `movsxd`. Exactly the corrected codegen the
   original hand-patch produced.

## Finding 2 (informational, no fix needed)

The freshly-compiled build prints `LOG_INFO`-level diagnostics (`Block size = ...`,
`Subblock size = ...`, `N_FFT = ...`) to stderr on every decode call — the already-tracked,
unrelated-to-R0 `native/ft8_lib_build/patched/common/monitor.c` has carried
`#define LOG_LEVEL LOG_INFO` since its very first port commit (`94779ac`). It never fired before
because `monitor.c` was never actually compiled — the shipped `monitor.obj` was a stale pre-built
object. Does not touch `FT8Result` fields (confirmed — AC-1/AC-2 diffs are clean), so no
behavioural effect, but it is further evidence that pre-R0 binaries diverged from tracked source
in ways nobody could previously see. Not fixed (out of scope, pre-existing, not part of this
change's touched files) — flagged for awareness.

## AC-1 / AC-2 / AC-3

New harness: `qa/cycleframer-alignment-replay/r0_ac1_ac2_replay.py` (decode + serialise) and
`r0_ac1_ac2_diff.py` (mechanical diff), reusing `p23_common.py`'s production preprocessing/decode
pipeline. **Cycle range: 250 contiguous cycles, `260808_004000`..`260808_014215`**, pinned 20m
corpus (`artefacts/20260808_live_run_0016-8080/wsjt-x/wav`).

- **AC-1** (vendored build vs. pinned baseline):
  `python r0_ac1_ac2_diff.py baseline_output.json build1_output.json` → **exit 0, PASS, zero
  differences across 250 cycles.**
  - Baseline DLL: `c559a049d103c1f350f1a87b319033d5f8d1a2f91b74d9756d8d7cf03d2e6112` / shim 20260038
    (confirmed matches the currently-shipped `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` before
    rebuild)
  - Vendored build 1: `0a0e19494c5a6ff740a7c9889c912f6674610fbf4bf3ceccfc88318a9149871` / shim 20260038
- **AC-2** (two independent clean builds vs. each other):
  `python r0_ac1_ac2_diff.py build1_output.json build2_output.json` → **exit 0, PASS, zero
  differences.** DLL SHAs differ (`0a0e1949...` vs `024f8c37...`) — expected, PE `TimeDateStamp`
  only (D2's design decision: decode *output* is the contract, not the DLL file).
- **AC-3** (shim version bump): `FT8_SHIM_VERSION` / `ExpectedShimVersion` → `20260039`. New DLL
  SHA256: **`fa87bd9779c4dba831b792f5bc2608f29db875d7ce8d6c535f93e094b485e6b8`**. ABI self-test
  confirmed (`ft8_lib_version_check() == 20260039`). Re-diffed against the pre-bump build: zero
  differences (the bump alone changes no decode behaviour).

## D5 / AC-4 — Licence compliance

`THIRD-PARTY-NOTICES.md` written at repo root (MIT/Kārlis Goba, BSD-3-Clause/Mark Borgerding, both
reproduced in full).

**GPL/AGPL scan** (`grep -rin "gnu general public|\bgpl\b|affero"`, case-insensitive, across the
vendored tree + `patched/`): **zero hits — cleaner than the spec's pre-registered scenario
anticipated.** The scenario expected "only the two known `ft8/constants.h` lines 75/78" as
flagged hits; measured reality is those two lines (confirmed present, unremoved, at exactly those
line numbers via a separate `grep -rn "WSJT-X"` sanity check) say only `"From WSJT-X's ..."` and
do not contain the literal search strings, so the scan returns zero hits total, not two. Recorded
precisely rather than silently declared "matches spec."

## D3 — Replay-harness determinism

`qa/cycleframer-alignment-replay/p23_common.py:182`: `ref = {k: a[k] for k in a.keys() & b.keys()}`
→ `sorted(a.keys() & b.keys())`, matching the established `x3_lattice_crowding.py`/
`x4_spectral_locality.py` fix pattern (hash-randomised set iteration silently breaks seeded
determinism across process runs).

## D4 — `--assert-dll-sha`

`p23_common.py`'s `Decoder` class already had a narrow DLL-SHA-pinning capability (hard-coded to
one module-level constant, currently stale — pins `39aa1031...`, the unmerged
`d001-rc4-decode-depth` three-pass build, not any binary this change compares). Extended with
`expected_sha256`/`expected_shim_version`/`check_version` parameters so any caller can pin against
the binary it actually intends to run. `r0_ac1_ac2_replay.py` requires `--dll-sha256` and
constructs `Decoder(verify=True, expected_sha256=..., check_version=False)` — SHA is the identity
check; shim-version checking is deliberately off since this harness compares across shim versions
(20260038 vs 20260039) by design. Verified both branches: correct SHA → succeeds; wrong SHA →
`REFUSED`, exit 2.

## Housekeeping beyond the letter of tasks.md

- **`.gitignore`**: removed the `message.obj` carve-out (design.md's Open Question 2, "recommended
  yes") — `git rm --cached native/ft8_lib_build/obj/message.obj`. The binary patch it protected
  has no purpose once `message.c` compiles from vendored source every build (with the D-006 fix
  now restored at the source level, per Finding 1).
- **`BUILD.md`**: updated (it directly documents what this change touches). The "Submodule path:
  `native/ft8_lib/`" line was already false before this change (confirmed:
  `.gitmodules` is empty, `git submodule status` returns nothing — this is the same stale
  assumption `dependency-licence-policy`'s spec delta already corrects) — now describes the
  vendoring approach actually taken. Compiled-file list and Windows build-procedure section
  updated to match the real 11-step build; Linux/macOS sections untouched (CI clones from GitHub
  directly on those legs — out of scope, R0 is a Windows/`rebuild_shim.bat` change per the
  proposal's own Impact section).

## 6.1 — Build and tests

- **`dotnet build` (managed layer):** 0 warnings, 0 errors.
- **`dotnet test tests/OpenWSFZ.Ft8.Tests`:** **306/306 passed** — matches the G2(a) baseline
  exactly, on the new 20260039 DLL.
- **Native build:** **38 warnings** (6× C4244 float-narrowing, 9× C4267 size_t→int narrowing,
  23× C4996 deprecated-CRT-string-function), all in the 9 files that were never compiled under
  MSVC before this change (only linked as opaque pre-built objects, so these warnings were never
  visible, not newly introduced by anything in this change). **Zero C4013/C4047** among them —
  checked specifically, since that pair is the pointer-hazard class Finding 1 surfaced.
  **Honest tension with task 6.1's literal "0 warnings":** achieving zero would require either
  editing vendored source (violates "vendor as-is" — Risk section of design.md) or `/wd`-
  suppressing specific warning codes (masks rather than fixes, and wasn't asked for). Not done
  either way; reported as a finding for the Captain/Architect to rule on, not silently resolved.

## Observation: DLL file size grew 55,808 → 195,584 bytes (3.5x)

Checked rather than glossed over. `dumpbin /headers` shows the growth is in the code (`0x1F600`)
and data (`0x21200`) sections; the Debug Directory is only 28 bytes (standard PE
timestamp/CodeView entry, not embedded symbols) — so this is not a debug-info artifact. Most
likely explanation: the previous DLL linked 9 objects pre-built at some undocumented point in
May–June 2026 with unknown (and possibly lighter/different) compiler settings; this build
compiles all 11 units fresh and consistently at `/O2`, and the data-heavy files (`ldpc.c`'s
generator/parity tables, `message.c`'s ~1000 lines) inflate accordingly. **Not independently
proven — flagged as an observation, not asserted as the cause.** AC-1/AC-2's byte-identical
decode-output diff over 250 real cycles is the actual correctness gate here and it passed; file
size is not part of either acceptance criterion.

## Summary of every SHA referenced

| Binary | SHA256 | Shim |
|---|---|---|
| Pre-R0 shipped (G2(a)) | `c559a049d103c1f350f1a87b319033d5f8d1a2f91b74d9756d8d7cf03d2e6112` | 20260038 |
| Vendored build 1 (pre-bump) | `0a0e19494c5a6ff740a7c9889c912f6674610fbf4bf3ceccfc88318a9149871` | 20260038 |
| Vendored build 2 (pre-bump) | `024f8c37c9352a9bdb27b51a3a464aab817989fb927bfa7cfa163e60ff4a4ad` | 20260038 |
| **Final (this change ships)** | **`fa87bd9779c4dba831b792f5bc2608f29db875d7ce8d6c535f93e094b485e6b8`** | **20260039** |

## What's next

R0 is complete pending the Captain's review. Per the sequencing memo (2026-08-13 16:40Z), this
unblocks R1 (`spec-r1-sync-refiner-instrument-validation`), which follows R0 on the D-001 closing
path (R2 ← R1 ← R0). G2(b) stays PARKED, sequenced after R0, per the Captain's 2026-08-13 16:49Z
ruling. Not pushed, not merged, `pre_merge_check.py` not run.
