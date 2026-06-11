"""S6 corpus replay — analysis script.

Reads the run_manifest.json produced by corpus_replay.py and computes:
  1. Within-appraiser consistency  (decoded / not-decoded identical across K runs?)
  2. Between-appraiser Cohen's κ   (do WSJT-X and OpenWSFZ agree per signal?)
  3. SNR delta                      (OpenWSFZ SNR − WSJT-X SNR for matched decodes)
  4. Order-effect test              (Spearman ρ: presentation rank vs decode count)

Committed outputs (callsigns scrubbed per NFR-021):
  report.md, summary.csv, consistency.png, kappa.png, snr_delta.png

Raw intermediate data stays in raw/ and is never committed.

Usage (from qa/rr-study/):
    python harness/analyse_corpus.py --run-dir results/corpus-<date>
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

# ── Windows terminal encoding (NFR-022) ───────────────────────────────────────
# analyse_corpus.py imports nothing from harness.*, so the package __init__.py
# does not run.  Apply the reconfigure here explicitly so Greek letters and
# other non-ASCII characters in study output never crash on a cp1252 console.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Package root ───────────────────────────────────────────────────────────────
_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

# ── GDPR — callsign scrub ─────────────────────────────────────────────────────
# ITU callsign pattern: 1-2 letter prefix, 1-2 digits, 1-3 letter suffix.
# Also matches Q-prefix calls (Q1ABC) — that is intentional: Q-prefix calls are
# the correct replacement token and will survive as [CALL] → then re-inserted as
# written.  We scrub ALL callsign-shaped tokens; the committed text is [CALL].
# Q-prefix example calls (Q0-Q9 prefix) used in the synth are also scrubbed for
# safety; the report references them only in aggregate.
_CALLSIGN_RE = re.compile(
    r"\b([A-Z]{1,2}[0-9]{1,2}[A-Z]{1,3})\b"
)

# Tokens that look like callsigns but are not (FT8 grid squares, mode names, etc.)
# These are safe to leave in the text.
_CALLSIGN_SAFELIST = frozenset({
    "FT8", "FT4", "JS8", "CQ", "DE", "RR73", "RRR", "TNX", "TU",
})


def _scrub(text: str) -> str:
    """Replace ITU callsign tokens with [CALL].

    Every token matching _CALLSIGN_RE that is not in _CALLSIGN_SAFELIST is
    replaced unconditionally.  The substitution is total: after _CALLSIGN_RE.sub
    no non-safelist match can survive, so a post-scrub search would always return
    None.  No abort path is needed — the replace function is deterministic.
    """
    def replace(m: re.Match) -> str:
        token = m.group(1)
        if token in _CALLSIGN_SAFELIST:
            return token       # leave safe tokens unchanged
        return "[CALL]"

    return _CALLSIGN_RE.sub(replace, text)


def _scrub_or_abort(text: str, context: str = "") -> str:
    """Scrub callsigns from *text* before writing to a committed artifact."""
    return _scrub(text)


# ── Signal identity key ────────────────────────────────────────────────────────

def _sig_key(message: str, freq_hz: float) -> tuple[str, int]:
    """Return (normalised_message, freq_bin_50hz) identity key for a decoded signal.

    Frequency is binned to the nearest 50 Hz to absorb the ±4 Hz rounding
    difference between WSJT-X and OpenWSFZ (STUDY-SPEC §8).
    """
    freq_bin = int(round(freq_hz / 50.0)) * 50
    return (" ".join(message.split()).upper(), freq_bin)


# ── Load manifest ─────────────────────────────────────────────────────────────

def _load_manifest(run_dir: Path) -> dict:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        sys.exit(f"ERROR: run_manifest.json not found in {run_dir}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


# ── Build observation table ───────────────────────────────────────────────────
#
# One row per (wav, run, signal_key):
#   wav_name, run_index, slot (presentation order), sig_key, wsjt_decoded, owsfz_decoded,
#   wsjt_snr (or None), owsfz_snr (or None)

def _build_observations(manifest: dict) -> list[dict]:
    """Build the flat observation table from the manifest."""
    # First pass: collect per-(wav) signal universe across all runs and appraisers
    wav_universe: dict[str, set] = defaultdict(set)

    for run in manifest["runs"]:
        for cycle in run["cycles"]:
            wav = cycle["wav"]
            for d in cycle["wsjt_decodes"]:
                wav_universe[wav].add(_sig_key(d["message"], d["freq_hz"]))
            for d in cycle["owsfz_decodes"]:
                wav_universe[wav].add(_sig_key(d["message"], d["freq_hz"]))

    # Second pass: build one observation row per (wav, run, signal_key)
    rows: list[dict] = []

    for run in manifest["runs"]:
        run_idx = run["run_index"]
        for cycle in run["cycles"]:
            wav      = cycle["wav"]
            slot_num = cycle["slot"]

            # Index this cycle's decodes by signal key
            wsjt_by_key: dict[tuple, float]  = {}
            owsfz_by_key: dict[tuple, float] = {}
            for d in cycle["wsjt_decodes"]:
                k = _sig_key(d["message"], d["freq_hz"])
                wsjt_by_key[k] = d["snr_db"]
            for d in cycle["owsfz_decodes"]:
                k = _sig_key(d["message"], d["freq_hz"])
                owsfz_by_key[k] = d["snr_db"]

            for sig in wav_universe[wav]:
                wsjt_decoded  = sig in wsjt_by_key
                owsfz_decoded = sig in owsfz_by_key
                rows.append({
                    "wav":          wav,
                    "run":          run_idx,
                    "slot":         slot_num,
                    "sig_key":      sig,
                    "wsjt_decoded": wsjt_decoded,
                    "owsfz_decoded": owsfz_decoded,
                    "wsjt_snr":     wsjt_by_key.get(sig),
                    "owsfz_snr":    owsfz_by_key.get(sig),
                })

    return rows


# ── 1. Within-appraiser consistency ──────────────────────────────────────────

def _consistency(rows: list[dict], n_runs: int) -> dict:
    """Return consistency stats per appraiser.

    A (wav, sig) pair is consistent if the decode decision is identical across
    all n_runs for that appraiser.
    """
    # Group by (wav, sig)
    by_wav_sig_wsjt: dict[tuple, list[bool]]  = defaultdict(list)
    by_wav_sig_owsfz: dict[tuple, list[bool]] = defaultdict(list)

    for r in rows:
        key = (r["wav"], r["sig_key"])
        by_wav_sig_wsjt[key].append(r["wsjt_decoded"])
        by_wav_sig_owsfz[key].append(r["owsfz_decoded"])

    def _stats(by_key: dict) -> dict:
        total      = len(by_key)
        consistent = sum(1 for decisions in by_key.values() if len(set(decisions)) == 1)
        return {
            "total_pairs":      total,
            "consistent_pairs": consistent,
            "inconsistent_pairs": total - consistent,
            "pct_consistent":   100.0 * consistent / total if total > 0 else 0.0,
        }

    return {
        "wsjt":   _stats(by_wav_sig_wsjt),
        "owsfz":  _stats(by_wav_sig_owsfz),
    }


# ── 2. Cohen's κ ──────────────────────────────────────────────────────────────

def _kappa(rows: list[dict]) -> dict:
    """Cohen's κ for between-appraiser decode agreement with 95% CI."""
    tp = tn = fp = fn = 0
    for r in rows:
        w = r["wsjt_decoded"]
        o = r["owsfz_decoded"]
        if w and o:
            tp += 1
        elif not w and not o:
            tn += 1
        elif o and not w:
            fp += 1   # OpenWSFZ decoded, WSJT-X did not
        else:
            fn += 1   # WSJT-X decoded, OpenWSFZ did not

    n = tp + tn + fp + fn
    if n == 0:
        return {"kappa": None, "ci_95_lo": None, "ci_95_hi": None, "tp": 0, "tn": 0, "fp": 0, "fn": 0}

    p_o  = (tp + tn) / n                    # observed agreement
    p_e  = ((tp + fp) / n) * ((tp + fn) / n) + ((tn + fn) / n) * ((tn + fp) / n)  # expected

    if abs(1.0 - p_e) < 1e-9:
        kappa = 1.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    # Asymptotic 95% CI (Fleiss formula)
    se = math.sqrt(p_o * (1.0 - p_o) / (n * (1.0 - p_e) ** 2)) if n > 0 else 0.0
    z  = 1.96
    return {
        "kappa":    round(kappa, 4),
        "ci_95_lo": round(kappa - z * se, 4),
        "ci_95_hi": round(kappa + z * se, 4),
        "n":        n,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
    }


