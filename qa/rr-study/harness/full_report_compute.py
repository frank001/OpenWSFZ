#!/usr/bin/env python3
"""Compute all Gauge R&R statistics needed for the combined full report.

Usage:
    python harness/full_report_compute.py

Reads from:
  - results/2026-06-07-4b3a4ca  (full run: S1..S8, wideband noise)
  - results/2026-06-09-d509b08  (targeted: S1+S1b, bandlimited noise)
"""
import csv
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE     = Path(__file__).resolve().parent.parent          # qa/rr-study/
FULL_RUN = HERE / "results" / "2026-06-07-4b3a4ca"
NEW_RUN  = HERE / "results" / "2026-06-09-d509b08"


# ─────────────────────────────────────────────────────────────────────────────
# Generic helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_matched(csv_path: Path, measure_col: str):
    """Return list of dicts with appraiser/part/trial/reference/measured."""
    rows = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            if r["false_positive"] == "True":
                continue
            if r["matched"] != "True":
                continue
            if r["part_index"] == "":
                continue
            ref_col = {
                "reported_snr_db":  "true_snr_db",
                "reported_freq_hz": "true_freq_hz",
                "reported_dt_s":    "true_dt_s",
            }[measure_col]
            if not r[measure_col] or not r[ref_col]:
                continue
            rows.append({
                "appraiser": r["appraiser"],
                "part":      int(r["part_index"]),
                "trial":     int(r["trial_index"]),
                "reference": float(r[ref_col]),
                "measured":  float(r[measure_col]),
            })
    return rows


