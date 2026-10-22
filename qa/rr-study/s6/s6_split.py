"""S6 log split (QA tooling): move the S6 window's lines out of the run directory's ALL.TXT copies and into a scratch dir OUTSIDE git.

    python s6_split.py --run-dir <dir> --wsjt-copy <wsjt-all.txt> --owsfz-copy <owsfz-all.txt> --scratch <dir>

S6 plays REAL off-air recordings, so the logs it produces hold real callsigns (NFR-021, HK-037): they must not sit in the battery's run folder,
and they must not reach the S1-S8 matcher either (every S6 line would be an unexplained decode there). S6 is the LAST playback of a battery, so
every line stamped at or after the first S6 slot (warm-up included) belongs to S6. Those lines go to <scratch>/wsjt-s6.txt and owsfz-s6.txt; the
copies keep everything before. Lines that cannot be dated are kept in the copies. Counts only on stdout.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

STAMP = re.compile(r"^\d{6}_\d{6}$")


def first_s6_slots(run_dir: str):
    """(first slot of the WSJT-X side, first slot of the OpenWSFZ side), or None without a play log. A concurrent S6 has one first slot for both. A SEQUENTIAL S6
    (s6_merge.py) played the two appraisers in two passes: warm-up and batch_plan rows carry "pass": "w"|"o" and a play row carries `slot_stamp_o` for the OpenWSFZ pass."""
    p = os.path.join(run_dir, "s6", "s6_playlog.jsonl")
    if not os.path.isfile(p):
        return None
    w, o = [], []
    for x in open(p, encoding="utf8"):
        if not x.strip():
            continue
        r = json.loads(x)
        stamp = r.get("slot_stamp") or r.get("first_slot")      # only the warm-up and play rows carry a slot_stamp (a batch_plan row has first_slot)
        who = r.get("pass")
        if stamp and who in (None, "w"):
            w.append(stamp)
        if stamp and who in (None, "o"):
            o.append(stamp)
        if r.get("slot_stamp_o"):
            o.append(r["slot_stamp_o"])
    if not w and not o:
        return None
    return (min(w) if w else min(o)), (min(o) if o else min(w))


def first_s6_slot(run_dir: str):
    """The earliest S6 slot of either side (the old single-slot view; a concurrent S6 has only one)."""
    f = first_s6_slots(run_dir)
    return None if f is None else min(f)


def split_one(copy_path: str, out_path: str, first: str) -> tuple:
    keep, moved = [], []
    with open(copy_path, encoding="utf-8", errors="replace", newline="") as fh:
        for line in fh:
            tok = line.split(None, 1)[0] if line.strip() else ""
            (moved if STAMP.match(tok) and tok >= first else keep).append(line)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(moved)
    with open(copy_path, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(keep)
    return len(keep), len(moved)


def split_logs(run_dir: str, wsjt_copy: str, owsfz_copy: str, scratch: str):
    """Both logs are cut at the EARLIEST S6 slot of either pass (the old rule: S6 is the last playback of a battery, so every line stamped at or after its first slot belongs to
    S6). In a sequential S6 that also means a decode of the appraiser that should be OFF during the other's pass lands in the S6 slice, where the S6-V2 stray-line check sees it."""
    firsts = first_s6_slots(run_dir)
    if firsts is None:
        return None
    first = min(firsts)
    os.makedirs(scratch, exist_ok=True)
    k1, m1 = split_one(wsjt_copy, os.path.join(scratch, "wsjt-s6.txt"), first)
    k2, m2 = split_one(owsfz_copy, os.path.join(scratch, "owsfz-s6.txt"), first)
    out = {"first_s6_slot": first, "wsjtx": {"kept": k1, "moved": m1}, "owsfz": {"kept": k2, "moved": m2}}
    if firsts[0] != firsts[1]:
        out["first_slot_wsjtx_pass"], out["first_slot_owsfz_pass"] = firsts
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--wsjt-copy", required=True)
    ap.add_argument("--owsfz-copy", required=True)
    ap.add_argument("--scratch", required=True)
    a = ap.parse_args()
    r = split_logs(a.run_dir, a.wsjt_copy, a.owsfz_copy, a.scratch)
    print("S6 split:", "no S6 play log, nothing to do" if r is None else r)


if __name__ == "__main__":
    main()
