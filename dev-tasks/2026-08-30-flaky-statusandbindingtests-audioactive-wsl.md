# Flaky test — `FR-020: GET /api/v1/status response includes audioActive boolean field`

**Date surfaced:** 2026-08-30, second `tools/pre_merge_check.py` run on the Captain's initiative
(HK-006), re-running to distinguish flake from regression on the first run's
`CycleArchiveServiceTests` failure (see
`dev-tasks/2026-08-30-flaky-cyclearchiveservicetests-manifestgapmarker-file-lock.md`). That earlier
failure did **not** reproduce — the Windows "Full test suite (Release)" gate passed clean this run,
confirming it as a flake, not a regression, per the Captain's own re-run. This document is a
**second, different** flake surfaced by the same re-run, on the **WSL Debian** gate rather than
Windows.

**Test:** `tests/OpenWSFZ.Web.Tests/StatusAndBindingTests.cs:122-136`
`StatusAndBindingTests.GetStatus_IncludesAudioActiveField` (`FR-020`)
**Owner area:** `OpenWSFZ.Web`'s `AudioActivityMonitor` / the `/api/v1/status` endpoint.
**Platform:** WSL Debian only — the Windows run of the same assembly (`OpenWSFZ.Web.Tests.dll`,
276/276) passed clean in both this run and the prior one; only the WSL execution failed.
**Policy:** TESTING_STRATEGY.md §11 (Flaky Test Policy), filed per item 1. **First observation** —
grepped the repo and found no prior doc, dev-task or commit naming this test or `audioActive`
flakiness (`dev-tasks/2026-07-06-f-005-status-endpoint-test-coverage.md` only documents the test's
original authoring, not a defect).

This branch (`qa/nbr-a-2026-08-29`) is docs/QA only — confirmed no `src/`, `native/` or `openspec/`
path in the diff vs `main` — and does not touch `AudioActivityMonitor`, `WebApp.cs`, `WebTestFactory`,
or this test.

## Symptom

```
Failed FR-020: GET /api/v1/status response includes audioActive boolean field [557 ms]
Error Message:
 Expected audioActiveProp.ValueKind to be JsonValueKind.False {value: 6} because no audio capture
 is running in tests so audioActive must be false, but found JsonValueKind.True {value: 5}.
   at StatusAndBindingTests.GetStatus_IncludesAudioActiveField() in
   .../StatusAndBindingTests.cs:line 134
```

1 of 276 in `OpenWSFZ.Web.Tests.dll` under WSL. The identical assembly passed 276/276 under Windows in
the same run.

## Root cause — plausible, not confirmed

`AudioActivityMonitor` (`src/OpenWSFZ.Web/AudioActivityMonitor.cs`) itself is simple and correct: a
`volatile bool _active`, default `false`, set `true` only by `ObserveSamples()` when a sample exceeds
the 1e-6f threshold. `IsActive` (read by `WebApp.cs:307/734/754`) returns that flag directly. A fresh
instance cannot start `true` on its own.

The test's `WebTestFactory` (`tests/OpenWSFZ.Web.Tests/WebTestFactory.cs:55-95`) runs the **real**
`Program.cs` startup via `WebApplicationFactory<Program>` and only substitutes `IConfigStore`,
`IFrequencyStore`, `IPropModeStore`, `IAdifLogWriter`, `ICatController` and `IAuthPolicy` with test
doubles — **nothing audio-related is stubbed out.** That means whatever real (or platform capture
stub) audio pipeline `Program.cs` wires up in the test host is live, and `AudioActivityMonitor`
receives whatever that pipeline actually produces. Two non-exclusive hypotheses, in order of how well
they fit "WSL-only, Windows-clean, first occurrence":

1. **Platform-dependent capture behaviour.** WSL Debian has no real WASAPI/audio hardware. Whatever
   fallback the capture path takes there (a null/dummy device, an ALSA stub, or an initialisation
   failure path) may feed `ObserveSamples()` a transient non-silent buffer that a real Windows
   audio device would not produce, or Windows's capture path may simply never start at all inside a
   TestServer host while a Linux fallback does.
2. **A singleton wider than this test's own `WebApplicationFactory` instance.** If the capture
   pipeline underneath `AudioActivityMonitor` holds any state outside the per-factory DI container
   (a process-wide static, a background thread started once and reused), a different test class
   elsewhere in the same `dotnet test` process — this suite has 1259 tests across 10 assemblies run
   together — could be the one actually driving activity, observed here rather than there.

Neither is confirmed; I have not instrumented a repro, and do not have `src/`/`tests/` write
authorization on this QA-only branch to do so (HK-011).

## Disposition

**Not resolved here, escalated per TESTING_STRATEGY.md §11 item 1**, same posture as the sibling
document filed minutes earlier for the unrelated `CycleArchiveServiceTests` flake. First occurrence —
§11 item 3's repeat-flake blocker threshold is not crossed by this document alone.

**Taken together with the sibling document:** two full `pre_merge_check.py` runs, two different
single-test failures, on an otherwise unrelated docs-only branch, with the first failure confirmed
non-reproducing on the second run. Neither individual test has repeated, so neither alone is a §11.3
blocker — but the pattern (a different test fails each full run) is itself worth the Architect's
attention as a question about the suite's overall flake rate at scale (1259 tests × 2 platforms),
separate from whether this specific branch may merge. Not asserted as a blocker here; reported for
that judgement.

## Cross-reference

- TESTING_STRATEGY.md §11 (Flaky Test Policy).
- `dev-tasks/2026-08-30-flaky-cyclearchiveservicetests-manifestgapmarker-file-lock.md` — the sibling
  flake from the first run of this same re-run sequence.
- `dev-tasks/2026-07-06-f-005-status-endpoint-test-coverage.md` — original authoring of this test.
- `qa/rr-study/2026-08-30-1204-architect-to-qa-TODO-pre-merge-nbr-a-branch.md` — the branch this
  `pre_merge_check.py` run was clearing for merge when this surfaced.