def grr_anova(rows, tolerance: float):
    """Full two-way ANOVA crossed Gauge R&R.  Returns dict of all stats."""
    from scipy.stats import f as fdist, t as tdist

    appraisers = sorted(set(r["appraiser"] for r in rows))
    parts      = sorted(set(r["part"]      for r in rows))
    a, b       = len(appraisers), len(parts)

    # Verify balanced design
    n_list = []
    Y = {app: {} for app in appraisers}
    for r in rows:
        Y[r["appraiser"]].setdefault(r["part"], []).append(r["measured"])
    for app in appraisers:
        for p in parts:
            n_list.append(len(Y[app][p]))
    assert len(set(n_list)) == 1, f"Unbalanced design: {set(n_list)}"
    n = n_list[0]
    N = a * b * n

    # Reference values per part
    ref = {}
    for r in rows:
        ref[r["part"]] = r["reference"]

    # Means
    all_vals   = [Y[app][p][t] for app in appraisers for p in parts for t in range(n)]
    grand_mean = sum(all_vals) / N
    cell_mean  = {(app,p): sum(Y[app][p])/n for app in appraisers for p in parts}
    op_mean    = {app: sum(Y[app][p][t] for p in parts for t in range(n))/(b*n)
                  for app in appraisers}
    part_mean  = {p: sum(Y[app][p][t] for app in appraisers for t in range(n))/(a*n)
                  for p in parts}

    # SS
    SS_part  = a*n * sum((part_mean[p]-grand_mean)**2 for p in parts)
    SS_op    = b*n * sum((op_mean[app]-grand_mean)**2 for app in appraisers)
    SS_inter = n   * sum((cell_mean[(app,p)]-op_mean[app]-part_mean[p]+grand_mean)**2
                         for app in appraisers for p in parts)
    SS_error = sum((Y[app][p][t]-cell_mean[(app,p)])**2
                   for app in appraisers for p in parts for t in range(n))
    SS_total = sum((v-grand_mean)**2 for v in all_vals)

    df_part, df_op, df_inter = b-1, a-1, (a-1)*(b-1)
    df_error, df_total       = a*b*(n-1), N-1

    MS_part  = SS_part  / df_part
    MS_op    = SS_op    / df_op
    MS_inter = SS_inter / df_inter
    MS_error = SS_error / df_error

    F_part  = MS_part  / MS_inter
    F_op    = MS_op    / MS_inter
    F_inter = MS_inter / MS_error
    P_part  = 1 - fdist.cdf(F_part,  df_part,  df_inter)
    P_op    = 1 - fdist.cdf(F_op,    df_op,    df_inter)
    P_inter = 1 - fdist.cdf(F_inter, df_inter, df_error)

    # Variance components (AIAG method, with-interaction model)
    var_repeat    = MS_error
    var_op_x_part = max(0.0, (MS_inter - MS_error) / n)
    var_operator  = max(0.0, (MS_op    - MS_inter)  / (b*n))
    var_reprod    = var_operator + var_op_x_part
    var_grr       = var_repeat + var_reprod
    var_part_     = max(0.0, (MS_part  - MS_inter)  / (a*n))
    var_total     = var_grr + var_part_

    def sv(v):   return 6 * math.sqrt(max(0.0, v))
    def pct_sv(v): return 100*sv(v)/sv(var_total) if var_total > 0 else 0
    def pct_tol(v): return 100*sv(v)/tolerance    if tolerance > 0 else 0

    ndc = max(1, int(1.41 * math.sqrt(var_part_/var_grr))) if var_grr > 0 else 1

    # Bias / linearity per appraiser
    bias_by_app = {}
    for app in appraisers:
        xs  = [ref[p]           for p in parts]
        obs = [sum(Y[app][p])/n for p in parts]
        bs  = [o-x for o,x in zip(obs,xs)]
        n_  = len(xs)
        x_bar, y_bar = sum(xs)/n_, sum(bs)/n_
        Sxx  = sum((x-x_bar)**2 for x in xs)
        Sxy  = sum((x-x_bar)*(y-y_bar) for x,y in zip(xs,bs))
        slope = Sxy/Sxx if Sxx else 0
        intercept = y_bar - slope*x_bar
        ss_res = sum((y-(slope*x+intercept))**2 for x,y in zip(xs,bs))
        ss_tot = sum((y-y_bar)**2 for y in bs)
        r2 = 1-ss_res/ss_tot if ss_tot>0 else 0.0
        se  = math.sqrt(sum((y-y_bar)**2 for y in bs)/(n_-1))/math.sqrt(n_) if n_>1 else 0
        t_s = y_bar/se if se>0 else float("inf")
        p_b = 2*(1-tdist.cdf(abs(t_s), n_-1)) if n_>1 else 0
        bias_by_app[app] = {
            "parts": list(zip(xs, obs, bs)),
            "mean_bias": y_bar, "slope": slope, "intercept": intercept,
            "r2": r2, "p_bias": p_b, "se": se,
        }

    return {
        # design
        "appraisers": appraisers, "parts": parts, "a": a, "b": b, "n": n, "N": N,
        "Y": Y, "ref": ref,
        # ANOVA
        "SS_part": SS_part, "SS_op": SS_op, "SS_inter": SS_inter,
        "SS_error": SS_error, "SS_total": SS_total,
        "df_part": df_part, "df_op": df_op, "df_inter": df_inter,
        "df_error": df_error, "df_total": df_total,
        "MS_part": MS_part, "MS_op": MS_op, "MS_inter": MS_inter, "MS_error": MS_error,
        "F_part": F_part, "F_op": F_op, "F_inter": F_inter,
        "P_part": P_part, "P_op": P_op, "P_inter": P_inter,
        # variance components
        "var_repeat": var_repeat, "var_op_x_part": var_op_x_part,
        "var_operator": var_operator, "var_reprod": var_reprod,
        "var_grr": var_grr, "var_part": var_part_, "var_total": var_total,
        # study variation
        "sv": sv, "pct_sv": pct_sv, "pct_tol": pct_tol, "tolerance": tolerance,
        "ndc": ndc,
        # bias
        "bias_by_app": bias_by_app,
    }


def fmt_p(p):
    return "0.000" if p < 0.001 else f"{p:.3f}"


