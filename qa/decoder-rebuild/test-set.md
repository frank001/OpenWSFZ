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
| Length used by DR-0 | 240 cycles, unless the §2.3 pilot shortens it (then record it here) |

## How it was picked

- The inventory covered the MS-ON-era 40 m nights on disk: `20261028_2233` (4,069 WAVs), `20261114_2312` (2,833), and the two RESERVED LR-FULL nights `20261118_1954` and `20261119_2204`. The reserved nights were left alone.
- For each of the first two, the 240-cycle contiguous window with the most WSJT-X decodes was found. Results: `20261028_2233` best 8,983 (`261029_021045` to `261029_031030`); `20261114_2312` best 9,431 (`261115_072930` to `261115_082915`).
- The busiest hour is `20261114_2312`'s.
- Script: a per-cycle line count of `ALL.TXT` timestamps; no message text was read out of the function that counts it (HK-037).
