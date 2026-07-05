# Developer Handoff — D-010: NullReferenceException in AllTxtWriter.AppendAsync

**Date:** 2026-07-05
**Prepared by:** QA Engineer
**Defect ID:** D-010 (Medium — open since 2026-07-02, no GitHub issue; tracked only in
`project-state` notes and the Open Defects table)

---

## 1. Context

D-010 was originally observed as a `NullReferenceException` inside
`AllTxtWriter.AppendAsync` during Linux daemon operation — twice, ~21 minutes after a
daemon restart, possibly correlated with a config `POST`. No fix had landed as of
2026-07-05; this write-up is the source-level root-cause analysis and fix, done in lieu
of the "requires source inspection" note in the defect record.

**Root cause — two contributing defects, one in each direction of the data flow:**

**(a) `POST /api/v1/config` can persist a `null` `DecodeLog` (and `Logging`) into the
live config.**
`AppConfig.DecodeLog` and `AppConfig.Logging` are declared as non-nullable, defaulted
properties:

```csharp
// src/OpenWSFZ.Abstractions/AppConfig.cs
public LoggingConfig    Logging   { get; init; } = new();
public DecodeLogConfig  DecodeLog { get; init; } = new();
```

`JsonConfigStore.Load()` already documents and works around a known System.Text.Json
source-generation quirk: when a JSON payload omits a key entirely, the source-generated
deserializer sets the non-nullable init property to `null` instead of falling back to
the `= new()` initialiser:

```csharp
// src/OpenWSFZ.Config/JsonConfigStore.cs, in Load()
// Guard against STJ source-generation overriding the property initialiser
// with null when the "logging" key is absent from older config files.
if (config.Logging is null)
    config = config with { Logging = new LoggingConfig() };

// Same guard for the newer "decodeLog" key ...
if (config.DecodeLog is null)
    config = config with { DecodeLog = new DecodeLogConfig() };
```

This guard exists **only** in `Load()` (the disk-read path at startup). It is **not**
applied in `POST /api/v1/config` (`WebApp.cs`, ~line 300–443), which deserialises the
HTTP request body straight into an `AppConfig` and passes it to `SaveAsync` unguarded:

```csharp
// src/OpenWSFZ.Web/WebApp.cs
config = await request.ReadFromJsonAsync(AppJsonContext.Default.AppConfig, ct);
// ... Cat / Tx / Decoder / RemoteAccess are validated here, Logging/DecodeLog are not ...
await store.SaveAsync(config, ct);
```

`JsonConfigStore.SaveAsync` then does `_current = config` verbatim — no guard there
either. If any client ever POSTs a JSON body that omits the `"decodeLog"` or
`"logging"` key (a stale cached settings payload from an older frontend build, a
hand-crafted API call, a future partial-update client, etc.), `_current.DecodeLog`
becomes `null` in memory for the remainder of the process's life — no restart is needed
to clear it, and no error is surfaced at POST time, since the endpoint returns
`200 OK`.

**(b) Once `DecodeLog` is `null`, four call sites dereference it unguarded, one of
them (`AllTxtWriter`) outside its own `try`/`catch`:**

```csharp
// src/OpenWSFZ.Daemon/AllTxtWriter.cs, AppendAsync — line 63, BEFORE the try block
var config = _configStore.Current.DecodeLog;   // NRE here if DecodeLog is null

if (!config.Enabled || results.Count == 0)      // never reached if the line above threw
    return;
...
try { ... }                                      // catch(Exception) below never sees it
```

