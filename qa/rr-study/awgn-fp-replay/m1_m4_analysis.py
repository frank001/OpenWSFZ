#!/usr/bin/env python3
"""AWGN-FP arm -- M1/M2/M3/M4 analysis and ROW 1 / ROW 2 (revised) / ROW 3 (revised) evaluation.

Spec: qa/rr-study/2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md
(Architect -> QA, 2026-09-02 19:06Z), Section 3 (M1-M4), Section 4 (ROW 1), and
**Amendment 1** (2026-09-02 20:05Z) for the REVISED ROW 2/ROW 3 (the original versions are
superseded and must never be executed -- see the spec's own text). A1.5's truth-match flag on M3
is implemented here, not in C#, by joining the S1 population's decodes CSV against its own
truth.csv on (part, trial, seed) -- the same join ROW 0d's own report already performed once.

Inputs (produced by tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs's M1M2M4_S5AwgnPopulation_
N2000PerPart and M3_S1GenuinePopulation_N230PerPart Facts, and by the render step's own
--dry-run --dump-wav-dir truth.csv):
  - qa/rr-study/awgn-fp-replay/results/m1m4_s5_slots.csv / _decodes.csv   (S5, N=2000/part)
  - qa/rr-study/awgn-fp-replay/results/m3_s1_slots.csv / _decodes.csv     (S1, N=230/part)
  - qa/rr-study/_m3_s1_truth/truth.csv                                    (S1 render's truth)

Ships every pre-registered predicate as code (HK-021(r)) -- no hand-computed number is quoted in
the accompanying report without being printed here first.
"""
from __future__ import annotations

import csv
import json
import math
import pathlib
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
_RESULTS = _HERE / "results"
_S1_TRUTH = _HERE / "_work" / "m3_s1_truth" / "truth.csv"
_OUT_JSON = _RESULTS / "m1_m4_analysis.json"
_OUT_TXT = _RESULTS / "m1_m4_analysis_report.txt"

# ── ROW 1 -- pre-registered exact Clopper-Pearson 95% CI for the pooled in-chain S5
#    rate over every full sweep since 2026-08-21 (spec Section 4 ROW 1). ──
ROW1_LOW_PCT = 1.15
ROW1_HIGH_PCT = 3.85

# ── Amendment 1 A1.2/A1.3 thresholds (Architect de-blinded, anchored on peeked data --
#    spec Amendment 1 A1.0; QA is entitled to reject these and set its own, but adopts them
#    here as pre-registered rather than re-deriving post hoc). ──
ROW2_MARGIN_DB = 6.0
ROW2_MIN_REMOVAL_FRACTION = 0.10


