#!/usr/bin/env python
"""NHARD-REP Amendment 3 (OSD-OFF): the pre-registered rows for arm N0 (nhard 0) PAIRED with the existing N40, computed AFTER the run, as code.

Spec (Architect 2026-10-06 18:19Z, section 14; the O-SAFE margin 0.10 pp was RATIFIED by the Captain ~18:20Z, before N0 ran, FROZEN): qa/rr-study/2026-10-06-1430-architect-to-qa-spec-nhard-replication.md
(branch arch/nhard-replication). Every threshold below is the spec's. Predicates are pure functions (tests/test_nhard_rep_n0_rows.py shows each fires and does not fire).

  NET_0 (pp) = 100 * sum(M0_i - M40_i) / sum(W_i), the closed NHARD-REP block bootstrap (block 8 sampled cycles, B 10 000, seed 20261006), N0 against the N40 on file.
  Rows, EXCLUSIVE, FIRST MATCH WINS, in this order:
    O-HARM  CI_hi(NET_0) <  0      something genuine depended on the inverted OSD (contradicts #215's analysis; the Architect re-examines before any default change)
    O-GAIN  CI_lo(NET_0) >  0      switching OSD off GAINS WSJT-X-confirmed decodes
    O-SAFE  CI_lo(NET_0) >= -0.10  off costs at most 0.10 pp of confirmed decodes
    O-OPEN  otherwise
  HK-038: 0 is the no-change point (not a carried figure); -0.10 pp is a decision margin ratified by the Captain (proposed basis: E3 found 2 of 57,594 confirmed decodes depended on OSD).
  HK-025(k), both ways: a blind instrument (nhard 0 never applied) would give N0 == N40, CI [0, 0], which CLEARS -0.10 and would fire O-SAFE: V2'' (P_lo REJECTED at 0 at both
  probe points, while ACCEPTED in N40) is the outcome-independent proof the setting reached the gate, and it gates the verdict.
  V6 is CARRIED from the closed run (N40's A/A: 200/200 identical): it is not re-run.

  python qa/rr-study/nhard-rep/nhard_rep_n0_rows.py [--n0 <dir>] [--n40 <dir>] [--results <dir>]
"""
import collections
import datetime
import hashlib
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import nhard_rep_rows as NR  # noqa: E402

O = NR.O
BAR_SAFE_MARGIN_PP = 0.10      # O-SAFE: ratified by the Captain 2026-10-06 ~18:20Z, FROZEN
ARM = "N0"
ARM_NHARD = 0
PAIRED_ARM = "N40"
STAMP = re.compile(r"^\d{6}_\d{6}$")


def verdict_row(ci_lo, ci_hi, margin=BAR_SAFE_MARGIN_PP):
    """Exclusive, first match wins, in the spec's order."""
    if ci_hi < 0:
        return "O-HARM"
    if ci_lo > 0:
        return "O-GAIN"
    if ci_lo >= -margin:
        return "O-SAFE"
    return "O-OPEN"


def row_v1(pins):
    """V1': the pin equal at the start and at the end of N0. A missing record FAILS."""
    seen = {p["when"]: p.get("libft8_sha256") == NR.DLL_PIN and p.get("pinned", NR.DLL_PIN) == NR.DLL_PIN for p in pins if p.get("arm") == ARM}
    bad = [w for w in ("start", "end") if not seen.get(w, False)]
    return (not bad), {"failed_or_missing": bad}


def row_v2pp(probe_n0, probe_n40):
    """V2'' (the setting reached the gate; outcome-independent): in N0 BOTH vectors are REJECTED (rc 0, path -1) at BOTH probe points (>= 1 row of each (point, vector)),
    AND in the N40 on file P_lo was ACCEPTED (rc 0, path 1, CRC 1, payload match) at both points: the contrast that proves 0 changed the gate's answer. Anything else FAILS,
    and an absent probe file never reads as a pass."""
    bad = []
    for w in ("start", "end"):
        for v in ("P_lo", "P_hi"):
            rows = [r for r in probe_n0 if r["when"] == w and r["vec"] == v]
            if not rows:
                bad.append(f"N0:{w}:{v} missing")
            for r in rows:
                if not (r["rc"] == 0 and r["path"] == -1):
                    bad.append(f"N0:{w}:{v} not rejected (path={r['path']} crc={r['crc_ok']})")
        lo40 = [r for r in probe_n40 if r["when"] == w and r["vec"] == "P_lo"]
        if not lo40:
            bad.append(f"N40:{w}:P_lo missing")
        for r in lo40:
            if not (r["rc"] == 0 and r["path"] == 1 and r["crc_ok"] == 1 and r["payload_match"]):
                bad.append(f"N40:{w}:P_lo not accepted")
    return (not bad), {"problems": bad, "n0_rows": len(probe_n0), "n40_rows": len(probe_n40)}


