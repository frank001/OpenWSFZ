"""A4: was audio LOST, or only late? Cross-correlate the daemon's archived cycle windows with the audio S6 actually played (QA tooling, 2026-10-13; Option A, Part A4).
Aggregates only: the audio is read inside this module and only times, offsets and correlation peaks leave it (no message text exists in audio anyway).

    python archive_xcorr.py --playlog <s6_playlog.jsonl> --corpus <corpus> --wavlist <s6-wavlist.json> --archive <cycle-audio dir> --from 2026-10-13T18:09:00 \
        --to 2026-10-13T18:29:00 --out <json>

The played stream is known exactly: each play's WSJT-X-side WAV (12 kHz) laid on a wall-clock timeline at its slot boundary (idle slots and the warm-up cycle are silence on this
timeline: they cannot be matched and are skipped). Each archived window (180,000 samples at 12 kHz, labelled with its slot start S) is cut into 1 s chunks; chunk j has the
nominal time S + j. The chunk is correlated (normalised, FFT) with the timeline within +-SEARCH_S of its nominal time; the best lag gives the chunk's SOURCE time, and
    e(chunk) = source time - nominal time          (healthy: a constant, the replay chain's own delay, about +0.1 s)
A jump of e between consecutive chunks (nominal spacing 1 s) is a DISCONTINUITY in the sample stream: positive = source audio SKIPPED (lost), negative = source audio REPEATED
(the framer's 3,000-sample realignment overlaps successive windows by 0.25 s). Steps are classified at window boundaries (the -0.25 s realignment, expected) and inside a window.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import wave
from datetime import datetime, timezone

import numpy as np
from scipy.signal import fftconvolve

FS = 12_000
WINDOW = 180_000
CHUNK = FS                       # 1 s chunks
SEARCH_S = 14.0                  # +- search of the source time around the nominal time
MIN_PEAK = 0.30                  # normalised correlation below this is "no match" (idle audio, silence); a DESIGN number, the healthy windows' peaks are reported beside it
STEP_MIN_S = 0.08                # a change of e between consecutive chunks larger than this is a step (the healthy scatter is a few samples; reported)
WINDOW_BOUNDARY_REALIGN_S = 0.25 # the framer's per-cycle correction (3,000 samples)


def parse_utc(s: str) -> float:
    s = s.rstrip("Z")
    fmt = "%Y-%m-%dT%H:%M:%S.%f" if "." in s else "%Y-%m-%dT%H:%M:%S"
    return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp()


def read_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        assert w.getframerate() == FS and w.getnchannels() == 1 and w.getsampwidth() == 2, os.path.basename(path)
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)


def build_timeline(plays: list, origin: float, length_s: float, load_wav) -> np.ndarray:
    """Float32 timeline at 12 kHz from `origin` (UTC seconds); each play's samples at its slot boundary; silence elsewhere. load_wav(wav_id) -> float32 samples."""
    tl = np.zeros(int(length_s * FS), dtype=np.float32)
    for p in plays:
        x = load_wav(p["wav_id"])
        i0 = int(round((parse_utc(p["boundary_utc"]) - origin) * FS))
        if i0 < 0 or i0 + len(x) > len(tl):
            continue
        tl[i0:i0 + len(x)] = x
    return tl


def best_lag(chunk: np.ndarray, seg: np.ndarray) -> tuple:
    """Normalised cross-correlation of `chunk` against every position of `seg`; -> (offset in samples of the best match, peak value)."""
    n = len(chunk)
    if len(seg) < n or not np.any(chunk):
        return None, 0.0
    c = chunk - chunk.mean()
    cn = float(np.sqrt(np.dot(c, c)))
    if cn == 0:
        return None, 0.0
    num = fftconvolve(seg, c[::-1], mode="valid")                 # sum(seg[k:k+n] * c)
    cs = np.concatenate(([0.0], np.cumsum(seg, dtype=np.float64)))
    cs2 = np.concatenate(([0.0], np.cumsum(seg.astype(np.float64) ** 2)))
    win_sum = cs[n:] - cs[:-n]
    win_sq = cs2[n:] - cs2[:-n]
    var = win_sq - win_sum ** 2 / n
    den = np.sqrt(np.maximum(var, 1e-9)) * cn
    r = num / den
    k = int(np.argmax(r))
    return k, float(r[k])


