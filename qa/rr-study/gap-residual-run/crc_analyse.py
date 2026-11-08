#!/usr/bin/env python3
"""COH-RES-CAND (#272) acceptance analysis (spec 2026-11-08-1614 section 3 + Amendments 1 (A1.1 to A1.4), 2 and 3 (section 11, 14f4e28d)). Adapted from tn_analyse.py at d50a98fe
(the L1' third night): the SAME scoring (L.match against the night's WSJT-X lines, the frozen U' instrument, the cycle bootstrap), arm B (--cohrescand 1) against arm A (--cohrescand 0).
Night 20260930_1930, the FIRST 400 of the 800-cycle selection 2575e115; classes frozen from all 800 Original cycles (u3_800/orig800_classes.json, SHA 8046a4be...), reused as they are.

    python crc_analyse.py v1                    V1-3N: arm A (PC) against the sol OFF-arm records for the same first 400 cycles (read BEFORE arm B starts, A1.4)
    python crc_analyse.py boff                  B-OFF: bo_new (setting OFF) against bo_main (main fe1454c1), 40 cycles, every published field
    python crc_analyse.py main <classes_sha256> B-NAT, B-WIRE, B-DUP, N-GO/N-STOP, U-OK/U-FAIL, B-AB, the verdict, and the descriptive lines
    env CRC_DRY=1 : the 3-cycle plumbing set (raw_dry / scratch_dry, dry_off / dry_on), smoke test only, never a result.

ROWS (mechanical; the predicates below are the code):
  B-NAT   git diff --stat fe1454c1 b0d01f4f -- native src/OpenWSFZ.Ft8/Native is empty AND the DLL SHA-256 of every arm's start/end = the pin 1ba8dc3d...
  B-OFF   bo_new publishes rows identical to bo_main's in 40 of 40 cycles (nc dump: kind, freq, dt, snr, path, text; the replay's matched flag included).
  B-WIRE  (A1.1 + Amendment 3) denominator = arm-B cycles whose fallback line shows audio=both(residual2|residual3) (a residual-level cycle logged fallback-orig stays IN it and counts
          against (i)). (i) resCand=residual-* in >= 95 % of them; (ii) resEligible != origEligible in >= 1 of them. Uses resEligible/origEligible only, never eligible= (N-2).
  B-DUP   no text appears twice in one cycle of arm B's published rows.
  N-GO    CI_lo(NET_B-A) > 0 pp.      N-STOP  CI_hi(NET_B-A) <= 0 pp.     (bar 0 pp: the Captain's choice for this arm)
  U-OK    CI_hi(dU'_ta) <= 0.021.     U-FAIL  CI_lo(dU'_ta) > 0.021.      dU'_ta = new-text, NOT corroborated, batch-4 (fallback) outputs of B, text absent from A's rows of that cycle, classified
          tested_absent by the frozen instrument, per cycle where WSJT-X decoded something (as tn_analyse.py with batch 4 in place of batch 5).
  B-AB    cycles whose fallback line has abandoned > 0 (the line carries ONE figure for both runs, so the per-run split of A1.2 cannot be read from it): count(B) <= count(A).
  V1-3N   A's published rows equal the sol OFF arm's in 400 of 400 cycles (kind, freq, dt, snr, text); any difference listed, and checked for untestable_class.
  VERDICT ACCEPT iff B-NAT, B-OFF, B-WIRE, B-DUP, N-GO, U-OK, B-AB all pass; FAIL iff N-STOP or U-FAIL; OPEN otherwise (goes to the Captain; no second night automatically).
Bootstrap: B = 2000 resamples of the cycles, seed 20261108, as tn_analyse.py (paired: the same cycle indices for both arms).
HK-037: counts only leave this script; message text lives in memory."""
import collections
import csv
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C      # noqa: E402
import gg_lib as L         # noqa: E402

