# DEV TASK — decode-panel-filtering: popup checkbox alignment + Select All/None

**Date:** 2026-07-10
**OpenSpec change:** `decode-panel-filtering` (open, on `feat/decode-panel-filtering`, not yet
archived)
**Branch:** continue on the existing `feat/decode-panel-filtering` branch — do not open a new one
**Status:** Backend and gating logic fully reviewed and approved (see QA review below). This
handoff covers two Captain-requested frontend UI corrections plus one blocking defect QA found
independently while verifying the change. Hold the merge until all three are done.

---

## 0. Where things stand

QA reviewed the completed implementation against `proposal.md`/`design.md`/the delta specs and
ran the full verification suite personally rather than trusting `tasks.md`'s claims:

- `dotnet build OpenWSFZ.slnx -c Release` — 0 warnings, 0 errors.
- `dotnet test OpenWSFZ.slnx -c Release` — **1006/1006**, matching the claimed count exactly.
- `openspec validate --strict --all` — **51/51**.
- Backend (`DecodeFilterState`, `DecodeFilterEvaluator`, `IDecodeFilterStore`, the
  `QsoAnswererService`/`QsoCallerService` gating hooks, the API + WebSocket broadcast) all match
  design.md's Decisions 1–3 exactly, including correct reuse of the N6 scope-guard pattern. No
  changes needed there.

**One defect QA found that you must fix as part of this task** (§3 below): `web/js/decodeFilter.test.js`'s own header comment does not parse — verify this yourself with
`node --check web/js/decodeFilter.test.js` before you start, so you're looking at the same
failure QA is describing.

**Two Captain-requested UI changes** (§1, §2 below), found while the Captain exercised the
popups the developer's own screenshots (`qa/uat-tmp/popup-ctc.png`, `popup-dxcc.png`) had
already captured.

---

## 1. Checkbox alignment in the filter popups

### What's wrong, precisely

The Captain's complaint was "the options aren't aligned on the left" in the column-header filter
popups. QA did not take this at face value — a `getBoundingClientRect()` check on the popup rows
themselves showed the **rows** (the `<label class="decode-filter-popup-row">` elements) are
already perfectly left-aligned, all at the same `x`, in every popup. The actual bug is one level
down: the **checkbox control itself** renders at an inconsistent width from row to row, which is
what reads as "misaligned" at a glance.

**Root cause, confirmed by direct pixel measurement (not guessed):** `web/css/app.css`'s global
`input, select` rule (line 68) sets `width: 100%; padding: 0.4rem 0.6rem;` on *every* `<input>` in
the app, including `type="checkbox"`. Inside `.decode-filter-popup-row`'s flex layout
(`app.css:480`), each checkbox competes for space against its sibling label text under
`flex-shrink`; because the checkbox's basis is `width: 100%` rather than its natural small
intrinsic size, how much it actually shrinks to depends on how much room the row's *own* text
takes up. Rows with short label text (e.g. "Never worked") leave the checkbox more room to
stretch into (measured: a 89px-wide checkbox in that row), rows with long label text (e.g.
"Worked — different band") starve it back down closer to normal (measured: 13px, correct). Three
checkboxes in the same popup, three different rendered widths, same left edge — which is why it
*looks* unaligned even though the row/label boxes themselves are not.

This codebase has already solved this exact problem twice — `.checkbox-label input[type="checkbox"]`
(`app.css:712`) and `.waterfall-hold-label input[type="checkbox"]` (`app.css:926`) both reset the
inherited `width: 100%` back to `width: auto; margin: 0;` for their respective checkboxes. The new
popup checkboxes never got the same treatment.

### Fix

Add a third instance of the same established pattern, in `web/css/app.css` near the other
`.decode-filter-popup-*` rules (the block currently runs `app.css:444`–`501`):

```css
.decode-filter-popup-row input[type="checkbox"] {
  width: auto;
  margin: 0;
  cursor: pointer;
  accent-color: var(--color-accent);
}
```

Place it directly after `.decode-filter-popup-row` (`app.css:480`) so the two rules read
together. `accent-color: var(--color-accent)` is included to match the other two precedents'
styling, not just their sizing fix — check that it doesn't clash with anything already implied
for these checkboxes (nothing currently sets `accent-color` on them, so this is a pure addition).

### Verification

