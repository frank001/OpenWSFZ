#!/usr/bin/env python3
"""D-001 Arm S.1 -- spectral locality, per the Architect's spec rev3:
2026-07-31-1649-architect-arm-s1-spec-rev3-segment-1-execution-ready.md

Question: is Measurement D's within-band density penalty frequency-LOCAL (H3 collision / H2
masking -- a co-channel signal within the reading width) or cycle-GLOBAL (H1 candidate
budget / H4 hash rejection -- a per-cycle capacity constant)? These differ by roughly an
order of magnitude in engineering cost (subtractive multi-pass architecture vs a constant),
so this arm runs first and alone, on segment 1 of the 20m corpus only (segment 2 is VOID as
a density comparison per `1602`, and running S.1 on it would inherit that void).

Reuses, does not reimplement (rev3 spec Sec3.1):
  - anova_common.parse_all_txt / filter_rows_by_window / normalize_hash_tokens
  - measurement_d_within_band_density.stratify_cycles / wilson_interval / median_or_nan /
    BIN_WIDTH / MIN_N
  - measurement_d_segment_rerun's segment-1 cut (2026-07-30T00:00:00)
  - The single-pass greedy matching mechanism identical to matched_stratified_bins, adapted
    here to return a PER-ROW matched flag (rather than pre-aggregated bins) because this arm
    needs a 3-way tally (density stratum x locality cell x SNR bin), not D's 2-way one.

Pre-registered reading rule, mandatory null and mandatory self-checks are all quoted
verbatim from the spec and are NOT to be edited after seeing any output of this script.

NFR-021: message text is read only to build the match key (identical to anova_common.py's
own match_pairs()) and is never printed or written out. Only aggregate per-bin counts and
per-cycle/per-row NUMERIC fields (density, n_local, matched flag) survive past parsing.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import math
import os
import random
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "endurance"))
from anova_common import filter_rows_by_window, normalize_hash_tokens, parse_all_txt  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from measurement_d_within_band_density import (  # noqa: E402
    BIN_WIDTH,
    MIN_N,
    median_or_nan,
    stratify_cycles,
    wilson_interval,
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ARTEFACTS = os.path.join(ROOT, "artefacts")
CORPUS_ROOT = os.path.join(ARTEFACTS, "20260729_live_run_1831-8081", "owsfz", "20m")
OUR_PATH = os.path.join(CORPUS_ROOT, "ALL.TXT")
REF_PATH = os.path.join(CORPUS_ROOT, "jt9_ALL.TXT")

import datetime  # noqa: E402
SEGMENT_1_CUT = datetime.datetime(2026, 7, 30, 0, 0, 0)

W_LADDER = [25, 50, 100, 200, 400, 800]
READING_W = 50

# --- Sec3.3 pre-registered fixed integer cuts (density axis; segment 1's own quartiles) ---
DENSITY_SPARSE_MAX = 23   # n_cycle <= 23 -> sparse
DENSITY_DENSE_MIN = 41    # n_cycle >= 41 -> dense

# --- Sec3.3 pre-registered fixed integer cuts (locality axis at W=50, per-stratum) --------
LOCALITY_CUTS = {
    "sparse": dict(lo_max=0, hi_min=1),   # n_local(50)==0 -> lo; >=1 -> hi
    "dense": dict(lo_max=1, hi_min=2),    # n_local(50)<=1 -> lo; >=2 -> hi
}

# --- Sec6 mandatory self-check expected/threshold values, quoted from the spec ------------
EXPECTED_MATCHED_TOTAL = 9751
DENSITY_CONTRAST_MIN = 2.0
LOCALITY_CONTRAST_MIN = 1.0
COMMON_SUPPORT_MIN_BINS = 10
EXPECTED_CUTS = {  # self-check 6, at W=50: (lo, hi) decode counts
    "sparse": (1620, 1631),
    "dense": (4359, 3410),
}
NULL_RUNS = 20
NULL_BAND_PTS = 2.0


def match_flags(ref_rows: list[dict], our_rows: list[dict]) -> list[bool]:
    """Identical mechanism to measurement_d_within_band_density.matched_stratified_bins's
    single-pass greedy consumption, over the FULL corpus (here: segment 1), in reference
    arrival order -- but returns a per-row flag instead of pre-aggregating into bins, since
    this arm needs a 3-way tally D's own function doesn't produce."""
    our_by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in our_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        our_by_key[key].append(r)
    consumed: Counter = Counter()
    flags = []
    for r in ref_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        avail = len(our_by_key.get(key, ()))
        is_match = consumed[key] < avail
        if is_match:
            consumed[key] += 1
        flags.append(is_match)
    return flags


def density_stratum_of(n_cycle: int) -> str:
    if n_cycle <= DENSITY_SPARSE_MAX:
        return "sparse"
    if n_cycle >= DENSITY_DENSE_MIN:
        return "dense"
    return "middle"


def compute_n_local(ref_rows: list[dict], W: float, freqs_override: dict[str, list[float]] | None = None
                     ) -> list[float]:
    """n_local(W) per reference decode: count of OTHER reference decodes in the SAME cycle
    within +-W Hz, excluding itself (Sec3.2). O(k^2) per cycle of size k -- cycles here run to
    a few dozen decodes, trivial. `freqs_override`, if given, maps cycle ts -> a permuted list
    of freq_hz values (same length/order as that cycle's row list) -- used by the mandatory
    null (Sec5) to recompute n_local under a within-cycle shuffle without touching the real
    freq_hz field on the row dicts themselves."""
    by_cycle: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(ref_rows):
        by_cycle[r["ts"]].append(i)

    n_local = [0.0] * len(ref_rows)
    for cycle, idxs in by_cycle.items():
        if freqs_override is not None:
            freqs = freqs_override[cycle]
        else:
            freqs = [ref_rows[i]["freq_hz"] for i in idxs]
        k = len(idxs)
        for a in range(k):
            cnt = 0
            fa = freqs[a]
            for b in range(k):
                if a == b:
                    continue
                if abs(freqs[b] - fa) <= W:
                    cnt += 1
            n_local[idxs[a]] = cnt
    return n_local


def locality_cell_fixed(stratum: str, nloc50: float) -> str | None:
    """Sec3.3's fixed, pre-registered, per-stratum cuts at W=50. Only sparse/dense rows get a
    cell; middle-quartile rows return None (not tallied, matching D's own convention)."""
    if stratum not in LOCALITY_CUTS:
        return None
    cuts = LOCALITY_CUTS[stratum]
    if stratum == "sparse":
        return "lo" if nloc50 <= cuts["lo_max"] else ("hi" if nloc50 >= cuts["hi_min"] else None)
    else:
        return "lo" if nloc50 <= cuts["lo_max"] else ("hi" if nloc50 >= cuts["hi_min"] else None)


def locality_cell_median_split(nloc: float, median: float) -> str:
    """Sec3.3: 'At every other W, use each stratum's own median n_local(W), ties to the low
    side.' Diagnostic only (W-ladder), never used for the W=50 reading."""
    return "lo" if nloc <= median else "hi"


def duplicate_key_rate_in(ref_rows: list[dict], membership: list[bool]) -> float:
    """Generalises measurement_d_within_band_density.duplicate_key_rate to an arbitrary
    boolean row membership mask (that module's version is fixed to a stratum name), needed
    here because self-check 4 operates on the 4 density x locality CELLS, not on the 2
    density strata D itself uses."""
    keys = [(r["ts"], normalize_hash_tokens(r["message"]))
            for r, m in zip(ref_rows, membership) if m]
    if not keys:
        return float("nan")
    counts = Counter(keys)
    dup_rows = sum(c for c in counts.values() if c > 1)
    return dup_rows / len(keys)


def build_bin_table(ref_rows: list[dict], matched: list[bool], stratum_of_row: list[str],
                     cell_of_row: list[str | None]) -> dict[float, dict[str, list[int]]]:
    """bin -> {'sparse_lo': [total,matched], 'sparse_hi': [...], 'dense_lo': [...],
    'dense_hi': [...]}, binned by the REFERENCE's own reported SNR (never ours -- the S7
    gain-error slope would re-enter as noise), 2 dB bins (Sec3.4)."""
    table: dict[float, dict[str, list[int]]] = defaultdict(
        lambda: {"sparse_lo": [0, 0], "sparse_hi": [0, 0], "dense_lo": [0, 0], "dense_hi": [0, 0]})
    for r, m, strat, cell in zip(ref_rows, matched, stratum_of_row, cell_of_row):
        if strat not in ("sparse", "dense") or cell not in ("lo", "hi"):
            continue
        key = f"{strat}_{cell}"
        b = math.floor(r["snr"] / BIN_WIDTH) * BIN_WIDTH
        table[b][key][0] += 1
        if m:
            table[b][key][1] += 1
    return table


def common_support_bins(table: dict[float, dict[str, list[int]]]) -> list[float]:
    cells = ("sparse_lo", "sparse_hi", "dense_lo", "dense_hi")
    return sorted(b for b, cell_counts in table.items()
                  if all(cell_counts[c][0] >= MIN_N for c in cells))


def recall(cell_counts: list[int]) -> float:
    tot, m = cell_counts
    return m / tot if tot else float("nan")


def compute_deltas(table: dict[float, dict[str, list[int]]], usable_bins: list[float]
                    ) -> tuple[float, float, float, float]:
    """Returns (delta_local, delta_cycle, delta_local_sparse, delta_local_dense) per the
    exact reduction Sec3.4 specifies:
      Delta_local = recall(lo) - recall(hi), computed WITHIN each density stratum (per usable
        bin, then median across bins), then averaged over the two strata.
      Delta_cycle = recall(sparse) - recall(dense), computed WITHIN each locality cell (per
        usable bin, then median across bins), then averaged over the two cells.
    Units: percentage points throughout."""
    diff_local_sparse = []
    diff_local_dense = []
    diff_cycle_lo = []
    diff_cycle_hi = []
    for b in usable_bins:
        c = table[b]
        diff_local_sparse.append((recall(c["sparse_lo"]) - recall(c["sparse_hi"])) * 100)
        diff_local_dense.append((recall(c["dense_lo"]) - recall(c["dense_hi"])) * 100)
        diff_cycle_lo.append((recall(c["sparse_lo"]) - recall(c["dense_lo"])) * 100)
        diff_cycle_hi.append((recall(c["sparse_hi"]) - recall(c["dense_hi"])) * 100)

    dl_sparse = median_or_nan(diff_local_sparse)
    dl_dense = median_or_nan(diff_local_dense)
    dc_lo = median_or_nan(diff_cycle_lo)
    dc_hi = median_or_nan(diff_cycle_hi)

    delta_local = (dl_sparse + dl_dense) / 2.0
    delta_cycle = (dc_lo + dc_hi) / 2.0
    return delta_local, delta_cycle, dl_sparse, dl_dense


def reading_rule(delta_local: float, delta_cycle: float) -> tuple[int, str, str]:
    """Sec4, quoted verbatim, evaluated in strict order -- first match wins."""
    if delta_local <= -8 or delta_cycle <= -8:
        return 0, "Reversal -- crowding *helps*, which no hypothesis predicts", \
            "ESCALATE. Do not interpret. Suspect the metric before the mechanism."
    if delta_local >= 8 and abs(delta_cycle) < 3:
        return 1, "Penalty is frequency-local", \
            "H3/H2. Row 4 needs multi-signal handling. Expensive; strengthens row 5. " \
            "S.2 is not run. ESCALATE before any engineering."
    if delta_cycle >= 8 and abs(delta_local) < 3:
        return 2, "Penalty is cycle-global", \
            "H1/H4. Capacity or budget. S.2a runs. A cheap component is likely; " \
            "strengthens row 4."
    if delta_local >= 8 and delta_cycle >= 8:
        ratio = delta_local / delta_cycle if delta_cycle else float("nan")
        return 3, "Two sub-mechanisms", \
            f"Both proceed. Report the ratio Delta_local/Delta_cycle = {ratio:.3f} -- it " \
            "prices the split."
    if abs(delta_local) < 3 and abs(delta_cycle) < 3:
        return 4, "Effect vanishes under joint stratification", \
            "Measurement D's effect is confounded by something neither variable captures. " \
            "ESCALATE. Do not rationalise."
    return 5, "Partial", "Ambiguous. Do not interpret further. ESCALATE."


def main() -> int:
    out_dir = os.path.dirname(__file__)
    report: list[str] = []
    report.append("# Arm S.1 -- spectral locality, segment 1 result (D-001)\n")
    report.append("Spec: `2026-07-31-1649-architect-arm-s1-spec-rev3-segment-1-execution-"
                   "ready.md`, quoted verbatim throughout. Corpus: "
                   "`artefacts/20260729_live_run_1831-8081/owsfz/20m`, restricted to "
                   "segment 1 (< 2026-07-30 00:00:00). Prerequisite (drift screen, segment 1) "
                   "cleared: `2026-07-31-1719-qa-drift-screen-8081-20m-per-segment-result.md` "
                   "(peak drift 0.136s vs the 0.5s bar).\n")

    our_rows_all = parse_all_txt(OUR_PATH)
    ref_rows_all = parse_all_txt(REF_PATH)
    our_rows = filter_rows_by_window(our_rows_all, None, SEGMENT_1_CUT)
    ref_rows = filter_rows_by_window(ref_rows_all, None, SEGMENT_1_CUT)
    print(f"segment 1: our={len(our_rows)} ref={len(ref_rows)}")

    stratum, density_by_cycle, q1, q3 = stratify_cycles(ref_rows)
    # Sec3.3 says these are now fixed integers, pre-registered from segment 1's own
    # quartiles -- confirm stratify_cycles (reused unmodified) reproduces the same cutoffs
    # the spec pre-registered, rather than silently trusting they still match.
    cutoffs_match = (math.floor(q1) == DENSITY_SPARSE_MAX or round(q1) == DENSITY_SPARSE_MAX) \
        and (math.ceil(q3) == DENSITY_DENSE_MIN or round(q3) == DENSITY_DENSE_MIN)
    print(f"stratify_cycles cutoffs: q1={q1} q3={q3} "
          f"(spec pre-registered sparse<={DENSITY_SPARSE_MAX}, dense>={DENSITY_DENSE_MIN}) "
          f"-- {'MATCH' if cutoffs_match else 'MISMATCH'}")
    report.append(f"**Cutoff reproduction check:** `stratify_cycles` on segment 1 gives "
                  f"q1={q1}, q3={q3}; spec pre-registers sparse<={DENSITY_SPARSE_MAX}, "
                  f"dense>={DENSITY_DENSE_MIN}. **{'MATCH' if cutoffs_match else 'MISMATCH -- STOP'}**\n")
    if not cutoffs_match:
        report.append("**MISMATCH on the density cutoffs the spec pre-registered against "
                       "this exact corpus -- something has changed (different ALL.TXT "
                       "content, different filter). STOPPING. Run is VOID.**\n")
        with open(os.path.join(out_dir, "measurement_s1_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report) + "\n")
        return 1

    matched = match_flags(ref_rows, our_rows)
    total_matched = sum(matched)

    # ================= Self-check 1: matching gate =================
    sc1_pass = total_matched == EXPECTED_MATCHED_TOTAL
    print(f"self-check 1 (matching gate): total_matched={total_matched} "
          f"expected={EXPECTED_MATCHED_TOTAL} [{'PASS' if sc1_pass else 'FAIL -- VOID'}]")
    report.append(f"## Self-check 1 -- matching gate\n\nSegment 1 total matched: "
                  f"**{total_matched}** (expected **{EXPECTED_MATCHED_TOTAL}**). "
                  f"**{'PASS' if sc1_pass else 'FAIL -- RUN IS VOID'}**\n")
    if not sc1_pass:
        report.append("Matching has been perturbed; nothing downstream means what it says. "
                       "STOPPING.\n")
        with open(os.path.join(out_dir, "measurement_s1_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report) + "\n")
        return 1

    # ================= Self-check 2: density contrast =================
    sparse_cycles = [c for c, s in stratum.items() if s == "sparse"]
    dense_cycles = [c for c, s in stratum.items() if s == "dense"]
    sparse_mean = statistics.mean(density_by_cycle[c] for c in sparse_cycles)
    dense_mean = statistics.mean(density_by_cycle[c] for c in dense_cycles)
    contrast = dense_mean / sparse_mean if sparse_mean else float("nan")
    sc2_pass = contrast >= DENSITY_CONTRAST_MIN
    print(f"self-check 2 (density contrast): sparse={sparse_mean:.2f} dense={dense_mean:.2f} "
          f"contrast={contrast:.2f}x (bar {DENSITY_CONTRAST_MIN}x) "
          f"[{'PASS' if sc2_pass else 'FAIL -- VOID'}]")
    report.append(f"## Self-check 2 -- density contrast\n\n{len(sparse_cycles)} sparse "
                  f"cycles (mean {sparse_mean:.2f}/cyc), {len(dense_cycles)} dense cycles "
                  f"(mean {dense_mean:.2f}/cyc). Contrast **{contrast:.2f}x** "
                  f"(bar >= {DENSITY_CONTRAST_MIN}x, expected 2.65x). "
                  f"**{'PASS' if sc2_pass else 'FAIL -- RUN IS VOID'}**\n")
    if not sc2_pass:
        with open(os.path.join(out_dir, "measurement_s1_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report) + "\n")
        return 1

    stratum_of_row = [density_stratum_of(density_by_cycle[r["ts"]]) for r in ref_rows]

    # n_local at the reading width, and the full W-ladder (diagnostic)
    n_local_by_w = {W: compute_n_local(ref_rows, W) for W in W_LADDER}
    nloc50 = n_local_by_w[READING_W]
    cell_of_row = [locality_cell_fixed(strat, nl) for strat, nl in zip(stratum_of_row, nloc50)]

    # ================= Self-check 2b: locality contrast =================
    report.append("## Self-check 2b -- locality contrast (W=50)\n")
    report.append("| stratum | mean n_local(lo) | mean n_local(hi) | contrast (hi-lo) | verdict |")
    report.append("|---|---:|---:|---:|---|")
    sc2b_pass = True
    for strat in ("sparse", "dense"):
        lo_vals = [nl for s, c, nl in zip(stratum_of_row, cell_of_row, nloc50)
                   if s == strat and c == "lo"]
        hi_vals = [nl for s, c, nl in zip(stratum_of_row, cell_of_row, nloc50)
                   if s == strat and c == "hi"]
        mlo = statistics.mean(lo_vals) if lo_vals else float("nan")
        mhi = statistics.mean(hi_vals) if hi_vals else float("nan")
        gap = mhi - mlo
        ok = (not math.isnan(gap)) and gap >= LOCALITY_CONTRAST_MIN
        sc2b_pass = sc2b_pass and ok
        report.append(f"| {strat} | {mlo:.3f} | {mhi:.3f} | {gap:.3f} | "
                      f"{'PASS' if ok else 'FAIL'} |")
        print(f"self-check 2b ({strat}): mean_lo={mlo:.3f} mean_hi={mhi:.3f} gap={gap:.3f} "
              f"(bar >= {LOCALITY_CONTRAST_MIN}) [{'PASS' if ok else 'FAIL'}]")
    report.append(f"\n**{'PASS' if sc2b_pass else 'FAIL -- RUN IS VOID'}** -- gap >= "
                  f"{LOCALITY_CONTRAST_MIN} required in BOTH strata.\n")
    if not sc2b_pass:
        with open(os.path.join(out_dir, "measurement_s1_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report) + "\n")
        return 1

    # ================= Self-check 6: cut reproduction =================
    # (checked before 3/4 in code order -- cheap, mechanical, catches an n_local
    # implementation divergence before any statistical machinery runs on top of it. Spec
    # numbers it 6 but calls it "the strongest gate here"; order among self-checks doesn't
    # matter since ALL must pass before the reading rule regardless.)
    report.append("## Self-check 6 -- cut reproduction (W=50)\n")
    report.append("| stratum | lo (computed) | hi (computed) | lo (expected) | hi (expected) | verdict |")
    report.append("|---|---:|---:|---:|---:|---|")
    sc6_pass = True
    for strat in ("sparse", "dense"):
        lo_n = sum(1 for s, c in zip(stratum_of_row, cell_of_row) if s == strat and c == "lo")
        hi_n = sum(1 for s, c in zip(stratum_of_row, cell_of_row) if s == strat and c == "hi")
        exp_lo, exp_hi = EXPECTED_CUTS[strat]
        ok = (lo_n == exp_lo) and (hi_n == exp_hi)
        sc6_pass = sc6_pass and ok
        report.append(f"| {strat} | {lo_n} | {hi_n} | {exp_lo} | {exp_hi} | "
                      f"{'PASS' if ok else 'FAIL'} |")
        print(f"self-check 6 ({strat}): lo={lo_n} hi={hi_n} expected=({exp_lo},{exp_hi}) "
              f"[{'PASS' if ok else 'FAIL'}]")
    report.append(f"\n**{'PASS' if sc6_pass else 'FAIL -- RUN IS VOID'}**\n")
    if not sc6_pass:
        report.append("n_local implementation differs from the one the cuts were chosen on. "
                       "STOP and reconcile before proceeding.\n")
        with open(os.path.join(out_dir, "measurement_s1_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report) + "\n")
        return 1

    # ================= Build the 4-cell x SNR-bin table =================
    table = build_bin_table(ref_rows, matched, stratum_of_row, cell_of_row)
    usable_bins = common_support_bins(table)

    # ================= Self-check 3: common support =================
    sc3_pass = len(usable_bins) >= COMMON_SUPPORT_MIN_BINS
    print(f"self-check 3 (common support): usable_bins={len(usable_bins)} "
          f"(bar >= {COMMON_SUPPORT_MIN_BINS}, expected 18) "
          f"[{'PASS' if sc3_pass else 'FAIL -- VOID'}]")
    report.append(f"## Self-check 3 -- common support\n\nUsable SNR bins (n>=20 in all four "
                  f"cells): **{len(usable_bins)}** (bar >= {COMMON_SUPPORT_MIN_BINS}, "
                  f"expected 18). **{'PASS' if sc3_pass else 'FAIL -- RUN IS VOID'}**\n")
    if not sc3_pass:
        with open(os.path.join(out_dir, "measurement_s1_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report) + "\n")
        return 1

    # ================= Compute Deltas (real data) =================
    delta_local, delta_cycle, dl_sparse, dl_dense = compute_deltas(table, usable_bins)
    print(f"Delta_local = {delta_local:+.3f} pts (sparse {dl_sparse:+.3f}, dense {dl_dense:+.3f})")
    print(f"Delta_cycle = {delta_cycle:+.3f} pts")

    # ================= Self-check 4: duplicate-key confound =================
    def mask(strat: str, cell: str) -> list[bool]:
        return [s == strat and c == cell for s, c in zip(stratum_of_row, cell_of_row)]

    dup = {(s, c): duplicate_key_rate_in(ref_rows, mask(s, c))
           for s in ("sparse", "dense") for c in ("lo", "hi")}
    gap_local_sparse = abs(dup[("sparse", "hi")] - dup[("sparse", "lo")]) * 100
    gap_local_dense = abs(dup[("dense", "hi")] - dup[("dense", "lo")]) * 100
    gap_cycle_lo = abs(dup[("dense", "lo")] - dup[("sparse", "lo")]) * 100
    gap_cycle_hi = abs(dup[("dense", "hi")] - dup[("sparse", "hi")]) * 100
    gap_local = max(gap_local_sparse, gap_local_dense)
    gap_cycle = max(gap_cycle_lo, gap_cycle_hi)

    confound_local = gap_local >= abs(delta_local) / 10.0
    confound_cycle = gap_cycle >= abs(delta_cycle) / 10.0
    sc4_pass = not (confound_local or confound_cycle)
    print(f"self-check 4 (dup-key confound): gap_local={gap_local:.3f}pts "
          f"(vs |Delta_local|/10={abs(delta_local)/10:.3f}) "
          f"gap_cycle={gap_cycle:.3f}pts (vs |Delta_cycle|/10={abs(delta_cycle)/10:.3f}) "
          f"[{'PASS' if sc4_pass else 'FAIL -- CONFOUNDED'}]")
    report.append("## Self-check 4 -- duplicate-key confound\n")
    report.append("Interpretation used (the spec states the principle -- gap must be < 1/10 "
                  "of the effect it could confound -- but this arm has two effects, not "
                  "one, so the gap is checked against each of the two it could plausibly "
                  "confound):\n")
    report.append("| cell pair | dup-key rate gap (pts) | vs |1/10 x relevant effect| | confounded? |")
    report.append("|---|---:|---:|---|")
    report.append(f"| local axis (hi vs lo, worst of sparse/dense) | {gap_local:.3f} | "
                  f"{abs(delta_local)/10:.3f} | {'**YES**' if confound_local else 'no'} |")
    report.append(f"| cycle axis (dense vs sparse, worst of lo/hi) | {gap_cycle:.3f} | "
                  f"{abs(delta_cycle)/10:.3f} | {'**YES**' if confound_cycle else 'no'} |")
    report.append(f"\n**{'PASS' if sc4_pass else 'FAIL -- RUN IS CONFOUNDED, MUST NOT BE READ'}**\n")
    if not sc4_pass:
        with open(os.path.join(out_dir, "measurement_s1_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report) + "\n")
        return 1

    # ================= Self-check 5: temporal composition =================
    report.append("## Self-check 5 -- temporal composition\n\nSatisfied by construction: "
                  "segment 1 is a single contiguous session "
                  "(2026-07-29 18:31:30 -> 21:14:30), stated explicitly per the spec rather "
                  "than silently omitted. **PASS**\n")
    print("self-check 5 (temporal composition): satisfied by construction [PASS]")

    report.append("**All six self-checks pass.**\n")

    # ================= Mandatory null (Sec5) =================
    print(f"\n=== mandatory null: {NULL_RUNS} within-cycle freq_hz shuffles ===")
    by_cycle_idx: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(ref_rows):
        by_cycle_idx[r["ts"]].append(i)

    null_deltas = []
    rng = random.Random(20260731)  # fixed seed, documented, for reproducibility
    for run_i in range(NULL_RUNS):
        freqs_override: dict[str, list[float]] = {}
        for cycle, idxs in by_cycle_idx.items():
            vals = [ref_rows[i]["freq_hz"] for i in idxs]
            rng.shuffle(vals)
            freqs_override[cycle] = vals
        shuffled_nloc50 = compute_n_local(ref_rows, READING_W, freqs_override=freqs_override)
        shuffled_cell = [locality_cell_fixed(strat, nl)
                         for strat, nl in zip(stratum_of_row, shuffled_nloc50)]
        shuffled_table = build_bin_table(ref_rows, matched, stratum_of_row, shuffled_cell)
        shuffled_usable = common_support_bins(shuffled_table)
        if not shuffled_usable:
            null_deltas.append(float("nan"))
            continue
        d_local, _, _, _ = compute_deltas(shuffled_table, shuffled_usable)
        null_deltas.append(d_local)
        print(f"  null run {run_i:2d}: Delta_local={d_local:+.3f} pts "
              f"(usable_bins={len(shuffled_usable)})")

    valid_null = [d for d in null_deltas if not math.isnan(d)]
    null_mean = statistics.mean(valid_null) if valid_null else float("nan")
    null_stdev = statistics.stdev(valid_null) if len(valid_null) > 1 else float("nan")
    null_pass = (not math.isnan(null_mean)) and abs(null_mean) <= NULL_BAND_PTS
    print(f"null: mean={null_mean:+.3f} pts, stdev={null_stdev:.3f} pts, n={len(valid_null)} "
          f"(bar: within +-{NULL_BAND_PTS} pts of zero) [{'PASS' if null_pass else 'FAIL -- VOID'}]")

    report.append(f"## Mandatory null (Sec5) -- {NULL_RUNS} within-cycle freq_hz shuffles, "
                  f"seed 20260731\n")
    report.append("| run | Delta_local (pts) |")
    report.append("|---:|---:|")
    for i, d in enumerate(null_deltas):
        report.append(f"| {i} | {d:+.3f} |" if not math.isnan(d) else f"| {i} | n/a |")
    report.append(f"\n**Mean: {null_mean:+.3f} pts. Stdev: {null_stdev:.3f} pts "
                  f"(n={len(valid_null)}/{NULL_RUNS}).** Bar: mean within +-{NULL_BAND_PTS} "
                  f"pts of zero. **{'PASS' if null_pass else 'FAIL -- ARM IS VOID'}**\n")
    if not null_pass:
        report.append("The locality metric is measuring something structural about how "
                       "frequencies are distributed. Reporting the null failure, not the "
                       "arm's result, per Sec5.\n")
        with open(os.path.join(out_dir, "measurement_s1_report.md"), "w", encoding="ascii") as fh:
            fh.write("\n".join(report) + "\n")
        return 1

    # ================= Report Deltas + reading (real data) =================
    report.append("## Result -- Delta_local and Delta_cycle at W=50 (the reading width)\n")
    report.append(f"- **Delta_local** = {delta_local:+.3f} pts (sparse stratum: "
                  f"{dl_sparse:+.3f} pts, dense stratum: {dl_dense:+.3f} pts, averaged)")
    report.append(f"- **Delta_cycle** = {delta_cycle:+.3f} pts")
    report.append("")

    row_num, reading, consequence = reading_rule(delta_local, delta_cycle)
    print(f"\n>>> READING RULE: row {row_num} -- {reading}")
    print(f">>> CONSEQUENCE: {consequence}")
    report.append("## Reading rule (Sec4, quoted verbatim), applied at W=50\n")
    report.append("""
| # | condition | reading | consequence |
|---|---|---|---|
| 0 | Delta_local <= -8 or Delta_cycle <= -8 | Reversal -- crowding *helps* | Escalate. Do not interpret. Suspect the metric before the mechanism |
| 1 | Delta_local >= 8 and abs(Delta_cycle) < 3 | Penalty is frequency-local | H3/H2. Row 4 needs multi-signal handling. Expensive; strengthens row 5. S.2 is not run. Escalate before any engineering |
| 2 | Delta_cycle >= 8 and abs(Delta_local) < 3 | Penalty is cycle-global | H1/H4. Capacity or budget. S.2a runs. A cheap component is likely; strengthens row 4 |
| 3 | Delta_local >= 8 and Delta_cycle >= 8 | Two sub-mechanisms | Both proceed. Report the ratio Delta_local/Delta_cycle |
| 4 | abs(Delta_local) < 3 and abs(Delta_cycle) < 3 | Effect vanishes under joint stratification | Measurement D's effect is confounded by something neither variable captures. Escalate. Do not rationalise |
| 5 | otherwise | Partial | Ambiguous. Do not interpret further. Escalate |
""")
    report.append(f"\n**Mechanical outcome: ROW {row_num} -- {reading}.**\n\n{consequence}\n")

    # ================= W-ladder (diagnostic only, Sec4 note) =================
    print("\n=== W-ladder (diagnostic only -- shape across W, NOT the reading) ===")
    report.append("## W-ladder -- diagnostic only, NOT part of the reading\n")
    report.append("Per Sec4: 'the reading is taken at W=50 Hz -- one FT8 signal width... Do "
                  "not take the reading at whichever W looks most decisive.' Reported here "
                  "for the shape across W, which is evidence for whoever scopes the fix, not "
                  "a reading.\n")
    report.append("| W (Hz) | Delta_local (pts, median-split) | Delta_cycle (pts, median-split) | usable bins |")
    report.append("|---:|---:|---:|---:|")
    for W in W_LADDER:
        nl = n_local_by_w[W]
        # Sec3.3: "At every other W, use each stratum's own median n_local(W), ties to the
        # low side." Compute the median separately within sparse and within dense.
        sparse_vals = [v for s, v in zip(stratum_of_row, nl) if s == "sparse"]
        dense_vals = [v for s, v in zip(stratum_of_row, nl) if s == "dense"]
        med_sparse = statistics.median(sparse_vals) if sparse_vals else float("nan")
        med_dense = statistics.median(dense_vals) if dense_vals else float("nan")
        cell_w = []
        for s, v in zip(stratum_of_row, nl):
            if s == "sparse":
                cell_w.append(locality_cell_median_split(v, med_sparse))
            elif s == "dense":
                cell_w.append(locality_cell_median_split(v, med_dense))
            else:
                cell_w.append(None)
        table_w = build_bin_table(ref_rows, matched, stratum_of_row, cell_w)
        usable_w = common_support_bins(table_w)
        if usable_w:
            dloc_w, dcyc_w, _, _ = compute_deltas(table_w, usable_w)
        else:
            dloc_w = dcyc_w = float("nan")
        print(f"  W={W:4d}  Delta_local={dloc_w:+7.3f}  Delta_cycle={dcyc_w:+7.3f}  "
              f"usable_bins={len(usable_w)}")
        report.append(f"| {W} | {dloc_w:+.3f} | {dcyc_w:+.3f} | {len(usable_w)} |")

    # ================= Per-bin table at W=50 (the reading width), for the record =========
    report.append("\n## Per-bin recall at W=50 (all four cells, usable bins only)\n")
    report.append("| SNR bin (dB) | sparse_lo n/m/recall | sparse_hi n/m/recall | "
                  "dense_lo n/m/recall | dense_hi n/m/recall |")
    report.append("|---:|---|---|---|---|")
    for b in usable_bins:
        c = table[b]
        def fmt(cell_counts):
            tot, m = cell_counts
            r = m / tot if tot else float("nan")
            return f"{tot}/{m}/{r*100:.1f}%"
        report.append(f"| [{b:.0f},{b+BIN_WIDTH:.0f}) | {fmt(c['sparse_lo'])} | "
                      f"{fmt(c['sparse_hi'])} | {fmt(c['dense_lo'])} | {fmt(c['dense_hi'])} |")

    report_path = os.path.join(out_dir, "measurement_s1_report.md")
    with open(report_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(report) + "\n")
    print(f"\nWrote report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
