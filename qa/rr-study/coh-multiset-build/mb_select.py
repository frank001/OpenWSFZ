#!/usr/bin/env python3
"""COH-MULTISET-BUILD replay (Architect spec section 6.1, A1.1): freeze the cycle selection BEFORE any decode of any arm.

Night 20260925_2010 (Windows PC, direct-USB chain, pre-Voicemeeter, 40 m), WHOLE night, no sampling (CPU projection ~5.4 h for REF + MS + MS-repeat is under the spec's 8 h).
WAV source owsfz/wav. The ordered list = the stamps present in BOTH owsfz/wav and wsjt-x/wav; the Replay81 stratum 'FULL' = every one of them; 'warmup' = the first stamp.
Only stamps and counts are persisted; no ALL.TXT line is read here (HK-037). Stamps are timestamps.

  python qa/rr-study/coh-multiset-build/mb_select.py        # writes selection.json, prints its sha256(LF)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RUN = "20260925_2010"
ART = os.environ.get("OPENWSFZ_ARTEFACTS", "D:/Projects/claude/OpenWSFZ/artefacts")
G = os.path.join(ART, f"{RUN}_endurance_run-gathered")
OUT_DIR = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-24-coh-multiset-build")
OUT = os.path.join(OUT_DIR, "selection.json")


def stamps(d):
    return sorted(f[:-4] for f in os.listdir(d) if f.lower().endswith(".wav"))


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ows, ws = set(stamps(os.path.join(G, "owsfz", "wav"))), set(stamps(os.path.join(G, "wsjt-x", "wav")))
    common = sorted(ows & ws)
    assert len(common) > 2000
    spec = {
        "note": "COH-MULTISET-BUILD replay: whole night, owsfz/wav; Replay81 selection format",
        "run": RUN, "wav_source": "owsfz/wav", "chain": "direct USB codec, pre-Voicemeeter, Windows PC",
        "wsjtx_alltxt_sha256": sha(os.path.join(G, "wsjt-x", "ALL.TXT")),
        "counts": {"owsfz_wavs": len(ows), "wsjtx_wavs": len(ws), "common_cycles": len(common), "ows_only": len(ows - ws), "wsjtx_only": len(ws - ows)},
        "runs": {RUN: {"warmup": common[0], "FULL": common}},
    }
    data = (json.dumps(spec, indent=0, sort_keys=True) + "\n").encode("utf-8")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "wb") as fh:
        fh.write(data)
    print(spec["counts"])
    print("selection.json sha256(LF)", hashlib.sha256(data).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
