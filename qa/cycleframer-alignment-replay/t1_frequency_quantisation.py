#!/usr/bin/env python3
"""T1 -- does candidate-grid frequency quantisation cost us decodes?

Spec: qa/cycleframer-alignment-replay/2026-08-08-2030-architect-to-qa-spec-t1-frequency-quantisation.md
Pre-registered gate per HK-021; rows mutually exclusive, strict order, boundary
values fall to the inconclusive row (see t1_row() below, copied verbatim from
the spec's own pseudocode).

Population: reference = intersection of the two WSJT-X instances (a decode
BOTH made), on the (ts, message) key -- the same conservative definition the
2026-08-08 1942 report uses. Matched = reference decode for which OpenWSFZ
8080 produced the same (ts, message). Missed = reference decode with no such
OpenWSFZ row.

Trap (spec S2): r is computed from the REFERENCE's reported frequency for
BOTH matched and missed groups, without exception. OpenWSFZ's own frequency
is on-grid by construction and must never enter the r computation -- it is
used only for the mean_r_ours instrument check (S4 gate).

No src/ change. No capture. Pure re-analysis of ALL.TXT already on disk.
"""
import io
import statistics
import sys

STEP = 3.125  # Hz -- K_FREQ_OSR=2 on 6.25 Hz tone spacing; NOT a tunable (spec S3.3)

# 20m clean window, per the 2026-08-08 1942 report S1 table.
WINDOW_20M = ("260808_004000", "260808_111500")
LEG_20M = {
    "owsfz": "artefacts/20260808_live_run_0016-8080/owsfz/ALL.TXT",
    "wsjtx_a": "artefacts/20260808_live_run_0016-8080/wsjt-x/ALL.TXT",   # FT991A
    "wsjtx_b": "artefacts/20260808_live_run_0016-8081/wsjt-x/ALL.TXT",  # FT991A-Copy
}

# 17m -- secondary/replication only. VOID under its own ROW 0b (board, 08-08
# 14:15Z); spec S3.1: "no row may be cited from it."
WINDOW_17M = ("260808_120000", "260808_193900")
LEG_17M = {
    "owsfz": "artefacts/20260808_live_run_1154-8080-17m/owsfz/ALL.TXT",
    "wsjtx_a": "artefacts/20260808_live_run_1154-8080-17m/wsjt-x/ALL.TXT",
    "wsjtx_b": "artefacts/20260808_live_run_1154-8081-17m/wsjt-x/ALL.TXT",
}


def residual(f_hz):
    m = f_hz % STEP
    return min(m, STEP - m)


