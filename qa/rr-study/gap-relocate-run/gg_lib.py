#!/usr/bin/env python3
"""COH-GATE-G library (QA): load the recorded fallback rows and re-run the product's publication path OFFLINE for any admission rule.

Faithful to Ft8Decoder.cs at 95e69e87: per run the NEW_GATED rows (here: N rows plus the admitted G rows), merged residual-first, then
CoherentFallbackSelector.Select (first row per payload, a later non-edge row replaces an edge one), unpack (text from the product's own unpack
for N payloads, from the post-cycle save/restore unpack for G payloads), empty skip, per-cycle text de-duplication against batches 1-3
(INCLUDING texts the plausibility filter dropped, because the product adds to `seen` before it checks plausibility), IsPlausibleMessage
(the recorded flag for G payloads; for N payloads: not among the cycle's recorded drops). Scoring is Replay81's: one-to-one nearest-first text
match within 10 Hz across batches 1-4.  Text lives in memory only (HK-037); callers write counts.
"""
from __future__ import annotations

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gr_common as C

S = r"D:\Projects\claude\_qa-scratch\coh-gate-g"
CORROB_HZ = 10


def load_arm(name: str):
    raw = f"{S}\\raw\\{name}"
    scr = f"{S}\\scratch\\{name}"
    a = {"name": name, "rows": collections.defaultdict(list), "U": collections.defaultdict(dict), "X": collections.defaultdict(dict),
         "nc": collections.defaultdict(list), "D": collections.defaultdict(set), "runs": {}}
    for r in C.load_tsv(scr + "\\stage_dump.tsv"):
        if len(r) < 3 or not r[0]:
            continue
        if r[1] == "G" and len(r) >= 17:
            a["rows"][r[0]].append(dict(run=int(r[2]), state=r[3], f1b=float(r[4]), snr=int(r[5]), edge=r[6] == "1", prov=int(r[7]),
                                        dfreq=float(r[8]), ddt=float(r[9]), pas=int(r[10]), freq=float(r[11]), payload=r[12],
                                        i3=int(r[13]), n3=int(r[14]), dt=float(r[15]), idx=int(r[16])))
        elif r[1] == "U" and len(r) >= 4:
            a["U"][r[0]][r[2]] = r[3]
        elif r[1] == "X" and len(r) >= 5:
            a["X"][r[0]][r[2]] = (r[3] == "1", r[4])
    for r in C.load_tsv(scr + "\\nc_dump.tsv"):
        if len(r) >= 11:
            a["nc"][r[0]].append((int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5]), int(r[9]), r[10]))
    for r in C.load_tsv(scr + "\\impl_dump.tsv"):
        if len(r) >= 3 and r[0] and r[1] == "D":
            a["D"][r[0]].add(r[2])
    import csv
    for row in csv.DictReader(open(raw + "\\stage.csv", encoding="utf-8")):
        k = list(row.keys())
        runs_s = row[k[1]]
        a["runs"][row[k[0]]] = 0 if runs_s == "-" else len(runs_s.split("|"))
    return a


def select(rows):
    """CoherentFallbackSelector.Select over rows already restricted to NEW_GATED-equivalent ones, in candidate order."""
    chosen = {}
    for i, r in enumerate(rows):
        k = r["payload"]
        if k not in chosen:
            chosen[k] = i
        elif rows[chosen[k]]["edge"] and not r["edge"]:
            chosen[k] = i
    return [rows[i] for i in sorted(chosen.values())]


def publish(arm, s, admit):
    """Fallback outputs of cycle s when `admit(row)` is true for the G rows admitted on top of the existing gate. Returns [(freq, text, row)]."""
    adm = [r for r in arm["rows"].get(s, []) if r["state"] == "N" or (r["state"] == "G" and admit(r))]
    two = arm["runs"].get(s, 0) == 2
    # CohFallbackAudioSelector.Merge: residual rows as they are; original rows only if admitted and the payload is not an admitted residual one;
    # sorted by (row index within its run, residual before original); then Select over that order.
    res_keys = {r["payload"] for r in adm if two and r["run"] == 0}
    comb = []
    for r in adm:
        src = 0 if (two and r["run"] == 0) else 1
        if src == 1 and two and r["payload"] in res_keys:
            continue
        comb.append((r["idx"], src, r))
    comb.sort(key=lambda c: (c[0], c[1]))
    rows = [c[2] for c in comb]
    seen = {x[6] for x in arm["nc"].get(s, []) if x[0] in (1, 2, 3)} | set(arm["D"].get(s, set()))
    out = []
    for r in select(rows):
        if r["payload"] in arm["U"].get(s, {}):
            text, plaus = arm["U"][s][r["payload"]], None
        elif r["payload"] in arm["X"].get(s, {}):
            plaus, text = arm["X"][s][r["payload"]]
        else:
            continue
        text = text.rstrip()
        if not text.strip():
            continue
        if text in seen:
            continue
        seen.add(text)
        if plaus is None:
            plaus = text not in arm["D"].get(s, set())
        if not plaus:
            continue
        out.append((int(round(r["freq"] + r["dfreq"])), text, r))
    return out


def match(ref_s, ows):
    """ows: [(kind, freq, text)] in kinds 1..4 order. Returns (set of matched REF idx, matched flag per ows index)."""
    cands = []
    for i, (_, f, t) in enumerate(ows):
        for j, (_, _, rf, rt) in enumerate(ref_s):
            df = abs(f - rf)
            if df <= CORROB_HZ and t == rt:
                cands.append((df, i, j))
    cands.sort()
    uo, uw = set(), set()
    for _, oi, wi in cands:
        if oi in uo or wi in uw:
            continue
        uo.add(oi)
        uw.add(wi)
    return uw, uo


def cycle_outputs(arm, s, admit):
    """All published messages of the cycle as [(kind, freq, text)] with the fallback ones from publish()."""
    base = [(x[0], x[2], x[6]) for x in arm["nc"].get(s, []) if x[0] in (1, 2, 3)]
    fb = publish(arm, s, admit)
    return base, fb
