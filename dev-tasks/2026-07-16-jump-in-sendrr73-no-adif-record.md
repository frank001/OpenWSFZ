# DEV TASK — Mid-exchange jump-in (`EngagePoint.SendRr73`) never writes an ADIF record, even for a genuinely completed QSO

**Date:** 2026-07-16
**OpenSpec change:** none open. Touches `QsoAnswererService` (`specs/qso-answerer`), `IQsoController`/
`EngagePoint` (`specs/qso-controller` — verify capability ownership), and the
`POST /api/v1/tx/engage-decode` endpoint in `WebApp.cs` (`specs/web-server`). This is a defect/gap
against an already-merged, already-archived feature (`D-CALLER-012`, GitHub context: dev-task
`dev-tasks/2026-06-27-d-caller-012-dblclick-engage.md`), not new scope — treat as a standalone
bugfix change, or fold into whichever change next touches the jump-in path.
**Branch:** none yet — not started.
**Status:** New. Found by QA while diagnosing why the Captain's real QSO with G7LHK (2026-07-16,
~21:20–21:23 local) never appeared in `ADIF.log`. Confirmed with the Captain that the exchange was
genuinely completed and should have been logged.
**Found by:** QA, reading `logs/openswfz-20260716T190223Z.log` end-to-end and cross-referencing
against `QsoAnswererService.cs`/`QsoCallerService.cs`/`WebApp.cs` source.
**Severity:** **Moderate.** Not merge-blocking for anything else, but it silently drops real,
completed QSOs from the log with no warning to the operator — the daemon returns `200 OK` from
`engage-decode` and transmits RR73 as if everything is normal; nothing tells the Captain the contact
won't be logged.

---

## Two things were investigated tonight; only one is an actual defect

QA's first pass suspected two problems. On inspection, only the first is real — the second turned
out to be correct, deliberate, already-tested behaviour, and is documented below **for the record
only, no code change requested.**

---

## Finding A (real defect) — `EngagePoint.SendRr73` jump-in skips ADIF entirely

### Evidence — tonight's G7LHK QSO

```
21:15:56  QsoControllerRouter: active role switched to Caller.
21:20:15  QsoCallerService TryParseResponder: msg='PD2FZ G7LHK IO92' → match=true
21:20:15  QsoCallerService: G7LHK answered our CQ at 1500 Hz — sending report.
21:20:15  QsoCallerService: TX → "G7LHK PD2FZ +00" at 1500 Hz.
21:20:28  QsoCallerService: watchdog reset for 1 minutes.        (armed to expire 21:21:28)
21:20:45  QsoCallerService: no response from G7LHK (retry 1/3) — retransmitting report.
21:21:15  QsoCallerService: no response from G7LHK (retry 2/3) — retransmitting report.
21:21:28  QsoCallerService: TX session cancelled during TX (state: "TxReport").   <- watchdog fires
21:21:28  QsoCallerService: aborted to Idle (was: "TxReport", partner: G7LHK).
21:21:28  QsoControllerRouter: caller QSO ended — reverting active role to "Answerer".
...
21:22:48  POST /api/v1/tx/engage-decode  (Captain double-clicked G7LHK's reply in the decode panel)
21:22:48  QsoAnswererService: jump-in to "SendRr73" with partner G7LHK at 1500 Hz.
21:22:48  QsoAnswererService: TX → "G7LHK PD2FZ RR73" at 1500 Hz.
21:23:00  QsoAnswererService: TX complete for "G7LHK PD2FZ RR73".
21:23:00  QsoAnswererService: aborted to Idle (was: "Tx73", partner: G7LHK).
21:23:15  (Captain re-engaged once more — G7LHK apparently repeated, same jump-in, same TX, same result)
```

G7LHK's reply arrived ~80 seconds after the original report — just outside the caller-side watchdog
window (see Finding B for why that expiry is correct behaviour, not the bug). The Captain manually
recovered the QSO by double-clicking the decode row, which fired `POST /api/v1/tx/engage-decode` →
`EngagePoint.SendRr73` → `QsoAnswererService.ExecuteJumpInAsync`. The Captain has confirmed this was
a genuine, successfully completed QSO. It was never written to `ADIF.log`.

### Root cause

