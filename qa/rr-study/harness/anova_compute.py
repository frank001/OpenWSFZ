#!/usr/bin/env python3
"""Standalone ANOVA computation for the Gauge R&R report.

Reads S1_matched.csv and S1b_matched.csv from the run directory supplied as
the first argument and prints all statistics needed for a Minitab-style report.
"""
import csv
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/2026-06-09-d509b08")

# ── Load S1 matched rows (true-positive matched only) ──────────────────────
rows = []
with open(run_dir / "S1_matched.csv") as f:
    for r in csv.DictReader(f):
        if r["false_positive"] == "True":
            continue
        if r["matched"] != "True":
            continue
        rows.append({
            "appraiser": r["appraiser"],
            "part":      int(r["part_index"]),
            "trial":     int(r["trial_index"]),
            "true_snr":  float(r["true_snr_db"]),
            "reported":  float(r["reported_snr_db"]),
        })

appraisers = sorted(set(r["appraiser"] for r in rows))
parts      = sorted(set(r["part"]      for r in rows))
a, b, n    = len(appraisers), len(parts), 3
N          = a * b * n

assert a == 2 and b == 10 and n == 3, f"Unexpected study dimensions: a={a} b={b}"

# Build Y[appraiser][part] = [rep0, rep1, rep2]
true_snrs = {}
Y = {app: {} for app in appraisers}
for r in rows:
    true_snrs[r["part"]] = r["true_snr"]
    Y[r["appraiser"]].setdefault(r["part"], []).append(r["reported"])

# ── Grand, operator, part, and cell means ──────────────────────────────────
all_vals   = [Y[app][p][t] for app in appraisers for p in parts for t in range(n)]
grand_mean = sum(all_vals) / N

cell_mean = {(app, p): sum(Y[app][p]) / n
             for app in appraisers for p in parts}
op_mean   = {app: sum(Y[app][p][t] for p in parts for t in range(n)) / (b * n)
             for app in appraisers}
part_mean = {p: sum(Y[app][p][t] for app in appraisers for t in range(n)) / (a * n)
             for p in parts}

# ── Sums of squares ────────────────────────────────────────────────────────
SS_part     = a * n * sum((part_mean[p] - grand_mean) ** 2 for p in parts)
SS_op       = b * n * sum((op_mean[app] - grand_mean) ** 2 for app in appraisers)
SS_inter    = n * sum(
    (cell_mean[(app, p)] - op_mean[app] - part_mean[p] + grand_mean) ** 2
    for app in appraisers for p in parts
)
SS_error    = sum(
    (Y[app][p][t] - cell_mean[(app, p)]) ** 2
    for app in appraisers for p in parts for t in range(n)
)
SS_total    = sum((v - grand_mean) ** 2 for v in all_vals)

# ── Degrees of freedom and mean squares ───────────────────────────────────
df_part, df_op, df_inter, df_error, df_total = b-1, a-1, (a-1)*(b-1), a*b*(n-1), N-1
MS_part  = SS_part  / df_part
MS_op    = SS_op    / df_op
MS_inter = SS_inter / df_inter
MS_error = SS_error / df_error

# ── F statistics and p-values ─────────────────────────────────────────────
from scipy.stats import f as fdist
F_part  = MS_part  / MS_inter
F_op    = MS_op    / MS_inter
F_inter = MS_inter / MS_error
P_part  = 1 - fdist.cdf(F_part,  df_part,  df_inter)
P_op    = 1 - fdist.cdf(F_op,    df_op,    df_inter)
P_inter = 1 - fdist.cdf(F_inter, df_inter, df_error)

# ── Variance components (AIAG / Minitab method) ───────────────────────────
var_repeat    = MS_error
var_op_x_part = max(0.0, (MS_inter - MS_error) / n)
var_operator  = max(0.0, (MS_op - MS_inter) / (b * n))
var_reprod    = var_operator + var_op_x_part
var_grr       = var_repeat + var_reprod
var_part      = max(0.0, (MS_part - MS_inter) / (a * n))
var_total     = var_grr + var_part

# Tolerance: ±2.0 dB → 4.0 dB total range
tolerance = 4.0

def sv(v):
    return 6 * math.sqrt(max(0.0, v))

def pct_sv(v):
    return 100 * sv(v) / sv(var_total)

def pct_tol(v):
    return 100 * sv(v) / tolerance

ndc = max(1, int(1.41 * math.sqrt(var_part / var_grr)))

