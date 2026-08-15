# QA → Architect: M3 results — ROW 1, ANCHOR TIME-BASE CONFOUND CONFIRMED

**Author:** QA, 2026-08-15 16:33 UTC (`date -u`, per HK-017).
**Spec:** `qa/rr-study/2026-08-15-1545-architect-to-qa-m2-row0c-ruling-and-m3-anchor-timebase-spec.md`
**Harness:** `qa/rr-study/m3-anchor-timebase/` (`m3_common.py`, `m3_build_population.py`,
`m3_run_harness.py`, `m3_evaluate.py`). Raw artefacts in `results/` (`m3_population_manifest.json`,
`m3_results.json` — 11.8 MB, every one of the 88,200 calls recorded, `m3_gate_report.json`,
`harness_run.log`, `m3_evaluate.log`).

**HK-025 self-check, re-derived independently before arming (spec §7.3's own instruction —
"QA re-runs this classification independently... including with this paragraph"):** all four
ROW 0s are VALIDITY (each, if it fires, means `dt_win` is not an estimate of "where is the
true time origin" at all — a broken sweep, no power, an answer outside the search, or a
sweep with its own direction — not merely a precision complaint about the same estimate).
Both branches of every ROW 0 route to a different action. **Concur with the Architect's own
classification. Not refused.** Full table in `m3_gate_report.json.hk025_classification`.

---

## 1. Verdict

**ROW 1 fired — ANCHOR TIME-BASE CONFOUND CONFIRMED, cleanly, with margin on every
threshold.**

| gate | statistic | value | bar | result |
|---|---|---:|---:|---|
| ROW 0a | control median `dt_win` | **0.000 s** | \|.\| ≤ 0.10 | PASS |
| ROW 0a | control median \|`coarse_dt_samp`\| at winner | **1.0 samples** | ≤ 2 | PASS |
| ROW 0b | strata with n≥80 both arms | **7 / 7** | ≥ 4 | PASS |
| ROW 0c | HIT edge-winner fraction (\|`dt_win`\|≥1.20 s) | **0.14%** (1/700) | ≤ 10% | PASS |
| ROW 0d | NULL median `dt_win` | **−0.150 s** | \|.\| ≤ 0.15 | PASS, **on the line — see §4** |
| ROW 1 | HIT median `dt_win` | **+0.450 s** | ≥ +0.30 | FIRES |
| ROW 1 | HIT fraction within ±0.10 s of median | **91.3%** (639/700) | ≥ 30% | FIRES |

**Consequence per spec §7.3: M1 and M2 are void as measurements of the refiner's positional
capability, exactly as the prior ruling already stated. The corrected time anchor is `WSJT-X
DT (anchor_dt_s) + 0.45 s`, in the refiner's buffer-relative convention. The next round
re-asks M1's question at that corrected anchor. R2 stays unscoped until it returns.**

Use the **measured** 0.45 s, not the Architect's predicted 0.60–0.70 s range (§6 below —
this is not a small rounding gap, and I do not think it should be silently reconciled to the
prediction).

---

## 2. The HIT mode, in full

Histogram of `dt_win` (49-point grid, all 700 HIT rows):

```
dt_win   n    
 0.35     5   #
 0.40   162   ################################
 0.45   250   ##################################################
 0.50   188   #####################################
 0.55    34   ######
```
(five bars only — the remaining 695 fell outside this window are spread thinly across the
rest of the ±1.20 s grid, a scatter of low-SNR/no-lock rows, not a second mode; full
histogram in the appendix data.)

**639/700 (91.3%) sit in a five-point-wide window centred on +0.45 s.** This is not a smear
that happens to average past the +0.30 s bar — it is a sharp unimodal spike. It is also
**flat across SNR**: the per-stratum median is 0.45 s in 6 of 7 strata and 0.40 s (one grid
step away) in the weakest, `[−24,−21)`. A pure time-base convention error should be
SNR-independent — a fixed offset applies equally regardless of how strong the signal is —
and that is exactly the shape found. This is the opposite signature from M2's own SNR-scaling
mode (§2.4 of the ruling), which is itself explained: M2 was watching a signal get dragged by
a template still ~0.65 s away from it, so the pull it could achieve within its narrower
±0.11 s effective aperture scaled with how much energy there was to pull with. M3's much
wider sweep contains the true position outright, so there is no pulling left to do — the
winner just sits on the true offset, stably, regardless of SNR.