Re-run the same measurement QA used, or simpler — visually confirm in a real browser that all
three "Never worked" / "Worked — different band" / "Worked — this band" checkboxes in every
popup (Ctc, DXCC, Cnt, CQz, ITz) render as identically-sized small squares whose left edges and
whose glyph rendering line up exactly, not just their containing `<label>` boxes. A new
screenshot per popup (mirroring the existing `qa/uat-tmp/popup-*.png` convention) is the
easiest way to prove this to QA on re-review.

---

## 2. "Select All" / "Select None" for the attribute allow-list section

**Scope, confirmed with the Captain:** this applies **only to the attribute allow-list section**
of the DXCC/Cnt/CQz/ITz popups (`web/js/main.js`, the block at `main.js:423`–`461`, guarded by
`if (axis.attributeField)`) — **not** to the worked-before tri-state section, and **not** to the
Ctc popup (which has no attribute allow-list section at all, per design.md Decision 4 — nothing to
add there). This matches why the Captain's request named DXCC/CNT/CQz/ITz specifically and not
Ctc.

### Placement

"On top" — i.e., above the per-value checkbox list, as the first thing rendered inside the
attribute-allow-list section (`main.js:426`, right after `section.className =
'decode-filter-popup-section'` and before the `values.length === 0` branch at `main.js:430`). It
should render whether or not there are any seen values yet — actually, if `values.length === 0`
there's nothing to select, so gate its rendering on `values.length > 0` the same way the checkbox
list itself is gated (i.e., inside the `else` branch at `main.js:435`, before the `for (const
value of values)` loop at `main.js:437`).

### Behaviour — reuse the existing null/empty-array convention, don't invent a new one

The per-checkbox handler (`main.js:443`–`454`) already encodes the filter's core semantics:
checking every box → `attributeField` set to `null` (no restriction, matches `Unfiltered`);
unchecking any → an explicit array of just the checked values (`[]` if none checked, which
`DecodeFilterEvaluator`/`isDecodeVisible` already treat as "nothing passes this axis" — see
`DecodeFilterEvaluatorTests.An_explicit_empty_allow_list_filters_everything_on_that_axis` and its
JS mirror). **Select All** and **Select None** must produce exactly those two states, not a new
third representation:

- **Select All** → set every checkbox in the section to `checked = true`, then set
  `currentDecodeFilter[attributeField] = null` (identical outcome to the operator manually
  checking every box).
- **Select None** → set every checkbox in the section to `checked = false`, then set
  `currentDecodeFilter[attributeField] = []` (identical outcome to the operator manually
  unchecking every box).
- Both must call `reapplyDecodeFilterToRenderedRows()` and `commitDecodeFilterChange()` afterward
  — the same two calls the per-checkbox handler already makes (`main.js:452`–`453`) — so the row
  hiding and the `POST /api/v1/decode-filter` round-trip behave identically regardless of which
  control the operator used.

### One control or two — your call, per the Captain's own framing

The Captain explicitly left this open ("This may also be one option that performs both"). Either
is acceptable:

- **Two small controls** ("Select All" / "Select None" as text-buttons or links side by side) —
  simplest to implement, unambiguous to the operator, no new state to track.
- **One combined control** (e.g. a single "select all" checkbox/toggle whose own checked state
  drives all the others) — fewer elements, but needs a decision on what it shows when the section
  is in a mixed state (some checked, some not) — a third, indeterminate visual state, which is
  more UI work for a section that already re-renders on every popup open anyway.

QA's recommendation, not a requirement: two buttons is the lower-risk choice given how this popup
already rebuilds its DOM from scratch on every open (`decodeFilterPopupEl.innerHTML = ''` at
`main.js:415`) — there's no persistent indeterminate-checkbox state to maintain across re-renders
either way, so the simpler control costs nothing.

Whichever you choose, style it consistently with the existing popup CSS vocabulary
(`.decode-filter-popup-*` classes) rather than introducing an unrelated button style — the
existing `.decode-filter-popup-close` button (`app.css:496`) is a reasonable visual reference
for a full-width or two-up button pair at the top of the section.

### Verification

- Confirm clicking "Select All" leaves every checkbox in that section checked, and a subsequent
  `GET /api/v1/decode-filter` shows that axis as `null`.
