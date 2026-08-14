## Context

`native/ft8_lib_build/rebuild_shim.bat` links eleven object files but compiles only two
(`decode.c`, `ft8_shim.c`) from tracked source. The other nine — `constants.obj`, `crc.obj`,
`kiss_fft.obj`, `kiss_fftr.obj`, `ldpc.obj`, `text.obj`, `encode.obj`, `monitor.obj`,
`message.obj` — are pre-built `.obj` files dated 2026-05-29 through 2026-06-14, and only
`message.obj` is tracked in git. The nominal source tree lives outside version control entirely, at
`C:\Temp\ft8_lib_headers` (a clone of `github.com/frank001/ft8_lib`, `msvc-compat` branch, HEAD
`d18ed84f058290b36652f50db41875f2cafbaa4c`). Verified this session: `git status --short` on that
tree reports 123 modified paths, but `git diff --ignore-cr-at-eol` is empty — every reported
modification is CRLF/LF line-ending noise, not content drift. The tree is genuinely
content-identical to `d18ed84`, but that fact alone does not make the *shipped binary*
reconstructible, because the build cannot regenerate nine of its eleven inputs regardless of
whether the source tree they nominally came from still matches.

This blocks R1 and R2 (the next two specs in the D-001 sync-refinement programme, both editing
`decode.c`/`ft8_shim.c`) from linking new code against a build foundation anyone can independently
verify. It also means every already-published D-001 result (X1–X5, P1–P3, T1/T2, C.1, G2) is pinned
to a binary whose full provenance cannot currently be checked.

Separately, `openspec/specs/dependency-licence-policy/spec.md` already contains a requirement
("kgoba/ft8_lib submodule is enumerated and approved") that assumes `ft8_lib` was integrated as a
git submodule at `/native/ft8_lib/`. It was not: `.gitmodules` is empty and `git submodule status`
returns nothing. This design vendors the sources as plain committed files instead, which is both
what actually happened in practice for every other piece of this codebase's native dependency and
the simplest fix for the "cannot rebuild" problem — a submodule would still leave the *build script*
unable to regenerate the nine untracked objects, which is the actual defect.

## Goals / Non-Goals

**Goals:**
- Every one of the eleven linked translation units builds from source under version control, with
  zero pre-built `.obj` inputs.
- The rebuilt binary's *decode behaviour* is verified byte-identical to the currently-shipped
  `c559a049…`/20260038 binary — behaviour is the contract, not bit-identical DLL files (MSVC embeds
  a build timestamp that makes bitwise reproducibility unattainable without touching the toolchain).
- Close the pre-existing third-party-attribution gap (`THIRD-PARTY-NOTICES.md`) using the same
  vendoring work, since R0 is the first time the sources exist in a place a notices file can
  reference.
- Fix `p23_common.py:182`'s non-determinism, since R0's own AC-1/AC-2 depend on the replay harness
  actually being deterministic, and R1/R2 inherit the same dependency.

**Non-Goals:**
- No decoder behaviour change. `K_MAX_PASSES`, candidate caps, passband, OSR, LLR scaling are all
  untouched — if a vendored source file needs an edit to compile at all, that is a finding to
  report, not a change to fold in silently.
- Not converting the vendor tree into a git submodule. Vendoring (plain committed files) is simpler,
  matches the existing pattern for the two already-patched files (`native/ft8_lib_build/patched/`),
  and avoids the operational overhead of a submodule for a fork we do not intend to track upstream
  changes on.
- Not backfilling `ft8lib-interop`'s version-history prose for the undocumented shim bumps between
  `20260032` and `20260038`. Only the "current expected constant" is brought current, per HK-002's
  own distinction between an ongoing requirement (must track reality) and historical, feature-named
  requirements (permanent markers, not touched).
- Not proposing R1 or R2 here — each gets its own change proposal once R0 is implemented and merged.

## Decisions

**D1 — Vendor as plain files under `native/ft8_lib_vendor/`, not a git submodule.**
Alternatives considered: (a) a git submodule pointing at `frank001/ft8_lib`, matching the stale
`dependency-licence-policy` requirement's assumption; (b) vendoring, as chosen. A submodule adds a
second git history to track, a detached-HEAD checkout step in CI, and does not by itself solve the
actual defect (the build still needs to *compile* every file, submodule or not). Vendoring is
consistent with how the two already-patched files (`decode.c`, `monitor.c`) are already handled in
this repo, and is licence-clean since the upstream is MIT and the fork is the Captain's own.

