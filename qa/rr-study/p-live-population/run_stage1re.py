#!/usr/bin/env python3
"""P-LIVE Stage 1RE -- limb 2 (N5's outcome conversion) at scale, on the CORRECTED
anchor, sequenced BEFORE the Phase B Developer session per the Captain's
2026-08-21 authorisation.

Spec: qa/rr-study/2026-08-21-1538-architect-to-qa-spec-stage-1re-limb2-at-scale.md
("this spec"). Supersedes withdrawn P-LIVE Stage 1 (run_stage1.py) IN EXECUTION
ONLY -- the withdrawn numbers (f_cross = 0/15,389, the 0.0765% bound) stay
withdrawn: never cited, compared against, or used to set expectations here.

WHAT THIS RUNS, in the order actually executed (see the note on ordering below):
  1. HK-025 -- independent re-classification of every ROW 0 in this spec's own
     Sec.3 (re-derived here, not copied from the spec's table).
  2. ROW 0a  -- DLL re-hashed from disk, asserted against THIS spec's own pin
     (Sec.header: SHA256 1889408787a2c7ea..., shim 20260043 -- NOT run_stage1.py's
     stale 20260042 pin; that script targets an older merge).
  3. Part A  -- verbatim reuse of run_stage2.run_part_a() on P-HIT/PRIMARY (spec
     Sec.2: "reuse Stage 2 Part A's derivation verbatim"). This ALREADY runs, in
     order: the mandatory sign unit test, the 49-point m3_common sweep, ROW 0c in
     Stage 2's OWN naming (this spec's ROW 0b, band [1%,15%] -- the two bands are
     numerically identical, ROW_0C_LO/HI = 0.010/0.150 in both modules) and ROW 0d
     in both modules' naming (quartile stability, tol 0.05s, identical). Renamed
     to this spec's ROW 0b / ROW 0d in every log line and report key below.
  4. Full P-LIVE measurement on PRIMARY at anchor_dt + OFFSET -- V0 (native grid)
     vs V3_cum (coherent order-3, Stage 1's own arms, UNCHANGED) -- over the WHOLE
     population, no truncation, no sampling (spec Sec.5: "cluster count is the
     entire point of this arm").
  5. ROW 0c (this spec's own, band [8%,40%] two-sided on median BER_V0-at-OFFSET)
     then ROW 0e (population floor, 500 rows / 200 clusters DELIVERED).
  6. f_net (this spec's own crossable-denominator definition, Sec.4 -- NOT
     n5_stats.f_net, which re-bases onto the whole population; a fresh cluster
     bootstrap is implemented here for exactly this quantity) -> ROW 1/2/3/4.

ORDERING NOTE (documented per HK-021(k) rather than silently reordered): the
spec's own Sec.3 table lists 0a, 0b, 0c, 0d, 0e in that sequence. 0b and 0d are
BOTH outputs of the SAME Part A sweep (Stage 2's run_part_a computes its own
"row_0c"/"row_0d" back to back from one sweep_matrix pass) -- there is no way to
learn 0d without already having 0b, and no compute is wasted by evaluating them
together. 0c (this spec's, the two-sided anchor-sanity band) is NOT knowable
until the full, expensive P-LIVE extraction pass has run -- it cannot precede 0d
in actual computation, only in the document's enumeration. This module therefore
evaluates 0a -> [0b, 0d from Part A, STOP on either firing before the expensive
pass runs] -> [full P-LIVE pass] -> [0c, 0e, STOP on either firing before any
gate is touched]. Every row still independently gates (HK-021(k)); nothing here
changes which action a fired row licenses, only when it is CHECKED, and it is
checked as early as it is computable in every case.

NFR-021: message text touches this module only inside measure_row_1re's call to
ex.true_codeword(row["message"]) and is never retained past that call or written
to any dict this module returns, prints, or serialises. Every emitted file is
grepped individually for "message" after the run, per every predecessor spec's
own instruction, not merely asserted.

Scope: no src/, no native/, no rebuild, no push, no merge -- HK-011 NOT engaged.
"""
from __future__ import annotations

