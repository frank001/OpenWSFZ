# Developer handoff: `cycleAudioArchive` null-config crash on Settings-page save

**Authored by:** QA (per HK-011/HK-015/HK-000), from a live incident during the 2026-07-28 10m
live-run session.
**Branch:** do **not** stack on `d001-c4-min-score-sweep` (that branch's `libft8.dll` carries an
unexplained size delta already flagged by the Architect as a merge blocker — a fix built on it
would not be trustworthy). Branch fresh off `main` (current tip `7a44b2c`), e.g.
`fix-cycle-audio-archive-null-config-crash`.
**Status:** live defect, reproduced and root-caused this session; not yet fixed. No regression
test exists for this path today.
**Affects:** shipped, archived change `openspec/changes/archive/2026-07-26-cycle-audio-archive`
(`cycle-audio-archive` capability). This is a defect against that closed change, not a reason to
reopen it.

---

## 1. Incident summary

During an unattended 10m live-run session, `OpenWSFZ.Daemon.exe` crashed mid-run with:

```
[ERR] Decode error: Object reference not set to an instance of an object.
System.NullReferenceException: Object reference not set to an instance of an object.
   at OpenWSFZ.Daemon.CycleArchiveService.TryEnqueue(Single[] pcm, DateTime cycleStart, DateTime closedUtc, Int32 decodeCount, Double dialMhz) in CycleArchiveService.cs:line 178
   at Program.<>c__DisplayClass0_3.<<<Main>$>b__35>d.MoveNext() in Program.cs:line 798
```

No graceful-shutdown log line followed — the process died outright, one decode cycle after the
exception. The operator restarted the daemon manually; on restart, `cycle-audio-archive` had
silently reverted to `Mode = Off`, so no WAV recordings were produced for the remainder of the
session even though archiving had previously been configured on. The run was aborted once this
was traced, rather than continuing to lose data to repeat crashes.

## 2. Root cause — two missing guards, one unconditional dereference

Three pieces of code interact to produce this failure. All three live in the `main` tree (verified
against the `main-80m-baseline` worktree, commit `7a44b2c`):

### 2.1 The trigger: `WebApp.cs`'s `POST /api/v1/config` guard list is missing `CycleAudioArchive`

`src/OpenWSFZ.Web/WebApp.cs:373-400` explicitly re-defaults five properties against a documented
System.Text.Json source-generation quirk (a JSON payload that omits a key deserialises a
non-nullable `init` property to `null` instead of honouring its `= new()` initialiser):

```csharp
if (config.Logging is null)
    config = config with { Logging = new LoggingConfig() };
if (config.DecodeLog is null)
    config = config with { DecodeLog = new DecodeLogConfig() };
if (config.DecodeNoiseSuppression is null)
    config = config with { DecodeNoiseSuppression = new DecodeNoiseSuppressionConfig() };
if (config.ExternalReporting is null)
    config = config with { ExternalReporting = new ExternalReportingConfig() };
// ... Ptt guarded separately below (line 399-400) ...
```

`CycleAudioArchive` (added 2026-07-26, after this guard block was written) is not in this list.
Neither is `RemoteAccess` — see §4 for why that one is lower priority. Confirmed via
`grep -rn "cycleAudioArchive" web/`: there is **no Settings-page UI field for it at all** (same
situation as `Ptt`, per the comment at `WebApp.cs:387-389`), so **every** ordinary Settings-page
save (toggling `showCycleCountdown`, changing log level, anything) POSTs a body that omits
`cycleAudioArchive`, hits the STJ null quirk, and is not caught by this guard block.

### 2.2 The second missed backstop: `JsonConfigStore.SaveAsync` only re-guards `Ptt`