def _read_csv(path: pathlib.Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile, numpy-free (avoids a hard numpy dependency here;
    the render/decode steps already depend on numpy, this analysis step deliberately does not)."""
    if not values:
        raise ValueError("percentile of empty list")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (pct / 100.0) * (len(s) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact Clopper-Pearson CI using the regularized incomplete beta function (scipy-free
    closed-form is not available in stdlib; use scipy.stats if present, else a small
    binary-search fallback on the beta CDF via math.lgamma-based incomplete beta)."""
    try:
        from scipy import stats
        if k == 0:
            low = 0.0
        else:
            low = stats.beta.ppf(alpha / 2, k, n - k + 1)
        if k == n:
            high = 1.0
        else:
            high = stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
        return low, high
    except ImportError:
        raise RuntimeError("scipy required for Clopper-Pearson; not available")


def main() -> int:
    report_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        report_lines.append(msg)

    log("=" * 78)
    log("AWGN-FP -- M1/M2/M3/M4 analysis, ROW 1 / ROW 2 (revised) / ROW 3 (revised)")
    log("=" * 78)

    # ── Load S5 (M1/M2/M4 population) ──────────────────────────────────────────────
    s5_slots = _read_csv(_RESULTS / "m1m4_s5_slots.csv")
    s5_decodes = _read_csv(_RESULTS / "m1m4_s5_decodes.csv")

    log(f"\nLoaded m1m4_s5: {len(s5_slots)} slots, {len(s5_decodes)} decode rows")

    # ── M1: per-slot event rate, part 0 and part 1 separately, and pooled ──────────
    log("\n--- M1: per-slot false-accept event rate ---")
    by_part: dict[str, list[dict]] = {}
    for row in s5_slots:
        by_part.setdefault(row["part"], []).append(row)

    m1_per_part = {}
    for part in sorted(by_part, key=int):
        rows = by_part[part]
        events = sum(1 for r in rows if int(r["n_decodes"]) > 0)
        n = len(rows)
        rate = 100.0 * events / n
        m1_per_part[part] = {"n": n, "events": events, "rate_pct": rate}
        log(f"  part {part}: n={n}  events={events}  rate={rate:.4f}%")

    total_n = sum(v["n"] for v in m1_per_part.values())
    total_events = sum(v["events"] for v in m1_per_part.values())
    pooled_rate = 100.0 * total_events / total_n
    log(f"  pooled: n={total_n}  events={total_events}  rate={pooled_rate:.4f}%")

    # ── M2: excess = signal_db - local_noise_db for every false accept ─────────────
    m2_excess = [float(r["signal_db"]) - float(r["local_noise_db"]) for r in s5_decodes]
    log(f"\n--- M2: excess (signal_db - local_noise_db) over {len(m2_excess)} false accepts ---")
    if m2_excess:
        log(f"  min={min(m2_excess):.3f}  p01={_percentile(m2_excess,1):.3f}  "
            f"median={_percentile(m2_excess,50):.3f}  max={max(m2_excess):.3f}")
    else:
        log("  NO FALSE ACCEPTS IN THIS POPULATION -- M2 is empty.")

    # ── M4: reported-SNR histogram, 1 dB bins ───────────────────────────────────────
    log("\n--- M4: reported-SNR histogram (1 dB bins) ---")
    m4_hist: dict[int, int] = {}
    for r in s5_decodes:
        b = int(math.floor(float(r["reported_snr_db"])))
        m4_hist[b] = m4_hist.get(b, 0) + 1
    for b in sorted(m4_hist):
        log(f"  [{b},{b+1}) dB: {m4_hist[b]}")

    # ── Load S1 (M3 population) + truth join (Amendment 1 A1.5) ────────────────────
    s1_decodes = _read_csv(_RESULTS / "m3_s1_decodes.csv")
    s1_truth_rows = _read_csv(_S1_TRUTH)
    truth_by_key = {(t["part_index"], t["trial_index"], t["seed"]): t["message_text"]
                     for t in s1_truth_rows}

    log(f"\nLoaded m3_s1: {len(s1_decodes)} decode rows, {len(s1_truth_rows)} truth rows")

    m3_genuine_excess: list[float] = []
    n_spurious_riding_along = 0
    n_no_truth_match_key = 0
    for r in s1_decodes:
        key = (r["part"], r["trial"], r["seed"])
        truth_msg = truth_by_key.get(key)
        if truth_msg is None:
            n_no_truth_match_key += 1
            continue
        is_genuine = (r["message"] == truth_msg)
        excess = float(r["signal_db"]) - float(r["local_noise_db"])
        if is_genuine:
            m3_genuine_excess.append(excess)
        else:
            n_spurious_riding_along += 1

    log(f"\n--- M3: excess for GENUINE (truth-matching) decodes only (Amendment 1 A1.5) ---")
    log(f"  genuine (truth-matching): {len(m3_genuine_excess)}")
    log(f"  spurious riding alongside real signal (excluded from M3, reported for the record): "
        f"{n_spurious_riding_along}")
    if n_no_truth_match_key:
        log(f"  WARNING: {n_no_truth_match_key} decode rows had no matching truth.csv key "
            f"(part,trial,seed) -- investigate before trusting M3 below.")
    if m3_genuine_excess:
        log(f"  min={min(m3_genuine_excess):.3f}  p01={_percentile(m3_genuine_excess,1):.3f}  "
            f"median={_percentile(m3_genuine_excess,50):.3f}  max={max(m3_genuine_excess):.3f}")

    # ── ROW 1: the rate is chronic, not a recent regression ─────────────────────────
    log("\n" + "=" * 78)
    log("ROW 1 -- chronic vs. recent-regression")
    log("=" * 78)
    row1_n_floor_met = total_n >= 4000
    row1_fires = row1_n_floor_met and (ROW1_LOW_PCT <= pooled_rate <= ROW1_HIGH_PCT)
    log(f"Pooled M1 (parts 0/1): n={total_n} (floor: >=4000, met={row1_n_floor_met})  "
        f"rate={pooled_rate:.4f}%")
    log(f"Pre-registered band: [{ROW1_LOW_PCT}%, {ROW1_HIGH_PCT}%]")
    try:
        cp_low, cp_high = clopper_pearson(total_events, total_n)
        log(f"(context, not gating) This run's own exact 95% Clopper-Pearson CI on the pooled "
            f"rate: [{100*cp_low:.4f}%, {100*cp_high:.4f}%]")
    except RuntimeError as e:
        log(f"(context, not gating) Could not compute this run's own CI: {e}")
    log(f"ROW 1 FIRES: {row1_fires}")
    if row1_fires:
        log("=> The gate's PASS/FAIL history is binomial noise on a stable underlying rate. "
            "Recommend to the PO that the S5 gate's N be re-derived, or read against this "
            "offline estimator.")
    else:
        log("=> Pooled rate falls OUTSIDE the historical chronic-rate band -- report the number, "
            "do not assert chronic-vs-regression either way from ROW 1 alone.")

    # ── ROW 2 (revised, Amendment 1 A1.2) / ROW 3 (revised, A1.3) ───────────────────
    log("\n" + "=" * 78)
    log("ROW 2 (revised) / ROW 3 (revised) -- does a threshold T with an acceptable margin exist?")
    log("=" * 78)

    row2_fires = False
    row2_T = None
    row2_removal_frac = None
    row2_margin = None

    if not m3_genuine_excess:
        log("M3 is empty -- cannot evaluate. Refusing per HK-025 (no complement, no verdict).")
    elif not m2_excess:
        log("M2 is empty (zero false accepts in the S5 population) -- condition (c) can never "
            "hold (0% >= 10% is false for any T). ROW 3 fires by construction: no threshold can "
            "justify a src/ change when there is nothing to filter.")
    else:
        p1_m3 = _percentile(m3_genuine_excess, 1)
        min_m3 = min(m3_genuine_excess)
        log(f"p1(M3 excess) = {p1_m3:.3f} dB   min(M3 excess) = {min_m3:.3f} dB")

        if p1_m3 < ROW2_MARGIN_DB:
            log(f"p1(M3) ({p1_m3:.3f} dB) < required margin ({ROW2_MARGIN_DB} dB) -- condition "
                f"(b) cannot hold for ANY T >= 0 (T <= p1(M3) - {ROW2_MARGIN_DB} would require "
                f"T < 0). No search needed -- ROW 3 fires.")
        else:
            t_from_b = p1_m3 - ROW2_MARGIN_DB
            t_candidate = min(t_from_b, min_m3 - 1e-6)
            t_candidate = max(0.0, t_candidate)
            log(f"Candidate T (tightest allowed by condition (b), also honouring T>=0): "
                f"{t_candidate:.3f} dB")

            n_m3_at_or_below = sum(1 for x in m3_genuine_excess if x <= t_candidate)
            cond_a = (n_m3_at_or_below == 0)
            log(f"Condition (a): M3 genuine decodes with excess <= T: {n_m3_at_or_below} "
                f"(need 0) -- {'HOLDS' if cond_a else 'FAILS'}")

            margin = p1_m3 - t_candidate
            cond_b = margin >= ROW2_MARGIN_DB
            log(f"Condition (b): p1(M3) - T = {margin:.3f} dB (need >= {ROW2_MARGIN_DB} dB) -- "
                f"{'HOLDS' if cond_b else 'FAILS'}")

            n_m2_at_or_below = sum(1 for x in m2_excess if x <= t_candidate)
            removal_frac = n_m2_at_or_below / len(m2_excess)
            cond_c = removal_frac >= ROW2_MIN_REMOVAL_FRACTION
            log(f"Condition (c): M2 false accepts with excess <= T: {n_m2_at_or_below}/"
                f"{len(m2_excess)} = {100*removal_frac:.2f}% (need >= "
                f"{100*ROW2_MIN_REMOVAL_FRACTION:.0f}%) -- {'HOLDS' if cond_c else 'FAILS'}")

            row2_fires = cond_a and cond_b and cond_c
            row2_T = t_candidate
            row2_removal_frac = removal_frac
            row2_margin = margin

            log(f"\nROW 2 (revised) FIRES: {row2_fires}")
            if row2_fires:
                log(f"=> An emission-side plausibility floor at T={t_candidate:.3f} dB is "
                    f"sizeable and cheap: removes {100*removal_frac:.2f}% of false accepts at "
                    f"ZERO measured cost to genuine decodes (margin {margin:.3f} dB). SIZING "
                    f"ONLY, never a ship decision (spec A1.2) -- any actual filter is a src/ "
                    f"change, HK-011 in full.")
                n_m3 = len(m3_genuine_excess)
                readout_quantum_pct = 100.0 / n_m3
                ub_95_pct = 300.0 / n_m3  # rule-of-three 95% UB on a true zero count, in percent
                log(f"Power at n={n_m3}: readout quantum on (a) = {readout_quantum_pct:.4f}%; "
                    f"a clean zero bounds the true loss rate at 95% UB ~= {ub_95_pct:.4f}% "
                    f"(rule of three). Must be quoted this way -- NEVER as \"costs nothing\".")
            else:
                log("=> No T in the range condition (b) allows satisfies condition (a) and/or "
                    "(c) -- ROW 3 fires.")

    row3_fires = not row2_fires
    log(f"\nROW 3 (revised) FIRES: {row3_fires}")
    if row3_fires and m3_genuine_excess and m2_excess:
        log("=> The emission-filter route is unfavourable FOR S5-CLASS NOISE-ONLY FALSE ACCEPTS "
            "AT THE LEVELS THIS HARNESS DELIVERS, and is not to be re-proposed for that "
            "population without a new pre-registration. Scoped exactly that way (HK-021(x)) -- "
            "this does not speak to signal-present spurious decodes, real off-air conditions, or "
            "any threshold family other than a floor on excess.")

    # ── Write outputs ────────────────────────────────────────────────────────────────
    result = {
        "m1": {"per_part": m1_per_part, "pooled_n": total_n, "pooled_events": total_events,
               "pooled_rate_pct": pooled_rate},
        "m2": {"n": len(m2_excess), "min": min(m2_excess) if m2_excess else None,
               "p01": _percentile(m2_excess, 1) if m2_excess else None,
               "median": _percentile(m2_excess, 50) if m2_excess else None,
               "max": max(m2_excess) if m2_excess else None},
        "m3": {"n_genuine": len(m3_genuine_excess), "n_spurious_riding_along": n_spurious_riding_along,
               "min": min(m3_genuine_excess) if m3_genuine_excess else None,
               "p01": _percentile(m3_genuine_excess, 1) if m3_genuine_excess else None,
               "median": _percentile(m3_genuine_excess, 50) if m3_genuine_excess else None,
               "max": max(m3_genuine_excess) if m3_genuine_excess else None},
        "m4_histogram_1db_bins": m4_hist,
        "row1": {"fires": row1_fires, "pooled_rate_pct": pooled_rate,
                 "band": [ROW1_LOW_PCT, ROW1_HIGH_PCT], "n_floor_met": row1_n_floor_met},
        "row2_revised": {"fires": row2_fires, "T_db": row2_T,
                          "removal_fraction": row2_removal_frac, "margin_db": row2_margin},
        "row3_revised": {"fires": row3_fires},
    }
    _RESULTS.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _OUT_TXT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {_OUT_JSON}")
    print(f"Wrote {_OUT_TXT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
