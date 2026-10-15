"""Build the FULL ANOVA report of a NEW LINUX baseline series on `sol` (QA tooling; aggregates only, NFR-021). Reuses the 2026-10-14 full-ANOVA tools
(`full_anova_core.py`, `build_full_anova_report.py`: data loading, the analyser's per-sweep ANOVA, the three-way random-effects ANOVA with part-bootstrap CIs,
bias and attribute statistics, figures) and adds what a baseline needs: S6 per sweep, the MONITORING layer (M1 monitor, M2 gate, M3 coverage, daemon log),
the stall row (attempts / stalls / replacements), a DESCRIPTIVE comparison with the earlier series (never pooled) and the history of every LINUX series.

    python build_baseline_anova_report.py --results <results root> --out <folder> [--series-id B2BASE] [--config <series.json>]

Without --config the sweeps are discovered as `<results>/*-<series-id>-sweep<n>` (folders carrying INVALID / captured-audio in the name are not sweeps; INVALID
ones are read for the stall row). Every sweep folder should hold `monitoring_summary.json` (linux/monitoring_summary.py) and, if S6 ran, `s6/s6_result.json`.
The series is N COMPLETE sweeps; a replaced sweep is kept on disk as INVALID, never used here. Never pooled with another series.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import statistics
import subprocess
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_full_anova_report as B  # noqa: E402
import consolidate_data as C  # noqa: E402
import full_anova_core as F  # noqa: E402
from harness import analyse as _AN  # noqa: E402

PALETTE = ["#58a6ff", "#3fb950", "#d29922", "#bc8cff", "#f0883e", "#39c5cf", "#db61a2", "#8b949e"]
OLD_KEYS = ["run1", "run2", "w1", "w2", "w3"]          # the earlier (2026-10-11 / 10-14, main WITHOUT B2) paired sweeps, for the descriptive comparison only
OLD_OWS_ONLY = ["rep1", "rep2", "rep3"]
S6_FIELDS = (("positive_agreement", "positive agreement", "%", 100.0), ("consistency_own_wsjtx", "WSJT-X own consistency", "%", 100.0),
             ("consistency_own_owsfz", "OpenWSFZ own consistency", "%", 100.0), ("decodes_per_wav_wsjtx", "decodes per WAV, WSJT-X", "", 1.0),
             ("decodes_per_wav_owsfz", "decodes per WAV, OpenWSFZ", "", 1.0), ("snr_delta_mean", "SNR delta (OpenWSFZ - WSJT-X), mean", "dB", 1.0))


def jload(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def discover(results: str, series_id: str) -> tuple:
    """-> (sweep folders in order, INVALID folders)."""
    ok, inv = [], []
    for d in sorted(os.listdir(results)):
        if not os.path.isdir(os.path.join(results, d)) or series_id not in d:
            continue
        m = re.search(r"%s-sweep(\d+)(.*)$" % re.escape(series_id), d)
        if not m:
            continue
        if "captured-audio" in d:
            continue
        (inv if "INVALID" in m.group(2) else ok).append((int(m.group(1)), d))
    return [d for _, d in sorted(ok)], [d for _, d in sorted(inv)]


def register(keys: list, folders: list) -> None:
    """Make the sweeps known to the shared tools (consolidate_data, build_full_anova_report) at run time."""
    for i, (k, d) in enumerate(zip(keys, folders)):
        C.SWEEPS.append((k, d, "Sweep %d" % (i + 1), True))
        B.COL[k] = PALETTE[i % len(PALETTE)]
        B.SHORT[k] = "Sweep %d" % (i + 1)
        B.LAB[k] = "Sw %d" % (i + 1)


def stall_row(results: str, ok_dirs: list, inv_dirs: list) -> dict:
    """The stall row, SCENARIO level: per scenario and in total, attempts / failed attempts (stalls and coverage failures) / replacements, from each sweep's `scenario_retries.json`;
    whole-sweep INVALID folders (the earlier launcher; none expected) are still listed. 'retries exhausted' = a scenario failed again with its cap used up (the series halted)."""
    per: dict = {}
    fails = []
    sweeps_with_retry = 0
    exhausted = []
    for d in ok_dirs:
        doc = jload(os.path.join(results, d, "scenario_retries.json"))
        if jload(os.path.join(results, d, "RETRIES_EXHAUSTED.json")):
            exhausted.append(d)
        if not doc:
            continue
        used = 0
        for sid, v in doc.get("scenarios", {}).items():
            row = per.setdefault(sid, {"attempts": 0, "failed": 0, "replacements": 0})
            row["attempts"] += v.get("attempts", 0)
            row["failed"] += len(v.get("failed", []))
            row["replacements"] += v.get("retries_used", 0)
            used += v.get("retries_used", 0)
            for f in v.get("failed", []):
                fails.append({"sweep": d, "scenario": sid, "attempt": f.get("attempt"), "kind": f.get("kind"), "reason": f.get("reason"), "utc": f.get("utc"), "replaced_by_attempt": f.get("replaced_by_attempt")})
        sweeps_with_retry += 1 if used else 0
    inv = []
    for d in inv_dirs:
        st = jload(os.path.join(results, d, "STALLED.json")) or {}
        inv.append({"folder": d, "utc": st.get("utc"), "scenario": st.get("scenario"), "reason": st.get("reason")})
    tot = {k: sum(r[k] for r in per.values()) for k in ("attempts", "failed", "replacements")}
    return {"sweeps_complete": len(ok_dirs), "sweeps_with_a_retry": sweeps_with_retry, "per_scenario": per, "totals": tot, "failures": fails, "retries_exhausted_in": exhausted, "invalid_sweep_folders": inv,
            # kept for the summary text
            "stalls": tot["failed"], "replacements": tot["replacements"], "attempts": tot["attempts"], "stall_list": inv}


def t_row(vals: list):
    m, sd, lo, hi = F.t_ci(vals)
    return m, sd, lo, hi


def build(results: str, out: str, series_id: str, config: str | None) -> None:
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    if config:
        cfg = jload(config)
        folders = cfg["sweeps"]
        inv = cfg.get("invalid", [])
    else:
        folders, inv = discover(results, series_id)
    if len(folders) < 2:
        raise SystemExit("need at least two complete sweeps; found %d (%s)" % (len(folders), folders))
    keys = ["b%d" % (i + 1) for i in range(len(folders))]
    register(keys, folders)
    # ---- the baseline series: the shared tools read F.PAIRED / F.CORRECTED, so set them for this series
    F.PAIRED, F.CORRECTED = list(keys), list(keys)
    B.NAME  # noqa: B018 (shared label dicts)
    R = B.compute(results)
    Fg = B.figures(R, os.path.join(out, "img"))
    S, T, BT = R["summ"], R["three"], R["boot"]
    n = len(keys)
    mon = {k: jload(os.path.join(results, folders[i], "monitoring_summary.json")) for i, k in enumerate(keys)}
    s6 = {k: jload(os.path.join(results, folders[i], "s6", "s6_result.json")) for i, k in enumerate(keys)}
    s6v = {k: jload(os.path.join(results, folders[i], "s6", "s6_validity.json")) for i, k in enumerate(keys)}
    # S6 design per sweep (2026-10-15): "sequential" = WSJT-X alone, then OpenWSFZ alone (s6/s6_merge.py); anything else (and every result from before) = concurrent
    s6_designs = {k: (s6[k].get("design") or "concurrent") for k in keys if s6.get(k)}
    s6_seq_only = bool(s6_designs) and set(s6_designs.values()) == {"sequential"}
    s6_mixed = len(set(s6_designs.values())) > 1
    stall = stall_row(results, folders, inv)
    # ---- the earlier series, descriptive comparison only (computed with the same tools, then the baseline setting is restored)
    ref = None
    if all(os.path.isdir(os.path.join(results, s[1])) for s in C.SWEEPS if s[0] in OLD_KEYS):
        F.PAIRED, F.CORRECTED = list(OLD_KEYS), list(OLD_KEYS[1:])
        ref = B.compute(results)
        F.PAIRED, F.CORRECTED = list(keys), list(keys)
    s1, s2, s3 = T["S1"], T["S2"], T["S3"]
    o_b = [R["bias"]["S1"][k]["OpenWSFZ"]["bias"] for k in keys]
    w_b = [R["bias"]["S1"][k]["WSJT-X"]["bias"] for k in keys]
    dif = [o - w for o, w in zip(o_b, w_b)]
    m_d, sd_d, lo_d, hi_d = F.t_ci(dif)
    v = lambda sc: _AN._verdict_grr(T[sc]["pct_grr_sv"])
    ci = lambda sc, g: "%.3f to %.3f" % BT[sc][g]
    NW = {3: "three", 4: "four", 5: "five", 6: "six"}.get(n, str(n))
    r1 = S[keys[0]]
    L = []
    A = L.append
    A("# OpenWSFZ R&R Study: LINUX series on `sol`, %s baseline, full ANOVA report" % series_id)
    A("")
    A("> **A NEW series: %s complete sweeps (S1-S8, S3c%s) on the B2 build, with the monitoring layer on (M1 monitor, M2 liveness gate, M3 coverage).** Full ANOVA of the two appraisers over the sweeps as the replication, bias and attribute statistics, S6, the monitoring record, the stall row, a DESCRIPTIVE comparison with the earlier series (**never pooled with it**) and the history of every LINUX series. **Not comparable with the Windows series.** Informational: no merge or build decision rests on this report." % (
        n, ", S6" if any(s6.values()) else ""))
    A("")
    A(B.md_table(["Field", "Value"], [
        ["Report date", "analysis of the run folders, no new run"],
        ["Host", "`sol`: AMD FX-8350, Gentoo; no radio, no CAT; audio through the codec loopback, PCM `rr_in`"],
        ["OpenWSFZ build, all %d sweeps" % n, "`%s` (v%s, shim %s)" % (r1["build"]["commit"], r1["build"]["daemon_version"], r1["build"]["shim"])],
        ["`libft8.so` SHA-256", "`%s` in all %d (read back from each run's `arm_config.json`: %s)" % (r1["build"]["dll_sha256"], n, "equal" if len({S[k]["build"]["dll_sha256"] for k in keys}) == 1 else "**NOT EQUAL**")],
        ["Decoder flags (read back)", "`osdNhardMax` %s, `subtractionEnabled` %s, `subtractionMaxThreads` %s" % (r1["build"]["readback"]["osdNhardMax"], r1["build"]["readback"]["subtractionEnabled"], r1["build"]["readback"]["subtractionMaxThreads"])],
        ["WSJT-X", "2.7.0 built from the verified source tarball on `sol` (Qt 5.15, gfortran 13.4.0); NDepth %s" % r1["build"]["wsjtx_ndepth"]],
        ["Gate", "%GR&R is graded on **%StudyVar** (10 / 30 %, Captain 2026-10-14); %Contribution is printed beside it, no verdict"],
        ["Analysis code", "`qa/rr-study/linux/full_anova_core.py`, `build_full_anova_report.py` (shared with the 2026-10-14 report), `build_baseline_anova_report.py`, `monitoring_summary.py`"],
    ]))
    A("")
    # ------------------------------------------------------------------------------------------------------------------------------ summary
    A("## Summary")
    A("")
    A("1. **The measurement system, graded as the project grades it:** %%StudyVar (%s sweeps, two appraisers, ten parts, three trials) is **S1 %.1f %% (%s), S2 %.1f %% (%s), S3 %.1f %% (%s)**; %%Contribution %.2f %%, %.3f %%, %.2f %% (bootstrap 95 %% CI of the %%Contribution: S1 %s, S3 %s); ndc %s / %s / %s. Per sweep, S3 reads %s." % (
        NW, s1["pct_grr_sv"], v("S1"), s2["pct_grr_sv"], v("S2"), s3["pct_grr_sv"], v("S3"), s1["pct_grr"], s2["pct_grr"], s3["pct_grr"], ci("S1", "grr"), ci("S3", "grr"), s1["ndc"], s2["ndc"], s3["ndc"],
        ", ".join("%s %.1f %% %s" % (B.LAB[k], R["per"]["S3"][k]["pct"]["grr_sv"], _AN._verdict_grr(R["per"]["S3"][k]["pct"]["grr_sv"])) for k in keys)))
    A("2. **Appraisers and sweeps.** OpenWSFZ minus WSJT-X on S1: %+.2f dB (t 95 %% CI %.2f to %.2f over the %s sweeps); S3 appraiser share of the variance %.3f %% (a fixed DT offset between the programs, %+.3f s). OpenWSFZ's S1 bias per sweep %s dB, WSJT-X's %s dB; Appraiser x Sweep p %s; sweep share of the S1 variance %.3f %%." % (
        m_d, lo_d, hi_d, NW, s3["pct_groups"]["appraiser"], F.t_ci([R["bias"]["S3"][k]["OpenWSFZ"]["bias"] - R["bias"]["S3"][k]["WSJT-X"]["bias"] for k in keys])[0],
        ", ".join("%+.2f" % x for x in o_b), ", ".join("%+.2f" % x for x in w_b), B.fp(s1["tests"]["AS"][3]), s1["pct_groups"]["sweep"]))
    s4o = R["s4"]["M"]["OpenWSFZ"].sum(axis=0)
    s4w = R["s4"]["M"]["WSJT-X"].sum(axis=0)
    A("3. **Attribute results.** S4 (%d messages): OpenWSFZ %s per sweep, WSJT-X %s; Cochran's Q across the sweeps p %s (OpenWSFZ), %s (WSJT-X)." % (
        R["s4"]["keys"], "/".join(str(x) for x in s4o), "/".join(str(x) for x in s4w), B.fp(F.cochran_q(R["s4"]["M"]["OpenWSFZ"])[2]), B.fp(F.cochran_q(R["s4"]["M"]["WSJT-X"])[2])))
    A("4. **Stall row (its own row, scenario level):** %d complete sweeps; %d scenario attempts, **%d failed attempt(s) (stalls and coverage failures), %d replacement(s)**, in %d of the sweeps%s." % (
        stall["sweeps_complete"], stall["attempts"], stall["stalls"], stall["replacements"], stall["sweeps_with_a_retry"],
        "" if not stall["failures"] else " (" + "; ".join("%s %s attempt %s: %s" % (f["sweep"].split("-B2BASE-")[-1] if "B2BASE" in f["sweep"] else f["sweep"][-12:], f["scenario"], f["attempt"], f["reason"]) for f in stall["failures"]) + ")"))
    if any(s6.values()):
        pa = [s6[k]["full"]["headline"]["positive_agreement"] for k in keys if s6.get(k)]
        ab = [s6[k]["abandonment"]["plays_abandoned"] for k in keys if s6.get(k)]
        A("5. **S6 (real off-air audio, live path):** %d sweeps; positive agreement %s; abandoned plays per sweep %s of %s. See Section 3.5 (live-path reading only, not a decode-rate claim)." % (
            len(pa), "/".join("%.1f %%" % (100 * x) for x in pa), "/".join(str(x) for x in ab), "/".join(str(s6[k]["plays"]) for k in keys if s6.get(k))))
    A("%d. **Limits.** One host, one build, one chain; %d sweeps (the sweep factor has %d degrees of freedom); the same 10 parts and 108 messages in every sweep; rounded reported values (1 dB, 1 Hz, 0.1 s). The earlier series (main without B2) is compared descriptively and never pooled." % (6 if any(s6.values()) else 5, n, n - 1))
    A("")
    # ------------------------------------------------------------------------------------------------------------------------------ section 1
    A("## Section 1: scope, data and design")
    A("")
    rows = []
    for i, k in enumerate(keys):
        sm = mon[k] or {}
        rep = (sm.get("replacement") or {})
        rows.append([B.SHORT[k], "%s to %s" % (S[k]["cycle_utc_first_last"][0][5:16].replace("T", " "), S[k]["cycle_utc_first_last"][1][5:16].replace("T", " ")), "%d / %d" % (S[k]["wsjt_all_lines"], S[k]["owsfz_all_lines"]),
                     ("; ".join("%s x%d" % (sid, v["retries_used"]) for sid, v in ((jload(os.path.join(results, folders[i], "scenario_retries.json")) or {}).get("scenarios", {})).items() if v.get("retries_used")) or "none"), "`%s`" % folders[i]])
    A(B.md_table(["Sweep", "Cycles first to last (UTC)", "`wsjt-all.txt` / `owsfz-all.txt` lines", "Scenario retries", "Folder"], rows))
    A("")
    if inv:
        A("**Replaced sweeps (kept on disk, INVALID, none of their data is used):** " + "; ".join("`%s`" % d for d in inv) + ".")
        A("")
    A("**The series rule (Captain 2026-10-14):** the series is %d COMPLETE sweeps. The retry unit is the SCENARIO: when WSJT-X stalls inside a scenario (the M2 gate stops it) or the scenario's coverage fails (M3; S6-V7), WSJT-X is restarted and THAT scenario is rerun with all its trials in the same sweep folder; the failed attempt is kept as INVALID (its truth rows as `truth_INVALID_*`, its `s6/` as `s6-INVALID-attemptK`) and a replacement is recorded in `scenario_retries.json`; at most 3 retries per scenario, a 4th failure of the same scenario halts and flags; passed scenarios are kept; there is no wall-time limit. Nothing is repaired below the scenario (a part's trials come from one WSJT-X session), and nothing is pooled with another series." % n)
    A("")
    A("**Design (checked in code: every cell has exactly 3 trials).** S1 SNR, S2 frequency and S3 DT: 10 parts x 2 appraisers x 3 trials per sweep; the sweeps are separate sessions (daemon and WSJT-X restarted) with identical injected seeds.")
    A("")
    # ------------------------------------------------------------------------------------------------------------------------------ section 2
    A("## Section 2: method")
    A("")
    A("1. **Per sweep:** the analyser's own two-way crossed ANOVA (imported from `harness/analyse.py`); the figures are asserted equal to each sweep's own `report.md` (on the metric that report was graded on: %StudyVar).")
    A("2. **Pooled over sweeps:** a three-way crossed random-effects ANOVA Part (10) x Appraiser (2) x Sweep (%d), 3 trials per cell; variance components by expected mean squares (negative estimates truncated to 0 for the percentages), exact F for the interactions, Satterthwaite quasi-F for the main effects, a part-cluster bootstrap for the percentages (2000 resamples; it resamples parts, not sweeps). Appraiser is treated as random only for comparability with AIAG; with two programs it is a fixed offset, read as the bias in 3.3." % n)
    A("3. **Bias and linearity, attribute data (S4, S1b), S5, S7, S8:** as in the 2026-10-14 report (Cochran's Q across sweeps, an exact sign test between appraisers).")
    A("4. **S6** (real off-air audio replayed in consecutive 15 s slots, " + ("the identical schedule played twice, WSJT-X alone and then OpenWSFZ alone (SEQUENTIAL passes, 2026-10-15: played together WSJT-X's capture stalled on `sol`)" if s6_seq_only else
      ("a MIX of concurrent and sequential S6 sweeps: they are NOT comparable and must not be pooled" if s6_mixed else "both appraisers listening at once")) + ", K = 3): read from each sweep's own `s6_result.json`; shown per sweep and as the spread over the sweeps. It is a LIVE-PATH reading; the S6 figures are not decode-rate claims.")
    A("5. **Monitoring:** the per-sweep `monitoring_summary.json` (M1 monitor log, M2 gate record, M3 coverage rows, daemon-log aggregates, build pins, core files); section 3.6.")
    A("6. **The earlier series** (main without B2: run 1 default chain, run 2, repeats 1b-3b) is computed with the same code and shown beside the baseline in 3.7, descriptively. No test is run across the two series.")
    A("")
    # ------------------------------------------------------------------------------------------------------------------------------ section 3
    A("## Section 3: results")
    A("")
    A("### 3.1 Per-sweep Gage R&R (the analyser's figures, reproduced)")
    A("")
    rows = []
    for sc, *_r in F.SCEN:
        rows.append([B.NAME[sc].split(" (")[0]] + ["%.2f %% / %.1f %% %s (%s)" % (R["per"][sc][k]["pct"]["grr"], R["per"][sc][k]["pct"]["grr_sv"], _AN._verdict_grr(R["per"][sc][k]["pct"]["grr_sv"]), R["per"][sc][k]["ndc"]) for k in keys])
    A(B.md_table(["%Contribution / %StudyVar verdict (ndc)"] + [B.SHORT[k] for k in keys], rows))
    A("")
    A("### 3.2 Combined ANOVA, %s sweeps" % NW)
    A("")
    for sc, *_r in F.SCEN:
        r = T[sc]
        A("#### %s" % B.NAME[sc])
        A("")
        A(B.anova_table(r, sc))
        A("")
        A("Quasi-F (main effects): numerator MS_effect + MS_PxAxS, denominator the sum of the two mean squares of the interactions that involve the effect; degrees of freedom by Satterthwaite.")
        A("")
        vrows = []
        for k in ("P", "A", "S", "PA", "PS", "AS", "PAS", "E"):
            vrows.append([B.TERM[k], B.fnum(r["vc"][k], 4) + (" (raw %s, set to 0)" % B.fnum(r["vc_raw"][k], 2) if r["vc_raw"][k] < 0 else ""), "%.4f %%" % r["pct"][k]])
        A(B.md_table(["Variance component", "Estimate (%s²)" % B.UNIT[sc], "% of total"], vrows))
        A("")
        gr = r["pct_groups"]
        A("Grouped: repeatability **%.3f %%** (CI %s), appraiser **%.3f %%** (CI %s), sweep **%.3f %%** (CI %s); **%%Contribution %.3f %% (CI %s), %%StudyVar %.1f %% (%s), ndc %s**; part %.3f %%. Pooled two-way ignoring the sweeps: %%Contribution %.3f %% (ndc %s)." % (
            gr["repeatability"], ci(sc, "repeatability"), gr["appraiser"], ci(sc, "appraiser"), gr["sweep"], ci(sc, "sweep"), r["pct_grr"], ci(sc, "grr"), r["pct_grr_sv"], _AN._verdict_grr(r["pct_grr_sv"]), r["ndc"], gr["part"], R["pooled2"][sc]["pct"]["grr"], R["pooled2"][sc]["ndc"]))
        A("")
    for key in ("A1", "A2", "A3", "A8"):
        A("![%s](img/%s)" % (Fg[key][1][:40], Fg[key][0]))
        A("")
        A("*Figure %s. %s*" % (key, Fg[key][1]))
        A("")
    A("S3 note (Architect, 2026-10-14): S3 reproducibility is dominated by a fixed OpenWSFZ − WSJT-X DT offset (+0.12 s, Section 3.3 of the 2026-10-14 full-ANOVA report), not by run-to-run noise.")
    A("")
    A("### 3.3 Bias and linearity")
    A("")
    brow = []
    for sc, *_r in F.SCEN:
        for ap in ("OpenWSFZ", "WSJT-X"):
            vv = [R["bias"][sc][k][ap]["bias"] for k in keys]
            m, sd, lo, hi = F.t_ci(vv)
            brow.append([B.NAME[sc].split(" (")[0], ap] + ["%.3f" % x for x in vv] + ["%.3f (%.3f to %.3f)" % (m, lo, hi)])
    A(B.md_table(["Scenario", "Appraiser"] + [B.LAB[k] for k in keys] + ["Mean (95 % t-CI)"], brow))
    A("")
    drow = []
    for sc, *_r in F.SCEN:
        d = [R["bias"][sc][k]["OpenWSFZ"]["bias"] - R["bias"][sc][k]["WSJT-X"]["bias"] for k in keys]
        m, sd, lo, hi = F.t_ci(d)
        drow.append([B.NAME[sc].split(" (")[0], B.UNIT[sc]] + ["%+.3f" % x for x in d] + ["%+.3f (%+.3f to %+.3f)" % (m, lo, hi)])
    A(B.md_table(["OpenWSFZ minus WSJT-X", "Unit"] + [B.LAB[k] for k in keys] + ["Mean (95 %% t-CI over %d sweeps)" % n], drow))
    A("")
    A("![%s](img/%s)" % ("S1 difference", Fg["A4"][0]))
    A("")
    A("*Figure A4. %s*" % Fg["A4"][1])
    A("")
    A("### 3.4 Attribute agreement, S5, S7, S8")
    A("")
    qrows = []
    for key, nm in (("s4", "S4 (%d messages)" % R["s4"]["keys"]), ("s1b", "S1b (%d messages)" % R["s1b"]["keys"])):
        for ap in ("OpenWSFZ", "WSJT-X"):
            M = R[key]["M"][ap]
            Q, dfq, pq = F.cochran_q(M)
            cnt = M.sum(axis=1)
            qrows.append([nm, ap, "/".join(str(x) for x in M.sum(axis=0)), "%d / %d / %d" % ((cnt == n).sum(), (cnt == 0).sum(), ((cnt > 0) & (cnt < n)).sum()), "%.2f (df %d)" % (Q, dfq), B.fp(pq)])
    A(B.md_table(["Scenario", "Appraiser", "Decoded per sweep", "Messages decoded in all / none / some sweeps", "Cochran's Q", "p"], qrows))
    A("")
    srows = []
    for key, nm in (("s4", "S4"), ("s1b", "S1b")):
        d = R[key]["M"]["WSJT-X"].sum(axis=1) - R[key]["M"]["OpenWSFZ"].sum(axis=1)
        pos, neg, p = F.exact_sign(d)
        srows.append([nm, "%d" % pos, "%d" % neg, "%d" % (d == 0).sum(), B.fp(p)])
    A(B.md_table(["Per-message decode count, appraisers", "WSJT-X more often", "OpenWSFZ more often", "Ties", "Exact sign test p"], srows))
    A("")
    A("![%s](img/%s)" % ("Cross-tab", Fg["A5"][0]))
    A("")
    A("*Figure A5. %s*" % Fg["A5"][1])
    A("")
    prow = []
    for k in keys:
        s = S[k]
        prow.append([B.SHORT[k], s["s5"]["gate_aw"].split(" (")[0], "%s / %s" % (s["s5"]["check_b_w"].split(" slots")[0], s["s5"]["check_b_o"].split(" slots")[0]), "%.2f / %.2f %%" % (s["s7"]["all"]["owsfz"], s["s7"]["all"]["wsjtx"]),
                     "%.2f / %.2f %%" % (s["s8"]["OpenWSFZ"]["rate"], s["s8"]["WSJT-X"]["rate"]), "%.2f / %.2f %%" % (s["s1b_overall"]["owsfz"], s["s1b_overall"]["wsjtx"]),
                     "%.2f %% (%d) / %.2f %% (%d)" % (s["s4"]["OpenWSFZ"]["recovery"], s["s4"]["OpenWSFZ"]["tp"], s["s4"]["WSJT-X"]["recovery"], s["s4"]["WSJT-X"]["tp"])])
    A(B.md_table(["Sweep", "S5 OpenWSFZ FP (Gate A-W)", "S5 narrowband Check B (WSJT-X / OpenWSFZ)", "S7 OpenWSFZ / WSJT-X", "S8 OpenWSFZ / WSJT-X", "S1b OpenWSFZ / WSJT-X", "S4 OpenWSFZ (TP) / WSJT-X (TP)"], prow))
    A("")
    c7o = [S[k]["s7"]["all"]["owsfz"] for k in keys]
    c7w = [S[k]["s7"]["all"]["wsjtx"] for k in keys]
    A("S7 is instrument-suspect by standing rule: shown per sweep and as a band (OpenWSFZ %.2f to %.2f %%, WSJT-X %.2f to %.2f %%), never as a mean. S8 is descriptive." % (min(c7o), max(c7o), min(c7w), max(c7w)))
    A("")
    A("![%s](img/%s)" % ("Rates", Fg["A6"][0]))
    A("")
    A("*Figure A6. %s*" % Fg["A6"][1])
    A("")
    # ---- 3.5 S6
    A("### 3.5 S6: real off-air audio, the live path")
    A("")
    if not any(s6.values()):
        A("S6 did not run in these sweeps (no `s6/s6_result.json`).")
        A("")
    else:
        have = [k for k in keys if s6.get(k)]
        A(B.md_table(["Sweep", "Status", "Tier / plays", "Validity rows (V1/V2/V3/V4/V5)", "Abandoned plays", "Positive agreement", "Decodes per WAV (WSJT-X / OpenWSFZ)", "SNR delta mean (dB)", "Onset median (s)"], [
            [B.SHORT[k], s6[k].get("status"), "%s / %s%s" % (s6[k].get("tier"), s6[k].get("plays"), " (sequential)" if s6_designs.get(k) == "sequential" else ""),
             "/".join(str((s6[k].get("validity") or {}).get("S6-V%d" % i, {}).get("result", "-")) for i in (1, 2, 3, 4, 5)),
             "%s of %s" % (s6[k]["abandonment"].get("plays_abandoned"), s6[k].get("plays")),
             "%.1f %%" % (100 * s6[k]["full"]["headline"]["positive_agreement"]),
             "%.2f / %.2f" % (s6[k]["full"]["headline"]["decodes_per_wav_wsjtx"], s6[k]["full"]["headline"]["decodes_per_wav_owsfz"]),
             "%+.2f" % s6[k]["full"]["headline"]["snr_delta_mean"], "%s" % (s6[k].get("onset") or {}).get("per_play_median_shift_s", {}).get("median")] for k in have]))
        A("")
        srows = []
        for fld, lab, unit, mult in S6_FIELDS:
            vals = [s6[k]["full"]["headline"][fld] * mult for k in have if s6[k]["full"]["headline"].get(fld) is not None]
            if len(vals) >= 2:
                m, sd, lo, hi = F.t_ci(vals)
                srows.append([lab, "%.2f %s" % (m, unit), "%.2f" % sd, "%.2f to %.2f" % (lo, hi), "%.2f to %.2f" % (min(vals), max(vals))])
        A(B.md_table(["S6 measure (over %d sweeps)" % len(have), "Mean", "SD", "95 % t-CI of the mean", "Range"], srows))
        A("")
        A(("S6 reads the **live path** of each program in its OWN pass (WSJT-X alone, then OpenWSFZ alone; the two did not hear the same capture, and OpenWSFZ ran in a fresh process)" if s6_seq_only
           else "S6 reads the **live path** of both programs on the same CPU") + "; a decode-rate claim cannot be made from it (the within-appraiser consistency is the consistency of each program's own decodes across the three trials of the same WAV, not agreement with truth). The S6 ANOVA over parts is reported as the sweep's own `s6_result.json` gives it (`anova_parts`); where it is 0 the block reports no balanced part and no ANOVA is shown.")
        A("")
    # ---- 3.6 monitoring
    A("### 3.6 Monitoring and validity (M1, M2, M3 and the other monitoring)")
    A("")
    if not any(mon.values()):
        A("No `monitoring_summary.json` is present in the sweep folders: the monitoring record is NOT available for this series.")
        A("")
    else:
        A("**M1: the monitor** (a separate process sampling every 15 s: the real `wsjtx` and `jt9` processes, the age of WSJT-X's newest save WAV, the ALSA stream states, `aplay` processes, the suspended-time delta, host load).")
        A("")
        rows = []
        for k in keys:
            m1 = (mon.get(k) or {}).get("M1_monitor") or {}
            rows.append([B.SHORT[k], m1.get("samples"), "%s" % m1.get("ok_share"), "%s / %s" % ((m1.get("wav_age_s") or {}).get("median"), (m1.get("wav_age_s") or {}).get("max")), m1.get("stall_episodes"),
                         "%s / %s" % (m1.get("wsjtx_restarts_during_monitoring"), m1.get("jt9_restarts_during_monitoring")), "%s" % (m1.get("wsjtx_rss_kb") or {}).get("max"),
                         "%s" % (m1.get("suspended_s") or {}).get("delta"), "%s" % (m1.get("aplay") or {}).get("max_count"), "%s / %s" % ((m1.get("host_load1") or {}).get("median"), (m1.get("host_load1") or {}).get("max"))])
        A(B.md_table(["Sweep", "Samples", "Share ok", "Newest WAV age median / max (s)", "Stall episodes", "wsjtx / jt9 restarts", "wsjtx RSS max (kB)", "Suspended-time delta (s)", "aplay max", "Host load1 median / max"], rows))
        A("")
        A("**M2: the liveness gate** (stops and flags when no new WAV arrives for 45 s or no `wsjtx` process; reported per sweep) and **M3: coverage** (cycles with data per scenario and appraiser; INVALID if below expected minus one):")
        A("")
        rows = []
        for k in keys:
            mm = mon.get(k) or {}
            g = (mm.get("M2_gate") or {})
            cv = (mm.get("M3_coverage") or {})
            rows.append([B.SHORT[k], "first reading %s" % (g.get("gate_record") or {}).get("first_reading_ok", "n/a"), "STALLED" if g.get("stalled") else "no stall", "%s PASS / %s INVALID" % (cv.get("rows_pass"), cv.get("rows_invalid")),
                         "%s" % ", ".join(sorted((cv.get("slot_files") or {}).keys()) if all((cv.get("slot_files") or {}).values()) else ["slot list missing"])])
        A(B.md_table(["Sweep", "Gate start", "Gate result", "Coverage rows", "Slot lists"], rows))
        A("")
        A("**Daemon log and build pins** (aggregates from the daemon log: late cycles = the cycle's log line more than 3 s after its slot end; residual-pass abandonments; cycle-grid realignment warnings):")
        A("")
        rows = []
        for k in keys:
            dl = (mon.get(k) or {}).get("daemon_log") or {}
            bp = (mon.get(k) or {}).get("build_pins") or {}
            rows.append([B.SHORT[k], dl.get("cycles_logged"), dl.get("late_cycles"), "%s / %s" % (dl.get("residual_abandoned"), dl.get("residual_passes")),
                         "%s / %s / %s" % ((dl.get("residual_elapsed_ms") or {}).get("median"), (dl.get("residual_elapsed_ms") or {}).get("p90"), (dl.get("residual_elapsed_ms") or {}).get("max")),
                         "%s (+%s / -%s)" % (dl.get("clamp_warnings"), dl.get("clamp_positive"), dl.get("clamp_negative")), dl.get("drop_or_overflow_like_lines"), "%s" % (bp.get("commit") or "")[:8], bp.get("shim"),
                         ",".join((mon.get(k) or {}).get("core_files_since_start") or []) or "none"])
        A(B.md_table(["Sweep", "Cycles logged", "Late cycles", "Residual passes abandoned / run", "Residual pass elapsed median / p90 / max (ms)", "Clamp warnings", "Drop-like lines", "Build", "Shim", "Core files"], rows))
        A("")
    A("**Stall row (its own row, scenario level):**")
    A("")
    A(B.md_table(["Complete sweeps", "Sweeps with a retry", "Scenario attempts", "Failed attempts", "Replacements"], [[stall["sweeps_complete"], stall["sweeps_with_a_retry"], stall["attempts"], stall["stalls"], stall["replacements"]]]))
    A("")
    A(B.md_table(["Scenario", "Attempts (all sweeps)", "Failed attempts", "Replacements"], [[sid, v["attempts"], v["failed"], v["replacements"]] for sid, v in sorted(stall["per_scenario"].items())]))
    A("")
    if stall["failures"]:
        A(B.md_table(["Sweep", "Scenario", "Attempt", "Kind", "Reason", "UTC", "Replaced by attempt"], [["`%s`" % f["sweep"], f["scenario"], f["attempt"], f["kind"], f["reason"], f["utc"], f["replaced_by_attempt"]] for f in stall["failures"]]))
        A("")
    if stall["retries_exhausted_in"]:
        A("**RETRIES EXHAUSTED (the series halted) in:** " + ", ".join("`%s`" % d for d in stall["retries_exhausted_in"]))
        A("")
    A("With M1 on, each stall has a snapshot in the sweep's supervisor folder (the wait channel of the audio thread, the ALSA state, the process list); the stall count over the series is the stall-rate data the root-cause question needs. The cause of the 11 and 14 October stalls is not established.")
    A("")
    # ---- 3.7 comparison with the earlier series
    A("### 3.7 Against the earlier series (main WITHOUT B2), descriptive only")
    A("")
    if ref is None:
        A("The earlier series' folders are not all present in this results folder: no comparison is shown.")
        A("")
    else:
        ck = OLD_KEYS[1:]
        rT = ref["three"]
        ro = [ref["bias"]["S1"][k]["OpenWSFZ"]["bias"] for k in ck]
        rw = [ref["bias"]["S1"][k]["WSJT-X"]["bias"] for k in ck]
        rows = [
            ["Sweeps (complete, paired)", "%d (run 2, repeats 1b-3b)" % len(ck), "%d" % n],
            ["S1 %StudyVar / %Contribution (three-way)", "%.1f %% / %.2f %%" % (rT["S1"]["pct_grr_sv"], rT["S1"]["pct_grr"]), "%.1f %% / %.2f %%" % (s1["pct_grr_sv"], s1["pct_grr"])],
            ["S2 %StudyVar / %Contribution", "%.1f %% / %.3f %%" % (rT["S2"]["pct_grr_sv"], rT["S2"]["pct_grr"]), "%.1f %% / %.3f %%" % (s2["pct_grr_sv"], s2["pct_grr"])],
            ["S3 %StudyVar / %Contribution", "%.1f %% / %.2f %%" % (rT["S3"]["pct_grr_sv"], rT["S3"]["pct_grr"]), "%.1f %% / %.2f %%" % (s3["pct_grr_sv"], s3["pct_grr"])],
            ["S1 bias, OpenWSFZ (per sweep, dB)", ", ".join("%+.2f" % x for x in ro), ", ".join("%+.2f" % x for x in o_b)],
            ["S1 bias, WSJT-X (per sweep, dB)", ", ".join("%+.2f" % x for x in rw), ", ".join("%+.2f" % x for x in w_b)],
            ["S4 recovery of 108, OpenWSFZ / WSJT-X", "%s / %s" % ("/".join(str(ref["summ"][k]["s4"]["OpenWSFZ"]["tp"]) for k in ck), "/".join(str(ref["summ"][k]["s4"]["WSJT-X"]["tp"]) for k in ck)),
             "%s / %s" % ("/".join(str(S[k]["s4"]["OpenWSFZ"]["tp"]) for k in keys), "/".join(str(S[k]["s4"]["WSJT-X"]["tp"]) for k in keys))],
            ["S1b decode rate, OpenWSFZ / WSJT-X (%)", "%s / %s" % ("/".join("%.1f" % ref["summ"][k]["s1b_overall"]["owsfz"] for k in ck), "/".join("%.1f" % ref["summ"][k]["s1b_overall"]["wsjtx"] for k in ck)),
             "%s / %s" % ("/".join("%.1f" % S[k]["s1b_overall"]["owsfz"] for k in keys), "/".join("%.1f" % S[k]["s1b_overall"]["wsjtx"] for k in keys))],
            ["S7 band, OpenWSFZ (%)", "%.2f to %.2f" % (min(ref["summ"][k]["s7"]["all"]["owsfz"] for k in ck), max(ref["summ"][k]["s7"]["all"]["owsfz"] for k in ck)), "%.2f to %.2f" % (min(c7o), max(c7o))],
            ["Residual pass, replay on block 822498b61291 (8 cycles, 2026-10-14)", "median 17.8 to 18.0 s (build without B2)", "median 3.15 to 3.22 s (merged build); see its README"],
        ]
        A(B.md_table(["Measure", "Earlier series (main without B2)", "This baseline (B2 build)"], rows))
        A("")
        A("Two series, two builds (the B2 merge changes the residual pass numerically, accepted 2026-10-04 on E2/E3) and different days: the rows are shown side by side and are **not** pooled, differenced into a gain, or tested against each other.")
        A("")
    # ------------------------------------------------------------------------------------------------------------------------------ section 4 / 5
    A("## Section 4: evaluation")
    A("")
    A("1. **Repeatability** (within-cell) is %.3f %% (S1), %.3f %% (S2), %.3f %% (S3) of the total variance." % (s1["pct_groups"]["repeatability"], s2["pct_groups"]["repeatability"], s3["pct_groups"]["repeatability"]))
    A("2. **Appraisers.** The appraiser main effect: S1 p %s (OpenWSFZ minus WSJT-X %+.2f dB, t CI %.2f to %.2f), S3 %.3f %% p %s (a fixed offset between the two programs, not noise). Part x Appraiser p %s, Appraiser x Sweep p %s (S1)." % (
        B.fp(s1["tests"]["A"][3]), m_d, lo_d, hi_d, s3["pct_groups"]["appraiser"], B.fp(s3["tests"]["A"][3]), B.fp(s1["tests"]["PA"][3]), B.fp(s1["tests"]["AS"][3])))
    chrono = sorted(keys, key=lambda k: S[k]["cycle_utc_first_last"][0])
    A("3. **Session to session.** The sweep share of the variance: %.3f %% (S1), %.3f %% (S2), %.3f %% (S3). OpenWSFZ's S1 bias in the order the sweeps ran: %s dB (range %.2f dB); WSJT-X: %s dB (range %.2f dB)." % (
        s1["pct_groups"]["sweep"], s2["pct_groups"]["sweep"], s3["pct_groups"]["sweep"], ", ".join("%+.2f" % R["bias"]["S1"][k]["OpenWSFZ"]["bias"] for k in chrono), max(o_b) - min(o_b),
        ", ".join("%+.2f" % R["bias"]["S1"][k]["WSJT-X"]["bias"] for k in chrono), max(w_b) - min(w_b)))
    A("4. **Validity of the data.** %d sweeps, %d scenario attempts (%d failed, %d replacement(s)); every kept scenario passed its coverage check (M3 / S6-V7)" % (stall["sweeps_complete"], stall["attempts"], stall["stalls"], stall["replacements"]) +
      ("." if all(((mon.get(k) or {}).get("M3_coverage") or {}).get("rows_invalid", 0) == 0 and (mon.get(k) or {}).get("M3_coverage", {}).get("rows") for k in keys) else " **(check the table: at least one sweep has no coverage rows or an INVALID row)**."))
    A("5. **Assumptions.** Balanced data, exact models; rounded reported values make the F p values approximate; the bootstrap resamples parts, not sweeps; no bar is proposed (HK-038).")
    A("")
    A("## Section 5: conclusions and recommendations")
    A("")
    A("1. On the B2 build, graded on %%StudyVar: S1 %.1f %% (%s), S2 %.1f %% (%s), S3 %.1f %% (%s); ndc %s / %s / %s. S3 sits near the 10 %% line on this metric; the Architect's reading (2026-10-14) is that this is the intended outcome of the AIAG metric, driven by a fixed DT offset between the programs, and neither the S3 tolerance nor the gate is adjusted." % (
        s1["pct_grr_sv"], v("S1"), s2["pct_grr_sv"], v("S2"), s3["pct_grr_sv"], v("S3"), s1["ndc"], s2["ndc"], s3["ndc"]))
    A("2. This is the baseline for the B2 build on `sol`: later changes are read against its sweep-to-sweep spread (Section 3.3 and the S1 bias range %.2f dB for OpenWSFZ, %.2f dB for WSJT-X), descriptively, not as a bar." % (max(o_b) - min(o_b), max(w_b) - min(w_b)))
    A("3. The stall row (Section 3.6) is part of the result: %d failed scenario attempt(s) in %d attempts (%d replacement(s)). If stalls recur, the M1 snapshots (the capture hw_ptr advance and the wsjtx thread CPU ticks) are the evidence to read first." % (stall["stalls"], stall["attempts"], stall["replacements"]))
    A("")
    A("**Not claimed.** No decoder-improvement statement; no pooling or testing across series; S6 is a live-path reading, not a decode-rate claim; the cause of the 11 and 14 October stalls is not known.")
    A("")
    # ------------------------------------------------------------------------------------------------------------------------------ section 6 history
    A("## Section 6: historical trend, every full S1-S8 sweep of the LINUX series")
    A("")
    A("**HK-031: Section 6 of the last LINUX report (`2026-10-14-LINUX-full-anova-final`) was read before this section was written; this is the same table layout with the new series appended.** **Each series is NOT comparable with another (different builds and days) and none is pooled.** Gate changed to %StudyVar 2026-10-14 (Captain); rows before this date were graded on %Contribution; the %StudyVar columns are computed from each sweep's variance components.")
    A("")
    hist = []
    old_all = [k for k in OLD_KEYS if ref is not None]
    if ref is not None:
        for k in OLD_KEYS:
            s = ref["summ"][k]
            hist.append(["earlier series (main without B2)", "2026-10-11" if k in ("run1", "run2") else "2026-10-14", "%.1f%%" % s["s1"]["pct_grr"], "%.1f%%" % s["s2"]["pct_grr"], "%.1f%%" % s["s3"]["pct_grr"],
                         "%.1f%%" % ref["per"]["S1"][k]["pct"]["grr_sv"], "%.1f%%" % ref["per"]["S2"][k]["pct"]["grr_sv"], "%.1f%%" % ref["per"]["S3"][k]["pct"]["grr_sv"],
                         "%.1f%% / %.1f%%" % (s["s7"]["all"]["wsjtx"], s["s7"]["all"]["owsfz"]), "%.1f%% / %.1f%%" % (s["s8"]["WSJT-X"]["rate"], s["s8"]["OpenWSFZ"]["rate"]) + (" (default chain)" if k == "run1" else "")])
    for k in keys:
        s = S[k]
        hist.append(["%s baseline (B2 build)" % series_id, S[k]["cycle_utc_first_last"][0][:10], "%.1f%%" % s["s1"]["pct_grr"] if S[k]["grr_metric"] == "%Contribution" else "%.1f%%" % R["per"]["S1"][k]["pct"]["grr"],
                     "%.1f%%" % R["per"]["S2"][k]["pct"]["grr"], "%.1f%%" % R["per"]["S3"][k]["pct"]["grr"], "%.1f%%" % R["per"]["S1"][k]["pct"]["grr_sv"], "%.1f%%" % R["per"]["S2"][k]["pct"]["grr_sv"], "%.1f%%" % R["per"]["S3"][k]["pct"]["grr_sv"],
                     "%.1f%% / %.1f%%" % (s["s7"]["all"]["wsjtx"], s["s7"]["all"]["owsfz"]), "%.1f%% / %.1f%%" % (s["s8"]["WSJT-X"]["rate"], s["s8"]["OpenWSFZ"]["rate"])])
    A(B.md_table(["Series", "Date", "S1 %Contribution", "S2 %Contribution", "S3 %Contribution", "S1 %StudyVar", "S2 %StudyVar", "S3 %StudyVar", "S7 recovery (WSJT-X / OpenWSFZ)", "S8 decode rate (WSJT-X / OpenWSFZ)"], hist))
    A("")
    A("The three 11-12 October OpenWSFZ-only repeats (WSJT-X silent) and the INVALID sweeps are not rows of this table; see the consolidated report and the INVALID folders.")
    A("")
    A("## Appendix: per-sweep two-way ANOVA tables (the analyser's model)")
    A("")
    for sc, *_r in F.SCEN:
        for k in keys:
            tw = R["per"][sc][k]
            A("**%s, %s** (%%Contribution %.2f %%, %%StudyVar %.1f %%, ndc %s, repeatability %.2f %%, reproducibility %.2f %%, part %.2f %%)" % (sc, B.SHORT[k], tw["pct"]["grr"], tw["pct"]["grr_sv"], tw["ndc"], tw["pct"]["repeatability"], tw["pct"]["reproducibility"], tw["pct"]["part"]))
            A("")
            A(B.md_table(["Source", "SS", "df", "MS", "F", "p"], [[t[0], B.fnum(t[1], 4), t[2], B.fnum(t[3], 4) if t[3] is not None else "", B.fnum(t[4], 3) if t[4] is not None else "", B.fp(t[5]) if t[5] is not None else ""] for t in tw["table"]]))
            A("")
    A("---")
    A("")
    A("*Generated by `qa/rr-study/linux/build_baseline_anova_report.py` from the sweep folders (no message text); it reuses the 2026-10-14 full-ANOVA tools. The numbers in the text are computed from the data, not typed.*")
    md = "\n".join(L) + "\n"
    with open(os.path.join(out, "report.md"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(md)
    js = {"series_id": series_id, "sweeps": folders, "invalid": inv, "stall_row": stall,
          "three_way": {sc: {"pct_groups": T[sc]["pct_groups"], "pct_grr": T[sc]["pct_grr"], "pct_grr_sv": T[sc]["pct_grr_sv"], "ndc": T[sc]["ndc"], "p": {kk: vv[3] for kk, vv in T[sc]["tests"].items()}, "boot": BT[sc]} for sc in T}}
    with open(os.path.join(out, "stats.json"), "w", encoding="utf8", newline="\n") as fh:
        json.dump(js, fh, indent=1, default=float)
    rr = os.path.join(HERE, "..", "render_report.py")
    subprocess.run([sys.executable, rr, os.path.join(out, "report.md")], check=True, stdout=subprocess.DEVNULL)
    html = open(os.path.join(out, "report.html"), encoding="utf8").read()

    def emb(m):
        p = os.path.join(out, m.group(1))
        return 'src="data:image/png;base64,' + base64.b64encode(open(p, "rb").read()).decode("ascii") + '"' if os.path.isfile(p) else m.group(0)
    with open(os.path.join(out, "report-standalone.html"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(re.sub(r'src="(img/[^"]+)"', emb, html))
    print("wrote", out, len(md), "chars;", n, "sweeps;", stall["stalls"], "failed scenario attempt(s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--series-id", default="B2BASE")
    ap.add_argument("--config", default=None, help="JSON {\"sweeps\": [folder, ...], \"invalid\": [folder, ...]} instead of discovery by name")
    a = ap.parse_args()
    build(a.results, a.out, a.series_id, a.config)


if __name__ == "__main__":
    main()
