# siggen.py — General-Purpose Signal Generator Reference

**Location:** `qa/rr-study/siggen.py`  
**Requires:** Python venv at `qa/rr-study/.venv/` (same venv as the R&R synthesiser)  
**Dependencies:** `numpy`, `scipy` (already present); no new packages required.

All commands below are run from the `qa/rr-study/` directory.  
Windows: `.venv\Scripts\python siggen.py …`  
Linux/macOS: `.venv/bin/python siggen.py …`

---

## 1. Overview

`siggen.py` is a standalone signal generator that reads a **JSONL scene file**
and renders an arbitrary mix of signals into a single audio output. Supported
signal types are:

| Type | Description |
|---|---|
| `sine` | Continuous-phase sinusoidal tone |
| `square` | Square wave (configurable duty cycle) |
| `sawtooth` | Sawtooth wave |
| `triangle` | Triangle wave |
| `chirp` | Linear or logarithmic frequency sweep |
| `noise` | AWGN burst (white or bandlimited) |
| `ft8` | FT8-encoded GFSK message (lazy import of `synth.encoder`) |

Outputs can be routed to a WAV file, an audio output device, or both
simultaneously. When no `ft8` signal is present, the FT8 encode chain is never
imported — `siggen.py` is fully usable without the FT8 stack.

### CLI synopsis

```
python siggen.py SCENE_FILE [--out PATH] [--device NAME] [--rate HZ]
                            [--duration S]

python siggen.py --batch BATCH_FILE [--out PATH] [--device NAME] [--rate HZ]
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `SCENE_FILE` | path | *(required unless `--batch`)* | JSONL scene file |
| `--out PATH` | str | *(from scene line or error)* | Output WAV file path |
| `--device NAME` | str | *(from scene line or none)* | Audio device name substring |
| `--rate HZ` | int | `48000` | Sample rate (Hz) |
| `--duration S` | float | *(auto)* | Total scene duration (s) |
| `--batch FILE` | path | *(none)* | Batch mode: JSON array of scene objects |

At least one output sink (`--out` or `--device`) must be resolvable — from
either the scene file or a CLI flag. If neither is present the script exits
with a descriptive error.

---

## 2. JSONL Scene File Format

A scene file is a sequence of UTF-8 text lines, each being an independent JSON
object (JSON Lines format). Lines are processed in order.

### Comment lines

Lines whose first non-whitespace character is `#` are silently skipped.
This is a `siggen.py`-specific pre-processing rule — not a JSON extension:

```jsonl
# This is a comment — ignored by siggen.py
{"type":"sine","freq_hz":1000,"amplitude":0.5,"start_s":0.0,"duration_s":2.0}
```

Blank lines are also ignored.

### `"type":"scene"` line

A line with `"type":"scene"` declares output sinks and global render parameters.
It may appear anywhere in the file; conventionally it is the first line. If
multiple `"type":"scene"` lines are present, the last one wins.

| Field | Type | Default | Description |
|---|---|---|---|
| `out` | str | *(none)* | Output WAV file path |
| `device` | str | *(none)* | Audio output device name substring |
| `sample_rate` | int | `48000` | Sample rate in Hz |
| `duration_s` | float | *(auto)* | Total scene duration; auto = `max(start_s + signal_duration)` |
| `seed` | int | `0` | Global RNG seed for noise signals that omit their own |

**Example — self-describing scene file (no CLI flags required):**

```jsonl
{"type":"scene","out":"out/tone.wav","sample_rate":48000,"duration_s":5.0}
{"type":"sine","freq_hz":1000,"amplitude":0.5,"start_s":0.0,"duration_s":5.0}
```

**CLI flags always override scene-line values.** `--out`, `--device`, `--rate`,
and `--duration` each take precedence over the corresponding scene-line field.

---

## 3. Signal Type Reference

### Amplitude specification

All signal types accept either `amplitude` (linear peak) or `level_dbfs`
(0 dBFS = amplitude 1.0). The two are **mutually exclusive**: providing both in
one signal object is a parse-time error. When neither is given, `amplitude`
defaults to `1.0`.

