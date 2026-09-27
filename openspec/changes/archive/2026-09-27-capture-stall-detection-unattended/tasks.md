Record correction 2026-09-27: boxes back-filled at archive time against named evidence. Note:
squash commit `42cf88f7`'s title says "no src/ diff", but it carries `src/` (`CaptureHealthMonitor.cs`
+232, `Program.cs`, `WebApp.cs`, `WebSocketHub.cs`, `DataFlowMonitor.cs`, `DaemonStatus.cs`,
`AudioWatchdog.cs` — 21 files, `+2076/-73` total per `git show --stat 42cf88f7`); the title is wrong
(it describes only the PR's first commit), the merge is correct. `main` history is not rewritten.

## 1. `CaptureHealthMonitor` — the daemon-lifetime ticker (design.md Decision 1)

- [x] 1.1 Add `CaptureHealthMonitor` to `OpenWSFZ.Web`: a `TimeProvider`-driven periodic owner of the
      5-second per-window evaluation, following the same production-`TimeProvider.System` /
      test-override-constructor pattern `QsoAnswererService` already uses
      (`src/OpenWSFZ.Daemon/QsoAnswererService.cs:145-149,198-`) so the window logic is testable
      without real 5 s sleeps (design D1, U3).
      **Evidence:** `src/OpenWSFZ.Web/CaptureHealthMonitor.cs` exists, `TimeProvider timeProvider ??
      TimeProvider.System` constructor pattern present.
- [x] 1.2 Each window, in order: consume `DataFlowMonitor` once; tick the singleton `AudioWatchdog`
      once with that window's `dataFlowing`; publish an immutable snapshot
      `{captureActive, dataFlowing, audioActive, windowEndedAt}`; write the `Heartbeat:` line (§2).
      Do not consume `AudioActivityMonitor` here — see §4 for its disposition.
      **Evidence:** `CaptureHealthMonitor.cs` `TickOnceAsync` — steps in the documented order,
      confirmed by inspection.
- [x] 1.3 Wire it in `WebApp.Create`, at the same call site that constructs the singleton
      `AudioWatchdog` today (`src/OpenWSFZ.Web/WebApp.cs:1948-1956`, gated on
      `captureManager is not null && restartPipeline is not null`, threshold `3`). Move the
      `AudioWatchdog` construction inside/alongside the new ticker — "the watchdog stays the B3
      singleton, constructed once, and moves to this owner" (design D1). Start the ticker with the
      host (`IHostedService`/`BackgroundService`, or a task tied to `app.Lifetime.ApplicationStopping`
      — either is acceptable, this is an implementation choice not prescribed by the spec).
      **Evidence:** `src/OpenWSFZ.Daemon/Program.cs:467` `var captureHealthMonitor = new
      CaptureHealthMonitor(...)`.
- [x] 1.4 **Shutdown ordering (Appendix B item 5).** The ticker's stop must sit inside the same guard
      that already protects shutdown from a concurrent `CaptureFailed`/watchdog restart —
      `restartSemaphore.Wait()` in `Program.cs`'s `ApplicationStopping` handler
      (`src/OpenWSFZ.Daemon/Program.cs:973-1001`, the `restartSemaphore.Wait()` call is at line 980).
      Stop the ticker **before** `captureManager` is disposed (currently line 985).
      **Evidence:** `Program.cs:1031-1046` — `restartSemaphore.Wait()` then, inside the `try`,
      `captureHealthMonitor.DisposeAsync()...` FIRST, with a comment citing this exact task and
      design.md Risk 4, before `StopFramerAsync`/`captureManager.StopAsync`/`DisposeAsync`. Read
      directly, not assumed.
- [x] 1.5 **Test-fixture landmine (Appendix B item 1, design Risk 1).** Sweep integration-test fixtures
      that host the daemon with a fake `IAudioSource` yielding nothing — they will now trip the
      headless watchdog after 15 s where they never did before. Either supply chunks or construct the
      test host without the ticker.
      **Evidence:** full existing suite green post-merge (commit message: Web.Tests 300/300,
      Daemon.Tests 621/621, Audio.Tests 19/19 unchanged) — no fixture regression surfaced.
- [x] 1.6 `HasClients`-gated logic elsewhere (spectrum FFT/serialisation) is untouched by this change
      (Appendix B item 3) — do not make it depend on the ticker or vice versa.
      **Evidence:** not in the changed-file list (`git show --stat 42cf88f7`); no spectrum/FFT file
      appears in the diff.

## 2. WebSocket connections become readers (design.md Decision 6)

- [x] 2.1 In `WebSocketHub.HandleAsync`'s per-connection heartbeat loop
      (`src/OpenWSFZ.Web/WebSocketHub.cs:315-366`): remove the `audioMonitor?.ConsumeAndReset()` call
      (line 330), remove the `dataFlowMonitor?.ConsumeAndReset()` call (line 335) and the
      `watchdog.TickAsync(dataFlowing)` call (lines 347-348). The loop's own 5 s `PeriodicTimer`, its
      close detection and its send semaphore are otherwise unchanged.
      **Evidence:** `grep -n "ConsumeAndReset\|TickAsync" src/OpenWSFZ.Web/WebSocketHub.cs` — no
      matches; only comments referencing the ticker remain.
- [x] 2.2 On each tick, send the ticker's **latest published snapshot** (§1.2) instead of a
      locally-computed value. A heartbeat frame may therefore carry a snapshot up to one window old —
      accepted, the value was already a window-old aggregate (design D6).
      **Evidence:** `WebSocketHub.cs:364-366` comment: "CaptureHealthMonitor's latest published
      snapshot, which may therefore be [a] window-old aggregate before this change."
- [x] 2.3 The `Heartbeat:` log line itself moves to the ticker (§1.2) — remove the duplicate log call
      currently at `WebSocketHub.cs:341-343`. Exact format unchanged (§3).
      **Evidence:** `CaptureHealthMonitor.cs:170` is the only remaining `"Heartbeat: captureActive=..."`
      log call site (`grep -rn "Heartbeat: captureActive"` across `src/OpenWSFZ.Web/`).
- [x] 2.4 The initial WebSocket `status` event (`WebSocketHub.cs:296-311`) currently sets
      `AudioActive: captureManager?.IsCapturing ?? false` (line 301) — a stand-in, not the real
      signal. Change it to read the ticker's latest snapshot, same as `GET /api/v1/status` (§3),
      fixing this stand-in (design D6).
      **Evidence:** covered by the same U6 cross-surface tests (§5.3) proving REST/initial-WS/heartbeat
      agree — that agreement is impossible if the initial event still read `IsCapturing` directly.

## 3. `Heartbeat:` line format and live status fields (design.md Decisions 2, 3, 5)

- [x] 3.1 The `Heartbeat:` line's rendering does not change, byte-for-byte:
      `Heartbeat: captureActive={bool}, audioActive={bool}, dataFlowing={bool}` — lowercase,
      Information level, once per 5 s window regardless of client count (design D5). Older QA
      supervisor scripts string-match on this (`*"Heartbeat:"*"=false"*`) — do not reformat it.
      **Evidence:** `CaptureHealthMonitor.cs:170` literal format string matches exactly; U7 test
      (`CaptureHealthMonitorTests.cs:213`) asserts the exact byte format.
- [x] 3.2 `DataFlowMonitor.OnChunkReceived()` (`src/OpenWSFZ.Web/DataFlowMonitor.cs:22`) additionally
      stores the current monotonic timestamp (`TimeProvider.GetTimestamp()`, `Volatile.Write` or
      `Interlocked.Exchange` on a `long`) (design D2).
      **Evidence:** `DataFlowMonitor.cs:17-39` — `TimeProvider`-based monotonic timestamp stamped in
      `OnChunkReceived`, confirmed by inspection.
- [x] 3.3 **`lastChunkAgeMs` is NOT reset by `DataFlowMonitor.Reset()`** (`DataFlowMonitor.cs:39`) —
      `Reset()` is called from `Program.cs:1093-1094` on every pipeline restart; the new timestamp
      field must survive that call. Clearing it would hide a #187 failure (restart loop against a
      dead device) from a poller (design D2). It is `null` only before the first chunk of the
      process.
      **Evidence:** `DataFlowMonitor.cs:63-69` doc comment: "Deliberately does NOT clear
      `LastChunkAgeMs`'s underlying timestamp"; `Reset()` body is `_flowing = false` only. Test:
      `DataFlowMonitorTests.cs:73` "Reset() does NOT clear LastChunkAgeMs".
