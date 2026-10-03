"""#122 gate 4a diagnostics D1 and D2 (POST-REGISTRATION; ruling qa/rr-study/2026-10-03-1420-architect-122-gate4a-v2-fail-ruling.md).
Labelled as such everywhere. Neither changes the V2 verdict on P (FAIL, 1 074 of 1 075).

  D1: arm F re-run on P in a fresh process -> per cycle, the numeric (freq, dt, snr) multiset of the FINAL decode equals the original arm F's. N/N.
  D2: arm T re-run on P in a fresh process -> per cycle, the FINAL multiset equals the original arm T's, AND every aggregate row of the cycle
      (call counts, matched, spur, band, dt, shift: everything except the ms column) equals the original arm T's. N/N.
      (The original run did not write the early decodes' numeric multisets, so the early decodes are compared through those aggregate rows;
       the re-run writes them with --early-outcomes true for any later comparison.)
  Also reported, from the original outputs: the one failing cycle's F-versus-T difference, and the D3 lines when --diag-out was given.

  python compare_diag.py --orig _out/p --rerun _out/diag/p
Counts and booleans only; no message text exists in any file it reads.
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyse_trunc as A  # noqa: E402


def agg_rows(path: Path):
    d = defaultdict(list)
    for r in csv.DictReader(path.open(encoding="utf-8")):
        d[r["stamp"]].append((r["x"], r["row"], r["key"], r["n"], r["m"], r["exc"]))   # ms dropped on purpose
    return {k: sorted(v) for k, v in d.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", default="_out/p")
    ap.add_argument("--rerun", default="_out/diag/p")
    a = ap.parse_args()
    o, r = Path(a.orig), Path(a.rerun)
    rc = 0
    for arm in ("F", "T"):
        if not (r / f"outcomes_{arm}.csv").exists():
            print(f"D{1 if arm == 'F' else 2}: no re-run output for arm {arm}"); continue
        kind = f"final_{arm}"
        of, nf = A.read_outcomes(o / f"outcomes_{arm}.csv", kind), A.read_outcomes(r / f"outcomes_{arm}.csv", kind)
        stamps = A.Arm(o / f"trunc_{arm}.csv").stamps
        rstamps = A.Arm(r / f"trunc_{arm}.csv").stamps
        diff = [s for s in stamps if of.get(s, []) != nf.get(s, [])]
        label = "D1 (arm F re-run)" if arm == "F" else "D2 (arm T re-run)"
        print(f"{label}, POST-REGISTRATION: cycles re-run {len(rstamps)} of {len(stamps)}; final multiset identical to the original in "
              f"{len(stamps) - len(diff)}/{len(stamps)}" + (f"; differing stamps: {diff}" if diff else ""))
        if arm == "T":
            ao, an = agg_rows(o / "trunc_T.csv"), agg_rows(r / "trunc_T.csv")
            bad = [s for s in stamps if ao.get(s) != an.get(s)]
            print(f"D2 aggregate rows (early decodes' counts, matches, spur, band, dt, shift) identical in {len(stamps) - len(bad)}/{len(stamps)}"
                  + (f"; differing stamps: {bad}" if bad else ""))
        if diff:
            rc = 1
    # the original failing cycle, numerically
    of, ot = A.read_outcomes(o / "outcomes_F.csv", "final_F"), A.read_outcomes(o / "outcomes_T.csv", "final_T")
    for s in sorted(set(of) | set(ot)):
        if of.get(s, []) != ot.get(s, []):
            print(f"original V2 failure {s}: only in F {[x for x in of.get(s, []) if x not in ot.get(s, [])]}; "
                  f"only in T {[x for x in ot.get(s, []) if x not in of.get(s, [])]}")
    for arm in ("F", "T"):
        p = r / f"diag_{arm}.csv"
        if p.exists():
            print(f"D3 (arm {arm}), booleans and counts only:")
            print(p.read_text(encoding="utf-8").rstrip())
    return rc


if __name__ == "__main__":
    sys.exit(main())
