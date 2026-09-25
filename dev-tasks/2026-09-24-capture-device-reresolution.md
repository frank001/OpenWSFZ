# Developer handoff: `capture-device-reresolution` (#187)

**Authored by:** QA (per HK-000/HK-015/HK-011). **Status:** ready for a Developer session, **but
depends on #188 (`capture-stall-detection-unattended`) landing first** — see §0.
**Source:** Architect → QA handoff
`openspec/changes/capture-stall-detection-unattended/architect-to-qa-handoff.md` (§1 task 1.3), plus
`openspec/changes/capture-device-reresolution/{proposal,design,specs/audio-capture/spec,
specs/audio-device/spec}.md` in this branch — read all four before starting, this document does not
repeat their content.
**OpenSpec change:** `openspec/changes/capture-device-reresolution/` (this branch, `openspec validate
--strict --all`: 64/64 counting both #188 and #187). Implements that change's `tasks.md` §1–§9
(QA-authored).
**Decision authority:** Captain ratified C2 (persist the re-resolved device ID — option A) at ~19:00Z
2026-09-24. Recorded in the handoff §0 and in `design.md` Decision 3.
**Branch:** `feat/capture-device-reresolution`, stacked on `feat/capture-stall-detection-unattended`'s
tip (HK-008 — this is a dependent PR, not an independent one; do not base it on `main` directly unless
#188 has already merged there, in which case rebase this branch onto `main` first and re-verify every
line anchor below). **Continue on this branch — do not cut a new one.**

🛑 **QA proposes this diff and stops here (HK-011). QA does not edit `src/`, does not build, does not
run `pre_merge_check.py` (HK-006 — Captain's initiative only).** A separate Developer session
implements this, builds, and runs the existing test suite. The Captain reviews the diff before any
push. QA returns afterward to run live acceptance tests L2/L3/L4 (handoff §2) — that is QA's, not the
Developer's.

Every file:line reference below was re-read on `origin/main`@`5a9290c6` immediately before writing
this document (HK-018/HK-022), matching the values `design.md` itself cites.

## 0. Sequencing — read before touching anything

This change's live tests read `lastChunkAgeMs`/`dataFlowing` from #188's status surface, and its
recovery-success signal (§4 below) is #188's `DataFlowMonitor` last-chunk timestamp advancing. **Do
not implement this change against a tree that doesn't already have #188's ticker, `DaemonStatus`
fields, and `AudioActivityMonitor` disposition settled** — build #188 first (its own dev-tasks handoff,
`dev-tasks/2026-09-24-capture-stall-detection-unattended.md`), confirm its diff, then come back here.
If #188's PR has already merged to `main` by the time you start this one, rebase this branch onto
`main` and re-grep every anchor below — line numbers will have moved.

## 1. What this changes, in one sentence

`config.json`'s `audioDeviceId` is a Windows MMDevice endpoint ID that can rotate on a replug/driver
reinit while the friendly name stays the same; today every automatic capture-start path retries the
dead ID forever with a flat 5 s delay and never recovers. This change adds a pure resolver, called
before every automatic start, that adopts the one uniquely-matching available device by exact
friendly-name match (never guessing), persists the adoption, and replaces the flat retry with a
bounded, never-stopping backoff — plus recovery state on the status endpoint.

## 2. `AudioDeviceInfo.Available` (design.md Decision 7)

- `src/OpenWSFZ.Abstractions/AudioDeviceInfo.cs` — currently `public sealed record
  AudioDeviceInfo(string Id, string Name);`. Add a third positional parameter:
  `bool Available = true`. The default keeps every non-WASAPI call site compiling and correct as-is.
- `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`'s `EnumerateDevices` (the `foreach (var ep in
  endpoints)` loop building `new AudioDeviceInfo(Id: ep.ID, Name: ep.FriendlyName)`) — add
  `Available: ep.State == DeviceState.Active`. This is the **only** provider that needs a real code
  change; `SubprocessAudioDeviceProvider`'s Linux/macOS parsers and `InMemoryAudioDeviceProvider`
  (test double) are correct with the default.
- `GET /api/v1/audio/devices` (`src/OpenWSFZ.Web/WebApp.cs`, ~lines 316-322) already serialises the
  whole record — confirm `available` reaches the JSON response (check
  `AppJsonContext`/source-generated serialisation if this type is source-generated; add it there if
  the new property doesn't show up automatically).
- This also resolves the existing `audio-device/spec.md` drift: the main spec still says "one per
  **active** WASAPI capture endpoint," but the code has enumerated `Active | Disabled` since a prior
  UX fix. With `available`, both the list (all endpoints) and the flag (their real state) become true.

## 3. The resolver (design.md Decisions 1, 2)

A pure function, no I/O:

```
Resolve(configuredId, configuredName, devices) →
    UseConfigured                configuredId present in devices AND that entry's Available == true
  | Adopt(newId)                 configuredId absent/unavailable; exactly one Available entry's Name
                                  == configuredName (ordinal, byte-exact — no trim, no case-fold, no
                                  substring)
  | NotFound                     configuredId absent/unavailable; zero Available name matches
  | Ambiguous(count)             configuredId absent/unavailable; ≥2 Available name matches
  | CannotResolve                devices is empty, or configuredName is null
