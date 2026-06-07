## Why

The R&R study's playback is dominated by single-signal controlled scenarios (S1, S2, S3 account for roughly 90 of the ~150 cycles played per run), each injecting one FT8 message at 1500 Hz. This sounds nothing like a real busy FT8 band — the characteristic "multi-tone whistling" texture of on-air FT8 is an emergent property of ten to thirty simultaneous stations — and it means the study never exercises the decoder against the holistic complexity that users actually experience. A fixed, human-readable multi-station band-scene scenario (S8) is needed to complement the per-variable controlled tests and to give both appraisers (WSJT-X and OpenWSFZ) a realistic stress test.

## What Changes

- **New scenario file** `qa/rr-study/scenarios/s8-band-scene.json` — a fixed band profile of 12 simultaneous stations at diverse audio frequencies (450–2550 Hz), realistic SNR spread (−15 to +3 dB), and deliberately varied message types (CQ, exchange, 73/RR73). The profile is static and human-readable; it does not change between study runs, making results directly comparable across versions.
- **New harness render path** — `run_scenario.py` gains `_render_band_scene()`, which reads the fixed signal list from the scenario JSON and delegates to `channel.mix_to_shared_floor()` (already implemented) at 48 kHz. No new synthesis primitives are needed.
- **Harness scenario dispatch** — the scenario `id = "S8"` branch is added to the `_run()` dispatcher alongside the existing S1–S7 branches.
- **Study runner** — `run_study.py` adds `s8-band-scene.json` to `SCENARIO_FILES` and `"S8"` to `SCENARIO_IDS`, so S8 runs first in every full study (before the controlled scenarios, as a "cold listening" check).
- **Analyser** — `analyse.py` gains an S8 summary section reporting holistic decode rate (messages decoded / messages injected) per appraiser, plus a between-appraiser delta, with no PASS/FAIL gate (S8 is informational).

## Capabilities

### New Capabilities

- `rr-band-scene`: S8 scenario definition, harness render path, and analyser reporting for a fixed realistic multi-station band scene used as a holistic decode-rate benchmark in the R&R study.

### Modified Capabilities

*(none — no existing spec-level requirements change)*

## Impact

- `qa/rr-study/scenarios/s8-band-scene.json` — new file
- `qa/rr-study/harness/run_scenario.py` — new `_render_band_scene()` function and S8 dispatch branch
- `qa/rr-study/run_study.py` — S8 added to study sequence (first position)
- `qa/rr-study/harness/analyse.py` — S8 holistic metrics section
- `qa/rr-study/harness/matcher.py` — S8 truth matching (one truth row per signal, same pattern as S7)
- No changes to the product source (`src/`), tests (`tests/`), or CI pipeline.
