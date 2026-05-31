## Context

The OpenWSFZ FT8 decoder wraps `kgoba/ft8_lib` via a thin native shim (`ft8_shim.c`) that orchestrates the full decode pipeline: build waterfall from PCM, find sync candidates, LDPC-decode each candidate, deduplicate, return results. The current pipeline performs a single pass. The `ft8-decoder` spec already includes iterative signal subtraction in a SHALL timing requirement but the shim has never implemented it.

Baseline measurement (42-cycle corpus, 887 WSJT-X decodes): 591 matched (66.6%), 24 false positives (3.9%). WSJT-X achieves parity by performing a second decode pass on the spectrogram residual after stripping decoded signals. Phase 2A exit criteria (RECOVERY_PLAN.md §7) require "real-signal fixtures decode at parity with WSJT-X; full suite green."

The native/ft8_lib submodule was forked onto branch `msvc-compat` (commit d18ed84) to commit the MSVC VLA compatibility patches. This is the prerequisite for Path A (C-shim implementation).

## Goals / Non-Goals

**Goals:**
- Implement a second spectrogram-domain decode pass in `ft8_shim.c` using the existing `ftx_find_candidates` / `ftx_decode_candidate` API.
- Suppress decoded signal energy from the `ftx_waterfall_t.mag` array between passes (all 8 FT8 tone bins × 79 symbols × all time/frequency over-sampling sub-bins → noise-floor median value).
- Add a named constant `K_MAX_PASSES 2` (no magic numbers).
- Expose per-pass new-decode counts to C# via `ft8_get_last_pass_counts()` so `Ft8Decoder` can log at Debug level per AC-IS-4.
- Bump `FT8_SHIM_VERSION` to `20260001`; ABI self-test catches stale binaries.
- Achieve ≥ 80% recovery on the 42-cycle corpus (≥ 710 / 887 matched) with false-positive rate ≤ 6%.
- Remain within the 13-second decode budget on development hardware and 30-second budget on CI runners.
- All three platform binaries rebuilt and committed; G6 gate green on all three CI legs.

**Non-Goals:**
- Exact WSJT-X waveform subtraction (precise PCM-domain reconstruction and subtraction). The simpler "zero all 8 tone bins" approach is sufficient to expose masked signals.
- More than two total passes. `K_MAX_PASSES = 2` matches WSJT-X behaviour; additional passes have diminishing returns and consume wall-clock budget.
- Changes to the C# `IModeDecoder` interface, `CycleFramer`, `AllTxtWriter`, audio pipeline, or web frontend — all unchanged.
- Porting the second-pass logic to the p11/Bluestein pipeline (abandoned).

## Decisions

### Decision 1 — Path A: implement in the C shim (`ft8_shim.c`), not in C# or a different library

**Chosen:** Path A (C shim).

**Rationale:**

