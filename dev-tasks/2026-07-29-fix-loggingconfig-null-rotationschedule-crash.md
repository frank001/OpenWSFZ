# Developer handoff: `LoggingConfig` missing the STJ-omitted-key guard — partial `logging` object crashes the whole host

**Authored by:** QA (per HK-011/HK-015/HK-000), found live while standing up two `OpenWSFZ.Daemon`
instances for the `external-reporting-single-connection` change's task 7.3 live verification
(2026-07-29 dual-receiver session, real radio on 40m + SDR Uno on 20m).
**Branch:** fresh off `main`, do not stack on any in-flight branch.
**Status:** confirmed root cause, reproduced twice, not yet fixed. Worked around for tonight's
session by setting `logging.fileEnabled: false` — not a real fix, just avoids the crash.
**Priority context:** this is a full, unhandled process crash (`Unhandled exception... Hosting failed
to start` / `BackgroundServiceExceptionBehavior.StopHost`) triggered by the single most ordinary
hand-edit an operator following this project's own "config-only until a later GUI-focused change"
posture would make — turning on file logging by hand in `config.json` without also copying every
other `logging.*` key. No Settings-page control exists for any of `logging.*` today, so **every**
operator who wants file logging is, by construction, editing a partial object by hand. This is the
exact same defect *shape* (`D-WFC-001` / "Lesson 6") this codebase has already found and fixed at
least five times (`CycleAudioArchiveConfig`, `DecodeNoiseSuppressionConfig`, `ExternalReportingConfig`
`InstanceId`/`Role`/`LeaderUrl`/`FollowerUrls`, `TxConfig`, `DecoderConfig`, `PttConfig` —
`dev-tasks/2026-07-12-cat-tx-ptt-null-ptt-config-guard.md`,
`dev-tasks/2026-07-11-decode-noise-suppression-null-config-guard.md`,
`dev-tasks/2026-07-05-d-010-decodelog-null-config-post.md`) — `LoggingConfig` is the one straggler
that was never given the same treatment, despite predating most of those fixes.

## 1. Symptom

Starting `OpenWSFZ.Daemon.exe --config <path>` against a hand-written `config.json` containing:

```json
{ "logging": { "fileEnabled": true, "directory": "logs", "fileLogLevel": "Debug" } }
```

(note: no `rotationSchedule`, `rotationTime`, `rotationDayOfWeek`, or `maxFiles` keys — a perfectly
natural partial edit) produces, within the same second as startup:

```
[ERR] BackgroundService failed
System.ArgumentOutOfRangeException: The value needs to translate in milliseconds to -1 (signifying
an infinite timeout), 0, or a positive integer less than or equal to the maximum allowed timer
duration. (Parameter 'delay')
   at System.Threading.Tasks.Task.ValidateTimeout(TimeSpan timeout, ExceptionArgument argument)
   at System.Threading.Tasks.Task.Delay(TimeSpan delay, TimeProvider timeProvider, CancellationToken cancellationToken)
   at OpenWSFZ.Daemon.Logging.LogRotationService.ExecuteAsync(CancellationToken stoppingToken) in
   D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Daemon\Logging\LogRotationService.cs:line 33
[FTL] The HostOptions.BackgroundServiceExceptionBehavior is configured to StopHost. A
BackgroundService has thrown an unhandled exception, and the IHost instance is stopping.
```

...and the entire daemon process exits. Reproduced identically on two separate instances (different
ports/config paths) in the same session — not a one-off fluke.

## 2. Root cause

`src/OpenWSFZ.Abstractions/LoggingConfig.cs:8-30` is a plain record with C# property initialisers
and **no `[JsonConstructor]`**:

```csharp
public sealed record LoggingConfig
{
    public bool   FileEnabled       { get; init; } = false;
    public string Directory         { get; init; } = "logs";
    public string FileLogLevel      { get; init; } = "Information";
    public string RotationSchedule  { get; init; } = "daily";
    public string RotationTime      { get; init; } = "00:00";
    public string RotationDayOfWeek { get; init; } = "Monday";
    public int    MaxFiles          { get; init; } = 7;
}
```

The class's own doc comment claims "All fields have defaults so existing config.json files without a
`logging` key continue to deserialise without error" — true for a **missing** `logging` key (guarded
separately, at the whole-object level, in `WebApp.cs`'s `POST /api/v1/config` handler and in
`JsonConfigStore.Load`), but false for a **present-but-partial** `logging` object, which is exactly
what a hand-edited `config.json` produces. Per the STJ source-generation quirk this project has
documented repeatedly elsewhere (see the `D-WFC-001`/"Lesson 6" references above): when
`System.Text.Json`'s source generator deserialises a record with **no** `[JsonConstructor]`, any key
absent from the JSON object resolves the corresponding property to its **CLR zero-value**
(`null` for a reference-type `string`, `0` for `int`), silently bypassing the C# property
initialiser shown above. So `{ "fileEnabled": true, "directory": "logs", "fileLogLevel": "Debug" }`
actually deserialises to `RotationSchedule = null`, `RotationTime = null`,
`RotationDayOfWeek = null`, `MaxFiles = 0` — not `"daily"`/`"00:00"`/`"Monday"`/`7` as every doc
comment and the class's own remarks promise.

`src/OpenWSFZ.Daemon/Logging/LogRotationService.cs:21-57` then compounds this:

```csharp
protected override async Task ExecuteAsync(CancellationToken stoppingToken)
{
    var cfg = _configStore.Current.Logging;
    if (!cfg.FileEnabled || cfg.RotationSchedule == "session")
        return;
    while (!stoppingToken.IsCancellationRequested)
    {
        var delay = CalculateNextBoundary(DateTime.UtcNow, cfg) - DateTime.UtcNow;
        // ...
```