| Specification | Effect |
|---|---|
| `"amplitude": 0.5` | Linear peak = 0.5 |
| `"level_dbfs": -6` | Linear peak = `10^(-6/20)` ≈ 0.501 |
| *(neither)* | Linear peak = 1.0 (default) |

For `noise` signals, the amplitude value is interpreted as the noise
**RMS (standard deviation)**, not peak, consistent with
`numpy.random.Generator.standard_normal` scaling.

---

### 3.1 `sine` — Sinusoidal tone

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_hz` | float | yes | — | Tone frequency (Hz) |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | yes | — | Start time within the scene (s) |
| `duration_s` | float | yes | — | Signal duration (s) |
| `phase_deg` | float | no | `0.0` | Initial phase (degrees) |

\* `amplitude` and `level_dbfs` are mutually exclusive.

```jsonl
{"type":"sine","freq_hz":1500,"amplitude":0.8,"start_s":0.0,"duration_s":3.0}
{"type":"sine","freq_hz":440,"level_dbfs":-12,"phase_deg":90,"start_s":1.0,"duration_s":2.0}
```

---

### 3.2 `square` — Square wave

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_hz` | float | yes | — | Fundamental frequency (Hz) |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | yes | — | Start time (s) |
| `duration_s` | float | yes | — | Signal duration (s) |
| `duty_cycle` | float | no | `0.5` | Duty cycle (0.0–1.0 exclusive) |

\* Mutually exclusive.

```jsonl
{"type":"square","freq_hz":500,"amplitude":0.6,"start_s":0.0,"duration_s":2.0}
{"type":"square","freq_hz":500,"amplitude":0.6,"duty_cycle":0.25,"start_s":0.0,"duration_s":2.0}
```

---

### 3.3 `sawtooth` — Sawtooth wave

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_hz` | float | yes | — | Fundamental frequency (Hz) |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | yes | — | Start time (s) |
| `duration_s` | float | yes | — | Signal duration (s) |

\* Mutually exclusive.

```jsonl
{"type":"sawtooth","freq_hz":440,"amplitude":0.5,"start_s":0.0,"duration_s":2.0}
```

---

### 3.4 `triangle` — Triangle wave

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_hz` | float | yes | — | Fundamental frequency (Hz) |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | yes | — | Start time (s) |
| `duration_s` | float | yes | — | Signal duration (s) |

\* Mutually exclusive.

```jsonl
{"type":"triangle","freq_hz":440,"amplitude":0.5,"start_s":0.0,"duration_s":2.0}
```

---

### 3.5 `chirp` — Frequency sweep

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `freq_start_hz` | float | yes | — | Start frequency (Hz) |
| `freq_end_hz` | float | yes | — | End frequency (Hz) |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | yes | — | Start time (s) |
| `duration_s` | float | yes | — | Sweep duration (s) |
| `method` | str | no | `"linear"` | `"linear"` or `"logarithmic"` |

\* Mutually exclusive. Implementation uses `scipy.signal.chirp`.

```jsonl
{"type":"chirp","freq_start_hz":500,"freq_end_hz":3000,"amplitude":0.7,"start_s":0.0,"duration_s":5.0}
{"type":"chirp","freq_start_hz":200,"freq_end_hz":4000,"amplitude":0.5,"method":"logarithmic","start_s":2.0,"duration_s":8.0}
```

---

### 3.6 `noise` — AWGN burst

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `amplitude` | float | no* | `1.0` | Noise RMS (std-dev) |
| `level_dbfs` | float | no* | — | Noise RMS in dBFS |
| `start_s` | float | yes | — | Burst start time (s) |
| `duration_s` | float | yes | — | Burst duration (s) |
| `cutoff_hz` | float | no | *(wideband)* | Kaiser FIR lowpass cutoff (Hz) |
| `seed` | int | no | *(scene `seed`)* | RNG seed (overrides scene global) |

\* Mutually exclusive. For `noise`, `amplitude` / `level_dbfs` is the noise
**RMS (standard deviation)**, not the peak amplitude.

The Kaiser FIR lowpass filter (255 taps, β=6.0, ~60 dB stopband) is the same
implementation used in `synth.channel.add_noise()`.

