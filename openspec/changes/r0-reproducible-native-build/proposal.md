**User-facing:** no

## Why

The shipped `libft8.dll` (currently `c559a049…`, shim `20260038`, following G2(a)'s merge) cannot
be rebuilt from its nominal source. `native/ft8_lib_build/rebuild_shim.bat` compiles only two of
eleven linked translation units (`decode.c`, `ft8_shim.c`); the other nine `.obj` files are
untracked build artefacts dated May–June 2026 with no recorded provenance, and only one
(`message.obj`) is even committed to git. Every decode-recall arm run so far (X1–X5, P1–P3, T1/T2,
C.1, G2) is pinned to a binary the project cannot independently reconstruct. R1 and R2 — the next
two specs in the D-001 sync-refinement programme — both modify `decode.c`/`ft8_shim.c` and would
link the new code against those same nine opaque objects, so a null result in R2 could be caused by
unreproducible build inputs rather than by the refinement change under test. Separately, the
repository ships **no** third-party attribution at all today (no `NOTICE`, `THIRD-PARTY`,
`COPYING`), which is a pre-existing, unrelated compliance gap that the same vendoring work is the
natural place to close.

This is also the first change in the D-001 statistics/build programme (running since 2026-07-25) to
go through OpenSpec — the Captain ruled 2026-08-13 that R0 onward should be governed this way after
QA found the intervening measurement arms and G2(a)/(b) had drifted to a dev-tasks-only process with
no `openspec/changes/` record at all (confirmed: PR #115 and G2 touched zero `openspec/` files).

## What Changes

- Vendor the native `ft8_lib` sources actually needed for the link (~24 `.c`/`.h` files, traced by
  include graph, not guessed) into version control under `native/ft8_lib_vendor/`, with mechanical
  provenance (upstream remote, HEAD SHA, a `git diff --ignore-cr-at-eol` proof of content identity).
  `ft4_ft8_public/` (Fortran, unused, no licence header) stays excluded.
- Extend `rebuild_shim.bat` to compile all eleven translation units from the vendored tree — no
  pre-built `.obj` may be linked. The exported symbol list is unchanged.
- Add a mechanical acceptance gate: a build from vendored sources must produce **byte-identical**
  decode output against the currently-shipped `c559a049…`/20260038 binary over a ≥200-cycle replay
  (AC-1), and two independent clean builds must agree with each other (AC-2). A FAIL on AC-1 is a
  stop-and-escalate finding about every already-published D-001 result pinned to that binary, not
  a defect to quietly patch around.
- Bump `FT8_SHIM_VERSION` to `20260039` for this change once the vendored build is verified
  behaviourally identical to `20260038` (AC-3) — a provenance/reproducibility marker, not a
  behaviour change.
- Add `THIRD-PARTY-NOTICES.md` at the repo root reproducing the MIT (`ft8_lib`) and BSD-3-Clause
  (KISS FFT) notices in full, and a mechanical scan asserting no vendored file is GPL/AGPL-licensed
  (AC-4). The two known WSJT-X-derived LDPC-table attribution comments in `ft8/constants.h`
  (lines 75/78) are Captain-ruled flagged-not-blocking and are expected AC-4 hits, not failures.
- Fix `qa/cycleframer-alignment-replay/p23_common.py:182`'s hash-randomised set iteration
  (`a.keys() & b.keys()` over string keys draws different indices per process even under a fixed
  seed) — R2's replay harness depends on this being genuinely deterministic, and P2/P3/P1a's
  "byte-identical across runs" claims were never actually verified for this reason.
- Add an `--assert-dll-sha` capability to the replay harness so every downstream run pins the
  binary it exercises by SHA256 and fails loudly on mismatch (the shim version integer alone is
  not a reliable identity — it has already collided twice, 20260034/20260035, across unmerged
  branches).

No decoder behaviour changes. No parameter change (`K_MAX_PASSES`, candidate caps, passband, OSR,
LLR scaling all untouched). If a vendored source file must be edited to compile at all, that is a
finding to report upward, not a change to make silently.

## Capabilities

### New Capabilities
- `native-build-provenance`: vendored native source tree under version control with recorded
  provenance, a rebuild script that builds every linked translation unit from that tree with no
  pre-built objects, and the byte-identical-behaviour + build-reproducibility acceptance gates
  (AC-1/AC-2) that make the shipped `libft8` binary independently reconstructible.

### Modified Capabilities
- `dependency-licence-policy`: the existing "kgoba/ft8_lib submodule is enumerated and approved"
  requirement describes a `/native/ft8_lib/` git submodule that was never actually created (`.gitmodules`
  is empty, `git submodule status` returns nothing) — the real dependency is a **vendored** tree
  (this change) of the `frank001/ft8_lib` fork (`msvc-compat` branch, not literally upstream
  `kgoba/ft8_lib`), and the licence-inventory tool's submodule enumerator does not and cannot cover
  it as currently written. This delta corrects the requirement to match the vendoring approach and
  adds the `THIRD-PARTY-NOTICES.md` obligation (MIT + BSD-3-Clause) this change introduces.
- `ft8lib-interop`: the "ABI self-test on first load" requirement's expected constant is stale
  (`20260031`, six versions behind the current shipped `20260038`) — this delta advances it to
  `20260039` for this change's own build. Catching up the requirement's version-history prose for
  the undocumented intermediate bumps (`20260032`–`20260038`) is explicitly **out of scope** here;
  flagged as a separate spec-sync backlog item, not fixed retroactively in this proposal.

## Impact

- **Affected code:** `native/ft8_lib_build/rebuild_shim.bat` (extended, not rewritten); new
  `native/ft8_lib_vendor/` directory (~24 files + `LICENSE`); `src/OpenWSFZ.Ft8/Native/ft8_shim.h`
  (version bump), `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` (`ExpectedShimVersion` bump); new
  `THIRD-PARTY-NOTICES.md` at repo root; `qa/cycleframer-alignment-replay/p23_common.py:182`;
  the replay harness used by R0's own AC-1/AC-2 and reused by R1/R2.
- **Downstream:** unblocks R1 (`spec-r1-sync-refiner-instrument-validation`) and R2
  (`spec-r2-refinement-in-decode-path`), both currently blocked on a trustworthy, reproducible
  build foundation. Each will get its own OpenSpec change proposal, not bundled into this one.
- **No `openspec/specs/` behavioural requirement for `ft8-decoder` changes** — this is a build/
  provenance/compliance change, not a decode-behaviour change (explicitly out of scope, see `What
  Changes`).
