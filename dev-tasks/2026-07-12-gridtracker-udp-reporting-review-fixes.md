# Developer Handoff — gridtracker-udp-reporting: required pre-merge fixes

**Date:** 2026-07-12
**Prepared by:** QA Engineer
**Status:** Required changes, blocking merge of `feat/gridtracker-udp-reporting`
**Scope:** Two items — one empirically-proven defect found during code review (D-014), and one
absolute, non-negotiable requirement requested directly by the Captain (no defect ID; treat as
Must Have on the same footing as an FR).

---

## 1. Context

This document is QA's "return with required changes" response to the pre-merge review of
`feat/gridtracker-udp-reporting`. The branch is **not yet merged** — these are amendments to an
in-flight change, not a post-merge defect fix, so **no new branch, no new OpenSpec change
proposal**. Continue on the existing branch and amend the existing change's own artifacts in
place (§5).

Two items, unrelated to each other, both must land before this branch merges:

1. **D-014** — the inbound UDP listener (Halt Tx / Reply / Free Text) silently fails to bind
   whenever the configured target's port is already owned by a real peer — which is the *normal*
   real-world case (GridTracker2 is the thing usually already running). Empirically proven
   against the actual `ExternalReportingService` code during review, not theoretical.
2. **Absolute exclusion of synthetic/unknown-region traffic from external output** — the Captain
   has directed, in the plainest possible terms, that **no** decode, status update, or logged QSO
   whose origin is an R&R-study synthetic signal or an unresolved (Unknown-region) callsign may
   ever reach an external program via this feature. **No exceptions** — not gated by, not
   overridable through, any operator setting. This is a data-integrity/privacy floor, not a
   preference: R&R synthetic signals (Q-prefix test callsigns, per the project's NFR-021
   synthetic-callsign convention) are not real amateur-radio traffic, and letting them leak into
   GridTracker2 — which itself may relay spots onward to a real map, a real logbook, or another
   real-world tool — would contaminate systems this project has no authority over. Unknown-region
   decodes are unverified/likely-noisy and get the same treatment for the same reason: nothing
   this application cannot vouch for should leave the machine on this channel.

---

## 2. Branch

Continue on **`feat/gridtracker-udp-reporting`** (the existing, unmerged feature branch). Do not
create a new branch for this.

---

## 3. D-014 — Inbound listener fails to bind when the target port is already owned by a peer

### 3.1 The defect, proven

`ExternalReportingService.Reconcile` (`src/OpenWSFZ.Daemon/ExternalReportingService.cs:254-275`)
binds the single inbound listener to `desiredEnabled[0].Port` — i.e. **the same port number the
target is configured on** — via a plain `new UdpClient(new IPEndPoint(IPAddress.Any,
desiredInboundPort))`, with no `SO_REUSEADDR`/`ExclusiveAddressUse=false` set:

```csharp
// src/OpenWSFZ.Daemon/ExternalReportingService.cs:261-274 (current)
if (desiredInboundPort > 0)
{
    try
    {
        _inboundClient    = new UdpClient(new IPEndPoint(IPAddress.Any, desiredInboundPort));
        _inboundBoundPort = desiredInboundPort;
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex,
            "external-reporting: failed to bind inbound listener on port {Port}.",
            desiredInboundPort);
    }
}
```

