# QA code review (HK-039): DR-3, the lean engine becomes the default, with the duplicate-decode fix

**Reviewed commit:** `75e7666654d54306ee1a24c406468e046250e9cf` (`feat/dr3-lean-default`, one commit on `main` `546ad125`, not pushed)
**Reviewed-commit:** 75e7666654d54306ee1a24c406468e046250e9cf
**Verdict:** APPROVED, with 5 minor notes
**Reviewer:** QA, 2026-11-26. Read: `native/ftz_decoder/ftz_decoder.c` and `.h` (the duplicate rule), `DecoderConfig.cs`, `DecoderEngine.cs`, `JsonConfigStore.cs` (the migration), `WebApp.cs` (the overlay), `Ft8LibInterop.cs`, `ft8_shim.h`, `Program.cs`, `web/js/decoderThreads.js`, `web/js/settings.js`, `web/settings.html`, `config.example.json`, the new `LeanEngineDuplicateRuleTests.cs` and the changed tests, against `dev-tasks/2026-11-26-dr3-lean-default-engine-and-duplicate-fix.md`.

## Tests QA ran (clean worktree at the commit, `D:\Projects\claude\_qa-scratch\dr3-review`, Release, whole projects, no `--filter`, HK-022)

- OpenWSFZ.Config.Tests: **Passed: 237, Failed: 0**.
- OpenWSFZ.Web.Tests: **Passed: 464, Failed: 0**.
- OpenWSFZ.Daemon.Tests: **Passed: 963, Failed: 0**.
- `DOTNET_PROCESSOR_COUNT=4`, OpenWSFZ.Ft8.Tests (5 m 41 s): **Passed: 910, Failed: 0** (includes the golden, determinism and the new `LeanEngineDuplicateRuleTests`).
- JavaScript, `node --test web/js/*.test.js`: **tests 131, pass 131, fail 0**.
- All equal the Developer's figures.
- From the Developer's report, not re-run by QA: ASan + UBSan fuzz (10,000 runs, determinism at 1/2/4/8/16 threads), `openspec validate --strict`, `check_version_docs.py` and `check_version_bump.py`, a live daemon rewriting a stored `classic` to `lean`. CI repeats ASan, Linux and macOS; `pre_merge_check` runs before any push.

## What was checked and found sound

- **D1, the default.** `DecoderEngineNames.Default` = `lean`; `DecoderConfig` and the constructor default follow it; `Parse` reads `classic` only for the word "classic" (any case, trimmed), so an absent key, a missing section and an unknown word read `lean`. The page's `DEFAULT_ENGINE`, the reset handler, the select's help text and `config.example.json` agree; the changed tests are the ones that pinned `classic` as the default (four files, each change a legitimate reversal).
- **D2, the migration.** `JsonConfigStore.Load` rewrites a persisted `classic` (case and spaces ignored) to `lean` once and sets `LeanEngineMigrationApplied`; any other loaded decoder section just gets the marker; a fresh install's section carries it already; the config POST overlay forces the stored value, so a request cannot set or clear it. One log line, no config content. After the marker an explicit `classic` persists (tests (a) to (f) of the task are present).
- **D3, the duplicate rule (native).** `ftz_dedup_select` runs over the round's hits in published order; a later same-payload hit (bit-identical in round 0, RR73-aware same transmission in a residual round) replaces an earlier one only if its score is **strictly** higher, otherwise the earlier survives, so a tie keeps today's rule. It compares `ftx_candidate_t.score`, the field the candidate search ranks by, through `hits[k].index`. The same-text rule (two payloads rendering alike in one round) replaces in place, only within the round (`s >= nres_before`), and only on a strictly higher score; a text from an earlier round stands. A replaced result is taken back out of the 12-bit-hash counters and the tier-B, ungated and CQ-AP counters through `ftz_h12_capture` / `ftz_h12_apply(-1)`, and its slot's payload, tier, round, score and re-encodability are overwritten, so the later rounds' subtraction reads the published result. The published order and the cross-round rule are unchanged; the new buffers are allocated and freed in the existing pattern.
- **D4, `kMinScorePass2`** is untouched.
- **D5, documents.** VERSION 1.1 (README and `REQUIREMENTS.md` cite it), a new FR with the changelog row after the previous one, the shim 20260079 with its two pure test exports added to `rebuild_shim.bat`; `libft8.dll` rebuilt.
- **HK-005 order:** the before screenshot (`dr3-lean-default-before.png`) precedes the change in the task order.

## Minor notes (none blocks)

1. **Ties will keep the lowest-frequency copy.** The sync score saturates for strong signals (the Developer measured 33 at two amplitudes), and equal scores keep the earlier, lower-frequency hit. If the 24 rows of LC-BASE section 5.1 are a strong signal plus a ghost about 100 Hz below it, a saturated tie still publishes the ghost. The one S40 replay after this review will show it; the rule is kept either way, as the Architect's spec says.
2. **A typo in `decoder.engine` now lands on `lean`.** By the task's wording and the `effort` precedent, but worth knowing: an operator who writes `"clasic"` gets the new engine silently.
3. **A deliberate `classic` saved before this release is migrated once.** That is the task's rule (the Settings page wrote `classic` into every saved config, so a stored `classic` cannot be told from a choice). The log line names the way back.
4. **The committed Linux `.so` and macOS `.dylib` are now one shim behind (20260078 against 20260079)** until CI's "commit rebuilt binaries" job opens its follow-up PR after the merge, as #292 did for 20260078. `pre_merge_check` will say so.
5. **`ftz_dedup_select` is quadratic in the round's hits** (about a thousand pairs at most per round); not a concern at the sizes seen, and it runs once per round.

## Next

`pre_merge_check` on this commit from a clean checkout (HK-006), then the push needs the Captain's go (HK-033). After it: the one optional lean S40 replay (170 cycles, about 5 minutes), reporting the count of "same text, other frequency" rows (was 14) and `rate` (was 81.52 %). Issue #294 stays open until that count is read.
