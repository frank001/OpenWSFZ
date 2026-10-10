#!/usr/bin/env python
"""OSD-FIX V2' probe vectors (ruling 2026-10-08-1545 A3): recalibrated on the corrected build and COMMITTED BEFORE ANY FIX-ARM DECODE.

The NHARD-REP probe vectors (probe_vectors.json, SHA pinned) were built in the OSD gate's own sign convention (llr > 0 means bit 0), which is what the
shipped, INVERTED OSD received un-negated. With the fix on, the build negates the LLRs before OSD and its gate, so a vector must now be given in the
EXTRACTOR convention (positive = bit 1): the new vectors are the old ones NEGATED. The gate then sees exactly the array the old vectors gave the old gate, so the
calibrated thresholds are expected unchanged (P_hi 52, P_lo 26); this script does not assume it, it scans.

Calibration on the new DLL (shim 20260060, SHA pinned), production parameters (k_min 10, corr 0.10), max_iters 1, depth 2:
  FIX vectors  (negated)  at switch 1: P_lo accepted for every N >= 26; P_hi accepted iff N >= 52, else path -1; BP never converges (path != 0); payload equal;
                          exact threshold by scan == nhard_true.
  OLD vectors  (as on file) at switch 0 on the NEW dll: the same table as on the old DLL (REF arms keep the OLD vectors, ruling A3).
  And as a blind-instrument control: the FIX vectors at switch 0 and the OLD vectors at switch 1 must NOT behave as calibrated (the vectors are sign-specific; if they
  did, the probe would not detect a switch that was not applied).
Fails (non-zero exit, nothing written) if any of this does not hold.

  python qa/rr-study/osd-fix/osd_fix_probe_vectors.py --new-dll <path> --new-sha <sha256>
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study"))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "r2-coherent-llr-instrument"))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "nhard-rep"))
from ldpc_decode_ctypes import LdpcDecodeLLRs, a91_to_bits, FT8_PAYLOAD_BITS  # noqa: E402
import nhard_probe_vectors as NPV  # noqa: E402  (set_params, constants)

OLD_JSON = os.path.join(REPO, "qa", "rr-study", "nhard-rep", "probe_vectors.json")
OLD_JSON_SHA256 = "bc914e99513a57f09b93f146ad18423d9836333eba41958174468b29b31e27b8"   # LF bytes (NHARD-REP pin)
OUT_JSON = os.path.join(HERE, "probe_vectors_fix.json")
NEW_SHIM = 20260060
N_VALUES = NPV.N_VALUES


def run_vector(d, llr, n, switch):
    d.dll.ft8_set_osd_sign_fix(switch)
    NPV.set_params(d.dll, n)
    return d.ldpc_decode_llrs([float(x) for x in llr], max_iters=NPV.MAX_ITERS, osd_depth=NPV.OSD_DEPTH)


def accepted(r):
    return r["rc"] == 0 and r["path"] == 1 and r["crc_ok"] == 1


def calibrate(d, name, llr, nh, cw, switch):
    """-> (rows by N, scan threshold, expected_a91_hex). Asserts the Amendment-2 predicate; raises AssertionError otherwise."""
    rows, a91 = {}, None
    for n in N_VALUES:
        r = run_vector(d, llr, n, switch)
        assert r["rc"] == 0 and r["path"] != 0, f"{name} N={n}: BP converged or rc != 0 {r}"
        acc = accepted(r)
        assert acc == (n >= nh), f"{name} N={n} switch={switch}: accepted={acc} expected {n >= nh} (nhard_true {nh}) {r}"
        if not acc:
            assert r["path"] == -1, (name, n, r)
        else:
            assert a91_to_bits(r["a91"], FT8_PAYLOAD_BITS) == cw[:FT8_PAYLOAD_BITS], (name, n, "payload differs")
            a91 = r["a91"].hex()
        rows[str(n)] = {"path": r["path"], "crc_ok": r["crc_ok"], "accepted": acc}
    thr = next(n for n in range(0, 130) if accepted(run_vector(d, llr, n, switch)))
    assert thr == nh, (name, switch, "scan threshold", thr, nh)
    return rows, thr, a91


def behaves_as_calibrated(d, llr, nh, switch):
    """True iff the vector shows the calibrated accept/reject pattern at every N (used for the negative controls: must be False)."""
    return all(accepted(run_vector(d, llr, n, switch)) == (n >= nh) for n in N_VALUES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-dll", required=True)
    ap.add_argument("--new-sha", required=True)
    a = ap.parse_args()
    assert hashlib.sha256(open(OLD_JSON, "rb").read().replace(b"\r\n", b"\n")).hexdigest() == OLD_JSON_SHA256, "old probe_vectors.json differs from its pin"
    old = json.load(open(OLD_JSON, encoding="utf-8"))
    d = LdpcDecodeLLRs(a.new_dll, verify=True, expected_sha256=a.new_sha, expected_shim_version=NEW_SHIM, check_version=True)
    cw = old["codeword_bits"]
    assert d.true_codeword(old["message"]) == cw, "codeword differs"
    out = {"message": old["message"], "label": "OSD-FIX-V2P", "dll_sha256": a.new_sha, "shim": NEW_SHIM, "max_iters": NPV.MAX_ITERS, "osd_depth": NPV.OSD_DEPTH,
           "k_min_score_pass2": NPV.K_MIN, "osd_corr_threshold": NPV.CORR, "osd_sign_fix": 1,
           "sign_convention": "llr>0 means bit 1 (the extractor/BP convention); the build negates it before OSD and its gate (switch 1)",
           "derived_from": {"file": "qa/rr-study/nhard-rep/probe_vectors.json", "sha256_lf": OLD_JSON_SHA256, "transform": "llr -> -llr"},
           "quant": old["quant"], "n_values": list(N_VALUES), "codeword_bits": cw, "vectors": {}, "calibration": {}, "old_vectors_switch0_on_new_dll": {}, "negative_controls": {}}
    for name, v in old["vectors"].items():
        nh = v["nhard_true"]
        neg = [-float(x) for x in v["llr"]]
        rows, thr, a91 = calibrate(d, name, neg, nh, cw, 1)
        assert a91 == v["expected_a91_hex"], (name, "payload bytes differ from the old calibration")
        out["vectors"][name] = {"nhard_true": nh, "llr": neg, "expected_a91_hex": a91, "payload_bits": v["payload_bits"], "flipped_positions": v["flipped_positions"]}
        out["calibration"][name] = {"by_N": rows, "scan_threshold": thr}
        # REF arms keep the OLD vectors at switch 0: they must still calibrate on the new DLL
        rows0, thr0, _ = calibrate(d, name, v["llr"], nh, cw, 0)
        out["old_vectors_switch0_on_new_dll"][name] = {"by_N": rows0, "scan_threshold": thr0}
        # negative controls: a vector given in the wrong convention for the switch must NOT look calibrated
        out["negative_controls"][name] = {"fix_vector_at_switch0_calibrated": behaves_as_calibrated(d, neg, nh, 0),
                                          "old_vector_at_switch1_calibrated": behaves_as_calibrated(d, v["llr"], nh, 1)}
        assert not out["negative_controls"][name]["fix_vector_at_switch0_calibrated"], (name, "blind: FIX vector passes at switch 0")
        assert not out["negative_controls"][name]["old_vector_at_switch1_calibrated"], (name, "blind: OLD vector passes at switch 1")
        print(name, "nhard_true", nh, "FIX@1 threshold", thr, "OLD@0 threshold", thr0, out["negative_controls"][name])
    d.dll.ft8_set_osd_sign_fix(1)
    NPV.set_params(d.dll, 60)
    with open(OUT_JSON, "w", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    sha = hashlib.sha256(open(OUT_JSON, "rb").read().replace(b"\r\n", b"\n")).hexdigest()
    print("wrote", OUT_JSON)
    print("probe_vectors_fix_sha256_lf", sha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