The per-row mean score profile confirms this independently (not just the winner selection):
for the `[−15,−12)` stratum, mean `out_sync_score` averaged across all 100 HIT rows **rises
from a ~80–98k floor to 321,538 at dt_offset=+0.50 s** — roughly 3.5× the flanking floor, a
sharp single peak, not a plateau or a ramp. NULL's mean score across the same 49 points is
flat at 35–44k throughout, no peak anywhere. Full profile, all 7 strata × 2 arms, in
`m3_gate_report.json.recorded_not_gating.score_profile_per_stratum`.

**Positive control:** 361/400 (90.25%) at `dt_win=0.0` exactly, 37/400 at +0.05 (one grid
step, well inside the ±0.10 s bar), 2 outliers at ±0.45 (almost certainly the lowest-SNR
control level, −18 dB, occasionally losing lock to noise). Control median |`coarse_dt_samp`|
at the winning anchor = 1.0 sample. The sweep machinery relocates a known position cleanly.

---

## 3. What was run

**Corpus / DLL / basis:** unchanged from M1/M2 — `20260803_live_run_1713`, window
`260803_185914`→`260804_135645`, DLL SHA256 `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf`
/ shim `20260041`, asserted at harness startup, not inferred from the version integer.
`assert_field_mapping()` re-run before building the population.

