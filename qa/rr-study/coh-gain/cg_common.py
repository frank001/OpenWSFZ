#!/usr/bin/env python3
"""COH-GAIN (A' step 1): shared constants, the pinned decoder, the anchor mapping and the four-arm per-signal evaluation.

Spec (PRE-REGISTERED, Architect 2026-10-06 16:22Z): qa/rr-study/2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md (branch arch/coherent-limb2).
BAR_G = 1.0 pp was RATIFIED by the Captain 2026-10-06 ~16:26Z, before any harness or extraction, and is FROZEN.

HK-037 / NFR-021: message text and every 77-bit / 174-bit array live ONLY inside evaluate_signal (the leg_fk2.py discipline). What leaves it is
numeric: success flags, decoder path / ldpc_errors / crc_ok, a bit-error COUNT, and the estimator's offsets. No text, no bits, no text-derived hash.

Arms (every arm feeds its 174 raw LLRs to ft8_ldpc_decode_llrs at nhard 40, max_iters 50, OSD depth 2: production's own BP -> OSD -> CRC):
  G   shipped ft8_extract_llrs_at, any of GAP-LOCATE's 9 lattice cells around the anchor (the control)
  C1  coherent order 1  (coherent_extract V1) at the data-free fine-sync estimate
  C3  coherent orders 1+2+3 (V3) at the same estimate                                  <- the A' candidate
  C3S as C3 at the ORACLE estimate (data-aided over all 79 tones): a ceiling, not a buildable decoder
Success = out_crc_ok == 1 AND comparator.payload_match (ROW 0f's v_star, the RR73 equivalence).

AMENDMENT 2 (Architect 2026-10-06 ~17:30Z, spec section 12; QA's OSD-sign finding, verified from source): osd_decode assumes positive = bit 0 while the extractor
and BP use positive = bit 1, so the shipped OSD stage receives the COMPLEMENT of the soft decisions. Two DESCRIPTIVE arms (no row) measure what a sign fix
would add at WSJT-X's positions:
  GO   G's LLRs: BP as production (osd_depth -1: the BP stage alone); if BP fails in a cell, OSD on the NEGATED LLRs (max_iters 1 so BP cannot converge on
       the complement, depth 2, nhard 40, corr 0.10). Any cell succeeding counts.
  C3O  the same on C3's LLRs.
Reported per arm: success, BP-only success, corrected-OSD TRUE recoveries, rows where corrected OSD returned a CRC-valid WRONG payload (the at-position FP
cost), and rows where the negated call returned path 0 (counted, treated as a failure).
"""
from __future__ import annotations

import hashlib
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RR = os.path.join(REPO_ROOT, "qa", "rr-study")
for sub in ("gap-locate", "n2-coherent-llr-extractor", "r2-coherent-llr-instrument", "n1-extract-llrs-at-position", "."):
    sys.path.insert(0, os.path.join(RR, sub))
sys.path.insert(0, HERE)

import coherent_extract as CE  # noqa: E402
import comparator as CMP  # noqa: E402
import fine_sync as FS  # noqa: E402
import lattice  # noqa: E402
import wavio  # noqa: E402
from ldpc_decode_ctypes import LdpcDecodeLLRs, a91_to_bits  # noqa: E402

