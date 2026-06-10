# siggen — Operator Reference

`siggen.py` is a general-purpose multi-signal audio scene renderer.  It reads a
plain-text scene file, mixes an arbitrary number of signals together, and routes the
result to a WAV file, a live audio output device, or both simultaneously.

Signal types supported: **sine, square, sawtooth, triangle, chirp, noise, ft8**.

---

## Table of contents

1. [Quick start](#1-quick-start)
2. [Scene file format](#2-scene-file-format)
3. [Scene configuration](#3-scene-configuration)
4. [Amplitude specification](#4-amplitude-specification)
5. [Signal types](#5-signal-types)
   - 5.1 [sine](#51-sine)
   - 5.2 [square](#52-square)
   - 5.3 [sawtooth](#53-sawtooth)
   - 5.4 [triangle](#54-triangle)
   - 5.5 [chirp](#55-chirp)
   - 5.6 [noise](#56-noise)
   - 5.7 [ft8](#57-ft8)
6. [CLI reference](#6-cli-reference)
7. [Batch mode](#7-batch-mode)
8. [Output sinks](#8-output-sinks)
9. [Python API](#9-python-api)
10. [Worked examples](#10-worked-examples)
11. [Extension points for music use](#11-extension-points-for-music-use)
12. [Architecture notes](#12-architecture-notes)

---

## 1. Quick start

```bash
# From the repo root — play a scene live through an audio device:
python qa/rr-study/siggen.py my_scene.jsonl --device "Voicemeeter Input"

# Write to a WAV file:
python qa/rr-study/siggen.py my_scene.jsonl --out output.wav

# Both simultaneously:
python qa/rr-study/siggen.py my_scene.jsonl --out output.wav --device "Voicemeeter Input"

# From qa/rr-study/ (the working directory for most study commands):
python siggen.py my_scene.jsonl --device "CABLE Input"
```

---

## 2. Scene file format

A **scene file** is a UTF-8 text file where every non-blank, non-comment line is a
valid JSON object terminated by a newline (JSONL — JSON Lines format).

| Line type | Rule |
|---|---|
| Blank line | Ignored |
| Line starting with `#` | Ignored (comment) |
| `{"type":"scene", ...}` | Scene configuration; merged into the scene config (last-wins for duplicate keys) |
| Any other JSON object | Signal descriptor; rendered in the order it appears |

**Minimal working scene file:**

```jsonl
# My first scene
{"type":"scene","out":"hello.wav"}
{"type":"sine","freq_hz":440,"amplitude":0.5,"start_s":0.0,"duration_s":2.0}
```

**Rules:**
- There may be zero, one, or more `"type":"scene"` lines; they are all merged.
- Signal descriptors are rendered and summed in file order.
- The output sink (`out` and/or `device`) must be declared either in a scene line or
  via a CLI flag — the renderer will exit with an error if neither is present.

---

## 3. Scene configuration

The scene config is built from all `"type":"scene"` lines in the file, then
overridden by any CLI flags that are explicitly provided.

| Field | Type | Default | Description |
|---|---|---|---|
| `sample_rate` | int (Hz) | `48000` | PCM sample rate for the entire scene. Applied to all signals. |
| `duration_s` | float (s) | auto | Total scene length. When absent, computed as the latest `start_s + duration_s` (or `start_s + 15 s` for `ft8`) across all signal descriptors. Required when `loop` is enabled. |
| `seed` | int | `0` | Base seed used for noise seed derivation (see §5.6). Does not affect non-noise signals. |
| `out` | string | — | Output WAV file path. Parent directories are created automatically. |
| `device` | string | — | Audio output device name substring (case-insensitive match). |
| `loop` | bool | `false` | When `true`, tile the signal list to fill `duration_s` (see §3.1). |
| `loop_period_s` | float (s) | auto | Repeat boundary in seconds. When absent, auto-derived as the latest signal end time. See §3.1 for beat-perfect looping. |

**Example:**

```jsonl
{"type":"scene","sample_rate":44100,"seed":12345,"out":"render.wav","duration_s":30.0}
```

### 3.1 Loop mode

When `"loop": true` is set, the renderer tiles the signal list to fill `duration_s`
without silence gaps.  Think of it as copy-pasting the bar pattern as many times as
needed to reach the end of the scene.

**How the period is determined:**

| Scenario | Period used |
|---|---|
| `loop_period_s` set explicitly | That value — exact musical boundary |
| `loop_period_s` absent | Auto-derived: latest `start_s + duration_s` across all signals |

**Important — beat-perfect loops:**  
The auto-derived period ends at the last *note event*, which is often earlier than
the musical bar boundary.  For example, a six-bar drum pattern at 80 BPM has bar
boundaries every 3.0 s (bar 6 ends at 18.0 s), but the last hi-hat event might end
at 17.645 s — the auto period would start bar 7 at 17.645 s instead of 18.0 s,
creating a 355 ms timing glitch.  Always set `loop_period_s` to the bar/phrase
length when precise tempo alignment matters.

**Noise in looped scenes:**  
Each copy of a `noise` signal receives an independent seed (derived from its position
in the expanded list), so the noise does not repeat audibly across loop iterations.
To force identical noise every time, set an explicit `seed` field on the descriptor.

**Requirements:**
- `duration_s` must be set (in the scene line or via `--duration`).
- All signals must have `start_s` defined (implied zero is fine).

```jsonl
# Six-bar backing loop — play for 5 minutes without writing out 300 s of events
{"type":"scene","sample_rate":48000,"duration_s":300.0,"loop":true,"loop_period_s":18.0,"out":"backing_loop.wav"}
{"type":"sawtooth","freq_hz":65.41,"amplitude":0.18,"start_s":0.00,"duration_s":0.35}
# … (remaining 6-bar content) …
```

---

## 4. Amplitude specification

Every signal descriptor may include exactly **one** of the following amplitude fields.
They are mutually exclusive — supplying both is an error.

| Field | Type | Interpretation |
|---|---|---|
| `amplitude` | float | Linear peak amplitude. `1.0` = full scale. |
| `level_dbfs` | float (dB) | Level relative to full scale. `0 dBFS = 1.0` linear; `-6 dBFS ≈ 0.501`. |
| *(neither)* | — | Defaults to `amplitude: 1.0`. |

> **Note for `noise` signals:** amplitude is treated as the sample **standard
> deviation (RMS)**, not a peak value, consistent with Gaussian noise statistics.
> See §5.6.

**Conversion:** `amplitude = 10 ** (level_dbfs / 20)`

**Practical levels:**

| `level_dbfs` | `amplitude` | Typical use |
|---|---|---|
| 0 | 1.000 | Full scale (clips if summed) |
| −6 | 0.501 | Single loud signal |
| −12 | 0.251 | Moderate |
| −20 | 0.100 | Background / weak signal |
| −40 | 0.010 | Very faint |

For scenes with multiple simultaneous signals, keep individual amplitudes modest
(e.g. `−12 dBFS` per signal) so their sum does not clip before normalisation.
The output normaliser (§8) handles peak limiting, but maintaining headroom in the
scene itself gives cleaner level relationships between signals.

---

## 5. Signal types

### 5.1 `sine`

A continuous-phase sinusoid.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `freq_hz` | float | ✓ | — | Frequency in Hz |
| `start_s` | float | ✓ | — | Start time in the scene (seconds) |
| `duration_s` | float | ✓ | — | Duration (seconds) |
| `amplitude` / `level_dbfs` | float | — | `1.0` | See §4 |
| `phase_deg` | float | — | `0.0` | Initial phase in degrees |

```jsonl
{"type":"sine","freq_hz":440.0,"amplitude":0.5,"start_s":0.0,"duration_s":4.0}
{"type":"sine","freq_hz":554.37,"amplitude":0.5,"start_s":0.0,"duration_s":4.0,"phase_deg":90}
```

**Music notes:** Sine waves produce pure fundamentals with no harmonics — useful for
tuning references and simple test tones.  They sound thin in musical context; for
richer tones use `sawtooth` (§5.3) or `square` (§5.2).

---

### 5.2 `square`

A square wave via `scipy.signal.square`.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `freq_hz` | float | ✓ | — | Frequency in Hz |
| `start_s` | float | ✓ | — | Start time (seconds) |
| `duration_s` | float | ✓ | — | Duration (seconds) |
| `amplitude` / `level_dbfs` | float | — | `1.0` | See §4 |
| `duty_cycle` | float | — | `0.5` | On-fraction (0.0–1.0 exclusive). `0.5` = symmetric square wave. |

```jsonl
# 4/4 metronome at 120 BPM — click on beat 1 (accent), beats 2–4 softer
{"type":"square","freq_hz":1000.0,"amplitude":0.3,"start_s":0.0,"duration_s":0.05}
{"type":"square","freq_hz":800.0,"amplitude":0.15,"start_s":0.5,"duration_s":0.05}
{"type":"square","freq_hz":800.0,"amplitude":0.15,"start_s":1.0,"duration_s":0.05}
{"type":"square","freq_hz":800.0,"amplitude":0.15,"start_s":1.5,"duration_s":0.05}
```

**Character:** Square waves contain odd harmonics (3rd, 5th, 7th…) with 1/n
roll-off — reminiscent of clarinet or chiptune.  A `duty_cycle` other than 0.5
introduces even harmonics, altering the timbre toward a pulse wave (nasal, hollow).

**Metronome pattern:** Beat duration = 60 / BPM seconds.  At 120 BPM each beat
is 0.5 s; at 100 BPM it is 0.6 s.  Short click duration (20–60 ms) keeps the
transient percussive feel.

---

### 5.3 `sawtooth`

A sawtooth wave (ramp up, instant reset) via `scipy.signal.sawtooth(width=1)`.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `freq_hz` | float | ✓ | — | |
| `start_s` | float | ✓ | — | |
| `duration_s` | float | ✓ | — | |
| `amplitude` / `level_dbfs` | float | — | `1.0` | |

```jsonl
{"type":"sawtooth","freq_hz":110.0,"amplitude":0.2,"start_s":0.0,"duration_s":8.0}
```

**Character:** Sawtooth waves contain all harmonics (1st, 2nd, 3rd…) with 1/n
roll-off — the richest harmonic content of the basic waveforms.  Analogous to a
bowed string, brass, or analogue synth pad.  Apply a low-pass `noise` cutoff in a
parallel channel to soften the brightness if needed.

---

### 5.4 `triangle`

A triangle wave via `scipy.signal.sawtooth(width=0.5)`.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `freq_hz` | float | ✓ | — | |
| `start_s` | float | ✓ | — | |
| `duration_s` | float | ✓ | — | |
| `amplitude` / `level_dbfs` | float | — | `1.0` | |

```jsonl
{"type":"triangle","freq_hz":261.63,"amplitude":0.4,"start_s":2.0,"duration_s":3.0}
```

**Character:** Odd harmonics only (like square), but with 1/n² roll-off — much
softer than square.  Hollow and flute-like at high frequencies; warm and muted at
low frequencies.

---

### 5.5 `chirp`

A sinusoidal frequency sweep (linear or logarithmic) via `scipy.signal.chirp`.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `freq_start_hz` | float | ✓ | — | Starting frequency |
| `freq_end_hz` | float | ✓ | — | Ending frequency |
| `start_s` | float | ✓ | — | |
| `duration_s` | float | ✓ | — | |
| `amplitude` / `level_dbfs` | float | — | `1.0` | |
| `method` | string | — | `"linear"` | `"linear"` or `"logarithmic"` |

```jsonl
# Rising glide from E2 to E4 over 2 seconds (logarithmic sweep = equal-temperament feel)
{"type":"chirp","freq_start_hz":82.41,"freq_end_hz":329.63,"start_s":0.0,"duration_s":2.0,"amplitude":0.4,"method":"logarithmic"}
```

**`"linear"` vs `"logarithmic"`:**
- `linear` — frequency changes at a constant Hz/s rate.  The high end of the sweep
  sounds faster than the low end to human ears.
- `logarithmic` — frequency changes at a constant octaves/s rate.  Each equal
  time interval spans the same number of semitones — perceptually uniform.
  **Use `"logarithmic"` for musical portamento effects.**

---

### 5.6 `noise`

Additive white Gaussian noise (AWGN), optionally bandlimited by a Kaiser FIR
lowpass filter.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `start_s` | float | ✓ | — | |
| `duration_s` | float | ✓ | — | |
| `amplitude` / `level_dbfs` | float | — | `1.0` | Treated as sample **std-dev (RMS)**, not peak |
| `cutoff_hz` | float | — | none | Kaiser FIR lowpass cutoff (Hz). When absent, noise is full-band (0 – fs/2). |
| `seed` | int | — | derived | Explicit seed overrides the auto-derived per-signal seed (see below). |

```jsonl
# Wideband hiss bed
{"type":"noise","amplitude":0.05,"start_s":0.0,"duration_s":30.0}

# Bandlimited ambient noise (simulates an SSB receiver, ~3 kHz bandwidth)
{"type":"noise","amplitude":0.08,"start_s":0.0,"duration_s":30.0,"cutoff_hz":3000}
```

**Amplitude semantics:** For noise, `amplitude` and `level_dbfs` control the sample
standard deviation (σ), not the peak.  A Gaussian signal with σ = 0.1 will have
occasional peaks of ±0.3–0.4; a σ = 0.3 will reach ±0.9 and may clip when summed
with other signals.  The output normaliser (§8) prevents hard clipping, but keep
noise σ well below 0.1 in mixed scenes.

**Seed derivation:** When `seed` is omitted, each noise descriptor receives a unique
deterministic seed derived from `scene_seed XOR Knuth_hash(signal_index)`.  This
ensures that two `noise` lines which both omit `seed` produce statistically
independent noise (not the same sequence).  The scene `seed` field (§3) is the
starting point; changing it regenerates all noise in the scene deterministically.

**`cutoff_hz` — bandlimiting:**  
The Kaiser FIR filter (numtaps = 255, β = 6.0) provides approximately 60 dB of
stopband attenuation and a ~720 Hz transition band at 48 kHz.  The passband is flat
to ±1 dB from 100 Hz to 85% of the cutoff frequency.  After filtering, the noise
RMS is renormalised to the requested `amplitude`, so the delivered level is accurate
regardless of how much energy the filter removes.

> **Important for R&R study use:** the `cutoff_hz` parameter of `siggen.py`'s noise
> type renormalises to target RMS, preserving perceived loudness.  This is different
> from the R&R harness (`channel.add_noise`), which preserves in-band SNR relative to
> a 2500 Hz reference.  The two are calibrated differently and are not interchangeable
> for SNR-precise measurements.

---

### 5.7 `ft8`

A synthesised FT8 transmission using the clean-room encoder (`synth/encoder.py`).
The encoder is independent of `libft8.dll` and implements only the transmit path
(text → tones → GFSK audio).

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `message` | string | ✓ | — | FT8 message text, e.g. `"CQ Q1ABC FN42"` |
| `freq_hz` | float | ✓ | — | Audio frequency of tone 0 (the lowest tone). Tone *k* sits at `freq_hz + k × 6.25 Hz`. |
| `start_s` | float | — | `0.0` | Slot start position in the scene (seconds) |
| `dt_s` | float | — | `0.0` | Timing offset within the FT8 slot (seconds). Simulates a late-starting transmitter. |
| `amplitude` / `level_dbfs` | float | — | `1.0` | |
| `duration_s` | — | **forbidden** | — | FT8 slots are always 15.0 s. Providing this field is an error. |

```jsonl
# FT8 signal at 1500 Hz, decoded by WSJT-X or OpenWSFZ
{"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":0.3,"start_s":0.0}

# Two co-channel stations, slightly time-offset
{"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":0.3,"start_s":0.0}
{"type":"ft8","message":"CQ Q4XYZ EM72","freq_hz":1800,"amplitude":0.2,"start_s":0.0,"dt_s":0.3}
{"type":"noise","amplitude":0.02,"start_s":0.0,"duration_s":15.0}
```

**Supported message formats:** Standard Type-1 messages only (`"CQ <callsign> <grid>"`,
`"<callsign1> <callsign2> <report>"`, `"<callsign1> <callsign2> RRR"`, etc.).
Non-standard callsigns, `/P` suffix, hashed calls, free-text, telemetry, and
EU-VHF format are not supported and will raise an error.

**GDPR note (NFR-021):** All messages in committed scene files must use
ITU-unallocated Q-prefix callsigns (`Q1ABC`, `Q4XYZ`, etc.).  Real callsigns
identify natural persons and must not appear in version control.

**Modulation:** GFSK (Gaussian Frequency Shift Keying) with BT = 2.0, matching
the FT8 specification.  A 10 ms raised-cosine fade-in and fade-out is applied to
eliminate click artefacts at transmission start and stop — identical to the ramp
used by real FT8 transmitters.

---

## 6. CLI reference

```
python siggen.py SCENE_FILE [options]
python siggen.py --batch BATCH_FILE [options]
```

| Argument | Description |
|---|---|
| `SCENE_FILE` | Path to a JSONL scene file (mutually exclusive with `--batch`) |
| `--out PATH` | Output WAV file path (overrides scene `out` field) |
| `--device NAME` | Audio output device name substring, case-insensitive (overrides scene `device` field) |
| `--rate HZ` | Sample rate in Hz (overrides scene `sample_rate`; default 48000) |
| `--duration S` | Total scene duration in seconds (overrides scene `duration_s`) |
| `--loop` | Tile signals to fill the scene duration (overrides scene `loop`; requires `duration_s`) |
| `--loop-period S` | Loop repeat boundary in seconds (overrides scene `loop_period_s`; see §3.1) |
| `--batch FILE` | Batch mode: process a JSON array of scene objects (mutually exclusive with `SCENE_FILE`) |

**CLI flags always take precedence** over scene-line values.  This is intentional:
the same scene file can be rendered at different sample rates or to different
devices without editing the file.

**Listing available audio devices:**  
If the `--device` substring matches nothing, `siggen.py` exits with an error message
that lists all available output devices with their indices and names.  Use this to
discover the correct substring for your system:

```bash
python siggen.py my_scene.jsonl --device "intentional_no_match"
# Outputs: available output devices: [0] ..., [1] ..., etc.
```

---

## 7. Batch mode

Batch mode processes a JSON array of scene objects sequentially.  Useful for
rendering multiple scenes in one command (e.g. a sequence of backing track sections).

**Batch file format:** a JSON array where each element is a scene object containing
a `"signals"` list and any scene configuration fields.

```json
[
  {
    "out": "section_A.wav",
    "duration_s": 16.0,
    "signals": [
      {"type":"sine","freq_hz":220.0,"amplitude":0.4,"start_s":0.0,"duration_s":16.0},
      {"type":"noise","amplitude":0.02,"start_s":0.0,"duration_s":16.0}
    ]
  },
  {
    "out": "section_B.wav",
    "duration_s": 16.0,
    "signals": [
      {"type":"sawtooth","freq_hz":440.0,"amplitude":0.3,"start_s":0.0,"duration_s":16.0},
      {"type":"noise","amplitude":0.02,"start_s":0.0,"duration_s":16.0}
    ]
  }
]
```

```bash
python siggen.py --batch my_batch.json
# CLI --device or --out override applies to ALL items in the batch
python siggen.py --batch my_batch.json --device "Voicemeeter Input"
```

**Error handling:** a failure in one batch item is printed and processing continues
with the next item.  The exit code is 0 if all items succeeded, 1 if any item
failed.

---

## 8. Output sinks

### WAV file output

Uses `synth/wavio.py` — stdlib `wave`, no third-party dependencies.

- **Format:** 16-bit mono PCM, little-endian (standard `.wav` format).
- **Normalisation:** the buffer is peak-normalised with 6 dB of headroom before
  writing.  The final peak is therefore at −6 dBFS.  This prevents clipping while
  leaving some headroom.
- Parent directories are created automatically.

### Audio device output

Uses `sounddevice` (must be installed: `pip install sounddevice`).

- **Normalisation:** the buffer is normalised to 0.9 peak amplitude (≈ −0.9 dBFS)
  before playback.  This avoids PortAudio hard-clipping artefacts that would occur
  if samples exceeded ±1.0.
- **Format sent to device:** float32 (PortAudio native floating-point path).
- **Blocking:** playback blocks until the audio is complete.
- **Device selection:** the first device whose name contains the supplied substring
  (case-insensitive) and has at least one output channel is used.

### Simultaneous file + device

Both sinks can be active at the same time.  The WAV file is written first, then
device playback begins.  The two operations use the same underlying float64 buffer,
so the WAV file and the device receive identical audio.

---

## 9. Python API

The synthesiser layers can be used directly from Python without going through
`siggen.py`.

### `synth.encoder` — end-to-end FT8 encode

```python
from synth.encoder import encode_message, message_to_tones, render_tones
from synth.constants import DEFAULT_SAMPLE_RATE_HZ

# Full pipeline: text → 15 s PCM slot (clean, no noise)
samples = encode_message("CQ Q1ABC FN42", base_freq_hz=1500.0)

# With AWGN at −6 dB SNR (2500 Hz reference bandwidth), seeded
samples = encode_message(
    "CQ Q1ABC FN42",
    base_freq_hz=1500.0,
    snr_db=-6.0,
    seed=42,
)

# Split pipeline: get the 79-tone vector first, then modulate
tones = message_to_tones("CQ Q1ABC FN42")   # list of 79 ints in [0,7]
samples = render_tones(tones, base_freq_hz=1500.0)
```

### `synth.modulator` — GFSK tone rendering

```python
from synth.modulator import modulate

# Render a known tone vector (e.g. all-zeros — continuous tone at base_freq_hz)
samples = modulate([0]*79, base_freq_hz=1000.0, dt_s=0.2)
```

### `synth.channel` — noise and mixing

```python
from synth.channel import add_noise, add_awgn, mix_to_shared_floor, measure_inband_snr_db

# Add AWGN to a signal at a target in-band SNR
noisy = add_noise(clean_signal, snr_db=-3.0, seed=7)

# Add bandlimited AWGN (Kaiser FIR, 3 kHz cutoff)
noisy = add_noise(clean_signal, snr_db=-3.0, seed=7, noise_cutoff_hz=3000.0)

# Mix multiple clean signals over a single shared noise floor
# (correct multi-station model — one noise floor, not N stacked floors)
mixed = mix_to_shared_floor(
    [signal_a, signal_b],
    snr_db_list=[0.0, -10.0],   # station A at 0 dB, station B 10 dB weaker
    seed=99,
    noise_cutoff_hz=4700.0,
)

# Verify realised SNR after adding noise
realised_db = measure_inband_snr_db(clean_signal, noisy)
```

### `synth.wavio` — WAV I/O

```python
from synth.wavio import write_wav, read_wav

write_wav("output.wav", samples, headroom_db=6.0)
samples, fs = read_wav("output.wav")
```

---

## 10. Worked examples

### 10.1 Tuning reference — 440 Hz sine to WAV

```jsonl
{"type":"scene","out":"a440.wav","sample_rate":48000}
{"type":"sine","freq_hz":440.0,"amplitude":0.5,"start_s":0.0,"duration_s":5.0}
```

```bash
python siggen.py a440.wav_scene.jsonl
```

---

### 10.2 A major chord — sine and sawtooth comparison

This is the existing `tests/siggen/a_chord.jsonl` test fixture.  Bars 1–5 use pure
sines; bars 5–10 switch to sawtooth to illustrate the harmonic difference.

```jsonl
{"type":"scene","sample_rate":48000}
# A major: A2 E3 A3 C#4 E4 A4
{"type":"sine","freq_hz":110.00,"amplitude":0.15,"start_s":0.0,"duration_s":5.0}
{"type":"sine","freq_hz":164.81,"amplitude":0.15,"start_s":0.0,"duration_s":5.0}
{"type":"sine","freq_hz":220.00,"amplitude":0.15,"start_s":0.0,"duration_s":5.0}
{"type":"sine","freq_hz":277.18,"amplitude":0.15,"start_s":0.0,"duration_s":5.0}
{"type":"sine","freq_hz":329.63,"amplitude":0.15,"start_s":0.0,"duration_s":5.0}
{"type":"sine","freq_hz":440.00,"amplitude":0.15,"start_s":0.0,"duration_s":5.0}
# Same chord — sawtooth (richer harmonics)
{"type":"sawtooth","freq_hz":110.00,"amplitude":0.15,"start_s":5.0,"duration_s":5.0}
{"type":"sawtooth","freq_hz":164.81,"amplitude":0.15,"start_s":5.0,"duration_s":5.0}
{"type":"sawtooth","freq_hz":220.00,"amplitude":0.15,"start_s":5.0,"duration_s":5.0}
{"type":"sawtooth","freq_hz":277.18,"amplitude":0.15,"start_s":5.0,"duration_s":5.0}
{"type":"sawtooth","freq_hz":329.63,"amplitude":0.15,"start_s":5.0,"duration_s":5.0}
{"type":"sawtooth","freq_hz":440.00,"amplitude":0.15,"start_s":5.0,"duration_s":5.0}
```

---

### 10.3 Metronome at 100 BPM (4/4 time)

Beat duration at 100 BPM = 0.60 s.  Bar duration = 2.40 s.

```jsonl
{"type":"scene","out":"metronome_100bpm.wav","duration_s":9.6}
# Beat 1 (accent) — higher pitch, louder
{"type":"square","freq_hz":1000.0,"amplitude":0.4,"start_s":0.00,"duration_s":0.04}
{"type":"square","freq_hz":1000.0,"amplitude":0.4,"start_s":2.40,"duration_s":0.04}
{"type":"square","freq_hz":1000.0,"amplitude":0.4,"start_s":4.80,"duration_s":0.04}
{"type":"square","freq_hz":1000.0,"amplitude":0.4,"start_s":7.20,"duration_s":0.04}
# Beats 2–4 — lower pitch, softer
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":0.60,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":1.20,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":1.80,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":3.00,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":3.60,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":4.20,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":5.40,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":6.00,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":6.60,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":7.80,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":8.40,"duration_s":0.03}
{"type":"square","freq_hz":700.0,"amplitude":0.2,"start_s":9.00,"duration_s":0.03}
```

---

### 10.4 Guitar backing — open E drone with ambient noise

A sustained open-E chord (E2 + harmonics) with a low bandlimited noise bed —
a passable ambient backing track for guitar practice.

```jsonl
{"type":"scene","out":"e_drone_backing.wav","duration_s":60.0,"seed":42}
# E2 fundamental and harmonics (82.41 Hz × 1,2,3,4,5)
{"type":"sawtooth","freq_hz":82.41,"amplitude":0.18,"start_s":0.0,"duration_s":60.0}
{"type":"sawtooth","freq_hz":164.81,"amplitude":0.12,"start_s":0.0,"duration_s":60.0}
{"type":"sawtooth","freq_hz":247.22,"amplitude":0.08,"start_s":0.0,"duration_s":60.0}
{"type":"sawtooth","freq_hz":329.63,"amplitude":0.05,"start_s":0.0,"duration_s":60.0}
{"type":"sawtooth","freq_hz":412.03,"amplitude":0.03,"start_s":0.0,"duration_s":60.0}
# Bandlimited ambient noise — warm hiss below 3 kHz
{"type":"noise","amplitude":0.02,"start_s":0.0,"duration_s":60.0,"cutoff_hz":3000}
```

---

### 10.5 Looping a backing track pattern (C–G–D–A–E–E at 80 BPM)

A six-bar progression at 80 BPM.  Each bar is 3.0 s; the full pattern is 18.0 s.
Only bars 1–6 need to be written out; `"loop": true` with `"loop_period_s": 18.0`
tiles them to fill the full 300-second scene.

```jsonl
# 80 BPM C-G-D-A-E-E backing track — 5-minute loop from a single 18-second pattern
{"type":"scene","sample_rate":48000,"duration_s":300.0,"loop":true,"loop_period_s":18.0,"out":"bass_drums_80bpm.wav"}

# Bar 1 - C (C2 = 65.41 Hz)
{"type":"sawtooth","freq_hz":65.41,"amplitude":0.18,"start_s":0.00,"duration_s":0.35}
{"type":"sawtooth","freq_hz":65.41,"amplitude":0.18,"start_s":0.75,"duration_s":0.35}
{"type":"sawtooth","freq_hz":65.41,"amplitude":0.18,"start_s":1.50,"duration_s":0.35}
{"type":"sawtooth","freq_hz":65.41,"amplitude":0.18,"start_s":2.25,"duration_s":0.35}
# … (remaining bar 1 events) …
# Bar 6 - E (last bar — ends at 18.0 s boundary)
{"type":"sawtooth","freq_hz":82.41,"amplitude":0.18,"start_s":15.00,"duration_s":0.35}
{"type":"sawtooth","freq_hz":82.41,"amplitude":0.18,"start_s":15.75,"duration_s":0.35}
{"type":"sawtooth","freq_hz":82.41,"amplitude":0.18,"start_s":16.50,"duration_s":0.35}
{"type":"sawtooth","freq_hz":82.41,"amplitude":0.18,"start_s":17.25,"duration_s":0.35}
```

Or equivalently from the CLI without modifying the scene file:

```bash
# The original scene file stays unchanged; loop is applied at render time
python siggen.py backing_pattern.jsonl --loop --loop-period 18.0 --duration 300 --out loop_300s.wav
```

**Why `loop_period_s` matters here:**  
The last note event in bar 6 ends at `17.625 + 0.02 = 17.645 s`.  Without
`loop_period_s`, the auto-derived period would be 17.645 s — bar 7 would start
355 ms early, making the loop feel rushed.  Setting `loop_period_s: 18.0` snaps
every repeat to the exact down-beat.

---

### 10.6 FT8 signal in noise — for decoder testing

```jsonl
{"type":"scene","out":"ft8_minus6db.wav","seed":100}
{"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":0.3,"start_s":0.0}
{"type":"noise","amplitude":0.05,"start_s":0.0,"duration_s":15.0,"cutoff_hz":3000}
```

> **Note:** For SNR-calibrated FT8 signals (where the dB value must match what
> WSJT-X or OpenWSFZ reports), use `synth.channel.add_noise()` directly via the
> Python API (§9) rather than the siggen noise type.  The R&R harness
> (`harness/run_scenario.py`) uses `add_noise` for all SNR-precise rendering.

---

## 11. Extension points for music use

The synthesiser is architecturally clean and well-suited for a music-production
fork.  The following capabilities are present today and immediately usable:

| What you have now | Music utility |
|---|---|
| `sine`, `square`, `sawtooth`, `triangle` | Four classic oscillator waveshapes |
| Multiple signals summed | Chords, counterpoint, layering |
| `start_s` / `duration_s` | Note scheduling on a timeline |
| `amplitude` / `level_dbfs` | Per-note dynamics |
| `noise` with `cutoff_hz` | Ambient beds, textured pads, white-noise percussion approximations |
| `chirp` (logarithmic) | Portamento / glide effects |
| Batch mode | Render multiple bars or sections in sequence |
| WAV output | Import into any DAW for further processing |

The following features are **not** present and would be the natural first additions
in a music fork:

| Feature | Notes |
|---|---|
| **Tempo grid** | Express `start_s` as beat/bar positions given a BPM; eliminates manual conversion. E.g. `"start_beat": 2, "bpm": 120`. |
| **ADSR envelope** | Per-signal attack/decay/sustain/release ramp, applied to the amplitude over time.  Without this, notes have instant-on / instant-off behaviour (click-suppressed by the modulator's 10 ms Hann fade, but no musical shape). |
| **Note names** | Express `freq_hz` as MIDI note numbers or note names (`"A4"`, `"E2"`) rather than raw Hz.  Conversion: `freq = 440 × 2 ** ((midi - 69) / 12)`. |
| **Stereo** | Panning field (`pan: -1.0` to `1.0`) and stereo WAV output.  Currently mono only. |
| **Repeat / loop** | ✅ **Implemented** — `"loop": true` + optional `"loop_period_s"` in the scene config, or `--loop` / `--loop-period` on the CLI.  See §3.1. |
| **Velocity** | Map a MIDI-style velocity (0–127) to `level_dbfs` automatically. |

A minimal music fork could be implemented without touching the synth layer at all —
it would be a new front-end scene parser that understands tempo/beat notation and
ADSR envelopes, translating them into the existing siggen signal descriptors.

---

## 12. Architecture notes

The synthesiser is organised as a layered Python package (`synth/`):

```
Layer   Module          Responsibility
──────  ──────────────  ────────────────────────────────────────────────
L1      constants.py    FT8 protocol constants (public facts only)
L2      crc.py          CRC-14 append / verify
L3      symbols.py      Codeword bits → 79 symbol tone indices (Gray map + Costas sync)
L4      modulator.py    Tone indices → GFSK audio (Gaussian pulse shaping, continuous phase)
L5      channel.py      AWGN generation, SNR calibration, Kaiser FIR bandlimiting, mixing
L6      wavio.py        16-bit mono WAV write / read (stdlib only)
L7      packing.py      FT8 Type-1 message text → 77-bit payload
L8      ldpc.py         LDPC(174,91) encode (parity generation)
L9      encoder.py      End-to-end pipeline: L7 → L2 → L8 → L3 → L4
```

**`siggen.py`** sits above the package and provides the JSONL scene engine.  It
imports only `synth.channel._lowpass_fir`, `synth.wavio`, and `synth.constants` at
module load time.  The FT8 encode chain (`synth.encoder`) is imported lazily — only
when a scene contains at least one `ft8` signal.  Scenes with no FT8 signals incur
no FT8 import cost.

**Key design invariants:**
- The `synth/` package is a **clean-room TX encoder only**.  It implements the
  transmit half of FT8 (text → audio), derived solely from the published protocol
  paper.  It shares no code with `libft8.dll` or `OpenWSFZ.Ft8/`.
- All FT8 decode work remains in `libft8.dll` (the product dependency) and is
  entirely separate from this synthesiser.
- The synthesiser is an independent oracle: it can produce reference signals that
  the decoder is then tested against, without circular dependency.
