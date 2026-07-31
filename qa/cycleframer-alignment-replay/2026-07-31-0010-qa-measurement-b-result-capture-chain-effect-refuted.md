# D-001 Measurement B -- RESULT: capture-chain effect REFUTED at n=300

**Author:** QA, 2026-07-31 (00:10 UTC, `date -u`, per HK-017).
**For:** Architect (ruling owed per S6.3's consequence column — this is a direct instruction
to "strike S3's percentages," not just information), and the Captain.
**Answers:** `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` S6
(redesigned at §R), which authorised this measurement and pre-registered its reading rule
before the run.
**Script/data:** `measurement_b_capture_chain.py`, `measurement_b_capture_chain_report.md`
(this directory; `_work/measurement_b/` is git-ignored, NFR-021).

---

## 0. Summary

Measurement B ran the primary (|drift| < 0.5 s, drift-free) arm at n=300 cycles, exactly as
redesigned in S6.2. The mechanical outcome, applying the pre-registered S6.3 reading rule with
no discretion exercised, is the **second row of its table**:

> **EFFECT REFUTED — interaction 95% CI comfortably spans no-effect [0.9526, 1.0421] around
> 0.9964, and both paired Wilcoxon tests are nowhere near significance (p=0.44, p=0.84).
> The original 30-cycle, ~10-13% "capture-chain effect" was noise. DROP IT. Strike S3's
> percentages from the record, per S9.**

This is consistent with, and now directly explains, the ruling's own S4 finding that the
original 30-cycle sample was confounded: it sat at 2.34 s of drift, at the cliff edge, so what
looked like a WAV-source effect was almost certainly the capture-clock-drift defect leaking
into a sample the original design never controlled for. With drift actually excluded (this
measurement's whole point), the effect vanishes to within noise.

## 1. Results (n=300, |drift| < 0.5 s only)

Pooled 2x2 (unique cycle,message decodes, 300 cycles):

| | our WAV | WSJT-X WAV |
|---|---:|---:|
| **our decoder** | 6118 (a) | 6139 (b) |
| **jt9** | 10091 (c) | 10089 (d) |

- Capture-chain ratio, our decoder: **1.0034 (+0.3%)** — compare the original n=30 estimate of
  +12.5%.
- Capture-chain ratio, jt9: **0.9998 (-0.0%)** — compare the original n=30 estimate of +9.9%.
- Interaction `ad/bc` = **0.9964, 95% CI [0.9526, 1.0421]** — spans 1.0 (no interaction) with
  wide margin either side.

Paired per-cycle Wilcoxon signed-rank (the decisive test per S6.2 — pooled ratios ignore
intra-cycle correlation and overstate significance):

| decoder | mean(our WAV) | mean(WSJT-X WAV) | W | p |
|---|---:|---:|---:|---:|
| ours | 20.393 | 20.463 | 10526.0 | 0.4442 |
| jt9 | 33.637 | 33.630 | 8096.0 | 0.8364 |

Both p-values are an order of magnitude past even the "ambiguous" band (0.01-0.05), let alone
the 0.01 bar for confirmation. At n=300 (10x the original sample, nominal z ~4.9 if a
+12.5% effect were real per the ruling's own S6.4 power table), finding p=0.44 is not "still
underpowered" — it is a clean null.

## 2. Why the sign flipped (+0.3% here vs +12.5%/+9.9% originally) — not a red flag

The point estimate landing almost exactly at 1.0 rather than merely "smaller but still
positive" is expected, not suspicious: the original sample's confound (S4's finding) was
specifically that OpenWSFZ's WAV was truncating content relative to WSJT-X's *because of
drift*, at a sample sitting right at the drift cliff. Remove the drift (this measurement's
entire design) and there is no remaining physical reason for OpenWSFZ's own capture of the
same feed to systematically under-perform WSJT-X's — which is exactly what a ratio of
0.9998-1.0034 says.

## 3. What this does NOT do

- Does not run the secondary (dose-response / DT-tolerance-curve) arm from S6.2 — that arm is
  explicitly descriptive, not subject to S6.3's reading rule, and Measurement C's collapsed-vs-
  healthy split already delivers the practically relevant version of that same information
  (the cliff sits where predicted, S6b's free-by-product). Not run here as a separate item;
  flagged rather than silently substituted.
- Does not itself edit S3/S9 of the ruling or QA's original findings note — S6.3's own
  consequence column routes the strike-through to whoever owns those documents next (the
  Architect, per S9's existing table format).
- Does not touch `src/` or native code. No push, no merge (HK-014/HK-010) — committed locally.
  No `pre_merge_check.py` run implied (HK-006).
- NFR-021: message text was read only for per-cycle de-duplication and matching (identical
  convention to `anova_common.py`); WAV copies and per-decode output live under git-ignored
  `_work/`. Only aggregate counts and statistics left the script.

## 4. Cross-references

- `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` S6 (§R
  revision) — the redesign and reading rule this document applies mechanically.
- `measurement_b_capture_chain.py`, `measurement_b_capture_chain_report.md` — script and
  full output.
- `2026-07-31-0210-qa-measurement-c-result-drift-collapse-confirmed-recoverable.md` — the
  companion measurement whose drift regression this one's cycle selection reused, and whose
  result explains *why* the original 30-cycle sample was confounded.
- `2026-07-30-2221-qa-to-architect-capture-chain-and-cross-band-findings.md` §3 — the original
  n=30 finding this measurement supersedes.

---

*Per HK-015 this is QA -> Architect/Captain material. Per HK-014/HK-010 committed locally, no
push, no merge. Per HK-011 nothing here touches `src/`. Per HK-017 filename and byline both
carry `date -u` UTC. Striking S3/S9 in the ruling itself, and any consequence for the row 4
decomposition, remain the Architect's/Captain's to action.*
