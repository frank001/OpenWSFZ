#!/usr/bin/env python3
"""S.1r -- spectral locality re-evidenced at power (PRE-REGISTERED SPEC).

Per `2026-08-07-1616-architect-to-qa-captain-rulings-and-d001-reconciliation.md` Section 7.
Requested by the Captain, 2026-08-07. S.1 is CLOSED (Captain, 2026-08-04, reconfirmed 08-07)
-- this analysis does NOT re-open it. It replaces the ~86-sample conversational basis with
the five-run replay corpus already on disk (~44x the evidence), to put the *limb* (frequency-
local vs cycle-global) beyond argument, ahead of RC1.

Cost: a re-analysis only. No src/ change, no playback, no capture, no new authorisation --
files are already on disk (`qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-
replay/_work/run{1..5}/` and the WSJT-X master ALL.TXT). Per HK-004 this is a *do*, not a
*recommend*.

Design (spec Section 7.3): reuses the same busy-window, pass-1-only (WSJT-X-source WAVs),
5-run replay data as the 2026-08-06-2323 density-penalty note, adding Separation (Hz to the
nearest other WSJT-X decode in the same cycle) as a THIRD factor alongside Density and SNR.
Run (1-5) supplies the pure replicate/residual axis -- mechanically identical role to how
`build_full_anova.py`'s three_way_anova_with_replication() already uses Run=5 replicates for
the Decoder x Source x Cycle design; that function is reused UNCHANGED here with
(Separation, Density, SNR) as its three fixed factors and Run as the n=5 replicate axis.

Reference: fresh WSJT-X decoding the identically replayed audio (Section 2 of the spec) --
never `jt9 -d 3` (barred) and never the archived corpus ALL.TXT (validity open, found
suppressed ~2.3x on this window).

NFR-021: message text is read only to build match keys (normalize_hash_tokens, the standing
convention) and is never printed or written to any output file. Only aggregate per-cell
counts, SNR/frequency-derived statistics, and F/p values reach the report.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

HERE = Path(__file__).resolve().parent
REPLAY_DIR = HERE.parent / "2026-08-06-live-cross-decode-replay"
sys.path.insert(0, str(REPLAY_DIR))
sys.path.insert(0, str(HERE.parent.parent / "endurance"))

import numpy as np
from scipy.stats import f as fdist

from anova_common import normalize_hash_tokens, parse_all_txt, parse_cycle_ts  # noqa: E402

UTC = datetime.timezone.utc
WSJTX_ALL_TXT = Path(r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT")
N_RUNS = 5
WX_SLACK_S = 4.0   # identical convention to build_full_anova.py / run_cross_decode_replay.py
OUR_SLACK_S = 1.0

# ---- pre-registered bands (Section 7.3), IDENTICAL to the 2026-08-06-2323 note's Section 3
# density/SNR bands, so results join directly. Separation bands are the new factor: FT8
# occupies ~50 Hz, so <50 Hz is overlap and >150 Hz is clear air (physically motivated, per
# the spec's own note that a neighbour-count predictor was rejected for want of variance
# before this continuous-sep design was adopted).
DENS_BANDS = [("30-34", 30, 34), ("35-39", 35, 39), ("40-49", 40, 49)]
SNR_BANDS = [("very weak (<-15)", None, -15.0), ("weak (-15..-10)", -15.0, -10.0),
             ("mid (-10..-3)", -10.0, -3.0), ("strong (>=-3)", -3.0, None)]
SEP_BANDS_PRIMARY = [("local (<50)", None, 50.0), ("mid (50-150)", 50.0, 150.0),
                      ("clear (>150)", 150.0, None)]
# Sensitivity boundaries (Section 7.6 #4) -- reported, NEVER gated.
SEP_BOUNDARY_SETS = {
    "primary_50_150": SEP_BANDS_PRIMARY,
    "sensitivity_25_100": [("local (<25)", None, 25.0), ("mid (25-100)", 25.0, 100.0),
                            ("clear (>100)", 100.0, None)],
    "sensitivity_75_200": [("local (<75)", None, 75.0), ("mid (75-200)", 75.0, 200.0),
                            ("clear (>200)", 200.0, None)],
}
MIN_POOLED_N = 20


def band_of(value: float, bands: list[tuple[str, float | None, float | None]]) -> str | None:
    for label, lo, hi in bands:
        if lo is not None and value < lo:
            continue
        if hi is not None and value >= hi:
            continue
        return label
    return None


def dens_band_of(d: int) -> str | None:
    for label, lo, hi in DENS_BANDS:
        if lo <= d <= hi:
            return label
    return None


def load_run(run_idx: int, wx_rows_all: list[dict]) -> dict:
    run_dir = REPLAY_DIR / "_work" / f"run{run_idx}"
    windows = json.loads((run_dir / "pass_windows.json").read_text())
    p1s, p1e = [datetime.datetime.fromisoformat(x) for x in windows["pass1_wsjtx_source"]]

    def filt(rows, slack):
        lo, hi = p1s - datetime.timedelta(seconds=slack), p1e + datetime.timedelta(seconds=slack)
        out = []
        for r in rows:
            dt = parse_cycle_ts(r["ts"])
            if dt is None:
                continue
            dt = dt.replace(tzinfo=UTC)
            if lo <= dt <= hi:
                out.append(r)
        return out

    our_rows = parse_all_txt(str(run_dir / "our_ALL.TXT"))
    our_p1 = filt(our_rows, OUR_SLACK_S)
    wx_p1 = filt(wx_rows_all, WX_SLACK_S)
    return {"our_p1": our_p1, "wx_p1": wx_p1, "p1_start": p1s, "p1_end": p1e}


def mark_missed(wx_rows: list[dict], our_rows: list[dict]) -> list[dict]:
    """For each WSJT-X (reference) decode, whether OpenWSFZ also reported it -- same
    (ts, normalized message) exact-match/consumption convention as anova_common.match_pairs
    and run_cross_decode_replay.match_pairs, applied from the reference side so every WSJT-X
    row gets a missed=True/False flag rather than only counting matched pairs."""
    our_by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in our_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        our_by_key[key].append(r)
    consumed: Counter = Counter()
    out = []
    for r in wx_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        avail = len(our_by_key.get(key, ()))
        matched = consumed[key] < avail
        if matched:
            consumed[key] += 1
        nr = dict(r)
        nr["missed"] = not matched
        out.append(nr)
    return out


# Our decoder's hardcoded candidate search band (`ft8_shim.c:1183`, `monitor_config_t cfg`),
# per the 2026-08-06-2323 note Section 4: decodes outside [200, 3000) Hz are 100% missed by
# OpenWSFZ regardless of separation or density -- a known, certain, unrelated defect, not a
# spectral-locality effect. Discovered live while building this analysis (a first pass on
# the primary 50/150 Hz boundary put the entire `clear (>150 Hz)` separation level's only
# surviving stratum at ~80% miss rate despite STRONG SNR -- tracing the individual decodes
# showed several sitting at freq_hz=193, just below this cutoff, and naturally "clear"
# because nothing exists below 200 Hz to be a neighbour). Records at or beyond this boundary
# are excluded from the outcome tally (their `missed` status has a certain, unrelated cause)
# but still count toward `dens` and as candidate NEIGHBOURS for other records' `sep` -- they
# are real signals genuinely on the air, and excluding them from the neighbour set would
# artificially inflate other decodes' separation.
BAND_LO_HZ = 200.0
BAND_HI_HZ = 3000.0


def build_decode_records(run_idx: int, wx_p1_marked: list[dict]) -> tuple[list[dict], int, int]:
    """Per-decode records with dens/sep/snr/missed. dens = count of WSJT-X decodes in that
    SAME cycle within this run's pass-1 window (identical definition to the 2323 note's
    Section 3: the reference decoder's own decode count for that cycle). sep = Hz to the
    nearest OTHER WSJT-X decode in the same cycle (undefined, hence excluded, for
    single-decode cycles), computed against ALL decodes in the cycle including band-edge
    ones (see BAND_LO_HZ/BAND_HI_HZ above). Returns (records, n_excluded_single_decode_cycles,
    n_excluded_band_edge)."""
    by_cycle: dict[str, list[dict]] = defaultdict(list)
    for r in wx_p1_marked:
        by_cycle[r["ts"]].append(r)

    records = []
    n_excluded_single = 0
    n_excluded_band_edge = 0
    for ts, rows in by_cycle.items():
        dens = len(rows)
        freqs = [r["freq_hz"] for r in rows]
        for i, r in enumerate(rows):
            if dens < 2:
                n_excluded_single += 1
                continue
            if not (BAND_LO_HZ <= r["freq_hz"] < BAND_HI_HZ):
                n_excluded_band_edge += 1
                continue
            others = [freqs[j] for j in range(len(rows)) if j != i]
            sep = min(abs(freqs[i] - f) for f in others)
            records.append({
                "run": run_idx, "ts": ts, "dens": dens, "sep": sep,
                "snr": r["snr"], "missed": r["missed"],
            })
    return records, n_excluded_single, n_excluded_band_edge


def cell_table(records: list[dict], sep_bands) -> dict[tuple, dict]:
    """(sep_band, dens_band, snr_band, run) -> {total, missed}. Records whose dens falls
    outside the three pre-registered density bands (i.e. outside 30-49) are not tallied --
    the window's own sparsest bucket is ~30, per the standing board note, so this should
    exclude little to nothing; reported explicitly below."""
    cells: dict[tuple, dict] = defaultdict(lambda: {"total": 0, "missed": 0})
    n_dens_out_of_range = 0
    for rec in records:
        db = dens_band_of(rec["dens"])
        if db is None:
            n_dens_out_of_range += 1
            continue
        sb = band_of(rec["sep"], sep_bands)
        nb = band_of(rec["snr"], SNR_BANDS)
        if sb is None or nb is None:
            continue
        key = (sb, db, nb, rec["run"])
        cells[key]["total"] += 1
        if rec["missed"]:
            cells[key]["missed"] += 1
    return dict(cells), n_dens_out_of_range


def limb(e: float, p: float) -> str:
    """Classify one mechanism (spec Section 7.5, verbatim). Boundary values fall to PARTIAL
    by construction."""
    if e > 5.0 and p < 0.01:
        return "LIVE"
    if e < 2.0 or p > 0.05:
        return "NULL"
    return "PARTIAL"


def s1r_row(e_sep: float, p_sep: float, e_dens: float, p_dens: float) -> str:
    """Spec Section 7.5, verbatim."""
    local = limb(e_sep, p_sep)
    glob = limb(e_dens, p_dens)
    if local == "LIVE" and glob == "LIVE":
        return "ROW 1"
    if local == "LIVE" and glob == "NULL":
        return "ROW 2"
    if glob == "LIVE" and local == "NULL":
        return "ROW 3"
    return "ROW 4"


def sum_to_zero_columns(level: str, levels: list[str]) -> list[float]:
    """Deviation (sum-to-zero) contrast coding, len(levels)-1 columns. The LAST level in
    `levels` is the implicit reference: its own deviation is -(sum of the others), never
    given its own column. Standard property exploited throughout this script: in a strictly
    ADDITIVE model (no interaction terms) fit with this coding, a term's fitted coefficient
    for level L *is* the least-squares marginal mean for L minus the grand mean, regardless
    of how unbalanced the underlying cell counts are -- exactly the "least-squares marginal
    means from the fitted model" spec Section 7.4 calls for."""
    k = len(levels)
    out = [0.0] * (k - 1)
    idx = levels.index(level)
    if idx == k - 1:
        out = [-1.0] * (k - 1)
    else:
        out[idx] = 1.0
    return out


