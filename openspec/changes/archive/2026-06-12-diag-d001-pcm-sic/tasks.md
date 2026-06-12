## 1. T1 — CP-FSK Synthesis Function (standalone, not wired into decode path)

This task produces a reviewed, CI-green synthesis function that can be merged independently.
`FT8_SHIM_VERSION` stays at `20260006`. Zero regression risk — the function is present
but never called.

- [x] 1.1 Read `ft8_lib/common/monitor.c` (or equivalent in the submodule) and confirm that `monitor_init` / `monitor_free` have no hidden global or static side effects — i.e., two `monitor_t` instances can be independently initialised and freed within the same call stack. Document the finding in a brief inline comment in `ft8_shim.c` before the T2 waterfall-rebuild code. **This is a go/no-go gate for T2.**
- [x] 1.2 Add named constants to `ft8_shim.c` if not already present: `#define TONE_SPACING_HZ 6.25f` and `#define FT8_SAMPLE_RATE_F 12000.0f` (float variants, to avoid integer-division errors in synthesis math). No magic numbers in the synthesis function.
- [x] 1.3 Implement `static void synth_ft8_cpsfc(const uint8_t* tones, float freq_hz, int start_sample, float* out_buf, int buf_len)` in `ft8_shim.c`. Requirements: (a) accumulates phase continuously across all 79 symbols at rate `2π × (freq_hz + tones[sym] × TONE_SPACING_HZ) / FT8_SAMPLE_RATE_F`; (b) writes `cosf(phase)` into `out_buf[start_sample + sym*SAMPLES_PER_SYMBOL + s]` for each sample; (c) skips any index outside `[0, buf_len)` (bounds guard, not an assert); (d) does NOT allocate any heap or stack buffer — caller provides `out_buf`; (e) does NOT modify any global or TLS state.
- [x] 1.4 Implement `static float compute_projection_amplitude(const float* pcm, const float* synth, int start, int end)` in `ft8_shim.c`. Returns `dot(pcm[start..end], synth[start..end]) / dot(synth[start..end], synth[start..end])`. Returns `0.0f` if denominator is zero or if `start >= end`. No heap allocation.
- [x] 1.5 Verify `FT8_SHIM_VERSION` is still `20260006` (grep or visual check — must not be bumped in T1).
- [x] 1.6 `dotnet build OpenWSFZ.slnx -c Release` → 0 errors, 0 warnings (shim must recompile cleanly).
- [x] 1.7 `dotnet test OpenWSFZ.slnx -c Release` → 319 passed, 0 failures (no regression from unreachable new code).

---

## 2. T2 — Integration, Waterfall Rebuild, Version Bump

Depends on T1 being merged and the monitor.c gate check (task 1.1) being documented.
This task wires the T1 functions into `ft8_decode_all`, removes spectrogram suppression,
rebuilds the waterfall from the PCM residual, and bumps the shim version.

