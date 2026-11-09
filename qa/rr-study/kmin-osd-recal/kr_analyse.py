#!/usr/bin/env python3
"""KMIN-OSD-RECAL analysis (spec arch/kmin-osd-recal sections 1-2 + Amendments 1 and 2). Adapted from crc_analyse.py (COH-RES-CAND) and tn_analyse.py d50a98fe: the SAME scoring (L.match against the night's
WSJT-X lines, the frozen U' instrument, the cycle bootstrap), arm B (kMinScorePass2 5, osdCorrThreshold 0.05) against arm A (10, 0.10). Night 20260930_1930, the FIRST 400 of the 800-cycle selection 2575e115;
classes frozen from all 800 Original cycles (u3_800/orig800_classes.json, SHA 8046a4be...), reused as they are.

    python kr_analyse.py main <classes_sha256>

ROWS (mechanical; the predicates below are the code):
  V-NAT    the build tree is at ef2fc84b with an empty native diff AND the DLL SHA-256 = the pin 1ba8dc3d... (now, and no 'dll pin mismatch' in either arm's status file).
  V-SET    each arm's "# readback start" and "# readback end" lines show exactly its table values: kMinScorePass2, osdCorrThreshold, nhard 24, osdSignFixRead 1, Deep, cohfb/cohms True, cohaudio Both,
           ungated True, lateround True, threadsResolved 8.
  V-WIRE   (A1.2 + A2.1) (i) V-SET; (ii) the native check on STORED RESIDUAL (R2) buffers, run and recorded BEFORE the freeze (wire_resid.out): second-pass candidates (index 1) B > A in 10/10 and pass 0 equal 10/10;
           and the OSD wire: accepted OSD candidates B >= A in every checked cycle and B > A in at least one, else UNTESTED (does not void the arms; the verdict then reads "the pair, osdCorrThreshold's effect unverified").
  N-BETTER CI_lo(NET_B-A) > 0 pp.        N-WORSE  CI_hi(NET_B-A) < 0 pp.       NET = corroborated(B) - corroborated(A), all batches, pp of the WSJT-X decodes in the 400 cycles (L.match, as tn_analyse.py).
  U-OK     CI_hi(dU'_ta) <= 0.021.       U-FAIL   CI_lo(dU'_ta) > 0.021.       dU'_ta = new-text, NOT corroborated, tested_absent outputs of B (any batch; text absent from A's rows of that cycle), per
           cycle where WSJT-X decoded something, classified by the frozen instrument (as COH-RES-CAND, all batches in place of batch 4). Beside it, descriptive: the same count for A's outputs absent from B.
  FLAG     HK026_untestable_class_outputs_need_refreeze = (B's new-text uncorroborated outputs in untestable_class) > 0  (A1.3: any B output of a class not in the frozen set).
  VERDICT  (on B relative to A; first row that applies):
           VOID       a V-row fails (V-NAT, V-SET, V-WIRE (i) or (ii-candidates)).
           REVERT-10  N-WORSE or U-FAIL fires.
           KEEP-5     N-BETTER and U-OK fire and FLAG is False.
           OPEN       N-BETTER fires and (U-OK and U-FAIL both unfired, or U-OK fired with FLAG True)   (A1.4).
           NO-DIFF    otherwise.
  The OSD wire UNTESTED is reported next to the verdict, never changes it. The width of the NET interval is reported (A1.5).
Bootstrap: B = 2000 resamples of the cycles, seed 20261109 (paired indices).  HK-037: counts only leave this script; message text lives in memory."""
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

