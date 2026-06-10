# libft8.dll — Build Provenance and API Notes

## Source

- **Library**: frank001/ft8_lib fork — branch `msvc-compat` (commit `d18ed84`)
- **Fork URL**: `https://github.com/frank001/ft8_lib.git` (submodule URL in `.gitmodules`)
- **Upstream**: `kgoba/ft8_lib`, tag `2.0` (commit `50ee0c06361388a992c80a1af9c1189652b72e51`)
- **Fork changes**: MSVC VLA patches (`common/monitor.c`, `ft8/decode.c`) — see commit message on `msvc-compat` branch
- **Licence**: MIT
- **Submodule path**: `native/ft8_lib/` (repo root; superproject pointer pinned to `d18ed84`)

> **Note (p15):** Always build from the `msvc-compat` branch for MSVC (Windows) builds.
> GCC and Clang builds may use the unpatched submodule sources directly (those compilers
> support C11 VLAs natively). The `msvc-compat` commit includes only the VLA patches —
> all other source files are identical to the upstream `2.0` tag.

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
| `snr` | `signal_db − noise_floor_db − 26`. `signal_db` = mean of per-symbol max-over-8-tones in the 79-symbol message window; `noise_floor_db` = histogram-median of all waterfall uint8 magnitudes, converted via `x * 0.5f − 120.0f`. Bandwidth correction: 10·log₁₀(2500/6.25) ≈ 26 dB (WSJT-X 2500 Hz reference). **No post-correction applied** — R6 weak-signal fallback (−8 dB when SNR < −10 dB) removed; see R&R-001 / GitHub issue #30. | dB, WSJT-X 2500 Hz bandwidth convention |
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
ft8/encode.c         (p15: required for ft8_encode() used in narrow tile suppression)
ft8/ldpc.c
ft8/message.c
ft8/text.c
common/monitor.c
fft/kiss_fft.c
fft/kiss_fftr.c
ft8_shim.c           (our shim — orchestrates the pipeline)
```

**Not included**: `common/audio.c`, `common/wave.c`
(audio I/O and WAV I/O are not needed for the decode-only DLL).

## Build Procedure (Windows x64, MSVC)

Prerequisites: Visual Studio Build Tools with MSVC v143 (or later), x64 Native Tools
Command Prompt.

```batch
cd native/ft8_lib

:: Compile ft8_lib source files
:: Note: encode.c is now required by ft8_shim.c (p15 narrow suppression uses ft8_encode)
cl /I. /std:c11 /O2 /W3 /c ^
   ft8/constants.c ft8/crc.c ft8/decode.c ft8/encode.c ft8/ldpc.c ft8/message.c ft8/text.c ^
   common/monitor.c ^
   fft/kiss_fft.c fft/kiss_fftr.c

:: Compile our shim
cl /I. /std:c11 /O2 /W3 /c ^
   ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c

:: Link into DLL
link /DLL /OUT:libft8.dll /EXPORT:ft8_lib_version_check /EXPORT:ft8_decode_all /EXPORT:ft8_get_last_pass_counts /EXPORT:ft8_get_max_passes /EXPORT:ft8_get_last_noise_floor_db ^
   constants.obj crc.obj decode.obj encode.obj ldpc.obj message.obj text.obj ^
   monitor.obj kiss_fft.obj kiss_fftr.obj ft8_shim.obj

:: Copy to repo location
copy libft8.dll ..\..\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll
```

## Build Procedure (Linux x64, GCC)

Prerequisites: GCC ≥ 10, `build-essential`. WSL2 running Debian is acceptable.

Run from `native/ft8_lib/` inside the repository root:

```bash
gcc -std=c11 -D_GNU_SOURCE -O2 -Wall -fPIC -I. -c \
    ft8/constants.c ft8/crc.c ft8/decode.c ft8/encode.c ft8/ldpc.c \
    ft8/message.c ft8/text.c \
    common/monitor.c \
    fft/kiss_fft.c fft/kiss_fftr.c
