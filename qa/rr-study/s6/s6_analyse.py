"""S6 analysis (QA tooling; spec 2026-10-13-1625 + amendment 1): one parse of both ALL.TXT slices after the last play.

    python s6_analyse.py --run-dir <dir> --scratch <dir holding wsjt-s6.txt / owsfz-s6.txt> [--daemon-log <daemon.stdout.log>]
                         [--series-label "..."]

Reads <run-dir>/s6/{s6_playlog.jsonl, s6_validity.json, s6_window.json, s6_pins.json} and the two S6 log slices (message text: they live in
the scratch dir OUTSIDE git, HK-037) and writes, into <run-dir>/s6/, aggregates only: s6_result.json, s6_section5.md, s6_section6_row.md.
Attribution is by the line's slot stamp. Validity rows (a FAIL voids the S6 block only; S1-S8 stand):
  S6-V1 corpus verified (from the player)         S6-V2 (1) every play starts within OFFSET_TOLERANCE_S of its nominal offset,
  S6-V3 warm-up decoded by both (player)                  (2) 0 decode lines stamped in a slot with no play, 0 slots with two plays
  S6-V4 plays completed = tier x 3                S6-V5 pins equal at start and end (player)
  S6-V7 appraiser coverage (2026-10-14): every play slot has a WSJT-X save WAV and an OpenWSFZ archive cycle; 0 missing per appraiser
Mandatory field (Architect, amendment 1): the per-play OpenWSFZ abandonment (deadlineAbandoned) from the daemon log; the report gives S6 in
full AND over the WAVs with no abandoned play.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import s6_play as P  # noqa: E402
import s6_stats as S  # noqa: E402

PASS_LINE = re.compile(r"^\[(\d\d):(\d\d):(\d\d) \w+\] Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) deadlineAbandoned=(True|False) "
                       r"containedException=(True|False) fittedSignals=(\d+)")
ONSET_BAR_S = (0.0, 0.3)          # S6-V2(d) (Architect amendment 3, 2026-10-14): every read play's median DT shift (replay - live) lies in [0.0, +0.3] s. Source (HK-038): TWO S6 quick dry runs on sol
                                  # (10-13: 66 plays read, 10-14: 44 read; 110 plays: per-play median 0.1 or 0.2 s, median 0.1, max 0.2) = the observed maximum plus one 0.1 s DT reading step.
                                  # PILOT-DERIVED, not a derived bar; re-examined after the first standard-tier baseline sweep, before it is frozen. (Until 2026-10-14 the bar was [0.0, 0.2].)
ONSET_EPS = 1e-9
MIN_ATTRIBUTED_SHARE = 0.9       # a DESIGN number (Architect 2026-10-13: stays 90 %): the daemon-log attribution is trusted only if this share of the residual-pass LINES in the window maps to a play slot


# ------------------------------------------------------------------ reading the logs (text stays in these functions)

def parse_log(path: str) -> dict:
    """{slot stamp: [(freq_hz, snr_db, text)]} for the FT8 rows of an ALL.TXT slice."""
    from harness.common import parse_all_txt
    out = defaultdict(list)
    if not os.path.isfile(path):
        return out
    recs, _ = parse_all_txt(__import__("pathlib").Path(path))
    for r in recs:
        out[r.utc.strftime("%y%m%d_%H%M%S")].append((float(r.freq_hz), float(r.snr_db), " ".join(r.message.split()).upper()))
    return out


def key_rows(rows: list) -> tuple:
    """-> ({key: snr} for the non-hashed rows, n_hashed). key = (text, rank among same-text rows by frequency)."""
    hashed = sum(1 for _, _, t in rows if "<" in t)
    seen, out = Counter(), {}
    for f, snr, t in sorted((r for r in rows if "<" not in r[2]), key=lambda r: (r[2], r[0])):
        out[(t, seen[t])] = snr
        seen[t] += 1
    return out, hashed


def stamp_o(p: dict) -> str:
    """The slot in which OpenWSFZ heard this play. A concurrent S6 has one slot per play (both appraisers listened at once); a SEQUENTIAL S6 (s6_merge.py) played the
    identical schedule twice, so a play has the WSJT-X pass's slot (`slot_stamp`) and the OpenWSFZ pass's slot (`slot_stamp_o`)."""
    return p.get("slot_stamp_o", p["slot_stamp"])


def design_of(plays: list) -> str:
    return "sequential" if plays and all("slot_stamp_o" in p for p in plays) else "concurrent"


def build_obs(plays: list, wsjt: dict, owsfz: dict, abandoned: dict) -> dict:
    obs = {}
    for p in plays:
        w, hw = key_rows(wsjt.get(p["slot_stamp"], []))
        o, ho = key_rows(owsfz.get(stamp_o(p), []))
        d = obs.setdefault(p["wav_id"], {"band": p["band"], "sun": p["sun"], "trials": {}})
        d["trials"][p["trial"]] = {"w": w, "o": o, "hw": hw, "ho": ho, "order": p["order"], "abandoned": bool(abandoned.get(stamp_o(p)))}
    return obs


# ------------------------------------------------------------------ the daemon log: per-play abandonment

CYCLE_LINE = re.compile(r"^\[(\d\d):(\d\d):(\d\d) \w+\] Cycle (\d\d):(\d\d):(\d\d): (\d+) decode\(s\) found")
DAEMON_START = re.compile(r"Native FT8 decoder shim ABI version")
EARLY_DECODE = re.compile(r"\] Early decode: cycle=")


def read_pass_lines(path: str) -> list:
    """The residual-pass lines of a daemon log, each with `cycle_sod`: the UTC start (second of day) of the cycle of the nearest PRECEDING 'Cycle HH:mm:ss: N decode(s) found' line (Architect
    amendment 5, 2026-10-15; the daemon logs the cycle's own start there, in UTC, while every line's own stamp is LOCAL time). In the TWO-STAGE decode path (the product default; its log has
    'Early decode: cycle=' lines) the pass runs AFTER the Cycle line (Ft8Decoder.cs:747), so the preceding Cycle line is the pass's own cycle. A single-stage log runs the pass BEFORE the Cycle
    line (:546): there `cycle_sod` would be the previous cycle, so it is left None and only the formula attributes. The pairing resets at every daemon start."""
    out = []
    if not (path and os.path.isfile(path)):
        return out
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read().splitlines()
    two_stage = any(EARLY_DECODE.search(x) for x in text)
    cycle = None
    for line in text:
        if DAEMON_START.search(line):
            cycle = None
            continue
        m = CYCLE_LINE.match(line)
        if m:
            cycle = int(m.group(4)) * 3600 + int(m.group(5)) * 60 + int(m.group(6))
            continue
        m = PASS_LINE.match(line)
        if m:
            h, mi, s, rd, ms, ab, ce, fs = m.groups()
            out.append({"sod": int(h) * 3600 + int(mi) * 60 + int(s), "elapsed_ms": int(ms), "abandoned": ab == "True",
                        "exception": ce == "True", "fitted": int(fs), "residual_decodes": int(rd), "cycle_sod": cycle if two_stage else None})
    return out


def attribute_pass_lines(lines: list, play_slots: list, tz_offset_s: int | None = None) -> dict:
    """Which pass line belongs to which play slot (the abandonment field). THE RULE (Architect amendment 5, 2026-10-15): a pass line belongs to the cycle of its adjacent 'Cycle' line
    (`cycle_sod`, see read_pass_lines). The older FORMULA (Architect 2026-10-13) is kept as a CROSS-CHECK: a line stamped T (LOCAL, whole seconds) that took `elapsed` ms belongs to the slot
    floor((T - offset - elapsed) / 15) * 15 - 15. Where the formula and the Cycle line disagree the Cycle line wins, because the formula has whole-second resolution and a fast pass (OpenWSFZ
    alone on the CPU) can end just before the next boundary: its second line falls one slot early (desk check of the first sequential S6 run: 9 of 68 lines). ONE line stands for a slot:
    a second line for a slot, or a line in no play slot, is UNMAPPED (an abandoned line stands for its slot, which changes no count). TRUST (Architect amendment 6, which replaces amendment 5's "both
    agree" floor): the attribution is TRUSTED only if (a) the share of window pass lines that map to a play slot BY THEIR CYCLE LINE is at least MIN_ATTRIBUTED_SHARE, (b) no play slot has
    two lines by the Cycle line, (c) there is no UNEXPLAINED disagreement between the Cycle line and the formula (a disagreement is explained only if the formula's slot is exactly one slot
    before the Cycle line's slot AND T - elapsed lies within 1.0 s before the end of the Cycle line's cycle; a long pass that printed after the NEXT Cycle line must show up here), and (d) the
    time-zone cross-check holds (the system offset equals the whole-hour offset that attributes the most lines; amendment 2 (b)). Otherwise the field reads UNKNOWN (but see run(): the interim
    rule). A log with no usable Cycle lines (single-stage) uses the formula alone under the floor of amendment 2 (b).
    -> {"offset_h", "tz_offset_s", "inferred_offset_h", "attributed_plays", "by_slot": {slot_stamp: line}, "trusted", "reason", counts of agreeing / disagreeing lines, "window_abandoned_lines"}"""
    slot_sod = {}
    for st in play_slots:
        d = datetime.strptime(st, "%y%m%d_%H%M%S")
        slot_sod[st] = d.hour * 3600 + d.minute * 60 + d.second
    sod_to_slot = defaultdict(list)
    for st, sod in slot_sod.items():
        sod_to_slot[sod].append(st)

    def formula_sod(ln: dict, off_s: int) -> int:
        start = ((ln["sod"] - off_s) % 86400) - ln["elapsed_ms"] / 1000.0
        return int(math.floor(start / 15.0) * 15 - 15) % 86400

    best = (-1, None)
    for off in range(-14, 15):                                     # the time-zone cross-check: the whole-hour offset that places the most lines in play slots by the formula
        hit = {st for ln in lines for st in sod_to_slot.get(formula_sod(ln, 3600 * off), [])}
        if len(hit) > best[0]:
            best = (len(hit), off)
    inferred = best[1]
    if tz_offset_s is None:
        return {"offset_h": None, "tz_offset_s": None, "inferred_offset_h": inferred, "attributed_plays": 0, "by_slot": {}, "trusted": False,
                "reason": "no system time zone recorded at S6 start (s6_tz.json missing)"}

    def slot_of(ln: dict) -> int:
        c = ln.get("cycle_sod")
        return c if c is not None else formula_sod(ln, tz_offset_s)

    got, standing = {}, set()                                      # {slot stamp: the line standing for it}, ids of the standing lines
    for ln in lines:
        for st in sod_to_slot.get(slot_of(ln), []):
            if st not in got:
                got[st] = ln
            elif ln["abandoned"] and not got[st]["abandoned"]:
                got[st] = ln                                       # an abandoned line stands for its slot: an abandonment is never hidden behind a first line
    standing = {id(v) for v in got.values()}
    first, last = min(slot_sod.values()), max(slot_sod.values())
    in_window = [ln for ln in lines if first <= ((ln["sod"] - tz_offset_s) % 86400) - ln["elapsed_ms"] / 1000.0 - P.SLOT_S <= last + 2 * P.SLOT_S]
    play_sods = set(slot_sod.values())
    use_cycle = any(ln.get("cycle_sod") is not None for ln in in_window)
    counts = Counter(slot_of(ln) for ln in in_window if slot_of(ln) in play_sods)
    slots_with_two = sum(1 for c in counts.values() if c > 1)                          # (b) one parsed line per cycle per daemon, so two lines in one slot are an error
    cycle_mapped = [ln for ln in in_window if id(ln) in standing]
    agree = [ln for ln in in_window if id(ln) in standing and (ln.get("cycle_sod") is None or ln["cycle_sod"] == formula_sod(ln, tz_offset_s))]
    disagree = [ln for ln in in_window if ln.get("cycle_sod") is not None and ln["cycle_sod"] != formula_sod(ln, tz_offset_s)]

    def md(a: float, b: float) -> float:                                               # a - b on the 24 h circle, in [-12 h, +12 h)
        return ((a - b + 43200.0) % 86400.0) - 43200.0

    def explained(ln: dict) -> bool:
        """Architect amendment 6 (c): a disagreement is explained ONLY if the formula's slot is exactly one slot BEFORE the Cycle line's slot AND T - elapsed lies within 1.0 s before the END of
        the Cycle line's cycle. The bar is the 1 s resolution of the log stamp, not this run's 0.0-0.3 s. Anything else is unexplained (e.g. a long pass that printed after the NEXT Cycle line)."""
        c = ln["cycle_sod"]
        start = ((ln["sod"] - tz_offset_s) % 86400) - ln["elapsed_ms"] / 1000.0
        return md(formula_sod(ln, tz_offset_s), c) == -P.SLOT_S and -1.0 <= md(start, c + P.SLOT_S) < 0.0

    n_expl = sum(1 for ln in disagree if explained(ln))
    n_unexpl = len(disagree) - n_expl
    share_cycle = (len(cycle_mapped) / len(in_window)) if in_window else None         # (a)
    share_both = (len(agree) / len(in_window)) if in_window else None                  # recorded; no longer the floor's basis when the Cycle line is used
    tz_agrees = tz_offset_s % 3600 == 0 and tz_offset_s // 3600 == inferred           # (d)
    if use_cycle:
        failed = []
        if not (share_cycle is not None and share_cycle >= MIN_ATTRIBUTED_SHARE):
            failed.append("(a) %d of %d pass lines in the window map to a play slot by their Cycle line (floor %.0f %%)" % (len(cycle_mapped), len(in_window), 100 * MIN_ATTRIBUTED_SHARE))
        if slots_with_two:
            failed.append("(b) %d play slot(s) have two pass lines by the Cycle line" % slots_with_two)
        if n_unexpl:
            failed.append("(c) %d unexplained disagreement(s) between the Cycle line and the formula" % n_unexpl)
        if not tz_agrees:
            failed.append("(d) the system offset (%+d s) and the inferred offset (%+d h) disagree" % (tz_offset_s, inferred))
        trusted, reason = not failed, "; ".join(failed)
        share = share_cycle
        enough = not failed
    else:
        # a single-stage log (or none with usable Cycle lines): the formula alone, under amendment 2 (b)'s floor, one line per slot
        share = share_both
        enough = share is not None and share >= MIN_ATTRIBUTED_SHARE
        trusted = enough and tz_agrees
        reason = "" if trusted else ("%d of %d pass lines in the window map to a play slot (formula only)" % (len(agree), len(in_window)) if not enough else
                                     "the system offset (%+d s) and the inferred offset (%+d h) disagree" % (tz_offset_s, inferred))
    return {"offset_h": tz_offset_s / 3600.0, "tz_offset_s": tz_offset_s, "inferred_offset_h": inferred, "attributed_plays": len(got), "by_slot": got,
            "lines_in_window": len(in_window), "lines_mapped": len(cycle_mapped) if use_cycle else len(agree), "line_share": share_both,
            "lines_agree": len(agree), "lines_disagree": len(disagree), "disagree_explained": n_expl, "disagree_unexplained": n_unexpl,
            "lines_cycle_mapped": len(cycle_mapped), "share_cycle_mapped": share_cycle, "slots_with_two_lines": slots_with_two,
            "attribution": "the adjacent Cycle line (formula as cross-check)" if use_cycle else "formula only (no usable Cycle lines in the log)",
            "window_abandoned_lines": sum(1 for ln in in_window if ln["abandoned"]), "tz_agrees": tz_agrees, "trusted": trusted, "reason": reason}


# ------------------------------------------------------------------ validity rows

def v2_rows(plays: list, warm_slots: list, wsjt: dict, owsfz: dict, warm_slots_o: list | None = None) -> dict:
    """Concurrent S6: one set of slots for both logs. Sequential S6 (`slot_stamp_o` present): each log is checked against ITS OWN pass's slots (the WSJT-X pass's
    `slot_stamp` and warm-up; the OpenWSFZ pass's `slot_stamp_o` and warm-up `warm_slots_o`)."""
    offs = [p["offset_s"] for p in plays] + [p["offset_s_o"] for p in plays if "offset_s_o" in p]
    bad_off = [o for o in offs if abs(o - P.OFFSET_NOMINAL_S) > P.OFFSET_TOLERANCE_S]
    play_slots = [p["slot_stamp"] for p in plays]
    play_slots_o = [stamp_o(p) for p in plays]
    dup = [s for s, c in Counter(play_slots).items() if c > 1]
    if design_of(plays) == "sequential":                       # the OpenWSFZ pass has its own slots: no slot may hold two plays there either
        dup += [s for s, c in Counter(play_slots_o).items() if c > 1]
    ok_w = set(play_slots) | set(warm_slots)
    ok_o = set(play_slots_o) | set(warm_slots if warm_slots_o is None else warm_slots_o)
    stray = {"wsjtx": sum(len(rows) for s, rows in wsjt.items() if s not in ok_w), "owsfz": sum(len(rows) for s, rows in owsfz.items() if s not in ok_o)}
    # (a) the player's call time against the boundary is RETIRED AS A CHECK (Architect amendment 3, 2026-10-14): it reads the scheduler's own timestamp and was 0.000 s on all
    # 144 plays of two runs, so it cannot fail. `plays_outside_tolerance` stays in the row as a RECORD; the row's other checks (no slot with two plays, no stray lines) stand.
    passed = not dup and stray["wsjtx"] == 0 and stray["owsfz"] == 0
    return {"result": "PASS" if passed else "FAIL",
            "offset_tolerance_s": P.OFFSET_TOLERANCE_S, "offset_nominal_s": P.OFFSET_NOMINAL_S,
            "offset_min_s": min(offs) if offs else None, "offset_max_s": max(offs) if offs else None, "plays_outside_tolerance": len(bad_off),
            "slots_with_two_plays": len(dup), "stray_lines": stray}


def v7_row(plays: list, run_dir: str) -> dict:
    """S6-V7, appraiser coverage (Architect amendment 3, 2026-10-14; V6 is taken by the option-A loss-counter row). For EVERY play slot of the playlog:
    (a) WSJT-X has a save WAV for the slot and (b) OpenWSFZ's cycle archive has the cycle. BAR: 0 missing slots per appraiser (stricter than the S1-S8 coverage row's
    expected - 1 on purpose: the S6 design is balanced by WAV x trial, and the liveness gate already stops a stall of more than 45 s, so a gap without a stall is an anomaly).
    The slot lists come from run_study.py (`coverage_slots_wsjtx.txt`, `coverage_slots_owsfz.txt`). If the battery ran with the liveness gate (`liveness_gate.json`) the lists are
    REQUIRED and their absence FAILS; without the gate (older runs, desk runs) the row reads NOT MEASURED and does not void the block."""
    from harness import liveness as LV
    gate_on = os.path.isfile(os.path.join(run_dir, "liveness_gate.json"))
    want_by = {"wsjtx": [LV.stamp_to_iso(p["slot_stamp"]) for p in plays],            # sequential S6: each appraiser against the slots of ITS OWN pass
               "owsfz": [LV.stamp_to_iso(stamp_o(p)) for p in plays]}
    want = want_by["wsjtx"]
    out: dict = {"bar": "0 missing play slots per appraiser", "plays": len(want)}
    ok = True
    measured_any = False
    for key, fname in (("wsjtx", "coverage_slots_wsjtx.txt"), ("owsfz", "coverage_slots_owsfz.txt")):
        want = want_by[key]
        slots = LV.read_slots(os.path.join(run_dir, fname))
        if slots is None:
            out[key] = {"measured": False}
            if gate_on:
                ok = False
            continue
        measured_any = True
        missing = [w for w in want if w not in slots]
        out[key] = {"measured": True, "missing": len(missing), "first_missing": missing[:3]}
        ok = ok and not missing
    if not measured_any:
        out["result"] = "FAIL" if gate_on else "NOT MEASURED"
        out["reason"] = "the battery ran with the liveness gate but the coverage slot lists are missing" if gate_on else "no coverage slot lists in the run folder (the battery ran without --liveness-save-dir)"
    else:
        out["result"] = "PASS" if ok else "FAIL"
        if gate_on and not ok and not all(out[k].get("measured") for k in ("wsjtx", "owsfz")):
            out["reason"] = "one appraiser's slot list is missing although the gate was on"
    return out


def onset_check(onset: dict | None, checkable: bool) -> dict:
    """S6-V2(d): for every play with >= MIN_ROWS matched rows the per-play median DT shift lies in ONSET_BAR_S. Plays with fewer rows are counted, not read.
    FAIL if any read play is outside, or if the check can be made but NO play could be read. 'NOT CHECKED' only when no corpus was given (tests, desk runs)."""
    if not checkable:
        return {"result": "NOT CHECKED", "reason": "no corpus given: the live ALL.TXT of the source runs was not available", "bar_s": list(ONSET_BAR_S)}
    if not onset or "error" in onset or not onset.get("plays_with_median"):
        return {"result": "FAIL", "reason": "no play could be read (%s)" % (onset.get("error") if onset and "error" in onset else "fewer than %d matched rows in every play" % (onset or {}).get("min_rows_per_play", 3)),
                "bar_s": list(ONSET_BAR_S)}
    pm = onset["per_play_median_shift_s"]
    ok = pm["min"] >= ONSET_BAR_S[0] - ONSET_EPS and pm["max"] <= ONSET_BAR_S[1] + ONSET_EPS
    return {"result": "PASS" if ok else "FAIL", "plays_read": onset["plays_with_median"], "plays_not_read": onset["plays_without_enough_rows"], "min_s": pm["min"], "max_s": pm["max"],
            "bar_s": list(ONSET_BAR_S), "min_rows_per_play": onset["min_rows_per_play"]}


def decode_summary(tallies_all: list) -> dict:
    return S.pool(tallies_all)


# ------------------------------------------------------------------ report text

def pct(x, d=1):
    return "n/a" if x is None else ("%.*f %%" % (d, 100 * x))


def ci_txt(c, scale=100.0, d=1, unit=" %"):
    return "" if not c else " [%.*f, %.*f]" % (d, c[0] * scale, d, c[1] * scale) if unit == " %" else " [%.*f, %.*f]" % (d, c[0], d, c[1])


def fmt_block(res: dict, label: str) -> str:
    L = []
    A = L.append
    v = res["validity"]
    seq = res.get("design") == "sequential"
    A("### S6 — Off-air WAV replay (K = 3, " + ("SEQUENTIAL: WSJT-X and OpenWSFZ each played the identical schedule in turn, one appraiser at a time)" if seq
                                               else "WSJT-X and OpenWSFZ listening to each playback at once)"))
    A("")
    if seq:
        A("*Sequential design (Captain, 2026-10-15). Played together, WSJT-X's Qt ALSA capture stopped delivering audio after OpenWSFZ's residual pass delayed its capture thread "
          "(sol, B2BASE sweep 1 and the isolation runs), so S6 is played twice with one appraiser listening each time: first WSJT-X alone, then OpenWSFZ alone, the same WAVs in the same "
          "order and the same slots of the schedule, at different clock times. The two appraisers therefore heard two separate captures of the same recording (codec noise and timing "
          "differ slightly) and OpenWSFZ ran in a fresh process. **Not pooled with a concurrent S6 row.** S6-V2 stray lines, S6-V3 and S6-V7 are judged per pass. "
          "Every figure marked † compares the two programs: in this design the appraiser effect is the program AND the pass together, **not separable**. Within-appraiser figures keep their meaning.*")
        A("")
    A("**%s.** Tier **%s**: %d WAVs x %d trials = %d plays on the 15 s grid; source = the WSJT-X-side WAV of the frozen reference-set corpus; peak-normalised to 0.9 as every scenario. "
      "No truth is assumed: the figures measure repeatability and reproducibility, not recall. Informational on its first battery." % (label, res["tier"], res["wavs"], S.K, res["plays"]))
    A("")
    od = v["S6-V2"].get("onset", {})
    A("**Validity** (a FAIL withholds this block only, the rest of the battery stands): " + "; ".join("%s %s" % (k, v[k]["result"]) for k in ("S6-V1", "S6-V2", "S6-V3", "S6-V4", "S6-V5", "S6-V7") if k in v)
      + ". **S6-V2(d) onset: %s**%s" % (od.get("result", "?"), (" (per-play median DT shift of %s plays read, min %+.1f, max %+.1f s, bar [%+.1f, %+.1f] s; %s plays not read)" % (
          od.get("plays_read"), od.get("min_s"), od.get("max_s"), od["bar_s"][0], od["bar_s"][1], od.get("plays_not_read")) if od.get("result") in ("PASS", "FAIL") and "plays_read" in od else
          (" (%s)" % od.get("reason") if od.get("reason") else ""))))
    A("")
    if res["status"] != "VALID":
        A("**S6 block WITHHELD: %s.** The rows above say which check failed; the figures below are not to be read." % res["status"])
        return "\n".join(L) + "\n"
    full = res["full"]
    A("**CPU and chain label:** %s. OpenWSFZ ran the product path with the subtraction deadline ON (per-play abandonment: %s). Load average (1 / 5 / 15 min) at the start of the plays %s and at the end %s." % (
        res["cpu_chain_label"], res["abandonment"]["summary"], res["pins"].get("start", {}).get("loadavg_1_5_15"), res["pins"].get("end", {}).get("loadavg_1_5_15")))
    ab = res["abandonment"]
    if seq:
        lib = (v.get("S6-V5") or {}).get("pass_o_daemon_library") or {}
        A("")
        A("**Library loaded by the fresh pass-O daemon** (read from the live process, once for this S6): `%s`, SHA-256 `%s` (pid %s); S6-V5 %s." % (
            lib.get("path"), lib.get("sha256"), lib.get("pid"), (v.get("S6-V5") or {}).get("result")))
        A("")
        A("*The abandonment count below is for the SEQUENTIAL design (OpenWSFZ alone on the CPU) and is NOT comparable with the concurrent 10-14 dry run's 0 of 68.*")
    A("")
    A("*Daemon-log attribution (Architect amendment 5): each pass line belongs to the cycle of its adjacent Cycle line (%s); the older formula is the cross-check: both rules agree on %s lines and disagree on %s (%s explained, %s unexplained). %s of %s residual-pass lines in the window map to a play slot by the rule above = %s (floor %.0f %%; by the formula and the Cycle line together %s; plays slots with two lines: %s). Trusted only if that share holds, no slot has two lines, no disagreement is unexplained (explained = the formula one slot early and T - elapsed within 1.0 s before the cycle's end) and the time zone checks out; a pass runs on only some cycles, here %s of %s plays have a line, and no line means no pass ran). Play-start offset, player call time (S6-V2 a; it cannot see the sound's onset, see the onset row): min %s s, max %s s, tolerance ±%.2f s (a design number).*" % (
        ab.get("attribution"), ab.get("lines_agree"), ab.get("lines_disagree"), ab.get("disagree_explained"), ab.get("disagree_unexplained"), ab.get("pass_lines_mapped"), ab.get("pass_lines_in_window"),
        pct(ab.get("share_cycle_mapped") if ab.get("share_cycle_mapped") is not None else ab.get("pass_line_share")), 100 * MIN_ATTRIBUTED_SHARE, pct(ab.get("lines_agree") / ab["pass_lines_in_window"]) if ab.get("pass_lines_in_window") else "n/a",
        ab.get("slots_with_two_lines"),
        ab["plays_with_pass_line"], res["plays"], v["S6-V2"]["offset_min_s"], v["S6-V2"]["offset_max_s"], P.OFFSET_TOLERANCE_S))
    if not v["S6-V5"].get("wsjtx_exe_pinned", False):
        A("")
        A("*The WSJT-X executable was not pinned by hash on this row (no path given): only the OpenWSFZ library is pinned.*")
    A("")
    for name, blk, boot in (("All plays", full, res["bootstrap_full"]), ("Sensitivity: WAVs with no abandoned play", res.get("no_abandon"), res.get("bootstrap_no_abandon"))):
        if not blk or not blk.get("headline"):
            A("**%s:** not available (%s)." % (name, res.get("no_abandon_note", "no data")))
            A("")
            continue
        if res["abandonment"].get("interim_rule") and name.startswith("Sensitivity"):
            A("*The abandonment field reads 0 by the interim rule (Architect amendment 5): no parsed pass line in the S6 window has deadlineAbandoned=True, so the sensitivity below equals the full figure.*")
            A("")
        h, b = blk["headline"], boot["headline"] if boot else {}
        A("**%s** (%d WAVs, %d signals in the non-hashed universe; WAV-clustered 95 %% CIs)" % (name, h["wavs"], h["signals_in_universe"]))
        A("")
        A("| figure | WSJT-X | OpenWSFZ |")
        A("|---|---|---|")
        A("| within-appraiser consistency, own universe (decoded in all 3 of the trials it decoded in at least once) | %s%s | %s%s |" % (
            pct(h["consistency_own_wsjtx"]), ci_txt(b.get("consistency_own_wsjtx")), pct(h["consistency_own_owsfz"]), ci_txt(b.get("consistency_own_owsfz"))))
        A("| within-appraiser consistency, legacy (union universe; comparable with the 2026-06/07 rows) | %s%s | %s%s |" % (
            pct(h["consistency_legacy_wsjtx"]), ci_txt(b.get("consistency_legacy_wsjtx")), pct(h["consistency_legacy_owsfz"]), ci_txt(b.get("consistency_legacy_owsfz"))))
        A("| decodes per WAV (non-hashed, mean of 3 trials) | %.2f%s | %.2f%s |" % (
            h["decodes_per_wav_wsjtx"], ci_txt(b.get("decodes_per_wav_wsjtx"), 1, 2, ""), h["decodes_per_wav_owsfz"], ci_txt(b.get("decodes_per_wav_owsfz"), 1, 2, "")))
        A("")
        dag = " †" if seq else ""
        A("- **Positive agreement between the appraisers**%s (rows both decoded / rows either decoded, per trial): **%s%s**." % (dag, pct(h["positive_agreement"]), ci_txt(b.get("positive_agreement"))))
        A("- Decodes per WAV, OpenWSFZ minus WSJT-X%s: %+.2f%s." % (dag, h["decodes_per_wav_diff_owsfz_minus_wsjtx"], ci_txt(b.get("decodes_per_wav_diff_owsfz_minus_wsjtx"), 1, 2, "")))
        if h.get("snr_delta_mean") is not None:
            A("- SNR delta (OpenWSFZ − WSJT-X)%s over %d matched pairs: mean %+.2f dB%s, SD %.2f dB." % (dag, h["snr_delta_n"], h["snr_delta_mean"], ci_txt(b.get("snr_delta_mean"), 1, 2, ""), h.get("snr_delta_sd", float("nan"))))
        k = blk["kappa"]
        A("- Cohen's κ%s (union universe over trials): %s %s (rows %s). *The both-negative cell exists only through trial-to-trial flicker, so κ mostly measures that; read it with the positive-agreement share.*" % (dag, k.get("kappa"), k.get("ci95_asymptotic"), k.get("rows")))
        g = h.get("anova")
        if g and "error" not in g:
            sv, bb = g["pct_study_var"], boot["anova"] if boot else {}
            A("")
            A("**Gage R&R ANOVA on SNR** (AIAG crossed, with interaction): %d parts of %d candidate signals (those both appraisers decoded in every trial; *conditional on detection, so repeatability is understated and ndc overstated*)." % (h["anova_parts"], h["signals_in_universe"]))
            A("")
            A("| component | %StudyVar | 95 % CI |")
            A("|---|---|---|")
            for key, nm in (("EV", "repeatability (EV)"), ("AV", "appraiser (AV)" + dag), ("INT", "part × appraiser (INT)" + dag), ("RR", "total R&R" + dag), ("PV", "part-to-part (PV)")):
                A("| %s | %.1f %% | %s |" % (nm, sv[key], ("[%.1f, %.1f]" % tuple(bb["pct_study_var/" + key])) if bb.get("pct_study_var/" + key) else "n/a"))
            A("")
            A("ndc %.1f%s; appraiser means%s %.2f / %.2f dB (WSJT-X / OpenWSFZ)." % (g["ndc"], (" [%.1f, %.1f]" % tuple(bb["ndc"])) if bb.get("ndc") else "", dag, g["appraiser_means_db"][0], g["appraiser_means_db"][1]))
        A("")
    on = res.get("onset")
    A("")
    if on and "error" not in on and on.get("plays_with_median"):
        pm = on["per_play_median_shift_s"]
        A("**Sound onset, from WSJT-X's own DT** (DT of the replay minus DT of the live decode of the same recording, per play; the delay the replay chain added; positive = later): median of the per-play medians **%+.2f s** (P10 %+.2f, P90 %+.2f, min %+.2f, max %+.2f) over %d plays with at least %d matched rows (%d rows in all). Descriptive, no bar yet; the keep-up run read +0.1 s." % (
            pm["median"], pm["p10"], pm["p90"], pm["min"], pm["max"], on["plays_with_median"], on["min_rows_per_play"], on["rows_matched"]))
    else:
        A("**Sound onset, from WSJT-X's own DT:** not computed (%s)." % (("error " + on["error"]) if on and "error" in on else "no corpus or too few matched rows"))
    A("")
    A("**Hashed rows** (excluded from every figure above): WSJT-X %.2f and OpenWSFZ %.2f per play." % (res["hashed_per_play"]["wsjtx"], res["hashed_per_play"]["owsfz"]))
    oe, te = res["order_effect"], res["trial_effect"]
    A("")
    A("**Order effect** (Spearman, position in trial vs decodes per play): WSJT-X ρ %s (p %s), OpenWSFZ ρ %s (p %s)." % (oe["wsjtx"]["rho"], oe["wsjtx"]["p"], oe["owsfz"]["rho"], oe["owsfz"]["p"]))
    A("")
    A("**Trial-index effect** (mean non-hashed decodes per play, trial 1 / 2 / 3): WSJT-X %s; OpenWSFZ %s. Paired difference trial 3 − trial 1: WSJT-X %+.2f %s, OpenWSFZ %+.2f %s." % (
        te["wsjtx"]["mean_by_trial"], te["owsfz"]["mean_by_trial"], te["wsjtx"]["diff_trial2_minus_trial0"]["mean"], te["wsjtx"]["diff_trial2_minus_trial0"]["ci95"],
        te["owsfz"]["diff_trial2_minus_trial0"]["mean"], te["owsfz"]["diff_trial2_minus_trial0"]["ci95"]))
    if res.get("per_band"):
        A("")
        A("**Per band** (descriptive; %s):" % res["per_band_note"])
        A("")
        A("| band | WAVs | consistency WSJT-X | consistency OpenWSFZ | positive agreement | decodes/WAV WSJT-X | decodes/WAV OpenWSFZ |")
        A("|---|---|---|---|---|---|---|")
        for band, r in res["per_band"].items():
            A("| %s | %d | %s | %s | %s | %.2f | %.2f |" % (band, r["wavs"], pct(r["consistency_own_wsjtx"]), pct(r["consistency_own_owsfz"]), pct(r["positive_agreement"]), r["decodes_per_wav_wsjtx"], r["decodes_per_wav_owsfz"]))
    A("")
    if res.get("figure"):
        A("")
        A("![S6 six-panel figure](s6/%s)" % res["figure"])
        A("")
    A("Counts by sun state of the WAVs played: %s. Per-WAV gain applied before playback is in `s6-wavlist.json`." % res["sun_counts"])
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ main

def alsa_chain_label(asoundrc: str | None = None) -> str:
    """The ALSA capture chain, read from the host's ~/.asoundrc: the corrected chain sets rate_converter "samplerate_best" (the default `linear` converter reads OpenWSFZ's SNR about 4.5 dB
    low, product issue #234; linux/README.md item 6). Never typed: an unreadable file says so."""
    p = asoundrc or os.path.expanduser("~/.asoundrc")
    try:
        txt = open(p, encoding="utf8", errors="replace").read()
    except OSError:
        return "ALSA chain NOT READ (no ~/.asoundrc)"
    m = re.search(r'rate_converter\s+"?([A-Za-z_]+)"?', txt)
    return ("non-default ALSA chain (rate_converter %s)" % m.group(1)) if m else "default ALSA chain (no rate_converter set)"


def describe_chain(run_dir: str, design: str = "concurrent") -> str:
    """The CPU / thread label of the block, from the RUN'S OWN arm_config.json and /proc/cpuinfo (never typed): the Architect's rule (2026-10-13) is that the
    dry run says 'subtractionMaxThreads N (station value, not auto)' and claims nothing about the default set-up."""
    cpus = os.cpu_count() or 0
    model = ""
    try:
        with open("/proc/cpuinfo", encoding="utf8", errors="replace") as fh:
            for line in fh:
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    threads = None
    try:
        threads = json.load(open(os.path.join(run_dir, "arm_config.json"), encoding="utf8"))["daemon"]["decoder_readback"].get("subtractionMaxThreads")
    except (OSError, KeyError, ValueError, TypeError):
        pass
    auto = max(1, cpus - 2) if cpus else None
    if threads is None:
        t = "subtractionMaxThreads NOT READ BACK"
    elif threads == 0:
        t = "subtractionMaxThreads 0 (auto = %s on %s CPUs)" % (auto, cpus)
    else:
        t = "subtractionMaxThreads %s on %s CPUs (as configured; auto would give %s)%s" % (threads, cpus, auto, " (station value, not auto)" if threads != auto else " (= auto)")
    if design == "sequential":
        # Architect amendment 4 (2026-10-15), 1b: "<host>, <CPU>, subtraction deadline ON, SEQUENTIAL (each appraiser alone on the CPU), <ALSA chain>". Every part is READ, none typed.
        import socket
        return "%s, %s, subtraction deadline ON, %s, SEQUENTIAL (each appraiser alone on the CPU), %s" % (socket.gethostname(), model or "host CPU unknown", t, alsa_chain_label())
    return "%s, subtraction deadline ON, %s, WSJT-X decoding on the same CPUs; a drop on the capture path would be SILENT (no counter or log line exists)" % (model or "host CPU unknown", t)


def run(run_dir: str, scratch: str, daemon_log: str | None, series_label: str, cpu_chain_label: str | None = None, n_boot: int = S.BOOT_N,
        corpus: str | None = None, wavlist_path: str | None = None) -> dict:
    s6 = os.path.join(run_dir, "s6")
    rows = [json.loads(x) for x in open(os.path.join(s6, "s6_playlog.jsonl"), encoding="utf8")]
    plays = [r for r in rows if r["kind"] == "play"]
    design = design_of(plays)
    # the warm-up rows of a sequential S6 are tagged with their pass ("w" = the WSJT-X pass, "o" = the OpenWSFZ pass); a concurrent S6's have no tag and serve both logs
    warm_slots = [r["slot_stamp"] for r in rows if r["kind"] == "warmup" and r.get("pass", "w") == "w"]
    warm_slots_o = [r["slot_stamp"] for r in rows if r["kind"] == "warmup" and r.get("pass", "o") == "o"]
    vp = os.path.join(s6, "s6_validity.json")
    # the player writes s6_validity.json on every exit it controls; a killed or crashed player leaves none: the block is VOID, not a crash
    validity = json.load(open(vp, encoding="utf8")) if os.path.isfile(vp) else {"tier": "unknown", "plays_planned": 0, "player_did_not_finish": True}
    window = json.load(open(os.path.join(s6, "s6_window.json"), encoding="utf8")) if os.path.isfile(os.path.join(s6, "s6_window.json")) else {}
    slices_present = os.path.isfile(os.path.join(scratch, "wsjt-s6.txt")) and os.path.isfile(os.path.join(scratch, "owsfz-s6.txt"))
    wsjt, owsfz = parse_log(os.path.join(scratch, "wsjt-s6.txt")), parse_log(os.path.join(scratch, "owsfz-s6.txt"))
    pins_file = os.path.join(s6, "s6_pins.json")
    pins = json.load(open(pins_file, encoding="utf8")) if os.path.isfile(pins_file) else {}
    cpu_chain_label = cpu_chain_label or describe_chain(run_dir, design)
    tier = validity["tier"]
    expected = validity["plays_planned"]
    v = {"S6-V1": validity.get("S6-V1", {"result": "MISSING"}), "S6-V3": validity.get("S6-V3", {"result": "MISSING"}), "S6-V5": validity.get("S6-V5", {"result": "MISSING"})}
    v["S6-V2"] = v2_rows(plays, warm_slots, wsjt, owsfz, warm_slots_o)
    onset = None
    can_check_onset = bool(corpus and wavlist_path and os.path.isfile(wavlist_path) and slices_present)
    if can_check_onset:
        try:
            import s6_onset
            onset = s6_onset.onset_row(plays, os.path.join(scratch, "wsjt-s6.txt"), corpus, json.load(open(wavlist_path, encoding="utf8")))
        except Exception as exc:                                    # never costs the other numbers, but the check then FAILS (it could not be made)
            onset = {"error": type(exc).__name__}
    v["S6-V2"]["onset"] = onset_check(onset, can_check_onset)
    if v["S6-V2"]["onset"]["result"] == "FAIL":
        v["S6-V2"]["result"] = "FAIL"
    # a block built on NO log lines is not a result: the split step may have failed (the first dry run's KeyError left the slices missing and the block read VALID)
    if not slices_present or sum(len(r) for r in wsjt.values()) + sum(len(r) for r in owsfz.values()) == 0:
        v["S6-V2"]["result"] = "FAIL"
        v["S6-V2"]["logs"] = "S6 log slices missing" if not slices_present else "both S6 log slices are empty"
    v["S6-V4"] = {"result": "PASS" if (len(plays) == expected and not validity.get("player_did_not_finish")) else "FAIL", "plays": len(plays), "expected": expected,
                  **({"note": "the player did not finish (no s6_validity.json)"} if validity.get("player_did_not_finish") else {})}
    v["S6-V7"] = v7_row(plays, run_dir)
    okr = lambda k: v[k]["result"] == "PASS" or (k == "S6-V7" and v[k]["result"] == "NOT MEASURED")
    ok = all(okr(k) for k in v)
    status = "VALID" if ok else "VOID: " + ", ".join("%s %s" % (k, v[k]["result"]) for k in v if not okr(k))
    res = {"tier": tier, "status": status, "design": design, "validity": v, "onset": onset, "plays": len(plays), "wavs": len({p["wav_id"] for p in plays}), "series_label": series_label,
           "cpu_chain_label": cpu_chain_label, "window": window, "pins": pins}
    if ok:
        tzp = os.path.join(s6, "s6_tz.json")
        tz_s = json.load(open(tzp, encoding="utf8"))["gmtoff_s"] if os.path.isfile(tzp) else None
        pl = (attribute_pass_lines(read_pass_lines(daemon_log), [stamp_o(p) for p in plays], tz_s) if daemon_log      # the daemon ran in the OpenWSFZ pass's slots
              else {"trusted": False, "by_slot": {}, "attributed_plays": 0, "offset_h": None, "inferred_offset_h": None, "reason": "no daemon log"})
        ab = {s: ln["abandoned"] for s, ln in pl["by_slot"].items()} if pl["trusted"] else {}
        n_ab = sum(1 for x in ab.values() if x)
        # INTERIM RULE (Architect amendment 5, ruling 2, mechanical): if the floor is not met but NO parsed pass line inside the S6 window has deadlineAbandoned=True (and the time zone checks
        # out, so the window is the right one), the field reads 0 and needs no attribution; the no-abandonment sensitivity then equals the full figure, and the block says so.
        interim = (not pl["trusted"]) and bool(pl.get("tz_agrees")) and (pl.get("lines_in_window") or 0) > 0 and pl.get("window_abandoned_lines") == 0
        res["abandonment"] = {"daemon_log_attributed": pl["trusted"], "plays_with_pass_line": pl["attributed_plays"], "pass_lines_in_window": pl.get("lines_in_window"), "pass_lines_mapped": pl.get("lines_mapped"),
                              "pass_line_share": pl.get("line_share"), "plays_abandoned": n_ab if pl["trusted"] else (0 if interim else None),
                              "interim_rule": interim, "attribution": pl.get("attribution"), "lines_agree": pl.get("lines_agree"), "lines_disagree": pl.get("lines_disagree"),
                              "lines_cycle_mapped": pl.get("lines_cycle_mapped"), "share_cycle_mapped": pl.get("share_cycle_mapped"), "window_abandoned_lines": pl.get("window_abandoned_lines"),
                              "disagree_explained": pl.get("disagree_explained"), "disagree_unexplained": pl.get("disagree_unexplained"), "slots_with_two_lines": pl.get("slots_with_two_lines"),
                              "tz_offset_h_system": pl["offset_h"], "tz_offset_h_inferred": pl.get("inferred_offset_h"), "not_trusted_because": pl.get("reason", ""),
                              "elapsed_ms_median": float(np.median([ln["elapsed_ms"] for ln in pl["by_slot"].values()])) if pl["trusted"] and pl["by_slot"] else None,
                              "fitted_signals_median": float(np.median([ln["fitted"] for ln in pl["by_slot"].values()])) if pl["trusted"] and pl["by_slot"] else None}
        res["abandonment"]["summary"] = (("%d of %d plays abandoned" % (n_ab, len(plays))) if pl["trusted"] else
                                         (("0 of %d plays abandoned (no abandoned line in the window; attribution not needed)" % len(plays)) if interim else
                                          "UNKNOWN (%s): no sensitivity is given" % (pl.get("reason") or "the log could not be matched to the plays")))
        obs = build_obs(plays, wsjt, owsfz, ab)
        tallies_by_wav = {w: S.wav_tally(o["trials"]) for w, o in obs.items()}
        tall = [tallies_by_wav[w] for w in sorted(tallies_by_wav)]
        res["full"] = {"headline": S.pool(tall), "kappa": S.kappa_legacy(tall)}
        res["bootstrap_full"] = S.bootstrap(tall, n_boot)
        if pl["trusted"]:
            keep = [w for w in sorted(obs) if not any(t["abandoned"] for t in obs[w]["trials"].values())]
            res["no_abandon_wavs"] = {"kept": len(keep), "of": len(obs)}
            if len(keep) >= 8:
                tk = [tallies_by_wav[w] for w in keep]
                res["no_abandon"] = {"headline": S.pool(tk), "kappa": S.kappa_legacy(tk)}
                res["bootstrap_no_abandon"] = S.bootstrap(tk, n_boot)
            else:
                res["no_abandon_note"] = "only %d WAVs have no abandoned play" % len(keep)
        elif interim:
            res["no_abandon_wavs"] = {"kept": len(obs), "of": len(obs)}
            res["no_abandon"], res["bootstrap_no_abandon"] = res["full"], res["bootstrap_full"]
            res["no_abandon_note"] = "equals the full figure: no abandoned line in the window"
        else:
            res["no_abandon_note"] = res["abandonment"]["summary"]
        res["hashed_per_play"] = {"wsjtx": sum(t["hw"] for o in obs.values() for t in o["trials"].values()) / max(1, len(plays)),
                                  "owsfz": sum(t["ho"] for o in obs.values() for t in o["trials"].values()) / max(1, len(plays))}
        try:
            import s6_figure
            res["figure"] = s6_figure.make_figure(os.path.join(s6, "s6_figure.png"), obs, tall, res["full"]["headline"], res["bootstrap_full"])
        except Exception as exc:                                            # a figure problem never costs the numbers
            res["figure"] = None
            res["figure_error"] = type(exc).__name__
        res["onset"] = onset
        res["order_effect"], res["trial_effect"] = S.order_effect(obs), S.trial_effect(obs, n_boot)
        res["sun_counts"] = dict(Counter(o["sun"] for o in obs.values()))
        if tier in ("standard", "extended"):
            res["per_band_note"] = "%d WAVs per band at the %s tier: wide intervals, no comparison between bands" % (len(obs) // 4, tier)
            res["per_band"] = {}
            for band in ("17m", "20m", "40m", "80m"):
                tb = [tallies_by_wav[w] for w in sorted(obs) if obs[w]["band"] == band]
                if tb:
                    res["per_band"][band] = S.pool(tb)
        else:
            res["per_band_note"] = "not given at the quick tier: too small"
    with open(os.path.join(s6, "s6_result.json"), "w", encoding="utf8", newline="\n") as fh:
        json.dump(res, fh, indent=1, default=lambda o: None if (isinstance(o, float) and not math.isfinite(o)) else (o.tolist() if hasattr(o, "tolist") else str(o)))
    with open(os.path.join(s6, "s6_section5.md"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(fmt_block(res, series_label))
    row = "| S6 | %s | tier %s | %s | %s |" % (status, tier, series_label, (pct(res["full"]["headline"].get("positive_agreement")) + " positive agreement") if ok else "withheld")
    with open(os.path.join(s6, "s6_section6_row.md"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(row + "\n")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--daemon-log", default=None)
    ap.add_argument("--series-label", default="First S6 row of the LINUX series")
    ap.add_argument("--corpus", default=None, help="the frozen corpus (live WSJT-X ALL.TXT of the source runs) for the onset row")
    ap.add_argument("--wavlist", default=os.path.join(HERE, "s6-wavlist.json"))
    ap.add_argument("--cpu-chain-label", default=None, help="default: built from the run's own arm_config.json and /proc/cpuinfo (describe_chain)")
    a = ap.parse_args()
    r = run(a.run_dir, a.scratch, a.daemon_log, a.series_label, a.cpu_chain_label, corpus=a.corpus, wavlist_path=a.wavlist)
    print("S6 analysis:", r["status"], "tier", r["tier"], "plays", r["plays"])
    sys.exit(0)


if __name__ == "__main__":
    main()