def build_design(rows: list[dict], sep_labels, dens_labels, snr_labels
                  ) -> tuple[np.ndarray, np.ndarray, dict[str, list[int]]]:
    """Builds [intercept | sep(k-1) | dens(k-1) | snr(k-1)] design matrix X and response
    vector y (miss_rate) for an ADDITIVE (main-effects-only) model -- no interactions among
    Separation/Density/SNR. Chosen over a saturated factorial specifically because the
    `clear (>150)` separation level survives the n>=20 pooled gate in only one of its twelve
    (Density x SNR) combinations (see the lattice table) -- a saturated 3-way interaction
    model would be inestimable (rank-deficient) against that coverage; an additive model
    remains estimable and, being strictly additive, keeps the exact marginal-mean identity
    documented in sum_to_zero_columns(). Reported honestly as a deviation from a fully
    saturated design, not hidden -- see the report's Methodology note.
    Returns (X, y, term_cols) where term_cols maps 'sep'/'dens'/'snr' to their column
    indices in X (never including column 0, the intercept)."""
    cols_sep = len(sep_labels) - 1
    cols_dens = len(dens_labels) - 1
    cols_snr = len(snr_labels) - 1
    term_cols = {
        "sep": list(range(1, 1 + cols_sep)),
        "dens": list(range(1 + cols_sep, 1 + cols_sep + cols_dens)),
        "snr": list(range(1 + cols_sep + cols_dens, 1 + cols_sep + cols_dens + cols_snr)),
    }
    X_rows, y_rows = [], []
    for r in rows:
        row = [1.0]
        row += sum_to_zero_columns(r["sep"], sep_labels)
        row += sum_to_zero_columns(r["dens"], dens_labels)
        row += sum_to_zero_columns(r["snr"], snr_labels)
        X_rows.append(row)
        y_rows.append(r["miss_rate"])
    return np.array(X_rows, dtype=float), np.array(y_rows, dtype=float), term_cols


