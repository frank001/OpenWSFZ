## Context

Audio can be lost in three places on the Linux capture path, and one existing measurement sees the result of any of them:

| # | Place | Visible today? |
|---|---|---|
| L1 | ALSA's capture ring under `arecord` (overrun when `arecord` does not read in time; `arecord` prints `overrun!!! (at least N ms long)` on stderr) | No: stderr is never read |
| L2 | The stdout pipe `arecord` to daemon (~64 KiB, about 1.37 s of 12 kHz float); if the daemon's reader is starved, `arecord` blocks and L1 overruns behind it | Only through L1's stderr line |
| L3 | `CaptureManager`'s channel (16 chunks, about 2.7 s, `DropOldest`) | No: no callback, no log |
| framer | `CycleFramer` compares the sample stream with the wall clock at each window start (`wanted`, `CycleFramer.cs` ~L298) | Only when clamped (> 250 ms, Warning); the applied value is Debug |

An overrun counter at zero does not prove nothing was lost (L3 loses audio without an `arecord` line), so all four are instrumented; the framer reading is the loss-agnostic check on the other three.

## Decisions

1. **Stderr is read on its own task**, from process start to exit, line by line. It never shares a read loop or a lock with the stdout loop, and it is drained even when nothing is logged (the hazard is the pipe filling). The reader task is awaited at the source's teardown with the same `WaitForExitAsync` ordering as today.
2. **An overrun is a line containing `overrun`, case-insensitive.** The reported length is parsed from `(at least N ms long)` when present (invariant culture, decimals allowed); an unparsable one still counts, adding nothing to `CaptureOverrunReportedMs`.
3. **The overrun log message carries its own UTC receive time to the millisecond** (`HH:mm:ss.fff`), because log-sink stamps are whole seconds. The study joins overrun time to step intervals at sub-second resolution.
4. **Other stderr lines (`arecord` prints a header on start) are Information, rate-limited**: the first 20, then every 100th, with a running count.
5. **`LC_ALL=C` is set in the `arecord` environment** (`ProcessStartInfo.Environment`). It is the only change to how `arecord` is started; arguments are untouched.
6. **Channel drops use `Channel.CreateBounded(options, itemDropped)`.** The callback increments a `long` with `Interlocked`, and logs at Warning on the first drop and every 100th, with the UTC millisecond time (the `CycleArchiveService.DroppedCycles` pattern). The callback runs in the writer's path: it only increments and may log; it never blocks. Cross-platform, so Windows gets it too.
7. **The per-window framer line moves Debug to Information and adds `wanted`.** One line per 15 s window: cycle start, `wanted` and applied (samples), consumed samples. Message text keeps the existing prefix `Window emitted (` so a grep for the old line still finds it (the Developer greps for parsers anyway and reports; none is known).
8. **Counters surface through `DaemonStatus`**, via providers passed to `WebApp` the way `cycleArchiveDroppedCyclesProvider` is, on `GET /api/v1/status` and the WebSocket `status` event. **The `Heartbeat:` log line (`CaptureHealthMonitor.cs`) is deliberately left alone**: FR-067 requires it byte-identical and supervisor scripts string-match it. The Architect's spec asks for "the heartbeat" too; this reading is flagged to him (QA message 2026-10-17).
9. **Counters are process-lifetime** (never reset by a capture restart), because the watchdog restarts the source inside one process and the study sums over a block.
10. **Where the counters live.** `ArecordAudioSource` is `internal` and created per platform behind `IAudioSource`; the overrun counters are exposed through a small optional interface (for example `ICaptureLossCounters`) that only the `arecord` source implements, which `CaptureManager` passes through. The Developer chooses the shape; the constraint is that other platforms report 0 and compile unchanged.

## Risks

- **Chunk bytes must not change.** A stderr task that touched the stdout buffer or delayed the read loop would alter the captured audio's timing, which is the very thing under study. Covered by the byte-identity test and by the study's own O7 overhead row.
- The `arecord` text is `alsa-utils`' own and has varied across versions; the case-insensitive `overrun` match and the unparsed-length fallback are the tolerance. The study records the verbatim line from the positive controls.
- Information-level framer lines add 240 lines an hour to the log; accepted.
