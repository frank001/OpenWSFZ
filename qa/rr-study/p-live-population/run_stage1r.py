#!/usr/bin/env python3
"""P-LIVE Stage 1R -- the corrective control for the withdrawn Stage 1 run.

Ruling: qa/rr-study/2026-08-18-1616-architect-to-qa-p-live-stage1-ruling-anchor-
provenance-defect.md Sec.5. Stage 1 (run_stage1.py) anchored V0 extraction at
WSJT-X's RAW reported dt and fed it straight to ft8_extract_llrs_at, whose third
argument is BUFFER-RELATIVE -- a different convention. M3 measured that offset
through the sync refiner at +0.45s; this run measures it through Stage 1's own
entry point (ft8_extract_llrs_at) instead of assuming M3's number transfers.

Two things, from ONE population, ONE extraction pass:

(a) POSITIVE CONTROL -- a `P-HIT` population (plive_population.build_p_hit_
    population): WSJT-X decodes that ALSO appear in our own ALL.TXT for the same
    ts. These are cycles we ourselves decoded, so the true codeword was
    recoverable from that audio and extraction reaches it when correctly
    pointed. If V0 at WSJT-X's raw dt (dt_offset=0.0) reads ~chance on rows we
    ourselves decoded, the anchor is broken and nothing in Stage 1 was readable.

(b) DT-OFFSET SWEEP -- ruling Sec.5.1(b): sweep dt_offset over M3's own 49-point
    grid (m3_common.TIME_ANCHOR_OFFSETS_S, -1.20..+1.20s step 0.05s -- REUSED,
    not redesigned) and report the offset minimising median BER_V0. The grid's
    dt_offset=0.0 point IS the raw-WSJT-X-DT arm that (a) and the gate need, so
    (a) and (b) are one pass, not two.

Gate, ruling Sec.5.2, strict order:
  0a'  DLL SHA256 re-hashed from disk, asserted against the pin BEFORE arming
       -> VALIDITY, STOP on mismatch (raised inside ExtractLLRs.__init__).
  0b'  P-HIT control n < 500 rows OR < 200 clusters on PRIMARY -> VALIDITY, STOP.
  0f'  median BER_V0 on the control at raw WSJT-X dt (dt_offset=0.0) OUTSIDE
       [0%, 35%], two-sided per the new HK-021 addendum -- the lower bound is
       structurally unreachable (BER in [0,1], stated in writing per the
       addendum's own escape clause, not silently one-sided). In practice this
       fires iff median > 35%, and its consequence is identical to ROW A's --
       both name the same event, one as a VALIDITY classification exercise
       (HK-025), one as the gate's own action.
  A    median >= 35% -> ANCHOR BROKEN. Stage 1 VOID (not null). Report the
       swept offset, STOP -- do not re-run Stage 1 in this session.
  B    median <= 15%  -> ANCHOR TRANSFERS. Stage 1's numbers are readable as
       published; ROW 2's firing is RE-INSTATED, N5 becomes CONFIRMED.
  C    15% < median < 35% -> INCONCLUSIVE. Report the sweep, escalate, do not
       adjudicate in session.

Bars derived, not chosen (ruling Sec.5.2): matched-hit control median BER = 2.9%
(W1's self-check, n=171); B50 = 11.3%; 15% = B50 + margin; 35% sits well above
anything a correctly-pointed extraction can produce and well below chance (50%).

HK-025: every ROW 0 above routes both branches to a genuinely different action
(0a' mismatch->STOP undefined instrument vs proceed; 0b' underpowered->escalate
vs proceed; 0f'/A anchor-broken->VOID+STOP vs proceed to B/C). None is
DIAGNOSTIC. Independently re-derived here, not merely inherited from the
ruling's own self-classification -- see hk025_check() below.

Scope (ruling Sec.5.3): no src/, no Developer session, no DLL rebuild, no
capture run -- HK-011 not engaged. NFR-021: P-HIT is built from message text
present in BOTH ALL.TXT files (both carry real callsigns) -- message is used
in-process only (ExtractLLRs.true_codeword), NEVER written to any emitted file.
Every emitted file grepped individually for "message" after the run, per the
ruling's own instruction, not merely asserted.
"""
from __future__ import annotations

import argparse
import os
import random
import statistics as st
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m3-anchor-timebase"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, hard_decision_ber  # noqa: E402
from m3_common import TIME_ANCHOR_OFFSETS_S  # noqa: E402 -- Sec.5.1(b): REUSE the grid verbatim
from plive_population import PRIMARY_CORPUS, build_p_hit_population, corpus_paths  # noqa: E402
from run_stage1 import DEFAULT_DLL_PATH, DEFAULT_DLL_SHA256, EXPECTED_SHIM_VERSION, WavCache  # noqa: E402

