# Developer Handoff — N6: `BroadcastDecodes`/`BroadcastAudioOffset`/`BroadcastTxState` lack the scope guard `BroadcastCatStatus` already has

**Date:** 2026-07-09
**Prepared by:** QA Engineer
**Defect ID:** N6 (Low — test-isolation flake only; no production impact, confirmed recurrence)

---

## 1. Context

`openspec/qa-backlog.md` already logs this as **N6**, found 2026-07-06 while reviewing PR #54.
It has now recurred exactly as that entry predicted ("worth doing before this test flakes
again — likely to recur as the Web test suite grows more WS-connecting tests sharing the same
process"): the post-merge CI run for PR #63 (`fix/d-013-...`, commit `bbf9420`) failed
`Build & Test (ubuntu-latest)` on **`WebSocketTests.WebSocket_DecodeEventReceived_AfterBroadcast`**
(`FR-009`) — same test, same failure shape as PR #54's `windows-latest` failure, just a
different platform this time (consistent with a scheduling-timing race, not anything
platform-specific). Confirmed unrelated to D-013's actual changes: that PR's own two earlier
CI runs (both `pull_request` and `push` events) passed on `ubuntu-latest` with identical code;
only the process-lifetime timing differed on the merge-to-main run.

**Root cause:** `WebSocketHub.ActiveSockets` (`src/OpenWSFZ.Web/WebSocketHub.cs:40`) is a
`private static readonly ConcurrentDictionary<WebSocket, Guid>` — shared by *every*
`WebApp`/test-host instance created in the same test process, not scoped per instance.
`BroadcastCatStatus` (`WebSocketHub.cs:443`) already guards against this
(`if (socketScope != scope) continue;` — added explicitly to stop one in-process test host's
`CatPollingService` from broadcasting into a concurrently-running test server's sockets) via
`CatEventBus`, which carries the `appScope` GUID `WebApp.Create` generates. `BroadcastDecodes`,
`BroadcastAudioOffset`, and `BroadcastTxState` never received the same treatment — they iterate
`ActiveSockets` unconditionally and send to every registered socket regardless of which
`WebApp` instance registered it.

Concretely: xUnit runs different test classes in parallel by default. `WebSocketTests`
(`IClassFixture<RealServerFixture>`, a real Kestrel listener) can be mid-connection with an
open socket at the exact moment `AudioOffsetEndpointTests` (`IClassFixture<WebTestFactory>`,
a separate in-memory `WebApp` instance) calls `POST /api/v1/audio-offset`, which fires
`WebSocketHub.BroadcastAudioOffset` — a static call with no notion of "which test's app this
is." That frame lands in `WebSocketTests`' socket receive buffer, and `FR-009`
(`WebSocketTests.cs:186`) naively reads "the very next frame" and assumes it must be the
`decode` event it just triggered. Two sibling tests in the same file already defend against
this exact class of interference with a loop-and-skip pattern (see
`WebSocket_HeartbeatDeliveredWithinSixSeconds`, `WebSocketTests.cs:55-58`, and
`TxState_BroadcastIncludesAutoAnswerEnabledField`, `WebSocketTests.cs:214`) — `FR-009` alone
does not.

**Severity is genuinely low** — a real daemon process hosts exactly one `WebApp` instance, so
there is only ever one scope in production; this is purely a test-process artifact. But it has
now cost two CI runs, and the fix is small and well-precedented (mirror `BroadcastCatStatus`),
so per the Captain's direction this is worth doing properly now rather than deferring again.

---

## 2. Branch

Create a new branch: **`fix/n6-websocket-broadcast-scope-guard`**
Do not commit directly to `main`.

---

## 3. Actions

### 3.1 — `src/OpenWSFZ.Web/WebSocketHub.cs` — add the scope guard to three broadcast methods

Mirror the exact pattern `BroadcastCatStatus` already uses (`WebSocketHub.cs:443-459`): add a
leading `Guid scope` parameter, and change the `foreach` to skip non-matching sockets.

```csharp
// BroadcastDecodes — was: public static Task BroadcastDecodes(IReadOnlyList<DecodeResult> results)
public static Task BroadcastDecodes(Guid scope, IReadOnlyList<DecodeResult> results)
{
    if (ActiveSockets.IsEmpty) return Task.CompletedTask;

    var msg   = new WsDecodeMessage(Type: "decode", Payload: [.. results]);
    var json  = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsDecodeMessage);
    var bytes = Encoding.UTF8.GetBytes(json);
    var segment = new ArraySegment<byte>(bytes);

    var tasks = new List<Task>();
    foreach (var (ws, socketScope) in ActiveSockets)
    {
        if (socketScope != scope) continue;   // scope guard — same pattern as BroadcastCatStatus
        tasks.Add(SendWithTimeoutAsync(ws, segment));
    }

    return Task.WhenAll(tasks);
}
```

Apply the identical `if (socketScope != scope) continue;` guard, plus the new leading `Guid
scope` parameter, to:
- `BroadcastAudioOffset` (`WebSocketHub.cs:498`)
- `BroadcastTxState` (`WebSocketHub.cs:472`)

Update both methods' XML doc `<summary>` — they currently say things like "sends to all
currently connected WebSocket clients" / "no scope guard since TX state is daemon-global";
that reasoning is now superseded and the comment should say so (mirror `BroadcastCatStatus`'s
doc comment explaining *why* the guard exists).

**Leave `BroadcastSpectrum` and `BroadcastQsoReview` unscoped for this task.** They share the
same theoretical gap but have not been observed to cause a failure, and N6 named only these
three methods. If you notice a `BroadcastQsoReview`/`BroadcastSpectrum` test flake in the
future, it is the same mechanism and the same fix — but scope creep beyond what was diagnosed
is not warranted here.

### 3.2 — Bus façades: thread `appScope` through, with a **default** parameter (not required)

`CatEventBus`'s constructor takes `Guid appScope` as a *required* parameter
(`CatEventBus.cs:29`) because it has few call sites. `DecodeEventBus`, `AudioOffsetEventBus`,
and `TxEventBus` do not have that luxury — `AudioOffsetEventBus` alone is directly constructed
via `new AudioOffsetEventBus()` at 15+ call sites across `QsoAnswererServiceTests.cs`,
`QsoCallerServiceTests.cs`, and `GracefulStopDelegationTests.cs`. None of those tests register
a real WebSocket (no `WebApp`/`RealServerFixture` involved), so `BroadcastX`'s
`if (ActiveSockets.IsEmpty) return;` guard short-circuits before the scope check ever runs —
the actual GUID value is irrelevant there. **Give all three constructors a defaulted
parameter** so none of those call sites need to change:

```csharp
// DecodeEventBus.cs
public sealed class DecodeEventBus
{
    private readonly Guid _appScope;
    public DecodeEventBus(Guid appScope = default) => _appScope = appScope;

    public Task Publish(IReadOnlyList<DecodeResult> results)
        => WebSocketHub.BroadcastDecodes(_appScope, results);
}
```

```csharp
// AudioOffsetEventBus.cs
public sealed class AudioOffsetEventBus
{
    private readonly Guid _appScope;
    public AudioOffsetEventBus(Guid appScope = default) => _appScope = appScope;

    public void Publish(int rxHz, int txHz, bool holdTxFreq)
        => WebSocketHub.BroadcastAudioOffset(_appScope, rxHz, txHz, holdTxFreq);
}
```

```csharp
// TxEventBus.cs
public sealed class TxEventBus : ITxEventBus
{
    private readonly Guid _appScope;
    public TxEventBus(Guid appScope = default) => _appScope = appScope;

    public void Publish(string state, string role, string? partner, bool autoAnswerEnabled, string? abortReason = null)
        => WebSocketHub.BroadcastTxState(_appScope, state, role, partner, autoAnswerEnabled, abortReason);

    // PublishQsoReview unchanged — BroadcastQsoReview is out of scope (see 3.1).
}
```

`ITxEventBus`'s interface members are unchanged (no `appScope` in the interface — it's a
constructor concern of the concrete `TxEventBus`, exactly like `CatEventBus` is not exposed
through an interface either).

### 3.3 — `src/OpenWSFZ.Web/WebApp.cs` — accept an externally-supplied scope

`decodeEventBus` is constructed in `Program.cs` at line 201, **before** `WebApp.Create` runs
at line 337 (it feeds the decode pump directly — "Channel 2: decode pump → DecodeEventBus,
direct call, no channel needed" — which is wired up long before the web host exists). For
`DecodeEventBus` to carry the *same* `appScope` GUID that gets tagged onto every socket
`WebApp.Create` accepts, `Program.cs` needs to generate the GUID itself and hand it to both
`DecodeEventBus` and `WebApp.Create`, rather than `WebApp.Create` always minting its own.

Add an optional parameter so every other existing caller (tests, `WebApp.Create(port: 0)`
call sites) is unaffected:

```csharp
// WebApp.cs — Create(...), near the top of the parameter list or alongside the other optional params
Guid? appScope = null,
// ...
{
    // S1: unique scope ID for this WebApp instance — use the caller-supplied value when
    // given (Program.cs generates one up front so DecodeEventBus, constructed before
    // WebApp.Create runs, can carry the same scope), otherwise mint one, as before.
    var scope = appScope ?? Guid.NewGuid();

    // ... replace the remaining uses of the old local `appScope` with `scope` ...
    var catEventBus = new CatEventBus(scope);
    // ...
    app.Lifetime.ApplicationStopping.Register(() => WebSocketHub.AbortAll(scope));
    // ... (the HandleAsync call site passing appScope, ~line 1472, becomes `scope`)
}
```

Rename is mechanical — every existing internal use of the local `appScope` variable becomes
`scope`; only the public parameter is newly named `appScope` (nullable, optional).

### 3.4 — `src/OpenWSFZ.Daemon/Program.cs` — wire the shared scope through

Generate the GUID once, before `decodeEventBus` is constructed (~line 201), and thread it
through to both `decodeEventBus` and the `WebApp.Create` call:

```csharp
// Before decodeEventBus construction (~line 201):
var appScope = Guid.NewGuid();
var decodeEventBus = new DecodeEventBus(appScope);
```

```csharp
// WebApp.Create call (~line 337) — add:
var app = WebApp.Create(
    port,
    appScope: appScope,
    // ... existing arguments unchanged ...
```

```csharp
// configureServices callback (~line 414-415) — construct with the same closed-over appScope
// instead of letting the DI container default-construct these types:
services.AddSingleton<ITxEventBus>(new TxEventBus(appScope));
services.AddSingleton(new AudioOffsetEventBus(appScope));
```

(The `configureServices` lambda already closes over other `Program.cs` locals this same way —
`allTxtWriter`, `loggingPipeline`, `callsignRegionStore`, etc. — so capturing `appScope` here
is consistent with the existing style, not a new pattern.)

No other call site changes: `QsoAnswererService`/`QsoCallerService`'s factory lambdas
(~line 430-459) already resolve `ITxEventBus`/`AudioOffsetEventBus` via
`sp.GetRequiredService<...>()`, which will now return the scoped singletons transparently.

---

## 4. Tests

No test *should* need to change for the fix itself to work — this is a production-code fix,
and `FR-009` will simply stop being flaky because `AudioOffsetEndpointTests`' broadcasts will
no longer reach `WebSocketTests`' sockets (different `WebApp` instances now carry different
scopes). Confirm this empirically:

1. Run `dotnet test --filter "FullyQualifiedName~OpenWSFZ.Web.Tests"` **repeatedly** (say, 10
   times, or use `dotnet test ... --filter ...` in a loop) on your local machine to build
   confidence the flake is actually gone, not just not-observed-this-time. A single green run
   proves nothing given this defect's nature — it only ever failed intermittently.
2. Add one new regression test to `WebSocketTests.cs` if practical: two `RealServerFixture`-
   style hosts (or a `RealServerFixture` + `WebTestFactory` pair, matching the actual
   contamination pattern observed) where one broadcasts a decode/audioOffset/txState event and
   the assertion is that the *other* instance's socket does **not** receive it. This is the
   most direct proof the scope guard works, rather than relying on absence-of-flakiness.
3. **Optional, defense-in-depth:** harden `FR-009` itself with the same loop-and-skip pattern
   `WebSocket_HeartbeatDeliveredWithinSixSeconds` and
   `TxState_BroadcastIncludesAutoAnswerEnabledField` already use (skip frames whose `type` is
   not `"decode"`, up to a short deadline). This is cheap, consistent with the rest of the
   file, and provides a second line of defense if a future, still-unscoped broadcast path
   (`BroadcastQsoReview`, `BroadcastSpectrum`) ever causes the same symptom. Not required for
   this task's acceptance, but recommended.
4. Run the **full** existing suite, not just `OpenWSFZ.Web.Tests` — confirm zero regressions
   in any test that constructs `DecodeEventBus`, `AudioOffsetEventBus`, or `TxEventBus`
   directly (the `Guid appScope = default` defaulting from §3.2 should mean none of those
   ~15+ call sites need edits, but verify the suite compiles and passes as evidence of that,
   not just as an assertion).

---

## 5. Acceptance Criteria

QA will verify all of the following before approving merge:

- [ ] **AC-1:** `BroadcastDecodes`, `BroadcastAudioOffset`, and `BroadcastTxState` all take a
  `Guid scope` parameter and only deliver to sockets whose registered scope matches, mirroring
  `BroadcastCatStatus`'s existing pattern exactly.
- [ ] **AC-2:** `DecodeEventBus`, `AudioOffsetEventBus`, and `TxEventBus` each carry an
  `appScope` GUID (defaulted, not required — see §3.2 rationale) and pass it through to the
  corresponding `WebSocketHub.Broadcast*` call.
- [ ] **AC-3:** `Program.cs` generates one `appScope` GUID and threads the *same* value through
  `decodeEventBus`, `WebApp.Create`, `ITxEventBus`, and `AudioOffsetEventBus` — not four
  independently-generated GUIDs that would defeat the fix.
- [ ] **AC-4:** A concurrently-running second `WebApp`/test-host instance's broadcast does
  **not** reach a different instance's socket (proven by the regression test in §4.2, not just
  asserted).
