# SUB-FEAS: spec §5's SNR-band X/D description — added, purely descriptive

**QA, 2026-09-28 01:10Z** (`date -u`, HK-017). Branch `qa/sub-feas`. Addendum to
`qa/rr-study/2026-09-28-0023-qa-to-architect-sub-feas-stage1-results.md`, per the Architect's
Stage 1 ruling (`d8a8436d`, item 3: "add it if the harness has it cheaply; otherwise note the
omission"). **This does not reopen or re-read the Stage 1 gate** — that reading (FAIL) stands as
ruled. Spec §5: "Report X and D by SNR band [0,5), [5,10), [10,∞) as a description only."

## What this cost

The original run didn't persist per-row fit records (only the gate's summary statistics), so this
required a **targeted re-fit of split B only** — `τ0` (−0.1600s) and `W*` (0.32s) both reused exactly
as accepted, not re-derived. `qa/rr-study/sub-feas/snr_band_addendum.py`, run detached (HK-023):
2,063/2,094 rows fit, 1,808s (~30 min). Full result: `artefacts/sub-feas/snr_band_addendum.json`
(gitignored; the numbers below are the complete, disclosed content).

## Result (split B, L2 at W*=0.32, by the row's own SNR)

| SNR band | n | median X (dB) | X p25/p75 | median D (dB) |
|---|---:|---:|---|---:|
| [0, 5) | 1,004 | 7.15 | 2.37 / 10.45 | 17.66 |
| [5, 10) | 586 | 9.59 | 4.77 / 13.14 | 19.99 |
| [10, ∞) | 473 | 12.86 | 7.04 / 17.50 | 22.46 |

(n sums to 2,063, matching the accepted `n_B_fit`.)

## Reading this, descriptively (not a re-gate)

X rises with SNR band, and D rises alongside it. This is the same pattern the Architect's own
`X_empty` control and QA's ROW 0b drift analysis both already surfaced: absolute leftover residual
after subtraction scales with the original signal's own strength (a roughly fixed *fractional*
modelling error leaves a *larger absolute* residual for a stronger signal), while the local noise
floor `N̂` does not scale with that row's own SNR. So a stronger signal is suppressed by more
absolute dB (`D` rises) while *also* reading further above the noise floor (`X` rises) — both
readings are consistent with the same underlying mechanism, not in tension.

Every band's median misses the PARTIAL bar on its own (all > 6.0dB), so no SNR band hides a different
verdict — the FAIL is not being driven by one band alone.

**Descriptive, worth recording**: `D` rises only ~5dB (17.7→22.5) while SNR rises ≥10dB across the
same bands. Suppression looks capped by a roughly fixed relative model error (~20dB below the
original signal), not by the noise floor — the residual is a fraction of the signal that stays
roughly constant across this SNR range, not a fixed absolute noise-limited floor.
