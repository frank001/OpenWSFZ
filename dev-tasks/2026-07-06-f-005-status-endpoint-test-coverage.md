# DEV TASK — F-005: add missing test coverage for HashTableRejectCount on the status/WS surface

**Date:** 2026-07-06
**Prepared by:** QA Engineer
**Found during:** QA review of `feat/f-005-hash-table-saturation-diagnostic` (uncommitted
working tree at review time, based on `main@7340e45`), before merge.
**Severity:** Minor / non-blocking — no functional defect. Independent verification during
review (ran the full Ft8/Daemon/Web suites, checked the rebuilt DLL's exports and embedded
shim version directly) confirms the feature itself works. This is a test-coverage gap only.
**OpenSpec change:** `openspec/changes/f-005-hash-table-saturation-diagnostic/` — extends
tasks.md §4 (Tests) and closes a residual instance of design.md's Risk 1 ("the getter is added
but nothing ever calls it") that the existing tests don't fully cover.
**Branch:** continue on the existing `feat/f-005-hash-table-saturation-diagnostic` branch — do
not open a new one; this change hasn't merged yet, so the missing tests belong in the same PR.

---

## 1. Context

F-005 adds a read-only native getter (`ft8_get_hash_table_reject_count`) for the hash table's
reject-when-full counter, and wires it through two independent surfaces:

1. **Session-end log line** (design.md D2, tasks.md §3.1) — `HashTableRejectCountReporter`,
   called from `Program.cs`'s `ApplicationStopping` hook.
