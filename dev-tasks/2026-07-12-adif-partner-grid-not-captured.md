# DEV TASK — `QsoCallerService` discards the partner's grid even when it is present in the CQ-answer message, so `ADIF.log`'s `GRIDSQUARE` field is silently omitted

**Date:** 2026-07-12
**OpenSpec change:** none open. Governed by the existing `specs/adif-log/spec.md` (Requirement:
"ADIF record field content" — `GRIDSQUARE` is listed as a mandatory-when-known field) and touches
`QsoCallerService`, which is documented under `specs/qso-caller`. This is a defect against an
already-merged, already-archived capability, not new scope — treat it as a standalone bugfix change
(or fold into whichever change next touches `QsoCallerService`, at the Captain's discretion).
**Branch:** none yet — not started.
**Status:** New. Found by QA while authoring the `cat-tx-ptt` hardware-acceptance write-up, cross-
checking two real, completed, ADIF-logged QSOs against `specs/adif-log/spec.md`'s field table.
**Found by:** QA, comparing real `ADIF.log` records against decoded FT8 exchanges in `ALL.TXT`.
**Severity:** **Minor — not merge-blocking for anything, but a real, fixable defect.** `GRIDSQUARE`
is cosmetic/enrichment data, not required for a QSO to be valid or confirmable (LoTW/QRZ/Clublog all
accept ADIF records without it), and both gaps described below predate `cat-tx-ptt` entirely — they
are not a regression from any recent change. Fix at normal priority, not urgently.

---

## Evidence

Two real QSOs completed 2026-07-12 (see `openspec/changes/cat-tx-ptt/hardware-acceptance.md`
§16.1–16.3 for the full, NFR-021-redacted evidence record). Both wrote a well-formed `ADIF.log`
record — but neither includes a `GRIDSQUARE` tag, even though the partner's grid was visible in the
decoded exchange for both:

**QSO 2** (driven entirely by `QsoCallerService` — a CQ we sent, answered, worked to completion):
```
ALL.TXT:  ...     7.074 Rx FT8      ...  PD2FZ [PARTNER] IO92        <- partner's grid, decoded
ADIF.log: <CALL:5>[PARTNER]<RST_SENT:3>+00<RST_RCVD:3>-04<QSO_DATE:8>20260712<TIME_ON:6>164345
          <QSO_DATE_OFF:8>20260712<TIME_OFF:6>164515<OPERATOR:5>PD2FZ<MY_GRIDSQUARE:4>JO33
          <MODE:3>FT8<FREQ:5>7.074<BAND:3>40m<COMMENT:14>OpenWSFZ v0.35<EOR>
```
No `GRIDSQUARE` tag anywhere in the record, despite `IO92` being right there in the decode that
`QsoCallerService` itself parsed to recognise the partner had answered our CQ. (Real callsign
withheld per NFR-021 — see local `ADIF.log`/`ALL.TXT`, `TIME_ON` 164345Z, for the unredacted record.)

**QSO 1** (completed via `QsoAnswererService`'s mid-exchange jump-in path — a separate, structurally
different gap, see "Root cause" part 2 below) also lacks `GRIDSQUARE`, for a different reason.

## Root cause

Two independent gaps, in two different services, both resulting in the same missing field.

### Part 1 — `QsoCallerService`: the grid is parsed and then thrown away (fixable)

`QsoCallerService.TryParseResponder` (`QsoCallerService.cs:1187-1228`) parses every candidate
CQ-answer message of the form `{ourCallsign} {theirCallsign} {theirGrid|signalReport}` and already
determines, token by token, whether the third token is a Maidenhead grid or a signal report:

```csharp
// QsoCallerService.cs:1213-1219
var thirdToken = parts[2];
var isGrid   = thirdToken.Length >= 2
               && char.IsLetter(thirdToken[0])
               && char.IsLetter(thirdToken[1]);
var isReport = IsSignalReport(thirdToken);
if (!isGrid && !isReport)
    return false;

partner = parts[1];
// isGrid is computed right here — and then discarded. thirdToken itself is never
// returned to the caller in any form.
```

`isGrid`/`thirdToken` are computed, used only to validate the match, and then dropped — the method's
only two `out` parameters are `partner` and `freqHz`. Every call site that consumes a successful
match (`QsoCallerService.cs:666` — `CallerPartnerSelectMode.First` auto-engage path — and the
`None`-mode manual/external-select path via `SelectResponderAsync`, `QsoCallerService.cs:274-306`,
which separately re-derives responder/frequency from `_recentResponderDecodes` without ever
re-parsing the grid either) therefore has no way to learn the grid even when it was present in the
very message that triggered the match.

`ExecuteTxReportAsync` (`QsoCallerService.cs:713-766`) — the method both call sites above eventually
call — never sets `_partnerGrid` at all; `QsoCallerService`'s `_partnerGrid` field simply stays
`null` for the entire session (compare `QsoAnswererService.ExecuteTxAnswerAsync`, `:789-793`, which
correctly captures `_partnerGrid = partnerGrid` from its own equivalent CQ-decode parse). This is
confirmed by the explicit, honest comment already in the code at the point the final `QsoRecord` is
built:

```csharp
// QsoCallerService.cs:833
PartnerGrid      = null,        // caller does not capture partner's grid in WaitRr73
```

This is fixable: the grid is sitting right there in the decoded text at the moment of the match, in
both the `First`-mode and `None`-mode paths. It just needs to be threaded through instead of thrown
away.

### Part 2 — `QsoAnswererService`'s mid-exchange jump-in path: the grid is genuinely never seen (not fixable, document only)

`QsoAnswererService.ExecuteJumpInAsync` (`QsoAnswererService.cs:856-` ff.) handles joining an
already-in-progress exchange we did not initiate — the daemon never decoded the original CQ (which
is the only FT8 message type that carries a grid). By the time we jump in, only report/RR73/73
messages are being exchanged, and **none of those FT8 message types carry a grid square** — it is
not in the protocol at that point. This is already honestly documented in the code:

```csharp
// QsoAnswererService.cs:872
_partnerGrid  = null;        // not available in mid-exchange jump-in
```

**This part is not a bug and there is no code fix for it** — the information genuinely does not
exist anywhere the daemon can observe it. Documenting it here only so it isn't rediscovered and
mistaken for the same defect as Part 1.

## Recommended fix (Part 1 only)

1. Extend `TryParseResponder`'s signature to surface the grid it already computes:
   ```csharp
   internal static bool TryParseResponder(
       string msg, string ourCallsign, out string partner, out double freqHz,
       out string? grid, ILogger? logger = null)
   ```
   Set `grid = isGrid ? thirdToken : null;` right where `isGrid` is already computed
   (`QsoCallerService.cs:1213-1219`) — no new parsing logic needed, just don't discard the value
   already in hand. Update the existing two call sites that don't care about grid
   (`QsoCallerService.cs:695`, the `None`-mode auto-track loop that only records into
   `_recentResponderDecodes`) to `out _` for the new parameter, same pattern already used there for
   `freqHz`.

2. `CallerPartnerSelectMode.First` path (`QsoCallerService.cs:666-680`): capture the new `grid`
   out-param and pass it through to `ExecuteTxReportAsync`.

3. `None`-mode manual/external-select path: `SelectResponderAsync` (`QsoCallerService.cs:274-306`)
   already looks up `_recentResponderDecodes.TryGetValue(callsign, out var recentDecode)` — the raw
   decoded message is available there (`recentDecode.Message`). Re-run `TryParseResponder` (or a
   small shared token-3-is-a-grid helper, to avoid re-validating the callsign match) against it to
   recover the grid, and store it in a new `_pendingResponderGrid` field alongside the existing
   `_pendingResponderCallsign`/`_pendingResponderFrequencyHz`/`_pendingResponderIsAPhase` (set at
   both `QsoCallerService.cs:295-298` and the test-only `TestSetPendingResponder`,
   `QsoCallerService.cs:377-387` — update both so test setup stays consistent with the real path).
   Thread `_pendingResponderGrid` into the pending-responder-fire call to `ExecuteTxReportAsync`
   (`QsoCallerService.cs:649`).

4. `ExecuteTxReportAsync` (`QsoCallerService.cs:713-717`): add a `string? partnerGrid` parameter, set
   `_partnerGrid = partnerGrid;` alongside the existing `_partner = partner;` assignment.

5. `QsoCallerService.cs:833`: change `PartnerGrid = null, // caller does not capture partner's grid
   in WaitRr73` to `PartnerGrid = _partnerGrid,` — and delete the now-inaccurate comment (or replace
   it with a note that grid is only ever known when the responder's *first* message to us included
   one; a bare-report answer with no grid still correctly yields `null` here, which is entirely
   normal FT8 behaviour, not a gap).

Do **not** attempt to fix Part 2 (`QsoAnswererService`'s jump-in path) — there is nothing to recover
there; see Root cause Part 2 above. Leave its `_partnerGrid = null` and comment exactly as they are.

## Tests required

- `QsoCallerServiceTests.cs`: `TryParseResponder` unit-level (or via the public behaviour it drives)
  case confirming a CQ-answer message containing a grid (e.g. `Q1OFZ Q2NOISE IO91`) results in the
  final `QsoRecord.PartnerGrid` being populated with that grid once the QSO completes, for the
  `CallerPartnerSelectMode.First` path.
- A second case for the `None`-mode manual-select path (`SelectResponderAsync` /
  `TestSetPendingResponder`) proving the same grid capture works there too — this is the path most
  likely to be missed if only the `First`-mode path is fixed, since it's a separate call site with
  its own field-threading.
- A case confirming a CQ-answer message that skips the grid and goes straight to a signal report
  (e.g. `Q1OFZ Q2NOISE -05` — valid FT8 behaviour per the existing doc comment on
  `TryParseResponder`) still correctly yields `PartnerGrid = null` — i.e. the fix must not invent a
  grid where none was sent.
- Re-run `QsoAnswererServiceTests.cs`'s existing jump-in coverage unmodified — Part 2 is explicitly
  out of scope; no assertion there should change.
- `AdifLogWriterTests.cs`: no change expected — `AdifLogWriter.BuildAdifRecord` already correctly
  omits `GRIDSQUARE` when `PartnerGrid` is null/empty and includes it otherwise; this fix only
  affects what `QsoCallerService` supplies, not how the writer formats it.

## Verification

1. `dotnet build` / `dotnet test` — expect unchanged pass counts plus the new grid-capture tests, all
   green.
2. `openspec validate --strict --all` — expect unchanged pass count (no spec text is changing; this
   closes a gap against the existing `adif-log` spec's field table rather than altering it).
3. Manual/hardware (optional but recommended given this was found via real QSOs): complete one more
   real QSO where the partner answers our CQ with a grid included (the common case), and confirm
   `ADIF.log`'s new record includes a populated `GRIDSQUARE` tag matching the grid visible in
   `ALL.TXT`.

## References

- `src/OpenWSFZ.Daemon/QsoCallerService.cs:1187-1228` (`TryParseResponder` — discards the grid it
  already parses), `:666-680` (`First`-mode call site), `:274-306` (`SelectResponderAsync`,
  `None`-mode manual/external-select), `:713-766` (`ExecuteTxReportAsync` — never sets
  `_partnerGrid`), `:833` (`PartnerGrid = null` in the final `QsoRecord`).
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs:789-793` (`ExecuteTxAnswerAsync` — the already-correct
  equivalent, for comparison), `:856-` ff. and `:872` (`ExecuteJumpInAsync` — Part 2, not fixable,
  document only).
- `openspec/specs/adif-log/spec.md:51-70` (Requirement: ADIF record field content — lists
  `GRIDSQUARE` as populated "when known").
- `openspec/changes/cat-tx-ptt/hardware-acceptance.md` §16.2 — where this gap was first surfaced,
  against real hardware evidence, and explicitly scoped out of that change.
- `src/OpenWSFZ.Daemon/AdifLogWriter.cs:135-137` — already correctly conditional on `PartnerGrid`;
  no change needed here.
