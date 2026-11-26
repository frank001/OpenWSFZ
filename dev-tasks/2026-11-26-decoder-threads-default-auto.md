# Developer task: the decoder thread count defaults to the most the PC supports (auto), and the Settings page stops freezing it

**Date:** 2026-11-26
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-25: "the default thread count = the max supported on the machine, the operator can lower it."
**Status:** Proposed. HK-011: `src/` and `web/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). Do not push, open a PR or merge; QA pushes.
**Branch:** `feat/threads-default-auto`, a child of `feat/threads-setting` (tip `fc4fb788`, reviewed APPROVED, CI green). The key, the control and the cap of 16 exist only there (HK-008).
**Test requirement (the Captain's rule, 2026-11-24):** unit tests, front-end tests in the existing style, one before and one after screenshot, and QA's review. No replay. Read the per-assembly "Passed: N" lines (HK-022).

**Reading to confirm with QA before you start if it is not obvious from the code:** QA reads "max supported on the machine" as `min(logical processors of the daemon PC, 16)`, the cap being the build's `MaxThreads`.

---

## 0. Why, with the data

Measured by QA (Slice 40, 170 cycles, same build, decodes identical at every count; `qa/decoder-rebuild/dr2e-result.md`): 2 threads `last_p95` 7,597 ms, `cpu_net` 9.90 CPU-s per cycle; 4 threads 4,374 ms, 10.89; 8 threads 2,706 ms, 12.24 (about +10 % and +12 % CPU per doubling). 16 threads: not measured yet. The Captain chose speed by default and lets the operator lower it.

Memory: about 32 MB per worker while subtracting, so up to about 514 MB at 16 workers (QA's review of `fc4fb788`).

Two defects the choice exposes in `fc4fb788`:

1. The default is the constant 2 (`DecoderConfig.DefaultThreads`), and the page shows 2 for an absent key.
2. **Saving the Settings page writes `threads: 2`, `engine: classic`, `effort: normal`** into the config (payload built at `web/js/settings.js` about :1503). So a default would be frozen the first time anyone saves anything, and a later change of default would never reach that install.

## 1. What to build

| Id | What |
|---|---|
| **D1 Auto in the config** | `decoder.threads`: **absent or 0 = auto.** Auto resolves at apply time to `min(Environment.ProcessorCount, MaxThreads)`, at least 1. A value 1 to 16 is explicit and respected. A value outside 0 to 16 is clamped with a warning as today (negative or above 16: clamped; do not turn it into auto). `DefaultThreads` becomes 0 (auto). Add a resolver next to `EffectiveThreads` (suggest `ResolveThreads(int processorCount)`, pure, so it is testable without the host); `EffectiveThreads` callers (`Program.cs` `SetLeanThreads`, the pump) use it with the host's `Environment.ProcessorCount`. The classic engine is unaffected. |
| **D2 Page shows the resolved value, stores nothing it was not asked to** | The input shows the number that is in effect: the stored explicit value, else the auto value (`min(processorCount, 16)`, from `processorCount` on `GET /api/v1/status`; if that is missing, show 2 as the old default and say nothing else). **Saving without touching the field must not write a number:** send `threads: 0` (or omit the key; the overlay keeps what is stored, HK-035). **Touching the field** (the operator types or steps it) writes that explicit number. If the operator types the number that equals the auto value, it is still an explicit choice and is stored. Next to the field a small "Auto" hint when it is auto: "Automatic: this PC has N logical processors, so N threads (maximum 16)." and a way back: "Reset to defaults" restores auto (not 2). |
| **D3 Engine and effort are not frozen either** | Same rule for `engine` and `effort`: a page save must not write `classic` / `normal` for a key the operator never touched. Send them only when changed (or when already present in the stored config, send the stored value). An absent key stays absent. This matters for DR-3 later: a default engine can only change for installs that never stored one. |
| **D4 Help text** | Replace the 2-vs-8 sentence with the three-point measurement above, once, with its limits: "On a 16-processor test PC replaying one 40 m night: 2 threads, last results about 7.6 s after decoding starts; 4 threads, 4.4 s; 8 threads, 2.7 s; CPU in total grows about 10 % each time the count doubles. Your PC will differ." Add the memory sentence: "Each worker needs about 32 MB while it subtracts signals, so 16 threads can use about 0.5 GB." Say plainly: "Automatic uses every logical processor up to 16. Lower it if this PC also runs other programs." Say it applies only with the lean engine selected. |
| **D5 Migration of an existing config** | An install whose config already holds `threads: 2` (written by an earlier page save, by `fc4fb788`) keeps 2 (explicit, respected). Do not guess that it was unintended. State in the report that the Captain's station may hold such a value and that he can press "Reset to defaults" to return to auto. No automatic rewrite. |
| **D6 Documents** | `REQUIREMENTS.md`: extend FR-108 (default auto, the cap, the not-frozen rule) **without writing any other FR number in prose** (Gate G3). OpenSpec change `lean-decoder` (tasks, delta spec) updated and validated `--strict`; `config.example.json` shows `threads` as 0 with a note if that file carries comments, otherwise unchanged. **VERSION:** none (the lean engine stays off by default; this changes only a setting that does nothing while `engine` is `classic`); run `check_version_bump.py` after committing. |

## 2. Task order (HK-005, checked by `tools/check_screenshot_task_order.py`)

1. **Screenshot, before:** the Advanced Decoder Settings block as at `fc4fb788` (Playwright, HK-007), under `dev-tasks/screenshots/`. **First, before any change.**
2. D1 to D6.
3. Tests (section 3).
4. **Screenshot, after:** the same block with the auto hint visible and the daemon running.

(Known: the HK-005 checker's complaint about the earlier task order is a false positive that is not in CI or `pre_merge_check`.)

## 3. Tests

1. **Config (C#):** `ResolveThreads` for processor counts 1, 2, 4, 8, 16, 17, 64 with threads 0 (expect 1, 2, 4, 8, 16, 16, 16); explicit 1, 6, 16 respected on a 64-processor host; explicit 20 clamped to 16 and negative clamped to 1 (D1); a config with the key absent reads as auto; `DefaultThreads == 0` asserted.
2. **Web (C#):** a POST that omits `threads` keeps a stored explicit value (overlay); a POST of 0 stores 0; out-of-range handled as D1 says.
3. **Front-end (JS), in the style of `decoderThreads.test.js`:** untouched page save sends no explicit number and does not add `engine` / `effort` that were absent; a touched field sends its number; a stored 6 is shown 6 and saved as 6; a stored 0 or absent shows the auto value from `processorCount` and the hint; a missing `processorCount` falls back to 2 without error; "Reset to defaults" restores auto; a changed value makes the page dirty, an untouched load does not.
4. **Nothing else changes:** native code, the decoder and the pump untouched; every existing suite green. Run the Config, Web and Ft8 projects separately and the JS runner, and quote each "Passed: N".

## 4. Out of scope

Changing the default engine (DR-3), physical-core detection (issue #290), a control for the classic engine's `subtractionMaxThreads`, any decoder or native change, a replay.

## 5. Report back

The commit SHA; the per-project "Passed: N" lines and the JS result; the two screenshot paths; what D1 does with a negative or oversize value; how D2 tells "touched" from "loaded" (name the mechanism); what the config of a fresh install looks like after one untouched save (paste the decoder block); anything that differs from the neighbouring controls' pattern.
