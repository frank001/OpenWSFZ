#!/usr/bin/env python3
"""Validity row for a third-pass sweep (Architect, 2026-10-18): the decoding depth READ BACK from the live daemon (/api/v1/status, thirdPass.decodingDepth, via the 1 Hz
status poll) must equal the depth in the sweep's config at the START and at the END of the sweep. ANY mismatch, or no read-back at all, VOIDS the sweep (not a warning).

    python3 depth_readback.py --config <rig config> --statuspoll <statuspoll.jsonl> --out <depth_readback.json>

Prints VALID or VOID: <reason> and exits 0 / 3. A config without the key means Normal (the build's default). Numeric/category data only.
"""
import argparse
import json
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--statuspoll", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
want = json.load(open(a.config, encoding="utf8"))["decoder"].get("decodingDepth", "Normal")
seen = []
try:
    for line in open(a.statuspoll, encoding="utf8"):
        j = json.loads(line)
        if j.get("depth") is not None:
            seen.append(j["depth"])
except FileNotFoundError:
    pass
res = {"config_depth": want, "polls_with_a_readback": len(seen), "first": seen[0] if seen else None, "last": seen[-1] if seen else None,
       "distinct": sorted(set(seen))}
if not seen:
    res["result"], res["reason"] = "VOID", "no read-back of thirdPass.decodingDepth in the status poll (poller missing, or the daemon lacks the status block)"
elif res["first"] != want or res["last"] != want or res["distinct"] != [want]:
    res["result"], res["reason"] = "VOID", "read-back %s (first %s, last %s) differs from the config's %s" % (res["distinct"], res["first"], res["last"], want)
else:
    res["result"], res["reason"] = "VALID", "all %d read-backs equal the config's %s, first and last included" % (len(seen), want)
json.dump(res, open(a.out, "w", encoding="utf8"), indent=1)
print(res["result"] + ": " + res["reason"])
sys.exit(0 if res["result"] == "VALID" else 3)
