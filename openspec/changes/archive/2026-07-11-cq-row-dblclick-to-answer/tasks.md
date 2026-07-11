## 1. Capture pre-fix baseline evidence

- [x] 1.1 Confirmed live against the running daemon (`http://localhost:8080`, still serving the
      pre-fix `main.js` at the time) via `qa/uat-tmp/cq-dblclick-before.mjs` (Playwright, WS-frame
      injection of a synthetic `CQ Q1TST JO22` decode row — no real audio/VAC signal needed). A
      single click fired exactly one `POST /api/v1/tx/answer-cq`. Screenshot:
      `qa/uat-tmp/cq-dblclick-01-before-single-click.png`. TX was immediately aborted afterward
      (`POST /api/v1/tx/abort`) to prevent an unintended real transmission from the test.

## 2. Implementation

- [x] 2.1 In `web/js/main.js`, inside the CQ-row block (`main.js:727`–`764`), remove the
      `tr.addEventListener('click', async () => {...})` listener that currently fires
      `postTxAnswerCq` and replace it with `tr.addEventListener('dblclick', async () => {...})`,
      keeping the handler body (callsign extraction, `postTxAnswerCq` call, `renderTxPanel`,
      error handling) otherwise unchanged.
- [x] 2.2 Keep the existing in-flight guard (`inFlight` boolean, `tr.style.pointerEvents =
      'none'` during the request, the 400 ms post-success `setTimeout` cooldown) exactly as-is,
      just attached to the `dblclick` handler now instead of `click` — per design.md Decision 3,
      this is a retarget, not a rewrite.
