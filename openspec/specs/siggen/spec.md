# siggen Specification

## Purpose
TBD - created by archiving change siggen. Update Purpose after archive.
## Requirements
### Requirement: siggen accepts a JSONL scene file and renders it to output sinks

`qa/rr-study/siggen.py` SHALL read a JSONL scene file in which each non-blank,
non-comment line is a JSON object. Lines beginning with `#` (after optional leading
whitespace) SHALL be silently skipped. Each JSON object SHALL have a `"type"` field
that identifies it as either a scene-configuration line (`"scene"`) or a signal
descriptor (any other recognised type). The script SHALL render all signal descriptors
into a single float64 sample buffer and route the result to all declared output sinks.

**CLI:**
```
python siggen.py SCENE_FILE [--out PATH] [--device NAME] [--rate HZ] [--duration S]
python siggen.py --batch BATCH_FILE [--out PATH] [--device NAME] [--rate HZ]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `SCENE_FILE` | path | *(required unless `--batch`)* | Path to JSONL scene file |
| `--out PATH` | str | *(from scene line or error)* | Output WAV file path — overrides scene `out` |
| `--device NAME` | str | *(from scene line or none)* | Audio device name substring — overrides scene `device` |
| `--rate HZ` | int | `48000` | Sample rate — overrides scene `sample_rate` |
| `--duration S` | float | *(auto)* | Total scene duration — overrides scene `duration_s` |
| `--batch FILE` | path | *(none)* | Batch mode: JSON array of scene objects |

At least one output sink (`out` file path or `device` name) MUST be resolvable from
either the scene file or CLI flags. If neither is present the script SHALL exit with a
descriptive error message and a non-zero exit code.

#### Scenario: Basic scene file renders to WAV
- **WHEN** `siggen.py scene.jsonl --out output.wav` is run with a valid JSONL file
- **THEN** a 16-bit mono PCM WAV file is written to `output.wav` containing the mixed
  signals described in the file, and the script prints a one-line completion summary

#### Scenario: Scene line `out` field used when --out not supplied
- **WHEN** the JSONL file contains `{"type":"scene","out":"my_scene.wav"}` and no
  `--out` flag is given
- **THEN** the WAV is written to `my_scene.wav`

#### Scenario: CLI --out overrides scene line out field
- **WHEN** the JSONL file contains `{"type":"scene","out":"scene.wav"}` and `--out
  override.wav` is given
- **THEN** the WAV is written to `override.wav`; `scene.wav` is not created

#### Scenario: No output sink specified exits with error
- **WHEN** neither `--out` nor `--device` is supplied and the scene file has no
  `"type":"scene"` line with an `out` or `device` field
- **THEN** the script exits with a non-zero code and prints an error naming the missing
  output sink requirement

#### Scenario: Comment lines are ignored
- **WHEN** the JSONL file contains lines beginning with `#`
- **THEN** those lines are skipped and do not cause parse errors

---

### Requirement: scene-configuration line declares output sinks and global parameters

The JSONL file SHALL support a scene-configuration line: a JSON object with `"type":"scene"`
that may appear anywhere in the file (conventionally the first line). If multiple
`"type":"scene"` lines are present the last one SHALL win.
The recognised fields are:

| Field | Type | Default | Description |
|---|---|---|---|
| `out` | str | *(none)* | Output WAV file path |
| `device` | str | *(none)* | Audio output device name substring (case-insensitive match) |
| `sample_rate` | int | `48000` | Sample rate in Hz |
| `duration_s` | float | *(auto)* | Total scene duration; auto = `max(start_s + signal_duration_s)` |
| `seed` | int | `0` | Global RNG seed for noise signals that do not specify their own |

#### Scenario: Scene line sets sample rate
- **WHEN** the scene line contains `"sample_rate": 12000`
- **THEN** all signals are rendered at 12 000 Hz and the output WAV has a 12 kHz frame rate

