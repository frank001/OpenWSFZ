# Design: a config save never changes a setting it did not send (#193)

Base `main` @ `c3f42362`. Source spec: Architect, `qa/2026-09-29-2112-architect-to-eng-spec-config-save-preserves-unsent-settings.md`
(`arch/config-save-preserves-settings` @ `6fb71458`). Read this file with §"Corrections to the source spec" first.

## Preconditions (spec §1), evaluated 2026-09-29

1. `git rev-parse --short origin/main` = `c3f42362` after `git fetch`. **PASS.**
2. Caller inventory of `POST /api/v1/config` outside `src/`, `web/`, `tests/`
   (`git grep -n "api/v1/config" -- qa tools '*.py' '*.ps1'`, excluding logs, `session_log*`, `console.log`, `*.md`, `*.html`).
   **PASS: no caller sends a partial body or relies on omission to reset a field.**

| Caller | GET / POST lines | Body it POSTs |
|---|---|---|
| `qa/cycleframer-alignment-replay/2026-08-04-isolated-replay-rerun/run_isolated_replay_generic.py` | 115 / 125 | the full GET body, with `audioDeviceId`, `audioDeviceFriendlyName`, `logging.*`, `decodeLog.*` set |
| `qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay/run_cross_decode_replay.py` | 129 / 139 | same |
| `qa/cycleframer-alignment-replay/2026-08-07-reference-suppression-m0-m4/replay_lib.py` | 183 / 193 | same |
| `qa/rr-study/results/2026-07-23-d001-tight-class-replay/run_tight_replay.py` | 142 / 152 | same |
| `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/run_isolated_replay.py` | 138 / 148 | same |

No `tools/`, `*.ps1` or endurance `.sh` caller exists. Callers inside `tests/` are covered by D6.

## Corrections to the source spec (recorded here; the Architect will not amend the spec)

- **§6 assumed the run tools already poll the config API. They do not.** `run_study_detached.py` calls
  no `/api/v1/config`, and the endurance supervisors are `.sh` files reading a `config.json` on disk.
  Part E is new code (D7), not an edit.
- **`run_study_detached.py` is not on `main`.** Per the Architect it is tracked only on branch
  `qa/live-gap-map` (`qa/rr-study/run_study_detached.py`, last commit `345e75ff`; local tip `62e8e74a`,
  origin tip `6e3b0a1e`, file identical on both), and is not in QA's current checkout (`qa/sub-feas`).
  This is the known "recovered piecemeal 3x" tooling. Which copy QA ran on 2026-09-29 is **unknown**.
  Getting the tool onto `main` is QA's branch and the Captain's call, and is **not** part of this change.
- **`CycleAudioArchiveMode` has four values, not three** (`Off`, `All`, `Decoded`, `NoDecodes`;
  `CycleAudioArchiveConfig.cs`). The Part C selector must offer all four, or a stored `noDecodes` would
  render as a wrong option and be silently rewritten by the next save.
- The `cycle-audio-archive` spec delta is ADDED, not MODIFIED: no existing requirement's text changes.

## D1: overlay merge (Part A)

Implement the spec §2 table. Recommended mechanism: serialise `store.Current` with `AppJsonContext` to a
`JsonNode`, deep-merge the parsed body onto it, deserialise the result, then run the existing validation
and clamping unchanged on the merged config. Notes the Developer must respect:

- Stored `null` plus body object: the body object is used as-is (defaults fill omitted keys). Recorded
  in the delta spec.
- **Explicit `null` on a non-nullable scalar** (e.g. `"port": null`) is not in the source spec. Today
  STJ throws and the handler answers 400 `Malformed JSON.`. **Keep that.** Do not widen the
  "treat as absent" rule beyond the seven sections.
- The set of non-nullable sections is derived from the table, **not** from reflection, so that a new
  nullable section does not silently become non-nullable. T4 covers new fields.
- Keep the `nhard40MigrationApplied` force. Keep a post-merge non-null assertion per non-nullable
  section, falling back to the **stored** value, never to a fresh default.
- Delete the redundant guards and the two stale comments (spec §2).

## D2: what the merge cannot protect

The overlay protects against **omission**. A client that sends a wrong value still wins. The Settings
page sends `cat` including `lastPolledFrequencyMHz` (`catOpaqueFields`, `settings.js:798`); that stays
client-side and is not touched.

## D3: T4 reflection fixture

Enumerate every leaf of `AppConfig` by reflection (records, nested records, lists as leaves), give each a
non-default value, persist it, POST `{}`, compare canonical JSON. New fields are covered automatically.
Special cases the fixture must handle: enums (pick a non-default member), `string?` (non-null),
`nhard40MigrationApplied` (set `true`), and `remoteAccess.enabled` (keep `false` unless a passphrase is
also set, or validation rejects the fixture).

## D4: dirty-state and payload (Part C)

`snapshotForm()` (`settings.js:330`) gains the archive group. `postConfig({...})` (`:1354-1371`) gains
`cycleAudioArchive`. The T13 payload-contract test pins the key set of that literal.

