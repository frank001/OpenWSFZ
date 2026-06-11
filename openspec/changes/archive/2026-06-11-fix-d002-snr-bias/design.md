## Context

`Ft8Decoder.cs` currently passes the raw captured PCM `float[]` to `Ft8LibInterop.DecodeAll` without any amplitude conditioning. The native `ft8_decode_all` function computes its noise floor estimate using a histogram-median of all `WF_ELEM_T` (uint8) waterfall bin values. The waterfall bins are populated from the windowed short-time FFT of the input PCM; the uint8 encoding has a resolution of 0.5 dB and a floor at 0 (representing approximately −120 dBfs).

Three independent R&R study runs (post-FIR-synthesiser-fix) show a flat +2.42 dB systematic bias in OpenWSFZ SNR reports vs true SNR (slope 0.002 dB/dB, R² = 0.001). WSJT-X over-reports by +0.98 dB using its own noise estimator. The 1.44 dB excess in OpenWSFZ is the gap to close.

**Hypothesised mechanism:** When PCM amplitude is low, waterfall bins quantise toward 0, causing the histogram-median to undercount the true noise power. Signal bins are stronger and remain well above the quantisation floor, so `signal_db` is accurate while `noise_floor_db` is biased low. Since `SNR = signal_db − noise_floor_db − 26`, a depressed noise floor yields an inflated SNR reading. Normalising PCM to a fixed RMS level keeps noise bins in a range where the histogram-median produces an accurate noise floor estimate, regardless of the source audio level.

## Goals / Non-Goals

**Goals:**
- Bring OpenWSFZ SNR bias within ±2.0 dB on the R&R S1 scenario
- Implement the fix entirely in managed code — no native changes
- Preserve decode message correctness (existing G6 fixture tests must continue to pass)
- Handle the silent-buffer edge case gracefully

**Non-Goals:**
- Fixing D-001 (co-channel decode gap) — separate root cause, separate investigation
- Fixing D-003 (intermittent `signal_db` drop) — separate root cause, separate investigation
- Matching WSJT-X SNR values exactly — the threshold is ±2.0 dB, not zero bias
- Improving decode sensitivity or message recovery rate

## Decisions

### D-1: RMS normalisation, not peak normalisation

**Chosen:** Normalise PCM to a fixed target RMS (`pcm_rms = sqrt(mean(pcm²))`), then scale all samples by `target_rms / pcm_rms`.

**Rejected: Peak normalisation** — peak is sensitive to outlier samples (a single transient spike skews the scale factor). RMS represents the energy distribution of the buffer, which is what the waterfall histogram measures.

**Rejected: Hardcoded dB offset** — a calibration constant baked into the code would require recalibration whenever the audio source or synthesiser amplitude changes. It does not address the root cause and would silently fail under different operating conditions.

**Rejected: Recomputing noise floor in managed code** — would require reimplementing the libft8 waterfall computation, introducing new sources of error and coupling to the native implementation details.

### D-2: Normalisation applied inside `Ft8Decoder.cs`, before `DecodeAll`

The normalisation is a pre-processing step owned by the managed decode orchestration layer. `Ft8LibInterop` remains a thin P/Invoke wrapper with no signal processing logic of its own. The `DecodeAll(float[])` signature is unchanged.

### D-3: Silent-buffer guard — skip normalisation if RMS ≈ 0

If `pcm_rms < ε` (proposed: `1e-6f`), the buffer is effectively silent and normalisation would produce infinity or NaN. In this case, pass the buffer unchanged to `DecodeAll`; the native library returns zero results for a silent buffer regardless of amplitude.

### D-4: Target RMS to be confirmed by R&R run

The exact target RMS value is an empirical constant. A value in the range 0.05–0.15 is expected to be appropriate for typical FT8 audio levels (signal + noise mixture with SNR −12 to +15 dB). The implementation will use **0.08** as the initial target; the R&R S1 run will confirm or refute this. If bias remains outside ±2.0 dB, the target is adjusted and re-run before merge. The chosen value is committed as a named constant `PcmNormalisationTargetRms` in `Ft8Decoder.cs` for easy tuning.

## Risks / Trade-offs

**[Risk] Normalisation changes decoded message set** → Mitigation: existing G6 cross-platform fixture tests pass PCM through `DecodeAll`; if any decode is lost or gained, those tests will catch it. The LDPC decoder works on soft log-likelihood ratios derived from relative bin magnitudes; uniform amplitude scaling should leave LLR ratios unchanged.

**[Risk] Target RMS is wrong on first attempt; bias remains outside ±2.0 dB** → Mitigation: the target is a named constant tunable without architecture changes. The R&R run is the acceptance gate; the change is not merged until the run passes.

**[Risk] Live production audio has different amplitude characteristics than the synthesiser** → Mitigation: RMS normalisation is amplitude-agnostic — it brings any input level to the same target, which is the point. The bias fix is expected to hold across input levels as long as the noise-floor mechanism holds.

**[Risk] Silent buffer edge case — divide-by-zero** → Mitigation: explicit `pcm_rms < 1e-6f` guard; no normalisation applied; passes unchanged to native. Covered by an existing test (`Decode does not stall… silent buffer`).

## Migration Plan

No migration required. The change is internal to `Ft8Decoder.cs`. The `PcmNormalisationTargetRms` constant is set once and committed. The R&R run is the validation gate. Rollback: revert `Ft8Decoder.cs` to the pre-normalisation version; no native or API changes to undo.

## Open Questions

**OQ-1:** Does the target RMS of 0.08 produce bias ≤ ±2.0 dB on S1? — Resolved at implementation time by running the R&R S1 scenario before merge.

**OQ-2:** Does normalisation affect the G6 fixture test pass rate? — Resolved at implementation time; G6 tests run as part of `dotnet test`.
