#!/usr/bin/env python3
"""NHARD-CEIL analysis (spec arch/fp-alarm-nhard section 2 + Amendment 1 A1.3 for TOOL-FAIL, ruling 2026-11-12-1724; QA freeze record names this file's blob).
How much does OSD contribute on today's decoder? N24 (--nhard 24) against N0 (--nhard 0, OSD off), the station stack (CQ-AP ON, v2 ON), night 20261110_1817 (40 m), the 500 cycles of
qa/cq-ap/live-session-cycle-list.txt. Reuses crc2_analyse.py (blob c6e48546...: loaders, the WSJT-X matcher, the cycle bootstrap, the frozen U' instrument wrapper).

    python nhard_analyse.py main     everything, ONCE (refuses to overwrite nhard_result.json)
    python nhard_selftest.py         the synthetic self-test (Q-prefix calls only) - must pass, every mutation killed, before the freeze

ROWS (mechanical; the predicates below are the code):
  VALIDITY (any failure => VOID)
  V-NAT   git diff --stat BASE BUILD -- native src/OpenWSFZ.Ft8/Native empty AND libft8.dll SHA-256 = the pin at the start and end of each arm (status files).
  V-SET   each arm's readback line, at the start and at the end, equals the other's with the nhard token removed, carries nhard 24 / 0 and cqap=True, cohrescand=True.
  V-WIRE  N24 and N0 differ in the published rows of >= 1 cycle (OSD really is off in N0). Plumbing floor only.
  PRECISION (the verdict is on these two only)
  C-NET   NET_{N24-N0} with a 95 % CI: corroborated rows (WSJT-X match) of N24 minus N0, per 100 reference rows, paired cycle bootstrap B = 2000, seed 20261112.
  C-U     dU'_ta,{N24-N0} with a 95 % CI: N24's new-text (absent from N0's rows of that cycle) NOT-corroborated outputs of ALL batches (OSD acts in every native pass), classified
          tested_absent by the frozen U' instrument (classes frozen from arm A of this night), per cycle where WSJT-X decoded something.
  VERDICT VOID iff a validity row fails; else SETTLED iff CI_hi(NET) < 0.15 pp AND CI_hi(dU'_ta) <= 0.021; GRID iff CI_lo(NET) >= 0.15 pp OR CI_lo(dU'_ta) > 0.021; else BETWEEN.
          FLAG (any non-VOID verdict): CI_hi(NET) < 0 means OSD COSTS decodes on this stack.
          Under TOOL-FAIL (ruling 2026-11-12-1724) the alarm does not enter: SETTLED is worded "settled where U' can see" and carries U-COV.
DESCRIPTIVE: U-COV (the share of N24-minus-N0 not-corroborated new rows in a testable class, hashed, untestable); NET and dU'_ta by batch; latest-batch p95 per arm against 13 s;
  abandoned counts (fallback, residual-pass rows, third-run resAbandoned, L1' round); N24 minus v2's Stage 2 arm B (only --cq-ap differs: the CQ-AP effect on the v2 stack), no verdict.
HK-037: counts only leave this script; message text lives in memory."""
import collections
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "coh-res-cand-v2"))
import crc2_analyse as K  # noqa: E402  (loaders, bootstrap, instrument wrapper, constants)

L = K.L
C = K.C

