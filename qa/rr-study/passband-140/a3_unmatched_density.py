#!/usr/bin/env python3
"""PASSBAND-140 A3: what the operator would see in the new band.

Spec section 3.5 A3: W40's post-chain decodes on C2 with freq_hz in
[137.5, 200): count, share REF-matched, share unmatched. Unmatched density
(unmatched decodes per 6.25 Hz bin per 100 cycles) in the new band, against
B40's in-band unmatched density. If the ratio exceeds 3, flag to the
Architect the same day, before any ship dev-task is written.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_HERE, "..", "live-gap-now"))
sys.path.append(os.path.join(_HERE, "..", "..", "cycleframer-alignment-replay"))

import dll_pin  # noqa: E402
import corpus  # noqa: E402
import matcher  # noqa: E402
from h1_hash_token_contamination import load as load_all_txt  # noqa: E402

REPO_ROOT = dll_pin.REPO_ROOT
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "passband-140", "_out")
DIAL_PREFIX = "14.074"
C2_REF_PATH = os.path.join(
    REPO_ROOT, "artefacts", "20260908_live_run_1827-fp-floor-live-2",
    "wsjtx-1-ft991a", "ALL.TXT")
C2_LO, C2_HI = "260908_193645", "269999_999999"

LOW_LO, LOW_HI = 137.5, 200.0   # new band, [137.5, 200)
IN_LO, IN_HI = 200.0, 2959.0    # existing in-band (B40's own baseline density)
BIN_HZ = 6.25


def load_chained(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            ts = rec["ts"]
            for r in rec["results"]:
                out[(ts, r["message"])] = (r["snr"], r["freq_hz"])
    return out


def matched_ows_keys(ref, ows):
    """The set of OWS (ts,msg) keys that count as 'matched' -- either an
    exact REF hit, or one of the wildcard-gained candidates for some REF row."""
    rec = matcher.recovery(ows, ref)
    matched = set(rec["exact_matched"])  # these ARE both REF and OWS keys (same tuple)
    for ref_key, cand_msgs in rec["gained"].items():
        ts = ref_key[0]
        for m in cand_msgs:
            matched.add((ts, m))
    return matched


def main():
    c2_ts, _ = corpus.c2_cycles()
    c2_ts = {ts for ts, _ in c2_ts}
    n_cycles = len(c2_ts)

    all_ref = load_all_txt(C2_REF_PATH, C2_LO, C2_HI, DIAL_PREFIX)
    ref = {k: v for k, v in all_ref.items() if k[0] in c2_ts}

    b40 = load_chained(os.path.join(OUT_DIR, "B40_C2_chained.jsonl"))
    w40 = load_chained(os.path.join(OUT_DIR, "W40_C2_chained.jsonl"))

    b40_matched = matched_ows_keys(ref, b40)
    w40_matched = matched_ows_keys(ref, w40)

    w40_low = [(k, v) for k, v in w40.items() if LOW_LO <= v[1] < LOW_HI]
    b40_in = [(k, v) for k, v in b40.items() if IN_LO <= v[1] < IN_HI]

    w40_low_matched = sum(1 for k, v in w40_low if k in w40_matched)
    w40_low_unmatched = len(w40_low) - w40_low_matched
    b40_in_matched = sum(1 for k, v in b40_in if k in b40_matched)
    b40_in_unmatched = len(b40_in) - b40_in_matched

    print("W40 post-chain decodes, C2, freq in [%.1f, %.1f): %d" % (LOW_LO, LOW_HI, len(w40_low)))
    print("  matched (exact or wildcard-gained): %d (%.2f%%)" %
          (w40_low_matched, 100.0 * w40_low_matched / len(w40_low) if w40_low else float("nan")))
    print("  unmatched: %d (%.2f%%)" %
          (w40_low_unmatched, 100.0 * w40_low_unmatched / len(w40_low) if w40_low else float("nan")))

    n_bins_low = (LOW_HI - LOW_LO) / BIN_HZ
    n_bins_in = (IN_HI - IN_LO) / BIN_HZ
    density_low = w40_low_unmatched / n_bins_low / (n_cycles / 100.0)
    density_in = b40_in_unmatched / n_bins_in / (n_cycles / 100.0)
    ratio = density_low / density_in if density_in else float("inf")

    print()
    print("new-band (W40, [137.5,200)): %d bins, unmatched density = %.4f per bin per 100 cycles" %
          (n_bins_low, density_low))
    print("in-band  (B40, [200,2959)): %d bins, unmatched density = %.4f per bin per 100 cycles" %
          (n_bins_in, density_in))
    print("ratio = %.4f" % ratio)
    print("FLAG (ratio > 3)?" , "YES -- flag to the Architect before any ship dev-task" if ratio > 3 else "no")


if __name__ == "__main__":
    main()
