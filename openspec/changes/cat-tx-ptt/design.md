## Context

Three pieces already exist independently:

- **CAT control** (`cat-control` spec): `IRadioConnection` (query/set VFO-A frequency only), `SerialCatConnection` (Kenwood/Yaesu-family serial dialect, `FA;`/`FA<Hz>;`), `RigctldConnection` (TCP to `rigctld`, `\get_freq\n`/`\set_freq <Hz>\n`), and `CatPollingService` — a single `IHostedService` that owns one `IRadioConnection` instance and polls it on a timer, publishing `ICatState`.
- **FT8 TX** (`ft8-tx` spec): `Ft8AudioSynthesiser` produces the GFSK waveform; `IPttController` is the seam between "have audio" and "make noise happen on a device"; `AudioOnlyPttController` is the only implementation, and it conflates two ideas that are actually separate — *asserting PTT* and *playing audio* — because for VOX they happen to be the same action (start audio → rig's VOX detects it → rig keys itself).
- **QSO automation** (`qso-answerer`, `qso-caller`): both resolve `IPttController` from DI and call `LoadAudio`/`KeyDownAsync`/`KeyUpAsync` at the right points in their state machines. Neither needs to change for this proposal — the whole point of the `IPttController` seam (per its own doc comment) is that new keying mechanisms plug in underneath it without touching the state machines.

This change makes OpenWSFZ able to key a real transmitter under its own control for the first time. That is a materially different risk profile from anything shipped so far — CAT frequency control is read-mostly and reversible; PTT keying, done wrong, means a transmitter stuck on the air. Every decision below is made with that asymmetry in mind: prefer the design that fails toward "rig stays silent" over the one that fails toward "rig stays keyed."

## Goals / Non-Goals

**Goals:**
- Let an operator select, per-config, how PTT is asserted: existing VOX (`AudioOnlyPttController`, unchanged), a new CAT-command controller, or a new serial RTS/DTR controller.
- Guarantee CAT frequency polling and CAT PTT commands never interleave on the wire.
- Guarantee PTT is always released — on normal completion, on any exception, on cancellation, on `DisposeAsync`, on daemon shutdown, and on a hard watchdog ceiling if nothing else fires.
- Keep today's behaviour as the zero-config default; nothing breaks for an operator who never touches the new config fields.
- Produce a real hardware-acceptance gate, because none of the above can be proven by CI against a real radio.

**Non-Goals:**
- No rig-specific dialect beyond the Kenwood/Yaesu-family command set `SerialCatConnection` already speaks. Rigs needing a different PTT dialect over serial CAT are out of scope for this change (they can use RTS/DTR instead, or a future change can add another `IRadioConnection` implementation).
- No mode-set, split, or any other rig-altering command. This change adds exactly one new rig-altering capability: PTT.
- No new UI. The existing CAT status badge is unchanged; no "TX keyed" indicator is added (see Decision 6).
  **Amended 2026-07-12 — see Decision 6's own amendment note below**: a Settings-page UI for
  `ptt` configuration (not a "TX keyed" indicator, which remains out of scope) is now in scope,
  raised by the Captain during hardware acceptance after discovering there is no way to change
  or verify `ptt.method` without hand-editing `config.json`.
- No change to `QsoAnswererService`/`QsoCallerService` state machines — they already consume `IPttController` correctly; this change only adds implementations underneath.

## Decisions

### 1. Wire serialization: `CatPollingService` becomes the single writer of the shared `IRadioConnection`

**Decision:** `CatPollingService` already owns the one `IRadioConnection` instance used for polling. It gains a private `SemaphoreSlim(1,1)` gate and a new internal method (exposed to the CAT-command PTT controller via a narrow interface, e.g. `ICatPttGate` with `Task SetPttAsync(bool, CancellationToken)`) that acquires the same gate the poll loop uses before touching the connection. Nothing outside `CatPollingService` ever calls `IRadioConnection.SetPttAsync` (or `GetDialFrequencyMhzAsync`/`SetDialFrequencyMhzAsync`) directly — the CAT-command `IPttController` implementation depends only on `ICatPttGate`, mirroring how `ICatTuner`/`ICatController` are already the narrow public seams `CatPollingService` exposes for its other capabilities.

**Why:** `SerialCatConnection` and `RigctldConnection` are not thread-safe with respect to each other's calls — they share one `SerialPort`/`TcpClient` and assume request/response calls do not overlap. The poll loop runs on a timer independent of QSO state; a PTT key-down can happen at any point in that cycle. Without serialization, a poll's `FA;` write could be immediately followed by a PTT `TX;` write before the poll's response is read, and the two responses could arrive interleaved — at best a spurious CAT error, at worst a misread response that causes a wrong action.

**Alternatives considered:**
- *Separate `IRadioConnection` instances for polling vs. PTT* — rejected: most CAT interfaces are a single serial port or a single `rigctld` TCP session; opening two connections to the same port either fails outright (serial, exclusive access) or requires `rigctld` to arbitrate (which it does, but then we've just moved the interleaving risk into `rigctld`'s own request queue, and we've lost the ability to guarantee ordering between "stop polling frequency" and "assert PTT" that a bad rig might care about).
- *Lock-free, "last writer wins" with retries* — rejected: retrying a `TX;` that the rig may have half-processed is exactly the kind of ambiguity this change must not introduce.
- *Pause polling entirely for the duration of a QSO's TX phases* — considered but not needed: the semaphore already forces polling to simply wait its turn (a poll blocked for ~100 ms behind a PTT command is invisible to the operator; the reverse — PTT waiting behind a slow poll — is bounded by the existing 500 ms serial/TCP read timeout).

### 2. `IRadioConnection.SetPttAsync` — same dialect family as the existing frequency commands

**Decision:** Add `Task SetPttAsync(bool transmitting, CancellationToken cancellationToken = default)` to `IRadioConnection`. `SerialCatConnection` sends `TX;\r` to key and `RX;\r` to unkey — the same Kenwood/Yaesu-family dialect its `FA;`/`FA<Hz>;` frequency commands already use, so no new rig-family assumption is introduced. `RigctldConnection` sends `\set_ptt 1\n` / `\set_ptt 0\n` and consumes the `RPRT` acknowledgement exactly as `SetDialFrequencyMhzAsync` already does for `\set_freq`. Like the frequency-set method, `SetPttAsync` is fire-and-forget on the wire (write, read+validate the ack where the protocol provides one, return) — it does not poll back to confirm the rig actually keyed, because `IRadioConnection` has no read-PTT-state query and adding one is out of scope.

**Why:** Consistency with the existing, already-shipped dialect keeps `SerialCatConnection` a single coherent implementation rather than a grab-bag of per-command rig assumptions. Reusing the ack-consumption pattern from `SetDialFrequencyMhzAsync` (rather than inventing a new one) keeps `RigctldConnection` internally consistent and avoids the exact receive-buffer-misalignment class of bug that `SetDialFrequencyMhzAsync`'s own history (see its doc comments referencing "F-006 Root A") already had to fix once.

**Alternatives considered:**
- *Read back and confirm PTT state after every set* — rejected for v1: `rigctld` does expose `\get_ptt`, but serial Kenwood/Yaesu dialect PTT read-back is inconsistent across rig families, and confirming here would still race with the watchdog described in Decision 4. Left as a documented Open Question / future hardening.

### 3. Two new `IPttController` implementations, sharing an extracted WASAPI helper; `AudioOnlyPttController` untouched in behaviour

**Decision:** Extract the WASAPI device-open/play/stop/release logic currently inline in `AudioOnlyPttController` into an internal, `WASAPI_SUPPORTED`-gated helper (e.g. `internal sealed class WasapiTxPlayer`) exposing `PlayAsync(float[] samples, string? deviceId, CancellationToken)` and `Stop()`. `AudioOnlyPttController` is refactored to call this helper but its public behaviour, timing, and requirements are unchanged — every existing scenario in the `ft8-tx` spec for `AudioOnlyPttController` continues to hold verbatim.

Two new sealed classes are added:
- `CatPttController : IPttController` — `KeyDownAsync` calls `ICatPttGate.SetPttAsync(true)`, waits `PttLeadTimeMs`, then plays the loaded audio via `WasapiTxPlayer` and awaits completion; `KeyUpAsync` stops any in-progress playback, waits `PttTailTimeMs`, then calls `ICatPttGate.SetPttAsync(false)`.
- `SerialRtsDtrPttController : IPttController` — same sequencing, but asserts/de-asserts a raw serial control line (via the new `ISerialPort.SetRts`/`SetDtr`, see Decision 5) on its own independently-configured `ISerialPort` instead of going through `ICatPttGate`.

Both new controllers wrap the watchdog described in Decision 4.

**Why:** For VOX, "start audio" and "assert PTT" are the same physical action by construction — that is why `AudioOnlyPttController` never needed to separate them. CAT-command and RTS/DTR PTT are physically asserted *before* any audio should appear (real rigs need tens of milliseconds for the PA to come up cleanly) and released *after* audio ends (to avoid clipping the tail of the last symbol) — this is exactly the "lead time / tail time" pattern used throughout amateur radio interfacing, and it cannot be expressed by the existing single-action `AudioOnlyPttController`. Extracting the WASAPI helper avoids a second ~150-line copy of device-open/play/stop/dispose logic (and a second copy of its finally/dispose bug surface) in each new controller.

**Alternatives considered:**
- *One `IPttController` implementation with a strategy enum inside it* — rejected: `IPttController`'s contract (`LoadAudio`/`KeyDownAsync`/`KeyUpAsync`/`DisposeAsync`) is already the strategy seam; a single class branching internally on a config enum just reinvents DI-time selection with an `if` statement, and makes each mechanism harder to unit-test in isolation (the existing `SerialCatConnection`/`RigctldConnection`/`AudioOnlyPttController` test suites all test one mechanism per class — this stays consistent with that).

### 4. Failsafe watchdog: a single, mechanism-agnostic guard

**Decision:** Both `CatPttController` and `SerialRtsDtrPttController` start a `CancellationTokenSource` timer (default `PttWatchdogTimeoutMs = 20000`, comfortably above one FT8 transmission's 12 640 ms) the instant PTT is asserted. If `KeyUpAsync` has not completed by the time the timer fires, the watchdog forces PTT release (bypassing tail-time) and logs at Error. The watchdog is cancelled the instant `KeyUpAsync` begins. PTT release is additionally guaranteed via `try/finally` around the entire key-down→play→key-up sequence (mirroring `AudioOnlyPttController`'s existing `_playerLock` finally pattern) and via `DisposeAsync`, so an exception anywhere in the sequence — including inside `WasapiTxPlayer` — still de-asserts PTT.

**Why:** This is the one part of the change where "silently do nothing" is worse than "do something loud." A hung WASAPI call, a cancelled task that doesn't unwind cleanly, or an unhandled exception must not leave a real transmitter keyed indefinitely. Twenty seconds is short enough to bound real-world harm (no single FT8 exchange step runs anywhere near that long) and long enough to never fire during correct operation, so it should never surprise an operator in normal use — only during a genuine bug, where it is exactly the last line of defence this change exists to provide.

### 5. `ISerialPort` gains RTS/DTR control; RTS/DTR PTT is wired independently of CAT

**Decision:** `ISerialPort` gains `bool RtsEnable { get; set; }` and `bool DtrEnable { get; set; }` (mirroring `System.IO.Ports.SerialPort`'s own properties 1:1, so `SerialPortWrapper` is a one-line pass-through each — same pattern as its existing `IsOpen`/`ReadTimeout`). `SerialRtsDtrPttController` opens its **own** `ISerialPort` instance, constructed from its own config (`Ptt.SerialPort`, independent of `cat.serialPort`), and does not share a connection with `CatPollingService` at all.

**Why:** In real operator setups, CAT (if used) and RTS/DTR PTT are frequently on different physical interfaces entirely — e.g. CAT over a USB-CI-V cable direct to the rig, PTT via a separate USB-serial adapter wired to a soundcard interface's RTS pin, or PTT-only with no CAT link at all (an operator who wants software PTT but has no CAT-capable rig, or prefers not to enable frequency polling). Forcing RTS/DTR PTT to reuse `cat.serialPort` would make that arrangement impossible to configure and would also drag RTS/DTR PTT into Decision 1's serialization gate for no reason — it is a different transport with no shared state to protect.

### 6. Configuration: additive fields on `CatConfig`, default preserves today's behaviour exactly; no new UI

**Decision:** Add a `PttConfig` record (new file, referenced from `AppConfig`, not nested inside `CatConfig` — PTT method is orthogonal to whether CAT is even enabled: an operator can run `SerialRtsDtr` PTT with `cat.enabled = false`):

```csharp
public sealed record PttConfig
{
    public string Method { get; init; } = "AudioVox"; // AudioVox | CatCommand | SerialRtsDtr
    public string SerialPort { get; init; } = <platform default, same pattern as CatConfig.SerialPort>;
    public string SerialLine { get; init; } = "Rts";   // Rts | Dtr — only used when Method == SerialRtsDtr
    public int LeadTimeMs { get; init; } = 50;
    public int TailTimeMs { get; init; } = 50;
    public int WatchdogTimeoutMs { get; init; } = 20000;
}
```

Unknown/missing `ptt` key deserialises to all defaults (`Method = "AudioVox"`), which is byte-for-byte today's behaviour — `Program.cs`'s DI registration switches on `configStore.Current.Ptt.Method` at startup the same way it already switches on `#if WASAPI_SUPPORTED` today, registering exactly one `IPttController`. An invalid/unrecognised `Method` value logs a Warning and falls back to `AudioVox`, matching the existing `CatConfig.RigModel` unknown-value handling (FR-034).

No new UI ships with this change. The existing CAT status badge (`ICatState.Status`) already tells the operator whether the CAT link itself is up; per FR-016, a "PTT currently asserted" indicator would need its own fully-working backend-to-UI round trip designed, reviewed, and tested, which is out of scope here — it can be proposed as a small follow-up once the underlying keying mechanisms exist and have been hardware-verified.

**Alternatives considered:**
- *Nest `Ptt` inside `CatConfig`* — rejected per above: couples PTT method selection to CAT being the owning capability, which is false for `SerialRtsDtr` and even for `AudioVox` (today's default has never depended on `CatConfig` at all).
- *Reuse `cat.serialPort`/`cat.baudRate` for `SerialRtsDtr`* — rejected per Decision 5.

**Amendment (2026-07-12) — "no new UI" reversed for `ptt` *configuration* only:** During hardware
acceptance (gates 14–15), the Captain discovered there is no way to change or verify `ptt.method`
without hand-editing `config.json` and restarting — which is itself how a null-`ptt`-guard defect
(`dev-tasks/2026-07-12-cat-tx-ptt-null-ptt-config-guard.md`) went undiagnosed for a full session: an
operator has no visibility into what `ptt` section is actually persisted. A Settings-page UI is now
in scope, added as tasks.md section 17. This does **not** reverse the rest of Decision 6 — no
"TX keyed" / watchdog-trip indicator is added; the scope is strictly the same fields already
described in this Decision's `PttConfig` record, exposed as editable form controls in a new
"PTT Config" fieldset alongside "CAT rig connection" (split side-by-side per the Captain's layout
sketch), plus one new capability with its own safety analysis below: a **Test** button.

**Test-button decision:** Per `IRadioConnection.SetPttAsync`'s own doc comment (Decision 2), no
implementation ever reads back PTT state — there is no way to confirm a rig physically keyed.
Given that hard limitation, Test performs a brief (~200–300 ms), **silent** software pulse — assert
PTT → tiny silence buffer → release — against the currently-**running** `IPttController` singleton
(i.e. whatever `Ptt.Method` the daemon was last started with; unsaved, un-restarted form edits are
not reflected, consistent with `Ptt.Method` already being read once at DI-registration time). Pass
means the assert/release commands completed without throwing (a real CAT ACK or a real RTS/DTR line
toggle happened); it explicitly does **not** mean the rig visibly keyed — the operator must still
watch the rig. No confirmation dialog gates the click (matches every other action already on this
page — Save, Retry, Refresh — none of which prompt "are you sure?").

**Safety-critical finding, must be fixed as part of this scope, not deferred:** `CatPttController`/
`SerialRtsDtrPttController` have **no internal call-serialisation** — `KeyDownAsync`/`KeyUpAsync`
assume exactly one caller (the active `QsoAnswererService`/`QsoCallerService`) ever calls them.
A Test click is a second, independent caller of the same DI singleton. Without a guard, a Test
firing while a real QSO is mid-transmission would call the *same* `KeyDownAsync`/`KeyUpAsync`
sequence concurrently: the shared `_watchdog` would be re-armed (silently resetting a real
transmission's failsafe countdown) and, worse, the Test's own short `KeyUpAsync` would set
`_pttAsserted = false` and de-assert PTT — **physically unkeying a real, in-progress over-the-air
transmission**, which is exactly the failure mode this entire change's stated design principle
("prefer the design that fails toward 'rig stays silent' over the one that fails toward 'rig stays
keyed'") exists to prevent, just inverted (fails toward "rig stops mid-transmission" instead). Two
layers of defence, both required:
1. `WebApp.cs`'s test endpoint checks `IQsoController.Keying` and rejects with 409 if a real QSO is
   currently keying — fast, clear feedback for the common case.
2. `CatPttController` and `SerialRtsDtrPttController` each gain a private `SemaphoreSlim(1,1)`
   acquired for the full `KeyDownAsync`→`KeyUpAsync` critical section, so even a request that races
   past check (1) queues behind the in-flight real transmission instead of interleaving with it.
   This mirrors Decision 1's own wire-serialisation gate, applied one layer up, and permanently
   closes this hazard for this caller and any future one — not just the Settings-page Test button.

## Risks / Trade-offs

- **[Risk] A rig's serial CAT dialect accepts `TX;`/`RX;` but interprets them differently than expected (e.g. `TX;` toggles rather than sets)** → Mitigation: this is precisely why the hardware-acceptance gate (see tasks.md) requires an operator to visually confirm actual rig behaviour on real hardware before this change is considered done; it cannot be fully de-risked by unit tests against a fake `ISerialPort`.
- **[Risk] Watchdog fires during a legitimately slow transmission (e.g. a saturated USB-audio path delays WASAPI playback)** → Mitigation: `WatchdogTimeoutMs` is configurable; the default 20 s carries ~7 s of margin over the fixed 12.64 s FT8 transmission length, and the hardware-acceptance plan includes a step that deliberately validates the watchdog fires only when expected.
- **[Risk] Extracting `WasapiTxPlayer` out of `AudioOnlyPttController` regresses its existing, already-shipped behaviour** → Mitigation: the existing `AudioOnlyPttController` unit test suite is the regression guard; tasks.md requires it to pass unmodified (assertions unchanged) against the refactored implementation before any new controller is added.
- **[Risk] `CatPollingService` becoming the gatekeeper for PTT commands makes it a more critical, harder-to-test component** → Trade-off accepted: the alternative (letting `CatPttController` open its own competing `IRadioConnection`) reintroduces the interleaving risk Decision 1 exists to remove. `ICatPttGate` is a narrow, single-method seam that keeps `CatPttController`'s own unit tests trivial (mock `ICatPttGate`, assert it's called in the right order with the right value).

## Migration Plan

- Purely additive: no existing config field changes meaning, no existing `IRadioConnection`/`IPttController` consumer call site changes (both interfaces gain members but no existing method loses parameters or changes behaviour).
- Deploy as a normal minor-version bump per `release-versioning`; no data migration, no config migration script needed (missing `ptt` key = default = today's behaviour).
- Rollback: reverting the change is safe at any point before an operator opts into `CatCommand`/`SerialRtsDtr` in their config, since `AudioVox` remains the default and is functionally identical to pre-change behaviour.

## Open Questions

- Should a future change add PTT read-back confirmation (`rigctld`'s `\get_ptt`) as an optional post-key-down sanity check? Deferred — see Decision 2's alternatives.
- Should the watchdog-fired event be surfaced to the operator via a WebSocket event (distinct from a log line) so a stuck-PTT recovery is visible in the UI without reading logs? Deferred with the rest of Decision 6's "no new UI" scope — worth revisiting once hardware acceptance has run at least once and it's known how often (if ever) the watchdog actually fires in practice.
