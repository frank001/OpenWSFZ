#!/usr/bin/env python3
"""P-LIVE -- population assembly, built directly from two ALL.TXT files per corpus.

Spec: qa/rr-study/2026-08-17-1806-architect-to-qa-p-live-population-and-n-series-
replication-spec.md Sec.2, AS AMENDED by Amendment A4 (2026-08-18-1457, Stage 1
go-ahead) Sec.2.1/Sec.4/Sec.5.2/Sec.6.

Mechanically, per corpus directory `R` (Sec.2, points 1-7):
  1. Parse both ALL.TXT with c2_phase2c_ber_measurement.parse_all_txt -- [5] is DT,
     [6] is frequency in INTEGER Hz (inverting them inverts the result exactly).
  2. Normalise every message with normalize_hash_tokens (unchanged convention).
  3. A row is a WSJT-X decode whose normalised message does NOT appear in our own
     ALL.TXT for the same ts.
  4. Anchor = WSJT-X's reported freq (integer Hz) and dt.
  5. True codeword recovery and no_true_codeword drop happen in the Stage 1 harness
     (this module never touches the DLL -- pure ALL.TXT parsing only).
  6. Audio = the WAV for that ts FROM THE LEG THAT SUPPLIED THE ANCHOR -- i.e. the
     wsjt-x leg's own wav/ directory, since the anchor (point 4) is WSJT-X's own
     report. ROW 0a (run separately, already CLEAR on all five corpora at
     2026-08-18 14:46Z) is what licenses treating that WAV as equivalent to ours.
  7. Cluster = ts. Always -- this module's own row dicts carry `ts` and nothing else
     that varies faster than the cycle for bootstrap purposes.

Sec.2.1: P-LIVE is a SUPERSET of THE 135/THE 567 (WSJT-X decoded it, we detected
NOTHING, not "a candidate sat there and failed") -- do not compare its numbers to
N1/N5 point estimates.

Amendment A4.2: PRIMARY_CORPUS = `20260803_live_run_1713` ALONE is the confirmatory
population for Stage 1 ROW 1/2/3. EXTENSION_CORPORA are descriptive replication,
reported per corpus, NEVER pooled or summed (Sec.5.2 -- 0016-8080/-8081 observe the
SAME cycles at median Jaccard 1.000/0.909/1.000, so summing their cluster counts
double-counts nearly identical rows).

Sec.6: `20260731_live_run_2004-*` and `20260729_live_run_1831-*` are EXCLUDED --
not present in ALL_CORPORA below.

NFR-021: rows returned by build_p_live_population() DO carry `message` (this
module's own return value, consumed in-process by the Stage 1 harness to recover
the true codeword) -- but this module itself never writes a file or prints a row.
The Stage 1 harness strips `message` before anything reaches disk or stdout beyond
aggregate counts.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))

import c2_phase2c_ber_measurement as C2  # noqa: E402

ARTEFACTS = os.path.join(REPO_ROOT, "artefacts")

# Amendment A4.2: the ONE confirmatory population.
PRIMARY_CORPUS = "20260803_live_run_1713"

# Sec.6: extension corpora, descriptive replication only, NEVER pooled/summed with
# each other or with PRIMARY_CORPUS (Sec.5.2 leg-handling rule).
EXTENSION_CORPORA = [
    "20260808_live_run_0016-8080",
    "20260808_live_run_0016-8081",
    "20260808_live_run_1154-8080-17m",
    "20260809_live_run_0155-8080-80m",
]

ALL_CORPORA = [PRIMARY_CORPUS] + EXTENSION_CORPORA


def corpus_paths(corpus_name: str) -> dict:
    root = os.path.join(ARTEFACTS, corpus_name)
    return {
        "root": root,
        "wsjtx_all_txt": os.path.join(root, "wsjt-x", "ALL.TXT"),
        "owsfz_all_txt": os.path.join(root, "owsfz", "ALL.TXT"),
        "wsjtx_wav_dir": os.path.join(root, "wsjt-x", "wav"),
        "owsfz_wav_dir": os.path.join(root, "owsfz", "wav"),
    }


def build_p_live_population(corpus_name: str) -> list[dict]:
    """Returns [{ts, message, anchor_freq_hz, anchor_dt, corpus}], one row per
    WSJT-X decode this corpus's own OpenWSFZ ALL.TXT does not contain (same ts,
    normalised message). message is present ONLY for this module's in-process
    callers -- see module docstring's NFR-021 note."""
    paths = corpus_paths(corpus_name)
    wsjtx_rows = C2.parse_all_txt(paths["wsjtx_all_txt"])
    mine_rows = C2.parse_all_txt(paths["owsfz_all_txt"])

    mine_msgset_by_cycle: dict[str, set[str]] = {}
    for r in mine_rows:
        mine_msgset_by_cycle.setdefault(r["ts"], set()).add(C2.normalize_hash_tokens(r["message"]))

    out = []
    for row in wsjtx_rows:
        key = C2.normalize_hash_tokens(row["message"])
        if key in mine_msgset_by_cycle.get(row["ts"], set()):
            continue
        out.append({
            "ts": row["ts"],
            "message": row["message"],
            "anchor_freq_hz": row["freq"],
            "anchor_dt": row["dt"],
            "corpus": corpus_name,
        })
    return out


if __name__ == "__main__":
    for _name in ALL_CORPORA:
        _pop = build_p_live_population(_name)
        _n_clusters = len({r["ts"] for r in _pop})
        print("%s: n_rows=%d n_clusters=%d" % (_name, len(_pop), _n_clusters))
