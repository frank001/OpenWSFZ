#!/usr/bin/env python3
"""Route B2 Phase B -- B-pos-A, the lattice-position arm.

Spec: qa/rr-study/2026-08-21-1330-architect-to-qa-spec-b-pos-a-lattice-position-arm.md
Authorised by the Captain 2026-08-21 ("go with B-pos-A now with B3 held").

STATUS (spec Sec.0): DIAGNOSTIC ONLY. Defines NO ROW, NO PASS/FAIL, NO f_net, NO gate.
ROW 0g is not re-read, re-metriced or amended -- it stands FIRED, task 4.3 stays VOID,
ROW 3 is not declared, Route B2 is not dead. No src/native edit, no DLL rebuild, no push,
no merge -- HK-011 not engaged (ft8_coherent_llr_at already takes (freq_hz, time_offset_s)
as floats and snaps internally; the per-path position search is a caller-side loop, spec
Sec.2.3). This arm measures what design.md D1 costs; it does NOT authorise changing D1.
B3 (out_diag) is HELD, not killed -- not built here.

Question (spec Sec.1): Phase A's A3 control (shared anchor, zero injected residual)
already read d_clean=-61.0 against ROW 0g-2's real d_real=-67.0 CI95[-71,-65] -- i.e. the
SHARED-POSITION mandate itself, not any injected residual, carries ~90% of the collapse.
This arm asks what that costs on the real population by letting each path read at its own
best lattice point instead of a shared one.

Design (spec Sec.3): reuses ROW 0g-2's population/sample/seed/anchor VERBATIM (HK-018) --
build_p_hit_population + deterministic_sample(N=200, SEED=20260821), anchor
round(anchor_freq_hz) / anchor_dt + STAGE2_ANCHOR_OFFSET_S. For each control-delivered row,
sweeps a 7 (time, m=-3..+3, quantum 0.08s) x 3 (freq, n=-1..+1, quantum 3.125Hz) = 21-cell
grid on BOTH paths. Primary statistic (Sec.3.2) is a GLOBAL per-path best cell chosen by
cluster-median n_err, deliberately NOT a per-row argmin (winner's-curse biased toward
"coherent recovers" -- rationale in Sec.3.2, reproduced in choose_best_cell()'s docstring
below). Per-row argmin is still computed as the Sec.5.1 PRIMARY shape readout (is the
coherent path's own displacement CONSTANT across rows, or SCATTERED?), with the bias named
alongside it every time it is reported (spec Sec.3.2 last paragraph, Sec.5.1 last line).

Two mechanical preconditions (Sec.4), evaluated BEFORE any headline number, STOP the run:
  P1  the (m=0,n=0) cell must reproduce ROW 0g-2 EXACTLY (n_delivered=193,
      n_clusters_delivered=190, d_control=-67.0). Any deviation -> STOP, do not proceed.
  P2  the chosen global optimum must be INTERIOR, not on the swept m boundary (HK-026).
      If it lands on the boundary, widen m by 2 quanta each side and re-sweep (only the
      NEW cells are computed -- per-row/per-cell results are memoised). Capped at
      MAX_WIDEN_STEPS; if still unresolved, reported as such, not silently accepted.

NFR-021: message text touches this module only in-process (ex.true_codeword calls) and is
never written to any row dict, JSON field, or log line emitted here -- only `ts` and
integer bit-error counts are retained per row.
"""
from __future__ import annotations

import os
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))
_SYNTH_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
sys.path.insert(0, _SYNTH_ROOT)
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
from extract_llrs_ctypes import FTX_LDPC_N, hard_decision_ber  # noqa: E402
from run_stage1 import DEFAULT_DLL_PATH, WavCache  # noqa: E402
from plive_population import PRIMARY_CORPUS, build_p_hit_population, corpus_paths  # noqa: E402
from run_stage1r import deterministic_sample  # noqa: E402 -- seeded, sort-stabilised (HK-018)
from n1_stats import cluster_bootstrap_median_diff  # noqa: E402 -- reused verbatim (HK-018)

