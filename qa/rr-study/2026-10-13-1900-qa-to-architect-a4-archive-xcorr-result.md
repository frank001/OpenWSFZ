# A4: the daemon's own cycle archive shows audio was LOST, in gaps of 7.15, 6.97 and 9.95 s, each inside an abandoned residual pass (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-13 19:00Z (`date -u` 18:58Z). **Go:** the Captain, in the QA window, 2026-10-13: "go".
- **Descriptive, from files the dry run already wrote; nothing was run on `sol` except this read-only analysis.** Tool `qa/rr-study/s6/archive_xcorr.py` (6 synthetic tests; `qa/refset` `a158bfe1` and its successors, local). Data: `qa/rr-study/results/2026-10-13-live-path-A4-archive-xcorr/a4-dryrun.json` (offsets and peaks only; no text). Label: the dry run's, `subtractionMaxThreads 8` (station value, not auto), WSJT-X decoding on the same CPUs, S6 quick tier, attempt 2.

## Method (HK-027: what the instrument already records)

The daemon's cycle archive holds every window it framed (180,000 samples at 12 kHz, labelled with its slot). The played stream is known exactly (play log plus the WSJT-X-side WAVs on the wall clock). Each window is cut into 15 chunks of 1 s; each chunk is correlated (normalised, FFT) with the played stream within ±14 s of its nominal time; the best lag gives the chunk's **source time**, and `e = source time − nominal time` (healthy: −0.115 s, the chain's own delay). A jump of `e` between consecutive chunks is a discontinuity in the sample stream: **positive = source audio skipped (lost), negative = repeated**. Match threshold: normalised peak ≥ 0.30 (a design number; matched chunks read 0.9 to 1.0; idle and silent stretches do not match and break the step chain). Steps with exactly ±15.000 s (identical WAV in adjacent slots) are ambiguity and excluded.

## Result 1: audio was lost, three times

| episode | window | step inside the window | where | abandoned residual pass (UTC start–end, elapsed, fits) | gap ÷ pass |
|---|---|---|---|---|---|
| 1 | 18:09:30 | **+7.149 s** (e −0.115 → +7.034), chunk 3 (18:09:33) | peaks 0.63 / 0.99 | 18:09:30.76 – 18:09:41.00, 10,242 ms, 11 fits | pass − gap = 3.09 s |
| 2 | 18:16:45 | **+6.974 s** (e +0.020 → +6.994), chunk 3 (18:16:48) | peaks 0.88 / 0.92 | 18:16:45.96 – 18:16:56.00, 10,043 ms, 12 fits | 3.07 s |
| 3 | 18:23:30 | **+9.947 s** (e +0.354 → +10.301), chunk 3 (18:23:33) | peaks 0.62 / 0.93 | 18:23:31.70 – 18:23:43.00, 11,296 ms, 11 fits | 1.35 s |

- **Each gap starts 1.3 to 2.2 s after the start of an abandoned residual pass and is inside it; its length is the pass's length minus 3.1 s (twice) or 1.35 s (once).** That is what a stalled reader looks like: roughly the first 1.4 to 3 s of the stall is absorbed by buffering (the 64 KiB pipe is about 1.4 s; the bounded channel about 2.7 s), the rest is lost.
- **Not a lag:** a delay that is only buffered would be drained and the offset would fall by seconds in a cycle; here the content is **contiguous after each gap** and `e` falls only by the framer's 0.25 s per window.
- The window labelled 18:09:30 closed 7.22 s late, 18:16:45 7.03 s, 18:23:30 10.32 s (the manifest's `window_closed_utc`): the same numbers as the steps, so **the manifest's close lag alone already measures the loss**.
- Where in the chain the samples vanish (`arecord` overrun, the bounded channel, the framer) is **not shown** by this instrument; A1/C2 do that.

## Result 2: what the framer does afterwards (visible as steps at window boundaries)

| phase | what the archive shows |
|---|---|
| positive crawl (episodes 1 and 2) | each window starts 0.25 s EARLIER in the source than the previous one ended: **0.25 s of audio is repeated per window** (51 steps of −0.25 s counted); no audio lost |
| after episode 3 | the label jumps 30 s (window 18:23:45 is never framed); the content of 18:24:00 starts at source 18:23:55.05, contiguous with the end of 18:23:30's content (18:23:55.3): **no further loss; the negative error is a label jump** |
| negative crawl (18:24:15 to 18:27:45) | each window starts 0.25 s LATER in the source (+0.250 s steps, 14 of them): **0.25 s of audio is deliberately DISCARDED per window, about 3.5 s in all** |
| end of the negative crawl, 18:27:30 chunk 9 | one step of +1.393 s: the remaining error applied in one go (the clamp's last correction, wanted −1.341 s) |

## Result 3: how decoding returns as the window error shrinks (windows with a constant offset)

| \|window close lag\| (s) | windows | OpenWSFZ rows | WSJT-X rows in the same slots | share |
|---|---|---|---|---|
| < 0.5 | 3 | 33 | 59 | 56 % |
| 0.5 to 1.0 | 4 | 40 | 55 | 73 % |
| 1.0 to 1.5 | 7 | 66 | 112 | 59 % |
| 1.5 to 2.0 | 5 | 47 | 115 | 41 % |
| 2.0 to 3.0 | 9 | 25 | 131 | 19 % |
| > 3.0 | 35 | 3 | 775 | 0 % |

Decoding is normal (56 to 73 %, in line with the 65 % read earlier) below 1.5 s of misalignment, halves by 2 s, and is gone above 3 s. This is the curve behind "blind for about 28 cycles" and it bears on C1: **a window more than about 2 s out is worth nothing, so the resync should not wait for 28 cycles of 0.25 s**; and it is evidence for the 1.000 s resync threshold (above it, decoding already falls).

## Two corrections to what I told you earlier

1. **`dropped_before` in the archive manifest is not a capture-drop counter.** It counts cycles dropped because the ARCHIVE writer's own queue was full (`CycleArchiveService.cs:77-78, 234-249`). It reads 0 for all 81 windows and says nothing about lost audio or `arecord`. I had pointed at it as a possible signal; it is not.
2. The "validity of the healthy reference" in the tool's header (`e_median` etc.) is built from the first six windows including idle ones and is not meaningful; the healthy offset is read from the first matched chunks (−0.115 to −0.134 s, the chain's delay), as in Result 1.

## Limits

One run (attempt 2), 81 windows, three losses; the third is the largest (9.95 s) and its pass the longest (11.3 s). Windows in idle slots between batches cannot be matched. The correlation threshold 0.30 is a design number (matched chunks read ≥ 0.6, mostly > 0.9; unmatched stretches are noise or silence). This shows WHAT was lost and WHEN, not WHERE in the capture chain, and says nothing about the default thread count.

## For the reading rule

- **M1/M2 versus M3 gets a new observable that needs no wrapper:** the loss starts 1.3 to 2.2 s after the pass starts and ends about when the pass ends. That is the signature of the reader being starved during the pass, not of a downstream drop that is independent of the pass.
- A1's `arecord` log and A2's counters remain needed to separate pool starvation from CPU contention (D2, D1, D3).
- A4 can be run on every arm's archive as a second, independent measure of lost audio (size and time), at a few minutes per arm; I propose adding it to Part B's rows.
