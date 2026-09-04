#!/usr/bin/env python3
"""
FP-REGRESSION -- E2: ROW 0a, the instrument-sensitivity gate.

Spec: qa/rr-study/2026-09-04-1432-architect-to-qa-spec-fp-regression-bisect.md, section 4, ROW 0a.
Pack: qa/rr-study/2026-09-04-1441-architect-to-qa-execution-pack-fp-regression.md, E2.

Decodes the full frozen 4,000-slot M1 S5 AWGN corpus through B1 (pre-regression, 3bd4cd0,
2026-08-05, last 0/120 in-chain sweep) and through B8 (post-step, c3a9ea8/f5dec23, 2026-08-22,
4/120 in-chain sweep), paired -- same WAVs through both. Drives the raw exported C ABI directly
via ctypes (never Ft8LibInterop's managed wrapper -- that hard-codes ExpectedShimVersion=20260050
at compile time and throws on any older binary before a decode call is reachable, a structural
obstacle already disclosed for ROW 0r; see tests/OpenWSFZ.Ft8.Tests/Row0rCarryForwardTests.cs).

Reuses the population and the WAV normalisation convention of the canonical harness
(tests/OpenWSFZ.Ft8.Tests/WavReader.cs: int16 -> float32, divided by 32768.0 -- NOT the raw
unnormalised int16 magnitude some other ctypes harnesses in this repo use for a different,
live-audio pipeline) so this instrument matches the one that produced the already-established
10.875% / 435-event-slot offline replay rate this arm's spec cites. AP bits disabled (mirrors
Ft8LibInterop.SetApBits([], [])); decode params left at native compiled defaults (10, 0.10, 60,
identical across B1..B8 per every shim header's own doc comment) -- the candidate-budget family
stays closed (spec sec.0), so nothing here may tune it.

FIRES iff the paired difference (B8 - B1) in offline false-accept rate is <= 0.
Signed difference reported, never |delta| (HK-021(l)). Paired 95% CI via the closed-form Wald
formula for the difference of paired proportions (HK-021(o): a readout quantum, not a bootstrap SE).

Usage:
    python row0a_instrument_sensitivity.py --dll-b1 <path> --dll-b8 <path> [--corpus <dir>] [--out <dir>]
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import math
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS = REPO_ROOT / "qa" / "rr-study" / "awgn-fp-replay" / "_work" / "m1m4_s5"
DEFAULT_OUT = Path(__file__).resolve().parent / "results"

# Pre-registered manifest values (pack E1.1), re-asserted here independently before either binary
# decodes anything. A mismatch is STOP, not a note.
EXPECTED_SHA256 = {
    "B1": "f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015",
    "B8": "bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f",
}

SLOT_RE = re.compile(r"^(?P<scenario>[A-Za-z0-9]+)_p(?P<part>\d+)_t(?P<trial>\d+)_s(?P<seed>\d+)\.wav$")

BUFFER_SAMPLES = 180_000
MAX_RESULTS = 340  # matches Ft8LibInterop.MaxResults (140 + 200 two-pass capacity), not p23's 200


class FT8Result(ctypes.Structure):
    _fields_ = [
        ("freq_hz", ctypes.c_int),
        ("dt", ctypes.c_float),
        ("snr", ctypes.c_int),
        ("message", ctypes.c_char * 36),
    ]


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Decoder:
    """Raw ctypes binding to the exported ABI, independent of Ft8LibInterop's compile-time
    ExpectedShimVersion self-test (that constant is fixed at 20260050 in the CURRENT managed
    assembly and would throw before any decode call is reachable for either B1 or B8, both
    older). ABI stability across B1..B8 confirmed by direct git-history read of ft8_shim.h at
    both endpoints (3bd4cd0, c3a9ea8): identical FT8Result layout, identical ft8_decode_all /
    ft8_set_ap_bits / ft8_lib_version_check signatures throughout."""

    def __init__(self, path: Path, expected_sha256: str, label: str):
        actual = sha256_of_file(path)
        if actual != expected_sha256:
            raise RuntimeError(
                f"{label}: SHA256 mismatch -- expected {expected_sha256}, got {actual}. "
                f"STOP per pack E1.1 -- do not decode with an unverified binary."
            )
        self.label = label
        self.sha256 = actual
        self.dll = ctypes.CDLL(str(path))
        d = self.dll
        d.ft8_lib_version_check.restype = ctypes.c_int
        d.ft8_set_ap_bits.argtypes = [
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_int,
        ]
        d.ft8_decode_all.restype = ctypes.c_int
        d.ft8_decode_all.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.c_int,
            ctypes.POINTER(FT8Result), ctypes.c_int,
        ]
        self.shim_version = d.ft8_lib_version_check()
        # Mirrors Ft8LibInterop.SetApBits([], []): both counts 0, non-null 1-byte buffers.
        zero_buf = (ctypes.c_uint8 * 1)(0)
        d.ft8_set_ap_bits(zero_buf, 0, zero_buf, 0)
        self._results = (FT8Result * MAX_RESULTS)()

    def decode(self, pcm) -> list[dict]:
        buf = (ctypes.c_float * len(pcm))(*pcm)
        n = self.dll.ft8_decode_all(buf, len(pcm), self._results, MAX_RESULTS)
        if n < 0:
            raise RuntimeError(f"{self.label}: native decode returned {n} (SEH-caught AV)")
        out = []
        for i in range(n):
            r = self._results[i]
            out.append({
                "message": r.message.decode("ascii", "replace").rstrip("\x00").strip(),
                "freq_hz": r.freq_hz,
                "dt_s": r.dt,
                "reported_snr_db": r.snr,
            })
        return out


def read_wav_normalised(path: Path) -> list[float]:
    """Mirrors tests/OpenWSFZ.Ft8.Tests/WavReader.cs exactly: 12 kHz mono 16-bit PCM ->
    float32, each sample divided by 32768.0 (NOT raw int16 magnitude -- a different ctypes
    harness elsewhere in this repo uses unnormalised magnitude for a separate live-audio
    RMS-scaling pipeline; using that convention here would desynchronise this instrument from
    the already-established 10.875%/435-event-slot offline replay rate this arm cites)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"not a RIFF/WAVE file: {path}")
    pos = 12
    fmt = None
    pcm_bytes = None
    while pos + 8 <= len(data):
        chunk_id = data[pos:pos + 4]
        chunk_size = struct.unpack_from("<I", data, pos + 4)[0]
        body_start = pos + 8
        if chunk_id == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", data, body_start)
        elif chunk_id == b"data":
            pcm_bytes = data[body_start:body_start + chunk_size]
        pos = body_start + chunk_size + (chunk_size % 2)
    if fmt is None or pcm_bytes is None:
        raise ValueError(f"missing fmt/data chunk: {path}")
    audio_format, channels, sample_rate, _byte_rate, _block_align, bits_per_sample = fmt
    if (audio_format, channels, sample_rate, bits_per_sample) != (1, 1, 12000, 16):
        raise ValueError(f"unexpected WAV format {fmt} in {path}")
    n_samples = len(pcm_bytes) // 2
    samples = struct.unpack_from(f"<{n_samples}h", pcm_bytes, 0)
    pcm = [s / 32768.0 for s in samples]
    if len(pcm) < BUFFER_SAMPLES:
        pcm = pcm + [0.0] * (BUFFER_SAMPLES - len(pcm))
    elif len(pcm) > BUFFER_SAMPLES:
        pcm = pcm[:BUFFER_SAMPLES]
    return pcm


