#!/usr/bin/env python3
"""C.3 -- characterising the candidate-GENERATION gap (QA-authored analysis only;
no native/managed code touched -- reuses C.2's own already-captured diagnostic
CSV and ALL.TXT files under the git-ignored artefacts/ tree, so no dev-task/
Developer session is needed per HK-000/HK-015/HK-011: this is pure offline
analysis, not a src/ change).

Background (qa/cycleframer-alignment-replay/2026-07-26-c2-llr-normalization-findings.md
section 3): of the 793 WSJT-X messages missed on the fixed 68-cycle corpus, C.2's
own Phase 1 matching found:
  - 135 (17.0%) matched one of our FAILED pass-0 candidates (the LLR-normalisation-
    eligible population Phase 2 would target).
  - ~658 had no candidate of ours (decoded or not) anywhere within tolerance; of
    those, an ad hoc check found ~10 near a DECODED candidate (a dedup/text-unpack
    loss), leaving ~648 (81.7% of the 793) with literally no candidate of ours
    anywhere nearby -- a candidate-GENERATION gap: ftx_find_candidates never
    proposes a sync candidate near that frequency/time at all. C.1 already tested
    raising K_MAX_CANDIDATES to 600 (4.3x the shipped 140) and found the real
    candidate population plateaus around 220-295 regardless of ceiling offered --
    so this is not an array-truncation question either. Neither C.1 nor C.2
    addresses this population; the consolidation doc's own decile-level "candidate
    yield is identical" claim cannot see it (a per-cycle COUNT can't distinguish
    "same count, right frequencies" from "same count, increasingly wrong
    frequencies").

Question this script asks: is the ~648 population better explained by
  (a) a plain weak-signal/SNR sensitivity gap (mundane -- WSJT-X's sync detector
      is simply more sensitive at low SNR), or
  (b) proximity to an already-decoded, stronger co-channel signal (structural --
      matches the consolidation doc's SS6.3 fallback: WSJT-X runs successive-
      interference-cancellation / extra decode passes that ft8_lib's single-pass
      sync search cannot replicate)?

Method: reproduce C.2's own population split independently first (verify, don't
just trust, the reported counts), then for the "no candidate anywhere" population
compare (i) WSJT-X-reported SNR and (ii) nearest-DECODED-candidate-of-ours
frequency distance on the same cycle, against the shared-hit population (which
gets an equivalent "nearest OTHER decoded neighbour" computed by excluding each
shared-hit message's own matching decode). Mann-Whitney U on both dimensions,
same discipline C.2 applied to prenorm_var/postnorm_mean_abs_llr.

ASCII-only console output (HK-009). NFR-021: this corpus contains real off-air
callsigns (public FT8 CQ/QSO traffic); this script reports aggregate statistics
only, never quotes an individual message/callsign, and all inputs/outputs live
under the git-ignored artefacts/ tree.
"""
from __future__ import annotations

import csv
import os
import re
import statistics as st
import sys
from math import isfinite, inf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from scipy.stats import mannwhitneyu
except ImportError:
    mannwhitneyu = None

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "artefacts", "20260725_live_run_1806")
WSJTX_ALL_TXT = os.path.join(BASE, "wsjt-x", "ALL.TXT")
WAV68_DIR     = os.path.join(BASE, "owsfz", "wav68")
MINE_ALL_TXT  = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "ALL.TXT")
DIAG_CSV      = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "candidate_diag.csv")

# Same tolerances C.2 used, recorded there for the same reason (one FT8 tone
# spacing (6.25 Hz) plus slop for two independent frequency estimators).
FREQ_TOL_HZ = 10.0
DT_TOL_S = 0.5

# A candidate within this distance of the "self" match is treated as the same
# decode, not a distinct neighbour, when computing a shared-hit message's
# nearest-OTHER-decoded-neighbour distance.
SELF_EXCLUDE_HZ = 1.0

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


def nearest_dist(freq: float, cands: list[dict], exclude_freq: float | None = None) -> float:
    best = inf
    for c in cands:
        if exclude_freq is not None and abs(c["freq_hz"] - exclude_freq) <= SELF_EXCLUDE_HZ:
            continue
        d = abs(c["freq_hz"] - freq)
        if d < best:
            best = d
    return best


def stats(label: str, vals: list[float]) -> None:
    vals = sorted(v for v in vals if isfinite(v))
    if not vals:
        print(f"  {label}: no finite values")
        return
    n = len(vals)
    print(f"  {label}: n={n} median={st.median(vals):.3f} mean={st.mean(vals):.3f} "
          f"q1={vals[n // 4]:.3f} q3={vals[(3 * n) // 4]:.3f} "
          f"min={vals[0]:.3f} max={vals[-1]:.3f}")


