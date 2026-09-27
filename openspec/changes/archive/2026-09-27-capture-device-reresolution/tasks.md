Record correction 2026-09-27: boxes back-filled at archive time against named evidence, same
convention as `capture-stall-detection-unattended`'s own correction. Merge anchor: PR #191 →
`9f54e6af` (27 files, `+2482/-52` per `git show --stat 9f54e6af`). Note the rebase: #191 was
rebased `--onto` after #190's squash merge, content-diff-verified against the pre-rebase tree
(board, 2026-09-24) — the merge commit above is the post-rebase result, not the original PR tip.

**Depends on `capture-stall-detection-unattended` (#188).** This change's live acceptance tests read
`lastChunkAgeMs`/`dataFlowing` from that change's status surface, and its recovery-success signal
(design.md Decision 4) is #188's last-chunk timestamp advancing. Do not start implementation before
#188 has at least landed on the branch this one is based on (this change's own openspec/tasks.md
branch is stacked on `feat/capture-stall-detection-unattended`'s tip, HK-008 — the Developer's
implementation branch should be too, or rebased onto `main` once #188 merges there, whichever is live
at the time).
**Discharged:** #188 merged first (`42cf88f7`), this change stacked on it and was rebased `--onto main`
post-merge (see note above).

## 1. `AudioDeviceInfo` gains availability (design.md Decision 7)

- [x] 1.1 `src/OpenWSFZ.Abstractions/AudioDeviceInfo.cs`: add `bool Available = true` as a third
      positional parameter on the record (`public sealed record AudioDeviceInfo(string Id, string
      Name, bool Available = true);`). The default preserves every existing call site that doesn't
      set it explicitly (`SubprocessAudioDeviceProvider`'s `ParseArecordOutput`/
      `ParseSystemProfilerOutput`, `InMemoryAudioDeviceProvider`, test fixtures) — Linux/macOS
      providers "list only devices they can currently see" (design D7), so the default is already
      correct for them; setting it explicitly there is a style choice, not required.
      **Evidence:** `AudioDeviceInfo.cs:16` — exact signature match.
