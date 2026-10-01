#!/usr/bin/env python
"""Flag-OFF control (Architect ruling 2, 2026-09-29): does the SUB-FEAS build's native decode
path (flag OFF == the native path never sees the flag) produce the SAME OUTCOME FIELDS as the
DLLs it descends from, on identical audio?

Pre-registration: qa/rr-study/2026-09-29-<HHMM>-qa-flagoff-control-preregistration.md (committed
BEFORE this script was run; predicates below are its predicates, in code).

Three DLLs, extracted by `git show <commit>:<path>` (never rebuilt), each decoded in its OWN
process (fresh, process-global hash table):
    a  merge-base of the feature branch with main        (c3f42362)   shim 20260051
    b  decoding_improvement DLL from R&R 2026-09-23      (84cac119)   shim 20260054
    c  the build under test                              (0d6b1937)   shim 20260055

Processing is the daemon's own: silence guard, D-002 RMS normalisation to 0.20 (float32
arithmetic, as Ft8Decoder.NormalisePcm), ft8_set_ap_bits(empty), ft8_set_decode_params(10, 0.10,
40) (the explicit config values of the R&R runs), ft8_decode_all with a 340-slot result buffer.

NFR-021 / HK-037: message text is NEVER read out of the result buffer into anything that is
printed or written. Only integers (freq Hz, DT float32 bit pattern, SNR dB) are kept. The only
line-level read of ALL.TXT keeps the stamp, SNR and freq fields.

Usage (from qa/rr-study/sub-feas, with the rr-study venv python):
    python flagoff_control.py --out <gitignored dir>
"""
from __future__ import annotations

import argparse
import collections
import csv
import ctypes
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import wave

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DLL_REL = "src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll"
VER_REL = "src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt"
DLLS = {  # label -> (commit, expected shim version)
    "a": ("c3f42362", 20260051),
    "b": ("84cac119", 20260054),
    "c": ("0d6b1937", 20260055),
}
RAW = os.path.join(REPO, "artefacts", "rr_2026-09-29_subfeas_off_on")
OFF_RESULTS = os.path.join(RAW, "2026-09-29-62e8e74-OFF")
OFF_WAVS = os.path.join(RAW, "2026-09-29-62e8e74-OFF-captured-audio", "owsfz", "wav")
# Amendment 1 (pre-registration note, before any decode): S3 dropped -- 25 of its 30 cycles fall
# inside the daemon-side archive gap (~15:58Z-16:42Z, #193), found by this harness's own
# missing-WAV assertion before anything was decoded.
SCENARIOS = ("S1", "S1b", "S2", "S7", "S8")
SINGLE = ("S1", "S1b", "S2")                # single-signal scenarios (V0 and C2 use these)

PCM_LEN = 180_000
MAX_RESULTS = 340
TARGET_RMS = 0.20
SILENCE_RMS = 1e-6
K_MIN, OSD_THR, NHARD = 10, 0.10, 40
FREQ_MATCH_HZ = 3.0                          # truth-to-decode frequency match (single signal)

# ---- pre-registered predicates / thresholds (see the pre-registration note) -----------------
V0_MIN_FRACTION = 0.95                       # replay reproduces the archived (count, snr, freq)
FLAT_MIN_DECODES = 300                       # C1 is vacuous unless DLL a decoded at least this many
FLAT_MIN_BIASED_LEVELS = 3                   # ... and S1 has >= 3 SNR levels with bias >= 1.0 dB
FLAT_BIAS_DB = 1.0
LINEAGE_SUPPORT_GAP_DB = 0.30                # bias(a) - bias(b) >= this  => lineage supported
LINEAGE_SAME_TOL_DB = 0.15                   # |bias(c) - bias(a)| <= this ; also refute threshold


class Res(ctypes.Structure):
    _fields_ = [("freq", ctypes.c_int), ("dt", ctypes.c_float), ("snr", ctypes.c_int),
                ("msg", ctypes.c_char * 36)]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_show(commit, rel, dest):
    data = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=REPO, check=True,
                          capture_output=True).stdout
    with open(dest, "wb") as fh:
        fh.write(data)
    return data


