#!/usr/bin/env python3
"""D-001 R.5 -- the hybrid ladder.

Bisects the gap between the two measured endpoints (isolated synthetic ~100%, real corpus ~61%)
by building a 5-rung ladder per real cycle that adds one property of real audio at a time:
rung 0 isolated synthetic baseline, rung 1 +real density/layout, rung 2 +real SNR distribution,
rung 3 +real noise background, rung 4 the real cycle unmodified (reused, not regenerated).

Design: `2026-07-27-1822-architect-r5-hybrid-ladder-design.md`. Operationalised by
`2026-07-27-r5-hybrid-ladder-task-spec.md`.

NFR-021: rungs 0-3 plant Q-prefix synthetic messages only (message text never printed). Rung 4
reuses existing corpus artefacts (real callsigns) restricted to aggregate hit/miss counts, never
message text, per every prior arm in this thread.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import ctypes
import json
import math
import os
import random
import subprocess
import sys
import time
import wave

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import b2_synthetic_calibration as b2
import b1_jt9_ablation as b1

REPO_ROOT = b1.REPO
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "d001_r5_hybrid_ladder")
BUF_DIR = os.path.join(OUT_DIR, "buffers")
JT9_SCRATCH = os.path.join(OUT_DIR, "jt9")

N_CYCLES = int(os.environ.get("R5_N_CYCLES", "20"))
FREQ_MIN = 200.0
FREQ_MAX = 2950.0  # base-frequency ceiling; occupied envelope reaches 2950+43.75=2993.75, per
                    # the 15:22 ruling's stop rule (task spec Sec.2.1)
SIG_OCCUPIED_HZ = 43.75  # 7 * 6.25, 8-tone alphabet
DT_MIN = 0.0
DT_MAX = (b2.BUFFER_SAMPLES - b2.SIG_SAMPLES) / b2.SR  # 2.3667s
DT_MARGIN = 0.0667
REFERENCE_SNR_DB = -14.0
NOTCH_GUARD_HZ = 5.0

RUNG4_JT9_STDOUT = os.path.join(REPO_ROOT, "artefacts", "d001_b1_jt9_ablation",
                                 "A2_d1", "stdout_raw.txt")


# -------------------- message-text-capable decode wrapper --------------------

def decode_all_with_messages(native: "b2.Native", pcm: np.ndarray) -> set[str]:
    """Re-invokes ft8_decode_all (already called inside b2.Native.decode_all for candidate-diag
    purposes, but that wrapper does not read out FT8Result.message). This calls the same shipped
    export directly and reads the decoded message text -- no native/src change (task spec Sec.3)."""
    assert pcm.shape == (b2.BUFFER_SAMPLES,)
    pcm_c = (ctypes.c_float * b2.BUFFER_SAMPLES)(*pcm.astype(np.float32))
    results = (native.FT8Result * 200)()
    n = native.dll.ft8_decode_all(pcm_c, b2.BUFFER_SAMPLES, results, 200)
    if n < 0:
        return set()
    return {results[i].message.decode("ascii", errors="replace") for i in range(n)}


# -------------------- selection --------------------

def select_cycles() -> list[str]:
    wav_names = sorted(os.path.splitext(f)[0]
                        for f in os.listdir(b1.OURS_WAV_DIR) if f.endswith(".wav"))
    assert len(wav_names) == 68, f"expected 68 matched cycles, got {len(wav_names)}"
    idx = sorted(set(int(round(x)) for x in np.linspace(0, len(wav_names) - 1, N_CYCLES)))
    return [wav_names[i] for i in idx]


def read_real_wav_float(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, b2.SR)
        n = w.getnframes()
        data = w.readframes(n)
    arr = np.frombuffer(data, dtype="<i2").astype(np.float64) / 32768.0
    assert arr.shape[0] == b2.BUFFER_SAMPLES, f"{path}: {arr.shape[0]} samples"
    return arr


# -------------------- real-layout extraction (Sec.2.4) --------------------

def real_layout_for_cycle(ts: str, all_wsjtx_rows: list[dict]) -> dict:
    """Returns dict with 'full' (all real messages this cycle, for notching, Sec.2.6) and
    'planted' (band+timing-filtered list of {freq, dt, snr, real_message}, the shared rung1-3
    layout, Sec.2.4). 'real_message' (normalized) is carried through ONLY so rung 4 can be
    restricted to the identical message population for a fair 3-vs-4 comparison (Sec.4 addendum)
    -- it is never used as planted content (rungs 1-3 plant synthetic Q-call messages at these
    positions, per NFR-021) and is never printed."""
    cyc_rows = [r for r in all_wsjtx_rows if r["ts"] == ts]
    full = [{"freq": float(r["freq"]), "snr": float(r["snr"])} for r in cyc_rows]

    band_ok = [{"freq": float(r["freq"]), "dt": float(r["dt"]), "snr": float(r["snr"]),
                "real_message": b1.normalize_hash_tokens(r["message"])}
               for r in cyc_rows if FREQ_MIN <= float(r["freq"]) <= FREQ_MAX]
    n_band_dropped = len(cyc_rows) - len(band_ok)

    if not band_ok:
        return {"full": full, "planted": [], "n_total": len(cyc_rows),
                "n_band_dropped": n_band_dropped, "n_timing_dropped": 0}

    min_dt = min(m["dt"] for m in band_ok)
    shift = 0.5 - min_dt
    planted = []
    n_timing_dropped = 0
    for m in band_ok:
        shifted = m["dt"] + shift
        if DT_MIN <= shifted <= DT_MAX - DT_MARGIN:
            planted.append({"freq": m["freq"], "dt": shifted, "snr": m["snr"],
                             "real_message": m["real_message"]})
        else:
            n_timing_dropped += 1

    return {"full": full, "planted": planted, "n_total": len(cyc_rows),
            "n_band_dropped": n_band_dropped, "n_timing_dropped": n_timing_dropped}


# -------------------- notching (Sec.2.6) --------------------

def notch_and_measure(real_pcm: np.ndarray, full_layout: list[dict]) -> tuple[np.ndarray, float]:
    n = len(real_pcm)
    spec = np.fft.rfft(real_pcm)
    freqs = np.fft.rfftfreq(n, d=1.0 / b2.SR)
    mask = np.ones_like(freqs, dtype=bool)
    for m in full_layout:
        lo = m["freq"] - NOTCH_GUARD_HZ
        hi = m["freq"] + SIG_OCCUPIED_HZ + NOTCH_GUARD_HZ
        mask &= ~((freqs >= lo) & (freqs <= hi))
    spec_notched = spec * mask
    residual = np.fft.irfft(spec_notched, n=n)
    noise_std_real = float(np.std(residual))
    return residual, noise_std_real


# -------------------- buffer construction per rung --------------------

def amplitude_for_snr(snr_db: float, noise_std: float) -> float:
    return noise_std * math.sqrt(2.0) * (10 ** (snr_db / 20.0))


def build_rung0(native: "b2.Native", rng_py: random.Random, rng_np: np.random.Generator,
                 noise_std_ref: float) -> tuple[np.ndarray, list[dict]]:
    buf = np.zeros(b2.BUFFER_SAMPLES, dtype=np.float64)
    n_slots = 8
    slot_width = (FREQ_MAX - FREQ_MIN) / n_slots
    planted = []
    for slot in range(n_slots):
        base_freq = FREQ_MIN + slot * slot_width + rng_py.uniform(20, slot_width - 40)
        msg = b2.make_message(rng_py)
        tones = native.encode(msg)
        sig = b2.synth_signal(tones, base_freq, b2.AMPLITUDE, rng_np)
        b2.plant(buf, sig, 0.6)
        planted.append({"message": msg, "freq_hz": base_freq, "dt": 0.6})
    buf += rng_np.normal(0.0, noise_std_ref, size=b2.BUFFER_SAMPLES)
    return buf, planted


def build_layout_rung(native: "b2.Native", rng_py: random.Random, rng_np: np.random.Generator,
                       layout: list[dict], amp_fn, noise_std: float,
                       background: np.ndarray | None) -> tuple[np.ndarray, list[dict]]:
    """amp_fn(entry) -> amplitude. background: None => synthetic AWGN at noise_std added;
    otherwise background is added as-is (already-notched real residual, rung 3) and noise_std is
    used only for amp_fn's reference, not added again."""
    buf = np.zeros(b2.BUFFER_SAMPLES, dtype=np.float64)
    planted = []
    for entry in layout:
        msg = b2.make_message(rng_py)
        tones = native.encode(msg)
        amp = amp_fn(entry)
        sig = b2.synth_signal(tones, entry["freq"], amp, rng_np)
        b2.plant(buf, sig, entry["dt"])
        planted.append({"message": msg, "freq_hz": entry["freq"], "dt": entry["dt"],
                         "real_snr_db": entry["snr"], "amplitude": amp})
    if background is None:
        buf += rng_np.normal(0.0, noise_std, size=b2.BUFFER_SAMPLES)
    else:
        buf = buf + background
    return buf, planted


