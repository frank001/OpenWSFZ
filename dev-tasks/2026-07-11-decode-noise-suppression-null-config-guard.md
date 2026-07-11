# DEV TASK — `POST /api/v1/config` can persist a null `DecodeNoiseSuppression`, silently dropping ALL.TXT/panel/QSO-automation every cycle

**Date:** 2026-07-11
**OpenSpec change:** `decode-noise-suppression` (implementation review) — no spec text changes
needed; this is a code defect in the implementation, not a requirements gap. The relevant
requirement is already correctly specified in
`openspec/changes/decode-noise-suppression/specs/decode-noise-suppression/spec.md` under
"Suppressed decodes are excluded from the decode panel and from QSO-controller eligibility" /
scenario "ALL.TXT is unaffected by suppression" — the bug below causes that requirement to be
violated at runtime.
**Branch:** `feat/decode-noise-suppression`.
**Status:** New. Found during pre-merge code review, confirmed by reproduction (not just static
reading).
**Found by:** QA, reviewing the change end-to-end against `openspec/changes/decode-noise-suppression/`.

---

## Evidence

`tests/OpenWSFZ.Web.Tests/ConfigApiNullGuardTests.cs` already exists in this codebase specifically
to prevent this class of bug (it is named after, and documents, incident **D-010**). It asserts
that `POST /api/v1/config` never persists a `null` `Logging` or `DecodeLog` section even when the
request body omits those keys — because System.Text.Json's source-generated deserializer sets a
non-nullable `init` property to `null` (bypassing its `= new()` initialiser) when the JSON key is
simply absent, rather than raising an error.

I reproduced the same failure mode for the new `DecodeNoiseSuppression` section with a throwaway
test mirroring that file's existing pattern exactly:

```csharp
var content = new StringContent("""{ "audioDeviceId": "test-device" }""", Encoding.UTF8, "application/json");
var postResp = await client.PostAsync("/api/v1/config", content);
postResp.StatusCode.Should().Be(HttpStatusCode.OK);          // passes — the POST is accepted

var getResp = await client.GetAsync("/api/v1/config");
// ...
doc.RootElement.TryGetProperty("decodeNoiseSuppression", out var el).Should().BeTrue();
el.ValueKind.Should().NotBe(JsonValueKind.Null);              // FAILS — comes back JSON null
```

Result: `decodeNoiseSuppression` round-trips as JSON `null`. It was persisted to disk and into the
live `IConfigStore.Current` with no rejection, no warning, nothing.

## Root cause

`src/OpenWSFZ.Web/WebApp.cs`'s `POST /api/v1/config` handler (starting line 331) explicitly guards
two other non-nullable config sections against exactly this quirk, immediately after
`ReadFromJsonAsync`:

```csharp
if (config.Logging is null)
    config = config with { Logging = new LoggingConfig() };
if (config.DecodeLog is null)
    config = config with { DecodeLog = new DecodeLogConfig() };
```

`DecodeNoiseSuppressionConfig.cs`'s own doc comment, and `JsonConfigStore.cs`'s `Load()` method
(lines 136–140), both correctly apply the equivalent guard **for the config-file-read path**:

```csharp
// JsonConfigStore.Load()
if (config.DecodeNoiseSuppression is null)
    config = config with { DecodeNoiseSuppression = new DecodeNoiseSuppressionConfig() };
```

But the same guard was never added to `WebApp.cs`'s `POST /api/v1/config` handler — the path that
handles a live HTTP request, as opposed to reading the file at startup. `JsonConfigStore.SaveAsync`
performs no validation of its own; it serializes and persists whatever `AppConfig` it is handed and
immediately updates `_current` in memory (`JsonConfigStore.cs:75`). So a request that omits the
`decodeNoiseSuppression` key sails straight through to persistence with the section `null`.

**This is not merely a stored-bad-value problem — it breaks the decode pipeline on the very next
cycle.** `Program.cs`'s decode-pump loop (~line 553) calls:

```csharp
var visibleResults = DecodeNoiseSuppressionFilter.Apply(
    results, configStore.Current.DecodeNoiseSuppression, callsignRegionStore);
```

