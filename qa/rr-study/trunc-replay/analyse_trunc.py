"""#122 gate 4a -- the pre-registered rows V0-V5, the outputs and the predictions TR1-TR6, as code (spec sections 5 and 8).

Reads only the numeric CSVs the harness wrote under _out/<corpus>/ (counts and numbers; no message text exists in them).
If any V0-V3 row FAILS, NO catch figure is printed (spec section 5): the report names the row and stops.
V4 is replaced by V4' (Amendment 1, 2026-10-03 13:53Z): per corpus, a FAIL withholds THAT corpus's catch figures.
The old V4 and C(0.5), C(4.0), D with its CI are always printed, PASS or FAIL.

  python analyse_trunc.py [--out _out] [--sel ../results/2026-10-03-122-gate4a-truncation-replay]
"""
import argparse
import csv
import hashlib
import json
import random
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

CORPORA = ["p", "r", "x17", "x80"]
GRID = [0.5, 1.0, 1.5, 2.0, 2.5]
CONTROL = 4.0
PARENT_SHA = "55a951c86147e92a8262be9d84ffd29362ecd7b63995f62caa7981bd53c977cf"
DLL_SHA = "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"
V4_MARGIN = 0.20          # the ORIGINAL V4, superseded by Amendment 1; reported, not used
V4P_C4_MAX = 0.98         # V4'(i): C(4.0) <= 0.98 (an uncut window gives exactly 1.000 at every x)
V5_TOLERANCE_S = 0.10
BLOCK = 10                # cycles per bootstrap block
BOOT_B = 10_000
BOOT_SEED = 20261003
XSTAR_C, XSTAR_SUNC = 0.90, 0.10
BANDS, DTBINS = ["A", "B", "C", "D"], ["<=0", "0.0-0.5", "0.5-1.0", "1.0-1.5", "1.5-2.0", "2.0-2.5", ">2.5"]


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class Arm:
    """One arm's CSV, indexed per cycle (ascending stamp order = file order)."""

    def __init__(self, path: Path):
        self.rows = list(csv.DictReader(path.open(encoding="utf-8")))
        self.stamps = []
        for r in self.rows:
            if r["row"] == "final":
                self.stamps.append(r["stamp"])
        self.by = defaultdict(list)
        for r in self.rows:
            self.by[(r["stamp"], r["x"], r["row"])].append(r)
        self.exceptions = sum(1 for r in self.rows if r["exc"])

    def n_final(self, s):
        return int(self.by[(s, "0.0", "call")][0]["n"])

    def call_ms(self, x):
        return [float(r["ms"]) for r in self.rows if r["row"] == "call" and r["x"] == f"{x:.1f}"]


def read_outcomes(path: Path, kind: str):
    d = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        p = line.split(",")
        if len(p) >= 6 and p[1] == kind:
            d[p[0]].append((int(p[3]), p[4], int(p[5])))
    return {k: sorted(v) for k, v in d.items()}


def boot(stamps, num, den, rng):
    """Non-overlapping block bootstrap (blocks of BLOCK consecutive cycles, last partial block kept), numerator and
    denominator resampled together. Returns the 95 % percentile CI of sum(num)/sum(den)."""
    blocks = [stamps[i:i + BLOCK] for i in range(0, len(stamps), BLOCK)]
    bn = [sum(num.get(s, 0) for s in b) for b in blocks]
    bd = [sum(den.get(s, 0) for s in b) for b in blocks]
    k, out = len(blocks), []
    for _ in range(BOOT_B):
        idx = [rng.randrange(k) for _ in range(k)]
        d = sum(bd[i] for i in idx)
        if d:
            out.append(sum(bn[i] for i in idx) / d)
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out)) - 1]


def boot_diff(stamps, num_a, num_b, den, rng):
    """95 % percentile CI of D = sum(num_a)/sum(den) - sum(num_b)/sum(den): the same blocks as boot(), the three
    sums resampled together (V4' (ii), Amendment 1)."""
    blocks = [stamps[i:i + BLOCK] for i in range(0, len(stamps), BLOCK)]
    ba = [sum(num_a.get(s, 0) for s in b) for b in blocks]
    bb = [sum(num_b.get(s, 0) for s in b) for b in blocks]
    bd = [sum(den.get(s, 0) for s in b) for b in blocks]
    k, out = len(blocks), []
    for _ in range(BOOT_B):
        idx = [rng.randrange(k) for _ in range(k)]
        d = sum(bd[i] for i in idx)
        if d:
            out.append((sum(ba[i] for i in idx) - sum(bb[i] for i in idx)) / d)
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out)) - 1]


