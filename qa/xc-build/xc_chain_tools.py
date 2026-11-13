#!/usr/bin/env python3
"""XC-BUILD PC chain helpers (spec arch/cross-cycle-prior Amendments 1 to 4).  QA tooling; no src/ or native/ change.  COUNTS AND NUMBERS ONLY are printed or written (HK-037):
the text-bearing files (nc.tsv, matched.csv) are compared line by line and never shown.
  te     <tr_dir> <out.json> [--dry] [--k-source tested|priors]   T_E from the TR arm: K, FA* = 0.021 / K, T_E = the smallest threshold with shadow exceedance <= FA*, V-TR-N.  Exit 0 ok, 3 V-TR-N fails (not --dry), 4 no shadow tests / K = 0.
  voff   <new_dir> <ref_dir> <out.json> [--nc-new F --nc-ref F --stamps FILE]   V-OFF: matchedbatch.csv and testb.csv line-identical, and the per-cycle (decodes, b1_n..b5_n) identical (timing excluded); with --nc-*: the published text rows (nc.tsv) of the listed stamps line-identical.  Exit 0 PASS, 5 FAIL.
  nccmp  <nc_a> <nc_b> <stamps_file> <out.json>   the published text rows of the listed stamps, line by line (the 100-cycle text leg).  Exit 0 PASS, 5 FAIL.
  check  <arm_dir> <nc_file> <want_rows> [--late-max FRAC] [--xc]   per-arm validity: rows, no exception, no negative decode count, b4_n column, text outputs non-empty; --late-max: late round abandoned fraction; --xc: the xc.csv counts line is present for every cycle.  Exit 0 ok, 6 invalid.
K SOURCE: the frozen analysis library (xb_lib.k_median, `7612378e`) takes K as the live templates TESTED per cycle; the spec text says 'live-prior count'.  Default 'tested' (the library); 'priors' uses priorsLive.  Both are recorded in the output."""
from __future__ import annotations

import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xb_lib as L  # noqa: E402

_NUM = lambda key: re.compile(r"\|" + key + r"=(-?\d+)")  # noqa: E731


def _xc_counts(path):
    """per-cycle {testedLive, priorsLive, testedShadow, shadowAbandoned, abandoned, outcome} from the stage's counts line (one row per cycle, numbers only)."""
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        if "outcome=" not in line:
            continue
        d = {"stamp": line.split(",", 1)[0]}
        for k in ("testedLive", "priorsLive", "testedShadow", "shadowAbandoned", "abandoned", "published", "detected", "shadowDetected"):
            m = _NUM(k).search(line)
            d[k] = int(m.group(1)) if m else 0
        m = re.search(r"\|outcome=([a-z-]+)", line)
        d["outcome"] = m.group(1) if m else "?"
        rows.append(d)
    return rows


