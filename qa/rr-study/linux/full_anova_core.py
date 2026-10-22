"""Statistics for the LINUX series' final full ANOVA report (QA tooling; aggregates only, NFR-021: message text never leaves the readers).

Data: the five PAIRED sweeps (run 1 on the default ALSA chain; run 2 and repeats 1b-3b on the corrected chain), each a full S1-S8 battery with
both appraisers decoding. The three 11-12 Oct repeats (WSJT-X silent) and the INVALID stalled sweep are not read.

Models (all balanced here: 10 parts x 2 appraisers x 3 trials per sweep, checked in code):
  * per sweep: the analyser's own two-way crossed Part x Appraiser ANOVA (harness/analyse.py, imported, so the figures are the analyser's, and
    compared with the figures in each sweep's own report);
  * pooled, sweeps ignored: the same two-way model with the sweeps as extra replicates (3 x S trials per cell);
  * pooled, sweeps as a random factor: three-way crossed random-effects ANOVA Part x Appraiser x Sweep with 3 trials per cell: all seven
    mean squares, exact F tests where they exist (PA, PS, AS, PAS) and Satterthwaite quasi-F tests for the three main effects, variance
    components by the expected-mean-squares method (negative estimates are reported and truncated to 0 for the percentages), and a
    part-cluster bootstrap for the percentages.
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, RR)
import consolidate_data as C  # noqa: E402
from harness import analyse as AN  # noqa: E402

PAIRED = ["run1", "run2", "w1", "w2", "w3"]
CORRECTED = ["run2", "w1", "w2", "w3"]
SCEN = (("S1", "reported_snr_db", "true_snr_db", "dB"), ("S2", "reported_freq_hz", "true_freq_hz", "Hz"), ("S3", "reported_dt_s", "true_dt_s", "s"))
APPR = ("WSJT-X", "OpenWSFZ")
BOOT_N = 2000
BOOT_SEED = 20261014
S3_DT_CORRECTION_S = 0.55          # scenarios/s3-dt-offset.json `wsjt_dt_correction_s`, applied to WSJT-X by the analyser; asserted below


# ----------------------------------------------------------------------------------------------------------------------------- loading
def load(results: str, folder: str, scen: str, resp: str, ref: str) -> pd.DataFrame:
    df = AN._load_matched_csvs(__import__("pathlib").Path(os.path.join(results, folder)), [scen], __import__("pathlib").Path(RR) / "scenarios")[scen]
    if scen == "S3":
        df = AN._apply_wsjt_dt_correction(df, S3_DT_CORRECTION_S)
    return df


def cube(df: pd.DataFrame, resp: str, ref: str):
    """-> (Y[parts, appraisers, trials], ref values per part) for the matched, non-false-positive rows; asserts a balanced 10 x 2 x 3 design."""
    m = df[(df["matched"] == True) & (df["false_positive"] == False)].dropna(subset=[resp, "part_index", "trial_index"]).copy()
    parts = sorted(m["part_index"].unique())
    refs = m.groupby("part_index")[ref].first()
    Y = np.full((len(parts), len(APPR), 3), np.nan)
    for i, p in enumerate(parts):
        for j, a in enumerate(APPR):
            v = m[(m["part_index"] == p) & (m["appraiser"] == a)].sort_values("trial_index")[resp].to_numpy()
            if len(v) != 3:
                raise SystemExit("unbalanced cell: part %s appraiser %s has %d trials" % (p, a, len(v)))
            Y[i, j, :] = v
    return Y, np.array([float(refs[p]) for p in parts])


# ----------------------------------------------------------------------------------------------------------------------------- ANOVA
def two_way(Y: np.ndarray) -> dict:
    """Balanced two-way crossed Part x Appraiser ANOVA on Y[P, A, n] (the analyser's formulas, AIAG MSA 4th ed.)."""
    P, A, n = Y.shape
    g = Y.mean()
    mP, mA, mPA = Y.mean(axis=(1, 2)), Y.mean(axis=(0, 2)), Y.mean(axis=2)
    ssP = A * n * ((mP - g) ** 2).sum()
    ssA = P * n * ((mA - g) ** 2).sum()
    ssPA = n * ((mPA - mP[:, None] - mA[None, :] + g) ** 2).sum()
    ssT = ((Y - g) ** 2).sum()
    ssE = ssT - ssP - ssA - ssPA
    dfP, dfA, dfPA, dfE = P - 1, A - 1, (P - 1) * (A - 1), P * A * (n - 1)
    msP, msA, msPA, msE = ssP / dfP, ssA / dfA, ssPA / dfPA, ssE / dfE
    rep = max(0.0, msE)
    inter = max(0.0, (msPA - msE) / n)
    reprod = max(0.0, (msA - msPA) / (P * n)) + inter
    part = max(0.0, (msP - msPA) / (A * n))
    grr = rep + reprod
    tot = grr + part
    pc = lambda v: 100.0 * v / tot if tot > 0 else 0.0
    tab = [("Part", ssP, dfP, msP, msP / msPA if msPA > 0 else float("nan"), stats.f.sf(msP / msPA, dfP, dfPA) if msPA > 0 else float("nan")),
           ("Appraiser", ssA, dfA, msA, msA / msPA if msPA > 0 else float("nan"), stats.f.sf(msA / msPA, dfA, dfPA) if msPA > 0 else float("nan")),
           ("Part x Appraiser", ssPA, dfPA, msPA, msPA / msE if msE > 0 else float("nan"), stats.f.sf(msPA / msE, dfPA, dfE) if msE > 0 else float("nan")),
           ("Repeatability (error)", ssE, dfE, msE, None, None), ("Total", ssT, P * A * n - 1, None, None, None)]
    return {"table": tab, "var": {"repeatability": rep, "reproducibility": reprod, "part": part, "grr": grr, "total": tot},
            "pct": {"repeatability": pc(rep), "reproducibility": pc(reprod), "part": pc(part), "grr": pc(grr), "grr_sv": (100.0 * math.sqrt(grr / tot) if tot > 0 else 0.0)},
            "ndc": (max(1, math.floor(1.41 * math.sqrt(part) / math.sqrt(grr))) if grr > 0 and part > 0 else None), "n": n, "grand_mean": g}


def three_way(Y: np.ndarray) -> dict:
    """Balanced three-way crossed RANDOM-effects ANOVA, Y[P, A, S, n]. Factors: Part, Appraiser, Sweep."""
    P, A, S, n = Y.shape
    g = Y.mean()
    mP, mA, mS = Y.mean(axis=(1, 2, 3)), Y.mean(axis=(0, 2, 3)), Y.mean(axis=(0, 1, 3))
    mPA, mPS, mAS = Y.mean(axis=(2, 3)), Y.mean(axis=(1, 3)), Y.mean(axis=(0, 3))
    mPAS = Y.mean(axis=3)
    ssP = A * S * n * ((mP - g) ** 2).sum()
    ssA = P * S * n * ((mA - g) ** 2).sum()
    ssS = P * A * n * ((mS - g) ** 2).sum()
    ssPA = S * n * ((mPA - mP[:, None] - mA[None, :] + g) ** 2).sum()
    ssPS = A * n * ((mPS - mP[:, None] - mS[None, :] + g) ** 2).sum()
    ssAS = P * n * ((mAS - mA[:, None] - mS[None, :] + g) ** 2).sum()
    inter3 = mPAS - mPA[:, :, None] - mPS[:, None, :] - mAS[None, :, :] + mP[:, None, None] + mA[None, :, None] + mS[None, None, :] - g
    ssPAS = n * (inter3 ** 2).sum()
    ssE = ((Y - mPAS[..., None]) ** 2).sum()
    ssT = ((Y - g) ** 2).sum()
    df = {"P": P - 1, "A": A - 1, "S": S - 1, "PA": (P - 1) * (A - 1), "PS": (P - 1) * (S - 1), "AS": (A - 1) * (S - 1), "PAS": (P - 1) * (A - 1) * (S - 1), "E": P * A * S * (n - 1)}
    ss = {"P": ssP, "A": ssA, "S": ssS, "PA": ssPA, "PS": ssPS, "AS": ssAS, "PAS": ssPAS, "E": ssE}
    ms = {k: ss[k] / df[k] for k in ss}
    vc_raw = {"E": ms["E"], "PAS": (ms["PAS"] - ms["E"]) / n, "PA": (ms["PA"] - ms["PAS"]) / (n * S), "PS": (ms["PS"] - ms["PAS"]) / (n * A), "AS": (ms["AS"] - ms["PAS"]) / (n * P),
              "P": (ms["P"] - ms["PA"] - ms["PS"] + ms["PAS"]) / (n * A * S), "A": (ms["A"] - ms["PA"] - ms["AS"] + ms["PAS"]) / (n * P * S), "S": (ms["S"] - ms["PS"] - ms["AS"] + ms["PAS"]) / (n * P * A)}
    vc = {k: max(0.0, v) for k, v in vc_raw.items()}

    def sat(num_terms, den_terms):                       # quasi-F with Satterthwaite degrees of freedom
        num = sum(ms[k] for k in num_terms)
        den = sum(ms[k] for k in den_terms)
        dnum = num ** 2 / sum(ms[k] ** 2 / df[k] for k in num_terms)
        dden = den ** 2 / sum(ms[k] ** 2 / df[k] for k in den_terms) if den > 0 else float("nan")
        F = num / den if den > 0 else float("nan")
        return F, dnum, dden, (stats.f.sf(F, dnum, dden) if den > 0 else float("nan"))
    tests = {"P": sat(["P", "PAS"], ["PA", "PS"]), "A": sat(["A", "PAS"], ["PA", "AS"]), "S": sat(["S", "PAS"], ["PS", "AS"])}
    for k, dn, dd, den in (("PA", df["PA"], df["PAS"], "PAS"), ("PS", df["PS"], df["PAS"], "PAS"), ("AS", df["AS"], df["PAS"], "PAS"), ("PAS", df["PAS"], df["E"], "E")):
        F = ms[k] / ms[den] if ms[den] > 0 else float("nan")
        tests[k] = (F, dn, dd, stats.f.sf(F, dn, dd) if ms[den] > 0 else float("nan"))
    total = sum(vc.values())
    groups = {"repeatability": vc["E"], "appraiser": vc["A"] + vc["PA"], "sweep": vc["S"] + vc["PS"] + vc["AS"] + vc["PAS"], "part": vc["P"]}
    grr = groups["repeatability"] + groups["appraiser"] + groups["sweep"]
    pc = lambda v: 100.0 * v / total if total > 0 else 0.0
    return {"ss": ss, "df": df, "ms": ms, "vc": vc, "vc_raw": vc_raw, "tests": tests, "total_var": total, "ss_total": ssT, "df_total": P * A * S * n - 1,
            "pct": {k: pc(v) for k, v in vc.items()}, "groups": groups, "pct_groups": {k: pc(v) for k, v in groups.items()}, "pct_grr": pc(grr), "pct_grr_sv": (100.0 * math.sqrt(grr / total) if total > 0 else 0.0), "grr_var": grr,
            "ndc": (max(1, math.floor(1.41 * math.sqrt(vc["P"]) / math.sqrt(grr))) if grr > 0 and vc["P"] > 0 else None), "n": (P, A, S, n), "grand_mean": g}


def boot_pct(Y: np.ndarray, seed: int = BOOT_SEED) -> dict:
    """Part-cluster bootstrap of the three-way percentages (resample the parts with replacement; the design stays balanced)."""
    rng = np.random.default_rng(seed)
    P = Y.shape[0]
    out = defaultdict(list)
    for _ in range(BOOT_N):
        idx = rng.integers(0, P, P)
        r = three_way(Y[idx])
        for k, v in r["pct_groups"].items():
            out[k].append(v)
        out["grr"].append(r["pct_grr"])
    return {k: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) for k, v in out.items()}


