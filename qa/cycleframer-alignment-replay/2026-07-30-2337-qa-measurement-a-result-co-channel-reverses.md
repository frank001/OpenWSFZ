# D-001 Measurement A -- RESULT: co-channel withdrawal REVERSES

**Author:** QA, 2026-07-30 (23:37 UTC, `date -u`, per HK-017).
**For:** Architect (ruling owed per the reading rule below), and the Captain (escalation, per
the same rule).
**Answers:** `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` S5,
which authorised this measurement and pre-registered its reading rule before the run.
**Script/data:** `measurement_a_snr_recall.py`, `measurement_a_snr_recall_report.md`,
`measurement_a_recall_by_snr.png` (all in this directory).

---

## 0. Summary

Measurement A ran exactly as designed in S5. The mechanical outcome, applying the
pre-registered reading rule with no discretion exercised, is:

> **DENSE BANDS SIT MATERIALLY BELOW SPARSE AT MATCHED SNR (36.0 pts max separation, far past
> the 10-pt bar; 80m-recall >= 20m-recall in 26/26 usable common-support bins).**
> **The co-channel withdrawal REVERSES. Per S5.3: "Escalate to the Captain before any further
> work."**

This is the opposite of the outcome that would have left row 4's target as pure sensitivity.
At matched reference SNR, the densest band (20m, 36.4 decodes/cycle) recalls dramatically worse
than the two sparser bands (10m at 8.5/cycle, 80m at 3.4/cycle) -- by 10 to 36 points, across
the *entire* measured SNR range, not just at the margins. A fixed-sensitivity deficit cannot
produce this: it would show up as a horizontal shift of one curve relative to another (same
shape, offset threshold), not a uniform vertical gap that holds from -24 dB to +28 dB alike.

## 1. Self-check (S5.2, mandatory before any reading)

All four corpora reproduced their published ANOVA matched-decode counts **exactly**:

| corpus | matched (this run) | published | status |
|---|---:|---:|---|
| 10m | 9177 | 9177 | OK |
| 20m | 24201 | 24201 | OK |
| 80m | 8290 | 8290 | OK |
| 40m (WSJT-X, context only) | 52736 | 52736 | OK |

The matching logic (identical key and multiplicity handling to `anova_common.py`'s
`match_pairs()`) has not drifted. The run is valid per S5.2's own gate.

## 2. What was measured

Per S5.2's design: reference decodes binned by the *reference's own* reported SNR (2 dB bins,
never OpenWSFZ's SNR -- S7's gain error means the two scales disagree, and mixing them would
have reintroduced that as noise into this measurement). Recall = matched / total per bin, with
95% Wilson intervals. Three jt9-referenced bands (10m/20m/80m) form the decisive comparison; the
40m live-WSJT-X corpus is reported as a separate, non-pooled context series per S3.2/S5.2 (it
sits on the drifting device -- see the capture-clock-drift defect report -- so its curve shape
below the healthy-window average is not interpretable here and is not part of the reading).

## 3. The result, read against the pre-registered rule

Common-SNR-support region across all three jt9-referenced bands, n >= 20 decodes/bin/band (26
usable bins, -24 dB to +28 dB):

| SNR | 10m | 20m | 80m |
|---:|---:|---:|---:|
| -24 to -22 dB | 13.8% | 11.1% | 44.7% |
| -8 to -6 dB | 74.9% | 39.6% | 75.5% |
| 0 to 2 dB | 83.5% | 51.2% | 86.2% |
| 12 to 14 dB | 95.9% | 71.9% | 88.9% |
| 26 to 28 dB | 92.6% | 84.3% | 96.6% |

(Full 26-bin table in `measurement_a_snr_recall_report.md`.)

- **Max separation: 36.0 points** (at -4 to -2 dB: 10m 79.4%, 20m 45.3%, 80m 81.3%). Wilson
  intervals at that SNR are +-2-3 points on each band -- the gap is not sampling noise.
- **80m-recall >= 20m-recall in every one of the 26 usable bins.** The two sparser bands sit
  above the densest band at every SNR level measured, from the weakest signals to the strongest.
- **10m and 80m track each other closely** (typically within 5-10 points, crossing a few times
  at high SNR where n per bin is smaller and CIs overlap) and both sit consistently, sharply
  above 20m. The separation is not a smooth density gradient across all three bands -- it reads
  as "20m behaves differently from the other two," which is worth flagging rather than
  smoothing over (HK-018).

Per S5.3's table, this is squarely the second row: *"Dense bands sit materially below sparse at
matched SNR (>= 10 pts, monotone in density)"* -> *"Competition, not sensitivity. The co-channel
withdrawal REVERSES. Escalate to the Captain before any further work."* No other row of the
table fits -- 36 points is more than 3x the 10-point bar, and the direction is consistent (not
crossing, not non-monotone) across the entire common-support region.

## 4. One observation, not a reinterpretation

The 10m/80m closeness versus 20m's much larger shortfall raises a natural question: is this
"decode density" generally, or specifically "20m's decode density," possibly interacting with a
fixed resource limit (`K_MAX_CANDIDATES = 140`, per the `d001-c1-candidate-cap-sweep` work
already on record)? 20m carries roughly 4x 10m's density and 11x 80m's. **This is not measured
here and is not being proposed as a finding** -- S5.3 is explicit that no reading beyond the
table is authorised, and per the closing handoff's cost discipline this is exactly the kind of
mechanism question that belongs to whoever picks up the escalation, not to QA extending the
measurement's scope unilaterally today. Recorded so it isn't re-discovered from nothing.

## 5. What this does NOT do

- Does not re-open the diagnostic programme as a standing QA-initiated effort -- this measurement
  was authorised in advance by the Captain via the Architect's ruling S5, with its reading rule
  fixed before the run (S5.3), exactly as that section specifies.
- Does not itself decide the row 4 vs row 1 vs row 5 menu question -- S5.3's own consequence
  column routes this to escalation, not to a QA conclusion.
- Does not touch `src/` or native code (HK-011). No push, no merge (HK-014/HK-010) -- committed
  locally and stops here. No `pre_merge_check.py` run implied (HK-006).
- Does not invalidate the 40m corpus reporting already on record -- its context-only series here
  is additive, not a new claim about it.
- NFR-021: message text was read only to build match keys (identical to `anova_common.py`) and
  never printed or written; only aggregate per-bin counts left the script.

## 6. Cross-references

- `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` S5 -- design,
  cost estimate, and the reading rule this document applies mechanically.
- `measurement_a_snr_recall.py` -- the script; `measurement_a_snr_recall_report.md` -- full
  59-bin-per-band table; `measurement_a_recall_by_snr.png` -- the overlay plot.
- `qa/endurance/anova_common.py` -- matching/normalisation logic reused, not reimplemented.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` -- why the 40m series here is context-only.
- `qa/endurance/2026-06-13-.../` `d001-c1-candidate-cap-sweep` work -- source of the
  `K_MAX_CANDIDATES = 140` figure referenced in S4 as an unmeasured observation, not a finding.

---

*Per HK-015 this is QA -> Architect/Captain material. Per HK-014/HK-010 committed locally, no
push, no merge. Per HK-011 nothing here touches `src/`. Per HK-017 filename and byline both
carry `date -u` UTC. The escalation itself, and the row 4/1/5 decision, remain the Captain's.*