```jsonl
# Wideband AWGN at RMS 0.1
{"type":"noise","amplitude":0.1,"start_s":0.0,"duration_s":15.0}

# Bandlimited to 3 kHz (real SSB receiver model)
{"type":"noise","amplitude":0.1,"cutoff_hz":3000,"start_s":0.0,"duration_s":15.0}

# Per-signal seed for reproducibility
{"type":"noise","amplitude":0.05,"cutoff_hz":3000,"seed":42,"start_s":0.0,"duration_s":15.0}
```

---

### 3.7 `ft8` — FT8-encoded message

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `message` | str | yes | — | FT8 message text (e.g. `"CQ Q1ABC FN42"`) |
| `freq_hz` | float | yes | — | Base audio frequency / tone 0 (Hz) |
| `amplitude` | float | no* | `1.0` | Peak linear amplitude |
| `level_dbfs` | float | no* | — | Peak amplitude in dBFS |
| `start_s` | float | no | `0.0` | Start time within the scene buffer (s) |
| `dt_s` | float | no | `0.0` | DT offset within the FT8 slot (s) |

\* Mutually exclusive.  
⚠ `duration_s` is **not accepted** — FT8 signals are always exactly 15.0 s
(`SLOT_LENGTH_S`). Supplying `duration_s` causes an immediate parse error.

`synth.encoder` is imported lazily on the first `ft8` signal encountered. A
scene with only primitive signal types (`sine`, `noise`, etc.) will never
import the FT8 encode chain.

```jsonl
# Single FT8 call at 1500 Hz base frequency, at −6 dBFS
{"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"level_dbfs":-6,"start_s":0.0}

# Two simultaneous FT8 signals (near-collision scenario)
{"type":"ft8","message":"Q1AW Q1ABC +05","freq_hz":1150,"amplitude":0.5,"start_s":0.0}
{"type":"ft8","message":"Q1ABC Q1AW RR73","freq_hz":1162,"amplitude":0.5,"start_s":0.0}
```

---

## 4. Output Routing

### File output

When `out` is declared (via scene line or `--out`), the mixed buffer is written
as a **16-bit mono PCM WAV** with 6 dB headroom peak normalisation using
`synth.wavio.write_wav()`. Parent directories are created if they do not exist.

### Device output

When `device` is declared (via scene line or `--device`), the name is matched
**case-insensitively as a substring** against `sounddevice.query_devices()`
output-capable devices. The first match is used. The buffer is normalised to
0.9 peak, cast to float32, and played via `sounddevice.play()` (blocking).

If no device matches, the script prints available output devices and exits with
a non-zero code.

### Simultaneous file + device

Both sinks may be active simultaneously. When both are declared, the WAV file
is written first, then playback begins.

```
# WAV file only
python siggen.py scene.jsonl --out tone.wav

# Device only
python siggen.py scene.jsonl --device "CABLE Input"

# Both simultaneously
python siggen.py scene.jsonl --out tone.wav --device "CABLE Input"
```

---

## 5. Batch Mode

Batch mode renders multiple scenes sequentially from a single JSON array file.

### Batch file format

```json
[
    {
        "out": "out/scene_a.wav",
        "sample_rate": 48000,
        "signals": [
            {"type":"sine","freq_hz":1000,"amplitude":0.5,"start_s":0.0,"duration_s":2.0}
        ]
    },
    {
        "out": "out/scene_b.wav",
        "signals": [
            {"type":"chirp","freq_start_hz":500,"freq_end_hz":3000,"amplitude":0.7,
             "start_s":0.0,"duration_s":5.0}
        ]
    }
]
```

Each element is a scene object:

| Field | Type | Description |
|---|---|---|
| `signals` | array | Signal descriptor objects (same schema as JSONL signal lines) |
| `out` | str | WAV output path for this item |
| `device` | str | Audio device name for this item |
| `sample_rate` | int | Sample rate (default: 48000) |
| `duration_s` | float | Scene duration (default: auto) |
| `seed` | int | Global RNG seed (default: 0) |

### Per-item failure handling

A failure in one batch item prints `[item N] ERROR: <msg>` and continues to
the next item (non-fatal). The script exits with code 1 after all items are
processed if any item failed.

