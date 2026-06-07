#!/usr/bin/env python3
"""Batch FT8 decoder — calls ft8_decode_all from a specified libft8 DLL directly
via ctypes. Reads a directory of 15-second 12 kHz mono WAV files and writes an
ALL.TXT formatted decode log.

Primary use-case — baseline capture:
  Load the pre-fix DLL (shim v20260002) and batch-decode the same WAV files that
  a fixed-shim live session produced, to get an apples-to-apples recall comparison
  without needing to re-run a 46-minute live capture.

Quick start:
    # 1. Extract the pre-fix DLL from git history (Windows):
    git show 879ec46:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll > baseline_libft8.dll

    # 2. Decode:
    python qa/rr-study/batch_decode.py \\
        --dll      baseline_libft8.dll \\
        --wav-dir  D001-pcm-sic_items/save/ \\
        --out      D001-pcm-sic_items/baseline_all.txt

    # 3. Compare (see compare_real_signal.py):
    python qa/rr-study/compare_real_signal.py \\
        --wsjt     "D001-pcm-sic_items/WSJT-X ALL.TXT" \\
        --baseline  D001-pcm-sic_items/baseline_all.txt \\
        --fix      "D001-pcm-sic_items/OpenWSFZ ALL.TXT" \\
        --out       qa/rr-study/QA-FINDINGS-D001-real-signal-comparison.md

WAV requirements:
  Sample rate : 12 000 Hz (exactly — ft8_decode_all requires 12 kHz mono input)
  Channels    : 1 (mono)
  Bit depth   : 16-bit signed integer
  Duration    : 15 s (180 000 samples); longer files are truncated, shorter padded

ALL.TXT format emitted:
  YYMMDD_HHMMSS     {freq_mhz:.3f} Rx FT8  {snr:5d} {dt:5.2f} {freq_hz:4d} {message}
  Timestamp is derived from the WAV filename (expects YYMMDD_HHMMSS.wav naming).
"""
from __future__ import annotations

import argparse
import ctypes
import struct
import sys
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

EXPECTED_SAMPLE_RATE   = 12_000
EXPECTED_SAMPLES       = 180_000  # 15 s × 12 kHz
MAX_RESULTS_SAFE       = 540      # Upper bound — pre-fix DLL returns ≤340, fix ≤540

WAV_HEADER_BYTES       = 44       # Standard PCM WAV header


# ── Native struct ────────────────────────────────────────────────────────────

class _Ft8NativeResult(ctypes.Structure):
    """Mirrors the C FT8Result struct (ft8_shim.h).

    Layout (48 bytes, no padding):
      offset  0: int   FreqHz   — audio-frequency centre, Hz
      offset  4: float Dt       — time offset from slot start, seconds
      offset  8: int   Snr      — SNR in dB (2500 Hz noise-bandwidth convention)
      offset 12: char  Message  — null-terminated text, max 35 chars + NUL

    This layout is stable across shim versions 20260002 and 20260003; only the
    decode logic changed between those versions, not the ABI struct.
    """
    _fields_ = [
        ("FreqHz",  ctypes.c_int),
        ("Dt",      ctypes.c_float),
        ("Snr",     ctypes.c_int),
        ("Message", ctypes.c_char * 36),
    ]

assert ctypes.sizeof(_Ft8NativeResult) == 48, (
    f"Struct size mismatch: expected 48, got {ctypes.sizeof(_Ft8NativeResult)}. "
    "Check platform alignment."
)


# ── DLL loader ───────────────────────────────────────────────────────────────

def _load_dll(dll_path: Path) -> ctypes.CDLL:
    """Load the native shim DLL and wire up the three function signatures."""
    if not dll_path.exists():
        sys.exit(f"ERROR: DLL not found: {dll_path}")

    try:
        lib = ctypes.CDLL(str(dll_path))
    except OSError as exc:
        sys.exit(f"ERROR: cannot load DLL '{dll_path}': {exc}")

    # ft8_lib_version_check() -> int
    lib.ft8_lib_version_check.restype  = ctypes.c_int
    lib.ft8_lib_version_check.argtypes = []

    # ft8_decode_all(float* pcm, int pcmLen, FT8Result* results, int maxResults) -> int
    lib.ft8_decode_all.restype  = ctypes.c_int
    lib.ft8_decode_all.argtypes = [
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_int,
        ctypes.POINTER(_Ft8NativeResult),
        ctypes.c_int,
    ]

    # Optional — may not exist in older shim versions; ignore if absent
    try:
        lib.ft8_get_max_passes.restype  = ctypes.c_int
        lib.ft8_get_max_passes.argtypes = []
        max_passes = lib.ft8_get_max_passes()
    except AttributeError:
        max_passes = None

    version = lib.ft8_lib_version_check()
    print(f"  DLL loaded: {dll_path.name}")
    print(f"  Shim version : {version}")
    if max_passes is not None:
        print(f"  K_MAX_PASSES : {max_passes}")
    else:
        print(f"  K_MAX_PASSES : (ft8_get_max_passes not exported — pre-20260002 shim?)")

    return lib


# ── WAV reading ──────────────────────────────────────────────────────────────