def print_grr(label, g, measure_unit=""):
    SEP = "─" * 72
    print(f"\n{'═'*72}")
    print(f"  {label}")
    print(f"  Measure: {measure_unit}   Tolerance: ±{g['tolerance']/2} → {g['tolerance']} total")
    print(f"{'═'*72}")

    print(f"\n{'─'*72}")
    print(f"  Two-Way ANOVA Table (with interaction)")
    print(f"{'─'*72}")
    print(f"  {'Source':<22}  {'DF':>4}  {'SS':>12}  {'MS':>12}  {'F':>9}  {'P':>7}")
    print(f"  {SEP[:68]}")
    print(f"  {'Part':<22}  {g['df_part']:>4}  {g['SS_part']:>12.4f}  {g['MS_part']:>12.4f}  {g['F_part']:>9.3f}  {fmt_p(g['P_part']):>7}")
    print(f"  {'Appraiser':<22}  {g['df_op']:>4}  {g['SS_op']:>12.4f}  {g['MS_op']:>12.4f}  {g['F_op']:>9.3f}  {fmt_p(g['P_op']):>7}")
    inter_note = "  ← not significant" if g['P_inter'] > 0.05 else ""
    print(f"  {'Appraiser×Part':<22}  {g['df_inter']:>4}  {g['SS_inter']:>12.4f}  {g['MS_inter']:>12.4f}  {g['F_inter']:>9.3f}  {fmt_p(g['P_inter']):>7}{inter_note}")
    print(f"  {'Repeatability':<22}  {g['df_error']:>4}  {g['SS_error']:>12.4f}  {g['MS_error']:>12.4f}")
    print(f"  {'Total':<22}  {g['df_total']:>4}  {g['SS_total']:>12.4f}")

    print(f"\n{'─'*72}")
    print(f"  Variance Components")
    print(f"{'─'*72}")
    vt = g['var_total']
    print(f"  {'Source':<30}  {'VarComp':>10}  {'%Contribution':>14}")
    print(f"  {SEP[:58]}")
    print(f"  {'Total Gauge R&R':<30}  {g['var_grr']:>10.5f}  {100*g['var_grr']/vt:>13.2f}%")
    print(f"  {'  Repeatability':<30}  {g['var_repeat']:>10.5f}  {100*g['var_repeat']/vt:>13.2f}%")
    print(f"  {'  Reproducibility':<30}  {g['var_reprod']:>10.5f}  {100*g['var_reprod']/vt:>13.2f}%")
    print(f"  {'    Appraiser':<30}  {g['var_operator']:>10.5f}  {100*g['var_operator']/vt:>13.2f}%")
    print(f"  {'    Appraiser×Part':<30}  {g['var_op_x_part']:>10.5f}  {100*g['var_op_x_part']/vt:>13.2f}%")
    print(f"  {'Part-To-Part':<30}  {g['var_part']:>10.5f}  {100*g['var_part']/vt:>13.2f}%")
    print(f"  {'Total Variation':<30}  {g['var_total']:>10.5f}  {'100.00%':>14}")

    print(f"\n{'─'*72}")
    print(f"  Study Variation  (6σ)   tolerance = {g['tolerance']} {measure_unit}")
    print(f"{'─'*72}")
    print(f"  {'Source':<30}  {'StdDev':>9}  {'StudyVar':>10}  {'%StudyVar':>11}  {'%Tolerance':>12}")
    print(f"  {SEP[:68]}")
    sv, pct_sv, pct_tol = g['sv'], g['pct_sv'], g['pct_tol']
    print(f"  {'Total Gauge R&R':<30}  {math.sqrt(g['var_grr']):>9.4f}  {sv(g['var_grr']):>10.4f}  {pct_sv(g['var_grr']):>10.2f}%  {pct_tol(g['var_grr']):>11.2f}%")
    print(f"  {'  Repeatability':<30}  {math.sqrt(g['var_repeat']):>9.4f}  {sv(g['var_repeat']):>10.4f}  {pct_sv(g['var_repeat']):>10.2f}%  {pct_tol(g['var_repeat']):>11.2f}%")
    print(f"  {'  Reproducibility':<30}  {math.sqrt(g['var_reprod']):>9.4f}  {sv(g['var_reprod']):>10.4f}  {pct_sv(g['var_reprod']):>10.2f}%  {pct_tol(g['var_reprod']):>11.2f}%")
    print(f"  {'    Appraiser':<30}  {math.sqrt(g['var_operator']):>9.4f}  {sv(g['var_operator']):>10.4f}  {pct_sv(g['var_operator']):>10.2f}%  {pct_tol(g['var_operator']):>11.2f}%")
    print(f"  {'    Appraiser×Part':<30}  {math.sqrt(g['var_op_x_part']):>9.4f}  {sv(g['var_op_x_part']):>10.4f}  {pct_sv(g['var_op_x_part']):>10.2f}%  {pct_tol(g['var_op_x_part']):>11.2f}%")
    print(f"  {'Part-To-Part':<30}  {math.sqrt(g['var_part']):>9.4f}  {sv(g['var_part']):>10.4f}  {pct_sv(g['var_part']):>10.2f}%  {pct_tol(g['var_part']):>11.2f}%")
    print(f"  {'Total Variation':<30}  {math.sqrt(g['var_total']):>9.4f}  {sv(g['var_total']):>10.4f}  {'100.00%':>11}  {pct_tol(g['var_total']):>11.2f}%")
    print(f"\n  Number of Distinct Categories (ndc) = {g['ndc']}")


