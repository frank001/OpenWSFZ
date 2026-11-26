# Developer task: an operator setting for the decoder's thread count (and the lean engine's engine and effort)

**Date:** 2026-11-25
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-25: "I'd like a setting that an operator can choose in the settings how much threads to use. That way the operator is in control; they know their hardware, we don't."
**Status:** Proposed (amended 2026-11-25 with D7, the cap of 16). HK-011: `src/`, `web/` and `native/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). Do not push, open a PR or merge; QA pushes.
**Branch:** `feat/threads-setting`, a child of `feat/lean-2e` (tip `57bda0eb`, reviewed, APPROVED, CI green). The settings it exposes (`decoder.threads`, `decoder.engine`, `decoder.effort`) exist only on that branch, so this change stacks on it (HK-008).
**Test requirement (the Captain's rule, 2026-11-24):** unit tests, front-end tests in the existing style, one before and one after screenshot, and QA's review. No replay. Run tests per project (HK-022) and read the per-assembly "Passed: N" lines.

---

## 0. Why

The lean decoder's time to the last batch depends on how many worker threads it may use, and so does its CPU. QA's replay of the same build and the same 170 cycles on a 16-processor PC (`qa/decoder-rebuild/dr2e-result.md`, addendum) read: **2 threads** `last_p95` 7,597 ms, `cpu_net` 9.90 CPU-s per cycle; **8 threads** `last_p95` 2,706 ms, `cpu_net` 12.24 CPU-s (24 % more); the decodes were identical. Which is better depends on the operator's PC and what else it runs, so the operator chooses. Today `decoder.threads` exists (1 to 8, default 2, `DecoderConfig.cs:106`, step 2a) but only in the config file and the API; the Settings page has no control for it, nor for `decoder.engine` and `decoder.effort`.

## 1. What to build

| Id | What |
|---|---|
| **D1 Threads control** | In the Settings page's "Advanced Decoder Settings" (`web/settings.html`, the `<details id="advanced-decoder-settings">` block, fields at lines 318 to 420 of the page at `57bda0eb`), a number input for `decoder.threads`, range **1 to 16** (D7), step 1, with a label and help text. **Default shown when the key is absent: 2** (the code default; do not change the default in this task). Wire it exactly as the neighbouring decoder controls are: the dirty-state snapshot, the pre-fill on load, the payload on save, and "Reset to defaults" (`web/js/settings.js`: the controls at about :142 to :160, the snapshot at about :411 to :418, the pre-fill at about :960 to :967, the payload at about :1458 to :1471, the reset at about :1209 to :1220). The POST is an overlay (HK-035): send `threads` so a change reaches the daemon, and a page that has not touched it must not overwrite a value set elsewhere. Takes effect on the next decode cycle (`Program.cs` already applies `SetLeanThreads` on every config save). |
| **D2 Say how many processors the PC has** | The operator "knows their hardware", but the browser may be on another machine (remote access exists), so `navigator.hardwareConcurrency` is the wrong number. Expose the **daemon host's** logical processor count (`Environment.ProcessorCount`) read-only on an existing GET the Settings page already calls (your choice of endpoint; say which), and show it in the help text: "This PC has N logical processors." |
| **D3 Help text** | Say plainly: more threads show the lean decoder's results sooner and use more CPU in total; fewer threads are gentler on a PC that also runs other things. Give the measurement as such, once, with its limits: "On a 16-processor test PC replaying one 40 m night: 2 threads, last results about 7.6 s after decoding starts; 8 threads, about 2.7 s, with about 24 % more CPU in total. Your PC will differ." Say it applies **only when the lean engine is selected** (D4); the classic engine ignores it. Say the maximum is 16. |
| **D4 Engine and effort controls** | Because `decoder.threads` does nothing on a default install (the default engine is `classic`), add two selects in the same block: **Engine** (`classic` default, `lean`) for `decoder.engine`, and **Effort** (`normal` default, `fast`) for `decoder.effort`, wired like D1, with help text (lean: the new decoder, off by default; effort: `fast` = no tier B and one subtract-and-retry round, lean only). This is included so an operator can actually try the lean engine; **if the Captain strikes it, D1 to D3 stand alone.** An unknown stored value shows the default and is not rewritten until the operator saves (the config already reads an unknown engine as `classic` and an unknown effort as `normal`). |
| **D5 Server side** | Check what `POST /api/v1/config` does with `decoder.threads`, `engine` and `effort` today (`WebApp.cs` sanitises the decoder block, about line 589 for the classic thread count; `DecoderConfig.EffectiveThreads` clamps 1 to 8). Make an out-of-range `threads` behave as the neighbouring values do (clamped, a warning logged, the clamped value stored or the request refused: follow the precedent at `WebApp.cs:589-599` and say which). The maximum becomes 16 (D7). |
| **D7 Raise the thread cap from 8 to 16** (added 2026-11-25 at the Captain's request, so 16 threads can be measured and offered to an operator whose PC has them) | The cap is 8 in three places that must move together: `FTZ_MAX_THREADS` (`native/ftz_decoder/ftz_decoder.h:33`; the worker and coherent-context arrays are sized by it, `ftz_decoder.c:169-170` and `:305`; the clamp is at `:673`), `DecoderConfig.MaxThreads` (`DecoderConfig.cs:106`, and `EffectiveThreads` at `:400`), and the Settings input's range. Raise all three to 16. Check every place that assumes 8 (the stats `threads` field, per-worker buffers, the pool rebuild when the count changes, the ASan fuzz and determinism tests). Memory per worker: state in the result how much a 16-worker cycle allocates against 8. The shim number moves (native code changed), `libft8.dll` rebuilt, as in 2e. The classic decoder is untouched. The lean engine's results must stay byte-identical at every thread count: the determinism test runs at 1, 2, 4, 8 and 16 threads. |
| **D6 Documents** | `REQUIREMENTS.md`: extend FR-108 **without writing any other FR number in prose** (Gate G3 counts them). The OpenSpec change `lean-decoder` (tasks, delta spec) updated and validated `--strict`; `config.example.json` gets the three keys with their defaults if the file lists the other decoder keys. **VERSION:** none (the lean engine stays default `classic`); run `check_version_bump.py` after committing. HK-005: see the task order below. |

## 2. Task order (HK-005, checked by `tools/check_screenshot_task_order.py`)

1. **Screenshot, before:** the Advanced Decoder Settings block as it is at `57bda0eb` (Playwright, HK-007), saved under `dev-tasks/screenshots/`. **First task, before any change.**
2. D1 to D6 (implementation).
3. Tests (section 3).
4. **Screenshot, after:** the same block with the new controls, with the daemon running so the processor count shows.

## 3. Tests

0. **Native:** the ASan + UBSan fuzz (10,000 runs, `ftz_fuzz.c`) includes 16 threads; the determinism test compares byte for byte at 1, 2, 4, 8 and 16 threads; `DOTNET_PROCESSOR_COUNT=4` and the host's own both run the golden and lean tests.
1. **Front-end, in the style of `web/js/settingsPayload.test.js` and `coherentFallbackDefault.test.js`:** the payload carries `threads`, `engine` and `effort`; an absent key shows 2, `classic` and `normal`; a stored value is shown as stored; the reset restores the defaults; a changed value makes the page dirty. Run with the existing JS test runner.
2. **Config tests (C#):** `threads`, `engine`, `effort` round-trip through the config store; the POST overlay keeps a stored `threads` when the payload does not carry it; an out-of-range `threads` is handled as D5 says; an unknown `engine` or `effort` reads as the default.
3. **Web tests (C#):** the GET that carries the host processor count returns it (a positive integer equal to `Environment.ProcessorCount`).
4. **Nothing else changes:** the decoder, the pump and the native code are untouched; every existing suite stays green (per-project "Passed: N" lines).

## 4. Out of scope

Changing the default thread count or the default engine (the Captain decides after the replay; DR-3 flips the engine), raising the maximum above 16, a control for the classic engine's `subtractionMaxThreads`, auto-detecting a "best" thread count, any decoder change.

## 5. Report back

The commit SHA; the rebuilt `libft8.dll` SHA256 and the shim number; the memory of a 16-worker cycle against 8; the per-project "Passed: N" lines and the JS test result; which GET carries the processor count; what D5 does with an out-of-range value; the two screenshot paths; anything in the page that differs from the neighbouring controls' pattern.
