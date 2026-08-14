#!/usr/bin/env python3
"""T2 -- the shape of the offset-vs-recovery curve, on the native 13-rung ladder.

Spec: qa/cycleframer-alignment-replay/2026-08-08-2102-architect-to-qa-spec-t2-offset-curve-shape.md
Follows T1 (ROW 3, G=3.16 pp) and does NOT reopen it (spec S1.1) -- 1.1/1.2/1.3/1.4
are hard prohibitions, reproduced at the call sites below.

Reuses T1's load()/residual()/has_unresolved_hash()/quintile_edges()/assign_quintile()
verbatim (import, not copy) so T2's population is provably the same one T1 read.

20m leg only (spec S1.3 -- 17m is VOID under its own ROW 0b and out of scope entirely).
No src/ change. No capture. No rebuild. Pure re-analysis of ALL.TXT already on disk.
NFR-021: no message text or callsign is read into memory beyond the (ts, message) key
already handled by t1's load(), and none is printed -- every figure below is a count,
a rate, or a frequency statistic.
"""
import glob
import io
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_frequency_quantisation import (  # noqa: E402
    STEP, WINDOW_20M, LEG_20M, residual, load, has_unresolved_hash,
    quintile_edges, assign_quintile,
)

# The 13 canonical ladder rungs, spec S0.1.
RUNGS = [round(i * 0.125, 3) for i in range(13)]

# Fixed rung groups, spec S3.2 -- declared before any per-rung data is seen,
# identical across every stratum (the S0.3 fix for T1's per-stratum re-derivation).
CEN = {0.000, 0.125, 0.250}   # bin centre
INT = {0.875, 1.000, 1.125}   # interior -- predicted worst case, spec S0.2
MID = {1.375, 1.500}          # near midpoint -- "two-candidate" region


def rung_of(r):
    """Snap a residual to its canonical 1/8 Hz rung, guarding float noise."""
    return round(round(r / 0.125) * 0.125, 3)