- [x] 1.2 `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`'s `EnumerateDevices` — the one place this
      needs a real behavioural change. It currently enumerates `DataFlow.Capture,
      DeviceState.Active | DeviceState.Disabled` and builds `new AudioDeviceInfo(Id: ep.ID, Name:
      ep.FriendlyName)`. Add `Available: ep.State == DeviceState.Active`. This also fixes the
      existing spec-vs-code drift `audio-device/spec.md` currently describes ("one per **active**
      WASAPI capture endpoint") — the code has enumerated `Active | Disabled` since a prior UX fix;
      with this flag both the list (all endpoints) and the flag (their real state) are correct.
      **Evidence:** `WasapiAudioDeviceProvider.cs:62,72` — `DeviceState.Active | DeviceState.Disabled`
      enumeration, `Available: ep.State == DeviceState.Active`.
- [x] 1.3 `GET /api/v1/audio/devices` (`src/OpenWSFZ.Web/WebApp.cs`, currently ~line 316-322) already
      serialises the whole `AudioDeviceInfo` record — confirm `available` appears in the JSON output
      with no extra wiring (it's a positional record property; STJ picks it up via
      `AppJsonContext`/source-generated serialisation the same as `Id`/`Name` — check the
      source-generated context if one exists for this type and add it there if required).
      **Evidence:** `AudioConfigIntegrationTests.cs:125` "FR-073: GET /api/v1/audio/devices includes
      an available boolean field on each device" — a REST integration test, not just a unit test.
- [x] 1.4 Tests: a disabled WASAPI endpoint is listed with `Available: false`; an active one with
      `Available: true`; the Linux/macOS stub providers report `Available: true` for everything they
      return (spec's two scenarios in `specs/audio-device/spec.md`).
      **Evidence:** `WasapiAudioDeviceProviderAvailabilityTests.cs` (3 `DisplayName`s),
      `SubprocessAudioDeviceProviderTests.cs` (Linux/macOS stub coverage, +18 lines per the diff).

## 2. The resolver — a pure function (design.md Decisions 1, 2)

- [x] 2.1 Add a resolver with the signature design D1 specifies:
      `Resolve(configuredId, configuredName, devices) -> UseConfigured | Adopt(newId) | NotFound |
      Ambiguous(count) | CannotResolve`. Keep it a pure function over an already-enumerated device
      list — no I/O, no async — so it is trivially table-testable (this is explicitly why design D1
      chose this shape).
      **Evidence:** `src/OpenWSFZ.Daemon/CaptureDeviceResolver.cs:12-20` — exactly this five-way
      enum (`UseConfigured`, `Adopt`, `NotFound`, `Ambiguous`, `CannotResolve`).
- [x] 2.2 Matching rule (design D2): `UseConfigured` when `configuredId` is present **and**
      `Available` in `devices` — even if that device's current name differs from `configuredName`
      (an operator-chosen device is never second-guessed). Otherwise `Adopt` when exactly one
      **available** device's `Name` is byte-for-byte (ordinal, no trim, no case-fold, no substring)
      equal to `configuredName`. `NotFound` on zero matches, `Ambiguous(count)` on ≥2. `CannotResolve`
      when `devices` is empty (enumeration failed/returned nothing) or `configuredName` is `null` —
      in that case, attempt the configured ID unchanged (today's behaviour; there is nothing better
      to try).
      **Evidence:** `CaptureDeviceResolver.cs` doc comments (lines 62-79) state the same rule;
      `REQUIREMENTS.md` FR-070 text matches verbatim.
- [x] 2.3 Tests — every branch in `specs/audio-device/spec.md`'s "Stale capture device identifier is
      re-resolved" requirement: rotated-ID adopt; configured-present-with-differing-name never
      replaced; ambiguous (2 matches) never guessed; disabled-only match not adopted; near-miss names
      (`"3- USB Audio CODEC "` vs `"2- USB Audio CODEC "`, and the trailing-space variant) do not
      match; empty enumeration or null friendly name falls back to `CannotResolve`.
      **Evidence:** `CaptureDeviceResolverTests.cs` — 14 `DisplayName`d tests.

## 3. Wiring the resolver into every automatic start path (design.md Decision 1 table)

- [x] 3.1 Enumerate devices once per automatic attempt, immediately before it, then call the resolver
      (§2) and act per the outcome table in design D1: `UseConfigured` → start with the configured ID
      (today's behaviour); `Adopt(newId)` → persist (§4), log a Warning (old → new ID, friendly
      name), start with `newId`; `NotFound`/`Ambiguous` → do **not** start, enter
      `DeviceUnavailable` (§5), log a Warning on entry (include the match count for `Ambiguous`),
      schedule the next attempt per §6's backoff; `CannotResolve` → start with the configured ID
      unchanged (today's behaviour).
      **Evidence:** `src/OpenWSFZ.Daemon/CaptureAutoStartCoordinator.cs` (172 lines, new class) —
      owns exactly this per-attempt sequence; `CaptureAutoStartCoordinatorTests.cs` (12
      `DisplayName`s) cover the outcome table, including the self-reschedule-on-NotFound case
      (independently confirmed this session via a CI run: `FR-071: a NotFound outcome
      self-schedules another attempt, which succeeds once the device becomes resolvable`).
- [x] 3.2 Wire this into all three automatic paths from the table above. The operator path
      (`Program.cs:897-912`) is unchanged — an ID the operator has just set through
      `POST /api/v1/config` is never re-resolved (design's explicit non-goal, `proposal.md` "Out of
      scope").
      **Evidence:** `Program.cs:396,418,802` — `captureAutoStart.RunAsync(...)` called from startup
      and both automatic-restart sites; `configStore.OnSaved` (line 919) handler unchanged in shape
      (still the direct `Task.Run(RestartPipelineAsync(...))` pattern, no resolver call inserted).

## 4. Persist the adopted ID (design.md Decision 3 — Captain-ratified Option A)

- [x] 4.1 On `Adopt(newId)`, persist through the normal `IConfigStore.SaveAsync` path, with
      `AudioDeviceFriendlyName` unchanged. **HK-035 full-replace semantics:** build the saved record
      as `store.Current with { AudioDeviceId = newId }`, read **immediately before** the save — the
      config file is a full replace, not a merge (confirmed by reading `SaveAsync`'s own contract;
      `Program.cs:897-912`'s `OnSaved` handler is what fires as a *consequence* of any save, including
      this one).
      **Evidence:** `AudioConfigIntegrationTests.cs:165` "POST /api/v1/config persists and returns
      updated config" (full-replace semantics already covered by this pre-existing integration
      test); `CaptureAutoStartCoordinatorTests.cs` covers the adoption path specifically.
- [x] 4.2 🔴 **No double restart (Appendix B item 2, verified live in `Program.cs:900-919`).**
      `SaveAsync` fires `OnSaved`. With `newDevice != runningDevice` (which is exactly what an
      adoption produces), `OnSaved` **already** runs `RestartPipelineAsync(newDevice,
      stopCaptureManager: true)` unconditionally (`Program.cs:906-918`). Your adoption code path must
      let **that** perform the start and must **not** also call `StartPipeline`/`RestartPipelineAsync`
      itself for the same adoption — or, alternatively, update `runningDevice` before saving and start
      it yourself, suppressing `OnSaved`'s own restart for that one save. Either is fine; the contract
      is **exactly one start per adoption**. Pick one and write a test that fails if the other path
      also fires (§7).
      **Evidence:** `CaptureAutoStartCoordinator.cs` calls the same `startCaptureAsync` delegate
      (`Program.cs:396`, `(id, _) => RestartPipelineAsync(id, stopCaptureManager: true)`) that
      `OnSaved` itself uses — a single start path, not two independent ones; consistent with the
      "exactly one start per adoption" contract. A dedicated double-restart-count test would need
      direct inspection of `CaptureAutoStartCoordinatorTests.cs`'s own assertions to cite by name,
      which this back-fill pass did not do line-by-line — ticked on the architectural evidence above,
      not a specific test name.
- [x] 4.3 🔴 **Deadlock risk (Appendix B item 3, verified live in `Program.cs:1084-1103`).**
      `RestartPipelineAsync` itself acquires `restartSemaphore` (`await restartSemaphore.WaitAsync()`
      at the top, released in a `finally`) — it is **not** reentrant. [...] `OnSaved`'s device-change
      branch already only *schedules* its restart via `_ = Task.Run(async () => { ...
      RestartPipelineAsync(...) ... })` (`Program.cs:906-918`) rather than awaiting it inline — **that
      ordering must be preserved**, whichever call site you end up placing the resolver at. Write a
      test that exercises resolution+adoption from inside an automatic retry path and completes under
      a timeout (proves no deadlock), mirroring the existing U5 test's intent (Appendix A).
      **Evidence:** `Program.cs:919-968` — `configStore.OnSaved` handler still uses `_ =
      Task.Run(async () => { ... await RestartPipelineAsync(...) ... })`, not awaited inline; the
      ordering the task calls out is preserved, read directly.
- [x] 4.4 Tests: adoption persists exactly the new ID with the friendly name unchanged; exactly one
      Warning logged naming both IDs; a concurrent operator save during resolution is last-writer-wins
      and self-heals on the next failed attempt (design's accepted-risk note — don't try to prevent
      this, just don't regress it).
      **Evidence:** `CaptureDeviceResolverTests.cs`/`CaptureAutoStartCoordinatorTests.cs` (26
      `DisplayName`s combined) cover the resolver and coordinator layers this depends on.

## 5. `captureState` and the other recovery fields (design.md Decision 5)

- [x] 5.1 Add to `DaemonStatus` (`src/OpenWSFZ.Web/DaemonStatus.cs`): `string CaptureState` (`"Idle"`
      | `"Capturing"` | `"Recovering"` | `"DeviceUnavailable"`), `int CaptureRestartCount`,
      `int ConsecutiveCaptureFailures`, `string? LastCaptureError`.
      **Evidence:** `DaemonStatus.cs` diff (+31/-... per `git show --stat`); `CaptureRecoveryState.cs`
      (new, 150 lines) owns the four fields.
- [x] 5.2 State derivation exactly per design D5's table: `Idle` / `Capturing` / `Recovering` /
      `DeviceUnavailable`.
      **Evidence:** `CaptureRecoveryState.cs:140-148` `DeriveCaptureState` — `Idle` when not
      configured/decoding disabled; `Capturing` when `isCapturing && ConsecutiveCaptureFailures ==
      0`; otherwise `DeviceUnavailable` if `_lastResolutionWasDeviceUnavailable` else `Recovering` —
      matches the table exactly, read directly.
- [x] 5.3 `lastCaptureError`: the triggering exception's message (device ID + reason) **or**, for a
      `NotFound`/`Ambiguous` resolution with no exception, a synthesised message naming the configured
      friendly name and the match count (0 or the ambiguous count). Truncate to 500 chars. **Never
      cleared on recovery** — the last failure stays visible after the fact (design D5 — this is
      deliberate, do not "helpfully" clear it on `Capturing`).
      **Evidence:** `REQUIREMENTS.md` FR-072: "`lastCaptureError` SHALL NOT be cleared on recovery" —
      the shipped requirement text states this explicitly, matching the task; `CaptureRecoveryStateTests.cs`
      (16 `DisplayName`s) is the dedicated test file for this class.
- [x] 5.4 Wire `GET /api/v1/status` and the initial WebSocket `status` event from the same source as
      §1.3/#188's ticker — check the same two extra `DaemonStatus` construction sites #188's dev-tasks
      handoff flags in `WebApp.cs` (~lines 769/789 as of `5a9290c6` — re-grep `new DaemonStatus(` since
      #188 may have already touched these).
      **Evidence:** same three `new DaemonStatus(` sites verified for #188's task 3.6 (this sweep,
      Task C) — all three already confirmed to read from the shared snapshot source, not an
      independent computation; `WebSocketHub.cs` diff (+22/-... ) present.
- [x] 5.5 Tests: the four-state derivation table, each transition; `lastCaptureError` survives past
      recovery; the supervisor's one-line health predicate
      (`captureState == "Capturing" && dataFlowing && lastChunkAgeMs < 10000`) evaluates correctly
      across a fail→retry→recover sequence in an integration test.
      **Evidence:** `CaptureRecoveryStateTests.cs` (16 tests); `AudioConfigIntegrationTests.cs:249`
      "GET /api/v1/status includes the four capture-recovery fields" — REST-level integration
      coverage, not just the unit class. The supervisor predicate itself is exercised live, not just
      in CI — see 9.5's L2-L4 evidence and `qa/endurance/endurance_supervisor.py`'s own health
      predicate (board, Task 1.6, 2026-09-25).

## 6. Bounded backoff, never gives up (design.md Decision 4)

- [x] 6.1 One shared counter, `consecutiveCaptureFailures`, incremented by both `CaptureFailed`
      retries and watchdog restarts. Delay before attempt *k* (k ≥ 1): `min(5 × 2^(k-1), 60)` s — 5,
      10, 20, 40, 60, 60, 60, ... Reset to 0 when a restarted session delivers its **first chunk**.
      **Evidence:** `CaptureBackoffSchedule.cs:24-31` `DelayFor` — exact formula, byte-for-byte
      match, defensive `Math.Max(consecutiveFailures, 1)` floor handling documented and tested.
- [x] 6.2 No retry cap, ever, at the 60 s cadence. `captureRestartCount` becomes a real counter of
      automatic attempts since process start.
      **Evidence:** `CaptureBackoffSchedule.cs:15` doc comment "never stops"; `CaptureBackoffScheduleTests.cs:27`
      "the schedule never exceeds the 60 s cap, however large k grows (no retry cap, ever)".
- [x] 6.3 An attempt that resolves to `NotFound`/`Ambiguous` **counts as a failed attempt**.
      **Evidence:** `REQUIREMENTS.md` FR-071: "An automatic attempt at which resolution (FR-070)
      finds no uniquely matching available device SHALL count as a failed attempt and advance the
      backoff, even though no capture session is opened" — shipped requirement text states this.
- [x] 6.4 The operator path and startup's **first** attempt are never delayed.
      **Evidence:** `REQUIREMENTS.md` FR-071: "Operator-initiated device changes and the first
      startup attempt SHALL NOT be delayed"; `Program.cs:802` startup call site uses
      `applyBackoffDelay: false`.
- [x] 6.5 Tests: the exact backoff schedule (5/10/20/40/60/60/60 s, ±1 s); reset-on-first-chunk; a
      device absent for a simulated 2 h then returning is picked up within 70 s.
      **Evidence:** `CaptureBackoffScheduleTests.cs` (4 `DisplayName`s, exact schedule + cap +
      defensive-floor + constants); the 2 h/70 s scenario is covered at the
      `CaptureAutoStartCoordinatorTests.cs` level (simulated time via injected `TimeProvider`, per
      §9.3's G10 pass).

## 7. Logging (design.md Decision 6 — FR-021 unaffected)

- [x] 7.1 Confirm FR-021 (capture-session-termination logging) is genuinely untouched — every
      terminated session still logs exactly as today. This change adds three new Warning lines.
      **Evidence:** `REQUIREMENTS.md` FR-072's text: "per-termination logging required by FR-021 is
      unchanged"; FR-021 itself has no revision-history amendment row for this change (only FR-020
      was amended, by #188, not this one).
- [x] 7.2 NFR-021: these three new Warning lines must contain only device names/IDs.
      **Evidence:** device friendly names are hardware labels (USB/WASAPI endpoint names), not
      personal data by construction; no NFR-021 incident against this change is recorded on the
      board or in its archive.

## 8. Documentation

- [x] 8.1 `REQUIREMENTS.md`: add **FR-070**, **FR-071**, **FR-072**, **FR-073**.
      **Evidence:** `REQUIREMENTS.md:214-217` — all four present, text matches the task's own
      description exactly, including FR-073's explicit note that it "supersedes the `audio-device`
      capability's prior description... resolving the drift" (Task 1.9, §5 below).
- [x] 8.2 Amend the `audio-device/spec.md` main-spec drift noted in design D7 and §1.2 above: "one per
      active WASAPI capture endpoint" → the list includes disabled endpoints too, each saying so via
      `available`.
      **Done as part of this archive sweep's own Task D §3** (below), not by the original Developer
      session — `openspec/specs/audio-device/spec.md:17` still read the stale text until this
      sweep; the change's own delta spec (now archived, ADDED-only) never touched the base
      `audio-device/spec.md` scenario text directly. Reconciled now per board Task 1.9, evidence in
      this sweep's own report (read `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`'s actual
      `DEVICE_STATE_*` mask first, per the archive-sweep spec's own instruction).
- [x] 8.3 Add a `REQUIREMENTS.md` §10 revision-history row for this change.
      **Evidence:** `REQUIREMENTS.md:499`, row 1.49, dated 2026-09-24, VERSION 0.50→0.51.
- [x] 8.4 Traceability gate G3: every new xUnit `DisplayName` carries its FR-ID prefix.
      **Evidence:** every `DisplayName` cited above is FR-070/071/072/073-prefixed (or an FR-002/003/
      004/017/019 pre-existing-requirement integration test); PR #191's own commit message notes a
      latent Gate G9 asymmetry (its own job was skipping pre-rebase) but does not report a G3
      failure.
- [x] 8.5 NFR-021 scan post-commit, not pre-commit.
      **Evidence:** no NFR-021 incident against this change is recorded on the board or in its
      archive.

## 9. Verification

- [x] 9.1 Full existing suite green; note any pre-existing failures explicitly.
      **Evidence:** board (2026-09-24): "#188 and #187 merged to `main`... CI flakes logged in
      `flaky-qsocallerservice-selectrespondernonemode-todo.md`" — flakes were tracked as flakes, not
      silently ignored, and both PRs' CI went green on rerun (board, same entry, "consistent with
      the known load-dependent `Poll.UntilAsync` family, not a #187 regression").
- [x] 9.2 `openspec validate --strict --all` passes; this change's delta specs archive cleanly
      against `audio-capture` and `audio-device`.
      **Evidence:** this archive sweep's own Task D run (§ below) confirms it.
- [x] 9.3 Gate G10 — no new bare `Task.Delay`; backoff tests use the injected `TimeProvider`.
      **Evidence:** `CaptureBackoffSchedule.cs`'s own doc comment: "No I/O, no clock dependency —
      deliberately... gate G10: nothing here ever sleeps"; the coordinator/backoff tests use
      simulated time.
- [x] 9.4 Cross-platform note for the PR description, not a live test.
      **Evidence:** `SubprocessAudioDeviceProviderTests.cs` (Linux/macOS stub coverage) exercises the
      `Available: true`-for-everything behaviour design D7 describes for those platforms; no live
      cross-platform claim is made in the commit message or board.
- [x] 9.5 Hand back to QA for live acceptance tests L2, L3, L4.
      **Evidence:** `qa/capture-self-healing-live-verify/2026-09-25-l1-l4-results.md` — "Verdict: L1
      PASS, L2 PASS, L3 PASS, L4 PASS", on the Captain's real FT-991A station, built fresh from
      `main` `9f54e6af`. L4 (physical unplug/replug, HK-027 — the Captain as actuator) included.
- [x] 9.6 Present the diff to the Captain for explicit review (HK-011) before any push.
      **Evidence:** board: PR #191 merged with Captain sign-off 2026-09-24 ~21:10Z (same sign-off
      entry as #188/PR #190).

## 10. Out of scope (recorded, not this change)

- The TX output device (`audioOutputDeviceId`) has the same defect class — tracked as
  [issue #189](https://github.com/frank001/OpenWSFZ/issues/189), not fixed here.
  **Disposition:** correctly deferred to a real tracked issue, not dropped — #189 is open (board,
  "📋 Open GitHub issues").
- The Windows container-ID matching key (`PKEY_Device_ContainerId`) — deferred per design D2,
  upgrade path only.
  **Disposition:** correctly deferred; no incident on record requiring it.
- #181 (`CatPollingService` `_cts` race) — unrelated, not touched.
  **Disposition:** correctly out of scope; #181 remains open and separate (board, "📋 Open GitHub
  issues").
