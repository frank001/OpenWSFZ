# Decoder rebuild: the fixed test set

**Picked by:** QA, 2026-11-24, per `spec-dr0-dr1-measure-and-relief.md` §1 (`arch/decoder-rebuild` `68f7f15e`).
**Fixed from here on.** Aggregates and folder names only (NFR-021).

## Slice 40 (the only slice; Slice 20 was dropped by the Captain on 2026-11-24)

| Item | Value |
|---|---|
| Night | `20261114_2312` (`artefacts/20261114_2312_endurance_run-gathered/`), 40 m |
| Era | MS ON (after 2026-10-25T11:22Z) |
| Audio | `wsjt-x/wav/` (WSJT-X's own WAVs, same audio as the `ALL.TXT` beside them) |
| Start cycle | `261115_072930` |
| End cycle | `261115_082915` |
| Cycles | 240 (15 s each, contiguous, checked) |
| WSJT-X decodes in the slice | 9,431 (lines of `wsjt-x/ALL.TXT` stamped inside the window) |
| Length used by DR-0 | **170 cycles** (`261115_072930` onward), set by the §2.3 pilot: 10-cycle pilots of every arm took 420.7 s wall in total (about 38.2 s per cycle over the 11 cycles each run decodes, the warm-up included), so all arms together fit 2 h up to about 188 cycles; 170 leaves a 10 % margin for extrapolating from 10 cycles. Fixed for every arm. Above the spec's 120-cycle minimum. |
| Audio replayed | `owsfz/wav/` of the same night (the audio OpenWSFZ captured; the harness's standing input; all 240 cycles present, stamps identical to `wsjt-x/wav/`), scored against the WSJT-X `ALL.TXT` of the same night. Warm-up cycle: the one before the slice (`261115_072915`). |

## How it was picked

- The inventory covered the MS-ON-era 40 m nights on disk: `20261028_2233` (4,069 WAVs), `20261114_2312` (2,833), and the two RESERVED LR-FULL nights `20261118_1954` and `20261119_2204`. The reserved nights were left alone.
- For each of the first two, the 240-cycle contiguous window with the most WSJT-X decodes was found. Results: `20261028_2233` best 8,983 (`261029_021045` to `261029_031030`); `20261114_2312` best 9,431 (`261115_072930` to `261115_082915`).
- The busiest hour is `20261114_2312`'s.
- Script: a per-cycle line count of `ALL.TXT` timestamps; no message text was read out of the function that counts it (HK-037).