#### Scenario: Scene duration auto-computed from signals
- **WHEN** no `duration_s` is specified in the scene line or CLI and the scene contains
  a `sine` signal with `start_s: 5.0, duration_s: 3.0`
- **THEN** the output buffer is at least 8.0 seconds long (5.0 + 3.0)

#### Scenario: Last scene line wins on duplicate
- **WHEN** two `"type":"scene"` lines are present and the second specifies `"out":"b.wav"`
- **THEN** the WAV is written to `b.wav` regardless of what the first scene line said

---

### Requirement: siggen renders signal type `sine`

A JSON object with `"type":"sine"` SHALL render a continuous-phase sinusoidal tone
placed at `start_s` within the scene buffer.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_hz` | float | yes | — | Tone frequency in Hz |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS (0 dBFS = 1.0) |
| `start_s` | float | yes | — | Signal start time in seconds |
| `duration_s` | float | yes | — | Signal duration in seconds |
| `phase_deg` | float | no | `0.0` | Initial phase in degrees |

\* `amplitude` and `level_dbfs` are mutually exclusive. If neither is given, `amplitude`
defaults to `1.0`. If both are given the script SHALL exit with a parse error.

#### Scenario: Sine tone at default amplitude
- **WHEN** `{"type":"sine","freq_hz":1000,"amplitude":1.0,"start_s":0.0,"duration_s":1.0}`
- **THEN** the rendered buffer contains a 1 kHz sinusoid occupying the first second; the
  peak value before output normalisation is 1.0

#### Scenario: Sine amplitude expressed in dBFS
- **WHEN** `{"type":"sine","freq_hz":1000,"level_dbfs":-6,"start_s":0.0,"duration_s":1.0}`
- **THEN** the peak amplitude is `10^(-6/20)` ≈ 0.501

#### Scenario: Sine placed at non-zero start
- **WHEN** `start_s: 5.0` in a 15 s scene
- **THEN** samples 0–4.999 s are zero; the tone begins at sample `5.0 * sample_rate`

#### Scenario: Both amplitude and level_dbfs raises error
- **WHEN** a `sine` object specifies both `amplitude` and `level_dbfs`
- **THEN** the script exits with a non-zero code before rendering begins

---

### Requirement: siggen renders signal type `square`

A JSON object with `"type":"square"` SHALL render a square wave using additive synthesis
of odd harmonics up to the Nyquist limit, placed at `start_s`.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_hz` | float | yes | — | Fundamental frequency in Hz |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | yes | — | Signal start time in seconds |
| `duration_s` | float | yes | — | Signal duration in seconds |
| `duty_cycle` | float | no | `0.5` | Duty cycle (0.0–1.0 exclusive) |

\* Same mutual-exclusion rule as `sine`.

#### Scenario: Square wave with default duty cycle
- **WHEN** `{"type":"square","freq_hz":500,"amplitude":0.8,"start_s":0.0,"duration_s":1.0}`
- **THEN** the rendered buffer contains a 500 Hz square wave at peak amplitude 0.8

#### Scenario: Square wave with custom duty cycle
- **WHEN** `"duty_cycle": 0.25`
- **THEN** the high phase occupies 25% of each period

---

### Requirement: siggen renders signal type `sawtooth`

A JSON object with `"type":"sawtooth"` SHALL render a sawtooth wave using additive
synthesis of harmonics up to the Nyquist limit, placed at `start_s`.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_hz` | float | yes | — | Fundamental frequency in Hz |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | yes | — | Signal start time in seconds |
| `duration_s` | float | yes | — | Signal duration in seconds |

\* Same mutual-exclusion rule as `sine`.

#### Scenario: Sawtooth wave renders correctly
- **WHEN** `{"type":"sawtooth","freq_hz":440,"amplitude":0.5,"start_s":0.0,"duration_s":2.0}`
- **THEN** the rendered buffer contains a 440 Hz sawtooth at peak amplitude 0.5 for 2 s

---

### Requirement: siggen renders signal type `triangle`

A JSON object with `"type":"triangle"` SHALL render a triangle wave using additive
synthesis of odd harmonics with alternating signs, placed at `start_s`.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_hz` | float | yes | — | Fundamental frequency in Hz |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | yes | — | Signal start time in seconds |
| `duration_s` | float | yes | — | Signal duration in seconds |