def row_v3(run_rows, restarts, contained):
    """V3: 0 exception rows, 0 non-zero exits, 0 contained exceptions in N0."""
    exc = sum(1 for r in run_rows if r["exception"])
    return (exc == 0 and restarts == 0 and contained == 0), {"exception_rows": exc, "nonzero_exits": restarts, "contained": contained, "rows": len(run_rows)}


def row_v4(readback, selection_sha, probe_sha):
    """V4: subtraction ON, threads 8, nhard 0 read back at start AND end; selection.json and probe_vectors.json SHAs equal the frozen values."""
    bad = []
    whens = {r["when"] for r in readback}
    if whens != {"start", "end"}:
        bad.append(f"readback lines {sorted(whens)}")
    for r in readback:
        if r["subtractionEnabled"] is not True:
            bad.append(f"{r['when']}: subtractionEnabled={r['subtractionEnabled']}")
        if r["threadsConfigured"] != NR.THREADS or r["nhard"] != ARM_NHARD:
            bad.append(f"{r['when']}: threads={r['threadsConfigured']} nhard={r['nhard']} (expected {ARM_NHARD})")
    if selection_sha != NR.SELECTION_SHA256:
        bad.append("selection.json SHA differs")
    if probe_sha != NR.PROBE_SHA256:
        bad.append("probe_vectors.json SHA differs")
    return (not bad), {"problems": bad}


def row_v5(abandon_n0, stamps):
    """V5: residual passes abandoned <= 5 % of the sampled cycles in N0; a missing record FAILS."""
    return O.row_v5(abandon_n0, stamps)


def _sum_b(cy, kind, idx):
    return sum(cy[kind][b][idx] for b in NR.BANDS)