2. **Live HTTP/WS surface** (tasks.md §3.2, marked optional/stretch — **"Captain elected to
   include it"**) — `DaemonStatus.HashTableRejectCount`, populated via a
   `Func<int> hashTableRejectCountProvider` threaded through `WebApp.Create` into three response
   sites (`GET /api/v1/status`, `POST /api/v1/decode/start`, `POST /api/v1/decode/stop`) and the
   initial WebSocket `status` event in `WebSocketHub.HandleAsync`.

Surface 1 got exactly the test design.md's Risk 1 asked for:
`tests/OpenWSFZ.Daemon.Tests/HashTableRejectCountReporterTests.cs` proves the log line is
actually emitted, with the right value, and that a native/ABI fault is contained rather than
propagated.

Surface 2 got no equivalent test. A repo-wide search at review time
(`grep -rn "HashTableRejectCount" tests/OpenWSFZ.Web.Tests/*.cs`) returned nothing — no test
asserts the field appears in the `GET /api/v1/status` JSON body, in the `decode/start`/
`decode/stop` responses, or in the WebSocket handshake's `status` payload.

This stands out because there is direct, current precedent for exactly this kind of test in the
same file: `tests/OpenWSFZ.Web.Tests/StatusAndBindingTests.cs` lines 55–87 already contains two
tests for the sibling `shimVersion` field (added by F-001) —
`GetStatus_IncludesShimVersionField` (asserts the property exists and is non-default) and
`GetStatus_ShimVersionIsStable_AcrossRepeatedCalls`. `HashTableRejectCount` was added to the
exact same `DaemonStatus` record, wired through the exact same `WebApp.Create` call sites, but
did not receive the analogous coverage.

Practical consequence if left unaddressed: if `hashTableRejectCountProvider` were ever wired
incorrectly (wrong delegate, dropped on a refactor of one of the three response sites, or the
WS handshake's snapshot silently reverted to the `?? 0` default), no test in the suite would
fail. The field would quietly stay `0` or vanish from the JSON while the full Ft8/Daemon/Web
suites (280/193/203 at time of review) stayed green.

QA verified the wiring is in fact currently correct by reading `WebApp.cs` and
`WebSocketHub.cs` directly — this is not a live bug, it's an uncovered regression surface for a
feature the Captain explicitly asked to be included.

---

## 2. Branch

Continue on `feat/f-005-hash-table-saturation-diagnostic`. This is a same-PR addition, not a
separate follow-up branch — F-005 has not merged yet.

---

## 3. Actions

No product code changes are required — `DaemonStatus.cs`, `WebApp.cs`, and `WebSocketHub.cs`
are already correctly wired (QA confirmed this by reading the diff and current source). This
task is test-only.

### 3.1 — `tests/OpenWSFZ.Web.Tests/StatusAndBindingTests.cs` — HTTP status coverage

Add tests immediately after `GetStatus_ShimVersionIsStable_AcrossRepeatedCalls` (line 87),
mirroring its structure:

1. **`GetStatus_IncludesHashTableRejectCountField`** — `GET /api/v1/status`, assert
   `TryGetProperty("hashTableRejectCount", ...)` is `true`. Unlike `shimVersion` (which must be
   `> 0` once the native shim loads), a fresh test-host process legitimately has never
   saturated its hash table, so assert `GetInt32().Should().BeGreaterThanOrEqualTo(0)` rather
   than requiring non-zero — the point of this test is that the field is *present and readable*,
   not that it has a particular value.
2. **`GetStatus_HashTableRejectCountIsLive_UnlikeShimVersion`** (optional but recommended,
   since D2's design note explicitly distinguishes this field from `shimVersion` on exactly this
   point) — if the test host exposes any way to force a rejection (e.g. reusing
   `HashedCallsignResolutionTests`' saturation helper, or a lighter-weight test-only hook), call
   `GET /api/v1/status` twice with a forced increment in between and assert the second read is
   `>=` the first. If wiring a real saturation scenario into `WebTestFactory` is impractical,
   it's acceptable to skip this one and note why in the PR — the presence test (3.1.1) is the
   one that must not be skipped.

### 3.2 — `POST /api/v1/decode/start` and `POST /api/v1/decode/stop` — same field, same response shape

Add (or extend an existing decode-control test file if one already POSTs to these endpoints and
inspects the JSON body):

3. **`decode/start`, `decode/stop` responses each include `hashTableRejectCount`** — same
   presence assertion as 3.1.1, applied to both endpoints' response bodies. These are separate
   `DaemonStatus` construction sites in `WebApp.cs` (not shared code with the `/status` GET), so
   a bug in either one specifically would not be caught by 3.1 alone.

### 3.3 — WebSocket `status` event coverage

Find (or add to, if one exists) the WS-focused test file under `tests/OpenWSFZ.Web.Tests/` that
opens a socket against the test factory and inspects the initial `status` message payload (check
for an existing `WsMessage`/`status`-type test first — several already exist for other
daemon-status-visibility fields per that capability's spec). Add:

4. **WS initial `status` event includes `hashTableRejectCount`** — connect, read the first
   `status` message, deserialize its `Payload`, assert the field is present. This is the one
   surface with *no* existing sibling-field precedent to copy from (the `shimVersion` tests are
   HTTP-only), so use whatever pattern the existing WS tests in this assembly already establish
   for reading the first message off the socket.

---

## 4. Acceptance Criteria

- [x] **AC-1:** `GetStatus_IncludesHashTableRejectCountField` passes — `GET /api/v1/status`
  response JSON has a `hashTableRejectCount` property. Added to `StatusAndBindingTests.cs`,
  immediately after the `shimVersion` tests; asserts presence and `>= 0`.
- [x] **AC-2:** `POST /api/v1/decode/start` and `POST /api/v1/decode/stop` responses both
  include `hashTableRejectCount`. Added `PostDecodeStartAndStop_ResponsesIncludeHashTableRejectCount`
  to `DecodeControlEndpointTests.cs`, asserting both (separate construction sites) independently.
- [x] **AC-3:** The WebSocket initial `status` event's payload includes `hashTableRejectCount`.
  Added `WebSocket_StatusEventCarriesHashTableRejectCountField` to `WebSocketTests.cs`, mirroring
  the existing `audioActive` status-event test.
- [x] **AC-4:** No existing test in `StatusAndBindingTests.cs` or the WS test file regresses.
  Web suite: 206 passed / 0 failed.
- [x] **AC-5:** Full suite still green: `OpenWSFZ.Ft8.Tests` (280), `OpenWSFZ.Daemon.Tests`
  (193), `OpenWSFZ.Web.Tests` (**206** = 203 + 3 new). New tests landed as additions to the Web
  count; nothing replaced.
- [x] **AC-6:** `openspec validate --strict --all` still passes (**47/47**) — this task added no
  new capability or requirement, so no spec changes were needed.

**Implementation note (dev-task §3.1.2, optional liveness test):** deliberately NOT implemented.
Forcing a real hash-table saturation through the web host would require pushing 264+ synthetic
Type 4 PCM decodes through the live decode pipeline, and `WebTestFactory` exposes no lighter
seam to override `hashTableRejectCountProvider`. The counter's increment-on-reject behaviour is
already proven directly against the native shim by
`HashedCallsignResolutionTests.HashTableSaturation_...` (reject-count delta assertion). A comment
recording this rationale sits alongside the new test in `StatusAndBindingTests.cs`.

---

## 5. References

- `openspec/changes/f-005-hash-table-saturation-diagnostic/design.md` — Risk 1 ("the getter is
  added but nothing ever calls it") and D2 (session-end logging vs. the live HTTP/WS
  alternative, explicitly left as optional/stretch for the implementer/Captain to decide).
- `openspec/changes/f-005-hash-table-saturation-diagnostic/tasks.md` §3.2 — the stretch item,
  marked done ("Captain elected to include it"), and §4 (Tests) — note that 4.1–4.4 all target
  the native getter and the session-end log line; none target the HTTP/WS surface added in §3.2.
- `tests/OpenWSFZ.Web.Tests/StatusAndBindingTests.cs` lines 55–87 — the `shimVersion` tests this
  task's new tests should mirror in structure and rigor.
- `src/OpenWSFZ.Web/DaemonStatus.cs`, `src/OpenWSFZ.Web/WebApp.cs`, `src/OpenWSFZ.Web/WebSocketHub.cs`
  — already correctly wired; no changes needed here, only new tests.
- QA review of `feat/f-005-hash-table-saturation-diagnostic`, 2026-07-06 — full review found the
  implementation otherwise sound (native shim, managed interop, session-end logging, and the
  extended saturation test in `HashedCallsignResolutionTests.cs` all independently verified);
  this was the sole finding.
