## 1. STUDY-SPEC and RUNBOOK updates

- [x] 1.1 Expand STUDY-SPEC §6 S6 entry from the one-liner placeholder into a full sub-specification: study type (attribute agreement), parts (42 WAVs), appraisers (WSJT-X + OpenWSFZ), K=3 runs, order randomisation, four measurements (consistency, κ, SNR delta, order effect), informational verdict (no PASS/FAIL gate), GDPR handling
- [x] 1.2 Add S6 corpus replay procedure to `RUNBOOK.md`: pre-run checklist (VB-CABLE routing, both apps in monitor mode, corpus path configured), run command, expected duration (~42 × 3 × 15 s ≈ 32 minutes), post-run scrub-and-commit step

## 2. Corpus replay harness — `corpus_replay.py`

- [x] 2.1 Implement WAV file discovery: scan the configured corpus directory for `*.wav` files matching the p10 naming pattern (`YYMMDD_HHMMSS.wav`); assert count == 42 or warn and continue
- [x] 2.2 Implement per-run order randomisation: for run index R, shuffle the WAV list with `seed = hash("S6", R)`; log the seed and order to a local run manifest
- [x] 2.3 Implement UTC 15-second cycle alignment: wait for the next UTC boundary before playing each WAV (reuse or import the timing logic from `run_study.py`)
- [x] 2.4 Implement WAV playback through sounddevice into VB-CABLE: resample from 12 kHz (corpus format) to 48 kHz (VB-CABLE preferred rate) if necessary; play mono signal
- [x] 2.5 Implement ALL.TXT snapshot capture: after each WAV cycle, copy the relevant decode lines from both WSJT-X and OpenWSFZ ALL.TXT files into a local run snapshot (keyed by WAV filename and run index)
- [x] 2.6 Implement run loop: execute K=3 runs; write a local `run_manifest.json` recording WAV order, seeds, and timing for reproducibility
- [x] 2.7 Add warmup guard: before the study run begins, play one silent cycle and confirm both apps are in a decoding state (adapt warmup logic from `harness/warmup.py`)

## 3. Analysis script — `analyse_corpus.py`

- [x] 3.1 Implement signal identity key: `(normalised_message_text, freq_bin_50hz)` where `freq_bin_50hz = round(freq_hz / 50) * 50`; apply to all decode rows from both appraisers
- [x] 3.2 Implement within-appraiser consistency computation: for each appraiser, for each (WAV, signal) pair, check whether the decode decision (decoded / not-decoded) is identical across all K runs; report as % consistent and count of inconsistent pairs
- [x] 3.3 Implement signal universe construction per WAV: union of all signals decoded by either appraiser in any run of that WAV
- [x] 3.4 Implement between-appraiser Cohen's κ: build the per-instance confusion matrix over all (WAV, run, signal) instances from the signal universe; compute κ and 95% CI using the standard formula
- [x] 3.5 Implement SNR delta computation: for every (WAV, run, signal) where both appraisers decoded the signal, compute `SNR(OpenWSFZ) − SNR(WSJT-X)`; report mean, std dev, and count; produce scatter plot (OpenWSFZ SNR vs WSJT-X SNR)
- [x] 3.6 Implement order effect test: for each appraiser, compute Spearman ρ between presentation order rank and per-WAV decode count across all K runs; flag p < 0.05 as a potential order effect
- [x] 3.7 Implement callsign scrub pass: apply ITU callsign pattern regex to all text that will be committed; replace matches with `[CALL]`; abort with non-zero exit code if any unclassifiable pattern is found
- [x] 3.8 Implement report writer: emit `report.md` (aggregate statistics, scrubbed), `summary.csv` (per-WAV metrics, no message text), and PNG plots (consistency bar chart, κ confidence band, SNR delta scatter) to the committable results directory

## 4. Results directory and gitignore

- [x] 4.1 Add `qa/rr-study/results/corpus-*/raw/` to `.gitignore` to ensure raw ALL.TXT snapshots and unscubbed CSVs are never committed
- [x] 4.2 Confirm that `qa/rr-study/results/corpus-*/report.md`, `summary.csv`, and `*.png` are NOT excluded (these are the scrubbed committable artifacts)

## 5. Validation

- [x] 5.1 Dry-run `corpus_replay.py` with K=1 and 3 WAVs from the corpus; confirm timing alignment, simultaneous capture, and local snapshot output
- [x] 5.2 Dry-run `analyse_corpus.py` on the K=1 dry-run output; confirm consistency, κ, SNR delta, and order-effect outputs are well-formed
- [x] 5.3 Confirm callsign scrub pass: seed the raw output with a known real callsign pattern; confirm it is replaced by `[CALL]` in the committed artifact
- [x] 5.4 Run the full study (K=3, all 42 WAVs); commit the scrubbed report and summary to `qa/rr-study/results/corpus-<date>/`
- [x] 5.5 Verify no real callsigns appear in the committed artifacts: `git diff HEAD --name-only` + manual inspection of `report.md` and `summary.csv`
