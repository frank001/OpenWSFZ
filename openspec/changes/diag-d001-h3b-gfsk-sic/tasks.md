## 1. T1 — GFSK Quadrature Synthesiser + Estimator (standalone, not wired into decode path)

This task replaces the two H3 synthesis/estimation functions with their H3b counterparts.
`FT8_SHIM_VERSION` stays at `20260008`. The new functions are present but not reachable from
`ft8_decode_all`. Zero regression risk; T1 is independently CI-green and reviewable.

- [x] 1.1 Remove the `synth_ft8_cpsfc` function definition from `ft8_shim.c` and its section
      comment. Remove the `compute_projection_amplitude` function definition. Remove the
      `/* ── CP-FSK synthesis helpers (T1 — present but not yet wired into decode) ── */`
      header comment block. Confirm that no call sites yet exist (the functions are referenced
      only in the pass==1 block which will be updated in T2 — do not touch that block in T1).

- [x] 1.2 Add a new section `/* ── GFSK quadrature synthesis helpers (H3b) ── */` in
      `ft8_shim.c` after the `suppress_candidate_tiles` function. Within that section:

      **1.2a** Add constants if not already present (check for duplicates before adding):
      ```c
      /* GFSK pulse parameters (BT=2.0, 3-symbol span — matches QA Python synthesiser) */
      #define GFSK_BT         2.0f
      #define GFSK_SPAN_SYMS  3
      #define GFSK_KERNEL_LEN (GFSK_SPAN_SYMS * FT8_SAMPLES_PER_SYMBOL)   /* 5760 */
      ```

      **1.2b** Implement `static void build_gfsk_kernel(float* kernel, float* prefix)`.
      This function computes the normalised Gaussian pulse into `kernel[GFSK_KERNEL_LEN]`
      and its prefix sum into `prefix[GFSK_KERNEL_LEN + 1]`, matching the Python formula
      exactly:
      ```
      sigma = sqrt(ln(2)) / (2 * pi * BT)     [in symbol periods, ≈ 0.06622]
      For j in [0, GFSK_KERNEL_LEN):
          t_j = ((float)j - (float)(GFSK_KERNEL_LEN / 2) + 0.5f)
                / (float)FT8_SAMPLES_PER_SYMBOL
          kernel[j] = expf(-t_j * t_j / (2.0f * sigma * sigma))
      Normalise: divide all kernel[j] by sum(kernel[j])
      prefix[0] = 0.0f
      For j in [0, GFSK_KERNEL_LEN): prefix[j+1] = prefix[j] + kernel[j]
      ```
      The function takes no other parameters. `kernel` and `prefix` are caller-allocated
      and caller-freed (heap buffers passed in from the SIC block). The function MUST NOT
      allocate any heap or stack arrays > 100 bytes internally.

      **1.2c** Implement `static void synth_ft8_gfsk_quad(const uint8_t* tones, float freq_hz,
      int start_sample, const float* prefix, float* buf_sin, float* buf_cos, int buf_len)`.
      Requirements:
      - Uses the precomputed kernel prefix sum to compute the GFSK-smoothed instantaneous
        frequency at each sample, using the piecewise-constant convolution optimisation
        described in design.md Decision 1 (at most 4 symbols contribute per sample).
      - Accumulates phase continuously: `phase += 2π × inst_freq_i / FT8_SAMPLE_RATE_F`
        for each sample, starting from `phase = 0.0f`.
      - For each sample index `i` in `[start_sample, start_sample + FT8_NN × FT8_SAMPLES_PER_SYMBOL)`:
        if `i` is in `[0, buf_len)`, writes `sinf(phase)` to `buf_sin[i]` and `cosf(phase)`
        to `buf_cos[i]`; samples outside `[0, buf_len)` are silently skipped (bounds guard).
      - Does NOT allocate any heap or stack buffer exceeding 100 bytes.
      - Does NOT modify any global or TLS state.
      - The `prefix` parameter is the output of `build_gfsk_kernel`; the function MUST NOT
        call `build_gfsk_kernel` internally.

      **1.2d** Implement `static void compute_quadrature_amplitude(const float* pcm,
      const float* synth_sin, const float* synth_cos, int start, int end,
      float* out_a_i, float* out_a_q)`. Requirements:
      - Computes `dot_I = dot(pcm[start..end], synth_sin[start..end])`,
        `dot_Q = dot(pcm[start..end], synth_cos[start..end])`,
        `energy = dot(synth_sin[start..end], synth_sin[start..end])`.
      - If `energy == 0.0f` OR `start >= end`: sets `*out_a_i = 0.0f; *out_a_q = 0.0f`; returns.
      - Otherwise: `a = sqrtf(dot_I*dot_I + dot_Q*dot_Q) / energy;
        phi = atan2f(dot_Q, dot_I);
        *out_a_i = a * cosf(phi); *out_a_q = a * sinf(phi);`
      - No heap allocation. No global or TLS state modified.