## D5: Part C validation is read from the service, not invented

Before writing server-side validation, the Developer reads `CycleArchiveService` and records the findings
in this section (a task, 4.1). Known so far, from reading `c3f42362`:

- `mode` is re-read on every `TryEnqueue` (`CycleArchiveService.cs:185`), so it is live.
- `directory` is read at write time (`:278-282`); whether it is live per cycle is **unverified**.
- `maxSizeMb` becomes `maxSizeMb * 1024 * 1024` bytes (`:430`) and `maxAgeHours` becomes a cutoff (`:422`).
  What `0` or a negative value does to retention (possibly deleting everything) is **unverified** and
  must be established before the UI allows it.

Then choose per field: keep a meaningful `0`, or clamp-with-warning, or 400. Record the choice here.

## D6: existing tests that assert the OLD behaviour

**Result (Developer, 2026-09-29, after Part A on branch `feat/config-save-preserves-unsent-settings`): no
existing test's assertion changed. The table has zero rows, and that is a measured result, not an omission.**

Procedure followed (task 2.4): Part A implemented, then `OpenWSFZ.Web.Tests` run in full (340 passed, 0
failed), then the three other projects whose sources mention `POST /api/v1/config`
(`OpenWSFZ.Config.Tests` 105, `OpenWSFZ.Daemon.Tests` 652, `OpenWSFZ.Ft8.Tests` `LoggingPipeline*` 16:
all green, none of them posts to the endpoint; they only cite it in comments).

| Test | Asserted (old) | Why it survives | Changed? |
|---|---|---|---|
| all seven `ConfigApiNullGuardTests` `PostConfig_Omitting<X>Key_DoesNotPersistNull<X>` | after `{audioDeviceId}` the section is not `null` and equals the **default** | each runs against a **fresh** `TestConfigStore`, whose stored section *is* the default; "keep the stored value" and "reset to default" are indistinguishable there. They still guard the null-persistence symptom | no |
| `PostConfig_UnrelatedSave_PreservesPreviouslyPersistedPtt`, the `InstanceId` and `role/leaderUrl/followerUrls` preservation tests | an unrelated save keeps the stored value | the intended behaviour, now provided by the overlay instead of a guard | no |
| `PostConfig_ExplicitInstanceIdResetToDefault_IsHonoured` | an explicit `"instanceId": "OpenWSFZ"` wins | a key present in the body replaces the stored value; the overlay honours it by construction | no |
| test `7.2m` (`DecoderConfigApiTests`, posts a serialised default `AppConfig`) | a null decoder is accepted (200) | the body carries an explicit `"decoder": null` and `decoder` is a nullable section, so `null` is stored, as before. It is **not** a body with no `decoder` key, contrary to the first read recorded above in this section's earlier draft | no |

**What the old tests could not see** (the gap that hid #193): the seven null-guard tests assert "reset to
default" only on a store that is already at default. A test that first stores a non-default value and then
posts a partial body was written only for `ptt` and `externalReporting`. Coverage of that shape is now
`ConfigSaveOverlayTests` T1, T4, T5, T7, T8; T8 in particular **fails on the old handler for six of the
seven sections** (the old handler reset them, the new one keeps them), which is the behaviour change
callers can see.

Behaviour change (b) of spec §2, "a body that omits `decoder` no longer clears a stored decoder whose
marker is `false`", has no pre-existing test either way; it is covered by T4 (stored decoder non-null,
`POST {}`).

## D7: Part E, config-drift module (revised by the Architect's ruling, 2026-09-29)

- A small standalone module `qa/config_drift.py`, with its own tests, that: reads `GET /api/v1/config`,
  takes a start snapshot, and on each poll (interval configurable, default 60 s, at most 300 s) compares a
  key list (at minimum `cycleAudioArchive.mode`, `cycleAudioArchive.directory`, `decodingEnabled` and all
  `decoder.*`). On a mismatch it writes a timestamped `CONFIG-DRIFT` line to a log and returns a row for
  the run report. It **never** restores.
- Values in the drift line are limited to the same allowlist as Part D (HK-037): paths for everything else.
- Wiring: only into run tools that exist on `main`. The endurance supervisors are `.sh` and would call
  the module through a one-line `python` invocation; whether a drift aborts a run is decided per battery
  and recorded in `qa/rr-study/RUNBOOK.md`.
- **Gap, recorded rather than worked around:** `run_study_detached.py` is not on `main`, so the R&R
  launcher cannot be wired. Nothing is landed on `qa/live-gap-map`.
- Lands only after QA has been told (spec §6).

## D8: sequencing of Part B

Part B is not built separately unless the Captain asks for #193 to be closed before Part A lands. If so:
one commit, `config.CycleAudioArchive ?? store.Current.CycleAudioArchive` (the Ptt pattern, never a fresh
default), with T1.

## D9: risks

- The merge changes what every non-UI caller sees. Mitigated by the caller inventory above and D6.
- `decoding_improvement` is unprotected until the sync merge (proposal, Impact).
- Live check L1 needs the station: agree the slot with QA first (HK-020, HK-024).
