# Developer handoff: `WebSocketHub.BroadcastSpectrum` is missing the N6 scope guard

**Authored by:** QA, 2026-09-01 (17:40 UTC, `date -u`, HK-017), per HK-000/HK-015.
**Status:** 🔴 Proposal, not approved work in itself (HK-011). A separate Developer session makes
the edit. The Captain reviews the diff and rules on the merge (HK-010) — QA does not declare
readiness. No push, no merge, no `pre_merge_check.py` from this document (HK-006/HK-014).
**Branch:** create a fresh short branch off `main` for the implementation, per the FR-064/R1
precedent — do not ride this on `fix/fr064-heartbeat-race` (scope-locked to that flake) or on this
QA branch (docs-only).
**Discovered:** incidentally, while independently verifying `pre_merge_check.py`'s WSL Debian gate
during the FR-064 pre-merge review (`fix/fr064-heartbeat-race`). Confirmed present on `main`@`75ea2c1`
directly — unrelated to that branch's diff.

---

## 0. The failing test and what it caught

`tests/OpenWSFZ.Web.Tests/WebSocketTests.cs`,
`Broadcast_FromDifferentAppInstance_DoesNotReachThisFixturesSocket` ("N6"). It stands up two
independent `WebApp` instances in the same test process, subscribes a socket to each, publishes a
`decode` event scoped to one instance, and asserts the other instance's socket receives nothing.

Observed failure (reproduced twice, independently, under WSL Debian full-suite parallel load — see
§3):

```
leakedFrame.Should().BeNull(
    "N6: BroadcastDecodes must not deliver to sockets registered under a different app scope");
```
```
Expected leakedFrame to be <null> ... but found
"{"type":"spectrum","payload":[0,0,0,0,0,...]}".
```

The leaked frame is a **`spectrum`** event — not the `decode` event the test itself published. That
is the tell: something is broadcasting spectrum frames to every socket in the process, regardless of
which `WebApp` instance registered them.

## 1. Root cause — confirmed by reading the code, not inferred from the symptom

`WebSocketHub` (`src/OpenWSFZ.Web/WebSocketHub.cs`) is a `static class` holding one **process-wide**
`ConcurrentDictionary<WebSocket, Guid> ActiveSockets` (`:40`) — every `WebApp` instance in the same
process shares this single dictionary. The only thing separating one instance's sockets from
another's is a `Guid scope` tag, checked at broadcast time. Three of the four broadcast methods carry
that guard, and each one's own doc comment names N6 explicitly as the reason:

- `BroadcastDecodes` (`:433-450`) — `:445` `if (socketScope != scope) continue;`
- `BroadcastCatStatus` (`:464-480`) — `:477`, doc comment cites `AbortAll`'s pattern
- `BroadcastTxState` (`:512` region, doc comment `:488-492`) — same guard, comment narrates a prior
  contamination bug this was fixed for

`BroadcastSpectrum` (`:399-410`) never received the parameter:

```csharp
internal static void BroadcastSpectrum(int[] bins)
{
    if (ActiveSockets.IsEmpty) return;
    var msg     = new WsSpectrumMessage(Type: "spectrum", Payload: bins);
    var json    = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsSpectrumMessage);
    var bytes   = Encoding.UTF8.GetBytes(json);
    var segment = new ArraySegment<byte>(bytes);

    foreach (var (ws, _) in ActiveSockets)      // <-- scope discarded, sent to every socket
        _ = SendWithTimeoutAsync(ws, segment);
}
```

The scope value in the tuple is thrown away (`_`). Every connected socket across every `WebApp`
instance in the process receives every spectrum frame, unconditionally. This is a straightforward
omission — the same fix was applied to three sibling methods and missed on this fourth one — not a
timing or synchronization defect.

## 2. Ruled out

- **Not a race in scope registration.** `RegisterSocket`/`UnregisterSocket` (`:217`, `:223`) are not
  implicated — the leak reproduces because `BroadcastSpectrum` never consults the scope at all, not
  because a registration hasn't landed yet.
