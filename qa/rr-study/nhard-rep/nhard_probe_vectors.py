#!/usr/bin/env python
"""NHARD-REP Amendment 2 (Architect 2026-10-06 15:18Z): build and CALIBRATE the two V2' probe vectors, offline, by ctypes on the pinned DLL.

V2' probes the native OSD gate (`if (nhard > OSD_NHARD_MAX)`, patched/ft8/decode.c:995, process-global s_osd_nhard_max) through the
test-only export ft8_ldpc_decode_llrs, inside each corpus arm's own process. The audio plays no part. It needs two frozen 174-float
RAW LLR vectors built from a codeword of a Q-prefix message (NFR-021), each with a chosen number of hard-decision errors:

  P_hi : nhard_true in [48, 56]   accepted iff N >= nhard_true   (accepted at 60; rejected at 40)
  P_lo : nhard_true in [20, 32]   accepted for every N >= nhard_true (accepted at 40 and at 60)

Construction (QA's): the flipped positions get the SMALLEST |LLR| on the information bits, 3-5 on the parity bits), the errors all on parity bits (see build_vector); the gate then sees exactly nhard_true. max_iters is small so BP
does not converge (a BP-converged decode never reaches the gate). Values are quantised to multiples of 1/64, which float32 and decimal
text both hold exactly, so the C# harness reads bit-identical floats.

Calibration predicate (Amendment 2), after ft8_set_decode_params(10, 0.10, N), for each vector and each N in {30, 40, 50, 60, 100}:
  P_lo: out_path == 1 and out_crc_ok == 1 for every N >= nhard_true;
  P_hi: out_path == 1 and out_crc_ok == 1 iff N >= nhard_true, otherwise out_path == -1;
  the returned payload (first 77 bits of a91) equals the encoded message's.
If a vector cannot be made to satisfy this, this script FAILS and the run stops; nothing is substituted.

  python qa/rr-study/nhard-rep/nhard_probe_vectors.py     # writes probe_vectors.json (committed) and prints the calibration table
"""
import ctypes
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study"))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "r2-coherent-llr-instrument"))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "n1-extract-llrs-at-position"))
from harness.common import compute_seed  # noqa: E402
from ldpc_decode_ctypes import LdpcDecodeLLRs, a91_to_bits, FT8_PAYLOAD_BITS  # noqa: E402

DLL_PIN = "2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365"   # shim 20260058
SHIM = 20260058
DLL_PATH = r"D:\Projects\claude\_qa-scratch\nhard-rep\out\libft8.dll"
OUT_JSON = os.path.join(HERE, "probe_vectors.json")

MESSAGE = "CQ Q1QAA AA00"          # Q-prefix synthetic call (NFR-021); never a real station
LABEL = "NHARD-REP-V2P"
N_VALUES = (30, 40, 50, 60, 100)  # Amendment 2
K_MIN, CORR = 10, 0.10            # the corpus arms' own values
MAX_ITERS = 1                     # small, so BP does not converge (calibration asserts it did not)
OSD_DEPTH = 2                     # production's ndeep (ftx_decode_candidate)
QUANT = 64.0
VECTORS = {"P_hi": 52, "P_lo": 26}   # nhard_true: [48,56] and [20,32] (Amendment 2)
RANGES = {"P_hi": (48, 56), "P_lo": (20, 32)}
GOOD_MAG, BAD_MAG, FLIP_MAG = (3.0, 5.0), (0.1, 0.5), (0.6, 0.8)   # parity-ok, information bits, parity-flipped


N_INFO = 91   # the FT8 LDPC (174,91) code is systematic: bits 0..90 (payload + CRC) are the information bits, 91..173 the 83 parity bits


def build_vector(cw, nhard_true, idx):
    """Sign convention is the gate's own: hd = llr > 0 ? 0 : 1 (decode.c:~985), so a positive LLR means bit 0. (BP, which reads the
    opposite sense, then sees the complement and never converges: the probe always reaches the OSD gate.)

    Why the errors go on the PARITY bits with HIGH |LLR| (found by reading osd_decode, decode.c:507, and by experiment): this OSD
    eliminates the parity-check matrix H in reliability order, so the 83 most reliable columns become PIVOTS, whose values are
    RE-COMPUTED from the free bits, and the 91 least reliable columns are the FREE bits, taken from hard decisions (flips searched
    only among the 32 least reliable). The code is systematic, so the 83 parity columns of H are invertible: giving them high |LLR|
    makes them exactly the pivots, and the 91 information bits (low |LLR|, all correct) the free set. The 0-flip trial then returns
    the true codeword whatever the signs of the pivot bits; the gate then counts the sign errors there: exactly nhard_true."""
    rng = np.random.default_rng(compute_seed(LABEL, idx, nhard_true))
    mag = np.concatenate([rng.uniform(*BAD_MAG, N_INFO), rng.uniform(*GOOD_MAG, 174 - N_INFO)])
    flipped = np.sort(N_INFO + rng.choice(174 - N_INFO, nhard_true, replace=False))
    # The flipped pivots stay ABOVE every information bit (0.6 > 0.5) so they are still pivots, but weak, so the gate's SECOND
    # feature (corr/norm >= osd_corr_threshold 0.10) still passes with 52 of the 83 pivot signs wrong.
    mag[flipped] = rng.uniform(*FLIP_MAG, nhard_true)
    llr = np.where(np.asarray(cw) == 0, 1.0, -1.0) * mag
    llr[flipped] *= -1.0
    llr = np.round(llr * QUANT) / QUANT
    assert np.all(llr != 0.0)
    return llr.astype(np.float32), flipped


