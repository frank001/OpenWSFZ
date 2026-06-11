## Why

The synthetic R&R study (S1–S8) controls all variables precisely but evaluates only engineered scenarios. S6 ("off-air corpus") has been a one-line placeholder in STUDY-SPEC §6 since the study was ratified. Building it now provides external validity that the synthetic scenarios cannot: real band conditions, genuine co-channel QRM, natural propagation variability, and a statistically robust sample of real-world decode behaviour across ~840 signal instances. It also provides a field validation of the D-002 SNR bias fix on audio that was never synthesised.

## What Changes

- **New R&R harness script** `qa/rr-study/harness/corpus_replay.py` — plays each of the 42 local off-air WAV files through VB-CABLE in independently randomised order, K=3 times per run; both WSJT-X and OpenWSFZ hear each WAV simultaneously (crossed design)
- **New analysis script** `qa/rr-study/harness/analyse_corpus.py` — computes within-appraiser consistency, between-appraiser Cohen's κ, SNR delta, and order-effect statistics; emits `report.md` + CSV + PNG
- **STUDY-SPEC §6 S6 entry** expanded from a one-liner into a full sub-specification matching the depth of S1–S8
- **GDPR (NFR-021) callsign-scrub step** in the commit pipeline: raw decode logs stay local-only; committed report artifacts contain only aggregate statistics and Q-prefix-scrubbed examples

## Capabilities

### New Capabilities

- `rr-corpus-replay`: Real-world off-air corpus replay study — harness, analysis, acceptance criteria, and GDPR handling for S6

### Modified Capabilities

_(none — no existing spec-level requirements change)_

## Impact

- `qa/rr-study/harness/` — two new Python scripts (`corpus_replay.py`, `analyse_corpus.py`)
- `qa/rr-study/STUDY-SPEC.md` — S6 section expanded
- `qa/rr-study/RUNBOOK.md` — corpus replay procedure added
- `qa/rr-study/results/` — new result directories per run (local-only for raw; committed for scrubbed aggregates)
- No changes to `OpenWSFZ.slnx`, production source, or native binaries
- No changes to existing synthetic scenarios (S1–S8) or their harness paths
- Local corpus `p10-decoder-ground-truth_items/` (already git-ignored) is the WAV source; no new files added to VCS