# ---- FROZEN DECISION VALUES (each with its source) -----------------------------------------------------------------------------------------------------------
V2 = "D:/Projects/claude/_qa-scratch/nhard-ceil"
N24_DIR, N0_DIR = V2 + "/arms/N24", V2 + "/arms/N0"
ARM_B_DIR = "D:/Projects/claude/_qa-scratch/coh-res-cand-v2/arms/B"       # v2's Stage 2 arm B (CQ-AP OFF), for the descriptive CQ-AP line
BIN_DLL = "D:/Projects/claude/_qa-scratch/coh-res-cand-v2/bin_v2/libft8.dll"
NIGHT = K.NIGHT
CLASSES = K.CLASSES                                   # frozen from arm A of this night (see the freeze record: the spec's "from N24" cannot exist before N24 has run)
BAR_NET_PP = 0.15     # the Architect's choice of the smallest prize worth a below-24 grid (A1.5, his E166); the Captain may move it before data, never after
BAR_U = 0.021         # U_bar_G, ruled absolute (v2 A1.3)
NH24, NH0 = 24, 0
SEED, B = 20261112, 2000
ALL_KINDS = (1, 2, 3, 4, 5)
BASE_COMMIT, BUILD_COMMIT = "59eb5a8f", "260190e8"     # bin_v2 is built from 59eb5a8f; main 260190e8 has an identical source tree (only Linux/macOS binaries differ)
assert (BAR_NET_PP, BAR_U, NH24, NH0, SEED, B) == (0.15, 0.021, 24, 0, 20261112, 2000)

VALIDITY = ("V-NAT", "V-SET", "V-WIRE")


def verdict(r):
    """r: dict with the validity booleans and net_lo, net_hi, u_lo, u_hi. Returns (verdict, flag_osd_costs)."""
    if not all(r[k] for k in VALIDITY):
        return "VOID", False
    flag = r["net_hi"] < 0
    if r["net_hi"] < BAR_NET_PP and r["u_hi"] <= BAR_U:
        return "SETTLED", flag
    if r["net_lo"] >= BAR_NET_PP or r["u_lo"] > BAR_U:
        return "GRID", flag
    return "BETWEEN", flag


def readback_lines(path):
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for tag in ("start", "end"):
                if line.startswith(f"# readback {tag}") and tag not in out:
                    out[tag] = line.rstrip("\n")
    return out


def row_set(rb24, rb0):
    """V-SET: both arms' readbacks equal except the nhard token; N24 reads nhard=24, N0 nhard=0; both cqap=True and cohrescand=True."""
    ok = True
    for tag in ("start", "end"):
        a, b = rb24.get(tag, ""), rb0.get(tag, "")
        if not a or not b:
            ok = False
            continue
        strip = lambda s: re.sub(r"nhard=\d+", "nhard=*", s)
        if strip(a) != strip(b):
            ok = False
        if f"nhard={NH24} " not in a or f"nhard={NH0} " not in b:
            ok = False
        for line in (a, b):
            if "cqap=True" not in line or "cohrescand=True" not in line:
                ok = False
    return {"PASS": ok}


def row_wire(n24, n0, stamps):
    diff = sum(1 for s in stamps if [K.key_full(x) for x in n24.get(s, [])] != [K.key_full(x) for x in n0.get(s, [])])
    return {"cycles_with_different_published_rows": diff, "PASS": diff >= 1}


def compute_nat(tree=K.TREE, bin_dll=BIN_DLL, statuses=(N24_DIR + "/status.txt", N0_DIR + "/status.txt")):
    import subprocess
    g = subprocess.run(["git", "-C", tree, "diff", "--stat", BASE_COMMIT, BUILD_COMMIT, "--", "native", "src/OpenWSFZ.Ft8/Native"], capture_output=True, text=True)
    empty = g.returncode == 0 and g.stdout.strip() == ""
    dll_ok = K.sha256(bin_dll) == K.DLL_PIN
    st_ok = True
    for sp in statuses:
        txt = open(sp, encoding="utf-8", errors="replace").read() if os.path.exists(sp) else ""
        st_ok = st_ok and f"dll={K.DLL_PIN}" in txt and "END dll pin mismatch" not in txt and "exit 0 preflight_end_ok=1" in txt
    return {"git_diff_native_empty": empty, "dll_pin_ok": dll_ok, "arms_pin_ok_at_start_and_end": st_ok, "PASS": empty and dll_ok and st_ok}


