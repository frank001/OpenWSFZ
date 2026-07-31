# QA — Measurement D RESULT: competition confirmed as a named, measured mechanism (ROW 1 fires)

**Author:** QA, 2026-07-31 (12:45 UTC, `date -u`, per HK-017). Repo at `e60d0b7`.
**Answers:** `2026-07-31-0853-architect-to-qa-measurement-d-spec-within-band-density.md`, authorised
by the Captain on `2026-07-31-0029` §1.4.
**Script/data:** `measurement_d_within_band_density.py`, `measurement_d_report.md`,
`measurement_d_recall_by_snr.png` (this directory).
**Note on the spec's §0 disclosure:** the Architect ran an exploratory version of this
measurement before being redirected to specify it instead, saw a result, and deliberately
withheld it — the Captain holds those figures. This write-up was produced blind to them, per
that disclosure's own requirement. If they disagree, that is itself a finding to chase, not
mine to reconcile.

---

## 0. Headline

**ROW 1 FIRES. Competition is confirmed as a named, measured mechanism — not 20m-specific, not
a density-law artefact of cross-corpus confounds.** Inside 20m alone, holding band, antenna,
receiver, and session constant, cycles in the top density quartile recall **18.21 points worse
at matched reference SNR** than cycles in the bottom quartile (median across 26 usable bins),
and this holds in **22 of 26 bins (85%)**, comfortably clearing the pre-registered ≥8pt/≥80%
bar. **Per the reading rule's own consequence: escalate to the Captain before any engineering.**
The row 4 decomposition re-scopes toward competition; it does not proceed on today's authorship.

## 1. Self-checks — all four pass

| # | check | result |
|---|---|---|
| 1 | Matching gate | **PASS** — 20m=24,201, 10m=9,177, 80m=8,290, all exact |
| 2 | Density contrast | **PASS** — 20m 2.20x (23.15→50.97/cycle), 10m 2.28x (5.17→11.78), 80m 4.01x (2.21→8.83). 20m clears the ~2x bar |
| 3 | Duplicate-key artefact | **PASS** — 20m dup-rate gap 0.24pt vs median diff 18.21pt (gap is 1.3% of the effect, nowhere near "within an order of magnitude"). 10m/80m gap is exactly 0.00pt |
| 4 | Common support | **PASS** — 20m 26 usable bins, 10m 20, 80m 26 — well above the ~10-bin floor |

Run is not void. Proceeding to the decisive reading.

## 2. Strata definitions

| band | sparse cutoff | dense cutoff | sparse mean density | dense mean density |
|---|---|---|---:|---:|
| **20m** | ≤30 ref decodes/cycle | ≥43 ref decodes/cycle | 23.15/cycle | 50.97/cycle |
| 10m | ≤6 | ≥10 | 5.17/cycle | 11.78/cycle |
| 80m | ≤3 | ≥7 | 2.21/cycle | 8.83/cycle |

