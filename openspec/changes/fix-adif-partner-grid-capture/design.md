## Context

`QsoCallerService` and `QsoAnswererService` are the two state-machine services that drive an
FT8 QSO end to end and both eventually build a `QsoRecord` that `AdifLogWriter` serialises to
`ADIF.log`. `QsoAnswererService.ExecuteTxAnswerAsync` already captures `_partnerGrid` correctly
from the CQ it answered (`QsoAnswererService.cs:789-793`). `QsoCallerService` has the mirror-image
opportunity — the grid is present in the CQ-answer message it receives and is already parsed by
`TryParseResponder` as part of validating the match — but the parsed value is discarded rather
than surfaced, so `QsoCallerService`'s `_partnerGrid` field is never set and the final
`QsoRecord.PartnerGrid` is hardcoded to `null` (`QsoCallerService.cs:833`).

There are two independent call sites that consume a successful `TryParseResponder` match:
- `CallerPartnerSelectMode.First` — auto-engages the first valid responder immediately
  (`QsoCallerService.cs:666-680`).
- `CallerPartnerSelectMode.None` — records candidates into `_recentResponderDecodes` for later
  manual/external selection via `SelectResponderAsync` (`QsoCallerService.cs:274-306`), which
  does not re-parse the original message for a grid at all today.

Both must be fixed for the defect to be closed; fixing only `First`-mode would leave the
manual-select path silently still broken.

## Goals / Non-Goals

**Goals:**
- Thread the already-parsed partner grid from `TryParseResponder` through both consuming call
  sites into `ExecuteTxReportAsync` and the final `QsoRecord.PartnerGrid`.
- Preserve existing behavior exactly when no grid was sent (bare signal-report answer) —
  `PartnerGrid` must remain `null` in that case, not a fabricated value.
- Keep the change confined to `QsoCallerService.cs`; no change to `AdifLogWriter`'s
  already-correct conditional `GRIDSQUARE` emission, and no change to the `qso-caller`/`adif-log`
  spec text (the requirement already says the ADIF record includes "partner callsign, grid" —
  this closes an implementation gap against it, not a new requirement).

**Non-Goals:**
- `QsoAnswererService.ExecuteJumpInAsync` (mid-exchange jump-in) is explicitly **not** touched.
  Once we join an in-progress exchange without having decoded the original CQ, no subsequent FT8
  message type (report/RR73/73) carries a grid square — there is nothing to recover. Its existing
  `_partnerGrid = null` and accompanying comment are correct and stay as-is.
- No change to the wire protocol, message parsing grammar, or any other field capture.

## Decisions

1. **Extend `TryParseResponder`'s signature with a new `out string? grid` parameter** rather than
   returning a tuple/record or adding a second method. Matches the existing pattern of the method
   (`out partner`, `out freqHz`) and requires no new parsing — `isGrid`/`thirdToken` are already
   computed at the point of decision (`QsoCallerService.cs:1213-1219`); the fix is `grid = isGrid
   ? thirdToken : null;` immediately after. The one call site that doesn't care about the grid
   (the `None`-mode auto-track loop, `:695`) passes `out _`, consistent with how it already
   ignores `freqHz` details it doesn't need.

2. **`None`-mode path re-runs the grid check against the stored raw decode rather than caching
   the grid at first-sight time.** `SelectResponderAsync` already looks up
   `_recentResponderDecodes.TryGetValue(callsign, out var recentDecode)` and has the raw
   `recentDecode.Message` available. Re-deriving the grid from that message at selection time
   (via `TryParseResponder` itself, or a small shared token-3-is-a-grid helper to avoid
   re-validating the callsign match) avoids adding a second cache dictionary keyed in parallel
   with `_recentResponderDecodes` and keeps a single source of truth for "is token 3 a grid."
   The recovered value is stored in a new `_pendingResponderGrid` field, set alongside the
   existing `_pendingResponderCallsign`/`_pendingResponderFrequencyHz`/`_pendingResponderIsAPhase`
   fields — including in the test-only `TestSetPendingResponder` helper, so test setup doesn't
   drift from the real path.

3. **`ExecuteTxReportAsync` takes the grid as a new parameter and assigns `_partnerGrid` inline**,
   mirroring exactly how `_partner` is already assigned in the same method — no new state-machine
   phase, no new branching, just one more field carried alongside the partner callsign that's
   already being threaded through the same call chain.

4. **Delta spec adds a new, narrowly-scoped `qso-caller` requirement rather than editing
   `TxRr73` or `adif-log`'s field table.** Both of those existing requirements already describe
   the correct, intended behavior (`adif-log`'s field table already says `GRIDSQUARE` is
   "omitted if null/empty"; `qso-caller`'s `TxRr73` already says the ADIF record includes
   "partner callsign, grid"). Editing either would misrepresent this change as altering
   established behavior. Instead, `specs/qso-caller/spec.md` (this change) ADDs a new
   "Partner grid capture for ADIF logging" requirement with explicit per-select-mode scenarios —
   this closes an ambiguity gap (the previous text never spelled out the `First`-mode vs.
   `None`-mode vs. no-grid-sent cases individually) without rewriting or contradicting existing
   requirement text.

## Risks / Trade-offs

- **[Risk] Fixing only one of the two call sites** (e.g. `First`-mode but not `None`-mode)
  → **Mitigation:** tasks.md requires an explicit test for both paths; the dev-task doc
  (`dev-tasks/2026-07-12-adif-partner-grid-not-captured.md`) already flags the `None`-mode path
  as "most likely to be missed."
- **[Risk] Accidentally touching `QsoAnswererService.ExecuteJumpInAsync`** while working nearby
  in a similarly-named file → **Mitigation:** tasks.md includes an explicit "re-run
  `QsoAnswererServiceTests.cs` unmodified, no assertion changes" verification step to catch any
  accidental regression there.
- **[Trade-off] Re-parsing the message in `SelectResponderAsync` instead of caching the grid at
  first-sight** costs a small amount of redundant string work on the (rare, user-driven) manual
  QSO-selection path, in exchange for not introducing a second parallel cache structure. Judged
  worth it given `None`-mode selection happens at most once per QSO, not per decode cycle.

## Migration Plan

No migration needed — this is a pure bugfix with no data model, schema, or config change.
Existing `ADIF.log` records already written without `GRIDSQUARE` are historical and are not
backfilled; only QSOs completed after this fix ships will include the field. No feature flag;
ships as soon as merged.

## Open Questions

None — root cause, fix plan, and test plan were already fully worked out in
`dev-tasks/2026-07-12-adif-partner-grid-not-captured.md` prior to this proposal.
