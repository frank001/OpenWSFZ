# Live cross-decode replay — full ANOVA report (n=5 runs)

**Author:** QA, 2026-08-06 (21:15 UTC, `date -u`, per HK-017). Repo `main` at `f6c5b46`.
**Requested by:** the Captain — "turn this test into a real anova... do another 4 and
create a full ANOVA report," then, after a methodology question about confounding,
"prepare the 3-way anova."
**Full report:** `qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay/full_anova_report.md`
(+ `.html`), `full_anova_summary.json`. Scripts: `run_cross_decode_replay.py`,
`build_full_anova.py`, both in the same directory.

---

## 1. Design

5 independent live replays of the identical 20-cycle window (`260804_085845` →
`260804_090330`, the busiest 5-minute window in `20260803_live_run_1713`). Every run: same
20 cycles, WSJT-X-source WAVs replayed first, then OpenWSFZ-source WAVs, both decoders
listening to `CABLE Output` simultaneously in real time — no offline `jt9`. Two statistical
designs, both new machinery built and validated (synthetic data + a dry run on duplicated
real data) before the real runs landed:

1. **3-way ANOVA** (Decoder × Source × Cycle, Run=5 replicates) — the direct answer to
   "are Decoder and Source confounded." Fixed-effects model, every term tested against the
   pure run-to-run residual.
2. **Per-source 2-way ANOVA** (Decoder × Cycle × Run) for decode count, and the project's
   established RCBD (Part × Appraiser) for SNR/DT/frequency — both run separately per
   source, as originally planned.

## 2. The confounding question, answered

| effect | F | p | %SS |
|---|---:|---:|---:|
| Decoder | 17423.0 | <0.000001 | 84.7% |
| Source | 5.2 | 0.0233 | 0.03% |
| Decoder × Source | 0.16 | 0.688 | 0.0008% |
| Cycle | 114.6 | <0.000001 | 10.6% |
| Decoder × Cycle | 32.1 | <0.000001 | 3.0% |
| Source × Cycle | 0.9 | 0.602 | 0.08% |
| Decoder × Source × Cycle | 1.55 | 0.066 | 0.14% |

**Decoder and Source are not confounded.** Every cell of the design has both decoders
decoding the same audio; the Decoder effect (84.7% of total variance) is not contaminated
by Source in any way this model can detect.

**Source itself is statistically detectable but trivial, and still can't be called
"Source"** — it's perfectly aliased with within-run pass order (WSJT-X-source always
played first, every run, no counterbalancing). At 0.03% of total variance it is not
practically meaningful regardless of what's driving it. The **Decoder × Source interaction
is not significant** (p=0.688) — whatever the tiny Source-or-order effect is, it does not
depend on which decoder is decoding, which is the strongest evidence available that it is
a shared artifact of running two passes in sequence, not a genuine difference between the
two capture chains' audio (consistent with the earlier WAV-content-comparison note, which
found in-band audio essentially identical between the two chains).

## 3. Decode count — robust, not a fluke

Per-source 2-way tables (AIAG convention, main effects vs. interaction):

| | OpenWSFZ mean/cycle | WSJT-X mean/cycle | Decoder F | p |
|---|---:|---:|---:|---:|
| WSJT-X-source | 23.07 | 37.79 | 482.7 | <0.00001 |
| OpenWSFZ-source | 22.77 | 37.58 | 557.9 | <0.00001 |

**Run-to-run repeatability is tiny relative to the decoder gap** — 0.8–1.3% of total
variance vs. ~91% for Decoder (variance-components tables, full report). The five runs'
raw WSJT-X-source-pass counts: **752, 754, 758, 759, 756** — a span of 7 across independent
live sessions. This is about as reproducible as a live measurement gets.

**The 2026-08-06-2022 note's standout finding is now confirmed, not a one-off.** Every one
of the 5 replicate runs put WSJT-X's decode count on this window at 748–759 — tightly
clustered, and **every single one roughly 2.3× the original archived live count for these
same 20 cycles (328)**. Whatever suppressed WSJT-X's live yield on 2026-08-03/04 is
consistent enough that five independent replays land nowhere near it. Still no root cause
established (unverified hypothesis remains CPU contention during the original session);
this result raises confidence that the gap is real and systematic rather than
measurement noise, and does the opposite of explaining it away.

## 4. SNR / DT / frequency — pooled across 5 runs (~2,200+ matched pairs per source)

| | SNR (dB) | DT (s) | Frequency (Hz) |
|---|---:|---:|---:|
| WSJT-X-source: OpenWSFZ | −6.12 | 1.388 | 1482.0 |
| WSJT-X-source: WSJT-X | −3.73 | 0.735 | 1481.9 |
| OpenWSFZ-source: OpenWSFZ | −6.49 | 1.387 | (same) |
| OpenWSFZ-source: WSJT-X | −4.30 | 0.731 | (same) |

- **SNR**: OpenWSFZ reads ~2.4–2.6 dB low, both sources, p<0.0001 — matches the
  already-tracked S7 gain-error calibration issue, now with a much larger, cleanly
  significant sample.
- **DT**: OpenWSFZ reports ~0.65 s later than WSJT-X, both sources, extremely consistently
  (0.653 s / 0.656 s) — same order of magnitude and same sign as the single-run finding.
  The caveat from the 2026-08-06-2022 note stands: this is measured on the replay
  pipeline's own latency, not directly comparable to the 2026-07-30 hardware-tracked DT
  signature.
- **Frequency**: 1482.0 vs 1481.9 Hz — technically "significant" (p<0.0001) purely because
  the pooled sample is large enough to detect a 0.1 Hz difference; not practically
  meaningful. Flagged so the p-value isn't misread as a real effect — statistical and
  practical significance diverge here on purpose, as an illustration of why %SS/effect
  size matters alongside p.

## 5. What this does and does not settle

- **Settles the confounding question directly**: Decoder is clean; Source-or-order is
  real but negligible and decoder-independent.
- **Does not settle what Source-or-order actually is** — order was never counterbalanced
  across the 5 runs, so this design cannot separate "which capture chain" from "which pass
  of the run." A future run alternating the pass order would resolve it; not proposed here
  without direction, per this project's cost discipline.
- **Strengthens, does not explain, the WSJT-X original-live-vs-replay decode gap** (§3) —
  the single most consequential number to come out of this whole exercise, now backed by 5
  independent replications instead of 1.
- **Replicates, at much higher confidence, every finding from the single-run note**: decoder
  gap real and large, SNR/DT offsets consistent, frequency agreement near-exact.

## 6. Cross-references

- `qa/cycleframer-alignment-replay/2026-08-06-2022-qa-live-cross-decode-replay-results.md`
  — the single-run version this replicates and extends.
- `qa/rr-study/harness/anova_compute.py` — the Gauge-R&R design the decode-count ANOVAs
  generalise from.
- `qa/endurance/anova_common.py` — the RCBD design reused unchanged for SNR/DT/freq.
- `qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay/` — all scripts,
  per-run raw data (`_work/run1`..`run5`, git-ignored), and the full report.

---

*Per HK-011 nothing here touches `src/`. Per HK-014/HK-010 committed locally, no push, no
merge implied. Per NFR-021, all scripts read message text only to build match keys —
never printed, never written to any committed file.*
