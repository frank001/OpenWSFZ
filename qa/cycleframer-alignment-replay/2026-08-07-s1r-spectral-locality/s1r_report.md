# S.1r -- spectral locality re-evidenced at power: results

Generated 2026-08-07 17:24 UTC. Script: `s1r_spectral_locality.py`, same directory.

Per Section 7 of `2026-08-07-1616-architect-to-qa-captain-rulings-and-d001-reconciliation.md`. S.1 is CLOSED; this re-evidences its limb only, at ~44x the sample the 08-04 conversational closure rested on. Reference: fresh WSJT-X on the identically replayed audio (never `jt9 -d 3`, never the archived corpus ALL.TXT).

## Per-run summary

| run | WSJT-X (pass 1) | OpenWSFZ (pass 1) | usable records | excluded (single-decode cycle) | excluded (band-edge) | missed | miss rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 752 | 461 | 742 | 0 | 10 | 295 | 39.8% |
| 2 | 754 | 457 | 744 | 0 | 10 | 296 | 39.8% |
| 3 | 758 | 461 | 748 | 0 | 10 | 296 | 39.6% |
| 4 | 759 | 465 | 749 | 0 | 10 | 293 | 39.1% |
| 5 | 756 | 463 | 746 | 0 | 10 | 296 | 39.7% |

