"""G2A-REMEASURE-A Part C (DESCRIPTIVE -- NOT GATED). Spec Sec.6.

hashTableRejectCount on both legs; unresolved-hash decode SNR-stratum
distribution on X1/X2's PINNED L1 edges [-15,-10,-5,2] (never re-derived);
total decode counts per leg -- G2(a)'s own commit message states the fix
CANNOT change the decode count (a hashed callsign's resolution failure is
already discarded without affecting whether a decode is produced), so any
observed difference here is a finding that CONTRADICTS the source and must
be escalated, not silently absorbed.

No stratification by frequency separation to a neighbouring decode, in any
form, under any name (spec Sec.6 prohibition, retired spectral-locality
metric). Nothing here does that.
"""
from __future__ import annotations

L1_SNR_EDGES = [-15, -10, -5, 2]


def _snr_stratum(snr, edges):
    for i, e in enumerate(edges):
        if snr <= e:
            return i
    return len(edges)


def _stratum_label(i, edges):
    if i == 0:
        return "(-inf, %d]" % edges[0]
    if i == len(edges):
        return "(%d, +inf)" % edges[-1]
    return "(%d, %d]" % (edges[i - 1], edges[i])


def run_part_c(l1_rows, l2_rows, l1_dump, l2_dump, log) -> dict:
    reject_l1 = l1_dump.get("final_hash_table_reject_count")
    reject_l2 = l2_dump.get("final_hash_table_reject_count")
    log("Part C: hashTableRejectCount -- L1(pre)=%s L2(post)=%s" % (reject_l1, reject_l2))

    n_l1 = len(l1_rows)
    n_l2 = len(l2_rows)
    decode_count_diff = n_l2 - n_l1
    log("Part C: total decode count -- L1=%d L2=%d diff=%+d (%.3f%%)"
        % (n_l1, n_l2, decode_count_diff, 100.0 * decode_count_diff / n_l1 if n_l1 else float("nan")))
    if decode_count_diff != 0:
        log("Part C: !! decode counts DIFFER between L1 and L2. G2(a)'s own commit message "
            "states the hash-table fix CANNOT change the decode count. This CONTRADICTS the "
            "source and is escalated here rather than absorbed as noise.")

    strata_out = {}
    for label, rows in (("L1(pre)", l1_rows), ("L2(post)", l2_rows)):
        hash_rows = [r for r in rows if r["has_hash"]]
        counts = [0] * (len(L1_SNR_EDGES) + 1)
        for r in hash_rows:
            counts[_snr_stratum(r["snr"], L1_SNR_EDGES)] += 1
        total = len(hash_rows)
        dist = []
        for i, c in enumerate(counts):
            share = (c / total) if total else 0.0
            dist.append({"stratum": _stratum_label(i, L1_SNR_EDGES), "n": c, "share": share})
        strata_out[label] = {"n_hash_decodes": total, "distribution": dist}
        log("Part C: [%s] unresolved-hash decodes = %d, SNR-stratum distribution:" % (label, total))
        for d in dist:
            log("Part C:   %-14s n=%-6d share=%.1f%%" % (d["stratum"], d["n"], d["share"] * 100))

    return {
        "hash_table_reject_count": {"l1_pre": reject_l1, "l2_post": reject_l2},
        "total_decodes": {"l1_pre": n_l1, "l2_post": n_l2, "diff": decode_count_diff},
        "snr_stratum_distribution": strata_out,
    }
