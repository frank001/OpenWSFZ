**User-facing:** no (a new configuration key, default OFF; the shipped behaviour does not change)

## Why

In `Both` mode the coherent fallback runs twice: first on the residual buffer (the third pass's, else the residual pass's), then on the original audio. Both runs are offered the candidate list of the ORIGINAL audio's decode (`cohSnapshot`, `Ft8Decoder.cs:714`). A signal that only shows after subtraction is never offered to the fallback at its own position. GAP-RESIDUAL (QA, 2026-10-29) measured the cost: of 261 rows the coherent path decodes on the product's own residual buffers, 153 (1.26 pp of the reference) had no eligible candidate in the fallback's search window.

Ruling and authority: Architect build spec `qa/rr-study/2026-11-08-1614-architect-to-qa-spec-coh-res-cand.md` (Amendments 1 and 2); the Captain's go for the Developer, 2026-11-08; QA task `dev-tasks/2026-11-08-coh-res-cand-272.md`. The build is authorised behind a setting, default OFF. It does not authorise a default change.

## What Changes

- `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: bool `decoder.coherentFallbackResidualCandidates` (property `CoherentFallbackResidualCandidates`), absent or false = today's behaviour; follows `decoder.coherentFallbackResidualUngated` (config file and API overlay, HK-035; no Settings-page control).
- `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs`: when asked (`captureCohSnapshot`, ON only), the residual decode's `DecodeAll` (`SubtractionPass.cs:446`, the one call site of both the residual pass and the third pass) is followed at once, on its thread, by `interop.CohFallbackSnapshot()`. The snapshot travels in `ResidualPassReport.CohSnapshot` (R2) and `ThirdPassResult.CohSnapshot` (R3). A failed snapshot is contained: it stays `null` and the pass keeps its decodes.
- `src/OpenWSFZ.Ft8/Subfeas/CohFallbackAudioSelector.cs`: `Select` returns the snapshot together with the buffer (`Choice.CohSnapshot`), so list and audio cannot come from different buffers.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs`: a volatile field set by the daemon (`SetCoherentFallbackResidualCandidates`), read once per window. In `RunCoherentFallbackBatchAsync` the run that reads the buffer `Select` returned gets that buffer's snapshot (`Both`: the first run; `Residual`: the only run); the original-audio run keeps `cohSnapshot`. A missing snapshot or no residual buffer leaves it on `cohSnapshot` and is counted `fallback-orig`. The log line gains `resCand`, `resEligible`, `origEligible` while the setting is effective; counters `GetResidualCandidatesCounters()` beside the late round's.
- `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs` and `Ft8NativeInteropAdapter.cs`: `CohFallbackEligibleCount(snapshot)`, a managed call to the existing native plan function, used only to count the eligible candidates of the original snapshot when a run's own statistics do not exist (an original run never started, or `Residual` mode). Default method returns -1.
- `src/OpenWSFZ.Daemon/Program.cs`: the two setter calls.
- **No native change.** `git diff --stat origin/main -- native/ src/OpenWSFZ.Ft8/Native/` must be empty and the `libft8.dll` SHA-256 must equal `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`.
- Tests, `VERSION` 0.68 to 0.69 (every place the gates check), `REQUIREMENTS.md` FR-103 and a changelog row.

## Out of scope

A merged candidate list; any change to the fallback's search window, gates or thresholds; R-F4, multi-set, the late round (L1'), batches 1 to 3 and the 13 s budget arithmetic; a native change; turning the setting ON by default; a Settings-page control; the 1,589 class-NR rows no extractor reaches.

## Era

None while the setting is OFF. Turning it ON on the station starts a new live era; live figures are never pooled across it.

## Capabilities

### New Capabilities

- `ft8-coherent-fallback-residual-candidates`: the setting, which snapshot each fallback run reads, the fallback when a snapshot is missing, and the log fields.
