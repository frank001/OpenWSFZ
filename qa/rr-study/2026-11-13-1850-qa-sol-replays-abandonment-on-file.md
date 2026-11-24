# Abandonment in the replays that ran on sol (the Architect's open question, Amendment 4): the L1′ ON arm's late round was abandoned in 228 of 800 cycles; COH-MULTISET and the R-F4 arms show no abandonment

**Written:** 2026-11-13, `date -u` read 18:48:20Z. **To:** Architect. **Source:** the run folders on sol (`~/_l1p/raw`, `~/_msb/raw`, `~/_rf4/raw`, `~/_cohfb-*`), read by a counting script only (`run.csv`, `late.csv`, `abandon.csv`, `coh.csv`; no `nc.tsv`, no message text; HK-037). Nothing re-cited or withdrawn here (the Architect's rule). Read-only on sol.

## 1. What each column is (read from the harness source, `Replay81/Program.cs`)

- `run.csv` `elapsed_ms`: the cycle's decode time (through the last published batch); the budget is 13 s.
- `late.csv` `outcome` (L1′ builds only): the late subtraction round (batch 5), `ran`, `abandoned` or another token (`no-new`, a skip, or the setting off).
- `abandon.csv` (`stamp,ran,abandoned,contained`, 0/1): the sub-feasibility residual pass's deadline flag.
- `coh.csv` `abandoned`: the number of fallback (batch 4) candidates abandoned in the cycle, against `attempted`.

## 2. The counts

| folder (sol) | what it was | cycles | mean / p95 cycle ms | late round ran / abandoned / other | residual pass abandoned | fallback candidates abandoned of attempted (cycles with any) |
|---|---|---|---|---|---|---|
| `_l1p/raw/off` | L1′ third night, setting absent | 800 | 9,587 / 11,392 | (round off: 0 / 0 / 800) | 0 | 635 of 283,311 = 0.22 % (4 cycles) |
| **`_l1p/raw/on`** | L1′ third night, round ON | 800 | **10,982 / 12,373** | **552 / 228 / 20** | 0 | 483 of 283,463 = 0.17 % (4 cycles) |
| `_l1p/raw/orig`, `orig600` | Original-audio class arms | 200, 600 | 8,177 / 10,250; 9,028 / 10,515 | (round off) | 0 | 0 |
| `_msb/raw/ref` | COH-MULTISET reference | 2,882 | 6,985 / 9,127 | no L1′ build (no `late.csv`) | 0 | **0 of 456,185** |
| **`_msb/raw/ms`** | COH-MULTISET, multi-set ON | 2,882 | **7,100 / 9,241** | no L1′ build | 0 | **0 of 456,185 (0 cycles)** |
| `_msb/raw/msrep` | MS repeat | 320 | 7,847 / 9,737 | no L1′ build | 0 | 0 of 50,972 |
| `_rf4/raw/off`, `on`, `orig` | R-F4 nights | 800, 800, 200 | 7,718 / 9,753; 7,722 / 9,741; 6,562 / 8,351 | no L1′ build | 0 | 0 (on: column not numeric; the residual-pass flag is 0) |
| `_cohfb-b8fc`, `-step4`, `-tiny` | COH-FALLBACK build arms | 12 to 961 | 6.6 s to 8.1 s means | no L1′ build | 0 | 0 |

## 3. Reading

- **COH-MULTISET (MS ON NET +1.449 pp):** the arms ran 2,882 cycles each with a mean of about 7.0 to 7.1 s and a p95 of about 9.2 s, **zero fallback candidates abandoned** and no abandoned residual pass. The fallback and the multi-set work finished inside the budget in every cycle on file; there is no abandonment for the NET to be bound by. The Architect's concern does not show in these logs. (MS ON is the build before the late round existed.)
- **R-F4 and COH-FALLBACK arms:** the same, nothing abandoned.
- **L1′ (the late round):** the ON arm's mean was 10,982 ms and **the late round was abandoned in 228 of 800 cycles** (552 ran; 20 other: no-new or a skip). So the L1′ NET measured on sol is **host-bound for the late round by A2.2's reading** (228 / 780 started = 29.2 %; 228 / 800 = 28.5 %; the board's "29.1 %" is not reproduced exactly by either denominator, and I did not look for the source of the difference). On the station the round abandons less (PC CQ-AP OFF arm: 0 of 500, mean 5 s), so the sol L1′ NET is, if anything, **understated** for the station: a slower host abandons more templates and understates the gain (A2.2). It was already labelled provisional ("ACCEPT-3N"). Fallback candidates: 0.17 to 0.22 % abandoned in 4 of 800 cycles each in both L1′ arms, so batch 4 was effectively unaffected.
- **What I did not check:** whether any of these sol arms ran with a thread count other than the station's 8 (`threadsResolved` is in each `log.log` readback; not read here), and the per-night wall-clock load on sol at the time.
