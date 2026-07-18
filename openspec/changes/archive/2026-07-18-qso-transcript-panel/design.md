## Context

Today the TX panel has two pieces of state display and no history of the conversation itself:

1. **`#tx-msg-1/2/3`** (`renderMessageRows` in `web/js/main.js`) — three rows that always show
   the *template* for the current exchange step (`{partner} {callsign} {grid|R+00|73}` for the
   answerer role, `CQ {callsign} {grid}` / `{partner} {callsign} +00` / `{partner} {callsign}
   RR73` for the caller role), re-rendered in place on every `txState` event. They never
   accumulate — the text for Tx 1 today is overwritten by tomorrow's Tx 1.
2. **`#tx-abort-log-section`** (titled "TX History") — a capped, newest-on-top list of abort
   *reasons* only (`FR-UX-002`, 2026-06-24), populated by `appendTxAbortLog`. It has no message
   content and was never given a formal spec requirement in `openspec/specs/web-frontend/spec.md`
   (confirmed by inspection — this change is the first time TX History gets one).

The only place a partner's actual decoded reply appears is `#decodes-table`, populated by
`handleDecodes` from the raw `decode` WebSocket event. `decode-panel-filtering`'s
`isDecodeVisible` (and, upstream of it, `decode-noise-suppression`) can legitimately hide a row
from that table — that's their job. The side effect is that the operator's own live QSO can
scroll out of view mid-exchange, with nothing else in the UI recording what was actually said.

## Goals / Non-Goals

**Goals:**
- Give the operator a single, always-visible, unfiltered record of their own QSO traffic: what
  was actually transmitted and what was actually received, in the order it happened.
- Make it survive partner switches within a session (rolling log, not per-QSO reset).
- Reuse the existing "TX History" DOM slot and its abort-reason content rather than adding a
  second competing list.
- Keep this frontend-only — no WebSocket wire-format or backend change, since every message this
  section needs already reaches the browser today.

**Non-Goals:**
- Per-message-type colorization (CQ vs. report vs. RR73 vs. 73) — direction-only for now
  (Captain's explicit decision); can be layered on later without restructuring the data model.
- Persisting the transcript across a page reload or app restart — it is session/in-memory state,
  exactly like the existing `txAbortLog` array it replaces.
- Any change to `decode-panel-filtering`'s or `decode-noise-suppression`'s own behavior — this
  change only adds a second, independent *consumer* of the pre-filter decode stream. Both
  existing capabilities continue to gate `#decodes-table` and QSO-engagement exactly as today.

## Decisions

### Decision 1 — Source of truth: two existing WebSocket events, no new backend event

Both inputs the transcript needs are already delivered to the browser:
- **Sent messages**: derivable inside `renderMessageRows`, which already computes the exact text
  for the active row from `partner`/`txCallsign`/`txGrid`/`role`.
- **Received messages**: the raw `results` array `handleDecodes` receives, *before*
  `isDecodeVisible`/noise-suppression gating is applied to the DOM row.

No new WebSocket frame, REST endpoint, or C# model change is needed. Considered adding a
backend-side "QSO transcript" event that pre-pairs sent/received messages server-side — rejected
as unnecessary complexity; the frontend already has everything and pairing by callsign token is
cheap and matches the existing `tokenMatchesCallsign` idiom used for `decode-partner` highlighting.

### Decision 2 — Sent-message capture: log on state-transition-into-active, not on every render

`renderMessageRows` is called on every `txState` WebSocket push, including repeated pushes while
the state hasn't materially changed (e.g. a duplicate status broadcast). Logging "sent" on every
call would produce duplicate transcript entries for a message transmitted exactly once.

**Decision**: track `previousTxState` at module scope (alongside the existing `currentTxState`).
Append a "sent" transcript entry only when the *new* state differs from the previous state AND
the new state is one of the role's active states (`TxAnswer`/`TxReport`/`Tx73` for answerer,
`TxCq`/`TxReport`/`TxRr73` for caller — same `activeStates` arrays `renderMessageRows` already
builds). This fires exactly once per actual transmission step, including retries (a retried
`TxReport` after a `WaitRr73` timeout re-enters `TxReport` from a different previous state and is
correctly logged again — each retry is a real re-transmission and the operator should see it).

