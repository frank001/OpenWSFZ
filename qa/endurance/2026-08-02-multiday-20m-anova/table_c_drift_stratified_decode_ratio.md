# Table C -- drift-stratified decode-ratio vs zero-drift control

**Run:** 2026-07-31 20:04Z -> 2026-08-02 15:52Z multi-day 20m live run: Table C, 8080 vs 8081 zero-drift control  
**Generated:** 2026-08-02T17:37:58Z (`date -u`, HK-017)  
**Method:** cycle-level, not decode-level -- 8080's decode_count per 15s cycle, grid-snapped and stratified by its own ORIGINAL (pre-snap) offset, matched against 8081's decode_count for the identical snapped cycle (same antenna, same instant -- propagation is common-mode by construction, per the Captain's splitter fact). Ratio is SUM(target decode_count)/SUM(control decode_count) per stratum, not a mean of per-cycle ratios, to avoid small-denominator cycles dominating.

## Control-matched ratio (the number that isolates drift's cost)

| 8080 drift stratum | matched cycles | 8080 decodes (matched cycles) | 8081 decodes (matched cycles) | ratio | vs +0s |
|---|---:|---:|---:|---:|---:|
| +0s | 3639 | 66998 | 69871 | 0.959 | -- |
| +1s | 4148 | 80427 | 86370 | 0.931 | -2.9% |
| +2s | 2702 | 37493 | 55717 | 0.673 | -29.8% |

## Raw per-stratum mean decode count (propagation-confounded -- do NOT use this for "what does drift cost")

| 8080 drift stratum | cycles | mean decodes/cycle | vs +0s |
|---|---:|---:|---:|
| +0s | 3639 | 18.41 | -- |
| +1s | 4148 | 19.39 | +5.3% |
| +2s | 2702 | 13.88 | -24.6% |

**Why these two tables disagree:** drift strata correlate with hours-since-restart, which correlates with time of day, which correlates with propagation. The raw table above inherits that confound; the control-matched table does not, because both instances hear the same antenna at the same instant regardless of which stratum the target's clock happens to be in.

