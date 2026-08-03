# Dev-task — CycleFramer clock drift is still present after PR #118
# The fix must MOVE the window every cycle, not merely re-measure where it drifted to.

**Author:** QA, 2026-08-02 (17:40 UTC). **Revised 2026-08-03 (14:35 UTC, `date -u`, HK-017), repo
at `5ba1f56`** — the original framed this as open investigation; the cause is now established and
a costed design exists. Filename retained at the 08-02 reopen date because four documents and
project memory cross-reference it by name.
**For:** a separate Developer-persona session (HK-011 — `src/` work, must not run in the QA session
that found the recurrence).
**Origin:** `qa/cycleframer-alignment-replay/2026-08-02-1714-architect-to-qa-correction-cycle-grid-
artefact-voids-8080-anova.md`; design in `…-2026-08-02-1813-architect-design-cycleframer-grid-
realignment.md`; reopens `DEFECT-capture-clock-drift-silent-decode-loss.md`.

> ### ⚠️ The one sentence that matters
> **Re-reading the clock tells you *where you are*; it does not *move you back*.** PR #118 re-read
> the clock every cycle and the window still drifts at 48.0 ppm. A fix that re-measures, or that
> re-labels, and does not change **which samples land in the window**, is the same defect again.
> §4 exists to make that failure mode impossible to ship green.

---

## 1. Root cause — established, not hypothesised

`CycleFramer.RunAsync` frames a cycle by **counting samples**: it emits when `filled ==
SamplesPerCycle` (180,000 at 12 kHz, `CycleFramer.cs:151-174`). Nothing re-anchors that boundary to
the UTC 15-second grid. On a capture device running 48 ppm slow, 180,000 samples take **15.00072 s**
of wall clock, so each window opens 0.72 ms later than the last. Measured in production: **+0.173
s/h**, constant to ±0.6 ppm across four independent uptime epochs.

PR #118 changed `cycleStart` from `previous + 15 s` arithmetic to `_clock.UtcNow` read at window
open (`CycleFramer.cs:135`). That made the **timestamp honest** — it now truthfully reports a
drifting window. It did not move the window, and the code says so plainly at
`CycleFramer.cs:123-134`:

> *"Deliberately NOT floored to the nearest 15-second UTC grid line … the sample buffer itself is
> untouched by this fix (still always exactly SamplesPerCycle samples — no padding, no truncation,
> no carry-over) … resync-every-cycle keeps that residual bounded to a single cycle's worth of
> clock error … so no rate estimation/PLL is needed."*

**The load-bearing error is that last claim.** The *per-cycle* error is bounded at 0.72 ms. The
*offset from the grid* is the running sum of those, and it is unbounded. The comment conflates
"every measurement is accurate" with "the error is bounded." Everything else in it is correct —
including its instinct that flooring the *timestamp* alone would be worse, since that would put a
false grid label on genuinely drifted audio. **Keep that instinct; it is the trap in §4.2.**

This is settled. Do not spend a session re-deriving it. What is open is the implementation and its
oracle.

## 2. What it costs — read this before sizing the work

FT8 is defined against UTC: transmissions start at `second % 15 == 0`. A receiver whose window
opens 2 s late is decoding a 2-s-shifted view of a protocol with a fixed time grid. Measured on the
43.6 h 07-31 corpus (8080 vs. the paired 8081 instance, pooled over three restart segments):

| uptime | accumulated drift | 8080/8081 decode ratio | |
|---:|---:|---:|---|
| 0–5 h | 0–0.86 s | 0.93–0.97 | flat, healthy |
| 6–11 h | 1.04–1.90 s | 0.95 → 0.81 | gradual decline |
| **12 h** | **2.07 s** | **0.713** | **cliff begins** |
| 13 h | 2.25 s | 0.426 | |
| 14 h | 2.42 s | **0.254** | past FT8's ~2.36 s guard interval |

**Past ~13.7 h uptime this daemon decodes at ~25% of an identical reference instance, silently,
with every health signal green.** Additionally, 65% of the 07-31 corpus is unusable for paired
analysis because the window had walked off-grid. A ~6 h session cap on the FT-991A chain is in
force as interim mitigation until this lands.

⚠️ **This defect and `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` are ONE
defect, not two.** That dev-task's "root cause not yet known" is answered here; this fix closes
both. Every candidate it ruled out is consistent with drift: power-cycling the radio didn't help
(software, not RF), a process restart cleared it completely (resets accumulated drift to zero),
and 8081 was unaffected throughout (4.7 ppm reaches 2 s at ~118 h; the run was 43.5 h).

**WSJT-X on the identical device held 100% on-grid for 43.8 h** — same machine, same USB CODEC,
same NTP discipline. The approach is proven on this exact hardware.

## 3. The fix — per-cycle sample-level realignment

Architect's design, `…-1813-architect-design-cycleframer-grid-realignment.md` §3. At each cycle
boundary, choose **how many samples to consume** so the window's audio spans the wall-clock
interval `[G, G+15]`, then pad or trim to exactly 180,000 for the decoder:

