"""S3c: score a battery's S3c playback against the pre-registered rows (spec 2026-10-02-1730 section 4).

    python s3c_score.py --scenario ../scenarios/s3c-edge-guard.json --run-dir <dir> \
        --wsjtx-alltxt <wsjt-all.txt> --owsfz-alltxt <owsfz-all.txt> \
        --subtraction-enabled true|false|unknown [--build-sha SHA] [--trend ../s3c_trend.csv]

For each part and decoder, X = matched of 32 (planted text exact, own cycle's boundary stamp,
|df| <= 10 Hz: the edge test's matcher, imported).  Rows, per the spec:

  S3c-WSJT-X (VALIDITY):  every WSJT-X part has X >= k*.  FAIL => the chain or the harness changed, not
                          our build; the OpenWSFZ rows of this battery are NOT READ (the report says so).
  S3c-OWSFZ  (GUARD):     every OpenWSFZ part has X >= k*.  FAIL is a FLAG to the Architect, not a verdict.
  A row with k* = 0 cannot fail: it is DESCRIPTIVE and excluded from the row verdict (but its X is
  reported).  4 parts x 2 decoders at 1 % each ~ 8 % chance of a false FAIL somewhere per battery
  (accepted by the spec: a FAIL triggers a repeat, not a ruling).

NFR-021 / HK-037: decoder message text is read only inside analysis.parse_all_txt, which keeps a line
iff its text is exactly one of this scenario's planted synthetic texts; the output is counts only.
Flag state is RECORDED and never pooled: the r_ref come from a flag-OFF edge run, so a flag-ON battery is
labelled 'S3c measured with subtractionEnabled=true (reference: flag OFF)'.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RR = HERE.parent
for p in (str(HERE), str(RR), str(RR / "lateness-edge")):
    if p not in sys.path:
        sys.path.insert(0, p)

import s3c_design as S  # noqa: E402
import analysis as EA  # noqa: E402  (the edge test's analysis.py)

PARTS = ("S3c-L90", "S3c-L50", "S3c-E90", "S3c-E50")
DECODERS = (("owsfz", "OpenWSFZ"), ("wsjtx", "WSJT-X"))
TREND_FIELDS = ["run_date", "build_sha", "subtraction_enabled", "dll_sha256_prefix"] + \
    [f"x_{d}_{p[4:].lower()}" for d in ("owsfz", "wsjtx") for p in PARTS] + \
    ["wsjtx_validity", "owsfz_guard", "wrong_cycle_decodes", "report_state"]


def score(scen: dict, wsjtx_alltxt: Path, owsfz_alltxt: Path, log_path: Path) -> dict:
    design = scen["design"]
    planted = {s["text"] for s in design["signals"]}
    boundaries = EA.read_playback_log(log_path)
    result: dict = {"scenario": S.SCENARIO_ID, "points": scen["points"], "decoders": {}}
    for dec, name in DECODERS:
        path = wsjtx_alltxt if dec == "wsjtx" else owsfz_alltxt
        rows, stamps, n_lines, n_other = EA.parse_all_txt(path, planted)
        matched, wrong = EA.match_decoder(design, boundaries, rows)
        per_part = {}
        for part in PARTS:
            sigs = [s for s in design["signals"] if s["cell"] == part]
            x = sum(1 for s in sigs if s["sig_id"] in matched)
            ref = scen["reference"][part][name]
            ok = x >= ref["k_star"]
            per_part[part] = {"L": scen["points"][part], "X": x, "n": len(sigs), "r_ref": ref["r_ref"],
                              "k_star": ref["k_star"], "descriptive": ref["descriptive"],
                              "pass": True if ref["descriptive"] else ok,
                              "rate": x / len(sigs)}
        result["decoders"][name] = {"parts": per_part, "alltxt_lines": n_lines, "alltxt_other_lines": n_other,
                                    "wrong_cycle_decodes": len(wrong),
                                    "planted_slots_with_decode_pass": sum(
                                        1 for i, b in boundaries.items()
                                        if design["cycles"][i]["planted"] and b in stamps)}
    wj = result["decoders"]["WSJT-X"]["parts"]
    ow = result["decoders"]["OpenWSFZ"]["parts"]
    validity = all(v["pass"] for v in wj.values())
    guard = all(v["pass"] for v in ow.values())
    result["rows"] = {
        "S3c-WSJT-X (validity)": "PASS" if validity else "FAIL",
        "S3c-OWSFZ (guard)": ("NOT READ (WSJT-X validity FAIL: the chain or the harness changed)"
                              if not validity else ("PASS" if guard else "FLAG (FAIL, to the Architect)")),
    }
    result["validity_pass"], result["guard_pass"] = validity, guard
    result["state"] = "VALID" if validity else "INVALID (OpenWSFZ rows not read)"
    return result


def render_md(res: dict, meta: dict) -> str:
    lines = ["# S3c start-time edge guard: result", ""]
    lines += [f"- Flag state: `subtractionEnabled = {meta['subtraction_enabled']}`"
              + ("  (reference rates from a flag-OFF edge run: labelled, never pooled)"
                 if meta["subtraction_enabled"] != "false" else ""),
              f"- Build: `{meta['build_sha']}`  DLL SHA-256 prefix: `{meta['dll_sha256_prefix']}`",
              f"- Scenario SHA-256: `{meta['scenario_sha256']}`", ""]
    lines += ["| decoder | part | L (s) | X / 32 | r_ref | k* | row |", "|---|---|---:|---:|---:|---:|---|"]
    for name in ("WSJT-X", "OpenWSFZ"):
        for part in PARTS:
            v = res["decoders"][name]["parts"][part]
            row = "DESCRIPTIVE (k* = 0)" if v["descriptive"] else ("PASS" if v["pass"] else "FAIL")
            lines.append(f"| {name} | {part} | {v['L']:+.2f} | {v['X']} | {v['r_ref']:.3f} | {v['k_star']} | {row} |")
    lines += ["", "## Rows", ""] + [f"- **{k}:** {v}" for k, v in res["rows"].items()]
    lines += ["", "A FAIL of the OpenWSFZ guard is a flag, not a verdict (one battery's 32 signals per part cannot tell "
              "a regression from bad luck at the 1 % level). ~8 % chance of at least one false FAIL somewhere per "
              "battery (4 parts x 2 decoders at 1 %), accepted by the spec. Counts only (NFR-021)."]
    for name in ("WSJT-X", "OpenWSFZ"):
        d = res["decoders"][name]
        lines.append(f"- {name}: planted slots with any decode pass {d['planted_slots_with_decode_pass']}/8; "
                     f"planted texts in the wrong cycle: {d['wrong_cycle_decodes']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--wsjtx-alltxt", required=True)
    ap.add_argument("--owsfz-alltxt", required=True)
    ap.add_argument("--subtraction-enabled", default="unknown", choices=["true", "false", "unknown"])
    ap.add_argument("--build-sha", default="unknown")
    ap.add_argument("--dll-sha256-prefix", default="unknown")
    ap.add_argument("--trend", default=None, help="append one row to this trend csv")
    a = ap.parse_args()
    import hashlib
    scen_path = Path(a.scenario)
    scen = json.loads(scen_path.read_text(encoding="utf-8"))
    out_dir = Path(a.run_dir) / "s3c"
    res = score(scen, Path(a.wsjtx_alltxt), Path(a.owsfz_alltxt), out_dir / "playback_log.csv")
    meta = {"subtraction_enabled": a.subtraction_enabled, "build_sha": a.build_sha,
            "dll_sha256_prefix": a.dll_sha256_prefix,
            "scenario_sha256": hashlib.sha256(scen_path.read_bytes().replace(b"
", b"
")).hexdigest()}  # LF-normalised: same on any checkout
    res["meta"] = meta
    (out_dir / "s3c_result.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "s3c_report.md").write_text(render_md(res, meta), encoding="utf-8")
    if a.trend:
        row = {"run_date": Path(a.run_dir).name[:10], "build_sha": a.build_sha,
               "subtraction_enabled": a.subtraction_enabled, "dll_sha256_prefix": a.dll_sha256_prefix,
               "wsjtx_validity": "PASS" if res["validity_pass"] else "FAIL",
               "owsfz_guard": ("NOT_READ" if not res["validity_pass"] else ("PASS" if res["guard_pass"] else "FLAG")),
               "wrong_cycle_decodes": sum(d["wrong_cycle_decodes"] for d in res["decoders"].values()),
               "report_state": res["state"]}
        for dec, name in DECODERS:
            for part in PARTS:
                row[f"x_{dec}_{part[4:].lower()}"] = res["decoders"][name]["parts"][part]["X"]
        tp = Path(a.trend)
        new = not tp.exists()
        with open(tp, "a", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=TREND_FIELDS, lineterminator="\n")
            if new:
                wr.writeheader()
            wr.writerow(row)
    print(json.dumps({"rows": res["rows"], "state": res["state"]}))


if __name__ == "__main__":
    main()
