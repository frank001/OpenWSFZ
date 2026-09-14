#!/usr/bin/env python3
"""PASSBAND-140 ROW 0d: seam fidelity.

Spec section 3.2 ROW 0d: B60 through the chain vs C2's live openwsfz/ALL.TXT,
seam_fidelity(): F_live >= 0.97. Report F_rep (after the chain), and live
cycles with no WAV. NOT gated on F_rep (spec's own explanation, section
3.2 "why each row changes the verdict": F_rep's known excess is implausible
messages, which cannot enter R, and the residual -- cold hash state -- is
common to both legs, so gating it would VOID the arm over something that
cannot bias D).

Reuses live-gap-now's seam.py seam_fidelity() verbatim (spec section 0.5).
"""
from __future__ import annotations

import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "live-gap-now"))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "cycleframer-alignment-replay"))

import seam  # noqa: E402  (live-gap-now's own seam.py, reused verbatim)
from h1_hash_token_contamination import load as load_all_txt  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "passband-140", "_out")

LIVE_ALL_TXT = os.path.join(
    REPO_ROOT, "artefacts", "20260908_live_run_1827-fp-floor-live-2", "openwsfz", "ALL.TXT")
C2_AUDIO_MANIFEST = os.path.join(
    REPO_ROOT, "artefacts", "20260908_live_run_1827-fp-floor-live-2",
    "cycle-audio", "cycle-archive.csv")
C2_LO = "260908_193645"
C2_HI = "269999_999999"  # practical upper bound; corpus.c2_cycles() is the authority on the real set
DIAL_PREFIX = "14.074"


def load_chained_jsonl(path):
    """{leg}_C2_chained.jsonl -> {(ts,msg): (snr,freq_hz)}, mirroring
    h1_hash_token_contamination.load()'s own dict shape."""
    import json
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            ts = rec["ts"]
            for r in rec["results"]:
                out[(ts, r["message"])] = (r["snr"], r["freq_hz"])
    return out


def live_cycles_with_no_wav():
    """Live ALL.TXT cycles (ts values) in the C2 window that have no
    corresponding cycle-audio WAV, i.e. seam_fidelity() cannot possibly
    reproduce them (spec's own required disclosure for ROW 0d)."""
    live_ts = set()
    for (ts, _msg) in load_all_txt(LIVE_ALL_TXT, C2_LO, C2_HI, DIAL_PREFIX):
        live_ts.add(ts)

    wav_ts = set()
    with open(C2_AUDIO_MANIFEST, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            fn = row["filename"]
            if fn.endswith("_2.wav"):
                continue
            wav_ts.add(fn[:-4])

    return sorted(live_ts - wav_ts)


def main():
    b60_chained_path = os.path.join(OUT_DIR, "B60_C2_chained.jsonl")

    print("loading live C2 ALL.TXT (%s <= ts <= %s)..." % (C2_LO, C2_HI))
    live = load_all_txt(LIVE_ALL_TXT, C2_LO, C2_HI, DIAL_PREFIX)
    print("loading B60-through-chain replay...")
    replay = load_chained_jsonl(b60_chained_path)

    result = seam.seam_fidelity(live, replay)
    print("F_live = %.4f (%d/%d)" % (result["F_live"], result["n_live_matched"], result["n_live_total"]))
    print("F_rep  = %.4f (%d/%d)  (NOT gated -- reported only)" %
          (result["F_rep"], result["n_rep_matched"], result["n_rep_total"]))

    missing_wav = live_cycles_with_no_wav()
    print("live cycles with no WAV: %d" % len(missing_wav))
    if missing_wav:
        print("  first few:", missing_wav[:5])

    passed = result["F_live"] >= 0.97
    print("ROW 0d:", "PASS" if passed else "VOID (F_live < 0.97)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
