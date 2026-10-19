#!/usr/bin/env python3
"""Descriptive audit of the UNMATCHED decodes of one live endurance run (OpenWSFZ vs live WSJT-X).

Written 2026-10-10 for run 20261009_1752 on the Captain's decision (relayed by the Architect,
09:58Z): cover BOTH groups,
  (a) OWS-only  (OpenWSFZ reported it, WSJT-X did not) against the matched population, using
      OpenWSFZ-side fields;
  (b) WSJT-X-only (WSJT-X reported it, OpenWSFZ did not) against the same matched population,
      using WSJT-X-side fields, plus per-cycle OCCUPANCY (share that falls in cycles where
      OpenWSFZ decoded nothing at all, against cycles where it decoded something).

DESCRIPTIVE ONLY. No pass/fail bar, no pre-registration, no cross-row reading. It cannot say
whether an unmatched decode is real (BOARD section 8.2 stays open); it only shows whether a group
looks like the matched population.

HK-037 / NFR-021: message text NEVER leaves `_read_all_txt`. That function returns only
(cycle timestamp, one-way digest of the normalised text, snr, dt, freq, hashed-flag); the text is
discarded inside the loop. Nothing printed or written is per-message: aggregates only.

Matching rule is the standing one (anova_common.match_pairs): key = (cycle ts, message text with
<...> tokens collapsed), duplicates paired in order, so the matched count per key is
min(count_ows, count_wsjtx). The unmatched remainder is what is audited here. The script asserts
the counts it is told to expect (--expect-*), so a drift in the matching rule fails loudly.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict

_HASH_BRACKET_RE = re.compile(r"<[^>]*>")
_TS_FMT = "%y%m%d_%H%M%S"
FT8_CYCLE_SECONDS = 15
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 20261010
Z95 = 1.959964

INF = float("inf")
SNR_EDGES = [-INF, -20, -15, -10, -5, 0, INF]       # dB, half-open (lo, hi]
FREQ_EDGES = [-INF, 500, 1000, 1500, 2000, 2500, 3000, INF]   # Hz, [lo, hi)
DT_EDGES = [-INF, 0.0, 0.5, 1.0, 1.5, INF]          # s, (lo, hi]
DENSITY_EDGES = [-INF, 10, 20, 30, 40, INF]            # decodes on that side in the cycle, [lo, hi)


def _read_all_txt(path: str) -> list[tuple]:
    """Rows as (ts, digest, snr, dt, freq_hz, hashed). The message text stays in this function."""
    rows = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            tok = line.rstrip("\r\n").split()
            if len(tok) < 8:
                continue
            try:
                snr, dt, freq = float(tok[4]), float(tok[5]), float(tok[6])
            except ValueError:
                continue
            text = " ".join(tok[7:])
            norm = _HASH_BRACKET_RE.sub("<HASH>", text)
            digest = hashlib.sha256(norm.encode("ascii", "replace")).hexdigest()[:16]
            rows.append((tok[0], digest, snr, dt, freq, "<" in text))
    return rows


def _wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + Z95 ** 2 / n
    c = (p + Z95 ** 2 / (2 * n)) / d
    h = Z95 * math.sqrt(p * (1 - p) / n + Z95 ** 2 / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _pct(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    lo, hi = _wilson(k, n)
    return f"{100 * k / n:.1f} % [{100 * lo:.1f}, {100 * hi:.1f}]"


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return float("nan") if n == 0 else (s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2]))


def _median_ci(xs: list[float]) -> str:
    if not xs:
        return "n/a"
    rng = random.Random(BOOTSTRAP_SEED)
    s = sorted(xs)
    meds = sorted(_median([s[rng.randrange(len(s))] for _ in s]) for _ in range(BOOTSTRAP_RESAMPLES))
    lo, hi = meds[int(0.025 * BOOTSTRAP_RESAMPLES)], meds[int(0.975 * BOOTSTRAP_RESAMPLES) - 1]
    return f"{_median(xs):.2f} [{lo:.2f}, {hi:.2f}]"


def _bin_index(v: float, edges: list[float], closed_right: bool) -> int:
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        if (lo < v <= hi) if closed_right else (lo <= v < hi):
            return i
    raise ValueError(f"value {v} outside bins {edges}")  # outer edges are infinite: cannot happen


def _bin_label(edges: list[float], i: int, closed_right: bool, unit: str) -> str:
    lo, hi = edges[i], edges[i + 1]
    lo_s = "-inf" if lo == -INF else f"{lo:g}"
    hi_s = "+inf" if hi == INF else f"{hi:g}"
    return f"({lo_s}, {hi_s}] {unit}" if closed_right else f"[{lo_s}, {hi_s}) {unit}"


def _compare_table(title: str, group: list[float], matched: list[float], edges: list[float],
                   closed_right: bool, unit: str, gname: str) -> list[str]:
    ng, nm = len(group), len(matched)
    cg, cm = Counter(_bin_index(v, edges, closed_right) for v in group), \
        Counter(_bin_index(v, edges, closed_right) for v in matched)
    L = [f"**{title}**", "",
         f"| bin | {gname} (n={ng}) | matched (n={nm}) |", "|---|---:|---:|"]
    for i in range(len(edges) - 1):
        L.append(f"| {_bin_label(edges, i, closed_right, unit)} | {_pct(cg[i], ng)} | {_pct(cm[i], nm)} |")
    L.append("")
    L.append(f"Median {gname}: {_median_ci(group)}; median matched: {_median_ci(matched)}.")
    L.append("")
    return L


def _shift(ts: str, cycles: int) -> str:
    d = datetime.datetime.strptime(ts, _TS_FMT) + datetime.timedelta(seconds=FT8_CYCLE_SECONDS * cycles)
    return d.strftime(_TS_FMT)


def audit(ows_path: str, wsjt_path: str, expect: dict) -> tuple[str, dict]:
    ows = _read_all_txt(ows_path)
    wsj = _read_all_txt(wsjt_path)
    assert len(ows) == expect["ows_total"], f"OWS rows {len(ows)} != expected {expect['ows_total']}"
    assert len(wsj) == expect["wsjt_total"], f"WSJT rows {len(wsj)} != expected {expect['wsjt_total']}"

    # Matching, as anova_common.match_pairs: per key, pair in order; remainder is unmatched.
    by_o, by_w = defaultdict(list), defaultdict(list)
    for r in ows:
        by_o[(r[0], r[1])].append(r)
    for r in wsj:
        by_w[(r[0], r[1])].append(r)
    m_o, m_w, u_o, u_w = [], [], [], []
    for key in sorted(set(by_o) | set(by_w)):
        a, b = by_o.get(key, []), by_w.get(key, [])
        k = min(len(a), len(b))
        m_o += a[:k]
        m_w += b[:k]
        u_o += a[k:]
        u_w += b[k:]
    assert len(m_o) == len(m_w) == expect["matched"], f"matched {len(m_o)} != {expect['matched']}"
    assert len(u_o) == expect["ows_only"], f"OWS-only {len(u_o)} != {expect['ows_only']}"
    assert len(u_w) == expect["wsjt_only"], f"WSJT-only {len(u_w)} != {expect['wsjt_only']}"
    assert len(m_o) + len(u_o) == len(ows) and len(m_w) + len(u_w) == len(wsj)

    dens_o, dens_w = Counter(r[0] for r in ows), Counter(r[0] for r in wsj)
    cyc_o, cyc_w = set(dens_o), set(dens_w)
    L: list[str] = []
    L += ["# Unmatched-decode audit (descriptive)", "",
          "Run 20261009_1752: OpenWSFZ (DI sync 5, shim 20260061, nhard 24, corrected OSD, subtraction ON) "
          "against live WSJT-X on the same feed, 40 m, direct USB CODEC. One night, one chain, first row of "
          "its kind: **no cross-row reading, no pass/fail bar**. Whether an unmatched decode is real "
          "(section 8.2) is NOT answered here. Aggregates only (HK-037). 95 % intervals: Wilson for shares, "
          f"bootstrap ({BOOTSTRAP_RESAMPLES} resamples, seed {BOOTSTRAP_SEED}) for medians.", "",
          "## Counts (asserted against the ANOVA report)", "",
          f"- OpenWSFZ rows {len(ows)}, WSJT-X rows {len(wsj)}, matched {len(m_o)}.",
          f"- OWS-only {len(u_o)} ({_pct(len(u_o), len(ows))} of OWS); WSJT-X-only {len(u_w)} "
          f"({_pct(len(u_w), len(wsj))} of WSJT-X).",
          f"- Cycles with at least one decode: OWS {len(cyc_o)}, WSJT-X {len(cyc_w)}, both {len(cyc_o & cyc_w)}, "
          f"WSJT-X only {len(cyc_w - cyc_o)}, OWS only {len(cyc_o - cyc_w)}.", ""]

    def fields(rows, side_dens):
        return ([r[2] for r in rows], [r[4] for r in rows], [r[3] for r in rows],
                [side_dens[r[0]] for r in rows], sum(1 for r in rows if r[5]))

    # (a) OWS-only vs matched, OWS-side fields
    L += ["## (a) OWS-only vs matched (OpenWSFZ-side fields)", ""]
    g = fields(u_o, dens_o)
    mt = fields(m_o, dens_o)
    L += _compare_table("SNR", g[0], mt[0], SNR_EDGES, True, "dB", "OWS-only")
    L += _compare_table("Frequency", g[1], mt[1], FREQ_EDGES, False, "Hz", "OWS-only")
    L += _compare_table("DT", g[2], mt[2], DT_EDGES, True, "s", "OWS-only")
    L += _compare_table("Cycle density (OWS decodes in the cycle)", g[3], mt[3], DENSITY_EDGES, False,
                        "decodes", "OWS-only")
    L += [f"**Hashed-message share:** OWS-only {_pct(g[4], len(u_o))}; matched {_pct(mt[4], len(m_o))}.", ""]
    per_cycle = Counter(r[0] for r in u_o)
    L += [f"**Clustering:** the {len(u_o)} OWS-only decodes sit in {len(per_cycle)} distinct cycles "
          f"(of {len(cyc_o)}); most in one cycle: {max(per_cycle.values())}; cycles with 2 or more: "
          f"{sum(1 for v in per_cycle.values() if v >= 2)}.", ""]
    o_in_wempty = sum(1 for r in u_o if r[0] not in cyc_w)
    L += [f"**Occupancy (mirror of (b)):** {_pct(o_in_wempty, len(u_o))} of the OWS-only decodes sit in cycles "
          f"where WSJT-X has no row at all ({len(cyc_o - cyc_w)} such cycles; WSJT-X produced nothing there, "
          "so these cannot be disagreements). Excluding them, OWS-only = "
          f"{len(u_o) - o_in_wempty} in {len(set(r[0] for r in u_o if r[0] in cyc_w))} cycles.", ""]
    # Neighbour-cycle check: same normalised text reported by WSJT-X one cycle earlier or later.
    w_keys = set(by_w)
    near = sum(1 for r in u_o if (_shift(r[0], -1), r[1]) in w_keys or (_shift(r[0], 1), r[1]) in w_keys)
    same_cyc_other = sum(1 for r in u_o if (r[0], r[1]) in w_keys)
    L += [f"**Timing-label check:** {_pct(near, len(u_o))} of the OWS-only decodes have the same text in "
          "WSJT-X one cycle earlier or later (a cycle-labelling difference, not a missed signal); "
          f"{same_cyc_other} have the same text in the same cycle on WSJT-X but beyond the pairing count "
          "(duplicate-text surplus).", ""]

    # (b) WSJT-X-only vs matched, WSJT-X-side fields
    L += ["## (b) WSJT-X-only vs matched (WSJT-X-side fields)", ""]
    g = fields(u_w, dens_w)
    mt = fields(m_w, dens_w)
    L += _compare_table("SNR", g[0], mt[0], SNR_EDGES, True, "dB", "WSJT-X-only")
    L += _compare_table("Frequency", g[1], mt[1], FREQ_EDGES, False, "Hz", "WSJT-X-only")
    L += _compare_table("DT", g[2], mt[2], DT_EDGES, True, "s", "WSJT-X-only")
    L += _compare_table("Cycle density (WSJT-X decodes in the cycle)", g[3], mt[3], DENSITY_EDGES, False,
                        "decodes", "WSJT-X-only")
    L += [f"**Hashed-message share:** WSJT-X-only {_pct(g[4], len(u_w))}; matched {_pct(mt[4], len(m_w))}.", ""]

    # Occupancy: missed cycles vs missed signals inside decoded cycles
    in_empty = sum(1 for r in u_w if r[0] not in cyc_o)
    in_busy = len(u_w) - in_empty
    wsj_in_empty = sum(1 for r in wsj if r[0] not in cyc_o)
    wsj_in_busy = len(wsj) - wsj_in_empty
    matched_in_busy = len(m_w)          # matched rows are by definition in OWS-nonempty cycles
    busy_cycles = len(cyc_w & cyc_o)
    L += ["### Occupancy: missed cycles versus missed signals inside decoded cycles", "",
          "| where OpenWSFZ decoded | WSJT-X decodes | of them WSJT-X-only | matched |",
          "|---|---:|---:|---:|",
          f"| nothing in the cycle (OWS has no row at all) | {wsj_in_empty} | {in_empty} | 0 |",
          f"| at least one decode in the cycle | {wsj_in_busy} | {in_busy} | {matched_in_busy} |", "",
          f"- Share of the {len(u_w)} WSJT-X-only decodes in cycles where OWS decoded nothing: "
          f"**{_pct(in_empty, len(u_w))}**; inside cycles OWS did decode: **{_pct(in_busy, len(u_w))}**.",
          f"- Inside cycles OWS did decode ({busy_cycles} cycles): matched share of WSJT-X's decodes "
          f"**{_pct(matched_in_busy, wsj_in_busy)}** (the decoder-gap figure; "
          f"{len(cyc_w - cyc_o)} cycles were decoded by WSJT-X and not at all by OpenWSFZ).",
          f"- Overall matched share of WSJT-X's decodes: {_pct(len(m_w), len(wsj))}.", ""]
    # distribution of OWS-empty cycles: how many cycles, and their WSJT-X load
    empty_cycles = sorted(cyc_w - cyc_o)
    load = [dens_w[c] for c in empty_cycles]
    L += [f"- OWS-empty cycles that WSJT-X decoded in: {len(empty_cycles)} (median WSJT-X decodes per such "
          f"cycle {_median_ci([float(x) for x in load])}).", ""]

    summary = {
        "ows_total": len(ows), "wsjt_total": len(wsj), "matched": len(m_o),
        "ows_only": len(u_o), "wsjt_only": len(u_w),
        "wsjt_only_in_ows_empty_cycles": in_empty, "wsjt_only_in_ows_busy_cycles": in_busy,
        "wsjt_in_ows_empty_cycles": wsj_in_empty, "wsjt_in_ows_busy_cycles": wsj_in_busy,
        "ows_only_cycles": len(per_cycle), "ows_only_in_wsjt_empty_cycles": o_in_wempty, "ows_only_near_cycle_text_in_wsjt": near,
    }
    return "\n".join(L) + "\n", summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ours-all-txt", required=True)
    ap.add_argument("--wsjtx-all-txt", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--expect-ows-total", type=int, required=True)
    ap.add_argument("--expect-wsjt-total", type=int, required=True)
    ap.add_argument("--expect-matched", type=int, required=True)
    ap.add_argument("--expect-ows-only", type=int, required=True)
    ap.add_argument("--expect-wsjt-only", type=int, required=True)
    a = ap.parse_args()
    expect = {"ows_total": a.expect_ows_total, "wsjt_total": a.expect_wsjt_total,
              "matched": a.expect_matched, "ows_only": a.expect_ows_only, "wsjt_only": a.expect_wsjt_only}
    md, summary = audit(a.ours_all_txt, a.wsjtx_all_txt, expect)
    with open(a.out_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md)
    with open(os.path.splitext(a.out_md)[0] + ".json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print(json.dumps(summary, sort_keys=True))
    print(f"wrote {a.out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
