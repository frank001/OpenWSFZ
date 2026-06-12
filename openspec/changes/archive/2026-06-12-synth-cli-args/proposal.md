## Why

The R&R synthesiser scripts contain hardcoded constants and machine-specific paths that
force an operator to edit source in order to vary SNR, seed, output location, or resume
point — a fragile and error-prone workflow. A standalone one-shot WAV generator does not
exist at all, making ad-hoc perceptual checks (e.g. waterfall inspection, quick decoder
smoke-tests) needlessly cumbersome.

## What Changes

- **`qa/rr-study/gen_decoder_fixtures.py`** — four hardcoded render constants
  (`_SNR_DB`, `_SEED`, `_DT_S`, `_SAMPLE_RATE_HZ`) and the output directory are exposed
  as optional CLI flags; all defaults reproduce today's hardcoded behaviour exactly.
- **`qa/rr-study/resume_study.py`** — `--device` and `--from-scenario` flags replace the
  hardcoded device name and fixed scenario set; the matcher list is derived from the
  supplied resume point rather than being hard-wired to `S2–S5`.
- **`qa/rr-study/synth_wav.py`** *(new file)* — standalone one-shot WAV generator:
  encode any FT8 message to a WAV file with full control over frequency, SNR, time offset,
  seed, sample rate, and noise cutoff; no changes to existing scripts.

No existing command lines (`run_study.py`, `harness/run_scenario.py`) are touched.
No new Python dependencies are introduced.

## Capabilities

### New Capabilities

- `synth-cli`: Command-line interface for the R&R synthesiser tools — fixture generator
  flags, study-resume flags, and a new standalone WAV-synthesis entry point.

### Modified Capabilities

*(none — no spec-level requirement changes to existing capabilities)*

## Impact

- **Affected files**: `qa/rr-study/gen_decoder_fixtures.py`, `qa/rr-study/resume_study.py`,
  new file `qa/rr-study/synth_wav.py`.
- **No impact on**: .NET solution, build, tests, or any file outside `qa/rr-study/`.
- **No new dependencies**: uses only `argparse` (stdlib), `numpy`, `soundfile`/`wavio`,
  and the existing `synth.*` package already present in the venv.