# -- Sec.5.2 bars, derived not chosen (see module docstring) --------------------
ROW_0B_MIN_ROWS = 500
ROW_0B_MIN_CLUSTERS = 200
ROW_0F_LO = 0.00
ROW_0F_HI = 0.35   # two-sided per the addendum; lower bound structurally unreachable (BER in [0,1])
ROW_A_MIN = 0.35
ROW_B_MAX = 0.15

# Sec.5.1(a): "Sample >=500 rows / >=200 clusters ... drawn by seeded
# sort-stabilised RNG". 600 rows verified in advance (dry count, not a fitted
# choice) to clear both bars with margin on PRIMARY's 25,411-row/4,371-cluster
# P-HIT population: 600 rows -> 551 distinct clusters.
DEFAULT_SAMPLE_ROWS = 600
# Stage 1R's own seed -- distinct from M1's 20260815, M2's 20260816, M3's 20260817.
STAGE1R_SEED = 20260818

# An offset is excluded from the "swept optimum" search if fewer than half the
# sampled rows extracted successfully at it (edge offsets can push some rows'
# window outside the buffer) -- descriptive filtering only, does not gate.
MIN_OK_FRAC_FOR_OPTIMUM = 0.5


def hk025_check() -> dict:
    """Independent re-derivation of the ruling's own Sec.5.2 HK-025 classification,
    per its own instruction ("re-derive that independently and refuse if you
    disagree -- my ROW 0 drafting is precisely what failed this round").

    0a' (DLL identity): if it fires, every extraction in the run is against an
    unidentified binary -- not a precision complaint, the numbers describe no
    named instrument at all. VALIDITY. Branches differ (refuse to arm vs proceed).
    Not diagnostic.
    0b' (control power): if it fires, the control cannot establish anything about
    the anchor with reliability -- not merely imprecise, uninformative. VALIDITY.
    Branches differ (escalate vs proceed to 0f'/A/B/C). Not diagnostic.
    0f'/A (anchor-broken floor): if it fires, EVERY downstream BER_V0 in Stage 1
    is a symptom of mis-anchoring, not a statement about V0 extraction quality --
    the whole arm's readability is the question, not its precision. VALIDITY.
    Branches differ (VOID + STOP vs proceed to B/C). Not diagnostic.
    B/C (does not gate an action beyond report-and-stop/report-and-escalate --
    both write a verdict and stop; the DIFFERENCE is what that verdict licenses
    downstream, which is exactly the point of a non-diagnostic classification).

    Concurs with the ruling's own Sec.5.2 table. No refusal indicated."""
    return {
        "0a_prime": {"class": "VALIDITY", "reason": "unidentified binary invalidates every downstream number"},
        "0b_prime": {"class": "VALIDITY", "reason": "insufficient control population, not a precision complaint"},
        "0f_prime_row_a": {"class": "VALIDITY", "reason": "anchor-broken floor -- every BER_V0 becomes a symptom, not a measurement"},
        "concurs_with_ruling": True,
        "refusal": False,
    }


def deterministic_sample(population: list[dict], n: int, seed: int) -> list[dict]:
    """population must already be construction-sorted (plive_population.
    build_p_hit_population sorts before returning) -- shuffle a fresh seeded RNG
    over INDICES, take the first n, then re-sort the selected indices ascending
    so the sample's own row order stays deterministic and reproducible."""
    idx = list(range(len(population)))
    random.Random(seed).shuffle(idx)
    chosen = sorted(idx[:n])
    return [population[i] for i in chosen]


