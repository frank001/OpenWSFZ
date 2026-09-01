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

### 🔴 Correction, 2026-09-01 ~18:40Z — §4's original "one line, test-unrelated file" claim was WRONG

A Developer session (`fix/websockethub-broadcastspectrum-scope-guard`, off `main`@`2c1a71e`) correctly
**stopped instead of improvising**, per this document's own §4 escalation instruction, and reported
back rather than invent a scope value. It found what QA's original read of the call site missed:
`BroadcastSpectrum`'s actual call path is `spectrumBus.Publish(bins)` →
`SpectrumEventBus.Publish(int[] bins) => WebSocketHub.BroadcastSpectrum(bins)`
(`src/OpenWSFZ.Web/SpectrumEventBus.cs:16`) — a façade with **no scope-carrying capability at all**,
unlike `DecodeEventBus`'s `Guid appScope = default` constructor pattern
(`src/OpenWSFZ.Web/DecodeEventBus.cs:19-30`). Worse: `Program.cs:224` constructs `spectrumBus` and
`:237-261` registers the lambda that calls `Publish` — both **before** `appScope` is even declared, at
`Program.cs:300` (`var appScope = Guid.NewGuid();`, itself already hoisted once, per its own comment
at `:295-299`, specifically so `DecodeEventBus` could have it — `spectrumBus` was evidently missed
when that hoist happened). §4 below is corrected accordingly; independently re-verified by QA against
the current tree, not taken on the Developer session's word alone.

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

## 4. The fix — CORRECTED: three files, one safe reordering, not "one line"

### 4a. `Program.cs` — hoist `appScope`'s declaration

Move `var appScope = Guid.NewGuid();` from its current position (`:300`) to **before** the
`// ── Spectrum analyser ──` section (`:222`, i.e. before `spectrumBus`'s construction at `:224` and
the `SpectrumReady` lambda registered at `:237-261`). This is safe to verify mechanically: nothing
between the old and new positions currently references `appScope` (grep the whole file — every use is
at `:300` or later), and `Guid.NewGuid()` has no dependency on anything else in the file. Do not move
anything else; this is a single-statement hoist, not a broader reorder.

### 4b. `SpectrumEventBus.cs` — give it the same scope-carrying pattern `DecodeEventBus` already has

```csharp
public sealed class SpectrumEventBus
{
    private readonly Guid _appScope;

    public SpectrumEventBus(Guid appScope = default) => _appScope = appScope;

    public bool HasClients => WebSocketHub.HasClients;

    public void Publish(int[] bins) => WebSocketHub.BroadcastSpectrum(_appScope, bins);
}
```

Matches `DecodeEventBus`'s exact shape (`src/OpenWSFZ.Web/DecodeEventBus.cs:19-41`) — optional
`default` so any test that constructs `SpectrumEventBus` directly without a real scope in play
continues to work unchanged (same reasoning `DecodeEventBus`'s own doc comment gives).

### 4c. `Program.cs` — pass the now-earlier-available scope at construction

`var spectrumBus = new SpectrumEventBus();` → `var spectrumBus = new SpectrumEventBus(appScope);`
(now legal, since 4a moved `appScope`'s declaration above this line).

### 4d. `WebSocketHub.cs` — the originally-planned guard, unchanged from before this correction

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

**Zero-overlap note:** `FR-020`'s dev-task also touches `Program.cs`, at `:733-735` and two other
`StartPipeline` call sites — textually distant from this fix's `:222-300` region, but both fixes now
touch the same file. Not a reason to serialize the two Developer sessions; just something whoever
merges second needs to rebase/re-diff cleanly against, not assume disjoint.

## 5. Definition of done

- [x] `appScope`'s declaration hoisted per §4a — confirmed clean in the diff, nothing between old and
      new positions referenced it
- [x] `SpectrumEventBus` takes an optional `Guid appScope = default` constructor parameter per §4b,
      matching `DecodeEventBus`'s exact pattern (including a matching doc comment)
- [x] `Program.cs`'s `spectrumBus` construction passes `appScope` per §4c
- [x] `BroadcastSpectrum` takes a `scope` parameter and filters `ActiveSockets` by it per §4d, matching
      the `BroadcastDecodes`/`BroadcastCatStatus`/`BroadcastTxState` pattern exactly
- [x] `N6` passes under WSL Debian full-suite load — run twice under WSL, twice under native Windows
      (4 full-suite runs total); `OpenWSFZ.Web.Tests` (containing N6) 276/276 on **every** run
- [x] `dotnet test OpenWSFZ.slnx -c Release` — full suite, green across all 4 runs for the relevant
      projects; the one incidental failure seen (`CycleArchiveServiceTests`, once, one native run) is
      the already-tracked, already Captain-ruled-on sibling defect, not this fix
- [x] `git diff main --stat` — confirmed limited to exactly the three files in §4, nothing in
      `FR-020` territory
- [x] NFR-021 — manual scan clean (0 callsign-shaped tokens); **also surfaced a real, separate finding
      worth keeping on record:** `qa/rr-study/nfr021_pre_merge_scan.py`'s `TEXT_SUFFIXES` doesn't
      include `.cs` — it silently scans zero of the files this diff touched. That script is scoped to
      R&R-study artefacts (csv/md/html/etc.), not general source review, so this isn't a defect in
      itself, but it's a reminder that script is not a substitute for a real NFR-021 check on `src/`
      changes — manual review remains necessary until a general-purpose scanner exists.
- [x] Commit message states the structural argument (the fourth broadcast method never received the
      scope guard its three siblings did), not "N green runs ⇒ fixed"

✅ **DONE. Commit `621f569` on `fix/websockethub-broadcastspectrum-scope-guard` (off `main`@`2c1a71e`,
not pushed).** QA independently verified: rebuilt clean, re-ran the target test standalone (pass),
read the full diff line by line — matches this checklist exactly, no incidental changes. One
operational note from the Developer session, not a task concern: its worktree was torn down and
recreated mid-task at a session boundary; no work was lost since nothing had been committed at that
point.

🛑 **Developer session stopped correctly** — no push, no merge, no `pre_merge_check.py` run
(HK-010/HK-014/HK-006). **Ready for the Captain's own diff review and merge ruling (HK-010)** — same
footing as `FR-020` and `CycleArchiveServiceTests`.
