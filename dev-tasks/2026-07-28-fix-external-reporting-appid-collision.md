# Developer handoff: make the WSJT-X-protocol `AppId` configurable (multi-instance collision)

**Authored by:** QA (per HK-011/HK-015/HK-000), from a live observation during the 2026-07-28
dual-receiver 10m/20m session.
**Branch:** fresh off `main` (same convention as `dev-tasks/2026-07-28-fix-cycle-audio-archive-null-config-crash.md`)
— do not stack on `d001-c4-min-score-sweep`, unrelated work, same merge-blocker concern applies.
**Status:** confirmed root cause, not yet fixed. Not blocking tonight's session (external reporting
was simply disabled again on the second instance once the impact was understood), but confirmed to
have a real functional effect, not merely cosmetic — see §2.
**Priority context**: multi-instance operation (one operator, one antenna split via an RF splitter,
two simultaneous `OpenWSFZ.Daemon.exe` processes each capturing a different band) is a real,
working, Captain-endorsed pattern as of tonight — this bug is the one thing standing between that
setup and clean interop with companion logging programs (GridTracker, and potentially others using
the same WSJT-X UDP protocol family, e.g. JTAlert, N1MM+), and it silently drops real spot data
rather than just misdisplaying it (§2), which pushes this above "nice to have someday."

## 1. Symptom

Running two simultaneous `OpenWSFZ.Daemon.exe` instances tonight — one on the live 10m antenna feed
(28.074 MHz), one on a Voicemeeter-routed SDRuno feed tuned to 20m (14.074 MHz), both correctly
configured with `tx.callsign = "PD2FZ"` and both reporting to the same local GridTracker UDP target
(`127.0.0.1:2237`) — GridTracker's live decode view began clearing itself roughly every 15 seconds
(one FT8 cycle) once the second instance's external reporting was enabled.

## 2. Root cause

`src/OpenWSFZ.Daemon/ExternalReportingService.cs:68`:

```csharp
private const string AppId = "OpenWSFZ";
```

This is the "Id" field of the WSJT-X UDP protocol's `Heartbeat`/`Status`/`Decode` datagrams —
companion programs (GridTracker among them) use it specifically to distinguish between multiple
simultaneously-running protocol-compatible instances, tracking each as an independent station with
its own band/frequency/decode stream. It is a compile-time `const`, identical across every running
instance, with **no config override**.

With two instances broadcasting under the literal same `"OpenWSFZ"` Id to the same target,
GridTracker cannot tell them apart. The most plausible mechanism for the observed clearing: it sees
what looks like a single instance whose reported dial frequency keeps jumping between 28.074 MHz and
14.074 MHz as the two instances' packets interleave, and (reasonably, from its own perspective)
treats each jump as a discontinuity worth clearing its display over.

**Confirmed, not just cosmetic**: the Captain initially accepted the GridTracker display glitch
and left both instances reporting, since GridTracker's live view wasn't load-bearing for tonight's
purpose. Checking PSKReporter directly afterward, though, showed the 20m instance's spots were not
arriving there at all — the collision breaks actual downstream delivery via GridTracker's
forwarding, not just its local display. External reporting on the 20m instance was disabled again
for the remainder of the session once this was confirmed. This raises the priority of this dev-task
somewhat: it isn't only a cosmetic nuisance, it silently drops real reception data that an operator
would reasonably expect to reach PSKReporter.

## 3. Design — add a configurable instance identifier

Add a new field to `ExternalReportingConfig` (`src/OpenWSFZ.Abstractions/ExternalReportingConfig.cs`),
e.g. `InstanceId`, defaulting to `"OpenWSFZ"` for exact backward compatibility with every existing
single-instance session:

```csharp
[JsonConstructor]
public ExternalReportingConfig(
    bool                                    enabled                                = false,
    IReadOnlyList<ExternalReportingTarget>? targets                                = null,
    bool                                    honourInboundCommands                  = false,
    bool                                    restrictExternalRepliesToDecodeFilter  = false,
    string                                  instanceId                             = "OpenWSFZ")
{
    // ...existing assignments...
    InstanceId = instanceId;
}

/// <summary>
/// WSJT-X-protocol "Id" field sent in every outbound Heartbeat/Status/Decode datagram.
/// Defaults to "OpenWSFZ" for single-instance sessions. Operators running more than one
/// simultaneous instance (e.g. two bands via a split antenna) MUST give each instance a
/// distinct value here, or companion programs (GridTracker, JTAlert, etc.) that key off
/// this field to distinguish multiple protocol-compatible instances will not be able to
/// tell them apart (2026-07-28 dual-receiver session finding).
/// </summary>
public string InstanceId { get; init; } = "OpenWSFZ";
```

**Critical — this field needs the exact same STJ-omitted-key guard discipline the whole codebase
just relearned the hard way today** (`dev-tasks/2026-07-28-fix-cycle-audio-archive-null-config-crash.md`):
`ExternalReportingConfig` already has a `[JsonConstructor]` with defaulted parameters (the Lesson
6/D-WFC-001 pattern, confirmed present at `ExternalReportingConfig.cs:75-86`), so adding
`instanceId` as a defaulted constructor parameter following the exact same shape as the four
existing parameters is the correct, already-proven-safe way to do this — do **not** add it as a
bare `{ get; init; } = "OpenWSFZ"` property without a matching constructor parameter default, or it
inherits the identical null-on-omitted-key vulnerability `CycleAudioArchive` had before today's fix.

Then in `ExternalReportingService.cs`:
- Remove the `private const string AppId = "OpenWSFZ";` line.
- Replace every `AppId` reference (currently passed to `WsjtxDatagram.EncodeStatus(AppId, ...)` and
  `WsjtxDatagram.EncodeDecode(AppId, ...)`, `DecodeLoopAsync`/`BuildStatusFields`/wherever else it's
  read) with `_configStore.Current.ExternalReporting.InstanceId`.

No UI is required for this dev-task's minimum scope — set via `POST /api/v1/config` (as used live
tonight for `tx`/`externalReporting`) is sufficient, matching how `Ptt`/`CycleAudioArchive` also
have no Settings-page field today.

## 4. Tests required

- Regression test on `ExternalReportingConfig`'s STJ round-trip: a POST/deserialize body omitting
  `instanceId` must resolve to `"OpenWSFZ"`, not null/empty — same shape as this afternoon's
  `CycleAudioArchive`/`RemoteAccess` regression tests in `ConfigApiNullGuardTests`/`JsonConfigStoreTests`.
- A test asserting `ExternalReportingService` actually uses the configured `InstanceId` in its
  outbound `Heartbeat`/`Status`/`Decode` datagrams rather than a hardcoded value — inspect the
  encoded datagram bytes/fields in the existing `ExternalReportingService` test suite.

## 5. Verification before handing back to QA

- Run two local instances simultaneously (same pattern as tonight: distinct ports, distinct
  `decodeLog.path`, distinct `cycleAudioArchive.directory`) with **distinct** `InstanceId` values,
  both reporting to the same local GridTracker target, and confirm GridTracker's live view no longer
  clears/resets — it should show two independent, stable per-band panes.
- Per §2's open question: with two instances correctly using distinct `InstanceId`s, verify
  PSKReporter (via GridTracker's forwarding) shows accurate, non-cross-contaminated frequency/band
  data for each instance's spots over a several-minute window — this is the check that was
  *not* done tonight and should close out whether the original collision was purely cosmetic.
- Confirm a single-instance session (no `instanceId` configured) is byte-for-byte unaffected —
  this must remain a fully backward-compatible, opt-in change.
