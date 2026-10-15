"""S6 SEQUENTIAL merge (QA tooling; Captain 2026-10-15): combine the two passes of a sequential S6 into the files the analyser already reads.

    python s6_merge.py --run-dir <dir>

WHY SEQUENTIAL. Run together on sol, WSJT-X's Qt ALSA capture (libqtaudio_alsa.so) silently stops delivering audio after OpenWSFZ's subtraction pass delays its
capture thread: it closes and reopens its PCM and the reopened input never ticks again (4 of 4 S6 attempts of B2BASE sweep 1; 4 of 4 daemon-on isolation runs on sol,
2026-10-15; none with WSJT-X alone, a bare reader, or the daemon without the residual pass). So S6 is played TWICE with ONE appraiser listening each time:
    pass W  (WSJT-X alone; the daemon is stopped)      -> <run-dir>/s6/pass-w/
    pass O  (OpenWSFZ alone; WSJT-X is stopped)        -> <run-dir>/s6/pass-o/
Both passes play the IDENTICAL schedule (same WAVs, same trial shuffles, same gain: the schedule is a pure function of the tier and the frozen list), at different
wall-clock slots. This tool joins them by play_index and writes, into <run-dir>/s6/, the same files a concurrent S6 writes:
  s6_playlog.jsonl  warm-up and batch_plan rows of both passes (each tagged "pass": "w"|"o"); one `play` row per play_index = the WSJT-X pass's row plus
                    slot_stamp_o / boundary_utc_o / offset_s_o = where the OpenWSFZ pass played the same play. `slot_stamp` stays the WSJT-X pass's.
  s6_validity.json  S6-V1 / V3 / V5 combined (a row passes only if it passed in BOTH passes; V5 also needs the pins equal across the whole S6)
  s6_window.json, s6_pins.json, s6_tz.json (the OpenWSFZ pass's: the daemon log is stamped in local time), s6_sequential.json (marker + pass windows)
The analyser (s6_analyse.py) reads `slot_stamp_o` for OpenWSFZ when it is present; a concurrent S6 has none and is read exactly as before.
Aggregates only: no message text is read or written here (NFR-021, HK-037). Exit 0 = merged, 1 = nothing written (a pass is missing or the schedules differ).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

SCHEDULE_KEYS = ("play_index", "trial", "order", "wav_id", "band", "sun", "gain")      # what must be identical between the two passes
PASSES = (("w", "pass-w", "wsjtx"), ("o", "pass-o", "owsfz"))


class MergeError(Exception):
    pass


def _rows(path: str) -> list:
    with open(path, encoding="utf8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def _json(path: str):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf8") as fh:
        return json.load(fh)


def _write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf8", newline="\n") as fh:
        json.dump(obj, fh, indent=1)


def merge_playlogs(rows_w: list, rows_o: list) -> list:
    """The merged playlog rows. Raises MergeError if the two passes did not play the same schedule."""
    plays_w = {r["play_index"]: r for r in rows_w if r.get("kind") == "play"}
    plays_o = {r["play_index"]: r for r in rows_o if r.get("kind") == "play"}
    if not plays_w or not plays_o:
        raise MergeError("a pass has no play rows (W %d, O %d)" % (len(plays_w), len(plays_o)))
    if set(plays_w) != set(plays_o):
        raise MergeError("the passes did not play the same plays (W %d, O %d; %d differ)" % (len(plays_w), len(plays_o), len(set(plays_w) ^ set(plays_o))))
    out: list = []
    for tag, rows in (("w", rows_w), ("o", rows_o)):
        for r in rows:
            if r.get("kind") in ("warmup", "batch_plan"):
                out.append({**r, "pass": tag})
    for i in sorted(plays_w):
        w, o = plays_w[i], plays_o[i]
        diff = [k for k in SCHEDULE_KEYS if w.get(k) != o.get(k)]
        if diff:
            raise MergeError("play %d differs between the passes in %s" % (i, ", ".join(diff)))
        out.append({**w, "slot_stamp_o": o["slot_stamp"], "boundary_utc_o": o["boundary_utc"], "offset_s_o": o["offset_s"]})
    return out


def _row_result(a: dict | None, b: dict | None) -> str:
    ra, rb = (a or {}).get("result", "MISSING"), (b or {}).get("result", "MISSING")
    if ra == rb:
        return ra
    for bad in ("FAIL", "MISSING", "NOT PINNED", "SKIPPED"):                 # the worst of the two, in this order
        if bad in (ra, rb):
            return bad
    return "FAIL"


def merge_validity(vw: dict | None, vo: dict | None, pins_w: dict | None, pins_o: dict | None) -> dict:
    if vw is None or vo is None:
        return {"tier": (vw or vo or {}).get("tier", "unknown"), "plays_planned": (vw or vo or {}).get("plays_planned", 0), "player_did_not_finish": True,
                "design": "sequential", "note": "a pass left no s6_validity.json (the player did not finish)"}
    out = {"tier": vw["tier"], "plays_planned": vw["plays_planned"], "design": "sequential"}
    if vw["tier"] != vo["tier"] or vw["plays_planned"] != vo["plays_planned"]:
        out["player_did_not_finish"] = True
        out["note"] = "the passes were played at different tiers or sizes"
        return out
    for k in ("S6-V1", "S6-V3", "S6-V5"):
        out[k] = {"result": _row_result(vw.get(k), vo.get(k)), "w": vw.get(k), "o": vo.get(k)}
    # V5 across the whole S6: the library and the WSJT-X executable at the start of pass W equal those at the end of pass O
    if out["S6-V5"]["result"] == "PASS" and pins_w and pins_o:
        from s6_play import pin_identity
        if pin_identity(pins_w["start"]) != pin_identity(pins_o["end"]):
            out["S6-V5"]["result"] = "FAIL"
            out["S6-V5"]["across_passes"] = "the pins at the start of pass W differ from those at the end of pass O"
    out["S6-V5"]["wsjtx_exe_pinned"] = bool((vw.get("S6-V5") or {}).get("wsjtx_exe_pinned"))
    out["S6-V4-plays_completed"] = min(vw.get("S6-V4-plays_completed", 0), vo.get("S6-V4-plays_completed", 0))
    ex = [x.get("exit_code") for x in (vw, vo) if x.get("exit_code")]
    out["exit_code"] = ex[0] if ex else 0
    out["note"] = "sequential S6: pass W (WSJT-X alone) then pass O (OpenWSFZ alone)"
    return out


def merge(run_dir: str) -> dict:
    s6 = os.path.join(run_dir, "s6")
    d = {tag: os.path.join(s6, sub) for tag, sub, _ in PASSES}
    for tag, path in d.items():
        if not os.path.isfile(os.path.join(path, "s6_playlog.jsonl")):
            raise MergeError("pass %s left no s6_playlog.jsonl (%s)" % (tag.upper(), path))
    rows_w, rows_o = _rows(os.path.join(d["w"], "s6_playlog.jsonl")), _rows(os.path.join(d["o"], "s6_playlog.jsonl"))
    merged = merge_playlogs(rows_w, rows_o)
    vw, vo = _json(os.path.join(d["w"], "s6_validity.json")), _json(os.path.join(d["o"], "s6_validity.json"))
    pw, po = _json(os.path.join(d["w"], "s6_pins.json")), _json(os.path.join(d["o"], "s6_pins.json"))
    ww, wo = _json(os.path.join(d["w"], "s6_window.json")), _json(os.path.join(d["o"], "s6_window.json"))
    with open(os.path.join(s6, "s6_playlog.jsonl"), "w", encoding="utf8", newline="\n") as fh:
        for r in merged:
            fh.write(json.dumps(r) + "\n")
    _write_json(os.path.join(s6, "s6_validity.json"), merge_validity(vw, vo, pw, po))
    if pw and po:
        _write_json(os.path.join(s6, "s6_pins.json"), {"start": pw["start"], "end": po["end"], "w": pw, "o": po})
    if ww and wo:
        win = dict(ww)
        win.update({"design": "sequential", "o_first_warmup_slot": wo.get("first_warmup_slot"), "o_first_play_slot": wo.get("first_play_slot"),
                    "o_last_play_slot": wo.get("last_play_slot"), "slips": ww.get("slips", 0) + wo.get("slips", 0), "end_utc": wo.get("end_utc")})
        _write_json(os.path.join(s6, "s6_window.json"), win)
    tz = _json(os.path.join(d["o"], "s6_tz.json")) or _json(os.path.join(d["w"], "s6_tz.json"))
    if tz:
        _write_json(os.path.join(s6, "s6_tz.json"), tz)
    marker = {"design": "sequential", "order": ["w", "o"],
              "w": {"appraiser": "wsjtx", "window": ww}, "o": {"appraiser": "owsfz", "window": wo}}
    _write_json(os.path.join(s6, "s6_sequential.json"), marker)
    return {"plays": sum(1 for r in merged if r.get("kind") == "play"), "rows": len(merged)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args()
    try:
        r = merge(a.run_dir)
    except MergeError as exc:
        print("S6 merge FAILED: %s" % exc, flush=True)
        sys.exit(1)
    print("S6 merge: %d plays joined (%d rows) in %s" % (r["plays"], r["rows"], os.path.join(a.run_dir, "s6")), flush=True)


if __name__ == "__main__":
    main()
