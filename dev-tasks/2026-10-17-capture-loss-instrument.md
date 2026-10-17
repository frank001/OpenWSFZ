# Capture-loss instrument: make lost audio visible on the Linux capture path (no behaviour change)

**Date:** 2026-10-17
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the Captain, 2026-10-17, Architect's window: "spec it for qa" (instrument first, before any fix). Spec: `qa/rr-study/2026-10-17-0927-architect-to-qa-spec-capture-loss-instrument.md` plus amendment 1 (`7c31c1dd`, `arch/ows-replay-consistency`). OpenSpec change: `openspec/changes/capture-loss-instrument/` (proposal, design, tasks, spec delta on `audio-capture`).
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. The Developer does not push or merge, and does not run `pre_merge_check.py` on its own initiative.
**Branch:** `feat/capture-loss-instrument`, cut from `origin/main` (`25aaf90f`, v0.58); never commit to `main`. **Do not touch `native/`.**
**Version:** `User-facing: no` in the proposal, so no VERSION bump is required by G9b; say so in the PR if you disagree.

---

## 0. Why (one paragraph)

OpenWSFZ's capture timing on `sol` wanders (audio is skipped forward in 21 of 180 windows, all during the previous cycle's residual pass), and the product cannot see audio being lost on Linux: `ArecordAudioSource` redirects `arecord`'s stderr and nothing reads it; `CaptureManager`'s `DropOldest` channel drops chunks silently; the framer's per-window `wanted` value is only logged when clamped. QA runs one instrumented S6 block on `sol` to say where the audio is lost. **This change adds the instruments and changes no capture behaviour.**

## 1. Precise scope (details and reasons in `design.md`)

1. **`ArecordAudioSource`:** read stderr on its own task from start to exit; an `overrun` line (case-insensitive) is logged at Warning with the UTC receive time **in the message text, to the millisecond**, plus the reported `N` ms from `(at least N ms long)`; counters `CaptureOverrunCount` and `CaptureOverrunReportedMs` (process lifetime). Other lines: Information, the first 20 then every 100th. Start `arecord` with `LC_ALL=C`. **Nothing else about how `arecord` is started or read changes.**
2. **`CaptureManager`:** `Channel.CreateBounded(options, itemDropped)`; counter `CaptureChannelDroppedChunks`; Warning on the first drop and every 100th with the UTC millisecond time (pattern: `CycleArchiveService.DroppedCycles`). The callback must never block.
3. **`CycleFramer`:** the `Window emitted` line (`CycleFramer.cs` ~L391) from Debug to Information, adding `wanted` beside the applied value, both in samples, with the cycle start. **No change to `wanted`, `correction`, `consume` or the clamp.**
4. **Surfacing:** the three counters in `DaemonStatus` (`GET /api/v1/status`, the WebSocket `status` event), provider delegates passed like `cycleArchiveDroppedCyclesProvider`; default 0. **Do not change the `Heartbeat:` log line** (`CaptureHealthMonitor.cs` ~L170): FR-067 fixes its text and QA supervisor scripts string-match it. (The Architect's spec said "heartbeat"; QA has asked him to confirm this reading. Do not append to that line unless told.)
5. **Not in this change:** any fix (buffer size, threads, priority, #234); the macOS `sox` source (same stderr pattern: follow-up, one line in the PR); Windows `WasapiAudioSource`; any GUI change.

## 2. Tests (test-first; HK-025(k): each must be able to fail)

The list is `tasks.md` section 1 (1.1-1.8). Three need emphasis:

- **Byte identity (1.2):** compare the raw bytes of the yielded chunks with and without stderr noise. A reader that disturbs the stdout loop must fail it.
- **Pipe-fill regression (1.3):** a fake that writes at least 256 KiB to stderr before stdout EOF. **Run it on the base commit first and record that it hangs** (use a timeout so the suite does not hang; say the observed result in the PR). If it does not hang on the base commit, say so; do not weaken the test.
- **Framer (1.7):** the existing alignment tests pass **unchanged**. Show the unchanged files in the diff stat.

Use `OpenWSFZ.TestSupport.Poll.*` for any wait; no fixed delays (TESTING_STRATEGY section 11).

## 3. What QA validates afterwards (the Developer needs none of this)

1. Review against `tasks.md` section 1, mutation of the three emphasised tests, full suite on a clean worktree, `git diff --stat -- native/` empty.
2. QA applies your commits onto `338ef61c` (the B2BASE build; the touched files are identical to `main`) in a scratch tree on `sol`, then runs positive controls C1 and C2 (SIGSTOP `arecord`; SIGSTOP the daemon) and one S6 block. That needs the Captain's go for `sol`.
3. The PR to `main` goes separately, when the Captain approves.

## 4. Notes for the PR

- `src/` only in `OpenWSFZ.Audio`, `OpenWSFZ.Ft8` (one log line), `OpenWSFZ.Web`, `OpenWSFZ.Daemon` (wiring). **User-facing: no.**
- List every hit of your grep for parsers of `Window emitted` and `Heartbeat:` (`tasks.md` 2.5). None is known.
- If anything here collides with what you find in the code, say so in the PR rather than choosing silently. The one thing that must hold is that the captured chunks do not change.
