## 1. Configuration schema

- [x] 1.1 Add `ExternalReportingConfig`/`ExternalReportingTarget` records to `OpenWSFZ.Config`
      (`enabled` bool default `false`; `targets` list of `{ name, host, port, enabled }`;
      `honourInboundCommands` bool default `false`), referenced from `AppConfig` as
      `ExternalReporting`.
- [x] 1.2 Deserialisation: missing `externalReporting` key yields the all-defaults object (mirror
      `CatConfig`'s missing-key handling). Add the section to the default config written on first
      run.
- [x] 1.3 `POST /api/v1/config` validation: reject (`HTTP 400`, no partial persistence) any target
      entry with `port` outside `1`–`65535`, matching the existing validation-error pattern.
- [x] 1.4 `OpenWSFZ.Config.Tests`: round-trip test, missing-key-defaults test, out-of-range-port
      rejection test (`specs/configuration/spec.md` scenarios).

## 2. WSJT-X datagram serialisation

- [x] 2.1 Add internal `WsjtxDatagram` static class in `OpenWSFZ.Daemon` implementing the
      magic-number + schema-version header and big-endian primitive read/write helpers, with no
      dependency on any other OpenWSFZ type.
- [x] 2.2 Implement encode for: Heartbeat, Status, Decode, Clear, QSOLogged, Close.
- [x] 2.3 Implement decode for: Heartbeat, Reply, Halt Tx, Free Text, Close, and a generic
      "recognised-but-unsupported-type" path (Replay, Location, Highlight Callsign, Switch
      Configuration, Configure, etc.) that consumes the datagram without error.
- [x] 2.4 Decode paths SHALL never throw on malformed input — truncated/garbage buffers become a
      discarded-datagram result, not an exception.
- [x] 2.5 `OpenWSFZ.Daemon.Tests`: byte-exact encode tests for every outbound type (assert exact
      byte sequence, not just field round-trip) and decode tests for every inbound type, including a
      fuzzed/truncated-buffer test proving no exception escapes.
- [~] 2.6 SKIPPED — no real WSJT-X/GridTracker2 wire capture was available in this environment.
      **Risk flag:** the field layouts for Status, Decode, QSOLogged, Reply, Halt Tx, and Free Text
      are implemented from documented protocol knowledge, not verified against a live capture —
      recommend running this task for real (or task 10.3's manual GridTracker2 sanity check) before
      relying on this feature in production.

## 3. Outbound broadcaster

- [ ] 3.1 Add `ExternalReportingService : IHostedService` in `OpenWSFZ.Daemon`; register
      unconditionally in `Program.cs`. No socket opened when inert (§1's defaults).
- [ ] 3.2 On enable (startup or config-save transition), open one outbound `UdpClient` per enabled
      target; on config-save, reconcile the target list (open new, close removed) without a daemon
      restart.
- [ ] 3.3 Wire Heartbeat on a fixed timer; wire Status on a timer plus on-change triggers (dial
      frequency, decoding-enabled, TX/transmitting state) sourced from existing `ICatState`/
      `IConfigStore.Current.Tx`/`IPttController` state — no new state tracking duplicated.
- [ ] 3.4 Subscribe to the existing per-cycle decode batch feed (same one `QsoAnswererService`
      consumes) for outbound Decode; send Clear at each new cycle boundary before that cycle's
      Decode datagrams.
- [ ] 3.5 Hook the existing `ADIF.log` write call site (FR-051) to also emit an outbound QSOLogged
      datagram with the same field values, skipped on watchdog/operator abort exactly as the ADIF
      write itself already is.
- [ ] 3.6 Send Close to every enabled target from `ExternalReportingService.StopAsync` before
      closing sockets.
- [ ] 3.7 `OpenWSFZ.Daemon.Tests`: bind a real loopback `UdpClient` per test as a fake target,
      assert each outbound message type is received with correct parsed fields, and assert delivery
      to two simultaneous targets (per `specs/external-reporting/spec.md`).

## 4. Inbound listener

- [ ] 4.1 Bind a single inbound `UdpClient` alongside the outbound sockets when enabled; receive
      loop discards anything that fails to parse (§2.4) and continues.
- [ ] 4.2 Halt Tx handler: call `IQsoController.AbortAsync` unconditionally (not gated by
      `honourInboundCommands`).
- [ ] 4.3 Reply and Free Text handlers: check `honourInboundCommands`; when `false`, discard with an
      Information log naming the ignored command; when `true`, dispatch (Reply → §5's
      `IExternalReplyTarget`; Free Text → store in memory, no transmission effect).
- [ ] 4.4 Close handler: Information log only; SHALL NOT terminate the daemon under any
      circumstance.
- [ ] 4.5 Any other recognised-but-unsupported inbound type: Debug log only, no state change.
- [ ] 4.6 `OpenWSFZ.Daemon.Tests`: inject synthetic inbound datagrams (real loopback send from the
      test into the service's bound port) for every scenario in `specs/external-reporting/spec.md`'s
      inbound requirements, including the malformed-datagram resilience scenario and the
      opt-in-gating scenarios for Reply/Free Text.

## 5. External reply routing

- [ ] 5.1 Add `IExternalReplyTarget` interface in `OpenWSFZ.Web` (alongside `IQsoRoleSwitcher`):
      `Task<bool> TryEngageAsync(string callsign, CancellationToken ct)`.
- [ ] 5.2 Implement on `QsoControllerRouter`: when active role is Answerer, delegate to the new
      `QsoAnswererService.TryEngageExternal`; when active role is Caller, delegate to the existing,
      unmodified `QsoCallerService.SelectResponderAsync`.
- [ ] 5.3 Add `Task<bool> TryEngageExternal(string callsign, CancellationToken ct = default)` to
      `QsoAnswererService` per `specs/qso-answerer/spec.md`'s new requirement — reuses the existing
      CQ-matching/`DecodeFilterState`/empty-callsign guards, targets a specific callsign instead of
      "first in batch," and is **not** gated by `tx.autoAnswer`.
- [ ] 5.4 `OpenWSFZ.Daemon.Tests`: all five new scenarios in `specs/qso-answerer/spec.md` (matching
      CQ engages, works with `autoAnswer=false`, unknown callsign no-ops, filtered-out callsign
      no-ops, already-engaged no-ops).
- [ ] 5.5 Wire the inbound Reply handler (§4.3) to call `IExternalReplyTarget.TryEngageAsync`,
      resolved via DI the same way `WebApp` resolves `IQsoRoleSwitcher` today.

## 6. Settings — before screenshot

- [ ] 6.1 Capture a screenshot of the current Settings page tab bar (all six existing tabs) as the
      "before" reference, saved under `dev-tasks/screenshots/`, before any markup changes land.

## 7. Settings UI implementation

- [ ] 7.1 Add the "External Programs" tab button and panel to `web/settings.html`, following the
      existing `settings-tab-btn`/`settings-tab-panel` pattern (see `tab-region-data` for the most
      recent precedent).
- [ ] 7.2 Implement the Enabled checkbox, the targets table (Name/Host/Port/Enabled/Delete columns,
      "Add target" button, empty-state placeholder row matching the Frequencies tab's pattern), and
      the "Honour inbound commands" checkbox with its Halt-Tx-is-always-on explanatory text, in
      `web/js/settings.js`.
- [ ] 7.3 Wire the tab's fields into the existing unsaved-changes dirty-check (FR-040) and into the
      `POST /api/v1/config` payload assembled on Save.
- [ ] 7.4 Confirm the tab is added to `sessionStorage` tab-persistence handling alongside the
      existing six tabs.

## 8. Settings — after screenshot

- [ ] 8.1 Capture a screenshot of the Settings page with the new "External Programs" tab selected
      and populated with at least one target row, saved under `dev-tasks/screenshots/`, as the
      "after" reference — compare against 6.1 to confirm the existing tabs are visually unaffected.

## 9. Documentation

- [ ] 9.1 Append new FR entries (FR-052 onward) to `REQUIREMENTS.md` §4.1 covering: the
      `externalReporting` config schema, the outbound broadcaster, the inbound listener and its
      trust boundary, and the Settings tab — following the FR-045-style amendment format.
- [ ] 9.2 Add a row to `REQUIREMENTS.md` §4.3 Integrations table for "GridTracker2 / WSJT-X UDP
      protocol" (Outbound + Inbound, Direction: Both), distinct from the still-future "PSK Reporter /
      DX cluster" row.
- [ ] 9.3 Add a `REQUIREMENTS.md` §10 revision-history row documenting this change, matching the
      existing row format (see the FR-029/NFR-016 entry for style).
- [ ] 9.4 Note in this change's own `proposal.md`/commit message that this is a post-v1.0 addition
      and does not alter any `IMPLEMENTATION_PLAN.md` phase or gate.

## 10. Verification

- [ ] 10.1 Run the full existing test suite (`dotnet test` across all projects) and confirm no
      existing test's assertions changed — this change must be additive-only per design.md's
      Migration Plan.
- [ ] 10.2 Run `openspec validate --strict --all` and confirm the delta specs archive cleanly against
      `configuration` and `qso-answerer`.
- [ ] 10.3 (Optional, not a merge gate per the agreed automated-tests-only verification strategy) If
      a real GridTracker2 install is available to the developer, a one-time manual sanity check —
      enable the feature pointed at GridTracker2's default port, confirm spots appear on its map and
      a Halt Tx click from GridTracker2 aborts an in-progress test QSO — is a valuable extra
      confidence check but SHALL NOT block merge if unavailable.
