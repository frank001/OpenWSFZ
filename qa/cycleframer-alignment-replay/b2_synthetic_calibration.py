#!/usr/bin/env python3
"""D-001 B.2 -- synthetic-waveform BER calibration.

Plants known FT8 signals into synthetic 15s/12kHz buffers, adds AWGN, decodes through the
UNMODIFIED shipped production path, and for every located planted signal reads its 174 raw
LLRs + decoded flag via the existing opt-in diagnostic exports (shim 20260034/35). Computes
hard-decision BER against the true (re-encoded) codeword and reads out P(decode | BER).

Design: `2026-07-26-2230-architect-sec6-redesign-ruling.md` Sec.5/Sec.6, operationalised by
`2026-07-26-b2-synthetic-calibration-task-spec.md`.

NFR-021: Q-prefix synthetic callsigns only. No message text or per-candidate record is ever
printed; only aggregate/binned statistics. ASCII-only console output (HK-009).
"""
from __future__ import annotations

import ctypes
import json
import math
import os
import random
import sys
import time

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "d001_b2_synthetic_calibration")

EXPECTED_SHIM_VERSION = 20260035

# -- FT8 constants (Ft8AudioSynthesiser.cs, direct-at-12kHz per task spec Sec.3) --
SR = 12_000
SAMPLES_PER_SYMBOL = 1920  # 12000 / 6.25
SYMBOL_COUNT = 79
TONE_SPACING_HZ = 6.25
SIG_SAMPLES = SAMPLES_PER_SYMBOL * SYMBOL_COUNT  # 151,680 (12.64 s)
BUFFER_SAMPLES = 180_000  # 15 s
FT8_NN = 79
FTX_LDPC_N = 174
SYNC_RANGES = [(0, 7), (36, 43), (72, 79)]
GRAY_MAP = [0, 1, 3, 2, 5, 6, 4, 7]  # verified in c2_phase2c_gray_sync_roundtrip_verify.py
INV_GRAY = [0] * 8
for _i, _v in enumerate(GRAY_MAP):
    INV_GRAY[_v] = _i

K_MAX_CANDIDATES = 140
FREQ_TOL_HZ = 10.0
DT_TOL_S = 0.5

AMPLITUDE = 0.15  # per-signal peak amplitude; headroom for up to 8 overlapping signals + noise


def is_sync_index(i: int) -> bool:
    return any(lo <= i < hi for lo, hi in SYNC_RANGES)


# -------------------- native binding --------------------

