#!/usr/bin/env python3
"""COH-RES-CAND v2 Stage 2 analysis (spec 2026-11-12-1340 section 3 + Amendments 1 (A1.2), 2 (A2.1) and 3 (A3.1, B-AB); QA review 158d610a / b5e65309).
Adapted from crc_analyse.py at 87c5486a (#272: the same scoring, the same frozen U' instrument, the same cycle bootstrap) and from cqap_analysis.py for the nc-dump loader.
Arm B (the v2 build, --cohrescand 1) against arm A (the CQ-AP OFF arm, REUSED) on the night 20261110_1817 (40 m), the 500 cycles of qa/cq-ap/live-session-cycle-list.txt.

    python crc2_analyse.py boff     B-OFF: the v2 build with the setting OFF (40 cycles) against arm A's rows for those 40 cycles; writes boff_result.json
    python crc2_analyse.py main     everything else, ONCE (refuses to overwrite crc2_result.json); needs boff_result.json with PASS
    python crc2_selftest.py         the synthetic self-test (Q-prefix calls only) - must pass before the freeze is committed

ROWS (mechanical; the predicates below are the code):
  VALIDITY (any failure => VOID: nothing else is read; the arm is repeated once on the fixed build)
  B-NAT   git diff --stat BASE BUILD -- native src/OpenWSFZ.Ft8/Native is empty AND libft8.dll SHA-256 = the pin at the start and end of every leg (status files).
  B-OFF   the build with the setting OFF publishes rows identical to arm A's for the first 40 cycles, every field (kind, matched, freq, dt, snr, path, text, apKind), 40 of 40.
  B-WIRE  denominator = arm-B cycles whose fallback line shows a residual level (coh.csv rescand = residual-R2|residual-R3). (i) resrun != no-snapshot in 100 % of them;
          (ii) resnewgated > 0 or resnewkept > 0 in at least one cycle (plumbing floor only).
  B-KEEP  every arm-A row of batches 1 to 4 (kind <= 4), by cycle and text, is in arm B. Allowed, listed and counted: an A row whose text holds a hashed call '<...>' and whose B row
          in the same cycle has the same freq and dt with a different rendering. Any other missing row fails. Batch 5 is outside B-KEEP (descriptive only).
  B-DUP   no text appears twice in one cycle of arm B's published rows.
  PRECISION
  N-GO    CI_lo(NET_B-A) > 0 pp.      N-STOP  CI_hi(NET_B-A) <= 0 pp.     (the Captain's bar for #272, carried unchanged)
  U-OK    CI_hi(dU'_ta) <= 0.021.     U-FAIL  CI_lo(dU'_ta) > 0.021.      dU'_ta = B's new-text (text absent from A's rows of that cycle), NOT corroborated outputs in batches 4 and 5,
          classified tested_absent by the frozen instrument (classes frozen from arm A), per cycle where WSJT-X decoded something. The U bar is absolute (Amendment 1 A1.3).
  B-AB    (Amendment 3) count of arm-B cycles with abandoned > 0 OR resabandoned > 0  <=  count of arm-A cycles with abandoned > 0.
  B-LATE  cycles whose L1' round was abandoned: count(B) <= count(A) + 5.
  VERDICT VOID iff any validity row fails; else ACCEPT iff N-GO, U-OK, B-AB, B-LATE all pass; FAIL iff N-STOP or U-FAIL; OPEN otherwise (goes to the Captain; no second night automatically).
DESCRIPTIVE (no verdict): resNew/resNewGated/resNewKept totals; resAbandoned total and cycle count; resRun counts; resWallMs median and max; latest-batch p95 of B and A against 13 s;
  B-only rows by batch (4 vs 5); the not-corroborated new-text outputs split tested_absent / tested_present / hashed / untestable; A-only batch-5 rows.
  NOT COMPUTABLE: the gated-out rows' C / TA split (spec 3): a gated-out row is dropped before publication, so no text of it exists in any output file.
Bootstrap: B = 2000 resamples of the cycles, seed 20261112 (paired: the same cycle indices for both arms), as crc_analyse.py.
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
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "gap-relocate-run"))
import gr_common as C      # noqa: E402
import gg_lib as L         # noqa: E402

CF = os.path.join(REPO, "qa", "rr-study", "coh-fallback")

# ---- FROZEN DECISION VALUES (each with its source) -----------------------------------------------------------------------------------------------------
V = "D:/Projects/claude/_qa-scratch/coh-res-cand-v2"
A_DIR = "D:/Projects/claude/_qa-scratch/cq-ap/arms/OFF"           # arm A = the CQ-AP OFF arm, reused (spec section 3; its repeat OFF2 differed in 0 of 500 cycles)
B_OFF_DIR = V + "/arms/B_OFF"
B_DIR = V + "/arms/B"
NIGHT = "D:/Projects/claude/OpenWSFZ/artefacts/20261110_1817_cq-ap-live"
CYCLE_LIST = os.path.join(REPO, "qa", "cq-ap", "live-session-cycle-list.txt")
CYCLE_LIST_SHA = "842e67909378a0d1dbf387b27d2e080b4f1e8c1dec3e9bd9770e2e3bac76c8f9"
CLASSES = os.path.join(HERE, "frozen", "uprime_arm_a_classes.json")
BASE_COMMIT, BUILD_COMMIT = "70bc72b1", "59eb5a8f"
TREE = V + "/tree"
DLL_PIN = "bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528"
N_CYCLES, N_BOFF = 500, 40
SEED, B = 20261112, 2000
BAR_NET_PP, U_BAR = 0.0, 0.021          # the Captain's 0 pp (#272, carried); U_bar_G ratified 2026-10-28 and ruled absolute for this night (Amendment 1 A1.3)
WIRE_SHARE = 1.0                         # spec: resRun != no-snapshot in 100 % (the plumbing passed 400/400 in #272)
LATE_SLACK = 5                           # spec B-LATE: 1 % of 500 cycles (the Architect's stated choice)
KEEP_MAX_KIND = 4                        # B-KEEP covers batches 1 to 4; batch 5 is descriptive
U_KINDS = (4, 5)                         # dU'_ta covers batches 4 and 5 (spec section 3)
LATE_BUDGET_MS = 13000.0
assert (N_CYCLES, N_BOFF, SEED, B, BAR_NET_PP, U_BAR, WIRE_SHARE, LATE_SLACK, KEEP_MAX_KIND, U_KINDS) == (500, 40, 20261112, 2000, 0.0, 0.021, 1.0, 5, 4, (4, 5))

VALIDITY = ("B-NAT", "B-OFF", "B-WIRE", "B-KEEP", "B-DUP")


# ---- loaders ---------------------------------------------------------------------------------------------------------------------------------------------
def norm(t):
    return " ".join(t.split())


def load_nc(path):
    """nc.tsv -> {stamp: [row]} sorted by kind (stable); row = dict(kind, matched, f, dt, snr, path, text, ap). Text stays in memory (HK-037)."""
    d = collections.defaultdict(list)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 11:
                continue
            d[p[0]].append(dict(kind=int(p[1]), matched=int(p[2]), f=int(p[3]), dt=float(p[4]), snr=int(p[5]), path=p[9], text=norm(p[10]), ap=(int(p[11]) if len(p) > 11 else None)))
    for s in d:
        d[s].sort(key=lambda x: x["kind"])
    return d


def csv_rows(p):
    with open(p, newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for ch in iter(lambda: fh.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def stamps_of(path=CYCLE_LIST, want_sha=CYCLE_LIST_SHA, n=N_CYCLES):
    assert sha256(path) == want_sha, "the cycle list differs from the frozen one"
    st = [l.strip()[:-4] for l in open(path) if l.strip().endswith(".wav")]
    assert len(st) == n, len(st)
    return st


def key_full(x):
    return (x["kind"], x["matched"], x["f"], round(x["dt"], 2), x["snr"], x["path"], x["text"], x["ap"])


# ---- the rows: ALL text comparisons live in these functions (HK-037) --------------------------------------------------------------------------------------
def row_boff(a, b, stamps40):
    """B-OFF: the setting-OFF build's rows equal arm A's, every field, in all 40 cycles."""
    same = sum(1 for s in stamps40 if [key_full(x) for x in a.get(s, [])] == [key_full(x) for x in b.get(s, [])])
    extra = sorted(set(b) - set(stamps40))
    return {"cycles_compared": len(stamps40), "identical_cycles": same, "cycles_in_B_outside_the_40": len(extra), "PASS": len(stamps40) == N_BOFF and same == N_BOFF and not extra}


def row_keep(a, b, stamps):
    """B-KEEP: every arm-A row of batches 1-4 is in arm B (by cycle and text); hashed re-renderings at the same freq and dt are allowed, listed and counted."""
    missing = exceptions = a_rows = 0
    for s in stamps:
        btexts = {x["text"] for x in b.get(s, [])}
        for x in a.get(s, []):
            if x["kind"] > KEEP_MAX_KIND:
                continue
            a_rows += 1
            if x["text"] in btexts:
                continue
            if "<" in x["text"] and any(y["f"] == x["f"] and round(y["dt"], 2) == round(x["dt"], 2) and y["text"] != x["text"] for y in b.get(s, [])):
                exceptions += 1
            else:
                missing += 1
    return {"A_rows_batches_1_to_4": a_rows, "missing": missing, "hashed_rerendering_exceptions": exceptions, "PASS": missing == 0}


def row_dup(b):
    dup = sum(len(rows) - len({x["text"] for x in rows}) for rows in b.values())
    return {"duplicate_text_instances_in_B": dup, "PASS": dup == 0}


def row_wire(coh_b):
    """B-WIRE from arm B's coh.csv res columns (resrun, rescand, resnewgated, resnewkept)."""
    den = [r for r in coh_b if (r.get("rescand") or "").startswith("residual-")]
    n_snap = sum(1 for r in den if r["resrun"] != "no-snapshot")
    share = (n_snap / len(den)) if den else 0.0
    cyc_new = sum(1 for r in coh_b if r.get("resnewgated") not in (None, "") and (int(r["resnewgated"]) > 0 or int(r["resnewkept"]) > 0))
    i, ii = share >= WIRE_SHARE and len(den) > 0, cyc_new >= 1
    return {"denominator_residual_level_cycles": len(den), "resrun_not_no_snapshot_share": share, "cycles_with_resNewGated_or_resNewKept_gt_0": cyc_new, "i": i, "ii": ii, "PASS": i and ii}


