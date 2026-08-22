# Architect -> QA: the DT collapse has a named mechanism -- spec for arms B-dt-C1 and B-dt-C2

**From:** Architect
**To:** QA
**Date:** 2026-08-22 14:11Z
**Branch at drafting:** `feat/r2-coherent-llr-phase-b`, HEAD `d44ffea`
**Status:** SPEC. Nothing here is a Developer session, a push, or a merge.

---

## 0. Read this first

Three things, in order of how much they change what you do:

1. **The `true_dt == 0` SNR collapse has a candidate mechanism, and it is a two-line
   indexing defect in our own shim** -- not in ft8_lib, not in the synth, not in the
   audio path. Section 1. It is a code fact plus a hypothesis; the hypothesis is what
   these two arms test.
2. **AC-N5's headline number needs a correction that only QA can make** (HK-015 -- the
   report is yours). Its `-6.01 dB` is confounded with scenario and is not the live
   collapse. Section 2. This is measured from the committed JSON, not argued.
3. **The obvious arm -- re-stratify the existing corpora by the sign of `reported_dt` --
   is DEAD, and I am withdrawing it before you spend time on it.** In every corpus on
   disk the two stratifiers are *perfectly collinear*, so that arm would return the same
   number under either label and both branches would land on the same row. That is an
   HK-021(k) diagnostic, and you would have been entitled to refuse it under HK-025.
   I caught it while drafting, which is what the drafting discipline is for. Section 3
   shows the 2x2 so you can re-check it in a minute rather than take my word for it.

What replaces it is two arms that *can* separate the two stratifiers: one offline and
cheap (Section 4), one live and short (Section 5).

---

## 1. The mechanism

### 1.1 The code

`src/OpenWSFZ.Ft8/Native/ft8_shim.c:1491-1498`, inside the `signal_db` block:

```c
int b0 = (int)cand->time_offset; if (b0 < 0) b0 = 0;   /* 1491 */
int b1 = b0 + FT8_NN;                                   /* 1492 */
...
int tone_col = (int)tones[b - b0];                      /* 1498 */
```

ft8_lib's own convention, which our estimator is supposed to be mirroring, is at
`native/ft8_lib_build/patched/ft8/decode.c:160` and `:226`:

```c
int block_abs = candidate->time_offset + block; // relative to the captured signal
if (block_abs < 0)
    continue;
```

ft8_lib **skips** out-of-range blocks and never re-anchors the symbol index. Our shim does
the opposite: it clamps `b0` to zero **and then derives the symbol index from the clamped
value**. When `cand->time_offset < 0`, block `b` is scored against `tones[b]` while the
symbol actually present there is `tones[b - time_offset]`. Every one of the 79 symbols is
read from the wrong tone bin, shifted by `|time_offset|`. `cnt` still reaches 79, so the
average is not thinned by missing samples -- it is corrupted by wrong ones.

Negative offsets are ordinary, not exotic: `decode.c:290` searches
`candidate.time_offset` over **-10 .. +19**.

### 1.2 Why this fits everything already measured

- **`local_noise_db` cannot move under this mechanism.**
  `compute_local_noise_floor_db` (`ft8_shim.c:1023`) sweeps `for (b = 0; b < num_blocks)`
  and is passed no time argument at all. It is structurally incapable of responding to a
  symbol-index shift. AC-N5 measured **+0.23 dB**. The agreement is not a coincidence --
  but note it is also *weak* evidence, because almost any signal-side mechanism predicts
  the same thing. Do not over-weight it.
- **The trigger should be the sign of `time_offset`, not the value of `true_dt`.**
  B-dt-A's own S3 profile: part 0, `reported_dt = -0.200 s`, error **-15.67 dB**; parts
  1-9, `reported_dt >= +0.167 s`, error **+1.0 .. +2.0 dB**. A step at the sign change.
