# Developer handoff: SUB-FEAS subtraction ON by default, with a one-time migration of existing installs

**Date:** 2026-10-02. **From:** QA. **To:** Developer. **Priority:** medium. **Spec (Architect, Captain's decisions of 2026-10-02):** `qa/rr-study/2026-10-02-0710-architect-to-qa-spec-sub-feas-default-on.md`, which lives on the branch `arch/subtraction-feasibility` and is not on `main`; read it with `git show arch/subtraction-feasibility:qa/rr-study/2026-10-02-0710-architect-to-qa-spec-sub-feas-default-on.md`. `src/` is touched, so a separate Developer session does it (HK-011). **Only QA pushes.** Prerequisite met: #199 is merged (PR #200), so the marker pattern below is the corrected one.

## 1. What to build (spec section 1, C1 to C5)

| # | Change | Where |
|---|---|---|
| C1 | Code default `subtractionEnabled` **true**: both the constructor parameter and the property initialiser. | `src/OpenWSFZ.Abstractions/DecoderConfig.cs` (:40 and :133 at `9bade2bc`; re-read the lines on current `main`). Update the XML doc that says "Default false". |
| C2 | One-time migration on load: a persisted `subtractionEnabled: false` becomes `true` **once**, with a new server-owned marker `subtractionOnMigrationApplied` (default **false** in `DecoderConfig`, like `Nhard40MigrationApplied`, so a legacy file without the key is migrated), written back to disk immediately. After that an operator's OFF persists. | `src/OpenWSFZ.Config/JsonConfigStore.cs`, next to the nhard 40 block |
| C3 | The POST overlay treats the marker as server-owned (forced from the store, as `nhard40MigrationApplied` is). | `src/OpenWSFZ.Web/WebApp.cs` (~:515 to 530), `ConfigOverlay.cs` |
| C4 | One stderr line on migration, as for nhard 40: the setting, old and new value, and how to turn it off. | `JsonConfigStore.cs` |
| C5 | Requirements: the flag FR (FR 9.4 per the merge) says default ON plus the migration; **VERSION 0.53 to 0.54**; README and any user-facing doc say the setting exists, defaults ON, and how to turn it off. | `REQUIREMENTS.md`, `README.md`, `VERSION` (G9a/G9b) |

**Unchanged, do not touch:** `subtractionMaxThreads` stays `0 = auto`; batch 2 stays out of the QSO controllers; two-stage publish stays as built; the native DLL stays as it is (`git diff --stat origin/main -- native` must be empty).

## 2. 🔴 The marker rule (this is the #199 lesson, built in from the start)

The marker means **"no migration is pending for this install"**. Take the corrected nhard 40 code as it is on `main` and follow it exactly:

1. **`Load`:** when a `decoder` section exists and `subtractionOnMigrationApplied` is false: if `subtractionEnabled == false`, set it true (the migration); **in either case set the marker true and write it back once** (`WriteAtomic`). Idempotent: a second `Load` writes nothing. A config is migrated at most once in its life, and its first load under 0.54 is that once. If both this and the nhard 40 migration fire on one load, write the file **once**.
2. **No config file, or no `decoder` section:** a section created from nothing (`CreateDefault`, `SaveAsync`, the config POST) gets the marker **true**, as #199 did for nhard 40. A fresh install must never carry marker false.
3. A POST over an existing section keeps the **stored** marker, whatever the client sends. A POST that creates the section where the store had none stores marker **true**.
4. Do not change the marker's `DecoderConfig` default (false): a legacy file without the key must still deserialise to false so a genuine legacy OFF is migrated once.
5. `git grep -n "new DecoderConfig" src` for any other place that builds a section from `null`; the same rule applies.

## 3. Acceptance (the spec's rows, each a test; QA may refuse a row on HK-025(k) grounds)

| Row | Predicate |
|---|---|
| A1 | No config file: loaded `SubtractionEnabled == true`, marker true on disk after the first load |
| A2 | Legacy file `subtractionEnabled:false`, no marker: `true`, marker true, written to disk, one stderr line |
| A3 | File `false` plus marker true: stays `false` across 2 reloads |
| A4 | Fresh install, POST sets `false`, reload twice: stays `false` (the #199 trap, for this flag) |
| A5 | A POST body carrying `subtractionOnMigrationApplied` (either value) cannot change the stored marker |
| A6 | The existing config-save tests T4 and T5 (reflection-enumerated) pass with the new field |
| A7 | CI green on all three platforms (A8, the live check on the station's config, is QA's, not yours) |

Add a second-`Load`-writes-nothing test (content and modification time unchanged) and a test that a legacy `false` plus a legacy nhard `60` migrate in one write. Existing tests that encode the old default (`false`) must be changed **deliberately**: list every one in your report with the old and new assertion and why, so QA can check nothing was weakened. Test-first: the new tests fail on the base, then pass.

## 4. Branch, checks, report

- Cut `feat/sub-feas-default-on` from `origin/main` (`git fetch` first). Commit locally; **no push** (only QA pushes).
- Unfiltered `dotnet test OpenWSFZ.slnx -c Release` on **Windows** and on **WSL Debian** (exact commands and per-assembly counts, HK-022). Export the WSL copy with `git archive` to an ext4 path and run it **without `nohup`** (the FR-059 SIGHUP test fails under nohup, a launch artefact). Re-run unchanged on the known `CS2012` or `StaticWebAssets` lock.
- Run and quote `python tools/check_test_delay_sync.py`, `python tools/check_version_bump.py origin/main` (commit first, it reads git), `check_version_docs.py`, and `openspec validate --all --strict`.
- Report the changed existing tests, the checks above, and `git diff --stat origin/main -- src/ native/` (native empty).
- 🔴 Do not run tests or builds while a QA timing run or the station is live; ask QA first (the CPU is shared).

## 5. References

- Spec, sections 1 to 3 (above); issue #199 and `dev-tasks/2026-10-02-nhard40-marker-trap-199.md` (the corrected pattern); PR #200.
- `src/OpenWSFZ.Config/JsonConfigStore.cs` (nhard 40 block), `src/OpenWSFZ.Web/WebApp.cs`, `src/OpenWSFZ.Abstractions/DecoderConfig.cs`.
- Standing rules: HK-011, HK-022, HK-035.
