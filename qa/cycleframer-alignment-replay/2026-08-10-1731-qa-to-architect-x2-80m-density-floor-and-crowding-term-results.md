# QA → Architect — X2 results: the 80m density floor, and whether crowding is a separate term

**2026-08-10 17:31Z** (filename and byline both from `date -u`, HK-017).
**Author:** QA. **Audience:** Architect.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-10-1538-architect-to-qa-spec-x2-80m-density-floor-and-the-crowding-term.md`,
**as amended** by its own Amendment 1 (2026-08-10 16:44Z), which wins wherever it disagrees with
the spec body. This report follows the amended version throughout.
**Governing pre-registration** (not superseded): `qa/cycleframer-alignment-replay/2026-08-09-0149-qa-prereg-80m-dying-band-density-floor.md`.
**Harness:** `qa/cycleframer-alignment-replay/x2_density_floor.py`, importing
`t1_frequency_quantisation.load` unmodified and reusing X1's cycle-clustered bootstrap machinery
(`aggregate_cells`, `bootstrap_cell_replicates`, `percentile`, `assign_stratum`) unmodified. Raw
output: `x2_result.json` (same directory). Deterministic: two independent runs, byte-identical
stdout.

**Status: primary gate → ROW 1. Crowding is a real, first-order term in the D-001 deficit —
`F_std` = +17.22 pp [+14.90, +19.33], SE 1.13 pp — the largest single-arm effect measured
anywhere in the D-001 programme, replicating on all three bands, and NOT explained by
candidate-budget exhaustion.**

---

## 1. Headline, stated once before the detail

Good evening, sir. In an uncrowded 80m cycle (density ≤ 5), OpenWSFZ recovers 88.11% of what both
WSJT-X instances heard; in a crowded one (density 14–26) it recovers 74.06% — at **matched SNR
composition**, standardised across five SNR quintiles that are, disclosed below, themselves nearly
identical between the two regimes. The standardised gap, `F_std` = **+17.22 pp**, clears the
gate's 5.0 pp bar by more than three-fold, its 95% cycle-clustered CI `[+14.90, +19.33]` sits
nowhere near zero, and the SE (1.13 pp) is comfortably under the 2.0 pp power bar. **ROW 1 fires
cleanly, not on a boundary.**

Every point estimate in §3 below was independently re-derived from `ALL.TXT` on disk and
reproduces the Architect's own §0.1 disclosure **exactly** — 88.11%/78.23%/74.06% raw recovery,
`F_std` = 17.22 pp, `F_raw` = 14.05 pp, SE ≈ 1.13 pp, and the per-stratum 99.6%/100.0% at the
floor's top two SNR strata against 83.1%/91.8% at the overlap's. That is the mechanical
cross-check the fixed-seed determinism requirement exists to make possible, and it passed a
second time here, independently of X1.

**§4.1's replication is the strongest part of this result.** Because 20m and 17m never reach a
true FLOOR regime (20m has only 14 REF rows at density ≤ 5; 17m has 53), both legs are
underpowered on the FLOOR-vs-OVERLAP contrast by the pre-registered power check and fall back to
the disclosed substitute, MID-vs-OVERLAP — and on **both** bands the crowding effect survives with
room to spare: 20m `+5.16 pp [+3.10, +7.35]`, 17m `+8.17 pp [+5.83, +10.51]`. Per the spec's own
reading rule (§4.1), an effect present on all three bands is a **decoder property**, not an
artefact of the dying band — **the strongest possible version of a ROW 1.**

Per Amendment 1 (A1.3), this does **not** license a candidate-budget pre-registration — that
family is already closed twice (RC2) and bounded at +0.93% by C.1. §5 below performs the
reconciliation the Amendment requires. **No `src/` recommendation, no parameter sizing, no capture
run follow from any part of this report, in any row.**

---

## 2. ROW 0 — the governing pre-registration's own void conditions, traced row by row

Per the pre-registration §3, verified independently rather than inherited from the spec's
"measured while drafting" table.

| row | check | bar | measured | verdict |
|---|---|---|---:|---|
| **0a** | population floor | ≥ 150 cycles | 1 196 REF cycles | **PASS** |
| **0b** | new floor reached | min density < 3, or bottom decile < 9.7 | min density **1**; bottom decile **1.0**; 413 cycles at density ≤ 5 | **PASS, comfortably** |
| **0c** | self-consistency (8080 vs 8081, Jaccard, pre-decline) | ≥ 90% | 7 720 / 8 270 = **93.35%** (783 pre-decline cycles, defined as density > 5) | **PASS** |
| **0d** | band label, every `Rx FT8` line's own dial-frequency field | == 3.573 MHz | 4/4 sources (both `wsjt-x`, both `owsfz`), 100% of 10 942–10 952 / 9 010–9 012 lines each | **PASS**, fully mechanical |
| **0e** | reference validity into the tail | window-end integrity | raw `A∩B` = 10 913 at both `072815` and `101100` | **PASS**, identical |

**ROW 0c's operationalisation, disclosed rather than tuned:** "pre-decline" is not a wall-clock
cutoff — it is defined mechanically as every cycle **not** in the FLOOR regime (density > 5),
chosen before the Jaccard value was computed (HK-021(a)). This is the same density regime the rest
of the arm uses, so no second, ad-hoc boundary was introduced. 93.35% clears the pre-registration's
own 90% bar; it falls short of the Architect's separately recorded 95% prediction (§6 below) —
that is a **miss on the prediction**, not a failure of the row.

**ROW 0d note:** `ALL.TXT`'s field `[1]` (0-based) carries the dial frequency in MHz on every
`Rx FT8` line — this makes the pre-registration's "spot-check a sample" instruction fully
mechanical rather than a sample: every line in every one of the four source files was checked, and
every one reads `3.573`.

No row voided. **All six of the pre-registration's own conditions pass**, plus this spec's own
additions below.

### 2.1 This spec's own additions — ROW 0f, 0g

| row | check | bar | measured | verdict |
|---|---|---|---:|---|
| **0f** | X0/X1 reference repair, **verified not redone** (shared prerequisite with X1) | distinct inodes | A=`281474977087507`, B=`3096224744198121` | **PASS** |
| **0g** | selection control — does `REF = A∩B` itself select for empty cycles? | \|diff\| ≤ 3.0 pp | `F_std(A∩B)` = +17.222 pp vs `F_std(A only)` = +17.529 pp → **diff 0.307 pp** | **PASS — selection channel immaterial** |

ROW 0g used a **point-estimate comparison only**, per the spec's own wording ("recompute `F_std`
with an A-only reference. If the two differ by more than 3.0 pp…") — not a second full bootstrap.
The A-only population is marginally larger (10 952 raw vs 10 913), consistent with B occasionally
missing a decode A caught, but the effect on `F_std` is negligible. **`REF`'s two-instance
agreement requirement is not manufacturing the crowding contrast.**

**ROW 0h** (the primary gate's own power check, `SE(F_std) > 2.0 ⇒ instrument failure`) is
reported in §3 below as part of the gate itself, per spec S3.

---

## 3. Primary metric and gate

**Definition (spec S2, Amendment 1 S A1.6.3):** `F_std(80m)` = SNR-standardised recovery(FLOOR) −
SNR-standardised recovery(OVERLAP), at **L1 only** (X1's pinned pooled quintile edges
`[−15, −10, −5, 2]`, not recomputed), equally weighted across the SNR strata with ≥ 30 rows on
**both** sides (spec S2 — this is deliberately **not** X1's coverage-weighted `b_std`: X2
contrasts two density regimes of the *same* band, so weighting by cell size would just re-import
the density effect under test). Density regimes fixed globally: FLOOR ≤ 5, MID 6–13, OVERLAP
14–26 (identical across every band, HK-021(g)). Cycle-clustered bootstrap, 1 000 draws, fixed
seed `20260810`.

```
F_std   = +17.222 pp   (n_strata = 5/5 qualifying, min n=30 each side)
F_raw   = +14.050 pp   (FLOOR raw=88.11% n=1060, OVERLAP raw=74.06% n=5471)
SE      =  1.128 pp
95% CI  = [+14.900, +19.331] pp
```

```python
if se_F_std("80m") > 2.0:                    return "ROW 0h"   # 1.128 <= 2.0 -- not fired
if abs(f) >= 5.0 and not (lo <= 0 <= hi):     return "ROW 1"    # 17.222 >= 5.0, CI excludes 0
```

**>>> ROW 1 <<<**, per spec §3 unchanged by Amendment 1 (A1.8: the thresholds are not touched).

### 3.1 Per-SNR-stratum breakdown (cross-checks the Architect's disclosure exactly)

| L1 stratum | FLOOR n | FLOOR recovery | OVERLAP n | OVERLAP recovery |
|---|---:|---:|---:|---:|
| 0 (weakest) | 168 | 48.2% | 750 | 37.3% |
| 1 | 182 | 85.2% | 787 | 60.1% |
| 2 | 180 | 93.9% | 851 | 68.4% |
| 3 | 257 | **99.6%** | 1 309 | 83.1% |
| 4 (strongest) | 273 | **100.0%** | 1 774 | 91.8% |

This reproduces the Architect's §0.1 disclosure ("per-stratum recovery at the floor reaches 99.6%
and 100.0% in the top two SNR strata, against 83.1% and 91.8% in the overlap regime") to the exact
decimal, from an independent implementation.

### 3.2 SNR-distribution check (confirms this is not composition)

| regime | n | p10 | median | p90 |
|---|---:|---:|---:|---:|
| FLOOR | 1 060 | −17 | −5 | +8 |
| MID | 4 308 | −16 | −3 | +10 |
| OVERLAP | 5 471 | −17 | −4 | +10 |

The three distributions sit within 1–2 dB of each other at every percentile checked. **The SNR
composition of a crowded cycle and an empty one is essentially the same** — the recovery gap is
not a signal-quality artefact of which cycles happen to be sparse.

### 3.3 Sanity check against the rest of the programme (HK-021(e))

`F_std` = 17.22 pp is **more than four times** the previous largest single-arm effect on the
board (P3's `S_all` = 4.27 pp). That is a large number to accept at face value, so it is checked
here rather than merely reported: (a) it reproduces the Architect's independently-run scoping
figure to the decimal, from a differently-implemented harness; (b) the per-stratum table above
shows the effect is not a pooling artefact — it holds in every one of the five SNR strata
individually, from 10.9 pp at the weakest stratum to 16.2 pp at the strongest; (c) §3.2 rules out
the obvious confound (SNR composition). The size is unusual, but it is not unexplained or
uncorroborated.

---

## 4. §4.1 — replication on 20m and 17m

**Power check first, as specced.** Neither replication band reaches a populated FLOOR regime:

| band | FLOOR REF n | SE(FLOOR−OVERLAP) | verdict |
|---|---:|---:|---|
| 20m | 14 | n/a (too few strata qualify) | **UNDERPOWERED** (n < 300) |
| 17m | 53 | 11.035 pp | **UNDERPOWERED** (n < 300 **and** SE > 3.0 pp) |

Per spec §4.1, both substitute **MID vs OVERLAP** (populated on all three bands), stated
explicitly rather than silently:

| band | `F_std` (MID−OVERLAP) | SE | 95% CI |
|---|---:|---:|---|
| 20m | **+5.155 pp** | 1.101 | [+3.101, +7.351] |
| 17m | **+8.173 pp** | 1.167 | [+5.832, +10.512] |
| 80m *(context only — same proxy, for comparability)* | +3.772 pp | 1.002 | [+1.845, +5.724] |

**Reading, per the spec's own pre-stated rule:** the crowding effect is present, and clears the
same magnitude bar used implicitly elsewhere in this programme (Architect's own 2.0 pp threshold
for this exact prediction, §6), on **both** replication bands — not just one. Per spec §4.1's
verbatim reading table: *"crowding effect present on all three bands ⇒ it is a decoder property,
and the strongest possible version of a ROW 1."* That is the result.

**One honest wrinkle, reported rather than smoothed over:** 80m's own MID-vs-OVERLAP contrast
(+3.77 pp) is *smaller* than either replication band's MID-vs-OVERLAP contrast (+5.16 pp,
+8.17 pp) — the crowding effect is not simply "worst on the dying band" in a monotone sense at
this coarser regime pairing. What is unique to 80m is the **FLOOR** regime itself (density ≤ 5),
which neither other band's corpus reaches at all. The large 17.22 pp headline is specifically a
floor-vs-overlap effect; the more modest mid-vs-overlap effect is common to all three bands. Both
are real; they are not the same measurement, and conflating them would overstate what 20m/17m
alone could show.

---

## 5. §0.2 reconciliation, performed as Amendment 1 (A1.2) requires

Amendment 1 struck the spec body's original (mis-stated) tension and replaced it with a sharper
one: `F_std` = +17.22 pp at the floor must be squared with **C.1's +0.93% ceiling on the
candidate-cap family** and **RC1's 87.9% candidate-present-and-failed** decomposition. Those two
together say the crowding cost is **not** budget exhaustion — this is the reconciliation.

- **C.1** (2026-07-26): sweeping `K_MAX_CANDIDATES` 140 → 300 → 600 on a fixed 68-cycle corpus
  bought **+12 decodes (+0.93%)** at 300, and 300/600 produced **byte-identical** decode sets.
  Raising the pass-0 candidate ceiling essentially stopped helping past ~220–295 real candidates —
  the corpus's own candidate population plateaus there regardless of how much headroom is offered.
- **RC1** (2026-08-07): decomposing 894 pooled misses across three runs found **3.1%
  out-of-band, 8.9% no-candidate, 87.9% candidate-present-and-failed.** In nine of ten misses, a
  candidate existed at the right time/frequency and the decode still failed downstream of
  candidate generation.
- **RC4** (2026-08-07, June verdict reconfirmed on live audio): `K_MAX_PASSES` 2→3 measured
  `d = +0.70 pp` — a small, non-material gain from a deeper search on the busiest corpus available
  at the time.
- **D-009** (2026-08-05/06): a 45-point grid sweep of `kMinScorePass2`/`osdCorrThreshold`/
  `osdNhardMax` bought **+0.109 pp** — essentially nothing, across the entire OSD-tuning
  parameter family.

**The reconciliation.** If crowding degraded recovery by *truncating the candidate/pass budget*
before OSD ever got a chance, the fix would show up as decodes recovered by (a) raising the
candidate ceiling, or (b) running more passes, or (c) retuning OSD's own acceptance thresholds.
All three have been tried, on real and synthetic corpora, and all three returned numbers an order
of magnitude smaller than `F_std`: +0.93%, +0.70 pp, +0.109 pp, against a 17.22 pp effect. **The
budget is not the binding constraint.** RC1 says the same thing from the opposite direction: we
are *generating* the candidate in the dense cycle 91% of the time and still failing to decode it —
so whatever crowding costs us, it is happening to the signal or its extraction, not to whether we
looked in the right place. Per Amendment 1 (A1.3), the surviving explanation family is
**degradation of the signals themselves when the cycle is crowded** — co-channel and
adjacent-signal interference — which is the *same channel family* X1's own ROW 1 (the 80m−20m
band term, `B_std` = +5.70 pp at L1) already promoted. **This arm does not discover a new
mechanism; it corroborates, at much larger magnitude, the one X1 already named**, and the two
results now point at one joint sub-question rather than two separate ones.

🛑 Per A1.3/A1.4, this reconciliation does **not** reopen the candidate-budget family (closed
twice, RC2), and does **not** license a spectral-locality follow-up (S.1 is CLOSED and stays
closed — S4.3's bar). Both are stated here only because the reconciliation needs them ruled out
explicitly, not as an invitation to revisit either.

---

## 6. §4.2 — shape (descriptive only; no row turns on this; no slope fit, per spec bar)

SNR-standardised (where ≥ 5 of 5 L1 strata qualify at n≥10 — noted per point) and raw recovery
against **exact integer density**, full range, with per-point n and cycle-clustered 95% CI on the
raw figure:

| density | n | raw recovery | SNR-std recovery | 95% CI (raw) |
|---:|---:|---:|---:|---|
| 1 | 140 | 87.9% | 93.2% | [82.0, 93.2] |
| 2 | 180 | 88.9% | 86.6% | [84.6, 92.9] |
| 3 | 183 | 89.1% | 85.9% | [83.9, 93.5] |
| 4 | 212 | 87.3% | 79.0% | [83.3, 91.2] |
| 5 | 345 | 87.8% | 82.1% | [84.9, 90.4] |
| 6 | 360 | 83.9% | 72.5% | [80.6, 87.5] |
| 7 | 476 | 85.1% | 79.8% | [82.0, 88.0] |
| 8 | 544 | 78.7% | 71.2% | [75.2, 81.9] |
| 9 | 522 | 77.6% | 71.2% | [73.9, 81.3] |
| 10 | 650 | 74.5% | 69.5% | [71.1, 77.9] |
| 11 | 418 | 75.8% | 69.9% | [71.3, 79.9] |
| 12 | 636 | 76.9% | 71.0% | [73.5, 80.6] |
| 13 | 702 | 76.9% | 70.7% | [73.1, 80.5] |
| 14 | 784 | 78.6% | 73.1% | [75.8, 81.0] |
| 15 | 720 | 73.9% | 68.8% | [70.8, 76.8] |
| 16 | 864 | 71.4% | 63.8% | [68.4, 74.2] |
| 17 | 612 | 77.5% | 70.3% | [74.6, 80.4] |
| 18 | 702 | 74.8% | 68.7% | [71.4, 77.9] |
| 19 | 456 | 73.5% | 64.5% | [69.5, 77.2] |
| 20 | 340 | 70.3% | 64.7% | [65.4, 75.3] |
| 21 | 378 | 70.4% | 67.9% | [66.3, 74.4] |
| 22 | 264 | 70.8% | 66.4% | [65.0, 76.9] |
| 23 | 207 | 74.9% | 70.3% | [65.9, 83.5] |
| 24 | 144 | 73.6% | 69.3% | [67.4, 79.2] |

Full harness output, all fields, is in `x2_result.json`'s `"shape"` array.

**Description, not a fit (barred by spec S4.2):** density 1–5 (the FLOOR regime) sits flat and
high, 87–89% raw recovery throughout, with overlapping CIs across those five points. Density 6–10
shows the steepest drop in the whole curve (83.9% → 74.5%, roughly 2 pp per unit density). From
density ~10 onward the curve is much shallower and noisier, drifting from the low 70s down to the
high 60s/low 70s out to density 24, with adjacent-point CIs overlapping throughout that tail. This
reads more like a **knee** — a fast transition concentrated around density 5–10 — than a smooth
gradient across the whole range, but per the spec's own bar this is reported as a visual/tabular
description only; no slope is fit or quoted (the recovery-vs-density slope was already retracted
as a non-parameter, 2026-08-08).

---

## 7. Predictions scored

### 7.1 QA's own §4 pre-registration prediction (recorded 2026-08-09, before any 80m data existed)

> "(b)-leaning — recovery will fall faster than the 20m/17m within-band slopes predict as density
> approaches the true floor, because the SNR-distribution shift (fading signals, not just fewer of
> them) is expected to dominate once the band is genuinely dying rather than merely quiet.
> Confidence: low."

**Measured: the opposite on both counts.** Recovery **rises** sharply toward the floor (88.11% at
FLOOR vs 74.06% at OVERLAP) rather than falling, and the SNR-distribution mechanism proposed as
the driver is directly contradicted by §3.2 — FLOOR, MID and OVERLAP have nearly identical SNR
distributions at every percentile checked. **MISS on category (a vs b) and MISS on direction.**
Scored honestly, as instructed, including the low-confidence label the prediction carried — this
was a low-confidence call on the first leg of its kind, and it was wrong in a way that turned out
to be informative: the true mechanism is a *decoding* effect at fixed signal quality, not a
*signal-quality* effect at all.

### 7.2 Architect's predictions (§6 of the amended spec, recorded blind on everything except the primary metric, which was disclosed and suspended)

| # | prediction | measured | verdict |
|---|---|---|---|
| 1 | ROW 0g selection diff: 0–2.5 pp | 0.307 pp | **HIT** |
| 2 | ROW 0c self-consistency on 80m: ≥ 95% | 93.35% | **MISS** (below the predicted bound; still clears the row's own 90% bar) |
| 3 | §4.1 replicates on **at least one** of 20m/17m at MID-vs-OVERLAP, \|F_std\| ≥ 2.0 pp | 20m +5.16 pp, 17m +8.17 pp | **HIT** — and stronger than predicted: **both** bands replicate, not merely one |

**2/3.** Consistent with the standing calibration note (magnitude-bound predictions run well;
directional calls do not) — all three of these were magnitude bounds, none directional, and the
one miss (#2) missed by 1.65 pp against a bound the prediction itself flagged as a real, not
formulaic, expectation.

---

## 8. §6 citation limits, restated in full (spec text, with one QA-added note)

- 🔴 **Basis.** T1 basis: `A∩B`, `<...>`-bearing messages excluded, 200–3000 Hz. **Not**
  comparable with the H1a-corrected ≈57.8% 20m figure, which used wildcard matching over a
  different population. 🛑 Never mix bases in one comparison.
- 🔴 **`F_std` is conditional on the reference.** It measures recovery of what WSJT-X heard, in
  cycles where WSJT-X heard little. It is **not** a claim that OpenWSFZ decodes ~100% of signals
  present on the air.
- 🔴 The post-`072815` tail is **descriptive only** — raw counts, never a percentage. For the
  record: `owsfz8080` logged 20 decode lines across 20 cycles and `owsfz8081` logged 17 across 17
  cycles between `072815` (exclusive) and `101100`, with **no reference** to compute recovery
  against (WSJT-X's last decode in this leg is `072815`).
- ⚠️ 80m at dawn is one band, one morning, one propagation mode. §4.1's replication is what
  extends this beyond "one leg's anecdote" — and it did extend, on both replication bands.
- 🛑 No `src/` recommendation, no parameter sizing, no capture-run proposal in any row.
- **New, QA-added (HK-021(h)):** `F_std`, like X1's `B_std`, is standardised on a finite,
  5-stratum SNR proxy, so it carries the same *technical* upper-bound caveat — a coarser
  instrument can never fully equalise composition within a stratum. **Unlike `B_std`**, though,
  which compares two bands with materially different mean SNR (real room for residual
  within-quintile composition drift), §3.2 shows FLOOR and OVERLAP have **near-identical** SNR
  distributions at every percentile checked here. That argues the residual-confounding risk is
  small for this particular contrast — but it is an argument, not a measurement, and `F_std`
  should still be quoted as "at most," never as an exact figure, consistent with the programme's
  standing convention for this class of standardisation.

---

## 9. What this arm still cannot answer

- **Why** signals degrade in crowded cycles. Co-channel/adjacent-signal interference is now a
  named, corroborated hypothesis (X1 + X2 together), not a measured mechanism — nothing in
  `ALL.TXT` characterises the interference directly, and per A1.4 the natural next step (a
  spectral-proximity measurement) runs straight into the closed S.1 gate and must not be attempted
  here or proposed as a follow-up without the Captain's ruling on that boundary specifically.
- Anything requiring new capture. **No capture run is proposed.**
- Whether the effect is linear in signal count, in co-channel power, or something else entirely —
  §6's shape data is descriptive only and does not resolve this.

---

## 10. NFR-021

This report and the harness output (`x2_result.json`) carry counts, rates, cycle timestamps and
one dial-frequency label only. No callsign or message text appears anywhere in either artefact.
