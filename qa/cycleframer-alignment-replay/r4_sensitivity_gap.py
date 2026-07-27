#!/usr/bin/env python3
"""D-001 R.4 -- the cost signal in dB.

Measures how much more sensitive WSJT-X's jt9 (minimum-effort, depth 1) is than our shipped
decoder on byte-identical synthetic buffers (ELTA_SNR), then converts that gap into a
messages-recovered-per-dB curve for each corpus's own currently-missed population.

Design: `2026-07-27-1730-architect-row4-scoping-design.md` Sec.4 (R.4), resequenced by
`2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` Sec.7. Operationalised by
`2026-07-27-r4-sensitivity-gap-task-spec.md`.

NFR-021: synthetic messages are Q-prefix by construction (Sec.2.1/2.2). Sec.2.3/self-check touch
real corpus data (WSJT-X ALL.TXT, B.1's own recorded jt9 stdout) and report aggregate counts/SNR
values only -- message text is never printed, even though these inputs live under git-ignored
artefacts/.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import json
import math
import os
import sys
import subprocess
import time
import wave

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import b2_synthetic_calibration as b2
import b1_jt9_ablation as b1
import b1b_second_corpus_ablation as b1b

REPO_ROOT = b1.REPO
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "d001_r4_sensitivity_gap")
BUF_DIR = os.path.join(OUT_DIR, "buffers")
JT9_SCRATCH = os.path.join(OUT_DIR, "jt9")
SELF_CHECK_WAV = os.path.join(b1.WSJTX_WAV_DIR, "260725_180615.wav")
SELF_CHECK_RECORDED = os.path.join(REPO_ROOT, "artefacts", "d001_b1_jt9_ablation",
                                    "A2_d1", "stdout_raw.txt")
SELF_CHECK_TS_TOKEN = "180615"
SELF_CHECK_DATE_PREFIX = "260725"

SNR_GRID = [x / 1.0 for x in range(-14, -31, -1)]  # -14 .. -30 dB inclusive, 1 dB steps (17 levels)
REPEATS = int(os.environ.get("R4_REPEATS", "3"))
SEED = 20260727


# -------------------- self-check --------------------

def run_self_check() -> bool:
    """Re-run jt9 -8 -d1 on B.1's own recorded WAV/timestamp and compare the decode set against
    what was already recorded in that session. Message text is compared but never printed
    (NFR-021); only match/mismatch counts are reported."""
    print("=" * 70)
    print("SELF-CHECK: reproduce B.1's own depth-1 decode set on a shared, unchanged WAV")
    print("=" * 70)
    if not os.path.isfile(SELF_CHECK_WAV):
        print(f"  [FAIL] self-check WAV missing: {SELF_CHECK_WAV}")
        return False
    if not os.path.isfile(SELF_CHECK_RECORDED):
        print(f"  [FAIL] recorded B.1 stdout missing: {SELF_CHECK_RECORDED}")
        return False

    with open(SELF_CHECK_RECORDED, encoding="utf-8", errors="replace") as fh:
        recorded_text = fh.read()
    recorded_rows = b1.parse_jt9_stdout(recorded_text, SELF_CHECK_DATE_PREFIX)
    recorded_set = {b1.normalize_hash_tokens(r["message"])
                     for r in recorded_rows if r["ts"] == f"{SELF_CHECK_DATE_PREFIX}_{SELF_CHECK_TS_TOKEN}"}

    scratch = os.path.join(JT9_SCRATCH, "selfcheck")
    os.makedirs(scratch, exist_ok=True)
    cmd = [b1.JT9_EXE, "-8", "-d", "1", "-p", "15", "-a", scratch, "-t", scratch, SELF_CHECK_WAV]
    t0 = time.time()
    result = subprocess.run(cmd, cwd=scratch, capture_output=True, text=True, timeout=120)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"  [FAIL] jt9 exited {result.returncode}")
        print(result.stderr[-1000:], file=sys.stderr)
        return False
    fresh_rows = b1.parse_jt9_stdout(result.stdout, SELF_CHECK_DATE_PREFIX)
    fresh_set = {b1.normalize_hash_tokens(r["message"]) for r in fresh_rows}

    n_recorded = len(recorded_set)
    n_fresh = len(fresh_set)
    n_match = len(recorded_set & fresh_set)
    n_only_recorded = len(recorded_set - fresh_set)
    n_only_fresh = len(fresh_set - recorded_set)
    print(f"  elapsed={elapsed:.2f}s recorded_n={n_recorded} fresh_n={n_fresh} "
          f"match={n_match} only_recorded={n_only_recorded} only_fresh={n_only_fresh}")
    ok = (n_only_recorded == 0 and n_only_fresh == 0 and n_recorded > 0)
    print(f"  {'[PASS]' if ok else '[FAIL]'} exact-set reproduction "
          f"{'confirmed' if ok else 'FAILED -- stop, do not trust the sweep below'}")
    return ok


# -------------------- buffer generation + dual decode --------------------

def write_wav(path: str, buf: np.ndarray) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    peak = np.max(np.abs(buf))
    if peak > 0.9:
        buf = buf * (0.9 / peak)
    pcm16 = np.clip(buf * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(b2.SR)
        w.writeframes(pcm16.tobytes())


def run_jt9_single(wav_path: str, scratch: str) -> list[dict]:
    os.makedirs(scratch, exist_ok=True)
    cmd = [b1.JT9_EXE, "-8", "-d", "1", "-p", "15", "-a", scratch, "-t", scratch, wav_path]
    result = subprocess.run(cmd, cwd=scratch, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  [WARN] jt9 exited {result.returncode} on {wav_path}", file=sys.stderr)
    return b1.parse_jt9_stdout(result.stdout, "buf")


def generate_and_decode(native: "b2.Native") -> tuple[list[dict], dict]:
    """Returns (measurements, manifest). measurements: one dict per planted signal with
    snr_db, ours_decoded (bool), jt9_decoded (bool). manifest: buffer_id -> planted list, for
    R.3's reuse."""
    import random as _random
    rng_py = _random.Random(SEED)
    measurements: list[dict] = []
    manifest: dict[str, list[dict]] = {}
    n_slots = 8
    slot_width = 3000.0 / n_slots
    buf_idx = 0
    t0 = time.time()

    for snr_db in SNR_GRID:
        for rep in range(REPEATS):
            buf_idx += 1
            buf_id = f"snr{snr_db:.0f}_r{rep}"
            rng = np.random.default_rng(SEED * 100003 + int(snr_db * 10) * 97 + rep)
            buf = np.zeros(b2.BUFFER_SAMPLES, dtype=np.float64)
            dt = 0.6
            planted = []
            for slot in range(n_slots):
                base_freq = 300.0 + slot * slot_width + rng_py.uniform(20, slot_width - 60)
                msg = b2.make_message(rng_py)
                tones = native.encode(msg)
                sig = b2.synth_signal(tones, base_freq, b2.AMPLITUDE, rng)
                b2.plant(buf, sig, dt)
                planted.append({"message": msg, "freq_hz": base_freq, "dt": dt})
            noise_std = (b2.AMPLITUDE / math.sqrt(2)) / (10 ** (snr_db / 20))
            buf += rng.normal(0.0, noise_std, size=b2.BUFFER_SAMPLES)

            # our decoder
            cands = native.decode_all(buf)
            ours_decoded_msgs = set()
            for p in planted:
                cand = b2.nearest_candidate(p["freq_hz"], p["dt"], cands)
                if cand is not None and cand["decoded"]:
                    ours_decoded_msgs.add(p["message"])

            # write WAV, run jt9
            wav_path = os.path.join(BUF_DIR, f"{buf_id}.wav")
            write_wav(wav_path, buf)
            scratch = os.path.join(JT9_SCRATCH, buf_id)
            jt9_rows = run_jt9_single(wav_path, scratch)
            jt9_decoded_msgs = {b1.normalize_hash_tokens(r["message"]) for r in jt9_rows}

            for p in planted:
                measurements.append({
                    "buf_id": buf_id, "snr_db": snr_db,
                    "ours_decoded": p["message"] in ours_decoded_msgs,
                    "jt9_decoded": p["message"] in jt9_decoded_msgs,
                })
            manifest[buf_id] = [{"message": p["message"], "freq_hz": p["freq_hz"], "dt": p["dt"],
                                  "snr_db": snr_db} for p in planted]

            if buf_idx % 10 == 0:
                print(f"  ... {buf_idx}/{len(SNR_GRID) * REPEATS} buffers, "
                      f"{time.time() - t0:.0f}s elapsed")

    print(f"generate_and_decode: {buf_idx} buffers, {len(measurements)} planted-signal "
          f"measurements, {time.time() - t0:.0f}s total")
    return measurements, manifest