- [ ] **AC-5:** No existing test's constructor call sites needed to change (defaulted params
  from §3.2 confirmed sufficient) — if any *did* need to change, document why the default
  wasn't viable there.
- [ ] **AC-6:** `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero warnings.
- [ ] **AC-7:** `dotnet test OpenWSFZ.slnx -c Release` — full suite green, **including
  `FR-009`**, run at least 3 times locally to build confidence the specific flake this task
  targets is actually gone (a single green run is not sufficient evidence for an intermittent
  defect).
- [ ] **AC-8:** CI green on all three platforms (this defect's whole reason for existing is
  that it only manifests under real parallel-scheduling timing, which local runs may not
  reproduce as reliably as CI).

---

## 6. References

- `openspec/qa-backlog.md` — **N6** entry (2026-07-06), the original diagnosis this task
  implements; mark it resolved once this merges (QA will do this at close-out, not part of
  this task's diff).
- `src/OpenWSFZ.Web/WebSocketHub.cs` — `BroadcastCatStatus` (line 443) and `AbortAll` (line
  206), the two existing scope-guarded methods this task's three new guards should match
  exactly in style and doc-comment reasoning.
- `src/OpenWSFZ.Web/CatEventBus.cs` — the existing façade pattern (`appScope` constructor
  field) this task extends to `DecodeEventBus`, `AudioOffsetEventBus`, and `TxEventBus`.
- CI run that surfaced the recurrence:
  https://github.com/frank001/OpenWSFZ/actions/runs/29026171025 (`ubuntu-latest`, `Test
  (Release)` step, `WebSocketTests.WebSocket_DecodeEventReceived_AfterBroadcast`).
- Commit `b126e61` ("fix(test): eliminate FR-009 WebSocket broadcast race") — a *different*,
  previously-fixed cause of the same symptom (fire-and-forget send race within a single test,
  fixed by awaiting `BroadcastDecodes`). This task fixes a second, distinct mechanism
  (cross-test static-registry contamination) producing the same symptom shape.