# ─────────────────────────────────────────────────────────────────────────────
# Load and compute all scenarios
# ─────────────────────────────────────────────────────────────────────────────

# S1 — SNR (old: wideband noise)
rows_s1_old = load_matched(FULL_RUN / "S1_matched.csv", "reported_snr_db")
g_s1_old = grr_anova(rows_s1_old, tolerance=4.0)

# S1 — SNR (new: bandlimited noise, this is the authoritative S1)
rows_s1_new = load_matched(NEW_RUN / "S1_matched.csv", "reported_snr_db")
g_s1_new = grr_anova(rows_s1_new, tolerance=4.0)

# S2 — frequency
rows_s2 = load_matched(FULL_RUN / "S2_matched.csv", "reported_freq_hz")
g_s2 = grr_anova(rows_s2, tolerance=50.0)  # ±25 Hz tolerance

# S3 — DT
rows_s3 = load_matched(FULL_RUN / "S3_matched.csv", "reported_dt_s")
g_s3 = grr_anova(rows_s3, tolerance=0.3)  # ±0.15 s

# ─────────────────────────────────────────────────────────────────────────────
# Print all computed statistics
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "█"*72)
print("  FULL GAUGE R&R STATISTICS — All Scenarios")
print("  Source run (S1–S8 baseline): 2026-06-07-4b3a4ca")
print("  S1/S1b noise model update:   2026-06-09-d509b08")
print("█"*72)

print_grr("S1 — SNR Repeatability/Bias  [NOISE MODEL: wideband AWGN — SUPERSEDED]",
          g_s1_old, measure_unit="dB")

print_grr("S1 — SNR Repeatability/Bias  [NOISE MODEL: bandlimited 3 kHz — CURRENT]",
          g_s1_new, measure_unit="dB")

print_grr("S2 — Frequency Accuracy",  g_s2, measure_unit="Hz")
print_grr("S3 — DT (timing) Accuracy", g_s3, measure_unit="s")

# S1 bias comparison table
print(f"\n{'═'*72}")
print("  S1 BIAS — PER PART COMPARISON  (wideband → bandlimited)")
print(f"{'═'*72}")
print(f"  {'Part':>4}  {'Ref(dB)':>8}  {'WX-old':>7}  {'OW-old':>7}  {'bWX':>7}  {'bOW':>7}  {'ΔWX':>6}  {'ΔOW':>6}")
old_ba = g_s1_old["bias_by_app"]
new_ba = g_s1_new["bias_by_app"]
for i, p in enumerate(g_s1_old["parts"]):
    ref = g_s1_old["ref"][p]
    wx_old = old_ba["WSJT-X"]["parts"][i][2]
    ow_old = old_ba["OpenWSFZ"]["parts"][i][2]
    wx_new = new_ba["WSJT-X"]["parts"][i][2]
    ow_new = new_ba["OpenWSFZ"]["parts"][i][2]
    print(f"  {p:>4}  {ref:>8.1f}  {wx_old:>+7.2f}  {ow_old:>+7.2f}  {wx_new:>+7.2f}  {ow_new:>+7.2f}  {wx_new-wx_old:>+6.2f}  {ow_new-ow_old:>+6.2f}")

