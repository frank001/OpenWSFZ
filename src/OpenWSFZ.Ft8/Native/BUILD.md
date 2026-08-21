# libft8.dll — Build Provenance and API Notes

## Source

- **Library**: frank001/ft8_lib fork — branch `msvc-compat` (commit `d18ed84`)
- **Fork URL**: `https://github.com/frank001/ft8_lib.git`
- **Upstream**: `kgoba/ft8_lib`, tag `2.0` (commit `50ee0c06361388a992c80a1af9c1189652b72e51`)
- **Fork changes**: MSVC VLA patches (`common/monitor.c`, `ft8/decode.c`) — see commit message on `msvc-compat` branch
- **Licence**: MIT (see `THIRD-PARTY-NOTICES.md` at the repo root)
- **Integration**: **vendored** (plain committed files), not a git submodule — see
  `native/ft8_lib_vendor/PROVENANCE.md` for the upstream HEAD SHA and content-identity proof.
  `common/monitor.c` and `ft8/decode.c` carry genuine MSVC-compat modifications and stay at
  `native/ft8_lib_build/patched/` rather than moving into the vendored tree, so that tree stays
  byte-identical to upstream (r0-reproducible-native-build).

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
| Pass-0 `kMin_score` | 10 | `K_MIN_SCORE` in ft8_shim.c |
| Pass-1 `kMin_score` | 10 (default) | `s_k_min_score_pass2` — runtime-configurable via `ft8_set_decode_params`; default calibrated by D-009 R&R study (shim 20260029) |
| Pass-0 `kMax_candidates` | 140 | `K_MAX_CANDIDATES` in ft8_shim.c |
| Pass-1 `kMax_candidates` | 200 | `K_MAX_CANDIDATES_PASS2` in ft8_shim.c |
| `kLDPC_iterations` | 50 | `K_LDPC_ITERATIONS` — raised from 25 at shim 20260025 (H_ITER diagnostic) |
| `OSD_CORR_THRESHOLD` | 0.10f (default) | `s_osd_corr_threshold` — runtime-configurable via `ft8_set_decode_params`; default calibrated by D-009 R4 (shim 20260028) |
| `OSD_NHARD_MAX` | 60 (default) | `s_osd_nhard_max` — runtime-configurable via `ft8_set_decode_params`; default calibrated by D-009 R5 (shim 20260028) |

## Source Files Compiled into libft8.dll

```
native/ft8_lib_vendor/ft8/constants.c
native/ft8_lib_vendor/ft8/crc.c
native/ft8_lib_build/patched/ft8/decode.c        (MSVC VLA compat patch)
native/ft8_lib_vendor/ft8/encode.c               (p15: required for ft8_encode() used in narrow tile suppression)
native/ft8_lib_vendor/ft8/ldpc.c
native/ft8_lib_vendor/ft8/message.c              (r0: /FI stpcpy_msvc_compat.h — see that file)
native/ft8_lib_vendor/ft8/text.c
native/ft8_lib_build/patched/common/monitor.c    (MSVC VLA compat patch)
native/ft8_lib_vendor/fft/kiss_fft.c
native/ft8_lib_vendor/fft/kiss_fftr.c
src/OpenWSFZ.Ft8/Native/ft8_shim.c               (our shim — orchestrates the pipeline)
native/ft8_lib_vendor/refine/sync_refiner.c      (r1: diagnostic-only coherent sync refiner,
                                                   OpenWSFZ-original, no production call site)
native/ft8_lib_vendor/refine/coherent_llr.c      (r2: diagnostic-only coherent multi-symbol LLR
                                                   formation, OpenWSFZ-original, no production
                                                   call site — reuses sync_refiner.c's own
                                                   downconvert_decimate/design_lowpass_hann via
                                                   refine_common.h)
```

r0-reproducible-native-build: every one of these now compiles from tracked source on every
`rebuild_shim.bat` invocation — no pre-built `.obj` file is linked. Nine of the eleven were
previously linked from untracked, unreproducible pre-built objects; see
`native/ft8_lib_vendor/PROVENANCE.md` for the vendoring provenance and
`ft8_shim.h`'s `FT8_SHIM_VERSION 20260039` changelog entry for the one genuine finding this
surfaced (the D-006 `stpcpy` pointer-truncation fix, previously a hand-patched opcode byte in
`message.obj` with no source-level counterpart, restored via a build-side-only compat header).

**Not included**: `common/audio.c`, `common/wave.c`
(audio I/O and WAV I/O are not needed for the decode-only DLL; also not vendored).

## Build Procedure (Windows x64, MSVC)

Prerequisites: Visual Studio Build Tools with MSVC v143 (or later), x64 Native Tools
Command Prompt.

**Use `native/ft8_lib_build/rebuild_shim.bat` — it is the authoritative build script and is kept
in sync with the exports and source list above; do not hand-run the commands below except to
understand what it does.**