# ---- frozen spec constants ---------------------------------------------------------------------------------------------------------
BAR_G = 1.0                    # pp of WSJT-X's decodes; ratified by the Captain 2026-10-06 ~16:26Z, FROZEN
SEED = 20261006
B_RESAMPLES = 10_000
BLOCK_CYCLES = 8               # section 5: 8 sampled cycles
BLOCKS_REPORTED = (4, 16)
SAMPLE_RESIDUE = 3             # section 4: positions i mod 10 == 3 (NHARD-REP used 0 and 5)
EXT_RESIDUE = 5                # AMENDMENT 4 (Architect 2026-10-06 18:19Z, spec section 14): the extension sample is positions i mod 10 == 5 (NOT 7: it hosted the pilot rows)
SAMPLE_MODULUS_PRIMARY = 10
SAMPLE_MODULUS_FALLBACK = 20   # if the 50-row timing pilot projects > PILOT_MAX_CPU_HOURS
PILOT_ROWS = 50
PILOT_RESIDUE = 7              # pilot rows come from positions i mod 10 == 7, i.e. NOT from the analysed sample
PILOT_MAX_CPU_HOURS = 6.0
V2_N = 200
V2_SNR_DB = -14.0
V2_DF_MAX_HZ = 1.5
V2_DT_MAX_S = 0.06
V2_C3_MIN = 0.95
V2_G_MIN = 0.90
# AMENDMENT 1 (Architect 2026-10-06 ~17:00Z, spec section 11, before any real-audio extraction): V2(b) -> (b'). The data-free Costas objective sums THREE
# 7-symbol blocks 36 symbols (5.76 s) apart, so its df surface has grating lobes every 1/5.76 s = 0.174 Hz: the 0.15 Hz median bar was unpassable for it.
V2_MEDIAN_DF_MAX_HZ = 0.20     # the lobe period 0.174 plus half a 0.1 Hz grid step
V2_SIGNED_MEDIAN_DF_MAX_HZ = 0.05   # no systematic frequency bias
V2_MEDIAN_DT_MAX_S = 0.0075
V2T_N = 200                    # AMENDMENT 1: DESCRIPTIVE tier near threshold (no row, never cited as the gain)
V2T_SNR_DB = -20.0
V3_MAX_EDGE_SHARE = 0.05
V4_G_MIN = 0.90
V5_ROWS = 300
ARMS = ("G", "C1", "C3", "C3S")
OSD_ARMS = ("GO", "C3O")                       # Amendment 2: descriptive, sign-corrected OSD
OSD_FIELDS = ("ok", "bp_ok", "osd_ok", "wrong", "neg0")
NEG_MAX_ITERS = 1                              # BP sees the complement of the negated LLRs and cannot converge in one iteration: the OSD path decides

# ---- frozen files, pinned by LF-normalised SHA-256 and ASSERTED by cg_run.py before anything is extracted ----
ROWS_JSON_SHA256 = "34b97c22fa61f0cb17a3ac57b8a9cad385375467fa93b96ba1d3803ea6e5c0b6"     # results/2026-10-06-coh-gain/rows.json (rows + pilot rows)
# AMENDMENT 5 (QA, under the Captain's overnight authorisation 2026-10-06 ~20:40Z): further FRESH samples. The residues not yet touched by any outcome are 1, 2, 4, 6, 8, 9
# (0 was NHARD-REP's sample, 3 the first sample, 5 the extension, 7 hosted the pilot rows). SAMPLE_PINS maps a residue to the LF SHA-256 of its frozen row list.
FRESH_RESIDUES = (1, 2, 4, 6, 8, 9)
SAMPLE_PINS = {1: "257714e02a6e840fe9307d952447d36e2b29b032f7199d98c9c0d608ce92cc07", 2: "338d13e2c53e0a2728cd7d41b94f1b7a19ef8eeb67f214d1b401f69897827e81", 4: "8491f8c308f1bc5db0ea3886d3c5814ac9b0b47881f95d315e1e9fa4643bed5d", 6: "4c892a6c291aac46492b3e819c2a78e16b474de4e0ea35e990b5683c07573346", 8: "7d75de195ac4a8406a0c3c3024fc9c449dbc02c3dfdf85416a690c3178c3d513", 9: "122d666f6a3fd2ee672da3c3cd8c05e81805e0297f4c3f996134777ad671e9e9"}   # LF SHA-256 of results/2026-10-06-coh-gain/rows_r<residue>.json, frozen BEFORE any extraction
ROWS_EXT_JSON_SHA256 = "7267de64c3979fe7838a32cbcd2a46d63e10316cc2dea1cad67220c9c4ff8852"  # results/2026-10-06-coh-gain/rows_ext.json (Amendment 4, i mod 10 == 5)
SYNTH_SHA256 = "ab787588b2a93a3817dc1f4781aee70199e7d6d87255a1ffcc11517c853f6a0e"        # synthetic_set.json (V2, -14 dB)
SYNTH_T_SHA256 = "3b5422caafd504fea49b6bdfcbd0f72db6a76d000f42ed503efda6a58e5f89fb"      # synthetic_set_t.json (V2-T, -20 dB, descriptive)


def sample_tag(residue: int) -> str:
    """Folder / file tag of a sample: the extension (residue 5) keeps its Amendment-4 names; every other fresh residue is r<residue>."""
    return "ext" if residue == EXT_RESIDUE else f"r{residue}"


