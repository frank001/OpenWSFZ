#!/usr/bin/env python3
"""`FP-FLOOR-LIVE-2` Part B -- read the frozen gate against the closed corpus.

Spec: qa/rr-study/2026-09-10-1426-architect-to-qa-fp-floor-live-2-part-b-authorised.md
      (arch/fp-floor-operator-setting, commit 32375fb). Reuses the withdrawn
      FP-FLOOR-LIVE spec's (2026-09-08-1710-...) ROW 0 / predicate / gate
      VERBATIM, with Amendment 1's two changes layered on: the emitted SNR is
      ROUNDED (3afc362) -- this arm's predicate removes excess<=3.0, a strict
      SUPERSET of T's excess<2.622 -- and REF = A only (b1076bf) -- WSJT-X #2
      (SDR Uno) is diagnostic-only, on its own span, never a corroborator.

      CORRECTED per the Architect's 2026-09-10 acceptance ruling
      (qa/rr-study/2026-09-10-1443-architect-fp-floor-live-2-part-b-acceptance-ruling.md):
      the measured K_removed is NEITHER an upper nor a lower bound on T's own
      genuine-loss rate. The predicate superset above biases it as an UPPER
      bound on T's own CORROBORATION rate (the extra slice T would keep sits
      in the -24 bin and is closer to the boundary, plausibly higher-
      corroboration); corroboration itself undercounts genuine decodes
      (the reference misses some too), which is a LOWER bound on true
      genuine loss. The two point in opposite directions. ROW 2 still holds
      for T under the worst-case allocation of the -24 bin's corroborated
      decodes (see the acceptance ruling for the derivation) -- report both
      the measured rate on the rounded cut AND that worst-case floor for T;
      never call either one "T's genuine-loss rate" alone.

Population: the Amendment 3 boundary, a single contiguous span
[2026-09-08T19:36:45Z, close). n = 601 (OpenWSFZ decodes at reported <=-24dB
in that span) -- this IS the arm's own stopping-rule count, reproduced here
from ALL.TXT rather than trusted from contents.md (HK-022).

Matching logic imported from h1_hash_token_contamination.wildcard_match
(the H1/H1a matcher), not reimplemented -- per spec S5 "Harness" note.

NFR-021: counts and rates only. No message_text, no callsign, is printed or
written anywhere by this script.
"""
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from h1_hash_token_contamination import wildcard_match  # reuse, do not reimplement

from scipy.stats import beta as _beta_dist  # same construction as f-nbr-a/stats_common.py

# --- fixed population, per spec S2.1 (Amendment 3 boundary) -----------------
BOUNDARY_TS = "260908_193645"     # 2026-09-08T19:36:45Z, frozen (Amendment 3)
DIAL_PREFIX = "14.074"

OWSFZ_ALL = (r"D:\Projects\claude\OpenWSFZ\artefacts\20260908_live_run_1827-fp-floor-live-2"
             r"\openwsfz\ALL.TXT")
WSJTX_A_ALL = r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT"        # REF = A (Amendment 1)
WSJTX_B_ALL = r"C:\Users\Frank\AppData\Local\WSJT-X - SDRUno\ALL.TXT"        # diagnostic only

B_STOP_TS = "260908_185245"       # Captain stopped SDR Uno, 18:52:45Z -- < boundary

# --- the predicate, VERBATIM from spec S2.4 ----------------------------------
# excess = Snr + 26.5   (FP-PARITY S2.2); T_EXCESS = 2.622 (FP-PARITY S4 ROW 2)
T_EXCESS = 2.622
SNR_CUT = T_EXCESS - 26.5              # -23.878
TOL_HZ = 3                             # H1a's derived tolerance, spec S2.2 -- not a tunable


def removed(snr):
    return snr < SNR_CUT               # integer readout => snr <= -24


def load(path, ts_lo, dial_prefix=DIAL_PREFIX):
    """(ts, message) -> (snr, freq_hz) for Rx FT8 lines on dial freq, ts >= ts_lo.
    Returns (dict, n_qualifying_lines) -- the dict may be smaller than the count
    if two lines share an exact (ts, message) key (rare, matches H1's own loader)."""
    out = {}
    n_lines = 0
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if not f[1].startswith(dial_prefix):
                continue
            ts = f[0]
            if ts < ts_lo:
                continue
            n_lines += 1
            try:
                snr, freq_hz = int(f[4]), int(f[6])
            except ValueError:
                continue
            out[(ts, " ".join(f[7:]))] = (snr, freq_hz)
    return out, n_lines


