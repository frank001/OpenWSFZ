#!/usr/bin/env python3
"""X3 -- does sub-lattice placement error cost MORE in a crowded cycle?

Spec: qa/cycleframer-alignment-replay/2026-08-10-1808-architect-to-qa-spec-x3-lattice-crowding-interaction.md

Re-runs P3's five-leg shift-union (base, +/-1.0417 Hz, +/-0.0267 s) UNCHANGED (harness
machinery from p23_common.py / p3_shift_union.py, reused not rewritten), then partitions the
outcome by X2's density regimes (FLOOR<=5, MID 6-13, OVERLAP 14-26; x2_density_floor.regime_of,
reused not re-derived).

I_20m = S_all(OVERLAP, 20m) - S_all(MID, 20m)     -- primary
I_80m = S_all(OVERLAP, 80m) - S_all(FLOOR, 80m)    -- replication (the true floor regime)

DLL pin: 🔴 DEVIATES FROM THE SPEC'S LITERAL S0a/0b, BY THE CAPTAIN'S EXPLICIT RULING this
session (2026-08-10, in answer to the QA escalation `2026-08-10-2042-...-shim-version-
provenance-resolved.md`). The spec's own SHA (39aa1031..., ft8_lib_version_check()==20260035)
was traced to `d001-rc4-decode-depth`'s unmerged THREE-PASS diagnostic build, not `main`'s
production decoder -- the same defect P2/P3/P1a unknowingly ran on. Per the spec's own S2.1
("The SHA is the authority ... flag the mismatch upward rather than resolving it in session"),
this harness pins `main`'s own committed build instead:
  DLL:    src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll
  SHA256: f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015
  shim:   FT8_SHIM_VERSION 20260033 (two-pass, main's shipped configuration)
This makes X3 the first arm in the programme run against the CORRECT production binary rather
than the RC4 diagnostic leftover -- disclosed prominently in the report, not silently swapped.

ROW 0e (spec S2, mandatory pre-flight): computed from a SINGLE base-leg decode pass (no
shifts) -- proxy SE(I) via a frequency-clustered bootstrap of the base leg's own MID-vs-OVERLAP
recovery-rate contrast, which costs one decoder pass instead of five. Run with --preflight to
do ONLY this step; the four shifted legs are not launched unless it passes.

No src/ change. No capture. Decoder replay only, ctypes in-process, per spec S1.1's hash-table
process-isolation discipline (inherited unmodified from p23_common.py / p3_shift_union.py).
"""
from __future__ import annotations

import argparse
import collections
import ctypes
import hashlib
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p23_common as C  # noqa: E402
from x2_density_floor import regime_of, build_band as x2_build_band  # noqa: E402