def analyse(stamps, n24, n0, arm_b, coh24, coh0, run24, run0, late24, late0, ref, status, nat, setrow):
    res = {"cycles": len(stamps), "V-NAT": nat, "V-SET": setrow, "V-WIRE": row_wire(n24, n0, stamps)}
    n_ref = sum(len(ref.get(s, [])) for s in stamps)
    refc = np.array([float(len(ref.get(s, []))) for s in stamps])
    w = np.array([1.0 if ref.get(s) else 0.0 for s in stamps])
    res["n_ref"], res["cycles_with_wsjtx"] = n_ref, int(w.sum())
    cols = {k: np.zeros(len(stamps)) for k in ("net", "ta", "hu", "pres", "unt", "out", "conf", "net_b")}
    by_kind_net = collections.Counter(); by_kind_ta = collections.Counter(); n24_only_by_kind = collections.Counter(); n0_only_rows = 0
    corr24 = corr0 = corr_b = 0
    for ci, s in enumerate(stamps):
        r = ref.get(s, [])
        a24, a0, ab = n24.get(s, []), n0.get(s, []), arm_b.get(s, [])
        u24, o24 = L.match(r, [(x["kind"], x["f"], x["text"]) for x in a24])
        u0, o0 = L.match(r, [(x["kind"], x["f"], x["text"]) for x in a0])
        ub, _ = L.match(r, [(x["kind"], x["f"], x["text"]) for x in ab])
        corr24 += len(u24); corr0 += len(u0); corr_b += len(ub)
        cols["net"][ci] = len(u24) - len(u0)
        cols["net_b"][ci] = len(u24) - len(ub)
        t0 = {x["text"] for x in a0}; t24 = {x["text"] for x in a24}
        n0_only_rows += len(t0 - t24)
        for i, x in enumerate(a24):
            if x["text"] in t0 or x["kind"] not in ALL_KINDS:
                continue
            n24_only_by_kind[x["kind"]] += 1
            cols["out"][ci] += 1
            if i in o24:
                cols["conf"][ci] += 1
                by_kind_net[x["kind"]] += 1
            else:
                sx = status(s, x["text"], x["f"], x["dt"])
                cols[{"tested_absent": "ta", "hashed_or_unencodable": "hu", "tested_present": "pres", "untestable_class": "unt"}[sx]][ci] += 1
                if sx == "tested_absent":
                    by_kind_ta[x["kind"]] += 1
    res["N24"] = {"corroborated": corr24, "pct": 100.0 * corr24 / n_ref if n_ref else float("nan")}
    res["N0"] = {"corroborated": corr0, "pct": 100.0 * corr0 / n_ref if n_ref else float("nan")}
    net_ci, u_ci = K.bootstrap(cols["net"], cols["ta"], refc, w)
    net_ci_b, _ = K.bootstrap(cols["net_b"], cols["ta"], refc, w)
    r = {"NET_pp": 100.0 * cols["net"].sum() / refc.sum(), "NET_CI": net_ci, "dU_ta": cols["ta"].sum() / w.sum(), "dU_ta_CI": u_ci}
    res["C-NET"] = {"NET_pp": r["NET_pp"], "CI": net_ci}
    res["C-U"] = {"dU_ta": r["dU_ta"], "CI": u_ci}
    nu = int(cols["out"].sum())
    res["descriptive"] = {
        "U-COV": {"N24_only_new_text_rows": nu, "corroborated": int(cols["conf"].sum()), "not_corroborated": nu - int(cols["conf"].sum()),
                  "tested_absent": int(cols["ta"].sum()), "tested_present": int(cols["pres"].sum()), "hashed_or_unencodable": int(cols["hu"].sum()), "untestable_class": int(cols["unt"].sum()),
                  "share_of_not_corroborated_judged_by_U_prime": ((int(cols["ta"].sum()) + int(cols["pres"].sum())) / (nu - int(cols["conf"].sum()))) if nu - int(cols["conf"].sum()) else None},
        "N24_only_new_text_rows_by_batch": dict(n24_only_by_kind), "N24_only_tested_absent_by_batch": dict(by_kind_ta), "N24_only_corroborated_by_batch": dict(by_kind_net),
        "N0_only_text_rows_total": n0_only_rows,
        "latest_batch_p95_ms": {"N24": K.p95(K.latest_batch_ms(run24)), "N0": K.p95(K.latest_batch_ms(run0)), "budget_ms": K.LATE_BUDGET_MS},
        "abandoned": {"N24": {"fallback_cycles": sum(1 for x in coh24 if int(x["abandoned"]) > 0), "resAbandoned_cycles": sum(1 for x in coh24 if x.get("resabandoned") not in (None, "") and int(x["resabandoned"]) > 0),
                              "late_round_cycles": sum(1 for x in late24 if x["outcome"] == "abandoned")},
                      "N0": {"fallback_cycles": sum(1 for x in coh0 if int(x["abandoned"]) > 0), "resAbandoned_cycles": sum(1 for x in coh0 if x.get("resabandoned") not in (None, "") and int(x["resabandoned"]) > 0),
                             "late_round_cycles": sum(1 for x in late0 if x["outcome"] == "abandoned")}},
        "CQ_AP_effect_on_the_v2_stack_N24_minus_arm_B_descriptive": {"corroborated_N24": corr24, "corroborated_arm_B": corr_b, "NET_pp": 100.0 * cols["net_b"].sum() / refc.sum(), "NET_CI": net_ci_b,
                                                                       "only_difference": "--cq-ap 1 (N24) vs --cq-ap 0 (arm B); same build, same cycles, nhard 24"},
    }
    flat = {k: bool(res[k]["PASS"]) for k in VALIDITY}
    flat.update({"net_lo": net_ci[0], "net_hi": net_ci[1], "u_lo": u_ci[0], "u_hi": u_ci[1]})
    v, flag = verdict(flat)
    res["verdict"] = v
    res["flag_OSD_costs_decodes"] = bool(flag)
    res["verdict_wording"] = ("SETTLED where U' can see (U-COV above states how much it cannot); nhard stays 24 for this stack, no grid" if v == "SETTLED"
                              else "GRID: a below-24 grid is worth asking the Captain about (its own spec)" if v == "GRID"
                              else "BETWEEN: goes to the Captain with the numbers" if v == "BETWEEN" else "VOID: a validity row failed; nothing else is read")
    return res


