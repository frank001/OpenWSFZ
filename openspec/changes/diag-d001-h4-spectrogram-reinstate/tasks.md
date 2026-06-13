## 1. Shim — Remove H3b infrastructure from ft8_decode_all

- [x] 1.1 In `ft8_decode_all()`, remove the four declarations added for H3b from the top of the function body: `monitor_t mon2;`, `bool mon2_initialized = false;`, `float* gfsk_kernel = NULL;`, `float* gfsk_prefix = NULL;`, and `float* synth_buf_q = NULL;` (and the surrounding `4b.` comment block)
- [x] 1.2 Replace the entire H3b `if (pass == 1)` PCM-domain SIC block (malloc / synth / subtract / monitor_init(mon2) / monitor_process loop / free sequence) with the original three-line spectrogram suppression call: `for (int i = 0; i < n_all_supp; i++) suppress_candidate_tiles(&mon.wf, &all_supp_cands[i], &all_supp_msgs[i], noise_raw, all_supp_snrs[i]);`
- [x] 1.3 Remove the `const monitor_t* mon_cur = ...` declaration and revert all `mon_cur->` field accesses back to `mon.` — specifically in `ftx_find_candidates`, `ftx_decode_candidate`, `freq_hz` calculation, `dt` calculation, and the `signal_db` inner block
- [x] 1.4 Remove `if (mon2_initialized) monitor_free(&mon2);` from the cleanup section (section 6)
- [x] 1.5 Verify the GFSK helper functions (`build_gfsk_kernel`, `synth_ft8_gfsk_quad`, `compute_quadrature_amplitude`) and the monitor isolation comment block are **left in place** — do not remove them
- [x] 1.6 Verify the D-003 diagnostic additions (`tls_last_noise_floor_db` TLS variable, `tls_last_noise_floor_db = noise_floor_db` assignment, `ft8_get_last_noise_floor_db()` function) are **left in place** — do not remove them

## 2. Shim — Version bump and comment

- [x] 2.1 Change `#define FT8_SHIM_VERSION 20260009` to `#define FT8_SHIM_VERSION 20260010`
- [x] 2.2 Add a history comment entry in the shim header block documenting that H3b (20260009) is superseded and spectrogram-domain soft-SNR suppression is reinstated as the pass-1 mechanism (one paragraph, consistent style with the existing entries)
- [x] 2.3 Update the `K_MAX_PASSES` comment from `"pass 1: PCM-residual waterfall"` back to `"pass 1: spectrogram-suppressed"` to match the baseline wording

## 3. Managed layer — Interop version assertion

- [x] 3.1 In `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, change `private const int ExpectedShimVersion = 20260009;` to `private const int ExpectedShimVersion = 20260010;`
- [x] 3.2 Update the XML doc comment on `ExpectedShimVersion` (currently describing H3b GFSK quadrature SIC) to describe shim 20260010: spectrogram suppression reinstated, H3b SIC call site removed

## 4. Native binary rebuild

- [x] 4.1 Build the Windows x64 binary (`libft8.dll`) from the updated shim and commit to `src/OpenWSFZ.Ft8/Native/win-x64/`
- [x] 4.2 Trigger the CI build to produce the Linux x64 binary (`libft8.so`) and commit to `src/OpenWSFZ.Ft8/Native/linux-x64/`
- [ ] 4.3 Trigger the CI build to produce the macOS ARM64 binary (`libft8.dylib`) and commit to `src/OpenWSFZ.Ft8/Native/osx-arm64/`
- [x] 4.4 Update `Native/libft8.version.txt` to record shim version 20260010 for all three platforms

## 5. Build and test verification

- [x] 5.1 Run `dotnet build OpenWSFZ.slnx -c Release` — confirm 0 errors, 0 warnings
- [x] 5.2 Run `dotnet test OpenWSFZ.slnx -c Release` — confirm **320 passed**, 0 failures, 0 skips
- [x] 5.3 Confirm the ABI version check passes at runtime: the existing `Ft8LibInteropTests` fixture that exercises `NativeVersionCheck()` must be among the 320 passing tests

## 6. QA — S7 validation run

- [ ] 6.1 Run the S7 scenario at K=3 (93 total observations) against the rebuilt shim
- [ ] 6.2 Record per-part results in a table matching the format of `qa/rr-study/results/2026-06-12-30972ba/report.md` section 3.1
- [ ] 6.3 Confirm Gate (a): overall result ≥ 54.84% (≥ 51/93)
- [ ] 6.4 Confirm Gate (b): no per-part regression vs the `e4a3982` baseline (each part ≥ its baseline count from the H3b report table)
- [ ] 6.5 Write an NFR-023-compliant `report.md` in `qa/rr-study/results/<date>-<sha>/` and commit it
