## 1. Vendor the native sources (D1)

- [x] 1.1 Trace the include graph from the nine untracked linked objects and confirm the file list
      in `specs/native-build-provenance/spec.md`'s "Vendored native source tree" requirement is
      complete (re-derive by attempting the build in §2, not by trusting this list blindly — a
      missed transitive header surfaces as a named `cl.exe` error).
      **Done:** traced every `#include` reachable from `decode.c`/`monitor.c`/`ft8_shim.c`; matches
      the spec's minimum list exactly (22 files), confirmed by the clean build in §2 succeeding.
- [x] 1.2 Copy the confirmed file list from `C:\Temp\ft8_lib_headers` into `native/ft8_lib_vendor/`
      (or a chosen alternative name — record whichever is used), verbatim, including the upstream
      `LICENSE`. No reformatting, no line-ending normalisation, no warning fixes.
      **Done:** `native/ft8_lib_vendor/`, byte-for-byte `cmp`'d against source, zero mismatches.
- [x] 1.3 Exclude `ft4_ft8_public/`, `demo/`, `test/`, `utils/`, `Makefile`, `README.md`,
      `.clang-format`, `.gitignore`, `.git/` from the vendored copy.
      **Done:** only the 22 confirmed files + `LICENSE` were ever copied.
- [x] 1.4 Record provenance mechanically: upstream remote URL, HEAD SHA
      (`d18ed84f058290b36652f50db41875f2cafbaa4c`), and the `git diff --ignore-cr-at-eol` command +
      output run against that HEAD (expected empty) — re-run it yourself, don't copy a prior run's
      output.
      **Done:** `native/ft8_lib_vendor/PROVENANCE.md`; diff re-run independently, 0 bytes, exit 0.
