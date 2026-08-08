#!/usr/bin/env python3
"""H1 -- how much do `<...>` hash tokens distort the 55.5% recovery figure and
the ~4% false-positive rate?

Spec: qa/cycleframer-alignment-replay/2026-08-08-2121-architect-to-qa-spec-h1-hash-token-contamination.md

NFR-021: no message text and no callsign may appear in any printed output --
counts and rates only. The `known` callsign set is held in memory for the
plausibility proxy and is never printed or written to disk.

Population: 20m leg only, window identical to T1 and the 1942 report S2.1.
Reference = intersection of the two WSJT-X instances on (ts, message).
"Ours" = OpenWSFZ 8080, matching the 1942 report's primary recovery figure.

Trap (spec S1.1): the four-decoder-interim-comparison harness's source paths
are dead (moved to _archived_...). Read from artefacts/ instead, keeping the
DIAL_PREFIX filter as a defensive belt-and-braces measure even though this
leg's artefact snapshots were pulled before the 17m leg began.

No src/ change. No capture. Pure re-analysis of ALL.TXT already on disk.
"""
import io
import re
import sys

WINDOW_20M = ("260808_004000", "260808_111500")
DIAL_PREFIX = "14.074"

SOURCES = {
    "owsfz_a": "artefacts/20260808_live_run_0016-8080/owsfz/ALL.TXT",    # OpenWSFZ 8080 -- "ours"
    "owsfz_b": "artefacts/20260808_live_run_0016-8081/owsfz/ALL.TXT",    # OpenWSFZ 8081 -- FP corroboration only
    "wsjtx_a": "artefacts/20260808_live_run_0016-8080/wsjt-x/ALL.TXT",   # WSJT-X FT991A
    "wsjtx_b": "artefacts/20260808_live_run_0016-8081/wsjt-x/ALL.TXT",   # WSJT-X FT991A-Copy
}

# Same shape as the interim-comparison harness's proxy -- deliberately permissive.
CALLSIGN_RE = re.compile(r"^[A-Z0-9]{1,3}[0-9][A-Z]{1,3}(/[A-Z0-9]{1,2})?$")


