#!/usr/bin/env python3
"""P-LIVE Stage 1 -- does order-3 coherent extraction CONVERT on the live-decode miss
population (WSJT-X decoded it, we detected NOTHING), at the shipping lattice anchor,
with no frequency estimator and no refinement?

Spec: qa/rr-study/2026-08-17-1806-architect-to-qa-p-live-population-and-n-series-
replication-spec.md Sec.3/Sec.4 Stage 1, AS AMENDED by Amendment A4
(qa/rr-study/2026-08-18-1457-architect-to-qa-p-live-stage1-go-ahead-and-amendment-a4.md)
Sec.A4.1 (ROW 0f), Sec.A4.2 (named PRIMARY), Sec.A4.3 (mandatory BER decile table).
ROW 0a/0b already ran and CLEARED on all five corpora (2026-08-18 14:46Z report);
this harness does not re-run them.

Arms, at WSJT-X's own reported (freq, dt) -- the anchor, per spec Sec.2 point 4 -- NO
search of any kind:
  V0      -- ft8_extract_llrs_at, unmodified native C (the shipping read), rounded
             anchor (a no-op here: WSJT-X's freq is already integer Hz).
  V3_cum  -- coherent_extract_ext's order-3 cumulative variant, UNROUNDED anchor
             (N4's mandatory fix, carried forward though a no-op for the same reason),
             df_hz=0.0 -- no offset, no sweep, no search.

Population: plive_population.build_p_live_population(corpus), one call per corpus.
Audio: the WAV for that ts from the corpus's OWN wsjt-x/wav/ directory -- "the leg
that supplied the anchor" (spec Sec.2 point 6); ROW 0a is what licenses this.

Primary, CONFIRMATORY population (Amendment A4.2): `20260803_live_run_1713` ALONE.
ROW 0c/0d/0e/0f and the ROW 1/2/3 gate are evaluated on this population ONLY.
Extension corpora (0016-8080, 0016-8081, 1154-17m, 0155-80m) are measured in full and
reported individually -- DESCRIPTIVE REPLICATION, gating nothing, NEVER pooled with
the primary or with each other (spec Sec.5.2 -- 0016-8080/-8081 observe the SAME
cycles at median per-cycle Jaccard 1.000/0.909/1.000).

Gate, strict order:
  0d  (run FIRST, before any real population is built, same precedent as N5's own
      run_n5.py ordering note): BOTH sign unit tests must pass fresh --
      n5_stats_sign_test.py (f_break/f_net logic) and n4_sign_unit_test.py (V3_cum
      DSP correctness). Re-run, not inherited from N4/N5's prior pass.
  0c  (PRIMARY only) n_measured<500 OR n_clusters_measured<200 -> PRECISION, escalate
  0e  (PRIMARY only) median hd_disagree_v0_v3 < 5/174 bits -> VALIDITY, escalate
  0f  (PRIMARY only, Amendment A4.1) median BER_V0 < 41.97% (43.97% - 2pp,
      one-sided) -> VALIDITY, escalate. Not a new threshold: 43.97% is N1/N5's own
      published THE-135 median, and the +/-2pp band is A1.1's own convention.

  ROW 1  CI_lo(f_cross) > 0.05 AND CI_lo(f_net) > 0   -> limb 2 CONVERTS materially
  ROW 2  CI_hi(f_cross) < 0.05                        -> upper-bounded below 5%,
                                                          BOTH LIMBS close
  ROW 3  residue (CI straddles 0.05)                  -> report interval, no side

All evaluated on the PRIMARY population's own cluster bootstrap (n_draws=2000, over
`ts`), reusing n5_stats.f_cross_row/f_break_row/cluster_bootstrap_f_cross_break_net
VERBATIM (spec Sec.4 Stage 1 item 3/4). Rule-of-three bound
(1 - 0.05**(1/n_clusters)) reported explicitly alongside every bootstrap CI, primary
and extensions alike (spec item 5) -- the honest bound when n_cross=0, since the
bootstrap CI is then degenerate by construction (every resample returns exactly
zero).

Amendment A4.3 (mandatory, descriptive, gates nothing): reports the decile
distribution of BER_V0 over the crossable denominator (BER_V0 > B50) on the PRIMARY
population, so a zero f_cross cannot be read as "V3 does not convert" when it may
instead mean "nothing was ever close to B50" (structural-ceiling check, HK-021(i)).
The same table is also reported for each extension corpus as bonus descriptive
context.

Scope (spec Sec.7, Amendment A4 Sec.1.2 -- unchanged): no src/, no Developer session,
no DLL rebuild, no capture run (HK-011 NOT engaged). No per-row frequency search;
common df only (df_hz=0.0 -- fixed, no sweep of any kind here). Rectangular window
only. DLL re-hashed from disk and asserted against the pin before arming (not
inferred from a label).

NFR-021 (sharper here than any prior round, spec Sec.7 / Amendment A4 Sec.1.2):
message TEXT is used in-process only (plive_population.build_p_live_population's own
return value, consumed inside measure_row to recover the true codeword via
ExtractLLRs.true_codeword) and is NEVER included in any dict this module writes to
disk or prints. measure_row's returned dict never carries a "message" key -- grepped
after every run, per spec instruction, not merely asserted.
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
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n2-coherent-llr-extractor"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n3-frequency-requirement"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n4-central-lobe-halfwidth"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n5-outcome-conversion"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
import n4_sign_unit_test  # noqa: E402
import n5_stats_sign_test  # noqa: E402
from coherent_extract_ext import extract_variants_ext  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, hard_decision_ber  # noqa: E402
from n5_stats import (  # noqa: E402
    B50_THRESHOLD, cluster_bootstrap_f_cross_break_net, d_ber_row, f_break_row, f_cross_row,
)
from plive_population import (  # noqa: E402
    ALL_CORPORA, EXTENSION_CORPORA, PRIMARY_CORPUS, build_p_live_population, corpus_paths,
)

DEFAULT_DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
DEFAULT_DLL_SHA256 = "6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672"
EXPECTED_SHIM_VERSION = 20260042

ROW_0C_MIN_ROWS = 500
ROW_0C_MIN_CLUSTERS = 200
ROW_0E_MIN_DISAGREE_BITS = 5
ROW_0F_TARGET = 0.4397          # N1/N5's own published THE-135 median (unchanged, A1.1's band)
ROW_0F_TOL = 0.02               # A4.1: FIRES if median < 43.97% - 2pp = 41.97% (one-sided)
ROW_1_CI_LO_F_CROSS_MIN = 0.05
ROW_2_CI_HI_F_CROSS_MAX = 0.05
MIN_BREAKABLE_FOR_DESCRIPTIVE = 30  # HK-021(j), same bar as N5


class WavCache:
    """Per-corpus WAV cache, generalised from run_n1.WavCache (that one is
    hardcoded to N1-N5's own WAV68_DIR). Reads from whatever directory the caller
    supplies -- here always the corpus's OWN wsjt-x/wav/ (the anchor-supplying
    leg, spec Sec.2 point 6)."""

    def __init__(self, wav_dir: str):
        self.wav_dir = wav_dir
        self._cache: dict[str, "object"] = {}

    def get(self, ts: str):
        if ts not in self._cache:
            wav_path = os.path.join(self.wav_dir, ts + ".wav")
            pcm = P.read_wav(wav_path)
            pcm = P.normalise_rms(pcm, P.PROD_TARGET_RMS)
            self._cache[ts] = pcm
        return self._cache[ts]


def hd_disagreement(llr_a, llr_b) -> int:
    """Identical logic to N2/N5's run_n2.hd_disagreement / run_n5.hd_disagreement --
    reimplemented here (not imported) to avoid pulling run_n5.py's own sys.path
    insertions and its bare-named `population` import, which run_n1.py's own comment
    already documents as a collision trap across this thread's several dirs."""
    hd_a = [1 if x > 0.0 else 0 for x in llr_a]
    hd_b = [1 if x > 0.0 else 0 for x in llr_b]
    return sum(1 for x, y in zip(hd_a, hd_b) if x != y)


