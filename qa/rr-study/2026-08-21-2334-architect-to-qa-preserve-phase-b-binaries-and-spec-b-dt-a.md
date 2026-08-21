# Architect -> QA: PRESERVE the Phase B binaries, then run arm B-dt-A

**Author:** Architect
**Date:** 2026-08-21 23:34Z (`date -u`, HK-017)
**Status:** **TASK 1 was URGENT and blocking -- it is now DONE** (executed 23:43Z by the
Architect on the Captain's instruction; see the banner in section 1, and section 1.3 for what
QA still owes it). TASK 2 is a pre-registered arm, no `src/` change, and is **the live work**.
**Supersedes nothing.** Companion to the 23:34Z **Amendment 3**, which corrects the
23:11Z Amendment 2. Read that one too; this document is the RUN, that one is the RECORD.
**HK-011:** neither task in this document touches `src/` or native code. No Developer
session required. QA runs both.

---

## 0. Read this first -- why TASK 1 cannot wait

The Phase B build (origin fix B1, fusion fix B2, `ft8_ldpc_decode_llrs` B4) is **built and
sitting UNCOMMITTED in the working tree**. The last commit that touched `libft8.dll` is
`5d3cac5` -- Route B2 Phase 1, shim **20260043**, i.e. *pre*-Phase-B.

Amendment 2 section 5 (AC-N1) gates on a replay diff "against the pre-Amendment-2 Phase B
binary", and Amendment 2 section 7 step 2 rebuilds **in place** over
`src/OpenWSFZ.Ft8/Native/{win-x64/libft8.dll, linux-x64/libft8.so}`.

**The rebuild destroys AC-N1's own reference, and `git checkout` cannot restore it** --
git holds the 20260043 build, not the Phase B one. The moment a Developer session starts,
AC-N1 becomes unrunnable and every Phase B acceptance result becomes unreproducible.

This is my error in the Amendment 2 spec. It is caught before the Developer session, which
is the only reason it is cheap.

---

## 1. TASK 1 -- ARCHIVE the Phase B binaries. Do this before anything else.

> ## ✅ TASK 1 IS DONE -- executed 2026-08-21 23:43Z by the Architect
>
> **On the Captain's direct instruction ("secure the binaries at all costs"),** because a
> file copy touches no `src/` content and delay was the whole risk. **QA does not need to
> perform this task.** What QA still owes it is section 1.3: **verify before relying on it.**
>
> Two independent copies, on different drives, both verified:
>
> | Location | Drive | Exposure |
> |---|---|---|
> | `artefacts/2026-08-21-phase-b-pre-amendment-2-binaries/` | D: | in-repo, gitignored -- **`git clean -xdf` would delete this** |
> | `C:\Users\Frank\.claude\projects\D--Projects-claude-OpenWSFZ\preserved-binaries\2026-08-21-phase-b-pre-amendment-2\` | C: | outside the repo, untouched by any git operation |
>
> Each contains `libft8.dll`, `libft8.so`, a mechanically generated `SHA256SUMS`, and a
> `README.md` carrying full provenance and recovery instructions. Binaries and manifests are
> set **read-only** on both POSIX bits and the Windows ReadOnly attribute.
>
> **Verification performed:** live originals re-hashed and matched the 23:31Z record before
> copying; `sha256sum -c` passed in both locations; `cmp` byte-for-byte against the live
> originals passed in both locations; the two archives `cmp` identical to each other; the
> live originals confirmed still intact afterwards.
>
> **Identity asserted from the artefacts, not from a version label** (both platforms agree):
> `ft8_ldpc_decode_llrs` **present** => this IS the Phase B build; `ft8_get_last_snr_terms`
> **absent** => this IS pre-Amendment-2; version constant **20260044** present, 20260043 and
> 20260045 both absent. This is what AC-N1 should assert against.
>
> **Still open, and NOT actioned:** these binaries are still not in version control.
> Committing the Phase B build is the durable fix and an **HK-011 Captain call** -- flagged
> in section 1.4, deliberately not acted on.

### 1.1 The two files at risk, with their SHA256 as of 23:31Z

| File | SHA256 |
|---|---|
| `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `a3d32b7839a0fd73dcc8d35bd514d60f962f3267179fd77cbd8a1ebd6ecc8d45` |
| `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` | `13d9799d91388d9edd10e457cecf59a09c7a088caa09eb7c56cd40ea5ec5f894` |

For contrast, the committed (pre-Phase-B, shim 20260043) versions of the same paths are
`1889408787a2c7ea...` and `8c79cf40f46bd0a5...`. **If you compute the working-tree hashes
and get those, the Phase B build is ALREADY LOST -- stop and escalate immediately.**