def _read_wav_as_float32(wav_path: Path) -> list[float] | None:
    """Read a 12 kHz mono 16-bit WAV and return samples normalised to [-1, 1].

    Returns None (with a warning) if the file does not match expected format.
    Truncates to EXPECTED_SAMPLES if longer; zero-pads if shorter.
    """
    data = wav_path.read_bytes()

    # Basic RIFF header validation
    if len(data) < WAV_HEADER_BYTES:
        print(f"  WARNING: {wav_path.name} too short ({len(data)} bytes) — skipping")
        return None
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        print(f"  WARNING: {wav_path.name} is not a valid RIFF/WAVE file — skipping")
        return None

    # Parse fmt chunk fields from standard 44-byte PCM header
    audio_format   = struct.unpack_from("<H", data, 20)[0]   # 1 = PCM
    num_channels   = struct.unpack_from("<H", data, 22)[0]
    sample_rate    = struct.unpack_from("<I", data, 24)[0]
    bits_per_sample = struct.unpack_from("<H", data, 34)[0]

    if audio_format != 1:
        print(f"  WARNING: {wav_path.name} is not PCM (format={audio_format}) — skipping")
        return None
    if num_channels != 1:
        print(f"  WARNING: {wav_path.name} has {num_channels} channels (expected 1) — skipping")
        return None
    if sample_rate != EXPECTED_SAMPLE_RATE:
        print(f"  WARNING: {wav_path.name} sample rate={sample_rate} Hz (expected 12000) — skipping")
        return None
    if bits_per_sample != 16:
        print(f"  WARNING: {wav_path.name} is {bits_per_sample}-bit (expected 16) — skipping")
        return None

    # Sample data starts at byte 44
    raw = data[WAV_HEADER_BYTES:]
    n_samples = len(raw) // 2  # 2 bytes per int16 sample

    # Unpack int16 samples
    samples_i16 = struct.unpack_from(f"<{n_samples}h", raw)

    # Normalise to [-1.0, 1.0]
    samples_f32 = [s / 32768.0 for s in samples_i16]

    if n_samples < EXPECTED_SAMPLES:
        # Zero-pad to 180 000
        samples_f32.extend([0.0] * (EXPECTED_SAMPLES - n_samples))
    elif n_samples > EXPECTED_SAMPLES:
        # Truncate — capture may run a few samples long
        samples_f32 = samples_f32[:EXPECTED_SAMPLES]

    return samples_f32


# ── Decoder ──────────────────────────────────────────────────────────────────

def _decode_wav(lib: ctypes.CDLL, samples: list[float]) -> list[_Ft8NativeResult]:
    """Call ft8_decode_all and return the list of decoded results."""
    pcm_arr     = (ctypes.c_float * EXPECTED_SAMPLES)(*samples)
    results_arr = (_Ft8NativeResult * MAX_RESULTS_SAFE)()

    count = lib.ft8_decode_all(pcm_arr, EXPECTED_SAMPLES, results_arr, MAX_RESULTS_SAFE)

    if count < 0:
        print(f"  WARNING: ft8_decode_all returned {count} — decode error")
        return []

    return list(results_arr[:count])


# ── ALL.TXT formatting ────────────────────────────────────────────────────────

def _format_line(timestamp: str, freq_mhz: float, result: _Ft8NativeResult) -> str:
    """Format one decode result as an ALL.TXT line.

    Format (matches OpenWSFZ emit):
      YYMMDD_HHMMSS     {freq_mhz:.3f} Rx FT8  {snr:5d} {dt:5.2f} {freq_hz:4d} {message}
    """
    message = result.Message.decode("ascii", errors="replace").rstrip("\x00")
    return (
        f"{timestamp}     {freq_mhz:.3f} Rx FT8"
        f"  {result.Snr:5d} {result.Dt:5.2f} {result.FreqHz:4d} {message}"
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dll",      required=True, type=Path,
                        help="Path to libft8.dll / libft8.so / libft8.dylib to use")
    parser.add_argument("--wav-dir",  required=True, type=Path,
                        help="Directory containing YYMMDD_HHMMSS.wav capture files")
    parser.add_argument("--out",      required=True, type=Path,
                        help="Output path for the generated ALL.TXT")
    parser.add_argument("--freq-mhz", type=float, default=14.074,
                        help="RF frequency in MHz for the ALL.TXT header (default: 14.074)")
    args = parser.parse_args()

    if not args.wav_dir.is_dir():
        sys.exit(f"ERROR: --wav-dir is not a directory: {args.wav_dir}")

    print("=" * 60)
    print("OpenWSFZ batch decoder")
    print("=" * 60)

    lib = _load_dll(args.dll)

    wav_files = sorted(args.wav_dir.glob("*.wav"))
    if not wav_files:
        sys.exit(f"ERROR: no .wav files found in {args.wav_dir}")
    print(f"\n  WAV files : {len(wav_files)} ({wav_files[0].stem} → {wav_files[-1].stem})")
    print(f"  Output    : {args.out}")
    print()

    total_decodes = 0
    skipped       = 0
    lines: list[str] = []

    for i, wav_path in enumerate(wav_files, 1):
        timestamp = wav_path.stem  # e.g. "260607_115545"
        print(f"  [{i:3d}/{len(wav_files)}] {timestamp} ...", end=" ", flush=True)

        samples = _read_wav_as_float32(wav_path)
        if samples is None:
            skipped += 1
            continue

        results = _decode_wav(lib, samples)
        for r in results:
            lines.append(_format_line(timestamp, args.freq_mhz, r))
        total_decodes += len(results)
        print(f"{len(results):3d} decodes")

    print()
    print(f"  Total decodes : {total_decodes}")
    print(f"  Skipped files : {skipped}")

    args.out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"  Written       : {args.out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