def row_ab(coh_a, coh_b):
    """B-AB (Amendment 3): B cycles with abandoned > 0 OR resabandoned > 0  <=  A cycles with abandoned > 0."""
    a = sum(1 for r in coh_a if int(r["abandoned"]) > 0)
    b = sum(1 for r in coh_b if int(r["abandoned"]) > 0 or (r.get("resabandoned") not in (None, "") and int(r["resabandoned"]) > 0))
    return {"A_cycles_abandoned_gt_0": a, "B_cycles_abandoned_or_resAbandoned_gt_0": b, "PASS": b <= a}


def row_late(late_a, late_b):
    """B-LATE: cycles whose L1' round was abandoned: count(B) <= count(A) + 5."""
    a = sum(1 for r in late_a if r["outcome"] == "abandoned")
    b = sum(1 for r in late_b if r["outcome"] == "abandoned")
    return {"A_late_round_abandoned_cycles": a, "B_late_round_abandoned_cycles": b, "PASS": b <= a + LATE_SLACK}


def ci_rows(net_ci, u_ci):
    return {"N-GO": net_ci[0] > BAR_NET_PP, "N-STOP": net_ci[1] <= BAR_NET_PP, "U-OK": u_ci[1] <= U_BAR, "U-FAIL": u_ci[0] > U_BAR}