# -------------------- I/O + jt9 --------------------

def write_wav(path: str, buf: np.ndarray) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    peak = np.max(np.abs(buf))
    scale = 1.0
    if peak > 0.9:
        scale = 0.9 / peak
        buf = buf * scale
    pcm16 = np.clip(buf * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(b2.SR)
        w.writeframes(pcm16.tobytes())
    return scale


def run_jt9_single(wav_path: str, scratch: str) -> set[str]:
    os.makedirs(scratch, exist_ok=True)
    cmd = [b1.JT9_EXE, "-8", "-d", "1", "-p", "15", "-a", scratch, "-t", scratch, wav_path]
    result = subprocess.run(cmd, cwd=scratch, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  [WARN] jt9 exited {result.returncode} on {wav_path}", file=sys.stderr)
    rows = b1.parse_jt9_stdout(result.stdout, "buf")
    return {b1.normalize_hash_tokens(r["message"]) for r in rows}


# -------------------- rung 4 (reused, Sec.2.5) --------------------

def rung4_reused(selected_cycles: list[str], all_wsjtx_rows: list[dict]) -> dict:
    cycle_set = set(selected_cycles)
    wsjtx_by_cycle = b1.to_by_cycle(r for r in all_wsjtx_rows if r["ts"] in cycle_set)
    ours_by_cycle = b1.to_by_cycle(r for r in b1.parse_all_txt(b1.OURS_OFFLINE_ALL_TXT)
                                    if r["ts"] in cycle_set)
    with open(RUNG4_JT9_STDOUT, encoding="utf-8", errors="replace") as fh:
        jt9_text = fh.read()
    jt9_rows = b1.parse_jt9_stdout(jt9_text, "260725")
    jt9_by_cycle = b1.to_by_cycle(r for r in jt9_rows if r["ts"] in cycle_set)

    n_total = n_ours_hit = n_jt9_hit = 0
    for ts, wset in wsjtx_by_cycle.items():
        n_total += len(wset)
        n_ours_hit += len(wset & ours_by_cycle.get(ts, set()))
        n_jt9_hit += len(wset & jt9_by_cycle.get(ts, set()))
    return {"n_total": n_total, "n_ours_hit": n_ours_hit, "n_jt9_hit": n_jt9_hit,
            "n_cycles": len(cycle_set)}


def rung4_matched(selected_cycles: list[str], all_wsjtx_rows: list[dict],
                   planted_real_messages: dict[str, list[str]]) -> dict:
    """Same as rung4_reused, but restricted per cycle to exactly the (normalized) real messages
    that survived the band/timing filters and were actually planted in rungs 1-3 -- an
    apples-to-apples population for the rung3-vs-rung4 comparison (Sec.4 addendum: rung 4's raw
    population is larger than rungs 1-3's since some real messages are excluded by those filters)."""
    cycle_set = set(selected_cycles)
    wsjtx_by_cycle = b1.to_by_cycle(r for r in all_wsjtx_rows if r["ts"] in cycle_set)
    ours_by_cycle = b1.to_by_cycle(r for r in b1.parse_all_txt(b1.OURS_OFFLINE_ALL_TXT)
                                    if r["ts"] in cycle_set)
    with open(RUNG4_JT9_STDOUT, encoding="utf-8", errors="replace") as fh:
        jt9_text = fh.read()
    jt9_rows = b1.parse_jt9_stdout(jt9_text, "260725")
    jt9_by_cycle = b1.to_by_cycle(r for r in jt9_rows if r["ts"] in cycle_set)

    n_total = n_ours_hit = n_jt9_hit = n_not_in_wsjtx = 0
    for ts, msgs in planted_real_messages.items():
        wset = wsjtx_by_cycle.get(ts, set())
        oset = ours_by_cycle.get(ts, set())
        jset = jt9_by_cycle.get(ts, set())
        for msg in msgs:
            if msg not in wset:
                n_not_in_wsjtx += 1  # should not happen -- these came from wsjtx rows themselves
                continue
            n_total += 1
            if msg in oset:
                n_ours_hit += 1
            if msg in jset:
                n_jt9_hit += 1
    return {"n_total": n_total, "n_ours_hit": n_ours_hit, "n_jt9_hit": n_jt9_hit,
            "n_not_in_wsjtx": n_not_in_wsjtx}


# -------------------- main --------------------

def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUF_DIR, exist_ok=True)
    t0 = time.time()

    print(f"Loading DLL: {b2.DLL_PATH}")
    native = b2.Native(b2.DLL_PATH)

    seed = int(os.environ.get("R5_SEED", "20260727"))
    noise_std_ref = (b2.AMPLITUDE / math.sqrt(2)) / (10 ** (REFERENCE_SNR_DB / 20))
    print(f"Reference SNR={REFERENCE_SNR_DB} dB -> noise_std_ref={noise_std_ref:.6f}")

    cycles = select_cycles()
    print(f"Selected {len(cycles)} cycles (stride sample of 68): {cycles}")

    all_wsjtx_rows = b1.parse_all_txt(b1.WSJTX_ALL_TXT)

    measurements: dict[str, list[dict]] = {0: [], 1: [], 2: [], 3: []}
    manifest: dict[str, dict] = {}
    layout_stats = []
    planted_real_messages: dict[str, list[str]] = {}

    for ci, ts in enumerate(cycles):
        rng_py = random.Random(seed * 1_000_003 + ci)
        real_wav_path = os.path.join(b1.WSJTX_WAV_DIR, ts + ".wav")
        real_pcm = read_real_wav_float(real_wav_path)

        layout_info = real_layout_for_cycle(ts, all_wsjtx_rows)
        planted_layout = layout_info["planted"]
        layout_stats.append({"ts": ts, "n_total": layout_info["n_total"],
                              "n_band_dropped": layout_info["n_band_dropped"],
                              "n_timing_dropped": layout_info["n_timing_dropped"],
                              "n_planted": len(planted_layout)})
        planted_real_messages[ts] = [e["real_message"] for e in planted_layout]

        residual, noise_std_real = notch_and_measure(real_pcm, layout_info["full"])

        cycle_buffers = {}

        # rung 0
        rng_np = np.random.default_rng(seed * 100_003 + ci)
        buf0, pl0 = build_rung0(native, rng_py, rng_np, noise_std_ref)
        cycle_buffers[0] = (buf0, pl0)

        # rung 1: uniform amplitude=0.15, synthetic AWGN at noise_std_ref
        rng_np = np.random.default_rng(seed * 100_003 + ci + 10_000)
        buf1, pl1 = build_layout_rung(native, rng_py, rng_np, planted_layout,
                                       lambda e: b2.AMPLITUDE, noise_std_ref, background=None)
        cycle_buffers[1] = (buf1, pl1)

        # rung 2: real-SNR amplitude (pinned to noise_std_ref), synthetic AWGN at noise_std_ref
        rng_np = np.random.default_rng(seed * 100_003 + ci + 20_000)
        buf2, pl2 = build_layout_rung(native, rng_py, rng_np, planted_layout,
                                       lambda e: amplitude_for_snr(e["snr"], noise_std_ref),
                                       noise_std_ref, background=None)
        cycle_buffers[2] = (buf2, pl2)

        # rung 3: real-SNR amplitude (pinned to noise_std_real), real notched background
        rng_np = np.random.default_rng(seed * 100_003 + ci + 30_000)
        buf3, pl3 = build_layout_rung(native, rng_py, rng_np, planted_layout,
                                       lambda e: amplitude_for_snr(e["snr"], noise_std_real),
                                       noise_std_real, background=residual)
        cycle_buffers[3] = (buf3, pl3)

        for rung, (buf, planted) in cycle_buffers.items():
            ours_msgs = decode_all_with_messages(native, buf)
            wav_path = os.path.join(BUF_DIR, f"rung{rung}_{ts}.wav")
            write_wav(wav_path, buf)
            scratch = os.path.join(JT9_SCRATCH, f"rung{rung}_{ts}")
            jt9_msgs = run_jt9_single(wav_path, scratch)
            for p in planted:
                measurements[rung].append({
                    "ts": ts, "rung": rung,
                    "ours_decoded": p["message"] in ours_msgs,
                    "jt9_decoded": p["message"] in jt9_msgs,
                })
            manifest.setdefault(f"rung{rung}_{ts}", []).extend(
                {"message": p["message"], "freq_hz": p["freq_hz"], "dt": p["dt"]} for p in planted)

        print(f"  [{ci+1}/{len(cycles)}] {ts}: real={layout_info['n_total']} "
              f"band_drop={layout_info['n_band_dropped']} timing_drop={layout_info['n_timing_dropped']} "
              f"planted={len(planted_layout)} noise_std_real={noise_std_real:.6f} "
              f"elapsed={time.time()-t0:.0f}s")

    with open(os.path.join(OUT_DIR, "measurements.json"), "w") as fh:
        json.dump(measurements, fh)
    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    with open(os.path.join(OUT_DIR, "layout_stats.json"), "w") as fh:
        json.dump(layout_stats, fh, indent=2)

    print()
    print("=" * 70)
    print("RUNGS 0-3 -- P(decode), both decoders")
    print("=" * 70)
    curves = {}
    for rung in [0, 1, 2, 3]:
        ms = measurements[rung]
        n = len(ms)
        k_ours = sum(1 for m in ms if m["ours_decoded"])
        k_jt9 = sum(1 for m in ms if m["jt9_decoded"])
        p_ours, lo_ours, hi_ours = b2.wilson_interval(k_ours, n)
        p_jt9, lo_jt9, hi_jt9 = b2.wilson_interval(k_jt9, n)
        curves[rung] = {"n": n, "ours": {"k": k_ours, "p": p_ours, "ci_lo": lo_ours, "ci_hi": hi_ours},
                         "jt9": {"k": k_jt9, "p": p_jt9, "ci_lo": lo_jt9, "ci_hi": hi_jt9}}
        print(f"rung {rung}: n={n:4d}  ours k={k_ours:4d} p={p_ours:6.1%} "
              f"ci=[{lo_ours:.1%},{hi_ours:.1%}]   jt9 k={k_jt9:4d} p={p_jt9:6.1%} "
              f"ci=[{lo_jt9:.1%},{hi_jt9:.1%}]")

    print()
    print("=" * 70)
    print("RUNG 4 -- reused real-corpus results, 20-cycle sample")
    print("=" * 70)
    r4 = rung4_reused(cycles, all_wsjtx_rows)
    p_ours4, lo4, hi4 = b2.wilson_interval(r4["n_ours_hit"], r4["n_total"])
    p_jt94, lo94, hi94 = b2.wilson_interval(r4["n_jt9_hit"], r4["n_total"])
    print(f"n_total={r4['n_total']}  ours: k={r4['n_ours_hit']} p={p_ours4:.1%} "
          f"ci=[{lo4:.1%},{hi4:.1%}]   jt9: k={r4['n_jt9_hit']} p={p_jt94:.1%} "
          f"ci=[{lo94:.1%},{hi94:.1%}]")
    print("(full-68-cycle published: ours ~61% overall hit-rate, B.1/R.4b. NOTE: jt9's headline")
    print(" '55.4%' figure elsewhere in this thread is jt9-depth1's coverage of OUR MISS")
    print(" population specifically (437/789), a different quantity from jt9's overall hit-rate")
    print(" against WSJT-X's full decode set, which B.1's own A2 arm puts at 1693/2028 = 83.5% --")
    print(" that overall figure is what this rung's jt9 number is comparable to.)")
    curves[4] = {"n": r4["n_total"],
                 "ours": {"k": r4["n_ours_hit"], "p": p_ours4, "ci_lo": lo4, "ci_hi": hi4},
                 "jt9": {"k": r4["n_jt9_hit"], "p": p_jt94, "ci_lo": lo94, "ci_hi": hi94}}

    print()
    print("=" * 70)
    print("RUNG 4 MATCHED -- restricted to exactly rungs 1-3's planted population (Sec.4 addendum)")
    print("=" * 70)
    r4m = rung4_matched(cycles, all_wsjtx_rows, planted_real_messages)
    p_ours4m, lo4m, hi4m = b2.wilson_interval(r4m["n_ours_hit"], r4m["n_total"])
    p_jt94m, lo94m, hi94m = b2.wilson_interval(r4m["n_jt9_hit"], r4m["n_total"])
    print(f"n_total={r4m['n_total']} (rungs 1-3 population was {curves[1]['n']}; "
          f"n_not_in_wsjtx={r4m['n_not_in_wsjtx']} sanity check, expect 0)")
    print(f"ours: k={r4m['n_ours_hit']} p={p_ours4m:.1%} ci=[{lo4m:.1%},{hi4m:.1%}]   "
          f"jt9: k={r4m['n_jt9_hit']} p={p_jt94m:.1%} ci=[{lo94m:.1%},{hi94m:.1%}]")
    curves["4_matched"] = {"n": r4m["n_total"],
                            "ours": {"k": r4m["n_ours_hit"], "p": p_ours4m, "ci_lo": lo4m, "ci_hi": hi4m},
                            "jt9": {"k": r4m["n_jt9_hit"], "p": p_jt94m, "ci_lo": lo94m, "ci_hi": hi94m}}

    with open(os.path.join(OUT_DIR, "curves.json"), "w") as fh:
        json.dump(curves, fh, indent=2)

    print()
    print("=" * 70)
    print("SELF-CHECKS (task spec Sec.4)")
    print("=" * 70)
    rung0_ok = curves[0]["ours"]["ci_lo"] >= 0.90 and curves[0]["jt9"]["ci_lo"] >= 0.90
    print(f"[{'PASS' if rung0_ok else 'FAIL'}] rung 0 Wilson lower CI >= 90%: "
          f"ours ci_lo={curves[0]['ours']['ci_lo']:.1%} jt9 ci_lo={curves[0]['jt9']['ci_lo']:.1%}")
    print(f"[INFO] rung 4 20-cycle sample vs full-68-cycle published: "
          f"ours {p_ours4:.1%} ci=[{lo4:.1%},{hi4:.1%}] (published ~61%), "
          f"jt9 {p_jt94:.1%} ci=[{lo94:.1%},{hi94:.1%}] (jt9's own full-corpus overall hit-rate "
          f"is 83.5% (A2=1693/2028, B.1 Sec.3) -- NOT the 55.4% miss-coverage figure, a different "
          f"quantity, see rung 4 note above)")

    print()
    print("=" * 70)
    print("LADDER SUMMARY -- per-step delta (percentage points)")
    print("=" * 70)
    ladder_order = [0, 1, 2, 3, "4_matched"]
    labels = {0: "rung0 (isolated synth)", 1: "rung1 (+real density/layout)",
              2: "rung2 (+real SNR)", 3: "rung3 (+real noise)",
              "4_matched": "rung4 (real, unmodified; matched population)"}
    prev_ours = prev_jt9 = None
    for key in ladder_order:
        c = curves[key]
        d_ours = "" if prev_ours is None else f"  (Delta ours={100*(c['ours']['p']-prev_ours):+.1f}pt)"
        d_jt9 = "" if prev_jt9 is None else f"  (Delta jt9={100*(c['jt9']['p']-prev_jt9):+.1f}pt)"
        print(f"  {labels[key]:<48} ours={c['ours']['p']:6.1%}{d_ours:>18}   "
              f"jt9={c['jt9']['p']:6.1%}{d_jt9:>16}")
        prev_ours, prev_jt9 = c["ours"]["p"], c["jt9"]["p"]

    print(f"\nTotal wall time: {time.time() - t0:.0f}s")
    print(f"All outputs under {OUT_DIR}")


if __name__ == "__main__":
    main()
