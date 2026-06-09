#!/usr/bin/env python3
"""Compute all GR&R statistics with correct tolerances and S3 DT correction."""
import csv, math, sys, os
from scipy.stats import f as fdist, t as tdist
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_FULL = os.path.join(HERE, "results", "2026-06-07-4b3a4ca")
BASE_NEW  = os.path.join(HERE, "results", "2026-06-09-d509b08")

# Tolerances per STUDY-SPEC §10 / analyse.py TOLERANCE_HALF
TOLS = {"S1": 5.0, "S2": 4.0, "S3": 0.2}


def load_matched(path, measure_col, dt_corr_wsjt=0.0):
    ref_map = {
        "reported_snr_db":  "true_snr_db",
        "reported_freq_hz": "true_freq_hz",
        "reported_dt_s":    "true_dt_s",
    }
    ref_col = ref_map[measure_col]
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["false_positive"] == "True":
                continue
            if r["matched"] != "True":
                continue
            if r["part_index"] == "":
                continue
            if not r[measure_col] or not r[ref_col]:
                continue
            m = float(r[measure_col])
            if measure_col == "reported_dt_s" and r["appraiser"] == "WSJT-X":
                m += dt_corr_wsjt
            rows.append({
                "appraiser": r["appraiser"],
                "part":      int(r["part_index"]),
                "trial":     int(r["trial_index"]),
                "reference": float(r[ref_col]),
                "measured":  m,
            })
    return rows


