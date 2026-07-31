# QA — Measurement A correction, escalated as `0029` §1.3 states it (dev-task 3)

**Author:** QA, 2026-07-31 (12:32 UTC, `date -u`, per HK-017). Repo at `90dbb63`.
**For:** the Captain (escalation), and the record (script/report correction).
**Origin:** `2026-07-31-1222-architect-to-qa-outstanding-work-after-task4.md` §4, itself
executing `2026-07-31-0029-architect-ruling-measurements-abc-and-drift-root-cause.md` §1.

---

## 1. The corrected reading — escalated, not interpreted further

Per `0029` §1.3, applied mechanically against the pre-registered reading rule (S5.3):

- **The co-channel withdrawal is dead.** Separation across the three jt9-referenced bands
  (10m/20m/80m) is 36.0 points — nowhere near the <5pt "curves overlay" bar row 1 needs. The
  pure-sensitivity explanation (a fixed dB-scale deficit acting through the SNR mix, predicting
  a horizontal shift) is refuted by a vertical gap holding from −24dB to +28dB.
- **The reversal is NOT licensed.** Row 2 ("dense bands sit materially below sparse, monotone
  in density") requires both a ≥10pt separation *and* the recall ordering to actually follow
  density (80m ≥ 10m ≥ 20m, since 80m is sparsest and 20m densest of the three). The separation
  condition holds; the monotonicity condition does not.
- **Rows 3 and 4 both fire.** The full three-band ordering holds in only 15 of 26 common-support
  bins (58%) and fails — curves genuinely cross — in the other 11 (42%): 10m dips below 20m at
  the low-SNR end ([−22,−20) dB) and rises above 80m repeatedly through the upper half of the
  range. Per the rule's own text, that means: *"Partial/ambiguous... do not interpret further"*
  **and** *"not anticipated by any current model... do not rationalise it."*

**What this establishes, and what it does not:** there is **one 20m-specific deficit of large
magnitude (10–35 points against the better of the other two bands) with no identified
mechanism** — not a density gradient, not evidence of co-channel competition. The withdrawal is
dead; competition is not established in its place. **The row 4 decomposition stays gated**,
unchanged from `0029` ruling §8 — it targets a different engineering problem depending on which
of these is true, and committing to the wrong one is exactly the wrong-sized commitment the B.3
menu caveat warns against.

**Where this originated: the rule's drafting, not QA's execution.** `0029` §1.1 already
established this and it bears repeating in the correction rather than leaving it implicit: rows
3 and 4 of the pre-registered rule are not mutually exclusive as written, and a rule that lets
two rows fire simultaneously without saying which one governs is a defect in the rule, not in
reading it. The original "monotone" verdict was a defensible reading of an under-specified test
(the outer band pair only) — not a QA execution error.

## 2. Script fix — `measurement_a_snr_recall.py`, lines ~196–226

Two defects, both now fixed and the script re-run to confirm:

**Defect 1 — `monotone_count` tested only the outer band pair.** `recall(80m) >= recall(20m)`
was checked (the two extreme-density bands) while `recall(10m)` — the middle band by density —
was never examined at all. Every one of the 26 common-support bins happens to satisfy the
outer-pair test (80m's recall is always the highest of the three), so the old check reported
26/26 = 100% "monotone" regardless of what 10m was doing, and the report printed *"Co-channel
withdrawal REVERSES"* from that alone.

**Fixed:** the check now tests the full three-band ordering (`80m >= 10m >= 20m`) required for
density to actually order the curves. Re-run result: **holds in 15/26 bins (58%), fails — curves
cross — in 11/26 (42%)**.

**One precision note, not a substantive change:** `0029` §1.2's own manual recomputation quotes
"10 of 26" bins failing `recall(80m) >= recall(10m)` specifically — that pairwise test alone.
The full chained ordering (which also requires `recall(10m) >= recall(20m)`, separately failing
at one additional bin, [−22,−20)dB, per that same section) fails in **11** of 26 once both
conditions are combined. Same conclusion either way (rows 3+4 both fire); the exact count is
11, not 10, once measured mechanically by the script rather than by hand from the pairwise
sub-tables.

**Defect 2 — the outcome if/elif chain could only ever print one row's verdict**, even when the
data satisfies two rows' conditions at once (exactly the rows-3-and-4 overlap this rule has).
Silently resolving that via elif precedence is the same failure shape as defect 1 — a script
picking one label when the honest answer is "both apply, escalate." Fixed: the script now
detects the overlap explicitly and prints it as its own outcome rather than picking a side.

Confirmed by re-running: `>>> MECHANICAL OUTCOME: ROWS 3 AND 4 BOTH FIRE (non-monotone in
density, AND curves cross in 11/26 bins) -> the reversal is NOT licensed... ESCALATE, do not
interpret further, do not rationalise.` All four corpora's self-checks still reproduce the
published ANOVA matched counts exactly (20m=24201, 10m=9177, 80m=8290, 40m=52736) — the fix
touched only the monotone/outcome logic, not the matching or binning.

## 3. Report corrected

`measurement_a_snr_recall_report.md` and `measurement_a_recall_by_snr.png` regenerated by the
fixed script (committed alongside this document). The auto-generated outcome line now reads
correctly; no hand-editing of the report was needed since the fix was to the script that
generates it.

## 4. What this does not do

- Does not touch `src/`. No push, no merge (HK-014/HK-010) — committed locally. No
  `pre_merge_check.py` (HK-006).
- Does not re-open the diagnostic programme — this is dev-task 3 of the already-authorised
  queue, per the closing handoff §0's stop rule.
- Does not deliver the row 4 decomposition — still owed by the Architect, still gated, now on
  Measurement D per `0029` §1.4/§8.
- NFR-021: no message text in any of the above; only aggregate per-bin counts.

## 5. Cross-references

- `2026-07-31-0029-architect-ruling-measurements-abc-and-drift-root-cause.md` §1 — the ruling
  this executes; §1.1's "drafting defect is mine" and §1.2's manual three-band recomputation.
- `2026-07-31-1222-architect-to-qa-outstanding-work-after-task4.md` §4 — this task's three
  parts, all completed above.
- `measurement_a_snr_recall.py`, `measurement_a_snr_recall_report.md`,
  `measurement_a_recall_by_snr.png` — the corrected script and regenerated output.
- `2026-07-30-2337-qa-measurement-a-result-co-channel-reverses.md` — QA's original (superseded)
  read of this measurement, the one `0029` §1 was answering.

---

*Per HK-015 this is QA → Captain/record material. Per HK-014/HK-010 committed locally, no push,
no merge. Per HK-011 nothing here touches `src/`. Per HK-017 filename and byline carry `date -u`
UTC.*
