# DEV TASK — TX-button live colour verification (redo) + settings tab-bar wrap (real root cause)

**Date:** 2026-07-10
**OpenSpec change:** none — item A is a verification gap on an already-ratified spec
(`tx-state-indicators`), not a spec change. Item B is a pure CSS layout fix; no live spec
governs the settings container's width.
**Branch:** continue on `feat/decode-status-control-merge` (same branch the gui-polish batch
landed on).
**Status:** New. Both items are **redo/regression handoffs** from
`dev-tasks/2026-07-10-gui-polish-batch.md` items 2 and 6, which the Captain re-tested live and
found still broken. Read the "What went wrong last time" note under each item before starting —
it names the specific process gap, not just the specific line to change.

---

## A. `#tx-enable-btn` still shows no visible colour change during real TX

**Captain's report, verbatim evidence:** the daemon log shows a real transmission window —

```
[21:06:15 INF] TX KeyDown — starting playback on device '...'
[21:06:45 INF] TX KeyUp — stopping playback.
```

— (exact timestamps not load-bearing; the Captain flagged afterward that they may have
mis-transcribed them — the point is a real KeyDown-to-KeyUp window exists) and `#tx-enable-btn`
did not visibly turn bright red during it.

**What QA checked this session (static code review only — see below for what's missing):**

Every `TransmitAsync` call site in both services correctly brackets the transmission with a
`SetStateAndNotify(Tx*)` immediately before and `SetStateAndNotify(Wait*/Idle)` immediately
after — this includes the retry path fixed in commit `c5de90e` (this session's item 2) *and* the
original non-retry paths that predate it:

- `QsoAnswererService.cs:725-738` (initial answer), `:809-813` (report), `:822-823` (73),
  `:1040-1048` (retry) — all bracketed.
- `QsoCallerService.cs:533-538` (CQ), `:702-707` (report), `:797-800` (RR73), `:840-843`/`:863-866`
  (retries) — all bracketed.

The frontend (`renderTxPanel` in `web/js/main.js:209-238`) correctly applies `tx-btn-transmitting`
(bright red, `app.css:222-231`) whenever `autoAnswerEnabled && isTransmittingSubState(state)`,
and nothing else in `main.js` touches `txEnableBtnEl.className`. On paper, this is all correct.

**What went wrong last time, and why this redo is different:** commit `c5de90e`'s own message
says outright: *"Live two-radio/VAC verification of the visible button-colour change during a
real retry is still outstanding — no such rig was available in this session; flagging for the
Captain/QA live-verification pass rather than claiming it."* That's an honest disclosure, but it
should not have been sufficient to close out a dev-task item whose own verification section
explicitly demanded a live check. QA also checked: **every one of the 1008 tests in
`OpenWSFZ.Daemon.Tests` mocks `IPttController` via `Substitute.For<IPttController>()`** — none of
them, including the two new tests added for the retry fix, exercise real WASAPI timing,
`WasapiOut.PlaybackStopped` callback latency, or real WebSocket delivery. So the code being
"correct on paper" and "1008/1008 green" together prove nothing about what the Captain actually
saw on screen. Static re-reading will not resolve this a second time — it needs a real
observation.

**Captain's direction (2026-07-10, supersedes the "diagnose the gap" framing below): stop
deriving the colour from the QSO state machine's `state` string at all.** The ground truth already
exists as two concrete, unambiguous events — the same two lines this bug report was raised
against:

- `"TX KeyDown — starting playback on device ..."` (`AudioOnlyPttController.cs:107`)
- `"TX KeyUp — stopping playback."` (`AudioOnlyPttController.cs:128`) **or** the natural-completion
  line `"TX KeyDown — playback completed."` (`:119`) — whichever fires first ends the keyed window.

Track a plain boolean — call it **`Keying`** — that is `true` from the moment `KeyDownAsync` is
entered until the moment it returns (normally, via cancellation, or via a concurrent `KeyUpAsync`
interrupting it), `false` otherwise. Drive `#tx-enable-btn` from `autoAnswerEnabled` and `Keying`
alone, per the Captain's exact rule:

| `autoAnswerEnabled` | `Keying` | Colour |
|---|---|---|
| `false` | (irrelevant) | background/neutral (unchanged) |
| `true` | `true` | bright red |
| `true` | `false` | dark red — this is the default/idle-armed case too: **before the first ever `KeyDownAsync` call in a session, `Keying` starts `false`, so an armed-but-never-yet-transmitted button is dark red**, not unstyled/unknown |

This is simpler than the current `state`-string derivation (no need to enumerate every `Tx*`/
`Wait*`/`Idle` sub-state name) and, more importantly, **structurally closes the whole class of bug
this session has been chasing**: today the correctness of the colour depends on every present and
future `TransmitAsync` call site remembering to bracket itself with `SetStateAndNotify` (six call
sites across two services, one of which — the answerer retry — was already found missing its
bracket once this session). `Keying` instead only needs instrumenting at the **one shared choke
point per service** that already wraps every `KeyDownAsync` call regardless of which QSO sub-state
triggered it: `QsoAnswererService.TransmitAsync` (`:1058`) and `QsoCallerService.TransmitAsync`
(`:872`) — confirmed by this session's `grep` to be the *only* call sites of
`_pttController.KeyDownAsync` in either service. Wrap the existing `await
_pttController.KeyDownAsync(...)` line in each with a `try`/`finally` that publishes `Keying=true`
before entering and `Keying=false` in the `finally` — this cannot be "forgotten" at a future call
site the way six scattered `SetStateAndNotify` brackets can, because there is only one
`KeyDownAsync` call per service to wrap in the first place.

**Suggested plumbing (your call on exact naming/shape, this is the contract, not a mandate):**

1. Add a `Keying` (or similar) boolean to whatever already carries `state`/`role`/`partner` out of
   each service to the web layer — either a new property on `IQsoController`
   (`src/OpenWSFZ.Abstractions/IQsoController.cs`), or a new parameter threaded through
   `ITxEventBus.Publish`/`TxEventBus.Publish` (`src/OpenWSFZ.Web/TxEventBus.cs:45`) and
   `WebSocketHub.BroadcastTxState` (`src/OpenWSFZ.Web/WebSocketHub.cs:492`) alongside the existing
   `state`/`role`/`partner`/`autoAnswerEnabled`/`abortReason` fields. Either way it needs to reach:
   - the `txState` WebSocket payload (so open tabs update live), **and**
   - `GET /api/v1/tx/status`'s `TxStatusResponse` (`WebApp.cs:969`, `AppJsonContext.cs:~125`) (so a
     freshly-loaded or reconnected tab gets the correct current value immediately, not just on the
     next transition).
2. Frontend: `web/js/main.js`'s `renderTxPanel` (`:209-238`) currently gates
   `tx-btn-transmitting` on `autoAnswerEnabled && isTransmittingSubState(state)` — change this to
   `autoAnswerEnabled && keying`, reading the new field from the `txState` WS payload and from the
   `/tx/status` response on initial load. `isTransmittingSubState` (`:124-126`) and its `Tx*`-prefix
   check become dead code for this purpose once this lands — remove it if nothing else uses it, or
   leave a comment if `#tx-call-cq-btn`'s engagement colour (a separate, unrelated requirement)
   still needs it.
3. **Spec sync (required, not optional):** `openspec/specs/tx-state-indicators/spec.md`'s
   Decision 2 (in the archived `f-004-operator-visibility-improvements` change) explicitly says
   the button colour is *"derived entirely from existing `txState` payload fields... with no
   additional server-side signal."* This change deliberately reverses that decision by adding
   exactly such a signal (`Keying`), on the Captain's explicit instruction. Update
   `tx-state-indicators/spec.md`'s requirement text and scenarios to describe the `Keying`-based
   rule instead of the `state`-prefix rule, and note in the requirement's rationale that this
   supersedes Decision 2 (cite this dev-task). Do not leave the ratified spec describing behaviour
   the code no longer implements — that is exactly the kind of drift QA's `openspec validate
   --strict --all` pass and manual spec-sync check exist to catch.
4. Unit tests: add coverage asserting `Keying` flips `true`→`false` around a `TransmitAsync` call
   in both services (mirroring the existing retry-bracket tests added in `c5de90e`, but this time
   for the new signal), **and** a test asserting `Keying` is `false` by construction before any
   transmission has occurred in a fresh service instance (the "armed but idle" default case).

**Live verification is still required — this is a redo of an item that was marked done without
one, not a pass.** This machine has VB-Audio Virtual Cable installed (confirmed by QA this session
— `Get-CimInstance Win32_SoundDevice` shows `VB-Audio Virtual Cable`). Build a live-verification
script following the exact pattern already established in
`qa/decode-filter-synth-verify/live_verify_9_axes.py` (isolated daemon on a scratch port/config
dir via `--port`/`--config`, no need to touch the Captain's real `%APPDATA%\OpenWSFZ\config.json`):

- Start an isolated daemon, `AudioOutputDeviceId` pointed at the VB-Cable input (or leave null for
  the system default — either is fine, this doesn't need to be audible).
- Configure `tx.autoAnswer = true`, a valid callsign/grid, and switch to caller role via
  `POST /api/v1/tx/call-cq` — the simplest real trigger: starts transmitting an actual CQ on the
  next cycle boundary with no decode input required.
- Open a WebSocket client against `/api/v1/ws` and record the wall-clock timestamp and `keying`
  value of every `txState` event received.
- In parallel, capture the daemon's own stdout/log timestamps for the `"TX KeyDown — starting
  playback"` and `"TX KeyDown — playback completed"` / `"TX KeyUp — stopping playback"` lines.
- **The proof QA needs to see:** `keying: true` arrives at or before the `TX KeyDown — starting
  playback` log line, and `keying: false` arrives at or after the matching completion/`KeyUp` log
  line, for at least one real transmission. Include the actual timestamp table in your completion
  notes.
- Also rule out the boring explanation while you're at it: confirm the daemon under test was
  actually rebuilt after this change landed (note process-start time vs. binary last-write time).

Do **not** hand this back with "outstanding, flagging for QA" a second time. If you genuinely
cannot get the live rig working, say so explicitly and stop — do not mark the item done.

---

## B. Settings tab bar still wraps on 5 of 7 tabs — real root cause found

**Captain's report:** "Logs" and "Region data" tabs don't wrap; General/Radio hardware/Logging/
Advanced/Frequencies still do, and the ask is to stop hand-picking which tabs get more room and
instead let the layout use whatever space the browser actually has.

**What went wrong last time:** commit `38e01d5` (gui-polish item 6) diagnosed the wrapping as
belonging to the `.logs-tail-output` content box inside the Region-data tab panel, and fixed
*that* correctly — but that was never the Captain's actual complaint surface. The real defect is
one level up, in the **tab button bar itself**:

- `web/settings.html:28-56` — there are now **seven** tab buttons (General, Radio hardware,
  Logging, Advanced, Frequencies, Logs, Region data). Region data was added by F-006
  (2026-07-07); Logs and General/etc. predate it.
- `web/css/app.css:810-813` — `.settings-tabs { display: flex; flex-wrap: wrap; }` — the button
  row wraps onto a second line whenever it doesn't fit the container.
- `web/css/app.css:658-667` — `#settings-page`/`#settings-main` default to `max-width: 700px`.
  The code comment directly above it (`app.css:659-661`) still says *"Base width covers the
  6-tab bar... on one unwrapped row"* — it was never updated to seven tabs when Region data was
  added, and 700px was evidently sized for six.
- `app.css:677-682` widens the container to 900px, but **only** via
  `body:has(#tab-logs.active)` / `body:has(#tab-region-data.active)` — i.e. only when one of
  those two specific tab panels is the active one. So: Logs/Region-data active → 900px → seven
  buttons fit on one row, no wrap. Any of the other five tabs active → 700px → the same
  seven-button row no longer fits and wraps. This matches the Captain's report exactly.

The previous fix and this one are not in conflict — `app.css:677-682`'s widening for the
`.logs-tail-output` content box inside Logs/Region-data is still correct and should stay; it's
the *tab-conditional* mechanism itself, applied to the whole page width, that's the wrong
approach and needs to go.

**Fix:** stop tying `#settings-page`/`#settings-main` width to which tab is active. Give it one
width, always, generous enough that the seven-button bar never wraps on a normal desktop window,
using the existing `min(px, vw)` idiom already established elsewhere in this file
(`app.css:1068`, the QSO log dialog: `width: min(520px, 95vw)`) so it still shrinks gracefully on
a narrow viewport instead of overflowing:

```css
#settings-page,
#settings-main {
  max-width: min(900px, 94vw);
  margin: 0 auto;
  padding: 0 1rem;
}
```

Then **delete** the three `body:has(...)` conditional blocks at `app.css:677-693` entirely (the
`#tab-logs.active` / `#tab-region-data.active` / `#logs-full-output` variants) — they become
dead code once the container is unconditionally wide enough. Update or remove the stale
"6-tab bar" comment at `app.css:659-661` to describe the new unconditional rule instead. Confirm
the 700px-vs-900px distinction in the original comment (short-form tabs' inputs looking
"stretched" at the wider column) doesn't actually manifest — spot-check General/Radio
hardware/Logging visually at 900px before/after; if fields genuinely look bad stretched that
wide, that's a real trade-off to flag back to the Captain rather than silently reverting to a
narrower width, since it directly contradicts what's being asked for here.

**Verification (follow HK-005 ordering — screenshot-before task first, then implement, then
screenshot-after):**
1. Before: screenshot the tab bar on General (or any narrow-tab) with the current code, showing
   the wrap.
2. Implement the fix above.
3. After: screenshot all seven tabs (or at minimum General, Logging, and Region data as
   representative samples) at a normal desktop window width, confirming the tab bar renders on
   one unwrapped row on every one of them, and confirming Logs/Region-data's wide monospace
   content still isn't cramped.
4. Also check a narrower window (e.g. ~800px) to confirm `94vw` still lets the container shrink
   sensibly rather than overflowing the viewport.

---

## What NOT to change

- `app.css:677-682`'s original purpose (widening `.logs-tail-output`'s effective column) is
  superseded by giving the whole settings container one generous width — don't try to preserve
  the conditional mechanism alongside the new unconditional rule; that would just leave two
  competing width rules.
