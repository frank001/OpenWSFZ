#!/usr/bin/env python3
"""Q-GATE-2 validity row V-T1 (spec section 6, amended): the type-4 scorer reproduces ENC-ID's persisted enc_match on the 795 FIELD-ID X rows: 795 / 795.

The scorer is cg_encid.enc_flags (the SAME code qg2.py imports, unchanged). The X payloads are re-extracted exactly as ENC-ID did (the OLD pinned DLL 2fa6d993, shim 20260058, via
cg_encid._work), the flags recomputed and compared with the persisted encid_rows.csv. The output goes to _qa-scratch, never over the persisted file.
HK-037: numbers and flags only. Usage: python qg2_vt1.py <out dir> [--workers 4]
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_encid as EN  # noqa: E402


def main():
    out = sys.argv[1]
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    os.makedirs(out, exist_ok=True)
    dll = os.path.join(EN.ART, "rr_2026-10-06_coh_gain", "bin", "libft8_20260058.dll")
    assert CG.file_sha256(dll) == CG.DLL_PIN, "old DLL differs from its pin"
    rows = EN.load_list()
    new_csv = os.path.join(out, "encid_rows_rerun.csv")
    recs, secs = EN._run(rows, EN._work, EN.OUT_COLUMNS, new_csv, workers, dll, lambda r: (r["kind"], r["sample"], r["cycle_index"], r["widx"]), 100)
    old = {(r["kind"], int(r["sample"]), int(r["cycle_index"]), int(r["widx"])): r for r in csv.DictReader(open(EN.OUT_CSV, newline=""))}
    n = same = same_all = 0
    for r in recs:
        if r["kind"] != "X":
            continue
        o = old[(r["kind"], int(r["sample"]), int(r["cycle_index"]), int(r["widx"]))]
        n += 1
        same += int(str(r["enc_match"]) == str(o["enc_match"]))
        same_all += int(all(str(r[k]) == str(o[k]) for k in ("enc_match", "call_eq", "hash_eq", "icq", "nrpt", "t_has_placeholder")))
    res = {"X_rows": n, "enc_match_equal": same, "all_flags_equal": same_all, "rows_total": len(recs), "V-T1": "PASS" if (n == 795 and same == 795) else "FAIL",
           "dll": CG.file_sha256(dll), "seconds": round(secs)}
    json.dump(res, open(os.path.join(out, "vt1.json"), "w"))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
