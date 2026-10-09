#!/usr/bin/env python
"""OSD-FIX A-SIGN' (spec section 5.1, ruling 2026-10-08-1545 section 3 / A5): is the sign fix real, row for row, on real LLRs?

Two DLLs are loaded in ONE process (distinct file names, so Windows keeps them apart):
  OLD  artefacts/rr_2026-10-06_coh_gain/bin/libft8_20260058.dll  SHA 2fa6d993...f365 (shim 20260058; native == origin/main 81f74ede)
  NEW  the Developer's build (feat/osd-sign-fix 3276573b, shim 20260060), SHA pinned below
For every row, for each of G's nine lattice cells' raw LLR vectors `llr` (the extractor is unchanged; asserted equal on both DLLs):
  REF-S   OLD.ldpc_decode_llrs( llr, max_iters=1, depth=2)        as shipped (inverted OSD)
  REF-N   OLD.ldpc_decode_llrs(-llr, max_iters=1, depth=2)        QA's 2026-10-06 method: the HARNESS negates (today's export then hands OSD and its gate the same corrected array)
  NEW-0   NEW (switch 0).ldpc_decode_llrs( llr, ...)              must equal REF-S                                  (iii)
  NEW-1   NEW (switch 1).ldpc_decode_llrs( llr, ...)              must equal REF-N                                  (ii)
"Equal" = rc, path, crc_ok, ldpc_errors and the 12-byte a91, all equal. The a91 never leaves this function (HK-037); what is persisted is numeric.
Also (information): the same four arms at max_iters 50 (the production setting) and the production-path count of true payloads.

Row sets (both reported):
  PILOT   the 50 pilot rows listed in rows.json ('pilot_rows'): the rows QA's 2026-10-06 reading (0/50 shipped, 16/50 negated) came from. If REF-S/REF-N
          reproduce that reading here, the ORIGINAL bars (switch-1 >= 16/50, switch-0 0/50) stand and (ii)/(iii) are added (ruling A5).
  GFAIL   the first 50 rows of the frozen list (rows.json order) with G_ok == 0 in the main-run rows.csv (the A5 fallback population).
A row counts as "true" if ANY of its nine cells returns a CRC-valid OSD (path 1) payload equal to the true payload (comparator.payload_match, ROW 0f v_star).

Predicates (code, committed before the run):
  (ii-a) on every cell where the NEW DLL's one-iteration BP did NOT converge (path != 0), NEW-1 == REF-N (same_osd: rc, path, crc_ok; ldpc_errors and a91 when OSD accepted)
         (cells where BP converges on +llr never reach OSD in NEW, so they cannot be compared; they are counted: bp_converged_cells)
  (ii-b) every row that REF-N recovers with a true payload is also recovered (any path) by NEW-1                       (no row lost by the DLL relative to the harness-negated method)
  (iii) NEW-0 == REF-S on every cell of every row of the set
  (iv)  rows with a switch-1 true payload >= 1
  (i)   R5(a) passes: external (the unit test); not computed here.
  ORIG  (pilot only) rows(true | REF-S) == 0 and rows(true | NEW-1, any path) >= 16.
  (iv)  rows with a switch-1 true payload by the OSD path (path 1) >= 1; true_new1_any (BP or OSD) is reported beside it.

  python qa/rr-study/osd-fix/osd_fix_asign.py --new-dll <path> --new-sha <sha256> --out <dir>
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "coh-gain"))

SET_SIZE = 50
OLD_DLL_REL = os.path.join("artefacts", "rr_2026-10-06_coh_gain", "bin", "libft8_20260058.dll")
MAIN_ROWS_CSV_REL = os.path.join("artefacts", "rr_2026-10-06_coh_gain", "rows.csv")
FROZEN_REL = os.path.join("qa", "rr-study", "results", "2026-10-06-coh-gain", "rows.json")
NEW_SHIM = 20260060
BP_ITERS_FORCED = 1          # QA's 2026-10-06 method: BP sees the complement and cannot converge, so OSD decides
OSD_DEPTH = 2
PILOT_ORIG_MIN_NEG = 16
FIELDS = ("rc", "path", "crc_ok", "ldpc_errors", "a91")


def same(a: dict, b: dict) -> bool:
    """Row-for-row equality of two ft8_ldpc_decode_llrs results (a91 included): the strict comparison used for (iii) and at 50 iterations."""
    return all(a[k] == b[k] for k in FIELDS)


def same_osd(a: dict, b: dict) -> bool:
    """Equality for (ii), where the two arms reach OSD through DIFFERENT BP inputs (new: +llr, old: -llr). BP's own residual parity count differs between
    an input and its complement, so ldpc_errors is compared only when OSD accepted (the export then resets it to 0); a91 only when a codeword came out.
    rc, path and crc_ok are always compared. Fires on any difference in the accepted payload (tests/test_osd_fix_asign.py)."""
    if (a["rc"], a["path"], a["crc_ok"]) != (b["rc"], b["path"], b["crc_ok"]):
        return False
    if a["path"] == 1:
        return a["ldpc_errors"] == b["ldpc_errors"] and a["a91"] == b["a91"]
    return True


def is_true_any(res: dict, truth_payload, text, CG, CMP, a91_to_bits) -> bool:
    """CRC-valid true payload by ANY path (BP or OSD)."""
    return bool(res["rc"] == 0 and res["crc_ok"] == 1 and res["path"] in (0, 1) and res["a91"] is not None
                and CMP.payload_match(truth_payload, a91_to_bits(res["a91"], CG.PAYLOAD_BITS), text, CG.V_STAR))


def is_true(res: dict, truth_payload, text, CG, CMP, a91_to_bits) -> bool:
    return bool(res["rc"] == 0 and res["path"] == 1 and res["crc_ok"] == 1 and res["a91"] is not None
                and CMP.payload_match(truth_payload, a91_to_bits(res["a91"], CG.PAYLOAD_BITS), text, CG.V_STAR))


def verdict(n_ii_fail, n_iii_fail, true_new1_osd_rows, rows_lost, ii_compared, orig=None):
    out = {"ii_a": n_ii_fail == 0 and ii_compared > 0, "ii_b": rows_lost == 0, "iii": n_iii_fail == 0, "iv": true_new1_osd_rows >= 1}
    if orig is not None:
        out["orig"] = orig
    return out


def pick_rows(frozen, main_csv):
    rows = frozen["rows"]
    pilot = [tuple(r) for r in frozen["pilot_rows"]]
    gok = {}
    for r in csv.DictReader(open(main_csv, newline="", encoding="utf-8")):
        if int(float(r["fault"] or 0)) == 0:
            gok[(int(float(r["cycle_index"])), int(float(r["widx"])))] = int(float(r["G_ok"]))
    gfail = [tuple(r) for r in rows if gok.get((r[0], r[2])) == 0][:SET_SIZE]
    return pilot, gfail


def run_set(name, rows, old, new, WS, CG, SEL, CMP, wavio, a91_to_bits, lattice):
    import numpy as np  # noqa: F401
    cur = {"rows": 0, "cells": 0, "fault_rows": 0, "ii_fail": 0, "iii_fail": 0, "ext_differs": 0,
           "true_refS": 0, "true_refN": 0, "true_new0": 0, "true_new1": 0,
           "it50_same0": 0, "it50_same1": 0, "it50_cells": 0, "true_prod_new1_rows": 0,
           "path1_refN_cells": 0, "path1_new1_cells": 0, "ii_compared": 0, "bp_converged_cells": 0,
           "true_new1_any": 0, "rows_lost": 0}
    per_row = []
    by_stamp = {}
    for r in rows:
        by_stamp.setdefault(r[1], []).append(r)
    for stamp, rs in by_stamp.items():
        pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, stamp + ".wav"))
        lines = WS.get(stamp, [])
        for (ci, _s, widx, ws_freq, ws_dt, ws_snr, ws_load, live_hit, _m20) in rs:
            ok_line = widx < len(lines) and lines[widx][0] == ws_snr and lines[widx][2] == ws_freq
            if not ok_line:
                cur["fault_rows"] += 1
                continue
            text = lines[widx][3]
            truth_bits = old.true_codeword(text)
            if truth_bits is None:
                cur["fault_rows"] += 1
                continue
            truth_payload = truth_bits[:CG.PAYLOAD_BITS]
            anchor_f, anchor_t = float(ws_freq), CG.anchor_time(ws_dt)
            row = {"true_refS": 0, "true_refN": 0, "true_new0": 0, "true_new1": 0, "true_new1_any": 0, "cells": 0, "ii_fail": 0, "iii_fail": 0}
            prod_true = 0
            for cell in lattice.snap_and_neighbours(anchor_f, anchor_t):
                rc_o, llr = old.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
                rc_n, llr_n = new.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
                if rc_o != 0 or rc_n != 0:
                    continue
                if list(llr) != list(llr_n):
                    cur["ext_differs"] += 1
                pos = [float(x) for x in llr]
                neg = [-x for x in pos]
                new.dll.ft8_set_osd_sign_fix(0)
                n0 = new.ldpc_decode_llrs(pos, max_iters=BP_ITERS_FORCED, osd_depth=OSD_DEPTH)
                n0_50 = new.ldpc_decode_llrs(pos, max_iters=50, osd_depth=OSD_DEPTH)
                new.dll.ft8_set_osd_sign_fix(1)
                n1 = new.ldpc_decode_llrs(pos, max_iters=BP_ITERS_FORCED, osd_depth=OSD_DEPTH)
                n1_50 = new.ldpc_decode_llrs(pos, max_iters=50, osd_depth=OSD_DEPTH)
                rS = old.ldpc_decode_llrs(pos, max_iters=BP_ITERS_FORCED, osd_depth=OSD_DEPTH)
                rN = old.ldpc_decode_llrs(neg, max_iters=BP_ITERS_FORCED, osd_depth=OSD_DEPTH)
                rS_50 = old.ldpc_decode_llrs(pos, max_iters=50, osd_depth=OSD_DEPTH)
                rN_50 = old.ldpc_decode_llrs(neg, max_iters=50, osd_depth=OSD_DEPTH)
                cur["cells"] += 1
                row["cells"] += 1
                if n1["path"] == 0:
                    cur["bp_converged_cells"] += 1
                else:
                    cur["ii_compared"] += 1
                    if not same_osd(n1, rN):
                        cur["ii_fail"] += 1
                        row["ii_fail"] += 1
                if not same(n0, rS):
                    cur["iii_fail"] += 1
                    row["iii_fail"] += 1
                cur["it50_cells"] += 1
                cur["it50_same0"] += int(same(n0_50, rS_50))
                cur["it50_same1"] += int(same(n1_50, rN_50))
                cur["path1_refN_cells"] += int(rN["path"] == 1)
                cur["path1_new1_cells"] += int(n1["path"] == 1)
                row["true_refS"] |= int(is_true(rS, truth_payload, text, CG, CMP, a91_to_bits))
                row["true_refN"] |= int(is_true(rN, truth_payload, text, CG, CMP, a91_to_bits))
                row["true_new0"] |= int(is_true(n0, truth_payload, text, CG, CMP, a91_to_bits))
                row["true_new1"] |= int(is_true(n1, truth_payload, text, CG, CMP, a91_to_bits))
                row["true_new1_any"] |= int(is_true_any(n1, truth_payload, text, CG, CMP, a91_to_bits))
                prod_true |= int(n1_50["rc"] == 0 and n1_50["crc_ok"] == 1 and n1_50["a91"] is not None
                                 and CMP.payload_match(truth_payload, a91_to_bits(n1_50["a91"], CG.PAYLOAD_BITS), text, CG.V_STAR))
            new.dll.ft8_set_osd_sign_fix(1)
            cur["rows"] += 1
            for k in ("true_refS", "true_refN", "true_new0", "true_new1", "true_new1_any"):
                cur[k] += row[k]
            cur["rows_lost"] += int(row["true_refN"] == 1 and row["true_new1_any"] == 0)
            cur["true_prod_new1_rows"] += prod_true
            per_row.append({"cycle_index": ci, "widx": widx, "ws_snr": ws_snr, **row})
    return cur, per_row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-dll", required=True)
    ap.add_argument("--new-sha", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import cg_common as CG
    import cg_select as SEL
    import wavio
    import comparator as CMP
    from ldpc_decode_ctypes import LdpcDecodeLLRs, a91_to_bits
    import lattice

    old_path = os.path.join(REPO, OLD_DLL_REL)
    old = CG.load_decoder(old_path)                          # pinned 2fa6d993..., shim 20260058, nhard 40
    new = LdpcDecodeLLRs(a.new_dll, verify=True, expected_sha256=a.new_sha, expected_shim_version=NEW_SHIM, check_version=True)
    new.dll.ft8_set_decode_params(*CG.PROD_PARAMS)
    assert CG.file_sha256(old_path) == CG.DLL_PIN and CG.file_sha256(a.new_dll) == a.new_sha

    frozen = json.load(open(os.path.join(REPO, FROZEN_REL)))
    assert CG.sha256_lf(os.path.join(REPO, FROZEN_REL)) == CG.ROWS_JSON_SHA256, "frozen rows.json differs from its pin"
    pilot, gfail = pick_rows(frozen, os.path.join(REPO, MAIN_ROWS_CSV_REL))
    assert len(pilot) == SET_SIZE and len(gfail) == SET_SIZE
    WS = SEL.read_alltxt(SEL.WS_ALLTXT)                       # text stays in this process

    result = {"old_dll_sha256": CG.DLL_PIN, "new_dll_sha256": a.new_sha, "new_shim": NEW_SHIM, "bp_iters_forced": BP_ITERS_FORCED,
              "osd_depth": OSD_DEPTH, "nhard": CG.PROD_PARAMS[2], "rows_json_sha256_lf": CG.ROWS_JSON_SHA256, "sets": {}}
    for name, rows in (("PILOT", pilot), ("GFAIL", gfail)):
        cur, per_row = run_set(name, rows, old, new, WS, CG, SEL, CMP, wavio, a91_to_bits, lattice)
        orig = None
        if name == "PILOT":
            orig = {"refS_rows": cur["true_refS"], "new1_rows": cur["true_new1"], "refN_rows": cur["true_refN"],
                    "reproduces": cur["true_refS"] == 0 and cur["true_refN"] >= PILOT_ORIG_MIN_NEG,
                    "new1_any_rows": cur["true_new1_any"],
                    "pass": cur["true_refS"] == 0 and cur["true_new1_any"] >= PILOT_ORIG_MIN_NEG}
        cur["verdict"] = verdict(cur["ii_fail"], cur["iii_fail"], cur["true_new1"], cur["rows_lost"], cur["ii_compared"], orig)
        cur["orig"] = orig
        result["sets"][name] = {"summary": cur, "per_row": per_row}
        print(name, json.dumps({k: v for k, v in cur.items()}, sort_keys=True))
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "asign_result.json"), "w", newline="\n") as fh:
        json.dump(result, fh, sort_keys=True, indent=1)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