def measure_row(ex: ExtractLLRs, wav_cache: WavCache, row: dict) -> "dict | None":
    """Returns a result dict (message text NEVER included) or a {"reason": ...} drop
    record. row: {ts, message, anchor_freq_hz, anchor_dt, corpus} from
    plive_population.build_p_live_population()."""
    try:
        pcm = wav_cache.get(row["ts"])
    except FileNotFoundError:
        return {"reason": "no_wav"}

    anchor_freq_int = round(row["anchor_freq_hz"])  # no-op: WSJT-X freq is already int Hz
    anchor_dt = float(row["anchor_dt"])
    raw_freq_hz = float(row["anchor_freq_hz"])  # unrounded, N4's fix, no-op for the same reason

    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return {"reason": "no_true_codeword"}

    try:
        rc0, llr_v0 = ex.extract_at(pcm, float(anchor_freq_int), anchor_dt)
        if rc0 != 0 or llr_v0 is None:
            return {"reason": "v0_extract_rc_%d" % rc0}

        pcm64 = np.asarray(pcm, dtype=np.float64)
        variants = extract_variants_ext(pcm64, raw_freq_hz, anchor_dt, df_hz=0.0)
        llr_v3 = list(variants["V3_cum"])
    except Exception as e:  # noqa: BLE001 -- unattended run over ~99k rows; record, don't crash
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
        "hd_disagree_v0_v3": hd_disagreement(llr_v0, llr_v3),
        "anchor_freq_hz": anchor_freq_int,
        "anchor_dt": anchor_dt,
    }


