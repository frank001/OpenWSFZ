# Unmatched-decode audit (descriptive)

Run 20261009_1752: OpenWSFZ (DI sync 5, shim 20260061, nhard 24, corrected OSD, subtraction ON) against live WSJT-X on the same feed, 40 m, direct USB CODEC. One night, one chain, first row of its kind: **no cross-row reading, no pass/fail bar**. Whether an unmatched decode is real (section 8.2) is NOT answered here. Aggregates only (HK-037). 95 % intervals: Wilson for shares, bootstrap (1000 resamples, seed 20261010) for medians.

## Counts (asserted against the ANOVA report)

- OpenWSFZ rows 62617, WSJT-X rows 93611, matched 62340.
- OWS-only 277 (0.4 % [0.4, 0.5] of OWS); WSJT-X-only 31271 (33.4 % [33.1, 33.7] of WSJT-X).
- Cycles with at least one decode: OWS 3630, WSJT-X 3628, both 3628, WSJT-X only 0, OWS only 2.

## (a) OWS-only vs matched (OpenWSFZ-side fields)

**SNR**

| bin | OWS-only (n=277) | matched (n=62340) |
|---|---:|---:|
| (-inf, -20] dB | 10.1 % [7.1, 14.2] | 2.4 % [2.3, 2.5] |
| (-20, -15] dB | 26.7 % [21.8, 32.2] | 16.4 % [16.1, 16.7] |
| (-15, -10] dB | 28.5 % [23.5, 34.1] | 26.5 % [26.2, 26.9] |
| (-10, -5] dB | 18.4 % [14.3, 23.4] | 24.7 % [24.4, 25.1] |
| (-5, 0] dB | 10.8 % [7.7, 15.0] | 16.5 % [16.2, 16.7] |
| (0, +inf] dB | 5.4 % [3.3, 8.7] | 13.5 % [13.2, 13.7] |

Median OWS-only: -12.00 [-13.00, -11.00]; median matched: -9.00 [-9.00, -9.00].

**Frequency**

| bin | OWS-only (n=277) | matched (n=62340) |
|---|---:|---:|
| [-inf, 500) Hz | 7.2 % [4.7, 10.9] | 9.1 % [8.9, 9.3] |
| [500, 1000) Hz | 15.5 % [11.7, 20.3] | 19.2 % [18.9, 19.5] |
| [1000, 1500) Hz | 25.6 % [20.8, 31.1] | 23.3 % [22.9, 23.6] |
| [1500, 2000) Hz | 25.6 % [20.8, 31.1] | 21.5 % [21.2, 21.9] |
| [2000, 2500) Hz | 17.7 % [13.6, 22.6] | 18.4 % [18.1, 18.7] |
| [2500, 3000) Hz | 8.3 % [5.6, 12.2] | 8.5 % [8.3, 8.7] |
| [3000, +inf) Hz | 0.0 % [0.0, 1.4] | 0.0 % [0.0, 0.1] |

Median OWS-only: 1516.00 [1397.00, 1628.00]; median matched: 1478.00 [1456.00, 1491.00].

**DT**

| bin | OWS-only (n=277) | matched (n=62340) |
|---|---:|---:|
| (-inf, 0] s | 13.0 % [9.5, 17.5] | 2.8 % [2.6, 2.9] |
| (0, 0.5] s | 1.1 % [0.4, 3.1] | 3.8 % [3.7, 4.0] |
| (0.5, 1] s | 48.4 % [42.6, 54.2] | 81.3 % [81.0, 81.6] |
| (1, 1.5] s | 29.6 % [24.5, 35.2] | 8.0 % [7.8, 8.2] |
| (1.5, +inf] s | 7.9 % [5.3, 11.7] | 4.1 % [3.9, 4.3] |

Median OWS-only: 0.90 [0.80, 1.00]; median matched: 0.80 [0.80, 0.80].

**Cycle density (OWS decodes in the cycle)**

| bin | OWS-only (n=277) | matched (n=62340) |
|---|---:|---:|
| [-inf, 10) decodes | 1.8 % [0.8, 4.2] | 2.9 % [2.8, 3.0] |
| [10, 20) decodes | 46.9 % [41.1, 52.8] | 51.7 % [51.3, 52.1] |
| [20, 30) decodes | 49.8 % [44.0, 55.7] | 43.2 % [42.8, 43.6] |
| [30, 40) decodes | 1.4 % [0.6, 3.7] | 2.2 % [2.1, 2.4] |
| [40, +inf) decodes | 0.0 % [0.0, 1.4] | 0.0 % [0.0, 0.0] |

Median OWS-only: 20.00 [19.00, 21.00]; median matched: 19.00 [19.00, 19.00].

**Hashed-message share:** OWS-only 1.4 % [0.6, 3.7]; matched 4.5 % [4.3, 4.7].

**Clustering:** the 277 OWS-only decodes sit in 214 distinct cycles (of 3630); most in one cycle: 23; cycles with 2 or more: 26.

**Occupancy (mirror of (b)):** 13.7 % [10.2, 18.3] of the OWS-only decodes sit in cycles where WSJT-X has no row at all (2 such cycles; WSJT-X produced nothing there, so these cannot be disagreements). Excluding them, OWS-only = 239 in 212 cycles.

