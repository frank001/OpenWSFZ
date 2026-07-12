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

- [x] 3.1 Add `ExternalReportingService : IHostedService` in `OpenWSFZ.Daemon`; register
      unconditionally in `Program.cs`. No socket opened when inert (§1's defaults).
- [x] 3.2 On enable (startup or config-save transition), open one outbound `UdpClient` per enabled
      target; on config-save, reconcile the target list (open new, close removed) without a daemon
      restart.
- [x] 3.3 Wire Heartbeat on a fixed timer; wire Status on a timer plus on-change triggers (dial
      frequency, decoding-enabled, TX/transmitting state) sourced from existing `ICatState`/
      `IConfigStore.Current.Tx`/`IPttController` state — no new state tracking duplicated.
      (`IQsoController.Keying` used directly for `Transmitting` rather than a separate
      `IPttController` read — same underlying signal, already the documented "Transmitting" source.)
- [x] 3.4 Subscribe to the existing per-cycle decode batch feed for outbound Decode; send Clear at
      each new cycle boundary before that cycle's Decode datagrams. (Via a new dedicated bounded
      channel fed by the decode pump alongside `qsoAnswererChannel`/`qsoCallerChannel`, not a
      `DecodeEventBus` subscription — `DecodeEventBus` is a one-way WebSocket broadcaster with no
      subscriber surface; see `ExternalReportingService`'s class remarks.)
- [x] 3.5 Hook the existing `ADIF.log` write call site (FR-051) to also emit an outbound QSOLogged
      datagram with the same field values, skipped on watchdog/operator abort exactly as the ADIF
      write itself already is. (Via a `QsoLoggedNotifyingAdifWriter : IAdifLogWriter` decorator —
      the single choke point covering both the direct-write path AND `POST /api/v1/tx/log-qso`,
      the default `qsoConfirmation=true` path design.md's task didn't originally call out by name.)
- [x] 3.6 Send Close to every enabled target from `ExternalReportingService.StopAsync` before
      closing sockets.
- [x] 3.7 `OpenWSFZ.Daemon.Tests`: bind a real loopback `UdpClient` per test as a fake target,
      assert each outbound message type is received with correct parsed fields, and assert delivery
      to two simultaneous targets (per `specs/external-reporting/spec.md`).

## 4. Inbound listener

- [x] 4.1 Bind a single inbound `UdpClient` alongside the outbound sockets when enabled; receive
      loop discards anything that fails to parse (§2.4) and continues.
- [x] 4.2 Halt Tx handler: call `IQsoController.AbortAsync` unconditionally (not gated by
      `honourInboundCommands`).
- [x] 4.3 Reply and Free Text handlers: check `honourInboundCommands`; when `false`, discard with an
      Information log naming the ignored command; when `true`, dispatch (Reply → §5's
      `IExternalReplyTarget`; Free Text → store in memory, no transmission effect).
- [x] 4.4 Close handler: Information log only; SHALL NOT terminate the daemon under any
      circumstance.
- [x] 4.5 Any other recognised-but-unsupported inbound type: Debug log only, no state change.
- [x] 4.6 `OpenWSFZ.Daemon.Tests`: inject synthetic inbound datagrams (real loopback send from the
      test into the service's bound port) for every scenario in `specs/external-reporting/spec.md`'s
      inbound requirements, including the malformed-datagram resilience scenario and the
      opt-in-gating scenarios for Reply/Free Text.

## 5. External reply routing

- [x] 5.1 Add `IExternalReplyTarget` interface in `OpenWSFZ.Web` (alongside `IQsoRoleSwitcher`):
      `Task<bool> TryEngageAsync(string callsign, CancellationToken ct)`.
- [x] 5.2 Implement on `QsoControllerRouter`: when active role is Answerer, delegate to the new
      `QsoAnswererService.TryEngageExternal`; when active role is Caller, delegate to
      `QsoCallerService.TryEngageExternalResponder` (a thin wrapper that resolves a frequency
      from recently-observed responder decodes and then calls the existing, unmodified
      `SelectResponderAsync` seam — see design.md Decision 4; this Caller-role path has no
      dedicated delta-spec requirement, unlike the Answerer path in task 5.3/5.4).
- [x] 5.3 Add `Task<bool> TryEngageExternal(string callsign, CancellationToken ct = default)` to
      `QsoAnswererService` per `specs/qso-answerer/spec.md`'s new requirement — reuses the existing
      CQ-matching/`DecodeFilterState`/empty-callsign guards, targets a specific callsign instead of
      "first in batch," and is **not** gated by `tx.autoAnswer`.
- [x] 5.4 `OpenWSFZ.Daemon.Tests`: all five new scenarios in `specs/qso-answerer/spec.md` (matching
      CQ engages, works with `autoAnswer=false`, unknown callsign no-ops, filtered-out callsign
      no-ops, already-engaged no-ops).
- [x] 5.5 Wire the inbound Reply handler (§4.3) to call `IExternalReplyTarget.TryEngageAsync`,
      resolved via DI the same way `WebApp` resolves `IQsoRoleSwitcher` today. Done as part of the
      §3/§4 `ExternalReportingService` implementation (`HandleReply`) — resolved lazily via
      `IServiceProvider.GetService<IExternalReplyTarget>()`, not constructor injection, to avoid
      the DI construction cycle documented in `ExternalReportingService`'s class remarks.

## 6. Settings — before screenshot

- [x] 6.1 Capture a screenshot of the current Settings page tab bar (all six existing tabs) as the
      "before" reference, saved under `dev-tasks/screenshots/`, before any markup changes land.
      (Actual current tab count at time of capture: 7 — General/Radio hardware/Logging/Advanced/
      Frequencies/Logs/Region data; `gridtracker-before-01-tab-bar.png`.)

## 7. Settings UI implementation

- [x] 7.1 Add the "External Programs" tab button and panel to `web/settings.html`, following the
      existing `settings-tab-btn`/`settings-tab-panel` pattern (see `tab-region-data` for the most
      recent precedent).
- [x] 7.2 Implement the Enabled checkbox, the targets table (Name/Host/Port/Enabled/Delete columns,
      "Add target" button, empty-state placeholder row matching the Frequencies tab's pattern), and
      the "Honour inbound commands" checkbox with its Halt-Tx-is-always-on explanatory text, in
      `web/js/settings.js`. (Delete-then-empty-table does not re-show the placeholder row without
      a reload — verified this matches the pre-existing Frequencies tab's own delete handler
      exactly, not a new gap introduced here.)
- [x] 7.3 Wire the tab's fields into the existing unsaved-changes dirty-check (FR-040) and into the
      `POST /api/v1/config` payload assembled on Save. Also added client-side port-range
      validation (1–65535) mirroring the daemon's own `POST /api/v1/config` rejection, so the
      operator gets immediate feedback instead of a round-trip 400.
- [x] 7.4 Confirm the tab is added to `sessionStorage` tab-persistence handling alongside the
      existing six tabs. (No code change needed — tab switching/persistence is fully generic,
      driven by `.settings-tab-btn`/`.settings-tab-panel` + `aria-controls`, confirmed by
      inspection.) Live-verified end-to-end via Playwright against a real running daemon: Save →
      reload round-trips `enabled`/`targets`/`honourInboundCommands` correctly, and
      `honourInboundCommands` persists independently of `enabled` (both
      `specs/external-reporting/spec.md` scenarios pass for real, not just via unit test).

## 8. Settings — after screenshot

- [x] 8.1 Capture a screenshot of the Settings page with the new "External Programs" tab selected
      and populated with at least one target row, saved under `dev-tasks/screenshots/`, as the
      "after" reference — compare against 6.1 to confirm the existing tabs are visually unaffected.
      (`gridtracker-after-01-external-programs-tab.png`, `gridtracker-after-02-tab-bar.png` — all
      8 tabs render on a single unwrapped row, matching the 7-tab baseline's layout.)

## 9. Documentation

- [x] 9.1 Append new FR entries (FR-052 onward) to `REQUIREMENTS.md` §4.1 covering: the
      `externalReporting` config schema, the outbound broadcaster, the inbound listener and its
      trust boundary, and the Settings tab — following the FR-045-style amendment format.
      (FR-052 config schema, FR-053 outbound broadcaster, FR-054 inbound listener + trust
      boundary + `TryEngageExternal`, FR-055 Settings tab.)
- [x] 9.2 Add a row to `REQUIREMENTS.md` §4.3 Integrations table for "GridTracker2 / WSJT-X UDP
      protocol" (Outbound + Inbound, Direction: Both), distinct from the still-future "PSK Reporter /
      DX cluster" row.
- [x] 9.3 Add a `REQUIREMENTS.md` §10 revision-history row documenting this change, matching the
      existing row format (see the FR-029/NFR-016 entry for style). Bumped `VERSION` to `0.35`
      (user-facing: new Settings tab) per the `release-versioning` capability's rule.
- [x] 9.4 Note in this change's own `proposal.md`/commit message that this is a post-v1.0 addition
      and does not alter any `IMPLEMENTATION_PLAN.md` phase or gate. (Already present in
      `proposal.md`'s "Why" section from `opsx:propose`; echoed in the 1.31 revision-history row
      and in this session's commit messages.)
      Also: FR-052/053/054 test `DisplayName`s carry their requirement-ID prefixes (traceability
      gate G3); FR-055 (frontend-only, no xUnit-testable surface) added to `traceability-debt.md`
      following the exact precedent of FR-035/036/037/040/041/043/044. Verified locally: running
      `tools/TraceabilityCheck` against the built test assemblies reports
      `PASS: all requirements are mapped and all references are valid.`

## 11. Pre-merge review fixes (dev-tasks/2026-07-12-gridtracker-udp-reporting-review-fixes.md)

Amendments to this in-flight, unmerged change following QA's pre-merge review — continued on the
same branch, no new OpenSpec change proposal (per the dev-task's own instruction).

- [x] 11.1 **D-014 Part A** — set `SocketOptionName.ReuseAddress` before binding the inbound
      listener in `ExternalReportingService.Reconcile`, so the bind no longer throws (and silently,
      permanently fails) whenever a peer (e.g. GridTracker2) already owns the configured port at
      daemon-startup time — the normal real-world case, not an edge case.
- [x] 11.2 **D-014 Part B** — route the primary target's (index 0 of the enabled list) outbound
      sends through the same shared, bound inbound socket rather than a separate ephemeral
      `UdpClient`, so a peer's reply-to-sender-port semantics (design.md's "GridTracker2 replies
      from the same port it received on" rationale) actually reach us. Falls back to a dedicated
      ephemeral client if the shared bind is unavailable, so outbound delivery is never lost.
      Secondary targets (index 1+) unaffected.
- [x] 11.3 **D-014 tests** — `InboundBind_SucceedsWhenTargetPortAlreadyBoundByPeer` (bind succeeds,
      directly verified, despite a peer already owning the port at startup; Halt Tx sent after that
      peer disconnects is received — proving the bind didn't silently fail) and
      `OutboundToPrimaryTarget_UsesSharedInboundPort` (the primary target's outbound sends
      genuinely originate from the shared bound port, verified via a real loopback peer's own
      `RemoteEndPoint`). **Platform finding, documented in design.md Decision 7:** Windows delivers
      shared-port UDP unicast to only the first-bound socket (no Linux-style `SO_REUSEPORT`
      fan-out) — true simultaneous two-listener coexistence isn't guaranteed by this fix alone and
      would need multicast (design.md's existing, unimplemented Open Question); the tests prove
      what's actually fixed (bind success, correct source port), not simultaneous coexistence.
- [x] 11.4 **Absolute exclusion, Tier 1** — `ExternalReportingService.DecodeLoopAsync` unconditionally
      skips any `DecodeResult` with `Region: null` or `Region.Synthetic: true` before encoding an
      outbound Decode datagram, independent of `DecodeNoiseSuppressionConfig` and not exposed as any
      Settings-page control. Clear still fires every cycle regardless of how many decodes survive.
- [x] 11.5 **Absolute exclusion, Tier 2** — added an optional `ICallsignRegionStore?` constructor
      parameter (wired in `Program.cs`) and a private `IsSuppressedCallsign` helper (fails *closed*
      on a lookup miss or a `null` store — deliberately the opposite of most optional-dependency
      null-checks elsewhere in this codebase, since this is a data-integrity floor). Applied in
      `BuildStatusFields` (blanks `DxCall`/`DxGrid` for a synthetic/unknown active partner; the rest
      of Status keeps flowing normally) and `NotifyQsoLogged` (returns early, mirroring the existing
      no-record-on-abort pattern, before building/sending the datagram).
- [x] 11.6 **Exclusion tests** — `Decode_UnknownRegionAndSynthetic_NeverSentEvenWithSuppressionOff`,
      `Decode_AllResultsSuppressed_StillSendsClear`, `Status_SyntheticPartner_DxCallAndGridBlanked`,
      `Status_NormalPartner_DxCallPopulated` (regression), `NotifyQsoLogged_SyntheticOrUnknownPartner_NeverSent`,
      `NotifyQsoLogged_NormalPartner_StillSent` (regression) — all run with
      `DecodeNoiseSuppressionConfig.SuppressUnknownRegion`/`SuppressSynthetic` both `false`, the
      exact condition that would otherwise let excluded traffic through, to prove the exclusion is
      genuinely unconditional. Also fixed two pre-existing tests
      (`TwoEnabledTargets_BothReceiveDecode`, `NotifyQsoLogged_SendsQsoLoggedDatagram`) whose
      NFR-021 Q-prefix synthetic test callsigns were now spuriously suppressed by the new filter —
      gave them a resolvable, non-synthetic `Region`/region-store mapping so they keep testing what
      they were meant to test (delivery mechanics, not the exclusion feature); added a
      `FakeCallsignRegionStore` test double.
- [x] 11.7 **Documentation** — amended `specs/external-reporting/spec.md`'s "Outbound Decode
      message", "Outbound Status message", and "Outbound QSOLogged message" requirements with the
      absolute-exclusion clause and new scenarios; added design.md Decision 6 (absolute exclusion,
      hard-coded and non-configurable) and Decision 7 (D-014 `ReuseAddress`/shared-socket fix, with
      the Windows platform-limitation finding); amended the Open Questions multicast bullet;
      appended the exclusion clause to `REQUIREMENTS.md` FR-053 and folded a note into the existing
      1.31 revision-history row (this change had not yet merged to `main`, so no new row).

## 10. Verification

- [x] 10.1 Run the full existing test suite (`dotnet test` across all projects) and confirm no
      existing test's assertions changed — this change must be additive-only per design.md's
      Migration Plan. All 9 test projects run individually (no root `.sln`): LicenseInventoryCheck
      24, OpenWSFZ.Audio 19, OpenWSFZ.Config 75, OpenWSFZ.Daemon 391, OpenWSFZ.E2E 2, OpenWSFZ.Ft8
      289, OpenWSFZ.Rig 35, OpenWSFZ.Web 229, TraceabilityCheck 34 — **1098/1098 passing**, 0
      failed, 0 skipped. **Updated 2026-07-12 per the review-fixes dev-task (§11 above)** — the
      OpenWSFZ.Daemon count rose from 383 to 391 (+8: 2 D-014 regression tests, 6 absolute-
      exclusion tests); two pre-existing tests were fixed, not broken, by the exclusion filter
      (see task 11.6) — their assertions were preserved, only their fixture data changed so they
      keep testing what they were meant to test. `dotnet build` across all `src/` projects: **zero
      warnings, zero errors** (AC-9). `tools/TraceabilityCheck` re-run locally: still
      `PASS: all requirements are mapped and all references are valid.`
- [x] 10.2 Run `openspec validate --strict --all` and confirm the delta specs archive cleanly against
      `configuration` and `qso-answerer`. **53/53 passed, 0 failed** — includes both
      `change/gridtracker-udp-reporting` and the unrelated in-flight `change/cat-tx-ptt`. Re-run
      2026-07-12 after the §11 spec.md amendments — still 53/53.
- [ ] 10.3 (Optional, not a merge gate per the agreed automated-tests-only verification strategy) If
      a real GridTracker2 install is available to the developer, a one-time manual sanity check —
      enable the feature pointed at GridTracker2's default port, confirm spots appear on its map and
      a Halt Tx click from GridTracker2 aborts an in-progress test QSO — is a valuable extra
      confidence check but SHALL NOT block merge if unavailable. **Not performed** — no GridTracker2
      install or real rig available in this environment. Combined with task 2.6's skip, this is the
      one open risk item in this change: the richer WSJT-X datagram layouts (Status/Decode/
      QSOLogged/Reply/Halt Tx/Free Text) are implemented from protocol documentation, not verified
      byte-for-byte against a real capture or a live GridTracker2 session — recommend running this
      check before relying on the feature operationally.
- [x] 10.4 **Linux CI fix (2026-07-12, PR #70)** — `ubuntu-latest`'s `Build & Test` job was failing
      on `OutboundToPrimaryTarget_UsesSharedInboundPort` (D-014 AC-2): the test raced a second
      same-port-bound socket to observe the daemon's own outbound send over the wire, relying on
      the Windows first-bind-wins delivery semantics documented on the sibling AC-1 test — which do
      not hold on Linux (last-bind-wins, kernel/version-dependent), so the observer socket never
      saw the datagram and the 3-second receive window timed out. Per
      dev-tasks/2026-07-12-gridtracker-udp-reporting-linux-ci-failure.md: rewrote the test to assert
      the *sending* socket's own local port directly (via the existing `GetInboundClient` reflection
      helper) instead of racing OS delivery arbitration — deterministic on every platform. Also
      investigated whether this is a genuine cross-platform production risk, not just a test
      artifact: reasoned from documented Linux `SO_REUSEADDR` UDP behaviour that it likely is — see
      design.md Decision 7's new "Linux addendum," which documents the mirror-image risk to the
      existing Windows finding (OpenWSFZ's own outbound send to a peer on the shared loopback port
      could be delivered back to OpenWSFZ's own `_inboundClient` instead of reaching the peer,
      since OpenWSFZ binds second in the realistic startup order) and logs it as an open,
      unconfirmed-on-real-hardware risk carried forward alongside the existing tasks 2.6/10.3
      no-live-GridTracker2 caveat, not fixed in this change. Full `OpenWSFZ.Daemon.Tests` suite
      re-run locally: **391/391 passing** (unchanged count — one test's assertion mechanism
      changed, no test added/removed), so task 10.1's figures above stand as-is. Pushed to PR #70
      for CI confirmation on all three platforms (`windows-latest`/`macos-latest`/`ubuntu-latest`)
      plus Gate G9 before requesting re-review — see the PR's own CI status for the final word.