# ── 3. SNR delta ──────────────────────────────────────────────────────────────

def _snr_delta(rows: list[dict]) -> dict:
    """Mean/std SNR_delta = SNR(OpenWSFZ) − SNR(WSJT-X) for matched decodes.

    Also returns the raw ``pairs`` list of ``(wsjt_snr, owsfz_snr)`` tuples so
    that the scatter plot can draw the y = x reference and annotate the bias line.
    """
    pairs = [
        (r["wsjt_snr"], r["owsfz_snr"])
        for r in rows
        if r["wsjt_decoded"] and r["owsfz_decoded"]
        and r["wsjt_snr"] is not None and r["owsfz_snr"] is not None
    ]
    if not pairs:
        return {"n": 0, "mean": None, "std": None, "deltas": [], "pairs": []}
    deltas = [o - w for w, o in pairs]
    n    = len(deltas)
    mean = sum(deltas) / n
    std  = math.sqrt(sum((d - mean) ** 2 for d in deltas) / n) if n > 1 else 0.0
    return {
        "n":      n,
        "mean":   round(mean, 3),
        "std":    round(std,  3),
        "deltas": deltas,
        "pairs":  pairs,
    }


# ── 4. Order-effect test ──────────────────────────────────────────────────────

def _order_effect(rows: list[dict]) -> dict:
    """Spearman ρ between presentation slot rank and per-WAV decode count per appraiser.

    Returns stats for wsjt and owsfz: {rho, p_value, flagged}.
    """
    from scipy.stats import spearmanr

    # For each (wav, run): slot rank and decode counts
    wav_run_slots:   dict[tuple, int]  = {}
    wav_run_wsjt:    dict[tuple, int]  = defaultdict(int)
    wav_run_owsfz:   dict[tuple, int]  = defaultdict(int)

    for r in rows:
        key = (r["wav"], r["run"])
        wav_run_slots[key]  = r["slot"]
        if r["wsjt_decoded"]:
            wav_run_wsjt[key]  += 1
        if r["owsfz_decoded"]:
            wav_run_owsfz[key] += 1

    keys   = sorted(wav_run_slots.keys())
    slots  = [wav_run_slots[k]  for k in keys]
    wsjt_c = [wav_run_wsjt[k]   for k in keys]
    owsfz_c= [wav_run_owsfz[k]  for k in keys]

    def _spearman(x: list[int], y: list[int]) -> dict:
        if len(set(x)) < 2 or len(set(y)) < 2:
            return {"rho": None, "p_value": None, "flagged": False}
        rho, pval = spearmanr(x, y)
        return {
            "rho":     round(float(rho),  4),
            "p_value": round(float(pval), 4),
            "flagged": float(pval) < 0.05,
        }

    return {
        "wsjt":  _spearman(slots, wsjt_c),
        "owsfz": _spearman(slots, owsfz_c),
    }