def verdict(rows):
    """rows: dict of row name -> bool (validity rows and N-GO, N-STOP, U-OK, U-FAIL, B-AB, B-LATE)."""
    if not all(rows[k] for k in VALIDITY):
        return "VOID"
    if rows["N-STOP"] or rows["U-FAIL"]:
        return "FAIL"
    if rows["N-GO"] and rows["U-OK"] and rows["B-AB"] and rows["B-LATE"]:
        return "ACCEPT"
    return "OPEN"


def latest_batch_ms(rows):
    """Per cycle, the latest batch's publication time (ms) from run.csv (as cqap_analysis.latest_batch_ms)."""
    out = []
    for r in rows:
        ts = [float(r[k]) for k in ("tb1_ms", "tb2_ms", "tb3_ms", "tb4_ms", "tb5_ms") if r.get(k) not in (None, "") and float(r[k]) > 0]
        if ts:
            out.append(max(ts))
    return out


def p95(v):
    return float(np.percentile(v, 95)) if v else float("nan")


def pc(a):
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def bootstrap(net, ta, refc, w):
    keep = np.arange(len(net))
    rng = np.random.default_rng(SEED)
    idx = keep[rng.integers(0, len(keep), size=(B, len(keep)))]
    den = refc[idx].sum(axis=1)
    netb = 100.0 * net[idx].sum(axis=1) / den
    tab = ta[idx].sum(axis=1) / w[idx].sum(axis=1)
    return pc(netb), pc(tab)


