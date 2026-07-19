# Handoff: QSO Transcript — split into its own scrollable section, separate from TX controls

**Date:** 2026-07-19
**Prepared by:** QA engineer (Captain request + source review)
**Status:** Not started
**Context:** UI-only enhancement, not tied to an open defect. The Captain attached two screenshots
(`2026-07-19 225032.png`, `2026-07-19 225204.png`) of a live session showing the right-hand TX panel:
the QSO Transcript list has grown long (65+ entries) and lives in the *same* scroll container as the
TX controls (Enable TX / Call CQ / Abort TX, State, Tx 1–3 rows). Scrolling down through the
transcript scrolls the controls out of view entirely — the Captain annotated this with a red
divider line and asked for the transcript to be its own section, clearly separated from the
controls.
**Clarified with Captain (AskUserQuestion):** of three options (independent-scroll same sidebar /
fully separate column / collapsible section), the Captain chose **same sidebar, independent
scroll** — TX controls stay fixed at the top of `#tx-panel` and never scroll away; the QSO
Transcript becomes its own scrollable sub-region below them, with a clear visual divider.

**Branch name:** `feat/qso-transcript-own-section`

**Severity:** Cosmetic/UX (no functional or data-correctness impact) — but a genuine usability
papercut on longer QSO sessions, per the Captain's live report.

---

## 1. Current structure (as-is)

`web/index.html:95-138` — everything lives directly inside one `<section id="tx-panel">`:

```html
<section id="tx-panel" aria-label="TX control">
  <div class="tx-controls-row"> ... Enable/Call CQ/Abort ... </div>
  <div id="pileup-mode-row" ...> ... </div>
  <div class="tx-state-row"> ... State ... </div>
  <div id="tx-msg-1" ...> ... </div>
  <div id="tx-msg-2" ...> ... </div>
  <div id="tx-msg-3" ...> ... </div>
  <div id="tx-transcript-section" hidden>
    <p class="tx-transcript-title">QSO Transcript</p>
    <ol id="tx-transcript-log" class="tx-transcript-list"></ol>
  </div>
</section>
```

`web/css/app.css:226-234` — `#tx-panel` is the *single* scroll container (`overflow-y: auto`),
`flex: 0 0 320px`, `display: flex; flex-direction: column`. Because there's only one scroll
region, a long transcript pushes the controls above it out of the visible viewport as the operator
scrolls down.

The dark-theme scrollbar rule block at `app.css:196-223` styles `#decodes-panel`, `#tx-panel`, and
`.decode-filter-popup` together — this will need `#tx-panel` replaced with the new transcript
container id once the scroll region moves.

**Important, already confirmed by source read — no JS logic changes needed.** `web/js/main.js`
(lines 99-114) looks up every element purely by `getElementById`/existing class names
(`tx-enable-btn`, `tx-call-cq-btn`, `tx-abort-btn`, `tx-state-display`, `tx-msg-1/2/3`,
`tx-transcript-section`, `tx-transcript-log`, `pileup-mode-row`). None of it depends on DOM
*nesting* or on `#tx-panel` being the scroll container. `web/js/qsoTranscript.js` is DOM-free
entirely. So this is an HTML/CSS-only restructuring — reparenting existing elements under new
wrapper `<div>`s and moving the scroll/overflow CSS — with **no element IDs renamed or removed**.

---

## 2. Actions

1. In `web/index.html`, wrap the existing TX-controls elements (the `.tx-controls-row` div, the
   `#pileup-mode-row` div, the `.tx-state-row` div, and the three `#tx-msg-1/2/3` rows — everything
   currently between `<section id="tx-panel">` and the existing `<!-- QSO Transcript -->` comment)
   in a new wrapper, e.g. `<div id="tx-controls-section">`. Do not rename, remove, or reorder any
   existing element IDs or classes inside it.
2. Leave `<div id="tx-transcript-section" hidden>` (and its children `.tx-transcript-title`,
   `#tx-transcript-log`) as a sibling of the new `#tx-controls-section`, both direct children of
   `<section id="tx-panel">`.