import r2_population as R2POP  # noqa: E402
from coherent_llr_ctypes import CoherentExtractLLRs, CURRENT_DLL_SHA256, CURRENT_SHIM_VERSION  # noqa: E402

SEED = 20260821  # SAME seed ROW 0g-2 used -- spec Sec.3.1: reuse verbatim, never re-derive
N_REAL_SAMPLE = 200

TIME_QUANTUM_S = 0.08      # spec Sec.2.1, measured this session by probing the merged binary
FREQ_QUANTUM_HZ = 3.125    # spec Sec.2.1, measured this session by probing the merged binary
M_RANGE_INITIAL = tuple(range(-3, 4))   # 7 points, +/-0.24s (spec Sec.3.1)
N_RANGE = tuple(range(-1, 2))            # 3 points, +/-3.125Hz -- physical cap, NEVER widened
MAX_WIDEN_STEPS = 3                      # P2 auto-widen cap (+2 quanta each side per step)

# ROW 0g-2's own result (row0g_report.json["row_0g2"]) -- the (m=0,n=0) cell is BY
# CONSTRUCTION the identical computation, spec Sec.4 P1.
CONTROL_N_DELIVERED = 193
CONTROL_N_CLUSTERS = 190
CONTROL_D = -67.0


def _n_err(llr, true_bits) -> int:
    """Same convention throughout this thread: ber is an exact k/174 by construction."""
    return int(round(hard_decision_ber(llr, true_bits) * FTX_LDPC_N))


def _cell_key(m: int, n: int) -> str:
    return "%d,%d" % (m, n)


def _extract_cell(ex: CoherentExtractLLRs, pcm, freq_int: float, corrected_dt: float,
                   m: int, n: int, true_bits):
    """Returns (n_err_grid_or_None, n_err_coh_or_None) at grid cell (m, n), m in time
    quanta, n in frequency quanta, relative to (freq_int, corrected_dt)."""
    freq_hz = freq_int + n * FREQ_QUANTUM_HZ
    time_offset_s = corrected_dt + m * TIME_QUANTUM_S
    rc_g, llr_g = ex.extract_at(pcm, freq_hz, time_offset_s)
    rc_c, llr_c = ex.coherent_extract_at(pcm, freq_hz, time_offset_s)
    ne_g = _n_err(llr_g, true_bits) if (rc_g == 0 and llr_g is not None) else None
    ne_c = _n_err(llr_c, true_bits) if (rc_c == 0 and llr_c is not None) else None
    return ne_g, ne_c


# =====================================================================================
# population / control-cell delivery (mirrors ROW 0g-2's own drop logic exactly, Sec.4 P1)
# =====================================================================================

def build_sample_and_deliver(ex: CoherentExtractLLRs, log) -> tuple[list[dict], dict, int]:
    full_p_hit = build_p_hit_population(PRIMARY_CORPUS)
    sample = deterministic_sample(full_p_hit, N_REAL_SAMPLE, SEED)
    wav_cache = WavCache(corpus_paths(PRIMARY_CORPUS)["wsjtx_wav_dir"])
    log("  sampled %d rows (seed=%d) from a %d-row/%d-cluster population"
        % (len(sample), SEED, len(full_p_hit), len({r["ts"] for r in full_p_hit})))

    delivered: list[dict] = []
    drop_reasons: dict[str, int] = {}

    def _drop(reason: str) -> None:
        drop_reasons[reason] = drop_reasons.get(reason, 0) + 1

    for row in sample:
        true_bits = ex.true_codeword(row["message"])
        if true_bits is None:
            _drop("no_true_codeword")
            continue
        try:
            pcm = wav_cache.get(row["ts"])
        except FileNotFoundError:
            _drop("no_wav")
            continue

        freq_int = float(round(row["anchor_freq_hz"]))
        corrected_dt = float(row["anchor_dt"]) + R2POP.STAGE2_ANCHOR_OFFSET_S

        ne_g0, ne_c0 = _extract_cell(ex, pcm, freq_int, corrected_dt, 0, 0, true_bits)
        if ne_g0 is None:
            _drop("grid_extract_fail_control")
            continue
        if ne_c0 is None:
            _drop("coh_extract_fail_control")
            continue

        delivered.append({
            "ts": row["ts"], "pcm": pcm, "true_bits": true_bits,
            "freq_int": freq_int, "corrected_dt": corrected_dt,
            "cells": {(0, 0): (ne_g0, ne_c0)},
        })

    return delivered, drop_reasons, len(sample)


