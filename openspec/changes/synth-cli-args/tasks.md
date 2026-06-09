## 1. Branch

- [x] 1.1 Create branch `feat/synth-cli-args` from `main`

## 2. gen_decoder_fixtures.py — expose render constants as CLI flags

- [x] 2.1 Add an `argparse.ArgumentParser` block to `main()` with flags
  `--snr-db` (float, default 15.0), `--seed` (int, default 20260606),
  `--dt` (float, default 0.2), `--sample-rate` (int, default 12000),
  `--output-dir` (str, default path to `tests/OpenWSFZ.Ft8.Tests/Fixtures/`
  computed relative to the script's own location as before)
- [x] 2.2 Remove the four module-level constants `_SNR_DB`, `_SEED`, `_DT_S`,
  `_SAMPLE_RATE_HZ`; thread the parsed values through `_render_fixture()`
  and the `main()` loop so `argparse` defaults are the single source of truth
- [x] 2.3 Verify: run with no arguments and confirm the output WAV files are
  created in the correct Fixtures directory (spot-check file size / existence)

## 3. resume_study.py — replace hardcoded scenario set with --from-scenario

- [x] 3.1 Add an `argparse.ArgumentParser` block to `main()` with flags
  `--device` (str, default `"CABLE Input"`) and
  `--from-scenario` (str, choices `S2 S3 S4 S5 S7 S8`, default `"S2"`)
- [x] 3.2 Replace the hardcoded `REMAINING_SCENARIOS` and `ALL_SCENARIO_IDS`
  lists with logic derived from `--from-scenario`:
  - Full controlled order: `[S2, S3, S4, S5, S7]` (S8 excluded from resume)
  - Scenarios to *play*: slice from `--from-scenario` to end of the list
  - Scenarios to *match*: `[S1]` + scenarios to play
  - Wire `args.device` through the `run()` call that invokes `harness/run_scenario.py`
- [x] 3.3 Verify: run `--from-scenario S4` (dry logic check, no live playback needed)
  and confirm the play set is `[S4, S5, S7]` and the match set is `[S1, S4, S5, S7]`
  (add a `--dry-run` print or trace through the code manually)

## 4. synth_wav.py — new standalone WAV generator

- [x] 4.1 Create `qa/rr-study/synth_wav.py` with a `main()` and argparse:
  positional `MESSAGE`; optional `--freq` (float, 1500.0), `--snr` (str, `"0.0"`),
  `--dt` (float, 0.0), `--seed` (int, 0), `--rate` (int, 48000),
  `--cutoff` (float, omitted), `--out` (str, omitted)
- [x] 4.2 Implement `--snr` sentinel: if the value is `"none"` or `"clean"`
  (case-insensitive), pass `snr_db=None` to `encoder.encode_message`; otherwise
  parse as float and pass as `snr_db`; raise `argparse.ArgumentTypeError` on
  invalid values
- [x] 4.3 Implement default output filename: lowercase MESSAGE, spaces to underscores,
  strip non-alphanumeric (keep underscores), truncate to 40 chars, append `.wav`
- [x] 4.4 Wire the pipeline: `encoder.encode_message(MESSAGE, base_freq_hz=--freq,
  dt_s=--dt, snr_db=..., seed=--seed, sample_rate_hz=--rate)`;
  if `--cutoff` is given, call `channel.add_noise(..., noise_cutoff_hz=--cutoff)`
  instead (clean render + bandlimited noise); write via `wavio.write_wav(--out, samples, --rate)`
- [x] 4.5 Print one-line summary on success:
  `Wrote <path> (<n> samples @ <rate> Hz, SNR=<value> dB)` or
  `Wrote <path> (<n> samples @ <rate> Hz, clean)`
- [x] 4.6 Verify: run `synth_wav.py "CQ Q1ABC FN42"` and confirm `cq_q1abc_fn42.wav`
  is created; run with `--snr none` and confirm the summary says `clean`;
  run with `--snr bad` and confirm a clean error message

## 5. Commit

- [ ] 5.1 Commit all three file changes with a clear message and open a PR
