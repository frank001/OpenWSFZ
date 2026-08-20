# QA → Architect: Stage 2 results — ROW 3 FIRES (HARM). N1's harm REPLICATES at scale, and Finding 2's defect is caught live, not just retrospectively

**Author:** QA
**Date:** 2026-08-18 20:13:02Z (mechanically derived via `date -u`, HK-017)
**Runs:** `qa/rr-study/2026-08-18-1921-architect-to-qa-stage2-unblock-ruling-and-combined-prereg.md`
("this document") in full, §6 order
**Harness (new):** `qa/rr-study/p-live-population/run_stage2.py`
**Status:** 🔴 **ROW 3 FIRES (HARM). Refinement makes the miss population's BER
materially WORSE, not neutral. Offset generalises cleanly to a second corpus.
QA STOPS here per §6.6 — no Stage 3, no Stage 4.**

---

## 0. Headline

**Part A re-derives the anchor-offset independently and lands exactly on
Stage 1R's own number: `OFFSET = +0.65s`**, on a fresh 600-row/551-cluster
seeded sample of PRIMARY's P-HIT population (25,411 rows/4,371 clusters),
median `BER_V0` at that offset = **5.75%** — matches Stage 1R's 5.75% to
three significant figures, an independent re-derivation landing on the same
answer. **ROW 0d found PERFECT stability**: all four chronological ts
quartiles independently swept to the identical `+0.65s` argmin, max deviation
from the pooled offset = **0.000s**. **Part A item 2 replicates the same
`+0.65s` offset on a second corpus** (`20260808_live_run_0016-8080`, a
different day, median BER 6.32%) — the offset is not a PRIMARY-corpus
artefact.

**Stage 2, at the corrected anchor, measured GRID vs REFINED on the full
P-LIVE population (15,383/18,012 rows measured, 3,916 clusters):
`d_ber = -3.45pp`, CI95 `[-3.45, -2.87]pp`, p = 0.0000.** The refiner does not
help — it **hurts**, with a confidence interval that excludes zero by a wide
margin. **ROW 3 (HARM) fires**, replicating N1's own `THE 135` finding
(-4.02pp) at nearly 60× the clusters (3,916 vs 67).

**§2's Finding 2 is not just a retrospective defect — it would have fired
live, on this exact data, tonight.** See §3 below: N1's own unsigned rule,
applied to Stage 2's real numbers, reports "no material effect." The signed
gate this document specced instead reports a real, p=0.0000 harm. This is the
same demonstration §4.1b ran against N1's *old* numbers, now run forward
against *new* data collected specifically to test it.

---

## 1. Gate trace, strict order

| Row | Condition | Measured | Result |
|---|---|---|---|
| 0a | DLL SHA256 re-hashed, asserted before arming, both bindings (`ExtractLLRs` + `Refiner`) | `6890d84c...`, shim 20260042 | **clear** |
| — | Mandatory sign unit test (§6, new construction — see §2.1) | see §2.1 | **PASS** |
| 0c | median `BER_V0` on `P-HIT` at swept `OFFSET`, outside [1.0%,15.0%] two-sided | OFFSET=+0.65s, median=**5.75%** | **clear** |
| 0d | any of 4 chronological ts-quartiles' own argmin differs from pooled by >0.05s | max deviation = **0.000s** (all 4 quartiles: +0.65s) | **clear** |
| 0b | `P-LIVE` dry count on PRIMARY, <500 rows OR <200 clusters | 18,012 rows / 4,113 clusters | **clear** |
| 0e | `frac_rail_t` (`\|delta_t\|≥0.0695s`) ≥ 0.50 | **6.5%** | **clear** |
| 0f | median`\|delta_t\|`≤0.005s OR median`\|delta_f\|`≤0.25Hz | 0.055s / 1.500Hz | **clear** |
| 0g | median `ber_grid` outside [8%,40%] two-sided | **31.03%** | **clear** |
| **ROW 1** | BENEFIT: d_ber≥+15pp AND CI_lo>+5pp AND f_cross≥20% | d_ber=-3.45pp | does not fire |
| **ROW 3** | HARM: CI_hi<0 AND d_ber≤-2pp | CI_hi=-2.87pp, d_ber=-3.45pp | 🔴 **FIRES** |

