## 1. Configuration schema

- [x] 1.1 Add `Role` (string enum `"leader"`|`"follower"`, default `"leader"`), `LeaderUrl` (nullable
      string, default `null`), and `FollowerUrls` (list of string, default `[]`) to
      `ExternalReportingConfig` in `OpenWSFZ.Abstractions`, following the exact same
      STJ-omitted-key-guard `[JsonConstructor]` parameter shape `InstanceId` already uses
      (`fix-external-reporting-appid-collision`).
- [x] 1.2 `WebApp.cs`'s `POST /api/v1/config` handler: extend the existing raw-JSON key-presence guard
      (currently checks for `instanceId`) to also preserve `role`/`leaderUrl`/`followerUrls` when
      omitted from a Settings-page-shaped save, mirroring the existing guard's rationale exactly —
      do not duplicate the JsonDocument parse, extend the same one.
- [x] 1.3 `POST /api/v1/config` validation: reject (`HTTP 400`, no partial persistence) `role:
      "follower"` with a missing/empty `leaderUrl`, matching the existing out-of-range-port
      validation-error pattern.
- [x] 1.4 `OpenWSFZ.Config.Tests`/`OpenWSFZ.Web.Tests`: missing-key-defaults test, round-trip test, the
      two Settings-page-shaped-save-preserves-value tests, and the follower-without-leaderUrl
      rejection test — the six new scenarios in this change's `specs/configuration/spec.md` delta.

## 2. Follower-side relay send path

- [x] 2.1 In `ExternalReportingService`, branch every existing outbound send call site
      (`SendToAllEnabledAsync`'s callers: Heartbeat/Status/Decode/QSOLogged/Clear/Close) on
      `_configStore.Current.ExternalReporting.Role`: `"leader"` keeps today's direct-UDP path
      unchanged; `"follower"` builds the same encoded byte array (no change to any `WsjtxDatagram.Encode*`
      call) and hands it to a new `RelayToLeaderAsync` instead of `SendToAllEnabledAsync`.
- [x] 2.2 Group one decode cycle's Status (if changed/due) and Decode datagrams into a single relay
      batch/POST body (per design.md Decision 3's ordering requirement) rather than one POST per
      datagram; Heartbeat/QSOLogged/Clear/Close each relay as their own single-datagram batch.
- [x] 2.3 `RelayToLeaderAsync`: `POST` the batch (base64-encoded datagram bytes, in order) to
      `{leaderUrl}/api/v1/external-reporting/relay` using a shared `HttpClient` with a short timeout
      (sub-second — this is a loopback/LAN call, not a WAN one).
- [x] 2.4 Degrade-and-reconcile: on relay failure (connect error, timeout, non-2xx), send the same
      batch directly to `targets` under this instance's own `instanceId` (reuse the existing
      `"leader"`-path send code, do not duplicate it) and log a Warning at most once per
      leader-unreachable state (mirror the existing `_resolutionWarned` once-per-failure-state
      pattern). Clear the warned state and resume relaying on the next successful POST.
- [x] 2.5 `OpenWSFZ.Daemon.Tests`: relay batch is well-formed and ordered (assert against a fake HTTP
      handler); degrade-to-direct-send on relay failure; automatic reconciliation once the fake
      leader endpoint starts responding again; absolute synthetic/unknown-region exclusion still
      applies before a datagram ever reaches the relay path (reuse existing exclusion test fixtures).

## 3. Leader-side relay endpoint and dispatch ordering

- [x] 3.1 Add `POST /api/v1/external-reporting/relay` in `WebApp.cs`: accepts `{ followerInstanceId,
      datagrams: [{ type, bytesBase64 }] }`; returns HTTP 503 (no send attempted) when this instance's
      own `externalReporting.enabled` is `false` or `role` is not `"leader"`.
- [x] 3.2 Add a single-consumer dispatch queue in `ExternalReportingService` that both the leader's own
      outbound sends (Heartbeat/Status/Decode/QSOLogged/Clear/Close) and every accepted relay batch
      enqueue onto, so that no batch is interleaved with another mid-dispatch (design.md Decision 3).
      This is the mechanism, not merely the config, that makes "single connection" true — do not skip
      it in favour of just forwarding relay batches straight to `SendToAllEnabledAsync` from the HTTP
      handler's own thread, which would reintroduce the interleaving risk design.md identifies.
- [x] 3.3 `OpenWSFZ.Daemon.Tests`/`OpenWSFZ.Web.Tests`: relay endpoint dispatches a batch's datagrams in
      order to every enabled target; a concurrent leader-own-traffic-plus-relayed-batch scenario
      proves no interleaving (assert via a fake loopback target capturing raw received bytes in
      arrival order); 503 rejection when not configured as an enabled leader.

## 4. Inbound Halt Tx broadcast to followers

- [x] 4.1 Extend the leader's existing `HandleHaltTxAsync` to also `POST /api/v1/tx/abort` (the
      existing endpoint, unmodified) to every URL in `followerUrls`, concurrently, best-effort — one
      follower's failure/timeout SHALL NOT block the leader's own `AbortAsync` call or delivery to any
      other follower.
