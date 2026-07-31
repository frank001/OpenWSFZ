# Measurement D -- per-segment re-run (R3/R4 of the 1530 ruling)

Per `2026-07-31-1530-architect-ruling-measurement-d-corpus-is-two-sessions.md` R3: the pooled 18.21-point figure is suspended because the 20m corpus is two sessions 18h28m apart, not one. This re-runs Measurement D's matched-SNR analysis on each segment separately, using the identical stratification, matching and reading-rule logic (`measurement_d_within_band_density.py`), quoting both rather than pooling.

**Note on self-check 1 (matching gate):** that check validates against the *full-corpus* published ANOVA count (24201) and does not apply per segment by construction -- each segment's total matched count is reported below as descriptive, not as a pass/fail gate.

## Segment composition

| segment | cycles | sparse n (cycles) | dense n (cycles) | sparse cutoff | dense cutoff | total matched |
|---|---:|---:|---:|---:|---:|---:|
| segment 1 | 618 | 176 | 159 | <= 23.0 | >= 41.0 | 9751 |
| segment 2 | 712 | 186 | 180 | <= 36.0 | >= 45.0 | 14450 |

## Self-check 2 (density contrast) per segment -- MECHANISED HARD GATE

Per `2026-07-31-1602-architect-ruling-segment-2-void-on-self-check-2.md` V3: `dense_mean / sparse_mean < 2.0` VOIDS the segment before any further check runs -- no duplicate-key check, no common-support check, no reading-rule row.

| segment | sparse mean ref decodes/cycle | dense mean ref decodes/cycle | contrast | verdict |
|---|---:|---:|---:|---|
| segment 1 | 18.47 | 48.86 | 2.65x | readable |
| segment 2 | 33.02 | 54.21 | 1.64x | **VOID (< 2.0x)** |

## Self-check 3 (duplicate-key artefact) per segment

| segment | sparse dup-key rate | dense dup-key rate | gap (pts) | median diff (pts) | confounded? |
|---|---:|---:|---:|---:|---|
| segment 1 | 0.00% | 0.00% | 0.00 | +22.33 | no |
| segment 2 | n/a | n/a | n/a | n/a | **VOID on self-check 2 -- not evaluated** |

## Self-check 4 (common support, n>=20 both strata) per segment

| segment | usable bins | verdict |
|---|---:|---|
| segment 1 | 21 | OK |
| segment 2 | n/a | **VOID on self-check 2 -- not evaluated** |

## segment 1 per-bin recall