# -------------------- curves --------------------

def p_decode_curve(measurements: list[dict], key: str) -> list[dict]:
    by_snr: dict[float, list[bool]] = {}
    for m in measurements:
        by_snr.setdefault(m["snr_db"], []).append(m[key])
    out = []
    for snr in sorted(by_snr, reverse=True):
        vals = by_snr[snr]
        n = len(vals)
        k = sum(1 for v in vals if v)
        p, lo, hi = b2.wilson_interval(k, n)
        out.append({"snr_db": snr, "n": n, "k": k, "p": p, "ci_lo": lo, "ci_hi": hi})
    return out


def find_50_crossing(curve: list[dict]) -> float | None:
    """curve sorted by snr_db descending (warm to cold). Find the snr_db where P crosses 0.5
    going from >=0.5 (warmer) to <0.5 (colder), linear-interpolated between grid points."""
    for i in range(len(curve) - 1):
        p_hi, p_lo = curve[i]["p"], curve[i + 1]["p"]
        if p_hi >= 0.5 >= p_lo and p_hi != p_lo:
            snr_hi, snr_lo = curve[i]["snr_db"], curve[i + 1]["snr_db"]
            frac = (p_hi - 0.5) / (p_hi - p_lo)
            return snr_hi + frac * (snr_lo - snr_hi)
    return None


