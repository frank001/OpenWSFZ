# DEV TASK — Settings panel too narrow now the Logs tab has been added

**Date:** 2026-07-05
**QA defect ID:** N/A — no formal defect number assigned yet; UI/UX regression found via
Captain's manual review of the just-shipped Logs tab, not a pre-merge gate (f-004 already
merged and archived)
**Severity:** Minor/Medium — not a functional defect (the log tail itself works, per its own
spec), but it materially hurts the usability of the feature f-004 just shipped: log lines wrap
so heavily they're hard to scan, and the tab bar itself visibly wraps ("Radio hardware" breaks
onto two lines in the reported screenshot)
**OpenSpec change:** `f-004-operator-visibility-improvements` (archived
`openspec/changes/archive/2026-07-05-f-004-operator-visibility-improvements/`) — this is a gap
in that change's delivery, not a new feature. No new OpenSpec change is required for a CSS
layout fix of this size; a dev-task is sufficient per house rule (HK-000).
**Branch:** cut a new branch off current `main` (e.g. `fix/settings-panel-width`)

---

## 1. Context

The Captain reported: *"the settings panel is too small now the logs section has been added"*,
with a screenshot of the Settings → Logs tab showing the tab bar wrapping ("Radio" / "hardware"
on separate lines) and the log tail box rendering very short, heavily-wrapped lines.

QA traced this to a pre-existing constraint that predates f-004 and was never revisited when
the Logs tab was designed:

- `web/css/app.css` lines 471–476:
  ```css
  #settings-page,
  #settings-main {
    max-width: 520px;
    margin: 0 auto;
    padding: 0 1rem;
  }
  ```
  Every settings tab — old and new — is squeezed into a single fixed 520px column. This was a
  reasonable width for short label/input form rows (General, Radio hardware, Logging, Advanced,
  Frequencies), but the Logs tab (`web/settings.html` lines 549–566) has fundamentally different
  content: a monospace log tail (`#logs-tail-output`, `.logs-tail-output` in
  `app.css` lines 937–953) whose lines (`2026-07-05 16:38:47.568 +02:00 [DBG] ...`) are naturally
  ~90–110 characters wide. Inside a ~488px content box at 0.78rem monospace, nearly every line
  wraps two or three times, which is what makes the box in the screenshot look cramped and hard
  to scan even though it already has correct internal scrolling (`max-height: 60vh; overflow-y:
  auto`, lines 940–941).

- `web/css/app.css` lines 593–609 (`.settings-tabs`, `.settings-tab-btn`): the tab bar is a plain
  `display: flex` row with no `flex-wrap` and no `white-space: nowrap` on the button text. With
  six tabs now competing for the same 520px row (up from five before f-004 added "Logs"), the
  longest label ("Radio hardware") wraps inside its own button — visible in the screenshot.

- `openspec/changes/archive/2026-07-05-f-004-operator-visibility-improvements/specs/log-viewer/spec.md`
  and `design.md` were checked: neither specifies anything about settings-panel container width
  or the tab bar's ability to accommodate a sixth tab. This was a genuine gap in that change's
  scope, not a documented trade-off — nobody was asked to sign off on shipping a cramped Logs
  tab.

QA is not prescribing a specific pixel value — that's a design call — but the fix must address
both symptoms (tab bar wrapping, log box being too narrow to read comfortably), not just one.

---

## 2. Actions

### 2.1 — Widen the settings container

Increase `max-width` on `#settings-page`/`#settings-main` (`app.css` lines 471–476) enough that:
- all six tab labels sit on one line without wrapping, at a typical desktop browser width, and
- the log tail box has enough horizontal room that a representative daemon log line no longer
  wraps two or three times over.

A few approaches, in ascending order of effort — pick whichever fits the codebase's existing
patterns best:
- Simplest: bump the fixed `max-width` to something like 760–900px. Cheap, but the short-form
  tabs (General, Logging, etc.) will have more empty space around narrow fields; check that
  doesn't look worse than the cramped version it's replacing.