- **`reported_dt < 0` is an EXACT proxy for `time_offset < 0`.** Derived, not assumed:
  `dt = (time_offset + time_sub/time_osr) * symbol_period` with `time_osr = 2`,
  `symbol_period = 0.16 s`. So `time_offset <= -1` implies `dt <= (-1 + 0.5) * 0.16 =
  -0.08 s`, and `time_offset >= 0` implies `dt >= 0`. **`dt` can never land in
  `(-0.08, 0)`** -- there is a gap either side of the boundary, so the sign survives both
  the 0.1 s print quantum in `ALL.TXT` and any averaging over trials.
- **The magnitude is consistent.** Working back from the live numbers with
  `snr = signal_db - local_noise_db - 26.5`: correct `signal_db ~ -9.0`, collapsed
  `~ -24.7`, i.e. the wrong-bin reads still sit ~11 dB above the local noise floor. That
  is what adjacent-bin leakage of a Gaussian-shaped FT8 tone should look like. Consistent,
  not proof.
- **It explains why B1 moved it +0.229 dB and no further.** B1 changed where the origin
  *is*. It did not change what this estimator does once a candidate lands left of it.
- **It explains why AC-N5 could not reproduce the collapse offline.** Offline PCM is placed
  at `dt = 0` in a 180,000-sample buffer with no playback/capture offset, so `time_offset`
  should be `>= 0` and the clamp never fires. **This is the prediction TASK 1 tests.**

### 1.3 What is NOT claimed

- Not claimed: that this is the *only* contributor. It is a sufficient mechanism for a
  large deficit; whether it accounts for all 15.7 dB is not established by either arm here.
- Not claimed: anything about `dt_s > 2.1` or about decode *rate* at negative DT. Those
  remain unmeasured (HK-026) and S3b remains unrun.
- Not claimed: that the fix is safe to write. That is a `src/` change, HK-011, and the
  Captain's session to open -- not mine to start and not yours to apply.

---

## 2. RECORD CORRECTION -- AC-N5 section 5.2 (QA owns this edit)

I re-analysed the committed `qa/rr-study/r2-coherent-llr-instrument/results/ac_n5_report.json`.
Mechanical, re-checkable, no new run. Grouping the 85 matched rows by scenario as well as
by `true_dt`:

| cell | n | mean `signal_db` |
|---|---|---|
| S3, `true_dt == 0` | 3 | **-7.58** |
| S3, `true_dt > 0` | 21 | **-7.99** |
| S8, `true_dt == 0` | 56 | -14.94 |
| S8, `true_dt > 0` | 5 | -10.90 |

**The stratifier is very nearly collinear with scenario:** 56 of 59 `dt=0` rows are S8,
21 of 26 `dt>0` rows are S3. The pooled `-6.01 dB` is therefore largely an S8-vs-S3 level
contrast wearing a `dt` label. Section 5.3 named the asymmetry as an artefact of
construction; it is stronger than that -- it is a confound, and it is load-bearing for the
headline.

**And within S3 -- the one place where `snr_db: 0` is fixed across all parts
(`qa/rr-study/scenarios/s3-dt-offset.json`, `fixed.snr_db = 0`) and only `dt` varies --
`true_dt = 0` shows no deficit at all**: reported SNR `+2.0` at part 0 against `+0.67 ..
+2.0` across parts 1-7. Compare the live arm at that same cell: **-15.67 dB**. The
phenomenon did not reproduce offline.

**What I am asking you to do with that** (yours to write, mine to state -- HK-015):

1. Edit `qa/rr-study/2026-08-22-1349-qa-to-architect-amendment2-ac-n1-n5-results.md`
   section 5.2 in place, not by annotation, to name the scenario confound and to withdraw
   `-6.01 dB` as a measure of the collapse. The honest statement of what AC-N5 established
   is: *`local_noise_db` does not move; `signal_db` is where any dt-dependence must live,
   by construction of the formula; the size of the live collapse is NOT what this
   measurement returned.*
