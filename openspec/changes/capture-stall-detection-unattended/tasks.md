## 1. `CaptureHealthMonitor` — the daemon-lifetime ticker (design.md Decision 1)

- [ ] 1.1 Add `CaptureHealthMonitor` to `OpenWSFZ.Web`: a `TimeProvider`-driven periodic owner of the
      5-second per-window evaluation, following the same production-`TimeProvider.System` /
      test-override-constructor pattern `QsoAnswererService` already uses
      (`src/OpenWSFZ.Daemon/QsoAnswererService.cs:145-149,198-`) so the window logic is testable
      without real 5 s sleeps (design D1, U3).
- [ ] 1.2 Each window, in order: consume `DataFlowMonitor` once; tick the singleton `AudioWatchdog`
      once with that window's `dataFlowing`; publish an immutable snapshot
      `{captureActive, dataFlowing, audioActive, windowEndedAt}`; write the `Heartbeat:` line (§2).
      Do not consume `AudioActivityMonitor` here — see §4 for its disposition.
- [ ] 1.3 Wire it in `WebApp.Create`, at the same call site that constructs the singleton
      `AudioWatchdog` today (`src/OpenWSFZ.Web/WebApp.cs:1948-1956`, gated on
      `captureManager is not null && restartPipeline is not null`, threshold `3`). Move the
      `AudioWatchdog` construction inside/alongside the new ticker — "the watchdog stays the B3
      singleton, constructed once, and moves to this owner" (design D1). Start the ticker with the
      host (`IHostedService`/`BackgroundService`, or a task tied to `app.Lifetime.ApplicationStopping`
      — either is acceptable, this is an implementation choice not prescribed by the spec).
- [ ] 1.4 **Shutdown ordering (Appendix B item 5).** The ticker's stop must sit inside the same guard
      that already protects shutdown from a concurrent `CaptureFailed`/watchdog restart —
      `restartSemaphore.Wait()` in `Program.cs`'s `ApplicationStopping` handler
      (`src/OpenWSFZ.Daemon/Program.cs:973-1001`, the `restartSemaphore.Wait()` call is at line 980).
      Stop the ticker **before** `captureManager` is disposed (currently line 985).
- [ ] 1.5 **Test-fixture landmine (Appendix B item 1, design Risk 1).** Sweep integration-test fixtures
      that host the daemon with a fake `IAudioSource` yielding nothing — they will now trip the
      headless watchdog after 15 s where they never did before. Either supply chunks or construct the
      test host without the ticker.
- [ ] 1.6 `HasClients`-gated logic elsewhere (spectrum FFT/serialisation) is untouched by this change
      (Appendix B item 3) — do not make it depend on the ticker or vice versa.

## 2. WebSocket connections become readers (design.md Decision 6)

- [ ] 2.1 In `WebSocketHub.HandleAsync`'s per-connection heartbeat loop
      (`src/OpenWSFZ.Web/WebSocketHub.cs:315-366`): remove the `audioMonitor?.ConsumeAndReset()` call
      (line 330), remove the `dataFlowMonitor?.ConsumeAndReset()` call (line 335) and the
      `watchdog.TickAsync(dataFlowing)` call (lines 347-348). The loop's own 5 s `PeriodicTimer`, its
      close detection and its send semaphore are otherwise unchanged.
- [ ] 2.2 On each tick, send the ticker's **latest published snapshot** (§1.2) instead of a
      locally-computed value. A heartbeat frame may therefore carry a snapshot up to one window old —
      accepted, the value was already a window-old aggregate (design D6).
- [ ] 2.3 The `Heartbeat:` log line itself moves to the ticker (§1.2) — remove the duplicate log call
      currently at `WebSocketHub.cs:341-343`. Exact format unchanged (§3).
- [ ] 2.4 The initial WebSocket `status` event (`WebSocketHub.cs:296-311`) currently sets
      `AudioActive: captureManager?.IsCapturing ?? false` (line 301) — a stand-in, not the real
      signal. Change it to read the ticker's latest snapshot, same as `GET /api/v1/status` (§3),
      fixing this stand-in (design D6).

## 3. `Heartbeat:` line format and live status fields (design.md Decisions 2, 3, 5)