# ── Bias / linearity per appraiser ────────────────────────────────────────
from scipy.stats import t as tdist
bias_stats = {}
for app in appraisers:
    xs = [true_snrs[p] for p in parts]
    obs_means = [sum(Y[app][p]) / n for p in parts]
    biases = [obs - ref for obs, ref in zip(obs_means, xs)]
    n_ = len(xs)
    x_bar = sum(xs) / n_
    y_bar = sum(biases) / n_
    Sxx = sum((x - x_bar) ** 2 for x in xs)
    Sxy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, biases))
    slope = Sxy / Sxx
    intercept = y_bar - slope * x_bar
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, biases))
    ss_tot = sum((y - y_bar) ** 2 for y in biases)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    # t-test for overall mean bias
    se = math.sqrt(sum((y - y_bar) ** 2 for y in biases) / (n_ - 1)) / math.sqrt(n_)
    t_stat = y_bar / se if se > 0 else float("inf")
    p_bias = 2 * (1 - tdist.cdf(abs(t_stat), n_ - 1))
    bias_stats[app] = {
        "part_biases": list(zip(xs, obs_means, biases)),
        "mean_bias":   y_bar,
        "slope":       slope,
        "intercept":   intercept,
        "r2":          r2,
        "p_bias":      p_bias,
        "se":          se,
    }

# ── S1b data ──────────────────────────────────────────────────────────────
s1b_rows = []
with open(run_dir / "S1b_matched.csv") as f:
    for r in csv.DictReader(f):
        if r["false_positive"] == "True":
            continue
        if r["part_index"] == "":
            continue
        s1b_rows.append({
            "appraiser": r["appraiser"],
            "part":      int(r["part_index"]),
            "true_snr":  float(r["true_snr_db"]),
            "matched":   r["matched"] == "True",
            "reported":  float(r["reported_snr_db"]) if r["reported_snr_db"] else None,
        })

s1b_parts    = sorted(set(r["part"] for r in s1b_rows))
s1b_true_snr = {r["part"]: r["true_snr"] for r in s1b_rows}

# ═══════════════════════════════════════════════════════════════════════════
# PRINT SECTION — formatted for transcription into the report
# ═══════════════════════════════════════════════════════════════════════════
SEP = "=" * 70

print(SEP)
print("MEASUREMENT MATRIX  (reported_snr_db)")
print(SEP)
print(f"{'Part':>4}  {'Ref SNR':>7}  {'WSJT-X (r1,r2,r3)':>22}  {'OpenWSFZ (r1,r2,r3)':>24}")
for p in parts:
    w = Y["WSJT-X"][p]
    o = Y["OpenWSFZ"][p]
    print(f"{p:>4}  {true_snrs[p]:>7.1f}  {str(w):>22}  {str(o):>24}")

print()
print(SEP)
print("TWO-WAY ANOVA TABLE WITH INTERACTION")
print(SEP)
hdr = f"{'Source':<22}  {'DF':>4}  {'SS':>10}  {'MS':>10}  {'F':>8}  {'P':>8}"
print(hdr)
print("-" * len(hdr))
print(f"{'Part':<22}  {df_part:>4}  {SS_part:>10.4f}  {MS_part:>10.4f}  {F_part:>8.3f}  {P_part:>8.4f}")
print(f"{'Appraiser':<22}  {df_op:>4}  {SS_op:>10.4f}  {MS_op:>10.4f}  {F_op:>8.3f}  {P_op:>8.4f}")
print(f"{'Appraiser×Part':<22}  {df_inter:>4}  {SS_inter:>10.4f}  {MS_inter:>10.4f}  {F_inter:>8.3f}  {P_inter:>8.4f}")
print(f"{'Repeatability':<22}  {df_error:>4}  {SS_error:>10.4f}  {MS_error:>10.4f}")
print(f"{'Total':<22}  {df_total:>4}  {SS_total:>10.4f}")

print()
print(SEP)
print("VARIANCE COMPONENTS")
print(SEP)
vc_hdr = f"{'Source':<30}  {'VarComp':>9}  {'%Contribution':>13}"
print(vc_hdr)
print("-" * len(vc_hdr))
print(f"{'Total Gauge R&R':<30}  {var_grr:>9.5f}  {100*var_grr/var_total:>12.2f}%")
print(f"{'  Repeatability':<30}  {var_repeat:>9.5f}  {100*var_repeat/var_total:>12.2f}%")
print(f"{'  Reproducibility':<30}  {var_reprod:>9.5f}  {100*var_reprod/var_total:>12.2f}%")
print(f"{'    Appraiser':<30}  {var_operator:>9.5f}  {100*var_operator/var_total:>12.2f}%")
print(f"{'    Appraiser×Part':<30}  {var_op_x_part:>9.5f}  {100*var_op_x_part/var_total:>12.2f}%")
print(f"{'Part-To-Part':<30}  {var_part:>9.5f}  {100*var_part/var_total:>12.2f}%")
print(f"{'Total Variation':<30}  {var_total:>9.5f}  {'100.00%':>13}")