HK-025: independently re-derived before arming (`run_stage2.py:hk025_check()`,
its own fresh reasoning, not copied from the spec's §4.3 table). Concurs on
all seven ROW 0 rows — each routes fired-vs-cleared to a genuinely different
downstream action. No refusal.

---

## 2. Part A — the anchor-offset arm

### 2.1 Mandatory sign unit test (§6)

New construction, distinct from N1's `sign_unit_test.py` (which only checks
the pure-statistics `d_ber`/`f_cross` sign convention on synthetic numbers —
it never touches the DLL). This one exercises the **real extraction code
path** the sweep itself uses: content untouched, the anchor **fed to the
sweep** is displaced by a known `delta` (`wrong_anchor = anchor_dt + delta`).
A too-late anchor needs an earlier-searching correction, so the sweep's
minimum should land at `dt_offset ≈ -delta` relative to that displaced
anchor — "lands at its negation," the spec's own phrase (§6).

On 20 real `P-HIT` contexts (WAV + true codeword already loaded, content
unmodified):

| | argmin | vs. expectation |
|---|---|---|
| baseline (`delta=0`) | `O0 = +0.70s` | — |
| `delta = +0.30s` | `O_pos = +0.40s` | expect `O0-delta=+0.40s` — **exact** |
| `delta = -0.30s` | `O_neg = +1.00s` | expect `O0-delta=+1.00s` — **exact** |

Both land exactly on the predicted grid point (not merely "within one grid
step"), and the two injected deltas produce compensating shifts of opposite
sign (`shift_pos=-0.30s`, `shift_neg=+0.30s`) as required. **PASS.**

(`O0=+0.70s` here is a 20-row subsample's own argmin, one grid step from the
full 556-row sample's `+0.65s` below — expected sampling noise on a much
smaller n, not a discrepancy; the test's own logic is self-referential and
does not depend on which value `O0` takes.)

### 2.2 Sample and sweep, PRIMARY

`build_p_hit_population(PRIMARY)`: 25,411 rows / 4,371 clusters. Sampled 600
by seeded (`20260818`, per §3's own instruction) sort-stabilised RNG (the
population is construction-sorted by `(ts, freq, dt, message)` before
shuffling, standing hash-randomisation rule) → 551 clusters. 44 rows dropped
at `no_true_codeword` (7.3%, same drop class Stage 1/1R saw). **n_measured =
556, n_clusters_measured = 515** — both ROW 0b-style bars would clear with
wide margin (not gated here; §3's own item 1 folds this into the offset
derivation, not a separate row).

49-point sweep (`m3_common.TIME_ANCHOR_OFFSETS_S`, reused verbatim), 556 × 49
= 27,244 extractions, **144.6s, zero extraction failures at any of the 49
offsets**. Shape:

- **-1.20s … +0.55s:** flat, chance-level (45.4–50.0%) throughout.
- **+0.60s:** 13.22%.
- **+0.65s: 5.75% — the minimum.**
- **+0.70s:** 6.90%.
- **+0.75s:** 39.94% — sharply back up.
- **+0.80s … +1.20s:** back to chance-level.

Full 49-row table in `results/stage2_report.json["part_a_primary"]["sweep_table"]`.
Same single sharp three-point trough Stage 1R found (`+0.60/+0.65/+0.70`,
width ≈0.15s), from an **independently re-derived sample and an
independently re-implemented sweep loop** — not the same code invoked twice.

### 2.3 ROW 0d — chronological quartile stability

| quartile | ts range | n_rows | n_clusters | argmin | Δ vs pooled |
|---|---|---|---|---|---|
| 0 | `260803_171815`…`260803_203445` | 139 | 125 | +0.65s | 0.000s |
| 1 | `260803_203730`…`260804_061700` | 139 | 131 | +0.65s | 0.000s |
| 2 | `260804_062115`…`260804_102045` | 139 | 130 | +0.65s | 0.000s |
| 3 | `260804_102115`…`260804_135615` | 139 | 129 | +0.65s | 0.000s |

**Every quartile's own independent sweep found the identical `+0.65s`
optimum.** This is a stronger result than the 0.05s tolerance bar asked
for — not "within one grid step," but bit-for-bit identical across four
independently-swept ~10-hour chronological slices spanning the full
18.96-hour PRIMARY window. Computed from ONE precomputed (row × offset) BER
matrix (no extra extraction calls) — the pooled and per-quartile curves are
paired, not independently noisy re-measurements.

### 2.4 Part A item 2 — second-corpus sweep (descriptive, gates nothing)

`20260808_live_run_0016-8080` (different day, same instrument pair): full
P-HIT population 43,664 rows / 2,733 clusters, sampled 600 (same seed,
same procedure) → 533 clusters, 549 measured (51 `no_true_codeword`) → 492
clusters. Sweep: **argmin `+0.65s`, median BER = 6.32%** — trough spans 2
grid points (`+0.65s`/`+0.70s`) within 5pp of the minimum, same shape as
PRIMARY's.

**The offset is not a PRIMARY-corpus artefact — it replicates exactly on an
independent corpus captured five days earlier**, same magnitude trough,
same location. Per §5's own instruction this is DESCRIPTIVE (HK-021(k) —
Stage 2 runs on PRIMARY regardless of what a second corpus says), but it is
strong supporting content for the anchor-offset question in its own right.