`QsoAnswererService.ExecuteJumpInAsync`, `EngagePoint.SendRr73` case:

```csharp
// QsoAnswererService.cs:942-951
case EngagePoint.SendRr73:
{
    // They sent RRR or R±NN → we reply RR73 → QsoComplete (no ADIF — partial QSO).
    var msg = $"{partner} {tx.Callsign} RR73";
    _lastTxMessage = msg;
    SetStateAndNotify(QsoState.Tx73);    // nearest proxy; UI shows as final TX
    await TransmitAsync(msg, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
    await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
    break;
}
```

Compare `EngagePoint.Send73` two cases below it (`QsoAnswererService.cs:953-957`), which correctly
calls `ExecuteTx73Async` — the same method the normal (non-jump-in) completion path uses, which
builds a `QsoRecord` and writes it via `_adifLog.AppendQsoAsync` (`QsoAnswererService.cs:1094-1133`).
`SendRr73` has no equivalent — it transmits and aborts, full stop.

This was a **known, deliberate Phase-1 tradeoff** when `D-CALLER-012` shipped
(`dev-tasks/2026-06-27-d-caller-012-dblclick-engage.md` §5 "Known limitations" and AC-4: *"No ADIF
write (partial QSO — expected)."*) — not an oversight. It was accepted at the time because the
jump-in was conceived as a recovery mechanism for exchanges the daemon "didn't start cleanly." What
that framing didn't anticipate is tonight's case: the exchange *was* started cleanly by this same
daemon (`QsoCallerService` sent the CQ, got the answer, sent the report) and was only interrupted by
the caller-side watchdog — the jump-in is completing a QSO of the daemon's own making, not rescuing
a stranger's mid-exchange decode. Treating every `SendRr73` jump-in as inherently "partial" is too
broad; it conflates "we don't have a grid square" (genuinely true, see the aside below) with "this
isn't a real QSO" (not true).

### Secondary data-quality bug in the same path

`ExecuteJumpInAsync` unconditionally hardcodes the received report:

```csharp
// QsoAnswererService.cs:891
_rstRcvd      = "+00";
```

...regardless of what the partner's decoded message actually said. Tonight's Captain-confirmed
payload was a bare `RRR` (no numeric report at all) — `+00` would have been fabricated data even if
ADIF *had* been written. `HandleWaitRr73Async`'s normal (non-jump-in) path already knows how to
derive the correct value from the decoded payload (`QsoCallerService.cs:830-832`: strip a leading
`R` if present, else use the payload as-is) — the jump-in path should do the same, using the actual
message text from the `engage-decode` request rather than a placeholder.

### Aside — `PartnerGrid = null` is correct and NOT part of this fix

`ExecuteJumpInAsync` also sets `_partnerGrid = null` (`QsoAnswererService.cs:889`) because a
mid-exchange jump-in, by construction, never saw the original CQ (the only FT8 message type that
carries a grid square). This is genuinely unrecoverable, already correctly documented, and is the
exact same situation as `dev-tasks/2026-07-12-adif-partner-grid-not-captured.md` Part 2. **Do not
attempt to fix this as part of this task** — there is nothing to recover.

### Recommended fix

1. **Write ADIF for `SendRr73`, mirroring `ExecuteTx73Async`'s pattern**
   (`QsoAnswererService.cs:942-951` → model on `:1079-1137`):
   - Build a `QsoRecord` with `PartnerCallsign = partner`, `PartnerGrid = null` (see aside above),
     `RstSent = "+00"`, `RstRcvd = _rstRcvd` (see point 2 below), `QsoStartUtc = _qsoStartUtc`,
     `QsoEndUtc = Ft8TimeHelper.DeriveFt8CycleStartUtc(DateTime.UtcNow)`,
     `OperatorCallsign = tx.Callsign`, `OperatorGrid = tx.Grid`,
     `DialFrequencyMHz = WebApp.ResolveEffectiveFrequency(_catState, _configStore.Current)`.
   - Respect the same `tx.QsoConfirmation` gate `ExecuteTx73Async` uses: if enabled, publish via
     `_txEventBus.PublishQsoReview(...)` and let the browser call `POST /api/v1/tx/log-qso`; if
     disabled, call `_adifLog.AppendQsoAsync(record)` directly. Do **not** do both (double-entry
     prevention, `qso-log-dialog` D3 — same rule `ExecuteTx73Async` already follows).
   - Move the `SetStateAndNotify(QsoState.QsoComplete)` / "QSO with {Partner} complete!" log line in
     ahead of `SafeAbortToIdleAsync`, matching `ExecuteTx73Async`'s ordering.

2. **Thread the actual decoded payload through so `RstRcvd` is real, not a placeholder:**
   - `POST /api/v1/tx/engage-decode` (`WebApp.cs:1415-1420`) already has the exact payload text in
     its local `info` variable at the point it dispatches to `EngagePoint.SendRr73` — it is simply
     not passed anywhere. Add a parameter (e.g. `string rawPayload`) to
     `IQsoController.EngageAtAsync` and thread it through: `WebApp.cs` call site → `EngageAtAsync`
     signature (`IQsoController.cs`) → `QsoControllerRouter.EngageAtAsync` (pass-through) →
     `QsoAnswererService.EngageAtAsync` → the jump-in state fields → `ExecuteJumpInAsync`.
   - In `ExecuteJumpInAsync`, replace the hardcoded `_rstRcvd = "+00";` with logic mirroring
     `QsoCallerService.cs:830-832`: if the payload starts with `R` followed by a signal report,
     strip the leading `R`; otherwise (bare `RRR`) keep it as-is. This makes tonight's actual case
     (`RRR`) log as `RST_RCVD=RRR` rather than a fabricated `+00`.
   - `QsoCallerService.EngageAtAsync` remains a no-op stub (`QsoCallerService.cs:395-401`) — it takes
     the new parameter for signature parity only, matching the existing stub pattern.

3. Consider (optional, Captain's call, not required for this fix): a short code comment or
   `openspec/specs/qso-answerer/spec.md` addition documenting this requirement explicitly — the
   spec is currently silent on the jump-in ADIF behaviour altogether (checked: no mention of
   `EngagePoint`, `jump-in` + ADIF, or `D-CALLER-012` anywhere in `specs/qso-answerer/spec.md`).
   Whoever picks this up should add a `### Requirement:` block with a scenario covering "jump-in to
   SendRr73 writes an ADIF record" so this doesn't regress silently a second time.

### Tests required

- `QsoAnswererServiceTests.cs`: new test asserting that after `EngageAtAsync(partner, freqHz,
  cycleStart, EngagePoint.SendRr73, rawPayload, ct)` fires its jump-in TX, `IAdifLogWriter
  .AppendQsoAsync` is called exactly once with a `QsoRecord` matching `PartnerCallsign`, and
  `RstRcvd` equal to the (normalized) `rawPayload` — cover both a bare `"RRR"` payload and a
  numeric `"R-05"` payload (asserting `RstRcvd == "-05"` for the latter).
- A companion test confirming `PartnerGrid` is still correctly `null` on this path (guards against
  someone "fixing" the aside above by mistake later).
- A `tx.QsoConfirmation = true` variant asserting `PublishQsoReview` fires instead of a direct
  `AppendQsoAsync` call, matching `ExecuteTx73Async`'s existing coverage for that gate.
- `EngageDecodeEndpointTests.cs` (`tests/OpenWSFZ.Web.Tests/`): confirm the `RRR`/`R±NN` dispatch
  branch (`WebApp.cs:1415-1420`) now forwards the matched payload text into `EngageAtAsync`.
- Re-run existing jump-in coverage (`QsoAnswererServiceTests.cs` D-CALLER-018/021 lines ~2558-2857)
  unmodified — this fix only changes what happens *after* the TX completes, not the phase-arming/
  expiry logic those tests cover.

### Verification

1. `dotnet build` / `dotnet test` — expect unchanged pass counts plus the new ADIF-on-jump-in tests,
   all green.
2. `openspec validate --strict --all` — expect unchanged pass count unless the optional spec
   addition (point 3 above) is taken, in which case expect it to still pass.
3. Manual/hardware (recommended, given this was found via a real QSO): recreate the shape of
   tonight's incident — let a caller-side session's retry/watchdog cycle expire mid-QSO, then
   double-click the partner's subsequent RRR/R±NN reply in the decode panel — and confirm
   `ADIF.log` gains a well-formed record with a real (non-placeholder) `RST_RCVD`.

---

## Finding B (investigated, **not a defect** — no code change requested)

QA's first read of tonight's log suspected the watchdog was wrongly cutting the G7LHK caller session
short before its configured 3 retries could run (watchdog reset once at `QsoCallerService.cs:802`,
armed for `WatchdogMinutes` = 1 minute per the Captain's current settings; three retries at the FT8
15 s cadence take noticeably longer than 60 s in practice, exactly as observed tonight at 21:21:28).

This turned out to be **exactly the fixed, intentionally-tested behaviour from D-008**
(`openspec/changes/archive/2026-06-15-ft8-qso-answerer-v1/dev-briefing-d007-d008.md`, GitHub #19):
before D-008, the watchdog was reset on every retry and could therefore never fire while retries
kept occurring. D-008's fix was specifically to make the watchdog run independently of the retry
counter — see the explicit guard comment at `QsoAnswererService.cs:1171-1173` ("D-008: watchdog is
NOT reset here — retries are not state transitions") and the regression test
`QsoAnswererServiceTests.cs:980` (`"D-008: Watchdog fires before retry count is exhausted when
partner goes silent"`), which asserts this exact interaction as correct. `QsoCallerService`'s
`WaitRr73` retry path (`QsoCallerService.cs:949-957`) mirrors the same design deliberately (comment:
"same as answerer").

**Reopening this would regress an already-fixed, already-tested defect. No change is recommended.**

The only real takeaway is a configuration one: with `RetryCount = 3` and the FT8 report/retry
cadence, `WatchdogMinutes` needs to be comfortably above ~90 seconds for the full retry budget to
ever run to completion; at `WatchdogMinutes = 1`, the watchdog will usually win the race. This is
worth mentioning to the Captain as a settings note, not a bug — optionally, a future low-priority
enhancement could add a soft warning in the Settings UI when `WatchdogMinutes` is configured too low
relative to `RetryCount`, but that is a nice-to-have, not part of this task.

---

## Note on tonight's specific G7LHK contact

The Captain has decided not to hand-patch `ADIF.log` for this one contact — this task is scoped to
the code fix only, so this class of QSO is logged correctly going forward. No data-recovery action
is included here.

---

## References

- `src/OpenWSFZ.Daemon/QsoAnswererService.cs:866-960` (`ExecuteJumpInAsync`, all three
  `EngagePoint` cases), `:889-892` (hardcoded `_partnerGrid = null` / `_rstRcvd = "+00"`),
  `:1079-1137` (`ExecuteTx73Async` — the pattern to mirror), `:1141-1175` (`RetryOrAbortAsync` —
  D-008 guard comment).
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:802` (single `ResetWatchdog` call on entering
  `WaitRr73`), `:918-965` (`RetryOrAbortAsync`, both `WaitAnswer`/`WaitRr73` branches),
  `:830-832` (`IsRogerReport` payload normalization — the pattern Finding A point 2 should reuse),
  `:1189-1203` (`StartWatchdog`/`ResetWatchdog`).
- `src/OpenWSFZ.Web/WebApp.cs:1362-1420` (`engage-decode` endpoint message parsing/dispatch —
  `info` variable holds the exact payload text that Finding A point 2 needs threaded through).
- `dev-tasks/2026-06-27-d-caller-012-dblclick-engage.md` — original `D-CALLER-012` handoff; §5
  "Known limitations" and AC-4 explicitly accepted the no-ADIF behaviour this task now revisits.
- `dev-tasks/2026-07-12-adif-partner-grid-not-captured.md` — Part 2 covers the same
  `_partnerGrid = null` gap this task's "Aside" explicitly leaves untouched.
- `openspec/changes/archive/2026-06-15-ft8-qso-answerer-v1/dev-briefing-d007-d008.md` — D-008
  origin (GitHub #19), for Finding B context.
- `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:978-1030` — existing D-008 regression
  test; re-run unmodified, do not touch.
- `logs/openswfz-20260716T190223Z.log` — tonight's incident log (lines ~2753-4021 cover the whole
  Caller→Answerer role-switch sequence and both G7LHK sessions).
