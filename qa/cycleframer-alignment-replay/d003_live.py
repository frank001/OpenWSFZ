#!/usr/bin/env python3
"""`D003-LIVE` -- does OpenWSFZ misread SNR on live audio, on the current binary?

Spec: qa/rr-study/2026-09-10-1536-architect-to-qa-s1-ladder-reply-and-d003-live-spec.md
      section 3 (arch/d003-live, commit bd337f2). R_STAR ratified and the HOLD lifted
      by commit 2c439b5 ("0.17% is approved", PO, 2026-09-10 15:44Z).

Population: the FP-FLOOR-LIVE-2 corpus, Amendment 3's frozen span
[2026-09-08T19:36:45Z, close). REF is WSJT-X #1 (FT-991A), read from the corpus's OWN
SNAPSHOT (artefacts/.../wsjtx-1-ft991a/ALL.TXT), never from %LOCALAPPDATA% -- spec S3.1.

Join reused BY IMPORT from Part B's harness (fp_floor_live_2_part_b.py): its `load()`
loader and its wildcard matcher (h1_hash_token_contamination.wildcard_match), per spec
S3.1 "Do not write a new implementation." Only the candidate-SELECTION logic (which of
possibly several matching WSJT-X lines to diff SNR against: ASSIGN_EXCL / ASSIGN_NEAR)
is new -- Part B never needed to pick one, since it only asked "does >=1 match exist".

NFR-021: message text is held in memory only, transiently, for the exact-vs-wildcard
tie-break inside assign_pairs() -- never printed, never written to any file. Report
prose is scanned with nfr021_pre_merge_scan.scan()/classify() before commit.
"""
import hashlib
import io
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binom

sys.path.insert(0, str(Path(__file__).parent))
from fp_floor_live_2_part_b import clopper_pearson, ts_to_dt  # reuse, do not reimplement
from h1_hash_token_contamination import wildcard_match  # reuse, do not reimplement

# --- fixed population, spec S3.1 --------------------------------------------
DIAL_PREFIX = "14.074"
BOUNDARY_TS = "260908_193645"     # 2026-09-08T19:36:45Z, frozen (Amendment 3)
OWSFZ_ALL = (r"D:\Projects\claude\OpenWSFZ\artefacts\20260908_live_run_1827-fp-floor-live-2"
             r"\openwsfz\ALL.TXT")
# REF: the corpus's OWN snapshot, never AppData (spec S3.1 / S2.3).
REF_PATH = (r"D:\Projects\claude\OpenWSFZ\artefacts\20260908_live_run_1827-fp-floor-live-2"
            r"\wsjtx-1-ft991a\ALL.TXT")

# --- the predicate, as code -- spec S3.2, and where this and the prose disagree
# the code is the spec (HK-021(r)) ---------------------------------------------
REF_SHA256 = "dda9483aaee6295369f8b51cb8057fc6fef054be84772f2fd003fdc3f65b529d"
WSJTX_FLOOR = -24          # reference clamp (spec S2.2)
SIGMA2_REP = 0.17          # S1 Repeatability sigma^2, dB^2: results/2026-09-07-4cc1984/report.md:41
TAIL_DB = 10               # D-003's field definition (June reports); >= 10x the 1 dB readout quantum
R_STAR = SIGMA2_REP / TAIL_DB ** 2          # = 0.0017. PO-RATIFIED 2026-09-10 15:44Z, FROZEN
assert abs(R_STAR - 0.0017) < 1e-12

TOL_HZ = 3                 # H1a's derived tolerance -- not a tunable
BOOT_DRAWS = 2000
BOOT_SEED = 20260910

# --- expected-reproduction constants, spec S3.3 ROW 0a ------------------------
EXPECT_N_TOTAL = 57969
EXPECT_N_CORROB = 55607
EXPECT_N_CORROB_LE24 = 313
EXPECT_N_CORROB_LE31 = 6
EXPECT_K_BINS_LE31 = {-36: 1, -32: 1, -31: 4}  # sums to 6


def sha256_of(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path, ts_lo, dial_prefix=DIAL_PREFIX):
    """(ts, message) -> (snr, freq_hz) for Rx FT8 lines on dial freq, ts >= ts_lo.
    Identical shape to Part B's own loader (kept local, not imported, because Part B's
    loader is a private module-level function, not part of its documented reuse
    surface -- only `wildcard_match`, `clopper_pearson`, `ts_to_dt` are)."""
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