print()
print(SEP)
print(f"STUDY VARIATION  (tolerance = ±2.0 dB → 4.0 dB range)")
print(SEP)
sv_hdr = f"{'Source':<30}  {'StdDev':>8}  {'StudyVar':>9}  {'%StudyVar':>10}  {'%Tolerance':>11}"
print(sv_hdr)
print("-" * len(sv_hdr))
print(f"{'Total Gauge R&R':<30}  {math.sqrt(var_grr):>8.4f}  {sv(var_grr):>9.4f}  {pct_sv(var_grr):>9.2f}%  {pct_tol(var_grr):>10.2f}%")
print(f"{'  Repeatability':<30}  {math.sqrt(var_repeat):>8.4f}  {sv(var_repeat):>9.4f}  {pct_sv(var_repeat):>9.2f}%  {pct_tol(var_repeat):>10.2f}%")
print(f"{'  Reproducibility':<30}  {math.sqrt(var_reprod):>8.4f}  {sv(var_reprod):>9.4f}  {pct_sv(var_reprod):>9.2f}%  {pct_tol(var_reprod):>10.2f}%")
print(f"{'    Appraiser':<30}  {math.sqrt(var_operator):>8.4f}  {sv(var_operator):>9.4f}  {pct_sv(var_operator):>9.2f}%  {pct_tol(var_operator):>10.2f}%")
print(f"{'    Appraiser×Part':<30}  {math.sqrt(var_op_x_part):>8.4f}  {sv(var_op_x_part):>9.4f}  {pct_sv(var_op_x_part):>9.2f}%  {pct_tol(var_op_x_part):>10.2f}%")
print(f"{'Part-To-Part':<30}  {math.sqrt(var_part):>8.4f}  {sv(var_part):>9.4f}  {pct_sv(var_part):>9.2f}%  {pct_tol(var_part):>10.2f}%")
print(f"{'Total Variation':<30}  {math.sqrt(var_total):>8.4f}  {sv(var_total):>9.4f}  {'100.00%':>10}  {pct_tol(var_total):>10.2f}%")
print(f"\nNumber of Distinct Categories = {ndc}")

print()
print(SEP)
print("BIAS AND LINEARITY")
print(SEP)
print(f"{'Part':>4}  {'Ref SNR':>7}  {'WSJT-X mean':>12}  {'WSJT-X bias':>12}  {'OW mean':>9}  {'OW bias':>9}")
for p in parts:
    t  = true_snrs[p]
    w  = sum(Y["WSJT-X"][p]) / n
    ow = sum(Y["OpenWSFZ"][p]) / n
    print(f"{p:>4}  {t:>7.1f}  {w:>12.2f}  {w-t:>+12.2f}  {ow:>9.2f}  {ow-t:>+9.2f}")

for app in appraisers:
    s = bias_stats[app]
    print(f"\n{app}")
    print(f"  Regression:  bias = {s['slope']:+.4f}×(ref_SNR) + {s['intercept']:+.4f}")
    print(f"  R² = {s['r2']:.4f}   Mean bias = {s['mean_bias']:+.4f} dB   SE = {s['se']:.4f}   p(bias=0) = {s['p_bias']:.5f}")
    verdict = "FAIL (|bias| > 2.0 dB)" if abs(s['mean_bias']) > 2.0 else "PASS"
    print(f"  Bias verdict: {verdict}")

print()
print(SEP)
print("S1b — SENSITIVITY THRESHOLD  (informational, no AIAG threshold)")
print(SEP)
print(f"{'Part':>4}  {'Ref SNR':>7}  {'WSJT dec':>9}  {'WSJT%':>7}  {'WSJT rep SNR':>13}  {'OW dec':>7}  {'OW%':>5}  {'OW rep SNR':>11}")
for p in s1b_parts:
    t   = s1b_true_snr[p]
    wr  = [r for r in s1b_rows if r["appraiser"]=="WSJT-X"   and r["part"]==p]
    owr = [r for r in s1b_rows if r["appraiser"]=="OpenWSFZ" and r["part"]==p]
    wd  = sum(1 for r in wr  if r["matched"])
    od  = sum(1 for r in owr if r["matched"])
    ws  = [r["reported"] for r in wr  if r["matched"] and r["reported"] is not None]
    os  = [r["reported"] for r in owr if r["matched"] and r["reported"] is not None]
    wmean = f"{sum(ws)/len(ws):+.1f}" if ws else "—"
    omean = f"{sum(os)/len(os):+.1f}" if os else "—"
    print(f"{p:>4}  {t:>7.1f}  {wd}/{len(wr)} ({100*wd//len(wr):3.0f}%)  {wmean:>13}  {od}/{len(owr)} ({100*od//len(owr):3.0f}%)  {omean:>11}")