# ---- the instrument (the frozen U' instrument as #272 used it, with this night's classes frozen from arm A) --------------------------------------------------
def make_status(classes_path, dll, night):
    spec = importlib.util.spec_from_file_location("cf_uprime_mod", CF + "/cf_uprime.py")
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)
    F, _ = U.load_instrument()
    enc = F.encoder(dll)
    frozen = json.load(open(classes_path))
    c_off = float(frozen["start_minus_dt_median_s"])
    testable = set(frozen["testable_classes"])
    pcms = {}

    def pcm_of(st):
        if st not in pcms:
            pcms[st] = F.wavio.load_cycle_pcm(os.path.join(night, "owsfz", "wav", st + ".wav"))
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


def compute_nat(tree=TREE, base=BASE_COMMIT, build=BUILD_COMMIT, bin_dll=V + "/bin_v2/libft8.dll", statuses=(B_OFF_DIR + "/status.txt", B_DIR + "/status.txt")):
    g = subprocess.run(["git", "-C", tree, "diff", "--stat", base, build, "--", "native", "src/OpenWSFZ.Ft8/Native"], capture_output=True, text=True)
    empty = g.returncode == 0 and g.stdout.strip() == ""
    dll_ok = sha256(bin_dll) == DLL_PIN
    st_ok = True
    for sp in statuses:
        txt = open(sp, encoding="utf-8", errors="replace").read() if os.path.exists(sp) else ""
        st_ok = st_ok and f"dll={DLL_PIN}" in txt and "END dll pin mismatch" not in txt and "exit 0 preflight_end_ok=1" in txt
    return {"git_diff_native_empty": empty, "dll_pin_ok": dll_ok, "legs_pin_ok_at_start_and_end": st_ok, "PASS": empty and dll_ok and st_ok}


