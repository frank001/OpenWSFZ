"""OWS-REPLAY-CONSISTENCY step 5: the LOG STEP (QA tooling; Architect step-test ruling section 3 + amendment 1 `arch/ows-replay-consistency` 4df9a2e3). DESK WORK on logs already kept: no run, no decode.

Do OpenWSFZ's forward steps (source audio skipped) coincide with the PREVIOUS cycle's decode passes?

    python ows_decode_overlap.py --runs DIR --shift DIR --daemon-log LOG --tz-h 2 --out JSON

Definitions (frozen with amendment 1; counts only, no CI, no bar):
  * A window of slot S starts at S. The previous cycle's (slot S-15) decode runs in the first seconds of it. Relative to S: pass 0 = [0, C] with C = that cycle's `elapsed=` (the
    'Cycle ...: N decode(s) found, elapsed=X ms' line); residual pass = [C, C + R] with R the residual pass line's `elapsedMs` for that cycle (attributed by the adjacent Cycle line, as
    s6_analyse.read_pass_lines does); decode-active = [0, C + R]. A cycle with no Cycle line is excluded and counted.
  * A step that begins at chunk c (the new e starts at chunk c) lies on the chunk boundary at t = c s after the window start; its interval is [c - 0.5, c + 0.5] s (about 1 s resolution).
    "Inside" = interval OVERLAP at that resolution. The daemon log stamps are whole seconds; pass starts are anchored on the Cycle line's elapsed instead, and the pass line's own stamp is
    reported as a cross-check.
  * (a) share of the step intervals that overlap decode-active, the residual pass, pass 0:
        (i)  POSITION-MATCHED control, the row that matters: the same chunk interval in an equal seeded set of step-free windows (each step window is paired with one seeded step-free window
             and takes its step's c); also in ALL step-free windows at each c.
        (ii) random-instant control: one seeded uniform instant per seeded step-free window, an interval of the same 1 s width.
        pass durations (descriptive): C, R and C + R of the step windows against the step-free windows.
  * (b) framer lines ("Cycle-grid realignment clamped") in the same window [S, S+15) and in the preceding cycle [S-15, S), step windows against step-free windows.
  * (c) whether any `arecord` stderr was captured anywhere: it confirms only that the instrument is blind (stderr is piped and never read), not that no overruns happened.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import collapse_check as cc  # noqa: E402
import ows_step_test as P  # noqa: E402
import s6_analyse as A  # noqa: E402

SLOT_S = 15
HALF = 0.5                    # a step interval is [c - 0.5, c + 0.5] s
SEED = 20261016


def overlaps(a_lo: float, a_hi: float, b_lo: float, b_hi: float) -> bool:
    return a_lo < b_hi and b_lo < a_hi


def decode_intervals(c_ms: float | None, r_ms: float | None) -> dict | None:
    """-> relative intervals (seconds from the window start) of the previous cycle's decode, or None when the Cycle line is missing."""
    if c_ms is None:
        return None
    c = c_ms / 1000.0
    out = {"pass0": (0.0, c), "residual": None, "active": (0.0, c)}
    if r_ms is not None:
        r = r_ms / 1000.0
        out["residual"] = (c, c + r)
        out["active"] = (0.0, c + r)
    return out


def step_positions(e: list, j: float) -> list:
    """The chunk c at which each step begins (the new e starts at chunk c)."""
    return [k + 1 for k, _ in P.steps_of(e, j)]


def share(flags: list) -> dict:
    return {"n": len(flags), "overlap": int(sum(flags)), "share": (sum(flags) / len(flags)) if flags else None}


def pair_controls(step_windows: list, free_windows: list, seed: int = SEED) -> tuple:
    """-> (seeded free windows, pairing {step window: free window}). The seeded set has as many windows as there are step windows."""
    rng = random.Random(seed)
    chosen = sorted(rng.sample(free_windows, len(step_windows)))
    shuffled = chosen[:]
    rng.shuffle(shuffled)
    return chosen, dict(zip(step_windows, shuffled))


def summarise(vals: list) -> dict:
    v = [x for x in vals if x is not None]
    if not v:
        return {"n": 0}
    return {"n": len(v), "median": float(np.median(v)), "p90": float(np.percentile(v, 90)), "max": float(max(v))}


