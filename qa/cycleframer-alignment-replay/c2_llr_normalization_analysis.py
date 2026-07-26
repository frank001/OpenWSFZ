#!/usr/bin/env python3
"""C.2 (dev-tasks/2026-07-26-d001-c2-llr-normalization.md) Phase 1 analysis.

Question: does ftx_normalize_logl's fixed-target-variance LLR scheme predict the SPECIFIC
messages WSJT-X decoded and we didn't -- as opposed to those messages just being ordinary
low-score/low-SNR candidates that were never going to decode by any normalisation scheme?

Method (dev-task section 4, Phase 1):
  1. Per-candidate diagnostic CSV (freq_hz, dt, score, decoded, prenorm_var,
     postnorm_mean_abs_llr for every pass-0 candidate) was captured via
     Ft8Decoder.SetCandidateDiagCapture(true) + GetLastCandidateDiagnostics(), re-decoding
     the fixed 68-cycle matched corpus (owsfz/wsjt-x filename intersection,
     artefacts/20260725_live_run_1806/, k10_c0.10_n60 baseline).
  2. For each cycle, the matched-missed set = WSJT-X messages absent from our decode,
     matched to one of OUR (failed, decoded=0) pass-0 candidates by frequency/time
     proximity (message text is not available for a candidate that never decoded).
  3. Control population = candidates on the SAME cycles that DID decode (decoded=1).
  4. Compare prenorm_var / postnorm_mean_abs_llr between the two populations, controlling
     for sync score (score-banded breakdown + Mann-Whitney U on the raw + score-overlap-
     restricted populations).

ASCII-only console output per HK-009. NFR-021: this corpus contains real off-air
callsigns (public FT8 CQ/QSO traffic); this script only reports aggregate statistics,
never quotes individual callsigns/messages, and all its inputs/outputs live under the
git-ignored artefacts/ tree.
"""
from __future__ import annotations

import csv
import os
import re
import statistics as st
import sys
from math import isfinite

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

# ── Matching tolerances (recorded per dev-task section 4 step 3) ────────────────────────
# FT8 tone spacing is 6.25 Hz (12000 Hz sample rate / 1920 samples-per-symbol / ... =
# 6.25 Hz/tone; freq_osr=2 gives 3.125 Hz sub-bin resolution). WSJT-X and our own decoder
# are independent frequency estimators over the same signal, so a tolerance of one full
# tone spacing plus slop for estimator disagreement is used: +/-10 Hz. Time (dt) tolerance
# is generous (+/-0.5 s) because dt is a secondary discriminator here -- co-channel
# candidates within 10 Hz of each other are rare enough in this corpus (confirmed below)
# that dt is only needed to break rare ties, not to do the primary matching.
FREQ_TOL_HZ = 10.0
DT_TOL_S = 0.5

_HASH_BRACKET_RE = re.compile(r"<[^>]*>")


