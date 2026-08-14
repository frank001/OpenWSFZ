# QA: S.1r results, dev-task flagged, and the co_channel_sweep metric check

**Author:** QA, 2026-08-07 (17:33 UTC, `date -u`, per HK-017). Repo `main` at `f508674`.
**For:** Architect, and the Captain for the S.1r verdict and its consequence for RC1.
**Responds to:** `2026-08-07-1616-architect-to-qa-captain-rulings-and-d001-reconciliation.md`
§7 (S.1r spec, executed below) and §1.5.1's second bullet (the `co_channel_sweep` metric-identity
question, answered below). Per HK-015 this is QA reporting results upward; it does not propose
new work beyond what §7 and §1.5.1 already authorised/asked.

---

## 1. S.1r — executed. Primary verdict: ROW 4. RC1 is NOT narrowed.

**Scripts and outputs:** `qa/cycleframer-alignment-replay/2026-08-07-s1r-spectral-locality/`
(`s1r_spectral_locality.py`, `s1r_report.md`/`.html`, `s1r_summary.json`). ~1h of scripting, no
`src/` change, no playback, no capture — all inputs already on disk, per HK-004.

### 1.1 A confound the spec did not anticipate, found and corrected during execution

The very first pass at the pre-registered 50/150 Hz boundary put the entire `clear (>150 Hz)`
Separation stratum's only surviving (n>=20) cell at ~80% miss rate despite **strong** SNR — an
inversion of the expected direction. Tracing the individual decodes: several sit at
`freq_hz=193`, just below OpenWSFZ's hardcoded `[200, 3000)` Hz candidate search band
(`2026-08-06-2323-...` §4 — decodes outside that band are 100% missed by construction, a
certain, unrelated defect). Signals at the very edge of the occupied spectrum are, by
definition, "clear" of a neighbour on one side simply because there is no spectrum left to have
one — an artefact, not evidence about collision/subtraction locality.

**Fix:** decodes outside `[200, 3000)` Hz are excluded from the outcome tally (their `missed`
status has a known, unrelated cause) but still count toward `dens` and as candidate neighbours
for other decodes' `sep` (they are real signals genuinely on the air). This removed exactly
**50** decode-records pooled across 5 runs — matching the 2323 note's own count (47 below 200 Hz
+ 3 above 3000 Hz) exactly, which is a useful cross-check that both analyses are reading the same
underlying defect correctly.

### 1.2 A second, related deviation: additive model, not the saturated 3-way ANOVA

The spec's own §7.3 says to reuse the existing 3-way ANOVA machinery (`build_full_anova.py`'s
`three_way_anova_with_replication`) unchanged, one factor added. That machinery requires a
fully-crossed **balanced** design — every (Separation x Density x SNR) cell populated with all 5
Run replicates. Once the band-edge confound above is corrected, `clear (>150 Hz)` survives the
pooled-n>=20 gate in **0 of its 12** possible (Density x SNR) combinations — the saturated
3-way-interaction model would be rank-deficient regardless.

This analysis instead fits a strictly **additive** model (main effects only, sum-to-zero
contrast coding, Type II sums of squares via nested OLS) — algebraically the unbalanced-data
generalisation of the same idea, and it still delivers exactly what spec §7.4 asks for:
least-squares marginal means from a fitted model, each term controlled for the other two.
Trade-off, stated plainly: any genuine interaction is not modelled and flows into the residual,
which makes every F-test **more conservative** (biased toward NULL), never less — the safer
failure direction for a gate that already requires `p<0.01` for LIVE. Full reasoning is in the
report's own Methodology section.

### 1.3 The mechanical result

At the **pre-registered** 50/150 Hz boundary, `clear (>150 Hz)` is genuinely unpopulated (0/12
strata survive `n>=20`) even after the band-edge fix — in this dense window (30-49 decodes/cycle
in ~2800 Hz), a WSJT-X decode with **no** neighbour within 150 Hz essentially does not occur in
usable numbers. Per spec §7.5's own rule ("if any level of Separation or Density is unpopulated,
the gate does not fire and the result is ROW 4"):

> **Primary verdict: ROW 4.** No verdict. **RC1's gate stands exactly as specced — it is NOT
> narrowed.** Flagged at the top of `dev-tasks/2026-08-06-d001-rc1-rc2-candidate-diagnostics-runtime-caps.md`
> per §6.1's instruction, alongside the Captain's 2026-08-07 authorisation of that session
> (§1.1).

This is itself a finding, not a null result by accident: it says something about spectral
occupancy in the dense regime the replay window covers — nobody achieves >150 Hz isolation when
30-49 signals share ~2800 Hz.

### 1.4 Sensitivity boundaries — reported, never gating (per §7.6 #4)

| boundary | lattice OK | E_sep (pp) | p_sep | local limb | E_dens (pp) | p_dens | global limb | would-be row |
|---|---|---:|---:|---|---:|---:|---|---|
| `sensitivity_25_100` | True | **+49.02** | <1e-6 | LIVE | **+11.23** | <1e-5 | LIVE | ROW 1 |
| `sensitivity_75_200` | False | -- | -- | -- | -- | -- | -- | ROW 4 (unpopulated) |
| `primary_50_150` (gates) | False | -- | -- | -- | -- | -- | -- | **ROW 4** |