def half_of(ts):
    """Cycle-parity split, spec S3.4. ts format YYMMDD_HHMMSS."""
    hh, mm, ss = int(ts[7:9]), int(ts[9:11]), int(ts[11:13])
    secs = hh * 3600 + mm * 60 + ss
    return (secs // 15) % 2


def build_population():
    """Identical to T1's analyse() population logic, 20m leg only (spec S2)."""
    lo, hi = WINDOW_20M
    owsfz = load(LEG_20M["owsfz"], lo, hi)
    wa = load(LEG_20M["wsjtx_a"], lo, hi)
    wb = load(LEG_20M["wsjtx_b"], lo, hi)
    ref_keys = set(wa) & set(wb)

    excl_hash = 0
    excl_band = 0
    kept = []
    for k in ref_keys:
        ts, msg = k
        if has_unresolved_hash(msg):
            excl_hash += 1
            continue
        snr, freq_hz = wa[k]  # reference frequency, both groups, without exception
        if not (200 <= freq_hz <= 3000):
            excl_band += 1
            continue
        kept.append(k)

    rows = []
    for k in kept:
        ts, msg = k
        snr, freq_hz = wa[k]
        r = residual(freq_hz)
        rows.append({
            "ts": ts, "snr": snr, "freq_hz": freq_hz,
            "r": r, "rung": rung_of(r),
            "matched": k in owsfz,
            "half": half_of(ts),
        })

    mean_r_ours = mean_r_ours_for(kept, owsfz)

    return {
        "rows": rows, "owsfz": owsfz, "kept": kept,
        "n_ref": len(ref_keys), "excl_hash": excl_hash, "excl_band": excl_band,
        "mean_r_ours": mean_r_ours,
    }


def mean_r_ours_for(kept, owsfz):
    """Instrument check, spec S4/ROW 0c -- OpenWSFZ's own residual, matched subset,
    this population (same construction T1 used, recomputed here rather than reused
    since T2's population, while intended identical, is independently rebuilt)."""
    freqs = []
    for k in kept:
        if k in owsfz:
            _, freq_hz_ours = owsfz[k]
            freqs.append(residual(freq_hz_ours))
    return statistics.mean(freqs) if freqs else float("nan")


def recovery_group(rows, rung_set):
    sub = [r for r in rows if r["rung"] in rung_set]
    n = len(sub)
    m = sum(1 for r in sub if r["matched"])
    pct = 100.0 * m / n if n else float("nan")
    return n, m, pct


def curve_13(rows):
    out = []
    for rung in RUNGS:
        n, m, pct = recovery_group(rows, {rung})
        out.append((rung, n, m, pct))
    return out


def contrasts(rows):
    n_cen, m_cen, p_cen = recovery_group(rows, CEN)
    n_int, m_int, p_int = recovery_group(rows, INT)
    n_mid, m_mid, p_mid = recovery_group(rows, MID)
    d_int = p_cen - p_int
    u = p_mid - p_int
    groups = {
        "CEN": (n_cen, m_cen, p_cen),
        "INT": (n_int, m_int, p_int),
        "MID": (n_mid, m_mid, p_mid),
    }
    return d_int, u, groups


def t2_row(n_min_group, n_distinct_rungs, mean_r_ours,
           d_int, d_int_half_0, d_int_half_1,
           u, u_half_0, u_half_1):
    """Verbatim from spec S4."""
    # ---- ROW 0: instrument failure, NOT a null. Evaluated first, in this order. ----
    if n_min_group < 2000:
        return "ROW 0a"      # a rung group is too small to read
    if n_distinct_rungs != 13:
        return "ROW 0b"      # the integer-Hz ladder premise (S0.1) is false
    if not (0.20 <= mean_r_ours <= 0.30):
        return "ROW 0c"      # our on-grid model is wrong
    if not (-2.0 <= d_int <= 15.0):
        return "ROW 0d"      # outside a bound already believed; instrument failure
    if (d_int_half_0 > 0) != (d_int_half_1 > 0):
        return "ROW 0e"      # shape unstable across split-half: too noisy to read shape at all

    # ---- substantive rows, mutually exclusive, strict order ----
    if u >= 1.5 and u_half_0 > 0 and u_half_1 > 0:
        return "ROW 1"
    if u <= 0.5:
        return "ROW 2"
    return "ROW 3"


def scan_decimal_frequency():
    """Spec S5.3 -- mechanically scan every gathered WSJT-X ALL.TXT in artefacts/
    for a frequency field ([6]) containing a decimal point. Excludes files under
    'ours_on_*' directories, which are OpenWSFZ's own output on WSJT-X-sourced
    audio, not a WSJT-X-authored ALL.TXT."""
    paths = []
    for p in glob.glob("artefacts/**/ALL.TXT", recursive=True):
        pl = p.replace("\\", "/").lower()
        if "wsjt" in pl and "ours_on" not in pl:
            paths.append(p)
    scanned = 0
    decimal_count = 0
    for p in sorted(paths):
        with io.open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                f = line.split()
                if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                    continue
                scanned += 1
                if "." in f[6]:
                    decimal_count += 1
    return paths, scanned, decimal_count


def print_group_line(label, n, m, pct):
    print("   %-4s n=%6d  matched=%6d  recovery=%5.1f%%" % (label, n, m, pct))


def main():
    print("=" * 78)
    print("T2 -- offset-vs-recovery curve shape, 20m leg, window %s..%s" % WINDOW_20M)
    print("=" * 78)

    pop = build_population()
    rows = pop["rows"]
    print("\nreference population (WSJT-X A ^ WSJT-X B): %d" % pop["n_ref"])
    print("excluded: <...> unresolved-hash = %d ; out-of-band (200-3000 Hz) = %d"
          % (pop["excl_hash"], pop["excl_band"]))
    print("population after exclusions: %d  (spec S2 expects 67243)" % len(pop["kept"]))
    if len(pop["kept"]) != 67243:
        print("   *** MISMATCH vs T1's population -- spec S2 says stop and report. ***")

    n_matched_total = sum(1 for r in rows if r["matched"])
    print("matched by OpenWSFZ 8080: %d / %d (%.1f%%)"
          % (n_matched_total, len(rows), 100.0 * n_matched_total / max(len(rows), 1)))

    print("\ninstrument check: mean_r_ours (OpenWSFZ, matched subset) = %.4f  (ROW 0c bar: 0.20-0.30)"
          % pop["mean_r_ours"])

    # --- 3.1 the full 13-rung curve ---
    print("\n" + "-" * 78)
    print("S3.1 -- full 13-rung curve (no binning, no quantiles)")
    print("-" * 78)
    curve = curve_13(rows)
    for rung, n, m, pct in curve:
        tag = ""
        if rung in CEN:
            tag = " CEN"
        elif rung in INT:
            tag = " INT"
        elif rung in MID:
            tag = " MID"
        print("   r=%.3f  n=%6d  matched=%6d  recovery=%5.1f%%%s" % (rung, n, m, pct, tag))
    n_distinct_rungs = sum(1 for _, n, _, _ in curve if n > 0)
    print("   n_distinct_rungs with n>0 = %d" % n_distinct_rungs)

    # --- 3.2 / 3.3 fixed groups and contrasts ---
    print("\n" + "-" * 78)
    print("S3.2/3.3 -- fixed rung groups and contrasts")
    print("-" * 78)
    d_int, u, groups = contrasts(rows)
    for label in ("CEN", "INT", "MID"):
        n, m, pct = groups[label]
        print_group_line(label, n, m, pct)
    print("   D_int = recovery(CEN) - recovery(INT) = %.2f pp" % d_int)
    print("   U     = recovery(MID) - recovery(INT) = %.2f pp" % u)
    n_min_group = min(groups[g][0] for g in ("CEN", "INT", "MID"))
    print("   min group n = %d" % n_min_group)

    # --- 3.4 split-half by cycle parity ---
    print("\n" + "-" * 78)
    print("S3.4 -- split-half replication, by cycle parity (not by time)")
    print("-" * 78)
    half_results = {}
    for h in (0, 1):
        sub_rows = [r for r in rows if r["half"] == h]
        d_int_h, u_h, groups_h = contrasts(sub_rows)
        half_results[h] = (d_int_h, u_h, groups_h, len(sub_rows))
        print("   half=%d  n=%6d  D_int=%.2f pp  U=%.2f pp" % (h, len(sub_rows), d_int_h, u_h))
        for label in ("CEN", "INT", "MID"):
            n, m, pct = groups_h[label]
            print_group_line("  h%d.%s" % (h, label), n, m, pct)

    d_int_half_0, u_half_0 = half_results[0][0], half_results[0][1]
    d_int_half_1, u_half_1 = half_results[1][0], half_results[1][1]

    # --- gate ---
    print("\n" + "-" * 78)
    print("S4 -- pre-registered gate, strict order")
    print("-" * 78)
    row = t2_row(n_min_group, n_distinct_rungs, pop["mean_r_ours"],
                 d_int, d_int_half_0, d_int_half_1,
                 u, u_half_0, u_half_1)
    print("   n_min_group      = %d   (bar >= 2000)" % n_min_group)
    print("   n_distinct_rungs = %d   (bar == 13)" % n_distinct_rungs)
    print("   mean_r_ours      = %.4f   (bar 0.20-0.30)" % pop["mean_r_ours"])
    print("   d_int            = %.2f pp   (bar -2.0..15.0)" % d_int)
    print("   d_int half0/half1 sign match = %s  (%.2f / %.2f)"
          % ((d_int_half_0 > 0) == (d_int_half_1 > 0), d_int_half_0, d_int_half_1))
    print("   u                = %.2f pp   (ROW1 bar >= 1.5 both halves positive; ROW2 bar <= 0.5)" % u)
    print("   u half0/half1    = %.2f / %.2f  (positive: %s / %s)"
          % (u_half_0, u_half_1, u_half_0 > 0, u_half_1 > 0))
    print("\n   >>> %s <<<" % row)

    # --- 5.1 argmin diagnostic ---
    print("\n" + "-" * 78)
    print("S5.1 -- argmin diagnostic (n>=2000 only), NOT gated")
    print("-" * 78)
    eligible = [(rung, n, m, pct) for rung, n, m, pct in curve if n >= 2000]
    argmin = min(eligible, key=lambda t: t[3])
    print("   argmin rung = %.3f  (n=%d, recovery=%.1f%%)  -- prediction 6: falls inside INT {0.875,1.000,1.125}"
          % (argmin[0], argmin[1], argmin[3]))
    print("   argmin in INT: %s" % (argmin[0] in INT))

    # --- 5.2 SNR strata, fixed rung groups ---
    print("\n" + "-" * 78)
    print("S5.2 -- SNR quintiles, fixed rung groups (the S0.3 fix)")
    print("-" * 78)
    snr_edges = quintile_edges([r["snr"] for r in rows])
    print("   SNR quintile edges: %s" % snr_edges)
    snr_buckets = [[] for _ in range(5)]
    for r in rows:
        q = assign_quintile(r["snr"], snr_edges)
        snr_buckets[q].append(r)
    mean_r_per_quintile = []
    for i in range(5):
        sub = snr_buckets[i]
        if len(sub) < 10:
            print("   SNR-Q%d  n=%d  (too few to sub-stratify)" % (i + 1, len(sub)))
            mean_r_per_quintile.append(float("nan"))
            continue
        d_int_i, u_i, groups_i = contrasts(sub)
        mean_r_i = statistics.mean(r["r"] for r in sub)
        mean_r_per_quintile.append(mean_r_i)
        print("   SNR-Q%d  n=%6d  mean_r=%.4f  D_int=%6.2f pp  U=%6.2f pp  (CEN n=%d, INT n=%d, MID n=%d)"
              % (i + 1, len(sub), mean_r_i, d_int_i, u_i,
                 groups_i["CEN"][0], groups_i["INT"][0], groups_i["MID"][0]))
    valid_means = [m for m in mean_r_per_quintile if m == m]  # drop NaN
    spread = (max(valid_means) - min(valid_means)) if valid_means else float("nan")
    print("   mean_r spread across SNR quintiles (max-min) = %.4f Hz  (bar < 0.02 Hz => independent of SNR)"
          % spread)

    # --- 5.3 corpus-wide instrument confirmation ---
    print("\n" + "-" * 78)
    print("S5.3 -- corpus-wide scan for a finer (decimal-Hz) frequency instrument")
    print("-" * 78)
    paths, scanned, decimal_count = scan_decimal_frequency()
    print("   WSJT-X ALL.TXT files scanned: %d" % len(paths))
    print("   Rx FT8 lines scanned: %d" % scanned)
    print("   lines with a decimal point in the frequency field: %d" % decimal_count)

    # --- summary for the report ---
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print("row=%s  D_int=%.2f pp  U=%.2f pp  n_pop=%d  n_distinct_rungs=%d  mean_r_ours=%.4f"
          % (row, d_int, u, len(pop["kept"]), n_distinct_rungs, pop["mean_r_ours"]))
    print("half0: D_int=%.2f  U=%.2f  n=%d | half1: D_int=%.2f  U=%.2f  n=%d"
          % (d_int_half_0, u_half_0, half_results[0][3], d_int_half_1, u_half_1, half_results[1][3]))
    print("argmin rung=%.3f in INT=%s | mean_r SNR-quintile spread=%.4f | decimal-freq lines corpus-wide=%d/%d"
          % (argmin[0], argmin[0] in INT, spread, decimal_count, scanned))


if __name__ == "__main__":
    main()
