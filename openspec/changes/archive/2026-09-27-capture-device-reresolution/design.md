# Design — re-resolving a stale capture device ID (#187)

## Context

There are three automatic capture-start paths today, and all of them trust `configStore.Current.AudioDeviceId`:

| Path | Where | Trigger |
|---|---|---|
| Startup auto-start | `Program.cs:742-744` | daemon start, with a device configured and decoding enabled |
| `CaptureFailed` retry | `Program.cs:361-395` | the capture task threw, or ended without cancellation |
| Watchdog restart | `Program.cs:401-420` | 3 × 5 s windows without a chunk (made headless by #188) |

A fourth path, the operator changing the device through `POST /api/v1/config` (`Program.cs:897-912`),
is **not automatic** and is deliberately left alone.

All automatic paths funnel into `RestartPipelineAsync(device, …)` (`Program.cs:1084`) or
`StartPipeline(device)`, serialised by `restartSemaphore` (B2).

## Decision 1 — one resolver, called by every automatic path

**Chosen:** a pure function over an enumerated device list, which is trivial to table-test:

```
Resolve(configuredId, configuredName, devices) →
    UseConfigured                 configuredId is present in devices and Available
  | Adopt(newId)                  configuredId absent/unavailable; exactly one Available
                                  device has Name == configuredName (ordinal, byte-exact)
  | NotFound                      configuredId absent/unavailable; zero Available name matches
  | Ambiguous(count)              configuredId absent/unavailable; ≥2 Available name matches
  | CannotResolve                 enumeration returned empty, or configuredName is null
```

The daemon enumerates **once per automatic attempt**, immediately before it. At the 5 s floor that is
at most one enumeration every 5 s, and at the 60 s cap one a minute. `WasapiAudioDeviceProvider`
already runs on its own STA thread and never throws.

Handling per outcome:

| Outcome | Action |
|---|---|
| `UseConfigured` | Start with the configured ID. This is today's behaviour. |
| `Adopt(newId)` | Persist (D3), log a Warning with old → new, and start with `newId`. |
| `NotFound` / `Ambiguous` | Do **not** start. Enter `DeviceUnavailable`, log a Warning on entry (with the count for `Ambiguous`), and schedule the next attempt per D4. |
| `CannotResolve` | Start with the configured ID. This is today's behaviour: without a device list or a name, there is nothing better to try. |

## Decision 2 — the matching rule: exact name, active endpoints only, unique, never guess

| Alternative | Verdict |
|---|---|
| Fuzzy or substring match (`"USB Audio CODEC"`) | **Rejected.** Windows numbers duplicate device names (`"2- USB Audio CODEC"`), and the FT-991A exposes CODEC endpoints for both directions. **Capturing the wrong radio silently is worse than capturing nothing loudly.** A wrong device corrupts every downstream figure, and nothing marks it as wrong. |
| Trim or normalise whitespace | **Rejected.** The real name carries a trailing space (`"Microphone (2- USB Audio CODEC )"`). The stored name came from the same enumeration, so a byte-exact compare is correct. |
| Accept a *disabled* endpoint with the right name | **Rejected.** Capture cannot open it. It would turn `DeviceUnavailable` into an opaque failure loop. |
| Pick the first of several matches | **Rejected** for the same wrong-radio reason. |
| **Windows container ID** (`PKEY_Device_ContainerId`) as the stable key | **Deferred, not rejected.** It is probably more stable than the name, because the name's `"2-"` prefix can itself renumber. But it needs a new config field and is WASAPI-only. The observed incident (name unchanged) is fully covered by name matching. This is the upgrade path **if** a future incident shows the name changing. |

**Honest limit.** If Windows renumbers the name prefix during the same event that rotates the GUID
(`"2- USB Audio CODEC"` → `"3- USB Audio CODEC"`), name matching finds nothing, and the daemon enters
`DeviceUnavailable` **loudly**. That is still a strict improvement: today the same event is silent. It is
not a fix. The incident on record did not do this, but only one incident is on record.

If the configured ID is present and available, it is used **even if its current name differs from
the stored name**. An endpoint the operator chose explicitly is never second-guessed.

## Decision 3 — persist the adopted ID (✅ CAPTAIN RATIFIED option A, 2026-09-24)

| Option | Consequence |
|---|---|
| **A (recommended) — persist** through the normal `IConfigStore.SaveAsync` | `config.json`, the Settings page and the next startup all agree with the device actually in use. The existing "capture starts with `AppConfig.AudioDeviceId`" requirement stays literally true. **The existing `OnSaved` device-change transition then performs the restart**, so there is one restart path, not two. |
| B — in-memory override only | `config.json` is never written by recovery. But the Settings page shows an ID that no longer exists. Every later automatic start re-resolves. A second "effective device ID" must be threaded through status, logs and restart paths, and the existing startup requirement becomes false. |

**Recommendation: A.** The daemon already writes `config.json` on operator saves and on shutdown.
Persisting one corrected ID with the friendly name unchanged is the least surprising outcome.

**Landmines if A is chosen (material for QA):**

1. **No double restart.** `SaveAsync` fires `OnSaved`. With `newDevice != runningDevice` that already
   runs `RestartPipelineAsync(newDevice, stopCaptureManager: true)` (`Program.cs:900-912`). The
   adopting path must let **that** perform the start and must not also start the pipeline itself.
   Alternatively, it updates `runningDevice` before saving and starts it itself. Either is fine.
   Exactly one start per adoption is the contract.
2. **Full-replace semantics (HK-035).** `SaveAsync` replaces the whole config. Build the new record as
   `store.Current with { AudioDeviceId = newId }`, read immediately before the save. A concurrent
   operator save is last-writer-wins. If the operator's stale page then re-posts the old ID, the next
   failure simply re-resolves again. That self-heals and is accepted.
3. **Deadlock risk.** The `CaptureFailed` retry runs under `restartSemaphore` via
   `RestartPipelineAsync`. If adoption calls `SaveAsync` **while holding** the semaphore, and
   `OnSaved`'s restart waits on the same semaphore, then as long as `OnSaved` only *schedules* a
   `Task.Run` (it does today) there is no deadlock. That ordering must be preserved and tested. Do not
   `await` the `OnSaved`-triggered restart while holding the semaphore.

## Decision 4 — bounded backoff, never giving up

One counter, `consecutiveCaptureFailures`, is shared by `CaptureFailed` retries and watchdog restarts.

- The delay before attempt *k* (k = 1, 2, …) is `min(5 × 2^(k−1), 60)` s: **5, 10, 20, 40, 60, 60, …**
- **Reset to 0 when a restarted session delivers its first chunk.** This is observed as the #188
  `DataFlowMonitor` last-chunk timestamp advancing past the attempt's start time. "`StartAsync`
  returned" is not a success signal, because it always returns immediately
  (`CaptureManager.cs:22-38`).
- **No retry cap.** The issue suggested stopping. Keeping on trying is better for this use case. A
  device unplugged at 03:00 and replugged at 07:00 should resume capture by itself, and a 60 s
  cadence costs one enumeration and one open attempt per minute.
- `captureRestartCount` becomes a real, exposed counter: automatic attempts since process start.
- **An attempt that resolves to `NotFound` or `Ambiguous` counts as a failed attempt.** It increments
  both counters and advances the backoff, even though no capture session was opened. Such an
  attempt writes **no** FR-021 termination line, because nothing terminated. So Error-line counts
  undercount attempts in `DeviceUnavailable`, and the counters are the instrument.

The **operator path** (`POST /api/v1/config` device change) and startup's **first** attempt are not
delayed. Backoff applies only to *repeated automatic* attempts.

## Decision 5 — recovery state on the status endpoint

| `captureState` | Meaning |
|---|---|
| `Idle` | Capture is intentionally not running: no device configured, or decoding disabled. |
| `Capturing` | A session is running and `consecutiveCaptureFailures == 0`. A stall shorter than the watchdog threshold shows here, and #188's `dataFlowing` / `lastChunkAgeMs` expose it. |
| `Recovering` | `consecutiveCaptureFailures ≥ 1`, and the last resolution was `UseConfigured`, `Adopt` or `CannotResolve`. The daemon is retrying an endpoint that should exist. |
| `DeviceUnavailable` | The last resolution was `NotFound` or `Ambiguous`. No usable endpoint exists right now. |

Also added: `captureRestartCount` (int), `consecutiveCaptureFailures` (int) and `lastCaptureError`
(string or null; the exception's message, which carries the device ID and the reason, **or**, for a
`NotFound`/`Ambiguous` resolution where no exception exists, a synthesised message naming the
configured friendly name and the match count. It is truncated to 500 chars and never cleared, so the
last failure stays visible after recovery).

A supervisor's health predicate becomes one line:
`captureState == "Capturing" && dataFlowing && lastChunkAgeMs < 10000`.

## Decision 6 — logging stays FR-021-compliant

FR-021 requires a log entry for **every** capture-session termination, and this change does not
weaken that. At the 60 s cap, a dead device therefore writes about 1,440 Error lines a day instead of
about 17,000. In addition, one **Warning** is written per state transition:

- entering `DeviceUnavailable` (reason: not found, or ambiguous with count);
- adoption (`old ID → new ID`, friendly name);
- recovery (`recovered after N attempts, M s without audio`).

These three lines are what a post-run reader greps for. They must not contain anything but device
names and IDs (no NFR-021 exposure: device names are hardware labels, not personal data).

## Decision 7 — `AudioDeviceInfo` carries availability

`AudioDeviceInfo(string Id, string Name)` gains `bool Available = true`. The WASAPI provider sets it
from `ep.State == DeviceState.Active`. The subprocess providers leave it `true`, because they only list
devices they can see. `GET /api/v1/audio/devices` serialises it as `available`.

This also resolves an existing spec-vs-code drift: `audio-device/spec.md` says the list is
"one per **active** WASAPI capture endpoint", but the code has deliberately enumerated
`Active | Disabled` since a UX fix. With the flag, both are true. The list includes disabled devices,
and each one says so.

## Risks

- **Wrong-device adoption.** This is mitigated by exact, unique, active-only matching (D2). The residual risk:
  two physically different devices with byte-identical names, one of them unplugged. Windows's
  `"N-"` numbering normally prevents identical names while both exist, but not after one leaves. It
  is accepted, and logged at Warning with both IDs on every adoption, so it is visible after the fact.
- **The name-prefix renumbering limit** (D2). Loud, not silent. The upgrade path is on record.
- **Cross-platform.** The same code runs on Linux and macOS through `IAudioDeviceProvider`. It is not
  live-tested there.
