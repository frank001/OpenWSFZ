# QA Review 2 — p2-audio-config (PR #6)

**Reviewer:** QA Gate  
**Date:** 2026-05-20  
**Branch:** `feat/p2-audio-config` → `main`  
**Scope:** Re-review following developer's resolution of all findings in `qa-review.md`

---

## Prior Findings — All Resolved ✅

Every item from `qa-review.md` has been addressed without exception. No further action required on those items.

---

## New Findings

### 🟡 Required Before Merge — Version string exposes the full 40-character git SHA

**File:** `src/OpenWSFZ.Web/AssemblyVersion.cs`

**Observed:**
```json
{
  "state": "Running",
  "version": "0.1.0+77c53732ec2e55db85471ecb31543438f3d07237",
  "audioDevice": null
}
```

**Root cause:** `AssemblyVersion.Resolve()` returns `AssemblyInformationalVersionAttribute.InformationalVersion` verbatim. The .NET SDK populates that attribute as `{Version}+{SourceRevisionId}`, where `SourceRevisionId` is the full 40-character git commit SHA injected at build time. The `+metadata` suffix is valid SemVer 2.0 but is unnecessarily verbose in a REST API response and inconsistent with the display convention used by every other .NET tooling surface.

**Required change — `src/OpenWSFZ.Web/AssemblyVersion.cs`:**

Replace the `Resolve()` method body with the following:

```csharp
private static string Resolve()
{
    var informational = typeof(AssemblyVersion).Assembly
        .GetCustomAttribute<AssemblyInformationalVersionAttribute>()
        ?.InformationalVersion;

    if (informational is not null)
    {
        // Strip build metadata (everything after '+') — the full git SHA is noise
        // in an API response. The clean semver e.g. "0.1.0" is what clients expect.
        var plusIndex = informational.IndexOf('+');
        return plusIndex >= 0 ? informational[..plusIndex] : informational;
    }

    return typeof(AssemblyVersion).Assembly.GetName().Version?.ToString()
           ?? "0.0.0";
}
```

After this change the status response must read:
```json
{ "state": "Running", "version": "0.1.0", "audioDevice": null }
```

**Required test addition — `tests/OpenWSFZ.Web.Tests/AudioConfigIntegrationTests.cs`:**

The existing Task 9.5 test (`GetStatus_IncludesAudioDeviceField`) already hits the endpoint. Add one assertion at the end of that test:

```csharp
// Version must not expose raw build metadata.
doc.RootElement.GetProperty("version").GetString()
   .Should().NotContain("+",
       "the version field must not expose raw build metadata (full git SHA)");
```

---

## Advisory Items (non-blocking — acknowledge or defer with a note)

### A. `InMemoryConfigStore._current` not `volatile`

**File:** `src/OpenWSFZ.Web/WebApp.cs` — `InMemoryConfigStore` inner class

`JsonConfigStore._current` was correctly marked `volatile` in response to QA Review 1. The `InMemoryConfigStore` introduced in the same file has the same structural pattern without the keyword:

```csharp
private AppConfig _current;  // ← not volatile
```

`InMemoryConfigStore` is used in tests and as the default when no persistent store is supplied. The concurrency risk is low in practice, but consistency with `JsonConfigStore` is preferable. Either mark `volatile` or add a `// volatile not required: single-threaded test use only` comment to make the omission deliberate and visible.

---

### B. `Results.BadRequest` (non-generic) remains in `POST /api/v1/config`

**File:** `src/OpenWSFZ.Web/WebApp.cs` — `MapPost("/api/v1/config", ...)`

The happy-path return was correctly updated to `TypedResults.Ok(store.Current)`. The two error returns still use the non-generic form:

```csharp
return Results.BadRequest("Malformed JSON.");
return Results.BadRequest("Missing or empty request body.");
```

`TypedResults.BadRequest<string>(...)` is available. The inconsistency is a style matter and carries no functional risk at this time, but mixing `Results.*` and `TypedResults.*` within a single handler is a maintenance trap. Please either convert both `BadRequest` calls to `TypedResults.BadRequest<string>(...)` or add a comment explaining why the non-generic form is preferred here.

---

## Summary

| # | Severity | File | Issue |
|---|---|---|---|
| 1 | 🟡 Required | `AssemblyVersion.cs` + `AudioConfigIntegrationTests.cs` | Strip `+<sha>` build metadata from version string; add test assertion |
| A | 🔵 Advisory | `WebApp.cs` — `InMemoryConfigStore` | `_current` not `volatile`; acknowledge or fix |
| B | 🔵 Advisory | `WebApp.cs` — `MapPost /api/v1/config` | `Results.BadRequest` vs `TypedResults.BadRequest` inconsistency |

Item 1 is a one-method change plus a single assertion. Advisory items A and B may be deferred with a note in the commit message if the Captain decides they are not worth a separate commit.

**Verdict: 🟡 RETURN FOR MINOR FIX** — address item 1 and this PR is clear to merge.