The blanket `catch (Exception ex)` lower in the method gives a false impression that
this method is fully fault-isolated (per its own doc comment: "Decode results and
WebSocket broadcast are unaffected (D1)"). It is not — the NRE happens before the try
block opens, and per the every-decode-cycle call pattern in `Program.cs`'s decode pump,
this is on the hot path: it will throw **every single decode cycle** thereafter, not
just once. That matches "twice, 21 min after a daemon restart" as the two log
occurrences QA happened to capture before the session ended, not the full extent of the
fault.

Three other call sites read `.DecodeLog.` and would NRE the same way if reached with a
null config, though none currently sit outside a try/catch the way `AllTxtWriter` does:
- `src/OpenWSFZ.Daemon/AdifLogWriter.cs:101` — `_configStore.Current.DecodeLog.Path`
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs:954` — `.DecodeLog.DialFrequencyMHz`
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:729` — `.DecodeLog.DialFrequencyMHz`

Fixing (a) prevents `DecodeLog` (and `Logging`) from ever becoming null in the first
place, which is the real fix for all four call sites. (b) is still worth doing as
defence in depth for `AllTxtWriter` specifically, since it is the one call site with no
enclosing guard at all.

---

## 2. Branch

Create a new branch: **`fix/d-010-decodelog-null-config-post`**
Do not commit directly to `main`.

---

## 3. Actions

### 3.1 — `src/OpenWSFZ.Web/WebApp.cs` — guard `Logging`/`DecodeLog` in `POST /api/v1/config`

In the `POST /api/v1/config` handler, immediately after the existing `if (config is
null)` early-return (~line 322) and before the Cat/Tx/Decoder/RemoteAccess validation
blocks, add the same null-coalescing guard `JsonConfigStore.Load()` already applies:

```csharp
if (config is null)
    return Results.BadRequest("Missing or empty request body.");

// Guard against the same STJ source-generation quirk documented in
// JsonConfigStore.Load(): a JSON payload that omits "logging" or "decodeLog"
// deserialises those non-nullable properties to null instead of falling back
// to their initialisers. Left unguarded here, a null DecodeLog persists into
// the live in-memory config and crashes every subsequent decode cycle
// (D-010: unguarded NRE in AllTxtWriter.AppendAsync).
if (config.Logging is null)
    config = config with { Logging = new LoggingConfig() };
if (config.DecodeLog is null)
    config = config with { DecodeLog = new DecodeLogConfig() };
```

Place this before the CAT validation block (~line 324) so the rest of the handler's
`config` references are already guarded.

### 3.2 — `src/OpenWSFZ.Daemon/AllTxtWriter.cs` — defence in depth

Move the `DecodeLog` read inside the existing try block (or null-coalesce it) so this
method genuinely cannot throw unguarded, regardless of what future code paths do to
`IConfigStore.Current`:

```csharp
public async Task AppendAsync(DateTime cycleUtc, double dialMhz, IReadOnlyList<DecodeResult> results)
{
    try
    {
        var config = _configStore.Current.DecodeLog;

        if (!config.Enabled || results.Count == 0)
            return;

        var path = config.Path;

        // Create parent directories if they do not exist.
        var dir = System.IO.Path.GetDirectoryName(path);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);

        // Open in append mode (create if absent), write all lines, close (D2).
        await using var writer = new StreamWriter(path, append: true, System.Text.Encoding.ASCII)
        {
            NewLine = "\r\n"
        };

        string date = cycleUtc.ToString("yyMMdd");

        foreach (var result in results)
        {
            string timePart = result.Time.Replace(":", "", StringComparison.Ordinal);
            string timestamp = $"{date}_{timePart}";

            string line = $"{timestamp}     {dialMhz:F3} Rx FT8 {result.Snr,6} {result.Dt,4:F1} {result.FreqHz,4} {result.Message}";
            await writer.WriteLineAsync(line);
        }
    }
    catch (IOException ex)
    {
        _logger.LogWarning(ex,
            "FR-028: Failed to write decode log — {Message}. " +
            "Decode results and WebSocket broadcast are unaffected.", ex.Message);
    }
    catch (UnauthorizedAccessException ex)
    {
        _logger.LogWarning(ex,
            "FR-028: Access denied writing decode log — {Message}. " +
            "Decode results and WebSocket broadcast are unaffected.", ex.Message);
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex,
            "FR-028: Cannot write decode log — {Message}. " +
            "Decode results and WebSocket broadcast are unaffected.", ex.Message);
    }
}
```

Note the `path`/`config.Path` reads move inside the try too, and the two `IOException`/
`UnauthorizedAccessException` log messages drop `path` from the format string (no
longer guaranteed to be assigned if the exception fires before that line) — replace
with the message-only form shown above, or capture `path` defensively with `?? "(unset)"`
if you'd rather keep it in the log line. Either is acceptable; QA will check the log
output is sensible, not the exact wording.

### 3.3 — Do not change `AdifLogWriter.cs` / `QsoAnswererService.cs` / `QsoCallerService.cs`

These three call sites are covered by the 3.1 fix (DecodeLog can no longer become null
via the API), and are out of scope for this defect. Flagging only so the reviewer knows
they were considered and deliberately left alone, not missed.

---

## 4. Tests

**`tests/OpenWSFZ.Web.Tests/` — new test file `ConfigApiNullGuardTests.cs`** (or add to
an existing config-API test file if you find one that better fits the assembly's
convention):

1. **`PostConfig_OmittingDecodeLogKey_DoesNotPersistNullDecodeLog`** — POST a raw JSON
   body (constructed via `StringContent`/`JsonContent`, NOT `new AppConfig() with {...}`
   — the latter always populates `DecodeLog` via the C# initialiser and will not
   reproduce the STJ quirk) that omits the `"decodeLog"` key entirely, e.g.:
   ```json
   { "audioDeviceId": "test-device" }
   ```
   Follow with `GET /api/v1/config` and assert the response's `decodeLog` key is present
   and non-null (or fetch `IConfigStore.Current.DecodeLog` directly via the test
   factory's service provider) — it must equal `new DecodeLogConfig()`, not be absent
   or null.

2. **`PostConfig_OmittingLoggingKey_DoesNotPersistNullLogging`** — same pattern for
   `"logging"`.

**`tests/OpenWSFZ.Daemon.Tests/AllTxtWriterTests.cs`** — add:

3. **`AppendAsync_ConfigStoreReturnsNullDecodeLog_DoesNotThrow`** — construct a fake/stub
   `IConfigStore` (or a minimal test double, matching whatever mocking approach the
   existing tests in this file already use for `IConfigStore`) whose `Current.DecodeLog`
   is `null`, call `AppendAsync`, and assert it completes without throwing (use
   `await FluentActions.Invoking(...).Should().NotThrowAsync()` or the codebase's
   established equivalent). This directly reproduces D-010's crash and proves the 3.2
   fix holds even if some future code path reintroduces a null `DecodeLog`.

---

## 5. Acceptance Criteria

QA will verify all of the following before approving merge:

- [ ] **AC-1:** `POST /api/v1/config` with a JSON body omitting `"decodeLog"` returns
  `200 OK`, and the resulting `IConfigStore.Current.DecodeLog` is a non-null
  `DecodeLogConfig` with default values — never `null`.
- [ ] **AC-2:** Same for `"logging"` → `IConfigStore.Current.Logging` never `null`.
- [ ] **AC-3:** `AllTxtWriter.AppendAsync` does not throw when `IConfigStore.Current.DecodeLog`
  is `null` (defence in depth — verified by test 3.3, independent of AC-1).
- [ ] **AC-4:** All three new tests pass, and no existing test in
  `AllTxtWriterTests.cs`, `DecoderConfigApiTests.cs`, or `CatConfigApiTests.cs`
  regresses.
- [ ] **AC-5:** `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero warnings.
- [ ] **AC-6:** `dotnet test OpenWSFZ.slnx -c Release` — full suite green (845+ tests,
  the pre-existing `FR-009` flaky WebSocket test excepted per established practice).

---

## 6. References

- Defect record: `project-state-2026-07.md`, Open Defects table, D-010 (Medium,
  `OpenWSFZ.Daemon` / `AllTxtWriter`, observed 2026-07-02, no GitHub issue).
- `src/OpenWSFZ.Config/JsonConfigStore.cs` — `Load()`'s existing guard comments are the
  documented precedent for why this STJ behaviour is real and already known in this
  codebase, not a new hypothesis.
- `src/OpenWSFZ.Web/WebApp.cs` — `POST /api/v1/config` handler (~line 300–443); existing
  Cat/Tx/Decoder validation blocks show the established pattern for this handler.
- `src/OpenWSFZ.Daemon/AllTxtWriter.cs` — `AppendAsync`, FR-028.
- Related (not in scope, informational only): `src/OpenWSFZ.Daemon/AdifLogWriter.cs:101`,
  `QsoAnswererService.cs:954`, `QsoCallerService.cs:729` — other `DecodeLog` readers that
  benefit transitively from the 3.1 fix.
