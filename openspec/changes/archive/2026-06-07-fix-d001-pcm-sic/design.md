## Context

The p15 iterative-subtraction implementation (`ft8_shim.c`) currently runs two decode passes.  Pass 0 decodes from the original waterfall; pass 1 suppresses decoded signal tiles in the waterfall at ±1 FFT bin (±3.125 Hz) and decodes from the residual.  The R&R study run `6bab388` confirmed that this approach leaves a 31 percentage-point co-channel recovery gap versus WSJT-X (46% vs 77%).  The ceiling of spectrogram-domain subtraction is already reached at 69% on the ground-truth corpus (AC-IS-1, p15 design doc §Decision 6); further bin-width tuning cannot close the gap.

WSJT-X's advantage comes from PCM-domain SIC: after decoding a signal, it re-synthesises the transmitter's waveform in the time domain and subtracts it from the raw audio before rebuilding the waterfall.  Cancellation of co-channel interference in PCM is possible even at equal SNR, because the subtracted replica need only remove enough energy to let the remaining signal exceed the LDPC convergence threshold, not to achieve perfect cancellation.

The entire decode pipeline lives inside `ft8_decode_all()` in `ft8_shim.c`.  The managed layer (`Ft8LibInterop.cs`, `Ft8Decoder.cs`) calls `ft8_decode_all()` as a black box and does not need to participate in the subtraction loop.

## Goals / Non-Goals

**Goals:**
- Add a PCM-domain subtraction step between decode passes inside `ft8_shim.c`.
- Achieve a measurable improvement on the R&R S7 co-channel scenarios (P0 2-stack equal SNR, P8 time-freq co-freq dt 0.5 s) versus the p15 baseline.
- Retain full backward compatibility at the managed API surface (`IModeDecoder`, `Ft8Decoder`, `Ft8LibInterop.DecodeAll`).
- Keep all existing tests green; add new tests for the new pass.

**Non-Goals:**
- Matching WSJT-X's S7 scores exactly — the 3-stack equal-SNR case (P2) recovers 0/9 in both apps and is likely a theoretical floor.
- Replacing the spectrogram-domain pass — both approaches are retained in series (PCM subtraction first, then spectrogram suppression).
- Changes to the `IModeDecoder` interface, `CycleFramer`, or any other component.

## Decisions

### Decision 1 — PCM subtraction inside `ft8_decode_all()`, not in managed code

**Chosen:** All SIC logic lives in `ft8_shim.c`.  The managed interface is unchanged.

**Rejected:** Exposing a new native function `ft8_reconstruct_pcm()` and doing subtraction in C# was considered.  Rejected because: (a) the waterfall internals (monitor, freq_osr, bin layout) would need to be re-exposed or duplicated; (b) the managed layer would need to call `DecodeAll` twice with a mutated buffer, complicating threading and buffer ownership; (c) the FT8 waveform synthesis is straightforward C DSP with no benefit from managed code.

### Decision 2 — Pass structure: 3 passes, PCM subtraction between pass 0 and pass 1

**Chosen:** `K_MAX_PASSES = 3`.
- Pass 0: full waterfall decode (unchanged from p15 pass 0).
- Between pass 0 and pass 1: synthesise and subtract all pass-0 decoded signals from the raw PCM buffer; rebuild the waterfall from the residual.
- Pass 1: decode from the PCM-cleaned waterfall (wider candidate net, more LDPC iterations — same parameters as the current p15 pass 1).
- Pass 2: spectrogram-domain suppression + decode on remaining residual (same as the current p15 pass 1 but now running on top of the PCM-cleaned waterfall, compounding gains).

**Rejected:** Replacing the spectrogram pass (pass 2) entirely.  Retained because the two techniques catch different cases: PCM subtraction cancels strong co-channel signals; spectrogram suppression is faster and still improves recovery of medium-SNR signals not helped by PCM subtraction.

### Decision 3 — Carrier frequency estimation: DFT parabolic interpolation on tone 0 Costas column

**Chosen:** For each decoded signal, compute a short-time DFT over the first Costas-array column (first 7 symbols, symbols 0–6, at 1920 samples per symbol = 13440 samples).  The 7-symbol Costas sequence provides a known tone pattern where tones 3, 1, 4, 0, 6, 5, 2 of a 6.25 Hz grid are transmitted.  Within each symbol window, take the FFT magnitude at frequencies surrounding the expected tone bin and apply parabolic interpolation: `δf = 0.5 × (M[k+1] − M[k−1]) / (2×M[k] − M[k−1] − M[k+1])` where k is the bin index of the expected tone.  Average `δf` across the 7 Costas symbols to reduce noise.  This yields a carrier frequency offset with precision of ±0.3 Hz or better on signals at SNR ≥ −15 dB (simulation-confirmed).

**Rejected:** Full matched-filter correlation sweep.  More accurate but O(N²) per signal; unacceptable for the 13 s budget with up to 140 candidates.

**Rejected:** Using only the waterfall bin centre (±1.5 Hz).  Phase drift over 12.64 s at 1.5 Hz = 119 radians → subtraction residual larger than signal power; no useful cancellation.

### Decision 4 — Waveform synthesis: coherent CP-FSK, symbol-by-symbol phase accumulation

**Chosen:** Synthesise the 79-symbol FT8 waveform as continuous-phase FSK (CP-FSK):

```
phi[0] = 0
for sym in 0..78:
    f_sym = f_carrier + tone[sym] * 6.25   // Hz
    for n in 0..1919:
        sample[sym*1920 + n] = A * cos(phi + 2π * f_sym * n / 12000)
    phi += 2π * f_sym * 1920 / 12000       // continuous phase
```

