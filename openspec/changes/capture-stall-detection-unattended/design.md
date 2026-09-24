# Design — capture stall detection on unattended runs (#188)

## Context

Today every piece of per-window capture-health logic lives inside
`WebSocketHub.HandleAsync`'s per-connection heartbeat loop (`WebSocketHub.cs:317-370`):

```
per WebSocket connection, every 5 s:
    audioMonitor.ConsumeAndReset()          // result discarded (B21)
    dataFlowing = dataFlowMonitor.ConsumeAndReset()
    log "Heartbeat: captureActive=…, audioActive=…, dataFlowing=…"
    _ = watchdog.TickAsync(dataFlowing)     // singleton watchdog (B3)
    send heartbeat frame
```

This produces three failures:

| Clients connected | What happens |
|---|---|
| 0 (unattended) | Nothing is evaluated: no watchdog, no heartbeat log line, and `audioActive` on REST latches `true` forever. |
| 1 | Works as designed. |
| N ≥ 2 | Shared flags are drained N times per window. The singleton watchdog is ticked N times per window, so its 15 s threshold is reached after about 15/N s of stall. There are N heartbeat log lines per 5 s. |

The design moves the evaluation to one owner with a lifetime equal to the daemon's, and makes
every other consumer a reader.

## Decision 1 — One daemon-lifetime ticker owns the per-window evaluation

**Chosen:** a new singleton, suggested name `CaptureHealthMonitor`, in `OpenWSFZ.Web`, started
with the host (an `IHostedService` / `BackgroundService`, or an equivalent task tied to
`ApplicationStopping`). Every 5 s it:

1. consumes `DataFlowMonitor` once (and `AudioActivityMonitor` once, if D4 keeps it);
2. ticks the singleton `AudioWatchdog` once with that window's `dataFlowing`;
3. publishes an immutable snapshot `{captureActive, dataFlowing, audioActive, windowEndedAt}`;
4. writes the `Heartbeat:` log line (D5).

The watchdog stays the B3 singleton, constructed once, and moves to this owner.

| Alternative | Verdict |
|---|---|
| Keep the tick in the WS loop and add a "headless" fallback timer that runs only when `HasClients` is false | **Rejected.** Two code paths that must hand over cleanly whenever a client connects or disconnects. The handover is itself a race, and the N-client over-tick remains. |
| Tick from the capture thread (`ChunkReceived`) | **Rejected.** A stall is the *absence* of chunks. A tick driven by chunks cannot fire during a stall. |
| Tick from the decode pump / `CycleFramer` | **Rejected.** A stall stops the framer too, so the same problem applies. This would also couple health to decoding being enabled. |
| **Independent periodic timer, one owner** | **Chosen.** It is the only design whose tick does not depend on the thing it is watching. |

The ticker **must take an injectable `TimeProvider`**, as `QsoAnswererService.cs:145-198` already does,
so the window logic can be unit-tested without real 5 s sleeps.

## Decision 2 — `lastChunkAgeMs`: a non-latching, request-time signal

`DataFlowMonitor.OnChunkReceived()` additionally stores the current monotonic timestamp
(`TimeProvider.GetTimestamp()`, via `Volatile.Write` or `Interlocked.Exchange` on a `long`).
`GET /api/v1/status` computes `lastChunkAgeMs` at request time, so it is correct to the millisecond
at the moment of the poll and cannot latch.

- It is `null` only before the first chunk of the process.
- It is **not** cleared by `DataFlowMonitor.Reset()` on a pipeline restart. A restart that never
  delivers audio must show a growing age, not reset it to "unknown". Clearing it would hide exactly
  the #187 failure (restart loop against a dead device) from a poller.
- Use a monotonic clock, not wall time. A wall-clock step from an NTP correction must not produce a
  negative or inflated age.

Why this field and not only `dataFlowing`: `dataFlowing` has a resolution of 5 s and describes the
**previous** window. `lastChunkAgeMs` lets an external supervisor choose its own threshold without
knowing the daemon's window length. The cost per chunk is one 64-bit store.

## Decision 3 — `dataFlowing` is the last *completed* window

Before the first window completes it reads `false`. This is the same value the WebSocket heartbeat
already carries today. It is re-exposed, not redefined.

## Decision 4 — one meaning for `audioActive` (✅ CAPTAIN RATIFIED option A, 2026-09-24)

Today it has three meanings in code, and FR-020 gives a fourth (see `proposal.md`).

