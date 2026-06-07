## 1. Scenario definition

- [x] 1.1 Create `qa/rr-study/scenarios/s8-band-scene.json` with `id = "S8"`, `trials: 5`, and the 12-station `signals` array as specified in design.md (stations A–L: freq 450–2550 Hz, SNR −15 to +3 dB, Q-prefix callsigns only, including the near-collision pair E/F at 1150/1162 Hz and capture pair G/H at 1500 Hz 0/−6 dB)
- [x] 1.2 Verify all `message_text` values are valid FT8 messages that the synthesiser encoder can pack without error (run a quick dry-render check or unit test)

## 2. Harness render path

- [x] 2.1 Add `_render_band_scene(scenario, seed)` to `qa/rr-study/harness/run_scenario.py` — reads `scenario["signals"]`, encodes each clean at 48 kHz, delegates to `channel.mix_to_shared_floor()`, returns `(mixed_samples, signals_meta)` following the S7 pattern
- [x] 2.2 Add `is_s8 = (scenario_id == "S8")` dispatch branch in `_run()` alongside the existing `is_s4` / `is_s7` branches; wire up truth-row logging using the per-signal S7 pattern (one truth row per signal per trial)
- [x] 2.3 Add `"S8"` to the valid scenario ID dispatch so `run_scenario.py` does not hit the default single-signal path

## 3. Study runner

- [x] 3.1 Add `--skip-s8` flag to `run_study.py`'s argument parser
- [x] 3.2 At startup (before any scenario loop), prompt `"Run S8 realistic band scene first? [Y/n]"` unless `--skip-s8` was passed; default answer is Y (bare Enter = include S8)
- [x] 3.3 Conditionally prepend `s8-band-scene.json` / `"S8"` to the scenario and ID lists only when the operator confirms (or when `--skip-s8` is absent and Y is accepted)

## 4. Matcher

- [x] 4.1 Confirm `qa/rr-study/harness/matcher.py` handles `scenario_id = "S8"` correctly via the existing per-signal truth-row path (same as S7 — verify no S7-specific guard blocks S8)

## 5. Analyser

- [x] 5.1 Add S8 summary section to `qa/rr-study/harness/analyse.py`: total injected (60), decoded count and percentage per appraiser, between-appraiser delta in percentage points
- [x] 5.2 Add per-station breakdown table to the S8 section: one row per station (A–L) showing decode rate (trials decoded / 5) for WSJT-X and OpenWSFZ
- [x] 5.3 Ensure no PASS/FAIL verdict line is emitted for S8 in the report (informational benchmark only)

## 6. Dry-run verification

- [x] 6.1 Run `python harness/run_scenario.py scenarios/s8-band-scene.json --dry-run` from `qa/rr-study/` and confirm 5 trials render without error, correct sample count (5 × 720 000 samples at 48 kHz), and truth.csv contains 60 rows with `scenario_id = "S8"`
- [x] 6.2 Play the rendered S8 audio on a speaker or headphones and confirm it sounds perceptibly like a busy FT8 band (multiple simultaneous tones sweeping across the passband) — this is a qualitative human-ear check, not a unit test (preview WAV written to qa/rr-study/s8-preview.wav). **Two audio defects found and fixed during this check:** (1) PortAudio hard-clipping 69.9 % of samples — root cause: wideband noise sigma ≈ 2.0 at 48 kHz exceeds ±1.0 float range; fixed by normalising to 0.9 peak before `sd.play()` in `_run()`. (2) Noise bandwidth mismatch — white noise occupied 0–24 kHz instead of simulating a real receiver's 3–4 kHz audio passband; fixed by applying a 4 kHz FFT brick-wall lowpass to the generated noise floor in `mix_to_shared_floor` (parameter `noise_cutoff_hz=4000` added to S4/S7/S8 render paths). In-band SNR (2 500 Hz reference) is mathematically preserved. Noiseless preview `s8-preview-clean.wav` also written to confirm sine-wave synthesis is correct.
