# QA response to the two-session ruling -- R1/R3 closed, R4 noted for S.1

**Author:** QA, 2026-07-31 (15:50 UTC, `date -u`, per HK-017). Repo at `30f2c58`.
**Responds to:** `2026-07-31-1530-architect-ruling-measurement-d-corpus-is-two-sessions.md`.
**Captain's instruction:** proceed with R1, R3 and R4 as scoped in that ruling.

---

## 0. What was done

| ruling item | action | status |
|---|---|---|
| **R1** | Errata banner added to `measurement_d_report.md`, stating the false premise, pointing to this response and to the segment re-run | **Done** |
| **R3** | New script `measurement_d_segment_rerun.py` re-runs Measurement D's matched-SNR analysis on each segment separately, quoting both | **Done -- results below** |
| **R4** | S.1 has not yet run (gated behind the work order's Task 1 drift screen). Noted here for whoever runs it: **partition on the same boundary, segment 1 primary** | **Noted, not actionable yet** |

## 1. Independent verification of R1, before acting on it

Before amending anything, the two-segment premise was checked directly against
`cycle-archive.csv` rather than taken on the ruling's arithmetic alone (per this programme's own
new self-check 5, and per HK-018's spirit applied to QA as much as to the Architect):

- One gap > 5 min in the 20m archive: **18.46 h**, matching the ruling's "18 h 28 m."
- Segment 1: 2026-07-29 18:31:30 -> 21:14:30 UTC. Segment 2: 2026-07-30 15:42:15 -> 18:40:00 UTC.

**One discrepancy surfaced and was resolved before proceeding:** the raw archive gives 653
cycles in segment 1 (712 in segment 2, matching), but the ruling's own table (and this re-run,
independently) both land on **618** for segment 1. Traced to
`measurement_d_within_band_density.stratify_cycles`: density is keyed off the *reference*
decoder's rows, so a cycle with **zero** jt9 reference decodes never enters
`density_by_cycle` at all and is silently excluded from stratification. 653 - 618 = 35 zero-
reference-decode cycles in segment 1 (none in segment 2). This is pre-existing Measurement D
methodology, not something the segment split introduced or a new defect -- confirmed by the
segment re-run script (below) landing on the same 618/712 split via the same function, unmodified.

## 2. R3 -- per-segment matched-SNR re-run

Script: `measurement_d_segment_rerun.py`. Reuses `measurement_d_within_band_density.py`'s
`stratify_cycles`, `matched_stratified_bins`, `duplicate_key_rate`, `wilson_interval` and
`median_or_nan` unmodified, and `anova_common.filter_rows_by_window` (already existing, not
written for this) to split the 20m corpus at the 07-29/07-30 boundary. Full output:
`measurement_d_segment_rerun_report.md`.

| | segment 1 (primary) | segment 2 |
|---|---:|---:|
| cycles | 618 | 712 |
| sparse / dense cycles | 176 / 159 | 186 / 180 |
| density contrast | 2.65x | 1.64x |
| duplicate-key gap | 0.00 pts (not confounded) | 0.47 pts (not confounded) |
| usable bins (self-check 4) | 21 (OK) | 28 (OK) |
| median diff | **+22.33 pts** | +12.26 pts |
| bins >= 8 pts | 90% | 75% |
| **mechanical outcome (spec S4, unmodified)** | **ROW 1 -- Competition CONFIRMED** | ROW 4 -- ambiguous |

**Both self-checks 2-4 pass cleanly on both segments** (self-check 1 does not apply per-segment
by construction -- it validates the full-corpus published ANOVA count, noted as such in the
report rather than silently skipped).

### 2.1 Reading, stated plainly

- **Segment 1 alone clears the pre-registered ROW 1 bar decisively** -- median diff +22.33 pts,
  stronger than the suspended pooled figure of 18.21. Per R3/R4, segment 1 is primary and this
  is the figure to cite going forward in place of the pooled one.
- **Segment 2 alone does not mechanically clear ROW 1** -- median diff +12.26 pts is well above
  the 8-point threshold, but only 75% of its 28 usable bins clear 8 pts against the 80% bar, so
  the pre-registered rule lands it on ROW 4 ("partial/ambiguous... do not interpret"). Every one
  of its 28 bins but one is positive (27/28), so the direction is the same effect at a smaller,
  less consistent magnitude -- but the rule was fixed before this run and is applied as written,
  not relaxed because the pattern "looks like" a near-miss. Reporting it as ROW 4 rather than
  quietly reading it as a second confirmation is the discipline the ruling's R4 asked for.
- **Both segments are directionally consistent and neither contradicts the other or the
  pooled result.** Nothing here reopens R2 -- the effect is upheld, and segment 1 alone is now
  the stronger, cleaner citation for it.

## 3. R4 -- noted for S.1, not yet actionable

Per the work order (`2026-07-31-1356-...`), arm S.1 (spectral locality) has **not been run** --
it is gated behind Task 1 (the 8081/20m drift screen), which is separately outstanding and is
not part of this response. Recorded here so it is on the record before S.1 starts:

> **S.1 must partition its 20m corpus at the same 2026-07-29/07-30 boundary used above
> (segment 1 = 618 cycles, primary; segment 2 = 712 cycles), not run pooled.** S.1's reading
> rule (rev2 spec S4) is otherwise unchanged and pre-registered -- only the corpus partition
> changes, per the ruling's own distinction (R4).

No script or task file is created for this yet since S.1 itself has not been authorised to
start beyond what the work order already scoped, and Task 1 has not been run.

## 4. What is not touched

- `2026-07-31-1355-...-rev2-competition-scoped.md` and
  `2026-07-31-1356-...-work-order-after-measurement-d.md` -- Architect-authored, not QA's to
  edit (HK-015). The ruling's own §5 already re-derives rev2's numbers on segment 1; that
  supersedes those documents' pooled figures without this response needing to touch them.
- `measurement_d_report.md`'s body (self-checks 1-4, per-bin tables, plot) -- left as originally
  computed, per the ruling's instruction that nothing about the pooled run needs re-computing,
  only re-reading. Only the errata banner was added.

## 5. Boundaries

- **No `src/`** (HK-011). New QA scripts and reports only.
- **No push** pending the Captain's sign-off convention for this session; committed locally.
- **No `pre_merge_check.py`** (HK-006) -- not requested.
- **NFR-021:** aggregates and ratios only; no callsigns or message text in any output.

## 6. Cross-references

- `2026-07-31-1530-architect-ruling-measurement-d-corpus-is-two-sessions.md` -- the ruling this
  closes out R1/R3 for and notes R4 from.
- `measurement_d_segment_rerun.py` / `measurement_d_segment_rerun_report.md` -- R3's deliverable.
- `measurement_d_report.md` -- amended with the errata banner (R1).
- `measurement_d_within_band_density.py` -- reused unmodified, per the ruling's own instruction.