```batch
:: Compile the nine files vendored under native/ft8_lib_vendor/ (constants, crc, ldpc, text,
:: encode, message, kiss_fft, kiss_fftr — plus monitor, patched, below), each /I'd at the vendor
:: root so both quote-form sibling includes and angle-bracket <ft8/...>/<common/...>/<fft/...>
:: includes resolve. message.c additionally needs /FI stpcpy_msvc_compat.h (D-006, see above).
cl /I native\ft8_lib_vendor /std:c11 /O2 /W3 /c ^
   native\ft8_lib_vendor\ft8\constants.c native\ft8_lib_vendor\ft8\crc.c ^
   native\ft8_lib_vendor\ft8\ldpc.c native\ft8_lib_vendor\ft8\text.c ^
   native\ft8_lib_vendor\ft8\encode.c ^
   native\ft8_lib_vendor\fft\kiss_fft.c native\ft8_lib_vendor\fft\kiss_fftr.c
cl /I native\ft8_lib_vendor /FI native\ft8_lib_build\patched\stpcpy_msvc_compat.h ^
   /std:c11 /O2 /W3 /c native\ft8_lib_vendor\ft8\message.c

:: Compile the two MSVC-VLA-patched files (still outside the vendor tree — see PROVENANCE.md)
cl /I native\ft8_lib_vendor\common /I native\ft8_lib_vendor /std:c11 /O2 /W3 /c ^
   native\ft8_lib_build\patched\common\monitor.c
cl /I native\ft8_lib_vendor\ft8 /I native\ft8_lib_vendor /I src\OpenWSFZ.Ft8\Native ^
   /std:c11 /O2 /W3 /c native\ft8_lib_build\patched\ft8\decode.c

:: Compile our shim
cl /I native\ft8_lib_vendor /I src\OpenWSFZ.Ft8\Native /std:c11 /O2 /W3 /c ^
   src\OpenWSFZ.Ft8\Native\ft8_shim.c

:: Compile the sync refiner (r1-sync-refiner-instrument-validation, diagnostic-only,
:: OpenWSFZ-original — no call site in decode.c/ft8_shim.c)
cl /I native\ft8_lib_vendor /I src\OpenWSFZ.Ft8\Native /std:c11 /O2 /W3 /c ^
   native\ft8_lib_vendor\refine\sync_refiner.c

:: Compile the coherent LLR export (r2-coherent-llr-instrument, diagnostic-only,
:: OpenWSFZ-original — no call site in decode.c/ft8_shim.c)
cl /I native\ft8_lib_vendor /I src\OpenWSFZ.Ft8\Native /std:c11 /O2 /W3 /c ^
   native\ft8_lib_vendor\refine\coherent_llr.c

:: Link into DLL — exports must stay in sync with rebuild_shim.bat
link /DLL /OUT:libft8.dll ^
   /EXPORT:ft8_lib_version_check ^
   /EXPORT:ft8_decode_all ^
   /EXPORT:ft8_get_last_pass_counts ^
   /EXPORT:ft8_get_max_passes ^
   /EXPORT:ft8_get_last_noise_floor_db ^
   /EXPORT:ft8_encode_message ^
   /EXPORT:ft8_get_last_candidate_counts ^
   /EXPORT:ft8_get_last_llr_stats ^
   /EXPORT:ft8_set_ap_bits ^
   /EXPORT:ft8_set_decode_params ^
   /EXPORT:ft8_get_hash_table_reject_count ^
   /EXPORT:ft8_refine_candidate ^
   /EXPORT:ft8_extract_llrs_at ^
   /EXPORT:ft8_coherent_llr_at ^
   constants.obj crc.obj decode.obj encode.obj ldpc.obj message.obj text.obj ^
   monitor.obj kiss_fft.obj kiss_fftr.obj ft8_shim.obj sync_refiner.obj coherent_llr.obj

:: Copy to repo location
copy libft8.dll ..\..\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll
```

## Build Procedure (Linux x64, GCC)

> **Note:** Since CI now rebuilds `libft8.so` from source on every Ubuntu run (see
> `"Build native Linux .so"` step in `.github/workflows/ci.yml`), a manual rebuild
> is only needed when developing locally on Linux or WSL2. The CI step clones
> `frank001/ft8_lib` (branch `msvc-compat`) and compiles against the current
> `ft8_shim.c`, so the committed binary is always superseded on the Ubuntu leg.

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
gcc -std=c11 -D_GNU_SOURCE -O2 -Wall -fPIC -I. -c \
    refine/sync_refiner.c refine/coherent_llr.c

gcc -shared -o libft8.so \
    constants.o crc.o decode.o encode.o ldpc.o message.o text.o \
    monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o sync_refiner.o coherent_llr.o \
    -lm

# Note: ft8_get_last_noise_floor_db is exported automatically (no explicit -Wl,--export-dynamic needed)
```

> **Note:** `-D_GNU_SOURCE` is required. `ft8_lib/ft8/message.c` calls `stpcpy`, which is
> a POSIX function declared in `<string.h>` only when `_GNU_SOURCE` or
> `_POSIX_C_SOURCE >= 200809L` is defined. Strict `-std=c11` does not expose it.

Verify exports (all fourteen symbols must appear — r1-sync-refiner-instrument-validation adds
ft8_refine_candidate, n1-extract-llrs-at-position adds ft8_extract_llrs_at,
r2-coherent-llr-instrument adds ft8_coherent_llr_at):

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
clang -std=c11 -D_GNU_SOURCE -O2 -Wall -fPIC -I. -target arm64-apple-macos11.0 -c \
    refine/sync_refiner.c refine/coherent_llr.c

clang -dynamiclib -target arm64-apple-macos11.0 \
    -o libft8.dylib \
    constants.o crc.o decode.o encode.o ldpc.o message.o text.o \
    monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o sync_refiner.o coherent_llr.o
```

> **Note:** `-D_GNU_SOURCE` is required for `stpcpy` on macOS as well (same reason as
> Linux — see note in the Linux section above).

Verify exports (`nm -gU` on macOS prefixes exported symbols with an underscore; all fourteen
symbols must appear — r1-sync-refiner-instrument-validation adds ft8_refine_candidate,
n1-extract-llrs-at-position adds ft8_extract_llrs_at, r2-coherent-llr-instrument adds
ft8_coherent_llr_at):

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