def clopper_pearson(k, n, alpha=0.05):
    lo = 0.0 if k == 0 else float(_beta_dist.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(_beta_dist.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def ts_to_dt(ts):
    return datetime.strptime(ts, "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc)


def main():
    print("=" * 78)
    print("FP-FLOOR-LIVE-2 Part B -- frozen gate, corpus 20260908_live_run_1827-fp-floor-live-2")
    print("valid span: [2026-09-08T19:36:45Z, close)  (Amendment 3, single contiguous span)")
    print("=" * 78)

    owsfz, n_owsfz_lines = load(OWSFZ_ALL, BOUNDARY_TS)
    wsjtx_a, n_a_lines = load(WSJTX_A_ALL, BOUNDARY_TS)
    wsjtx_b, n_b_lines = load(WSJTX_B_ALL, BOUNDARY_TS)

    print("\n--- population (all mechanically re-derived from ALL.TXT, not trusted from contents.md) ---")
    print("OpenWSFZ qualifying lines  (dict size) : %d  (%d)" % (n_owsfz_lines, len(owsfz)))
    print("WSJT-X #1 (A) qualifying lines (dict)  : %d  (%d)" % (n_a_lines, len(wsjtx_a)))
    print("WSJT-X #2 (B) qualifying lines (dict)  : %d  (%d)  -- expect 0, diagnostic only" % (n_b_lines, len(wsjtx_b)))
    print("expected total decodes in span = 57969 : %s" % ("MATCH" if n_owsfz_lines == 57969 else "MISMATCH"))

    owsfz_by_ts = {}
    for (ts, msg), (snr, freq) in owsfz.items():
        owsfz_by_ts.setdefault(ts, []).append((msg, snr, freq))
    wsjtx_a_by_ts = {}
    for (ts, msg), (snr, freq) in wsjtx_a.items():
        wsjtx_a_by_ts.setdefault(ts, []).append((msg, freq))

    def is_corroborated(ts, msg, freq):
        """spec S2.2: same cycle, |df|<=TOL_HZ, wildcard message matching mandatory.
        wildcard_match() also accepts an exact textual match (all tokens equal),
        so this one predicate covers both halves of the spec's matching rule."""
        exact_only = False
        wild_only = False
        for cand_msg, cand_freq in wsjtx_a_by_ts.get(ts, []):
            if abs(freq - cand_freq) > TOL_HZ:
                continue
            if not wildcard_match(msg, cand_msg):
                continue
            if cand_msg == msg:
                exact_only = True
            else:
                wild_only = True
        if exact_only or wild_only:
            return True, wild_only and not exact_only
        return False, False

    n_removed = 0
    k_removed_corrob = 0
    n_kept = 0
    k_kept_corrob = 0
    n_wildcard_only_total = 0
    by_snr = {}   # s -> [n, k]  for s in -38..+10 pooled over ALL decodes (not just removed)
    n_ge0 = 0
    k_ge0 = 0

    for (ts, msg), (snr, freq) in owsfz.items():
        corrob, wildcard_only_case = is_corroborated(ts, msg, freq)
        if wildcard_only_case:
            n_wildcard_only_total += 1
        if -38 <= snr <= 10:
            rec = by_snr.setdefault(snr, [0, 0])
            rec[0] += 1
            if corrob:
                rec[1] += 1
        if snr >= 0:
            n_ge0 += 1
            if corrob:
                k_ge0 += 1
        if removed(snr):
            n_removed += 1
            if corrob:
                k_removed_corrob += 1
        else:
            n_kept += 1
            if corrob:
                k_kept_corrob += 1

    n_all = n_removed + n_kept
    k_all = k_removed_corrob + k_kept_corrob
    K_removed_val = k_removed_corrob / n_removed if n_removed else float("nan")
    K_kept_val = k_kept_corrob / n_kept if n_kept else float("nan")
    K_all_val = k_all / n_all if n_all else float("nan")
    K_ge0 = k_ge0 / n_ge0 if n_ge0 else float("nan")

    # --- ROW 0 ---------------------------------------------------------------
    print("\n--- ROW 0 (preconditions, evaluated in full, HK-025) ---")

    # 0a: provenance -- files are genuinely distinct captures, not a hardlink.
    import hashlib
    def sha256_of(path):
        h = hashlib.sha256()
        with io.open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    h_owsfz, h_a = sha256_of(OWSFZ_ALL), sha256_of(WSJTX_A_ALL)
    row0a = h_owsfz != h_a and n_owsfz_lines > 0 and n_a_lines > 0
    print("0a provenance: OpenWSFZ ALL.TXT sha256[:12]=%s  WSJT-X#1 ALL.TXT sha256[:12]=%s  distinct=%s  %s"
          % (h_owsfz[:12], h_a[:12], h_owsfz != h_a, "PASS" if row0a else "FAIL"))

    row0b = K_ge0 >= 0.90
    print("0b positive control: K(s>=0) = %d/%d = %.4f >= 0.90   %s"
          % (k_ge0, n_ge0, K_ge0, "PASS" if row0b else "FAIL"))

    row0c = n_removed >= 300
    print("0c removed>=300: n_removed=%d   %s" % (n_removed, "PASS" if row0c else "FAIL"))

    row0d = n_wildcard_only_total >= 1
    print("0d wildcard matching ON: %d decodes matched ONLY under wildcard (not exact)   %s"
          % (n_wildcard_only_total, "PASS" if row0d else "FAIL"))

    # 0e (Amendment 1 replacement): REF=A only asserted in code (trivial -- wsjtx_b
    # is never referenced above) + combiner constant across the whole span (single
    # contiguous span, already established) + "no B coverage".
    #
    # CORRECTED 2026-09-10 (Architect's catch, bd337f2): "B has 0 qualifying lines in
    # span" is VACUOUS as a standalone check -- B's ALL.TXT was already empty and
    # un-appended-to at 2026-09-08T18:16:31Z (see artefacts/.../wsjtx-SNAPSHOT.md +
    # contents.md), BEFORE the 18:33:11Z capture start, let alone this span. An
    # already-frozen-empty file passes an "any lines >= boundary" check trivially no
    # matter when the boundary sits, so it cannot by itself distinguish "B correctly
    # logged nothing in-span" from "B's pipe was broken the whole time". The
    # LOAD-BEARING check is the operational timestamp comparison below; the line
    # count is reported alongside it only as a (non-diagnostic) consistency note.
    b_stopped_before_span = B_STOP_TS < BOUNDARY_TS
    row0e = b_stopped_before_span
    print("0e REF=A only, combiner constant, no B coverage: B stopped %s, span starts %s -> %s   %s"
          % (B_STOP_TS, BOUNDARY_TS, "no overlap" if b_stopped_before_span else "OVERLAP",
             "PASS" if row0e else "FAIL"))
    print("   (B's qualifying-line count in span = %d -- consistent, but VACUOUS on its own: B's"
          " ALL.TXT was already empty before capture start, so this count would read 0 regardless"
          " of whether B ever overlapped the span.)" % n_b_lines)

    row0_all_pass = row0a and row0b and row0c and row0d and row0e
    print("\n>>> ROW 0: %s <<<" % ("CLEAR" if row0_all_pass else "FIRES -- ROW 4 VOID"))
    if not row0_all_pass:
        print("\nPer spec S2.3/S4 ROW4: NO K_removed is quoted even descriptively. Stopping here.")
        return

    # --- headline --------------------------------------------------------------
    lo, hi = clopper_pearson(k_removed_corrob, n_removed)
    print("\n" + "=" * 78)
    print("HEADLINE (measured on the ROUNDED/emitted cut -- Amendment 1, 3afc362)")
    print("=" * 78)
    print("k (corroborated AND removed) = %d" % k_removed_corrob)
    print("n (removed)                  = %d" % n_removed)
    print("K_removed = k/n = %.4f%%   CP95 = [%.4f%%, %.4f%%]" % (100 * K_removed_val, 100 * lo, 100 * hi))
    print("NEITHER bound on T's own genuine-loss rate (Architect's 2026-09-10 acceptance ruling,")
    print("qa/rr-study/2026-09-10-1443-architect-fp-floor-live-2-part-b-acceptance-ruling.md):")
    print("predicate superset (this cut removes excess<=3.0, T removes excess<2.622) makes this an")
    print("upper bound on T's own CORROBORATION rate; corroboration undercounting genuine decodes")
    print("(the reference misses some too) makes any such figure a lower bound on true genuine loss.")

    n_bin24, k_bin24 = by_snr.get(-24, [0, 0])
    k_t1, n_t1 = k_removed_corrob - k_bin24, n_removed - k_bin24   # strip only the -24 bin's corroborated decodes
    k_t2, n_t2 = k_removed_corrob - k_bin24, n_removed - n_bin24   # drop the whole -24 bin
    lo_t1, hi_t1 = clopper_pearson(k_t1, n_t1) if n_t1 else (float("nan"), float("nan"))
    lo_t2, hi_t2 = clopper_pearson(k_t2, n_t2) if n_t2 else (float("nan"), float("nan"))
    print("\nT worst-case floor (strip -24 bin's corroborated decodes from k AND n, assuming they're")
    print("all the extra slice T would keep): k=%d n=%d -> %.2f%%  CP95 lo=%.2f%%"
          % (k_t1, n_t1, 100 * k_t1 / n_t1 if n_t1 else float("nan"), 100 * lo_t1))
    print("T worst-case floor, alternative (drop the whole -24 bin): k=%d n=%d -> %.2f%%  CP95 lo=%.2f%%"
          % (k_t2, n_t2, 100 * k_t2 / n_t2 if n_t2 else float("nan"), 100 * lo_t2))
    print("Either way, ROW 2 holds for T too (lo far past the >=5% bar).")

    t0 = ts_to_dt(BOUNDARY_TS)
    last_ts = max(ts for (ts, _msg) in owsfz)
    t1 = ts_to_dt(last_ts)
    span_hours = (t1 - t0).total_seconds() / 3600.0
    rate_per_hour = k_removed_corrob / span_hours if span_hours else float("nan")
    print("span: %s -> %s (last OpenWSFZ decode ts) = %.3f h" % (t0.isoformat(), t1.isoformat(), span_hours))
    print("genuine decodes lost per operating hour (k / span_hours) = %.4f" % rate_per_hour)

    print("\n--- context (sibling (u): a rate is not evidence without its base rate) ---")
    print("K_kept  (corroboration among KEPT decodes, snr>-24) = %d/%d = %.4f%%" % (k_kept_corrob, n_kept, 100 * K_kept_val))
    print("K_all   (corroboration over ALL decodes in span)    = %d/%d = %.4f%%" % (k_all, n_all, 100 * K_all_val))
    print("ROW 0b control K(s>=0)                              = %d/%d = %.4f%%" % (k_ge0, n_ge0, 100 * K_ge0))

    print("\n--- the OTHER bound (not the headline), with its direction (spec S4) ---")
    junk_removed_n = n_removed - k_removed_corrob
    print("removed AND NOT corroborated = %d / %d removed = %.4f%%"
          % (junk_removed_n, n_removed, 100 * junk_removed_n / n_removed if n_removed else float("nan")))
    print("This is an UPPER BOUND on junk removed, not a count of junk (uncorroborated != false).")

    print("\n--- full K(s) curve, s=-38..+10 (spec S5 item 2) ---")
    print("%6s %8s %8s %10s" % ("s(dB)", "n", "k", "K(s)"))
    for s in range(-38, 11):
        n_s, k_s = by_snr.get(s, [0, 0])
        rate_str = ("%9.2f%%" % (100.0 * k_s / n_s)) if n_s else "      n/a"
        print("%6d %8d %8d %s" % (s, n_s, k_s, rate_str))

    print("\n--- no B coverage (spec S5 item 4) ---")
    print("WSJT-X #2 (SDR Uno) stopped 2026-09-08T18:52:45Z; analysed span starts 2026-09-08T19:36:45Z;")
    print("44-minute gap, zero overlap -- basis is the OPERATIONAL TIMELINE (0e above), not the line")
    print("count: B's ALL.TXT was already empty since 18:16:31Z, before capture even started, so its")
    print("%d qualifying-lines-in-span figure is consistent but VACUOUS as independent confirmation." % n_b_lines)

    # --- reading rule, strict order, spec S2.5 ---------------------------------
    print("\n" + "=" * 78)
    print("READING RULE (spec S2.5, evaluated in strict order)")
    print("=" * 78)
    if hi <= 0.02:
        row = "ROW 1"
        consequence = ("Architect is cleared to DRAFT a separate pre-registration for a "
                        "default-off operator control. NOT a licence to build, touch src/, "
                        "or author a settings page.")
    elif lo >= 0.05:
        row = "ROW 2"
        consequence = "No operator control is drafted. State the loss rate per hour and stop."
    else:
        row = "ROW 3"
        consequence = ("Report k, n, [lo,hi], per-hour rate; draft nothing. Position decides "
                        "a straddle, not width (sibling (w)).")
    print("hi=%.4f%% vs ROW1 bar <=2.00%%   lo=%.4f%% vs ROW2 bar >=5.00%%" % (100 * hi, 100 * lo))
    print(">>> %s <<<" % row)
    print(consequence)

    print("\n" + "=" * 78)
    print("Reminder, unchanged by this run (spec S3): FP-PARITY ROW3 (F-T=5.378dB) stays fired;")
    print("no baseline created, FP-REGRESSION untouched; no src/ work authorised in any row;")
    print("D-003 (bandlimited noise-floor misestimate) remains untested by this arm.")


if __name__ == "__main__":
    main()
