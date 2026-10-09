# S3c E -2.00: per-cycle capture lag against per-cycle counts (post hoc, descriptive only; the Architect's optional request, ruling 4c)

**From:** QA. **Status:** POST HOC, NOT pre-registered, 12 points, no test, no claim. The question is closed as instrument variation (ruling 4c);
this only records a pattern in data already gathered. `src/`/`native/` untouched.

## Data
E -2.00 (S3c-E50) decodes per early cycle, 8 signals each, from the replay outputs (identical on `cddd7e34` and `766f9cc2`):

| Early cycle | battery 1 | battery 2 | battery 3 |
|---|---:|---:|---:|
| 5 | 3 | 0 | 8 |
| 7 | 0 | 8 | 8 |
| 9 | 8 | 0 | 8 |
| 11 | 6 | 8 | 8 |

Capture lag of the same cycle, by cross-correlating the archived WAVs over samples 20 000 to 160 000 (all batteries play identical source audio).
Convention: positive lag = the content sits LATER in that battery's WAV than in the reference battery 1's, that is, the capture window began
earlier relative to the audio, so less of the early-armed signal's onset is cut. 12 kHz, 1 sample = 0.083 ms. Correlation peak in brackets.

| Early cycle | b2 minus b1 (lag, samples / ms) | b2 count minus b1 count | b3 minus b1 (lag) | b3 count minus b1 count |
|---|---|---:|---|---:|
| 5 | -93 / -7.8 ms (0.893) | -3 | +118 / +9.8 ms (0.562, weak) | +5 |
| 7 | +192 / +16.0 ms (0.893) | +8 | +261 / +21.8 ms (0.998) | +8 |
| 9 | -100 / -8.3 ms (0.894) | -8 | +27 / +2.3 ms (0.894) | 0 |
| 11 | +210 / +17.5 ms (0.972) | +2 | +80 / +6.7 ms (0.894) | +2 |

## What it shows (descriptive)
- Battery 2 against battery 1: the lag and the count change have the SAME SIGN in 4 of 4 cycles (negative lag with fewer decodes in cycles 5 and 9,
  positive lag with more in cycles 7 and 11).
- Battery 3 against battery 1: the lag is positive in 4 of 4 cycles and the count is never lower (+5, +8, 0, +2).
- The lags are small, a few to about 20 ms, against a cut of 1 s or more, and cycle 5's battery 3 estimate is weak (peak 0.56).

## Limits, and one hypothesis
Four cycles per pair, one reference battery, a correlation lag taken over the whole cycle rather than at the signal's onset, and a sign pattern
that four points give by chance 1 time in 16 per pair. It is a pattern, not a result. The hypothesis it suggests (untested, for the Architect): the
decoder's start-time search steps in a coarse grid, and a capture offset of a few to 20 ms moves the edge signals of a whole cycle across a step
together, which would also explain why the cell passes or fails a cycle at a time. No further arm is proposed (ruling 4c: no further arm on this).
