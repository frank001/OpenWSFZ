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


def first_s6_slot(run_dir: str):
    p = os.path.join(run_dir, "s6", "s6_playlog.jsonl")
    if not os.path.isfile(p):
        return None
    # only the warm-up and play rows carry a slot_stamp (a batch_plan row has first_slot): the first S6 slot is the earliest of either
    slots = []
    for x in open(p, encoding="utf8"):
        if not x.strip():
            continue
        r = json.loads(x)
        if "slot_stamp" in r:
            slots.append(r["slot_stamp"])
        elif "first_slot" in r:
            slots.append(r["first_slot"])
    return min(slots) if slots else None


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
    first = first_s6_slot(run_dir)
    if first is None:
        return None
    os.makedirs(scratch, exist_ok=True)
    k1, m1 = split_one(wsjt_copy, os.path.join(scratch, "wsjt-s6.txt"), first)
    k2, m2 = split_one(owsfz_copy, os.path.join(scratch, "owsfz-s6.txt"), first)
    return {"first_s6_slot": first, "wsjtx": {"kept": k1, "moved": m1}, "owsfz": {"kept": k2, "moved": m2}}


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
