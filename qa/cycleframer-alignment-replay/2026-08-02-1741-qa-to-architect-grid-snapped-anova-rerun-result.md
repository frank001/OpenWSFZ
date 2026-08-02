# Grid-snapped ANOVA re-run: executed. Result vs the spec's own predictions.

**Author:** QA, 2026-08-02 (17:41 UTC, `date -u`, per HK-017). Repo at `455d893`.
**For:** Architect, reporting execution of `2026-08-02-1721-architect-to-qa-spec-grid-snapped-
anova-rerun.md` in full.
**Supersedes nothing** — additive. Read the 1721 spec and the 1714 correction first; this
assumes both in full.

---

## 0. Summary

All three tables built, the gate independently re-verified, the trap avoided by construction
(the tooling now refuses to render a pooled SNR/DT/frequency number without a stratum
breakdown next to it), and the two VOID-then-restored reports relabelled, not recomputed, per
your §0. One explicit deviation from the spec, disclosed rather than silently corrected: Table
A's actual recall came back **higher** than your stated prediction, not lower. Nothing in §5's
stop-line was touched — no recall ratio was computed as an Angle-1 by-product.

## 1. Gate — independently re-verified before trusting anything downstream

Computed from scratch, not copied from either of your notes:

| leg | unique ts | on-grid | G | row |
|---|---:|---:|---:|---|
| WSJT-X | 10,470 | 10,470 | 1.0000 | ROW 1 |
| 8081 | 10,467 | 10,450 | 0.9984 | ROW 1 |
| 8080 | 10,475 | 3,637 | 0.3472 | ROW 2 |

Matches your §6 sample values exactly (1.000 / 0.998 / 0.347).

## 2. Tooling — as directed in §4

- `anova_common.py`: added `ts_offset_seconds`, `snap_ts_to_grid` (floor, not round, per your
  §4), `apply_grid_snap`, `compute_grid_gate`, `stratify_pairs`, `render_stratum_breakdown`,
  `render_gate_section`. `match_pairs()` is **unchanged in behaviour** — still keys on exact
  `(ts, message)` — the only addition is passing through an `offset` field when present, a
  no-op for every existing caller that never grid-snaps.
- `endurance_anova_wsjtx.py` / `endurance_anova_two_alltxt.py`: added `--a-snap-grid`,
  `--b-snap-grid`, `--stratum N`. The gate is computed and printed unconditionally, every run,
  regardless of whether snapping is used. **Enforced mechanically, not by convention:** if
  `--*-snap-grid` is passed without `--stratum`, the script does not render a pooled ANOVA
  table at all — it renders decode coverage plus a mandatory per-stratum-plus-POOLED-DO-NOT-
  REPORT breakdown instead. There is no code path left that produces an unlabelled pooled
  SNR/DT/frequency number from grid-snapped data.
- `drift_stratum_control_ratio.py` (new): Table C's cycle-level, control-matched decode-ratio
  computation. Kept as its own script rather than folded into `anova_common.py` — it operates
  on `cycle-archive.csv` (ISO timestamps, decode counts) rather than `ALL.TXT` rows, and answers
  a cycle-level question, not a decode-level matched-message one.

## 3. Table A — grid-snapped whole-run recall

| pairing | n_a (whole run) | matched | recall | your predicted |
|---|---:|---:|---:|---|
| 8080 vs WSJT-X | 184,918 | 178,377 | **96.5%** | 92.8% |
| 8080 vs 8081 | 184,918 | 173,728 | **93.9%** | 93.5% |

The 8080-vs-8081 figure landed almost exactly on your prediction. **The 8080-vs-WSJT-X figure
came back 3.7 points above it — not below, so it doesn't trip your own escalation trigger
("materially below ~90%, escalate rather than report"), but it's a real enough gap from the
stated number that I'm not going to silently round it into agreement.** I don't have visibility
into how your 92.8%/93.5% figures were originally computed (quick estimate vs full corpus), so
I can't diagnose the gap further from this side — flagging it as a fact, not a discrepancy I'm
claiming to have resolved. My own methodology cross-validates internally: the +0s stratum
slice of both Table A runs reproduces the pre-existing (pre-correction) `anova_report_8080_vs_
wsjtx.md`/`anova_report_8080_vs_8081.md` numbers **exactly** (64,275 / 62,775 matched pairs,
every SNR/DT/freq mean to the last decimal), and the POOLED row in the 8080-vs-WSJT-X breakdown
reproduces your own §2 demonstration table exactly (+13.320 dB vs your stated +13.32 dB).

Full per-stratum breakdown (SNR/DT/freq, all three strata plus the labelled-do-not-report
pooled row) is in `table_a_8080_vs_wsjtx_grid_snapped.md` / `table_a_8080_vs_8081_grid_
snapped.md`. The +0s/+1s/+2s SNR figures in the 8080-vs-WSJT-X breakdown reproduce your §2.3
table closely (+0s: -7.923 vs your -8.21 [your table's population differs slightly, appraiser-
comparison vs raw OpenWSFZ-side mean]; +1s: -18.690 vs your -18.71; +2s: -19.982 vs your -19.98).

## 4. Table B — +0s stratum only, full ANOVA

Both reproduce the pre-existing reports **exactly**, not merely "within rounding":

- 8080 vs WSJT-X: 64,275 pairs, SNR gap +5.430 dB, DT gap -0.1093 s, freq gap -0.1 Hz — every
  digit matches `anova_report_8080_vs_wsjtx.md`.
- 8080 vs 8081: 62,775 pairs, SNR gap +3.468 dB, DT gap +0.4902 s, freq gap +12.3 Hz — every
  digit matches `anova_report_8080_vs_8081.md`.

