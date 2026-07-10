# DEV TASK — GUI polish batch (7 items)

**Date:** 2026-07-10
**OpenSpec change:** none — every item below either has no live spec governing it, or (item 2)
stays fully within the existing ratified `tx-state-indicators` spec. If any item turns out to
require a behavioural change beyond what's described here, stop and flag it to QA rather than
editing `openspec/specs/` directly.
**Branch:** continue on whichever branch `/opsx:apply` created for the `decode-status-control-merge`
change (implement that change's `tasks.md` first, land it as its own clean commit(s), then layer
these seven items on top as additional commits on the same branch) — do **not** open a second
branch off `main`. The three shared files (`web/index.html`, `web/js/main.js`, `web/css/app.css`)
don't overlap at the line level between the two workstreams (verified), so this is purely to avoid
an unnecessary rebase later, not a sign the two are entangled. Keep each of the seven items below
as its own commit (especially item 2, which is a backend `src/` fix unrelated to the other six —
don't squash it in with the frontend commits) so the history stays revertible item-by-item.
**Status:** New. Split off from an 8-item Captain feedback list; item 4 (merge the Decoding
label+button into one control) is being handled separately via a proper `openspec-propose`
change (`decode-status-control-merge`) because it contradicts two ratified requirements in
`web-frontend/spec.md` — do not implement it here, it's already fully specced in that change's
`tasks.md`.

---

## 1. Bold the column header when its filter axis is active

**Where:** `web/js/main.js` (`FILTER_AXES` at `main.js:381`–`387`, `currentDecodeFilter`
mutations at `main.js:446`, `458`, `477`, `509`, `580`, `1676`, all of which call
`reapplyDecodeFilterToRenderedRows()` at `main.js:366` immediately afterward), `web/css/app.css`
(`.filterable-col` rules at `app.css:425`–`432`).

**What to do:**
- Add a helper, e.g. `updateFilterHeaderStyles()`, that iterates `FILTER_AXES` and, for each axis,
  computes whether it is currently restricting anything:
  `const active = currentDecodeFilter[axis.statesField] != null || (axis.attributeField &&
  currentDecodeFilter[axis.attributeField] != null);`
  then toggles a new CSS class (e.g. `filter-axis-active`) on `document.getElementById(axis.headerId)`
  accordingly.
- Call this helper from inside `reapplyDecodeFilterToRenderedRows()` (or immediately alongside
  every one of its six call sites — inside is simpler and covers all of them for free, since that
  function already re-runs after every `currentDecodeFilter` mutation without exception).
- Add the CSS rule near the existing `.filterable-col` block (`app.css:425`):
  `#decodes-table th.filterable-col.filter-axis-active { font-weight: 700; }`

**Verification:** open a filter popup on any of Ctc/DXCC/Cnt/CQz/ITz, restrict it (uncheck at
least one value, or select a worked-before state), close the popup, confirm that column's header
text renders bold and the other four don't. Clear the filter (re-check everything back to the
unfiltered default) and confirm the bold reverts. Reload the page with a filter already active
server-side (`GET /api/v1/decode-filter` non-default) and confirm the header renders bold
immediately on load, not just after the next local change (this exercises the `main.js:580` and
`main.js:1676` call sites, not just the popup-driven ones).

---

## 2. TX-enable button under-reports colour during answerer retries