def grr_anova(rows, tol_half):
    tol = 2.0 * tol_half
    appraisers = sorted(set(r["appraiser"] for r in rows))
    parts      = sorted(set(r["part"]      for r in rows))
    a, b       = len(appraisers), len(parts)

    Y   = {app: {} for app in appraisers}
    ref = {}
    for r in rows:
        Y[r["appraiser"]].setdefault(r["part"], []).append(r["measured"])
        ref[r["part"]] = r["reference"]

    n = len(Y[appraisers[0]][parts[0]])
    N = a * b * n

    all_v = [Y[app][p][t] for app in appraisers for p in parts for t in range(n)]
    gm    = sum(all_v) / N
    cm    = {(app, p): sum(Y[app][p]) / n  for app in appraisers for p in parts}
    om    = {app: sum(Y[app][p][t] for p in parts for t in range(n)) / (b * n) for app in appraisers}
    pm    = {p:   sum(Y[app][p][t] for app in appraisers for t in range(n)) / (a * n) for p in parts}

    SS_p = a * n * sum((pm[p]  - gm) ** 2 for p in parts)
    SS_o = b * n * sum((om[ap] - gm) ** 2 for ap in appraisers)
    SS_i = n * sum((cm[(ap, p)] - om[ap] - pm[p] + gm) ** 2 for ap in appraisers for p in parts)
    SS_e = sum((Y[ap][p][t] - cm[(ap, p)]) ** 2 for ap in appraisers for p in parts for t in range(n))
    SS_t = sum((v - gm) ** 2 for v in all_v)

    df_p, df_o, df_i = b - 1, a - 1, (a - 1) * (b - 1)
    df_e, df_t       = a * b * (n - 1), N - 1

    MS_p, MS_o = SS_p / df_p, SS_o / df_o
    MS_i, MS_e = SS_i / df_i, SS_e / df_e

    F_p  = MS_p / MS_i
    F_o  = MS_o / MS_i
    F_i  = MS_i / MS_e
    P_p  = 1 - fdist.cdf(F_p, df_p, df_i)
    P_o  = 1 - fdist.cdf(F_o, df_o, df_i)
    P_i  = 1 - fdist.cdf(F_i, df_i, df_e)

    vr   = MS_e
    vox  = max(0.0, (MS_i - MS_e)  / n)
    vo   = max(0.0, (MS_o - MS_i)  / (b * n))
    vrp  = vo + vox
    vg   = vr + vrp
    vpa  = max(0.0, (MS_p - MS_i)  / (a * n))
    vt   = vg + vpa

    def sv(v):   return 6.0 * math.sqrt(max(0.0, v))
    def pct(v):  return 100.0 * sv(v) / sv(vt) if vt > 0 else 0.0
    def ptol(v): return 100.0 * sv(v) / tol    if tol > 0 else 0.0

    ndc = max(1, int(1.41 * math.sqrt(vpa / vg))) if vg > 0 else 1

    bias = {}
    for ap in appraisers:
        xs  = [ref[p]           for p in parts]
        obs = [sum(Y[ap][p]) / n for p in parts]
        bs  = [o - x for o, x in zip(obs, xs)]
        nb  = len(xs)
        xb, yb = sum(xs) / nb, sum(bs) / nb
        Sxx = sum((x - xb) ** 2 for x in xs)
        Sxy = sum((x - xb) * (y - yb) for x, y in zip(xs, bs))
        sl  = Sxy / Sxx if Sxx else 0.0
        ic  = yb - sl * xb
        ss_r = sum((y - (sl * x + ic)) ** 2 for x, y in zip(xs, bs))
        ss_t2 = sum((y - yb) ** 2 for y in bs)
        r2   = 1.0 - ss_r / ss_t2 if ss_t2 > 0 else 0.0
        se   = math.sqrt(sum((y - yb) ** 2 for y in bs) / (nb - 1)) / math.sqrt(nb) if nb > 1 else 0.0
        ts   = yb / se if se > 0 else float("inf")
        pb   = 2.0 * (1.0 - tdist.cdf(abs(ts), nb - 1))
        bias[ap] = {
            "parts":     list(zip(xs, obs, bs)),
            "mean_bias": yb,
            "slope":     sl,
            "intercept": ic,
            "r2":        r2,
            "p_bias":    pb,
        }

    def verdict_grr():
        pct_contrib = 100.0 * vg / vt if vt > 0 else 0.0
        if pct_contrib < 10.0:  return "PASS"
        if pct_contrib < 30.0:  return "MARGINAL"
        return "FAIL"

    def verdict_ndc():
        if ndc >= 5: return "PASS"
        if ndc >= 2: return "MARGINAL"
        return "FAIL"

    return dict(
        appraisers=appraisers, parts=parts, a=a, b=b, n=n, N=N, Y=Y, ref=ref,
        SS_p=SS_p, SS_o=SS_o, SS_i=SS_i, SS_e=SS_e, SS_t=SS_t,
        df_p=df_p, df_o=df_o, df_i=df_i, df_e=df_e, df_t=df_t,
        MS_p=MS_p, MS_o=MS_o, MS_i=MS_i, MS_e=MS_e,
        F_p=F_p, F_o=F_o, F_i=F_i, P_p=P_p, P_o=P_o, P_i=P_i,
        vr=vr, vox=vox, vo=vo, vrp=vrp, vg=vg, vpa=vpa, vt=vt,
        sv=sv, pct=pct, ptol=ptol, tol=tol, tol_half=tol_half,
        ndc=ndc, verdict_grr=verdict_grr, verdict_ndc=verdict_ndc, bias=bias,
    )


