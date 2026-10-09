#!/usr/bin/env python
"""EARLY-DUP Part A1 verdict rows (spec 2026-10-09-1025-architect-to-qa-spec-early-dup.md, amendment 1). Counts and Hz only (HK-037).

  python qa/rr-study/early-dup/early_dup_rows.py <play1.jsonl> <play2.jsonl> --pins <pins.json>

Each play file is the classifier-v2 output (cycle_v2 records written at FINALIZE, plus the frames and any disconnect lines). pins.json: {"play1": {"start": sha, "end": sha}, "play2": {...}}
(the published main DLL SHA-256 recorded before and after each play; the publish is identified by its DLL SHA, never by a shim number: amendment 1).

Verdict rows, EXCLUSIVE, first match wins, pooled over both plays (amendment 1 order):
  ED-INVALID : any play has a truth cycle with no final frame, a disconnect between its first frame and FINALIZE, lookup_miss > 0 in any cycle, or a build pin that differs
               between start and end  => no verdict, replay once.
  ED-NONE    : 0 unconfirmed early rows in total (two plays on main). Reported as such; NOT support for H-DUP (non-vacuity: "every row is ..." is vacuously true on 0 rows).
  ED-DUP     : >= 1 unconfirmed row, EVERY row is FREQ_MISS and DUP and E_ON_COPY and F_ON_OTHER_COPY, and cycles WITHOUT a repeated text have 0 unconfirmed rows.
  ED-OTHER   : otherwise (>= 1 unconfirmed row H-DUP does not explain) => counts by label to the Architect.
Also reported (descriptive): unconfirmed DUP rows per play beside the fix build's 8 (first re-play) and 3 (S4b).
"""
import collections
import json
import sys


def play_facts(lines, pins=None):
    cyc = [r for r in lines if r.get("kind") == "cycle_v2"]
    frames = [r for r in lines if r.get("kind") == "frame"]
    fin = next((r for r in lines if r.get("kind") == "finalized"), None)
    first = min((r["utc"] for r in frames), default=None)
    last = fin["utc"] if fin else None
    disc = [r for r in lines if r.get("kind") == "disconnect" and first and last and first <= r["utc"] <= last]
    return {"cycles": cyc, "disconnects_during": len(disc), "finalized": fin is not None,
            "pin_ok": (pins is None) or (pins.get("start") == pins.get("end") and bool(pins.get("start")))}


def invalid_reasons(plays):
    why = []
    for i, p in enumerate(plays, 1):
        if not p["finalized"]:
            why.append(f"play{i}: not finalized")
        miss = [c["cycle_utc"] for c in p["cycles"] if not c["final_frame"]]
        if miss:
            why.append(f"play{i}: {len(miss)} cycle(s) without a final frame")
        if p["disconnects_during"]:
            why.append(f"play{i}: {p['disconnects_during']} disconnect(s) during S4")
        if any(c["lookup_miss"] > 0 for c in p["cycles"]):
            why.append(f"play{i}: lookup_miss > 0")
        if not p["pin_ok"]:
            why.append(f"play{i}: build pin differs between start and end")
    return why


def explained(row):
    return row["label"] == "FREQ_MISS" and row["DUP"] and row["E_ON_COPY"] and row["F_ON_OTHER_COPY"]


def verdict(plays):
    """plays: list of play_facts dicts. -> (verdict, details). Pure (tested)."""
    why = invalid_reasons(plays)
    if why:
        return "ED-INVALID", {"reasons": why}
    rows = [(c, r) for p in plays for c in p["cycles"] for r in c["rows"]]
    labels = collections.Counter(r["label"] for _c, r in rows)
    det = {"unconfirmed_total": len(rows), "labels": dict(labels),
           "dup_rows_per_play": [sum(1 for c in p["cycles"] for r in c["rows"] if r["DUP"]) for p in plays],
           "rows_in_cycles_without_a_repeated_text": sum(1 for c, _r in rows if not c["repeated_text_in_truth"]),
           "unexplained_rows": sum(1 for _c, r in rows if not explained(r))}
    if not rows:
        return "ED-NONE", det
    if det["unexplained_rows"] == 0 and det["rows_in_cycles_without_a_repeated_text"] == 0:
        return "ED-DUP", det
    return "ED-OTHER", det


def main(argv):
    pins = json.load(open(argv[argv.index("--pins") + 1])) if "--pins" in argv else {}
    files = [a for a in argv[1:] if a.endswith(".jsonl")]
    plays = [play_facts([json.loads(ln) for ln in open(f, encoding="utf-8") if ln.strip()], pins.get(f"play{i}")) for i, f in enumerate(files, 1)]
    v, det = verdict(plays)
    print(json.dumps({"verdict": v, "details": det, "reference_fix_build_unconfirmed": {"first_replay": 8, "S4b": 3}}, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
