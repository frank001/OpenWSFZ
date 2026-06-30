## Context

`QsoAnswererService` is the only `IQsoController` implementation. It handles the
answerer role: it listens passively, detects incoming CQs, and responds. No mechanism
exists for the operator to originate a CQ call.

The `IQsoController` abstraction was designed with a second implementation in mind;
the `gui-tx-panel` change archived the `QsoRole` and `QsoCallerService` deferrals
explicitly. The TX panel UI surface now exists. This change delivers the second role.

The FT8 caller-role exchange (K1JT calls CQ; W1AW answers):

| Phase | Role    | Message                           |
|-------|---------|-----------------------------------|
| A     | Caller  | `CQ PD2FZ JO33`                   |
| B     | Answerer| `PD2FZ Q1ABC JO22` ← partner responds |
| A     | Caller  | `Q1ABC PD2FZ +00` ← signal report |
| B     | Answerer| `PD2FZ Q1ABC R-07` ← roger report |
| A     | Caller  | `Q1ABC PD2FZ RR73` ← QSO complete |

The caller sends `RR73` (not `73`). The answerer sends `73` (existing behaviour).

---

## Goals / Non-Goals

**Goals:**
- `QsoCallerService` implements the complete caller-role state machine.
- `CallerPartnerSelect = First`: auto-engage the first station that responds.
- `CallerPartnerSelect = None`: operator selects a responder by double-clicking a
  highlighted row in the decode table.
- The existing retry, watchdog, ADIF logging, H6 AP decode, and HoldTxFreq mechanics
  reuse identical logic — no duplication of those subsystems.
- The TX panel renders role-appropriate message rows without a page reload.
- Settings page exposes TX Mode and Partner Selection.

**Non-Goals:**
- `MaxDistance` partner selection (requires grid-to-distance logic).
- SNR-derived reports (TX-D04 deferred; `+00` used as placeholder).
- Runtime role switching without restart.
- Rename of `QsoState` → `AnswererState` (deferred to limit blast radius).
- CQ DX / directional CQ.

---

## Decisions

### D1 — Separate `CallerState` enum; `QsoState` unchanged

**Decision:** Introduce a new `CallerState` enum in `OpenWSFZ.Abstractions`. The
existing `QsoState` enum is NOT renamed in this change.

```csharp
public enum CallerState
{
    Idle,
    TxCq,        // Transmitting "CQ {callsign} {grid}"
    WaitAnswer,  // Waiting for a station to respond
    TxReport,    // Transmitting signal report "{partner} {callsign} +00"
    WaitRr73,    // Waiting for partner's R+report (to send RR73)
    TxRr73,      // Transmitting "{partner} {callsign} RR73"
    QsoComplete, // Logging ADIF; returning to Idle
}
```

**Rationale:** The Captain explicitly requested separate enums per role. Renaming
`QsoState` would touch 24 files (tests, web, daemon, frontend JS) in a single commit;
deferring the rename separates concerns and limits blast radius. The wire format uses
string serialisation; the `role` field on `txState` events tells the frontend which
enum to interpret.

**Alternatives considered:**
- *Extend `QsoState` with caller states* — merges two distinct concepts; makes the
  enum unwieldy and state-machine branching harder to read.
- *Rename `QsoState` → `AnswererState` in this change* — correct long-term, but the
  mechanical rename across 24 files obscures the substantive changes in code review.

---

### D2 — `IQsoController` gains `QsoRole Role { get; }` and `SelectResponderAsync`

**Decision:** `IQsoController` is updated with:

```csharp
QsoRole Role { get; }

Task SelectResponderAsync(
    string callsign, double frequencyHz,
    DateTimeOffset responseCycleStart, CancellationToken ct);
```

`QsoAnswererService.SelectResponderAsync` is a no-op (returns immediately; the HTTP
handler returns HTTP 405 if the active role is Answerer). `QsoCallerService` implements
it fully.

