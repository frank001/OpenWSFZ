"""G2A-REMEASURE-A ROW 0 -- preconditions, spec Sec.3, amendment unaffected.
Evaluated in strict order; 0a/0b/0c/0d are VOID-on-fail, 0e is VOID-on-fail
(audio integrity). run_all.py drives this against the decode dumps already
produced by decode_corpus.py (three background runs: L1, L2_run1, L2_run2).
"""
from __future__ import annotations

import hashlib
import os

import common_g2a as G

# Enumerated version delta between L1 (shim 20260033, empirically confirmed
# via ft8_lib_version_check() against D:\...\OpenWSFZ-8080-capture\libft8.dll,
# mtime 2026-08-08, matches the board's own pre-G2a main pin f2f30c89...) and
# L2 (shim 20260046, native/ft8_lib_build/libft8.dll, current working tree).
# No on-disk candidate reports shim 20260038 (G2(a)'s OWN build, c559a049...)
# -- every DLL this session could locate is either <=20260029 (older than L1)
# or exactly L1 (20260033) or exactly L2 (20260046). Per spec Sec.2.1 this is
# a DISCLOSED CONFOUND: L2 differs from L1 in far more than G2(a) alone.
VERSION_DELTA_COMMITS = [
    "9500e03 g2(a): HASH_TABLE_SIZE 256 -> 4096 (shim 20260038) -- THE measured treatment",
    "3bc2b9d feat(native): r0-reproducible-native-build -- vendor ft8_lib, rebuild all 11 objects from source",
    "0b39805 fix(native): silence dormant monitor.c LOG_INFO stderr spam (R0 review follow-up)",
    "6fd9410 chore(native): rebuild Linux binary to shim 20260039; repoint build_linux.sh at the vendored tree",
    "af2f466 feat(ft8): implement r1-sync-refiner-instrument-validation (AC-3 unresolved, escalated)",
    "aa434cb feat(ft8): implement r1b-sync-refiner-instrument-correction",
    "4c73130 docs(ft8): A1 -- correct the withdrawn AC-3 mechanism comment in sync_refiner.c",
    "56ef0c0 feat(ft8): implement n1-extract-llrs-at-position, shim 20260042",
    "5d3cac5 feat(r2): Route B2 Phase 1 -- ft8_coherent_llr_at diagnostic export",
    "7ed8b0c feat(r2): Phase B build -- origin fix (B1), fusion normalisation (B2), ft8_ldpc_decode_llrs export (B4)",
    "c3a9ea8 fix(ft8): negative time_offset SNR collapse (shim 20260046) -- THE current build",
]
CONFOUND_NOTE = (
    "L1/L2 differ in far more than G2(a): notably R1/R1b (sync-refiner instrument, "
    "separately measured on P-LIVE Stage2 as ROW 3 HARM, d_ber=-3.45pp) and R2 Phase B "
    "(waterfall-origin fix + fusion normalisation). Per spec Sec.2.1 this DOWNGRADES "
    "Part A and Part B from a clean causal isolation of G2(a) to a descriptive "
    "'pre-08-13 vs current main' comparison. Stated in full, not papered over."
)


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def row0a(log) -> dict:
    l1_ok = os.path.exists(G.L1_DLL_PATH) and sha256_of(G.L1_DLL_PATH) == G.L1_SHA256
    l2_ok = os.path.exists(G.L2_DLL_PATH) and sha256_of(G.L2_DLL_PATH) == G.L2_SHA256
    log("ROW 0a: L1 dll=%s sha256_match=%s shim=%d" % (G.L1_DLL_PATH, l1_ok, G.L1_SHIM_VERSION))
    log("ROW 0a: L2 dll=%s sha256_match=%s shim=%d" % (G.L2_DLL_PATH, l2_ok, G.L2_SHIM_VERSION))
    log("ROW 0a: version delta enumerated (%d commits), CONFOUND DISCLOSED -- see CONFOUND_NOTE"
        % len(VERSION_DELTA_COMMITS))
    for c in VERSION_DELTA_COMMITS:
        log("ROW 0a:   " + c)
    log("ROW 0a: " + CONFOUND_NOTE)
    ok = l1_ok and l2_ok
    log("ROW 0a: %s" % ("PASS (both DLLs located and hashed; delta enumerated; "
                         "confound disclosed, downgrades A/B to descriptive per spec Sec.2.1)"
                         if ok else "VOID -- a pinned DLL could not be located/hashed"))
    return {"pass": ok, "l1_sha_ok": l1_ok, "l2_sha_ok": l2_ok,
            "version_delta_commits": VERSION_DELTA_COMMITS, "confound_note": CONFOUND_NOTE,
            "confound_disclosed": True}


