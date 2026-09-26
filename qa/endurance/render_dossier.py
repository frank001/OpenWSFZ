#!/usr/bin/env python3
"""Step 3 of the standard post-endurance-run routine (Captain's instruction, 2026-09-24):
assembles the full HTML dossier -- every ANOVA section plus the spectrum-scan + spectral-
trace sections from steps 1-2 -- ready for Claude to publish with the Artifact tool.

Prerequisites (run first):
    1. python endurance_anova_wsjtx.py ...   -- the standard report; writes anova_report.md/
                                                 .html/.meta.json + the 6 anova_report_*.png
                                                 charts into --run-dir. This script reads
                                                 that meta.json AND recomputes the same ANOVA
                                                 stats directly from the two ALL.TXTs (via
                                                 anova_common, the exact same functions that
                                                 script itself calls) rather than parsing the
                                                 rendered markdown -- guarantees the numbers in
                                                 this dossier match the standard report by
                                                 construction, and needs no markdown scraping.
    2. python spectrum_scan.py --wav-dir <run-dir>/owsfz/wav --out-json <run-dir>/spectrum_scan.json
    3. python spectrum_scan_report.py --scan-json <run-dir>/spectrum_scan.json \\
           --wav-dir <run-dir>/owsfz/wav --all-txt <run-dir>/owsfz/ALL.TXT \\
           --out-dir <run-dir> [--control-scan-json <prior-run>/spectrum_scan.json]

Then:
    python render_dossier.py --run-dir <run-dir>

Design note: this recomputes the ANOVA (parse + match + two_way_anova_no_replication) from
the two ALL.TXT files rather than parsing anova_report.md's text, precisely to avoid a
second, drifting copy of that parsing logic (HK-034 spirit: single source of truth is the
imported anova_common module, not a regex against its own rendered output). The historical
Section 4/5 table is built from anova_common.scan_historical_runs()'s own structured
dictionaries for the same reason -- never re-derived, never hand-copied.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anova_common as ac  # noqa: E402


def esc(s) -> str:
    if s is None:
        return "&mdash;"
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(v, spec="{:.3f}"):
    if v is None or (isinstance(v, float) and v != v):
        return "not recorded"
    if isinstance(v, str):
        return v
    try:
        return spec.format(v)
    except (ValueError, TypeError):
        return str(v)


CSS = """
  :root{
    --ink:#1b1712; --panel:#24201a; --panel-2:#2c2620;
    --cream:#ece5d8; --dim:#a89984; --hair:#3c3428;
    --amber:#d99a3d; --amber-dim:#8a6432;
    --alert:#c1503f; --alert-dim:#5c2f28;
    --ok:#7c9a6c; --ok-dim:#3f5233;
    --info:#7a93ad;
    --mono:'JetBrains Mono', ui-monospace, 'SF Mono', Consolas, monospace;
    --sans:'IBM Plex Sans', system-ui, sans-serif;
  }
  @media (prefers-color-scheme: light){
    :root:not([data-theme="light"]){
      --ink:#f4efe4; --panel:#fffdf8; --panel-2:#f7f1e4;
      --cream:#241f18; --dim:#6b6154; --hair:#ddd2bd;
      --amber:#a9661a; --amber-dim:#c9a06a;
      --alert:#a33d2d; --alert-dim:#e6c3ba;
      --ok:#4f7241; --ok-dim:#cddcc4;
      --info:#3d5978;
    }
  }
  :root[data-theme="light"]{
      --ink:#f4efe4; --panel:#fffdf8; --panel-2:#f7f1e4;
      --cream:#241f18; --dim:#6b6154; --hair:#ddd2bd;
      --amber:#a9661a; --amber-dim:#c9a06a;
      --alert:#a33d2d; --alert-dim:#e6c3ba;
      --ok:#4f7241; --ok-dim:#cddcc4;
      --info:#3d5978;
  }
  :root[data-theme="dark"]{
      --ink:#1b1712; --panel:#24201a; --panel-2:#2c2620;
      --cream:#ece5d8; --dim:#a89984; --hair:#3c3428;
      --amber:#d99a3d; --amber-dim:#8a6432;
      --alert:#c1503f; --alert-dim:#5c2f28;
      --ok:#7c9a6c; --ok-dim:#3f5233;
      --info:#7a93ad;
  }
  body{ background:var(--ink); color:var(--cream); font-family:var(--sans); padding-inline:16px; }
  .wrap{ max-width:960px; margin:0 auto; padding-block:40px 72px; }
  .eyebrow{ font-family:var(--mono); font-size:11.5px; letter-spacing:.12em; text-transform:uppercase;
            color:var(--amber); margin:0 0 10px; }
  h1{ font-family:var(--mono); font-weight:700; font-size:clamp(26px,4.4vw,36px);
      margin:0 0 8px; letter-spacing:-.01em; line-height:1.15; }
  .dek{ color:var(--dim); font-size:15.5px; line-height:1.6; max-width:70ch; margin:0 0 6px; }
  .meta{ font-family:var(--mono); font-size:12px; color:var(--dim); border-top:1px solid var(--hair);
         border-bottom:1px solid var(--hair); padding-block:10px; margin:22px 0 30px;
         display:flex; flex-wrap:wrap; gap:6px 22px; }
  .meta b{ color:var(--cream); font-weight:600; }
  nav.toc{ display:flex; flex-wrap:wrap; gap:8px; margin:0 0 36px; }
  nav.toc a{ font-family:var(--mono); font-size:11.5px; color:var(--dim); text-decoration:none;
             border:1px solid var(--hair); border-radius:20px; padding:6px 13px; background:var(--panel); }
  nav.toc a:hover{ color:var(--amber); border-color:var(--amber-dim); }
  .verdicts{ display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--hair);
             border:1px solid var(--hair); margin-bottom:40px; border-radius:4px; overflow:hidden; }
  .verdict{ background:var(--panel); padding:20px 18px; }
  .verdict .arm{ font-family:var(--mono); font-size:10.5px; text-transform:uppercase; letter-spacing:.08em;
                 color:var(--dim); margin-bottom:10px; }
  .verdict .row{ font-family:var(--mono); font-size:22px; font-weight:700; line-height:1.2; margin-bottom:8px; }
  .verdict .row.ok{ color:var(--ok); } .verdict .row.alert{ color:var(--alert); } .verdict .row.info{ color:var(--info); }
  .verdict .note{ font-size:12.5px; color:var(--dim); line-height:1.5; }
  section{ margin-bottom:56px; }
  .section-head{ display:flex; align-items:baseline; justify-content:space-between; gap:12px;
                 border-bottom:1px solid var(--hair); padding-bottom:10px; margin-bottom:22px; flex-wrap:wrap; }
  h2{ font-family:var(--mono); font-size:15px; text-transform:uppercase; letter-spacing:.06em;
      color:var(--amber); margin:0; scroll-margin-top:16px; }
  .section-tag{ font-family:var(--mono); font-size:11px; padding:3px 10px; border-radius:20px; white-space:nowrap; }
  .tag-ok{ background:var(--ok-dim); color:var(--ok); }
  .tag-alert{ background:var(--alert-dim); color:var(--alert); }
  .tag-info{ background:var(--panel-2); color:var(--info); border:1px solid var(--hair); }
  h3{ font-family:var(--mono); font-size:12.5px; text-transform:uppercase; letter-spacing:.05em;
      color:var(--dim); margin:26px 0 12px; }
  p{ font-size:14.5px; line-height:1.65; max-width:72ch; margin:0 0 14px; }
  p.tight{ max-width:none; }
  code{ font-family:var(--mono); font-size:0.92em; background:var(--panel-2); padding:1px 5px; border-radius:3px; }
  table{ width:100%; border-collapse:collapse; font-size:13px; margin:0 0 22px; }
  th, td{ text-align:right; padding:7px 10px; border-bottom:1px solid var(--hair); font-variant-numeric:tabular-nums; }
  th:first-child, td:first-child{ text-align:left; }
  th{ font-family:var(--mono); font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--dim);
      font-weight:500; border-bottom:1px solid var(--amber-dim); }
  tr:last-child td{ border-bottom:none; }
  .tbl-wrap{ overflow-x:auto; margin-bottom:22px; }
  td.hl{ color:var(--amber); font-weight:600; }
  ol.fn{ font-family:var(--mono); font-size:11.5px; color:var(--dim); line-height:1.8; padding-left:20px; margin:0 0 24px; }
  .grid2{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  figure{ margin:0 0 22px; background:var(--panel); border:1px solid var(--hair); border-radius:4px;
          padding:12px 12px 14px; }
  figure img{ width:100%; display:block; border-radius:2px; background:#0d0b08; }
  figcaption{ font-size:12px; color:var(--dim); margin-top:9px; line-height:1.5; }
  figcaption b{ color:var(--cream); }
  .callout{ padding:14px 16px; border-radius:4px; border:1px solid var(--hair); background:var(--panel);
            border-left:3px solid var(--amber); font-size:13.5px; line-height:1.6; margin:0 0 20px; }
  .callout.ok{ border-left-color:var(--ok); }
  .callout.alert{ border-left-color:var(--alert); }
  .callout b{ color:var(--cream); }
  .pill-row{ display:flex; flex-wrap:wrap; gap:8px; margin:0 0 20px; }
  .pill{ font-family:var(--mono); font-size:11px; padding:5px 11px; border-radius:20px; background:var(--panel-2);
         border:1px solid var(--hair); color:var(--dim); }
  .pill b{ color:var(--cream); }
  .pill.hit{ color:var(--ok); border-color:var(--ok-dim); }
  .pill.miss{ color:var(--alert); border-color:var(--alert-dim); }
  .pill.watch{ color:var(--info); border-color:var(--hair); }
  footer{ border-top:1px solid var(--hair); padding-top:18px; font-family:var(--mono); font-size:11px;
          color:var(--dim); line-height:1.8; }
  footer a{ color:var(--dim); }
  @media (max-width:720px){ .verdicts{ grid-template-columns:1fr; } .grid2{ grid-template-columns:1fr; } }
"""


def anova_table_html(stats: dict) -> str:
    def row(label, ss, df, ms, f_, p_):
        return (f"<tr><td>{label}</td><td>{fmt(ss)}</td><td>{fmt(df,'{:d}')}</td>"
                f"<td>{fmt(ms)}</td><td>{fmt(f_)}</td><td>{fmt(p_,'{:.4f}')}</td></tr>")
    return (
        '<div class="tbl-wrap"><table><thead><tr><th>Source</th><th>SS</th><th>df</th>'
        "<th>MS</th><th>F</th><th>P</th></tr></thead><tbody>"
        + row("Part", stats["ss_part"], stats["df_part"], stats["ms_part"], stats["f_part"], stats["p_part"])
        + row("Appraiser", stats["ss_appraiser"], stats["df_appraiser"], stats["ms_appraiser"],
              stats["f_appraiser"], stats["p_appraiser"])
        + row("Residual (confounded w/ interaction, n=1/cell)", stats["ss_error"], stats["df_error"],
              stats["ms_error"], None, None)
        + row("Total", stats["ss_total"], stats["df_total"], None, None, None)
        + "</tbody></table></div>"
    )


_IMG_SOURCES = {
    # dossier-relative name (what every <img src="img/...."> tag below actually references)
    # -> source filename this run's own prior steps (spectrum_scan_report.py,
    # endurance_anova_wsjtx.py) already wrote directly in run_dir.
    "level_timeseries.png": "spectrum_scan_level_timeseries.png",
    "example_spectrum.png": "spectrum_scan_example_spectrum.png",
    "hum_timeseries.png": "spectrum_scan_hum_timeseries.png",
    "spur_histogram.png": "spectrum_scan_spur_histogram.png",
    "spectral_trace.png": "spectral_trace.png",
    "anova_snr_scatter.png": "anova_report_snr_scatter.png",
    "anova_snr_residual.png": "anova_report_snr_residual.png",
    "anova_dt_scatter.png": "anova_report_dt_scatter.png",
    "anova_dt_residual.png": "anova_report_dt_residual.png",
    "anova_freq_scatter.png": "anova_report_freq_hz_scatter.png",
    "anova_freq_residual.png": "anova_report_freq_hz_residual.png",
}


def _populate_img_dir(run_dir: str) -> None:
    """Every <img src="img/...."> tag below assumes an img/ subdirectory next to the
    rendered HTML -- found live, 2026-09-26 (Captain, reading a rendered dossier with every
    image broken): this function never existed, so img/ was never created and the dossier
    was broken on EVERY run that ever used it, including the one it was first built for
    (2026-09-24), not just this one. Best-effort per file: a missing source is a real gap
    worth seeing broken in the HTML (a silently-skipped image is not more honest than a
    broken one), so this only warns, it does not raise."""
    import shutil
    img_dir = os.path.join(run_dir, "img")
    os.makedirs(img_dir, exist_ok=True)
    for dest_name, src_name in _IMG_SOURCES.items():
        src = os.path.join(run_dir, src_name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(img_dir, dest_name))
        else:
            print(f"[WARN] _populate_img_dir: source {src} not found -- "
                  f"img/{dest_name} will be a broken image in the rendered HTML",
                  file=sys.stderr)


def build(args) -> str:
    run_dir = os.path.abspath(args.run_dir)
    _populate_img_dir(run_dir)
    owsfz_txt = os.path.join(run_dir, "owsfz", "ALL.TXT")
    wsjtx_txt = os.path.join(run_dir, "wsjt-x", "ALL.TXT")
    meta_path = os.path.join(run_dir, "anova_report.meta.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.isfile(meta_path) else {}

    a_rows = ac.parse_all_txt(owsfz_txt)
    b_rows = ac.parse_all_txt(wsjtx_txt)

    # Window start/end shown in the meta bar: derived MECHANICALLY from the decode logs'
    # own cycle timestamps (HK-017 spirit -- never hand-typed), not from meta.json's `date`
    # field alone, which is date-only and was found live (2026-09-24, Captain) to leave a
    # reader with no way to see what time the run actually started or ended.
    all_ts = [t for t in (ac.parse_cycle_ts(r["ts"]) for r in a_rows + b_rows) if t is not None]
    if all_ts:
        window_start_dt, window_end_dt = min(all_ts), max(all_ts)
        window_start_s = window_start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        # +15s: each ts is a cycle's START; the window runs to the END of the last cycle.
        window_end_s = (window_end_dt + datetime.timedelta(seconds=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        window_start_s = window_end_s = "not recorded"

    gate_a = ac.compute_grid_gate(a_rows)
    gate_b = ac.compute_grid_gate(b_rows)
    pairs = ac.match_pairs(a_rows, b_rows)
    n_a, n_b, n_m = len(a_rows), len(b_rows), len(pairs)

    responses = {}
    for resp in ac.RESPONSES:
        tuples = ac.response_tuples(pairs, resp["key"])
        stats = ac.two_way_anova_no_replication(tuples) if len(tuples) >= 2 else None
        responses[resp["key"]] = (resp, stats)

    scan = json.load(open(args.scan_json, encoding="utf-8"))["summary"]
    findings = json.load(open(args.findings_json, encoding="utf-8"))

    here = os.path.dirname(os.path.abspath(__file__))
    hist = ac.scan_historical_runs(here)

    dq = findings["data_quality"]
    hum = findings["hum"]
    spur = findings["spur"]

    dq_ok = dq["ok"]
    spur_resolved = spur.get("verdict", "").startswith("RESOLVED") or not spur.get("material", False)
    spur_open = spur.get("verdict", "").startswith("OPEN")
    hum_ok = "diverges" not in hum.get("verdict", "")

    # -- Verdict cards ---------------------------------------------------------------------
    v1_cls, v1_row = ("ok", "CLEAN") if dq_ok else ("alert", "ISSUES FOUND")
    v2_cls, v2_row = ("alert", "OPEN") if spur_open or not hum_ok else ("ok", "NONE FOUND")
    comparable_hist = [h for h in hist if h.get("reference") == "live_wsjtx"
                        and h.get("band") == meta.get("band") and h.get("nhard") == meta.get("nhard")]

    body = []
    body.append(f"""<title>{esc(args.title)}</title>
<style>{CSS}</style>
<div class="wrap">
  <p class="eyebrow">OpenWSFZ &middot; QA final report &middot; endurance run</p>
  <h1>{esc(args.title)}</h1>
  <p class="dek">{esc(args.purpose)}</p>
  <div class="meta">
    <span>Window <b>{esc(window_start_s)} &rarr; {esc(window_end_s)}</b> ({esc(meta.get('hours','not recorded'))}h)</span>
    <span>Band <b>{esc(meta.get('band'))}</b></span>
    <span>Build <b>{esc(meta.get('build_branch'))} {esc(str(meta.get('build_commit',''))[:8])}</b>
      (DLL <b>{esc(str(meta.get('dll_sha256',''))[:8])}&hellip;</b>, shim <b>{esc(meta.get('shim'))}</b>, nhard <b>{esc(meta.get('nhard'))}</b>)</span>
    <span>Chain <b>{esc(meta.get('radio_chain'))}</b></span>
    <span>REF <b>{esc(meta.get('reference'))}</b></span>
  </div>
  <nav class="toc">
    <a href="#verdicts">Verdicts</a><a href="#health">1&middot;Run health</a>
    <a href="#spectrum">2&middot;Spectrum scan</a><a href="#anova">3&middot;ANOVA</a>
    <a href="#spectral">4&middot;Spectral trace</a><a href="#trend">5&middot;Historical trend</a>
    <a href="#provenance">Provenance</a>
  </nav>
  <div class="verdicts" id="verdicts">
    <div class="verdict"><div class="arm">&sect;1&#8211;2 Run health + spectrum scan</div>
      <div class="row {v1_cls}">{v1_row}</div>
      <div class="note">{dq['n_errors']} read errors, {dq['clipping_file_count']} clipped,
        {dq['silent_file_count']} dropouts, {dq['hot_file_count']} hot spikes across
        {dq['n_files']} cycles. Level {fmt(dq['dbfs_median'],'{:.2f}')} &plusmn; {fmt(dq['dbfs_mad'],'{:.2f}')} dBFS (MAD).</div></div>
    <div class="verdict"><div class="arm">&sect;2, &sect;4 Spectral anomaly hunt</div>
      <div class="row {v2_cls}">{'OPEN ITEM' if v2_cls=='alert' else 'NONE FOUND'}</div>
      <div class="note">Hum: {esc(hum['verdict'])}. Spur: {esc(spur.get('verdict','n/a'))}</div></div>
    <div class="verdict"><div class="arm">&sect;5 HK-036 Section 4 &middot; chain effect</div>
      <div class="row info">{'n=' + str(len(comparable_hist))+' comparable' if comparable_hist else 'no comparable rows yet'}</div>
      <div class="note">SNR gap this run: {fmt(meta.get('snr_gap_db'),'{:+.3f}')} dB. See &sect;5 for the
        full historical series before reading any movement as a chain effect.</div></div>
  </div>""")

    # -- Section 1: run health --------------------------------------------------------------
    body.append(f"""
  <section id="health">
    <div class="section-head"><h2>1&nbsp;&middot;&nbsp;Run completion &amp; health</h2>
      <span class="section-tag {'tag-ok' if dq_ok else 'tag-alert'}">{'clean' if dq_ok else 'review needed'}</span></div>
    <div class="tbl-wrap"><table><thead><tr><th>Decode counts</th><th>OpenWSFZ</th><th>Reference</th><th>Matched</th></tr></thead>
      <tbody><tr><td>this window</td><td>{n_a:,}</td><td>{n_b:,}</td><td>{n_m:,}</td></tr></tbody></table></div>
  </section>""")

    # -- Section 2: spectrum scan ------------------------------------------------------------
    hum_cls = "ok" if hum_ok else "alert"
    spur_cls = "ok" if not spur_open else "alert"
    body.append(f"""
  <section id="spectrum">
    <div class="section-head"><h2>2&nbsp;&middot;&nbsp;Spectrum anomaly scan</h2>
      <span class="section-tag tag-info">run before the ANOVA comparison, per standing instruction</span></div>
    <p>Every cycle WAV in <code>owsfz/wav/</code> read in full, no subsampling. Script:
      <code>spectrum_scan.py</code> + <code>spectrum_scan_report.py</code>.</p>
    <div class="tbl-wrap"><table><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>
      <tr><td>Files read / errors</td><td>{scan['n_files']:,} / {scan['n_files']-scan['n_errors']:,} ok, {scan['n_errors']} errors</td></tr>
      <tr><td>Format consistency</td><td>{'100% consistent' if scan['format_consistent'] else 'INCONSISTENT -- review'}</td></tr>
      <tr><td>Clipping</td><td>{scan['clipping_file_count']} files</td></tr>
      <tr><td>Dropouts / hot spikes</td><td>{scan['silent_file_count']} / {scan['hot_file_count']} files</td></tr>
      <tr><td>Level</td><td>median {fmt(scan['dbfs_median'],'{:.2f}')} dBFS, MAD {fmt(scan['dbfs_mad'],'{:.2f}')} dB</td></tr>
      <tr><td>Sub-passband hum (45-125Hz)</td><td>{fmt(scan['hum2_over_floor_median_db'],'{:.2f}')} dB over floor (median)</td></tr>
      <tr><td>In-band &gt;40dB spur candidates</td><td>{scan['spur_file_count']:,} files</td></tr>
    </tbody></table></div>
    <h3>Level over the run</h3>
    <figure><img src="img/level_timeseries.png" alt="Capture level over the run">
      <figcaption>Gain-step / dropout / drift check.</figcaption></figure>
    <h3>Representative single-cycle spectrum</h3>
    <figure><img src="img/example_spectrum.png" alt="Representative single-cycle spectrum with analysis bands annotated">
      <figcaption>Representative file: <code>{esc(findings['representative_file'])}</code>.</figcaption></figure>
    <h3>Sub-passband hum</h3>
    <figure><img src="img/hum_timeseries.png" alt="Sub-passband hum band over the run">
      <figcaption>{esc(hum['verdict'])}</figcaption></figure>
    <div class="callout {hum_cls}"><b>Hum verdict:</b> {esc(hum['verdict'])}</div>
    <h3>In-band spur candidates</h3>
    <figure><img src="img/spur_histogram.png" alt="In-band spur candidate frequency spread">
      <figcaption>Peak-frequency spread of >40dB-over-local-median candidates.</figcaption></figure>
    <div class="callout {spur_cls}"><b>Spur verdict:</b> {esc(spur.get('verdict','n/a'))}""")
    if spur.get("ran"):
        body.append(f""" &mdash; {spur['n_hits']} decodes, {spur['distinct_messages']} distinct
      messages at {fmt(spur['top_freq_hz'],'{:.0f}')}&nbsp;Hz, SNR range [{spur.get('snr_min')}, {spur.get('snr_max')}].""")
    body.append("</div>\n  </section>")

    # -- Section 3: full ANOVA ---------------------------------------------------------------
    body.append(f"""
  <section id="anova">
    <div class="section-head"><h2>3&nbsp;&middot;&nbsp;ANOVA &mdash; matched-decode metrics</h2>
      <span class="section-tag tag-info">recomputed directly from both ALL.TXT files</span></div>
    <p>Two-way ANOVA without replication over <b>{n_m:,}</b> matched pairs. Recomputed here via
      <code>anova_common.py</code> (the same module the standard report uses), not parsed from
      rendered markdown.</p>
    <h3>Grid-alignment gate</h3>
    <div class="tbl-wrap"><table><thead><tr><th>Appraiser</th><th>Unique ts</th><th>On-grid</th><th>G</th><th>Row</th><th>Verdict</th></tr></thead>
      <tbody>
        <tr><td>OpenWSFZ</td><td>{gate_a['n_unique_ts']:,}</td><td>{gate_a['n_on_grid']:,}</td><td class="hl">{gate_a['g']:.4f}</td><td>ROW {gate_a['row']}</td><td>{gate_a['verdict']}</td></tr>
        <tr><td>Reference</td><td>{gate_b['n_unique_ts']:,}</td><td>{gate_b['n_on_grid']:,}</td><td class="hl">{gate_b['g']:.4f}</td><td>ROW {gate_b['row']}</td><td>{gate_b['verdict']}</td></tr>
      </tbody></table></div>
    <h3>Decode coverage</h3>
    <div class="tbl-wrap"><table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>
      <tr><td>OpenWSFZ decodes</td><td>{n_a:,}</td></tr>
      <tr><td>Reference decodes</td><td>{n_b:,}</td></tr>
      <tr><td>Matched pairs</td><td class="hl">{n_m:,} ({n_m/n_a*100 if n_a else 0:.1f}% of OpenWSFZ, {n_m/n_b*100 if n_b else 0:.1f}% of reference)</td></tr>
    </tbody></table></div>""")

    chart_map = {"snr": "anova_snr", "dt": "anova_dt", "freq_hz": "anova_freq"}
    for key, (resp, stats) in responses.items():
        if stats is None:
            body.append(f"<h3>{esc(resp['label'])} ({esc(resp['unit'])})</h3><p>Too few matched pairs to compute.</p>")
            continue
        stem = chart_map[key]
        body.append(f"""
    <h3>{esc(resp['label'])} ({esc(resp['unit'])})</h3>
    {anova_table_html(stats)}
    <p class="tight">Appraiser means: OpenWSFZ <b>{stats['appraiser_means']['a']:.4f} {esc(resp['unit'])}</b>,
      Reference <b>{stats['appraiser_means']['b']:.4f} {esc(resp['unit'])}</b>,
      grand mean {stats['grand_mean']:.4f} {esc(resp['unit'])}.</p>
    <div class="grid2">
      <figure><img src="img/{stem}_scatter.png" alt="Matched-decode {esc(resp['label'])} scatter"><figcaption>n={n_m:,} pairs.</figcaption></figure>
      <figure><img src="img/{stem}_residual.png" alt="Per-Part {esc(resp['label'])} residual"><figcaption>Per-Part residual vs reference.</figcaption></figure>
    </div>""")

    body.append("""
    <p style="font-size:12.5px;color:var(--dim);"><b>Caveat (structural, not a defect):</b> with one
      observation per Part&times;Appraiser cell, the interaction term and the residual/error term are
      mathematically confounded for every response above -- the standard property of an unreplicated
      factorial design. Cross-run comparison and interpretation is Architect/Captain territory, not
      this pipeline's.</p>
  </section>""")

    # -- Section 4: spectral trace ------------------------------------------------------------
    body.append(f"""
  <section id="spectral">
    <div class="section-head"><h2>4&nbsp;&middot;&nbsp;Spectral trace</h2>
      <span class="section-tag {'tag-ok' if not spur_open else 'tag-alert'}">QA diagnostic</span></div>
    <p>Representative cycles chosen mechanically from the full-corpus scan: quietest, loudest,
      closest-to-median, and (if the spur-resolve step above found and confirmed a dominant
      in-band peak) the cycle that produced it.</p>
    <figure><img src="img/spectral_trace.png" alt="Welch PSD and STFT spectrogram comparison">
      <figcaption>Welch PSD (left) and STFT spectrogram (right), 12kHz sample rate. Panels:
        {', '.join(esc(p) for p in findings['spectral_trace_panels'])}.</figcaption></figure>
  </section>""")

    # -- Section 5: historical trend -----------------------------------------------------------
    rows_html = []
    fn_list = []
    fn_idx = 0
    for h in hist:
        cite = ""
        comparable = h.get("reference") == "live_wsjtx"
        if not comparable:
            fn_idx += 1
            fn_list.append(f"non-comparable reference ({esc(h.get('reference'))}) &mdash; {esc(h.get('date'))} {esc(h.get('band'))}")
            cite = f"<sup>{fn_idx}</sup>"
        if h.get("drift_contaminated"):
            fn_idx += 1
            fn_list.append(f"{esc(h.get('drift_note',''))} &mdash; {esc(h.get('date'))} {esc(h.get('band'))}")
            cite += f"<sup>{fn_idx}</sup>"
        is_this_run = os.path.normpath(str(h.get("run_dir", ""))) == run_dir
        row_style = ' style="background:var(--panel-2);"' if is_this_run else ""
        label = f"<b>{esc(h.get('date'))} (this run)</b>" if is_this_run else esc(h.get("date"))
        rows_html.append(
            f"<tr{row_style}><td>{label}{cite}</td><td>{esc(h.get('band'))}</td>"
            f"<td>{fmt(h.get('hours'),'{}')}</td><td>{esc(h.get('shim'))}</td><td>{esc(h.get('nhard'))}</td>"
            f"<td>{esc(h.get('reference'))}</td><td>{esc(h.get('radio_chain'))}</td>"
            f"<td>{fmt(h.get('grid_gate_g'),'{:.4f}')}</td><td>{fmt(h.get('n_pairs'),'{:,}')}</td>"
            f"<td>{fmt(h.get('matched_pct_of_ref'),'{:.1f}')}</td><td>{fmt(h.get('ows_only_pct'),'{:.1f}')}</td>"
            f"<td>{fmt(h.get('snr_gap_db'),'{:.3f}')}</td><td>{fmt(h.get('dt_gap_s'),'{:+.4f}')}</td></tr>")

    comp_rows_html = ""
    if len(comparable_hist) >= 2:
        prev = comparable_hist[-2]
        cur = comparable_hist[-1]
        d_snr = cur.get("snr_gap_db", float("nan")) - prev.get("snr_gap_db", float("nan"))
        comp_rows_html = f"""
    <h3>Most recent comparable pair</h3>
    <div class="tbl-wrap"><table><thead><tr><th>Date</th><th>Hours</th><th>Radio chain</th><th>Matched %</th><th>OWS-only %</th><th>SNR gap</th><th>DT gap</th></tr></thead>
      <tbody>
        <tr><td>{esc(prev.get('date'))}</td><td>{fmt(prev.get('hours'),'{}')}</td><td>{esc(prev.get('radio_chain'))}</td>
          <td>{fmt(prev.get('matched_pct_of_ref'),'{:.1f}')}</td><td>{fmt(prev.get('ows_only_pct'),'{:.1f}')}</td>
          <td>{fmt(prev.get('snr_gap_db'),'{:.3f}')}</td><td>{fmt(prev.get('dt_gap_s'),'{:+.4f}')}</td></tr>
        <tr style="background:var(--panel-2);"><td><b>{esc(cur.get('date'))}</b></td><td>{fmt(cur.get('hours'),'{}')}</td><td><b>{esc(cur.get('radio_chain'))}</b></td>
          <td>{fmt(cur.get('matched_pct_of_ref'),'{:.1f}')}</td><td>{fmt(cur.get('ows_only_pct'),'{:.1f}')}</td>
          <td class="hl">{fmt(cur.get('snr_gap_db'),'{:.3f}')}</td><td>{fmt(cur.get('dt_gap_s'),'{:+.4f}')}</td></tr>
      </tbody></table></div>
    <p><b>SNR gap moved {d_snr:+.3f} dB</b> vs. the immediately preceding comparable row (same band,
      same nhard, live reference). n={len(comparable_hist)} comparable rows total for this
      band/nhard combination -- read this delta against that sample size, not as a trend.</p>"""

    body.append(f"""
  <section id="trend">
    <div class="section-head"><h2>5&nbsp;&middot;&nbsp;Historical trend (HK-036 Section 4 read)</h2>
      <span class="section-tag tag-info">{len(hist)} runs on record</span></div>
    <p><code>G</code> is the grid-alignment gate (ROW 1 PASS &ge; 0.99). Non-comparable and
      drift-contaminated rows are footnoted, never pooled. Never pool different <code>nhard</code>
      values or different bands.</p>
    <div class="tbl-wrap"><table><thead><tr>
      <th>Date</th><th>Band</th><th>Hrs</th><th>Shim</th><th>nhard</th><th>Ref.</th><th>Radio chain</th>
      <th>G</th><th>Matched</th><th>Matched % ref</th><th>OWS-only %</th><th>SNR gap</th><th>DT gap</th>
    </tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>
    <ol class="fn">{''.join(f'<li>{f}</li>' for f in fn_list)}</ol>
    {comp_rows_html}
  </section>""")

    body.append(f"""
  <footer id="provenance">
    Corpus (gitignored, NFR-021): <code>{esc(os.path.relpath(run_dir))}</code>.
    Pipeline: <code>spectrum_scan.py</code> &rarr; <code>spectrum_scan_report.py</code> &rarr;
    <code>render_dossier.py</code> &mdash; the standard routine after every endurance run
    (Captain's instruction, 2026-09-24). Generated by <code>render_dossier.py</code>.
  </footer>
</div>""")
    return "\n".join(body)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True, help="The *-gathered directory (owsfz/, wsjt-x/, anova_report.meta.json)")
    ap.add_argument("--scan-json", default=None, help="Default: <run-dir>/spectrum_scan.json")
    ap.add_argument("--findings-json", default=None, help="Default: <run-dir>/findings.json")
    ap.add_argument("--out", default=None, help="Default: <run-dir>/FINAL_REPORT_dossier.html")
    ap.add_argument("--title", default="Endurance Dossier")
    ap.add_argument("--purpose", default="Standard post-endurance-run report: full-corpus spectral "
                     "anomaly scan, complete matched-decode ANOVA, and the HK-036 historical trend read.")
    args = ap.parse_args()
    args.scan_json = args.scan_json or os.path.join(args.run_dir, "spectrum_scan.json")
    args.findings_json = args.findings_json or os.path.join(args.run_dir, "findings.json")
    out = args.out or os.path.join(args.run_dir, "FINAL_REPORT_dossier.html")

    html = build(args)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