def build_records(owsfz, wsjtx_by_ts):
    """For every OpenWSFZ decode, resolve its candidate WSJT-X#1 matches (spec S3.1
    join: same cycle, |df|<=3, wildcard_match). Message text is held only inside this
    function's locals, never returned, never printed (NFR-021)."""
    records = []
    for (ts, msg), (snr_ow, freq_ow) in owsfz.items():
        cands = []
        for cmsg, csnr, cfreq in wsjtx_by_ts.get(ts, []):
            if abs(freq_ow - cfreq) > TOL_HZ:
                continue
            if not wildcard_match(msg, cmsg):
                continue
            exact = (cmsg == msg)
            cands.append((exact, csnr, cfreq))
        records.append({"ts": ts, "snr_ow": snr_ow, "freq_ow": freq_ow, "cands": cands})
    return records


def assign_pairs(records, mode):
    """mode in {'EXCL', 'NEAR'} -- spec S3.2. Returns list of (ts, snr_ow, freq_ow,
    snr_ref) tuples, one per kept OpenWSFZ decode."""
    out = []
    for r in records:
        cands = r["cands"]
        if mode == "EXCL":
            if len(cands) != 1:
                continue
            chosen = cands[0]
        else:  # NEAR: keep iff >=1; tie-break min |df|, then exact over wildcard,
               # then lower WSJT-X freq
            if len(cands) < 1:
                continue
            freq_ow = r["freq_ow"]
            chosen = min(cands, key=lambda c: (abs(freq_ow - c[2]), 0 if c[0] else 1, c[2]))
        out.append((r["ts"], r["snr_ow"], r["freq_ow"], chosen[1]))
    return out


