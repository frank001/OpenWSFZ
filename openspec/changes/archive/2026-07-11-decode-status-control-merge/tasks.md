## 1. Markup

- [x] 1.1 In `web/index.html`, remove the `<span id="decode-badge" ...>Decoding</span>` element
      (around line 28). Keep `<button id="decode-toggle" ...>` (line 30) as the sole element;
      update its default/initial text content in the markup to match the new label conventions
      (it will be overwritten on first render regardless, but keep the static markup honest).

## 2. Frontend logic (`web/js/main.js`)

- [x] 2.1 Remove the `decodeBadgeEl` element reference (line 948); keep `decodeToggleEl` (line
      949).
- [x] 2.2 Rewrite `setDecodingState` (the function assigning `decodeBadgeEl`/`decodeToggleEl`
      text/class/disabled around lines 1091–1110) to drive only `decodeToggleEl`, per the three
      states defined in the delta spec's "Combined decode status/toggle control" requirement:
      - No device (`!audioDevice`): `decodeToggleEl.textContent = 'No device'`,
        `decodeToggleEl.disabled = true`, apply the neutral/disabled style (no active/stopped
        class).
      - Active (`enabled === true`, device present): `decodeToggleEl.textContent = 'DECODING'`,
        `decodeToggleEl.disabled = false`, apply the active (bright-green) class.
      - Stopped (`enabled === false`, device present): `decodeToggleEl.textContent = 'Start
        decoding'` (capital S only), `decodeToggleEl.disabled = false`, apply the stopped
        (bright-red) class.
      Reuse `decodingEnabled = enabled;` bookkeeping (line 1091) unchanged — the click handler at
      line 1548 still needs it to pick `/decode/start` vs `/decode/stop`.
- [x] 2.3 Confirm the click handler (`decodeToggleEl.addEventListener('click', ...)`, line 1547)
      and its two callers of `setDecodingState` (line 1563, from the start/stop POST response; line
      1593, from the WebSocket status event) need no logic changes — they already call
      `setDecodingState(enabled, hasDevice)`, which now drives one element instead of two.
- [x] 2.4 Grep `web/js/*.test.js` and any other JS for `decode-badge`, `decodeBadgeEl`,
      `decoding-active`, `decoding-stopped` to confirm nothing else references the removed
      element/classes; update any hits found (none were found during proposal drafting, but
      re-verify — this is a live check, not a rubber stamp).

## 3. Styling (`web/css/app.css`)

- [x] 3.1 Remove the `#decode-badge` rule block and its `.decoding-active`/`.decoding-stopped`
      sub-rules (around `app.css:559`–`578`).
- [x] 3.2 Replace the existing compact `#decode-toggle` sizing rule (`app.css:581`–`584`) with the
      merged control's styling: base button style (compact status-bar sizing, keep the existing
      `padding`/`font-size`), plus two new state classes (name them e.g. `decode-toggle-active` /
      `decode-toggle-stopped`, or reuse `decoding-active`/`decoding-stopped` class names on the
      button itself — developer's choice, but be consistent with naming used elsewhere in this
      file) using `var(--color-success)` for the active/"DECODING" state and
      `var(--color-danger)` for the stopped/"Start decoding" state, matching Decision 2 in
      `design.md` (no new colour values). Keep the disabled/"No device" state using the browser's
      native `:disabled` styling (no colour override), matching Decision 3.
- [x] 3.3 Update the `FR-017` code comment references at `app.css:558` and `app.css:580` (or
      remove them if no longer accurate) to reflect the merged control rather than two separate
      ones.

## 4. Verification

- [x] 4.1 `dotnet build OpenWSFZ.slnx -c Release` / `dotnet test OpenWSFZ.slnx -c Release
      --no-build` — expect unchanged pass count (frontend-only change, no `src/` touched).
      Verified: build 0 warnings/0 errors, full suite 1006/1006 passed.
- [x] 4.2 `openspec validate --strict decode-status-control-merge` — must pass before requesting
      review. Verified: "Change 'decode-status-control-merge' is valid".
- [x] 4.3 Live/manual check in a real browser: toggle decode on/off and confirm the single
      `#decode-toggle` element shows bright-green "DECODING" when active and bright-red "Start
      decoding" when stopped, with correct capitalisation in both (not "Decoding"/"start
      decoding"/"START DECODING" or any other casing variant). Simulate/verify the no-device case
      (or reason through it from the code if no device-less test rig is available) shows "No
      device" and is unclickable.
      Verified live against the running daemon (Playwright, `qa/uat-tmp/decode-toggle-merge-screenshots.mjs`):
      stopped → bright-red bg `rgb(248,81,73)` (= `--color-danger`), text exactly "Start decoding";
      active → bright-green bg (`--color-success` base), text exactly "DECODING"; no-device
      (synthetic `status` frame, `audioDevice: null`) → text "No device", `disabled: true`, no
      colour class applied. **Caught and fixed a real defect in this pass**: the first CSS draft
      (task 3.2) carried over `text-transform: uppercase` from the old badge rule onto the base
      `#decode-toggle` selector, which forced *both* states to render visually all-caps
      ("START DECODING") regardless of `textContent` — exactly the casing-flattening risk called
      out in `design.md` Risk 2. Removed the property (kept `font-weight: 700` only); rebuilt,
      restarted the daemon, and re-verified screenshots show correct sentence-case "Start decoding"
      vs. all-caps "DECODING".
- [x] 4.4 Confirm clicking the control while active calls `/api/v1/decode/stop` and while stopped
      calls `/api/v1/decode/start` (unchanged endpoints) — e.g. via browser devtools network tab.
      Verified via Playwright network capture in the same script: click while stopped →
      `POST /api/v1/decode/start`; click while active → `POST /api/v1/decode/stop`. Both endpoints
      unchanged.
- [x] 4.5 Take a before/after screenshot of the status bar for the QA re-review, following the
      existing `qa/uat-tmp/` naming convention.
      Captured via `git stash` of the three changed files + rebuild/restart to render the genuine
      pre-change UI, then stash-pop + rebuild/restart to return to the merged UI:
      `qa/uat-tmp/decode-toggle-before-OLD-two-element.png` (old: separate green "DECODING" badge
      + adjacent "Stop Decoding" button) vs. `qa/uat-tmp/decode-toggle-after-active.png` /
      `decode-toggle-before-stopped.png` / `decode-toggle-no-device.png` (new: single merged
      `#decode-toggle` control cycling through all three states). Dev box's
      `AppData\Roaming\OpenWSFZ\config.json` `decodingEnabled` restored to its original `false`
      afterward; no daemon process left running.
