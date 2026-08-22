# Developer session notes — fix-negative-time-offset-snr-collapse

## Branching

Per Captain's explicit direction (2026-08-22 Developer session): created
`fix/negative-time-offset-snr-collapse` from `feat/r2-coherent-llr-phase-b` HEAD,
carrying forward the uncommitted r2-coherent-llr-instrument Amendment 2/3 work
(shim `20260045`) already sitting in that branch's working tree. Plan: two separate
commits on this branch -- one for the pre-existing `20260045` work, one for this
change's own `20260046` fix -- rather than mixing both into a single commit.

## Binary rebuild (tasks 3.1-3.5)

- **win-x64** (`rebuild_shim.bat`, MSVC 19.44.35223): rebuilt clean, 0 errors.
  SHA256: `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`
- **linux-x64**: no git in the local WSL2 Debian environment, so instead of CI's
  `git clone frank001/ft8_lib` step, mirrored the same recipe using this repo's own
  `native/ft8_lib_vendor/` tree (already byte-identical to the `msvc-compat` branch's
  unpatched upstream sources per `PROVENANCE.md`), overlaying
  `native/ft8_lib_build/patched/{ft8/decode.c,common/monitor.c}` exactly as CI's clone
  + overlay step does. GCC 14.2.0 (Debian 14.2.0-19), 0 errors. All 16 `/EXPORT`-listed
  symbols present (plus `ft8_encode`, ELF's default-export-all-non-static behaviour,
  pre-existing).
  SHA256: `9394a8e3bf7578428f08ad71be95385f29605c3966e20d4b2e3b6a47c5267386`
- **osx-arm64**: **DEFERRED** by explicit Captain decision (no Mac available locally;
  the normal path is a one-shot `workflow_dispatch` GH Actions job requiring a push,
  which this Developer session does not do unprompted). The committed
  `osx-arm64/libft8.dylib` remains at its pre-this-fix version and is **not**
  shim-20260046-compatible. `ExpectedShimVersion` in `Ft8LibInterop.cs` is `20260046`
  regardless (matching the win/linux binaries), so a macOS build loading the stale
  dylib will fail the ABI self-test loudly (by design) rather than silently run
  stale code -- this is the existing, intended failure mode for a version mismatch,
  not a new gap introduced by this change. Follow-up: dispatch the CI workflow (or
  let `commit-native-binaries` catch it on next push) before this change is
  considered complete on macOS.

## Verification (§5): build/test

- `dotnet build -c Release`: clean, 0 warnings/errors. (First attempt blocked by an
  orphaned PID 37432 `OpenWSFZ.Daemon.exe` from a prior rr-study run, parent already
  dead -- true orphan per HK-019; killed it, cleared stale `rr_study_daemon.*` files.)
- `dotnet test -c Release`: 2 failures (`OpenWSFZ.E2E.Tests` banner timeout x2,
  `OpenWSFZ.Daemon.Tests` manifest-poll timeout x1), both confirmed parallel-run flakes
  by re-running each project in isolation (both pass clean). `OpenWSFZ.Ft8.Tests.dll`:
  317/317. G6 gate (`RealSignalFixtureTests`, NFR-016): 3/3 isolated.

## Section 6 (AC-N1 replay regression) -- STOPPED, escalated

Replayed the same window (WINDOW_20M, 250 cycles, start_index=0) against both fixed
binaries. Result: **85/250 cycles differ from the pre-fix reference, on BOTH
platforms, the same 85 cycles** -- but every single differing entry (95 per platform)
has a negative `dt`, zero diffs touch any `dt >= 0` entry, and every diff is SNR-only
(message/freq/dt unchanged). This is structurally what a correct fix should produce on
a corpus that (contrary to `proposal.md`'s stated premise) already contains negative-
`time_offset` decodes -- but `tasks.md` §6.2 is a pre-registered gate whose literal
stop condition fired, and reinterpreting a QA/Architect-authored gate's premise is not
this session's call. Asked the Captain; instructed to stop and escalate rather than
accept the evidence and proceed to §7.

**Full writeup:** `qa/rr-study/2026-08-22-1611-developer-to-architect-ac-n1-premise-false.md`
**Section 7 (B-dt-C3 acceptance re-run): NOT started.**

Output files (uncommitted QA artefacts, this session's own):
- `qa/rr-study/r2-coherent-llr-instrument/results/replay_win_negdt_fix.json`
- `qa/rr-study/r2-coherent-llr-instrument/results/replay_linux_negdt_fix.json`

## Commits: deliberately NOT made this session

Asked the Captain whether to make the two planned commits (20260045 Amendment 2/3, then
20260046 this fix) now or leave them uncommitted pending the escalation above. Captain's
answer: leave uncommitted. Everything (native fix, version bump, binary rebuilds, interop
update, this notes file, the escalation writeup, the QA replay outputs) remains as
working-tree changes on `fix/negative-time-offset-snr-collapse` -- nothing pushed,
nothing committed, matching how the pre-existing Amendment 2/3 work was already sitting.
Splitting the mixed diffs in `ft8_shim.c`/`ft8_shim.h`/`Ft8LibInterop.cs` into the two
planned commits (hunk-level separation of "already there before this session" vs "this
fix's own edit") is the first thing to do once the escalation resolves and commits are
wanted -- not yet attempted, to avoid a risky hand-split before the surrounding spec
wording (which may still change) is settled.
