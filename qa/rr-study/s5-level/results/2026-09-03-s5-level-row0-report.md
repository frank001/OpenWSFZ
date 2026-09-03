# `S5-LEVEL` ROW 0 report — scope of the `level_dbfs` normalisation defect

**QA, 2026-09-03 15:12Z** (`date -u`, HK-017). Base `main`@`b4dd754`, shim `20260049`.
Spec: `qa/rr-study/2026-09-02-2002-architect-to-qa-spec-s5-level-normalisation-scope-and-repair.md`
(Architect → QA, 2026-09-02 20:02Z). Script:
`qa/rr-study/s5_level_scope.py` (HK-021(r) — predicates shipped as code, not hand-computed), raw
output: `qa/rr-study/s5_level_scope_results.txt`.

**Headline: all four ROW 0 checks PASS. The Architect's §0 scope claims are confirmed mechanically,
not inherited.** The defect is real, narrow, and does not touch the S5 false-positive gate
arithmetic. Recommendation below, decision left to the PO per spec §7.

---

## 1. ROW 0 verdicts, with measured numbers

| Row | Check | Result | Measured |
|---|---|---|---|
| **0f** | Enumerate `scenarios/*.json` containing `level_dbfs`; count files and files with >1 distinct value | **PASS** | Exactly 4 files (`s5-noise.json`, `s5-noise-wide.json`, `s5-noise-wide-n300.json`, `s5-noise-diag40.json`); exactly 1 (`s5-noise.json`) has >1 distinct value (`{-20, -10}`, across parts 0–3: `[-20, -10, -20, -20]`). The other three each declare a single uniform `-20` across their one part. |
| **0g** | RMS dBFS per part, REAL `run_scenario.py --dry-run --dump-wav-dir` baseline render (peak-normalised) — reused from the `AWGN-FP` arm's own ROW 0b population, not re-rendered, so this check introduces no second noise source | **PASS** | Part 0 (declared −20 dBFS): mean **−20.87 dBFS** actual RMS, n=30, range [−22.69, −20.26]. Part 1 (declared −10 dBFS): mean **−21.24 dBFS** actual RMS, n=30, range [−22.23, −20.49]. Spread **0.37 dB** (threshold ≤ 2.0 dB). |
| **0h** | RMS dBFS per part, level-preserving re-render (`render_row0c_level_preserving.py`, skips the peak-renormalise step) | **PASS** | Part 0: mean **−26.18 dBFS**. Part 1: mean **−16.19 dBFS**. Step **9.99 dB** (target 10.0 ± 1.0 dB). |
| **0i** | `_finalize_playback_samples` and the main-loop call site both apply `_PLAYBACK_PEAK_LEVEL` | **PASS** | `_finalize_playback_samples` at `run_scenario.py:609` (definition), used inside its own body at `:610`/`:621`; a second, independent application at the main render loop, `:1158` (the spec's own text cites `:1156` — code has drifted three lines since the spec was written, same call site). `_PLAYBACK_PEAK_LEVEL` declared once (`:30`), applied at both sites. |

ROW 0f did not fire its STOP branch, so ROW 0g/0h/0i were all evaluated — none fired their own
STOP branches either. No escalation required.

## 2. Scope statement, as measured (not quoted from the spec)

- **The defect is confined to exactly one scenario file, `s5-noise.json`, and within it to exactly
  one pair of parts (0/1, both `noise_type: awgn`).** The other three `level_dbfs`-bearing files
  each declare a single value across their one part — a constant that cancels identically and
  changes nothing, confirmed by ROW 0f's own distinct-value count.
- **The peak-normalisation step is real, present at both code paths that matter, and is the
  mechanism**, confirmed directly (not inferred) by two independent measurements that bracket it:
  ROW 0g shows the *normal* render path collapsing a declared 10 dB step to 0.37 dB; ROW 0h shows
  the *same seeds, same amplitude formula*, with only the renormalisation step removed, recovering
  9.99 dB — within 0.01 dB of the declared step. ROW 0i confirms the normalising code is not a
  one-off in the offline dump path: the identical constant and helper apply before live hardware
  playback too, so this has been true of every S5 sweep ever run, not only offline replays.
- 🛑 **What is NOT in scope, confirmed by ROW 0f's own enumeration:** S1, S2, S3, S7, S8 (no
  `level_dbfs` key at all), and S5 parts 2/3 (carrier/multi-carrier, not AWGN — `level_dbfs`
  present but at the same `-20` as part 0, so even if it *were* functional it would still equal
  part 0's declared level).

## 3. What this defect does and does not touch

**Untouched — do not restate any of these as being in question:**
- The S5 false-positive gate arithmetic: `4/60`, `1/60`, `3.3%/N=120`, and every other
  ratified-era S5 FP figure. The gate counts AWGN slots (60 = 2 parts × 30 trials); they were 60
  slots delivered at one actual level either way, which is exactly what ROW 0g/0h measured.
- `AWGN-FP` ROW 0c's ±10 dB level-dependence finding (baseline/−10/+10 → 6/7/7 events, all
  in-band, PASS). ROW 0h confirms that reading's own rendering path (the same
  `render_row0c_level_preserving.py`) actually delivered the declared step — ROW 0c's validity is
  **strengthened**, not merely assumed, by this report.
