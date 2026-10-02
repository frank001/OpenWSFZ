"""LATENESS / EDGE test: the post-playback predicates P3 to P6 (and optional P7) and the edge outputs.

Pure functions plus a small CLI. Pre-registered (spec 2026-10-02-0720, Amendment 2): every predicate
is code, every threshold a named constant. Counts only in the output (NFR-021); decoder text is read
ONLY inside `parse_all_txt`, which keeps a line's text iff it is exactly one of the session's planted
synthetic texts (HK-037: message text of anything else never leaves that function; it is counted).

    python analysis.py --manifest M --playback-log P.csv --alltxt-wsjtx A --alltxt-owsfz B --out R.json [--p7]

`playback_log.csv`: columns cycle_index, boundary_utc (ISO, Z). One row per cycle, planted or idle.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

import design as D

# --- predicates as named constants (spec section 4) --------------------------------------------
P3_MIN_RATE = 0.90
P3B_MAX_COUNT_DIFF = 3                      # matched signals (of 32), early vs late L=0, -8 dB
P5_SNR_TOL_DB = 3.0
P5_SNR_NOMINAL_DB = -8.0
FREQ_TOL_HZ = 10.0
EDGE_THRESHOLDS = (0.50, 0.90)
WILSON_Z = 1.959964
EXPECTED_PLANTED = 152
assert (P3_MIN_RATE, P3B_MAX_COUNT_DIFF, P5_SNR_TOL_DB, FREQ_TOL_HZ, EXPECTED_PLANTED) == (0.90, 3, 3.0, 10.0, 152)

_STAMP = re.compile(r"^(\d{6})_(\d{6})$")


def stamp_to_utc(tok: str) -> datetime | None:
    m = _STAMP.match(tok)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def parse_all_txt(path: Path, planted_texts: set[str]):
    """Return (rows, stamps, n_lines, n_other). rows: decodes whose text is exactly a planted text
    (dicts: utc, text, freq_hz, snr_db, dt_s). stamps: every decode-pass stamp seen (no text).
    ALL.TXT columns: [0] stamp, [1] MHz, [2] Rx, [3] FT8, [4] SNR, [5] DT, [6] freq Hz, [7:] text."""
    rows, stamps, n, other = [], set(), 0, 0
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        t = line.split()
        if len(t) < 8:
            continue
        utc = stamp_to_utc(t[0])
        if utc is None:
            continue
        n += 1
        stamps.add(utc)
        text = " ".join(t[7:])
        if text in planted_texts:
            try:
                rows.append({"utc": utc, "text": text, "snr_db": float(t[4]), "dt_s": float(t[5]),
                             "freq_hz": float(t[6])})
            except ValueError:
                other += 1
        else:
            other += 1
    return rows, stamps, n, other


def read_playback_log(path: Path) -> dict[int, datetime]:
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[int(r["cycle_index"])] = datetime.strptime(r["boundary_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return out


def wilson(k: int, n: int, z: float = WILSON_Z) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


# --------------------------------------------------------------------------- matching
def match_decoder(design: dict, boundaries: dict[int, datetime], rows: list[dict]):
    """Per signal: matched (planted text, own cycle stamp, |df| <= 10 Hz). Also wrong-cycle decodes.
    Returns (matched: {sig_id: row}, wrong_cycle: list)."""
    by_stamp_text: dict[tuple, list[dict]] = {}
    for r in rows:
        by_stamp_text.setdefault((r["utc"], r["text"]), []).append(r)
    text_to_sig = {s["text"]: s for s in design["signals"]}
    matched, wrong = {}, []
    for s in design["signals"]:
        b = boundaries.get(s["cycle"])
        if b is None:
            continue
        for r in by_stamp_text.get((b, s["text"]), []):
            if abs(r["freq_hz"] - s["freq_hz"]) <= FREQ_TOL_HZ:
                matched[s["sig_id"]] = r
                break
    cycle_of_stamp = {b: i for i, b in boundaries.items()}
    for r in rows:
        s = text_to_sig[r["text"]]
        own = boundaries.get(s["cycle"])
        if r["utc"] != own:
            ci = cycle_of_stamp.get(r["utc"])
            planted = bool(ci is not None and design["cycles"][ci]["planted"])
            wrong.append({"sig_id": s["sig_id"], "stamp_cycle": ci, "in_planted_cycle": planted})
    return matched, wrong


def rates(design: dict, matched: dict) -> dict:
    """r(cell) = matched / 32 with Wilson 95 % CI."""
    out = {}
    cnt: dict[str, int] = {}
    for s in design["signals"]:
        cnt.setdefault(s["cell"], 0)
        if s["sig_id"] in matched:
            cnt[s["cell"]] += 1
    for cid, k in cnt.items():
        lo, hi = wilson(k, D.SIGNALS_PER_CELL)
        out[cid] = {"k": k, "n": D.SIGNALS_PER_CELL, "r": k / D.SIGNALS_PER_CELL, "lo": lo, "hi": hi}
    return out


def edge(grid: list[float], r_at: dict[float, float], thr: float, early: bool):
    """Late: largest L >= 0 with r >= thr at L and every smaller grid L >= 0 (None if r(0) < thr).
    Early: most negative L with r >= thr at L and every grid L between it and 0. Returns
    (value or None, label, non_monotone_after_edge list)."""
    ordered = sorted(grid, reverse=True) if early else sorted(grid)
    ordered = [L for L in ordered if (L <= 0 if early else L >= 0)]
    if early:
        ordered = sorted((L for L in grid if L <= 0), reverse=True)     # 0, -0.25, ... -3.0
    ok_to = None
    for L in ordered:
        if r_at[L] >= thr:
            ok_to = L
        else:
            break
    end = ordered[-1]
    if ok_to is None:
        return None, "none (fails at L = 0)", []
    if ok_to == end:
        label = "< -3.00" if early else "> 6.00"
    else:
        label = f"{ok_to:+.2f}"
    after = [L for L in ordered if (L < ok_to if early else L > ok_to) and r_at[L] >= thr]
    return ok_to, label, after


def add_dt_form(table: dict, delta_chain_s) -> dict:
    """DT_edge = L_edge + Delta_chain, labelled 'WSJT-X DT convention, via this chain's offset'
    (Amendment 3). L stays the primary grid. Open-ended labels keep their direction."""
    for key, e in table.items():
        if delta_chain_s is None or e["edge"] is None:
            e["dt_edge"] = None
            e["dt_edge_label"] = e["label"]
            continue
        e["dt_edge"] = e["edge"] + delta_chain_s
        if e["label"].startswith(">"):
            e["dt_edge_label"] = f"> {6.0 + delta_chain_s:+.2f}"
        elif e["label"].startswith("<"):
            e["dt_edge_label"] = f"< {-3.0 + delta_chain_s:+.2f}"
        else:
            e["dt_edge_label"] = f"{e['dt_edge']:+.2f}"
        e["dt_convention"] = "WSJT-X DT convention, via this chain's offset (Delta_chain, P7)"
    return table


def q2_fraction(t2_s: list[float], k_s: float, dt_edge_s: float) -> float:
    """Q2 in DT form (Amendment 3): fraction of on-air cycles with T2 + k - 0.5 <= DT_edge(WSJT-X, s)."""
    if not t2_s:
        return float("nan")
    return sum(1 for t in t2_s if t + k_s - 0.5 <= dt_edge_s) / len(t2_s)


def edges_table(design: dict, cell_rates: dict) -> dict:
    out = {}
    for block, grid, early in (("LATE", list(D.LATE_L_GRID), False), ("EARLY", list(D.EARLY_L_GRID), True)):
        for snr in D.SNRS_DB:
            r_at = {L: cell_rates[D.cell_id(block, L, snr)]["r"] for L in grid}
            for thr in EDGE_THRESHOLDS:
                key = f"{'E' if not early else 'E'}{int(thr * 100)}{'e' if early else ''}(snr={snr})"
                v, label, after = edge(grid, r_at, thr, early)
                out[key] = {"edge": v, "label": label, "non_monotone_after_edge": after}
    return out


# --------------------------------------------------------------------------- the validity rows
def cell_count(design: dict, matched: dict, block: str, L: float, snr: int) -> int:
    cid = D.cell_id(block, L, snr)
    return sum(1 for s in design["signals"] if s["cell"] == cid and s["sig_id"] in matched)


def _dt_stats(dts: list[float]) -> dict:
    if not dts:
        return {"n": 0, "median_dt_s": None, "q1": None, "q3": None, "iqr": None}
    q = statistics.quantiles(dts, n=4, method="inclusive") if len(dts) >= 2 else [dts[0]] * 3
    return {"n": len(dts), "median_dt_s": statistics.median(dts), "q1": q[0], "q3": q[2], "iqr": q[2] - q[0]}


def validity(design: dict, boundaries: dict, per_dec: dict, p7: bool = True) -> dict:
    """per_dec: decoder -> {matched, wrong, stamps}. Returns rows P3..P6 (and P7 if asked)."""
    rows = {"P3": {}, "P3b": {}, "P4": {}, "P5": {}, "P6": {}}
    planted = [i for i, c in enumerate(design["cycles"]) if c["planted"]]
    assert len(planted) == EXPECTED_PLANTED
    for d, v in per_dec.items():
        kl = cell_count(design, v["matched"], "LATE", 0.0, -8)
        ke = cell_count(design, v["matched"], "EARLY", 0.0, -8)
        rows["P3"][d] = {"k": kl, "rate": kl / 32, "PASS": kl / 32 >= P3_MIN_RATE}
        rows["P3b"][d] = {"k_early": ke, "k_late": kl, "rate": ke / 32,
                          "PASS": ke / 32 >= P3_MIN_RATE and abs(ke - kl) <= P3B_MAX_COUNT_DIFF}
        missing = [i for i in planted if boundaries.get(i) not in v["stamps"]]
        rows["P4"][d] = {"planted_cycles_with_a_pass": len(planted) - len(missing),
                         "missing_cycles": missing, "PASS": not missing}
        snrs = [v["matched"][s["sig_id"]]["snr_db"] for s in design["signals"]
                if s["cell"] == D.cell_id("LATE", 0.0, -8) and s["sig_id"] in v["matched"]]
        med = statistics.median(snrs) if snrs else float("nan")
        rows["P5"][d] = {"median_snr_db": med, "n": len(snrs),
                         "PASS": bool(snrs) and abs(med - P5_SNR_NOMINAL_DB) <= P5_SNR_TOL_DB}
        in_planted = [w for w in v["wrong"] if w["in_planted_cycle"]]
        in_idle = [w for w in v["wrong"] if not w["in_planted_cycle"]]
        rows["P6"][d] = {"wrong_in_planted_cycles": len(in_planted), "listed_idle_cycle_decodes": len(in_idle),
                         "PASS": not in_planted}
    # P7 (Amendment 3; DESCRIPTIVE, no bar): median reported DT and IQR at L = 0, -8 dB, per decoder
    # and per arming path. Delta_chain := the median WSJT-X DT at L = 0 from the LATE block.
    rows["P7"] = {}
    for d, v in per_dec.items():
        rows["P7"][d] = {}
        for block in ("LATE", "EARLY"):
            dts = [v["matched"][s["sig_id"]]["dt_s"] for s in design["signals"]
                   if s["cell"] == D.cell_id(block, 0.0, -8) and s["sig_id"] in v["matched"]]
            rows["P7"][d][block] = _dt_stats(dts)
    wl = rows["P7"].get("wsjtx", {}).get("LATE", {})
    rows["delta_chain_s"] = wl.get("median_dt_s")
    ok = all(r["PASS"] for k, row in rows.items() if k in ("P3", "P3b", "P4", "P5", "P6") for r in row.values())
    rows["ALL_VALIDITY_PASS"] = ok
    return rows


def run(design: dict, boundaries: dict, rows_by_dec: dict, stamps_by_dec: dict, p7: bool = True) -> dict:
    per = {}
    for d, rows in rows_by_dec.items():
        matched, wrong = match_decoder(design, boundaries, rows)
        per[d] = {"matched": matched, "wrong": wrong, "stamps": stamps_by_dec[d]}
    val = validity(design, boundaries, per, p7)
    out = {"validity": val, "cells": {}, "edges": {}, "note": ""}
    for d, v in per.items():
        cr = rates(design, v["matched"])
        out["cells"][d] = cr
        if val["ALL_VALIDITY_PASS"]:
            out["edges"][d] = add_dt_form(edges_table(design, cr), val.get("delta_chain_s"))
    if not val["ALL_VALIDITY_PASS"]:
        failed = sorted({k for k, row in val.items() if k in ("P3", "P3b", "P4", "P5", "P6")
                         for r in row.values() if not r["PASS"]})
        out["note"] = f"VALIDITY FAIL on {failed}: no edge is reported (spec section 4)."
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--playback-log", required=True)
    ap.add_argument("--alltxt-wsjtx", required=True)
    ap.add_argument("--alltxt-owsfz", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    design = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    boundaries = read_playback_log(Path(a.playback_log))
    texts = {s["text"] for s in design["signals"]}
    rows_by, stamps_by, meta = {}, {}, {}
    for name, p in (("wsjtx", a.alltxt_wsjtx), ("owsfz", a.alltxt_owsfz)):
        r, st, n, other = parse_all_txt(Path(p), texts)
        rows_by[name], stamps_by[name] = r, st
        meta[name] = {"lines": n, "planted_text_lines": len(r), "other_lines_counted_only": other}
    res = run(design, boundaries, rows_by, stamps_by)
    res["alltxt_meta"] = meta

    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items() if k not in ("matched", "stamps")}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        return o
    Path(a.out).write_text(json.dumps(clean(res), indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"ALL_VALIDITY_PASS": res["validity"]["ALL_VALIDITY_PASS"], "note": res["note"]}))


if __name__ == "__main__":
    main()
