"""Gage R&R analyser and report generator for the OpenWSFZ R&R study harness.

Usage:
    python harness/analyse.py --run-dir <dir> [--scenario S1,S2]

Reads all *_matched.csv files in the run directory (or the specified subset),
computes ANOVA-method Gage R&R variance components for continuous scenarios
(S1, S2, S3), Attribute Agreement Analysis for attribute scenarios (S4, S5),
writes six-panel charts and a report.md, and appends a row to trend.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Matplotlib in non-interactive mode
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Resolve qa/rr-study as package root
_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTINUOUS_SCENARIOS = {"S1", "S2", "S3"}
ATTRIBUTE_SCENARIOS = {"S4", "S5"}

# Response variable per continuous scenario
RESPONSE_VAR = {
    "S1": "reported_snr_db",
    "S2": "reported_freq_hz",
    "S3": "reported_dt_s",
}

# Tolerance half-widths (STUDY-SPEC §10)
TOLERANCE_HALF = {
    "S1": 2.0,   # ±2 dB
    "S2": 4.0,   # ±4 Hz
    "S3": 0.2,   # ±0.2 s
}

REQUIRED_COLUMNS = {
    "scenario_id", "part_index", "trial_index", "seed", "appraiser", "message_text",
    "true_snr_db", "true_dt_s", "true_freq_hz",
    "reported_snr_db", "reported_dt_s", "reported_freq_hz",
    "matched", "false_positive", "cycle_utc",
}

# STUDY-SPEC §10 verdict thresholds
THRESH_GRR_PASS = 10.0      # %GR&R < 10% → PASS
THRESH_GRR_MARGINAL = 30.0  # %GR&R 10–30% → MARGINAL; > 30% → FAIL
NDC_FAIL = 2                 # ndc < 2 → FAIL
NDC_PASS = 5                 # ndc ≥ 5 → PASS
THRESH_KAPPA_PASS = 0.90
THRESH_KAPPA_MARGINAL = 0.70
THRESH_FP_PASS = 6.0        # FP rate ≤ 6% → PASS; > 6% → FAIL
THRESH_BIAS_PASS = 2.0      # |bias| ≤ 2 dB → PASS; > 2 dB → FAIL

APPRAISERS = ("WSJT-X", "OpenWSFZ")

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def _verdict_grr(pct: float) -> str:
    if pct < THRESH_GRR_PASS:
        return "PASS"
    if pct <= THRESH_GRR_MARGINAL:
        return "MARGINAL"
    return "FAIL"


def _verdict_ndc(ndc: int) -> str:
    if ndc >= NDC_PASS:
        return "PASS"
    if ndc >= NDC_FAIL:
        return "MARGINAL"
    return "FAIL"


def _verdict_kappa(kappa: float) -> str:
    if kappa >= THRESH_KAPPA_PASS:
        return "PASS"
    if kappa >= THRESH_KAPPA_MARGINAL:
        return "MARGINAL"
    return "FAIL"


def _verdict_fp(pct: float) -> str:
    return "PASS" if pct <= THRESH_FP_PASS else "FAIL"


def _verdict_bias(bias: float) -> str:
    return "PASS" if abs(bias) <= THRESH_BIAS_PASS else "FAIL"


# ---------------------------------------------------------------------------
# Task 4.1 — Matched CSV loading
# ---------------------------------------------------------------------------

def _load_scenario_meta(scenarios_dir: Path) -> dict[str, dict]:
    """Return {scenario_id: metadata} from all scenarios/*.json files."""
    meta = {}
    for p in sorted(scenarios_dir.glob("*.json")):
        if p.stem == "study-messages":
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if "id" in d:
                meta[d["id"]] = d
        except (json.JSONDecodeError, KeyError):
            pass
    return meta


def _load_matched_csvs(run_dir: Path, scenario_filter: list[str] | None,
                       scenarios_dir: Path) -> dict[str, pd.DataFrame]:
    """Discover and load all *_matched.csv files in run_dir.

    Returns {scenario_id: DataFrame}.
    """
    found: dict[str, pd.DataFrame] = {}
    for p in sorted(run_dir.glob("*_matched.csv")):
        scen_id = p.stem.replace("_matched", "")
        if scenario_filter and scen_id not in scenario_filter:
            continue
        try:
            df = pd.read_csv(p, dtype=str)
        except Exception as exc:
            sys.exit(f"ERROR: cannot read {p.name}: {exc}")
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            sys.exit(
                f"ERROR: {p.name} missing required column: {', '.join(sorted(missing))}"
            )
        # Parse numeric columns (NaN for empty/missing)
        for col in ("part_index", "trial_index"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in ("reported_snr_db", "reported_dt_s", "reported_freq_hz",
                    "true_snr_db", "true_dt_s", "true_freq_hz"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["matched"] = df["matched"].map({"True": True, "False": False, True: True, False: False})
        df["false_positive"] = df["false_positive"].map(
            {"True": True, "False": False, True: True, False: False}
        )
        found[scen_id] = df
    return found


# ---------------------------------------------------------------------------
# Task 4.2 — Two-way crossed ANOVA (Part × Appraiser)
# ---------------------------------------------------------------------------

def _two_way_anova(df_matched: pd.DataFrame, response: str,
                   scenario_id: str) -> dict | None:
    """Compute AIAG MSA 4th ed. two-way crossed ANOVA variance components.

    Returns a dict of components, or None if insufficient data.
    """
    df = df_matched[df_matched["matched"] == True].copy()
    df[response] = pd.to_numeric(df[response], errors="coerce")
    df = df.dropna(subset=[response, "part_index", "trial_index", "appraiser"])

    parts = df["part_index"].unique()
    appraisers = df["appraiser"].unique()
    n_parts = len(parts)
    n_appraisers = len(appraisers)
    # n_trials per cell
    cell_counts = df.groupby(["part_index", "appraiser"])[response].count()
    if cell_counts.min() < 2:
        print(
            f"WARNING: {scenario_id} — insufficient matched data for Gage R&R; skipping.",
            file=sys.stderr,
        )
        return None
    n_trials = int(cell_counts.min())  # use minimum trials per cell

    grand_mean = df[response].mean()
    n_total = len(df)

    # Cell means
    cell_means = df.groupby(["part_index", "appraiser"])[response].mean()
    part_means = df.groupby("part_index")[response].mean()
    appraiser_means = df.groupby("appraiser")[response].mean()

    # SS decomposition
    # SS_Total
    SS_total = float(((df[response] - grand_mean) ** 2).sum())

    # SS_Part
    SS_part = float(n_appraisers * n_trials * sum(
        (part_means[p] - grand_mean) ** 2 for p in parts
    ))

    # SS_Appraiser
    SS_appraiser = float(n_parts * n_trials * sum(
        (appraiser_means[a] - grand_mean) ** 2 for a in appraisers
    ))

    # SS_Interaction (Part × Appraiser)
    SS_cells = float(n_trials * sum(
        (cell_means.get((p, a), grand_mean) - part_means[p] - appraiser_means[a] + grand_mean) ** 2
        for p in parts for a in appraisers
    ))
    SS_interaction = SS_cells

    # SS_Error (within-cell residual)
    SS_error = SS_total - SS_part - SS_appraiser - SS_interaction

    # Degrees of freedom
    df_part = n_parts - 1
    df_appraiser = n_appraisers - 1
    df_interaction = df_part * df_appraiser
    df_error = n_parts * n_appraisers * (n_trials - 1)

    # Mean squares (guard against zero df)
    MS_part = SS_part / df_part if df_part > 0 else 0.0
    MS_appraiser = SS_appraiser / df_appraiser if df_appraiser > 0 else 0.0
    MS_interaction = SS_interaction / df_interaction if df_interaction > 0 else 0.0
    MS_error = SS_error / df_error if df_error > 0 else 0.0

    # Variance components (AIAG MSA 4th ed.)
    var_repeatability = max(0.0, MS_error)
    var_reproducibility_no_interact = max(
        0.0, (MS_appraiser - MS_interaction) / (n_parts * n_trials)
    )
    var_interaction = max(0.0, (MS_interaction - MS_error) / n_trials)
    # Reproducibility includes interaction
    var_reproducibility = var_reproducibility_no_interact + var_interaction
    var_part = max(0.0, (MS_part - MS_interaction) / (n_appraisers * n_trials))
    var_grr = var_repeatability + var_reproducibility
    var_total = var_grr + var_part

    return {
        "n_parts": n_parts,
        "n_appraisers": n_appraisers,
        "n_trials": n_trials,
        "SS_part": SS_part,
        "SS_appraiser": SS_appraiser,
        "SS_interaction": SS_interaction,
        "SS_error": SS_error,
        "MS_part": MS_part,
        "MS_appraiser": MS_appraiser,
        "MS_interaction": MS_interaction,
        "MS_error": MS_error,
        "var_repeatability": var_repeatability,
        "var_reproducibility": var_reproducibility,
        "var_interaction": var_interaction,
        "var_part": var_part,
        "var_grr": var_grr,
        "var_total": var_total,
    }


# ---------------------------------------------------------------------------
# Task 4.3 — Derived metrics
# ---------------------------------------------------------------------------

def _derived_metrics(anova: dict, tol_half: float) -> dict:
    vt = anova["var_total"]
    vgrr = anova["var_grr"]
    vrep = anova["var_repeatability"]
    vreprod = anova["var_reproducibility"]
    vp = anova["var_part"]

    def pct_contribution(v: float) -> float:
        return 100.0 * v / vt if vt > 0 else 0.0

    sigma_total = math.sqrt(vt) if vt > 0 else 0.0
    sigma_grr = math.sqrt(vgrr) if vgrr > 0 else 0.0
    sigma_part = math.sqrt(vp) if vp > 0 else 0.0

    def pct_study_var(v: float) -> float:
        return 100.0 * math.sqrt(v) / sigma_total if sigma_total > 0 else 0.0

    pct_tol = (6.0 * sigma_grr / (2.0 * tol_half) * 100.0) if tol_half > 0 else float("nan")
    ndc = max(1, math.floor(1.41 * sigma_part / sigma_grr)) if sigma_grr > 0 else 1

    return {
        "pct_contribution_repeat": pct_contribution(vrep),
        "pct_contribution_reprod": pct_contribution(vreprod),
        "pct_contribution_part": pct_contribution(vp),
        "pct_contribution_grr": pct_contribution(vgrr),
        "pct_study_var_repeat": pct_study_var(vrep),
        "pct_study_var_reprod": pct_study_var(vreprod),
        "pct_study_var_part": pct_study_var(vp),
        "pct_study_var_grr": pct_study_var(vgrr),
        "pct_tolerance": pct_tol,
        "ndc": ndc,
        "sigma_grr": sigma_grr,
        "sigma_part": sigma_part,
        "sigma_total": sigma_total,
    }


# ---------------------------------------------------------------------------
# Task 4.4 — Six-panel Gage R&R figure
# ---------------------------------------------------------------------------

def _plot_grr_panel(df_matched: pd.DataFrame, response: str,
                    anova: dict, metrics: dict,
                    scenario_id: str, run_dir: Path) -> Path:
    df = df_matched[df_matched["matched"] == True].copy()
    df[response] = pd.to_numeric(df[response], errors="coerce")
    df = df.dropna(subset=[response, "part_index", "appraiser"])
    df["part_index"] = df["part_index"].astype(int)

    fig, axes = plt.subplots(2, 3, figsize=(12, 10))
    fig.suptitle(f"{scenario_id} — Gage R&R Panel ({response})", fontsize=13)

    # 1. Components of Variation
    ax = axes[0, 0]
    components = ["Repeatability", "Reproducibility", "Part-to-Part", "GR&R"]
    pct_contrib = [
        metrics["pct_contribution_repeat"],
        metrics["pct_contribution_reprod"],
        metrics["pct_contribution_part"],
        metrics["pct_contribution_grr"],
    ]
    colors = ["steelblue", "orange", "green", "red"]
    ax.barh(components, pct_contrib, color=colors)
    ax.set_xlabel("% Contribution")
    ax.set_title("Components of Variation")
    ax.axvline(10, color="green", linestyle="--", lw=0.8, label="10%")
    ax.axvline(30, color="red", linestyle="--", lw=0.8, label="30%")
    ax.legend(fontsize=7)

    # 2. R-chart by Appraiser
    ax = axes[0, 1]
    for appr in sorted(df["appraiser"].unique()):
        sub = df[df["appraiser"] == appr]
        ranges = sub.groupby("part_index")[response].apply(lambda x: x.max() - x.min())
        ax.plot(ranges.index, ranges.values, marker="o", label=appr)
    # UCL ≈ D4 × R-bar (for n_trials=3, D4=2.575)
    if len(df) > 0:
        n_t = anova.get("n_trials", 3)
        D4 = {2: 3.267, 3: 2.575, 4: 2.282, 5: 2.115}.get(n_t, 2.575)
        all_ranges = df.groupby(["appraiser", "part_index"])[response].apply(
            lambda x: x.max() - x.min()
        )
        r_bar = all_ranges.mean()
        ucl = D4 * r_bar
        ax.axhline(ucl, color="red", linestyle="--", lw=0.8, label=f"UCL={ucl:.2f}")
    ax.set_title("R-chart by Appraiser")
    ax.set_xlabel("Part")
    ax.set_ylabel("Range")
    ax.legend(fontsize=7)

    # 3. Xbar-chart by Appraiser
    ax = axes[0, 2]
    grand_mean = df[response].mean()
    for appr in sorted(df["appraiser"].unique()):
        sub = df[df["appraiser"] == appr]
        means = sub.groupby("part_index")[response].mean()
        ax.plot(means.index, means.values, marker="s", label=appr)
    ax.axhline(grand_mean, color="black", linestyle="--", lw=0.8, label="Grand mean")
    ax.set_title("Xbar-chart by Appraiser")
    ax.set_xlabel("Part")
    ax.set_ylabel("Mean")
    ax.legend(fontsize=7)

    # 4. Measurement by Part
    ax = axes[1, 0]
    parts = sorted(df["part_index"].unique())
    data_by_part = [df[df["part_index"] == p][response].dropna().values for p in parts]
    ax.boxplot(data_by_part, positions=parts, widths=0.6)
    ax.set_title("Measurement by Part")
    ax.set_xlabel("Part")
    ax.set_ylabel(response)

    # 5. Measurement by Appraiser
    ax = axes[1, 1]
    appraisers = sorted(df["appraiser"].unique())
    data_by_app = [df[df["appraiser"] == a][response].dropna().values for a in appraisers]
    ax.boxplot(data_by_app, tick_labels=appraisers)
    ax.set_title("Measurement by Appraiser")
    ax.set_ylabel(response)

    # 6. Appraiser × Part Interaction
    ax = axes[1, 2]
    for appr in sorted(df["appraiser"].unique()):
        sub = df[df["appraiser"] == appr]
        means = sub.groupby("part_index")[response].mean()
        ax.plot(means.index, means.values, marker="^", label=appr)
    ax.set_title("Appraiser × Part Interaction")
    ax.set_xlabel("Part")
    ax.set_ylabel(f"Mean {response}")
    ax.legend(fontsize=7)

    plt.tight_layout()
    out_path = run_dir / f"{scenario_id}_grr_panel.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Task 4.5 — S1 Bias & Linearity
# ---------------------------------------------------------------------------

def _bias_linearity(df_matched: pd.DataFrame, run_dir: Path) -> dict:
    df = df_matched[df_matched["matched"] == True].copy()
    df["reported_snr_db"] = pd.to_numeric(df["reported_snr_db"], errors="coerce")
    df["true_snr_db"] = pd.to_numeric(df["true_snr_db"], errors="coerce")
    df = df.dropna(subset=["reported_snr_db", "true_snr_db"])
    df["bias"] = df["reported_snr_db"] - df["true_snr_db"]

    results: dict[str, dict] = {}

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(0, color="black", linestyle="--", lw=0.8)

    for appr in APPRAISERS:
        sub = df[df["appraiser"] == appr]
        if sub.empty:
            continue
        x = sub["true_snr_db"].values
        y = sub["bias"].values
        mean_bias = float(np.mean(y))
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = float(coeffs[0]), float(coeffs[1])
        y_pred = np.polyval(coeffs, x)
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        results[appr] = {
            "mean_bias": mean_bias,
            "slope": slope,
            "intercept": intercept,
            "r2": r2,
        }

        x_line = np.linspace(x.min(), x.max(), 50)
        ax.scatter(x, y, label=f"{appr} (bias)", alpha=0.6, s=20)
        ax.plot(x_line, np.polyval(coeffs, x_line),
                label=f"{appr} fit (slope={slope:.3f})")

    ax.set_xlabel("True SNR (dB)")
    ax.set_ylabel("Bias = Reported − True (dB)")
    ax.set_title("S1 Bias & Linearity")
    ax.legend(fontsize=8)
    plt.tight_layout()
    out_path = run_dir / "S1_bias_linearity.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    return results


# ---------------------------------------------------------------------------
# Task 4.6 — Kappa for attribute scenarios
# ---------------------------------------------------------------------------

def _compute_kappa(df_matched: pd.DataFrame, scenario_id: str) -> dict:
    """Compute Cohen's κ for S4/S5 with 95% CI via bootstrap."""
    from sklearn.metrics import cohen_kappa_score

    df = df_matched[df_matched["false_positive"] == False].copy()

    # Binary decision: matched (True) or not-matched (False)
    truth_decisions: dict[tuple, bool] = {}
    # Group by (part_index, trial_index) to get the "truth" label (always True if injected)
    for _, row in df.iterrows():
        key = (row["part_index"], row["trial_index"])
        # truth: the signal was injected, so the "true label" is always True (decoded expected)
        truth_decisions[key] = True

    results: dict = {}

    appr_decisions: dict[str, dict[tuple, bool]] = {}
    for appr in APPRAISERS:
        sub = df[df["appraiser"] == appr]
        appr_decisions[appr] = {}
        for _, row in sub.iterrows():
            key = (row["part_index"], row["trial_index"])
            appr_decisions[appr][key] = bool(row["matched"])

    # Each-appraiser-vs-truth Kappa
    all_keys = sorted(set(truth_decisions.keys()))
    truth_labels = [truth_decisions.get(k, True) for k in all_keys]

    for appr in APPRAISERS:
        app_labels = [appr_decisions.get(appr, {}).get(k, False) for k in all_keys]
        if len(set(truth_labels)) < 2 or len(set(app_labels)) < 2:
            kappa = float("nan")
            ci_lo, ci_hi = float("nan"), float("nan")
        else:
            kappa = float(cohen_kappa_score(truth_labels, app_labels))
            # Bootstrap 95% CI
            rng = np.random.default_rng(seed=42)
            boot_kappas = []
            n = len(truth_labels)
            for _ in range(1000):
                idx = rng.integers(0, n, size=n)
                t_boot = [truth_labels[i] for i in idx]
                a_boot = [app_labels[i] for i in idx]
                if len(set(t_boot)) < 2 or len(set(a_boot)) < 2:
                    continue
                try:
                    boot_kappas.append(float(cohen_kappa_score(t_boot, a_boot)))
                except Exception:
                    pass
            if boot_kappas:
                ci_lo = float(np.percentile(boot_kappas, 2.5))
                ci_hi = float(np.percentile(boot_kappas, 97.5))
            else:
                ci_lo = ci_hi = kappa

        results[f"{appr}_vs_truth"] = {"kappa": kappa, "ci_lo": ci_lo, "ci_hi": ci_hi}

    # Between-appraiser Kappa
    a1_labels = [appr_decisions.get(APPRAISERS[0], {}).get(k, False) for k in all_keys]
    a2_labels = [appr_decisions.get(APPRAISERS[1], {}).get(k, False) for k in all_keys]
    if len(set(a1_labels)) < 2 or len(set(a2_labels)) < 2:
        ba_kappa = float("nan")
    else:
        ba_kappa = float(cohen_kappa_score(a1_labels, a2_labels))
    results["between_appraisers"] = {"kappa": ba_kappa}

    return results


# ---------------------------------------------------------------------------
# Task 4.7 — False-positive rate (S5)
# ---------------------------------------------------------------------------

def _fp_rate(df_matched: pd.DataFrame) -> dict[str, float]:
    """Compute false-positive rate per appraiser for S5."""
    results: dict[str, float] = {}
    # Total signal-free cycles = total rows (all are signal-free)
    total_cycles_df = df_matched[df_matched["false_positive"] == False]
    # Actually for S5 there are no truth rows with signals — every injected row IS signal-free.
    # FP = rows where false_positive=True; denominator = all app-log rows (FP + non-FP app rows)
    for appr in APPRAISERS:
        sub = df_matched[df_matched["appraiser"] == appr]
        n_fp = int((sub["false_positive"] == True).sum())
        n_total = len(sub)
        if n_total == 0:
            print(f"WARNING: S5 — zero app-log rows for {appr}; FP rate undefined", file=sys.stderr)
            results[appr] = float("nan")
        else:
            results[appr] = 100.0 * n_fp / n_total
    return results


# ---------------------------------------------------------------------------
# Task 4.8 — Verdict engine
# ---------------------------------------------------------------------------

def _collect_verdicts(
    continuous_results: dict[str, dict],
    kappa_results: dict[str, dict],
    fp_results: dict[str, float],
    bias_results: dict[str, dict],
) -> tuple[list[tuple[str, str, float | str, str]], str]:
    """Collect all metric verdicts and return (rows, overall_verdict)."""
    verdict_rows: list[tuple[str, str, float | str, str]] = []
    # (metric_name, scenario/appraiser, value, verdict)
    fails: list[str] = []
    marginals: list[str] = []

    for scen_id, res in continuous_results.items():
        if res is None:
            continue
        pct_grr = res["metrics"]["pct_contribution_grr"]
        ndc = res["metrics"]["ndc"]
        v_grr = _verdict_grr(pct_grr)
        v_ndc = _verdict_ndc(ndc)
        verdict_rows.append(("%GR&R", scen_id, f"{pct_grr:.1f}%", v_grr))
        verdict_rows.append(("ndc", scen_id, str(ndc), v_ndc))
        if v_grr == "FAIL":
            fails.append(f"%GR&R ({scen_id}) = {pct_grr:.1f}% (threshold: < {THRESH_GRR_PASS}% Acceptable)")
        elif v_grr == "MARGINAL":
            marginals.append(f"%GR&R ({scen_id}) = {pct_grr:.1f}%")

    for label, info in kappa_results.items():
        kappa = info.get("kappa", float("nan"))
        if math.isnan(kappa):
            continue
        v = _verdict_kappa(kappa)
        verdict_rows.append(("Kappa", label, f"{kappa:.3f}", v))
        if v == "FAIL":
            fails.append(f"Kappa ({label}) = {kappa:.3f} (threshold: ≥ {THRESH_KAPPA_PASS} Acceptable)")
        elif v == "MARGINAL":
            marginals.append(f"Kappa ({label}) = {kappa:.3f}")

    for appr, rate in fp_results.items():
        if math.isnan(rate):
            continue
        v = _verdict_fp(rate)
        verdict_rows.append(("FP rate", f"S5/{appr}", f"{rate:.1f}%", v))
        if v == "FAIL":
            fails.append(f"FP rate ({appr}) = {rate:.1f}% (threshold: ≤ {THRESH_FP_PASS}%)")

    for appr, info in bias_results.items():
        bias = info.get("mean_bias", float("nan"))
        if math.isnan(bias):
            continue
        v = _verdict_bias(bias)
        verdict_rows.append(("SNR bias", f"S1/{appr}", f"{bias:+.2f} dB", v))
        if v == "FAIL":
            fails.append(
                f"SNR bias ({appr}) = {bias:+.2f} dB (threshold: ≤ ±{THRESH_BIAS_PASS} dB)"
            )

    if fails:
        overall = "FAIL"
    elif marginals:
        overall = "MARGINAL"
    else:
        overall = "PASS"

    return verdict_rows, overall, fails


# ---------------------------------------------------------------------------
# Task 4.9 — Write report.md
# ---------------------------------------------------------------------------

def _fmt_num(v: Any, fmt: str = ".2f") -> str:
    if isinstance(v, float) and math.isnan(v):
        return "—"
    try:
        return format(float(v), fmt)
    except (TypeError, ValueError):
        return str(v)


def _write_report(
    run_dir: Path,
    git_sha: str,
    continuous_results: dict,
    kappa_results: dict,
    fp_results: dict,
    bias_results: dict,
    verdict_rows: list,
    overall: str,
    fails: list[str],
) -> Path:
    lines: list[str] = []
    run_date = run_dir.name.split("-")[0:3]
    run_date_str = "-".join(run_date) if len(run_date) >= 3 else run_dir.name

    # WSJT-X version
    ver_path = run_dir / "wsjt-version.txt"
    wsjt_ver = ver_path.read_text(encoding="utf-8").strip() if ver_path.exists() else "unknown"

    lines += [
        "# OpenWSFZ R&R Study Report",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Run date | {run_date_str} |",
        f"| OpenWSFZ SHA | `{git_sha}` |",
        f"| WSJT-X version | {wsjt_ver} |",
        "",
    ]

    # Continuous scenarios
    for scen_id, res in sorted(continuous_results.items()):
        if res is None:
            lines += [f"## {scen_id}", "", "_Insufficient data — skipped._", ""]
            continue
        anova = res["anova"]
        metrics = res["metrics"]
        response = res["response"]
        tol_half = res["tol_half"]

        lines += [
            f"## {scen_id} — {response}",
            "",
            "### Variance Components",
            "",
            "| Component | σ² | %Contribution |",
            "|---|---|---|",
            f"| Repeatability | {_fmt_num(anova['var_repeatability'])} | {_fmt_num(metrics['pct_contribution_repeat'])}% |",
            f"| Reproducibility | {_fmt_num(anova['var_reproducibility'])} | {_fmt_num(metrics['pct_contribution_reprod'])}% |",
            f"| Part-to-Part | {_fmt_num(anova['var_part'])} | {_fmt_num(metrics['pct_contribution_part'])}% |",
            f"| Total GR&R | {_fmt_num(anova['var_grr'])} | {_fmt_num(metrics['pct_contribution_grr'])}% |",
            f"| Total | {_fmt_num(anova['var_total'])} | 100.00% |",
            "",
            "### Study Metrics",
            "",
            "| Metric | Value | Verdict |",
            "|---|---|---|",
            f"| %Tolerance (GR&R) | {_fmt_num(metrics['pct_tolerance'])}% | {_verdict_grr(metrics['pct_contribution_grr'])} |",
            f"| %Study Var (GR&R) | {_fmt_num(metrics['pct_study_var_grr'])}% | — |",
            f"| ndc | {metrics['ndc']} | {_verdict_ndc(metrics['ndc'])} |",
            "",
        ]
        # Embedded PNG
        png_name = f"{scen_id}_grr_panel.png"
        lines += [f"![{scen_id} GR&R panel]({png_name})", ""]

        if scen_id == "S1" and bias_results:
            lines += ["### Bias & Linearity (S1)", ""]
            lines += ["| Appraiser | Mean Bias (dB) | Slope | Intercept | R² | Verdict |",
                      "|---|---|---|---|---|---|"]
            for appr, bi in bias_results.items():
                v = _verdict_bias(bi["mean_bias"])
                lines.append(
                    f"| {appr} | {bi['mean_bias']:+.2f} | {bi['slope']:.3f} | "
                    f"{bi['intercept']:.3f} | {bi['r2']:.3f} | {v} |"
                )
            lines += ["", f"![S1 Bias & Linearity](S1_bias_linearity.png)", ""]

    # Attribute scenarios
    if kappa_results:
        lines += ["## Attribute Agreement Analysis (S4/S5)", ""]
        lines += ["### Kappa", ""]
        lines += ["| Pair | κ | 95% CI | Verdict |",
                  "|---|---|---|---|"]
        for label, info in sorted(kappa_results.items()):
            kappa = info.get("kappa", float("nan"))
            if "ci_lo" in info:
                ci = f"[{_fmt_num(info['ci_lo'])}, {_fmt_num(info['ci_hi'])}]"
            else:
                ci = "—"
            v = _verdict_kappa(kappa) if not math.isnan(kappa) else "—"
            lines.append(f"| {label} | {_fmt_num(kappa, '.3f')} | {ci} | {v} |")
        lines += [""]

    if fp_results:
        lines += ["### False-positive rate (S5)", ""]
        lines += ["| Appraiser | FP rate | Verdict |",
                  "|---|---|---|"]
        for appr, rate in fp_results.items():
            v = _verdict_fp(rate) if not math.isnan(rate) else "—"
            lines.append(f"| {appr} | {_fmt_num(rate)}% | {v} |")
        lines += [""]

    # Summary
    lines += [
        "## Summary",
        "",
        "| Metric | Scope | Value | Verdict |",
        "|---|---|---|---|",
    ]
    for row in verdict_rows:
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
    lines += [
        "",
        f"**Overall verdict: {overall}**",
        "",
    ]

    if fails:
        lines += ["### Defect Notices", ""]
        for f in fails:
            lines.append(f"- ❌ FAIL — {f}")
        lines += [""]

    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Task 4.10 — Append trend.csv
# ---------------------------------------------------------------------------

_TREND_COLUMNS = [
    "run_date", "git_sha", "pct_grr_snr", "ndc_snr", "bias_snr_owsfz",
    "kappa_s4", "fp_rate_s5",
]


def _append_trend(qa_rr_root: Path, run_dir: Path, git_sha: str,
                  continuous_results: dict, kappa_results: dict,
                  fp_results: dict, bias_results: dict) -> None:
    trend_path = qa_rr_root / "trend.csv"
    write_header = not trend_path.exists()

    run_date = run_dir.name.split("-")[0:3]
    run_date_str = "-".join(run_date) if len(run_date) >= 3 else run_dir.name

    def _safe(v: Any) -> str:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        return str(v)

    pct_grr_snr = ""
    ndc_snr = ""
    if "S1" in continuous_results and continuous_results["S1"] is not None:
        pct_grr_snr = _safe(continuous_results["S1"]["metrics"]["pct_contribution_grr"])
        ndc_snr = _safe(continuous_results["S1"]["metrics"]["ndc"])

    bias_snr_owsfz = ""
    if "OpenWSFZ" in bias_results:
        bias_snr_owsfz = _safe(bias_results["OpenWSFZ"].get("mean_bias"))

    kappa_s4 = ""
    for label, info in kappa_results.items():
        if "OpenWSFZ_vs_truth" in label:
            kappa_s4 = _safe(info.get("kappa"))
            break

    fp_rate_s5 = ""
    if "OpenWSFZ" in fp_results:
        fp_rate_s5 = _safe(fp_results.get("OpenWSFZ"))

    row = {
        "run_date": run_date_str,
        "git_sha": git_sha,
        "pct_grr_snr": pct_grr_snr,
        "ndc_snr": ndc_snr,
        "bias_snr_owsfz": bias_snr_owsfz,
        "kappa_s4": kappa_s4,
        "fp_rate_s5": fp_rate_s5,
    }

    with open(trend_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_TREND_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Task 4.11 — Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="R&R study analyser — compute Gage R&R and write report.md"
    )
    parser.add_argument("--run-dir", required=True, help="Run directory containing *_matched.csv files")
    parser.add_argument(
        "--scenario",
        help="Comma-separated scenario IDs to analyse (default: all found in run-dir)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        sys.exit(f"ERROR: run directory does not exist: {run_dir}")

    scenario_filter = [s.strip() for s in args.scenario.split(",")] if args.scenario else None
    scenarios_dir = _QA_ROOT / "scenarios"

    # Load matched CSVs
    matched = _load_matched_csvs(run_dir, scenario_filter, scenarios_dir)
    if not matched:
        sys.exit(f"ERROR: no *_matched.csv files found in {run_dir}")

    print(f"Analysing: {', '.join(sorted(matched.keys()))}")

    git_sha = _git_sha()
    continuous_results: dict = {}
    kappa_results: dict = {}
    fp_results: dict = {}
    bias_results: dict = {}

    # --- Continuous scenarios ---
    for scen_id, df in matched.items():
        if scen_id not in CONTINUOUS_SCENARIOS:
            continue
        response = RESPONSE_VAR[scen_id]
        tol_half = TOLERANCE_HALF[scen_id]
        anova = _two_way_anova(df, response, scen_id)
        if anova is None:
            continuous_results[scen_id] = None
            continue
        metrics = _derived_metrics(anova, tol_half)
        continuous_results[scen_id] = {
            "anova": anova,
            "metrics": metrics,
            "response": response,
            "tol_half": tol_half,
        }
        print(f"  {scen_id}: %GR&R={metrics['pct_contribution_grr']:.1f}%  ndc={metrics['ndc']}")
        # Six-panel chart
        png = _plot_grr_panel(df, response, anova, metrics, scen_id, run_dir)
        print(f"    -> {png.name}")

    # --- S1 Bias & Linearity ---
    if "S1" in matched and continuous_results.get("S1") is not None:
        bias_results = _bias_linearity(matched["S1"], run_dir)
        for appr, info in bias_results.items():
            print(f"  S1 bias ({appr}): {info['mean_bias']:+.2f} dB  slope={info['slope']:.3f}")

    # --- Attribute scenarios ---
    for scen_id, df in matched.items():
        if scen_id not in ATTRIBUTE_SCENARIOS:
            continue
        if scen_id == "S5":
            fp_results = _fp_rate(df)
            for appr, rate in fp_results.items():
                print(f"  S5 FP rate ({appr}): {_fmt_num(rate)}%")
        kappas = _compute_kappa(df, scen_id)
        kappa_results.update(kappas)
        for label, info in kappas.items():
            print(f"  Kappa {label}: {_fmt_num(info.get('kappa', float('nan')), '.3f')}")

    # --- Verdicts ---
    verdict_rows, overall, fails = _collect_verdicts(
        continuous_results, kappa_results, fp_results, bias_results
    )

    # --- Write report ---
    report_path = _write_report(
        run_dir, git_sha, continuous_results, kappa_results,
        fp_results, bias_results, verdict_rows, overall, fails
    )
    print(f"\nReport written: {report_path}")
    print(f"Overall verdict: {overall}")

    if fails:
        print("\n⚠  DEFECT NOTICES:")
        for f in fails:
            print(f"  FAIL — {f}")

    # --- Trend CSV ---
    _append_trend(_QA_ROOT, run_dir, git_sha, continuous_results,
                  kappa_results, fp_results, bias_results)
    print(f"Trend row appended: {_QA_ROOT / 'trend.csv'}")

    # --- Append trend row ---
    # (already done above)


if __name__ == "__main__":
    main()
