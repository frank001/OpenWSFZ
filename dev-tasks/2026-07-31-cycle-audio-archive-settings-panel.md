# Developer handoff: cycle-audio-archive Settings-page panel (+ required guard-pattern fix)

**Authored by:** QA (per HK-011/HK-015/HK-000), from a Captain's question during the pre-flight
review of the 2026-07-31 multi-day 20m live run ("where is the save-files settings page?").
**Branch:** fresh off `main`, current tip `2dacd1a`. **Do not** touch `src/OpenWSFZ.Web/WebApp.cs`
or `src/OpenWSFZ.Config/JsonConfigStore.cs` on a branch that could get merged while the multi-day
20m run (see `qa/cycleframer-alignment-replay/2026-07-31-1907-architect-to-qa-preflight-brief-
multiday-20m-live-run.md`) is still in flight — that run's two live instances must not be rebuilt
mid-flight. Confirm the run has ended, or hold this PR, before merging to `main`.
**Status:** feature build-out, not a defect fix. Nothing is broken; this closes a deliberately
parked gap.
**Affects:** `openspec/specs/cycle-audio-archive/spec.md` (shipped capability, config/API-only
today); `openspec/changes/archive/2026-07-26-cycle-audio-archive/design.md` Decision 9 ("No GUI in
this change... the settings panel is a separate later change") is the origin of this task — read
it before starting, it records the intended panel contents.

---

## 1. Why now

There is currently no Settings-page UI for `cycleAudioArchive` at all — confirmed via
`grep -i archive web/settings.html web/js/settings.js`, zero hits. The capability is configured
through `config.json` / `POST /api/v1/config` only. This was a deliberate sequencing decision
(Decision 9: "UI controls appear only once their backend is fully implemented and testable
end-to-end"), not an oversight — but the backend has been fully implemented, tested, and now
live-run-proven since PR #109 (2026-07-26) and PR #119 (2026-07-31, the null-config crash fix), so
the parking condition no longer holds.

## 2. Required fix, Part A — the guard must switch to the `Ptt` pattern FIRST

This is a prerequisite, not an afterthought: `src/OpenWSFZ.Web/WebApp.cs:501-502` currently
defaults a missing `cycleAudioArchive` key to a **fresh** `new CycleAudioArchiveConfig()`
(`Mode = Off`, `MaxSizeMb = 2048`, `MaxAgeHours = 168`) on every `POST /api/v1/config`:

```csharp
if (config.CycleAudioArchive is null)
    config = config with { CycleAudioArchive = new CycleAudioArchiveConfig() };
```

The in-code comment immediately above this (lines 488-500) already predicts exactly this task and
already specifies the fix — switch to the `Ptt` guard's pattern (`WebApp.cs:515-516`), which falls
back to the *persisted* value instead of a hardcoded default:

```csharp
if (config.CycleAudioArchive is null)
    config = config with { CycleAudioArchive = store.Current.CycleAudioArchive ?? new CycleAudioArchiveConfig() };
```

**This must land in the same PR as the panel, not before and not after.** Before the panel exists,
changing this guard is inert (every save omits the key regardless, so the fallback path is never
exercised either way) — landing it early is safe but pointless on its own. After the panel exists
without this fix, the very first unrelated Settings-page save (adjusting the watchdog timer,
toggling a checkbox on another tab) silently clobbers whatever archive mode/directory/retention the
operator just set through the new panel back to `Off`/defaults — reproducing the exact
"stuck-on-VOX"-class bug the `Ptt` guard exists to prevent, this time through the panel meant to
fix that very gap. Ship them together.

`JsonConfigStore.SaveAsync` (`JsonConfigStore.cs:73-74`) already uses the correct
`_current.CycleAudioArchive ?? new CycleAudioArchiveConfig()` fallback — no change needed there.
`CycleArchiveService.cs:185` and `:277` also already read defensively
(`_configStore.Current.CycleAudioArchive ?? new CycleAudioArchiveConfig()`) — no change needed
there either. **Only `WebApp.cs`'s POST handler is wrong.**

## 3. Required fix, Part B — the panel itself

Add an eighth Settings-page tab (or a `fieldset` inside an existing tab — Advanced is the closest
fit if a new top-level tab feels like too much chrome; Developer's call, note the choice in the
PR). Mirror the existing `Logging` tab's checkbox + dependent-fields pattern
(`web/settings.html:382-420`, `web/js/settings.js:24-28`, `:337-340`, `:746-749`) — same
element-ref / collect / populate shape used for every other section.

Decision 9 recorded the intended contents; treat these as the scope for this task, split into must
and stretch:

**Must-have (this task):**
- Mode selector: `Off` / `All` / `Decoded` / `NoDecodes`, each with a one-line plain-language
  description — `NoDecodes` especially, since its value ("captures the misses, for false-negative
  investigation") is not self-evident from the name alone. A `<select>` is fine; match whatever
  pattern `TX Mode` on the General tab already uses (`web/settings.html`, search `TX MODE`) since
  that is the closest existing precedent for a described-options dropdown.
- Directory field (text input, same shape as `decode-log-path`). An "open folder" button is
  stretch (see below) — the text field alone is must-have.
- Retention fields: `MaxSizeMb` and `MaxAgeHours`, numeric inputs, same shape as
  `decode-log-dial-freq`.
- All four fields wired into `settings.js`'s collect/populate functions under a `cycleAudioArchive`
  key, matching `decodeLog`'s shape exactly (see `web/js/settings.js:337-340` and `:746-749` for
  the pattern to copy).

**Stretch (do if time allows, otherwise file as a follow-up rather than blocking this PR):**
- "Open folder" affordance next to the directory field.
- Live "N files, M MB used" readout. **No backend surface exists for this today** —
  `CycleArchiveService` tracks drops/retention internally but nothing is exposed via API. This
  needs a small new read-only endpoint (e.g. `GET /api/v1/cycle-audio-archive/stats`) before the
  UI can show it. Scope as a separate dev-task if it doesn't fit here — don't let it block the
  must-have fields above.
- One-shot "record the next N cycles" button. Also has no backend today (current modes are all
  steady-state, not counted-burst) — this is closer to a small feature than a UI wiring task. File
  separately; explicitly out of scope for this PR unless the Developer judges it trivial once the
  mode selector exists.

## 4. Tests required

- **The regression test this whole task exists to enable:** a test driving `POST /api/v1/config`
  twice — first setting `cycleAudioArchive.mode = "all"` (simulating a save from the new panel),
  then a second save with a body that omits `cycleAudioArchive` entirely (simulating an unrelated
  save from any other tab, since that's how `web/js/settings.js` will still behave for every field
  the new panel doesn't own on that particular save round-trip if the client ever sends a partial
  body — and is exactly how every non-archive-tab save behaves today). Assert the *second*
  response's `cycleAudioArchive.mode` is still `"all"`, not reset to `"off"`. This is the direct
  regression test for the WebApp.cs guard fix in §2, and the single most important test in this
  task — it is the test that would have caught the bug this task exists to prevent from being
  reintroduced.
- Unit test on the mode-selector round trip: each of the four modes set via the panel's payload
  shape, `GET /api/v1/config` reflects it back correctly.
- Front-end: whatever this project's existing convention is for settings-page field wiring tests
  (check for existing Playwright/DOM tests over the Logging or External Programs tab and mirror
  that harness rather than introducing a new one — HK-007 confirms Playwright is available with no
  committed devDependency needed).

## 5. Verification before handing back to QA

- Manually: open the new panel, set `Mode = All` and a custom `MaxSizeMb`, Save. Reload the page —
  values persist. Switch to the General tab, change something unrelated, Save. Return to the
  archive panel — `Mode` and `MaxSizeMb` are unchanged (this is the live manual repro of §4's
  regression test).
- Confirm `config.json` on disk shows the expected `cycleAudioArchive` block after each save, not a
  literal reset to defaults.
- Run the existing `CycleArchiveService`/`JsonConfigStoreTests`/`ConfigApiNullGuardTests` suites
  (from PR #119) to confirm no regression on the null-guard paths those cover.
- Per HK-006, `python3 tools/pre_merge_check.py` is QA's own gate to run at merge time, not a
  dev-task checklist item — do not add it here.
- Per HK-014/HK-011, this PR needs Captain sign-off before merge regardless of green CI, and — per
  the branch note at the top of this file — should not land while the 20m multi-day run's
  instances are live.
