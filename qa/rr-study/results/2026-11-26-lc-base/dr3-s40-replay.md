# DR-3 replay: the lean decoder on S40 with the duplicate fix

**Date:** 2026-11-26 · **Author:** QA · **Spec:** the optional, reported-only replay of the DR-3 task (`dev-tasks/2026-11-26-dr3-lean-default-engine-and-duplicate-fix.md` §4; Architect's `spec-dr2-lean-decoder.md` §4). One run, no bars. Aggregates only (NFR-021).

## What was run

- **Build:** the DR-3 source (`75e76666`, in `feat/dr3-lean-default` `4fa2c637`), harness `Ft8.FitProbe` with `HasLean`, `libft8.dll` shim 20260079, **SHA-256 `199ccbb906e64112450c1e716010889b067a29cbcd6069f5f2988c836c99f5af`** (equal to the Developer's reported hash; the runner asserts it before and after). Run by `qa/decoder-rebuild/lc_base_run.py S40 L 170 --tag dr3 --bin ...\lc-base\bin_dr3 --pin 199ccbb9…`; no `--filter` (a replay).
- **Same as before:** slice S40 (170 cycles from `261115_072930`, 6,773 WSJT-X decodes), arm L (lean, 16 threads, effort normal, the LC-BASE flags), the same scoring. The comparison run is DR-2e's L5 (`fc4fb788`, shim 20260078).

## Result

| | Lean before DR-3 (L5) | Lean with DR-3 | Classic (A6, for reference) |
|---|---:|---:|---:|
| `rate` | 81.515 % | **84.704 %** | 84.39 % |
| matched / ours | 5,521 / 5,780 | **5,737 / 6,009** | 5,716 / 5,971 |
| `ours_only` | 3.824 % | 4.016 % | 3.77 % |
| "same text, other frequency" rows | **14** | **0** | 0 |
| CPU per cycle | 13.41 s | 14.11 s | 25.25 s |
| last batch p95 | 2,053 ms | 2,024 ms | 7,332 ms |
| abandoned cycles / native errors | 0 / 0 | 0 / 0 | 0 |

- **The 14 rows are gone** (0 now; before, all at about 100 Hz below WSJT-X, all round 0). The Architect's hypothesis holds: with the highest-score copy published, the ghost no longer wins.
- **The rate rose by 3.19 pp, far more than 14 rows explain (0.2 pp).** Compared per WSJT-X decode: 236 newly matched, 20 no longer matched, net **+216**. By the batch that found them: batch 1 (round 0) **+14** (exactly the 14 rows), **batch 2 (rounds 1 to 3) +213** (1,353 to 1,566), cross-cycle stage −11. 115 of the 170 cycles changed.
- **Lean now matches classic's A6 on this slice** (84.70 % against 84.39 %, +0.31 pp) at 56 % of its CPU and about 28 % of its last-batch time.
- The false side grew by 0.19 pp (3.82 to 4.02 %), still inside the DR-2 bar of 4.27 %.

## Reading (not a ruling)

- The round-0 fix explains only the 14 rows. The 213 extra decodes in rounds 1 to 3 are the knock-on effect of the same change: the duplicate rule also applies in the residual rounds (same transmission and same text), and a round-0 result at the right frequency is subtracted at the right frequency, so the weaker signals beside it are found afterwards. That is the crowded-signal mechanism of CS-MAP (a weaker signal next to a stronger one that was found), reached through a bug fix. **This is a reading from one aggregate, not a measurement of the mechanism;** QA did not separate the round-0 and residual-round parts of the rule.
- **One slice, one run.** LC-BASE's other two slices (H40, H20) were run on the pre-DR-3 build, so their lean rates (84.27 %, 82.03 %) are not comparable with this result. Re-running lean on H40 and H20 (about 7 minutes each, classic unchanged) would say whether the gain holds; not done, outside the one allowed replay.
- Issue #294 (the ~100 Hz offset): the symptom is gone on S40; the cause stays a hypothesis.

## Files

Run data (text-bearing `nc.tsv`, KEEP): `D:\Projects\claude\_qa-scratch\lc-base\runs\dr3_S40_L_n170`; aggregate-only copy `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-11-26-lc-base\runs\dr3_S40_L_n170\` (root results folder).