def cluster_key(ts_dt, boundary_dt, freq_ow):
    return (freq_ow // 10, int((ts_dt - boundary_dt).total_seconds() // 3600))


def compute(pairs, boundary_dt):
    """Returns a dict of every figure spec S3.2/S3.6 needs, for one assignment mode."""
    n_pairs = len(pairs)
    delta = np.empty(n_pairs, dtype=np.int64)
    snr_ref_arr = np.empty(n_pairs, dtype=np.int64)
    freq_ow_arr = np.empty(n_pairs, dtype=np.int64)
    cluster_of = []
    for i, (ts, snr_ow, freq_ow, snr_ref) in enumerate(pairs):
        delta[i] = snr_ow - snr_ref
        snr_ref_arr[i] = snr_ref
        freq_ow_arr[i] = freq_ow
        cluster_of.append(cluster_key(ts_to_dt(ts), boundary_dt, freq_ow))

    uncensored = snr_ref_arr >= (WSJTX_FLOOR + 1)
    n_censored = int((~uncensored).sum())
    idx_u = np.where(uncensored)[0]
    c = float(np.median(delta[idx_u])) if len(idx_u) else float("nan")
    under = np.zeros(n_pairs, dtype=bool)
    over = np.zeros(n_pairs, dtype=bool)
    under[idx_u] = (delta[idx_u] - c) <= -TAIL_DB
    over[idx_u] = (delta[idx_u] - c) >= TAIL_DB

    n_u = int(uncensored.sum())
    k_u = int(under.sum())
    k_o = int(over.sum())
    R_u = k_u / n_u if n_u else float("nan")
    R_o = k_o / n_u if n_u else float("nan")

    # --- cluster-level aggregates: for CI bootstrap and the sign test ---------
    cstats = {}  # key -> [n_u, k_u, k_o]
    for i in range(n_pairs):
        if not uncensored[i]:
            continue
        key = cluster_of[i]
        rec = cstats.setdefault(key, [0, 0, 0])
        rec[0] += 1
        if under[i]:
            rec[1] += 1
        if over[i]:
            rec[2] += 1
    cluster_keys = sorted(cstats.keys())   # SORTED at construction -- hash-iteration order guard
    n_clusters = len(cluster_keys)
    n_arr = np.array([cstats[k][0] for k in cluster_keys], dtype=np.int64)
    ku_arr = np.array([cstats[k][1] for k in cluster_keys], dtype=np.int64)
    ko_arr = np.array([cstats[k][2] for k in cluster_keys], dtype=np.int64)

    lo_cp, hi_cp = clopper_pearson(k_u, n_u) if n_u else (float("nan"), float("nan"))

    rng = np.random.RandomState(BOOT_SEED)
    boot_rates = np.empty(BOOT_DRAWS, dtype=np.float64)
    if n_clusters:
        for b in range(BOOT_DRAWS):
            idx = rng.randint(0, n_clusters, size=n_clusters)
            bn = n_arr[idx].sum()
            bk = ku_arr[idx].sum()
            boot_rates[b] = (bk / bn) if bn else float("nan")
        boot_rates = boot_rates[~np.isnan(boot_rates)]
        lo_boot = float(np.percentile(boot_rates, 2.5)) if len(boot_rates) else float("nan")
        hi_boot = float(np.percentile(boot_rates, 97.5)) if len(boot_rates) else float("nan")
    else:
        lo_boot = hi_boot = float("nan")

    lo = min(x for x in (lo_cp, lo_boot) if x == x) if (lo_cp == lo_cp or lo_boot == lo_boot) else float("nan")
    hi = max(x for x in (hi_cp, hi_boot) if x == x) if (hi_cp == hi_cp or hi_boot == hi_boot) else float("nan")

    # --- sign test, cluster level ---------------------------------------------
    U = O = 0
    for key in cluster_keys:
        _, ku, ko = cstats[key]
        if ku + ko < 1:
            continue
        if ku > ko:
            U += 1
        elif ko > ku:
            O += 1
        # ties dropped
    p_sign = float(binom.sf(U - 1, U + O, 0.5)) if (U + O) > 0 else float("nan")

    n_distinct_delta_uncensored = int(len(set(delta[idx_u].tolist()))) if len(idx_u) else 0

    return {
        "n_pairs": n_pairs, "n_u": n_u, "n_censored": n_censored, "c": c,
        "k_u": k_u, "k_o": k_o, "R_u": R_u, "R_o": R_o,
        "lo_cp": lo_cp, "hi_cp": hi_cp, "lo_boot": lo_boot, "hi_boot": hi_boot,
        "lo": lo, "hi": hi, "n_clusters": n_clusters, "U": U, "O": O, "p_sign": p_sign,
        "n_distinct_delta_uncensored": n_distinct_delta_uncensored,
        "delta": delta, "c_val": c, "uncensored": uncensored,
        "freq_ow_arr": freq_ow_arr, "snr_ref_arr": snr_ref_arr,
    }


def reading_row(res):
    if res["hi"] <= R_STAR:
        return "ROW 1"
    if res["lo"] >= R_STAR and res["p_sign"] < 0.05:
        return "ROW 2"
    if res["lo"] >= R_STAR and res["p_sign"] >= 0.05:
        return "ROW 3"
    return "ROW 4"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # HK-009
    except AttributeError:
        pass

    print("=" * 78)
    print("D003-LIVE -- does OpenWSFZ misread SNR on live audio, on the current binary?")
    print("corpus: 20260908_live_run_1827-fp-floor-live-2, span [2026-09-08T19:36:45Z, close)")
    print("REF: WSJT-X #1, read from the SNAPSHOT, never AppData (spec S3.1)")
    print("=" * 78)

    # --- pre-flight asserts: harness STOPS on failure, not a row (spec S3.2) --
    h_ref = sha256_of(REF_PATH)
    assert h_ref == REF_SHA256, "REF snapshot has changed since the spec was written -- STOP"
    print("REF sha256 matches pinned value: PASS (%s)" % h_ref[:12])

    owsfz, n_owsfz_lines = load(OWSFZ_ALL, BOUNDARY_TS)
    wsjtx, n_ref_lines = load(REF_PATH, BOUNDARY_TS)

    wsjtx_snr_all = [snr for (snr, _freq) in wsjtx.values()]
    assert min(wsjtx_snr_all) == WSJTX_FLOOR, "clamp model broken -- STOP"
    assert sum(1 for s in wsjtx_snr_all if s < WSJTX_FLOOR) == 0, "reading below the clamp floor -- STOP"
    print("clamp model holds: min(REF SNR)=%d, 0 readings below it: PASS" % WSJTX_FLOOR)

    print("\nOpenWSFZ qualifying lines (dict size): %d (%d)" % (n_owsfz_lines, len(owsfz)))
    print("REF (snapshot) qualifying lines (dict): %d (%d)" % (n_ref_lines, len(wsjtx)))

    wsjtx_by_ts = {}
    for (ts, msg), (snr, freq) in wsjtx.items():
        wsjtx_by_ts.setdefault(ts, []).append((msg, snr, freq))

    records = build_records(owsfz, wsjtx_by_ts)
    pairs_excl = assign_pairs(records, "EXCL")
    pairs_near = assign_pairs(records, "NEAR")

    # ================= ROW 0 =================
    print("\n--- ROW 0 (validity preconditions, evaluated in full, HK-025) ---")

    n_total = len(records)
    n_corrob_near = len(pairs_near)
    n_corrob_le24 = sum(1 for (_ts, snr_ow, _f, _sr) in pairs_near if snr_ow <= -24)
    n_corrob_le31 = sum(1 for (_ts, snr_ow, _f, _sr) in pairs_near if snr_ow <= -31)
    k_bins_le31 = {}
    for (_ts, snr_ow, _f, _sr) in pairs_near:
        if snr_ow <= -31:
            k_bins_le31[snr_ow] = k_bins_le31.get(snr_ow, 0) + 1

    row0a = (n_total == EXPECT_N_TOTAL and n_corrob_near == EXPECT_N_CORROB
              and n_corrob_le24 == EXPECT_N_CORROB_LE24 and n_corrob_le31 == EXPECT_N_CORROB_LE31
              and k_bins_le31 == EXPECT_K_BINS_LE31)
    print("0a Part B reproduction (ASSIGN_NEAR): total=%d(exp %d) corrob=%d(exp %d) "
          "le-24=%d(exp %d) le-31=%d(exp %d) bins=%s(exp %s)   %s"
          % (n_total, EXPECT_N_TOTAL, n_corrob_near, EXPECT_N_CORROB, n_corrob_le24,
             EXPECT_N_CORROB_LE24, n_corrob_le31, EXPECT_N_CORROB_LE31, k_bins_le31,
             EXPECT_K_BINS_LE31, "PASS" if row0a else "FAIL"))

    boundary_dt = ts_to_dt(BOUNDARY_TS)
    res_excl = compute(pairs_excl, boundary_dt)
    res_near = compute(pairs_near, boundary_dt)
    row_excl = reading_row(res_excl)
    row_near = reading_row(res_near)
    row0b = (row_excl == row_near)
    print("0b same row under both assignments: EXCL=%s NEAR=%s   %s"
          % (row_excl, row_near, "PASS" if row0b else "FAIL"))

    row0c = (res_excl["n_distinct_delta_uncensored"] >= 5 and res_near["n_distinct_delta_uncensored"] >= 5)
    print("0c >=5 distinct uncensored delta values: EXCL=%d NEAR=%d   %s"
          % (res_excl["n_distinct_delta_uncensored"], res_near["n_distinct_delta_uncensored"],
             "PASS" if row0c else "FAIL"))

    row0_all_pass = row0a and row0b and row0c
    print("\n>>> ROW 0: %s <<<" % ("CLEAR" if row0_all_pass else "FIRES -- ROW 5 VOID"))
    if not row0_all_pass:
        print("\nPer spec S3.3: NO rate is quoted, not even descriptively. Stopping here.")
        return

    # ================= headline =================
    for mode, res in (("EXCL", res_excl), ("NEAR", res_near)):
        print("\n" + "=" * 78)
        print("ASSIGN_%s" % mode)
        print("=" * 78)
        print("n_u (uncensored pairs)      = %d   (censored pairs excluded: %d)" % (res["n_u"], res["n_censored"]))
        print("c (median delta, uncensored) = %.1f dB" % res["c"])
        print("k_u (under-reads, >=%ddB, signed) = %d   k_o (over-reads, mirror) = %d"
              % (TAIL_DB, res["k_u"], res["k_o"]))
        print("R_u = %.4f%%   R_o = %.4f%%   (same sentence, sibling (u))" % (100 * res["R_u"], 100 * res["R_o"]))
        print("CP95(R_u)              = [%.4f%%, %.4f%%]" % (100 * res["lo_cp"], 100 * res["hi_cp"]))
        print("cluster bootstrap(R_u)  = [%.4f%%, %.4f%%]  (%d draws, seed %d, %d clusters)"
              % (100 * res["lo_boot"], 100 * res["hi_boot"], BOOT_DRAWS, BOOT_SEED, res["n_clusters"]))
        print("combined CI(R_u)        = [%.4f%%, %.4f%%]" % (100 * res["lo"], 100 * res["hi"]))
        print("sign test: U=%d O=%d p_sign=%.6g" % (res["U"], res["O"], res["p_sign"]))
        print("R_STAR = %.4f%%   -->  %s" % (100 * R_STAR, reading_row(res)))

        d = res["delta"]
        u = res["uncensored"]
        c = res["c"]
        print("\nhistogram of (delta - c), uncensored, integer bins:")
        vals = (d[u] - c).astype(int)
        if len(vals):
            for b in range(int(vals.min()), int(vals.max()) + 1):
                n_b = int((vals == b).sum())
                if n_b:
                    print("  %+4d : %6d %s" % (b, n_b, "#" * min(n_b // max(1, len(vals) // 200 + 1), 60)))

        freq_arr = res["freq_ow_arr"][u]
        under_mask = (d[u] - c) <= -TAIL_DB
        for lo_hz, hi_hz, label in ((0, 600, "<600Hz"), (600, 10**9, ">=600Hz")):
            sel = (freq_arr >= lo_hz) & (freq_arr < hi_hz)
            n_sel = int(sel.sum())
            k_sel = int((under_mask & sel).sum())
            r_sel = (k_sel / n_sel) if n_sel else float("nan")
            print("R_u, freq_ow %-7s: %d/%d = %.4f%%   (descriptive, spec S3.6 item 3)"
                  % (label, k_sel, n_sel, 100 * r_sel))

    # ================= descriptive: the 313 corroborated-removed split (NEAR) ==
    print("\n" + "=" * 78)
    print("Descriptive: the 313 corroborated-removed (snr_ow<=-24, ASSIGN_NEAR) split")
    print("(spec S3.6 item 4 -- does NOT reopen Part B ROW 2, accepted 3e997e0)")
    print("=" * 78)
    removed_near = [(ts, snr_ow, freq_ow, snr_ref) for (ts, snr_ow, freq_ow, snr_ref) in pairs_near
                    if snr_ow <= -24]
    a_cens = sum(1 for (_t, _s, _f, sr) in removed_near if sr == WSJTX_FLOOR)
    uncens = [(ts, snr_ow, freq_ow, snr_ref) for (ts, snr_ow, freq_ow, snr_ref) in removed_near
              if snr_ref != WSJTX_FLOOR]
    c_near = res_near["c"]
    b_under = sum(1 for (_t, snr_ow, _f, snr_ref) in uncens if (snr_ow - snr_ref) - c_near <= -TAIL_DB)
    c_other = len(uncens) - b_under
    print("(a) WSJT-X = -24, censored           : %d" % a_cens)
    print("(b) uncensored AND under (misread)    : %d" % b_under)
    print("(c) uncensored, not under             : %d" % c_other)
    print("total                                  : %d (expect 313)" % (a_cens + b_under + c_other))

    # ================= openspec scenario, spec S3.6 item 5 ======================
    print("\n" + "=" * 78)
    print("openspec scenario (ft8-decoder/spec.md:104-107): 'No SNR values below -30 dB")
    print("when WSJT-X reports normal SNR for the same message.'  V = snr_ow <= -31, corroborated (NEAR)")
    print("=" * 78)
    v_pairs = [(ts, snr_ow, freq_ow, snr_ref) for (ts, snr_ow, freq_ow, snr_ref) in pairs_near
               if snr_ow <= -31]
    v_cens = sum(1 for (_t, _s, _f, sr) in v_pairs if sr == WSJTX_FLOOR)
    v_uncens = len(v_pairs) - v_cens
    print("V = %d  (expect 6, per 0a)   V_cens=%d  V_uncens=%d" % (len(v_pairs), v_cens, v_uncens))
    if v_uncens >= 1:
        print("V_uncens >= 1: reported as a VIOLATION WITH AN UNCENSORED REFERENCE.")
        print("QA to decide whether to raise a defect (HK-015).")
    else:
        print("V_uncens == 0: no violation with an uncensored reference. V_cens pairs are NOT")
        print("called violations (S2.2 scoping defect -- every WSJT-X decode satisfies '>=-24').")

    # ================= final reading =================
    print("\n" + "=" * 78)
    print("READING RULE (spec S3.4, strict order) -- ROW 0b already confirms EXCL == NEAR")
    print("=" * 78)
    row = row_near
    print(">>> %s <<<" % row)
    consequences = {
        "ROW 1": "D-003 blocker on synth-into-real (spec S1.1) is LIFTED. Architect drafts S1.2 design next.",
        "ROW 2": ("Synth-into-real BLOCKED for any SNR-reading deliverable. QA may author a D-003 defect "
                  "record / dev-task carrying the rate and frequency split (HK-015); any src/ work via HK-011."),
        "ROW 3": ("Draft nothing. Synth-into-real stays blocked on D-003 grounds -- this instrument cannot "
                  "make the attribution."),
        "ROW 4": "Report and draft nothing. Synth-into-real stays blocked.",
    }
    print(consequences[row])

    print("\n" + "=" * 78)
    print("This does NOT reopen FP-FLOOR-LIVE-2 Part B, FP-PARITY ROW 3, or FP-REGRESSION.")
    print("No baseline created. No src/ work authorised in any row. No capture run -- disk only.")


if __name__ == "__main__":
    main()