```

`UseConfigured` applies **even if the matched device's current name differs from `configuredName`** —
an operator-chosen device is never second-guessed by this resolver. Table-test every branch against
`specs/audio-device/spec.md`'s scenarios: rotated-ID adopt; configured-present-with-differing-name
never replaced; ambiguous (2 matches) never guessed, `DeviceUnavailable`; disabled-only match not
adopted; near-miss names (`"Microphone (3- USB Audio CODEC )"` vs the configured `"Microphone (2- USB
Audio CODEC )"`, and the same string minus its trailing space) do not match; empty enumeration or
null friendly name → `CannotResolve` → attempt the configured ID unchanged.

## 4. Wiring — the three automatic paths, and the one path to leave alone

| Path | Where (as of `5a9290c6`) | Touch? |
|---|---|---|
| Startup auto-start | `src/OpenWSFZ.Daemon/Program.cs:741-744` | Yes — resolve before calling `StartPipeline` |
| `CaptureFailed` retry | `Program.cs:361-395` | Yes |
| Watchdog restart (#188's ticker calls into this) | `Program.cs:401-420` | Yes |
| Operator device change, `POST /api/v1/config` | `Program.cs:897-912` (`OnSaved`) | **No — explicit non-goal.** An ID the operator just set is never re-resolved. |

Enumerate devices once per automatic attempt, immediately before it (at the 5 s floor that's at most
one enumeration/5 s; at the 60 s cap, one a minute). Act on the resolver's outcome per §3's table:
`UseConfigured` → start with the configured ID (today's behaviour, unchanged); `Adopt(newId)` →
persist (§5), log a Warning (old ID → new ID, friendly name), start with `newId`; `NotFound`/
`Ambiguous` → do not start, enter `DeviceUnavailable` (§6), log a Warning naming the reason (and
match count for `Ambiguous`), schedule the next attempt per §7's backoff; `CannotResolve` → start with
the configured ID unchanged (today's behaviour).

## 5. Persisting an adopted ID (design.md Decision 3 — two landmines verified live)

Persist through the normal `IConfigStore.SaveAsync`, friendly name unchanged. **HK-035:** build the
saved record as `store.Current with { AudioDeviceId = newId }`, read immediately before the save (full
replace, not a merge).

🔴 **No double restart.** `SaveAsync` fires `OnSaved`. With `newDevice != runningDevice` — exactly
what an adoption produces — `OnSaved` **already, unconditionally** runs
`RestartPipelineAsync(newDevice, stopCaptureManager: true)` (`Program.cs:906-918`). Your adoption code
must let **that** be the one restart, not also trigger its own — or update `runningDevice` before
saving and start the pipeline yourself while suppressing `OnSaved`'s redundant restart for that one
save. Pick one; write a test asserting `CaptureAsync` is called exactly once per adoption (mirrors the
Appendix A "U5" fake-source-call-count pattern).

🔴 **Deadlock risk.** `RestartPipelineAsync` (`Program.cs:1084-1103`) itself acquires
`restartSemaphore` and is not reentrant. If you place resolution/adoption *inside*
`RestartPipelineAsync`, before its own `StartPipeline(device)` call, and the adoption's `SaveAsync`
triggers `OnSaved`'s device-change branch, that branch must keep only *scheduling* its own restart via
`_ = Task.Run(async () => { ... RestartPipelineAsync(...) ... })` (as it already does,
`Program.cs:906-918`) rather than awaiting it inline — otherwise the inner call would try to
re-acquire the still-held semaphore and deadlock. Do not change that `Task.Run` wrapping. Write a test
that exercises resolution+adoption from inside an automatic retry path and completes under a timeout.

## 6. `captureState` and the status endpoint (design.md Decision 5)

Add to `DaemonStatus` (`src/OpenWSFZ.Web/DaemonStatus.cs`): `string CaptureState` (`Idle` |
`Capturing` | `Recovering` | `DeviceUnavailable`), `int CaptureRestartCount`,
`int ConsecutiveCaptureFailures`, `string? LastCaptureError`.

- `Idle` — no device configured, or decoding disabled.
- `Capturing` — a session running, `consecutiveCaptureFailures == 0`.
- `Recovering` — `consecutiveCaptureFailures >= 1`, last resolution was `UseConfigured`, `Adopt`, or
  `CannotResolve`.
- `DeviceUnavailable` — last resolution was `NotFound` or `Ambiguous`.

`lastCaptureError`: the triggering exception's message, or (for `NotFound`/`Ambiguous`, where there is
no exception) a synthesised message naming the configured friendly name and the match count.
Truncate to 500 chars. **Never cleared on recovery** — do not "helpfully" reset it when `captureState`
returns to `Capturing`; the last failure stays visible on purpose.

Wire `GET /api/v1/status` and the initial WebSocket `status` event from the same source. Re-check the
two extra `DaemonStatus` construction sites #188's own dev-tasks handoff flags in `WebApp.cs`
(~lines 769/789 as of `5a9290c6` — #188 may already have touched them; re-grep `new DaemonStatus(`).

A supervisor's health predicate becomes one line:
`captureState == "Capturing" && dataFlowing && lastChunkAgeMs < 10000` — that last pair comes from
#188.

## 7. Bounded backoff, never gives up (design.md Decision 4)

One shared counter, `consecutiveCaptureFailures`, incremented by both `CaptureFailed` retries and
watchdog restarts. Delay before attempt *k* (k ≥ 1): `min(5 × 2^(k-1), 60)` s → 5, 10, 20, 40, 60, 60,
60, ... **Reset to 0 only when a restarted session delivers its first chunk** — observed via #188's
`DataFlowMonitor` last-chunk timestamp advancing past the attempt's start time, **not** "`StartAsync`
returned" (which always returns immediately regardless of success —
`src/OpenWSFZ.Audio/CaptureManager.cs:22-38`'s own doc comment states this explicitly). No cap, ever,
at the 60 s cadence (`Program.cs:358`'s existing "audio capture must always be running" comment).
`captureRestartCount` becomes a real, read counter (today it's logged and never read,
`Program.cs:388`). A `NotFound`/`Ambiguous` resolution counts as a failed attempt and advances the
backoff even though nothing terminated (no FR-021 line) — the counters are the instrument for
attempts in `DeviceUnavailable`, log-line counts will undercount. The operator path and startup's
first attempt are never delayed.

Use #188's established injected-`TimeProvider` convention for the backoff timer, not a second
time-handling approach — do not sleep for real in the tests.

## 8. Logging (design.md Decision 6)

FR-021 (per-termination logging) is unchanged — every terminated session still logs exactly as today.
Add, on top: one Warning on entering `DeviceUnavailable` (reason + match count if `Ambiguous`), one
Warning per adoption (old ID → new ID, friendly name), one Warning on recovery (attempt count, seconds
without audio). These three lines contain only device names/IDs — hardware labels, not personal data,
no new NFR-021 exposure — but don't assume that if a custom operator-entered device rename could ever
carry something else; a quick look is enough, this isn't expected to be a real risk.

## 9. Tests

Mirror `tasks.md` §2/§4.4/§5.5/§6.5 (this change's own tasks.md has the full breakdown; summarised
here):

- Resolver table: every outcome in §3.
- Adoption: persists exactly the new ID, friendly name unchanged; exactly one Warning; concurrent
  operator save during resolution is last-writer-wins and self-heals on the next attempt (accepted,
  don't try to prevent it).
- Exactly one `CaptureAsync` call per adoption (no double restart).
- No deadlock: resolution+adoption from inside an automatic retry path completes under a timeout.
- Backoff schedule 5/10/20/40/60/60/60 s (±1 s via injected `TimeProvider`); reset-on-first-chunk; a
  device absent for a simulated 2 h then returning is picked up within 70 s with no operator action.
- `captureState` four-state derivation, every transition; `lastCaptureError` survives past recovery.
- Full existing suite green.

## 10. Definition of done

- [ ] §2's `AudioDeviceInfo.Available` added; only `WasapiAudioDeviceProvider` needed a real change.
- [ ] §3's resolver is a pure, table-tested function.
- [ ] §4's three automatic paths call it; the operator path (`Program.cs:897-912`) is untouched.
- [ ] §5's persistence: exactly one start per adoption; no deadlock under the semaphore ordering
      described.
- [ ] §6's `captureState`/`captureRestartCount`/`consecutiveCaptureFailures`/`lastCaptureError` wired
      on both `GET /api/v1/status` and the initial WS event; `lastCaptureError` never auto-clears.
- [ ] §7's backoff schedule exact; no retry cap; reset only on first-chunk-after-restart.
- [ ] §8's three new Warning lines added; FR-021 unaffected.
- [ ] §9's tests added and passing; full suite green.
- [ ] Gate G10 OK — no new bare `Task.Delay`.
- [ ] `openspec validate --strict --all` passes.
- [ ] `git diff --stat` against the #188 branch tip (or `main`, if rebased) touches only
      `OpenWSFZ.Abstractions/AudioDeviceInfo.cs`, `OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`,
      `OpenWSFZ.Web/{WebApp.cs,DaemonStatus.cs}`, `OpenWSFZ.Daemon/Program.cs`, and the corresponding
      test projects. **Zero diff under `native/`.**
- [ ] Present the diff to the Captain for explicit review (HK-011) before any push. Per HK-010 the
      merge always needs the Captain's explicit sign-off regardless of green CI.
- [ ] 🛑 **Do not run `pre_merge_check.py`** (HK-006 — Captain's initiative only). **Do not push, do
      not merge.**

Once the diff is ready, control returns to QA for live acceptance tests L2, L3, L4
(`architect-to-qa-handoff.md` §2): a deterministic stale-ID-at-startup adoption (L2), an unresolvable
device — bogus ID and a friendly name matching nothing — loud, bounded, never guessed (L3), and a real
physical unplug/replug with the Captain pulling the cable (L4 — the human is the actuator, not the
sensor, HK-027; every timestamp comes from the instrument's own polls). Don't run L4 during a live
endurance window (WSJT-X shares the physical device and has no equivalent recovery).

## 11. What this handoff does NOT authorize

- 🛑 No push, no merge, no `pre_merge_check.py`.
- 🛑 No work on the TX output device (`audioOutputDeviceId`) — same defect class, different (loud,
  per-attempt) failure mode, tracked as
  [issue #189](https://github.com/frank001/OpenWSFZ/issues/189), not this change.
- 🛑 No Windows container-ID matching key — deferred (design D2), only becomes the upgrade path if a
  future incident shows the friendly-name prefix itself renumbering.
- 🛑 No touching `Program.cs:897-912`'s operator-save path — re-resolution there is explicitly out of
  scope.
- 🛑 No re-litigating Captain-ratified C2 (design D3, Option A — persist) — the FR-070 text already
  reflects it.

## 12. Cross-references

- `openspec/changes/capture-device-reresolution/{proposal,design,specs/audio-capture/spec,
  specs/audio-device/spec}.md` — the full spec this handoff implements `tasks.md` §1–§9 of.
- `openspec/changes/capture-device-reresolution/tasks.md` — QA-authored, section numbers correspond
  1:1 to this document's sections (tasks.md §1 ↔ here §2, §2 ↔ §3, §3 ↔ §4, §4 ↔ §5, §5 ↔ §6, §6 ↔ §7,
  §7 ↔ §8, §8/§9 ↔ this document's §9/§10 combined).
- `dev-tasks/2026-09-24-capture-stall-detection-unattended.md` — #188's handoff; the `TimeProvider`
  convention and the `DaemonStatus` extra-construction-site note both point back here.
- `src/OpenWSFZ.Abstractions/AudioDeviceInfo.cs`, `src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`,
  `src/OpenWSFZ.Web/{WebApp,DaemonStatus}.cs`, `src/OpenWSFZ.Daemon/Program.cs` — every file this
  change touches; line numbers as of `origin/main`@`5a9290c6`, re-grep if the tree has moved.
