## 1. Requirements Registration

- [ ] 1.1 Add `FR-026` to `REQUIREMENTS.md`: *FT8 decode throughput — the decoder SHALL complete each 15-second cycle within 13 seconds of wall-clock time; no more than 2 Goertzel candidates SHALL be evaluated per (time-position, base-frequency) sweep pair*

## 2. Goertzel Coefficient Caching

- [ ] 2.1 In `SymbolExtractor.Extract`, compute an array of 15 Goertzel coefficients (`float[] coeffs = new float[GridWidth]`) before the symbol loop; replace the per-(sym,col) `MathF.Cos` call inside `GoertzelDetector.ComputeEnergy` with a pre-computed coefficient parameter
- [ ] 2.2 Update `GoertzelDetector.ComputeEnergy` to accept an optional pre-computed `coeff` parameter (keep the existing signature for callers that compute it on the fly); or add an overload `ComputeEnergyWithCoeff(ReadOnlySpan<float> samples, float coeff)`
- [ ] 2.3 Verify `dotnet build -c Release` exits 0 with no new warnings

## 3. Costas Candidate Cap

- [ ] 3.1 Add `private const int MaxCandidatesPerSweep = 2;` to `Ft8Decoder`
- [ ] 3.2 After `CostasSynchroniser.FindCandidates` returns in the frequency sweep loop, truncate the candidate list to `MaxCandidatesPerSweep` entries (candidates are already sorted by score descending — take the first N)
- [ ] 3.3 Verify `dotnet build -c Release` exits 0

## 4. Parallel Time Sweep

- [ ] 4.1 Remove the `private readonly float[,] _spectrogram` pre-allocated instance field from `Ft8Decoder`
- [ ] 4.2 Replace the sequential `for (int startSample = 0; ...)` loop with `Parallel.For(0, stepCount, new ParallelOptions { CancellationToken = ct }, i => { ... })` where each iteration allocates its own local `float[SymbolCount, SpecBins]` spectrogram buffer
- [ ] 4.3 Collect decode results from parallel iterations into a thread-safe structure (e.g. `ConcurrentBag<DecodeResult>`) and merge into the final list after the parallel loop; apply the existing `seen` de-duplication after merging
- [ ] 4.4 Verify cancellation: `OperationCanceledException` thrown inside the parallel body must propagate correctly through `Parallel.For` and out of `DecodeAsync`
- [ ] 4.5 Verify `dotnet build -c Release` exits 0

## 5. Elapsed Time Logging

- [ ] 5.1 Capture `var sw = Stopwatch.StartNew()` before the time sweep loop in `DecodeAsync`; stop it after the loop; include `elapsed={sw.ElapsedMilliseconds} ms` in the existing cycle diagnostic `LogInformation` call

## 6. Performance Regression Test

- [ ] 6.1 In `Ft8DecoderFixtureTests`, add `[Fact(DisplayName = "FR-026: DecodeAsync completes within 10 s on 8-signal fixture")]` test: use `TestFt8Encoder` to synthesise 8 FT8 signals at frequencies 500, 750, 1000, 1250, 1500, 1750, 2000, 2250 Hz; superimpose into one PCM buffer with additive Gaussian noise (σ = 0.001); assert method returns within 10,000 ms and result count ≥ 6
- [ ] 6.2 Mark the test with `[Trait("Category", "Performance")]` so it can be run in isolation with `--filter "Category=Performance"` if needed, while remaining part of the default `dotnet test` run

## 7. Build and Test Verification

- [ ] 7.1 Run `dotnet build -c Release` — 0 errors, 0 warnings
- [ ] 7.2 Run `dotnet test -c Release` — all existing tests green, new performance test passes within the time budget
- [ ] 7.3 Check the operator log on a live band: confirm `elapsed=` appears in cycle log lines and values are under 13,000 ms; confirm Costas candidate counts are below 500 per cycle
- [ ] 7.4 Confirm decode output rate: results should appear every 15 seconds (or at worst every 30 seconds on a very busy band), not once per minute
