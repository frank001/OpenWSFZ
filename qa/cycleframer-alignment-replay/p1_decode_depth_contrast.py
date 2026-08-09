#!/usr/bin/env python3
"""P1 -- how much of the D-001 gap is decode DEPTH rather than capability?

Spec: qa/cycleframer-alignment-replay/2026-08-08-2357-architect-to-qa-spec-p1-decode-depth-contrast.md

Offline jt9 -d1 vs -d3 replay of WSJT-X FT991A's own WAVs, 20m clean window.
No src/ change, no capture, no rebuild, no WSJT-X reconfiguration.
NFR-021: counts and rates only -- no message text or callsign in any output file.

Method:
  1. Timing probe: 20 files at each depth, wall-clock, extrapolate to the full
     2 748-ish in-window population. <=90 min -> full window. >90 min -> a
     pre-registered random subsample of 1000 cycles, seed recorded before any
     decode output is inspected.
  2. Decode every processed file at both depths via jt9.exe, parse stdout,
     dedupe (ts, message) exactly as Angle 1's N4 requires (report raw+dedup).
  3. REF = intersection of the two WSJT-X instances (T1/T2/H1's 69 222
     denominator), restricted to cycles actually replayed. MISS = REF minus
     OpenWSFZ 8080. D1/D3 = deduped jt9 sets at each depth.
  4. A = |MISS ^ (D3\\D1)| / |REF| (pp), frequency-clustered bootstrap CI.
     B = |D3\\D1|/|D1| raw yield. C = |D1 ^ REF|/|REF| context.
  5. Pre-registered ROW 0a-d instrument gate, then the A-gate (ROW1/2/3).

NFR-021 note: this harness never writes a callsign or message body to any
file under version control. jt9's own stdout (transient, scratch dir only)
necessarily contains message text; nothing from it is copied into the JSON
result or the committed report beyond counts.
"""
import argparse
import io
import json
import os
import random
import re
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_frequency_quantisation import load, WINDOW_20M, LEG_20M  # noqa: E402

JT9_EXE = r"D:/WSJT/wsjtx/bin/jt9.exe"
WAV_DIR = "artefacts/20260808_live_run_0016-8080/wsjt-x/wav/"
DATE_PREFIX = "260808_"

MARKER_RE = re.compile(r"^[a-f]\d+$")


def in_window_files(window):
    lo, hi = window
    files = []
    for name in sorted(os.listdir(WAV_DIR)):
        if not name.endswith(".wav"):
            continue
        ts = DATE_PREFIX + name[len(DATE_PREFIX):-4]  # e.g. 260808_004000
        if lo <= ts <= hi:
            files.append((ts, os.path.abspath(os.path.join(WAV_DIR, name))))
    return files


def parse_jt9_stdout(text):
    """Yield (message,) for each decode line. ts is NOT read from the line
    (jt9 prints only HHMMSS with no date and it is redundant -- the caller
    already knows which file/ts produced this stdout)."""
    out = []
    for line in text.splitlines():
        if "~" not in line:
            continue
        if "<DecodeFinished>" in line:
            continue
        after = line.split("~", 1)[1]
        toks = after.split()
        while toks and (toks[-1] == "?" or MARKER_RE.match(toks[-1])):
            toks.pop()
        if not toks:
            continue
        out.append(" ".join(toks))
    return out


def _decode_one(path, depth, cwd):
    r = subprocess.run(
        [JT9_EXE, "-8", "-d", str(depth), path],
        cwd=cwd, capture_output=True, text=True, timeout=120,
    )
    return parse_jt9_stdout(r.stdout)


def run_jt9(files, depth, scratch_root, workers=1):
    """files: list of (ts, absolute wav path). Returns dict ts -> list[message]
    (raw, may contain duplicates -- N4). Pure execution-speed parallelism: each
    file is decoded independently, so the RESULT is identical regardless of
    `workers` -- only wall-clock changes. workers>1 assigns each in-flight jt9
    call its own scratch subdirectory (a small mutual-exclusion pool) so
    concurrent processes never race on the same jt9_wisdom.dat/timer.out."""
    if workers <= 1:
        return {ts: _decode_one(path, depth, scratch_root) for ts, path in files}

    import queue as queue_mod
    dir_pool = queue_mod.Queue()
    for i in range(workers):
        d = os.path.join(scratch_root, "w%d" % i)
        os.makedirs(d, exist_ok=True)
        dir_pool.put(d)

    def task(ts, path):
        d = dir_pool.get()
        try:
            return ts, _decode_one(path, depth, d)
        finally:
            dir_pool.put(d)

    per_file = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(task, ts, path) for ts, path in files]
        for fut in as_completed(futs):
            ts, msgs = fut.result()
            per_file[ts] = msgs
    return per_file