# ----------------------------------------------------------------------------------------------------------------------------- bias
def t_ci(v, conf=0.95):
    v = np.asarray(v, dtype=float)
    n = len(v)
    m = float(v.mean())
    if n < 2:
        return m, float("nan"), float("nan"), float("nan")
    sd = float(v.std(ddof=1))
    h = float(stats.t.ppf(0.5 + conf / 2, n - 1)) * sd / math.sqrt(n)
    return m, sd, m - h, m + h


def bias_tables(cubes: dict) -> dict:
    """Per sweep and appraiser: mean error (reported - reference) and the OLS slope of the error on the reference (linearity)."""
    out = {}
    for sc in cubes:
        out[sc] = {}
        for k, (Y, ref) in cubes[sc].items():
            e = Y - ref[:, None, None]
            row = {}
            for j, a in enumerate(APPR):
                ee = e[:, j, :]
                slope = stats.linregress(np.repeat(ref, 3), ee.reshape(-1)).slope
                row[a] = {"bias": float(ee.mean()), "slope": float(slope), "sd_within": float(ee.std(ddof=1))}
            out[sc][k] = row
    return out


# ----------------------------------------------------------------------------------------------------------------------------- attribute
def units_s4(results: str, folder: str) -> dict:
    """S4 positive units -> {appraiser: {unit key: decoded}} following the analyser's _attribute_agreement (a unit is decoded if ANY of its rows matched)."""
    df = AN._load_matched_csvs(__import__("pathlib").Path(os.path.join(results, folder)), ["S4"], __import__("pathlib").Path(RR) / "scenarios")["S4"]
    d = df[df["false_positive"] == False]
    u = {a: {} for a in APPR}
    for r in d.itertuples(index=False):
        key = (int(r.part_index), int(r.trial_index), r.message_text)    # the cycle stamp differs between sweeps; (part, trial, text) is the same injected signal; the text stays in this function
        u[r.appraiser][key] = u[r.appraiser].get(key, False) or bool(r.matched)
    return u


