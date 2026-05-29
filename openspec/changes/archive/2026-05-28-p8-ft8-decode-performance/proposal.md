## Why

The FT8 decode pipeline takes ~59 seconds per 15-second cycle on a live band, causing 3–4 consecutive cycles to be dropped and the operator to receive results roughly once per minute instead of every 15 seconds. Root cause: the FFT-based Costas candidate scan produces ~4,235 false-positive candidates per cycle on a real band (26× above expected), each triggering an expensive Goertzel call. Nearly all candidates are noise (avg initial parity failures ≈ 41/83 ≈ random), yet the decoder runs full Goertzel extraction and 50-iteration LDPC on every one of them. This is a blocking usability defect — decodes are happening, but far too infrequently to be useful.

## What Changes

- **Candidate pre-filter**: Add an energy threshold or candidate cap that discards low-quality FFT Costas hits before committing to a Goertzel call. This is the primary lever — reducing candidates from ~4,235 to ~200 reduces Goertzel work by ~21× and brings decode time within the 15-second budget.
- **Parallel time sweep**: Run the 103 time-domain start positions concurrently using `Parallel.ForEach` or `Task.WhenAll`. Independent per-position; no shared mutable state aside from the pre-allocated spectrogram buffer (which must be made per-thread or replaced with pooled buffers).
- **Goertzel coefficient caching**: Precompute the 15 Goertzel coefficients once per `Extract` call instead of recomputing `MathF.Cos` 1,185 times per call.
- **Decode elapsed time logging**: Add wall-clock elapsed milliseconds to the existing cycle diagnostic log line so performance regressions are visible in the operator log without instrumentation.
- **Performance regression test**: Add a CI test that runs `DecodeAsync` on a known-busy synthetic PCM fixture (multiple simultaneous signals) and asserts completion within a time budget, preventing silent regressions.

## Capabilities

### New Capabilities

- `ft8-decoder`: FT8 decode pipeline requirements — cycle throughput, latency budget, candidate handling, and decode quality guarantees. Covers both the existing decode correctness requirements (previously untested at spec level) and the new performance requirements introduced by this change.

### Modified Capabilities

*(none — no existing spec covers the FT8 decode pipeline)*

## Impact

- `src/OpenWSFZ.Ft8/Dsp/SymbolExtractor.cs` — `Extract` method (coefficient caching); `FillSpectrogram` (thread-safety for parallel time sweep)
- `src/OpenWSFZ.Ft8/Dsp/CostasSynchroniser.cs` — candidate filtering or threshold change
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — parallelised time sweep, elapsed logging
- `tests/OpenWSFZ.Ft8.Tests/Ft8DecoderFixtureTests.cs` — new performance regression test
- No changes to API, configuration schema, or web frontend