def run(runs_dir: str, shift_dir: str, daemon_log: str, tz_h: float) -> dict:
    plan = json.load(open(os.path.join(runs_dir, "plan.json"), encoding="utf8"))
    off = json.load(open(os.path.join(shift_dir, "chunk_offsets.json"), encoding="utf8"))
    c_o = {int(k): v for k, v in off["e_o"].items()}
    j = json.load(open(os.path.join(shift_dir, "step_result.json"), encoding="utf8"))["J_s"]
    d = cc.parse(daemon_log, tz_h)
    cyc = {c["slot_sod"]: c for c in d["cycles"]}
    passes = {x["cycle_sod"]: x for x in A.read_pass_lines(daemon_log) if x["cycle_sod"] is not None}
    clamps = sorted(c["t_sod"] for c in d["clamps"])

    def slot_sod(stamp: str) -> int:
        return int(stamp[7:9]) * 3600 + int(stamp[9:11]) * 60 + int(stamp[11:13])
    info, steps = {}, {}
    for p in plan:
        i = p["index"]
        s_sod = slot_sod(p["stamp_o"])
        prev = (s_sod - SLOT_S) % 86400
        cy, ps = cyc.get(prev), passes.get(prev)
        info[i] = {"S": s_sod, "iv": decode_intervals(cy["elapsed_ms"] if cy else None, ps["elapsed_ms"] if ps else None),
                   "c_ms": cy["elapsed_ms"] if cy else None, "r_ms": ps["elapsed_ms"] if ps else None,
                   "clamps_same": sum(1 for t in clamps if 0 <= (t - s_sod) % 86400 < SLOT_S), "clamps_prev": sum(1 for t in clamps if 0 < (s_sod - t) % 86400 <= SLOT_S)}
        steps[i] = step_positions(c_o[i], j)
    step_w = sorted(i for i, s in steps.items() if s)
    free_w = sorted(i for i, s in steps.items() if not s)
    seeded, pairing = pair_controls(step_w, free_w)
    res = {"J_s": j, "plays": len(plan), "step_windows": len(step_w), "step_free_windows": len(free_w), "seeded_step_free": len(seeded),
           "windows_without_prev_cycle_line": sum(1 for i in info if info[i]["iv"] is None), "residual_line_missing": sum(1 for i in info if info[i]["iv"] and info[i]["iv"]["residual"] is None),
           "resolution": "step interval [c-0.5, c+0.5] s about 1 s; overlap at that resolution; pass starts anchored on the Cycle line's elapsed"}
    rng = random.Random(SEED + 1)

    def hit(i, lo, hi, which):
        iv = info[i]["iv"]
        if iv is None or iv[which] is None:
            return None
        return overlaps(lo, hi, *iv[which])
    rows = {}
    for which in ("active", "residual", "pass0"):
        steps_flags = [hit(i, c - HALF, c + HALF, which) for i in step_w for c in steps[i]]
        paired = [hit(pairing[i], c - HALF, c + HALF, which) for i in step_w for c in steps[i]]          # position-matched, seeded set
        allfree = {}
        for c in sorted({c for i in step_w for c in steps[i]}):
            allfree[str(c)] = share([x for x in (hit(i, c - HALF, c + HALF, which) for i in free_w) if x is not None])
        rand = []
        for i in seeded:
            t = rng.uniform(HALF, SLOT_S - HALF)
            rand.append(hit(i, t - HALF, t + HALF, which))
        rows[which] = {"steps": share([x for x in steps_flags if x is not None]), "position_matched_seeded": share([x for x in paired if x is not None]),
                       "position_matched_all_step_free_by_c": allfree, "random_instant_seeded": share([x for x in rand if x is not None])}
    res["rows_a"] = rows
    res["durations_s"] = {k: {"step_windows": summarise([(info[i][f] / 1000.0) if info[i][f] is not None else None for i in step_w]),
                              "step_free_windows": summarise([(info[i][f] / 1000.0) if info[i][f] is not None else None for i in free_w])}
                          for k, f in (("pass0_C", "c_ms"), ("residual_R", "r_ms"))}
    tot = lambda i: ((info[i]["c_ms"] + info[i]["r_ms"]) / 1000.0) if info[i]["c_ms"] is not None and info[i]["r_ms"] is not None else None
    res["durations_s"]["active_C_plus_R"] = {"step_windows": summarise([tot(i) for i in step_w]), "step_free_windows": summarise([tot(i) for i in free_w])}
    res["rows_b_framer_clamp_lines"] = {
        "step_windows": {"same_window": summarise([info[i]["clamps_same"] for i in step_w]), "preceding_cycle": summarise([info[i]["clamps_prev"] for i in step_w]),
                         "with_any_same_or_prev": sum(1 for i in step_w if info[i]["clamps_same"] + info[i]["clamps_prev"] > 0)},
        "step_free_windows": {"same_window": summarise([info[i]["clamps_same"] for i in free_w]), "preceding_cycle": summarise([info[i]["clamps_prev"] for i in free_w]),
                              "with_any_same_or_prev": sum(1 for i in free_w if info[i]["clamps_same"] + info[i]["clamps_prev"] > 0)}}
    res["step_positions_c"] = dict(Counter(c for i in step_w for c in steps[i]))
    res["dropish_lines_in_daemon_log"] = {"count": len(d["dropish"]), "note": "lines matching overflow|dropp|xrun|overrun|backlog|discard|underrun|DropOldest|stall in the whole daemon log (counts only)"}
    return res


def arecord_stderr_check(paths: list) -> dict:
    """(c): count 'overrun' and 'arecord' mentions in the kept logs. Absence confirms only that the instrument is blind (stderr piped, never read)."""
    out = {}
    pat = re.compile(r"overrun|arecord", re.I)
    for p in paths:
        if os.path.isfile(p):
            n = 0
            with open(p, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    n += 1 if pat.search(line) else 0
            out[os.path.basename(os.path.dirname(p)) + "/" + os.path.basename(p)] = n
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--shift", required=True)
    ap.add_argument("--daemon-log", required=True)
    ap.add_argument("--tz-h", type=float, default=2.0)
    ap.add_argument("--check-logs", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = run(a.runs, a.shift, a.daemon_log, a.tz_h)
    r["arecord_stderr_check_mentions_of_overrun_or_arecord"] = arecord_stderr_check(a.check_logs)
    json.dump(r, open(a.out, "w"), indent=1)
    print("step windows", r["step_windows"], "free", r["step_free_windows"], "no prev cycle line", r["windows_without_prev_cycle_line"])


if __name__ == "__main__":
    main()
