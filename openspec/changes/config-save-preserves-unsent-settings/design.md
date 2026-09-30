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

### D3.1: fields that exist only on unmerged branches (Architect note, 2026-09-30)

`decoder.subtractionEnabled` (on `feat/sub-feas-native-subtraction`, `DecoderConfig.cs`) and
`decoder.subtractionMaxThreads` (QA's speed-redesign change, `0` = auto) are not on `c3f42362`, so the
§0.1 audit could not see them. The Settings page sends neither, so today a save resets both.

- **Confirmed:** T4 and T5 MUST enumerate `AppConfig` **by reflection at test time**, never from a
  hand-written field list, so they cover both fields whichever change merges second. A hand-written
  list is a review-blocking defect. The Developer adds one guard test asserting the enumeration
  reaches every public property of `DecoderConfig` (count taken by reflection, compared with the
  leaves the fixture set).
- **`decoder.nhard40MigrationApplied` MUST keep working when `DecoderConfig` gains fields.** The force
  from the store is a per-key override applied after the merge, so it must name only that key and must
  not rebuild the record positionally or copy a fixed field list. T10 stays valid unchanged.
- Part E's `decoder.*` watch prefix already covers both new keys with no code change, which matters for
  SUB-FEAS flag-OFF/flag-ON controls.
- Whichever change merges second must re-run T4/T5. Record that in its own handoff.

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

Not enumerated yet, and must not be guessed. Procedure for the Developer (task 2.4): after Part A, run
`OpenWSFZ.Web.Tests`, and for **every** test that fails or changes, add a row here with the test name,
what it asserted, why the old assertion was a symptom of the defect, and the new assertion. No test is
rewritten without a row (HK-022). Expected candidates, from a first read: the `ConfigApiNullGuardTests`
group and the test named `7.2m` (a body with no `decoder`).

## D7: Part E, config-drift module (revised by the Architect's ruling, 2026-09-29)

- A small standalone module `qa/config_drift.py`, with its own tests, that: reads `GET /api/v1/config`,
  takes a start snapshot, and on each poll (interval configurable, default 60 s, at most 300 s) compares a
  key list (at minimum `cycleAudioArchive.mode`, `cycleAudioArchive.directory`, `decodingEnabled` and all
  `decoder.*`). On a mismatch it writes a timestamped `CONFIG-DRIFT` line to a log and returns a row for
  the run report. It **never** restores.
- Values in the drift line are limited to the same allowlist as Part D (HK-037): paths for everything else.
- Wiring (as built): **no existing tool is edited.** The endurance supervisors are dated, per-run QA
  scripts, so the module is run detached beside a run (`qa/rr-study/RUNBOOK.md` §2.1) instead of being
  spliced into them. Drift policy is recorded there: continue and report by default, `--abort-on-drift`
  (exit 3) only for a battery that any drift invalidates.
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