import argparse
import os
import statistics as st
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n3-frequency-requirement"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n5-outcome-conversion"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m3-anchor-timebase"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
from coherent_extract_ext import extract_variants_ext  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, hard_decision_ber  # noqa: E402
from n5_stats import B50_THRESHOLD, d_ber_row, f_break_row, f_cross_row  # noqa: E402
from plive_population import PRIMARY_CORPUS, build_p_live_population, corpus_paths  # noqa: E402
from run_stage1 import WavCache, decile_table  # noqa: E402
from run_stage2 import ROW_0C_HI as PART_A_ROW_0C_HI  # noqa: E402 -- Part A's own band, for the log label only
from run_stage2 import ROW_0C_LO as PART_A_ROW_0C_LO  # noqa: E402
from run_stage2 import run_part_a  # noqa: E402 -- Sec.2: reuse Part A verbatim

# -- This spec's OWN binary pin (header block) -- NOT run_stage1.py's stale one --
DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
DLL_SHA256 = "1889408787a2c7ea545dbe8477691b090417a74fc81116cbf1ea52413bfbdb3a"
SHIM_VERSION = 20260043

# -- Sec.3 ROW 0c (this spec's own numbering) -- two-sided anchor sanity --------
ROW_0C_LO, ROW_0C_HI = 0.08, 0.40

# -- Sec.3 ROW 0e -- population floor, on DELIVERED rows/clusters ---------------
ROW_0E_MIN_ROWS = 500
ROW_0E_MIN_CLUSTERS = 200

# -- Sec.4 gate bounds ------------------------------------------------------------
ROW_2_BOUND_MAX = 0.005   # rule-of-three (or CI_hi) < 0.5%  -> LIMB 2 CLOSES
ROW_3_BOUND_MAX = 0.05    # ... in [0.5%, 5%]                -> STILL OPEN, TIGHTER

# This arm's own seed -- today's date (HK-017 provenance), distinct from every
# prior stage's seed (Stage1R/Stage2's shared 20260818, N-series' 20260815/16/17).
STAGE1RE_SEED = 20260821
DEFAULT_N_DRAWS = 2000


# =============================================================================
# HK-025 -- independent re-classification (re-derived, not copied from Sec.3)
# =============================================================================

def hk025_check() -> dict:
    """0a: fires -> the run proceeds against an unidentified binary, no named
        instrument at all -- refuse to arm. Clears -> proceed on a pinned SHA.
        VALIDITY, not diagnostic.
    0b (Part A's own "row_0c"): fires -> no offset this sweep finds reads a
        plausible signal on rows we ourselves decoded -- no usable anchor
        correction exists AT ALL. Clears -> a real offset exists. VALIDITY.
    0d (Part A's own "row_0d"): fires -> the offset drifts by cycle, so ONE
        global correction is the wrong design for every P-LIVE row. Clears ->
        one constant offset is valid. Different downstream DESIGNS, not
        different confidence in the same design. VALIDITY.
    0c (this spec's own): fires -> either chance-level (structural, d-b's own
        Stage 2 ROW 0g logic: BER at the corrected anchor reads noise, so the
        contrast is not about V0 vs V3 at all) or implausibly low (membership
        leak, a DIFFERENT population). Both fired-subcases share ONE downstream
        action (stop, do not read the measurement) against ONE cleared-branch
        action (proceed). VALIDITY, not diagnostic -- HK-025 requires only that
        fired-vs-cleared differ, which it does, even though the two fired
        subcases differ from each other.
    0e: fires -> the delivered population cannot support a reliable cluster
        bootstrap -- not reduced precision on a still-valid measurement, an
        underpowered instrument. VALIDITY.

    No refusal. Concurs with the spec's own Sec.3/Sec.4."""
    reasons = {
        "0a": "unidentified binary invalidates every downstream number",
        "0b": "no usable global anchor correction on positive-control rows -- "
              "premise failure, not imprecision",
        "0d": "offset not one constant across the cycle timeline -- wrong "
              "DESIGN (needs a per-cycle correction), not noise",
        "0c": "chance-level (structural) or implausibly low (membership leak) "
              "-- either way the V0-vs-V3 question does not apply as framed",
        "0e": "delivered population underpowered for a reliable cluster bootstrap",
    }
    classification = {k: {"class": "VALIDITY", "reason": v} for k, v in reasons.items()}
    return {"classification": classification, "refusal": False, "concurs_with_spec": True}


