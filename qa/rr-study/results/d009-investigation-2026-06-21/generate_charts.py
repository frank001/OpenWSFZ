"""
generate_charts.py — D-009 investigation charts for the consolidated report.

Run from any directory:
    python qa/rr-study/results/d009-investigation-2026-06-21/generate_charts.py

Produces four PNG files in the same directory as this script:
    fig1_investigation_timeline.png
    fig2_trade_curve.png
    fig3_gate_per_part.png
    fig4_ablation_summary.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Colour palette (GitHub dark-mode inspired)
# ---------------------------------------------------------------------------
CLR_BLUE    = "#58a6ff"
CLR_GREEN   = "#3fb950"
CLR_ORANGE  = "#f0883e"
CLR_RED     = "#f85149"
CLR_PURPLE  = "#bc8cff"
CLR_GREY    = "#8b949e"
CLR_BG      = "#0d1117"
CLR_PANEL   = "#161b22"
CLR_BORDER  = "#30363d"
CLR_TEXT    = "#c9d1d9"
CLR_THRESH  = "#d29922"   # amber for threshold lines

def _style(fig, axes):
    fig.patch.set_facecolor(CLR_BG)
    for ax in (axes if hasattr(axes, "__iter__") else [axes]):
        ax.set_facecolor(CLR_PANEL)
        ax.tick_params(colors=CLR_TEXT, labelsize=9)
        ax.xaxis.label.set_color(CLR_TEXT)
        ax.yaxis.label.set_color(CLR_TEXT)
        for spine in ax.spines.values():
            spine.set_edgecolor(CLR_BORDER)
        ax.title.set_color(CLR_TEXT)
        ax.grid(color=CLR_BORDER, linewidth=0.6, linestyle="--")


# ===========================================================================
# Figure 1 — Investigation timeline
# ===========================================================================
def fig1_timeline():
    """Waterfall chart of S7 co_channel_sweep vs investigation round."""
    rounds = [
        ("OSD merge\n(d70aad5 ref)",      92.14, "●"),
        ("Shim 20260028\n(R5 nhard gate)", None,   "◆"),  # not measured
        ("R6 diagnostic\n(nhard/sync diag)", None, "◆"),  # diag only
        ("Pass-1 sweep\n(K sweep P0–P2)",  None,   "◆"),  # sweep measured P0–P2 only
        ("K=10 gate\n(contaminated)",      85.0,  "▲"),
        ("K=10 gate\n(clean)",             86.67, "●"),
        ("Ablation cfg1\n(K=1 gates off)", 80.0,  "●"),
        ("Ablation cfg2\n(K=10 gates off)",44.2,  "●"),
        ("Ablation cfg3\n(K=10 gates on)", 86.67, "●"),
        ("Ablation cfg4\n(K=5 gates off)", 75.0,  "●"),
    ]

    labels  = [r[0] for r in rounds]
    values  = [r[1] for r in rounds]
    markers = [r[2] for r in rounds]

    fig, ax = plt.subplots(figsize=(12, 4.5))
    _style(fig, ax)

    x = list(range(len(rounds)))
    # Plot only measured points
    meas_x = [i for i, v in enumerate(values) if v is not None]
    meas_v = [v for v in values if v is not None]

    ax.plot(meas_x, meas_v, color=CLR_GREY, linewidth=1, linestyle="--", zorder=1)

    colors_map = {
        "●": CLR_BLUE,
        "▲": CLR_ORANGE,
        "◆": CLR_GREY,
    }
    for i, (v, m) in enumerate(zip(values, markers)):
        if v is not None:
            c = CLR_ORANGE if m == "▲" else CLR_BLUE
            ax.scatter(i, v, color=c, s=80, zorder=3)
            ax.annotate(f"{v:.1f}%", (i, v), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=8, color=CLR_TEXT)
        else:
            ax.axvline(i, color=CLR_GREY, linewidth=0.5, linestyle=":", alpha=0.5)

    ax.axhline(89.0, color=CLR_THRESH, linewidth=1.2, linestyle="--", label="89% gate threshold")
    ax.axhline(92.14, color=CLR_GREEN, linewidth=1.0, linestyle="-.", alpha=0.7, label="92.14% reference")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5, rotation=25, ha="right")
    ax.set_ylabel("co_channel_sweep %", fontsize=9)
    ax.set_ylim(30, 100)
    ax.set_title("D-009 Investigation: S7 co_channel_sweep across rounds", fontsize=10, color=CLR_TEXT)
    ax.legend(fontsize=8, framealpha=0.3, labelcolor=CLR_TEXT,
              facecolor=CLR_PANEL, edgecolor=CLR_BORDER)

    fig.tight_layout()
    out = OUT_DIR / "fig1_investigation_timeline.png"
    fig.savefig(out, dpi=140, facecolor=CLR_BG)
    plt.close(fig)
    print(f"Wrote {out}")


# ===========================================================================
# Figure 2 — K sweep trade curve (dual axis)
# ===========================================================================
def fig2_trade_curve():
    K_vals  = [1, 3, 5, 7, 10]
    fp_slot = [0.675, 0.525, 0.533, 0.558, 0.042]
    co_ch   = [28.6,  31.4,  45.7,  42.9,  37.1]

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    _style(fig, ax1)

    ax2 = ax1.twinx()
    ax2.set_facecolor(CLR_PANEL)
    ax2.tick_params(colors=CLR_TEXT, labelsize=9)
    ax2.yaxis.label.set_color(CLR_TEXT)
    for spine in ax2.spines.values():
        spine.set_edgecolor(CLR_BORDER)

    l1, = ax1.plot(K_vals, fp_slot, "o-", color=CLR_RED,   linewidth=2, markersize=7, label="FP/slot (D-009 cost ↓)")
    l2, = ax2.plot(K_vals, co_ch,   "s-", color=CLR_BLUE,  linewidth=2, markersize=7, label="co_channel % P0–P2 (D-001 benefit ↑)")

    ax1.set_xlabel("K_MIN_SCORE_PASS2", fontsize=9)
    ax1.set_ylabel("S5 FP / slot", fontsize=9, color=CLR_RED)
    ax2.set_ylabel("S7 co_channel P0–P2 %", fontsize=9, color=CLR_BLUE)
    ax1.set_ylim(-0.05, 0.85)
    ax2.set_ylim(0, 60)
    ax1.set_xticks(K_vals)

    # Annotate each point
    for k, f, c in zip(K_vals, fp_slot, co_ch):
        ax1.annotate(f"{f:.3f}", (k, f), textcoords="offset points",
                     xytext=(-5, 8), fontsize=7.5, color=CLR_RED)
        ax2.annotate(f"{c:.1f}%", (k, c), textcoords="offset points",
                     xytext=(4, -12), fontsize=7.5, color=CLR_BLUE)

    # Threshold line on FP axis
    ax1.axhline(0.10, color=CLR_THRESH, linewidth=1, linestyle="--", alpha=0.8, label="FP ≤ 0.10 threshold")

    lines = [l1, l2, plt.Line2D([0], [0], color=CLR_THRESH, linestyle="--", label="FP ≤ 0.10 threshold")]
    ax1.legend(handles=lines, fontsize=8, framealpha=0.3, labelcolor=CLR_TEXT,
               facecolor=CLR_PANEL, edgecolor=CLR_BORDER, loc="upper left")

    ax1.set_title("Pass-1 K_MIN_SCORE_PASS2 Trade Curve\n(shim 20260028; gating fixed)", fontsize=10, color=CLR_TEXT)
    fig.tight_layout()
    out = OUT_DIR / "fig2_trade_curve.png"
    fig.savefig(out, dpi=140, facecolor=CLR_BG)
    plt.close(fig)
    print(f"Wrote {out}")


# ===========================================================================
# Figure 3 — K=10 gate: per-part co_channel_sweep breakdown
# ===========================================================================
def fig3_gate_per_part():
    parts      = ["P15\nΔ5 Hz", "P16\nΔ7 Hz", "P17\nΔ10 Hz", "P18\nΔ15 Hz", "P19\nΔ8 Hz", "P20\nΔ9 Hz"]
    ref_pct    = [80.0,  85.0,  100.0, 100.0,  95.0, 100.0]   # d70aad5, K=1, K=10 trials
    k10_pct    = [50.0,  70.0,  100.0, 100.0, 100.0, 100.0]   # shim 20260029, K=10, K=5 trials

    x   = np.arange(len(parts))
    w   = 0.35

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _style(fig, ax)

    bars1 = ax.bar(x - w/2, ref_pct,  w, label="K=1 reference (d70aad5, 20260025)", color=CLR_GREEN,  alpha=0.85)
    bars2 = ax.bar(x + w/2, k10_pct,  w, label="K=10 gate run (shim 20260029)",     color=CLR_ORANGE, alpha=0.85)

    for bar in bars1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 1.5, f"{h:.0f}%",
                ha="center", va="bottom", fontsize=8, color=CLR_TEXT)
    for bar in bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 1.5, f"{h:.0f}%",
                ha="center", va="bottom", fontsize=8, color=CLR_TEXT)

    ax.axhline(89.0, color=CLR_THRESH, linewidth=1.2, linestyle="--", label="89% gate threshold")

    ax.set_xticks(x)
    ax.set_xticklabels(parts, fontsize=8.5)
    ax.set_ylabel("Recovery %", fontsize=9)
    ax.set_ylim(0, 115)
    ax.set_title("co_channel_sweep Per-Part: K=1 ref vs K=10 gate run\n(G-A failure driven by P15 −30pp, P16 −15pp)", fontsize=10, color=CLR_TEXT)
    ax.legend(fontsize=8, framealpha=0.3, labelcolor=CLR_TEXT,
              facecolor=CLR_PANEL, edgecolor=CLR_BORDER)

    fig.tight_layout()
    out = OUT_DIR / "fig3_gate_per_part.png"
    fig.savefig(out, dpi=140, facecolor=CLR_BG)
    plt.close(fig)
    print(f"Wrote {out}")


# ===========================================================================
# Figure 4 — 2×2 ablation summary
# ===========================================================================
def fig4_ablation():
    configs   = ["cfg1\n(K=1\ngates off)", "cfg2\n(K=10\ngates off)", "cfg3\n(K=10\ngates on)", "cfg4\n(K=5\ngates off)"]
    co_ch     = [45.7,  14.3, 34.3, 48.6]   # cfg2: K5-equivalent 14.3%
    sweep     = [80.0,  44.2, 86.7, 75.0]
    fp_norm   = [69.2,   4.2,  4.2, 70.0]   # FP% (0–100) = FP/slot × 100

    thresh_co_ch   = 45.0
    thresh_sweep   = 89.0
    thresh_fp_norm = 10.0   # 0.10/slot → 10%

    x = np.arange(len(configs))
    w = 0.25

    fig, ax = plt.subplots(figsize=(10, 5))
    _style(fig, ax)

    b1 = ax.bar(x - w,     co_ch,   w, label="co_channel P0–P2 %",    color=CLR_BLUE,   alpha=0.85)
    b2 = ax.bar(x,         sweep,   w, label="co_channel_sweep %",    color=CLR_PURPLE, alpha=0.85)
    b3 = ax.bar(x + w,     fp_norm, w, label="S5 FP rate × 100 (lower=better)", color=CLR_RED, alpha=0.85)

    # Threshold markers
    ax.axhline(thresh_co_ch,   color=CLR_BLUE,   linewidth=1.2, linestyle="--", alpha=0.7, label=f"co_ch ≥ {thresh_co_ch}% threshold")
    ax.axhline(thresh_sweep,   color=CLR_PURPLE, linewidth=1.2, linestyle="--", alpha=0.7, label=f"sweep ≥ {thresh_sweep}% threshold")
    ax.axhline(thresh_fp_norm, color=CLR_RED,    linewidth=1.2, linestyle="--", alpha=0.7, label=f"FP ≤ 0.10/slot threshold (×100={thresh_fp_norm})")

    # Value labels
    for bar in list(b1) + list(b2) + list(b3):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.8, f"{h:.1f}",
                ha="center", va="bottom", fontsize=7.5, color=CLR_TEXT)

    ax.set_xticks(x)
    ax.set_xticklabels(configs, fontsize=8.5)
    ax.set_ylabel("Rate / % (FP×100 for legibility)", fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_title("Gate-Isolation Ablation: 4-config 2×2 factorial\n(all configs fail pre-committed criteria → trade irreducible)", fontsize=10, color=CLR_TEXT)
    ax.legend(fontsize=7.5, framealpha=0.3, labelcolor=CLR_TEXT,
              facecolor=CLR_PANEL, edgecolor=CLR_BORDER, ncol=2)

    # Outcome annotation
    outcomes = ["FAIL: FP+sweep", "FAIL: co_ch+sweep", "FAIL: co_ch\n(closest)", "FAIL: FP+sweep"]
    for i, txt in enumerate(outcomes):
        ax.text(i, 2, txt, ha="center", va="bottom", fontsize=6.5, color=CLR_GREY,
                bbox=dict(boxstyle="round,pad=0.15", facecolor=CLR_BG, edgecolor=CLR_BORDER, alpha=0.7))

    fig.tight_layout()
    out = OUT_DIR / "fig4_ablation_summary.png"
    fig.savefig(out, dpi=140, facecolor=CLR_BG)
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    print("Generating D-009 investigation charts...")
    fig1_timeline()
    fig2_trade_curve()
    fig3_gate_per_part()
    fig4_ablation()
    print("Done.")
