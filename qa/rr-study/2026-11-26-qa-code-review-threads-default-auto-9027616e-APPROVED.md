# QA code review (HK-039): the decoder thread count defaults to automatic, and the Settings page stops freezing it

**Reviewed commit:** `9027616ef4f720ec4a6473502acc21be5097b577` (`feat/threads-default-auto`, one commit on `feat/threads-setting` `fc4fb788`, not pushed)
**Reviewed-commit:** 9027616ef4f720ec4a6473502acc21be5097b577
**Verdict:** APPROVED, with 3 minor notes
**Reviewer:** QA, 2026-11-26. Read: `DecoderConfig.cs`, `Program.cs` (both `SetLeanThreads` calls), `Ft8Decoder.cs`, the clamp in `WebApp.cs`, `web/js/decoderThreads.js`, `web/js/settings.js`, `web/settings.html`, the tests, `REQUIREMENTS.md` FR-108 and its changelog row 1.75, `openspec/changes/lean-decoder/tasks.md` section 10, against `dev-tasks/2026-11-26-decoder-threads-default-auto.md`.

## Tests QA ran (clean worktree at the commit, `D:\Projects\claude\_qa-scratch\threads-auto-review`)

- OpenWSFZ.Config.Tests (whole project): **Passed: 227, Failed: 0**.
- OpenWSFZ.Web.Tests (whole project): **Passed: 461, Failed: 0**.
- `DOTNET_PROCESSOR_COUNT=4`, OpenWSFZ.Ft8.Tests (whole project, 5 m 49 s): **Passed: 901, Failed: 0**.
- JavaScript, `node --test web/js/*.test.js`: **tests 131, pass 131, fail 0**.
- All four equal the Developer's figures. No `--filter` was used (whole projects, so nothing is silently filtered out, HK-022).
- Not re-run by QA: `openspec validate --strict`, `check_version_bump.py` (Developer: valid, no bump), the screenshots' contents beyond their presence.

## What was checked and found sound

- **D1, auto in the config.** `AutoThreads` 0 and `DefaultThreads` 0; the pure `ResolveThreads(configured, processorCount)` gives `min(processors, 16)` with a floor of 1 for 0, and clamps any other value to 1 to 16 (a negative value is 1, never auto). Both `SetLeanThreads` calls in `Program.cs` (start-up and `OnSaved`) use it with `Environment.ProcessorCount`, so a later save re-resolves. `Ft8Decoder`'s own initial value is auto. The config test pins processor counts 0, 1, 2, 4, 8, 16, 17 and 64 and explicit 1, 6, 16, 20, -5.
- **D2, the page.** `decoderThreadsLoaded`: a stored integer other than 0 is explicit (shown clamped to 1 to 16); absent, 0 or non-numeric is auto and shows `min(processorCount, 16)`, or 2 when the count is missing (no hint then). The `_decoderThreadsAuto` flag is cleared only by the field's `input` event, which a programmatic `.value` assignment does not fire, so a load or a reset never counts as a touch; typing the auto number is still an explicit choice. An untouched save posts 0; a stored 6 is shown and posted as 6. The dirty snapshot carries the `auto:`/`set:` prefix, so an untouched load is clean. "Reset to defaults" restores auto, not 2.
- **D3, engine and effort.** `decoderChoicePayload`: a changed select posts the new word, an unchanged one posts the stored word back (an unknown word is kept) or nothing when the key was never stored. Correct at the page level.
- **D4, the help text.** The 2, 4 and 8 thread measurement, the "about 10 % per doubling" sentence, the memory sentence (about 32 MB per worker, about 0.5 GB at 16), "automatic uses every logical processor up to 16" and the lean-only sentence are all present.
- **D5, an existing `threads: 2`** is explicit and is respected; no automatic rewrite. The server keeps 0, clamps a negative value to 1 and an oversize one to 16 with a warning (test table: 0 stored as 0, -3 and -1 as 1, 17 and 64 as 16, 9 kept), and a POST that omits `threads` keeps the stored value (HK-035 overlay, tested with a stored 6 and an `effort`-only body).

## Minor notes (none blocks)

1. **D3 holds at the page level only.** The daemon's config writer still serialises `engine: "classic"` and `effort: "normal"` into the file after any save (`DefaultIgnoreCondition.Never`, pinned by an existing test), so an install that has saved anything still has `engine: classic` stored. This is what the Developer reported. DR-3's migration (a stored `classic` becomes the new default) is still required; the task's wording "an absent key stays absent" is true only for what the page posts, not for the file. QA accepts this and keeps it as a DR-3 requirement.
2. **A cleared field means automatic.** An empty or non-numeric entry in the number input posts 0, so clearing the field and saving silently returns the setting to auto. Reasonable, and consistent with the hint, but the help text does not say it.
3. **Old API clients.** A client that posted `threads: 0` expecting it to mean "one thread" (the clamp until `fc4fb788`) now stores auto. The only API client is the Settings page and `fc4fb788` is unpushed, so no one is affected; noted for the record.

## Next

`pre_merge_check` on this commit from a clean checkout (HK-006), then the push needs the Captain's go (HK-033). The lean chain (`feat/lean-2b` to `feat/threads-setting`, now `feat/threads-default-auto`) still has no PR; DR-3 is not requested.