def check_p1(delivered: list[dict], log) -> tuple[bool, int, int, float, dict]:
    n_delivered = len(delivered)
    n_clusters = len({d["ts"] for d in delivered})
    rows_for_boot = [{"ts": d["ts"],
                       "d_ber": float(d["cells"][(0, 0)][0] - d["cells"][(0, 0)][1])}
                      for d in delivered]
    boot = cluster_bootstrap_median_diff(rows_for_boot)
    d_control = boot["point_estimate"]
    log("  P1 control cell (m=0,n=0): n_delivered=%d n_clusters=%d d_control=%.3f"
        % (n_delivered, n_clusters, d_control))
    ok = (n_delivered == CONTROL_N_DELIVERED and n_clusters == CONTROL_N_CLUSTERS
          and abs(d_control - CONTROL_D) < 1e-9)
    return ok, n_delivered, n_clusters, d_control, boot


# =====================================================================================
# grid sweep + cell selection
# =====================================================================================

def sweep_cells(ex: CoherentExtractLLRs, delivered: list[dict], m_range, n_range, log) -> float:
    """Extracts both paths at every (m, n) in m_range x n_range for every delivered row,
    for cells not already memoised in d["cells"] (so a P2 widen only pays for the NEW
    cells)."""
    todo = [(m, n) for m in m_range for n in n_range]
    t0 = time.time()
    cell_fail_counts: dict[tuple[int, int], int] = {}
    n_calls = 0
    for d in delivered:
        for m, n in todo:
            if (m, n) in d["cells"]:
                continue
            ne_g, ne_c = _extract_cell(ex, d["pcm"], d["freq_int"], d["corrected_dt"], m, n,
                                        d["true_bits"])
            d["cells"][(m, n)] = (ne_g, ne_c)
            n_calls += 1
            if ne_g is None or ne_c is None:
                cell_fail_counts[(m, n)] = cell_fail_counts.get((m, n), 0) + 1
    elapsed = time.time() - t0
    log("  swept %d new row-cells in %.1fs" % (n_calls, elapsed))
    if cell_fail_counts:
        log("  extraction failures by cell (row dropped from THAT cell only): %s"
            % {_cell_key(*k): v for k, v in sorted(cell_fail_counts.items())})
    return elapsed


def cell_cluster_median(delivered: list[dict], m: int, n: int, which: int):
    """which: 0 = grid path, 1 = coherent path. 'Cluster-median' (spec Sec.3.2): first the
    per-cluster (per ts) median n_err at this cell (collapsing any rows sharing a ts), then
    the median of those per-cluster medians -- a row sharing a cycle with another row does
    not get double weight (HK-021(i))."""
    by_ts: dict[str, list[int]] = {}
    for d in delivered:
        val = d["cells"].get((m, n))
        if val is None or val[which] is None:
            continue
        by_ts.setdefault(d["ts"], []).append(val[which])
    if not by_ts:
        return None, 0
    per_cluster_medians = [st.median(vals) for vals in by_ts.values()]
    return float(st.median(per_cluster_medians)), len(by_ts)