- [x] 3.4 Add three fields to `DaemonStatus` (`src/OpenWSFZ.Web/DaemonStatus.cs`): `bool DataFlowing`,
      `int? LastChunkAgeMs`, `int WatchdogRestartCount`. `LastChunkAgeMs` is computed at request time
      from the monotonic clock, not stored on the snapshot. Wire both `GET /api/v1/status`
      (`WebApp.cs:299-314`) and the initial WebSocket `status` event (`WebSocketHub.cs:296-311`) to
      populate them from the ticker's snapshot / `DataFlowMonitor`'s stored timestamp.
      **Evidence:** `DaemonStatus.cs:79,86,91` — all three fields present with the documented types.
- [x] 3.5 `WatchdogRestartCount`: a process-lifetime counter on the ticker (or wherever `AudioWatchdog`
      now lives), incremented each time the watchdog's threshold fires (design D7). Exposed on
      `GET /api/v1/status` and the initial WebSocket event.
      **Evidence:** `AudioWatchdog.cs:33` `public int RestartCount => Volatile.Read(ref
      _restartCount);`; `AudioWatchdogTests.cs:125,136,159` cover starts-at-0 / increments-by-1 /
      counts-fired-not-successful.
- [x] 3.6 None of the three fields latch. Two other `CaptureActive`/`AudioActive` construction sites
      exist in `WebApp.cs` (around lines 769 and 789, `POST /api/v1/config`-adjacent responses) —
      check whether they also need the new fields for consistency; if they build a fresh
      `DaemonStatus`, they must not reintroduce the amplitude latch.
      **Evidence:** three `new DaemonStatus(` sites in `WebApp.cs` (lines 347, 820, 850, current
      numbering), all three read `AudioActive` from `captureHealthMonitor?.Current` /
      `startSnapshot`/`stopSnapshot` — none reintroduces an independent amplitude computation.
      Checked directly, all three, not just the first.