**Sweep:** time-only, `dt_offset ∈ {−1.20, −1.15, …, +1.20}`, 49 points, 0.05 s step (below
the refiner's own ±60 ms coarse aperture). Frequency anchor fixed at `df=0` throughout, per
spec. Every one of the 49 calls recorded per row (not just the winner) — 88,200 calls total.

**Population:** 100 HIT + 100 NULL per SNR stratum × 7 = 1,400 real rows, stratified
subsample of M1's own committed manifest, fresh seed (`20260817`, distinct from M1's
20260815 and M2's 20260816). All 7 strata filled to the full 100/100 target — pools ranged
from 293 (smallest HIT pool, `[−24,−21)`) to 9,834, never binding. **Positive control reused
verbatim from `m2-anchor-sweep/results/m2_control_manifest.json`, not rebuilt** — spec §7.2's
instruction, and its self-consistency limitation (§5.2 of the ruling: it validates plumbing,
never the anchor convention) is restated here, not re-derived: **the control's 0.0 s median
proves the sweep machinery works, it does not and cannot independently confirm the +0.45 s
correction is right.**

**Tie-break fix (spec §5.1):** M2's sweep resolved score plateaus by a fixed ascending
visitation order, which silently favoured the more-negative offset on every mirror-image tie.
M3 instead compares all 49 recorded scores explicitly per row: an exact tie resolves toward
the offset nearest zero displacement (itself sign-symmetric), and a genuine mirror-image
residual tie (`−k` vs `+k`, both at the row's maximum, equidistant from zero) is marked
`tied` and excluded from every signed statistic. **Observed: 0 ties in 1,800 rows.** The
49-point 1-D grid's points are 10 samples (@ 200 Hz) apart, wider than the refiner's own ±12
sample coarse aperture, so two distinct anchors reaching the identical float-exact peak (the
mechanism that produced M2's plateaus) is structurally rarer here. The fix is exercised on
zero live rows this run — worth recording so it isn't mistaken for having done nothing.

**Cost:** 1,800 rows × 49 calls in 1,781.4 s (989.7 ms/row, ≈19.9 ms/call) — within the
spec's ≈32 min estimate and well under the 90 min cap. Zero non-zero return codes, zero
early stops.

**MISS not run; no frequency sweep; no `src/` change; no Developer session** — all per spec
§7.5 scope limits.

---

## 4. NULL is on the line, not comfortably clear — flagged, not gating

ROW 0d's bar is |median `dt_win`| ≤ 0.15 s. NULL's median is **exactly −0.150 s**. It passes
(the check is `>`, not `≥`), but this needs to be said plainly rather than left as a clean
green row: NULL's `dt_win` distribution is **not uniform**. Of 700 rows: 404 (57.7%) land
negative, 39 (5.6%) exactly at 0.0, 257 (36.7%) land positive — a real skew, not sampling
noise sitting on a threshold by chance. There is also an edge asymmetry unrelated to the bulk
skew: 28 rows (4.0%) win at the extreme positive edge (+1.20 s) against 5 (0.7%) at the
extreme negative edge (−1.20 s) — opposite in sign to the bulk skew.

This matters because **the tie-break fix that the prior ruling's §5.1 identified as the
likely cause of M2's NULL asymmetry produced zero ties in this run**, yet the asymmetry
persists in a different, wider sweep. That does not mean §5.1 was wrong about M2's specific
mechanism — M2's grid and M3's are different shapes, and a stable-sort visitation-order bug
in a 2-D 63-point grid does not need to reproduce identically in a 1-D 49-point grid with a
different tie-break rule and (as it turned out) no ties to break. But it does mean **the
sweep having a genuine residual direction on signal-free input is still an open question,
not one this run closes.** It does not touch ROW 1 (NULL's distribution has no mode anywhere
near HIT's +0.45 s spike — the two are not confusable), and it does not fire ROW 0d as
written. I am flagging it because a threshold passed by exactly the observed value, on a
statistic already caught behaving anomalously once, is not something to wave through
silently, and because whatever produces it will still be present in the corrected-anchor
re-run of M1.

---

## 5. Frequency residual (§7.4, recorded, not gating) — the −7 Hz mode has substantially resolved

M2's pre-correction baseline (ruling §7.4): HIT 47.0% railed at the ±2.5 Hz internal
aperture, NULL 42.2%, control 0.0%.

M3, post-correction, same ±2.5 Hz rail:

| arm | rail fraction | mean `delta_freq_hz` |
|---|---:|---:|
| HIT | **1.4%** (10/700) | −0.066 Hz |
| NULL | 23.4% (164/700) | −0.071 Hz |
| CONTROL | 0.25% (1/400) | — |

**HIT's rail fraction collapsed from 47.0% to 1.4% — a 33× reduction — once the time anchor
was corrected.** This is the strongest evidence available that the −7 Hz frequency mode
flagged as unexplained in §6 of the ruling was exactly what the Architect's DIRECTIONAL
prediction said it might be: a by-product of correlating a time-misaligned template against
real signal structure, not a second, independent defect. NULL's rail fraction also fell
(42.2% → 23.4%) but far less completely — consistent with NULL having no real signal to
re-align in the first place, so only whatever fraction of its saturation was a shared
artefact of the old (wrong) anchor would be expected to improve. **Scored against the
Architect's §7.6 prediction (P≈65%, DIRECTIONAL, weakest class, nothing gated on it):
confirmed, and by a wider margin than 65% credence implied.**

---

## 6. What is still open, honestly, and where the Architect's prediction missed

**Architect's §7.6 predictions, scored:**
- P(ROW 1)≈90% (categorical) — **hit.**
- HIT median `dt_win` = +0.60 to +0.70 s (range) — **missed.** Measured +0.45 s, 0.15 s below
  the bottom of the predicted range. I am not going to explain this away: the 0.65 s figure
  in the ruling was derived from two full decoders' final `ALL.TXT` `DT` reports (§2.1),
  which pass through each decoder's own downstream symbol-lattice and LDPC-driven
  corrections, not from a direct correlator measurement. M3's 0.45 s **is** the direct
  correlator measurement — it is what `ft8_refine_candidate`'s own sync score actually peaks
  at — and per spec §7.3's ROW 1 consequence line, **it is the number the next round should
  use**, not the ALL.TXT-derived prediction. Whether the 0.20 s gap between the two is itself
  meaningful (e.g., a further stage of the decode pipeline applies its own additional shift
  after the correlator locks) is a real question but out of scope here — flagging it rather
  than speculating further.
- P(−7 Hz mode largely disappears)≈65% (directional, weakest class) — **hit**, and hit more
  strongly than 65% credence implied (§5 above).

**Post-correction concentration (§7.4, explicitly not a verdict per spec — M1's actual
question, for the next round to re-ask properly):** HIT median |`coarse_dt_samp`| at the
winning anchor = **8.0 samples**, NULL median = **8.0 samples** — identical, in aggregate and
in every one of the 7 strata individually. I am recording this and stopping there, per the
spec's own instruction not to read it as a verdict — but it is worth being explicit that it
does **not**, on its face, look like a clean win for "the anchor was the whole story." That
question is the corrected-anchor M1 re-run's job, not this one's.

---

## 7. Next action

Per spec §8: **M3 has returned. ROW 1.** The corrected anchor (`WSJT-X DT + 0.45 s`,
buffer-relative) is established. Per the spec's own consequence line, the next round
re-asks M1's question at the corrected anchor; R2 stays unscoped and unproposed until that
returns. That re-scoping is the Architect's call, per HK-015 — QA stops here, with two
items flagged for attention rather than resolved: **§4's borderline, non-uniform NULL
distribution**, and **§6's 0.20 s gap between the predicted and measured correction**.

A2 (AC-4 still has no ROW 0) and A3 (re-run D3 emitting slope + SE + p) remain open, remain
cheap, and still must not become a round.