# =============================================================================
# Full P-LIVE measurement at the corrected anchor -- V0 grid vs V3_cum coherent
# =============================================================================

def measure_row_1re(ex: ExtractLLRs, wav_cache: WavCache, row: dict, offset: float) -> dict:
    """Stage 1's own V0/V3_cum arms, UNCHANGED (spec Sec.4: "reuse verbatim") --
    the only change from the withdrawn run is anchor_dt + OFFSET here, Sec.2."""
    try:
        pcm = wav_cache.get(row["ts"])
    except FileNotFoundError:
        return {"reason": "no_wav"}

    anchor_freq_int = round(row["anchor_freq_hz"])  # no-op: WSJT-X freq already int Hz
    raw_freq_hz = float(row["anchor_freq_hz"])       # unrounded, N4's fix, no-op here too
    corrected_dt = float(row["anchor_dt"]) + offset

    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return {"reason": "no_true_codeword"}

    try:
        rc0, llr_v0 = ex.extract_at(pcm, float(anchor_freq_int), corrected_dt)
        if rc0 != 0 or llr_v0 is None:
            return {"reason": "v0_extract_rc_%d" % rc0}

        pcm64 = np.asarray(pcm, dtype=np.float64)
        variants = extract_variants_ext(pcm64, raw_freq_hz, corrected_dt, df_hz=0.0)
        llr_v3 = list(variants["V3_cum"])
    except Exception as e:  # noqa: BLE001 -- unattended run over ~18k rows; record, don't crash
        return {"reason": "exception_%s" % type(e).__name__}

    ber_v0 = hard_decision_ber(llr_v0, true_bits)
    ber_v3 = hard_decision_ber(llr_v3, true_bits)

    return {
        "ts": row["ts"],
        "corpus": row["corpus"],
        "ber_v0": ber_v0,
        "ber_v3": ber_v3,
        "d_ber": d_ber_row(ber_v0, ber_v3),
        "crosses": f_cross_row(ber_v0, ber_v3),
        "breaks": f_break_row(ber_v0, ber_v3),
        "anchor_freq_hz": anchor_freq_int,
        "corrected_dt": corrected_dt,
    }


# =============================================================================
# Sec.4's own f_net -- crossable-denominator, cluster-bootstrapped by ts
# =============================================================================

def _compute_point_1re(rows: list[dict]) -> dict:
    """f_net = (n_cross - n_break) / n_crossable, spec Sec.4 verbatim -- NOT
    n5_stats._compute_point, which re-bases both terms onto n_total instead."""
    crossable = [r for r in rows if r["ber_v0"] > B50_THRESHOLD]
    breakable = [r for r in rows if r["ber_v0"] <= B50_THRESHOLD]
    n_cross = sum(1 for r in crossable if r["crosses"])
    n_break = sum(1 for r in breakable if r["breaks"])
    n_crossable = len(crossable)
    n_breakable = len(breakable)
    f_cross = (n_cross / n_crossable) if n_crossable else float("nan")
    f_break = (n_break / n_breakable) if n_breakable else float("nan")
    f_net = ((n_cross - n_break) / n_crossable) if n_crossable else float("nan")
    return {
        "n_total": len(rows), "n_cross": n_cross, "n_crossable": n_crossable,
        "n_break": n_break, "n_breakable": n_breakable,
        "f_cross": f_cross, "f_break": f_break, "f_net": f_net,
    }


