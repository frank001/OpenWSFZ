# Developer Briefing — Settings: Dirty-State Tracking & Navigation Guard

**Date:** 2026-06-03
**Branch:** `feat/p18-settings-dirty-state` (suggested; adjust to project convention)
**Requirements:** FR-040, FR-041
**Status:** Ready for implementation

---

## 1. Overview

This change adds two closely related behaviours to the Settings page.

| Req    | Summary                                                                         |
|--------|---------------------------------------------------------------------------------|
| FR-040 | Unsaved-changes visual indicator — form footer shows a badge when the form is dirty |
| FR-041 | Navigation guard — operator is warned before leaving the page with unsaved changes |

**No backend changes are required.** All work is confined to the frontend:
`web/js/settings.js`, `web/css/app.css`, and `web/settings.html`.

---

## 2. Clarification: Tab-Switch State Retention

The current tab implementation (FR-035, shipped in p17) is **CSS-based**: all three
tab panels exist in the DOM simultaneously; only the active panel is shown via
`display: block`, the others via `display: none`. This means every form field value
is preserved automatically when the operator switches between the Radio hardware,
Logging, and Advanced tabs — the elements and their state never leave the DOM.

**No additional code is needed for within-page tab-switch retention.** The
developer should confirm this behaviour is working correctly during manual
verification but does not need to implement anything new for it.

What the operator currently loses is state when they navigate *away* from the
Settings page (to `/ `) and then return — the page performs a fresh load from the
API and any uncommitted edits are discarded. FR-041 addresses this by warning the
operator before they can accidentally discard their work.

---

## 3. Requirements

### FR-040 — Unsaved-changes visual indicator

Whenever any form field value differs from the value it held immediately after
the page finished loading (the *clean baseline*), a visible indicator SHALL appear
in the form footer. The indicator SHALL disappear:

- immediately after a successful Save; and
- if the operator manually restores every field to its baseline value.

The indicator SHALL be visible regardless of which tab is currently active.

### FR-041 — Navigation guard

When the form is dirty (FR-040), navigating away from the Settings page SHALL
present the operator with a confirmation step before proceeding. Two navigation
paths must be guarded:

1. **"← Back to main" breadcrumb link** — intercept the anchor click and show a
   `confirm()` dialog: *"You have unsaved changes. Leave without saving?"*. If the
   operator confirms, navigate. If they cancel, remain on the page.

2. **Browser-level navigation** (back button, tab close, address-bar entry,
   page refresh) — register a `beforeunload` handler that calls
   `event.preventDefault()` when the form is dirty. Modern browsers will display
   their built-in "Leave site?" dialog; custom message text is not supported and
   must not be set.

The `beforeunload` handler **SHALL be removed** (or made a no-op) as soon as the
form becomes clean. Do not leave it permanently registered — it will otherwise
fire on every navigation even after a successful save.

---

## 4. Implementation

### 4.1 Clean baseline snapshot

The snapshot is a serialized representation of all form values at the moment the
page finishes loading. It is used to determine whether the current state is dirty.

Add the following near the top of `settings.js` alongside the other module-level
declarations:

```js
/** JSON string of form values captured immediately after a successful page load.
 *  Compared against the current form state to determine the dirty flag.
 *  @type {string}
 */
let _cleanSnapshot = '';
```

Add a `collectFormValues()` function that returns a plain object whose shape
exactly matches the object passed to `postConfig()` in the Save handler — this
ensures the comparison is apples-to-apples. Place it below the existing helpers,
before the Save handler:

```js
/**
 * Serialise all editable form fields into the same shape as the postConfig
 * payload.  Used for dirty-state detection; NOT used for the actual save
 * (the save handler remains the authoritative source to avoid duplication).
 *
 * @returns {string}  JSON string of the current form values.
 */
function snapshotForm() {
  return JSON.stringify({
    audioDeviceId:        deviceSelect.value.trim() || null,
    port:                 portInput.value,
    showCycleCountdown:   cycleCountdownToggle.checked,
    logLevel:             logLevelSelect.value,
    decodeLog: {
      enabled:            decodeLogEnabled.checked,
      path:               decodeLogPath.value.trim(),
      dialFrequencyMHz:   decodeLogDialFreq.value,
    },
    logging: {
      fileEnabled:        loggingFileEnabled.checked,
      directory:          loggingDirectory.value.trim(),
      fileLogLevel:       loggingFileLogLevel.value,
      rotationSchedule:   loggingSchedule.value,
      rotationTime:       loggingTime.value,
      rotationDayOfWeek:  loggingDay.value,
      maxFiles:           loggingMaxFiles.value,
    },
    cat: {
      enabled:            catEnabled.checked,
      rigModel:           catRigModel.value,
      serialPort:         catSerialPort.value.trim(),
      baudRate:           catBaudRate.value,
      rigctldHost:        catRigctldHost.value.trim(),
      rigctldPort:        catRigctldPort.value,
      pollIntervalSeconds: catPollInterval.value,
    },
  });
}
```

