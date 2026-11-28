#!/usr/bin/env python3
"""Held-out replay of the FG ON night (20261128_0038): two contiguous blocks of 400 archived cycles (NB = the busiest, NQ = the quietest) through two builds, scored against the night's WSJT-X.

  python -I fg_night_run.py <NB|NQ> L 400 --tag nx|nf --bin <harness dir> --pin <libft8.dll sha256> --probe [--grid 1:4:4]

A thin wrapper of lc_base_run.py: it only registers the two blocks (cycle list = the night's gathered WAVs in order, `_qa-scratch\\lc-base\\sel_fgnight.json`; the first cycle of a block is preceded by the cycle
before it as the warm-up, as for the other slices). Blocks (chosen from WSJT-X rows per cycle, before any decode): busy 261128_080645 .. 094630 (37.4 per cycle), quiet 261128_005945 .. 023930 (15.4 per cycle).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lc_base_run as R  # noqa: E402

SEL = R.SC + r"\lc-base\sel_fgnight.json"
FOLDER = "20261128_0038_endurance_run-gathered"
R.SLICES["NB"] = ("20261128_0038", FOLDER, SEL, "261128_080645")
R.SLICES["NQ"] = ("20261128_0038", FOLDER, SEL, "261128_005945")

if __name__ == "__main__":
    R.main()