def choose_best_cell(delivered: list[dict], m_range, n_range, which: int, log, label: str):
    """Chooses the SINGLE global cell minimising cluster-median n_err for one path, pooled
    across the whole sample -- spec Sec.3.2's deliberate design call, NOT a per-row argmin.
    Rationale (spec Sec.3.2, reproduced here so the choice travels with the code): a per-row
    minimum over 21 noisy cells is winner's-curse biased, and more so for whichever path's
    response varies more across position -- Phase A's A2 says that is the coherent path
    (narrow/peaked vs. grid's wide plateau), so a per-row argmin would be biased PRECISELY
    toward "coherent recovers", the conclusion that would push toward amending D1. A single
    cell chosen from 190 clusters over 21 candidates carries negligible selection bias, and
    is also the more architecturally honest question: a production fix would be a fixed
    convention offset, not a per-signal search."""
    best = None  # (median, m, n, n_clusters)
    table: dict[tuple[int, int], tuple] = {}
    for m in m_range:
        for n in n_range:
            med, nclust = cell_cluster_median(delivered, m, n, which)
            table[(m, n)] = (med, nclust)
            if med is None:
                continue
            if best is None or med < best[0]:
                best = (med, m, n, nclust)
    log("  %s global best cell: m=%d n=%d cluster-median n_err=%.3f (n_clusters=%d)"
        % (label, best[1], best[2], best[0], best[3]))
    return best, table


def widen_if_needed(ex: CoherentExtractLLRs, delivered: list[dict], m_range, log):
    """Spec Sec.4 P2 (HK-026): if either path's chosen m lands on the swept boundary, the
    grid measured its own edge, not the path's optimum. Widens m by 2 quanta each side and
    re-sweeps (memoised -- only new cells cost anything), up to MAX_WIDEN_STEPS. n is NEVER
    widened (physical cap, spec Sec.3.1)."""
    current = list(m_range)
    steps = 0
    while True:
        best_g, table_g = choose_best_cell(delivered, current, N_RANGE, 0, log, "grid")
        best_c, table_c = choose_best_cell(delivered, current, N_RANGE, 1, log, "coherent")
        boundary = max(abs(current[0]), abs(current[-1]))
        hit_g = abs(best_g[1]) == boundary
        hit_c = abs(best_c[1]) == boundary
        if not (hit_g or hit_c):
            return current, steps, best_g, table_g, best_c, table_c, False
        if steps >= MAX_WIDEN_STEPS:
            log("  P2: boundary optimum PERSISTS after %d widen step(s) (grid_hit=%s "
                "coh_hit=%s) -- capping here, ESCALATE rather than silently accept."
                % (steps, hit_g, hit_c))
            return current, steps, best_g, table_g, best_c, table_c, True
        steps += 1
        new_lo, new_hi = current[0] - 2, current[-1] + 2
        log("  P2 FIRES: boundary optimum at |m|=%d (grid_hit=%s coh_hit=%s) -- widening m "
            "to [%d, %d] and re-sweeping (step %d/%d)."
            % (boundary, hit_g, hit_c, new_lo, new_hi, steps, MAX_WIDEN_STEPS))
        current = list(range(new_lo, new_hi + 1))
        sweep_cells(ex, delivered, current, N_RANGE, log)


def compute_d_global(delivered: list[dict], cell_g: tuple[int, int], cell_c: tuple[int, int],
                      log) -> tuple[dict, int]:
    rows = []
    n_missing = 0
    for d in delivered:
        vg = d["cells"].get(cell_g)
        vc = d["cells"].get(cell_c)
        if vg is None or vc is None or vg[0] is None or vc[1] is None:
            n_missing += 1
            continue
        rows.append({"ts": d["ts"], "d_ber": float(vg[0] - vc[1])})
    if n_missing:
        log("  d_global pairing: %d/%d delivered rows missing an extraction at the chosen "
            "cells, excluded from the paired statistic" % (n_missing, len(delivered)))
    boot = cluster_bootstrap_median_diff(rows)
    return boot, len(rows)


