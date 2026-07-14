# Handoff: D-CALLER-020 — Partner's own re-transmitted CQ is misread as "working another station" and aborts the QSO

**Date:** 2026-07-14
**Prepared by:** QA engineer (analysis of `logs/openswfz-20260714T171230Z.log`, real-hardware field
test of PR #72 by the Captain)
**Status:** Awaiting developer action
**Defect ID:** D-CALLER-020
**Severity:** High — the application abandons an in-progress QSO on its own initiative, after the
operator did everything right, because it cannot distinguish "partner hasn't heard us yet, still
calling CQ" from "partner has genuinely moved on to another station." Pre-existing defect, **not**
introduced by PR #72 (`fix/d-caller-018-abort-hard-stop`) — confirmed present in `main` before that
merge and untouched by its diff.

---

## 1. Context

### 1.1 What the log shows

Real-hardware session, `logs/openswfz-20260714T171230Z.log`. The Captain double-clicked EA1FUB's CQ
row; the engage landed cleanly within the valid window, TX completed normally, one retry fired on
schedule after no reply — all correct so far:

```
19:28:16.448  pending CQ target 'EA1FUB' at 488 Hz — answering at B phase.
19:28:16.459  KeyDown — PTT asserted
19:28:29.262  KeyUp — PTT released; TX complete for "EA1FUB PD2FZ JO33"; state → WaitReport
19:28:45.927  no response from EA1FUB (retry 1/3) — retransmitting.
19:28:45.934  KeyDown — PTT asserted
19:28:58.749  KeyUp — PTT released; TX complete; state → WaitReport
19:29:15.923  QsoAnswererService: EA1FUB is working CQ — aborting.
19:29:15.924  QsoAnswererService: aborted to Idle (was: "WaitReport", partner: EA1FUB).
```

Between the retry completing and the abort, the decoder picked up EA1FUB's own next transmission —
almost certainly `CQ EA1FUB <grid>`, i.e. EA1FUB simply hadn't decoded us yet and was still calling
CQ generally, which after only one retry is entirely unremarkable. The application read this as
"EA1FUB has moved on to work someone/something called 'CQ'" and gave up permanently. The Captain's
own framing of this from the field: *"timing was impeccable, but the application just decided to end
the whole qso."*

### 1.2 Root cause

`QsoAnswererService.cs`, `HandleWaitReportAsync` (currently line 973), lines 1030–1038:

```csharp
// ── Partner is working another station — abort ──
if (fromPartner && !toUs)
{
    _logger.LogInformation(
        "QsoAnswererService: {Partner} is working {OtherDest} — aborting.",
        partner, dest);
    await SafeAbortToIdleAsync(stoppingToken, $"Partner {partner} is working another station").ConfigureAwait(false);
    return;
}
```

`TryParseMessage` (line 1494) splits an FT8 message on whitespace into exactly three tokens —
`dest src payload`. A standard CQ message `"CQ EA1FUB IM58"` parses as `dest="CQ"`, `src="EA1FUB"`,
`payload="IM58"`. `fromPartner` (`src.Equals(partner)`) is true; `toUs` (`dest.Equals(ours)`) is
false — `"CQ" != "PD2FZ"` — so the condition `fromPartner && !toUs` is satisfied and the code treats
a routine, undirected CQ call exactly the same as a directed message to a *different* real callsign
(e.g. `"Q2OTHER EA1FUB +03"`, which genuinely does mean the partner is now working someone else and
is the correct case to abort on).

These are not the same situation:
- **`dest` is a real callsign, not ours** → the partner is demonstrably in QSO with a third station.
  Continuing to wait is pointless. **Correct to abort.**
- **`dest == "CQ"`** → the partner is not in QSO with anyone; they are still calling CQ generally,
  most likely because they have not yet decoded us. This is the normal, expected state of affairs
  early in a retry sequence and is not evidence the partner has "moved on." **Should not abort on
  this alone** — it should be treated the same as "no matching message" (fall through to the
  existing `RetryOrAbortAsync`, which already has its own configurable retry-count/watchdog
  backstop for genuinely giving up).

The identical bug, byte-for-byte, exists in `QsoCallerService.cs`, `HandleWaitRr73Async` (currently
line 770), lines 803–812 — same condition, same log message shape, same fix required. The caller side
is symmetric: after we've sent our report and are waiting for RR73, if the partner re-transmits their
own CQ instead of answering us, the caller side gives up immediately instead of retrying.

### 1.3 Test coverage gap

`QsoAnswererServiceTests.cs:447`, `"6.6: Partner working another station in WaitReport → abort to
Idle"`, only ever exercises the genuine-third-party case:

```csharp
Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
await WaitForStateAsync(_sut!, QsoState.WaitReport);

// Partner sends to a third station.
Send(Make($"Q2OTHER {PartnerCall} +03"));
await WaitForStateAsync(_sut!, QsoState.Idle, timeout: TimeSpan.FromSeconds(3));
```

There is no test anywhere that sends `Make($"CQ {PartnerCall} {PartnerGrid}")` a *second* time while
already in `WaitReport` — the exact case that failed in the field. Same gap in
`QsoCallerServiceTests.cs:695` (`"5.9: HandleWaitRr73Async — partner working another station
aborts"`).

---

## 2. Branch

Suggested name: `fix/d-caller-020-working-cq-false-abort`, off `main` (PR #72 already merged as of
2026-07-14).

---

## 3. Action

**Files:** `src/OpenWSFZ.Daemon/QsoAnswererService.cs` (`HandleWaitReportAsync`, ~line 1030) and
`src/OpenWSFZ.Daemon/QsoCallerService.cs` (`HandleWaitRr73Async`, ~line 804).

Narrow the abort condition so it only fires when `dest` is a real, addressed callsign — not the
literal `"CQ"` token (case-insensitive; also guard against an empty/malformed `dest` from a
line that squeaked past `TryParseMessage`'s 3-token check with garbage). Suggested shape:

```csharp
// ── Partner working another station — abort. Distinguish this from the partner simply
// still calling CQ (dest == "CQ"), which is not evidence they've moved on — see D-CALLER-020. ──
if (fromPartner && !toUs && !dest.Equals("CQ", StringComparison.OrdinalIgnoreCase))
{
    _logger.LogInformation(
        "QsoAnswererService: {Partner} is working {OtherDest} — aborting.",
        partner, dest);
    await SafeAbortToIdleAsync(stoppingToken, $"Partner {partner} is working another station").ConfigureAwait(false);
    return;
}
```

When `dest == "CQ"`, fall through — do **not** `return` early, do **not** treat it as a matching
decode either (it isn't a report or RR73/RRR from the partner to us). It should reach the same
"no matching message — retry or abort" path at the bottom of the handler as a genuinely silent
cycle, so the existing `RetryOrAbortAsync` retry-count/watchdog backstop is what eventually gives up
if the partner truly never answers — not a same-cycle snap decision based on one CQ decode.

Apply the identical change to `QsoCallerService.cs`'s `HandleWaitRr73Async`.

**Do not** touch the genuine-third-party path — `Q2OTHER {PartnerCall} +03` must continue to abort
immediately exactly as today; that is correct behaviour and is already covered by
`6.6`/`5.9`.

---

## 4. Acceptance criteria

**AC-1.** `QsoAnswererService`, `WaitReport`: partner re-transmitting their own CQ
(`"CQ {PartnerCall} {PartnerGrid}"`) while we are in `WaitReport` does **not** abort the QSO; it is
treated as a silent cycle and falls into the existing retry/watchdog path. Add as a new unit test
alongside `6.6` — e.g. `WaitReport_PartnerStillCallingCq_DoesNotAbort_RetriesInstead`.

**AC-2.** `QsoAnswererService`, `WaitReport`: partner addressing a genuine third callsign
(`"Q2OTHER {PartnerCall} +03"`) still aborts immediately — existing `6.6` test must continue to pass
unmodified.

**AC-3 / AC-4.** Same pair (still-CQ → no abort, retry instead; genuine third party → abort) for
`QsoCallerService`'s `HandleWaitRr73Async`, alongside existing `5.9`.

**AC-5.** Full retry-exhaustion path still works: if the partner keeps calling CQ (or stays silent)
for `tx.RetryCount` consecutive cycles with no report/RR73 ever addressed to us, the QSO still ends
via `RetryOrAbortAsync`'s existing "retry count exceeded" abort — this defect must not turn into an
infinite-retry regression. Confirm `WaitReport_NoResponse_RetriesThenAborts` (line 460) and its
caller-side equivalent still pass unmodified.

**AC-6.** `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings.

**AC-7.** Full test suite green, no regressions (baseline: full suite as of `main` post-PR#72).

---

## 5. Live verification requirement

This defect was only caught by real-hardware field testing, not by unit tests — the existing `6.6`/
`5.9` tests all passed while this was broken, because neither ever sent the partner's own CQ a second
time. Per this project's standing convention for QSO-flow defects (see the D-CALLER-018 dev-task,
§5), unit tests alone are not sufficient sign-off here. Before merge, either:
- reproduce the exact field sequence (engage → retry → partner's own CQ decoded again) against a
  real isolated daemon over its real HTTP/WebSocket API and confirm no premature abort, or
- at minimum, replay the relevant excerpt of `logs/openswfz-20260714T171230Z.log` (lines
  ~2895–3047, EA1FUB) through a synthetic-decode harness and confirm the fixed code no longer emits
  `"is working CQ — aborting"` for that sequence.

---

## 6. References

- Evidence log: `logs/openswfz-20260714T171230Z.log`, lines 2896–3047 (EA1FUB sequence).
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs`:
  - `HandleWaitReportAsync` — line 973; fix target at lines 1030–1038.
  - `TryParseMessage` — line 1494 (confirms `dest="CQ"` parsing for a `CQ CALL GRID` message).
  - `RetryOrAbortAsync` — line 1149 (existing genuine-timeout backstop, unaffected).
- `src/OpenWSFZ.Daemon/QsoCallerService.cs`:
  - `HandleWaitRr73Async` — line 770; fix target at lines 803–812.
  - `TryParseMessage` — line 1162 (same parsing logic, separate copy).
- `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`:
  - `6.6: Partner working another station in WaitReport → abort to Idle` — line 447/448 (must keep
    passing unmodified; genuine-third-party case).
  - `6.6: No matching decode in WaitReport → retry; after max retries → Idle` — line 459/460 (must
    keep passing unmodified; retry-exhaustion backstop).
- `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs`:
  - `5.9: HandleWaitRr73Async — partner working another station aborts` — line 695 (must keep
    passing unmodified).
- Related but distinct: `dev-tasks/2026-07-14-engage-window-wsjtx-redesign.md` — the other finding
  from the same field session (late-start-threshold model), tracked separately; not the same root
  cause and does not depend on this fix or vice versa.
- PR #72 QA sign-off comment (this session) — full mapping of all three field complaints to root
  causes, of which this is one.