```
G_next      = nearestGridLine(clock.UtcNow)         // NEAREST, not floor
error       = clock.UtcNow - G_next                 // seconds, signed
correction  = clamp(round(error * SampleRate), -MaxCorrection, +MaxCorrection)
consume     = SamplesPerCycle - correction          // ~9 samples at 48 ppm
// emit exactly SamplesPerCycle to the decoder: zero-pad or trim the tail
cycleStart  = G_next                                // now honestly ON the grid
```

**`consume` is the fix.** `cycleStart = G_next` is bookkeeping that becomes *true* only because
`consume` moved the window. If `consume` is not varying cycle-to-cycle on a drifting device, the
fix is not implemented — whatever the timestamps say.

Four properties that make this safe:

1. **The correction is tiny** — ~9 samples (0.72 ms) per cycle at 48 ppm. It cannot accumulate,
   because every cycle re-anchors independently against the grid rather than against its
   predecessor.
2. **It lands in dead air.** FT8 occupies 12.64 s of the 15 s window; the remaining ~2.36 s is
   guard. Trimming or padding at the tail is invisible to the decoder.
3. **Nearest, not floor.** Flooring a window that opened 14.9 s late would throw it a full cycle
   backwards. Nearest-grid-line converges from either side.
4. **`MaxCorrection` is the safety valve.** A system-clock *step* — NTP correction, sleep/resume, a
   VM pause — must not discard or duplicate a large block in one cycle. Suggested **250 ms**
   (3,000 samples): a genuine step converges over a few cycles; a 48 ppm crystal never approaches
   the cap. Extract as a named constant alongside `SamplesPerCycle`, not a literal.

**Per cycle, not per minute.** A minute lets ~2.9 ms accumulate and corrects it in one visible
jump, and the correction has to happen at a cycle boundary regardless — the timer buys nothing.

**No PLL, no resampler.** The #118 comment was right that rate estimation is unnecessary: sample
drop/pad in the guard interval suffices because FT8 tolerates sub-millisecond timing error against
160 ms symbols. Asynchronous sample-rate conversion would be correct and is overkill.

**Preserve two existing behaviours while you are in `RunAsync`:**
- The **lazy** resync point (`CycleFramer.cs:118`, `needsResync`) is deliberate — the clock must be
  read when the next window's first real sample arrives, not when the previous window closed, or a
  dropped chunk's gap is invisible. Realign at that same point; do not move it earlier.
- `windowDialFreq` (`CycleFramer.cs:146`) must stay snapshotted at the identical instant as
  `cycleStart` — see `dev-tasks/2026-07-31-fix-cycleframer-dial-freq-lazy-resync-consistency.md`.

## 4. ⚠️ The oracle — the existing one passes green against this defect by construction

### 4.1 Why the current test cannot fail

`CycleFramerClockDriftOracleTests.cs:120-124` computes ground truth as:

```csharp
double trueOpenSecs = (lastIdx * (double)SamplesPerCycle) / effectiveHz;
DateTime trueOpen   = startUtc.AddSeconds(trueOpenSecs);   // drift-INCLUSIVE
double driftSeconds = (emitted[lastIdx] - trueOpen).TotalSeconds;
```

`trueOpen` already contains the accumulated drift. The assertion therefore asks *"does the reported
timestamp equal when the window actually opened?"* — **label honesty**. After #118 that is
identically zero by construction, since `cycleStart = _clock.UtcNow` is read at window open. The
test cannot fail no matter how far the window has walked. Its failure message describes the right
property; the assertion measures a different one. This is HK-022 with the green number being a
passing test.

### 4.2 ⚠️ The corrected assertion is NECESSARY BUT NOT SUFFICIENT — read this before writing it

The design's §4 proposes measuring the emitted timestamp's offset from the grid:

```csharp
DateTime grid   = AlignToCycleStart(emitted[lastIdx]);
double offGrid  = (emitted[lastIdx] - grid).TotalSeconds;
if (offGrid > CycleDurationSecs / 2.0) offGrid -= CycleDurationSecs;   // signed, nearest
Math.Abs(offGrid).Should().BeLessThan(ToleranceSeconds);
```

That is correct and required — **and on its own it is defeatable.** §3 sets `cycleStart = G_next`,
so after the fix the emitted timestamp sits on the grid *by assignment*. An implementation that
snaps the label and never touches `consume` passes this assertion with `offGrid == 0` while the
audio is exactly as misaligned as it is today — and it would be **worse than the status quo**,
because the label would now lie. That is precisely the failure §1's own comment warned against.

**So the oracle must also assert on the audio.** The falsifiable property is sample consumption: to
hold a 15 s wall-clock window on a source running at `effectiveHz`, the framer must consume
`effectiveHz × 15` source samples per cycle, **not** `SamplesPerCycle`. Over N cycles:

| | expected cumulative source samples consumed after N cycles |
|---|---|
| broken (today, and label-snap) | `N × 180_000` |
| fixed | `≈ effectiveHz × 15 × N` (at 48 ppm slow: `N × 179_991`, a divergence of ~9 samples/cycle) |

