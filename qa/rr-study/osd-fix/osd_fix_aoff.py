#!/usr/bin/env python
"""OSD-FIX A-OFF, part 1 (spec section 5.1, row A-OFF; R7): with the switch at 0 the NEW build's native decode equals origin/main's.

Two DLLs in one process (distinct file names): OLD = libft8_20260058.dll (SHA 2fa6d993...f365, native == origin/main 81f74ede) and NEW (the
Developer's build). The FIRST `--cycles` cycles (default 100) of the frozen TRAIN list (osd_fix_select.py's selection.json, SHA pinned)
are decoded with ft8_decode_all by OLD and by NEW with ft8_set_osd_sign_fix(0), both at production parameters (k_min 10, corr 0.10, nhard 40).
Compared per cycle: the multiset of (freq_hz, dt, snr, message). Message text stays in this function (HK-037); what is persisted is numeric.
Information (not a predicate): NEW at switch 1 on the same cycles (count and how many cycles differ from switch 0).

PASS iff 0 cycles differ between OLD and NEW(switch 0). Part 2 (the Replay81 pipeline vs the N40 arm on file) is a separate harness run.

  python qa/rr-study/osd-fix/osd_fix_aoff.py --new-dll <path> --new-sha <sha256> --out <dir>
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "coh-gain"))
sys.path.insert(0, HERE)

SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-08-osd-fix", "selection.json")
SELECTION_SHA256 = "27bb840f45c77da6e65f18f855ade547e9a002a253c2946bf723a6eaa53db11e"
OLD_DLL_REL = os.path.join("artefacts", "rr_2026-10-06_coh_gain", "bin", "libft8_20260058.dll")
NEW_SHIM = 20260060


def canon(rows):
    return sorted((r["freq_hz"], round(r["dt"], 6), r["snr"], r["message"]) for r in rows)


def cycles_differ(a_by_cycle, b_by_cycle):
    """-> number of cycles whose canonical multisets differ (a missing cycle counts as differing)."""
    keys = set(a_by_cycle) | set(b_by_cycle)
    return sum(1 for k in keys if canon(a_by_cycle.get(k) or []) != canon(b_by_cycle.get(k) or []) or (k not in a_by_cycle) != (k not in b_by_cycle))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-dll", required=True)
    ap.add_argument("--new-sha", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cycles", type=int, default=100)
    a = ap.parse_args()

    import cg_common as CG
    import cg_select as SEL
    import wavio
    from ldpc_decode_ctypes import LdpcDecodeLLRs

    assert CG.sha256_lf(SELECTION) == SELECTION_SHA256, "TRAIN selection.json differs from its pin"
    stamps = json.load(open(SELECTION, encoding="utf-8"))["TRAIN"][: a.cycles]
    assert len(stamps) == a.cycles
    old = CG.load_decoder(os.path.join(REPO, OLD_DLL_REL))
    new = LdpcDecodeLLRs(a.new_dll, verify=True, expected_sha256=a.new_sha, expected_shim_version=NEW_SHIM, check_version=True)
    new.dll.ft8_set_decode_params(*CG.PROD_PARAMS)
    assert CG.file_sha256(os.path.join(REPO, OLD_DLL_REL)) == CG.DLL_PIN and CG.file_sha256(a.new_dll) == a.new_sha

    res_old, res_new0, res_new1 = {}, {}, {}
    n_old = n_new0 = n_new1 = 0
    for st in stamps:
        pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, st + ".wav"))
        r_old = old.decode_all(pcm)
        new.dll.ft8_set_osd_sign_fix(0)
        r_new0 = new.decode_all(pcm)
        new.dll.ft8_set_osd_sign_fix(1)
        r_new1 = new.decode_all(pcm)
        if r_old is None or r_new0 is None or r_new1 is None:
            raise SystemExit(f"native fault on a cycle ({st})")
        res_old[st], res_new0[st], res_new1[st] = r_old, r_new0, r_new1
        n_old += len(r_old); n_new0 += len(r_new0); n_new1 += len(r_new1)
    new.dll.ft8_set_osd_sign_fix(1)
    out = {"cycles": len(stamps), "selection_sha256_lf": SELECTION_SHA256, "old_dll_sha256": CG.DLL_PIN, "new_dll_sha256": a.new_sha,
           "decodes_old": n_old, "decodes_new_switch0": n_new0, "decodes_new_switch1": n_new1,
           "cycles_differ_old_vs_new0": cycles_differ(res_old, res_new0),
           "cycles_differ_new0_vs_new1": cycles_differ(res_new0, res_new1),
           "params": {"k_min_score_pass2": CG.PROD_PARAMS[0], "osd_corr": CG.PROD_PARAMS[1], "nhard": CG.PROD_PARAMS[2]}}
    out["A_OFF_part1_pass"] = out["cycles_differ_old_vs_new0"] == 0 and n_old > 0
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "aoff_part1.json"), "w", newline="\n") as fh:
        json.dump(out, fh, sort_keys=True, indent=1)
        fh.write("\n")
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