def fp_str(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def print_grr(label, g):
    print(f"\n{'='*72}")
    print(f"  {label}")
    print(f"  Tolerance: ±{g['tol_half']}  (full range = {g['tol']})")
    print(f"{'='*72}")
    print(f"\n  ANOVA TABLE (two-way, crossed, with interaction)")
    print(f"  {'Source':<22}  {'DF':>4}  {'SS':>12}  {'MS':>12}  {'F':>9}  {'P':>8}")
    print(f"  {'-'*68}")
    print(f"  {'Part':<22}  {g['df_p']:>4}  {g['SS_p']:>12.4f}  {g['MS_p']:>12.4f}  {g['F_p']:>9.3f}  {fp_str(g['P_p']):>8}")
    print(f"  {'Appraiser':<22}  {g['df_o']:>4}  {g['SS_o']:>12.4f}  {g['MS_o']:>12.4f}  {g['F_o']:>9.3f}  {fp_str(g['P_o']):>8}")
    ni = "  [NS]" if g['P_i'] > 0.05 else ""
    print(f"  {'Appraiser×Part':<22}  {g['df_i']:>4}  {g['SS_i']:>12.4f}  {g['MS_i']:>12.4f}  {g['F_i']:>9.3f}  {fp_str(g['P_i']):>8}{ni}")
    print(f"  {'Repeatability':<22}  {g['df_e']:>4}  {g['SS_e']:>12.4f}  {g['MS_e']:>12.4f}")
    print(f"  {'Total':<22}  {g['df_t']:>4}  {g['SS_t']:>12.4f}")

    vt = g['vt']
    print(f"\n  VARIANCE COMPONENTS")
    print(f"  {'Source':<30}  {'VarComp':>10}  {'%Contrib':>9}  Verdict")
    print(f"  {'-'*60}")
    print(f"  {'Total Gauge R&R':<30}  {g['vg']:>10.5f}  {100*g['vg']/vt:>8.2f}%  {g['verdict_grr']()}")
    print(f"  {'  Repeatability':<30}  {g['vr']:>10.5f}  {100*g['vr']/vt:>8.2f}%")
    print(f"  {'  Reproducibility':<30}  {g['vrp']:>10.5f}  {100*g['vrp']/vt:>8.2f}%")
    print(f"  {'    Appraiser':<30}  {g['vo']:>10.5f}  {100*g['vo']/vt:>8.2f}%")
    print(f"  {'    Appraiser×Part':<30}  {g['vox']:>10.5f}  {100*g['vox']/vt:>8.2f}%")
    print(f"  {'Part-To-Part':<30}  {g['vpa']:>10.5f}  {100*g['vpa']/vt:>8.2f}%")
    print(f"  {'Total Variation':<30}  {vt:>10.5f}  {'100.00%':>9}")

    sv, pct, ptol = g['sv'], g['pct'], g['ptol']
    print(f"\n  STUDY VARIATION (6σ)   Tolerance = {g['tol']}")
    print(f"  {'Source':<30}  {'StdDev':>9}  {'6×SD':>9}  {'%SV':>8}  {'%Tol':>9}  Verdict")
    print(f"  {'-'*78}")
    print(f"  {'Total Gauge R&R':<30}  {math.sqrt(g['vg']):>9.4f}  {sv(g['vg']):>9.4f}  {pct(g['vg']):>7.2f}%  {ptol(g['vg']):>8.2f}%  {g['verdict_grr']()}")
    print(f"  {'  Repeatability':<30}  {math.sqrt(g['vr']):>9.4f}  {sv(g['vr']):>9.4f}  {pct(g['vr']):>7.2f}%  {ptol(g['vr']):>8.2f}%")
    print(f"  {'  Reproducibility':<30}  {math.sqrt(g['vrp']):>9.4f}  {sv(g['vrp']):>9.4f}  {pct(g['vrp']):>7.2f}%  {ptol(g['vrp']):>8.2f}%")
    print(f"  {'    Appraiser':<30}  {math.sqrt(g['vo']):>9.4f}  {sv(g['vo']):>9.4f}  {pct(g['vo']):>7.2f}%  {ptol(g['vo']):>8.2f}%")
    print(f"  {'    Appraiser×Part':<30}  {math.sqrt(g['vox']):>9.4f}  {sv(g['vox']):>9.4f}  {pct(g['vox']):>7.2f}%  {ptol(g['vox']):>8.2f}%")
    print(f"  {'Part-To-Part':<30}  {math.sqrt(g['vpa']):>9.4f}  {sv(g['vpa']):>9.4f}  {pct(g['vpa']):>7.2f}%  {ptol(g['vpa']):>8.2f}%")
    print(f"  {'Total Variation':<30}  {math.sqrt(vt):>9.4f}  {sv(vt):>9.4f}  {'100.00%':>8}  {ptol(vt):>8.2f}%")
    print(f"\n  ndc = {g['ndc']}  [{g['verdict_ndc']()}]")

    print(f"\n  BIAS BY APPRAISER")
    print(f"  {'Appraiser':<14}  {'Mean Bias':>10}  {'Slope':>8}  {'Intercept':>10}  {'R²':>6}  {'p(b=0)':>8}")
    print(f"  {'-'*64}")
    for ap in g['appraisers']:
        b = g['bias'][ap]
        print(f"  {ap:<14}  {b['mean_bias']:>+10.4f}  {b['slope']:>+8.5f}  {b['intercept']:>+10.4f}  {b['r2']:>6.4f}  {fp_str(b['p_bias']):>8}")


# ── Run all computations ──────────────────────────────────────────────────────
g_s1o = grr_anova(load_matched(os.path.join(BASE_FULL, "S1_matched.csv"), "reported_snr_db"), 5.0)
g_s1n = grr_anova(load_matched(os.path.join(BASE_NEW,  "S1_matched.csv"), "reported_snr_db"), 5.0)
g_s2  = grr_anova(load_matched(os.path.join(BASE_FULL, "S2_matched.csv"), "reported_freq_hz"), 4.0)
g_s3  = grr_anova(load_matched(os.path.join(BASE_FULL, "S3_matched.csv"), "reported_dt_s", dt_corr_wsjt=0.55), 0.2)

print_grr("S1 — SNR [run 4b3a4ca | wideband AWGN — SUPERSEDED]", g_s1o)
print_grr("S1 — SNR [run d509b08 | bandlimited 3 kHz — CURRENT]", g_s1n)
print_grr("S2 — Frequency [run 4b3a4ca]", g_s2)
print_grr("S3 — DT  [run 4b3a4ca | +0.55s WSJT-X correction applied]", g_s3)

# Bias delta table
print(f"\n{'='*72}")
print("  S1 BIAS DELTA  wideband (4b3a4ca) → bandlimited 3 kHz (d509b08)")
print(f"  {'Part':>4}  {'Ref dB':>7}  {'WX-wb':>7}  {'OW-wb':>7}  {'WX-bl':>7}  {'OW-bl':>7}  {'ΔWX':>6}  {'ΔOW':>6}")
print(f"  {'-'*60}")
for i, p in enumerate(g_s1o['parts']):
    r   = g_s1o['ref'][p]
    wxo = g_s1o['bias']['WSJT-X']['parts'][i][2]
    owo = g_s1o['bias']['OpenWSFZ']['parts'][i][2]
    wxn = g_s1n['bias']['WSJT-X']['parts'][i][2]
    own = g_s1n['bias']['OpenWSFZ']['parts'][i][2]
    print(f"  {p:>4}  {r:>7.1f}  {wxo:>+7.2f}  {owo:>+7.2f}  {wxn:>+7.2f}  {own:>+7.2f}  {wxn-wxo:>+6.2f}  {own-owo:>+6.2f}")
mx = g_s1n['bias']['WSJT-X']['mean_bias']  - g_s1o['bias']['WSJT-X']['mean_bias']
mo = g_s1n['bias']['OpenWSFZ']['mean_bias']- g_s1o['bias']['OpenWSFZ']['mean_bias']
print(f"  {'Mean':>4}  {'':>7}  {g_s1o['bias']['WSJT-X']['mean_bias']:>+7.2f}  {g_s1o['bias']['OpenWSFZ']['mean_bias']:>+7.2f}  {g_s1n['bias']['WSJT-X']['mean_bias']:>+7.2f}  {g_s1n['bias']['OpenWSFZ']['mean_bias']:>+7.2f}  {mx:>+6.2f}  {mo:>+6.2f}")

# S3 per-part bias table
print(f"\n{'='*72}")
print("  S3 DT — BIAS PER PART (WSJT-X +0.55s corrected)")
print(f"  {'Part':>4}  {'Ref(s)':>7}  {'WSJT-X':>9}  {'Bias':>7}  {'OpenWSFZ':>10}  {'Bias':>7}")
print(f"  {'-'*54}")
for i, p in enumerate(g_s3['parts']):
    r   = g_s3['ref'][p]
    wxb = g_s3['bias']['WSJT-X']['parts'][i]
    owb = g_s3['bias']['OpenWSFZ']['parts'][i]
    print(f"  {p:>4}  {r:>7.2f}  {wxb[1]:>9.3f}  {wxb[2]:>+7.3f}  {owb[1]:>10.3f}  {owb[2]:>+7.3f}")
print(f"  Mean biases: WSJT-X={g_s3['bias']['WSJT-X']['mean_bias']:+.4f}s  OpenWSFZ={g_s3['bias']['OpenWSFZ']['mean_bias']:+.4f}s")

print("\nDONE")