2. Correct the board's own one-liner the same way, in the same edit (HK-024).
3. **AC-N2/N3/N4 are untouched by this.** The three gates stand, the getter is good, and
   its acceptance is not reopened. Only the reported, ungated AC-N5 reading changes.
4. The non-reproduction is not a defect in your harness. It is a *finding*, and TASK 1
   turns it into the arm's main evidence.

---

## 3. Why the offline re-stratification arm is dead (measured, so you can re-check it)

Over the OpenWSFZ matched rows in both live run directories, cross-tabulating
`true_dt == 0` against `reported_dt < 0`, counting **clusters** (`(scenario, part_index,
true_freq_hz)`) and rows:

| run | (`tdt=0`, `rdt<0`) | (`tdt=0`, `rdt>=0`) | (`tdt>0`, `rdt<0`) | (`tdt>0`, `rdt>=0`) |
|---|---|---|---|---|
| `2026-08-22-d4ce254` (post-B1) | 10 / 48 | **0 / 0** | **0 / 0** | 20 / 62 |
| `2026-08-21-7d36038` (pre-B1) | 75 / 277 | **0 / 0** | **0 / 0** | 35 / 112 |

**Both off-diagonal cells are empty in both corpora.** Every `true_dt == 0` decode reports
a negative DT and every `true_dt > 0` decode reports a non-negative one. The two stratifiers
partition the data identically, so re-labelling returns the identical number and lands on
the identical row whichever hypothesis is true. Withdrawn.

The collinearity is itself consistent with Section 1 (an origin convention displacing
everything by ~1.25 symbols makes the two labels coincide in these scenarios) -- but a fact
that is *predicted* by the hypothesis and cannot discriminate against it is not evidence
for it. Both arms below exist to fill an off-diagonal cell.

---

## 4. TASK 1 -- arm B-dt-C1: fill the off-diagonal cell offline

**Cost: minutes. No live run, no code change, no new binary, no Developer session.**

### 4.1 What to run

Re-run `qa/rr-study/r2-coherent-llr-instrument/ac_n5_dt_stratified_measurement.py` with
**one addition: record `res.dt` per decode** alongside `signal_db`/`local_noise_db`.
`dt` is already a field of the ctypes `FT8Result` struct these harnesses use
(`qa/cycleframer-alignment-replay/c5a_waterfall.py:109` is the existing precedent) -- this
is a new output column, not new instrumentation.

S3 parts 0-7 only, same scope and the same 12 kHz / 180,000-sample rendering AC-N5 used.
S8 is not needed for this arm and adds only the confound of Section 2; run it or skip it,
but do not pool it into anything gated below.

### 4.2 Preconditions -- assert, do not assume

1. **Binary identity.** SHA256 of the library under test, working tree as of this drafting:
   `f0c081b968b04515f3fe76b853b423c77be1495d8e645115ceb3434f9e81fe58` (win-x64
   `libft8.dll`) / `1ba510b8358029c36e3ad9b8927bf80c140784655211f5e7bffddfb7eb7c046b`
   (linux-x64 `libft8.so`). **Never infer the build from `FT8_SHIM_VERSION`.** Mismatch
   => STOP and say so; do not "probably the same build" it. Note these files are
   **uncommitted** in the working tree -- if the Captain commits or rebuilds before you
   run, re-pin and record the new hash rather than reusing this one.
2. `fixed.snr_db == 0` still holds in `s3-dt-offset.json` (it is the denominator of every
   error below). `git diff d44ffea -- qa/rr-study/scenarios/s3-dt-offset.json` empty.

### 4.3 Definitions, fixed before the run

- `D_off` = mean(`reported_snr` - `true_snr`) over matched offline S3 **part 0** decodes.
  `true_snr = 0` by scenario.
- `dt_off_0` = mean `res.dt` over those same rows, taken from the struct (no print
  rounding offline).
- Live reference, already measured and not re-derived here: S3 part 0 error **-15.67 dB**,
  `reported_dt` **-0.200 s**, 3/3 (B-dt-A sections 5.1 / 5.3).
