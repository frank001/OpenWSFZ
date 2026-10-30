#!/usr/bin/env python3
"""LATE-SUB L1' THIRD ACCEPTANCE NIGHT analysis (build spec section 4 + Amendment 1 + the ruling 2026-10-30-1802 section 4). Night 20260930_1930, 40 m; sol records pulled to the PC
by tn_pull.sh into _qa-scratch/late-sub/sol3n. Adapted from gs_analyze.py (the R-F4 second night), batch 5 in place of batch 4.
Rows: V-3N-AB, V-3N-REF, N-GO / N-STOP on NET, U-OK / U-FAIL on dU'(tested_absent), H-SHARE; ACCEPT-3N / FAIL-3N / OPEN-3N.
NET = (ON corroborated - OFF corroborated) in pp of the WSJT-X decodes in the selected cycles; both arms are real product outputs (nc dumps) from sol.
dU' as on TEST: the new-text, not-corroborated batch-5 outputs, classified by the frozen instrument over cycles where WSJT-X decoded something.
CLASSES come from THIS night's Original arm (first 200 cycles) and must be frozen first:
  python qa/rr-study/coh-fallback/cf_uprime.py off <sol3n/scratch/orig/nc_dump.tsv> <sol3n/raw/orig/testb.csv> <wav_root> 20260930_1930 <libft8.dll> <u3/orig.json>   (writes u3/orig_classes.json)
Timing (reported, vetoes nothing) from late.csv per the ruling's section 4: outcome counts (no-new split fit = 0 / fit > 0), R2-eligible = outcome does not start with skipped-,
T-WARN and BL-4 on R2-eligible with the fit > 0 rate beside it, elapsedMs median/p90/max on rows with fit > 0 only, endMs max on all rows, the night's new and published totals,
and any no-new with fit > 0 (no test pins that label). NOTE for the record: the R6-vs-inner elapsedMs agreement (within 1 ms) was checked on cycles 1-60 of the refset only.
usage: python tn_analyse.py [classes_sha256] ; counts only leave this script; text lives in memory (HK-037)."""
import collections
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C      # noqa: E402
import gg_lib as L         # noqa: E402

S = "D:/Projects/claude/_qa-scratch/late-sub"
SOL = S + "/sol3n"
# F-KA (Architect ruling 2026-10-30-1802 s7): TN_CFG=ka points the SAME scoring at the PC's raw_lr OFF and ON arms, refset 20260925_2010 cycles 401-1,200 (only input paths and the night change).
KA = os.environ.get("TN_CFG") == "ka"
SCR_DIR = (S + "/scratch_lr") if KA else (SOL + "/scratch")
RAW_DIR = (S + "/raw_lr") if KA else (SOL + "/raw")
ARMS = ("off", "on") if KA else ("off", "on", "orig")
OUT_JSON = (S + "/ka_result.json") if KA else (S + "/third_night_result.json")
CF = os.path.join(HERE, "..", "coh-fallback")
DLL = S + "/bin_dev/libft8.dll"            # the PC's DLL is used only for the U' re-encoder (tones), as in the second night
WAV_ROOT = "D:/Projects/claude/OpenWSFZ/artefacts"
RUN = "20260925_2010" if KA else "20260930_1930"
NIGHT = WAV_ROOT + f"/{RUN}_endurance_run-gathered"
SELF = "D:/Projects/claude/_qa-scratch/coh-gate-r-f4/selection1200.json" if KA else S + "/selection_3n.json"
CLASSES = "D:/Projects/claude/_qa-scratch/coh-gate-g/u/uprime_orig_classes.json" if KA else S + "/u3/orig_classes.json"
BAR_G, U_BAR_G, H = 0.5, 0.021, 0.5
B, SEED = 2000, 20261030
assert (BAR_G, U_BAR_G, H, B, SEED) == (0.5, 0.021, 0.5, 2000, 20261030)
N_CYCLES, REF_MIN_CYCLES = 800, 790
HASHED = re.compile(r"<[^>]*>")
BUDGET_MS = 13000
T_WARN_SHARE = 0.10


def load_nc(arm):
    d = collections.defaultdict(list)
    for r in C.load_tsv(f"{SCR_DIR}/{arm}/nc_dump.tsv"):
        if len(r) >= 11:
            d[r[0]].append(dict(kind=int(r[1]), matched=int(r[2]), f=int(r[3]), dt=float(r[4]), snr=int(r[5]), text="\t".join(r[10:])))
    for s in d:
        d[s].sort(key=lambda x: x["kind"])             # stable: kinds 1..5, as Replay81 scores them
    return d


def rows(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))] if v else None


