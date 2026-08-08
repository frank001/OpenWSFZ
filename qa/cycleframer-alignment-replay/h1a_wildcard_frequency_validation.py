#!/usr/bin/env python3
"""H1a -- validate H1's wildcard matches by frequency.

Spec: qa/cycleframer-alignment-replay/2026-08-08-2156-architect-to-qa-spec-h1a-wildcard-frequency-validation.md
      (committed c1fe9b6 BEFORE this ran; gate + Architect prediction are in it.)

Imports H1's loader and matcher rather than reimplementing them, so the gained
set is provably the same rows H1 measured (spec S6.1).

Tolerance is DERIVED, not chosen (spec S0.2): our frequency is on the 3.125 Hz
lattice, so 1.5625 (max lattice offset) + 0.5 (our rounding) + 0.5 (reference
rounding) = 2.5625 Hz  =>  |df| <= 3 Hz.

The null is MEASURED, not assumed (spec S2.2): a within-cycle permutation gives
the spurious-match rate this corpus actually produces.

NFR-021: counts, rates and frequency statistics only. No message text, no
callsign, is printed anywhere.
"""
import random
import sys

from h1_hash_token_contamination import (
    SOURCES, WINDOW_20M, load, has_hash, wildcard_match,
    CALLSIGN_RE,
)

TOL_HZ = 3          # derived, spec S0.2 -- NOT a tunable
SEED = 20260808     # recorded, spec S2.2


# --- gate, verbatim from spec S3 --------------------------------------------

def h1a_row0(n_gained, v, v_null):
    if not (1500 <= n_gained <= 1620):
        return "ROW 0a"   # did not reproduce H1's gained population (1 563)
    if v_null > 0.10:
        return "ROW 0b"   # discriminator has no power on this corpus
    if v < v_null:
        return "ROW 0c"   # genuine pairs match worse than random -- instrument failure
    return None


def h1a_gate(v):
    if v >= 0.95:
        return "ROW 1"
    if v <= 0.75:
        return "ROW 2"
    return "ROW 3"


def callsign_tokens(msg):
    return [t.strip("<>") for t in msg.split() if CALLSIGN_RE.match(t.strip("<>"))]


def plausibility_counts(keys, known):
    raw_n = total = ok = 0
    for _, msg in keys:
        raw_n += 1
        cs = callsign_tokens(msg)
        if not cs:
            continue
        total += 1
        if all(c in known for c in cs):
            ok += 1
    return raw_n, total, ok, raw_n - total


def known_callsigns(keys):
    found = set()
    for _, msg in keys:
        for tok in msg.split():
            tok = tok.strip("<>")
            if CALLSIGN_RE.match(tok):
                found.add(tok)
    return found


