"""Extract the numbers of the LINUX series' sweeps from their run folders (QA tooling; aggregates only, no message text leaves).

    python consolidate_data.py --results <results root> --out <json>

The five sweeps (host `sol`): run 1 (default ALSA chain), run 2 (corrected chain, the assembled report), repeats 1-3 (corrected chain).
Everything is read from each folder's own files: report.md (summary, S1b, S4, S7, S8), the *_matched.csv files (S1 bias by SNR, S2/S3
errors, S7+S8 pooled counts, cycle times), arm_config.json (build, library, flags), s3c/s3c_result.json (S3c).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics as st
from collections import defaultdict

SWEEPS = [
    ("run1", "2026-10-11-64246e4-LINUX-sol", "Run 1: DEFAULT ALSA chain (out of the box)", False),
    ("run2", "2026-10-11-64246e4-LINUX-sol-SAMPLERATE-chain", "Run 2: corrected chain (samplerate_best)", True),
    ("rep1", "2026-10-11-64246e4-LINUX-sol-SAMPLERATE-chain-REPEAT1", "Repeat 1: corrected chain", True),
    ("rep2", "2026-10-11-64246e4-LINUX-sol-SAMPLERATE-chain-REPEAT2", "Repeat 2: corrected chain", True),
    ("rep3", "2026-10-11-64246e4-LINUX-sol-SAMPLERATE-chain-REPEAT3", "Repeat 3: corrected chain", True),
    # 2026-10-14: the corrected-chain repeats rerun WITH WSJT-X decoding (mechanical warm-up on). W2 is the REPLACEMENT for a sweep whose WSJT-X
    # stalled at 11:09:30Z (folder `...-WSJTX-REPEAT2`, INVALID, never read here).
    ("w1", "2026-10-14-64246e4-LINUX-sol-SAMPLERATE-chain-WSJTX-REPEAT1", "Repeat 1b: corrected chain, WSJT-X decoding", True),
    ("w2", "2026-10-14-64246e4-LINUX-sol-SAMPLERATE-chain-WSJTX-REPEAT2-REPLACEMENT", "Repeat 2b: corrected chain, WSJT-X decoding (replacement)", True),
    ("w3", "2026-10-14-64246e4-LINUX-sol-SAMPLERATE-chain-WSJTX-REPEAT3", "Repeat 3b: corrected chain, WSJT-X decoding", True),
]


def read_csv(path):
    with open(path, newline="", encoding="utf8") as fh:
        return list(csv.DictReader(fh))


def pct(s):
    # a summary cell can read "4.7% (%Contribution 0.2%, no verdict)" (the %StudyVar gate, 2026-10-14): the figure is the leading number
    m = re.match(r"\s*\**\s*(-?[\d.]+)", s)
    return float(m.group(1)) if m else float(s.replace("*", "").strip().rstrip("%"))


def summary_rows(md: str) -> list:
    i = md.index("## Summary")
    seg = md[i:md.index("**Overall verdict", i)]
    rows = []
    for line in seg.splitlines():
        m = re.match(r"^\| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", line)
        if m and m.group(1) not in ("Metric", "---"):
            rows.append(m.groups())
    return rows


def section(md: str, title_start: str, stop: str = "\n## ") -> str:
    i = md.index(title_start)
    j = md.find(stop, i + len(title_start))
    return md[i:j if j > 0 else len(md)]


def table_rows(seg: str) -> list:
    out = []
    for line in seg.splitlines():
        if line.startswith("|") and not re.match(r"^\|[-| ]+\|$", line):
            out.append([c.strip() for c in line.strip().strip("|").split("|")])
    return out


def one(results: str, key: str, folder: str, label: str, corrected: bool) -> dict:
    d = os.path.join(results, folder)
    md = open(os.path.join(d, "report.md"), encoding="utf8").read()
    arm = json.load(open(os.path.join(d, "arm_config.json"), encoding="utf8"))
    out = {"key": key, "folder": folder, "label": label, "corrected_chain": corrected}
    out["build"] = {"commit": arm["build"]["commit"], "dll_sha256": arm["daemon"]["dll_sha256"], "shim": arm["daemon"]["shim_version"],
                    "daemon_version": arm["daemon"]["daemon_version"], "readback": arm["daemon"]["decoder_readback"], "audio_device": arm["daemon"]["audio_device"],
                    "wsjtx_ndepth": arm["wsjtx"].get("NDepth"), "wsjtx_mode": arm["wsjtx"].get("mode"), "recorded_utc": arm["recorded_utc"]}
    out["overall"] = re.search(r"\*\*Overall verdict: (\w+)\*\*", md).group(1)
    out["summary"] = [{"metric": a, "scope": b, "value": c, "verdict": v} for a, b, c, v in summary_rows(md)]
    sm = {(a, b): (c, v) for a, b, c, v in summary_rows(md)}
    # From 2026-10-14 the analyser's row is "%GR&R (%StudyVar)" (the gate metric moved from %Contribution to %StudyVar); reports before that date
    # carry "%GR&R" (= %Contribution). The figure is read from whichever row exists and the metric is recorded, never silently mixed.
    out["grr_metric"] = "%StudyVar" if ("%GR&R (%StudyVar)", "S1") in sm else "%Contribution"
    g = lambda m, s: sm[("%GR&R (%StudyVar)" if (m == "%GR&R" and ("%GR&R (%StudyVar)", s) in sm) else m, s)]
    out["s1"] = {"pct_grr": pct(g("%GR&R", "S1")[0]), "ndc": float(g("ndc", "S1")[0]), "bias_owsfz": float(g("SNR bias", "S1/OpenWSFZ")[0].split()[0]),
                 "bias_wsjtx": float(g("SNR bias", "S1/WSJT-X")[0].split()[0]) if ("SNR bias", "S1/WSJT-X") in sm else None,
                 "bias_verdict": g("SNR bias", "S1/OpenWSFZ")[1], "pct_grr_verdict": g("%GR&R", "S1")[1], "ndc_verdict": g("ndc", "S1")[1]}
    out["s2"] = {"pct_grr": pct(g("%GR&R", "S2")[0]), "ndc": float(g("ndc", "S2")[0]), "ndc_verdict": g("ndc", "S2")[1]}
    out["s3"] = {"pct_grr": pct(g("%GR&R", "S3")[0]), "ndc": float(g("ndc", "S3")[0]), "ndc_verdict": g("ndc", "S3")[1]}
    out["kappa"] = {k: float(g("Kappa (advisory)", k)[0]) for k in ("OpenWSFZ_vs_truth", "WSJT-X_vs_truth", "between_appraisers") if ("Kappa (advisory)", k) in sm}
    out["s5"] = {"gate_aw": g("FP event rate (95% UB), Gate A-W", "S5/OpenWSFZ")[0], "gate_ad": g("FP event rate change, Gate A-Δ", "S5/OpenWSFZ")[0],
                 "check_b_w": g("FP events, Check B (narrowband)", "S5/WSJT-X")[0], "check_b_o": g("FP events, Check B (narrowband)", "S5/OpenWSFZ")[0]}
    # S1b
    s1b = table_rows(section(md, "### Per-part decode rate", "\n**Overall"))
    out["s1b"] = [{"part": r[0], "snr": float(r[1]), "w": r[2], "w_rate": pct(r[3]), "o": r[4], "o_rate": pct(r[5])} for r in s1b[1:]]
    mo = re.search(r"Overall decode rate — WSJT-X: ([\d.]+)%  OpenWSFZ: ([\d.]+)%", md)
    out["s1b_overall"] = {"wsjtx": float(mo.group(1)), "owsfz": float(mo.group(2))}
    # S4 confusion
    conf = table_rows(section(md, "### Confusion vs truth", "\n### "))
    out["s4"] = {r[0]: {"tp": int(r[1]), "fn": int(r[2]), "fp": int(r[3]), "tn": int(r[4]), "recovery": pct(r[5]), "specificity": pct(r[6])} for r in conf[1:]}
    # S7
    s7 = table_rows(section(md, "### Recovery by overlap family", "\n### "))
    out["s7"] = {r[0].replace("*", ""): {"wsjtx": pct(r[1]), "owsfz": pct(r[2])} for r in s7[1:]}
    # S8
    s8 = table_rows(section(md, "### Overall decode rate", "\n**Between"))
    out["s8"] = {r[0]: {"decoded": int(r[1]), "injected": int(r[2]), "rate": pct(r[3])} for r in s8[1:]}
    # matched CSVs: S1 bias by SNR, S2/S3 errors, pooled S7+S8, cycle times
    s1 = read_csv(os.path.join(d, "S1_matched.csv"))
    by = defaultdict(list)
    for r in s1:
        if r["matched"] == "True" and r["reported_snr_db"] != "":
            by[(r["appraiser"], float(r["true_snr_db"]))].append(float(r["reported_snr_db"]) - float(r["true_snr_db"]))
    out["s1_bias_by_snr"] = {a: {str(s): {"mean": round(st.mean(v), 3), "sd": round(st.pstdev(v), 3), "n": len(v)} for (aa, s), v in sorted(by.items()) if aa == a}
                             for a in ("WSJT-X", "OpenWSFZ")}
    s1_det = defaultdict(lambda: [0, 0])
    for r in s1:
        s1_det[r["appraiser"]][1] += 1
        s1_det[r["appraiser"]][0] += r["matched"] == "True"
    out["s1_decoded"] = {a: v for a, v in s1_det.items()}
    pooled = defaultdict(int)
    for sc in ("S7", "S8"):
        for r in read_csv(os.path.join(d, sc + "_matched.csv")):
            if r["matched"] == "True":
                pooled[r["appraiser"]] += 1
    out["s78_pooled_matched"] = dict(pooled)
    times = []
    for f in os.listdir(d):
        if f.endswith("_matched.csv"):
            times += [r["cycle_utc"] for r in read_csv(os.path.join(d, f)) if r["cycle_utc"]]
    out["cycle_utc_first_last"] = [min(times), max(times)] if times else None
    try:
        s3c = json.load(open(os.path.join(d, "s3c", "s3c_result.json"), encoding="utf8"))
        parts = [p for dec in s3c["decoders"].values() for p in dec["parts"].values()]
        out["s3c"] = {"parts": len(parts), "pass": sum(1 for p in parts if p.get("pass")), "descriptive": sum(1 for p in parts if p.get("descriptive"))}
    except (OSError, KeyError, ValueError):
        out["s3c"] = None
    def nlines(f):
        with open(os.path.join(d, f), encoding="utf8", errors="replace") as fh:
            return sum(1 for _ in fh)
    out["wsjt_all_lines"], out["owsfz_all_lines"] = nlines("wsjt-all.txt"), nlines("owsfz-all.txt")
    out["wsjtx_present"] = out["wsjt_all_lines"] > 0
    try:
        out["s3c_failed_parts"] = sorted("%s/%s" % (dn, pn) for dn, dec in s3c["decoders"].items() for pn, p in dec["parts"].items() if not p.get("pass"))
    except (NameError, KeyError, TypeError):
        out["s3c_failed_parts"] = None
    if not out["wsjtx_present"]:           # a missing appraiser is "no data", never a zero rate
        for r in out["s1b"]:
            r["w"], r["w_rate"] = None, None
        out["s1b_overall"]["wsjtx"] = None
        out["s4"].pop("WSJT-X", None)
        for fam in out["s7"].values():
            fam["wsjtx"] = None
        out["s8"].pop("WSJT-X", None)
        out["s1"]["bias_wsjtx"] = None
    lab = os.path.join(d, "CHAIN-LABEL.txt")
    out["chain_label"] = open(lab, encoding="utf8").read().strip() if os.path.isfile(lab) else None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = {"sweeps": [one(a.results, *s) for s in SWEEPS]}
    with open(a.out, "w", encoding="utf8", newline="\n") as fh:
        json.dump(data, fh, indent=1)
    for s in data["sweeps"]:
        print(s["key"], s["overall"], "wsjtx_present", s["wsjtx_present"], "S3c", s["s3c"], s["s3c_failed_parts"], s["cycle_utc_first_last"])


if __name__ == "__main__":
    main()