def main():
    pins = {SELF: None, CLASSES: sys.argv[1] if len(sys.argv) > 1 else None}
    for p, want in pins.items():
        if want:
            assert hashlib.sha256(open(p, "rb").read()).hexdigest() == want, f"{p} differs from the frozen hash"
    sel = json.load(open(SELF))["runs"][RUN]["FULL"]
    stamps = [e if isinstance(e, str) else e[0] for e in sel]
    if KA:
        stamps = stamps[400:]                  # TEST = cycles 401-1,200 of a run that began at cycle 1 (one process)
    assert len(stamps) == N_CYCLES
    C.ALLTXT = NIGHT + "/wsjt-x/ALL.TXT"
    ref = C.load_ref(set(stamps))
    n_ref = sum(len(ref.get(s, [])) for s in stamps)
    refc = np.array([float(len(ref.get(s, []))) for s in stamps])
    w = np.array([1.0 if ref.get(s) else 0.0 for s in stamps])
    res = {"night": RUN, "cycles": len(stamps), "n_ref": n_ref, "cycles_with_wsjtx": int(w.sum())}

    # ---- V-3N-AB: residual pass, third pass (the cycle's FIRST Third pass line) and fallback abandoned = 0 in both arms (and orig) -----------------------------
    ab = {}
    for arm in ARMS:
        c = rows(f"{RAW_DIR}/{arm}/coh.csv")
        ar = [l.rstrip("\n").split(",") for l in open(f"{RAW_DIR}/{arm}/abandon.csv") if l[:1].isdigit()]
        th = rows(f"{RAW_DIR}/{arm}/third.csv")
        ab[arm] = {"fallback_abandoned": sum(int(r["abandoned"]) for r in c), "residual_abandoned": sum(int(r[2]) for r in ar),
                   "third_pass_abandoned_or_failed": sum(1 for r in th if r["outcome"] in ("abandoned", "failed"))}
    res["V-3N-AB"] = dict(ab, PASS=all(v == 0 for a in ab.values() for v in a.values()),
                          note="if not PASS: re-run both arms with the budget lifted (R-F4 A2.3) and read the rows from that pair; report this pair's counts")
    res["V-3N-REF"] = {"n_ref": n_ref, "cycles_with_wsjtx_lines": int(w.sum()), "need_at_least": REF_MIN_CYCLES, "PASS": int(w.sum()) >= REF_MIN_CYCLES}

    off, on = load_nc("off"), load_nc("on")
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

    cols = {k: np.zeros(len(stamps)) for k in ("net", "ta", "hu", "pres", "unt", "out", "conf", "hashed")}
    corr_off = corr_on = flag_off = flag_on = 0
    b5_off_rows = b5_on_rows = b5_on_conf = 0
    by = collections.defaultdict(collections.Counter)
    for ci, s in enumerate(stamps):
        r = ref.get(s, [])
        o_rows, n_rows = off.get(s, []), on.get(s, [])
        o_uw, o_uo = L.match(r, [(x["kind"], x["f"], x["text"]) for x in o_rows])
        n_uw, n_uo = L.match(r, [(x["kind"], x["f"], x["text"]) for x in n_rows])
        corr_off += len(o_uw)
        corr_on += len(n_uw)
        flag_off += sum(x["matched"] for x in o_rows)
        flag_on += sum(x["matched"] for x in n_rows)
        cols["net"][ci] = len(n_uw) - len(o_uw)
        b5_off_rows += sum(1 for x in o_rows if x["kind"] == 5)
        b5_on_rows += sum(1 for x in n_rows if x["kind"] == 5)
        off_texts = {x["text"] for x in o_rows}
        for i, x in enumerate(n_rows):
            if x["kind"] != 5 or x["text"] in off_texts:
                continue
            cols["out"][ci] += 1
            cols["hashed"][ci] += bool(HASHED.search(x["text"]))
            by["band"][C.band_of(x["snr"])] += 1
            if i in n_uo:
                cols["conf"][ci] += 1
                b5_on_conf += 1
            else:
                sx = status(s, x["text"], x["f"], x["dt"])
                cols[{"tested_absent": "ta", "hashed_or_unencodable": "hu", "tested_present": "pres", "untestable_class": "unt"}[sx]][ci] += 1
    res["match_vs_replay_flag"] = {"off_L_match": corr_off, "off_flag_sum": flag_off, "on_L_match": corr_on, "on_flag_sum": flag_on,
                                   "PASS": corr_off == flag_off and corr_on == flag_on}
    res["baseline_OFF"] = {"corroborated": corr_off, "pct": 100.0 * corr_off / n_ref, "batch5_rows_in_off_arm": b5_off_rows}
    res["ON"] = {"corroborated": corr_on, "pct": 100.0 * corr_on / n_ref, "batch5_rows": b5_on_rows, "batch5_new_text_corroborated": b5_on_conf}

    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(stamps), size=(B, len(stamps)))
    den = refc[idx].sum(axis=1)
    net = 100.0 * cols["net"][idx].sum(axis=1) / den
    wcnt = w[idx].sum(axis=1)
    pc = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    ta = cols["ta"][idx].sum(axis=1) / wcnt
    hu = cols["hu"][idx].sum(axis=1) / wcnt
    pres = cols["pres"][idx].sum(axis=1) / wcnt
    outs = cols["out"].sum()
    r = {"NET_pp": 100.0 * cols["net"].sum() / refc.sum(), "NET_CI": pc(net),
         "dU_ta": cols["ta"].sum() / w.sum(), "dU_ta_CI": pc(ta), "dU_hu": cols["hu"].sum() / w.sum(), "dU_hu_CI": pc(hu),
         "dU_present": cols["pres"].sum() / w.sum(), "dU_present_CI": pc(pres), "dU_untestable_class": cols["unt"].sum() / w.sum(),
         "untestable_class_outputs": int(cols["unt"].sum()),
         "admitted_new_text": int(outs), "admitted_corroborated": int(cols["conf"].sum()),
         "corroborated_share": float(cols["conf"].sum() / outs) if outs else None,
         "hashed_share_of_new": float(cols["hashed"].sum() / outs) if outs else None,
         "by_band": dict(by["band"])}
    res["L1p-3N"] = r
    rows_ = {"N-GO": r["NET_CI"][0] >= BAR_G, "N-STOP": r["NET_CI"][1] < BAR_G, "U-OK": r["dU_ta_CI"][1] <= U_BAR_G,
             "U-FAIL": r["dU_ta_CI"][0] > U_BAR_G, "H-SHARE_fires": (r["hashed_share_of_new"] or 0.0) > H}
    res["rows"] = rows_
    res["HK026_untestable_class_outputs_need_refreeze"] = r["untestable_class_outputs"] > 0

    # ---- timing (reported; vetoes nothing), from late.csv per the ruling section 4 -------------------------------------------------------------------------
    late = rows(f"{RAW_DIR}/on/late.csv") if os.path.exists(f"{RAW_DIR}/on/late.csv") else []   # raw_lr has no late.csv (F-KA)
    out_ct = collections.Counter()
    for x in late:
        out_ct[x["outcome"] if x["outcome"] != "no-new" else ("no-new(fit=0)" if x["fit"] == "0" else "no-new(fit>0)")] += 1
    elig = [x for x in late if not x["outcome"].startswith("skipped-")]
    elig_fit = [x for x in elig if int(x["fit"]) > 0]
    ab_ct = lambda L_: sum(1 for x in L_ if x["outcome"] == "abandoned")
    share = lambda L_: (ab_ct(L_) / len(L_)) if L_ else None
    el = [int(x["elapsedMs"]) for x in late if int(x["fit"]) > 0]
    ends = [int(x["endMs"]) for x in late]
    res["timing_sol"] = {
        "late_csv_rows": len(late), "unmatched_lines": sum(int(x["unmatched"]) for x in late), "cycles_with_exactly_one_line": sum(1 for x in late if x["lines"] == "1"),
        "outcome_counts": dict(out_ct), "R2_eligible_cycles": len(elig), "R2_eligible_with_fit_gt_0": len(elig_fit),
        "abandoned_share_of_R2_eligible": share(elig), "abandoned_share_of_fit_gt_0": share(elig_fit),
        "T-WARN_fires_registered_denominator": (share(elig) or 0.0) > T_WARN_SHARE, "T-WARN_fires_fit_gt_0": (share(elig_fit) or 0.0) > T_WARN_SHARE,
        "BL-4_abandoned_le_5pct_registered_denominator": (share(elig) or 0.0) <= 0.05, "BL-4_abandoned_le_5pct_fit_gt_0": (share(elig_fit) or 0.0) <= 0.05,
        "elapsedMs_fit_gt_0_median_p90_max": [q(el, .5), q(el, .9), max(el) if el else None],
        "endMs_all_rows_max": max(ends) if ends else None, "margin_to_13000_ms": (BUDGET_MS - max(ends)) if ends else None,
        "new_total": sum(int(x["new"]) for x in late), "published_total": sum(int(x["published"]) for x in late),
        "no_new_with_fit_gt_0_cycles": sum(1 for x in late if x["outcome"] == "no-new" and int(x["fit"]) > 0),
        "skip_reasons": {k: v for k, v in out_ct.items() if k.startswith("skipped-")}}

    def fb_end(arm):
        t = open(f"{RAW_DIR}/{arm}/log.log", encoding="utf-8", errors="replace").read()
        e = [int(a) + int(b) for a, b in re.findall(r"fbStartMs=(-?\d+), fbWallMs=(-?\d+)", t) if int(b) >= 0]
        return {"max_fallback_end_ms": max(e), "fallback_lines": len(re.findall("Coherent fallback:", t))}
    res["timing_fallback"] = {"off": fb_end("off"), "on": fb_end("on")}
    verdict = ("ACCEPT-3N" if rows_["N-GO"] and rows_["U-OK"] and not rows_["H-SHARE_fires"] else
               "FAIL-3N" if rows_["N-STOP"] or rows_["U-FAIL"] else "OPEN-3N")
    res["verdict"] = verdict
    res["verdict_valid_only_if"] = "V-3N-AB PASS and V-3N-REF PASS and HK026_untestable_class_outputs_need_refreeze False (else follow the spec: budget-lifted re-run / Original on the other 600 cycles and re-freeze)"
    json.dump(res, open(OUT_JSON, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