\* Same mutual-exclusion rule as `sine`.

#### Scenario: Triangle wave renders correctly
- **WHEN** `{"type":"triangle","freq_hz":440,"amplitude":0.5,"start_s":0.0,"duration_s":2.0}`
- **THEN** the rendered buffer contains a 440 Hz triangle wave at peak amplitude 0.5

---

### Requirement: siggen renders signal type `chirp`

A JSON object with `"type":"chirp"` SHALL render a linear (or logarithmic)
frequency-swept sinusoid placed at `start_s`. The instantaneous frequency sweeps from
`freq_start_hz` to `freq_end_hz` over `duration_s` seconds.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_start_hz` | float | yes | — | Start frequency in Hz |
| `freq_end_hz` | float | yes | — | End frequency in Hz |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | yes | — | Signal start time in seconds |
| `duration_s` | float | yes | — | Sweep duration in seconds |
| `method` | str | no | `"linear"` | Sweep method: `"linear"` or `"logarithmic"` |

\* Same mutual-exclusion rule as `sine`. Implementation SHALL use `scipy.signal.chirp`.

#### Scenario: Linear chirp up-sweeps frequency
- **WHEN** `{"type":"chirp","freq_start_hz":500,"freq_end_hz":2000,"amplitude":0.5,"start_s":0.0,"duration_s":3.0}`
- **THEN** the instantaneous frequency at t=0 is 500 Hz and at t=3.0 s is 2000 Hz

#### Scenario: Logarithmic chirp
- **WHEN** `"method": "logarithmic"` is specified
- **THEN** the sweep follows a logarithmic (exponential) frequency progression

#### Scenario: Chirp placed mid-scene
- **WHEN** `"start_s": 5.0` in a scene with `duration_s: 15.0`
- **THEN** the chirp occupies samples from 5 s to `5 + duration_s` seconds; samples before
  5 s and after `5 + duration_s` s contain no contribution from this signal

---

### Requirement: siggen renders signal type `noise`

A JSON object with `"type":"noise"` SHALL render a burst of AWGN (white or bandlimited)
placed at `start_s` and lasting `duration_s`. The implementation SHALL reuse
`synth.channel._lowpass_fir` for bandlimiting when `cutoff_hz` is specified.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `amplitude` | float | no* | `1.0` | Noise RMS (sample std-dev); not peak |
| `level_dbfs` | float | no* | — | Noise RMS level in dBFS |
| `start_s` | float | yes | — | Burst start time in seconds |
| `duration_s` | float | yes | — | Burst duration in seconds |
| `cutoff_hz` | float | no | *(none — wideband)* | Lowpass cutoff for bandlimited noise (Kaiser FIR) |
| `seed` | int | no | *(from scene global `seed`)* | RNG seed for reproducibility |

\* `amplitude` and `level_dbfs` are mutually exclusive; same rule as `sine`. For `noise`,
`amplitude` is interpreted as the noise RMS (standard deviation), not peak, to maintain
consistency with `numpy.random.Generator.standard_normal` scaling.

#### Scenario: Wideband AWGN burst
- **WHEN** `{"type":"noise","amplitude":0.1,"start_s":0.0,"duration_s":5.0}`
- **THEN** the rendered buffer contains 5 s of AWGN with sample std-dev ≈ 0.1

#### Scenario: Bandlimited noise with cutoff
- **WHEN** `{"type":"noise","amplitude":0.1,"cutoff_hz":3000,"start_s":0.0,"duration_s":5.0}`
- **THEN** the noise PSD above 3600 Hz (1.2 × cutoff) is at least 30 dB below the
  passband mean, verified by `synth.channel.verify_noise_psd`

#### Scenario: Noise seed is reproducible
- **WHEN** two separate runs use the same scene file with the same `seed`
- **THEN** the output WAV files are bit-identical

#### Scenario: Noise burst placed mid-scene
- **WHEN** `"start_s": 3.0, "duration_s": 2.0` in a 15 s scene
- **THEN** samples outside 3–5 s contain no contribution from this noise signal

---

### Requirement: siggen renders signal type `ft8`

A JSON object with `"type":"ft8"` SHALL encode a valid FT8 message using `synth.encoder`
and place the resulting GFSK audio at `start_s` within the scene buffer. The `synth.encoder`
module SHALL be imported lazily — only when the first `ft8` line is encountered. A scene
with no `ft8` lines SHALL run without importing any FT8 encode chain module.

The FT8 signal occupies exactly `SLOT_LENGTH_S` seconds (15.0 s) starting at `start_s`.
The `duration_s` field is NOT used for `ft8` signals (and SHALL be rejected with an
error if supplied, to prevent confusion).

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `message` | str | yes | — | FT8 message text (e.g. `"CQ Q1ABC FN42"`) |
| `freq_hz` | float | yes | — | Base audio frequency (tone 0) in Hz |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude of the encoded signal |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | no | `0.0` | Start time within the scene buffer |
| `dt_s` | float | no | `0.0` | DT offset within the FT8 slot (passed to `modulator.modulate`) |

\* Same mutual-exclusion rule as `sine`.

#### Scenario: FT8 signal encodes and places correctly
- **WHEN** `{"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":0.5,"start_s":0.0}`
- **THEN** the rendered buffer contains a GFSK FT8 signal centred on 1500 Hz at peak
  amplitude 0.5, decodable by libft8 / WSJT-X

#### Scenario: FT8 without FT8 type does not import encoder
- **WHEN** a scene contains only `sine`, `chirp`, and `noise` signals
- **THEN** `synth.encoder` is never imported during the render

#### Scenario: Invalid FT8 message exits with error
- **WHEN** `"message"` contains text that `synth.encoder.encode_message` cannot pack
- **THEN** the script exits with a non-zero code and a descriptive error before any
  output is written

#### Scenario: duration_s in ft8 line is rejected
- **WHEN** a `ft8` signal descriptor includes a `duration_s` field
- **THEN** the script exits with a non-zero code naming the offending field

---

### Requirement: siggen mixes all signals into a single output buffer

All rendered signal arrays SHALL be element-wise summed into a single float64 buffer of
length `ceil(duration_s * sample_rate)`. Each signal contributes only to the samples
spanning `[start_s * sample_rate, (start_s + signal_duration_s) * sample_rate)`. Signals
that extend beyond the scene `duration_s` SHALL be truncated at the buffer boundary
without error.

#### Scenario: Two simultaneous signals are summed
- **WHEN** a scene contains a 1 kHz sine and a 2 kHz sine both at `start_s: 0.0`
- **THEN** the output buffer equals the element-wise sum of the two individual renders

#### Scenario: Non-overlapping signals occupy separate windows
- **WHEN** signal A has `start_s: 0.0, duration_s: 5.0` and signal B has `start_s: 7.0,
  duration_s: 5.0` in a 15 s scene
- **THEN** samples 5–7 s contain neither signal's contribution (zero from both)

#### Scenario: Signal extending past scene boundary is truncated
- **WHEN** a signal has `start_s: 13.0, duration_s: 5.0` in a 15 s scene
- **THEN** only 2 s of the signal is rendered; no buffer overrun occurs

---

### Requirement: siggen routes output to file and/or audio device

When a file path is declared (`out` field or `--out`), the mixed buffer SHALL be written
as a 16-bit mono PCM WAV via `wavio.write_wav()` (6 dB headroom normalisation).

When a device is declared (`device` field or `--device`), the mixed buffer SHALL be
normalised to 0.9 peak amplitude, cast to float32, and played via `sounddevice.play()`
(blocking). The device name is matched case-insensitively as a substring against
`sounddevice.query_devices()` output device names; if no match is found the script SHALL
print available output devices and exit with a non-zero code.

Both sinks MAY be active simultaneously. When both are declared, the WAV file is written
first, then playback begins.

#### Scenario: File-only output
- **WHEN** only `out` is specified and no `device`
- **THEN** a WAV file is written; no audio device is opened

#### Scenario: Device-only output
- **WHEN** only `device` is specified and no `out`
- **THEN** audio is played to the device; no WAV file is written

#### Scenario: Simultaneous file and device output
- **WHEN** both `out` and `device` are declared
- **THEN** the WAV file is written and audio playback occurs; both operations use the same
  rendered buffer

#### Scenario: Unknown device name exits with help
- **WHEN** the declared device name does not match any output device
- **THEN** the script exits with a non-zero code and lists all available output devices
  with their indices and names

---

### Requirement: siggen supports batch mode for unattended multi-scene rendering

When invoked with `--batch BATCH_FILE`, `siggen.py` SHALL read a JSON array from
`BATCH_FILE` where each element is a scene object. A scene object has a `signals` array
(list of signal descriptor objects, same schema as JSONL signal lines) and optionally
`out`, `device`, `sample_rate`, `duration_s`, `seed`. CLI flags (`--out`, `--device`,
`--rate`) are applied as overrides to every batch item. Batch items are processed
sequentially. A failure in one item (invalid signal, bad device, etc.) SHALL print an
error identifying the item index and continue processing the remaining items. The script
exits with a non-zero code if any item failed.

#### Scenario: Batch renders multiple WAV files
- **WHEN** `--batch jobs.json` is supplied with a 3-element array, each with distinct
  `out` paths
- **THEN** three WAV files are written sequentially without interruption; progress is
  printed for each item

#### Scenario: Batch item failure does not abort remaining items
- **WHEN** the second of three batch items contains an invalid signal descriptor
- **THEN** item 1 and item 3 complete successfully; item 2 prints an error; the script
  exits with a non-zero code after all items are processed

#### Scenario: CLI --out override applied to all batch items
- **WHEN** `--batch jobs.json --out /tmp/override.wav` is supplied
- **THEN** every batch item writes its WAV to `/tmp/override.wav`, overwriting each
  predecessor (last item's output survives)

---

### Requirement: siggen documentation in docs/siggen-reference.md

`docs/siggen-reference.md` SHALL be a complete operator reference covering:

1. **Overview** — what `siggen.py` does, where it lives, how to invoke it
2. **JSONL scene file format** — structure, comment syntax, `"type":"scene"` line fields
3. **Signal type reference** — one sub-section per signal type, all fields, defaults,
   examples
4. **Amplitude specification** — `amplitude` vs `level_dbfs`, mutual exclusion rule,
   default
5. **Output routing** — file sink, device sink, simultaneous use
6. **Batch mode** — batch file format, per-item error handling, CLI override behaviour
7. **Examples** — at minimum:
   - Single sine tone to WAV
   - Multi-signal mixed scene (sine + noise + ft8)
   - Chirp sweep to audio device
   - Batch file generating a sweep of SNR levels
   - Near-collision FT8 pair (R-003 recipe)
8. **R&R improvement recipes** — practical scene files for each recommended improvement
   (R-001 through R-004)

`docs/rr-synth-cli-guide.md` SHALL be updated with a cross-reference section pointing
to `docs/siggen-reference.md`.

#### Scenario: Documentation covers all signal types
- **WHEN** `docs/siggen-reference.md` is read
- **THEN** every signal type (`sine`, `square`, `sawtooth`, `triangle`, `chirp`,
  `noise`, `ft8`) has a dedicated sub-section with field table and at least one
  example JSON object

#### Scenario: Cross-reference added to existing guide
- **WHEN** `docs/rr-synth-cli-guide.md` is read
- **THEN** it contains a section or note directing operators to `docs/siggen-reference.md`
  for the general-purpose signal generator

