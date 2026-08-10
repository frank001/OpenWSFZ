# QA → Architect — X1 results: cross-band recovery decomposition (20m / 17m / 80m)

**2026-08-10 16:22Z** (filename and byline both from `date -u`, HK-017).
**Author:** QA. **Audience:** Architect.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-10-1538-architect-to-qa-spec-x1-cross-band-recovery-decomposition.md`.
**Harness:** `qa/cycleframer-alignment-replay/x1_cross_band_decomposition.py`, importing
`t1_frequency_quantisation.load` unmodified. Raw output: `x1_result.json` (same directory).
**Status: primary gate → ROW 1. Band is a first-order term in the decode gap, confirmed after
exact density × SNR standardisation, on all three levels of the ladder, with the cycle-clustered
95% CI clearing zero by a wide margin.**

---

## 1. Headline, stated once before the detail

Good evening, sir. The spec's central question was whether "band" survives exact density and
SNR matching, or dissolves entirely into composition. It does not dissolve. On the primary pair
(80m vs 20m), the standardised contrast is **+5.70 pp at L1 (quintile)**, falling only to
**+4.83 pp at L3 (20-tile)** — 85% of the coarse-level effect survives the finest SNR
stratification the corpus can support — and the cycle-clustered 95% CI is **[+3.91, +7.42] pp**,
nowhere near zero. All three pre-registered ROW 1 conditions (`b1 ≥ 3.0`, `b3 ≥ 0.5·b1`, CI
excludes 0) are met with room to spare. **This promotes channel characterisation to a live D-001
sub-question**, per the spec's own consequence table — and, per that same table, **licenses
nothing else**: no `src/` recommendation, no capture run.

Every number in §3 below was independently re-derived from `ALL.TXT` on disk and reproduces the
Architect's own §0.1 disclosure to the decimal — population counts, raw recovery, and all nine
standardised contrasts. That is not a coincidence to be quietly pleased about; it is the
mechanical cross-check the spec's determinism requirement (fixed seed, HK-021) exists to make
possible, and it passed.

---

## 2. X0 — the 80m reference repair

Executed before any part of the harness was written, per the spec's own sequencing (§2: "if X0
cannot be completed, X1 is VOID").

**Defect confirmed exactly as described.** `-8080-80m/wsjt-x/ALL.TXT` and `-8081-80m/wsjt-x/ALL.TXT`
resolved to the same inode (`281474977087507`, `links=2`, identical md5, 706 943 bytes) before
repair — `tools/gather_live_run_artefacts.py`'s `--wsjtx-link-from` had hardlinked the `-8080`
leg's `FT991A` file into `-8081` instead of reading the live `FT991A-Copy` instance, silently
degenerating this leg's `REF` from `A ∩ B` to `A ∩ A`.

**Repair.** The hardlinked file was renamed (`ALL.TXT.hardlink-bak-ft991a`, preserved, not
deleted), then `tools/gather_live_run_artefacts.py`'s own `filter_alltxt()` was called directly
against the live, untouched `C:\Users\Frank\AppData\Local\WSJT-X - FT991A-Copy\ALL.TXT`, same
window convention as every other leg (`260809_015445`–`260809_072815`).

**Result, checked against every number the spec pre-registered — all matched exactly:**

| check | spec expectation | measured | match |
|---|---:|---:|---|
| FT991A-Copy lines / cycles in window | 10 942 / 1 196 | 10 942 / 1 196 | ✅ |
| distinct from FT991A's | 10 952 / 1 197 | 10 952 / 1 197 (unchanged, confirmed distinct) | ✅ |
| repaired `A∩B` raw | 10 913 | 10 913 | ✅ |
| repaired `A∩B` clean | 10 839 | 10 839 | ✅ |
| recovery, old basis → repaired | 76.84% → 77.09% (+0.25 pp) | 76.84% → 77.09% (+0.25 pp) | ✅ |
| ROW 0e (window-end integrity) | identical at `072815`/`101100` | 10 913 both ways | ✅ |

`qa/artefact_inventory.py` regenerated; `--check` clean; the **HARDLINKED** annotation on the
80m pair is confirmed gone (the script only flags shared `ALL.TXT` inodes — `wsjt-x/wav/` is
still hardlinked from `-8080`, out of scope for any `ALL.TXT`-only arm, flagged below).

**Recorded, not fixed here (X0's own instruction):** `artefacts/20260809_live_run_0155-8081-80m/contents.md`
now carries an "X0 repair" section with the full account, and an operational note
(`operational-note-gather-tool-wsjtx-link-from-two-instance-defect.md`) documents the tool
defect.

🔴 **Note for the record, not X1's business to act on:** 21 minutes after the X1 spec, a
separate Architect spec landed — `2026-08-10-1559-architect-to-qa-spec-g1-gather-tool-
reference-provenance-guard.md` — independently diagnosing the identical defect via a cleaner
instance-identity audit method, confirming the same blast radius (20m/17m sound, 80m alone
defective), and specifying the actual tool fix (provenance recording, a premise guard, tests,
a full retro-audit). Its §3.1 names the exact repair performed above as shared with X0 and
states it "can land first" — it has. The Captain has ruled (G1 §0) that fix is QA tooling
requiring no Developer session. **G1's remaining deliverables (§3.2–3.6, §4, §5) are not
executed in this report** — they are a separate spec with their own deliverables list, not part
of X1's scope. Flagging its existence here only so it is not lost between two specs filed
within half an hour of each other.

---

## 3. ROW 0 — void, identifiability, power (ordered trace)

| row | check | result |
|---|---|---|
| **0a** | 80m `wsjt-x/ALL.TXT` distinct inodes + `\|A∩B\|/\|A\| ≥ 0.95` all three bands | **PASS** — distinct inodes confirmed; ratios 20m 0.9978, 17m 0.9864, 80m 0.9964 |
| **0b** | clean REF reproduces exactly: 20m 67 243, 17m 38 047 | **PASS** — both exact |
| **0c** | coverage ≥ 0.60 at L1/L2/L3, per pair | **PASS on all three pairs** (table below) |
| **0d** | cycle-clustered SE(B_std) at L1 ≤ 1.5 pp, per pair | **PASS on all three pairs** (table below) |
| **0e** | 80m REF identical at window end `072815` vs `101100` | **PASS** — 10 913 both ways |

No row voided. No pair is an instrument failure. **Every pair is identifiable and powered —**
this includes the two secondary pairs, so their ladder figures below are reportable on their own
terms, not merely descriptive.

| pair | coverage L1/L2/L3 | SE(L1) |
|---|---|---:|
| 80m − 20m | 85.5% / 80.3% / 66.8% | 0.896 pp |
| 17m − 20m | 99.7% / 99.2% / 98.2% | 0.446 pp |
| 80m − 17m | 79.5% / 71.9% / 63.8% | 0.802 pp |

**Sanity checks run alongside ROW 0, not part of the formal gate but worth recording:** clean
population + exclusions reconciles exactly to the raw intersection on every band
(20m 67 243+1 113+866 = 69 222; 17m 38 047+582+198 = 38 827; 80m 10 839+16+58 = 10 913); raw
recovery independently reproduces the spec's §0.1 disclosure exactly (20m 56.18%, 17m 64.08%,
80m 77.09%); REF cycle counts match exactly (2 529 / 1 835 / 1 196).

---

## 4. The full ladder — every pair, every level, coverage-weighted, cycle-clustered

Pooled SNR strata edges, computed once from all three bands' clean REF SNR values combined
(n = 116 129), per HK-021(g):

- L1 (quintile): [−15, −10, −5, 2]
- L2 (decile): [−19, −15, −13, −10, −8, −5, −2, 2, 7]
- L3 (20-tile): [−21, −19, −17, −15, −14, −13, −12, −10, −9, −8, −7, −5, −4, −2, 0, 2, 4, 7, 11]

| pair | level | `B_std` | coverage | SE | 95% CI (cycle-clustered, 1000 draws) |
|---|---|---:|---:|---:|---|
| **80m − 20m** | L1 | **+5.70 pp** | 85.5% | 0.896 | [+3.91, +7.42] |
| | L2 | +5.57 pp | 80.3% | 0.931 | [+3.65, +7.25] |
| | L3 | **+4.83 pp** | 66.8% | 0.896 | [+3.36, +6.88] |
| 17m − 20m | L1 | +1.34 pp | 99.7% | 0.446 | [+0.17, +1.95] |
| | L2 | +0.84 pp | 99.2% | 0.448 | [+0.10, +1.86] |
| | L3 | +0.76 pp | 98.2% | 0.424 | [+0.09, +1.76] |
| 80m − 17m | L1 | +2.70 pp | 79.5% | 0.802 | [+1.18, +4.28] |
| | L2 | +2.68 pp | 71.9% | 0.806 | [+1.00, +4.16] |
| | L3 | +2.02 pp | 63.8% | 0.844 | [+0.46, +3.76] |

Every point estimate above reproduces the Architect's §0.1 disclosure exactly (to two decimal
places in every cell), and every "min coverage" figure matches the disclosed table (67% / 64% /
98%) to the nearest integer. This is an independent re-derivation from `ALL.TXT`, not a copy —
the agreement is the cross-check working as intended, not evidence recycled from the spec.

**All three secondary-pair 95% CIs also exclude zero.** 17m−20m's CI is the tightest to zero
([+0.17, +1.95] at L1) of the three, consistent with it being both the smallest effect and the
best-powered pair (SE 0.446 vs 0.896/0.802 for the pairs touching 80m's smaller, sparser corpus).

---

## 5. The primary gate

```
b1 = |B_std(80m,20m,L1)| = 5.695 pp
b3 = |B_std(80m,20m,L3)| = 4.834 pp   (84.9% of b1 -- well above the 50% bar)
95% CI (L1) = [+3.908, +7.420] pp     (excludes 0)