DRY = os.environ.get("CRC_DRY") == "1"
S = "D:/Projects/claude/_qa-scratch/coh-res-cand"
LS = "D:/Projects/claude/_qa-scratch/late-sub"
RAW = S + ("/raw_dry" if DRY else "/raw")
SCR = S + ("/scratch_dry" if DRY else "/scratch")
ARM_A, ARM_B = ("dry_off", "dry_on") if DRY else ("A", "B")
RUN = "20260930_1930"
NIGHT = "D:/Projects/claude/OpenWSFZ/artefacts/" + RUN + "_endurance_run-gathered"
SELF = (LS + "/selection_3n_dry.json") if DRY else (LS + "/selection_3n.json")
SEL_SHA = "2575e115378c71c068cd250d26dd002a17d7d365366cd00e6aaa3a99d2329c4f"
CLASSES = LS + "/u3_800/orig800_classes.json"
DLL = LS + "/bin_dev/libft8.dll"            # only the U' re-encoder (tones), as in tn_analyse.py
WAV_ROOT = "D:/Projects/claude/OpenWSFZ/artefacts"
PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
CF = os.path.join(HERE, "..", "coh-fallback")
N_CYCLES = 3 if DRY else 400
BAR_NET_PP, U_BAR, B, SEED = 0.0, 0.021, 2000, 20261108
assert (BAR_NET_PP, U_BAR, B, SEED, N_CYCLES) == (0.0, 0.021, 2000, 20261108, 3 if DRY else 400)
WIRE_SHARE = 0.95
HASHED = re.compile(r"<[^>]*>")
FB = re.compile(r"Coherent fallback: .*?abandoned=(\d+), .*?audio=both\((\w+)\)(?:.*?resCand=(\S+), resEligible=(-?\d+), origEligible=(-?\d+))?")
KIND_FALLBACK = 4


def load_nc(path):
    d = collections.defaultdict(list)
    for r in C.load_tsv(path):
        if len(r) >= 11:
            d[r[0]].append(dict(kind=int(r[1]), matched=int(r[2]), f=int(r[3]), dt=float(r[4]), snr=int(r[5]), path=r[9], text="\t".join(r[10:])))
    for s in d:
        d[s].sort(key=lambda x: x["kind"])
    return d


def rows(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def stamps_of():
    assert DRY or sha(SELF) == SEL_SHA, "selection differs from the frozen one"
    sel = json.load(open(SELF))["runs"][RUN]["FULL"]
    st = [e if isinstance(e, str) else e[0] for e in sel][:N_CYCLES]
    assert len(st) == N_CYCLES
    return st


def instrument(classes_sha):
    assert classes_sha is None or sha(CLASSES) == classes_sha, "classes differ from the frozen hash"
    spec = importlib.util.spec_from_file_location("cf_uprime_mod", CF + "/cf_uprime.py")
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)
    F, _ = U.load_instrument()
    enc = F.encoder(DLL)
    frozen = json.load(open(CLASSES))
    c_off = float(frozen["start_minus_dt_median_s"])
    testable = set(frozen["testable_classes"])
    pcms = {}

    def pcm_of(st):
        if st not in pcms:
            pcms[st] = F.wavio.load_cycle_pcm(os.path.join(NIGHT, "owsfz", "wav", st + ".wav"))
        return pcms[st]

    def status(stamp, text, freq, dt):
        tones = enc(text)
        if any(x.startswith("<") for x in text.split()) or tones is None:
            return "hashed_or_unencodable"
        if F.shape_class(text) not in testable:
            return "untestable_class"
        sh, outs = F.locate_and_score({}, pcm_of(stamp), freq, dt + c_off, F.DT_HALF_WINDOW_S, [tones[i] for i in F.SYNC_IDX], [tones])
        return "tested_present" if outs[0] >= U.T_FROZEN else "tested_absent"
    return status


def key(x):
    return (x["kind"], x["f"], round(x["dt"], 2), x["snr"], x["path"], x["text"], x["matched"])


def cmd_boff():
    a, b = load_nc(f"{SCR}/bo_main/nc_dump.tsv"), load_nc(f"{SCR}/bo_new/nc_dump.tsv")
    st = sorted(set(a) | set(b))
    same = sum(1 for s in st if [key(x) for x in a.get(s, [])] == [key(x) for x in b.get(s, [])])
    res = {"cycles_compared": len(st), "identical_cycles": same, "B-OFF": {"PASS": len(st) == 40 and same == 40}}
    print(json.dumps(res, indent=1))
    return res


def cmd_v1(classes_sha):
    stamps = stamps_of()
    a = load_nc(f"{SCR}/{ARM_A}/nc_dump.tsv")
    sol = load_nc(f"{LS}/sol3n/scratch/off/nc_dump.tsv")
    k4 = lambda x: (x["kind"], x["f"], round(x["dt"], 2), x["snr"], x["text"])
    diff = [s for s in stamps if [k4(x) for x in a.get(s, [])] != [k4(x) for x in sol.get(s, [])]]
    out = {"cycles": len(stamps), "identical_cycles": len(stamps) - len(diff), "differing_cycles": diff, "V1-3N": {"PASS": not diff}}
    if diff:
        status = instrument(classes_sha)
        unt = 0
        for s in diff:
            ks = collections.Counter(k4(x) for x in sol.get(s, []))
            ka = collections.Counter(k4(x) for x in a.get(s, []))
            for t, n in ((ka - ks) + (ks - ka)).items():
                if status(s, t[4], t[1], t[2]) == "untestable_class":
                    unt += n
        out["differing_rows_in_untestable_class"] = unt
        out["reaches_untestable_class"] = unt > 0
    print(json.dumps(out, indent=1))
    return out