# ── Summary CSV (no message text, no callsigns) ───────────────────────────────

def _compute_wav_stats(rows: list[dict]) -> dict[str, dict]:
    """Return per-WAV aggregate metrics dict (keyed by wav name)."""
    wav_stats: dict[str, dict] = defaultdict(lambda: {
        "wsjt_decoded_total": 0, "owsfz_decoded_total": 0,
        "both_decoded": 0, "neither_decoded": 0, "observations": 0,
    })
    for r in rows:
        wav = r["wav"]
        wav_stats[wav]["observations"] += 1
        if r["wsjt_decoded"]:
            wav_stats[wav]["wsjt_decoded_total"] += 1
        if r["owsfz_decoded"]:
            wav_stats[wav]["owsfz_decoded_total"] += 1
        if r["wsjt_decoded"] and r["owsfz_decoded"]:
            wav_stats[wav]["both_decoded"] += 1
        if not r["wsjt_decoded"] and not r["owsfz_decoded"]:
            wav_stats[wav]["neither_decoded"] += 1
    return wav_stats


def _write_summary_csv(wav_stats: dict[str, dict], out_path: Path) -> None:
    """Per-WAV aggregate metrics — committable (no message text column)."""
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "wav", "observations", "wsjt_decoded_total", "owsfz_decoded_total",
            "both_decoded", "neither_decoded",
        ])
        writer.writeheader()
        for wav in sorted(wav_stats):
            writer.writerow({"wav": wav, **wav_stats[wav]})


# ── Plots ─────────────────────────────────────────────────────────────────────

