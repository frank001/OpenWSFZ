## Context

The R&R synthesiser (`qa/rr-study/`) is a pure-Python QA instrument with no connection to
the .NET solution. It consists of three top-level entry points (`run_study.py`,
`resume_study.py`, `gen_decoder_fixtures.py`) and one harness driver
(`harness/run_scenario.py`). Two of those entry points contain hardcoded constants that
prevent reuse without source edits. A fourth entry point — standalone WAV synthesis —
does not exist at all.

The internal `synth.*` package already exposes a clean API:
`encoder.encode_message(text, base_freq_hz, dt_s, snr_db, seed, sample_rate_hz)`
and `channel.add_noise(..., noise_cutoff_hz)`, `wavio.write_wav(path, samples, rate)`.
All proposed CLI tools are thin wrappers over this existing API; no library changes are
needed.

## Goals / Non-Goals

**Goals:**
- Expose `gen_decoder_fixtures.py` render constants as optional flags with defaults
  that reproduce today's hardcoded behaviour exactly (no silent behaviour change).
- Make `resume_study.py` portable: `--device` and `--from-scenario` replace hardcoded
  machine-specific values.
- Provide `synth_wav.py` as a one-shot WAV synthesiser for ad-hoc use (perceptual
  checks, decoder smoke-tests, S8-preview regeneration).

**Non-Goals:**
- Modifying `run_study.py` or `harness/run_scenario.py` (already have adequate CLIs).
- Touching any file outside `qa/rr-study/`.
- Introducing new Python dependencies.
- Providing a batch or scripted invocation mode for `synth_wav.py` (one message per run
  is sufficient; shell loops cover the rest).

## Decisions

### D-1 — `argparse` with explicit defaults, not `os.environ` or config files

All three scripts use `argparse` with typed defaults matching the current hardcoded
values. Environment variables and config files add lookup complexity and hidden state;
explicit flags keep the call site self-documenting and match the style of the existing
`run_study.py` and `harness/run_scenario.py` CLIs.

### D-2 — `--snr none` sentinel for clean (noise-free) renders in `synth_wav.py`

`encoder.encode_message` already accepts `snr_db=None` to mean "no noise". The CLI
cannot distinguish a missing `--snr` from `--snr 0.0` if the default is `0.0`. Using
the string sentinel `"none"` (case-insensitive) lets the user request a clean render
explicitly, while a float value adds noise. Parsed once at argument-validation time;
passed as `None` or `float` to the encoder.

### D-3 — Output filename defaulting in `synth_wav.py`

Default output filename is derived from the MESSAGE text: lowercase, spaces→underscores,
non-alphanumeric characters stripped, truncated to 40 chars, `.wav` appended. This
produces a predictable, human-readable name (e.g. `cq_q1abc_fn42.wav`) without
requiring the user to supply `--out` for routine use.

### D-4 — `--from-scenario` drives the matcher list in `resume_study.py`

The full ordered scenario registry is `[S1, S1b, S2, S3, S4, S5, S7, S8]`.
`--from-scenario S2` means "S2 was the first scenario not yet played"; the remaining
scenarios to play are `[S2, S3, S4, S5, S7]` and the matcher runs for
`[S1, S2, S3, S4, S5, S7]` (S1 was already injected before the resume). The matcher
list is always `[S1] + played_scenarios` — all scenarios from S1 through the last
resumed one. S8 is excluded from default resume (it is pre-pended by `run_study.py`
when the user opts in); S8 can be included via `--from-scenario S8` if a full re-run
from S8 is needed.

## Risks / Trade-offs

- **[Risk] Silent default mismatch** — if a default value in `argparse` drifts from the
  hardcoded constant (e.g., someone changes `_SNR_DB` but forgets to update the default),
  the "no flags = same behaviour" guarantee breaks.
  → **Mitigation**: constants at the top of each file are removed once the `argparse`
  default is in place; there is one authoritative value, not two.

- **[Risk] `wavio.write_wav` float32 vs int16** — the existing function was used in
  `gen_decoder_fixtures.py` at 12 kHz int16; `synth_wav.py` targets 48 kHz float32
  for study use. Confirm `wavio.write_wav` handles both sample rates and dtypes cleanly.
  → **Mitigation**: read `wavio.py` before implementation; add `dtype` normalisation
  in `synth_wav.py` if needed (cast to float32 before write).
