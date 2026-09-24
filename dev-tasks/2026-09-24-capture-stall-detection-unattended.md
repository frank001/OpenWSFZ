# Developer handoff: `capture-stall-detection-unattended` (#188)

**Authored by:** QA (per HK-000/HK-015/HK-011). **Status:** ready for a Developer session.
**Source:** Architect → QA handoff
`openspec/changes/capture-stall-detection-unattended/architect-to-qa-handoff.md` (§1 task 1.3), plus
`design.md`/`proposal.md`/`specs/audio-capture/spec.md` in the same folder — read all three before
starting, this document does not repeat their content.
**OpenSpec change:** `openspec/changes/capture-stall-detection-unattended/` (this branch,
`openspec validate --strict --all`: 63/63). This handoff implements that change's `tasks.md`
§1–§7 (QA-authored).
**Decision authority:** Captain ratified C1 (`audioActive` = last-window `dataFlowing`, everywhere;
amend FR-020) at ~19:00Z 2026-09-24. Recorded in the handoff §0 and in `design.md` Decision 4.
**Branch:** `feat/capture-stall-detection-unattended`, based on `origin/main`@`5a9290c6`, already
checked out, already carries the openspec change, `tasks.md`, and the REQUIREMENTS.md amendment
below. **Continue on this branch — do not cut a new one.**

🛑 **QA proposes this diff and stops here (HK-011). QA does not edit `src/`, does not build, does not
run `pre_merge_check.py` (HK-006 — Captain's initiative only).** A separate Developer session
implements this, builds, and runs the existing test suite. The Captain reviews the diff before any
push. QA returns afterward to run the live acceptance test L1 (handoff §2) — that is QA's, not the
Developer's, and **L1 cannot verify stall recovery itself** (see §5 below — do not let a clean L1 run
be reported as more than it is).

Every file:line reference below was re-read on `origin/main`@`5a9290c6` immediately before writing
this document (HK-018/HK-022), matching the values `design.md` itself cites. If your working tree has
moved since, re-grep the anchors rather than trusting the line numbers blindly.

---

## 1. What this changes, in one sentence

Capture-health evaluation (the `AudioWatchdog` tick, the `Heartbeat:` log line, and the
`dataFlowing`/`audioActive` state) moves from inside `WebSocketHub.HandleAsync`'s per-connection
heartbeat loop — which runs **zero times** with no browser tab connected, and over-ticks the shared
watchdog when N ≥ 2 clients are connected — to a single daemon-lifetime ticker that runs identically
at 0, 1, or N clients. `GET /api/v1/status` gains three live fields so an HTTP-only supervisor
(`qa/endurance/endurance_supervisor.py`) can see a silent stall without a browser open.

## 2. New component — `CaptureHealthMonitor` (design.md Decision 1)

Add to `OpenWSFZ.Web`, following the `TimeProvider`-injectable pattern
`QsoAnswererService` already establishes (`src/OpenWSFZ.Daemon/QsoAnswererService.cs`: production
constructor defaults `_timeProvider = TimeProvider.System`; an `internal` test constructor accepts an
override — same file, look for the two constructors). Do **not** use `DateTime.UtcNow` or a bare
`Task.Delay` on a magic constant anywhere in the ticker or its tests (gate G10,
`tools/check_test_delay_sync.py`).

Every 5-second window, in this order:

1. Consume `DataFlowMonitor` once (`ConsumeAndReset()`).
2. Tick the singleton `AudioWatchdog` once with that window's `dataWasFlowing`.
3. Publish an immutable snapshot: `{captureActive, dataFlowing, audioActive, windowEndedAt}`.
4. Write the `Heartbeat:` line (§4) at Information level.

**Wiring.** `AudioWatchdog` is currently constructed directly inside `WebApp.Create`
(`src/OpenWSFZ.Web/WebApp.cs:1948-1956`):

```csharp
var audioWatchdog = captureManager is not null && restartPipeline is not null
    ? new AudioWatchdog(
          isCapturing: () => captureManager.IsCapturing,
          onRestart:   restartPipeline,
          threshold:   3)
    : null;
```

Move this construction inside (or alongside, sharing ownership with) the new
`CaptureHealthMonitor` — "the watchdog stays the B3 singleton, constructed once, and moves to this
owner" (design D1). `captureManager`, `audioMonitor`, `dataFlowMonitor` are already `WebApp.Create`
parameters (`WebApp.cs:82-84`) — the ticker can be constructed the same way, in the same method, with
the same closure-capture style already used for `audioWatchdog` and `restartPipeline`. Start it with
the host — either a registered `BackgroundService`/`IHostedService` (see `configureServices` usage
around `Program.cs:486-707` for how other hosted services are wired through `WebApp.Create`'s
`configureServices` callback) or a task tied to `app.Lifetime.ApplicationStopping`. Either satisfies
the spec; pick whichever fits the existing DI shape more cleanly — this is an implementation choice,
not prescribed.

