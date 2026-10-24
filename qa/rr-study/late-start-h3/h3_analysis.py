"""H3 analysis (frozen before playback). Aggregates only (HK-037): no message text in any output.

    python h3_analysis.py --manifest M --log playback_log.csv --all-txt ALL.TXT --save-stamps stamps.txt
                          --placement placement.json --out result.json

ALL.TXT columns: [0] stamp, [1] MHz, [2] Rx, [3] FT8, [4] SNR, [5] DT, [6] freq Hz, [7:] text.
A decode is MATCHED to its cycle when its text is exactly the planted text, its stamp equals the cycle's boundary
(playback log) and |freq - 1500| <= 10 Hz (the lateness-edge convention).

Validity rows (all must PASS before G1/G2 are read; a failed row means the arm is INVALID, nothing is reported as a result):
  V1 placement (A1.1): the render step's placement report is PASS.
  V2 liveness: a WSJT-X save WAV exists for the stamp of every cycle (the decoder ran on that cycle). SaveAll is on.
  V3 control: style F, t = 0.62 s, -8 dB decodes >= 4/5. Source of the bar: the lateness-edge run (2026-10-02) decoded
     32/32 at L = 0, -8 dB on the Windows chain with a different WSJT-X build; this arm has its own chain (sol), so the
     bar is stated here, not inherited: a clip on time at the radio's SNR must decode, or "G2 failed" would mean nothing.
  V4 attribution: no boundary carries more than one matched decode. (One text is planted in every cycle, so a decode
     in a stamp that is not a cycle's boundary cannot be attributed; its count is reported, descriptive.)
Gates (the Architect's spec, section 4 H3):
  G1 control: style O, t = 4.9 s, -8 dB decodes 0/5.   (fires only if the DT analysis is wrong)
  G2: style A, t = 3.5 s, -8 dB decodes >= 4/5.
Everything else is descriptive.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

FREQ_TOL_HZ = 10.0
_STAMP = re.compile(r"^(\d{6})_(\d{6})$")


def stamp_to_utc(tok: str):
    m = _STAMP.match(tok)
    return datetime.strptime(m.group(1) + m.group(2), "%y%m%d%H%M%S").replace(tzinfo=timezone.utc) if m else None


def read_log(path: Path) -> dict[int, datetime]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        c, b, _ = line.split(",")
        out[int(c)] = datetime.strptime(b, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return out


def parse_all_txt(path: Path, planted_text: str, t0: datetime, t1: datetime):
    """Planted-text rows within [t0, t1] as dicts; message text does not leave this function."""
    rows, n_other = [], 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        t = line.split()
        if len(t) < 8:
            continue
        utc = stamp_to_utc(t[0])
        if utc is None or utc < t0 or utc > t1:
            continue
        if " ".join(t[7:]) == planted_text:
            rows.append({"utc": utc, "snr_db": float(t[4]), "dt_s": float(t[5]), "freq_hz": float(t[6])})
        else:
            n_other += 1
    return rows, n_other


def wilson(k: int, n: int, z: float = 1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)


def run(man, boundaries, rows, save_stamps, placement_pass, freq_hz, n_other):
    cyc = {c["cycle"]: c for c in man["cycles"]}
    by_stamp = defaultdict(list)
    for r in rows:
        if abs(r["freq_hz"] - freq_hz) <= FREQ_TOL_HZ:
            by_stamp[r["utc"]].append(r)
    matched = {}
    for i, b in boundaries.items():
        if by_stamp.get(b):
            matched[i] = by_stamp[b][0]
    cell = defaultdict(lambda: {"n": 0, "k": 0, "dt": [], "snr": []})
    for i, c in cyc.items():
        key = (c["style"], c["t"], c["snr"])
        cell[key]["n"] += 1
        if i in matched:
            cell[key]["k"] += 1
            cell[key]["dt"].append(matched[i]["dt_s"])
            cell[key]["snr"].append(matched[i]["snr_db"])
    stamps_of_cycles = set(boundaries.values())
    unattributed = [r for r in rows if abs(r["freq_hz"] - freq_hz) <= FREQ_TOL_HZ and r["utc"] not in stamps_of_cycles]
    multi = [b for b, v in by_stamp.items() if len(v) > 1]
    live_missing = [i for i, b in boundaries.items() if b.strftime("%y%m%d_%H%M%S") not in save_stamps]
    ctrl = cell[("F", 0.62, -8)]
    g1 = cell[("O", 4.9, -8)]
    g2 = cell[("A", 3.5, -8)]
    validity = {
        "V1_placement_A1_1": placement_pass,
        "V2_liveness_all_cycles": {"missing": live_missing, "PASS": not live_missing and len(boundaries) == len(cyc)},
        "V3_control_F_0.62_-8dB_ge_4_of_5": {"k": ctrl["k"], "n": ctrl["n"], "PASS": ctrl["k"] >= 4},
        "V4_attribution": {"unattributed_planted_text_decodes": len(unattributed), "boundaries_with_more_than_one": len(multi),
                           "PASS": not multi},
    }
    valid = bool(placement_pass) and validity["V2_liveness_all_cycles"]["PASS"] and validity["V3_control_F_0.62_-8dB_ge_4_of_5"]["PASS"] \
        and validity["V4_attribution"]["PASS"]
    gates = {"G1_O_4.9_-8dB_eq_0_of_5": {"k": g1["k"], "n": g1["n"], "PASS": g1["k"] == 0},
             "G2_A_3.5_-8dB_ge_4_of_5": {"k": g2["k"], "n": g2["n"], "PASS": g2["k"] >= 4}}
    table = []
    for (style, t, snr), v in sorted(cell.items(), key=lambda kv: (kv[0][1], kv[0][0], -kv[0][2])):
        table.append({"style": style, "t": t, "snr": snr, "k": v["k"], "n": v["n"], "wilson95": wilson(v["k"], v["n"]),
                      "median_dt_s": (round(median(v["dt"]), 2) if v["dt"] else None),
                      "median_snr_db": (round(median(v["snr"]), 1) if v["snr"] else None)})
    delta = None
    if ctrl["dt"]:
        delta = round(median(ctrl["dt"]) - (0.62 - 0.5), 2)
    return {"VALID": valid, "validity": validity, "gates": gates if valid else "NOT READ: arm invalid",
            "delta_chain_s_from_F_0.62_-8dB": delta, "n_other_lines_in_window": n_other, "table": table}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--all-txt", required=True)
    ap.add_argument("--save-stamps", required=True)
    ap.add_argument("--placement", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    boundaries = read_log(Path(a.log))
    t0, t1 = min(boundaries.values()), max(boundaries.values())
    rows, n_other = parse_all_txt(Path(a.all_txt), man["text"], t0, t1)
    stamps = set(Path(a.save_stamps).read_text(encoding="utf-8").split())
    placement_pass = bool(json.loads(Path(a.placement).read_text(encoding="utf-8"))["A1_1_placement"]["PASS"])
    res = run(man, boundaries, rows, stamps, placement_pass, man["freq_hz"], n_other)
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"VALID": res["VALID"], "validity": {k: (v if isinstance(v, bool) else v["PASS"]) for k, v in res["validity"].items()},
                      "gates": res["gates"]}, indent=1))


if __name__ == "__main__":
    main()