The one exception: a caller's initial `CQ {callsign} {grid}` (Tx 1, state `TxCq`) has no partner
yet. It is still logged, with the entry rendered partner-less (e.g. `CQ …` with no partner-change
separator triggered), until a partner subsequently engages and `currentTxPartner` becomes non-null.

### Decision 3 — Received-message capture and matching rule

A decode belongs to the tracked conversation when its space-delimited tokens include either
`txCallsign` (the operator's own callsign) or `currentTxPartner` (the active partner) — precisely
the same matching idiom `handleDecodes` already uses for `tokenMatchesCallsign` when deciding
whether to apply the `decode-partner` highlight class. This is at least as strict as that existing
highlight (in fact identical), so nothing that would fail to highlight today would incorrectly
appear in the transcript, and vice versa — the two mechanisms stay conceptually aligned even
though they serve different DOM elements.

The check runs on the raw `results` array inside `handleDecodes`, ahead of (and independent of)
the `tr.hidden = !isDecodeVisible(...)` line — so a decode hidden from `#decodes-table` by the
column filter still reaches the transcript.

**Idle-state decodes**: when `currentTxPartner` is `null` and the operator is not mid-QSO, a
decode matching only `txCallsign` (e.g. someone unexpectedly calling with our callsign in the
message, or residual traffic from a just-completed QSO) still qualifies — this is intentionally
permissive rather than silently dropping traffic that does reference the operator, consistent
with "never hide the operator's own conversation."

### Decision 4 — Unified list: fold abort reasons in as a distinct entry kind

`appendTxAbortLog` is renamed/absorbed into a single `appendTranscriptEntry(kind, ...)` function
with `kind` one of `'sent' | 'received' | 'abort'`. All three kinds share one backing array,
one newest-on-top render, and one cap. This lets an abort show inline exactly where it happened
in the conversation (e.g. after `Tx 2` sent, before a `Tx 3` that never came) rather than in an
entirely separate list the operator has to cross-reference by timestamp.

### Decision 5 — Rolling log, partner-change separator, cap

- Backing array: unbounded conceptually, capped at **`TRANSCRIPT_LOG_MAX = 100` entries**
  (raised from the prior `TX_ABORT_LOG_MAX = 10`, since a single QSO alone can now produce 3–6
  entries plus an abort; 100 keeps roughly the last 15–30 QSOs visible without unbounded DOM
  growth over a long session).
- A partner-change separator entry (kind `'partner-change'`, not colorized, e.g. `— now working
  Q2XYZ —`) is appended whenever `currentTxPartner` changes to a new non-null value from a
  different previous value. It counts toward the same cap.
- Newest-on-top, matching the existing `txAbortLog` convention (already confirmed with the
  Captain) — this keeps the most recent activity visible without scrolling, at the cost of the
  in-progress exchange reading bottom-to-top rather than top-to-bottom; this trade-off was
  explicitly accepted when the placement/scope questions were put to the Captain.

### Decision 6 — Direction colorization

Two CSS classes on each `<li>`: `.transcript-sent` and `.transcript-received` (abort/
partner-change entries get a third, neutral `.transcript-event` class, unstyled by direction).
Exact colors are a CSS/design decision left to implementation — reuse existing `--color-*` custom
properties in `app.css` where a suitable one already exists (e.g. an accent color already used
for `tx-msg-active`) rather than inventing new raw hex values, per this project's established
preference for tokenized colors (see the standing TODO about the `#803030` armed-button color
that was *not* tokenized — do not repeat that shortcut here).

### Decision 7 — Testability: extract a DOM-free module, mirroring `decodeFilter.js`

The matching/aggregation logic (message-belongs-to-conversation check, active-state-transition
detection, entry-kind construction, cap enforcement) is extracted into a new DOM-free module,
`web/js/qsoTranscript.js`, exporting pure functions (e.g. `shouldCaptureDecode(decode, txCallsign,
currentPartner)`, `buildTranscriptEntry(...)`, `pushEntry(log, entry, maxLen)`), following the
exact precedent `web/js/decodeFilter.js` + `decodeFilter.test.js` already set: no `document`/
`window` references, exercised directly via `node --test web/js/qsoTranscript.test.js` (already
wired into CI at `.github/workflows/ci.yml` line 280's `node --test web/js/*.test.js` glob — no
CI change needed, the new `*.test.js` file is picked up automatically). `web/js/main.js` imports
from it and handles only DOM rendering, exactly as it already does for `isDecodeVisible`.

**On Gate G3 traceability**: G3 (`tools/pre_merge_check.py` → `tools/TraceabilityCheck`) scans
compiled C# `*.Tests.dll` assemblies for `DisplayName`s carrying an `"FR-###: "` prefix — it does
not, and structurally cannot, inspect `node --test` JS test names. Checked against precedent:
`FR-040`, `FR-041`, and `FR-044` (all frontend-only requirements) have **zero** matches anywhere
in `tests/` for their FR ids, and CI has never flagged this. **Conclusion: FR-062 will not be
picked up by G3 either, consistent with every prior frontend-only FR** — this is a pre-existing,
accepted gap in the traceability tooling (out of scope to fix here), not a defect specific to this
change. The JS unit tests in `qsoTranscript.test.js` are still required, for ordinary regression
safety, independent of whether G3 can see them.

## Risks / Trade-offs

- **[Risk] Matching by callsign token can mis-attribute traffic** if a third station's message
  happens to contain both the operator's callsign and the tracked partner's callsign as
  substrings of an unrelated exchange (rare, but FT8 message tokens are short and collisions are
  not impossible with certain callsign/suffix combinations). → **Mitigation**: identical
  acceptance-risk profile to the pre-existing `decode-partner` highlight, which uses the same
  matcher today; not a new class of risk introduced by this change.
- **[Risk] Unbounded growth within a very long unattended session** even with a 100-entry cap —
  a long multi-hour run produces many partner-change separators and abort entries alongside
  sent/received pairs, and the cap alone doesn't guarantee "last N complete QSOs" semantics (a
  QSO with many retries could push an older *complete* QSO out before a newer, still-incomplete
  one). → **Mitigation**: accepted for this iteration; flagged explicitly rather than silently
  ignored. A future iteration could cap by "last N complete QSOs" instead of raw entry count if
  this proves annoying in practice.