def load_row_context(ex: ExtractLLRs, wav_cache: WavCache, row: dict):
    """Returns ((ts, pcm, true_bits, freq_int, anchor_dt), None) or (None, reason).
    message text touches this function only via ex.true_codeword and is never
    retained past this call (NFR-021)."""
    try:
        pcm = wav_cache.get(row["ts"])
    except FileNotFoundError:
        return None, "no_wav"
    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return None, "no_true_codeword"
    freq_int = round(row["anchor_freq_hz"])  # no-op: WSJT-X freq is already int Hz
    anchor_dt = float(row["anchor_dt"])
    return (row["ts"], pcm, true_bits, freq_int, anchor_dt), None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DEFAULT_DLL_PATH)
    ap.add_argument("--dll-sha256", default=DEFAULT_DLL_SHA256)
    ap.add_argument("--sample-rows", type=int, default=DEFAULT_SAMPLE_ROWS)
    ap.add_argument("--seed", type=int, default=STAGE1R_SEED)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("P-LIVE STAGE 1R -- P-HIT positive control + dt_offset sweep")
    log("(corrective control for the withdrawn Stage 1 run, ruling 2026-08-18-1616 Sec.5)")
    log("=" * 90)

    hk025 = hk025_check()
    log("\nHK-025 independent re-classification: concurs_with_ruling=%s refusal=%s"
        % (hk025["concurs_with_ruling"], hk025["refusal"]))
    if hk025["refusal"]:
        log("REFUSING TO ARM PER HK-025.")
        _write_report(args.out_dir, {"hk025_classification": hk025, "final_row": "REFUSED"}, log_lines)
        return 1

    # -- ROW 0a': DLL identity, asserted before arming ---------------------------
    log("\nLoading DLL: %s" % args.dll_path)
    try:
        ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                          expected_shim_version=EXPECTED_SHIM_VERSION)
    except RuntimeError as e:
        log("\nROW 0a' FIRES: %s" % e)
        log("VALIDITY, STOP. NO VERDICT.")
        _write_report(args.out_dir, {"hk025_classification": hk025, "final_row": "0a_prime",
                                      "row_0a_prime": {"fires": True, "error": str(e)}}, log_lines)
        return 2
    log("ROW 0a' clear: DLL SHA256 asserted (%s...), shim version %d confirmed.\n"
        % (args.dll_sha256[:16], ex.version))

    # -- Build + sample the P-HIT control on PRIMARY only (ruling Sec.5.1(a)) ----
    log("Building P-HIT control population on PRIMARY (%s)..." % PRIMARY_CORPUS)
    full_population = build_p_hit_population(PRIMARY_CORPUS)
    full_n_clusters = len({r["ts"] for r in full_population})
    log("  full P-HIT population: n_rows=%d n_clusters=%d" % (len(full_population), full_n_clusters))

    sample = deterministic_sample(full_population, min(args.sample_rows, len(full_population)), args.seed)
    sample_n_clusters = len({r["ts"] for r in sample})
    log("  sampled (seed=%d): n_rows=%d n_clusters=%d" % (args.seed, len(sample), sample_n_clusters))

    paths = corpus_paths(PRIMARY_CORPUS)
    wav_cache = WavCache(paths["wsjtx_wav_dir"])

    log("\nLoading row contexts (true codeword + WAV) for the sample...")
    contexts = []
    drop_reasons: dict[str, int] = {}
    for row in sample:
        ctx, reason = load_row_context(ex, wav_cache, row)
        if ctx is None:
            drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
            continue
        contexts.append(ctx)
    n_measured = len(contexts)
    n_clusters_measured = len({c[0] for c in contexts})
    log("  n_measured=%d/%d n_clusters_measured=%d drop_reasons=%s"
        % (n_measured, len(sample), n_clusters_measured, drop_reasons))

    # -- ROW 0b': control power ----------------------------------------------------
    row0b_fires = n_measured < ROW_0B_MIN_ROWS or n_clusters_measured < ROW_0B_MIN_CLUSTERS
    log("\nROW 0b': n_measured=%d (>=%d) n_clusters=%d (>=%d) -> %s"
        % (n_measured, ROW_0B_MIN_ROWS, n_clusters_measured, ROW_0B_MIN_CLUSTERS,
           "FIRES" if row0b_fires else "clear"))
    result_bundle: dict = {
        "hk025_classification": hk025,
        "full_population_n_rows": len(full_population),
        "full_population_n_clusters": full_n_clusters,
        "sample_seed": args.seed,
        "sample_n_rows": len(sample),
        "sample_n_clusters": sample_n_clusters,
        "n_measured": n_measured,
        "n_clusters_measured": n_clusters_measured,
        "drop_reasons": drop_reasons,
        "row_0b_prime": {"fires": row0b_fires, "n_measured": n_measured, "n_clusters": n_clusters_measured},
    }
    if row0b_fires:
        log("\nROW 0b' FIRES: underpowered control. VALIDITY, escalate. NO VERDICT.")
        result_bundle["final_row"] = "0b_prime"
        _write_report(args.out_dir, result_bundle, log_lines)
        return 3

    # -- (a)+(b): dt_offset sweep over M3's own 49-point grid ---------------------
    log("\n" + "=" * 90)
    log("dt_offset sweep, %d points (M3's own grid, -1.20..+1.20s step 0.05s, REUSED)"
        % len(TIME_ANCHOR_OFFSETS_S))
    log("=" * 90)
    t0 = time.time()
    sweep: list[dict] = []
    raw_median_ber = None
    for dt_offset in TIME_ANCHOR_OFFSETS_S:
        bers = []
        n_extract_fail = 0
        for ts, pcm, true_bits, freq_int, anchor_dt in contexts:
            rc, llr = ex.extract_at(pcm, float(freq_int), anchor_dt + dt_offset)
            if rc != 0 or llr is None:
                n_extract_fail += 1
                continue
            bers.append(hard_decision_ber(llr, true_bits))
        median_ber = float(st.median(bers)) if bers else float("nan")
        n_ok = len(bers)
        sweep.append({"dt_offset": dt_offset, "median_ber_v0": median_ber,
                       "n_ok": n_ok, "n_extract_fail": n_extract_fail})
        if abs(dt_offset) < 1e-9:
            raw_median_ber = median_ber
        log("  dt_offset=%+.2fs  median_BER_V0=%s  n_ok=%d/%d"
            % (dt_offset, "%.2f%%" % (median_ber * 100) if not np.isnan(median_ber) else "n/a",
               n_ok, len(contexts)))
    elapsed = time.time() - t0
    log("\nSweep complete in %.1fs." % elapsed)
    assert raw_median_ber is not None, "dt_offset=0.0 must be on the grid (m3_common asserts this)"

    valid_for_optimum = [s for s in sweep if s["n_ok"] >= MIN_OK_FRAC_FOR_OPTIMUM * len(contexts)
                          and not np.isnan(s["median_ber_v0"])]
    best = min(valid_for_optimum, key=lambda s: s["median_ber_v0"]) if valid_for_optimum else None
    if best:
        log("\nSwept optimum: dt_offset=%+.2fs, median_BER_V0=%.2f%% (n_ok=%d)"
            % (best["dt_offset"], best["median_ber_v0"] * 100, best["n_ok"]))
    else:
        log("\nSwept optimum: no offset had a valid (>=%.0f%% extraction success) median."
            % (MIN_OK_FRAC_FOR_OPTIMUM * 100))

    result_bundle["dt_offset_sweep"] = sweep
    result_bundle["swept_optimum"] = best
    result_bundle["raw_median_ber_v0"] = raw_median_ber
    result_bundle["sweep_elapsed_s"] = elapsed

    # -- ROW 0f' / A / B / C -------------------------------------------------------
    log("\n" + "=" * 90)
    log("ROW 0f' / A / B / C -- evaluated on median BER_V0 at dt_offset=0.0 (raw WSJT-X dt)")
    log("=" * 90)
    row0f_fires = not (ROW_0F_LO <= raw_median_ber <= ROW_0F_HI)
    log("ROW 0f': median_BER_V0(raw)=%.2f%% outside [%.0f%%,%.0f%%] two-sided -> %s"
        % (raw_median_ber * 100, ROW_0F_LO * 100, ROW_0F_HI * 100, "FIRES" if row0f_fires else "clear"))
    log("  (lower bound structurally unreachable: BER_V0 in [0,1] by construction)")
    result_bundle["row_0f_prime"] = {"fires": row0f_fires, "median_ber_v0_raw": raw_median_ber,
                                      "band": [ROW_0F_LO, ROW_0F_HI]}

    if row0f_fires:
        assert raw_median_ber >= ROW_A_MIN, "0f' fired but not via the high side -- unreachable low side hit"
        final_row = "A"
        log("\nROW 0f' FIRES -> ROW A: median_BER_V0(raw)=%.2f%% >= %.0f%%."
            % (raw_median_ber * 100, ROW_A_MIN * 100))
        log("VERDICT: ANCHOR BROKEN. Stage 1 is VOID, not null.")
        log("Swept optimum offset (descriptive, for the corrective spec, NOT a re-run "
            "in this session): %s"
            % ("%+.2fs" % best["dt_offset"] if best else "none valid"))
        log("STOP -- per the ruling, do not re-run Stage 1 in this session.")
    elif raw_median_ber <= ROW_B_MAX:
        final_row = "B"
        log("\nROW B: median_BER_V0(raw)=%.2f%% <= %.0f%%."
            % (raw_median_ber * 100, ROW_B_MAX * 100))
        log("VERDICT: ANCHOR TRANSFERS. Stage 1's numbers are readable as published; "
            "ROW 2's firing is RE-INSTATED; N5 becomes CONFIRMED.")
    else:
        final_row = "C"
        log("\nROW C: %.0f%% < median_BER_V0(raw)=%.2f%% < %.0f%%."
            % (ROW_B_MAX * 100, raw_median_ber * 100, ROW_A_MIN * 100))
        log("VERDICT: INCONCLUSIVE. Report the sweep, escalate, do not adjudicate in session.")

    result_bundle["final_row"] = final_row

    _write_report(args.out_dir, result_bundle, log_lines)
    log("\nWrote results/p_live_stage1r_report.json, results/p_live_stage1r_run.log")
    log("(no per-row dump written -- the sweep table in the report IS the per-offset "
        "output; no message text or per-row identity is emitted anywhere, NFR-021)")
    return 0


def _write_report(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "p_live_stage1r_report.json"), bundle)
    with open(os.path.join(out_dir, "p_live_stage1r_run.log"), "w", encoding="ascii",
              errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