class Native:
    def __init__(self, dll_path: str):
        self.dll = ctypes.CDLL(os.path.abspath(dll_path))
        d = self.dll

        d.ft8_lib_version_check.restype = ctypes.c_int

        d.ft8_encode_message.restype = ctypes.c_int
        d.ft8_encode_message.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint8),
                                          ctypes.c_int]

        d.ft8_set_decode_params.restype = None
        d.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]

        d.ft8_set_candidate_diag_capture.restype = None
        d.ft8_set_candidate_diag_capture.argtypes = [ctypes.c_int]

        d.ft8_set_candidate_diag_llr_capture.restype = None
        d.ft8_set_candidate_diag_llr_capture.argtypes = [ctypes.c_int]

        d.ft8_get_last_candidate_diag.restype = ctypes.c_int
        d.ft8_get_last_candidate_diag.argtypes = [
            ctypes.POINTER(ctypes.c_float),   # out_freq_hz
            ctypes.POINTER(ctypes.c_float),   # out_dt
            ctypes.POINTER(ctypes.c_int16),   # out_score
            ctypes.POINTER(ctypes.c_uint8),   # out_decoded
            ctypes.POINTER(ctypes.c_float),   # out_prenorm_var
            ctypes.POINTER(ctypes.c_float),   # out_postnorm_mean_abs
            ctypes.c_int,                     # capacity
        ]

        d.ft8_get_last_candidate_llr.restype = ctypes.c_int
        d.ft8_get_last_candidate_llr.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int]

        FT8ResultArray = ctypes.c_float  # placeholder, ft8_decode_all uses a struct array
        class FT8Result(ctypes.Structure):
            _fields_ = [("freq_hz", ctypes.c_int), ("dt", ctypes.c_float),
                        ("snr", ctypes.c_int), ("message", ctypes.c_char * 36)]
        self.FT8Result = FT8Result

        d.ft8_decode_all.restype = ctypes.c_int
        d.ft8_decode_all.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int,
                                      ctypes.POINTER(FT8Result), ctypes.c_int]

        version = d.ft8_lib_version_check()
        if version != EXPECTED_SHIM_VERSION:
            print(f"[WARN] shim version {version}, expected {EXPECTED_SHIM_VERSION}",
                  file=sys.stderr)

        d.ft8_set_decode_params(10, ctypes.c_float(0.10), 60)
        d.ft8_set_candidate_diag_capture(1)
        d.ft8_set_candidate_diag_llr_capture(1)

    def encode(self, message: str) -> list[int]:
        buf = (ctypes.c_uint8 * FT8_NN)()
        rc = self.dll.ft8_encode_message(message.encode("ascii", errors="replace"), buf, FT8_NN)
        if rc != FT8_NN:
            raise RuntimeError(f"ft8_encode_message('{message}') -> {rc}")
        return list(buf)

    def true_codeword(self, message: str) -> list[int]:
        tones = self.encode(message)
        data_tones = [t for i, t in enumerate(tones) if not is_sync_index(i)]
        bits: list[int] = []
        for tone in data_tones:
            b3 = INV_GRAY[tone]
            bits.append((b3 >> 2) & 1)
            bits.append((b3 >> 1) & 1)
            bits.append(b3 & 1)
        return bits

    def decode_all(self, pcm: np.ndarray) -> list[dict]:
        assert pcm.shape == (BUFFER_SAMPLES,)
        pcm_c = (ctypes.c_float * BUFFER_SAMPLES)(*pcm.astype(np.float32))
        results = (self.FT8Result * 200)()
        n = self.dll.ft8_decode_all(pcm_c, BUFFER_SAMPLES, results, 200)
        if n < 0:
            print(f"[WARN] ft8_decode_all returned {n}", file=sys.stderr)

        cap = K_MAX_CANDIDATES
        out_freq = (ctypes.c_float * cap)()
        out_dt = (ctypes.c_float * cap)()
        out_score = (ctypes.c_int16 * cap)()
        out_decoded = (ctypes.c_uint8 * cap)()
        out_prenorm = (ctypes.c_float * cap)()
        out_postnorm = (ctypes.c_float * cap)()
        n_cand = self.dll.ft8_get_last_candidate_diag(out_freq, out_dt, out_score, out_decoded,
                                                        out_prenorm, out_postnorm, cap)
        out_llr = (ctypes.c_float * (cap * FTX_LDPC_N))()
        n_llr = self.dll.ft8_get_last_candidate_llr(out_llr, cap)
        assert n_llr == n_cand, f"candidate/llr count mismatch: {n_cand} vs {n_llr}"

        cands = []
        for i in range(n_cand):
            llr = [out_llr[i * FTX_LDPC_N + k] for k in range(FTX_LDPC_N)]
            cands.append({
                "freq_hz": out_freq[i], "dt": out_dt[i], "score": out_score[i],
                "decoded": bool(out_decoded[i]), "llr174": llr,
            })
        return cands


def nearest_candidate(freq: float, dt: float, cands: list[dict]) -> dict | None:
    best, best_fd = None, None
    for c in cands:
        fd = abs(c["freq_hz"] - freq)
        dd = abs(c["dt"] - dt)
        if fd <= FREQ_TOL_HZ and dd <= DT_TOL_S:
            if best is None or fd < best_fd:
                best, best_fd = c, fd
    return best


def hard_decision_ber(llr174: list[float], true_bits: list[int]) -> float:
    errors = 0
    for llr, tb in zip(llr174, true_bits):
        hd = 1 if llr > 0.0 else 0  # empirically-verified sign convention (c2_phase2c_ber_measurement.py)
        if hd != tb:
            errors += 1
    return errors / FTX_LDPC_N


# -------------------- synthesis --------------------

def synth_signal(tones: list[int], base_freq_hz: float, amplitude: float,
                  rng: np.random.Generator) -> np.ndarray:
    """Continuous-phase FSK, direct at 12 kHz."""
    out = np.zeros(SIG_SAMPLES, dtype=np.float64)
    phase = 0.0
    for sym in range(SYMBOL_COUNT):
        freq = base_freq_hz + tones[sym] * TONE_SPACING_HZ
        inc = 2.0 * math.pi * freq / SR
        idx0 = sym * SAMPLES_PER_SYMBOL
        n = np.arange(SAMPLES_PER_SYMBOL)
        seg_phase = phase + inc * n
        out[idx0:idx0 + SAMPLES_PER_SYMBOL] = amplitude * np.sin(seg_phase)
        phase = seg_phase[-1] + inc
    return out


