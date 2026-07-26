#!/usr/bin/env python3
"""D-001 C.4 -- min-score sweep analysis (dev-tasks/2026-07-26-d001-c4-min-score-sweep.md).

For each of the four K_MIN_SCORE settings {10 (baseline), 8, 6, 4} -- all built with
K_MAX_CANDIDATES=600 per that dev-task's Sec.3 -- this script reports, over the fixed
68-cycle corpus (this time cross-decoding WSJT-X's OWN captured audio,
artefacts/20260725_live_run_1806/wsjt-x/wav68/, through OUR decoder, per the dev-task's
own Sec.3 step 3 deviation from C.1/C.2's owsfz-audio methodology -- keeps the already
0.5%-measured capture-chain difference out of this experiment):

  1. Count of C.3's specific 648 candidate-generation-gap messages that now have ANY
     candidate of ours (decoded or not) within tolerance in that setting's own
     candidate_diag.csv (dev-task Sec.4 step 4) -- reuses c3_candidate_generation_gap_
     analysis.py's own matching machinery/tolerances rather than reinventing them.
  2. Total decodes, failCands/meanAbsLLR (median/mean, pass-0 only, ldpc_stats.py's own
     methodology applied to this harness's --debug-log output).
  3. Decode elapsed time (median/p90 ms/cycle), derived from the gap between
     consecutive "Starting decode for cycle" timestamps in decode.log -- the harness
     processes WAVs strictly sequentially for a single --points restriction, so this
     gap is a direct per-WAV wall-time proxy (68 cycles -> 67 deltas).
  4. Unique-to-us decode count (ours minus WSJT-X ALL.TXT, mirroring C.1/C.3's own
     baseline ~49 count) -- the false-positive spot-check dev-task Sec.4 step 6 requires.

IMPORTANT: the "648" population is defined once, from C.2 Phase 1's ORIGINAL owsfz-audio
run (artefacts/20260725_live_run_1806/c2_phase1/k10_c0.10_n60/), exactly as
c3_candidate_generation_gap_analysis.py computed it -- that identity (which WSJT-X
messages) does not change just because C.4 decodes a different audio source; only
whether a NEW candidate now exists nearby (in the C.4 setting's own wsjt-x-audio-based
candidate_diag.csv) changes.

ASCII-only console output (HK-009). NFR-021: aggregate stats only, no callsigns.
"""
from __future__ import annotations

import csv
import os
import re
import statistics as st
import sys
from datetime import datetime
from math import inf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "artefacts", "20260725_live_run_1806")
WSJTX_ALL_TXT = os.path.join(BASE, "wsjt-x", "ALL.TXT")
WAV68_DIR     = os.path.join(BASE, "owsfz", "wav68")

# The 648 population's ORIGIN (C.2 Phase 1, owsfz audio, K_MIN_SCORE=10/K_MAX_CANDIDATES=140).
C2_MINE_ALL_TXT = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "ALL.TXT")
C2_DIAG_CSV     = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "candidate_diag.csv")

# The four C.4 settings (wsjt-x audio, K_MAX_CANDIDATES=600 throughout).
SETTINGS = [
    ("k10 (baseline)", os.path.join(BASE, "c4_min_score", "k10", "k10_c0.10_n60")),
    ("k8",             os.path.join(BASE, "c4_min_score", "k8",  "k10_c0.10_n60")),
    ("k6",             os.path.join(BASE, "c4_min_score", "k6",  "k10_c0.10_n60")),
    ("k4",             os.path.join(BASE, "c4_min_score", "k4",  "k10_c0.10_n60")),
    ("k8_cap2000",     os.path.join(BASE, "c4_min_score", "k8_cap2000", "k10_c0.10_n60")),
    ("k6_cap2000",     os.path.join(BASE, "c4_min_score", "k6_cap2000", "k10_c0.10_n60")),
    ("k4_cap2000",     os.path.join(BASE, "c4_min_score", "k4_cap2000", "k10_c0.10_n60")),
]

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
    by_cycle: dict[str, list[dict]] = {}
    with open(path, newline="", encoding="ascii", errors="replace") as fh:
        for row in csv.DictReader(fh):
            rec = {
                "freq_hz": float(row["freq_hz"]),
                "dt": float(row["dt"]),
                "score": int(row["score"]),
                "decoded": row["decoded"] == "1",
            }
            by_cycle.setdefault(row["cycle_ts"], []).append(rec)
    return by_cycle