- [ ] 3.1 The `Heartbeat:` line's rendering does not change, byte-for-byte:
      `Heartbeat: captureActive={bool}, audioActive={bool}, dataFlowing={bool}` — lowercase,
      Information level, once per 5 s window regardless of client count (design D5). Older QA
      supervisor scripts string-match on this (`*"Heartbeat:"*"=false"*`) — do not reformat it.
- [ ] 3.2 `DataFlowMonitor.OnChunkReceived()` (`src/OpenWSFZ.Web/DataFlowMonitor.cs:22`) additionally
      stores the current monotonic timestamp (`TimeProvider.GetTimestamp()`, `Volatile.Write` or
      `Interlocked.Exchange` on a `long`) (design D2).
- [ ] 3.3 **`lastChunkAgeMs` is NOT reset by `DataFlowMonitor.Reset()`** (`DataFlowMonitor.cs:39`) —
      `Reset()` is called from `Program.cs:1093-1094` on every pipeline restart; the new timestamp
      field must survive that call. Clearing it would hide a #187 failure (restart loop against a
      dead device) from a poller (design D2). It is `null` only before the first chunk of the
      process.
- [ ] 3.4 Add three fields to `DaemonStatus` (`src/OpenWSFZ.Web/DaemonStatus.cs`): `bool DataFlowing`,
      `int? LastChunkAgeMs`, `int WatchdogRestartCount`. `LastChunkAgeMs` is computed at request time
      from the monotonic clock, not stored on the snapshot. Wire both `GET /api/v1/status`
      (`WebApp.cs:299-314`) and the initial WebSocket `status` event (`WebSocketHub.cs:296-311`) to
      populate them from the ticker's snapshot / `DataFlowMonitor`'s stored timestamp.
- [ ] 3.5 `WatchdogRestartCount`: a process-lifetime counter on the ticker (or wherever `AudioWatchdog`
      now lives), incremented each time the watchdog's threshold fires (design D7). Exposed on
      `GET /api/v1/status` and the initial WebSocket event.
- [ ] 3.6 None of the three fields latch. Two other `CaptureActive`/`AudioActive` construction sites
      exist in `WebApp.cs` (around lines 769 and 789, `POST /api/v1/config`-adjacent responses) —
      check whether they also need the new fields for consistency; if they build a fresh
      `DaemonStatus`, they must not reintroduce the amplitude latch.

## 4. One meaning for `audioActive` everywhere (design.md Decision 4 — Captain-ratified Option A)

- [ ] 4.1 `audioActive` = the `dataFlowing` value of the most recent completed window, on
      `GET /api/v1/status`, the initial WebSocket `status` event, and the WebSocket `heartbeat` frame.
      It does not latch.
- [ ] 4.2 Amend **FR-020** in `REQUIREMENTS.md` to this definition; remove the `1×10⁻⁶` amplitude
      clause (§6 below).
- [ ] 4.3 `AudioActivityMonitor` (`src/OpenWSFZ.Web/AudioActivityMonitor.cs`) has no remaining
      consumer once §2.1 and §4.1 land. Design D4 says QA/Developer **may** delete it — this is not
      mandatory for this change to ship, but if deleted: remove its construction/injection through
      `WebApp.Create` (the `audioMonitor` parameter, `WebApp.cs:83`), its `.Reset()` call in
      `RestartPipelineAsync` (`Program.cs:1093`), and its `ChunkReceived` wiring in
      `CaptureManager.StartAsync` (`src/OpenWSFZ.Audio/CaptureManager.cs:100`) that feeds it via
      FR-020's original comment. If NOT deleted this change, leave a one-line note in the PR
      description that it is now dead code, so it isn't mistaken for a second, competing amplitude
      signal by a future change.

## 5. Tests (Appendix A)

- [ ] 5.1 **U3 Headless watchdog.** Zero clients; a fake `IAudioSource` that stops yielding chunks
      **without throwing**; exactly one restart after 3 windows. With 3 clients over 10 windows:
      exactly 10 ticks and 10 consumes (proves the N-client over-tick regression is fixed).
- [ ] 5.2 **U4 `lastChunkAgeMs`.** Not reset by `DataFlowMonitor.Reset()`; `null` before the first
      chunk; monotonic — a wall-clock/`DateTime.UtcNow` change does not affect it (use the injected
      `TimeProvider`, never `DateTime.UtcNow`, for both the write and the read side).