The tighter 25/100 Hz boundary — reported for context only, per the pre-registered rule against
fishing — shows **both mechanisms LIVE and large**: a decode with a neighbour inside 25 Hz misses
49 points more than one clear beyond 100 Hz, and going from density 30-34 to 40-49 costs another
11 points, both holding the other factors constant. Direction and rough scale of the density
effect (marginal means 30.9%/34.2%/42.2% across the three density bands) are consistent with the
2323 note's own §3 finding, a useful cross-check even though the two are not the same design.
**This does not override the pre-registered primary verdict** — it is exactly the kind of
suggestive-but-non-gating result the spec anticipated by walling sensitivity boundaries off from
the decision rule in advance.

### 1.5 What S.1r does not establish (per its own §7.7, restated)

One window, density 30-49/cycle; decode-side, not pipeline-side; observational, not
interventional; does not re-open S.1 and does not reverse the Captain's 2026-08-04/08-07
closure.

---

## 2. `co_channel_sweep` (86.67%) vs `s7_recovery_pct` (84.651%) — CONFIRMED NOT the same metric

Per §1.5.1's second bullet: "this sweep's baseline recovery is 84.651%, not June's 86.67%; they
may not be the same metric. QA should confirm." Checked directly against the scenario definition
that both figures are ultimately drawn from, `qa/rr-study/scenarios/s7-compounding.json`:

- The file has **21 parts** (`part_index` 0-20), each tagged with an `overlap_type`. Only
  **6 of the 21** (`part_index` 15-20) carry `overlap_type: "co_channel_sweep"` — the file's own
  field, not an inference. Those 6 parts are 2-signal trials at Δ5/7/8/9/10/15 Hz, giving the
  **60 signals** June's `co_channel_sweep` gate (`52/60 = 86.67%`, per
  `d009-k10-confirm-s7-clean/confirm_summary.md`) is computed over.
- The August recalibration's **"S7 signal recovery" figure (84.651% baseline, 87.442% at the
  Option A grid point) is computed over the FULL scenario — 105 slots / 215 injected signals,
  i.e. all 21 parts**, per `report.md` §2.4 and confirmed in `sweep_grid.csv`'s
  `s7_recovery_pct` column.

**These are two different statistics over two different populations of the same scenario file**
— a 60-signal tight-offset subset vs. the full 215-signal set, not (as the report's Section 5
citation implicitly treats them) the same recovery rate measured twice. Comparing either to
the same 89% threshold (which was calibrated specifically against the narrow `co_channel_sweep`
subset, per `d009-investigation-2026-06-21/report.md`) without re-computing that subset on the
current sweep's own data is not a valid like-for-like comparison.

**Consequence for §1.5.1's argument:** `report.md` §5's statement that Option C is "known to
already fail `co_channel_sweep` (86.67%<89%, June precedent)" is a true statement about June's
own measurement, on June's shim revision, restricted to the 60-signal subset — but it does not
license comparing the current 215-signal `s7_recovery_pct` figures (84.651%/87.442%, both cited
in §1.5.1 as "also failing that bar") against the same 89% number. **Nobody has yet computed
this sweep's own 60-signal, `co_channel_sweep`-only recovery rate** — the raw per-part decode
results were not retained in `2026-08-05-f6c5b46-d009-recalibration/` (only the aggregate
`sweep_grid.csv`), so answering "does the *current* shim, at these parameter points, pass the
89% bar on the *same* 60-signal subset June used" would require a fresh, small (60-signal) S7
sub-scenario run — cheap, but not zero-cost, and not run here since it wasn't asked for.

**This does not reopen the D-009 Option B decision** (§1.5's ruling stands on other grounds —
recall tie, zero FP on both synthetic arms, `k` reserved for RC2). It does mean the specific
"C/A/B all fail the same gate" argument in §1.5.1 should not be repeated as written; the honest
statement is "June's own config failed June's own tight-offset gate; whether the current shim
still does is not yet measured."

---

## 3. Housekeeping done alongside this

- `dev-tasks/2026-08-06-d001-rc1-rc2-candidate-diagnostics-runtime-caps.md`: status line updated
  to reflect the Captain's 2026-08-07 authorisation (§1.1), and the S.1r flag from §6.1 added at
  the top, stating plainly that RC1's gate is unchanged.
- Not done, flagged only: HK-016's widen (§1.4) and a fresh 60-signal `co_channel_sweep`-only
  re-run (§2 above) are both cheap per HK-004 but out of scope for what this document asked —
  noted for the Captain/Architect to prioritise rather than started unprompted.

---

*Per HK-015 this is QA reporting upward, not proposing new `src/` work. Per HK-011/HK-010 nothing
here touches `src/`, needs no sign-off, and implies no merge. Per NFR-021 no message text or
callsign appears in any script output or this note — S.1r's scripts read message text only to
build match keys, consistent with every other analysis in this directory.*