During review I wrote a temporary probe test (not committed) against the real
`ExternalReportingService`: bind a fake "GridTracker2" `UdpClient` to a free port **first** (the
realistic startup order — the operator's mapping tool is usually already running), then start
`ExternalReportingService` configured with a target on that same port, then send a well-formed
Halt Tx datagram to that port. **Result: `IQsoController.AbortAsync` was never called.** The bind
throws (`SocketException`: *"Only one usage of each socket address... is normally permitted"*),
is swallowed by the `catch` above, and logged only at **Warning**. `_inboundClient` stays `null`;
`InboundLoopAsync` spins harmlessly forever. There is no operator-visible indication that the one
message this change treats as safety-critical and ungated (`Requirement: Inbound Halt Tx always
honoured`, `specs/external-reporting/spec.md`) is completely unreachable.

The existing test suite does not catch this because the one test that puts two sockets on the
same port (`TwoEnabledTargets_BothReceiveDecode`, `ExternalReportingServiceTests.cs:91-136`) only
asserts outbound delivery — it never exercises inbound receipt on that same, silently-unbound
port.

### 3.2 Required fix — Part A: let the inbound bind coexist with a peer already on that port

Set `ReuseAddress` on the socket before binding, mirroring the real WSJT-X reference
implementation's own `ShareAddress | ReuseAddressHint` bind option — the exact mechanism
`design.md`'s own rationale ("the app listens on the same port it's configured to send to") is
relying on without actually implementing:

```csharp
if (desiredInboundPort > 0)
{
    try
    {
        var client = new UdpClient(AddressFamily.InterNetwork);
        client.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
        client.Client.Bind(new IPEndPoint(IPAddress.Any, desiredInboundPort));
        _inboundClient    = client;
        _inboundBoundPort = desiredInboundPort;
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex,
            "external-reporting: failed to bind inbound listener on port {Port}.",
            desiredInboundPort);
    }
}
```

(`AddressFamily` is in `System.Net.Sockets`, already `using`d in this file.)

### 3.3 Required fix — Part B: route the primary target's outbound sends through the same bound socket

Fixing the bind alone is necessary but may not be sufficient. `design.md`'s own stated rationale
is that GridTracker2 "replies from the same port it received on" — i.e. it addresses its Reply/
Halt Tx datagrams back to whatever **source port** it last observed traffic from us on. Today,
outbound sends for every target (including the first/primary one, whose port the inbound
listener binds to) go out through a **separate, unbound, ephemeral-port** `UdpClient`
(`Reconcile`, `_outboundClients.Add((target, new UdpClient()))`,
`ExternalReportingService.cs:244`). If GridTracker2 genuinely uses reply-to-sender semantics, its
replies go to that ephemeral port — not to the fixed port our inbound listener binds to — and are
lost regardless of Part A.

**Required:** for the target whose port equals the bound inbound port (by construction, this is
always `desiredEnabled[0]`, the primary target), send outbound datagrams **through the same
`_inboundClient` socket** rather than through a separate ephemeral `UdpClient`. Any additional
targets (index 1+, a second companion program on a different port) keep their own dedicated
outbound-only `UdpClient`s exactly as today — this fix only applies to the one target that shares
a port number with the inbound listener.

Suggested shape (adjust to fit the existing `_outboundClients` bookkeeping — the exact structure
is your call, but the send-through-the-bound-socket behaviour for the primary target is not
optional):

- When building `desiredEnabled`, treat index `0` specially: do not open a new ephemeral
  `UdpClient` for it; instead, record that sends to it should go through `_inboundClient`
  (`client.Client.SendTo(...)` or `UdpClient.Send(datagram, datagram.Length, target.Host,
  target.Port)` called on the shared instance).
- `SendToAllEnabledAsync` needs to resolve, per target, which socket to send from (shared
  `_inboundClient` for the primary target, dedicated `UdpClient` for the rest).
- If `_inboundClient` failed to bind (Part A's own catch block fired for some other reason), fall
  back to the current ephemeral-socket behaviour for the primary target too, so a bind failure
  degrades to "outbound-only, like before" rather than losing outbound delivery entirely.

**Verification:** this is the one piece of D-014 I could not confirm against a live GridTracker2
in this environment (task 10.3 was already flagged as skipped for the same reason before my
review). Implement it per the design rationale already committed to `design.md`, add the
round-trip test in §3.4 below to prove the *mechanism* works against a real loopback peer, and
flag task 10.3 as the place a live GridTracker2 session should specifically re-confirm reply
routing before this is fully trusted operationally — same spirit as the existing task 2.6/10.3
caveats, not a new category of risk.

### 3.4 Tests — D-014

Add to `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs`:

1. **`InboundBind_SucceedsWhenTargetPortAlreadyBoundByPeer`** — bind a fake peer `UdpClient`
   to a free port *before* constructing/starting the SUT (mirrors my review probe), configure a
   target on that same port, start the SUT, send a well-formed Halt Tx to that port from a third,
   independent sender socket, and assert `IQsoController.AbortAsync` **was** called. This is the
   direct regression test for the bind fix (§3.2).
2. **`OutboundToPrimaryTarget_UsesSharedInboundPort_ReplyRoundTrips`** — start the SUT with one
   target; from a fake-peer `UdpClient` bound to that target's port, receive an outbound Decode
   or Heartbeat datagram sent by the SUT and record its `RemoteEndPoint` (the *source* port the
   SUT actually sent from); assert that source port equals the SUT's configured target port (i.e.
   the primary target's sends genuinely come from the shared bound socket, not an ephemeral one).
   Then, from the fake peer, send a Halt Tx **back to that same port** and assert
   `IQsoController.AbortAsync` is called — proving the full send-then-reply loop a real
   GridTracker2 would exercise.

---

## 4. Absolute exclusion of synthetic/unknown-region traffic — no exceptions

### 4.1 What "no exceptions" means precisely

Today, `ExternalReportingService`'s outbound path receives whatever the decode pump hands it on
`externalReportingChannel`, which is `visibleResults` — the output of
`DecodeNoiseSuppressionFilter.Apply(results, configStore.Current.DecodeNoiseSuppression,
callsignRegionStore)` (`Program.cs:589-601`). **This is an operator-configurable filter**
(`DecodeNoiseSuppressionConfig.SuppressUnknownRegion`/`SuppressSynthetic`,
`src/OpenWSFZ.Abstractions/DecodeNoiseSuppressionConfig.cs:45,54`, default
`SuppressSynthetic=true` but `SuppressUnknownRegion` defaults from region-table presence and
**either can be turned off by the operator** on the Region-data settings tab). If the operator
turns both off, `Apply` returns `results` unchanged and Unknown-region/synthetic decodes flow
through to `externalReportingChannel` identically to every other consumer.

**That is not acceptable for external output, regardless of what the operator has chosen for the
decode panel or the QSO controllers.** The fix must be a **second, unconditional filter inside
`ExternalReportingService` itself** — not merely "default the suppression settings on," and not
exposed as any new Settings-tab checkbox. It must hold even when
`DecodeNoiseSuppressionConfig.SuppressUnknownRegion == false` and `SuppressSynthetic == false`.
Putting the guarantee inside the class that actually emits UDP traffic, rather than relying on
upstream channel wiring staying a particular way, means it survives future refactors of
`Program.cs`'s decode pump too — it does not depend on anyone remembering to keep filtering the
right channel.

Determination of "Unknown region" / "synthetic" for a `DecodeResult` is already fully solved
elsewhere and must be reused, not reinvented: `DecodeResult.Region` (`RegionInfo?`,
`src/OpenWSFZ.Abstractions/DecodeResult.cs:43`) is pre-resolved by the decoder pipeline.
`Region is null` = unknown region (a lookup miss); `Region.Synthetic == true` = R&R-study
synthetic entry (the dedicated `Q`-prefix catalog row,
`src/OpenWSFZ.Daemon/CallsignRegionDefaults.cs:84`). This is the exact same test
`DecodeNoiseSuppressionFilter` already uses (`src/OpenWSFZ.Daemon/DecodeNoiseSuppressionFilter.cs:50-63`)
— reuse the semantics, do not duplicate/re-derive them from the callsign string.

### 4.2 Required fix — Tier 1: outbound Decode datagrams (the literal, explicit ask)

In `ExternalReportingService.DecodeLoopAsync` (`ExternalReportingService.cs:286-312`), skip any
result that is unknown-region or synthetic **unconditionally**, before encoding:

```csharp
foreach (var r in batch.Results)
{
    // Absolute guarantee — NOT gated by DecodeNoiseSuppressionConfig, NOT configurable,
    // NOT an opt-out. R&R-synthetic and unknown-region decodes SHALL NEVER be broadcast to
    // any external program, regardless of the operator's decode-panel suppression settings.
    if (r.Region is null || r.Region.Synthetic)
    {
        _logger.LogDebug(
            "external-reporting: suppressed outbound Decode for '{Message}' — {Reason}.",
            r.Message, r.Region is null ? "unknown region" : "synthetic (R&R study)");
        continue;
    }

    var fields = new WsjtxDatagram.DecodeFields(/* unchanged */);
    await SendToAllEnabledAsync(WsjtxDatagram.EncodeDecode(AppId, fields)).ConfigureAwait(false);
}
```

The `Clear` datagram at the top of the loop iteration is **unaffected** — it must still fire every
cycle regardless of how many (or how few) decodes survive the filter, per the existing "Clear
sent on new decode cycle boundary" requirement.

### 4.3 Required fix — Tier 2: outbound Status and QSOLogged (same principle, other message types that can name a callsign)

Read literally, the Captain's instruction names "decodes." Read for intent — **no external
program may ever learn of a synthetic or unresolved callsign through this feature, full stop** —
two other outbound message types can leak one:

- **Status** (`BuildStatusFields`, `ExternalReportingService.cs:355-383`): while a QSO with a
  synthetic partner is active (only possible during an R&R study session, but real once one is
  running), `DxCall`/`DxGrid` carries that partner's callsign in **real time**, visible on
  GridTracker2's map before the QSO even completes.
- **QSOLogged** (`NotifyQsoLogged`, `ExternalReportingService.cs:395-412`): a completed QSO with
  a synthetic or unresolved partner would otherwise be reported to GridTracker2 as a real logged
  contact.

Neither `QsoRecord` (`src/OpenWSFZ.Abstractions/QsoRecord.cs`) nor the live `IQsoController.Partner`
string carries a pre-resolved `Region` — both are bare callsign strings. Add
`ICallsignRegionStore?` as a new optional constructor parameter to `ExternalReportingService`
(same pattern as the existing optional `ICatState?` parameter), wire it in `Program.cs`'s DI
factory (`services.AddSingleton<ICallsignRegionStore>(callsignRegionStore)` is already registered,
`Program.cs:395` — just add `sp.GetService<ICallsignRegionStore>()` to the `ExternalReportingService`
factory call, `Program.cs:449-454`), and add one shared helper:

```csharp
private bool IsSuppressedCallsign(string? callsign)
{
    if (string.IsNullOrWhiteSpace(callsign)) return false; // nothing to suppress
    var region = _regionStore?.TryGetRegion(callsign);
    return region is null || region.Synthetic;
}
```

Apply it:

- In `BuildStatusFields`: if `IsSuppressedCallsign(partner)`, send `DxCall = ""`, `DxGrid = ""`
  instead of the real values — the rest of Status (frequency, TX/RX state, decoding-enabled)
  still flows normally; only the fake callsign is withheld. Do **not** suppress the whole Status
  datagram — it has its own independent "at least once per heartbeat interval" requirement that
  must keep being met.
- In `NotifyQsoLogged`: if `IsSuppressedCallsign(record.PartnerCallsign)`, log at Information
  ("suppressed outbound QSOLogged for synthetic/unknown-region partner") and `return` before
  building/sending the datagram — mirroring the existing "no record on watchdog/operator abort"
  early-return pattern already in this method.

If, on reflection, the Captain considers Tier 2 out of scope for this pass, that is a call for
the Captain to make explicitly — do not silently drop it; flag it back to QA/the Captain rather
than deciding unilaterally either way.

### 4.4 Tests

Add to `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs`:

1. **`Decode_UnknownRegionAndSynthetic_NeverSentEvenWithSuppressionOff`** — configure
   `DecodeNoiseSuppressionConfig` with **both** `SuppressUnknownRegion: false` and
   `SuppressSynthetic: false` (the exact condition that currently lets them through), submit a
   batch containing one normal decode, one `Region: null` decode, and one `Region: { Synthetic:
   true }` decode; assert the fake target receives Clear + exactly **one** Decode datagram (the
   normal one only).
2. **`Decode_AllResultsSuppressed_StillSendsClear`** — a batch containing only unknown/synthetic
   entries still produces a Clear datagram, proving Clear isn't accidentally gated by the new
   filter.
3. **`Status_SyntheticPartner_DxCallAndGridBlanked`** — drive an active QSO (via the substitute
   `IQsoController`) reporting `Partner` as a known synthetic callsign; assert the next Status
   datagram's `DxCall`/`DxGrid` fields are empty, while other Status fields (frequency,
   `Transmitting`, `Decoding`) are populated normally.
4. **`Status_NormalPartner_DxCallPopulated`** — regression check: a real, resolvable partner
   callsign still appears in `DxCall` as before.
5. **`NotifyQsoLogged_SyntheticOrUnknownPartner_NeverSent`** — call `NotifyQsoLogged` with a
   `QsoRecord` whose `PartnerCallsign` resolves to synthetic (and, separately, to no region at
   all), and assert no QSOLogged datagram reaches the fake target either time.
6. **`NotifyQsoLogged_NormalPartner_StillSent`** — regression check for the existing
   `NotifyQsoLogged sends a QSOLogged datagram` test (`ExternalReportingServiceTests.cs:184`) —
   confirm it still passes unmodified.

---

## 5. Documentation — amend the in-flight change's own artifacts (no new change proposal)

Since `gridtracker-udp-reporting` has not merged/archived, amend it in place:

- **`openspec/changes/gridtracker-udp-reporting/specs/external-reporting/spec.md`** — amend the
  "Outbound Decode message" requirement to state the unconditional exclusion explicitly, and add
  a new scenario ("Unknown-region and synthetic decodes are never broadcast, even with
  suppression disabled"). Amend "Outbound Status message" and "Outbound QSOLogged message"
  similarly if Tier 2 is implemented (§4.3).
- **`openspec/changes/gridtracker-udp-reporting/design.md`** — add a Decision documenting why
  this exclusion is hard-coded and non-configurable (data-integrity: R&R synthetic signals must
  never reach a real-world tool/network via this channel), and note the D-014 socket-sharing
  rationale/verification status alongside the existing task 2.6/10.3 caveats.
- **`openspec/changes/gridtracker-udp-reporting/tasks.md`** — add new (unchecked, then checked
  off as completed) task items for both D-014 and the exclusion requirement, with their own test
  sub-items. Task 10.1's "1090/1090 passing" and 10.2's "53/53" figures will both need updating
  once the new tests land — do not leave stale counts in a task already marked `[x]`.
- **`REQUIREMENTS.md`** — append the unconditional-exclusion clause to FR-053 (outbound
  broadcaster) and, if Tier 2 lands, note it applies to Status/QSOLogged too. Add a revision-
  history row per the existing 1.31 row's pattern once this lands, or fold it into that row if it
  hasn't been committed elsewhere yet — check current `main` state before deciding which.

---

## 6. Acceptance Criteria

QA will verify all of the following before approving merge:

- [ ] **AC-1 (D-014):** With a fake peer already bound to the configured target's port before
  the daemon starts, `ExternalReportingService`'s inbound listener still binds successfully and
  a Halt Tx sent to that port is received and acted on.
- [ ] **AC-2 (D-014):** Outbound datagrams to the primary target are sent from the same local
  port the inbound listener is bound to (verified via `RemoteEndPoint` on a real loopback fake
  peer), and a reply sent to that port reaches the listener.
- [ ] **AC-3 (exclusion, Tier 1):** With `DecodeNoiseSuppressionConfig.SuppressUnknownRegion` and
  `SuppressSynthetic` both `false`, no unknown-region or synthetic `DecodeResult` ever produces an
  outbound Decode datagram to any target. Clear datagrams are unaffected.
- [ ] **AC-4 (exclusion, Tier 2 — if implemented):** No outbound Status datagram ever names a
  synthetic/unknown-region partner in `DxCall`/`DxGrid`; no outbound QSOLogged datagram is ever
  sent for a synthetic/unknown-region partner.
- [ ] **AC-5:** The exclusion in AC-3/AC-4 is not exposed as, or controllable via, any new
  Settings-page control or config field. It is unconditional.
- [ ] **AC-6:** No regression in any existing `ExternalReportingServiceTests.cs`,
  `WsjtxDatagramTests.cs`, `QsoAnswererServiceExternalReplyTests.cs`, or
  `DecodeNoiseSuppressionFilterTests.cs` test.
- [ ] **AC-7:** `openspec validate --strict --all` still passes.
- [ ] **AC-8:** Full test suite green; updated pass counts recorded in `tasks.md` task 10.1/10.2
  match the actual run, not the stale pre-fix figures.
- [ ] **AC-9:** `dotnet build` — zero errors, zero warnings.

---

## 7. References

- `src/OpenWSFZ.Daemon/ExternalReportingService.cs` — `Reconcile` (bind logic, §3), `DecodeLoopAsync`
  (§4.2), `BuildStatusFields`/`NotifyQsoLogged` (§4.3).
- `src/OpenWSFZ.Daemon/Program.cs:589-601` — decode-pump fan-out; confirms all three consumer
  channels currently receive the same operator-filterable `visibleResults`.
- `src/OpenWSFZ.Daemon/DecodeNoiseSuppressionFilter.cs:50-63` — the existing, operator-toggleable
  suppression this task's hard filter must NOT be confused with or rely on.
- `src/OpenWSFZ.Abstractions/DecodeNoiseSuppressionConfig.cs`, `DecodeResult.cs`,
  `CallsignRegionEntry.cs` (`RegionInfo.Synthetic`), `QsoRecord.cs`.
- `src/OpenWSFZ.Abstractions/ICallsignRegionStore.cs:34` (`TryGetRegion`),
  `src/OpenWSFZ.Daemon/CallsignRegionStore.cs`, `CallsignRegionDefaults.cs:84` (the dedicated
  `Q`-prefix synthetic catalog entry).
- `openspec/changes/gridtracker-udp-reporting/design.md` — original "GridTracker2 replies from
  the same port it received on" rationale that §3.3 implements properly.
- `openspec/changes/gridtracker-udp-reporting/specs/external-reporting/spec.md` — requirements
  to amend per §5.
- Privacy/GDPR callsign policy (NFR-021) — the project-wide convention that Q-prefix synthetic
  callsigns exist precisely so R&R test traffic is distinguishable from real traffic; this task
  is that same principle applied to a new egress point this application didn't have before.