**Shutdown ordering — do not skip.** `Program.cs`'s `ApplicationStopping` handler
(`src/OpenWSFZ.Daemon/Program.cs:973-1001`) already guards teardown against a concurrent
`CaptureFailed`/watchdog restart with `restartSemaphore.Wait()` at line 980, before
`captureManager.StopAsync()`/`DisposeAsync()` at lines 984-985. The ticker's stop must happen inside
that same guarded region, before `captureManager` is disposed — otherwise the watchdog can fire a
restart into a pipeline that is mid-teardown.

**Test-fixture landmine.** Any integration-test fixture that hosts the daemon with a fake
`IAudioSource` that yields nothing will now trip the watchdog after 15 s, where it silently never did
before (design Risk 1). Grep the test projects for a silent fake source hosting `WebApp.Create`/the
daemon and either feed it chunks or construct that particular test host without the ticker.

## 3. WebSocket connections become readers (design.md Decision 6)

In `WebSocketHub.HandleAsync`'s per-connection loop
(`src/OpenWSFZ.Web/WebSocketHub.cs:315-366`):

- Remove `audioMonitor?.ConsumeAndReset()` (line 330).
- Remove `dataFlowMonitor?.ConsumeAndReset()` (line 335) and the local `var dataFlowing = ...`/
  `var active = ...` computation it feeds (lines 335-336).
- Remove the `Heartbeat:` log call at lines 341-343 (it moves to the ticker, §4).
- Remove `if (watchdog is not null) _ = watchdog.TickAsync(dataFlowing);` (lines 347-348).
- On each 5 s tick, read the ticker's **latest published snapshot** and send it instead. A frame may
  therefore carry a snapshot up to one window old — accepted (design D6), it was already a
  window-old aggregate before this change.
- The loop's own `PeriodicTimer`, close detection (`ReceiveUntilCloseAsync`), and send semaphore are
  unchanged.

**Initial `status` event.** Currently sets `AudioActive: captureManager?.IsCapturing ?? false`
(`WebSocketHub.cs:301`) — a stand-in, not the real signal (the design doc calls this out explicitly:
"fixes the `IsCapturing` stand-in at `WebSocketHub.cs:300`"). Change it to read the same ticker
snapshot `GET /api/v1/status` reads (§5), so both surfaces agree from the first frame.

`HasClients`-gated logic elsewhere (spectrum FFT/serialisation) is untouched — do not make it depend
on the ticker, and do not make the ticker depend on it (design Risk 3).

## 4. `Heartbeat:` line — exact format preserved (design.md Decision 5)

```
Heartbeat: captureActive={bool}, audioActive={bool}, dataFlowing={bool}
```

Lowercase, Information level, **exactly** this rendering, written once per 5 s window by the ticker
regardless of client count (0 included). Older QA supervisor scripts string-match on
`*"Heartbeat:"*"=false"*` and on "no `Heartbeat:` line within 60 s of relaunch" — a reformat silently
breaks both. Do not switch to once-per-minute or only-on-change (design rejected both explicitly: a
liveness check needs a line on every window, not only on transition).

## 5. Live status fields (design.md Decisions 2, 3, 7)

**`DataFlowMonitor`** (`src/OpenWSFZ.Web/DataFlowMonitor.cs`): `OnChunkReceived()` (line 22)
additionally stores the current monotonic timestamp (`TimeProvider.GetTimestamp()`, via
`Volatile.Write`/`Interlocked.Exchange` on a `long` field — the class is currently a single
`volatile bool _flowing`, this adds a sibling field, not a replacement).

🔴 **`Reset()` (line 39) must NOT clear the new timestamp field.** `Reset()` is called from
`Program.cs:1093-1094` inside `RestartPipelineAsync` on every pipeline restart (both the `audioMonitor`
and `dataFlowMonitor` `Reset()` calls live there, right after `if (stopCaptureManager)
captureManager.StopAsync();`). If the new field were cleared there, a restart that then fails to
deliver anything would read as "unknown" instead of "ageing" — exactly the #187 failure mode
(restart loop against a dead device) this field exists to expose to a poller. Keep `_flowing`'s reset
behaviour; add the new field's storage/read path alongside it, unreset.

**`DaemonStatus`** (`src/OpenWSFZ.Web/DaemonStatus.cs`): add three fields —
`bool DataFlowing`, `int? LastChunkAgeMs`, `int WatchdogRestartCount`.

