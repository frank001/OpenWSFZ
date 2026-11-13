#!/usr/bin/env python3
"""TA-CHECK groups (spec 2006 + Amendment 1).  Builds the groups from arm B's matchedbatch.csv and WSJT-X's ALL.TXT of the night (text read INSIDE this process, HK-037).
    python tc_groups.py     -> D:/Projects/claude/_qa-scratch/ta-check/frozen/tc_groups.json   (stamps, indices, bands, batches, flags: NO text)
Counts reported: confirmed rows by batch; for batches 4 and 5 how many are hashed / untestable-class / unencodable (not scored); n(T), n(T_bur), band mixes; the B1 and B1m draws."""
from __future__ import annotations

import collections
import csv
import hashlib
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.join(HERE, "..", "rr-study")
for p in (HERE, os.path.join(RR, "coh-fallback"), os.path.join(RR, "gap-relocate-run"), os.path.join(RR, "gap-residual-run")):
    sys.path.insert(0, p)
import tc_lib as L          # noqa: E402
import cf_uprime as U       # noqa: E402
import gr_common as C       # noqa: E402
import nrtax_defs as D      # noqa: E402

ART = "D:/Projects/claude/OpenWSFZ/artefacts/20261110_1817_cq-ap-live"
ALLTXT = ART + "/wsjt-x/ALL.TXT"
WAVS = ART + "/owsfz/wav"
MATCHED = "D:/Projects/claude/_qa-scratch/coh-res-cand-v2/arms/B/matchedbatch.csv"
CLASSES = os.path.join(HERE, "..", "coh-res-cand-v2", "frozen", "uprime_arm_a_classes.json")
OUT = "D:/Projects/claude/_qa-scratch/ta-check"
DLL = os.path.join(C.S, "bin", "libft8.dll")
DLL_PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"