### CLI overrides in batch mode

`--out`, `--device`, and `--rate` are applied as overrides to every batch item.
For `--out`, this means all items write to the same path (last item survives).
This is useful when combined with a per-item `device` field.

```
# Process all items in jobs.json
python siggen.py --batch jobs.json

# Override output directory isn't supported directly, but --device can be
# applied globally to all items
python siggen.py --batch jobs.json --device "CABLE Input"
```

---

## 6. Examples

### 6.1 Single sine tone to WAV

```jsonl
# sine_1k.jsonl
{"type":"scene","out":"sine_1k.wav","duration_s":3.0}
{"type":"sine","freq_hz":1000,"amplitude":0.8,"start_s":0.0,"duration_s":3.0}
```

```
python siggen.py sine_1k.jsonl
```

Or without a scene line:

```
python siggen.py sine_1k.jsonl --out sine_1k.wav --duration 3.0
```

---

### 6.2 Multi-signal mixed scene (sine + noise + ft8)

```jsonl
# mixed.jsonl
{"type":"scene","out":"mixed.wav"}
# FT8 signal at 1500 Hz
{"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":0.5,"start_s":0.0}
# Interference tone at 1200 Hz
{"type":"sine","freq_hz":1200,"amplitude":0.1,"start_s":0.0,"duration_s":15.0}
# Bandlimited channel noise (3 kHz SSB model)
{"type":"noise","amplitude":0.05,"cutoff_hz":3000,"start_s":0.0,"duration_s":15.0}
```

```
python siggen.py mixed.jsonl
```

---

### 6.3 Chirp sweep to audio device

Play a 500 Hz → 3 kHz sweep through VB-CABLE for waterfall calibration:

```jsonl
# sweep.jsonl
{"type":"chirp","freq_start_hz":500,"freq_end_hz":3000,"amplitude":0.7,
 "start_s":0.0,"duration_s":10.0}
```

```
python siggen.py sweep.jsonl --device "CABLE Input" --duration 10.0
```

---

### 6.4 Batch file — SNR sweep for sensitivity characterisation

Generate a ladder of FT8 WAVs at different SNR levels (for S1b-style analysis).
Each item applies a different noise amplitude to simulate a given SNR:

```json
[
    {"out":"snr_m24.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":31.62,"cutoff_hz":3000,"start_s":0.0,"duration_s":15.0}
    ]},
    {"out":"snr_m21.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":22.39,"cutoff_hz":3000,"start_s":0.0,"duration_s":15.0}
    ]},
    {"out":"snr_m18.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":15.85,"cutoff_hz":3000,"start_s":0.0,"duration_s":15.0}
    ]}
]
```

```
python siggen.py --batch snr_sweep.json
```

---

### 6.5 Near-collision FT8 pair (R-003 recipe)

Two FT8 stations 12 Hz apart — same technique as S8 stations E/F but within
a standalone scene for rapid iteration:

```jsonl
# near_collision.jsonl
{"type":"scene","out":"near_collision.wav"}
{"type":"ft8","message":"Q1AW Q1ABC +05","freq_hz":1150,"amplitude":0.5,"start_s":0.0}
{"type":"ft8","message":"Q1ABC Q1AW RR73","freq_hz":1162,"amplitude":0.5,"start_s":0.0}
{"type":"noise","amplitude":0.05,"cutoff_hz":3000,"start_s":0.0,"duration_s":15.0}
```

```
python siggen.py near_collision.jsonl
```

---

## 7. R&R Scenario Improvement Recipes

These recommendations are enabled by `siggen.py`. They apply to future R&R
study runs and are not required before using `siggen.py` itself.

---

### R-001 — Revert S1/S2/S3 to wideband AWGN (HIGH priority)

**Problem:** The bandlimited 3 kHz noise applied in `harness/run_scenario.py`
(commit `c9556a2`) was correct for multi-signal perceptual quality (S4, S7, S8)
but **breaks S1 as a calibration measurement**: the WSJT-X reference appraiser
shifted from +1.00 dB bias to −2.00 dB under 3 kHz noise, causing it to fail
its own ±2.0 dB criterion; S1 %GR&R deteriorated from 1.40% to 10.19%.