- SNR readout quantum **1 dB**; DT grid quantum **0.08 s**.

### 4.4 Pre-registered rows -- mechanical, strict order, mutually exclusive

**ROW 0 -- VALIDITY (two limbs, either fires).**
(a) fewer than **3** matched decodes at S3 part 0, or fewer than **12** matched across
parts 1-7; or
(b) `|D_off - (+2.0)| > 1.0 dB` -- i.e. the offline instrument fails to reproduce AC-N5's
own part-0 value to within one readout quantum.
=> **STOP, escalate. Do not evaluate ROW 1 or ROW 2.**
*Why this changes the verdict rather than decorating it (HK-021(k)):* limb (b) failing
means the offline path is not the same instrument that produced AC-N5, so `dt_off_0` is a
reading off an unvalidated instrument and the row below would attribute to `time_offset`
something that is really run-to-run drift. The action is "re-establish the harness", which
is a different action from either row below. Two-sided by construction (HK-021(n)) --
deviation in either direction is equally disqualifying, which is why limb (b) is the one
place in this spec `| |` is legitimate.

**ROW 1 -- `dt_off_0 >= 0.0`.** => **MECHANISM SUPPORTED.**
Same `true_dt` (0.0), opposite `time_offset` sign, opposite outcome. The off-diagonal cell
is filled and the two stratifiers are separated for the first time: what tracks the
collapse is the sign of `time_offset`, not the value of `true_dt`. => Proceed to TASK 2,
and recommend the Section 1.1 fix to the Captain as a candidate Developer session.

**ROW 2 -- `dt_off_0 < 0.0`.** => **MECHANISM REFUTED AS STATED.**
Negative `time_offset` with no collapse means the clamp is not sufficient on its own, and
the live/offline difference lives somewhere else -- playback/capture alignment, buffer
placement, or a term neither of us has named. => **STOP, escalate to the Architect. Do NOT
run TASK 2 and do NOT recommend a Developer session.**

**Threshold justification (HK-021(m), stated while drafting).** The bar is `0.0`, and it is
not a statistical choice -- it is the literal branch condition at `ft8_shim.c:1491`. The
signed statistic is used throughout, never `|dt|` (HK-021(l)). Distance from the line is
resolved against the **0.08 s DT grid quantum**: the live value is `-0.200 s`, **2.5
quanta** below; a ROW 1 outcome at `dt = 0.00` is exactly on the code's own boundary and is
correctly on the non-clamping side (`b0 = 0` is not `< 0`, and `tones[b - 0]` is the right
symbol). Because `dt` cannot occupy `(-0.08, 0)` (Section 1.2), no value sits ambiguously
astride the line.

### 4.5 Reported, NOT gated

1. `res.dt` at every S3 part 0-7, offline, beside B-dt-A's live `reported_dt` column. If
   the two columns differ by a roughly constant offset, that offset is the live path's
   alignment term and it is worth a number.
2. `signal_db` and `local_noise_db` per part, offline -- the AC-N5 columns, now readable
   per part instead of pooled.
3. Whether any S8 station offline reports `dt < 0`, and if so whether those specific
   stations are the low-`signal_db` ones. Same test as ROW 1 on a different population,
   ungated only because S8's per-station powers differ by design.

---

## 5. TASK 2 -- arm B-dt-C2: localise the step, live

**Run this only if TASK 1 fires ROW 1.** Cost: one short live run, ~10 minutes of cycles.

### 5.1 The question

TASK 1 establishes that the sign of `time_offset` tracks the collapse. TASK 2 asks the
sharper question that separates my mechanism from the rival "the signal falls partly
outside the decode window": **where in `true_dt` does the step sit, and does it sit exactly
where `reported_dt` changes sign?**

- Under Section 1: the step is at the `time_offset` sign change (somewhere in `true_dt` =
  0.0 .. 0.3 s given the ~0.2 s origin offset), it is a **step**, and the deficit is
  roughly **flat** on the negative side -- a 1-symbol and a 3-symbol shift are equally
  wrong.