def has_any_candidate_nearby(freq: float, dt: float, cands: list[dict]) -> bool:
    for c in cands:
        if abs(c["freq_hz"] - freq) <= FREQ_TOL_HZ and abs(c["dt"] - dt) <= DT_TOL_S:
            return True
    return False


def compute_648_population(cycles: list[str]) -> list[dict]:
    """Reproduces c3_candidate_generation_gap_analysis.py's Step 1 exactly, against the
    ORIGINAL C.2 Phase 1 (owsfz-audio) artefacts -- the fixed population C.4 tests."""
    wsjtx_rows = parse_all_txt(WSJTX_ALL_TXT)
    wsjtx_by_cycle: dict[str, list[dict]] = {}
    cycle_set = set(cycles)
    for r in wsjtx_rows:
        if r["ts"] in cycle_set:
            wsjtx_by_cycle.setdefault(r["ts"], []).append(r)

    mine_rows = parse_all_txt(C2_MINE_ALL_TXT)
    mine_msgset_by_cycle: dict[str, set[str]] = {}
    for r in mine_rows:
        key = normalize_hash_tokens(r["message"])
        mine_msgset_by_cycle.setdefault(r["ts"], set()).add(key)

    cand_by_cycle = load_candidate_diag(C2_DIAG_CSV)

    no_candidate_anywhere: list[dict] = []
    matched_missed_failed = 0
    near_decoded = 0
    shared_hit = 0

    for ts in cycles:
        my_msgs = mine_msgset_by_cycle.get(ts, set())
        cands = cand_by_cycle.get(ts, [])
        failed_cands = [c for c in cands if not c["decoded"]]
        decoded_cands = [c for c in cands if c["decoded"]]

        for row in wsjtx_by_cycle.get(ts, []):
            key = normalize_hash_tokens(row["message"])
            if key in my_msgs:
                shared_hit += 1
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], failed_cands):
                matched_missed_failed += 1
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], decoded_cands):
                near_decoded += 1
                continue
            no_candidate_anywhere.append({**row, "ts": ts})

    print(f"648-population re-derivation (from C.2 Phase 1 owsfz-audio artefacts):")
    print(f"  shared_hit={shared_hit} matched_missed_failed={matched_missed_failed} "
          f"near_decoded={near_decoded} no_candidate_anywhere={len(no_candidate_anywhere)}")
    print(f"  (C.3 findings doc reports 1235 / 135 / 10 / 648 respectively -- expect exact "
          f"agreement, same script logic against the same frozen artefacts.)")
    return no_candidate_anywhere


# ── decode.log parsing (ldpc_stats.py's own regex methodology, applied to the harness's
# --debug-log output instead of a live daemon log) ─────────────────────────────────────
TS = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \+\d{2}:00 "
RE_START = re.compile(r"^" + TS + r"\[DBG\] Starting decode for cycle")
RE_LLR = re.compile(r"^" + TS + r"\[DBG\] Iterative subtraction: pass 1 LDPC fail stats — "
                                 r"failCands=(\d+) meanAbsLLR=([\d.eE+-]+) prenormVar=([\d.eE+-]+)")


