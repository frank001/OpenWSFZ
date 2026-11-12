#!/usr/bin/env python3
"""CS-CEIL library (spec arch/cs-model-ceiling 6d911263 + Amendment 1 section 8, fc82317a; QA (k) review ab9c690c). QA tooling: no src/ or native/ change, no replay, no station.
Pure functions and constants first (the self-test drives them on synthetic data); the data loaders are at the bottom.  HK-037: message text is read in memory by the worker that needs
it (the fit and the forced legs) and is never persisted; every file written holds stamps, indices and numbers only.  Every inherited constant is an ASSERTION here, not a reminder.

RELOCATION (spec 1): for a row, fit ITS OWN signal on the stored R3 (R2 in the 18 cycles without R3) with the product fitter (ft8_subfeas_fit_signal) data-aided from WSJT-X's tones,
start (dt + DELTA_P, freq); take the real part of the frequency-shifted analytic waveform; add it into the nearest qualifying empty 60 Hz slot of the SAME cycle; run gr_forced.force_cycle
UNCHANGED at (freq + delta, same dt).  Decodable = forced primary found OR forced coherent v3_match (sc_analyse.either).

SLOT RULE (frozen as code, spec 1 + A1.3 + F1):
  window [f_s, f_s + 60) on a 6.25 Hz grid inside [300, 2700]; blocked if ANY n_ref row or ANY decode of ours (any batch) of the cycle has a frequency in [f_s - 60, f_s + 120);
  the copy's base frequency = f_s + COPY_OFFSET_HZ, so delta = f_s + 5 - f_row; the row's own band = [f_row - 5, f_row + 55).
  TAIL (F1, measured on these buffers: per-cycle max WSJT-X dt has median 1.7 s, so a fixed 13.2-14.8 s window is inside late signals): the tail window starts at
  t0 = max(13.2 s, latest END of any n_ref row whose 50 Hz signal overlaps the row's own band, end = dt + DELTA_P + 12.64 s) and runs to 14.9 s; it must be >= TAIL_MIN_S long, else the row has NO SLOT.
  The slot's tail PSD and the row's own-band tail PSD, both over that same window, must be within +-1.0 dB.
  IN-WINDOW (A1.3): the slot's PSD over [0.5, 13.1] s minus its own tail PSD must be <= X dB, X = median of that difference over every (row, slot) pair passing the blocker and tail
  conditions + 1.0 dB (the no-copy pilot, at freeze).
  The qualifying slot NEAREST in frequency to the row (centre to centre; ties: the lower frequency).  No slot => the row is excluded and counted (A1.2).
PSD = Hann periodogram, 2|X|^2 / (fs sum w^2), mean over the band's bins, in dB, so windows of different lengths compare."""
from __future__ import annotations

import json
import math
import os
import random
import sys

import numpy as np

# --------------------------------------------------------------------------------------------- frozen constants
SEED = 20261112
B_BOOT = 2000
N_REF = 12124
N_CYCLES = 400
FS = 12000
PCM = 180000
DELTA_P, DELTA_C = 0.6, 0.7                    # GAP-RELOCATE deltas.json (frozen); asserted against the file in cc_prep
SIGNAL_S = 79 * 0.16                           # 12.64 s
SIGNAL_HZ = 50.0                               # 8 tones x 6.25 Hz
SLOT_W, F_LO, F_HI, STEP = 60.0, 300.0, 2700.0, 6.25
BLOCK_LO, BLOCK_HI = 60.0, 120.0               # blocked if a freq in [f_s - 60, f_s + 120)
COPY_OFFSET_HZ = 5.0
ROW_LO, ROW_HI = 5.0, 55.0                     # row's own band [f - 5, f + 55)
TAIL_FLOOR_START, TAIL_END, TAIL_MIN_S = 13.2, 14.9, 0.4
IN_LO, IN_HI = 0.5, 13.1
TOL_DB = 1.0                                   # spec 1: tail floor within +-1.0 dB
X_PLUS_DB = 1.0                                # A1.3: X = median + 1.0 dB
BAR_PP = 1.0                                   # CS-REFIT's BUILD-WORTH bar (spec 4, HK-038: a prize threshold)
V_REPRO, V_SLOT, V_REL = 0.98, 0.90, 0.80
N_CTRL_HIT = 300
BANDS = ("A", "B", "C", "D")
assert (SEED, B_BOOT, N_REF, N_CYCLES, PCM) == (20261112, 2000, 12124, 400, 180000)
assert abs(SIGNAL_S - 12.64) < 1e-9 and (BAR_PP, V_REPRO, V_SLOT, V_REL, N_CTRL_HIT) == (1.0, 0.98, 0.90, 0.80, 300)
assert (DELTA_P, DELTA_C, TOL_DB, X_PLUS_DB) == (0.6, 0.7, 1.0, 1.0) and SLOT_W == 60.0 and STEP == 6.25 and (F_LO, F_HI) == (300.0, 2700.0)