def decile_table(values: list[float]) -> dict:
    """Amendment A4.3: deciles, not a "within X pp of B50" count (that would be a new
    threshold). Empty-safe."""
    if not values:
        return {"n": 0, "deciles": []}
    arr = np.array(sorted(values))
    deciles = [float(np.percentile(arr, p)) for p in range(0, 101, 10)]
    return {"n": len(arr), "deciles": deciles}  # index i = (i*10)th percentile


def measure_corpus(ex: ExtractLLRs, corpus_name: str, log) -> dict:
    log("\n" + "=" * 90)
    log("Corpus: %s" % corpus_name)
    log("=" * 90)
    paths = corpus_paths(corpus_name)
    population = build_p_live_population(corpus_name)
    n_population = len(population)
    log("  population (WSJT-X decoded, we did not): n_rows=%d n_clusters=%d"
        % (n_population, len({r["ts"] for r in population})))

    wav_cache = WavCache(paths["wsjtx_wav_dir"])

    t0 = time.time()
    rows: list[dict] = []
    reasons: dict[str, int] = {}
    for i, row in enumerate(population):
        result = measure_row(ex, wav_cache, row)
        if result is None or "reason" in result:
            reason = result["reason"] if result else "none"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        rows.append(result)
        if (i + 1) % 5000 == 0:
            log("  ... %d/%d rows processed (%d measured, %.1fs elapsed)"
                % (i + 1, n_population, len(rows), time.time() - t0))
    elapsed = time.time() - t0
    n_clusters_measured = len({r["ts"] for r in rows})
    log("  measured %d/%d rows (%.1fs). drop reasons: %s"
        % (len(rows), n_population, elapsed, reasons))
    log("  n_clusters_measured=%d" % n_clusters_measured)

    median_v0_ber = float(st.median(r["ber_v0"] for r in rows)) if rows else float("nan")
    median_disagree = float(st.median(r["hd_disagree_v0_v3"] for r in rows)) if rows else float("nan")
    log("  median BER_V0=%.2f%%  median hd_disagree_v0_v3=%.1f/174 bits"
        % (median_v0_ber * 100 if rows else float("nan"), median_disagree))

    boot = cluster_bootstrap_f_cross_break_net(rows, n_draws=2000) if rows else None
    n_clusters_for_r3 = boot["n_clusters"] if boot else 0
    rule_of_three = (1.0 - 0.05 ** (1.0 / n_clusters_for_r3)) if n_clusters_for_r3 > 0 else float("nan")

    crossable_bers = [r["ber_v0"] for r in rows if r["ber_v0"] > B50_THRESHOLD]
    deciles = decile_table(crossable_bers)

    if boot is not None:
        log("  f_cross (n_crossable=%d/%d clusters=%d): point=%.4f%% CI95=[%.4f, %.4f]%%"
            % (boot["point"]["n_crossable"], boot["point"]["n_total"],
               boot["point"]["n_clusters_crossable"],
               boot["point"]["f_cross"] * 100 if not np.isnan(boot["point"]["f_cross"]) else float("nan"),
               boot["f_cross"]["ci95"][0] * 100, boot["f_cross"]["ci95"][1] * 100))
        log("  rule-of-three bound (n_clusters=%d): %.4f%%" % (n_clusters_for_r3, rule_of_three * 100))
        if boot["point"]["n_breakable"] >= MIN_BREAKABLE_FOR_DESCRIPTIVE:
            log("  f_break (n_breakable=%d/%d clusters=%d): point=%.4f%% CI95=[%.4f, %.4f]%%"
                % (boot["point"]["n_breakable"], boot["point"]["n_total"],
                   boot["point"]["n_clusters_breakable"], boot["point"]["f_break"] * 100,
                   boot["f_break"]["ci95"][0] * 100, boot["f_break"]["ci95"][1] * 100))
        else:
            log("  f_break: n_breakable=%d < %d -- DESCRIPTIVE ONLY (HK-021(j))"
                % (boot["point"]["n_breakable"], MIN_BREAKABLE_FOR_DESCRIPTIVE))
        log("  f_net (whole-population denom, n=%d): point=%+.4f%% CI95=[%+.4f, %+.4f]%%"
            % (boot["point"]["n_total"], boot["point"]["f_net"] * 100,
               boot["f_net"]["ci95"][0] * 100, boot["f_net"]["ci95"][1] * 100))

    return {
        "corpus": corpus_name,
        "n_population": n_population,
        "n_measured": len(rows),
        "n_clusters_measured": n_clusters_measured,
        "drop_reasons": reasons,
        "elapsed_s": elapsed,
        "median_v0_ber": median_v0_ber,
        "median_hd_disagree": median_disagree,
        "bootstrap": boot,
        "rule_of_three_bound": rule_of_three,
        "crossable_ber_deciles": deciles,
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DEFAULT_DLL_PATH)
    ap.add_argument("--dll-sha256", default=DEFAULT_DLL_SHA256)
    ap.add_argument("--limit-rows", type=int, default=None,
                     help="cap population to this many rows PER CORPUS (smoke runs only)")
    ap.add_argument("--corpus", action="append", default=None,
                     help="restrict to this corpus (repeatable); default = all 5")
    ap.add_argument("--n-draws", type=int, default=2000)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("P-LIVE STAGE 1 -- does order-3 coherent extraction CONVERT on the live-decode miss population?")
    log("=" * 90)

    log("\n[MANDATORY] Running BOTH sign unit tests fresh (ROW 0d, not inherited)...")
    log("-- (a) n5_stats_sign_test.py (f_break/f_net logic) --")
    rc_a = n5_stats_sign_test.main()
    log("-- (b) n4_sign_unit_test.py (V3_cum DSP correctness) --")
    rc_b = n4_sign_unit_test.main()
    if rc_a != 0 or rc_b != 0:
        log("\nROW 0d FIRES: sign unit test(s) failed (a=%d b=%d). Refusing to arm. NO VERDICT."
            % (rc_a, rc_b))
        _write_report(args.out_dir, {"final_row": "0d",
                                      "row_0d": {"fires": True, "rc_a": rc_a, "rc_b": rc_b}},
                       log_lines)
        return 1
    log("Both sign unit tests PASSED. Arming.\n")

    log("Loading DLL: %s" % args.dll_path)
    ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                      expected_shim_version=EXPECTED_SHIM_VERSION)
    log("DLL SHA256 asserted (%s...), shim version %d confirmed.\n"
        % (args.dll_sha256[:16], ex.version))

    corpora = args.corpus if args.corpus else ALL_CORPORA
    if args.limit_rows is not None:
        log("--limit-rows=%d applied PER CORPUS (SMOKE RUN, not a valid gate evaluation)"
            % args.limit_rows)

    per_corpus: dict[str, dict] = {}
    for name in corpora:
        if args.limit_rows is not None:
            pop = build_p_live_population(name)[: args.limit_rows]
            paths = corpus_paths(name)
            wav_cache = WavCache(paths["wsjtx_wav_dir"])
            rows, reasons = [], {}
            t0 = time.time()
            for row in pop:
                result = measure_row(ex, wav_cache, row)
                if result is None or "reason" in result:
                    reason = result["reason"] if result else "none"
                    reasons[reason] = reasons.get(reason, 0) + 1
                    continue
                rows.append(result)
            elapsed = time.time() - t0
            n_clusters_measured = len({r["ts"] for r in rows})
            log("\n[SMOKE %s] n_measured=%d/%d n_clusters=%d (%.1fs) drop=%s"
                % (name, len(rows), len(pop), n_clusters_measured, elapsed, reasons))
            boot = cluster_bootstrap_f_cross_break_net(rows, n_draws=args.n_draws) if rows else None
            per_corpus[name] = {
                "corpus": name, "n_population": len(pop), "n_measured": len(rows),
                "n_clusters_measured": n_clusters_measured, "drop_reasons": reasons,
                "elapsed_s": elapsed,
                "median_v0_ber": float(st.median(r["ber_v0"] for r in rows)) if rows else float("nan"),
                "median_hd_disagree": float(st.median(r["hd_disagree_v0_v3"] for r in rows)) if rows else float("nan"),
                "bootstrap": boot, "rule_of_three_bound": float("nan"),
                "crossable_ber_deciles": decile_table([r["ber_v0"] for r in rows if r["ber_v0"] > B50_THRESHOLD]),
                "rows": rows,
            }
        else:
            per_corpus[name] = measure_corpus(ex, name, log)

    result_bundle: dict = {"per_corpus": {}}
    all_rows_by_corpus: dict[str, list[dict]] = {}
    for name, d in per_corpus.items():
        all_rows_by_corpus[name] = d.pop("rows")
        result_bundle["per_corpus"][name] = d

    if PRIMARY_CORPUS not in per_corpus:
        log("\nPRIMARY_CORPUS (%s) not in the corpora run this time (--corpus filter?) -- "
            "no gate can be evaluated. Descriptive-only output written." % PRIMARY_CORPUS)
        result_bundle["final_row"] = "no_primary"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, all_rows_by_corpus)
        return 0

    primary = per_corpus[PRIMARY_CORPUS]
    log("\n" + "=" * 90)
    log("ROW 0c/0e/0f -- evaluated on PRIMARY (%s) ONLY, per Amendment A4.2" % PRIMARY_CORPUS)
    log("=" * 90)

    row0c_fires = (primary["n_measured"] < ROW_0C_MIN_ROWS
                   or primary["n_clusters_measured"] < ROW_0C_MIN_CLUSTERS)
    log("ROW 0c: n_measured=%d (>=%d) n_clusters=%d (>=%d) -> %s"
        % (primary["n_measured"], ROW_0C_MIN_ROWS, primary["n_clusters_measured"],
           ROW_0C_MIN_CLUSTERS, "FIRES" if row0c_fires else "clear"))
    result_bundle["row_0c"] = {"fires": row0c_fires, "n_measured": primary["n_measured"],
                                "n_clusters": primary["n_clusters_measured"]}
    if row0c_fires:
        log("\nROW 0c FIRES: PRECISION, escalate. NO VERDICT.")
        result_bundle["final_row"] = "0c"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, all_rows_by_corpus)
        return 2

    row0e_fires = primary["median_hd_disagree"] < ROW_0E_MIN_DISAGREE_BITS
    log("ROW 0e: median hd_disagree_v0_v3=%.1f/174 (floor %d) -> %s"
        % (primary["median_hd_disagree"], ROW_0E_MIN_DISAGREE_BITS,
           "FIRES" if row0e_fires else "clear"))
    result_bundle["row_0e"] = {"fires": row0e_fires,
                                "median_disagree_bits": primary["median_hd_disagree"],
                                "floor_bits": ROW_0E_MIN_DISAGREE_BITS}
    if row0e_fires:
        log("\nROW 0e FIRES: the contrast cannot move; no null is interpretable. "
            "VALIDITY, escalate. NO VERDICT.")
        result_bundle["final_row"] = "0e"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, all_rows_by_corpus)
        return 3

    row0f_target_lo = ROW_0F_TARGET - ROW_0F_TOL
    row0f_fires = primary["median_v0_ber"] < row0f_target_lo
    log("ROW 0f (Amendment A4.1): median BER_V0=%.2f%% vs floor %.2f%% (%.2f%%-%.0fpp) -> %s"
        % (primary["median_v0_ber"] * 100, row0f_target_lo * 100, ROW_0F_TARGET * 100,
           ROW_0F_TOL * 100, "FIRES" if row0f_fires else "clear"))
    result_bundle["row_0f"] = {"fires": row0f_fires, "median_v0_ber": primary["median_v0_ber"],
                                "floor": row0f_target_lo}
    if row0f_fires:
        log("\nROW 0f FIRES: P-LIVE primary median BER_V0 sits below N1/N5's own "
            "published band -- the assembly is not selecting the population Sec.2 "
            "defines. VALIDITY, escalate. NO VERDICT.")
        result_bundle["final_row"] = "0f"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, all_rows_by_corpus)
        return 4

    log("ROW 0c/0e/0f all clear on PRIMARY.\n")

    log("=" * 90)
    log("ROW 1/2/3 -- the confirmatory gate, evaluated on PRIMARY (%s) ONLY (Amendment A4.2)"
        % PRIMARY_CORPUS)
    log("=" * 90)
    pboot = primary["bootstrap"]
    ci_lo_cross, ci_hi_cross = pboot["f_cross"]["ci95"]
    ci_lo_net, _ci_hi_net = pboot["f_net"]["ci95"]
    row1_fires = ci_lo_cross > ROW_1_CI_LO_F_CROSS_MIN and ci_lo_net > 0.0
    row2_fires = (not row1_fires) and ci_hi_cross < ROW_2_CI_HI_F_CROSS_MAX

    if row1_fires:
        final_row = "1"
        log("ROW 1 FIRES: CI_lo(f_cross)=%.4f%% (>%.0f%%) AND CI_lo(f_net)=%+.4f%% (>0%%)."
            % (ci_lo_cross * 100, ROW_1_CI_LO_F_CROSS_MIN * 100, ci_lo_net * 100))
        log("CONSEQUENCE: limb 2 CONVERTS materially on the live-decode miss population "
            "-- C integration becomes scopeable and a proper sizing is ORDERED. Does NOT "
            "authorise building it.")
    elif row2_fires:
        final_row = "2"
        log("ROW 2 FIRES: CI_hi(f_cross)=%.4f%% (<%.0f%%)."
            % (ci_hi_cross * 100, ROW_2_CI_HI_F_CROSS_MAX * 100))
        log("CONSEQUENCE: limb 2's prize is upper-bounded below %.0f%% of the crossable "
            "population -- BOTH LIMBS close." % (ROW_2_CI_HI_F_CROSS_MAX * 100))
    else:
        final_row = "3"
        log("ROW 3 (residue -- CI straddles %.0f%%): CI(f_cross)=[%.4f, %.4f]%%, "
            "CI(f_net)=[%+.4f, %+.4f]%%." % (ROW_1_CI_LO_F_CROSS_MIN * 100, ci_lo_cross * 100,
                                              ci_hi_cross * 100, pboot["f_net"]["ci95"][0] * 100,
                                              pboot["f_net"]["ci95"][1] * 100))
        log("CONSEQUENCE: report the interval, do NOT pick a side.")

    log("\nRule-of-three bound on PRIMARY (n_clusters=%d): %.4f%% -- the headline if "
        "n_cross=0 (bootstrap CI is then degenerate by construction)."
        % (pboot["n_clusters"], primary["rule_of_three_bound"] * 100))

    log("\nAmendment A4.3 -- BER_V0 decile table over PRIMARY's crossable denominator "
        "(rows with BER_V0 > B50=%.1f%%), n=%d:"
        % (B50_THRESHOLD * 100, primary["crossable_ber_deciles"]["n"]))
    for i, v in enumerate(primary["crossable_ber_deciles"]["deciles"]):
        log("  p%d = %.2f%%" % (i * 10, v * 100))

    result_bundle["final_row"] = final_row
    result_bundle["gate_ci_f_cross"] = [ci_lo_cross, ci_hi_cross]
    result_bundle["gate_ci_f_net"] = pboot["f_net"]["ci95"]

    log("\n" + "=" * 90)
    log("EXTENSION CORPORA -- descriptive replication, gating nothing, never pooled")
    log("=" * 90)
    for name in EXTENSION_CORPORA:
        if name not in per_corpus:
            continue
        d = per_corpus[name]
        eboot = d["bootstrap"]
        if eboot is None:
            log("  [%s] n_measured=0 -- no bootstrap." % name)
            continue
        elo, ehi = eboot["f_cross"]["ci95"]
        log("  [%s] n_measured=%d clusters=%d median_BER_V0=%.2f%% f_cross=%.4f%% "
            "CI95=[%.4f,%.4f]%% rule-of-three=%.4f%%"
            % (name, d["n_measured"], d["n_clusters_measured"], d["median_v0_ber"] * 100,
               eboot["point"]["f_cross"] * 100 if not np.isnan(eboot["point"]["f_cross"]) else float("nan"),
               elo * 100, ehi * 100, d["rule_of_three_bound"] * 100))

    _write_report(args.out_dir, result_bundle, log_lines)
    _write_rows(args.out_dir, all_rows_by_corpus)
    log("\nWrote results/p_live_stage1_report.json, results/p_live_stage1_rows.json, "
        "results/p_live_stage1_run.log")
    return 0


def _write_rows(out_dir: str, all_rows_by_corpus: dict[str, list[dict]]) -> None:
    # every row dict already carries ONLY ts/corpus + numeric fields (measure_row
    # never stores message text past its own local scope) -- NFR-021.
    P.write_json(os.path.join(out_dir, "p_live_stage1_rows.json"), all_rows_by_corpus)


def _write_report(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "p_live_stage1_report.json"), bundle)
    with open(os.path.join(out_dir, "p_live_stage1_run.log"), "w", encoding="ascii",
              errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
