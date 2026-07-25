#!/usr/bin/env python3
"""Absolute cycle-window alignment measurement via decoder DT, 2x2 decoder-vs-audio design.

Companion to measure_capture_alignment.py (waveform cross-correlation). That script measures
the *relative* offset between our capture window and WSJT-X's. This one pins down which side
is misaligned in *absolute* terms, and separates capture error from decoder error.

Why DT is an absolute reference: DT is each decoder's estimate of a signal's time offset
within the cycle. The transmitting stations are collectively time-locked, so the median DT
across many stations in a cycle measures the receiver's own window alignment against UTC.
A correctly aligned receiver reads median DT ~ 0.

The 2x2 design separates the two candidate causes:

                        | our audio            | WSJT-X audio
    --------------------+----------------------+----------------------
    our decoder         | live ALL.TXT +       | offline replay
                        | offline replay       |
    WSJT-X decoder      | (not available)      | WSJT-X live ALL.TXT

  - Same decoder, two audio sources  -> isolates CAPTURE window offset.
  - Same audio, two decoders         -> isolates DECODER DT offset.

NFR-021: parses ALL.TXT for the numeric DT column only. Message text and callsigns are never
read into memory beyond the split, never stored, and never printed. Output is aggregate only.
"""
import collections
import os
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORK = os.path.join(ROOT, "qa", "cycleframer-alignment-replay", "_work")
ART = os.path.join(ROOT, "artefacts", "20260725_live_run_1806")

DT_FIELD = 5          # 0=file 1=dial 2=Rx 3=mode 4=snr 5=dt 6=freq 7+=message
MIN_DECODES = 3       # cycles with fewer decodes give an unreliable median


def load_dt_by_cycle(path):
    """cycle-id -> list of DT values. Never retains message text."""
    if not os.path.exists(path):
        return None
    out = collections.defaultdict(list)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 7 or f[2] != "Rx":
                continue
            try:
                out[f[0]].append(float(f[DT_FIELD]))
            except ValueError:
                continue
    return out


def summarize(label, by_cycle):
    flat = np.array([v for vals in by_cycle.values() for v in vals])
    med = np.array([np.median(v) for v in by_cycle.values() if len(v) >= MIN_DECODES])
    print(f"  {label:<34} n={len(flat):5d} cycles={len(by_cycle):3d} "
          f"medianDT={np.median(flat):+.3f}s  per-cycle med: mean={med.mean():+.3f}s "
          f"sd={med.std():.3f}s")
    return med


def main():
    sets = {
        "our decoder / our audio (live)": os.path.join(ART, "owsfz", "ALL.TXT"),
        "our decoder / our audio (offline)": os.path.join(WORK, "ours_decoded", "k10_c0.10_n60", "ALL.TXT"),
        "our decoder / WSJT-X audio (offline)": os.path.join(WORK, "wsjtx_decoded", "k10_c0.10_n60", "ALL.TXT"),
        "WSJT-X decoder / WSJT-X audio (live)": os.path.join(ART, "wsjt-x", "ALL.TXT"),
    }
    print("=== 2x2 decoder-vs-audio DT summary ===")
    med = {}
    for label, path in sets.items():
        d = load_dt_by_cycle(path)
        if d is None:
            print(f"  {label:<34} MISSING: {path}")
            continue
        med[label] = summarize(label, d)

    print()
    print("=== decomposition ===")
    a = med.get("our decoder / our audio (offline)")
    b = med.get("our decoder / WSJT-X audio (offline)")
    c = med.get("WSJT-X decoder / WSJT-X audio (live)")
    if a is not None and b is not None:
        print(f"  CAPTURE offset  (same decoder, our audio - WSJT-X audio): "
              f"{a.mean() - b.mean():+.3f} s")
    if b is not None and c is not None:
        print(f"  DECODER offset  (same audio, our decoder - WSJT-X decoder): "
              f"{b.mean() - c.mean():+.3f} s")
    print()
    print("=== window stability (same decoder, so this is the capture chain alone) ===")
    if a is not None:
        print(f"  our capture    : per-cycle median DT sd = {a.std()*1000:6.1f} ms")
    if b is not None:
        print(f"  WSJT-X capture : per-cycle median DT sd = {b.std()*1000:6.1f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
