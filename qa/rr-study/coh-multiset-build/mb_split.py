#!/usr/bin/env python3
"""COH-MULTISET-BUILD section 6.7 / Amendment 4.2 companion: the per-set split (published / KNOWN / gated out), DESCRIPTIVE. Numbers only; no message text is persisted (HK-037).

The native run export (ft8_coherent_fallback_run, the product's own per-candidate body) is called on the FROZEN replay selection (night 20260925_2010 WHOLE, 2,882 cycles, owsfz/wav) with the Stage 2 DLL pin,
once with flags 0 (OFF) and once with FT8_COH_RUN_MULTISET (ON), budget -1 (no deadline). Per cycle, the candidates and the ordinary-decode snapshot come from ONE ft8_decode_all pass (this is not the
Deep multi-pass product pipeline of the replay: it is the same fallback on a single-pass candidate list, so the counts describe the sets, not the replay's totals).
Classification of an ON row whose OFF row is NO_CRC (V3 found nothing; the walk was entered), by the set that won (provenance 1 C1, 2 J2, 3 J3, 4 N1):
  KNOWN      the CRC-valid payload is one the ordinary decode produced in the call (state 2)
  GATED_OUT  CRC-valid, new, F1b > T1 (state 3)
  NEW_GATED  CRC-valid, new, F1b <= T1: a publication candidate (state 4); 'published distinct' counts the distinct payloads per cycle (the per-cycle text dedup admits each once)
Also reported: rows where the walk found nothing (provenance -1), the V3 baseline states of the OFF arm, and the same split restricted to the FIRST success per row (which is what provenance is).

  python mb_split.py --dll <Stage 2 libft8.dll> --out <json> [--workers 12] [--cycles N]
"""
from __future__ import annotations

import argparse
import collections
import ctypes as C
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mb_pw as P  # noqa: E402  (structs, the DLL loader, the state constants)
import ms_run as R  # noqa: E402
import wavio  # noqa: E402

RUN = "20260925_2010"
SELECTION = os.path.join(HERE, "..", "..", "..", "qa", "rr-study", "results", "2026-10-24-coh-multiset-build", "selection.json")
SELECTION_SHA256_LF = "53d9ba4ec52b0f6bca8f4a4cb03a92ad3493387dfb1f4d11e7a29709857331c4"
WAV_DIR = os.path.join(R.CG.REPO_ROOT, "artefacts", f"{RUN}_endurance_run-gathered", "owsfz", "wav")
STATE_NAME = {P.KNOWN: "KNOWN", P.GATED_OUT: "GATED_OUT", P.NEW_GATED: "NEW_GATED"}
SET_NAME = {1: "C1", 2: "J2", 3: "J3", 4: "N1"}


def _cycle(stamp):
    D = P._D
    pcm = np.ascontiguousarray(wavio.load_cycle_pcm(os.path.join(WAV_DIR, stamp + ".wav")), dtype=np.float32)
    p = pcm.ctypes.data_as(C.POINTER(C.c_float))
    cands = (P.Cand * 200)()
    D.ft8_decode_all(p, 180000, cands, 200)
    size = D.ft8_coherent_fallback_snapshot_size()
    snap = (C.c_uint8 * size)()
    assert D.ft8_coherent_fallback_snapshot(snap, size) == size
    res = {}
    for flag in (0, 1):
        st = P.Stats()
        rows = (P.Out * 2000)()
        n = D.ft8_coherent_fallback_run(p, 180000, snap, size, flag, -1.0, None, C.byref(st), rows, 2000)
        assert n >= 0, n
        res[flag] = [rows[i] for i in range(n)]
    off, on = res[0], res[1]
    c = collections.Counter()
    c["cycles"] = 1
    if len(off) != len(on):
        c["row_count_mismatch"] += 1
        return c
    c["rows"] = len(on)
    for r in off:
        if r.state != P.ABANDONED:
            c[f"off_state_{r.state}"] += 1
    off_new = {bytes(r.payload)[:10] for r in off if r.state == P.NEW_GATED}
    on_new_by_set = collections.defaultdict(set)
    for r0, r1 in zip(off, on):
        if r1.state == P.ABANDONED or r0.state != P.NO_CRC:
            continue
        c["walk_rows"] += 1
        if r1.provenance <= 0:
            c["walk_found_nothing"] += 1
            continue
        s = SET_NAME[r1.provenance]
        c[f"{s}_first_success"] += 1
        c[f"{s}_{STATE_NAME.get(r1.state, 'OTHER')}"] += 1
        if r1.state == P.NEW_GATED:
            on_new_by_set[s].add(bytes(r1.payload)[:10])
    all_on_new = set().union(*on_new_by_set.values()) if on_new_by_set else set()
    c["published_distinct_new_vs_off"] += len(all_on_new - off_new)
    for s, v in on_new_by_set.items():
        c[f"{s}_published_distinct"] += len(v - off_new)
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--cycles", type=int, default=0)
    a = ap.parse_args()
    assert R.CG.file_sha256(a.dll) == P.PIN
    import hashlib
    assert hashlib.sha256(open(SELECTION, "rb").read().replace(b"\r\n", b"\n")).hexdigest() == SELECTION_SHA256_LF
    stamps = json.load(open(SELECTION))["runs"][RUN]["FULL"]
    if a.cycles:
        stamps = stamps[:a.cycles]
    tot = collections.Counter()
    with ProcessPoolExecutor(max_workers=a.workers, initializer=P._init, initargs=(a.dll, P.PIN)) as ex:
        for c in ex.map(_cycle, stamps, chunksize=8):
            tot.update(c)
    out = dict(sorted(tot.items()))
    out["dll_sha256"] = P.PIN
    out["selection_sha256_lf"] = SELECTION_SHA256_LF
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