# ---- the analysis ------------------------------------------------------------------------------------------------------------------------------------------
def analyse(stamps, a, b, coh_a, coh_b, late_a, late_b, run_a, run_b, ref, status, nat, boff, wire_log_check=None):
    """The whole of Stage 2 from loaded data. ref: {stamp: [(snr, dt, freq, text)]}; status(stamp, text, freq, dt) -> class string."""
    res = {"cycles": len(stamps)}
    res["B-NAT"], res["B-OFF"] = nat, boff
    res["B-WIRE"], res["B-KEEP"], res["B-DUP"] = row_wire(coh_b), row_keep(a, b, stamps), row_dup(b)
    if wire_log_check is not None:
        res["B-WIRE"]["log_residual_level_lines_equals_denominator"] = wire_log_check == res["B-WIRE"]["denominator_residual_level_cycles"]
    res["B-AB"], res["B-LATE"] = row_ab(coh_a, coh_b), row_late(late_a, late_b)
    n_ref = sum(len(ref.get(s, [])) for s in stamps)
    refc = np.array([float(len(ref.get(s, []))) for s in stamps])
    w = np.array([1.0 if ref.get(s) else 0.0 for s in stamps])
    res["n_ref"], res["cycles_with_wsjtx"] = n_ref, int(w.sum())
    cols = {k: np.zeros(len(stamps)) for k in ("net", "ta", "hu", "pres", "unt", "out", "conf", "hashed")}
    corr_a = corr_b = 0
    b_only_by_kind = collections.Counter()
    a_only_b5 = 0
    for ci, s in enumerate(stamps):
        r = ref.get(s, [])
        a_rows, b_rows = a.get(s, []), b.get(s, [])
        a_uw, _ = L.match(r, [(x["kind"], x["f"], x["text"]) for x in a_rows])
        b_uw, b_uo = L.match(r, [(x["kind"], x["f"], x["text"]) for x in b_rows])
        corr_a += len(a_uw)
        corr_b += len(b_uw)
        cols["net"][ci] = len(b_uw) - len(a_uw)
        a_texts, b_texts = {x["text"] for x in a_rows}, {x["text"] for x in b_rows}
        a_only_b5 += sum(1 for x in a_rows if x["kind"] == 5 and x["text"] not in b_texts)
        for i, x in enumerate(b_rows):
            if x["text"] in a_texts:
                continue
            b_only_by_kind[x["kind"]] += 1
            if x["kind"] not in U_KINDS:
                continue
            cols["out"][ci] += 1
            cols["hashed"][ci] += "<" in x["text"]
            if i in b_uo:
                cols["conf"][ci] += 1
            else:
                sx = status(s, x["text"], x["f"], x["dt"])
                cols[{"tested_absent": "ta", "hashed_or_unencodable": "hu", "tested_present": "pres", "untestable_class": "unt"}[sx]][ci] += 1
    res["A"] = {"corroborated": corr_a, "pct": 100.0 * corr_a / n_ref if n_ref else float("nan")}
    res["B"] = {"corroborated": corr_b, "pct": 100.0 * corr_b / n_ref if n_ref else float("nan")}
    net_ci, u_ci = bootstrap(cols["net"], cols["ta"], refc, w)
    r = {"NET_pp": 100.0 * cols["net"].sum() / refc.sum(), "NET_CI": net_ci, "dU_ta": cols["ta"].sum() / w.sum(), "dU_ta_CI": u_ci,
         "dU_hu": cols["hu"].sum() / w.sum(), "dU_present": cols["pres"].sum() / w.sum(), "dU_untestable_class_outputs": int(cols["unt"].sum()),
         "new_text_batch4_5_outputs": int(cols["out"].sum()), "new_text_batch4_5_corroborated": int(cols["conf"].sum())}
    res["result"] = r
    res["rows"] = ci_rows(net_ci, u_ci)
    res["descriptive"] = {
        "resNew_resNewGated_resNewKept_totals": [sum(int(x["resnew"]) for x in coh_b if x.get("resnew") not in (None, "")), sum(int(x["resnewgated"]) for x in coh_b if x.get("resnewgated") not in (None, "")),
                                                 sum(int(x["resnewkept"]) for x in coh_b if x.get("resnewkept") not in (None, ""))],
        "resAbandoned_total_and_cycles": [sum(int(x["resabandoned"]) for x in coh_b if x.get("resabandoned") not in (None, "")), sum(1 for x in coh_b if x.get("resabandoned") not in (None, "") and int(x["resabandoned"]) > 0)],
        "resRun_counts": dict(collections.Counter(x["resrun"] for x in coh_b if x.get("resrun"))),
        "resWallMs_median_max": ([float(np.median(v)), float(max(v))] if (v := [float(x["reswallms"]) for x in coh_b if x.get("reswallms") not in (None, "")]) else None),
        "latest_batch_p95_ms": {"A": p95(latest_batch_ms(run_a)), "B": p95(latest_batch_ms(run_b)), "B_minus_A": p95(latest_batch_ms(run_b)) - p95(latest_batch_ms(run_a)), "budget_ms": LATE_BUDGET_MS},
        "B_only_rows_by_batch": dict(b_only_by_kind), "A_only_batch5_rows": a_only_b5,
        "not_corroborated_new_text_split_per_cycle": {"tested_absent": r["dU_ta"], "hashed_or_unencodable": r["dU_hu"], "tested_present": r["dU_present"]},
        "gated_out_rows_C_TA_split": "NOT COMPUTABLE: a gated-out row is dropped before publication, so no text of it exists in any output file (spec section 3 descriptive line)"}
    allrows = {k: bool(res[k]["PASS"]) for k in VALIDITY}
    allrows.update(res["rows"])
    allrows["B-AB"], allrows["B-LATE"] = bool(res["B-AB"]["PASS"]), bool(res["B-LATE"]["PASS"])
    res["verdict"] = verdict(allrows)
    return res