def stamp_of(cycle_utc):
    """2026-09-29T15:37:30Z -> 260929_153730"""
    d, t = cycle_utc.rstrip("Z").split("T")
    return d[2:4] + d[5:7] + d[8:10] + "_" + t.replace(":", "")


def read_wav(path):
    with wave.open(path) as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == 12000, path
        assert w.getnframes() == PCM_LEN, (path, w.getnframes())
        raw = w.readframes(PCM_LEN)
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / np.float32(32768.0)


def rms32(pcm):
    s = float((pcm * pcm).astype(np.float32).sum(dtype=np.float64))
    return np.float32(math.sqrt(s / len(pcm)))


def normalise(pcm):
    r = rms32(pcm)
    if r < SILENCE_RMS:
        return pcm
    scale = np.float32(TARGET_RMS) / r
    return (pcm * scale).astype(np.float32)


# ---------------------------------------------------------------- worker (one DLL, one process)
def worker(dll_path, expected_version, stamps_json, variant, out_json):
    os.add_dll_directory(os.path.dirname(os.path.abspath(dll_path)))
    lib = ctypes.CDLL(dll_path)
    lib.ft8_lib_version_check.restype = ctypes.c_int
    ver = lib.ft8_lib_version_check()
    assert ver == expected_version, (ver, expected_version)
    lib.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]
    lib.ft8_set_decode_params.restype = None
    lib.ft8_set_ap_bits.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    lib.ft8_set_ap_bits.restype = None
    lib.ft8_decode_all.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int,
                                   ctypes.POINTER(Res), ctypes.c_int]
    lib.ft8_decode_all.restype = ctypes.c_int
    lib.ft8_set_decode_params(K_MIN, ctypes.c_float(OSD_THR), NHARD)

    stamps = json.load(open(stamps_json))
    out = {}
    av = 0
    for st in stamps:
        pcm = read_wav(os.path.join(OFF_WAVS, st + ".wav"))
        if rms32(pcm) < SILENCE_RMS:
            out[st] = {"skipped_silent": True, "d": []}
            continue
        if variant == "N":
            pcm = normalise(pcm)
        pcm = np.ascontiguousarray(pcm, dtype=np.float32)
        lib.ft8_set_ap_bits(b"", 0, b"", 0)
        buf = (Res * MAX_RESULTS)()
        n = lib.ft8_decode_all(pcm.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), PCM_LEN, buf, MAX_RESULTS)
        if n == -2:
            av += 1
            out[st] = {"av": True, "d": []}
            continue
        assert n >= 0, (st, n)
        d = []
        for i in range(n):
            r = buf[i]
            # outcome fields only: freq, DT as its float32 bit pattern, SNR.  msg is never read.
            d.append([int(r.freq), struct.unpack("<I", struct.pack("<f", r.dt))[0], int(r.snr)])
        d.sort()
        out[st] = {"d": d}
    json.dump({"shim": ver, "variant": variant, "av": av, "cycles": out}, open(out_json, "w"))