- Confirm clicking "Select None" leaves every checkbox unchecked, and `GET /api/v1/decode-filter`
  shows that axis as `[]` (an empty array, not `null` — the same "explicit empty is distinct from
  untouched" rule the rest of this feature already enforces).
- Confirm the worked-before section and the Ctc popup are visually and functionally unchanged.

---

## 3. Blocking defect — `web/js/decodeFilter.test.js` does not parse

Independent of the two Captain requests above, QA ran the JS test suite as part of verifying
`tasks.md`'s claims and found it does not execute at all:

```
$ node --check web/js/decodeFilter.test.js
web/js/decodeFilter.test.js:8
 * Run with: node --test web/js/decodeFilter.test.js  (or: node --test "web/js/**/*.test.js")
                                                                                  ^
SyntaxError: Unexpected token '*'
```

**Cause:** the file's own JSDoc header comment (line 8) contains the example command `node --test
"web/js/**/*.test.js"`. That glob contains a literal `**/`, which is JavaScript's block-comment
*close* sequence — it terminates the file's own `/** ... */` header early, mid-sentence, leaving
the rest as invalid bare source. QA confirmed the underlying 21 test cases and the
`isDecodeVisible` predicate itself are correct (all 21 pass once the comment text is reworded in
a scratch copy) — this is purely a self-inflicted parse error in the comment text, not a logic
defect. But as committed, none of the 21 tests actually run, and `tasks.md`'s claims for tasks 5.1
and 6.2 are not reproducible.

**Fix:** reword the example command so no contiguous `**/` appears — e.g. `node --test
web/js/*.test.js` (a single-star glob is sufficient; there is exactly one JS test file today).
Do not just delete the sentence — keep the "how to run this" guidance, just phrased so it can't
close its own comment.

**Verification:** `node --check web/js/decodeFilter.test.js` must exit cleanly, and `node --test
web/js/decodeFilter.test.js` must report `tests 21 / pass 21 / fail 0`. Please also note in your
completion notes whether you'd like a `package.json` script or CI step added so this can't
silently regress again — not required for this task's acceptance, but worth a decision since
nothing currently runs this suite automatically (grepped `.github/workflows/` — no `node --test`
step exists anywhere).

---

## 4. What NOT to change

- Nothing in `src/` — backend is fully reviewed and approved, no changes requested there.
- `DecodeFilterEvaluator.IsVisible` / `isDecodeVisible` predicate logic itself — unaffected by any
  of the above; only the popup's checkbox CSS and the Select-All/None convenience controls change.
- `web/index.html` — no markup changes needed for either UI fix; both are pure `main.js` DOM
  construction + `app.css` changes.
- Ctc popup — explicitly out of scope for §2 (no attribute-allow-list section exists there to add
  Select All/None to).

## 5. Re-verification before handing back

1. `dotnet build OpenWSFZ.slnx -c Release` / `dotnet test OpenWSFZ.slnx -c Release --no-build` —
   expect the same 1006/1006 (§1/§2 are frontend-only, §3 doesn't touch dotnet-counted tests).
2. `node --test web/js/decodeFilter.test.js` — expect 21/21 passing (currently 0 run at all).
3. `openspec validate --strict decode-panel-filtering` — expect unchanged pass; none of these
   three fixes should require spec-text changes (they're implementation-detail corrections, not
   behavioural/requirement changes).
4. New or updated screenshots in `qa/uat-tmp/` for the DXCC and Ctc popups showing corrected
   checkbox alignment, and a new one showing the Select All/None controls on (e.g.) the DXCC
   popup.

## 6. QA re-review

Once §1–§3 are complete, QA will re-check: checkbox sizing is now consistent across all five
popups, Select All/None produce exactly `null`/`[]` on the wire (not some other representation),
the worked-before section and Ctc popup are untouched, and `node --test` genuinely runs and
passes. Please hold the merge for that pass.

## 7. References

- `openspec/changes/decode-panel-filtering/design.md` — Decision 4 (column-header popup UI,
  attribute-allow-list scope).
- `web/css/app.css:68` (`input, select` global rule — the source of §1's bug),
  `app.css:712` and `app.css:926` (`.checkbox-label`/`.waterfall-hold-label` — the two existing
  precedents §1's fix mirrors), `app.css:444`–`501` (the `.decode-filter-popup-*` block to extend).
- `web/js/main.js:381`–`387` (`FILTER_AXES`), `main.js:413`–`508` (`openFilterPopup`,
  attribute-list section at `423`–`461`, worked-before section at `463`–`494`).
- `web/js/decodeFilter.test.js:8` — the broken comment line for §3.
- `qa/uat-tmp/popup-dxcc.png`, `qa/uat-tmp/popup-ctc.png`,
  `qa/uat-tmp/popup-ctc-tabB-after-sync.png` — the developer's own existing screenshots; new ones
  for this task should follow the same naming convention.
