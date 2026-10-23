"""Side-by-side summary of one R&R series on `sol` (QA tooling; aggregates only, NFR-021). QA 2026-10-23.

    python build_series_summary.py --results <results root> --series DI7COH2 --reference MAINDEEP --out <folder>

Reads each <date>-<sha7>-<SERIES>-sweep<n> folder (report.md, depth_readback.json, flag_readback.json, scenario_retries.json,
f2_record.json, capture_counters.txt) and, for comparison, the single sweep folder named *-<REFERENCE>-sweep1.
It does NOT pool sweeps and does NOT compute a new statistic: every figure is copied from the sweep's own report or sidecar
files, and the script asserts each one was found. Writes <out>/report.md, <out>/data.json, <out>/img/s6_consistency.png.
Rendering to HTML is a separate step (render_report.py), as for every other report.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CI = r"(\d+\.\d+) % \[(\d+\.\d+), (\d+\.\d+)\]"
N_SWEEPS = 3


def must(m, what, where):
    if not m:
        sys.exit(f"NOT FOUND: {what} in {where}")
    return m


def s6_block(text):
    i = text.index("### S6 ")
    j = text.index("**Sensitivity", i)
    return text[i:j]


def parse_report(path):
    t = open(path, encoding="utf8").read()
    out = {}
    out["verdict"] = must(re.search(r"\*\*Overall verdict: (\w+)\*\*", t), "overall verdict", path).group(1)
    # summary table rows
    rows = {}
    sec = t[t.index("## Summary"):t.index("**Overall verdict")]
    for m in re.finditer(r"^\| ([^|]+) \| ([^|]+) \| ([^|]+) \| (PASS|MARGINAL|FAIL)[^|]* \|$", sec, re.M):
        rows[(m.group(1).strip(), m.group(2).strip())] = (m.group(3).strip(), m.group(4))
    out["summary"] = {f"{k[0]} / {k[1]}": v for k, v in rows.items() if not k[0].startswith("Coverage")}
    out["coverage_all_pass"] = all(v[1] == "PASS" for k, v in rows.items() if k[0].startswith("Coverage"))
    out["coverage_rows"] = sum(1 for k in rows if k[0].startswith("Coverage"))
    b = s6_block(t)
    own = must(re.search(r"own universe[^|]*\| " + CI + r" \| " + CI + r" \|", b), "S6 own-universe row", path)
    leg = must(re.search(r"legacy[^|]*\| " + CI + r" \| " + CI + r" \|", b), "S6 legacy row", path)
    dpw = must(re.search(r"decodes per WAV \(non-hashed[^|]*\| (\d+\.\d+) \[[^\]]+\] \| (\d+\.\d+) \[[^\]]+\] \|", b), "S6 decodes/WAV", path)
    pos = must(re.search(r"Positive agreement[^\n]*?: \*\*(\d+\.\d+) % \[(\d+\.\d+), (\d+\.\d+)\]\*\*", b), "S6 positive agreement", path)
    snr = must(re.search(r"mean (-?\d+\.\d+) dB \[(-?\d+\.\d+), (-?\d+\.\d+)\], SD (\d+\.\d+) dB", b), "S6 SNR delta", path)
    val = must(re.search(r"\*\*Validity\*\*[^:]*: (.+?)\. \*\*S6-V2\(d\) onset: (\w+)\*\*", b), "S6 validity", path)
    out["s6"] = {
        "wsjtx_own": [float(x) for x in own.groups()[:3]], "owsfz_own": [float(x) for x in own.groups()[3:]],
        "wsjtx_legacy": [float(x) for x in leg.groups()[:3]], "owsfz_legacy": [float(x) for x in leg.groups()[3:]],
        "dpw_wsjtx": float(dpw.group(1)), "dpw_owsfz": float(dpw.group(2)),
        "pos_agree": [float(x) for x in pos.groups()],
        "snr_delta": [float(x) for x in snr.groups()],
        "validity": val.group(1), "onset": val.group(2),
    }
    s1b = must(re.search(r"\*\*Overall decode rate . WSJT-X: (\S+)\s+OpenWSFZ: (\S+)\*\*", t), "S1b overall", path)
    out["s1b"] = {"wsjtx": s1b.group(1), "owsfz": s1b.group(2)}
    s7 = must(re.search(r"\| \*\*all\*\* \| \*\*(\S+)\*\* \| \*\*(\S+)\*\* \|", t), "S7 all-family row", path)
    out["s7"] = {"wsjtx": s7.group(1), "owsfz": s7.group(2)}
    co = must(re.search(r"\| co_channel \| (\S+) \| (\S+) \|", t), "S7 co_channel row", path)
    out["s7_co_channel"] = {"wsjtx": co.group(1), "owsfz": co.group(2)}
    s8 = re.search(r"### Overall decode rate\s+\| Appraiser[^\n]*\n\|[-| ]+\|\n\| WSJT-X \| \d+ \| \d+ \| (\S+) \|\n\| OpenWSFZ \| \d+ \| \d+ \| (\S+) \|", t)
    must(s8, "S8 overall rates", path)
    out["s8"] = {"wsjtx": s8.group(1), "owsfz": s8.group(2)}
    return out


def parse_sidecars(d):
    r = {}
    for name in ("depth_readback", "flag_readback", "scenario_retries", "f2_record"):
        p = os.path.join(d, name + ".json")
        r[name] = json.load(open(p, encoding="utf8")) if os.path.exists(p) else None
    cc = os.path.join(d, "capture_counters.txt")
    r["capture_counters"] = open(cc, encoding="utf8").read() if os.path.exists(cc) else None
    return r


def counter(text, label):
    m = re.search(label + r":\s+(\d+)", text or "")
    return int(m.group(1)) if m else None


def residual(text):
    m = re.search(r"n=(\d+) median=(\d+) ms p90=(\d+) ms max=(\d+) ms abandoned=(\d+)", text or "")
    return [int(x) for x in m.groups()] if m else None


def find_sweeps(root, series):
    d = sorted(glob.glob(os.path.join(root, f"*-{series}-sweep[0-9]*")))
    return [x for x in d if "captured-audio" not in x]


def load(d):
    r = parse_report(os.path.join(d, "report.md"))
    r.update(parse_sidecars(d))
    r["folder"] = os.path.basename(d.rstrip("/\\"))
    return r


def fmt(v):
    return f"{v[0]:.1f} [{v[1]:.1f}, {v[2]:.1f}]"


def build(args):
    sweeps = find_sweeps(args.results, args.series)
    assert len(sweeps) == N_SWEEPS, f"expected {N_SWEEPS} sweeps of {args.series}, found {len(sweeps)}"
    S = [load(d) for d in sweeps]
    refd = find_sweeps(args.results, args.reference)
    assert len(refd) == 1, f"expected exactly one {args.reference} sweep, found {len(refd)}"
    R = load(refd[0])
    for s in S:  # the validity rows must be VALID or the sweep is not reported as a result
        assert s["depth_readback"]["result"] == "VALID", s["folder"]
        assert s["flag_readback"]["result"] == "VALID", s["folder"]

    os.makedirs(os.path.join(args.out, "img"), exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    labels = [f"sweep {i + 1}" for i in range(N_SWEEPS)] + [args.reference]
    for k, (key, col, off) in enumerate((("wsjtx_own", "#3fb950", -0.12), ("owsfz_own", "#58a6ff", 0.12))):
        for i, s in enumerate(S + [R]):
            v = s["s6"][key]
            ax.errorbar(i + off, v[0], yerr=[[v[0] - v[1]], [v[2] - v[0]]], fmt="o", color=col, capsize=3,
                        label=("WSJT-X" if key == "wsjtx_own" else "OpenWSFZ") if i == 0 else None)
    ax.axhline(93.9, ls="--", lw=0.8, color="#888")
    ax.text(len(labels) - 0.5, 93.95, "tripwire 93.9 %", ha="right", va="bottom", fontsize=8, color="#666")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_ylabel("S6 consistency, own universe (%)")
    ax.set_title("S6 within-appraiser consistency, WAV-clustered 95 % CI (each sweep alone; no pooling)", fontsize=9)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "img", "s6_consistency.png"), dpi=130)
    plt.close(fig)

    L = []
    w = L.append
    w(f"# {args.series}: side-by-side report of {N_SWEEPS} sweeps on `sol`\n")
    w("Built by `qa/rr-study/linux/build_series_summary.py` from each sweep's own `report.md` and sidecar files. **Nothing is pooled and no new statistic is computed:** "
      "every figure is copied from the sweep's own report; the script asserts each one was found and that the depth and flag read-backs are VALID. "
      f"The comparison column is `{R['folder']}` (reference series {args.reference}, same rig, a different build: the figures differ across a build change, so the comparison is descriptive and not a measurement of one change alone).\n")
    w("## Sweeps\n")
    w("| | " + " | ".join(f"sweep {i + 1}" for i in range(N_SWEEPS)) + f" | {args.reference} |")
    w("|---|" + "---|" * (N_SWEEPS + 1))
    row = lambda name, f: w(f"| {name} | " + " | ".join(f(s) for s in S + [R]) + " |")
    row("folder", lambda s: f"`{s['folder']}`")
    row("battery verdict", lambda s: f"**{s['verdict']}**")
    row("depth read-back (V-D)", lambda s: f"{s['depth_readback']['result']} ({s['depth_readback']['polls_with_a_readback']} polls, {s['depth_readback']['distinct'][0]})" if s["depth_readback"] else "n/a")
    row("fallback line (V-F)", lambda s: f"{s['flag_readback']['result']} ({s['flag_readback']['fallback_lines']}/{s['flag_readback']['cycle_lines']} cycles)" if s["flag_readback"] else "n/a (not in this series)")
    row("scenario attempts / failed", lambda s: "{}/{}".format(sum(v["attempts"] for v in s["scenario_retries"]["scenarios"].values()), sum(len(v["failed"]) for v in s["scenario_retries"]["scenarios"].values())) if s["scenario_retries"] else "n/a")
    w("")
    w("## Section 6: S6 off-air replay, sequential, 180 plays\n")
    w("| figure | " + " | ".join(f"sweep {i + 1}" for i in range(N_SWEEPS)) + f" | {args.reference} |")
    w("|---|" + "---|" * (N_SWEEPS + 1))
    row("WSJT-X consistency, own universe (%)", lambda s: fmt(s["s6"]["wsjtx_own"]))
    row("OpenWSFZ consistency, own universe (%)", lambda s: fmt(s["s6"]["owsfz_own"]))
    row("OpenWSFZ consistency, legacy universe (%)", lambda s: fmt(s["s6"]["owsfz_legacy"]))
    row("decodes per WAV, WSJT-X / OpenWSFZ", lambda s: f"{s['s6']['dpw_wsjtx']:.2f} / {s['s6']['dpw_owsfz']:.2f}")
    row("positive agreement (%)", lambda s: fmt(s["s6"]["pos_agree"]))
    row("SNR delta OpenWSFZ - WSJT-X (dB)", lambda s: f"{s['s6']['snr_delta'][0]:.2f} [{s['s6']['snr_delta'][1]:.2f}, {s['s6']['snr_delta'][2]:.2f}]")
    row("S6 validity", lambda s: s["s6"]["validity"].replace(" PASS", "").replace("; ", " ") + f" PASS; onset {s['s6']['onset']}")
    w("\n![S6 consistency per sweep](img/s6_consistency.png)\n")
    w("## Battery summary rows (verdicts as the report states them)\n")
    keys = sorted({k for s in S + [R] for k in s["summary"]})
    w("| row | " + " | ".join(f"sweep {i + 1}" for i in range(N_SWEEPS)) + f" | {args.reference} |")
    w("|---|" + "---|" * (N_SWEEPS + 1))
    for k in keys:
        w(f"| {k} | " + " | ".join((f"{s['summary'][k][0]} ({s['summary'][k][1]})" if k in s["summary"] else "-") for s in S + [R]) + " |")
    row("coverage rows all PASS", lambda s: f"{s['coverage_rows']} rows, {'all PASS' if s['coverage_all_pass'] else 'NOT all pass'}")
    w("\n## Other scenarios (informational)\n")
    w("| figure | " + " | ".join(f"sweep {i + 1}" for i in range(N_SWEEPS)) + f" | {args.reference} |")
    w("|---|" + "---|" * (N_SWEEPS + 1))
    row("S1b decode rate WSJT-X / OpenWSFZ", lambda s: f"{s['s1b']['wsjtx']} / {s['s1b']['owsfz']}")
    row("S7 recovery, all families, WSJT-X / OpenWSFZ", lambda s: f"{s['s7']['wsjtx']} / {s['s7']['owsfz']}")
    row("S7 co-channel family, WSJT-X / OpenWSFZ", lambda s: f"{s['s7_co_channel']['wsjtx']} / {s['s7_co_channel']['owsfz']}")
    row("S8 band scene, WSJT-X / OpenWSFZ", lambda s: f"{s['s8']['wsjtx']} / {s['s8']['owsfz']}")
    w("\n## Capture and timing counters (F2)\n")
    w("| figure | " + " | ".join(f"sweep {i + 1}" for i in range(N_SWEEPS)) + f" | {args.reference} |")
    w("|---|" + "---|" * (N_SWEEPS + 1))
    row("channel drops (daemon log)", lambda s: str(counter(s["capture_counters"], "channel drops")))
    row("clamped grid windows (daemon log)", lambda s: str(counter(s["capture_counters"], "clamped grid windows")))
    row("plays with a clamped cycle", lambda s: str(s["f2_record"]["plays_with_clamped_cycle"]) if s["f2_record"] else "n/a")
    row("placebo check (amendment 1)", lambda s: (s["f2_record"]["amendment1_check"] if isinstance(s["f2_record"]["amendment1_check"], str) else s["f2_record"]["amendment1_check"]["verdict"] + f" (without the clamped WAVs: {s['f2_record']['amendment1_check']['delta_pp']:+.2f} pp)") if s["f2_record"] else "n/a")
    row("residual pass, last daemon: n / median / p90 / max ms, abandoned", lambda s: "{} / {} / {} / {}, {}".format(*residual(s["capture_counters"])) if residual(s["capture_counters"]) else "n/a")
    w("\nBar for the residual pass: median <= 4,000 ms and 0 abandoned. The Architect closed the clamp look on 2026-10-23 (board, \"DI7COH2 CLAMP LOOK\"): keep reporting clamp counts and the placebo row; reopen only if clamps fall outside the placebo or the station shows one (the DI7COH-E station run had 0 clamps and 0 channel drops over 12 h).\n")
    w("## Reading rules\n")
    w("- The series is its own era row (DI7COH: `decoding_improvement` synced with `main`, fallback ON, Deep, `nhard` 24). Never pooled with MAINDEEP, TPDEEP, TPNORMAL, B2CAP, B2BASE or any concurrent S6.")
    w("- The WSJT-X tripwire is the Architect's (ruling 2026-10-17-2218): FLAG iff the WAV-clustered 95 % CI of the WSJT-X consistency excludes 93.9 %. It is a check on the rig, not a result about OpenWSFZ.")
    w("- Sampler rows (audio-setup) are PARTIAL on `sol` by construction (the Windows worker cannot run there).")
    open(os.path.join(args.out, "report.md"), "w", encoding="utf8").write("\n".join(L) + "\n")
    json.dump({"sweeps": [{k: v for k, v in s.items() if k != "capture_counters"} for s in S],
               "reference": {k: v for k, v in R.items() if k != "capture_counters"}}, open(os.path.join(args.out, "data.json"), "w", encoding="utf8"), indent=1)
    print("wrote", os.path.join(args.out, "report.md"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--series", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--out", required=True)
    build(ap.parse_args())