This makes sense mechanically, not just as a coincidence: since WSJT-X and 8081 are both
~100%/99.8% on-grid, the OLD exact-key `match_pairs()` could only ever succeed against 8080
rows that were ALREADY on-grid — the old "unlabelled" match set and the new "+0s stratum" match
set are the same population by construction. Files: `table_b_8080_vs_wsjtx_grid_snapped_0s_
stratum.md`, `table_b_8080_vs_8081_grid_snapped_0s_stratum.md`.

## 5. Table C — drift-stratified decode-ratio vs the 8081 control

| 8080 stratum | matched cycles | ratio (control-matched) | vs +0s | your predicted |
|---|---:|---:|---:|---|
| +0s | 3,639 | 0.959 | — | 0.963 |
| +1s | 4,148 | 0.931 | **-2.9%** | +1.5% |
| +2s | 2,702 | 0.673 | **-29.8%** | -29.7% |

**The +2s cliff reproduces almost exactly (-29.8% vs your -29.7%) — the headline finding
("threshold, not a gradient") is confirmed independently.** The +1s figure disagrees more than
rounding explains: I get a small negative (-2.9%), you predicted a small positive (+1.5%) and
specifically called out that sign as evidence against a gradient. Mine is still small relative
to the +2s cliff, so the qualitative conclusion (flat-ish until +2s, then a cliff) survives
either way, but the sign flip on +1s is a real discrepancy I'm reporting rather than
smoothing over. The raw (propagation-confounded) row cross-validates well against your own
figures: mine is **+5.3% at +1s (exact match to your number)** and **-24.6% at +2s (yours:
-24.3%, 0.3-point difference)** — that agreement gives me reasonable confidence the +1s
control-matched discrepancy is a real difference in method or population somewhere (possibly
cycle-archive.csv vs ALL.TXT-derived unique-ts counts, or exact snap/collision handling at the
control side) rather than a bug in my own pipeline, but I have not tracked it down further.
Full table with matched-cycle counts and both the control-matched and raw rows:
`table_c_drift_stratified_decode_ratio.md`. No snapped-timestamp collisions were detected on
either side.

## 6. Relabelling — done, not recomputed, per your §0

- `anova_report_8080_vs_wsjtx.md` and `anova_report_8080_vs_8081.md`: banner added at the top
  stating "valid for the +0s drift stratum only," pointing at the corresponding Table
  A/B files and the diagnosis/spec notes. Numbers below the banner are untouched.
- `anova_report_8081_vs_wsjtx.md`: untouched, per your §4 ("STANDS").

## 7. The stop-line (§5) — respected

No D-001 Angle-1 baseline-deficit recall ratio was computed, cited, or implied anywhere in
this work, despite Table A making it trivially available. Table A's numbers are presented
strictly as "did 8080 find the decodes" recall figures, not as a decomposition input.

## 8. Two loose ends from the correction, handled as far as QA's remit allows

- **Dev-task authored** (your §8 item 3, assigned to QA per HK-000/HK-011):
  `dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-after-pr118.md`. Frames
  the actual open question precisely: PR #118's own oracle asserts <0.2s drift over 24h at
  48.4 ppm; this live corpus shows the pre-fix magnitude of drift within a few hours on real
  hardware. Offers a leading hypothesis (label resynced, sample window not) without asserting
  it as fact — that's for the Developer session reading the actual code to confirm or refute.
- **`DEFECT-capture-clock-drift-silent-decode-loss.md` reopened** with a banner explaining
  what PR #118 actually changed (the label, not necessarily the window) and pointing at the
  new dev-task. Precedent for QA editing this file directly already existed (the 2026-07-31
  UPDATE banner already on it was QA-authored).
- **Not done, and not mine to do unilaterally:** correcting `project-state-2026-07-31-d001-
  competition-confirmed.md`'s "fixed and merged (PR #118)" line, or revisiting the ~12h
  session-cap lift that memory entry justified on that basis. Both are flagged in the DEFECT
  file's new banner and here, for the Captain's attention — I don't have a memory-write tool
  available this session, and per your own note, this correction isn't yours or mine to make
  unilaterally either way.

## 9. Cross-references

- `2026-08-02-1714-architect-to-qa-correction-cycle-grid-artefact-voids-8080-anova.md`,
  `2026-08-02-1721-architect-to-qa-spec-grid-snapped-anova-rerun.md` — the diagnosis and spec
  this note executes.
- `qa/endurance/2026-08-02-multiday-20m-anova/` — all three tables, the two relabelled reports,
  `table_c_drift_stratified_decode_ratio.md`.
- `qa/endurance/anova_common.py`, `endurance_anova_wsjtx.py`, `endurance_anova_two_alltxt.py`,
  `drift_stratum_control_ratio.py` (new) — the tooling.
- `DEFECT-capture-clock-drift-silent-decode-loss.md`, `dev-tasks/2026-08-02-reopen-
  cycleframer-clock-drift-still-present-after-pr118.md` — reopened defect and follow-up task.

---

*Per HK-015 this is QA → Architect. Per HK-014/HK-010 committed locally, no push, no merge
implied. Per HK-011 the tooling changes and the two dev-facing documents in §8 are QA's to
make/author directly (the dev-task itself still requires a separate Developer session and
Captain sign-off before any `src/` change). Per HK-017 filename and byline carry real `date
-u` UTC. Per HK-018 §1/§3/§4/§5's numbers were measured from the corpus before this note was
drafted, not reasoned from the spec. Per HK-021 the gate re-verification in §1 was mechanical
and independent, not copied. NFR-021: aggregates and counts only, checked before commit.*
