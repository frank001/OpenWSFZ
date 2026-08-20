# Architect → QA: G3 arming instruction (full-DT-grid self-validation)

**UTC:** 2026-08-19 17:09Z
**Authorises:** Route B §8 step 5 item (1) — G3 manual WSJT-X confirmation, ONLY.
**Does NOT authorise:** the S3b live run, S3b pre-registration, any `src/` change, any push or merge.
**HK-011:** NOT engaged (no `src/` edit in this task). **HK-015:** Architect → QA, one-directional.

---

## §0 — READ FIRST: the rig the Captain just set up is NOT what G3 uses

The Captain reports: *WSJT-X FT991A listening to Voicemeeter B1; Voicemeeter AUX routed to B1.*

**That is the LIVE PLAYBACK chain. G3 does not use it.**

`g3_full_grid_self_validation_render.py`'s own docstring is explicit:

> *"This is a file-based check (no live device, no VB-CABLE/Voicemeeter routing) ... WSJT-X's
> File > Open decodes whatever is in the file — it does not need the file to start exactly at a
> slot boundary."*

G3 is **`File > Open` on 20 already-rendered WAVs**. No audio routing, no device argument, no
`--device "Voicemeeter AUX Input"`, no daemon, no OpenWSFZ running. The routing the Captain has
built is correct and needed — but for **G4 and the S3b live run**, which come after this.

🔴 **Consequence for QA: do not pass a `--device` flag anywhere in this task. If you find yourself
choosing an audio device, you are running the wrong gate.**

---

## §1 — State on disk, verified 17:09Z (do not re-render)

All 20 WAVs already exist at `qa/rr-study/g3_full_grid_wav/`, rendered 2026-08-19 18:46 local.
**Re-rendering is not required and is not authorised** — it churns the artefacts for no gain and
breaks correspondence with the 16:54Z report.

Format verified: **16-bit mono, 12 000 Hz** — WSJT-X `File > Open` compatible.

Durations confirm the extended buffers are mechanically correct:

| File | Label `dt_s` | Duration | Expected |
|---|---|---|---|
| `S3_part0_dt+0.0.wav` | +0.0 | 15.0000 s | nominal slot |
| `S3_part8_dt+2.4.wav` | +2.4 | 15.0400 s | +0.04 s past slot |
| `S3_part9_dt+2.7.wav` | +2.7 | 15.3400 s | +0.34 s past slot |
| `S3b_part9_dt-2.7.wav` | −2.7 | 17.7000 s | +2.7 s of lead-in |

The overflow on S3 parts 8/9 is **exactly** what the old clamp used to swallow
(2.7 − 2.36 = 0.34 s). That is the defect, now visible in a file listing.

**Expected decoded text for every one of the 20 files: `CQ Q1ABC FN42`** (MSG-01).
Q-prefix synthetic, NFR-021-clean.

---

## §2 — My one concern, stated once: the uncleared `ALL.TXT`

The Captain has explicitly not cleared `ALL.TXT` or the WAV save folder. **I am not asking them
to.** The mechanical fix below costs QA nothing and requires the Captain to touch nothing.

**Baseline snapshot, taken by me at 17:09Z:**

```
C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT
  9,595,310 bytes
  146,167 lines
  mtime 2026-08-15 23:56:56 +0200
```

That file has not been written since **15 August**, so the boundary is clean right now.

🔴 **QA: re-take that snapshot immediately before the first `File > Open`, and again after the
last one. Everything between the two offsets is unambiguously ours.** Use the line count as the
cut point (`sed -n '146168,$p'` or equivalent against the post-run file). Do not diff whole files.

⚠️ **NFR-021 handling rule — this is a handling rule, NOT a gate row.** I considered making
"the delta contains only Q-prefix callsigns" a pre-registered ROW 0 check and **rejected it under
HK-025**: leaked live audio cannot manufacture a false `CQ Q1ABC FN42`, so the check cannot change
the verdict either way ⇒ DIAGNOSTIC ⇒ QA would have been right to refuse it. It stays as
commit hygiene instead:

- **Do NOT commit `ALL.TXT`, any copy of it, or any file derived from it.**
- If you produce a delta file for the record, grep **every file individually** before committing —
  the R&R precedent is 203 920 real-callsign rows inside a single `S1_matched.csv` that a report
  had already declared clean.
- Anything you must keep goes to `artefacts/` (blanket-gitignored), never into `qa/`.

---

## §3 — Pre-flight, before the first file (HK-022 / HK-019)