`src/OpenWSFZ.Config/JsonConfigStore.cs:43-61` documents itself as "the one true chokepoint all
persistence goes through, not just the POST /api/v1/config handler" and re-applies the same
null-vs-initialiser guard — but only for `Ptt` (line 59-60). `Load()` (same file, lines 138-178)
guards **seven** sections (`Logging`, `DecodeLog`, `RemoteAccess`, `DecodeNoiseSuppression`,
`ExternalReporting`, `CycleAudioArchive`, `Ptt`); `SaveAsync` guards **one**. Whatever a caller
hands `SaveAsync` — including a `WebApp.cs`-built config with a null `CycleAudioArchive` that
slipped past §2.1 — is written to disk and installed into live `_current` verbatim.

The result: the null is persisted to `%APPDATA%\OpenWSFZ\config.json` (confirmed on disk this
session — literal `"cycleAudioArchive": null`) **and** immediately live in the running process's
`_configStore.Current`.

### 2.3 The crash site: `CycleArchiveService` dereferences `CycleAudioArchive` unconditionally, twice

- `TryEnqueue` (`src/OpenWSFZ.Daemon/CycleArchiveService.cs:178`, the crash site):
  ```csharp
  var mode = _configStore.Current.CycleAudioArchive.Mode;
  ```
  This is the *first line* of the method, executed on every decode cycle regardless of archive
  mode. No null-check.
- `ProcessItemAsync` (same file, line 269) has the identical pattern:
  ```csharp
  var config    = _configStore.Current.CycleAudioArchive;
  var directory = string.IsNullOrWhiteSpace(config.Directory) ...
  ```
  Not hit in this incident (the writer never got an item enqueued before the crash), but it has
  the same latent NRE waiting for the next queued item once `CycleAudioArchive` is null.

Once §2.1/§2.2 let a null through, every subsequent decode cycle crashes at §2.3 until the
process is restarted — and restarting doesn't fix the persisted `null` in `config.json`, so
`Load()`'s own guard (§2.4) papers over it every time by silently substituting
`new CycleAudioArchiveConfig()`, whose default `Mode` is `Off`
(`src/OpenWSFZ.Abstractions/CycleAudioArchiveConfig.cs:78`). **That is why the operator's
previously-configured archive mode was silently lost on restart**: not a separate bug, the direct
consequence of §2.1-2.3 combined with `Load()`'s defaulting behaviour.

### 2.4 For contrast: this exact class of bug has already been fixed once, in `AllTxtWriter`

`src/OpenWSFZ.Daemon/AllTxtWriter.cs:64-68` carries a comment describing the identical failure
mode against `DecodeLog` (D-010, already resolved) and the fix pattern this dev-task should
mirror:

```csharp
// D-010 defence in depth: read _configStore.Current.DecodeLog inside the try
// block so this method cannot throw unguarded even if some future code path
// reintroduces a null DecodeLog into IConfigStore.Current (the actual root
// cause — a null-persisting POST /api/v1/config body — is fixed at the
// source in WebApp.cs, but this method should be self-defending regardless).
```

`ExternalReportingService.Reconcile` (`ExternalReportingService.cs:282-284`) applies the same
two-layer pattern: fix at the source (`WebApp.cs`), *and* `config ??= new ExternalReportingConfig();`
as defence in depth at the consumer. `CycleArchiveService` currently has neither layer for
`CycleAudioArchive`.

## 3. Required fix — three layers, matching the established pattern exactly

1. **`WebApp.cs:373-400`** — add a `CycleAudioArchive` guard to the existing block, same shape as
   `DecodeLog`/`ExternalReporting`:
   ```csharp
   if (config.CycleAudioArchive is null)
       config = config with { CycleAudioArchive = new CycleAudioArchiveConfig() };
   ```
   Note this reverts to `Mode = Off` on an omitted key exactly like the four existing guards do —
   consistent with those, but worth flagging in review: because there is no Settings-page UI for
   this field, every generic settings save will keep re-defaulting it, so the moment a future PR
   adds a `cycle-audio-archive` UI to the Settings page, this guard needs the same
   `?? store.Current.CycleAudioArchive` fallback pattern `Ptt` uses (line 399-400) instead of a
   fresh default — otherwise re-enabling archiving via a dedicated panel would get silently
   clobbered by the very next unrelated settings save, reproducing the "stuck-on-VOX"-style bug
   the `Ptt` guard exists to prevent. Not required for this fix (no such UI exists yet), but leave
   a comment saying so for whoever adds it.

