# Architect → QA: G3 GATE AMENDMENT — jt9 becomes the primary readout

**UTC:** 2026-08-19 17:31Z
**Amends:** the 17:09Z instruction's §5 gate — **INSTRUMENT ONLY. Thresholds unchanged.**
**Captain's ruling:** jt9 over all 20, plus a 3-file WSJT-X spot check.
**Reason for amendment:** the Captain is a human and cannot serve as a 20-row recording
instrument. That constraint is permanent and legitimate; the previous protocol was mis-specified.

---

## §0 — DISCLOSURE: I am not blind, and I am saying so before anything else

🔴 **Before this amendment was written I ran jt9 on 3 of the 20 files and saw the results.** They
are:

```
S3_part0_dt+0.0.wav    10  -0.5  1500  ~  CQ Q1ABC FN42     <DecodeFinished> 0 1 0
S3_part9_dt+2.7.wav    10   2.2  1500  ~  CQ Q1ABC FN42     <DecodeFinished> 0 1 0
S3b_part9_dt-2.7.wav   11  -0.5  1500  ~  CQ Q1ABC FN42     <DecodeFinished> 0 1 0
```

**What this means for the gate's integrity:**

- ✅ **The thresholds are untouched and were fixed at 17:09Z, before any observation existed.**
  `N` = 20 / {18,19} / ≤17 and the ROW 0a/0b conditions are quoted verbatim below. **I have not
  moved a threshold after seeing a number** — that is the prohibited re-read and it has not
  happened.
- ⚠️ **But ROW 0a is now pre-satisfied for the jt9 instrument** — I have already seen the dt=0
  control pass. QA must still evaluate it mechanically for the record; it is no longer a blind check.
- ⚠️ **3 of 20 files are known-passing under jt9, including both extremes.** My §6 predictions
  were sealed at 17:09Z and stand as recorded, but **they are no longer blind and must be scored
  with that caveat, or not scored at all.** My call: **do not score them.** A prediction that
  partially resolved before I restated it is not calibration data.

---

## §1 — The instrument change, and why it is legitimate

`gate_render.py`'s own source comment (predating all of this, June):

> *"jt9.exe (WSJT-X command-line decoder) processes audio at 12 000 Hz internally and cannot
> resample a 48 kHz WAV. **The gate therefore renders at 12 kHz so that jt9 can validate the
> encoded output directly.**"*

🔴 **jt9-as-render-validator is the original design of this gate family.** The 12 kHz convention
G3 inherited exists *for* it. I built a prohibition fence around it at 17:18Z without checking
that — an HK-018 miss, recorded.

**The standing jt9 prohibition is NOT engaged here, and here is the distinction:**

| Barred use | This use |
|---|---|
| jt9 as a **reference decoder** — comparative recall against OpenWSFZ | jt9 as a **sufficiency check** on our own synth |
| Produces a comparative number (+93.8 %, VOIDed Angle 1) | Produces no comparative number at all |
| Duplicate `(ts, message)` pairs corrupt the count | Per-file invocation, count read from `<DecodeFinished>` |

✅ **The duplicate-pair concern is measured, not assumed:** all three spike files returned
`<DecodeFinished> 0 1 0` — **exactly one decode each.** The pathology does not appear on
single-file invocations.

⚠️ **G3 does NOT need to prove placement — G1 already did**, by cross-correlation, max error
0.0000 s, no decoder involved. G3's only remaining question is *"can a real FT8 decoder read the
extended renders?"* jt9 answers exactly that.

---

## §2 — Primary readout: jt9 over all 20 (QA, unattended)

**Invoke ONE FILE PER CALL.** Do not pass multiple files to one invocation and do not use the
shared-memory path — per-file invocation is what makes attribution exact and keeps the duplicate
pathology out.

```
/d/WSJT/wsjtx/bin/jt9.exe -8 -a <tmp> -t <tmp> <one-file.wav>
```

- `-8` = FT8. **Pass NO `-d` flag** — default depth. The barred configuration was `-d 3`;
  record the exact command line in the report regardless.
- Read the decoded text, and read the decode count from the middle field of `<DecodeFinished>`.
- ⚠️ **Reported SNR and DT will NOT match injected values** (the spike shows −2.7 reported as −0.5,
  +2.7 as +2.2) — jt9 reads from file start, so the extended lead-in shifts its frame. **This is
  expected and is NOT a failure. Only text is gated.**