- [x] 1.5 Decide and record where the already-tracked, MSVC-patched `decode.c`/`monitor.c`
      (currently at `native/ft8_lib_build/patched/`) live relative to the new vendor directory —
      leave in place or consolidate (design.md's Open Question 1). Either is acceptable; state
      which was chosen and why in the PR description.
      **Decided: left in place.** Keeps the vendored tree byte-identical to upstream (its whole
      provenance guarantee); minimal churn to a script already correctly pointing there. Recorded
      in `PROVENANCE.md` and `BUILD.md`.
- [x] 1.6 Report the total committed size of the vendored tree.
      **159 KB, 22 files, 115,705 bytes** — see `PROVENANCE.md` and the QA report.

## 2. Extend the rebuild script (D2)

- [x] 2.1 Add `cl` compile steps to `native/ft8_lib_build/rebuild_shim.bat` for the nine
      currently-linked-not-built objects (`constants`, `crc`, `kiss_fft`, `kiss_fftr`, `ldpc`,
      `text`, `encode`, `monitor`, `message`), pointing at the vendored tree via `/I`, ahead of the
      existing `decode.c`/`ft8_shim.c` compile steps and the `link` step.
      **Done.** Also added an `obj\*.obj` clear-before-build step (spec requires starting from
      empty `obj/`) and repointed `decode.c`/`ft8_shim.c`'s `/I` flags off `C:\Temp\...` onto the
      vendored tree.
- [x] 2.2 Confirm the `link` step's `/EXPORT:` list is unchanged (eleven symbols) and every object
      it references was produced earlier in the same script invocation.
      **Confirmed via `dumpbin /exports`** on the built DLL: exactly the same eleven symbols.
- [x] 2.3 Run a clean build from an empty `obj/` directory. If any vendored source file needs an
      edit to compile, STOP and report it as a finding — do not edit silently and continue.
      **Ran three independent clean builds, all succeeded.** One finding surfaced and escalated to
      the Captain before proceeding (not silently patched) — see the QA report: `ft8/message.c`
      calls `stpcpy()` with no MSVC prototype in scope, mechanically confirmed (C4013/C4047, then
      disassembly) to reproduce D-006's exact root cause. Fixed via a build-side-only `/FI`
      compat header (`native/ft8_lib_build/patched/stpcpy_msvc_compat.h`) per the Captain's ruling
      — **zero bytes of the vendored tree were edited.**

## 3. Behavioural and reproducibility verification (AC-1, AC-2, AC-3)

- [x] 3.1 Replay ≥200 contiguous cycles from the pinned 20m corpus
      (`artefacts/20260808_live_run_0016-8080/`) through both the vendored-source DLL and the
      pinned `c559a049…`/20260038 DLL, same input, same parameters, same order. Record the exact
      cycle range used.
      **250 cycles, `260808_004000`..`260808_014215`** (new `qa/cycleframer-alignment-replay/
      r0_ac1_ac2_replay.py`, reusing `p23_common.py`'s production preprocessing/decode pipeline).
- [x] 3.2 Mechanically diff the two runs' serialised decode output (never an eyeballed summary or a
      count-of-decodes match). Report the diff command and its exit status.
      **`r0_ac1_ac2_diff.py baseline_output.json build1_output.json` → exit 0.**
- [x] 3.3 **Evaluate the result honestly against both pre-registered branches:** PASS (zero
      differences) ⇒ proceed to 3.4. FAIL (any difference) ⇒ STOP, do not adjust vendored sources to
      force a match, and escalate through QA to the Architect/Captain immediately — this is a
      finding about every already-published D-001 result pinned to the shipped binary, not merely a
      blocker for this task.
      **PASS — zero differences across 250 cycles.**
- [x] 3.4 Run two independent clean builds (each from an empty `obj/` directory) and mechanically
      diff their decode output against each other over the same corpus subset (AC-2). DLL files
      themselves are not required to match bit-for-bit.
      **PASS — zero differences.** DLL SHAs differ (`0a0e1949...` vs `024f8c37...`, PE timestamp
      only, per D2's design decision); decode output is byte-identical.
- [x] 3.5 Bump `FT8_SHIM_VERSION` (`src/OpenWSFZ.Ft8/Native/ft8_shim.h`) and `ExpectedShimVersion`
      (`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`) to `20260039`, in the same commit as the
      verified-passing build. Record the new DLL's SHA256.
      **Done.** New DLL SHA256: `fa87bd9779c4dba831b792f5bc2608f29db875d7ce8d6c535f93e094b485e6b8`.
      ABI self-test confirmed (`ft8_lib_version_check() == 20260039`). Re-diffed against the
      pre-bump build: zero differences (the version bump alone changes no decode behaviour).

## 4. Licence compliance (D5, AC-4)

- [x] 4.1 Write `THIRD-PARTY-NOTICES.md` at the repo root: MIT text with Kārlis Goba's copyright,
      BSD-3-Clause text with Mark Borgerding's copyright (reproduced in full, not by reference to a
      `COPYING` file that doesn't exist in the vendored `fft/` directory).
      **Done** — `THIRD-PARTY-NOTICES.md` at repo root.
- [x] 4.2 Scan the vendored tree for `GNU General Public`, `GPL`, `Affero`. Report every hit with
      file and line. Confirm the only hits are the two expected `ft8/constants.h` lines 75/78
      (WSJT-X LDPC-table attribution comments) — do **not** delete those comments if found; they are
      the only record of that provenance.
      **Scanned (case-insensitive too): ZERO hits, cleaner than the spec anticipated** — the two
      WSJT-X attribution comments at `constants.h:75,78` (confirmed present, unremoved) say only
      "From WSJT-X's ..." and don't contain the literal search strings. See `PROVENANCE.md`.
- [x] 4.3 Confirm every vendored source file's own licence header is present and unmodified.
      **Confirmed via the byte-for-byte `cmp` in 1.2 — headers are untouched by construction.**
- [x] 4.4 Confirm `ft4_ft8_public/` is absent from the vendored tree (should already hold from 1.3).
      **Confirmed.**

## 5. Replay-harness determinism and pinning (D3, D4)

- [x] 5.1 Fix `qa/cycleframer-alignment-replay/p23_common.py:182`'s hash-randomised set iteration
      (`a.keys() & b.keys()`) by sorting at construction — match the fix pattern already used in
      `x4_spectral_locality.py`/`x3_lattice_crowding.py`, don't re-derive a new one. This must land
      before R2 starts; R0's own AC-1/AC-2 in §3 above also depend on it being genuinely
      deterministic.
      **Done** — `sorted(a.keys() & b.keys())`, same pattern as x3/x4.
- [x] 5.2 Check whether `p23_common.py` or `g2_verification_replay.py` already has a DLL-SHA-pinning
      capability before adding a new one. Add `--assert-dll-sha` (or extend what exists) so a replay
      run fails loudly on a SHA mismatch rather than silently running whatever binary is on disk.
      **Checked: `p23_common.py`'s `Decoder` class already has one, narrowly hard-coded to a single
      (currently stale) module-level SHA.** `g2_verification_replay.py` doesn't exist on `main`
      (unmerged G2(b) branch). Extended `Decoder.__init__` with `expected_sha256`/
      `expected_shim_version`/`check_version` parameters so any caller can pin against the binary
      it actually intends to run, not just the module's one hard-coded pin.
- [x] 5.3 Wire the new pinning capability into the AC-1/AC-2 replay itself so those two runs
      self-verify which binaries they actually compared.
      **Done** — `r0_ac1_ac2_replay.py` requires `--dll-sha256`, constructs `Decoder` with
      `verify=True, expected_sha256=..., check_version=False` (SHA is the identity check; the
      shim-version check is deliberately off since this harness compares across shim versions by
      design). Verified both branches: correct SHA → succeeds; wrong SHA → refuses, exit 2.

## 6. Wrap-up

- [x] 6.1 Build clean (0 warnings), full `OpenWSFZ.Ft8.Tests` suite green (baseline: 306/306 on the
      G2(a) build — re-verify, don't assume it stays 306 after this change).
      **`dotnet build` (managed): 0 warnings, 0 errors. `dotnet test`: 306/306 passed** on the new
      20260039 DLL — matches the G2(a) baseline exactly. **Native build: 38 warnings** (C4244/
      C4267/C4996 — float/size_t narrowing, deprecated CRT string functions), all newly *visible*
      rather than newly *introduced*: they're pre-existing in the 9 files that were never compiled
      under MSVC before this change (only linked as opaque pre-built `.obj`s). Zero C4013/C4047
      (the pointer-hazard class) among them — checked specifically. Reported as a finding, not
      silently suppressed via `/wd` or fixed by editing vendored source (would violate "vendor
      as-is"); see the QA report for the honest tension against this task's literal "0 warnings."
- [x] 6.2 Write the QA→Architect report per the proposal's reporting requirements: upstream remote +
      HEAD SHA + content-identity diff output; old and new DLL SHA256 + shim integer; AC-1 cycle
      range, diff command, exit status; AC-4 scan output in full; committed vendored size; for any
      AC-1 FAIL, which decodes differ and how, before any diagnosis.
      **Done** — see `qa/cycleframer-alignment-replay/2026-08-14-*-r0-developer-to-qa-report.md`.
- [x] 6.3 Stop. No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006) — the Captain
      reviews the diff and decides on merge; this task does not declare readiness unprompted.
      **Stopping here.** Nothing pushed, nothing merged, `pre_merge_check.py` not run.
