# DR-0 result and DR-1 decisions (QA, 2026-11-24)

Spec: `docs/decoder-rebuild/spec-dr0-dr1-measure-and-relief.md` on `arch/decoder-rebuild` `68f7f15e`. A measurement; no verdict on the plan. Aggregates only (NFR-021); the text-bearing working files stay under `D:\Projects\claude\_qa-scratch\dr0\` (KEEP).

## What was run

- **Slice 40:** `qa/decoder-rebuild/test-set.md`: night `20261114_2312`, 40 m, **170 cycles** from `261115_072930` (shortened from 240 by the spec's 2 h rule; see "Time" below), warm-up cycle `261115_072915`, **6,773 WSJT-X decodes** in the window (`ALL.TXT` lines stamped inside it, counted by code).
- **Harness:** `Ft8.FitProbe.exe` (Replay81 over the shipped decoder), binary dir `_qa-scratch\xc-chain\bin_defaults`. `libft8.dll` SHA256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`, asserted equal to the pin before and after every arm. The runner `qa/decoder-rebuild/dr0_run.py` refuses to start with a competing process up.
- **`--filter` / projects:** none; this is a replay, not a test run. Each arm's `# readback` lines were checked in its log (A7: `nhard=0` start and end; A9: `threadsResolved=2` start and end; A6: `nhard=24`).
- **`cpu_s`:** user + kernel CPU seconds of the harness process, from its process handle after exit, divided by 170. It includes the process's start-up and WAV reading.
- **`ours`/`matched`:** distinct (cycle, text) rows of the harness's per-row file; `matched` = rows the harness marked as matching a WSJT-X decode in that cycle. `rate = matched / 6,773`; `ours_only = (ours - matched) / 6,773`.
- **`last_p95`:** p95 over cycles of the latest batch time in the harness's per-cycle file, measured from the decode's start. `abandoned`: cycles with any abandoned or contained step in the abandon file.
- **A0:** the harness cannot idle; left empty, floor `cpu_s` = 0. **A8:** the staged replay path never runs the early decode, so per the spec A8's saving is A1's `cpu_s` - A0's = **0.57 CPU-s per cycle** (it includes the harness's own start-up; read it as an upper bound).

## The table (Slice 40, 170 cycles, one run per arm)

| Arm | Configuration | cpu_s | last_p95 (ms) | abandoned | ours | matched | rate % | ours_only % |
|---|---|---|---|---|---|---|---|---|
| A0 | decoding off | (empty, floor 0) | | | | | | |
| A1 | primary only | 0.566 | 631 | 0 | 3,827 | 3,788 | 55.93 | 0.58 |
| A2 | + residual pass | 10.196 | 634 | 0 | 4,661 | 4,603 | 67.96 | 0.86 |
| A3 | + coherent fallback (Normal) | 13.696 | 3,724 | 0 | 5,045 | 4,955 | 73.16 | 1.33 |
| A4 | Deep (third pass) | 22.254 | 6,030 | 0 | 5,595 | 5,451 | 80.48 | 2.13 |
| A5 | + late round | 24.356 | 7,308 | 0 | 5,737 | 5,583 | 82.43 | 2.27 |
| **A6** | **+ XC = today's station = BASELINE** | **25.247** | **7,332** | **0** | **5,971** | **5,716** | **84.39** | **3.77** |
| A7 | A6 with OSD off (`--nhard 0`) | 25.280 | 7,316 | 0 | 5,968 | 5,715 | 84.38 | 3.74 |
| A8 | A6 without the early decode | not replayable; saving reported as A1 - A0 = 0.57 | | | | | | |
| A9 | A6 with worker threads capped at 2 | 21.281 | 12,798 | 0 | 5,806 | 5,581 | 82.40 | 3.32 |

Total wall time of the eight arms: 7,488 s = **2 h 05 min**, started 19:01:43Z, all arms finished by 21:06Z.

## Per step

