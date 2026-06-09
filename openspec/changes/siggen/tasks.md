## 1. Branch

- [ ] 1.1 Create branch `feat/siggen` from `main`

## 2. Scaffold `siggen.py` — argument parser and entry point

- [ ] 2.1 Create `qa/rr-study/siggen.py` with a `main()` and `argparse.ArgumentParser`:
  positional `SCENE_FILE` (mutually exclusive with `--batch`); optional `--out` (str),
  `--device` (str), `--rate` (int, default 48000), `--duration` (float); flag `--batch`
  (str path). Add the `sys.path` insert for `qa/rr-study` as the package root
  (matching the pattern in `synth_wav.py`)
- [ ] 2.2 Implement the two top-level dispatch paths in `main()`: single-scene mode
  (SCENE_FILE supplied) and batch mode (`--batch` supplied). Raise a parser error if
  neither or both are given

## 3. JSONL scene file parser

- [ ] 3.1 Implement `parse_scene(path: str) -> tuple[dict, list[dict]]` that reads the
  JSONL file line by line, skips blank lines and lines whose stripped form begins with
  `#`, calls `json.loads` on each remaining line, and separates `"type":"scene"` objects
  (last-wins for duplicates) from signal descriptor objects. Return `(scene_config,
  signals)`
- [ ] 3.2 Implement `resolve_config(scene_config: dict, args: argparse.Namespace) ->
  dict` that merges the parsed scene config with CLI flag overrides (`--out`, `--device`,
  `--rate`, `--duration`) — CLI flags take precedence. Validate that at least one output
  sink is present; if not, exit with a descriptive error
- [ ] 3.3 Implement `_parse_amplitude(d: dict) -> float` helper: returns `d["amplitude"]`
  if present, `10 ** (d["level_dbfs"] / 20)` if `level_dbfs` is present, or `1.0` if
  neither is present. Raises `ValueError` if both are present

## 4. Signal renderers — primitive types (no FT8 dependency)

All renderers SHALL have the signature
`render_<type>(d: dict, n_samples: int, sample_rate: int) -> np.ndarray`
and return a float64 array of length `n_samples` with the signal placed at `d["start_s"]`.

- [ ] 4.1 Implement `render_sine`: generate a sinusoid using `np.sin(2π·freq·t + phase)`
  scaled by amplitude, placed in a zero-filled slot buffer at `start_s`
- [ ] 4.2 Implement `render_square`: additive synthesis of odd harmonics
  (`scipy.signal.square` or manual Fourier series up to Nyquist), scaled by amplitude,
  placed at `start_s`; honour `duty_cycle` (default 0.5)
- [ ] 4.3 Implement `render_sawtooth`: additive synthesis of harmonics
  (`scipy.signal.sawtooth` with `width=1`), scaled by amplitude, placed at `start_s`
- [ ] 4.4 Implement `render_triangle`: additive synthesis of odd harmonics with
  alternating signs (`scipy.signal.sawtooth` with `width=0.5`), scaled by amplitude,
  placed at `start_s`
- [ ] 4.5 Implement `render_chirp`: `scipy.signal.chirp(t, f0, t1, f1, method=method)`
  scaled by amplitude, placed at `start_s`; validate `method` is `"linear"` or
  `"logarithmic"`, reject unknown values with a descriptive error
- [ ] 4.6 Implement `render_noise`: generate `np.random.default_rng(seed).standard_normal
  (n_signal_samples) * amplitude`; apply `synth.channel._lowpass_fir` when `cutoff_hz`
  is present; place result at `start_s`. Seed resolution: use `d["seed"]` if present,
  else `scene_config["seed"]` (default 0)

## 5. Signal renderer — `ft8` type (lazy import)

- [ ] 5.1 Implement `render_ft8(d: dict, n_samples: int, sample_rate: int, scene_config:
  dict) -> np.ndarray`: on first call, import `synth.encoder` and `synth.constants`
  inside the function body (lazy import per design D-5). Reject the descriptor with a
  clear error if `"duration_s"` is present. Call `encoder.encode_message(text,
  base_freq_hz=freq_hz, dt_s=dt_s, snr_db=None, sample_rate_hz=sample_rate)` to
  get the clean render, scale by amplitude, place at `start_s` in a zero-filled buffer
  of `n_samples`