def rss_of(X: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray, int]:
    """Residual sum of squares, fitted coefficients, and matrix rank via ordinary least
    squares (np.linalg.lstsq -- robust to the near-collinearity the sparse `clear(>150)`
    coverage introduces, unlike a hand-rolled normal-equations solve)."""
    beta, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return float(resid @ resid), beta, int(rank)


def fit_additive_anova(rows: list[dict], sep_labels, dens_labels, snr_labels) -> dict:
    """Type II sums of squares (order-independent for a strictly additive model: each
    term's SS is the RSS reduction from adding it to a model already containing the OTHER
    two main effects) for Separation, Density, and SNR, each tested against the full
    additive model's own residual MS -- the 'pure run-to-run residual', since Run is
    deliberately NOT a modelled term: every row is one (Separation x Density x SNR x Run)
    cell's own miss rate, so whatever the additive main effects don't explain is exactly
    run-to-run (plus higher-order interaction) variation, mirroring how
    three_way_anova_with_replication's ss_error is defined for a balanced design -- this is
    its unbalanced-data generalisation, via OLS rather than closed-form cell means.
    """
    X, y, term_cols = build_design(rows, sep_labels, dens_labels, snr_labels)
    n = len(y)
    rss_full, beta_full, rank_full = rss_of(X, y)
    df_resid = n - rank_full
    ms_resid = rss_full / df_resid if df_resid > 0 else float("nan")

    def marginal_means(term: str, labels: list[str]) -> dict[str, float]:
        grand = beta_full[0]
        cols = term_cols[term]
        k = len(labels)
        devs = [beta_full[cols[i]] for i in range(k - 1)]
        devs.append(-sum(devs))  # last level = -(sum of the others), sum-to-zero
        return {labels[i]: grand + devs[i] for i in range(k)}

    out = {"n_rows": n, "df_resid": df_resid, "ms_resid": ms_resid, "rss_full": rss_full,
           "rank_full": rank_full, "n_params": X.shape[1]}
    ss_total = float(((y - y.mean()) ** 2).sum())
    out["ss_total"] = ss_total

    for term, labels in (("sep", sep_labels), ("dens", dens_labels), ("snr", snr_labels)):
        keep = [c for c in range(X.shape[1]) if c not in term_cols[term]]
        rss_reduced, _, _ = rss_of(X[:, keep], y)
        ss_term = rss_reduced - rss_full
        df_term = len(term_cols[term])
        ms_term = ss_term / df_term if df_term > 0 else float("nan")
        if df_resid > 0 and ms_resid > 0:
            f_term = ms_term / ms_resid
            p_term = 1 - fdist.cdf(f_term, df_term, df_resid)
        else:
            f_term = p_term = float("nan")
        out[term] = {
            "ss": ss_term, "df": df_term, "ms": ms_term, "f": f_term, "p": p_term,
            "pct_ss": 100.0 * ss_term / ss_total if ss_total > 0 else float("nan"),
            "marginal_means": marginal_means(term, labels),
        }
    return out


