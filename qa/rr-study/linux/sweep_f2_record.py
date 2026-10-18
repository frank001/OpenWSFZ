#!/usr/bin/env python3
"""F2 record for ONE sweep, computed ON sol (QA 2026-10-18; Architect: third-pass sweeps, items 1-2). Aggregates and numeric files only (HK-037).

    python3 sweep_f2_record.py --run-dir <results/..-sweepN> --scratch <qa-scratch/s6-..-sweepN> --daemon-log <rr-run/<name>/daemon.stdout.log> [--statuspoll FILE.jsonl] [--out DIR]

Per PLAY of S6 pass O (any tier) (the OpenWSFZ pass), from the LAST daemon's log (the S6 pass-O daemon):
  - residual pass: wall ms and deadlineAbandoned, mapped to the play by its adjacent 'Cycle HH:MM:SS' line (the same rule as s6_analyse.read_pass_lines);
  - third pass: outcome, wall ms, new decodes, mapped the SAME way, kept as ITS OWN field beside the residual pass's, never folded into it (Architect);
  - clamped: 1 if a 'Cycle-grid realignment clamped' line immediately precedes that play's Cycle line (the clamp applies to the cycle that follows it, as traced by hand for B2CAPR);
  - channel drops whose 'at HH:MM:SS UTC' falls inside the play's 15 s window; arecord overrun and channel-drop deltas over that window from the 1 Hz status poll if present.
Then the Amendment-1 check of the B2CAPR ruling (section 3), per sweep: if any clamp falls on a play of S6 pass O, drop those plays' WAVs and compare OWS own-universe
consistency with a placebo of the same number of random WAVs (2,000 draws, seed 20261018); FLAG if the result lies outside the placebo p2.5 / p97.5. If no clamp falls on
a play, that is recorded and the check stops. Writes f2_per_play.csv and f2_record.json into --out (default: the run dir) and prints a summary.
"""
import argparse
import csv
import json
import os
import random
import re
import sys
from datetime import datetime, timezone

RR = "/home/claude/rr-work-b2/qa/rr-study"
sys.path[:0] = [RR + "/s6", RR]
import s6_analyse as A      # noqa: E402
import s6_stats as S        # noqa: E402

SEED, DRAWS = 20261018, 2000
START = "arecord stdout pipe enlarged"
CYCLE = re.compile(r"^\[\d\d:\d\d:\d\d \w+\] Cycle (\d\d):(\d\d):(\d\d): (\d+) decode\(s\) found")
CLAMP = re.compile(r"Cycle-grid realignment clamped")
PASS = re.compile(r"Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) deadlineAbandoned=(True|False) containedException=(True|False)")
THIRD = re.compile(r"Third pass: newDecodes=(\d+) elapsedMs=(\d+) outcome=(ran|skipped-no-new|skipped-abandoned|abandoned|failed) fittedSignals=(\d+)")
DROP = re.compile(r"Capture channel dropped a chunk at (\d\d):(\d\d):(\d\d)\.(\d+) UTC")


def sod_of(stamp):
    return int(stamp[7:9]) * 3600 + int(stamp[9:11]) * 60 + int(stamp[11:13])