### 1.2 What to do

Per HK-016: a dated, `README.md`'d directory under `artefacts/` (blanket-gitignored, so
binaries are safe there), containing:

1. Both binaries, copied -- not moved.
2. A `SHA256SUMS` file, generated mechanically (`sha256sum`), not transcribed.
3. `README.md` recording: what these are (Phase B B1/B2/B4, pre-Amendment-2), the shim
   version they report (**20260044**), the working-tree state they were built from, and
   the commit they are *not* in (`5d3cac5` is the last committed build).
4. Re-verify the copies against `SHA256SUMS` after copying. A copy you have not verified
   is not a backup.

### 1.3 What QA still owes TASK 1 -- verify, do not inherit

The archive above was made by the Architect, so QA has not verified it. **Before AC-N1 or
anything else relies on it**, independently confirm:

1. `sha256sum -c SHA256SUMS` passes in **both** locations in the banner above.
2. The hashes equal `a3d32b78...` / `13d9799d...` -- the values in section 1.1.
3. `ft8_get_last_snr_terms` is **absent** from both binaries (i.e. it really is the
   pre-Amendment-2 build), and `ft8_ldpc_decode_llrs` is **present** (it really is Phase B).

A backup nobody has verified is not a backup. That applies to mine.

### 1.4 Then flag this to the Captain, do not decide it yourself

The durable fix is to **commit the Phase B build**, not to keep it in a gitignored folder.
That is an HK-011 `src/` decision and therefore the Captain's, not QA's and not mine.
Raise it; do not act on it.

### 1.5 The standing rule this sits under

`FT8_SHIM_VERSION` identifies nothing -- 20260044 will be reported by both the current
build and the post-Amendment-2 build if the bump is missed. **Pin and assert the SHA256.**
Every SHA256 recorded during the 22:09Z review is void; these two, at 23:31Z, replace them.

---

## 2. Why TASK 2 exists -- a finding that changes what Phase B is looking at

### 2.1 What I got wrong

Amendment 2 section 1.3 states the SNR-error mechanism "is unidentified and **cannot be
identified from outside the shim**", and that sentence is the entire justification for
building `ft8_get_last_snr_terms`. **It is false.** The mechanism was identifiable from
data already on disk. I did not run the stratification. HK-018.

### 2.2 The stratification I should have run

`qa/rr-study/results/2026-08-21-7d36038/*_matched.csv`, OpenWSFZ appraiser, matched
decodes only, reported-minus-true SNR, stratified by **true DT** (an INPUT, not a decoder
output):

| true_dt (s) | n | clusters | mean err (dB) |
|---|---|---|---|
| **0.00** | 277 | **75** | **-13.9** |
| 0.20 | 66 | 22 | +1.1 |
| 0.30 | 3 | 1 | +1.3 |
| 0.50 | 10 | 2 | +1.0 |
| 0.60 .. 2.70 (9 strata) | 30 | 9 | +1.0 .. +2.0 |

Total separation, no overlap, on a controlled input, 75 clusters against 34. Not the
HK-021(i) artefact.

### 2.3 "Single-signal vs multi-signal" was a confound for DT

Of the 277 collapsed rows, **274 are the S4/S7/S8 multi-signal rows -- and every one of
those parts is synthesised at `true_dt = 0.0`.** The other 3 are **S3 part 0, which is
single-signal at DT 0.0 and collapses identically**:

| | true_snr | reported_snr | true_dt | reported_dt | freq |
|---|---|---|---|---|---|
| S3 part 0, OpenWSFZ (3/3 identical) | 0 dB | **-16.0 dB** | 0.0 | **-0.2** | 1500 Hz |
| S3 part 0, WSJT-X (3/3 identical) | 0 dB | +1.0 dB | 0.0 | -0.8 | 1500 Hz |
| S2 part 0, OpenWSFZ (3/3 identical) | 0 dB | **+1.0 dB** | 0.2 | 0.0 | 1500 Hz |

Same frequency, same true SNR, single signal in both, no neighbours in either. The only
difference is DT, and the SNR moves 17 dB.

It also dissolves the anomaly I called unexplainable: the S8 650 Hz vs 1650 Hz 18 dB split
at identical true SNR is a DT split. 1650 Hz is one of the few S8 stations at `true_dt > 0`.

### 2.4 The discriminator that keeps this a decoder defect, not a synthesis artefact

The obvious alternative -- "at DT 0.0 the harness clips the first symbol, so the audio
really *is* weak and OpenWSFZ is right" -- is refuted by the same table: **WSJT-X reports
+1.0 dB on that identical audio.** If the emitted signal were 17 dB down, WSJT-X would say
so. It does not. The audio is fine; the estimator is ours.