# --------------------------------------------------------------------------------------------- PSD and slots
def hann_psd_prefix(seg: np.ndarray):
    """-> (prefix sums of the periodogram over bins, freq of bin 0 = 0, bin width Hz).  PSD(f) = 2|X|^2 / (fs sum w^2)."""
    n = len(seg)
    w = np.hanning(n)
    x = np.fft.rfft(seg.astype(np.float64) * w)
    psd = 2.0 * (x.real ** 2 + x.imag ** 2) / (FS * float(np.sum(w * w)))
    return np.concatenate(([0.0], np.cumsum(psd))), FS / n


def band_db(prefix, binw, f_lo, f_hi):
    """mean PSD over the bins whose centre lies in [f_lo, f_hi), in dB (None if no bin)."""
    i0 = int(math.ceil(f_lo / binw))
    i1 = int(math.ceil(f_hi / binw))
    i0, i1 = max(i0, 0), min(i1, len(prefix) - 1)
    if i1 <= i0:
        return None
    m = (prefix[i1] - prefix[i0]) / (i1 - i0)
    return 10.0 * math.log10(max(m, 1e-300))


def slot_grid():
    n = int(round((F_HI - SLOT_W - F_LO) / STEP)) + 1
    return [F_LO + k * STEP for k in range(n)]


def blocked(f_s, freqs):
    return any(f_s - BLOCK_LO <= f < f_s + BLOCK_HI for f in freqs)


def tail_start(row_f, others):
    """others = [(freq, dt)] of every n_ref row of the cycle (the row itself included).  Latest END of a signal overlapping the row's own band."""
    lo, hi = row_f - ROW_LO, row_f + ROW_HI
    t0 = TAIL_FLOOR_START
    for f, dt in others:
        if f < hi and f + SIGNAL_HZ > lo:
            t0 = max(t0, dt + DELTA_P + SIGNAL_S)
    return t0


def choose_slot(row_f, tail_row_db, tail_slot_db, in_slot_db, freqs_block, x_db, collect=None):
    """tail_slot_db / in_slot_db: dict f_s -> dB (or None).  Returns the nearest qualifying f_s or None.  collect (list) receives in-tail differences of pairs passing blocker + tail."""
    best = None
    row_c = row_f + SIGNAL_HZ / 2.0
    for f_s in slot_grid():
        if blocked(f_s, freqs_block):
            continue
        ts, tin = tail_slot_db.get(f_s), in_slot_db.get(f_s)
        if ts is None or tin is None or tail_row_db is None:
            continue
        if abs(ts - tail_row_db) > TOL_DB:
            continue
        diff = tin - ts
        if collect is not None:
            collect.append(diff)
        if x_db is not None and diff > x_db:
            continue
        d = abs((f_s + SLOT_W / 2.0) - row_c)
        key = (d, f_s)
        if best is None or key < best[0]:
            best = (key, f_s)
    return None if best is None else best[1]


def relocation_delta(f_s, row_f):
    return f_s + COPY_OFFSET_HZ - row_f


# --------------------------------------------------------------------------------------------- the copy
def shift_copy(shat: np.ndarray, re_: np.ndarray, im_: np.ndarray, delta_hz: float) -> np.ndarray:
    """Real part of the analytic waveform of shat (re_ + j im_, from ft8_subfeas_compute_analytic) shifted by delta_hz, float32."""
    t = np.arange(PCM, dtype=np.float64) / FS
    ph = 2.0 * math.pi * delta_hz * t
    return (re_.astype(np.float64) * np.cos(ph) - im_.astype(np.float64) * np.sin(ph)).astype(np.float32)


# --------------------------------------------------------------------------------------------- groups
def band_quota(counts: dict, total: int):
    """Largest-remainder allocation of `total` over the bands in proportion to counts."""
    s = sum(counts.values())
    raw = {b: total * counts.get(b, 0) / s for b in BANDS}
    base = {b: int(math.floor(raw[b])) for b in BANDS}
    rem = total - sum(base.values())
    for b in sorted(BANDS, key=lambda b: (-(raw[b] - base[b]), b))[:rem]:
        base[b] += 1
    assert sum(base.values()) == total
    return base


