# QA code review (HK-039): the operator setting for the decoder thread count, with engine and effort, and the cap of 16

**Reviewed commit:** `fc4fb7887425a12fdf341d34b7f7dce118234f2a` (`feat/threads-setting`, one commit on `57bda0eb`, not pushed)
**Verdict:** APPROVED, with 4 minor notes
**Reviewer:** QA, 2026-11-25. Read: the native cap change (`ftz_decoder.h`), `DecoderConfig.cs`, `DaemonStatus.cs`, the clamp in `WebApp.cs`, `web/settings.html`, `web/js/settings.js`, `web/js/decoderThreads.js`, the after screenshot, against `dev-tasks/2026-11-25-operator-decoder-threads-setting.md` (with D7).

## Tests QA ran (clean worktree at the commit, `D:\Projects\claude\_qa-scratch\dr2f-review`)

- `DOTNET_PROCESSOR_COUNT=4`, OpenWSFZ.Ft8.Tests, `--filter "FullyQualifiedName~Golden|FullyQualifiedName~LeanEngine"`: **Passed: 79, Failed: 0**.
- OpenWSFZ.Web.Tests, `--filter "FullyQualifiedName~DecoderConfigApi|FullyQualifiedName~StatusAndBinding"`: **Passed: 40, Failed: 0**.
- OpenWSFZ.Config.Tests, `--filter "FullyQualifiedName~LeanEngine"`: **Passed: 15, Failed: 0**.
- JavaScript, `node --test web/js/*.test.js`: **tests 127, pass 127, fail 0**.
- From the Developer's report, not re-run by QA: Ft8 901, Web 459, Config 219, Daemon 963, ASan+UBSan 10,000 runs with the thread count cycling 1/2/4/8/16, determinism at 1/2/4/8/16/2/1, openspec strict 84. CI on the pushed branch repeats ASan, Linux and macOS.

## What was checked and found sound

- **D7, the cap.** `FTZ_MAX_THREADS` 16, `DecoderConfig.MaxThreads` 16 and the page's input range 1 to 16 move together; the fit workspace pool's own cap is 64 (`SUBFEAS_POOL_MAX_BOUND`), so 16 workers cannot starve it. The worker arrays and per-worker coherent contexts follow the constant. Determinism holds byte for byte at 1/2/4/8/16 in the managed tests and the native harness; a request for 99 threads reports 16.
- **D2, the processor count.** `processorCount` on `GET /api/v1/status` (a `DaemonStatus` property filled from `Environment.ProcessorCount`), which the page already calls on load; the browser's `navigator.hardwareConcurrency` is not used, and a test asserts that. The page labels it "logical processors", as agreed.
- **D5, the server.** `threads` outside 1 to 16 is clamped with a warning and the clamped value stored (the neighbouring values' precedent); engine and effort are kept as written; the POST overlay keeps stored values when the body carries another decoder key. Tests cover 1, 5, 8, 16 kept, 9 kept, 0 and -3 to 1, 17 and 64 to 16.
- **D1, D3, D4, the page.** Three controls above Reset, wired like the neighbours (dirty snapshot, pre-fill, payload, reset); an absent key shows classic / normal / 2; an unknown stored engine or effort word shows the default and is posted back as stored until the operator changes the select; threads posts a clamped integer (empty posts 2). The help text states the single measurement with its limits, says the lean engine only, the maximum 16 and the default 2. The after screenshot shows all of it, including "This PC has 16 logical processors."
- **HK-005 order** was followed in fact: the before screenshot (`threads-setting-before.png`) was taken first, against `57bda0eb`. The checker's complaint about `openspec/changes/lean-decoder/tasks.md` is a **false positive** (that file's task list is cumulative across steps 2a to 2e, so the new "before" task sits after earlier numbered tasks); the checker is not part of CI or of `tools/pre_merge_check.py` (checked: neither references it), so nothing gates on it. Accepted; no rewording.

## Minor notes (none blocks)

1. **A stale comment.** The comment above the new `threads` clamp in `WebApp.cs` says "clamped to [1, 8] ... (the native pool is sized for 8)"; the code uses the constants and clamps to 1 to 16. Reword the comment with the next change.
2. **Memory at high thread counts is not in the help text.** The Developer's own numbers: a fit workspace is 32.1 MB and each worker can hold one while fitting, so a cycle with 16 or more fits (a real cycle has about 30) can hold about 514 MB at 16 workers, 257 MB at 8, about 64 MB at 2; the coherent contexts add about 3.5 MB per extra worker; and the fit workspace pool stays allocated between cycles until the next pool configure or shutdown. An operator who sets 16 on a small PC should be told. One sentence in the help text ("each extra worker needs about 32 MB while subtracting") would do it.
3. **Saving the page freezes the defaults.** The first save writes `engine: "classic"`, `effort: "normal"` and `threads: 2` into the config (as the neighbouring controls do for their own defaults). When DR-3 flips the default engine to lean, an operator who has saved the page will keep `classic` unless DR-3 migrates the stored value (the spec already has the Developer migrate `engine` once). Remember it when DR-3 is specified.
4. **Native memory idle.** Same as note 2: the retained workspace pool means a 16-worker setting costs resident memory even between cycles. Not a defect (the operator chose it), but worth knowing before 16 is offered as a recommendation.

## Next

Push of `feat/threads-setting` needs the Captain's go (HK-033), and `pre_merge_check` runs first (HK-006). Then the 16-thread replay: harness built from this branch (`HasLean`), the same 170 cycles, `--lean-threads 16`; the decodes must be identical to the 2, 4 and 8 thread runs, and the interest is CPU and `last_p95`.