- [x] 1.3 Add a unit test in `OpenWSFZ.Ft8.Tests` — new test class `GfskQuadratureSynthTests`.
      The test class MUST be `internal` and placed in the `OpenWSFZ.Ft8.Tests` namespace.
      It requires `[InternalsVisibleTo]` or test of exported behaviour (see note below).

      Since `synth_ft8_gfsk_quad` and `build_gfsk_kernel` are `static` C functions not
      directly callable from managed code, the unit test MUST be written as an integration
      test through a thin managed wrapper or by verifying synthesiser behaviour via
      `Ft8Decoder.DecodeAsync` on a known synthetic fixture.

      The required assertion: call `Ft8Decoder.DecodeAsync` with the `synth-qso-01` fixture
      (mono PCM, 12 kHz, 180 000 samples). Assert that the decode result is non-empty and
      that the decoded message matches the expected text for `synth-qso-01`. This verifies
      that the new functions, when wired (in T2), do not break the basic decode path. Tag this
      test `[Fact(Skip = "Wired in T2")]` for now so it is present but skipped until T2.

      Note: a deeper unit test comparing C synthesiser output against Python synthesiser
      output sample-by-sample is desirable but requires a test harness capable of calling
      the native functions directly. If the Developer cannot construct such a test within the
      existing test framework without significant scaffolding, the integration smoke-test
      above is sufficient for T1. QA will confirm correct GFSK output via S7 R&R in T3.

- [x] 1.4 Verify `FT8_SHIM_VERSION` remains `20260008` (grep the shim; it must not be bumped
      in T1).

- [x] 1.5 `dotnet build OpenWSFZ.slnx -c Release` → 0 errors, 0 warnings.

- [x] 1.6 `dotnet test OpenWSFZ.slnx -c Release` → all existing tests pass; the new skipped
      test appears in output as `Skipped`; no failures.

---

## 2. T2 — Integration, Version Bump, Binary Rebuild

Depends on T1 being merged. This task wires the T1 functions into `ft8_decode_all`, replaces
the H3 scalar SIC path with the H3b quadrature path, and bumps the shim version.

- [ ] 2.1 In the `/* ── 4a. Cross-pass SIC accumulator ─── */` section of `ft8_decode_all`,
      confirm the existing `all_supp_cands`, `all_supp_msgs`, `all_supp_snrs` arrays and
      `n_all_supp` counter are unchanged. No modification needed in this section.

- [ ] 2.2 In the `/* ── 4b. Second monitor ─── */` section, add declarations for the two new
      heap buffer pointers alongside the existing `mon2` / `mon2_initialized` declarations:
      ```c
      float* gfsk_kernel = NULL;
      float* gfsk_prefix = NULL;
      float* synth_buf_q = NULL;
      ```
      These are declared alongside the existing `monitor_t mon2; bool mon2_initialized = false;`
      so that all SIC-related state is visible in one location.

