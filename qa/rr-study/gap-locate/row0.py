#!/usr/bin/env python3
"""GAP-LOCATE ROW 0 (spec sec.3) -- mechanical preconditions plus population assembly.

0a identity, 0b harness reproduction, 0d audio length are self-contained here (fast).
0c (P_ctrl >= 0.90) needs Leg K's own forced-decode results (leg_fk.py) and is
evaluated by run_gap_locate.py once that leg is done. 0e (replay sanity) needs Leg R's
own per-cycle decode counts (leg_r.py) and is evaluated the same way.

NFR-021: this module and its printed/written output carry counts, rates, SNR/DT/freq
values keyed by (ts, message) internally only for population assembly -- message text
itself is never printed or serialised by anything in this file.
"""
from __future__ import annotations

import json
import os
import sys
import wave
from statistics import median

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "live-gap-now"))
sys.path.insert(0, HERE)

import loader  # noqa: E402
import matcher  # noqa: E402
import gl_dll_pin as dll_pin  # noqa: E402  (renamed: live-gap-now/dll_pin.py is a DIFFERENT
                               # module with the same generic name -- sys.modules caching
                               # means path re-ordering alone doesn't fix the collision)

SNR_STRONG = -10
CORPUS_DIR = os.path.join(REPO_ROOT, "artefacts", "20260921_1624_live_run-live-gap-map")
BUFFER_SAMPLES = 180_000

EXPECT_N_REF = 127482
EXPECT_H10 = 19.268602626253116
EXPECT_STRONG = 24564

K_SEED = 20260922
K_SIZE = 2000


def row0a(run_dir: str, log) -> dict:
    r = dll_pin.identity_check(run_dir)
    log("ROW 0a: sha256=%s pin_match=%s shim=%s resolves=%s -> %s"
        % (r["sha256"][:16] + "...", r["sha256"] == r["pin"], r["shim_reported"], r["resolves"],
           "PASS" if r["pass"] else "VOID"))
    return r


def load_population(log) -> dict:
    """Loads C3 (Amendment 3 cut), reproduces n_ref/H10/strong_misses (0b), computes
    delta (median OWS DT - REF DT over exact-matched pairs), and assembles M (strong
    misses) and the seeded control sample K."""
    d = loader.load_c3_with_dt(CORPUS_DIR, cut_amendment3=True)
    ref, live = d["ref"], d["live"]
    n_ref = len(ref)
    rec = matcher.recovery(live, ref)
    hit = set(rec["exact_matched"]) | set(rec["gained"])
    miss = [k for k in ref if k not in hit]
    strong = sorted(k for k in miss if ref[k][0] >= SNR_STRONG)  # M, sorted for determinism
    H10 = 100.0 * len(strong) / n_ref

    ok_0b = (n_ref == EXPECT_N_REF) and (abs(H10 - EXPECT_H10) < 1e-9) and (len(strong) == EXPECT_STRONG)
    log("ROW 0b: n_ref=%d (want %d) H10=%.12f (want %.12f) |M|=strong_misses=%d (want %d) -> %s"
        % (n_ref, EXPECT_N_REF, H10, EXPECT_H10, len(strong), EXPECT_STRONG,
           "PASS" if ok_0b else "VOID"))

    exact = rec["exact_matched"]
    deltas = [live[k][1] - ref[k][1] for k in exact]
    delta = median(deltas)
    log("ROW 0c prep: delta = median(OWS_DT - REF_DT) over %d exact-matched pairs = %.4f s"
        % (len(exact), delta))

    # Control population K: hits with REF SNR >= -10, seeded uniform sample n=2000.
    hit_strong = sorted(k for k in ref if k in hit and ref[k][0] >= SNR_STRONG)
    import random
    rng = random.Random(K_SEED)
    K_pop = hit_strong if len(hit_strong) <= K_SIZE else rng.sample(hit_strong, K_SIZE)
    log("Population K: %d hit rows (SNR>=-10) available, sampled %d (seed %d)"
        % (len(hit_strong), len(K_pop), K_SEED))

    return {
        "d": d, "ref": ref, "live": live, "n_ref": n_ref, "H10": H10,
        "M": strong, "K": sorted(K_pop), "delta": delta,
        "row0b": {"n_ref": n_ref, "H10": H10, "n_strong": len(strong), "pass": ok_0b},
    }


def row0d(pop: dict, log) -> dict:
    """ROW 0d: every WAV used (M union K's own cycles) is exactly BUFFER_SAMPLES long;
    exclusions must be <= 1% of M."""
    ref = pop["ref"]
    needed_ts = sorted({k[0] for k in pop["M"]} | {k[0] for k in pop["K"]})
    bad = []
    for ts in needed_ts:
        p = loader.cycle_wav_path(CORPUS_DIR, ts)
        try:
            with wave.open(p, "rb") as w:
                n = w.getnframes()
                fr = w.getframerate()
                ch = w.getnchannels()
                sw = w.getsampwidth()
            if n != BUFFER_SAMPLES or fr != 12000 or ch != 1 or sw != 2:
                bad.append((ts, n, fr, ch, sw))
        except (FileNotFoundError, OSError, wave.Error) as e:
            bad.append((ts, "ERROR:%s" % e, None, None, None))
    excluded_M_rows = sum(1 for k in pop["M"] if k[0] in {b[0] for b in bad})
    frac = excluded_M_rows / len(pop["M"]) if pop["M"] else 0.0
    ok = frac <= 0.01
    log("ROW 0d: %d/%d cycle WAVs checked bad, excluding %d/%d M rows (%.3f%%) -> %s"
        % (len(bad), len(needed_ts), excluded_M_rows, len(pop["M"]), 100 * frac,
           "PASS" if ok else "VOID"))
    return {"n_cycles_checked": len(needed_ts), "n_bad": len(bad), "bad_ts": [b[0] for b in bad],
            "excluded_M_rows": excluded_M_rows, "excluded_frac": frac, "pass": ok}


if __name__ == "__main__":
    def _log(msg):
        print(msg, flush=True)
    run_dir = sys.argv[1] if len(sys.argv) > 1 else None
    if run_dir:
        a = row0a(run_dir, _log)
    pop = load_population(_log)
    d0d = row0d(pop, _log)
    print(json.dumps({"row0b": pop["row0b"], "delta": pop["delta"], "row0d": d0d}, indent=2))