def main():
    lo, hi = WINDOW_20M
    print("=" * 78)
    print("H1a -- wildcard-match frequency validation, 20m leg, %s..%s" % (lo, hi))
    print("tolerance |df| <= %d Hz (DERIVED, spec S0.2)   seed=%d" % (TOL_HZ, SEED))
    print("=" * 78)

    owsfz_a = load(SOURCES["owsfz_a"], lo, hi)
    owsfz_b = load(SOURCES["owsfz_b"], lo, hi)
    wsjtx_a = load(SOURCES["wsjtx_a"], lo, hi)
    wsjtx_b = load(SOURCES["wsjtx_b"], lo, hi)

    ref_keys = set(wsjtx_a) & set(wsjtx_b)
    n_ref_pop = len(ref_keys)
    exact_matched = ref_keys & set(owsfz_a)

    # --- rebuild H1's gained set, identical construction --------------------
    owsfz_by_ts = {}
    for (ts, msg) in owsfz_a:
        owsfz_by_ts.setdefault(ts, []).append(msg)

    gained = {}
    for k in (ref_keys - exact_matched):
        ts, ref_msg = k
        cands = [m for m in owsfz_by_ts.get(ts, []) if wildcard_match(ref_msg, m)]
        if cands:
            gained[k] = cands
    n_gained = len(gained)
    print("\nreference population = %d ; exact matches = %d ; n_wild_gained = %d"
          % (n_ref_pop, len(exact_matched), n_gained))

    # --- S2.1 df for each gained pair --------------------------------------
    deltas = []          # (ref_key, df) using first candidate (deterministic, file order)
    deltas_unambig = []
    for k, cands in gained.items():
        ts, ref_msg = k
        f_ref = wsjtx_a[k][1]
        f_ours = owsfz_a[(ts, cands[0])][1]
        d = abs(f_ours - f_ref)
        deltas.append(d)
        if len(cands) == 1:
            deltas_unambig.append(d)

    n_within = sum(1 for d in deltas if d <= TOL_HZ)
    V = n_within / n_gained if n_gained else 0.0
    V_unambig = (sum(1 for d in deltas_unambig if d <= TOL_HZ) / len(deltas_unambig)
                 if deltas_unambig else 0.0)

    print("\n--- 2.1 validation fraction ---")
    print("V = %d / %d = %.4f   (predicted 0.95-0.99)" % (n_within, n_gained, V))
    print("V restricted to unambiguous rows only: %d rows, V=%.4f" % (len(deltas_unambig), V_unambig))

    print("\ndf histogram (Hz, 1 Hz bins):")
    for b in range(0, 21):
        n = sum(1 for d in deltas if d == b)
        if n:
            print("   %3d Hz  %6d  %5.1f%%  %s" % (b, n, 100.0 * n / n_gained, "#" * min(60, n // 20)))
    over = sum(1 for d in deltas if d > 20)
    print("   >20 Hz  %6d  %5.1f%%" % (over, 100.0 * over / n_gained))

    # --- S2.2 null, MEASURED by within-cycle permutation --------------------
    rng = random.Random(SEED)
    null_deltas = []
    no_alternative = 0
    for k, cands in gained.items():
        ts, ref_msg = k
        pool = [m for m in owsfz_by_ts.get(ts, []) if m not in cands]
        if not pool:
            no_alternative += 1
            continue
        pick = rng.choice(pool)
        null_deltas.append(abs(owsfz_a[(ts, pick)][1] - wsjtx_a[k][1]))
    V_null = (sum(1 for d in null_deltas if d <= TOL_HZ) / len(null_deltas)
              if null_deltas else 0.0)
    print("\n--- 2.2 null (within-cycle permutation, as specced) ---")
    print("V_null = %d / %d = %.4f   (predicted <0.03; ROW 0b if >0.10)"
          % (sum(1 for d in null_deltas if d <= TOL_HZ), len(null_deltas), V_null))
    print("cycles with no alternative row available: %d" % no_alternative)

    # --- BEYOND SPEC: a STRICTER null that runs against my own prediction ----
    # The specced null draws any other row in the cycle. But a real spurious
    # wildcard match must still be TOKEN-COMPATIBLE, so the honest adversarial
    # null draws only from rows with the same token count. This is harder to
    # beat and is reported as an extra bound, not as the gated number.
    rng2 = random.Random(SEED)
    strict_deltas = []
    strict_none = 0
    for k, cands in gained.items():
        ts, ref_msg = k
        ntok = len(ref_msg.split())
        pool = [m for m in owsfz_by_ts.get(ts, [])
                if m not in cands and len(m.split()) == ntok]
        if not pool:
            strict_none += 1
            continue
        pick = rng2.choice(pool)
        strict_deltas.append(abs(owsfz_a[(ts, pick)][1] - wsjtx_a[k][1]))
    V_null_strict = (sum(1 for d in strict_deltas if d <= TOL_HZ) / len(strict_deltas)
                     if strict_deltas else 0.0)
    print("\n--- 2.2b STRICTER null (token-count-matched; BEYOND SPEC, not gated) ---")
    print("V_null_strict = %d / %d = %.4f"
          % (sum(1 for d in strict_deltas if d <= TOL_HZ), len(strict_deltas), V_null_strict))
    print("rows with no token-compatible alternative: %d" % strict_none)

    # --- S2.3 corrected upper end ------------------------------------------
    R_base = 100.0 * len(exact_matched) / n_ref_pop
    R_wild = 100.0 * (len(exact_matched) + n_gained) / n_ref_pop
    R_wild_val = 100.0 * (len(exact_matched) + n_within) / n_ref_pop
    print("\n--- 2.3 corrected upper end ---")
    print("R_base = %.2f%%   R_wild = %.2f%%   R_wild_val = %.2f%%" % (R_base, R_wild, R_wild_val))

    # --- gate ---------------------------------------------------------------
    print("\n--- gate trace (spec S3) ---")
    row0 = h1a_row0(n_gained, V, V_null)
    print("0a: 1500 <= n_gained(%d) <= 1620          %s" % (n_gained, "PASS" if 1500 <= n_gained <= 1620 else "FAIL"))
    print("0b: V_null(%.4f) <= 0.10                  %s" % (V_null, "PASS" if V_null <= 0.10 else "FAIL"))
    print("0c: V(%.4f) >= V_null(%.4f)               %s" % (V, V_null, "PASS" if V >= V_null else "FAIL"))
    if row0:
        print("\n   >>> %s <<<   (instrument failure -- bracket STANDS unchanged)" % row0)
        return
    print(">>> ROW 0 CLEAR <<<")
    row = h1a_gate(V)
    print("V = %.4f  vs  ROW 1 bar 0.95 / ROW 2 bar 0.75" % V)
    print("\n   >>> %s <<<" % row)

    # --- S4 second deliverable: the FP level's unstated uncertainty ---------
    print("\n" + "=" * 78)
    print("S4 -- FP level uncertainty from the 280 silently-excluded rows")
    print("=" * 78)
    A, B = set(owsfz_a), set(owsfz_b)
    W = set(wsjtx_a) | set(wsjtx_b)
    known = known_callsigns(W)
    corro = (A & B) - W
    single = (A | B) - W - (A & B)
    c_raw, c_tot, c_ok, c_excl = plausibility_counts(corro, known)
    s_raw, s_tot, s_ok, s_excl = plausibility_counts(single, known)
    implausible = (c_tot - c_ok) + (s_tot - s_ok)
    denom = len(A | B)
    silent = c_excl + s_excl
    F_lo = 100.0 * implausible / denom
    F_hi = 100.0 * (implausible + silent) / denom
    c_rate = (c_tot - c_ok) / c_tot if c_tot else 0.0
    s_rate = (s_tot - s_ok) / s_tot if s_tot else 0.0
    expected = c_excl * c_rate + s_excl * s_rate
    F_mid = 100.0 * (implausible + expected) / denom
    print("novel-corroborated : raw=%d total=%d ok=%d silently_excluded=%d implausible_rate=%.3f"
          % (c_raw, c_tot, c_ok, c_excl, c_rate))
    print("novel-single-only  : raw=%d total=%d ok=%d silently_excluded=%d implausible_rate=%.3f"
          % (s_raw, s_tot, s_ok, s_excl, s_rate))
    print("implausible=%d  denom|AuB|=%d  silently_excluded_total=%d" % (implausible, denom, silent))
    print("F_lo  (all 280 legitimate)  = %.2f%%" % F_lo)
    print("F_hi  (all 280 fabricated)  = %.2f%%" % F_hi)
    print("F_mid (class-rate weighted, an ESTIMATE not a measurement) = %.2f%%  (expected %.1f of %d)"
          % (F_mid, expected, silent))


if __name__ == "__main__":
    main()
