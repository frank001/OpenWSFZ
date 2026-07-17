## Why

`QsoCallerService` parses the partner's Maidenhead grid out of every CQ-answer message it
receives (`TryParseResponder`), but throws the parsed value away instead of surfacing it —
`_partnerGrid` is never set on the caller-initiated path, so the final `QsoRecord.PartnerGrid`
is hardcoded to `null`. As a result, `ADIF.log`'s `GRIDSQUARE` field is silently omitted for
every QSO driven by `QsoCallerService`, even when the partner's grid was visible in the decode
that triggered the match. This is a defect against already-committed spec text — the
`qso-caller` spec's "TxRr73" requirement already says the ADIF record must include "partner
callsign, grid" — not new scope. Found 2026-07-12 by QA against two real, completed,
ADIF-logged QSOs (see `dev-tasks/2026-07-12-adif-partner-grid-not-captured.md` for full
evidence and root-cause analysis).

## What Changes

- `QsoCallerService.TryParseResponder` gains a new `out string? grid` parameter, set to the
  third token when it was already validated as a grid (no new parsing logic — the value is
  already computed and currently discarded).
- The `CallerPartnerSelectMode.First` auto-engage path captures the new `grid` out-param and
  threads it through to `ExecuteTxReportAsync`.
- The `None`-mode manual/external-select path (`SelectResponderAsync`) re-derives the grid from
  the stored `_recentResponderDecodes` entry's raw message and stores it in a new
  `_pendingResponderGrid` field, threaded the same way as the existing
  `_pendingResponderCallsign`/`_pendingResponderFrequencyHz` fields (including the test-only
  `TestSetPendingResponder` helper).
- `ExecuteTxReportAsync` gains a `string? partnerGrid` parameter and sets `_partnerGrid`
  alongside the existing `_partner` assignment.
- The final `QsoRecord` construction sets `PartnerGrid = _partnerGrid` instead of a hardcoded
  `null`, and the now-inaccurate "caller does not capture partner's grid" comment is removed.
- **Explicitly out of scope:** `QsoAnswererService.ExecuteJumpInAsync` (the mid-exchange
  jump-in path) is untouched. Its `_partnerGrid = null` is correct as-is — the grid genuinely
  never appears in the FT8 protocol once we've missed the original CQ — and is not the same
  defect.
- No public API, wire format, or ADIF field-table change. `AdifLogWriter` already correctly
  omits `GRIDSQUARE` when `PartnerGrid` is null/empty and includes it otherwise
  (`AdifLogWriter.cs:135-137`, unchanged).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `qso-caller`: adds an explicit "Partner grid capture for ADIF logging" requirement with
  scenarios for the `First`-mode, `None`-mode manual-select, and no-grid-sent cases. This makes
  testable and explicit a guarantee that was previously only implied parenthetically inside the
  `TxRr73` requirement ("same fields as `QsoAnswererService`: partner callsign, grid, ...") —
  it does not change what `TxRr73` or `adif-log`'s field table already say, it closes an
  ambiguity gap so the behavior is spec-verifiable per select-mode.

## Impact

- **Code:** `src/OpenWSFZ.Daemon/QsoCallerService.cs` only
  (`TryParseResponder`, `SelectResponderAsync`, `TestSetPendingResponder`,
  `ExecuteTxReportAsync`, the final `QsoRecord` construction, and the two call sites at
  `:666-680` and `:695`).
- **Tests:** `QsoCallerServiceTests.cs` (new grid-capture cases for both the `First`-mode and
  `None`-mode paths, plus a no-grid/signal-report-only regression case).
  `QsoAnswererServiceTests.cs` and `AdifLogWriterTests.cs` are expected to pass unmodified.
- **No API/schema/spec-text changes.** `openspec validate --strict --all` pass count is
  expected to be unchanged.