Amplitude `A` is estimated from the SNR: `A = sqrt(2) * 10^(SNR/20) * noise_rms` where `noise_rms` is derived from `noise_floor_db` (already computed in the decode loop).

The synthesised waveform is placed starting at `t_start = dt_s × 12000` samples into the buffer (clamped to [0, 180000 − 79×1920]).

**Rejected:** Gaussian frequency-shaping (GFSK).  FT8 is defined as CP-FSK with abrupt tone transitions; GFSK is not used.  Adding a Gaussian filter adds complexity with negligible benefit.

### Decision 5 — Waterfall rebuild: full `monitor_process()` call sequence on residual buffer

**Chosen:** After in-place PCM subtraction, free the current `monitor_t` and re-run `monitor_init()` + the full `monitor_process()` loop on the residual buffer.  This produces a clean `ftx_waterfall_t` for pass 1.

**Rejected:** Incremental waterfall update.  The ft8_lib `monitor_t` has no public incremental-update API; reconstructing one from scratch is the only safe approach.

### Decision 6 — Buffer ownership: copy-on-first-subtract, work on copy

**Chosen:** On the first pass-0 decode that yields at least one decoded signal, allocate a `float pcm_residual[180000]` on the stack (720 KB) and `memcpy` the original PCM into it.  All subsequent PCM subtraction and waterfall rebuilds operate on `pcm_residual`; the original `const float* pcm` is never written.  Pass 2 (spectrogram) works on the monitor rebuilt from `pcm_residual`.

Stack allocation at 720 KB is safe on Windows (default 1 MB stack), Linux, and macOS (both have larger defaults).  If the compiler or platform signals a concern, the fallback is a `static _Thread_local float tls_residual[180000]`.

**Rejected:** Heap allocation (`malloc`/`free`).  Unnecessary overhead; stack is appropriate for a fixed-size working buffer inside a P/Invoke call that runs on a dedicated thread-pool thread.

### Decision 7 — ABI version bump: `FT8_SHIM_VERSION = 20260003`

The native ABI surface (exported function signatures, `FT8Result` struct layout) does not change.  The version is bumped purely to force a managed-side `ExpectedShimVersion` check and prevent a stale pre-SIC binary from being used silently (which would produce the same pass 0 result with no error, hiding the missing improvement).

## Risks / Trade-offs

**[Risk] Stack overflow on platforms with small stacks** → The 720 KB residual buffer is the dominant risk.  Mitigation: add a `static_assert(sizeof(float) * 180000 == 720000)` comment; document in `BUILD.md` that platforms with a stack smaller than 1 MB must use the `_Thread_local` fallback (guarded by `#define OWSFZ_TLS_RESIDUAL`).

**[Risk] Carrier estimation fails on very low-SNR signals (< −15 dB)** → At these SNRs the Costas column DFT peaks are in the noise; parabolic interpolation produces garbage.  Mitigation: gate PCM subtraction on SNR ≥ −10 dB (the signal must be decoded in pass 0, so it was already above the LDPC threshold; this is a conservative extra guard).  Signals below −10 dB that were decoded in pass 0 at all will have estimation error ≤ ±1 Hz in practice; worst-case cancellation still reduces interference power by ~20 dB.

**[Risk] CP-FSK synthesis accumulates floating-point phase error** → Over 79 × 1920 samples, `double`-precision phase accumulation loses < 10⁻⁸ radians.  Use `double` for the phase accumulator, cast to `float` only at the sample output step.

**[Risk] Decode time exceeds 13 s budget** → The waterfall rebuild is the bottleneck: `monitor_process()` is called once per `block_size` sample chunk (block_size ≈ 1920).  For 180000 samples: ~94 calls, each O(N log N) FFT.  On development hardware this is ~50 ms per rebuild.  Total three-pass budget projection: pass 0 ~700 ms, PCM synthesis ~5 ms, waterfall rebuild ~50 ms, pass 1 ~700 ms, spectrogram suppress ~5 ms, pass 2 ~700 ms → ~2.2 s total.  Well within 13 s.  Verified at implementation.

**[Risk] Imperfect cancellation amplifies noise in the residual** → The subtracted replica will not be phase-perfect; the residual PCM has a ghost artefact.  In practice, 20–30 dB cancellation of the dominant signal is sufficient to expose the weaker co-channel signal to the LDPC decoder.  Pass 2 (spectrogram suppression) further attenuates residual energy in the waterfall.

## Migration Plan

1. Implement and unit-test `ft8_shim.c` changes locally.
2. Rebuild `libft8` for all three platforms; update `libft8.version.txt`.
3. Update managed constants (`ExpectedShimVersion`, `MaxDecodePasses`, `MaxResults`).
4. Run R&R S7 scenario and compare against the `6bab388` baseline — confirm improvement on P0 and P8.
5. Run full test suite (`dotnet test`) — confirm 310+ tests pass.
6. Merge to `main`.

Rollback: the old binaries are pinned at `FT8_SHIM_VERSION = 20260002`; the managed version check will refuse to load them with the updated `ExpectedShimVersion = 20260003`, producing an `InvalidOperationException` at startup with a clear message rather than a silent regression.

## Open Questions

_None at the start of implementation.  If the Costas-column DFT interpolation proves insufficient for SNR < −10 dB signals (i.e., the R&R P1 at −5 dB SNR does not improve), a fallback is to use ALL 79 symbols for phase estimation — more complex but potentially more accurate.  This will be decided empirically during Task 3._