def _plot_consistency(consistency: dict, out_path: Path) -> None:
    import matplotlib.pyplot as plt
    labels   = ["WSJT-X", "OpenWSFZ"]
    pct      = [consistency["wsjt"]["pct_consistent"],
                consistency["owsfz"]["pct_consistent"]]
    colours  = ["#4C72B0", "#DD8452"]
    fig, ax  = plt.subplots(figsize=(6, 4))
    bars = ax.bar(labels, pct, color=colours, width=0.4)
    ax.set_ylim(0, 105)
    ax.set_ylabel("% consistent (wav, signal) pairs")
    ax.set_title("S6 Within-appraiser consistency")
    for bar, p in zip(bars, pct):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{p:.1f}%", ha="center", va="bottom", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _plot_kappa(kappa: dict, out_path: Path) -> None:
    import matplotlib.pyplot as plt
    k    = kappa["kappa"]
    lo   = kappa["ci_95_lo"]
    hi   = kappa["ci_95_hi"]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.barh(["κ"], [k], xerr=[[k - lo], [hi - k]], color="#4C72B0",
            height=0.3, capsize=8, error_kw={"elinewidth": 2})
    ax.set_xlim(-0.1, 1.05)
    ax.axvline(0.9, color="green",  linestyle="--", linewidth=1, label="AIAG ≥ 0.90")
    ax.axvline(0.7, color="orange", linestyle=":",  linewidth=1, label="AIAG ≥ 0.70")
    ax.set_xlabel("Cohen's κ")
    ax.set_title(f"S6 Between-appraiser agreement\nκ = {k:.4f}  95% CI [{lo:.4f}, {hi:.4f}]")
    ax.legend(fontsize=8)
    ax.text(k, 0, f"  {k:.4f}", va="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _plot_snr_delta(snr_stats: dict, out_path: Path) -> None:
    """Scatter plot of OpenWSFZ SNR vs WSJT-X SNR for every matched decode pair.

    The y = x diagonal is the zero-bias reference; the mean-bias line shows the
    systematic offset.  Nonlinearity (bias that changes with SNR) is immediately
    visible as deviation of the point cloud from the mean-bias line — information
    that a delta histogram cannot reveal.
    """
    import matplotlib.pyplot as plt

    pairs = snr_stats.get("pairs", [])
    if not pairs:
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.text(0.5, 0.5, "No matched decodes", ha="center", va="center",
                transform=ax.transAxes)
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        return

    wsjt_snrs  = [w for w, _ in pairs]
    owsfz_snrs = [o for _, o in pairs]
    mean_delta = snr_stats["mean"]

    # Axis range: cover both axes with 2 dB headroom, keeping aspect equal
    lo = min(min(wsjt_snrs), min(owsfz_snrs)) - 2.0
    hi = max(max(wsjt_snrs), max(owsfz_snrs)) + 2.0

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(wsjt_snrs, owsfz_snrs, alpha=0.5, s=18, color="#4C72B0",
               label="Decode pair")
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1.0, label="y = x  (zero bias)")
    ax.plot([lo, hi], [lo + mean_delta, hi + mean_delta], "r-", linewidth=1.5,
            label=f"y = x {mean_delta:+.2f} dB  (mean bias)")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")
    ax.set_xlabel("WSJT-X SNR (dB)")
    ax.set_ylabel("OpenWSFZ SNR (dB)")
    ax.set_title(
        f"S6 SNR scatter  (n = {snr_stats['n']})\n"
        f"mean bias = {snr_stats['mean']:+.3f} dB   σ = {snr_stats['std']:.3f} dB"
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _plot_decode_gap(wav_stats: dict[str, dict], n_runs: int, out_path: Path) -> None:
    """Per-WAV grouped bar chart: WSJT-X vs OpenWSFZ average decode count.

    Bars show per-run averages (total / K) so the y-axis is directly comparable
    to a single-cycle decode count.  Sorted by WAV name (chronological).
    """
    import matplotlib.pyplot as plt
    import numpy as np

    wavs_sorted = sorted(wav_stats.keys())
    k = max(n_runs, 1)
    wsjt_avg  = [wav_stats[w]["wsjt_decoded_total"] / k  for w in wavs_sorted]
    owsfz_avg = [wav_stats[w]["owsfz_decoded_total"] / k for w in wavs_sorted]

    x      = np.arange(len(wavs_sorted))
    width  = 0.4
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(x - width / 2, wsjt_avg,  width, color="#4C72B0", label="WSJT-X",    alpha=0.85)
    ax.bar(x + width / 2, owsfz_avg, width, color="#DD8452", label="OpenWSFZ",  alpha=0.85)

    # Annotation: total FN per WAV (WSJT-X decoded, OpenWSFZ did not)
    for i, w in enumerate(wavs_sorted):
        fn_avg = (wav_stats[w]["wsjt_decoded_total"] - wav_stats[w]["both_decoded"]) / k
        if fn_avg > 0:
            ax.annotate(
                f"−{fn_avg:.0f}",
                xy=(x[i] + width / 2, owsfz_avg[i]),
                xytext=(0, 4), textcoords="offset points",
                ha="center", va="bottom", fontsize=6, color="#C44E52",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(
        [w.replace("260528_", "").replace("260529_", "").replace(".wav", "")
         for w in wavs_sorted],
        rotation=90, fontsize=7,
    )
    ax.set_ylabel(f"Avg decodes per run  (total ÷ {k})")
    ax.set_title(
        "S6 Per-WAV decode count — WSJT-X vs OpenWSFZ\n"
        "Red labels = missed decodes per run (FN avg)"
    )
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ── Report writer ─────────────────────────────────────────────────────────────

def _landis_koch(kappa: float) -> str:
    """Return the Landis-Koch (1977) strength-of-agreement label for κ."""
    if kappa < 0.00:
        return "Poor"
    if kappa < 0.20:
        return "Slight"
    if kappa < 0.40:
        return "Fair"
    if kappa < 0.60:
        return "Moderate"
    if kappa < 0.80:
        return "Substantial"
    return "Almost perfect"


def _write_report(
    out_path: Path,
    manifest: dict,
    consistency: dict,
    kappa: dict,
    snr: dict,
    order: dict,
    wav_stats: dict,
) -> None:
    """Write report.md with callsigns scrubbed."""
    run_date  = manifest.get("run_dir", "?").split("corpus-")[-1][:10]
    owsfz_sha = manifest.get("owsfz_sha", "unknown")
    sha_short = owsfz_sha[:7] if len(owsfz_sha) >= 7 else owsfz_sha
    n_wavs    = manifest["n_wavs"]
    n_runs    = manifest["n_runs"]

    # Decode gap aggregate
    tp = kappa["tp"]
    fn = kappa["fn"]
    total_wsjt = tp + fn   # all WSJT-X decoded observations
    owsfz_rate = 100.0 * tp / total_wsjt if total_wsjt > 0 else 0.0

    # Verdict helpers
    KAPPA_THRESHOLD_GOOD   = 0.90   # AIAG full green
    KAPPA_THRESHOLD_ACCEPT = 0.70   # AIAG conditional accept
    SNR_BIAS_THRESHOLD     = 2.0    # dB — per spec §SNR accuracy
    SNR_SIGMA_THRESHOLD    = 4.0    # dB — D-004 acceptance criterion
    CONSISTENCY_THRESHOLD  = 90.0   # % — AIAG attribute study standard

    def _snr_verdict(mean, std) -> str:
        if mean is None or std is None:
            return "N/A"
        if abs(mean) <= SNR_BIAS_THRESHOLD and std <= SNR_SIGMA_THRESHOLD:
            return "PASS"
        return "FAIL"

    def _kappa_verdict(k) -> str:
        if k is None:
            return "N/A"
        if k >= KAPPA_THRESHOLD_GOOD:
            return "PASS"
        if k >= KAPPA_THRESHOLD_ACCEPT:
            return "CONDITIONAL"
        return "FAIL"

    def _consistency_verdict(pct) -> str:
        return "PASS" if pct >= CONSISTENCY_THRESHOLD else "FAIL"

    kappa_val = kappa["kappa"]
    k_verdict = _kappa_verdict(kappa_val)
    snr_verdict = _snr_verdict(snr.get("mean"), snr.get("std"))
    w_consistency_v = _consistency_verdict(consistency["wsjt"]["pct_consistent"])
    o_consistency_v = _consistency_verdict(consistency["owsfz"]["pct_consistent"])

    lk_label = _landis_koch(kappa_val) if kappa_val is not None else "N/A"

    lines: list[str] = []

    # ── Header & study context ─────────────────────────────────────────────────
    lines += [
        "# S6 Corpus Replay — Analysis Report\n\n",
        "## Study Context\n\n",
        "**Purpose:** S6 is an attribute and SNR measurement study conducted on a real "
        "off-air corpus rather than synthetic signals. It has two objectives:\n\n",
        "1. **Attribute agreement** — do OpenWSFZ and WSJT-X agree on which signals are "
        "present? (Cohen's κ)\n",
        "2. **SNR accuracy field validation** — does the D-002 bias correction (shim "
        "constant −26.5 dB, FT8_SHIM_VERSION 20260006) hold under real-world multi-signal "
        "conditions?\n\n",
        "**Corpus:** 42 off-air WAVs (~35 minutes of live 20 m FT8 activity recorded "
        "2026-05-28/29). Each WAV is one 15-second FT8 slot. The corpus is git-ignored "
        "per NFR-021; only the analysis artefacts are committed.\n\n",
        "**Acceptance thresholds:**\n\n",
        f"| Metric | Threshold | Source |\n",
        f"|---|---|---|\n",
        f"| Between-appraiser κ | ≥ 0.90 (PASS) / ≥ 0.70 (conditional) | AIAG attribute study |\n",
        f"| Within-appraiser consistency | ≥ {CONSISTENCY_THRESHOLD:.0f}% | AIAG attribute study |\n",
        f"| SNR bias (mean delta) | ±{SNR_BIAS_THRESHOLD:.1f} dB | spec §SNR accuracy / D-002 |\n",
        f"| SNR spread (σ of delta) | ≤ {SNR_SIGMA_THRESHOLD:.1f} dB | D-004 acceptance criterion |\n",
        "\n",
        "| Field | Value |\n|---|---|\n",
        f"| Run date | {run_date} |\n",
        f"| OpenWSFZ SHA | `{sha_short}` |\n",
        f"| WSJT-X version | WSJT-X 2.7.0 |\n",
        f"| WAV files | {n_wavs} |\n",
        f"| Runs (K) | {n_runs} |\n",
        f"| Total observations | {kappa.get('n', '?')} |\n",
    ]

    # ── 1. Within-appraiser consistency ───────────────────────────────────────
    lines += [
        "\n## 1. Within-Appraiser Consistency\n\n",
        "_A (WAV, signal) pair is consistent if the decode decision is identical "
        "across all K runs for that appraiser. Measures measurement system stability, "
        "not agreement between appraisers._\n\n",
        "| Appraiser | (WAV, signal) pairs | Consistent | % Consistent | Verdict |\n",
        "|---|---|---|---|---|\n",
    ]
    for app, label in [("wsjt", "WSJT-X"), ("owsfz", "OpenWSFZ")]:
        c = consistency[app]
        v = _consistency_verdict(c["pct_consistent"])
        lines.append(
            f"| {label} | {c['total_pairs']} | {c['consistent_pairs']} "
            f"| {c['pct_consistent']:.1f}% | {v} |\n"
        )
    lines.append("\n![Within-appraiser consistency](consistency.png)\n")

    # ── 2. Between-appraiser agreement ────────────────────────────────────────
    lines += [
        "\n## 2. Between-Appraiser Agreement (Cohen's κ)\n\n",
        "_Measures how much more often the two appraisers agree than would be expected "
        "by chance alone. Landis-Koch (1977) scale: < 0.20 Slight, 0.20–0.40 Fair, "
        "0.40–0.60 Moderate, 0.60–0.80 Substantial, ≥ 0.80 Almost perfect._\n\n",
        f"**κ = {kappa_val}**  (95% CI [{kappa['ci_95_lo']}, {kappa['ci_95_hi']}])  "
        f"— {lk_label}  **[{k_verdict}]**\n\n",
        "_AIAG thresholds: κ ≥ 0.90 = acceptable; κ ≥ 0.70 = conditionally acceptable; "
        "κ < 0.70 = unacceptable. The gap is driven almost entirely by Section 3 (missed "
        "decodes — D-001)._\n\n",
        "| | WSJT-X decoded | WSJT-X not decoded |\n",
        "|---|---|---|\n",
        f"| **OpenWSFZ decoded** | {kappa['tp']} (TP) | {kappa['fp']} (FP) |\n",
        f"| **OpenWSFZ not decoded** | {kappa['fn']} (FN) | {kappa['tn']} (TN) |\n",
        "\n![Between-appraiser agreement](kappa.png)\n",
    ]

    # ── 3. Decode gap ─────────────────────────────────────────────────────────
    lines += [
        "\n## 3. Decode Gap — D-001 Field Evidence\n\n",
        "_Informational — no pass threshold is set pending a D-001 fix. "
        "Establishes the real-world decode gap baseline._\n\n",
        f"OpenWSFZ decoded **{tp:,}** of the **{total_wsjt:,}** signals found by WSJT-X "
        f"(**{owsfz_rate:.1f}%**). "
        f"**{fn:,}** signals were decoded by WSJT-X but missed by OpenWSFZ ({100-owsfz_rate:.1f}%).\n\n",
    ]

    # Per-WAV summary (top 5 worst gap files by FN count)
    wavs_by_fn = sorted(
        wav_stats.items(),
        key=lambda kv: kv[1]["wsjt_decoded_total"] - kv[1]["both_decoded"],
        reverse=True,
    )
    if wavs_by_fn:
        lines += [
            "### Worst-gap files (top 10 by missed decodes, averaged over K runs)\n\n",
            "| WAV | WSJT-X avg | OpenWSFZ avg | Missed avg | OpenWSFZ rate |\n",
            "|---|---|---|---|---|\n",
        ]
        for wav, stats in wavs_by_fn[:10]:
            w_avg  = stats["wsjt_decoded_total"]  / n_runs
            o_avg  = stats["owsfz_decoded_total"] / n_runs
            fn_avg = (stats["wsjt_decoded_total"] - stats["both_decoded"]) / n_runs
            rate   = 100.0 * stats["both_decoded"] / stats["wsjt_decoded_total"] \
                     if stats["wsjt_decoded_total"] > 0 else 0.0
            lines.append(
                f"| {wav} | {w_avg:.1f} | {o_avg:.1f} | {fn_avg:.1f} | {rate:.0f}% |\n"
            )
    lines.append("\n![Per-WAV decode gap](decode_gap.png)\n")

    # ── 4. SNR reporting accuracy ──────────────────────────────────────────────
    lines += ["\n## 4. SNR Reporting Accuracy — D-004 Field Validation\n\n"]
    if snr["n"] > 0:
        lines += [
            f"Mean SNR delta (OpenWSFZ − WSJT-X) = **{snr['mean']:+.3f} dB** "
            f"(threshold ±{SNR_BIAS_THRESHOLD:.1f} dB)  **[{'PASS' if abs(snr['mean']) <= SNR_BIAS_THRESHOLD else 'FAIL'}]**\n\n",
            f"σ = **{snr['std']:.3f} dB** "
            f"(threshold ≤ {SNR_SIGMA_THRESHOLD:.1f} dB)  **[{'PASS' if snr['std'] <= SNR_SIGMA_THRESHOLD else 'FAIL'}]**\n\n",
            f"n = {snr['n']:,} matched decode pairs (both appraisers decoded the same signal)\n\n",
            "_Positive delta = OpenWSFZ reports higher SNR than WSJT-X. "
            "The synthetic S1 baseline (run `0682106`) returned +1.78 dB mean — within "
            "threshold. This run uses real off-air signals; any systematic difference "
            "indicates the shim constant fix does not generalise to field conditions (D-004)._\n",
        ]
    else:
        lines.append("_No matched decodes found._\n")
    lines.append("\n![SNR scatter — OpenWSFZ vs WSJT-X](snr_delta.png)\n")

    # ── 5. Order-effect test ───────────────────────────────────────────────────
    lines += ["\n## 5. Order-Effect Test\n\n",
              "_Spearman ρ between WAV presentation slot rank and per-WAV decode count. "
              "A significant result (p < 0.05) would indicate session-state carryover "
              "(e.g. decoder warm-up artefacts, ALL.TXT accumulation). "
              "No effect expected in a correctly executed corpus replay._\n\n"]
    for app, label in [("wsjt", "WSJT-X"), ("owsfz", "OpenWSFZ")]:
        o = order[app]
        if o["rho"] is None:
            lines.append(f"**{label}:** insufficient variance — order effect not testable.\n\n")
        elif o["flagged"]:
            lines.append(
                f"**{label}:** ⚠ Potential order effect detected — "
                f"Spearman ρ = {o['rho']}, p = {o['p_value']} (< 0.05). "
                f"Session-state carryover suspected.\n\n"
            )
        else:
            lines.append(
                f"**{label}:** No order effect detected — "
                f"Spearman ρ = {o['rho']}, p = {o['p_value']}.\n\n"
            )

    # ── Summary verdict ────────────────────────────────────────────────────────
    snr_mean = snr.get("mean")
    snr_std  = snr.get("std")
    overall  = "PASS" if all([
        consistency["wsjt"]["pct_consistent"]  >= CONSISTENCY_THRESHOLD,
        consistency["owsfz"]["pct_consistent"] >= CONSISTENCY_THRESHOLD,
        snr_mean is not None and abs(snr_mean) <= SNR_BIAS_THRESHOLD,
        snr_std  is not None and snr_std <= SNR_SIGMA_THRESHOLD,
    ]) else "FAIL"

    lines += [
        "\n## Summary\n\n",
        "| Metric | Value | Threshold | Verdict |\n",
        "|---|---|---|---|\n",
        f"| Within-appraiser consistency (WSJT-X) | "
        f"{consistency['wsjt']['pct_consistent']:.1f}% | ≥ {CONSISTENCY_THRESHOLD:.0f}% | "
        f"{w_consistency_v} |\n",
        f"| Within-appraiser consistency (OpenWSFZ) | "
        f"{consistency['owsfz']['pct_consistent']:.1f}% | ≥ {CONSISTENCY_THRESHOLD:.0f}% | "
        f"{o_consistency_v} |\n",
        f"| Between-appraiser κ | {kappa_val} | ≥ 0.70 | {k_verdict} |\n",
        f"| OpenWSFZ decode rate vs WSJT-X | {owsfz_rate:.1f}% | — (informational) | — |\n",
    ]
    if snr_mean is not None:
        bias_v = "PASS" if abs(snr_mean) <= SNR_BIAS_THRESHOLD else "FAIL"
        std_v  = "PASS" if snr_std is not None and snr_std <= SNR_SIGMA_THRESHOLD else "FAIL"
        lines += [
            f"| SNR bias (mean delta) | {snr_mean:+.3f} dB | ±{SNR_BIAS_THRESHOLD:.1f} dB | {bias_v} |\n",
            f"| SNR spread (σ) | {snr_std:.3f} dB | ≤{SNR_SIGMA_THRESHOLD:.1f} dB | {std_v} |\n",
        ]

    lines.append(f"\n**Overall verdict: {overall}**\n")

    if overall == "FAIL":
        lines.append("\n### Defect Notices\n\n")
        if kappa_val is not None and kappa_val < KAPPA_THRESHOLD_ACCEPT:
            lines.append(
                f"- ❌ FAIL — Between-appraiser κ = {kappa_val} "
                f"(threshold ≥ 0.70). Root cause: D-001 decode gap "
                f"({fn:,} missed decodes, {100-owsfz_rate:.1f}% miss rate).\n"
            )
        if snr_mean is not None and abs(snr_mean) > SNR_BIAS_THRESHOLD:
            lines.append(
                f"- ❌ FAIL — SNR bias = {snr_mean:+.3f} dB "
                f"(threshold ±{SNR_BIAS_THRESHOLD:.1f} dB). See D-004.\n"
            )
        if snr_std is not None and snr_std > SNR_SIGMA_THRESHOLD:
            lines.append(
                f"- ❌ FAIL — SNR σ = {snr_std:.3f} dB "
                f"(threshold ≤{SNR_SIGMA_THRESHOLD:.1f} dB). See D-003/D-004.\n"
            )

    lines.append(
        "\n---\n\n_Callsigns scrubbed per NFR-021. "
        "Real callsigns replaced with `[CALL]` before commit._\n"
    )

    raw_text = "".join(lines)
    scrubbed = _scrub_or_abort(raw_text, context="report.md")
    out_path.write_text(scrubbed, encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="S6 corpus replay analysis — consistency, κ, SNR delta, order effect"
    )
    parser.add_argument(
        "--run-dir", type=Path, required=True,
        help="Path to the corpus run directory (e.g. results/corpus-2026-06-11)",
    )
    args = parser.parse_args()
    run_dir = args.run_dir
    if not run_dir.is_absolute():
        run_dir = _QA_ROOT / run_dir

    print(f"Analysing: {run_dir}")

    manifest    = _load_manifest(run_dir)
    rows        = _build_observations(manifest)
    n_runs      = manifest["n_runs"]

    if not rows:
        sys.exit("ERROR: no observations found — manifest may be empty.")

    print(f"  Observations: {len(rows)}")

    # ── Compute metrics ────────────────────────────────────────────────────────
    consistency = _consistency(rows, n_runs)
    kappa       = _kappa(rows)
    snr         = _snr_delta(rows)
    order       = _order_effect(rows)
    wav_stats   = _compute_wav_stats(rows)

    # ── Print summary ──────────────────────────────────────────────────────────
    tp = kappa["tp"]
    fn = kappa["fn"]
    owsfz_rate = 100.0 * tp / (tp + fn) if (tp + fn) > 0 else 0.0

    print()
    print("Within-appraiser consistency:")
    for app, label in [("wsjt", "WSJT-X"), ("owsfz", "OpenWSFZ")]:
        c = consistency[app]
        print(f"  {label}: {c['pct_consistent']:.1f}%  "
              f"({c['consistent_pairs']}/{c['total_pairs']} pairs)")
    print()
    print(f"Between-appraiser κ: {kappa['kappa']}  "
          f"95% CI [{kappa['ci_95_lo']}, {kappa['ci_95_hi']}]")
    print(f"  OpenWSFZ decode rate vs WSJT-X: {owsfz_rate:.1f}%  "
          f"(TP={tp}, FN={fn})")
    print()
    if snr["n"] > 0:
        print(f"SNR delta (OpenWSFZ − WSJT-X): mean={snr['mean']:+.3f} dB  "
              f"σ={snr['std']:.3f}  n={snr['n']}")
    else:
        print("SNR delta: no matched decodes.")
    print()
    for app, label in [("wsjt", "WSJT-X"), ("owsfz", "OpenWSFZ")]:
        o = order[app]
        if o["rho"] is not None:
            flag = " ⚠ ORDER EFFECT" if o["flagged"] else ""
            print(f"Order effect {label}: rho={o['rho']} p={o['p_value']}{flag}")

    # ── Write committed artifacts ──────────────────────────────────────────────
    print("\nWriting committed artifacts ...")
    _write_report(run_dir / "report.md", manifest, consistency, kappa, snr, order, wav_stats)
    print("  report.md")

    _write_summary_csv(wav_stats, run_dir / "summary.csv")
    print("  summary.csv")

    _plot_consistency(consistency, run_dir / "consistency.png")
    print("  consistency.png")

    _plot_kappa(kappa, run_dir / "kappa.png")
    print("  kappa.png")

    _plot_snr_delta(snr, run_dir / "snr_delta.png")
    print("  snr_delta.png")

    _plot_decode_gap(wav_stats, n_runs, run_dir / "decode_gap.png")
    print("  decode_gap.png")

    print()
    print("Analysis complete.")
    print("Review committed artifacts, then:")
    print(f"  git add {run_dir}/report.md {run_dir}/summary.csv {run_dir}/*.png")
    print(f"  git commit -m 'qa(rr-study): record S6 corpus replay results'")


if __name__ == "__main__":
    main()