Density = the reference (jt9) decoder's own decode count per cycle throughout, per spec S2 —
never OpenWSFZ's own count. Matching resolved once per band, over the full corpus, in reference
arrival order (identical mechanism to `measurement_a_snr_recall.py`'s `recall_by_snr_bin`); the
stratum a cycle belongs to only selects which stratum's bin table its outcome is tallied into,
never re-resolving the match.

## 3. Per-bin recall — 20m (DECISIVE)

Full table in `measurement_d_report.md`. Summary: sparse recall exceeds dense recall in **24 of
26 bins**, with the gap growing from single digits at the SNR extremes to a broad plateau of
+17 to +24 points across the entire mid-range (roughly −16dB to +18dB, where the bulk of the
matched decodes sit). The two negative bins sit at the very ends of the range
([−24,−22)dB: −4.2pt, n≈220 both strata; [24,26)dB: −7.9pt, n=23/132) — the smallest-n bins in
the table, consistent with sampling noise rather than a reversal of the effect.

**No disagreement between the printed verdict and the visible table** — unlike Measurement A,
where the auto-generated "monotone" line overrode a human observation that should have caught
it. Here the per-bin pattern is unambiguous on inspection: a large, consistent, one-directional
gap across nearly the entire usable range, not a mixed or crossing pattern.

Median diff: **+18.21 points.** 22/26 bins (85%) at or above the 8pt bar.

## 4. Replication bands — reported, not decisive

| band | median diff | bins ≥8pt | contrast |
|---|---:|---:|---:|
| 10m | +7.81 pts | 10/20 (50%) | 2.28x |
| 80m | +3.63 pts | 7/26 (27%) | 4.01x |

Both point the same direction as 20m (sparse recalls better than dense) but at smaller
magnitude and lower bin-consistency — neither would independently clear row 1's bar. Per the
spec, these do not override or dilute the 20m reading; they are reported for completeness.

## 5. Reading rule — quoted verbatim, applied to 20m only

| # | condition | reading | consequence |
|---|---|---|---|
| 1 | median `diff` ≥ 8 pts AND ≥ 80% of usable bins have `diff ≥ 8` | At the same signal strength we miss more when the band is busier, with band identity held constant. | **Competition confirmed as a named, measured mechanism.** Row 4's decomposition re-scopes toward it. **Escalate to the Captain before any engineering.** |
| 2 | else if −3 < median `diff` < 3 | Density does not act within a band. | The cross-band effect is 20m-specific and the density law is withdrawn entirely. |
| 3 | else if median `diff` ≤ −3 | Sparse recalls worse than dense. | Escalate. Do not rationalise. |
| 4 | else | Partial. | Report as ambiguous. Do not interpret. Escalate. |

Evaluated in strict order (no row-overlap possible, unlike Measurement A's rule). **20m: median
diff +18.21, 85% of bins ≥8pt → ROW 1 fires, unambiguously.** Not close to any other row's
boundary.

## 6. Descriptive extras — inform mechanism, not subject to the reading rule

### 6.1 Effect size vs. density contrast — points toward absolute density, not a ratio law

| band | contrast (dense/sparse) | median diff |
|---|---:|---:|
| 20m | 2.20x | +18.21 pt |
| 10m | 2.28x | +7.81 pt |
| 80m | 4.01x | +3.63 pt |

**80m has the largest contrast (4.01x) and the smallest effect; 20m has the smallest contrast
(2.20x) and the largest effect.** If competition scaled with the *ratio* between strata, 80m
should show the biggest gap — it shows the opposite. What tracks the effect size instead is
**absolute density**: 20m's two strata (23.15/cycle, 50.97/cycle) sit far above 80m's (2.21,
8.83) in raw terms, and the median diff tracks that ordering exactly (20m > 10m > 80m in both
absolute density and effect size). **This is consistent with a threshold/capacity mechanism —
something that only bites once occupancy is high in absolute terms — rather than a
proportional density law.** Descriptive; not a finding on its own per the spec, but a concrete
lead for whoever scopes the row 4 decomposition.

### 6.2 Our decodes/cycle vs. the reference's — a visible capacity ceiling

| band | bucket | mean ref/cycle | mean ours/cycle |
|---|---|---:|---:|
| 20m | Q1 (sparsest) | 23.15 | 14.16 |
| 20m | Q2 | 35.09 | 19.15 |
| 20m | Q3 | 40.89 | 21.67 |
| 20m | Q4 (densest) | 52.32 | 23.01 |
| 10m | Q1 | 5.17 | 4.33 |
| 10m | Q4 | 12.61 | 9.32 |
| 80m | Q1 | 2.21 | 2.15 |
| 80m | Q4 | 9.61 | 8.20 |

**20m shows the clearest flattening**: as the reference's per-cycle count climbs from 23.15 to
52.32 (+126%), ours climbs from 14.16 to 23.01 (+62%) — decelerating at each step (+5.0, +2.5,
+1.3 per quartile step, against the reference's roughly steady rise). 10m and 80m show much
milder flattening. **20m's dense quartile (52.32 ref decodes/cycle) is well above the ~19/cycle
regime the `2026-07-26-c1-candidate-cap-sweep-findings.md` sweep tested** — that sweep is on
record as measuring a ~1% marginal yield from raising `K_MAX_CANDIDATES`, but explicitly at a
density this measurement did not reach. Per the standing citation-blacklist entry
(*"`K_MAX_CANDIDATES` is untested in the dense regime, not refuted"*), this table is a concrete,
free reason to treat that question as live rather than closed, if and when it is priced and
authorised. **Not proposed as a task here** — per the spec's own boundary (§7), any follow-up
touching native rebuilds is a different cost class and returns to the Captain, priced,
separately.

**Implementation note on this table's bucketing:** for this descriptive table only, quartiles
are cut by simple index position (`n//4`, `n//2`, `3n//4`) over the sorted per-cycle density
list — a different (simpler) method than the `statistics.quantiles(..., method="exclusive")`
cutoffs used for the decisive sparse/dense stratification in §2–§5. This does not affect the
reading; it is flagged for transparency since the two "quartile" boundaries in this document are
not numerically identical constructions.

## 7. What this does not do

- **Does not itself re-scope the row 4 decomposition.** Per the reading rule's own consequence,
  this escalates to the Captain before any engineering; it does not authorise it.
- **Does not authorise any follow-up measurement** (e.g., re-running the c1 sweep in the dense
  regime). Per spec §7, that is a different cost class and returns to the Captain, priced,
  separately — not started off the back of this run.
- **Does not touch `src/` or native code** (HK-011). Read-only analysis of already-committed
  artefacts.
- **Does not re-open the diagnostic programme** (closing handoff §0). One arm, one stop rule.
- NFR-021: message text used only to build match keys via `anova_common`'s own convention;
  never printed beyond aggregate counts.

## 8. Cross-references

- `2026-07-31-0853-architect-to-qa-measurement-d-spec-within-band-density.md` — the spec this
  executes in full, including its three confound warnings and the duplicate-key check that
  turned out (correctly) not to be the story here.
- `2026-07-31-0029-architect-ruling-measurements-abc-and-drift-root-cause.md` §1.4 — the
  authorisation and power calculation (20m p90/p10=2.23, ~13pt predicted effect) this measures
  against; the observed 18.21pt exceeds that prediction.
- `2026-07-31-1232-qa-measurement-a-correction-escalated.md` — Measurement A's corrected
  reading (20m-specific deficit, mechanism unknown), which this measurement was designed to
  explain and now does: competition, not a 20m-specific artefact.
- `qa/endurance/anova_common.py` — matching/normalisation logic reused throughout.
- `2026-07-26-c1-candidate-cap-sweep-findings.md` — the sweep §6.2 above notes was never run in
  the dense regime this measurement's 20m-dense stratum actually reaches.

---

*Per HK-015 this is QA → Architect/Captain material. Per HK-014/HK-010 committed locally, no
push, no merge. Per HK-011 nothing here touches `src/`. Per HK-017 filename and byline carry
`date -u` UTC. Per the spec's own instruction, this was written without seeing the Architect's
withheld exploratory figures — any disagreement between the two is to be chased, not
reconciled quietly.*