b1 >= 3.0            -> True
b3 >= 0.5 * b1        -> True (2.848 bar, 4.834 measured)
CI excludes 0         -> True

==> ROW 1
```

**ROW 1 fires cleanly, not on a boundary.** `b1` clears its 3.0 pp bar by 2.7 pp; `b3` clears
its 2.85 pp bar (half of `b1`) by exactly 1.99 pp — the standardised effect barely attenuates
between the coarsest and finest SNR stratification the corpus supports, which is itself
informative: it says the residual confounding L3 was designed to squeeze out was small to begin
with, i.e. the L1 estimate was already close to the standardised truth rather than an artefact of
under-stratified SNR.

### Replicate check (reported, not gated)

| | B_std(80m,20m,L1) |
|---|---:|
| SUT = 8080 (primary) | +5.695 pp |
| SUT = 8081 (replicate) | +5.718 pp |
| \|difference\| | **0.022 pp** — comfortably inside the 1.0 pp stability bar |

The instrument is stable under an unseen validity check using the *other* OpenWSFZ instance as
the system under test, same reference throughout. Per the spec's own warning (§4), this
agreement is **not** read as a band property — the 20m capture-start-alignment confound (the
08-08 13:00Z finding) still applies to any 8080-vs-8081 comparison and is not being invoked here,
only the magnitude of the replicate gap.

---

## 6. Predictions scored (§5.2)

| # | prediction (blind) | measured | verdict |
|---|---|---|---|
| 1 | SE(B_std) at L1, 80m−20m: 0.8–1.6 pp | 0.896 pp | **HIT** |
| 2 | Coverage at L3, 80m−20m: 60–75% | 66.8% | **HIT** |
| 3 | Replicate agreement ≤ 1.0 pp | 0.022 pp | **HIT** |
| 4 | ROW 0 fires on no pair | confirmed — 0a/0b/0e pass, 0c/0d pass on all three pairs | **HIT** |

**4/4.** All four were magnitude bounds, per the standing calibration note (no directional
calls in this spec's predictions, as instructed). §5.1's primary-metric prediction-scoring stays
suspended, as disclosed — the Architect had already seen `B_std` at all three levels for all
three pairs before this spec was written, and this report's independent re-derivation is the
part that was genuinely blind: whether the mechanical pipeline, run fresh from `ALL.TXT`, would
reproduce those disclosed numbers exactly. It did.

---

## 7. §6 citation limits, restated in full (spec text, unmodified)

- 🔴 **Basis warning.** Recovery levels here use the **T1 basis**: `A∩B`, `<...>`-bearing
  messages **excluded**, 200–3000 Hz. They are **not** comparable with the H1a-corrected
  **≈57.8%** 20m figure, which used wildcard matching over a different population. 🛑 **Never
  compare a figure on one basis against a figure on the other.**
- 🔴 **`B_std` is an UPPER bound on the band term, not a floor.** Matching on a noisy, finite-
  resolution proxy for signal quality leaves residual confounding, which inflates the contrast.
  This is the **opposite** direction from T1's `G` (a floor). Quote **"at most"**, never "at
  least."
- Raw, unstandardised recovery differences between bands are **descriptive only** and must
  always appear beside the standardised figure, never alone. (Raw levels, for reference: 20m
  56.18%, 17m 64.08%, 80m 77.09% — not monotone in dial frequency, per the spec's own §1 note,
  and not to be read as "band order" without the standardisation above.)
- The 80m leg's own dying tail is **out of scope here** (X2's subject).
- 🛑 No `src/` recommendation is drawn from this arm, in any row.
- **New, from this run:** `B_std` here is a magnitude of a real, statistically clear contrast
  (ROW 1), not an inconclusive or composition-only reading — the "upper bound, never a floor"
  caveat above matters *more*, not less, now that there is a citable number people will want to
  quote as if it were exact.

---

## 8. What this arm still cannot answer (spec §7, unchanged)

- **Why** the band term exists. Multipath/Doppler spread is a hypothesis promoted to a named
  D-001 sub-question by this result, not measured by it — nothing in `ALL.TXT` characterises
  channel impairment directly.
- Anything about `G`, the lattice, OSR, or the midpoint question (spec §0.3 — already measured
  and closed by the Architect's own scoping pass, not re-litigated here).
- Anything requiring new capture. **No capture run is proposed.**

---

## 9. NFR-021

This report and the harness output (`x1_result.json`) carry counts, rates, and cycle timestamps
only. No callsign or message text appears anywhere in either artefact.