def sha256_lf(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()

# ---- the pinned decoder -------------------------------------------------------------------------------------------------------------
DLL_PIN = "2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365"   # shim 20260058 (the NHARD-REP pin)
SHIM = 20260058
PROD_PARAMS = (10, 0.10, 40)   # k_min_score_pass2, osd_corr_threshold, nhard: production, as in the NHARD-REP arms
K_LDPC_ITERATIONS = 50         # ft8_shim.c:509 (gap-locate/gl_dll_pin.py's own constant, reused value)
OSD_DEPTH = 2                  # decode.c:666 ndeep
PAYLOAD_BITS = 77
V_STAR = (0, 32373)            # GAP-LOCATE ROW 0f: (ir, igrid4) the on-air RR73 tokens pack as
RR73_STD = CMP.RR73_STD
DELTA_S = 0.7                  # GAP-LOCATE Amendment 2 convention: t = WS_DT + delta; delta = median(OWS_DT - WS_DT) on THIS night's exact matches
                               # (measured 2026-10-06: median 0.7, mean 0.659 over 68,525 pairs; logging resolution 0.1 s)
assert V_STAR == (0, 32373) and RR73_STD == (0, 32403) and K_LDPC_ITERATIONS == 50 and OSD_DEPTH == 2


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_decoder(dll_path: str) -> LdpcDecodeLLRs:
    """The pinned DLL, SHA-256 and shim version verified at load; production decode parameters set (nhard 40)."""
    dec = LdpcDecodeLLRs(dll_path, verify=True, expected_sha256=DLL_PIN, expected_shim_version=SHIM, check_version=True)
    dec.dll.ft8_set_decode_params(PROD_PARAMS[0], PROD_PARAMS[1], PROD_PARAMS[2])
    return dec


def encode_tones(dec, text: str):
    """79 transmitted tones of a message via the vendored encoder (or None if it cannot pack it). Text stays with the caller."""
    import ctypes
    buf = (ctypes.c_uint8 * CE.N_SYM)()
    rc = dec.dll.ft8_encode_message(text.encode("ascii", errors="replace"), buf, CE.N_SYM)
    return list(buf) if rc == CE.N_SYM else None


def anchor_time(ws_dt_s: float) -> float:
    """GAP-LOCATE Amendment 2: the time offset handed to the extractors is WS_DT + delta, RAW (no +0.16)."""
    return float(ws_dt_s) + DELTA_S


def _decode_llr(dec, llr):
    """-> (success_inputs) dict from ft8_ldpc_decode_llrs for a raw LLR vector (list/array of 174)."""
    return dec.ldpc_decode_llrs([float(x) for x in llr], max_iters=K_LDPC_ITERATIONS, osd_depth=OSD_DEPTH)


def _arm_result(dec, llr, truth_bits, text, truth_payload):
    """One arm's numeric record from one LLR vector. truth_bits: 174-bit true codeword; text/payload used ONLY for the match, never returned."""
    res = _decode_llr(dec, llr)
    ok = False
    if res["rc"] == 0 and res["a91"] is not None and res["crc_ok"] == 1:
        recovered = a91_to_bits(res["a91"], PAYLOAD_BITS)
        ok = CMP.payload_match(truth_payload, recovered, text, V_STAR)
    hard = (np.asarray(llr, dtype=np.float64) > 0).astype(int)        # BP's sense: positive LLR means bit 1 (asserted on clean signals by V2's test)
    nbe = int(np.sum(hard != np.asarray(truth_bits)))
    return {"ok": int(ok), "path": int(res["path"]), "crc": int(res["crc_ok"]), "ldpc": int(res["ldpc_errors"]), "nbe": nbe}


def corrected_osd_arm(dec, llrs, text, truth_payload) -> dict:
    """AMENDMENT 2: BP as production, then OSD on the NEGATED LLRs, over one or several LLR vectors (G's nine lattice cells, or C3's single vector).
    Per vector: BP alone (osd_depth -1, 50 iterations); if BP converges that is production's own outcome (true payload -> bp_ok, otherwise nothing further);
    if BP fails, OSD on the negated vector (max_iters 1, depth 2). The negated call must reach the OSD gate: path 1 with CRC ok is an acceptance (true payload
    -> osd_ok, WRONG payload -> wrong); path 0 on the negated call is COUNTED (neg0) and treated as a failure. Text and bits never leave this function."""
    out = {"bp_ok": 0, "osd_ok": 0, "wrong": 0, "neg0": 0}
    for llr in llrs:
        r = dec.ldpc_decode_llrs([float(x) for x in llr], max_iters=K_LDPC_ITERATIONS, osd_depth=-1)
        if r["rc"] == 0 and r["path"] == 0:
            if r["crc_ok"] == 1 and CMP.payload_match(truth_payload, a91_to_bits(r["a91"], PAYLOAD_BITS), text, V_STAR):
                out["bp_ok"] = 1
            continue
        n = dec.ldpc_decode_llrs([-float(x) for x in llr], max_iters=NEG_MAX_ITERS, osd_depth=OSD_DEPTH)
        if n["rc"] != 0:
            continue
        if n["path"] == 0:
            out["neg0"] = 1
        elif n["path"] == 1 and n["crc_ok"] == 1 and n["a91"] is not None:
            if CMP.payload_match(truth_payload, a91_to_bits(n["a91"], PAYLOAD_BITS), text, V_STAR):
                out["osd_ok"] = 1
            else:
                out["wrong"] = 1
    out["ok"] = int(bool(out["bp_ok"] or out["osd_ok"]))
    return out


def coherent_llrs(pcm, anchor_f, anchor_t, est: dict) -> dict:
    """V1 / V3 LLRs at an estimate (offsets from the anchor)."""
    t = FS.anchor_dt_for_step(anchor_t, est["dt_step"])
    return CE.extract_variants(pcm, anchor_f, t, df_hz=est["est_df_hz"])


def evaluate_signal(dec, pcm: np.ndarray, anchor_f: float, anchor_t: float, text: str, true_df_hz=None, true_dt_s=None) -> dict:
    """All four arms for ONE signal. Returns numeric fields only. `text` never leaves this function.

    anchor_f / anchor_t: the anchor in the extractors' convention (real rows: WS freq, WS_DT + delta). true_*: synthetic truth, unused here."""
    out = {"fault": 0}
    truth_bits = dec.true_codeword(text)
    tones = encode_tones(dec, text)
    if truth_bits is None or tones is None:
        return {"fault": 1}
    truth_payload = truth_bits[:PAYLOAD_BITS]

    # ---- G: any of the 9 lattice cells around the anchor (leg_fk2.py's own loop) ----
    best = None
    won = None
    g_llrs = []
    for cell in lattice.snap_and_neighbours(anchor_f, anchor_t):
        rc, llr = dec.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
        if rc != 0:
            out["fault"] = 1
            continue
        g_llrs.append(llr)
        r = _arm_result(dec, llr, truth_bits, text, truth_payload)
        if best is None or (r["ok"], -r["nbe"]) > (best["ok"], -best["nbe"]):
            best = r
        if r["ok"] and won is None:
            won = r
    g = won if won is not None else best
    if g is None:
        return {"fault": 1}
    out.update({f"G_{k}": v for k, v in g.items()})
    out.update({f"GO_{k}": v for k, v in corrected_osd_arm(dec, g_llrs, text, truth_payload).items()})

    # ---- C1 / C3 at the DATA-FREE estimate; C3S at the ORACLE estimate ----
    est = FS.estimate(pcm, anchor_f, anchor_t)
    v = coherent_llrs(pcm, anchor_f, anchor_t, est)
    for arm, key in (("C1", "V1"), ("C3", "V3")):
        r = _arm_result(dec, v[key], truth_bits, text, truth_payload)
        out.update({f"{arm}_{k}": val for k, val in r.items()})
        out[f"{arm}_df"] = est["est_df_hz"]
        out[f"{arm}_dt"] = est["est_dt_s"]
    out["C3_edge"] = int(est["edge"])
    out.update({f"C3O_{k}": v for k, v in corrected_osd_arm(dec, [v["V3"]], text, truth_payload).items()})
    est_o = FS.estimate(pcm, anchor_f, anchor_t, FS.oracle_tones(tones))
    vo = coherent_llrs(pcm, anchor_f, anchor_t, est_o)
    r = _arm_result(dec, vo["V3"], truth_bits, text, truth_payload)
    out.update({f"C3S_{k}": val for k, val in r.items()})
    out["C3S_df"] = est_o["est_df_hz"]
    out["C3S_dt"] = est_o["est_dt_s"]
    out["C3S_edge"] = int(est_o["edge"])
    return out


ROW_FIELDS = (["fault"] + [f"{a}_{k}" for a in ARMS for k in ("ok", "path", "crc", "ldpc", "nbe")]
              + ["C1_df", "C1_dt", "C3_df", "C3_dt", "C3_edge", "C3S_df", "C3S_dt", "C3S_edge"]
              + [f"{a}_{k}" for a in OSD_ARMS for k in OSD_FIELDS])


class CpuTimer:
    """Per-row CPU time (process_time), for the timing pilot only; never part of the determinism comparison."""
    def __enter__(self):
        self.t0 = time.process_time()
        return self

    def __exit__(self, *a):
        self.dt = time.process_time() - self.t0