def csv_escape(s: str) -> str:
    if "," in s or '"' in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def decode_corpus(decoder: Decoder, wav_dir: Path, out_dir: Path, label: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(
        (p for p in wav_dir.glob("*.wav") if SLOT_RE.match(p.name)),
        key=lambda p: p.name,  # ordinal string sort, matches StringComparer.Ordinal
    )
    slots_path = out_dir / f"row0a_{label}_slots.csv"
    decodes_path = out_dir / f"row0a_{label}_decodes.csv"
    slot_events: dict[tuple, int] = {}  # (part, trial, seed) -> n_decodes
    with open(slots_path, "w", encoding="utf-8", newline="") as sf, \
         open(decodes_path, "w", encoding="utf-8", newline="") as df:
        sf.write("scenario,part,trial,seed,n_decodes\r\n")
        df.write("scenario,part,trial,seed,message,freq_hz,dt_s,reported_snr_db\r\n")
        for i, path in enumerate(files):
            m = SLOT_RE.match(path.name)
            scenario, part, trial, seed = m["scenario"], int(m["part"]), int(m["trial"]), int(m["seed"])
            pcm = read_wav_normalised(path)
            decodes = decoder.decode(pcm)
            sf.write(f"{scenario},{part},{trial},{seed},{len(decodes)}\r\n")
            for d in decodes:
                df.write(",".join([
                    scenario, str(part), str(trial), str(seed),
                    csv_escape(d["message"]), str(d["freq_hz"]),
                    f"{d['dt_s']:.3f}", str(d["reported_snr_db"]),
                ]) + "\r\n")
            slot_events[(part, trial, seed)] = len(decodes)
            if (i + 1) % 500 == 0:
                print(f"  [{label}] {i + 1}/{len(files)} decoded", file=sys.stderr, flush=True)
    print(f"[{label}] wrote {slots_path.name}, {decodes_path.name}; {len(files)} slots")
    return slot_events


def paired_stats(events_b1: dict, events_b8: dict):
    keys = sorted(set(events_b1) & set(events_b8))
    n = len(keys)
    n11 = n10 = n01 = n00 = 0
    for k in keys:
        e1 = events_b1[k] > 0
        e8 = events_b8[k] > 0
        if e1 and e8:
            n11 += 1
        elif e1 and not e8:
            n10 += 1
        elif (not e1) and e8:
            n01 += 1
        else:
            n00 += 1
    rate_b1 = (n11 + n10) / n
    rate_b8 = (n11 + n01) / n
    diff = rate_b8 - rate_b1  # signed: B8 - B1, never |diff|
    # Wald CI for the difference of paired proportions (closed-form, HK-021(o) -- no bootstrap).
    var = (n01 + n10 - (n01 - n10) ** 2 / n) / (n ** 2)
    se = math.sqrt(var) if var > 0 else 0.0
    ci_lo, ci_hi = diff - 1.96 * se, diff + 1.96 * se
    return {
        "n": n, "n11": n11, "n10": n10, "n01": n01, "n00": n00,
        "rate_b1": rate_b1, "rate_b8": rate_b8,
        "diff": diff, "se": se, "ci95": (ci_lo, ci_hi),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-b1", required=True, type=Path)
    ap.add_argument("--dll-b8", required=True, type=Path)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=None, help="debug only: decode first N files")
    args = ap.parse_args()

    print("=== E2 -- ROW 0a, instrument-sensitivity gate ===")
    print(f"Corpus: {args.corpus}")

    dec_b1 = Decoder(args.dll_b1, EXPECTED_SHA256["B1"], "B1")
    print(f"B1: {args.dll_b1.name}  SHA256={dec_b1.sha256}  shim_version={dec_b1.shim_version}")
    dec_b8 = Decoder(args.dll_b8, EXPECTED_SHA256["B8"], "B8")
    print(f"B8: {args.dll_b8.name}  SHA256={dec_b8.sha256}  shim_version={dec_b8.shim_version}")

    files = sorted(p for p in args.corpus.glob("*.wav") if SLOT_RE.match(p.name))
    if args.limit:
        # Debug path only -- writes into a _debug subdir so a partial run can never be mistaken
        # for the full 4,000-slot population's committed result.
        tmp_dir = args.corpus.parent / "_debug_limit"
        tmp_dir.mkdir(exist_ok=True)
        for p in files[: args.limit]:
            dst = tmp_dir / p.name
            if not dst.exists():
                dst.write_bytes(p.read_bytes())
        wav_dir = tmp_dir
        out_dir = args.out / "_debug"
    else:
        wav_dir = args.corpus
        out_dir = args.out

    events_b1 = decode_corpus(dec_b1, wav_dir, out_dir, "B1")
    events_b8 = decode_corpus(dec_b8, wav_dir, out_dir, "B8")

    stats = paired_stats(events_b1, events_b8)

    print()
    print("=== ROW 0a result ===")
    print(f"n = {stats['n']}")
    print(f"n11 (both fire) = {stats['n11']}  n10 (B1 only) = {stats['n10']}  "
          f"n01 (B8 only) = {stats['n01']}  n00 (neither) = {stats['n00']}")
    print(f"rate(B1) = {stats['rate_b1']*100:.4f}%  ({stats['n11']+stats['n10']}/{stats['n']})")
    print(f"rate(B8) = {stats['rate_b8']*100:.4f}%  ({stats['n11']+stats['n01']}/{stats['n']})")
    print(f"signed diff (B8 - B1) = {stats['diff']*100:+.4f} pp")
    print(f"paired 95% CI = [{stats['ci95'][0]*100:+.4f}, {stats['ci95'][1]*100:+.4f}] pp")
    print()
    predicate = stats["diff"] <= 0
    print("Predicate: FIRES iff (B8 - B1) <= 0")
    print(f"ROW 0a VERDICT: {'FIRES -- STOP, bisect void' if predicate else 'DOES NOT FIRE -- offline instrument is responsive'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