> **Note:** `catOpaqueFields` (e.g. `lastPolledFrequencyMHz`) is intentionally
> excluded from the snapshot — it is server-managed and the operator cannot edit
> it, so it cannot contribute to dirtiness.

### 4.2 Dirty-state engine

Add the following after the `snapshotForm` function:

```js
// ── Dirty-state tracking (FR-040) ────────────────────────────────────────

const unsavedBadge = /** @type {HTMLElement} */ (document.getElementById('unsaved-badge'));

function isDirty() {
  return snapshotForm() !== _cleanSnapshot;
}

function syncDirtyUI() {
  const dirty = isDirty();
  unsavedBadge.hidden = !dirty;

  // Guard: add/remove beforeunload only as needed to avoid stale listeners.
  if (dirty) {
    window.addEventListener('beforeunload', onBeforeUnload);
  } else {
    window.removeEventListener('beforeunload', onBeforeUnload);
  }
}

function onBeforeUnload(event) {
  event.preventDefault();
  // event.returnValue must be set for legacy Chromium compatibility.
  event.returnValue = '';
}
```

Register form-level event delegation **once**, in module scope (outside
`DOMContentLoaded`), so it captures events from dynamically-shown/hidden fields:

```js
document.getElementById('settings-form').addEventListener('input',  syncDirtyUI);
document.getElementById('settings-form').addEventListener('change', syncDirtyUI);
```

> Using `input` in addition to `change` ensures that text-input edits are caught
> character-by-character, giving the operator immediate feedback rather than only
> on field blur.

### 4.3 Capture the clean baseline

At the very end of the `DOMContentLoaded` success path, after all fields have
been populated and all init helpers have been called, add:

```js
// Capture the clean baseline after all fields are populated.
_cleanSnapshot = snapshotForm();
```

This must be the last statement in the `try` block of the `DOMContentLoaded`
handler (i.e. after `updateDialFreqLock()`, `loadSerialPorts()`, etc.) so the
snapshot reflects the fully-initialised form state.

### 4.4 Reset the baseline after a successful save

In the `saveBtn` click handler, after the `showFeedback('Saved ✓', 'success')`
line, add:

```js
_cleanSnapshot = snapshotForm();
syncDirtyUI();          // clears the badge and removes the beforeunload guard
```

This ensures a successful save becomes the new clean baseline. If the operator
edits fields after saving, the dirty state will resume correctly.

### 4.5 Navigation guard — breadcrumb link (FR-041)

The breadcrumb anchor is `<a href="/">← Back to main</a>` in `settings.html`.
Add an `id` to it so it can be referenced without a fragile DOM query:

```html
<!-- Before -->
<a href="/">← Back to main</a>

<!-- After -->
<a id="back-link" href="/">← Back to main</a>
```

In `settings.js`, add the element reference near the other declarations at the
top of the file:

```js
const backLink = /** @type {HTMLAnchorElement} */ (document.getElementById('back-link'));
```

Register the guard in module scope (no need to wait for `DOMContentLoaded` — the
element is already in the DOM when the script is parsed as a module):

```js
// ── Breadcrumb navigation guard (FR-041) ─────────────────────────────────

backLink.addEventListener('click', event => {
  if (isDirty()) {
    const confirmed = window.confirm(
      'You have unsaved changes. Leave without saving?'
    );
    if (confirmed) {
      // Stand down the beforeunload guard — the operator has already confirmed
      // intent to discard. Without this, the browser fires beforeunload as part
      // of the navigation and produces a second, redundant prompt.
      window.removeEventListener('beforeunload', onBeforeUnload);
    } else {
      event.preventDefault();
    }
  }
});
```

---

## 5. HTML Changes (`web/settings.html`)

Two small changes are needed.

**Change 1 — Add `id` to the breadcrumb link** (see §4.5 above):

