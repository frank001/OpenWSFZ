#!/usr/bin/env python3
"""D-001 C.2 Phase 2c, Part A -- LLR shrinkage trial weight-sweep analysis.

(dev-tasks/2026-07-26-d001-c2-phase2c-shrinkage-trial-and-ber.md Sec.2/Sec.4.)

WHAT THIS MEASURES
-------------------
For each shrinkage weight in {0.0, 0.25, 0.5, 0.75, 1.0}, swept via
`--llr-shrinkage-weight` against the fixed 68-cycle discovery corpus at the SHIPPED
K_MIN_SCORE=10/K_MAX_CANDIDATES=140 config (the only config under consideration for
shipping), this script reports the C.1/C.4 "matched decodes" table shape -- total
decodes, matched (exact hash-normalised text intersection with WSJT-X), unique-to-us,
Delta matched relative to weight 0.0, and unique share -- split across THREE populations
per the dev-task's Sec.2 item 5:

  1. THE 135 -- C.2 Phase 1's original matched-missed population (score >= 10; these
     candidates exist in the K10/cap140 candidate set the sweep actually runs against).
  2. THE 567 -- Phase 2a's expanded matched-missed population (score 5-9). These
     candidates were found to exist ONLY in a separate K_MIN_SCORE=4/K_MAX_CANDIDATES=2000
     candidate set (a different native compile-time build, not runtime-togglable) -- at
     the shipped K10/cap140 config this sweep runs at, NO candidate exists for them at
     all, with or without shrinkage. Reported anyway (expected near-zero) because the
     dev-task requires it and because a non-zero result there would be a genuine surprise
     worth flagging, not because a change is expected.
  3. MATCHED-HIT CONTROL -- the messages already matched (decoded) at weight 0.0 baseline.
     Checked for REGRESSION (do they remain matched at each subsequent weight) rather than
     recovery -- this is the "does shrinkage cost decodes" question in Sec.4's decision
     rule ("negative at any weight" row).

POPULATION IDENTITY, reproduced from committed artefacts (frozen, independent of this
session's runs):
  - THE 135: c2_llr_normalization_analysis.py's matched-missed population (C.2 Phase 1,
    K10/cap140, owsfz audio, candidate_diag.csv-based freq/dt match against WSJT-X-only
    messages).
  - THE 567: c2_phase2_ceiling_rederivation.py's "expanded_matched_missed" population
    (the 648 candidate-generation-gap population, reclassified against the K=4/cap2000
    candidate_diag.csv, keeping only those matching a FAILED candidate there after
    dropping messages that text-matched a genuine K=4/cap2000 recovery).

This script does NOT re-run those two scripts' full statistical analyses -- it reproduces
only the POPULATION IDENTITY (the list of WSJT-X (ts, message) pairs) using the same
frozen inputs and matching logic, then checks presence/absence of each message's TEXT in
this session's own weight-sweep ALL.TXT outputs.

ASCII-only console output per HK-009. NFR-021: aggregate statistics only -- no callsign,
message text, or per-record field is ever printed.
"""
from __future__ import annotations

import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "artefacts", "20260725_live_run_1806")
WSJTX_ALL_TXT = os.path.join(BASE, "wsjt-x", "ALL.TXT")
WAV68_DIR = os.path.join(BASE, "owsfz", "wav68")

# THE 135's own source run (C.2 Phase 1, owsfz audio, K10/cap140).
C2_MINE_ALL_TXT = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "ALL.TXT")
C2_DIAG_CSV     = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "candidate_diag.csv")

# THE 567's source: K=4/cap2000 candidate set (separate native build; Phase 2a).
K4_DIAG_CSV = os.path.join(BASE, "c4_min_score", "k4_cap2000", "k10_c0.10_n60", "candidate_diag.csv")
K4_ALL_TXT  = os.path.join(BASE, "c4_min_score", "k4_cap2000", "k10_c0.10_n60", "ALL.TXT")
K10_BASELINE_ALL_TXT = os.path.join(BASE, "c4_min_score", "k10", "k10_c0.10_n60", "ALL.TXT")

# This session's own weight-sweep outputs (K10/cap140, shipped config + shrinkage toggle).
SWEEP_BASE = os.path.join(BASE, "..", "d001_c2_phase2c", "sweep")
WEIGHTS = ["0.00", "0.25", "0.50", "0.75", "1.00"]

FREQ_TOL_HZ = 10.0
DT_TOL_S = 0.5

_HASH_BRACKET_RE = re.compile(r"<[^>]*>")


def normalize_hash_tokens(message: str) -> str:
    return _HASH_BRACKET_RE.sub("<HASH>", message)


