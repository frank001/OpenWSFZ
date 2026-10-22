"""S6 onset row (QA tooling; Architect ruling 2026-10-13, 1a): did the sound arrive on the slot's grid? From data the run ALREADY records (HK-027).

The player's call-time offset cannot see the sound's onset (HK-026: aplay -> codec -> loopback latency is invisible to it). WSJT-X can: it reports a DT for each decode, measured against its own slot clock. The same recording was decoded LIVE by WSJT-X when it was recorded, so for every row that WSJT-X decodes in BOTH the replay and the live log,
    shift = DT(replay) - DT(live)
is the extra delay the replay chain added (a later onset reads as a larger DT). Per play: the median shift over the rows matched by text (non-hashed; text + rank by frequency); the distribution of those per-play medians over the plays is the row. The 70 min keep-up run read +0.1 s at lead 0.0 s.
Descriptive: no bar (the Architect sets it from this row). Message text is read inside this module's functions and never leaves; outputs are numbers.
"""
from __future__ import annotations

import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
if RR not in sys.path:
    sys.path.insert(0, RR)

MIN_ROWS_PER_PLAY = 3          # a play with fewer matched rows gives no per-play median (counted, not dropped silently)


def read_rows(path: str, wanted_stamps: set | None = None) -> dict:
    """{slot stamp YYMMDD_HHMMSS: [(text, rank-by-freq, dt_s)]} of the non-hashed FT8 rows of an ALL.TXT (only the stamps asked for, when given)."""
    from pathlib import Path
    from harness.common import parse_all_txt
    recs, _ = parse_all_txt(Path(path))
    raw = defaultdict(list)
    for r in recs:
        st = r.utc.strftime("%y%m%d_%H%M%S")
        if wanted_stamps is not None and st not in wanted_stamps:
            continue
        t = " ".join(r.message.split()).upper()
        if "<" in t:
            continue
        raw[st].append((t, float(r.freq_hz), float(r.dt_s)))
    out = {}
    for st, rows in raw.items():
        seen, keyed = defaultdict(int), []
        for t, f, dt in sorted(rows, key=lambda x: (x[0], x[1])):
            keyed.append(((t, seen[t]), dt))
            seen[t] += 1
        out[st] = keyed
    return out


def per_play_shifts(plays: list, replay: dict, live_by_run: dict, items_by_id: dict) -> list:
    """-> [{"slot", "n_matched", "median_shift_s"}] for each play. replay = read_rows(slice); live_by_run = {run: read_rows(corpus ALL.TXT of that run)}."""
    out = []
    for p in plays:
        it = items_by_id[p["wav_id"]]
        live = dict(live_by_run.get(it["run"], {}).get(it["stamp"], []))
        rep = dict(replay.get(p["slot_stamp"], []))
        shifts = [round(rep[k] - live[k], 3) for k in rep if k in live]      # DT has 0.1 s resolution: the difference is rounded to 3 places
        out.append({"slot": p["slot_stamp"], "n_matched": len(shifts), "median_shift_s": round(statistics.median(shifts), 3) if len(shifts) >= MIN_ROWS_PER_PLAY else None,
                    "_shifts": shifts})
    return out


def summarise(per_play: list) -> dict:
    meds = sorted(x["median_shift_s"] for x in per_play if x["median_shift_s"] is not None)
    allrows = sorted(s for x in per_play for s in x["_shifts"])

    def q(v, p):
        return v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))] if v else None
    return {"plays": len(per_play), "plays_with_median": len(meds), "plays_without_enough_rows": len(per_play) - len(meds), "min_rows_per_play": MIN_ROWS_PER_PLAY,
            "rows_matched": len(allrows),
            "per_play_median_shift_s": {"min": meds[0] if meds else None, "p10": q(meds, 0.1), "median": q(meds, 0.5), "p90": q(meds, 0.9), "max": meds[-1] if meds else None},
            "all_rows_shift_s": {"p10": q(allrows, 0.1), "median": q(allrows, 0.5), "p90": q(allrows, 0.9)},
            "reading": "DT(replay) - DT(live) of the same WSJT-X rows: the delay the replay chain added to the sound's onset (positive = later); descriptive, no bar yet"}


def onset_row(plays: list, replay_slice: str, corpus: str, wavlist: dict) -> dict:
    items = {it["id"]: it for it in wavlist["items"]}
    stamps = {p["slot_stamp"] for p in plays}
    replay = read_rows(replay_slice, stamps)
    runs = {items[p["wav_id"]]["run"] for p in plays}
    live_by_run = {}
    for run in runs:
        wanted = {items[p["wav_id"]]["stamp"] for p in plays if items[p["wav_id"]]["run"] == run}
        path = os.path.join(corpus, "wsjt-x", run, "ALL.TXT")
        live_by_run[run] = read_rows(path, wanted) if os.path.isfile(path) else {}
    pp = per_play_shifts(plays, replay, live_by_run, items)
    return summarise(pp)