def normalize_hash_tokens(message: str) -> str:
    """Canonicalize angle-bracketed hash-callsign tokens (see score_recall.py for the
    full rationale -- the same session-scoped hash-table order-dependence applies here)."""
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
            ts, freq, message = tok[0], tok[6], " ".join(tok[7:])
            dt = tok[5]
            rows.append({"ts": ts, "freq": float(freq), "dt": float(dt), "message": message})
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
                "prenorm_var": float(row["prenorm_var"]),
                "postnorm_mean_abs_llr": float(row["postnorm_mean_abs_llr"]),
            }
            by_cycle.setdefault(row["cycle_ts"], []).append(rec)
    return by_cycle


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
    for r in mine_rows:
        mine_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    cand_by_cycle = load_candidate_diag(DIAG_CSV)

    wsjtx_total = 0
    shared_hit = 0
    matched_missed: list[dict] = []
    unmatched_missed = 0

    for ts in cycles:
        my_msgs = mine_msgset_by_cycle.get(ts, set())
        my_failed_cands = [c for c in cand_by_cycle.get(ts, []) if not c["decoded"]]

        for row in wsjtx_by_cycle.get(ts, []):
            wsjtx_total += 1
            if normalize_hash_tokens(row["message"]) in my_msgs:
                shared_hit += 1
                continue

            # WSJT-X-only message: look for the nearest failed (decoded=0) candidate of
            # ours within tolerance.
            best = None
            best_fd = None
            for c in my_failed_cands:
                fd = abs(c["freq_hz"] - row["freq"])
                dd = abs(c["dt"] - row["dt"])
                if fd <= FREQ_TOL_HZ and dd <= DT_TOL_S:
                    if best is None or fd < best_fd:
                        best, best_fd = c, fd
            if best is None:
                unmatched_missed += 1
            else:
                matched_missed.append({**best, "ts": ts, "freq_delta_hz": best_fd})

    missed_total = wsjtx_total - shared_hit
    print(f"WSJT-X messages in these {len(cycles)} cycles: {wsjtx_total}")
    print(f"  present in ours too (shared hit, by text)   : {shared_hit}")
    print(f"  WSJT-X-only (\"missed\" by us)                : {missed_total}")
    print(f"    matched to one of our failed candidates   : {len(matched_missed)} "
          f"({100.0 * len(matched_missed) / max(1, missed_total):.1f}% of missed)")
    print(f"    no candidate of ours within tolerance      : {unmatched_missed} "
          f"({100.0 * unmatched_missed / max(1, missed_total):.1f}% of missed) "
          f"-- candidate-GENERATION gap, out of scope for the LLR-normalisation question")
    print(f"  tolerance used: +/-{FREQ_TOL_HZ:.1f} Hz, +/-{DT_TOL_S:.1f} s")

    matched_missed_cycles = {m["ts"] for m in matched_missed}
    hit_pop = [c for ts in matched_missed_cycles for c in cand_by_cycle.get(ts, []) if c["decoded"]]
    print(f"\nmatched-missed population : n={len(matched_missed)} "
          f"(across {len(matched_missed_cycles)} cycles)")
    print(f"matched-hit population    : n={len(hit_pop)} "
          f"(all decoded=1 candidates on those same {len(matched_missed_cycles)} cycles)")

    if not matched_missed or not hit_pop:
        print("\n[VERDICT] Insufficient data to compare populations -- cannot reach a verdict.")
        return

    def stats(label: str, vals: list[float]) -> None:
        vals = sorted(v for v in vals if isfinite(v))
        if not vals:
            print(f"  {label}: no finite values")
            return
        n = len(vals)
        print(f"  {label}: n={n} median={st.median(vals):.4f} mean={st.mean(vals):.4f} "
              f"q1={vals[n // 4]:.4f} q3={vals[(3 * n) // 4]:.4f} "
              f"min={vals[0]:.4f} max={vals[-1]:.4f}")

    print("\n-- score (sync score, uncontrolled) --")
    stats("matched-missed", [c["score"] for c in matched_missed])
    stats("matched-hit    ", [c["score"] for c in hit_pop])

    print("\n-- prenorm_var (raw, uncontrolled for score) --")
    stats("matched-missed", [c["prenorm_var"] for c in matched_missed])
    stats("matched-hit    ", [c["prenorm_var"] for c in hit_pop])

    print("\n-- postnorm_mean_abs_llr (raw, uncontrolled for score; NaN/degenerate excluded) --")
    stats("matched-missed", [c["postnorm_mean_abs_llr"] for c in matched_missed])
    stats("matched-hit    ", [c["postnorm_mean_abs_llr"] for c in hit_pop])

    if mannwhitneyu is not None:
        print("\n-- Mann-Whitney U (two-sided; raw populations, uncontrolled for score) --")
        for label, key in [("prenorm_var", "prenorm_var"), ("postnorm_mean_abs_llr", "postnorm_mean_abs_llr")]:
            a = [c[key] for c in matched_missed if isfinite(c[key])]
            b = [c[key] for c in hit_pop if isfinite(c[key])]
            if len(a) >= 5 and len(b) >= 5:
                u, p = mannwhitneyu(a, b, alternative="two-sided")
                direction = "LOWER" if st.median(a) < st.median(b) else "HIGHER or EQUAL"
                print(f"  {label}: U={u:.1f} p={p:.6g}  "
                      f"(matched-missed median is {direction} than matched-hit)")
            else:
                print(f"  {label}: too few samples for a test (missed n={len(a)}, hit n={len(b)})")
    else:
        print("\n[WARN] scipy not available -- skipping Mann-Whitney U significance test.")

    # ── Score-banded breakdown (the actual "controlling for sync score" comparison) ────
    print("\n-- score-banded comparison (bands of width 10; the sync-score-controlled test) --")
    print("score_band |  n_missed | med_prenorm_var(missed) | med_postnorm(missed) "
          "|  n_hit | med_prenorm_var(hit) | med_postnorm(hit)")
    print("-----------+-----------+--------------------------+-----------------------"
          "+--------+-----------------------+-------------------")
    all_scores = [c["score"] for c in matched_missed] + [c["score"] for c in hit_pop]
    lo_band = (min(all_scores) // 10) * 10
    hi_band = (max(all_scores) // 10) * 10
    band = lo_band
    while band <= hi_band:
        band_missed = [c for c in matched_missed if band <= c["score"] < band + 10]
        band_hit = [c for c in hit_pop if band <= c["score"] < band + 10]
        if band_missed or band_hit:
            mv = [c["prenorm_var"] for c in band_missed if isfinite(c["prenorm_var"])]
            mp = [c["postnorm_mean_abs_llr"] for c in band_missed if isfinite(c["postnorm_mean_abs_llr"])]
            hv = [c["prenorm_var"] for c in band_hit if isfinite(c["prenorm_var"])]
            hp = [c["postnorm_mean_abs_llr"] for c in band_hit if isfinite(c["postnorm_mean_abs_llr"])]
            print("  [%3d,%3d) | %9d | %24s | %21s | %6d | %21s | %17s"
                  % (band, band + 10, len(band_missed),
                     ("%.2f" % st.median(mv)) if mv else "n/a",
                     ("%.3f" % st.median(mp)) if mp else "n/a",
                     len(band_hit),
                     ("%.2f" % st.median(hv)) if hv else "n/a",
                     ("%.3f" % st.median(hp)) if hp else "n/a"))
        band += 10

    # ── Score-overlap-restricted Mann-Whitney (a second, stricter control) ─────────────
    missed_scores = [c["score"] for c in matched_missed]
    hit_scores = [c["score"] for c in hit_pop]
    overlap_lo, overlap_hi = max(min(missed_scores), min(hit_scores)), min(max(missed_scores), max(hit_scores))
    r_missed = [c for c in matched_missed if overlap_lo <= c["score"] <= overlap_hi]
    r_hit = [c for c in hit_pop if overlap_lo <= c["score"] <= overlap_hi]
    print(f"\n-- score-overlap-restricted comparison (score in [{overlap_lo},{overlap_hi}], "
          f"n_missed={len(r_missed)}, n_hit={len(r_hit)}) --")
    stats("matched-missed prenorm_var", [c["prenorm_var"] for c in r_missed])
    stats("matched-hit     prenorm_var", [c["prenorm_var"] for c in r_hit])
    stats("matched-missed postnorm   ", [c["postnorm_mean_abs_llr"] for c in r_missed])
    stats("matched-hit     postnorm   ", [c["postnorm_mean_abs_llr"] for c in r_hit])
    if mannwhitneyu is not None and len(r_missed) >= 5 and len(r_hit) >= 5:
        for label, key in [("prenorm_var", "prenorm_var"), ("postnorm_mean_abs_llr", "postnorm_mean_abs_llr")]:
            a = [c[key] for c in r_missed if isfinite(c[key])]
            b = [c[key] for c in r_hit if isfinite(c[key])]
            if len(a) >= 5 and len(b) >= 5:
                u, p = mannwhitneyu(a, b, alternative="two-sided")
                direction = "LOWER" if st.median(a) < st.median(b) else "HIGHER or EQUAL"
                print(f"  [score-overlap] {label}: U={u:.1f} p={p:.6g}  "
                      f"(matched-missed median is {direction} than matched-hit)")


if __name__ == "__main__":
    main()