- **[Trade-off] Newest-on-top reads against natural chat-log direction** for a live in-progress
  exchange (see Decision 5) — accepted consciously to stay consistent with the existing TX
  History convention, per the Captain's own confirmed preference.

## Migration Plan

1. Ship `web/js/qsoTranscript.js` + tests (additive, no behavior change yet).
2. Rename `appendTxAbortLog` → `appendTranscriptEntry` in `main.js`; update the single existing
   call site (the `txState` handler's abort-reason branch) to pass `kind: 'abort'`.
3. Add the two new capture hooks (sent-message on state-transition-into-active; received-message
   inside `handleDecodes`, pre-filter).
4. Replace the `#tx-abort-log-section` markup in `web/index.html` with the renamed/expanded
   section (new title "QSO Transcript", same `hidden`-until-first-entry behavior).
5. Add `.transcript-sent`/`.transcript-received`/`.transcript-event` CSS.
6. No rollback complexity beyond a normal revert — no data migration, no persisted state, no API
   version to roll back.

## Open Questions

None outstanding — the three scope questions (rolling-log vs. per-QSO, placement, colorization)
were settled directly with the Captain before this design was written, and the remaining
technical unknowns raised during exploration (Idle-state decode handling, matching strictness,
cap sizing, backend involvement) are resolved above as Decisions 3, 3, 5, and 1 respectively.