# =====================================================================================
# 5.1 primary readout -- per-row argmin shape (CONSTANT vs SCATTERED)
# =====================================================================================

def per_row_argmin_mode(delivered: list[dict], m_range, n_range, which: int, log, label: str):
    """Per spec Sec.5.1: per-row argmin over the FULL swept grid (both axes jointly -- the
    spec's own null of 1/21 only holds if the argmin is taken over all cells, not a
    marginal). Deterministic tie-break: lowest n_err, then closest to (0,0), then
    lexicographic (m, n) ascending -- so re-running is bit-reproducible. Also reports the
    m-axis marginal mode as extra, informational context (the "one-symbol displacement"
    hypothesis is a statement about m specifically)."""
    n_cells = len(m_range) * len(n_range)
    cell_counts: dict[tuple[int, int], int] = {}
    m_counts: dict[int, int] = {}
    n_complete = 0

    for d in delivered:
        vals = []
        complete = True
        for m in m_range:
            for n in n_range:
                v = d["cells"].get((m, n))
                if v is None or v[which] is None:
                    complete = False
                    break
                vals.append((v[which], m, n))
            if not complete:
                break
        if not complete:
            continue
        n_complete += 1
        vals.sort(key=lambda t: (t[0], abs(t[1]), abs(t[2]), t[1], t[2]))
        _, bm, bn = vals[0]
        cell_counts[(bm, bn)] = cell_counts.get((bm, bn), 0) + 1
        m_counts[bm] = m_counts.get(bm, 0) + 1

    if n_complete == 0:
        log("  %s: no rows had a complete grid -- cannot compute a mode." % label)
        return None

    mode_cell = max(cell_counts, key=lambda k: cell_counts[k])
    frac_at_mode = cell_counts[mode_cell] / n_complete
    mode_m = max(m_counts, key=lambda k: m_counts[k])
    frac_m_at_mode = m_counts[mode_m] / n_complete
    null = 1.0 / n_cells

    log("  %s: modal cell (m=%d,n=%d) frac_at_mode=%.3f (%d/%d complete rows; null~1/%d=%.3f) "
        "-- WINNER'S-CURSE BIAS NAMED PER SPEC SEC.3.2/5.1: this is a per-row argmin, biased "
        "toward whichever path varies more across position (expected: coherent)."
        % (label, mode_cell[0], mode_cell[1], frac_at_mode, cell_counts[mode_cell], n_complete,
           n_cells, null))
    log("  %s: m-axis marginal mode = %d, frac=%.3f (informational only, not the spec's own "
        "1/n_cells null statistic)" % (label, mode_m, frac_m_at_mode))

    return {
        "mode_cell": {"m": mode_cell[0], "n": mode_cell[1]}, "frac_at_mode": frac_at_mode,
        "n_complete": n_complete, "n_cells": n_cells, "null": null,
        "cell_counts": {_cell_key(*k): v for k, v in sorted(cell_counts.items())},
        "mode_m": mode_m, "frac_m_at_mode": frac_m_at_mode,
        "m_counts": {str(k): v for k, v in sorted(m_counts.items())},
    }


# =====================================================================================
# main
# =====================================================================================

