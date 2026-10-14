#!/usr/bin/env python
"""EARLY-DUP Part A0 (spec 2026-10-09-1025-architect-to-qa-spec-early-dup.md, amendment 1): a mechanical check on data on file. No station, no decode.

Counts and Hz only (HK-037): the S4 truth texts are compared INSIDE `s4_cycles` (distinct-text counts); nothing that leaves it contains text.

  A0-a  per S4 cycle (truth.csv of 2026-10-08-0a1ff63): signals, distinct texts, copies per text, pairwise spacings of the copies of one text (Hz).
  A0-b  every unconfirmed early row in BOTH fix-build S4 re-plays lies in a cycle with >= 1 repeated text. Frames are mapped to cycles by FRAME TIME (amendment 1):
        cycle start = floor((t - 5 s) / 15 s) x 15 s (an early frame arrives about 13 s into its cycle, the final frame about 15 s). The first re-play
        (2026-10-08-5989f5e, counts only) missed S4 cycle 1; the second (94b8199, classifier) covers all 15. NON-VACUOUS: needs >= 1 unconfirmed row to be TRUE.
  A0-c  every S4b FREQ_MISS delta-f lies within +-3 Hz of a pairwise truth spacing of its cycle (decoded frequencies are whole Hz from 3.125 Hz bins, so two decodes of
        copies a fixed distance apart can differ from it by about one bin; HK-038). NON-VACUOUS: needs >= 1 row. S4b recorded 3 rows; the first re-play recorded no delta-f.

  python qa/rr-study/early-dup/early_dup_a0.py     -> results/2026-10-09-early-dup/a0_result.json
"""
import csv
import collections
import datetime as dt
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RES = os.path.join(REPO, "qa", "rr-study", "results")
OUT = os.path.join(RES, "2026-10-09-early-dup")
TRUTH_RUN = "2026-10-08-0a1ff63"
PLAYS = {"first_replay": ("2026-10-08-5989f5e", "early_counts_s4.jsonl"), "S4b": ("2026-10-08-94b8199", "early_classify_s4.jsonl")}
TOL_HZ = 3.0
FRAME_OFFSET_S, CYCLE_S = 5.0, 15.0


def s4_cycles(truth_rows):
    """truth.csv dict rows -> {cycle_utc: {'signals', 'distinct', 'copies': sorted copies-per-text, 'spacings': sorted pairwise Hz between copies of one text}}.
    Texts are compared here and never returned."""
    by = collections.defaultdict(list)
    for r in truth_rows:
        if r["scenario_id"] == "S4":
            by[r["cycle_utc"]].append((r["message_text"], float(r["true_freq_hz"])))
    out = {}
    for c, rows in by.items():
        per = collections.defaultdict(list)
        for t, f in rows:
            per[t].append(f)
        sp = sorted({round(abs(a - b), 1) for fs in per.values() for a, b in itertools.combinations(fs, 2)})
        out[c] = {"signals": len(rows), "distinct": len(per), "copies": sorted(len(v) for v in per.values()), "spacings": sp}
    return out


def cycle_of(frame_utc, cycle_starts):
    """frame time (ISO, 'Z') -> the truth cycle_utc it belongs to, or None."""
    t = dt.datetime.strptime(frame_utc.rstrip("Z"), "%Y-%m-%dT%H:%M:%S.%f") if "." in frame_utc else dt.datetime.strptime(frame_utc.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
    secs = (t - dt.datetime(2000, 1, 1)).total_seconds() - FRAME_OFFSET_S
    start = dt.datetime(2000, 1, 1) + dt.timedelta(seconds=(secs // CYCLE_S) * CYCLE_S)
    key = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    return key if key in cycle_starts else None


def unconfirmed_by_cycle(frames, cycle_starts, kind="final"):
    """-> ({cycle_utc: unconfirmed rows}, covered cycles). Frames: the listener's counts-only rows ('final' in v1, 'cycle' in the classifier)."""
    got, cov = collections.Counter(), set()
    for fr in frames:
        if fr.get("kind") not in ("final", "cycle"):
            continue
        c = cycle_of(fr["utc"], cycle_starts)
        if c is None:
            continue
        cov.add(c)
        got[c] += int(fr.get("unconfirmed", 0))
    return dict(got), cov


def a0b(unc, cycles):
    """TRUE iff there is >= 1 unconfirmed row and every one lies in a cycle with a repeated text. -> (verdict, rows, rows_outside)."""
    rows = sum(unc.values())
    outside = sum(v for c, v in unc.items() if v and max(cycles[c]["copies"]) < 2)
    return (rows >= 1 and outside == 0), rows, outside


def a0c(frames, cycle_starts, cycles, tol=TOL_HZ):
    """every FREQ_MISS delta-f within tol of a pairwise spacing of its cycle. -> (verdict, rows, [per-row detail])."""
    detail = []
    for fr in frames:
        if fr.get("kind") != "cycle" or not fr.get("labels", {}).get("FREQ_MISS"):
            continue
        c = cycle_of(fr["utc"], cycle_starts)
        for d in fr.get("df_this_hz", []):
            sp = cycles[c]["spacings"] if c else []
            near = min((abs(d - s) for s in sp), default=None)
            detail.append({"cycle": c, "df_hz": d, "nearest_spacing_hz": near, "within_tol": near is not None and near <= tol})
    return (len(detail) >= 1 and all(x["within_tol"] for x in detail)), len(detail), detail


def load_frames(path):
    return [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]


def main():
    truth = s4_cycles(csv.DictReader(open(os.path.join(RES, TRUTH_RUN, "truth.csv"), encoding="utf-8")))
    order = sorted(truth)
    res = {"A0-a": [{"cycle": i + 1, "signals": truth[c]["signals"], "distinct_texts": truth[c]["distinct"], "copies_per_text": sorted(set(truth[c]["copies"])),
                     "spacings_hz": truth[c]["spacings"]} for i, c in enumerate(order)]}
    res["A0-b"] = {}
    for name, (run, fn) in PLAYS.items():
        t = s4_cycles(csv.DictReader(open(os.path.join(RES, run, "truth.csv"), encoding="utf-8")))
        starts = set(t)
        frames = load_frames(os.path.join(RES, run, fn))
        unc, cov = unconfirmed_by_cycle(frames, starts)
        ok, rows, outside = a0b(unc, t)
        res["A0-b"][name] = {"verdict": ok, "unconfirmed_rows": rows, "rows_in_cycles_without_a_repeated_text": outside, "cycles_covered": len(cov), "of": len(starts),
                             "unconfirmed_per_cycle": [unc.get(c, 0) for c in sorted(starts)]}
    run, fn = PLAYS["S4b"]
    t = s4_cycles(csv.DictReader(open(os.path.join(RES, run, "truth.csv"), encoding="utf-8")))
    ok, rows, detail = a0c(load_frames(os.path.join(RES, run, fn)), set(t), t)
    res["A0-c"] = {"verdict": ok, "rows": rows, "detail": detail}
    res["A0-b_overall"] = all(v["verdict"] for v in res["A0-b"].values())
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, "a0_result.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