- [ ] 5.3 **U6 Surfaces agree.** REST `audioActive` == WS initial `status.audioActive` == the value
      carried by the next WS `heartbeat` frame, for the same window.
- [ ] 5.4 **U7 Heartbeat format.** A regex asserting the emitted line matches
      `Heartbeat: captureActive=(true|false), audioActive=(true|false), dataFlowing=(true|false)`
      exactly, lowercase, one per window regardless of client count (0, 1, or N).
- [ ] 5.5 A test proving `watchdogRestartCount` increments by exactly 1 per fired watchdog restart and
      is 0 until the first one fires.
- [ ] 5.6 Full existing suite green; in particular, sweep and fix (§1.5) any silent-fake-source
      fixture the new ticker now trips.

## 6. Documentation

- [ ] 6.1 Amend **FR-020** in `REQUIREMENTS.md` §4.1: `audioActive` no longer means "amplitude above
      1×10⁻⁶ in the last 5 s interval" — it means "the `dataFlowing` value of the most recent
      completed 5-second window, on every surface (REST, initial WebSocket `status`, WebSocket
      `heartbeat`); does not latch." Remove the now-false claim that it mirrors the RMS silence guard
      in `Ft8Decoder.DecodeAsync`.
- [ ] 6.2 Add **FR-067** (capture health is evaluated independently of client connections), **FR-068**
      (live data-flow status fields: `dataFlowing`, `lastChunkAgeMs`, `watchdogRestartCount` on
      `GET /api/v1/status` and the initial WebSocket event), **FR-069** (audio activity has one
      meaning on every surface — the amended FR-020 relationship). Text for all four entries is
      already drafted in this change's REQUIREMENTS.md diff (see this handoff's companion commit) —
      copy/adjust rather than redrafting from scratch if it has drifted from the final implementation.
- [ ] 6.3 Add a `REQUIREMENTS.md` §10 revision-history row for this change, matching the existing row
      format (see FR-063's row for the most recent precedent).
- [ ] 6.4 Ensure every new xUnit test's `DisplayName` carries a requirement-ID prefix (traceability
      gate G3); re-run `tools/TraceabilityCheck` and confirm `PASS: all requirements are mapped and
      all references are valid.`
- [ ] 6.5 NFR-021 scan **post-commit**, not pre-commit (the scanner misses uncommitted files).

## 7. Verification

- [ ] 7.1 Run the full existing test suite (`dotnet test` across all projects); confirm no
      pre-existing test's assertions changed meaning. Note any pre-existing failures explicitly as
      pre-existing (re-run on the unmodified base commit, don't just assert it).
- [ ] 7.2 `openspec validate --strict --all` passes; this change's delta spec archives cleanly against
      `audio-capture`.
- [ ] 7.3 Gate G10 (`check_test_delay_sync.py`) OK — no new bare `Task.Delay(...)` in the diff; the
      ticker and its tests must use the injected `TimeProvider`.
- [ ] 7.4 Hand back to QA for the live acceptance test L1 (`architect-to-qa-handoff.md` §2) — a real
      30-minute headless run against the standing daemon build, no browser tab open. **L1 cannot
      verify stall recovery itself** (a silent WASAPI stall cannot be induced on demand) — that is
      proven only at the unit level (§5.1, U3). A green L1 must never be reported as "stall recovery
      verified live" (HK-022, HK-026 — design.md's own "Verification philosophy" section says this
      explicitly; do not let a clean live run drift into a stronger claim in review).
- [ ] 7.5 Present the diff to the Captain for explicit review (HK-011) before any push. Per HK-010 the
      merge always needs the Captain's explicit sign-off regardless of green CI. QA does not run
      `pre_merge_check.py` as part of this handoff (HK-006 — Captain's initiative only).

## 8. Out of scope (recorded, not this change)

- Re-resolving a stale device ID, retry backoff, and the recovery state machine — issue #187,
  `capture-device-reresolution`, which **depends on this change** for its status surface and
  `lastChunkAgeMs` signal. Do not start #187 on a branch based on `main` before this change merges —
  base it on this branch's tip instead (stacked PR, HK-008), or rebase onto `main` once this merges,
  whichever the Developer session finds live at the time.
