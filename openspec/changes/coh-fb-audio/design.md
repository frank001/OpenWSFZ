## Decisions

**D1. The default is `Both`.** The Captain's pick (2026-10-28, after B2 and `FBAUDIO`). The Architect recommended it; the PC margin to the 13 s limit
(8,238 ms) is wide. On `sol` it is 724 ms (descriptive; `Residual` alone was not measured there), which is why D3 is a merge condition.

**D2. `Both` is sequential, residual first.** Each run already uses `workers` threads; a parallel pair would double them for no wall time the budget needs, and
a deadline between two sequential runs is a plain countable event. The residual runs first because it is the run that matters when the budget is short. With
no usable residual buffer the original audio runs once, never twice. On a payload found by both runs the **residual row is kept** (its SNR and DT are
measured with the neighbours removed).

**D3. One shared budget, with a guard that exists (`9ef703d0`).** `budgetMs` is the time left when the fallback starts, less the publish reserve. The second
run gets `leftMs = budgetMs − elapsed since the fallback start`. If `leftMs <= 0` it is not started and its eligible candidates count as abandoned
(`Ft8Decoder.cs:1049-1061`). Inside a run a worker claims no candidate once the run's wall clock is past its `budgetMs` (`CohFallbackParallelRunner.cs:65`).
**N-1 tests this; it adds no code.** Line numbers are from `9ef703d0`: record any drift on the branch tip (task 1.1).

**D4. Why the guard matters in practice.** On `sol` the late fallback cycles start late (maximum start 10,424 ms) because the earlier passes spend the time; the
fallback's own wall time is at most 2,419 ms (FBAUDIO, counts from the daemon log). The guard is what bounds a slower machine.

**D5. The key replaces the probe's environment switch.** `OPENWSFZ_COHFB_AUDIO` and `CohFallbackAudio.IsActive` are removed in `9ef703d0`; the key is the only control.

**D6. Config API.** `POST` of the config is an overlay on `main` (HK-035): a test must show that a partial post leaves `decoder.coherentFallbackAudio` as it was.

## Risks

- A fallback that ends late on a slow machine. Mitigation: D3, N-1, and the 13 s limit unchanged.
- A shipped or example config that writes the key with an old value. Mitigation: none shipped writes it today; any that does SHALL write `Both` (task 3.2).
- A new live era. Mitigation: stated in the proposal; the daemon's start time stamps it.
