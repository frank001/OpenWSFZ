# Result: OWS-REPLAY-CONSISTENCY step 2, the input-difference line, sweep 1 (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-16 19:35Z (`date -u`). **Follows:** the sweep-1 ruling section 4.2.
- **Scope line:** B2BASE sweep 1 only, `sol` (FX-8350), build `338ef61c` shim 20260062, non-default ALSA chain, S6 SEQUENTIAL, standard tier (60 WAVs x 3 trials). Replayed audio, not the station's live operation. No decode-rate claim; nothing about "better" or "worse"; nothing about the Windows station.
- **Method:** `qa/rr-study/s6/ows_input_spread.py` (commit `b5aada12` + one join fix), reusing `archive_xcorr.py`'s own `build_timeline` / `analyse_window`. The played stream of each pass is rebuilt from the corpus audio at that pass's own boundary (`boundary_utc` for the WSJT-X pass, `boundary_utc_o` for the OpenWSFZ pass). Each play's captured window (OpenWSFZ: its cycle-archive WAV; WSJT-X: its save WAV) is cut into 1 s chunks and correlated within +-14 s with the played stream: e = source time - nominal time. **e of a play** = the median over its matched chunks (180 of 180 plays of each appraiser had an offset, median 15 of 15 chunks matched). **Spread of a WAV** = max - min of the e of its 3 trials. The WAVs are split at the median spread (a data-derived cut: descriptive); lower = below it, upper = above it. Own-universe consistency per group from `s6_stats` via `ows_replay_consistency`; the upper - lower difference has an UNPAIRED WAV-clustered bootstrap CI (2,000 resamples; the groups are disjoint WAV sets). 3 unit tests added (offset recovered from a shifted window to within 2 ms; spread/exclusion; split and separation both ways); 12 tests passing with the replay tests.
- **Command:** `ows_input_spread.py --sweep-dir <sweep1> --audio-dir <sweep1-captured-audio> --corpus ~/rr-s6-refset-corpus --wavlist s6-wavlist.json --runs ~/qa-scratch/ows-consistency/sweep1`; 3.6 min wall on `sol`, idle otherwise. No `--filter` applies. Evidence: `qa/rr-study/ows-replay-consistency/sweep1_input_spread.json` (aggregates only).

## The spread of the capture, per appraiser

| appraiser | WAVs with a spread | median spread | p90 | max | min |
|---|---|---|---|---|---|
| OpenWSFZ (cycle archive) | 60 of 60 | **0.520 s** | 1.416 s | 1.586 s | 0.007 s |
| WSJT-X (save WAVs) | 60 of 60 | **0.025 s** | 0.050 s | 0.059 s | 0.002 s |

The same corpus WAV, played three times by the same player, is captured by WSJT-X within about 0.06 s of itself every time, and by OpenWSFZ with its start moving by a median half-second and up to 1.6 s. The mean offset is similar for the two (median play e: OpenWSFZ -0.078 s, WSJT-X -0.109 s), so this is a spread between trials, not a constant lag.

## Does the spread separate the consistent WAVs from the inconsistent ones?

| capture | measure | lower-spread half (n) | upper-spread half (n) | upper - lower [95 % CI] | separates | Spearman rho of spread against the WAV's consistency (n, p) |
|---|---|---|---|---|---|---|
| OpenWSFZ's own (median cut 0.520 s) | A, OpenWSFZ on its own captures | 81.6 % (30) | 63.2 % (30) | **-18.45 pp [-30.40, -5.25]** | **yes** | -0.228 (59, p 0.083) |
| WSJT-X's (median cut 0.0246 s; 6 WAVs equal to the median set aside) | W, OpenWSFZ on WSJT-X's captures | 92.5 % (28) | 87.9 % (26) | -4.62 pp [-8.80, +0.03] | no (CI contains 0) | -0.145 (59, p 0.273) |
| WSJT-X's (same cut) | C_w, WSJT-X's own consistency | 95.1 % (28) | 93.4 % (26) | -1.74 pp [-5.04, +1.48] | no | -0.103 (59, p 0.439) |

- **OpenWSFZ's own captures:** the half of the WAVs whose captures move most between trials is 18.5 pp less consistent than the half whose captures move least, and the CI excludes 0. The rank correlation points the same way (rho -0.23) but does not reach p 0.05 (p 0.083, n 59). The split is a median cut chosen from the data, so this is descriptive.
- **WSJT-X's captures:** the spread there is at most 0.06 s, and it does not separate the WAVs for either program (both CIs contain 0; the OpenWSFZ-on-WSJT-X difference only just: upper limit +0.03 pp).

## Reading, and the limits (HK-021 style, pre-stated)

- The pre-stated reading was: if the spread does not separate them, say so plainly. For OpenWSFZ's own captures it does separate them (CI excludes 0); for WSJT-X's captures it does not.
- This matches X3: OpenWSFZ's captures of one WAV differ from each other in start time by a median of 0.52 s, WSJT-X's by 0.025 s, and OpenWSFZ is 18.8 pp more consistent when decoding WSJT-X's. It does not show that the start-time spread is THE cause: the split is one cut of one sweep, rho is not significant, and other differences between the captures (level, the resampling chain, the framer's realignment) are not measured here.
- **Player jitter cannot explain it:** the same player produced the WSJT-X pass, whose spread is 0.025 s. The play log's `offset_s_o` is the nominal intercept (0.0 for all 180 plays) and is not an actual start time, so the OpenWSFZ pass's own player timing is covered only by that comparison.
- The offset e is one number per play (the median over chunks). Steps inside a window (the framer's -0.25 s realignment, lost or repeated audio) are not separated here; `archive_xcorr.py` already does that per window and was not re-run.
- Sweep 1 only. Sweeps 2-5 not run (the Architect asked for sweep 1, then a decision).

## NFR-021

Aggregates only; the JSON and this report scanned for callsign patterns: none.