### 2.5 Two things this does NOT settle, stated so nobody over-reads it

- **The boundary shape is unmeasured.** We have DT 0.0 (collapsed) and DT 0.2/0.3 (clean),
  and *nothing between*. Whether it is a step at exactly zero, a knee, or a ramp is
  unknown, and the current grid cannot answer it -- the instrument is blind between those
  points (HK-026). Do not interpolate.
- **Negative DT is entirely unmeasured.** `s3b-dt-boundary.json` is the wider-aperture
  instrument for that, and it is `BUILT, NOT YET RUN` -- ~4.2 h, Captain's hardware, HK-013
  supervisor. **Not in scope here.** Its `_status_warning` also voids the old
  "reports DT ~= 0" finding; do not cite that.

### 2.6 What is still NOT claimed

That this costs decodes. That fixing it helps D-001. Neither follows, and neither is
tested by anything below.

---

## 3. TASK 2 -- arm B-dt-A: does the Phase B origin fix already fix this?

### 3.1 The question, and why it is worth a run before a Developer session

Phase B **B1 is the waterfall origin fix** -- a time-alignment change. The defect in
section 2 is keyed to time alignment. The 2026-08-21 sweep ran at commit `7d36038`, which
is **pre-Phase-B**. The post-B1 binary is built and in the working tree right now.

So: the change that may already fix this has never been measured against it. If B1 fixes
it, Amendment 2's motivating defect is gone and the getter should be re-scoped before a
Developer session, not after. That is a cheap run standing in front of an expensive one.

### 3.2 What to run

**On the archived Phase B binary from TASK 1** (assert its SHA256 first -- section 3.3).

Minimum required scenario set:

| Scenario | Role | Why it is in the set |
|---|---|---|
| **S3** (`s3-dt-offset.json`) | the DT sweep | 10 parts, DT 0.0 .. 2.7, single signal, everything else held. The controlled contrast. |
| **S2** (`s2-freq-sweep.json`) | DT > 0 control | fixed DT 0.2, 10 clusters, known-clean pre-B1 (+1.0) |
| **S8** (`s8-band-scene.json`) | DT = 0 multi-cluster | 10 distinct frequencies at DT 0.0 -- the cluster count that makes the collapse stratum powered |

Run S4 and S7 as well **if and only if** the schedule allows; they add n but no new
condition. Do not cut S3, S2 or S8 to fit them in.

Same seeds, same scenario JSONs, same corpus as the 2026-08-21 sweep. **If any scenario
JSON has changed since `7d36038`, say so in the report and do not silently proceed** --
the pre/post contrast dies if the audio changed.

Note for the record: S3 parts 8/9 are **no longer mislabelled**. `requires_extended_dt`
was flipped true on 2026-08-20 per the S3 re-grid ruling, so the positive-clamp defect
does not touch this run. Their pre-B1 values (+2.0, +1.0) are valid.

### 3.3 Preconditions -- assert, do not assume

1. **Binary identity.** SHA256 of the DLL/SO under test == `a3d32b78...` / `13d9799d...`
   (section 1.1). **Never infer the build from `FT8_SHIM_VERSION`** -- 20260044 is not
   unique to it. Mismatch => STOP.
2. **Device.** `--device "Voicemeeter AUX Input"` passed EXPLICITLY. The default in
   `run_study.py` is still `"CABLE Input"`, which is the known-faulty path on this machine.
3. **`captureActive=true`** before arming, per the stale-endpoint-GUID note.
4. **`ALL.TXT` cleared** before the run, or every `*_matched.csv` inherits the
   NFR-021 contamination. Grep each output file individually before committing it.

### 3.4 Definitions, fixed before the run

- `M0` = mean(reported_snr - true_snr) over **matched OpenWSFZ decodes at `true_dt == 0.0`**,
  pooled across all scenarios in the run.
- `Mplus` = the same quantity over **`true_dt > 0.0`**.
- **Cluster** = a distinct `(scenario, part_index, true_freq_hz)` triple. Report cluster
  counts, never bare row counts.
- Readout quantum = **1 dB** (`FT8Result.snr` is int-rounded at `ft8_shim.c:1479`).
  All distances below are resolved against that quantum, not against a bootstrap SE
  (HK-021(o)).

### 3.5 Pre-registered rows -- mechanical, strict order, mutually exclusive

