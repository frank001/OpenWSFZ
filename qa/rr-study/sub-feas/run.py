#!/usr/bin/env python3
"""SUB-FEAS orchestrator: population -> ROW 0 (0a-0i) -> Stage 1. Stops after
Stage 1 per spec sec.10 ("Stage 2 needs the Captain's go"). Numeric-only output
(HK-037/NFR-021) -- sub_feas_result.json never contains message text.
"""
from __future__ import annotations

import argparse
import json
import os
import time

import common

common.log_stdout_utf8()
import corpus
import row0
import bigfit
import stage1
import gl_dll_pin as DC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                     help="smoke-test subsample sizes, for pipeline validation only")
    args = ap.parse_args()

    os.makedirs(common.RUN_DIR, exist_ok=True)
    log_path = os.path.join(common.RUN_DIR, "run.log")
    log = common.make_logger(log_path)
    t_start = time.time()

    dll_path = os.path.join(common.RUN_DIR, "bin", "libft8_C3.dll")
    log("=== SUB-FEAS run start, quick=%s dll=%s ===" % (args.quick, dll_path))

    enc = corpus.Encoder(dll_path)
    pop = corpus.build_population(enc, log)

    result = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # Spec sec.3 timing probe, updated for Amendment 2's drift-extended fit + the
    # Amendment 3 parallelisation. Both measured live, 2026-09-27, on this exact
    # corpus/hardware, before this run:
    #   - fine_fit_with_drift: 60 rows sampled (seed 20260927), 232.5s -> 3.875 s/row
    #     (bigfit.fit_population(..., parallel=False)).
    #   - parallel speedup (bigfit.py's N_WORKERS, min(12, cpu_count()-1)): 40-row sample,
    #     157.9s serial -> 32.3s parallel = 4.9x, RESULT VERIFIED IDENTICAL to the
    #     serial run row-for-row (qa/rr-study/sub-feas/_verify_parallel.py; the one
    #     nominal "diff" was NaN != NaN on an identical L0-void row, not a real
    #     mismatch -- every non-NaN field matched exactly).
    # Amendment 3: thinning applies ONLY while it keeps ROW 0d satisfied
    # (|P_A|,|P_B| >= 1,000 each); otherwise run unthinned and disclose the
    # overrun -- a runtime convenience must never manufacture a validity FAIL.
    PROBE_SECONDS_PER_ROW = 3.875
    PROBE_N = 60
    PROBE_ELAPSED_S = 232.5
    PARALLEL_SPEEDUP = 4.9
    n_a, n_b, n_anchor, n_rr73 = len(pop["split_a"]), len(pop["split_b"]), len(pop["anchor_rows"]), pop["n_rr73"]
    anchor_wide_cost_factor = 1.65  # ROW 0g's OWN wide search: 401 vs 121 Δt steps (x3.31), smaller FFT (÷2)
    plain_fit_s_per_row = 1.727     # ROW 0f/0g still use the plain (non-drift) fine_fit
    bigfit_rows = n_a + n_b + n_anchor  # split A+B (L1/L2) + anchor-for-0h, all via bigfit.fit_population
    projected_s = (
        bigfit_rows * PROBE_SECONDS_PER_ROW / PARALLEL_SPEEDUP   # parallelised
        + n_anchor * plain_fit_s_per_row * anchor_wide_cost_factor  # ROW 0g's own wide search (serial)
        + n_rr73 * 2 * plain_fit_s_per_row          # ROW 0f, both encodings (serial)
        + (30 if args.quick else 400) * PROBE_SECONDS_PER_ROW    # ROW 0b, drift-extended (serial)
        + 60  # ROW 0a/0c, decode-only/no-fine-fit, small fixed overhead
    )
    k_thin = 1
    while projected_s / k_thin > 3 * 3600:
        k_thin += 1
    thinning_would_break_0d = k_thin > 1 and (n_a // k_thin < 1000 or n_b // k_thin < 1000)
    if thinning_would_break_0d:
        log("timing probe: k=%d would give n_A=%d n_B=%d, below ROW 0d's 1,000 bar -- "
            "Amendment 3: thinning yields to 0d, running UNTHINNED (overrun disclosed)"
            % (k_thin, n_a // k_thin, n_b // k_thin))
        k_thin = 1
    result["timing_probe"] = {
        "probe_n": PROBE_N, "probe_elapsed_s": PROBE_ELAPSED_S,
        "probe_s_per_row": PROBE_SECONDS_PER_ROW, "parallel_speedup": PARALLEL_SPEEDUP,
        "projected_total_s": projected_s, "projected_total_h": projected_s / 3600.0,
        "k": k_thin, "thinning_would_break_0d": thinning_would_break_0d,
    }
    log("timing probe: n=%d elapsed=%.1fs s_per_row=%.3f parallel_speedup=%.1fx -> "
        "projected_total=%.0fs (%.2fh) -> k=%d"
        % (PROBE_N, PROBE_ELAPSED_S, PROBE_SECONDS_PER_ROW, PARALLEL_SPEEDUP,
           projected_s, projected_s / 3600.0, k_thin))
    if k_thin > 1:
        def _thin(rows):
            cycles = sorted({r["cycle_ts"] for r in rows})
            keep = set(cycles[::k_thin])
            return [r for r in rows if r["cycle_ts"] in keep]
        pop["split_a"] = _thin(pop["split_a"])
        pop["split_b"] = _thin(pop["split_b"])
        log("timing probe: k=%d applied -> n_A=%d n_B=%d (post-thin)"
            % (k_thin, len(pop["split_a"]), len(pop["split_b"])))

    result["row0d"] = row0.row0d(pop, log)
    result["row0e"] = row0.row0e(dll_path, DC.PINNED_DLL_SHA256, log)
    result["row0i"] = row0.row0i(pop, log)

    dec = DC.load_decoder(common.RUN_DIR)
    n0a = 30 if args.quick else 300
    result["row0a"] = row0.row0a(dec, pop, log, n_sample=n0a)

    if args.quick:
        anchor_rows = pop["anchor_rows"][:60]
    else:
        anchor_rows = pop["anchor_rows"]
    result["row0g"] = row0.row0g({**pop, "anchor_rows": anchor_rows}, log)
    tau0_s = result["row0g"]["tau0_s"]

    result["row0f"] = row0.row0f(
        {**pop, "all_rows": pop["all_rows"][:300]} if args.quick else pop, tau0_s, log)

    n0bc_total = 45 if args.quick else 400
    n0bc_half = 20 if args.quick else 200
    result["row0b"] = row0.row0b(enc, log, n_total=n0bc_total)
    result["row0c"] = row0.row0c(log, n_noise_only=n0bc_half, n_with_signals=n0bc_half)

    log("=== ROW 0 table ===")
    for k in ("row0a", "row0b", "row0c", "row0d", "row0e", "row0f", "row0g", "row0i"):
        log("  %s: pass=%s" % (k, result[k]["pass"]))

    any_row0_fail = any(not result[k]["pass"] for k in
                         ("row0a", "row0b", "row0c", "row0d", "row0e", "row0f", "row0g", "row0i"))

    if any_row0_fail:
        log("=== ROW 0 FAIL -- STOP per spec sec.6 (a FAIL is not a result) ===")
        result["stage1"] = None
        result["row0h"] = None
    else:
        fit_rows_a = pop["split_a"][:400] if args.quick else pop["split_a"]
        fit_rows_b = pop["split_b"][:400] if args.quick else pop["split_b"]
        fit_rows_anchor = anchor_rows

        log("=== bigfit: split A (%d rows) ===" % len(fit_rows_a))
        fits_a = bigfit.fit_population(fit_rows_a, tau0_s, log, progress_every=100)
        log("=== bigfit: split B (%d rows) ===" % len(fit_rows_b))
        fits_b = bigfit.fit_population(fit_rows_b, tau0_s, log, progress_every=100)
        log("=== bigfit: anchor pool (%d rows, for 0h only) ===" % len(fit_rows_anchor))
        fits_anchor = bigfit.fit_population(fit_rows_anchor, tau0_s, log, progress_every=100)

        fits_all = fits_a + fits_b + fits_anchor
        result["row0h"] = row0.row0h(fits_all, log)

        rows_by_id = {r["row_id"]: r for r in (fit_rows_a + fit_rows_b + fit_rows_anchor)}

        if not result["row0h"]["pass"]:
            log("=== ROW 0h FAIL -- STOP per spec sec.6 ===")
            result["stage1"] = None
        else:
            wsel = stage1.select_w_star(fits_a, log)
            result["w_selection"] = wsel
            result["stage1"] = stage1.stage1_gate(fits_b, rows_by_id, wsel["w_star"], log)

    result["elapsed_s"] = time.time() - t_start
    out_path = common.RESULT_PATH if not args.quick else os.path.join(common.RUN_DIR, "sub_feas_result.quick.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str)
    log("=== wrote %s (elapsed=%.0fs) ===" % (out_path, result["elapsed_s"]))


if __name__ == "__main__":
    main()