```html
<a id="back-link" href="/">← Back to main</a>
```

**Change 2 — Add the unsaved-badge element** to the `.form-footer`:

```html
<div class="form-footer">
  <button id="save-btn" type="button" class="primary">Save</button>
  <span id="unsaved-badge" hidden>Unsaved changes</span>
  <p id="feedback" aria-live="polite"></p>
</div>
```

The `hidden` attribute provides the initial off state without JavaScript.
The badge is toggled programmatically via `unsavedBadge.hidden`.

---

## 6. CSS Changes (`web/css/app.css`)

Add the following rule in the settings-specific block, near the existing
`#feedback` rules:

```css
/* FR-040: Unsaved-changes indicator */
#unsaved-badge {
  font-size: 0.85rem;
  color: var(--color-warning, #d4a017);
  font-style: italic;
}
```

> If `--color-warning` is not yet defined in the CSS custom properties block,
> add it there with an appropriate amber value (e.g. `#d4a017` for the dark
> theme). If the project already has an amber/warning token under a different
> name, use that instead.

---

## 7. Testing Requirements

### 7.1 Manual verification checklist

These are the acceptance criteria for this change. The developer SHALL verify
each item manually before raising the PR.

**Dirty-state indicator (FR-040)**

- [ ] The "Unsaved changes" badge is **not visible** immediately after page load.
- [ ] Changing any field on the **Radio hardware** tab causes the badge to appear.
- [ ] Switching to the **Logging** tab does **not** clear the badge (it persists across tabs).
- [ ] Changing any field on the **Logging** tab causes the badge to appear.
- [ ] Changing any field on the **Advanced** tab causes the badge to appear.
- [ ] Manually restoring a changed field to its original value causes the badge to disappear
  (provided no other field remains changed).
- [ ] Clicking **Save** causes the badge to disappear immediately on success.
- [ ] After a failed save (e.g. network error), the badge remains visible.
- [ ] After a successful save, changing a field again causes the badge to reappear.

**Navigation guard — breadcrumb link (FR-041)**

- [ ] With a clean form, clicking "← Back to main" navigates immediately with **no dialog**.
- [ ] With a dirty form, clicking "← Back to main" shows a confirm dialog.
- [ ] Clicking **Cancel** in the dialog remains on the Settings page with all field values intact.
- [ ] Clicking **OK** (or equivalent) navigates to the main page.

**Navigation guard — browser-level (FR-041)**

- [ ] With a clean form, pressing the browser back button or pressing F5 produces **no dialog**.
- [ ] With a dirty form, pressing the browser back button triggers the browser's built-in
  "Leave site?" or "Reload site?" prompt.
- [ ] With a dirty form, closing the browser tab triggers the browser's built-in "Leave site?" prompt.
- [ ] After a successful save, browser-level navigation proceeds without a prompt.

**Edge cases**

- [ ] The page loads with CAT enabled and `cat-serial-port` populated via `loadSerialPorts()`;
  no spurious dirty state is triggered by the asynchronous population of the port dropdown.
  *(The `loadSerialPorts()` function modifies `catSerialPort.innerHTML` and
  `catSerialPort.value` programmatically — these changes fire `input`/`change` events.
  See §8.1 for the required fix.)*
- [ ] Toggling the "Enable CAT frequency polling" checkbox (which disables/re-enables the
  dial frequency input via `updateDialFreqLock`) does not cause a spurious dirty state
  when the checkbox was not actually changed by the operator.

---

## 8. Edge Cases & Known Risks

### 8.1 Spurious dirty state from `loadSerialPorts()`

`loadSerialPorts()` programmatically replaces the content of `#cat-serial-port`
and sets `catSerialPort.value`. Depending on the browser, programmatic changes to
a `<select>` element **may or may not** fire `change` events. If they do, the
`syncDirtyUI` listener will fire and compare the new port value against the
snapshot — which already contains the pre-load placeholder — and report the form
as dirty even though the operator has changed nothing.

**Fix:** Capture the clean baseline *after* `loadSerialPorts()` completes, not
before. Since `loadSerialPorts()` is async, the safe approach is to call
`snapshotForm()` inside `loadSerialPorts()` once the port list is stable, or to
defer the baseline capture to a `Promise.allSettled` wrapper:

