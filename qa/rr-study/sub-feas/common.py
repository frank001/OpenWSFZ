#!/usr/bin/env python3
"""SUB-FEAS: shared paths, sys.path wiring, and small utilities.

Spec: qa/rr-study/2026-09-27-1855-architect-to-qa-spec-sub-feas-data-aided-subtraction-feasibility.md
Corpus: artefacts/20260925_2010_endurance_run-gathered/ (40m, direct-CODEC, nhard 40,
decoding_improvement 51e40b55, shim 20260054, DLL SHA-256 38a21f84...589a1cba, per
artefacts/20260925_2010_endurance_run/arm_config.json).

HK-037/NFR-021: this module and corpus.py are the ONLY places that read message text
out of ALL.TXT. Every function here and downstream deals in numeric fields
(cycle_ts, freq_hz, dt, snr, row_id) plus in-memory tone arrays (not text/callsigns)
needed transiently by the fitter. Nothing with message text is ever written to disk.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# APPEND (never insert at 0): this arm's own directory must keep priority over
# gap-locate's -- both directories have a `row0.py`, and an insert(0, ...) here
# previously caused gap-locate's row0.py to shadow this arm's own module.
for rel in ("qa/rr-study/gap-locate", "qa/rr-study", "qa/rr-study/r2-coherent-llr-instrument",
            "qa/rr-study/n1-extract-llrs-at-position"):
    p = os.path.join(REPO_ROOT, *rel.split("/"))
    if p not in sys.path:
        sys.path.append(p)

CORPUS_DIR = os.path.join(REPO_ROOT, "artefacts", "20260925_2010_endurance_run-gathered")
OWSFZ_ALL_TXT = os.path.join(CORPUS_DIR, "owsfz", "ALL.TXT")
WSJTX_ALL_TXT = os.path.join(CORPUS_DIR, "wsjt-x", "ALL.TXT")
OWSFZ_WAV_DIR = os.path.join(CORPUS_DIR, "owsfz", "wav")
CYCLE_ARCHIVE_CSV = os.path.join(CORPUS_DIR, "owsfz", "cycle-archive.csv")

ARM_CONFIG_PATH = os.path.join(REPO_ROOT, "artefacts", "20260925_2010_endurance_run", "arm_config.json")

RUN_DIR = os.path.join(REPO_ROOT, "artefacts", "sub-feas")  # gitignored (artefacts/ is blanket-gitignored)
RESULT_PATH = os.path.join(REPO_ROOT, "qa", "rr-study", "sub-feas", "sub_feas_result.json")

DIAL_PREFIX = "7.074"
SAMPLE_RATE_HZ = 12000
BUFFER_SAMPLES = 180_000  # 15 s @ 12 kHz -- matches wavio.py / extract_llrs_ctypes.py

SEED = 20260927


def log_stdout_utf8():
    """HK-009: stdout is cp1252 on Windows consoles by default."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def make_logger(path):
    fh = open(path, "a", encoding="utf-8")

    def log(msg):
        print(msg, flush=True)
        fh.write(str(msg) + "\n")
        fh.flush()

    return log