**ROW 0 -- VALIDITY.** Clusters at `true_dt == 0.0` < **10**, OR clusters at
`true_dt > 0.0` < **10**.
=> **STOP, escalate. Do not evaluate ROW 1 or ROW 2.**
Consequence and why it differs: a shortfall means B1 changed decode **yield**, so `M0` is
a mean over a different population than the pre-B1 figure and the contrast is not
identifiable. That is a *finding about B1*, not a measurement of the SNR error -- a
different verdict and a different next action from either row below, which is what makes
this a precondition and not decoration (HK-021(k)/HK-025).

**ROW 1 -- `M0 >= -5.0 dB`.** => **B1 FIXED IT.**
Amendment 2's motivating defect is resolved by the origin fix. **Amendment 2, as corrected
by Amendment 3, is DEFERRED pending Architect re-scope.** QA reports and stops. Do NOT
open a Developer session on the getter.

**ROW 2 -- `M0 < -5.0 dB`.** => **COLLAPSE PERSISTS.**
Amendment 2 proceeds as corrected by Amendment 3. The getter is required, because
separating `signal_db` from `local_noise_db` is the only remaining way to localise it.

**Threshold justification (HK-021(m), stated while drafting):** -5.0 dB sits **11.0 dB
(11 quanta)** from the pre-B1 S3-part-0 value (-16.0) and **8.9 dB (8.9 quanta)** from the
pre-B1 pooled value (-13.9); and **6.5 dB (6.5 quanta)** from the fixed-case expectation
(+1.5, the pre-B1 `Mplus`). Both candidate outcomes are many quanta clear of the line.
Signed statistic throughout -- never `|x|` (HK-021(l)).

A *partial* fix (say `M0` = -7 dB) falls in ROW 2, which is correct: the getter is still
needed. Report the magnitude regardless -- see 3.6.

### 3.6 Reported, NOT gated

No thresholds on any of these. They inform the next spec; they do not decide this one.

1. **The full S3 per-part profile**, parts 0-9, post-B1, beside the pre-B1 values. Shows
   whether B1 moved the whole curve or only part 0.
2. **`Mplus`**, and `M0 - Mplus` (the within-run contrast, immune to any level shift).
3. **`reported_dt` at S3 part 0.** Pre-B1 it was **-0.2**, 3/3. If B1 moved it to 0.0 and
   the SNR recovered, that is the mechanism in one line.
4. **Composition diff.** The set of `(scenario, part_index, true_freq_hz)` clusters that
   decoded post-B1, diffed against the same set pre-B1.
   *This exists because of HK-022's drafting question:* ROW 0 counts clusters, so it
   **cannot detect a swap** -- one station dropping out and another appearing at constant
   cluster count. The diff is the only thing in this spec that can.
5. **WSJT-X on the same run**, all strata, as the standing cross-check that the audio and
   truth labels did not move.

Do not compute Gage R&R on the DT response for any of this.

### 3.7 One thing that does not need worrying about

`wsjt_dt_correction_s: 0.55` is flagged UNKNOWN-ACCURACY in the standing notes, and it
does affect appraiser-to-appraiser *reported DT* comparisons. **It does not touch anything
gated here** -- every row above stratifies on **true** DT and compares SNR. Say so in the
report so the next reader does not re-litigate it.

---

## 4. What this document does NOT license

- Does **not** license any `src/`, native, or `ft8_shim.c` change. Both tasks are read-only
  plus a file copy. HK-011 is not engaged by this document.
- Does **not** license running S3b, or any negative-DT work (section 2.5).
- Does **not** license re-gridding S3, or changing any scenario JSON. If the grid looks
  wrong, report it -- the re-grid call is explicitly reserved.
- Does **not** reopen H5, change the SNR formula, or touch suppression or
  `K_SOFT_SUPP_SNR_*`. Unchanged by anything here.
- Does **not** bear on ROW 0g (still FIRED), task 4.3 (still VOID), Route B2 (not dead),
  or B3 (HELD).
- **HK-025 stands.** If any row above fails the mechanical test on inspection, refuse the
  run, name the row and both branches, and stop. You do not need my agreement.

---

## 5. Architect predictions (calibration, recorded before the run)

| Prediction | Confidence |
|---|---|
| ROW 0 does not fire (yield holds) | 85% |
| ROW 2 fires -- B1 does NOT fix the SNR collapse | 65% |
| `reported_dt` at S3 part 0 is still -0.2 post-B1 | 60% |
| If ROW 2 fires, the collapse localises to `signal_db`, not `local_noise_db` | 80% |

**Read these with the record in mind.** Three of my mechanism claims on this dataset have
now failed: two proposals refuted against the data, and one assertion of impossibility
(section 2.1) refuted by the data I already had. The last row above is the one Amendment 3
inverts relative to Amendment 2, and it is the one I would bet on least comfortably.