- Better: keep the short-form tabs at (or near) their current comfortable width, but let the
  Logs tab panel specifically opt into a wider layout (e.g. a modifier class on `#settings-main`
  or `#settings-page` toggled when `tab-logs` is active, alongside the existing
  `.settings-tab-panel.active` show/hide logic at lines 623–629).
- Also acceptable: a responsive width (e.g. `clamp(520px, 60vw, 900px)`) if that fits the rest
  of the app's CSS conventions better than a fixed breakpoint — check `web/css/app.css` for
  existing use of `clamp()`/viewport units elsewhere before introducing a new pattern.

### 2.2 — Fix tab bar wrapping

Whatever the container-width fix ends up being, separately confirm the tab bar
(`.settings-tabs`, `.settings-tab-btn`, lines 593–609) no longer wraps "Radio hardware" (or any
other label) onto two lines at the container's new width. If widening the container alone
doesn't fully resolve it, consider `white-space: nowrap` on `.settings-tab-btn` and/or reducing
horizontal padding slightly (currently `0.5rem 1.2rem`, line 608).

### 2.3 — Don't regress the small-viewport case

`web/settings.html` and `app.css` were not reviewed for a responsive/narrow-window breakpoint
specific to this container (none was found by QA, but please check for one before assuming
there isn't). If the app is ever run in a narrow window (small popup, low-res display), confirm
the wider settings panel still degrades reasonably — e.g. tabs wrap or the panel shrinks
gracefully rather than clipping or overflowing the viewport horizontally.

---

## 3. Acceptance criteria

The QA engineer will verify the following before approving merge:

- [ ] **AC-1** All six settings tab labels (General, Radio hardware, Logging, Advanced,
  Frequencies, Logs) render on a single line, unwrapped, in the tab bar at a normal desktop
  browser window size.
- [ ] **AC-2** On the Logs tab, a representative daemon log line (timestamp + level + message,
  e.g. the sample lines from the reported screenshot) wraps at most once, not two or three
  times, at a normal desktop browser window size.
- [ ] **AC-3** The other five tabs (General, Radio hardware, Logging, Advanced, Frequencies)
  are visually reviewed after the width change and do not look regressed (no awkward stretching,
  no orphaned short rows in an overly wide column). Screenshot comparison before/after.
- [ ] **AC-4** Narrow-viewport behavior (if the app window is resized small) does not clip or
  horizontally overflow — confirmed by manual resize test, not just at default size.
- [ ] **AC-5** No JS/behavioral regression: tab switching (`settings.js`), the "Open full log in
  new tab" button, and the auto-refreshing log tail still function exactly as before — this is
  a CSS-only fix; if it turns out to require JS changes, flag that back to QA before proceeding.
- [ ] **AC-6** Manual before/after screenshots attached to the PR (matching the Captain's
  original report format) so the fix can be visually confirmed without re-running the app.

---

## 4. References

- `web/settings.html` lines 27–53 (tab nav), 549–566 (Logs tab panel), 568–572 (shared form
  footer)
- `web/css/app.css` lines 470–486 (`#settings-page`/`#settings-main` fixed 520px container —
  root cause), 593–609 (`.settings-tabs`/`.settings-tab-btn` — tab bar wrapping), 623–629
  (`.settings-tab-panel`/`.active` show-hide, no per-tab sizing), 937–953 (`.logs-tail-output`
  — internal scroll is fine, box is just too narrow)
- `openspec/changes/archive/2026-07-05-f-004-operator-visibility-improvements/specs/log-viewer/spec.md`
  and `design.md` — confirmed no sizing/layout acceptance criteria were ever specified for the
  Logs tab; this was an oversight in that change's scope, not a deliberate trade-off
- Original report: Captain's screenshot, 2026-07-05, showing the Settings → Logs tab with
  wrapped tab labels and a heavily-wrapped log tail box
