#!/usr/bin/env python3
"""Step 4 of the standard post-endurance-run routine -- assembles the MECHANICAL majority of
FINAL_REPORT.md automatically: every ANOVA table, every spectrum-scan chart (embedded with
real, working relative paths -- not the img/ redirect render_dossier.py uses for its own
HTML), the spur/hum resolution, and the full historical comparison table, all inline. No
"see anova_report.md" pointers for anything this script can compute itself.

WHY THIS EXISTS (Captain, 2026-09-26, after the 20260925_2010 run's FINAL_REPORT.md shipped
with broken/missing images and the ANOVA left in a separate file): "I'd like to have the
final report, with all the graphs and spectral data and including the anova report without
me pushing so much for it." A hand-authored report can always forget to embed something; a
script that recomputes and embeds everything mechanically cannot forget, by construction.

Recomputes the ANOVA (parse + match + two_way_anova_no_replication) directly from the two
ALL.TXT files via anova_common, the same functions endurance_anova_wsjtx.py and
render_dossier.py both already call (HK-034: one source of truth, never a second markdown-
scraping copy of the same logic).

This script does NOT write the QA narrative -- the run-health read, any cross-run finding
worth a ruling, and the overall verdict need human judgement, not a template, and a
templated verdict would be worse than an honest gap. It writes clearly-marked
"**[ QA: fill in ... ]**" placeholders for those instead, so what's missing is visibly a TODO
in the rendered output, never silently absent.

Prerequisites (run first, same as render_dossier.py's own):
    1. endurance_anova_wsjtx.py  -- writes anova_report.md/.html/.meta.json + the 6
                                     anova_report_*.png charts into --run-dir.
    2. spectrum_scan.py          -- writes --out-json (usually <run-dir>/spectrum_scan.json).
    3. spectrum_scan_report.py   -- writes findings.json + the 4 spectrum_scan_*.png charts
                                     + spectral_trace.png into --run-dir.

Usage:
    python compose_final_report.py --run-dir <gathered-dir> --corpus-dir <supervisor-corpus-dir> \\
        --title "<run label>" --purpose "<one-sentence why this run exists>" \\
        --out <run-dir>/FINAL_REPORT.md
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anova_common as ac  # noqa: E402


def fmt(v, spec="{}"):
    if v is None or (isinstance(v, float) and v != v):
        return "not recorded"
    try:
        return spec.format(v)
    except (ValueError, TypeError):
        return str(v)


def read_health(corpus_dir: str | None) -> dict:
    """Mechanical facts from the supervisor's own record -- state.json/heartbeat.json/
    supervisor.log -- never hand-typed. Returns an all-"not recorded" dict if corpus_dir
    wasn't given or the files aren't there (a run gathered by hand, or a corpus dir the
    caller didn't have on this machine) -- degrades to a visible gap, not a guess."""
    out = {"phase": "not recorded", "consecutive_restarts": "not recorded",
           "captureRestartCount": "not recorded", "watchdogRestartCount": "not recorded",
           "orphan_check": "not recorded", "precheck_all_pass": "not recorded"}
    if not corpus_dir or not os.path.isdir(corpus_dir):
        return out
    state_p = os.path.join(corpus_dir, "state.json")
    if os.path.isfile(state_p):
        out["phase"] = json.load(open(state_p, encoding="utf-8")).get("phase", "not recorded")
    hb_p = os.path.join(corpus_dir, "heartbeat.json")
    if os.path.isfile(hb_p):
        hb = json.load(open(hb_p, encoding="utf-8"))
        for k in ("consecutive_restarts", "captureRestartCount", "watchdogRestartCount"):
            if k in hb:
                out[k] = hb[k]
    log_p = os.path.join(corpus_dir, "supervisor.log")
    if os.path.isfile(log_p):
        text = open(log_p, encoding="utf-8", errors="replace").read()
        out["orphan_check"] = "clean" if "HK-019 orphan check: clean" in text else (
            "ORPHAN(S) LEFT -- see supervisor.log" if "HK-019" in text else "not recorded")
        for line in text.splitlines():
            if line.strip().startswith(("20", "PRECHECK")) and "PRECHECK" in line:
                out["precheck_all_pass"] = '"all_pass": true' in line
    return out


def build(args) -> str:
    run_dir = os.path.abspath(args.run_dir)
    owsfz_txt = os.path.join(run_dir, "owsfz", "ALL.TXT")
    wsjtx_txt = os.path.join(run_dir, "wsjt-x", "ALL.TXT")
    meta_path = os.path.join(run_dir, "anova_report.meta.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.isfile(meta_path) else {}

    a_rows = ac.parse_all_txt(owsfz_txt)
    b_rows = ac.parse_all_txt(wsjtx_txt)
    gate_a = ac.compute_grid_gate(a_rows)
    gate_b = ac.compute_grid_gate(b_rows)
    pairs = ac.match_pairs(a_rows, b_rows)
    n_a, n_b, n_m = len(a_rows), len(b_rows), len(pairs)

    responses = {}
    for resp in ac.RESPONSES:
        tuples = ac.response_tuples(pairs, resp["key"])
        stats = ac.two_way_anova_no_replication(tuples) if len(tuples) >= 2 else None
        responses[resp["key"]] = (resp, stats)

    scan_json = args.scan_json or os.path.join(run_dir, "spectrum_scan.json")
    findings_json = args.findings_json or os.path.join(run_dir, "findings.json")
    scan = json.load(open(scan_json, encoding="utf-8"))["summary"] if os.path.isfile(scan_json) else {}
    findings = json.load(open(findings_json, encoding="utf-8")) if os.path.isfile(findings_json) else {}
    dq = findings.get("data_quality", {})
    hum = findings.get("hum", {})
    spur = findings.get("spur", {})

    here = os.path.dirname(os.path.abspath(__file__))
    hist = ac.scan_historical_runs(here)
    comparable_hist = [h for h in hist if h.get("reference") == "live_wsjtx"
                        and h.get("band") == meta.get("band") and h.get("nhard") == meta.get("nhard")]

    health = read_health(args.corpus_dir)

    L = []
    L.append(f"# {args.title} -- FINAL REPORT\n")
    L.append(f"**Window (UTC):** `{meta.get('date', 'not recorded')}`, "
              f"{fmt(meta.get('hours'))}h -- see Section 1 for the mechanical start/end.  ")
    L.append(f"**Build:** `{meta.get('build_branch', 'not recorded')}`@"
              f"`{str(meta.get('build_commit', 'not recorded'))[:12]}`, "
              f"shim `{meta.get('shim', 'not recorded')}`, "
              f"DLL SHA256 `{str(meta.get('dll_sha256', 'not recorded'))[:8]}…`, "
              f"`osd_nhard_max={meta.get('nhard', 'not recorded')}`  ")
    L.append(f"**Radio chain:** {meta.get('radio_chain', 'not recorded')}  ")
    L.append("**Purpose:** **[ QA: fill in -- why this run exists, what question it answers ]**  ")
    L.append(f"**Generated:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} (`date -u`, HK-017)\n")
    L.append("---\n")

    # ---------------------------------------------------------------- Section 1: run health
    L.append("## 1. Run completion & health\n")
    L.append(f"- Supervisor phase: `{health['phase']}`. PRECHECK `all_pass`: "
              f"`{health['precheck_all_pass']}`. HK-019 orphan check: **{health['orphan_check']}**.")
    L.append(f"- Final heartbeat: `consecutive_restarts`={health['consecutive_restarts']}, "
              f"`captureRestartCount`={health['captureRestartCount']}, "
              f"`watchdogRestartCount`={health['watchdogRestartCount']}.")
    L.append(f"- Decode counts: OpenWSFZ {n_a:,}; WSJT-X (reference) {n_b:,}; matched {n_m:,}.")
    L.append("- **[ QA: fill in -- anything about this run's health worth a human note "
              "(e.g. an out-of-band event during the window) ]**\n")

    # ---------------------------------------------------------------- Section 2: spectrum scan
    L.append("## 2. Spectrum anomaly scan\n")
    if scan:
        L.append(f"**Method:** every one of the {scan.get('n_files', 0):,} cycle WAVs in "
                  "`owsfz/wav/` read in full, no subsampling (`spectrum_scan.py`, this directory; "
                  "full results `spectrum_scan.json`).\n")
        L.append("| Check | Result |")
        L.append("|---|---|")
        L.append(f"| Files read / errors | {scan.get('n_files', 0):,} / "
                  f"{scan.get('n_files', 0) - scan.get('n_errors', 0):,} ok, "
                  f"**{scan.get('n_errors', 0)} errors** |")
        L.append(f"| Format consistency | {'100% consistent' if scan.get('format_consistent') else 'INCONSISTENT -- review'} |")
        L.append(f"| Clipping (samples >= 32760) | **{scan.get('clipping_file_count', 0)} file(s)** |")
        L.append(f"| Dropouts / hot spikes | {scan.get('silent_file_count', 0)} / {scan.get('hot_file_count', 0)} files |")
        L.append(f"| Level stability | median {fmt(scan.get('dbfs_median'), '{:.2f}')} dBFS, "
                  f"MAD {fmt(scan.get('dbfs_mad'), '{:.2f}')} dB, "
                  f"range {fmt(scan.get('dbfs_min'), '{:.2f}')} to {fmt(scan.get('dbfs_max'), '{:.2f}')} dBFS |")
        L.append(f"| Sub-passband hum (45-125Hz) | {fmt(scan.get('hum2_over_floor_median_db'), '{:.2f}')} dB over floor (median) |")
        L.append(f"| In-band >40dB spur candidates | {scan.get('spur_file_count', 0):,} files |\n")
        L.append("### Level over the run\n")
        L.append("![Capture level over the run](spectrum_scan_level_timeseries.png)\n")
        if findings.get("representative_file"):
            L.append("### Representative single-cycle spectrum\n")
            L.append("![Representative single-cycle spectrum with analysis bands annotated](spectrum_scan_example_spectrum.png)\n")
            L.append(f"Representative file: `{findings['representative_file']}`.\n")
        L.append("### Sub-passband hum\n")
        L.append("![Sub-passband hum band over the run](spectrum_scan_hum_timeseries.png)\n")
        L.append(f"**Hum verdict:** {hum.get('verdict', 'not recorded')}\n")
        L.append("### In-band spur candidates\n")
        L.append("![In-band spur candidate frequency spread](spectrum_scan_spur_histogram.png)\n")
        spur_line = f"**Spur verdict:** {spur.get('verdict', 'not recorded')}"
        if spur.get("ran"):
            spur_line += (f" -- {spur.get('n_hits')} decodes, {spur.get('distinct_messages')} "
                           f"distinct messages at {fmt(spur.get('top_freq_hz'), '{:.0f}')} Hz, "
                           f"SNR range [{spur.get('snr_min')}, {spur.get('snr_max')}].")
        L.append(spur_line + "\n")
        if os.path.isfile(os.path.join(run_dir, "spectral_trace.png")):
            L.append("### Welch PSD / STFT comparison\n")
            panels = ", ".join(findings.get("spectral_trace_panels", []))
            L.append("![Welch PSD and STFT spectrogram comparison](spectral_trace.png)\n")
            L.append(f"Panels: {panels}.\n")
    else:
        L.append("**[ spectrum_scan.json / findings.json not found in this run-dir -- "
                  "run spectrum_scan.py + spectrum_scan_report.py first ]**\n")

    # ---------------------------------------------------------------- Section 3: ANOVA
    L.append(f"## 3. Matched-decode ANOVA (OpenWSFZ vs {meta.get('reference', 'reference')}, "
              f"n={n_m:,} pairs)\n")
    L.append("Recomputed directly from both `ALL.TXT` files via `anova_common.py` -- the same "
              "module `endurance_anova_wsjtx.py` and `render_dossier.py` both call -- not parsed "
              "from rendered markdown.\n")
    L.append("### Grid-alignment gate (per HK-021, 2026-08-02 correction)\n")
    L.append("| appraiser | unique ts | on-grid | G | row | verdict |")
    L.append("|---|---:|---:|---:|---|---|")
    L.append(f"| OpenWSFZ | {gate_a['n_unique_ts']:,} | {gate_a['n_on_grid']:,} | "
              f"{gate_a['g']:.4f} | ROW {gate_a['row']} | {gate_a['verdict']} |")
    L.append(f"| Reference | {gate_b['n_unique_ts']:,} | {gate_b['n_on_grid']:,} | "
              f"{gate_b['g']:.4f} | ROW {gate_b['row']} | {gate_b['verdict']} |\n")
    L.append("### Decode coverage\n")
    L.append(f"- OpenWSFZ decoded **{n_a:,}** messages; reference decoded **{n_b:,}**.")
    L.append(f"- **{n_m:,}** matched ({n_m/n_a*100 if n_a else 0:.1f}% of OpenWSFZ, "
              f"{n_m/n_b*100 if n_b else 0:.1f}% of reference).")
    L.append(f"- OpenWSFZ-only: **{n_a-n_m:,}** ({(n_a-n_m)/n_a*100 if n_a else 0:.1f}%). "
              f"Reference-only: **{n_b-n_m:,}** ({(n_b-n_m)/n_b*100 if n_b else 0:.1f}%).\n")

    chart_stems = {"snr": ("SNR (dB)", "anova_report_snr"), "dt": ("DT (time offset) (s)", "anova_report_dt"),
                    "freq_hz": ("Frequency offset (Hz)", "anova_report_freq_hz")}
    for key, (resp, stats) in responses.items():
        label, stem = chart_stems[key]
        L.append(f"### {label}\n")
        if stats is None:
            L.append("Too few matched pairs to compute.\n")
            continue
        L.append(f"![Matched-decode {resp['label']} scatter]({stem}_scatter.png)")
        L.append(f"![Per-Part residual vs reference {resp['label']}]({stem}_residual.png)\n")
        L.append("| Source | SS | df | MS | F | P |")
        L.append("|---|---:|---:|---:|---:|---:|")
        s = stats
        L.append(f"| Part | {s['ss_part']:.4f} | {s['df_part']} | {s['ms_part']:.4f} | "
                  f"{s['f_part']:.3f} | {s['p_part']:.4f} |")
        L.append(f"| Appraiser | {s['ss_appraiser']:.4f} | {s['df_appraiser']} | "
                  f"{s['ms_appraiser']:.4f} | {s['f_appraiser']:.3f} | {s['p_appraiser']:.4f} |")
        L.append(f"| Residual (confounded with interaction, n=1/cell) | {s['ss_error']:.4f} | "
                  f"{s['df_error']} | {s['ms_error']:.4f} | | |")
        L.append(f"| Total | {s['ss_part']+s['ss_appraiser']+s['ss_error']:.4f} | {s['df_total']} | | | |\n")
        L.append(f"Appraiser means ({label}): OpenWSFZ **{s['appraiser_means']['a']:.4f} {resp['unit']}**, "
                  f"reference **{s['appraiser_means']['b']:.4f} {resp['unit']}**, "
                  f"grand mean {s['grand_mean']:.4f} {resp['unit']}.\n")

    L.append("### Caveat (structural, not a defect)\n")
    L.append("With one observation per Part x Appraiser cell, the interaction term and the "
              "residual/error term are mathematically confounded for every response above -- "
              "the standard property of an unreplicated factorial design. Cross-run comparison "
              "and interpretation of these numbers is Architect/Captain/QA-judgement territory, "
              "not this script's -- see Section 4.\n")

    # ---------------------------------------------------------------- Section 4: historical trend
    L.append("## 4. HK-036 Section 4 read (historical trend)\n")
    L.append("| Date | Band | Hours | nhard | Ref. | Radio chain | G | Matched pairs | "
              "Matched % of ref | OWS-only % | SNR gap (dB) | DT gap (s) |")
    L.append("|---|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|")
    for h in hist:
        is_this = os.path.normpath(str(h.get("run_dir", ""))) == run_dir
        date_cell = f"**{h.get('date')} (this run)**" if is_this else h.get("date", "not recorded")
        L.append(f"| {date_cell} | {h.get('band','not recorded')} | {fmt(h.get('hours'))} | "
                  f"{h.get('nhard','not recorded')} | {h.get('reference','not recorded')} | "
                  f"{h.get('radio_chain','not recorded')} | {fmt(h.get('grid_gate_g'),'{:.4f}')} | "
                  f"{fmt(h.get('n_pairs'),'{:,}')} | {fmt(h.get('matched_pct_of_ref'),'{:.1f}')} | "
                  f"{fmt(h.get('ows_only_pct'),'{:.1f}')} | {fmt(h.get('snr_gap_db'),'{:.3f}')} | "
                  f"{fmt(h.get('dt_gap_s'),'{:+.4f}')} |")
    L.append("")
    if len(comparable_hist) >= 2:
        prev, cur = comparable_hist[-2], comparable_hist[-1]
        d_snr = cur.get("snr_gap_db", float("nan")) - prev.get("snr_gap_db", float("nan"))
        L.append(f"**SNR gap moved {d_snr:+.3f} dB** vs. the immediately preceding comparable row "
                  f"(same band, same nhard, live reference). n={len(comparable_hist)} comparable "
                  "rows total for this band/nhard combination.\n")
    L.append("**[ QA: fill in -- is this movement worth a ruling, per any standing follow-up "
              "note? Say so explicitly (settled/flagged/noise) rather than leaving it as a bare "
              "number -- see MEMORY.md's retired-figures guard for the standing rule on citing "
              "any figure here without a qualifier once one exists.] **\n")

    # ---------------------------------------------------------------- Section 5: verdict
    L.append("## 5. Overall verdict\n")
    L.append("- **[ QA: fill in -- data quality verdict, one line ]**")
    L.append("- **[ QA: fill in -- this run's actual question and answer, one line ]**")
    L.append("- **[ QA: fill in -- adoption-gate / next-step implication, if any ]**\n")

    L.append("## Files in this directory\n")
    L.append("- `anova_report.md` / `.html` -- the standalone, script-generated original this "
              "section's content matches by construction (recomputed independently, not copied)")
    L.append("- `anova_report_{snr,dt,freq_hz}_{scatter,residual}.png` -- the 6 ANOVA charts, embedded above")
    L.append("- `spectrum_scan.py` / `spectrum_scan_report.py` -- the anomaly-scan scripts")
    L.append("- `spectrum_scan.json` / `findings.json` -- the scan's full results and mechanical verdicts")
    L.append("- `spectrum_scan_level_timeseries.png`, `spectrum_scan_hum_timeseries.png`, "
              "`spectrum_scan_spur_histogram.png`, `spectrum_scan_example_spectrum.png`, "
              "`spectral_trace.png` -- the spectral charts, embedded above")
    L.append("- `FINAL_REPORT_dossier.html` -- an auto-rendered HTML alternate view of Sections "
              "1-3 (does not carry Section 4/5's QA narrative)")
    L.append("- `owsfz/`, `wsjt-x/` -- gathered decode logs and WAVs\n")

    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, help="The *-gathered directory (owsfz/, wsjt-x/, anova_report.meta.json)")
    ap.add_argument("--corpus-dir", default=None,
                     help="The supervisor's own corpus dir (state.json/heartbeat.json/supervisor.log) "
                          "-- usually --run-dir with the -gathered suffix stripped. Omit if unavailable; "
                          "Section 1's mechanical health facts will read 'not recorded' instead of guessing.")
    ap.add_argument("--scan-json", default=None, help="Default: <run-dir>/spectrum_scan.json")
    ap.add_argument("--findings-json", default=None, help="Default: <run-dir>/findings.json")
    ap.add_argument("--title", required=True, help="e.g. '12h endurance run'")
    ap.add_argument("--out", default=None, help="Default: <run-dir>/FINAL_REPORT.md")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.abspath(a.run_dir), "FINAL_REPORT.md")
    md = build(a)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {out}")
    print("\n*** Fill in every '[ QA: ... ]' placeholder before calling this report done. ***", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
