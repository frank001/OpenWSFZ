#!/usr/bin/env python3
"""COH-MULTISET step 2: freeze the cycle selection (spec section 4 + Amendment 1 / A1.7). No audio is decoded here and no ALL.TXT text is read.

Night 20261022_1949 (Windows PC, Voicemeeter chain, 40 m). Accepted by the Architect 2026-10-24 (message after 12:47Z); WAV source owsfz/wav, for parity with COH-GAIN.

  ordered list  = the stamps that exist in BOTH owsfz/wav and wsjt-x/wav, sorted ascending         (index i = position in that list)
  sample        = every cycle with i mod 3 == 1                                                    (k = 3, odd, so both TX-period parities occur)
  pilot         = the first 100 cycles with i mod 3 == 2                                           (disjoint; used ONLY for the counted half-width, timing and the delta check;
                                                                                                   never pooled with the sample)
  Q-GATE-2      = even/odd slot counts of the sample, within 2 % of each other (slot parity = (second // 15) % 2 of the stamp)

HK-037 / NFR-021: only cycle stamps (timestamps) and counts are persisted. Nothing here opens a message.

  python qa/rr-study/coh-multiset/ms_select.py            # writes selection.json and prints its sha256(LF)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ART = os.environ.get("OPENWSFZ_ARTEFACTS", "D:/Projects/claude/OpenWSFZ/artefacts")
RUN = "20261022_1949"
GATHERED = os.path.join(ART, f"{RUN}_endurance_run-gathered")
OWS_WAV = os.path.join(GATHERED, "owsfz", "wav")
WS_WAV = os.path.join(GATHERED, "wsjt-x", "wav")
WS_ALLTXT = os.path.join(GATHERED, "wsjt-x", "ALL.TXT")
OUT_DIR = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-24-coh-multiset")
OUT = os.path.join(OUT_DIR, "selection.json")

# Constants as assertions in the code, not prose (Architect Amendment 1 / A1.7).
MODULUS = 3
SAMPLE_RESIDUE = 1
PILOT_RESIDUE = 2
PILOT_CYCLES = 100
MIN_SAMPLE_CYCLES = 600
QGATE2_MAX_RELATIVE_DIFF = 0.02
SLOT_SECONDS = 15
assert (SAMPLE_RESIDUE, PILOT_RESIDUE, MODULUS) == (1, 2, 3) and SAMPLE_RESIDUE != PILOT_RESIDUE


def stamps(wav_dir):
    return sorted(f[:-4] for f in os.listdir(wav_dir) if f.lower().endswith(".wav"))


def slot_parity(stamp):
    """Stamp 'YYMMDD_HHMMSS' -> 0 for the :00/:30 slots, 1 for the :15/:45 slots."""
    sec = int(stamp[-2:])
    assert sec % SLOT_SECONDS == 0, stamp
    return (sec // SLOT_SECONDS) % 2


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build():
    ows, ws = set(stamps(OWS_WAV)), set(stamps(WS_WAV))
    common = sorted(ows & ws)
    sample = [(i, s) for i, s in enumerate(common) if i % MODULUS == SAMPLE_RESIDUE]
    pilot = [(i, s) for i, s in enumerate(common) if i % MODULUS == PILOT_RESIDUE][:PILOT_CYCLES]
    assert len(sample) >= MIN_SAMPLE_CYCLES and len(pilot) == PILOT_CYCLES
    assert {i for i, _ in sample}.isdisjoint({i for i, _ in pilot})
    par = [slot_parity(s) for _, s in sample]
    even, odd = par.count(0), par.count(1)
    rel = abs(even - odd) / max(even, odd)
    return {
        "spec": "qa/rr-study/2026-10-24-1240-architect-to-qa-spec-coh-multiset.md (arch/coh-multiset) section 4 + Amendment 1",
        "night": RUN, "wav_source": "owsfz/wav",
        "wsjtx_alltxt_sha256": file_sha256(WS_ALLTXT),
        "rule": {"ordered_list": "stamps present in both owsfz/wav and wsjt-x/wav, ascending", "sample": "index mod 3 == 1",
                 "pilot": "first 100 cycles with index mod 3 == 2; never pooled with the sample"},
        "counts": {"owsfz_wavs": len(ows), "wsjtx_wavs": len(ws), "common_cycles": len(common), "ows_only": len(ows - ws), "wsjtx_only": len(ws - ows),
                   "sample_cycles": len(sample), "pilot_cycles": len(pilot), "sample_even_slots": even, "sample_odd_slots": odd},
        "q_gate_2": {"relative_difference": round(rel, 6), "limit": QGATE2_MAX_RELATIVE_DIFF, "pass": bool(rel <= QGATE2_MAX_RELATIVE_DIFF)},
        "sample": [[i, s] for i, s in sample],
        "pilot": [[i, s] for i, s in pilot],
    }


def main():
    spec = build()
    data = (json.dumps(spec, indent=0, sort_keys=True) + "\n").encode("utf-8")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "wb") as fh:
        fh.write(data)
    print("wrote", OUT)
    print(spec["counts"])
    print("Q-GATE-2", spec["q_gate_2"])
    print("selection.json sha256(LF)", hashlib.sha256(data).hexdigest())
    return 0 if spec["q_gate_2"]["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