### 2.5 Compute-budget disclosure (§3 item 1: "state which")

Sampled, not full population, on both corpora. **Full population would have
required ≈110 min (PRIMARY, 25,411 rows) + ≈189 min (second corpus, 43,664
rows) ≈ 5h for Part A alone** (measured rate: 27,244 extractions in 144.6s =
188.4/s), before Stage 2's own ≈9.3 min — over the §6 3h cap. Sampling at
n=600 is explicitly licensed by §3 item 1 ("run the full population if
compute allows — state which"); stated here per that instruction, not
silently done.

### 2.6 What this does and does not license (§5)

✅ States the offset's value (**+0.65s**), its stability across the cycle
timeline (perfect, §2.3), and its stability across two corpora (§2.4).

🛑 **Does NOT claim the offset is a defect in the production decode path.**
Nothing in this arm touches `CycleFramer` or the live daemon; the harness
anchoring is not the production framer. Whether the production buffer sits
offset from the UTC grid is Route A's territory and needs its own
pre-registration with its own instrument (§5, restated verbatim per
instruction).

---

## 3. Stage 2 — GRID vs REFINED on P-LIVE at the corrected anchor

### 3.1 Population and drops

Dry count (ROW 0b, before any measurement): `build_p_live_population(PRIMARY)`
= 18,012 rows / 4,113 clusters — clears 500/200 with wide margin.

Measured at `anchor_dt + 0.65s`: **15,383/18,012 rows (555.7s), 3,916
clusters.** Drop reasons: `no_true_codeword` 1,605 (8.9%, matches Stage 1's
own ~7.5–9.2% on this same population type), `grid_extract_rc_-3` 1,018
(5.65%, WSJT-X's passband is wider than our hardcoded 200–3000Hz production
window — same drop class Stage 1 documented), `refined_extract_rc_-3` 6
(negligible).

### 3.2 ROW 0e / 0f / 0g

- **`frac_rail_t` = 6.5%** (bound <50%) — clear, and worth reading against
  §1.1's finding: N1's *raw, uncorrected* anchor railed the refiner on 36.3%
  of rows (5.4% at the hard ceiling). Here, at the **corrected** anchor, the
  rail fraction drops to a sixth of that. This is exactly what §1's
  diagnosis predicts — a correctly-placed anchor puts the true position
  inside the refiner's ±70ms window far more often — and is a supporting
  cross-check on the offset's correctness, not merely a gate clearing.
  `frac_rail_f` (descriptive, ungated per §4) = 26.2%.
- **median`\|delta_t\|` = 0.055s, median`\|delta_f\|` = 1.500Hz** — both
  comfortably above N1's own 0.005s/0.25Hz floors. A real treatment contrast
  exists. Clear.
- **median `ber_grid` = 31.03%** — inside [8%,40%]. Neither chance-level
  (would mean d_ber is a difference of two noise readings) nor implausibly
  low (would suggest a membership leak). Clear. Decile table (A4.3-style
  disclosure): `0% / 14.9% / 18.4% / 22.4% / 26.4% / 31.0% / 35.6% / 39.1% /
  43.1% / 47.1% / 61.5%` — a real, spread-out distribution of GRID-position
  BER on this miss population, not a degenerate spike at either end.

### 3.3 Primary statistics

`cluster_bootstrap_median_diff` (`n1_stats`, reused **verbatim**, its own
default seed `20260816`), `n_draws=2000`:

**`d_ber` (paired median BER_grid − BER_refined, positive = refinement
helped): point = -3.45pp, mean = -3.37pp, se = 0.198pp,
CI95 = [-3.45, -2.87]pp, p = 0.0000 (n_rows=15,383, n_clusters=3,916).**

`f_cross` (ALL-rows denominator, N1's own convention — **not** n5_stats'
crossable-only denominator, a different quantity for a different purpose): a
**new** cluster bootstrap (`f_cross_cluster_bootstrap`, this harness, own
seed `20260818` since no prior verbatim implementation of a *clustered* CI
for this exact statistic existed — N1 reported only a bare point):

**point = 0.15%, CI95 = [0.09%, 0.21%], n_cross = 23/15,383, n_clusters =
3,916.** (`n_cross > 0`, so the rule-of-three bound does not apply here —
reported as `null` in the JSON per that convention, not omitted.)

### 3.4 The gate: ROW 3 fires

`d_ber = -3.45pp ≤ -2pp` **and** `CI_hi = -2.87pp < 0` ⇒ **ROW 3 (HARM)
fires.** ROW 1 (benefit) does not fire (`d_ber` is negative, nowhere near
+15pp). **Refinement makes BER on the miss population materially WORSE, at
p = 0.0000, on 3,916 clusters.**

---

## 4. Finding 2, demonstrated live, not just retrospectively

§4.1b of this document's own spec ran N1's old unsigned rule
(`abs(d_ber)≤5pp AND CI_hi<15pp`) against N1's **already-collected**
`THE 135` numbers and showed it would have reported "no material effect"
over a real -4.02pp harm. **The same check, run here against Stage 2's own
FRESH numbers, gives the identical result:**

```
abs(d_ber) = abs(-3.45pp) = 3.45pp  <= 5pp   -> True
CI_hi      = -2.87pp                 < 15pp  -> True
=> N1's OLD unsigned ROW 2 rule WOULD HAVE FIRED: "no material effect."
```

**The signed gate this document specced instead correctly reports ROW 3
(HARM), p = 0.0000.** This is not a hypothetical or a replay of old data —
it is tonight's population, measured fresh, and the old rule would have
buried a real, large, highly significant harm behind "no material effect"
a second time. §2's HK-021 sibling (l) finding is confirmed operationally,
not just historically.

---

## 5. Predictions scored (§8 — nothing gated on these)

| prediction | outcome | class | result |
|---|---|---|---|
| P(ROW 2 — null) ≈ 45% (plurality) | ROW 3 fired | categorical | **MISS** on the plurality call — but ROW 3 carried the second-highest assigned mass (35%), not a surprise outcome |
| P(ROW 3 — harm) ≈ 35% | ROW 3 fired | categorical | **HIT** as a named, non-trivial possibility |
| P(ROW 1 — benefit) ≈ 5% | did not fire | categorical | consistent |
| P(ROW 4 / any ROW 0 fires) ≈ 15% | no ROW 0 fired, ROW 3 not ROW 4 | categorical | consistent |
| `frac_rail_t` ∈ [0.10, 0.45] | **6.5%** | range | **MISS** — below the range. Informative miss: see §3.2, the low rail fraction is itself evidence the corrected anchor is doing its job |
| re-derived `OFFSET` ∈ [+0.60, +0.70]s | **+0.65s** | range | **HIT**, dead centre |

Per standing practice, QA scores each prediction individually here and
leaves the aggregate running-tally arithmetic to the Architect's own
bookkeeping (as the board's own convention has been since Stage 1R).

The `frac_rail_t` miss and the plurality miss both point the same direction:
**the corrected anchor works better than expected** — less railing than
predicted, and a *harm* materialised (not merely a null) with more
statistical force (p=0.0000, 3,916 clusters) than a coin-flip-adjacent
categorical prediction would suggest was likely.

---

## 6. What this does and does not change

✅ **N1's ROW 2 stands, strengthened.** Limb 1 (position refinement via the
current ±70ms/±2.5Hz sync refiner) is not merely dead on the small
candidate-present-and-failed population — it is actively costly on the much
larger P-LIVE miss population, at far tighter statistical power.

🛑 **Does NOT rehabilitate R2** (§7, restated per instruction — a ROW 1
firing would not have licensed it either; ROW 3 firing certainly does not).

🛑 **Stage 1 stays WITHDRAWN.** This arm does not re-run it and is not a
re-reading of its numbers with a correction applied.

🛑 **N5 stays HELD** on its own 4.37% bound (`THE 135`/`THE 567`, anchored
from OUR OWN candidate positions). Nothing in this arm touches it.

🛑 **N4/N3/N2's status unchanged.**

🛑 **Stages 3 and 4 remain BLOCKED** — the Captain's ruling named Stage 2
only; nothing here releases them.

🛑 **D-001's position is unchanged**: limb 1 dead (now doubly so), limb 2
held on a thin bound, Route A the best-motivated untested thing on the
board — exactly as at 19:02Z, per §9's own instruction.

⚠️ **The anchor-offset finding (§2) is real, replicated across two
independent samples of PRIMARY and across two corpora, and STILL not
pre-registered as a finding in its own right.** Per §5, it may not be read
as a production defect. Awaiting the Architect's ruling on whether/how to
pursue it on its own terms.

---

## 7. Scope and NFR-021

No `src/`, no Developer session, no DLL rebuild, no capture run — HK-011 not
engaged. DLL re-hashed from disk immediately before arming (both `ExtractLLRs`
and `Refiner` bindings), matches the pin exactly
(`6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`).

**No per-row dump this round** — `run_stage2.py` never assembles a per-row
list for P-LIVE or P-HIT; every deliverable is a summary statistic, a sweep
table (49 points, no row identity), or a quartile table (counts and ts
ranges, no message text). `results/stage2_report.json` is 17KB,
`results/stage2_run.log` is 6KB — neither approaches the `*_rows.json` class
the standing `.gitignore` pattern exists for, and neither needed
`artefacts/`.

NFR-021: message TEXT is used in-process only
(`ExtractLLRs.true_codeword`, inside `load_row_context` / `measure_stage2_row`)
and is **never** written to any row dict, JSON field, or log line. Verified
mechanically, not asserted:

```
$ grep -ni "message" results/stage2_report.json results/stage2_run.log
(no output, exit code 1)
```

Both emitted files grepped individually. Zero hits.

---

## 8. Next

Per §10: **QA stops here.** No Stage 3, no Stage 4, regardless of outcome.
Awaiting the Architect's ruling on:

1. Whether/how to pre-register the anchor-offset finding (§2 here, §5/§6.2 of
   the 19:02Z ledger) on its own terms — now with a THIRD independent
   confirmation (this round's own re-derivation) and cross-corpus
   replication added to Stage 1R's positive control and M3's refiner-mediated
   measurement.
2. GitHub issue #3 update — not yet done this round; folding in on
   instruction or in the same round as the ruling, whichever the Architect
   prefers.
