"""CAPTURE-LOSS INSTRUMENT: rows O1-O7 and classes K1-K4 of the instrumented S6 block (QA tooling; Architect spec 2026-10-17-0927 sections 4-5 + amendment 1).

    python cl_rows.py --run DIR --audio DIR --corpus DIR --wavlist JSON --runs DIR --log daemon.stdout.log --out JSON

Inputs: the run folder (s6/s6_playlog.jsonl), the captured audio (OpenWSFZ cycle archive + WSJT-X save WAVs), the plan written by `ows_replay_consistency.py lists`,
the pass-O daemon log. Output: aggregates only (HK-037: overrun, drop and framer lines carry no message text; no decoded text is read here).

Frozen rules (spec + amendment 1):
  * Steps and J: exactly ows_step_test (J = p99.9 of THIS run's WSJT-X chunk-to-chunk |delta e|); B2BASE sweep-1 J = 0.01704 s is shown beside as sensitivity.
  * A step between chunk k and k+1 starts at chunk k+1 (ows_step_test.describe_steps); its interval is [cycle start + (k+1), cycle start + (k+2)) in UTC.
  * Overrun time = the UTC millisecond time in the Warning text. Anchor window +-2 s (primary); +-1 s and +-4 s are sensitivity only.
  * O1 = among windows with a step, the share with >= 1 overrun within the window of ANY of its steps. O2 = the same test on the same chunk positions in every step-free window
    (per step window, averaged over the step-free windows). Bootstrap: WAV-clustered, 2,000 resamples of the 60 WAVs, SEED below.
  * K1..K4: one class per STEP, first match wins (K1 overrun within +-2 s; K2 channel drop within +-2 s; K3 next window's `wanted` >= +0.2 s = 2400 samples; K4 none).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import ows_input_spread as I  # noqa: E402
import ows_shift_test as T  # noqa: E402
import ows_step_test as S  # noqa: E402

SEED = 20261017
N_BOOT = 2000
ANCHOR_S = 2.0
SENSITIVITY_S = (1.0, 4.0)
K3_WANTED_SAMPLES = 2400          # +0.2 s at 12 kHz (amendment 1, A2)
HIT_BAR = 0.80
J_SWEEP1 = 0.01703520000000426    # B2BASE sweep 1, shown beside only
RATE = 12000
CYCLE_S = 15
OVR_RE = re.compile(r"arecord overrun at (\d\d):(\d\d):(\d\d)\.(\d{3}) UTC: reported ([0-9.]+) ms \(overrun #(\d+), [0-9]+ ms reported in total\): (.*)$")
WIN_RE = re.compile(r"Window emitted \(\d+ samples, cycle (\d\d):(\d\d):(\d\d)\); wanted (-?\d+), applied (-?\d+) samples; consumed (\d+)")
DROP_RE = re.compile(r"channel.*dropp|dropped.*chunk", re.I)


def day_epoch(stamp: str) -> float:
    """UTC midnight (epoch s) of the date in a `YYMMDD_HHMMSS` stamp."""
    return I.stamp_to_epoch(stamp[:6] + "_000000")


def parse_log(path: str, day0: float) -> dict:
    overruns, windows, drops, unexpected = [], {}, [], 0
    for line in open(path, encoding="utf8", errors="replace"):
        m = OVR_RE.search(line)
        if m:
            h, mi, s, ms = (int(m.group(i)) for i in (1, 2, 3, 4))
            overruns.append({"t": day0 + h * 3600 + mi * 60 + s + ms / 1000.0, "reported_ms": float(m.group(5)), "n": int(m.group(6)), "text": m.group(7).strip()})
            continue
        m = WIN_RE.search(line)
        if m:
            h, mi, s = (int(m.group(i)) for i in (1, 2, 3))
            windows[day0 + h * 3600 + mi * 60 + s] = {"wanted": int(m.group(4)), "applied": int(m.group(5)), "consumed": int(m.group(6))}
            continue
        if "Capture ended unexpectedly" in line:
            unexpected += 1
        if " WRN]" in line and DROP_RE.search(line) and "arecord" not in line:
            drops.append(line.strip()[:120])
    return {"overruns": overruns, "windows": windows, "drops": drops, "unexpected_end_lines": unexpected}


def near(t_lo: float, t_hi: float, times: list, w: float) -> bool:
    return any(t_lo - w <= t <= t_hi + w for t in times)


def boot_ci(vals: np.ndarray) -> tuple:
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("--run", "--audio", "--corpus", "--wavlist", "--runs", "--log", "--out"):
        ap.add_argument(a, required=True)
    a = ap.parse_args()
    plan, po, pw = T.load_join(a.run, a.runs)
    wl = {it["id"]: it for it in json.load(open(a.wavlist, encoding="utf8"))["items"]}
    cache = {}

    def load(wid):
        if wid not in cache:
            it = wl[wid]
            cache[wid] = S.X.read_wav(os.path.join(a.corpus, "wsjt-x", it["run"], it["stamp"] + ".wav"))
        return cache[wid]
    c_o, _, _ = S.play_chunk_offsets(po, "boundary_utc_o", lambda p: os.path.join(a.audio, "owsfz", "wav", p["stamp"] + ".wav"), load)
    c_w, _, _ = S.play_chunk_offsets(pw, "boundary_utc", lambda p: os.path.join(a.audio, "wsjt-x", "wav", p["stamp"] + ".wav"), load)
    j_run = S.threshold_j(c_w)
    day0 = day_epoch(plan[0]["stamp_o"])
    lg = parse_log(a.log, day0)
    cs = {q["index"]: I.stamp_to_epoch(q["stamp_o"]) for q in plan}
    t_first, t_last = min(cs.values()), max(cs.values()) + CYCLE_S
    block_ov = [o for o in lg["overruns"] if t_first - 2 * CYCLE_S <= o["t"] <= t_last + 2 * CYCLE_S]
    ov_times = [o["t"] for o in block_ov]
    ov_all = [o["t"] for o in lg["overruns"]]
    drop_times = []   # no per-drop timestamps parsed (P5 log is a Warning; the count is read from status); see `drops` below
    n = len(plan)
    wav_ids = sorted({q["wav_id"] for q in plan})
    wav_of = {q["index"]: q["wav_id"] for q in plan}

    def per_j(j: float, window_s: float) -> dict:
        steps = {i: S.steps_of(c_o[i], j) for i in cs}                      # [(k, size)] per window
        pos = {i: [k + 1 for k, _ in steps[i]] for i in cs}                  # chunk k+1 is where the step starts
        # H[i][p] = an overrun within window_s of chunk p's 1 s interval in window i
        H = np.zeros((n, S.N_CHUNKS + 1), dtype=bool)
        for i in cs:
            for p in range(1, S.N_CHUNKS):
                H[i, p] = near(cs[i] + p, cs[i] + p + 1, ov_times, window_s)
        has = np.array([bool(steps[i]) for i in range(n)])
        o1_w = np.array([any(H[i, p] for p in pos[i]) if has[i] else False for i in range(n)])

        def rows_for(idx: np.ndarray) -> tuple:
            sw = [i for i in idx if has[i]]
            fw = [i for i in idx if not has[i]]
            if not sw or not fw:
                return None, None
            o1 = float(np.mean([o1_w[i] for i in sw]))
            o2 = float(np.mean([np.mean([any(H[f, p] for p in pos[i]) for f in fw]) for i in sw]))
            return o1, o2
        o1, o2 = rows_for(np.arange(n))
        rng = random.Random(SEED)
        by_wav = {w: [i for i in range(n) if wav_of[i] == w] for w in wav_ids}
        d, o1s, skipped = [], [], 0
        for _ in range(N_BOOT):
            idx = np.array([i for w in (rng.choice(wav_ids) for _ in wav_ids) for i in by_wav[w]])
            r1, r2 = rows_for(idx)
            if r1 is None:
                skipped += 1
                continue
            d.append(r1 - r2)
            o1s.append(r1)
        out = {"window_s": window_s, "J_s": j, "windows_with_step": int(has.sum()), "steps": int(sum(len(v) for v in steps.values())), "O1": o1, "O2": o2, "O1_minus_O2": (o1 - o2) if o1 is not None else None,
               "O1_minus_O2_CI95": boot_ci(np.array(d)) if d else None, "O1_CI95": boot_ci(np.array(o1s)) if o1s else None, "resamples_used": len(d), "resamples_skipped_no_step_or_no_free_window": skipped,
               "O1_hits": int(sum(1 for i in range(n) if o1_w[i])), "step_free_windows": int((~has).sum())}
        return out, steps, pos, H, has

    primary, steps, pos, H, has = per_j(j_run, ANCHOR_S)
    res = {"seed": SEED, "n_boot": N_BOOT, "J_run_s": j_run, "J_sweep1_s": J_SWEEP1, "anchor_s": ANCHOR_S, "plays": n, "wavs": len(wav_ids),
           "overruns_in_log_total": len(lg["overruns"]), "overruns_in_block": len(block_ov), "unexpected_end_lines": lg["unexpected_end_lines"], "channel_drop_warning_lines": len(lg["drops"]),
           "primary": primary, "sensitivity": {}}
    for jv, jn in ((j_run, "J_run"), (J_SWEEP1, "J_sweep1")):
        for w in ((ANCHOR_S,) + SENSITIVITY_S if jn == "J_run" else (ANCHOR_S,)):
            if jn == "J_run" and w == ANCHOR_S:
                continue
            r = per_j(jv, w)[0]
            res["sensitivity"]["%s_window_%gs" % (jn, w)] = r
    # ----- O3: overruns not within the window of any step
    step_ints = [(cs[i] + p, cs[i] + p + 1) for i in cs for p in pos[i]]
    o3 = []
    for o in block_ov:
        near_step = any(lo - ANCHOR_S <= o["t"] <= hi + ANCHOR_S for lo, hi in step_ints)
        if near_step:
            continue
        w_i = max((i for i in cs if cs[i] <= o["t"]), key=lambda i: cs[i], default=None)
        o3.append({"n": o["n"], "position_in_window_s": round(o["t"] - cs[w_i], 3) if w_i is not None else None, "reported_ms": o["reported_ms"]})
    res["O3"] = {"overruns_not_near_a_step": len(o3), "of_block_overruns": len(block_ov), "items": o3}
    # ----- O4: channel drops (count from the status counter is read separately; the Warning lines in the log are counted here)
    res["O4"] = {"channel_drop_warning_lines": len(lg["drops"]), "items": lg["drops"][:5]}
    # ----- O5 / K: next-window wanted
    wanted_next = {}
    for i in cs:
        nxt = lg["windows"].get(cs[i] + CYCLE_S)
        wanted_next[i] = nxt["wanted"] if nxt else None
    step_idx = [i for i in cs if has[i]]
    free_idx = [i for i in cs if not has[i]]
    cls = {"K1": 0, "K2": 0, "K3": 0, "K4": 0}
    per_step = []
    for i in step_idx:
        for (k, size), p in zip(steps[i], pos[i]):
            lo, hi = cs[i] + p, cs[i] + p + 1
            if near(lo, hi, ov_times, ANCHOR_S):
                c = "K1"
            elif near(lo, hi, drop_times, ANCHOR_S):
                c = "K2"
            elif wanted_next[i] is not None and wanted_next[i] >= K3_WANTED_SAMPLES:
                c = "K3"
            else:
                c = "K4"
            cls[c] += 1
            per_step.append({"play": i, "chunk": p, "size_s": round(size, 4), "class": c, "next_wanted_samples": wanted_next[i]})
    nsteps = len(per_step)
    res["K"] = {"steps": nsteps, "counts": cls, "shares": {k: (v / nsteps if nsteps else None) for k, v in cls.items()},
                "majority_class": next((k for k, v in cls.items() if nsteps and v / nsteps > 0.5), None)}
    free_w = [wanted_next[i] for i in free_idx if wanted_next[i] is not None]
    step_w = [wanted_next[i] for i in step_idx if wanted_next[i] is not None]
    res["O5"] = {"steps_windows_with_next_wanted": len(step_w), "share_ge_0p2s_after_step_windows": (sum(1 for x in step_w if x >= K3_WANTED_SAMPLES) / len(step_w)) if step_w else None,
                 "step_windows_next_wanted_samples_quantiles": [float(np.percentile(step_w, q)) for q in (0, 25, 50, 75, 100)] if step_w else None,
                 "stepfree_windows_with_next_wanted": len(free_w), "K3_control_share_ge_0p2s_in_stepfree_windows": (sum(1 for x in free_w if x >= K3_WANTED_SAMPLES) / len(free_w)) if free_w else None,
                 "stepfree_next_wanted_samples_quantiles": [float(np.percentile(free_w, q)) for q in (0, 25, 50, 75, 100)] if free_w else None}
    # ----- O6: step sizes
    sizes = np.array([abs(s["size_s"]) for s in per_step])
    res["O6"] = {"steps": nsteps, "median_abs_s": float(np.median(sizes)) if nsteps else None, "max_abs_s": float(sizes.max()) if nsteps else None,
                 "share_within_0.05s_of_0.25s": float((np.abs(sizes - 0.25) <= 0.05).mean()) if nsteps else None,
                 "share_within_0.05s_of_a_multiple_of_0.25s": float((np.abs(sizes / 0.25 - np.round(sizes / 0.25)) * 0.25 <= 0.05).mean()) if nsteps else None,
                 "reported_ms_of_all_block_overruns": [o["reported_ms"] for o in block_ov]}
    # ----- O7: step rate
    res["O7"] = {"windows_with_step": int(has.sum()), "of": n, "in_band_2_40": bool(2 <= int(has.sum()) <= 40), "sweep1": "21/180",
                 "wsjtx_windows_with_step_at_J_run": int(sum(1 for e in c_w.values() if S.steps_of(e, j_run)))}
    res["per_step"] = per_step
    with open(a.out, "w", encoding="utf8", newline="\n") as fh:
        json.dump(res, fh, indent=1, default=lambda o: None if (isinstance(o, float) and not math.isfinite(o)) else (o.tolist() if hasattr(o, "tolist") else str(o)))
    pr = res["primary"]
    print("J_run %.5f; windows with step %d/%d; steps %d; O1 %s O2 %s diff %s CI %s" % (j_run, pr["windows_with_step"], n, pr["steps"], pr["O1"], pr["O2"], pr["O1_minus_O2"], pr["O1_minus_O2_CI95"]))
    print("K", res["K"]["counts"], "majority", res["K"]["majority_class"], "| overruns in block", len(block_ov), "| O3", res["O3"]["overruns_not_near_a_step"])


if __name__ == "__main__":
    main()
