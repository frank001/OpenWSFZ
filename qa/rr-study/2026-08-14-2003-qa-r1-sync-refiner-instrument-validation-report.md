# QA → Architect report: r1-sync-refiner-instrument-validation

**Date (UTC):** 2026-08-14 20:03 (`date -u`)
**Change:** `r1-sync-refiner-instrument-validation`
**Branch:** `feat/r1-sync-refiner-instrument-validation` (not pushed, not merged — HK-014/HK-010/HK-006)
**Session role:** Developer session via `/opsx:apply` (HK-011 flow)

## 1. Outcome, up front

**AC-1 PASS · AC-2 PASS · AC-3 FAIL (frequency sub-check PASS, time sub-check FAIL) · AC-4 FAIL (marginal) · AC-5 PASS · AC-6 measured, not gated, no escalation.**

Per the spec's four outcome branches (task 6.2): **AC-3 FAILED, so R2 (wiring refinement into the decode path) must NOT be proposed until this is resolved.** This is escalated to the Captain per design.md D5 — the AC-3 time-dimension finding is real and reproducible but its root mechanism was not fully identified in this session (see §5). AC-1/AC-2/AC-4 are implementation findings, not D-001 findings, per HK-021(k) — none of the six ACs measure recovery or false-positive rate; that is R2's concern entirely and was never touched here.

Two genuine, deep implementation defects were found and fixed during this session (§3) before AC-1/AC-2 could pass at all. A third, real, reproducible finding in AC-3 was diagnosed extensively but not resolved (§5) — reported honestly rather than forced to a false PASS or silently narrowed.

## 2. New DLL SHA256s and shim version

