# HK-039 code review: DR-2 step 2a, the lean engine's first cut, `340c7123` (QA, 2026-11-24)

Reviewed-commit: 340c71237faf61bb5dc5ac9cfb9f15c31634a462
Verdict: APPROVED

Developer branch `feat/lean-2a`, one commit on `origin/main` `452af459`. Task: `dev-tasks/2026-11-24-dr2a-lean-decoder-tier-a.md` (`cc6da2fc`). Counts only; no message text (HK-037).

## What was checked

- **Diff:** 28 files, +2,490/-6 (`git diff --stat 452af459 340c7123`). Read in full: `native/ftz_decoder/ftz_decoder.c` and `.h`, the `decode.c` patch (`ftx_decode_candidate_tier_a`), the `ft8_shim.c`/`.h` change, `ci.yml`, `Ft8Decoder.cs`, `Interop/LeanCycle.cs`, `Program.cs`. Not read line by line: the four new test files, the OpenSpec change, the interop adapter and `DecoderConfig.cs` (skimmed).
- **QA's own runs,** clean detached worktree `_qa-scratch\qa-lean2a-review` at `340c7123`, per project, in Release: Config 215 of 215; Ft8 846 of 846 with `--filter "Category!=AwgnFpReplay"` (the same count the Developer reports); Web 448 of 448. **Not re-run by QA:** Daemon (961), Audio (40), Rig (41), TestSupport (12): the Developer's counts stand. `AwgnFpReplayTests.PinnedShaWinX64` untouched.
- **`libft8.dll`:** the SHA256 of the committed file equals the one in `libft8.version.txt` (`1954e4df...81240`).
- **Classic path:** the only statement that runs when the engine is `classic` is one `if (_engine == Lean)` at the top of the cycle (`Ft8Decoder.cs`), and the `Dispose` call. Both are no-ops for `classic`. The Developer's golden test (recorded on `452af459`) covers the key absent and set to `classic`.

## Findings

Correctness of the native code, as read: the worker pool is sound (one generation per job, every worker sees every generation, `ftz_pool_run` waits for all started workers); every array index is bounded by sizes the call computed; allocations are checked and freed on every exit; the sort happens before anything reads the callsign table, so the output is independent of the thread count; tier A (`ftx_decode_candidate_tier_a`) reads the waterfall and writes only its own stack and out-parameters, so it is safe on several threads. The degenerate-LLR guard is a real hazard handled.

Minor notes (none blocks; fix when convenient, e.g. in step 2b):
1. **Orphaned doc comment.** In `Ft8Decoder.cs` the insertion of the lean block landed between `RunCoherentFallback`'s `/// <summary>` and the method itself (`:1738-1741` of the commit). The summary now attaches to nothing and `RunCoherentFallback` has none. Move the lean block above that summary.
2. **No cycle deadline in the lean path.** `DecodeLeanAsync` passes no budget; tier A is bounded work, so this is fine for step 2a, but step 2c (the loop) needs the 13 s budget the spec names.
3. **Shared callsign table.** The lean call takes its own lock (`g_ftz_call_lock`) and the classic path its own; both use `g_session_hash_table`. Only one engine runs per cycle and the switch takes effect on the next cycle, so no overlap is expected. Worth one sentence in the design if the engine is ever switched at run time while a classic cycle is in flight.
4. **Result order is by frequency, then time, then payload** (spec rule 7), not by candidate score as the classic pass publishes. The callsign table is therefore learned in a different order than classic, which can matter only for a Type-4 hash resolved by an earlier decode in the same cycle. The spec sanctions the order; recorded here so nobody is surprised in step 2d's replay.
5. **Duplicated publish loop** (plausibility, region, worked-before) next to `MapNative`. Acceptable while the classic decoder exists; DR-4 deletes one of them.
6. **Test depth.** The primary-pass equality test uses three synthetic fixtures. That is what the task and spec ask for in step 2a; real-audio equivalence is step 2d's single replay.

Developer's six review points: (1) include of the `.c` into `ft8_shim.c`: accepted, and the reason given (shared statics, no new compile line) holds. (2) sort key third element is the payload: accepted. (3) early decode returns nothing under `lean`: matches the plan. (4) both log lines kept: fine; one line on request. (5) the -4 code for NaN, infinity or a sample beyond 1e6: accepted. (6) exports, shim `20260073`, DLL rebuilt: checked; Linux `.so` and macOS `.dylib` are CI's (the macOS leg is expected).

## Not verified, and why

- **The ASan CI job `native-asan` has not run** in CI (nothing pushed); the Developer ran the same script in WSL Debian locally, no report. QA did not repeat it. CI is the check, and its result is read when the branch is pushed.
- **Mutants:** none run. Under the Captain's minimal-test rule (2026-11-24) the review is the check for a step whose only gate is unit tests.
- **`pre_merge_check.py`:** once per PR, not per step (2026-11-24); not run for this commit.

Nothing pushed. The next step, 2b (tier B and CQ-AP), needs DR-0's baseline only for the later steps, not for this one.