def log_residual_lines(path):
    n = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "Coherent fallback:" in line and re.search(r"audio=both\(residual[23]\)", line):
                n += 1
    return n


def cmd_boff():
    stamps40 = stamps_of()[:N_BOFF]
    res = row_boff(load_nc(A_DIR + "/nc.tsv"), load_nc(B_OFF_DIR + "/nc.tsv"), stamps40)
    out = {"B-OFF": res, "arm_B_OFF_nc_sha256": sha256(B_OFF_DIR + "/nc.tsv")}
    print(json.dumps(out, indent=1))
    json.dump(out, open(V + "/boff_result.json", "w"), indent=1)
    return out


def cmd_main():
    out_path = V + "/crc2_result.json"
    assert os.environ.get("CRC2_OVERWRITE") == "1" or not os.path.exists(out_path), "crc2_result.json exists: the analysis runs ONCE"
    boff = json.load(open(V + "/boff_result.json"))["B-OFF"]
    stamps = stamps_of()
    a, b = load_nc(A_DIR + "/nc.tsv"), load_nc(B_DIR + "/nc.tsv")
    C.ALLTXT = NIGHT + "/wsjt-x/ALL.TXT"
    ref = C.load_ref(set(stamps))
    res = analyse(stamps, a, b, csv_rows(A_DIR + "/coh.csv"), csv_rows(B_DIR + "/coh.csv"), csv_rows(A_DIR + "/late.csv"), csv_rows(B_DIR + "/late.csv"),
                  csv_rows(A_DIR + "/run.csv"), csv_rows(B_DIR + "/run.csv"), ref, make_status(CLASSES, V + "/bin_v2/libft8.dll", NIGHT), compute_nat(), boff,
                  wire_log_check=log_residual_lines(B_DIR + "/log.log"))
    res["inputs"] = {"classes_sha256": sha256(CLASSES), "cycle_list_sha256": CYCLE_LIST_SHA, "arm_A_nc_sha256": sha256(A_DIR + "/nc.tsv"), "arm_B_nc_sha256": sha256(B_DIR + "/nc.tsv")}
    print(json.dumps(res, indent=1, default=float))
    json.dump(res, open(out_path, "w"), indent=1, default=float)
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "boff":
        cmd_boff()
    elif cmd == "main":
        cmd_main()
    else:
        sys.exit("usage: crc2_analyse.py boff | main")