| Step | Δcpu_s | NET (pp) | NET per CPU-s |
|---|---|---|---|
| A1 to A2 (residual pass) | +9.63 | +12.03 | 1.25 |
| A2 to A3 (coherent fallback) | +3.50 | +5.20 | 1.49 |
| A3 to A4 (third pass, Deep) | +8.56 | +7.32 | 0.86 |
| A4 to A5 (late round) | +2.10 | +1.95 | 0.93 |
| A5 to A6 (XC) | +0.89 | +1.96 | 2.20 |
| A6 to A7 (OSD off) | +0.03 | -0.015 | n/a |
| A6 to A9 (threads capped at 2) | -3.97 | -1.99 | 0.50 |

**Baseline for everything after this (A6):** `rate` 84.39 %, `ours_only` 3.77 %, `cpu_net` = 25.247 - 0 = **25.25 CPU-s per cycle**, `last_p95` 7,332 ms. The plan's CPU target (25 % of today) is therefore **6.31 CPU-s per cycle** on this replay.

## DR-1: the mechanical decisions (spec 3.1)

| Decision | Number it rests on | Result |
|---|---|---|
| Early decode | the Product Owner's decision, independent of the table | **OFF** |
| Third pass (A3 to A4) | NET +7.32 pp, bar 0.30 | stays **ON** |
| Late round (A4 to A5) | NET +1.95 pp, bar 0.30 | stays **ON** |
| OSD (A6 to A7) | NET -0.015 pp, bar 0.30 | **OFF** |
| Thread cap at 2 | A9 `last_p95` 12,798 ms, bar 11,000 ms (abandoned 0) | **not applied** |
| Residual pass, fallback, XC | fixed by the spec | stay ON |

**A10** = A6 with early decode off and OSD off. The replay never runs the early decode, so A10's configuration **is** A7's, and its row is A7's (the runs are deterministic: the A6 pilot reproduced `ours` and `matched` exactly across two runs). No extra run was made.

| | A6 | A10 (= A7) | Bar | |
|---|---|---|---|---|
| rate | 84.394 % | 84.379 % | at least A6 - 1.00 pp = 83.394 % | pass |
| ours_only | 3.765 % | 3.735 % | at most A6 + 0.50 pp = 4.265 % | pass |
| abandoned | 0 | 0 | 0 | pass |

**DR-1 PASSES.** Its measured CPU relief is **0.0 CPU-s per cycle** (25.247 to 25.280, within noise): OSD costs essentially nothing in this replay, and the early decode cannot be measured here. **Settings alone cannot approach the 6.3 CPU-s target; only the lean engine can.** For the PR body (spec 3.3): A6 vs A10 `cpu_net` 25.25 vs 25.28, `rate` 84.39 vs 84.38, `ours_only` 3.77 vs 3.74, `last_p95` 7,332 vs 7,316 ms.

## Caveats the Captain should know

- **Time:** the eight arms took 2 h 05 min against the 2 h cap (4 % over). The estimate from the 10-cycle pilots under-counted A9, which took 2,062 s against about 1,630 s extrapolated (27 % more); the cause was not investigated. Noted, not repeated.
- **One run per arm, one night, one hour** (the spec's design). No confidence intervals, as the light process says.
- **The replay runs flat out, not in real time:** CPU per cycle is comparable across arms and against the lean engine measured the same way, not against live CPU load.
- **`last_p95` is measured from the decode's own start** in a replay that has no cycle-end offset; the 7.3 s baseline sits well under the 13 s budget. A9's 12.8 s is under the 13 s budget but over DR-1's 11 s bar.
- **A9 lost 2.0 pp:** the capped decoder finishes later and some late batches miss their window (no cycle was formally "abandoned").
- **Warm-up:** the callsign table starts from one warm-up cycle, not a night's history, in every arm alike.

## Next

DR-1's Developer task (defaults: early decode OFF, OSD off, one-time migration, FR updates, VERSION 1.1) follows once the Captain has seen this; the lean-engine steps (2b onward) compare against the A6 row above.
