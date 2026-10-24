**User-facing:** no

## Why

COH-MULTISET (offline arm, ruled L1-GO and final by the Architect 2026-10-24, report `qa/rr-study/results/2026-10-24-coh-multiset/report.md`): at WSJT-X's own positions on one 40 m night, where both the shipped extractor (G) and today's coherent fallback (C3 = V3 + BP) found no CRC-valid payload, four further coherent bit-metric sets tried one after the other recovered **+2.115 pp [1.937, 2.302]** of WSJT-X's decodes (554 right, 15 wrong on 7,498 consulted rows; wrong share 2.64 % against 3.02 % for C3 on the same night). The order C1 > J2 > J3 > N1 was fixed in advance; J2 and J3 supplied 85 % of the first successes. The Captain ratified the size of gain that justifies this build (0.5 pp, 2026-10-24 12:50:57Z) and authorised the build spec ("yes, write the build spec").

This change builds exactly that walk into the coherent fallback, behind a flag that is **off by default**, so it can be measured in replay on the product's own candidates, with the F1b gate on the outputs and the false-output instrument U', before anyone decides whether it should ever be on. **What the arm did not measure and this build does:** the gain from our own candidates, the gate's effect on the sets' outputs, false outputs on the product's noise candidates, and the native CPU cost.

Architect spec: `qa/rr-study/2026-10-24-1455-architect-to-qa-spec-coh-multiset-build.md` (branch `arch/coh-multiset`, `37a1a298`), with section 10 Amendment 1 (`b59f7d7a`, QA's (k) review M1 to M4 adopted in full). Licence (Captain, 2026-10-24): method only; no WSJT-X source is opened, copied, transliterated or ported. The reference is QA's own clean-room Python `qa/rr-study/coh-multiset/ms_metrics.py` (commit `96aa80d4`), written from the spec's prose and FT8's public constants.

## What Changes

- In the fallback's per-candidate body (`cf_process_one`, and the parallel `ft8_coherent_fallback_process`), **when V3 + BP gives no CRC-valid output**, the same candidate gets up to four more tries, in this fixed order: C1 (order 1 on power), J2 (joint pairs), J3 (joint triples), N1 (order 1 on magnitudes, normalised bit by bit). Each is built from the per-symbol correlations `cf_v3_llrs` has just computed at the same estimate, goes to BP only (no OSD), and is followed by the CRC. The first CRC-valid output ends the walk and then takes the **existing** path unchanged: known-payload check, `cf_snr_db`, the F1b gate (`F1b <= CF_T1_DB`), dedup, plausibility, batch 4.
- If V3 gives a CRC-valid output, or the candidate was not attempted, **nothing new runs**.
- A new config flag `decoder.coherentFallbackMultiSet`, **default `false`**, acts only when `decoder.coherentFallbackEnabled` is true; **no Settings-page control**. Flag off: identical native calls, outputs, counters (apart from added zeros) and order.
- Every fallback result records which set produced its payload (0 = V3, 1 = C1, 2 = J2, 3 = J3, 4 = N1, -1 none), in the harness outputs and the per-cycle counters. `ALL.TXT`, UDP and panel formats are unchanged.
- The per-cycle `Coherent fallback:` log line gains aggregates only (`sets=on/off`, candidates that entered the walk, CRC-valid counts per set).
- A new diagnostic-only native export (the Developer names it, e.g. `ft8_coherent_fallback_sets_at`) returns, for one position, the estimate, V3's BP outcome and, for **each** of the four sets, its 174 raw values, BP result, CRC flag and payload (computed for every set whatever the walk does), plus the walk's result. Existing exports and struct layouts are unchanged.
- `FT8_SHIM_VERSION` becomes **20260071** (20260069 is `origin/main`; 20260070 is held by `decoding_improvement`'s sync 7).

## Capabilities

### New Capabilities
- `ft8-coherent-fallback`: the multi-set walk, its flag, its provenance and its diagnostic export (the existing fallback has no capability spec; this change specifies only what it adds).

### Modified Capabilities
- (none)

## Impact

`native/ft8_lib_vendor/refine/coherent_fallback.c/.h`, `src/OpenWSFZ.Ft8/Native/ft8_shim.c/.h`, `src/OpenWSFZ.Ft8/Interop/` (interop and `CohFallbackTypes.cs`), `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, `src/OpenWSFZ.Abstractions/DecoderConfig.cs`, the daemon wiring that reads the flag once per cycle, and tests. The committed Linux and macOS native binaries need the usual follow-up refresh (as PR #254 did for 20260069). Merge with the flag off needs the Captain's sign-off (HK-010); default ON is a separate decision after a replay (D-GO and U'-OK).
