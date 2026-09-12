#!/usr/bin/env python3
"""LIVE-GAP-NOW corpora: cycle listing for C1 and C2 (spec section 1).

C1: artefacts/20260808_live_run_0016-8080/owsfz/wav/ -- window WINDOW_20M,
    2,529 cycles (H1's own window/count).
C2: artefacts/20260908_live_run_1827-fp-floor-live-2/cycle-audio/ -- cycles
    whose cycle_start_utc >= 2026-09-08T19:36:45Z and dial_mhz == 14.074, from
    cycle-archive.csv. Any *_2.wav duplicate-pipeline file is excluded.
"""
from __future__ import annotations

import csv
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

C1_DIR = os.path.join(REPO_ROOT, "artefacts", "20260808_live_run_0016-8080")
C1_WAV_DIR = os.path.join(C1_DIR, "owsfz", "wav")
C1_WINDOW = ("260808_004000", "260808_111500")  # WINDOW_20M, H1/p23_common

C2_DIR = os.path.join(REPO_ROOT, "artefacts", "20260908_live_run_1827-fp-floor-live-2")
C2_AUDIO_DIR = os.path.join(C2_DIR, "cycle-audio")
C2_MANIFEST = os.path.join(C2_AUDIO_DIR, "cycle-archive.csv")
C2_BOUNDARY_UTC = "2026-09-08T19:36:45"
C2_DIAL_MHZ = "14.074"


def c1_cycles():
    """Sorted list of (ts, wav_path) for C1's window."""
    lo, hi = C1_WINDOW
    out = []
    for fn in sorted(os.listdir(C1_WAV_DIR)):
        if not fn.endswith(".wav"):
            continue
        ts = fn[:-4]
        if lo <= ts <= hi:
            out.append((ts, os.path.join(C1_WAV_DIR, fn)))
    return out


def c2_cycles():
    """Sorted list of (ts, wav_path) for C2, plus a report of excluded *_2.wav
    duplicate-pipeline files (spec: "none is expected after the boundary; count
    and report them")."""
    out = []
    n_dup_excluded = 0
    n_dup_excluded_in_window = 0
    with open(C2_MANIFEST, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            fn = row["filename"]
            in_window = row["cycle_start_utc"] >= C2_BOUNDARY_UTC and row["dial_mhz"] == C2_DIAL_MHZ
            if fn.endswith("_2.wav"):
                n_dup_excluded += 1
                if in_window:
                    n_dup_excluded_in_window += 1
                continue
            if not in_window:
                continue
            ts = fn[:-4]
            out.append((ts, os.path.join(C2_AUDIO_DIR, fn)))
    out.sort(key=lambda t: t[0])
    return out, {"dup_excluded_total": n_dup_excluded, "dup_excluded_in_window": n_dup_excluded_in_window}


if __name__ == "__main__":
    c1 = c1_cycles()
    c2, dup_report = c2_cycles()
    print("C1: %d cycles, window %s..%s" % (len(c1), C1_WINDOW[0], C1_WINDOW[1]))
    print("C2: %d cycles, boundary %s.., dial %s" % (len(c2), C2_BOUNDARY_UTC, C2_DIAL_MHZ))
    print("C2 dup report:", dup_report)
