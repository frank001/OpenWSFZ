# Developer handoff: R0 code review follow-up — silence the native `LOG_INFO` stderr spam; two items need the Captain's ruling

**Authored by:** QA, 2026-08-14 (15:04 UTC, `date -u`, HK-017), per HK-000/HK-015.
**Follows:** the QA code review of `feat/r0-reproducible-native-build` (`3bc2b9d`), 2026-08-14.
**Status:** 🔴 **Proposal, not approved work in itself (HK-011).** A separate Developer session runs
`opsx:apply` (build + tests only — never `pre_merge_check.py`, that is HK-006, the Captain's
initiative alone). The Captain reviews the diff before any push or merge (HK-010/HK-014). QA does
not declare readiness.

**Scope of this document:** ONE fix (§1), plus two items surfaced honestly in the Developer's own
report that still need an explicit ruling before R0 is called finished (§2). Everything else in
`3bc2b9d` was independently re-verified by QA (re-cloned upstream, diffed all 22 vendored files
byte-for-byte, re-ran the GPL scan, confirmed the DLL SHA on disk, traced the `stpcpy` fix to its
real definition) and needs no further work. This is a small follow-up, not a re-implementation.

---

## 1. 🔴 Fix — `monitor_init()` now writes 4 unstructured lines to `stderr` on *every* decode cycle, and `stderr` is the daemon's entire structured log channel

### What's actually happening

`native/ft8_lib_build/patched/common/monitor.c:4` has carried `#define LOG_LEVEL LOG_INFO` since
its very first port commit. It never fired in production because `monitor.c` was never actually
compiled — the shipped `monitor.obj` was a stale pre-built object. R0 makes it compile for real,
so it now fires.

`monitor_init()` is called from `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1231`, **unconditionally, at
the top of every single `ft8_decode_all` invocation** — not once at process startup. Each call
prints, via `fprintf(stderr, ...)` (see `ft8/debug.h`'s `LOG_PRINTF` macro):

```
Block size = ...
Subblock size = ...
N_FFT = ...
N_iFFT = ...
```

Separately, `src/OpenWSFZ.Daemon/Logging/StderrLoggerProvider.cs` writes the daemon's **entire**
structured application log to `stderr`, in the house format (FR-019):

```
[OpenWSFZ] YYYY-MM-DD HH:MM:SS [LEVEL]  ComponentName — message
```

Put together: a 24/7 daemon decoding roughly every 15 seconds will now interleave four raw,
unstructured native lines into that same stream, on every cycle, forever. This is a permanent
change to production log output that did not exist before this change — not a one-off curiosity.
It is a different question from "does it touch `FT8Result`" (it doesn't — AC-1/AC-2 are correctly
unaffected, decode correctness is not in question here).

The Developer's own report (`qa/cycleframer-alignment-replay/2026-08-14-1452-r0-developer-to-qa-report.md`,
"Finding 2") correctly *found* this and correctly reasoned about its cause, but classified it
**"informational, no fix needed"** on the grounds that it doesn't touch decode output. That's true
for AC-1/AC-2, but the classification stops one step short: it doesn't ask where the daemon's
`stderr` goes, which is the actual question that determines whether this is fine to ship.

### The fix

`native/ft8_lib_build/patched/common/monitor.c` is the **already-patched, already-tracked** file
(MSVC VLA compat patches), not a member of the byte-identical vendored tree at
`native/ft8_lib_vendor/`. Editing it does **not** violate this change's "vendor as-is" guarantee —
that constraint is scoped to `native/ft8_lib_vendor/` only, and this file has never been part of
it.

Remove or raise `monitor.c:4`'s `#define LOG_LEVEL LOG_INFO`. Two acceptable options — pick one
and say which, and why, in the commit message:

- **(a) Undefine it entirely.** `ft8/debug.h`'s `#else` branch (no `LOG_LEVEL` defined) expands
  `LOG(...)` to nothing at every call site, at every level, including a future `LOG_WARN`/
  `LOG_ERROR`/`LOG_FATAL` call if one is ever added upstream. Simplest, but silently drops any
  future genuine warning too.
- **(b) Raise it above the levels actually used.** `monitor.c` only ever calls `LOG_DEBUG` (2
  sites) and `LOG_INFO` (4 sites) — grep confirms zero `LOG_WARN`/`LOG_ERROR`/`LOG_FATAL` call
  sites in this file today. Setting `#define LOG_LEVEL LOG_WARN` silences exactly today's noisy
  calls while leaving the `LOG()` mechanism live for any future `LOG_WARN`-or-above diagnostic.
  **Recommended** — it is the smaller behavioural change and doesn't discard a mechanism that
  exists for a reason.