Pooled usable records: **3729**. Pooled excluded (single-decode cycles, `sep` undefined): **0**. Pooled excluded (band-edge, outside [200,3000) Hz -- OpenWSFZ's hardcoded search band, per 2026-08-06-2323 Section 4, a certain defect unrelated to spectral locality): **50**. ⚠️ Discovered live while running this analysis (see the Methodology note below) -- not one of the confounds Section 7.6 anticipated in advance.

## Separation (`sep`) distribution -- mandatory lattice check (Section 7.3)

n=3729, mean=38.8 Hz, p10=5.0, p50=32.0, p90=81.0, min=0.0, max=275.0 Hz.

## Boundary set: `primary_50_150`

- Records dropped for density outside 30-49/cycle: 0
- Strata (sep x dens x snr) included (pooled n>=20): 24; excluded: 8
- Excluded strata: clear (>150) | 40-49 | strong (>=-3), clear (>150) | 35-39 | weak (-15..-10), clear (>150) | 30-34 | mid (-10..-3), clear (>150) | 35-39 | very weak (<-15), clear (>150) | 30-34 | strong (>=-3), clear (>150) | 35-39 | mid (-10..-3), clear (>150) | 30-34 | weak (-15..-10), clear (>150) | 35-39 | strong (>=-3)
- Populated Separation levels: local (<50), mid (50-150)
- Populated Density levels: 30-34, 35-39, 40-49
- Lattice OK (all 3 Separation and all 3 Density levels populated at n>=20 somewhere): **False**
- Coverage (surviving strata per level, out of 12 possible Density x SNR / Separation x SNR combinations): local (<50)=12/12, mid (50-150)=12/12, clear (>150)=0/12, 30-34=8/12, 35-39=8/12, 40-49=8/12

| stratum (sep \| dens \| snr) | pooled n |
|---|---:|
| clear (>150) | 30-34 | mid (-10..-3) (EXCLUDED) | 6 |
| clear (>150) | 30-34 | strong (>=-3) (EXCLUDED) | 1 |
| clear (>150) | 30-34 | weak (-15..-10) (EXCLUDED) | 3 |
| clear (>150) | 35-39 | mid (-10..-3) (EXCLUDED) | 3 |
| clear (>150) | 35-39 | strong (>=-3) (EXCLUDED) | 5 |
| clear (>150) | 35-39 | very weak (<-15) (EXCLUDED) | 2 |
| clear (>150) | 35-39 | weak (-15..-10) (EXCLUDED) | 11 |
| clear (>150) | 40-49 | strong (>=-3) (EXCLUDED) | 9 |
| local (<50) | 30-34 | mid (-10..-3) | 66 |
| local (<50) | 30-34 | strong (>=-3) | 91 |
| local (<50) | 30-34 | very weak (<-15) | 66 |
| local (<50) | 30-34 | weak (-15..-10) | 68 |
| local (<50) | 35-39 | mid (-10..-3) | 468 |
| local (<50) | 35-39 | strong (>=-3) | 438 |
| local (<50) | 35-39 | very weak (<-15) | 243 |
| local (<50) | 35-39 | weak (-15..-10) | 328 |
| local (<50) | 40-49 | mid (-10..-3) | 217 |
| local (<50) | 40-49 | strong (>=-3) | 248 |
| local (<50) | 40-49 | very weak (<-15) | 92 |
| local (<50) | 40-49 | weak (-15..-10) | 201 |
| mid (50-150) | 30-34 | mid (-10..-3) | 35 |
| mid (50-150) | 30-34 | strong (>=-3) | 58 |
| mid (50-150) | 30-34 | very weak (<-15) | 41 |
| mid (50-150) | 30-34 | weak (-15..-10) | 48 |
| mid (50-150) | 35-39 | mid (-10..-3) | 174 |
| mid (50-150) | 35-39 | strong (>=-3) | 221 |
| mid (50-150) | 35-39 | very weak (<-15) | 143 |
| mid (50-150) | 35-39 | weak (-15..-10) | 147 |
| mid (50-150) | 40-49 | mid (-10..-3) | 48 |
| mid (50-150) | 40-49 | strong (>=-3) | 140 |
| mid (50-150) | 40-49 | very weak (<-15) | 50 |
| mid (50-150) | 40-49 | weak (-15..-10) | 58 |

## Boundary set: `sensitivity_25_100`

- Records dropped for density outside 30-49/cycle: 0
- Strata (sep x dens x snr) included (pooled n>=20): 29; excluded: 6
- Excluded strata: clear (>100) | 40-49 | weak (-15..-10), clear (>100) | 40-49 | very weak (<-15), clear (>100) | 30-34 | strong (>=-3), clear (>100) | 30-34 | mid (-10..-3), clear (>100) | 30-34 | weak (-15..-10), clear (>100) | 30-34 | very weak (<-15)
- Populated Separation levels: clear (>100), local (<25), mid (25-100)
- Populated Density levels: 30-34, 35-39, 40-49
- Lattice OK (all 3 Separation and all 3 Density levels populated at n>=20 somewhere): **True**
- Coverage (surviving strata per level, out of 12 possible Density x SNR / Separation x SNR combinations): local (<25)=12/12, mid (25-100)=12/12, clear (>100)=5/12, 30-34=8/12, 35-39=12/12, 40-49=9/12

| stratum (sep \| dens \| snr) | pooled n |
|---|---:|
| clear (>100) | 30-34 | mid (-10..-3) (EXCLUDED) | 9 |
| clear (>100) | 30-34 | strong (>=-3) (EXCLUDED) | 14 |
| clear (>100) | 30-34 | very weak (<-15) (EXCLUDED) | 6 |
| clear (>100) | 30-34 | weak (-15..-10) (EXCLUDED) | 17 |
| clear (>100) | 35-39 | mid (-10..-3) | 36 |
| clear (>100) | 35-39 | strong (>=-3) | 31 |
| clear (>100) | 35-39 | very weak (<-15) | 35 |
| clear (>100) | 35-39 | weak (-15..-10) | 34 |
| clear (>100) | 40-49 | strong (>=-3) | 32 |
| clear (>100) | 40-49 | very weak (<-15) (EXCLUDED) | 10 |
| clear (>100) | 40-49 | weak (-15..-10) (EXCLUDED) | 5 |
| local (<25) | 30-34 | mid (-10..-3) | 42 |
| local (<25) | 30-34 | strong (>=-3) | 40 |
| local (<25) | 30-34 | very weak (<-15) | 50 |
| local (<25) | 30-34 | weak (-15..-10) | 44 |
| local (<25) | 35-39 | mid (-10..-3) | 295 |
| local (<25) | 35-39 | strong (>=-3) | 264 |
| local (<25) | 35-39 | very weak (<-15) | 153 |
| local (<25) | 35-39 | weak (-15..-10) | 213 |
| local (<25) | 40-49 | mid (-10..-3) | 164 |
| local (<25) | 40-49 | strong (>=-3) | 189 |
| local (<25) | 40-49 | very weak (<-15) | 58 |
| local (<25) | 40-49 | weak (-15..-10) | 110 |
| mid (25-100) | 30-34 | mid (-10..-3) | 56 |
| mid (25-100) | 30-34 | strong (>=-3) | 96 |
| mid (25-100) | 30-34 | very weak (<-15) | 51 |
| mid (25-100) | 30-34 | weak (-15..-10) | 58 |
| mid (25-100) | 35-39 | mid (-10..-3) | 314 |
| mid (25-100) | 35-39 | strong (>=-3) | 369 |
| mid (25-100) | 35-39 | very weak (<-15) | 200 |
| mid (25-100) | 35-39 | weak (-15..-10) | 239 |
| mid (25-100) | 40-49 | mid (-10..-3) | 101 |
| mid (25-100) | 40-49 | strong (>=-3) | 176 |
| mid (25-100) | 40-49 | very weak (<-15) | 74 |
| mid (25-100) | 40-49 | weak (-15..-10) | 144 |

## Boundary set: `sensitivity_75_200`

- Records dropped for density outside 30-49/cycle: 0
- Strata (sep x dens x snr) included (pooled n>=20): 19; excluded: 8
- Excluded strata: mid (75-200) | 40-49 | weak (-15..-10), mid (75-200) | 40-49 | very weak (<-15), mid (75-200) | 30-34 | mid (-10..-3), clear (>200) | 30-34 | mid (-10..-3), mid (75-200) | 30-34 | very weak (<-15), clear (>200) | 30-34 | strong (>=-3), clear (>200) | 35-39 | mid (-10..-3), clear (>200) | 35-39 | strong (>=-3)
- Populated Separation levels: local (<75), mid (75-200)
- Populated Density levels: 30-34, 35-39, 40-49
- Lattice OK (all 3 Separation and all 3 Density levels populated at n>=20 somewhere): **False**
- Coverage (surviving strata per level, out of 12 possible Density x SNR / Separation x SNR combinations): local (<75)=12/12, mid (75-200)=7/12, clear (>200)=0/12, 30-34=6/12, 35-39=8/12, 40-49=5/12

| stratum (sep \| dens \| snr) | pooled n |
|---|---:|
| clear (>200) | 30-34 | mid (-10..-3) (EXCLUDED) | 6 |
| clear (>200) | 30-34 | strong (>=-3) (EXCLUDED) | 1 |
| clear (>200) | 35-39 | mid (-10..-3) (EXCLUDED) | 3 |
| clear (>200) | 35-39 | strong (>=-3) (EXCLUDED) | 5 |
| local (<75) | 30-34 | mid (-10..-3) | 90 |
| local (<75) | 30-34 | strong (>=-3) | 119 |
| local (<75) | 30-34 | very weak (<-15) | 96 |
| local (<75) | 30-34 | weak (-15..-10) | 96 |
| local (<75) | 35-39 | mid (-10..-3) | 571 |
| local (<75) | 35-39 | strong (>=-3) | 588 |
| local (<75) | 35-39 | very weak (<-15) | 327 |
| local (<75) | 35-39 | weak (-15..-10) | 419 |
| local (<75) | 40-49 | mid (-10..-3) | 265 |
| local (<75) | 40-49 | strong (>=-3) | 355 |
| local (<75) | 40-49 | very weak (<-15) | 127 |
| local (<75) | 40-49 | weak (-15..-10) | 253 |
| mid (75-200) | 30-34 | mid (-10..-3) (EXCLUDED) | 11 |
| mid (75-200) | 30-34 | strong (>=-3) | 30 |
| mid (75-200) | 30-34 | very weak (<-15) (EXCLUDED) | 11 |
| mid (75-200) | 30-34 | weak (-15..-10) | 23 |
| mid (75-200) | 35-39 | mid (-10..-3) | 71 |
| mid (75-200) | 35-39 | strong (>=-3) | 71 |
| mid (75-200) | 35-39 | very weak (<-15) | 61 |
| mid (75-200) | 35-39 | weak (-15..-10) | 67 |
| mid (75-200) | 40-49 | strong (>=-3) | 42 |
| mid (75-200) | 40-49 | very weak (<-15) (EXCLUDED) | 15 |
| mid (75-200) | 40-49 | weak (-15..-10) (EXCLUDED) | 6 |

## Methodology note: additive model, not saturated interaction model

The pre-registered spec (Section 7.3) says to reuse the existing 3-way ANOVA machinery, one factor added. That machinery (`three_way_anova_with_replication`, `build_full_anova.py`) assumes a fully-crossed BALANCED design -- every (Separation x Density x SNR) cell populated with exactly 5 (Run) replicates. The real data does not support that: at the primary 50/150 Hz boundary the `clear (>150 Hz)` Separation level survives the pooled-n>=20 gate in 0 of its 12 possible (Density x SNR) combinations once the band-edge exclusion is applied (see the coverage line above and the band-edge note), which would make a saturated 3-way-interaction model rank-deficient even before the lattice check itself already routes this boundary to ROW 4. This analysis instead fits a strictly ADDITIVE model (main effects only, no interactions among Separation/Density/SNR) via ordinary least squares with sum-to-zero (deviation) contrast coding, Type II sums of squares (each term tested against a model containing the other two main effects), and the full model's own residual as the error term -- algebraically the unbalanced-data generalisation of the same idea, and it still delivers exactly what Section 7.4 asks for: least-squares marginal means from the fitted model, each term's effect controlled for the other two. The trade-off, stated plainly: any genuine Separation x Density (or other) interaction is NOT modelled and instead flows into the residual, which makes every F-test in this report MORE conservative (biased toward NULL), never less -- the safer failure direction for a pre-registered LIVE gate that already requires p<0.01.

## Pre-registered gate (Section 7.5), primary 50/150 Hz boundary ONLY

Sensitivity boundaries (25/100, 75/200) are reported above (pooled-n tables) but per Section 7.6 #4 never evaluate the gate.

**Gate did not fire: lattice check failed (unpopulated level). Verdict: ROW 4 (no verdict / RC1 not narrowed).**

## Sensitivity boundaries -- reported, NEVER gated (Section 7.6 #4)

Per spec: 'reporting the others guards against a boundary artefact; letting them fire the gate would be fishing.' Shown for context only.

| boundary | lattice OK | E_sep (pp) | p_sep | local limb | E_dens (pp) | p_dens | global limb | would-be row |
|---|---|---:|---:|---|---:|---:|---|---|
| `sensitivity_25_100` | True | +49.02 | 0.000000 | LIVE | +11.23 | 0.000002 | LIVE | ROW 1 |
| `sensitivity_75_200` | False | -- | -- | -- | -- | -- | -- | ROW 4 (lattice check failed (unpopulated level)) |

## What this does and does not establish

Per spec Section 7.7: one window, density 30-49/cycle (silent on the ~7/cycle regime); decode-side, not pipeline-side; observational, not interventional; does not re-open S.1 and does not reverse the Captain's closure.

