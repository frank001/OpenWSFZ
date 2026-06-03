# QA Review — p16-cat-control Round 2 (Post-Fix CI Run)

**Reviewer:** QA  
**Date:** 2026-06-03  
**Branch:** `feat/p16-cat-control`  
**PR:** https://github.com/frank001/OpenWSFZ/pull/20  
**Verdict:** ❌ Return for changes — two CI failures; both are blocking

All three issues from [qa-review.md](qa-review.md) were resolved correctly.
The fix commit (`9173695`) introduced no new defects.
However, the commit exposed two pre-existing problems that the new code
makes visible for the first time.

---

## Blocking Issue 1 — `FR-009` WebSocket test receives `cat_status` instead of `decode`

**Gate:** G1 — Build & Test (ubuntu-latest, windows-latest)

**Error:**
```
Expected doc.RootElement.GetProperty("type").GetString() to be "decode"
but "cat_status" has a length of 10, differs near "cat" (index 0).
  at WebSocketTests.WebSocket_DecodeEventReceived_AfterBroadcast()
     WebSocketTests.cs:line 161
```

### Root cause

`WebTestFactory` extends `WebApplicationFactory<Program>` with no overrides.
`WebApplicationFactory<Program>` boots the full daemon — including `CatPollingService`
— as an in-process hosted service. `WebSocketHub.ActiveSockets` is a **static**
dictionary shared by every `WebApp` instance in the same process.

When `CatConfigApiTests.PostConfig_WithFullCatObject_RoundTrips` POSTs
`cat.enabled = true` with `rigModel = "RigCtld"` pointing at `10.0.0.1:9999`
(unreachable in CI), the following chain fires:

1. `CatPollingService` in `WebTestFactory`'s host reads the updated config.
2. It attempts `TcpClient.ConnectAsync("10.0.0.1", 9999)` — connection refused.
3. Status transitions `Disabled → Error`; `EmitIfChanged` detects the state
   change and calls `CatEventBus.Publish`.
4. `CatEventBus.Publish` calls the static `WebSocketHub.BroadcastCatStatus`.
5. `BroadcastCatStatus` iterates `ActiveSockets` — which includes the real
   socket held open by the concurrently running `WebSocketTests.FR-009` test
   (connected to the entirely separate `RealServerFixture` server).
6. The `cat_status` frame lands on that socket before the `decode` frame the
   test is waiting for.

The scope guard that already protects `AbortAll` was not extended to the
broadcast methods when `CatPollingService` was added.

### Required fix — scope `BroadcastCatStatus` by app scope

`AbortAll(Guid scope)` already demonstrates the correct pattern. Apply the
same scope guard to `BroadcastCatStatus`.

**Step 1 — Carry the scope in `CatEventBus`:**

Change `CatEventBus` from a no-argument instance to one that receives the
`appScope` assigned by `WebApp.Create`:

```csharp
// CatEventBus.cs
public sealed class CatEventBus
{
    private readonly Guid _appScope;

    public CatEventBus(Guid appScope) => _appScope = appScope;

    public void Publish(CatConnectionStatus status, double? dialFrequencyMHz)
        => WebSocketHub.BroadcastCatStatus(_appScope, status, dialFrequencyMHz);
}
```

**Step 2 — Add the scope parameter to `BroadcastCatStatus`:**

```csharp
// WebSocketHub.cs
internal static void BroadcastCatStatus(
    Guid scope, CatConnectionStatus status, double? dialFrequencyMHz)
{
    if (ActiveSockets.IsEmpty) return;

    var payload = new CatStatusPayload(status.ToString(), dialFrequencyMHz);
    var msg     = new WsCatStatusMessage(Type: "cat_status", Payload: payload);
    var json    = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsCatStatusMessage);
    var bytes   = Encoding.UTF8.GetBytes(json);
    var segment = new ArraySegment<byte>(bytes);

    foreach (var (ws, socketScope) in ActiveSockets)
    {
        if (socketScope != scope) continue;   // ← scope guard
        _ = SendWithTimeoutAsync(ws, segment);
    }
}
```

**Step 3 — Pass the scope when constructing `CatEventBus` in `Program.cs`:**

```csharp
// Program.cs  (the appScope is already computed inside WebApp.Create;
// it must be threaded out to the caller, or CatEventBus must be
// constructed inside WebApp.Create where appScope is already in scope)
```

The cleanest approach: move the `CatEventBus` construction inside
`WebApp.Create` (alongside `catState`) and pass it through to `Program.cs`
via the existing `configureServices` lambda — or return it from `Create`
alongside the `WebApplication`. Use whichever pattern minimises churn.

### Alternative fix (acceptable but carries architectural debt)

Override `WebTestFactory` to remove `CatPollingService` from hosted services:

```csharp
public sealed class WebTestFactory : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            // Remove CatPollingService so CI test runs don't boot a live
            // polling loop that broadcasts to the shared static WebSocketHub.
            var descriptor = services.SingleOrDefault(
                d => d.ImplementationType == typeof(CatPollingService));
            if (descriptor is not null)
                services.Remove(descriptor);
        });
    }
}
```