| SNR bin (dB) | sparse n | sparse matched | sparse recall | sparse 95% CI | dense n | dense matched | dense recall | dense 95% CI | diff (pts) |
|---:|---:|---:|---:|---|---:|---:|---:|---|---:|
| [-24, -22) | 90 | 9 | 10.0% | [5.4%,17.9%] | 99 | 16 | 16.2% | [10.2%,24.7%] | -6.2 |
| [-22, -20) | 109 | 34 | 31.2% | [23.3%,40.4%] | 83 | 19 | 22.9% | [15.2%,33.0%] | +8.3 |
| [-20, -18) | 163 | 39 | 23.9% | [18.0%,31.0%] | 136 | 24 | 17.6% | [12.2%,24.9%] | +6.3 |
| [-18, -16) | 239 | 72 | 30.1% | [24.7%,36.2%] | 178 | 32 | 18.0% | [13.0%,24.3%] | +12.1 |
| [-16, -14) | 283 | 114 | 40.3% | [34.7%,46.1%] | 273 | 49 | 17.9% | [13.9%,22.9%] | +22.3 |
| [-14, -12) | 271 | 122 | 45.0% | [39.2%,51.0%] | 355 | 79 | 22.3% | [18.2%,26.9%] | +22.8 |
| [-12, -10) | 298 | 144 | 48.3% | [42.7%,54.0%] | 441 | 126 | 28.6% | [24.6%,33.0%] | +19.8 |
| [-10, -8) | 267 | 165 | 61.8% | [55.8%,67.4%] | 484 | 158 | 32.6% | [28.6%,36.9%] | +29.2 |
| [-8, -6) | 254 | 152 | 59.8% | [53.7%,65.7%] | 552 | 165 | 29.9% | [26.2%,33.8%] | +30.0 |
| [-6, -4) | 214 | 144 | 67.3% | [60.7%,73.2%] | 534 | 198 | 37.1% | [33.1%,41.3%] | +30.2 |
| [-4, -2) | 186 | 116 | 62.4% | [55.2%,69.0%] | 580 | 219 | 37.8% | [33.9%,41.8%] | +24.6 |
| [-2, 0) | 177 | 133 | 75.1% | [68.3%,80.9%] | 569 | 261 | 45.9% | [41.8%,50.0%] | +29.3 |
| [0, 2) | 124 | 84 | 67.7% | [59.1%,75.3%] | 524 | 236 | 45.0% | [40.8%,49.3%] | +22.7 |
| [2, 4) | 111 | 89 | 80.2% | [71.8%,86.5%] | 496 | 254 | 51.2% | [46.8%,55.6%] | +29.0 |
| [4, 6) | 105 | 83 | 79.0% | [70.3%,85.7%] | 458 | 263 | 57.4% | [52.9%,61.9%] | +21.6 |
| [6, 8) | 85 | 72 | 84.7% | [75.6%,90.8%] | 378 | 223 | 59.0% | [54.0%,63.8%] | +25.7 |
| [8, 10) | 55 | 42 | 76.4% | [63.7%,85.6%] | 326 | 203 | 62.3% | [56.9%,67.4%] | +14.1 |
| [10, 12) | 57 | 49 | 86.0% | [74.7%,92.7%] | 274 | 182 | 66.4% | [60.6%,71.8%] | +19.5 |
| [12, 14) | 32 | 27 | 84.4% | [68.2%,93.1%] | 211 | 142 | 67.3% | [60.7%,73.3%] | +17.1 |
| [14, 16) | 28 | 25 | 89.3% | [72.8%,96.3%] | 162 | 124 | 76.5% | [69.5%,82.4%] | +12.7 |
| [16, 18) | 23 | 23 | 100.0% | [85.7%,100.0%] | 141 | 99 | 70.2% | [62.2%,77.1%] | +29.8 |

**Median diff: +22.33 pts. 19/21 bins (90%) have diff >= 8 pts.**

**Mechanical outcome (segment 1), Measurement D's spec S4 rule, unmodified: ROW 1: median diff >= 8pts AND >= 80% of bins >= 8pts -> Competition CONFIRMED as a named, measured mechanism.**

## segment 2 per-bin recall

**VOID on self-check 2.** Density contrast 1.64x is below the 2.0x bar -- the strata are too close to read (this segment's sparse stratum, at 33.02 ref decodes/cycle, sits above segment 1's entire sparse-to-middle range and above segment 1's own sparse cutoff -- it compares dense against denser, not sparse against dense). Per the standing stop rule, this segment produced **no reading of any kind** -- not ambiguous, not weak, void. No per-bin table, no median diff, no row outcome is reported, and none should be quoted from this segment (see `1602`'s ruling, citation blacklist).

## Summary

| | segment 1 | segment 2 |
|---|---:|---:|
| cycles | 618 | 712 |
| density contrast | 2.65x | **1.64x -- VOID (< 2.0x)** |
| usable bins | 21 | n/a (void) |
| median diff (pts) | +22.33 | n/a (void) |
| mechanical outcome | ROW 1 -- confirmed | **VOID on self-check 2** |

**Segment 2 is VOID on self-check 2**, per `2026-07-31-1602-architect-ruling-segment-2-void-on-self-check-2.md`: its contrast (1.64x) is too low because its sparse stratum (33.02 ref decodes/cycle) sits above segment 1's entire sparse-to-middle range -- it compares dense against denser, not sparse against dense. It produced no reading of any kind, not an ambiguous or weak one. Do not cite its median diff, bin count, or bin fraction (citation blacklist, `1602` SS7). **Segment 1's ROW 1 stands alone as the reading, unqualified** -- R3/R4's primary designation for segment 1 turns out to be the only segment capable of producing a reading at all, not merely the better of two.