# ---------------------------------------------------------------- orchestrator
def load_truth():
    rows = []
    with open(os.path.join(OFF_RESULTS, "truth.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["scenario_id"] in SCENARIOS and r["cycle_utc"]:
                rows.append(r)
    return rows


def load_archived():
    """stamp -> sorted list of (snr, freq) from the daemon's ALL.TXT. Text is never kept."""
    arch = collections.defaultdict(list)
    with open(os.path.join(OFF_RESULTS, "owsfz-all.txt"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.split()
            if len(p) >= 8 and len(p[0]) == 13 and p[0][6] == "_":
                arch[p[0]].append((int(p[4]), int(p[6])))
    for k in arch:
        arch[k].sort()
    return arch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--worker", nargs=5, metavar=("DLL", "VER", "STAMPS", "VARIANT", "OUT"))
    a = ap.parse_args()
    if a.worker:
        d, v, s, var, o = a.worker
        return worker(d, int(v), s, var, o)

    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    # NFR-021: outputs must be git-ignored before anything is decoded.
    chk = subprocess.run(["git", "check-ignore", "-q", os.path.join(out, "x")], cwd=REPO)
    assert chk.returncode == 0, "output dir is not gitignored: " + out
    tracked = subprocess.run(["git", "ls-files", "--", out], cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert tracked == "", "output dir contains tracked files"

    # ---- pins (HK-022): actual SHA per extracted DLL, and whether the SHA is quoted in that
    #      commit's own libft8.version.txt (a self-reference, NOT an independent pin) ----------
    pins = {}
    dll_paths = {}
    for lab, (commit, ver) in DLLS.items():
        p = os.path.join(out, f"libft8_{lab}.dll")
        git_show(commit, DLL_REL, p)
        sha = sha256(p)
        vtxt = subprocess.run(["git", "show", f"{commit}:{VER_REL}"], cwd=REPO, capture_output=True, text=True).stdout
        pins[lab] = {"commit": commit, "shim": ver, "sha256": sha, "sha_quoted_in_version_txt": sha in vtxt}
        dll_paths[lab] = p

    truth = load_truth()
    stamps = sorted({stamp_of(r["cycle_utc"]) for r in truth})
    missing = [s for s in stamps if not os.path.exists(os.path.join(OFF_WAVS, s + ".wav"))]
    assert not missing, ("missing WAVs", len(missing))
    stamps_json = os.path.join(out, "stamps.json")
    json.dump(stamps, open(stamps_json, "w"))
    stamps_sha = sha256(stamps_json)

    # ---- run each DLL in its own process ---------------------------------------------------
    runs = {}
    for lab, variant in (("a", "N"), ("b", "N"), ("c", "N"), ("c", "U")):
        oj = os.path.join(out, f"decode_{lab}_{variant}.json")
        subprocess.run([sys.executable, os.path.abspath(__file__), "--out", out, "--worker",
                        dll_paths[lab], str(DLLS[lab][1]), stamps_json, variant, oj], check=True)
        runs[(lab, variant)] = json.load(open(oj))

    res = {"pins": pins, "stamps_sha256": stamps_sha, "n_cycles": len(stamps),
           "scenarios": list(SCENARIOS), "filter": "none (all listed scenarios' stamps)"}

    # ---- V0: instrument validity (must pass or STOP) --------------------------------------
    arch = load_archived()
    single_stamps = sorted({stamp_of(r["cycle_utc"]) for r in truth if r["scenario_id"] in SINGLE})

    def v0(variant):
        ok = 0
        for st in single_stamps:
            replay = sorted((x[2], x[0]) for x in runs[("c", variant)]["cycles"][st]["d"])
            if replay == arch.get(st, []):
                ok += 1
        return ok, len(single_stamps)

    vn, vn_tot = v0("N")
    vu, vu_tot = v0("U")
    res["V0"] = {"normalised_match": vn, "unnormalised_match": vu, "cycles": vn_tot,
                 "threshold": V0_MIN_FRACTION}
    variant_used = None
    if vn / vn_tot >= V0_MIN_FRACTION:
        variant_used = "N"
    elif vu / vu_tot >= V0_MIN_FRACTION:
        variant_used = "U"
    res["V0"]["variant_used"] = variant_used
    if variant_used is None:
        res["verdict"] = "STOP: V0 failed for both variants; the replay does not reproduce the daemon"
        json.dump(res, open(os.path.join(out, "summary.json"), "w"), indent=1)
        print(json.dumps(res, indent=1))
        return 2
    if variant_used == "U":
        # decodes for a and b were run normalised only; the pre-registration forbids improvising
        res["verdict"] = "STOP: V0 passed only for the un-normalised variant; a/b were not run that way"
        json.dump(res, open(os.path.join(out, "summary.json"), "w"), indent=1)
        print(json.dumps(res, indent=1))
        return 2

    # ---- C1: (c) == (a) on outcome fields, every cycle -------------------------------------
    A, B, C = (runs[(k, "N")]["cycles"] for k in ("a", "b", "c"))
    diff_ca = [st for st in stamps if A[st]["d"] != C[st]["d"] or A[st].get("av") != C[st].get("av")]
    diff_ba = [st for st in stamps if A[st]["d"] != B[st]["d"]]
    diff_bc = [st for st in stamps if B[st]["d"] != C[st]["d"]]
    tot_a = sum(len(A[st]["d"]) for st in stamps)
    res["C1"] = {"cycles_compared": len(stamps), "decodes_in_a": tot_a,
                 "c_vs_a_cycles_differing": len(diff_ca), "c_vs_a_differing_stamps": diff_ca[:50],
                 "av_a": runs[("a", "N")]["av"], "av_b": runs[("b", "N")]["av"], "av_c": runs[("c", "N")]["av"]}

    # ---- C2: S1 SNR bias per DLL and per level (truth used only for freq/snr, in this function)
    def bias(cyc, scen):
        per = collections.defaultdict(list)
        for r in truth:
            if r["scenario_id"] != scen:
                continue
            st = stamp_of(r["cycle_utc"])
            tf, ts = float(r["true_freq_hz"]), float(r["true_snr_db"])
            best = None
            for f, _dt, snr in cyc[st]["d"]:
                if abs(f - tf) <= FREQ_MATCH_HZ and (best is None or abs(f - tf) < abs(best[0] - tf)):
                    best = (f, snr)
            if best is not None:
                per[ts].append(best[1] - ts)
        allv = [x for v in per.values() for x in v]
        return (sum(allv) / len(allv) if allv else None, len(allv),
                {k: round(sum(v) / len(v), 3) for k, v in sorted(per.items())})

    c2 = {}
    for lab, cyc in (("a", A), ("b", B), ("c", C)):
        m, n, lv = bias(cyc, "S1")
        c2[lab] = {"S1_bias_db": None if m is None else round(m, 3), "matched_cycles": n, "per_level": lv}
    res["C2"] = c2
    res["FLAT_GUARD"] = {
        "decodes_a": tot_a, "min_decodes": FLAT_MIN_DECODES,
        "levels_with_bias_ge": sum(1 for v in c2["c"]["per_level"].values() if v >= FLAT_BIAS_DB),
        "min_levels": FLAT_MIN_BIASED_LEVELS, "bias_db": FLAT_BIAS_DB}
    flat_ok = (tot_a >= FLAT_MIN_DECODES and res["FLAT_GUARD"]["levels_with_bias_ge"] >= FLAT_MIN_BIASED_LEVELS)
    res["FLAT_GUARD"]["passes"] = flat_ok

    ba, bb, bc = (c2[k]["S1_bias_db"] for k in ("a", "b", "c"))
    if None in (ba, bb, bc):
        lineage = "INCONCLUSIVE (a bias could not be computed)"
    elif ba - bb >= LINEAGE_SUPPORT_GAP_DB and abs(bc - ba) <= LINEAGE_SAME_TOL_DB:
        lineage = "SUPPORTED (a and c share the higher bias; b lower)"
    elif abs(bb - ba) < LINEAGE_SAME_TOL_DB:
        lineage = "REFUTED as lineage (b and a agree)"
    else:
        lineage = "INCONCLUSIVE"
    res["C2"]["lineage_reading"] = lineage

    res["C3_descriptive"] = {"b_vs_a_cycles_differing": len(diff_ba), "b_vs_c_cycles_differing": len(diff_bc)}

    if len(diff_ca) > 0:
        res["verdict"] = "C1 FAIL: flag-OFF build differs from its merge-base on outcome fields (defect; blocks merge; Developer)"
    elif not flat_ok:
        res["verdict"] = "C1 PASS but VACUOUS by the flat guard: cannot clear S1 (HK-026)"
    else:
        res["verdict"] = "C1 PASS: c == a on outcome fields for every cycle; claim holds for this audio set"
    json.dump(res, open(os.path.join(out, "summary.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
