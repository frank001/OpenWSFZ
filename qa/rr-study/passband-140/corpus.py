#!/usr/bin/env python3
"""PASSBAND-140 corpora: cycle listing for C2 (primary) and C1' (sign replication).

Spec: qa/rr-study/2026-09-14-1542-architect-to-qa-spec-g2b-140-passband-rearm.md
section 1.

C2: identical corpus/boundary/dial to LIVE-GAP-NOW's own C2 -- reused via
live-gap-now.corpus.c2_cycles(), not re-implemented (spec section 0.5).

C1': artefacts/20260808_live_run_0016-8080/owsfz/wav/ (our own capture),
stems in [260808_011045, 260808_111500]. The lower bound is the burned-
cycle cut (ROW 0h): the 251st sorted wsjt-x/wav/*.wav file. Verified
mechanically 2026-09-14 (qa/rr-study/passband-140/row_status.md ROW 0h):
`ls .../wsjt-x/wav | sort | sed -n '251p'` == 260808_011045.wav. Upper
bound is LIVE-GAP-NOW's own WINDOW_20M upper bound (260808_111500) --
unchanged, this arm only tightens the LOWER bound to hold out the burned
dev-set cycles.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

# Load live-gap-now/corpus.py under a DISTINCT module name (not "corpus") --
# this directory's own module is also named corpus.py, and a plain
# `sys.path.insert` + `import corpus` here would self-collide: Python
# resolves the second "import corpus" to the module already mid-import
# (this very file), producing infinite self-recursion the first time
# c2_cycles() is called. importlib avoids the name collision entirely.
_spec = importlib.util.spec_from_file_location(
    "live_gap_now_corpus", os.path.join(_HERE, "..", "live-gap-now", "corpus.py"))
_live_gap_now_corpus = importlib.util.module_from_spec(_spec)
sys.modules["live_gap_now_corpus"] = _live_gap_now_corpus
_spec.loader.exec_module(_live_gap_now_corpus)

REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

C1_DIR = os.path.join(REPO_ROOT, "artefacts", "20260808_live_run_0016-8080")
C1_OWSFZ_WAV_DIR = os.path.join(C1_DIR, "owsfz", "wav")
C1_WSJTX_WAV_DIR = os.path.join(C1_DIR, "wsjt-x", "wav")

# The burned-cycle cut (ROW 0h), re-derived here as a function (not a hardcoded
# literal) so a corpus change would change this too, mechanically.
def row0h_cut() -> str:
    """Returns the stem of the 251st sorted wsjt-x/wav/*.wav file."""
    files = sorted(f for f in os.listdir(C1_WSJTX_WAV_DIR) if f.endswith(".wav"))
    if len(files) < 251:
        raise RuntimeError("ROW 0h VOID: only %d wsjt-x/wav files, need >= 251" % len(files))
    return files[250][:-4]  # 251st, 0-indexed


C1_PRIME_HI = "260808_111500"  # LIVE-GAP-NOW's own WINDOW_20M upper bound, unchanged


def c1_prime_cycles():
    """Sorted list of (ts, wav_path) for C1', decoded from our own capture
    (owsfz/wav/), stems in [row0h_cut(), C1_PRIME_HI]."""
    lo = row0h_cut()
    hi = C1_PRIME_HI
    out = []
    for fn in sorted(os.listdir(C1_OWSFZ_WAV_DIR)):
        if not fn.endswith(".wav"):
            continue
        ts = fn[:-4]
        if lo <= ts <= hi:
            out.append((ts, os.path.join(C1_OWSFZ_WAV_DIR, fn)))
    return out


def c2_cycles():
    """Reused verbatim from live-gap-now.corpus.c2_cycles() (spec section 0.5)."""
    return _live_gap_now_corpus.c2_cycles()


if __name__ == "__main__":
    cut = row0h_cut()
    c1p = c1_prime_cycles()
    c2, dup_report = c2_cycles()
    print("ROW 0h cut: %s" % cut)
    print("C1': %d cycles, window %s..%s" % (len(c1p), cut, C1_PRIME_HI))
    print("C2: %d cycles" % len(c2))
    print("C2 dup report:", dup_report)
