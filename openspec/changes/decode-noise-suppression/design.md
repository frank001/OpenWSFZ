## Context

Decodes are produced once per cycle by `Ft8Decoder.DecodeAsync` (`src/OpenWSFZ.Ft8/Ft8Decoder.cs`),
which already resolves `Region` (via `ICallsignRegionStore.TryGetRegion`, including the dedicated
`Synthetic` flag for Q-prefix R&R traffic) and `WorkedBefore` onto each `DecodeResult` before
returning. The daemon's decode-pump loop (`src/OpenWSFZ.Daemon/Program.cs`, inside the
`framerOutput.Reader.ReadAllAsync` loop, roughly lines 545–554) then fans the same `results` list
out four ways in sequence:

1. `decodeEventBus.Publish(results)` — WebSocket broadcast to the live decode panel (fire-and-forget).
2. `allTxtWriter.AppendAsync(cycleStart, dialFreq, results)` — the `ALL.TXT` ground-truth log.
3. `qsoAnswererChannel.Writer.TryWrite(batch)` — feeds `QsoAnswererService`.
4. `qsoCallerChannel.Writer.TryWrite(batch)` — feeds `QsoCallerService`.

There is no separate server-side "recent decodes" REST endpoint the frontend replays on connect —
the decode panel is populated purely from the live WebSocket stream, so gating step (1) fully
covers "hidden from the decode panel."

`WorkedBeforeIndex.Register` (the only *write* path into the worked-before index) is called from
`AdifLogWriter` only when a QSO is actually logged (`src/OpenWSFZ.Daemon/AdifLogWriter.cs:93`) —
i.e. only as a result of a completed automation-driven or manual QSO. It is not written per-decode.
Consequently, gating (3) and (4) (QSO-controller eligibility) is sufficient by itself to satisfy
the proposal's "excluded from `WorkedBeforeIndex` updates" requirement — a decode that never
reaches `QsoAnswererService`/`QsoCallerService` can never result in a logged QSO, hence never
registers into the index. No separate `WorkedBeforeIndex` change is needed.

## Goals / Non-Goals

**Goals:**
- Suppress (a) decodes with unresolved (`null`) region and (b) decodes flagged `Region.Synthetic`,
  from the decode panel and from QSO-controller eligibility, per two independent, persisted,
  operator-controlled settings on the Region data settings page.
- Never disable/grey out the Unknown-suppression control; only its computed default depends on
  region-data presence, and only until the operator makes an explicit choice.
- Leave `ALL.TXT` completely unaffected — it continues to record every decode exactly as today.

**Non-Goals:**
- No change to `DecodeFilterState`/`DecodeFilterEvaluator` (the existing ephemeral, per-session
  column filter) or its API. This is a separate, persisted, upstream gate.
- No change to `WorkedBeforeIndex`'s write path, read path, or the `region-lookup` resolution logic
  itself — this change only consumes the `Region`/`Region.Synthetic` values already produced.
- No UI affordance to reset an explicit operator choice back to "auto" once made — out of scope for
  this change; the operator can always flip the checkbox manually to the value they want.
- No change to manual (operator-initiated, non-automation) QSO engagement — suppressed decodes are
  simply never visible to click in the first place, so this falls out for free rather than needing
  separate handling.

## Decisions

### Decision 1: Single filtering gate inserted once, upstream of the three consumers that must not see suppressed decodes

Compute a filtered view of `results` exactly once per decode cycle, immediately after
`ft8Decoder.DecodeAsync` returns and before any fan-out:

```csharp
var results = await ft8Decoder.DecodeAsync(pcmWindow, cycleStart, currentBand);
var visibleResults = DecodeNoiseSuppressionFilter.Apply(results, configStore.Current.DecodeNoiseSuppression, regionStore);
_ = decodeEventBus.Publish(visibleResults);
await allTxtWriter.AppendAsync(cycleStart, dialFreq, results); // unfiltered — ALL.TXT unaffected
var batch = new DecodeBatch(new DateTimeOffset(cycleStart, TimeSpan.Zero), visibleResults);
qsoAnswererChannel.Writer.TryWrite(batch);
qsoCallerChannel.Writer.TryWrite(batch);
```