2. **`JsonConfigStore.SaveAsync` (`JsonConfigStore.cs:59-60`)** — extend the belt-and-braces guard
   to cover `CycleAudioArchive` (and, while touching this, consider whether the other five
   `Load()`-guarded sections belong here too — see §4):
   ```csharp
   if (config.CycleAudioArchive is null)
       config = config with { CycleAudioArchive = _current.CycleAudioArchive ?? new CycleAudioArchiveConfig() };
   ```

3. **`CycleArchiveService.cs`** — defence in depth at both call sites, matching `AllTxtWriter`'s
   pattern:
   - Line 178 (`TryEnqueue`): `var archiveConfig = _configStore.Current.CycleAudioArchive; if (archiveConfig is null) return;` before reading `.Mode`, or `(_configStore.Current.CycleAudioArchive ?? new CycleAudioArchiveConfig()).Mode` inline — either is fine, prefer whichever reads closer to the `AllTxtWriter` precedent.
   - Line 269 (`ProcessItemAsync`): same coalesce before reading `.Directory`.

## 4. Scope note — `RemoteAccess` is the same gap, lower urgency

`WebApp.cs`'s guard block also omits `RemoteAccess`, which `JsonConfigStore.Load()` guards
(line 150-151) but `SaveAsync` and `WebApp.cs`'s POST handler do not. Nothing today dereferences
`RemoteAccess` unconditionally the way `CycleArchiveService` does `CycleAudioArchive`, so it isn't
an active crash — but it's the same latent shape of bug and worth a one-line fix alongside this
one if convenient. Not blocking; use judgement on whether to bundle it into this branch or file it
separately.

## 5. Tests required

- **Regression test** (per this repo's stated policy that every bug fix carries one): a test
  driving `POST /api/v1/config` with a body that omits `cycleAudioArchive` (mirroring how
  `web/js/settings.js` actually builds its payload — no key sent at all) must assert the server
  response's `CycleAudioArchive` is non-null with `Mode = Off`, **and** that a subsequent
  `IConfigStore.Current.CycleAudioArchive` read (simulating the very next decode cycle calling
  `TryEnqueue`) does not throw.
- A unit test on `JsonConfigStore.SaveAsync` directly: construct an `AppConfig` with
  `CycleAudioArchive = null`, call `SaveAsync`, assert `Current.CycleAudioArchive` is non-null
  afterward.
- A unit test on `CycleArchiveService.TryEnqueue`/`ProcessItemAsync` with a config store stub
  whose `Current.CycleAudioArchive` is null — assert no exception, cycle is treated as a no-op
  drop (or off-mode skip), consistent with existing drop-accounting tests in this class
  (`qa`/existing suite already covers queue-full and free-space-floor drop paths — see
  `dev-tasks/2026-07-26-flaky-cyclearchiveservice-retention-sizecap.md` for the existing test
  file to extend rather than duplicate).

## 6. Verification before handing back to QA

- Confirm via a manual `POST /api/v1/config` with a minimal body (no `cycleAudioArchive` key) that
  `GET /api/v1/config` afterward shows a non-null `cycleAudioArchive` object.
- Confirm the daemon survives at least one decode cycle immediately after such a POST without the
  `TryEnqueue` NRE reappearing in the log.
- Run the existing `CycleArchiveService` test suite (retention/size-cap tests referenced above)
  to confirm no regression there.
- Per HK-006, `python3 tools/pre_merge_check.py` is QA's own gate to run at merge time, not a
  dev-task checklist item — do not add it here.
