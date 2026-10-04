# Developer handoff: an absent key inside a present config section reads default(T) — fix CatConfig, PttConfig, DecodeLogConfig, and add the regression tests

**Date:** 2026-10-04. **From:** QA. **To:** Developer. **Priority:** high, right after PR #208 merges and before the Stage B B2 merge (the Architect's order). **Approved:** Architect, 2026-10-04 12:5xZ by his clock (fix plan as below). **Issue:** #209 (the audit table is in it). `src/` change (HK-011): no `native/`, no shim.
**Branch:** `feat/config-absent-key-fix` off `origin/main` **after #208 has merged** (the DecoderConfig fix and `EarlyDecodeDefaultTests` come with it). QA tells you when. NEVER commit to `main`.

## 1. The defect (read #209 first)

System.Text.Json's source generator builds `init`-only properties through a synthesised parameter path, so for a record **without** a `[JsonConstructor]`, a key that is absent from a *present* JSON section reads `default(T)` (null / 0 / false), not the property initialiser. `JsonConfigStore.Load` guards only wholly absent sections. QA's mechanical audit (real `ConfigJsonContext`, real `JsonConfigStore`) found three affected records:

- `PttConfig`: `Method`, `SerialPort`, `SerialLine` read null; `LeadTimeMs`, `TailTimeMs`, `WatchdogTimeoutMs` read 0 (defaults `"AudioVox"`, `"COM7"`, `"Rts"`, 50, 50, 20000). `PttWatchdog.Arm(0, …)` creates a `Timer` with `dueTime` 0, which fires at once and force-releases right after keying: fails safe, TX unusable.
- `CatConfig`: `RigModel`, `SerialPort`, `RigctldHost` null; `BaudRate`, `RigctldPort`, `PollIntervalSeconds` 0 (defaults `"SerialCat"`, `"COM6"`, `"127.0.0.1"`, 9600, 4532, 1).
- `DecodeLogConfig`: `Path` null (default `"ALL.TXT"`).

The other seven records (`TxConfig`, `RemoteAccessConfig`, `DecoderConfig` after #208, `DecodeNoiseSuppressionConfig`, `ExternalReportingConfig` and `ExternalReportingTarget`, `CycleAudioArchiveConfig`, `LoggingConfig`) already have a `[JsonConstructor]` with default parameters and are clean: copy their pattern exactly (the file comments cite it as Lesson 6 / D-WFC-001, see `LoggingConfig.cs`).

## 2. Actions

1. **Fix** `CatConfig`, `PttConfig`, `DecodeLogConfig`: an explicit `[JsonConstructor]` whose parameters carry the intended defaults (parameter names equal the property names with a lower-case first letter, so the JSON binding is unchanged), assigning every property. **No behaviour change for a complete config**: the serialised JSON (property names, order, values) of an existing config must come out byte-identical (the existing T4/T5 reflection tests and a round-trip test pin it). Keep `CatConfig.LastPolledFrequencyMHz` (nullable, default null) as a parameter too. Do not touch any other record.
2. **ONE reflection-driven regression test** in `tests/OpenWSFZ.Config.Tests`: for **every** config record type registered in `ConfigJsonContext` (enumerate the `[JsonSerializable]` attributes by reflection, so a newly added record is covered without editing the test), deserialise `"{}"` through `ConfigJsonContext.Default` and compare each public property with the same property of a default-constructed instance (`Activator.CreateInstance` with `BindingFlags.OptionalParamBinding`; QA's program in `artefacts/20261004_config_absent_key_audit/Program.cs` is the model; serialise both property values to JSON to compare). `AppConfig` is the one deliberate exception: its section properties read null for an absent key and `JsonConfigStore.Load` guards exactly those, so assert **through the store** for `AppConfig` instead (an empty file loads every non-nullable section non-null with its defaults). The test must **fail** when a property with a non-default initialiser is added to a `[JsonConstructor]` record without being a constructor parameter (QA mutates it).
3. **Store-level tests** (real `JsonConfigStore` load path): a stored config with only `{"ptt":{"method":"SerialRtsDtr"}}`, only `{"cat":{"enabled":true}}`, only `{"decodeLog":{"enabled":true}}` loads each section with the documented defaults in the keys not named (including `WatchdogTimeoutMs` 20000), and an explicit `0` or `null` that IS named is kept as the user wrote it (an explicit value is respected).
4. Test names carry an `FR-` or capability prefix per gate G3 (check `REQUIREMENTS.md` for the FR these configs belong to: PTT FR-056, CAT FR-031, decode log FR-027/028); `REQUIREMENTS.md` gets a one-line note under the PTT / CAT / decode-log rows if the traceability gate needs it. **`VERSION` bump** if the gate wants one (this is a bug fix; check `tools/check_version_bump.py origin/main` and the proposal rules; if no OpenSpec proposal is needed for a bug fix, say so).

## 3. Run and report

Full unfiltered `dotnet test OpenWSFZ.slnx` and `node --test web/js/*.test.js`: quote the exact lines and counts (HK-022); bracket the station config's mtime. Tell QA before the full suite. Report: commit hash, every file changed, the test names, the **mutation you ran** on the reflection test (add a non-ctor property with a non-default initialiser to a record: it must fail), the byte-identity result of the JSON round trip, and anything you could not do. **Do not read or write the real `%APPDATA%\OpenWSFZ\config.json`.**

## 4. What QA does after

QA reruns the mechanical audit (expects 0 divergent on every type), mutates the regression test, reads the diff, runs the full suite on a clean worktree, and (as always after a config change) reads the station's real `config.json` once after the merge.