# -------------------- corpus miss-population SNR --------------------

def corpus1_miss_and_hit_snr() -> tuple[list[float], list[float]]:
    wav_names = sorted(os.path.splitext(f)[0]
                        for f in os.listdir(b1.OURS_WAV_DIR) if f.endswith(".wav"))
    cycle_set = set(wav_names)
    wsjtx_rows = [r for r in b1.parse_all_txt(b1.WSJTX_ALL_TXT) if r["ts"] in cycle_set]
    ours_by_cycle = b1.to_by_cycle(r for r in b1.parse_all_txt(b1.OURS_OFFLINE_ALL_TXT)
                                    if r["ts"] in cycle_set)
    return _split_miss_hit_snr(wsjtx_rows, ours_by_cycle)


def corpus2_miss_and_hit_snr() -> tuple[list[float], list[float]]:
    wav_names = sorted(os.path.splitext(f)[0]
                        for f in os.listdir(b1b.WAV_DIR) if f.endswith(".wav"))
    cycle_set = set(wav_names)
    wsjtx_rows = [r for r in b1.parse_all_txt(b1b.WSJTX_ALL_TXT) if r["ts"] in cycle_set]
    ours_by_cycle = b1.to_by_cycle(r for r in b1.parse_all_txt(b1b.OURS_OFFLINE_ALL_TXT)
                                    if r["ts"] in cycle_set)
    return _split_miss_hit_snr(wsjtx_rows, ours_by_cycle)


def _split_miss_hit_snr(wsjtx_rows: list[dict],
                         ours_by_cycle: dict[str, set[str]]) -> tuple[list[float], list[float]]:
    miss_snr, hit_snr = [], []
    for r in wsjtx_rows:
        key = b1.normalize_hash_tokens(r["message"])
        ours = ours_by_cycle.get(r["ts"], set())
        snr = float(r["snr"])
        if key in ours:
            hit_snr.append(snr)
        else:
            miss_snr.append(snr)
    return miss_snr, hit_snr


def db_to_messages_curve(miss_snr: list[float], hit_snr: list[float],
                          delta_snr: float) -> list[dict]:
    hit_sorted = sorted(hit_snr)
    if not hit_sorted:
        return []
    idx = max(0, min(len(hit_sorted) - 1, round(0.05 * (len(hit_sorted) - 1))))
    threshold = hit_sorted[idx]
    out = []
    x = 0.0
    prev_count = 0
    while x <= delta_snr + 1e-9:
        lo = threshold - x
        count = sum(1 for s in miss_snr if lo <= s < threshold)
        out.append({"x_db": round(x, 1), "threshold": threshold, "count": count,
                     "pct_of_miss": 100.0 * count / max(1, len(miss_snr))})
        x += 0.5
    return out


