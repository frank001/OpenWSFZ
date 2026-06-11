## 1. Spec corrections

- [x] 1.1 Update `openspec/specs/ft8lib-interop/spec.md` — change ABI self-test expected constant from `20260004` to `20260005` and update the version history narrative in the requirement text and scenarios
- [x] 1.2 Update `openspec/specs/ft8-decoder/spec.md` — add the SNR accuracy requirement (±2.0 dB bias threshold, R&R S1 pass criterion) and all four scenarios as specified in `specs/ft8-decoder/spec.md`
- [x] 1.3 Confirm `openspec validate --all` passes after spec edits

## 2. Implementation — PCM normalisation

- [x] 2.1 Add private static helper `NormalisePcm(float[] pcm, float targetRms)` to `Ft8Decoder.cs`: compute `pcm_rms = sqrt(mean(pcm²))`; if `pcm_rms < 1e-6f` return unchanged; otherwise scale all samples by `targetRms / pcm_rms`
- [x] 2.2 Add named constant `private const float PcmNormalisationTargetRms = 0.08f` in `Ft8Decoder.cs`
- [x] 2.3 Call `NormalisePcm` on the PCM array immediately before the `Task.Run` lambda that calls `Ft8LibInterop.DecodeAll` — operate on a copy so the original buffer is not mutated
- [x] 2.4 Confirm the silent-buffer guard path is exercised: a zero buffer passed through `NormalisePcm` returns the zero buffer unchanged

## 3. Unit tests — normalisation helper

- [x] 3.1 Add `PcmNormalisationTests` test class in `OpenWSFZ.Ft8.Tests`
- [x] 3.2 Test: white-noise buffer of known RMS → output RMS equals target (within 0.1%)
- [x] 3.3 Test: silent buffer (all zeros) → returned unchanged, no exception
- [x] 3.4 Test: single-sample buffer → normalised correctly
- [x] 3.5 Test: buffer already at target RMS → scale factor ≈ 1.0, output unchanged within floating-point tolerance

## 4. Regression — existing tests still green

- [x] 4.1 Run `dotnet test OpenWSFZ.slnx -c Release` — all 313+ tests pass, 0 failures (319 passed: Ft8.Tests 84 incl. 6 new normalisation tests)
- [x] 4.2 Confirm G6 cross-platform fixture tests pass (decode results unchanged by normalisation)

## 5. R&R validation

- [x] 5.1 Run `python run_study.py --scenarios S1` with the normalisation change deployed
- [x] 5.2 Confirm OpenWSFZ S1 bias is within ±2.0 dB — three runs required; PCM normalisation alone insufficient (bias plateau at +2.28 dB regardless of target); shim constant −26.0→−26.5 dB brought bias to +1.78 dB (PASS, margin 0.22 dB). See qa-analysis.md in `results/2026-06-11-0682106/`.
- [x] 5.3 Confirm S1 %GR&R ≤ 10% and ndc ≥ 5 are unaffected by the change — %GR&R = 0.5%, ndc = 19 (both improved vs baseline)
- [x] 5.4 Record results in `qa/rr-study/results/<date>-<sha>/` and commit

## 6. Close-out

- [x] 6.1 Close GitHub issue #8 (D-002) once R&R run confirms bias ≤ ±2.0 dB
- [x] 6.2 Update MEMORY.md: D-002 resolved; R&R overall verdict updated; D-002 removed from open defects table
- [x] 6.3 Archive this OpenSpec change (`openspec archive fix-d002-snr-bias`)