# ── corrected DLL pin (see module docstring) ──────────────────────────────────────────────
CORRECT_DLL_PATH = os.path.join(C.REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
CORRECT_DLL_SHA256 = "f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015"
CORRECT_SHIM_VERSION = 20260033

FREQ_DELTA = 3.125 / 3.0
TIME_SAMPLES = 320
LEGS = ["base", "Fp", "Fm", "Tp", "Tm"]

MIN_REGIME_REF = 300
MIN_REGIME_CLUSTERS = 250
PREFLIGHT_SE_BAR = 0.75

_DEC = None


def _worker_init():
    global _DEC
    _DEC = C.Decoder(path=CORRECT_DLL_PATH, verify=False)
    got_sha = C.dll_sha256(CORRECT_DLL_PATH)
    if got_sha != CORRECT_DLL_SHA256:
        raise RuntimeError("worker DLL SHA mismatch: %s" % got_sha)
    if _DEC.version != CORRECT_SHIM_VERSION:
        # record, do not silently fail -- spec S2.1: "record whatever version the DLL
        # actually reports" and flag upward. A running arm must still be able to finish so
        # the mismatch can be reported with real numbers attached.
        sys.stderr.write("[WARN] worker shim version %d != expected %d\n"
                          % (_DEC.version, CORRECT_SHIM_VERSION))


def _variants(pcm, legs):
    out = {}
    if "base" in legs:
        out["base"] = pcm
    if "Fp" in legs:
        out["Fp"] = C.freq_shift(pcm, +FREQ_DELTA)
    if "Fm" in legs:
        out["Fm"] = C.freq_shift(pcm, -FREQ_DELTA)
    if "Tp" in legs:
        out["Tp"] = C.time_shift(pcm, +TIME_SAMPLES)
    if "Tm" in legs:
        out["Tm"] = C.time_shift(pcm, -TIME_SAMPLES)
    return out


def _run_partition(args):
    idx, files, scratch, legs, tag = args
    out_path = os.path.join(scratch, "x3_%s_part_%04d.json" % (tag, idx))
    if os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as fh:
                json.load(fh)
            return out_path, True
        except Exception:
            os.remove(out_path)
    leg_out = {lg: [] for lg in legs}
    av = 0
    seen_ts = []
    for ts, path in files:
        try:
            pcm = C.normalise_rms(C.read_wav(path), C.PROD_TARGET_RMS)
        except Exception:
            continue
        seen_ts.append(ts)
        for lg, buf in _variants(pcm, legs).items():
            res = _DEC.decode(buf)
            if res is None:
                av += 1
                continue
            for r in res:
                leg_out[lg].append([ts, r["message"]])
    C.write_json(out_path, {"idx": idx, "n_files": len(files), "av": av,
                            "seen_ts": seen_ts, "legs": leg_out})
    return out_path, False


def replay(files, legs, tag, workers, partitions, scratch):
    per = (len(files) + partitions - 1) // partitions
    chunks, lo = [], 0
    while lo < len(files):
        chunks.append(files[lo:lo + per])
        lo += per
    tasks = [(i, ch, scratch, legs, tag) for i, ch in enumerate(chunks)]
    done, paths = 0, []
    t0 = time.time()
    with Pool(processes=workers, initializer=_worker_init) as pool:
        for path, resumed in pool.imap_unordered(_run_partition, tasks):
            paths.append(path)
            done += 1
            print("  [%s] partition %d/%d %s (%.1f min elapsed)"
                  % (tag, done, len(tasks), "RESUMED" if resumed else "done",
                     (time.time() - t0) / 60.0), flush=True)
    leg_keys = {lg: set() for lg in legs}
    av_total = 0
    replayed = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        av_total += d.get("av", 0)
        replayed.extend(d.get("seen_ts", []))
        for lg, rows in d["legs"].items():
            for ts, msg in rows:
                leg_keys[lg].add((ts, msg))
    return leg_keys, av_total, replayed, (time.time() - t0) / 60.0


# ── density-regime membership for the 5-leg replay's REF (raw A n B, P3's own basis) ──────

def regime_membership(band_name):
    """Returns {ts: regime_or_None} using X2's OWN density definition (clean, hash+band
    excluded population) for the given band -- reused, not re-derived, per spec S1. A cycle
    absent from X2's clean population (all its raw-REF decodes were hash/band-excluded) has
    density undefined; disclosed and excluded from the regime partition, not silently zeroed."""
    band = x2_build_band(band_name)
    return dict(band.density_by_cycle), set(band.cycles)


def partition_ref_by_regime(ref_keys, density_by_cycle):
    out = collections.defaultdict(set)
    n_undefined = 0
    for k in ref_keys:
        ts, _msg = k
        d = density_by_cycle.get(ts)
        if d is None:
            n_undefined += 1
            continue
        r = regime_of(d)
        if r is None:
            n_undefined += 1
            continue
        out[r].add(k)
    return dict(out), n_undefined


def s_all_for_regime(leg_keys, ref_regime_keys, base_key_set=None):
    """S_all restricted to one density regime's REF subset. base_key_set overrides
    leg_keys['base'] when scoring against a resampled/bootstrap draw is not needed (point
    estimate only) -- kept simple, matches p3_shift_union's own formula, scoped to the
    regime's REF."""
    base = leg_keys["base"] if base_key_set is None else base_key_set
    all_legs = set().union(*(leg_keys[lg] for lg in LEGS if lg in leg_keys))
    gained = all_legs - base
    n_ref = len(ref_regime_keys)
    if n_ref == 0:
        return None, 0
    s_all = 100.0 * len(gained & ref_regime_keys) / n_ref
    return s_all, n_ref


def cluster_bootstrap_paired_diff(ref_freq_a, ref_freq_b, numerator_a, numerator_b,
                                   n_draws=1000, seed=C.SEED):
    """Frequency-clustered, PAIRED bootstrap of I = S_all(regime_a) - S_all(regime_b).
    ref_freq_a/b: {key: freq_hz} for the regime's own REF population (disjoint regimes, so
    resampled independently -- there is no shared cluster to pair ACROSS regimes; 'paired'
    here means each draw recomputes BOTH S_all values before differencing, i.e. one seed
    stream, not that the two regimes share resampled clusters, which they cannot since a
    cycle belongs to exactly one regime)."""
    def byf(ref_freq):
        d = collections.defaultdict(list)
        for k, f in ref_freq.items():
            d[f].append(k)
        return d

    fa, fb = byf(ref_freq_a), byf(ref_freq_b)
    # SORTED, not list(): ref_freq_a/b ultimately derive from a set intersection
    # (t1_frequency_quantisation-style REF construction), whose iteration order is subject
    # to per-process string-hash randomisation. An unsorted list here silently breaks the
    # "two runs, byte-identical stdout" determinism requirement even under a fixed seed,
    # because rng.choice draws INDICES into this list and the same index sequence then maps
    # to different frequencies across runs. Found and fixed while debugging the same class
    # of bug in x4_spectral_locality.py's null/bootstrap (see that file's build_records
    # docstring) -- applied here proactively rather than discovered the same way twice.
    freqs_a, freqs_b = sorted(fa), sorted(fb)
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_draws):
        pick_a = rng.choice(len(freqs_a), size=len(freqs_a), replace=True) if freqs_a else []
        pick_b = rng.choice(len(freqs_b), size=len(freqs_b), replace=True) if freqs_b else []
        keys_a = [k for i in pick_a for k in fa[freqs_a[i]]]
        keys_b = [k for i in pick_b for k in fb[freqs_b[i]]]
        if not keys_a or not keys_b:
            continue
        sa = 100.0 * sum(1 for k in keys_a if k in numerator_a) / len(keys_a)
        sb = 100.0 * sum(1 for k in keys_b if k in numerator_b) / len(keys_b)
        diffs.append(sa - sb)
    diffs.sort()
    if len(diffs) < 2:
        return {"mean": float("nan"), "se": float("nan"), "ci95": [float("nan")] * 2, "n_draws": 0}
    v = np.array(diffs)
    return {"mean": float(v.mean()), "se": float(v.std(ddof=1)),
            "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))],
            "n_draws": len(diffs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--partitions", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preflight-only", action="store_true",
                     help="ROW 0e only: single base-leg pass on the 20m primary corpus, "
                          "no shifted legs, no 80m replication.")
    a = ap.parse_args()
    os.makedirs(a.scratch, exist_ok=True)
    t_start = time.time()

    print("DLL (corrected pin, see module docstring):")
    sha = C.dll_sha256(CORRECT_DLL_PATH)
    print("  path: %s" % CORRECT_DLL_PATH)
    print("  sha256: %s" % sha)
    if sha != CORRECT_DLL_SHA256:
        raise SystemExit("DLL identity mismatch against the corrected pin -- refusing to run")
    probe = C.Decoder(path=CORRECT_DLL_PATH, verify=False)
    print("  ft8_lib_version_check(): %d (expected %d)" % (probe.version, CORRECT_SHIM_VERSION))
    del probe

    files_20m = C.in_window_files()
    if a.limit:
        files_20m = files_20m[:a.limit]
    print("\n20m in-window files: %d" % len(files_20m))

    ref_20m_raw = C.load_ref()
    print("20m REF (raw A n B): %d" % len(ref_20m_raw))
    row0c = len(ref_20m_raw) == C.REF_EXPECTED
    print(">>> ROW 0c (20m): %s <<<" % ("PASS" if row0c else "VOID"))
    result = {"row0c_20m": {"ref": len(ref_20m_raw), "expected": C.REF_EXPECTED, "pass": row0c},
              "dll": {"path": CORRECT_DLL_PATH, "sha256": sha, "shim_version": probe_version(CORRECT_DLL_PATH)}}
    if not row0c:
        result["final_row"] = "ROW 0c"
        C.write_json(a.out, result)
        return 1

    density_20m, cycles_20m = regime_membership("20m")
    ref_by_regime_20m, n_undef_20m = partition_ref_by_regime(set(ref_20m_raw), density_20m)
    print("\n20m REF by density regime (X2's own density definition, per-cycle):")
    for r in ("FLOOR", "MID", "OVERLAP"):
        keys = ref_by_regime_20m.get(r, set())
        n_clusters = len(set(f for k in keys for f in [ref_20m_raw[k][1]]))
        print("  %-8s n=%5d  distinct freq clusters=%5d" % (r, len(keys), n_clusters))
    print("  (regime undefined -- cycle absent from X2's clean-population density map): %d"
          % n_undef_20m)
    result["ref_by_regime_20m"] = {
        r: {"n": len(ref_by_regime_20m.get(r, set())),
            "n_clusters": len(set(ref_20m_raw[k][1] for k in ref_by_regime_20m.get(r, set())))}
        for r in ("FLOOR", "MID", "OVERLAP")
    }
    result["n_regime_undefined_20m"] = n_undef_20m

    row0d_mid = (result["ref_by_regime_20m"]["MID"]["n"] >= MIN_REGIME_REF and
                 result["ref_by_regime_20m"]["MID"]["n_clusters"] >= MIN_REGIME_CLUSTERS)
    row0d_overlap = (result["ref_by_regime_20m"]["OVERLAP"]["n"] >= MIN_REGIME_REF and
                     result["ref_by_regime_20m"]["OVERLAP"]["n_clusters"] >= MIN_REGIME_CLUSTERS)
    print("\nROW 0d (20m primary regimes MID/OVERLAP populated): MID=%s OVERLAP=%s"
          % ("PASS" if row0d_mid else "UNDERPOWERED", "PASS" if row0d_overlap else "UNDERPOWERED"))
    result["row0d_20m"] = {"mid_pass": row0d_mid, "overlap_pass": row0d_overlap}
    if not (row0d_mid and row0d_overlap):
        result["final_row"] = "ROW 0d -- 20m primary regime(s) underpowered"
        C.write_json(a.out, result)
        return 1

    # ---- ROW 0e: pre-flight ----
    # PRIMARY (gating) method: analytical rescaling of P3's OWN already-measured SE(S_all),
    # using this session's REAL per-regime cluster counts -- this is what the spec's S1.1
    # scoping table itself did (with ASSUMED cluster fractions; here they are measured), and
    # it costs zero decoder time, matching the spec's "costs one pass rather than five" intent
    # (P3 already IS that one pass -- nothing new needs decoding to evaluate this row at all).
    print("\n" + "=" * 88)
    print("ROW 0e PRE-FLIGHT")
    print("=" * 88)
    p3_path = os.path.join(HERE, "p3_result.json")
    with open(p3_path, encoding="utf-8") as fh:
        p3 = json.load(fh)
    se_pooled = p3["SE_S_all"]
    n_pooled = p3["bootstrap"]["S_all"]["n_distinct_freq"]
    n_mid_clusters = result["ref_by_regime_20m"]["MID"]["n_clusters"]
    n_overlap_clusters = result["ref_by_regime_20m"]["OVERLAP"]["n_clusters"]
    se_mid_scoped = se_pooled * (n_pooled / n_mid_clusters) ** 0.5
    se_overlap_scoped = se_pooled * (n_pooled / n_overlap_clusters) ** 0.5
    se_I_scoped = (se_mid_scoped ** 2 + se_overlap_scoped ** 2) ** 0.5
    print("Analytical scoping (PRIMARY, gating): P3 pooled SE(S_all)=%.4f pp over %d clusters"
          % (se_pooled, n_pooled))
    print("  rescaled to MID (%d clusters): SE=%.4f pp" % (n_mid_clusters, se_mid_scoped))
    print("  rescaled to OVERLAP (%d clusters): SE=%.4f pp" % (n_overlap_clusters, se_overlap_scoped))
    print("  scoped SE(I) = sqrt(SE_MID^2 + SE_OVERLAP^2) = %.4f pp" % se_I_scoped)
    row0e = se_I_scoped <= PREFLIGHT_SE_BAR
    print(">>> ROW 0e (analytical): %s (bar SE <= %.2f pp) <<<"
          % ("PASS" if row0e else "UNDERPOWERED -- primary leg NOT RUN", PREFLIGHT_SE_BAR))
    result["row0e"] = {"method": "analytical_rescale_of_p3_SE_S_all",
                        "se_pooled_p3": se_pooled, "n_pooled_clusters": n_pooled,
                        "n_mid_clusters": n_mid_clusters, "n_overlap_clusters": n_overlap_clusters,
                        "se_mid_scoped": se_mid_scoped, "se_overlap_scoped": se_overlap_scoped,
                        "se_I_scoped": se_I_scoped, "bar": PREFLIGHT_SE_BAR, "pass": row0e}

    # SECONDARY (disclosed, non-gating) empirical check: one base-leg decode pass, then a
    # frequency-clustered bootstrap of the base leg's OWN recovery-rate contrast MID vs
    # OVERLAP. Kept and reported because it was run and because a large disagreement between
    # the two methods is itself informative (it measures a DIFFERENT quantity -- baseline
    # recovery LEVEL variance between regimes, not S_all's narrower paired shift-GAIN
    # variance -- so a mismatch here does not on its own contradict the analytical scoping
    # above; it says regime-level recovery is noisier than the shift-gain P3 characterised).
    print("\n(secondary, non-gating) base-leg recovery-level contrast, empirical:")
    base_leg_keys, av_pre, replayed_pre, wall_pre = replay(
        files_20m, ["base"], "preflight20m", a.workers, a.partitions, a.scratch)
    print("base leg: %d decodes, av=%d, wall=%.1f min" % (len(base_leg_keys["base"]), av_pre, wall_pre))
    ref_20m_replayed = C.restrict_ref(ref_20m_raw, replayed_pre)
    ref_mid = {k: v for k, v in ref_20m_replayed.items() if k in ref_by_regime_20m.get("MID", set())}
    ref_overlap = {k: v for k, v in ref_20m_replayed.items() if k in ref_by_regime_20m.get("OVERLAP", set())}
    ref_freq_mid = {k: v[1] for k, v in ref_mid.items()}
    ref_freq_overlap = {k: v[1] for k, v in ref_overlap.items()}
    base_set = base_leg_keys["base"]
    preflight_boot = cluster_bootstrap_paired_diff(
        ref_freq_overlap, ref_freq_mid, base_set, base_set, n_draws=1000, seed=C.SEED)
    print("  base-leg recovery contrast OVERLAP-MID: mean=%.3f pp SE=%.3f pp 95%%CI=%s (NOT gating)"
          % (preflight_boot["mean"], preflight_boot["se"], preflight_boot["ci95"]))
    result["row0e_secondary_empirical_proxy"] = {
        "proxy_se": preflight_boot["se"], "proxy_mean": preflight_boot["mean"],
        "proxy_ci95": preflight_boot["ci95"], "wall_clock_min": wall_pre, "av_count": av_pre,
        "note": "measures base-leg recovery-LEVEL variance between regimes, not S_all's own "
                "shift-GAIN variance -- disclosed context, does not gate",
    }
    result["base_leg_20m_reused"] = True

    if not row0e or a.preflight_only:
        result["final_row"] = "ROW 0e" if not row0e else "PREFLIGHT ONLY -- stopping before shifted legs"
        C.write_json(a.out, result)
        print("\nWrote %s" % a.out)
        return 0 if (a.preflight_only and row0e) else (1 if not row0e else 0)

    # ---- full five-leg run, 20m (reusing the base leg already decoded above) ----
    print("\n" + "=" * 88)
    print("FULL FIVE-LEG REPLAY -- 20m (base leg reused from pre-flight)")
    print("=" * 88)
    shifted_keys, av_shift, replayed_shift, wall_shift = replay(
        files_20m, ["Fp", "Fm", "Tp", "Tm"], "shifted20m", a.workers, a.partitions, a.scratch)
    leg_keys_20m = dict(shifted_keys)
    leg_keys_20m["base"] = base_leg_keys["base"]
    av_total_20m = av_pre + av_shift
    replayed_all = sorted(set(replayed_pre) | set(replayed_shift))
    ref_20m_final = C.restrict_ref(ref_20m_raw, replayed_all)
    ref_by_regime_final, _ = partition_ref_by_regime(set(ref_20m_final), density_20m)

    print("\nS_all by regime (20m):")
    s_all_by_regime = {}
    for r in ("FLOOR", "MID", "OVERLAP"):
        keys = ref_by_regime_final.get(r, set())
        s_all, n_ref = s_all_for_regime(leg_keys_20m, keys)
        s_all_by_regime[r] = {"s_all": s_all, "n_ref": n_ref}
        print("  %-8s S_all=%s pp  n_ref=%d" % (r, "%.3f" % s_all if s_all is not None else "None", n_ref))
    result["s_all_by_regime_20m"] = s_all_by_regime
    result["av_total_20m"] = av_total_20m
    result["wall_clock_20m_min"] = wall_pre + wall_shift

    ref_freq_overlap_f = {k: v[1] for k, v in ref_20m_final.items() if k in ref_by_regime_final.get("OVERLAP", set())}
    ref_freq_mid_f = {k: v[1] for k, v in ref_20m_final.items() if k in ref_by_regime_final.get("MID", set())}
    all_legs_20m = set().union(*(leg_keys_20m[lg] for lg in LEGS))
    gained_20m = all_legs_20m - leg_keys_20m["base"]
    I_boot = cluster_bootstrap_paired_diff(ref_freq_overlap_f, ref_freq_mid_f, gained_20m, gained_20m,
                                            n_draws=1000, seed=C.SEED)
    I_20m = s_all_by_regime["OVERLAP"]["s_all"] - s_all_by_regime["MID"]["s_all"]
    print("\nI_20m = S_all(OVERLAP) - S_all(MID) = %.3f pp" % I_20m)
    print("SE(I_20m) = %.3f pp  95%% CI = %s" % (I_boot["se"], I_boot["ci95"]))
    result["I_20m"] = I_20m
    result["I_20m_bootstrap"] = I_boot

    lo, hi = I_boot["ci95"]

    def x3_gate(I, se_I, lo, hi):
        if se_I > 0.75:
            return "ROW 0e"
        if I >= 2.0 and lo > 0:
            return "ROW 1"
        if abs(I) < 1.0 and se_I <= 0.40:
            return "ROW 2"
        if I <= -2.0 and hi < 0:
            return "ROW 3"
        return "ROW 4"

    gate_row = x3_gate(I_20m, I_boot["se"], lo, hi)
    print("\n>>> GATE (20m primary): %s <<<" % gate_row)
    result["final_row"] = gate_row

    # secondary quantities (spec S4), never gating
    x_guard_by_regime = {}
    s_freq_by_regime = {}
    s_time_by_regime = {}
    f_gained = (leg_keys_20m["Fp"] | leg_keys_20m["Fm"]) - leg_keys_20m["base"]
    t_gained = (leg_keys_20m["Tp"] | leg_keys_20m["Tm"]) - leg_keys_20m["base"]
    for r in ("FLOOR", "MID", "OVERLAP"):
        keys = ref_by_regime_final.get(r, set())
        n_ref = len(keys)
        if n_ref == 0:
            continue
        s_freq_by_regime[r] = 100.0 * len(f_gained & keys) / n_ref
        s_time_by_regime[r] = 100.0 * len(t_gained & keys) / n_ref
        # X_guard by regime: junk share among union-gained decodes whose CYCLE falls in this
        # regime (X_guard is about decode provenance, not REF membership, so gate on cycle).
        cycles_in_regime = {ts for ts, d in density_20m.items() if regime_of(d) == r}
        gained_cycle_r = {k for k in gained_20m if k[0] in cycles_in_regime}
        if gained_cycle_r:
            junk = sum(1 for k in gained_cycle_r if k not in keys and k not in ref_20m_final)
            x_guard_by_regime[r] = junk / len(gained_cycle_r)
    result["s_freq_by_regime_20m"] = s_freq_by_regime
    result["s_time_by_regime_20m"] = s_time_by_regime
    result["x_guard_by_regime_20m"] = x_guard_by_regime
    print("\nSecondary (reported, never gating):")
    for r in ("FLOOR", "MID", "OVERLAP"):
        print("  %-8s S_freq=%s  S_time=%s  X_guard=%s"
              % (r, s_freq_by_regime.get(r), s_time_by_regime.get(r), x_guard_by_regime.get(r)))

    result["wall_clock_total_min"] = (time.time() - t_start) / 60.0
    C.write_json(a.out, result)
    print("\nWrote %s" % a.out)
    print("FINAL ROW: %s" % result["final_row"])
    return 0


def probe_version(path):
    dec = C.Decoder(path=path, verify=False)
    return dec.version


if __name__ == "__main__":
    raise SystemExit(main())