def timed_probe(files, depth, scratch_root, workers=1):
    t0 = time.time()
    per_file = run_jt9(files, depth, scratch_root, workers)
    dt = time.time() - t0
    return dt, per_file


def to_keyset(per_file):
    """per_file: ts -> [msg, msg, ...] (raw, with dupes). Returns (raw_count,
    dedup_keyset)."""
    raw = 0
    keys = set()
    for ts, msgs in per_file.items():
        raw += len(msgs)
        for m in msgs:
            keys.add((ts, m))
    return raw, keys


def cluster_bootstrap_A(ref_freq, in_numerator, n_draws, seed):
    """ref_freq: dict key -> freq_hz for every key in REF.
    in_numerator: set of keys in MISS ^ (D3\\D1).
    Frequency-clustered bootstrap over distinct REF frequencies (HK-021(i)):
    resample distinct frequencies with replacement, recompute A on the
    resampled multiset of REF rows each draw."""
    byf = {}
    for k, f in ref_freq.items():
        byf.setdefault(f, []).append(k in in_numerator)
    freqs = list(byf)
    rng = random.Random(seed)
    samp = []
    for _ in range(n_draws):
        pick = [rng.choice(freqs) for _ in freqs]
        tot = ok = 0
        for f in pick:
            v = byf[f]
            tot += len(v)
            ok += sum(v)
        samp.append(100.0 * ok / tot if tot else 0.0)
    mu = sum(samp) / len(samp)
    se = statistics.stdev(samp) if len(samp) > 1 else float("nan")
    s = sorted(samp)
    lo_i = int(0.025 * len(s))
    hi_i = int(0.975 * len(s)) - 1
    return {
        "n_distinct_freq": len(freqs),
        "n_draws": n_draws,
        "seed": seed,
        "bootstrap_mean": mu,
        "bootstrap_se": se,
        "ci95_pct": [s[lo_i], s[hi_i]],
    }


def p1_row0(n1_raw, n1_dedup, n3_raw, n3_dedup, ratio_d3_live, n_cycles):
    if n_cycles < 800:
        return "ROW 0a", "n_cycles=%d < 800" % n_cycles
    if n3_dedup == n1_dedup:
        return "ROW 0b", "n3_dedup == n1_dedup == %d" % n1_dedup
    if not (0.90 <= ratio_d3_live <= 1.40):
        return "ROW 0c", "ratio_d3_live=%.4f outside [0.90, 1.40]" % ratio_d3_live
    if n1_raw == n1_dedup and n3_raw == n3_dedup:
        return "ROW 0d", "dedup removed nothing on either leg (n1 %d==%d, n3 %d==%d)" % (
            n1_raw, n1_dedup, n3_raw, n3_dedup)
    return None, None