def draw_ctrl_hit(cands: list, quota: dict, seed: int = SEED):
    """cands: [(stamp, idx, band)] eligible CS hits.  Draw quota[b] per band, random.Random(seed) on the sorted list, without replacement."""
    rng = random.Random(seed)
    out = []
    for b in BANDS:
        pool = sorted(c for c in cands if c[2] == b)
        assert len(pool) >= quota[b], ("CTRL-HIT band short", b, len(pool), quota[b])
        out += rng.sample(pool, quota[b])
    return sorted(out)


# --------------------------------------------------------------------------------------------- readout (pure; the self-test drives it)
def either(rec):
    if rec is None or rec.get("unencodable"):
        return False
    return bool((rec.get("fp") or {}).get("found") or (rec.get("fc") or {}).get("v3_match"))


def boot_indices(ncyc=N_CYCLES, b=B_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    return rng.integers(0, ncyc, size=(b, ncyc))


def ci(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [float("nan"), float("nan")]


def readout(cyc: dict, idx: np.ndarray):
    """cyc: per-cycle numpy arrays (length 400):
         nref                       n_ref rows of the cycle
         ns_dec, ns_fitzero, ns_noslot   CS-NR rows: decodable relocated / fit-zero / no slot
         pure_dec, pure_copy        CS-pure rows: decodable relocated / rows with a copy
         hit_dec, hit_copy          CTRL-HIT rows decodable relocated / rows with a copy
         weak_dec, weak_copy        CTRL-WEAK rows decodable relocated / rows with a copy
       Returns the point values, the CIs and the verdict inputs.  RAW_worst counts fit-zero AND no-slot rows as rescued (A1.2); NET-CEIL counts both as not rescued."""
    g = lambda k: cyc[k].astype(float)
    nref = g("nref")
    raw_n = g("ns_dec") + g("ns_fitzero") + g("ns_noslot")

    def point(sel):
        d = nref[sel].sum()
        rl_hit = g("hit_dec")[sel].sum() / max(g("hit_copy")[sel].sum(), 1e-12)
        rl_weak = g("weak_dec")[sel].sum() / max(g("weak_copy")[sel].sum(), 1e-12)
        raw = 100.0 * raw_n[sel].sum() / d
        net = 100.0 * (g("pure_dec")[sel].sum() - rl_weak * g("pure_copy")[sel].sum()) / d
        return raw, rl_hit, rl_weak, net

    allc = np.arange(len(nref))
    raw0, rlh0, rlw0, net0 = point(allc)
    raws, rlhs, rlws, nets = [], [], [], []
    for row in idx:
        r, h, w, n = point(row)
        raws.append(r)
        rlhs.append(h)
        rlws.append(w)
        nets.append(n)
    raws, rlhs, rlws, nets = map(np.asarray, (raws, rlhs, rlws, nets))
    ratio = np.where(rlhs > 0, raws / np.where(rlhs > 0, rlhs, 1.0), np.inf)
    out = {"RAW_worst_pp": raw0, "RAW_worst_pp_CI": ci(raws), "RL_CTRL_HIT": rlh0, "RL_CTRL_HIT_CI": ci(rlhs), "RL_CTRL_WEAK": rlw0, "RL_CTRL_WEAK_CI": ci(rlws),
           "RAW_over_RL_pp": raw0 / rlh0 if rlh0 > 0 else float("inf"), "RAW_over_RL_pp_CI": ci(np.where(np.isfinite(ratio), ratio, np.nan)),
           "RAW_over_RL_hi_incl_inf": float(np.percentile(ratio, 97.5)), "NET_CEIL_pp": net0, "NET_CEIL_pp_CI": ci(nets),
           "F3_RAW_over_RL_ge_NET_all_replicates": bool(np.all(ratio + 1e-9 >= nets)) if np.all(rlhs <= 1.0 + 1e-12) else None}
    return out


def verdict(res: dict, v_repro_ok: bool, v_slot_ok: bool, v_rel_ok: bool):
    """Mechanical.  STOP (V-REPRO) > VOID (V-SLOT, V-REL) > CLOSE iff CI_hi(RAW_worst / RL(CTRL-HIT)) < 1.0 pp > MODEL-STUDY iff CI_lo(NET-CEIL) >= 1.0 pp > BETWEEN."""
    if not v_repro_ok:
        return "STOP"
    if not (v_slot_ok and v_rel_ok):
        return "VOID"
    close = res["RAW_over_RL_hi_incl_inf"] < BAR_PP
    study = res["NET_CEIL_pp_CI"][0] >= BAR_PP
    assert not (close and study), "CLOSE and MODEL-STUDY fired together"
    return "CLOSE" if close else "MODEL-STUDY" if study else "BETWEEN"
