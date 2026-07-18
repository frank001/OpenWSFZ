## Why

Once an operator deselects even one value on any of the four decode-filter attribute
allow-list axes (DXCC entity, Continent, CQ Zone, ITU Zone), the frontend collapses that axis
from "no restriction" (`null`) to a concrete array built only from attribute values *already
seen this session*. Any attribute value that has never appeared before — including a
genuinely brand-new DXCC entity, continent, CQ zone, or ITU zone the operator never had the
chance to see, let alone tick or untick — is absent from that array and is therefore treated
as excluded: hidden from `#decodes-table`, and silently skipped by `QsoAnswererService`/
`QsoCallerService`'s auto-answer/auto-call engagement decision, which reads the same
`DecodeFilterState`. New contacts are disabled by default the moment any one filter option on
that axis is deselected — the opposite of the intended behaviour ("only what I've explicitly
excluded should be hidden"), and a real operational risk for a DX-hunting tool that otherwise
exists specifically to surface new entities/zones as they appear.

## What Changes

- Auto-admission moves to the **daemon**, not the browser. A freshly-decoded attribute value
  (DXCC entity, Continent, CQ Zone, or ITU Zone) that has never been observed this session SHALL
  be auto-admitted into that axis's allow-list the moment the daemon itself processes the
  decode — regardless of whether any browser tab is open. This is necessary because the daemon
  can run fully headless (`daemon-background-mode`, `--background`/`--background-worker`); a
  frontend-only fix would leave the original bug completely unaddressed for any unattended run,
  which defeats the purpose of treating this as an automation-safety fix in the first place.
- `IDecodeFilterStore` (or a small collaborator alongside it) SHALL track, server-side, which
  attribute values have been seen this session per axis — mirroring what `web/js/main.js`'s
  `seenEntities`/`seenContinents`/`seenCqZones`/`seenItuZones` already do client-side today, but
  authoritative and independent of any connected browser. When a decode carries a value not yet
  in that axis's seen-set **and** that axis is currently narrowed (non-null allow-list), the
  daemon SHALL add the value to the allow-list, update `IDecodeFilterStore`, and broadcast the
  change via the existing `decodeFilterChanged` WebSocket event — the same mechanism an
  operator-driven `POST /api/v1/decode-filter` already triggers, so every connected client's
  popup/table and both QSO controller services observe the identical, single authoritative
  state. Only values the operator has explicitly unchecked SHALL remain excluded; a value never
  yet offered SHALL pass by default, exactly as if the axis were untouched.
- `web/js/main.js`'s own `seenEntities`/etc. client-side tracking becomes redundant for the
  purposes of gating admission (the daemon is now authoritative) but may remain for populating
  the popup's checkbox candidate list, since `decodeFilterChanged` keeps every tab's
  `currentDecodeFilter` in sync regardless.
- `DecodeFilterState`'s wire shape and `DecodeFilterEvaluator.IsVisible`/`isDecodeVisible`'s
  predicate logic are **unchanged** — this remains a nullable, per-axis allow-list
  (`null` = unrestricted); the fix is in what array gets constructed and who maintains it, not
  in how it is evaluated. (Captain-decided: deny-list wire semantics considered and explicitly
  rejected.)
- The worked-before tri-state axes (Ctc/DXCC/Cnt/CQz/ITz — `Never`/`DifferentBand`/`ThisBand`)
  are confirmed **unaffected**: their checkbox options are a fixed, always-fully-shown 3-value
  enum, not a dynamically-discovered "seen this session" set, so they cannot exhibit this
  snapshot problem. No behavioural change needed there; this proposal documents that
  confirmation rather than re-fixing something already correct.
- Per standing policy, `qa/decode-filter-synth-verify/live_verify_9_axes.py` SHALL be re-run
  before merge — this change touches `DecodeFilterState`/`IDecodeFilterStore` directly and
  alters engagement-gating behaviour for both `QsoAnswererService` and `QsoCallerService`.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `decode-panel-filtering`: adds a new requirement — the daemon SHALL auto-admit a
  previously-unseen attribute value into a *narrowed-but-non-empty* allow-list axis at decode
  time, so it passes by default until the operator explicitly excludes it, instead of being
  permanently absent from a frozen snapshot. Authoritative in the daemon (not the browser), so it
  applies identically whether or not a browser tab is attached, including headless
  (`--background`) operation. The existing "an axis explicitly driven to fully empty (`[]`)
  filters everything, including future new values" behavior is unchanged and explicitly
  preserved — auto-admission only applies to a narrowed-but-not-fully-empty axis.

No delta needed for `web-frontend`, `qso-answerer`, or `qso-caller`: the frontend already
re-evaluates and re-renders on any `decodeFilterChanged` event regardless of what triggered it
(existing requirement), and both QSO controller services already read whatever
`IDecodeFilterStore.Current` currently holds at their existing engagement-decision point — neither
needs new requirement text for this fix.

## Impact

- `src/OpenWSFZ.Abstractions/IDecodeFilterStore.cs` (or a small new collaborator alongside the
  existing `DecodeFilterStore`) — server-side per-axis "seen this session" tracking and the
  auto-admission decision.
- `src/OpenWSFZ.Daemon/Program.cs` or wherever decodes are fanned out — the auto-admission check
  needs to run once per newly-arrived `DecodeResult`, before/alongside the existing
  `QsoAnswererService`/`QsoCallerService`/WebSocket dispatch, so automation for that same decode
  cycle benefits immediately rather than one cycle later.
- `src/OpenWSFZ.Web/WebSocketHub.cs` / wherever `decodeFilterChanged` is currently only emitted
  from the `POST /api/v1/decode-filter` handler — needs to also fire from the new daemon-side
  auto-admission path.
- `web/js/main.js` — `seenEntities`/etc. client-side tracking may be simplified or left as
  popup-candidate bookkeeping only, since the daemon is now authoritative; no client-side
  admission logic is added.
- `DecodeFilterState.cs` / `DecodeFilterEvaluator.cs` — wire shape and predicate **unchanged**;
  included here only because the standing live-verification policy applies to any change
  affecting this filtering hook's real-world behaviour.
- `qa/decode-filter-synth-verify/live_verify_9_axes.py` — re-run before merge (standing policy),
  and its scenarios should be checked for coverage of the new auto-admission path specifically.