- Item A: the six existing `SetStateAndNotify(Tx*/Wait*)` brackets across both services stay
  exactly as they are — they still drive `state`/`role`/`partner` for the TX panel's message-row
  display and `#tx-call-cq-btn`'s engagement colour, neither of which is in scope here. `Keying` is
  an *additional*, independent signal layered in via the two `TransmitAsync` methods only — this
  task is not a rewrite of the state machine's broadcast logic, just a new orthogonal boolean for
  `#tx-enable-btn`'s colour specifically.

## Re-verification before handing back

1. `dotnet build OpenWSFZ.slnx -c Release` / `dotnet test OpenWSFZ.slnx -c Release --no-build` —
   expect unchanged pass count (neither item touches existing test-covered logic; item A may add
   a live-verification script that is explicitly *not* part of `OpenWSFZ.slnx`, following the
   `qa/decode-filter-synth-verify` precedent of being manually run, not CI-collected).
2. `openspec validate --strict --all` — expect unchanged pass count.
3. Item A: the real timestamp-correlation evidence described above — not a mock-level test, not a
   restated claim.
4. Item B: the four-step screenshot verification above.

## QA re-review

QA will check item A's live-evidence artifact directly (script + captured timestamps/log
excerpts) and item B's screenshots directly. Neither item will be accepted on the strength of a
"should work" narrative alone this time — both items were handed back once already on exactly
that basis.

## References

- `dev-tasks/2026-07-10-gui-polish-batch.md` items 2 and 6 — original (insufficient) attempts.
- `c5de90e` — the retry-bracketing commit whose own message flagged live verification as
  outstanding.
- `qa/decode-filter-synth-verify/live_verify_9_axes.py` — the established pattern for real,
  isolated-daemon, hardware-in-the-loop verification on this machine; item A's live check should
  follow the same shape (isolated scratch daemon, real audio device, real WebSocket client, own
  timestamped report).
- `openspec/specs/tx-state-indicators/spec.md` — governs `#tx-enable-btn`'s colour rule. **Must be
  updated** as part of this task (see item A step 3): the Captain has explicitly directed the
  `Keying`-signal design above, which supersedes this spec's Decision 2 ("no additional
  server-side signal"). This is a deliberate, instructed reversal, not a drift to avoid — update
  the requirement text/scenarios to match, citing this dev-task in the rationale.
