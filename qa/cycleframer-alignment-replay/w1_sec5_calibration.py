#!/usr/bin/env python3
"""D-001 W1 -- the standing Sec.5 calibration: P(decode | measured BER), Arm A / Arm B.

Spec: `2026-08-07-2241-architect-to-qa-consolidated-work-queue.md` Sec.2 (and its pointer,
`2026-07-26-2230-architect-sec6-redesign-ruling.md` Sec.5/Sec.6, same design, unchanged).

Principle (pre-registered, do not deviate): STOP CHOOSING THE LLRs, LET THE CHANNEL GENERATE
THEM. Plants Q-prefix synthetic signals of KNOWN ground truth (via `qa/rr-study/synth`'s
`assemble_symbols()` -- codeword -> tones -> GFSK), adds real AWGN via
`qa/rr-study/synth.channel.mix_to_shared_floor` (real receiver model: one shared noise floor,
each station's own SNR relative to it), decodes through the UNMODIFIED shipped decode path
(`ft8_set_decode_params(10, 0.10, 60)`, `K_MAX_CANDIDATES`=140 -- verified against
`src/OpenWSFZ.Ft8/Native/ft8_shim.c` before this script was written, see the dated findings doc),
and reads each located candidate's raw 174 LLRs + `decoded` flag via the existing opt-in
diagnostic exports. Never hand-constructs or injects bit errors directly -- that is the exact
defect that sank C.5a (`2026-07-26-2230-...` Sec.4; retracted `2026-08-07`, see
`2026-08-07-2241-...` Sec.0/Sec.1.1).

Runs against a WORKTREE-LOCAL diagnostic build, `native/ft8_lib_build/libft8_diag_llr.dll`,
compiled from THIS worktree's `d001-c4-min-score-sweep` sources with
`-DFT8_ENABLE_RAW_LLR_CAPTURE=1` (see `native/ft8_lib_build/rebuild_diag_llr.bat`, added by this
session): the branch's COMMITTED `win-x64/libft8.dll` has that capture compile-time-gated OFF by
default (shim 20260035, gate added 2026-07-27, `FT8_ENABLE_RAW_LLR_CAPTURE`) and would silently
return 0 raw LLRs -- see `ft8_shim.c`'s own documented contract for
`ft8_get_last_candidate_llr` when the gate is off. `ft8_set_llr_shrinkage` is NEVER called (stays
at its default 0.0 no-op) -- that mechanism was closed on evidence in a separate investigation
(C.2 Phase 2) and using it here would contaminate this measurement.

NFR-021: Q-prefix synthetic callsigns only, generated fresh and distinct for every planted signal
across the ENTIRE sweep (a global uniqueness registry enforces this) -- the native hash-dedup at
`ft8_shim.c` (and the session-scoped cross-cycle hashed-callsign table) would otherwise risk
collapsing a repeat and reading a dedup artefact as a decode failure. No message text or per-
candidate record is ever printed; only aggregate/binned statistics. ASCII-only console output
(HK-009).
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

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(HERE, "..", "..")
SYNTH_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
sys.path.insert(0, SYNTH_ROOT)
from synth import packing, crc, ldpc, symbols, modulator, channel  # noqa: E402
from synth.constants import REFERENCE_BANDWIDTH_HZ  # noqa: E402

DLL_PATH = os.path.join(REPO_ROOT, "native", "ft8_lib_build", "libft8_diag_llr.dll")
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "d001_w1_sec5_calibration")

EXPECTED_SHIM_VERSION = 20260035

SR = 12_000
BUFFER_SAMPLES = 180_000  # 15 s at 12 kHz -- matches FT8_EXPECTED_SAMPLES exactly
SLOT_LENGTH_S = 15.0
FT8_NN = 79
FTX_LDPC_N = 174
SYNC_RANGES = [(0, 7), (36, 43), (72, 79)]
GRAY_MAP = [0, 1, 3, 2, 5, 6, 4, 7]  # kFT8_Gray_map -- verified against the native encoder below
INV_GRAY = [0] * 8
for _i, _v in enumerate(GRAY_MAP):
    INV_GRAY[_v] = _i

K_MAX_CANDIDATES = 140
FREQ_TOL_HZ = 10.0  # reused, not re-derived (c2_phase2c_ber_measurement.py)
DT_TOL_S = 0.5

F_MIN_HZ = 350.0
F_MAX_HZ = 2750.0

_seen_messages: set[str] = set()


# -------------------- native binding (mirrors b2_synthetic_calibration.Native) --------------------

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
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_int16), ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.c_int,
        ]

        d.ft8_get_last_candidate_llr.restype = ctypes.c_int
        d.ft8_get_last_candidate_llr.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_int]

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
        self.version = version

        # Shipped config -- verified against ft8_shim.c before this script was written
        # (K_MIN_SCORE=10, K_MAX_CANDIDATES=140, defaults s_k_min_score_pass2=10,
        # s_osd_corr_threshold=0.10f, s_osd_nhard_max=60 -- this call is a documented no-op
        # against those defaults, made explicit per the spec). ft8_set_llr_shrinkage is
        # DELIBERATELY NEVER CALLED -- stays at its default 0.0 (exact no-op, closed on
        # evidence in C.2 Phase 2).
        d.ft8_set_decode_params(10, ctypes.c_float(0.10), 60)
        d.ft8_set_candidate_diag_capture(1)
        d.ft8_set_candidate_diag_llr_capture(1)

    def encode_tones(self, message: str) -> list[int]:
        buf = (ctypes.c_uint8 * FT8_NN)()
        rc = self.dll.ft8_encode_message(message.encode("ascii", errors="replace"), buf, FT8_NN)
        if rc != FT8_NN:
            raise RuntimeError(f"ft8_encode_message failed, rc={rc}")
        return list(buf)

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


# -------------------- message / ground-truth generation --------------------

def q_call(rng: random.Random) -> str:
    return f"Q{rng.choice('123456789')}{''.join(rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(3))}"


def make_message(rng: random.Random) -> str:
    """Fresh, distinct 'CQ <Q-call> <grid>' message. Enforces global uniqueness across the
    ENTIRE sweep (not just within one buffer) per the mandatory-distinctness instruction --
    ft8_shim.c's hash dedup would otherwise silently collapse a repeat and read as a decode
    failure that is actually a dedup artefact."""
    for _ in range(1000):
        grid = (f"{rng.choice('ABCDEFGHIJKLMNOPQR')}{rng.choice('ABCDEFGHIJKLMNOPQR')}"
                f"{rng.randint(0, 9)}{rng.randint(0, 9)}")
        msg = f"CQ {q_call(rng)} {grid}"
        if msg not in _seen_messages:
            _seen_messages.add(msg)
            return msg
    raise RuntimeError("could not generate a fresh distinct message after 1000 tries")


def true_codeword_and_tones(message: str) -> tuple[list[int], list[int]]:
    """Ground truth from qa/rr-study/synth (confirmed-reusable path, cross-validated bit-for-bit
    against the native ft8_encode_message + Gray-decode convention for 5 message forms before
    this script was written -- see the dated findings doc Sec.2)."""
    message_bits = packing.pack_message(message)
    message_plus_crc = crc.append_crc(message_bits)
    codeword = ldpc.encode_ldpc(message_plus_crc)
    tones = symbols.assemble_symbols(codeword)
    return codeword, tones


# -------------------- candidate matching / BER --------------------

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
    """Empirically-validated sign convention, reused not re-derived
    (c2_phase2c_ber_measurement.py's hard_decision_ber docstring)."""
    errors = 0
    for llr, tb in zip(llr174, true_bits):
        hd = 1 if llr > 0.0 else 0
        if hd != tb:
            errors += 1
    return errors / FTX_LDPC_N


# -------------------- buffer builders --------------------

def freq_slots_arm_a(n: int, rng: random.Random) -> list[float]:
    span = F_MAX_HZ - F_MIN_HZ
    step = span / n
    jitter = min(70.0, step * 0.22)  # guarantees min gap >= step - 2*jitter >= step*0.56 > 150 Hz for n<=9
    return [F_MIN_HZ + step * (i + 0.5) + rng.uniform(-jitter, jitter) for i in range(n)]


def build_buffer_arm_a(native: Native, rng_py: random.Random, rng_np: np.random.Generator,
                        snr_list: list[float]) -> tuple[np.ndarray, list[dict]]:
    """8-10 isolated planted signals/buffer, >=150 Hz apart, each own freq/dt/SNR, one shared
    AWGN floor (mix_to_shared_floor -- real single-receiver model)."""
    n = len(snr_list)
    freqs = freq_slots_arm_a(n, rng_py)
    rng_py.shuffle(freqs)  # decorrelate slot position from SNR-list order
    clean_signals = []
    planted = []
    for freq, snr_db in zip(freqs, snr_list):
        msg = make_message(rng_py)
        codeword, tones = true_codeword_and_tones(msg)
        dt = rng_py.uniform(0.2, 2.0)
        sig = modulator.modulate(tones, freq, dt_s=dt, sample_rate_hz=SR, slot_length_s=SLOT_LENGTH_S)
        clean_signals.append(sig)
        planted.append({"freq": freq, "dt": dt, "codeword": codeword, "snr_db": snr_db})
    seed = int(rng_np.integers(0, 2**31 - 1))
    buf = channel.mix_to_shared_floor(clean_signals, snr_list, seed,
                                       sample_rate_hz=SR, bandwidth_hz=REFERENCE_BANDWIDTH_HZ)
    return buf, planted


def build_buffer_arm_b(native: Native, rng_py: random.Random, rng_np: np.random.Generator,
                        pair_snrs: list[float], deltas: list[float]) -> tuple[np.ndarray, list[dict]]:
    """Co-channel pairs/buffer: len(pair_snrs) pairs, one per delta in `deltas` (cycled if fewer
    deltas than pairs), each pair at a shared dt and near-identical SNR (+/-0.5 dB jitter)."""
    n_pairs = len(pair_snrs)
    base_freqs = freq_slots_arm_a(n_pairs, rng_py)
    rng_py.shuffle(base_freqs)
    clean_signals = []
    snr_list = []
    planted = []
    for i, (base_freq, pair_snr) in enumerate(zip(base_freqs, pair_snrs)):
        delta = deltas[i % len(deltas)]
        dt = rng_py.uniform(0.2, 2.0)
        for which in range(2):
            f = base_freq + (delta if which == 1 else 0.0)
            msg = make_message(rng_py)
            codeword, tones = true_codeword_and_tones(msg)
            sig = modulator.modulate(tones, f, dt_s=dt, sample_rate_hz=SR, slot_length_s=SLOT_LENGTH_S)
            snr = pair_snr + rng_py.uniform(-0.5, 0.5)
            clean_signals.append(sig)
            snr_list.append(snr)
            planted.append({"freq": f, "dt": dt, "codeword": codeword, "snr_db": snr,
                             "delta_hz": delta, "pair": i})
    seed = int(rng_np.integers(0, 2**31 - 1))
    buf = channel.mix_to_shared_floor(clean_signals, snr_list, seed,
                                       sample_rate_hz=SR, bandwidth_hz=REFERENCE_BANDWIDTH_HZ)
    return buf, planted


def measure_buffer(native: Native, buf: np.ndarray, planted: list[dict], arm: str) -> list[dict]:
    peak = float(np.max(np.abs(buf)))
    scale = 1.0
    if peak > 0.95:
        scale = 0.95 / peak
        buf = buf * scale
    cands = native.decode_all(buf)
    out = []
    for p in planted:
        cand = nearest_candidate(p["freq"], p["dt"], cands)
        row = {"arm": arm, "snr_db": p["snr_db"], "peak_scaled": scale != 1.0}
        if "delta_hz" in p:
            row["delta_hz"] = p["delta_hz"]
        if cand is None:
            row["located"] = False
            out.append(row)
            continue
        ber = hard_decision_ber(cand["llr174"], p["codeword"])
        row.update({"located": True, "ber": ber, "decoded": cand["decoded"],
                     "score": cand["score"]})
        out.append(row)
    return out


# -------------------- binning / Wilson CI --------------------

def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return (0.0, 0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


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


def p_decode_interp(curve: list[dict], ber: float) -> float:
    """Linear interpolation between bin-centre P(decode) values; nearest-bin at the edges.
    Documented per the task spec's requirement to pick and disclose one defensible method."""
    ber_pct = ber * 100
    if not curve:
        return 0.0
    centres = [(row["ber_lo"] + row["ber_hi"]) / 2 for row in curve]
    ps = [row["p"] for row in curve]
    if ber_pct <= centres[0]:
        return ps[0]
    if ber_pct >= centres[-1]:
        return ps[-1]
    for i in range(len(centres) - 1):
        if centres[i] <= ber_pct <= centres[i + 1]:
            span = centres[i + 1] - centres[i]
            if span <= 0:
                return ps[i]
            t = (ber_pct - centres[i]) / span
            return ps[i] * (1 - t) + ps[i + 1] * t
    return ps[-1]


def p_decode_nearest(curve: list[dict], ber: float) -> float:
    ber_pct = ber * 100
    best, best_d = None, None
    for row in curve:
        mid = (row["ber_lo"] + row["ber_hi"]) / 2
        d = abs(mid - ber_pct)
        if best is None or d < best_d:
            best, best_d = row, d
    return 0.0 if best is None else best["p"]


def transition_coverage(curve: list[dict], lo_p: float = 0.05, hi_p: float = 0.95) -> list[dict]:
    """Bins whose P(decode) sits strictly between lo_p and hi_p -- the 'transition region'
    the sample-size target (>=40/bin) applies to."""
    return [row for row in curve if lo_p < row["p"] < hi_p]


def pct_from_list(values: list[float], pct: float) -> float:
    s = sorted(values)
    if not s:
        return float("nan")
    idx = min(len(s) - 1, int(round(pct / 100 * (len(s) - 1))))
    return s[idx]


def curve_crossing(curve: list[dict], target_p: float) -> float:
    """BER (fraction, 0-1) at which the curve first crosses target_p, walking bin centres from
    low BER to high BER; linear-interpolated between adjacent bin centres. NaN if the curve never
    spans target_p."""
    if not curve:
        return float("nan")
    pts = [((row["ber_lo"] + row["ber_hi"]) / 2, row["p"]) for row in curve]
    for i in range(len(pts) - 1):
        (b0, p0), (b1, p1) = pts[i], pts[i + 1]
        if (p0 - target_p) * (p1 - target_p) <= 0 and p0 != p1:
            t = (target_p - p0) / (p1 - p0)
            return (b0 + t * (b1 - b0)) / 100.0
    # fallback: nearest point
    nearest = min(pts, key=lambda pb: abs(pb[1] - target_p))
    return nearest[0] / 100.0


if __name__ == "__main__":
    print("w1_sec5_calibration.py is a library; run w1_run_sweep.py to execute the measurement.")
