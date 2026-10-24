## Context

The coherent fallback (shim 20260066 to 20260069) runs, after the last ordinary batch, on every candidate the ordinary decode could not decode: fine sync, V3 coherent LLRs (orders 1 + 2 + 3 summed), BP only, CRC-14, then the known-payload check, SNR, the F1b gate, dedup, plausibility and publication as batch 4. COH-MULTISET showed that four other bit-metric sets, tried in a fixed order where V3 failed, would add decodes. `ms_metrics.py` @ `96aa80d4` is the reference; the walk must reproduce it.

## Decisions

1. **Where the walk goes.** Inside the per-candidate body, right after V3's BP returns no CRC-valid output (`cf_process_one` at `ft8_shim.c:2247`; `_process` at `:2663-2665`, the serial `_run` at `:2507-2509`, where today the no-CRC return is). Both paths get it. A V3 CRC-valid output (known, new, gated, gated out) never enters the walk. A candidate the fallback did not attempt never enters it.
2. **Same correlations, same estimate.** The sets read `c->x_re / c->x_im` that `cf_v3_llrs` computed (`coherent_fallback.c:392-416`) for this candidate. They add no second downconversion and no second estimate. The F1b gate uses the same `r.peak`.
3. **Order and stop.** C1 > J2 > J3 > N1, fixed (the arm's order, chosen in advance, never tuned). The first CRC-valid output ends the walk and follows the existing path exactly as a V3 output would. A KNOWN or gated-out payload is **not** retried with a later set.
4. **BP only, no OSD.** `ftx_ldpc_decode_llrs(llr, K_LDPC_ITERATIONS, -1, ...)` as `cf_run_bp` (`ft8_shim.c:2236-2244`): float cast, production normalisation, then CRC-14. L2 (OSD on coherent bits) is closed.
5. **The gate applies to set outputs.** A set's new payload is published only if `F1b <= CF_T1_DB` (same constant, same `cf_f1b_db` call as V3: `:2680-2683`, `_run` `:2527-2530`). The arm did not apply the gate; it can only lower both gain and false outputs, and the replay measures both.
6. **Exact port; faster computation only if B1 passes.** Doubles throughout as `cf_v3_llrs`. J3 has 512 hypotheses per triple; an exact rearrangement of the max-log is allowed, B1 decides.
7. **Provenance without a layout change.** `FT8CohFallbackOut` ends in `int32_t reserved` (`ft8_shim.h:1599`): it carries the provenance (0 V3, 1 C1, 2 J2, 3 J3, 4 N1, -1 none). Its size does not change.
8. **The flag reaches native as a per-call bit, not a process global.** `ft8_coherent_fallback_run` documents `flags must be 0 (reserved)` (`ft8_shim.h:1609`): the multi-set bit uses it. `ft8_coherent_fallback_process` has **no flags argument** (`ft8_shim.c:2634-2636`; its scratch context comes from the argument-less `ft8_coherent_fallback_ctx_new`, `ft8_shim.h:1638`), so the same bit reaches it through the per-thread scratch context (an added setter such as `ft8_coherent_fallback_ctx_set_flags`; the existing signatures stay unchanged). The Developer records the exact FILE:LINE of the choice. Read once per cycle as `coherentFallbackEnabled` is (`Ft8Decoder.cs:197-214`, daemon wiring `Program.cs:807` and `:910`).
9. **No mutable global state** in the per-candidate code (`coherent_fallback.c:28-31`): scratch lives in `cf_ctx_t` or on the stack. Parallel results stay deterministic, gathered in candidate order.
10. **A diagnostic export computes all four sets for every position, regardless of the walk's rules**, because the port-fidelity row B1 compares each set separately. Existing exports and struct layouts are untouched; a new field goes in a new struct, or in an appended field with `CohFallbackTypes.cs` changed in the same commit, a size assertion and a test.
11. **Log line.** The `Coherent fallback:` line (`Ft8Decoder.cs:1038`) gains `sets=on/off`, the candidates that entered the walk, and CRC-valid counts per set. Aggregates only, no message text.
12. **Shim number 20260071.** `origin/main` is 20260069; `decoding_improvement` already holds 20260070 (sync 7). The DLL SHA-256 is what identifies a build (era rule: flag-on decodes are a new era, never pooled with flag-off figures).
13. **Linux/macOS binaries.** They are committed and refreshed by a follow-up chore after the native change (PR #254 for 20260069); the Developer's handoff lists the step.

## Risks

- A port that is right on the common case and wrong on a rarer class of successes hides under a large "no output on both sides" population: B1 therefore has a positive-class criterion (Architect Amendment 1, M2).
- The sets must never run where V3 already has an output (R2); B1 cannot show that, so a native walk-entry test does (M1).
- Cost: four more BP runs on candidates where V3 fails. Measured in the replay (fallback wall time per cycle, median and p95, flag on against off); the deadline and abandonment rule are unchanged.
