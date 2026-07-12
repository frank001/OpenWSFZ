# DEV TASK — Add a Settings-page UI for PTT configuration, with a safe hardware Test button

**Date:** 2026-07-12
**OpenSpec change:** `cat-tx-ptt` — amends design.md Decision 6 ("no new UI") and adds tasks.md
section 17. Both already edited in this branch; this document is the developer handoff, not a
duplicate spec — **read `openspec/changes/cat-tx-ptt/design.md`'s 2026-07-12 amendment to Decision 6
first**, it contains the full safety analysis for the semaphore requirement below, and
`openspec/changes/cat-tx-ptt/tasks.md` section 17 is the authoritative, line-by-line task list.
**Branch:** `feat/cat-tx-ptt`.
**Status:** New. Raised directly by the Captain after the null-`ptt`-guard fix
(`dev-tasks/2026-07-12-cat-tx-ptt-null-ptt-config-guard.md`) landed and hardware acceptance still
couldn't proceed smoothly — there is currently no way to see or change `ptt.method` without
hand-editing `config.json` and fully restarting, which is itself part of why the null-guard defect
went unnoticed for a full session.
**Found by:** Captain, via a hand-annotated screenshot of the Settings → Radio hardware tab
(reproduced below in words since the image isn't reproducible here): split the existing "CAT rig
connection" box into two side-by-side boxes, the new one labelled "PTT Config", with a Test button
and a Pass/Error visual result.
**Severity:** High — blocks efficient continuation of hardware acceptance (gates 14–16), and the
underlying safety finding below (concurrent PTT callers) is a real hazard independent of this UI.

---

## What was decided, and how

Two points here key on live hardware, so I put them to the Captain directly rather than assuming:

1. **What does "Test" verify?** → **Software-only pulse.** Per `IRadioConnection.SetPttAsync`'s own
   doc comment (design.md Decision 2), no implementation ever reads back PTT state — there is no way
   to prove the rig physically keyed. Test asserts PTT briefly (~200–300 ms, silent — no audible
   tone), then releases. Pass = the command was accepted without throwing (a real CAT ACK, or a real
   RTS/DTR line toggle). The UI must say plainly that this confirms the *command*, not that the rig
   *visibly keyed* — the operator still has to watch the rig themselves.
2. **Confirmation dialog before firing Test?** → **No.** A single click is enough, consistent with
   every other action already on this page (Save, Retry, Refresh) — none of which prompt "are you
   sure?" — and the pulse is brief and watchdog-protected regardless.

## A safety-critical finding surfaced while scoping this — fix required, not optional

Reading `CatPttController.cs` to figure out how Test should actually invoke it surfaced something
that has nothing to do with the UI itself: **`CatPttController`/`SerialRtsDtrPttController` have no
internal call-serialisation.** `KeyDownAsync`/`KeyUpAsync` were written assuming exactly one caller —
the active `QsoAnswererService`/`QsoCallerService` — ever calls them. A Test click is a second,
independent caller of the same DI singleton `IPttController`.

Without a guard, firing Test while a real QSO is mid-transmission would run a second
`KeyDownAsync`/`KeyUpAsync` sequence concurrently against the *same* controller instance: the shared
watchdog gets silently re-armed (resetting a real transmission's failsafe countdown to a fresh
timer), and — worse — the Test's own short `KeyUpAsync` sets `_pttAsserted = false` and de-asserts
PTT, **physically unkeying a real, in-progress over-the-air transmission**. That is precisely the
kind of failure this change's own stated design principle ("prefer the design that fails toward 'rig
stays silent' over the one that fails toward 'rig stays keyed'") exists to prevent — this feature, if
built without the guard below, would introduce a fresh way to *stop* a legitimate transmission mid-
flight from an unrelated browser tab.

**Required, two layers (see tasks.md 17.2/17.3):**
1. `POST /api/v1/ptt/test` checks `IQsoController.Keying` and rejects with 409 if a real QSO is
   currently keying.
2. `CatPttController` and `SerialRtsDtrPttController` each gain a private `SemaphoreSlim(1,1)`
   around their entire `KeyDownAsync`→`KeyUpAsync` critical section, so a request that races past
   check (1) queues behind the real transmission instead of interleaving with it. This is small and
   mirrors design.md Decision 1's own wire-serialisation gate one layer up — do this **before** any
   UI work (tasks.md 17.2 is explicitly ordered first for this reason).

Existing `CatPttControllerTests.cs`/`SerialRtsDtrPttControllerTests.cs` suites must pass **unmodified**
after adding the semaphore (same "zero assertion changes" discipline task 7.3 already established for
the `WasapiTxPlayer` extraction) — plus one new test per controller proving two concurrent
`KeyDownAsync` callers serialise rather than interleave.

## Scope (full detail in tasks.md section 17 — summarised here)

- **Layout:** split `#cat-settings` into two side-by-side fieldsets ("CAT rig connection" unchanged,
  new "PTT Config") on wide viewports, stacking on narrow ones — reuse whatever breakpoint
  `app.css` already uses elsewhere in this page rather than inventing a new one.
- **New fields:** `ptt.method` (AudioVox/CatCommand/SerialRtsDtr), `serialPort`/`serialLine` (shown
  only for SerialRtsDtr — reuse the existing generic `/api/v1/serial/ports` endpoint and the
  `cat-serial-port`/`cat-serial-refresh` `input-with-action` pattern verbatim), `leadTimeMs`,
  `tailTimeMs`, `watchdogTimeoutMs` (hidden for AudioVox — nothing to configure).
- **Test button + badge:** mirrors `.cat-status-badge`'s existing three-state visual pattern
  (`.cat-connected`/`.cat-error`/`.cat-disabled` → new `.ptt-test-pass`/`.ptt-test-error`/
  `.ptt-test-idle`, same CSS custom properties). Disabled/hidden when the **live**, already-running
  method is AudioVox (there's nothing to test), with a hint that a Save + restart is required before
  Test reflects a newly-selected method — `ptt.method` is read once at DI-registration time, not
  hot-reloaded (already corrected in `docs/cat-control-operator-guide.md`).
- **`settings.js`'s save payload now includes a `ptt` key** for the first time — this is the
  deliberate, intended end of the "Settings page never sends `ptt`" behaviour design.md Decision 6
  originally described. The null-guard fix's fallback-to-`Current.Ptt` behaviour
  (`WebApp.cs`/`JsonConfigStore.cs`, merged same day) is unaffected and remains correct
  defense-in-depth for any caller that still omits the key.
- **Backend:** new `POST /api/v1/ptt/test` per the safety section above.
- **Docs:** `docs/cat-control-operator-guide.md`'s "no Settings-page UI for `ptt`" line is now false
  once this ships — update it, and document Test's exact semantics (software pulse, not a physical
  confirmation).
- **REQUIREMENTS.md:** add **FR-057** (next free number after FR-056) for this UI, following the
  existing FR-056 entry's format, plus a version-history row.

## Verification

1. `dotnet build -c Release` / `dotnet test -c Release --no-build` — all green, plus the new
   concurrent-KeyDownAsync serialisation tests and the new `POST /api/v1/ptt/test` coverage.
2. Manual: with `ptt.method = "CatCommand"` and CAT connected, load Settings → Radio hardware, click
   Test, confirm a Pass badge and `CatPttController: KeyDown — PTT asserted (CAT).` /
   `KeyUp — PTT released (CAT).` in the log within the ~200–300 ms window, and confirm the rig's own
   TX indicator pulses briefly. Then start a real automated QSO (or simulate one via the existing TX
   test flow) and click Test *while it is transmitting* — confirm the endpoint returns 409 and the
   real transmission's audio/PTT is completely undisturbed (this is the regression test for the
   safety finding above; do not skip it).