def mwu(label: str, a: list[float], b: list[float], a_name: str, b_name: str) -> None:
    a = [v for v in a if isfinite(v)]
    b = [v for v in b if isfinite(v)]
    if mannwhitneyu is None:
        print(f"  [WARN] scipy not available -- skipping Mann-Whitney U for {label}.")
        return
    if len(a) < 5 or len(b) < 5:
        print(f"  {label}: too few samples for a test ({a_name} n={len(a)}, {b_name} n={len(b)})")
        return
    u, p = mannwhitneyu(a, b, alternative="two-sided")
    direction = f"{a_name} LOWER" if st.median(a) < st.median(b) else f"{a_name} HIGHER or EQUAL"
    print(f"  {label}: U={u:.1f} p={p:.6g}  ({direction} than {b_name})")


def main() -> None:
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(WAV68_DIR) if f.endswith(".wav"))
    print(f"corpus: {len(cycles)} cycles (owsfz/wsjt-x filename intersection)")

    wsjtx_rows = parse_all_txt(WSJTX_ALL_TXT)
    wsjtx_by_cycle: dict[str, list[dict]] = {}
    for r in wsjtx_rows:
        if r["ts"] in set(cycles):
            wsjtx_by_cycle.setdefault(r["ts"], []).append(r)

    mine_rows = parse_all_txt(MINE_ALL_TXT)
    mine_msgset_by_cycle: dict[str, set[str]] = {}
    mine_freq_by_cycle_msg: dict[str, dict[str, float]] = {}
    for r in mine_rows:
        key = normalize_hash_tokens(r["message"])
        mine_msgset_by_cycle.setdefault(r["ts"], set()).add(key)
        mine_freq_by_cycle_msg.setdefault(r["ts"], {})[key] = r["freq"]

    cand_by_cycle = load_candidate_diag(DIAG_CSV)

    # ── Step 1: reproduce C.2's own population split independently ──────────
    wsjtx_total = 0
    shared_hit_rows: list[dict] = []
    matched_missed_failed: list[dict] = []       # matched to a FAILED candidate (C.2's population)
    near_decoded: list[dict] = []                # not matched to a failed cand, but near a DECODED one
    no_candidate_anywhere: list[dict] = []        # the population this script investigates

    for ts in cycles:
        my_msgs = mine_msgset_by_cycle.get(ts, set())
        cands = cand_by_cycle.get(ts, [])
        failed_cands = [c for c in cands if not c["decoded"]]
        decoded_cands = [c for c in cands if c["decoded"]]

        for row in wsjtx_by_cycle.get(ts, []):
            wsjtx_total += 1
            key = normalize_hash_tokens(row["message"])
            if key in my_msgs:
                shared_hit_rows.append({**row, "ts": ts})
                continue

            best_failed, best_failed_d = None, None
            for c in failed_cands:
                fd = abs(c["freq_hz"] - row["freq"])
                dd = abs(c["dt"] - row["dt"])
                if fd <= FREQ_TOL_HZ and dd <= DT_TOL_S:
                    if best_failed is None or fd < best_failed_d:
                        best_failed, best_failed_d = c, fd
            if best_failed is not None:
                matched_missed_failed.append({**row, "ts": ts})
                continue

            best_decoded, best_decoded_d = None, None
            for c in decoded_cands:
                fd = abs(c["freq_hz"] - row["freq"])
                dd = abs(c["dt"] - row["dt"])
                if fd <= FREQ_TOL_HZ and dd <= DT_TOL_S:
                    if best_decoded is None or fd < best_decoded_d:
                        best_decoded, best_decoded_d = c, fd
            if best_decoded is not None:
                near_decoded.append({**row, "ts": ts})
                continue

            no_candidate_anywhere.append({**row, "ts": ts})

    missed_total = wsjtx_total - len(shared_hit_rows)
    print(f"\nWSJT-X messages in these {len(cycles)} cycles: {wsjtx_total}")
    print(f"  shared hit (by text)                          : {len(shared_hit_rows)}")
    print(f"  missed (WSJT-X-only)                          : {missed_total}")
    print(f"    matched to a FAILED candidate of ours        : {len(matched_missed_failed)} "
          f"({100.0 * len(matched_missed_failed) / max(1, missed_total):.1f}% of missed) "
          f"-- C.2's Phase 1 population (LLR-normalisation-eligible)")
    print(f"    near a DECODED candidate, no failed match     : {len(near_decoded)} "
          f"({100.0 * len(near_decoded) / max(1, missed_total):.1f}% of missed) "
          f"-- dedup/text-unpack loss")
    print(f"    no candidate of ours anywhere within tolerance: {len(no_candidate_anywhere)} "
          f"({100.0 * len(no_candidate_anywhere) / max(1, missed_total):.1f}% of missed) "
          f"-- THE CANDIDATE-GENERATION GAP this script investigates")
    print(f"  (cross-check against the findings doc's reported 135 / ~10 / ~648 -- "
          f"expect close agreement, not necessarily bit-identical, since this is an "
          f"independent re-derivation from the same CSVs.)")

    if not no_candidate_anywhere:
        print("\n[VERDICT] Empty population -- nothing to compare.")
        return

    # ── Step 2: for each "no candidate anywhere" message, compute nearest- ───
    # decoded-candidate-of-ours distance on the same cycle (co-channel/SIC proxy).
    gap_nearest_decoded = []
    for row in no_candidate_anywhere:
        cands = cand_by_cycle.get(row["ts"], [])
        decoded_cands = [c for c in cands if c["decoded"]]
        gap_nearest_decoded.append(nearest_dist(row["freq"], decoded_cands))

    # ── Step 3: equivalent control for shared-hit messages -- nearest OTHER ──
    # decoded neighbour, excluding the message's own matching decode.
    hit_nearest_decoded = []
    for row in shared_hit_rows:
        ts = row["ts"]
        key = normalize_hash_tokens(row["message"])
        self_freq = mine_freq_by_cycle_msg.get(ts, {}).get(key)
        cands = cand_by_cycle.get(ts, [])
        decoded_cands = [c for c in cands if c["decoded"]]
        hit_nearest_decoded.append(nearest_dist(row["freq"], decoded_cands, exclude_freq=self_freq))

    print("\n-- Hypothesis (b) proxy: nearest DECODED candidate-of-ours, same cycle (Hz) --")
    stats("candidate-generation-gap (n=%d)" % len(gap_nearest_decoded), gap_nearest_decoded)
    stats("shared-hit, excl. self (n=%d)  " % len(hit_nearest_decoded), hit_nearest_decoded)
    mwu("nearest-decoded-neighbour distance", gap_nearest_decoded, hit_nearest_decoded,
        "gap", "shared-hit")
    close_gap = sum(1 for d in gap_nearest_decoded if d <= 50.0)
    close_hit = sum(1 for d in hit_nearest_decoded if d <= 50.0)
    print(f"  within 50 Hz of a decoded neighbour: gap {close_gap}/{len(gap_nearest_decoded)} "
          f"({100.0*close_gap/len(gap_nearest_decoded):.1f}%), "
          f"shared-hit {close_hit}/{len(hit_nearest_decoded)} "
          f"({100.0*close_hit/len(hit_nearest_decoded):.1f}%)")

    print("\n-- Hypothesis (a) proxy: WSJT-X-reported SNR (dB) --")
    gap_snr = [r["snr"] for r in no_candidate_anywhere]
    hit_snr = [r["snr"] for r in shared_hit_rows]
    stats("candidate-generation-gap", gap_snr)
    stats("shared-hit               ", hit_snr)
    mwu("SNR", gap_snr, hit_snr, "gap", "shared-hit")

    # ── Step 4: joint view -- does the gap population's SNR disadvantage ────
    # explain away the proximity effect, or is proximity still doing work
    # after roughly matching for SNR? Cheap check: split each population by
    # SNR band and compare nearest-decoded-neighbour distance within band.
    print("\n-- SNR-banded nearest-decoded-neighbour distance (controls for signal strength) --")
    print("snr_band | n_gap | med_dist(gap) | n_hit | med_dist(hit)")
    print("---------+-------+---------------+-------+---------------")
    all_snr = gap_snr + hit_snr
    if all_snr:
        lo = (min(all_snr) // 5) * 5
        hi = (max(all_snr) // 5) * 5
        band = lo
        while band <= hi:
            g = [d for r, d in zip(no_candidate_anywhere, gap_nearest_decoded)
                 if band <= r["snr"] < band + 5]
            h = [d for r, d in zip(shared_hit_rows, hit_nearest_decoded)
                 if band <= r["snr"] < band + 5]
            if g or h:
                print("  [%3d,%3d) | %5d | %13s | %5d | %13s"
                      % (band, band + 5, len(g),
                         ("%.1f" % st.median(g)) if g else "n/a",
                         len(h),
                         ("%.1f" % st.median(h)) if h else "n/a"))
            band += 5


if __name__ == "__main__":
    main()
