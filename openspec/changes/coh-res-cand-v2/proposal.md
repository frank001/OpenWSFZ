**User-facing:** no (a new configuration key, default OFF; the shipped behaviour does not change)

## Why

#272 (`feat/coh-res-cand`, `b0d01f4f`, never merged) REPLACED the candidate list the coherent fallback's residual run reads. It gained 120 corroborated rows, lost 58 good ones (the Architect's error E136) and its not-corroborated new rows cost a wrong-payload rate of 0.0475 per cycle against a bar of 0.021: FAIL by U. COH-RES-CAND v2 (programme candidate #3) changes the design in two pieces: it ADDS a third, last fallback run and does not replace anything, and it GATES that run's new-text rows with one threshold frozen from #272's data before the build existed.

Authority: Architect spec `qa/rr-study/2026-11-12-1340-architect-to-qa-spec-coh-res-cand-v2.md` (`arch/coh-res-cand-v2`; §2 R1 to R8, Amendment 1 A1.2, Amendment 2 A2.1, `538ecc29`); QA's Stage 0 record `qa/rr-study/2026-11-12-1352-qa-coh-res-cand-v2-stage0-record.md` (`qa/same-chain` `271b5562`, verdict FEASIBLE, narrowly); the Captain's go for the Developer, 2026-11-12; QA task `dev-tasks/2026-11-12-coh-res-cand-v2.md`. The build is authorised behind a setting, default OFF. It does not authorise a default change.

## What Changes

- `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: bool `decoder.coherentFallbackResidualCandidates` (property `CoherentFallbackResidualCandidates`; the key and names #272 used, so QA's replay harness works unchanged). Absent or false = today's behaviour. Follows `decoder.coherentFallbackResidualUngated` (config file and API overlay, HK-035; no Settings-page control).
- `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs`, `CohFallbackAudioSelector.cs` (`Choice.CohSnapshot`): the residual-snapshot plumbing ported from `b0d01f4f`: after the residual decode's `DecodeAll` (the one call site of the residual pass and the third pass) `interop.CohFallbackSnapshot()` is called on that thread, only when asked (setting ON, `Both` mode, Deep). The snapshot travels with the buffer `Select` returns.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs`: `SetCoherentFallbackResidualCandidates`, read once per window. In `Both` mode with a residual buffer a THIRD `RunCoherentFallback` runs last: `choice.Pcm` with the residual snapshot, on the budget left after the second run. The first two runs are untouched. The third run's rows never enter `CohFallbackAudioSelector.Merge`, so R-F4's ungating cannot reach them: only F1b-passed rows (`NewGated`) are taken. A row whose text is not already published in the cycle is kept only if its published integer frequency is at most **1097 Hz** (`CohFallbackAudioSelector.ResidualRunMaxFreqHz`); the rest are dropped and counted. Kept rows are appended after the first two runs' rows and go through the same `MapNative` text de-duplication, plausibility filter and L1' fit list. The log line gains `resRun`, `resCand`, `resEligible`, `resNew`, `resNewGated`, `resNewKept`, `resWallMs` while the setting is effective.
- `src/OpenWSFZ.Daemon/Program.cs`: the two setter calls.
- **No native change.** `git diff --stat origin/main -- native/ src/OpenWSFZ.Ft8/Native/` is empty; `FT8_SHIM_VERSION` stays 20260072; `libft8.dll` SHA-256 stays `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`.
- Tests, `VERSION` 0.70 to 0.71 (every place the gates check), `REQUIREMENTS.md` FR-104 and a changelog row.

## The gate and where it comes from

`freq <= 1097` Hz on the published integer frequency. Chosen by QA's Stage 0 on #272's arm-B data (149 new-text batch-4 rows: 119 corroborated, 19 tested_absent, 9 tested_present, 2 hashed): `kept_C` 57 of 119, `kept_TA` 4 of 19, `p_perm` 0.0476. Frozen into the spec by Amendment 2 (A2.1). No mechanism is known; it may not transfer to another night, configuration or band. Stage 2 (QA's arm B on the 40 m night `20261110`) is the test. The constant is never re-fitted here (HK-021(p)).

## Out of scope

Any change to the first two runs, F1b, R-F4, multi-set, L1', CQ-AP, batches 1 to 3, the 13 s budget or `native/`; a Settings-page control; turning the setting ON by default; `Original` and `Residual` modes (no effect there).

## Era

None while the setting is OFF. Turning it ON on the station starts a new live era; live figures are never pooled across it.

## Capabilities

### New Capabilities

- `ft8-coherent-fallback-residual-run`: the setting, the third run, its snapshot, the gate, R-F4's exclusion and the log fields.
