# Developer handoff: R0 pre-merge gate — Linux and macOS native binaries are stale, need the standard refresh

**Authored by:** QA, 2026-08-14 (15:45 UTC, `date -u`, HK-017), per HK-000/HK-015.
**Follows:** the Captain's request to run `tools/pre_merge_check.py` against `feat/r0-reproducible-native-build` (`0b39805`), 2026-08-14.
**Status:** 🔴 **Proposal, not approved work in itself (HK-011).** A separate Developer session runs
`opsx:apply` (build + tests only — never `pre_merge_check.py` itself again unless re-verifying this
fix, that is HK-006, the Captain's initiative). The Captain reviews the diff before any push or
merge (HK-010/HK-014). QA does not declare readiness.

---

## 0. `pre_merge_check.py` result: **NOT READY** — one gate failed, ten passed

Run at the Captain's explicit request (HK-006). Full summary:

```
[PASS ] G9a — doc/VERSION consistency
[PASS ] G9b — mandatory VERSION bump on user-facing change
[PASS ] Solution build (Release)
[PASS ] Lint — UDP capture margin check
[PASS ] G10 — test-delay-synchronization lint
[PASS ] Full test suite (Release)
[PASS ] G3 — requirement traceability
[FAIL ] WSL Debian compile + test
[PASS ] G8 — OpenSpec strict validation
[PASS ] Self-contained non-AOT publish (local platform)
[PASS ] AOT publish (local platform)
```

**Everything that exercises the Windows DLL — which is what R0 actually changed — is clean.** The
one failure is scoped precisely, below, and it is not a defect in R0's actual diff.

---

## 1. Root cause — traced, not guessed

The WSL Debian leg's `dotnet test` failed with four real test failures, all with the identical
error:

```
System.InvalidOperationException : Native library ABI mismatch at
'.../OpenWSFZ.Web.Tests/bin/Release/net10.0/libft8.so'.
Expected FT8_SHIM_VERSION=20260039, got 20260033.
```

I confirmed this mechanically, not just from the stack trace — `tools/check_native_version.py`
against the two non-Windows committed binaries:

```
src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so     → STALE (does not contain 20260039)
src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib  → STALE (does not contain 20260039)
src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll      → OK (contains 20260039)
```

**R0 (`3bc2b9d`) and its follow-up (`0b39805`) bumped `FT8_SHIM_VERSION` to `20260039` and rebuilt
only the Windows DLL.** The Linux `.so` and macOS `.dylib` were never touched — they still carry
whatever the last "chore(native): rebuild Linux and macOS binaries to shim NNNNN" commit left them
at (`20260033`, per `git log`). This is exactly the same class of drift that's been fixed three
times before in this repo's history (`ec5bae0`, `1f595ed`, `6cdf92b`) — a fourth iteration is due,
for `20260039`.

### Important nuance — this probably will NOT fail real GitHub CI, but it's still wrong to ship

`.github/workflows/ci.yml`'s Linux and macOS legs **rebuild `libft8.so`/`libft8.dylib` fresh from a
live clone of `frank001/ft8_lib`** (overlaying the tracked patched `decode.c`) **before** `dotnet
test` runs — so the actual GitHub Actions run would very likely test against a freshly-built,
correctly-versioned binary regardless of what's committed. There's also a "Check committed .so/
.dylib is current" step (`continue-on-error: true` — non-blocking) that exists specifically to
flag this staleness; it would print a warning annotation on this PR, not fail it.

`pre_merge_check.py`'s WSL step does **not** replicate that fetch-and-rebuild step — it tests
directly against whatever's tracked in the repo, which is why it caught this locally as a hard
FAIL. **That's the tool doing its job, not a false alarm**: the underlying fact — two of the
three committed platform binaries are out of sync with the shim version they claim to implement —
is real, matches this project's own established practice of catching and fixing it, and should not
ship as-is even though real CI would likely paper over it by rebuilding from scratch.

---

## 2. The fix is real and verified — I built it myself before writing this

I did not just diagnose this and hand it over speculatively. In a scratch directory outside the
repo (nothing committed, nothing left in `git status`), using WSL Debian's `gcc` and the exact
compile/link recipe `ci.yml`'s "Build native Linux .so" step uses, built from the **already-tracked
vendored tree** (`native/ft8_lib_vendor/` + the patched `decode.c`/`monitor.c` + the current
`src/OpenWSFZ.Ft8/Native/ft8_shim.c`):

```
OBJ-BUILD-OK
SHIM-BUILD-OK
LINK-OK
<all eleven expected exports present, nm -D confirms>
Result : OK — binary contains shim version 20260039
```

Clean build, correct exports, correct version. **This is a small, mechanical fix**, the same shape
as the three prior "chore(native)" commits — not a redesign.

### One implementation choice for the Developer session to record (not mandated here)

- **(a)** Match the established pattern exactly: clone `frank001/ft8_lib` `msvc-compat` fresh (as
  `ci.yml` and the three prior chore commits do) and overlay the patched `decode.c`.
- **(b)** Build from the now-tracked `native/ft8_lib_vendor/` directly (what I used to verify
  above) — arguably more consistent with R0's own reproducibility goal, since it needs no live
  network fetch and is guaranteed content-identical to (a) by R0's own AC-1 proof.

Either is correct and produces the same object code. **Note which was chosen and why** — if (b),
that's worth a line in the commit message since it's a small, natural extension of R0's own
reproducibility argument to a second platform, even though R0's proposal explicitly scoped Linux/
macOS out (this doesn't reopen that scope — CI's fetch-based rebuild step is untouched either way,
this only concerns the *committed* binary).

**macOS `.dylib` needs the identical treatment but I have no macOS/clang toolchain available in
this environment to verify it the same way.** `ci.yml` lines 81–116 carry the exact recipe
(clang, `-target arm64-apple-macos11.0`, plus the `zero_dylib_uuid.py` determinism step). Rebuild
it on real macOS hardware or accept it stays stale until CI's own macOS runner naturally refreshes
it on a future PR — Captain's call if this blocks the current merge or is tracked separately.

---

## 3. What to do

1. Rebuild `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` to shim `20260039` (recipe above; pick
   (a) or (b) and say which).
2. Rebuild `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib` to shim `20260039`, if a macOS
   toolchain is available; otherwise flag it explicitly as still-stale and let the Captain decide
   whether that blocks this merge.
3. Verify both with `tools/check_native_version.py <path> 20260039` — expect `OK`, not `STALE`.
4. Re-run the WSL leg (or the full `pre_merge_check.py`) and confirm the four previously-failing
   tests now pass.
5. Commit as its own `chore(native): rebuild Linux and macOS binaries to shim 20260039` commit,
   matching the established message format — do not fold this into `0b39805` or `3bc2b9d`.

---

## 4. What NOT to do

🛑 No decode-behaviour change, same as R0 itself. This is strictly bringing two committed binaries
into version-sync with the shim version they already claim (per their own file, `ft8_shim.h`) to
implement — nothing else.

---

## 5. Definition of done

- [ ] `linux-x64/libft8.so` rebuilt; `check_native_version.py` reports `OK` for `20260039`
- [ ] `osx-arm64/libft8.dylib` rebuilt (or explicitly flagged as still-stale with the Captain's
      acknowledgement, if no macOS toolchain is available)
- [ ] WSL Debian leg (or full `pre_merge_check.py`) re-run; the four ABI-mismatch test failures
      are gone
- [ ] Committed as its own `chore(native)` commit, not folded into R0's own commits

🛑 **Then stop.** No push, no merge, no request for either (HK-010/HK-014). No further
`pre_merge_check.py` runs beyond re-verifying this specific fix (HK-006 — the Captain's
initiative). The Captain reviews the diff and decides on merge.