3. `openspec validate --strict --all` — expect unchanged pass count (design.md/tasks.md are not
   spec-graded content; no spec text changes).
4. Before/after screenshots of the Radio hardware tab, before-first per the project's standing
   screenshot-ordering rule.

## QA re-review

QA will re-run the manual reproduction in "Verification" step 2 directly (including the
concurrent-Test-during-a-real-QSO case — this is not optional given what triggered the requirement),
inspect the semaphore addition in both controllers line-by-line rather than trusting "tests pass",
confirm the operator-guide and REQUIREMENTS.md updates land, and confirm the full suite plus
`openspec validate --strict --all` are green before sign-off.

## References

- `openspec/changes/cat-tx-ptt/design.md` — Decision 6's 2026-07-12 amendment (authoritative safety
  analysis for the semaphore requirement).
- `openspec/changes/cat-tx-ptt/tasks.md` — section 17 (authoritative, itemised task list).
- `src/OpenWSFZ.Daemon/CatPttController.cs`, `src/OpenWSFZ.Daemon/SerialRtsDtrPttController.cs` —
  no existing internal call-serialisation; add the `SemaphoreSlim(1,1)` here.
- `src/OpenWSFZ.Abstractions/IRadioConnection.cs:52-62` (`SetPttAsync` — no read-back capability,
  hence Test can only confirm the command, never the physical rig state).
- `web/settings.html:153-229` (`#cat-settings` fieldset — markup pattern to mirror for the new
  fieldset), `web/js/settings.js` (CAT element refs/handlers — pattern to mirror for PTT),
  `web/css/app.css:848-882` (`input-with-action` and `.cat-status-badge` — patterns to mirror).
- `src/OpenWSFZ.Web/WebApp.cs:809` (`IQsoController` resolution pattern already used by every
  `/api/v1/tx/*` endpoint — reuse for the 409-while-keying guard), `WebApp.cs:951-` (`/api/v1/cat/retry`
  — endpoint shape to mirror for `/api/v1/ptt/test`).
- `docs/cat-control-operator-guide.md`, "PTT (Transmit Keying) Configuration" section (the
  "no Settings-page UI" line to correct).