**before** `await allTxtWriter.AppendAsync(cycleStart, dialFreq, results)`. With
`configStore.Current.DecodeNoiseSuppression == null`, `Apply` throws a `NullReferenceException` on
its first property read (`config.SuppressUnknownRegion`). The loop's outer `catch (Exception ex)`
(`Program.cs:570`) swallows this and logs `"Decode error: ..."`, but by then the cycle has already
aborted — `allTxtWriter.AppendAsync` is never reached. **Every decode cycle from that point on
produces nothing at all**: no `ALL.TXT` entry, no decode-panel broadcast, no QSO-controller batch —
until the daemon restarts (`JsonConfigStore.Load()`'s guard would self-heal at that point) or the
operator happens to revisit Settings and hit Save (which always sends the field, repairing it).

This directly violates the change's own spec scenario "ALL.TXT is unaffected by suppression" — in
the broken state ALL.TXT receives *zero* decodes, which is a great deal more than "affected."

**How this would actually get triggered in practice:** the frontend (`web/js/settings.js`)
currently always includes `decodeNoiseSuppression` in its `postConfig(...)` payload, so a
freshly-loaded settings page won't trip this. The realistic trigger is a browser tab left open
across an upgrade (still running the pre-change `settings.js` bundle) hitting Save after the
backend has been upgraded to expect the new field — or any other script/tool that POSTs a partial
config body to this general-purpose local API, which is exactly the scenario the existing
`ConfigApiNullGuardTests.cs` fixture was written to guard against for the other sections.

**Not a pre-existing gap for this section** — `DecodeNoiseSuppressionConfig` is new in this change,
so this guard's omission is this change's responsibility. (Aside, out of scope for this task:
`config.RemoteAccess` has the identical unguarded gap already on `main`, predating this branch —
noted for a separate follow-up, not blocking here.)

## Recommended fix

1. In `src/OpenWSFZ.Web/WebApp.cs`'s `POST /api/v1/config` handler, add the same guard used for
   `Logging`/`DecodeLog`, right alongside them:

   ```csharp
   if (config.DecodeNoiseSuppression is null)
       config = config with { DecodeNoiseSuppression = new DecodeNoiseSuppressionConfig() };
   ```

2. Do not attempt to fix this by adding null-checks inside `DecodeNoiseSuppressionFilter.Apply` or
   at its `Program.cs` call site instead — that would treat the symptom (the crash) without
   preventing the underlying bad state from being written to disk and read back on next load in a
   context that lacks `JsonConfigStore.Load()`'s own guard. Fix it at the same layer the existing
   `Logging`/`DecodeLog` guards already fix it at.

## Tests required

- Extend `tests/OpenWSFZ.Web.Tests/ConfigApiNullGuardTests.cs` with a third case, following the
  existing two exactly (raw JSON via `StringContent`, not `new AppConfig() with {...}`, since the
  latter never reproduces the quirk): POST a body omitting `"decodeNoiseSuppression"`, then GET
  `/api/v1/config` back and assert the section round-trips as a non-null object with the documented
  defaults (`suppressUnknownRegion: null` inside the JSON is fine and expected — the *object itself*
  must not be JSON `null`; assert `suppressSynthetic == true`).
- No change needed to `DecodeNoiseSuppressionFilterTests.cs` or `JsonConfigStoreTests.cs` — both
  already correctly cover their respective layers (the filter's own logic, and the file-load path
  guard). This gap was specifically in the HTTP POST path, which has its own dedicated test file for
  exactly this reason.

## Verification

1. `dotnet build -c Release` / `dotnet test -c Release --no-build` — expect unchanged pass counts
   plus the one new test, all green.
2. Re-run the reproduction from this task manually (or via the new test) and confirm
   `GET /api/v1/config` now returns a populated `decodeNoiseSuppression` object, never `null`, after
   a POST that omits the key.
3. `openspec validate --strict --all` — expect unchanged pass count (no spec text is being
   changed by this fix).

## References

- `src/OpenWSFZ.Web/WebApp.cs:331-364` (`POST /api/v1/config` handler — existing `Logging`/
  `DecodeLog` guards to mirror; fix belongs at line ~364).
- `src/OpenWSFZ.Config/JsonConfigStore.cs:136-140` (the equivalent guard already correctly applied
  to the file-load path — same pattern, different layer).
- `src/OpenWSFZ.Daemon/Program.cs:545-564` (the decode-pump loop; shows why a null config here is
  worse than a stored-bad-value problem — it aborts the cycle before `allTxtWriter.AppendAsync`).
- `src/OpenWSFZ.Abstractions/DecodeNoiseSuppressionConfig.cs` (the new config section; its own doc
  comment already describes the STJ quirk correctly, just wasn't guarded against at this call site).
- `tests/OpenWSFZ.Web.Tests/ConfigApiNullGuardTests.cs` (existing D-010 regression fixture; extend
  this file rather than creating a new one).
- `openspec/changes/decode-noise-suppression/specs/decode-noise-suppression/spec.md`, requirement
  "Suppressed decodes are excluded from the decode panel and from QSO-controller eligibility",
  scenario "ALL.TXT is unaffected by suppression" — the requirement this bug violates at runtime.

## QA re-review

QA will re-run the reproduction (POST omitting `decodeNoiseSuppression`, GET to confirm no null
section persists) directly against the fix, check the new test's assertions rather than just
"tests pass," and confirm the full suite (`dotnet test`, `web/js` `node --test`,
`openspec validate --strict --all`) is still green before sign-off. No re-run of
`qa/decode-filter-synth-verify/live_verify_9_axes.py` is required for this fix alone — it doesn't
touch the suppression predicate or the QSO-controller batch shape, only the config-load guard —
but it remains required before this branch merges per the change's own task 7.1, unless already
satisfied by the existing report at
`qa/decode-filter-synth-verify/live-reports/2026-07-11T173215Z-497e733.md`.