- [ ] 5.2 Verify lazy import: add a comment assertion that `synth.encoder` does not
  appear in the module-level import block of `siggen.py`

## 6. Mix and output routing

- [ ] 6.1 Implement `render_scene(signals: list[dict], config: dict) -> np.ndarray`:
  compute `n_samples = ceil(duration_s * sample_rate)`; initialise a float64 zero
  buffer; dispatch each signal descriptor to its renderer; accumulate the result by
  in-place addition; return the mixed buffer
- [ ] 6.2 Implement `write_outputs(buffer: np.ndarray, config: dict) -> None`:
  if `config["out"]` is set, call `wavio.write_wav(path, buffer, sample_rate_hz)`
  (creates parent directories if needed); if `config["device"]` is set, normalise to
  0.9 peak, cast to float32, call `sounddevice.play(samples, samplerate, blocking=False)`
  then `sounddevice.wait()`. Print a one-line summary per output sink
- [ ] 6.3 Implement device selection helper `_select_device(substring: str) -> int`
  (reuse the same pattern as `harness/run_scenario.py`): case-insensitive substring
  match against output-capable devices; exit with device list on no match

## 7. Batch mode

- [ ] 7.1 Implement `run_batch(batch_path: str, cli_overrides: dict) -> bool`: read the
  JSON array from `batch_path`; for each item, merge `cli_overrides` over the item's
  own `out`/`device`/`sample_rate`/`duration_s`; extract `item["signals"]` as the
  signal list; call `render_scene` and `write_outputs`; catch all exceptions per item,
  print `[item N] ERROR: <msg>` and continue; return `True` if all items succeeded,
  `False` if any failed
- [ ] 7.2 Wire `run_batch` into `main()`: call it when `--batch` is supplied; exit with
  code 1 if `run_batch` returns `False`

## 8. Verification

- [ ] 8.1 Verify single `sine` scene: `python siggen.py sine_test.jsonl --out sine.wav`
  with `{"type":"sine","freq_hz":1000,"amplitude":0.8,"start_s":0.0,"duration_s":1.0}`;
  confirm `sine.wav` is created, length ≈ 1 s, playable in an audio tool
- [ ] 8.2 Verify `chirp` scene: confirm frequency rises audibly from start to end of
  sweep
- [ ] 8.3 Verify multi-signal scene with `noise` + `sine` + `ft8`: confirm the output
  WAV is decodable by WSJT-X / libft8 (the FT8 signal survives the mix)
- [ ] 8.4 Verify FT8 lazy import: run a scene with only `sine` and `noise`; confirm no
  import error even if `synth.encoder` were to be missing (use a comment in the verify
  step recording that the import guard works)
- [ ] 8.5 Verify batch mode: create a 3-item `jobs.json`; confirm all three WAV files
  are produced; introduce a deliberate error in item 2 and confirm items 1 and 3 still
  complete
- [ ] 8.6 Verify device routing: run `python siggen.py scene.jsonl --device "CABLE Input"`
  and confirm the audio plays through VB-CABLE; verify simultaneous file + device by
  specifying both and confirming both outputs are produced

## 9. Documentation

- [ ] 9.1 Create `docs/siggen-reference.md` covering all sections required by the spec:
  overview, JSONL format, comment syntax, `"type":"scene"` fields, all signal type
  reference tables with examples, amplitude/level_dbfs mutual-exclusion rule, output
  routing, batch mode, and the R&R improvement recipes (R-001 through R-004)
- [ ] 9.2 Add a "General-purpose signal generator — siggen.py" section to
  `docs/rr-synth-cli-guide.md` with a two-sentence overview and a link to
  `docs/siggen-reference.md`

## 10. Commit and PR

- [ ] 10.1 Commit `qa/rr-study/siggen.py`, `docs/siggen-reference.md`, and the updated
  `docs/rr-synth-cli-guide.md` with a descriptive message
- [ ] 10.2 Open a PR targeting `main` referencing this OpenSpec change
