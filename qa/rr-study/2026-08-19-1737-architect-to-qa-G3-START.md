# Architect → QA: G3 — START

**UTC:** 2026-08-19 17:37Z · **Captain's order: start.**
Operates under the 17:31Z amendment (jt9 primary). **Thresholds fixed 17:09Z, unchanged.**
🔴 **The human reports NOTHING. Every observation is read from a machine.**

---

## 1. Boundary — SIMPLIFIED, the file is now empty

✅ **The Captain truncated `ALL.TXT` to 0 bytes at 19:39 local (2026-08-19).** Verified.

```
C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT   ->  0 bytes
```

🔴 **No delta arithmetic. No line-count snapshot. Read the WHOLE file** — everything in it from
now on is ours. The previous protocol's off-by-one risk, its dependency on nothing being written
between snapshot and start, and the 431 stale `Q1ABC` lines from 2026-08-15 that would have been
live false-positive bait are **all removed at once.** The Captain's instinct beat the Architect's
protocol; recorded as such.

⚠️ Still true and still binding: **never commit `ALL.TXT` or anything derived from it.** Once the
Captain's three files are opened it will contain our synthetic decodes only, but that is a
property of this moment, not a guarantee — grep before committing anything, every file
individually.

## 2. jt9 sweep — all 20 files, one file per invocation (unattended)

```
/d/WSJT/wsjtx/bin/jt9.exe -8 -a <tmp> -t <tmp> <one-file.wav>
```
Files: `qa/rr-study/g3_full_grid_wav/*.wav` (20). **No `-d` flag.** **Do not re-render.**
**Do not pass `--device` anywhere in this task.**

Per file record: `filename | scenario | label dt_s | decoded text | decode count`.
Decode count = middle field of `<DecodeFinished> 0 N 0`.

⚠️ Reported SNR/DT will NOT match injected values (−2.7 reads −0.5, +2.7 reads +2.2). **Expected.
Text only is gated.**

🔴 **Run the sweep TWICE and mechanically diff the two outputs** (HK-022). Assert, don't claim.

## 3. Read the gate

`N` = files producing **exactly one** decode with text `CQ Q1ABC FN42`.
Quantum = one file; thresholds integer; **no SE, no CI, no bootstrap** (HK-021(o)).
First row that fires wins; stop there.

| Row | Condition | Verdict |
|---|---|---|
| 0a | Either `dt+0.0` control fails | VOID — instrument. *(pre-satisfied under jt9, §0 of the 17:31Z doc)* |
| 0b | Any file yields **>1** decode | VOID — synth defect (HK-021(n)) |
| 1 | N = 20 | **PASS** |
| 2 | N ∈ {18,19}, all failures \|dt_s\| ≥ 2.4 | PASS, GRID BOUNDED — S3b truncated; *this is the parts-vs-wall-clock answer* |
| 3 | N ∈ {18,19}, ≥1 failure \|dt_s\| ≤ 2.1 | FAIL — non-monotonic. STOP |
| 4 | N ≤ 17 | FAIL. STOP |

## 4. Captain's 3 files — QA reads ALL.TXT, Captain says nothing

Captain opens, in WSJT-X, at their own pace:
`S3_part0_dt+0.0.wav` · `S3_part9_dt+2.7.wav` · `S3b_part9_dt-2.7.wav`

**QA reads `ALL.TXT` (now empty, so the whole file is the result) and reads the outcome from there.**
Do not ask the Captain what appeared. If the file is still empty afterwards, `File > Open` does not log to
`ALL.TXT` — **say so and escalate; do not substitute the Captain's eyes without asking.**

🛑 **NOT part of G3's gate — cannot pass or fail it** (HK-025: cannot change G3's verdict).
Separate consequence table, reported separately:

| ALL.TXT shows | Consequence |
|---|---|
| All 3 texts present | No constraint. S3b grid stands as jt9 validated it. |
| Control present, an extreme absent | 🔴 **`File > Open`'s aperture — not our synth — bounds the live run. S3b grid TRUNCATED. §5.1 HK-026 hazard CONFIRMED.** |
| Control absent | 🛑 WSJT-X config. STOP — live run cannot be armed. |

## 5. Report and STOP

Report: `ALL.TXT` contents · 20-row tally · `N` · row fired · exact jt9 command line · the
twice-run diff result · spot-check result in its own section.

**Never commit `ALL.TXT` or anything derived from it.** `artefacts/` only (gitignored). Grep every
file individually before committing (203 920-row `S1_matched.csv` precedent).

**Then STOP.** G4, parts-vs-wall-clock, and the S3 re-grid are Architect + Captain calls.
**No `src/` change. HK-011 not engaged. No push (HK-014).**