def parse_all_txt(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            tok = line.split()
            if len(tok) < 8:
                print(f"[WARN] unparsable ALL.TXT line in {path}: {line!r}", file=sys.stderr)
                continue
            ts, snr, dt, freq, message = tok[0], tok[4], tok[5], tok[6], " ".join(tok[7:])
            rows.append({"ts": ts, "snr": float(snr), "dt": float(dt),
                         "freq": float(freq), "message": message})
    return rows


def load_candidate_diag(path: str) -> dict[str, list[dict]]:
    import csv
    by_cycle: dict[str, list[dict]] = {}
    with open(path, newline="", encoding="ascii", errors="replace") as fh:
        for row in csv.DictReader(fh):
            rec = {
                "freq_hz": float(row["freq_hz"]),
                "dt": float(row["dt"]),
                "decoded": row["decoded"] == "1",
            }
            by_cycle.setdefault(row["cycle_ts"], []).append(rec)
    return by_cycle


def has_any_candidate_nearby(freq: float, dt: float, cands: list[dict]) -> bool:
    for c in cands:
        if abs(c["freq_hz"] - freq) <= FREQ_TOL_HZ and abs(c["dt"] - dt) <= DT_TOL_S:
            return True
    return False


def nearest_candidate(freq: float, dt: float, cands: list[dict]) -> dict | None:
    best, best_fd = None, None
    for c in cands:
        fd = abs(c["freq_hz"] - freq)
        dd = abs(c["dt"] - dt)
        if fd <= FREQ_TOL_HZ and dd <= DT_TOL_S:
            if best is None or fd < best_fd:
                best, best_fd = c, fd
    return best


def compute_135_population(cycles: list[str]) -> set[tuple[str, str]]:
    """Reproduces c2_llr_normalization_analysis.py's matched-missed population identity.
    Returns a set of (ts, normalised_message_text) pairs."""
    wsjtx_rows = parse_all_txt(WSJTX_ALL_TXT)
    cycle_set = set(cycles)
    wsjtx_by_cycle: dict[str, list[dict]] = {}
    for r in wsjtx_rows:
        if r["ts"] in cycle_set:
            wsjtx_by_cycle.setdefault(r["ts"], []).append(r)

    mine_rows = parse_all_txt(C2_MINE_ALL_TXT)
    mine_msgset_by_cycle: dict[str, set[str]] = {}
    for r in mine_rows:
        mine_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    cand_by_cycle = load_candidate_diag(C2_DIAG_CSV)

    population: set[tuple[str, str]] = set()
    for ts in cycles:
        my_msgs = mine_msgset_by_cycle.get(ts, set())
        failed_cands = [c for c in cand_by_cycle.get(ts, []) if not c["decoded"]]
        for row in wsjtx_by_cycle.get(ts, []):
            key = normalize_hash_tokens(row["message"])
            if key in my_msgs:
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], failed_cands):
                population.add((ts, key))
    return population


def compute_648_population(cycles: list[str]) -> list[dict]:
    """Reproduces c3/c4/c2_phase2_ceiling_rederivation's 648 candidate-generation-gap
    population identity exactly (frozen, from C.2 Phase 1 owsfz-audio artefacts)."""
    wsjtx_rows = parse_all_txt(WSJTX_ALL_TXT)
    cycle_set = set(cycles)
    wsjtx_by_cycle: dict[str, list[dict]] = {}
    for r in wsjtx_rows:
        if r["ts"] in cycle_set:
            wsjtx_by_cycle.setdefault(r["ts"], []).append(r)

    mine_rows = parse_all_txt(C2_MINE_ALL_TXT)
    mine_msgset_by_cycle: dict[str, set[str]] = {}
    for r in mine_rows:
        mine_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    cand_by_cycle = load_candidate_diag(C2_DIAG_CSV)

    no_candidate_anywhere: list[dict] = []
    for ts in cycles:
        my_msgs = mine_msgset_by_cycle.get(ts, set())
        cands = cand_by_cycle.get(ts, [])
        failed_cands = [c for c in cands if not c["decoded"]]
        decoded_cands = [c for c in cands if c["decoded"]]
        for row in wsjtx_by_cycle.get(ts, []):
            key = normalize_hash_tokens(row["message"])
            if key in my_msgs:
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], failed_cands):
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], decoded_cands):
                continue
            no_candidate_anywhere.append({**row, "ts": ts})
    return no_candidate_anywhere


def compute_567_population(cycles: list[str], population_648: list[dict]) -> set[tuple[str, str]]:
    """Reproduces c2_phase2_ceiling_rederivation.py's expanded_matched_missed population
    identity: the 648, reclassified against K=4/cap2000, keeping those that match a
    FAILED candidate there, minus messages that text-matched a genuine K=4/cap2000
    recovery."""
    k4_cand_by_cycle = load_candidate_diag(K4_DIAG_CSV)
    k4_msgset_by_cycle: dict[str, set[str]] = {}
    for r in parse_all_txt(K4_ALL_TXT):
        k4_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    expanded_matched_missed: list[dict] = []
    for row in population_648:
        cands = k4_cand_by_cycle.get(row["ts"], [])
        found = nearest_candidate(row["freq"], row["dt"], cands)
        if found is not None and not found["decoded"]:
            expanded_matched_missed.append(row)

    text_matched = {(row["ts"], normalize_hash_tokens(row["message"]))
                     for row in population_648
                     if normalize_hash_tokens(row["message"]) in k4_msgset_by_cycle.get(row["ts"], set())}

    population = {(row["ts"], normalize_hash_tokens(row["message"]))
                  for row in expanded_matched_missed}
    population -= text_matched
    return population