def gate_hamming(llr, cw):
    """The gate's own arithmetic (decode.c:~985): hd = llr > 0 ? 0 : 1 against the codeword bits."""
    hd = np.where(llr > 0.0, 0, 1)
    return int(np.sum(hd != np.asarray(cw)))


def set_params(dll, n):
    dll.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]
    dll.ft8_set_decode_params.restype = None
    dll.ft8_set_decode_params(K_MIN, ctypes.c_float(CORR), n)


def decode(d, llr, n):
    set_params(d.dll, n)
    return d.ldpc_decode_llrs(list(map(float, llr)), max_iters=MAX_ITERS, osd_depth=OSD_DEPTH)


def main():
    d = LdpcDecodeLLRs(DLL_PATH, verify=True, expected_sha256=DLL_PIN, expected_shim_version=SHIM)
    cw = d.true_codeword(MESSAGE)
    assert cw is not None and len(cw) == 174
    # --- 1. sanity: a clean vector (0 errors) reaches the OSD gate (BP sees the complement and fails) and decodes, payload equal ---
    llr0, _ = build_vector(cw, 0, 99)
    set_params(d.dll, 60)
    r0 = d.ldpc_decode_llrs(list(map(float, llr0)), max_iters=MAX_ITERS, osd_depth=OSD_DEPTH)
    assert r0["rc"] == 0 and r0["path"] == 1 and r0["crc_ok"] == 1 and a91_to_bits(r0["a91"], FT8_PAYLOAD_BITS) == cw[:FT8_PAYLOAD_BITS], r0
    print("clean vector: path", r0["path"], "crc", r0["crc_ok"], "payload equal")
    # --- 2. build, then calibrate ---
    out = {"message": MESSAGE, "label": LABEL, "dll_sha256": DLL_PIN, "shim": SHIM, "max_iters": MAX_ITERS, "osd_depth": OSD_DEPTH,
           "k_min_score_pass2": K_MIN, "osd_corr_threshold": CORR, "sign_convention": "llr>0 means bit 0 (the gate's hd = llr>0?0:1)", "quant": QUANT,
           "n_values": list(N_VALUES), "good_mag": GOOD_MAG, "bad_mag": BAD_MAG, "flip_mag": FLIP_MAG, "codeword_bits": [int(b) for b in cw],
           "vectors": {}, "calibration": {}}
    for idx, (name, nh) in enumerate(VECTORS.items()):
        lo, hi = RANGES[name]
        assert lo <= nh <= hi
        llr, flipped = build_vector(cw, nh, idx)
        gh = gate_hamming(llr, cw)
        assert gh == nh, (name, gh, nh)   # the gate's arithmetic on the sign vector gives exactly nhard_true
        rows = {}
        expected_a91 = None
        for n in N_VALUES:
            r = decode(d, llr, n)
            assert r["rc"] == 0, (name, n, r)
            accepted = r["path"] == 1 and r["crc_ok"] == 1
            payload_ok = accepted and a91_to_bits(r["a91"], FT8_PAYLOAD_BITS) == cw[:FT8_PAYLOAD_BITS]
            want = n >= nh
            assert r["path"] != 0, f"BP converged on {name} at N={n}: the probe would not reach the gate (lower max_iters)"
            assert accepted == want, f"{name} N={n}: accepted={accepted} expected {want} (nhard_true {nh}) {r}"
            if not want:
                assert r["path"] == -1, (name, n, r)
            if accepted:
                assert payload_ok, (name, n)
                expected_a91 = r["a91"].hex()
            rows[str(n)] = {"path": r["path"], "crc_ok": r["crc_ok"], "accepted": accepted, "payload_match": bool(payload_ok)}
        # the exact threshold, by scan: rejected at nhard_true - 1, accepted at nhard_true
        thr = next(n for n in range(0, 130) if (lambda r: r["path"] == 1 and r["crc_ok"] == 1)(decode(d, llr, n)))
        assert thr == nh, (name, thr, nh)
        out["vectors"][name] = {"nhard_true": nh, "llr": [float(x) for x in llr], "flipped_positions": [int(x) for x in flipped],
                                "expected_a91_hex": expected_a91, "payload_bits": FT8_PAYLOAD_BITS}
        out["calibration"][name] = {"by_N": rows, "scan_threshold": thr}
        print(name, "nhard_true", nh, "scan threshold", thr, {n: rows[str(n)]["accepted"] for n in N_VALUES})
    set_params(d.dll, 60)   # leave the process-global at the default; this process exits anyway
    with open(OUT_JSON, "w", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("wrote", OUT_JSON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