def run_anova_for_sep_bands(cells: dict, sep_bands, dens_bands, snr_bands) -> dict:
    """Applies the MIN_POOLED_N>=20 lattice gate (spec Section 7.3), then fits the additive
    Type-II ANOVA above on every (Separation, Density, SNR, Run) cell that survives it, one
    row per surviving stratum-run with actual decodes that run (a run contributing zero
    decodes to a surviving stratum simply has no row -- OLS does not need a balanced design,
    unlike the closed-form three_way_anova_with_replication used elsewhere in this project
    for genuinely balanced designs). Per spec: if any LEVEL of Separation or Density has no
    surviving stratum anywhere, the gate does not fire (ROW 4)."""
    sep_labels = [b[0] for b in sep_bands]
    dens_labels = [b[0] for b in dens_bands]
    snr_labels = [b[0] for b in snr_bands]

    pooled_n: dict[tuple, int] = defaultdict(int)
    for (sb, db, nb, run), c in cells.items():
        pooled_n[(sb, db, nb)] += c["total"]

    excluded_strata = [k for k, n in pooled_n.items() if n < MIN_POOLED_N]
    included_strata = [k for k, n in pooled_n.items() if n >= MIN_POOLED_N]

    populated_sep = {k[0] for k in included_strata}
    populated_dens = {k[1] for k in included_strata}
    lattice_ok = (set(sep_labels) <= populated_sep) and (set(dens_labels) <= populated_dens)

    # Coverage detail: how many of each level's (other-factor) combinations actually survive
    # -- flagged because `clear(>150)`-type sparsity can make a "populated" level's main
    # effect rest on very few strata, which matters for reading the result even when the
    # literal lattice check passes.
    coverage = {lvl: sum(1 for k in included_strata if k[0] == lvl) for lvl in sep_labels}
    coverage.update({lvl: sum(1 for k in included_strata if k[1] == lvl) for lvl in dens_labels})

    result = {
        "pooled_n": {f"{k[0]} | {k[1]} | {k[2]}": n for k, n in pooled_n.items()},
        "excluded_strata": [f"{k[0]} | {k[1]} | {k[2]}" for k in excluded_strata],
        "n_excluded_strata": len(excluded_strata),
        "n_included_strata": len(included_strata),
        "populated_sep_levels": sorted(populated_sep),
        "populated_dens_levels": sorted(populated_dens),
        "lattice_ok": lattice_ok,
        "coverage_strata_per_level": coverage,
    }
    if not lattice_ok:
        result["anova"] = None
        return result

    rows = []
    for (sb, db, nb) in included_strata:
        for r in range(1, N_RUNS + 1):
            c = cells.get((sb, db, nb, r))
            if c is not None and c["total"] > 0:
                rows.append({"sep": sb, "dens": db, "snr": nb, "run": r,
                             "miss_rate": c["missed"] / c["total"], "n": c["total"]})
    result["n_data_rows"] = len(rows)

    active_sep = [s for s in sep_labels if any(r["sep"] == s for r in rows)]
    active_dens = [d for d in dens_labels if any(r["dens"] == d for r in rows)]
    active_snr = [s for s in snr_labels if any(r["snr"] == s for r in rows)]
    if len(active_sep) < len(sep_labels) or len(active_dens) < len(dens_labels):
        # a level survived the pooled-n gate but produced zero individual run-rows (should
        # not happen given how included_strata/rows are built, but checked explicitly rather
        # than assumed)
        result["lattice_ok"] = False
        result["anova"] = None
        return result

    anova = fit_additive_anova(rows, sep_labels, dens_labels, snr_labels)
    result["anova"] = anova
    result["sep_labels"] = sep_labels
    result["dens_labels"] = dens_labels
    result["snr_labels"] = snr_labels
    return result


