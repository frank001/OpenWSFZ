# DEV TASK — Logs tab tail viewer: show newest lines first

**Date:** 2026-07-05
**QA defect ID:** N/A — UX enhancement requested by the Captain during review of
`fix/settings-panel-width`, not a functional defect.
**Severity:** Minor — enhancement, not a defect. The tail viewer already shows correct content;
this changes display order for readability during live polling.
**OpenSpec change:** None. This is a small, self-contained behavioural tweak to an existing
feature (`log-viewer`, `f-004-operator-visibility-improvements`, already archived); a dev-task
is sufficient per house rule (HK-000) rather than reopening that change.
**Branch:** cut a new branch off current `main` (e.g. `fix/logs-tail-newest-first`)

---

## 1. Context

The Captain asked: *"can you add to reverse the log in the last 150? newest on top."*

Today, `web/js/settings.js` renders the Logs tab's tail viewer oldest-first, exactly as the API
returns it:

```js
// web/js/settings.js, lines 940–957
/**
 * Fetches the last LOGS_TAIL_LINES lines of the active log file and renders them
 * (oldest first, as returned by the API) — but only while the Logs tab is actually
 * the visible tab, so this doesn't poll uselessly in the background on every other tab.
 */
async function refreshLogsTailIfActive() {
  const panel = document.getElementById('tab-logs');
  if (!panel || !panel.classList.contains('active') || !logsTailOutputEl) return;

  try {
    const { lines } = await getLogsTail(LOGS_TAIL_LINES);
    logsTailOutputEl.textContent = (Array.isArray(lines) && lines.length > 0)
      ? lines.join('\n')
      : '(no log content — file logging may be disabled, or no log file exists yet)';
    ...
```

This polls every `LOGS_POLL_INTERVAL_MS` (3000ms, line 938) while the tab is open, and each
poll replaces `textContent` wholesale. QA did not find any `scrollTop`/`scrollIntoView` handling
anywhere in `web/js/` — there is none — so on every 3-second refresh the box's scroll position
is whatever the browser defaults a freshly-replaced `<pre>` to, which in practice means the
newest lines (currently at the bottom) require the operator to keep re-scrolling down after
every poll to see what just happened. Putting the newest line first fixes this at the root: the
default (unscrolled) view is always the freshest content, no manual scrolling needed during
normal use.

This request is scoped to the Logs tab tail viewer only (`web/js/settings.js`). The standalone
full-log page (`web/logs.html` / `web/js/logs.js`) fetches once on load and deliberately does
**not** auto-refresh — that was an explicit design decision (`design.md` Decision 4, referenced
in `logs.js` line 6) specifically to avoid this class of problem there, so it is not in scope
here. If the Captain wants that page reversed too for consistency, say so explicitly and QA
will fold it in or spin up a second task — it is not assumed here.

---

## 2. Actions

### 2.1 — Reverse tail line order client-side

In `refreshLogsTailIfActive` (`web/js/settings.js` line ~950), reverse the `lines` array before
joining, so the most recent log line renders first:

```js
const { lines } = await getLogsTail(LOGS_TAIL_LINES);
logsTailOutputEl.textContent = (Array.isArray(lines) && lines.length > 0)
  ? lines.slice().reverse().join('\n')
  : '(no log content — file logging may be disabled, or no log file exists yet)';
```

(`.slice()` before `.reverse()` avoids mutating whatever array reference `getLogsTail` returns,
in case that matters elsewhere — check whether it does before assuming `.reverse()` in place is
safe.)

This is believed to be a pure client-side change — no API/backend change should be required,
since `getLogsTail` already returns the full set of lines and only display order changes. If
that assumption turns out to be wrong (e.g. the API only returns a stream/generator that can't
be cheaply reversed client-side, or there's a reason the ordering needs to come from the
server), flag it back to QA before proceeding.

### 2.2 — Update the stale doc comment

The function's doc comment (line 942, `"(oldest first, as returned by the API)"`) describes the
current behaviour and will be wrong after this change — update it to describe the new
newest-first rendering, and note that the API itself is unchanged (still returns oldest-first;
the reversal is purely a display-layer concern in this function).

### 2.3 — Sanity-check the "no log content" and error-message paths

Confirm the placeholder text (`'(no log content — ...)'`) and the error path
(`` `Failed to load log tail: ${err.message}` ``, line 955) are unaffected — those are single
strings, not line arrays, so no reversal applies, but confirm nothing upstream assumes line
order when these paths are hit.

---

## 3. Acceptance criteria

- [ ] **AC-1** On the Settings → Logs tab, the most recent log line appears at the top of the
  tail viewer (`#logs-tail-output`), and the oldest of the 150 fetched lines appears at the
  bottom.
- [ ] **AC-2** After the 3-second poll fires and new content arrives, the newest line is still
  visible at the top without the operator needing to scroll — confirmed by manual observation
  over at least two poll cycles while the daemon is producing log output.
- [ ] **AC-3** The full-log page (`web/logs.html`) is unchanged — still renders oldest-first,
  top to bottom, exactly as before — unless the Captain has explicitly asked for it to be
  included, which is not assumed by this task.
- [ ] **AC-4** The "no log content" placeholder and the fetch-error message still render
  correctly (these are not line arrays and should pass through unreversed and unaffected).
- [ ] **AC-5** No regression to the existing 150-line cap, the 3-second poll interval, or the
  "only polls while the Logs tab is the active tab" behaviour (line 947) — this is a display-
  order change only.
- [ ] **AC-6** Manual before/after screenshot (or short description, given this is an ordering
  change rather than a layout change — a static screenshot won't show polling behaviour, so a
  brief written note on AC-2's manual observation is an acceptable substitute for a screenshot
  here) attached to the PR.

---

## 4. References

- `web/js/settings.js` lines 931–979 (`Log viewer` section — `refreshLogsTailIfActive`,
  `LOGS_TAIL_LINES`, `LOGS_POLL_INTERVAL_MS`, tab-open listener).
- `web/js/api.js` lines 362–364 (`getLogsTail` — plain passthrough to
  `GET /api/v1/logs/tail?lines=N`, no ordering logic here).
- `web/js/logs.js` (full page — explicitly out of scope, see Decision 4 reference at line 6).
- `openspec/changes/archive/2026-07-05-f-004-operator-visibility-improvements/` — original
  `log-viewer` feature this tail viewer belongs to.
- Captain's request, verbal, 2026-07-05, during QA review of `fix/settings-panel-width`.