def analyse_window(win: np.ndarray, nominal_start: float, tl: np.ndarray, origin: float) -> list:
    """-> per chunk [{"j", "e_s", "peak"}] (e_s None when no match)."""
    out = []
    for j in range(len(win) // CHUNK):
        chunk = win[j * CHUNK:(j + 1) * CHUNK]
        t_nom = nominal_start + j - origin                         # seconds on the timeline
        lo = int((t_nom - SEARCH_S) * FS)
        hi = int((t_nom + 1 + SEARCH_S) * FS)
        lo_c, hi_c = max(lo, 0), min(hi, len(tl))
        if hi_c - lo_c < CHUNK:
            out.append({"j": j, "e_s": None, "peak": 0.0})
            continue
        k, peak = best_lag(chunk, tl[lo_c:hi_c])
        if k is None or peak < MIN_PEAK:
            out.append({"j": j, "e_s": None, "peak": round(peak, 3)})
            continue
        t_src = (lo_c + k) / FS
        out.append({"j": j, "e_s": round(t_src - t_nom, 4), "peak": round(peak, 3)})
    return out


def find_steps(windows: list) -> list:
    """windows: [{"slot", "chunks": [...]}] in time order. -> every step of e between consecutive MATCHED chunks that are consecutive in nominal time (1 s apart)."""
    steps, prev = [], None
    for w in windows:
        for c in w["chunks"]:
            if c["e_s"] is None:
                prev = None                                    # a gap in matching: no step is claimed across it
                continue
            if prev is not None:
                d = round(c["e_s"] - prev["e_s"], 4)
                if abs(d) > STEP_MIN_S:
                    at_boundary = (c["j"] == 0 and prev["slot"] != w["slot"])
                    kind = "window_boundary_realign" if (at_boundary and abs(d + WINDOW_BOUNDARY_REALIGN_S) < 0.06) else ("window_boundary" if at_boundary else "inside_window")
                    steps.append({"slot": w["slot"], "chunk": c["j"], "step_s": d, "kind": kind, "e_before_s": prev["e_s"], "e_after_s": c["e_s"]})
            prev = {"e_s": c["e_s"], "slot": w["slot"]}
    return steps


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--playlog", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--wavlist", required=True)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = [json.loads(x) for x in open(a.playlog, encoding="utf8") if x.strip()]
    plays = [r for r in rows if r["kind"] == "play"]
    wl = {it["id"]: it for it in json.load(open(a.wavlist, encoding="utf8"))["items"]}
    cache = {}

    def load(wid):
        if wid not in cache:
            it = wl[wid]
            cache[wid] = read_wav(os.path.join(a.corpus, "wsjt-x", it["run"], it["stamp"] + ".wav"))
        return cache[wid]
    t0, t1 = parse_utc(a.t_from), parse_utc(a.t_to)
    tl = build_timeline(plays, t0 - 30, (t1 - t0) + 90, load)
    origin = t0 - 30
    import csv
    manifest = [r for r in csv.DictReader(open(os.path.join(a.archive, "cycle-archive.csv"), encoding="utf8"))]
    windows = []
    for r in manifest:
        S = parse_utc(r["cycle_start_utc"])
        if not (t0 <= S <= t1):
            continue
        fn = os.path.join(a.archive, r["filename"])
        if not os.path.isfile(fn):
            continue
        win = read_wav(fn)
        ch = analyse_window(win, S, tl, origin)
        windows.append({"slot": r["cycle_start_utc"][11:19], "closed_lag_s": round(parse_utc(r["window_closed_utc"]) - S - 15, 3), "decode_count": int(r["decode_count"]), "chunks": ch,
                        "matched_chunks": sum(1 for c in ch if c["e_s"] is not None)})
    steps = find_steps(windows)
    healthy = [c["e_s"] for w in windows[:6] for c in w["chunks"] if c["e_s"] is not None]
    res = {"windows": len(windows), "min_peak_design_number": MIN_PEAK, "step_min_s": STEP_MIN_S,
           "healthy_reference": {"chunks": len(healthy), "e_median_s": float(np.median(healthy)) if healthy else None,
                                 "e_min_s": min(healthy) if healthy else None, "e_max_s": max(healthy) if healthy else None},
           "steps": steps,
           "per_window": [{"slot": w["slot"], "closed_lag_s": w["closed_lag_s"], "decodes": w["decode_count"], "matched_chunks": w["matched_chunks"],
                           "e_first_s": next((c["e_s"] for c in w["chunks"] if c["e_s"] is not None), None), "e_last_s": next((c["e_s"] for c in reversed(w["chunks"]) if c["e_s"] is not None), None),
                           "median_peak": float(np.median([c["peak"] for c in w["chunks"]]))} for w in windows]}
    json.dump(res, open(a.out, "w"), indent=1)
    print("windows", len(windows), "steps", len(steps), "healthy e", res["healthy_reference"])
    for s in steps:
        if s["kind"] != "window_boundary_realign":
            print("  STEP", s)
    print("realign steps (-0.25 s at window boundaries):", sum(1 for s in steps if s["kind"] == "window_boundary_realign"))


if __name__ == "__main__":
    main()
