# DEV TASK — adif-qso-confirmation: replace disabled checkboxes with checkmark spans

**Date:** 2026-07-08
**OpenSpec change:** `adif-qso-confirmation` (still open, on `feat/adif-qso-confirmation`, not
yet archived) — `openspec validate --strict adif-qso-confirmation` passes after this task's spec
amendments
**Branch:** continue on the existing `feat/adif-qso-confirmation` branch — do not open a new one
**Status:** Backend fully reviewed and approved (see QA review below). This handoff covers one
outstanding frontend correction only.

---

## 1. Context

QA reviewed the completed `adif-qso-confirmation` implementation and ran it past the Captain.
Verdict on the backend: solid — matches design.md's six decisions exactly, 941/941 tests pass
(28 new, all meaningful assertions against the actual spec scenarios, not coverage padding), zero
build warnings, `openspec validate --strict` passes.

One issue came back from the Captain's own inspection of the running UI: the P/C/R columns
render as `<input type="checkbox" disabled>`, and the disabled state is very hard to read against
the dark theme — exactly the risk design.md's original Open Question flagged, but the
`accent-color` mitigation the developer applied wasn't enough in practice (most browsers suppress
`accent-color` on `:disabled` controls regardless of what CSS says).

**Captain's direction, already applied to the OpenSpec artifacts for you:** replace the checkbox
with a plain `<span>` — a green checkmark when the boolean is `true`, empty when `false`. QA has
already:

- Added **Decision 7** to `design.md` documenting this correction and closing the Open Question.
- Rewritten the `web-frontend` spec delta's requirement text and all six scenarios to describe
  the span/checkmark shape instead of the checkbox shape (`openspec validate --strict` still
  passes).
- Added **§5** to `tasks.md` (tasks 5.1–5.5) with the concrete implementation steps below.

You do not need to re-derive the design decision — just implement it.

## 2. Actions

Follow `openspec/changes/adif-qso-confirmation/tasks.md` §5 in order:

1. **`web/js/main.js`** — `makeWorkedBeforeCell(checked)` (currently ~line 368) builds an
   `<input type="checkbox" disabled>`. Replace it with a `<span>`:
   ```js
   function makeWorkedBeforeCell(checked) {
     const td = document.createElement('td');
     const span = document.createElement('span');
     span.className = 'worked-before-mark';
     span.textContent = checked ? '✓' : ''; // ✓
     td.appendChild(span);
     return td;
   }
   ```
   Keep the JSDoc comment accurate (it currently says "readonly (disabled) checkbox cell" —
   update to describe the span). No click/change handler, same as before — a `<span>` has nothing
   to disable.

2. **`web/css/app.css`** — find the block added for this feature (search
   `qso-confirmation capability` or `nth-child(7)`). Two rules exist there:
   - The narrow-column width/padding/centring rule (`th:nth-child(7/8/9)`,
     `td:nth-child(7/8/9)` — width/padding/text-align). **Keep this as-is**, it's unaffected.
   - The checkbox-specific rule (`td:nth-child(7/8/9) input[type="checkbox"]` — `margin`,
     `accent-color`, `cursor`) and its explanatory comment about disabled-checkbox rendering.
     **Remove both** and replace with a rule for the new glyph, e.g.:
     ```css
     #decodes-table .worked-before-mark {
       color: var(--color-success);
       font-weight: 600;
     }
     ```
     `--color-success` (`#3fb950`) is already defined at the top of this file and already used
     elsewhere for a positive-state indicator (the Call-CQ button, `#ws-state.connected::before`)
     — reuse it, don't introduce a new colour value.

3. **Re-verify visually.** Start the daemon from the repo root as before (real `ADIF.log` is
   still in place) and confirm: checkmarks are clearly legible against the dark background for
   all three columns, empty cells don't visually misalign the narrow column width/centring, and
   a row with a mix of true/false across P/C/R reads unambiguously at a glance. A screenshot
   following the existing convention
   (`dev-tasks/screenshots/adif-qso-confirmation-01-decode-table-columns.png` was the prior one —
   a new one, e.g. `-02-checkmark-indicators.png`, would be useful for the record but isn't
   mandatory if you're confident from direct observation).

4. This is a rendering-only change — no backend payload shape changed, no new C# code. Still,
   run `dotnet build OpenWSFZ.slnx` and `dotnet test OpenWSFZ.slnx --no-build` to confirm zero
   regressions (expect the same 941/941 as before — nothing here touches tested code paths), and
   re-run `openspec validate --strict adif-qso-confirmation` (already confirmed passing after
   QA's spec edits, but re-check after your own changes).

5. Mark tasks.md §5 (5.1–5.5) `[x]` as you complete each one.

## 3. What NOT to change

- Nothing in `src/` — this is a pure frontend rendering change. The `WorkedBefore` payload field,
  `DecodeResult`, `Ft8Decoder`, `AdifLogWriter`, `WorkedBeforeIndex` are all already reviewed and
  approved; do not touch them.
- `web/index.html` — the `<th>` markup, `title` attributes, and `colspan="9"` placeholder row are
  unchanged; only the *cell content* rendering in `main.js` and its CSS change.
- Do not modify the repo's real `ADIF.log`.

## 4. QA re-review

Once §5 is complete, QA will re-check: the checkmark renders correctly for true/false/absent
`workedBefore` sub-fields, the empty-string case doesn't leave a stray text node or layout shift,
`--color-success` is reused rather than a new hardcoded colour, and the full test suite still
passes. Please hold the merge for that pass rather than proceeding once CI is green.

## 5. References

- `openspec/changes/adif-qso-confirmation/design.md` — Decision 7 (new, documents this
  correction and its rationale).
- `openspec/changes/adif-qso-confirmation/specs/web-frontend/spec.md` — updated requirement and
  scenarios (span/checkmark, not checkbox).
- `openspec/changes/adif-qso-confirmation/tasks.md` §5 — the concrete task breakdown mirrored
  above.
- `web/js/main.js` — `makeWorkedBeforeCell` (~line 368), `handleDecodes()` (~line 419-427).
- `web/css/app.css` — the `qso-confirmation capability` comment block (~line 366 onward).