This prevents the symptom without changing the broadcast architecture.
Noted as debt: the `BroadcastDecodes` and `BroadcastSpectrum` static methods
have the same cross-contamination exposure and should eventually receive the
same scope guard.

---

## Blocking Issue 2 — Gate G3 Traceability: 7 requirements unmapped

**Gate:** G3 — Traceability check (ubuntu-latest)

**Error:**
```
FAIL: 7 requirement(s) not mapped to any test:
  FR-031  FR-032  FR-033  FR-034  NFR-017  NFR-018  NFR-019
```

### Root cause

The traceability tool maps tests to requirements by scanning test display
names for `FR-NNN:` / `NFR-NNN:` tokens. The project convention for product
tests is `FR-NNN: description` (see every existing test in the suite).

The P16 tests were written with `P16-Cat:` prefixes instead. `P16-Cat:` is
the convention for *tool tests* (`P0-Tool:` in `TraceabilityCheck.Tests`),
not for product tests. The tool finds no `FR-031:` token in any test display
name and therefore reports FR-031 as unmapped.

### Required fix — two-part

#### Part A — Rename test display names to `FR-NNN:` prefix

Replace `P16-Cat:` with the relevant requirement ID in every test whose
scenario is traceable to a specific FR. The mapping below covers all 26 tests
across the four new test files.

| Test file | Tests to rename | New prefix |
|---|---|---|
| `CatConfigTests.cs` | All tests (CAT config schema, round-trip, clamping, unknown rigModel) | `FR-031:` |
| `SerialCatConnectionTests.cs` | All tests (ConnectAsync, GetDialFrequency, Disconnect, Dispose) | `FR-032:` |
| `RigctldConnectionTests.cs` | All tests (ConnectAsync, GetDialFrequency, Disconnect, Dispose) | `FR-032:` |
| `CatPollingServiceTests.cs` | Graceful-degradation and retry tests | `FR-034:` |
| `CatPollingServiceTests.cs` | Polling-starts, polling-stops, update-ICatState tests | `FR-032:` |
| `AllTxtWriterTests.cs` (new effective-frequency tests) | CAT-value-takes-precedence, null-falls-back-to-config | `FR-032:` |
| `CatConfigApiTests.cs` | GET/POST /api/v1/config round-trip tests | `FR-031:` |

Example rename:
```csharp
// Before
[Fact(DisplayName = "P16-Cat: ConnectAsync opens the serial port and IsConnected becomes true")]

// After
[Fact(DisplayName = "FR-032: ConnectAsync opens the serial port and IsConnected becomes true")]
```

#### Part B — Add to `traceability-debt.md`

The four requirements below have no unit-test coverage in this change and
should not be expected to have any. Add them to the debt file under a new
`## Pending — Phase 16 (CAT control)` section:

```markdown
## Pending — Phase 16 (CAT control)

FR-033  # CAT status indicator in UI — JavaScript/HTML status bar and badge;
        # verified manually via hardware acceptance gates (tasks 15 & 16).
        # No unit test references this ID. Remove when a UI-layer test is added.

NFR-017 # Secrets scan gate G7 — the gate itself IS the test (gitleaks in CI);
        # no unit test references this ID. Remove when a test with prefix
        # "NFR-017:" is added (or if the gate is ever made a unit-testable concern).

NFR-018 # Decode parity — v1.0 release gate; enforced by the real-signal fixture
        # integration tests (FR-029). No separate "NFR-018:" test exists.
        # Remove when a test explicitly prefixes "NFR-018:".

NFR-019 # Brand neutrality — policy requirement; no automated test is feasible.
        # Enforced by code review. Remove if a lint/grep-based test is added.
```

---

## Summary Checklist for Developer

Before requesting a re-review, confirm each item:

**Issue 1 — WebSocket cross-contamination:**
- [ ] Either (a) `BroadcastCatStatus` is scoped by `appScope` matching the
  pattern already used in `AbortAll`, **OR** (b) `WebTestFactory` overrides
  `ConfigureWebHost` to remove `CatPollingService` from hosted services
- [ ] `FR-009` passes locally: `dotnet test --filter "FR-009"` green

**Issue 2 — Traceability:**
- [ ] All 26 P16 test display names use `FR-NNN:` prefix (not `P16-Cat:`)
  per the mapping table above
- [ ] `traceability-debt.md` includes `FR-033`, `NFR-017`, `NFR-018`,
  `NFR-019` under a `## Pending — Phase 16` section
- [ ] Gate G3 passes locally: run the TraceabilityCheck tool and confirm
  0 unmapped requirements

**Regression guard:**
- [ ] Full test suite still green: `dotnet test -c Release` — 0 failed
- [ ] Push to branch and wait for all three CI legs (Windows, Linux, macOS)
  to go green before requesting re-review
