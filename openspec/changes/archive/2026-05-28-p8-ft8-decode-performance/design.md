## Context

The FT8 decode pipeline in `Ft8Decoder.DecodeAsync` processes one 15-second PCM window per call using a hybrid FFT + Goertzel strategy: a pre-computed spectrogram is scanned for Costas sync patterns (cheap), and confirmed candidates are re-evaluated with exact-frequency Goertzel (expensive). In practice on a live band with 20+ concurrent transmissions, the FFT-based Costas scan produces ~4,235 candidates per cycle. Nearly all are noise false positives. Each candidate triggers a full `SymbolExtractor.Extract` call (79 symbols × 15 tones × 1,920-sample Goertzel) — ~2.3M operations — making the decode take ~59 seconds on a single thread. The 15-second cycle budget requires the decode to complete in under ~13 seconds (leaving ~2 seconds headroom for framing and delivery).

## Goals / Non-Goals

**Goals:**
- Reduce decode wall time to under 13 seconds on a single modern CPU core, measured end-to-end on a synthetic multi-signal fixture
- Reduce Costas false-positive candidates to O(actual signals × time positions with plausible alignment) — target under 300 per cycle on a busy band
- Add a CI performance regression test that fails if decode time exceeds a defined budget
- Preserve decode quality: all currently decoded messages must continue to decode correctly

**Non-Goals:**
- SIMD / AVX vectorisation of Goertzel (may come later; not required to meet the budget)
- GPU offload
- Changes to the FT8 protocol interpretation, message unpacking, or UI
- Reducing the time-sweep resolution below the current half-symbol step (that would re-open D11)

## Decisions

### Decision 1 — Primary fix: Costas candidate cap per time position

**Choice**: After `FindCandidates` returns for a given (time, freq) grid, retain only the top-N candidates by score rather than all candidates above the threshold. A cap of **2 per (time, baseHz) pair** is sufficient — a real signal produces at most one strong hit; the second slot handles partial-overlap edge cases.

**Rationale**: The threshold alone is insufficient on a live band because noise energy is elevated uniformly across all bins. The cap is frequency-agnostic and robust to noise floor variation. With ~103 time positions × 59 freq steps = 6,077 sweep pairs × 2 candidates = 12,154 cap, but in practice only positions near real signals score above 0.45, so the effective count will be far lower.

**Alternative considered**: Raising the Costas threshold to 0.6 or higher. Rejected as the primary fix because it risks losing weak signals at marginal SNR — the LDPC decoder can decode signals at −20 dB SNR, and their Costas scores may legitimately fall between 0.45 and 0.6 depending on noise conditions.

**Alternative considered**: A global candidate cap (top-K across all positions). Rejected because it creates a non-monotonic dependency on band activity; a quiet band would silently reduce coverage.

### Decision 2 — Secondary fix: Parallel time sweep

**Choice**: Replace the sequential `for (startSample...)` loop in `DecodeAsync` with `Parallel.For`, each iteration operating on its own per-iteration spectrogram buffer (allocated inside the lambda, not shared).

**Rationale**: The 103 time positions are fully independent — no shared mutable state except the pre-allocated `_spectrogram` field, which must be removed. Each parallel iteration allocates a local `float[79, 1024]` buffer (~316 KB). On a quad-core machine this gives a ~4× wall-time reduction before the candidate cap is applied; combined, decode time should be well under 5 seconds.

**Thread safety**: The existing `_spectrogram` field is a pre-allocation optimisation to avoid LOH pressure. With parallelism, each thread needs its own buffer. Options: (a) allocate per-iteration (simple, ~316 KB × thread count, short-lived), (b) use `ArrayPool<float>` with a 2D adaptor (lower GC pressure, more complex). Choose option (a) for simplicity; revisit if GC pressure is observed.

**Alternative considered**: `Task.WhenAll` with manual partitioning. Rejected in favour of `Parallel.For` which handles partitioning, thread pool management, and cancellation propagation automatically.

### Decision 3 — Tertiary fix: Goertzel coefficient caching in `Extract`

**Choice**: Precompute the 15 Goertzel coefficients (one per tone column) once at the start of `SymbolExtractor.Extract`, and pass each coefficient directly to the inner loop rather than recomputing `MathF.Cos` 1,185 times.

**Rationale**: `MathF.Cos` is a hardware intrinsic but still costs ~5–20 ns. 1,185 calls per `Extract` × 4,235 calls per cycle = 5.0M trig evaluations, saved entirely. The fix is two lines of code and zero risk.

### Decision 4 — Performance regression test using multi-signal synthetic fixture

**Choice**: Add `DecodeAsync_MultiSignal_CompletesWithinBudget` to `Ft8DecoderFixtureTests`. It synthesises **8 simultaneous FT8 signals** at distinct frequencies using `TestFt8Encoder`, superimposes them into a single PCM buffer with additive noise, and asserts that `DecodeAsync` completes in under **10,000 ms** and returns at least 6 of the 8 known messages.

**Rationale**: A single-signal fixture cannot expose the candidate explosion. Eight signals with noise approximates a moderately busy band. The 10-second budget is conservative (target is under 5 s after fixes); it provides a safety margin for CI runner variance while still catching regressions.

**Note on test placement**: The test will be marked `[Trait("Category", "Performance")]` so it can be excluded from the fast unit-test run if needed, while remaining part of the default CI suite.

## Risks / Trade-offs

- **Candidate cap may miss weak signals at unusual time offsets** → The cap of 2 per (time, baseHz) pair is generous; a signal present at a given time position produces exactly one strong Costas hit. The second slot is headroom. If a real edge case is found post-release, the cap can be raised to 3 or 4 without changing the architecture.
- **Parallel.For introduces non-deterministic decode order** → De-duplication by message string is already in place. Order of `DecodeResult` entries in the output list may vary between runs. The downstream `DecodeEventBus.Publish` does not depend on order. Acceptable.
- **Per-iteration spectrogram allocation (~316 KB × thread count)** → On a quad-core machine: 4 × 316 KB = 1.26 MB short-lived LOH allocations per cycle. With GC running at 4 Hz (once per cycle), this is ~5 MB/s LOH churn. Acceptable. If profiling reveals GC as a bottleneck, switch to `ArrayPool`.
- **Test flakiness on slow CI runners** → The 10,000 ms budget is 2× the expected post-fix time. If a CI runner is unusually slow, the test may fail spuriously. Mitigation: mark as `[Trait("Category", "Performance")]` so it can be re-run in isolation without the full suite.

## Migration Plan

No configuration changes, no API changes, no data migration. The changes are internal to `Ft8Decoder` and `SymbolExtractor`. A clean build and test run are sufficient to validate.

## Open Questions

- **Optimal candidate cap value**: 2 is proposed based on theoretical analysis. If live testing shows missed decodes at marginal SNR, raise to 3. The value should be a named constant (`MaxCandidatesPerSweep`) to make future tuning explicit.
- **Whether `Parallel.For` degree-of-parallelism should be capped**: On a machine running other services, unbounded parallelism may cause resource contention. Consider `new ParallelOptions { MaxDegreeOfParallelism = Environment.ProcessorCount / 2 }` or leave uncapped and rely on the thread pool scheduler. Decision deferred to implementation.