def cmd_te(tr_dir, out, dry=False, k_source="tested"):
    probe = list(csv.DictReader(open(os.path.join(tr_dir, "probe.csv"), encoding="utf-8")))
    shadow = [float(r["s_e_star"]) for r in probe if r["kind"] == "shadow"]
    cyc = _xc_counts(os.path.join(tr_dir, "xc.csv"))
    ks = {"tested": L.k_median([c["testedLive"] for c in cyc]) if cyc else 0.0,
          "priors": L.k_median([c["priorsLive"] for c in cyc]) if cyc else 0.0}
    k = ks[k_source]
    res = {"k_source": k_source, "K_tested": ks["tested"], "K_priors": ks["priors"], "K": k, "cycles": len(cyc), "n_shadow_tests": len(shadow),
           "n_live_tests": sum(1 for r in probe if r["kind"] == "live"), "dry": dry}
    if k <= 0 or not shadow:
        res.update(T_E=None, FA_star=None, V_TR_N=False, reason="no shadow tests or K = 0")
        json.dump(res, open(out, "w"), indent=1)
        print("TE: no shadow tests or K = 0", res)
        return 4
    fa = L.fa_star(k)
    te = L.threshold_te(shadow, fa)
    alt = {s: (L.threshold_te(shadow, L.fa_star(v)) if v > 0 else None) for s, v in ks.items()}
    vtrn = L.v_tr_n(len(shadow), fa)
    sh_ab = sum(c["shadowAbandoned"] for c in cyc)
    sh_t = sum(c["testedShadow"] for c in cyc)
    res.update(T_E=te, FA_star=fa, V_TR_N=bool(vtrn), n_needed=3.0 / fa, T_E_if_tested=alt["tested"], T_E_if_priors=alt["priors"],
               shadow_abandoned=sh_ab, shadow_tested=sh_t, shadow_abandoned_fraction=(sh_ab / (sh_ab + sh_t)) if (sh_ab + sh_t) else 0.0,
               exceed_at_T_E=sum(1 for s in shadow if s >= te))
    json.dump(res, open(out, "w"), indent=1)
    print("TE:", {k_: res[k_] for k_ in ("K", "FA_star", "T_E", "n_shadow_tests", "n_needed", "V_TR_N", "T_E_if_tested", "T_E_if_priors", "shadow_abandoned_fraction")})
    return 0 if (vtrn or dry) else 3


def _lines(path):
    return open(path, encoding="utf-8", errors="replace").read().splitlines()


def _ndiff(a, b):
    return sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))