- [x] 2.1 Confirm task 1.1's monitor.c finding is documented. Do not proceed if `monitor_init` / `monitor_free` are not confirmed state-safe.
- [x] 2.2 In `ft8_decode_all`, immediately before the PCM-domain SIC phase (which replaces the old `if (pass == 1)` spectrogram-suppression block), heap-allocate two buffers: `float* residual_pcm = malloc(FT8_EXPECTED_SAMPLES * sizeof(float));` and `float* synth_buf = malloc(FT8_EXPECTED_SAMPLES * sizeof(float));`. If either returns NULL, `free` both (safe per C11 §7.22.3.3 — `free(NULL)` is a no-op), skip PCM-domain SIC, and jump to the existing pass-1 decode using the original `mon.wf`.
- [x] 2.3 On successful allocation: `memcpy(residual_pcm, pcm, FT8_EXPECTED_SAMPLES * sizeof(float))` to initialise the residual with the full input.
- [x] 2.4 Replace the existing `if (pass == 1)` spectrogram-suppression block (the `suppress_candidate_tiles` loop) with PCM-domain SIC: for each signal `i` in `[0, n_all_supp)`, (a) `memset(synth_buf, 0, FT8_EXPECTED_SAMPLES * sizeof(float))`; (b) compute `start_sample = all_supp_cands[i].time_offset * mon.block_size`, clamped to `[0, FT8_EXPECTED_SAMPLES)`; (c) compute `freq_hz_i` from `all_supp_cands[i]` using the same formula already in the SNR block; (d) call `ft8_encode(all_supp_msgs[i].payload, tones_tmp)` where `tones_tmp` is a local `uint8_t[FT8_NN]`; (e) call `synth_ft8_cpsfc(tones_tmp, freq_hz_i, start_sample, synth_buf, FT8_EXPECTED_SAMPLES)`; (f) compute signal window `[start_sample, min(start_sample + FT8_NN * SAMPLES_PER_SYMBOL, FT8_EXPECTED_SAMPLES))`; (g) call `compute_projection_amplitude` over that window; (h) subtract `a * synth_buf[j]` from `residual_pcm[j]` for each j in the window.
- [x] 2.5 After the PCM-domain SIC loop, `free(synth_buf)` (no longer needed).
- [x] 2.6 Declare `monitor_t mon2;` on the stack (the struct itself is small). Call `monitor_init(&mon2, &cfg)` with the same config used for `mon`. Process `residual_pcm` through `mon2` block-by-block: `for (int pos = 0; pos + mon2.block_size <= FT8_EXPECTED_SAMPLES; pos += mon2.block_size) monitor_process(&mon2, residual_pcm + pos);`. Then `free(residual_pcm)`.
- [x] 2.7 In the pass==1 decode block, replace all `&mon.wf` references with `&mon2.wf` so pass 1 searches the rebuilt waterfall. Also update the `freq_hz` and `dt` extraction in that block to use `mon2` parameters (symbol_period, min_bin, etc.) — these will be identical since the config is the same, but references must be consistent.
- [x] 2.8 After pass 1 completes, call `monitor_free(&mon2)` before the existing `monitor_free(&mon)` in section 6 (cleanup).
- [x] 2.9 Bump `FT8_SHIM_VERSION` from `20260006` to `20260008` in `ft8_shim.c`. Add the version history entry: `20260008 — diag-d001-pcm-sic: PCM-domain SIC replaces spectrogram suppression; heap-allocated residual_pcm and synth_buf; CP-FSK synthesis at phase zero; waterfall rebuilt from PCM residual before pass 1.`
- [x] 2.10 Update `ExpectedShimVersion` in `Ft8LibInterop.cs` from `20260006` to `20260008`. Add corresponding version history entry in the `ExpectedShimVersion` XML doc comment.
- [x] 2.11 Update the `MaxResults` and `MaxDecodePasses` XML doc comments in `Ft8LibInterop.cs` to note that pass 1 now decodes the PCM-residual waterfall (no capacity change — still 340 / 2).
- [x] 2.12 Rebuild the Windows x64 `libft8.dll` from updated `ft8_shim.c`. Update `libft8.version.txt` with new SHA, build date, and shim version `20260008`.
- [x] 2.13 Rebuild the Linux x64 `libft8.so` and macOS ARM64 `libft8.dylib`. Update `libft8.version.txt` for all three platforms. (macOS ARM64: CI always rebuilds from ft8_shim.c — see .github/workflows/ci.yml step "Build native macOS dylib")
- [x] 2.14 Add an integration smoke-test in `OpenWSFZ.Ft8.Tests`: call `Ft8Decoder.DecodeAsync` with the `synth-qso-01` fixture (the same fixture used by `RealSignalFixtureTests`); assert that the result is non-empty and that the expected message is present. This test must pass before T2 is merged.
- [x] 2.15 `dotnet build OpenWSFZ.slnx -c Release` → 0 errors, 0 warnings.
- [x] 2.16 `dotnet test OpenWSFZ.slnx -c Release` → all tests pass (≥ 320 including the new smoke-test).

---

## 3. T3 — S7 R&R Study (QA, post-T2 merge)

This task is triggered by NS-001 condition (a): H3 fix merged → re-run S7 and S8.

- [x] 3.1 Confirm the build under test is at `FT8_SHIM_VERSION = 20260008` before starting the study run.
- [x] 3.2 Run the S7 R&R harness (K=3, all 14 parts P0–P14) against shim `20260008` and WSJT-X 2.7.0 as the reference appraiser.
- [x] 3.3 Evaluate H3 gate: (a) primary — any measurable improvement on P0 or P1 vs baseline 0/6 (K=3); (b) secondary — ≥ +5 pp overall improvement vs the 2-pass baseline (54.84%). Both gates must be met for H3 to be accepted.
- [x] 3.4 Generate all supporting artefacts (CSV, PNGs) and write an NFR-023-compliant `report.md` in `qa/rr-study/results/<date>-<sha>/`. The five mandatory sections must be present: hypothesis, data summary, results with graphs, summary verdict table, recommendations.
- [x] 3.5 Update `openspec/specs/iterative-subtraction/spec.md` AC-IS-1 history section with the H3 result (PASS or FAIL) and the S7 overall percentage.
- [x] 3.6 Update `MEMORY.md` with the H3 result and the new NS-001 trigger state.
- [x] 3.7 **If H3 ACCEPTED:** Close or annotate GitHub issue #3 with evidence. Evaluate H3b (phase estimation) and PCM-SIC + residual-spectrogram combination as follow-on improvements. Update D-001 severity if the gap to WSJT-X has materially closed. *(N/A — H3 REJECTED; this path never fires. See task 3.8 and qa/rr-study/results/2026-06-12-da133f4/report.md.)*
- [x] 3.8 **If H3 REJECTED:** Record H3 findings in issue #3. Evaluate H3b (phase estimation via dot-product correlation sweep) as the next hypothesis. Update MEMORY.md deferred-next-steps accordingly.