1. **Confirm exactly ONE WSJT-X instance is running.** Two instances share one `save\` folder and
   silently overwrite each other's UTC-named WAVs. Check `Win32_Process` for strays, not the taskbar.
2. **Confirm which instance you are about to drive** and that its `ALL.TXT` is the FT991A one
   snapshotted above. If the Captain is driving `WSJT-X - FT991A-Copy` or the bare `WSJT-X`
   profile, the baseline is wrong and the delta is meaningless — re-snapshot the right one.
3. **Mode = FT8.** Nothing else in the WSJT-X configuration matters for a `File > Open`.

---

## §4 — Procedure

For each of the 20 WAVs in `qa/rr-study/g3_full_grid_wav/`:

```
File > Open  ->  select the .wav
Observe Band Activity
Record: filename | decode appeared? | decoded text | how many decode lines that file produced
```

🔴 **Record the per-file decode COUNT, not just pass/fail.** Row 0b turns on it.

⚠️ SNR and DT as reported by WSJT-X **will not match** the injected values for the early/late
parts — that is by construction and is not a failure. **Only text correctness is gated.**

**This step needs the Captain's hands. QA cannot drive a GUI** (same convention as
`gate_render.py`). QA's job is the pre-flight, the snapshot, the tally, and the gate reading.

---

## §5 — Pre-registered gate (HK-021)

Let **N** = the number of the 20 WAVs that produce **exactly one** decode whose text is
`CQ Q1ABC FN42`.

**Resolution statement (HK-021(o)):** the readout quantum is **one file**. N is an integer on
[0, 20] and every threshold below is an integer. The gate resolves to the quantum exactly; a
straddle is not possible. No bootstrap, no SE, no CI — a variance estimate on this statistic
would be exactly the decorative pass that (o) was minted for.

Rows are strictly ordered and mutually exclusive. **Read the first that fires and stop.**

| Row | Condition | Verdict and consequence (assertion) |
|---|---|---|
| **0a** | Either `S3_part0_dt+0.0.wav` or `S3b_part0_dt+0.0.wav` fails to decode `CQ Q1ABC FN42` | **VOID — instrument failure.** The dt=0 control is the one part with no extended-range content, so a failure there is WSJT-X config / file format / mode, not our synth. **STOP. Read no other part. The whole gate is void.** |
| **0b** | Any single WAV produces **more than one** decode of the expected text | **VOID — synth defect.** The extended buffer duplicates the signal; reading N would over-count. **STOP, report which file(s).** *(Two-sided per HK-021(n): the failure mode that inflates N is gated as hard as the one that deflates it.)* |
| **1** | N = 20 | **PASS.** Extended-range synth is sound across the full grid. G3 clears. Proceed to G4 and the §7 decisions. |
| **2** | N ∈ {18, 19} **and** every failure is at \|dt_s\| ≥ 2.4 | **PASS, GRID BOUNDED.** Sound over the validated range only. **S3b's grid is truncated to the last validated \|dt\| before any live run** — and that truncation *is* the answer to the parts-vs-wall-clock question, cutting PARTS, which is the direction already ruled. |
| **3** | N ∈ {18, 19} **and** ≥1 failure is at \|dt_s\| ≤ 2.1 | **FAIL — non-monotonic.** A hole in the interior is a defect, not a range limit. **STOP, report which dt_s. No live run.** |
| **4** | N ≤ 17 | **FAIL.** The extended render is not sound. **STOP, report every failing dt_s. No live run, no S3b pre-registration.** |

### §5.1 Interpretation hazard, named in advance (HK-026)

A failure on **`S3_part8` or `S3_part9` specifically** is ambiguous. Those two files run *past* the
nominal 15 s window, and WSJT-X's `File > Open` may simply truncate to its own expected window.
**That would be the instrument's aperture, not our synth** — and using that instrument's output to
bound our own render is precisely the HK-026 error.

🔴 If and only if ROW 2/3/4 fires *and* the failures are confined to S3 parts 8/9, the
disambiguation is to re-render those two with the same signal offset inside a nominal 15 s file and
re-test. **Do not perform that re-test unless the gate sends you there, and report it as a separate
follow-up, never folded into G3's reading.** The negative side (S3b) carries no such ambiguity —
a longer file with lead-in is ordinary for `File > Open`.

---

## §6 — Sealed blind predictions (Architect, recorded before the run)

Calibration discipline. Board tally is categorical 9/15, ranges 12/20, and my ranges run
**under-dispersed** — read these as wider than stated.

- **ROW 1 (N = 20): P ≈ 0.65**
- ROW 2 (bounded grid): P ≈ 0.25
- ROW 3 (non-monotonic): P ≈ 0.03
- ROW 4 (N ≤ 17): P ≈ 0.07
- ROW 0a or 0b: P ≈ 0.03
- **Most likely single failure, if any: I now think S3 parts 8/9 are likelier than
  `S3b_part9_dt-2.7.wav`, on the §5.1 aperture argument I did not have when I wrote the 16:30Z
  spec.** That is a revision of my earlier "G3 fails at ≥1 extreme point, P ≈ 0.3", made before
  seeing any result and recorded here as a revision rather than quietly replaced.

---

## §7 — What QA does when the gate is read

Report to Architect with: the 20-row tally, N, the row that fired, both `ALL.TXT` offsets, and
confirmation that nothing containing real callsigns was staged for commit.

**Then STOP.** Items (2) G4, (3) parts-vs-wall-clock, (4) the S3 re-grid ruling are Architect and
Captain calls and are not authorised by this document.

⚠️ **G4 is ready to arm and the rig is warm.** G4 (≥95 % decode at dt=0 — HK-026: without it the
S3b run measures SNR margin rather than the DT boundary) **does** need the Voicemeeter chain the
Captain has just built. If ROW 1 fires, say so immediately and I will issue G4's arming instruction
while the routing is still up, rather than asking for it to be rebuilt later.
