# QA code review: COH-FALLBACK step 4, `db3d7df5` (Developer, `feat/coh-fallback-stage1`, base `1405ada4`, shim 20260069)

**Reviewer:** QA. **Stamped:** 2026-10-21 by `date -u` (~17:4xZ). **To:** Developer, Architect, Captain.
**Spec:** `arch/coherent-limb2` step3-build.md §14 + §15. **Handoff:** `dev-tasks/2026-10-21-coh-fallback-step4.md` (`d8033b25`).
**Scope read:** the whole `git diff 1405ada4 db3d7df5` (28 files, +1,757 / −193): `Ft8Decoder.cs`, the new `CohFallbackParallelRunner.cs` and `CohFallbackLibBackend.cs`, the interop and type changes, `ft8_shim.c/.h`, `LateBatch.cs` (`QsoBatchQueue`), `DecodePump.cs`, `Program.cs`, the QSO service comments, and the tests (`CoherentFallbackParallelRunnerTests`, `CoherentFallbackStep4NativeTests`, `CoherentFallbackWiringTests`, `LateBatch4Tests`). I did NOT re-run the unfiltered suite or the sanitizers; those are the Developer's figures (Ft8 579, Daemon 779, Web 402, Config 168 green; self-test 254/258 checks).

**Verdict: APPROVED to proceed to acceptance. No blocking defect. Four non-blocking notes (R-1 to R-4), one of which I ask the Developer to take before the Captain's merge decision.**

Mistake of mine, recorded: I told the Developer and Architect I would wait for the commit and run acceptance, and I started the A2(e) run **before** reviewing the code. Review precedes acceptance. The run was stopped by the Captain before it executed; nothing ran.

## What I checked against the handoff

| handoff item | finding | where |
|---|---|---|
| R6‴/R7‴ start after the last ordinary batch; nothing concurrent with pass 0 follow-on, residual or third pass | **Met.** The Stage 2 `Task.Run` at batch 1 is gone. The fallback starts in `RunCoherentFallbackBatchAsync`, called after batch 3 is handed off on Deep (also when batch 3 is empty), after batch 2 on Normal, after batch 1 when pass 0 decoded nothing. | `Ft8Decoder.cs` ~881–935 |
| publish as a batch of its own, only if non-empty, Deep 4 / Normal 3 | **Met.** `FallbackBatchDeep = 4`, `FallbackBatchNormal = 3`; the callback is called only when `batch.Count > 0`. Same dedup, plausibility filter and R6'' selector (unchanged). | `Ft8Decoder.cs` ~1030, constants after the method |
| flag OFF unchanged (R13) | **Met by construction:** `cohOn` is false, so the `fallbackReady` branches are never entered; `if (!fallbackReady) return second;` keeps the old return value on Normal. Tests cover call order OFF on Deep and Normal. | `Ft8Decoder.cs` ~509–520, ~909–916 |
| `DecodeTwoStageAsync` has no effect | **Met and explicit**: `cohOn` requires all three callbacks. | `Ft8Decoder.cs` ~516 |
| R15 parallel, gather in candidate order | **Met.** Claim-by-counter, each worker writes only its own row `e`, rows are the plan's rows indexed by candidate, so the list does not depend on scheduling. Deadline and cancellation are checked before a claim only, so the candidates run are a prefix (the abandoned tail keeps the pre-filled row). A fault stops all claims and is rethrown after every worker has stopped. | `CohFallbackParallelRunner.cs` |
| native per-candidate body unchanged | **Met.** `ft8_coherent_fallback_process` is `ft8_coherent_fallback_run`'s loop body statement for statement (I diffed it: same estimate, CRC, known-payload check, SNR-before-F1b order, counters). `ft8_shim.c` is append-only (113 insertions, 0 deletions); `coherent_fallback.c`, `_at` and the F1b code are not in the diff. | `ft8_shim.c` 2580–2692 |
| R14 capacity 4 batches | **Met with a better design than asked:** the capacity stays 8 with the flag OFF and is 10 with it ON, enforced by the writer (`QsoBatchQueue`), because the flag can change at run time and the channel is made once. The arithmetic is named constants (`QsoCyclesQueued`, `QsoChannelSpare`, `BatchesPerCycleFallbackOn`). | `LateBatch.cs` 54–77, 140–185 |
| panel / pump accept batch 4; Normal depth with the flag ON uses the staged entry | **Met.** `CoherentFallbackOn` in `DecodePumpDependencies` selects `DecodeStaged`. | `DecodePump.cs`, `Program.cs` |
| R12' log fields, `-1` never averaged | **Met.** `batch4Published` is an explicit flag beside `batch4PublishMs`. | `Ft8Decoder.cs` ~1030–1045 |
| tests: no fixed delays | **Met.** Waits are on positive conditions (`WaitOne`/`Wait` with a 30 s ceiling as a failure bound, not a pause); the interleaving perturbation is a seeded `SpinWait`/`Yield`, deterministic. Worker counts are test parameters, never the machine's core count. | `CoherentFallbackParallelRunnerTests.cs` |
| magic numbers | None new that matter. The 13 s budget and the 250 ms reserve are the existing named constants. | — |