def main() -> int:
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("B-POS-A -- the lattice-position arm (DIAGNOSTIC ONLY -- no ROW, no gate, no verdict)")
    log("Spec: qa/rr-study/2026-08-21-1330-architect-to-qa-spec-b-pos-a-lattice-position-arm.md")
    log("ROW 0g stands FIRED. Task 4.3 stays VOID. ROW 3 is NOT declared. Route B2 is NOT dead.")
    log("=" * 90)

    log("\nLoading DLL: %s (pinned to CURRENT merged binary, shim %d)"
        % (DEFAULT_DLL_PATH, CURRENT_SHIM_VERSION))
    try:
        ex = CoherentExtractLLRs(DEFAULT_DLL_PATH, verify=True, expected_sha256=CURRENT_DLL_SHA256,
                                  expected_shim_version=CURRENT_SHIM_VERSION)
    except (RuntimeError, AttributeError) as e:
        log("DLL pin FAILED: %s" % e)
        bundle = {"final": "dll_pin_fail", "error": str(e)}
        _write(out_dir, bundle, log_lines)
        return 2
    log("DLL pin confirmed: SHA256 %s..., shim version %d" % (CURRENT_DLL_SHA256[:16], ex.version))
    bundle: dict = {"dll_pin": {"sha256_prefix": CURRENT_DLL_SHA256[:16], "shim_version": ex.version}}

    log("\nBuilding P-HIT population + deterministic sample (VERBATIM reuse of ROW 0g-2's own "
        "population/sample/seed/anchor, spec Sec.3.1 / HK-018) ...")
    delivered, drop_reasons, n_sampled = build_sample_and_deliver(ex, log)
    log("  n_sampled=%d control-delivered=%d drop_reasons=%s"
        % (n_sampled, len(delivered), drop_reasons))
    bundle["sample"] = {"n_sampled": n_sampled, "n_control_delivered": len(delivered),
                         "drop_reasons": drop_reasons}

    log("\n" + "-" * 90)
    log("PRECONDITION P1 -- control cell (m=0,n=0) must reproduce ROW 0g-2 EXACTLY")
    log("-" * 90)
    p1_ok, n_delivered, n_clusters, d_control, boot_control = check_p1(delivered, log)
    bundle["p1"] = {
        "n_delivered": n_delivered, "n_clusters_delivered": n_clusters, "d_control": d_control,
        "control_bootstrap_ci95": boot_control["ci95"], "n_clusters_bootstrap": boot_control["n_clusters"],
        "expected": {"n_delivered": CONTROL_N_DELIVERED, "n_clusters": CONTROL_N_CLUSTERS,
                     "d_control": CONTROL_D},
        "passed": p1_ok,
    }
    if not p1_ok:
        log("\nP1 FAILED TO REPRODUCE ROW 0g-2 EXACTLY -- STOP AND ESCALATE (spec Sec.4 P1). "
            "Expected n_delivered=%d n_clusters=%d d_control=%.1f; got n_delivered=%d "
            "n_clusters=%d d_control=%.3f. Every other cell would be uninterpretable if the "
            "harness is not calling what 0g-2 called -- not proceeding."
            % (CONTROL_N_DELIVERED, CONTROL_N_CLUSTERS, CONTROL_D, n_delivered, n_clusters, d_control))
        bundle["final"] = "p1_failed_escalate"
        _write(out_dir, bundle, log_lines)
        return 3
    log("\nP1 PASSED: control cell reproduces ROW 0g-2 exactly (n_delivered=%d n_clusters=%d "
        "d_control=%.1f)." % (n_delivered, n_clusters, d_control))

    log("\n" + "-" * 90)
    log("Sweeping the initial %d x %d = %d-cell grid over %d control-delivered rows ..."
        % (len(M_RANGE_INITIAL), len(N_RANGE), len(M_RANGE_INITIAL) * len(N_RANGE), len(delivered)))
    log("-" * 90)
    sweep_cells(ex, delivered, M_RANGE_INITIAL, N_RANGE, log)

    log("\n" + "-" * 90)
    log("PRECONDITION P2 -- chosen global optimum must be INTERIOR (HK-026)")
    log("-" * 90)
    m_range_final, widen_steps, best_g, table_g, best_c, table_c, unresolved = \
        widen_if_needed(ex, delivered, M_RANGE_INITIAL, log)
    bundle["p2"] = {"widen_steps": widen_steps, "final_m_range": list(m_range_final),
                     "unresolved_boundary": unresolved}
    if unresolved:
        log("\nP2 UNRESOLVED after %d widen step(s) -- reporting the widest grid tried "
            "([%d,%d] quanta), flagged explicitly, NOT silently accepted as an interior "
            "optimum." % (widen_steps, m_range_final[0], m_range_final[-1]))
    elif widen_steps:
        log("\nP2 resolved after %d widen step(s): final m range [%d, %d] quanta."
            % (widen_steps, m_range_final[0], m_range_final[-1]))
    else:
        log("\nP2 clear: both paths' chosen optima are interior to the initial [%d, %d] range."
            % (M_RANGE_INITIAL[0], M_RANGE_INITIAL[-1]))

    cell_g = (best_g[1], best_g[2])
    cell_c = (best_c[1], best_c[2])
    bundle["best_cells"] = {
        "grid": {"m": cell_g[0], "n": cell_g[1], "cluster_median_n_err": best_g[0],
                 "n_clusters": best_g[3]},
        "coherent": {"m": cell_c[0], "n": cell_c[1], "cluster_median_n_err": best_c[0],
                     "n_clusters": best_c[3]},
    }

    log("\n" + "=" * 90)
    log("SEC 5.2 -- SECONDARY: does an own-best global offset close the gap?")
    log("=" * 90)
    log("  chosen cells (quanta): grid (m=%d,n=%d) coherent (m=%d,n=%d)"
        % (cell_g[0], cell_g[1], cell_c[0], cell_c[1]))
    boot_global, n_rows_global = compute_d_global(delivered, cell_g, cell_c, log)
    log("  d_global (median n_err_grid[best] - n_err_coh[best]) = %.3f, cluster-bootstrap "
        "CI95=[%.3f, %.3f] (n_rows=%d, n_clusters=%d, n_draws=%d)"
        % (boot_global["point_estimate"], boot_global["ci95"][0], boot_global["ci95"][1],
           n_rows_global, boot_global["n_clusters"], boot_global["n_draws"]))
    log("  for reference, d_control (shared m=0,n=0) = %.1f CI95=[%.1f, %.1f]"
        % (d_control, boot_control["ci95"][0], boot_control["ci95"][1]))
    bundle["d_global"] = {
        "point_estimate": boot_global["point_estimate"], "ci95": boot_global["ci95"],
        "n_rows": n_rows_global, "n_clusters": boot_global["n_clusters"],
        "n_draws": boot_global["n_draws"], "p_two_sided": boot_global["p_two_sided"],
        "cells": {"grid": {"m": cell_g[0], "n": cell_g[1]}, "coherent": {"m": cell_c[0], "n": cell_c[1]}},
        "d_control_reference": {"point_estimate": d_control, "ci95": boot_control["ci95"]},
    }

    log("\n" + "=" * 90)
    log("SEC 5.1 -- PRIMARY: is the coherent path's own-best displacement CONSTANT or SCATTERED?")
    log("=" * 90)
    argmin_coh = per_row_argmin_mode(delivered, m_range_final, N_RANGE, 1, log, "coherent")
    argmin_grid = per_row_argmin_mode(delivered, m_range_final, N_RANGE, 0, log, "grid")
    bundle["argmin_shape"] = {"coherent": argmin_coh, "grid": argmin_grid}

    log("\n" + "=" * 90)
    log("B-POS-A DONE. DIAGNOSTIC ONLY -- no verdict, no gate, no ROW. Numbers above are for "
        "the Architect to read against Sec.6's blind predictions and Sec.7's branches.")
    log("ROW 0g still stands FIRED; task 4.3 still VOID; ROW 3 still not declared; Route B2 "
        "still not dead; design.md D1 still not amended (1201 spec Sec.5 ruling still owed).")
    log("=" * 90)
    bundle["final"] = "diagnostic_complete"
    _write(out_dir, bundle, log_lines)
    return 0


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "b_pos_a_report.json"), bundle)
    with open(os.path.join(out_dir, "b_pos_a_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