- `LastChunkAgeMs` is **computed at request time** (`GET /api/v1/status` handler,
  `src/OpenWSFZ.Web/WebApp.cs:299-314`) from `TimeProvider.GetTimestamp()` minus the stored
  timestamp — not stored on the ticker's snapshot itself, since it must be correct to the millisecond
  at poll time, not at last-window time. `null` only before the first chunk of the process.
- `WatchdogRestartCount` is a process-lifetime counter, incremented wherever the watchdog's threshold
  fires (inside `AudioWatchdog.TickAsync`, `src/OpenWSFZ.Web/AudioWatchdog.cs:67-71`, or on the
  ticker that owns it now — either is fine, just one counter, incremented exactly once per fired
  restart).
- Wire both `GET /api/v1/status` (`WebApp.cs:299-314`) and the initial WebSocket `status` event
  (`WebSocketHub.cs:296-311`) from the same source so they can never disagree.
- **Check the two other `DaemonStatus` construction sites** in `WebApp.cs` (around lines 769 and
  789 — `POST /api/v1/config`-adjacent responses at the time this was written; re-grep
  `new DaemonStatus(` to find them fresh) for whether they also need the new fields for response-shape
  consistency. If they do, wire them from the same source; do not reintroduce a fourth, different
  `AudioActive` computation on any of them.

None of the three new fields latch.

## 6. One meaning for `audioActive` (design.md Decision 4 — Captain-ratified Option A)

`audioActive` = `dataFlowing` of the most recent completed window, identically on `GET /api/v1/status`,
the initial WebSocket `status` event, and every WebSocket `heartbeat` frame.

`GET /api/v1/status` currently computes it as `audioMonitor?.IsActive ?? false` (`WebApp.cs:307`) — a
one-way latch that never resets without a connected WebSocket client. Replace with the ticker's
`dataFlowing` value, same source as §5.

**`AudioActivityMonitor`** (`src/OpenWSFZ.Web/AudioActivityMonitor.cs`) has no remaining consumer once
§3 and this section land. Design D4 says it **may** be deleted — not mandatory for this change, your
call. If you delete it, remove:

- Its construction/parameter in `WebApp.Create` (`audioMonitor` param, `WebApp.cs:83`, and every call
  site that passes one in).
- Its `.Reset()` call in `RestartPipelineAsync` (`Program.cs:1093`).
- Its `ChunkReceived` wiring inside `CaptureManager.StartAsync`
  (`src/OpenWSFZ.Audio/CaptureManager.cs:100`, `ChunkReceived?.Invoke(chunk);` — check whether that
  delegate has any other subscriber before removing the wiring itself; the delegate property on
  `CaptureManager` may still be needed for the data-flow monitor's own chunk notification, so remove
  only the `AudioActivityMonitor`'s specific subscription, not the mechanism).

If you leave it in place (dead code) for this PR, say so plainly in the PR description so it isn't
mistaken later for a second, competing amplitude signal.

## 7. Tests

Match these to the `tasks.md` §5 items (Appendix A of the Architect handoff, ported into `tasks.md`):

- **U3** — zero clients, a fake `IAudioSource` that stops yielding **without throwing**: exactly one
  restart after 3 windows (15 s of simulated time via the injected `TimeProvider`, not real sleep).
  3 clients over 10 windows: exactly 10 watchdog ticks and 10 monitor consumes — this is the
  regression test for the N-client over-tick bug this change fixes.
- **U4** — `lastChunkAgeMs` survives `DataFlowMonitor.Reset()` unreset; `null` before the first chunk;
  advancing the injected `TimeProvider` (not `DateTime.UtcNow`) changes it monotonically.
- **U6** — REST `audioActive` == initial WS `status.audioActive` == the next WS `heartbeat.audioActive`,
  for the same window, across a stopped→started→stopped capture-state sequence.
- **U7** — regex-match the emitted `Heartbeat:` line against
  `^Heartbeat: captureActive=(true|false), audioActive=(true|false), dataFlowing=(true|false)$`,
  lowercase, exactly one per window at 0, 1, and 2+ simulated clients.
- `watchdogRestartCount` starts at 0, increments by exactly 1 per fired restart, is unaffected by a
  restart that itself fails to reconnect (it counts *attempts*, i.e. fired triggers, not successes —
  confirm this matches your reading of design D7; if you read it differently, flag it rather than
  guess).
- Full existing suite green, including the fixture sweep from §2's test-fixture landmine.

## 8. Documentation — already drafted, verify it still matches your diff

`REQUIREMENTS.md` already carries, on this branch: FR-020 amended, and new FR-067/FR-068/FR-069 added
(§4.1), plus a `REQUIREMENTS.md` §10 revision-history row (1.48) and the `README.md`/`REQUIREMENTS.md`
version-anchor bump to **v0.50** (`VERSION` file). **Do not re-bump VERSION for this change** — it's
already done. If your implementation ends up differing from what these three FR entries describe
(field names, exact semantics), correct the FR text to match reality rather than silently drifting —
traceability (NFR-020) depends on the two staying in sync.

- [ ] Confirm every new xUnit test's `DisplayName` carries a requirement-ID prefix (`FR-067`/
      `FR-068`/`FR-069`) — gate G3. Re-run `tools/TraceabilityCheck` and confirm
      `PASS: all requirements are mapped and all references are valid.`
