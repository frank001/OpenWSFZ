## Context

The existing synthetic R&R study (S1–S8) runs via `run_study.py`, which drives the synthesiser, plays audio through VB-CABLE, and reads `ALL.TXT` from both WSJT-X and OpenWSFZ. The study is fully automated — no operator interaction required after setup.

S6 ("Off-air corpus") has been a one-line placeholder since ratification. The local corpus at `p10-decoder-ground-truth_items/` already exists: 42 × 15-second WAVs, 12 kHz mono int16, captured on 7.074 MHz. This corpus is git-ignored (NFR-021: real callsigns). It was previously used only for the p10 offline replay harness (recovery rate vs WSJT-X answer key, one pass, WSJT-X as ground truth). The new study uses it differently: as a source of real-world audio scenes for an agreement and consistency study, with no WSJT-X-as-truth assumption.

The key structural difference from the synthetic study is that **there is no injected ground truth**. The measurands are consistency (does the same decoder give the same answer twice?) and agreement (do two decoders give the same answer?), not accuracy vs a known standard.

## Goals / Non-Goals

**Goals:**
- Implement S6 as a full corpus-based attribute agreement study with order randomisation
- Measure within-appraiser consistency for both WSJT-X and OpenWSFZ
- Measure between-appraiser agreement (Cohen's κ) per-signal
- Measure SNR delta (OpenWSFZ − WSJT-X) for matched decodes as a field validation of D-002
- Detect order effects (session-state / cycle-history dependence) in either decoder
- Produce committed report artifacts free of real callsigns (NFR-021)
- Reuse the existing VB-CABLE / ALL.TXT pipeline established by the synthetic study

**Non-Goals:**
- Replacing or modifying the synthetic S1–S8 study or its harness
- Establishing a PASS/FAIL regression gate (S6 is informational, like S7/S8)
- Solving the ground-truth problem — this study deliberately makes no claim about what is truly in each WAV
- Testing the corpus WAVs for authenticity or provenance
- Committing WAV files or raw decode logs to VCS

## Decisions

### D-1: Pure agreement study — no ground truth

**Chosen:** No ground truth; measure consistency and agreement only.

**Rejected: WSJT-X majority vote as ground truth** — circular for the WSJT-X self-consistency arm. If WSJT-X is the reference, its repeatability is by definition 100%, hiding any real non-determinism. The study's most valuable finding would be destroyed.

**Rejected: Consensus union** — the union of all decodes across all runs and both appraisers inflates false positives and makes the within-appraiser metric sensitive to FP rate rather than consistency.

### D-2: Randomise WAV presentation order independently per run

Each of the K=3 runs presents the 42 WAVs in a freshly seeded random order. The seed is derived from `hash("S6", run_index)` for reproducibility. This detects order effects: if decode results for WAV_i correlate with its position in the sequence, there is session-state carryover in that decoder.

**Rejected: Fixed sequential order (chronological)** — cannot detect order effects; any state carryover would be invisible.

**Rejected: Fully randomised without seeding** — unreproducible; cannot re-run to verify a finding.

### D-3: Both appraisers hear each WAV simultaneously (crossed design)

The same VB-CABLE pipeline as the synthetic study. `corpus_replay.py` plays each WAV into VB-CABLE; both WSJT-X and OpenWSFZ capture from VB-CABLE output simultaneously. This mirrors the synthetic study's crossed design and eliminates between-appraiser timing differences as a confound.

**Rejected: Sequential (WSJT-X first, then OpenWSFZ)** — introduces a temporal confound. If the band changes between the two runs (it cannot for a WAV file, but the VB-CABLE state might differ), results are not comparable.

### D-4: WAV playback aligned to 15-second UTC cycle boundary

`corpus_replay.py` waits for the next UTC 15-second boundary before playing each WAV, exactly as `run_study.py` does for synthesised audio. Both decoders align their decode windows to the 15-second UTC grid; playing mid-cycle would produce a partial decode.

The original timestamp in the WAV filename is ignored for playback timing — the harness plays each WAV at the current real-time UTC cycle, not at the original capture time. Both decoders see the audio as a current cycle.

### D-5: Signal identity for agreement matching — text + frequency

A decoded signal is identified by `(message_text_normalised, freq_hz_rounded_to_nearest_50)`. Frequency binning to 50 Hz accounts for the ±4 Hz decoding tolerance already established in STUDY-SPEC §8. Two appraisers are considered to have agreed on a signal if they both produced a match for the same `(text, freq_bin)` key within the same WAV × run.

**Rejected: Text alone** — the same message (e.g., `CQ Q1ABC FN42`) can appear at multiple frequencies from different stations; text-only matching produces false agreements.

**Rejected: Exact frequency match** — WSJT-X and OpenWSFZ report integer Hz; a ±1–2 Hz rounding difference would create false misses. The 50 Hz bin is conservative (one FT8 signal occupies ≈50 Hz).

### D-6: SNR delta computed only for cross-appraiser matched decodes

`SNR_delta = SNR(OpenWSFZ) − SNR(WSJT-X)` is computed only when both appraisers decoded the same signal (same `(text, freq_bin)`) in the same WAV × run. This gives a direct field comparison of SNR reporting, independent of decode rate differences. The mean delta across all matched pairs is the field equivalent of the S1 bias measurement.

### D-7: GDPR — two-tier result storage

**Local only (never committed):**
- Source WAVs (`p10-decoder-ground-truth_items/*.wav`)
- Raw `ALL.TXT` snapshots from each run (contain real callsigns)
- Raw matched CSV (contains real callsigns in `message_text`)

**Committed (callsigns scrubbed):**
- `report.md` — aggregate statistics only; any example decode text uses Q-prefix placeholders
- `summary.csv` — per-WAV aggregate metrics (match counts, consistency flags, SNR deltas) with no message text column
- PNG plots — frequency/SNR distributions with no text labels identifying callsigns

The scrub step is a post-analysis pass that replaces any string matching an ITU callsign pattern with `[CALL]` before writing committed artifacts.

## Risks / Trade-offs

**[Risk] WSJT-X is deterministic in monitor mode → within-appraiser consistency = 100%, order effect = 0** → This is a valid finding, not a failure. It means WSJT-X's context-awareness is purely a UI/active-QSO feature and does not affect the decode engine in monitor mode. Document as conclusion, not as a null result.

**[Risk] OpenWSFZ is deterministic → same outcome** → Also a valid finding; confirms stateless-per-cycle design. No mitigation needed.

**[Risk] VB-CABLE audio routing introduces per-run variance** → Mitigated by the crossed design (both appraisers hear identical audio); any VB-CABLE timing jitter affects both equally and cancels in the agreement metric.

**[Risk] 42 WAVs is a small corpus for κ estimation** → With ~20 signals per WAV, the total signal-instance count is ~840. This is sufficient for a 95% CI on κ with width ≈ ±0.05 at κ ≈ 0.70. Acceptable for an informational study; noted in the report.

**[Risk] Callsign scrub misses a pattern** → Mitigation: the scrub regex is validated against the raw CSV before the committed artifact is written; if any unrecognised callsign pattern is found, the commit step aborts and flags for manual review.

## Migration Plan

No migration required. The new scripts are additive to `qa/rr-study/harness/`. Existing synthetic study scripts are untouched. The local corpus is already in place. The study is run on demand, not in CI.

## Open Questions

**OQ-1:** Should K=3 runs be the default, or K=5 to improve κ confidence intervals? — Propose K=3 to match the synthetic study trials convention; can be increased if the first run reveals high within-appraiser variance warranting tighter estimation.

**OQ-2:** Should the 50 Hz frequency bin for signal identity be confirmed empirically before the first run, or accepted from the STUDY-SPEC §8 ±4 Hz tolerance? — Accept from STUDY-SPEC §8; can be tuned if matching analysis shows unexpectedly high miss rates on clearly-same signals.
