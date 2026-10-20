#!/usr/bin/env python3
"""Q-GATE-2 validity rows V-G1 and V-C1 (spec section 6 + Amendment 1 A1.3: the equivalence evidence on the pinned DLL).

Sample: COH-GAIN extension sample `ext` (rows_ext.json, residue 5 of the 20261004_1634 night), with its persisted results (rr_2026-10-06_coh_gain_ext/rows.csv, produced by DLL 2fa6d993, shim 20260058,
nhard 40, inverted OSD).
  V-G1  every ext row persisted as G-RIGHT on path 0 (BP; G_ok = 1 and G_path = 0) is G-RIGHT on path 0 with the pinned DLL (nine cells, BP only, osd_depth -1):  >= 99.9 %.
  V-C1  on the first 300 rows (sorted by cycle_index, widx; fault rows excluded as in the persisted run): C3_ok / C3_crc / C3_path / C3_nbe reproduce on 100 % of the rows whose persisted
        C3_path is 0; and the NEW path is 0 exactly when the OLD path was 0 for ALL 300 rows (BP is unchanged by the OSD fix). Rows with an old OSD path (1) are counted, not compared (the fix
        changes OSD by design).
HK-037: numbers only. Usage: python qg2_vg.py <out dir> [--workers 4]
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_rows as ROWS  # noqa: E402
import cg_select as SEL  # noqa: E402
import comparator as CMP  # noqa: E402
import fine_sync as FS  # noqa: E402
import lattice  # noqa: E402
import qg2  # noqa: E402
import wavio  # noqa: E402
from ldpc_decode_ctypes import a91_to_bits  # noqa: E402

EXT_DIR = os.path.join(SEL.ART, "rr_2026-10-06_coh_gain_ext")
_DEC = _WS = None


def _init(dll):
    global _DEC, _WS
    _DEC = qg2.load_decoder(dll)
    _WS = SEL.read_alltxt(SEL.WS_ALLTXT)


def _work(task):
    stamp, items = task                      # items: [(widx, freq, dt, snr, want_g, want_c3)]
    pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, stamp + ".wav"))
    lines = _WS.get(stamp, [])
    out = []
    for (ci, widx, freq, dt, snr, want_g, want_c3) in items:
        rec = {"ci": ci, "widx": widx}
        if widx >= len(lines) or lines[widx][0] != snr or lines[widx][2] != freq:
            rec["fault"] = 1
            out.append(rec)
            continue
        text = lines[widx][3]
        truth_bits = _DEC.true_codeword(text)
        truth_payload = truth_bits[:CG.PAYLOAD_BITS]
        af, at = float(freq), CG.anchor_time(dt)
        if want_g:
            ok = 0
            for cell in lattice.snap_and_neighbours(af, at):
                rc, llr = _DEC.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
                if rc != 0:
                    continue
                r = _DEC.ldpc_decode_llrs([float(x) for x in llr], max_iters=CG.K_LDPC_ITERATIONS, osd_depth=-1)
                if r["rc"] == 0 and r["path"] == 0 and r["crc_ok"] == 1 and CMP.payload_match(truth_payload, a91_to_bits(r["a91"], CG.PAYLOAD_BITS), text, CG.V_STAR):
                    ok = 1
                    break
            rec["g_path0_ok"] = ok
        if want_c3:
            est = FS.estimate(pcm, af, at)
            v = CG.coherent_llrs(pcm, af, at, est)
            r = CG._arm_result(_DEC, v["V3"], truth_bits, text, truth_payload)
            rec.update({"c3_ok": r["ok"], "c3_path": r["path"], "c3_crc": r["crc"], "c3_nbe": r["nbe"]})
        out.append(rec)
    return out


def main():
    out_dir = sys.argv[1]
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    dll = os.path.join(qg2.WORK, "bin", "libft8.dll")
    os.makedirs(out_dir, exist_ok=True)
    old = ROWS.load_rows(os.path.join(EXT_DIR, "rows.csv"))
    spec = json.load(open(SEL.EXT_ROWS_JSON))
    meta = {(r[0], r[2]): r for r in spec["rows"]}             # (cycle_index, widx) -> [ci, stamp, widx, freq, dt, snr, ...]
    ordered = sorted(old, key=lambda r: (int(r["cycle_index"]), int(r["widx"])))
    first300 = {(int(r["cycle_index"]), int(r["widx"])) for r in [x for x in ordered][:CG.V5_ROWS]}
    by = {}
    for r in old:
        if int(r["fault"]):
            continue
        k = (int(r["cycle_index"]), int(r["widx"]))
        m = meta[k]
        want_g = int(r["G_ok"]) == 1 and int(r["G_path"]) == 0
        want_c3 = k in first300
        if want_g or want_c3:
            by.setdefault((m[0], m[1]), []).append((m[0], m[2], m[3], m[4], m[5], want_g, want_c3))
    tasks = list(by.items())
    t0 = time.time()
    res = {}
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(dll,)) as ex:
        for recs in ex.map(_work, [(st, items) for (_ci, st), items in tasks], chunksize=4):
            for r in recs:
                res[(r["ci"], r["widx"])] = r
    # ---- V-G1
    g_rows = [(int(r["cycle_index"]), int(r["widx"])) for r in old if not int(r["fault"]) and int(r["G_ok"]) == 1 and int(r["G_path"]) == 0]
    g_ok = sum(res[k].get("g_path0_ok", 0) for k in g_rows)
    g_share = g_ok / len(g_rows)
    # ---- V-C1
    c_rows = [r for r in ordered[:CG.V5_ROWS] if not int(r["fault"])]
    cmp_rows = [r for r in c_rows if int(r["C3_path"]) == 0]
    same = sum(int(all(res[(int(r["cycle_index"]), int(r["widx"]))][f"c3_{k}"] == int(r[f"C3_{k}"]) for k in ("ok", "crc", "path", "nbe"))) for r in cmp_rows)
    bp_agree = sum(int((res[(int(r["cycle_index"]), int(r["widx"]))]["c3_path"] == 0) == (int(r["C3_path"]) == 0)) for r in c_rows)
    out = {"dll_sha256": CG.file_sha256(dll), "ext_rows_total": len(old),
           "V-G1": {"persisted_G_right_path0_rows": len(g_rows), "reproduced": g_ok, "share": round(g_share, 6), "bar": 0.999, "result": "PASS" if g_share >= 0.999 else "FAIL"},
           "V-C1": {"first300_rows_used": len(c_rows), "old_path0_rows_compared": len(cmp_rows), "identical_ok_crc_path_nbe": same,
                    "old_path_not_0_rows_not_compared": len(c_rows) - len(cmp_rows), "bp_path0_agreement_all_rows": f"{bp_agree}/{len(c_rows)}",
                    "result": "PASS" if (same == len(cmp_rows) and bp_agree == len(c_rows)) else "FAIL"},
           "seconds": round(time.time() - t0)}
    json.dump(out, open(os.path.join(out_dir, "vg.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