**D2 — Byte-identical *decode output*, not byte-identical DLL, is the acceptance bar (AC-1/AC-2).**
MSVC embeds a PE COFF `TimeDateStamp` (and a Debug Directory mirror) that differs on every build
even from unmodified sources — confirmed by G2(a)'s own control rebuild, which differed from the
previously-shipped binary in exactly those 6 bytes and nowhere else. Requiring bitwise-identical
`.dll` files would make the acceptance criterion permanently unsatisfiable for reasons unrelated to
whether the build is actually correct. Decode behaviour (same decodes, same order, same
`freq_hz`/`dt`/SNR fields) is the real contract.

**D3 — AC-1 FAIL escalates; it is not a defect to patch until it passes.**
If the vendored-source build does *not* reproduce the shipped binary's behaviour, that is evidence
the shipped DLL does not correspond to its nominal source — a finding about every already-published
result pinned to that binary (X3 in particular), not merely a blocker for this change. The
Developer session must stop and escalate through QA/Architect rather than adjust vendored sources
until the diff disappears, which would launder the actual finding.

**D4 — Two independent build-script edits (D1+D2) land together, not the licence/tooling fixes.**
D1 (vendoring) and D2 (`rebuild_shim.bat` extension) are interdependent — the script's new compile
steps must point at wherever D1 actually lands the files — so they land as one unit. D3
(`p23_common.py` determinism fix) and D4 (`--assert-dll-sha`) are independent of the native build
itself and can land on their own schedule, though D3 must land before R2 starts (R2's spec already
depends on it). D5 (`THIRD-PARTY-NOTICES.md`) needs D1's vendored tree to scan for AC-4, so it
follows D1.

**D5 — Where the already-patched `decode.c`/`monitor.c` live is left as an implementation choice,
not mandated here.** Two reasonable placements (leave in `native/ft8_lib_build/patched/` as today,
or consolidate under the new vendor root) both satisfy this design's goals; forcing one in the
proposal stage would be deciding an implementation detail before the Developer session has looked
at how much churn each costs `rebuild_shim.bat`. Recorded as an Open Question below, to be answered
and documented (not silently picked) during implementation.

## Risks / Trade-offs

- **[Risk] AC-1 FAILs** — the shipped binary turns out not to correspond to its nominal source at
  all → **Mitigation:** this is treated as a first-class finding (D3 above), escalated immediately,
  not absorbed into this change. The spec's acceptance criteria evaluate both branches before
  running (PASS is expected; FAIL is fully actionable and arguably the higher-value outcome for the
  programme's overall trustworthiness).
- **[Risk] A transitively-needed header was missed** from the ~24-file list traced by `grep`-ing
  `#include` chains → **Mitigation:** the build itself is the check; a missing header surfaces as a
  named `cl.exe` compile error, which is the correct way to discover it, not a defect in this
  design.
- **[Risk] Vendoring "tidies" the source inadvertently** (line-ending normalisation, formatting,
  warning fixes applied while copying) → **Mitigation:** explicit instruction in the tasks to vendor
  as-is; AC-1's byte-identical check would itself catch behavioural drift, but formatting-only
  changes wouldn't necessarily be caught by AC-1 and are called out separately as prohibited.
- **[Trade-off] Vendoring duplicates ~24 files' worth of upstream source inside this repo** rather
  than referencing them via submodule. Accepted: the alternative doesn't solve the actual
  reproducibility defect (see D1), and the fork is small (~24 files, well under the 45 MB full
  upstream tree with tests/demo/`.git` excluded).

## Migration Plan

No runtime migration — this is a build-tooling and compliance change. Deployment is: merge to
`main`, next native rebuild uses the extended `rebuild_shim.bat`. Rollback is a plain `git revert`
of the vendoring + script-extension commit; the previously-shipped `c559a049…`/20260038 binary stays
valid and pinned in R1/R2's own specs regardless (those specs pin by SHA, not by build-process
identity).

## Open Questions

1. **Where do the already-patched `decode.c`/`monitor.c` end up?** (D5 above) — left to the
   Developer session, recorded in the PR description either way.
2. **Does the `native/ft8_lib_build/obj/message.obj` gitignore carve-out get removed** once D2 makes
   it redundant (the object becomes reproducible from vendored source, so tracking the pre-built
   binary loses its purpose)? Recommended yes, not mandated — a housekeeping call for the Developer
   session.