- [ ] 2.3 In the `if (pass == 1)` SIC block, after the existing `synth_buf` heap allocation
      and NULL-check, add two further allocations:
      ```c
      gfsk_kernel = malloc((GFSK_KERNEL_LEN)     * sizeof(float));
      gfsk_prefix = malloc((GFSK_KERNEL_LEN + 1) * sizeof(float));
      synth_buf_q = malloc(FT8_EXPECTED_SAMPLES  * sizeof(float));
      ```
      Extend the NULL-check to cover all five buffers: if ANY of
      `residual_pcm`, `synth_buf`, `synth_buf_q`, `gfsk_kernel`, `gfsk_prefix`
      is NULL, free all five (in any order — `free(NULL)` is a no-op) and skip to the
      waterfall rebuild (same fallback pattern as H3: `mon2_initialized` stays `false`,
      pass 1 falls back to `mon.wf`).

- [ ] 2.4 On successful allocation, call `build_gfsk_kernel(gfsk_kernel, gfsk_prefix)`
      immediately after the NULL-check, before the signal subtraction loop.

- [ ] 2.5 In the signal subtraction loop (the `for (int i = 0; i < n_all_supp; i++)` block),
      replace the existing synthesis and amplitude computation:

      **Remove:**
      ```c
      synth_ft8_cpsfc(tones_tmp, freq_hz_i, start_sample, synth_buf, FT8_EXPECTED_SAMPLES);
      ...
      float a = compute_projection_amplitude(residual_pcm, synth_buf, win_start, win_end);
      for (int j = win_start; j < win_end; j++)
          residual_pcm[j] -= a * synth_buf[j];
      ```

      **Replace with:**
      ```c
      memset(synth_buf,   0, FT8_EXPECTED_SAMPLES * sizeof(float));
      memset(synth_buf_q, 0, FT8_EXPECTED_SAMPLES * sizeof(float));
      synth_ft8_gfsk_quad(tones_tmp, freq_hz_i, start_sample,
                          gfsk_prefix, synth_buf, synth_buf_q, FT8_EXPECTED_SAMPLES);

      float a_i, a_q;
      compute_quadrature_amplitude(residual_pcm, synth_buf, synth_buf_q,
                                   win_start, win_end, &a_i, &a_q);
      for (int j = win_start; j < win_end; j++)
          residual_pcm[j] -= a_i * synth_buf[j] + a_q * synth_buf_q[j];
      ```

- [ ] 2.6 After the subtraction loop and before `monitor_init(&mon2, &cfg)`, free the three
      synthesis-only buffers that are no longer needed:
      ```c
      free(synth_buf);    synth_buf    = NULL;
      free(synth_buf_q);  synth_buf_q  = NULL;
      free(gfsk_kernel);  gfsk_kernel  = NULL;
      free(gfsk_prefix);  gfsk_prefix  = NULL;
      ```
      `residual_pcm` is still needed for the waterfall rebuild and is freed after
      `monitor_process` calls complete (same as H3 task 2.5/2.6).

- [ ] 2.7 Bump `FT8_SHIM_VERSION` from `20260008` to `20260009` in `ft8_shim.c`. Add the
      version history entry in the top-of-file block comment:
      ```
      20260009 — diag-d001-h3b-gfsk-sic: GFSK quadrature synthesiser replaces CP-FSK
                 scalar synthesiser; analytic quadrature amplitude estimator replaces
                 scalar projection; two additional heap buffers (synth_buf_q, gfsk_kernel)
                 plus GFSK kernel prefix sum (gfsk_prefix) allocated in the pass-1 SIC
                 block; total PCM-domain SIC heap ≈ 2.21 MB.
      ```
      Also update the `/* diag-d001-pcm-sic (FT8_SHIM_VERSION 20260008) */` block comment
      with a short note that H3b supersedes it at version 20260009.