**Root cause, confirmed by direct code reading, not guessed:** the ratified `tx-state-indicators`
spec (`openspec/specs/tx-state-indicators/spec.md`) says the button SHALL render bright red
whenever `state` is a `Tx*` sub-state and dark red otherwise, "derived entirely from existing
`txState` payload fields... with no additional server-side signal" (Decision 2) — and the current
implementation is a correct reading of that spec in the normal path. But
`QsoAnswererService.RetryOrAbortAsync` (`src/OpenWSFZ.Daemon/QsoAnswererService.cs:1015`–`1040`)
retransmits audio on a retry (`TransmitAsync` at line 1034) **without** calling
`SetStateAndNotify` first — the comment at line 1036 explains this was deliberate ("D-008:
watchdog is NOT reset here — retries are not state transitions... Stay in current state"), but the
side effect is that the broadcast `state` stays `WaitReport`/`WaitRr73` (dark red) for the full
duration of the retransmission, even though audio is actually playing. The button under-reports —
it shows dark red while the rig is transmitting.

**This is not hypothetical — the caller-role service already gets this right.**
`QsoCallerService.RetryOrAbortAsync` (`src/OpenWSFZ.Daemon/QsoCallerService.cs:816`–~`871`)
brackets its retry transmission with two extra `SetStateAndNotify` calls, e.g. for the
`WaitAnswer` branch (lines 838–843):
```csharp
SetStateAndNotify(CallerState.TxCq);
await TransmitAsync(cqMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
_skipNextRetry = true;
SetStateAndNotify(CallerState.WaitAnswer);
```
i.e. broadcast the `Tx*` sub-state immediately before retransmitting, then broadcast back to the
`Wait*` state immediately after. `SetStateAndNotify` (`QsoAnswererService.cs:1072`–`1083`) only
sets `_state` and publishes to `_txEventBus` — it does **not** call `ResetWatchdog()` (that's a
separate, explicit call made only at genuine forward-transition sites). So mirroring the caller's
pattern in the answerer does **not** reintroduce the watchdog-reset-on-retry problem D-008 was
guarding against; it only fixes the broadcast.

**Fix:** in `QsoAnswererService.RetryOrAbortAsync`, bracket the retransmission the same way:
- Before `await TransmitAsync(_lastTxMessage, _lastTxFreqHz, stoppingToken)`, call
  `SetStateAndNotify(...)` with the `Tx*` sub-state corresponding to the message being
  retransmitted — `_state == QsoState.WaitReport` → `SetStateAndNotify(QsoState.TxAnswer)` (the
  original answer is what's being retried); `_state == QsoState.WaitRr73` →
  `SetStateAndNotify(QsoState.TxReport)`. Capture the original `_state` (or just branch on it)
  before overwriting, since `SetStateAndNotify` mutates `_state`.
- After the `await TransmitAsync(...)` line, call `SetStateAndNotify(...)` back to the original
  `Wait*` state (`WaitReport` or `WaitRr73` respectively) so the button reverts to dark red once
  the retransmission finishes and the daemon resumes waiting for a response.
- Leave the `_skipNextRetry = true;` line and the "watchdog is NOT reset here" comment exactly as
  they are — this fix only changes what gets broadcast, not the retry/watchdog timing logic.

**Verification:**
- Extend `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` with a test exercising a retry
  cycle (no response received within a slot, from both `WaitReport` and `WaitRr73`) and assert the
  event bus received the bracketing `Tx*` state broadcast before the retransmission and the
  original `Wait*` state broadcast after — mirroring whatever test already covers
  `QsoCallerService`'s `WaitAnswer`-retry bracketing (find and pattern-match it in
  `QsoCallerServiceTests.cs`).
- Add/keep a test explicitly asserting the watchdog is **not** reset across this bracketed retry
  (i.e. D-008 still holds) — this is the one place a naive fix could regress silently.
- Live verification: use a two-radio (or virtual-audio-cable) setup where one station is
  configured to never reply, force an answerer-role retry, and confirm `#tx-enable-btn` visibly
  flips to bright red for the duration of each retransmission and back to dark red while waiting.

---

## 3. CAT badge: static "CAT" text, keep the existing colour coding

**Root cause:** `setCatStatus` (`web/js/main.js:1062`–`1072`) sets
`catBadgeEl.textContent = status;` — the badge literally displays the raw status word
("Connected", "Connecting", "Error"). The colour differentiation already lives entirely in the
CSS classes (`app.css:845`–`848`: `.cat-connected` / `.cat-connecting` / `.cat-error` /
`.cat-disabled`), keyed off `catBadgeEl.className = 'cat-badge cat-' + status.toLowerCase()` — the
text is redundant with (and, per the Captain, more confusing than) the colour. This mirrors the
existing `#audio-indicator` pattern next to it in the status bar, which already uses a fixed
"Audio" label plus a coloured dot rather than a raw status word.

**Fix:** in `setCatStatus`, change line 1070 to `catBadgeEl.textContent = 'CAT';` — do **not**
touch the `className` line (line 1071); the colour-coding behaviour (which the Captain
explicitly said is fine) must be unchanged. Leave the early-return branch (lines 1063–1068, the
`Disabled`/absent-status case that hides the badge entirely) untouched. Optionally — not
required — consider updating the `title` attribute (currently a static `"CAT rig connection
state"` on the `<span>` in `index.html:26`) to include the live status word for accessibility/
hover users, e.g. via `catBadgeEl.title = 'CAT rig connection state: ' + status;` in the same
function, but only if it's a trivial addition; skip it if it complicates the diff.

**Verification:** with CAT connected, connecting, and erroring (or mocked via whatever harness
already drives `QsoAnswererServiceTests`/CAT integration tests for this), confirm the badge always
reads exactly "CAT" and only its background colour changes between green/blue/red per the existing
classes.

---

## 4. (Not this task) — merge Decoding label+button

Handled separately via `openspec-propose`. Do not touch `#decode-badge` / `#decode-toggle` as part
of this dev task.

---

## 5. Remove the waterfall canvas's tooltip text

**Where:** `web/index.html:47` —
```html
<canvas id="waterfall" title="Ctrl+click: set RX &middot; Ctrl+right-click: set TX &middot; Shift+click: set both &middot; unmodified clicks do nothing"></canvas>
```
This is a hover tooltip (the `title` attribute), not on-canvas rendered text — the equivalent
information is already shown permanently in `#waterfall-controls` just below the canvas
(`index.html:51`–`61`, `.freq-readout-hint` span at line 60: "Ctrl+click: RX · Ctrl+right-click:
TX · Shift+click: both").

**Fix:** remove the `title="..."` attribute from the `<canvas id="waterfall">` element entirely.
Leave the element otherwise unchanged (`id="waterfall"` is depended on by `web/js/spectrum.js` —
do not rename it). No live spec constrains this attribute's content (checked: `web-frontend/spec.md`
only requires the `<canvas id="waterfall">` element to exist and be visible, not any particular
`title`), so this is a pure removal with no spec-sync follow-up needed.

**Verification:** hovering the waterfall shows no browser tooltip; the on-screen hint text below
the waterfall is unchanged and still present.

---

## 6. Settings "Region data" tab wraps except when Logs tab was last active

**Root cause, confirmed by reading the CSS, not guessed:** `#settings-main` defaults to
`max-width: 700px` (`app.css:628`–`633`). A separate rule (`app.css:641`–`644`) widens it to
`900px`, but only via the selector `body:has(#tab-logs.active)` — i.e. it only fires when the
Logs tab panel (`id="tab-logs"`, `settings.html:554`) carries the `.active` class. The Region-data
tab panel (`id="tab-region-data"`, `settings.html:573`) has its own wide monospace content — the
`<pre id="region-data-lookup-result" class="logs-tail-output">` box (`settings.html:612`) uses the
exact same `.logs-tail-output` class as the Logs tab's own tail output — but isn't included in
that selector, so it's stuck at the narrower 700px width and wraps. This is exactly the same class
of problem the code comment at `app.css:635`–`644` already describes for the Logs tab itself; the
Region-data tab was simply never added to the fix.

**Fix:** extend the selector at `app.css:641`–`642` to include the Region-data tab panel:
```css
body:has(#tab-logs.active) #settings-page,
body:has(#tab-logs.active) #settings-main,
body:has(#tab-region-data.active) #settings-page,
body:has(#tab-region-data.active) #settings-main {
  max-width: 900px;
}
```
Update the explanatory comment above it (currently says "only while that tab is active, so
General/Radio hardware/Logging/Advanced/Frequencies keep the narrower column above") to mention
Region data is now also included, so a future reader doesn't have to re-derive this from the CSS.

**Verification:** open Settings, click the Region data tab directly (without visiting Logs first
in that session) and confirm the status summary and the lookup result `<pre>` box render at the
same 900px-wide, non-wrapped layout the Logs tab gets. Click through General/Radio
hardware/Logging/Advanced/Frequencies and confirm they are still at the narrower 700px column
(unaffected).

---

## 7. Remove the duplicate "Back to main" link from the standalone full-log page

**Where:** `web/logs.html:13` — `<a id="back-link" href="/">← Back to main</a>` inside the
`<nav class="settings-nav" aria-label="Breadcrumb">` block (lines 12–16).

**Context:** this page is opened via "Open full log in new tab" on the Settings → Logs tab
(`settings.js:983`–`991`, `window.open(url, '_blank')`) as a genuinely standalone tab — it is not
a step in a navigation flow the operator needs a way back from; closing the tab is the natural
exit. The Captain's complaint: clicking it duplicates the main application page in the new tab
rather than usefully navigating anywhere the operator wants to be. No live spec
(`openspec/specs/log-viewer/spec.md`) requires this link — it names only the page's own content
and no-auto-refresh behaviour.

**Fix:** remove the `<a id="back-link" href="/">← Back to main</a>` line and the now-redundant
`<span aria-hidden="true">/</span>` breadcrumb separator right after it (`logs.html:14`), leaving
just the "Full Log" breadcrumb label (line 15) — or simplify the whole `<nav class="settings-nav">`
block to plain text if a single-item breadcrumb looks odd once the link is gone; use your
judgement on the minimal sensible markup. Do **not** touch `settings.html:14`, which has the same
`id="back-link"` markup but lives on the Settings page proper, where "Back to main" is a real,
useful navigation affordance (Settings is reached by clicking through from the main page, not
opened as a standalone tab) — that one stays exactly as is.

**Verification:** open Settings → Logs → "Open full log in new tab"; the new tab shows only the
"Full Log" heading/content, no "Back to main" link or dangling breadcrumb separator. Settings'
own "Back to main" link (reached via `⚙ Settings` from the main page) is unaffected.

---

## 8. Dark-theme scrollbar styling for `#decodes-panel`

**Where:** `web/css/app.css`, `#decodes-panel` rule at `app.css:182`–`198` (`overflow-y: auto;` at
line 197 is what produces the scrollbar the Captain screenshotted). No existing `scrollbar-*` or
`::-webkit-scrollbar` rules exist anywhere in `app.css` (checked) — this is genuinely unstyled,
falling back to the OS/browser default light scrollbar, which reads as a glaring white bar against
the app's dark theme (`--color-bg: #0d1117`, `--color-surface: #161b22`).

**Fix:** add both the standard and WebKit-specific scrollbar rules, scoped to `#decodes-panel` (or
broadened to `body` / `:root` if you'd rather make every scrollable panel in the app consistently
dark — use your judgement, but at minimum cover `#decodes-panel`), using the existing design
tokens rather than new hard-coded colours:
```css
#decodes-panel {
  scrollbar-color: var(--color-border) var(--color-surface);
}
#decodes-panel::-webkit-scrollbar {
  width: 10px;
}
#decodes-panel::-webkit-scrollbar-track {
  background: var(--color-surface);
}
#decodes-panel::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: var(--radius);
}
#decodes-panel::-webkit-scrollbar-thumb:hover {
  background: var(--color-muted);
}
```
Place this near the `#decodes-panel` block (after line 198) so the two read together.

**Verification:** populate enough decode rows to force a vertical scrollbar (or shrink the
viewport), confirm the scrollbar track/thumb now render in dark tones consistent with the rest of
the theme rather than the stark white default. Check both Chromium (WebKit rules) and Firefox
(`scrollbar-color` rule) if both are available to you; if only one browser is available, note which
one you verified in your completion notes.

---

## What NOT to change

- Item 4 (merge Decoding label+button) — separate `openspec-propose` change, not this task.
- `openspec/specs/tx-state-indicators/spec.md` or `openspec/specs/web-frontend/spec.md` — item 2's
  fix is a bug fix that brings the implementation back in line with the existing ratified spec; it
  does not change what the spec says, so no spec-text edit is needed or wanted.
- `DecodeFilterEvaluator` / `isDecodeVisible` predicate logic (item 1) — unaffected; only a new
  header CSS class and its toggle logic are added.
- `_skipNextRetry` / watchdog timing in `QsoAnswererService.RetryOrAbortAsync` (item 2) — only the
  state-broadcast bracketing changes; retry counting, watchdog reset behaviour (D-008), and the
  message content itself are untouched.
- `settings.html:14`'s "Back to main" link (item 7) — stays; only `logs.html`'s copy is removed.

## Re-verification before handing back

1. `dotnet build OpenWSFZ.slnx -c Release` / `dotnet test OpenWSFZ.slnx -c Release --no-build` —
   expect the current baseline count plus the new retry-bracketing test(s) from item 2; no
   regressions elsewhere.
2. `openspec validate --strict --all` — expect unchanged pass count; none of these seven items
   should require any `openspec/` edits.
3. Manual/live pass through each of the seven verification sections above — screenshots for the
   visual ones (1, 3, 5, 6, 7, 8) are the fastest way to prove them to QA on re-review, following
   the existing `qa/uat-tmp/` naming convention.

## QA re-review

Once all seven are complete, QA will re-check each item's verification steps directly (not just
trust this document's claims), confirm no spec drift, and confirm item 2's watchdog-preservation
test actually exercises the D-008 guarantee rather than just the new broadcast. Hold the merge for
that pass.

## References

- Captain's original 8-item feedback list (this session, 2026-07-10); item 4 split out to a
  separate `openspec-propose` change.
- `openspec/specs/tx-state-indicators/spec.md` — governs item 2's target behaviour; unchanged by
  this fix.
- `openspec/changes/archive/2026-07-05-f-004-operator-visibility-improvements/` — origin of the
  `#tx-enable-btn` armed/transmitting design (D-TX-UI-002, Decision 2).
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:816`–`871` — the existing correct retry-bracketing
  pattern item 2 mirrors.
- `dev-tasks/2026-07-08-d-013-qso-record-stale-dial-frequency.md` — prior precedent for a
  dev-task-sized (not openspec-change-sized) defect fix in this same service pair.
