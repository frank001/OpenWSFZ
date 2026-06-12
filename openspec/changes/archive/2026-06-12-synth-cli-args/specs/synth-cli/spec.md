## ADDED Requirements

### Requirement: gen_decoder_fixtures accepts render-parameter flags
`gen_decoder_fixtures.py` SHALL accept the following optional CLI flags; when omitted
every flag SHALL default to the value that was previously hardcoded, so the script
produces bit-identical output when run with no arguments.

| Flag | Type | Default | Previously hardcoded |
|---|---|---|---|
| `--snr-db` | float | `15.0` | `_SNR_DB = 15.0` |
| `--seed` | int | `20260606` | `_SEED = 20260606` |
| `--dt` | float | `0.2` | `_DT_S = 0.2` |
| `--sample-rate` | int | `12000` | `_SAMPLE_RATE_HZ = 12_000` |
| `--output-dir` | path | `tests/OpenWSFZ.Ft8.Tests/Fixtures/` (relative to repo root) | `_FIXTURES_DIR` |

The original module-level constants SHALL be removed; `argparse` defaults are the single
source of truth.

#### Scenario: Run with no arguments produces same fixtures as before
- **WHEN** `gen_decoder_fixtures.py` is run with no CLI arguments
- **THEN** it writes the same WAV and `.expected.txt` files to
  `tests/OpenWSFZ.Ft8.Tests/Fixtures/` as the hardcoded version did

#### Scenario: Custom SNR produces a different WAV
- **WHEN** `gen_decoder_fixtures.py --snr-db 6.0` is run
- **THEN** the generated WAVs are at 6 dB SNR (verified by `synth.channel.measure_inband_snr_db`)

#### Scenario: Custom output-dir redirects output
- **WHEN** `gen_decoder_fixtures.py --output-dir /tmp/fixtures` is run
- **THEN** WAV and `.expected.txt` files are written to `/tmp/fixtures/` and
  the default Fixtures directory is untouched

---

### Requirement: resume_study accepts device and resume-point flags
`resume_study.py` SHALL accept `--device` and `--from-scenario` optional flags.

- `--device <substring>` — audio output device name substring; default `"CABLE Input"`.
- `--from-scenario <ID>` — the first scenario that has NOT yet been played (i.e. the
  resume point); default `"S2"`. Valid values: `S2 S3 S4 S5 S7 S8`.

The set of scenarios to *play* SHALL be all scenarios from `--from-scenario` to the
end of the controlled set `[S2, S3, S4, S5, S7]` (inclusive of `--from-scenario`).
S8 is excluded from this set; it is never replayed via `resume_study.py`.

The set of scenarios to *match* SHALL be `[S1]` plus all scenarios that will be played
(S1 was already injected before the resume).

The hardcoded `REMAINING_SCENARIOS` and `ALL_SCENARIO_IDS` lists SHALL be replaced by
logic derived from `--from-scenario`.

#### Scenario: Default resume from S2 matches existing hardcoded behaviour
- **WHEN** `resume_study.py` is run with no arguments
- **THEN** it plays S2–S7 and runs the matcher for S1–S7, identical to the old
  hardcoded behaviour

#### Scenario: Resume from S4 plays only S4 onwards
- **WHEN** `resume_study.py --from-scenario S4` is run
- **THEN** it plays S4, S5, S7 and runs the matcher for S1, S4, S5, S7

#### Scenario: Unknown scenario ID is rejected
- **WHEN** `resume_study.py --from-scenario XX` is run
- **THEN** argparse prints an error and exits with a non-zero code

---

### Requirement: synth_wav.py generates a WAV file from a single FT8 message
`qa/rr-study/synth_wav.py` SHALL be a new standalone script that encodes one FT8
message to a WAV file using the `synth.*` package.

**Positional argument:**
- `MESSAGE` — the FT8 message text to encode (e.g. `"CQ Q1ABC FN42"`).

**Optional flags:**

| Flag | Type | Default | Description |
|---|---|---|---|
| `--freq` | float | `1500.0` | Base audio frequency (Hz) |
| `--snr` | str | `"0.0"` | In-band SNR (dB), or `"none"` / `"clean"` for noise-free render |
| `--dt` | float | `0.0` | Time offset (s) applied to the signal start |
| `--seed` | int | `0` | RNG seed for the noise realisation |
| `--rate` | int | `48000` | Sample rate (Hz) |
| `--cutoff` | float | *(omitted)* | Noise lowpass cutoff (Hz); if omitted, noise is wideband |
| `--out` | path | *(auto)* | Output WAV path; default derived from MESSAGE text |

**Output filename default rule:** lowercase MESSAGE, spaces → underscores, strip
non-alphanumeric characters (keep underscores), truncate to 40 chars, append `.wav`.
Example: `"CQ Q1ABC FN42"` → `cq_q1abc_fn42.wav`.

The script SHALL write a float32 mono WAV file and print a one-line summary:
`Wrote <path> (<n> samples @ <rate> Hz, SNR=<value> dB)` or
`Wrote <path> (<n> samples @ <rate> Hz, clean)`.

#### Scenario: Basic encode with defaults
- **WHEN** `synth_wav.py "CQ Q1ABC FN42"` is run
- **THEN** a file `cq_q1abc_fn42.wav` is written to the current directory,
  containing a 48 kHz float32 mono WAV of approximately 12.64 s

#### Scenario: Clean (noise-free) render
- **WHEN** `synth_wav.py "CQ Q1ABC FN42" --snr none` is run
- **THEN** the output WAV contains only the FT8 signal with no additive noise,
  and the summary line contains the word `clean`

#### Scenario: Custom output path
- **WHEN** `synth_wav.py "CQ Q1ABC FN42" --out /tmp/test.wav` is run
- **THEN** the WAV file is written to `/tmp/test.wav`

#### Scenario: Noise cutoff is applied when --cutoff is supplied
- **WHEN** `synth_wav.py "CQ Q1ABC FN42" --snr -5 --cutoff 3000` is run
- **THEN** the noise in the output WAV is bandlimited to 3000 Hz
  (verified by `synth.channel.verify_noise_psd`)

#### Scenario: Invalid message text exits with error
- **WHEN** `synth_wav.py "NOTAVALIDFT8MESSAGE_TOOLONG_EXCEEDSCHARACTERLIMIT"` is run
- **THEN** the script exits with a non-zero code and prints a descriptive error
