**Depends on `capture-stall-detection-unattended` (#188).** This change's live acceptance tests read
`lastChunkAgeMs`/`dataFlowing` from that change's status surface, and its recovery-success signal
(design.md Decision 4) is #188's last-chunk timestamp advancing. Do not start implementation before
#188 has at least landed on the branch this one is based on (this change's own openspec/tasks.md
branch is stacked on `feat/capture-stall-detection-unattended`'s tip, HK-008 — the Developer's
implementation branch should be too, or rebased onto `main` once #188 merges there, whichever is live
at the time).

## 1. `AudioDeviceInfo` gains availability (design.md Decision 7)

- [ ] 1.1 `src/OpenWSFZ.Abstractions/AudioDeviceInfo.cs`: add `bool Available = true` as a third
      positional parameter on the record (`public sealed record AudioDeviceInfo(string Id, string
      Name, bool Available = true);`). The default preserves every existing call site that doesn't
      set it explicitly (`SubprocessAudioDeviceProvider`'s `ParseArecordOutput`/
      `ParseSystemProfilerOutput`, `InMemoryAudioDeviceProvider`, test fixtures) — Linux/macOS
      providers "list only devices they can currently see" (design D7), so the default is already
      correct for them; setting it explicitly there is a style choice, not required.
- [ ] 1.2 `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`'s `EnumerateDevices` — the one place this
      needs a real behavioural change. It currently enumerates `DataFlow.Capture,
      DeviceState.Active | DeviceState.Disabled` and builds `new AudioDeviceInfo(Id: ep.ID, Name:
      ep.FriendlyName)`. Add `Available: ep.State == DeviceState.Active`. This also fixes the
      existing spec-vs-code drift `audio-device/spec.md` currently describes ("one per **active**
      WASAPI capture endpoint") — the code has enumerated `Active | Disabled` since a prior UX fix;
      with this flag both the list (all endpoints) and the flag (their real state) are correct.
- [ ] 1.3 `GET /api/v1/audio/devices` (`src/OpenWSFZ.Web/WebApp.cs`, currently ~line 316-322) already
      serialises the whole `AudioDeviceInfo` record — confirm `available` appears in the JSON output
      with no extra wiring (it's a positional record property; STJ picks it up via
      `AppJsonContext`/source-generated serialisation the same as `Id`/`Name` — check the
      source-generated context if one exists for this type and add it there if required).
- [ ] 1.4 Tests: a disabled WASAPI endpoint is listed with `Available: false`; an active one with
      `Available: true`; the Linux/macOS stub providers report `Available: true` for everything they
      return (spec's two scenarios in `specs/audio-device/spec.md`).

## 2. The resolver — a pure function (design.md Decisions 1, 2)

- [ ] 2.1 Add a resolver with the signature design D1 specifies:
      `Resolve(configuredId, configuredName, devices) -> UseConfigured | Adopt(newId) | NotFound |
      Ambiguous(count) | CannotResolve`. Keep it a pure function over an already-enumerated device
      list — no I/O, no async — so it is trivially table-testable (this is explicitly why design D1
      chose this shape).
- [ ] 2.2 Matching rule (design D2): `UseConfigured` when `configuredId` is present **and**
      `Available` in `devices` — even if that device's current name differs from `configuredName`
      (an operator-chosen device is never second-guessed). Otherwise `Adopt` when exactly one
      **available** device's `Name` is byte-for-byte (ordinal, no trim, no case-fold, no substring)
      equal to `configuredName`. `NotFound` on zero matches, `Ambiguous(count)` on ≥2. `CannotResolve`
      when `devices` is empty (enumeration failed/returned nothing) or `configuredName` is `null` —
      in that case, attempt the configured ID unchanged (today's behaviour; there is nothing better
      to try).
- [ ] 2.3 Tests — every branch in `specs/audio-device/spec.md`'s "Stale capture device identifier is
      re-resolved" requirement: rotated-ID adopt; configured-present-with-differing-name never
      replaced; ambiguous (2 matches) never guessed; disabled-only match not adopted; near-miss names
      (`"3- USB Audio CODEC "` vs `"2- USB Audio CODEC "`, and the trailing-space variant) do not
      match; empty enumeration or null friendly name falls back to `CannotResolve`.

## 3. Wiring the resolver into every automatic start path (design.md Decision 1 table)

The daemon has three automatic capture-start paths, all currently trusting
`configStore.Current.AudioDeviceId` verbatim, plus a fourth (operator `POST /api/v1/config`) that
must NOT be touched by this change:

| Path | Where (as of `origin/main`@`5a9290c6`) |
|---|---|
| Startup auto-start | `src/OpenWSFZ.Daemon/Program.cs:741-744` |
| `CaptureFailed` retry | `Program.cs:361-395` |
| Watchdog restart | `Program.cs:401-420` (the `restartPipeline` delegate #188 wires the ticker to) |
| Operator device change (`POST /api/v1/config`) | `Program.cs:897-912` (`OnSaved`'s device-change transition) — **leave alone, do not re-resolve here** (design's explicit non-goal) |

- [ ] 3.1 Enumerate devices once per automatic attempt, immediately before it, then call the resolver
      (§2) and act per the outcome table in design D1: `UseConfigured` → start with the configured ID
      (today's behaviour); `Adopt(newId)` → persist (§4), log a Warning (old → new ID, friendly
      name), start with `newId`; `NotFound`/`Ambiguous` → do **not** start, enter
      `DeviceUnavailable` (§5), log a Warning on entry (include the match count for `Ambiguous`),
      schedule the next attempt per §6's backoff; `CannotResolve` → start with the configured ID
      unchanged (today's behaviour).
- [ ] 3.2 Wire this into all three automatic paths from the table above. The operator path
      (`Program.cs:897-912`) is unchanged — an ID the operator has just set through
      `POST /api/v1/config` is never re-resolved (design's explicit non-goal, `proposal.md` "Out of
      scope").

## 4. Persist the adopted ID (design.md Decision 3 — Captain-ratified Option A)

- [ ] 4.1 On `Adopt(newId)`, persist through the normal `IConfigStore.SaveAsync` path, with
      `AudioDeviceFriendlyName` unchanged. **HK-035 full-replace semantics:** build the saved record
      as `store.Current with { AudioDeviceId = newId }`, read **immediately before** the save — the
      config file is a full replace, not a merge (confirmed by reading `SaveAsync`'s own contract;
      `Program.cs:897-912`'s `OnSaved` handler is what fires as a *consequence* of any save, including
      this one).
- [ ] 4.2 🔴 **No double restart (Appendix B item 2, verified live in `Program.cs:900-919`).**
      `SaveAsync` fires `OnSaved`. With `newDevice != runningDevice` (which is exactly what an
      adoption produces), `OnSaved` **already** runs `RestartPipelineAsync(newDevice,
      stopCaptureManager: true)` unconditionally (`Program.cs:906-918`). Your adoption code path must
      let **that** perform the start and must **not** also call `StartPipeline`/`RestartPipelineAsync`
      itself for the same adoption — or, alternatively, update `runningDevice` before saving and start
      it yourself, suppressing `OnSaved`'s own restart for that one save. Either is fine; the contract
      is **exactly one start per adoption**. Pick one and write a test that fails if the other path
      also fires (§7).
- [ ] 4.3 🔴 **Deadlock risk (Appendix B item 3, verified live in `Program.cs:1084-1103`).**
      `RestartPipelineAsync` itself acquires `restartSemaphore` (`await restartSemaphore.WaitAsync()`
      at the top, released in a `finally`) — it is **not** reentrant. All three automatic paths call
      into `RestartPipelineAsync` from outside any semaphore they hold themselves, so today there is
      no reentrancy. The risk this change introduces: if resolution/adoption is placed *inside*
      `RestartPipelineAsync`, before its own `StartPipeline(device)` call (a natural place to put it,
      since that's exactly where `device` is about to be used), and the adoption's `SaveAsync` call
      triggers `OnSaved`'s device-change branch, that branch must **not** synchronously `await` its
      own resulting `RestartPipelineAsync` call — doing so would try to re-acquire the
      still-held semaphore from inside the outer call and deadlock. `OnSaved`'s device-change branch
      already only *schedules* its restart via `_ = Task.Run(async () => { ... RestartPipelineAsync(...)
      ... })` (`Program.cs:906-918`) rather than awaiting it inline — **that ordering must be
      preserved**, whichever call site you end up placing the resolver at. Write a test that exercises
      resolution+adoption from inside an automatic retry path and completes under a timeout (proves no
      deadlock), mirroring the existing U5 test's intent (Appendix A).
- [ ] 4.4 Tests: adoption persists exactly the new ID with the friendly name unchanged; exactly one
      Warning logged naming both IDs; a concurrent operator save during resolution is last-writer-wins
      and self-heals on the next failed attempt (design's accepted-risk note — don't try to prevent
      this, just don't regress it).

## 5. `captureState` and the other recovery fields (design.md Decision 5)

- [ ] 5.1 Add to `DaemonStatus` (`src/OpenWSFZ.Web/DaemonStatus.cs`): `string CaptureState` (`"Idle"`
      | `"Capturing"` | `"Recovering"` | `"DeviceUnavailable"`), `int CaptureRestartCount`,
      `int ConsecutiveCaptureFailures`, `string? LastCaptureError`.
- [ ] 5.2 State derivation exactly per design D5's table:
      - `Idle` — no device configured, or decoding disabled.
      - `Capturing` — a session running, `consecutiveCaptureFailures == 0`.
      - `Recovering` — `consecutiveCaptureFailures >= 1` and the last resolution was `UseConfigured`,
        `Adopt`, or `CannotResolve`.
      - `DeviceUnavailable` — the last resolution was `NotFound` or `Ambiguous`.
- [ ] 5.3 `lastCaptureError`: the triggering exception's message (device ID + reason) **or**, for a
      `NotFound`/`Ambiguous` resolution with no exception, a synthesised message naming the configured
      friendly name and the match count (0 or the ambiguous count). Truncate to 500 chars. **Never
      cleared on recovery** — the last failure stays visible after the fact (design D5 — this is
      deliberate, do not "helpfully" clear it on `Capturing`).
- [ ] 5.4 Wire `GET /api/v1/status` and the initial WebSocket `status` event from the same source as
      §1.3/#188's ticker — check the same two extra `DaemonStatus` construction sites #188's dev-tasks
      handoff flags in `WebApp.cs` (~lines 769/789 as of `5a9290c6` — re-grep `new DaemonStatus(` since
      #188 may have already touched these).
- [ ] 5.5 Tests: the four-state derivation table, each transition; `lastCaptureError` survives past
      recovery; the supervisor's one-line health predicate
      (`captureState == "Capturing" && dataFlowing && lastChunkAgeMs < 10000`) evaluates correctly
      across a fail→retry→recover sequence in an integration test.

## 6. Bounded backoff, never gives up (design.md Decision 4)

- [ ] 6.1 One shared counter, `consecutiveCaptureFailures`, incremented by both `CaptureFailed`
      retries and watchdog restarts. Delay before attempt *k* (k ≥ 1): `min(5 × 2^(k-1), 60)` s — 5,
      10, 20, 40, 60, 60, 60, ... Reset to 0 when a restarted session delivers its **first chunk**
      (observed via #188's `DataFlowMonitor` last-chunk timestamp advancing past the attempt's start
      time — **not** "`StartAsync` returned", which always returns immediately regardless of success,
      `CaptureManager.cs:22-38`'s own doc comment says this explicitly).
- [ ] 6.2 No retry cap, ever, at the 60 s cadence — the standing directive "audio capture must always
      be running" (`Program.cs:358`'s existing comment) applies. `captureRestartCount` becomes a real
      counter of automatic attempts since process start (today it's logged and never read,
      `Program.cs:388`).
- [ ] 6.3 An attempt that resolves to `NotFound`/`Ambiguous` **counts as a failed attempt** — it
      increments both counters and advances the backoff, even though no capture session opened and no
      FR-021 termination line is written (nothing terminated). This means Error-line counts undercount
      attempts while in `DeviceUnavailable` — the counters are the instrument, not the log volume.
- [ ] 6.4 The operator path and startup's **first** attempt are never delayed — backoff applies only
      to *repeated automatic* attempts.
- [ ] 6.5 Tests: the exact backoff schedule (5/10/20/40/60/60/60 s, ±1 s, via the injected
      `TimeProvider` — see #188's dev-tasks for the established pattern, do not introduce a second
      time-handling convention); reset-on-first-chunk; a device absent for a simulated 2 h then
      returning is picked up within 70 s of becoming available with no operator action (spec
      scenario).

## 7. Logging (design.md Decision 6 — FR-021 unaffected)

- [ ] 7.1 Confirm FR-021 (capture-session-termination logging) is genuinely untouched — every
      terminated session still logs exactly as today. This change adds, on top of that: one Warning
      on entering `DeviceUnavailable` (reason + match count if `Ambiguous`), one Warning per adoption
      (old ID → new ID, friendly name), one Warning on recovery (attempts, seconds without audio).
- [ ] 7.2 NFR-021: these three new Warning lines must contain only device names/IDs — hardware
      labels, not personal data, so this is not a new NFR-021 exposure surface, but confirm no
      operator-entered free text (e.g. a custom device rename) could smuggle something else in before
      treating this as settled.

## 8. Documentation

- [ ] 8.1 `REQUIREMENTS.md`: add **FR-070** (stale capture device identifier is re-resolved by
      friendly name), **FR-071** (automatic capture restarts use bounded backoff and never stop),
      **FR-072** (capture recovery state on the status endpoint), and **FR-073** (enumerated devices
      report their availability — this one amends the `audio-device` capability, not `audio-capture`).
      Numbering continues from #188's FR-069 (this branch is stacked on #188's tip, so those IDs are
      already reserved in this branch's `REQUIREMENTS.md` — do not renumber if #188's own PR merges
      with a different final FR count before this one does; re-check the tip of `main` and adjust if
      so, per the standing `FT8_SHIM_VERSION`-style renumber caution).
- [ ] 8.2 Amend the `audio-device/spec.md` main-spec drift noted in design D7 and §1.2 above: "one per
      active WASAPI capture endpoint" → the list includes disabled endpoints too, each saying so via
      `available`.
- [ ] 8.3 Add a `REQUIREMENTS.md` §10 revision-history row for this change, matching the established
      format (see #188's row 1.48 for the immediately-preceding precedent). Bump `VERSION` per
      `release-versioning` if this change is judged user-facing on its own merits at implementation
      time (it adds new `captureState`/`available` API surface an operator can observe even without a
      dedicated GUI element — same posture as `cycle-audio-archive`/leader-follower-relay, rows
      1.45/1.46 — but confirm against the final diff, don't assume).
- [ ] 8.4 Traceability gate G3: every new xUnit `DisplayName` carries its FR-ID prefix; re-run
      `tools/TraceabilityCheck`.
- [ ] 8.5 NFR-021 scan post-commit, not pre-commit.

## 9. Verification

- [ ] 9.1 Full existing suite green; note any pre-existing failures explicitly, re-run on the
      unmodified base to confirm they're pre-existing rather than asserting it.
- [ ] 9.2 `openspec validate --strict --all` passes; this change's delta specs archive cleanly against
      `audio-capture` and `audio-device`.
- [ ] 9.3 Gate G10 — no new bare `Task.Delay`; backoff tests use the injected `TimeProvider`.
- [ ] 9.4 Cross-platform note for the PR description, not a live test: the resolver runs only through
      `IAudioDeviceProvider`; on macOS `Id == Name` so it's a no-op; on Linux, `hw:N,M` can also move
      across a replug and name matching applies unchanged. Live verification is Windows-only (design's
      own statement — do not claim cross-platform live coverage that wasn't done).
- [ ] 9.5 Hand back to QA for live acceptance tests L2, L3, L4 (`architect-to-qa-handoff.md` §2) — a
      deterministic stale-ID-at-startup adoption, an unresolvable-device bounded-loud-never-guessed
      run, and a real physical unplug/replug with the Captain as actuator (HK-027 — the human pulls
      the cable, the instrument's own polls determine every timestamp). L4 note: don't run it during a
      live endurance window (WSJT-X on the same physical device has no equivalent recovery).
- [ ] 9.6 Present the diff to the Captain for explicit review (HK-011) before any push. Per HK-010 the
      merge always needs the Captain's explicit sign-off regardless of green CI. QA does not run
      `pre_merge_check.py` as part of this handoff (HK-006).

## 10. Out of scope (recorded, not this change)

- The TX output device (`audioOutputDeviceId`) has the same defect class — tracked as a separate new
  GitHub issue (handoff §1 task 1.7), not fixed here.
- The Windows container-ID matching key (`PKEY_Device_ContainerId`) as a more-stable-than-name
  fallback — deferred per design D2, upgrade path only if a future incident shows the friendly-name
  prefix itself renumbering (`"2-"` → `"3-"`).
- #181 (`CatPollingService` `_cts` race) — a similar lifecycle-class defect, unrelated, not touched.