- [ ] 2.8 Update `ExpectedShimVersion` in `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` from
      `20260008` to `20260009`. Add the corresponding entry in the `ExpectedShimVersion` XML
      doc comment history section:
      ```
      20260009 — diag-d001-h3b-gfsk-sic: GFSK quadrature SIC; analytic phase estimation;
                 heap increased from 1.44 MB to ~2.21 MB for PCM-domain SIC stage.
      ```

- [ ] 2.9 Remove the `[Fact(Skip = "Wired in T2")]` attribute from the smoke-test added in
      T1 task 1.3. Confirm the test asserts the expected decode for `synth-qso-01` and passes.

- [ ] 2.10 Rebuild the Windows x64 `libft8.dll` from the updated `ft8_shim.c` (see
      `BUILD.md` for exact compiler command). Update `libft8.version.txt` with new SHA,
      build date, and `FT8_SHIM_VERSION = 20260009` for the Windows entry.

- [ ] 2.11 Rebuild the Linux x64 `libft8.so`. Update `libft8.version.txt` for Linux.

- [ ] 2.12 Rebuild the macOS ARM64 `libft8.dylib` (Captain responsibility — cross-compilation
      from Windows is not supported). Update `libft8.version.txt` for macOS.

- [ ] 2.13 `dotnet build OpenWSFZ.slnx -c Release` → 0 errors, 0 warnings.

- [ ] 2.14 `dotnet test OpenWSFZ.slnx -c Release` → all tests pass (smoke-test from T1 now
      runs and passes; no other regressions). Confirm the ABI self-test passes (version check
      in `Ft8LibInterop` must see `20260009` and not throw).

---

## 3. T3 — S7 R&R Study (QA, post-T2 merge)

This task is triggered by NS-001 condition (a): H3b fix merged → re-run S7.
Same gate criteria as H3. Both gates must be met for H3b to be accepted.

- [ ] 3.1 Confirm the build under test is at `FT8_SHIM_VERSION = 20260009` before starting.

- [ ] 3.2 Run the S7 R&R harness (K=3, all parts P0–P14) against shim `20260009` and
      WSJT-X 2.7.0 as the reference appraiser.

- [ ] 3.3 Evaluate H3b gate:
      - **Gate (a) — primary (co-channel):** any measurable improvement on P0 or P1 vs
        baseline 0/6 (K=3). Baseline from `da133f4` H3 run: 0/6 for both.
      - **Gate (b) — secondary (overall):** overall decode rate ≥ +5 pp vs the 2-pass
        spectrogram-suppression baseline of 54.84% (i.e., ≥ 59.84%).
        Recall: H3 scored 40.86% (−13.98 pp) — a regression; any result above 54.84% + 5 pp
        constitutes progress. Both gates must be met.

- [ ] 3.4 Generate all supporting artefacts (CSV, PNGs) and write an NFR-023-compliant
      `report.md` in `qa/rr-study/results/<date>-<sha>/`. All five mandatory sections must
      be present: hypothesis, data summary, results with graphs, summary verdict table,
      recommendations.

- [ ] 3.5 Update `openspec/specs/iterative-subtraction/spec.md` AC-IS-1 history section
      with the H3b result (ACCEPTED or REJECTED) and the S7 overall percentage.

- [ ] 3.6 Update `MEMORY.md` with the H3b result and the new NS-001 trigger state.

- [ ] 3.7 **If H3b ACCEPTED:** Close or annotate GitHub issue #3 with evidence. Evaluate
      whether combining PCM-domain SIC with residual spectrogram suppression offers further
      improvement (H3c). Update D-001 severity if the gap to WSJT-X has materially closed.

- [ ] 3.8 **If H3b REJECTED:** Record H3b findings in issue #3. Analyse root cause: if
      amplitude is still near-zero, the synthesiser is still mismatched (check kernel formula
      vs Python); if amplitude is non-zero but P0/P1 remain at 0/6, the cancellation is
      insufficient at 0 dB SNR (evaluate H3c: amplitude scaling + residual spectrogram
      suppression, or defer D-001). Update MEMORY.md deferred-next-steps accordingly.
