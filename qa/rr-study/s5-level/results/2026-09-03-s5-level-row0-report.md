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

---

## 7. AMENDMENT 1 EXECUTION — 2026-09-03 ~16:40Z (QA) — Option 2 deletion + ROW 0j/0k/0l

**PO ruled Option 2** (delete `level_dbfs`, S5 single-level) on §5's recommendation plus the
Architect's concurring one. This section extends the report (project convention: extend, never
overwrite) with the deletion's own execution and the three pre-registered checks the amendment
requires before trusting it (spec Amendment 1 A1.3). Script:
`qa/rr-study/s5_level_deletion_verify.py` (HK-021(r)), raw output:
`qa/rr-study/s5_level_deletion_verify_results.txt`. ROW 0k's decode comparison is a new xunit Fact,
`Row0k_S5LevelDeletion_DecodeSetsIdenticalBeforeAfter` in
`tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs` (HK-015: the decode seam is `internal`, only
reachable from a test assembly — same reasoning as every other `AWGN-FP` decode check). Zero
`src/`/`native/` diff (`git diff --stat -- src/ native/` empty, re-verified after every edit in
this section).

### 7.1 What was deleted, and what stayed

`level_dbfs` removed from all four scenario files it appeared in (`s5-noise.json`,
`s5-noise-wide.json`, `s5-noise-wide-n300.json`, `s5-noise-diag40.json`) — the parts' `note` fields
updated in place to record the deletion, dated. Per spec A1.2, `qa/rr-study/awgn-fp-replay/
scenarios/` (`s5-noise-row0c-minus10.json`, `-plus10.json`, `s5-noise-m1m4.json`) was **not**
touched — confirmed by grep, the key is still present there, functionally (the ROW 0c ±10 dB legs
depend on it) or as a pinned, dated artefact of the completed M1–M4 arm.

### 7.2 ROW 0j — byte-identity — **FAIL** (part 1 only, 1 LSB max)

Rendered S5 parts 0/1 for the same 60 in-chain seeds through the real, unmodified
`--dry-run --dump-wav-dir` path after the deletion (`awgn-fp-replay/_work/row0j_after/`), SHA256'd
against the pre-existing pre-deletion population (`_work/row0b_baseline/`, the `AWGN-FP` arm's own
ROW 0b anchor render — reused, not re-rendered, so ROW 0j introduces no second render of the
"before" state).

| Part | Declared before | Default after deletion | Pairs identical |
|---|---|---|---|
| 0 | −20 dBFS | −20 dBFS (same) | **30/30** |
| 1 | −10 dBFS | −20 dBFS (default) | **0/30** |

**60/60 required for PASS; got 30/60 → ROW 0j FAILS.** Not a surprise — spec A1.1 point 2 flagged
this exact risk ("two different float multiplies followed by a division are not guaranteed
bit-identical"). Measured directly on the WAV samples (int16 PCM): **max absolute difference 1
LSB**, affecting **788 of 5,400,000 samples** (0.0146%) across the 30 mismatched part-1 pairs —
floating-point rounding noise from peak-normalisation dividing by a different pre-normalisation
amplitude, not a mechanism failure. Per spec A1.3, ROW 0j's FAIL routes to ROW 0k.

### 7.3 ROW 0k — decode-invisibility — **PASS**

Decoded both 60-slot populations (`row0b_baseline` before, `row0j_after` after) through the
existing `AwgnFpReplayTests` seam and compared, per slot, the full decode set (count, message,
freq, DT, reported SNR).

**60/60 slots identical → ROW 0k PASSES.** The 1-LSB difference does not move the decoder's output
at all, on any of the 60 slots. Per spec A1.3: **"Option 2 lands, with the byte difference
disclosed in the report and on the board — never silently."** This section is that disclosure. The
STOP branch (revert, record-correction-only) is **not** taken.

NFR-021: the two decode CSVs this Fact produced (`row0k_before_decodes.csv`,
`row0k_after_decodes.csv`) carry the same class of noise-hallucinated callsign-shaped message text
as every other `AWGN-FP` decode CSV. Redacted before commit: `redact_row0k_decodes.py` (same
method as `redact_m1_m4_decodes.py` — imports the project's own scanner, HK-022, guards every
flagged token against both renders' `truth.csv` `message_text` columns first — 0 of 6 flagged
tokens found in truth, S5 being signal-free the guard set is 0 messages anyway), byte-level
UTF-8-BOM/CRLF-preserving rewrite (9 CRLF before/after, both files), re-scanned to 0. Map:
`REDACTION-MAP-ROW0K.md` (`K`-infix placeholders, distinct from ROW 0's `<RDCTnn>` and M1–M4's
`<RDCTMnn>`).

### 7.4 ROW 0l — `truth.csv` consumers survive the empty `true_snr_db` — **PASS**

Copied the historical `2026-09-02-3b52608` sweep's CSVs into a gitignored scratch directory (under
`awgn-fp-replay/_work/`, removed again at the end of the run — never left on disk, never
committed), ran `harness/analyse.py --run-dir` once unmodified (baseline), then blanked
`true_snr_db` on every S5 row of both `S5_matched.csv` (1,030 rows) and `truth.csv` (60 rows) —
exactly what `run_scenario.py:1113`'s new default (`part.get("level_dbfs", "")` → `""`) produces —
and ran `analyse.py` again.

**Both runs exit 0. `stdout` and `report.md` are byte-identical before vs. after** (Python
`==` comparison on the full text, not a diff-count heuristic). `render_report.py` also exits 0 on
the resulting `report.md`. Confirms directly — not merely by code-reading the `pd.to_numeric(...,
errors="coerce")` coercions spec A1.1 point 3 cites — that no S5 figure (FP event rate, decode
rate, 95% UB, κ) changes: **WSJT-X 0/60 (UB 4.87%), OpenWSFZ 4/60 (event rate 6.67%, UB 14.61%)**,
identical in both runs.

### 7.5 Verdict

**All three A1.3 checks resolved: ROW 0j FAIL (disclosed, 1 LSB, part 1 only) → ROW 0k PASS
(decode-invisible) → Option 2 EXECUTED, not reverted.** ROW 0l PASS confirms the empty
`true_snr_db` column is inert downstream. `STUDY-SPEC.md`'s R&R-009 correction paragraph carries
the required dated addition (spec A1.4) recording the deletion and this section's outcome.

**Nothing in §1–§5 above is disturbed by this section** — the ROW 0 scope checks were run before
the deletion, against the then-current (level_dbfs-bearing) scenario files, and remain a correct
record of what those files looked like at that time.
