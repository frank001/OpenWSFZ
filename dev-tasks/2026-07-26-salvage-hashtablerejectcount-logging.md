# Developer handoff: salvage `hashTableRejectCount` per-cycle logging from PR #108

**Authored by:** QA (per HK-000/HK-015). **Status:** ready for a Developer session.
**Source:** `qa/cycleframer-alignment-replay/2026-07-26-0100-architect-to-qa-land-housekeep-and-continue-d001.md`
Part B.2, endorsing `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §4's salvage list.

---

## 1. Why this exists, and why it's small on purpose

PR #108 (`docs/propose-fix-cycle-boundary-clock-drift`) is being closed unfixed — three live-tested
fix rounds for a `CycleFramer` drift-correction mechanism that turned out not to exist (see
`qa/cycleframer-alignment-replay/2026-07-25-2300-alignment-root-cause.md`: our framer holds σ = 59 ms
with zero dropped samples over 21 minutes, no accumulation). Closing it discards the branch and
everything uncommitted on it.

One committed diff on that branch is worth keeping regardless: **per-cycle `hashTableRejectCount`
logging in `Ft8Decoder.cs`.** `hashTableRejectCount` is a decoder-side counter (native
`g_session_hash_table` rejects), and D-001's live lead is now squarely a decoder problem — 98.5% of
the recall gap (`2026-07-26-0015-d001-consolidation-and-clean-slate.md` §1). This logging line will
be wanted for that thread's future live runs, so it should exist on `main` before D-001 work
continues, independent of PR #108's fate.

**Do not salvage anything else from that branch.** In particular, do *not* bring over the capture-gap
/ enqueue-latency telemetry (`WasapiAudioSource.cs`, `CaptureManager.cs` diffs) also present there —
the Architect recommended it on 2026-07-25 23:30 and explicitly withdrew the recommendation at 00:15:
it instruments the capture chain, which is now measured at 0.5% of the D-001 gap. Adding permanent
telemetry to a subsystem just proven innocent is exactly the reflex that produced PR #108's sprawl.

## 2. What to cherry-pick — exactly these two files, nothing else

Source branch: `docs/propose-fix-cycle-boundary-clock-drift` (currently `bd6b4e4`, PR #108, do not
push to it or otherwise touch it — QA/Captain own its closure separately).

| file | change |
|---|---|
| `src/OpenWSFZ.Ft8/Ft8Decoder.cs` | +19 lines, one new log call in `DecodeAsync` |
| `tests/OpenWSFZ.Ft8.Tests/HashTableRejectCountLoggingTests.cs` | new file, +141 lines |

Do this as a clean cherry-pick or manual re-application onto a fresh branch off current `main` —
**not** a merge or rebase of the PR #108 branch, which carries unrelated commits and the paused
`CycleFramer.cs`/`CycleFramerTests.cs` diff you must not bring over (§3).

### 2.1 The `Ft8Decoder.cs` change, verbatim

Inserted immediately after the existing per-cycle decode-elapsed-time log line in `DecodeAsync`
(around line 427 on `main` — confirm the exact anchor by searching for the `"Cycle {Time}: {Count}
decode(s) found, elapsed={Elapsed} ms."` log call and inserting directly after it, before the
D-003 noise-floor diagnostic block):

```csharp
// ── tasks.md 8.4 (fix-cycle-boundary-clock-drift): systematic hashTableRejectCount
// logging at a regular (once-per-cycle) cadence ──────────────────────────────────
// Prior to this, hashTableRejectCount (see GetHashTableRejectCount's doc comment) was
// only observable via ad hoc GET /api/v1/status polling. Logging it here, at the same
// per-cycle cadence and Information level as the elapsed-time line above, lets a raw
// daemon log reconstruct a session-long trend without needing ad hoc endpoint polling
// during the session. This is process-lifetime cumulative (GetHashTableRejectCount's
// own contract), not a per-cycle delta — logging it every cycle still lets a raw-log
// analysis compute cycle-over-cycle deltas or a whole-session trend.
_logger?.LogInformation(
    "Cycle {Time}: hashTableRejectCount={HashTableRejectCount} (process-lifetime cumulative).",
    timeStr, _interop.GetHashTableRejectCount());
```

The `tasks.md 8.4` reference in the comment is to the now-dead `fix-cycle-boundary-clock-drift`
change; leave the comment text as-is (it's accurate history of why the line was written) rather than
rewriting it to cite this handoff — the mechanism and log format are what matter, not the citation.

### 2.2 The test file

Copy `tests/OpenWSFZ.Ft8.Tests/HashTableRejectCountLoggingTests.cs` from the source branch verbatim.
It uses the existing `IFt8NativeInterop` injection seam (same pattern as `D005MessageTrimTests`), so
it does not load the native DLL and does not depend on `HashTableRejectCountTests`' real-shim
run-order constraints. Two tests: the log line fires with the right value at Information level, and a
zero count is logged explicitly (not suppressed as falsy).

## 3. Landmine — do not also bring the `CycleFramer.cs` diff

The source branch also carries an **uncommitted, HK-011-held diff** to `CycleFramer.cs` /
`CycleFramerTests.cs` (the paused attempt #4 drift-correction fix). It is not part of either file
above, was never committed to that branch's history as a clean commit, and must not come along for
the ride. If your diff touches `CycleFramer.cs` at all, stop — you have picked up more than these two
files.

## 4. Definition of done

- [ ] Exactly the two files in §2 added/modified on a fresh branch off current `main`.
- [ ] `git diff --stat` against `main` shows only those two files.
- [ ] `dotnet test tests/OpenWSFZ.Ft8.Tests` passes, including the two new
      `HashTableRejectCountLoggingTests` cases.
- [ ] `python3 tools/pre_merge_check.py` green (HK-006).
- [ ] Per HK-011: present the diff to the Captain for explicit pre-push sign-off. Per HK-010:
      `gh pr merge` always needs the Captain's explicit sign-off, green CI notwithstanding.
- [ ] Raised as its own small PR, **before** PR #108 is closed (so the two files are pulled from a
      still-live branch rather than a deleted one — cherry-picking from a closed PR's branch is still
      possible via the ref if the branch isn't deleted, but simpler to sequence this first).

## 5. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md` §4, §5.2
  — the salvage/withdraw decision this handoff implements.
- `qa/cycleframer-alignment-replay/2026-07-26-0100-architect-to-qa-land-housekeep-and-continue-d001.md`
  Part B.2 — the instruction this handoff was drafted from.
- `dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md` Evidence 5 — the
  original motivation for this logging (informal `/api/v1/status` polling that couldn't be
  reconciled against the raw log after the fact).