**Rationale:** Adding to the shared interface keeps the web layer simple — one
`IQsoController` resolution handles both roles. The 405 guard in the route handler
surfaces a clear error if the endpoint is called against the wrong role.

**Alternatives considered:**
- *`IQsoCallerController` sub-interface* — the route handler would `as`-cast and
  return 405 on null; functionally equivalent but adds a type to the abstraction layer
  without meaningful benefit at this scale.
- *Route handler casts directly to `QsoCallerService`* — couples the web layer to the
  concrete type; defeats the interface abstraction.

---

### D3 — Role-conditional DI; restart required for role switch

**Decision:** `Program.cs` reads `config.Tx?.Role` before DI container build and
registers one implementation:

```csharp
if (config.Tx?.Role == TxRole.Caller)
{
    services.AddSingleton<QsoCallerService>();
    services.AddSingleton<IQsoController>(sp =>
        sp.GetRequiredService<QsoCallerService>());
    services.AddHostedService(sp =>
        sp.GetRequiredService<QsoCallerService>());
}
else // default: Answerer
{
    services.AddSingleton<QsoAnswererService>();
    services.AddSingleton<IQsoController>(sp =>
        sp.GetRequiredService<QsoAnswererService>());
    services.AddHostedService(sp =>
        sp.GetRequiredService<QsoAnswererService>());
}
```

Switching roles via the Settings page saves `tx.role` to disk. The daemon must be
restarted for the change to take effect. The Settings page SHALL display a visible
"Restart required for mode change to take effect" notice after saving a role change.

**Rationale:** Conditional DI at startup is safe, simple, and directly mirrors how
the existing decode-pipeline and LAN-mode validator work. Runtime switching of a
BackgroundService would require a custom lifecycle wrapper or the
`IHostedServiceFactory` pattern — significant complexity for a feature that operators
change infrequently (once per session at most).

**Alternatives considered:**
- *Both services registered; a `QsoControllerRouter` delegates to the active one* —
  eliminates the restart but adds a non-trivial concurrency surface (two state machines
  reading the same decode channel).
- *`IHostedServiceFactory` / `ObjectDisposedException`-guarded restart* — possible but
  fragile; the operator restart model is well understood.

---

### D4 — `CallerPartnerSelect = None` uses decode-table click, not a separate panel

**Decision:** In `None` mode, when `QsoCallerService` is in `WaitAnswer` and a decode
batch contains one or more `{our_callsign} {any_callsign} {grid}` responses, the
service broadcasts a `txState` event with `state = "WaitAnswer"`. The frontend applies
the CSS class `decode-responder` to all matching rows. The operator double-clicks one;
`main.js` calls `POST /api/v1/tx/select-responder { callsign, frequencyHz,
responseCycleStartUtc }`. The backend's `SelectResponderAsync` then sets a
`_pendingResponder` (analogous to `_pendingTargetCallsign` in `AnswerCqAsync`) and
fires TX on the correct answer phase.

**Phase semantics:** The responder answered on phase B (if our CQ was on phase A) →
we reply on phase A. Same `IsAPhase` / `RoundDownTo15s` logic as `AnswerCqAsync`.

**Rationale:** Reuses the established CQ-click pattern symmetrically. No new UI
surface needed beyond a CSS class and a click handler.

**Alternatives considered:**
- *Separate "responders" panel listing incoming answers* — more prominent but adds
  DOM structure. The decode table already shows these rows; highlighting + click is
  sufficient.

---

### D5 — `CallerPartnerSelect = First`: auto-engage from `WaitAnswer`

