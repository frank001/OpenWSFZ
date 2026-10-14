#!/usr/bin/env python
"""S1-SNR-REPLAY follow-up diagnostic (QA): for the S1 rows whose SNR differs between the two builds, list every decode of that cycle through each build's native
`ft8_decode_all` (a raw C-ABI call: first decode call only, NOT the live path; it shows what each DLL returns for the cycle, nothing more) with its frequency, SNR and
whether its TEXT EQUALS THE TRUTH TEXT of that S1 row. Text is compared inside `report`; only numbers and booleans are printed (HK-037).

  python s1_row_diag.py <audio key> <stamp> [<stamp> ...]
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.abspath(os.path.join(HERE, ".."))
for p in ("sub-feas", "nhard-rep", "coh-gain", "r2-coherent-llr-instrument"):
    sys.path.insert(0, os.path.join(RR, p))
sys.path.insert(0, HERE)
import s1_snr_replay as S  # noqa: E402
import cg_common as CG  # noqa: E402
import wavio  # noqa: E402
from ldpc_decode_ctypes import LdpcDecodeLLRs  # noqa: E402

DLLS = {"M": (os.path.join(S.BUILDS["M"]["dir"], "libft8.dll"), S.BUILDS["M"]["dll"], 20260058),
        "F": (r"D:\Projects\claude\_qa-scratch\osd-fix-review\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll", S.BUILDS["F"]["dll"], 20260060)}


def report(audio, stamp, results, truth_text, truth_freq):
    """-> list of {freq, snr, is_truth_text, near_truth_freq}; text never leaves."""
    out = []
    for r in results:
        msg = " ".join(str(r.get("message", r.get("text", ""))).split())
        f = float(r.get("freq_hz", r.get("freq", 0.0)))
        out.append({"freq": round(f, 1), "snr": r.get("snr"), "is_truth_text": msg == truth_text, "within_4hz_of_truth_freq": abs(f - truth_freq) <= 4.0})
    return out


def main(argv):
    if argv[1] == "--all":
        import json
        res = all_cells()
        json.dump(res, open(os.path.join(S.OUT_RES, "s1_text_aware.json"), "w"), indent=1, sort_keys=True)
        return 0
    audio, stamps = argv[1], argv[2:]
    truth = {}
    for r in csv.DictReader(open(os.path.join(S.RES_ROOT, S.AUDIO[audio][1], "truth.csv"), encoding="utf-8")):
        if r["scenario_id"] == "S1":
            truth[S.stamp_of(r["cycle_utc"])] = (" ".join(r["message_text"].split()), float(r["true_freq_hz"]), float(r["true_snr_db"]))
    for build, (dll, sha, shim) in DLLS.items():
        d = LdpcDecodeLLRs(dll, verify=True, expected_sha256=sha, expected_shim_version=shim, check_version=True)
        d.dll.ft8_set_decode_params(*CG.PROD_PARAMS)
        if build == "F":
            d.dll.ft8_set_osd_sign_fix(1)
        for st in stamps:
            pcm = wavio.load_cycle_pcm(os.path.join(S.wav_dir(audio), st + ".wav"))
            res = d.decode_all(pcm)
            t = truth[st]
            print(build, st, "true_snr", t[2], "decodes", report(audio, st, res or [], t[0], t[1]))
    return 0



def all_cells():
    """Text-aware pass over every S1 cycle of every audio set through both DLLs (raw first decode call; text compared inside; numbers only).
    -> {audio: {build: {stamp: {'truth_snr': int|None, 'n_decodes': int, 'n_wrong_text': int}}}}"""
    out = {}
    for audio in S.AUDIO:
        truth = {}
        for r in csv.DictReader(open(os.path.join(S.RES_ROOT, S.AUDIO[audio][1], "truth.csv"), encoding="utf-8")):
            if r["scenario_id"] == "S1":
                truth[S.stamp_of(r["cycle_utc"])] = (" ".join(r["message_text"].split()), float(r["true_freq_hz"]), float(r["true_snr_db"]))
        out[audio] = {}
        for build, (dll, sha, shim) in DLLS.items():
            d = LdpcDecodeLLRs(dll, verify=True, expected_sha256=sha, expected_shim_version=shim, check_version=True)
            d.dll.ft8_set_decode_params(*CG.PROD_PARAMS)
            if build == "F":
                d.dll.ft8_set_osd_sign_fix(1)
            rows = {}
            for st, (txt, f, n) in sorted(truth.items()):
                res = d.decode_all(wavio.load_cycle_pcm(os.path.join(S.wav_dir(audio), st + ".wav"))) or []
                rep = report(audio, st, res, txt, f)
                good = [x for x in rep if x["is_truth_text"]]
                rows[st] = {"truth_snr": good[0]["snr"] if good else None, "n_decodes": len(rep), "n_wrong_text": len(rep) - len(good), "true_snr": n}
            out[audio][build] = rows
            print(audio, build, "done", flush=True)
    return out

if __name__ == "__main__":
    sys.exit(main(sys.argv))
