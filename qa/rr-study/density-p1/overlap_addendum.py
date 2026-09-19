#!/usr/bin/env python
"""DENSITY-P1 Stage 2 -- ADDENDUM 1 (REPORTING ONLY; gates nothing; cannot move the verdict).

Requested by the Architect, spec Sec.8.2 (arch/density 10e8f7fe), corrected to THREE cells: the non-excluded
real-suppression cells strong D12, strong D18.75 and E+15 D12. Computed for ALL 14 cells (cheap, same data).

Data: the run-A per-trial JSONL already gathered by the pre-registered harness (73ee2d4f). NO new decode, NO new data.
The overlap classification is density_p1.collateral_vs_residual VERBATIM (E's attenuated bins tone +-1 vs F's tone bin,
per data symbol); it is a function of the two FIXED messages and the delta only, so the overlap-bit count per trial is
fixed per delta (84 / 27 / 12 at delta 6.25 / 12 / 18.75).

Adds one view the Architect's question needs ("threshold or dose?"): per-trial RAW hard-decision bit errors of the pass-1
probe (of 174) vs whether the LDPC oracle decoded, so the overlap errors can be read against FEC capacity.
"""
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import density_p1 as D  # noqa: E402

OUT = os.path.join(HERE, "results", "stage2_overlap_addendum.json")


def per_trial(recs, true_bits):
    errs, hits = [], []
    for r in recs:
        s = r["P1"]["signs"]
        if s is None:
            continue
        errs.append(sum(int((s[i] == "1") != bool(true_bits[i])) for i in range(174)))
        hits.append(bool(r["P1"]["hit"]))
    return errs, hits


def main():
    cells, summ, recs, _r0d, _sha = D._load_run("A")
    _sh, dec, true_bits = D.make_instrument()
    out = {"note": "REPORTING ONLY. Run-A data of the pre-registered harness 73ee2d4f. No new decode.", "cells": {}}
    for c in cells:
        k = c["key"]
        cv = D.collateral_vs_residual(dec, c, recs[k], true_bits)
        errs, hits = per_trial(recs[k], true_bits)
        hit_e = [e for e, h in zip(errs, hits) if h]
        miss_e = [e for e, h in zip(errs, hits) if not h]
        out["cells"][k] = {
            "delta_hz": c["delta_hz"], "e_snr_db": c["e_snr_db"], "f_snr_db": c["f_snr_db"],
            "E_factor_median": summ[k]["E_factor_median"], "prod": summ[k]["prod"], "P1_hit_rate": summ[k]["P1"],
            "overlap_bits_per_trial": cv["overlap"]["bits"] / 100.0, "overlap": cv["overlap"], "no_overlap": cv["no_overlap"],
            "raw_errors_per_trial": {"n": len(errs), "median": st.median(errs), "min": min(errs), "max": max(errs),
                                     "median_when_decoded": (st.median(hit_e) if hit_e else None),
                                     "max_when_decoded": (max(hit_e) if hit_e else None),
                                     "min_when_not_decoded": (min(miss_e) if miss_e else None),
                                     "median_when_not_decoded": (st.median(miss_e) if miss_e else None),
                                     "n_decoded": len(hit_e), "n_not_decoded": len(miss_e)}}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