def cluster_bootstrap_f_net_1re(rows: list[dict], n_draws: int = DEFAULT_N_DRAWS,
                                 seed: int = STAGE1RE_SEED) -> dict:
    """Cluster bootstrap over `ts` (HK-021(i)), one resample per draw, f_net (and
    descriptive f_cross/f_break) all recomputed from that SAME resampled row set,
    matching n5_stats' "same draws" discipline but with Sec.4's own denominator."""
    by_ts: dict[str, list[dict]] = {}
    for r in rows:
        by_ts.setdefault(r["ts"], []).append(r)
    ts_list = sorted(by_ts)  # sort before any seeded draw indexes into this list
    n_clusters = len(ts_list)

    point = _compute_point_1re(rows)
    point["n_clusters"] = n_clusters
    point["n_clusters_crossable"] = len({r["ts"] for r in rows if r["ber_v0"] > B50_THRESHOLD})
    point["n_clusters_breakable"] = len({r["ts"] for r in rows if r["ber_v0"] <= B50_THRESHOLD})

    nan_summary = {"ci95": [float("nan"), float("nan")], "se": float("nan"), "n_draws": 0}
    if n_clusters < 2 or not rows:
        return {"point": point, "f_cross": nan_summary, "f_break": nan_summary,
                "f_net": nan_summary, "n_clusters": n_clusters, "seed": seed}

    rng = np.random.default_rng(seed)
    draws_cross: list[float] = []
    draws_break: list[float] = []
    draws_net: list[float] = []
    for _ in range(n_draws):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        sub_rows: list[dict] = []
        for i in pick:
            sub_rows.extend(by_ts[ts_list[i]])
        d = _compute_point_1re(sub_rows)
        if not np.isnan(d["f_cross"]):
            draws_cross.append(d["f_cross"])
        if not np.isnan(d["f_break"]):
            draws_break.append(d["f_break"])
        if not np.isnan(d["f_net"]):
            draws_net.append(d["f_net"])

    def _summarise(draws: list[float]) -> dict:
        if not draws:
            return dict(nan_summary)
        arr = np.array(draws)
        return {"ci95": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))],
                "se": float(arr.std(ddof=1)) if len(arr) > 1 else float("nan"),
                "n_draws": len(arr)}

    return {
        "point": point,
        "f_cross": _summarise(draws_cross),
        "f_break": _summarise(draws_break),
        "f_net": _summarise(draws_net),
        "n_clusters": n_clusters,
        "seed": seed,
    }