def load(path, lo, hi):
    """(ts, message) -> (snr, freq_hz) for Rx FT8 lines in the window.

    Field indices are 0-based on whitespace split, per the spec S0.3 correction:
    [0] ts  [4] SNR  [5] DT  [6] freq Hz  [7:] message.
    """
    out = {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            ts = f[0]
            if not (lo <= ts <= hi):
                continue
            try:
                snr, freq_hz = int(f[4]), int(f[6])
            except ValueError:
                continue
            out[(ts, " ".join(f[7:]))] = (snr, freq_hz)
    return out


def has_unresolved_hash(msg):
    return "<...>" in msg


def quintile_edges(values):
    """5 quantile cut points over a sorted list, boundaries via nearest-rank."""
    s = sorted(values)
    n = len(s)
    edges = [s[int(n * k / 5)] for k in range(1, 5)]
    return edges


def assign_quintile(v, edges):
    for i, e in enumerate(edges):
        if v < e:
            return i
    return len(edges)


def recovery_by_quintile(rows, key_fn, matched_flags):
    """rows: list of dicts with a numeric field extracted by key_fn.
    matched_flags: parallel list of bool (True if OpenWSFZ matched this row).
    Returns (edges, [(n, matched, recovery_pct), ...]) for 5 quintiles.
    """
    values = [key_fn(r) for r in rows]
    edges = quintile_edges(values)
    buckets = [[0, 0] for _ in range(5)]  # [n, matched]
    for r, m in zip(rows, matched_flags):
        q = assign_quintile(key_fn(r), edges)
        buckets[q][0] += 1
        buckets[q][1] += 1 if m else 0
    out = [(n, mm, 100.0 * mm / n if n else 0.0) for n, mm in buckets]
    return edges, out


def t1_row(G, n_min_quintile, mean_r_ours, mean_r_ref):
    """Verbatim from the spec S4."""
    if n_min_quintile < 500:
        return "ROW 0"   # instrument failure, NOT a null
    if mean_r_ours >= 0.45:
        return "ROW 0"   # our grid model is wrong
    if mean_r_ref < 0.50:
        return "ROW 0"   # reference is on our grid too: no contrast
    if G >= 4.0:
        return "ROW 1"
    if G <= 1.0:
        return "ROW 2"
    return "ROW 3"


def analyse(leg_name, paths, window, primary):
    lo, hi = window
    print("=" * 78)
    print("%s  window %s..%s  (%s)" % (leg_name, lo, hi, "PRIMARY, citable" if primary else "SECONDARY, replication only -- NO ROW may be cited"))
    print("=" * 78)

    owsfz = load(paths["owsfz"], lo, hi)
    wa = load(paths["wsjtx_a"], lo, hi)
    wb = load(paths["wsjtx_b"], lo, hi)

    ref_keys = set(wa) & set(wb)
    print("\nreference population (WSJT-X A ^ WSJT-X B): %d" % len(ref_keys))

    # --- S3.2 pre-registered exclusions, applied symmetrically ---
    excl_hash = 0
    excl_band = 0
    kept = []
    for k in ref_keys:
        ts, msg = k
        if has_unresolved_hash(msg):
            excl_hash += 1
            continue
        snr, freq_hz = wa[k]  # reference frequency: WSJT-X A, for BOTH groups without exception
        if not (200 <= freq_hz <= 3000):
            excl_band += 1
            continue
        kept.append(k)
    print("excluded: <...> unresolved-hash = %d ; out-of-band (200-3000 Hz) = %d" % (excl_hash, excl_band))
    print("population after exclusions: %d" % len(kept))

    rows = []
    matched_flags = []
    for k in kept:
        ts, msg = k
        snr, freq_hz = wa[k]
        r = residual(freq_hz)
        is_matched = k in owsfz
        rows.append({"ts": ts, "snr": snr, "freq_hz": freq_hz, "r": r})
        matched_flags.append(is_matched)

    n_matched = sum(matched_flags)
    print("matched by OpenWSFZ 8080: %d / %d (%.1f%%)" % (n_matched, len(kept), 100.0 * n_matched / max(len(kept), 1)))

    # --- S4 instrument checks ---
    mean_r_ref = statistics.mean(r["r"] for r in rows)
    # mean_r_ours: residual of OpenWSFZ's OWN reported frequency, matched subset only,
    # same window, same exclusions -- the instrument check from spec S0.3, recomputed
    # on this population rather than reused from the whole corpus.
    ours_freqs = []
    for k in kept:
        if k in owsfz:
            _, freq_hz_ours = owsfz[k]
            ours_freqs.append(residual(freq_hz_ours))
    mean_r_ours = statistics.mean(ours_freqs) if ours_freqs else float("nan")

    print("\ninstrument check:")
    print("   mean_r (reference, this population) = %.4f" % mean_r_ref)
    print("   mean_r (OpenWSFZ, matched subset)    = %.4f" % mean_r_ours)

    # --- S3.3 primary metric: quintiles of reference r ---
    edges, buckets = recovery_by_quintile(rows, lambda r: r["r"], matched_flags)
    print("\nrecovery by r-quintile (edges=%s):" % ["%.4f" % e for e in edges])
    for i, (n, m, pct) in enumerate(buckets):
        print("   Q%d  n=%6d  matched=%6d  recovery=%5.1f%%" % (i + 1, n, m, pct))
    G = buckets[0][2] - buckets[4][2]
    n_min = min(b[0] for b in buckets)
    print("   G = recovery(Q1) - recovery(Q5) = %.2f pp" % G)
    print("   min quintile n = %d" % n_min)

    row = t1_row(G, n_min, mean_r_ours, mean_r_ref)
    print("\n   >>> %s <<<" % row)
    if not primary:
        print("   (SECONDARY leg -- reported as replication signal only, per spec S3.1; do not cite this row.)")

    # --- S3.4 mandatory control: recompute G within SNR quintiles ---
    print("\ncontrol: G recomputed within reference-SNR quintiles (SNR always from reference):")
    snr_edges = quintile_edges([r["snr"] for r in rows])
    print("   SNR quintile edges: %s" % snr_edges)
    snr_buckets = [[] for _ in range(5)]
    snr_matched = [[] for _ in range(5)]
    for r, m in zip(rows, matched_flags):
        q = assign_quintile(r["snr"], snr_edges)
        snr_buckets[q].append(r)
        snr_matched[q].append(m)
    for i in range(5):
        sub_rows = snr_buckets[i]
        sub_matched = snr_matched[i]
        if len(sub_rows) < 10:
            print("   SNR-Q%d  n=%d  (too few to sub-stratify)" % (i + 1, len(sub_rows)))
            continue
        sub_edges, sub_out = recovery_by_quintile(sub_rows, lambda r: r["r"], sub_matched)
        g_sub = sub_out[0][2] - sub_out[4][2]
        print("   SNR-Q%d  n=%6d  r-quintile recoveries=%s  G_sub=%.2f pp"
              % (i + 1, len(sub_rows), ["%.1f" % o[2] for o in sub_out], g_sub))

    return {"leg": leg_name, "primary": primary, "G": G, "row": row,
            "n_min_quintile": n_min, "mean_r_ours": mean_r_ours, "mean_r_ref": mean_r_ref,
            "n_population": len(kept), "n_matched": n_matched,
            "excl_hash": excl_hash, "excl_band": excl_band}


def main():
    results = []
    results.append(analyse("20m (PRIMARY)", LEG_20M, WINDOW_20M, primary=True))
    print()
    results.append(analyse("17m (secondary, VOID leg -- replication only)", LEG_17M, WINDOW_17M, primary=False))

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    for r in results:
        print("%-45s G=%6.2f pp  row=%-6s  n_pop=%6d  min_q=%5d  mean_r_ours=%.3f  mean_r_ref=%.3f"
              % (r["leg"], r["G"], r["row"], r["n_population"], r["n_min_quintile"], r["mean_r_ours"], r["mean_r_ref"]))


if __name__ == "__main__":
    main()
