# Developer handoff: rebuild the stale `linux-x64/libft8.so` (D-001 C.2 Phase 2c follow-up)

**Authored by:** QA (per HK-000/HK-015), following up on the Phase 2c shrinkage-trial-and-BER
session's own findings doc, whose last DoD item (`pre_merge_check.py`) was left correctly unchecked
and deferred to QA per today's HK-006 correction.
**Branch:** continue on the current branch, `d001-c4-min-score-sweep` — per this thread's own
established convention (stated explicitly in the Phase 2c findings doc §0) of stacking each D-001
phase onto the same feature branch rather than opening a fresh one per session. Do not branch off.
**Status:** small, mechanical, single-artifact fix. No logic change, no new exports, nothing beyond
rebuilding one binary and (optionally) its provenance note.

---

## 1. Context — what's broken and why

QA ran `python3 tools/pre_merge_check.py` (now QA's own step, not the Developer's — see the
2026-07-26 HK-006/HK-011 addenda) against the Phase 2c diff and got:

```
[PASS ] G9a, G9b, Solution build, Lint, G10, Full test suite (Release), G3, G8,
        Self-contained non-AOT publish, AOT publish
[FAIL ] WSL Debian compile + test
Result : NOT READY — at least one gate failed.
```

**Every gate is green except one.** The WSL Debian leg fails because
`src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` still reports `FT8_SHIM_VERSION=20260034`, while the
managed code (`Ft8LibInterop.ExpectedShimVersion`) now correctly expects `20260035` (this session's
own shim bump — see `libft8.version.txt`'s current top entry). Every WSL-side test that touches the
Ft8 native library throws `System.InvalidOperationException: Native library ABI mismatch...` at
startup, which cascades into ~500 further `OpenWSFZ.Daemon.Tests` failures (their state machines
never see a decode, so they sit at `Idle` waiting for a `WaitReport` transition that never arrives,
and time out one by one). One root cause, not many.

**This is not a logic defect in Phase 2c's work.** `git diff --stat` shows the `.so` *did* change
size this session (67232→67488 bytes), so it was rebuilt at some point — almost certainly before
the shim version got bumped from 34→35, with the session interrupted (per the Captain's own
account) before a final Linux-side rebuild could catch up. The Windows `.dll` got that final
rebuild correctly (Windows leg is 100% green, 297/297 `OpenWSFZ.Ft8.Tests` included) — the Linux
`.so` didn't.

**This exact defect class has happened before in this thread**, per `libft8.version.txt`'s own
"--- Linux x64 ---" section (untouched by this session — that's the tell): the 2026-07-26 D-001 C.4
entry records `pre_merge_check.py`'s WSL gate failing the same way, fixed the same way, with an
honest note that CI itself would have self-healed regardless (it always rebuilds `libft8.so` from
current source on every push — `.github/workflows/ci.yml`'s "Build native Linux .so" step) but
that the local gate still needed a real binary, not a wave-off. Same situation, same fix, one
version later.

## 2. Actions

1. **Rebuild the Linux `.so` under WSL2 Debian using the existing script — do not hand-roll GCC
   commands.** `native/ft8_lib_build/build_linux.sh` already compiles from the correct current
   sources (`native/ft8_lib_build/patched/ft8/decode.c` + `src/OpenWSFZ.Ft8/Native/ft8_shim.c`,
   both already carrying this session's Phase 2c changes and the version bump to 20260035) and
   copies the result into `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`:
   ```
   wsl -d Debian -- bash -c "cd '<wslpath-to-repo>' && ./native/ft8_lib_build/build_linux.sh"
   ```
2. **Verify the rebuilt binary reports the correct version** before trusting it —
   `tools/check_native_version.py` is the same tool CI's own staleness check uses:
   ```
   python3 tools/check_native_version.py src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so 20260035
   ```
3. **Confirm the diff is surgical.** `git status`/`git diff --stat` should show exactly one changed
   file — `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` — beyond what Phase 2c already committed.
   Nothing else in the working tree should move as a byproduct of this step.
4. **Local verification only — build and test, do not run `pre_merge_check.py` yourself.** Per
   today's standing correction (HK-006/HK-011): that gate is QA's own review step now, not part of
   the Developer session's checklist. A reasonable local check for this specific fix, inside WSL:
   ```
   wsl -d Debian -- bash -c "cd '<wslpath-to-repo>' && /home/<user>/.dotnet/dotnet build OpenWSFZ.slnx -c Release && /home/<user>/.dotnet/dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --no-build"
   ```
   (absolute `dotnet` path per HK-006's own documented `PATH` gotcha for non-interactive
   `wsl -- bash -c` invocations — `PATH` doesn't reliably carry it in). Confirm the ABI-mismatch
   exception is gone and `OpenWSFZ.Ft8.Tests` passes; you do not need to run the full Daemon/Web
   suites locally under WSL for this narrow fix, but doing so is not wrong either if you want extra
   confidence.
5. **Update `libft8.version.txt`'s "--- Linux x64 ---" section** to record the rebuild, mirroring
   the existing entries' style (compiler/flags unchanged; update `Build date` to today, note the
   shim version now matches 20260035, and reference this dev-task). This section is currently still
   describing the C.4-era rebuild that brought it to 20260034 — it never got touched by the Phase
   2c session, which is the paper-trail confirmation of what went wrong.
6. **Do not touch anything else.** No logic changes, no new exports, no changes to the Windows
   binary, no changes to `ft8_shim.c`/`decode.c` source. If you find yourself editing C source to
   make this work, stop — that means the actual defect is different from what's diagnosed here, and
   it should come back to QA before proceeding.

## 3. Acceptance criteria (what QA will check)

- [ ] `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` reports `FT8_SHIM_VERSION=20260035` via
      `tools/check_native_version.py`.
- [ ] `git diff --stat` shows only the `.so` binary and (if done) `libft8.version.txt` changed —
      nothing else.
- [ ] Local WSL build + `OpenWSFZ.Ft8.Tests` run clean, no ABI-mismatch exception.
- [ ] `libft8.version.txt`'s Linux section updated (build date, version, this dev-task reference) —
      optional but preferred, matching the existing provenance discipline used everywhere else in
      this file.
- [ ] Nothing else in the working tree touched.
- [ ] **Not on this checklist, deliberately:** running `pre_merge_check.py`. QA re-runs the full
      gate suite after this lands and will report the result.

## 4. References

- `qa/cycleframer-alignment-replay/2026-07-26-c2-phase2c-shrinkage-trial-and-ber-findings.md` — the
  session this follows up on; its own DoD correctly left `pre_merge_check.py` unchecked and
  deferred it to QA.
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` lines 121–134 — the Linux provenance section,
  showing this exact defect class occurring once already in this thread (D-001 C.4) and how it was
  resolved.
- `native/ft8_lib_build/build_linux.sh` — the existing, already-correct rebuild script; use it
  as-is, don't hand-roll the GCC invocation.
- `tools/check_native_version.py` — the version-verification tool, same one CI's own staleness
  check (`ci.yml`, "Check committed Linux .so is current" step) uses.
- `.github/workflows/ci.yml` lines 166–210 — confirms real CI rebuilds `libft8.so` from source on
  every push regardless (so this specific failure would not have broken CI), and that the staleness
  check is `continue-on-error: true` there. Recorded for context, not as a reason to skip this fix.
- `src/OpenWSFZ.Ft8/Native/BUILD.md` — the general Linux build procedure section, for background;
  `build_linux.sh` is the concrete, already-working instantiation of it for this repo.

---

*Per HK-011, this is `src/`-adjacent native rebuild work — stays in a Developer session, diff
reviewed by QA, Captain sign-off before push. Per HK-014/HK-015 convention applied to Developer
sessions in this thread, nothing is pushed or merged from here; hand the diff back to QA when done.*
