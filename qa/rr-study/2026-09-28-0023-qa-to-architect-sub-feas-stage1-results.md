# SUB-FEAS: Stage 1 read — FAIL. The precondition does not hold on real signals

**QA, 2026-09-28 00:23Z** (`date -u`, HK-017). Branch `qa/sub-feas` (from `origin/main`, HK-032).
Spec `2026-09-27-1855-…-sub-feas-…md` + Amendments 1–3 (`arch/subtraction-feasibility` `b0dff3d2`,
all verified against the branch, not taken on trust). Harness `qa/rr-study/sub-feas/`. Full result:
`qa/rr-study/sub-feas/sub_feas_result.json` (NFR-021/HK-037 scanned clean, every file in this
delivery). **Stop after Stage 1, per spec sec.10 — Stage 2 is not run and is not authorised** (it
needs PASS/PARTIAL and the Captain's go; this read FAIL).

## Amendment 2/3 implementation, sanity-checked before trusting it

- **0g replaced** (split-half `τ0` stability, ±10ms) and **§4's fine-fit box widened to ±100ms** —
  implemented as specified.
- **0b drift term**: added `ḟ ∈ [-0.10,+0.10] Hz/s` (0.005 steps) to the template, coarse-to-fine
  search as specified (fit `(Δt,Δf)` at `ḟ=0` → search `ḟ` with `Δf` re-fit → refine `Δt` once).
  **Sanity-checked on a synthetic ground-truth signal before trusting it on real data**: recovers
  `ḟ=0.04` exactly (the true injected rate) and drops `X` from 5.24dB (plain fit, the old failure
  mode) to −0.31dB (drift-aware fit) at the same SNR that failed under Amendment 1's harness. L0
  (the June control) was left untouched — plain `r_fit`, no drift, single scalar — confirmed by
  inspection, not just by assertion.
- **Amendment 3 (runtime vs validity conflict, found before re-running)**: the drift search made
  L1/L2's fit ~2.25× more expensive (3.875 s/row, live-measured, vs 1.727 s/row plain), projecting
  ~5.4h — over §3's 3h bar. §3's own thinning rule would need k=3, which drops `|P_A|`≈635,
  `|P_B|`≈698, both under ROW 0d's 1,000 floor. Escalated rather than picked a side; ruled: thinning
  yields to 0d, run unthinned, parallelise if easy. **Parallelised `bigfit.fit_population` across
  cycles** (multiprocessing, 12 workers) — verified **byte-identical** to a serial run first
  (`qa/rr-study/sub-feas/_verify_parallel.py`; measured 4.9× speedup on a 40-row sample, 157.9s→32.3s).
  Real projected total came down to 2.11h, under 3h — k=1 applied for the ordinary reason, Amendment
  3's override never had to fire in practice, but the logic is there and disclosed either way.
- **One more implementation bug found and fixed** (disclosed, not smoothed over): the first Amendment
  2 re-run read `split_half_diff_ms=10.000000000000009` and FAILed against the `≤10.0` bar — a pure
  IEEE-754 rounding artefact (`-0.165 - (-0.165)`-class subtraction), not a real >10ms difference.
  Fixed with a documented `round(..., 6)` (the true values are multiples of 0.5ms from a 5ms search
  grid, so this only removes representation noise, not signal).

## ROW 0 table (this run, full population, unthinned)

| row | result | bar | verdict |
|---|---|---|---|
| 0a encoder fidelity | 296/296 tested (4 void, negative-DT, excluded) | ≥99% | **PASS** |
| 0b synthetic recovery (drift-extended) | none/drift/fade all PASS every SNR | ≤1.0/2.0dB | **PASS** |
| 0b′ (new) drift-invention guard | 135/135 = 100% \|ḟ\|≤0.005Hz/s on "none" | ≥90% | **PASS** |
| 0c noise floor | 400/400 | ≥95% | **PASS** |
| 0d population size | A=1,906 B=2,094 | ≥1,000 each | **PASS** |
| 0e DLL pin | sha256 match | equal | **PASS** |
| 0f RR73 form | 342/345 = 99.13% on-air-grid wins | ≥90% | **PASS** |
| 0g anchor (replaced) | τ0=−0.1600s, split-half diff=10.0ms, median Δf=−0.641Hz | ≤10ms and ∈[−1,+1] | **PASS** |
| 0h convergence (load-bearing) | 36/4,361 = 0.83% at a Δt/Δf/ḟ box edge | ≤2% | **PASS** |
| 0i twin sanity | twin share 94.75%, 0 double-twins | ≥90% and =0 | **PASS** |

**All of ROW 0 passes.** W* selected on split A (n=1,855 fitted): **0.32s** (the smallest family
member — finer envelope tracking always won).

## Stage 1 gate (split B, n=2,063 fitted rows, L2 at W*=0.32)

| statistic | value |
|---|---|
| median X | **8.75dB**, 95% CI [8.47, 9.10] (cycle-clustered bootstrap, 2,000 draws) |
| median D (suppression) | 19.25dB |
| **gate** | **FAIL** (`ci_hi`=9.10 > 6.0 — misses even the PARTIAL bar, not just PASS) |

**Controls** (paired, same cycle-clustered bootstrap):
- L0 − L2: median **19.12dB** [18.91, 19.25] — the fitted+enveloped method beats the naïve
  lattice-snapped single-scalar control (June's own model) by a wide, tightly-bounded margin.
- L1 − L2: median **10.33dB** [10.07, 10.68] — time-varying envelope tracking (W*) beats a single
  scalar gain AT THE SAME fitted position by a similarly wide margin.
- C-FLAG: L0 alone's own median X is 27.03dB, CI [26.63, 27.41] — nowhere near the 3.0dB PASS bar,
  so **C-FLAG does not fire**. June's 2026 failure was genuinely a modelling problem (§7's own
  disclosed check), and this arm's improvement over it is real, not a re-run of the same null.

## Reading this result

The method **works, substantially** — going from L0 (~27dB residual) to L2 (~8.75dB) is roughly
19dB of real, disclosed engineering progress: data-aided positioning plus a time-varying envelope
recovers most of a decoded signal's true waveform. **It does not work enough.** The pre-registered
bar (`ci_hi ≤ 3.0dB` and `median D ≥ 10.0dB` for PASS, `ci_hi ≤ 6.0dB` for PARTIAL) asks for the
residual to sit at or below the noise floor, so a masked neighbour would see it as ≤3dB above
nothing. At 8.75dB (CI floor 8.47dB — this is not a borderline, noisy read; n=2,063 rows makes the
CI tight and it sits nowhere near either bar), real off-air signals carry residual structure — timing
jitter beyond a linear drift term, non-Rayleigh fading, phase noise, co-channel contamination inside
the isolation window that a 60Hz frequency-only test can't fully exclude — that this method's
amplitude/phase/linear-drift model does not capture.

**Per spec sec.10: Stage 2 (the payoff — decode residuals, count corroborated new decodes) is not
run.** It needed PASS or PARTIAL and the Captain's go; this reads neither. The `qa/` measurement
harness itself, and every bug found and fixed while building it, is preserved on `qa/sub-feas` for
any future arm that wants to build on it.

## What this settles, and what it doesn't

- **Settles**: on this real 40m corpus, data-aided subtraction — as specified, including the
  Amendment 2 drift extension — cannot suppress a decoded signal to within 3dB (or even 6dB) of the
  noise floor. This is the answer to the precondition the record named as missing
  (board archive, 2026-09-13): it now exists as a measured, disclosed number, not an open question.
- **Does not settle**: whether a DIFFERENT residual model (non-linear drift, explicit phase-noise
  term, joint multi-signal fitting for the co-channel case) would close the remaining ~6–9dB gap.
  That would be new work, not a re-run of this spec, and is the Architect's/Captain's call per the
  standing subtraction-build prohibition.

## Housekeeping

- HK-019 orphan check after the parallel run: clean, zero Python processes remaining post-exit.
- All deliverables NFR-021/HK-037 scanned clean (`nfr021_pre_merge_scan.scan()`).
- Nothing pushed (HK-033); holding on `qa/sub-feas` for the Captain's/Architect's disposition of the
  branch (archive as a closed measurement, or otherwise).