gcc -std=c11 -D_GNU_SOURCE -O2 -Wall -fPIC -I. -c \
    ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c

gcc -shared -o libft8.so \
    constants.o crc.o decode.o encode.o ldpc.o message.o text.o \
    monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o \
    -lm

# Note: ft8_get_last_noise_floor_db is exported automatically (no explicit -Wl,--export-dynamic needed)
```

> **Note:** `-D_GNU_SOURCE` is required. `ft8_lib/ft8/message.c` calls `stpcpy`, which is
> a POSIX function declared in `<string.h>` only when `_GNU_SOURCE` or
> `_POSIX_C_SOURCE >= 200809L` is defined. Strict `-std=c11` does not expose it.

Verify exports (all five symbols must appear):

```bash
nm -D libft8.so | grep "ft8_"
```

Install to repo:

```bash
mkdir -p ../../src/OpenWSFZ.Ft8/Native/linux-x64
cp libft8.so ../../src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so
```

Expected binary size: ~100–150 KB.

Use the **unpatched** submodule sources (`native/ft8_lib/`) — GCC supports C11 VLAs
natively; the MSVC VLA patches in `native/ft8_lib_build/patched/` are not needed.

---

## Build Procedure (macOS ARM64, Clang)

Prerequisites: Xcode Command Line Tools (`xcode-select --install`) — available on any
macOS machine or the `macos-latest` GitHub Actions runner.

> **Note:** Since no Mac is available locally, in practice this binary is produced via
> the one-shot `workflow_dispatch` GitHub Actions workflow described in
> `tasks.md` sections 2.1–2.7. The workflow is deleted after the binary is committed.
> The commands below are provided for manual reproduction if needed.

Run from `native/ft8_lib/` inside the repository root:

```bash
clang -std=c11 -D_GNU_SOURCE -O2 -Wall -fPIC -I. -target arm64-apple-macos11.0 -c \
    ft8/constants.c ft8/crc.c ft8/decode.c ft8/encode.c ft8/ldpc.c \
    ft8/message.c ft8/text.c \
    common/monitor.c \
    fft/kiss_fft.c fft/kiss_fftr.c
clang -std=c11 -D_GNU_SOURCE -O2 -Wall -fPIC -I. -target arm64-apple-macos11.0 -c \
    ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c

clang -dynamiclib -target arm64-apple-macos11.0 \
    -o libft8.dylib \
    constants.o crc.o decode.o encode.o ldpc.o message.o text.o \
    monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o
```

> **Note:** `-D_GNU_SOURCE` is required for `stpcpy` on macOS as well (same reason as
> Linux — see note in the Linux section above).

Verify exports (`nm -gU` on macOS prefixes exported symbols with an underscore; all five symbols must appear):

```bash
nm -gU libft8.dylib | grep "ft8_"
```

Install to repo:

```bash
mkdir -p ../../src/OpenWSFZ.Ft8/Native/osx-arm64
cp libft8.dylib ../../src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib
```

Expected binary size: ~60–120 KB.

The `-target arm64-apple-macos11.0` flag is required: the CI matrix configures the
`macos-latest` leg with `rid: osx-arm64`, and the .NET 10 runtime on that runner
executes as ARM64. A P/Invoke native library loaded by an ARM64 .NET process must
itself be ARM64. macOS 11.0 (Big Sur) is the minimum deployment target because it
is the first macOS version released on Apple Silicon hardware.

Use the **unpatched** submodule sources (`native/ft8_lib/`) — Clang supports C11 VLAs
natively; the MSVC VLA patches are not needed.

---

## Version File

`win-x64/libft8.version.txt` records the source commit SHA, compiler version, and build
date so the DLL is auditable without needing to rebuild it. The file covers all three
platform binaries (Windows, Linux, macOS) — each platform adds its own row.