def analyse(n0_dir, n40_dir, results_dir=None, selection_path=None):
    selection_path = selection_path or os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")
    sel_bytes = open(selection_path, "rb").read().replace(b"\r\n", b"\n")
    sel_sha = hashlib.sha256(sel_bytes).hexdigest()
    probe_sha = hashlib.sha256(open(os.path.join(HERE, "probe_vectors.json"), "rb").read().replace(b"\r\n", b"\n")).hexdigest()
    sel = json.loads(sel_bytes)
    run = sel["run"]
    stamps = sel["runs"][run]["SAMPLE"]

    P0, P40 = NR.arm_paths(n0_dir, ARM), NR.arm_paths(n40_dir, PAIRED_ARM)
    t0, t40 = O.load_testb(P0["testb"]), O.load_testb(P40["testb"])
    m0, m40 = NR.load_matched(P0["matched"]), NR.load_matched(P40["matched"])
    log0 = O.parse_log(P0["log"])
    pins = O.load_pins(os.path.join(n0_dir, "pins.jsonl"))
    restarts = 0
    pe = os.path.join(n0_dir, "process_exits.log")
    if os.path.exists(pe):
        restarts = sum(1 for line in open(pe) if (re.search(r"rc=(-?\d+)", line) and re.search(r"rc=(-?\d+)", line).group(1) != "0"))
    ab0 = O.load_abandon(P0["abandon"])
    ab40 = O.load_abandon(P40["abandon"])

    v = {"V1": row_v1(pins), "V2pp": row_v2pp(_load_probe(P0["probe"]), _load_probe(P40["probe"])),
         "V3": row_v3(O.load_run_csv(P0["run"]), restarts, log0["contained"]), "V4": row_v4(log0["readback"], sel_sha, probe_sha), "V5": row_v5(ab0, stamps)}

    present = [s for s in stamps if s in t0 and s in t40]
    missing = [s for s in stamps if s not in t0 or s not in t40]
    W = [t40[s]["W"] for s in present]
    M40 = [t40[s]["M"] for s in present]
    M0 = [t0[s]["M"] for s in present]
    K = G = 0
    kg_ok = True
    for s in present:
        a, b = m40.get(s), m0.get(s)
        if a is None or b is None or len(a) != t40[s]["M"] or len(b) != t0[s]["M"]:
            kg_ok = False
            continue
        K += len(b - a)
        G += len(a - b)
    consistency = {
        "all_sampled_cycles_present_in_N0_and_N40": (not missing, {"missing": len(missing)}),
        "wsjtx_W_identical_in_N0_and_N40": (all(t0[s]["W"] == t40[s]["W"] for s in present), {}),
        "M_equals_b1_plus_b2_matched": (all(c[s]["M"] == _sum_b(c[s], "b1", 1) + _sum_b(c[s], "b2", 1) for c in (t0, t40) for s in present), {}),
        "matched_index_sets_present_and_size_equal_M": (kg_ok, {}),
        "K_minus_G_equals_sum_d": (kg_ok and (K - G) == (sum(M0) - sum(M40)), {"K": K, "G": G}),
    }
    all_valid = all(ok for ok, _ in v.values()) and all(ok for ok, _ in consistency.values())
    failing = [k for k, (ok, _) in {**v, **consistency}.items() if not ok]
    result = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "O_SAFE_margin_pp": BAR_SAFE_MARGIN_PP,
              "n_sampled": len(stamps), "n_scored": len(present),
              "validity": {k: {"pass": ok, **d} for k, (ok, d) in v.items()}, "consistency": {k: {"pass": ok, **d} for k, (ok, d) in consistency.items()},
              "failing_rows": failing, "v6": "carried from the closed run: N40's A/A, 200/200 cycles identical"}
    if present:
        d = [b - a for a, b in zip(M40, M0)]
        net = NR.net_pp(W, M40, M0)
        lo, hi, nb = NR.ci(W, M40, M0)
        sW = float(sum(W))
        n40 = [_sum_b(t40[s], "b1", 0) + _sum_b(t40[s], "b2", 0) for s in present]
        n0 = [_sum_b(t0[s], "b1", 0) + _sum_b(t0[s], "b2", 0) for s in present]
        nc40 = [a - b for a, b in zip(n40, M40)]
        nc0 = [a - b for a, b in zip(n0, M0)]
        band = {}
        for b in NR.BANDS:
            row = {}
            for arm, c in (("N40", t40), ("N0", t0)):
                n = sum(c[s]["b1"][b][0] + c[s]["b2"][b][0] for s in present)
                m = sum(c[s]["b1"][b][1] + c[s]["b2"][b][1] for s in present)
                w = O.wilson(n - m, n)
                row[arm] = {"n": n, "not_confirmed": n - m, "rate": ((n - m) / n if n else None), "wilson95": [round(w[0], 4), round(w[1], 4)] if n else None}
            band[b] = row
        d_nc = sum(nc0) - sum(nc40)
        result["estimand"] = {"NET_0_pp": net, "ci95": [lo, hi], "block": NR.BLOCK_REGISTERED, "n_blocks": nb, "B": NR.B_RESAMPLES, "seed": NR.SEED,
                              "sum_W": int(sum(W)), "sum_M40": int(sum(M40)), "sum_M0": int(sum(M0))}
        result["cluster"] = NR.cluster_report(d)
        result["descriptive"] = {
            "K_confirmed_at_0_absent_at_40": K, "G_confirmed_at_40_absent_at_0": G, "K_minus_G": K - G,
            "not_confirmed_per_cycle": {"N40": sum(nc40) / len(present), "N0": sum(nc0) / len(present), "sumN40": int(sum(nc40)), "sumN0": int(sum(nc0)),
                                        "change_per_cycle": (sum(nc0) - sum(nc40)) / len(present)},
            "not_confirmed_by_ows_snr_band": band,
            "NET_by_batch_pp": {kind: 100.0 * sum(t0[s][kind][b][1] - t40[s][kind][b][1] for s in present for b in NR.BANDS) / sW for kind in ("b1", "b2")},
            "decodes_by_batch": {"N40": {k: int(sum(_sum_b(t40[s], k, 0) for s in present)) for k in ("b1", "b2")},
                                 "N0": {k: int(sum(_sum_b(t0[s], k, 0) for s in present)) for k in ("b1", "b2")}},
            "exchange_rate_extra_confirmed_per_extra_not_confirmed": ((sum(M0) - sum(M40)) / d_nc if d_nc != 0 else None),
            "abandoned_residual_passes": {"N40": sum(1 for s in present if ab40.get(s, {}).get("abandoned")), "N0": sum(1 for s in present if ab0.get(s, {}).get("abandoned"))}}
        if all_valid:
            result["verdict"] = verdict_row(lo, hi)
        else:
            result["verdict"] = "NO VERDICT"
            result["verdict_withheld_because"] = failing
    else:
        result["verdict"] = "NO VERDICT"
        result["verdict_withheld_because"] = failing or ["no scored cycles"]
    if results_dir:
        os.makedirs(results_dir, exist_ok=True)
        json.dump(result, open(os.path.join(results_dir, "n0_analysis.json"), "w"), indent=1, sort_keys=True, default=str)
    return result


def _load_probe(path):
    """Probe rows (numeric). Same format as the harness' --probe-out; shared with the COH-GAIN loader."""
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8").read().splitlines()[1:]:
        p = line.split(",")
        if len(p) >= 6 and p[2].lstrip("-").isdigit():
            out.append({"when": p[0], "vec": p[1], "rc": int(p[2]), "path": int(p[3]), "crc_ok": int(p[4]), "payload_match": p[5] == "1"})
    return out


def main(argv):
    import argparse
    art = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--n0", default=os.path.join(art, "rr_2026-10-06_nhard_rep_n0"))
    ap.add_argument("--n40", default=os.path.join(art, "rr_2026-10-06_nhard_rep"))
    ap.add_argument("--results", default=os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep"))
    a = ap.parse_args(argv)
    res = analyse(a.n0, a.n40, a.results)
    print(json.dumps({k: res[k] for k in ("verdict", "failing_rows", "estimand", "cluster") if k in res}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