print(f"\n  {'Mean':>4}  {'':>8}  {old_ba['WSJT-X']['mean_bias']:>+7.2f}  {old_ba['OpenWSFZ']['mean_bias']:>+7.2f}  {new_ba['WSJT-X']['mean_bias']:>+7.2f}  {new_ba['OpenWSFZ']['mean_bias']:>+7.2f}  {new_ba['WSJT-X']['mean_bias']-old_ba['WSJT-X']['mean_bias']:>+6.2f}  {new_ba['OpenWSFZ']['mean_bias']-old_ba['OpenWSFZ']['mean_bias']:>+6.2f}")

# S1b from both runs
print(f"\n{'═'*72}")
print("  S1b — DECODE SENSITIVITY  (per-part, both noise models)")
print(f"{'═'*72}")
for run_label, run_dir in [("Wideband AWGN (4b3a4ca)", FULL_RUN),
                            ("Bandlimited 3kHz (d509b08)", NEW_RUN)]:
    s1b = []
    with open(run_dir / "S1b_matched.csv") as f:
        for r in csv.DictReader(f):
            if r["false_positive"] == "True" or r["part_index"] == "":
                continue
            s1b.append({
                "app": r["appraiser"], "part": int(r["part_index"]),
                "true_snr": float(r["true_snr_db"]),
                "matched": r["matched"] == "True",
                "rep_snr": float(r["reported_snr_db"]) if r["reported_snr_db"] else None,
            })
    parts_s1b = sorted(set(r["part"] for r in s1b))
    true_s1b  = {r["part"]: r["true_snr"] for r in s1b}
    print(f"\n  [{run_label}]")
    print(f"  {'Part':>4}  {'RefSNR':>7}  {'WSJT-X':>8}  {'WSJT%':>6}  {'WX_rep':>7}  {'OW':>8}  {'OW%':>5}  {'OW_rep':>7}")
    for p in parts_s1b:
        t   = true_s1b[p]
        wr  = [r for r in s1b if r["app"]=="WSJT-X"   and r["part"]==p]
        owr = [r for r in s1b if r["app"]=="OpenWSFZ" and r["part"]==p]
        wd  = sum(1 for r in wr  if r["matched"])
        od  = sum(1 for r in owr if r["matched"])
        ws  = [r["rep_snr"] for r in wr  if r["matched"] and r["rep_snr"] is not None]
        os  = [r["rep_snr"] for r in owr if r["matched"] and r["rep_snr"] is not None]
        wm  = f"{sum(ws)/len(ws):+.1f}" if ws else "  —  "
        om  = f"{sum(os)/len(os):+.1f}" if os else "  —  "
        print(f"  {p:>4}  {t:>7.1f}  {wd}/{len(wr)} ({100*wd//len(wr):3.0f}%)  {wm:>7}  {od}/{len(owr)} ({100*od//len(owr):3.0f}%)  {om:>7}")
    w_tot  = sum(1 for r in s1b if r["app"]=="WSJT-X"   and r["matched"])
    ow_tot = sum(1 for r in s1b if r["app"]=="OpenWSFZ" and r["matched"])
    w_all  = sum(1 for r in s1b if r["app"]=="WSJT-X")
    ow_all = sum(1 for r in s1b if r["app"]=="OpenWSFZ")
    print(f"  {'TOTAL':>4}  {'':>7}  {w_tot}/{w_all} ({100*w_tot//w_all:3.0f}%)  {'':>7}  {ow_tot}/{ow_all} ({100*ow_tot//ow_all:3.0f}%)")