- [x] 4.2 `OpenWSFZ.Daemon.Tests`: Halt Tx aborts the leader and every reachable configured follower;
      an unreachable follower does not block the leader's own abort or a second, reachable follower.

## 5. Inbound Reply — v1 scope diagnostic logging

- [x] 5.1 In the leader's existing Reply handler, when `TryExtractCallsign` succeeds but the callsign
      is not found in this instance's own current decode batch, log a distinct Information entry
      (separate from the existing "no callsign could be extracted" log) naming the callsign — no
      behavioural change, this is purely a diagnosability improvement per design.md Decision 5's
      documented v1 limitation.
- [x] 5.2 `OpenWSFZ.Daemon.Tests`: the new distinct log entry fires for a callsign absent from the
      leader's own decode batch, and the pre-existing "no callsign extracted" log path is unchanged.

## 6. Documentation

- [x] 6.1 Append new FR entries (FR-063 onward) to `REQUIREMENTS.md` §4.1 covering: the
      `role`/`leaderUrl`/`followerUrls` config schema, the follower relay send path and its degrade
      fallback, the leader relay endpoint and its ordering guarantee, and Halt-Tx-broadcast-to-
      followers — following the existing FR-052-style amendment format
      (`gridtracker-udp-reporting`) and the FR-062-style amendment format
      (`fix-external-reporting-appid-collision`).
- [x] 6.2 Update the `REQUIREMENTS.md` §4.3 Integrations table row for "GridTracker2 / WSJT-X UDP
      protocol" to note multi-instance leader/follower relay support.
- [x] 6.3 Add a `REQUIREMENTS.md` §10 revision-history row documenting this change, matching the
      existing row format. Bump `VERSION` per the `release-versioning` capability's rule if any
      user-facing surface ships (none is planned in this change's scope — no Settings-page tab
      changes — confirm against the final diff before deciding whether a bump is warranted).
- [x] 6.4 Ensure every new xUnit test's `DisplayName` carries its requirement-ID prefix (traceability
      gate G3); re-run `tools/TraceabilityCheck` and confirm `PASS: all requirements are mapped and
      all references are valid.`

## 7. Verification

- [x] 7.1 Run the full existing test suite (`dotnet test` across all projects) and confirm every
      pre-existing test's assertions are unchanged — this change must be additive-only for any
      instance left at `role: "leader"` with no followers, per design.md's Migration Plan.
- [x] 7.2 Run `openspec validate --strict --all` and confirm this change's delta specs archive cleanly
      against `external-reporting` and `configuration`.
- [ ] 7.3 Per `decode-panel-filtering-live-verification-policy`-style precedent for this capability:
      once implemented, hand back to QA for a live two-instance verification against a real
      GridTracker2 (and, if reachable that session, confirmation that PSK Reporter actually receives
      spots) — this is the change's actual acceptance criterion and cannot be fully confirmed by
      automated tests alone (GridTracker2's own instance-selection/PSK-relay behaviour that motivated
      this change was itself only discoverable live, not from either codebase). Not performed as part
      of authoring these artifacts (QA session, no `src/` changes made here per HK-011).