def row0b(l1_dump: dict, l2_dump: dict, log) -> dict:
    r1 = l1_dump.get("final_hash_table_reject_count")
    r2 = l2_dump.get("final_hash_table_reject_count")
    ok = (r1 is not None) and (r2 is not None) and (r1 > r2)
    log("ROW 0b: hash_table_reject_count L1=%s L2=%s -> %s"
        % (r1, r2, "PASS (L1 > L2, expected direction)" if ok
           else "VOID -- reject count did not move in the expected direction"))
    return {"pass": ok, "reject_l1": r1, "reject_l2": r2}


def row0c(l1_rows: list[dict], l0_rows: list[dict], log) -> dict:
    """Replay fidelity: L1's decode set reproduces L0's, matched on (ts, message_norm)."""
    l1_keys = {(r["ts"], r["message_norm"]) for r in l1_rows}
    l0_keys = {(r["ts"], r["message_norm"]) for r in l0_rows}
    if not l0_keys:
        log("ROW 0c: L0 has zero rows -- VOID")
        return {"pass": False, "fidelity": 0.0}
    matched = l0_keys & l1_keys
    fidelity = len(matched) / len(l0_keys)
    ok = fidelity >= 0.95
    log("ROW 0c: L0 keys=%d L1 keys=%d matched=%d fidelity=%.4f -> %s"
        % (len(l0_keys), len(l1_keys), len(matched), fidelity,
           "PASS" if ok else "VOID -- offline replay does not reproduce live capture"))
    return {"pass": ok, "fidelity": fidelity, "n_l0": len(l0_keys), "n_l1": len(l1_keys),
            "n_matched": len(matched)}


def row0d(l2_run1_dump: dict, l2_run2_dump: dict, log) -> dict:
    """Determinism: two independent full L2 decode runs (separate processes,
    fresh DLL load each), mechanically diffed on every field except wall-clock
    timing. If the records disagree in ANY way, this VOIDs the whole arm."""
    fields_to_compare = ["dll_sha256", "shim_version", "n_wavs", "n_decodes",
                          "n_native_av", "native_av_files",
                          "final_hash_table_reject_count", "records"]
    diffs = []
    for f in fields_to_compare:
        a = l2_run1_dump.get(f)
        b = l2_run2_dump.get(f)
        if a != b:
            diffs.append(f)
    ok = len(diffs) == 0
    log("ROW 0d: two independent full L2 runs, mechanically diffed on %s -> %s"
        % (fields_to_compare, "byte-identical (PASS)" if ok
           else "VOID -- fields differ: %s" % diffs))
    return {"pass": ok, "diffs": diffs}


def row0e(log) -> dict:
    n = len([f for f in os.listdir(G.OURS_WAV_DIR) if f.endswith(".wav")])
    ok = n == G.EXPECTED_WAV_COUNT
    log("ROW 0e: WAV count in %s = %d, expected %d (per qa/ARTEFACT_INVENTORY.md) -> %s"
        % (G.OURS_WAV_DIR, n, G.EXPECTED_WAV_COUNT, "PASS" if ok else "VOID"))
    return {"pass": ok, "n_wavs": n, "expected": G.EXPECTED_WAV_COUNT}