def parse_decode_log(path: str) -> tuple[list[float], list[int], list[float]]:
    """Returns (elapsed_ms_per_cycle, failCands[], meanAbsLLR[]) -- pass-0 (logged "pass 1") only."""
    starts: list[datetime] = []
    fail_cands: list[int] = []
    mean_abs: list[float] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = RE_START.match(line)
            if m:
                starts.append(datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f"))
                continue
            m = RE_LLR.match(line)
            if m:
                fail_cands.append(int(m.group(2)))
                mean_abs.append(float(m.group(3)))
    elapsed_ms = [(b - a).total_seconds() * 1000.0 for a, b in zip(starts, starts[1:])]
    return elapsed_ms, fail_cands, mean_abs


def stats_line(label: str, vals: list[float]) -> str:
    if not vals:
        return f"{label}: n=0"
    v = sorted(vals)
    n = len(v)
    median = st.median(v)
    mean = st.mean(v)
    p90 = v[min(n - 1, int(0.9 * (n - 1)))]
    return f"{label}: n={n} median={median:.2f} mean={mean:.2f} p90={p90:.2f}"


def main() -> None:
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(WAV68_DIR) if f.endswith(".wav"))
    print(f"corpus: {len(cycles)} matched cycles\n")

    population_648 = compute_648_population(cycles)
    print()

    wsjtx_rows = parse_all_txt(WSJTX_ALL_TXT)
    wsjtx_msgset_by_cycle: dict[str, set[str]] = {}
    cycle_set = set(cycles)
    for r in wsjtx_rows:
        if r["ts"] in cycle_set:
            wsjtx_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    header = (f"{'setting':<16} {'total_dec':>9} {'recov648':>9} {'recov%':>7} "
              f"{'unique_us':>9} {'uniq/rec':>9} {'failCands_med':>13} {'meanLLR_med':>11} "
              f"{'ms_med':>7} {'ms_p90':>7}")
    print(header)
    print("-" * len(header))

    for label, out_dir in SETTINGS:
        all_txt_path = os.path.join(out_dir, "ALL.TXT")
        diag_csv_path = os.path.join(out_dir, "candidate_diag.csv")
        decode_log_path = os.path.join(out_dir, "decode.log")

        mine_rows = parse_all_txt(all_txt_path)
        total_decodes = len(mine_rows)

        mine_msgset_by_cycle: dict[str, set[str]] = {}
        for r in mine_rows:
            mine_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

        unique_to_us = 0
        for ts, msgs in mine_msgset_by_cycle.items():
            wsjtx_set = wsjtx_msgset_by_cycle.get(ts, set())
            unique_to_us += len(msgs - wsjtx_set)

        cand_by_cycle = load_candidate_diag(diag_csv_path)
        cand_counts = [len(v) for v in cand_by_cycle.values()]
        cand_med = st.median(cand_counts) if cand_counts else 0
        cand_max_seen = max(cand_counts) if cand_counts else 0
        n_at_ceiling = sum(1 for c in cand_counts if c == cand_max_seen)
        recovered = 0
        for row in population_648:
            cands = cand_by_cycle.get(row["ts"], [])
            if has_any_candidate_nearby(row["freq"], row["dt"], cands):
                recovered += 1
        recov_pct = 100.0 * recovered / max(1, len(population_648))
        uniq_per_recov = (unique_to_us / recovered) if recovered else float("inf")

        elapsed_ms, fail_cands, mean_abs = parse_decode_log(decode_log_path)
        fc_med = st.median(fail_cands) if fail_cands else float("nan")
        fc_mean = st.mean(fail_cands) if fail_cands else float("nan")
        la_med = st.median(mean_abs) if mean_abs else float("nan")
        la_mean = st.mean(mean_abs) if mean_abs else float("nan")
        ms_sorted = sorted(elapsed_ms)
        ms_med = st.median(ms_sorted) if ms_sorted else float("nan")
        ms_p90 = ms_sorted[min(len(ms_sorted) - 1, int(0.9 * (len(ms_sorted) - 1)))] if ms_sorted else float("nan")

        print(f"{label:<16} {total_decodes:>9} {recovered:>9} {recov_pct:>6.1f}% "
              f"{unique_to_us:>9} {uniq_per_recov:>9.2f} {fc_med:>13.1f} {la_med:>11.3f} "
              f"{ms_med:>7.0f} {ms_p90:>7.0f}")

        print(f"    -- failCands mean={fc_mean:.2f} meanAbsLLR mean={la_mean:.3f} "
              f"(n_pass0_calls={len(fail_cands)}, n_elapsed_deltas={len(ms_sorted)})")
        print(f"    -- pass-0 candidates/cycle: median={cand_med:.0f} max_seen={cand_max_seen} "
              f"cycles_at_max={n_at_ceiling}/{len(cand_counts)} "
              f"{'[LIKELY CEILING-SATURATED]' if n_at_ceiling == len(cand_counts) and len(cand_counts) > 0 else ''}")

    print("\nnote: recov% is share of the fixed 648-message candidate-generation-gap "
          "population (C.3) that now has ANY candidate (decoded or not) nearby -- not "
          "the same as a decode. uniq/rec: unique-to-us decode count divided by recovered "
          "648-count -- a rising ratio flags a false-positive risk per dev-task Sec.4 step 6.")


if __name__ == "__main__":
    main()