def load_msgset_by_cycle(all_txt_path: str) -> dict[str, set[str]]:
    by_cycle: dict[str, set[str]] = {}
    for r in parse_all_txt(all_txt_path):
        by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))
    return by_cycle


def count_present(population: set[tuple[str, str]], msgset_by_cycle: dict[str, set[str]]) -> int:
    return sum(1 for ts, key in population if key in msgset_by_cycle.get(ts, set()))


def main() -> None:
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(WAV68_DIR) if f.endswith(".wav"))
    print(f"corpus: {len(cycles)} cycles (owsfz/wsjt-x filename intersection)\n")

    pop135 = compute_135_population(cycles)
    print(f"THE 135 population identity: n={len(pop135)} (expect 135)")

    population_648 = compute_648_population(cycles)
    print(f"648 candidate-generation-gap population identity: n={len(population_648)} (expect 648)")

    pop567 = compute_567_population(cycles, population_648)
    print(f"THE 567 population identity: n={len(pop567)} (expect 567)\n")

    # Matched-hit control: messages shared (decoded) at the weight=0.0 baseline.
    wsjtx_by_cycle = load_msgset_by_cycle(WSJTX_ALL_TXT)
    cycle_set = set(cycles)
    wsjtx_total = sum(len(v) for ts, v in wsjtx_by_cycle.items() if ts in cycle_set)

    baseline_path = os.path.join(SWEEP_BASE, "w0.00", "k10_c0.10_n60", "ALL.TXT")
    baseline_msgset = load_msgset_by_cycle(baseline_path)
    matched_hit_control = {(ts, key) for ts in cycles for key in baseline_msgset.get(ts, set())
                            if key in wsjtx_by_cycle.get(ts, set())}
    print(f"MATCHED-HIT CONTROL population identity (baseline weight=0.0 shared hits): "
          f"n={len(matched_hit_control)}\n")

    print("=" * 100)
    print("PART A -- LLR shrinkage weight sweep, K10/cap140 (shipped config), discovery corpus")
    print("=" * 100)

    base_matched = base_total = None
    rows = []
    for w in WEIGHTS:
        all_txt = os.path.join(SWEEP_BASE, f"w{w}", "k10_c0.10_n60", "ALL.TXT")
        if not os.path.exists(all_txt):
            print(f"[WARN] missing {all_txt} -- skipping weight {w}")
            continue
        my_rows = parse_all_txt(all_txt)
        by_cycle: dict[str, set[str]] = {}
        for r in my_rows:
            by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))
        dedup = sum(len(v) for v in by_cycle.values())
        matched = sum(len(v & wsjtx_by_cycle.get(ts, set())) for ts, v in by_cycle.items())
        unique = sum(len(v - wsjtx_by_cycle.get(ts, set())) for ts, v in by_cycle.items())

        if base_matched is None:
            base_matched, base_total = matched, len(my_rows)

        n135 = count_present(pop135, by_cycle)
        n567 = count_present(pop567, by_cycle)
        n_hit_regressed = len(matched_hit_control) - count_present(matched_hit_control, by_cycle)

        rows.append({
            "weight": w, "total": len(my_rows), "dedup": dedup, "matched": matched,
            "unique": unique, "d_total": len(my_rows) - base_total,
            "d_matched": matched - base_matched,
            "uniq_share": unique / max(1, dedup),
            "n135": n135, "n567": n567, "n_hit_regressed": n_hit_regressed,
        })

    hdr = (f"{'weight':>7} {'total':>6} {'dedup':>6} {'matched':>8} {'unique':>7} "
           f"{'d_total':>8} {'d_matched':>9} {'uniq_share':>11} "
           f"{'135_hit':>8} {'567_hit':>8} {'hit_ctrl_regressed':>19}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['weight']:>7} {r['total']:>6} {r['dedup']:>6} {r['matched']:>8} {r['unique']:>7} "
              f"{r['d_total']:>+8} {r['d_matched']:>+9} {r['uniq_share']:>10.1%} "
              f"{r['n135']:>8} {r['n567']:>8} {r['n_hit_regressed']:>19}")

    print()
    print("READING:")
    print(f"  - '135_hit'/'567_hit': count of THE 135 / THE 567 population's own messages")
    print(f"    present (matched) in this weight's decode output (out of {len(pop135)} / {len(pop567)}).")
    print(f"  - 'hit_ctrl_regressed': count of the matched-hit control population "
          f"(n={len(matched_hit_control)}, baseline weight=0.0 shared hits) that DROPPED OUT at this")
    print(f"    weight -- a positive number here is a regression (shrinkage costing an")
    print(f"    already-working decode), independent of whether 'd_matched' looks positive overall.")
    print(f"  - 'd_matched' is read against Sec.4's decision rule: >=50 / 10-49 / <10 / negative.")

    if base_matched is not None:
        print()
        print(f"[baseline] weight=0.00: total={base_total} matched={base_matched} "
              f"(793-gap ceiling context: WSJT-X total on these cycles={wsjtx_total})")


if __name__ == "__main__":
    main()
