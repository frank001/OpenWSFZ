## Decisions

**D1. C#-only, behind a setting, default OFF.** OFF is today's code on every path and takes no extra snapshot (acceptance row B-OFF compares 40 cycles byte for byte against `main`). With the setting ON the fallback's `eligible=` field of the combined log line is the larger of the two runs' counts (`CombineStats` is unchanged), which is a log-only difference.

**D2. R2 diagnostics question: answered in the shim, no native change.** The residual `DecodeAll` runs with `SetDiagnosticsEnabled(false)` (`SubtractionPass.cs:443`). In `ft8_shim.c` the candidate list and the decoded payloads are recorded in `ft8_decode_all` at `:1858-1866` (`tls_cf_cands`) and `:1882-1884` (`tls_cf_payloads`), BEFORE the diagnostics switch is consulted at `:1893` (`if (!tls_diagnostics_enabled) continue;`), which skips only the LDPC-failure sums (`tls_llr_*`). So the snapshot is complete with diagnostics off and nothing is switched on for the call. The snapshot is taken inside the same `try` as the call, so the diagnostics switch is restored by the existing `finally` afterwards.

**D3. One call site for R2 and R3.** Both the residual pass and the third pass reach `interop.DecodeAll(residual)` at `SubtractionPass.cs:446` inside `RunCoreUnguarded`, on the pass's own `Task.Run` thread. The snapshot is taken there, after `DecodeAll` and before anything else on that thread, and handed out through `PassStats` into `ResidualPassReport` (R2) and `ThirdPassResult` (R3). It is taken even when that decode finds nothing new (the candidate list is what counts), and only when `captureCohSnapshot` is true (ON, Deep, the staged cycle).

**D4. The snapshot travels with the buffer (R2 of the spec).** `CohFallbackAudioSelector.Select` returns `Choice(Pcm, Level, CohSnapshot)`: the third pass's pair when it ran, else the residual pass's pair. The decoder uses `choice.CohSnapshot` for the run that reads `choice.Pcm`. The third-pass snapshot is not used when the third pass did not run, so snapshot and audio cannot drift apart.

**D5. How the fallback uses a snapshot's payloads, and a batch-1 payload.** `ft8_coherent_fallback_run` (`ft8_shim.c:2565-2625`) takes the candidate list from the snapshot and, for a candidate whose CRC-valid result matches a payload held in `snap->payloads` (`:2613-2616`), sets the row state `KNOWN` and does not publish it. The residual snapshot holds the payloads decoded on the residual buffer, not pass 0's. A payload published in batch 1 can therefore be re-found by the residual run and not be marked `KNOWN` there. The guards: the residual buffer has those signals subtracted, the original-audio run keeps pass 0's snapshot (so it marks them `KNOWN`), and above all the per-cycle text de-duplication in `MapNative` (`seen`) drops any text already published in a cycle. R4 of the spec is unchanged; a test pins that a batch-1 text is not published twice.

**D6. A missing snapshot never costs a decode.** `CohFallbackSnapshot()` returning null or throwing leaves the run on `cohSnapshot` (`fallback-orig`, counted, logged). A throw inside the residual pass is caught around that one call so the pass keeps its decodes and its other results.

**D7. Counts for the log line.** `resEligible` is the eligible count of the run that read the residual-side snapshot (its own statistics); `origEligible` the original-audio run's. When that run was never started (budget spent) its abandoned count is its own eligible count, taken from the native plan of `cohSnapshot` (`CohFallbackEligibleCount`, a managed call to the existing `ft8_coherent_fallback_plan`); -1 when unavailable, in which case the previous basis is used.

**D8. Config.** Follows `decoder.coherentFallbackResidualUngated`: `DecoderConfig`, a volatile field set by the daemon before the first window and on every config save, read once per window, HK-035 overlay semantics.

## Risks

- A longer candidate list costs fallback time. Mitigation: acceptance row B-AB (abandoned in B not above A); NET already prices a lost row.
- The residual run may re-find a batch-1 payload (D5). Mitigation: text de-duplication; row B-DUP.
- A native-thread mistake (snapshot on the wrong thread). Mitigation: D3; the test records which `DecodeAll` each snapshot followed and which snapshot each run received.