3. In `web/css/app.css`:
   - Change `#tx-panel` (`:226-234`) to remain `flex: 0 0 320px; display: flex; flex-direction:
     column;` but **remove** `overflow-y: auto` and `padding: 0.75rem` from it — padding moves to
     the two new sub-sections (or stays on `#tx-panel` and only the transcript list scrolls inside
     its own inset — developer's call, whichever reads cleanest, but the *controls* must never
     themselves need to scroll).
   - Add `#tx-controls-section { flex: 0 0 auto; padding: 0.75rem 0.75rem 0; }` (or equivalent) —
     fixed height, never shrinks, never scrolls.
   - Add `#tx-transcript-section` layout rules: `flex: 1 1 auto; min-height: 0; overflow-y: auto;
     padding: 0.75rem; border-top: 1px solid var(--color-border); margin-top: 0.5rem;` — this is
     the visual divider the Captain drew in red, and the independent scroll region. (`min-height:
     0` is required — same reasoning as the existing `#content-row` comment at `app.css:183` — or
     a flex child with default `min-height: auto` will refuse to shrink and won't scroll.)
   - Update the dark-theme scrollbar selector block at `app.css:196-223` — replace `#tx-panel` with
     `#tx-transcript-section` in all five selector groups (`scrollbar-color`, `::-webkit-scrollbar`,
     `-track`, `-thumb`, `-thumb:hover`), since the transcript region is now the scrolling element,
     not `#tx-panel` itself.
   - `#tx-transcript-section[hidden]` should still collapse to nothing when empty (native `hidden`
     attribute behaviour already handles this — just confirm the new flex/border/margin rules don't
     apply visually while `hidden` is set, i.e. don't accidentally render an empty bordered strip
     before the first transcript entry arrives).
4. Do not touch `web/js/main.js` or `web/js/qsoTranscript.js` — no JS changes are expected for this
   task. If during implementation you find a reason JS *does* need to change, stop and flag it back
   to QA rather than proceeding on an assumption.

---

## 3. Acceptance criteria (QA will check these)

- Visually: TX controls (Enable TX/Call CQ/Abort TX, State, Tx 1–3 rows) sit in a clearly bordered
  section at the top of the right-hand panel; QSO Transcript sits below a visible divider, in its
  own section with its own heading.
- Functionally: with a transcript long enough to overflow (≥ 30 entries, matching the Captain's
  screenshots), scrolling the transcript list scrolls *only* the transcript — the TX controls above
  remain pinned and fully visible at all times.
- The transcript section still starts `hidden` and appears only once the first entry is logged
  (existing behaviour via `txTranscriptSection.hidden = false` in `main.js:158` — unchanged).
- No change to any element `id` referenced from `web/js/main.js` — before/after `grep -n
  "getElementById" web/js/main.js` should resolve to the same set of IDs, all still present in
  `index.html`.
- No regression to the pileup-mode row's existing show/hide behaviour (FR-PILEUP-001) — it stays
  inside the controls section, not the transcript.
- Dark-theme scrollbar styling (thumb/track colours) still applies to whichever element now
  actually scrolls — check in an actual browser, not just by reading the CSS, since scrollbar
  pseudo-elements are easy to silently mis-target.
- `web/js/qsoTranscript.test.js` (`node --test`) still passes unmodified — this module is DOM-free
  and should be untouched by a layout-only change; if it needs edits, that's a signal scope crept
  beyond what this task describes.
- Screenshot before/after per HK-005 ordering (screenshot-before → implementation →
  screenshot-after), lint with `tools/check_screenshot_task_order.py` if this work is tracked via
  OpenSpec tasks.

---

## 4. References

- Captain's screenshots: `2026-07-19 225032.png`, `2026-07-19 225204.png` (TX panel + long QSO
  Transcript, red annotations marking the desired divider).
- `web/index.html:94-138` (current structure), `web/css/app.css:174-234` (`#content-row`/`#tx-panel`
  layout), `:1105-1121` (QSO Transcript styling), `:196-223` (shared dark-theme scrollbar rules).
- `web/js/main.js:97-159` (TX panel DOM element lookups and `appendTranscriptEntry`) — read-only
  reference confirming no JS changes are required.
- Originating feature: `openspec/changes/archive/2026-07-18-qso-transcript-panel/` (FR-062, design
  decisions 2–6 referenced in `app.css` comments) — this task does not change any of that feature's
  behavioural contract, only its visual/layout presentation.

This is a small enough, self-contained UI change that a full OpenSpec proposal is likely
unnecessary — a straightforward branch + PR through the normal review path should suffice. QA will
confirm during review that no behavioural spec (`web-frontend` or otherwise) needs updating as a
result.