S = "D:/Projects/claude/_qa-scratch/kmin-osd-recal"
LS = "D:/Projects/claude/_qa-scratch/late-sub"
RAW, SCR = S + "/raw", S + "/scratch"
RUN = "20260930_1930"
NIGHT = "D:/Projects/claude/OpenWSFZ/artefacts/" + RUN + "_endurance_run-gathered"
SEL = "D:/Projects/claude/_qa-scratch/coh-res-cand/sel_400.json"
CLASSES = LS + "/u3_800/orig800_classes.json"
DLL = LS + "/bin_dev/libft8.dll"            # only the U' re-encoder (tones), as in tn_analyse.py
PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
CF = os.path.join(HERE, "..", "coh-fallback")
ARMS = {"A": (10, "0.10"), "B": (5, "0.05")}
N_CYCLES, BAR_NET_PP, U_BAR, B, SEED = 400, 0.0, 0.021, 2000, 20261109
assert (N_CYCLES, BAR_NET_PP, U_BAR, B, SEED) == (400, 0.0, 0.021, 2000, 20261109)
HASHED = re.compile(r"<[^>]*>")


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


def instrument(classes_sha):
    assert sha(CLASSES) == classes_sha, "classes differ from the frozen hash"
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


def v_set(arm):
    kmin, osd = ARMS[arm]
    out = {}
    for tag in ("start", "end"):
        line = next((x for x in open(f"{RAW}/{arm}/log.log", encoding="utf-8", errors="replace") if x.startswith(f"# readback {tag}")), "")
        need = ["decodingDepth=Deep", "nhard=24", "osdSignFixRead=1", "cohfb=True", "cohms=True", "cohaudio=Both", "ungated=True", "lateround=True", "threadsResolved=8",
                f"kMinScorePass2={kmin} ", f"osdCorrThreshold={osd}"]
        out[tag] = {"missing": [n for n in need if n not in line]}
    return {"missing": out, "PASS": all(not v["missing"] for v in out.values())}


def v_wire():
    txt = open(S + "/wire_resid.out", encoding="utf-8").read()
    cyc = re.findall(r"^\d+ \{'A': \((\d+), (\d+), (\d+), (\d+), (\d+)\), 'B': \((\d+), (\d+), (\d+), (\d+), (\d+)\)\}", txt, re.M)
    v = [tuple(int(x) for x in c) for c in cyc]
    cand = sum(1 for t in v if t[6] > t[1])
    ctrl = sum(1 for t in v if t[5] == t[0])
    ge = sum(1 for t in v if t[8] >= t[3])
    gt = sum(1 for t in v if t[8] > t[3])
    zero = all(t[3] == 0 and t[8] == 0 for t in v)
    return {"cycles": len(v), "candidates_B_gt_A_idx1": cand, "pass0_equal": ctrl, "cand_PASS": len(v) == 10 and cand == 10 and ctrl == 10,
            "osd_B_ge_A": ge, "osd_B_gt_A": gt, "osd_status": "UNTESTED" if zero else ("PASS" if ge == len(v) and gt >= 1 else "FAIL")}


def timing(arm):
    c = rows(f"{RAW}/{arm}/coh.csv")
    ar = [l.rstrip(chr(10)).split(",") for l in open(f"{RAW}/{arm}/abandon.csv") if l[:1].isdigit()]
    th = rows(f"{RAW}/{arm}/third.csv")
    late = rows(f"{RAW}/{arm}/late.csv")
    run = rows(f"{RAW}/{arm}/run.csv")
    latest = []
    for r in run:
        ts = [float(r[k]) for k in ("tb1_ms", "tb2_ms", "tb3_ms", "tb4_ms", "tb5_ms") if r.get(k) not in (None, "") and float(r[k]) > 0]
        if ts:
            latest.append(max(ts))
    q = lambda v, p: float(np.percentile(v, p)) if v else None
    return {"fallback_abandoned_cycles": sum(1 for r in c if int(r["abandoned"]) > 0), "residual_abandoned_cycles": sum(1 for r in ar if int(r[2]) > 0),
            "third_abandoned_or_failed_cycles": sum(1 for r in th if r["outcome"] in ("abandoned", "failed")),
            "late_round_abandoned_cycles": sum(1 for r in late if r["outcome"] == "abandoned"), "late_round_rows": len(late),
            "latest_batch_arrival_ms_median_p95_max": [q(latest, 50), q(latest, 95), max(latest) if latest else None]}


