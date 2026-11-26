# Developer task: DR-3, the lean decoder becomes the default engine, with the duplicate-decode fix inside it

**Date:** 2026-11-26
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** the Product Owner (the Captain), 2026-11-26, as recorded in the Architect's spec `docs/decoder-rebuild/spec-dr2-lean-decoder.md` §4 (`arch/decoder-rebuild` `ef62c8cc`): "both at once, fix inside DR-3", after LC-BASE (`qa/rr-study/results/2026-11-26-lc-base/lc-base-result.md`, §5.1).
**Status:** Proposed. HK-011: `src/`, `web/` and `native/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). Do not push, open a PR or merge; QA pushes.
**Branch:** `feat/dr3-lean-default`, off `main` (`546ad125` or later: the whole lean chain, PR #291, is on `main`). Start from a fresh `git fetch origin`.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay by you (QA runs the one optional S40 replay afterwards, section 4). Read the per-assembly "Passed: N" lines (HK-022).

---

## 0. Why, with the data

- **The default.** The Captain wants the lean decoder to be the engine every install runs. On recorded audio (LC-BASE) it decodes within about one decode per cycle of classic (rate −2.88, −1.02 and +0.78 pp on three slices) at 53 to 70 % of the CPU (lean 16 threads, classic 8) and about a third of the latency (last batch p95 2.1 s against 6.2 to 7.3 s).
- **The migration.** Before `9027616e` the Settings page wrote `engine: "classic"` into every saved config, and the daemon's config writer still serialises it after any save. A default flip alone would leave every such install on classic. QA's review notes on `fc4fb788` and `9027616e` named this.
- **The duplicate fix.** LC-BASE §5.1: on S40 and H40 lean published 14 and 10 decodes whose text WSJT-X decoded in the same cycle at a different frequency (classic: 0, and 0 on H20). **All 24 are 98 to 103 Hz *below* WSJT-X's frequency, all round 0, tier A.** The Architect's hypothesis (not a finding): round 0 decodes the real signal and a second copy about 100 Hz away, and lean keeps the lowest-frequency copy of two same-payload hits.

## 1. What to build

| Id | What |
|---|---|
| **D1 Default engine = lean** | `DecoderConfig`: the default of `Engine` becomes `lean` (`DecoderEngineNames`). An absent key, a missing `decoder` section and a fresh install read `lean`. An unknown word reads as the default (today it reads `classic`: say in the report which you chose and why; the spec only says the default changes). The Settings page's Engine select shows `lean` for an absent key, "Reset to defaults" restores `lean`, and its help text no longer says the lean engine is off by default (`web/settings.html`, `web/js/decoderThreads.js` `DEFAULT_ENGINE`, `web/js/settings.js`). `config.example.json` shows `engine` as `lean`. |
| **D2 Migrate a stored `classic` once** | A one-time migration with a marker, exactly in the pattern of the `nhard` and subtraction migrations (`JsonConfigStore.cs`: the markers `Nhard40MigrationApplied` / `SubtractionOnMigrationApplied`, the load-time migrations about `:270-350`, and the fresh-config line about `:437`): a config that holds `decoder.engine: "classic"` and does not yet carry the new marker (suggest `decoder.leanEngineMigrationApplied`, server-owned like the others, not editable through the config POST overlay: see `ConfigOverlay.cs`) is rewritten to `lean` and the marker set; **after the marker, an explicit `classic` is respected** and never touched again. A config that holds no engine key needs no rewrite but gets the marker. A fresh install's new config sets the marker already (as the line about `:437` does for the others). The migration runs once, logs one line (aggregates only, no config content), and the rewritten file is saved. |
| **D3 The duplicate fix (native, lean only)** | Today, in each round `ftz_decode_cycle` sorts its hits by frequency (`ftz_hit_cmp` at `native/ftz_decoder/ftz_decoder.c:451`, `qsort` at `:1081`) and publishes the **first** of two hits with the same payload (round 0) or the same transmission (residual rounds: `ftz_payload_same_qso`), and then the first of two with the same rendered text (the loop from `:1117`), so **the lowest-frequency copy always wins**. **New rule:** among two or more hits **in one round** with the same payload (and, for the text de-duplication, the same rendered text), publish the one with the **highest candidate sync score**, at its own frequency and time; **equal scores fall back to today's order** (ascending frequency, then the existing tie-breaks). Everything else stays: the order in which results are published, the cross-round rule (a decode from an earlier round stands), the effort and fit-skip rules, and determinism: the order stays total, the same input gives byte-identical output at 1, 2, 4, 8 and 16 threads, and **the existing determinism and golden tests must pass unchanged.** The candidate's sync score is reachable from the hit through its `index` into the candidate arrays (`ftz_hit_t.index`); check that the score you compare is the one the candidate search ranks by, and say which field. This is the only native change: no change to the candidate search, the fit, tier B or the XC stage. |
| **D4 `kMinScorePass2` stays** | The lean engine reads it as the minimum candidate score of the residual search (`ftz_decoder.c:679`). It stays a setting, now and after DR-4. Do not drop, ignore or rename it. |
| **D5 VERSION and documents** | **VERSION one minor** (`main` is 1.0, so 1.1; run `check_version_docs.py` and `check_version_bump.py`: README and `REQUIREMENTS.md` cite the version). `REQUIREMENTS.md`: a **new FR for the lean engine** (the next free number in the FR table; check it, FR-108 is the last at `546ad125`) that states the default, the migration and the duplicate rule of D3; the changelog row is the next one after 1.76. **Do not write any other FR number in prose** (Gate G3 counts every `FR-nnn` string; an unassigned one fails it). The OpenSpec change `lean-decoder` gets a section for DR-3 (tasks, delta spec) and passes `openspec validate --strict`. The shim version moves (native code changed), `libft8.dll` rebuilt as in 2e. |

## 2. Task order (HK-005, checked by `tools/check_screenshot_task_order.py`)

1. **Screenshot, before:** the Settings page's Advanced Decoder Settings block as it is on `main` (Playwright, HK-007), under `dev-tasks/screenshots/`. **First, before any change.**
2. D1 to D5.
3. Tests (section 3).
4. **Screenshot, after:** the same block showing the default `lean`.

## 3. Tests

1. **Migration (C#, Config):** (a) a stored `engine: "classic"` without the marker loads as `lean` with the marker set, and the saved file carries both; (b) an explicit `classic` **after** the marker is kept across a load, a save and a reload; (c) no engine key: reads `lean`, marker set; (d) a fresh install's config has `engine` `lean` and the marker set; (e) the marker cannot be set or cleared through the config POST overlay (as for the other server-owned markers); (f) the migration runs once: a second load changes nothing.
2. **Defaults (C# and JS):** `DecoderConfig` default `lean`; an unknown engine word reads as D1 says; the Settings page shows `lean` for an absent key, posts nothing for an untouched engine select, and "Reset to defaults" restores `lean` (`web/js/decoderThreads.test.js` style).
3. **The duplicate rule (native, at the selection level):** **two hits with the same payload where the higher-score hit has the HIGHER frequency: the higher-score one must be published, at its own frequency** (today's code would publish the lower one); two hits with equal scores: today's order (lower frequency first); the same for the same rendered text from two different payloads; a hit of an earlier round still wins over a later round's copy. Add a lean test at the C# level too if the native selection cannot be reached directly. **The existing golden, determinism (1, 2, 4, 8, 16 threads) and lean tests pass unchanged**; the ASan + UBSan fuzz (10,000 runs) still passes.
4. **Nothing else changes:** run the Config, Web, Ft8 and Daemon projects separately and the JS runner; quote each "Passed: N". Also run the Ft8 project at `DOTNET_PROCESSOR_COUNT=4` (the golden must not depend on the host).

## 4. After your hand-back (QA, not you)

HK-039 review, `pre_merge_check`, then QA's **one optional replay, reported only:** the lean arm on S40 (170 cycles, about 5 min), scored as LC-BASE. It reports the count of "same text, other frequency" rows (**was 14**) and `rate` (**was 81.52 %**). If the count is not lower, the Architect's hypothesis is wrong; the rule is kept anyway because it is the more sensible one. Push and merge need the Captain's go.

## 5. Out of scope

DR-4 (deleting the classic decoder: not requested), the crowded-signal decoder work (decoder changes wait until DR-3 merges, spec §6), the thread count, physical-core detection (issue #290), the ~100 Hz offset beyond this rule (the cause is a hypothesis), any change to the candidate search, fit, tier B or XC.

## 6. Report back

The commit SHA; the rebuilt `libft8.dll` SHA256 and the shim number; the per-project "Passed: N" lines (Ft8 also at 4 processors) and the JS result; which sync-score field the duplicate rule compares and how ties and the total order are kept; what an unknown `engine` word reads as and why; the marker's name and where it is owned; the two screenshot paths; anything that differs from the neighbouring migrations' pattern.