**Timing-label check:** 0.0 % [0.0, 1.4] of the OWS-only decodes have the same text in WSJT-X one cycle earlier or later (a cycle-labelling difference, not a missed signal); 0 have the same text in the same cycle on WSJT-X but beyond the pairing count (duplicate-text surplus).

## (b) WSJT-X-only vs matched (WSJT-X-side fields)

**SNR**

| bin | WSJT-X-only (n=31271) | matched (n=62340) |
|---|---:|---:|
| (-inf, -20] dB | 16.4 % [16.0, 16.8] | 2.1 % [2.0, 2.2] |
| (-20, -15] dB | 26.4 % [26.0, 26.9] | 9.3 % [9.1, 9.5] |
| (-15, -10] dB | 26.5 % [26.0, 27.0] | 18.8 % [18.5, 19.1] |
| (-10, -5] dB | 17.8 % [17.4, 18.2] | 23.8 % [23.5, 24.2] |
| (-5, 0] dB | 8.6 % [8.3, 8.9] | 20.8 % [20.5, 21.1] |
| (0, +inf] dB | 4.3 % [4.1, 4.5] | 25.2 % [24.8, 25.5] |

Median WSJT-X-only: -13.00 [-13.00, -13.00]; median matched: -5.00 [-5.00, -5.00].

**Frequency**

| bin | WSJT-X-only (n=31271) | matched (n=62340) |
|---|---:|---:|
| [-inf, 500) Hz | 6.9 % [6.6, 7.2] | 9.1 % [8.9, 9.4] |
| [500, 1000) Hz | 22.4 % [22.0, 22.9] | 19.3 % [19.0, 19.6] |
| [1000, 1500) Hz | 24.1 % [23.6, 24.6] | 23.3 % [23.0, 23.6] |
| [1500, 2000) Hz | 24.2 % [23.7, 24.7] | 21.3 % [21.0, 21.7] |
| [2000, 2500) Hz | 16.2 % [15.8, 16.6] | 18.4 % [18.1, 18.7] |
| [2500, 3000) Hz | 6.0 % [5.8, 6.3] | 8.5 % [8.3, 8.7] |
| [3000, +inf) Hz | 0.1 % [0.0, 0.1] | 0.0 % [0.0, 0.1] |

Median WSJT-X-only: 1444.00 [1433.00, 1456.00]; median matched: 1479.00 [1456.00, 1490.00].

**DT**

| bin | WSJT-X-only (n=31271) | matched (n=62340) |
|---|---:|---:|
| (-inf, 0] s | 13.4 % [13.0, 13.7] | 11.4 % [11.2, 11.7] |
| (0, 0.5] s | 78.3 % [77.8, 78.7] | 79.6 % [79.3, 79.9] |
| (0.5, 1] s | 5.7 % [5.5, 6.0] | 5.9 % [5.7, 6.1] |
| (1, 1.5] s | 1.9 % [1.7, 2.0] | 2.4 % [2.3, 2.6] |
| (1.5, +inf] s | 0.8 % [0.7, 0.9] | 0.7 % [0.6, 0.7] |

Median WSJT-X-only: 0.20 [0.20, 0.20]; median matched: 0.20 [0.20, 0.20].

**Cycle density (WSJT-X decodes in the cycle)**

| bin | WSJT-X-only (n=31271) | matched (n=62340) |
|---|---:|---:|
| [-inf, 10) decodes | 0.0 % [0.0, 0.1] | 0.1 % [0.0, 0.1] |
| [10, 20) decodes | 12.8 % [12.4, 13.2] | 14.4 % [14.1, 14.6] |
| [20, 30) decodes | 42.9 % [42.3, 43.4] | 44.6 % [44.3, 45.0] |
| [30, 40) decodes | 36.2 % [35.7, 36.7] | 34.0 % [33.6, 34.4] |
| [40, +inf) decodes | 8.1 % [7.8, 8.4] | 6.9 % [6.7, 7.1] |

Median WSJT-X-only: 28.00 [28.00, 28.00]; median matched: 28.00 [28.00, 28.00].

**Hashed-message share:** WSJT-X-only 7.7 % [7.4, 8.0]; matched 4.5 % [4.3, 4.7].

### Occupancy: missed cycles versus missed signals inside decoded cycles

| where OpenWSFZ decoded | WSJT-X decodes | of them WSJT-X-only | matched |
|---|---:|---:|---:|
| nothing in the cycle (OWS has no row at all) | 0 | 0 | 0 |
| at least one decode in the cycle | 93611 | 31271 | 62340 |

- Share of the 31271 WSJT-X-only decodes in cycles where OWS decoded nothing: **0.0 % [0.0, 0.0]**; inside cycles OWS did decode: **100.0 % [100.0, 100.0]**.
- Inside cycles OWS did decode (3628 cycles): matched share of WSJT-X's decodes **66.6 % [66.3, 66.9]** (the decoder-gap figure; 0 cycles were decoded by WSJT-X and not at all by OpenWSFZ).
- Overall matched share of WSJT-X's decodes: 66.6 % [66.3, 66.9].

- OWS-empty cycles that WSJT-X decoded in: 0 (median WSJT-X decodes per such cycle n/a).

