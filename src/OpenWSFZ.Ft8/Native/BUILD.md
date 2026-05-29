# libft8.dll — Build Provenance and API Notes

## Source

- **Library**: [kgoba/ft8_lib](https://github.com/kgoba/ft8_lib)
- **Tag**: `2.0`
- **Commit SHA**: `50ee0c06361388a992c80a1af9c1189652b72e51`
- **Licence**: MIT
- **Submodule path**: `native/ft8_lib/` (repo root)

## Integration Point (Task 1.1–1.2 findings)

ft8_lib v2.0 does **not** expose a single "decode all signals from PCM" function. The
caller must orchestrate the full pipeline:

```
monitor_init()           — allocate the waterfall (STFT spectrogram)
  └─ monitor_process()   — feed PCM in blocks (block_size samples per call)
ftx_find_candidates()    — find sync candidates by Costas score
  └─ ftx_decode_candidate() — LDPC + CRC decode per candidate
       └─ ftx_message_decode() — unpack text from decoded payload
monitor_free()           — release waterfall memory
```

The shim (`ft8_shim.c`) implements this pipeline internally and exposes the simple
`ft8_decode_all()` entry point declared in `ft8_shim.h`.

## FT8Result Field Mapping (Task 1.3)

| FT8Result field | ft8_lib source | Unit / notes |
|---|---|---|
| `freq_hz` | `(min_bin + cand.freq_offset + (float)cand.freq_sub / freq_osr) / symbol_period` | Hz, rounded to int |
| `dt` | `(cand.time_offset + (float)cand.time_sub / time_osr) * symbol_period` | seconds |
| `snr` | `cand.score * 0.5f` | dB approximation (same formula as demo/decode_ft8.c) |
| `message[36]` | `ftx_message_decode()` output | null-terminated, max 35 chars (FTX_MAX_MESSAGE_LENGTH=35) |

`sizeof(FT8Result)` = 4 (freq_hz) + 4 (dt) + 4 (snr) + 36 (message) = **48 bytes**.
No padding — fields are naturally aligned.

## Monitor Configuration

```c
monitor_config_t cfg = {
    .f_min       = 200.0f,
    .f_max       = 3000.0f,
    .sample_rate = 12000,
    .time_osr    = 2,        // half-symbol time resolution
    .freq_osr    = 2,        // half-bin frequency resolution
    .protocol    = FTX_PROTOCOL_FT8
};
```

Waterfall memory: ~188 blocks × 2 × 2 × 448 bins × 1 byte (uint8_t) ≈ 337 KB heap.

## Decode Parameters

| Parameter | Value | Source |
|---|---|---|
| `kMin_score` | 10 | demo/decode_ft8.c default |
| `kMax_candidates` | 140 | demo/decode_ft8.c default |
| `kLDPC_iterations` | 25 | demo/decode_ft8.c default |
| `kMax_decoded_messages` | 50 | demo/decode_ft8.c default |

## Source Files Compiled into libft8.dll

```
ft8/constants.c
ft8/crc.c
ft8/decode.c
ft8/ldpc.c
ft8/message.c
ft8/text.c
common/monitor.c
fft/kiss_fft.c
fft/kiss_fftr.c
ft8_shim.c           (our shim — orchestrates the pipeline)
```

**Not included**: `ft8/encode.c`, `common/audio.c`, `common/wave.c`
(encoder, audio I/O, and WAV I/O are not needed for the decode-only DLL).

## Build Procedure (Windows x64, MSVC)

Prerequisites: Visual Studio Build Tools with MSVC v143 (or later), x64 Native Tools
Command Prompt.

```batch
cd native/ft8_lib

:: Compile ft8_lib source files
cl /I. /std:c11 /O2 /W3 /c ^
   ft8/constants.c ft8/crc.c ft8/decode.c ft8/ldpc.c ft8/message.c ft8/text.c ^
   common/monitor.c ^
   fft/kiss_fft.c fft/kiss_fftr.c

:: Compile our shim
cl /I. /std:c11 /O2 /W3 /c ^
   ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c

:: Link into DLL
link /DLL /OUT:libft8.dll /EXPORT:ft8_lib_version_check /EXPORT:ft8_decode_all ^
   constants.obj crc.obj decode.obj ldpc.obj message.obj text.obj ^
   monitor.obj kiss_fft.obj kiss_fftr.obj ft8_shim.obj

:: Copy to repo location
copy libft8.dll ..\..\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll
```

## Version File

`win-x64/libft8.version.txt` records the source commit SHA, compiler version, and build
date so the DLL is auditable without needing to rebuild it.