## Empirical cross-check by QA (not in the Developer's tests)

On `sol`, the same 12 cycles of `20260922_2056` through both builds: the **fallback decodes (path 2) of the single-thread Stage 2 build and of the 8-worker step-4 build are identical sets of (frequency, DT, SNR)** on all 10 cycles that had any, 15 decodes against 15. That is the property the parallel code has to keep, observed through the real library and the real decoder, and it is on a CPU where the thread interleaving differs from the Developer's.

## Notes

- **R-1 (ask: Developer, before the merge decision).** `CoherentFallbackStep4NativeTests.ParallelRows_EqualTheSingleThreadRun` compares every field, which is good, but it never asserts that any candidate reached a **CRC-valid, new** state (`NewGated` / `GatedOut`, i.e. the SNR and F1b path). On weak synthetic noise every row may be `NoCrc` or `Known`, and then the equality holds trivially. A worker's native context is reused across the candidates it happens to run, so the one thing the 1/2/8-worker equality is there to catch (a result that depends on which candidates shared a context) is exercised only if some row goes through `cf_snr_db` and `cf_f1b_db`. Add `reference.Stats.CrcNew.Should().BeGreaterThan(0)` for at least one seed (or choose a seed/SNR where it holds). My sol comparison above is evidence that it holds on real audio, not a substitute for the test.
- **R-2 (low).** The R12' log line is written **after** the batch callback. If the callback throws (a publish failure), the cycle's line is lost although the fallback ran. Write the line in a `finally`, or before the callback with `batch4PublishMs` filled afterwards. Not a correctness issue for the replay; it matters for the live R14 check, which reads that line.
- **R-3 (doc staleness).** The XML summary of `DecodeStagedAsync` (`Ft8Decoder.cs` ~443–458) still lists batches 1–3 and the `publishBatch` parameter says "1, 2 or 3". Add batch 4.
- **R-4 (observation, no action).** Each cycle allocates up to 8 native contexts and starts 7 long-running threads. At one cycle per 15 s that is immaterial; if the station ever shows a thread-creation cost in `fbStartMs`/`fbWallMs`, pooling is the remedy.

## Known and accepted (Architect, A14.2/A14.4), restated so the Captain has it

Batch 4 leaves at about 7.9 s from decode start on `sol` (median, 11 cycles), far past the 2.36 s reply guard. A reply to a batch-4 decode will therefore almost always be **deferred** to the next batch 1 of the right parity. That is the design; the R14 live check exists to show it works.

## Next (QA)

A2(e) 100/100, then the OFF arm, on the pinned `db3d7df5` (DLL `aaf6b03e…`, SO `0197f9ce…`, both verified to equal the committed blobs). The push for the macOS leg waits for the Captain's go (HK-033).