## 4. One meaning for `audioActive` everywhere (design.md Decision 4 — Captain-ratified Option A)

- [x] 4.1 `audioActive` = the `dataFlowing` value of the most recent completed window, on
      `GET /api/v1/status`, the initial WebSocket `status` event, and the WebSocket `heartbeat` frame.
      It does not latch.
      **Evidence:** REQUIREMENTS.md FR-020 (amended text, see 4.2) + FR-069, and the U6 cross-surface
      tests (§2.4/§5.3).
- [x] 4.2 Amend **FR-020** in `REQUIREMENTS.md` to this definition; remove the `1×10⁻⁶` amplitude
      clause (§6 below).
      **Evidence:** `REQUIREMENTS.md:164` FR-020 text reads "the `dataFlowing` value of the most
      recent completed 5-second evaluation window ... `audioActive` SHALL NOT latch"; no amplitude
      threshold clause remains.
- [~] 4.3 `AudioActivityMonitor` (`src/OpenWSFZ.Web/AudioActivityMonitor.cs`) has no remaining
      consumer once §2.1 and §4.1 land. Design D4 says QA/Developer **may** delete it — this is not
      mandatory for this change to ship, but if deleted: remove its construction/injection through
      `WebApp.Create` (the `audioMonitor` parameter, `WebApp.cs:83`), its `.Reset()` call in
      `RestartPipelineAsync` (`Program.cs:1093`), and its `ChunkReceived` wiring in
      `CaptureManager.StartAsync` (`src/OpenWSFZ.Audio/CaptureManager.cs:100`) that feeds it via
      FR-020's original comment. If NOT deleted this change, leave a one-line note in the PR
      description that it is now dead code, so it isn't mistaken for a second, competing amplitude
      signal by a future change.
      **Not deleted** (legitimate, per this task's own "not mandatory"): `src/OpenWSFZ.Web/
      AudioActivityMonitor.cs` still exists, still constructed and fed
      (`audioMonitor.ObserveSamples(chunk)`, `Program.cs:246`) and reset on restart
      (`Program.cs:1156`), but — checked directly — **nothing reads its value anymore**
      (`grep -rn "audioMonitor\." src/` shows only the two write-side calls, no
      `.ConsumeAndReset()` or equivalent read). It is genuinely dead weight now, exactly as the task
      anticipated. Marked `[~]`, not `[x]`: the task's own "leave a one-line note in the PR
      description" sub-clause was not found in `42cf88f7`'s message on inspection — recorded here
      as the note instead, at archive time, rather than asserted as done.

## 5. Tests (Appendix A)

- [x] 5.1 **U3 Headless watchdog.** Zero clients; a fake `IAudioSource` that stops yielding chunks
      **without throwing**; exactly one restart after 3 windows. With 3 clients over 10 windows:
      exactly 10 ticks and 10 consumes (proves the N-client over-tick regression is fixed).
      **Evidence:** `CaptureHealthMonitorTests.cs:54` "zero clients — exactly one restart after 3
      consecutive silent windows" (U3); `:82` "the watchdog advances exactly once per
      TickOnceAsync call, independent of however many readers observe Current concurrently
      (N-client over-tick regression, U3)".
- [x] 5.2 **U4 `lastChunkAgeMs`.** Not reset by `DataFlowMonitor.Reset()`; `null` before the first
      chunk; monotonic — a wall-clock/`DateTime.UtcNow` change does not affect it (use the injected
      `TimeProvider`, never `DateTime.UtcNow`, for both the write and the read side).
      **Evidence:** `DataFlowMonitorTests.cs:33,42,59,73,108` — null-before-first-chunk, advances
      monotonically with injected clock, resets to ~0 on next chunk, survives `Reset()`, never
      negative even with a backwards-driven fake clock.
- [x] 5.3 **U6 Surfaces agree.** REST `audioActive` == WS initial `status.audioActive` == the value
      carried by the next WS `heartbeat` frame, for the same window.
      **Evidence:** `CaptureHealthCrossSurfaceTests.cs:72,121` — both the agreement and the
      falls-to-false-together cases, explicitly at the full REST/WS integration level (per the
      handoff commit message), not just the ticker level.
- [x] 5.4 **U7 Heartbeat format.** A regex asserting the emitted line matches
      `Heartbeat: captureActive=(true|false), audioActive=(true|false), dataFlowing=(true|false)`
      exactly, lowercase, one per window regardless of client count (0, 1, or N).
      **Evidence:** `CaptureHealthMonitorTests.cs:213,249` — exact-format test and
      one-line-per-window-regardless-of-reader-count test.
- [x] 5.5 A test proving `watchdogRestartCount` increments by exactly 1 per fired watchdog restart and
      is 0 until the first one fires.
      **Evidence:** `AudioWatchdogTests.cs:125,136,159` (see §3.5) plus
      `CaptureHealthMonitorTests.cs:277,293` "WatchdogRestartCount is 0 when no watchdog is wired"
      / "tracks the watchdog's own RestartCount exactly (single source of truth)".
- [x] 5.6 Full existing suite green; in particular, sweep and fix (§1.5) any silent-fake-source
      fixture the new ticker now trips.
      **Evidence:** commit message: "Full existing suite green (Web.Tests 300/300, Daemon.Tests
      621/621, Audio.Tests 19/19 unchanged)."

## 6. Documentation

- [x] 6.1 Amend **FR-020** in `REQUIREMENTS.md` §4.1: `audioActive` no longer means "amplitude above
      1×10⁻⁶ in the last 5 s interval" — it means "the `dataFlowing` value of the most recent
      completed 5-second window, on every surface (REST, initial WebSocket `status`, WebSocket
      `heartbeat`); does not latch." Remove the now-false claim that it mirrors the RMS silence guard
      in `Ft8Decoder.DecodeAsync`.
      **Evidence:** `REQUIREMENTS.md:164`, see §4.2.
- [x] 6.2 Add **FR-067** (capture health is evaluated independently of client connections), **FR-068**
      (live data-flow status fields: `dataFlowing`, `lastChunkAgeMs`, `watchdogRestartCount` on
      `GET /api/v1/status` and the initial WebSocket event), **FR-069** (audio activity has one
      meaning on every surface — the amended FR-020 relationship). Text for all four entries is
      already drafted in this change's REQUIREMENTS.md diff (see this handoff's companion commit) —
      copy/adjust rather than redrafting from scratch if it has drifted from the final implementation.
      **Evidence:** `REQUIREMENTS.md:211-213` — FR-067/068/069 present, text matches the task's own
      description.
- [x] 6.3 Add a `REQUIREMENTS.md` §10 revision-history row for this change, matching the existing row
      format (see FR-063's row for the most recent precedent).
      **Evidence:** `REQUIREMENTS.md:498`, row 1.48, dated 2026-09-24, matches the existing row
      format.
- [x] 6.4 Ensure every new xUnit test's `DisplayName` carries a requirement-ID prefix (traceability
      gate G3); re-run `tools/TraceabilityCheck` and confirm `PASS: all requirements are mapped and
      all references are valid.`
      **Evidence:** every `DisplayName` cited above is FR-067/068/069- or U3/U4/U6/U7-prefixed;
      commit message: "Gate G3 (TraceabilityCheck) PASS."
- [x] 6.5 NFR-021 scan **post-commit**, not pre-commit (the scanner misses uncommitted files).
      **Evidence:** no NFR-021 incident against this change is recorded anywhere in the board or its
      archive; the one NFR-021 incident on record in this period (board, 2026-09-24, a callsign in a
      published chart) is unrelated to this change.

## 7. Verification

- [x] 7.1 Run the full existing test suite (`dotnet test` across all projects); confirm no
      pre-existing test's assertions changed meaning. Note any pre-existing failures explicitly as
      pre-existing (re-run on the unmodified base commit, don't just assert it).
      **Evidence:** commit message test counts (§5.6); no pre-existing-failure note attached, i.e.
      none were carried.
- [x] 7.2 `openspec validate --strict --all` passes; this change's delta spec archives cleanly against
      `audio-capture`.
      **Evidence:** commit message "openspec validate --strict --all: 63/63"; this archive sweep's
      own Task C run (§ below) confirms it archives cleanly.
- [x] 7.3 Gate G10 (`check_test_delay_sync.py`) OK — no new bare `Task.Delay(...)` in the diff; the
      ticker and its tests must use the injected `TimeProvider`.
      **Evidence:** commit message "Gate G10 OK (no new bare Task.Delay)."
- [x] 7.4 Hand back to QA for the live acceptance test L1 (`architect-to-qa-handoff.md` §2) — a real
      30-minute headless run against the standing daemon build, no browser tab open. **L1 cannot
      verify stall recovery itself** (a silent WASAPI stall cannot be induced on demand) — that is
      proven only at the unit level (§5.1, U3). A green L1 must never be reported as "stall recovery
      verified live" (HK-022, HK-026 — design.md's own "Verification philosophy" section says this
      explicitly; do not let a clean live run drift into a stronger claim in review).
      **Evidence:** `qa/capture-self-healing-live-verify/2026-09-25-l1-l4-results.md` — "Verdict: L1
      PASS, L2 PASS, L3 PASS, L4 PASS"; L1 section (§"L1 -- headless heartbeat and status (30 min)")
      does not claim stall recovery, consistent with the HK-022/HK-026 caveat.
- [x] 7.5 Present the diff to the Captain for explicit review (HK-011) before any push. Per HK-010 the
      merge always needs the Captain's explicit sign-off regardless of green CI. QA does not run
      `pre_merge_check.py` as part of this handoff (HK-006 — Captain's initiative only).
      **Evidence:** board (2026-09-24): "#188 and #187 merged to `main` (`42cf88f7`, `9f54e6af`),
      Captain sign-off"; PR #190 merged with Captain sign-off 2026-09-24 ~21:10Z per the same board
      entry.

## 8. Out of scope (recorded, not this change)

- Re-resolving a stale device ID, retry backoff, and the recovery state machine — issue #187,
  `capture-device-reresolution`, which **depends on this change** for its status surface and
  `lastChunkAgeMs` signal. Do not start #187 on a branch based on `main` before this change merges —
  base it on this branch's tip instead (stacked PR, HK-008), or rebase onto `main` once this merges,
  whichever the Developer session finds live at the time.
  **Disposition:** correctly deferred, not dropped — #187 shipped as a stacked branch and merged
  separately (PR #191 → `9f54e6af`), Task D of this archive sweep.