- [x] 2.3 Add `event.preventDefault()` at the top of the `dblclick` handler (accept the event
      object as the callback's parameter) to suppress the browser's native double-click
      text-selection behavior on the row (design.md Decision 5), and immediately follow it with
      `window.getSelection()?.removeAllRanges()` to clear whatever the native gesture selected —
      **not** `user-select: none` on `.decode-cq`. An initial pass used `user-select: none` (per
      this task's original wording); QA re-review caught that it silently disabled *all* text
      selection on *every* CQ row permanently (the Captain reported being unable to select/copy a
      callsign), not just during the double-click. Reverted that CSS rule and replaced it with the
      handler-scoped `removeAllRanges()` call — see design.md Decision 5's revision note and task
      4.6 below for the re-verification.
- [x] 2.4 Update the code comment currently citing D-TX-UI-005 ("Delay guard reset to block
      human double-clicks...") to reflect that the guard now protects against a rapid *repeat
      double-click*, not a stray single click following the trigger — the mechanism is unchanged,
      only what it's guarding against needs re-describing accurately.
- [x] 2.5 Confirm `.decode-cq`'s hover/cursor affordance (`tr.style.cursor = 'pointer'` at
      `main.js:730`, `.decode-cq:hover` in `app.css`) is untouched — it must still visually mark
      the row as interactive even though the trigger gesture changed.

## 3. Test updates

**Decision (2026-07-11, Captain sign-off):** this codebase has no DOM-event-simulation test
infrastructure — `main.js` performs 15+ top-level `document.getElementById(...)` calls and isn't
structured for import-and-exercise under `node --test`; there is no jsdom (`web/js/package.json`
states "no npm dependencies" by design); every existing `*.test.js` file
(`decodeFilter.test.js`, `decodeNoiseSuppression.test.js`) tests a pure extracted function, never
DOM wiring. This project's established pattern for verifying DOM/click behavior is live
Playwright-driven QA evidence capture (`qa/uat-tmp/*.mjs`), which is exactly what tasks 1 and 4
already do. Tasks 3.1–3.4 as originally drafted assumed automated DOM-click test coverage that
does not exist and was not added for the pre-existing single-click behavior either. Per Captain's
explicit choice, this change relies on live verification only (tasks 1 and 4) for the
click/dblclick wiring; no new test scaffolding or dependency was introduced.

- [x] 3.1 Searched for any existing frontend test asserting a single click on `.decode-cq` calls
      `postTxAnswerCq` / triggers `POST /api/v1/tx/answer-cq`. **None found** (confirmed via
      repo-wide grep for `decode-cq`, `postTxAnswerCq`, `answer-cq`, `dblclick` across
      `web/js/*.test.js` and `tests/**`) — nothing to update.
- [x] 3.2 **Not added**, per Captain's decision above — no automated unit-test infra exists to
      host this assertion without introducing new scaffolding/dependencies; the negative
      assertion (single click does not arm TX) is instead covered live by task 4.1.
- [x] 3.3 Confirmed via grep: no test under `tests/OpenWSFZ.Web.Tests`, `tests/OpenWSFZ.Daemon.Tests`,
      or elsewhere asserts or depends on single-click arming TX (`TxEndpointTests.cs` and
      `QsoAnswererServiceTests.cs` test the backend endpoint/service directly, independent of
      click cardinality — unaffected by this change).
- [x] 3.4 Confirmed by reading `main.js:791`–`820`: `.decode-responder`'s click-to-select-responder
      handler still uses `tr.addEventListener('click', ...)`, untouched by this change — out of
      scope per design.md's Non-Goals and Open Question 1. Live regression check remains at
      task 4.4.

## 4. Capture post-fix verification evidence

All of 4.1–4.5 run live against `http://localhost:8080` via `qa/uat-tmp/cq-dblclick-after.mjs`
(plus a follow-up re-verify script for 4.3) after hot-copying the fixed `web/js/main.js` /
`web/css/app.css` into the running daemon's served copy
(`src/OpenWSFZ.Daemon/bin/Debug/net10.0/web/`) — no rebuild/restart needed for these pure static
asset changes. TX was aborted (`POST /api/v1/tx/abort`) after every arm/keying observed during
these tests.

- [x] 4.1 Single-clicked the injected `CQ Q1TST JO22` row while `Idle`: **zero**
      `POST /api/v1/tx/answer-cq` requests observed. Screenshot:
      `qa/uat-tmp/cq-dblclick-02-after-single-click.png`.
- [x] 4.2 Double-clicked the same row: exactly **one** `POST /api/v1/tx/answer-cq` fired with
      `{"callsign":"Q1TST","frequencyHz":1500,"cqCycleStartUtc":"2026-07-11T12:00:00Z"}` (server
      log confirms `200`). `renderTxPanel` is called unconditionally on 200 in the (untouched)
      handler body. Screenshot: `qa/uat-tmp/cq-dblclick-03-after-double-click-armed.png`.
- [x] 4.3 First pass: `window.getSelection().toString()` returned `"CQ "` after the dblclick —
      `event.preventDefault()` alone was **not** sufficient, confirming the contingency design.md
      Decision 5 flagged. Applied the `user-select: none` fallback to `.decode-cq` in `app.css`
      (task 2.3) and re-verified via `qa/uat-tmp/cq-dblclick-reverify-selection.mjs`:
      `window.getSelection().toString()` now returns `""`. Screenshot (visually confirms no blue
      selection highlight, contrast with 03 above):
      `qa/uat-tmp/cq-dblclick-06-after-userselect-none-fix.png`.
      **Superseded by task 4.6** — the `user-select: none` fix used here caused a regression
      (caught by the Captain after QA's first review pass), replaced with a handler-scoped fix.
- [x] 4.4 Regression-checked `.decode-responder`'s single-click path live: injected a synthetic
      `txState` WS frame (`role: 'caller', state: 'WaitAnswer'`, `callerPartnerSelect` already
      `'None'` from config) plus a decode row addressed to the operator callsign
      (`PD2FZ/P Q3BAR -05`), then single-clicked the resulting `.decode-responder` row: exactly
      **one** `POST /api/v1/tx/select-responder` fired (server returned `405` since the *backend's*
      own role was never actually switched — expected and irrelevant to this regression check,
      which only verifies the untouched click→request wiring itself is intact). Screenshot:
      `qa/uat-tmp/cq-dblclick-05-after-responder-regression.png`.
- [x] 4.5 Tested by double-clicking a *second*, different CQ row (`CQ Q2FOO JN58`) immediately
      after the first was armed. **Finding, out of scope for this change:** the second
      `answer-cq` POST also returned `200` (not `409`) and silently re-armed/re-targeted the
      pending answer — `GET /api/v1/tx/status` continued reporting `state: "Idle"` for several
      seconds after arming (the `state` field apparently doesn't flip away from `Idle` until the
      FT8 cycle phase actually locks in), so a strict "second request while not-Idle → 409" probe
      wasn't reproducible via synthetic WS injection without real cycle-phase timing. The
      frontend's 409-handling code path itself is unchanged from the pre-existing single-click
      implementation (same `catch` block, same `console.warn`, per design.md Decision 3) so it is
      not a regression introduced by this change. Flagging to the Captain as a pre-existing
      backend characteristic of `QsoAnswererService.AnswerCqAsync` (explicitly out of scope per
      proposal.md's Impact section — "Backend: none") worth a separate look, not fixed here.
- [x] 4.6 **Post-review addendum (2026-07-11).** The Captain reported, after QA's first review
      pass, that hovering/interacting with the decode panel no longer let them select text to
      copy. Reproduced live first (`qa/uat-tmp/cq-dblclick-07-selection-regression-check.png` /
      `.mjs`): a deliberate click-and-drag over a CQ row's message cell returned an empty
      `window.getSelection().toString()` — confirmed the `user-select: none` fix from task 4.3
      blocked *all* selection on CQ rows, not just the double-click's own stray selection (it's an
      inherited property, applied unconditionally on the base `.decode-cq` rule, affecting every
      CQ row at all times). Fixed per design.md Decision 5's revision: removed `user-select: none`
      from `app.css`; the `dblclick` handler now calls `window.getSelection()?.removeAllRanges()`
      immediately after `event.preventDefault()` instead, clearing only the double-click's own
      selection. Re-verified all three properties hold simultaneously in one pass
      (`qa/uat-tmp/cq-dblclick-08-refix-full-reverify.mjs`): (1) double-click still fires exactly
      one `answer-cq` request and arms TX — screenshot `cq-dblclick-08-after-refix-dblclick.png`;
      (2) double-click still leaves no residual selection; (3) an ordinary click-and-drag
      immediately afterward on the same row *does* select and return the row's text — screenshot
      `cq-dblclick-09-after-refix-drag-select.png`, confirming the regression is resolved. Also
      directly probed `getComputedStyle(td).color` and `window.getSelection().rangeCount` before
      and after the double-click (`cq-dblclick-10-investigate-blue-text.mjs`) to rule out any
      residual visual/selection artifact beyond what screenshots alone could show — both confirm a
      clean state (`rangeCount: 0`, unchanged `--color-text` colour).

## 5. Regression & spec validation

- [x] 5.1 `dotnet build OpenWSFZ.slnx -c Release` — 0 warnings, 0 errors. `dotnet test
      OpenWSFZ.slnx -c Release --no-build` — 1031 passed, 0 failed across all suites except
      `OpenWSFZ.E2E.Tests` (2 failures: `FR-002`/`FR-007`, "Daemon did not emit welcome banner on
      stdout within 10 s"). Confirmed via `git stash` that these 2 failures reproduce identically
      on unmodified `main` — pre-existing, unrelated to this change (the E2E harness launches the
      AOT-published binary directly; per project memory this has a known AOT/WASAPI startup
      limitation, distinct from the `dotnet run` deployment model). No regressions introduced; no
      task-3.2 test was added per the Section 3 decision above, so the baseline count is unchanged
      rather than +1.
- [x] 5.2 `openspec validate --strict --all` — **52 passed, 0 failed** (baseline was 51/51 per
      project memory; +1 is this change's own delta spec — exactly the expected "unchanged pass
      count outside this change's own delta spec").
- [x] 5.3 This project maintains no `CHANGELOG.md`/release-notes file (confirmed — none exists
      anywhere in the repo). The operator-facing behavior change is recorded in `proposal.md`'s
      Impact section, which is this project's artifact of record for exactly this purpose; no
      further file to update.

## 6. QA re-review

**First pass (2026-07-11):** QA reviewed the implementation as originally submitted — code diff,
task-by-task cross-check, independent `dotnet build`/`dotnet test`/`openspec validate --strict --all`
re-runs, and direct inspection of the evidence screenshots/scripts. Verdict: approve, with three
cosmetic comment nits and a process point (implementation was sitting uncommitted on local `main`;
moved to its own branch, `feat/cq-row-dblclick-to-answer`, per Captain's direction).

**Regression found post-review, same day:** the Captain, on a follow-up glance, reported being
unable to select/copy text on decode rows — traced to the `user-select: none` fix from task 4.3.
See task 4.6 above for the reproduction, fix, and re-verification. This was not caught by QA's
first-pass review (the three-property live re-check now covered by task 4.6 hadn't been performed
at that point) — noted so the gap in the first review pass is on record, not glossed over.

Before this change is archived: confirm the two cosmetic comment nits and the `.decode-responder`
click parity/discoverability open questions (design.md) are either resolved or explicitly deferred
by the Captain, and confirm the delta spec's four scenarios all pass one more time against the
final committed state (not just the pre-commit working tree).
