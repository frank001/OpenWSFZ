## Context

`web/js/main.js:727`–`764` currently arms TX on a single `click` of a CQ decode-table row,
implementing the ratified TX-D01 requirement in `web-frontend/spec.md` exactly as written. The
code already carries an in-flight guard (`inFlight` boolean, `tr.style.pointerEvents = 'none'`,
and a 400 ms post-success cooldown citing decision **D-TX-UI-005**) whose stated purpose is to
*suppress* a human double-click from firing the POST twice — i.e. the existing design already
anticipated operators double-clicking and treated the second click as noise to swallow, not as
signal.

The Captain reports this single-click trigger is too easy to hit by accident during normal decode
table interaction (scrolling, reading, scanning for callsigns) and wants the trigger changed to a
genuine double-click, so a stray single click no longer arms live TX.

## Goals / Non-Goals

**Goals:**
- Require a double-click (not a single click) to call `POST /api/v1/tx/answer-cq` and arm TX from
  a CQ decode-table row.
- A single click on a CQ row does nothing — no request, no state change.
- Preserve every other part of TX-D01: callsign extraction, frequency/cycle-start derivation, the
  `answer-cq` payload shape, and 200/409/error handling are unchanged.
- Preserve the row's existing hover/cursor affordance so it still visually reads as interactive.
- Reuse the existing in-flight guard shape, retargeted to the `dblclick` event.

**Non-Goals:**
- No in-app confirmation dialog/modal — a double-click is itself the confirmation gesture; this
  change does not add a second UI surface.
- No change to `.decode-responder`'s click-to-select-responder interaction (a distinct requirement,
  distinct code path at `main.js:791`–`814`). Not requested by the Captain; flagged as an open
  question below in case symmetry is wanted later.
- No change to the backend (`QsoAnswererService.AnswerCqAsync`, the `qso-controller` spec) — it
  receives the identical payload it always has, just triggered by a different frontend gesture.
- No adjustable/configurable double-click timing threshold — use the browser's native `dblclick`
  event and whatever OS/browser double-click-speed setting the operator already has.

## Decisions

**1. Use the native `dblclick` DOM event, not a hand-rolled click-counting timer.**
Browsers already implement double-click detection consistently, respecting the user's own
OS-level double-click-speed setting (accessibility-relevant). Reimplementing that with a manual
`setTimeout`-based click counter would duplicate platform behavior, introduce a magic timing
constant of our own, and behave worse for operators who've configured a slower double-click
interval for accessibility reasons. Alternative considered and rejected: manual two-click-within-N-ms
tracking — strictly worse on every axis for this use case.

**2. Remove the `click` listener for the answer-cq action entirely; add a `dblclick` listener in
its place.** Do not keep a `click` listener around that does nothing — that would be dead code
inviting confusion later. The row's `cursor: pointer` styling (already present via
`tr.style.cursor = 'pointer'` at `main.js:730`, backed by the `.decode-cq:hover` CSS rule) is
sufficient standalone affordance that the row is interactive; no click handler is needed to
preserve it.

**3. Retarget the existing in-flight guard from `click` to `dblclick`, keep its shape unchanged.**
The `inFlight` boolean, `tr.style.pointerEvents = 'none'` during the request, and the 400 ms
post-success cooldown (D-TX-UI-005's rationale — "operator does not need to retry; 400 ms is
harmless") all still apply verbatim; only the event name they're attached to changes. The failure
mode they guard against (a rapid repeat gesture firing a second overlapping POST before the first
resolves) is identical in shape whether the gesture is a single click or a double-click.

**4. No special handling needed for the native `click`/`click`/`dblclick` event triple.**
A real double-click fires `click`, `click`, then `dblclick` in the DOM event sequence. Since no
`click` listener remains on `.decode-cq` rows after this change, those two `click` events are
inert by construction — there is no risk of the first click of a double-click sequence sneaking
through and arming TX before the `dblclick` fires.

**5. Guard against double-click's default text-selection behavior — by clearing the selection in
the handler, not by disabling selection at the CSS level.** Rapid double-clicking near text often
triggers the browser's native "select the word under the cursor" behavior, which would visually
select decode-row text as a side effect of answering a CQ. The `dblclick` handler calls
`event.preventDefault()` and, since that alone was confirmed live to be insufficient (a stray
selection remained), also calls `window.getSelection()?.removeAllRanges()` immediately afterward
to clear whatever the native gesture just selected.

**Revised during implementation (2026-07-11, after Captain-reported regression):** the first
implementation pass used `user-select: none` on `.decode-cq` as the `preventDefault()` fallback,
per this decision's original wording. That fix was too blunt — `user-select` is inherited, so it
silently disabled **all** text selection on **every** CQ row, permanently, not just during the
double-click gesture. The Captain reported being unable to select/copy text (e.g. a callsign) from
CQ rows at all, which every scenario in this requirement was silent on and never intended.
`removeAllRanges()` in the handler is the correct fix: it removes only the selection the
double-click itself just created, in the same synchronous tick, before paint — ordinary
click-and-drag selection on a CQ row (a different, deliberate gesture, not a `dblclick` event)
is completely unaffected the rest of the time. Verified live: `qa/uat-tmp/
cq-dblclick-08-after-refix-dblclick.png` / `-09-after-refix-drag-select.png`, plus a direct
`getComputedStyle`/`window.getSelection().rangeCount` probe (`cq-dblclick-10-investigate-blue-text.mjs`)
confirming no residual selection state and no stray text-colour change after the double-click.

## Risks / Trade-offs

- **[Risk]** Operators muscle-memory-trained on the old single-click behavior will click once,
  see nothing happen, and may not immediately realize a second click is now required.
  → **Mitigation:** call this out explicitly as an operator-facing behavior change in the release
  notes/changelog (already flagged in `proposal.md`'s Impact section). No in-app messaging is
  added by this change; if confusion persists in practice, a future follow-up could add a subtle
  first-click cue, but that's explicitly out of scope here.
- **[Risk]** A double-click's native text-selection side effect (Decision 5) could look like a
  glitch if not suppressed. → **Mitigation:** `preventDefault()` in the handler; verify live before
  merge.
- **[Trade-off]** Losing the single-click trigger means there is now zero-latency-of-intent
  feedback on the *first* click of an intended double-click (nothing visibly happens until the
  second click completes the gesture). Accepted — this is the entire point of the change (trading
  a small amount of response latency for the intended safety margin against accidental single
  clicks).

## Migration Plan

Pure frontend code change, no persisted state, no schema, no backend contract change. Ship as a
normal commit/PR; rollback is a plain revert with no data cleanup required. No feature flag needed
given the small, self-contained blast radius (one event listener in one file).

## Open Questions

1. Should `.decode-responder`'s click-to-select-responder interaction (`main.js:791`–`814`,
   a distinct TX-D01-adjacent but textually separate requirement) get the same double-click
   treatment for consistency? Not requested; raised here so the Captain can decide whether a
   follow-up change is wanted, rather than silently expanding this change's scope.
2. Is any in-app discoverability affordance beyond the existing hover/cursor styling wanted (e.g.
   a tooltip stating "double-click to answer")? Deferred as a non-goal above; revisit if operators
   report confusion in practice.
