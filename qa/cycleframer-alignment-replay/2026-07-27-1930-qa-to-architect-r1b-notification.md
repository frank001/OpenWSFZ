# D-001: QA -> Architect notification — R.1b fired row 2 (anti-correlation), not row 3

**Author:** QA, 2026-07-27 (19:30). **For:** the Architect, per HK-015.
**Answers:** `2026-07-27-1900-architect-r1-acceptance-and-r2-revision.md` §5 (R.1b), run per its own
reading rule.
**This is a notification carrying a result, not an escalation QA cannot resolve** — same posture as
the R.1 notification.

---

## 1. Result

**Row 2 of your §5 table fires at K=4@2000: anti-correlation.** 11 of 12 tolerance cells put the
true recov648 rate below the null mean; 10 of those 11 put it below the null's entire 8-trial
*range*, not just its mean — e.g. 5 Hz/0.16 s: true 22.2% against a null floor of 31.8% (9.6 points
clear). Only the published ±10 Hz/±0.5 s cell (your R.1 result) separates the other way. At K=10@600
the direction is consistent across all 12 cells but the effect is too small relative to the null's
own spread (~220 candidates/cycle, 9x fewer than K=4@2000) to confirm on its own.

Full tables in `2026-07-27-r1b-tight-tolerance-null-findings.md`.

## 2. Reading, per your own table, applied

> True materially below null at tight tolerance → **Anti-correlation.** The detector systematically
> does not fire where these signals are. Strongest available pointer at the sync scoring metric;
> R.3's D-miss class is expected to dominate and R.3 becomes the confirmatory arm, not the
> exploratory one.

Not row 3 ("true separates above null at some tolerance τ") — there is no τ at which true ever
separates upward once you leave the ±10 Hz/±0.5 s cell that R.1 already flagged as measuring density.

## 3. Why I'm routing this back rather than proceeding to R.2 as revised

Two things follow mechanically from your own §5/§6/§7, stated as observations for your ruling, not
QA judgement calls on study direction:

1. **No separation tolerance τ exists to size R.2's grid from.** Your §9 already flagged the widened
   grid as "still a guess if R.1b returns no separation tolerance" — that branch is the one that
   fired. The two-lattice-step grid in §6 stands only on your judgement, not a measurement, exactly
   as you anticipated.
2. **R.2 as designed (planting signals at controlled offsets from a known lattice point, measuring
   what that offset does to demodulation) doesn't test the mechanism row 2 points at.** Anti-
   correlation says the detector doesn't fire near these signals at all — a scoring/detection-metric
   question. R.2 answers "what does an offset cost," which presupposes a candidate exists to be
   offset. R.3's D-miss/E-loss/X-loss split is the arm built to see this. Your §7 already promotes
   R.3 to always-run and R.4 ahead of it; this result is a reason to weigh whether R.2 still belongs
   ahead of R.3 in sequence, or whether R.1b's own result makes R.3 (or R.4, already first) more
   urgent than a grid you've already flagged as unmeasured.

Not doing: starting R.2 or R.3 in this session. Holding per the same discipline R.1 established.

## 4. What is and is not affected

Nothing in §3 (C.4's +2, B.2's E=5.69, C.3's SNR split, B.1/B.1b's 437) is touched by this — R.1b is
downstream of the same tolerance question R.1 already settled for those. This result sharpens *why*
row 4's front end is failing (a detection question, not merely an imprecision question) without
changing anything about *how much* it's failing (437, unchanged).

## 5. Request

Rule on R.2's grid / sequencing given no τ was returned, and on whether R.1b's anti-correlation
result changes how R.3 (or R.4, if not yet run) should be designed to specifically test the sync
scoring metric rather than only estimator precision.

## 6. Cross-references

- `2026-07-27-r1b-tight-tolerance-null-findings.md` — full result.
- `2026-07-27-1900-architect-r1-acceptance-and-r2-revision.md` §5, §6, §7, §9 — the design and the
  caveat this result lands on.
- `2026-07-27-r1-coincidence-null-findings.md` — R.1, which this extends.

---

*Per HK-014, nothing here is pushed or merged. Per HK-011, nothing here touches `src/` or native
code — R.1b was offline analysis against already-frozen artefacts only.*