```csharp
internal static DateTime CalculateNextBoundary(DateTime utcNow, LoggingConfig cfg) =>
    cfg.RotationSchedule switch
    {
        "hourly" => NextHourly(utcNow),
        "daily"  => NextDaily(utcNow, cfg.RotationTime),
        "weekly" => NextWeekly(utcNow, cfg.RotationDayOfWeek, cfg.RotationTime),
        _        => utcNow.AddDays(36500), // "session" or unknown — effectively never
    };
```

With `RotationSchedule = null`: the early-return guard at line 25 only checks for the literal string
`"session"`, so `null` does **not** trip it — execution falls through into the `while` loop. The
switch's catch-all (intended for the literal `"session"` value, which is guarded above and should
never actually reach the switch) matches `null` too, producing `utcNow.AddDays(36500)` — a delay of
**~100 years**, or roughly 3.15 trillion milliseconds. `Task.Delay`'s maximum is `Int32.MaxValue`
milliseconds (~24.8 days); anything beyond that throws `ArgumentOutOfRangeException` immediately,
which propagates out of `ExecuteAsync` uncaught, which `Microsoft.Extensions.Hosting`'s default
`BackgroundServiceExceptionBehavior.StopHost` treats as fatal — the entire `IHost`, and with it
every other hosted service (decode pipeline, web server, `ExternalReportingService`, everything),
is torn down.

## 3. Design — give `LoggingConfig` the same `[JsonConstructor]` guard every sibling config already has

Follow the exact, already-proven pattern from `CycleAudioArchiveConfig`/`DecodeNoiseSuppressionConfig`
/`ExternalReportingConfig` (all cited above): add a `[JsonConstructor]` with defaulted parameters
matching every existing property default exactly, and assign from those parameters rather than
relying on property initialisers STJ's source generator does not honour for a partial object:

```csharp
[JsonConstructor]
public LoggingConfig(
    bool   fileEnabled       = false,
    string directory         = "logs",
    string fileLogLevel      = "Information",
    string rotationSchedule  = "daily",
    string rotationTime      = "00:00",
    string rotationDayOfWeek = "Monday",
    int    maxFiles          = 7)
{
    FileEnabled       = fileEnabled;
    Directory         = directory;
    FileLogLevel      = fileLogLevel;
    RotationSchedule  = rotationSchedule;
    RotationTime      = rotationTime;
    RotationDayOfWeek = rotationDayOfWeek;
    MaxFiles          = maxFiles;
}
```

**Belt-and-braces, not a substitute for the above:** `LogRotationService.CalculateNextBoundary`'s
catch-all (`_ => utcNow.AddDays(36500)`) is reachable by *any* unrecognised `RotationSchedule` value,
not just `null` — a hand-typed typo (`"Daily"`, `"dialy"`) hits the exact same crash even after the
constructor fix, since the fix only restores the *intended default* for an *omitted* key; it does
nothing for a *present-but-misspelled* value. Consider either (a) clamping the switch's catch-all to
something `Task.Delay`-safe (e.g. `TimeSpan.FromDays(1)` — "come back and check again tomorrow" —
rather than 36500 days), independent of the constructor fix, or (b) validating `RotationSchedule`
against the known set at the `POST /api/v1/config` layer (matching the existing out-of-range-port /
follower-without-leaderUrl rejection pattern in `WebApp.cs`) so a bad value never reaches
`LogRotationService` at all. Recommend (a) regardless of whether (b) is also done — it is the one
change that makes this class of crash structurally impossible rather than merely less likely.

## 4. Tests required

- `LoggingConfig` STJ round-trip regression test: a JSON `logging` object present but omitting
  `rotationSchedule`/`rotationTime`/`rotationDayOfWeek`/`maxFiles` must deserialise to `"daily"`/
  `"00:00"`/`"Monday"`/`7` respectively — not `null`/`null`/`null`/`0` — mirroring the existing
  missing-key-defaults tests for `CycleAudioArchiveConfig`/`ExternalReportingConfig` in
  `OpenWSFZ.Config.Tests`.
- `LogRotationService.CalculateNextBoundary` unit test: an unrecognised/`null` `RotationSchedule`
  must return a boundary within `Task.Delay`'s valid range (e.g. assert the returned delay is
  `<= TimeSpan.FromDays(24)`), not a multi-decade-out date — this is the test that would have caught
  the crash even before the constructor fix, and is the one that survives if a future value is ever
  hand-typed wrong again.
- Integration-level regression: boot a real host (`WebTestFactory` or equivalent) with a `logging`
  object that has `fileEnabled: true` and nothing else, and assert the host actually starts and stays
  up — this is the test that would have caught tonight's crash directly, at the level it actually
  manifested (a full host teardown, not just a bad computed value).

## 5. Verification before handing back to QA

- Confirm the exact repro from §1 (partial `logging` object, `fileEnabled: true`, no rotation keys)
  no longer crashes the host, and that file logging actually activates with the intended `"daily"`
  rotation default.
- Confirm an existing full-schema `config.json` (every `logging.*` key present, as the daemon writes
  on first run) is byte-for-byte unaffected — this must be a purely additive, backward-compatible fix.
- Confirm a deliberately-misspelled `rotationSchedule` (e.g. `"Daily"`) no longer crashes the host
  either, per §3's belt-and-braces recommendation — logs a warning and falls back to a safe cadence
  instead.
