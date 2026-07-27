# D-001 R.4b — real-corpus decode-probability curve, QA task spec

**Author:** QA, 2026-07-27 (per HK-017, `date -u` at commit). **Operationalises:**
`2026-07-27-1522-architect-r4-ruling-and-r4b.md` §4 (R.4b), §7 (Q1/Q2), §8 (sequencing: R.4 ✅ →
**R.4b** → R.3 → R.2). Also incorporates §11's independent-verification ask, resolved directly in
this session (see §0 below) before R.4b was scoped.
**QA-runnable directly: arithmetic on data already in hand, no `src/`/native change, no new
capture, no `dev-tasks/` entry** — same posture as every prior arm in this thread.

---

## 0. §11's verification, done first

The ruling asked QA to confirm the 2.62 dB correction independently rather than accept the
Architect's regrouping on faith, and flagged an open question: 11 of 51 slot-7 buffers have a
*base* frequency under 3000 Hz but may still occupy spectrum past it (FT8 spans 7×6.25 = 43.75 Hz
above base for an 8-tone alphabet).

**Done, this session, against the persisted `measurements.json`/`manifest.json` directly (not
re-derived from the ruling's own numbers):** reconstructed per-slot rows by zipping each buffer's
measurement list against its manifest (both written in slot order 0–7), confirmed the plateau
failure set is exactly slot 7 (147 of 168 plateau rows are slots 0–6, all decoding 21/21; slot 7 is
1/21), then re-ran the 50%-crossing computation two ways:

| exclusion rule | plateau `ours` | ΔSNR |
|---|---|---:|
| Wholesale (drop all 51 slot-7 rows) — the ruling's number | 147/147 | 2.625 dB |
| Per-signal (drop only rows whose occupied ceiling ≥ 3000 Hz — 49 of 51, keeping 2 genuinely
  in-band) | 148/148 | **2.625 dB — identical** |

The two genuinely in-band slot-7 points recovered by the stricter test (2945.1→2988.85 Hz,
decoded; 2951.06→2994.81 Hz, low-SNR, not decoded) don't move the 50% crossing at all. **2.62 dB
stands, confirmed independently, robust to which exclusion rule is used.**

## 1. Question

What is our decoder's real-world sensitivity curve — P(we also decode it | WSJT-X's reported SNR)
— measured directly against WSJT-X as reference on **real traffic**, with no synthetic-to-real
conversion anywhere in it? And: does shifting that curve left by the corrected 2.62 dB explain
materially more of the miss population than the withdrawn step-model floor (50/120 messages, §3 of
the R.4 findings, now relabelled a floor rather than an estimate)?

## 2. Method

Reuses `b1_jt9_ablation.py` / `b1b_second_corpus_ablation.py`'s `parse_all_txt` and cycle-set
filtering directly (imported). For each corpus:

1. **Per-message rows.** WSJT-X `ALL.TXT`, restricted to the corpus's own cycle set, each row
   carrying `(ts, snr, message)`. Cross-referenced against our offline `ALL.TXT` (same cycle set)
   to label each row **hit** (we also decoded it) or **miss**.
2. **Binning.** Whole-dB bins (`round(snr)`) — the native resolution of WSJT-X's own report, per
   R.4 findings §6's quantisation caveat; no half-dB steps.
3. **The curve.** `P(bin) = hits(bin) / (hits(bin) + misses(bin))`, Wilson interval, per corpus,
   **never collapsed across corpora** (design's own standing rule, restated in every arm since).
4. **High-SNR asymptote.** `P` averaged (pooled hits/misses, not averaged-of-averages) over bins
   at or above a strong-signal cutoff (+5 dB and above, chosen because it is comfortably clear of
   both corpora's hit-population medians — corpus 1 +1 dB, corpus 2 −2 dB, per R.4 findings §3 —
   so "strong" here means unambiguously strong, not merely above-median). Reported per corpus.
5. **Shift-model recovery estimate.** For every missed message at SNR `s`, look up `P(s + 2.62)`
   on that corpus's own curve (nearest-bin, same technique as B.2's `p_decode_from_curve`/E
   estimator — reused convention, not a new one) and sum across the miss population. This is an
   **expected-value** estimate, not a step function, and is reported *beside* the step-model floor
   (50 / 120 messages) so the two are directly comparable, per the ruling §4 deliverable 3.
6. **Cycle-density split.** For each cycle, density = count of WSJT-X-decoded messages in that
   cycle (a same-corpus, same-instrument congestion proxy — no new data). Split cycles at the
   corpus's own median density into "sparse" and "dense" halves, recompute the SNR-binned curve
   for each half separately, and compare `P` at matched SNR bins between them.

## 3. Reading rule — fixed by the Architect, reused verbatim (ruling §4 table)

| result | reading |
|---|---|
| P saturates (≥ ~95%) above the threshold region | Misses above threshold are genuinely structural. QA's original conclusion is confirmed and strengthened; ~6% becomes approximately right for the sensitivity component; R.3 must attribute the structural remainder. |
| P stays materially below saturation across a broad SNR band | Our loss is broad-spectrum and probabilistic. The step model understates the shift benefit; the shift-model number replaces 6.3%/6.2% as the sensitivity contribution and may be materially larger. |
| P is high in sparse cycles and depressed in dense ones at the same SNR | Co-channel/collision is the driver. Row 4's target is co-channel handling, which neither Arm A nor R.3's isolated geometry can see. |

QA computes and reports against this table; no new judgement call introduced at this step, same
convention as R.1/R.1b/R.4.

## 4. Self-check

`hits(bin) + misses(bin)` summed across all bins must equal each corpus's total WSJT-X message
count already published (corpus 1: shared-hit 1239 + missed 789; corpus 2: shared-hit 2437 +
missed 1934 — both already computed and printed by R.4's own `corpus1_miss_and_hit_snr` /
`corpus2_miss_and_hit_snr`, reused verbatim here, not re-derived). If it does not match, stop and
report the mismatch rather than the curve.

## 5. What this does not authorise

Same guardrails as every prior arm: no native/`src/` change, no push/merge, no
`pre_merge_check.py` (HK-006), NFR-021 (aggregate counts/SNR-bin statistics only, real corpus data
stays inside git-ignored `artefacts/`, message text never printed).

## 6. Cross-references

- `2026-07-27-1522-architect-r4-ruling-and-r4b.md` §4, §7, §8 — the design this operationalises.
- `2026-07-27-r4-sensitivity-gap-findings.md` — the step-model floor (50/120) this compares against,
  and the corrected ΔSNR (2.62 dB, confirmed independently in §0 above).
- `b1_jt9_ablation.py`, `b1b_second_corpus_ablation.py` — `parse_all_txt`/cycle-set filtering,
  reused verbatim.
- `b2_synthetic_calibration.py` — `wilson_interval`, `p_decode_from_curve` convention reused for
  the shift-model estimate.