**Decision:** When `First` is selected and `QsoCallerService` is in `WaitAnswer`, the
first `HandleWaitAnswerAsync` call whose batch contains a valid response immediately
calls `ExecuteTxReportAsync` (the caller's equivalent of `ExecuteTxAnswerAsync`),
skipping the operator interaction entirely. No pending-target mechanism needed — the
batch is processed in-line.

**Rationale:** `First` mode is conceptually simple. The caller answered their own CQ
automatically. No concurrency surface beyond what already exists.

---

### D6 — `txState` wire event gains `role` field

**Decision:** `TxEventBus.Publish(...)` is updated to include a `role` string
(`"answerer"` / `"caller"`). `TxStatusResponse` gains a `string Role` property.

Wire format (caller, active):
```json
{"type":"txState","role":"caller","state":"TxCq","partner":null,"autoAnswerEnabled":true}
```

Wire format (answerer, unchanged except for new field):
```json
{"type":"txState","role":"answerer","state":"TxAnswer","partner":"Q2XYZ","autoAnswerEnabled":true}
```

The frontend defaults to `"answerer"` when `role` is absent (forward-compat with any
old event from a pre-deploy page load).

**Impact on `renderMessageRows`:** The function branches on `role` to select the
correct message templates:

| Row  | Answerer template             | Caller template              |
|------|-------------------------------|------------------------------|
| Tx 1 | `{partner} {ours} {grid}`     | `CQ {ours} {grid}`           |
| Tx 2 | `{partner} {ours} R+00`       | `{partner} {ours} +00`       |
| Tx 3 | `{partner} {ours} 73`         | `{partner} {ours} RR73`      |

Active-row state mapping:

| State (Answerer) | Row | State (Caller) | Row |
|------------------|-----|----------------|-----|
| `TxAnswer`       | 1   | `TxCq`         | 1   |
| `TxReport`       | 2   | `TxReport`     | 2   |
| `Tx73`           | 3   | `TxRr73`       | 3   |

**Rationale:** A single `role` field is the minimum-schema change. The frontend
template switch is one `if` branch in `renderMessageRows`.

---

### D7 — `QsoCallerService` reuses `_stateLock`, watchdog, `SafeAbortToIdleAsync` pattern

**Decision:** `QsoCallerService` mirrors the internal structure of `QsoAnswererService`:
same `_stateLock` for thread-safe state reads, same CTS-based watchdog pattern, same
`SafeAbortToIdleAsync` idiom. The `_wakeupChannel` mechanism (for `SelectResponderAsync`
in `None` mode) is likewise identical to `AnswerCqAsync`'s wakeup.

Key state fields:
```
private volatile CallerState _callerState = CallerState.Idle;
private volatile string?     _partner     = null;
private string               _lastTxFreqHz;
private int                  _retryCount;
private bool                 _skipNextRetry; // A-01 guard
private DateTime             _qsoStartUtc;
// Pending responder (None mode — mirrors _pendingTargetCallsign in answerer)
private readonly object      _stateLock = new();
private string?              _pendingResponderCallsign;
private double               _pendingResponderFrequencyHz;
private bool                 _pendingResponderIsAPhase;
private DateTimeOffset       _pendingResponderSetAt;
```

`IQsoController.State` returns `QsoState.Idle` when `_callerState == CallerState.Idle`
and `QsoState.TxAnswer` (or the closest answerer-state proxy) otherwise. **Wait** —
this doesn't work cleanly with a shared `QsoState` on the interface. See D8.

---

### D8 — `IQsoController.State` returns `object`; wire serialisation uses strings

**Decision:** `IQsoController.State` currently returns `QsoState`. With two role-
specific enums, this must change. Options:

1. Return `QsoState` for answerer, box `CallerState` via `object` — ugly.
2. Introduce a shared `ITxState` marker interface on both enums — enums can't implement
   interfaces.
3. Keep `IQsoController.State` as `QsoState` for now, with `QsoCallerService` mapping
   `CallerState` to the closest `QsoState` value.
4. Change `IQsoController.State` to `string` — loses type safety.
5. Add a separate `CallerState CallerState { get; }` property to a sub-interface,
   keep the `QsoState State` on the base for the answerer, and have the web layer
   discriminate.

**Decision:** Option 3 for this change, with a clear comment. `QsoCallerService`
exposes:
- `QsoState.Idle` when `CallerState == Idle`
- `QsoState.TxAnswer` when `CallerState == TxCq` (closest semantic match — TX active)
- `QsoState.WaitReport` when `CallerState == WaitAnswer`
- `QsoState.TxReport` when `CallerState == TxReport`
- `QsoState.WaitRr73` when `CallerState == WaitRr73`
- `QsoState.Tx73` when `CallerState == TxRr73`
- `QsoState.QsoComplete` when `CallerState == QsoComplete`

The `txState` wire event uses the raw `CallerState` string name (not the mapped
`QsoState`), delivered via the `role`-aware branch in `TxEventBus.Publish`. The frontend
renders based on the string name, not a C# enum value, so there is no breaking change.

The `role` field (D6) is the authoritative discriminant on the wire. The `State`
property on `IQsoController` is used only for HTTP status responses (`/tx/status`,
`/tx/enable` etc.), where the `role` field accompanies it and the client can
interpret correctly.

**Rationale:** This is a known short-term compromise. The `QsoState` → `AnswererState`
rename (deferred from D1) is the clean long-term fix; it removes the need for this
mapping entirely. The mapping is documented in `QsoCallerService` with a reference to
the rename task.

---

### D9 — Repeat-CQ logic on retry: retransmit CQ, not last message

**Decision:** In `WaitAnswer`, when no response arrives and retries are enabled, the
service re-enters `TxCq` and retransmits the CQ message (not `_lastTxMessage`). This
is the only departure from the answerer's retry pattern (the answerer retransmits
`_lastTxMessage` which is always valid for retries). The caller's retry state is
`WaitAnswer` (return to it after each CQ retransmit), not `WaitReport` / `WaitRr73`.