`DecodeNoiseSuppressionFilter` is a small, pure, independently-unit-testable static class/method in
`OpenWSFZ.Daemon` (alongside `WorkedBeforeIndex.cs`/similar daemon-local helpers) — not a new
service, no DI lifecycle concerns. It takes the raw `results`, the persisted
`DecodeNoiseSuppressionConfig`, and `ICallsignRegionStore` (needed only to resolve the Unknown
setting's live default when the persisted value is unset — see Decision 3), and returns the subset
that should be visible/engageable.

**Alternatives considered:**
- *Fold into `DecodeFilterEvaluator`/`DecodeFilterState` as new axes.* Rejected: that state is
  explicitly ephemeral and resets on daemon restart (per `decode-panel-filtering` capability); these
  new settings must persist across restarts like any other operator preference, and mixing a
  persisted concern into an intentionally-ephemeral one would muddy both contracts.
- *Filter independently inside `QsoAnswererService`/`QsoCallerService` and inside the WebSocket
  broadcast path separately.* Rejected: duplicates the predicate in three places (panel, answerer,
  caller) with a real risk of the three drifting out of sync over time. A single upstream gate
  guarantees "hidden from panel" and "ineligible for automation" are always the same decode set by
  construction, satisfying the "treated as if it never arrived" framing from the proposal.

### Decision 2: `Region.Synthetic` flag reused directly — no new callsign-pattern detection

`RegionInfo.Synthetic` (`src/OpenWSFZ.Abstractions/CallsignRegionEntry.cs`) already distinguishes
R&R-synthetic Q-prefix decodes from both real entities and genuine `Unknown` misses (per the
existing `region-lookup` capability, requirement "Synthetic Q-prefix callsigns resolve to a
distinct synthetic region"). The suppression predicate reads this flag; it does not re-derive
synthetic-ness from the callsign string. This avoids a second, potentially-diverging definition of
"synthetic" living in two capabilities.

### Decision 3: Nullable persisted value for the Unknown-suppression setting; `Synthetic`-suppression is a plain non-nullable boolean

`DecodeNoiseSuppressionConfig` (new section of the existing `IConfigStore`/`JsonConfigStore`-backed
config, alongside `Decoder`, `DecodeLog`, etc.):

```csharp
public sealed record DecodeNoiseSuppressionConfig(
    bool? SuppressUnknownRegion = null,   // null = operator has never explicitly chosen
    bool  SuppressSynthetic     = true);  // plain default-on, no gating condition
```

- `SuppressUnknownRegion == null` ("operator hasn't decided yet") resolves at evaluation time to
  `regionStore.EntryCount > 0` (reusing whatever count already backs the existing
  `GET /api/v1/region-data/status` view from the `region-lookup-data-refresh` capability — no new
  counting logic). This means: before any region-data refresh, Unknown decodes are never suppressed
  (avoids the "new operator sees zero decodes and assumes the app is broken" failure mode); once
  data is present, they start being suppressed automatically, without the operator having touched
  anything.
- The moment the operator explicitly checks or unchecks the settings-page control, the persisted
  value becomes `true` or `false` (never `null` again), and that explicit choice is authoritative
  from then on regardless of subsequent region-data-refresh activity — the control is never
  overwritten out from under the operator.
- `SuppressSynthetic` needs no such nullable/live-default dance — it has no data-availability
  precondition, so a plain default-`true` boolean is sufficient, and the settings-page checkbox
  simply reflects and edits it directly.
- The settings-page checkbox for Unknown-suppression is **always enabled/interactive** in both
  states (no region data / region data present) — clicking it while no region data is loaded is
  perfectly legal and simply sets an explicit `true`/`false` that will apply the moment data
  eventually arrives, or immediately if some decodes already resolved before data existed (edge
  case, harmless).

### Decision 4: Frontend surface

Two new checkboxes added to the Region data settings tab (`web/settings.html`, wired in
`web/js/settings.js` next to the existing status/refresh and lookup fieldsets), persisted through
the existing settings-save round-trip (same `JsonConfigStore`-backed pattern, same serialized
`SaveAsync` used elsewhere on this tab per commit `640bc86`/`640bc89`). The Unknown checkbox's
displayed state reflects the live-resolved effective value (including the auto-computed default
when the persisted value is `null`), not merely the raw persisted field, so the operator always
sees what's actually happening rather than a stale "unset" indicator.

## Risks / Trade-offs

- **[Risk]** The `region-lookup` capability's existing invariant is "a lookup miss ... SHALL still
  reach `ALL.TXT` and the UI" — this change deliberately punches a operator-opt-in hole in the "and
  the UI" half for the Unknown case. → **Mitigation:** this is a new, separate, explicitly
  operator-controlled capability layered on top, not a silent change to `region-lookup`'s own
  behavior (which is unmodified and remains true by default until the operator opts in); call this
  out in code comments at the filter site and in this design doc so a future reader of the
  `region-lookup` spec doesn't conclude it's been silently violated.
- **[Risk]** Auto-flipping the Unknown default from "not suppressed" to "suppressed" the instant a
  region-data refresh completes (while the persisted value is still `null`) could surprise an
  operator who refreshes data mid-session and suddenly sees fewer decodes with no settings-page
  visit in between. → **Mitigation:** acceptable per explicit product-owner instruction; the
  settings-page display of the live-resolved value (Decision 4) makes the state discoverable, and
  the operator can immediately override with an explicit choice if undesired.
- **[Risk]** Decode counts shown in the panel will now sometimes be lower than what's in `ALL.TXT`
  for the same cycle, which could read as a discrepancy/bug to an operator inspecting both. →
  **Mitigation:** none beyond documentation; flagging as a known, intentional trade-off for review.
- **[Risk]** This change touches the `QsoAnswererService`/`QsoCallerService` input path (the batch
  each channel receives), which per standing project policy requires re-running
  `qa/decode-filter-synth-verify/live_verify_9_axes.py` (real isolated daemon, real virtual-audio-
  cable injection, real native decoder, real API) before merge, in addition to unit/integration
  coverage. → **Mitigation:** called out explicitly as a required task in `tasks.md`.

## Migration Plan

- New config section defaults cleanly for existing installs (`SuppressUnknownRegion: null`,
  `SuppressSynthetic: true`) via the existing `JsonConfigStore` first-run/missing-key conventions —
  no migration script needed; an existing `config.json` without this section simply gets the
  default record on next load/save.
- No daemon restart required beyond the normal settings-save path already used by this tab.
- Rollback: revert the change; the new config section is additive and ignored by older code if a
  rollback ever needed to read a config file saved by the new version.

## Open Questions

- None blocking. If implementation surfaces a genuine requirement-level change needed in
  `decode-panel-filtering`, `qso-answerer`, `qso-caller`, or `decode-log`, add the corresponding
  delta spec before `tasks.md` is finalised (per the proposal's Modified Capabilities note).
