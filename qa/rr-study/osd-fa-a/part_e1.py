#!/usr/bin/env python3
"""OSD-FA-A Part E1 (Amendment 1 sec.5.1) -- D-009 Option B's FP benefit on noise.

HK-020: population = the 4,000 M1 S5 AWGN slots (same population as Part 0), through
the PRODUCTION input contract. That contract is (verified directly against source, not
assumed):
  Ft8Decoder.cs:271 WavReader.Read (int16/32768 -> [-1,1]) then NormalisePcm(pcm, 0.20)
  (Ft8Decoder.cs:52 PcmNormalisationTargetRms=0.20f, :51 SilenceRmsThreshold=1e-6f).
This is mathematically identical to part_d.read_wav_normalised's own convention (raw
int16 magnitude, then RMS-rescale to the same 0.20 target) -- normalise_rms(pcm, t) =
pcm * t/rms(pcm) is scale-invariant to the caller's own choice of intermediate units,
so int16-then-normalise and (int16/32768)-then-normalise produce IDENTICAL output.
Reused here rather than reimplemented (HK-018), and the equivalence is disclosed rather
than assumed.

Two legs, nhard 60 and 40, SAME SESSION (one process, one decoder instance), paired by
slot -- decode each slot at 60, then again at 40, immediately, before moving to the next
slot (Amendment 1 sec.5.1: "Two legs ... same session, paired by slot").

Event = slot with >=1 decode -- COUNT-BASED ONLY. Message text plays no part (Amendment
1 sec.5.1's own instruction, avoiding the session-hash-table-history confound this whole
arm has repeatedly hit) -- decode results are discarded immediately after len() is read;
no text is ever stored.

Statistic: r = event at 60, none at 40. a = the reverse. Exact two-sided McNemar,
reusing fp-parity/p3_parity.py's own binomtest(min(r,a), r+a, p=0.5, "two-sided")
convention (HK-018).

No +0.16 offset -- runs the full decoder, extracts nothing.

NFR-021: not engaged -- AWGN noise-only population (Part 0's own scope note), and this
leg never even reads message text (count-based only).

Usage:
    python part_e1.py <out_json>
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)

import dll_pin as P  # noqa: E402
from row0_bc import bind_decode_params  # noqa: E402
from part_d import read_wav_normalised  # noqa: E402
from scipy.stats import binomtest  # noqa: E402

POP_DIR = r"D:\Projects\claude\OpenWSFZ\qa\rr-study\awgn-fp-replay\_work\m1m4_s5"
FNAME_RE = re.compile(r"^S5_p(\d+)_t(\d+)_s(\d+)\.wav$")

NHARD_TREATMENT = 40
NHARD_CONTROL = 60
K_MIN_SCORE_PASS2 = 10
OSD_CORR_THRESHOLD = 0.10


def main() -> int:
    out_json = sys.argv[1]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    if not os.path.isdir(POP_DIR):
        raise SystemExit(f"population directory not found: {POP_DIR}")
    files = sorted(fn for fn in os.listdir(POP_DIR) if FNAME_RE.match(fn))
    print(f"population: {len(files)} files (sorted filename order, same convention as "
          f"Part 0 -- lexicographic over variable-width trial indices)", flush=True)

    dec = P.load_decoder(verify=True)
    bind_decode_params(dec.dll)
    print(f"shim={dec.version}", flush=True)

    r = a = both = neither = 0
    n_60 = n_40 = 0

    t0 = time.perf_counter()
    for idx, fn in enumerate(files):
        pcm = read_wav_normalised(os.path.join(POP_DIR, fn))

        dec.dll.ft8_set_decode_params(K_MIN_SCORE_PASS2, OSD_CORR_THRESHOLD, NHARD_CONTROL)
        d60 = dec.decode_all(pcm)
        event_60 = bool(d60)

        dec.dll.ft8_set_decode_params(K_MIN_SCORE_PASS2, OSD_CORR_THRESHOLD, NHARD_TREATMENT)
        d40 = dec.decode_all(pcm)
        event_40 = bool(d40)

        if event_60:
            n_60 += 1
        if event_40:
            n_40 += 1
        if event_60 and not event_40:
            r += 1
        elif event_40 and not event_60:
            a += 1
        elif event_60 and event_40:
            both += 1
        else:
            neither += 1

        if (idx + 1) % 500 == 0:
            print(f"  {idx + 1}/{len(files)} ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    n_disc = r + a
    p_value = binomtest(min(r, a), n_disc, p=0.5, alternative="two-sided").pvalue if n_disc else None

    if p_value is not None and p_value < 0.05 and r > a:
        row = "E1-1"
    else:
        row = "E1-2"

    out = {
        "n_slots": len(files), "n_60": n_60, "n_40": n_40, "r": r, "a": a,
        "both": both, "neither": neither, "n_discordant": n_disc, "p_value": p_value,
        "row": row, "nhard_control": NHARD_CONTROL, "nhard_treatment": NHARD_TREATMENT,
        "total_wall_s": total_wall,
    }
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    os.replace(tmp, out_json)

    print(f"DONE n_60={n_60} n_40={n_40} r={r} a={a} both={both} neither={neither} "
          f"p={p_value} ROW={row} wall={total_wall:.0f}s -> {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