def cmd_main(classes_sha):
    stamps = stamps_of()
    res = {"night": RUN, "cycles": len(stamps), "dry": DRY}
    # ---- B-NAT
    tree = S + "/tree"
    g = subprocess.run(["git", "-C", tree, "diff", "--stat", "fe1454c1", "b0d01f4f", "--", "native", "src/OpenWSFZ.Ft8/Native"], capture_output=True, text=True)
    dll_ok = all(sha(f"{S}/{b}/libft8.dll") == PIN for b in ("bin_new", "bin_main"))
    res["B-NAT"] = {"git_diff_native_empty": g.returncode == 0 and g.stdout.strip() == "", "dll_pin_ok": dll_ok, "PASS": g.returncode == 0 and g.stdout.strip() == "" and dll_ok}
    # ---- B-WIRE, B-AB from the arms' logs / coh.csv
    fb = {}
    for arm in (ARM_A, ARM_B):
        lines = [FB.search(x) for x in open(f"{RAW}/{arm}/log.log", encoding="utf-8", errors="replace") if "Coherent fallback:" in x]
        fb[arm] = [m.groups() for m in lines if m]
    wire = [g_ for g_ in fb[ARM_B] if g_[1] in ("residual2", "residual3")]
    n_res = sum(1 for g_ in wire if (g_[2] or "").startswith("residual-"))
    diff_elig = sum(1 for g_ in wire if g_[2] and g_[3] != g_[4])
    share = (n_res / len(wire)) if wire else 0.0
    res["B-WIRE"] = {"fallback_lines_B": len(fb[ARM_B]), "denominator_residual_level_cycles": len(wire), "resCand_residual_share": share,
                     "cycles_resEligible_ne_origEligible": diff_elig, "i": share >= WIRE_SHARE, "ii": diff_elig >= 1, "PASS": share >= WIRE_SHARE and diff_elig >= 1,
                     "by_resCand": dict(collections.Counter(g_[2] for g_ in fb[ARM_B]))}
    ab = {}
    for arm in (ARM_A, ARM_B):
        c = rows(f"{RAW}/{arm}/coh.csv")
        ar = [l.rstrip(chr(10)).split(",") for l in open(f"{RAW}/{arm}/abandon.csv") if l[:1].isdigit()]
        th = rows(f"{RAW}/{arm}/third.csv")
        ab[arm] = {"fallback_abandoned_cycles": sum(1 for r in c if int(r["abandoned"]) > 0), "residual_abandoned_cycles": sum(1 for r in ar if int(r[2]) > 0),
                   "third_abandoned_or_failed_cycles": sum(1 for r in th if r["outcome"] in ("abandoned", "failed")),
                   "fallback_abandoned_candidates_total": sum(int(r["abandoned"]) for r in c),
                   "fb_wall_ms_median_max": [float(np.median([int(r["fb_wall_ms"]) for r in c])), max(int(r["fb_wall_ms"]) for r in c)],
                   "fb_end_ms_max": max(int(r["fb_start_ms"]) + int(r["fb_wall_ms"]) for r in c if int(r["fb_wall_ms"]) >= 0)}
    res["B-AB"] = {"A": ab[ARM_A], "B": ab[ARM_B], "PASS": ab[ARM_B]["fallback_abandoned_cycles"] <= ab[ARM_A]["fallback_abandoned_cycles"],
                   "note": "the fallback line carries one abandoned figure for both runs; the per-run split of A1.2 is not in the log"}
    # ---- scoring
    C.ALLTXT = NIGHT + "/wsjt-x/ALL.TXT"
    ref = C.load_ref(set(stamps))
    n_ref = sum(len(ref.get(s, [])) for s in stamps)
    refc = np.array([float(len(ref.get(s, []))) for s in stamps])
    w = np.array([1.0 if ref.get(s) else 0.0 for s in stamps])
    res["n_ref"], res["cycles_with_wsjtx"] = n_ref, int(w.sum())
    a, b = load_nc(f"{SCR}/{ARM_A}/nc_dump.tsv"), load_nc(f"{SCR}/{ARM_B}/nc_dump.tsv")
    status = instrument(classes_sha)
    cols = {k: np.zeros(len(stamps)) for k in ("net", "ta", "hu", "pres", "unt", "out", "conf", "hashed")}
    corr_a = corr_b = 0
    dup = 0
    by_cand = collections.Counter()
    bonly_rows = aonly_rows = 0
    line_of_cycle = {}
    for ci, s in enumerate(stamps):
        r = ref.get(s, [])
        a_rows, b_rows = a.get(s, []), b.get(s, [])
        a_uw, a_uo = L.match(r, [(x["kind"], x["f"], x["text"]) for x in a_rows])
        b_uw, b_uo = L.match(r, [(x["kind"], x["f"], x["text"]) for x in b_rows])
        corr_a += len(a_uw)
        corr_b += len(b_uw)
        cols["net"][ci] = len(b_uw) - len(a_uw)
        texts_b = [x["text"] for x in b_rows]
        dup += len(texts_b) - len(set(texts_b))
        a_texts, b_texts = {x["text"] for x in a_rows}, set(texts_b)
        bonly_rows += len(b_texts - a_texts)
        aonly_rows += len(a_texts - b_texts)
        for i, x in enumerate(b_rows):
            if x["kind"] != KIND_FALLBACK or x["text"] in a_texts:
                continue
            cols["out"][ci] += 1
            cols["hashed"][ci] += bool(HASHED.search(x["text"]))
            if i in b_uo:
                cols["conf"][ci] += 1
            else:
                sx = status(s, x["text"], x["f"], x["dt"])
                cols[{"tested_absent": "ta", "hashed_or_unencodable": "hu", "tested_present": "pres", "untestable_class": "unt"}[sx]][ci] += 1
    res["B-DUP"] = {"duplicate_text_instances_in_B": dup, "PASS": dup == 0}
    res["A"] = {"corroborated": corr_a, "pct": 100.0 * corr_a / n_ref}
    res["B"] = {"corroborated": corr_b, "pct": 100.0 * corr_b / n_ref}
    keep = np.arange(len(stamps))
    rng = np.random.default_rng(SEED)
    idx = keep[rng.integers(0, len(keep), size=(B, len(keep)))]
    den = refc[idx].sum(axis=1)
    net = 100.0 * cols["net"][idx].sum(axis=1) / den
    wcnt = w[idx].sum(axis=1)
    pc = lambda a_: [float(np.percentile(a_, 2.5)), float(np.percentile(a_, 97.5))]
    ta = cols["ta"][idx].sum(axis=1) / wcnt
    r = {"NET_pp": 100.0 * cols["net"].sum() / refc.sum(), "NET_CI": pc(net), "dU_ta": cols["ta"].sum() / w.sum(), "dU_ta_CI": pc(ta),
         "dU_hu": cols["hu"].sum() / w.sum(), "dU_present": cols["pres"].sum() / w.sum(), "dU_untestable_class_outputs": int(cols["unt"].sum()),
         "new_text_batch4_outputs": int(cols["out"].sum()), "new_text_batch4_corroborated": int(cols["conf"].sum())}
    rows_ = {"N-GO": r["NET_CI"][0] > BAR_NET_PP, "N-STOP": r["NET_CI"][1] <= BAR_NET_PP, "U-OK": r["dU_ta_CI"][1] <= U_BAR, "U-FAIL": r["dU_ta_CI"][0] > U_BAR}
    res["result"], res["rows"] = r, rows_
    res["descriptive"] = {"B_minus_A_row_texts": {"B_only_texts": bonly_rows, "A_only_texts": aonly_rows},
                          "gained_corroborated_share_of_GAP_RESIDUAL_153_ceiling_INDICATIVE_ONLY_other_night": (corr_b - corr_a) / 153.0,
                          "note": "the B-A row count split by resCand: see B-WIRE.by_resCand (per fallback line); wall time per arm in B-AB (fbWallMs, both runs together)"}
    allpass = res["B-NAT"]["PASS"] and res["B-WIRE"]["PASS"] and res["B-DUP"]["PASS"] and res["B-AB"]["PASS"] and rows_["N-GO"] and rows_["U-OK"]
    res["verdict"] = ("ACCEPT (B-OFF and V1-3N are read separately and must also pass)" if allpass else "FAIL" if (rows_["N-STOP"] or rows_["U-FAIL"]) else "OPEN")
    print(json.dumps(res, indent=1, default=float))
    if not DRY:
        json.dump(res, open(S + "/crc_result.json", "w"), indent=1, default=float)
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "boff":
        cmd_boff()
    elif cmd == "v1":
        cmd_v1(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "main":
        cmd_main(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        sys.exit("usage: crc_analyse.py v1 [classes_sha] | boff | main [classes_sha]")
