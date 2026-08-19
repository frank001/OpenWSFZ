# QA → Architect: G3 primary readout — jt9 x 20, twice, diffed. ROW 1 FIRES.

**UTC:** 2026-08-19 18:01Z
**Executes:** `2026-08-19-1737-architect-to-qa-G3-START.md` Sec.2-3, under the 17:31Z gate
amendment. Thresholds verbatim from 17:09Z, unchanged, quoted below.
**Result: N = 20 / 20 -> ROW 1 fires -> PASS. Extended-range synth is sound across the full grid.**

---

## 1. ALL.TXT — read whole file, human reports nothing

The Captain's spot check (3 files) had already run before this task started; `ALL.TXT` was found
at 189 bytes / 3 lines, matching the board's prior report exactly (not re-triggered by me):

```
_part0_dt+0.0    14.074 Rx FT8     11 -0.5 1500 CQ Q1ABC FN42
_part9_dt+2.7    14.074 Rx FT8     10  2.2 1500 CQ Q1ABC FN42
_part9_dt-2.7    14.074 Rx FT8     12 -0.5 1500 CQ Q1ABC FN42
```

Verified unchanged (still 189 bytes / 3 lines) after the jt9 sweep below — jt9 with `-a`/`-t`
pointed at a scratch temp dir does not write to the WSJT-X profile's `ALL.TXT`, as expected; the
two instruments are fully separate. Not copied into the repo or `artefacts/`; read in place only.

## 2. Exact jt9 command line

Per file, one invocation per file, twenty files, run twice (forty invocations total):

```
D:\WSJT\wsjtx\bin\jt9.exe -8 -a <scratch-tmp> -t <scratch-tmp> <one-file.wav>
```

`-8` = FT8. **No `-d` flag** (default depth). `<scratch-tmp>` is a fresh `tempfile.TemporaryDirectory`
per invocation, never `qa/` or `artefacts/` shared state. Script:
`artefacts/g3_jt9_sweep_2026-08-19/run_g3_jt9_sweep.py` (gitignored, not for commit).

## 3. Twice-run diff (HK-022)

Diffed on two levels, both clean:

- **Gate-relevant fields** (`decoded_texts`, decode count from `<DecodeFinished>`'s middle field):
  **0 files differ, run1 vs run2.**
- **Full raw stdout** (includes SNR/DT/freq, which are NOT gated and were expected to be stable
  but not asserted as such in advance): **0 files differ, run1 vs run2** — byte-identical stdout
  on all 20 files across both runs. Not merely claimed; mechanically diffed
  (`g3_jt9_sweep_diff.json`, `diff_count: 0`).

## 4. 20-row tally (run1; run2 identical per §3)

`N` = files producing exactly one decode of `CQ Q1ABC FN42`.

| File | dt_s (label) | Decode count | Text | Pass |
|---|---|---|---|---|
| S3_part0_dt+0.0.wav | +0.0 | 1 | CQ Q1ABC FN42 | Y |
| S3_part1_dt+0.3.wav | +0.3 | 1 | CQ Q1ABC FN42 | Y |
| S3_part2_dt+0.6.wav | +0.6 | 1 | CQ Q1ABC FN42 | Y |
| S3_part3_dt+0.9.wav | +0.9 | 1 | CQ Q1ABC FN42 | Y |
| S3_part4_dt+1.2.wav | +1.2 | 1 | CQ Q1ABC FN42 | Y |
| S3_part5_dt+1.5.wav | +1.5 | 1 | CQ Q1ABC FN42 | Y |
| S3_part6_dt+1.8.wav | +1.8 | 1 | CQ Q1ABC FN42 | Y |
| S3_part7_dt+2.1.wav | +2.1 | 1 | CQ Q1ABC FN42 | Y |
| S3_part8_dt+2.4.wav | +2.4 | 1 | CQ Q1ABC FN42 | Y |
| S3_part9_dt+2.7.wav | +2.7 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part0_dt+0.0.wav | +0.0 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part1_dt-0.3.wav | −0.3 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part2_dt-0.6.wav | −0.6 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part3_dt-0.9.wav | −0.9 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part4_dt-1.2.wav | −1.2 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part5_dt-1.5.wav | −1.5 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part6_dt-1.8.wav | −1.8 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part7_dt-2.1.wav | −2.1 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part8_dt-2.4.wav | −2.4 | 1 | CQ Q1ABC FN42 | Y |
| S3b_part9_dt-2.7.wav | −2.7 | 1 | CQ Q1ABC FN42 | Y |

**N = 20 / 20.**

## 5. Gate read (verbatim from 17:09Z / 17:31Z, HK-021(o) — integer thresholds, no SE/CI)

| Row | Condition | Fired? |
|---|---|---|
| 0a | Either `dt+0.0` control fails | No — both `S3_part0` and `S3b_part0` decoded correctly, count=1 each |
| 0b | Any file yields >1 decode | No — every file's `<DecodeFinished>` middle field = 1 |
| **1** | **N = 20** | **YES — fires here. Stop.** |
| 2 | N in {18,19}, failures only at \|dt_s\|>=2.4 | not reached |
| 3 | N in {18,19}, a failure at \|dt_s\|<=2.1 | not reached |
| 4 | N <= 17 | not reached |

**Row fired: 1 — PASS. Extended-range synth is sound across the full grid.**

## 6. Spot-check result (separate section, NOT part of G3's gate — HK-025)

Already reported on the board (2026-08-19, "G3 SPOT CHECK DONE"), reproduced here for completeness
since §1 confirms the same `ALL.TXT` state independently:

| File | Result |
|---|---|
| `S3_part0_dt+0.0.wav` (control) | Decoded, `CQ Q1ABC FN42` |
| `S3_part9_dt+2.7.wav` (positive extreme) | Decoded, `CQ Q1ABC FN42` |
| `S3b_part9_dt-2.7.wav` (negative extreme) | Decoded, `CQ Q1ABC FN42` |

Per the amendment's consequence table: **all 3 present -> no constraint. S3b's grid stands as
jt9 validated it.** The §5.1 HK-026 aperture hazard did not materialise on either instrument.

## 7. Commit hygiene

Nothing containing `ALL.TXT` content, or derived from it, is staged. All raw jt9 stdout and JSON
artefacts live under `artefacts/g3_jt9_sweep_2026-08-19/` (blanket-gitignored, confirmed via
`git check-ignore`). This report contains only the synthetic `CQ Q1ABC FN42` text (Q-prefix,
NFR-021-clean) and no real callsigns.

---

**STOP per §5 of the START doc.** G4, the parts-vs-wall-clock call, and the S3 re-grid ruling
remain Architect + Captain decisions. No `src/` change. HK-011 not engaged. No push (HK-014).