Assert cumulative consumption tracks wall-clock elapsed × `effectiveHz` to within `MaxCorrection`.
A label-only fix, a label-snap fix, and current `main` all fail this. Only a fix that actually moves
the window passes it. **This assertion is the Captain's requirement made mechanical (HK-021): it is
a hard threshold, evaluated in code, that no re-measuring implementation can satisfy.**

### 4.3 Discipline

1. **Both assertions must be RED against current `main` before the fix lands.** Expected red value
   for the grid-offset assertion at 48.4 ppm over 24 h: **~4.1 s** against a 0.2 s tolerance. If
   either is green on unfixed `main`, the test is wrong — stop and re-derive it. The existing
   test's failure to be red is the entire reason we are here.
2. **Do not relax the 0.2 s tolerance.** ⚠️ Note carefully: the number was always right — it is the
   **reference** it was measured against that was wrong. You *must* change what the assertion
   compares to (§4.2); you must *not* change the threshold. If the real fix cannot hit 0.2 s, stop
   and raise it with QA/Architect rather than loosening the criterion unilaterally.
3. **Re-check Case 2** (`RunAsync_DroppedChunkMidStream_…`) against the same corrected ground truth
   — a dropped chunk shifts the window off-grid permanently and the same blind spot may apply.
4. **Add a restart-punctuated multi-epoch case.** Drift accumulates for N hours, process restarts,
   repeats — that is the observed live failure shape, and a single-epoch design cannot distinguish
   "bounded forever" from "bounded until the next restart happened to arrive first." This is
   supplementary to §4.2, not a substitute for it.
5. **Add a clock-step case** exercising `MaxCorrection`: inject an NTP-sized step and assert no
   single cycle discards or duplicates more than the clamp, and that the window reconverges.

## 5. Acceptance bar

Set from measured decode loss, not from taste:

| offset from grid | measured decode loss | verdict |
|---|---:|---|
| < 0.2 s | not measurable | **target** |
| ~1.0 s | −3.8% | tolerable, not acceptable |
| ~2.0 s | −29.8% | failure |

**Bar: `|offset| < 0.2 s` sustained over a simulated 24 h at 48.4 ppm — with §4.2's consumption
assertion also green — and over a real multi-hour run on the FT-991A chain.**

## 6. Evidence available

- `…-2026-08-02-1813-architect-design-cycleframer-grid-realignment.md` — **the design. Read first.**
- `…-2026-08-02-1714-architect-to-qa-correction-cycle-grid-artefact-voids-8080-anova.md` §2 — the
  grid/sawtooth mechanism, per-hour offset table, three restart-aligned resets, and §2.3's DT/SNR-
  vs-offset table (each second of label drift costs ~10 dB reported SNR, moves DT ~0.9 s).
- `…-2026-08-02-2316-architect-to-qa-handoff-t1-closed-and-corrected-scope.md` §T9 — the decode-
  ratio-vs-drift cliff in §2 above, and the identification with the 8080 collapse dev-task.
- `qa/endurance/2026-08-02-multiday-20m-anova/table_c_drift_stratified_decode_ratio.md` — decode
  cost corrected for a same-instant reference. Note it is a **threshold, not a gradient**: flat to
  ~+1 s, then a cliff. A linear degradation model would not match what was measured.
- `artefacts/20260731_live_run_2004-8080/` (git-ignored, NFR-021) — ALL.TXT, 5 log files spanning
  the 3 restarts, and cycle-audio-archive WAVs, if offline reproduction against real captured audio
  is wanted. See `qa/ARTEFACT_INVENTORY.md` before concluding anything is missing (HK-018).
- `src/OpenWSFZ.Ft8/CycleFramer.cs:111-174` and
  `tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs` — read both in full first.

## 7. Boundaries (do not deviate)

- Per **HK-011**: `src/` implementation. Local build/tests only. **Show findings and the diff to the
  Captain for sign-off before `git push`** — not merely before merge.
- Per **HK-006**: do **not** run `python3 tools/pre_merge_check.py` as part of this task or put it
  in any checklist — Captain's trigger only, at merge time.
- Per **HK-010**: merge to `main` needs the Captain's explicit sign-off regardless of green CI.
- **If the investigation contradicts §1** — i.e. the live code path differs from what is described
  here — **stop and escalate to QA/Architect** rather than proceeding on the design. §1 is read off
  the source, but the source is not the running binary.
- If the fix turns out to require rethinking the framer's whole timing model rather than a targeted
  change, **stop and escalate** rather than expanding scope unilaterally.

## 8. Traceability

- `DEFECT-capture-clock-drift-silent-decode-loss.md` — reopened 2026-08-02, full history.
- `dev-tasks/2026-07-31-fix-cycleframer-clock-drift-boundary-resync.md` — the PR #118 task this
  follows up; its "What to build" carries the original design intent.
- `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` — **the same defect** (§2). This
  fix closes it; it should be archived against this work, not investigated separately.
- `dev-tasks/2026-07-31-fix-cycleframer-dial-freq-lazy-resync-consistency.md` — the `windowDialFreq`
  invariant that must survive this change (§3).
- `project-state-2026-07-31-d001-competition-confirmed.md` (QA memory) — carries the reopening;
  needs a final correction once this task's outcome is known.
