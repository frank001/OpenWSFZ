#!/usr/bin/env python3
"""GAP-LOCATE Amendment 4 sec.3: M_nonstd_W3 classification.

For each N row (Leg F, not found) that has >=1 CRC-valid wrong payload somewhere in its
9-cell search, re-extract and check whether ANY such payload's i3 differs from REF's own
i3 (a genuine type mismatch, same class as K-WHO's W3). Counted separately per Amendment 4
sec.3 ("must be disclosed, not folded into N").

NFR-021/HK-037: X/Y/bits live only in this function; only the boolean classification and
counts leave it.
"""
from __future__ import annotations

import sys
import os
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lattice  # noqa: E402
import wavio  # noqa: E402
import gl_dll_pin as DC  # noqa: E402
from ldpc_decode_ctypes import a91_to_bits  # noqa: E402
import pack77_fields as PF  # noqa: E402


def classify(dec, corpus_dir: str, rows: list, ref: dict, delta: float, cycle_wav_path_fn, log) -> dict:
    """rows: list of (ts, message) keys (N rows with f_wrong True)."""
    import collections
    by_ts = collections.OrderedDict()
    for k in rows:
        by_ts.setdefault(k[0], []).append(k)

    n_type_mismatch = 0
    n_same_type_diff_content = 0
    t0 = time.perf_counter()
    n_done = 0
    for ts, keys_here in by_ts.items():
        pcm = wavio.load_cycle_pcm(cycle_wav_path_fn(corpus_dir, ts))
        for k in keys_here:
            msg = k[1]
            snr, ref_dt, freq_hz = ref[k]
            x_true = dec.true_codeword(msg)
            X = x_true[:DC.FT8_PAYLOAD_BITS]
            ix = PF.i3_of(X)
            nominal_t = ref_dt + delta
            cells = lattice.snap_and_neighbours(freq_hz, nominal_t)
            row_type_mismatch = False
            row_same_type = False
            for cell in cells:
                rc, llr = dec.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
                if rc != 0:
                    continue
                res = dec.ldpc_decode_llrs(llr, max_iters=DC.K_LDPC_ITERATIONS, osd_depth=DC.OSD_DEPTH)
                if res["a91"] is None or res["crc_ok"] != 1:
                    continue
                Y = a91_to_bits(res["a91"], DC.FT8_PAYLOAD_BITS)
                if Y == X:
                    continue  # would have been 'found' already -- shouldn't occur in N population
                iy = PF.i3_of(Y)
                if iy != ix:
                    row_type_mismatch = True
                else:
                    row_same_type = True
            if row_type_mismatch:
                n_type_mismatch += 1
            elif row_same_type:
                n_same_type_diff_content += 1
            n_done += 1
            if n_done % 200 == 0:
                log("  [%d/%d rows] elapsed=%.0fs" % (n_done, len(rows), time.perf_counter() - t0))
    log("classify_nonstd done: %d rows, type_mismatch=%d, same_type_diff_content=%d (elapsed=%.0fs)"
        % (n_done, n_type_mismatch, n_same_type_diff_content, time.perf_counter() - t0))
    return {"n_rows": n_done, "n_type_mismatch": n_type_mismatch,
            "n_same_type_diff_content": n_same_type_diff_content}


if __name__ == "__main__":
    import row0
    import loader

    def log(m):
        print(m, flush=True)

    pop = row0.load_population(log)
    ref = pop["ref"]
    legf = json.load(open("../../../artefacts/20260927_1327_gap-locate/legf_result.json", encoding="utf-8"))
    recs = legf["records"]
    M_not_S_json = None  # reconstruct keys the same way run was launched
    legr = json.load(open("../../../artefacts/20260927_1327_gap-locate/legr_result.json", encoding="utf-8"))
    s_hits = legr["s_hits"]
    M = pop["M"]
    M_not_S = [k for k in M if ("%s|%s" % (k[0], k[1])) not in s_hits]
    assert len(M_not_S) == len(recs)

    wrong_keys = [k for k, r in zip(M_not_S, recs)
                  if (not r["excluded_unencodable"]) and (not r["found"]) and r["f_wrong"]]
    log("f_wrong N rows to classify: %d" % len(wrong_keys))

    run_dir = "../../../artefacts/20260927_1327_gap-locate"
    dec = DC.load_decoder(run_dir)
    result = classify(dec, row0.CORPUS_DIR, wrong_keys, ref, pop["delta"], loader.cycle_wav_path, log)

    out = "../../../artefacts/20260927_1327_gap-locate/nonstd_classification.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("wrote", out)