def plant(buf: np.ndarray, sig: np.ndarray, dt: float) -> None:
    start = int(round(dt * SR))
    end = start + len(sig)
    assert end <= len(buf), f"planted signal exceeds buffer: start={start} end={end}"
    buf[start:end] += sig


def q_call(rng: random.Random) -> str:
    # NFR-021: Q-prefix synthetic callsigns, ITU-unallocated.
    return f"Q{rng.choice('0123456789')}{''.join(rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(3))}"


def make_message(rng: random.Random) -> str:
    grid = f"{rng.choice('ABCDEFGHIJKLMNOPQR')}{rng.choice('ABCDEFGHIJKLMNOPQR')}{rng.randint(0,9)}{rng.randint(0,9)}"
    return f"CQ {q_call(rng)} {grid}"


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return (0.0, 0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


# -------------------- arm drivers --------------------

def run_arm_a(native: Native, snr_grid: list[float], repeats: int, seed: int) -> list[dict]:
    """Isolated signals: 8 per buffer, well-separated frequency slots, same dt/SNR per buffer."""
    rng_py = random.Random(seed)
    measurements = []
    n_slots = 8
    slot_width = 3000.0 / n_slots  # spread across ~300-3300 Hz
    for snr_db in snr_grid:
        for rep in range(repeats):
            rng = np.random.default_rng(seed * 100003 + int(snr_db * 10) * 97 + rep)
            buf = np.zeros(BUFFER_SAMPLES, dtype=np.float64)
            dt = 0.6
            planted = []
            for slot in range(n_slots):
                base_freq = 300.0 + slot * slot_width + rng_py.uniform(20, slot_width - 60)
                msg = make_message(rng_py)
                tones = native.encode(msg)
                sig = synth_signal(tones, base_freq, AMPLITUDE, rng)
                plant(buf, sig, dt)
                planted.append((msg, base_freq, dt))
            # AWGN sized to per-signal amplitude (broadband time-domain ratio, see task spec Sec.3)
            noise_std = (AMPLITUDE / math.sqrt(2)) / (10 ** (snr_db / 20))
            buf += rng.normal(0.0, noise_std, size=BUFFER_SAMPLES)
            # Global linear rescale to keep the buffer inside [-1, 1] with headroom, rather than
            # clipping samples -- a fixed-level per-signal amplitude cannot keep pace with a wide
            # noise sweep, and clipping is a nonlinear channel the "let the channel generate the
            # LLRs" design (22:30 ruling Sec.5) explicitly does not want. A linear rescale changes
            # nothing about the SNR ratio (both signal and noise are scaled together).
            peak = np.max(np.abs(buf))
            clipped = 0
            if peak > 0.9:
                buf *= 0.9 / peak
            cands = native.decode_all(buf)
            for msg, base_freq, pdt in planted:
                true_bits = native.true_codeword(msg)
                cand = nearest_candidate(base_freq, pdt, cands)
                if cand is None:
                    measurements.append({"arm": "A", "snr_db": snr_db, "located": False})
                    continue
                ber = hard_decision_ber(cand["llr174"], true_bits)
                measurements.append({"arm": "A", "snr_db": snr_db, "located": True,
                                      "ber": ber, "decoded": cand["decoded"],
                                      "clipped": int(clipped)})
    return measurements


def run_arm_b(native: Native, snr_grid: list[float], repeats: int, seed: int) -> list[dict]:
    """Co-channel pairs: 4 pairs per buffer (one per delta-f), same dt within a pair."""
    rng_py = random.Random(seed + 1)
    measurements = []
    deltas = [0.0, 3.0, 7.0, 15.0]
    n_pairs = len(deltas)
    slot_width = 3000.0 / n_pairs
    for snr_db in snr_grid:
        for rep in range(repeats):
            rng = np.random.default_rng(seed * 200003 + int(snr_db * 10) * 97 + rep + 500000)
            buf = np.zeros(BUFFER_SAMPLES, dtype=np.float64)
            dt = 0.6
            planted = []
            for pi, delta in enumerate(deltas):
                base_freq = 300.0 + pi * slot_width + rng_py.uniform(60, slot_width - 60)
                for which in range(2):
                    f = base_freq + (delta if which == 1 else 0.0)
                    msg = make_message(rng_py)
                    tones = native.encode(msg)
                    sig = synth_signal(tones, f, AMPLITUDE, rng)
                    plant(buf, sig, dt)
                    planted.append((msg, f, dt, delta))
            noise_std = (AMPLITUDE / math.sqrt(2)) / (10 ** (snr_db / 20))
            buf += rng.normal(0.0, noise_std, size=BUFFER_SAMPLES)
            peak = np.max(np.abs(buf))
            clipped = 0
            if peak > 0.9:
                buf *= 0.9 / peak
            cands = native.decode_all(buf)
            for msg, f, pdt, delta in planted:
                true_bits = native.true_codeword(msg)
                cand = nearest_candidate(f, pdt, cands)
                if cand is None:
                    measurements.append({"arm": "B", "snr_db": snr_db, "delta_hz": delta,
                                          "located": False})
                    continue
                ber = hard_decision_ber(cand["llr174"], true_bits)
                measurements.append({"arm": "B", "snr_db": snr_db, "delta_hz": delta,
                                      "located": True, "ber": ber, "decoded": cand["decoded"],
                                      "clipped": int(clipped)})
    return measurements


# -------------------- binning / reporting --------------------

def bin_curve(measurements: list[dict], bin_width: float = 2.5) -> list[dict]:
    located = [m for m in measurements if m.get("located")]
    bins: dict[int, list[dict]] = {}
    for m in located:
        b = int(m["ber"] * 100 // bin_width)
        bins.setdefault(b, []).append(m)
    out = []
    for b in sorted(bins):
        items = bins[b]
        n = len(items)
        k = sum(1 for m in items if m["decoded"])
        p, lo, hi = wilson_interval(k, n)
        lo_pct = b * bin_width
        out.append({"ber_lo": lo_pct, "ber_hi": lo_pct + bin_width, "n": n, "k": k,
                     "p": p, "ci_lo": lo, "ci_hi": hi})
    return out


def p_decode_from_curve(curve: list[dict], ber: float) -> float:
    """Nearest-bin lookup; falls back to nearest populated bin at the edges."""
    ber_pct = ber * 100
    best, best_d = None, None
    for row in curve:
        mid = (row["ber_lo"] + row["ber_hi"]) / 2
        d = abs(mid - ber_pct)
        if best is None or d < best_d:
            best, best_d = row, d
    if best is None:
        return 0.0
    return best["p"]


def percentile_from_curve_located(measurements: list[dict], pct: float) -> float:
    bers = sorted(m["ber"] for m in measurements if m.get("located"))
    if not bers:
        return float("nan")
    idx = min(len(bers) - 1, int(round(pct / 100 * (len(bers) - 1))))
    return bers[idx]


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    print(f"Loading DLL: {DLL_PATH}")
    native = Native(DLL_PATH)

    snr_grid = [x / 2 for x in range(-8, -56, -1)]  # -4.0 down to -27.5 dB in 0.5 dB steps
    repeats = int(os.environ.get("B2_REPEATS", "3"))
    seed = 20260726

    print(f"Arm A: {len(snr_grid)} SNR levels x {repeats} repeats x 8 signals/buffer")
    t1 = time.time()
    arm_a = run_arm_a(native, snr_grid, repeats, seed)
    print(f"  done in {time.time() - t1:.1f}s, {len(arm_a)} planted-signal measurements "
          f"({sum(1 for m in arm_a if m['located'])} located)")

    print(f"Arm B: {len(snr_grid)} SNR levels x {repeats} repeats x 4 pairs (8 signals)/buffer")
    t1 = time.time()
    arm_b = run_arm_b(native, snr_grid, repeats, seed)
    print(f"  done in {time.time() - t1:.1f}s, {len(arm_b)} planted-signal measurements "
          f"({sum(1 for m in arm_b if m['located'])} located)")

    with open(os.path.join(OUT_DIR, "arm_a_raw.json"), "w") as fh:
        json.dump(arm_a, fh)
    with open(os.path.join(OUT_DIR, "arm_b_raw.json"), "w") as fh:
        json.dump(arm_b, fh)

    curve_a = bin_curve(arm_a)
    curve_b = bin_curve(arm_b)

    print()
    print("ARM A (isolated) -- P(decode | BER)")
    print(f"{'BER bin':>12} {'n':>5} {'k':>5} {'P':>7} {'CI_lo':>7} {'CI_hi':>7}")
    for row in curve_a:
        print(f"{row['ber_lo']:>5.1f}-{row['ber_hi']:<5.1f} {row['n']:>5} {row['k']:>5} "
              f"{row['p']:>6.1%} {row['ci_lo']:>6.1%} {row['ci_hi']:>6.1%}")

    print()
    print("ARM B (co-channel, pooled deltas) -- P(decode | BER)")
    print(f"{'BER bin':>12} {'n':>5} {'k':>5} {'P':>7} {'CI_lo':>7} {'CI_hi':>7}")
    for row in curve_b:
        print(f"{row['ber_lo']:>5.1f}-{row['ber_hi']:<5.1f} {row['n']:>5} {row['k']:>5} "
              f"{row['p']:>6.1%} {row['ci_lo']:>6.1%} {row['ci_hi']:>6.1%}")

    print()
    print("Per-delta breakdown, Arm B:")
    delta_curves = {}
    for delta in [0.0, 3.0, 7.0, 15.0]:
        sub = [m for m in arm_b if m.get("delta_hz") == delta]
        curve_d = bin_curve(sub)
        delta_curves[delta] = curve_d
        n_planted = len(sub)
        n_located = sum(1 for m in sub if m["located"])
        print(f"  delta={delta}Hz: n_planted={n_planted} n_located={n_located} "
              f"({n_located / max(1, n_planted):.1%} location rate)")
        print(f"    {'BER bin':>12} {'n':>5} {'k':>5} {'P':>7}")
        for row in curve_d:
            print(f"    {row['ber_lo']:>5.1f}-{row['ber_hi']:<5.1f} {row['n']:>5} "
                  f"{row['k']:>5} {row['p']:>6.1%}")
    with open(os.path.join(OUT_DIR, "delta_curves.json"), "w") as fh:
        json.dump({str(k): v for k, v in delta_curves.items()}, fh, indent=2)

    n_clipped = sum(1 for m in arm_a + arm_b if m.get("clipped", 0) > 0)
    print(f"\nBuffers with any clipped sample: informational count across measurements = "
          f"{n_clipped} (each buffer contributes multiple measurement rows)")

    with open(os.path.join(OUT_DIR, "curve_a.json"), "w") as fh:
        json.dump(curve_a, fh, indent=2)
    with open(os.path.join(OUT_DIR, "curve_b.json"), "w") as fh:
        json.dump(curve_b, fh, indent=2)

    # -- E estimator (22:30 ruling Sec.6): reuse c2_phase2c_ber_measurement.py's THE-135
    # population/measurement, do not re-derive it. --
    print()
    print("=" * 70)
    print("E ESTIMATOR (THE 135, using Arm B's curve per Sec.6)")
    print("=" * 70)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import c2_phase2c_ber_measurement as ber_mod

    cycles = sorted(os.path.splitext(f)[0]
                     for f in os.listdir(ber_mod.WAV68_DIR) if f.endswith(".wav"))
    pop135 = ber_mod.compute_135_population(cycles)
    k10_cand_by_cycle = ber_mod.load_candidate_diag_with_llr(
        os.path.join(ber_mod.K10_CAP_DIR, "candidate_diag.csv"))
    encoder = ber_mod.Encoder(ber_mod.DLL_PATH)
    bers135 = ber_mod.measure_population("THE 135", pop135, k10_cand_by_cycle, encoder,
                                          require_decoded=False)
    print(f"THE 135: n measured = {len(bers135)}")

    e_from_b = sum(p_decode_from_curve(curve_b, ber) for ber in bers135)
    e_from_a = sum(p_decode_from_curve(curve_a, ber) for ber in bers135)
    print(f"E (Arm B curve) = {e_from_b:.2f}")
    print(f"E (Arm A curve, for comparison) = {e_from_a:.2f}")

    bers135_sorted = sorted(bers135)
    if bers135_sorted:
        def pct(p):
            idx = min(len(bers135_sorted) - 1, int(round(p / 100 * (len(bers135_sorted) - 1))))
            return bers135_sorted[idx]
        b10, b50, b90 = pct(10), pct(50), pct(90)
        n_below_b50 = sum(1 for b in bers135 if b <= b50)
        print(f"B10={b10:.1%} B50={b50:.1%} B90={b90:.1%}  N(BER<=B50)={n_below_b50}")

    with open(os.path.join(OUT_DIR, "e_estimator.json"), "w") as fh:
        json.dump({"e_from_b": e_from_b, "e_from_a": e_from_a, "n_135_measured": len(bers135),
                    "bers135": bers135}, fh, indent=2)

    print(f"\nTotal wall time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
