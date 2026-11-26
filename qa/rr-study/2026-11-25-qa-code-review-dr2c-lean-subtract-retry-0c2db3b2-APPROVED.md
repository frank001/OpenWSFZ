# QA code review (HK-039): DR-2 step 2c, the lean engine's subtract-and-retry loop

**Reviewed commit:** `0c2db3b269eaa931b3a8ede45f9c4bcb07f589ac` (`feat/lean-2c`, one commit on `963f717f`, not pushed)
**Verdict:** APPROVED, with 6 minor notes and 1 ruling
**Reviewer:** QA, 2026-11-25. Read: the whole `ftz_decoder.c` and `.h` diff, `LeanCycle.cs`, the `Ft8Decoder.cs` wiring, `LeanEngineRoundsTests.cs`, against the task `dev-tasks/2026-11-25-dr2c-lean-decoder-subtract-and-retry-loop.md`.

## Tests QA ran (clean worktree at the commit, `D:\Projects\claude\_qa-scratch\dr2c-review`)

- `DOTNET_PROCESSOR_COUNT=4`, `dotnet test tests/OpenWSFZ.Ft8.Tests --filter "FullyQualifiedName~Golden|FullyQualifiedName~LeanEngine"`: **Passed: 47, Failed: 0** (OpenWSFZ.Ft8.Tests.dll). Same count as the Developer's.
- Not re-run by QA, taken from the Developer's report: full Ft8 suite 869 passed; ASan+UBSan under WSL 10,000 runs clean; LicenseInventoryCheck 25; openspec strict 84. CI on the pushed branch will repeat ASan, Linux and macOS.

## What was checked and found sound

- Fits run on one analytic signal of the original audio, computed once, read-only; shat summed in sorted order, in chunks of 16, so the residual is the same bytes at any thread count (test 6 diffs 1/2/4/2/1 threads).
- rc -3 contributes zero and is counted; -4 is a deadline outcome; -2 and others map to FAULT or NOMEM. Every allocation is freed at `done`; every `goto done` is reached with the pointers initialised to NULL.
- Budget: a round is all or nothing (`round_incomplete`, the cancel flag, the 1,500 ms reserve), earlier rounds stand, `abandoned` set.
- Tier B contexts take `pcm_full` per call, so nothing stale is cached between rounds. `known` is refilled from every payload seen. Per-candidate state is cleared each round.
- Accept rules match task section 3: payload and RR73-aware dedup, text dedup, floor 10 / cap 200 / 50 iterations, F1b or ungated, 1097 Hz rule.
- D3 (re-encodable rule on the unpacked text, tones from the payload) is as asked, and the Developer's note that lean subtracts the true RR73 payload where classic re-encodes the text is a fidelity improvement, not a defect.

## Ruling on the Developer's item 1 (ungated rows lost when the residual-candidates flag is on)

The Developer applied my task's section 3 item 5 literally, so this is the task's wording, not a coding error. Classic has two separate paths (run 2: original candidates read on the residual audio, F1b-passed or ungated at any frequency; run 3: the residual's own candidates, F1b-passed new text at 1097 Hz or below). Lean has one candidate list and cannot tell which path a row would have taken. With both flags on (the baseline A6), lean therefore drops ungated rows and F1b-passed rows above 1097 Hz that classic would have kept through run 2.

**Ruling: keep the literal rule for 2c; do not change it now.** It is flag-controlled, one line (`ftz_residual_b_accept`), and the loss direction is toward fewer residual decodes, not toward false ones. The 2d replay (A6, one run) reads the effect as a number. If the lean rate misses T2 (83.39 %), the first lever is this line: admit `f1b_passed || ungated_on` at any frequency (the faithful union of classic's two paths, at the cost of the v2 frequency guard on residual-only rows). Test 4d would change with it.

## Minor notes (none blocks)

1. `ftz_params_t.expire_round` is a test hook in the production ABI. Harmless at 0; worth a comment that it is never set outside tests (the header says TEST HOOK, so only a reminder).
2. `cancel` is a plain `volatile int` written by the waiting thread and read by the workers: fine in practice on x86-64 and arm64, but a C11 data race by the letter; a relaxed atomic would be cleaner. A ThreadSanitizer job would flag it if one is ever added.
3. Inline path (threads 1 or one item): a running fit is not interrupted, so the budget can overshoot by one fit (about 0.6 s). Disclosed; acceptable inside the 1.5 s reserve.
4. Tests 4c and 4d exercise `ftz_residual_b_accept` as a pure function and the flags' wiring from `Ft8Decoder` (`bothAudio` gating of both flags) has no test. Test 5 does not exercise a cycle that runs to round 3, and no fixture produces a fit that answers -3. All three disclosed; the code paths are small and were read.
5. In the lean path the C# side now always asks for rounds, and publishes every round's results as one batch. That is correct for this step (task D4: no separate batch 2 until 2d), but 2d must split by `Rounds[]`.
6. Legacy stats fields are cumulative over rounds with the loop on; per-round values are in `rounds[]`. Disclosed and documented in the header.

## S3 CPU split (the Architect's watch item), from the Developer's fixture, not measured by QA

Fit about 625 ms, decode about 78 ms, sum plus re-spectrogram about 16 ms, search below the clock tick, for one signal subtracted over two rounds. Fitting dominates, as the Architect feared: about 0.6 CPU-s per subtracted signal. Extrapolated (not measured) 20 to 40 signals is 12 to 25 CPU-s against T1 of 6.31 CPU-s for the whole cycle. **This is the main risk to T1 and the real finding of this step.** The 2d replay will give the true figure; if it confirms it, the lever is the fit (fewer fits per cycle, a cheaper fit, or subtracting only what can mask), not the search.

## Next

Push of `feat/lean-2c` needs the Captain's go (HK-033). Whether `pre_merge_check` runs before this push (HK-006, 2026-10-23) or once per PR (the minimal-test rule, 2026-11-24) is for the Captain to say; QA asks with the push go.