- S1/S2/S3/S7/S8 in their entirety (no `level_dbfs` key exists in any of their scenario files;
  ROW 0f's enumeration is exhaustive, not a sample).

**Void, and corrected in this session (§4):**
- Any claim that S5 parts 0 and 1 constitute a *level contrast*. They are two replicates of one
  delivered condition and have been since the scenario file's parts were authored, 2026-06-20.
  `STUDY-SPEC.md`'s R&R-009 table (part labels "AWGN moderate"/"AWGN hot") and `s5-noise.json`'s
  own part 0/1 `note` fields both carried this framing; both are corrected below. The FP *event
  counts* those table rows carry (37 and 15) are unaffected data and are retained unedited — only
  the level-contrast interpretation of the row labels is struck.

## 4. Record correction (spec §4, required under either repair option) — DONE this session

1. ✅ `qa/rr-study/scenarios/s5-noise.json` — part 0/1 `note` fields replaced with a factual,
   dated statement that both render to the same delivered level, pointing at this report and the
   measurement. Re-parsed and confirmed valid JSON after the edit.
2. ✅ `qa/rr-study/STUDY-SPEC.md` — R&R-009's part table: row labels de-editorialised
   ("AWGN moderate (−20 dBFS)" / "AWGN hot (−10 dBFS)" → "AWGN (−20 dBFS declared)" /
   "AWGN (−10 dBFS declared)"), a dated correction paragraph inserted immediately after the table
   with the measured numbers and pointers to this report and the script. Event-count data (37/15)
   left untouched, per §4's own instruction not to rewrite history — only the interpretation was
   corrected.
3. ✅ No historical sweep report (`qa/rr-study/results/*/report.md`) was edited — per spec §4 item
   3 and the project's own "extends, never overwrites" convention, those stand as what the
   instrument reported at the time.

## 5. Recommendation to the PO — QA does not pick, per spec §7

**QA concurs with the Architect's own recommendation: Option 2 (delete `level_dbfs`, declare S5
single-level).** Reasoning, stated for the PO's own judgement rather than as a derivation (the
Architect's own honesty framing in spec §3 applies equally to QA's concurrence):

- Option 2 changes no delivered audio on any future sweep — every one of the fifteen historical
  full sweeps stays comparable to the sixteenth, with no re-baseline needed.
- The one reading that would motivate paying Option 1's price — a genuine level axis showing
  level-*dependent* false-accept behaviour — does not exist: `AWGN-FP` ROW 0c (now corroborated by
  this report's ROW 0h, §3) found the false-accept rate flat across a genuine ±10 dB range at
  n=60/leg.
- Option 1's cost is not contained to S5: changing the peak-normalisation reference affects the
  delivered audio for *every* scenario on the next sweep (spec §3), which is a much larger
  decision than repairing one mislabelled part pair, and — per the Architect's own framing — should
  be taken deliberately as a new instrument with its own paired re-baseline, not folded into a bug
  fix.

**This is a recommendation, not a ruling.** Per spec §7, the choice between Option 1 and Option 2
is the PO's; nothing in this report or the record correction above depends on which is chosen (the
correction is honest either way — it states what has actually been delivered, not what will be
delivered after a repair).

## 6. NFR-021

No callsign-shaped, noise-hallucinated, or otherwise sensitive content in this report or in
`s5_level_scope.py`/`s5_level_scope_results.txt` — this arm measures RMS amplitude on signal-free
AWGN buffers only; no decode, no message text, no `*_matched.csv`-style output was produced or
read. Scanned by inspection (all three files) rather than the project's `nfr021_pre_merge_scan.py`
CALL_RE, since there is no callsign-shaped surface here to miss — confirmed by reading, not
assumed.