- The spectrogram (`ftx_waterfall_t.mag`) is a `WF_ELEM_T*` (non-const) heap buffer allocated inside `monitor_t`. The shim already owns this memory between the waterfall-build step and `monitor_free`. Suppression is a direct array write — no reconstruction, no approximation.
- Path B (PCM-domain subtraction from C#) requires reconstructing the FT8 signal waveform at the correct amplitude, frequency, and phase. Any error in reconstruction degrades rather than improves the second pass. This path is materially harder to implement correctly and is more likely to introduce regressions.
- Path C (different library) — no permissively-licensed FT8 decoder with iterative subtraction was identified that satisfies the project's licence constraint. Research deferred; no candidate found.
- Path A adds zero new dependencies. The second pass calls the same `ftx_find_candidates` and `ftx_decode_candidate` functions already called in the first pass. The waterfall memory is already allocated.

**Disadvantage acknowledged:** the shim now diverges from upstream `kgoba/ft8_lib`. This is managed by the `msvc-compat` fork already in place; the iterative subtraction code lives in `ft8_shim.c` (our overlay), not inside the submodule, so no submodule divergence is introduced by this change.

---

### Decision 2 — Waterfall suppression: zero all 8 tone bins × 79 symbols × all sub-bins

**Chosen:** suppress the entire 8-tone × 79-symbol × (time_osr × freq_osr) tile region to the noise-floor median raw byte.

**Rationale:**

The exact WSJT-X approach subtracts a precisely modeled waveform from the spectrogram (requiring known per-symbol tone assignments). The "zero all 8 bins" approach is:
- Simpler: no need to know which tone was transmitted at each symbol.
- More conservative: over-suppresses the signal (can't mask a weak co-channel signal that happens to share bins), but this is acceptable for two passes because strong signals dominate many bins anyway.
- Correct: setting tiles to the noise-floor median is equivalent to telling the second pass "there is nothing interesting here," which is the goal.

Setting to `noise_raw` (the median histogram byte, not zero) avoids introducing a visible notch below the noise floor that could confuse the candidate scorer.

---

### Decision 3 — ABI version bump and `ft8_get_last_pass_counts` as a new export

**Chosen:** bump `FT8_SHIM_VERSION` to `20260001`; add `ft8_get_last_pass_counts(int* out_counts, int capacity)` as a second exported function.

**Rationale:**

The first pass count changes semantically (it is now one of two passes). Without a version bump, a stale binary would silently give incorrect results. The ABI self-test (`ft8_lib_version_check`) fires on first load and fails fast with a clear error, protecting against "worked on my machine" bugs.

`ft8_get_last_pass_counts` is added rather than changing the `ft8_decode_all` signature so that:
- Callers who do not need per-pass stats are unaffected.
- The per-pass counts are stored in thread-local storage (`tls_pass_counts`), populated during `ft8_decode_all`, and readable after the call returns — matching the call pattern in `Ft8Decoder.cs` (call `DecodeAll`, then read stats, then log).

**Alternative rejected:** returning per-pass counts via an extra `out` parameter on `ft8_decode_all`. This changes the function signature, requires updating all three binaries, and breaks any future P/Invoke callers — unnecessary complexity for a single-consumer shim.

---

### Decision 4 — `K_MAX_PASSES = 2` matching WSJT-X default

**Chosen:** two total passes (one first pass, one residual pass).

**Rationale:** WSJT-X performs exactly two passes by default. The 33.4% gap is almost entirely attributable to the missing second pass. A third pass would add ~2–3 s of wall-clock time with negligible recovery gain (the residual after two passes contains only signals too weak to decode). The timing budget (13 s / 30 s CI) is comfortable with two passes based on the current ~2–3 s first-pass baseline.

If the timing budget is tight on a 30-simultaneous-signal test case (worst case ~10 s first pass), the second pass will still fit within 30 s on CI runners. The `Ft8DecoderPerformanceTests` assertions cover this.

---

### Decision 5 — `"parity"` numerical definition

Per AC-IS-7 §5: the Architect considers **80% recovery rate** (≥ 710 / 887 matched decodes) as the acceptable long-term steady state. This aligns with the AC-IS-1 merge requirement and leaves headroom for the ~6% theoretical maximum recoverable by a second pass (signals buried below all-noise bins that not even WSJT-X's full reconstruction can surface). True 100% parity would require exact waveform reconstruction; the "zero all tone bins" approach is expected to recover 80–87% of the WSJT-X corpus. Anything ≥ 80% is "parity" for this project.

## Risks / Trade-offs

- **[Timing risk]** A busy band with 30+ simultaneous signals could push first-pass candidate scoring beyond 8–10 s, leaving insufficient budget for a second pass. → Mitigation: characterise worst-case timing on the replay harness before merging. The `Ft8DecoderPerformanceTests` suite gates this. If the second pass makes a timing assertion fail, add a guard: skip the second pass when first-pass elapsed time exceeds `K_SECOND_PASS_TIME_LIMIT_MS`.

- **[False positive increase]** The second pass surfaces borderline candidates that were masked by stronger signals. Some of these may be true FT8 messages; others may be LDPC false positives. → Mitigation: the AC-IS-1 false-positive allowance is relaxed to ≤ 6% (from current 3.9%). The existing `IsPlausibleMessage` filter in `Ft8Decoder.cs` provides a second layer of protection.

- **[Binary rebuild logistics]** All three platform binaries must be rebuilt and committed; the macOS binary requires a GitHub Actions workflow_dispatch job or CI matrix build. → Mitigation: build Windows locally (MSVC), Linux via WSL2 (GCC), macOS via the existing CI workflow pattern from p13.

- **[Deduplication correctness]** The second pass must not re-emit messages already decoded in the first pass. The existing message hash table is shared across both passes; a message decoded in pass 1 occupies a slot in `decoded_ht`, so pass 2 will detect it as a duplicate and skip it. This must be verified by a unit test with a synthetic case where the same message appears in both passes.

- **[Submodule ABI]** The MSVC patches are on `native/ft8_lib@msvc-compat` (not on `origin/main` of the submodule fork). The submodule pointer is committed in the superproject. Any new developer who clones the repo with `--recurse-submodules` will get the `msvc-compat` commit, which is correct. CI runs `git submodule update --init --recursive`, which will also get the right commit. No action required.

## Migration Plan

1. Implement and test locally (Windows, Release, replay harness).
2. Rebuild `libft8.dll` (Windows, MSVC from `native/ft8_lib` on `msvc-compat`).
3. Rebuild `libft8.so` (Linux, WSL2 GCC).
4. Rebuild `libft8.dylib` (macOS, GitHub Actions workflow_dispatch).
5. Run replay harness → confirm ≥ 80% recovery. Regenerate `findings.md`.
6. Expand `.expected.txt` fixture answer keys for medium-SNR signals (QA review).
7. Run full test suite on Windows. Confirm G6 green with expanded keys.
8. Push branch; CI confirms G6 green on all three platforms.
9. Update `RECOVERY_PLAN.md` Phase 2A exit criteria.
10. Open PR; QA reviews expanded answer keys individually per AC-IS-2.

**Rollback:** revert `ft8_shim.c` to the single-pass version, restore `FT8_SHIM_VERSION` to `20240001`, rebuild all three binaries, revert `ExpectedShimVersion` in `Ft8LibInterop.cs`. The `.expected.txt` answer-key expansion can remain (it is additive; single-pass decoder still recovers all high-SNR entries).

---

### Decision 6 — Measured performance: 69.1% (not 80%) — spectrogram-domain ceiling

**Finding (post-implementation measurement):**

Path A achieves **69.1% recovery (613/887 matched)** against the 42-cycle WSJT-X corpus, up from 66.6% baseline. The 80% AC-IS-1 target was not reached. Extensive parametric tuning was performed:

| Approach | Matched | Recovery |
|---|---|---|
| Baseline (single pass, K_MIN_SCORE=10) | 591 | 66.6% |
| Broad suppression (zero all 8 tone bins) | 594 | 67.0% |
| Narrow suppression (exact tone from ft8_encode) | 606 | 68.3% |
| ±1 bin (capture Hann first sidelobe) + LDPC=50 pass2 | **613** | **69.1%** |
| ±2 bin (too aggressive, destroys co-channel signal) | 607 | 68.5% |

**Root cause analysis:** The waterfall stores only MAGNITUDES (uint8 per bin). The FFT Hann window creates leakage in bins ±1 to ±5 from the transmitted tone. Suppressing the exact tone bin (and ±1 neighbour) removes the immediate sidelobe but cannot undo the full leakage pattern. The remaining sidelobe energy of strong signals still masks weak co-channel signals.

**More fundamentally:** PCM-domain waveform reconstruction was investigated but found infeasible with the current waterfall frequency resolution. The waterfall provides carrier frequency at ±3.125 Hz accuracy. Over a 1920-sample FT8 symbol at 12 kHz, a ±3.125 Hz frequency error causes a ±π phase drift at the end of the symbol — destroying coherent cancellation.

**Path to 80%+:** Sub-Hz carrier frequency estimation (e.g., fine-grained DFT over [freq−6.25, freq+6.25] Hz in 0.1 Hz steps) followed by PCM-domain CP-FSK waveform synthesis and subtraction. This approach reconstructs the STFT from the residual, properly removing FFT-window sidelobes. Scheduled as a future change (p16-pcm-iterative-subtraction or similar).

**Parity definition:** 69.1% is the best achievable "parity" with the spectrogram-domain approach. True WSJT-X parity (≥85%) requires PCM-domain subtraction.

## Open Questions

- **AC-IS-1 target not met:** The 80% threshold requires QA agreement to accept 69.1% or approve a follow-up change for PCM-domain subtraction. This is the primary open item for the PR review.
- The macOS dylib must be rebuilt via CI (see tasks.md 4.5).
