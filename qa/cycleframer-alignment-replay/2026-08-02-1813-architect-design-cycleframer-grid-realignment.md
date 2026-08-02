# Architect — design: re-anchor the cycle window to the UTC grid (the actual drift fix)
# PR #118 fixed the label. This fixes the window. Includes the corrected oracle — without it the same fix passes green again.

**Author:** Architect, 2026-08-02 (18:13 UTC, `date -u`, per HK-017). Repo at `852b1e0`.
**For:** QA, to fold into the dev-task per HK-000/HK-011. **`src/` change — Developer session
required, Captain sign-off before push.** I am not authoring the dev-task (HK-015).
**Origin:** the Captain's own diagnosis this session — *"just use the system clock, it is right
there, it is part of what FT8 specifies."* That is correct, and this note is that idea costed out.

---

## 1. Root cause, stated exactly

`CycleFramer.RunAsync` frames a cycle by **counting samples**: it emits when the buffer reaches
`SamplesPerCycle` (180,000 at 12 kHz). Nothing ever re-anchors that boundary to the UTC 15-second
grid. At a capture device running 48 ppm slow, 180,000 samples take **15.00072 s** of wall clock,
so each window opens 0.72 ms later than the last. Measured in production: **+0.173 s/h**, constant
to ±0.6 ppm across four independent uptime epochs.

PR #118 changed `cycleStart` from `previous + 15 s` arithmetic to `_clock.UtcNow` read at window
open. That made the **timestamp honest** — it now truthfully reports a drifting window. It did not
move the window. The code says so plainly (`CycleFramer.cs:122-134`):

> *"Deliberately NOT floored to the nearest 15-second UTC grid line … the sample buffer itself is
> untouched by this fix (still always exactly SamplesPerCycle samples — no padding, no truncation,
> no carry-over) … resync-every-cycle keeps that residual bounded to a single cycle's worth of
> clock error … so no rate estimation/PLL is needed."*

**The load-bearing error is that last claim.** Re-reading the clock tells you *where you are*; it
does not *move you back*. The per-cycle error is bounded (0.72 ms); the offset from the grid is a
running sum of those and is not bounded. The comment conflates "every measurement is accurate"
with "the error is bounded." Everything else in it is correct — including its instinct that
flooring the *timestamp* alone would be worse, because that would put a false grid label on
genuinely drifted audio.

## 2. Why the buffer, not the label, is the thing to fix

FT8 is defined against UTC: transmissions start at `second % 15 == 0`. A receiver whose window
opens 2 s late is decoding a 2-s-shifted view of a protocol with a fixed time grid. That is not a
bookkeeping problem; it is a signal-alignment problem, and it costs decodes — measured this run at
**−3.8% at 1 s and −29.8% at 2 s** of accumulated offset.

**WSJT-X on the identical device held 100% on-grid for 43.8 h.** Same machine, same USB CODEC,
same NTP discipline. That is empirical proof the approach works on this exact hardware — and note
what it also proves: the two apps are *not* consuming an identical framed stream, or WSJT-X would
have drifted too. Each app frames the shared device stream independently.

## 3. The fix

At each cycle boundary, choose how many samples to consume so the window's audio spans the
wall-clock interval `[G, G+15]`, where `G` is the grid line — then pad or trim to exactly 180,000
for the decoder:

```
G_next      = nearestGridLine(clock.UtcNow)         // NEAREST, not floor
error       = clock.UtcNow - G_next                 // seconds, signed
correction  = clamp(round(error * SampleRate), -MaxCorrection, +MaxCorrection)
consume     = SamplesPerCycle - correction          // ~9 samples at 48 ppm
// emit exactly SamplesPerCycle to the decoder: zero-pad or trim the tail
cycleStart  = G_next                                // now honestly ON the grid
```

Four properties that make this safe:

1. **The correction is tiny.** ~9 samples per cycle at 48 ppm — 0.72 ms. It cannot accumulate,
   because every cycle re-anchors independently.
2. **It lands in dead air.** FT8 occupies 12.64 s of the 15 s window; the remaining ~2.36 s is
   guard. Trimming or padding at the tail is invisible to the decoder.
3. **Nearest, not floor.** Flooring a window that opened 14.9 s late would throw it a full cycle
   backwards. Nearest-grid-line converges from either side.
4. **`MaxCorrection` is the safety valve.** A system-clock *step* — NTP correction, sleep/resume,
   a VM pause — must not discard or duplicate a large block in one cycle. Suggest **250 ms**
   (3,000 samples): a genuine step converges over a few cycles; a 48 ppm crystal never approaches
   the cap.

