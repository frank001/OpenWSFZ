#!/usr/bin/env python3
"""GAP-LOCATE corpus loader.

Spec sec.0/1: reuses the LIVE-GAP-MAP harness's own cycle-window/Amendment-3-cut
logic verbatim (HK-018, imported from lgm_harness.py, not re-derived) so the included
cycle set is BIT-IDENTICAL to the one that produced lgm_result_amendment3.json's
n_ref=127,482 / H10=19.2686pp -- ROW 0b's whole point is to reproduce those numbers
independently, not to compute new ones under a similar-looking filter.

Extended beyond lgm_harness.matcher.load_all: this loader keeps column [5] (DT) as
well as [4] (SNR) and [6] (freq_hz), because Leg F/K need REF's own DT to compute the
forced-read position (spec sec.2: t = REF DT + delta). matcher.recovery() only ever
inspects dict KEYS (ts, message), never values, so widening the value tuple here does
not change any hit/miss/n_ref computation -- cross-checked in row0.py by asserting this
loader's own key set reproduces lgm_harness's ref/live key sets exactly.

NFR-021: (snr, dt, freq_hz) values only; message text is the dict KEY and must never be
printed, logged or written to disk from this module or its callers.
"""
from __future__ import annotations

import csv
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "live-gap-map"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "live-gap-now"))

import lgm_harness as LGM  # noqa: E402  (AMD3_EXCLUDE, _in_amd3_window, cyc_index -- reused verbatim)

DIAL_PREFIX = "14.074"


def _load_with_dt(path: str, lo: str, hi: str, dial_prefix: str = DIAL_PREFIX) -> dict:
    """(ts, message) -> (snr, dt, freq_hz) for Rx FT8 lines on the dial freq in [lo, hi].
    Same filter as h1_hash_token_contamination.load() / matcher.load_all, extended with DT."""
    out = {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if not f[1].startswith(dial_prefix):
                continue
            ts = f[0]
            if not (lo <= ts <= hi):
                continue
            try:
                snr, dt, freq_hz = int(f[4]), float(f[5]), int(f[6])
            except ValueError:
                continue
            out[(ts, " ".join(f[7:]))] = (snr, dt, freq_hz)
    return out


def load_c3_with_dt(corpus_dir: str, cut_amendment3: bool = True) -> dict:
    """Mirrors lgm_harness.load_c3 exactly (cycle discovery, Amendment 3 cut, lo/hi
    window), substituting _load_with_dt for matcher.load_all."""
    st = json.load(open(os.path.join(corpus_dir, "state.json"), encoding="utf-8"))
    ws = datetime.datetime.strptime(st["window_start"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    we = datetime.datetime.strptime(st["window_end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    W_all = []
    with open(os.path.join(corpus_dir, "cycle-audio", "cycle-archive.csv"), encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            t = datetime.datetime.strptime(row["cycle_start_utc"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
            if ws <= t < we and row["dial_mhz"] == "14.074" and row["filename"].endswith(".wav") and not row["filename"].endswith("_2.wav"):
                W_all.append(row["filename"][:-4])
    W_all = sorted(set(W_all))
    removed = [w for w in W_all if LGM._in_amd3_window(w)] if cut_amendment3 else []
    removed_set = set(removed)
    W = [w for w in W_all if w not in removed_set]
    S = set(W)
    lo, hi = min(W_all), max(W_all)
    ref = _load_with_dt(os.path.join(corpus_dir, "wsjtx-1-ft991a", "ALL.TXT"), lo, hi)
    live = _load_with_dt(os.path.join(corpus_dir, "openwsfz", "ALL.TXT"), lo, hi)
    ref = {k: v for k, v in ref.items() if k[0] in S}
    live = {k: v for k, v in live.items() if k[0] in S}
    row0 = json.load(open(os.path.join(corpus_dir, "row0.json"), encoding="utf-8"))
    wall_cycles = int(round((we - ws).total_seconds() / 15)) - len(removed)
    return {
        "ref": ref, "live": live, "cycles": W, "wall_cycles": wall_cycles, "row0": row0,
        "window": {"start": st["window_start"], "end": st["window_end"]},
        "label": os.path.basename(corpus_dir), "cut_amendment3": cut_amendment3,
        "removed_cycles": len(removed), "lo": lo, "hi": hi,
    }


def cycle_wav_path(corpus_dir: str, ts: str) -> str:
    return os.path.join(corpus_dir, "cycle-audio", ts + ".wav")
