# DEV TASK — `POST /api/v1/config` can persist a null `Ptt`, silently disabling CAT-command/serial RTS-DTR PTT (and risking a stuck-key NRE)

**Date:** 2026-07-12
**OpenSpec change:** `cat-tx-ptt` (implementation review) — no spec text changes needed; this is
a code defect in the implementation, not a requirements gap. The relevant requirement is already
correctly specified in `openspec/changes/cat-tx-ptt/specs/ft8-tx/spec.md` under "PTT method
configuration" / scenario "Default configuration preserves existing VOX behaviour" (`AppConfig.Ptt`
must always resolve to a usable, non-null `PttConfig`) — the bug below causes that invariant to be
violated at runtime, at the exact layer the spec doesn't reach (the live HTTP config-save path).
**Branch:** `feat/cat-tx-ptt`.
**Status:** New. Found during hardware acceptance (Gate 14/15): Captain reported "the radio never
enables TX" after configuring CAT-command PTT. Root-caused by QA via log inspection + static code
reading, not yet reproduced with an automated test (see "Tests required" below — this doc specifies
that test rather than including it, so the developer's fix and the regression test land together).
**Found by:** QA, diagnosing `logs/openswfz-20260712T131050Z.log` against the `cat-tx-ptt` review
already performed the same day.
**Severity:** High. This is not merely "a setting doesn't stick" — see "Why this is worse than it
looks" below for the stuck-PTT NullReferenceException path.

---

## Evidence

The Captain's live `C:\Users\Frank\AppData\Roaming\OpenWSFZ\config.json` currently contains:

```json
"ptt": null,
```

The session log (`logs/openswfz-20260712T131050Z.log`) shows every TX cycle logging the exact,
literal message `AudioOnlyPttController.KeyDownAsync` emits:

```
TX KeyDown — starting playback on device '...' (606720 samples).
```

`CatPttController: KeyDown — PTT asserted (CAT).` and `SerialRtsDtrPttController: KeyDown — PTT
asserted (...).` — the messages the CAT-command and serial RTS/DTR controllers would log — never
appear anywhere in the file. Whatever `ptt.method` the Captain intended for this hardware-acceptance
run, the daemon ran on plain VOX (`AudioOnlyPttController`) throughout, which is consistent with a
`ptt.method` that silently reverted to `"AudioVox"` before or during the session.

The log also contains exactly one `POST /api/v1/config` (15:11:59.920, from the Settings page,
loaded at 15:11:39), which is the only way this session touched persisted config after startup.

## Root cause

This is the same class of bug as **D-010** and its two prior recurrences (`decodeLog`, `logging`,
`decodeNoiseSuppression`, `externalReporting` — see
`tests/OpenWSFZ.Web.Tests/ConfigApiNullGuardTests.cs`), now recurring for the new `Ptt` section this
change introduces.

1. **`web/js/settings.js`'s save handler never sends a `ptt` key.** The `postConfig({...})` payload
   (built starting ~line 1097) lists `audioDeviceId, ..., cat, tx, remoteAccess, decoder,
   decodeNoiseSuppression, externalReporting` — every other config section, but not `ptt`. This is
   correct and intentional: `cat-tx-ptt` deliberately ships with no Settings-page UI for PTT
   configuration (design.md Decision 6, matching FR-016 — no speculative UI). The consequence is
   that **every single Settings-page save omits the `ptt` key from its request body**, by design.

2. **`WebApp.cs`'s `POST /api/v1/config` handler has no guard for `Ptt`.** It deserializes the
   request body directly into a whole new `AppConfig` (`request.ReadFromJsonAsync(...)`,
   `WebApp.cs:339`). System.Text.Json's source-generated deserializer sets a non-nullable `init`
   property to `null` when its JSON key is absent, rather than falling back to the property's `=
   new()` initialiser — the exact quirk this same handler already guards against for four other
   sections, immediately after the read (`WebApp.cs:361-368`):

   ```csharp
   if (config.Logging is null)
       config = config with { Logging = new LoggingConfig() };
   if (config.DecodeLog is null)
       config = config with { DecodeLog = new DecodeLogConfig() };
   if (config.DecodeNoiseSuppression is null)
       config = config with { DecodeNoiseSuppression = new DecodeNoiseSuppressionConfig() };
   if (config.ExternalReporting is null)
       config = config with { ExternalReporting = new ExternalReportingConfig() };
   ```

   **`Ptt` is missing from this list.** `PttConfig` has the identical shape to all four guarded
   types (`AppConfig.Ptt` is a non-nullable `{ get; init; } = new()` property — see
   `src/OpenWSFZ.Abstractions/AppConfig.cs:54`), so it is subject to the identical quirk — and,
   unlike the other four, it is *guaranteed* to be absent from every request the Settings page
   sends, because there is no field for it in the JS payload at all.

3. **`JsonConfigStore.SaveAsync` performs no validation of its own** (`JsonConfigStore.cs:43-90`);
   it serializes and persists whatever `AppConfig` it is handed and immediately updates `_current`
   in memory (`JsonConfigStore.cs:75`). So the null `Ptt` sails straight through to both the file on
   disk and the live in-memory config for the remainder of the process.

`JsonConfigStore.Load()` (`JsonConfigStore.cs:153-154`) *does* correctly guard `Ptt` — the developer
clearly knew about this quirk and handled it for the file-read-at-startup path (task 2.5's own round-
trip verification covers exactly this). What's missing is the parallel guard on the live-HTTP-write
path, which is a different code path entirely and isn't exercised by `PttConfigTests.cs` or
`JsonConfigStoreTests.cs` (both correctly test the layer they're testing — this gap is specifically
in `WebApp.cs`, which has its own dedicated null-guard test file for exactly this reason).

## Why this is worse than it looks

**Case A — daemon started with `ptt.method = "AudioVox"` (the default, or after a previous null
reset):** the very next Settings-page save does nothing new, because `AudioOnlyPttController` never
reads `AppConfig.Ptt` at all. The operator sees no error. If they'd separately hand-edited
`config.json` to `"CatCommand"`/`"SerialRtsDtr"` expecting it to take effect on save/reload (as the
operator guide currently — incorrectly, see "Also update the docs" below — implies is possible), that
edit is silently discarded the moment any Settings save happens, and the *next restart* resolves back
to `AudioVox` with no warning logged anywhere. This is almost certainly what the Captain hit.

**Case B — a `CatCommand`/`SerialRtsDtr` controller is already the active DI-registered singleton**
(daemon was started fresh with the correct `ptt.method` on disk, and a Settings save happens
afterward, mid-session, for any reason): the next `KeyDownAsync` call does

```csharp
// CatPttController.KeyDownAsync (SerialRtsDtrPttController is structurally identical)
var ptt = _configStore.Current.Ptt;                            // now null
...
await _pttGate.SetPttAsync(true, ct).ConfigureAwait(false);     // PTT physically asserted — rig keys
_pttAsserted = true;
_watchdog.Arm(ptt.WatchdogTimeoutMs, ForceReleaseAsync);        // NullReferenceException here
```

The NRE fires **after** PTT has been physically asserted and **after** `_pttAsserted = true`, but
**before** the watchdog is armed and **before** the exception-safe `try` block (the one wrapping the
lead-time wait and playback, whose `catch` calls `KeyUpAsync` to release PTT) has even begun. None of
this change's carefully-built release guarantees apply to an exception thrown here — this is exactly
the stuck-transmitter failure mode `cat-tx-ptt`'s entire watchdog/failsafe design exists to prevent,
triggered by an unrelated, ordinary Settings save (e.g. tweaking the CAT serial port, which is
precisely the kind of adjustment an operator makes while setting up hardware acceptance testing).

Not reproduced against real hardware in this pass — flagging as a static-analysis-confirmed risk
requiring the same fix as Case A, verified by the same test.

## Recommended fix

Two small, mechanical additions, matching the established pattern exactly (do not invent a new
pattern — this is the fourth time this exact bug shape has occurred; use the same fix shape as
D-010/`decode-noise-suppression`/`gridtracker-udp-reporting` did):

1. **`src/OpenWSFZ.Web/WebApp.cs`**, alongside the four existing guards (~`WebApp.cs:368`):

   ```csharp
   if (config.Ptt is null)
       config = config with { Ptt = new PttConfig() };
   ```

2. **`src/OpenWSFZ.Config/JsonConfigStore.cs`'s `SaveAsync`** — belt-and-braces. `SaveAsync` is the
   one true chokepoint all persistence goes through (not just this one HTTP handler — e.g. any
   future caller that builds an `AppConfig` from a partial source), and it currently guards nothing.
   Add the identical guard at the top of `SaveAsync`, before the write:

   ```csharp
   if (config.Ptt is null)
       config = config with { Ptt = new PttConfig() };
   ```

   (Optional but recommended while touching this method: consider whether `Logging`/`DecodeLog`/
   `DecodeNoiseSuppression`/`ExternalReporting` should receive the same defense-in-depth treatment
   here rather than relying solely on the `WebApp.cs`-side guard — out of scope for this task, note
   only, do not fix unrelated sections as a drive-by.)

3. **Do not** attempt to fix this by adding null-checks inside `CatPttController`/
   `SerialRtsDtrPttController`/`PttControllerSelector` instead — that would treat the symptom (the
   NRE) without preventing the underlying bad state from being written to disk and read back in a
   context that lacks `JsonConfigStore.Load()`'s own guard. Fix it at the same layer the existing
   `Logging`/`DecodeLog`/`DecodeNoiseSuppression`/`ExternalReporting` guards already fix it at.

## Also update the docs

`docs/cat-control-operator-guide.md`'s new PTT section currently says:

> There is currently no Settings-page UI for `ptt` — edit the config file directly (same location
> as every other setting) and restart the daemon (**or save/reload**) to pick up changes.

The "or save/reload" half is actively misleading given `Ptt.Method` is only ever read once, at
`Program.cs`'s DI-registration time (~`Program.cs:436`) — it is not hot-reloaded on config save the
way, say, `CatConfig` is. Please correct this line once the guard fix above is in, to state plainly
that a full daemon restart is required for a `ptt` change to take effect, and that (post-fix) a
Settings-page save no longer discards a manually-edited `ptt` section.

## Tests required

- Extend `tests/OpenWSFZ.Web.Tests/ConfigApiNullGuardTests.cs` with a fifth case, following the
  existing four exactly (raw JSON via `StringContent`, **not** `new AppConfig() with {...}`, since
  the latter never reproduces the quirk — see the file's own class-level doc comment): POST a body
  omitting `"ptt"`, then GET `/api/v1/config` back and assert the section round-trips as a non-null
  object with the documented defaults (`method == "AudioVox"`, `serialLine == "Rts"`, `leadTimeMs ==
  50`, `tailTimeMs == 50`, `watchdogTimeoutMs == 20000`) — not merely non-null.
- No change needed to `PttConfigTests.cs`, `JsonConfigStoreTests.cs`, `CatPttControllerTests.cs`, or
  `SerialRtsDtrPttControllerTests.cs` — all four already correctly cover their respective layers
  (schema defaults, the file-load path guard, and each controller's own behaviour given a
  well-formed, non-null `PttConfig`). This gap is specifically in the HTTP POST path, which has its
  own dedicated test file for exactly this reason.
- Optional, if practical: a `CatPttControllerTests.cs`/`SerialRtsDtrPttControllerTests.cs` case
  constructing the controller with a mock `IConfigStore` whose `Current.Ptt` is `null`, asserting
  `KeyDownAsync` fails in a PTT-released state rather than leaving `_pttAsserted == true` — this
  would directly cover Case B above at the controller layer as well as the config layer. Not
  required for this task's sign-off if time-constrained; the `WebApp.cs`/`JsonConfigStore.cs` guard
  fix already prevents `Ptt` from ever reaching either controller as `null` in the first place, which
  is the correct place to fix it (see "Do not" above) — this would be pure defense-in-depth.

## Verification

1. `dotnet build -c Release` / `dotnet test -c Release --no-build` — expect unchanged pass counts
   plus the one new test, all green (442 → 443 in `OpenWSFZ.Daemon.Tests` is unaffected since this
   test lives in `OpenWSFZ.Web.Tests`; that suite's count should go up by exactly one).
2. Manually repeat the Captain's scenario: set `ptt.method = "CatCommand"` in `config.json`, start
   the daemon, confirm `CatPttController: KeyDown — PTT asserted (CAT).` appears on the first TX
   cycle. Then perform any unrelated Settings-page save (e.g. toggle `showCycleCountdown`) and
   confirm the *next* TX cycle still logs the `CatPttController` message, not `AudioOnlyPttController`'s
   `TX KeyDown — starting playback...` — and confirm `config.json`'s `ptt.method` still reads
   `"CatCommand"` after the save.
3. `openspec validate --strict --all` — expect unchanged pass count (no spec text is being changed
   by this fix).

## References

- `src/OpenWSFZ.Web/WebApp.cs:331-368` (`POST /api/v1/config` handler — existing `Logging`/
  `DecodeLog`/`DecodeNoiseSuppression`/`ExternalReporting` guards to mirror; fix belongs at line
  ~368).
- `src/OpenWSFZ.Config/JsonConfigStore.cs:43-90` (`SaveAsync` — no guard today; add one) and
  `JsonConfigStore.cs:148-154` (the equivalent guard already correctly applied to the file-load
  path — same pattern, different layer).
- `src/OpenWSFZ.Daemon/CatPttController.cs:113-145` (`KeyDownAsync` — shows the exact NRE-after-
  assert ordering described in Case B) and `src/OpenWSFZ.Daemon/SerialRtsDtrPttController.cs:135-172`
  (structurally identical risk).
- `src/OpenWSFZ.Abstractions/AppConfig.cs:54` (`Ptt` property — non-nullable, `= new()` initialiser,
  same shape as the four already-guarded sections).
- `tests/OpenWSFZ.Web.Tests/ConfigApiNullGuardTests.cs` (existing D-010-class regression fixture;
  extend this file rather than creating a new one).
- `docs/cat-control-operator-guide.md`, "PTT (Transmit Keying) Configuration" section (the
  "restart the daemon (or save/reload)" line to correct).
- `openspec/changes/cat-tx-ptt/specs/ft8-tx/spec.md`, requirement "PTT method configuration",
  scenario "Default configuration preserves existing VOX behaviour" — the invariant this bug
  violates at runtime (a missing/reset `ptt` section must always resolve to a well-formed
  `PttConfig`, not `null`).
- `logs/openswfz-20260712T131050Z.log` — the session in which this was caught; every TX cycle logs
  `AudioOnlyPttController`'s message, never `CatPttController`'s or `SerialRtsDtrPttController`'s.

## QA re-review

QA will re-run the manual reproduction in "Verification" step 2 directly against the fix (not just
trust that tests pass), check the new test's assertions rather than "count went up by one," confirm
the operator-guide correction lands, and confirm the full suite (`dotnet test`,
`openspec validate --strict --all`) is still green before sign-off. Hardware acceptance (Gates
14–16 in `openspec/changes/cat-tx-ptt/tasks.md`) should not be re-attempted by the Captain until this
fix has merged — there is no point re-testing real hardware against a config layer known to discard
the setting under test.
