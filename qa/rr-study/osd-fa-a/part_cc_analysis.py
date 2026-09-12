#!/usr/bin/env python3
"""NHARD40-DEFAULT `CC` analysis -- ROW 0d verdict, the gate (CC-S1/S2/S3), and the
descriptive picture (spec Sec.2.5/2.6/2.7). Pure computation over part_cc.py's
persisted JSON -- no decoding here.

Definitions (spec Sec.2.3/2.4, predicates as code -- HK-021(r)):
  Unit = station-cycle. present_L(s) = leg L has a decode whose PAYLOAD equals
         station s's payload (no frequency condition -- spec Sec.2.3).
  G = station-cycles with present_60. K = of those, absent@40 (killed). C = of
      those, absent@0 (OSD-rescued ceiling). gains = station-cycles NOT present@60
      but present@40 (report-only, spec Sec.2.5).
  L = K/G, pooled and per family. CI = cycle-clustered bootstrap (2,000 resamples,
      seed compute_seed('NHARD40-CC-BOOT',0,0)); when K=0 in a set, the upper bound
      is the Clopper-Pearson 95% upper bound on 0 of N_cycles (cycles in that set
      with >=1 genuine decode at 60) -- stats_common.clopper_pearson already
      returns lo=0 at k=0 by construction, so this is the SAME function NT used
      (HK-018), not a special case.

Gate (spec Sec.2.6, first match wins, ROW 0d checked first):
  0d: G < 1,000 -> S3 (routes, does not gate directly).
  CC-S2: CI_lo(L) >= BAR_S, OR for any family f, CI_lo(L_f) >= BAR_S.
  CC-S1: CI_hi(L) < BAR_S.
  CC-S3: otherwise.

Report-only (spec Sec.2.5, evaluated both ways per HK-021(k)): gains, and net K -
gains. Descriptive (spec Sec.2.7): per-family G/C/K/gains, capture strong/weak roles,
false decodes/cycle/leg, and the R6 question (parts 0-2: OSD accepts at 60 split into
genuine (C) vs false (false decodes at 60 minus at 0)).

Usage:
    python part_cc_analysis.py <cc_json>
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study"))
sys.path.insert(0, HERE)

from stats_common import clopper_pearson  # noqa: E402
from part_d import cycle_clustered_bootstrap_ci  # noqa: E402
from harness.common import compute_seed  # noqa: E402
import part_cc as CC  # noqa: E402

BAR_S = 0.05  # PO-ratified, frozen, 2026-09-12 ~10:00Z, before any CC datum (spec Sec.2.9)
G_FLOOR = 1000
N_BOOT = 2000
BOOT_SEED = compute_seed("NHARD40-CC-BOOT", 0, 0)


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    parts = {int(k): v for k, v in state["parts"].items()}
    return state, parts


def station_role(signals: list, i: int) -> str:
    """Capture-family role (spec Sec.2.7): strong/weak by relative snr_db within
    the part; 'equal' if tied (co_channel/near_collision/time_freq/co_channel_sweep
    parts are all equal-SNR or use dt/freq separation, not level, so 'equal' there)."""
    snrs = [float(s["snr_db"]) for s in signals]
    if len(set(snrs)) == 1:
        return "equal"
    return "strong" if snrs[i] == max(snrs) else "weak"


def per_cycle_rows(parts: dict):
    """Yields (part_index, family, trial, n_stations, signals, [g60,g40,g0]xN) for
    every persisted cycle."""
    for pidx, rec in parts.items():
        family = rec["overlap_type"]
        signals = rec["signals"]
        for row in rec["trials"]:
            g60 = row["60"]["present"]
            g40 = row["40"]["present"]
            g0 = row["0"]["present"]
            yield pidx, family, row["trial"], len(row["msg_ids"]), signals, g60, g40, g0


def set_stats(cycles: list):
    """cycles: list of (n_stations, signals, g60, g40, g0) tuples (one scene each).
    Returns G/K/C/gains, per-cycle K/G arrays (for bootstrap), N_cycles_with_G,
    and per-role (strong/weak/equal) presence tallies."""
    G = K = C = gains = 0
    K_per_cycle = []
    G_per_cycle = []
    N_cycles_with_G = 0
    role_tally = {}  # role -> {"n60":0,"n40":0,"n0":0,"n":0}
    for n_stations, signals, g60, g40, g0 in cycles:
        cyc_G = cyc_K = 0
        for i in range(n_stations):
            role = station_role(signals, i)
            rt = role_tally.setdefault(role, {"n60": 0, "n40": 0, "n0": 0, "n": 0})
            rt["n"] += 1
            rt["n60"] += int(g60[i])
            rt["n40"] += int(g40[i])
            rt["n0"] += int(g0[i])
            if g60[i]:
                G += 1
                cyc_G += 1
                if not g40[i]:
                    K += 1
                    cyc_K += 1
                if not g0[i]:
                    C += 1
            if (not g60[i]) and g40[i]:
                gains += 1
        K_per_cycle.append(cyc_K)
        G_per_cycle.append(cyc_G)
        if cyc_G >= 1:
            N_cycles_with_G += 1
    return {
        "G": G, "K": K, "C": C, "gains": gains, "net_K_minus_gains": K - gains,
        "K_per_cycle": K_per_cycle, "G_per_cycle": G_per_cycle,
        "N_cycles": len(cycles), "N_cycles_with_G": N_cycles_with_G,
        "roles": {r: {"p60": t["n60"] / t["n"], "p40": t["n40"] / t["n"],
                       "p0": t["n0"] / t["n"], "n": t["n"]}
                  for r, t in role_tally.items()},
    }


def ci_for(stats: dict):
    K, G = stats["K"], stats["G"]
    L = (K / G) if G else None
    if K == 0:
        lo = 0.0
        _, hi = clopper_pearson(0, stats["N_cycles_with_G"]) if stats["N_cycles_with_G"] else (0.0, 1.0)
    else:
        lo, hi = cycle_clustered_bootstrap_ci(
            stats["K_per_cycle"], stats["G_per_cycle"], N_BOOT, BOOT_SEED)
    return L, lo, hi


def false_decodes_per_cycle(parts: dict, leg: str):
    total_false = total_n = 0
    for rec in parts.values():
        for row in rec["trials"]:
            total_false += row[leg]["n_false"]
            total_n += 1
    return (total_false / total_n) if total_n else None


def main() -> int:
    path = sys.argv[1]
    state, parts = load(path)

    all_cycles = []  # (n_stations, signals, g60, g40, g0)
    by_family = {}
    for pidx, family, trial, n_stations, signals, g60, g40, g0 in per_cycle_rows(parts):
        item = (n_stations, signals, g60, g40, g0)
        all_cycles.append(item)
        by_family.setdefault(family, []).append(item)

    pooled = set_stats(all_cycles)
    pooled["L"], pooled["ci_lo"], pooled["ci_hi"] = ci_for(pooled)
    print("POOLED:", json.dumps(
        {k: v for k, v in pooled.items() if k not in ("K_per_cycle", "G_per_cycle")},
        indent=2))

    family_stats = {}
    for fam, cycles in by_family.items():
        fs = set_stats(cycles)
        fs["L"], fs["ci_lo"], fs["ci_hi"] = ci_for(fs)
        family_stats[fam] = fs
        print(f"FAMILY {fam}:", json.dumps(
            {k: v for k, v in fs.items() if k not in ("K_per_cycle", "G_per_cycle")},
            indent=2))

    # ROW 0d
    if pooled["G"] < G_FLOOR:
        row, reason = "S3", f"ROW 0d short: G={pooled['G']} < {G_FLOOR}"
    else:
        s2_pool = pooled["ci_lo"] >= BAR_S
        s2_family = any(fs["ci_lo"] >= BAR_S for fs in family_stats.values())
        if s2_pool or s2_family:
            which = "pooled" if s2_pool else [f for f, fs in family_stats.items()
                                               if fs["ci_lo"] >= BAR_S]
            row, reason = "CC-S2", f"CI_lo >= BAR_S={BAR_S} ({which})"
        elif pooled["ci_hi"] < BAR_S:
            row, reason = "CC-S1", f"pooled CI_hi={pooled['ci_hi']:.4f} < BAR_S={BAR_S}"
        else:
            row, reason = "CC-S3", (f"pooled CI=[{pooled['ci_lo']:.4f},{pooled['ci_hi']:.4f}] "
                                     f"straddles BAR_S={BAR_S}")
    print(f"GATE ROW: {row} ({reason})")

    # R6 question: parts 0-2 (co_channel) OSD accepts at 60, split genuine (C) vs false.
    co_channel_cycles = by_family.get("co_channel", [])
    r6_C = set_stats(co_channel_cycles)["C"]
    r6_false60 = r6_false0 = r6_n = 0
    for pidx, rec in parts.items():
        if rec["overlap_type"] != "co_channel":
            continue
        for trial_row in rec["trials"]:
            r6_false60 += trial_row["60"]["n_false"]
            r6_false0 += trial_row["0"]["n_false"]
            r6_n += 1
    r6_osd_false = r6_false60 - r6_false0
    print(f"R6 QUESTION (parts 0-2, co_channel): genuine OSD-rescued station-cycles "
          f"(C) = {r6_C}; false decodes attributable to OSD (false@60 - false@0) = "
          f"{r6_osd_false} (false@60={r6_false60}, false@0={r6_false0}, n_cycles={r6_n})")

    desc = {
        "false_decodes_per_cycle_60": false_decodes_per_cycle(parts, "60"),
        "false_decodes_per_cycle_40": false_decodes_per_cycle(parts, "40"),
        "false_decodes_per_cycle_0": false_decodes_per_cycle(parts, "0"),
        "r6_genuine_C": r6_C, "r6_false_at_60": r6_false60, "r6_false_at_0": r6_false0,
        "r6_osd_false": r6_osd_false, "r6_n_cycles": r6_n,
    }
    print("Descriptive:", json.dumps(desc, indent=2))

    out = {
        "pooled": {k: v for k, v in pooled.items() if k not in ("K_per_cycle", "G_per_cycle")},
        "by_family": {f: {k: v for k, v in fs.items() if k not in ("K_per_cycle", "G_per_cycle")}
                      for f, fs in family_stats.items()},
        "gate_row": row, "gate_reason": reason, "descriptive": desc,
        "bar_s": BAR_S, "g_floor": G_FLOOR, "boot_seed": BOOT_SEED,
    }
    out_path = path.rsplit(".json", 1)[0] + "_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
