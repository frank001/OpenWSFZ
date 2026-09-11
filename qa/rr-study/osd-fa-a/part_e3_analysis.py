#!/usr/bin/env python3
"""OSD-FA-A E3 analysis (Amendment 1 sec.5.3) -- reproduction, removal, corroboration.

Reuses two already-computed legs (HK-018, no re-decode):
  60-leg: artefacts/2026-09-10-f001-l3-live-measurement/subject_20260050.json
          (F-001 L3's own subject replay -- production defaults, same corpus/window)
  40-leg: artefacts/2026-09-11-osd-fa-a-e3/replay40.json (part_e3_replay40.py, new)

Population: OpenWSFZ's own live-emitted decodes (production ALL.TXT, dial-filtered,
span-filtered) -- counting only live-emitted decodes keeps out whatever either replay
adds that production never showed (Amendment 1 sec.5.3).

For each live decode:
  reproduced  = the 60-leg replay has a decode in the SAME CYCLE, wildcard-matching
                message, |delta_f| <= 3 Hz (the "<...> matches one token" matcher,
                reused from h1_hash_token_contamination.wildcard_match).
  removed     = reproduced at 60 AND no such match in the 40-leg (same criteria).

E3-0 (VALIDITY): reproduction share < 0.90 => VOID.
n = removed decodes (among reproduced live decodes). k = removed AND corroborated by
REF = WSJT-X #1 (same matcher, part_d2.is_corroborated/load_ref_a, reused).
[lo,hi] = Clopper-Pearson 95%. BAR_H = 0.05 (frozen, PO-ratified 2026-09-11 16:26Z).

  E3-H: lo >= BAR_H => Option B measurably removes real stations on live audio.
  E3-N: otherwise    => no live harm detected at this resolution. NEVER "safe".

NFR-021: message text held in memory only (wildcard matching) -- never printed, logged,
or written. Output is counts only.

Usage:
    python part_e3_analysis.py <out_json>
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, HERE)

import part_d2 as PD2  # noqa: E402
from h1_hash_token_contamination import wildcard_match  # noqa: E402
from scipy.stats import beta as _beta_dist  # noqa: E402

LEG60_JSON = os.path.join(REPO_ROOT, "artefacts", "2026-09-10-f001-l3-live-measurement",
                           "subject_20260050.json")
LEG40_JSON = os.path.join(REPO_ROOT, "artefacts", "2026-09-11-osd-fa-a-e3", "replay40.json")
REPRODUCTION_BAR = 0.90
BAR_H = 0.05
TOL_HZ = 3


def clopper_pearson(k, n, alpha=0.05):
    lo = 0.0 if k == 0 else float(_beta_dist.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(_beta_dist.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def load_replay_by_cycle(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    by_cycle = {}
    for entry in d["per_file"]:
        by_cycle[entry["ts"]] = [(dec["f"], dec.get("dt"), dec["m"]) for dec in entry["decodes"]]
    return by_cycle, d


def find_match(live_msg: str, live_freq: float, replay_decodes: list) -> bool:
    for rf, _rdt, rm in replay_decodes:
        if abs(rf - live_freq) <= TOL_HZ and wildcard_match(live_msg, rm):
            return True
    return False


def main() -> int:
    out_json = sys.argv[1]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    leg60_by_cycle, meta60 = load_replay_by_cycle(LEG60_JSON)
    leg40_by_cycle, meta40 = load_replay_by_cycle(LEG40_JSON)
    print(f"leg60: {meta60['n_files']} files, sha256={meta60['dll_sha256'][:16]}..., "
          f"window={meta60['window']}", flush=True)
    print(f"leg40: {meta40['n_files']} files, sha256={meta40['dll_sha256'][:16]}..., "
          f"nhard={meta40['nhard']}, window={meta40['window']}", flush=True)
    assert meta60["dll_sha256"] == meta40["dll_sha256"], "leg60/leg40 binary mismatch"
    assert tuple(meta60["window"]) == tuple(meta40["window"]), "leg60/leg40 window mismatch"

    by_cycle = PD2.parse_all_txt_with_snr(PD2.ALL_TXT)
    lo_ts, hi_ts = meta60["window"]
    by_cycle = {ts: v for ts, v in by_cycle.items() if lo_ts <= ts < hi_ts}
    n_live_total = sum(len(v) for v in by_cycle.values())
    print(f"live population: {len(by_cycle)} cycles with >=1 decode, "
          f"{n_live_total} live decodes in span", flush=True)

    ref_a = PD2.load_ref_a(PD2.WSJTX_A_ALL, lo_ts)

    n_reproduced = 0
    n_removed = 0
    k_corroborated = 0
    n_not_reproduced_by_snr = {}

    t0 = time.perf_counter()
    n_done = 0
    for cycle_ts, decodes in by_cycle.items():
        leg60_decodes = leg60_by_cycle.get(cycle_ts, [])
        leg40_decodes = leg40_by_cycle.get(cycle_ts, [])
        for freq_hz, dt_s, message, snr in decodes:
            reproduced = find_match(message, freq_hz, leg60_decodes)
            if not reproduced:
                continue
            n_reproduced += 1
            removed = not find_match(message, freq_hz, leg40_decodes)
            if removed:
                n_removed += 1
                if PD2.is_corroborated(ref_a, cycle_ts, message, freq_hz):
                    k_corroborated += 1
        n_done += 1
        if n_done % 500 == 0:
            print(f"  {n_done}/{len(by_cycle)} cycles ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    reproduction_share = n_reproduced / n_live_total if n_live_total else None
    void_e3 = reproduction_share is None or reproduction_share < REPRODUCTION_BAR
    print(f"reproduction share = {n_reproduced}/{n_live_total} = {reproduction_share}", flush=True)

    row = None
    lo = hi = None
    if not void_e3:
        lo, hi = clopper_pearson(k_corroborated, n_removed) if n_removed else (None, None)
        if lo is not None:
            row = "E3-H" if lo >= BAR_H else "E3-N"

    out = {
        "n_live_total": n_live_total, "n_reproduced": n_reproduced,
        "reproduction_share": reproduction_share, "void_e3": void_e3,
        "n_removed": n_removed, "k_corroborated": k_corroborated,
        "ci_lo": lo, "ci_hi": hi, "row": row, "bar_h": BAR_H,
        "total_wall_s": total_wall,
    }
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    os.replace(tmp, out_json)

    print(f"DONE n_removed={n_removed} k_corroborated={k_corroborated} CI=[{lo},{hi}] "
          f"ROW={row} VOID={void_e3} wall={total_wall:.0f}s -> {out_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