- **`FT8_SHIM_VERSION` = 20260040** (bumped from R0's 20260039; `ft8_shim.h` and `Ft8LibInterop.ExpectedShimVersion`).
- **Windows x64** (`rebuild_shim.bat`, MSVC 19.44.35223): SHA256
  `fe0b7d534e06fd4d1f79575739af650f78a524861cb195178a1c1c9036139cdc`
- **Linux x64** (`build_linux.sh`, GCC 14.2.0 via WSL2 Debian): SHA256
  `61eef0945bd6b7bc85a9579411677e425b4008db5de24d5e790e64b14292fa07`
- **macOS ARM64**: NOT rebuilt this session — no Mac available locally, the identical limitation R0 recorded. Requires the one-shot `workflow_dispatch` GitHub Actions path (R0's tasks.md 2.1–2.7 pattern). Honestly flagged, not silently skipped.
- `dumpbin /exports` (Windows) and `nm -D` (Linux) both confirm all twelve exported symbols present, including the new `ft8_refine_candidate`, with the eleven pre-existing symbols' presence otherwise unaffected.
- Full build/debug/fix history recorded in `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`'s new top entry and in `native/ft8_lib_vendor/refine/sync_refiner.c`'s doc comments.

## 3. Two implementation defects found and fixed (task 1.1–1.4, 4.2 "fix and re-run")

Both were diagnosed empirically (temporary `getenv`-gated `fprintf` instrumentation, since fully removed from the shipped source) and cross-verified with an independent Python re-implementation and idealised noiseless toy signals — never asserted from re-reading the code, per the sign-error mitigation discipline design.md names for a sibling defect class.

**Defect 1 — cross-block complex summing was invalid.** The initial implementation summed complex correlations across all 21 Costas symbols (all three sync blocks) using one continuous absolute-time phase reference. FT8 is genuine continuous-phase FSK (CPFSK): the transmitter's phase at sync block 1 (symbol 36) and block 2 (symbol 72) carries the accumulated phase of the ~29 data symbols between blocks — message-dependent and unknown at this diagnostic stage. **Fix:** coherent (complex) summing retained *within* each 7-symbol block; the three blocks' magnitudes combined non-coherently (summed as magnitudes) across blocks.

**Defect 2 (the dominant one) — the within-block reference itself didn't track true continuous phase.** Even with defect 1 fixed, a clean noiseless synthetic signal at exact truth still measured `Δf = −1.0 Hz`, `Δt = +21 ms` — smooth, sharp, and completely wrong. Root cause: the per-symbol reference phase `2·π·ref_hz·idx/fs2` implicitly assumes each symbol's own tone had been running since sample 0, when the real CPFSK signal's phase at symbol *j* carries the accumulated phase of the block's own preceding tones (0..j−1) — a known, computable quantity for Costas symbols, but never computed by the old per-symbol-independent formula. **Fix:** a running phase accumulator integrates each symbol's own `2·π·ref_hz/fs2` step continuously across the block (matching `qa/rr-study/synth/modulator.py`'s own cumsum-inclusive phase convention). Verified against four independent clean `(freq, dt)` test points: all converge to `Δf = 0.0000 Hz`, `Δt = 0.5 ms` (Stage C's discretisation floor).

**A third defect (sequential-search coupling)** surfaced once the population itself was run: RMS(Δf) was excellent (<0.1 Hz) for `|true Δf| ≤ 0.4 Hz` but jumped to several Hz for `|true Δf| ≥ 0.8 Hz`. Cause: the original design did coarse **time** search at `Δf = 0` fixed, *then* frequency search at that time fixed (matching the spec's literal stage-order wording) — an implicit assumption that breaks when the true frequency offset is not near zero, since Stage A's own scoring is itself frequency-mismatched. **Fix:** Stage A+B became a **joint** 2-D grid search (25 time × 11 freq = 275 evaluations, still cheap) — still "coarse time → frequency" before the fine-time stage, per design.md D3's latitude on search-parameter mechanics, just evaluated jointly rather than sequentially. Verified across the full `{0, ±0.4, ±0.8, ±1.2, ±1.5} Hz` grid: all errors now within ±0.2 Hz / ±2 ms.

All three corrections are documented in full in `native/ft8_lib_vendor/refine/sync_refiner.c`'s doc comments (`costas_coherent_sum`'s header, and the Stage A+B joint-search header).

## 4. AC-1 / AC-2 (RMS accuracy / systematic bias)

| | measured | bar | verdict |
|---|---|---|---|
| RMS(Δf), SNR ≥ −10 dB | 0.1430 Hz | ≤ 0.30 Hz | **PASS** |
| RMS(Δt), SNR ≥ −10 dB | 1.135 ms | ≤ 7.7 ms | **PASS** |
| mean(Δf error) | −0.0019 Hz | ≤ 0.10 Hz | **PASS** |
| mean(Δt error) | +0.429 ms | ≤ 2.0 ms | **PASS** |

n = 1,600 (4 SNR strata × 2 offset classes × 200) for the SNR ≥ −10 dB subset. No sign-error signature (mean error is small relative to RMS in both dimensions — the specific defect class named in advance in design.md's Risks section was checked for and not found in the final build).

## 5. AC-3 (noise-only null) — FAIL, escalated per D5

n = 1,200 pure-noise trials, coarse positions drawn across a broad band (300–2700 Hz, 0.1–1.0 s).

**Test correction made during evaluation (HK-021(k), recorded per HK-025's discipline):** the harness's first AC-3 pass used a Kolmogorov–Smirnov test against a *continuous* uniform null. That is the wrong instrument for `ft8_refine_candidate`'s actual output, which is drawn from an explicit *discrete* search grid (11 frequency values; a combination of a 25-point coarse-time grid and a 41-point fine-time grid). At n=1,200 a KS test against a continuous null rejects *any* discretised distribution purely from the discreteness itself, regardless of fairness — this is a mismatch between the metric and what the gate names, not evidence about the refiner. Replaced with:
- **Frequency:** chi-squared goodness-of-fit against the 11 discrete grid categories directly.
- **Time:** chi-squared goodness-of-fit against the theoretical **convolution** of the two search grids' PMFs (computed mechanically, not asserted — the sum of two uniforms is trapezoidal, not flat, so a flat-uniform null is *also* the wrong instrument here even for a hypothetically perfect refiner).

| | statistic | p-value | verdict |
|---|---|---|---|
| Frequency (11 categories) | χ² | **0.9420** | **PASS** |
| Time (14 bins, convolution null) | χ² | **0.0000** | **FAIL** |

Frequency counts (11 grid points, −2.5…+2.5 Hz): `[117, 116, 105, 106, 99, 100, 109, 114, 107, 108, 119]` — close to the expected ~109/bin, unremarkable.

Time counts (14 bins, −0.07…+0.07 s) vs. the convolution-null expectation: bin 0 (most negative, near −0.07 s) shows **102 observed vs. 32.8 expected**; bin 13 (most positive, near +0.07 s) shows **6 observed vs. 32.8 expected**. A strong, real, directional asymmetry — not an edge-discreteness artefact (the null already accounts for the trapezoidal shape).

**Diagnostic trail (extensive, all findings below are measured, not asserted):**
- `costas_coherent_sum`'s own math is unbiased: fed a constant-DC synthetic signal over a large buffer (no truncation possible), the score curve is perfectly flat across the full ±20-sample search range.
- An independent Python re-implementation of the entire pipeline (`downconvert_decimate` + `costas_coherent_sum` + the Stage A+B/C search), run outside the C code entirely, **reproduces the identical bias** — ruling out a C-specific bug.
- The bias **disappears** when Stage C is fed a *fixed/forced* (non-selected) time or frequency offset instead of the value `argmax`-selected by Stage A+B on the same noise. It reappears (reproducibly, ~90%+ of trials in one 20-trial sample at a single fixed coarse position across 20 independent noise realisations) only when Stage C's `base_origin2`/`refined_carrier` are built from the Stage A+B `argmax` selection.
- `best_dt_samp` and `best_df` (Stage A+B's own selections) each look individually close to uniform across many independent trials at different positions.

**Conclusion:** this is a real, reproducible **selection-bias / "double-dipping" interaction** between Stage A+B's noise-optimised `(best_dt_samp, best_df)` pair and Stage C's own re-derivation and search on the *same* underlying noise realisation — not a simple sign or indexing defect, and not present in the correlator's own math in isolation. The exact mechanism was not identified within this session's time budget. Per design.md D5, **this is escalated rather than iterated on further locally**: *"An AC-3 FAIL SHALL NOT be treated merely as an implementation defect to fix and re-run locally... SHALL be escalated for explicit resolution before any proposal to wire refinement into the decode path is written."*

The full empirical trail (including the constant-DC control, the independent Python replica, and the fixed-vs-selected comparison) is preserved in this report and in `sync_refiner.c`'s "KNOWN UNRESOLVED FINDING" comment ahead of Stage C, so a follow-up session does not have to re-derive any of it.

## 6. AC-4 (SNR monotonicity) — FAIL (marginal)

| SNR (dB) | n | RMS(Δf) Hz | RMS(Δt) ms |
|---|---|---|---|
| −20 | 400 | 0.1442 | 1.515 |
| −15 | 400 | 0.1416 | 1.237 |
| −10 | 400 | 0.1432 | 1.175 |
| −5 | 400 | 0.1428 | 1.116 |
| 0 | 400 | 0.1473 | 1.140 |
| +5 | 400 | 0.1386 | 1.109 |

Broken pairs (RMS increasing where the gate requires non-increasing): (−15→−10 dB, freq, +0.0016 Hz), (−5→0 dB, freq, +0.0045 Hz), (−5→0 dB, time, +0.024 ms). All three violations are tiny relative to the overall RMS scale (≤3% relative change) and are plausibly sampling noise at n=400/stratum rather than a genuine non-monotonicity — but AC-4 is a mechanical, strict gate (design.md: "SHALL NOT increase... at any point") and is reported as **FAIL** per its literal definition, not softened. This is an implementation/measurement finding, not a D-001 finding, per HK-021(k) — same disposition as AC-1/AC-2 would have been.

## 7. AC-5 (determinism) — PASS

Three independent process runs of the full harness (2,400 signal + 1,200 noise trials each) against the same population, byte-diffed pairwise. All three results files (`run_a.json`, `run_b.json`, `run_c.json`, committed under `qa/rr-study/r1-sync-refiner/results/2026-08-14/`) are **1,209,182 bytes, byte-identical**. Depends on R0's `p23_common.py` sort-at-construction determinism fix (already landed) — this harness's own `population.py` independently avoids the same hash-randomised-set-iteration pitfall by construction (all strata are tuples walked in fixed order; the only randomness is a single seeded `np.random.default_rng` consumed in a fixed sequence). Wall-clock timing is deliberately excluded from the byte-diffed files (a separate `.timing.json` sidecar) specifically so non-deterministic scheduler jitter could never cause a spurious AC-5 FAIL.

## 8. AC-6 (cost) — measured, not gated

Mean measured wall-clock cost: **21.5 ms/candidate** (3,600 calls across signal + noise populations). Projected full-corpus runtime (2,529-cycle reference corpus, per design.md's own Trade-off note):

| candidates/cycle | projected full-corpus time |
|---|---|
| 100 (illustrative lower estimate) | 1.51 h |
| 340 (K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2, worst-case upper bound) | 5.14 h |

Both comfortably under the ~8 h escalation threshold — **no escalation triggered**. This figure does not gate PASS/FAIL per the spec.

## 9. Per-cell power (task 3.3)

All 12 signal-population cells (6 SNR strata × {grid, random} offset class) report exactly **n = 200** — the pre-registered floor, met everywhere. **Zero underpowered cells.** AC-3's noise population is n = 1,200 (a single pool, 6× the 200 floor).

## 10. Production-decode-equality replay (task 5.3)

`r0_ac1_ac2_replay.py` + `r0_ac1_ac2_diff.py`, 250 contiguous cycles, pinned 20 m corpus (`260808_004000`..`260808_014215`, identical range to R0's own AC-1), comparing the pre-change `20260039` binary (extracted from git `HEAD`, SHA256 confirmed to match R0's own shipped pin `897f81dd…` exactly) against the final `20260040` binary: **`RESULT: PASS — zero differences across 250 cycles`**. The new diagnostic export did not alter production decode behaviour by a single byte.

## 11. .NET build/test (task 5.4)

`dotnet build src/OpenWSFZ.Ft8`: **0 Warning(s), 0 Error(s)**.
`dotnet test tests/OpenWSFZ.Ft8.Tests`: **309/309 passed**, 0 failed, 0 skipped (306 R0 baseline + 3 new `RefineCandidateTests`).

## 12. Decision (task 6.2)

**AC-3 FAILED. R2 (wiring the refiner into the decode path) MUST NOT be proposed until this is resolved.** AC-1/AC-2 pass cleanly and represent a real, hard-won correctness result (two deep architectural defects found and fixed, verified against both synthetic and the full pre-registered population). AC-4's violations are almost certainly measurement noise but are reported as a strict FAIL per the mechanical gate. AC-3's time-dimension failure is the blocking finding — it is real, reproducible, extensively diagnosed, but not yet root-caused, and per design.md D5 requires the Captain's explicit resolution path (not a local fix-and-retry) before this change can report an unconditional PASS or before R2 may be proposed.

## 13. Stop (task 6.3)

No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006). This report does not declare readiness for merge. The Captain reviews the diff and decides.

## Appendix: artefact locations

- Native source: `native/ft8_lib_vendor/refine/sync_refiner.c` (new, OpenWSFZ-original, diagnostic-only).
- Managed binding: `src/OpenWSFZ.Ft8/Interop/{Ft8LibInterop.cs, IFt8NativeInterop.cs, Ft8NativeInteropAdapter.cs}`.
- Validation harness: `qa/rr-study/r1-sync-refiner/{population.py, refiner_ctypes.py, run_harness.py, evaluate_acs.py}`.
- Raw results (byte-identical across 3 runs, per AC-5): `qa/rr-study/r1-sync-refiner/results/2026-08-14/{run_a,run_b,run_c}.json` + `.timing.json` sidecars + `ac_evaluation_report.json` + `production_equality_replay_20260040.json`.
- New tests: `tests/OpenWSFZ.Ft8.Tests/RefineCandidateTests.cs`.
- `openspec/changes/r1-sync-refiner-instrument-validation/tasks.md` — all tasks checked off with implementation notes.