```js
// Replace the last line of the DOMContentLoaded try block:
// Old:
_cleanSnapshot = snapshotForm();

// New:
// Delay baseline capture until serial port population is complete, so the
// programmatic DOM update does not trigger a false dirty state.
if (catRigModel.value === 'SerialCat') {
  await loadSerialPorts();
}
_cleanSnapshot = snapshotForm();
```

This requires `loadSerialPorts()` to not already be called earlier in the block.
Consolidate the existing `if (catRigModel.value === 'SerialCat') { loadSerialPorts(); }`
call (currently at the end of `DOMContentLoaded`) into this single awaited call.

> **Important:** Remove the original unawaited `loadSerialPorts()` call that
> already exists at the bottom of the `DOMContentLoaded` block to avoid calling
> it twice.

### 8.2 `confirm()` is synchronous and blocking

`window.confirm()` blocks the browser's event loop until the operator responds.
This is the correct, idiomatic choice for a navigation guard. Async alternatives
(custom modal dialogs) are not required by this change and add unnecessary
complexity for a safety-net use case.

### 8.3 `beforeunload` custom message text

All modern browsers (Chrome 51+, Firefox 44+, Safari 9.1+) ignore custom message
strings in `beforeunload` handlers for security reasons. Do **not** attempt to set
`event.returnValue` to a custom string — it will be silently discarded. The
browser's built-in "Leave site?" message is the only supported behaviour.
`event.returnValue = ''` is set solely for legacy Chromium compatibility
(see §4.2).

### 8.4 Form re-population after save

`postConfig` returns the saved config object. The current Save handler does not
re-populate the form fields from the response — it re-reads the values that are
already in the DOM. The new `_cleanSnapshot = snapshotForm()` baseline capture
after save is therefore consistent: it snapshots the DOM values that were just
sent, which matches what the server accepted.

---

## 9. Suggested Implementation Order

1. **`web/settings.html`** — add `id="back-link"` and `id="unsaved-badge"`.
2. **`web/css/app.css`** — add `#unsaved-badge` rule (and `--color-warning` token
   if absent).
3. **`web/js/settings.js`** — in order:
   a. Add `unsavedBadge` element reference.
   b. Add `backLink` element reference.
   c. Add `snapshotForm()` function.
   d. Add `isDirty()`, `syncDirtyUI()`, `onBeforeUnload()` functions.
   e. Register form-level `input`/`change` delegation.
   f. Register breadcrumb click guard.
   g. Update `DOMContentLoaded` — await `loadSerialPorts()` inline (§8.1),
      then call `_cleanSnapshot = snapshotForm()` as the final statement.
   h. Update Save handler — add `_cleanSnapshot = snapshotForm(); syncDirtyUI()`
      after a successful save.
4. **Manual verification** — work through the full checklist in §7.1.
5. **Raise PR** against `main`.

---

## 10. Requirements Record

The following entries SHALL be added to `REQUIREMENTS.md` §4.1 before the PR is
merged:

| ID     | Feature                                  | Description                                                                                                                                                                                                                                                                                                                                                                                 | Priority  |
|--------|------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|
| FR-040 | Settings unsaved-changes indicator       | When any Settings page field value differs from the value it held immediately after the page finished loading, a visible "Unsaved changes" indicator SHALL appear in the form footer. The indicator SHALL disappear after a successful Save and if the operator manually restores all fields to their loaded values. The indicator SHALL be visible regardless of which tab is active. The dirty state SHALL be computed by comparing a JSON snapshot of all editable form values taken after page-load completion against the current form state; server-managed fields not exposed in the UI (e.g. `lastPolledFrequencyMHz`) SHALL be excluded from the comparison. | Must Have |
| FR-041 | Settings navigation guard                | When the Settings form is dirty (FR-040), navigating away from the page SHALL prompt the operator before proceeding. Two paths SHALL be guarded: **(1)** the breadcrumb "← Back to main" anchor — a `confirm()` dialog SHALL ask *"You have unsaved changes. Leave without saving?"*; if the operator cancels, navigation is suppressed; **(2)** browser-level navigation (back button, tab close, page refresh) — a `beforeunload` handler SHALL call `event.preventDefault()` to trigger the browser's built-in leave-site prompt. The `beforeunload` handler SHALL be attached only when the form is dirty and removed immediately when it becomes clean, to prevent stale listeners intercepting navigation after a successful save. | Must Have |

---

*This briefing introduces no changes to the backend API, configuration schema,
or test projects. All changes are confined to the three frontend files listed in
§9. No existing FR or NFR is superseded.*