def v4_rows(stamps, num05, num4, den):
    """V4' (replaces V4, Amendment 1): PASS iff (i) C(4.0) <= 0.98 AND (ii) the CI lower bound of D = C(0.5) - C(4.0) > 0.
    Also returns the superseded original V4 (reported, not used). Fresh Random(BOOT_SEED) per call: same blocks and seed."""
    total = sum(den.values())
    c05, c4 = sum(num05.values()) / total, sum(num4.values()) / total
    lo, hi = boot_diff(stamps, num05, num4, den, random.Random(BOOT_SEED))
    return {"c05": c05, "c4": c4, "d": c05 - c4, "d_lo": lo, "d_hi": hi,
            "i": c4 <= V4P_C4_MAX, "ii": lo > 0, "pass": c4 <= V4P_C4_MAX and lo > 0,
            "old_v4_pass": c4 <= c05 - V4_MARGIN}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_out")
    ap.add_argument("--sel", default="../results/2026-10-03-122-gate4a-truncation-replay")
    ap.add_argument("--allow-incomplete", action="store_true", help="dry-run on a partial output; never for the report")
    a = ap.parse_args()
    out, sel = Path(a.out), Path(a.sel)
    frozen = json.loads((sel / "selection_shas.json").read_text(encoding="utf-8"))
    fails, F, T = [], {}, {}

    # ---- V0 inputs, V3 stability, V2 undisturbed final decode, V1 is asserted in-process (a failure exits 3) ----
    for c in CORPORA:
        d = out / c
        if not (d / "trunc_F.csv").exists() or not (d / "trunc_T.csv").exists():
            fails.append(f"V0 {c}: output missing"); continue
        F[c], T[c] = Arm(d / "trunc_F.csv"), Arm(d / "trunc_T.csv")
        want = json.loads((sel / f"selection_{c}.json").read_text(encoding="utf-8"))["runs"]
        stamps = list(next(iter(want.values()))["ALL"])
        if lf_sha(sel / f"selection_{c}.json") != frozen[c]:
            fails.append(f"V0 {c}: selection file SHA differs from the frozen SHA")
        if c == "p" and json.loads((sel / "selection_p.json").read_text(encoding="utf-8"))["parent_sha256_lf"] != PARENT_SHA:
            fails.append("V0 p: parent SHA")
        for arm_name, arm in (("F", F[c]), ("T", T[c])):
            if arm.stamps != stamps and not a.allow_incomplete:
                fails.append(f"V0 {c}-{arm_name}: cycles done {len(arm.stamps)} != frozen list {len(stamps)}")
            log = (d / f"log_{arm_name}.txt").read_text(encoding="utf-8", errors="replace")
            marks = re.findall(r"# readback (start|end) .*?subtractionEnabled=(\w+).*?dllSha256=(\w+)", log)
            ok = len(marks) == 2 and all(m[1] == "False" and m[2] == DLL_SHA for m in marks)
            if not ok or "nhard=40" not in log:
                fails.append(f"V0 {c}-{arm_name}: readback (flag OFF / nhard 40 / DLL SHA) at start and end")
            if (d / f"selection_sha_{arm_name}.txt").read_text().strip() != frozen[c]:
                fails.append(f"V0 {c}-{arm_name}: selection SHA at run time differs")
            ex = (d / f"exit_{arm_name}.txt").read_text().strip()
            if arm.exceptions or ex != "0" or "FATAL" in log or "WARN-TEMPLATE" in log:
                fails.append(f"V3 {c}-{arm_name}: exceptions={arm.exceptions} exit={ex}")
        of, ot = read_outcomes(d / "outcomes_F.csv", "final_F"), read_outcomes(d / "outcomes_T.csv", "final_T")
        bad = [s for s in F[c].stamps if of.get(s, []) != ot.get(s, [])]
        if bad:
            fails.append(f"V2 {c}: {len(bad)}/{len(F[c].stamps)} cycles differ (PASS iff N/N)")

    def catch(c, x):
        t, f = T[c], F[c]
        num = {s: int(t.by[(s, f"{x:.1f}", "matched")][0]["n"]) for s in t.stamps}
        den = {s: f.n_final(s) for s in f.stamps}
        return num, den

    if fails:
        print("VALIDITY FAILED; no catch figure is reported:")
        for f in fails: print("  FAIL", f)
        return 1

    # ---- V4' positive control (Amendment 1): always reported, PASS or FAIL; a FAIL withholds that corpus only ----
    active, old_v4 = [], {}
    for c in CORPORA:
        num4, den = catch(c, CONTROL); num05, _ = catch(c, 0.5)
        r = v4_rows(F[c].stamps, num05, num4, den)
        print(f"V4' {c}: {'PASS' if r['pass'] else 'FAIL'}  C(0.5)={r['c05']:.3f}  C(4.0)={r['c4']:.3f}  "
              f"D={r['d']:.3f} [{r['d_lo']:.3f}, {r['d_hi']:.3f}]  (i) C(4.0)<=0.98: {r['i']}  (ii) CI lower bound>0: {r['ii']}")
        print(f"     V4 as first registered, C(4.0)<=C(0.5)-0.20: {'PASS' if r['old_v4_pass'] else 'FAIL'} "
              "(superseded by Amendment 1; reported, not used)  |  V1 (cut exactness) is asserted in-process: the run exited 0")
        old_v4[c] = r["old_v4_pass"]
        if r["pass"]: active.append(c)
        else: print(f"     {c}: catch figures WITHHELD (V4' FAIL)")
    if not active:
        return 1

    rng = random.Random(BOOT_SEED)
    # ---- V5 window alignment ----
    med = {c: statistics.median(float(r["key"]) for r in F[c].rows if r["row"] == "v5") for c in CORPORA}
    v5 = {c: (c == "p") or abs(med[c] - med["p"]) <= V5_TOLERANCE_S for c in CORPORA}
    print("V5 median DT(OpenWSFZ - WSJT-X) of corroborated pairs, arm F:", {c: round(med[c], 3) for c in active})
    for c in active: print(f"  V5 {c}: {'PASS' if v5[c] else f'FAIL (offset differs from P by {med[c] - med['p']:+.2f} s; x not comparable)'}")

    C, S = {}, {}
    for c in active:
        den = {s: F[c].n_final(s) for s in F[c].stamps}
        print(f"\n=== corpus {c}: {len(F[c].stamps)} cycles, {sum(den.values())} arm-F decodes ===")
        print("x      C(x)   [95% CI]          S_corr/100  S_unc/100  SNRshift(med)  t(x) med/p95 ms")
        for x in GRID + [CONTROL]:
            num, _ = catch(c, x)
            lo, hi = boot(F[c].stamps, num, den, rng)
            cv = sum(num.values()) / sum(den.values())
            sp = {k: sum(int(r["n"]) for s in T[c].stamps for r in T[c].by[(s, f"{x:.1f}", "spur")] if r["key"] == k) for k in ("corr", "unc")}
            sc, su = 100 * sp["corr"] / sum(den.values()), 100 * sp["unc"] / sum(den.values())
            C[(c, x)], S[(c, x)] = cv, su
            sh = [int(r["key"]) for r in T[c].rows if r["row"] == "shift" and r["x"] == f"{x:.1f}"]
            ms = sorted(T[c].call_ms(x))
            print(f"{x:<5}  {cv:.3f}  [{lo:.3f}, {hi:.3f}]   {sc:9.2f}  {su:9.2f}  {statistics.median(sh) if sh else float('nan'):>11}  {statistics.median(ms):.0f}/{ms[int(0.95 * len(ms)) - 1]:.0f}")
        ms0 = sorted(F[c].call_ms(0.0))
        t0 = statistics.median(ms0)
        print(f"t(0) full decode median/p95 ms: {t0:.0f}/{ms0[int(0.95 * len(ms0)) - 1]:.0f}")
        for x in GRID:
            tx = statistics.median(T[c].call_ms(x))
            print(f"  G({x}) = x + t(0) - t(x) = {x + (t0 - tx) / 1000:.2f} s (design estimate, this CPU, one process, no other load)")
        for x in (1.0, 2.0):
            for kind, labels in (("band", BANDS), ("dt", DTBINS)):
                cells = []
                for lab in labels:
                    n = sum(int(r["n"]) for s in T[c].stamps for r in T[c].by[(s, f"{x:.1f}", kind)] if r["key"] == lab)
                    m = sum(int(r["m"]) for s in T[c].stamps for r in T[c].by[(s, f"{x:.1f}", kind)] if r["key"] == lab)
                    cells.append(f"{lab}: {m}/{n}" + (f"={m / n:.2f}" if n else ""))
                print(f"  C({x}) by {kind}: " + "; ".join(cells))

    xstar = {c: max((x for x in GRID if C[(c, x)] >= XSTAR_C and S[(c, x)] <= XSTAR_SUNC), default=None) for c in active}
    print("\nx* (largest grid x with C>=0.90 and S_unc<=0.10 per 100), descriptive:", xstar, "(P is the design point; R beside it)")

    print("\nPredictions (scored at the Architect's ruling):")
    have = lambda *cs: all(c in active for c in cs)
    if have("p"):
        print("TR1 C_P(1.0)>=0.85:", C[("p", 1.0)] >= 0.85, round(C[("p", 1.0)], 3))
        print("TR2 C_P(2.0) in [0.55,0.85] (as registered):", 0.55 <= C[("p", 2.0)] <= 0.85, round(C[("p", 2.0)], 3))
        print("TR3 S_unc_P(1.0)<=0.50:", S[("p", 1.0)] <= 0.50, round(S[("p", 1.0)], 3))
    print("TR4 |C_P(1.0)-C_R(1.0)|<=0.05:", (abs(C[("p", 1.0)] - C[("r", 1.0)]) <= 0.05) if have("p", "r") else "n/a (P or R withheld)")
    # TR5 is the Architect's prediction and stays AS REGISTERED ("V0-V4 all pass the first time"), scored against the ORIGINAL V4
    # (Amendment 1 leaves the predictions unchanged). V4' is shown beside it as a note.
    print("TR5 V0-V4 all pass the first time (original V4):", all(old_v4.values()),
          {c: old_v4[c] for c in CORPORA}, "| note: V4' passed on", sorted(active))
    for c in ("x17", "x80"):
        print(f"TR6 {c}:", (abs(C[(c, 1.0)] - C[("p", 1.0)]) <= 0.08) if have(c, "p") and v5[c] else "n/a (withheld or V5 failed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