def load(path, lo, hi, dial_prefix=DIAL_PREFIX):
    """(ts, message) -> (snr, freq_hz) for Rx FT8 lines on the dial freq in window."""
    out = {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if not f[1].startswith(dial_prefix):
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


def has_hash(msg):
    return "<...>" in msg


def wildcard_match(msg_a, msg_b):
    """Token-wise identical, treating '<...>' on EITHER side as a wildcard
    matching exactly one token in the same position. Token counts must match."""
    ta, tb = msg_a.split(), msg_b.split()
    if len(ta) != len(tb):
        return False
    for x, y in zip(ta, tb):
        if x == y:
            continue
        if x == "<...>" or y == "<...>":
            continue
        return False
    return True


def callsign_tokens(msg):
    return [t.strip("<>") for t in msg.split() if CALLSIGN_RE.match(t.strip("<>"))]


def known_callsigns(keys):
    """keys: iterable of (ts, message). Held in memory only -- never printed."""
    found = set()
    for _, msg in keys:
        for tok in msg.split():
            tok = tok.strip("<>")
            if CALLSIGN_RE.match(tok):
                found.add(tok)
    return found


def plausibility_counts(keys, known):
    """Returns (raw_n, total_after_cs_filter, ok, silently_excluded).

    Mirrors 2026-08-08-four-decoder-interim-comparison.py's plausibility():
    a message whose only callsign-shaped tokens are all filtered out (e.g. by
    strip("<>") turning '<...>' into '...', which fails CALLSIGN_RE) yields an
    empty cs list and is silently dropped from the denominator entirely
    (line 83's `if not cs: continue`). We surface that count explicitly here.
    """
    raw_n = 0
    total = 0
    ok = 0
    for _, msg in keys:
        raw_n += 1
        cs = callsign_tokens(msg)
        if not cs:
            continue
        total += 1
        if all(c in known for c in cs):
            ok += 1
    return raw_n, total, ok, raw_n - total


# --- ROW 0 + gates, verbatim from spec S4 -----------------------------------

def h1_row0(r_base, m, ours_hash_share, n_ours_hash, n_ref_pop):
    if abs(r_base - 55.5) > 0.5:
        return "ROW 0a"
    if not (0.03 <= ours_hash_share <= 0.08):
        return "ROW 0b"
    if m < -0.1:
        return "ROW 0c"
    if m > 100.0 * n_ours_hash / n_ref_pop:
        return "ROW 0d"
    return None


def h1_gate_a(m):
    if m >= 2.0:
        return "A-ROW 1"
    if m <= 0.5:
        return "A-ROW 2"
    return "A-ROW 3"


def h1_gate_b(d_f):
    if d_f >= 1.0:
        return "B-ROW 1"
    if d_f <= 0.25:
        return "B-ROW 2"
    return "B-ROW 3"


def main():
    lo, hi = WINDOW_20M
    print("=" * 78)
    print("H1 -- hash-token contamination, 20m leg, window %s..%s" % (lo, hi))
    print("=" * 78)

    owsfz_a = load(SOURCES["owsfz_a"], lo, hi)
    owsfz_b = load(SOURCES["owsfz_b"], lo, hi)
    wsjtx_a = load(SOURCES["wsjtx_a"], lo, hi)
    wsjtx_b = load(SOURCES["wsjtx_b"], lo, hi)

    print("\nraw counts (window+dial filtered): owsfz_a=%d owsfz_b=%d wsjtx_a=%d wsjtx_b=%d"
          % (len(owsfz_a), len(owsfz_b), len(wsjtx_a), len(wsjtx_b)))

    ref_keys = set(wsjtx_a) & set(wsjtx_b)
    n_ref_pop = len(ref_keys)
    print("reference population (wsjtx_a ^ wsjtx_b): %d" % n_ref_pop)

    # --- S3.1 R_base ---------------------------------------------------
    exact_matched = ref_keys & set(owsfz_a)
    R_base = 100.0 * len(exact_matched) / n_ref_pop
    print("\n--- 3.1 R_base (exact match, no exclusions) ---")
    print("R_base = %d / %d = %.2f%%  (must reproduce 55.5%% +/- 0.5)" % (len(exact_matched), n_ref_pop, R_base))

    # --- instrument facts: our <...> share, reference <...> share ------
    n_ours_total = len(owsfz_a)
    n_ours_hash = sum(1 for k in owsfz_a if has_hash(k[1]))
    ours_hash_share = n_ours_hash / n_ours_total if n_ours_total else float("nan")
    n_ref_hash = sum(1 for k in ref_keys if has_hash(k[1]))
    ref_hash_share = n_ref_hash / n_ref_pop if n_ref_pop else float("nan")
    print("\nours (8080) <...> share (whole window, not just ref pop): %d / %d = %.4f (predicted ~0.055)"
          % (n_ours_hash, n_ours_total, ours_hash_share))
    print("reference <...> share (within ref population): %d / %d = %.4f (predicted ~0.017)"
          % (n_ref_hash, n_ref_pop, ref_hash_share))

    # --- S3.2 R_excl -----------------------------------------------------
    pop_excl = {k for k in ref_keys if not has_hash(k[1])}
    matched_excl = {k for k in pop_excl if k in owsfz_a and not has_hash(k[1])}
    R_excl = 100.0 * len(matched_excl) / len(pop_excl) if pop_excl else float("nan")
    print("\n--- 3.2 R_excl (symmetric exclusion) ---")
    print("population after dropping ref rows with <...>: %d (dropped %d)" % (len(pop_excl), n_ref_pop - len(pop_excl)))
    print("R_excl = %d / %d = %.2f%%" % (len(matched_excl), len(pop_excl), R_excl))

    # --- S3.3 R_wild + mandatory ambiguity accounting ---------------------
    owsfz_by_ts = {}
    for (ts, msg) in owsfz_a:
        owsfz_by_ts.setdefault(ts, []).append(msg)

    remaining = ref_keys - exact_matched
    gained = {}  # ref_key -> list of matching owsfz messages
    for k in remaining:
        ts, ref_msg = k
        candidates = [m for m in owsfz_by_ts.get(ts, []) if wildcard_match(ref_msg, m)]
        if candidates:
            gained[k] = candidates

    n_wild_gained = len(gained)
    R_wild = 100.0 * (len(exact_matched) + n_wild_gained) / n_ref_pop
    M = R_wild - R_base

    # ambiguity: gained ref row is ambiguous if (a) it had >=2 candidate owsfz
    # rows, or (b) any of its candidate owsfz rows also matched >=2 distinct
    # gained ref rows.
    owsfz_match_count = {}
    for k, cands in gained.items():
        for c in cands:
            owsfz_match_count.setdefault((k[0], c), []).append(k)  # key by (ts, msg) since msg alone isn't unique across ts
    ambiguous_refs = set()
    for k, cands in gained.items():
        if len(cands) >= 2:
            ambiguous_refs.add(k)
            continue
        c = cands[0]
        if len(owsfz_match_count[(k[0], c)]) >= 2:
            ambiguous_refs.add(k)
    n_ambiguous = len(ambiguous_refs)
    ambiguous_frac = n_ambiguous / n_wild_gained if n_wild_gained else 0.0

    print("\n--- 3.3 R_wild (exact OR wildcard, upper bound) ---")
    print("n_wild_gained (ref rows newly matched under wildcarding) = %d" % n_wild_gained)
    print("n_ambiguous = %d  (n_ambiguous / n_wild_gained = %.1f%%, predicted <15%%)" % (n_ambiguous, 100.0 * ambiguous_frac))
    print("R_wild = (%d + %d) / %d = %.2f%%" % (len(exact_matched), n_wild_gained, n_ref_pop, R_wild))
    print("M = R_wild - R_base = %.2f pp  (predicted 1.5-3.0 pp)" % M)

    # --- ROW 0 + Gate A, strict ordered trace ------------------------------
    print("\n--- ROW 0 trace (evaluated in strict order) ---")
    row0 = None
    checks = [
        ("0a: |R_base - 55.5| <= 0.5", abs(R_base - 55.5) <= 0.5, abs(R_base - 55.5)),
        ("0b: 0.03 <= ours_hash_share <= 0.08", 0.03 <= ours_hash_share <= 0.08, ours_hash_share),
        ("0c: M >= -0.1", M >= -0.1, M),
        ("0d: M <= 100*n_ours_hash/n_ref_pop", M <= 100.0 * n_ours_hash / n_ref_pop, (M, 100.0 * n_ours_hash / n_ref_pop)),
    ]
    for name, passed, val in checks:
        print("   %-42s %-5s  value=%s" % (name, "PASS" if passed else "FAIL", val))
    row0 = h1_row0(R_base, M, ours_hash_share, n_ours_hash, n_ref_pop)
    print("   >>> %s <<<" % (row0 if row0 else "ROW 0 CLEAR"))

    gate_a = h1_gate_a(M) if row0 is None else "VOID (%s)" % row0
    print("\n>>> GATE A: %s <<<" % gate_a)

    # --- S3.4 FP side -------------------------------------------------------
    print("\n" + "=" * 78)
    print("FP SIDE")
    print("=" * 78)

    A, B = set(owsfz_a), set(owsfz_b)
    W1, W2 = set(wsjtx_a), set(wsjtx_b)
    W = W1 | W2
    known = known_callsigns(W)  # held in memory only, never printed

    def fp_rate(A_set, B_set, label):
        novel_corr = (A_set & B_set) - W
        novel_single = (A_set | B_set) - W - (A_set & B_set)
        raw_c, tot_c, ok_c, excl_c = plausibility_counts(novel_corr, known)
        raw_s, tot_s, ok_s, excl_s = plausibility_counts(novel_single, known)
        numerator = (tot_c - ok_c) + (tot_s - ok_s)
        denom = len(A_set | B_set)
        f_rate = 100.0 * numerator / denom if denom else float("nan")
        print("   [%s] novel_corroborated raw=%d total=%d ok=%d silent_excl=%d" % (label, raw_c, tot_c, ok_c, excl_c))
        print("   [%s] novel_single_only  raw=%d total=%d ok=%d silent_excl=%d" % (label, raw_s, tot_s, ok_s, excl_s))
        print("   [%s] implausible=%d / |A u B|=%d  ->  F = %.2f%%" % (label, numerator, denom, f_rate))
        return f_rate, excl_c + excl_s

    print("\n--- F_base (novel buckets as-is, existing proxy) ---")
    F_base, silent_excl_base = fp_rate(A, B, "base")

    A2 = {k for k in A if not has_hash(k[1])}
    B2 = {k for k in B if not has_hash(k[1])}
    print("\n--- F_excl (our <...> rows removed from A/B before classification) ---")
    print("   dropped from A: %d   dropped from B: %d" % (len(A) - len(A2), len(B) - len(B2)))
    F_excl, silent_excl_after = fp_rate(A2, B2, "excl")

    delta_F = F_base - F_excl
    print("\nsilent-exclusion count (S3.4, F_base pass): %d rows dropped from the plausibility denominator"
          " because every callsign-shaped token in the message was hashed" % silent_excl_base)
    print("delta_F = F_base - F_excl = %.2f - %.2f = %.2f pp  (predicted 0.5-1.5 pp)" % (F_base, F_excl, delta_F))

    gate_b = h1_gate_b(delta_F)
    print("\n>>> GATE B: %s <<<" % gate_b)

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print("R_base=%.2f%%  R_excl=%.2f%%  R_wild=%.2f%%  M=%.2f pp  n_wild_gained=%d  n_ambiguous=%d (%.1f%%)"
          % (R_base, R_excl, R_wild, M, n_wild_gained, n_ambiguous, 100.0 * ambiguous_frac))
    print("F_base=%.2f%%  F_excl=%.2f%%  delta_F=%.2f pp  silent_excl(base)=%d" % (F_base, F_excl, delta_F, silent_excl_base))
    print("ROW 0 = %s" % (row0 if row0 else "CLEAR"))
    print("GATE A = %s" % gate_a)
    print("GATE B = %s" % gate_b)


if __name__ == "__main__":
    main()
