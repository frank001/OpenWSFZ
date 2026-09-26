#!/usr/bin/env python3
"""Step 2 of the standard post-endurance-run routine (Captain's instruction, 2026-09-24):
charts + automated anomaly resolution from spectrum_scan.py's output.

Produces, into --out-dir:
    spectrum_scan_level_timeseries.png   -- dBFS over the run, gain-step/dropout check
    spectrum_scan_hum_timeseries.png     -- sub-passband hum band over the run, with the
                                             control run's line drawn if --control-scan-json given
    spectrum_scan_spur_histogram.png     -- in-band spur-candidate peak-frequency spread
    spectrum_scan_example_spectrum.png   -- one representative cycle, bands annotated
    spectral_trace.png                   -- Welch PSD + STFT spectrogram, quiet/typical/loud
                                             cycles plus (if resolved) the dominant spur cycle
    findings.json                        -- machine-readable verdicts for render_dossier.py

Two things are resolved MECHANICALLY here rather than left as prose caveats (HK-021):

1. Sub-passband hum. A fixed low-frequency line over the noise floor is what you'd expect
   from a ground-loop/isolation problem. Pass --control-scan-json (a prior run's own
   spectrum_scan.py output, same band, different capture chain if that's what's being
   tested) to compare medians; without one, this step says so plainly rather than assert a
   verdict it has no control for.

2. In-band spur candidates. A >40dB-over-local-median peak in the FT8 passband is also
   exactly what a strong, correctly-decoded station's tone looks like -- this script cannot
   tell the two apart from the audio alone. If the dominant spur-frequency bin covers at
   least SPUR_MATERIAL_SHARE of all files, it is cross-referenced against the run's own
   ALL.TXT (frequency +/- SPUR_XREF_TOLERANCE_HZ): >=SPUR_XREF_MIN_HITS decodes and
   >=SPUR_XREF_MIN_DISTINCT_MESSAGES distinct message texts there is real, varying-SNR
   station traffic (a birdie decodes nothing coherent); anything short of that is left an
   open ALERT for a human to look at, never silently resolved either way.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import wave
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import welch, spectrogram
from matplotlib.colors import LinearSegmentedColormap

# -- Palette: identical tokens to anova_common.py's render_charts() (HK-034) --------------
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
ACCENT = "#2a78d6"
ACCENT_LIGHT = "#9ec5f4"
CONTROL_RED = "#b3403a"

# -- Dossier dark palette, for the spectral-trace figure only -----------------------------
D_INK = "#1b1712"
D_PANEL = "#24201a"
D_CREAM = "#ece5d8"
D_DIM = "#a89984"
D_HAIR = "#3c3428"
D_AMBER = "#d99a3d"
D_INFO = "#7a93ad"
SPEC_CMAP = LinearSegmentedColormap.from_list(
    "dossier_spec", ["#1b1712", "#4a3420", "#8a6432", "#d99a3d", "#f2d9a0"])

FT8_BAND = (200.0, 2900.0)
HUM_FUND = (45.0, 65.0)
HUM_H2 = (95.0, 125.0)
NOISE_FLOOR_HZ = (5000.0, 5900.0)

HUM_CONTROL_TOLERANCE_DB = 5.0        # within this of the control = "predates the chain"
SPUR_MATERIAL_SHARE = 0.05            # dominant bin must cover >=5% of all files to chase
SPUR_XREF_TOLERANCE_HZ = 3.0
SPUR_XREF_MIN_HITS = 10
SPUR_XREF_MIN_DISTINCT_MESSAGES = 5


def style_ax(ax):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=INK_MUTED)
    for spine in ax.spines.values():
        spine.set_color(INK_MUTED)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)
    ax.title.set_color(INK_PRIMARY)


def to_hours(ts: str, t0: str) -> float:
    import datetime
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.datetime.strptime(ts, fmt) - datetime.datetime.strptime(t0, fmt)).total_seconds() / 3600.0


def read_wav(path: str):
    with wave.open(path, "rb") as w:
        fs = w.getframerate()
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    return x - x.mean(), fs


def render_charts(rows: list[dict], out_dir: str, control_summary: dict | None) -> dict:
    rows = [r for r in rows if "error" not in r]
    rows.sort(key=lambda r: r["ts"])
    t0 = rows[0]["ts"]
    hours = np.array([to_hours(r["ts"], t0) for r in rows])
    dbfs = np.array([r["dbfs"] for r in rows])
    hum2 = np.array([r["hum2_over_floor_db"] for r in rows])
    peak_freq = np.array([r["peak_freq_hz"] for r in rows])
    peak_db = np.array([r["peak_to_med_db"] for r in rows])
    order = np.argsort(hours)
    h_sorted = hours[order]
    win = min(120, max(10, len(rows) // 20))

    # 1. Level over time
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    fig.patch.set_facecolor(SURFACE); style_ax(ax)
    ax.scatter(hours, dbfs, s=3, alpha=0.25, color=ACCENT_LIGHT, linewidths=0, label=f"per-cycle dBFS (n={len(rows)})")
    roll = np.array([np.median(dbfs[order][max(0, i - win // 2):i + win // 2]) for i in range(len(order))])
    ax.plot(h_sorted, roll, color=ACCENT, linewidth=1.4, label="rolling median")
    ax.axhline(float(np.median(dbfs)), linestyle="--", linewidth=1.0, color=INK_SECONDARY,
               label=f"corpus median = {np.median(dbfs):.2f} dBFS")
    ax.set_xlabel(f"hours since window open ({t0})"); ax.set_ylabel("level (dBFS)")
    ax.set_title("Capture level over the run")
    ax.legend(loc="lower right", fontsize=8, facecolor=SURFACE, edgecolor=INK_MUTED)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "spectrum_scan_level_timeseries.png"), dpi=130, facecolor=SURFACE)
    plt.close(fig)

    # 2. Hum band over time (+ control line if given)
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    fig.patch.set_facecolor(SURFACE); style_ax(ax)
    ax.scatter(hours, hum2, s=3, alpha=0.25, color=ACCENT_LIGHT, linewidths=0,
               label=f"per-cycle 95-125Hz-over-floor (n={len(rows)})")
    roll2 = np.array([np.median(hum2[order][max(0, i - win // 2):i + win // 2]) for i in range(len(order))])
    ax.plot(h_sorted, roll2, color=ACCENT, linewidth=1.4, label="rolling median")
    if control_summary is not None:
        cval = control_summary["hum2_over_floor_median_db"]
        ax.axhline(cval, linestyle="--", linewidth=1.4, color=CONTROL_RED,
                   label=f"control run median = {cval:.2f} dB")
    ax.set_xlabel(f"hours since window open ({t0})"); ax.set_ylabel("95-125Hz band power over floor bucket (dB)")
    ax.set_title("Sub-passband hum band over the run")
    ax.legend(loc="upper right", fontsize=8, facecolor=SURFACE, edgecolor=INK_MUTED)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "spectrum_scan_hum_timeseries.png"), dpi=130, facecolor=SURFACE)
    plt.close(fig)

    # 3. Spur frequency histogram
    spur_mask = peak_db > 40.0
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    fig.patch.set_facecolor(SURFACE); style_ax(ax)
    bins = np.arange(FT8_BAND[0], FT8_BAND[1] + 25, 25)
    ax.hist(peak_freq[spur_mask], bins=bins, color=ACCENT, edgecolor=SURFACE, linewidth=0.3)
    ax.set_xlabel("in-band peak frequency (Hz)")
    ax.set_ylabel(f"file count (of {int(spur_mask.sum())} spur candidates)")
    ax.set_title("In-band spur-candidate frequency spread")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "spectrum_scan_spur_histogram.png"), dpi=130, facecolor=SURFACE)
    plt.close(fig)

    # 4. Representative example spectrum (closest-to-median file)
    med_dbfs = float(np.median(dbfs))
    rep_row = rows[int(np.argmin(np.abs(dbfs - med_dbfs)))]
    x, fs = read_wav(os.path.join(args.wav_dir, rep_row["file"]))
    xw = x * np.hanning(len(x))
    spec = np.fft.rfft(xw)
    power_db = 10 * np.log10(spec.real**2 + spec.imag**2 + 1e-9)
    freqs = np.fft.rfftfreq(len(x), d=1.0 / fs)
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    fig.patch.set_facecolor(SURFACE); style_ax(ax)
    m = freqs <= 6000
    ax.plot(freqs[m], power_db[m], color=ACCENT, linewidth=0.5)
    for band, name, color in [(HUM_FUND, "hum fund. 45-65Hz", "#e0a458"),
                               (HUM_H2, "hum 2nd harm. 95-125Hz", "#c97a3a"),
                               (FT8_BAND, "FT8 decode passband", "#7fb7e8"),
                               (NOISE_FLOOR_HZ, "near-Nyquist floor bucket", INK_MUTED)]:
        ax.axvspan(band[0], band[1], color=color, alpha=0.18, label=name)
    ax.set_xlabel("frequency (Hz)"); ax.set_ylabel("power (dB, arbitrary reference)")
    ax.set_title(f"Representative single-cycle spectrum ({rep_row['file']})")
    ax.legend(loc="upper right", fontsize=7.5, facecolor=SURFACE, edgecolor=INK_MUTED)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "spectrum_scan_example_spectrum.png"), dpi=130, facecolor=SURFACE)
    plt.close(fig)

    return {"representative_file": rep_row["file"]}


def resolve_spur(summary: dict, all_txt_path: str | None) -> dict:
    """Mechanical spur resolution (HK-021): dominant frequency bin -> ALL.TXT cross-reference."""
    bins = summary.get("top_spur_frequency_bins_hz") or []
    n_files = summary["n_files"]
    if not bins:
        return {"ran": False, "verdict": "no spur candidates found", "material": False}
    top_freq, top_count = bins[0]
    share = top_count / n_files if n_files else 0.0
    if share < SPUR_MATERIAL_SHARE:
        return {"ran": False, "material": False, "top_freq_hz": top_freq, "top_count": top_count,
                "share_of_files": share,
                "verdict": f"no dominant bin (top = {share*100:.1f}% of files, below the "
                           f"{SPUR_MATERIAL_SHARE*100:.0f}% materiality bar) -- ordinary spread traffic"}
    if not all_txt_path or not os.path.isfile(all_txt_path):
        return {"ran": False, "material": True, "top_freq_hz": top_freq, "top_count": top_count,
                "share_of_files": share,
                "verdict": "dominant bin found but no ALL.TXT supplied for cross-reference -- "
                           "OPEN, needs manual review before shipping this report"}

    # NFR-021 (per anova_common.py's own, stricter convention for exactly this class of
    # QA-pipeline output): message text is read ONLY to build the distinct-message count
    # and the top-message SHARE below -- it is never captured into a local variable that
    # survives this loop, never printed, and never written to findings.json or anywhere
    # else. A real third-party callsign was found live (2026-09-24) in a published
    # artefact whose only source was this function returning the literal message text --
    # fixed by never letting that text leave this function's stack in the first place,
    # not by remembering to redact it downstream every time.
    n_hits = 0
    msg_counts: Counter = Counter()
    snr_min = snr_max = None
    with open(all_txt_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 8:
                continue
            try:
                freq = int(parts[6])
                snr = int(parts[4])
            except ValueError:
                continue
            if abs(freq - top_freq) <= SPUR_XREF_TOLERANCE_HZ:
                n_hits += 1
                msg_counts[" ".join(parts[7:])] += 1  # local to this loop only
                snr_min = snr if snr_min is None else min(snr_min, snr)
                snr_max = snr if snr_max is None else max(snr_max, snr)

    distinct = len(msg_counts)
    top_msg_count = msg_counts.most_common(1)[0][1] if msg_counts else 0
    del msg_counts  # never returned, never printed -- see note above

    if n_hits >= SPUR_XREF_MIN_HITS and distinct >= SPUR_XREF_MIN_DISTINCT_MESSAGES:
        verdict = "RESOLVED: real station traffic, not a hardware/decoder artefact"
    else:
        verdict = ("OPEN -- ALERT: too few decodes or too little message diversity at this "
                   "frequency to confirm real traffic; investigate before shipping this report")

    return {
        "ran": True, "material": True,
        "top_freq_hz": top_freq, "top_count": top_count, "share_of_files": share,
        "xref_tolerance_hz": SPUR_XREF_TOLERANCE_HZ,
        "n_hits": n_hits, "distinct_messages": distinct,
        "top_message_share": (top_msg_count / n_hits) if n_hits else float("nan"),
        "snr_min": snr_min, "snr_max": snr_max,
        "verdict": verdict,
    }


def render_spectral_trace(rows: list[dict], wav_dir: str, spur: dict, out_path: str) -> dict:
    rows = [r for r in rows if "error" not in r]
    quiet_row = min(rows, key=lambda r: r["dbfs"])
    loud_row = max(rows, key=lambda r: r["dbfs"])
    med_dbfs = float(np.median([r["dbfs"] for r in rows]))
    typical_row = min(rows, key=lambda r: abs(r["dbfs"] - med_dbfs))

    panels = [
        ("QUIET", quiet_row["file"], f"{quiet_row['dbfs']:.2f} dBFS, corpus minimum"),
        ("TYPICAL", typical_row["file"], f"{typical_row['dbfs']:.2f} dBFS, closest to median"),
        ("LOUD", loud_row["file"], f"{loud_row['dbfs']:.2f} dBFS, corpus maximum"),
    ]
    notable_file = None
    if spur.get("ran") and spur.get("verdict", "").startswith("RESOLVED"):
        target_ts = None
        target_freq = spur["top_freq_hz"]
        for r in rows:
            if abs(r["peak_freq_hz"] - target_freq) <= 5 and r["peak_to_med_db"] > 40:
                target_ts = r
                break
        if target_ts is not None:
            notable_file = target_ts["file"]
            panels.append(("SPUR-RESOLVED", notable_file,
                            f"{target_freq:.0f} Hz -- {spur['n_hits']} decodes, "
                            f"{spur['distinct_messages']} distinct messages"))

    n = len(panels)
    fig, axes = plt.subplots(n, 2, figsize=(11, 3.1 * n))
    if n == 1:
        axes = axes.reshape(1, 2)
    fig.patch.set_facecolor(D_INK)

    for i, (label, fname, note) in enumerate(panels):
        x, fs = read_wav(os.path.join(wav_dir, fname))
        ax_psd, ax_spec = axes[i, 0], axes[i, 1]
        for ax in (ax_psd, ax_spec):
            ax.set_facecolor(D_PANEL)
            for spine in ax.spines.values():
                spine.set_color(D_HAIR)
            ax.tick_params(colors=D_DIM, labelsize=8)

        f_w, p_w = welch(x, fs=fs, nperseg=2048, noverlap=1024)
        p_db = 10 * np.log10(p_w + 1e-9)
        ax_psd.plot(f_w, p_db, color=D_AMBER, linewidth=0.9)
        ax_psd.fill_between(f_w, p_db, p_db.min(), color=D_AMBER, alpha=0.12)
        ax_psd.set_xlim(0, 3000)
        ax_psd.set_ylabel("PSD (dB)", color=D_DIM, fontsize=8.5)
        ax_psd.set_title(f"{label} -- Welch PSD", color=D_CREAM, fontsize=9.5, loc="left")

        f_s, t_s, Sxx = spectrogram(x, fs=fs, nperseg=512, noverlap=384)
        Sxx_db = 10 * np.log10(Sxx + 1e-9)
        band = f_s <= 3000
        band_db = Sxx_db[band, :]
        vmin, vmax = np.percentile(band_db, [15, 99.5])
        ax_spec.pcolormesh(t_s, f_s[band], band_db, cmap=SPEC_CMAP, shading="auto", vmin=vmin, vmax=vmax)
        ax_spec.set_ylabel("Hz", color=D_DIM, fontsize=8.5)
        ax_spec.set_title(f"{label} -- STFT spectrogram", color=D_CREAM, fontsize=9.5, loc="left")
        if label == "SPUR-RESOLVED":
            ax_spec.axhline(spur["top_freq_hz"], color=D_INFO, linewidth=0.9, linestyle="--", alpha=0.85)
        if i == n - 1:
            ax_psd.set_xlabel("Hz", color=D_DIM, fontsize=8.5)
            ax_spec.set_xlabel("s", color=D_DIM, fontsize=8.5)
        ax_spec.text(0.01, 0.97, note, transform=ax_spec.transAxes, ha="left", va="top",
                     fontsize=7, color=D_CREAM, family="monospace",
                     bbox=dict(facecolor=D_INK, alpha=0.55, edgecolor="none", pad=2))

    fig.tight_layout(pad=1.6, h_pad=1.8)
    fig.savefig(out_path, dpi=140, facecolor=D_INK)
    plt.close(fig)
    return {"panels": [p[0] for p in panels], "notable_file": notable_file}


def main() -> int:
    global args
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scan-json", required=True, help="Output of spectrum_scan.py for this run")
    ap.add_argument("--wav-dir", required=True)
    ap.add_argument("--all-txt", default=None, help="This run's owsfz ALL.TXT, for spur cross-reference")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--control-scan-json", default=None,
                     help="A prior run's spectrum_scan.py output (same band, comparison chain) "
                          "for the hum-band control check. Omit if none applies -- the report "
                          "will say a control was not available rather than guess.")
    args = ap.parse_args()

    with open(args.scan_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    summary, rows = data["summary"], data["rows"]

    control_summary = None
    if args.control_scan_json:
        with open(args.control_scan_json, "r", encoding="utf-8") as f:
            control_summary = json.load(f)["summary"]

    chart_info = render_charts(rows, args.out_dir, control_summary)
    spur = resolve_spur(summary, args.all_txt)
    trace_info = render_spectral_trace(rows, args.wav_dir, spur,
                                        os.path.join(args.out_dir, "spectral_trace.png"))

    hum_verdict: dict = {"this_run_median_db": summary["hum2_over_floor_median_db"]}
    if control_summary is not None:
        cval = control_summary["hum2_over_floor_median_db"]
        delta = summary["hum2_over_floor_median_db"] - cval
        hum_verdict.update({
            "control_median_db": cval, "delta_db": delta,
            "verdict": ("consistent with control -- predates any chain change" if abs(delta) <= HUM_CONTROL_TOLERANCE_DB
                        else f"diverges from control by {delta:+.1f} dB -- investigate, do not assume chain-caused without more data"),
        })
    else:
        hum_verdict["verdict"] = "no control run supplied -- not claiming chain-independence, compare manually if a comparator exists"

    data_quality_ok = (summary["n_errors"] == 0 and summary["format_consistent"]
                        and summary["clipping_file_count"] == 0 and summary["silent_file_count"] == 0
                        and summary["hot_file_count"] == 0)

    findings = {
        "data_quality": {
            "ok": data_quality_ok,
            "n_files": summary["n_files"], "n_errors": summary["n_errors"],
            "format_consistent": summary["format_consistent"],
            "clipping_file_count": summary["clipping_file_count"],
            "silent_file_count": summary["silent_file_count"],
            "hot_file_count": summary["hot_file_count"],
            "dbfs_median": summary["dbfs_median"], "dbfs_mad": summary["dbfs_mad"],
            "dbfs_range": [summary["dbfs_min"], summary["dbfs_max"]],
        },
        "hum": hum_verdict,
        "spur": spur,
        "representative_file": chart_info["representative_file"],
        "spectral_trace_panels": trace_info["panels"],
    }
    findings_path = os.path.join(args.out_dir, "findings.json")
    with open(findings_path, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=1)

    print(json.dumps(findings, indent=2))
    print(f"\nwrote charts + spectral_trace.png + {findings_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