# -------------------- main --------------------

def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUF_DIR, exist_ok=True)

    ok = run_self_check()
    if not ok and os.environ.get("R4_FORCE") != "1":
        print("\nSelf-check failed -- stopping per the design's stop rule. "
              "Set R4_FORCE=1 to override (not recommended).", file=sys.stderr)
        sys.exit(1)

    print()
    print(f"Loading DLL: {b2.DLL_PATH}")
    native = b2.Native(b2.DLL_PATH)

    print(f"\nGrid: {len(SNR_GRID)} SNR levels x {REPEATS} repeats x 8 signals/buffer "
          f"= {len(SNR_GRID) * REPEATS} buffers, {len(SNR_GRID) * REPEATS * 8} planted signals")
    measurements, manifest = generate_and_decode(native)

    with open(os.path.join(OUT_DIR, "measurements.json"), "w") as fh:
        json.dump(measurements, fh)
    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    ours_curve = p_decode_curve(measurements, "ours_decoded")
    jt9_curve = p_decode_curve(measurements, "jt9_decoded")

    print()
    print("OURS  P(decode) vs snr_db")
    for row in ours_curve:
        print(f"  {row['snr_db']:6.1f} dB  n={row['n']:3d} k={row['k']:3d} "
              f"p={row['p']:6.1%} ci=[{row['ci_lo']:.1%},{row['ci_hi']:.1%}]")
    print()
    print("JT9   P(decode) vs snr_db")
    for row in jt9_curve:
        print(f"  {row['snr_db']:6.1f} dB  n={row['n']:3d} k={row['k']:3d} "
              f"p={row['p']:6.1%} ci=[{row['ci_lo']:.1%},{row['ci_hi']:.1%}]")

    ours_50 = find_50_crossing(ours_curve)
    jt9_50 = find_50_crossing(jt9_curve)
    print()
    print(f"ours 50% crossing: {ours_50}")
    print(f"jt9  50% crossing: {jt9_50}")

    bracket_ok = ours_50 is not None and jt9_50 is not None
    if not bracket_ok:
        print("[BRACKETING FAILURE] one or both curves did not cross 50% inside the swept grid "
              "-- ELTA_SNR cannot be computed from this sweep. Reporting as a finding, not "
              "extrapolating.")
        delta_snr = None
    else:
        delta_snr = ours_50 - jt9_50
        print(f"DELTA_SNR (ours_50 - jt9_50) = {delta_snr:.2f} dB")

    with open(os.path.join(OUT_DIR, "curves.json"), "w") as fh:
        json.dump({"ours": ours_curve, "jt9": jt9_curve, "ours_50": ours_50, "jt9_50": jt9_50,
                    "delta_snr": delta_snr}, fh, indent=2)

    if delta_snr is not None and delta_snr > 0:
        print()
        print("=" * 70)
        print("dB-to-messages curves (per corpus, never collapsed)")
        print("=" * 70)
        for slug, label, fn in [("corpus1", "corpus 1 (40m, 68 cyc)", corpus1_miss_and_hit_snr),
                                 ("corpus2", "corpus 2 (20m, 126 cyc)", corpus2_miss_and_hit_snr)]:
            miss_snr, hit_snr = fn()
            curve = db_to_messages_curve(miss_snr, hit_snr, delta_snr)
            if curve:
                print(f"\n{label}: miss_n={len(miss_snr)} hit_n={len(hit_snr)} "
                      f"threshold={curve[0]['threshold']:.1f} dB (5th pct of hit SNR)")
            else:
                print(f"\n{label}: no hit population, cannot set threshold")
            for row in curve:
                print(f"  x={row['x_db']:4.1f} dB  count={row['count']:4d}  "
                      f"({row['pct_of_miss']:.1f}% of miss)")
            with open(os.path.join(OUT_DIR, f"db_to_messages_{slug}.json"), "w") as fh:
                json.dump({"label": label, "miss_n": len(miss_snr), "hit_n": len(hit_snr),
                            "curve": curve}, fh, indent=2)
    else:
        print("\nDELTA_SNR not positive/available -- skipping dB-to-messages step (design Sec.4 "
              "table's 'flat until near-full-DELTA_SNR' reading applies vacuously; report as-is).")

    print(f"\nAll outputs under {OUT_DIR}")


if __name__ == "__main__":
    main()