- Run the full sweep **twice** and diff the output mechanically (HK-022 — "byte-identical" is
  asserted far too often and diffed far too rarely).

### Gate — thresholds VERBATIM from the 17:09Z instruction, unchanged

`N` = number of the 20 files producing **exactly one** decode with text `CQ Q1ABC FN42`.
Readout quantum = one file; all thresholds integer; **no SE, no CI, no bootstrap** (HK-021(o)).
Strictly ordered, mutually exclusive, read the first that fires and stop.

| Row | Condition | Verdict |
|---|---|---|
| **0a** | Either `dt+0.0` control file fails | **VOID — instrument failure.** ⚠️ Known pre-satisfied under jt9 (§0). |
| **0b** | Any single file yields **>1** decode of the expected text | **VOID — synth defect.** Two-sided per HK-021(n). |
| **1** | N = 20 | **PASS.** Extended-range synth sound across the full grid. |
| **2** | N ∈ {18,19}, all failures at \|dt_s\| ≥ 2.4 | **PASS, GRID BOUNDED** — S3b truncated to the validated range; that truncation *is* the parts-vs-wall-clock answer. |
| **3** | N ∈ {18,19}, ≥1 failure at \|dt_s\| ≤ 2.1 | **FAIL — non-monotonic.** STOP, no live run. |
| **4** | N ≤ 17 | **FAIL.** STOP, no live run, no S3b pre-registration. |

---

## §3 — The 3-file WSJT-X spot check: what it is, and what it is NOT

The Captain will open exactly three files and report **only** whether the text appeared:

```
S3_part0_dt+0.0.wav     control
S3_part9_dt+2.7.wav     positive extreme (runs 0.34 s past the slot)
S3b_part9_dt-2.7.wav    negative extreme (2.7 s of lead-in)
```

**No counts. No timings. No snapshots. No table. Three yes/no answers.**

🛑 **CORRECTION TO WHAT THE OPTION IMPLIED: this spot check is NOT part of G3's gate and cannot
pass or fail it.** I have to say so plainly rather than let three clicks be believed to confirm
something they do not.

**HK-025 applied honestly.** Ask whether the spot check can change G3's verdict. It cannot: if jt9
reads all 20, the render contains a decodable signal at every grid point, and that is G3's entire
question. A WSJT-X failure on top of a jt9 pass would not make the render unsound. **As a G3 gate
row it would be DIAGNOSTIC and correctly refused.**

🔴 **It is not wasted — it answers a DIFFERENT question, with a real consequence.** WSJT-X, not
jt9, is the instrument for the **live S3b run**. So:

| Spot-check outcome | Consequence (assertion) |
|---|---|
| All 3 show correct text | No constraint added. S3b's grid stands as validated by jt9. |
| **Control passes, but an extreme fails** | 🔴 **WSJT-X's own aperture — not our synth — bounds the live run.** The S3b grid **must be truncated** to what WSJT-X can actually read via `File > Open`, and the §5.1 HK-026 hazard is **confirmed rather than hypothesised**. This truncates the grid *even though the render is sound*. |
| **Control itself fails** | 🛑 WSJT-X config problem. **STOP** — the live run cannot be armed until resolved, independent of G3. |

That middle row is why the three clicks are worth making: **it can shorten the 4.2 h live run, and
it is the only thing that distinguishes "our render is wrong" from "File > Open's window is
narrow."** jt9 reading a file that WSJT-X cannot is exactly that signature.

---

## §4 — What QA does

1. Run §2's sweep, twice, diffed. Build the 20-row tally.
2. Read the gate. Report `N` and the row that fired.
3. Report the spot-check consequence table with the Captain's three answers filled in **as a
   separate section**, explicitly not folded into G3's verdict.
4. `ALL.TXT` snapshot: **still take it around the Captain's three files** (baseline 9 595 310 bytes
   / 146 167 lines) — it is three files now, so this is cheap. **Never commit `ALL.TXT` or anything
   derived from it**; `artefacts/` only (gitignored); grep every file individually before committing.
5. **Then STOP.** G4, the parts-vs-wall-clock call and the S3 re-grid ruling remain Architect and
   Captain decisions.

**No `src/` change. HK-011 not engaged. No push, no merge (HK-014).**