| Option | Meaning | Consequence |
|---|---|---|
| **A (recommended)** | `audioActive` = `dataFlowing` of the last completed window, everywhere | Matches what the UI indicator already shows through the heartbeat (B21: "a quiet band is not an application failure"). FR-020 is amended to say so, and the 1×10⁻⁶ amplitude clause is removed. `AudioActivityMonitor` then has no consumer, and QA/Developer may delete it. |
| B | `audioActive` = amplitude above 1×10⁻⁶ in the last completed window, everywhere (FR-020 as written) | Reverses B21. The UI dot would go dark on a genuinely silent input, for example a radio on a dead band into a virtual cable carrying zeros. It keeps a second signal that nobody currently acts on. |
| C | Leave as is and only add the new fields | Leaves the REST latch serving a value that is wrong on every unattended run. **Not recommended.** |

**Recommendation: A.** Both of the other options keep a field whose name promises something it
does not deliver on at least one surface.

## Decision 5 — the `Heartbeat:` log line: once per window, exact format kept

Written by the ticker once per 5 s window, at Information level, in the **exact** existing format:

```
Heartbeat: captureActive={bool}, audioActive={bool}, dataFlowing={bool}
```

Observed rendering in a real daemon log (2026-08-21) is lowercase: `captureActive=true, …`. The
older scripts match the lowercase `=false`, which is case-sensitive in bash. The rendering must not
change.

Older QA supervisor scripts string-match on it (`*"Heartbeat:"*"=false"*`, and "no `Heartbeat:`
line within 60 s of relaunch"). The standing pre-arm check tells the operator to read it.

- Volume: about 17,300 lines/day, about 1.7 MB. That is the same as an attended run with one browser tab today.
- Rejected: once per minute, or only on change. That would silently break the 60 s liveness checks
  in the existing scripts, and a line that appears only on change cannot prove liveness.

## Decision 6 — WebSocket connections become pure readers

The per-connection loop keeps its structure: its own 5 s timer, its close detection and its send
semaphore. On each tick it sends the **ticker's latest snapshot**. It must no longer call any
`ConsumeAndReset()` and must no longer touch the watchdog.

A heartbeat frame may therefore carry a snapshot up to one window old. That is acceptable: the
value was already a window-old aggregate.

The initial WebSocket `status` event uses the same snapshot, which fixes the `IsCapturing` stand-in at
`WebSocketHub.cs:300`.

**Rejected:** broadcasting heartbeats from the ticker to all sockets. That is cleaner in principle,
but it restructures the connection lifecycle for no functional gain in this change.

## Decision 7 — `watchdogRestartCount`

A process-lifetime counter, incremented each time the watchdog's threshold fires, and exposed on
`GET /api/v1/status`. It lets a supervisor tell "healthy" apart from "healthy because the
watchdog has restarted it 40 times". Backoff between repeated watchdog restarts belongs to #187
(one bounded backoff policy for every automatic restart), not here.

## Risks and landmines (material for QA — not instructions to the Developer)

1. **The watchdog becomes live on every unattended run.** R&R batteries and endurance runs will
   now restart the pipeline after 15 s of no chunks. A virtual cable carrying digital silence still
   delivers buffers, so it is unaffected (any chunk counts). A **fake `IAudioSource` in integration
   tests that yields nothing** will now trigger restarts that it never triggered before. Test fixtures that
   host the daemon with a silent fake source must either supply chunks or construct the host without
   the ticker.
2. **Restart discards the partial cycle** (`DEFECT-cycle-discard-on-restart.md`). This is only on a genuine
   stall, where the cycle is already lost, so it is not a regression. It is worth one line in the
   release note.
3. **`HasClients` gating elsewhere** (spectrum FFT) must stay as it is. This change must not make FFT
   or serialisation run with zero clients.
4. **Ordering at shutdown.** The ticker must stop before `CaptureManager` is disposed, or the watchdog
   could fire a restart into a stopping pipeline. `Program.cs:979` already guards shutdown against a
   concurrent `CaptureFailed` or watchdog restart. The ticker's stop must sit inside the same guard.
5. **FR-021 is untouched.** Every capture-session termination still logs. This change adds no
   suppression of those lines.

## Verification philosophy

A silent WASAPI stall **cannot be induced on demand on real hardware**. Pulling the USB cable
produces a thrown failure (the #187 path), not a stall. The stall path is therefore proven at the
**unit/integration level** with a fake source that stops yielding without throwing, and the live
test proves only that the headless heartbeat and status fields exist and track reality (see the
handoff). This limit is stated here so that nobody later reads a clean live run as "stall
recovery verified live" (HK-022, HK-026).