- Under "partly outside the window": the deficit **ramps** with `|dt|` and need not be
  co-located with the sign change at all.

### 5.2 What to run

A fine DT sweep, S3's machinery unchanged except for the parts list: `true_dt` =
**0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30 s**, `fixed` = `{snr_db: 0, base_freq_hz: 1500}`
exactly as S3, `message_ids: ["MSG-01"]`, **5 trials per part**, both appraisers.
`requires_extended_dt` is **not** needed -- every part is `>= 0`.

New scenario JSON, QA's to author (`s3c-dt-fine-sweep.json` or whatever fits the
convention). 7 parts x 5 trials = 35 cycles, ~9 minutes plus overhead.

**Trial count justification (HK-021(o)):** this is a continuous dB response against a 1 dB
readout quantum with an expected contrast of ~17 dB, not an attribute rate -- S3b's
100-trials-per-part sizing note does not apply and must not be copied across. 5 trials
resolves a 17 dB step trivially; it is there to catch a flaky part, not to buy precision.

### 5.3 Preconditions

1. `--device "Voicemeeter AUX Input"` passed **explicitly** (the `run_study.py` default is
   still the known-faulty `"CABLE Input"`).
2. `captureActive=true` confirmed on the heartbeat immediately before arming.
3. Both `ALL.TXT` files cleared before the run; preserve pre-clear copies rather than
   discarding them; grep every `*_matched.csv` individually for NFR-021 contamination
   before committing.
4. Binary SHA asserted against whatever is actually loaded at run time, per 4.2(1).

### 5.4 Definitions

- `E(p)` = mean(`reported_snr` - `true_snr`) over matched OpenWSFZ decodes at part `p`.
- `T(p)` = mean `reported_dt` at part `p`.
- `p_step` = the part index `p >= 1` maximising `E(p) - E(p-1)`.
- `p_sign` = the **lowest** part index with `T(p) >= 0`.
- Cluster = `(scenario, part_index, true_freq_hz)`. Report clusters, never bare rows.

### 5.5 Pre-registered rows -- mechanical, strict order, mutually exclusive

**ROW 0 -- VALIDITY.** Two or more parts with fewer than 3 matched OpenWSFZ decodes, OR no
part with `T(p) >= 0`, OR no part with `T(p) < 0`.
=> **STOP, escalate.** Without both signs present the sweep did not straddle the boundary
and `p_sign` is undefined -- a finding about the sweep's placement, needing a re-render at
a shifted range, which is a different action from every row below.

**ROW 1 -- `max_p [E(p) - E(p-1)] < 8.0 dB`.** => **NO STEP.**
The effect did not reproduce in this sweep. => STOP, escalate. Do not read `p_step`; it is
not defined without a step.

**ROW 2 -- a step of `>= 8.0 dB` exists AND `p_step == p_sign`.** => **CO-LOCATED,
MECHANISM CONFIRMED** as far as an observational arm can take it. The SNR step and the
`time_offset` sign change are the same event. => Recommend the Section 1.1 fix to the
Captain as a Developer session, with the regression check in 5.7.

**ROW 3 -- a step of `>= 8.0 dB` exists AND `p_step != p_sign`.** => **SEPARATED,
MECHANISM REFUTED.** The two are distinguishable and the clamp is not what drives the
collapse. => STOP, escalate. Do not open a Developer session.

**Threshold justification (HK-021(m)).** `8.0 dB` sits **9.2 quanta** below the expected
step (17.2 dB, from `-15.67` to `+1.5`) and **8.0 quanta** above the no-effect case. Both
candidate outcomes are many quanta clear of the line. Signed throughout (HK-021(l)).