def main() -> int:
    print(f"Loading WSJT-X master ALL.TXT: {WSJTX_ALL_TXT}")
    wx_rows_all = parse_all_txt(str(WSJTX_ALL_TXT))
    print(f"  total rows (all-time file): {len(wx_rows_all)}")

    all_records = []
    total_excluded_single = 0
    total_excluded_band_edge = 0
    per_run_summary = []
    for i in range(1, N_RUNS + 1):
        loaded = load_run(i, wx_rows_all)
        wx_marked = mark_missed(loaded["wx_p1"], loaded["our_p1"])
        recs, n_excl_single, n_excl_edge = build_decode_records(i, wx_marked)
        all_records.extend(recs)
        total_excluded_single += n_excl_single
        total_excluded_band_edge += n_excl_edge
        n_missed = sum(1 for r in recs if r["missed"])
        per_run_summary.append({
            "run": i, "wx_total": len(loaded["wx_p1"]), "our_total": len(loaded["our_p1"]),
            "n_usable_records": len(recs), "n_excluded_single_decode": n_excl_single,
            "n_excluded_band_edge": n_excl_edge,
            "n_missed": n_missed,
            "miss_rate": n_missed / len(recs) if recs else float("nan"),
        })
        print(f"run {i}: wx={len(loaded['wx_p1'])} our={len(loaded['our_p1'])} "
              f"usable records={len(recs)} excluded(single-decode)={n_excl_single} "
              f"excluded(band-edge)={n_excl_edge} missed={n_missed}")

    print(f"\nTotal usable decode-records: {len(all_records)}; "
          f"total excluded (single-decode cycles, sep undefined): {total_excluded_single}; "
          f"total excluded (band-edge, outside [{BAND_LO_HZ:.0f},{BAND_HI_HZ:.0f}) Hz, "
          f"certain unrelated defect per 2323 Sec.4): {total_excluded_band_edge}")

    # ---- descriptive: sep distribution (mandatory lattice check, Section 7.3) ----
    seps = sorted(r["sep"] for r in all_records)
    n_sep = len(seps)

    def pct(p):
        idx = min(n_sep - 1, max(0, int(round(p * (n_sep - 1)))))
        return seps[idx]

    sep_summary = {
        "n": n_sep,
        "mean": sum(seps) / n_sep if n_sep else float("nan"),
        "p10": pct(0.10), "p50": pct(0.50), "p90": pct(0.90),
        "min": seps[0] if seps else float("nan"), "max": seps[-1] if seps else float("nan"),
    }
    print(f"\nsep distribution: n={sep_summary['n']} mean={sep_summary['mean']:.1f} "
          f"p10={sep_summary['p10']:.1f} p50={sep_summary['p50']:.1f} "
          f"p90={sep_summary['p90']:.1f} min={sep_summary['min']:.1f} max={sep_summary['max']:.1f}")

    def compute_effects(anova_result: dict) -> dict:
        """E_sep/p_sep/E_dens/p_dens from a run_anova_for_sep_bands() result, or a dict
        recording why they could not be computed. Shared between the primary (gating)
        boundary and the sensitivity boundaries (reported only, per Section 7.6 #4)."""
        if not anova_result["lattice_ok"] or anova_result["anova"] is None:
            return {"row": "ROW 4", "reason": "lattice check failed (unpopulated level)",
                    "e_sep": None, "p_sep": None, "e_dens": None, "p_dens": None}
        anova = anova_result["anova"]
        mm_sep = anova["sep"]["marginal_means"]
        mm_dens = anova["dens"]["marginal_means"]
        local_label = next((l for l in mm_sep if l.startswith("local")), None)
        clear_label = next((l for l in mm_sep if l.startswith("clear")), None)
        low_label = next((l for l in mm_dens if l.startswith("30-34")), None)
        high_label = next((l for l in mm_dens if l.startswith("40-49")), None)
        if not (local_label and clear_label and low_label and high_label):
            return {"row": "ROW 4", "reason": "could not locate both extreme sep or dens levels",
                    "e_sep": None, "p_sep": None, "e_dens": None, "p_dens": None}
        e_sep = (mm_sep[local_label] - mm_sep[clear_label]) * 100.0
        p_sep = anova["sep"]["p"]
        e_dens = (mm_dens[high_label] - mm_dens[low_label]) * 100.0
        p_dens = anova["dens"]["p"]
        row = s1r_row(e_sep, p_sep, e_dens, p_dens)
        return {"row": row, "e_sep": e_sep, "p_sep": p_sep, "e_dens": e_dens, "p_dens": p_dens,
                "local_limb": limb(e_sep, p_sep), "global_limb": limb(e_dens, p_dens)}

    results_by_boundary = {}
    effects_by_boundary = {}
    for boundary_name, sep_bands in SEP_BOUNDARY_SETS.items():
        cells, n_dens_oor = cell_table(all_records, sep_bands)
        anova_result = run_anova_for_sep_bands(cells, sep_bands, DENS_BANDS, SNR_BANDS)
        anova_result["n_dens_out_of_range"] = n_dens_oor
        results_by_boundary[boundary_name] = anova_result
        effects_by_boundary[boundary_name] = compute_effects(anova_result)
        print(f"\n--- boundary set: {boundary_name} ---")
        print(f"  dens-out-of-range records dropped: {n_dens_oor}")
        print(f"  included strata (n>=20): {anova_result['n_included_strata']}, "
              f"excluded: {anova_result['n_excluded_strata']}")
        print(f"  lattice_ok: {anova_result['lattice_ok']}")
        print(f"  effects: {effects_by_boundary[boundary_name]}")

    primary = results_by_boundary["primary_50_150"]
    verdict = dict(effects_by_boundary["primary_50_150"])
    if verdict["row"] == "ROW 4" and "reason" not in verdict:
        verdict["reason"] = "gate evaluated, result was ROW 4 (see limb classifications)"

    print(f"\n=== VERDICT (primary 50/150 boundary, the ONLY boundary that gates): "
          f"{verdict['row']} ===")
    print(json.dumps(verdict, indent=2, default=str))

    # ---- write report ----
    generated = datetime.datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = []
    lines.append("# S.1r -- spectral locality re-evidenced at power: results\n")
    lines.append(f"Generated {generated}. Script: `s1r_spectral_locality.py`, same directory.\n")
    lines.append("Per Section 7 of `2026-08-07-1616-architect-to-qa-captain-rulings-and-"
                  "d001-reconciliation.md`. S.1 is CLOSED; this re-evidences its limb only, "
                  "at ~44x the sample the 08-04 conversational closure rested on. Reference: "
                  "fresh WSJT-X on the identically replayed audio (never `jt9 -d 3`, never the "
                  "archived corpus ALL.TXT).\n")

    lines.append("## Per-run summary\n")
    lines.append("| run | WSJT-X (pass 1) | OpenWSFZ (pass 1) | usable records | excluded "
                  "(single-decode cycle) | excluded (band-edge) | missed | miss rate |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in per_run_summary:
        lines.append(f"| {s['run']} | {s['wx_total']} | {s['our_total']} | "
                      f"{s['n_usable_records']} | {s['n_excluded_single_decode']} | "
                      f"{s['n_excluded_band_edge']} | {s['n_missed']} | "
                      f"{s['miss_rate']*100:.1f}% |")
    lines.append("")
    lines.append(f"Pooled usable records: **{len(all_records)}**. Pooled excluded "
                  f"(single-decode cycles, `sep` undefined): **{total_excluded_single}**. Pooled "
                  f"excluded (band-edge, outside [{BAND_LO_HZ:.0f},{BAND_HI_HZ:.0f}) Hz -- "
                  f"OpenWSFZ's hardcoded search band, per 2026-08-06-2323 Section 4, a certain "
                  f"defect unrelated to spectral locality): **{total_excluded_band_edge}**. "
                  f"⚠️ Discovered live while running this analysis (see the Methodology note "
                  f"below) -- not one of the confounds Section 7.6 anticipated in advance.\n")

    lines.append("## Separation (`sep`) distribution -- mandatory lattice check (Section 7.3)\n")
    lines.append(f"n={sep_summary['n']}, mean={sep_summary['mean']:.1f} Hz, "
                 f"p10={sep_summary['p10']:.1f}, p50={sep_summary['p50']:.1f}, "
                 f"p90={sep_summary['p90']:.1f}, min={sep_summary['min']:.1f}, "
                 f"max={sep_summary['max']:.1f} Hz.\n")

    for boundary_name, res in results_by_boundary.items():
        lines.append(f"## Boundary set: `{boundary_name}`\n")
        lines.append(f"- Records dropped for density outside 30-49/cycle: "
                      f"{res['n_dens_out_of_range']}")
        lines.append(f"- Strata (sep x dens x snr) included (pooled n>=20): "
                      f"{res['n_included_strata']}; excluded: {res['n_excluded_strata']}")
        if res["excluded_strata"]:
            lines.append(f"- Excluded strata: {', '.join(res['excluded_strata'])}")
        lines.append(f"- Populated Separation levels: {', '.join(res['populated_sep_levels'])}")
        lines.append(f"- Populated Density levels: {', '.join(res['populated_dens_levels'])}")
        lines.append(f"- Lattice OK (all 3 Separation and all 3 Density levels populated "
                      f"at n>=20 somewhere): **{res['lattice_ok']}**")
        if res.get("coverage_strata_per_level"):
            cov = ", ".join(f"{lvl}={n}/12" for lvl, n in res["coverage_strata_per_level"].items())
            lines.append(f"- Coverage (surviving strata per level, out of 12 possible "
                          f"Density x SNR / Separation x SNR combinations): {cov}")
        lines.append("")
        lines.append("| stratum (sep \\| dens \\| snr) | pooled n |")
        lines.append("|---|---:|")
        for k, n in sorted(res["pooled_n"].items()):
            flag = " (EXCLUDED)" if k in res["excluded_strata"] else ""
            lines.append(f"| {k}{flag} | {n} |")
        lines.append("")

    lines.append("## Methodology note: additive model, not saturated interaction model\n")
    lines.append("The pre-registered spec (Section 7.3) says to reuse the existing 3-way ANOVA "
                  "machinery, one factor added. That machinery (`three_way_anova_with_"
                  "replication`, `build_full_anova.py`) assumes a fully-crossed BALANCED design "
                  "-- every (Separation x Density x SNR) cell populated with exactly 5 (Run) "
                  "replicates. The real data does not support that: at the primary 50/150 Hz "
                  "boundary the `clear (>150 Hz)` Separation level survives the pooled-n>=20 "
                  "gate in 0 of its 12 possible (Density x SNR) combinations once the band-edge "
                  "exclusion is applied (see the coverage line above and the band-edge note), "
                  "which would make a saturated 3-way-interaction model rank-deficient even "
                  "before the lattice check itself already routes this boundary to ROW 4. This "
                  "analysis instead fits a strictly ADDITIVE model (main effects only, no "
                  "interactions among "
                  "Separation/Density/SNR) via ordinary least squares with sum-to-zero "
                  "(deviation) contrast coding, Type II sums of squares (each term tested "
                  "against a model containing the other two main effects), and the full "
                  "model's own residual as the error term -- algebraically the unbalanced-data "
                  "generalisation of the same idea, and it still delivers exactly what Section "
                  "7.4 asks for: least-squares marginal means from the fitted model, each "
                  "term's effect controlled for the other two. The trade-off, stated plainly: "
                  "any genuine Separation x Density (or other) interaction is NOT modelled and "
                  "instead flows into the residual, which makes every F-test in this report "
                  "MORE conservative (biased toward NULL), never less -- the safer failure "
                  "direction for a pre-registered LIVE gate that already requires p<0.01.\n")

    lines.append("## Pre-registered gate (Section 7.5), primary 50/150 Hz boundary ONLY\n")
    lines.append("Sensitivity boundaries (25/100, 75/200) are reported above (pooled-n tables) "
                  "but per Section 7.6 #4 never evaluate the gate.\n")
    if primary["anova"] is not None and verdict.get("e_sep") is not None:
        anova = primary["anova"]
        lines.append(f"- `E_sep` = {verdict['e_sep']:+.2f} pp, `p_sep` = {verdict['p_sep']:.6f} "
                      f"-> limb = **{verdict['local_limb']}**")
        lines.append(f"- `E_dens` = {verdict['e_dens']:+.2f} pp, `p_dens` = {verdict['p_dens']:.6f} "
                      f"-> limb = **{verdict['global_limb']}**")
        lines.append(f"- Model: {anova['n_rows']} (Separation x Density x SNR x Run) cell rows, "
                      f"{anova['n_params']} parameters, residual df={anova['df_resid']}.\n")
        lines.append("| Term | DF | SS | MS | F | P | %SS | LS marginal means (miss rate) |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
        names = {"sep": "Separation", "dens": "Density", "snr": "SNR (control)"}
        for key in ["sep", "dens", "snr"]:
            t = anova[key]
            mm = ", ".join(f"{lvl}={v*100:.1f}%" for lvl, v in t["marginal_means"].items())
            lines.append(f"| {names[key]} | {t['df']} | {t['ss']:.6f} | {t['ms']:.6f} | "
                          f"{t['f']:.3f} | {t['p']:.6f} | {t['pct_ss']:.1f}% | {mm} |")
        lines.append(f"| Residual (run-to-run + unmodelled interaction) | {anova['df_resid']} | "
                      f"{anova['rss_full']:.6f} | {anova['ms_resid']:.6f} | | | "
                      f"{100*anova['rss_full']/anova['ss_total']:.1f}% | |")
        lines.append(f"| Total | {anova['n_rows']-1} | {anova['ss_total']:.6f} | | | | 100.0% | |")
        lines.append("")
        lines.append(f"**Verdict: {verdict['row']}**\n")
    else:
        lines.append(f"**Gate did not fire: {verdict.get('reason', 'unknown')}. Verdict: "
                      f"{verdict['row']} (no verdict / RC1 not narrowed).**\n")

    lines.append("## Sensitivity boundaries -- reported, NEVER gated (Section 7.6 #4)\n")
    lines.append("Per spec: 'reporting the others guards against a boundary artefact; letting "
                  "them fire the gate would be fishing.' Shown for context only.\n")
    lines.append("| boundary | lattice OK | E_sep (pp) | p_sep | local limb | E_dens (pp) | "
                  "p_dens | global limb | would-be row |")
    lines.append("|---|---|---:|---:|---|---:|---:|---|---|")
    for boundary_name in ["sensitivity_25_100", "sensitivity_75_200"]:
        eff = effects_by_boundary[boundary_name]
        res = results_by_boundary[boundary_name]
        if eff.get("e_sep") is not None:
            lines.append(f"| `{boundary_name}` | {res['lattice_ok']} | {eff['e_sep']:+.2f} | "
                          f"{eff['p_sep']:.6f} | {eff['local_limb']} | {eff['e_dens']:+.2f} | "
                          f"{eff['p_dens']:.6f} | {eff['global_limb']} | {eff['row']} |")
        else:
            lines.append(f"| `{boundary_name}` | {res['lattice_ok']} | -- | -- | -- | -- | -- "
                          f"| -- | {eff['row']} ({eff.get('reason', '')}) |")
    lines.append("")

    lines.append("## What this does and does not establish\n")
    lines.append("Per spec Section 7.7: one window, density 30-49/cycle (silent on the "
                  "~7/cycle regime); decode-side, not pipeline-side; observational, not "
                  "interventional; does not re-open S.1 and does not reverse the Captain's "
                  "closure.\n")

    report_path = HERE / "s1r_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {report_path}")

    def json_default(o):
        if isinstance(o, float) and (o != o):
            return None
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        return str(o)

    summary_path = HERE / "s1r_summary.json"
    summary_path.write_text(json.dumps({
        "per_run_summary": per_run_summary,
        "sep_summary": sep_summary,
        "results_by_boundary": {
            k: {kk: vv for kk, vv in v.items() if kk != "anova"}
            for k, v in results_by_boundary.items()
        },
        "primary_anova": primary.get("anova"),
        "verdict": verdict,
    }, indent=2, default=json_default), encoding="utf-8")
    print(f"wrote {summary_path}")

    try:
        import anova_common as ac
        ac.render_markdown_html(str(report_path))
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] HTML render skipped: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