def p1_gate(a):
    if a >= 5.0:
        return "ROW 1"
    if a <= 1.5:
        return "ROW 2"
    return "ROW 3"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-n", type=int, default=20)
    ap.add_argument("--time-budget-min", type=float, default=90.0)
    ap.add_argument("--subsample-n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260809)
    ap.add_argument("--boot-draws", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=1,
                     help="parallel jt9 processes; execution-speed only, does not "
                          "affect decode results (each file is independent)")
    ap.add_argument("--smoke-test", type=int, default=0,
                     help="if >0, override everything and just process this many files "
                          "(chronological) at both depths -- mechanics check only, not the gate")
    ap.add_argument("--out", default="p1_result.json")
    args = ap.parse_args()

    scratch = tempfile.mkdtemp(prefix="p1_jt9_")
    print("scratch dir: %s" % scratch)

    all_files = in_window_files(WINDOW_20M)
    print("in-window wav files (%s..%s): %d" % (WINDOW_20M[0], WINDOW_20M[1], len(all_files)))

    if args.smoke_test:
        chosen = all_files[:args.smoke_test]
        print("SMOKE TEST: processing %d files, both depths, no gate evaluated" % len(chosen))
        d1 = run_jt9(chosen, 1, scratch, args.workers)
        d3 = run_jt9(chosen, 3, scratch, args.workers)
        n1_raw, k1 = to_keyset(d1)
        n3_raw, k3 = to_keyset(d3)
        print("d1: raw=%d dedup=%d" % (n1_raw, len(k1)))
        print("d3: raw=%d dedup=%d" % (n3_raw, len(k3)))
        print("sample d1 keys:", list(k1)[:2])
        return

    # ---- 2.1 timing probe FIRST ----
    probe_files = all_files[:args.probe_n]
    print("\n=== TIMING PROBE: %d files/depth, chronological, first files in window, workers=%d ==="
          % (args.probe_n, args.workers))
    t1_probe, probe_d1 = timed_probe(probe_files, 1, scratch, args.workers)
    print("d1 probe: %.2fs for %d files (%.3fs/file wall, workers=%d)"
          % (t1_probe, len(probe_files), t1_probe / len(probe_files), args.workers))
    t3_probe, probe_d3 = timed_probe(probe_files, 3, scratch, args.workers)
    print("d3 probe: %.2fs for %d files (%.3fs/file wall, workers=%d)"
          % (t3_probe, len(probe_files), t3_probe / len(probe_files), args.workers))

    rate_d1 = t1_probe / len(probe_files)
    rate_d3 = t3_probe / len(probe_files)
    full_n = len(all_files)
    extrapolated_sec = (rate_d1 + rate_d3) * full_n
    extrapolated_min = extrapolated_sec / 60.0
    print("extrapolated full-window total (both depths, at workers=%d): %.1f min (n=%d)"
          % (args.workers, extrapolated_min, full_n))

    result = {
        "probe": {
            "probe_n": args.probe_n,
            "workers": args.workers,
            "t1_probe_sec": t1_probe,
            "t3_probe_sec": t3_probe,
            "rate_d1_sec_per_file": rate_d1,
            "rate_d3_sec_per_file": rate_d3,
            "full_n": full_n,
            "extrapolated_min": extrapolated_min,
            "budget_min": args.time_budget_min,
        }
    }

    if extrapolated_min <= args.time_budget_min:
        path = "FULL_WINDOW"
        working_set = all_files
        print("\nDECISION: extrapolated %.1f min <= %.1f min budget -> FULL WINDOW (%d files)"
              % (extrapolated_min, args.time_budget_min, len(working_set)))
    else:
        path = "SUBSAMPLE"
        rng = random.Random(args.seed)
        working_set = rng.sample(all_files, min(args.subsample_n, len(all_files)))
        working_set.sort()
        print("\nDECISION: extrapolated %.1f min > %.1f min budget -> SUBSAMPLE n=%d, seed=%d"
              % (extrapolated_min, args.time_budget_min, len(working_set), args.seed))
    result["path"] = path
    result["working_set_n"] = len(working_set)
    result["seed"] = args.seed if path == "SUBSAMPLE" else None

    # Reuse probe decodes for any file that lands in the working set (avoid re-running).
    probe_ts_set = {ts for ts, _ in probe_files}
    working_ts_set = {ts for ts, _ in working_set}
    remaining = [(ts, p) for ts, p in working_set if ts not in probe_ts_set]
    reused = [(ts, p) for ts, p in working_set if ts in probe_ts_set]
    print("\nreusing %d probe files already decoded; decoding %d more files at each depth"
          % (len(reused), len(remaining)))

    t0 = time.time()
    d1_rest = run_jt9(remaining, 1, scratch, args.workers) if remaining else {}
    t_d1_rest = time.time() - t0
    print("d1 remaining decode: %.1f min" % (t_d1_rest / 60.0))

    t0 = time.time()
    d3_rest = run_jt9(remaining, 3, scratch, args.workers) if remaining else {}
    t_d3_rest = time.time() - t0
    print("d3 remaining decode: %.1f min" % (t_d3_rest / 60.0))

    d1_all = dict(probe_d1)
    d1_all.update(d1_rest)
    d1_all = {ts: msgs for ts, msgs in d1_all.items() if ts in working_ts_set}

    d3_all = dict(probe_d3)
    d3_all.update(d3_rest)
    d3_all = {ts: msgs for ts, msgs in d3_all.items() if ts in working_ts_set}

    n1_raw, D1 = to_keyset(d1_all)
    n3_raw, D3 = to_keyset(d3_all)
    n1_dedup, n3_dedup = len(D1), len(D3)
    print("\nD1: raw=%d dedup=%d" % (n1_raw, n1_dedup))
    print("D3: raw=%d dedup=%d" % (n3_raw, n3_dedup))

    # ---- populations from ALL.TXT, restricted to cycles actually replayed ----
    lo, hi = WINDOW_20M
    wa = load(LEG_20M["wsjtx_a"], lo, hi)
    wb = load(LEG_20M["wsjtx_b"], lo, hi)
    owsfz = load(LEG_20M["owsfz"], lo, hi)

    ref_all = set(wa) & set(wb)
    print("\nREF (raw intersection, full window, unrestricted): %d" % len(ref_all))
    REF = {k for k in ref_all if k[0] in working_ts_set}
    print("REF restricted to replayed cycles (n=%d): %d" % (len(working_ts_set), len(REF)))

    MISS = {k for k in REF if k not in owsfz}
    print("MISS = REF \\ OpenWSFZ8080, restricted: %d" % len(MISS))

    D3_minus_D1 = D3 - D1
    numerator_set = MISS & D3_minus_D1
    A = 100.0 * len(numerator_set) / len(REF) if REF else float("nan")
    B = 100.0 * len(D3_minus_D1) / len(D1) if D1 else float("nan")
    C = 100.0 * len(D1 & REF) / len(REF) if REF else float("nan")
    print("\nA = |MISS ^ (D3\\D1)| / |REF| = %d / %d = %.3f pp" % (len(numerator_set), len(REF), A))
    print("B = |D3\\D1| / |D1|           = %d / %d = %.3f%%" % (len(D3_minus_D1), len(D1), B))
    print("C = |D1 ^ REF| / |REF|        = %d / %d = %.3f%%" % (len(D1 & REF), len(REF), C))

    wa_live_replayed = {k for k in wa if k[0] in working_ts_set}
    ratio_d3_live = len(D3) / len(wa_live_replayed) if wa_live_replayed else float("nan")
    print("\nratio_d3_live = |D3| / |WSJT-X A live, replayed cycles| = %d / %d = %.4f"
          % (len(D3), len(wa_live_replayed), ratio_d3_live))

    row0, row0_reason = p1_row0(n1_raw, n1_dedup, n3_raw, n3_dedup, ratio_d3_live, len(working_ts_set))
    print("\n=== GATE ===")
    if row0:
        print(">>> %s <<< (%s)" % (row0, row0_reason))
        final_row = row0
    else:
        final_row = p1_gate(A)
        print(">>> %s <<< (A=%.3f pp)" % (final_row, A))

    # ---- frequency-clustered bootstrap CI on A ----
    ref_freq = {k: wa[k][1] for k in REF}
    boot = cluster_bootstrap_A(ref_freq, numerator_set, args.boot_draws, args.seed)
    binomial_se = (A / 100.0 * (1 - A / 100.0) / len(REF)) ** 0.5 * 100 if REF else float("nan")
    print("\nclustered bootstrap on A: mean=%.3f se=%.3f ci95=%s (n_distinct_freq=%d, draws=%d, seed=%d)"
          % (boot["bootstrap_mean"], boot["bootstrap_se"], boot["ci95_pct"],
             boot["n_distinct_freq"], boot["n_draws"], boot["seed"]))
    print("binomial SE (for comparison ONLY, not to be cited): %.3f -> design effect ~%.2fx"
          % (binomial_se, boot["bootstrap_se"] / binomial_se if binomial_se else float("nan")))

    result.update({
        "n1_raw": n1_raw, "n1_dedup": n1_dedup,
        "n3_raw": n3_raw, "n3_dedup": n3_dedup,
        "ref_all_unrestricted": len(ref_all),
        "REF": len(REF), "MISS": len(MISS),
        "D3_minus_D1": len(D3_minus_D1), "numerator": len(numerator_set),
        "A": A, "B": B, "C": C,
        "ratio_d3_live": ratio_d3_live,
        "wa_live_replayed": len(wa_live_replayed),
        "row0": row0, "row0_reason": row0_reason,
        "final_row": final_row,
        "bootstrap": boot,
        "binomial_se_for_comparison_only": binomial_se,
        "t_d1_rest_sec": t_d1_rest, "t_d3_rest_sec": t_d3_rest,
        "working_ts_sample": sorted(working_ts_set)[:5],
    })

    with io.open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()
