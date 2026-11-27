# PAYLOAD-FIT: are the added decodes that WSJT-X did not confirm real?

**Date:** 2026-11-27 · **Author:** QA · **Asked by:** the Captain, via the Architect (2026-11-27: "keep it, and count the extra decodes"; data on disk only, no new run) · **Status:** a count, no bars. Aggregates only (NFR-021 / HK-037): message text is read inside one function (`pf_oo_check.analyse_slice`) and only counts, repeat flags and SNR numbers leave it.
**Inputs:** the SUB-PROBE runs (`probe_*`) and the PAYLOAD-FIT runs (`pf_*`) of `payload-fit-result.md`, and WSJT-X's own decodes of each slice. Script `qa/decoder-rebuild/pf_oo_check.py`, output `pf_oo_check.json` beside this note.

## Summary

1. **The added decodes WSJT-X did not confirm (ours_only) are 32, 19 and 56 on S40, H40 and H20** (gross: in the PAYLOAD-FIT run and not in the SUB-PROBE run, not matched). 4, 3 and 6 ours_only decodes of the baseline disappeared, so the net is **28, 16 and 50**, the figures the Architect quoted.
2. **They repeat about as often as the decodes WSJT-X did confirm.** The same message at about the same frequency (+-10 Hz) appears in one of the next four cycles in **41 %, 32 % and 59 %** of them, against **40 %, 45 % and 53 %** for the matched extras and **44 %, 51 % and 54 %** for the baseline ours_only decodes. A decode that is not a real transmission does not come back with the same text.
3. **WSJT-X itself decodes the same message in a later cycle** for **38 %, 26 % and 48 %** of them (12 of 32, 5 of 19, 27 of 56): independent evidence from the reference decoder that the station was there; the matched extras give 38 %, 43 % and 48 %.
4. **They are weak:** median SNR **-18.5, -18 and -18 dB** (quartiles -21 to -16, -19 to -16, -19 to -16), against **-15, -10 and -15 dB** for the matched extras and **-17, -18 and -17 dB** for the baseline ours_only decodes. They sit where WSJT-X decodes least, as the baseline ours_only decodes do.
5. **What it does not show:** no decode that does not repeat can be called false (a real station may transmit once, and only 40 to 53 % of the matched extras repeat either); and nothing here proves a single repeating decode is correct. The result is that the added unconfirmed decodes look like the baseline unconfirmed ones, not like noise. H40 has the lowest share (6 of 19) on the smallest number; 6 of 19 against the 45 % of the matched extras is 2.5 fewer repeats than expected.

## 1. The table

Repeat = the same message, within +-10 Hz, in any of the next four cycles (15 to 60 s later) of the PAYLOAD-FIT run's decodes or of WSJT-X's decodes of that cycle. Only decodes with all four following cycles in the replay are evaluated (the last cycles are left out: 0 to 10 per group, shown).

| Slice | Group | decodes | evaluated | repeated | repeat share | of which WSJT-X also saw it | median SNR dB (q1 to q3) |
|---|---|---:|---:|---:|---:|---:|---|
| S40 | **added, not matched (ours_only)** | **32** | 32 | 13 | **40.6 %** | 12 | **-18.5 (-21 to -16)** |
|  | added, matched | 212 | 208 | 83 | 39.9 % | 78 | -15 (-18 to -8) |
|  | baseline ours_only | 272 | 265 | 117 | 44.2 % | 90 | -17 (-19 to -13) |
| H40 | **added, not matched (ours_only)** | **19** | 19 | 6 | **31.6 %** | 5 | **-18 (-19 to -16)** |
|  | added, matched | 91 | 89 | 40 | 44.9 % | 38 | -10 (-17 to +2) |
|  | baseline ours_only | 612 | 602 | 309 | 51.3 % | 249 | -18 (-20 to -17) |
| H20 | **added, not matched (ours_only)** | **56** | 56 | 33 | **58.9 %** | 27 | **-18 (-19 to -16)** |
|  | added, matched | 227 | 223 | 118 | 52.9 % | 106 | -15 (-17 to -13) |
|  | baseline ours_only | 601 | 596 | 323 | 54.2 % | 227 | -17 (-19 to -16) |

Messages that start with "CQ" repeat more often (S40: added ours_only 2 of 5, matched extras 23 of 47; H40: 5 of 8 and 24 of 33; H20: 4 of 9 and 28 of 38); the added ours_only decodes are mostly not CQ messages (27, 11 and 47 of 32, 19 and 56), so the share of the non-CQ ones is the fairer comparison: 11 of 27, 1 of 11 and 29 of 47, against 60 of 161, 16 of 56 and 90 of 185 for the matched extras (37 %, 29 %, 49 %). The numbers are small; H40's 1 of 11 is the one low figure.

## 2. What was decided and how it was built

- **Group definitions:** a decode is one (cycle, message) of the lean's published results, as `dr0_run.py` counts them; *added* = in the PAYLOAD-FIT run and not in the SUB-PROBE run by cycle and message; *matched* = matched to a WSJT-X decode by the harness; the SNR is the decoder's own.
- **Message comparison:** text with single spaces, WSJT-X's trailing decoration tokens (`?`, `aN`) dropped; frequency from each decoder's own field.
- **Consistency check:** added ours_only minus the baseline ours_only that disappeared equals the net change in ours_only (32 - 4 = 28, 19 - 3 = 16, 56 - 6 = 50), and matched added minus matched lost equals the matched change of the main result (212 - 3 = 209, 91 - 4 = 87, 227 - 11 = 216).
- **Not done:** no new run; no check of whether any individual decode's text is correct against the audio (that would need WSJT-X to decode the cycle again or a longer observation of the station).