**Recommended fix:** Restore `noise_cutoff_hz=None` in `_render_single()` for
S1/S2/S3 in `harness/run_scenario.py`. S4, S7, S8 should retain `noise_cutoff_hz=3000`.

**Verification with siggen.py:**

```jsonl
# S1-style calibration scene — wideband noise, single FT8 signal
{"type":"scene","out":"s1_verify.wav"}
{"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0}
{"type":"noise","amplitude":0.178,"start_s":0.0,"duration_s":15.0}
```

Play through WSJT-X and confirm the reported SNR matches the expected value.

---

### R-002 — S1b threshold sweep (MEDIUM priority)

**Problem:** S1b currently tests a single threshold at −21 dB (OpenWSFZ: 0%,
WSJT-X: 100%), giving a cliff with no curve. This does not characterise the
sensitivity boundary for either appraiser.

**Recommended fix:** Sweep from −24 to −18 dB in 1 dB steps (7 levels) to
build a decode probability vs. SNR curve for both appraisers.

**Batch file recipe:**

```json
[
    {"out":"s1b_m24.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":50.12,"start_s":0.0,"duration_s":15.0}
    ]},
    {"out":"s1b_m23.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":44.67,"start_s":0.0,"duration_s":15.0}
    ]},
    {"out":"s1b_m22.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":39.81,"start_s":0.0,"duration_s":15.0}
    ]},
    {"out":"s1b_m21.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":35.48,"start_s":0.0,"duration_s":15.0}
    ]},
    {"out":"s1b_m20.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":31.62,"start_s":0.0,"duration_s":15.0}
    ]},
    {"out":"s1b_m19.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":28.18,"start_s":0.0,"duration_s":15.0}
    ]},
    {"out":"s1b_m18.wav","signals":[
        {"type":"ft8","message":"CQ Q1ABC FN42","freq_hz":1500,"amplitude":1.0,"start_s":0.0},
        {"type":"noise","amplitude":25.12,"start_s":0.0,"duration_s":15.0}
    ]}
]
```

```
python siggen.py --batch s1b_sweep.json
```

Load each WAV into WSJT-X and OpenWSFZ in turn, recording decode success/failure
at each level to build the sensitivity curve.

---

### R-003 — S7 near-collision sub-scenario (MEDIUM priority)

**Problem:** S8 exercises frequency resolution (stations E/F at 12 Hz spacing)
but S7 has no near-collision test. Adding a near-collision part would measure
the co-channel frequency resolution capability of both appraisers.

**Recipe for rapid prototyping:**

```jsonl
# s7_near_collision_proto.jsonl
{"type":"scene","out":"s7_near_collision.wav"}
# Station A at 1150 Hz
{"type":"ft8","message":"Q1AW Q1ABC +05","freq_hz":1150,"amplitude":0.5,"start_s":0.0}
# Station B at 1162 Hz (12 Hz apart — same as S8 E/F pair)
{"type":"ft8","message":"Q1ABC Q1AW RR73","freq_hz":1162,"amplitude":0.5,"start_s":0.0}
# Shared bandlimited noise floor
{"type":"noise","amplitude":0.05,"cutoff_hz":3000,"start_s":0.0,"duration_s":15.0}
```

Play through both appraisers and record decode results. If both appraisers
consistently decode both messages, reduce the frequency separation to find the
resolution limit. Once satisfactory parameters are found, formalise as a new
part in `scenarios/s7-compounding.json`.

---

### R-004 — resume_study.py log path parameterisation (LOW priority)

**Problem:** `WSJT_ALL_TXT` and `OWSFZ_ALL_TXT` in `resume_study.py` are
hardcoded machine-specific paths (QA finding F-002 from the `synth-cli-args`
review). The script cannot be used on a different machine without editing source.

**Recommended fix:** Add `--wsjt-log` and `--owsfz-log` flags to `resume_study.py`:

```
python resume_study.py --from-scenario S4 \
    --wsjt-log "C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT" \
    --owsfz-log "C:\ProgramData\OpenWSFZ\all.txt"
```

This is outside the scope of `siggen.py` but should be captured for the next
synthesiser CLI improvement change.