**Per cycle, not per minute.** The Captain proposed "each minute or so"; per-cycle is both smaller
and simpler. A minute lets ~2.9 ms accumulate and then corrects in one visible jump, and the
correction has to happen at a cycle boundary regardless — so the minute timer buys nothing.

**No PLL, no resampler.** The #118 comment was right that rate estimation is unnecessary. Sample
drop/pad in the guard interval is sufficient precisely because FT8 tolerates sub-millisecond
timing error against 160 ms symbols. Asynchronous sample-rate conversion would be correct and is
overkill.

## 4. ⚠️ The oracle must change, or this fix passes green while still broken

`CycleFramerClockDriftOracleTests.cs:117-131` computes ground truth as

```csharp
double trueOpenSecs = (lastIdx * (double)SamplesPerCycle) / effectiveHz;
DateTime trueOpen   = startUtc.AddSeconds(trueOpenSecs);   // drift-INCLUSIVE
double driftSeconds = (emitted[lastIdx] - trueOpen).TotalSeconds;
```

`trueOpen` already contains the accumulated drift. So the assertion is *"does the reported
timestamp equal when the window actually opened?"* — **label honesty**. After #118 that is
identically zero by construction, because `cycleStart = _clock.UtcNow` is read at window open.
The test cannot fail no matter how far the window has walked.

Its own failure message describes the right property — *"must not let cycle boundaries drift more
than 0.2s from true UTC"* — but the assertion measures a different one. This is HK-022 with the
green number being a passing test.

**Corrected assertion** — measure offset from the grid, not from the drifted open time:

```csharp
// Ground truth is the UTC 15-second grid itself, not where the window happened to open.
DateTime grid   = AlignToCycleStart(emitted[lastIdx]);
double offGrid  = (emitted[lastIdx] - grid).TotalSeconds;
if (offGrid > CycleDurationSecs / 2.0) offGrid -= CycleDurationSecs;   // signed, nearest
Math.Abs(offGrid).Should().BeLessThan(ToleranceSeconds);
```

**This must be RED against current `main`** before the fix lands — that is the regression-oracle
discipline, and the existing test's failure to be red is the whole reason we are here. Expected
red value at 48.4 ppm over 24 h: **~4.1 s** against a 0.2 s tolerance.

Case 2 (dropped-chunk) should be re-checked against the same corrected ground truth; a dropped
chunk shifts the window off-grid permanently and the same blind spot may apply.

## 5. Acceptance bar

Set from this run's measured decode loss, not from taste:

| offset from grid | measured decode loss | verdict |
|---|---:|---|
| < 0.2 s | not measurable | **target** |
| ~1.0 s | −3.8% | tolerable, not acceptable |
| ~2.0 s | −29.8% | failure |

**Bar: `|offset| < 0.2 s` sustained over a simulated 24 h at 48.4 ppm, and over a real
multi-hour run on the FT-991A chain.** Note 0.2 s is the existing `ToleranceSeconds` — it was
always the right number; it was simply measured against the wrong reference.

## 6. Interim mitigation until this ships

At 48 ppm the 2 s cliff arrives at **11.6 h** — which is almost exactly the old ~12 h session cap.
That cap was doing real work, whether or not anyone knew why, and lifting it on the belief that
#118 had fixed the drift is the proximate reason this corpus spent 2,702 cycles in the +2 s regime.

**Reinstate a cap at ~6 h** (1 s, ~4% loss) for the FT-991A chain until the fix lands. See the
corrections note for the record-keeping side of this.

## 7. Cross-references

- `src/OpenWSFZ.Ft8/CycleFramer.cs:118-149` — the resync block and its comment.
- `tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs:117-131` — the oracle to correct.
- `2026-08-02-1714-…-correction-cycle-grid-artefact-voids-8080-anova.md` — how the drift was found.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — reopened by QA.
- `2026-08-02-1813-architect-corrections-to-record-drift-controls-and-my-own-errors.md` — §6's cap.

---

*Per HK-015 this is Architect → QA: the design is mine, the `dev-tasks/` entry is QA's to author.
Per HK-011 this is `src/` and needs a separate Developer session plus Captain sign-off. Per
HK-014/HK-010 committed locally, no push, no merge, and I do not ask for one. Per HK-017 filename
and byline carry real `date -u` UTC. Per HK-018 every figure is measured from the 43.8 h corpus.
Per HK-022 §4 exists because the existing oracle is green against a defect it was written to catch.*