Retry count and watchdog semantics are identical to the answerer.

---

## Risks / Trade-offs

**[Risk] `IQsoController.State` mapping (D8) may confuse HTTP clients if both roles
are tested via `/api/v1/tx/status`** →  
The `role` field in both `TxStatusResponse` and `txState` events is the correct
discriminant. Existing clients that only read `state` without `role` will see plausible
(if imprecise) state names. Document the mapping in `QsoCallerService`.

**[Risk] Restart required for role switch is a UX friction point** →  
The Settings page SHALL display a restart notice after saving a role change. For most
operators this is acceptable — the role changes at most once per session.

**[Risk] `None` mode responder-click and `AnswerCqAsync` pending-target have similar
structure — divergence over time** →  
Both are documented as "pending target" patterns. Consider extracting a shared
`PendingTarget` struct in a future tidy-up pass.

**[Risk] Caller sends `+00` as fixed report (TX-D04 deferred)** →  
This is a known placeholder. The partner will log `+00` in their ADIF regardless of
actual signal quality. Acceptable for v1; TX-D04 closes this gap.

**[Risk] `CallerPartnerSelect = None` UX in a busy band** →  
Multiple stations may respond to a single CQ simultaneously; the operator must pick
one within one cycle (15 s). Partial mitigation: `decode-responder` highlighting makes
them visually prominent. No hard timeout on partner selection — the operator can abort
and retry.

## Migration Plan

1. All new fields in `TxConfig` have defaults (`Role = Answerer`, `CallerPartnerSelect
   = First`). Existing config files load without change.
2. Existing deployments running `Role = Answerer` (default) behave identically to
   pre-change; zero functional regression.
3. To switch to Caller mode: Settings → General → TX Mode → Caller → Save → restart.
4. No database or file format migrations needed beyond the `TxConfig` fields, which
   are round-tripped safely by STJ.
5. The `[JsonConstructor]` on `TxConfig` MUST carry default values for `Role` and
   `CallerPartnerSelect`; absent JSON fields must not deserialise to `0` (lesson 6
   from MEMORY.md).