def epoch_of(stamp):
    return datetime.strptime(stamp, "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc).timestamp()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--daemon-log", required=True)
    ap.add_argument("--statuspoll", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or a.run_dir
    rows = [json.loads(x) for x in open(os.path.join(a.run_dir, "s6", "s6_playlog.jsonl"), encoding="utf8")]
    plays = [r for r in rows if r["kind"] == "play"]
    assert plays, "no plays in s6_playlog.jsonl"      # 180 at the standard tier, 72 at the quick tier (the dry run), 36 at the smallest: no hard-coded count
    lines = open(a.daemon_log, encoding="utf-8", errors="replace").read().splitlines()
    starts = [i for i, x in enumerate(lines) if START in x]
    lines = lines[starts[-1]:] if starts else lines

    # walk the last daemon's log once: per cycle (by UTC time of day) what followed its Cycle line
    per_cycle, drops = {}, []
    cur, pending_clamp = None, False
    for x in lines:
        if CLAMP.search(x):
            pending_clamp = True
            continue
        m = CYCLE.match(x)
        if m:
            cur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            per_cycle[cur] = {"clamped": 1 if pending_clamp else 0, "resid_ms": None, "resid_abandoned": None, "third": None, "pass0": int(m.group(4))}
            pending_clamp = False
            continue
        if cur is not None:
            m = PASS.search(x)
            if m:
                per_cycle[cur]["resid_ms"], per_cycle[cur]["resid_abandoned"] = int(m.group(2)), 1 if (m.group(3) == "True" or m.group(4) == "True") else 0
                continue
            m = THIRD.search(x)
            if m:
                per_cycle[cur]["third"] = (m.group(3), int(m.group(2)), int(m.group(1)))
                continue
        m = DROP.search(x)
        if m:
            drops.append(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)))

    polls = []
    if a.statuspoll and os.path.isfile(a.statuspoll):
        polls = [j for j in (json.loads(l) for l in open(a.statuspoll, encoding="utf8")) if j.get("drops") is not None]

    def counter_at(key, t):
        before = [p for p in polls if p["t"] <= t]
        return before[-1].get(key) if before else None

    table, clamped_plays = [], []
    for p in plays:
        st = A.stamp_o(p)
        sod = sod_of(st)
        c = per_cycle.get(sod, {})
        # A play with no third-pass line is NOT an unknown: the decoder returns before the residual pass (and so before the third pass) when pass 0 found nothing, and logs neither
        # line. "no-pass0-decodes" = the Cycle line said 0 decodes (explained); "MISSING-LINE" = pass 0 had decodes yet no third-pass line (a defect to look at).
        th = c.get("third") or (("no-pass0-decodes" if c.get("pass0") == 0 else "MISSING-LINE") if c else "no-cycle-line", 0, 0)
        nd = sum(1 for d in drops if sod <= d < sod + 15)
        t0 = epoch_of(st)
        ov = None if not polls else _delta("overruns", polls, t0)
        dd = None if not polls else _delta("drops", polls, t0)
        table.append({"play": p["play_index"], "slot_o": st, "resid_ms": c.get("resid_ms"), "resid_abandoned": c.get("resid_abandoned"),
                      "third_outcome": th[0], "third_ms": th[1], "third_new": th[2], "clamped": c.get("clamped", 0), "drops_in_window": nd,
                      "poll_overruns_delta": ov, "poll_drops_delta": dd})
        if c.get("clamped"):
            clamped_plays.append(p)
    with open(os.path.join(out, "f2_per_play.csv"), "w", encoding="utf8", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)

    rec = {"plays": len(plays), "plays_with_clamped_cycle": len(clamped_plays), "clamped_play_indices": [p["play_index"] for p in clamped_plays],
           "plays_with_a_channel_drop": sum(1 for r in table if r["drops_in_window"]), "channel_drops_in_last_daemon_log": len(drops),
           "residual_abandoned_plays": sum(1 for r in table if r["resid_abandoned"]),
           "third_pass_outcomes": _count(r["third_outcome"] for r in table),
           "statuspoll_present": bool(polls)}
    if polls:
        rec["overruns_total_over_play_windows"] = sum(r["poll_overruns_delta"] or 0 for r in table)
        rec["drops_total_over_play_windows_poll"] = sum(r["poll_drops_delta"] or 0 for r in table)

    # Amendment 1 of the B2CAPR ruling: drop the clamped plays' WAVs, compare with a placebo of the same size
    if not clamped_plays:
        rec["amendment1_check"] = "no clamp fell on a play of S6 pass O: recorded, check not owed"
    else:
        wsjt, owsfz = A.parse_log(os.path.join(a.scratch, "wsjt-s6.txt")), A.parse_log(os.path.join(a.scratch, "owsfz-s6.txt"))
        obs = A.build_obs(plays, wsjt, owsfz, {})
        tallies = lambda excl: [S.wav_tally(d["trials"]) for w, d in sorted(obs.items()) if w not in excl]
        full = S.pool(tallies(set()))["consistency_own_owsfz"]
        wavs = {p["wav_id"] for p in clamped_plays}
        res = S.pool(tallies(wavs))["consistency_own_owsfz"]
        rnd, ids, vals = random.Random(SEED), sorted(obs), []
        for _ in range(DRAWS):
            vals.append(S.pool(tallies(set(rnd.sample(ids, len(wavs)))))["consistency_own_owsfz"])
        vals.sort()
        q = lambda f: 100 * vals[min(len(vals) - 1, int(f * len(vals)))]
        rec["amendment1_check"] = {"full_own_pct": round(100 * full, 2), "without_clamped_wavs_pct": round(100 * res, 2), "wavs_dropped": len(wavs),
                                   "delta_pp": round(100 * (res - full), 2), "placebo_p2_5_p50_p97_5": [round(q(.025), 2), round(q(.5), 2), round(q(.975), 2)],
                                   "draws_seed": [DRAWS, SEED],
                                   "verdict": "FLAG (outside the placebo p2.5/p97.5)" if (100 * res < q(.025) or 100 * res > q(.975)) else "inside the placebo: not flagged"}
    json.dump(rec, open(os.path.join(out, "f2_record.json"), "w"), indent=1)
    print(json.dumps(rec, indent=1))


def _count(it):
    d = {}
    for x in it:
        d[x] = d.get(x, 0) + 1
    return d


def _delta(key, polls, t0):
    def at(t):
        b = [p for p in polls if p["t"] <= t]
        return b[-1].get(key) if b else None
    a0, a1 = at(t0), at(t0 + 15)
    return None if a0 is None or a1 is None else a1 - a0


if __name__ == "__main__":
    main()
