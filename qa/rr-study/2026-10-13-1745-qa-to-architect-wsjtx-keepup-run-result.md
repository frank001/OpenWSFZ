# The 70 min WSJT-X run on `sol`: live WSJT-X was thin on the 0803 night because of the live run, not the audio; and WSJT-X's own keep-up on this CPU (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-13 17:45Z (`date -u` 17:44Z). **Go:** the Captain, in the QA window, 2026-10-13: "start the 70-min run first on the linux test pc."
- **Descriptive, one replicate, not a ruling.** Nothing filed, nothing pushed. Aggregates only (NFR-021, HK-037); working files with message text stay on `sol` in `~/qa-scratch/leg-e-subset/` until job close.

## What ran (HK-022 pins)

| item | value |
|---|---|
| Queue | `queue_leg_e_subset.sh 1` (`qa/refset`, copied to `~/refset-src/…`), detached, started 16:24:45Z, complete 17:43:01Z; 7 blocks done, 0 excluded, orphan check 0 processes |
| Driver / summariser | `run_leg_e.py` SHA-256 `66316f6c…`, `summarize_leg_e.py` `ecd42d33…` (both equal to the committed files) |
| WSJT-X | 2.7.0 built from source on `sol`; executable SHA-256 `2f968b2f…` = the pin; PRECHECK canary decoded; ini `NDepth=3 FT8AP=false Ftol=50 Mode=FT8 SingleDecode=false FastMode=false`; lead 0.0 s |
| Blocks (7 × 40 cycles, 224 scored) | the 4 burst blocks of `20260803_live_run_1713` (`83f94f506343`, `9ebd39e27d03`, `b7ae2a6ac687`, `e66c2a6b2b1b`, all 20 m) and the 3 busiest by live WSJT-X rows per cycle (`9dbe42bc46d9` 40 m, `c6eab9b20b9f` 40 m, `9a4810a87380` 20 m) |
| Method | WSJT-X's own recording of each block played in real time through the codec loopback into a FRESH WSJT-X per block; decodes read from its UDP messages; compared with the station's live WSJT-X `ALL.TXT` and with OpenWSFZ leg B of the first run (`76aa48cd` + override, budget unlimited, `.so` `dc517dc9…`) |
| Files | `qa/rr-study/results/2026-10-13-wsjtx-keepup-run-sol/` (`SUMMARY-rep1.json`, `compare-rep1.json`, `QUEUE-STATUS.txt`); script `qa/rr-study/refset/harness/leg_e_subset_compare.py` (`qa/refset` `bfb6e0aa`, local) |

## Result 1: the 0803 night. Replaying the SAME WSJT-X on the SAME audio finds about twice what live WSJT-X reported

Non-hashed rows, scored cycles, sm_01 key (LIVE = the station's WSJT-X; E = WSJT-X 2.7.0 replayed on `sol`; B = OpenWSFZ leg B):

| set of blocks | LIVE rows | E rows | B rows | live rows E reproduces | live rows B reproduces | B-only against LIVE | B-only against E |
|---|---|---|---|---|---|---|---|
| **the 4 blocks of `20260803_live_run_1713`** | 879 | **1,966** | 1,605 | 91–96 % per block | 73–78 % per block | **927** | **52** |
| the 3 busiest blocks (other nights) | 3,588 | 3,370 | 2,373 | 89–94 % per block | 59–70 % per block | 7 | 99 |

Per block (rows per cycle, LIVE / E / B): `83f94f…` 13.5 / 28.3 / 22.8; `9ebd39…` 8.5 / 20.5 / 17.2; `b7ae2a…` 3.0 / 5.8 / 4.6; `e66c2a…` 2.5 / 6.8 / 5.6; `9dbe42…` 39.2 / 35.4 / 27.6; `c6eab9…` 38.3 / 36.4 / 26.2; `9a4810…` 34.6 / 33.6 / 20.3.

**Reading.** On the 0803 night the OpenWSFZ "extras" (972 OWS-only rows against live WSJT-X, 927 of them in these four blocks) are **not extras against WSJT-X as such**: a WSJT-X 2.7.0 replay decodes about 2.2 times what the live WSJT-X logged, and OpenWSFZ has only **52** rows (3.2 % of its 1,605) that the replay does not also have. So **the thin live log was a property of that live run (its WSJT-X settings, depth or load that night, none recorded), not of the audio and not of WSJT-X's algorithm.** The cause inside the live run is still **not shown**. On the three busy blocks of other nights the replay and the live log agree (E-only 70 rows of 3,370) and OpenWSFZ reproduces 59 to 72 % of the replay's rows, i.e. the 74 % leg-B reading of the first run is the real decoder difference, not an artefact.

This changes how the first run's figures are best cited: the matched share against **live** WSJT-X (74.0 %) and the OWS-only count (972, or 44 without the 0803 night) stand as ruled; this run adds that **against a WSJT-X replay the 0803 OWS-only rows nearly vanish (52)**.

## Result 2: does WSJT-X keep up on this CPU? (one FX-8350, one decode process)

| measure (224 scored cycles) | value |
|---|---|
| WSJT-X decode busy span, median / P90 / max | 4.9 s / 6.4 s / 14.7 s |
| arrival of the cycle's LAST decode after the boundary, median / P90 / max | 15.4 s / 17.1 s / 29.0 s |
| cycles whose last decode came more than 17 s after the boundary ("late") | **11.2 %** [2.2, 21.0] (7 blocks, block-clustered) |
| late share by live row count ≤ 10 / 11–20 / 21–30 / > 30 | 1.1 % (92 cycles) / 0 % (36) / 0 % (2) / **25.5 %** (94) |
| OpenWSFZ leg B whole-decode compute time (a file replay, budget unlimited), median / P90 / max | 25.8 s / 36.5 s / 50.6 s; above 15 s in 72 % of cycles |
| decodes: replay against live, all 224 cycles | 5,835 against 4,869 (median 2 more per cycle) |

WSJT-X itself is on time in quiet cycles and runs past two seconds into the next slot in a quarter of the busiest cycles on this CPU (worst 29 s). The two timings are **not the same quantity** (WSJT-X: real-time decoding of played audio; OpenWSFZ: compute time of a file replay with no deadline) and are shown side by side only to place the old-CPU question. The DT of the replay reads 0.1 s above live (median; lead 0.0 s).

## What this does not show

1. Why the live WSJT-X was thin on 0803: its settings, depth and load on that night are not recorded (the source run's own provenance: one 20 m session, build `1ff4293` with uncommitted changes).
2. One replicate; a replay of WSJT-X's own recording, not a second live run; WSJT-X 2.7.0 built by QA (NDepth 3), not the station's installation.
3. The three busy blocks are chosen as the busiest, so their agreement says nothing about quiet bands. Seven blocks of two bands; 17 m and 80 m are absent.
4. No keep-up claim about the station PC, or about OpenWSFZ's live path (its deadline stops the residual pass; only the replay's compute time is shown).

## For your ruling

1. Whether the 0803 reading above may replace "WSJT-X live decode thin, cause unknown" by "**thin live decode, not the audio**: a WSJT-X replay on the same audio finds 2.2 times the rows (cause inside the live run unknown)" in the citation guard for the OWS-only count.
2. Whether the keep-up figures (late share 11.2 %, 25.5 % of the busiest cycles) are wanted as a standing row of the S6 / reference-set report or stay a one-off.
3. The old-CPU profile (your step 0) is next on `sol`, with the Captain's go in my window; `perf` is installed.
