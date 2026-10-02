#!/usr/bin/env python
"""Offline flag-OFF/ON replay: build and freeze the cycle list (selection.json).

Spec: qa/rr-study/2026-10-01-1935-architect-to-qa-spec-sub-feas-offline-onoff-replay.md, section 3.

  Included  = every archived WAV of the on-air night that passes R0, EXCEPT the first and last stamps of the window.
  R0 (per file, as in the harness) = RIFF/WAVE, mono, 12 000 Hz, 16-bit, exactly 180 000 samples.
  NOT excluded: cycles where WSJT-X logged 0 decodes (excluding on the reference would be a selection on the outcome)
                and clipped WAVs (both arms hear the same audio).
  Warm-up   = the FIRST stamp (an excluded edge cycle), decoded and discarded at every process start by the harness.
  V6 list   = the first 160 INCLUDED cycles (the ON-repeat of row V6).

Excluded cycles are counted by reason inside selection.json. The file is deterministic (sorted keys, fixed indentation, LF),
and its SHA-256 is pinned in onoff_replay_run.py and asserted before every run. No decode happens here: only the 44-byte
WAV headers are read. stamps are cycle timestamps; no message text, callsign or ALL.TXT content is read or written (HK-037).

  python qa/rr-study/sub-feas/select_onoff.py            # writes selection.json, prints its SHA-256
  OPENWSFZ_ARTEFACTS=<dir> overrides the artefacts directory (gitignored data does not travel between worktrees).
"""
import hashlib
import json
import os
import re
import struct
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ART = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
RUN = "20260930_1930"
WAV_DIR = os.path.join(ART, f"{RUN}_endurance_run", "cycle-audio")
OUT_DIR = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-01-sub-feas-offline-onoff-replay")
SELECTION = os.path.join(OUT_DIR, "selection.json")
STAMP = re.compile(r"^\d{6}_\d{6}$")
PCM_SAMPLES = 180_000
SAMPLE_RATE_HZ = 12_000
V6_CYCLES = 160   # spec section 6, row V6


def r0_ok(path):
    """The harness's own per-file assertion (Program.cs ReadWav): 12 kHz mono 16-bit, exactly 180 000 samples."""
    with open(path, "rb") as fh:
        b = fh.read()
    if len(b) < 44 or b[0:4] != b"RIFF" or b[8:12] != b"WAVE":
        return False, "not_riff_wave"
    pos, channels, rate, bits, data_len = 12, 0, 0, 0, -1
    while pos + 8 <= len(b):
        cid = b[pos:pos + 4]
        (clen,) = struct.unpack_from("<i", b, pos + 4)
        if cid == b"fmt ":
            channels = struct.unpack_from("<h", b, pos + 10)[0]
            rate = struct.unpack_from("<i", b, pos + 12)[0]
            bits = struct.unpack_from("<h", b, pos + 22)[0]
        elif cid == b"data":
            data_len = clen
            break
        pos += 8 + clen + (clen & 1)
    if channels != 1 or rate != SAMPLE_RATE_HZ or bits != 16 or data_len < 0 or data_len // 2 != PCM_SAMPLES:
        return False, f"format ch={channels} rate={rate} bits={bits} samples={data_len // 2 if data_len >= 0 else -1}"
    return True, ""


def build():
    stamps = sorted(f[:-4] for f in os.listdir(WAV_DIR) if f.endswith(".wav"))
    bad_name = [s for s in stamps if not STAMP.match(s)]
    assert not bad_name, f"unexpected file names: {len(bad_name)}"
    assert len(stamps) >= 3, "too few cycles"
    first, last = stamps[0], stamps[-1]
    included, r0_failed = [], []
    for s in stamps[1:-1]:
        ok, why = r0_ok(os.path.join(WAV_DIR, s + ".wav"))
        (included if ok else r0_failed).append(s)
    assert included == sorted(included)
    sel = {
        "spec": "qa/rr-study/2026-10-01-1935-architect-to-qa-spec-sub-feas-offline-onoff-replay.md section 3",
        "run": RUN,
        "source_dir": f"artefacts/{RUN}_endurance_run/cycle-audio",
        "counts": {
            "wav_files": len(stamps),
            "excluded_window_edge": 2,
            "excluded_r0_failed": len(r0_failed),
            "included": len(included),
            "v6_cycles": min(V6_CYCLES, len(included)),
        },
        "excluded": {"window_edge": [first, last], "r0_failed": r0_failed},
        "runs": {RUN: {"warmup": first, "ALL": included, "V6": included[:V6_CYCLES]}},
    }
    return sel


def serialise(sel):
    return (json.dumps(sel, indent=1, sort_keys=True) + "\n").encode("utf-8")


def main():
    sel = build()
    data = serialise(sel)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SELECTION, "wb") as fh:
        fh.write(data)
    sha = hashlib.sha256(data).hexdigest()
    c = sel["counts"]
    print(f"wrote {SELECTION}")
    print(f"wav files {c['wav_files']}: edge excluded {c['excluded_window_edge']}, R0 failed {c['excluded_r0_failed']}, "
          f"included {c['included']}, V6 list {c['v6_cycles']}")
    print(f"first included {sel['runs'][RUN]['ALL'][0]}  last included {sel['runs'][RUN]['ALL'][-1]}  warm-up {sel['runs'][RUN]['warmup']}")
    print(f"selection.json sha256 {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