def _perm_cols(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    keep = [c for c in ("stamp", "decodes", "b1_n", "b2_n", "b3_n", "b4_n", "b5_n") if rows and c in rows[0]]
    return keep, {r["stamp"]: tuple(r[c] for c in keep) for r in rows}


def cmd_voff(new_dir, ref_dir, out, nc_new=None, nc_ref=None, stamps=None):
    res = {}
    for f in ("matchedbatch.csv", "testb.csv"):
        a, b = _lines(os.path.join(new_dir, f)), _lines(os.path.join(ref_dir, f))
        res[f] = {"lines_new": len(a), "lines_ref": len(b), "lines_differing": _ndiff(a, b)}
    kn, rn = _perm_cols(os.path.join(new_dir, "run.csv"))
    kr, rr = _perm_cols(os.path.join(ref_dir, "run.csv"))
    common = [c for c in kn if c in kr]
    idx_n = [kn.index(c) for c in common]
    idx_r = [kr.index(c) for c in common]
    stamps_all = sorted(set(rn) | set(rr))
    cyc_diff = sum(1 for s in stamps_all if s not in rn or s not in rr or tuple(rn[s][i] for i in idx_n) != tuple(rr[s][i] for i in idx_r))
    res["per_cycle_counts"] = {"columns": common, "cycles": len(stamps_all), "cycles_differing": cyc_diff}
    if nc_new and nc_ref:
        keep = set(open(stamps).read().split()) if stamps else None

        def sel(p):
            out_l = []
            for line in open(p, encoding="utf-8", errors="replace"):
                if keep is None or line.split("\t", 1)[0] in keep:
                    out_l.append(line)
            return out_l
        a, b = sel(nc_new), sel(nc_ref)
        res["nc_text_rows"] = {"rows_new": len(a), "rows_ref": len(b), "rows_differing": _ndiff(a, b), "stamps_listed": len(keep) if keep else None}
    ok = all(v.get("lines_differing", 0) == 0 for v in res.values() if isinstance(v, dict) and "lines_differing" in v) \
        and res["per_cycle_counts"]["cycles_differing"] == 0 and res.get("nc_text_rows", {}).get("rows_differing", 0) == 0 \
        and (res.get("nc_text_rows", {}).get("rows_new", 1) > 0)
    res["verdict"] = "PASS" if ok else "FAIL"
    json.dump(res, open(out, "w"), indent=1)
    print("VOFF:", json.dumps(res))
    return 0 if ok else 5


def cmd_nccmp(nc_a, nc_b, stamps, out):
    """the text leg of V-OFF: the published rows of the listed stamps, line by line, in order (counts printed, never text)."""
    keep = set(open(stamps).read().split())

    def sel(p):
        return [ln for ln in open(p, encoding="utf-8", errors="replace") if ln.split("\t", 1)[0] in keep]
    a, b = sel(nc_a), sel(nc_b)
    res = {"rows_a": len(a), "rows_b": len(b), "rows_differing": _ndiff(a, b), "stamps_listed": len(keep)}
    res["verdict"] = "PASS" if res["rows_differing"] == 0 and res["rows_a"] > 0 else "FAIL"
    json.dump(res, open(out, "w"), indent=1)
    print("NCCMP:", json.dumps(res))
    return 0 if res["verdict"] == "PASS" else 5


def cmd_check(arm, nc, want, late_max=None, xc=False):
    rows = list(csv.DictReader(open(os.path.join(arm, "run.csv"), encoding="utf-8")))
    bad = []
    if len(rows) != want:
        bad.append("rows %d != %d" % (len(rows), want))
    exc = sum(1 for r in rows if r.get("exception"))
    neg = sum(1 for r in rows if r.get("decodes", "0").lstrip("-").isdigit() and int(r["decodes"]) < 0)
    if exc:
        bad.append("exceptions in %d cycles" % exc)
    if neg:
        bad.append("negative decode counts in %d cycles" % neg)
    if rows and "b4_n" not in rows[0]:
        bad.append("no b4_n column (build lacks HasCohFb4)")
    if not os.path.isfile(nc) or os.path.getsize(nc) == 0:
        bad.append("nc.tsv empty")
    for f, mn in (("matchedbatch.csv", 2), ("outcomes.csv", 1)):
        p = os.path.join(arm, f)
        if not os.path.isfile(p) or len(_lines(p)) < mn:
            bad.append(f + " has no rows")
    info = {"rows": len(rows), "exceptions": exc, "negative": neg}
    if late_max is not None:
        lp = os.path.join(arm, "late.csv")
        lr = list(csv.DictReader(open(lp, encoding="utf-8"))) if os.path.isfile(lp) else []
        ab = sum(1 for r in lr if r.get("outcome") == "abandoned")
        started = sum(1 for r in lr if r.get("outcome") in ("ran", "abandoned"))
        frac = ab / len(lr) if lr else 1.0
        info.update(late_abandoned=ab, late_rows=len(lr), late_started=started, late_abandoned_fraction=frac)
        if frac > late_max:
            bad.append("late round abandoned in %.1f %% of cycles > %.1f %% (A4 capacity rule)" % (100 * frac, 100 * late_max))
    if xc:
        cyc = _xc_counts(os.path.join(arm, "xc.csv")) if os.path.isfile(os.path.join(arm, "xc.csv")) else []
        info["xc_cycles"] = len(cyc)
        if len(cyc) != want:
            bad.append("xc.csv counts lines %d != %d" % (len(cyc), want))
        info["xc_outcomes"] = {o: sum(1 for c in cyc if c["outcome"] == o) for o in sorted({c["outcome"] for c in cyc})}
        info["published"] = sum(c["published"] for c in cyc)
        info["shadow_detected"] = sum(c["shadowDetected"] for c in cyc)
    info["invalid"] = bad
    print("CHECK:", json.dumps(info))
    return 6 if bad else 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, a = argv[0], argv[1:]
    opt = lambda name, default=None: a[a.index(name) + 1] if name in a else default  # noqa: E731
    if cmd == "te":
        return cmd_te(a[0], a[1], dry="--dry" in a, k_source=opt("--k-source", "tested"))
    if cmd == "voff":
        return cmd_voff(a[0], a[1], a[2], opt("--nc-new"), opt("--nc-ref"), opt("--stamps"))
    if cmd == "nccmp":
        return cmd_nccmp(a[0], a[1], a[2], a[3])
    if cmd == "check":
        lm = opt("--late-max")
        return cmd_check(a[0], a[1], int(a[2]), float(lm) if lm is not None else None, "--xc" in a)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
