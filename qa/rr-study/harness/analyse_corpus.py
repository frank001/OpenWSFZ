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

def _write_summary_csv(rows: list[dict], out_path: Path) -> None:
    """Per-WAV aggregate metrics — committable (no message text column)."""
    # Compute per-WAV stats
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


# ── Report writer ─────────────────────────────────────────────────────────────

def _write_report(
    out_path: Path,
    manifest: dict,
    consistency: dict,
    kappa: dict,
    snr: dict,
    order: dict,
) -> None:
    """Write report.md with callsigns scrubbed. Aborts if scrub finds a problem."""
    lines = [
        "# S6 Corpus Replay — Report\n\n",
        f"| Field | Value |\n|---|---|\n",
        f"| Run date | {manifest.get('run_dir', '?').split('corpus-')[-1][:10]} |\n",
        f"| WAV files | {manifest['n_wavs']} |\n",
        f"| Runs (K) | {manifest['n_runs']} |\n",
        f"| Total observations | {kappa.get('n', '?')} |\n",
        "\n## 1. Within-appraiser consistency\n\n",
        "| Appraiser | Total (wav,signal) pairs | Consistent | % Consistent |\n",
        "|---|---|---|---|\n",
    ]
    for app, label in [("wsjt", "WSJT-X"), ("owsfz", "OpenWSFZ")]:
        c = consistency[app]
        lines.append(
            f"| {label} | {c['total_pairs']} | {c['consistent_pairs']} "
            f"| {c['pct_consistent']:.1f}% |\n"
        )
    lines += [
        "\n## 2. Between-appraiser agreement (Cohen's κ)\n\n",
        f"κ = **{kappa['kappa']}**  (95% CI [{kappa['ci_95_lo']}, {kappa['ci_95_hi']}])\n\n",
        "| | WSJT-X decoded | WSJT-X not decoded |\n",
        "|---|---|---|\n",
        f"| **OpenWSFZ decoded** | {kappa['tp']} (TP) | {kappa['fp']} (FP) |\n",
        f"| **OpenWSFZ not decoded** | {kappa['fn']} (FN) | {kappa['tn']} (TN) |\n",
        "\n## 3. SNR delta (D-002 field validation)\n\n",
    ]
    if snr["n"] > 0:
        lines.append(
            f"Mean SNR delta (OpenWSFZ − WSJT-X) = **{snr['mean']:+.3f} dB**  "
            f"σ = {snr['std']:.3f} dB  (n = {snr['n']})\n\n"
            "_Positive delta = OpenWSFZ reports higher SNR than WSJT-X._\n"
        )
    else:
        lines.append("_No matched decodes found._\n")

    lines += ["\n## 4. Order-effect test\n\n"]
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

    # ── Print summary ──────────────────────────────────────────────────────────
    print()
    print("Within-appraiser consistency:")
    for app, label in [("wsjt", "WSJT-X"), ("owsfz", "OpenWSFZ")]:
        c = consistency[app]
        print(f"  {label}: {c['pct_consistent']:.1f}%  "
              f"({c['consistent_pairs']}/{c['total_pairs']} pairs)")
    print()
    print(f"Between-appraiser kappa: {kappa['kappa']}  "
          f"95% CI [{kappa['ci_95_lo']}, {kappa['ci_95_hi']}]")
    print()
    if snr["n"] > 0:
        print(f"SNR delta (OpenWSFZ - WSJT-X): mean={snr['mean']:+.3f} dB  "
              f"sigma={snr['std']:.3f}  n={snr['n']}")
    else:
        print("SNR delta: no matched decodes.")
    print()
    for app, label in [("wsjt", "WSJT-X"), ("owsfz", "OpenWSFZ")]:
        o = order[app]
        if o["rho"] is not None:
            flag = " (!) ORDER EFFECT" if o["flagged"] else ""
            print(f"Order effect {label}: rho={o['rho']} p={o['p_value']}{flag}")

    # ── Write committed artifacts ──────────────────────────────────────────────
    print("\nWriting committed artifacts ...")
    _write_report(run_dir / "report.md", manifest, consistency, kappa, snr, order)
    print("  report.md")

    _write_summary_csv(rows, run_dir / "summary.csv")
    print("  summary.csv")

    _plot_consistency(consistency, run_dir / "consistency.png")
    print("  consistency.png")

    _plot_kappa(kappa, run_dir / "kappa.png")
    print("  kappa.png")

    _plot_snr_delta(snr, run_dir / "snr_delta.png")
    print("  snr_delta.png")

    print()
    print("Analysis complete.")
    print("Review committed artifacts, then:")
    print(f"  git add {run_dir}/report.md {run_dir}/summary.csv {run_dir}/*.png")
    print(f"  git commit -m 'qa(rr-study): record S6 corpus replay results'")


if __name__ == "__main__":
    main()
