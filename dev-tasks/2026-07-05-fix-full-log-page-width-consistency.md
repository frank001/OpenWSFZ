# DEV TASK — Full-log page (logs.html) still wraps despite the Logs-tab width fix

**Date:** 2026-07-05
**QA defect ID:** N/A — follow-up gap found during QA review of
`fix/settings-panel-width` (commit `630f499`), not a fresh Captain report.
**Severity:** Minor/Cosmetic — no functional defect; the full-log page renders and fetches
correctly, it is just harder to scan than it now needs to be, and inconsistent with the sibling
page it's one click away from.
**OpenSpec change:** None. Same class of CSS-only layout fix as
`dev-tasks/2026-07-05-settings-logs-tab-panel-too-narrow.md`; a dev-task is sufficient per
house rule (HK-000).
**Branch:** cut a new branch off current `main` (e.g. `fix/full-log-page-width`)

---

## 1. Context

QA reviewed `fix/settings-panel-width` (commit `630f499`), which widened the Settings → Logs
tab's container from 520px to 900px (while active) so the daemon's monospace log lines wrap at
most once instead of two or three times. That fix was approved and is sound for what it covers.

While tracing the CSS, QA noticed `web/logs.html` — the standalone "full log" page, opened via
the **Open full log in new tab** button that sits directly above the log tail on the Logs tab —
reuses the exact same shared container IDs:

```html
<!-- web/logs.html -->
<header id="settings-page">
  ...
</header>
<main id="settings-main">
  <pre id="logs-full-output" class="logs-full-page">Loading…</pre>
</main>
```

It renders the same style of long daemon log lines (`.logs-full-page`, `app.css` lines
976–984 — same monospace font, same `pre-wrap`/`break-word` wrapping behaviour as the tail
viewer's `.logs-tail-output`), and per its own description shows the *complete* log file, so if
anything it has more lines to scan than the 150-line tail.

However, the widening added in `630f499` only fires conditionally:

```css
/* web/css/app.css, lines 482–491 */
body:has(#tab-logs.active) #settings-page,
body:has(#tab-logs.active) #settings-main {
  max-width: 900px;
}
```

`logs.html` has no `#tab-logs` element anywhere on the page (it has no tab bar at all — it's a
single-purpose page), so this rule never matches there. `logs.html` only inherits the base
520px → 700px bump that now applies to every page sharing `#settings-page`/`#settings-main`.
The net effect: an operator who finds the Logs tab's tail comfortably wide, clicks **Open full
log in new tab** expecting the same or better readability, and lands on a page that's
narrower (700px, not 900px) despite showing more log content. This was out of scope for the
original dev-task (which named only `settings.html` in its references) and is not a regression
introduced by `630f499` — the full-log page was already on the shared 520px container before
that fix and nobody had revisited it either. It's a pre-existing gap that fixing the Logs tab
just made more noticeable by contrast.

---

## 2. Actions

### 2.1 — Widen the full-log page's container

Give `web/logs.html` the same ~900px-class treatment the Logs tab now gets, using whichever of
these fits the codebase best (QA is not prescribing the mechanism):

- Simplest, and consistent with the pattern `630f499` just introduced: add a `:has()` rule
  keyed off an element unique to this page, e.g.
  `body:has(#logs-full-output) #settings-page, body:has(#logs-full-output) #settings-main { max-width: 900px; }`
  — no HTML changes required, mirrors the existing Logs-tab rule exactly.
- Alternative: since `logs.html` is a single-purpose page (unlike `settings.html`'s six-tab
  container), it may be simpler and clearer to stop sharing `#settings-page`/`#settings-main`
  with the tabbed settings page altogether and give it its own id/class with a fixed wider
  `max-width` — check which reads better against the rest of `app.css`'s conventions before
  choosing this over the smaller `:has()` addition above.

### 2.2 — Don't regress the small-viewport case

Confirm the wider full-log page still degrades gracefully in a narrow window (no horizontal
clip/overflow) — same check as AC-4 in the original dev-task, same expected outcome (the page
has no tab bar to wrap, just the `<pre>` block, which already wraps its own content).

---

## 3. Acceptance criteria

- [ ] **AC-1** `web/logs.html`, opened via **Open full log in new tab** from the Settings →
  Logs tab, renders at the same (or greater) width as the Logs tab's tail viewer — a
  representative daemon log line wraps at most once, not two or three times, at a normal
  desktop browser window size.
- [ ] **AC-2** The other pages sharing `#settings-page`/`#settings-main` (i.e. `settings.html`'s
  five short-form tabs) are unaffected by this change — confirm no width regression there.
- [ ] **AC-3** Narrow-viewport behaviour for `logs.html` does not clip or horizontally overflow
  — confirmed by manual resize test.
- [ ] **AC-4** No JS/behavioural regression: `logs.js`'s single fetch-on-load behaviour is
  unchanged — this is expected to be a CSS-only fix; flag back to QA if it turns out not to be.
- [ ] **AC-5** Manual before/after screenshots of `logs.html` attached to the PR.

---

## 4. References

- `web/logs.html` (full page, 33 lines) — shares `#settings-page`/`#settings-main` with
  `web/settings.html` but has no tab bar and no `#tab-logs` element.
- `web/css/app.css` lines 470–491 (`#settings-page`/`#settings-main` base + Logs-tab-conditional
  `:has()` override — added by `630f499`), lines 976–984 (`.logs-full-page`).
- `dev-tasks/2026-07-05-settings-logs-tab-panel-too-narrow.md` — the original Logs-tab width
  fix this follows up on.
- QA review of `fix/settings-panel-width` (commit `630f499`), 2026-07-05 — noted this as a
  non-blocking observation on that PR before drafting this follow-up task.