# S4/S5 attribute — load raw
print(f"\n{'═'*72}")
print("  S4/S5 — ATTRIBUTE AGREEMENT ANALYSIS")
print(f"{'═'*72}")
s4_rows, s5_rows = [], []
for fname, target in [("S4_matched.csv", s4_rows), ("S5_matched.csv", s5_rows)]:
    with open(FULL_RUN / fname) as f:
        for r in csv.DictReader(f):
            if r.get("false_positive","") == "True":
                continue
            if r.get("part_index","") == "":
                continue
            target.append(r)

for app in ["WSJT-X", "OpenWSFZ"]:
    tp = sum(1 for r in s4_rows if r["appraiser"]==app and r["matched"]=="True")
    fn = sum(1 for r in s4_rows if r["appraiser"]==app and r["matched"]!="True")
    tn = sum(1 for r in s5_rows if r["appraiser"]==app and r.get("false_positive","")!="True")
    print(f"  {app}: TP={tp}  FN={fn}  TN={tn}  Recovery={100*tp/(tp+fn) if tp+fn>0 else 0:.1f}%")

# S7 recovery
print(f"\n{'═'*72}")
print("  S7 — CO-CHANNEL RECOVERY")
print(f"{'═'*72}")
s7_rows = []
with open(FULL_RUN / "S7_matched.csv") as f:
    for r in csv.DictReader(f):
        if r.get("part_index","") == "":
            continue
        s7_rows.append(r)

parts_s7 = sorted(set(int(r["part_index"]) for r in s7_rows if r["part_index"]))
print(f"  {'Part':>4}  {'WSJT-X':>10}  {'OpenWSFZ':>10}")
for p in parts_s7:
    pr  = [r for r in s7_rows if r["part_index"]==str(p)]
    wd  = sum(1 for r in pr if r["appraiser"]=="WSJT-X"   and r["matched"]=="True")
    od  = sum(1 for r in pr if r["appraiser"]=="OpenWSFZ" and r["matched"]=="True")
    wt  = sum(1 for r in pr if r["appraiser"]=="WSJT-X")
    ot  = sum(1 for r in pr if r["appraiser"]=="OpenWSFZ")
    print(f"  {p:>4}  {wd}/{wt} ({100*wd//wt if wt else 0:3.0f}%)  {od}/{ot} ({100*od//ot if ot else 0:3.0f}%)")

# S8 per-station
print(f"\n{'═'*72}")
print("  S8 — BAND SCENE RECOVERY")
print(f"{'═'*72}")
s8_rows = []
with open(FULL_RUN / "S8_matched.csv") as f:
    for r in csv.DictReader(f):
        if r.get("part_index","") == "":
            continue
        s8_rows.append(r)

parts_s8 = sorted(set(int(r["part_index"]) for r in s8_rows if r["part_index"]))
print(f"  {'Part':>4}  {'WSJT-X':>10}  {'OpenWSFZ':>10}  {'Freq':>6}  {'SNR':>5}")
for p in parts_s8:
    pr  = [r for r in s8_rows if r["part_index"]==str(p)]
    wd  = sum(1 for r in pr if r["appraiser"]=="WSJT-X"   and r["matched"]=="True")
    od  = sum(1 for r in pr if r["appraiser"]=="OpenWSFZ" and r["matched"]=="True")
    wt  = sum(1 for r in pr if r["appraiser"]=="WSJT-X")
    ot  = sum(1 for r in pr if r["appraiser"]=="OpenWSFZ")
    freq = pr[0].get("true_freq_hz","?") if pr else "?"
    snr  = pr[0].get("true_snr_db","?")  if pr else "?"
    print(f"  {p:>4}  {wd}/{wt} ({100*wd//wt if wt else 0:3.0f}%)  {od}/{ot} ({100*od//ot if ot else 0:3.0f}%)  {freq:>6}  {snr:>5}")