**Why co-location, and not "the step is at `true_dt = 0.20`" (this matters).** The
`true_dt` label is the harness's *intent*; the live playback path carries its own
unmeasured latency, so an absolute claim about where the boundary sits in `true_dt` would
be a claim about the playback path as much as about the decoder. ROW 2 compares two
quantities measured **on the same rows of the same run**, so any common offset shifts both
and cancels. This is also why the arm does not violate HK-026: it does not use the
decoder's output to bound the decoder's own blind spot -- `p_sign` is read from the
decoder, `p_step` is read from the decoder, and the gate is on whether they *agree*, not
on where either one lands.

### 5.6 Reported, NOT gated

1. The full `E(p)` / `T(p)` table, all seven parts, both appraisers.
2. **Flatness on the negative side:** `max E(p) - min E(p)` over the parts with `T(p) < 0`.
   Section 1 predicts flat (within a few dB); a ramp is the rival's signature. Not gated,
   because with at most four parts on that side the contrast is too thin to carry a
   threshold honestly.
3. WSJT-X across the same sweep, as the standing check that the audio and truth labels did
   not move. Section 1 predicts no step anywhere in WSJT-X's own column.
4. Cluster composition across parts -- a part dropping out entirely is not the same as a
   part decoding badly, and `E(p)` alone cannot tell them apart (HK-022's drafting
   question).

### 5.7 The regression check to hand forward, if ROW 2 fires

State it in the report so the Developer session inherits it rather than inventing one: the
Section 1.1 fix touches only decodes with `time_offset < 0`, so on any corpus where every
decode has `dt >= 0` the replay must be **bit-identical**, decode for decode. The eight
committed `results/replay_*.json` files from AC-N1 are exactly such a corpus. That is a
cheap, mechanical containment check with a hard pass/fail, and it is stronger than "tests
still green".

---

## 6. What this document does NOT license

- Does **not** authorise any `src/` or `native/` change. Section 1.1 names a fix; naming is
  not applying. HK-011: the Captain opens a Developer session or nothing happens.
- Does **not** reopen AC-N2/N3/N4, the getter, or the Amendment 2/3 acceptance.
- Does **not** substitute for `tasks.md` section 11 (Phase B's own ROW 0g re-run), which
  remains open and unscheduled.
- Does **not** bear on H5, suppression, the SNR *formula* (`- 26.5`), Route B2/B3, C2, C3,
  or `DEFECT-snr-reported-gain-error.md`'s eventual fix choice.
- Does **not** license any statement about negative `true_dt`, `dt_s > 2.1`, or decode
  *rate* at any DT. S3b remains unrun and its old description field remains VOID per its
  own `_status_warning`.
- Does **not** license reading the collinearity in Section 3 as evidence for the mechanism.
  It is predicted by it and cannot discriminate.

---

## 7. Architect predictions -- recorded before either arm runs

Calibration record. My categorical ROW calls have run 2/4 historically and both range
misses were too pessimistic about how cleanly effects separate; read these as asymmetric.

| # | Arm | Prediction | Confidence |
|---|---|---|---|
| 1 | C1 | ROW 0 does not fire (both limbs clear) | 85% |
| 2 | C1 | **ROW 1 fires** -- `dt_off_0 >= 0` | 80% |
| 3 | C1 | `dt_off_0` lands in `[0.00, +0.16]`, i.e. `time_offset` 0 or 1 | 65% |
| 4 | C2 | ROW 0 does not fire -- the 0.00-0.30 range straddles the sign change | 70% |
| 5 | C2 | **ROW 2 fires** -- `p_step == p_sign` | 70% |
| 6 | C2 | `p_sign` is part 3 or 4 (`true_dt` 0.15 or 0.20 s) | 50% |
| 7 | C2 | Negative-side flatness (5.6.2) is `<= 4 dB` -- step, not ramp | 60% |
| 8 | C2 | WSJT-X shows no step of any size across the sweep | 90% |

Prediction 5 is the one that matters. If it misses, Section 1 is wrong, and I would rather
find that out in a 10-minute sweep than after a Developer session.