def cmd_main(classes_sha):
    stamps = [e if isinstance(e, str) else e[0] for e in json.load(open(SEL))["runs"][RUN]["FULL"]][:N_CYCLES]
    assert len(stamps) == N_CYCLES
    res = {"night": RUN, "cycles": len(stamps)}
    tree = S + "/tree"
    head = subprocess.run(["git", "-C", tree, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    g = subprocess.run(["git", "-C", tree, "diff", "--stat", "ef2fc84b", "--", "native", "src/OpenWSFZ.Ft8/Native"], capture_output=True, text=True)
    st_ok = all("mismatch" not in open(f"{RAW}/{a}_status.txt").read() for a in ARMS)
    res["V-NAT"] = {"tree_head": head, "native_diff_empty": g.returncode == 0 and g.stdout.strip() == "", "dll_pin_ok": sha(f"{S}/bin/libft8.dll") == PIN and st_ok,
                    "PASS": head.startswith("ef2fc84b") and g.returncode == 0 and g.stdout.strip() == "" and sha(f"{S}/bin/libft8.dll") == PIN and st_ok}
    res["V-SET"] = {a: v_set(a) for a in ARMS}
    res["V-SET"]["PASS"] = all(res["V-SET"][a]["PASS"] for a in ARMS)
    res["V-WIRE"] = {"i_V-SET": res["V-SET"]["PASS"], "ii": v_wire()}
    res["V-WIRE"]["PASS"] = res["V-WIRE"]["i_V-SET"] and res["V-WIRE"]["ii"]["cand_PASS"]
    C.ALLTXT = NIGHT + "/wsjt-x/ALL.TXT"
    ref = C.load_ref(set(stamps))
    n_ref = sum(len(ref.get(s, [])) for s in stamps)
    refc = np.array([float(len(ref.get(s, []))) for s in stamps])
    w = np.array([1.0 if ref.get(s) else 0.0 for s in stamps])
    res["n_ref"], res["cycles_with_wsjtx"] = n_ref, int(w.sum())
    a, b = load_nc(f"{SCR}/A/nc_dump.tsv"), load_nc(f"{SCR}/B/nc_dump.tsv")
    status = instrument(classes_sha)
    cols = {k: np.zeros(len(stamps)) for k in ("net", "ta", "hu", "pres", "unt", "out", "conf", "a_ta", "a_hu", "a_unt", "a_pres", "a_out", "a_conf")}
    corr_a = corr_b = dup = 0
    by_kind = {"B_only": collections.Counter(), "A_only": collections.Counter()}
    osd_rows = {"A": 0, "B": 0}
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
        osd_rows["A"] += sum(1 for x in a_rows if "osd" in x["path"].lower())
        osd_rows["B"] += sum(1 for x in b_rows if "osd" in x["path"].lower())
        for x in b_rows:
            if x["text"] not in a_texts:
                by_kind["B_only"][x["kind"]] += 1
        for x in a_rows:
            if x["text"] not in b_texts:
                by_kind["A_only"][x["kind"]] += 1
        for i, x in enumerate(b_rows):
            if x["text"] in a_texts:
                continue
            cols["out"][ci] += 1
            if i in b_uo:
                cols["conf"][ci] += 1
            else:
                sx = status(s, x["text"], x["f"], x["dt"])
                cols[{"tested_absent": "ta", "hashed_or_unencodable": "hu", "tested_present": "pres", "untestable_class": "unt"}[sx]][ci] += 1
        for i, x in enumerate(a_rows):
            if x["text"] in b_texts:
                continue
            cols["a_out"][ci] += 1
            if i in a_uo:
                cols["a_conf"][ci] += 1
            else:
                sx = status(s, x["text"], x["f"], x["dt"])
                cols[{"tested_absent": "a_ta", "hashed_or_unencodable": "a_hu", "tested_present": "a_pres", "untestable_class": "a_unt"}[sx]][ci] += 1
    res["B-DUP_descriptive"] = {"duplicate_text_instances_in_B": dup}
    res["A"], res["B"] = {"corroborated": corr_a, "pct": 100.0 * corr_a / n_ref}, {"corroborated": corr_b, "pct": 100.0 * corr_b / n_ref}
    keep = np.arange(len(stamps))
    rng = np.random.default_rng(SEED)
    idx = keep[rng.integers(0, len(keep), size=(B, len(keep)))]
    den = refc[idx].sum(axis=1)
    net = 100.0 * cols["net"][idx].sum(axis=1) / den
    wcnt = w[idx].sum(axis=1)
    pc = lambda a_: [float(np.percentile(a_, 2.5)), float(np.percentile(a_, 97.5))]
    ta = cols["ta"][idx].sum(axis=1) / wcnt
    r = {"NET_pp": 100.0 * cols["net"].sum() / refc.sum(), "NET_CI": pc(net), "NET_CI_width_pp": pc(net)[1] - pc(net)[0], "dU_ta": cols["ta"].sum() / w.sum(), "dU_ta_CI": pc(ta),
         "dU_hu": cols["hu"].sum() / w.sum(), "dU_present": cols["pres"].sum() / w.sum(),
         "B_new_text_outputs": int(cols["out"].sum()), "B_new_text_corroborated": int(cols["conf"].sum()),
         "B_untestable_class_outputs": int(cols["unt"].sum()), "B_hashed_or_unencodable_outputs": int(cols["hu"].sum()), "B_tested_absent_outputs": int(cols["ta"].sum()),
         "A_only_outputs": int(cols["a_out"].sum()), "A_only_corroborated": int(cols["a_conf"].sum()), "A_only_untestable_class_outputs": int(cols["a_unt"].sum()),
         "A_only_hashed_or_unencodable_outputs": int(cols["a_hu"].sum()), "A_only_tested_absent_outputs": int(cols["a_ta"].sum())}
    rw = {"N-BETTER": r["NET_CI"][0] > BAR_NET_PP, "N-WORSE": r["NET_CI"][1] < BAR_NET_PP, "U-OK": r["dU_ta_CI"][1] <= U_BAR, "U-FAIL": r["dU_ta_CI"][0] > U_BAR}
    flag = r["B_untestable_class_outputs"] > 0
    res["result"], res["rows"], res["HK026_untestable_class_outputs_need_refreeze"] = r, rw, flag
    vrows = res["V-NAT"]["PASS"] and res["V-SET"]["PASS"] and res["V-WIRE"]["PASS"]
    if not vrows:
        verdict = "VOID"
    elif rw["N-WORSE"] or rw["U-FAIL"]:
        verdict = "REVERT-10"
    elif rw["N-BETTER"] and rw["U-OK"] and not flag:
        verdict = "KEEP-5"
    elif rw["N-BETTER"] and ((not rw["U-OK"] and not rw["U-FAIL"]) or (rw["U-OK"] and flag)):
        verdict = "OPEN"
    else:
        verdict = "NO-DIFF"
    res["verdict"] = verdict
    res["osd_wire_note"] = ("osdCorrThreshold's effect unverified (the OSD wire is UNTESTED): read the verdict as the pair" if res["V-WIRE"]["ii"]["osd_status"] != "PASS" else "osd wire verified")
    res["descriptive"] = {"B_only_texts_by_batch": dict(by_kind["B_only"]), "A_only_texts_by_batch": dict(by_kind["A_only"]), "rows_with_osd_path": osd_rows,
                          "timing_A": timing("A"), "timing_B": timing("B")}
    print(json.dumps(res, indent=1, default=float))
    json.dump(res, open(S + "/kr_result.json", "w"), indent=1, default=float)
    return res


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "main":
        cmd_main(sys.argv[2])
    else:
        sys.exit("usage: kr_analyse.py main <classes_sha256>")
