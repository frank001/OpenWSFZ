# QA code review (HK-039): DR-2 step 2d, three batches, XC on the lean residual, `decoder.effort`

**Reviewed commit:** `6c7460291abcb329ac0106c0cf376ec40f1570bc` (`feat/lean-2d`, one commit on `0c2db3b2`, not pushed)
**Verdict:** APPROVED, with 4 minor notes
**Reviewer:** QA, 2026-11-25. Read: the native diff (`ftz_decoder.c`, `.h`), `Ft8LibInterop.cs`, `LeanCycle.cs`, `IFt8NativeInterop.cs`, the whole of `DecodeLeanAsync` and the shared XC stage in `Ft8Decoder.cs`, `DecodePump.cs`, `Program.cs`, `DecoderConfig.cs`, `DecoderEngine.cs`, and the new tests (`LeanEngineBatchesTests.cs`), against the task `dev-tasks/2026-11-25-dr2d-lean-decoder-batches-xc-effort.md`.

## Tests QA ran (clean worktree at the commit, `D:\Projects\claude\_qa-scratch\dr2d-review`)

- `DOTNET_PROCESSOR_COUNT=4`, OpenWSFZ.Ft8.Tests, `--filter "FullyQualifiedName~Golden|FullyQualifiedName~LeanEngine|FullyQualifiedName~CrossCycle"`: **Passed: 157, Failed: 0**.
- OpenWSFZ.Daemon.Tests, `--filter "FullyQualifiedName~LateBatch4|FullyQualifiedName~DecodePump"`, 4 processors: **Passed: 35, Failed: 0**.
- OpenWSFZ.Config.Tests, `--filter "FullyQualifiedName~LeanEngine"`: **Passed: 15, Failed: 0**.
- From the Developer's report, not re-run by QA: Ft8 891, Daemon 963, Config 219, Web 448, ASan+UBSan 10,000 runs clean, openspec strict 84. CI on the pushed branch repeats ASan, Linux and macOS.

## What was checked and found sound

- **D2, how batch 1 leaves early.** A native callback (`ftz_round0_fn`), called once after round 0 is unpacked and before round 1, on the calling thread, with the lock held. The callee copies and returns; the managed callback completes a `TaskCompletionSource` created with `RunContinuationsAsynchronously`, so the publish never runs on the native thread and native never waits on the consumer. The callback has a managed try/catch around the whole body and an SEH guard on the native side; the delegate is kept alive across the call (`GC.KeepAlive`). A faulting callee returns `FTZ_ERR_FAULT` and `done:` does not export a residual after a fault.
- **Fallbacks for batch 1.** If the hand-off never comes (error before round 0 is unpacked, callback failure), batch 1 is built from the returned results, exactly once, empty or not (`batch1Delivered`). `Task.WhenAny(round0, native)` covers the native call ending first.
- **Test 1 proves the ordering without a delay.** The real native library blocks inside the hand-off on an event that only the publisher sets, so a batch 1 that could only leave after the call would time out; it also records "native has returned" as false at publish time. The only wait is a bounded wait on that positive condition.
- **D3, the residual.** Exported as of the last subtraction made; not exported when nothing was subtracted, when a fit round was cancelled (the buffer is half-subtracted: `resid_valid = 0`), or after a fault. The XC stage body is extracted once (`RunCrossCycleStageSharedAsync`) and used by both engines; the classic caller passes the same inputs and the stage's log line and probe records are unchanged (classic batch number 6, lean 3). `out_residual` and `has_residual` are bounds-clean (fixed 180,000 floats, caller-allocated and pinned).
- **D4 priors**, batch 1 and 2 recorded with `Batch` 1 and 2, batch 3 mapped with `xcBatch: 0` and never stored (test 4). **D5 effort**: `FTZ_FLAG_NO_TIER_B` skips eligibility in every round, `MaxRounds` 1; an absent, empty or unknown value reads `normal`; read once per cycle (test 6). **D6 routing**: `LeanEngine` hook checked first, classic branches textually unchanged when it is false or absent.
- Params struct version 4 is backwards-safe: a caller with the shorter struct reads NULL for the three new fields (`ftz_decode_cycle` copies `min(struct_size, sizeof)` into a zeroed struct).

## Minor notes (none blocks)

1. **A publish failure is reported as a lean decode failure.** In `DecodeLeanAsync` the `await onFirstBatch(...)` for batch 1 sits inside the same `try` as the native call, so an exception from the publisher is logged as "lean decode failed", the cycle's outcome is replaced by an empty one (batch 2 and XC then never run), and the native task is left running un-awaited. Classic lets a publish exception propagate. The consequence is small (the pump's publish does not normally throw, and the next cycle's native call simply waits on the lock) but the try should cover only `await native`. Worth a tidy before DR-3.
2. **A half-subtracted residual can be exported on a non-fault error return.** `resid_valid` stays 1 from an earlier round if a later round's fit returns -1 (a bad argument or no workspace, mapped to `FTZ_ERR_NOMEM`) after some of its chunks were summed. Only `FTZ_ERR_FAULT` is excluded in `done:`. Not reachable in practice (-1 means an internal argument error), but clearing `resid_valid` at the start of each round's subtraction would make it exact.
3. **NativeAOT is not exercised here.** `Marshal.GetFunctionPointerForDelegate` and `Marshal.PtrToStructure<Ft8NativeResultWire>` (a struct with an inline string) are new in the production path; this machine has no native linker, so the pre-merge AOT step is inconclusive as for 2c. CI's AOT job, if it has one for this branch, is the check; otherwise the first run of the lean engine in an AOT build is.
4. **Log timing differs from classic and is disclosed.** The "N decode(s) found, elapsed" line is written once, after the native call and XC, with the count of all batches; classic writes it at batch 1 time. The `lean:` line is also written at the end. Anything that parses the "found, elapsed" line for batch-1 latency must use the batch timestamps instead; the replay harness reads the time to each batch from its own callbacks, so T4 is unaffected.

## Next

Push of `feat/lean-2d` needs the Captain's go (HK-033), and his word on `pre_merge_check` before it (HK-006). Then QA's own work for the one replay: extend the harness for `--engine lean` and `--effort`, pin the lean build, run Slice 40 (170 cycles) against the DR-0 A6 baseline. A run over 2 hours needs his explicit go.