- [ ] NFR-021 scan **post-commit**, not pre-commit (the scanner misses uncommitted files).

## 9. Definition of done

- [ ] §2's `CaptureHealthMonitor` added; `AudioWatchdog` construction moved to/shared with it; shutdown
      ordering preserved inside `restartSemaphore`'s existing guard.
- [ ] §3's `WebSocketHub` loop is a pure reader: no `ConsumeAndReset()`, no `TickAsync`, no
      `Heartbeat:` log call remaining in `WebSocketHub.cs`.
- [ ] §4's `Heartbeat:` line byte-identical to today's format, once per window, at 0/1/N clients.
- [ ] §5's three new `DaemonStatus` fields wired on both `GET /api/v1/status` and the initial WS event;
      none latch; `lastChunkAgeMs` survives a restart unreset.
- [ ] §6's `audioActive` reads identically on all three surfaces; `AudioActivityMonitor` either fully
      removed or explicitly left as documented dead code.
- [ ] §7's tests added and passing; full suite green; fixture sweep done.
- [ ] Gate G10 (`check_test_delay_sync.py`) OK — no new bare `Task.Delay(...)`.
- [ ] `openspec validate --strict --all` passes.
- [ ] `git diff --stat` against `main` touches only `OpenWSFZ.Web`, `OpenWSFZ.Daemon/Program.cs`
      (wiring only), `OpenWSFZ.Audio/CaptureManager.cs` (only if §6's `AudioActivityMonitor` deletion
      touches its `ChunkReceived` wiring), and the corresponding test projects. **Zero diff under
      `native/`.**
- [ ] Present the diff to the Captain for explicit review (HK-011) before any push. Per HK-010 the
      merge always needs the Captain's explicit sign-off regardless of green CI.
- [ ] 🛑 **Do not run `pre_merge_check.py`** (HK-006 — Captain's initiative only). **Do not push, do
      not merge.**

Once the diff is ready, control returns to QA for the live acceptance test L1
(`architect-to-qa-handoff.md` §2): a real 30-minute headless run against the standing daemon build, no
browser tab open, `ws_accepted == 0` verified mechanically. **L1 cannot exercise stall recovery
itself** — a silent WASAPI stall cannot be induced on demand on real hardware; that path is proven
only by §7's U3 unit test. Do not let a green L1 be reported as "stall recovery verified live"
(HK-022, HK-026 — `design.md`'s own "Verification philosophy" section states this limit explicitly).

## 10. What this handoff does NOT authorize

- 🛑 No push, no merge, no `pre_merge_check.py`.
- 🛑 No work on #187 (`capture-device-reresolution`) — separate change, separate handoff, depends on
  this one's status surface and ships second (recommendation: base its branch on this branch's tip,
  a stacked PR per HK-008, or rebase onto `main` once this merges).
- 🛑 No re-litigating Captain-ratified C1 (design D4, Option A) — the amended FR-020 text already
  reflects it.
- 🛑 No TX-output-device work — same defect class, tracked separately (handoff §1 task 1.7, a new
  GitHub issue).

## 11. Cross-references

- `openspec/changes/capture-stall-detection-unattended/{proposal,design,specs/audio-capture/spec,
  architect-to-qa-handoff}.md` — the full spec this handoff implements `tasks.md` §1–§7 of.
- `openspec/changes/capture-stall-detection-unattended/tasks.md` — QA-authored, section numbers match
  this document's section numbers 1:1 (tasks.md §1 ↔ here §2, tasks.md §2 ↔ here §3, etc. — tasks.md
  §6 "Documentation" and §7 "Verification" map to here §8/§9 combined).
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — the `TimeProvider`-injectable `BackgroundService`
  pattern to mirror.
- `src/OpenWSFZ.Web/{WebSocketHub,WebApp,DaemonStatus,DataFlowMonitor,AudioActivityMonitor,
  AudioWatchdog}.cs`, `src/OpenWSFZ.Daemon/Program.cs`, `src/OpenWSFZ.Audio/CaptureManager.cs` — every
  file this change touches; line numbers as of `origin/main`@`5a9290c6`, re-grep if drifted.