Either way:
- Do not touch `native/ft8_lib_vendor/ft8/debug.h` (it is genuinely vendored, upstream-unmodified,
  and correct as-is — the bug is `monitor.c`'s own `#define`, not the macro machinery).
- Rebuild via `rebuild_shim.bat` and confirm the DLL SHA changes (it must — this is a real, if
  tiny, code change to a compiled file) and record the new SHA.
- **Re-run AC-1/AC-2** (`qa/cycleframer-alignment-replay/r0_ac1_ac2_replay.py` +
  `r0_ac1_ac2_diff.py`) against the same 250-cycle range
  (`260808_004000`..`260808_014215`) used in the original session. Expect **zero decode-output
  differences** — this fix touches only what gets printed to `stderr`, nothing in `FT8Result`.
  If AC-1/AC-2 show *any* difference, stop and report — that would mean the log-level change
  somehow perturbed decode behaviour, which would itself be a new, more serious finding.
- Confirm by inspection (or a quick manual decode-and-watch) that `stderr` is quiet on a normal
  decode cycle after the fix.
- Bump `FT8_SHIM_VERSION`/`ExpectedShimVersion` again if the Captain wants a fresh version marker
  for this follow-up, or fold it into the same `20260039` if this lands before that commit is
  otherwise finalised — Captain's call, note which was done.

---

## 2. Two items already honestly disclosed in the Developer's report — need the Captain's explicit ruling, not a silent pass

These are **not** defects to fix unprompted. QA is flagging them so they get an explicit decision
rather than being treated as "done" by default because the report mentioned them.

### 2.1 Task 6.1's literal "0 warnings" bar is unmet for the native build

`dotnet build` (managed layer): 0 warnings — met. **Native build: 38 warnings** (C4244/C4267/
C4996 — float/size_t narrowing, deprecated CRT string functions), all in the 9 files that were
never compiled under MSVC before this change and were therefore never visible, not newly
introduced. Zero C4013/C4047 (the pointer-hazard class Finding 1 was about) among them —
correctly checked specifically.

The report is honest about this tension and correctly did **not** silently suppress it via `/wd`
or fix it by editing vendored source (either would be worse than leaving it visible). This needs
the Captain (or Architect, if delegated) to explicitly accept 38 warnings as the new native-build
baseline, or to instruct otherwise. **No code change requested here** — this is a ruling, not a
task.

### 2.2 `dependency-licence-policy` spec scenario text doesn't match the measured result

`openspec/changes/r0-reproducible-native-build/specs/dependency-licence-policy/spec.md`'s new
scenario "GPL/AGPL scan finds only the two expected, flagged hits" states the scan's only hits
SHALL be the two WSJT-X-attribution lines at `constants.h:75,78`. The actual scan (`grep -rin
"gnu general public\|\bgpl\b|affero"`, QA independently re-ran it, same result) finds **zero**
hits total — the attribution comments say "From WSJT-X's ..." and don't contain the literal
strings the scan searches for, so they were never going to register as hits under this scan in
the first place.

`PROVENANCE.md` and the QA report both state this honestly ("cleaner than the spec's
pre-registered scenario anticipated"). The spec text itself still describes the anticipated,
not-actual, scenario. **Recommended fix:** correct the scenario wording in
`specs/dependency-licence-policy/spec.md` before this change is archived, so a future reader
doesn't read "the only hits SHALL be the two lines" and expect two hits as the normal, healthy
case, when the actually-observed healthy case is zero. Small edit, no code change, no re-run
required — just correct the prose to match what AC-4 actually measured.

---

## 3. What NOT to do

🛑 No other change. Everything else in `3bc2b9d` — the vendored tree, `rebuild_shim.bat`, the
`stpcpy` compat header, the AC-1/AC-2 replay harness, `p23_common.py`'s determinism fix and
DLL-SHA-pinning extension, `THIRD-PARTY-NOTICES.md`, `BUILD.md` — was independently re-verified by
QA against the actual upstream repository (not merely re-read) and needs no rework. Do not
re-derive or "improve" any of it as part of this follow-up.

---

## 4. Definition of done

- [ ] §1: `monitor.c`'s `LOG_LEVEL` lowered/removed (state which option and why in the commit
      message); DLL rebuilt; new SHA recorded
- [ ] §1: AC-1/AC-2 re-run on the same 250-cycle range; zero decode-output differences confirmed
      (not assumed)
- [ ] §1: `stderr` confirmed quiet on a normal decode cycle after the fix
- [ ] §2.1: Captain's ruling obtained and recorded (accept 38 native warnings as baseline, or
      other instruction) — no code change unless the ruling asks for one
- [ ] §2.2: spec scenario text corrected to match the measured zero-hit result
- [ ] Build clean (managed layer); full `OpenWSFZ.Ft8.Tests` suite green; report the count
      (currently 306/306 on the `20260039` DLL — re-verify, don't assume it stays 306)

🛑 **Then stop.** No push, no merge, no request for either (HK-010/HK-014). No
`pre_merge_check.py` (HK-006). The Captain reviews the diff and decides on merge; QA does not
declare readiness unprompted.