assert (U.T_FROZEN, U.MIN_PRESENT_RATE, U.NULL_P99_TOLERANCE) == (L.T_FROZEN, L.BAR, L.NULL_TOL) and D.OVERLAP_HZ == L.OVERLAP_HZ
assert all(C.band_of(s) == L.band_of(s) for s in range(-30, 15))


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_ref_night(stamps):
    """gr_common.load_ref's filter (Replay81.LoadWsjtx) on THIS night's ALL.TXT: stamp -> [(snr, dt, freq, text)] in file order."""
    ref = {}
    with open(ALLTXT, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8" or f[0] not in stamps:
                continue
            try:
                snr, dt, freq = int(f[4]), float(f[5]), int(f[6])
            except ValueError:
                continue
            ref.setdefault(f[0], []).append((snr, dt, freq, " ".join(f[7:]).strip()))
    return ref


def load_rows():
    """[(stamp, [rows])] in matchedbatch order; row = dict(idx, snr, dt, freq, batch|None, cls, hashed, tones_ok).  Text exists only in this function's frame and the encoder call."""
    assert sha(DLL) == DLL_PIN, "libft8.dll pin"
    F, blob = U.load_instrument()
    enc = F.encoder(DLL)
    mb, order = {}, []
    for r in csv.reader(open(MATCHED)):
        if not r or r[0] == "stamp":
            continue
        mb[r[0]] = {int(a.split(":")[0]): int(a.split(":")[1]) for a in r[1].split(";") if a}
        order.append(r[0])
    ref = load_ref_night(set(order))
    assert len(order) == 500 and sum(len(v) for v in ref.values()) == 13997 and sum(len(v) for v in mb.values()) == 11654
    out = []
    for s in order:
        rows = []
        for i, (snr, dt, f, text) in enumerate(ref.get(s, [])):
            rows.append({"idx": i, "snr": snr, "dt": dt, "freq": f, "batch": mb[s].get(i), "cls": F.shape_class(text), "hashed": any(x.startswith("<") for x in text.split()),
                         "tones_ok": enc(text) is not None})
        out.append((s, rows))
    return out, blob


def main():
    os.makedirs(OUT + "/frozen", exist_ok=True)
    cyc, blob = load_rows()
    classes = json.load(open(CLASSES))
    assert tuple(classes["testable_classes"]) == L.TESTABLE and classes["T_frozen"] == L.T_FROZEN
    all_rows, conf_by_batch = [], collections.Counter()
    excluded = collections.Counter()
    for s, rows in cyc:
        tup = [(r["snr"], r["dt"], r["freq"]) for r in rows]
        for r in rows:
            if r["batch"] is None:
                continue
            conf_by_batch[r["batch"]] += 1
            ok = (not r["hashed"]) and r["tones_ok"] and r["cls"] in L.TESTABLE
            if not ok:
                excluded[(r["batch"], "hashed" if r["hashed"] else "unencodable" if not r["tones_ok"] else "untestable_class")] += 1
                continue
            all_rows.append({"stamp": s, "idx": r["idx"], "snr": r["snr"], "freq": r["freq"], "band": L.band_of(r["snr"]), "batch": r["batch"], "bur": L.is_buried(r["idx"], tup), "nbr": L.strongest_neighbour(r["idx"], tup)})
    b1 = [r for r in all_rows if r["batch"] == 1]
    T = [r for r in all_rows if r["batch"] in (4, 5)]
    key = lambda r: (r["stamp"], r["idx"])
    t_band = collections.Counter(r["band"] for r in T)
    pool_by_band = {b: [key(r) for r in b1 if r["band"] == b] for b in L.BANDS}
    quota = L.band_quota({b: len(v) for b, v in pool_by_band.items()}, t_band)
    b1_draw = L.draw([key(r) for r in b1], L.N_B1)
    b1m_draw = L.draw_matched(pool_by_band, quota)
    assert len(b1m_draw) == len(T) == sum(quota.values())
    S1, S1m = set(b1_draw), set(b1m_draw)
    for r in all_rows:
        k = key(r)
        r["in_B1"], r["in_B1m"] = k in S1, k in S1m
        r["in_T"] = r["batch"] in (4, 5)
        r["in_Tbur"] = r["in_T"] and r["bur"]
    summary = {"blob_cf_fbid": blob, "dll_sha256": DLL_PIN, "confirmed_by_batch": dict(sorted(conf_by_batch.items())),
               "excluded_confirmed_rows_by_batch_and_reason": {f"{b}:{w}": n for (b, w), n in sorted(excluded.items())},
               "scored_pool_by_batch": dict(sorted(collections.Counter(r["batch"] for r in all_rows).items())),
               "n_T": len(T), "n_T4": sum(1 for r in T if r["batch"] == 4), "n_T5": sum(1 for r in T if r["batch"] == 5), "n_Tbur": sum(1 for r in T if r["bur"]), "n_Tiso": sum(1 for r in T if not r["bur"]),
               "T_band_mix": dict(t_band), "Tbur_band_mix": dict(collections.Counter(r["band"] for r in T if r["bur"])), "Tiso_band_mix": dict(collections.Counter(r["band"] for r in T if not r["bur"])),
               "B1_pool": len(b1), "B1_pool_by_band": {b: len(v) for b, v in pool_by_band.items()}, "B1_draw": len(b1_draw), "B1m_quota": quota, "B1m_draw": len(b1m_draw),
               "B1_draw_band_mix": dict(collections.Counter(r["band"] for r in b1 if r["in_B1"])),
               "V_N": {"n_T_ge_400": len(T) >= L.V_N_T, "n_Tbur_ge_100": sum(1 for r in T if r["bur"]) >= L.V_N_TBUR},
               "inputs": {"matchedbatch_sha256": sha(MATCHED), "ALL_TXT_sha256": sha(ALLTXT), "classes_sha256": sha(CLASSES)}}
    json.dump({"summary": summary, "rows": all_rows, "stamps": [s for s, _ in cyc]}, open(OUT + "/frozen/tc_groups.json", "w"))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