# =============================================================================
# main
# =============================================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DLL_PATH)
    ap.add_argument("--dll-sha256", default=DLL_SHA256)
    ap.add_argument("--n-draws", type=int, default=DEFAULT_N_DRAWS)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("P-LIVE STAGE 1RE -- limb 2 at scale, on the CORRECTED anchor")
    log("(spec 2026-08-21-1538, sequenced ahead of Phase B per the Captain's authorisation)")
    log("=" * 90)

    hk025 = hk025_check()
    log("\nHK-025 independent re-classification: concurs_with_spec=%s refusal=%s"
        % (hk025["concurs_with_spec"], hk025["refusal"]))
    if hk025["refusal"]:
        log("REFUSING TO ARM PER HK-025.")
        _write(args.out_dir, {"hk025": hk025, "final_row": "REFUSED"}, log_lines)
        return 1

    bundle: dict = {"hk025": hk025}

    # -- ROW 0a: this spec's own pin, asserted before arming --------------------
    log("\nLoading DLL: %s" % args.dll_path)
    log("Pin (this spec's header, NOT run_stage1.py's stale one): SHA256=%s... shim=%d"
        % (args.dll_sha256[:16], SHIM_VERSION))
    try:
        ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                          expected_shim_version=SHIM_VERSION)
    except RuntimeError as e:
        log("\nROW 0a FIRES: %s" % e)
        log("VALIDITY, STOP. NO VERDICT.")
        bundle["final_row"] = "0a"
        bundle["row_0a"] = {"fires": True, "error": str(e)}
        _write(args.out_dir, bundle, log_lines)
        return 2
    log("ROW 0a clear: DLL SHA256 asserted, shim version %d confirmed." % ex.version)
    bundle["row_0a"] = {"fires": False}

    # -- Part A on PRIMARY, verbatim reuse of run_stage2.run_part_a -------------
    log("\n" + "=" * 90)
    log("PART A -- verbatim reuse of run_stage2.run_part_a (spec Sec.2)")
    log("=" * 90)
    part_a = run_part_a(ex, PRIMARY_CORPUS, log, descriptive_only=False)
    bundle["part_a"] = part_a

    if part_a.get("sign_unit_test_passed") is not True:
        log("\nMANDATORY SIGN UNIT TEST FAILED (or did not run). STOP. NO VERDICT.")
        bundle["final_row"] = "sign_unit_test"
        _write(args.out_dir, bundle, log_lines)
        return 3

    row0b_fires = part_a.get("row_0c", {}).get("fires", True)  # Part A's own "0c" == this spec's "0b"
    log("\nROW 0b (Part A's own row_0c, band [%.0f%%,%.0f%%]): %s"
        % (PART_A_ROW_0C_LO * 100, PART_A_ROW_0C_HI * 100, "FIRES" if row0b_fires else "clear"))
    bundle["row_0b"] = part_a.get("row_0c", {"fires": True})
    if row0b_fires:
        log("\nROW 0b FIRES: no usable global anchor correction on the positive control. "
            "VALIDITY, STOP, escalate. NO VERDICT.")
        bundle["final_row"] = "0b"
        _write(args.out_dir, bundle, log_lines)
        return 4

    row0d_fires = part_a.get("row_0d", {}).get("fires", True)
    log("ROW 0d (Part A's own row_0d, offset stability, tol 0.05s): %s"
        % ("FIRES" if row0d_fires else "clear"))
    bundle["row_0d"] = part_a.get("row_0d", {"fires": True})
    if row0d_fires:
        log("\nROW 0d FIRES: the offset is not one constant across the cycle timeline. "
            "VALIDITY, STOP, escalate. NO VERDICT.")
        bundle["final_row"] = "0d"
        _write(args.out_dir, bundle, log_lines)
        return 5

    offset = part_a["offset"]
    log("\nPart A clear. OFFSET = %+.2fs (swept argmin, derived on THIS run, not inherited)."
        % offset)
    if abs(offset - 0.65) > 0.08 + 1e-9:
        log("\n*** ESCALATION FLAG (spec Sec.2): swept argmin differs from Stage 1R's own "
            "+0.65s by more than one lattice cell (0.08s). This is an instrument change, "
            "not a nuisance parameter. STOP AND ESCALATE PER SEC.2 -- reporting the number "
            "and halting before the expensive P-LIVE pass rather than burning the budget.")
        bundle["final_row"] = "offset_escalation"
        bundle["offset"] = offset
        _write(args.out_dir, bundle, log_lines)
        return 6
    log("(within one lattice cell of Stage 1R's +0.65s -- Sec.2's own escalation trigger "
        "does not fire; proceeding.)")
    bundle["offset"] = offset

    # -- Full P-LIVE measurement on PRIMARY, no truncation, no sampling ---------
    log("\n" + "=" * 90)
    log("FULL P-LIVE MEASUREMENT on PRIMARY (%s) at anchor_dt %+.2fs -- V0 grid vs V3_cum coherent"
        % (PRIMARY_CORPUS, offset))
    log("(no truncation, no sampling -- spec Sec.5: cluster count is the entire point)")
    log("=" * 90)
    paths = corpus_paths(PRIMARY_CORPUS)
    population = build_p_live_population(PRIMARY_CORPUS)
    n_population = len(population)
    n_pop_clusters = len({r["ts"] for r in population})
    log("  P-LIVE population (pre-extraction): n_rows=%d n_clusters=%d" % (n_population, n_pop_clusters))

    wav_cache = WavCache(paths["wsjtx_wav_dir"])
    t0 = time.time()
    rows: list[dict] = []
    reasons: dict[str, int] = {}
    for i, row in enumerate(population):
        r = measure_row_1re(ex, wav_cache, row, offset)
        if r is None or "reason" in r:
            reason = r["reason"] if r else "none"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        rows.append(r)
        if (i + 1) % 3000 == 0:
            log("  ... %d/%d processed (%d measured, %.1fs elapsed)"
                % (i + 1, n_population, len(rows), time.time() - t0))
    elapsed = time.time() - t0
    n_measured = len(rows)
    n_clusters_measured = len({r["ts"] for r in rows})
    log("  measured %d/%d rows (%.1fs). n_clusters_measured=%d. drop_reasons=%s"
        % (n_measured, n_population, elapsed, n_clusters_measured, reasons))
    bundle["n_population"] = n_population
    bundle["n_population_clusters"] = n_pop_clusters
    bundle["n_measured"] = n_measured
    bundle["n_clusters_measured"] = n_clusters_measured
    bundle["drop_reasons"] = reasons
    bundle["measure_elapsed_s"] = elapsed

    if n_measured == 0:
        log("\nNo rows measured -- cannot evaluate ROW 0c/0e. STOP.")
        bundle["final_row"] = "no_rows_measured"
        _write(args.out_dir, bundle, log_lines)
        return 7

    # -- ROW 0c: this spec's own two-sided anchor sanity -------------------------
    median_ber_v0 = float(st.median(r["ber_v0"] for r in rows))
    log("\n  median BER_V0(OFFSET)=%.2f%%" % (median_ber_v0 * 100))
    row0c_fires = not (ROW_0C_LO <= median_ber_v0 <= ROW_0C_HI)
    log("ROW 0c: median_BER_V0=%.2f%% outside [%.0f%%,%.0f%%] two-sided -> %s"
        % (median_ber_v0 * 100, ROW_0C_LO * 100, ROW_0C_HI * 100, "FIRES" if row0c_fires else "clear"))
    bundle["row_0c"] = {"fires": row0c_fires, "median_ber_v0": median_ber_v0,
                         "band": [ROW_0C_LO, ROW_0C_HI]}
    if row0c_fires:
        log("\nROW 0c FIRES: %s. VALIDITY, STOP, escalate. NO VERDICT."
            % ("chance-level (structural)" if median_ber_v0 > ROW_0C_HI
               else "implausibly low (suspect membership leak)"))
        bundle["final_row"] = "0c"
        _write(args.out_dir, bundle, log_lines)
        return 8

    # -- ROW 0e: population floor, DELIVERED counts -------------------------------
    row0e_fires = n_measured < ROW_0E_MIN_ROWS or n_clusters_measured < ROW_0E_MIN_CLUSTERS
    log("ROW 0e: n_measured=%d (>=%d) n_clusters_measured=%d (>=%d) -> %s"
        % (n_measured, ROW_0E_MIN_ROWS, n_clusters_measured, ROW_0E_MIN_CLUSTERS,
           "FIRES" if row0e_fires else "clear"))
    bundle["row_0e"] = {"fires": row0e_fires, "n_measured": n_measured,
                         "n_clusters_measured": n_clusters_measured}
    if row0e_fires:
        log("\nROW 0e FIRES: fewer than %d rows or %d clusters delivered. STOP, escalate. "
            "NO VERDICT." % (ROW_0E_MIN_ROWS, ROW_0E_MIN_CLUSTERS))
        bundle["final_row"] = "0e"
        _write(args.out_dir, bundle, log_lines)
        return 9

    log("\nROW 0c/0e both clear. Preconditions satisfied -- proceeding to the primary statistic.\n")

    # -- Primary statistic: f_net (Sec.4's own crossable-denominator definition) -
    log("=" * 90)
    log("PRIMARY STATISTIC -- f_net = (n_cross - n_break) / n_crossable, cluster bootstrap by ts")
    log("=" * 90)
    boot = cluster_bootstrap_f_net_1re(rows, n_draws=args.n_draws)
    pt = boot["point"]
    n_clusters = boot["n_clusters"]
    rule_of_three = (1.0 - 0.05 ** (1.0 / n_clusters)) if n_clusters > 0 else float("nan")

    log("  n_crossable=%d (clusters=%d) n_cross=%d n_breakable=%d (clusters=%d) n_break=%d"
        % (pt["n_crossable"], pt["n_clusters_crossable"], pt["n_cross"],
           pt["n_breakable"], pt["n_clusters_breakable"], pt["n_break"]))
    log("  f_cross (own denom, descriptive): point=%.4f%% CI95=[%.4f,%.4f]%% n_draws=%d"
        % (pt["f_cross"] * 100 if not np.isnan(pt["f_cross"]) else float("nan"),
           boot["f_cross"]["ci95"][0] * 100, boot["f_cross"]["ci95"][1] * 100, boot["f_cross"]["n_draws"]))
    log("  f_break (own denom, descriptive): point=%.4f%% CI95=[%.4f,%.4f]%% n_draws=%d"
        % (pt["f_break"] * 100 if not np.isnan(pt["f_break"]) else float("nan"),
           boot["f_break"]["ci95"][0] * 100, boot["f_break"]["ci95"][1] * 100, boot["f_break"]["n_draws"]))
    log("  f_net (SIGNED, HK-021(l), primary): point=%+.4f%% CI95=[%+.4f,%+.4f]%% n_draws=%d n_clusters=%d"
        % (pt["f_net"] * 100 if not np.isnan(pt["f_net"]) else float("nan"),
           boot["f_net"]["ci95"][0] * 100, boot["f_net"]["ci95"][1] * 100,
           boot["f_net"]["n_draws"], n_clusters))
    log("  rule-of-three bound (n_clusters=%d): %.4f%%  [the headline if n_cross=0 -- the "
        "bootstrap CI is then degenerate by construction]" % (n_clusters, rule_of_three * 100))

    bundle["f_net_bootstrap"] = boot
    bundle["rule_of_three_bound"] = rule_of_three

    # -- ROW 1/2/3/4 gate ----------------------------------------------------------
    log("\n" + "=" * 90)
    log("ROW 1 / 2 / 3 / 4 -- the gate")
    log("=" * 90)
    ci_lo, ci_hi = boot["f_net"]["ci95"]
    n_cross = pt["n_cross"]
    bound = rule_of_three if n_cross == 0 else ci_hi
    log("  gate metric: %s = %.4f%% (rule-of-three used because n_cross=%d; CI_hi(f_net) "
        "used otherwise)" % ("rule-of-three" if n_cross == 0 else "CI_hi(f_net)", bound * 100, n_cross))

    if np.isnan(ci_lo) or np.isnan(ci_hi):
        final_row = "degenerate_ci"
        log("\nCI is degenerate (NaN) -- cannot evaluate ROW 1-4. Report n_clusters=%d and "
            "the rule-of-three bound only. Escalate." % n_clusters)
    elif ci_lo > 0.0:
        final_row = "1"
        log("\nROW 1 FIRES: CI_lo(f_net)=%+.4f%% > 0%%." % (ci_lo * 100))
        log("CONSEQUENCE: LIMB 2 CONVERTS. Coherent LLRs convert real misses at scale. "
            "Route B2 is strongly motivated; Phase B becomes high-value. Point estimate "
            "f_net=%+.4f%% against the ~42pp gap -- a conversion rate is NOT yet a "
            "recovered-message count." % (pt["f_net"] * 100))
    elif ci_hi < 0.0:
        final_row = "4"
        log("\nROW 4 FIRES: CI_hi(f_net)=%+.4f%% < 0%%." % (ci_hi * 100))
        log("CONSEQUENCE: LIMB 2 HARMS. Coherent LLRs break more than they convert -- the "
            "limb-1 pattern (Stage 2 ROW 3) repeating on limb 2. Escalate hard; do NOT "
            "proceed to Phase B without a Captain ruling.")
    elif bound < ROW_2_BOUND_MAX:
        final_row = "2"
        log("\nROW 2 FIRES: CI contains 0 AND gate metric=%.4f%% < %.1f%%." % (bound * 100, ROW_2_BOUND_MAX * 100))
        log("CONSEQUENCE: LIMB 2 CLOSES. At this cluster count (%d) the prize is bounded "
            "below %.1f%% of the crossable population. ESCALATE TO THE CAPTAIN BEFORE ANY "
            "PHASE B DEVELOPER SESSION -- this materially changes what Route B2 is worth."
            % (n_clusters, ROW_2_BOUND_MAX * 100))
    elif bound <= ROW_3_BOUND_MAX:
        final_row = "3"
        log("\nROW 3 FIRES: CI contains 0 AND gate metric=%.4f%% in [%.1f%%,%.0f%%]."
            % (bound * 100, ROW_2_BOUND_MAX * 100, ROW_3_BOUND_MAX * 100))
        log("CONSEQUENCE: STILL OPEN, TIGHTER. N5's 4.37%% bound is improved but not "
            "decisive. Phase B proceeds as authorised.")
    else:
        final_row = "residue_beyond_5pct"
        log("\nRESIDUE: CI contains 0 but gate metric=%.4f%% exceeds the 5%% band the spec's "
            "own HK-021(m) note expected to be unreachable at this cluster count (n_clusters=%d). "
            "Report the interval as-is, do not pick a side, escalate -- this was NOT "
            "pre-registered as a named ROW." % (bound * 100, n_clusters))

    bundle["final_row"] = final_row
    bundle["gate_metric"] = bound
    bundle["gate_metric_is_rule_of_three"] = (n_cross == 0)

    log("\nAmendment-style descriptive: BER_V0-at-OFFSET decile table over the crossable "
        "denominator (rows with BER_V0 > B50=%.1f%%), n=%d:" % (B50_THRESHOLD * 100, pt["n_crossable"]))
    crossable_bers = [r["ber_v0"] for r in rows if r["ber_v0"] > B50_THRESHOLD]
    deciles = decile_table(crossable_bers)
    for i, v in enumerate(deciles["deciles"]):
        log("  p%d = %.2f%%" % (i * 10, v * 100))
    bundle["crossable_ber_deciles"] = deciles

    log("\n" + "=" * 90)
    log("FINAL ROW: %s" % final_row)
    log("=" * 90)

    _write(args.out_dir, bundle, log_lines)
    _write_rows(args.out_dir, rows)
    log("\nWrote results/stage1re_report.json, results/stage1re_rows.json, results/stage1re_run.log")
    return 0


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "stage1re_report.json"), bundle)
    with open(os.path.join(out_dir, "stage1re_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


def _write_rows(out_dir: str, rows: list[dict]) -> None:
    # every row dict already carries ONLY ts/corpus + numeric fields (measure_row_1re
    # never stores message text past its own local scope) -- NFR-021.
    P.write_json(os.path.join(out_dir, "stage1re_rows.json"), rows)


if __name__ == "__main__":
    raise SystemExit(main())