def units_s1b(results: str, folder: str) -> dict:
    df = AN._load_matched_csvs(__import__("pathlib").Path(os.path.join(results, folder)), ["S1b"], __import__("pathlib").Path(RR) / "scenarios")["S1b"]
    d = df[df["false_positive"] == False]
    u = {a: {} for a in APPR}
    for r in d.itertuples(index=False):
        u[r.appraiser][(int(r.part_index), int(r.trial_index))] = u[r.appraiser].get((int(r.part_index), int(r.trial_index)), False) or bool(r.matched)
    return u


def cochran_q(M: np.ndarray) -> tuple:
    """Cochran's Q test of equal proportions across the columns (sweeps) of a units x sweeps 0/1 matrix."""
    k = M.shape[1]
    rows = M.sum(axis=1)
    cols = M.sum(axis=0)
    N = M.sum()
    den = k * N - (rows ** 2).sum()
    if den == 0:
        return 0.0, k - 1, 1.0
    Q = (k - 1) * (k * (cols ** 2).sum() - N ** 2) / den
    return float(Q), k - 1, float(stats.chi2.sf(Q, k - 1))


def exact_sign(d: np.ndarray) -> tuple:
    pos, neg = int((d > 0).sum()), int((d < 0).sum())
    n = pos + neg
    p = float(stats.binomtest(min(pos, neg), n, 0.5).pvalue) if n > 0 else 1.0
    return pos, neg, p