- **Not a timeout/async-primitive issue.** `SendWithTimeoutAsync` (`:619`) is the same send path every
  other (correctly-scoped) broadcast method uses; it is not the source of the leak.
- **Scope is exactly this one method.** `BroadcastDecodes`, `BroadcastCatStatus`, `BroadcastTxState`,
  and `AbortAll` (`:206`) were all checked against `ActiveSockets` and all correctly filter by scope.

## 3. Reproduction

Run under WSL Debian (same kernel family as CI's `ubuntu-latest`), full solution suite, twice
independently, on two different bases:

- `fix/fr064-heartbeat-race`@`2c1a71e` — fails.
- `main`@`75ea2c1` (unmodified, no relation to the FR-064 diff) — fails identically.

Both runs: `N6` fails with a leaked `spectrum` frame. Not observed to fail in a native-Windows
`dotnet test` run of the same commit — plausibly because the WSL run's longer wall-clock time and
higher parallel contention gives `SpectrumAnalyser.SpectrumReady` more opportunities to fire mid-test;
the underlying bug is present on every platform since it is unconditional, not host-dependent.

## 4. The fix — one line, test-unrelated file

Give `BroadcastSpectrum` a `Guid scope` parameter and the same guard its three siblings already carry:

```csharp
internal static void BroadcastSpectrum(Guid scope, int[] bins)
{
    if (ActiveSockets.IsEmpty) return;
    var msg     = new WsSpectrumMessage(Type: "spectrum", Payload: bins);
    var json    = JsonSerializer.Serialize(msg, AppJsonContext.Default.WsSpectrumMessage);
    var bytes   = Encoding.UTF8.GetBytes(json);
    var segment = new ArraySegment<byte>(bytes);

    foreach (var (ws, socketScope) in ActiveSockets)
    {
        if (socketScope != scope) continue;   // scope guard — same pattern as BroadcastDecodes
        _ = SendWithTimeoutAsync(ws, segment);
    }
}
```

This is a **`src/` change**, unlike FR-064's test-only fix — `BroadcastSpectrum`'s one call site
(`Program.cs`, wired via `spectrumAnalyser.SpectrumReady += magnitudes => { ... }`, see
`Program.cs:237-259`) will need the app-instance's scope threaded through to the call. Confirm the
call site has the scope value available (it should — `WebApp.Create` already threads a scope `Guid`
through to `WebSocketHub.HandleAsync`/`RegisterSocket` for this exact instance) before editing the
signature; if it does not, stop and escalate rather than inventing a scope value.

## 5. Definition of done

- [ ] `BroadcastSpectrum` takes a `scope` parameter and filters `ActiveSockets` by it, matching the
      `BroadcastDecodes`/`BroadcastCatStatus`/`BroadcastTxState` pattern exactly
- [ ] Call site(s) updated to pass the correct instance scope — confirm the value is already
      available at the call site; do not invent one
- [ ] `N6` (`Broadcast_FromDifferentAppInstance_DoesNotReachThisFixturesSocket`) passes under WSL
      Debian full-suite load, run at least twice consecutively (this flake only reproduced under
      full-suite parallel load, per §3 — an isolated single-test run is not sufficient evidence
      either way, same caveat as FR-064's dev-task)
- [ ] `dotnet test OpenWSFZ.slnx -c Release` — full suite, green, both under native Windows and WSL
      Debian
- [ ] `git diff main --stat` — confirm the diff is limited to `WebSocketHub.cs` and its call site(s);
      no incidental changes elsewhere
- [ ] NFR-021 scan run after commit — clean
- [ ] Commit message states the structural argument (the fourth broadcast method never received the
      scope guard its three siblings did), not "N green runs ⇒ fixed"

🛑 **Then stop.** No push, no merge, no request for either (HK-010/HK-014). No `pre_merge_check.py`
(HK-006 — Captain's initiative only).
