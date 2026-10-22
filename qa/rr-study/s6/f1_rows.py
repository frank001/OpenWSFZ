"""F1' capture-buffer arm: rows F-1..F-5 (QA tooling; Architect spec F1 + amendment 1, 2026-10-17).

    python f1_rows.py --run DIR --daemon-log LOG --base-run DIR --base-log LOG --out JSON

Unit: the OpenWSFZ window of each of the 60 plays, [boundary, +15 s).  F-1 = overrun Warning lines in those windows (cross-check: counter delta over the block);
F-2 = windows with |wanted| > 600 samples on THEIR OWN `Window emitted` line (cycle = the play's boundary); F-3 = windows at the clamp (|applied| >= 3000);
F-4 = for each remaining overrun: position in the window, next window's wanted (the loss size), size against G; F-5 = decodes per play (aggregate counts, HK-037).
Baseline = trial 0 (play_index 0-59) of the 2026-10-17 block, same WAVs, same order, taken at G = 0.2 s.  F-1 classes: <=1 EFFECTIVE, 2-5 PARTIAL, >=6 NO EFFECT (decided before the data).
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone

OVR_RE = re.compile(r"arecord overrun at (\d\d):(\d\d):(\d\d)\.(\d{3}) UTC")
WIN_RE = re.compile(r"Window emitted \(\d+ samples, cycle (\d\d):(\d\d):(\d\d)\); wanted (-?\d+), applied (-?\d+) samples")
OFF_GRID = 600
CLAMP = 3000
EFFECTIVE_MAX, PARTIAL_MAX = 1, 5


def epoch(iso: str) -> float:
    return datetime.strptime(iso.replace("Z", "").split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()


def parse_log(path: str, day0: float) -> tuple:
    ov, win = [], {}
    for line in open(path, encoding="utf8", errors="replace"):
        m = OVR_RE.search(line)
        if m:
            ov.append(day0 + int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000.0)
            continue
        m = WIN_RE.search(line)
        if m:
            win[day0 + int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))] = (int(m.group(4)), int(m.group(5)))
    return ov, win


def plays_of(playlog: str) -> list:
    out = []
    for line in open(playlog, encoding="utf8"):
        d = json.loads(line)
        if d.get("kind") == "play":
            b = d.get("boundary_utc_o") or d["boundary_utc"]
            out.append({"i": d["play_index"], "wav": d["wav_id"], "gain": d["gain"], "t": epoch(b), "stamp": d.get("slot_stamp_o") or d["slot_stamp"]})
    return sorted(out, key=lambda p: p["i"])


def decodes_by_stamp(all_txt: str) -> dict:
    c = {}
    if os.path.isfile(all_txt):
        for line in open(all_txt, encoding="utf8", errors="replace"):
            t = line.split(None, 1)
            if t:
                c[t[0]] = c.get(t[0], 0) + 1
    return c


def block_rows(plays: list, ov: list, win: dict, decodes: dict, g_s: float | None) -> dict:
    rows = {"plays": len(plays)}
    in_win = [(p, [o for o in ov if p["t"] <= o < p["t"] + 15]) for p in plays]
    rows["F1_overruns_in_play_windows"] = sum(len(x) for _, x in in_win)
    rows["F1_windows_with_overrun"] = sum(1 for _, x in in_win if x)
    own = [win.get(p["t"]) for p in plays]
    rows["windows_with_framer_line"] = sum(1 for x in own if x)
    rows["F2_off_grid_gt_600"] = sum(1 for x in own if x and abs(x[0]) > OFF_GRID)
    rows["F3_at_clamp"] = sum(1 for x in own if x and abs(x[1]) >= CLAMP)
    f4 = []
    for p, xs in in_win:
        for o in xs:
            nxt = win.get(p["t"] + 15)
            wanted = nxt[0] if nxt else None
            f4.append({"play": p["i"], "position_s": round(o - p["t"], 3), "next_window_wanted_samples": wanted,
                       "loss_s": round(wanted / 12000.0, 3) if wanted is not None else None,
                       "loss_vs_G": (round(wanted / 12000.0 / g_s, 3) if (wanted is not None and g_s) else None)})
    rows["F4_remaining_overruns"] = f4
    rows["F5_decodes_total"] = sum(decodes.get(p["stamp"], 0) for p in plays)
    rows["F5_plays_with_decode_lines"] = sum(1 for p in plays if decodes.get(p["stamp"], 0) > 0)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("--run", "--daemon-log", "--base-run", "--base-log", "--out"):
        ap.add_argument(a, required=True)
    ap.add_argument("--base-all", default=None, help="the baseline block's owsfz ALL.TXT (counts only)")
    ap.add_argument("--run-all", default=None, help="this block's owsfz ALL.TXT (counts only)")
    a = ap.parse_args()
    plays = plays_of(os.path.join(a.run, "s6", "pass-o", "s6_playlog.jsonl"))
    base_plays = [p for p in plays_of(os.path.join(a.base_run, "s6", "pass-o", "s6_playlog.jsonl")) if p["i"] < 60]
    day0 = plays[0]["t"] - (plays[0]["t"] % 86400)
    bday0 = base_plays[0]["t"] - (base_plays[0]["t"] % 86400)
    ov, win = parse_log(a.daemon_log, day0)
    bov, bwin = parse_log(a.base_log, bday0)
    g = float(open(os.path.join(a.run, "G.txt")).read().strip()) if os.path.isfile(os.path.join(a.run, "G.txt")) else None
    res = {"G_s": g, "same_wavs_same_order": [p["wav"] for p in plays] == [p["wav"] for p in base_plays],
           "same_gains": all(abs(p["gain"] - q["gain"]) < 1e-5 for p, q in zip(plays, base_plays)),
           "this_block": block_rows(plays, ov, win, decodes_by_stamp(a.run_all) if a.run_all else {}, g),
           "baseline_trial0_G_0.2s": block_rows(base_plays, bov, bwin, decodes_by_stamp(a.base_all) if a.base_all else {}, 0.2)}
    n = res["this_block"]["F1_overruns_in_play_windows"]
    res["F1_class"] = "EFFECTIVE" if n <= EFFECTIVE_MAX else ("PARTIAL" if n <= PARTIAL_MAX else "NO EFFECT")
    cb, ca = os.path.join(a.run, "counters_before.txt"), os.path.join(a.run, "counters_after.txt")
    if os.path.isfile(cb) and os.path.isfile(ca):
        b0, a0 = [int(x) for x in open(cb).read().split()], [int(x) for x in open(ca).read().split()]
        res["counter_delta_overruns_over_block_incl_tail"] = a0[0] - b0[0]
        res["counter_delta_channel_drops"] = a0[1] - b0[1]
        res["counter_delta_watchdog_restarts"] = a0[2] - b0[2]
    with open(a.out, "w", encoding="utf8", newline="\n") as fh:
        json.dump(res, fh, indent=1)
    print("F-1 %d (%s); this block F-2 %d F-3 %d | baseline trial 0: F-1 %d F-2 %d F-3 %d" % (
        n, res["F1_class"], res["this_block"]["F2_off_grid_gt_600"], res["this_block"]["F3_at_clamp"],
        res["baseline_trial0_G_0.2s"]["F1_overruns_in_play_windows"], res["baseline_trial0_G_0.2s"]["F2_off_grid_gt_600"], res["baseline_trial0_G_0.2s"]["F3_at_clamp"]))


if __name__ == "__main__":
    main()
