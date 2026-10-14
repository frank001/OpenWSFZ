# Developer handoff: #122 step 4 — `decoder.earlyDecodeEnabled` ships with the default **true** (the Captain's decision)

**Date:** 2026-10-04. **From:** QA. **To:** Developer. **Priority:** high (it blocks the step-4 merge). **Authorised:** the Captain, 2026-10-04 about 11:10Z in the Architect's window ("default on"), and **confirmed to QA directly in QA's window** ("default on confirmed"). Architect's note: spec §0c on `arch/122-latency` (`1aab93a9`) and QA's relay of 11:10Z.
**Branch:** your `feat/122-step4-early-decode-panel` (tip `ca8e3118`). Commit there; QA merges it into the PR branch `qa/122-step4-merge` (PR #208). NEVER commit to `main`. This is `src/` (HK-011); **no `native/` change, no new shim number**, no `VERSION` change (0.56 stays).

## 1. What changes

`DecoderConfig.EarlyDecodeEnabled` (`src/OpenWSFZ.Abstractions/DecoderConfig.cs`, the init property `= false`) becomes `= true`, with its XML doc, the `Default`/constant (if one exists), and every place that says "default false" updated. `EarlyDecodeCutSeconds` stays 2.0. Nothing else in the behaviour changes: with the flag true the early decode, panel and gate behave exactly as the A3 live run (flag ON hours) measured.

## 2. Check first (HK-035, read before you change)

1. **Deserialisation of an absent key.** A stored `config.json` with a `decoder` object that has no `earlyDecodeEnabled` key must come out **true** (property initialiser), and one with an explicit `false` must stay false. Confirm that `DecoderConfig` really is a plain record with init properties (no `[JsonConstructor]` with parameters that would zero an omitted key, the Lesson 6 / D-WFC-001 pattern in `LoggingConfig.cs` / `CycleAudioArchiveConfig.cs`), and **write the two tests** (absent key ⇒ true, explicit false ⇒ false) through the real `ConfigStore` load path, not only the record.
2. **A config with no `decoder` block at all** (the station's file today has one, but an older file might not): `configStore.Current.Decoder ?? new DecoderConfig()` in `Program.cs` (the framer provider) must give true. Test it.
3. **The partial POST** (config overlay, FR-074): a POST that does not name the field leaves it as it was **including when it is true**; a POST of `{"decoder":{"earlyDecodeEnabled":false}}` turns it off and persists. (Existing 7.2 test, extended to the true default.)
4. **The Settings page** (`web/settings.html`, `web/js/settings.js`): the checkbox must show the **stored** value (checked for a station that has no stored key), and the posted object keeps exactly the fixture's keys (the `settings.js` fixture test). Update the fixture if it lists the default.

## 3. Tests and text to update (the default flip touches these)

- Tests that relied on the default being false: `tests/**` for `EarlyDecodeEnabled`, `earlyDecodeEnabled`, `DefaultEarlyDecode`, the "defaults" test of 7.2, the T4/T5 reflection config tests, the A1 flag-OFF characterisation (`EarlyDecodeDaemonTests` 5.4a and any config-driven one): they must now **set `false` explicitly** where they mean "flag OFF" and assert the new default `true` where they assert the default. The pump characterisation (5.4a) is delegate-driven and probably unchanged; say so in the report.
- `REQUIREMENTS.md` **FR-083** (default now true; the row text), the OpenSpec change `decode-early-batch-panel`: `proposal.md`, `design.md` D8 and D9 (**"with the flag false nothing early exists" stays true as a statement about the OFF state; the DEFAULT sentence changes**), `specs/early-decode/spec.md` (the default-OFF requirement becomes default-ON with an explicit-false scenario), `tasks.md` 7.1/7.2/9.7. Keep `openspec validate decode-early-batch-panel --strict` valid (QA re-runs `--all`).
- User-facing text: `README.md` and the Settings helper text ("defaults ON", what *early* and *unconfirmed* mean, how to turn it off). The proposal's `**User-facing:** yes` stays.
- The `DecoderConfig` XML doc and the `Program.cs` comment ("read once per window; ... default") .

## 4. Run and report

Full unfiltered `dotnet test OpenWSFZ.slnx` and `node --test web/js/*.test.js`: quote the exact lines and the counts (HK-022); bracket the station config's mtime (`%APPDATA%\OpenWSFZ\config.json`). The PC is free (no QA timing job is running); tell QA before the full suite as usual. **Do not run A3 or any live run: QA owns them.** Report: the commit hash, every file changed, the tests added (names), the two deserialisation tests' results, and anything you could not do.

## 5. What QA does after (not yours)

Re-merge into `qa/122-step4-merge`, re-run A5 (Playwright: the Settings checkbox default, early rows with a default config), `live_verify_9_axes.py` is not affected (the isolated config in that script has no early key ⇒ now ON: QA re-runs it once to prove the filter result is unchanged with the flag at its new default), and **after the merge reads the station's real `config.json`**: no stored key means ON; an explicit false would silently stay OFF and QA reports it.
