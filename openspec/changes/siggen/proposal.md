## Why

The R&R synthesiser toolchain can only produce FT8-encoded audio; there is no way to
generate a raw sine wave, a swept tone, or shaped noise without hand-rolling numpy code
or editing Python source. This makes ad-hoc perceptual checks, interference scenario
construction, and decoder stress-testing unnecessarily cumbersome — and completely
inaccessible to an operator who should not need to understand the FT8 encode chain to
produce a 1 500 Hz test tone.

## What Changes

- **`qa/rr-study/siggen.py`** *(new file)* — standalone signal generator that reads a
  JSONL scene file and renders an arbitrary mix of signals (sine, square, sawtooth,
  triangle, chirp, noise, ft8) to a file and/or audio device simultaneously. No FT8
  encoder is loaded unless a signal of type `ft8` is present.
- **`docs/siggen-reference.md`** *(new file)* — full operator reference: JSONL format,
  all signal types and their parameters, examples, batch mode, and R&R scenario
  improvement recipes.
- **`docs/rr-synth-cli-guide.md`** *(extended)* — cross-reference section pointing to
  the new `siggen-reference.md`.
- No changes to `synth_wav.py`, `run_study.py`, `resume_study.py`,
  `gen_decoder_fixtures.py`, `harness/run_scenario.py`, or any file in the .NET
  solution.

## Capabilities

### New Capabilities

- `siggen`: General-purpose multi-signal audio scene renderer — JSONL scene file format,
  all primitive signal types, output routing (file / device / both), and batch mode for
  unattended multi-scene rendering.

### Modified Capabilities

*(none)*

## Impact

- **Affected files**: `qa/rr-study/siggen.py` (new), `docs/siggen-reference.md` (new),
  `docs/rr-synth-cli-guide.md` (extended).
- **No impact on**: .NET solution, build, tests, or any file outside `qa/rr-study/` and
  `docs/`.
- **New Python dependencies**: none. `numpy` and `scipy` are already present in the
  `qa/rr-study/.venv`; the `synth.*` package is present and optionally used. No new
  packages required.
- **R&R scenario improvements**: `siggen.py` enables several recommended improvements
  to the R&R study that are currently impractical without it (see design.md).