def cmd_main():
    out_path = V2 + "/nhard_result.json"
    assert os.environ.get("NHARD_OVERWRITE") == "1" or not os.path.exists(out_path), "nhard_result.json exists: the analysis runs ONCE"
    stamps = K.stamps_of()
    n24, n0, arm_b = K.load_nc(N24_DIR + "/nc.tsv"), K.load_nc(N0_DIR + "/nc.tsv"), K.load_nc(ARM_B_DIR + "/nc.tsv")
    C.ALLTXT = NIGHT + "/wsjt-x/ALL.TXT"
    ref = C.load_ref(set(stamps))
    res = analyse(stamps, n24, n0, arm_b, K.csv_rows(N24_DIR + "/coh.csv"), K.csv_rows(N0_DIR + "/coh.csv"), K.csv_rows(N24_DIR + "/run.csv"), K.csv_rows(N0_DIR + "/run.csv"),
                  K.csv_rows(N24_DIR + "/late.csv"), K.csv_rows(N0_DIR + "/late.csv"), ref, K.make_status(CLASSES, BIN_DLL, NIGHT), compute_nat(),
                  row_set(readback_lines(N24_DIR + "/log.log"), readback_lines(N0_DIR + "/log.log")))
    res["inputs"] = {"classes_sha256": K.sha256(CLASSES), "cycle_list_sha256": K.CYCLE_LIST_SHA, "N24_nc_sha256": K.sha256(N24_DIR + "/nc.tsv"), "N0_nc_sha256": K.sha256(N0_DIR + "/nc.tsv")}
    print(json.dumps(res, indent=1, default=float))
    json.dump(res, open(out_path, "w"), indent=1, default=float)
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "main":
        cmd_main()
    else:
        sys.exit("usage: nhard_analyse.py main")
