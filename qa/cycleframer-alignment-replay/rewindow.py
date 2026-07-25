#!/usr/bin/env python3
"""Alignment-replay re-windowing tool.

Implements SPEC.md section 5.1: groups a directory of WSJT-X 15-second WAV captures
into contiguous segments, concatenates each segment's PCM, and cuts new windows at an
arbitrary offset delta (seconds) from the original grid. Output windows are written as
standard 12 kHz mono 16-bit PCM WAVs plus a manifest.csv (wav,cycle_utc,...) consumable
by qa/rr-study/d001-param-sweep-2026-07-22's D001ParamSweep --manifest option, so the
existing decode harness can be reused UNMODIFIED (SPEC.md section 8).

This is "the one genuinely new capability" SPEC.md calls for; everything downstream
(decoding, scoring) reuses existing tooling.

HK-009: this machine's Python stdout is cp1252 -- reconfigure to UTF-8 up front.
NFR-021: output WAVs and manifests may contain/imply real third-party callsign audio;
callers MUST write all outputs under a git-ignored directory (see .gitignore in this
directory).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import wave
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SAMPLE_RATE = 12_000
WINDOW_SAMPLES = 180_000  # 15.000 s at 12 kHz -- Ft8Decoder's hard contract (ExpectedSamples)
GAP_SECONDS = 15.0        # contiguous inter-file spacing; anything else breaks a segment

HERE = Path(__file__).resolve().parent


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=HERE, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# WAV I/O
# ---------------------------------------------------------------------------

def read_wav_int16(path: Path) -> np.ndarray:
    """Read a 12 kHz mono 16-bit PCM WAV; return raw int16 samples, little-endian."""
    with wave.open(str(path), "rb") as w:
        fmt = (w.getnchannels(), w.getsampwidth(), w.getframerate())
        if fmt != (1, 2, SAMPLE_RATE):
            raise ValueError(
                f"{path}: unexpected format {fmt[0]}ch {fmt[1] * 8}bit {fmt[2]}Hz "
                f"(expected 1ch 16bit {SAMPLE_RATE}Hz)"
            )
        n = w.getnframes()
        if n != WINDOW_SAMPLES:
            raise ValueError(f"{path}: {n} frames (expected {WINDOW_SAMPLES})")
        data = w.readframes(n)
    arr = np.frombuffer(data, dtype="<i2")
    if len(arr) != WINDOW_SAMPLES:
        raise ValueError(f"{path}: decoded {len(arr)} samples (expected {WINDOW_SAMPLES})")
    return arr


def write_wav_int16(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(np.ascontiguousarray(arr, dtype="<i2").tobytes())


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

@dataclass
class WavEntry:
    path: Path
    ts: datetime  # UTC, from filename


@dataclass
class Segment:
    index: int
    entries: list  # list[WavEntry]

    @property
    def start(self) -> datetime:
        return self.entries[0].ts

    @property
    def end(self) -> datetime:
        return self.entries[-1].ts

    @property
    def n_files(self) -> int:
        return len(self.entries)


def parse_ts(stem: str) -> datetime:
    return datetime.strptime(stem, "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc)


def list_wavs(wav_dir: Path) -> list[WavEntry]:
    entries = []
    skipped = 0
    for p in sorted(wav_dir.glob("*.wav"), key=lambda p: p.name):
        try:
            ts = parse_ts(p.stem)
        except ValueError:
            skipped += 1
            continue
        entries.append(WavEntry(p, ts))
    if skipped:
        print(f"[list_wavs] skipped {skipped} file(s) with non-YYMMDD_HHMMSS names", file=sys.stderr)
    return entries


def find_segments(entries: list) -> list:
    """Group into contiguous segments: consecutive files exactly GAP_SECONDS apart.
    Any other gap (or same/earlier timestamp -- duplicate/out-of-order) breaks the segment."""
    segments = []
    cur: list = []
    for e in entries:
        if cur and (e.ts - cur[-1].ts).total_seconds() != GAP_SECONDS:
            segments.append(cur)
            cur = []
        cur.append(e)
    if cur:
        segments.append(cur)
    return [Segment(i, seg) for i, seg in enumerate(segments)]


def cmd_segments(args: argparse.Namespace) -> None:
    entries = list_wavs(Path(args.wav_dir))
    segs = find_segments(entries)
    rows = []
    for s in segs:
        rows.append({
            "segment_index": s.index,
            "n_files": s.n_files,
            "start": s.start.isoformat(),
            "end": s.end.isoformat(),
            "duration_s": (s.end - s.start).total_seconds() + GAP_SECONDS,
        })
        print(f"segment {s.index:3d}: {s.n_files:5d} files  {s.start.isoformat()} -> "
              f"{s.end.isoformat()}  ({rows[-1]['duration_s']:.0f}s)")
    total = sum(r["n_files"] for r in rows)
    print(f"TOTAL: {len(segs)} segments, {total} files ({len(entries)} listed, "
          f"{len(entries) - total} dropped as single-file/broken segments)")
    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=2))
        print(f"-> {args.out}")


# ---------------------------------------------------------------------------
# Re-windowing
# ---------------------------------------------------------------------------

def window_k_range(n_samples: int, base_offset: int) -> tuple[int, int]:
    """Inclusive [k_min, k_max] of window indices k such that the window
    [base_offset + k*W, base_offset + k*W + W) lies fully inside [0, n_samples)."""
    k_min = math.ceil(-base_offset / WINDOW_SAMPLES)
    k_max = math.floor((n_samples - WINDOW_SAMPLES - base_offset) / WINDOW_SAMPLES)
    return k_min, k_max


def cut_segment(seg_pcm: np.ndarray, delta_seconds: float,
                 k_start: int | None = None, k_end: int | None = None):
    """Yield (k, window_int16_array) for every full window at offset
    round(delta*SAMPLE_RATE) + k*WINDOW_SAMPLES, per SPEC.md 5.1 step 3."""
    base = round(delta_seconds * SAMPLE_RATE)
    k_min, k_max = window_k_range(len(seg_pcm), base)
    if k_start is not None:
        k_min = max(k_min, k_start)
    if k_end is not None:
        k_max = min(k_max, k_end)
    for k in range(k_min, k_max + 1):
        idx = base + k * WINDOW_SAMPLES
        yield k, seg_pcm[idx: idx + WINDOW_SAMPLES]


def concat_segment(seg: Segment) -> np.ndarray:
    arrs = [read_wav_int16(e.path) for e in seg.entries]
    return np.concatenate(arrs)


def window_label(seg: Segment, delta_seconds: float, k: int) -> datetime:
    return seg.start + timedelta(seconds=delta_seconds + GAP_SECONDS * k)


def fmt_ts(dt: datetime) -> str:
    # Millisecond precision, explicit UTC 'Z' -- DateTime.Parse(AssumeUniversal) compatible.
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def wav_name(delta_seconds: float, seg_idx: int, k: int) -> str:
    sign = "p" if delta_seconds >= 0 else "n"
    dtag = f"{sign}{abs(delta_seconds):04.2f}".replace(".", "")
    ktag = f"k{k:+06d}".replace("+", "p").replace("-", "n")
    return f"d{dtag}_seg{seg_idx:03d}_{ktag}.wav"


def do_rewindow(wav_dir: Path, out_dir: Path, delta_seconds: float,
                 segment_indices: list[int] | None, k_start: int | None, k_end: int | None,
                 clean: bool) -> tuple[Path, dict]:
    entries = list_wavs(wav_dir)
    segs = find_segments(entries)
    if segment_indices is not None:
        segs = [s for s in segs if s.index in segment_indices]
    if not segs:
        raise SystemExit("no segments selected (check --segment-index / source dir)")

    if clean and out_dir.exists():
        for f in out_dir.glob("*.wav"):
            f.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    sha = git_sha()
    for seg in segs:
        seg_pcm = concat_segment(seg)
        for k, window in cut_segment(seg_pcm, delta_seconds, k_start, k_end):
            label = window_label(seg, delta_seconds, k)
            name = wav_name(delta_seconds, seg.index, k)
            write_wav_int16(out_dir / name, window)
            manifest_rows.append({
                "wav": name,
                "cycle_utc": fmt_ts(label),
                "segment_index": seg.index,
                "k": k,
                "delta_s": delta_seconds,
                "source_wav_dir": str(wav_dir),
                "harness_git_sha": sha,
            })

    manifest_path = out_dir / "manifest.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(manifest_rows[0].keys()))
        wr.writeheader()
        wr.writerows(manifest_rows)

    provenance = {
        "source_wav_dir": str(wav_dir),
        "out_dir": str(out_dir),
        "delta_seconds": delta_seconds,
        "segment_indices": sorted(s.index for s in segs),
        "k_start": k_start, "k_end": k_end,
        "n_windows": len(manifest_rows),
        "harness_git_sha": sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2))
    return manifest_path, provenance


def cmd_rewindow(args: argparse.Namespace) -> None:
    seg_idx = None
    if args.segment_index is not None:
        seg_idx = [int(x) for x in args.segment_index.split(",")]
    manifest_path, prov = do_rewindow(
        Path(args.wav_dir), Path(args.out_dir), args.delta,
        seg_idx, args.k_start, args.k_end, args.clean,
    )
    print(f"rewindow: delta={args.delta}s segments={prov['segment_indices']} "
          f"windows={prov['n_windows']} -> {manifest_path}")


# ---------------------------------------------------------------------------
# Mandatory self-test (SPEC.md 5.1): delta=0 must reproduce source files
# sample-for-sample. Cheapest available guard against off-by-one/concat errors.
# ---------------------------------------------------------------------------

def cmd_selftest(args: argparse.Namespace) -> None:
    wav_dir = Path(args.wav_dir)
    entries = list_wavs(wav_dir)
    segs = find_segments(entries)
    if args.segment_index is not None:
        segs = [s for s in segs if s.index == args.segment_index]
    if not segs:
        raise SystemExit("no segments selected")

    failures = 0
    checked = 0
    for seg in segs:
        seg_pcm = concat_segment(seg)
        for k, window in cut_segment(seg_pcm, 0.0):
            original = read_wav_int16(seg.entries[k].path)
            checked += 1
            if not np.array_equal(window, original):
                failures += 1
                n_diff = int(np.count_nonzero(window != original))
                print(f"[FAIL] segment {seg.index} k={k} ({seg.entries[k].path.name}): "
                      f"{n_diff}/{WINDOW_SAMPLES} samples differ")

    if failures:
        print(f"SELF-TEST FAILED: {failures}/{checked} window(s) mismatched")
        sys.exit(1)
    print(f"SELF-TEST PASSED: {checked} windows, delta=0 reproduces source files "
          f"sample-for-sample across {len(segs)} segment(s)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("segments", help="list contiguous segments")
    sp.add_argument("--wav-dir", required=True)
    sp.add_argument("--out", default=None, help="optional segments.json output path")
    sp.set_defaults(fn=cmd_segments)

    sp = sub.add_parser("rewindow", help="cut new windows at offset --delta")
    sp.add_argument("--wav-dir", required=True)
    sp.add_argument("--out-dir", required=True)
    sp.add_argument("--delta", type=float, required=True, help="offset in seconds, e.g. 2.0 or -1.5")
    sp.add_argument("--segment-index", default=None, help="comma-separated segment indices (default: all)")
    sp.add_argument("--k-start", type=int, default=None)
    sp.add_argument("--k-end", type=int, default=None)
    sp.add_argument("--clean", action="store_true", help="remove existing *.wav in --out-dir first")
    sp.set_defaults(fn=cmd_rewindow)

    sp = sub.add_parser("selftest", help="mandatory delta=0 sample-for-sample self-test")
    sp.add_argument("--wav-dir", required=True)
    sp.add_argument("--segment-index", type=int, default=None, help="restrict to one segment (default: all)")
    sp.set_defaults(fn=cmd_selftest)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
